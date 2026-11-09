"""Unit tests for Continuous Calibration & Feedback Loop for LLM Judge."""
import pytest
from core.review_reasons import ReviewCalibrationTracker, ReviewReasonCode
from core.db import DatabaseManager
from core.review_service import ReviewService

def test_cohens_kappa_perfect_agreement():
    multi_reviews = [
        {
            "id": "1",
            "reviews": [
                {"reviewer": "alice", "decision": "approve", "codes": []},
                {"reviewer": "bob", "decision": "approve", "codes": []},
            ],
        },
        {
            "id": "2",
            "reviews": [
                {"reviewer": "alice", "decision": "reject", "codes": [ReviewReasonCode.FACTUAL_HALLUCINATION.value]},
                {"reviewer": "bob", "decision": "reject", "codes": [ReviewReasonCode.FACTUAL_HALLUCINATION.value]},
            ],
        },
    ]

    stats = ReviewCalibrationTracker.compute_inter_annotator_calibration(multi_reviews)
    assert stats["decision_agreement_pct"] == 100.0
    assert stats["cohens_kappa"] == 1.0
    assert stats["calibration_verdict"] == "well_calibrated"
    assert stats["recommended_arbitration_rate"] == 0.05
    assert "rubric_weights" in stats
    assert round(sum(stats["rubric_weights"].values()), 2) == 1.0


def test_cohens_kappa_disagreement_and_dynamic_reweighting():
    multi_reviews = [
        {
            "id": "1",
            "reviews": [
                {"reviewer": "alice", "decision": "approve", "codes": []},
                {"reviewer": "bob", "decision": "reject", "codes": [ReviewReasonCode.FACTUAL_HALLUCINATION.value]},
            ],
            "reason_codes": [ReviewReasonCode.FACTUAL_HALLUCINATION.value],
        },
        {
            "id": "2",
            "reviews": [
                {"reviewer": "alice", "decision": "reject", "codes": [ReviewReasonCode.STATUTORY_MISQUOTATION.value]},
                {"reviewer": "bob", "decision": "approve", "codes": []},
            ],
            "reason_codes": [ReviewReasonCode.STATUTORY_MISQUOTATION.value],
        },
    ]

    stats = ReviewCalibrationTracker.compute_inter_annotator_calibration(multi_reviews)
    assert stats["decision_agreement_pct"] == 0.0
    assert stats["cohens_kappa"] < 0.0
    assert stats["calibration_verdict"] == "divergent_guidelines_needed"
    assert stats["recommended_arbitration_rate"] == 0.30
    # Because grounding reason codes occurred, grounding weight is boosted
    assert stats["rubric_weights"]["grounding"] > stats["baseline_weights"]["grounding"]


@pytest.mark.asyncio
async def test_review_service_rebalance_and_db_reports(tmp_path):
    db_path = tmp_path / "test_calibration.db"
    db = DatabaseManager(f"sqlite+aiosqlite:///{db_path}")
    await db.create_tables()

    review_service = ReviewService(db=db)
    result = await review_service.rebalance_rubrics()
    assert result["status"] == "rebalanced"
    assert "report_id" in result
    assert "rebalanced_rubrics" in result

    # Check that report is retrieved from history
    history = await review_service.get_calibration_history()
    assert len(history) == 1
    assert history[0]["id"] == result["report_id"]

    await db.close()
