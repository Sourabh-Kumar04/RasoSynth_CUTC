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
        """Compute agreement rate, Cohen's Kappa, rubric failure distribution, and dynamic weights."""
        total_pairs = 0
        decision_agreements = 0
        code_jaccard_sum = 0.0

        r1_counts: Dict[str, int] = defaultdict(int)
        r2_counts: Dict[str, int] = defaultdict(int)
        all_categories: Set[str] = set()

        # Rubric category definitions
        rubric_mapping = {
            "grounding": {
                ReviewReasonCode.FACTUAL_HALLUCINATION.value,
                ReviewReasonCode.STATUTORY_MISQUOTATION.value,
            },
            "instruction_following": {
                ReviewReasonCode.INCOMPLETE_EXPLANATION.value,
                ReviewReasonCode.CALCULATION_OR_LOGIC_ERROR.value,
                ReviewReasonCode.OUT_OF_DOMAIN.value,
            },
            "clarity_style": {
                ReviewReasonCode.UNSUITABLE_TONE_OR_STYLE.value,
                ReviewReasonCode.POOR_VERNACULAR_OR_TRANSLATION.value,
            },
            "formatting": {
                ReviewReasonCode.FORMAT_COMPLIANCE_FAILURE.value,
                ReviewReasonCode.CORRUPTED_TEMPLATE_TOKENS.value,
            },
            "safety_and_dedup": {
                ReviewReasonCode.PII_OR_SECURITY_RISK.value,
                ReviewReasonCode.DUPLICATE_SAMPLE.value,
            },
        }

        baseline_weights = {
            "grounding": 0.35,
            "instruction_following": 0.25,
            "clarity_style": 0.15,
            "formatting": 0.15,
            "safety_and_dedup": 0.10,
        }

        rubric_failure_counts: Dict[str, int] = defaultdict(int)
        total_failures = 0

        for item in multi_reviews:
            # Count any observed reason codes for rubric distribution
            item_codes = []
            meta = item.get("metadata") or item.get("extra_metadata") or {}
            if isinstance(meta, dict) and meta.get("reason_codes"):
                item_codes.extend(meta.get("reason_codes"))
            elif item.get("reason_codes"):
                item_codes.extend(item.get("reason_codes"))
            elif item.get("reason_code"):
                item_codes.append(item.get("reason_code"))

            for rc in item_codes:
                rc_str = str(rc).lower()
                for dim, dim_codes in rubric_mapping.items():
                    if rc_str in dim_codes:
                        rubric_failure_counts[dim] += 1
                        total_failures += 1

            reviews = item.get("reviews", [])
            if len(reviews) < 2:
                continue

            # Compare pairs of reviews
            for i in range(len(reviews)):
                for j in range(i + 1, len(reviews)):
                    r1 = reviews[i]
                    r2 = reviews[j]
                    total_pairs += 1

                    dec1 = str(r1.get("decision", "")).strip().lower()
                    dec2 = str(r2.get("decision", "")).strip().lower()
                    r1_counts[dec1] += 1
                    r2_counts[dec2] += 1
                    all_categories.add(dec1)
                    all_categories.add(dec2)

                    if dec1 == dec2:
                        decision_agreements += 1

                    codes1 = set(r1.get("codes", []))
                    codes2 = set(r2.get("codes", []))
                    if codes1 or codes2:
                        jaccard = len(codes1 & codes2) / len(codes1 | codes2)
                        code_jaccard_sum += jaccard
                    else:
                        code_jaccard_sum += 1.0

        # Calculate Cohen's Kappa when pairs exist
        cohens_kappa = None
        dec_agreement = None
        mean_jaccard = None
        verdict = "insufficient_data"
        arbitration_rate = 0.05

        if total_pairs > 0:
            p_o = decision_agreements / total_pairs
            dec_agreement = round(p_o * 100, 1)
            mean_jaccard = round(code_jaccard_sum / total_pairs, 3)

            p_e = 0.0
            for cat in all_categories:
                p_e += (r1_counts[cat] / total_pairs) * (r2_counts[cat] / total_pairs)

            if p_e >= 0.999999:
                cohens_kappa = 1.0
            else:
                kappa_raw = (p_o - p_e) / (1.0 - p_e)
                cohens_kappa = round(max(-1.0, min(1.0, kappa_raw)), 3)

            if dec_agreement >= 80.0:
                verdict = "well_calibrated"
                arbitration_rate = 0.05
            else:
                verdict = "divergent_guidelines_needed"
                arbitration_rate = 0.30 if (cohens_kappa is not None and cohens_kappa < 0.45) else 0.15

        # Dynamic rubric reweighting
        raw_weights = {}
        for dim, base_w in baseline_weights.items():
            dim_failures = rubric_failure_counts[dim]
            failure_ratio = (dim_failures / total_failures) if total_failures > 0 else 0.0
            # Boost weight if this dimension exhibits high failure or low kappa
            multiplier = 1.0 + failure_ratio
            if cohens_kappa is not None and cohens_kappa < 0.65 and dim in ("grounding", "instruction_following"):
                multiplier += 0.25
            raw_weights[dim] = base_w * multiplier

        weight_sum = sum(raw_weights.values())
        reweighted_rubrics = {
            dim: round(w / weight_sum, 4) for dim, w in raw_weights.items()
        }

        return {
            "multi_reviewed_count": len([i for i in multi_reviews if len(i.get("reviews", [])) >= 2]),
            "evaluated_pairs": total_pairs,
            "decision_agreement_pct": dec_agreement,
            "cohens_kappa": cohens_kappa,
            "reason_code_jaccard": mean_jaccard,
            "calibration_verdict": verdict,
            "recommended_arbitration_rate": arbitration_rate,
            "rubric_weights": reweighted_rubrics,
            "baseline_weights": baseline_weights,
            "dimension_failures": dict(rubric_failure_counts),
            "status": "calibrated" if total_pairs > 0 else "insufficient_multi_review_data",
        }
