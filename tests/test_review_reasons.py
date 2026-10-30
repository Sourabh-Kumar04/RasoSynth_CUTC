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
