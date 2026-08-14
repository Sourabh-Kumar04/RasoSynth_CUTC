"""
Human Review Service — manages review queue, approvals, rejections, edits.
In-memory implementation for now, designed for easy DB backend swap.
"""
import uuid
from datetime import datetime
from typing import Optional
from enum import Enum


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"
    IN_REVIEW = "in_review"


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class ReviewQueueItem:
    """In-memory review queue item representation."""

    def __init__(
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
    ):
        self.id = str(uuid.uuid4())
        self.job_id = job_id
        self.dataset_id = dataset_id
        self.instruction = instruction
        self.response = response
        self.source_url = source_url
        self.source_text = source_text
        self.quality_score = quality_score
        self.hallucination_risk = hallucination_risk
        self.duplicate_score = duplicate_score
        self.diversity_score = diversity_score

        self.review_status = ReviewStatus.PENDING
        self.review_decision: Optional[str] = None
        self.review_notes = ""
        self.reviewed_by = ""
        self.review_timestamp: Optional[datetime] = None
        self.edited_instruction: Optional[str] = None
        self.edited_response: Optional[str] = None
        self.review_version = 0

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "dataset_id": self.dataset_id,
            "instruction": self.instruction,
            "response": self.response,
            "source_url": self.source_url,
            "source_text": self.source_text[:200] if self.source_text else "",
            "quality_score": self.quality_score,
            "hallucination_risk": self.hallucination_risk,
            "duplicate_score": self.duplicate_score,
            "diversity_score": self.diversity_score,
            "review_status": self.review_status.value if isinstance(self.review_status, Enum) else self.review_status,
            "review_decision": self.review_decision,
            "review_notes": self.review_notes,
            "reviewed_by": self.reviewed_by,
            "review_timestamp": self.review_timestamp.isoformat() if self.review_timestamp else None,
            "edited_instruction": self.edited_instruction,
            "edited_response": self.edited_response,
            "review_version": self.review_version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ReviewService:
    """Manages the human review queue."""

    def __init__(self):
        self._items: dict[str, ReviewQueueItem] = {}

    def submit(
        self,
        instruction: str,
        response: str,
        job_id: str,
        **kwargs,
    ) -> ReviewQueueItem:
        item = ReviewQueueItem(instruction, response, job_id, **kwargs)
        self._items[item.id] = item
        return item

    def approve(self, item_id: str, reviewer: str, notes: str = "") -> Optional[dict]:
        item = self._items.get(item_id)
        if not item:
            return None
        item.review_status = ReviewStatus.APPROVED
        item.review_decision = ReviewDecision.APPROVE
        item.review_notes = notes
        item.reviewed_by = reviewer
        item.review_timestamp = datetime.utcnow()
        item.review_version += 1
        item.updated_at = datetime.utcnow()
        return item.to_dict()

    def reject(self, item_id: str, reviewer: str, reason: str = "") -> Optional[dict]:
        item = self._items.get(item_id)
        if not item:
            return None
        item.review_status = ReviewStatus.REJECTED
        item.review_decision = ReviewDecision.REJECT
        item.review_notes = reason
        item.reviewed_by = reviewer
        item.review_timestamp = datetime.utcnow()
        item.review_version += 1
        item.updated_at = datetime.utcnow()
        return item.to_dict()

    def edit(
        self,
        item_id: str,
        reviewer: str,
        edited_instruction: str = None,
        edited_response: str = None,
        notes: str = "",
    ) -> Optional[dict]:
        item = self._items.get(item_id)
        if not item:
            return None
        item.edited_instruction = edited_instruction or item.instruction
        item.edited_response = edited_response or item.response
        item.review_status = ReviewStatus.APPROVED
        item.review_decision = ReviewDecision.EDIT
        item.review_notes = notes
        item.reviewed_by = reviewer
        item.review_timestamp = datetime.utcnow()
        item.review_version += 1
        item.updated_at = datetime.utcnow()
        return item.to_dict()

    def get_queue(
        self,
        status: str = None,
        job_id: str = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        items = list(self._items.values())
        if status:
            items = [i for i in items if i.review_status.value == status or i.review_status == status]
        if job_id:
            items = [i for i in items if i.job_id == job_id]

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        return {
            "items": [i.to_dict() for i in page_items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
        }

    def get_item(self, item_id: str) -> Optional[dict]:
        item = self._items.get(item_id)
        return item.to_dict() if item else None

    def get_stats(self) -> dict:
        total = len(self._items)
        pending = sum(1 for i in self._items.values() if i.review_status == ReviewStatus.PENDING)
        approved = sum(1 for i in self._items.values() if i.review_status == ReviewStatus.APPROVED)
        rejected = sum(1 for i in self._items.values() if i.review_status == ReviewStatus.REJECTED)
        flagged = sum(1 for i in self._items.values() if i.review_status == ReviewStatus.FLAGGED)
        in_review = sum(1 for i in self._items.values() if i.review_status == ReviewStatus.IN_REVIEW)
        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "flagged": flagged,
            "in_review": in_review,
            "approval_rate": round(approved / max(total, 1) * 100, 1),
            "rejection_rate": round(rejected / max(total, 1) * 100, 1),
        }

    def bulk_approve(self, filters: dict, reviewer: str, reason: str = "") -> int:
        items = self._get_filtered(filters)
        count = 0
        for item in items:
            self.approve(item.id, reviewer, reason)
            count += 1
        return count

    def bulk_reject(self, filters: dict, reviewer: str, reason: str = "") -> int:
        items = self._get_filtered(filters)
        count = 0
        for item in items:
            self.reject(item.id, reviewer, reason)
            count += 1
        return count

    def _get_filtered(self, filters: dict) -> list[ReviewQueueItem]:
        items = list(self._items.values())
        if filters.get("status"):
            items = [i for i in items if i.review_status.value == filters["status"]]
        if filters.get("job_id"):
            items = [i for i in items if i.job_id == filters["job_id"]]
        if filters.get("quality_min"):
            items = [i for i in items if i.quality_score >= filters["quality_min"]]
        if filters.get("quality_max"):
            items = [i for i in items if i.quality_score <= filters["quality_max"]]
        if filters.get("hallucination_max"):
            items = [i for i in items if i.hallucination_risk <= filters["hallucination_max"]]
        return items