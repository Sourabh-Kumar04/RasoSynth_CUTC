"""
Planning Schemas

Schemas for execution planning, cost estimation,
resource allocation, and workflow optimization.
"""

from typing import Dict, List, Optional, Any, Set, Union, Literal, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from api.schemas.base import BaseSchema, Constraint
from api.schemas.workflow import WorkflowStep, StepResourceAllocation


class PlanStatus(str, Enum):
    """Status of execution plan."""
    DRAFT = "draft"
    VALIDATED = "validated"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStep(BaseSchema):
    """Individual step in execution plan."""
    step_id: str
    workflow_step_id: Optional[str] = None

    name: str
    description: Optional[str] = None

    step_order: int = 0
    parallel_group: Optional[int] = None

    assigned_provider: Optional[str] = None
    assigned_model: Optional[str] = None
    assigned_worker: Optional[str] = None

    resources: StepResourceAllocation

    estimated_duration_seconds: int = 0
    estimated_cost_usd: float = 0.0

    input_dependencies: List[str] = Field(default_factory=list)
    output_produced: List[str] = Field(default_factory=list)

    retry_policy: Dict[str, Any] = Field(default_factory=dict)
    checkpoint_enabled: bool = True

    quality_metrics: Dict[str, float] = Field(default_factory=dict)
    success_criteria: Dict[str, Any] = Field(default_factory=dict)

    status: PlanStatus = PlanStatus.DRAFT


class ExecutionPlan(BaseSchema):
    """Complete execution plan."""
    plan_id: str
    request_id: str

    status: PlanStatus = PlanStatus.DRAFT

    steps: List[PlanStep] = Field(default_factory=list)

    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None

    orchestration_mode: Literal["sequential", "parallel", "hierarchical", "swarm", "adaptive"] = "sequential"
    execution_strategy: Literal["auto", "cost", "speed", "quality", "balanced"] = "balanced"

    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    total_estimated_duration_seconds: int = 0
    total_estimated_cost_usd: float = 0.0

    total_gpu_hours: float = 0.0
    total_compute_units: float = 0.0

    parallelization_factor: float = 1.0
    efficiency_score: float = 0.0

    provider_distribution: Dict[str, int] = Field(default_factory=dict)

    risk_score: float = 0.0
    risk_factors: List[str] = Field(default_factory=list)

    optimization_applied: List[str] = Field(default_factory=list)

    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

    metadata: Dict[str, Any] = Field(default_factory=dict)

    def validate_plan(self) -> List[str]:
        """Validate execution plan."""
        errors = []

        step_ids = {step.step_id for step in self.steps}
        for step in self.steps:
            for dep in step.input_dependencies:
                if dep not in step_ids:
                    errors.append(f"Step {step.step_id}: dependency {dep} not found")

        seen_orders = {}
        for step in self.steps:
            if step.step_order in seen_orders:
                errors.append(f"Duplicate step order: {step.step_order}")
            seen_orders[step.step_order] = step.step_id

        return errors

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        """Get step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_steps_by_phase(self, phase: str) -> List[PlanStep]:
        """Get steps by phase."""
        return [s for s in self.steps if s.metadata.get("phase") == phase]


class CostEstimate(BaseSchema):
    """Cost estimation for request."""
    request_id: str

    input_cost_per_1k: Dict[str, float] = Field(default_factory=dict)
    output_cost_per_1k: Dict[str, float] = Field(default_factory=dict)

    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0

    estimated_api_calls: int = 1
    estimated_batch_size: int = 1

    per_provider_costs: Dict[str, float] = Field(default_factory=dict)
    per_model_costs: Dict[str, float] = Field(default_factory=dict)

    total_compute_cost_usd: float = 0.0
    total_api_cost_usd: float = 0.0
    total_storage_cost_usd: float = 0.0

    total_estimated_cost_usd: float = 0.0

    budget_limit: Optional[float] = None
    budget_vs_estimate: Optional[float] = None

    cost_confidence: float = 0.0
    cost_factors: Dict[str, float] = Field(default_factory=dict)

    optimization_potential: float = 0.0
    optimization_suggestions: List[str] = Field(default_factory=list)

    breakdown: Dict[str, float] = Field(default_factory=dict)


class StorageEstimate(BaseSchema):
    """Storage estimation for request."""
    request_id: str

    input_storage_gb: float = 0.0
    intermediate_storage_gb: float = 0.0
    output_storage_gb: float = 0.0

    total_storage_gb: float = 0.0

    storage_class: Literal["hot", "warm", "cold", "archive"] = "hot"

    compression_factor: float = 1.0
    deduplication_savings: float = 0.0

    backup_required: bool = False
    replication_factor: float = 1.0

    estimated_storage_cost_monthly_usd: float = 0.0

    storage_constraints: Dict[str, Any] = Field(default_factory=dict)
    storage_bottleneck: Optional[str] = None


class TimeEstimate(BaseSchema):
    """Time estimation for request."""
    request_id: str

    phase_estimates: Dict[str, int] = Field(default_factory=dict)

    data_collection_time_seconds: Optional[int] = None
    processing_time_seconds: Optional[int] = None
    generation_time_seconds: Optional[int] = None
    validation_time_seconds: Optional[int] = None
    export_time_seconds: Optional[int] = None

    total_estimated_seconds: int = 0
    total_estimated_hours: float = 0.0

    parallel_time_seconds: Optional[int] = None
    sequential_time_seconds: Optional[int] = None

    parallelization_speedup: float = 1.0

    bottleneck_phase: Optional[str] = None

    time_confidence: float = 0.0
    time_factors: Dict[str, float] = Field(default_factory=dict)


class ResourceAllocation(BaseSchema):
    """Resource allocation plan."""
    request_id: str

    gpu_allocation: Dict[str, int] = Field(default_factory=dict)
    cpu_allocation: Dict[str, int] = Field(default_factory=dict)
    memory_allocation_gb: Dict[str, float] = Field(default_factory=dict)

    worker_count: int = 1
    worker_type: Literal["cpu", "gpu", "high_memory"] = "cpu"

    provider_allocation: Dict[str, float] = Field(default_factory=dict)

    storage_allocation_gb: float = 0.0
    network_bandwidth_mbps: Optional[float] = None

    total_compute_units: float = 0.0
    total_gpu_hours: float = 0.0

    resource_constraints: Dict[str, Any] = Field(default_factory=dict)
    resource_availability: Dict[str, Any] = Field(default_factory=dict)

    scheduling_strategy: Literal["immediate", "batch", "scheduled"] = "immediate"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class ProviderRecommendation(BaseSchema):
    """Provider recommendation for request."""
    provider: str
    model: str

    score: float = 0.0
    score_breakdown: Dict[str, float] = Field(default_factory=dict)

    estimated_cost_usd: float = 0.0
    estimated_latency_ms: float = 0.0
    estimated_quality_score: float = 0.0

    capabilities_match: float = 1.0
    constraints_satisfied: float = 1.0

    provider_status: Literal["healthy", "degraded", "unavailable"] = "healthy"

    fallback_recommended: bool = False
    fallback_providers: List[str] = Field(default_factory=list)

    warnings: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class PlanOptimization(BaseSchema):
    """Plan optimization suggestions."""
    optimization_id: str

    category: Literal["cost", "speed", "quality", "resource", "reliability"] = "cost"

    title: str
    description: str

    current_value: Any
    optimized_value: Any

    estimated_improvement_percent: float = 0.0

    implementation_steps: List[str] = Field(default_factory=list)
    implementation_risk: Literal["low", "medium", "high"] = "low"

    expected_outcome: Dict[str, Any] = Field(default_factory=dict)
    actual_outcome: Optional[Dict[str, Any]] = None

    applied: bool = False
    applied_at: Optional[datetime] = None


class WorkflowOptimization(BaseSchema):
    """Complete workflow optimization."""
    plan_id: str

    optimizations: List[PlanOptimization] = Field(default_factory=list)

    original_cost_usd: float = 0.0
    optimized_cost_usd: float = 0.0
    cost_savings_percent: float = 0.0

    original_duration_seconds: int = 0
    optimized_duration_seconds: int = 0
    duration_savings_percent: float = 0.0

    original_quality_score: float = 0.0
    optimized_quality_score: float = 0.0
    quality_impact: float = 0.0

    tradeoffs: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

    auto_apply: bool = False
    verified: bool = False