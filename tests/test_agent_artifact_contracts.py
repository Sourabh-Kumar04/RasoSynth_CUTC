import pytest

from agents.agents.discovery import SourceDiscoveryAgent
from agents.agents.extraction import WebCrawlerAgent
from agents.agents.quality import DedupAgent, QualityEvaluationAgent
from agents.agents.synthetic import ConsensusAgent, SyntheticGenerationAgent
from agents.base import AgentConfig, AgentContext, AgentType


@pytest.fixture
def context():
    return AgentContext(job_id="job", dataset_id="dataset")


@pytest.mark.asyncio
async def test_discovery_ranks_real_candidates_without_fabricating_sources(context):
    agent = SourceDiscoveryAgent(AgentConfig(agent_type=AgentType.SOURCE_DISCOVERY))
    await agent.initialize()

    result = await agent.execute({
        "query": "climate data",
        "sources": [
            {
                "url": "https://example.org/report",
                "title": "Climate data report",
                "content": "Verified climate data evidence.",
                "license": "CC-BY-4.0",
            },
            {"url": "not-a-url", "content": "must be ignored"},
        ],
    }, context)

    assert result.success
    assert result.output["total_discovered"] == 1
    assert result.output["sources"][0]["url"] == "https://example.org/report"


@pytest.mark.asyncio
async def test_crawler_agent_only_adapts_supplied_page_artifacts(context):
    agent = WebCrawlerAgent(AgentConfig(agent_type=AgentType.WEB_CRAWLER))
    await agent.initialize()

    result = await agent.execute({"pages": [{
        "url": "https://example.org/report",
        "title": "Report",
        "text": "Actual extracted content.",
    }]}, context)

    assert result.success
    page = result.output["extracted_content"][0]
    assert page["url"] == "https://example.org/report"
    assert page["text"] == "Actual extracted content."
    assert "adapted_at" in page["metadata"]


@pytest.mark.asyncio
async def test_quality_contracts_are_explainable_and_do_not_invent_reviews(context):
    quality = QualityEvaluationAgent(AgentConfig(agent_type=AgentType.QUALITY_EVALUATION))
    dedup = DedupAgent(AgentConfig(agent_type=AgentType.DEDUPLICATION))
    await quality.initialize()
    await dedup.initialize()

    scored = await quality.execute({"samples": [{
        "instruction": "x" * 300,
        "response": "A supported answer.",
        "metadata": {"provenance": {"source_url": "https://example.org/source"}},
    }]}, context)
    duplicates = await dedup.execute({"samples": [{"input": "same"}, {"input": "same"}]}, context)

    assert scored.output["individual_scores"][0]["scores"]["accuracy"]["score"] == 0.9
    assert duplicates.output["duplicate_count"] == 1


@pytest.mark.asyncio
async def test_synthesis_and_consensus_require_real_provider_artifacts(context):
    synthesis = SyntheticGenerationAgent(AgentConfig(agent_type=AgentType.SYNTHETIC_GENERATION))
    consensus = ConsensusAgent(AgentConfig(agent_type=AgentType.CONSENSUS))
    await synthesis.initialize()
    await consensus.initialize()

    generated = await synthesis.execute({"count": 2}, context)
    reviewed = await consensus.execute({"samples": [{"review_votes": [1, 1, 0]}], "num_models": 3}, context)

    assert generated.output["count"] == 0
    assert reviewed.output["agreement_rate"] == 1.0
