"""Tests for the deduplication engine."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.deduplication import DeduplicationEngine, DuplicateResult


@pytest.mark.asyncio
async def test_dedup_initialization():
    engine = DeduplicationEngine()
    assert engine is not None
    assert engine.fuzzy_threshold == 0.85
    assert engine.embedding_threshold == 0.92


@pytest.mark.asyncio
async def test_exact_dedup():
    engine = DeduplicationEngine()
    text = "The quick brown fox jumps over the lazy dog."

    result1 = await engine.check(text, "sample1")
    assert not result1.is_duplicate
    assert result1.duplicate_score == 0.0

    await engine.add(text, "sample1")

    result2 = await engine.check(text, "sample2")
    assert result2.is_duplicate
    assert result2.match_type == "exact"
    assert result2.duplicate_score == 1.0


@pytest.mark.asyncio
async def test_check_and_add():
    engine = DeduplicationEngine()

    result1 = await engine.check_and_add("First unique text", "id1")
    assert not result1.is_duplicate

    result2 = await engine.check_and_add("First unique text", "id2")
    assert result2.is_duplicate
    assert result2.match_type == "exact"


@pytest.mark.asyncio
async def test_nonexact_not_detected():
    engine = DeduplicationEngine()

    await engine.add("This is a very long and detailed text about artificial intelligence.", "id1")
    result = await engine.check("This is a very different text about machine learning.", "id2")
    # Should NOT be detected as exact duplicate
    assert result.match_type != "exact"


@pytest.mark.asyncio
async def test_get_stats():
    engine = DeduplicationEngine()
    stats = engine.get_stats()
    assert "exact_matches" in stats
    assert "total_checks" in stats
    assert stats["total_checks"] == 0

    await engine.check("test", "id1")
    stats = engine.get_stats()
    assert stats["total_checks"] == 1


def test_duplicate_result_dataclass():
    dr = DuplicateResult(
        is_duplicate=True,
        duplicate_score=0.95,
        match_type="fuzzy",
        matched_id="original123",
        similarity=0.95,
        cluster_id="cluster1",
    )
    assert dr.is_duplicate
    assert dr.match_type == "fuzzy"
    assert dr.cluster_id == "cluster1"


@pytest.mark.asyncio
async def test_minhash_linear_permutation_fuzzy_matching():
    """Verify Broder linear permutation MinHash detects near duplicates with estimated Jaccard."""
    engine = DeduplicationEngine(config={"fuzzy_threshold": 0.80, "num_permutations": 128})
    t1 = "Under Section 16(2) of the CGST Act 2017, a registered person can claim ITC only if they hold a valid tax invoice or debit note."
    t2 = "Under Section 16(2) of the CGST Act 2017, a registered person can claim ITC only if they hold a valid tax invoice."
    t3 = "Photosynthesis is the biological process by which green plants convert sunlight into biochemical energy."

    await engine.add(t1, "sample-1")
    res_fuzzy = await engine.check(t2, "sample-2")
    res_diff = await engine.check(t3, "sample-3")

    assert res_fuzzy.is_duplicate is True
    assert res_fuzzy.match_type == "fuzzy"
    assert res_fuzzy.matched_id == "sample-1"
    assert res_fuzzy.similarity >= 0.80

    assert res_diff.is_duplicate is False
    assert res_diff.match_type == "none"
