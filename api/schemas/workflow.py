"""
Workflow Schemas

Schemas for workflow configuration, step definitions,
execution strategies, and orchestration modes.
"""

from typing import Dict, List, Optional, Any, Set, Union, Literal, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, computed_field, model_validator
from api.schemas.base import BaseSchema, Constraint, RetryPolicy, TimeoutConfig


class OrchestrationMode(str, Enum):
    """Workflow orchestration modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    SWARM = "swarm"
    ADAPTIVE = "adaptive"


class ExecutionStrategy(str, Enum):
    """Execution strategy for workflows."""
    AUTO = "auto"
    COST_OPTIMIZED = "cost_optimized"
    SPEED_OPTIMIZED = "speed_optimized"
    QUALITY_OPTIMIZED = "quality_optimized"
    BALANCED = "balanced"
    RELIABILITY_FOCUSED = "reliability_focused"


class StepStatus(str, Enum):
    """Status of a workflow step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class StepType(str, Enum):
    """Types of workflow steps."""
    DATA_COLLECTION = "data_collection"
    DATA_FILTERING = "data_filtering"
    DATA_AUGMENTATION = "data_augmentation"
    SYNTHETIC_GENERATION = "synthetic_generation"
    QUALITY_ASSESSMENT = "quality_assessment"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    EXPORT = "export"
    ANALYSIS = "analysis"
    ORCHESTRATION = "orchestration"
    AGENT_TASK = "agent_task"
    CUSTOM = "custom"


class StepDependency(BaseModel):
    """Dependency specification for workflow steps."""
    step_id: str
    dependency_type: Literal["must_complete", "must_succeed", "optional"] = "must_complete"

    pass_results: bool = True
    pass_partial_results: bool = False


class StepResourceAllocation(BaseModel):
    """Resource allocation for a workflow step."""
    gpu_count: int = 0
    gpu_memory_gb: Optional[float] = None
    cpu_count: Optional[int] = None
    memory_gb: Optional[float] = None

    preferred_providers: List[str] = Field(default_factory=list)
    blocked_providers: List[str] = Field(default_factory=list)

    priority: int = 100

    timeout_seconds: Optional[int] = None


class WorkflowStep(BaseSchema):
    """Individual workflow step definition."""
    step_id: str
    name: str
    step_type: StepType

    description: Optional[str] = None

    dependencies: List[StepDependency] = Field(default_factory=list)
    parallel_with: List[str] = Field(default_factory=list)

    config: Dict[str, Any] = Field(default_factory=dict)

    resources: StepResourceAllocation = Field(default_factory=StepResourceAllocation)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    timeout: Optional[TimeoutConfig] = None

    conditions: Optional[Dict[str, Any]] = None
    on_failure: Literal["continue", "abort", "retry"] = "retry"

    agent_id: Optional[str] = None
    model_id: Optional[str] = None

    checkpoint_enabled: bool = True
    checkpoint_interval_seconds: int = 300

    metrics_to_collect: List[str] = Field(default_factory=lambda: [
        "latency", "quality", "cost", "throughput"
    ])

    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    @computed_field
    @property
    def estimated_duration_seconds(self) -> Optional[int]:
        """Estimate step duration based on type and config."""
        base_durations = {
            StepType.DATA_COLLECTION: 300,
            StepType.DATA_FILTERING: 180,
            StepType.DATA_AUGMENTATION: 600,
            StepType.SYNTHETIC_GENERATION: 1200,
            StepType.QUALITY_ASSESSMENT: 120,
            StepType.VALIDATION: 60,
            StepType.TRANSFORMATION: 180,
            StepType.EXPORT: 300,
            StepType.ANALYSIS: 120,
            StepType.ORCHESTRATION: 60,
        }
        base = base_durations.get(self.step_type, 180)
        return base + self.resources.timeout_seconds if self.resources.timeout_seconds else base


class WorkflowConfig(BaseSchema):
    """Complete workflow configuration."""
    workflow_id: Optional[str] = None
    name: str
    description: str = ""

    version: str = "1.0.0"

    steps: List[WorkflowStep] = Field(default_factory=list)

    orchestration_mode: OrchestrationMode = OrchestrationMode.SEQUENTIAL
    execution_strategy: ExecutionStrategy = ExecutionStrategy.BALANCED

    max_concurrent_steps: int = 5
    max_retries: int = 3
    global_timeout_seconds: int = 7200

    enable_checkpoints: bool = True
    checkpoint_interval_seconds: int = 300

    enable_caching: bool = True
    cache_ttl_seconds: int = 3600

    enable_monitoring: bool = True
    monitoring_interval_seconds: int = 30

    observability_enabled: bool = True
    trace_enabled: bool = True

    on_workflow_failure: Literal["continue", "abort", "cleanup"] = "abort"

    metadata: Dict[str, Any] = Field(default_factory=dict)

    def validate_workflow(self) -> List[str]:
        """Validate workflow configuration."""
        errors = []

        step_ids = {step.step_id for step in self.steps}
        for step in self.steps:
            for dep in step.dependencies:
                if dep.step_id not in step_ids:
                    errors.append(f"Step '{step.step_id}': dependency '{dep.step_id}' not found")
                if dep.step_id == step.step_id:
                    errors.append(f"Step '{step.step_id}': self-dependency detected")

        circular_deps = self._check_circular_dependencies()
        if circular_deps:
            errors.append(f"Circular dependencies detected: {' -> '.join(circular_deps)}")

        return errors

    def _check_circular_dependencies(self) -> Optional[List[str]]:
        """Check for circular dependencies."""
        graph = {step.step_id: [dep.step_id for dep in step.dependencies] for step in self.steps}

        def has_cycle(node, visited, path):
            visited.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor in path:
                    return path[path.index(neighbor):] + [neighbor]
                if neighbor not in visited:
                    cycle = has_cycle(neighbor, visited, path.copy())
                    if cycle:
                        return cycle

            return None

        visited = set()
        for node in graph:
            if node not in visited:
                cycle = has_cycle(node, visited, [])
                if cycle:
                    return cycle

        return None

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """Get step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_ready_steps(self, completed_steps: Set[str]) -> List[WorkflowStep]:
        """Get steps ready for execution based on dependencies."""
        ready = []
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue

            dependencies_met = all(
                dep.step_id in completed_steps
                for dep in step.dependencies
            )
            if dependencies_met:
                ready.append(step)

        return ready


class WorkflowPlan(BaseSchema):
    """Generated execution plan for a workflow."""
    workflow_id: str
    plan_id: str

    estimated_total_duration_seconds: int = 0
    estimated_total_cost_usd: float = 0.0

    steps_order: List[str] = Field(default_factory=list)
    parallel_execution_groups: List[List[str]] = Field(default_factory=list)

    resource_estimates: Dict[str, StepResourceAllocation] = Field(default_factory=dict)
    provider_assignments: Dict[str, str] = Field(default_factory=dict)

    checkpoint_plan: List[Dict[str, Any]] = Field(default_factory=list)

    risk_factors: List[str] = Field(default_factory=list)
    optimization_opportunities: List[str] = Field(default_factory=list)

    estimated_quality: float = 0.0
    confidence_score: float = 0.0

    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class WorkflowExecution(BaseSchema):
    """Active workflow execution tracking."""
    execution_id: str
    workflow_id: str

    status: Literal["pending", "running", "completed", "failed", "cancelled", "paused"] = "pending"

    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    current_step: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    failed_steps: List[str] = Field(default_factory=list)

    progress_percentage: float = 0.0
    estimated_remaining_seconds: Optional[int] = None

    metrics: Dict[str, Any] = Field(default_factory=dict)

    checkpoint_id: Optional[str] = None
    last_checkpoint_at: Optional[datetime] = None

    error_log: List[Dict[str, Any]] = Field(default_factory=list)


class WorkflowTemplate(BaseSchema):
    """Reusable workflow template."""
    template_id: str
    name: str
    description: str = ""

    category: str = "general"
    tags: List[str] = Field(default_factory=list)

    workflow_config: WorkflowConfig
    parameters: Dict[str, Any] = Field(default_factory=dict)

    is_public: bool = False
    author_id: Optional[str] = None

    version: str = "1.0.0"
    usage_count: int = 0


class WorkflowSearch(BaseSchema):
    """Search criteria for workflow templates."""
    query: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None

    orchestration_mode: Optional[OrchestrationMode] = None
    execution_strategy: Optional[ExecutionStrategy] = None

    min_steps: Optional[int] = None
    max_steps: Optional[int] = None

    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    sort_by: Literal["name", "created_at", "usage_count", "rating"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"

    page: int = 1
    page_size: int = 20