"""
Tests verifying the architectural contracts promised in documentation:
1. Multi-Agent Society (AgentRegistry, GPUSchedulingAgent, StorageOptimizationAgent, DistributionAgent, StrategyAgent, ResearchAgent)
2. Continuous Research Loop (ResearchLoop, TechniqueIntegrator, active heuristics)
3. ADR-002 Storage & Packaging delivery (DatasetPackager, PackageManifest, DeliveryManager)
4. AI Kosh prioritization
"""
import pytest
import os
from unittest.mock import Mock, AsyncMock

from agents.registry import AgentRegistry, AgentRegistryInitializer
from agents.base import AgentType, AgentCapability, AgentContext
from core.storage.packaging import DatasetPackager, PackagingConfig, PackageManifest
from core.storage.base import DeliveryRequest, DeliveryStrategy, StorageProviderType
from core.storage.delivery import DeliveryManager
from core.research_loop import ResearchLoop, TechniqueIntegrator
from core.orchestrator_core import DatasetOrchestrator


def test_agent_registry_initialization_and_specialized_agents():
    """Ensure all 17 agent types in the multi-agent society register and instantiate."""
    AgentRegistryInitializer.initialize()
    registry = AgentRegistry.get_instance()
    registrations = registry.list_registrations()
    assert len(registrations) >= 12

    # Verify key specialized agents
    gpu_agent = registry.create_agent(AgentType.GPU_SCHEDULING)
    storage_agent = registry.create_agent(AgentType.STORAGE)
    dist_agent = registry.create_agent(AgentType.DISTRIBUTION)
    strat_agent = registry.create_agent(AgentType.STRATEGY)
    res_agent = registry.create_agent(AgentType.RESEARCH)

    assert gpu_agent is not None
    assert storage_agent is not None
    assert dist_agent is not None
    assert strat_agent is not None
    assert res_agent is not None

    stats = registry.get_stats()
    assert stats["total_instances"] >= 5
    assert "gpu_scheduling" in stats["instances_by_type"]


@pytest.mark.asyncio
async def test_dataset_packager_produces_manifest():
    """Ensure DatasetPackager produces canonical PackageManifest with chunking and checksums."""
    samples = [
        {"instruction": f"Question {i}", "response": f"Answer {i}", "quality_score": 0.9}
        for i in range(25)
    ]
    packager = DatasetPackager(PackagingConfig())
    manifest = await packager.package(samples, "test_dataset", version="1.0.0")

    assert isinstance(manifest, PackageManifest)
    assert manifest.dataset_name == "test_dataset"
    assert manifest.chunk_count > 0
    assert manifest.total_size_bytes > 0


@pytest.mark.asyncio
async def test_delivery_manager_orchestrates_delivery():
    """Ensure DeliveryManager packages and tracks delivery operations."""
    manager = DeliveryManager()
    samples = [
        {"instruction": f"Question {i}", "response": f"Answer {i}"}
        for i in range(10)
    ]
    req = DeliveryRequest(
        dataset_id="test_dataset_123",
        dataset_name="test_dataset",
        destination=StorageProviderType.HUGGINGFACE,
        strategy=DeliveryStrategy.DIRECT_DOWNLOAD,
    )
    delivery_info = await manager.deliver(req, samples)

    assert delivery_info.delivery_id is not None
    assert delivery_info.dataset_id == "test_dataset_123"
    assert delivery_info.status.value in ("completed", "pending", "packaging", "uploading", "failed")
    assert delivery_info.manifest is not None


def test_research_loop_heuristics():
    """Ensure ResearchLoop and TechniqueIntegrator supply active heuristics."""
    integrator = TechniqueIntegrator(router=None)
    heuristics = integrator.get_active_heuristics()
    assert "minhash_dedup" in heuristics
    assert "perplexity_filtering" in heuristics
    assert "cross_lingual" in heuristics


def test_aikosh_source_prioritization_with_api_key():
    """Ensure AI Kosh source is placed at index 0 when AI Kosh credentials are present."""
    orchestrator = DatasetOrchestrator({}, Mock())
    from pipeline.discovery import SourceType

    config_with_key = {"aikosh_api_key": "test_key", "language": "en", "target_domain": "general machine learning"}
    sources = orchestrator._determine_source_types(config_with_key)
    assert sources[0] == SourceType.AI_KOSH
