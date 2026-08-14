"""
Tests for the Hallucination Detector module.
"""
import pytest

from pipeline.hallucination_detector import HallucinationDetector, HallucinationResult


@pytest.fixture
def detector():
    return HallucinationDetector()


@pytest.fixture
def sample_source():
    return (
        "Transformer models, introduced by Vaswani et al. in 2017, "
        "revolutionized natural language processing. The key innovation "
        "is the self-attention mechanism, which allows the model to weigh "
        "the importance of different words in a sequence. BERT, developed "
        "by Google in 2018, uses a bidirectional training approach. "
        "GPT-3, released by OpenAI in 2020, has 175 billion parameters."
    )


@pytest.mark.asyncio
async def test_evaluate_well_grounded(detector, sample_source):
    """Response closely grounded in source should get low risk."""
    response = (
        "Transformer models were introduced by Vaswani et al. in 2017 "
        "and use a self-attention mechanism. BERT was developed by Google "
        "in 2018 with bidirectional training."
    )
    result = await detector.evaluate(
        instruction="Explain transformer models",
        response=response,
        source_text=sample_source,
    )
    assert isinstance(result, HallucinationResult)
    assert result.source_grounding_score > 0.5
    assert result.hallucination_risk_score < 0.5
    assert result.risk_level in ("low", "medium")


@pytest.mark.asyncio
async def test_evaluate_hallucinated(detector, sample_source):
    """Response with claims not in source should get high risk."""
    response = (
        "Transformer models were invented by Alan Turing in 1950 "
        "and have 1 trillion parameters. They use recursive neural "
        "networks instead of attention mechanisms."
    )
    result = await detector.evaluate(
        instruction="Explain transformer models",
        response=response,
        source_text=sample_source,
    )
    assert result.hallucination_risk_score > 0.5
    assert result.risk_level in ("high", "critical")
    assert len(result.flagged_patterns) > 0


@pytest.mark.asyncio
async def test_evaluate_empty_source(detector):
    """Empty source should return zero grounding."""
    result = await detector.evaluate(
        instruction="Test", response="Some response", source_text=""
    )
    assert result.source_grounding_score == 0.0


@pytest.mark.asyncio
async def test_evaluate_empty_response(detector, sample_source):
    """Empty response should return zero grounding."""
    result = await detector.evaluate(
        instruction="Test", response="", source_text=sample_source
    )
    assert result.source_grounding_score == 0.0


@pytest.mark.asyncio
async def test_citation_matching(detector):
    """Citations that match source content should score well."""
    source = "Smith et al. (2020) showed that LLMs exhibit emergent abilities."
    response = "According to Smith et al., LLMs show emergent abilities [1]."
    result = await detector.evaluate(
        instruction="Summarize findings",
        response=response,
        source_text=source,
    )
    assert result.citation_match_score >= 0.5


@pytest.mark.asyncio
async def test_entity_extraction(detector):
    """Entity extraction should find named entities."""
    text = "Google and Microsoft collaborated with Stanford University on Project Quantum."
    entities = detector._extract_entities(text)
    assert len(entities) > 0
    assert "Google" in entities or "Microsoft" in entities


@pytest.mark.asyncio
async def test_claim_extraction(detector):
    """Claim extraction should find declarative factual sentences."""
    text = "The Earth orbits the Sun. This process takes 365 days. Machine learning is popular."
    claims = detector._extract_claims(text)
    assert len(claims) > 0
    assert any("Earth orbits" in c for c in claims)


@pytest.mark.asyncio
async def test_citation_extraction_bracket(detector):
    """Bracket-style citations should be extracted."""
    text = "Attention is all you need [1]. Later work [2,3] extended this."
    citations = detector._extract_citations(text)
    types = [c["type"] for c in citations]
    assert "bracket" in types


@pytest.mark.asyncio
async def test_citation_extraction_author_year(detector):
    """Author-year citations should be extracted."""
    text = "Recent work (Vaswani, 2017) showed promising results."
    citations = detector._extract_citations(text)
    types = [c["type"] for c in citations]
    assert "author_year" in types


@pytest.mark.asyncio
async def test_absolute_language_flagging(detector):
    """Absolute language should be flagged."""
    source = "Some LLMs can perform translation tasks."
    response = "LLMs can always perform translation tasks perfectly for everyone."
    risk, flagged = await detector._compute_hallucination_risk(
        0.5, 0.5, response, source
    )
    flagged_types = [f.split(":")[0] for f in flagged]
    assert "absolute_language" in flagged_types


@pytest.mark.asyncio
async def test_entity_mismatch_flagging(detector):
    """Entities not in source should be flagged."""
    source = "The model achieved good results on the test set."
    response = "Google BERT achieved 99% accuracy on ImageNet."
    risk, flagged = await detector._compute_hallucination_risk(
        0.5, 0.5, response, source
    )
    flagged_types = [f.split(":")[0] for f in flagged]
    assert "entities_not_in_source" in flagged_types


@pytest.mark.asyncio
async def test_longest_common_substring(detector):
    """LCS ratio should be between 0 and 1."""
    ratio = detector._longest_common_substring_ratio("hello world", "hello there")
    assert 0 < ratio <= 1.0

    ratio_zero = detector._longest_common_substring_ratio("abc", "xyz")
    assert ratio_zero == 0.0

    ratio_empty = detector._longest_common_substring_ratio("", "test")
    assert ratio_empty == 0.0


@pytest.mark.asyncio
async def test_batch_evaluation(detector, sample_source):
    """Batch evaluation should return results for all samples."""
    samples = [
        {
            "instruction": "Explain transformers",
            "response": "Transformers use self-attention.",
            "source_text": sample_source,
        },
        {
            "instruction": "Explain BERT",
            "response": "BERT was developed by Google in 2018.",
            "source_text": sample_source,
        },
    ]
    results = await detector.evaluate_batch(samples)
    assert len(results) == 2
    assert all(isinstance(r, HallucinationResult) for r in results)


@pytest.mark.asyncio
async def test_risk_levels(detector, sample_source):
    """All risk levels should be reachable under appropriate conditions."""
    # Very high grounding -> low risk
    result_low = await detector.evaluate(
        instruction="Test",
        response="Vaswani et al. introduced transformers in 2017.",
        source_text=sample_source,
    )

    # Very low grounding -> high risk
    result_high = await detector.evaluate(
        instruction="Test",
        response="Aliens built pyramids using unknown technology.",
        source_text=sample_source,
    )

    assert result_low.risk_level in ("low", "medium")
    assert result_high.risk_level in ("high", "critical")


@pytest.mark.asyncio
async def test_numerical_claim_flagging(detector):
    """Unsourced numerical claims should be flagged."""
    source = "The model performed well."
    response = "The model achieved 99.9% accuracy with 3x speed improvement."
    risk, flagged = await detector._compute_hallucination_risk(
        0.5, 0.5, response, source
    )
    flagged_types = [f.split(":")[0] for f in flagged]
    assert "unsupported_numerical_claims" in flagged_types


@pytest.mark.asyncio
async def test_date_flagging(detector):
    """Dates not in source should be flagged."""
    source = "The system was released."
    response = "The system was released on January 15, 2025."
    risk, flagged = await detector._compute_hallucination_risk(
        0.5, 0.5, response, source
    )
    assert any("unsupported_dates" in f for f in flagged)


@pytest.mark.asyncio
async def test_short_source_penalty(detector):
    """Very short sources should trigger conservative scoring."""
    result = await detector.evaluate(
        instruction="Test",
        response="A long detailed response about something.",
        source_text="Short source.",
    )
    assert result.details["grounding"].get("short_source_warning", False)


@pytest.mark.asyncio
async def test_config_custom_weights():
    """Custom weights should be respected."""
    detector = HallucinationDetector(config={
        "grounding_weight": 0.8,
        "citation_weight": 0.2,
        "min_grounding_threshold": 0.5,
    })
    assert detector.grounding_weight == 0.8
    assert detector.citation_weight == 0.2
    assert detector.min_grounding_threshold == 0.5