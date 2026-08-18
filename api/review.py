"""
Human Review API — endpoints for managing the human review queue.

Added vs v1:
  GET  /api/review/queue/export         stream approved items as JSONL
  GET  /api/review/paused               list dataset jobs currently paused at HITL gate
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/review", tags=["review"])


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
    quality_score: float = 0.0
    hallucination_risk: float = 0.0
    duplicate_score: float = 0.0
    diversity_score: float = 0.0


class ReviewAction(BaseModel):
    reviewer: str
    notes: str = ""


class EditAction(ReviewAction):
    edited_instruction: Optional[str] = None
    edited_response: Optional[str] = None


class BulkAction(BaseModel):
    filters: dict
    reviewer: str
    reason: str = ""


# ── Queue endpoints ───────────────────────────────────────────────────────────

@router.get("/queue")
async def list_queue(
    status: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    svc=Depends(_svc),
):
    return await svc.get_queue(status=status, job_id=job_id, page=page, page_size=page_size)


@router.get("/queue/export")
async def export_approved(
    job_id: Optional[str] = Query(None, description="Filter by dataset job ID"),
    svc=Depends(_svc),
):
    """
    Stream all approved review items as a JSONL file suitable for fine-tuning.
    Each line: {"instruction": ..., "response": ..., "input": "", ...}
    """
    async def _stream():
        async for line in svc.export_approved(job_id=job_id):
            yield line

    return StreamingResponse(
        _stream(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="approved_samples.jsonl"'},
    )


@router.get("/queue/{item_id}")
async def get_item(item_id: str, svc=Depends(_svc)):
    item = await svc.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.post("/queue", status_code=201)
async def submit_for_review(body: SubmitRequest, svc=Depends(_svc)):
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
    )


@router.post("/queue/{item_id}/approve")
async def approve_item(item_id: str, action: ReviewAction, svc=Depends(_svc)):
    result = await svc.approve(item_id, action.reviewer, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/reject")
async def reject_item(item_id: str, action: ReviewAction, svc=Depends(_svc)):
    result = await svc.reject(item_id, action.reviewer, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/edit")
async def edit_item(item_id: str, action: EditAction, svc=Depends(_svc)):
    result = await svc.edit(
        item_id, action.reviewer,
        edited_instruction=action.edited_instruction,
        edited_response=action.edited_response,
        notes=action.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/flag")
async def flag_item(item_id: str, action: ReviewAction, svc=Depends(_svc)):
    result = await svc.flag(item_id, action.reviewer, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/bulk")
async def bulk_action(action: BulkAction, svc=Depends(_svc)):
    # Copy to avoid mutating the pydantic model's dict
    filters = dict(action.filters)
    action_type = filters.pop("action", "approve")
    if action_type == "approve":
        count = await svc.bulk_approve(filters, action.reviewer, action.reason)
    else:
        count = await svc.bulk_reject(filters, action.reviewer, action.reason)
    return {"affected": count, "action": action_type}


@router.get("/stats")
async def review_stats(svc=Depends(_svc)):
    return await svc.get_stats()


# ── HITL endpoints ────────────────────────────────────────────────────────────

@router.get("/paused")
async def list_paused_jobs(svc=Depends(_svc)):
    """Return list of dataset job IDs currently paused at the HITL gate."""
    return {"paused_jobs": svc.get_paused_jobs()}


@router.get("/jobs/{job_id}/status")
async def hitl_job_status(job_id: str, svc=Depends(_svc)):
    return {"job_id": job_id, "paused": svc.is_job_paused(job_id)}


@router.post("/jobs/{job_id}/resume")
async def hitl_resume_job(job_id: str, svc=Depends(_svc)):
    resumed = await svc.resume_job(job_id)
    if not resumed:
        raise HTTPException(status_code=404, detail=f"Job {job_id} is not currently paused")
    return {"status": "resumed", "job_id": job_id}
