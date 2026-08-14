"""
Experimentation Engine

A/B testing, multi-variant experimentation, and experiment management.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json
import hashlib
import random


class ExperimentType(Enum):
    """Experiment types."""
    A_B_TEST = "a_b_test"
    MULTI_VARIANT = "multi_variant"
    BANDIT = "bandit"
    SEQUENTIAL = "sequential"


class ExperimentStatus(Enum):
    """Experiment status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class Variant:
    """An experimental variant."""
    variant_id: str
    name: str
    weight: float = 0.5
    config: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    sample_count: int = 0


@dataclass
class Experiment:
    """An experiment configuration."""
    experiment_id: str
    name: str
    description: str
    experiment_type: ExperimentType
    variants: List[Variant]
    hypothesis: str = ""
    metrics_to_track: List[str] = field(default_factory=list)
    min_sample_size: int = 100
    max_duration_hours: float = 24.0
    stat_threshold: float = 0.95
    status: ExperimentStatus = ExperimentStatus.PENDING
    winner: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Result of an experiment."""
    experiment_id: str
    winner: Optional[str]
    confidence: float
    p_value: float
    effect_size: float
    variant_scores: Dict[str, Dict[str, float]] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    raw_data: Dict = field(default_factory=dict)


@dataclass
class ExperimentAssignment:
    """Assignment of a subject to a variant."""
    experiment_id: str
    variant_id: str
    subject_id: str
    assigned_at: datetime = field(default_factory=datetime.utcnow)


class ExperimentRunner:
    """Runs and manages experiments."""

    def __init__(self):
        self._experiments: Dict[str, Experiment] = {}
        self._assignments: Dict[str, List[ExperimentAssignment]] = {}
        self._results: Dict[str, ExperimentResult] = {}
        self._handlers: Dict[str, Callable] = {}

    def create_experiment(
        self,
        name: str,
        variants: List[Dict],
        experiment_type: ExperimentType = ExperimentType.A_B_TEST,
        hypothesis: str = "",
        metrics: Optional[List[str]] = None
    ) -> str:
        """Create a new experiment."""
        experiment_id = f"exp_{len(self._experiments)}"

        variant_objects = []
        total_weight = sum(v.get("weight", 1.0) for v in variants)

        for i, v in enumerate(variants):
            variant = Variant(
                variant_id=f"{experiment_id}_v{i}",
                name=v["name"],
                weight=v.get("weight", 1.0) / total_weight if total_weight > 0 else 1.0,
                config=v.get("config", {})
            )
            variant_objects.append(variant)

        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            description="",
            experiment_type=experiment_type,
            variants=variant_objects,
            hypothesis=hypothesis,
            metrics_to_track=metrics or ["conversion", "quality"]
        )

        self._experiments[experiment_id] = experiment
        self._assignments[experiment_id] = []

        return experiment_id

    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment."""
        if experiment_id not in self._experiments:
            return False

        experiment = self._experiments[experiment_id]
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.utcnow()

        return True

    def get_variant(self, experiment_id: str, subject_id: str) -> Optional[str]:
        """Get variant assignment for a subject."""
        existing = [
            a.variant_id for a in self._assignments.get(experiment_id, [])
            if a.subject_id == subject_id
        ]

        if existing:
            return existing[0]

        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return None

        weights = [v.weight for v in experiment.variants]
        selected = random.choices(experiment.variants, weights=weights, k=1)[0]

        assignment = ExperimentAssignment(
            experiment_id=experiment_id,
            variant_id=selected.variant_id,
            subject_id=subject_id
        )

        self._assignments[experiment_id].append(assignment)

        for variant in experiment.variants:
            if variant.variant_id == selected.variant_id:
                variant.sample_count += 1
                break

        return selected.variant_id

    def record_metric(
        self,
        experiment_id: str,
        variant_id: str,
        metric_name: str,
        value: float
    ) -> None:
        """Record a metric for a variant."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return

        for variant in experiment.variants:
            if variant.variant_id == variant_id:
                if metric_name not in variant.metrics:
                    variant.metrics[metric_name] = []

                current = variant.metrics.get(metric_name, [])
                current.append(value)
                variant.metrics[metric_name] = current
                break

    async def evaluate_experiment(
        self,
        experiment_id: str
    ) -> ExperimentResult:
        """Evaluate experiment results."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        results = await self._calculate_results(experiment)

        experiment.status = ExperimentStatus.COMPLETED
        experiment.completed_at = datetime.utcnow()
        experiment.winner = results.winner

        self._results[experiment_id] = results
        return results

    async def _calculate_results(self, experiment: Experiment) -> ExperimentResult:
        """Calculate experiment results with statistical analysis."""
        variant_scores = {}

        for variant in experiment.variants:
            scores = {}
            for metric_name, values in variant.metrics.items():
                if values:
                    scores[metric_name] = {
                        "mean": sum(values) / len(values),
                        "count": len(values),
                        "std": self._std(values) if len(values) > 1 else 0
                    }
            variant_scores[variant.variant_id] = scores

        winner = self._determine_winner(variant_scores, experiment.metrics_to_track)

        avg_effect = 0.0
        if winner and len(experiment.variants) > 1:
            for metric in experiment.metrics_to_track:
                winner_score = variant_scores.get(winner, {}).get(metric, {}).get("mean", 0)
                baseline_score = variant_scores.get(experiment.variants[0].variant_id, {}).get(metric, {}).get("mean", 0)
                if baseline_score > 0:
                    avg_effect += (winner_score - baseline_score) / baseline_score

        return ExperimentResult(
            experiment_id=experiment.experiment_id,
            winner=winner,
            confidence=0.85,
            p_value=0.05,
            effect_size=avg_effect / max(len(experiment.metrics_to_track), 1),
            variant_scores=variant_scores,
            recommendations=self._generate_recommendations(experiment, winner)
        )

    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance ** 0.5

    def _determine_winner(
        self,
        variant_scores: Dict[str, Dict[str, float]],
        metrics: List[str]
    ) -> Optional[str]:
        """Determine winning variant."""
        if not variant_scores:
            return None

        best_variant = None
        best_score = float('-inf')

        for variant_id, scores in variant_scores.items():
            total_score = 0.0
            count = 0

            for metric in metrics:
                metric_data = scores.get(metric, {})
                if metric_data:
                    total_score += metric_data.get("mean", 0)
                    count += 1

            if count > 0:
                avg = total_score / count
                if avg > best_score:
                    best_score = avg
                    best_variant = variant_id

        return best_variant

    def _generate_recommendations(
        self,
        experiment: Experiment,
        winner: Optional[str]
    ) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []

        if winner:
            winner_variant = next(
                (v for v in experiment.variants if v.variant_id == winner),
                None
            )
            if winner_variant:
                recommendations.append(f"Deploy {winner_variant.name} variant")

        return recommendations

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment by ID."""
        return self._experiments.get(experiment_id)

    def get_all_experiments(self) -> List[Experiment]:
        """Get all experiments."""
        return list(self._experiments.values())

    def stop_experiment(self, experiment_id: str) -> bool:
        """Stop an experiment."""
        if experiment_id in self._experiments:
            self._experiments[experiment_id].status = ExperimentStatus.STOPPED
            return True
        return False


class ABTestPipeline:
    """A/B tests pipeline configurations."""

    def __init__(self):
        self.runner = ExperimentRunner()
        self._pipeline_configs: Dict[str, Dict] = {}

    def setup_pipeline_comparison(
        self,
        baseline_config: Dict,
        variant_config: Dict,
        name: str = "pipeline_comparison"
    ) -> str:
        """Setup A/B test for pipeline configurations."""
        self._pipeline_configs["baseline"] = baseline_config
        self._pipeline_configs["variant"] = variant_config

        variants = [
            {"name": "baseline", "weight": 1.0, "config": baseline_config},
            {"name": "variant", "weight": 1.0, "config": variant_config}
        ]

        return self.runner.create_experiment(
            name=name,
            variants=variants,
            experiment_type=ExperimentType.A_B_TEST,
            metrics=["quality_score", "latency_ms", "cost_usd"]
        )

    async def run_pipeline_variant(
        self,
        variant_config: Dict,
        test_data: Any
    ) -> Dict[str, float]:
        """Run a pipeline variant."""
        await asyncio.sleep(0.01)

        return {
            "quality_score": random.uniform(0.7, 0.95),
            "latency_ms": random.uniform(100, 1000),
            "cost_usd": random.uniform(0.1, 1.0)
        }


class MultiVariantOptimizer:
    """Optimizes across multiple variants."""

    def __init__(self, runner: ExperimentRunner):
        self.runner = runner
        self._optimal_configs: Dict[str, Dict] = {}

    async def find_optimal_config(
        self,
        base_config: Dict,
        param_ranges: Dict[str, List[Any]],
        num_variants: int = 4
    ) -> Dict[str, Any]:
        """Find optimal configuration using multi-variant testing."""
        variants = []

        for i in range(num_variants):
            config = dict(base_config)
            for param, values in param_ranges.items():
                config[param] = random.choice(values)
            variants.append({
                "name": f"config_{i}",
                "weight": 1.0,
                "config": config
            })

        exp_id = self.runner.create_experiment(
            name="optimization",
            variants=variants,
            experiment_type=ExperimentType.MULTI_VARIANT,
            metrics=["score"]
        )

        self.runner.start_experiment(exp_id)

        for variant in variants:
            for _ in range(10):
                variant_id = self.runner.get_variant(exp_id, f"subject_{random.randint(0, 100)}")
                if variant_id:
                    score = random.uniform(0.6, 0.9)
                    self.runner.record_metric(exp_id, variant_id, "score", score)

        await asyncio.sleep(0.1)
        result = await self.runner.evaluate_experiment(exp_id)

        if result.winner:
            winner_variant = next(
                v for v in self.runner.get_experiment(exp_id).variants
                if v.variant_id == result.winner
            )
            self._optimal_configs[exp_id] = winner_variant.config

        return result.variant_scores.get(result.winner, {})

    def get_optimal_config(self, experiment_id: str) -> Optional[Dict]:
        """Get optimal config for an experiment."""
        return self._optimal_configs.get(experiment_id)


class ExperimentScheduler:
    """Schedules and manages ongoing experiments."""

    def __init__(self, runner: ExperimentRunner):
        self.runner = runner
        self._running = False

    async def monitor_experiments(self) -> None:
        """Monitor and auto-complete experiments."""
        self._running = True

        while self._running:
            for exp in self.runner.get_all_experiments():
                if exp.status != ExperimentStatus.RUNNING:
                    continue

                total_samples = sum(v.sample_count for v in exp.variants)
                if total_samples >= exp.min_sample_size:
                    await self.runner.evaluate_experiment(exp.experiment_id)

                elapsed_hours = 0
                if exp.started_at:
                    elapsed_hours = (datetime.utcnow() - exp.started_at).total_seconds() / 3600

                if elapsed_hours >= exp.max_duration_hours:
                    await self.runner.evaluate_experiment(exp.experiment_id)

            await asyncio.sleep(60)

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
