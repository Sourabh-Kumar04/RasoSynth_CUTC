"""Tests for code translation dataset relevance filtering."""
import pytest
from pipeline.filtering import FilteringPipeline


@pytest.fixture
def relevance_pipeline():
    """Create a FilteringPipeline instance configured for relevance testing."""
    # Use a minimal config that doesn't interfere with relevance scoring
    config = {
        "quality_threshold": 0.0,       # Disable quality filtering
        "statistical_threshold": 0.0,
        "semantic_threshold": 0.0,
        "reasoning_threshold": 0.0,
        "grounding_threshold": 0.0,
        "toxicity_threshold": 1.0,      # Never fail due to toxicity
        "min_length": 0,
        "max_length": 1000000,          # Very high length limit
    }
    # Use None router to avoid external calls and use simple term matching
    return FilteringPipeline(router=None, config=config)


def test_code_translation_relevance_rejected_datasets(relevance_pipeline):
    """Test that irrelevant datasets for code translation query are rejected."""
    rejected_samples = [
        "A collection of JavaScript one-liners for code golfing challenges.",
        "JavaScript interview questions and answers for frontend developers.",
        "Techniques for obfuscating JavaScript code to prevent reverse engineering.",
        "Source code for a Python-to-JavaScript transpiler compiler.",
        "Benchmark suite comparing the performance of Python and JavaScript interpreters.",
        "Dataset of French to English translation pairs for language learners.",
        "Medical dictionary containing translations of criminal law terminology.",
        "Satellite imagery dataset showing habitat maps of national parks.",
        "Glossary of mathematical symbols used in physics textbooks.",
        "Collection of cooking recipes translated from Italian to Spanish."
    ]

    domain = "Python to JavaScript translation"

    for sample in rejected_samples:
        score = relevance_pipeline._score_relevance(sample, domain)
        # Expect low relevance score (< 0.5) for irrelevant datasets
        assert score < 0.5, f"Expected low relevance (<0.5) for: {sample[:50]}... (got {score})"


def test_code_translation_relevance_accepted_datasets(relevance_pipeline):
    """Test that relevant datasets for code translation query are accepted."""
    accepted_samples = [
        "Paired dataset of equivalent Python and JavaScript functions for common tasks.",
        "Tutorial showing side-by-side implementations of algorithms in Python and JavaScript.",
        "Documentation of Python idioms and their equivalent JavaScript approaches.",
        "Human-validated dataset of JavaScript functions translated from Python equivalents.",
        "Collection of competitive programming solutions implemented in both Python and JavaScript.",
        "Dataset of Python functions with their JavaScript translations for machine translation.",
        "Parallel corpus of Python and JavaScript code snippets from open-source projects.",
        "Evaluation benchmark for code translation models including HumanEval-X and MultiPL-E.",
        "Dataset containing TransCoder model outputs for Python-JavaScript translation.",
        "Lost in Translation paper dataset for evaluating code translation quality."
    ]

    domain = "Python to JavaScript translation"

    for sample in accepted_samples:
        score = relevance_pipeline._score_relevance(sample, domain)
        # Expect high relevance score (>= 0.5) for relevant datasets
        assert score >= 0.5, f"Expected high relevance (>=0.5) for: {sample[:50]}... (got {score})"


def test_code_translation_relevance_threshold_boundary(relevance_pipeline):
    """Test edge cases around the relevance threshold."""
    # These samples should be around the boundary - adjust as needed based on actual scoring
    boundary_samples = [
        ("Python JavaScript function pairs", 0.5),  # Exact match of domain terms
        ("Python to JavaScript translation guide", 0.6),  # Contains all domain terms
        ("JavaScript functions", 0.25),  # Missing Python and translation
        ("Python code examples", 0.25),  # Missing JavaScript and translation
    ]

    domain = "Python to JavaScript translation"

    for sample, expected_min_score in boundary_samples:
        score = relevance_pipeline._score_relevance(sample, domain)
        assert score >= expected_min_score, f"Sample '{sample}' scored {score}, expected at least {expected_min_score}"