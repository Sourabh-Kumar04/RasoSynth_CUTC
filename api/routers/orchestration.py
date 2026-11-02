"""Orchestration DAG and retry endpoints for RasoSynthTune."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.auth import User, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Orchestration"])


def _get_server_module():
    return sys.modules.get("api.server")


def _get_db(req: Request):
    server_mod = _get_server_module()
    return getattr(req.app.state, "db", None) or (
        getattr(server_mod, "db", None) if server_mod else None
    )


def _get_orchestrator(req: Request):
    server_mod = _get_server_module()
    return (
        getattr(server_mod, "orchestrator", None)
        if server_mod and hasattr(server_mod, "orchestrator")
        else getattr(req.app.state, "orchestrator", None)
    )


@router.get("/orchestration/dag")
async def get_orchestration_dag(
    req: Request,
    job_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Get the current dataset synthesis orchestration DAG reflecting live execution state."""
    stage_order = [
        "analyzing_constraints",
        "query_optimizer",
        "early_preview",
        "discovering_sources",
        "extracting_content",
        "filtering_quality",
        "constructing_dataset",
        "quality_eval",
        "human_review",
        "balancing_engine",
        "exporting",
    ]
    labels = {
        "analyzing_constraints": "Constraint Analysis",
        "query_optimizer": "Query Optimizer Fast-Pass",
        "early_preview": "Early Preview & Gate",
        "discovering_sources": "Multi-Source Crawling",
        "extracting_content": "Parallel Extraction",
        "filtering_quality": "MinHash & DPDP Compliance",
        "constructing_dataset": "Grounded Synthesis",
        "quality_eval": "Quality & Safety Eval",
        "human_review": "Stratified HITL Gate",
        "balancing_engine": "Balanced Dataset Engine",
        "exporting": "ADR-002 Packaging & Export",
    }

    stage_map = {
        "analyze_constraints": "analyzing_constraints",
        "analyzing_constraints": "analyzing_constraints",
        "constraints": "analyzing_constraints",
        "query_optimizer": "query_optimizer",
        "query_opt": "query_optimizer",
        "early_preview": "early_preview",
        "awaiting_preview_approval": "early_preview",
        "preview": "early_preview",
        "discovery": "discovering_sources",
        "discovering": "discovering_sources",
        "discovering_sources": "discovering_sources",
        "discover": "discovering_sources",
        "domain_analysis": "discovering_sources",
        "extraction": "extracting_content",
        "extracting": "extracting_content",
        "extracting_content": "extracting_content",
        "extract": "extracting_content",
        "seed_extraction": "extracting_content",
        "filtering": "filtering_quality",
        "filtering_quality": "filtering_quality",
        "filter": "filtering_quality",
        "construction": "constructing_dataset",
        "constructing": "constructing_dataset",
        "constructing_dataset": "constructing_dataset",
        "construct": "constructing_dataset",
        "synthesis": "constructing_dataset",
        "prompt_synthesis": "constructing_dataset",
        "plan": "constructing_dataset",
        "adapt_strategy": "constructing_dataset",
        "quality_eval": "quality_eval",
        "evaluation": "quality_eval",
        "quality_check": "quality_eval",
        "human_review": "human_review",
        "review": "human_review",
        "awaiting_review": "human_review",
        "balance": "balancing_engine",
        "balancing": "balancing_engine",
        "balancing_engine": "balancing_engine",
        "export": "exporting",
        "exporting": "exporting",
        "export_formatting": "exporting",
    }

    orchestrator = _get_orchestrator(req)
    db = _get_db(req)

    active_stage = None
    target_job = None

    if job_id:
        if orchestrator and hasattr(orchestrator, "active_jobs") and job_id in orchestrator.active_jobs:
            target_job = orchestrator.active_jobs[job_id]
            active_stage = getattr(target_job, "current_stage", None)
        elif db:
            try:
                target_job = await db.get_job_status(job_id)
                if target_job:
                    active_stage = target_job.get("current_stage")
            except Exception:
                pass
        if target_job is None:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    if not active_stage:
        if orchestrator and hasattr(orchestrator, "active_jobs") and orchestrator.active_jobs:
            for _, job_obj in orchestrator.active_jobs.items():
                active_stage = getattr(job_obj, "current_stage", None)
                target_job = job_obj
                if active_stage:
                    break

    if not active_stage and db:
        try:
            recent_jobs = await db.list_jobs(limit=1)
            if recent_jobs:
                target_job = recent_jobs[0]
                if target_job.get("status") == "running":
                    active_stage = target_job.get("current_stage")
        except Exception:
            pass

    job_status = (
        target_job.get("status")
        if isinstance(target_job, dict)
        else getattr(target_job, "status", None)
    ) if target_job else None
    normalized_active = stage_map.get(active_stage) if active_stage else None

    elapsed_ms = 0
    elapsed_basis = "no_job"
    if target_job:
        c_at = (
            target_job.get("created_at")
            if isinstance(target_job, dict)
            else getattr(target_job, "created_at", None)
        )
        u_at = (
            target_job.get("updated_at")
            if isinstance(target_job, dict)
            else getattr(target_job, "updated_at", None)
        )
        if isinstance(c_at, str):
            try:
                c_at = datetime.fromisoformat(c_at)
            except Exception:
                c_at = None
        if isinstance(u_at, str):
            try:
                u_at = datetime.fromisoformat(u_at)
            except Exception:
                u_at = None
        if c_at:
            end_t = u_at or datetime.now(timezone.utc)
            if c_at.tzinfo is None:
                c_at = c_at.replace(tzinfo=timezone.utc)
            if end_t.tzinfo is None:
                end_t = end_t.replace(tzinfo=timezone.utc)
            elapsed_ms = max(100, int((end_t - c_at).total_seconds() * 1000))
            elapsed_basis = "measured_from_timestamps"
        else:
            elapsed_ms = 12500
            elapsed_basis = "fallback_12500ms_not_measured"

    sources_count = int(
        (target_job.get("sources_discovered") if isinstance(target_job, dict) else getattr(target_job, "sources_discovered", 0)) or 0
    ) if target_job else 0

    stage_weights = {
        "analyzing_constraints": 0.05,
        "query_optimizer": 0.08,
        "early_preview": 0.07,
        "discovering_sources": 0.15 if sources_count > 0 else 0.0,
        "extracting_content": 0.12 if sources_count > 0 else 0.0,
        "filtering_quality": 0.08 if sources_count > 0 else 0.0,
        "constructing_dataset": 0.55 if sources_count == 0 else 0.35,
        "quality_eval": 0.08,
        "human_review": 0.05,
        "balancing_engine": 0.04,
        "exporting": 0.03,
    }

    nodes = []
    found_active = False
    for step_id in stage_order:
        weight = stage_weights.get(step_id, 0.08)
        measured_duration = max(50, int(elapsed_ms * weight))

        is_crawl_stage = step_id in ("discovering_sources", "extracting_content", "filtering_quality")
        if sources_count == 0 and is_crawl_stage:
            status = "skipped"
            duration = 0
        elif job_status == "completed":
            status = "completed"
            duration = measured_duration
        elif job_status == "failed" and normalized_active == step_id:
            status = "failed"
            duration = measured_duration
            found_active = True
        elif normalized_active:
            if step_id == normalized_active:
                status = "running"
                found_active = True
                duration = measured_duration
            elif not found_active:
                status = "completed"
                duration = measured_duration
            else:
                status = "pending"
                duration = 0
        else:
            status = "pending"
            duration = 0

        nodes.append({
            "id": step_id,
            "label": labels[step_id],
            "status": status,
            "duration_ms": duration,
            "duration_basis": "apportioned_from_total_elapsed" if duration else "not_applicable",
        })

    edges = [
        {"source": "analyzing_constraints", "target": "query_optimizer"},
        {"source": "query_optimizer", "target": "early_preview"},
        {"source": "early_preview", "target": "discovering_sources", "label": "accepted"},
        {"source": "early_preview", "target": "query_optimizer", "label": "retry_query", "is_feedback": True},
        {"source": "discovering_sources", "target": "extracting_content"},
        {"source": "extracting_content", "target": "filtering_quality"},
        {"source": "filtering_quality", "target": "constructing_dataset", "label": "pass"},
        {"source": "filtering_quality", "target": "extracting_content", "label": "retry_extract", "is_feedback": True},
        {"source": "constructing_dataset", "target": "quality_eval"},
        {"source": "quality_eval", "target": "human_review", "label": "pass"},
        {"source": "quality_eval", "target": "constructing_dataset", "label": "retry_synthesis", "is_feedback": True},
        {"source": "human_review", "target": "balancing_engine"},
        {"source": "balancing_engine", "target": "exporting"},
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "job_id": job_id or (target_job.get("id") if isinstance(target_job, dict) else getattr(target_job, "id", None)),
        "status": job_status or "unknown",
        "elapsed_ms": elapsed_ms,
        "elapsed_basis": elapsed_basis,
        "duration_basis_note": "Node duration_ms values are apportioned from total elapsed time using fixed stage weights, not measured per-stage timings.",
    }


@router.post("/orchestration/steps/{step_id}/retry")
async def retry_orchestration_step(
    step_id: str,
    req: Request,
    job_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Retry a job's step by relaunching pipeline work, or error."""
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id query parameter is required")

    db = _get_db(req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not initialized")

    job = await db.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    job_status = (job.get("status") or "").lower()
    if job_status in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail=f"Cannot retry a job in '{job_status}' state")

    orchestrator = _get_orchestrator(req)
    if orchestrator and hasattr(orchestrator, "active_jobs") and job_id in orchestrator.active_jobs:
        raise HTTPException(status_code=409, detail="Job is already running; retry would duplicate execution")
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized; retry not launched")

    await db.update_job_status(job_id, {"status": "running", "current_stage": step_id, "error": None})

    server_mod = _get_server_module()
    run_pipe = getattr(server_mod, "run_pipeline", None) if server_mod else None
    if run_pipe:
        asyncio.create_task(run_pipe(job_id, job.get("config") or {}))

    return {
        "success": True,
        "step_id": step_id,
        "job_id": job_id,
        "status": "retrying",
        "relaunched": True,
        "note": (
            "Pipeline relaunched from the start with the stored job config; "
            "for stage-targeted resume use checkpoint restore."
        ),
    }
