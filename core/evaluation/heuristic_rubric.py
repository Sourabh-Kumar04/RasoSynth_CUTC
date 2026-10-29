"""Heuristic multi-dimensional evaluation rubric (NOT an LLM judge).

Scores synthetic instruction-response pairs across 5 dimensions with fixed
rules and constants (word overlap, keyword checks, length bands, a guardrail
predicate). No model is called, nothing is "judged" by an LLM, and the
weights are this repo's own — they do not match AlpacaEval / MT-Bench or
any other external standard. Every result carries method="heuristic_rubric"
so downstream consumers cannot mistake these constants for model judgements.
"""

import re
from typing import Any, Dict, Optional


def evaluate_sample_rubric(
    instruction: str,
    response: str,
    reference_context: Optional[str] = None,
    language: str = "en",
    formality_register: str = "formal",
) -> Dict[str, Any]:
    """
    Score sample quality with the heuristic rubric (no model call).

    Returns:
        Dict with dimension scores, overall_score, qualitative assessment,
        and method="heuristic_rubric".
    """
    inst = (instruction or "").strip()
    resp = (response or "").strip()

    if not inst or not resp:
        return {
            "method": "heuristic_rubric",
            "groundedness": None,
            "authenticity": 0.0,
            "domain_correctness": 0.0,
            "safety_tone": 0.0,
            "conciseness": 0.0,
            "overall_score": 0.0,
            "rating": "unacceptable",
        }

    # 1. Groundedness
    if reference_context and reference_context.strip():
        ref_words = set(re.findall(r"\w{4,}", reference_context.lower()))
        resp_words = set(re.findall(r"\w{4,}", resp.lower()))
        overlap = len(ref_words & resp_words) / max(len(resp_words), 1)
        groundedness: Optional[float] = min(1.0, round(0.4 + overlap * 0.8, 2))
    else:
        # No reference context provided -> unmeasured/None (never fabricated 0.90)
        groundedness = None

    # 2. Linguistic Authenticity
    lang = (language or "en").lower()
    authenticity = 0.85
    if "hi" in lang or "hinglish" in lang:
        if formality_register == "formal" and ("आप" in resp or "aap" in resp.lower() or "kripya" in resp.lower()):
            authenticity = 0.95
        elif formality_register == "casual" and ("tum" in resp.lower() or "तुम" in resp):
            authenticity = 0.92

    # 3. Domain & Statutory Correctness
    # Check for hallucinated boilerplate ("as an ai language model")
    bad_boilerplate = ["as an ai", "i do not have opinions", "knowledge cutoff", "as a machine learning"]
    has_boilerplate = any(b in resp.lower() for b in bad_boilerplate)
    domain_correctness = 0.40 if has_boilerplate else 0.92

    # 4. Safety & Tone
    from core.validation.cultural_guardrails import check_cultural_safety
    is_safe, _ = check_cultural_safety(resp)
    safety_tone = 0.98 if is_safe else 0.10

    # 5. Conciseness
    resp_len = len(resp.split())
    if 25 <= resp_len <= 350:
        conciseness = 0.95
    elif resp_len < 10:
        conciseness = 0.40
    else:
        conciseness = 0.80

    # Overall Weighted Index
    # When groundedness is missing, re-normalize across measured dimensions
    # Groundedness weight: 0.25, Authenticity: 0.20, Domain: 0.25, Safety: 0.20, Conciseness: 0.10
    if groundedness is not None:
        overall = round(
            (groundedness * 0.25) +
            (authenticity * 0.20) +
            (domain_correctness * 0.25) +
            (safety_tone * 0.20) +
            (conciseness * 0.10),
            2
        )
        rating = (
            "excellent" if overall >= 0.88
            else "proficient" if overall >= 0.72
            else "needs_refinement" if overall >= 0.50
            else "unacceptable"
        )
    else:
        # Re-weight across remaining 0.75 weight
        measured_sum = (
            (authenticity * 0.20) +
            (domain_correctness * 0.25) +
            (safety_tone * 0.20) +
            (conciseness * 0.10)
        )
        overall = round(measured_sum / 0.75, 2)
        # Without groundedness verification, rating cannot be "excellent" from constants alone
        if overall >= 0.72:
            rating = "proficient"
        elif overall >= 0.50:
            rating = "needs_refinement"
        else:
            rating = "unacceptable"

    return {
        "method": "heuristic_rubric",
        "groundedness": groundedness,
        "authenticity": authenticity,
        "domain_correctness": domain_correctness,
        "safety_tone": safety_tone,
        "conciseness": conciseness,
        "overall_score": overall,
        "rating": rating,
    }
