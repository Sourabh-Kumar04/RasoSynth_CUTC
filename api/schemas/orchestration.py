"""
Orchestration Schemas

Schemas for distributed execution, task graphs,
provider routing, and GPU allocation.
"""

from typing import Dict, List, Optional, Any, Set, Union, Literal, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, computed_field, model_validator
from api.schemas.base import BaseSchema, Constraint, RetryPolicy
from api.schemas.workflow import WorkflowStep, StepResourceAllocation


class TaskStatus(str, Enum):
    """Status of a task node."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(str, Enum):
    """Task execution priority."""
    LOW = 1
    NORMAL = 50
    HIGH = 80
    URGENT = 95
    CRITICAL = 100


class TaskNode(BaseSchema):
    """Individual task node in execution graph."""
    task_id: str
    name: str

    workflow_step_id: Optional[str] = None

    task_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)

    priority: TaskPriority = TaskPriority.NORMAL

    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)

    assigned_worker: Optional[str] = None
    assigned_provider: Optional[str] = None
    assigned_model: Optional[str] = None

    resources: StepResourceAllocation = Field(default_factory=StepResourceAllocation)

    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)

    timeout_seconds: Optional[int] = None

    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0

    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0

    metrics: Dict[str, Any] = Field(default_factory=dict)

    def can_execute(self, completed_tasks: Set[str]) -> bool:
        """Check if task can be executed based on dependencies."""
        return all(dep in completed_tasks for dep in self.dependencies)


class TaskGraph(BaseSchema):
    """Complete task graph for distributed execution."""
    graph_id: str
    workflow_id: Optional[str] = None

    nodes: Dict[str, TaskNode] = Field(default_factory=dict)
    edges: List[tuple[str, str]] = Field(default_factory=list)

    execution_mode: Literal["parallel", "sequential", "pipelined", "hybrid"] = "parallel"

    max_concurrent_tasks: int = 10
    max_retries: int = 3

    enable_fault_tolerance: bool = True
    enable_checkpoints: bool = True

    estimated_duration_seconds: int = 0
    estimated_cost_usd: float = 0.0

    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_ready_tasks(self, completed_tasks: Set[str]) -> List[TaskNode]:
        """Get tasks ready for execution."""
        ready = []
        for task_id, task in self.nodes.items():
            if task.status != TaskStatus.PENDING:
                continue
            if task.can_execute(completed_tasks):
                ready.append(task)
        return sorted(ready, key=lambda t: t.priority.value, reverse=True)

    def get_execution_order(self) -> List[List[str]]:
        """Get topological order for execution."""
        in_degree = {task_id: len(task.dependencies) for task_id, task in self.nodes.items()}
        ready = [task_id for task_id, deg in in_degree.items() if deg == 0]
        result = []

        while ready:
            current_level = ready.copy()
            result.append(current_level)
            ready = []

            for task_id in current_level:
                for dependent in self.nodes[task_id].dependents:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0 and self.nodes[dependent].status == TaskStatus.PENDING:
                        ready.append(dependent)

        return result

    def add_node(self, node: TaskNode) -> None:
        """Add a task node."""
        self.nodes[node.task_id] = node
        for dep in node.dependencies:
            if dep in self.nodes:
                self.nodes[dep].dependents.append(node.task_id)

    def remove_node(self, task_id: str) -> bool:
        """Remove a task node."""
        if task_id not in self.nodes:
            return False

        node = self.nodes[task_id]
        for dep in node.dependencies:
            if dep in self.nodes and task_id in self.nodes[dep].dependents:
                self.nodes[dep].dependents.remove(task_id)

        for dependent in node.dependents:
            if dependent in self.nodes and task_id in self.nodes[dependent].dependencies:
                self.nodes[dependent].dependencies.remove(task_id)

        del self.nodes[task_id]
        self.edges = [(s, d) for s, d in self.edges if s != task_id and d != task_id]
        return True


class GPUAllocation(BaseSchema):
    """GPU allocation specification."""
    gpu_count: int = 1
    gpu_indices: List[int] = Field(default_factory=list)

    memory_per_gpu_gb: float = 16.0
    memory_reserved_gb: float = 2.0

    compute_capability_required: Optional[str] = None

    allocate_fraction: bool = False
    memory_fraction: float = 1.0

    model_to_load: Optional[str] = None
    quantization_type: Literal["none", "int8", "int4", "fp16", "bf16"] = "fp16"

    preferred_device_type: Literal["any", "nvidia", "amd", "intel"] = "any"

    exclusive_mode: bool = False
    enable_mps: bool = False

    def validate_allocation(self, available_gpus: int, total_memory_gb: float) -> bool:
        """Validate allocation against available resources."""
        if self.gpu_count > available_gpus:
            return False
        required_memory = self.gpu_count * self.memory_per_gpu_gb
        if required_memory > total_memory_gb:
            return False
        return True


class ProviderRouting(BaseSchema):
    """Provider routing configuration."""
    primary_provider: Optional[str] = None
    fallback_providers: List[str] = Field(default_factory=list)

    preferred_models: List[str] = Field(default_factory=list)
    blocked_models: List[str] = Field(default_factory=list)

    enable_provider_selection: bool = True
    enable_model_selection: bool = True

    cost_limit_per_request: Optional[float] = None
    latency_limit_ms: Optional[int] = None

    quality_threshold: float = 0.7

    capability_requirements: Dict[str, bool] = Field(default_factory=dict)

    routing_strategy: Literal["quality", "cost", "speed", "balanced", "adaptive"] = "balanced"

    def meets_capabilities(self, provider_caps: Dict[str, bool]) -> bool:
        """Check if provider meets capability requirements."""
        for cap, required in self.capability_requirements.items():
            if required and not provider_caps.get(cap, False):
                return False
        return True


class DistributedExecution(BaseSchema):
    """Distributed execution configuration."""
    execution_id: str

    task_graph: TaskGraph

    worker_pool_size: int = 10
    worker_timeout_seconds: int = 300

    enable_work_stealing: bool = True
    enable_speculative_execution: bool = False

    task_broadcast_enabled: bool = False
    result_aggregation: Literal["all", "first", "weighted"] = "first"

    gpu_allocation: Optional[GPUAllocation] = None

    provider_routing: ProviderRouting = Field(default_factory=ProviderRouting)

    execution_backend: Literal["celery", "ray", "kubernetes", "local"] = "celery"

    queue_name: str = "ai_dataset_tasks"
    priority_queue_enabled: bool = True

    max_parallel_tasks: int = 50
    task_chunk_size: int = 1

    enable_profiling: bool = False
    profile_interval_seconds: int = 60

    metrics_aggregation_interval_seconds: int = 30

    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrchestrationRequest(BaseSchema):
    """Request for orchestrating distributed execution."""
    workflow_id: Optional[str] = None
    workflow_config: Optional[Dict[str, Any]] = None

    execution: DistributedExecution

    enable_adaptive_planning: bool = True
    enable_constraint_reasoning: bool = True

    plan_only: bool = False
    dry_run: bool = False

    callback_url: Optional[str] = None
    webhook_events: List[str] = Field(default_factory=lambda: [
        "started", "progress", "completed", "failed"
    ])

    priority: Literal["low", "normal", "high", "urgent"] = "normal"

    start_after: Optional[datetime] = None
    deadline: Optional[datetime] = None

    max_total_cost_usd: Optional[float] = None
    max_duration_seconds: Optional[int] = None


class ExecutionMetrics(BaseSchema):
    """Metrics for distributed execution."""
    execution_id: str

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0

    success_rate: float = 0.0
    failure_rate: float = 0.0

    avg_task_duration_ms: float = 0.0
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0

    total_cost_usd: float = 0.0
    cost_per_task_usd: float = 0.0

    gpu_utilization: float = 0.0
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0

    throughput_tasks_per_second: float = 0.0

    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkerState(BaseSchema):
    """State of a worker in distributed execution."""
    worker_id: str

    status: Literal["idle", "busy", "error", "offline"] = "idle"

    current_task_id: Optional[str] = None
    completed_tasks: List[str] = Field(default_factory=list)

    gpu_allocations: List[GPUAllocation] = Field(default_factory=list)

    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    task_started_at: Optional[datetime] = None

    metrics: Dict[str, Any] = Field(default_factory=dict)


class ShardingConfig(BaseSchema):
    """Configuration for data sharding across workers."""
    shard_count: int = 10
    shuffle: bool = False
    seed: Optional[int] = None

    partition_key: Optional[str] = None
    partition_strategy: Literal["hash", "range", "round_robin", "custom"] = "hash"

    preserve_order: bool = False

    min_shard_size: Optional[int] = None
    max_shard_size: Optional[int] = None