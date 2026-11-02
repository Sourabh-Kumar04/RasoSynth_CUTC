"""Tests for structured review reasons, feedback signals, and reviewer calibration."""

import pytest

from core.review_reasons import (
    ReviewCalibrationTracker,
    ReviewReasonCode,
    normalize_reason_codes,
)


def test_reason_code_normalization_and_aliases():
    """Verify structured reason code normalization and alias resolution."""
    # Direct code
    res = normalize_reason_codes(["factual_hallucination"])
    assert res == ["factual_hallucination"]

    # Alias mapping
    res = normalize_reason_codes(["hallucination", "statute", "privacy"])
    assert "factual_hallucination" in res
    assert "statutory_misquotation" in res
    assert "pii_or_security_risk" in res

    # Space or comma separated string
    res = normalize_reason_codes("format, incomplete")
    assert "format_compliance_failure" in res
    assert "incomplete_explanation" in res

    # Keyword extraction from free-form notes
    res = normalize_reason_codes([], notes="Omitted Section 16(2) citation and wrong GST threshold")
    assert "statutory_misquotation" in res


def test_feedback_signals_aggregation():
    """Verify feedback signal computation and vulnerable strata detection."""
    items = [
        {
            "review_decision": "reject",
            "metadata": {
                "topic": "taxation",
                "reason_codes": ["statutory_misquotation", "factual_hallucination"],
            },
        },
        {
            "review_decision": "reject",
            "metadata": {
                "topic": "taxation",
                "reason_codes": ["statutory_misquotation"],
            },
        },
        {
            "review_decision": "reject",
            "metadata": {
                "topic": "taxation",
                "reason_codes": ["statutory_misquotation"],
            },
        },
        {
            "review_decision": "edit",
            "metadata": {
                "topic": "corporate_law",
                "reason_codes": ["incomplete_explanation"],
            },
        },
        {
            "review_decision": "approve",
            "metadata": {"topic": "compliance"},
        },
    ]

    signals = ReviewCalibrationTracker.compute_feedback_signals(items)

    assert signals["total_reviewed"] == 5
    assert signals["total_rejected"] == 3
    assert signals["total_edited"] == 1
    assert signals["total_approved"] == 1

    assert signals["rejections_by_reason"]["statutory_misquotation"] == 3
    assert signals["rejections_by_reason"]["factual_hallucination"] == 1
    assert signals["edits_by_reason"]["incomplete_explanation"] == 1

    # Check vulnerable strata recommendations
    assert len(signals["vulnerable_strata"]) == 1
    stratum = signals["vulnerable_strata"][0]
    assert stratum["topic"] == "taxation"
    assert stratum["primary_failure"] == "statutory_misquotation"
    assert "mitigate statutory_misquotation" in stratum["recommendation"]


def test_inter_annotator_calibration():
    """Verify reviewer disagreement and calibration tracking."""
    # 1. Multi-review agreement test
    multi_reviews = [
        {
            "item_id": "item-1",
            "reviews": [
                {"reviewer": "alice", "decision": "reject", "codes": ["factual_hallucination"]},
                {"reviewer": "bob", "decision": "reject", "codes": ["factual_hallucination"]},
            ],
        },
        {
            "item_id": "item-2",
            "reviews": [
                {"reviewer": "alice", "decision": "approve", "codes": []},
                {"reviewer": "bob", "decision": "approve", "codes": []},
            ],
        },
        {
            "item_id": "item-3",
            "reviews": [
                {"reviewer": "alice", "decision": "reject", "codes": ["statutory_misquotation"]},
                {"reviewer": "bob", "decision": "edit", "codes": ["incomplete_explanation"]},
            ],
        },
    ]

    cal = ReviewCalibrationTracker.compute_inter_annotator_calibration(multi_reviews)

    assert cal["multi_reviewed_count"] == 3
    assert cal["evaluated_pairs"] == 3
    assert cal["decision_agreement_pct"] == round((2 / 3) * 100, 1)  # 66.7%
    assert cal["calibration_verdict"] == "divergent_guidelines_needed"

    # 2. Perfect agreement
    perfect_reviews = [
        {
            "item_id": "item-1",
            "reviews": [
                {"reviewer": "alice", "decision": "approve", "codes": []},
                {"reviewer": "bob", "decision": "approve", "codes": []},
            ],
        },
    ]
    perf_cal = ReviewCalibrationTracker.compute_inter_annotator_calibration(perfect_reviews)
    assert perf_cal["decision_agreement_pct"] == 100.0
    assert perf_cal["calibration_verdict"] == "well_calibrated"


def test_10_code_review_reason_taxonomy_completeness():
    """Verify all 10 canonical review reason codes exist, are non-empty, and documented."""
    from core.review_reasons import REASON_DESCRIPTIONS, ReviewReasonCode

    canonical_10_codes = [
        ReviewReasonCode.FACTUAL_HALLUCINATION,
        ReviewReasonCode.STATUTORY_MISQUOTATION,
        ReviewReasonCode.INCOMPLETE_EXPLANATION,
        ReviewReasonCode.CALCULATION_OR_LOGIC_ERROR,
        ReviewReasonCode.UNSUITABLE_TONE_OR_STYLE,
        ReviewReasonCode.POOR_VERNACULAR_OR_TRANSLATION,
        ReviewReasonCode.FORMAT_COMPLIANCE_FAILURE,
        ReviewReasonCode.CORRUPTED_TEMPLATE_TOKENS,
        ReviewReasonCode.PII_OR_SECURITY_RISK,
        ReviewReasonCode.OUT_OF_DOMAIN,
    ]

    assert len(canonical_10_codes) == 10
    for code in canonical_10_codes:
        assert isinstance(code.value, str)
        assert len(code.value) > 0
        assert code in REASON_DESCRIPTIONS
        assert len(REASON_DESCRIPTIONS[code]) > 0

    # Also verify the supplementary codes
    assert ReviewReasonCode.DUPLICATE_SAMPLE in REASON_DESCRIPTIONS
    assert ReviewReasonCode.OTHER in REASON_DESCRIPTIONS


def test_cohen_kappa_calibration_computation_and_edge_cases():
    """Verify calibration computation under empty, single-reviewer, and varied agreement."""
    # Empty list
    res_empty = ReviewCalibrationTracker.compute_inter_annotator_calibration([])
    assert res_empty["status"] == "insufficient_multi_review_data"
    assert res_empty["multi_reviewed_count"] == 0

    # Single reviews only (no pairs)
    single_reviews = [
        {"item_id": "1", "reviews": [{"reviewer": "r1", "decision": "approve"}]},
        {"item_id": "2", "reviews": [{"reviewer": "r2", "decision": "reject"}]},
    ]
    res_single = ReviewCalibrationTracker.compute_inter_annotator_calibration(single_reviews)
    assert res_single["status"] == "insufficient_multi_review_data"

    # Perfect agreement
    perfect = [
        {
            "item_id": "1",
            "reviews": [
                {"reviewer": "r1", "decision": "reject", "codes": ["out_of_domain"]},
                {"reviewer": "r2", "decision": "reject", "codes": ["out_of_domain"]},
            ],
        }
    ]
    res_perf = ReviewCalibrationTracker.compute_inter_annotator_calibration(perfect)
    assert res_perf["decision_agreement_pct"] == 100.0
    assert res_perf["reason_code_jaccard"] == 1.0
    assert res_perf["calibration_verdict"] == "well_calibrated"


def test_review_signals_and_calibration_endpoints(test_client, auth_headers):
    """Verify GET /api/review/signals and GET /api/review/calibration endpoints."""
    from unittest.mock import AsyncMock, MagicMock
    from api.server import app

    mock_svc = MagicMock()
    mock_svc.get_feedback_signals = AsyncMock(return_value={
        "total_reviewed": 10,
        "total_approved": 8,
        "total_rejected": 2,
        "total_edited": 0,
        "rejections_by_reason": {"factual_hallucination": 2},
        "edits_by_reason": {},
        "vulnerable_strata": [],
    })
    mock_svc.get_calibration_stats = AsyncMock(return_value={
        "multi_reviewed_count": 5,
        "evaluated_pairs": 5,
        "decision_agreement_pct": 100.0,
        "reason_code_jaccard": 0.85,
        "calibration_verdict": "well_calibrated",
    })

    orig_svc = getattr(app.state, "review_service", None)
    app.state.review_service = mock_svc

    try:
        # 1. Signals endpoint
        resp_signals = test_client.get("/api/review/signals", headers=auth_headers)
        assert resp_signals.status_code == 200
        sig_data = resp_signals.json()
        assert sig_data["total_reviewed"] == 10
        assert sig_data["total_rejected"] == 2
        assert sig_data["rejections_by_reason"]["factual_hallucination"] == 2

        # 2. Calibration endpoint
        resp_cal = test_client.get("/api/review/calibration", headers=auth_headers)
        assert resp_cal.status_code == 200
        cal_data = resp_cal.json()
        assert cal_data["multi_reviewed_count"] == 5
        assert cal_data["decision_agreement_pct"] == 100.0
        assert cal_data["calibration_verdict"] == "well_calibrated"
    finally:
        app.state.review_service = orig_svc
