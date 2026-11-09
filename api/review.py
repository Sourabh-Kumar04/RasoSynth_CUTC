"""
Human Review API — endpoints for managing the human review queue.

Added vs v1:
  GET  /api/review/queue/export         stream approved items as JSONL
  GET  /api/review/paused               list dataset jobs currently paused at HITL gate
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from api.auth import User, UserRole, get_current_user, require_role
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
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
        db = getattr(request.app.state, "db", None)
        if db is not None:
            from core.review_service import ReviewService
            db_mgr = getattr(db, "db", db)
            svc = ReviewService(db=db_mgr)
            request.app.state.review_service = svc
            return svc
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
    reason_code: Optional[str] = None
    reason_codes: Optional[list[str]] = None


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
    current_user: User = Depends(get_current_user),
    status: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    strategy: str = Query("fifo", pattern="^(fifo|uncertainty|entropy|quality_asc|quality_desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    svc=Depends(_svc)):
    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    if strategy in ("uncertainty", "entropy", "quality_asc", "quality_desc"):
        items, total = await svc.get_prioritized_queue(
            strategy=strategy,
            status=status or "pending",
            job_id=job_id,
            page=page,
            page_size=page_size,
            owner=owner_filter,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size, "strategy": strategy}
    return await svc.get_queue(status=status, job_id=job_id, page=page, page_size=page_size, owner=owner_filter)


@router.get("/queue/export")
async def export_approved(
    current_user: User = Depends(get_current_user),
    job_id: Optional[str] = Query(None, description="Filter by dataset job ID"),
    svc=Depends(_svc)):
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


@router.get("/queue/export-dpo")
async def export_dpo_pairs_endpoint(
    current_user: User = Depends(get_current_user),
    job_id: Optional[str] = Query(None, description="Filter by dataset job ID"),
    svc=Depends(_svc)):
    """
    Export pairwise DPO/ORPO training records mined from human reviewer edits.
    Each row: {"prompt": ..., "chosen": ..., "rejected": ..., "source_review_id": ...}
    """
    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    pairs = await svc.export_dpo_pairs(job_id=job_id, owner=owner_filter)
    return {"pairs": pairs, "count": len(pairs)}


class TriggerDpoFinetuneRequest(BaseModel):
    base_model: str = "sarvamai/sarvam-2b-v0.5"
    training_method: str = "dpo"
    output_model_name: Optional[str] = None
    num_train_epochs: int = 3
    learning_rate: float = 0.0002
    lora_r: int = 16
    lora_alpha: int = 32


@router.post("/jobs/{job_id}/trigger-dpo-finetune")
async def trigger_dpo_finetune_endpoint(
    job_id: str,
    request: Request,
    body: TriggerDpoFinetuneRequest = Body(...),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
    svc=Depends(_svc),
):
    """
    Closed-loop alignment trigger:
    Extracts mined DPO preference pairs for `job_id`,
    persists them as a JSONL training dataset, and creates an automated fine-tuning job.
    """
    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    pairs = await svc.export_dpo_pairs(job_id=job_id, owner=owner_filter)
    if not pairs:
        raise HTTPException(
            status_code=400,
            detail=f"No DPO preference pairs mined for job '{job_id}'. Edit items in the review queue to produce chosen/rejected pairs."
        )

    out_dir = Path("outputs/finetune")
    out_dir.mkdir(parents=True, exist_ok=True)
    dpo_filename = f"dpo_{job_id}_{int(time.time())}.jsonl"
    dpo_path = out_dir / dpo_filename

    with open(dpo_path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    output_model_name = body.output_model_name or f"dpo-aligned-{job_id[:8]}"

    manager = getattr(request.app.state, "ft_manager", None)
    if manager is None:
        try:
            from finetuning.job_manager import FinetuneJobManager
            from core.db import DatabaseManager
            db_mgr = getattr(request.app.state, "db", None) or DatabaseManager()
            manager = FinetuneJobManager(db_manager=db_mgr)
            request.app.state.ft_manager = manager
        except Exception as e:
            logger.warning("Could not instantiate FinetuneJobManager: %s", e)

    job_result = None
    if manager:
        payload = {
            "dataset_path": str(dpo_path),
            "base_model": body.base_model,
            "training_method": body.training_method,
            "output_model_name": output_model_name,
            "num_train_epochs": body.num_train_epochs,
            "learning_rate": body.learning_rate,
            "lora_r": body.lora_r,
            "lora_alpha": body.lora_alpha,
            "owner": current_user.username,
        }
        job_result = await manager.create_job(payload)

    return {
        "status": "launched" if job_result else "dataset_prepared",
        "job_id": job_id,
        "finetune_job_id": job_result.get("id") if isinstance(job_result, dict) else str(job_result or ""),
        "preference_pairs_count": len(pairs),
        "dataset_path": str(dpo_path),
        "output_model_name": output_model_name,
        "finetune_job": job_result,
    }


@router.get("/queue/{item_id}")
async def get_item(item_id: str,
    current_user: User = Depends(get_current_user),
    svc=Depends(_svc)):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    return item


@router.post("/queue", status_code=201)
async def submit_for_review(body: SubmitRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
    svc=Depends(_svc)):
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
async def approve_item(item_id: str, action: ReviewAction,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
    svc=Depends(_svc)):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    result = await svc.approve(item_id, current_user.username, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/reject")
async def reject_item(item_id: str, action: ReviewAction,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
    svc=Depends(_svc)):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    codes = action.reason_codes or ([action.reason_code] if action.reason_code else None)
    result = await svc.reject(item_id, current_user.username, action.notes, reason_codes=codes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/edit")
async def edit_item(item_id: str, action: EditAction,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
    svc=Depends(_svc)):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    codes = action.reason_codes or ([action.reason_code] if action.reason_code else None)
    result = await svc.edit(
        item_id, current_user.username,
        edited_instruction=action.edited_instruction,
        edited_response=action.edited_response,
        notes=action.notes,
        reason_codes=codes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/{item_id}/flag")
async def flag_item(item_id: str, action: ReviewAction,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
    svc=Depends(_svc)):
    item = await svc.get_item(item_id)
    _enforce_owner(item, current_user)
    result = await svc.flag(item_id, current_user.username, action.notes)
    if not result:
        raise HTTPException(status_code=404, detail="Review item not found")
    return result


@router.post("/queue/bulk")
async def bulk_action(action: BulkAction,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    svc=Depends(_svc)):
    # Copy to avoid mutating the pydantic model's dict
    filters = dict(action.filters)
    action_type = filters.pop("action", "approve")
    if action_type == "approve":
        count = await svc.bulk_approve(filters, current_user.username, action.reason)
    else:
        count = await svc.bulk_reject(filters, current_user.username, action.reason)
    return {"affected": count, "action": action_type}


@router.get("/stats")
async def review_stats(
    current_user: User = Depends(get_current_user),
    svc=Depends(_svc)):
    return await svc.get_stats()


@router.get("/signals")
async def review_signals(
    current_user: User = Depends(get_current_user),
    job_id: Optional[str] = Query(None),
    svc=Depends(_svc),
):
    """Return aggregated structured reason feedback signals for dataset stratification."""
    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    return await svc.get_feedback_signals(job_id=job_id, owner=owner_filter)


@router.get("/calibration")
async def review_calibration(
    current_user: User = Depends(get_current_user),
    job_id: Optional[str] = Query(None),
    svc=Depends(_svc),
):
    """Return reviewer calibration and inter-annotator disagreement metrics."""
    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    return await svc.get_calibration_stats(job_id=job_id, owner=owner_filter)


@router.post("/calibration/rebalance")
async def review_calibration_rebalance(
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
    job_id: Optional[str] = Query(None),
    svc=Depends(_svc),
):
    """Trigger automated continuous calibration and dynamic rubric reweighting."""
    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    return await svc.rebalance_rubrics(job_id=job_id, owner=owner_filter)


@router.post("/calibration/drift-audit")
async def review_calibration_drift_audit(
    request: Request,
    min_reviews: int = Query(5, ge=1, le=100),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
    svc=Depends(_svc),
):
    """Run an on-demand calibration drift audit and broadcast alerts if Kappa < 0.60."""
    ws_mgr = getattr(request.app.state, "ws_manager", None)
    result = await svc.check_and_auto_rebalance(min_reviews=min_reviews, ws_manager=ws_mgr)
    if result is None:
        return {
            "status": "skipped",
            "reason": f"Insufficient review samples (< {min_reviews}) for statistical calibration",
        }
    return result


@router.get("/calibration/history")
async def review_calibration_history(
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    svc=Depends(_svc),
):
    """Retrieve historical review calibration reports."""
    return await svc.get_calibration_history(limit=limit)


# ── HITL endpoints ────────────────────────────────────────────────────────────

@router.get("/paused")
async def list_paused_jobs(
    current_user: User = Depends(get_current_user),
    svc=Depends(_svc)):
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
async def hitl_job_status(job_id: str,
    current_user: User = Depends(get_current_user),
    svc=Depends(_svc)):
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
async def hitl_resume_job(job_id: str,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER])),
    svc=Depends(_svc)):
    if hasattr(svc, "db") and svc.db:
        job = await svc.db.get_job(job_id)
        if job:
            _enforce_owner(job.to_dict(), current_user, resource_name="Job")
    resumed = await svc.resume_job(job_id)
    if not resumed:
        raise HTTPException(status_code=404, detail=f"Job {job_id} is not currently paused")
    return {"status": "resumed", "job_id": job_id}
