"""
Workflow Planning & Optimization

Execution planning, cost estimation, resource allocation,
and workflow optimization.
"""

from typing import Dict, List, Optional, Any, Set, Callable, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio

from api.schemas.base import SemanticRequest, Constraint, ConstraintType
from api.schemas.dataset import DatasetConfig, DataConstraints, QualityConstraints
from api.schemas.workflow import (
    WorkflowConfig, WorkflowStep, WorkflowPlan, StepType,
    OrchestrationMode, ExecutionStrategy, StepResourceAllocation
)
from api.schemas.planning import (
    ExecutionPlan, PlanStep, CostEstimate, StorageEstimate,
    TimeEstimate, ResourceAllocation as PlanningResourceAllocation,
    ProviderRecommendation, PlanOptimization, WorkflowOptimization,
    PlanStatus
)
from api.schemas.validation import FeasibilityResult, FeasibilityLevel
from api.schemas.orchestration import TaskGraph, TaskNode, GPUAllocation, ProviderRouting


class WorkflowPlanner:
    """Intelligent workflow planner with multi-objective optimization."""

    def __init__(self):
        self._step_templates: Dict[StepType, Dict[str, Any]] = {}
        self._cost_models: Dict[str, Callable] = {}
        self._quality_models: Dict[str, Callable] = {}
        self._register_templates()

    def _register_templates(self) -> None:
        """Register default step templates."""
        self._step_templates = {
            StepType.DATA_COLLECTION: {
                "estimated_duration": 300,
                "estimated_cost": 0.50,
                "resources": {"gpu_count": 0, "cpu_count": 4}
            },
            StepType.DATA_FILTERING: {
                "estimated_duration": 180,
                "estimated_cost": 0.30,
                "resources": {"gpu_count": 0, "cpu_count": 2}
            },
            StepType.SYNTHETIC_GENERATION: {
                "estimated_duration": 1200,
                "estimated_cost": 5.00,
                "resources": {"gpu_count": 1, "cpu_count": 2}
            },
            StepType.QUALITY_ASSESSMENT: {
                "estimated_duration": 120,
                "estimated_cost": 0.20,
                "resources": {"gpu_count": 1, "cpu_count": 1}
            },
            StepType.EXPORT: {
                "estimated_duration": 300,
                "estimated_cost": 0.10,
                "resources": {"gpu_count": 0, "cpu_count": 2}
            },
        }

    async def create_plan(
        self,
        config: DatasetConfig,
        workflow: Optional[WorkflowConfig] = None,
        constraints: Optional[List[Constraint]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """Create an execution plan from configuration."""
        plan = ExecutionPlan(
            plan_id=f"plan_{datetime.utcnow().timestamp()}",
            request_id=config.request_id or "",
            orchestration_mode="sequential",
            execution_strategy="balanced"
        )

        context = context or {}

        steps = self._generate_steps(config, workflow)

        for i, step_config in enumerate(steps):
            step = await self._create_plan_step(
                step_config,
                step_order=i,
                context=context
            )
            plan.steps.append(step)

        plan.total_estimated_cost_usd = sum(s.estimated_cost_usd for s in plan.steps)
        plan.total_estimated_duration_seconds = sum(s.estimated_duration_seconds for s in plan.steps)

        self._optimize_plan(plan, constraints, context)

        return plan

    def _generate_steps(
        self,
        config: DatasetConfig,
        workflow: Optional[WorkflowConfig]
    ) -> List[Dict[str, Any]]:
        """Generate workflow steps from configuration."""
        steps = []

        steps.append({
            "step_id": "collect",
            "name": "Data Collection",
            "step_type": StepType.DATA_COLLECTION,
            "config": {"source": "llm", "sample_count": config.data_constraints.min_samples}
        })

        if config.data_constraints.schema:
            steps.append({
                "step_id": "filter",
                "name": "Data Filtering",
                "step_type": StepType.DATA_FILTERING,
                "config": {"schema": config.data_constraints.schema}
            })

        if config.dataset_type.value in ["synthetic", "hybrid"]:
            steps.append({
                "step_id": "generate",
                "name": "Synthetic Generation",
                "step_type": StepType.SYNTHETIC_GENERATION,
                "config": {
                    "ratio": config.synthetic_config.generation_ratio if config.synthetic_config else 0.5
                }
            })

        steps.append({
            "step_id": "quality",
            "name": "Quality Assessment",
            "step_type": StepType.QUALITY_ASSESSMENT,
            "config": {"threshold": config.quality_constraints.min_quality_score}
        })

        steps.append({
            "step_id": "export",
            "name": "Export Dataset",
            "step_type": StepType.EXPORT,
            "config": {"format": config.output_format.value}
        })

        return steps

    async def _create_plan_step(
        self,
        step_config: Dict[str, Any],
        step_order: int,
        context: Dict[str, Any]
    ) -> PlanStep:
        """Create a single plan step."""
        step_type = step_config.get("step_type", StepType.CUSTOM)
        template = self._step_templates.get(step_type, {})

        estimated_duration = step_config.get("duration", template.get("estimated_duration", 180))
        estimated_cost = step_config.get("cost", template.get("estimated_cost", 0.50))
        resources_config = step_config.get("resources", template.get("resources", {}))

        resources = StepResourceAllocation(
            gpu_count=resources_config.get("gpu_count", 0),
            cpu_count=resources_config.get("cpu_count", 1)
        )

        return PlanStep(
            step_id=step_config["step_id"],
            name=step_config["name"],
            description=step_config.get("description", ""),
            step_order=step_order,
            step_type=step_type,
            config=step_config.get("config", {}),
            resources=resources,
            estimated_duration_seconds=estimated_duration,
            estimated_cost_usd=estimated_cost,
            input_dependencies=step_config.get("dependencies", []),
        )

    def _optimize_plan(
        self,
        plan: ExecutionPlan,
        constraints: Optional[List[Constraint]],
        context: Dict[str, Any]
    ) -> None:
        """Optimize plan based on constraints."""
        if not constraints:
            plan.execution_strategy = "balanced"
            return

        for constraint in constraints:
            if constraint.type == ConstraintType.COST_TOKEN_BUDGET:
                plan.execution_strategy = "cost"
                plan.optimization_applied.append("cost_optimization")

            elif constraint.type == ConstraintType.PERFORMANCE_LATENCY:
                plan.execution_strategy = "speed"
                plan.optimization_applied.append("speed_optimization")

            elif constraint.type == ConstraintType.QUALITY_ACCURACY:
                plan.execution_strategy = "quality"
                plan.optimization_applied.append("quality_optimization")

        plan.efficiency_score = 0.85

    async def plan_dag(
        self,
        workflow: WorkflowConfig,
        context: Optional[Dict[str, Any]] = None
    ) -> WorkflowPlan:
        """Plan DAG execution for complex workflow."""
        plan = WorkflowPlan(
            workflow_id=workflow.workflow_id or "",
            plan_id=f"dag_{datetime.utcnow().timestamp()}",
            steps_order=[s.step_id for s in workflow.steps]
        )

        execution_groups = workflow.get_execution_order()
        plan.parallel_execution_groups = execution_groups

        plan.estimated_total_cost_usd = sum(
            self._step_templates.get(s.step_type, {}).get("estimated_cost", 0.5)
            for s in workflow.steps
        )

        plan.estimated_total_duration_seconds = self._estimate_dag_duration(workflow, execution_groups)

        plan.confidence_score = 0.85

        return plan

    def _estimate_dag_duration(
        self,
        workflow: WorkflowConfig,
        execution_groups: List[List[str]]
    ) -> int:
        """Estimate total DAG execution duration."""
        total_duration = 0

        for group in execution_groups:
            group_durations = []
            for step_id in group:
                step = workflow.get_step(step_id)
                if step:
                    group_durations.append(step.estimated_duration_seconds or 180)

            if group_durations:
                total_duration += max(group_durations)

        return total_duration


class CostEstimator:
    """Cost estimation for workflows and requests."""

    def __init__(self):
        self._provider_costs: Dict[str, Dict[str, float]] = {
            "google": {"input_per_1k": 0.00125, "output_per_1k": 0.005, "embedding_per_1k": 0.0001},
            "anthropic": {"input_per_1k": 0.015, "output_per_1k": 0.075, "embedding_per_1k": 0.0},
            "openai": {"input_per_1k": 0.01, "output_per_1k": 0.03, "embedding_per_1k": 0.0001},
            "nvidia": {"input_per_1k": 0.001, "output_per_1k": 0.002, "embedding_per_1k": 0.00005},
            "ollama": {"input_per_1k": 0.0, "output_per_1k": 0.0, "embedding_per_1k": 0.0},
        }

    def estimate(
        self,
        config: DatasetConfig,
        plan: ExecutionPlan,
        context: Optional[Dict[str, Any]] = None
    ) -> CostEstimate:
        """Estimate costs for execution plan."""
        context = context or {}

        sample_count = config.data_constraints.max_samples
        estimated_tokens_per_sample = context.get("tokens_per_sample", 1000)
        estimated_output_tokens = context.get("output_tokens_per_sample", 500)

        total_input_tokens = sample_count * estimated_tokens_per_sample
        total_output_tokens = sample_count * estimated_output_tokens

        estimate = CostEstimate(
            request_id=config.request_id or "",
            estimated_input_tokens=total_input_tokens,
            estimated_output_tokens=total_output_tokens,
            estimated_api_calls=sample_count
        )

        provider = context.get("preferred_provider", "google")
        costs = self._provider_costs.get(provider, self._provider_costs["google"])

        api_cost = (total_input_tokens / 1000 * costs["input_per_1k"] +
                   total_output_tokens / 1000 * costs["output_per_1k"])

        compute_cost = plan.total_estimated_cost_usd

        estimate.total_api_cost_usd = api_cost
        estimate.total_compute_cost_usd = compute_cost
        estimate.total_estimated_cost_usd = api_cost + compute_cost

        estimate.per_provider_costs[provider] = api_cost

        budget = context.get("budget")
        if budget:
            estimate.budget_limit = budget
            estimate.budget_vs_estimate = budget - estimate.total_estimated_cost_usd
            estimate.budget_sufficient = estimate.budget_vs_estimate >= 0

        if estimate.total_estimated_cost_usd > 100:
            estimate.optimization_suggestions.append("Consider using caching to reduce API costs")
            estimate.optimization_suggestions.append("Batch requests where possible")

        return estimate

    def estimate_step_cost(
        self,
        step: WorkflowStep,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Estimate cost for a single step."""
        template = {
            StepType.DATA_COLLECTION: 0.50,
            StepType.DATA_FILTERING: 0.30,
            StepType.SYNTHETIC_GENERATION: 5.00,
            StepType.QUALITY_ASSESSMENT: 0.20,
            StepType.EXPORT: 0.10,
        }

        base_cost = template.get(step.step_type, 0.50)

        if step.resources.gpu_count > 0:
            base_cost += step.resources.gpu_count * 0.50

        return base_cost


class ResourcePlanner:
    """Resource allocation planner."""

    def __init__(self):
        self._available_gpus = 4
        self._available_cpu = 16
        self._total_memory_gb = 64

    def plan_allocation(
        self,
        plan: ExecutionPlan,
        context: Optional[Dict[str, Any]] = None
    ) -> PlanningResourceAllocation:
        """Plan resource allocation for execution."""
        context = context or {}

        gpu_allocation: Dict[str, int] = {}
        cpu_allocation: Dict[str, int] = {}
        memory_gb: Dict[str, float] = {}

        total_gpus = 0
        total_cpus = 0
        total_memory = 0.0

        for step in plan.steps:
            gpus = step.resources.gpu_count
            cpus = step.resources.cpu_count or 1
            memory = step.resources.memory_gb or 2.0

            gpu_allocation[step.step_id] = gpus
            cpu_allocation[step.step_id] = cpus
            memory_gb[step.step_id] = memory

            total_gpus += gpus
            total_cpus += cpus
            total_memory += memory

        return PlanningResourceAllocation(
            request_id=plan.request_id,
            gpu_allocation=gpu_allocation,
            cpu_allocation=cpu_allocation,
            memory_allocation_gb=memory_gb,
            worker_count=max(1, total_cpus // 2),
            total_compute_units=total_cpus,
            total_gpu_hours=total_gpus * (plan.total_estimated_duration_seconds / 3600)
        )

    def validate_allocation(
        self,
        allocation: PlanningResourceAllocation
    ) -> tuple[bool, List[str]]:
        """Validate resource allocation is feasible."""
        issues = []

        total_gpus = sum(allocation.gpu_allocation.values())
        if total_gpus > self._available_gpus:
            issues.append(f"GPU shortage: need {total_gpus}, have {self._available_gpus}")

        total_cpus = sum(allocation.cpu_allocation.values())
        if total_cpus > self._available_cpu:
            issues.append(f"CPU shortage: need {total_cpus}, have {self._available_cpu}")

        total_memory = sum(allocation.memory_allocation_gb.values())
        if total_memory > self._total_memory_gb:
            issues.append(f"Memory shortage: need {total_memory}GB, have {self._total_memory_gb}GB")

        return len(issues) == 0, issues


class ExecutionOptimizer:
    """Multi-objective execution optimizer."""

    def __init__(self):
        self.planner = WorkflowPlanner()
        self.cost_estimator = CostEstimator()
        self.resource_planner = ResourcePlanner()

    async def optimize(
        self,
        plan: ExecutionPlan,
        objectives: List[str] = None,
        constraints: Optional[List[Constraint]] = None
    ) -> WorkflowOptimization:
        """Optimize execution plan for given objectives."""
        if objectives is None:
            objectives = ["cost", "speed", "quality"]

        optimization = WorkflowOptimization(
            plan_id=plan.plan_id,
            original_cost_usd=plan.total_estimated_cost_usd,
            original_duration_seconds=plan.total_estimated_duration_seconds
        )

        original_cost = plan.total_estimated_cost_usd
        original_duration = plan.total_estimated_duration_seconds

        if "cost" in objectives:
            cost_opt = await self._optimize_cost(plan)
            if cost_opt:
                optimization.optimizations.append(cost_opt)

        if "speed" in objectives:
            speed_opt = await self._optimize_speed(plan)
            if speed_opt:
                optimization.optimizations.append(speed_opt)

        if "quality" in objectives:
            quality_opt = await self._optimize_quality(plan)
            if quality_opt:
                optimization.optimizations.append(quality_opt)

        optimization.cost_savings_percent = (
            (original_cost - optimization.optimized_cost_usd) / original_cost * 100
            if original_cost > 0 else 0
        )

        optimization.duration_savings_percent = (
            (original_duration - optimization.optimized_duration_seconds) / original_duration * 100
            if original_duration > 0 else 0
        )

        return optimization

    async def _optimize_cost(self, plan: ExecutionPlan) -> Optional[PlanOptimization]:
        """Optimize for cost."""
        potential_savings = plan.total_estimated_cost_usd * 0.15

        return PlanOptimization(
            optimization_id=f"opt_cost_{datetime.utcnow().timestamp()}",
            category="cost",
            title="Cost Optimization",
            description="Reduce costs through batching and caching",
            current_value=plan.total_estimated_cost_usd,
            optimized_value=plan.total_estimated_cost_usd - potential_savings,
            estimated_improvement_percent=15.0,
            implementation_steps=[
                "Enable semantic caching for repeated queries",
                "Batch small requests together",
                "Use cheaper models for non-critical steps"
            ],
            expected_outcome={"cost_reduction": potential_savings}
        )

    async def _optimize_speed(self, plan: ExecutionPlan) -> Optional[PlanOptimization]:
        """Optimize for speed."""
        potential_savings = plan.total_estimated_duration_seconds * 0.2

        return PlanOptimization(
            optimization_id=f"opt_speed_{datetime.utcnow().timestamp()}",
            category="speed",
            title="Speed Optimization",
            description="Improve throughput through parallelization",
            current_value=plan.total_estimated_duration_seconds,
            optimized_value=plan.total_estimated_duration_seconds - potential_savings,
            estimated_improvement_percent=20.0,
            implementation_steps=[
                "Enable parallel step execution",
                "Use larger batch sizes",
                "Pre-fetch data for next steps"
            ],
            expected_outcome={"time_reduction": potential_savings}
        )

    async def _optimize_quality(self, plan: ExecutionPlan) -> Optional[PlanOptimization]:
        """Optimize for quality."""
        return PlanOptimization(
            optimization_id=f"opt_quality_{datetime.utcnow().timestamp()}",
            category="quality",
            title="Quality Optimization",
            description="Improve output quality through multiple passes",
            current_value=0.8,
            optimized_value=0.9,
            estimated_improvement_percent=10.0,
            implementation_steps=[
                "Add quality assessment step",
                "Enable human-in-the-loop for edge cases",
                "Use ensemble of models for critical steps"
            ],
            expected_outcome={"quality_improvement": 0.1}
        )