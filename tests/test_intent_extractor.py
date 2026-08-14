"""Test intent extraction functionality."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.intent import IntentExtractionError, UserIntent
from core.intent_extractor import extract_intent


# ---- Unit tests (mock provider router) ----
@pytest.mark.asyncio
async def test_extract_intent_valid_response():
    """Test that a valid JSON response is parsed correctly."""
    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "primary_task": "code translation",
        "domain": "software engineering",
        "modality": "code",
        "anti_domains": ["linguistics", "legal"],
        "key_entities": ["CodeNet", "AVATAR"],
        "specialized_queries": ["CodeNet dataset", "Python to C parallel corpus"],
        "constraints": ["no GPL-3 code"],
        "output_format": "jsonl",
        "confidence": 0.9
    })
    # Set the route method to return the mock_response when awaited
    mock_provider.route = AsyncMock(return_value=mock_response)
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None  # cache miss

    intent = await extract_intent("code translation Python to C", mock_provider, redis_mock)

    assert isinstance(intent, UserIntent)
    assert intent.primary_task == "code translation"
    assert intent.domain == "software engineering"
    assert intent.modality == "code"
    assert intent.anti_domains == ["linguistics", "legal"]
    assert intent.key_entities == ["CodeNet", "AVATAR"]
    assert intent.specialized_queries == ["CodeNet dataset", "Python to C parallel corpus"]
    assert intent.constraints == ["no GPL-3 code"]  # IntentExtractionError: Intent JSON missing required fields: {'constraints'}
    assert intent.output_format == "jsonl"
    assert intent.confidence == 0.9
    assert intent.raw_input == "code translation Python to C"
    assert redis_mock.get.called
    assert redis_mock.setex.called


@pytest.mark.asyncio
async def test_extract_intent_markdown_fences():
    """Test that JSON wrapped in markdown fences is stripped before parsing."""
    mock_provider = AsyncMock()
    inner_json = json.dumps({
        "primary_task": "sentiment analysis",
        "domain": "NLP",
        "modality": "text",
        "anti_domains": ["finance", "chemistry"],
        "key_entities": [],
        "specialized_queries": ["sentiment analysis of tweets dataset"],
        "constraints": [],
        "output_format": "jsonl",
        "confidence": 0.8
    })
    mock_response = MagicMock()
    mock_response.content = (
        "```json\n"
        + inner_json
        + "\n```"
    )
    mock_provider.route = AsyncMock(return_value=mock_response)
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    intent = await extract_intent("sentiment analysis of tweets", mock_provider, redis_mock)

    assert intent.primary_task == "sentiment analysis"
    assert intent.domain == "NLP"
    assert intent.anti_domains == ["finance", "chemistry"]


@pytest.mark.asyncio
async def test_extract_intent_low_confidence():
    """Test that confidence below threshold raises IntentExtractionError."""
    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "primary_task": "translation",
        "domain": "NLP",
        "modality": "text",
        "anti_domains": [],
        "key_entities": [],
        "specialized_queries": ["some query"],
        "constraints": [],
        "output_format": "jsonl",
        "confidence": 0.5  # below threshold
    })
    mock_provider.route = AsyncMock(return_value=mock_response)
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    with pytest.raises(IntentExtractionError, match="Low confidence"):
        await extract_intent("some input", mock_provider, redis_mock)


@pytest.mark.asyncio
async def test_extract_intent_missing_field():
    """Test that missing required fields raises IntentExtractionError."""
    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "primary_task": "test",
        # domain missing
        "modality": "text",
        "anti_domains": [],
        "key_entities": [],
        "specialized_queries": ["q"],
        "constraints": [],
        "output_format": "jsonl",
        "confidence": 0.9
    })
    mock_provider.route = AsyncMock(return_value=mock_response)
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    with pytest.raises(IntentExtractionError, match="Intent JSON missing required fields"):
        await extract_intent("some input", mock_provider, redis_mock)


@pytest.mark.asyncio
async def test_extract_intent_malformed_json():
    """Test that malformed JSON raises IntentExtractionError."""
    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = "not json {"
    mock_provider.route = AsyncMock(return_value=mock_response)
    redis_mock = AsyncMock()
    redis_mok = None  # not used but for placeholder
    redis_mock.get.return_value = None

    with pytest.raises(IntentExtractionError, match="LLM returned non-JSON response"):
        await extract_intent("some input", mock_provider, redis_mock)


@pytest.mark.asyncio
async def test_extract_intent_provider_exception():
    """Test that provider exception propagates as IntentExtractionError."""
    mock_provider = AsyncMock()
    mock_route = AsyncMock(side_effect=Exception("provider down"))
    mock_provider.route = mock_route
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    with pytest.raises(IntentExtractionError, match="LLM call failed"):
        await extract_intent("some input", mock_provider, redis_mock)


@pytest.mark.asyncio
async def test_extract_intent_cache_hit():
    """Test that cache hit returns cached intent without calling LLM."""
    mock_provider = AsyncMock()
    redis_mock = AsyncMock()
    cached_data = {
        "primary_task": "code translation",
        "domain": "software engineering",
        "modality": "code",
        "anti_domains": ["linguistic"],
        "key_entities": ["CodeNet"],
        "specialized_queries": ["CodeNet dataset"],
        "constraints": [],
        "output_format": "jsonl",
        "confidence": 0.95
    }
    redis_mock.get.return_value = json.dumps(cached_data)

    intent = await extract_intent("any input", mock_provider, redis_mock)

    assert intent.primary_task == "code translation"
    assert intent.domain == "software engineering"
    assert intent.modality == "code"
    assert intent.anti_domains == ["linguistic"]
    assert intent.key_entities == ["CodeNet"]
    assert intent.specialized_queries == ["CodeNet dataset"]  # must be list
    assert intent.constraints == []
    assert intent.output_format == "jsonl"
    assert intent.confidence == 0.95
    assert intent.raw_input == "any input"
    # Provider should NOT have been called
    mock_provider.route.assert_not_awaited()
    # Cache should have been read
    redis_mock.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_intent_cache_write():
    """Test that a fresh intent is written to cache."""
    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "primary_task": "test",
        "domain": "test",
        "modality": "text",
        "anti_domains": [],
        "key_entities": [],
        "specialized_queries": ["q"],
        "constraints": [],
        "output_format": "jsonl",
        "confidence": 0.9
    })
    mock_provider.route = AsyncMock(return_value=mock_response)
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None  # cache miss

    intent = await extract_intent("test input", mock_provider, redis_mock)

    assert intent.primary_task == "test"
    # Cache write should have been called
    assert redis_mock.setex.called


@pytest.mark.asyncio
async def test_extract_intent_anti_domains_processing():
    """Test that anti_domains are lower-cased, trimmed, deduplicated, capped."""
    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "primary_task": "test",
        "domain": "test",
        "modality": "text",
        "anti_domains": ["  Linguistics ", "LEGAL", "Linguistics", "extra"] * 10,  # duplicates, mixed case, extra spaces
        "key_entities": [],
        "specialized_queries": ["q1", "q2"] * 10,
        "constraints": [],
        "output_format": "jsonl",
        "confidence": 0.9
    })
    mock_provider.route = AsyncMock(return_value=mock_response)
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    intent = await extract_intent("test", mock_provider, redis_mock)

    # Should be lower-cased, trimmed, deduplicated, capped at MAX_ANTI_DOMAINS (15)
    assert intent.anti_domains == ["linguistics", "legal", "extra"]


@pytest.mark.asyncio
async def test_extract_intent_queries_processing():
    """Test that queries are stripped, length‑filtered, deduplicated, and anti‑domain guarded."""
    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "primary_task": "test",
        "domain": "test",
        "modality": "text",
        "anti_domains": ["forbidden"],
        "key_entities": [],
        "specialized_queries": [
            "ok query",
            "   another ok   ",
            "this query contains forbidden term inside",
            "a" * 201,  # too long
            "ok query",  # duplicate
        ],
        "constraints": [],
        "output_format": "jsonl",
        "confidence": 0.9
    })
    mock_provider.route = AsyncMock(return_value=mock_response)
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    intent = await extract_intent("test", mock_provider, redis_mock)

    # Should be stripped, length‑filtered, deduplicated, and anti‑domain term removed
    assert intent.specialized_queries == ["ok query", "another ok"]