"""
Multi-Agent Graph Architecture for Specialized Dataset Engineering

A graph-based multi-agent orchestration system where specialized AI agents
collaborate dynamically across distributed workflows.

Architecture:
- Agent Graph: Dynamic execution graph with agent nodes
- Agent Registry: Plugin-based agent discovery and management
- Communication: Structured protocols for inter-agent messaging
- Memory: Shared persistent context across agents
- Orchestration: Intelligent routing and coordination
"""

from agents.base import (
    Agent,
    AgentConfig,
    AgentCapability,
    AgentType,
    AgentMessage,
    MessageType,
    AgentState,
)
from agents.registry import AgentRegistry, register_agent
from agents.graph import (
    AgentGraph,
    GraphNode,
    GraphEdge,
    ExecutionPlan,
    GraphExecutor,
)
from agents.communication import (
    AgentBus,
    MessageQueue,
    EventSystem,
    SharedMemory,
)
from agents.coordination import (
    Supervisor,
    HierarchicalPlanner,
    TaskDelegator,
    ConsensusResolver,
)
from agents.memory import (
    VectorMemory,
    EpisodicMemory,
    GraphMemory,
    KnowledgeBase,
)
from agents.orchestrator import (
    MultiAgentOrchestrator,
    AgentScheduler,
    LoadBalancer,
)
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

__all__ = [
    # Base
    "Agent",
    "AgentConfig",
    "AgentCapability",
    "AgentType",
    "AgentMessage",
    "MessageType",
    "AgentState",

    # Registry
    "AgentRegistry",
    "register_agent",

    # Graph
    "AgentGraph",
    "GraphNode",
    "GraphEdge",
    "ExecutionPlan",
    "GraphExecutor",

    # Communication
    "AgentBus",
    "MessageQueue",
    "EventSystem",
    "SharedMemory",

    # Coordination
    "Supervisor",
    "HierarchicalPlanner",
    "TaskDelegator",
    "ConsensusResolver",

    # Memory
    "VectorMemory",
    "EpisodicMemory",
    "GraphMemory",
    "KnowledgeBase",

    # Orchestrator
    "MultiAgentOrchestrator",
    "AgentScheduler",
    "LoadBalancer",

    # Specialized Agents
    "ResearchAgent",
    "StrategyAgent",
    "SourceDiscoveryAgent",
    "SearchOptimizationAgent",
    "WebCrawlerAgent",
    "OCRAgent",
    "MultimodalAgent",
    "QualityEvaluationAgent",
    "DedupAgent",
    "ToxicityAgent",
    "SyntheticGenerationAgent",
    "ValidationAgent",
    "FineTuningAgent",
    "CurriculumAgent",
    "GPUSchedulingAgent",
    "StorageOptimizationAgent",
    "DistributionAgent",
]