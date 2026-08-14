"""
Base API Schemas

Foundational schemas for constraint modeling,
semantic requests, and base validation types.
"""

from typing import Dict, List, Optional, Any, Set, Union, Literal, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, computed_field, model_validator
from pydantic.types import StrictInt, StrictFloat


class ConstraintType(str, Enum):
    """Types of constraints supported by the system."""
    DATA_SIZE = "data_size"
    DATA_SCHEMA = "data_schema"
    DATA_MODALITY = "data_modality"
    QUALITY_ACCURACY = "quality_accuracy"
    QUALITY_TOXICITY = "quality_toxicity"
    QUALITY_DIVERSITY = "quality_diversity"
    INFRA_GPU = "infra_gpu"
    INFRA_MEMORY = "infra_memory"
    INFRA_STORAGE = "infra_storage"
    COST_TOKEN_BUDGET = "cost_token_budget"
    COST_API_SPEND = "cost_api_spend"
    LEGAL_LICENSING = "legal_licensing"
    LEGAL_REGIONAL = "legal_regional"
    SECURITY_PRIVACY = "security_privacy"
    SECURITY_OFFLINE = "security_offline"
    SECURITY_SENSITIVE = "security_sensitive"
    PERFORMANCE_LATENCY = "performance_latency"
    PERFORMANCE_THROUGHPUT = "performance_throughput"
    SEMANTIC_DOMAIN = "semantic_domain"
    SEMANTIC_SPECIFICITY = "semantic_specificity"
    SYNTHETIC_RATIO = "synthetic_ratio"
    PROVIDER_ALLOWED = "provider_allowed"
    PROVIDER_BLOCKED = "provider_blocked"
    CUSTOM = "custom"


class ConstraintScope(str, Enum):
    """Scope of constraint application."""
    GLOBAL = "global"
    DATASET = "dataset"
    WORKFLOW = "workflow"
    STEP = "step"
    PROVIDER = "provider"


class Constraint(BaseModel):
    """Individual constraint specification."""
    type: ConstraintType
    scope: ConstraintScope = ConstraintScope.GLOBAL

    value: Any
    unit: Optional[str] = None

    soft: bool = False
    priority: int = 100

    description: Optional[str] = None
    reason: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_satisfiable(self) -> bool:
        """Check if constraint value is valid."""
        if self.value is None:
            return False
        if isinstance(self.value, (int, float)) and self.value < 0:
            return False
        return True


class ConstraintGroup(BaseModel):
    """Group of related constraints."""
    name: str
    constraints: List[Constraint] = Field(default_factory=list)
    combine_with: Literal["AND", "OR"] = "AND"
    priority: int = 100


class SemanticRequest(BaseModel):
    """Semantic understanding wrapper for user requests."""
    request_id: Optional[str] = None
    raw_request: str
    language: str = "en"

    intent: Optional[str] = None
    entities: Dict[str, Any] = Field(default_factory=dict)

    constraints: List[Constraint] = Field(default_factory=list)
    constraint_groups: List[ConstraintGroup] = Field(default_factory=list)

    confidence: float = 1.0
    ambiguity_score: float = 0.0

    inferred_context: Dict[str, Any] = Field(default_factory=dict)
    normalized_requirements: Dict[str, Any] = Field(default_factory=dict)

    processing_hints: Dict[str, Any] = Field(default_factory=dict)

    def get_all_constraints(self) -> List[Constraint]:
        """Get all constraints including from groups."""
        constraints = list(self.constraints)
        for group in self.constraint_groups:
            constraints.extend(group.constraints)
        return constraints

    def get_constraints_by_type(self, constraint_type: ConstraintType) -> List[Constraint]:
        """Get constraints filtered by type."""
        return [c for c in self.get_all_constraints() if c.type == constraint_type]

    def get_constraints_by_scope(self, scope: ConstraintScope) -> List[Constraint]:
        """Get constraints filtered by scope."""
        return [c for c in self.get_all_constraints() if c.scope == scope]


class BaseSchema(BaseModel):
    """Enhanced base schema with semantic capabilities."""

    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None

    semantic_context: Optional[SemanticRequest] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "validate_assignment": True,
        "extra": "allow",
        "json_schema_extra": {
            "example": {
                "request_id": "req_abc123",
                "timestamp": "2026-05-12T10:00:00Z",
                "metadata": {}
            }
        }
    }

    @computed_field
    @property
    def schema_version(self) -> str:
        """Return schema version."""
        return "1.0.0"

    def to_semantic_request(self) -> SemanticRequest:
        """Convert schema to semantic request for analysis."""
        return SemanticRequest(
            raw_request=str(self.model_dump_json()),
            constraints=self._extract_constraints()
        )

    def _extract_constraints(self) -> List[Constraint]:
        """Extract constraints from schema fields."""
        constraints = []
        data = self.model_dump()

        for field_name, value in data.items():
            if isinstance(value, dict):
                if "constraint" in str(field_name).lower():
                    constraint_type = field_name.upper().replace("_", "_")
                    try:
                        ct = ConstraintType(constraint_type)
                    except ValueError:
                        ct = ConstraintType.CUSTOM
                    constraints.append(Constraint(
                        type=ct,
                        value=value.get("value"),
                        description=field_name
                    ))

        return constraints


class RequestPriority(str, Enum):
    """Request processing priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class RetryPolicy(BaseModel):
    """Retry policy for failed operations."""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_backoff: bool = True
    jitter: bool = True

    retry_on_errors: List[str] = Field(default_factory=lambda: [
        "timeout", "rate_limit", "server_error"
    ])


class TimeoutConfig(BaseModel):
    """Timeout configuration for operations."""
    total_timeout_seconds: int = 3600
    per_step_timeout_seconds: int = 300
    idle_timeout_seconds: int = 600

    @field_validator("total_timeout_seconds", "per_step_timeout_seconds", "idle_timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Timeout must be positive")
        return v