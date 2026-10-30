"""Structured Review Reasons and Reviewer Calibration Tracking.

Provides standardized structured reason codes for human rejection and edit decisions,
allowing review decisions to serve as direct feedback and stratification signals:
1. Enumerates canonical structured reason codes (not free-form text only).
2. Validates and extracts codes from review requests.
3. Tracks reviewer calibration and disagreement across multi-annotator reviews.
4. Translates rejection patterns into stratification and prompt feedback signals.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ReviewReasonCode(str, Enum):
    """Standardized rejection and edit reason codes."""

    # Factual and domain accuracy
    FACTUAL_HALLUCINATION = "factual_hallucination"
    STATUTORY_MISQUOTATION = "statutory_misquotation"
    INCOMPLETE_EXPLANATION = "incomplete_explanation"
    CALCULATION_OR_LOGIC_ERROR = "calculation_or_logic_error"

    # Tone, style, and language
    UNSUITABLE_TONE_OR_STYLE = "unsuitable_tone_or_style"
    POOR_VERNACULAR_OR_TRANSLATION = "poor_vernacular_or_translation"

    # Formatting and structure
    FORMAT_COMPLIANCE_FAILURE = "format_compliance_failure"
    CORRUPTED_TEMPLATE_TOKENS = "corrupted_template_tokens"

    # Safety and relevance
    PII_OR_SECURITY_RISK = "pii_or_security_risk"
    OUT_OF_DOMAIN = "out_of_domain"
    DUPLICATE_SAMPLE = "duplicate_sample"

    # Fallback
    OTHER = "other"


# Human-friendly descriptions for each code
REASON_DESCRIPTIONS: Dict[ReviewReasonCode, str] = {
    ReviewReasonCode.FACTUAL_HALLUCINATION: "Factual inaccuracy or fabricated assertions.",
    ReviewReasonCode.STATUTORY_MISQUOTATION: "Incorrect citation, section reference, or statutory misinterpretation.",
    ReviewReasonCode.INCOMPLETE_EXPLANATION: "Omitted critical condition, limitation, or exception.",
    ReviewReasonCode.CALCULATION_OR_LOGIC_ERROR: "Mathematical or deduction error in reasoning.",
    ReviewReasonCode.UNSUITABLE_TONE_OR_STYLE: "Inappropriate persona, unnatural style, or conversational artifacts.",
    ReviewReasonCode.POOR_VERNACULAR_OR_TRANSLATION: "Grammatical errors or unnatural phrasing in regional language / Hinglish.",
    ReviewReasonCode.FORMAT_COMPLIANCE_FAILURE: "Did not conform to requested output schema (JSON, markdown, tables).",
    ReviewReasonCode.CORRUPTED_TEMPLATE_TOKENS: "Contained unrendered prompt delimiters or stray tokens.",
    ReviewReasonCode.PII_OR_SECURITY_RISK: "Contained personal information, phone numbers, or unscrubbed identifiers.",
    ReviewReasonCode.OUT_OF_DOMAIN: "Instruction falls outside the target legal/statutory curriculum.",
    ReviewReasonCode.DUPLICATE_SAMPLE: "Exact or near-duplicate of existing training sample.",
    ReviewReasonCode.OTHER: "Other reason specified in reviewer notes.",
}

# Aliases for fuzzy matching from free-form text or older UI inputs
CODE_ALIASES: Dict[str, ReviewReasonCode] = {
    "hallucination": ReviewReasonCode.FACTUAL_HALLUCINATION,
    "factual": ReviewReasonCode.FACTUAL_HALLUCINATION,
    "citation": ReviewReasonCode.STATUTORY_MISQUOTATION,
    "statute": ReviewReasonCode.STATUTORY_MISQUOTATION,
    "misquotation": ReviewReasonCode.STATUTORY_MISQUOTATION,
    "incomplete": ReviewReasonCode.INCOMPLETE_EXPLANATION,
    "missing": ReviewReasonCode.INCOMPLETE_EXPLANATION,
    "tone": ReviewReasonCode.UNSUITABLE_TONE_OR_STYLE,
    "style": ReviewReasonCode.UNSUITABLE_TONE_OR_STYLE,
    "language": ReviewReasonCode.POOR_VERNACULAR_OR_TRANSLATION,
    "hinglish": ReviewReasonCode.POOR_VERNACULAR_OR_TRANSLATION,
    "format": ReviewReasonCode.FORMAT_COMPLIANCE_FAILURE,
    "schema": ReviewReasonCode.FORMAT_COMPLIANCE_FAILURE,
    "pii": ReviewReasonCode.PII_OR_SECURITY_RISK,
    "privacy": ReviewReasonCode.PII_OR_SECURITY_RISK,
    "domain": ReviewReasonCode.OUT_OF_DOMAIN,
    "irrelevant": ReviewReasonCode.OUT_OF_DOMAIN,
    "duplicate": ReviewReasonCode.DUPLICATE_SAMPLE,
}


def normalize_reason_codes(
    codes: Optional[List[str] | str] = None,
    notes: str = "",
) -> List[str]:
    """Normalize input reason codes to canonical ReviewReasonCode values.

    Extracts codes from explicit list, and falls back to scanning notes if empty.
    """
    valid_codes = {c.value for c in ReviewReasonCode}
    normalized: Set[str] = set()

    raw_list: List[str] = []
    if isinstance(codes, str):
        raw_list = [c.strip() for c in codes.replace(",", " ").split() if c.strip()]
    elif isinstance(codes, list):
        raw_list = [str(c).strip() for c in codes if str(c).strip()]

    for item in raw_list:
        clean = item.lower().replace("-", "_")
        if clean in valid_codes:
            normalized.add(clean)
        elif clean in CODE_ALIASES:
            normalized.add(CODE_ALIASES[clean].value)

    # If no codes were passed explicitly, attempt keyword extraction from notes
    if not normalized and notes:
        lower_notes = notes.lower()
        for alias, code in CODE_ALIASES.items():
            if alias in lower_notes:
                normalized.add(code.value)

    if not normalized and (notes or raw_list):
        normalized.add(ReviewReasonCode.OTHER.value)

    return sorted(list(normalized))


class ReviewCalibrationTracker:
    """Computes reviewer disagreement, inter-annotator calibration, and feedback signals."""

    @staticmethod
    def compute_feedback_signals(review_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate structured reason codes by segment/stratum for pipeline feedback."""
        rejection_counts_by_code: Dict[str, int] = defaultdict(int)
        edit_counts_by_code: Dict[str, int] = defaultdict(int)
        rejections_by_topic: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        total_rejected = 0
        total_edited = 0
        total_approved = 0

        for item in review_items:
            decision = str(item.get("review_decision") or item.get("review_status") or "").lower()
            meta = item.get("metadata") or item.get("extra_metadata") or {}
            if not isinstance(meta, dict):
                meta = {}
            topic = str(meta.get("topic") or meta.get("domain") or "general").lower()
            codes = meta.get("reason_codes") or []
            if not isinstance(codes, list):
                codes = [str(codes)]

            if decision == "reject":
                total_rejected += 1
                for c in codes:
                    rejection_counts_by_code[c] += 1
                    rejections_by_topic[topic][c] += 1
            elif decision == "edit":
                total_edited += 1
                for c in codes:
                    edit_counts_by_code[c] += 1
            elif decision == "approve":
                total_approved += 1

        # Identify vulnerable strata needing synthesis adjustment
        vulnerable_strata = []
        for top, breakdown in rejections_by_topic.items():
            tot_topic_rej = sum(breakdown.values())
            if tot_topic_rej >= 3:
                dominant_code = max(breakdown.items(), key=lambda x: x[1])[0]
                vulnerable_strata.append({
                    "topic": top,
                    "rejections": tot_topic_rej,
                    "primary_failure": dominant_code,
                    "recommendation": f"Increase grounding constraints for '{top}' to mitigate {dominant_code}.",
                })

        return {
            "total_reviewed": total_approved + total_rejected + total_edited,
            "total_approved": total_approved,
            "total_rejected": total_rejected,
            "total_edited": total_edited,
            "rejections_by_reason": dict(rejection_counts_by_code),
            "edits_by_reason": dict(edit_counts_by_code),
            "vulnerable_strata": vulnerable_strata,
        }

    @staticmethod
    def compute_inter_annotator_calibration(multi_reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute agreement rate and calibration statistics when multi-annotator reviews exist."""
        # multi_reviews: items with a list of reviews: [{"reviewer": ..., "decision": ..., "codes": [...]}]
        total_pairs = 0
        decision_agreements = 0
        code_jaccard_sum = 0.0

        for item in multi_reviews:
            reviews = item.get("reviews", [])
            if len(reviews) < 2:
                continue

            # Compare pairs of reviews
            for i in range(len(reviews)):
                for j in range(i + 1, len(reviews)):
                    r1 = reviews[i]
                    r2 = reviews[j]
                    total_pairs += 1

                    if r1.get("decision") == r2.get("decision"):
                        decision_agreements += 1

                    codes1 = set(r1.get("codes", []))
                    codes2 = set(r2.get("codes", []))
                    if codes1 or codes2:
                        jaccard = len(codes1 & codes2) / len(codes1 | codes2)
                        code_jaccard_sum += jaccard
                    else:
                        code_jaccard_sum += 1.0

        if total_pairs == 0:
            return {
                "multi_reviewed_count": 0,
                "decision_agreement_pct": None,
                "reason_code_jaccard": None,
                "status": "insufficient_multi_review_data",
            }

        dec_agreement = round((decision_agreements / total_pairs) * 100, 1)
        mean_jaccard = round(code_jaccard_sum / total_pairs, 3)

        return {
            "multi_reviewed_count": len(multi_reviews),
            "evaluated_pairs": total_pairs,
            "decision_agreement_pct": dec_agreement,
            "reason_code_jaccard": mean_jaccard,
            "calibration_verdict": "well_calibrated" if dec_agreement >= 80.0 else "divergent_guidelines_needed",
        }
