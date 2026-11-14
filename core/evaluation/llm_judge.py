"""Backwards-compatible shim for core.evaluation.llm_judge -> core.evaluation.heuristic_rubric.

NOTE: This module is NOT an LLM judge; it evaluates heuristic rubric rules.
See `core.evaluation.heuristic_rubric` for full details.
"""

from core.evaluation.heuristic_rubric import evaluate_sample_rubric
from core.evaluation.alignment_judge import AlignmentJudge, ComparativeBenchmarkResult, EvaluationComparisonItem

__all__ = [
    "evaluate_sample_rubric",
    "AlignmentJudge",
    "ComparativeBenchmarkResult",
    "EvaluationComparisonItem",
]
