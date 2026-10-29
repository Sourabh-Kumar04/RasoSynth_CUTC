"""Direct Synthetic Benchmark Evaluator.

Evaluates candidate model outputs against held-out synthetic test splits,
computing Exact Match (EM), Token-F1, character-level overlap, and citation grounding.
"""

import re
from typing import Any, Dict, List, Optional
from core.metrics.fidelity import compute_chrf_score


def normalize_text_for_eval(text: str) -> str:
    """Normalize text by stripping whitespace, punctuation, and lowercasing."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return " ".join(cleaned.split())


def compute_token_f1(prediction: str, ground_truth: str) -> float:
    """Compute token-level precision, recall, and F1 score between strings."""
    pred_tokens = normalize_text_for_eval(prediction).split()
    gt_tokens = normalize_text_for_eval(ground_truth).split()

    if not pred_tokens or not gt_tokens:
        return 1.0 if pred_tokens == gt_tokens else 0.0

    common = set(pred_tokens) & set(gt_tokens)
    if not common:
        return 0.0

    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gt_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return round(f1, 3)


def evaluate_benchmark_split(
    evaluation_pairs: List[Dict[str, str]],
    benchmark_name: str = "Synthetic Indic QA",
    target_model: str = "Candidate LLM",
    held_out: bool = False,
) -> Dict[str, Any]:
    """Run comprehensive benchmark metrics across evaluation pairs.

    Args:
        evaluation_pairs: List of dicts with prediction, reference, and optional id.
        benchmark_name: Name of benchmark split.
        target_model: Candidate model under evaluation.
        held_out: Whether the evaluation split is verified held-out.
                  Ratings 'production_ready' and 'frontier_exceptional' are only
                  awarded when held_out is True. Defaults to False.
    """
    if not evaluation_pairs:
        return {
            "benchmark_name": benchmark_name,
            "target_model": target_model,
            "held_out": held_out,
            "total_samples": 0,
            "exact_match_pct": 0.0,
            "mean_token_f1": 0.0,
            "mean_chrf_score": 0.0,
            "citation_accuracy_pct": None,
            "rating": "no_data",
        }

    em_count = 0
    f1_scores = []
    chrf_scores = []
    citation_checks = []

    detailed_results = []

    for idx, pair in enumerate(evaluation_pairs):
        pred = str(pair.get("prediction", "")).strip()
        ref = str(pair.get("reference", "")).strip()

        norm_pred = normalize_text_for_eval(pred)
        norm_ref = normalize_text_for_eval(ref)

        is_em = norm_pred == norm_ref
        if is_em:
            em_count += 1

        f1 = compute_token_f1(pred, ref)
        f1_scores.append(f1)

        chrf = compute_chrf_score(pred, ref)
        chrf_scores.append(chrf)

        # Citation check if reference contains [1] or similar
        ref_has_citation = bool(re.search(r"\[\d+\]", ref))
        if ref_has_citation:
            pred_has_citation = bool(re.search(r"\[\d+\]", pred))
            citation_checks.append(1 if pred_has_citation else 0)

        detailed_results.append({
            "sample_id": pair.get("id", f"eval-{idx+1}"),
            "exact_match": is_em,
            "token_f1": f1,
            "chrf_score": chrf,
        })

    n = len(evaluation_pairs)
    em_pct = round((em_count / n) * 100, 1)
    mean_f1 = round(sum(f1_scores) / n, 3)
    mean_chrf = round(sum(chrf_scores) / n, 2)
    # If no reference had citations, citation_accuracy_pct is None (never fake 100.0)
    citation_acc = round((sum(citation_checks) / len(citation_checks)) * 100, 1) if citation_checks else None

    composite = (em_pct * 0.4) + (mean_f1 * 40) + (mean_chrf * 0.2)

    # Only assign production_ready or frontier_exceptional when split is verified held-out
    if held_out:
        if composite >= 85:
            rating = "frontier_exceptional"
        elif composite >= 70:
            rating = "production_ready"
        elif composite >= 50:
            rating = "acceptable_requires_tuning"
        else:
            rating = "suboptimal_hallucination_prone"
    else:
        if composite >= 50:
            rating = "unverified_split_not_held_out"
        else:
            rating = "suboptimal_hallucination_prone"

    return {
        "benchmark_name": benchmark_name,
        "target_model": target_model,
        "held_out": held_out,
        "total_samples": n,
        "exact_match_pct": em_pct,
        "mean_token_f1": mean_f1,
        "mean_chrf_score": mean_chrf,
        "citation_accuracy_pct": citation_acc,
        "composite_score": round(composite, 1),
        "rating": rating,
        "sample_evaluations": detailed_results[:10],
    }
