"""
Agent Registry - Plugin-based agent discovery and management
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from agents.base import (
    Agent,
    AgentConfig,
    AgentType,
    AgentCapability,
    AgentFactory,
    AgentState,
)


@dataclass
class AgentRegistration:
    """Registration information for an agent."""
    agent_type: AgentType
    name: str
    description: str
    capabilities: List[AgentCapability]
    factory_func: Callable[[AgentConfig], Agent]
    version: str = "1.0.0"
    author: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    """Registry for managing agent types and instances."""

    _instance = None
    _registrations: Dict[AgentType, AgentRegistration] = {}
    _instances: Dict[str, Agent] = {}
    _type_instances: Dict[AgentType, List[str]] = {}

    @classmethod
    def get_instance(cls) -> 'AgentRegistry':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def register(
        cls,
        agent_type: AgentType,
        name: str,
        description: str,
        capabilities: List[AgentCapability],
        factory_func: Callable[[AgentConfig], Agent],
        version: str = "1.0.0",
        author: str = "",
        metadata: Dict[str, Any] = None
    ) -> None:
        """Register an agent type."""
        registration = AgentRegistration(
            agent_type=agent_type,
            name=name,
            description=description,
            capabilities=capabilities,
            factory_func=factory_func,
            version=version,
            author=author,
            metadata=metadata or {},
        )

        cls._registrations[agent_type] = registration
        AgentFactory.register(agent_type, factory_func.__self__.__class__ if hasattr(factory_func, '__self__') else factory_func)

    @classmethod
    def create_agent(
        cls,
        agent_type: AgentType,
        config: Optional[AgentConfig] = None
    ) -> Optional[Agent]:
        """Create a new agent instance."""
        registration = cls._registrations.get(agent_type)
        if not registration:
            return None

        if config is None:
            config = AgentConfig(
                agent_id=str(uuid.uuid4()),
                agent_type=agent_type,
                name=registration.name,
            )

        agent = registration.factory_func(config)
        cls._instances[agent.agent_id] = agent

        if agent_type not in cls._type_instances:
            cls._type_instances[agent_type] = []
        cls._type_instances[agent_type].append(agent.agent_id)

        return agent

    @classmethod
    def get_agent(cls, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return cls._instances.get(agent_id)

    @classmethod
    def remove_agent(cls, agent_id: str) -> bool:
        """Remove an agent instance."""
        if agent_id in cls._instances:
            agent = cls._instances[agent_id]
            agent_type = agent.agent_type

            cls._instances.pop(agent_id)

            if agent_type in cls._type_instances:
                try:
                    cls._type_instances[agent_type].remove(agent_id)
                except ValueError:
                    pass

            return True
        return False

    @classmethod
    def list_agents(cls, agent_type: Optional[AgentType] = None) -> List[Agent]:
        """List all agent instances."""
        if agent_type:
            agent_ids = cls._type_instances.get(agent_type, [])
            return [cls._instances.get(aid) for aid in agent_ids if aid in cls._instances]
        return list(cls._instances.values())

    @classmethod
    def list_registrations(cls) -> List[AgentRegistration]:
        """List all registered agent types."""
        return list(cls._registrations.values())

    @classmethod
    def find_by_capability(cls, capability: AgentCapability) -> List[AgentRegistration]:
        """Find agents with a specific capability."""
        return [
            reg for reg in cls._registrations.values()
            if capability in reg.capabilities
        ]

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_registrations": len(cls._registrations),
            "total_instances": len(cls._instances),
            "instances_by_type": {
                at.value: len(ids) for at, ids in cls._type_instances.items()
            },
            "capabilities": {
                cap.value: len([
                    reg for reg in cls._registrations.values()
                    if cap in reg.capabilities
                ])
                for cap in AgentCapability
            },
        }


def register_agent(
    agent_type: AgentType,
    name: str,
    description: str,
    capabilities: List[AgentCapability],
    version: str = "1.0.0",
    author: str = "",
    metadata: Dict[str, Any] = None
) -> Callable:
    """Decorator to register an agent."""
    def decorator(cls):
        def factory(config: AgentConfig) -> Agent:
            return cls(config)

        AgentRegistry.register(
            agent_type=agent_type,
            name=name,
            description=description,
            capabilities=capabilities,
            factory_func=factory,
            version=version,
            author=author,
            metadata=metadata,
        )

        return cls

    return decorator


# Auto-register base agents
class AgentRegistryInitializer:
    """Initialize default agent registrations."""

    @staticmethod
    def initialize():
        """Register all default agent types."""
        from agents.agents.research import ResearchAgent
        from agents.agents.planning import StrategyAgent
        from agents.agents.discovery import SourceDiscoveryAgent, SearchOptimizationAgent
        from agents.agents.extraction import WebCrawlerAgent, OCRAgent, MultimodalAgent
        from agents.agents.quality import QualityEvaluationAgent, DedupAgent, ToxicityAgent
        from agents.agents.synthetic import SyntheticGenerationAgent, ValidationAgent
        from agents.agents.optimization import FineTuningAgent, CurriculumAgent
        from agents.agents.infrastructure import (
            GPUSchedulingAgent,
            StorageOptimizationAgent,
            DistributionAgent,
        )

        # Register each agent type
        AgentRegistry.register(
            AgentType.RESEARCH,
            "Research Agent",
            "Understands dataset objectives, analyzes domain requirements",
            [AgentCapability.REASONING, AgentCapability.TEXT_PROCESSING],
            lambda c: ResearchAgent(c),
        )

        AgentRegistry.register(
            AgentType.STRATEGY,
            "Strategy Agent",
            "Designs execution plans, optimizes workflows",
            [AgentCapability.REASONING],
            lambda c: StrategyAgent(c),
        )

        AgentRegistry.register(
            AgentType.SOURCE_DISCOVERY,
            "Source Discovery Agent",
            "Finds relevant data sources across the web",
            [AgentCapability.TEXT_PROCESSING, AgentCapability.WEB_SCRAPING],
            lambda c: SourceDiscoveryAgent(c),
        )

        AgentRegistry.register(
            AgentType.SEARCH_OPTIMIZATION,
            "Search Optimization Agent",
            "Optimizes search queries for better retrieval",
            [AgentCapability.TEXT_PROCESSING],
            lambda c: SearchOptimizationAgent(c),
        )

        AgentRegistry.register(
            AgentType.WEB_CRAWLER,
            "Web Crawler Agent",
            "Handles large-scale web crawling and scraping",
            [AgentCapability.WEB_SCRAPING],
            lambda c: WebCrawlerAgent(c),
        )

        AgentRegistry.register(
            AgentType.OCR,
            "OCR Agent",
            "Processes scanned documents and images",
            [AgentCapability.OCR, AgentCapability.MULTIMODAL],
            lambda c: OCRAgent(c),
        )

        AgentRegistry.register(
            AgentType.MULTIMODAL,
            "Multimodal Extraction Agent",
            "Extracts text, tables, images from documents",
            [AgentCapability.MULTIMODAL, AgentCapability.TEXT_PROCESSING],
            lambda c: MultimodalAgent(c),
        )

        AgentRegistry.register(
            AgentType.QUALITY_EVALUATION,
            "Quality Evaluation Agent",
            "Scores dataset quality across multiple dimensions",
            [AgentCapability.QUALITY_SCORING, AgentCapability.GPU_EXECUTION],
            lambda c: QualityEvaluationAgent(c),
        )

        AgentRegistry.register(
            AgentType.DEDUPLICATION,
            "Deduplication Agent",
            "Detects and removes duplicate content",
            [AgentCapability.DEDUPLICATION],
            lambda c: DedupAgent(c),
        )

        AgentRegistry.register(
            AgentType.TOXICITY,
            "Toxicity Agent",
            "Detects unsafe and harmful content",
            [AgentCapability.TOXICITY],
            lambda c: ToxicityAgent(c),
        )

        AgentRegistry.register(
            AgentType.SYNTHETIC_GENERATION,
            "Synthetic Generation Agent",
            "Generates synthetic training data",
            [AgentCapability.SYNTHETIC_GENERATION, AgentCapability.GPU_EXECUTION],
            lambda c: SyntheticGenerationAgent(c),
        )

        AgentRegistry.register(
            AgentType.VALIDATION,
            "Validation Agent",
            "Verifies synthetic data quality",
            [AgentCapability.VALIDATION, AgentCapability.GPU_EXECUTION],
            lambda c: ValidationAgent(c),
        )

        AgentRegistry.register(
            AgentType.FINE_TUNING,
            "Fine-Tuning Agent",
            "Optimizes datasets for fine-tuning",
            [AgentCapability.TEXT_PROCESSING],
            lambda c: FineTuningAgent(c),
        )

        AgentRegistry.register(
            AgentType.CURRICULUM,
            "Curriculum Agent",
            "Creates learning progression for datasets",
            [AgentCapability.TEXT_PROCESSING],
            lambda c: CurriculumAgent(c),
        )

        AgentRegistry.register(
            AgentType.GPU_SCHEDULING,
            "GPU Scheduling Agent",
            "Optimizes GPU allocation and scheduling",
            [AgentCapability.GPU_EXECUTION],
            lambda c: GPUSchedulingAgent(c),
        )

        AgentRegistry.register(
            AgentType.STORAGE,
            "Storage Optimization Agent",
            "Handles dataset sharding and compression",
            [AgentCapability.DISTRIBUTION],
            lambda c: StorageOptimizationAgent(c),
        )

        AgentRegistry.register(
            AgentType.DISTRIBUTION,
            "Distribution Agent",
            "Manages dataset delivery to various platforms",
            [AgentCapability.DISTRIBUTION],
            lambda c: DistributionAgent(c),
        )