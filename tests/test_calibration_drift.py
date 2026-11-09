"""
Test Automated Review Calibration Daemon & Drift Alert Notifications.
"""

import pytest
from core.review_service import ReviewService


class MockItem:
    def __init__(self, id, llm_decision, human_decision, quality=0.8):
        self.id = id
        self.quality_score = quality
        self.instruction = "Test Instruction"
        self.response = "Test Response"
        self.review_version = 1
        self.reviews = [
            {"reviewer": "llm_judge", "decision": llm_decision, "codes": []},
            {"reviewer": "human_reviewer", "decision": human_decision, "codes": []},
        ]
        self.extra_metadata = {"reviews": self.reviews}
        self.review_decision = human_decision

    def to_dict(self):
        return {
            "id": self.id,
            "quality_score": self.quality_score,
            "instruction": self.instruction,
            "response": self.response,
            "reviews": self.reviews,
            "metadata": self.extra_metadata,
            "review_decision": self.review_decision,
        }


class MockDBManager:
    def __init__(self, items):
        self.items = items
        self.saved_reports = []

    async def list_review_items(self, status=None, job_id=None, page=1, page_size=100, owner=None):
        return self.items, len(self.items)

    async def create_review_calibration_report(self, stats):
        report = {"id": f"report-{len(self.saved_reports)+1}", **stats}
        self.saved_reports.append(report)
        return report

    async def list_calibration_reports(self, limit=50):
        return self.saved_reports


class MockWSManager:
    def __init__(self):
        self.broadcasts = []

    async def broadcast(self, message):
        self.broadcasts.append(message)


@pytest.mark.asyncio
async def test_calibration_drift_detection_and_alert():
    # Construct heavy disagreement: LLM approves, Humans reject -> Cohen's Kappa < 0
    items = []
    for i in range(20):
        llm_dec = "approve" if i % 2 == 0 else "reject"
        human_dec = "reject" if i % 2 == 0 else "approve"
        items.append(MockItem(f"item-{i}", llm_dec, human_dec))

    db = MockDBManager(items)
    ws = MockWSManager()
    svc = ReviewService(db=db, ws_manager=ws)

    result = await svc.check_and_auto_rebalance(min_reviews=10, ws_manager=ws)
    assert result is not None
    assert result["drift_detected"] is True
    assert result["drift_severity"] in ("warning", "critical")
    assert result["calibration"]["cohens_kappa"] < 0.60

    # Ensure WebSocket alert was broadcast
    assert len(ws.broadcasts) >= 1
    alert = ws.broadcasts[0]
    assert alert["type"] == "calibration_drift_alert"
    assert "kappa" in alert["data"]
    assert alert["data"]["kappa"] < 0.60


@pytest.mark.asyncio
async def test_calibration_normal_agreement():
    # Construct high agreement: LLM and Humans agree 90%
    items = []
    for i in range(20):
        dec = "approve" if i < 18 else "reject"
        items.append(MockItem(f"item-{i}", dec, dec))

    db = MockDBManager(items)
    ws = MockWSManager()
    svc = ReviewService(db=db, ws_manager=ws)

    result = await svc.check_and_auto_rebalance(min_reviews=10, ws_manager=ws)
    assert result is not None
    assert result["drift_detected"] is False
    assert result["drift_severity"] == "normal"
    assert result["calibration"]["cohens_kappa"] >= 0.60

    # No drift alert broadcast
    assert len(ws.broadcasts) == 0
