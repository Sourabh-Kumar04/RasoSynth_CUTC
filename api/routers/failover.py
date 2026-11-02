"""Provider switching and automatic failover endpoints for RasoSynthTune."""
from __future__ import annotations

import logging
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.auth import User, UserRole, get_current_user, require_role
from api.legacy_schemas import (
    FailoverHistoryResponse,
    FailoverRequest,
    FailoverResponse,
    MigrationRecordResponse,
    ProviderSwitchRequest,
    ProviderSwitchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Failover"])


def _get_server_module():
    return sys.modules.get("api.server")


def _get_failover_engine(req: Request):
    server_mod = _get_server_module()
    return getattr(req.app.state, "failover_engine", None) or (
        getattr(server_mod, "failover_engine", None) if server_mod else None
    )


def _get_provider_hot_switcher(req: Request):
    server_mod = _get_server_module()
    return getattr(req.app.state, "provider_hot_switcher", None) or (
        getattr(server_mod, "provider_hot_switcher", None) if server_mod else None
    )


def _get_orchestrator(req: Request):
    server_mod = _get_server_module()
    return getattr(server_mod, "orchestrator", None) if server_mod and hasattr(server_mod, "orchestrator") else getattr(req.app.state, "orchestrator", None)


def _get_router(req: Request):
    server_mod = _get_server_module()
    return getattr(server_mod, "router", None) if server_mod and hasattr(server_mod, "router") else getattr(req.app.state, "router", None)


@router.post("/providers/switch", response_model=ProviderSwitchResponse, tags=["Providers"])
async def switch_provider(
    request: ProviderSwitchRequest,
    req: Request,
    admin_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Manually switch to a different provider during job execution."""
    hot_switcher = _get_provider_hot_switcher(req)
    if not hot_switcher:
        raise HTTPException(status_code=503, detail="Provider switcher not available")

    success = await hot_switcher.switch_provider(
        job_id=request.job_id,
        new_provider=request.new_provider,
        create_checkpoint=request.create_checkpoint,
    )

    if success:
        return ProviderSwitchResponse(
            success=True,
            to_provider=request.new_provider,
            message=f"Switched to provider {request.new_provider}",
        )
    return ProviderSwitchResponse(
        success=False,
        message=f"Failed to switch to provider {request.new_provider}",
    )


@router.post("/providers/failover", response_model=FailoverResponse, tags=["Providers"])
async def trigger_failover(
    request: FailoverRequest,
    req: Request,
    admin_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Manually trigger failover for a job."""
    failover_engine = _get_failover_engine(req)
    if not failover_engine:
        raise HTTPException(status_code=503, detail="Failover engine not available")

    orchestrator = _get_orchestrator(req)
    current_provider = None
    if orchestrator and hasattr(orchestrator, "active_jobs") and request.job_id in orchestrator.active_jobs:
        job = orchestrator.active_jobs[request.job_id]
        current_provider = job.config.get("provider") if hasattr(job, "config") and job.config else None

    if not current_provider:
        router_inst = _get_router(req)
        current_provider = (
            router_inst.config.provider_priority[0]
            if router_inst and hasattr(router_inst, "config") and hasattr(router_inst.config, "provider_priority") and router_inst.config.provider_priority
            else "google_gemini"
        )

    new_provider = await failover_engine.handle_failure(
        job_id=request.job_id,
        current_provider=current_provider,
        error=Exception(request.reason or "Manual failover triggered"),
        stage="extraction",
        progress=0.5,
    )

    if new_provider:
        return FailoverResponse(
            success=True,
            from_provider=current_provider,
            to_provider=new_provider,
            failure_type="manual_failover",
            message=f"Failover completed: {current_provider} -> {new_provider}",
        )
    return FailoverResponse(
        success=False,
        from_provider=current_provider,
        message="No fallback provider available",
    )


@router.get("/failover/history", response_model=FailoverHistoryResponse)
async def get_failover_history(
    req: Request,
    job_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Get failover history."""
    failover_engine = _get_failover_engine(req)
    if not failover_engine:
        raise HTTPException(status_code=503, detail="Failover engine not available")

    migrations = failover_engine.get_migration_history(job_id)
    migrations = migrations[-limit:]

    return FailoverHistoryResponse(
        migrations=[
            MigrationRecordResponse(
                migration_id=m.migration_id,
                job_id=m.job_id,
                from_provider=m.from_provider,
                to_provider=m.to_provider,
                failure_type=m.failure_type.value if m.failure_type else None,
                checkpoint_id=m.checkpoint_id,
                success=m.success,
                timestamp=m.timestamp,
                error=m.error,
            )
            for m in migrations
        ],
        total_count=len(migrations),
        failure_stats=failover_engine.get_failure_stats(),
    )


@router.get("/failover/stats")
async def get_failover_stats(
    req: Request,
    current_user: User = Depends(get_current_user),
):
    """Get failover statistics."""
    failover_engine = _get_failover_engine(req)
    if not failover_engine:
        raise HTTPException(status_code=503, detail="Failover engine not available")

    return {
        "failure_stats": failover_engine.get_failure_stats(),
        "total_migrations": len(failover_engine.migration_history),
        "circuit_breakers": {
            name: {"state": cb.state.value, "failures": cb.failure_count}
            for name, cb in failover_engine.circuit_breakers.items()
        },
    }
