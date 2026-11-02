"""Checkpoint management and recovery endpoints for RasoSynthTune."""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.auth import User, UserRole, enforce_owner, get_current_user, require_role
from api.legacy_schemas import (
    CheckpointResponse,
    CheckpointStage,
    CreateCheckpointRequest,
    ProviderContextSchema,
    RestoreCheckpointRequest,
    RestoreCheckpointResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Checkpoints"])


def _get_server_module():
    return sys.modules.get("api.server")


def _get_db(req: Request):
    server_mod = _get_server_module()
    return getattr(req.app.state, "db", None) or (
        getattr(server_mod, "db", None) if server_mod else None
    )


def _get_checkpoint_manager(req: Request):
    server_mod = _get_server_module()
    return getattr(req.app.state, "checkpoint_manager", None) or (
        getattr(server_mod, "checkpoint_manager", None) if server_mod else None
    )


def _get_orchestrator(req: Request):
    server_mod = _get_server_module()
    return (
        getattr(server_mod, "orchestrator", None)
        if server_mod and hasattr(server_mod, "orchestrator")
        else getattr(req.app.state, "orchestrator", None)
    )


def _build_checkpoint_response(checkpoint) -> CheckpointResponse:
    provider_context = None
    if getattr(checkpoint, "provider_context", None):
        pc = checkpoint.provider_context
        provider_context = ProviderContextSchema(
            provider_name=pc.provider_name,
            model=pc.model,
            api_key_hash=pc.api_key_hash,
            base_url=pc.base_url,
            capabilities=pc.capabilities,
            latency_ms=pc.latency_ms,
            cost_accumulated=pc.cost_accumulated,
        )

    return CheckpointResponse(
        checkpoint_id=checkpoint.checkpoint_id,
        job_id=checkpoint.job_id,
        stage=CheckpointStage(checkpoint.stage.value if hasattr(checkpoint.stage, "value") else checkpoint.stage),
        progress=checkpoint.progress,
        sources_discovered=checkpoint.sources_discovered,
        sources_extracted=checkpoint.sources_extracted,
        samples_filtered=checkpoint.samples_filtered,
        samples_generated=checkpoint.samples_generated,
        provider_context=provider_context,
        fallback_provider=checkpoint.fallback_provider,
        created_at=checkpoint.created_at,
        version=checkpoint.version,
    )


@router.post("/checkpoints", response_model=CheckpointResponse, status_code=201)
async def create_checkpoint(
    request: CreateCheckpointRequest,
    req: Request,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
):
    """Create a new checkpoint for a job."""
    checkpoint_manager = _get_checkpoint_manager(req)
    if not checkpoint_manager:
        raise HTTPException(status_code=503, detail="Checkpoint manager not available")
    db = _get_db(req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Verify job existence and owner
    job = await db.get_job_status(request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
    enforce_owner(job, current_user, resource_name="Job")

    from core.orchestrator_pkg.checkpoints import ProviderContext

    provider_context = None
    if request.provider_name:
        provider_context = ProviderContext(
            provider_name=request.provider_name,
            model=request.provider_model or "",
            api_key_hash="",
            capabilities=[],
        )

    checkpoint = await checkpoint_manager.create_checkpoint(
        job_id=request.job_id,
        stage=request.stage,
        progress=request.progress,
        sources_discovered=request.sources_discovered,
        sources_extracted=request.sources_extracted,
        samples_filtered=request.samples_filtered,
        samples_generated=request.samples_generated,
        provider_context=provider_context,
        extracted_content=request.extracted_content,
        filtered_samples=request.filtered_samples,
        constructed_samples=request.constructed_samples,
        metadata=request.metadata,
    )

    return _build_checkpoint_response(checkpoint)


@router.get("/checkpoints/{job_id}", response_model=CheckpointResponse)
async def get_checkpoint(
    job_id: str,
    req: Request,
    checkpoint_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Get checkpoint(s) for a job."""
    checkpoint_manager = _get_checkpoint_manager(req)
    if not checkpoint_manager:
        raise HTTPException(status_code=503, detail="Checkpoint manager not available")
    db = _get_db(req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Verify job existence and owner
    job = await db.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    enforce_owner(job, current_user, resource_name="Job")

    if checkpoint_id:
        checkpoint = await checkpoint_manager.store.get_by_id(checkpoint_id)
        if checkpoint and checkpoint.job_id != job_id:
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint {checkpoint_id} does not belong to job {job_id}",
            )
    else:
        checkpoint = await checkpoint_manager.store.get_latest(job_id)

    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return _build_checkpoint_response(checkpoint)


@router.get("/checkpoints/{job_id}/history", response_model=list[CheckpointResponse])
async def get_checkpoint_history(
    job_id: str,
    req: Request,
    limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Get checkpoint history for a job."""
    checkpoint_manager = _get_checkpoint_manager(req)
    if not checkpoint_manager:
        raise HTTPException(status_code=503, detail="Checkpoint manager not available")
    db = _get_db(req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Verify job existence and owner
    job = await db.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    enforce_owner(job, current_user, resource_name="Job")

    checkpoints = await checkpoint_manager.store.get_history(job_id, limit)
    return [_build_checkpoint_response(cp) for cp in checkpoints]


@router.post("/checkpoints/{job_id}/restore", response_model=RestoreCheckpointResponse)
async def restore_checkpoint(
    job_id: str,
    request: RestoreCheckpointRequest,
    req: Request,
    admin_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Resume a non-completed job from persisted pipeline state."""
    if request.job_id != job_id:
        raise HTTPException(
            status_code=400,
            detail=f"Path job_id '{job_id}' does not match request body job_id '{request.job_id}'",
        )

    checkpoint_manager = _get_checkpoint_manager(req)
    if not checkpoint_manager:
        raise HTTPException(status_code=503, detail="Checkpoint manager not available")
    db = _get_db(req)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    stored_job = await db.get_job_status(job_id)
    if not stored_job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if request.checkpoint_id:
        cp = await checkpoint_manager.store.get_by_id(request.checkpoint_id)
        if not cp or cp.job_id != job_id:
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint {request.checkpoint_id} does not belong to job {job_id}",
            )

    resume_state = await checkpoint_manager.resume_from_checkpoint(
        job_id=request.job_id,
        checkpoint_id=request.checkpoint_id,
    )

    if not resume_state:
        return RestoreCheckpointResponse(
            success=False,
            message="No checkpoint found to restore from",
        )

    checkpoint = resume_state["checkpoint"]
    stage_val = checkpoint.stage.value if hasattr(checkpoint.stage, "value") else str(checkpoint.stage)
    if stage_val == "completed":
        return RestoreCheckpointResponse(
            success=False,
            message="Completed checkpoints cannot be resumed.",
        )

    orchestrator = _get_orchestrator(req)
    if not db or not orchestrator:
        raise HTTPException(status_code=503, detail="Pipeline is not available for checkpoint recovery")
    if hasattr(orchestrator, "active_jobs") and request.job_id in orchestrator.active_jobs:
        raise HTTPException(status_code=409, detail="Job is already running")

    requested_stage = request.resume_from_stage or resume_state["resume_from_stage"]
    resume_state["resume_from_stage"] = requested_stage
    stage_name = getattr(requested_stage, "value", requested_stage)
    await db.update_job(
        request.job_id,
        status="pending",
        current_stage=f"resuming_{stage_name}",
        progress=resume_state["progress"],
        error=None,
    )

    server_mod = _get_server_module()
    run_pipe = getattr(server_mod, "run_pipeline", None) if server_mod else None
    if run_pipe:
        asyncio.create_task(run_pipe(request.job_id, stored_job["config"], resume_state=resume_state))

    resume_stage_str = (
        resume_state["resume_from_stage"].value
        if hasattr(resume_state["resume_from_stage"], "value")
        else str(resume_state["resume_from_stage"])
    )

    return RestoreCheckpointResponse(
        success=True,
        checkpoint=_build_checkpoint_response(checkpoint),
        resume_from_stage=resume_stage_str,
        progress=resume_state["progress"],
        samples_generated=resume_state["samples_generated"],
        message="Checkpoint accepted. The job has been queued to resume from the saved stage.",
    )
