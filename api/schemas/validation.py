"""
Validation Schemas

Schemas for constraint analysis, feasibility evaluation,
conflict detection, and optimization suggestions.
"""

from typing import Dict, List, Optional, Any, Set, Union, Literal, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from api.schemas.base import BaseSchema, Constraint, ConstraintType, ConstraintScope


class ValidationStatus(str, Enum):
    """Validation status."""
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ValidationSeverity(str, Enum):
    """Severity of validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUGGESTION = "suggestion"


class FeasibilityLevel(str, Enum):
    """Feasibility assessment level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"
    UNKNOWN = "unknown"


class ConflictDetection(BaseSchema):
    """Detected constraint conflicts."""
    conflict_id: str

    involved_constraints: List[str] = Field(default_factory=list)
    conflict_type: Literal["contradiction", "incompatibility", "resource_contention", "mutual_exclusion"] = "contradiction"

    description: str
    severity: ValidationSeverity = ValidationSeverity.WARNING

    resolution_suggestions: List[str] = Field(default_factory=list)
    auto_resolution_possible: bool = False

    metadata: Dict[str, Any] = Field(default_factory=dict)


class OptimizationSuggestion(BaseSchema):
    """Optimization suggestion for constraints."""
    suggestion_id: str

    category: Literal["cost", "quality", "speed", "resource", "reliability"] = "cost"

    description: str
    potential_savings: Optional[Dict[str, float]] = None

    estimated_impact: float = 0.0
    confidence: float = 0.0

    implementation_effort: Literal["trivial", "easy", "moderate", "complex"] = "easy"

    constraint_adjustments: Dict[str, Any] = Field(default_factory=dict)
    expected_outcome: Optional[str] = None

    priority: int = 50


class ConstraintAnalysis(BaseSchema):
    """Analysis of request constraints."""
    request_id: str

    constraints: List[Constraint] = Field(default_factory=list)

    constraint_categories: Dict[str, List[str]] = Field(default_factory=dict)

    constraint_complexity_score: float = 0.0
    constraint_confidence: float = 1.0

    missing_inferences: List[str] = Field(default_factory=list)
    inferred_constraints: List[Constraint] = Field(default_factory=list)
    constraint_groups: List[str] = Field(default_factory=list)

    def add_inferred_constraint(self, constraint: Constraint, reason: str) -> None:
        """Add an inferred constraint with explanation."""
        constraint.metadata["inferred_from"] = reason
        self.inferred_constraints.append(constraint)


class FeasibilityResult(BaseSchema):
    """Feasibility assessment result."""
    request_id: str

    overall_feasibility: FeasibilityLevel = FeasibilityLevel.UNKNOWN
    feasibility_score: float = 0.0

    constraints_met: List[str] = Field(default_factory=list)
    constraints_violated: List[str] = Field(default_factory=list)
    constraints_conflicting: List[str] = Field(default_factory=list)

    estimated_success_probability: float = 0.0

    blockers: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)

    recommendations: List[str] = Field(default_factory=list)

    alternative_approaches: List[Dict[str, Any]] = Field(default_factory=list)

    execution_strategy_suggestion: Optional[str] = None
    provider_suggestion: Optional[str] = None

    estimated_duration_hours: float = 0.0
    estimated_cost_usd: float = 0.0

    confidence: float = 0.0
    confidence_factors: Dict[str, float] = Field(default_factory=dict)


class ValidationIssue(BaseSchema):
    """Individual validation issue."""
    issue_id: str
    field_path: str

    severity: ValidationSeverity

    code: str
    message: str
    details: Optional[str] = None

    suggestion: Optional[str] = None
    auto_fix_available: bool = False

    related_issues: List[str] = Field(default_factory=list)

    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseSchema):
    """Complete validation result."""
    request_id: str
    status: ValidationStatus

    issues: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=lambda: [])
    suggestions: List[ValidationIssue] = Field(default_factory=lambda: [])

    semantic_analysis: Optional[Dict[str, Any]] = None

    constraint_analysis: Optional[ConstraintAnalysis] = None
    feasibility_result: Optional[FeasibilityResult] = None

    conflicts: List[ConflictDetection] = Field(default_factory=list)
    optimizations: List[OptimizationSuggestion] = Field(default_factory=list)

    processing_recommendations: List[str] = Field(default_factory=list)

    validation_duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def has_errors(self) -> bool:
        """Check if there are validation errors."""
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return len(self.warnings) > 0

    def get_error_count(self) -> int:
        """Get count of errors."""
        return sum(1 for issue in self.issues if issue.severity == ValidationSeverity.ERROR)

    def get_warning_count(self) -> int:
        """Get count of warnings."""
        return len(self.warnings)


class SemanticAnalysis(BaseSchema):
    """Semantic analysis of user request."""
    request_id: str

    raw_input: str
    normalized_input: str

    intent: str
    intent_confidence: float = 1.0

    entities: Dict[str, Any] = Field(default_factory=dict)
    entity_types: Dict[str, str] = Field(default_factory=dict)

    extracted_constraints: List[Constraint] = Field(default_factory=list)
    implied_constraints: List[Constraint] = Field(default_factory=list)

    domain_classification: Optional[str] = None
    task_classification: Optional[str] = None

    ambiguity_score: float = 0.0
    clarity_score: float = 1.0

    processing_recommendations: List[str] = Field(default_factory=list)

    example_queries: List[str] = Field(default_factory=list)


class CostAnalysis(BaseSchema):
    """Cost analysis for request."""
    request_id: str

    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0

    estimated_api_calls: int = 1
    estimated_concurrent_requests: int = 1

    per_provider_costs: Dict[str, float] = Field(default_factory=dict)
    total_estimated_cost_usd: float = 0.0

    cost_budget: Optional[float] = None
    budget_sufficient: bool = True

    cost_optimization_suggestions: List[str] = Field(default_factory=list)

    cost_confidence: float = 0.0
    cost_factors: Dict[str, float] = Field(default_factory=dict)


class ResourceAnalysis(BaseSchema):
    """Resource requirement analysis."""
    request_id: str

    estimated_gpu_hours: float = 0.0
    estimated_cpu_hours: float = 0.0
    estimated_memory_gb_hours: float = 0.0

    estimated_storage_gb: float = 0.0

    peak_concurrent_gpus: int = 0
    peak_concurrent_workers: int = 0

    total_compute_units: float = 0.0

    resource_constraints: Dict[str, Any] = Field(default_factory=dict)
    resource_availability: Dict[str, Any] = Field(default_factory=dict)

    bottleneck_identified: Optional[str] = None
    bottleneck_confidence: float = 0.0


class ScalabilityAssessment(BaseSchema):
    """Scalability assessment for request."""
    request_id: str

    current_scale_feasible: bool = True
    scale_limits_identified: List[str] = Field(default_factory=list)

    max_achievable_samples: int = 1000000
    min_cost_per_sample_usd: float = 0.001

    scaling_recommendations: List[str] = Field(default_factory=list)

    parallelization_opportunities: List[str] = Field(default_factory=list)
    chunking_opportunities: List[str] = Field(default_factory=list)

    estimated_time_at_scale: Dict[int, float] = Field(default_factory=dict)
    estimated_cost_at_scale: Dict[int, float] = Field(default_factory=dict)


class ValidationSummary(BaseSchema):
    """Summary of validation results."""
    total_requests: int = 0
    valid_requests: int = 0
    invalid_requests: int = 0
    partial_requests: int = 0

    total_issues: int = 0
    total_errors: int = 0
    total_warnings: int = 0

    avg_validation_duration_ms: float = 0.0

    common_issues: Dict[str, int] = Field(default_factory=dict)
    common_suggestions: Dict[str, int] = Field(default_factory=dict)

    feasibility_distribution: Dict[str, int] = Field(default_factory=dict)

    timestamp: datetime = Field(default_factory=datetime.utcnow)