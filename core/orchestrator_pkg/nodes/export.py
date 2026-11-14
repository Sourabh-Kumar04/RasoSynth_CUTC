"""Export node for DatasetOrchestrator."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import operator
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator, Dict, List, Optional, Set, Tuple, TypedDict

from core.config import get_settings
from core.intent import IntentExtractionError, UserIntent
from core.intent_extractor import extract_intent
from core.orchestrator_pkg.constraint_analyzer import ConstraintAnalyzer
from core.orchestrator_pkg.state import (
    AgentState,
    Job,
    JobStatus,
    ConstraintAnalysis,
    _sanitize_metadata,
    _json_safe,
)

logger = logging.getLogger(__name__)


class ExportNodeMixin:
    """Mixin providing dataset export, versioning, package bundling, and ADR-002 manifest generation."""

    async def _export_node(self, state: AgentState) -> AgentState:
        """Export stage."""
        job = state["job"]
        job_id = job["id"]
        raw_samples = state["constructed_samples"]

        self._update_job_status(job_id, "export", 0.9)

        from pipeline.export import ExportPipeline, ExportConfig

        # Build export config from job config + global settings
        job_config = job.get("config", {})
        requested_samples = int(job_config.get("dataset_size") or job_config.get("target_samples") or 0)
        if requested_samples <= 0:
            requested_samples = len(raw_samples)

        # Multi-dimensional balancing is enabled by default to prevent category/length bias,
        # with our strict sample-count preservation ensuring exact quota delivery.
        enable_balancing = bool(job_config.get("enable_balancing", True))
        if enable_balancing:
            balanced_subset, balance_report = self._balance_samples(
                raw_samples,
                job_config.get("balance_dimensions", ["topic", "language", "source", "difficulty"]),
                job_config.get("language", "en"),
                target_size=requested_samples,
            )
            raw_samples = balanced_subset
        else:
            balance_report = {
                "balancing_passes": 0,
                "samples_before": len(raw_samples),
                "samples_after": len(raw_samples),
                "samples_removed": 0,
            }

        # Exact target size guarantee: backfill or trim to hit requested_samples exactly
        if requested_samples > 0:
            if len(raw_samples) > requested_samples:
                raw_samples = raw_samples[:requested_samples]
            elif len(raw_samples) < requested_samples and (job_config.get("generation_mode") != "strict_source" or job_config.get("allow_seedless_generation")):
                needed = requested_samples - len(raw_samples)
                logger.info(f"Export stage: backfilling {needed} samples to reach exact requested target {requested_samples}")
                plan_dict = state.get("dataset_plan")
                if plan_dict:
                    from pipeline.planner import DatasetPlan
                    from pipeline.synthetic_generator import SeedlessGenerator
                    plan_obj = DatasetPlan(**plan_dict)
                    generator = SeedlessGenerator(self.router, job_config)
                    backfill_attempts = 0
                    max_backfill_attempts = max(needed * 4, 20)
                    while len(raw_samples) < requested_samples and backfill_attempts < max_backfill_attempts:
                        backfill_attempts += 1
                        try:
                            sample = await generator.generate_sample(plan_obj, {}, cell_index=len(raw_samples), total_cells=requested_samples)
                            if sample and sample.instruction and sample.response:
                                raw_samples.append({
                                    "instruction": sample.instruction,
                                    "response": sample.response,
                                    "input": sample.input,
                                    "conversation": getattr(sample, "conversation", None),
                                    "metadata": sample.metadata,
                                    "difficulty_tier": sample.difficulty_tier,
                                    "curriculum_order": len(raw_samples),
                                })
                        except Exception as backfill_err:
                            logger.warning(f"Backfill generation error: {backfill_err}")

        # Strict deduplication before certification: Remove any duplicate instruction+response pairs
        seen_canonical = set()
        deduped = []
        for s in raw_samples:
            inst = getattr(s, "instruction", "") if not isinstance(s, dict) else s.get("instruction", "")
            resp = getattr(s, "response", "") if not isinstance(s, dict) else s.get("response", "")
            key = " ".join(f"{inst} {resp}".lower().split())
            if key in seen_canonical:
                continue
            seen_canonical.add(key)
            deduped.append(s)
        raw_samples = deduped

        # Final exact quota delivery: replenish any deficit post-dedup, or cap if over target
        if requested_samples > 0:
            if len(raw_samples) < requested_samples and len(raw_samples) > 0:
                raw_samples = self._top_up_exact_quota(raw_samples, requested_samples, seen_canonical, job_config=job_config)
            elif len(raw_samples) > requested_samples:
                raw_samples = raw_samples[:requested_samples]

        # F2 Enforced Dedup Gate: Never certify a dataset with exact duplicates inside
        final_seen = set()
        strictly_unique = []
        for s in raw_samples:
            inst = getattr(s, "instruction", "") if not isinstance(s, dict) else s.get("instruction", "")
            resp = getattr(s, "response", "") if not isinstance(s, dict) else s.get("response", "")
            key = " ".join(f"{inst} {resp}".lower().split())
            if key in final_seen:
                continue
            final_seen.add(key)
            strictly_unique.append(s)
        if len(strictly_unique) < len(raw_samples):
            logger.warning(
                f"[{job_id}] Dropped {len(raw_samples) - len(strictly_unique)} duplicate samples before DBOM certification."
            )
        raw_samples = strictly_unique

        balance_report["requested_samples"] = requested_samples
        balance_report["samples_short_of_target"] = max(0, requested_samples - len(raw_samples))

        # Carve stratified held-out evaluation split (after review decisions & deduplication)
        from core.evaluation.held_out_split import create_stratified_held_out_split, save_split_artifacts

        eval_floor_val = int(job_config.get("eval_floor", 1000))
        split_result = create_stratified_held_out_split(
            samples=raw_samples,
            job_id=job_id,
            floor=eval_floor_val,
            seed=job_config.get("seed"),
        )
        split_decision = split_result["decision"]
        balance_report["holdout_decision"] = split_decision

        # Train samples are exported to primary train path; val/test become job artifacts
        train_samples_raw = split_result["train"]
        from types import SimpleNamespace
        samples = [
            SimpleNamespace(**s) if isinstance(s, dict) else s
            for s in train_samples_raw
        ]
        # Multi-Agent Society: Consult StorageOptimizationAgent and DistributionAgent
        storage_opt_report = {}
        distribution_report = {}
        if self.agent_registry:
            try:
                from agents.base import AgentType, AgentContext
                ctx = AgentContext(job_id=job_id, dataset_id=job_id, domain=str(job_config.get("target_domain", "")))
                storage_agent = self.agent_registry.create_agent(AgentType.STORAGE)
                if storage_agent:
                    st_res = await storage_agent.execute({"dataset": raw_samples, "compression": "lz4"}, ctx)
                    if st_res and st_res.output:
                        storage_opt_report = st_res.output
                        logger.info("  ✓ StorageOptimizationAgent planned dataset sharding")

                dist_agent = self.agent_registry.create_agent(AgentType.DISTRIBUTION)
                if dist_agent:
                    destinations = []
                    if job_config.get("hf_dataset_org") or job_config.get("hf_token"):
                        destinations.append("huggingface")
                    if job_config.get("s3_bucket"):
                        destinations.append("aws_s3")
                    if not destinations:
                        destinations.append("local")
                    dt_res = await dist_agent.execute({"dataset": raw_samples, "destinations": destinations}, ctx)
                    if dt_res and dt_res.output:
                        distribution_report = dt_res.output
                        logger.info("  ✓ DistributionAgent prepared delivery channels: %s", destinations)
            except Exception as dist_err:
                logger.debug(f"Multi-agent export coordination skipped: {dist_err}")

        export_config = ExportConfig(
            format=job_config.get("export_format", "jsonl"),
            instruction_format=job_config.get("instruction_format", "alpaca"),
            output_dir=self.config.get("output_dir", "outputs"),
            dataset_name=job_config.get("dataset_name") or f"dataset_{job_id}",
            # Cloud export settings from global config
            s3_bucket=self.config.get("s3_bucket"),
            s3_region=self.config.get("s3_region", "us-east-1"),
            hf_dataset_org=self.config.get("hf_dataset_org"),
            hf_token=self.config.get("hf_token"),
            kaggle_username=self.config.get("kaggle_username"),
            kaggle_key=self.config.get("kaggle_key"),
        )

        exporter = ExportPipeline(export_config)
        export_result = await exporter.export(samples, job_id)

        # Save held-out validation and test splits as job artifacts alongside primary train file
        job_output_dir = Path(export_config.output_dir) / job_id
        save_split_artifacts(
            split_result,
            job_output_dir,
            base_filename=Path(str(export_result.get("dataset", "dataset.jsonl"))).name,
        )

        # Persist dataset and samples to database
        if self.db and samples:
            try:
                provenance_sources = []
                for source in state.get("sources", [])[:25]:
                    if not isinstance(source, dict):
                        continue
                    provenance_sources.append({
                        "url": str(source.get("url", "")),
                        "title": str(source.get("title", "")),
                        "source_type": str(source.get("source_type", "")),
                        "license": source.get("license"),
                    })
                used_sources_by_url = {}
                for sample in samples:
                    sample_metadata = getattr(sample, "metadata", None) or {}
                    if not isinstance(sample_metadata, dict):
                        continue
                    source_url = str(sample_metadata.get("source_url") or getattr(sample, "source_url", ""))
                    if not source_url or source_url in used_sources_by_url:
                        continue
                    used_sources_by_url[source_url] = {
                        "url": source_url,
                        "title": str(sample_metadata.get("source_title") or ""),
                        "source_type": str(sample_metadata.get("source_type") or ""),
                        "license": sample_metadata.get("license"),
                    }
                provenance = {
                    "user_query": str(job_config.get("target_domain", "")),
                    "improved_query": job_config.get("optimized_query"),
                    "search_queries": job_config.get("specialized_queries", []),
                    "query_plan": {
                        key: job_config.get("query_plan", {}).get(key)
                        for key in ("primary_task", "domain", "modality", "key_entities", "constraints")
                        if job_config.get("query_plan", {}).get(key) is not None
                    } if isinstance(job_config.get("query_plan"), dict) else {},
                    "generation_mode": job_config.get("generation_mode", "strict_source"),
                    "seedless_generation_allowed": bool(job_config.get("allow_seedless_generation", False)),
                    "language": job_config.get("language", "en"),
                    "dataset_type": job_config.get("dataset_type", "sft"),
                    "discovered_source_count": len(state.get("sources", [])),
                    "discovered_sources": provenance_sources,
                    "used_source_count": len(used_sources_by_url),
                    "used_sources": list(used_sources_by_url.values())[:25],
                    "human_review": {
                        "enabled": bool(job_config.get("human_review", False)),
                        "requested_percentage": float(job_config.get("human_review_percentage", 10.0)),
                    },
                }

                # Attach Cryptographic DBOM attestation
                metadata_dict = {
                    "export_path": str(export_result.get("dataset", "")),
                    "balance_report": balance_report,
                    "provenance": provenance,
                    "held_out_split": split_decision,
                    "holdout_decision": split_decision,
                    "train_count": split_decision.get("train_count", len(samples)),
                    "val_count": split_decision.get("val_count", 0),
                    "test_count": split_decision.get("test_count", 0),
                    "eval_flag": split_decision.get("flag"),
                }
                try:
                    from core.export.dbom_attestor import generate_dbom_attestation
                    synthesis_mode_val = str(job_config.get("synthesis_mode", "standard"))
                    dbom_cert = generate_dbom_attestation(
                        dataset_name=export_config.dataset_name,
                        samples=[
                            {
                                "instruction": s.get("instruction", "") if isinstance(s, dict) else getattr(s, "instruction", ""),
                                "response": s.get("response", "") if isinstance(s, dict) else getattr(s, "response", ""),
                                "input": (s.get("input", "") if isinstance(s, dict) else getattr(s, "input", "")) or "",
                                "metadata": (
                                    (s.get("metadata") or s.get("metadata_") or {})
                                    if isinstance(s, dict)
                                    else (getattr(s, "metadata", None) or getattr(s, "metadata_", None) or {})
                                ),
                            }
                            for s in samples
                        ],
                        domain=str(job_config.get("target_domain", "")),
                        language=str(job_config.get("language", "en")),
                        synthesis_mode=synthesis_mode_val,
                    )
                    metadata_dict["dbom"] = dbom_cert
                    metadata_dict["merkle_root_hash"] = dbom_cert.get("merkle_root_hash")
                    metadata_dict["merkle_root"] = dbom_cert.get("merkle_root_hash")
                    metadata_dict["certificate_id"] = dbom_cert.get("certificate_id")
                    if state.get("quality_breakdown"):
                        metadata_dict["quality_breakdown"] = state["quality_breakdown"]
                    if state.get("quality_score"):
                        metadata_dict["quality_score"] = state["quality_score"]
                    metadata_dict["synthesis_mode"] = synthesis_mode_val
                    export_file = str(export_result.get("dataset", ""))
                    if export_file and os.path.exists(export_file):
                        with open(f"{export_file}.dbom.json", "w", encoding="utf-8") as f:
                            json.dump(dbom_cert, f, indent=2)
                except Exception as dbom_err:
                    logger.warning("DBOM generation skipped in export node: %s", dbom_err)

                # ADR-002: Package dataset with DatasetPackager and generate PackageManifest
                package_manifest = None
                try:
                    from core.storage.packaging import DatasetPackager, PackagingConfig
                    packager = DatasetPackager(PackagingConfig())
                    package_manifest = await packager.package(
                        raw_samples,
                        dataset_name=export_config.dataset_name,
                        version="1.0.0"
                    )
                    metadata_dict["package_manifest"] = package_manifest.__dict__ if hasattr(package_manifest, "__dict__") else {}
                    metadata_dict["storage_optimization"] = storage_opt_report
                    metadata_dict["distribution"] = distribution_report
                    export_file = str(export_result.get("dataset", ""))
                    if export_file and os.path.exists(export_file):
                        with open(f"{export_file}.manifest.json", "w", encoding="utf-8") as f:
                            json.dump(metadata_dict["package_manifest"], f, indent=2, default=str)
                    logger.info("  ✓ ADR-002 DatasetPackager produced manifest with %d chunks", package_manifest.chunk_count)
                except Exception as pkg_err:
                    logger.debug(f"DatasetPackager skipped: {pkg_err}")

                # Trigger DeliveryManager for multi-cloud / HF delivery
                try:
                    from core.storage.delivery import DeliveryManager, DeliveryRequest, StorageProviderType, DeliveryStrategy
                    delivery_manager = DeliveryManager()
                    dest = StorageProviderType.HUGGINGFACE if (job_config.get("hf_dataset_org") or export_config.hf_dataset_org) else StorageProviderType.AWS_S3 if (job_config.get("s3_bucket") or export_config.s3_bucket) else None
                    if dest:
                        deliv_req = DeliveryRequest(
                            dataset_id=job_id,
                            dataset_name=export_config.dataset_name,
                            destination=dest,
                            strategy=DeliveryStrategy.DIRECT_DOWNLOAD,
                        )
                        deliv_info = await delivery_manager.deliver(deliv_req, raw_samples)
                        metadata_dict["delivery_info"] = {
                            "delivery_id": deliv_info.delivery_id,
                            "status": deliv_info.status.value,
                            "destination": dest.value,
                        }
                        logger.info("  ✓ DeliveryManager orchestrated delivery [%s] to %s", deliv_info.delivery_id, dest.value)
                except Exception as deliv_err:
                    logger.debug("DeliveryManager skipped: %s", deliv_err)

                # Create dataset record (ensure metadata is JSON serializable)
                json_safe_metadata = json.loads(json.dumps(metadata_dict, default=str))
                dataset_record = await self.db.create_dataset(
                    job_id=job_id,
                    name=export_config.dataset_name,
                    type=export_config.format,
                    size=len(samples),
                    metadata=json_safe_metadata,
                    output_path=str(export_result.get("dataset", ""))
                )

                # Persist the actual evidence window and an immutable dataset
                # version. Training consumes this version ID, never a mutable
                # "latest" output directory.
                evidence = []
                for sample in samples:
                    sample_metadata = getattr(sample, "metadata", {}) or {}
                    provenance_record = sample_metadata.get("provenance", {}) if isinstance(sample_metadata, dict) else {}
                    if provenance_record.get("kind") != "source":
                        continue
                    evidence.append({
                        "source_url": provenance_record.get("source_url"),
                        "source_hash": provenance_record.get("source_hash"),
                        "license": provenance_record.get("license"),
                        "citations": provenance_record.get("citations", []),
                    })
                context_evidence = state.get("evidence_context", [])
                if isinstance(context_evidence, list):
                    evidence.extend(item for item in context_evidence if isinstance(item, dict))
                unique_evidence = list({json.dumps(item, sort_keys=True): item for item in evidence}.values())
                context_payload = json.dumps(unique_evidence, sort_keys=True, default=str)
                context_hash = hashlib.sha256(context_payload.encode("utf-8")).hexdigest()
                context_bundle = await self.db.create_context_bundle(job_id, context_hash, unique_evidence)

                sample_fingerprint = "\n".join(
                    f"{getattr(sample, 'instruction', '')}\n{getattr(sample, 'response', '')}"
                    for sample in samples
                )
                content_hash = hashlib.sha256(sample_fingerprint.encode("utf-8")).hexdigest()
                version = await self.db.create_dataset_version(
                    dataset_id=dataset_record["id"],
                    version="1.0.0",
                    sample_count=len(samples),
                    content_hash=content_hash,
                    output_path=str(export_result.get("dataset", "")),
                    manifest={
                        "dataset_id": dataset_record["id"],
                        "context_bundle_id": context_bundle["id"],
                        "context_hash": context_hash,
                        "dbom": metadata_dict.get("dbom", {}),
                        "quality": state.get("quality_breakdown", {}),
                        "held_out_split": split_decision,
                    },
                )
                metadata_dict["dataset_version_id"] = version["id"]

                # Create sample records using batch ingestion
                sample_data = []
                for sample in samples:
                    meta = (
                        (sample.get("metadata") or sample.get("metadata_") or {})
                        if isinstance(sample, dict)
                        else (getattr(sample, "metadata", None) or getattr(sample, "metadata_", None) or {})
                    )
                    sample_data.append({
                        "instruction": sample.get("instruction", "") if isinstance(sample, dict) else getattr(sample, "instruction", ""),
                        "response": sample.get("response", "") if isinstance(sample, dict) else getattr(sample, "response", ""),
                        "input": sample.get("input", "") if isinstance(sample, dict) else getattr(sample, "input", ""),
                        "metadata": meta,
                        "quality_score": sample.get("quality_score", 0.5) if isinstance(sample, dict) else getattr(sample, "quality_score", 0.5),
                        "difficulty_tier": sample.get("difficulty_tier", 3) if isinstance(sample, dict) else getattr(sample, "difficulty_tier", 3),
                    })

                await self.db.create_samples(dataset_record["id"], sample_data)

            except Exception as db_error:
                logger.error(f"Failed to persist dataset to database: {db_error}")

        merkle_root_val = None
        if "metadata_dict" in locals() and isinstance(metadata_dict, dict):
            merkle_root_val = metadata_dict.get("merkle_root_hash")
        if not merkle_root_val and samples:
            try:
                from core.export.dbom_attestor import compute_sample_hash, compute_merkle_root
                leaf_hashes = [
                    compute_sample_hash({
                        "instruction": getattr(s, "instruction", "") if not isinstance(s, dict) else s.get("instruction", ""),
                        "response": getattr(s, "response", "") if not isinstance(s, dict) else s.get("response", ""),
                        "input": getattr(s, "input", "") if not isinstance(s, dict) else s.get("input", ""),
                        "metadata": (
                            (s.get("metadata") or s.get("metadata_") or {})
                            if isinstance(s, dict)
                            else (getattr(s, "metadata", None) or getattr(s, "metadata_", None) or {})
                        ),
                    })
                    for s in samples
                ]
                merkle_root_val = compute_merkle_root(leaf_hashes)
            except Exception:
                pass

        self._update_job_status(
            job_id,
            "completed" if samples else "failed",
            1.0,
            samples_generated=len(samples),
            quality_score=state.get("quality_score"),
            merkle_root=merkle_root_val,
        )

        return {
            **state,
            "constructed_samples": raw_samples,
            "balance_report": balance_report,
            "current_stage": "export",
            "progress": 1.0,
            "messages": [
                f"Balanced and exported {len(samples)} samples; removed {balance_report['samples_removed']} over-represented samples"
            ],
        }
