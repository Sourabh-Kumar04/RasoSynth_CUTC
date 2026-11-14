"""
Core Evaluator — central entry point for model and dataset quality evaluation.

Re-exports benchmark evaluators, LLM-as-a-judge alignment engines,
heuristic rubrics, and comparative inference harnesses.
"""

from core.evaluation.benchmark_evaluator import (
    evaluate_benchmark_split,
    compute_token_f1,
    normalize_text_for_eval,
)
from core.evaluation.alignment_judge import (
    AlignmentJudge,
    ComparativeBenchmarkResult,
    EvaluationComparisonItem,
)
from core.evaluation.heuristic_rubric import evaluate_sample_rubric
from core.evaluation.inference_harness import (
    evaluate_base_vs_finetuned,
    check_format_compliance,
    compute_pseudo_perplexity,
)
from core.evaluation.arena import (
    ComparativeEloArena,
    ArenaMatch,
    ModelEloRating,
)
from core.evaluation.judge_calibrator import (
    calibrate_judge_alignment,
    compute_cohens_kappa,
)
from finetuning.trainer import evaluate_finetuned_model

__all__ = [
    "evaluate_benchmark_split",
    "compute_token_f1",
    "normalize_text_for_eval",
    "AlignmentJudge",
    "ComparativeBenchmarkResult",
    "EvaluationComparisonItem",
    "evaluate_sample_rubric",
    "evaluate_base_vs_finetuned",
    "evaluate_finetuned_model",
    "check_format_compliance",
    "compute_pseudo_perplexity",
    "ComparativeEloArena",
    "ArenaMatch",
    "ModelEloRating",
    "calibrate_judge_alignment",
    "compute_cohens_kappa",
]
