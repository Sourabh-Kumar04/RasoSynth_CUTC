"""Tests for the review service (async, DB-backed)."""
import pytest
import pytest_asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Lightweight in-memory DB stub ─────────────────────────────────────────────

class _FakeItem:
    def __init__(self, id_, job_id, instruction, response, **kw):
        self.id = id_
        self.job_id = job_id
        self.instruction = instruction
        self.response = response
        self.dataset_id = kw.get("dataset_id", "")
        self.source_url = kw.get("source_url", "")
        self.source_text = kw.get("source_text", "")
        self.quality_score = kw.get("quality_score", 0.0)
        self.hallucination_risk = kw.get("hallucination_risk", 0.0)
        self.duplicate_score = kw.get("duplicate_score", 0.0)
        self.diversity_score = kw.get("diversity_score", 0.0)
        self.review_status = kw.get("review_status", "pending")
        self.review_decision = kw.get("review_decision", None)
        self.review_notes = kw.get("review_notes", "")
        self.reviewed_by = kw.get("reviewed_by", "")
        self.review_timestamp = kw.get("review_timestamp", None)
        self.edited_instruction = kw.get("edited_instruction", None)
        self.edited_response = kw.get("edited_response", None)
        self.review_version = kw.get("review_version", 0)
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


class _FakeDB:
    """Minimal async in-memory stub replacing DatabaseManager for tests."""

    def __init__(self):
        self._store: dict[str, _FakeItem] = {}
        self._counter = 0

    async def create_review_item(self, data: dict) -> _FakeItem:
        import uuid
        item = _FakeItem(str(uuid.uuid4()), **{k: v for k, v in data.items() if k != "id"})
        self._store[item.id] = item
        return item

    async def get_review_item(self, item_id: str):
        return self._store.get(item_id)

    async def update_review_item(self, item_id: str, **kwargs):
        item = self._store.get(item_id)
        if not item:
            return None
        for k, v in kwargs.items():
            if hasattr(item, k):
                setattr(item, k, v)
        item.updated_at = datetime.utcnow()
        return item

    async def list_review_items(self, status=None, job_id=None, page=1, page_size=50):
        items = list(self._store.values())
        if status:
            items = [i for i in items if i.review_status == status]
        if job_id:
            items = [i for i in items if i.job_id == job_id]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def review_stats(self):
        items = list(self._store.values())
        total = len(items)
        counts = {}
        for s in ("pending", "in_review", "approved", "rejected", "flagged"):
            counts[s] = sum(1 for i in items if i.review_status == s)
        return {
            "total": total,
            **counts,
            "approval_rate": round(counts["approved"] / max(total, 1) * 100, 1),
            "rejection_rate": round(counts["rejected"] / max(total, 1) * 100, 1),
        }


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def svc():
    from core.review_service import ReviewService
    db = _FakeDB()
    service = ReviewService(db)
    await service.submit("What is AI?",   "AI is artificial intelligence.", job_id="job1")
    await service.submit("What is ML?",   "ML is machine learning.",         job_id="job1")
    await service.submit("What is Py?",   "Python is a language.",           job_id="job2")
    return service


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit():
    from core.review_service import ReviewService
    db = _FakeDB()
    service = ReviewService(db)
    item = await service.submit("Test", "Response", job_id="j1", quality_score=0.8)
    assert item["instruction"] == "Test"
    assert item["review_status"] == "pending"
    assert item["quality_score"] == 0.8


@pytest.mark.asyncio
async def test_approve(svc):
    q = await svc.get_queue()
    item_id = q["items"][0]["id"]
    result = await svc.approve(item_id, "reviewer1", "Looks good")
    assert result["review_status"] == "approved"
    assert result["review_decision"] == "approve"
    assert result["reviewed_by"] == "reviewer1"
    assert result["review_version"] == 1


@pytest.mark.asyncio
async def test_reject(svc):
    q = await svc.get_queue()
    item_id = q["items"][0]["id"]
    result = await svc.reject(item_id, "reviewer1", "Not accurate")
    assert result["review_status"] == "rejected"
    assert result["review_decision"] == "reject"


@pytest.mark.asyncio
async def test_edit(svc):
    q = await svc.get_queue()
    item_id = q["items"][0]["id"]
    result = await svc.edit(
        item_id, "reviewer1",
        edited_instruction="What is Artificial Intelligence?",
        edited_response="AI is artificial intelligence.",
        notes="Improved wording",
    )
    assert result["review_status"] == "approved"
    assert result["review_decision"] == "edit"
    assert result["edited_instruction"] == "What is Artificial Intelligence?"


@pytest.mark.asyncio
async def test_flag(svc):
    q = await svc.get_queue()
    item_id = q["items"][0]["id"]
    result = await svc.flag(item_id, "reviewer1", "Needs fact-check")
    assert result["review_status"] == "flagged"


@pytest.mark.asyncio
async def test_get_queue_filtered(svc):
    all_q = await svc.get_queue()
    assert all_q["total"] == 3

    j1 = await svc.get_queue(job_id="job1")
    assert j1["total"] == 2

    j2 = await svc.get_queue(job_id="job2")
    assert j2["total"] == 1


@pytest.mark.asyncio
async def test_get_queue_pagination(svc):
    p1 = await svc.get_queue(page=1, page_size=2)
    assert len(p1["items"]) == 2
    assert p1["total"] == 3
    assert p1["total_pages"] == 2

    p2 = await svc.get_queue(page=2, page_size=2)
    assert len(p2["items"]) == 1


@pytest.mark.asyncio
async def test_get_stats(svc):
    stats = await svc.get_stats()
    assert stats["total"] == 3
    assert stats["pending"] == 3
    assert stats["approved"] == 0


@pytest.mark.asyncio
async def test_bulk_approve(svc):
    count = await svc.bulk_approve({"job_id": "job1"}, "reviewer1", "Bulk")
    assert count == 2
    stats = await svc.get_stats()
    assert stats["approved"] == 2


@pytest.mark.asyncio
async def test_bulk_reject(svc):
    count = await svc.bulk_reject({}, "reviewer1", "Bulk reject")
    assert count == 3
    stats = await svc.get_stats()
    assert stats["rejected"] == 3


@pytest.mark.asyncio
async def test_hitl_pause_resume(svc):
    import asyncio
    event = await svc.pause_job_for_review("job99")
    assert svc.is_job_paused("job99")
    assert "job99" in svc.get_paused_jobs()

    resumed = await svc.resume_job("job99")
    assert resumed is True
    assert not svc.is_job_paused("job99")
    assert event.is_set()


@pytest.mark.asyncio
async def test_resume_nonexistent(svc):
    result = await svc.resume_job("nonexistent-job")
    assert result is False
