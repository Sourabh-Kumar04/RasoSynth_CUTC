"""Tests for deterministic quality scoring."""
import pytest
from pipeline.quality_breakdown import (
    QualityScoreBreakdown,
    compute_final_score,
    FilterThresholds,
    get_thresholds,
    DEFAULT_THRESHOLDS,
    DATASET_TYPE_THRESHOLDS,
)


class TestQualityScoreBreakdown:
    """Test QualityScoreBreakdown dataclass."""

    def test_immutable(self):
        """Breakdown should be frozen (immutable)."""
        breakdown = QualityScoreBreakdown(
            signal_score=0.8,
            statistical_score=0.7,
            semantic_score=0.9,
            reasoning_score=0.85,
            grounding_score=0.75,
        )
        with pytest.raises(Exception):  # frozen dataclass
            breakdown.signal_score = 0.5

    def test_to_dict(self):
        """to_dict should return all fields."""
        breakdown = QualityScoreBreakdown(
            signal_score=0.8,
            statistical_score=0.7,
            semantic_score=0.9,
            reasoning_score=0.85,
            grounding_score=0.75,
            filter_passed=True,
            failed_dimensions=[],
        )
        result = breakdown.to_dict()
        assert "signal" in result
        assert "statistical" in result
        assert "semantic" in result
        assert "reasoning" in result
        assert "grounding" in result
        assert "final" in result
        assert result["filter_passed"] is True

    def test_filter_passed_default(self):
        """Default filter_passed should be True."""
        breakdown = QualityScoreBreakdown(
            signal_score=0.8,
            statistical_score=0.7,
            semantic_score=0.9,
            reasoning_score=0.85,
            grounding_score=0.75,
        )
        assert breakdown.filter_passed is True
        assert breakdown.failed_dimensions == []


class TestComputeFinalScore:
    """Test the single authoritative formula."""

    def test_perfect_scores(self):
        """All 1.0 scores should yield 1.0 final."""
        breakdown = QualityScoreBreakdown(
            signal_score=1.0,
            statistical_score=1.0,
            semantic_score=1.0,
            reasoning_score=1.0,
            grounding_score=1.0,
        )
        assert compute_final_score(breakdown) == 1.0

    def test_zero_scores(self):
        """All 0.0 scores should yield 0.0 final."""
        breakdown = QualityScoreBreakdown(
            signal_score=0.0,
            statistical_score=0.0,
            semantic_score=0.0,
            reasoning_score=0.0,
            grounding_score=0.0,
        )
        assert compute_final_score(breakdown) == 0.0

    def test_weights_sum_to_one(self):
        """Verify weights: 0.10 + 0.15 + 0.25 + 0.25 + 0.25 = 1.0."""
        breakdown = QualityScoreBreakdown(
            signal_score=1.0,
            statistical_score=0.0,
            semantic_score=0.0,
            reasoning_score=0.0,
            grounding_score=0.0,
        )
        assert compute_final_score(breakdown) == 0.10

        breakdown = QualityScoreBreakdown(
            signal_score=0.0,
            statistical_score=1.0,
            semantic_score=0.0,
            reasoning_score=0.0,
            grounding_score=0.0,
        )
        assert compute_final_score(breakdown) == 0.15

    def test_mid_range_sample(self):
        """Test realistic mid-range scores."""
        breakdown = QualityScoreBreakdown(
            signal_score=0.8,
            statistical_score=0.7,
            semantic_score=0.9,
            reasoning_score=0.85,
            grounding_score=0.75,
        )
        expected = (
            0.8 * 0.10 +
            0.7 * 0.15 +
            0.9 * 0.25 +
            0.85 * 0.25 +
            0.75 * 0.25
        )
        assert abs(compute_final_score(breakdown) - expected) < 0.0001


class TestFilterThresholds:
    """Test static threshold configuration."""

    def test_default_thresholds(self):
        """Default thresholds should be immutable."""
        thresholds = DEFAULT_THRESHOLDS
        assert thresholds.signal == 0.40
        assert thresholds.statistical == 0.40
        assert thresholds.semantic == 0.40
        assert thresholds.reasoning == 0.40
        assert thresholds.grounding == 0.40

    def test_thresholds_frozen(self):
        """Thresholds should be immutable."""
        with pytest.raises(Exception):
            DEFAULT_THRESHOLDS.signal = 0.5

    def test_dataset_type_presets_sft(self):
        """SFT dataset should have standard thresholds."""
        thresholds = get_thresholds("sft")
        assert thresholds.signal == 0.40
        assert thresholds.grounding == 0.40

    def test_dataset_type_presets_rag(self):
        """RAG dataset should have higher grounding threshold."""
        thresholds = get_thresholds("rag")
        assert thresholds.grounding == 0.90

    def test_unknown_dataset_type_falls_back(self):
        """Unknown dataset type should use defaults."""
        thresholds = get_thresholds("unknown_type_xyz")
        assert thresholds == DEFAULT_THRESHOLDS

    def test_all_dataset_types_defined(self):
        """All expected dataset types should have presets."""
        expected_types = [
            "sft", "rag", "rlhf", "classification",
            "coding", "reasoning", "conversational", "tool_calling"
        ]
        for ds_type in expected_types:
            thresholds = get_thresholds(ds_type)
            assert thresholds is not None


class TestDeterminism:
    """Verify scoring is 100% deterministic."""

    def test_same_input_same_output(self):
        """Same input should always produce same output."""
        breakdown = QualityScoreBreakdown(
            signal_score=0.82,
            statistical_score=0.73,
            semantic_score=0.91,
            reasoning_score=0.86,
            grounding_score=0.77,
        )
        results = [compute_final_score(breakdown) for _ in range(100)]
        assert len(set(results)) == 1  # All identical

    def test_formula_order_independent(self):
        """Formula should be commutative (order independent)."""
        b1 = QualityScoreBreakdown(
            signal_score=0.8, statistical_score=0.7,
            semantic_score=0.9, reasoning_score=0.85, grounding_score=0.75,
        )
        b2 = QualityScoreBreakdown(
            grounding_score=0.75, reasoning_score=0.85,
            semantic_score=0.9, statistical_score=0.7, signal_score=0.8,
        )
        assert compute_final_score(b1) == compute_final_score(b2)