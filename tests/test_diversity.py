"""Tests for the dataset diversity analyzer."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.diversity import DatasetDiversityAnalyzer, DiversityMetrics


@pytest.mark.asyncio
async def test_diversity_initialization():
    analyzer = DatasetDiversityAnalyzer()
    assert analyzer is not None
    assert analyzer.DIMENSION_WEIGHTS["topic"] == 0.25


@pytest.mark.asyncio
async def test_diversity_empty():
    analyzer = DatasetDiversityAnalyzer()
    metrics = await analyzer.analyze([])
    assert isinstance(metrics, DiversityMetrics)
    assert metrics.overall_diversity >= 0.0


@pytest.mark.asyncio
async def test_diversity_with_samples():
    analyzer = DatasetDiversityAnalyzer()
    samples = [
        {"instruction": "What is AI?", "response": "AI is artificial intelligence.", "source_url": "https://example.com/ai"},
        {"instruction": "Explain Python.", "response": "Python is a programming language.", "source_url": "https://example.com/python"},
        {"instruction": "Describe SQL.", "response": "SQL is for databases.", "source_url": "https://example.com/sql"},
    ]
    metrics = await analyzer.analyze(samples)
    assert 0.0 <= metrics.topic_diversity <= 1.0
    assert 0.0 <= metrics.source_diversity <= 1.0
    assert 0.0 <= metrics.instruction_diversity <= 1.0
    assert 0.0 <= metrics.response_diversity <= 1.0
    assert 0.0 <= metrics.domain_diversity <= 1.0


@pytest.mark.asyncio
async def test_diversity_single_sample():
    analyzer = DatasetDiversityAnalyzer()
    samples = [
        {"instruction": "What is AI?", "response": "AI is artificial intelligence."},
    ]
    metrics = await analyzer.analyze(samples)
    assert metrics.overall_diversity >= 0.0


def test_shannon_entropy():
    analyzer = DatasetDiversityAnalyzer()
    # Uniform distribution -> high entropy
    uniform = {"a": 10, "b": 10, "c": 10}
    entropy = analyzer._shannon_entropy(uniform)
    assert entropy > 0.0
    assert entropy <= 1.585  # log2(3) ≈ 1.585


def test_diversity_rating():
    analyzer = DatasetDiversityAnalyzer()
    assert analyzer._rating(0.9) == "very_high"
    assert analyzer._rating(0.7) == "high"
    assert analyzer._rating(0.5) == "medium"
    assert analyzer._rating(0.3) == "low"
    assert analyzer._rating(0.1) == "very_low"


def test_diversity_metrics_dataclass():
    dm = DiversityMetrics(
        topic_diversity=0.8,
        source_diversity=0.7,
        instruction_diversity=0.9,
        response_diversity=0.6,
        domain_diversity=0.75,
        overall_diversity=0.76,
        entropies={"topic": 1.2, "source": 0.9},
        distributions={"topic": {"ai": 5, "ml": 3}},
    )
    assert dm.overall_diversity == 0.76
    assert dm.entropies["topic"] == 1.2