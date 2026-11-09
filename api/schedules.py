"""Durable recrawl, refresh, and retraining schedule API.

Note: Schedules currently operate in single-tenant mode across the cluster;
retraining and recrawl schedules are managed by system operators.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth import User, UserRole, get_current_user, require_role
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class ScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    workflow_type: Literal["recrawl", "refresh", "retrain", "calibration", "drift_audit", "periodic_dpo_alignment"]
    interval_seconds: int = Field(ge=60)
    workflow_config: dict[str, Any] = Field(default_factory=dict)
    next_run_at: Optional[datetime] = None


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database is not initialized")
    return db


@router.post("", status_code=201)
async def create_schedule(body: ScheduleCreateRequest, db=Depends(_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    """Create a durable workflow schedule. Note: schedules operate in single-tenant mode."""
    if body.workflow_type == "retrain" and not body.workflow_config.get("dataset_version_id"):
        raise HTTPException(status_code=422, detail="Retraining schedules require an immutable dataset_version_id")
    return await db.create_workflow_schedule(**body.model_dump())


@router.get("")
async def list_schedules(limit: int = 100, db=Depends(_db),
    current_user: User = Depends(get_current_user)):
    """List schedules. Note: operates in single-tenant mode."""
    return {"items": await db.list_workflow_schedules(limit=min(max(limit, 1), 500))}


@router.get("/{schedule_id}/runs")
async def list_schedule_runs(schedule_id: str, limit: int = 100, db=Depends(_db),
    current_user: User = Depends(get_current_user)):
    """List runs for a schedule. Note: operates in single-tenant mode."""
    return {"items": await db.list_workflow_schedule_runs(schedule_id, limit=min(max(limit, 1), 500))}


@router.post("/{schedule_id}/execute")
async def execute_schedule_now(
    schedule_id: str,
    request: Request,
    db=Depends(_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    """Trigger manual execution of a workflow schedule."""
    schedules = await db.list_workflow_schedules(limit=500)
    sched = next((s for s in schedules if s.get("id") == schedule_id), None)
    if not sched:
        raise HTTPException(status_code=404, detail=f"Schedule '{schedule_id}' not found")

    wtype = sched.get("workflow_type")
    wconfig = sched.get("workflow_config", {})

    run_result = {"status": "dispatched", "workflow_type": wtype, "schedule_id": schedule_id}

    if wtype == "periodic_dpo_alignment":
        review_svc = getattr(request.app.state, "review_service", None)
        if review_svc:
            min_pairs = int(wconfig.get("min_preference_pairs", 25))
            job_filter = wconfig.get("job_id")
            pairs = await review_svc.export_dpo_pairs(job_id=job_filter)
            if len(pairs) >= min_pairs:
                from core.orchestrator_pkg.orchestrator import DatasetOrchestrator
                orch = getattr(request.app.state, "orchestrator", None)
                if orch:
                    dpo_res = await orch.trigger_dpo_finetune(
                        job_id=job_filter or "scheduled-dpo-batch",
                        base_model=wconfig.get("base_model", "sarvamai/sarvam-2b-v0.5"),
                        training_method="dpo",
                        review_service=review_svc,
                    )
                    run_result["dpo_alignment"] = dpo_res
            else:
                run_result["status"] = "skipped_below_threshold"
                run_result["available_pairs"] = len(pairs)
                run_result["threshold"] = min_pairs

    return run_result
