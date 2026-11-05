"""Filtering, quality evaluation, curriculum balancing, and HITL review nodes."""
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


class EvaluationNodeMixin:
    """Mixin providing quality filtering, LLM-as-judge evaluation, human-in-the-loop review, and curriculum balance."""

    async def _filter_node(self, state: AgentState) -> AgentState:
        """Enhanced filtering with adaptive thresholds."""
        job = state["job"]
        job_id = job["id"]
        extracted = state["extracted_content"]
        intent = state["intent"]

        self._update_job_status(job_id, "filter", 0.5)

        from pipeline.filtering import FilteringPipeline

        filtering_config = {**self.config, **job["config"]}
        filtering = FilteringPipeline(self.router, filtering_config)
        filtered = []

        target_domain = (intent.domain if intent else "") or job["config"].get("target_domain", "")

        # NOTE: Thresholds are now STATIC (see pipeline/quality_breakdown.py)
        # No runtime learning — ensures deterministic scoring across runs

        # Process in batches for parallel I/O and event loop responsiveness
        BATCH_SIZE = 5
        for batch_start in range(0, len(extracted), BATCH_SIZE):
            if self._is_cancelled(job_id):
                break
            await asyncio.sleep(0)  # Yield to event loop

            batch = extracted[batch_start:batch_start + BATCH_SIZE]
            from types import SimpleNamespace
            content_objs = [SimpleNamespace(**d) for d in batch]

            # Add batch diagnostic logging
            logger.info(
                f"[{job_id}] Filter batch {batch_start // BATCH_SIZE + 1}: "
                f"{len(batch)} items | "
                f"first item keys: {list(batch[0].keys()) if batch else 'empty'}"
            )

            batch_start_time = asyncio.get_event_loop().time()

            filter_timeout = job["config"].get("filter_timeout_seconds", 90)

            filter_tasks = [
                asyncio.wait_for(
                    filtering.filter(content, intent, return_all=True),
                    timeout=filter_timeout
                )
                for content in content_objs
            ]
            batch_results = await asyncio.gather(*filter_tasks, return_exceptions=True)

            # Add batch result logging
            exc_count  = sum(1 for r in batch_results if isinstance(r, Exception))
            pass_count = sum(
                1 for r in batch_results
                if not isinstance(r, Exception) and r and getattr(r, "passed", False)
            )
            logger.info(
                f"[{job_id}] Batch result: "
                f"{pass_count} passed | "
                f"{exc_count} exceptions | "
                f"{len(batch_results) - pass_count - exc_count} failed quality"
            )

            for content_dict, result in zip(batch, batch_results):
                source_url = content_dict.get("url", "unknown")
                start_time = asyncio.get_event_loop().time()

                try:
                    if isinstance(result, Exception):
                        logger.error(
                            f"[{job_id}] Filter exception for {source_url}: "
                            f"{type(result).__name__}: {result}",
                            exc_info=result,
                        )
                        self.observability.log_pipeline_stage(
                            job_id=job_id,
                            stage="filtering",
                            source_url=source_url,
                            duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
                            decision="failed",
                            issues=[f"{type(result).__name__}: {result}"],
                        )
                        state["warnings"].append(
                            f"Filter exception [{source_url}]: {type(result).__name__}: {result}"
                        )
                        logger.info(
                                f"[{job_id}] Filter score | url={source_url[:60]} | "
                                        f"quality={getattr(result, 'quality_score', 'N/A'):.3f} | "
                                        f"relevance={getattr(result, 'relevance_score', 'N/A'):.3f} | "
                                        f"passed={getattr(result, 'passed', 'N/A')} | "
                                        f"issues={getattr(result, 'issues', [])}"
                                        if result and not isinstance(result, Exception) else
                                        f"[{job_id}] Filter result is None or Exception for {source_url}"
                        )
                        continue

                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    if result and result.passed:
                        filtered.append({
                            "content": result.content,
                            "quality_score": result.quality_score,
                            "relevance_score": result.relevance_score,
                            "toxicity_score": result.toxicity_score,
                            "hallucination_risk": result.hallucination_risk,
                            "uniqueness_score": result.uniqueness_score,
                            "issues": result.issues,
                            "warnings": result.warnings,
                            "source_url": result.source_url,
                            "metadata": content_dict.get("metadata", {}) or {},
                            "confidence": result.confidence,
                        })
                        decision = "accepted"
                    else:
                        decision = "rejected"

                    self.observability.log_pipeline_stage(
                        job_id=job_id,
                        stage="filtering",
                        source_url=source_url,
                        duration_ms=duration_ms,
                        decision=decision,
                        quality_score=result.quality_score if result else 0.0,
                        threshold=filtering.quality_threshold,
                        issues=result.issues if result else [],
                        metadata={
                            "relevance_score": result.relevance_score if result else 0.0,
                            "toxicity_score": result.toxicity_score if result else 0.0,
                            "uniqueness_score": result.uniqueness_score if result else 0.0,
                            "filter_reason": getattr(result, "filter_reason", "unknown") if result else "unknown"
                        }
                    )
                except Exception as e:
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    self.observability.log_pipeline_stage(
                        job_id=job_id,
                        stage="filtering",
                        source_url=source_url,
                        duration_ms=duration_ms,
                        decision="failed",
                        issues=[str(e)]
                    )

        # Score-based bypass for zero-sample situations
        # Check domain relevance of extracted items before bypassing
        if len(filtered) == 0 and len(extracted) > 0:
            analyzer = ConstraintAnalyzer(job["config"])
            raw_input = intent.raw_input if intent else job["config"].get("raw_input", "")
            relevant_extracted = [
                item for item in extracted
                if analyzer._is_source_domain_relevant(item, target_domain, raw_input=raw_input)
            ]

            if relevant_extracted:
                logger.warning(
                    f"[{job_id}] Filtering resulted in zero samples. "
                    f"Applying score-based bypass on {len(relevant_extracted)} domain-relevant items."
                )
                sorted_extracted = sorted(
                    relevant_extracted,
                    key=lambda x: x.get("quality_score", 0),
                    reverse=True
                )
                filtered = sorted_extracted[:min(10, len(sorted_extracted))]
                for sample in filtered:
                    sample["filter_bypassed"] = True
                    sample["bypass_reason"] = "zero_sample_situation"
            else:
                logger.warning(
                    f"[{job_id}] No extracted items passed relevance checks for '{target_domain}'. "
                    "Continuing with no samples because source-grounded generation is required."
                )
                filtered = []

        self._update_job_status(
            job_id,
            "filter",
            0.7,
            samples_filtered=len(filtered)
        )

        # Check if we need to adapt strategy
        if len(filtered) < 10 and state.get("low_resource_mode"):
            state["should_retry"] = True
            state["adaptation_notes"].append("Low resource mode: few samples passed filter, adapting strategy")

        return {
            **state,
            "filtered_samples": filtered,
            "current_stage": "filter",
            "progress": 0.5,
            "messages": [f"Filtered to {len(filtered)} quality samples"],
        }

    async def _quality_eval_node(self, state: AgentState) -> AgentState:
        """Quality evaluation gate verifying synthesized samples before HITL / Balancing."""
        job = state["job"]
        job_id = job["id"]
        config = job.get("config", {})
        samples = state.get("constructed_samples", [])

        # Enforce deduplication before scoring and certification
        seen_eval_keys = set()
        deduped_eval_samples = []
        for s in samples:
            if not isinstance(s, dict):
                continue
            norm_k = " ".join(f"{s.get('instruction', '')} {s.get('response', '')}".lower().split())
            if norm_k in seen_eval_keys:
                continue
            seen_eval_keys.add(norm_k)
            deduped_eval_samples.append(s)
        samples = deduped_eval_samples

        target_dataset_size = int(config.get("dataset_size") or config.get("target_samples") or 0)
        if target_dataset_size > 0 and len(samples) < target_dataset_size and len(samples) > 0:
            samples = self._top_up_exact_quota(samples, target_dataset_size, seen_eval_keys)

        state["constructed_samples"] = samples

        self._update_job_status(job_id, "quality_eval", 0.72)

        user_prompt = config.get("raw_input") or config.get("prompt") or config.get("target_domain", "")
        target_domain_str = config.get("target_domain", "")

        # Optional provider-diverse review runs after construction, where each
        # candidate has its source excerpt and before the existing HITL gate.
        ensemble_reviewed = 0
        if config.get("llm_review_enabled", False) and samples:
            try:
                from pipeline.review_ensemble import ReviewEnsemble

                panel = ReviewEnsemble(
                    self.router,
                    providers=config.get("llm_review_providers"),
                    approval_threshold=float(config.get("llm_review_threshold", 0.75)),
                    minimum_consensus=float(config.get("llm_review_consensus", 0.80)),
                    max_concurrency=int(config.get("llm_review_concurrency", 3)),
                )
                review_limit = max(1, int(config.get("llm_review_sample_limit", 50)))

                async def review_candidate(sample: dict) -> None:
                    verdict = await panel.review(
                        str(sample.get("instruction", "")),
                        str(sample.get("response", "")),
                        source=str(sample.get("source_text", "")),
                        domain=target_domain_str,
                    )
                    sample.setdefault("metadata", {})["review_ensemble"] = verdict.to_dict()
                    sample["llm_review_score"] = verdict.score
                    sample["needs_human_review"] = verdict.needs_human_review

                await asyncio.gather(
                    *(review_candidate(sample) for sample in samples[:review_limit] if isinstance(sample, dict))
                )
                ensemble_reviewed = min(len(samples), review_limit)
            except Exception as review_error:
                logger.warning("[%s] LLM review ensemble failed; using normal quality/HITL gates: %s", job_id, review_error)

        # Every sample now gets a uniform provenance record. Strict grounded
        # jobs cannot pass quality evaluation with synthetic/unattributed data.
        from pipeline.provenance import attach_provenance, has_reference_provenance
        strict_provenance = bool(config.get("require_reference_sources", False))
        missing_reference_count = 0
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            attach_provenance(sample)
            if strict_provenance and not has_reference_provenance(sample):
                sample["needs_human_review"] = True
                missing_reference_count += 1

        evidence_context = []
        if self.agent_registry:
            try:
                from agents.base import AgentContext, AgentType
                context_agent = self.agent_registry.create_agent(AgentType.CONTEXT)
                if context_agent:
                    result = await context_agent.execute(
                        {"items": samples, "max_items": config.get("context_max_sources", 50)},
                        AgentContext(job_id=job_id, dataset_id=job_id, domain=target_domain_str),
                    )
                    if result.success and isinstance(result.output, dict):
                        evidence_context = result.output.get("evidence", [])
            except Exception as context_error:
                logger.debug("Context agent skipped: %s", context_error)

        topic_scores = []
        grounding_scores = []
        clarity_scores = []
        completeness_scores = []
        domain_scores = []

        for s in samples:
            if not isinstance(s, dict):
                continue
            inst = str(s.get("instruction", "")).strip()
            resp = str(s.get("response", "")).strip()
            t_score = s.get("topic_score")
            if t_score is None:
                t_score = self._compute_sample_lexical_topic_relevance(inst, resp, user_prompt, target_domain_str)
                s["topic_score"] = t_score
            if t_score is not None:
                topic_scores.append(t_score)
            
            # Grounding: only append if real score is available
            g_val = s.get("llm_review_score") or s.get("quality_score")
            if g_val is not None:
                try:
                    grounding_scores.append(float(g_val))
                except (ValueError, TypeError):
                    pass

            # Clarity & completeness: unmeasured heuristics should not be derived from length alone
            # Domain: unmeasured unless real scorer evaluated it

        avg_topic = (sum(topic_scores) / len(topic_scores)) if topic_scores else None
        avg_grounding = (sum(grounding_scores) / len(grounding_scores)) if grounding_scores else None
        avg_clarity = None
        avg_completeness = None
        avg_domain = None

        quality_breakdown = {
            "topic_fidelity": round(avg_topic, 3) if avg_topic is not None else None,
            "source_grounding": round(avg_grounding, 3) if avg_grounding is not None else None,
            "instruction_clarity": None,
            "response_completeness": None,
            "domain_correctness": None,
        }
        
        measured_values = [v for v in [avg_topic, avg_grounding] if v is not None]
        composite_score = round(sum(measured_values) / len(measured_values), 3) if measured_values else None
        quality_breakdown["composite"] = composite_score

        # F2: BLOCK "Ready" + DBOM certification when sampled topic fidelity is below 80% (0.80)
        passed = (
            (len(samples) > 0)
            and (avg_topic is not None and avg_topic >= 0.80)
            and (composite_score is not None and composite_score >= 0.65)
            and missing_reference_count == 0
        )

        # Persist breakdown into job metadata and dataset record
        job_meta = job.setdefault("metadata", {})
        job_meta["quality_breakdown"] = quality_breakdown
        # A failed gate must NOT persist a passing mean
        if passed:
            job_meta["quality_score"] = composite_score
            job["quality_score"] = composite_score
        else:
            job_meta["quality_score"] = None
            job["quality_score"] = None

        retries = int(state.get("synthesis_retries", 0))
        if not passed:
            retries += 1
            logger.warning(
                f"[{job_id}] Quality Eval topic fidelity gate FAILED (attempt {retries}): topic_fidelity={avg_topic} (<0.80) or composite={composite_score}. "
                "Marking for HITL review."
            )
        else:
            logger.info(
                f"[{job_id}] Quality Eval PASSED: topic_fidelity={avg_topic:.2f}, composite={composite_score:.2f}"
            )

        return {
            **state,
            "quality_eval_passed": passed,
            "synthesis_retries": retries,
            "quality_breakdown": quality_breakdown,
            "quality_score": composite_score if passed else None,
            "missing_reference_count": missing_reference_count,
            "evidence_context": evidence_context,
            "current_stage": "quality_eval",
            "progress": 0.75,
            "messages": [
                f"Quality eval (topic_fidelity={avg_topic}, composite={composite_score}, "
                f"ensemble_reviewed={ensemble_reviewed}, missing_references={missing_reference_count}, pass={passed})"
            ],
        }

    def _quality_eval_check(self, state: AgentState) -> str:
        """Route conditionally after quality evaluation."""
        if state.get("quality_eval_passed", True):
            return "pass"
        retries = int(state.get("synthesis_retries", 0))
        if retries <= 1:
            return "retry_synthesis"
        return "pass"

    async def _balance_node(self, state: AgentState) -> AgentState:
        """Balanced Dataset Engine: curriculum tiers, topic spread, exact sample size guarantee."""
        job = state["job"]
        job_id = job["id"]
        config = job.get("config", {})
        raw_samples = state.get("constructed_samples", [])

        self._update_job_status(job_id, "balance", 0.88)

        target_size = int(config.get("dataset_size") or config.get("target_samples") or (len(raw_samples) or 100))
        balanced, report = self._balance_samples(
            raw_samples,
            config.get("balance_dimensions", ["topic", "language", "source", "difficulty"]),
            config.get("language", "en"),
            target_size=target_size,
        )

        if target_size > 0 and len(balanced) < target_size and len(balanced) > 0:
            seen_balance_keys = {
                " ".join(f"{s.get('instruction', '')} {s.get('response', '')}".lower().split())
                for s in balanced if isinstance(s, dict)
            }
            balanced = self._top_up_exact_quota(balanced, target_size, seen_balance_keys)

        logger.info(f"[{job_id}] Balanced Dataset Engine: guaranteed {len(balanced)} rows (target: {target_size})")

        return {
            **state,
            "constructed_samples": balanced,
            "balance_report": report,
            "current_stage": "balance",
            "progress": 0.90,
            "messages": [f"Balanced Dataset Engine guaranteed exact {len(balanced)} rows across curriculum tiers"],
        }

    async def _human_review_node(self, state: AgentState) -> AgentState:
        """
        Human-in-the-loop (HITL) gate.

        1. Submits a deterministic stratified sample to the persistent review queue.
        2. If `human_review_mode` is "blocking" (default when human_review=True),
           pauses the pipeline and awaits a reviewer calling
           POST /api/review/jobs/{job_id}/resume.
        3. Once resumed, marks the job approved and continues to export.

        Config keys:
          human_review        (bool, default False) — enable sampled HITL review
          human_review_mode   (str)  — "blocking" | "async"
            blocking: wait for explicit /resume call (real HITL)
            async:    submit for review but continue immediately
          hitl_timeout_seconds (int) — max seconds to wait (0 = unlimited)
        """
        job = state["job"]
        job_id = job["id"]
        config = job.get("config", {})
        samples = state.get("constructed_samples", [])

        # Enforce deduplication before scoring and certification
        seen_eval_keys = set()
        deduped_eval_samples = []
        for s in samples:
            if not isinstance(s, dict):
                continue
            norm_k = " ".join(f"{s.get('instruction', '')} {s.get('response', '')}".lower().split())
            if norm_k in seen_eval_keys:
                continue
            seen_eval_keys.add(norm_k)
            deduped_eval_samples.append(s)
        samples = deduped_eval_samples

        target_dataset_size = int(config.get("dataset_size") or config.get("target_samples") or 0)
        if target_dataset_size > 0 and len(samples) < target_dataset_size and len(samples) > 0:
            samples = self._top_up_exact_quota(samples, target_dataset_size, seen_eval_keys)

        state["constructed_samples"] = samples
        constructed_count = len(samples)
        config = job.get("config", {})

        quality_eval_passed = state.get("quality_eval_passed", True)
        hitl_enabled = config.get("human_review", True)  # Route stratified audit sample to review queue by default
        hitl_mode = config.get("human_review_mode", "blocking" if not quality_eval_passed else "async")
        hitl_timeout = int(config.get("hitl_timeout_seconds", 0))
        review_percentage = float(config.get("human_review_percentage", 10.0))
        if review_percentage <= 0:
            review_percentage = 10.0

        # Draw a deterministic, approximately stratified audit sample so the
        # same job always presents the same examples if its state is replayed.
        review_samples = []
        if samples and hitl_enabled and review_percentage > 0:
            import hashlib
            from collections import defaultdict
            strata = defaultdict(list)
            for sample in samples:
                metadata = sample.get("metadata", {}) or {}
                key = (
                    str(metadata.get("topic") or metadata.get("domain") or "unclassified"),
                    str(metadata.get("language") or config.get("language", "unknown")),
                    str(sample.get("difficulty_tier", "unknown")),
                )
                strata[key].append(sample)
            ordered_keys = sorted(
                strata,
                key=lambda key: hashlib.sha256(f"{job_id}:{key}".encode()).hexdigest(),
            )
            buckets = {
                key: sorted(
                    strata[key],
                    key=lambda item: hashlib.sha256(
                        f"{job_id}:{item.get('instruction', '')}:{item.get('response', '')}".encode()
                    ).hexdigest(),
                )
                for key in ordered_keys
            }
            target = min(len(samples), max(1, round(len(samples) * review_percentage / 100)))
            # Allocate review slots roughly in proportion to stratum size. The
            # previous round-robin gave every stratum the same number of slots,
            # which heavily over-sampled rare topics when group sizes differed.
            # When the requested audit is large enough, reserve one slot for
            # each stratum before distributing the remaining slots by size.
            allocations = {key: 0 for key in ordered_keys}
            if target >= len(ordered_keys):
                allocations.update({key: 1 for key in ordered_keys})
                remaining = target - len(ordered_keys)
                capacity = {key: len(buckets[key]) - 1 for key in ordered_keys}
                total_capacity = sum(capacity.values())
                if remaining and total_capacity:
                    exact = {
                        key: remaining * capacity[key] / total_capacity
                        for key in ordered_keys
                    }
                    for key in ordered_keys:
                        extra = min(capacity[key], int(exact[key]))
                        allocations[key] += extra
                    unassigned = target - sum(allocations.values())
                    for key in sorted(
                        ordered_keys,
                        key=lambda item: (-(exact[item] - int(exact[item])), ordered_keys.index(item)),
                    ):
                        if unassigned <= 0:
                            break
                        if allocations[key] < len(buckets[key]):
                            allocations[key] += 1
                            unassigned -= 1
            else:
                # If there are more strata than review slots, choose strata
                # deterministically and uniformly via their job-scoped hashes.
                for key in ordered_keys[:target]:
                    allocations[key] = 1

            for key in ordered_keys:
                review_samples.extend(buckets[key][:allocations[key]])

            # Confidence-based flagging: automatically route low-quality or high-hallucination samples to HITL review
            seen_sample_ids = {id(s) for s in review_samples}
            for s in samples:
                if id(s) not in seen_sample_ids:
                    q_score = float(s.get("quality_score", 1.0) or 1.0)
                    h_risk = float(s.get("hallucination_risk", 0.0) or 0.0)
                    if q_score < 0.70 or h_risk > 0.40 or s.get("needs_human_review", False):
                        review_samples.append(s)
                        seen_sample_ids.add(id(s))

        # Cap review_samples to strictly respect the configured HITL sampling ratio
        max_review_quota = min(len(samples), max(1, round(len(samples) * review_percentage / 100)))
        review_samples = review_samples[:max_review_quota]

        submitted = 0
        review_service = None
        review_ids = {}

        # Add the arbiter's uncertainty routing to the stratified sample. The
        # ReviewService remains the only component that can approve/edit data.
        if self.agent_registry and samples:
            try:
                from agents.base import AgentContext, AgentType
                arbiter = self.agent_registry.create_agent(AgentType.HUMAN_ARBITER)
                if arbiter:
                    decision = await arbiter.execute(
                        {"samples": samples},
                        AgentContext(job_id=job_id, dataset_id=job_id, domain=str(config.get("target_domain", ""))),
                    )
                    if decision.success:
                        for candidate in (decision.output or {}).get("review_candidates", []):
                            if candidate not in review_samples:
                                review_samples.append(candidate)
            except Exception as arbiter_error:
                logger.debug("Human arbiter agent skipped: %s", arbiter_error)

        if hitl_enabled and review_samples:
            # ── Resolve the ReviewService ──────────────────────────────
            # Try to get the shared instance from app state first
            try:
                # When running inside the FastAPI lifespan, the service is
                # stored as a module-level singleton via _review_service_instance.
                from core import _review_service_instance  # type: ignore
                review_service = _review_service_instance
            except (ImportError, AttributeError):
                review_service = None

            if review_service is None and (getattr(self, "db_manager", None) or getattr(getattr(self, "db", None), "db", None)):
                try:
                    from core.review_service import ReviewService
                    db_mgr = getattr(self, "db_manager", None) or getattr(getattr(self, "db", None), "db", None)
                    review_service = ReviewService(db_mgr)
                    self.review_service = review_service
                except Exception:
                    review_service = None
            elif review_service is not None:
                self.review_service = review_service

            if review_service is not None:
                for sample in review_samples:
                    try:
                        import hashlib
                        sample_review_id = hashlib.sha256(
                            f"{job_id}:{sample.get('instruction', '')}:{sample.get('response', '')}".encode()
                        ).hexdigest()
                        await review_service.submit(
                            instruction=sample.get("instruction", ""),
                            response=sample.get("response", ""),
                            job_id=job_id,
                            dataset_id=sample_review_id,
                            source_url=sample.get("metadata", {}).get("source_url", ""),
                            source_text=sample.get("source_text", ""),
                            quality_score=float(sample.get("quality_score", 0.5)),
                            hallucination_risk=float(sample.get("hallucination_risk", 0.0)),
                            duplicate_score=float(sample.get("duplicate_score", 0.0)),
                            diversity_score=float(sample.get("diversity_score", 0.0)),
                            metadata=sample.get("metadata", {}),
                        )
                        review_ids[sample_review_id] = sample
                        submitted += 1
                    except Exception as sub_err:
                        logger.warning("Failed to submit sample for review: %s", sub_err)

                logger.info("Job %s: submitted %d/%d stratified audit samples (%.1f%% requested, mode=%s)",
                            job_id, submitted, constructed_count, review_percentage, hitl_mode)
            else:
                logger.warning(
                    f"Job {job_id} requested a human review audit, but the review service is unavailable. Proceeding."
                )

        # ── Blocking HITL gate ─────────────────────────────────────────
        approved = False
        if hitl_enabled and hitl_mode == "blocking" and review_service is not None and review_ids:
            # Update DB status so the UI shows the job is paused
            try:
                if self.db_manager:
                    await self.db_manager.update_job(
                        job_id,
                        status=JobStatus.AWAITING_REVIEW.value,
                        current_stage="human_review",
                    )
            except Exception:
                pass

            event = await review_service.pause_job_for_review(job_id)
            logger.info("Job %s paused at HITL gate — waiting for reviewer", job_id)

            try:
                loop = asyncio.get_running_loop()
                deadline = loop.time() + hitl_timeout if hitl_timeout > 0 else None
                # Review decisions are stored in the shared database, but a
                # Celery worker and the API process have separate asyncio
                # events. Poll the DB periodically so API-side approvals also
                # release jobs running in another process.
                poll_interval = 2.0
                while True:
                    remaining = deadline - loop.time() if deadline is not None else None
                    if remaining is not None and remaining <= 0:
                        raise asyncio.TimeoutError
                    wait_seconds = min(poll_interval, remaining) if remaining is not None else poll_interval
                    try:
                        await asyncio.wait_for(event.wait(), timeout=wait_seconds)
                    except asyncio.TimeoutError:
                        # A timeout is a polling tick unless the configured
                        # overall HITL deadline has actually elapsed.
                        if deadline is not None and loop.time() >= deadline:
                            raise

                    queue = await review_service.get_queue(job_id=job_id, page=1, page_size=500)
                    review_items = list(queue.get("items", []))
                    for page in range(2, queue.get("total_pages", 1) + 1):
                        more = await review_service.get_queue(job_id=job_id, page=page, page_size=500)
                        review_items.extend(more.get("items", []))
                    by_review_id = {
                        str(item.get("dataset_id", "")): item
                        for item in review_items
                        if str(item.get("dataset_id", "")) in review_ids
                    }
                    pending = [
                        sample_id for sample_id in review_ids
                        if by_review_id.get(sample_id, {}).get("review_status") in {None, "pending"}
                    ]
                    if not pending:
                        break
                    logger.info("Job %s still has %d pending review samples", job_id, len(pending))
                    event = await review_service.pause_job_for_review(job_id)
                    if self.db_manager:
                        await self.db_manager.update_job(
                            job_id, status=JobStatus.AWAITING_REVIEW.value, current_stage="human_review"
                        )

                approved = True
            except asyncio.TimeoutError:
                logger.warning("Job %s HITL timeout (%ds) — pending reviewed examples will be excluded", job_id, hitl_timeout)
                approved = True
                await review_service.resume_job(job_id)
                queue = await review_service.get_queue(job_id=job_id, page=1, page_size=500)
                review_items = list(queue.get("items", []))
                for page in range(2, queue.get("total_pages", 1) + 1):
                    more = await review_service.get_queue(job_id=job_id, page=page, page_size=500)
                    review_items.extend(more.get("items", []))
                by_review_id = {
                    str(item.get("dataset_id", "")): item
                    for item in review_items
                    if str(item.get("dataset_id", "")) in review_ids
                }
        else:
            # async mode or service unavailable — continue without waiting
            approved = True

        if hitl_enabled and hitl_mode == "blocking" and review_service is not None and review_ids:
            retained_samples = []
            rejected_count = 0
            edited_count = 0
            duplicate_count = 0
            reviewed_sample_ids = {id(sample): sample_id for sample_id, sample in review_ids.items()}
            retained_sample_keys = set()
            for sample in samples:
                sample_id = reviewed_sample_ids.get(id(sample))
                if sample_id:
                    item = by_review_id.get(sample_id, {})
                    if item.get("review_status") != "approved":
                        rejected_count += 1
                        continue
                    edited_instruction = str(item.get("edited_instruction") or "").strip()
                    edited_response = str(item.get("edited_response") or "").strip()
                    if edited_instruction:
                        sample["instruction"] = edited_instruction
                    if edited_response:
                        sample["response"] = edited_response

                instruction_key = " ".join(str(sample.get("instruction", "")).casefold().split())
                response_key = " ".join(str(sample.get("response", "")).casefold().split())
                if not instruction_key or not response_key:
                    rejected_count += 1
                    continue
                sample_key = (instruction_key, response_key)
                if sample_key in retained_sample_keys:
                    duplicate_count += 1
                    rejected_count += int(sample_id is not None)
                    continue
                retained_sample_keys.add(sample_key)
                if sample_id and by_review_id.get(sample_id, {}).get("review_decision") == "edit":
                    edited_count += 1
                retained_samples.append(sample)
            samples = retained_samples
            retained_review_count = len(review_ids) - rejected_count
            logger.info("Job %s resumed after HITL approval", job_id)
            state["messages"].append(
                f"Review decisions applied: {rejected_count} rejected or unresolved, "
                f"{duplicate_count} duplicate edits removed, {edited_count} edited, "
                f"{retained_review_count} retained (including edits)."
            )

        return {
            **state,
            "constructed_samples": samples,
            "human_approval_needed": hitl_enabled and bool(review_samples),
            "human_approved": approved,
            "messages": [
                f"HITL audit: {submitted}/{constructed_count} samples submitted "
                f"({review_percentage:.1f}% requested), "
                f"mode={hitl_mode}, approved={approved}"
            ],
        }

    def _human_approval_check(self, state: AgentState) -> str:
        """Check if human approved. Defaults to approved (samples queued for review)."""
        if state.get("human_review_pending") and state.get("human_explicitly_rejected"):
            return "rejected"
        return "approved"
