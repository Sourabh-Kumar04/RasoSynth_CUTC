"""
Provider Schemas

Schemas for provider constraints, model selection,
cost budgets, and routing policies.
"""

from typing import Dict, List, Optional, Any, Set, Literal, Callable
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from api.schemas.base import BaseSchema, Constraint, ConstraintType


class ProviderConstraint(BaseSchema):
    """Provider-specific constraint specification."""
    provider: str

    allowed: bool = True
    reason: Optional[str] = None

    constraints: List[Constraint] = Field(default_factory=list)

    rate_limit_requests_per_minute: Optional[int] = None
    rate_limit_tokens_per_minute: Optional[int] = None

    max_cost_per_request: Optional[float] = None
    max_daily_cost: Optional[float] = None

    quality_floor: float = 0.0
    latency_ceiling_ms: Optional[int] = None


class ModelConstraint(BaseSchema):
    """Model-specific constraint specification."""
    model_id: str

    allowed: bool = True
    reason: Optional[str] = None

    preferred: bool = False

    constraints: List[Constraint] = Field(default_factory=list)

    max_tokens: Optional[int] = None
    supported_modalities: List[str] = Field(default_factory=list)

    cost_per_1k_input: Optional[float] = None
    cost_per_1k_output: Optional[float] = None


class CostBudget(BaseSchema):
    """Cost budget specification."""
    max_total_cost_usd: Optional[float] = None
    max_cost_per_sample_usd: Optional[float] = None
    max_cost_per_request_usd: Optional[float] = None

    max_daily_cost_usd: Optional[float] = None
    max_monthly_cost_usd: Optional[float] = None

    warn_threshold_percent: float = 80.0
    stop_threshold_percent: float = 95.0

    auto_optimize: bool = True
    fallback_to_cheaper: bool = True

    preferred_providers: List[str] = Field(default_factory=list)

    def check_budget(self, current_cost: float, budget: Optional[float]) -> Literal["ok", "warning", "exceeded"]:
        """Check if cost is within budget."""
        if budget is None:
            return "ok"

        percentage = (current_cost / budget) * 100

        if percentage >= self.stop_threshold_percent:
            return "exceeded"
        elif percentage >= self.warn_threshold_percent:
            return "warning"
        return "ok"


class RoutingPolicy(BaseSchema):
    """Provider routing policy specification."""
    policy_id: str
    name: str

    priority_strategy: Literal["quality", "cost", "speed", "balanced", "adaptive"] = "balanced"

    provider_preferences: Dict[str, int] = Field(default_factory=dict)
    model_preferences: Dict[str, int] = Field(default_factory=dict)

    fallback_enabled: bool = True
    fallback_chain: List[str] = Field(default_factory=list)

    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 60

    rate_limiting_enabled: bool = True

    cost_optimization_enabled: bool = True
    auto_downgrade_on_budget: bool = False

    quality_threshold: float = 0.7
    latency_threshold_ms: Optional[int] = None

    enable_exploration: bool = True
    exploration_rate: float = 0.1


class ModelSelection(BaseSchema):
    """Model selection criteria and recommendations."""
    task_type: str

    required_capabilities: Dict[str, bool] = Field(default_factory=dict)
    preferred_capabilities: Dict[str, bool] = Field(default_factory=dict)

    quality_requirement: Literal["minimum", "standard", "high", "maximum"] = "standard"
    latency_requirement: Literal["low", "medium", "high"] = "medium"
    cost_requirement: Literal["minimum", "balanced", "maximum"] = "balanced"

    max_cost_per_1k_tokens: Optional[float] = None
    max_latency_ms: Optional[int] = None

    required_modalities: List[str] = Field(default_factory=list)
    preferred_modalities: List[str] = Field(default_factory=list)

    def calculate_score(
        self,
        provider_caps: Dict[str, bool],
        cost: float,
        latency_ms: float,
        quality_score: float
    ) -> float:
        """Calculate model selection score."""
        score = 0.0

        required_match = sum(
            1 for cap, required in self.required_capabilities.items()
            if required and provider_caps.get(cap, False)
        ) / max(len(self.required_capabilities), 1)
        score += required_match * 40

        if self.quality_requirement == "maximum":
            score += quality_score * 30
        elif self.quality_requirement == "high":
            score += quality_score * 20
        else:
            score += quality_score * 15

        latency_factor = 1.0 - (latency_ms / 10000) if latency_ms else 0.5
        score += latency_factor * 15

        cost_factor = 1.0 - (cost / 1.0) if cost else 0.5
        score += cost_factor * 15

        return min(1.0, score)


class ProviderMetrics(BaseSchema):
    """Provider performance metrics."""
    provider: str

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    success_rate: float = 0.0

    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    avg_cost_usd: float = 0.0
    total_cost_usd: float = 0.0

    avg_quality_score: float = 0.0
    hallucination_rate: float = 0.0

    rate_limit_hits: int = 0
    timeout_rate: float = 0.0

    last_updated: datetime = Field(default_factory=datetime.utcnow)


class ProviderHealth(BaseSchema):
    """Provider health status."""
    provider: str

    status: Literal["healthy", "degraded", "unhealthy", "unknown"] = "unknown"

    latency_ms: Optional[float] = None
    error_rate: float = 0.0

    rate_limit_remaining: Optional[int] = None
    rate_limit_reset_at: Optional[datetime] = None

    last_successful_call: Optional[datetime] = None
    last_failed_call: Optional[datetime] = None

    consecutive_failures: int = 0
    circuit_breaker_open: bool = False

    active_requests: int = 0


class ProviderConfigUpdate(BaseSchema):
    """Update provider configuration."""
    provider: str

    enabled: Optional[bool] = None
    priority: Optional[int] = None

    rate_limit_requests_per_minute: Optional[int] = None
    rate_limit_tokens_per_minute: Optional[int] = None

    max_cost_per_request: Optional[float] = None

    circuit_breaker_threshold: Optional[int] = None
    circuit_breaker_timeout_seconds: Optional[int] = None