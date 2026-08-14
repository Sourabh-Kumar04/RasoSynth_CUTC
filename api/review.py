"""
Human Review API — endpoints for managing the human review queue.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from core.review_service import ReviewService

router = APIRouter(prefix="/api/review", tags=["review"])

review_service = ReviewService()


# --- Pydantic schemas ---


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


# --- Endpoints ---


@router.get("/queue")
async def list_queue(
    status: Optional[str] = Query(None, description="Filter by status"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """List the review queue with filtering and pagination."""
    return review_service.get_queue(status=status, job_id=job_id, page=page, page_size=page_size)


@router.get("/queue/{item_id}")
async def get_item(item_id: str):
    """Get a single review queue item."""
    item = review_service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item


@router.post("/queue")
async def submit_for_review(request: SubmitRequest):
    """Submit a sample for human review."""
    item = review_service.submit(
        instruction=request.instruction,
        response=request.response,
        job_id=request.job_id,
        dataset_id=request.dataset_id,
        source_url=request.source_url,
        source_text=request.source_text,
        quality_score=request.quality_score,
        hallucination_risk=request.hallucination_risk,
        duplicate_score=request.duplicate_score,
        diversity_score=request.diversity_score,
    )
    return item.to_dict()


@router.post("/queue/{item_id}/approve")
async def approve_item(item_id: str, action: ReviewAction):
    """Approve a review queue item."""
    result = review_service.approve(item_id, action.reviewer, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/reject")
async def reject_item(item_id: str, action: ReviewAction):
    """Reject a review queue item."""
    result = review_service.reject(item_id, action.reviewer, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/edit")
async def edit_item(item_id: str, action: EditAction):
    """Edit and approve a review queue item."""
    result = review_service.edit(
        item_id,
        action.reviewer,
        edited_instruction=action.edited_instruction,
        edited_response=action.edited_response,
        notes=action.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/bulk")
async def bulk_action(action: BulkAction):
    """Bulk approve or reject items matching filters."""
    action_type = action.filters.pop("action", "approve")
    if action_type == "approve":
        count = review_service.bulk_approve(action.filters, action.reviewer, action.reason)
    else:
        count = review_service.bulk_reject(action.filters, action.reviewer, action.reason)
    return {"affected": count, "action": action_type}


@router.get("/stats")
async def review_stats():
    """Get review statistics."""
    return review_service.get_stats()