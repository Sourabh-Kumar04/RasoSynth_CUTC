"""Durable recrawl, refresh, and retraining schedule API."""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth import User, get_current_user
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class ScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    workflow_type: Literal["recrawl", "refresh", "retrain"]
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
    current_user: User = Depends(get_current_user)):
    if body.workflow_type == "retrain" and not body.workflow_config.get("dataset_version_id"):
        raise HTTPException(status_code=422, detail="Retraining schedules require an immutable dataset_version_id")
    return await db.create_workflow_schedule(**body.model_dump())


@router.get("")
async def list_schedules(limit: int = 100, db=Depends(_db),
    current_user: User = Depends(get_current_user)):
    return {"items": await db.list_workflow_schedules(limit=min(max(limit, 1), 500))}


@router.get("/{schedule_id}/runs")
async def list_schedule_runs(schedule_id: str, limit: int = 100, db=Depends(_db),
    current_user: User = Depends(get_current_user)):
    return {"items": await db.list_workflow_schedule_runs(schedule_id, limit=min(max(limit, 1), 500))}
