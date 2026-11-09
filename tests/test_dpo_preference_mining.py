"""
Unit tests for DPO/ORPO Preference Dataset Mining & Active Learning Review Prioritization.
"""

import pytest
from core.review_service import ReviewService


class MockReviewItem:
    def __init__(self, id, instruction, orig_resp, edited_resp, status="approved", quality=0.72):
        self.id = id
        self.instruction = instruction
        self.response = orig_resp
        self.edited_instruction = instruction
        self.edited_response = edited_resp
        self.status = status
        self.quality_score = quality
        self.metadata = {"reason_codes": ["factual_hallucination"] if edited_resp != orig_resp else []}

    def to_dict(self):
        return {
            "id": self.id,
            "instruction": self.instruction,
            "response": self.response,
            "edited_instruction": self.edited_instruction,
            "edited_response": self.edited_response,
            "status": self.status,
            "quality_score": self.quality_score,
            "metadata": self.metadata,
        }


class MockDBManager:
    def __init__(self, items):
        self.items = items

    async def list_review_items(self, status=None, job_id=None, page=1, page_size=100, owner=None):
        filtered = self.items
        if status:
            filtered = [i for i in filtered if i.status == status]
        start = (page - 1) * page_size
        return filtered[start : start + page_size], len(filtered)


@pytest.mark.asyncio
async def test_dpo_preference_mining_from_edits():
    items = [
        # Item 1: edited by human (yields a DPO pair)
        MockReviewItem("item-1", "Explain quantum tunneling", "It is magic", "It is a quantum mechanical phenomenon"),
        # Item 2: approved unchanged (does NOT yield a DPO pair)
        MockReviewItem("item-2", "What is 2+2?", "4", "4"),
        # Item 3: edited by human (yields a second DPO pair)
        MockReviewItem("item-3", "Capital of France", "Berlin", "Paris"),
    ]

    db = MockDBManager(items)
    svc = ReviewService(db=db)

    pairs = await svc.export_dpo_pairs()
    assert len(pairs) == 2
    assert pairs[0]["prompt"] == "Explain quantum tunneling"
    assert pairs[0]["chosen"] == "It is a quantum mechanical phenomenon"
    assert pairs[0]["rejected"] == "It is magic"
    assert pairs[0]["source_review_id"] == "item-1"

    assert pairs[1]["prompt"] == "Capital of France"
    assert pairs[1]["chosen"] == "Paris"
    assert pairs[1]["rejected"] == "Berlin"


@pytest.mark.asyncio
async def test_uncertainty_driven_queue_prioritization():
    # Construct items with varying quality scores
    items = [
        MockReviewItem("item-high", "High quality prompt", "Resp", "Resp", status="pending", quality=0.98), # Far from 0.70 boundary
        MockReviewItem("item-borderline", "Borderline prompt", "Resp", "Resp", status="pending", quality=0.71), # Very close to 0.70 boundary (max uncertainty)
        MockReviewItem("item-low", "Low quality prompt", "Resp", "Resp", status="pending", quality=0.20), # Far from 0.70 boundary
    ]

    db = MockDBManager(items)
    svc = ReviewService(db=db)

    # Prioritize with active learning uncertainty strategy
    prioritized, total = await svc.get_prioritized_queue(strategy="uncertainty", status="pending")
    assert total == 3
    # The borderline item (0.71) should be ranked first!
    assert prioritized[0]["id"] == "item-borderline"
    assert prioritized[0]["uncertainty_score"] > prioritized[1]["uncertainty_score"]
