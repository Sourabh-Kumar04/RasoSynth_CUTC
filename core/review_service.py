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
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from core.db import DatabaseManager, ReviewQueueItem
from core.review_reasons import ReviewCalibrationTracker, normalize_reason_codes

logger = logging.getLogger(__name__)


class ReviewService:
    """
    Async review service backed by DatabaseManager.
    One instance stored on app.state.review_service.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        db: Optional[DatabaseManager] = None,
        ws_manager: Any = None,
    ):
        manager = db_manager or db
        if manager is None:
            raise ValueError("db_manager must be provided to ReviewService")
        self.db = manager
        self.ws_manager = ws_manager
        # job_id -> asyncio.Event (set when reviewer calls resume_job)
        self._resume_events: dict[str, asyncio.Event] = {}
        self._reviews_since_rebalance: int = 0

    async def recover_paused_jobs(self) -> int:
        """
        Called once at startup.

        Scans the jobs table for any rows with status='awaiting_review'
        that were left there by a previous server run, and recreates their
        asyncio.Event so the pipeline can be resumed via the API.

        Returns the number of jobs recovered.
        """
        from sqlalchemy import select
        from core.db import Job as JobModel

        recovered = 0
        try:
            async with self.db.session_maker() as session:
                result = await session.execute(
                    select(JobModel).where(JobModel.status == "awaiting_review")
                )
                jobs = result.scalars().all()
                for job in jobs:
                    if job.id not in self._resume_events:
                        event = asyncio.Event()
                        self._resume_events[job.id] = event
                        recovered += 1
                        logger.info(
                            "ReviewService: restored awaiting_review event for job %s", job.id
                        )
        except Exception as e:
            logger.warning("ReviewService: failed to recover paused jobs: %s", e)

        return recovered

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
        metadata: Optional[dict] = None,
        owner: Optional[str] = None,
    ) -> dict:
        if dataset_id and hasattr(self.db, "get_review_item_for_job_sample"):
            existing = await self.db.get_review_item_for_job_sample(job_id, dataset_id)
            if existing is not None:
                return existing.to_dict()

        resolved_owner = owner or (metadata or {}).get("owner")
        if not resolved_owner and job_id and self.db:
            try:
                j = await self.db.get_job(job_id)
                if j and getattr(j, "owner", None):
                    resolved_owner = j.owner
            except Exception:
                pass

        item = await self.db.create_review_item(dict(
            job_id=job_id,
            dataset_id=dataset_id,
            owner=resolved_owner,
            instruction=instruction,
            response=response,
            source_url=source_url,
            source_text=source_text,
            quality_score=quality_score,
            hallucination_risk=hallucination_risk,
            duplicate_score=duplicate_score,
            diversity_score=diversity_score,
            extra_metadata=metadata or {},
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
        owner: Optional[str] = None,
    ) -> dict:
        items, total = await self.db.list_review_items(
            status=status, job_id=job_id, page=page, page_size=page_size, owner=owner
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
            review_timestamp=datetime.now(timezone.utc),
            review_version=(existing.review_version or 0) + 1,
        )
        self._record_review_activity()
        return item.to_dict() if item else None

    async def reject(
        self,
        item_id: str,
        reviewer: str,
        reason: str = "",
        reason_codes: Optional[list[str] | str] = None,
    ) -> Optional[dict]:
        existing = await self.db.get_review_item(item_id)
        if not existing:
            return None
        
        normalized_codes = normalize_reason_codes(reason_codes, notes=reason)
        raw_meta = getattr(existing, "extra_metadata", None) or getattr(existing, "metadata", None) or {}
        meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
        meta["reason_codes"] = normalized_codes
        meta["primary_reason_code"] = normalized_codes[0] if normalized_codes else "other"

        item = await self.db.update_review_item(
            item_id,
            review_status="rejected",
            review_decision="reject",
            review_notes=reason,
            reviewed_by=reviewer,
            review_timestamp=datetime.now(timezone.utc),
            review_version=(existing.review_version or 0) + 1,
            extra_metadata=meta,
        )
        self._record_review_activity()
        return item.to_dict() if item else None

    async def edit(
        self,
        item_id: str,
        reviewer: str,
        edited_instruction: Optional[str] = None,
        edited_response: Optional[str] = None,
        notes: str = "",
        reason_codes: Optional[list[str] | str] = None,
    ) -> Optional[dict]:
        existing = await self.db.get_review_item(item_id)
        if not existing:
            return None

        normalized_codes = normalize_reason_codes(reason_codes, notes=notes)
        raw_meta = getattr(existing, "extra_metadata", None) or getattr(existing, "metadata", None) or {}
        meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
        meta["reason_codes"] = normalized_codes
        meta["primary_reason_code"] = normalized_codes[0] if normalized_codes else "other"

        item = await self.db.update_review_item(
            item_id,
            edited_instruction=edited_instruction or existing.instruction,
            edited_response=edited_response or existing.response,
            review_status="approved",
            review_decision="edit",
            review_notes=notes,
            reviewed_by=reviewer,
            review_timestamp=datetime.now(timezone.utc),
            review_version=(existing.review_version or 0) + 1,
            extra_metadata=meta,
        )
        self._record_review_activity()
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
            review_timestamp=datetime.now(timezone.utc),
            review_version=(existing.review_version or 0) + 1,
        )
        self._record_review_activity()
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

    async def get_feedback_signals(self, job_id: Optional[str] = None, owner: Optional[str] = None) -> dict:
        """Aggregate structured review reason signals for pipeline feedback."""
        items, _ = await self.db.list_review_items(job_id=job_id, page=1, page_size=10000, owner=owner)
        dict_items = [i.to_dict() for i in items]
        return ReviewCalibrationTracker.compute_feedback_signals(dict_items)

    async def get_calibration_stats(self, job_id: Optional[str] = None, owner: Optional[str] = None) -> dict:
        """Compute reviewer calibration / disagreement metrics across reviews."""
        items, _ = await self.db.list_review_items(job_id=job_id, page=1, page_size=10000, owner=owner)
        dict_items = [i.to_dict() for i in items]
        return ReviewCalibrationTracker.compute_inter_annotator_calibration(dict_items)

    async def rebalance_rubrics(self, job_id: Optional[str] = None, owner: Optional[str] = None) -> dict:
        """Calculate latest calibration metrics, dynamically rebalance rubric weights, and persist report."""
        stats = await self.get_calibration_stats(job_id=job_id, owner=owner)
        report_record = await self.db.create_review_calibration_report(stats)
        report_id = report_record.get("id") if isinstance(report_record, dict) else getattr(report_record, "id", None)
        return {
            "report_id": report_id,
            "calibration": stats,
            "rebalanced_rubrics": stats.get("rubric_weights", {}),
            "status": "rebalanced",
        }

    async def check_and_auto_rebalance(self, min_reviews: int = 10, ws_manager: Any = None) -> Optional[dict]:
        """
        Evaluate reviewer calibration, detect LLM judge drift, dynamically
        rebalance rubrics, and broadcast drift warnings if Cohen's Kappa < 0.60.
        """
        stats = await self.get_calibration_stats()
        evaluated_count = stats.get("evaluated_pairs", 0) or stats.get("multi_reviewed_count", 0)
        if evaluated_count < min_reviews:
            return None

        result = await self.rebalance_rubrics()
        kappa = stats.get("cohens_kappa")
        drift_detected = kappa is not None and kappa < 0.60

        result["drift_detected"] = drift_detected
        result["drift_severity"] = (
            "critical" if (kappa is not None and kappa < 0.40)
            else "warning" if drift_detected
            else "normal"
        )

        mgr = ws_manager or self.ws_manager
        if drift_detected and kappa is not None:
            logger.warning(
                f"LLM Judge Calibration Drift Detected: Cohen's Kappa κ={kappa:.3f} (< 0.60). "
                f"Dynamic rubrics reweighted: {result.get('rebalanced_rubrics')}"
            )
            if mgr and hasattr(mgr, "broadcast"):
                try:
                    await mgr.broadcast({
                        "type": "calibration_drift_alert",
                        "data": {
                            "kappa": kappa,
                            "agreement_rate": stats.get("decision_agreement_pct"),
                            "severity": result["drift_severity"],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "rubric_weights": result.get("rebalanced_rubrics"),
                        }
                    })
                except Exception as ws_err:
                    logger.debug(f"Failed to broadcast drift alert: {ws_err}")

        return result

    def _record_review_activity(self):
        """Track reviews and trigger periodic auto-rebalance."""
        self._reviews_since_rebalance += 1
        if self._reviews_since_rebalance >= 20:
            self._reviews_since_rebalance = 0
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.check_and_auto_rebalance())
            except Exception:
                pass

    async def get_calibration_history(self, limit: int = 50) -> list[dict]:
        """Fetch past persisted calibration reports."""
        if hasattr(self.db, "list_calibration_reports"):
            records = await self.db.list_calibration_reports(limit=limit)
            return [r.to_dict() if hasattr(r, "to_dict") else r for r in records]
        return []

    async def export_approved(self, job_id: Optional[str] = None, owner: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Yield JSONL lines of all approved items (optionally filtered by job/owner)."""
        import json
        page = 1
        while True:
            items, total = await self.db.list_review_items(
                status="approved", job_id=job_id, page=page, page_size=500, owner=owner
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

    async def export_dpo_pairs(self, job_id: Optional[str] = None, owner: Optional[str] = None) -> list[dict]:
        """
        Extract pairwise preference records for DPO/ORPO training from human review edits.
        The human-edited text is 'chosen'; the original LLM generation is 'rejected'.
        """
        pairs = []
        page = 1
        while True:
            items, total = await self.db.list_review_items(
                job_id=job_id, page=page, page_size=500, owner=owner
            )
            for item in items:
                d = item.to_dict()
                edited_resp = d.get("edited_response")
                orig_resp = d.get("response")
                if edited_resp and orig_resp and edited_resp.strip() != orig_resp.strip():
                    pairs.append({
                        "prompt": d.get("edited_instruction") or d.get("instruction") or "",
                        "chosen": edited_resp.strip(),
                        "rejected": orig_resp.strip(),
                        "source_review_id": d["id"],
                        "job_id": d.get("job_id"),
                        "quality_score": d.get("quality_score"),
                    })
            if page * 500 >= total or not items:
                break
            page += 1
        return pairs

    async def get_prioritized_queue(
        self,
        strategy: str = "fifo",
        status: str = "pending",
        job_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        owner: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """
        Retrieve review queue sorted by strategy:
        - fifo: order by creation timestamp ascending
        - uncertainty: active learning entropy/uncertainty sampling
        - quality_asc: lowest quality first
        - quality_desc: highest quality first
        """
        fetch_size = 1000 if strategy in ("uncertainty", "entropy") else page_size
        items, total = await self.db.list_review_items(
            status=status,
            job_id=job_id,
            page=1 if strategy in ("uncertainty", "entropy") else page,
            page_size=fetch_size,
            owner=owner,
        )
        dict_items = [i.to_dict() for i in items]

        if strategy in ("uncertainty", "entropy"):
            for it in dict_items:
                q = it.get("quality_score") or 0.70
                distance_to_boundary = abs(q - 0.70)
                uncertainty = max(0.0, 1.0 - (distance_to_boundary * 2.5))
                meta = it.get("metadata") or {}
                if meta.get("reason_codes"):
                    uncertainty = min(1.0, uncertainty + 0.15)
                it["uncertainty_score"] = round(uncertainty, 4)

            dict_items.sort(key=lambda x: x.get("uncertainty_score", 0.0), reverse=True)
            start = (page - 1) * page_size
            dict_items = dict_items[start : start + page_size]
        elif strategy == "quality_asc":
            dict_items.sort(key=lambda x: x.get("quality_score", 0.0))
        elif strategy == "quality_desc":
            dict_items.sort(key=lambda x: x.get("quality_score", 0.0), reverse=True)

        return dict_items, total

    # ── HITL pause / resume ───────────────────────────────────────────────────

    async def pause_job_for_review(self, job_id: str) -> asyncio.Event:
        """Returns an Event that will be set when resume_job() is called."""
        event = asyncio.Event()
        self._resume_events[job_id] = event
        logger.info("Job %s paused at HITL gate", job_id)
        return event

    async def resume_job(self, job_id: str) -> bool:
        event = self._resume_events.pop(job_id, None)
        resumed = False
        if event is not None:
            event.set()
            resumed = True
        if self.db:
            try:
                job = await self.db.get_job(job_id)
                if job and job.status == "awaiting_review":
                    await self.db.update_job(job_id, status="running")
                    resumed = True
            except Exception:
                pass
        if resumed:
            logger.info("Job %s resumed", job_id)
            return True
        logger.warning("resume_job: job %s was not paused", job_id)
        return False

    def is_job_paused(self, job_id: str) -> bool:
        return job_id in self._resume_events

    def get_paused_jobs(self) -> list[str]:
        """Return list of job_ids currently paused at the HITL gate."""
        return list(self._resume_events.keys())
