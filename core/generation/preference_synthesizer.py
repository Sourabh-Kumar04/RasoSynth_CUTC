"""KTO (Kahneman-Tversky Optimization) & SimPO Preference Synthesizer.

Provides advanced alignment format transformations beyond standard DPO:
1. KTO: Binary signal optimization (instruction, completion, label: True/False) based on prospect theory.
2. SimPO: Length-normalized margin alignment without requiring reference models.
"""

from typing import Any, Dict, List, Optional, Tuple


def format_kto_sample(
    instruction: str,
    completion: str,
    is_desirable: bool,
    feedback_reason: Optional[str] = None,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Format an unpaired sample for Kahneman-Tversky Optimization (KTO).

    KTO aligns models on binary utility signals (thumbs up / thumbs down)
    without requiring paired counterfactual completions.
    """
    sample = {
        "prompt": instruction.strip(),
        "completion": completion.strip(),
        "label": bool(is_desirable),
        "kto_tag": "desirable" if is_desirable else "undesirable",
    }
    metadata = {}
    if feedback_reason:
        metadata["feedback_reason"] = feedback_reason
    if domain:
        metadata["domain"] = domain
    if metadata:
        sample["metadata"] = metadata

    return sample


def format_simpo_pair(
    instruction: str,
    chosen: str,
    rejected: str,
    target_margin: float = 0.5,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Format a pair for Simple Preference Optimization (SimPO).

    SimPO directly optimizes:
        L_SimPO = -E[log sigmoid( beta/|y_w| * log pi(y_w|x) - beta/|y_l| * log pi(y_l|x) - gamma )]
    incorporating length-normalization to prevent verbosity exploitation.
    """
    chosen_clean = chosen.strip()
    rejected_clean = rejected.strip()
    c_words = len(chosen_clean.split())
    r_words = len(rejected_clean.split())
    length_ratio = round(c_words / max(r_words, 1), 2)

    # Flag verbosity bias if chosen is > 2.5x longer than rejected
    is_verbosity_biased = length_ratio > 2.5

    record = {
        "instruction": instruction.strip(),
        "chosen": chosen_clean,
        "rejected": rejected_clean,
        "simpo_metadata": {
            "target_margin": target_margin,
            "chosen_word_count": c_words,
            "rejected_word_count": r_words,
            "length_ratio": length_ratio,
            "verbosity_bias_flag": is_verbosity_biased,
        }
    }
    if domain:
        record["simpo_metadata"]["domain"] = domain

    return record


def build_preference_directive(mode: str) -> str:
    """Return LLM prompting directive for preference synthesis."""
    if mode == "kto":
        return (
            "KTO (KAHNEMAN-TVERSKY) SPECIFICATION:\n"
            "Emit a binary desirable response that maximally satisfies statutory correctness, clarity, and tone. "
            "Also synthesize an undesirable completion marked by common pitfalls (e.g., outdated rate, over-verbosity, vague guidance).\n"
        )
    elif mode == "simpo":
        return (
            "SimPO (SIMPLE PREFERENCE OPTIMIZATION) SPECIFICATION:\n"
            "Emit both 'chosen' and 'rejected' responses.\n"
            "CRITICAL: The 'chosen' response must be concise, accurate, and direct. "
            "DO NOT make the chosen response artificially verbose. High information density with zero fluff.\n"
        )
    return ""
