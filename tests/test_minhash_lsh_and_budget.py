"""
Unit tests for MinHash LSH Sub-Linear Deduplication and Tenant Budget Limiting.
"""

import pytest
import time
from pipeline.deduplication import DeduplicationEngine
from core.provider_router import TenantBudgetLimiter


@pytest.mark.asyncio
async def test_minhash_lsh_deduplication():
    engine = DeduplicationEngine(config={"fuzzy_threshold": 0.75, "num_permutations": 64, "num_bands": 8})

    text_original = "The quick brown fox jumps over the lazy sleeping dog in the sunny park."
    text_near_duplicate = "The quick brown fox jumps over the lazy sleeping dog in the quiet park."
    text_unrelated = "Artificial intelligence transforms scalable synthesis workflows."

    # Add original text
    dup1 = await engine.check_and_add(text_original, "sample-1")
    assert dup1.is_duplicate is False

    # Check near-duplicate: should be detected as fuzzy duplicate via LSH index
    dup2 = await engine.check(text_near_duplicate)
    assert dup2.is_duplicate is True
    assert dup2.match_type == "fuzzy"
    assert dup2.matched_id == "sample-1"
    assert dup2.similarity >= 0.75

    # Check unrelated text: should not match
    dup3 = await engine.check(text_unrelated)
    assert dup3.is_duplicate is False


def test_tenant_budget_and_rate_limiter():
    limiter = TenantBudgetLimiter(default_budget_usd=10.0, default_rpm=5)
    tenant_id = "tenant-research-01"

    # Send 5 requests (within rate limit)
    for _ in range(5):
        ok, msg = limiter.check_and_record_request(tenant_id, estimated_cost=0.01)
        assert ok is True

    # 6th request within same minute should hit rate limit (5 req/min)
    ok_limit, msg_limit = limiter.check_and_record_request(tenant_id, estimated_cost=0.01)
    assert ok_limit is False
    assert "Rate limit exceeded" in msg_limit

    # Record token usage reaching $9.95
    limiter.record_tokens_and_cost(tenant_id, tokens=500000, cost_usd=9.95)

    # Next expensive request ($0.10) exceeds $10.00 cap
    # Reset timestamps to test budget check specifically
    limiter.get_or_create(tenant_id).request_timestamps.clear()
    ok_budget, msg_budget = limiter.check_and_record_request(tenant_id, estimated_cost=0.10)
    assert ok_budget is False
    assert "Monthly budget limit" in msg_budget
