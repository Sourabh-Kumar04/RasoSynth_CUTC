"""
Distributed Execution Base Infrastructure

Core types and configuration for the distributed pipeline.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, List, Dict
from datetime import datetime
import json
import hashlib


class NodeStatus(Enum):
    """Worker node status."""
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    FAILED = "failed"
    DRAINING = "draining"


class ResourceType(Enum):
    """Types of compute resources."""
    CPU = "cpu"
    GPU = "gpu"
    MEMORY = "memory"
    VRAM = "vram"
    DISK = "disk"
    NETWORK = "network"


@dataclass
class ResourceRequirement:
    """Resource requirements for a task."""
    cpu_cores: int = 1
    gpu_count: int = 0
    gpu_memory_gb: float = 0.0
    ram_gb: float = 1.0
    vram_gb: float = 0.0
    disk_gb: float = 0.0
    estimated_duration_seconds: float = 60.0
    priority: int = 5  # 1-10, higher is more urgent


@dataclass
class GPUInfo:
    """Information about a GPU."""
    gpu_id: int
    name: str
    total_memory_gb: float
    available_memory_gb: float
    utilization_percent: float
    temperature_celsius: float
    power_usage_watts: float
    compute_capability: str
    mig_enabled: bool = False


@dataclass
class WorkerNode:
    """Represents a worker node in the distributed cluster."""
    node_id: str
    hostname: str
    ip_address: str
    status: NodeStatus = NodeStatus.ACTIVE
    # Resources
    cpu_cores: int = 0
    gpu_count: int = 0
    total_memory_gb: float = 0.0
    available_memory_gb: float = 0.0
    gpus: List[GPUInfo] = field(default_factory=list)
    # Metrics
    current_load: float = 0.0
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    # Capabilities
    capabilities: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class DistributedConfig:
    """Configuration for distributed execution."""
    # Cluster settings
    cluster_name: str = "rasosynthtune"
    ray_head_address: str = "auto"
    ray_object_store_memory_gb: float = 0.5
    # Worker settings
    min_workers: int = 1
    max_workers: int = 100
    worker_timeout_seconds: float = 300.0
    # GPU settings
    gpu_selection_strategy: str = "memory"  # memory, utilization, round_robin
    max_concurrent_gpu_tasks: int = 4
    enable_mig: bool = False
    # Queue settings
    queue_backend: str = "redis"  # redis, rabbitmq, kafka
    redis_url: str = "redis://localhost:6379/0"
    queue_prefix: str = "dataset:"
    # Execution settings
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    checkpoint_interval_seconds: float = 60.0
    # Resource allocation
    default_resource_requirement: ResourceRequirement = field(default_factory=ResourceRequirement)
    # Scaling
    autoscaling_enabled: bool = True
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.2
    # Monitoring
    metrics_port: int = 9090
    enable_profiling: bool = False


@dataclass
class ExecutionResult:
    """Result of a distributed execution."""
    task_id: str = ""
    success: bool = False
    output: Optional[Any] = None
    error: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    gpu_used: bool = False
    gpu_time_ms: float = 0.0
    cpu_time_ms: float = 0.0
    memory_peak_gb: float = 0.0
    checkpointed: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class TaskSpec:
    """Specification for a distributed task."""
    task_id: str = ""
    task_type: str = ""
    function_name: str = ""
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    resources: ResourceRequirement = field(default_factory=ResourceRequirement)
    dependencies: List[str] = field(default_factory=list)
    priority: int = 5
    retry_policy: dict = field(default_factory=lambda: {
        "max_retries": 3,
        "backoff": "exponential",
        "max_backoff": 300,
    })
    checkpoint_enabled: bool = True
    timeout_seconds: float = 3600.0
    metadata: dict = field(default_factory=dict)


@dataclass
class PipelineState:
    """State of a pipeline execution."""
    pipeline_id: str = ""
    job_id: str = ""
    status: str = "pending"
    current_stage: str = ""
    progress_percent: float = 0.0
    stages_completed: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    checkpoints: dict = field(default_factory=dict)


class CheckpointData:
    """Checkpoint data for task recovery."""

    def __init__(self, task_id: str, stage: str):
        self.task_id = task_id
        self.stage = stage
        self.timestamp = datetime.utcnow()
        self.progress = 0.0
        self.data = {}
        self.dependencies_resolved = []

    def to_json(self) -> str:
        return json.dumps({
            "task_id": self.task_id,
            "stage": self.stage,
            "timestamp": self.timestamp.isoformat(),
            "progress": self.progress,
            "data": self.data,
            "dependencies_resolved": self.dependencies_resolved,
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'CheckpointData':
        data = json.loads(json_str)
        checkpoint = cls(data["task_id"], data["stage"])
        checkpoint.timestamp = datetime.fromisoformat(data["timestamp"])
        checkpoint.progress = data["progress"]
        checkpoint.data = data["data"]
        checkpoint.dependencies_resolved = data["dependencies_resolved"]
        return checkpoint


class DistributedState:
    """Distributed state management."""

    def __init__(self, config: DistributedConfig):
        self.config = config
        self._nodes: dict[str, WorkerNode] = {}
        self._tasks: dict[str, TaskSpec] = {}
        self._results: dict[str, ExecutionResult] = {}
        self._checkpoints: dict[str, CheckpointData] = {}

    def register_node(self, node: WorkerNode) -> None:
        """Register a worker node."""
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[WorkerNode]:
        """Get a worker node."""
        return self._nodes.get(node_id)

    def get_available_nodes(self) -> list[WorkerNode]:
        """Get all available nodes."""
        return [n for n in self._nodes.values() if n.status == NodeStatus.ACTIVE]

    def get_gpu_nodes(self) -> list[WorkerNode]:
        """Get nodes with GPU."""
        return [n for n in self._nodes.values() if n.gpu_count > 0]

    def submit_task(self, task: TaskSpec) -> str:
        """Submit a task for execution."""
        self._tasks[task.task_id] = task
        return task.task_id

    def get_task(self, task_id: str) -> Optional[TaskSpec]:
        """Get task specification."""
        return self._tasks.get(task_id)

    def store_result(self, result: ExecutionResult) -> None:
        """Store execution result."""
        self._results[result.task_id] = result

    def get_result(self, task_id: str) -> Optional[ExecutionResult]:
        """Get execution result."""
        return self._results.get(task_id)

    def save_checkpoint(self, checkpoint: CheckpointData) -> None:
        """Save a checkpoint."""
        key = f"{checkpoint.task_id}_{checkpoint.stage}"
        self._checkpoints[key] = checkpoint

    def load_checkpoint(self, task_id: str, stage: str) -> Optional[CheckpointData]:
        """Load a checkpoint."""
        key = f"{task_id}_{stage}"
        return self._checkpoints.get(key)

    def get_cluster_summary(self) -> dict:
        """Get cluster summary."""
        total_cpus = sum(n.cpu_cores for n in self._nodes.values())
        total_gpus = sum(n.gpu_count for n in self._nodes.values())

        return {
            "total_nodes": len(self._nodes),
            "active_nodes": len(self.get_available_nodes()),
            "gpu_nodes": len(self.get_gpu_nodes()),
            "total_cpus": total_cpus,
            "total_gpus": total_gpus,
            "total_tasks": len(self._tasks),
            "completed_tasks": len([r for r in self._results.values() if r.success]),
            "failed_tasks": len([r for r in self._results.values() if not r.success]),
        }