"""Deterministic quality scoring system.

Replaces the previous adaptive, multi-formula quality scoring with a single,
reproducible formula. All five dimensions are always computed, and the final
score uses the same weighted sum regardless of whether a sample passes or
fails filtering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Immutable data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FilterThresholds:
    """Static, configurable thresholds.  Never changed at runtime."""
    signal: float = 0.60
    statistical: float = 0.60
    semantic: float = 0.70
    reasoning: float = 0.70
    grounding: float = 0.80
    quality: float = 0.50   # <— legacy general threshold (kept for backward compat)
    toxicity: float = 0.70
    min_length: int = 50
    max_length: int = 50000


# Preset thresholds per dataset type (immutable).
DATASET_TYPE_THRESHOLDS: dict[str, FilterThresholds] = {
    "sft": FilterThresholds(0.40, 0.40, 0.40, 0.40, 0.40),
    "rag": FilterThresholds(0.50, 0.50,0.75, 0.75, 0.90),
    "rlhf": FilterThresholds(0.65, 0.65, 0.70, 0.70, 0.75),
    "classification": FilterThresholds(0.70, 0.70, 0.65, 0.65, 0.70),
    "coding": FilterThresholds(0.60, 0.60, 0.70, 0.80, 0.70),
    "reasoning": FilterThresholds(0.60, 0.65, 0.70, 0.80, 0.75),
    "conversational": FilterThresholds(0.55, 0.55, 0.65, 0.65, 0.70),
    "tool_calling": FilterThresholds(0.60, 0.60, 0.70, 0.75, 0.75),
}

DEFAULT_THRESHOLDS = FilterThresholds(0.40, 0.40, 0.40, 0.40, 0.40)


@dataclass(frozen=True)
class QualityScoreBreakdown:
    """Immutable, always-computed quality breakdown for a single sample."""
    signal_score: float = 0.0
    statistical_score: float = 0.0
    semantic_score: float = 0.0
    reasoning_score: float = 0.0
    grounding_score: float = 0.0
    confidence: float = 1.0
    filter_passed: bool = True
    failed_dimensions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "signal": round(self.signal_score, 4),
            "statistical": round(self.statistical_score, 4),
            "semantic": round(self.semantic_score, 4),
            "reasoning": round(self.reasoning_score, 4),
            "grounding": round(self.grounding_score, 4),
            "confidence": round(self.confidence, 4),
            "final": round(compute_final_score(self), 4),
            "filter_passed": self.filter_passed,
            "failed": list(self.failed_dimensions),
        }


def compute_final_score(breakdown: QualityScoreBreakdown) -> float:
    """Single authoritative formula for quality score.

    _Always_ uses the same weighting, regardless of pass/fail.
    """
    return (
        breakdown.signal_score * 0.10
        + breakdown.statistical_score * 0.15
        + breakdown.semantic_score * 0.25
        + breakdown.reasoning_score * 0.25
        + breakdown.grounding_score * 0.25
    )


def get_thresholds(dataset_type: str | None = None) -> FilterThresholds:
    """Return static thresholds; optionally select by dataset type."""
    if dataset_type:
        return DATASET_TYPE_THRESHOLDS.get(dataset_type, DEFAULT_THRESHOLDS)
    return DEFAULT_THRESHOLDS
