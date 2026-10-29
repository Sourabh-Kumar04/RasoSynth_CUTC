"""
Human Review API — endpoints for managing the human review queue.

Added vs v1:
  GET  /api/review/queue/export         stream approved items as JSONL
  GET  /api/review/paused               list dataset jobs currently paused at HITL gate
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from api.auth import User, UserRole, get_current_user, require_role
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/review", tags=["review"])


def _enforce_owner(resource: Optional[dict], current_user: User, resource_name: str = "Review item"):
    """Enforce owner check: Admin can access any row; non-admin can only access own rows.
    
    Rows with owner=None (legacy single-tenant rows) are visible only to ADMIN.
    Returns 404 (Not Found) on mismatch to prevent existence leakage.
    """
    if not resource:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")
    if current_user.role == UserRole.ADMIN:
        return
    owner = resource.get("owner")
    if not owner or owner != current_user.username:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")


# ── Dependency ────────────────────────────────────────────────────────────────

def _svc(request: Request):
    svc = getattr(request.app.state, "review_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Review service not initialised")
    return svc


# ── Schemas ───────────────────────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    instruction: str
    response: str
    job_id: str
    dataset_id: str = ""
    source_url: str = ""
    source_text: str = ""
    # Omitted scores are unavailable (None -> NULL in the review queue),
    # never a measured 0.0.
    quality_score: Optional[float] = None
    hallucination_risk: Optional[float] = None
    duplicate_score: Optional[float] = None
    diversity_score: Optional[float] = None


class ReviewAction(BaseModel):
    # Accepted for client compatibility but IGNORED: reviewer identity is taken
    # from the auth token (current_user.username) in every handler below.
    reviewer: str = ""
    notes: str = ""


class EditAction(ReviewAction):
    edited_instruction: Optional[str] = None
    edited_response: Optional[str] = None


class BulkAction(BaseModel):
    filters: dict
    # Ignored: reviewer identity is taken from the auth token (see ReviewAction).
    reviewer: str = ""
    reason: str = ""


# ── Queue endpoints ───────────────────────────────────────────────────────────

@router.get("/queue")
async def list_queue(
    status: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    svc=Depends(_svc),
    current_user: User = Depends(get_current_user)):
    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    return await svc.get_queue(status=status, job_id=job_id, page=page, page_size=page_size, owner=owner_filter)


@router.get("/queue/export")
async def export_approved(
    job_id: Optional[str] = Query(None, description="Filter by dataset job ID"),
    svc=Depends(_svc),
    current_user: User = Depends(get_current_user)):
    """
    Stream all approved review items as a JSONL file suitable for fine-tuning.
    Each line: {"instruction": ..., "response": ..., "input": "", ...}
    """
    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    async def _stream():
        async for line in svc.export_approved(job_id=job_id, owner=owner_filter):
            yield line

    return StreamingResponse(
        _stream(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="approved_samples.jsonl"'},
    )


@router.get("/queue/{item_id}")
async def get_item(item_id: str, svc=Depends(_svc),
    current_user: User = Depends(get_current_user)):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    return item


@router.post("/queue", status_code=201)
async def submit_for_review(body: SubmitRequest, svc=Depends(_svc),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    return await svc.submit(
        instruction=body.instruction,
        response=body.response,
        job_id=body.job_id,
        dataset_id=body.dataset_id,
        source_url=body.source_url,
        source_text=body.source_text,
        quality_score=body.quality_score,
        hallucination_risk=body.hallucination_risk,
        duplicate_score=body.duplicate_score,
        diversity_score=body.diversity_score,
        owner=current_user.username,
    )


@router.post("/queue/{item_id}/approve")
async def approve_item(item_id: str, action: ReviewAction, svc=Depends(_svc),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    result = await svc.approve(item_id, current_user.username, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/reject")
async def reject_item(item_id: str, action: ReviewAction, svc=Depends(_svc),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    result = await svc.reject(item_id, current_user.username, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/edit")
async def edit_item(item_id: str, action: EditAction, svc=Depends(_svc),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    result = await svc.edit(
        item_id, current_user.username,
        edited_instruction=action.edited_instruction,
        edited_response=action.edited_response,
        notes=action.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/flag")
async def flag_item(item_id: str, action: ReviewAction, svc=Depends(_svc),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    result = await svc.flag(item_id, current_user.username, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/bulk")
async def bulk_action(action: BulkAction, svc=Depends(_svc),
    current_user: User = Depends(require_role([UserRole.ADMIN]))):
    # Copy to avoid mutating the pydantic model's dict
    filters = dict(action.filters)
    action_type = filters.pop("action", "approve")
    if action_type == "approve":
        count = await svc.bulk_approve(filters, current_user.username, action.reason)
    else:
        count = await svc.bulk_reject(filters, current_user.username, action.reason)
    return {"affected": count, "action": action_type}


@router.get("/stats")
async def review_stats(svc=Depends(_svc),
    current_user: User = Depends(get_current_user)):
    return await svc.get_stats()


# ── HITL endpoints ────────────────────────────────────────────────────────────

@router.get("/paused")
async def list_paused_jobs(svc=Depends(_svc),
    current_user: User = Depends(get_current_user)):
    """Return list of dataset job IDs currently paused at the HITL gate."""
    paused = set(svc.get_paused_jobs())
    if hasattr(svc, "db") and svc.db:
        try:
            from sqlalchemy import select
            from core.db import Job as JobModel
            async with svc.db.session_maker() as session:
                result = await session.execute(
                    select(JobModel.id).where(JobModel.status == "awaiting_review")
                )
                for row in result.fetchall():
                    paused.add(str(row[0]))
        except Exception:
            pass
    return {"paused_jobs": sorted(list(paused))}


@router.get("/jobs/{job_id}/status")
async def hitl_job_status(job_id: str, svc=Depends(_svc),
    current_user: User = Depends(get_current_user)):
    if hasattr(svc, "db") and svc.db:
        job = await svc.db.get_job(job_id)
        if job:
            _enforce_owner(job.to_dict(), current_user, resource_name="Job")
    is_paused = svc.is_job_paused(job_id)
    if not is_paused and hasattr(svc, "db") and svc.db:
        try:
            job = await svc.db.get_job(job_id)
            if job and job.status == "awaiting_review":
                is_paused = True
        except Exception:
            pass
    return {"job_id": job_id, "paused": is_paused}


@router.post("/jobs/{job_id}/resume")
async def hitl_resume_job(job_id: str, svc=Depends(_svc),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    if hasattr(svc, "db") and svc.db:
        job = await svc.db.get_job(job_id)
        if job:
            _enforce_owner(job.to_dict(), current_user, resource_name="Job")
    resumed = await svc.resume_job(job_id)
    if not resumed:
        raise HTTPException(status_code=404, detail=f"Job {job_id} is not currently paused")
    return {"status": "resumed", "job_id": job_id}
