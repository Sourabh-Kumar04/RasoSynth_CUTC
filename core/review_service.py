"""
Human Review Service — async, DB-backed.

Improvements over v1:
- _bump_version inlined into update call (one round-trip instead of two)
- get_paused_jobs() exposes currently-blocked dataset jobs
- export_approved() streams approved items as JSONL for fine-tuning
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from core.db import DatabaseManager, ReviewQueueItem

logger = logging.getLogger(__name__)


class ReviewService:
    """
    Async review service backed by DatabaseManager.
    One instance stored on app.state.review_service.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        # job_id -> asyncio.Event (set when reviewer calls resume_job)
        self._resume_events: dict[str, asyncio.Event] = {}

    # ── Submit / query ────────────────────────────────────────────────────────

    async def submit(
        self,
        instruction: str,
        response: str,
        job_id: str,
        dataset_id: str = "",
        source_url: str = "",
        source_text: str = "",
        quality_score: float = 0.0,
        hallucination_risk: float = 0.0,
        duplicate_score: float = 0.0,
        diversity_score: float = 0.0,
    ) -> dict:
        item = await self.db.create_review_item(dict(
            job_id=job_id,
            dataset_id=dataset_id,
            instruction=instruction,
            response=response,
            source_url=source_url,
            source_text=source_text,
            quality_score=quality_score,
            hallucination_risk=hallucination_risk,
            duplicate_score=duplicate_score,
            diversity_score=diversity_score,
            review_status="pending",
        ))
        return item.to_dict()

    async def get_item(self, item_id: str) -> Optional[dict]:
        item = await self.db.get_review_item(item_id)
        return item.to_dict() if item else None

    async def get_queue(
        self,
        status: Optional[str] = None,
        job_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        items, total = await self.db.list_review_items(
            status=status, job_id=job_id, page=page, page_size=page_size
        )
        return {
            "items": [i.to_dict() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
        }

    # ── Review actions ────────────────────────────────────────────────────────

    async def approve(self, item_id: str, reviewer: str, notes: str = "") -> Optional[dict]:
        existing = await self.db.get_review_item(item_id)
        if not existing:
            return None
        item = await self.db.update_review_item(
            item_id,
            review_status="approved",
            review_decision="approve",
            review_notes=notes,
            reviewed_by=reviewer,
            review_timestamp=datetime.utcnow(),
            review_version=(existing.review_version or 0) + 1,
        )
        return item.to_dict() if item else None

    async def reject(self, item_id: str, reviewer: str, reason: str = "") -> Optional[dict]:
        existing = await self.db.get_review_item(item_id)
        if not existing:
            return None
        item = await self.db.update_review_item(
            item_id,
            review_status="rejected",
            review_decision="reject",
            review_notes=reason,
            reviewed_by=reviewer,
            review_timestamp=datetime.utcnow(),
            review_version=(existing.review_version or 0) + 1,
        )
        return item.to_dict() if item else None

    async def edit(
        self,
        item_id: str,
        reviewer: str,
        edited_instruction: Optional[str] = None,
        edited_response: Optional[str] = None,
        notes: str = "",
    ) -> Optional[dict]:
        existing = await self.db.get_review_item(item_id)
        if not existing:
            return None
        item = await self.db.update_review_item(
            item_id,
            edited_instruction=edited_instruction or existing.instruction,
            edited_response=edited_response or existing.response,
            review_status="approved",
            review_decision="edit",
            review_notes=notes,
            reviewed_by=reviewer,
            review_timestamp=datetime.utcnow(),
            review_version=(existing.review_version or 0) + 1,
        )
        return item.to_dict() if item else None

    async def flag(self, item_id: str, reviewer: str, reason: str = "") -> Optional[dict]:
        existing = await self.db.get_review_item(item_id)
        if not existing:
            return None
        item = await self.db.update_review_item(
            item_id,
            review_status="flagged",
            review_notes=reason,
            reviewed_by=reviewer,
            review_timestamp=datetime.utcnow(),
            review_version=(existing.review_version or 0) + 1,
        )
        return item.to_dict() if item else None

    # ── Bulk operations ───────────────────────────────────────────────────────

    async def bulk_approve(self, filters: dict, reviewer: str, reason: str = "") -> int:
        items, _ = await self.db.list_review_items(
            status=filters.get("status"),
            job_id=filters.get("job_id"),
            page=1, page_size=10000,
        )
        count = 0
        for item in items:
            if filters.get("quality_min") and (item.quality_score or 0) < filters["quality_min"]:
                continue
            await self.approve(item.id, reviewer, reason)
            count += 1
        return count

    async def bulk_reject(self, filters: dict, reviewer: str, reason: str = "") -> int:
        items, _ = await self.db.list_review_items(
            status=filters.get("status"),
            job_id=filters.get("job_id"),
            page=1, page_size=10000,
        )
        count = 0
        for item in items:
            await self.reject(item.id, reviewer, reason)
            count += 1
        return count

    # ── Stats & export ────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        return await self.db.review_stats()

    async def export_approved(self, job_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Yield JSONL lines of all approved items (optionally filtered by job)."""
        import json
        page = 1
        while True:
            items, total = await self.db.list_review_items(
                status="approved", job_id=job_id, page=page, page_size=500
            )
            for item in items:
                d = item.to_dict()
                # Use edited text if available, else original
                yield json.dumps({
                    "instruction": d.get("edited_instruction") or d["instruction"],
                    "response": d.get("edited_response") or d["response"],
                    "input": "",
                    "source_review_id": d["id"],
                    "job_id": d["job_id"],
                    "quality_score": d["quality_score"],
                }) + "\n"
            if page * 500 >= total:
                break
            page += 1

    # ── HITL pause / resume ───────────────────────────────────────────────────

    async def pause_job_for_review(self, job_id: str) -> asyncio.Event:
        """Returns an Event that will be set when resume_job() is called."""
        event = asyncio.Event()
        self._resume_events[job_id] = event
        logger.info("Job %s paused at HITL gate", job_id)
        return event

    async def resume_job(self, job_id: str) -> bool:
        event = self._resume_events.pop(job_id, None)
        if event is not None:
            event.set()
            logger.info("Job %s resumed", job_id)
            return True
        logger.warning("resume_job: job %s was not paused", job_id)
        return False

    def is_job_paused(self, job_id: str) -> bool:
        return job_id in self._resume_events

    def get_paused_jobs(self) -> list[str]:
        """Return list of job_ids currently paused at the HITL gate."""
        return list(self._resume_events.keys())
