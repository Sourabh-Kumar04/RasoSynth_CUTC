"""
Multi-Agent Base Infrastructure

Core types, agent base class, and communication protocols.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Dict, List, Callable
from datetime import datetime
import uuid
import json


class AgentType(Enum):
    """Types of specialized agents."""
    # Planning
    RESEARCH = "research"
    STRATEGY = "strategy"

    # Discovery
    SOURCE_DISCOVERY = "source_discovery"
    SEARCH_OPTIMIZATION = "search_optimization"
    WEB_INTELLIGENCE = "web_intelligence"

    # Extraction
    WEB_CRAWLER = "web_crawler"
    OCR = "ocr"
    MULTIMODAL = "multimodal"

    # Language & Semantic
    LANGUAGE_DETECTION = "language_detection"
    SEMANTIC_RECONSTRUCTION = "semantic_reconstruction"
    KNOWLEDGE_GRAPH = "knowledge_graph"

    # Quality
    QUALITY_EVALUATION = "quality_evaluation"
    DEDUPLICATION = "deduplication"
    TOXICITY = "toxicity"

    # Synthetic
    SYNTHETIC_GENERATION = "synthetic_generation"
    VALIDATION = "validation"
    CONSENSUS = "consensus"

    # Optimization
    FINE_TUNING = "fine_tuning"
    CURRICULUM = "curriculum"

    # Infrastructure
    GPU_SCHEDULING = "gpu_scheduling"
    STORAGE = "storage"
    DISTRIBUTION = "distribution"


class AgentCapability(Enum):
    """Capabilities of agents."""
    TEXT_PROCESSING = "text_processing"
    WEB_SCRAPING = "web_scraping"
    OCR = "ocr"
    QUALITY_SCORING = "quality_scoring"
    DEDUPLICATION = "deduplication"
    SYNTHETIC_GENERATION = "synthetic_generation"
    VALIDATION = "validation"
    DISTRIBUTION = "distribution"
    GPU_EXECUTION = "gpu_execution"
    MULTIMODAL = "multimodal"
    MULTILINGUAL = "multilingual"
    REASONING = "reasoning"


class MessageType(Enum):
    """Types of inter-agent messages."""
    TASK = "task"
    RESULT = "result"
    ERROR = "error"
    QUERY = "query"
    RESPONSE = "response"
    EVENT = "event"
    HEARTBEAT = "heartbeat"
    COORDINATION = "coordination"


class AgentState(Enum):
    """Agent execution states."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    agent_id: str = ""
    agent_type: AgentType = AgentType.RESEARCH
    name: str = ""
    description: str = ""
    capabilities: List[AgentCapability] = field(default_factory=list)
    # Execution settings
    timeout_seconds: float = 300.0
    max_retries: int = 3
    priority: int = 5
    # Resource requirements
    gpu_required: bool = False
    vram_required_gb: float = 0.0
    memory_required_gb: float = 1.0
    # Model settings
    model_preference: str = "auto"
    temperature: float = 0.7
    max_tokens: int = 4096
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMessage:
    """Message between agents."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    receiver: str = ""
    message_type: MessageType = MessageType.TASK
    content: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    priority: int = 5

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
            "correlation_id": self.correlation_id,
            "priority": self.priority,
        }


@dataclass
class TaskResult:
    """Result of agent task execution."""
    task_id: str
    agent_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    confidence: float = 0.0
    execution_time_ms: float = 0.0
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class AgentContext:
    """Context shared between agents."""
    job_id: str
    dataset_id: str
    domain: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict] = field(default_factory=list)
    extracted_data: List[Dict] = field(default_factory=list)
    filtered_data: List[Dict] = field(default_factory=list)
    constructed_samples: List[Dict] = field(default_factory=list)
    quality_scores: Dict[str, float] = field(default_factory=dict)
    lineage: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Agent(ABC):
    """Base class for all agents."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent_id = config.agent_id or str(uuid.uuid4())
        self.agent_type = config.agent_type
        self.name = config.name or config.agent_type.value
        self.state = AgentState.IDLE
        self._message_queue: List[AgentMessage] = []
        self._memory: Dict[str, Any] = {}
        self._children: List[str] = []
        self._parent: Optional[str] = None
        self._execution_history: List[TaskResult] = []
        self._capabilities = config.capabilities

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the agent."""
        pass

    @abstractmethod
    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute the agent's specialized task."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup agent resources."""
        pass

    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process an incoming message."""
        self._message_queue.append(message)
        return None

    async def send_message(
        self,
        receiver: str,
        content: Any,
        message_type: MessageType = MessageType.TASK,
        priority: int = 5
    ) -> AgentMessage:
        """Send a message to another agent."""
        message = AgentMessage(
            sender=self.agent_id,
            receiver=receiver,
            message_type=message_type,
            content=content,
            priority=priority,
        )
        return message

    def update_state(self, state: AgentState) -> None:
        """Update agent state."""
        self.state = state

    def get_capabilities(self) -> List[AgentCapability]:
        """Get agent capabilities."""
        return self._capabilities

    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has a capability."""
        return capability in self._capabilities

    async def spawn_child(
        self,
        agent_type: AgentType,
        config: Optional[AgentConfig] = None
    ) -> str:
        """Spawn a child agent."""
        child_id = str(uuid.uuid4())
        self._children.append(child_id)
        return child_id

    async def terminate_children(self) -> None:
        """Terminate all child agents."""
        self._children.clear()

    def record_result(self, result: TaskResult) -> None:
        """Record execution result."""
        self._execution_history.append(result)

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        total = len(self._execution_history)
        successful = sum(1 for r in self._execution_history if r.success)
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "state": self.state.value,
            "total_executions": total,
            "successful": successful,
            "success_rate": successful / max(total, 1),
            "children_count": len(self._children),
        }

    def to_dict(self) -> dict:
        """Serialize agent to dict."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "name": self.name,
            "state": self.state.value,
            "capabilities": [c.value for c in self._capabilities],
            "children": self._children,
            "parent": self._parent,
            "config": {
                "timeout_seconds": self.config.timeout_seconds,
                "max_retries": self.config.max_retries,
                "gpu_required": self.config.gpu_required,
            },
        }


class AgentFactory:
    """Factory for creating agent instances."""

    _agent_classes: Dict[AgentType, type] = {}

    @classmethod
    def register(cls, agent_type: AgentType, agent_class: type) -> None:
        """Register an agent class."""
        cls._agent_classes[agent_type] = agent_class

    @classmethod
    def create(cls, config: AgentConfig) -> Agent:
        """Create an agent instance."""
        agent_class = cls._agent_classes.get(config.agent_type)
        if not agent_class:
            raise ValueError(f"No agent class registered for {config.agent_type}")

        return agent_class(config)

    @classmethod
    def list_types(cls) -> List[AgentType]:
        """List all registered agent types."""
        return list(cls._agent_classes.keys())