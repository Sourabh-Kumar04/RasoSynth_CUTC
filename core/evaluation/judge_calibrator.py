"""LLM Judge Calibration & Human Agreement Engine.

Measures inter-annotator agreement (Cohen's Kappa), systematic bias,
and calibration curves between automated LLM Judge evaluations and human reviewer decisions.
"""

from typing import Any, Dict, List, Tuple


def compute_cohens_kappa(human_labels: List[int], judge_labels: List[int]) -> float:
    """Compute Cohen's Kappa coefficient between binary human and judge decisions."""
    if not human_labels or len(human_labels) != len(judge_labels):
        return 0.0

    n = len(human_labels)
    # Observed agreement
    agree = sum(1 for h, j in zip(human_labels, judge_labels) if h == j)
    po = agree / n

    # Marginal probabilities
    h1 = sum(human_labels) / n
    h0 = 1.0 - h1
    j1 = sum(judge_labels) / n
    j0 = 1.0 - j1

    pe = (h1 * j1) + (h0 * j0)
    if pe >= 1.0:
        return 1.0

    kappa = (po - pe) / (1.0 - pe)
    return round(max(-1.0, min(1.0, kappa)), 3)


def calibrate_judge_alignment(
    evaluations: List[Dict[str, Any]],
    default_threshold: float = 0.70,
) -> Dict[str, Any]:
    """Analyze judge-human alignment, compute Kappa, detect bias, and find optimal threshold."""
    if not evaluations:
        return {
            "total_pairs": 0,
            "cohens_kappa": 0.0,
            "accuracy": 0.0,
            "bias_direction": "none",
            "optimal_threshold": default_threshold,
            "agreement_strength": "none",
        }

    human_binary = []
    judge_scores = []

    for ev in evaluations:
        h_decision = ev.get("human_decision")
        if isinstance(h_decision, str):
            h_val = 1 if h_decision.lower() in ("approved", "accepted", "pass", "good") else 0
        else:
            h_val = 1 if bool(h_decision) else 0

        j_score = float(ev.get("judge_score", 0.0))
        human_binary.append(h_val)
        judge_scores.append(j_score)

    judge_binary = [1 if s >= default_threshold else 0 for s in judge_scores]

    # Accuracy & Kappa
    n = len(human_binary)
    matches = sum(1 for h, j in zip(human_binary, judge_binary) if h == j)
    accuracy = round((matches / n) * 100, 1)

    kappa = compute_cohens_kappa(human_binary, judge_binary)

    # Systematic bias: judge approving more than human vs less
    h_approved_pct = (sum(human_binary) / n) * 100
    j_approved_pct = (sum(judge_binary) / n) * 100
    diff = j_approved_pct - h_approved_pct

    if diff > 5.0:
        bias = "lenient_score_inflation"
    elif diff < -5.0:
        bias = "harsh_over_rejection"
    else:
        bias = "unbiased_aligned"

    # Search for optimal threshold that maximizes agreement
    best_thresh = default_threshold
    best_acc = matches / n

    for test_t in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
        test_bin = [1 if s >= test_t else 0 for s in judge_scores]
        acc = sum(1 for h, j in zip(human_binary, test_bin) if h == j) / n
        if acc > best_acc:
            best_acc = acc
            best_thresh = test_t

    # Agreement strength classification (Landis & Koch standard)
    if kappa >= 0.81:
        strength = "almost_perfect"
    elif kappa >= 0.61:
        strength = "substantial"
    elif kappa >= 0.41:
        strength = "moderate"
    elif kappa >= 0.21:
        strength = "fair"
    else:
        strength = "slight_or_poor"

    return {
        "total_pairs": n,
        "cohens_kappa": kappa,
        "agreement_strength": strength,
        "pairwise_accuracy_pct": accuracy,
        "bias_direction": bias,
        "human_approval_rate_pct": round(h_approved_pct, 1),
        "judge_approval_rate_pct": round(j_approved_pct, 1),
        "current_threshold": default_threshold,
        "recommended_calibrated_threshold": best_thresh,
        "potential_accuracy_gain_pct": round((best_acc - (matches / n)) * 100, 1),
    }
