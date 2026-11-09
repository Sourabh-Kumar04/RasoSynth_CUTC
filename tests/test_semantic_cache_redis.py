import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from core.cache.semantic import SemanticCacheManager


@pytest.mark.asyncio
async def test_semantic_cache_redis_write_through():
    mock_redis = MagicMock()
    mock_redis.set = MagicMock(return_value=True)
    mock_redis.get = MagicMock(return_value=None)
    mock_redis.delete = MagicMock(return_value=True)

    cache = SemanticCacheManager(redis_client=mock_redis)

    await cache.store(
        key="query-1",
        query="What are symptoms of type 2 diabetes?",
        response="Frequent urination, excessive thirst, and unexplained weight loss.",
    )

    # In-memory hit
    res = await cache.get("query-1")
    assert res == "Frequent urination, excessive thirst, and unexplained weight loss."
    assert mock_redis.set.called


@pytest.mark.asyncio
async def test_semantic_cache_redis_fallback():
    mock_redis = MagicMock()
    stored_payload = json.dumps({
        "key": "query-remote",
        "query": "Explain quantum entanglement",
        "response": "Particles remain connected such that actions performed on one affect the other.",
        "embedding": [0.1] * 384,
        "semantic_hash": "hash123",
        "created_at": "2026-11-09T16:00:00+00:00",
        "metadata": {},
        "partial_content": None,
    })
    mock_redis.get = MagicMock(return_value=stored_payload)

    cache = SemanticCacheManager(redis_client=mock_redis)

    # Not in local cache, fetches from Redis
    res = await cache.get("query-remote")
    assert res == "Particles remain connected such that actions performed on one affect the other."
    assert "query-remote" in cache._cache


@pytest.mark.asyncio
async def test_semantic_cache_redis_invalidate():
    mock_redis = MagicMock()
    mock_redis.set = MagicMock(return_value=True)
    mock_redis.delete = MagicMock(return_value=True)

    cache = SemanticCacheManager(redis_client=mock_redis)
    await cache.store("k1", "q1", "r1")
    await cache.invalidate("k1")

    assert "k1" not in cache._cache
    assert mock_redis.delete.called
