"""Tests for the semantic quality scorer."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.quality_scorer import QualityScorer, QualityScore


@pytest.mark.asyncio
async def test_quality_scorer_initialization():
    scorer = QualityScorer()
    assert scorer is not None
    assert scorer.weights["semantic"] == 0.30
    assert scorer.weights["relevance"] == 0.20


@pytest.mark.asyncio
async def test_quality_scorer_basic():
    scorer = QualityScorer()
    result = await scorer.score(
        instruction="Explain what machine learning is.",
        response="Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
        domain="artificial intelligence",
    )
    assert isinstance(result, QualityScore)
    assert 0.0 <= result.semantic_score <= 1.0
    assert 0.0 <= result.relevance_score <= 1.0
    assert 0.0 <= result.completeness_score <= 1.0
    assert 0.0 <= result.coherence_score <= 1.0
    assert 0.0 <= result.final_score <= 1.0
    assert result.details is not None


@pytest.mark.asyncio
async def test_quality_scorer_no_domain():
    scorer = QualityScorer()
    result = await scorer.score(
        instruction="Hello, how are you?",
        response="I'm doing well, thank you!",
    )
    assert isinstance(result, QualityScore)
    assert result.relevance_score == 0.7  # Default when no domain


@pytest.mark.asyncio
async def test_quality_scorer_empty():
    scorer = QualityScorer()
    result = await scorer.score("", "")
    assert result.final_score >= 0.0


@pytest.mark.asyncio
async def test_quality_scorer_batch():
    scorer = QualityScorer()
    samples = [
        {"instruction": "What is AI?", "response": "AI is artificial intelligence."},
        {"instruction": "Explain Python.", "response": "Python is a programming language."},
    ]
    results = await scorer.score_batch(samples)
    assert len(results) == 2
    for r in results:
        assert isinstance(r, QualityScore)


def test_quality_score_dataclass():
    qs = QualityScore(
        semantic_score=0.8,
        relevance_score=0.7,
        completeness_score=0.9,
        coherence_score=0.85,
        final_score=0.82,
        scores={"semantic": 0.8, "relevance": 0.7, "completeness": 0.9, "coherence": 0.85},
        details={},
    )
    assert qs.final_score == 0.82
    assert qs.semantic_score == 0.8


@pytest.mark.asyncio
async def test_quality_scorer_custom_weights():
    weights = {"semantic": 0.5, "relevance": 0.3, "completeness": 0.1, "coherence": 0.1}
    scorer = QualityScorer(weights=weights)
    assert scorer.weights["semantic"] == 0.5