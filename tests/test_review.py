"""Tests for the review system."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.review_service import ReviewService, ReviewStatus, ReviewDecision, ReviewQueueItem


@pytest.fixture
def review_service():
    svc = ReviewService()
    svc.submit("What is AI?", "AI is artificial intelligence.", job_id="job1")
    svc.submit("What is ML?", "ML is machine learning.", job_id="job1")
    svc.submit("What is Python?", "Python is a language.", job_id="job2")
    return svc


def test_submit():
    svc = ReviewService()
    item = svc.submit("Test instruction", "Test response", job_id="test_job")
    assert item is not None
    assert item.instruction == "Test instruction"
    assert item.response == "Test response"
    assert item.job_id == "test_job"
    assert item.review_status == ReviewStatus.PENDING


def test_approve(review_service):
    items = review_service.get_queue()
    item_id = items["items"][0]["id"]

    result = review_service.approve(item_id, "reviewer1", "Looks good")
    assert result is not None
    assert result["review_status"] == "approved"
    assert result["review_decision"] == "approve"
    assert result["reviewed_by"] == "reviewer1"


def test_reject(review_service):
    items = review_service.get_queue()
    item_id = items["items"][0]["id"]

    result = review_service.reject(item_id, "reviewer1", "Not accurate")
    assert result is not None
    assert result["review_status"] == "rejected"
    assert result["review_decision"] == "reject"


def test_edit(review_service):
    items = review_service.get_queue()
    item_id = items["items"][0]["id"]

    result = review_service.edit(item_id, "reviewer1",
                                  edited_instruction="What is Artificial Intelligence?",
                                  edited_response="AI is artificial intelligence.",
                                  notes="Improved wording")
    assert result is not None
    assert result["review_status"] == "approved"
    assert result["review_decision"] == "edit"
    assert result["edited_instruction"] == "What is Artificial Intelligence?"


def test_get_queue_filtered(review_service):
    all_items = review_service.get_queue()
    assert all_items["total"] == 3

    job1_items = review_service.get_queue(job_id="job1")
    assert job1_items["total"] == 2

    job2_items = review_service.get_queue(job_id="job2")
    assert job2_items["total"] == 1


def test_get_queue_pagination(review_service):
    page1 = review_service.get_queue(page=1, page_size=2)
    assert len(page1["items"]) == 2
    assert page1["total"] == 3

    page2 = review_service.get_queue(page=2, page_size=2)
    assert len(page2["items"]) == 1


def test_get_item(review_service):
    items = review_service.get_queue()
    item_id = items["items"][0]["id"]

    item = review_service.get_item(item_id)
    assert item is not None
    assert item["id"] == item_id

    missing = review_service.get_item("nonexistent")
    assert missing is None


def test_get_stats(review_service):
    stats = review_service.get_stats()
    assert stats["total"] == 3
    assert stats["pending"] == 3
    assert stats["approved"] == 0
    assert stats["rejected"] == 0


def test_bulk_approve(review_service):
    filters = {"job_id": "job1"}
    count = review_service.bulk_approve(filters, "reviewer1", "Bulk approval")
    assert count == 2

    stats = review_service.get_stats()
    assert stats["approved"] == 2


def test_bulk_reject(review_service):
    filters = {"status": "pending"}
    count = review_service.bulk_reject(filters, "reviewer1", "Bulk rejection")
    assert count == 3

    stats = review_service.get_stats()
    assert stats["rejected"] == 3