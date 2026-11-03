"""Jobs lifecycle, execution, preview, and download endpoints."""
from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
import logging
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from api.auth import (
    User,
    UserRole,
    get_auth_manager,
    get_current_user,
    get_current_user_optional,
    require_role,
)
from api.disk_resolver import resolve_dynamic_disk_dataset, _resolve_dynamic_disk_dataset
from api.legacy_schemas import JobDetailResponse, JobRequest, JobResponse
from api.schemas import JobStatus as JobStatusEnum
from api.security import (
    _enforce_owner,
    _sign_approved_examples,
    _sign_download_token,
    _verify_download_token,
)
from core.config import get_settings
from core.orchestrator_core import Job, JobStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Jobs"])

MAX_SAMPLE_LOAD_LIMIT = int(os.getenv("MAX_SAMPLE_LOAD_LIMIT", "10000"))
active_websockets: dict[str, list[WebSocket]] = {}


def _get_server_module():
    return sys.modules.get("api.server")


def _get_db(req: Optional[Request] = None):
    server_mod = _get_server_module()
    if req and hasattr(req, "app") and getattr(req.app.state, "db", None):
        return req.app.state.db
    return getattr(server_mod, "db", None) if server_mod else None


def _get_orchestrator(req: Optional[Request] = None):
    server_mod = _get_server_module()
    if req and hasattr(req, "app") and getattr(req.app.state, "orchestrator", None):
        return req.app.state.orchestrator
    return getattr(server_mod, "orchestrator", None) if server_mod else None


def _get_cache(req: Optional[Request] = None):
    server_mod = _get_server_module()
    if req and hasattr(req, "app") and getattr(req.app.state, "cache", None):
        return req.app.state.cache
    return getattr(server_mod, "cache", None) if server_mod else None


def _get_observability(req: Optional[Request] = None):
    server_mod = _get_server_module()
    if req and hasattr(req, "app") and getattr(req.app.state, "observability", None):
        return req.app.state.observability
    return getattr(server_mod, "observability", None) if server_mod else None


def _get_admission(req: Optional[Request] = None):
    server_mod = _get_server_module()
    if req and hasattr(req, "app") and getattr(req.app.state, "admission_controller", None):
        return req.app.state.admission_controller
    return getattr(server_mod, "admission_controller", None) if server_mod else None


def _get_review_service(req: Optional[Request] = None):
    server_mod = _get_server_module()
    if req and hasattr(req, "app") and getattr(req.app.state, "review_service", None):
        return req.app.state.review_service
    return getattr(server_mod, "review_service", None) if server_mod else None


async def _authenticate_websocket(websocket: WebSocket):
    """Verify a WebSocket caller before accept."""
    token = None
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return None
    try:
        auth_mgr = get_auth_manager()
        token_data = auth_mgr.verify_token(token)
        user = auth_mgr.get_user(token_data.username)
    except Exception:
        await websocket.close(code=4401)
        return None
    if not user:
        await websocket.close(code=4401)
        return None
    return user


@router.websocket("/jobs/{job_id}/stream")
@router.websocket("/ws/jobs/{job_id}")
async def job_stream(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress streaming."""
    if await _authenticate_websocket(websocket) is None:
        return
    db = _get_db()
    orchestrator = _get_orchestrator()
    if db is not None:
        try:
            existing = await db.get_job_status(job_id)
        except Exception:
            existing = None
        if not existing and not (orchestrator and job_id in getattr(orchestrator, "active_jobs", {})):
            await websocket.close(code=4404)
            return
    await websocket.accept()

    if job_id not in active_websockets:
        active_websockets[job_id] = []
    active_websockets[job_id].append(websocket)

    try:
        while True:
            if db:
                job = await db.get_job_status(job_id)
                if job:
                    if job_id in (orchestrator.active_jobs if orchestrator else {}):
                        job_obj = orchestrator.active_jobs[job_id]
                        if job_obj.constraint_analysis:
                            job["constraint_analysis"] = {
                                "feasibility_score": job_obj.constraint_analysis.feasibility_score,
                                "warnings": job_obj.constraint_analysis.warnings,
                            }

                    await websocket.send_json(job)

                    if job.get("status") in ["completed", "failed", "cancelled"]:
                        break

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        if job_id in active_websockets:
            try:
                active_websockets[job_id].remove(websocket)
                if not active_websockets[job_id]:
                    del active_websockets[job_id]
            except Exception:
                pass


@router.websocket("/ws/jobs")
async def jobs_list_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time jobs list streaming."""
    if await _authenticate_websocket(websocket) is None:
        return
    await websocket.accept()
    list_key = "__jobs_list__"
    if list_key not in active_websockets:
        active_websockets[list_key] = []
    active_websockets[list_key].append(websocket)

    try:
        while True:
            db = _get_db()
            if db:
                try:
                    jobs = await db.list_jobs(limit=25)
                    await websocket.send_json({"jobs": jobs})
                except Exception:
                    pass
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    finally:
        if list_key in active_websockets:
            try:
                active_websockets[list_key].remove(websocket)
                if not active_websockets[list_key]:
                    del active_websockets[list_key]
            except Exception:
                pass


# ── Job Request / Response Models ──────────────────────────────────────────────

class SourcePreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    optimize_query: bool = True
    override_query: Optional[str] = None
    query_plan: Optional[dict] = None
    language: str = "en"
    region_restrictions: list[str] = Field(default_factory=list)
    max_sources: int = 8

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Describe the dataset you want")
        return value


class ExampleBatchPreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    sources: list[dict] = Field(min_length=1, max_length=5)
    carry_forward_examples: list[dict] = Field(default_factory=list, max_length=3)
    carry_forward_indices: Optional[list[int]] = Field(default=None, max_length=3)
    carry_forward_token: Optional[str] = None
    query_plan: Optional[dict] = None
    dataset_type: str = "sft"
    language: str = "en"
    max_examples: int = Field(default=3, ge=1, le=3)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Describe the dataset you want")
        return value


class AcceptPreviewRequest(BaseModel):
    edited_samples: Optional[list[dict]] = None


class RejectPreviewRequest(BaseModel):
    updated_prompt: Optional[str] = None
    notes: Optional[str] = None


class SignedUrlRequest(BaseModel):
    ttl_seconds: int = Field(3600, ge=60, le=86400, description="Token validity duration in seconds (60 to 86400)")
    format: Optional[str] = Field("jsonl", description="Target export format: jsonl, csv, xml, parquet, json")


class SignedUrlResponse(BaseModel):
    job_id: str
    token: str
    expires_at: int
    expires_in_seconds: int
    format: str
    download_url: str


# ── Idempotency Cache ─────────────────────────────────────────────────────────

from collections import OrderedDict
_idempotency_cache: OrderedDict[str, dict] = OrderedDict()
_IDEMPOTENCY_CACHE_MAX_SIZE = 1000
_IDEMPOTENCY_TTL_SECONDS = 300.0


def _get_idempotent_entry(key: str) -> Optional[dict]:
    now_ts = time.time()
    entry = _idempotency_cache.get(key)
    if not entry:
        return None
    ttl = entry.get("ttl", _IDEMPOTENCY_TTL_SECONDS)
    if now_ts - entry.get("timestamp", 0) > ttl:
        _idempotency_cache.pop(key, None)
        return None
    _idempotency_cache.move_to_end(key)
    return entry


def _set_idempotent_entry(key: str, response_data: dict, ttl: float = _IDEMPOTENCY_TTL_SECONDS) -> None:
    now_ts = time.time()
    _idempotency_cache[key] = {
        "timestamp": now_ts,
        "ttl": ttl,
        "response": response_data,
    }
    _idempotency_cache.move_to_end(key)
    while len(_idempotency_cache) > _IDEMPOTENCY_CACHE_MAX_SIZE:
        _idempotency_cache.popitem(last=False)


# ── Preview and Plan Endpoints ────────────────────────────────────────────────

@router.post("/jobs/preview", tags=["Jobs"])
async def preview_job_sources(
    request: SourcePreviewRequest,
    fastapi_req: Request,
    current_user: User = Depends(get_current_user),
):
    """Build an improved search plan and fetch a small source-only preview."""
    orchestrator = _get_orchestrator(fastapi_req)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Discovery pipeline is not available")

    from core.intent import UserIntent
    from core.intent_extractor import extract_intent
    from pipeline.discovery import DiscoveryPipeline

    intent = None
    if request.query_plan:
        try:
            intent = UserIntent(
                primary_task=request.query_plan.get("primary_task", "custom dataset generation"),
                domain=request.query_plan.get("domain") or request.query.strip(),
                modality=request.query_plan.get("modality", "text"),
                anti_domains=request.query_plan.get("anti_domains", []),
                key_entities=request.query_plan.get("key_entities", []),
                specialized_queries=request.query_plan.get("specialized_queries", []),
                constraints=request.query_plan.get("constraints", []),
                output_format=request.query_plan.get("output_format", "jsonl"),
                confidence=float(request.query_plan.get("confidence", 0.5)),
                raw_input=request.query,
            )
        except (TypeError, ValueError) as exc:
            logger.warning("Ignoring invalid saved query plan: %s", exc)

    cache = _get_cache(fastapi_req)
    if intent is None and request.optimize_query and orchestrator.router:
        try:
            intent = await extract_intent(
                request.query,
                orchestrator.router,
                redis_client=cache.redis if cache is not None else None,
            )
        except Exception as exc:
            logger.warning("Query planning failed; previewing the original request: %s", exc)

    specialized = list(getattr(intent, "specialized_queries", []) or [])
    improved_query = (request.override_query or "").strip() or (specialized[0] if specialized else request.query.strip())
    if request.override_query and request.override_query.strip():
        planned_queries = [improved_query] + [query for query in specialized if query != improved_query][:9]
    else:
        planned_queries = specialized[:10] or [improved_query]
    preview_queries = planned_queries[:2]
    query_plan = ({
        "primary_task": intent.primary_task,
        "domain": intent.domain,
        "modality": intent.modality,
        "anti_domains": intent.anti_domains,
        "key_entities": intent.key_entities,
        "specialized_queries": planned_queries,
        "constraints": intent.constraints,
        "output_format": intent.output_format,
        "confidence": intent.confidence,
    } if intent else {
        "primary_task": "custom dataset generation",
        "domain": request.query.strip(),
        "modality": "text",
        "anti_domains": [],
        "key_entities": [],
        "specialized_queries": planned_queries,
        "constraints": [],
        "output_format": "jsonl",
        "confidence": 0.5,
    })
    config = {
        "target_domain": getattr(intent, "domain", "") or improved_query,
        "language": request.language,
        "region_restrictions": request.region_restrictions,
        "aikosh_api_key": get_settings().aikosh_api_key,
        "max_results": max(1, min(request.max_sources, 20)),
        "health_check_enabled": False,
        "quality_min_score": 0.0,
    }
    source_config = {**config, "target_domain": request.query}
    source_types = orchestrator._determine_source_types(source_config)[:8]
    from pipeline.discovery import SourceType
    for st in (SourceType.WIKIPEDIA, SourceType.BOOKS, SourceType.BLOG):
        if st not in source_types:
            source_types.append(st)
    discovery = DiscoveryPipeline(config, router=orchestrator.router)
    sources = []
    seen = set()
    for query in preview_queries:
        async for source in discovery.discover(
            query, config["target_domain"], source_types,
            preview=True, query_is_optimized=True,
        ):
            if source.url in seen:
                continue
            if orchestrator and hasattr(orchestrator, "_is_source_relevant") and not orchestrator._is_source_relevant(source, intent):
                continue
            seen.add(source.url)
            metadata = source.metadata or {}
            reported_license = source.license or metadata.get("license") or metadata.get("license_title")
            reported_language = getattr(source, "language", None) or metadata.get("language") or metadata.get("languages")
            if isinstance(reported_license, dict):
                reported_license = reported_license.get("name") or reported_license.get("id") or reported_license.get("spdx_id")
            if isinstance(reported_language, dict):
                reported_language = reported_language.get("name") or reported_language.get("code")
            if isinstance(reported_language, list):
                reported_language = [str(value) for value in reported_language if value]
            elif reported_language is not None:
                reported_language = str(reported_language)
            sources.append({
                "url": source.url,
                "title": source.title,
                "description": source.description,
                "source_type": source.source_type.value,
                "quality_score": source.quality_score,
                "license": str(reported_license) if reported_license else None,
                "license_status": metadata.get("license_status") or ("verify_access_and_terms" if metadata.get("catalogue_only") else ("reported" if reported_license else "not_provided")),
                "language": reported_language,
                "metadata": metadata,
            })
            if len(sources) >= max(1, min(request.max_sources, 20)):
                break
        if len(sources) >= max(1, min(request.max_sources, 20)):
            break
    return {
        "original_query": request.query,
        "improved_query": improved_query,
        "specialized_queries": planned_queries,
        "preview_queries": preview_queries,
        "query_plan": query_plan,
        "sources": sources,
        "source_count": len(sources),
        "preview_only": True,
        "notice": "AIKosh files are discovered from the permitted API scope. Review each dataset's access and reuse terms before using its content.",
    }


@router.post("/jobs/preview/batch", tags=["Jobs"])
async def preview_job_example_batch(
    request: ExampleBatchPreviewRequest,
    fastapi_req: Request,
    current_user: User = Depends(get_current_user),
):
    """Extract, filter, and generate a tiny grounded example batch for approval."""
    orchestrator = _get_orchestrator(fastapi_req)
    if not orchestrator or not orchestrator.router:
        raise HTTPException(status_code=503, detail="A configured AI provider is required to generate example records")

    if request.carry_forward_examples:
        expected_token = _sign_approved_examples(request.query, request.carry_forward_examples)
        if not request.carry_forward_token or not hmac.compare_digest(request.carry_forward_token, expected_token):
            raise HTTPException(status_code=400, detail="Previously reviewed examples are invalid. Generate a fresh preview batch.")
        indices = request.carry_forward_indices
        if indices is None:
            indices = list(range(len(request.carry_forward_examples)))
        if not indices or len(set(indices)) != len(indices) or any(index < 0 or index >= len(request.carry_forward_examples) for index in indices):
            raise HTTPException(status_code=400, detail="Select valid examples to keep before requesting replacements.")
    elif request.carry_forward_indices is not None or request.carry_forward_token:
        raise HTTPException(status_code=400, detail="Carry-forward approval data is incomplete.")
    else:
        indices = []

    from core.intent import UserIntent
    from pipeline.construction import ConstructionPipeline, DatasetType
    from pipeline.extraction import ExtractionPipeline, _is_safe_url
    from pipeline.filtering import FilteringPipeline
    from pipeline.discovery import SourceType

    plan = request.query_plan or {}
    intent = UserIntent(
        primary_task=plan.get("primary_task", "custom dataset generation"),
        domain=plan.get("domain") or request.query.strip(),
        modality=plan.get("modality", "text"),
        anti_domains=plan.get("anti_domains", []),
        key_entities=plan.get("key_entities", []),
        specialized_queries=plan.get("specialized_queries", [request.query.strip()]),
        constraints=plan.get("constraints", []),
        output_format=plan.get("output_format", "jsonl"),
        confidence=float(plan.get("confidence", 0.5)),
        raw_input=request.query,
    )
    config = {
        "target_domain": intent.domain,
        "dataset_type": request.dataset_type,
        "language": request.language,
        "quality_level": "high",
        "quality_threshold": 0.55,
        "timeout": 20,
        "min_length": 80,
        "max_length": 20000,
        "synthetic_ratio": 0.0,
        "aikosh_api_key": orchestrator.config.get("aikosh_api_key") or get_settings().aikosh_api_key,
    }
    try:
        dataset_type = DatasetType(request.dataset_type)
    except ValueError:
        dataset_type = DatasetType.SFT

    extractor = ExtractionPipeline(config, router=orchestrator.router)
    filtering = FilteringPipeline(orchestrator.router, config)
    construction = ConstructionPipeline(orchestrator.router, config)
    examples = [request.carry_forward_examples[index] for index in indices]
    existing_example_keys = {
        (" ".join(str(example.get("instruction", "")).casefold().split()),
         " ".join(str(example.get("response", "")).casefold().split()))
        for example in request.carry_forward_examples
    }
    warnings = []
    sources_processed = 0

    for source_data in request.sources:
        metadata = source_data.get("metadata") or {}
        if metadata.get("catalogue_only"):
            warnings.append("Skipped an AIKosh catalogue page; choose a dataset download you can access and whose license you have verified.")
            continue
        url = str(source_data.get("url", ""))
        is_safe, reason = _is_safe_url(url)
        if not is_safe:
            warnings.append(f"Skipped unsafe source URL: {reason}")
            continue
        try:
            source_type = SourceType(source_data.get("source_type", SourceType.WEB_PAGE.value))
        except ValueError:
            source_type = SourceType.WEB_PAGE
        source = SimpleNamespace(
            url=url,
            source_type=source_type,
            title=source_data.get("title", ""),
            description=source_data.get("description", ""),
            license=source_data.get("license"),
            metadata=metadata,
            metadata__=metadata,
        )

        try:
            extracted = None
            async with asyncio.timeout(120):
                async for content in extractor.extract(source):
                    if content.content and content.content_type != "error":
                        extracted = content
                        break
            if extracted is None:
                warnings.append(f"Could not extract usable text from {source.title or url}")
                continue
            sources_processed += 1

            provenance = {
                "source_url": url,
                "source_type": source_type.value,
                "source_title": source.title,
                "license": source.license,
                "language": extracted.language or request.language,
            }
            extracted.metadata = {**(extracted.metadata or {}), **{k: v for k, v in provenance.items() if v}}
            filtered = await asyncio.wait_for(filtering.filter(extracted, intent), timeout=60)
            if not filtered:
                warnings.append(f"Source text did not pass quality checks: {source.title or url}")
                continue

            filtered.metadata = {**(filtered.metadata or {}), **{k: v for k, v in provenance.items() if v}}
            previous_count = len(examples)
            async with asyncio.timeout(120):
                async for constructed in construction.construct(filtered, intent, dataset_type=dataset_type):
                    example_key = (
                        " ".join(str(constructed.instruction or "").casefold().split()),
                        " ".join(str(constructed.response or "").casefold().split()),
                    )
                    if example_key in existing_example_keys:
                        continue
                    existing_example_keys.add(example_key)
                    examples.append({
                        "instruction": constructed.instruction,
                        "response": constructed.response,
                        "input": constructed.input,
                        "source_text": filtered.content[:2000],
                        "quality_score": filtered.quality_score,
                        "difficulty_tier": constructed.difficulty_tier,
                        "source_url": url,
                        "source_title": source.title,
                        "source_type": source_type.value,
                        "metadata": {**(constructed.metadata or {}), **provenance},
                    })
                    if len(examples) >= request.max_examples:
                        break
            if len(examples) == previous_count:
                warnings.append(f"No valid examples were returned for {source.title or url}")
        except Exception as exc:
            logger.warning("Example batch preview failed for %s: %s", url, exc)
            warnings.append(f"Could not build examples from {source.title or url}: {exc}")
        if len(examples) >= request.max_examples:
            break

    final_examples = examples[:request.max_examples]
    return {
        "examples": final_examples,
        "example_count": len(final_examples),
        "approved_examples_token": _sign_approved_examples(request.query, final_examples),
        "sources_processed": sources_processed,
        "warnings": warnings,
        "preview_only": True,
    }


@router.post("/jobs/estimate", tags=["Jobs"])
async def estimate_job(
    request: JobRequest,
    fastapi_req: Request,
    current_user: User = Depends(get_current_user),
):
    """Estimate feasibility and flag a planning-budget mismatch before a job starts."""
    from core.orchestrator_core import ConstraintAnalyzer

    settings = get_settings()
    analysis = await ConstraintAnalyzer(settings.model_dump()).analyze(request.model_dump())
    return {
        "estimated_sources": analysis.estimated_sources,
        "estimated_samples": analysis.estimated_samples,
        "estimated_cost_usd": analysis.estimated_cost,
        "planning_budget_usd": request.cost_budget_usd,
        "within_budget": analysis.estimated_cost <= request.cost_budget_usd,
        "warnings": analysis.warnings,
        "suggested_adjustments": analysis.fallback_strategies,
    }


@router.post("/jobs/plan", tags=["Jobs"])
async def plan_job(
    request: JobRequest,
    fastapi_req: Request = None,
    current_user: User = Depends(get_current_user),
):
    """Generate an execution plan with resource allocation, step costs, and workflow optimization."""
    try:
        from api.planning.planner import WorkflowPlanner
        from api.schemas.dataset import DatasetConfig
        from pipeline.planner import DatasetPlanner, CoveragePlanner

        domain_val = getattr(request, "target_domain", None) or getattr(request, "domain", "general")
        size_val = int(getattr(request, "dataset_size", None) or getattr(request, "target_size", 20))
        output_fmt = getattr(request, "output_format", getattr(request, "export_format", "jsonl"))
        config = DatasetConfig(
            name=request.dataset_name or domain_val or "dataset",
            domain=domain_val,
            synthesis_mode=getattr(request, "synthesis_mode", "standard"),
            language=request.language,
            output_format=output_fmt,
        )
        planner = WorkflowPlanner()
        plan = await planner.create_plan(config)

        cov_matrix_dict = {}
        try:
            orchestrator = _get_orchestrator(fastapi_req)
            dp = DatasetPlanner(orchestrator.router if orchestrator else None, config.model_dump())
            dplan = await dp.create_plan(domain_val or "general")
            cov_planner = CoveragePlanner(config.model_dump())
            cov_matrix = cov_planner.generate_matrix(dplan, target_size=min(size_val, 50))
            cov_matrix_dict = {
                "dimensions": cov_matrix.dimensions,
                "cells": cov_matrix.cells[:30],
                "total_cells": len(cov_matrix.cells),
            }
        except Exception as cov_err:
            logger.debug("CoveragePlanner skipped in /jobs/plan: %s", cov_err)

        return {
            "plan_id": plan.plan_id,
            "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
            "estimated_cost": plan.total_estimated_cost_usd,
            "estimated_duration_seconds": plan.total_estimated_duration_seconds,
            "is_estimate": True,
            "template_estimate": True,
            "efficiency_score": plan.efficiency_score,
            "confidence_score": 0.85,
            "confidence_score_is_estimate": True,
            "orchestration_mode": plan.orchestration_mode,
            "execution_strategy": plan.execution_strategy,
            "steps": [step.model_dump() for step in plan.steps],
            "total_gpu_hours": plan.total_gpu_hours,
            "coverage_matrix": cov_matrix_dict,
        }
    except Exception as exc:
        logger.error(f"Planning failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate workflow plan")


# ── Pipeline Runner ───────────────────────────────────────────────────────────

async def run_pipeline(job_id: str, request: JobRequest | dict, resume_state: Optional[dict] = None):
    """Run the dataset generation pipeline."""
    orchestrator = _get_orchestrator()
    db = _get_db()
    admission_controller = _get_admission()
    observability = _get_observability()

    if not orchestrator:
        logger.error(f"Cannot run pipeline {job_id}: orchestrator not initialized")
        if db:
            await db.update_job(job_id, status="failed", error="Orchestrator not initialized")
        return

    if not db:
        logger.error(f"Cannot run pipeline {job_id}: database not available")
        raise RuntimeError(f"Database connection required for job execution. Job {job_id} cannot proceed.")

    admission = admission_controller
    admission_acquired = False
    try:
        if admission:
            admission_acquired = await admission.acquire(job_id)
            if not admission_acquired:
                logger.error(f"Cannot run pipeline {job_id}: admission rejected (queue full)")
                if db:
                    await db.update_job(job_id, status="failed", error="Admission rejected: server at capacity")
                return
    except Exception as e:
        logger.warning(f"Admission control check failed for {job_id}: {e}")

    if observability is not None:
        observability.log_job_event(job_id, "pipeline_started")

    job = Job(
        id=job_id,
        status=JobStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        current_stage="analyzing_constraints",
        progress=0.0,
        samples_processed=0,
        samples_generated=0,
        sources_discovered=0,
        sources_extracted=0,
        samples_filtered=0,
        cost_usd=0.0,
        error=None,
        config=request.model_dump() if hasattr(request, "model_dump") else dict(request),
    )

    try:
        await orchestrator.run(job, resume_state=resume_state)

        if getattr(job, "samples_generated", 0) == 0:
            rejection_details = (
                f"Zero samples were constructed. "
                f"Discovered: {getattr(job, 'sources_discovered', 0)}, "
                f"Extracted: {getattr(job, 'sources_extracted', 0)}, "
                f"Filtered: {getattr(job, 'samples_filtered', 0)}."
            )
            raise ValueError(f"Pipeline completed but generated 0 samples. Details: {rejection_details}")

        if observability is not None:
            observability.log_job_event(job_id, "pipeline_completed")
        try:
            await db.update_job(
                job_id,
                status="completed",
                progress=1.0,
                current_stage="export",
                samples_generated=job.samples_generated,
                samples_processed=job.samples_processed,
                sources_discovered=getattr(job, "sources_discovered", 0),
                sources_extracted=getattr(job, "sources_extracted", 0),
                samples_filtered=getattr(job, "samples_filtered", 0),
            )
        except Exception as db_error:
            logger.error(f"Failed to update completed job status in DB: {db_error}")
    except Exception as e:
        logger.error(f"Pipeline {job_id} failed: {e}")
        if observability is not None:
            observability.log_job_event(job_id, "pipeline_failed", {"error": str(e)})
        try:
            await db.update_job(job_id, status="failed", error=str(e), current_stage=job.current_stage)
        except Exception as db_error:
            logger.error(f"Failed to update job status in DB: {db_error}")
    finally:
        if admission and admission_acquired:
            try:
                admission.release(job_id)
            except Exception as release_err:
                logger.warning(f"Failed to release admission slot for {job_id}: {release_err}")

    if job_id in active_websockets:
        for ws in active_websockets[job_id]:
            try:
                await ws.send_json({"status": job.status.value, "job_id": job_id})
            except Exception:
                pass


# ── Job CRUD Endpoints ────────────────────────────────────────────────────────

@router.post("/jobs", response_model=JobResponse, status_code=201, tags=["Jobs"])
async def create_job(
    request: JobRequest,
    background_tasks: BackgroundTasks,
    fastapi_req: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
):
    """Create a new dataset generation job and kick off the pipeline."""
    orchestrator = _get_orchestrator(fastapi_req)
    db = _get_db(fastapi_req)

    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    user_prefix = current_user.username or "anonymous"
    raw_cfg_key = f"{request.target_domain}:{request.dataset_size}:{getattr(request, 'language', 'en')}:{getattr(request, 'raw_input', '')[:100]}"
    fingerprint = hashlib.sha256(raw_cfg_key.encode("utf-8")).hexdigest()
    dedup_key = f"{user_prefix}:{idempotency_key}" if idempotency_key else f"{user_prefix}:{fingerprint}"
    is_explicit_key = bool(idempotency_key)

    cached = _get_idempotent_entry(dedup_key)
    if cached:
        logger.info("Idempotent create_job hit for key %s -> returning existing job %s", dedup_key, cached["response"]["id"])
        return JobResponse(**cached["response"])

    if request.approved_examples:
        expected_token = _sign_approved_examples(request.target_domain, request.approved_examples)
        if not request.approved_examples_token or not hmac.compare_digest(request.approved_examples_token, expected_token):
            raise HTTPException(status_code=400, detail="Example batch is invalid or no longer matches this query. Preview the examples again.")
        if request.approved_example_indices is not None:
            indices = request.approved_example_indices
            if not indices or len(set(indices)) != len(indices) or any(index < 0 or index >= len(request.approved_examples) for index in indices):
                raise HTTPException(status_code=400, detail="Select at least one valid example from the reviewed preview batch.")

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    config = request.model_dump()
    if request.approved_examples and request.approved_example_indices is not None:
        config["approved_examples"] = [request.approved_examples[index] for index in request.approved_example_indices]
    config["id"] = job_id
    config["owner"] = current_user.username

    try:
        await db.create_job(config)
    except Exception as e:
        logger.error(f"Failed to persist new job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create job")

    queued = False
    if get_settings().enable_celery:
        try:
            from workers.celery_app import run_pipeline_task
            run_pipeline_task.apply_async(args=[job_id, config], retry=False)
            queued = True
            logger.info("Queued dataset job %s with Celery", job_id)
        except Exception as dispatch_error:
            logger.warning("Celery dispatch failed for job %s; using in-process fallback: %s", job_id, dispatch_error)

    if not queued:
        server_mod = _get_server_module()
        run_fn = getattr(server_mod, "run_pipeline", None) or run_pipeline
        background_tasks.add_task(run_fn, job_id, request)

    resp = JobResponse(
        id=job_id,
        status=JobStatusEnum.PENDING,
        created_at=now,
        progress=0.0,
        cost_usd=0.0,
        samples_generated=0,
        current_stage="initializing",
    )
    _set_idempotent_entry(
        dedup_key,
        resp.model_dump(),
        ttl=300.0 if is_explicit_key else 30.0,
    )
    return resp


@router.get("/jobs", tags=["Jobs"])
async def list_jobs(
    fastapi_req: Request,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """List dataset generation jobs (most recent first)."""
    db = _get_db(fastapi_req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    try:
        jobs = await db.list_jobs(status=status, limit=limit + 1, cursor=cursor, owner=owner_filter)
    except Exception as e:
        if "no such table" in str(e).lower() or "relation" in str(e).lower():
            logger.info("Database table missing — auto-creating tables...")
            try:
                await db.create_tables()
                jobs = await db.list_jobs(status=status, limit=limit + 1, owner=owner_filter)
            except Exception as retry_err:
                logger.error(f"Failed to list jobs after table creation: {retry_err}")
                raise HTTPException(status_code=500, detail="Failed to list jobs after table creation")
        else:
            logger.error(f"Failed to list jobs: {e}")
            raise HTTPException(status_code=500, detail="Database query error while listing jobs")

    has_more = len(jobs) > limit
    page = jobs[:limit]
    next_cursor = page[-1]["id"] if has_more and page else None

    return {
        "data": page,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


@router.get("/jobs/{job_id}", response_model=JobDetailResponse, tags=["Jobs"])
async def get_job(
    job_id: str,
    fastapi_req: Request,
    current_user: User = Depends(get_current_user),
):
    """Get a single job's full detail."""
    db = _get_db(fastapi_req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    job_cfg = job.get("config") or {}
    job_meta = job.get("metadata") or {}
    quality_score = job.get("quality_score")
    if quality_score is None:
        quality_score = job_meta.get("quality_score") or (job_meta.get("quality_breakdown") or {}).get("composite")
    is_simulated = bool(job_cfg.get("is_simulated") or job.get("is_simulated") or job.get("execution_mode") == "simulated")

    raw_created = job.get("created_at")
    parsed_created = None
    if isinstance(raw_created, str):
        try:
            parsed_created = datetime.fromisoformat(raw_created)
        except (ValueError, TypeError):
            parsed_created = None
    elif isinstance(raw_created, datetime):
        parsed_created = raw_created

    return JobDetailResponse(
        id=job["id"],
        status=job["status"],
        created_at=parsed_created,
        progress=job.get("progress", 0.0),
        cost_usd=job.get("cost_usd", 0.0),
        samples_generated=job.get("samples_generated", 0),
        current_stage=job.get("current_stage"),
        config=job_cfg,
        error=job.get("error"),
        sources_discovered=job.get("sources_discovered", 0),
        sources_extracted=job.get("sources_extracted", 0),
        samples_filtered=job.get("samples_filtered", 0),
        quality_score=quality_score,
        metadata=job_meta,
        is_simulated=is_simulated,
        execution_mode="simulated" if is_simulated else "live",
    )


@router.post("/jobs/{job_id}/cancel", tags=["Jobs"])
async def cancel_job(
    job_id: str,
    fastapi_req: Request,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
):
    """Cancel an active or pending dataset generation job."""
    db = _get_db(fastapi_req)
    orchestrator = _get_orchestrator(fastapi_req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    status = (job.get("status") or "").lower()
    if status in {"cancelled", "completed", "failed"}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel job in '{status}' state")

    if orchestrator and hasattr(orchestrator, "active_jobs") and job_id in orchestrator.active_jobs:
        active_task = orchestrator.active_jobs.get(job_id)
        if hasattr(active_task, "cancel") and callable(active_task.cancel):
            try:
                active_task.cancel()
            except Exception:
                pass

    await db.update_job_status(job_id, {"status": "cancelled", "error": "Cancelled by user request"})

    if job_id in active_websockets:
        updated_job = await db.get_job_status(job_id)
        for ws in list(active_websockets[job_id]):
            try:
                await ws.send_json(updated_job)
            except Exception:
                pass

    return {"status": "cancelled", "job_id": job_id, "message": "Job cancelled successfully"}


@router.delete("/jobs/{job_id}", tags=["Jobs"])
async def delete_job_endpoint(
    job_id: str,
    fastapi_req: Request,
    admin_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Delete a job, all associated datasets/samples, and output files."""
    db = _get_db(fastapi_req)
    orchestrator = _get_orchestrator(fastapi_req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if orchestrator and hasattr(orchestrator, "active_jobs") and job_id in orchestrator.active_jobs:
        active_task = orchestrator.active_jobs.get(job_id)
        if hasattr(active_task, "cancel") and callable(active_task.cancel):
            try:
                active_task.cancel()
            except Exception:
                pass

    try:
        output_dir = Path("outputs")
        if output_dir.exists():
            for f in output_dir.glob(f"*{job_id}*"):
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        pass

    success = await db.delete_job(job_id)
    return {"success": success, "message": f"Job {job_id} and associated data deleted"}


@router.get("/jobs/{job_id}/preview_samples", tags=["Jobs"])
async def get_job_preview_samples(
    job_id: str,
    fastapi_req: Request,
    current_user: User = Depends(get_current_user),
):
    """Retrieve early dataset preview samples generated for a job."""
    db = _get_db(fastapi_req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")
    config = job.get("config") or {}
    preview_samples = config.get("preview_samples", [])
    return {
        "job_id": job_id,
        "status": job["status"],
        "samples": preview_samples,
        "sample_count": len(preview_samples),
    }


@router.post("/jobs/{job_id}/accept_preview", tags=["Jobs"])
async def accept_job_preview(
    job_id: str,
    fastapi_req: Request,
    payload: AcceptPreviewRequest = Body(default_factory=AcceptPreviewRequest),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
):
    """Accept early preview samples, optionally with user edits, and advance pipeline."""
    db = _get_db(fastapi_req)
    orchestrator = _get_orchestrator(fastapi_req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    status = (job.get("status") or "").lower()
    stage = (job.get("current_stage") or "").lower()
    if status not in {"awaiting_preview_approval", "pending", "running"} and "preview" not in stage:
        raise HTTPException(status_code=409, detail=f"Job {job_id} is in state '{status}' (stage '{stage}') and not awaiting preview approval")

    if orchestrator and hasattr(orchestrator, "accept_preview"):
        success = orchestrator.accept_preview(job_id, edited_samples=payload.edited_samples)
        if success:
            return {"success": True, "message": f"Preview accepted for job {job_id}. Advancing pipeline."}
    if db:
        await db.update_job_status(job_id, {"status": "running", "current_stage": "discover"})
        return {"success": True, "message": f"Job {job_id} resumed."}
    raise HTTPException(status_code=404, detail="Job not found or not awaiting preview")


@router.post("/jobs/{job_id}/reject_preview", tags=["Jobs"])
async def reject_job_preview(
    job_id: str,
    fastapi_req: Request,
    payload: RejectPreviewRequest = Body(default_factory=RejectPreviewRequest),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
):
    """Reject early preview samples, optionally supply updated prompt, and re-generate preview."""
    db = _get_db(fastapi_req)
    orchestrator = _get_orchestrator(fastapi_req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    status = (job.get("status") or "").lower()
    stage = (job.get("current_stage") or "").lower()
    if status not in {"awaiting_preview_approval", "pending", "running"} and "preview" not in stage:
        raise HTTPException(status_code=409, detail=f"Job {job_id} is in state '{status}' (stage '{stage}') and not awaiting preview approval")

    if orchestrator and hasattr(orchestrator, "reject_preview"):
        success = orchestrator.reject_preview(job_id, updated_prompt=payload.updated_prompt)
        if success:
            return {"success": True, "message": "Preview rejected. Re-optimizing query and generating fresh samples."}
    if db:
        status_update: dict[str, Any] = {"status": "running", "current_stage": "query_optimizer"}
        if payload.updated_prompt:
            cfg = job.get("config") or {}
            cfg["target_domain"] = payload.updated_prompt
            status_update["config"] = cfg
        await db.update_job_status(job_id, status_update)
        return {"success": True, "message": "Job updated for regeneration."}
    raise HTTPException(status_code=404, detail="Job not found or not awaiting preview")


@router.get("/jobs/{job_id}/records", tags=["Jobs"])
async def get_job_records(
    job_id: str,
    fastapi_req: Request,
    limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Get sample records from datasets belonging to a job."""
    db = _get_db(fastapi_req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    server_mod = _get_server_module()
    resolve_disk_fn = getattr(server_mod, "_resolve_dynamic_disk_dataset", None) or resolve_dynamic_disk_dataset
    disk_info = resolve_disk_fn(job_id)
    if disk_info and Path(disk_info["output_path"]).exists() and disk_info["output_path"].endswith(".jsonl"):
        disk_records = []
        with open(disk_info["output_path"], "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if line.strip():
                    item = json.loads(line)
                    disk_records.append({
                        "id": f"{job_id}-{idx}",
                        "dataset_id": job_id,
                        "instruction": item.get("instruction", ""),
                        "response": item.get("response", ""),
                        "input": item.get("input", ""),
                        "quality_score": item.get("quality_score"),
                        "difficulty_tier": item.get("difficulty_tier"),
                        "created_at": item.get("created_at"),
                    })
                if len(disk_records) >= limit:
                    break
        return {
            "records": disk_records,
            "count": len(disk_records),
            "message": None,
        }

    try:
        datasets = await db.get_datasets_by_job(job_id)
        records: list[dict] = []
        for ds in datasets:
            samples = await db.get_samples(ds["id"], limit=limit)
            for sample in samples:
                records.append({
                    "id": sample["id"],
                    "dataset_id": sample["dataset_id"],
                    "instruction": sample.get("instruction", ""),
                    "response": sample.get("response", ""),
                    "input": sample.get("input", ""),
                    "quality_score": sample.get("quality_score"),
                    "difficulty_tier": sample.get("difficulty_tier"),
                    "created_at": sample.get("created_at"),
                })
                if len(records) >= limit:
                    break
            if len(records) >= limit:
                break

        if not records and job and job.get("config"):
            cfg = job["config"]
            preview_samples = cfg.get("preview_samples") or []
            for idx, ps in enumerate(preview_samples[:limit]):
                records.append({
                    "id": f"preview-{idx}",
                    "dataset_id": job_id,
                    "instruction": ps.get("instruction", ""),
                    "response": ps.get("response", ""),
                    "input": ps.get("input", ""),
                    "quality_score": ps.get("metadata", {}).get("quality_score"),
                    "difficulty_tier": ps.get("metadata", {}).get("difficulty_tier"),
                    "created_at": job.get("created_at"),
                })

        return {
            "records": records[:limit],
            "count": len(records[:limit]),
            "message": None,
        }
    except Exception as e:
        logger.error(f"Failed to get records for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get records")


@router.get("/jobs/{job_id}/summary", tags=["Jobs"])
async def get_job_dataset_summary(
    job_id: str,
    fastapi_req: Request,
    current_user: User = Depends(get_current_user),
):
    """Return persisted quality, provenance, balance, and review coverage for a job."""
    db = _get_db(fastapi_req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    job = await db.get_job_status(job_id)
    _enforce_owner(job, current_user, resource_name="Job")

    datasets = await db.get_datasets_by_job(job_id)
    config = job.get("config") or {}
    review_enabled = bool(config.get("human_review"))
    review = {
        "enabled": review_enabled,
        "requested_percentage": float(config.get("human_review_percentage", 10.0)) if review_enabled else 0.0,
        "total": 0,
        "approved": 0,
        "rejected": 0,
        "pending": 0,
        "flagged": 0,
    }
    review_service = _get_review_service(fastapi_req)
    if review["enabled"] and review_service:
        queue = await review_service.get_queue(job_id=job_id, page=1, page_size=1)
        review["total"] = queue.get("total", 0)
        for st in ("approved", "rejected", "pending", "flagged"):
            status_queue = await review_service.get_queue(status=st, job_id=job_id, page=1, page_size=1)
            review[st] += status_queue.get("total", 0)

    if not datasets:
        return {
            "job_id": job_id,
            "status": job.get("status"),
            "sample_count": job.get("samples_generated", 0),
            "sample_cap": 10000,
            "balance_report": None,
            "provenance": None,
            "quality": {"mean": job.get("quality_score"), "scored_samples": 0},
            "sources": {},
            "languages": {},
            "topics": {},
            "human_review": review,
            "sampled_records": 0,
        }

    from collections import Counter
    dataset = datasets[0]
    dataset_meta = dataset.get("metadata") or {}
    stored = await db.get_samples(dataset["id"], limit=10000)
    sources, languages, topics = Counter(), Counter(), Counter()
    scores = []
    for sample in stored:
        metadata = sample.get("metadata") or {}
        for counter, key in ((sources, "source_type"), (languages, "language"), (topics, "topic")):
            value = metadata.get(key)
            if value:
                counter[str(value)] += 1
        score = sample.get("quality_score")
        if isinstance(score, (int, float)):
            scores.append(float(score))

    job_quality = job.get("quality_score") if isinstance(job, dict) else getattr(job, "quality_score", None)
    if job_quality is None and isinstance(job, dict):
        job_quality = (job.get("metadata") or {}).get("quality_score") or ((job.get("metadata") or {}).get("quality_breakdown") or {}).get("composite")
    if job_quality is None:
        job_quality = dataset_meta.get("quality_score") or (dataset_meta.get("quality_breakdown") or {}).get("composite")
    canonical_mean = job_quality if job_quality is not None else (round(sum(scores) / len(scores), 4) if scores else None)

    return {
        "job_id": job_id,
        "dataset_id": dataset["id"],
        "status": job.get("status"),
        "sample_count": dataset.get("size", len(stored)),
        "sample_cap": 10000,
        "balance_report": dataset_meta.get("balance_report"),
        "provenance": dataset_meta.get("provenance"),
        "quality": {"mean": canonical_mean, "scored_samples": len(scores)},
        "sources": dict(sources),
        "languages": dict(languages),
        "topics": dict(topics),
        "human_review": review,
        "sampled_records": len(stored),
    }


@router.get("/jobs/{job_id}/report", tags=["Jobs"])
async def get_job_report(
    job_id: str,
    fastapi_req: Request,
    current_user: User = Depends(get_current_user),
):
    """Return comprehensive analytical and execution report for a job."""
    summary = await get_job_dataset_summary(job_id, fastapi_req, current_user)
    db = _get_db(fastapi_req)
    job = await db.get_job_status(job_id) if db else None
    config = (job.get("config") or {}) if job else {}
    return {
        "job_id": job_id,
        "status": job.get("status") if job else summary.get("status"),
        "created_at": job.get("created_at") if job else None,
        "completed_at": job.get("completed_at") if job else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "summary": summary,
        "error": job.get("error") if job else None,
    }


# ── Signed URLs and Downloads ─────────────────────────────────────────────────

@router.post("/jobs/{job_id}/signed-url", response_model=SignedUrlResponse, tags=["Jobs"])
@router.post("/datasets/{job_id}/signed-url", response_model=SignedUrlResponse, tags=["Datasets"])
@router.get("/jobs/{job_id}/signed-url", response_model=SignedUrlResponse, tags=["Jobs"])
@router.get("/datasets/{job_id}/signed-url", response_model=SignedUrlResponse, tags=["Datasets"])
async def create_presigned_download_url(
    job_id: str,
    request: Request,
    ttl_seconds: int = Query(3600, description="Token validity in seconds (default 3600)"),
    format: Optional[str] = Query(None, description="Dataset format: jsonl, csv, xml, parquet, json"),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
):
    """Generate an ephemeral HMAC-SHA256 presigned token for streaming private datasets."""
    db = _get_db(request)
    if db:
        target_obj = await db.get_job_status(job_id)
        if not target_obj:
            target_obj = await db.get_dataset(job_id)
        if not target_obj:
            datasets_for_job = await db.get_datasets_by_job(job_id)
            if datasets_for_job:
                target_obj = datasets_for_job[0]
        if not target_obj:
            raise HTTPException(status_code=404, detail=f"Job or Dataset '{job_id}' not found")
        _enforce_owner(target_obj, current_user, resource_name="Job/Dataset")

    parsed_req = None
    if request.method == "POST":
        try:
            raw_body = await request.body()
            if raw_body:
                body_data = json.loads(raw_body)
                try:
                    parsed_req = SignedUrlRequest(**body_data)
                except Exception as val_err:
                    raise HTTPException(status_code=400, detail=f"Invalid SignedUrlRequest: {val_err}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Malformed request body: {e}")

    if parsed_req:
        final_ttl = parsed_req.ttl_seconds
        final_format = (parsed_req.format or "jsonl").lower().strip()
    else:
        if ttl_seconds < 60 or ttl_seconds > 86400:
            raise HTTPException(status_code=400, detail="ttl_seconds must be between 60 and 86400 seconds")
        final_ttl = ttl_seconds
        final_format = (format or "jsonl").lower().strip()

    valid_formats = {"jsonl", "csv", "xml", "parquet", "json"}
    if final_format not in valid_formats:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{final_format}'. Allowed: {sorted(valid_formats)}")

    expires_at = int(time.time()) + final_ttl
    user_binding = current_user.username if current_user else ""
    server_mod = _get_server_module()
    sign_fn = getattr(server_mod, "_sign_download_token", None) or _sign_download_token
    try:
        token = sign_fn(job_id, expires_at, user=user_binding, format=final_format)
    except RuntimeError as sec_err:
        raise HTTPException(status_code=503, detail=str(sec_err))
    download_path = f"/jobs/{job_id}/download?token={token}&expires={expires_at}&format={final_format}"

    return SignedUrlResponse(
        job_id=job_id,
        token=token,
        expires_at=expires_at,
        expires_in_seconds=final_ttl,
        format=final_format,
        download_url=download_path,
    )


@router.get("/jobs/{job_id}/download", tags=["Jobs"])
@router.get("/datasets/{job_id}/download", tags=["Datasets"])
async def download_job_dataset(
    job_id: str,
    format: Optional[str] = Query(None, description="Export format: jsonl, csv, xml, parquet, json"),
    token: Optional[str] = Query(None, description="Ephemeral HMAC-SHA256 presigned token"),
    expires: Optional[int] = Query(None, description="Unix timestamp expiration of signed token"),
    request: Request = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Download the completed dataset file for a job or dataset ID."""
    db = _get_db(request)
    server_mod = _get_server_module()
    verify_fn = getattr(server_mod, "_verify_download_token", None) or _verify_download_token
    resolve_disk_fn = getattr(server_mod, "_resolve_dynamic_disk_dataset", None) or resolve_dynamic_disk_dataset

    req_format = (format or "").lower().strip()
    if not req_format and request:
        accept = request.headers.get("accept", "").lower()
        if "text/csv" in accept:
            req_format = "csv"
        elif "application/xml" in accept or "text/xml" in accept:
            req_format = "xml"
        elif "parquet" in accept:
            req_format = "parquet"
        elif "application/json" in accept and "x-ndjson" not in accept:
            req_format = "json"
        elif "x-ndjson" in accept:
            req_format = "jsonl"

    if req_format not in {"jsonl", "csv", "xml", "parquet", "json"}:
        req_format = "jsonl"

    authorized = False
    auth_user = current_user

    if auth_user:
        authorized = True
        if auth_user.role != UserRole.ADMIN and db:
            target_res = await db.get_job_status(job_id)
            if not target_res:
                target_res = await db.get_dataset(job_id)
            if not target_res:
                datasets_for_job = await db.get_datasets_by_job(job_id)
                if datasets_for_job:
                    target_res = datasets_for_job[0]
            if not target_res:
                raise HTTPException(status_code=404, detail="Resource not found")
            owner = target_res.get("owner")
            if owner and owner != auth_user.username:
                raise HTTPException(status_code=404, detail="Resource not found")

    if not authorized:
        if token and expires is not None:
            if verify_fn(job_id, token, expires, format=req_format):
                authorized = True
            else:
                verified_with_target = False
                if db:
                    target_res = await db.get_job_status(job_id)
                    if not target_res:
                        target_res = await db.get_dataset(job_id)
                    if not target_res:
                        datasets_for_job = await db.get_datasets_by_job(job_id)
                        if datasets_for_job:
                            target_res = datasets_for_job[0]
                    if target_res:
                        res_owner = target_res.get("owner") or ""
                        if verify_fn(job_id, token, expires, user=res_owner, format=req_format):
                            authorized = True
                            verified_with_target = True
                if not verified_with_target:
                    raise HTTPException(
                        status_code=403,
                        detail="Invalid or expired download token. Please request a new signed URL via POST /jobs/{job_id}/signed-url.",
                    )
        elif token or expires is not None:
            raise HTTPException(
                status_code=403,
                detail="Both 'token' and 'expires' parameters are required for presigned dataset access.",
            )
        else:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Provide a valid Bearer token or presigned download URL (?token=...&expires=...).",
            )

    if not authorized:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Unauthorized dataset access for '{job_id}'. "
                "Private dataset streaming requires a valid HMAC-SHA256 presigned token "
                "(?token=...&expires=...) or Bearer token header. "
                "Generate an ephemeral signed URL via POST /jobs/{job_id}/signed-url."
            ),
        )

    if db:
        job_status_obj = await db.get_job_status(job_id)
        if job_status_obj:
            status_val = job_status_obj.get("status") if isinstance(job_status_obj, dict) else getattr(job_status_obj, "status", None)
            if status_val and status_val != "completed":
                raise HTTPException(status_code=409, detail=f"Job '{job_id}' is not complete (current status: {status_val})")

    media_types = {
        "jsonl": "application/x-ndjson",
        "csv": "text/csv; charset=utf-8",
        "xml": "application/xml; charset=utf-8",
        "parquet": "application/vnd.apache.parquet",
        "json": "application/json; charset=utf-8",
    }

    disk_match = resolve_disk_fn(job_id)
    if disk_match:
        disk_dir = disk_match.get("dir")
        if disk_dir and Path(disk_dir).is_dir():
            target_format_files = list(Path(disk_dir).glob(f"*.{req_format}"))
            if target_format_files:
                chosen_file = target_format_files[0]
                return FileResponse(
                    path=str(chosen_file),
                    filename=chosen_file.name,
                    media_type=media_types.get(req_format, "application/octet-stream"),
                )
        if disk_match.get("type") == req_format and Path(disk_match.get("output_path", "")).exists():
            return FileResponse(
                path=disk_match["output_path"],
                filename=Path(disk_match["output_path"]).name,
                media_type=media_types.get(req_format, "application/octet-stream"),
            )

    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    dataset = await db.get_dataset(job_id) if hasattr(db, "get_dataset") else None
    if not dataset:
        job = await db.get_job_status(job_id)
        if job:
            datasets = await db.get_datasets_by_job(job_id)
            if datasets:
                dataset = datasets[0]

    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset or Job '{job_id}' not found")

    output_path = dataset.get("output_path")
    if output_path:
        cand_p = Path(output_path).with_suffix(f".{req_format}")
        if cand_p.exists():
            return FileResponse(
                path=str(cand_p),
                filename=cand_p.name,
                media_type=media_types.get(req_format, "application/octet-stream"),
            )

    page_size = 1000
    first_page = await db.get_samples(dataset["id"], limit=page_size, offset=0)
    if not first_page:
        raise HTTPException(status_code=404, detail="No samples found for this dataset")

    download_name = f"{dataset.get('name', 'dataset')}.{req_format}"

    if req_format == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            all_samples = await db.get_samples(dataset["id"], limit=MAX_SAMPLE_LOAD_LIMIT)
            rows = []
            for s in all_samples:
                rows.append({
                    "instruction": str(s.get("instruction", "")),
                    "input": str(s.get("input", "")),
                    "response": str(s.get("response", "")),
                    "quality_score": float(s.get("quality_score", 0.0) or 0.0),
                    "difficulty_tier": int(s.get("difficulty_tier", 1) or 1),
                })
            table = pa.Table.from_pylist(rows)
            buf = io.BytesIO()
            pq.write_table(table, buf)
            buf.seek(0)
            return Response(
                content=buf.getvalue(),
                media_type="application/vnd.apache.parquet",
                headers={"Content-Disposition": f"attachment; filename={download_name}"},
            )
        except Exception as e:
            logger.warning("Parquet dynamic export failed, falling back to JSONL: %s", e)
            req_format = "jsonl"
            download_name = f"{dataset.get('name', 'dataset')}.jsonl"

    if req_format == "xml":
        import xml.sax.saxutils as xml_escape

        async def xml_generator():
            yield '<?xml version="1.0" encoding="UTF-8"?>\n<dataset>\n'
            offset = 0
            page = first_page
            while page:
                for sample in page:
                    inst = xml_escape.escape(str(sample.get("instruction", "")))
                    inp = xml_escape.escape(str(sample.get("input", "")))
                    resp = xml_escape.escape(str(sample.get("response", "")))
                    score = sample.get("quality_score", "")
                    tier = sample.get("difficulty_tier", "")
                    yield f'  <sample>\n    <instruction>{inst}</instruction>\n    <input>{inp}</input>\n    <response>{resp}</response>\n    <quality_score>{score}</quality_score>\n    <difficulty_tier>{tier}</difficulty_tier>\n  </sample>\n'
                offset += len(page)
                if len(page) < page_size:
                    break
                page = await db.get_samples(dataset["id"], limit=page_size, offset=offset)
            yield '</dataset>\n'

        return StreamingResponse(
            xml_generator(),
            media_type="application/xml; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={download_name}"},
        )

    if req_format == "csv":
        async def csv_generator():
            s_io = io.StringIO()
            writer = csv.writer(s_io)
            writer.writerow(["instruction", "input", "response", "quality_score", "difficulty_tier"])
            yield s_io.getvalue()
            s_io.seek(0)
            s_io.truncate(0)

            offset = 0
            page = first_page
            while page:
                for sample in page:
                    writer.writerow([
                        sample.get("instruction", ""),
                        sample.get("input", ""),
                        sample.get("response", ""),
                        sample.get("quality_score", ""),
                        sample.get("difficulty_tier", ""),
                    ])
                    yield s_io.getvalue()
                    s_io.seek(0)
                    s_io.truncate(0)
                offset += len(page)
                if len(page) < page_size:
                    break
                page = await db.get_samples(dataset["id"], limit=page_size, offset=offset)

        return StreamingResponse(
            csv_generator(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={download_name}"},
        )

    if req_format == "json":
        async def json_array_generator():
            yield "[\n"
            first_item = True
            offset = 0
            page = first_page
            while page:
                for sample in page:
                    item = {
                        "instruction": sample.get("instruction", ""),
                        "response": sample.get("response", ""),
                        "input": sample.get("input", ""),
                        "quality_score": sample.get("quality_score"),
                        "difficulty_tier": sample.get("difficulty_tier"),
                    }
                    prefix = "" if first_item else ",\n"
                    first_item = False
                    yield prefix + "  " + json.dumps(item, ensure_ascii=False)
                offset += len(page)
                if len(page) < page_size:
                    break
                page = await db.get_samples(dataset["id"], limit=page_size, offset=offset)
            yield "\n]\n"

        return StreamingResponse(
            json_array_generator(),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={download_name}"},
        )

    async def jsonl_generator():
        offset = 0
        page = first_page
        while page:
            for sample in page:
                item = {
                    "instruction": sample.get("instruction", ""),
                    "response": sample.get("response", ""),
                    "input": sample.get("input", ""),
                    "quality_score": sample.get("quality_score"),
                    "difficulty_tier": sample.get("difficulty_tier"),
                    "metadata": sample.get("metadata", {}),
                }
                yield json.dumps(item, ensure_ascii=False) + "\n"
            offset += len(page)
            if len(page) < page_size:
                break
            page = await db.get_samples(dataset["id"], limit=page_size, offset=offset)

    return StreamingResponse(
        jsonl_generator(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f"attachment; filename={download_name}"},
    )
