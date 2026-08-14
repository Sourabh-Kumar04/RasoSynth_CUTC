"""
Constraint Reasoning & Validation Engine

Intelligent constraint analysis, semantic validation,
conflict detection, and feasibility evaluation.
"""

from typing import Dict, List, Optional, Any, Set, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field
import asyncio
import json

from api.schemas.base import (
    Constraint, ConstraintType, ConstraintScope,
    SemanticRequest, ConstraintGroup
)
from api.schemas.validation import (
    ValidationStatus, ValidationSeverity, FeasibilityLevel,
    ConflictDetection, OptimizationSuggestion, ConstraintAnalysis,
    FeasibilityResult, ValidationIssue, ValidationResult,
    SemanticAnalysis, CostAnalysis
)
from api.schemas.dataset import DatasetConfig, QualityConstraints, DataConstraints
from api.schemas.workflow import WorkflowConfig, WorkflowStep


class ConstraintReasoningEngine:
    """AI-powered constraint reasoning engine."""

    def __init__(self):
        self._constraint_rules: Dict[ConstraintType, Callable] = {}
        self._inference_rules: List[Callable] = []
        self._conflict_patterns: List[Dict[str, Any]] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register default constraint reasoning rules."""
        self._constraint_rules[ConstraintType.COST_TOKEN_BUDGET] = self._reason_cost_constraint
        self._constraint_rules[ConstraintType.QUALITY_ACCURACY] = self._reason_quality_constraint
        self._constraint_rules[ConstraintType.INFRA_GPU] = self._reason_gpu_constraint
        self._constraint_rules[ConstraintType.SECURITY_OFFLINE] = self._reason_offline_constraint

        self._conflict_patterns.extend([
            {
                "type": "contradiction",
                "patterns": [
                    (ConstraintType.SECURITY_OFFLINE, ConstraintType.DATA_MODALITY, ["vision", "audio"]),
                    (ConstraintType.COST_TOKEN_BUDGET, ConstraintType.QUALITY_ACCURACY, None),
                    (ConstraintType.INFRA_GPU, ConstraintType.COST_API_SPEND, None),
                ]
            },
            {
                "type": "incompatibility",
                "patterns": [
                    (ConstraintType.PROVIDER_BLOCKED, ConstraintType.PROVIDER_ALLOWED, None),
                    (ConstraintType.SECURITY_PRIVACY, ConstraintType.DATA_MODALITY, ["video", "audio"]),
                ]
            }
        ])

    def analyze(self, request: SemanticRequest) -> ConstraintAnalysis:
        """Analyze constraints from semantic request."""
        analysis = ConstraintAnalysis(
            request_id=request.request_id or f"analysis_{datetime.utcnow().timestamp()}",
            constraints=request.get_all_constraints()
        )

        self._categorize_constraints(analysis)
        self._calculate_complexity(analysis)
        self._infer_missing_constraints(analysis, request)

        return analysis

    def evaluate_feasibility(
        self,
        request: SemanticRequest,
        context: Optional[Dict[str, Any]] = None
    ) -> FeasibilityResult:
        """Evaluate feasibility of request given constraints."""
        result = FeasibilityResult(
            request_id=request.request_id or f"feasibility_{datetime.utcnow().timestamp()}",
            overall_feasibility=FeasibilityLevel.UNKNOWN,
            feasibility_score=0.0
        )

        context = context or {}
        available_resources = context.get("available_resources", {})
        budget = context.get("budget", None)
        gpu_available = available_resources.get("gpu_count", 0)
        memory_gb = available_resources.get("memory_gb", 0)

        all_constraints = request.get_all_constraints()

        for constraint in all_constraints:
            is_met = self._evaluate_constraint(constraint, context)
            if is_met:
                result.constraints_met.append(constraint.description or str(constraint.type))
            else:
                result.constraints_violated.append(constraint.description or str(constraint.type))

            if constraint.type == ConstraintType.QUALITY_ACCURACY and is_met:
                result.recommendations.append(
                    f"Quality requirement of {constraint.value} is achievable"
                )

        self._detect_conflicts(result, all_constraints)
        self._estimate_success_probability(result, all_constraints)
        self._generate_recommendations(result, context, all_constraints)
        self._calculate_estimated_metrics(result, all_constraints, context)

        return result

    def _categorize_constraints(self, analysis: ConstraintAnalysis) -> None:
        """Categorize constraints by type."""
        categories: Dict[str, List[str]] = {
            "data": [],
            "quality": [],
            "infrastructure": [],
            "cost": [],
            "security": [],
            "provider": []
        }

        for constraint in analysis.constraints:
            cat = constraint.type.value.split("_")[0]
            if cat in categories:
                categories[cat].append(str(constraint.type))
            else:
                categories["data"].append(str(constraint.type))

        analysis.constraint_categories = categories

    def _calculate_complexity(self, analysis: ConstraintAnalysis) -> None:
        """Calculate constraint complexity score."""
        score = 0.0
        score += len(analysis.constraints) * 0.1
        score += len(analysis.constraint_groups) * 0.2

        for constraint in analysis.constraints:
            if constraint.soft:
                score += 0.05
            else:
                score += 0.15

        analysis.constraint_complexity_score = min(1.0, score)
        analysis.constraint_confidence = 1.0 - (analysis.constraint_complexity_score * 0.1)

    def _infer_missing_constraints(
        self,
        analysis: ConstraintAnalysis,
        request: SemanticRequest
    ) -> None:
        """Infer missing constraints from request context."""
        inferred = []

        if request.ambiguity_score > 0.3:
            inferred.append("Consider adding explicit quality thresholds")

        entity_types = request.entities.get("type", [])
        if "code" in entity_types or "programming" in str(request.raw_request).lower():
            inferred.append(Constraint(
                type=ConstraintType.SEMANTIC_SPECIFICITY,
                value="programming",
                description="Inferred code-specific constraints"
            ))
            analysis.add_inferred_constraint(
                Constraint(
                    type=ConstraintType.SEMANTIC_SPECIFICITY,
                    value="programming"
                ),
                "Request contains code-related content"
            )

        if "multilingual" in str(request.raw_request).lower():
            analysis.add_inferred_constraint(
                Constraint(
                    type=ConstraintType.DATA_MODALITY,
                    value="multilingual"
                ),
                "Request mentions multilingual content"
            )

        analysis.missing_inferences = inferred

    def _evaluate_constraint(
        self,
        constraint: Constraint,
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate if a constraint is satisfied."""
        available_resources = context.get("available_resources", {})
        budget = context.get("budget")

        if constraint.type == ConstraintType.COST_TOKEN_BUDGET and budget:
            return constraint.value >= budget

        if constraint.type == ConstraintType.INFRA_GPU:
            gpu_count = available_resources.get("gpu_count", 0)
            return gpu_count >= constraint.value

        if constraint.type == ConstraintType.SECURITY_OFFLINE:
            return context.get("offline_mode", False)

        return True

    def _reason_cost_constraint(
        self,
        constraint: Constraint,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reason about cost constraints."""
        budget = context.get("budget", 0)
        estimated_cost = context.get("estimated_cost", 0)

        return {
            "is_satisfiable": budget >= estimated_cost,
            "gap": budget - estimated_cost if budget < estimated_cost else 0,
            "suggestions": [
                "Consider using cheaper models for initial iterations",
                "Enable semantic caching to reduce API costs"
            ] if budget < estimated_cost else []
        }

    def _reason_quality_constraint(
        self,
        constraint: Constraint,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reason about quality constraints."""
        quality_target = constraint.value
        available_quality = context.get("model_quality", 0.8)

        return {
            "is_satisfiable": available_quality >= quality_target,
            "gap": quality_target - available_quality if available_quality < quality_target else 0,
            "suggestions": [
                f"Model quality {available_quality:.2f} may not meet target {quality_target:.2f}",
                "Consider using Claude Opus or Gemini 2.5 Pro for higher quality"
            ] if available_quality < quality_target else []
        }

    def _reason_gpu_constraint(
        self,
        constraint: Constraint,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reason about GPU constraints."""
        gpus_requested = constraint.value
        gpus_available = context.get("available_resources", {}).get("gpu_count", 0)

        return {
            "is_satisfiable": gpus_available >= gpus_requested,
            "shortage": gpus_requested - gpus_available if gpus_available < gpus_requested else 0,
            "suggestions": [
                "Consider using quantized models to reduce GPU requirements",
                "Enable pipeline parallelism for multi-GPU workloads"
            ] if gpus_available < gpus_requested else []
        }

    def _reason_offline_constraint(
        self,
        constraint: Constraint,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reason about offline/security constraints."""
        has_multimodal = context.get("requires_multimodal", False)
        modality_type = context.get("modality_type")

        if has_multimodal and modality_type in ["image", "audio", "video"]:
            return {
                "is_satisfiable": False,
                "conflict": "Offline mode cannot support real-time multimodal processing",
                "suggestions": [
                    "Consider pre-processing images/audio locally",
                    "Use smaller distilled models for offline inference"
                ]
            }

        return {"is_satisfiable": True, "suggestions": []}

    def _detect_conflicts(
        self,
        result: FeasibilityResult,
        constraints: List[Constraint]
    ) -> None:
        """Detect conflicting constraints."""
        constraint_map = {c.type: c for c in constraints}

        if ConstraintType.PROVIDER_ALLOWED in constraint_map:
            allowed = constraint_map[ConstraintType.PROVIDER_ALLOWED]
            if ConstraintType.PROVIDER_BLOCKED in constraint_map:
                result.constraints_conflicting.append(
                    f"PROVIDER_ALLOWED conflicts with PROVIDER_BLOCKED: "
                    f"allowed={allowed.value}, blocked={constraint_map[ConstraintType.PROVIDER_BLOCKED].value}"
                )

        if ConstraintType.COST_TOKEN_BUDGET in constraint_map and ConstraintType.QUALITY_ACCURACY in constraint_map:
            cost_budget = constraint_map[ConstraintType.COST_TOKEN_BUDGET].value
            quality_target = constraint_map[ConstraintType.QUALITY_ACCURACY].value

            if cost_budget < 0.01 and quality_target > 0.9:
                result.risk_factors.append(
                    f"Low budget ${cost_budget} may not achieve high quality {quality_target}"
                )

    def _estimate_success_probability(
        self,
        result: FeasibilityResult,
        constraints: List[Constraint]
    ) -> None:
        """Estimate probability of success."""
        if not constraints:
            result.estimated_success_probability = 1.0
            return

        met_ratio = len(result.constraints_met) / len(constraints)
        conflict_penalty = len(result.constraints_conflicting) * 0.1
        blocker_penalty = len(result.blockers) * 0.2

        result.estimated_success_probability = max(0, min(1, met_ratio - conflict_penalty - blocker_penalty))

        if result.estimated_success_probability > 0.8:
            result.overall_feasibility = FeasibilityLevel.HIGH
        elif result.estimated_success_probability > 0.5:
            result.overall_feasibility = FeasibilityLevel.MEDIUM
        elif result.estimated_success_probability > 0.2:
            result.overall_feasibility = FeasibilityLevel.LOW
        else:
            result.overall_feasibility = FeasibilityLevel.NONE

    def _generate_recommendations(
        self,
        result: FeasibilityResult,
        context: Dict[str, Any],
        constraints: List[Constraint]
    ) -> None:
        """Generate optimization recommendations."""
        if result.estimated_success_probability < 0.5:
            result.recommendations.append(
                "Consider relaxing some constraints to improve feasibility"
            )

        if any(c.type == ConstraintType.COST_TOKEN_BUDGET for c in constraints):
            result.recommendations.append(
                "Enable cost optimization with model routing"
            )

        if any(c.type == ConstraintType.INFRA_GPU for c in constraints):
            result.recommendations.append(
                "Consider using model quantization to reduce GPU requirements"
            )

    def _calculate_estimated_metrics(
        self,
        result: FeasibilityResult,
        constraints: List[Constraint],
        context: Dict[str, Any]
    ) -> None:
        """Calculate estimated duration and cost."""
        sample_count = context.get("sample_count", 1000)
        estimated_per_sample = context.get("estimated_cost_per_sample", 0.001)

        result.estimated_cost_usd = sample_count * estimated_per_sample
        result.estimated_duration_hours = sample_count / 1000 * 0.1

        result.confidence = result.estimated_success_probability


class SemanticValidator:
    """Semantic validation beyond syntax checking."""

    def __init__(self):
        self._validators: Dict[str, Callable] = {}
        self._semantic_rules: List[Dict[str, Any]] = []
        self._register_default_validators()

    def _register_default_validators(self) -> None:
        """Register default semantic validators."""
        self._semantic_rules.extend([
            {
                "name": "gpu_allocation_feasibility",
                "check": self._validate_gpu_allocation,
                "severity": ValidationSeverity.ERROR,
                "message": "GPU allocation exceeds available resources"
            },
            {
                "name": "provider_compatibility",
                "check": self._validate_provider_compatibility,
                "severity": ValidationSeverity.ERROR,
                "message": "Incompatible provider combination detected"
            },
            {
                "name": "constraint_feasibility",
                "check": self._validate_constraint_feasibility,
                "severity": ValidationSeverity.WARNING,
                "message": "Constraint combination may not be achievable"
            },
            {
                "name": "multimodal_consistency",
                "check": self._validate_multimodal_consistency,
                "severity": ValidationSeverity.WARNING,
                "message": "Multimodal combination may have processing issues"
            }
        ])

    def validate(
        self,
        request: SemanticRequest,
        config: Union[DatasetConfig, WorkflowConfig],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Perform comprehensive semantic validation."""
        result = ValidationResult(
            request_id=request.request_id or f"validation_{datetime.utcnow().timestamp()}",
            status=ValidationStatus.VALID
        )

        context = context or {}

        for rule in self._semantic_rules:
            is_valid, details = rule["check"](request, config, context)
            if not is_valid:
                issue = ValidationIssue(
                    issue_id=f"issue_{rule['name']}_{datetime.utcnow().timestamp()}",
                    field_path="semantic",
                    severity=rule["severity"],
                    code=rule["name"],
                    message=rule["message"],
                    details=details
                )
                result.issues.append(issue)

        if result.issues:
            has_errors = any(i.severity == ValidationSeverity.ERROR for i in result.issues)
            result.status = ValidationStatus.INVALID if has_errors else ValidationStatus.WARNING

        return result

    def _validate_gpu_allocation(
        self,
        request: SemanticRequest,
        config: Any,
        context: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate GPU allocation is feasible."""
        if hasattr(config, "resources"):
            allocated_gpus = getattr(config.resources, "gpu_count", 0) if hasattr(config.resources, "gpu_count") else 0
        else:
            allocated_gpus = 0

        available_gpus = context.get("available_resources", {}).get("gpu_count", 0)

        if allocated_gpus > available_gpus:
            return False, f"Requested {allocated_gpus} GPUs but only {available_gpus} available"

        return True, None

    def _validate_provider_compatibility(
        self,
        request: SemanticRequest,
        config: Any,
        context: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate provider compatibility."""
        allowed_providers = request.get_constraints_by_type(ConstraintType.PROVIDER_ALLOWED)
        blocked_providers = request.get_constraints_by_type(ConstraintType.PROVIDER_BLOCKED)

        allowed_names = [c.value for c in allowed_providers]
        blocked_names = [c.value for c in blocked_providers]

        overlap = set(allowed_names) & set(blocked_names)
        if overlap:
            return False, f"Providers in both allowed and blocked lists: {overlap}"

        return True, None

    def _validate_constraint_feasibility(
        self,
        request: SemanticRequest,
        config: Any,
        context: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate constraint combination is feasible."""
        budget = request.get_constraints_by_type(ConstraintType.COST_TOKEN_BUDGET)
        quality = request.get_constraints_by_type(ConstraintType.QUALITY_ACCURACY)

        if budget and quality:
            budget_val = budget[0].value if budget else 0
            quality_val = quality[0].value if quality else 0

            if budget_val < 0.01 and quality_val > 0.9:
                return False, "High quality requirements may exceed budget"

        return True, None

    def _validate_multimodal_consistency(
        self,
        request: SemanticRequest,
        config: Any,
        context: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate multimodal combinations are consistent."""
        modalities = request.get_constraints_by_type(ConstraintType.DATA_MODALITY)
        offline_mode = request.get_constraints_by_type(ConstraintType.SECURITY_OFFLINE)

        if offline_mode and any(m.value in ["video", "audio"] for m in modalities):
            return False, "Offline mode may not support video/audio processing"

        return True, None


class ConstraintAnalyzer:
    """Advanced constraint analyzer with AI reasoning."""

    def __init__(self):
        self.reasoning_engine = ConstraintReasoningEngine()
        self.semantic_validator = SemanticValidator()

    async def analyze_request(
        self,
        request: SemanticRequest,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Perform complete request analysis."""
        result = ValidationResult(
            request_id=request.request_id or f"analysis_{datetime.utcnow().timestamp()}",
            status=ValidationStatus.VALID
        )

        constraint_analysis = self.reasoning_engine.analyze(request)
        result.constraint_analysis = constraint_analysis

        feasibility = self.reasoning_engine.evaluate_feasibility(request, context)
        result.feasibility_result = feasibility

        if feasibility.overall_feasibility == FeasibilityLevel.NONE:
            result.status = ValidationStatus.INVALID
            for blocker in feasibility.blockers:
                result.issues.append(ValidationIssue(
                    issue_id=f"blocker_{len(result.issues)}",
                    field_path="constraints",
                    severity=ValidationSeverity.ERROR,
                    code="FEASIBILITY_BLOCKER",
                    message=blocker
                ))

        for conflict in feasibility.constraints_conflicting:
            result.conflicts.append(ConflictDetection(
                conflict_id=f"conflict_{len(result.conflicts)}",
                conflict_type="contradiction",
                description=conflict
            ))

        return result

    def detect_conflicts(
        self,
        constraints: List[Constraint]
    ) -> List[ConflictDetection]:
        """Detect conflicts between constraints."""
        conflicts = []

        constraint_map: Dict[ConstraintType, List[Constraint]] = {}
        for c in constraints:
            if c.type not in constraint_map:
                constraint_map[c.type] = []
            constraint_map[c.type].append(c)

        if ConstraintType.PROVIDER_ALLOWED in constraint_map:
            if ConstraintType.PROVIDER_BLOCKED in constraint_map:
                conflicts.append(ConflictDetection(
                    conflict_id="provider_conflict",
                    involved_constraints=[
                        str(ConstraintType.PROVIDER_ALLOWED),
                        str(ConstraintType.PROVIDER_BLOCKED)
                    ],
                    conflict_type="mutual_exclusion",
                    description="Provider allowed and blocked lists overlap",
                    resolution_suggestions=["Remove overlap between allowed and blocked providers"]
                ))

        if ConstraintType.COST_TOKEN_BUDGET in constraint_map:
            cost_c = constraint_map[ConstraintType.COST_TOKEN_BUDGET][0]
            if cost_c.value < 0.005:
                if ConstraintType.QUALITY_ACCURACY in constraint_map:
                    quality_c = constraint_map[ConstraintType.QUALITY_ACCURACY][0]
                    if quality_c.value > 0.85:
                        conflicts.append(ConflictDetection(
                            conflict_id="quality_cost_conflict",
                            involved_constraints=[
                                str(ConstraintType.COST_TOKEN_BUDGET),
                                str(ConstraintType.QUALITY_ACCURACY)
                            ],
                            conflict_type="resource_contention",
                            description=f"Low budget ${cost_c.value} vs high quality {quality_c.value}",
                            resolution_suggestions=[
                                "Increase budget or lower quality requirements",
                                "Use more cost-efficient models"
                            ]
                        ))

        return conflicts