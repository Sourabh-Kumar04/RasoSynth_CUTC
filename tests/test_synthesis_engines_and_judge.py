"""Tests for the 7 standalone synthesis engines integration and real LLM judge in FilteringPipeline."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock

from pipeline.construction import ConstructionPipeline, DatasetType, ConstructedSample
from pipeline.filtering import FilteringPipeline
from core.intent import UserIntent
from api.server import RateLimiter, _validate_security_config
from core.config import get_settings


class DummySample:
    def __init__(self, content: str, quality_score: float = 0.85):
        self.content = content
        self.quality_score = quality_score
        self.metadata = {"source_url": "https://example.com/statute"}


@pytest.fixture
def mock_intent():
    return UserIntent(
        raw_input="Generate a comprehensive dataset for Indian taxation and GST statutory compliance.",
        domain="taxation",
        primary_task="statutory_analysis",
        modality="text",
        anti_domains=["astrology", "gaming"],
        key_entities=["CGST Act", "ITC", "GSTR-3B"],
        specialized_queries=["Section 16 CGST Act input tax credit eligibility"],
        constraints=["accuracy", "grounding"],
        output_format="jsonl",
        confidence=0.95,
    )


@pytest.mark.asyncio
async def test_synthesis_engine_cot(mock_intent):
    config = {
        "dataset_type": "sft",
        "synthesis_mode": "cot",
        "language": "en",
    }
    pipeline = ConstructionPipeline(router=None, config=config)
    assert pipeline.synthesis_mode == "cot"

    sample = DummySample(
        "Under Section 16(2) of the CGST Act, no registered person shall be entitled to input tax credit "
        "unless they possess a tax invoice, have received the goods, the tax has been paid to the Government, "
        "and they have furnished the return under Section 39."
    )

    items = []
    async for item in pipeline.construct(sample, mock_intent):
        items.append(item)

    assert len(items) > 0
    first = items[0]
    assert isinstance(first, ConstructedSample)
    assert first.metadata.get("type") == "cot_reasoning"
    assert "<thought>" in first.response
    assert "</thought>" in first.response


@pytest.mark.asyncio
async def test_synthesis_engine_socratic(mock_intent):
    config = {
        "dataset_type": "sft",
        "synthesis_mode": "socratic",
    }
    pipeline = ConstructionPipeline(router=None, config=config)
    assert pipeline.synthesis_mode == "socratic"

    sample = DummySample(
        "Section 17(5)(h) restricts ITC on goods lost, stolen, destroyed, written off or disposed of by way of gift or free samples. "
        "However, promotional schemes such as 'Buy One Get One Free' represent composite supplies rather than free gifts."
    )

    items = []
    async for item in pipeline.construct(sample, mock_intent):
        items.append(item)

    assert len(items) > 0
    first = items[0]
    assert first.metadata.get("type") == "dialectic_debate"
    assert "Adjudicated Consensus Verdict" in first.response


@pytest.mark.asyncio
async def test_synthesis_engine_preference(mock_intent):
    config = {
        "dataset_type": "sft",
        "synthesis_mode": "simpo",
    }
    pipeline = ConstructionPipeline(router=None, config=config)
    assert pipeline.synthesis_mode == "simpo"

    sample = DummySample(
        "Section 50(1) prescribes interest on delayed payment of GST at 18% per annum calculated on the net cash liability."
    )

    items = []
    async for item in pipeline.construct(sample, mock_intent):
        items.append(item)

    assert len(items) > 0
    first = items[0]
    assert "rejected" in first.metadata
    assert "target_margin" in first.metadata


@pytest.mark.asyncio
async def test_synthesis_engine_multi_turn(mock_intent):
    config = {
        "dataset_type": "sft",
        "synthesis_mode": "multi_turn",
    }
    pipeline = ConstructionPipeline(router=None, config=config)
    assert pipeline.synthesis_mode == "multi_turn"

    sample = DummySample(
        "Section 29 allows the proper officer to cancel GST registration.\n"
        "Circumstances include non-filing of returns for consecutive tax periods.\n"
        "A show cause notice must be issued before cancellation.\n"
        "The taxpayer has 30 days to apply for revocation of cancellation under Section 30."
    )

    items = []
    async for item in pipeline.construct(sample, mock_intent):
        items.append(item)

    assert len(items) > 0
    first = items[0]
    assert first.conversation is not None
    assert len(first.conversation) >= 2


@pytest.mark.asyncio
async def test_synthesis_engine_tool_calling(mock_intent):
    config = {
        "dataset_type": "sft",
        "synthesis_mode": "tool_calling",
    }
    pipeline = ConstructionPipeline(router=None, config=config)
    assert pipeline.synthesis_mode == "tool_calling"

    sample = DummySample(
        "Taxpayer with GSTIN 27AAPFU0939F1ZV has pending refund claims under ARN AA2703250012345."
    )

    items = []
    async for item in pipeline.construct(sample, mock_intent):
        items.append(item)

    assert len(items) > 0
    first = items[0]
    assert first.metadata.get("type") == "tool_calling"
    assert "check_itc_balance" in first.response


@pytest.mark.asyncio
async def test_synthesis_engine_contrastive(mock_intent):
    config = {
        "dataset_type": "sft",
        "synthesis_mode": "contrastive",
    }
    pipeline = ConstructionPipeline(router=None, config=config)
    assert pipeline.synthesis_mode == "contrastive"

    sample = DummySample(
        "The standard GST rate on specified services is 18%, and filing GSTR-1 by the 11th of every month is mandatory."
    )

    items = []
    async for item in pipeline.construct(sample, mock_intent):
        items.append(item)

    assert len(items) > 0
    first = items[0]
    assert first.metadata.get("type") == "contrastive_critique"
    assert "perturbed_negative" in first.metadata
    assert "critique" in first.metadata


@pytest.mark.asyncio
async def test_synthesis_engine_rag(mock_intent):
    config = {
        "dataset_type": "sft",
        "synthesis_mode": "rag",
    }
    pipeline = ConstructionPipeline(router=None, config=config)
    assert pipeline.synthesis_mode == "rag"

    sample = DummySample(
        "Section 73 deals with non-fraud tax demands, with a normal limitation period of 3 years from the annual return due date."
    )

    items = []
    async for item in pipeline.construct(sample, mock_intent):
        items.append(item)

    assert len(items) > 0
    first = items[0]
    assert first.metadata.get("type") == "rag"
    assert "[1]" in first.response


@pytest.mark.asyncio
async def test_filtering_llm_judge_pure_evaluation_and_semantic_cosine():
    # Test without router: returns neutral score
    filter_pipe = FilteringPipeline(router=None, config={"dataset_type": "sft"})
    score, issues = await filter_pipe._llm_judge_quality(
        "Section 16(2) provides four cumulative conditions for ITC eligibility: tax invoice, receipt of goods, payment of tax, and return filing.",
        "taxation"
    )
    assert score == 0.5
    assert issues == []

    # Test with router mock: verifies real LLMJudge is called and returned directly
    mock_router = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"accuracy": 0.95, "reasoning": 0.90, "completeness": 0.85, "consistency": 1.0, "helpfulness": 0.90, "grounding": 0.95, "explanation": "High quality statutory analysis."}'
    mock_router.route = AsyncMock(return_value=mock_response)

    mock_emb_resp = MagicMock()
    mock_emb_resp.embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    mock_router.embed = AsyncMock(return_value=mock_emb_resp)

    filter_pipe_with_llm = FilteringPipeline(router=mock_router, config={"dataset_type": "sft"})
    assert filter_pipe_with_llm.llm_judge is not None

    score_llm, issues_llm = await filter_pipe_with_llm._llm_judge_quality(
        "Section 16(2) provides four cumulative conditions for ITC eligibility: tax invoice, receipt of goods, payment of tax, and return filing.",
        "taxation"
    )
    assert 0.85 <= score_llm <= 1.0

    # Test real neural cosine similarity in _semantic_quality
    sem_score, sem_issues = await filter_pipe_with_llm._semantic_quality(
        "Input tax credit rules under Section 16", "taxation"
    )
    assert 0.8 <= sem_score <= 1.0


@pytest.mark.asyncio
async def test_multi_worker_rate_limiter_redis_fallback():
    limiter = RateLimiter(max_requests=2, window_seconds=60, prefix="test")

    # In-memory check
    assert limiter.check("127.0.0.1") is True
    assert limiter.check("127.0.0.1") is True
    assert limiter.check("127.0.0.1") is False

    # Mock Redis client
    mock_redis = MagicMock()
    mock_redis.incr = AsyncMock(side_effect=[1, 2, 3])
    mock_redis.expire = AsyncMock(return_value=True)

    redis_limiter = RateLimiter(max_requests=2, window_seconds=60, prefix="test_redis")
    assert await redis_limiter.check_async("192.168.1.1", redis_client=mock_redis) is True
    assert await redis_limiter.check_async("192.168.1.1", redis_client=mock_redis) is True
    assert await redis_limiter.check_async("192.168.1.1", redis_client=mock_redis) is False


def test_production_jwt_secret_validation(monkeypatch):
    monkeypatch.setenv("AI_DATASET_ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "rasosynthtune-sovereign-production-jwt-token-secret-key-32b-secure")
    monkeypatch.delenv("SPACE_ID", raising=False)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError) as exc_info:
        _validate_security_config()
    assert "CRITICAL SECURITY ERROR" in str(exc_info.value)


def test_hf_space_jwt_secret_autogen(monkeypatch, tmp_path):
    monkeypatch.setenv("SPACE_ID", "Sourabh-Kumar04/RasoSynthTune")
    monkeypatch.setenv("JWT_SECRET", "rasosynthtune-sovereign-production-jwt-token-secret-key-32b-secure")
    monkeypatch.delenv("AI_DATASET_ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    get_settings.cache_clear()

    _validate_security_config()
    autogen_secret = os.getenv("JWT_SECRET")
    assert autogen_secret != "rasosynthtune-sovereign-production-jwt-token-secret-key-32b-secure"
    assert len(autogen_secret) >= 32
    assert (tmp_path / ".rasosynth_jwt_secret").exists()


@pytest.mark.asyncio
async def test_agent_memory_persistence(tmp_path):
    from agents.memory import AgentMemoryManager, MemoryType
    storage_dir = str(tmp_path / "agent_memory")

    # Manager 1: Store memory
    manager1 = AgentMemoryManager(agent_id="agent_tax_researcher", storage_dir=storage_dir)
    entry = await manager1.store(
        content="Section 16(2) requires invoice, possession of goods, and tax payment.",
        memory_type=MemoryType.EPISODIC,
        tags=["taxation", "itc"],
        importance=0.9
    )
    assert entry.entry_id in manager1.vector_memory._entries

    # Manager 2: Recreate manager for same agent_id and ensure memory persisted to disk
    manager2 = AgentMemoryManager(agent_id="agent_tax_researcher", storage_dir=storage_dir)
    assert entry.entry_id in manager2.vector_memory._entries
    loaded_entry = manager2.vector_memory._entries[entry.entry_id]
    assert loaded_entry.content == entry.content
    assert "itc" in loaded_entry.tags


@pytest.mark.asyncio
async def test_provider_router_semantic_cache():
    from core.provider_router import ProviderRouter, TaskType
    from providers.core_lib.base import LLMResponse

    call_count = 0
    async def fake_generate(request, **kwargs):
        nonlocal call_count
        call_count += 1
        return LLMResponse(content=f"Response {call_count} for: {request.input[:30]}", tokens_used=50)

    mock_p = MagicMock()
    mock_p.generate = AsyncMock(side_effect=fake_generate)

    router = ProviderRouter(config={"mock": {"api_key": "dummy"}})
    router._providers["mock"] = mock_p
    router._provider_configs["mock"] = {"api_key": "dummy"}
    router.config.provider_priority = ["mock"]

    # Call 1: Misses cache, generates
    res1 = await router.route(TaskType.TEXT_GENERATION, "Explain Section 16(2) GST invoice condition")
    assert res1 is not None
    assert call_count == 1

    # Call 2: Exact prompt hit
    res2 = await router.route(TaskType.TEXT_GENERATION, "Explain Section 16(2) GST invoice condition")
    assert res2 == res1
    assert call_count == 1  # No extra generation call

