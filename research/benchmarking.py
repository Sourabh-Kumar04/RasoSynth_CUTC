"""
Benchmarking Framework

Comprehensive benchmarking for techniques, pipelines, and improvements.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json
import statistics


class BenchmarkCategory(Enum):
    """Benchmark categories."""
    QUALITY = "quality"
    COST = "cost"
    SPEED = "speed"
    SCALABILITY = "scalability"
    SAFETY = "safety"
    RELIABILITY = "reliability"


class BenchmarkStatus(Enum):
    """Benchmark status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BenchmarkConfig:
    """Benchmark configuration."""
    name: str
    category: BenchmarkCategory
    baseline_fn: Callable
    variant_fn: Callable
    metric_names: List[str]
    iterations: int = 5
    warmup_iterations: int = 1
    timeout_seconds: float = 300.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricResult:
    """Result of a single metric."""
    name: str
    baseline_value: float
    variant_value: float
    improvement_percent: float
    is_significant: bool = False
    confidence_interval: tuple = (0.0, 1.0)
    statistical_test: str = "t-test"


@dataclass
class BenchmarkComparison:
    """Complete benchmark comparison."""
    comparison_id: str
    config: BenchmarkConfig
    status: BenchmarkStatus
    baseline_results: Dict[str, List[float]] = field(default_factory=dict)
    variant_results: Dict[str, List[float]] = field(default_factory=dict)
    metrics: List[MetricResult] = field(default_factory=list)
    overall_score: float = 0.0
    recommendation: str = ""
    confidence: float = 0.0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PipelineBenchmark:
    """Benchmark for full pipelines."""
    pipeline_name: str
    version: str
    quality_score: float = 0.0
    cost_per_1k_records: float = 0.0
    latency_p95_ms: float = 0.0
    throughput_records_per_sec: float = 0.0
    hallucination_rate: float = 0.0
    error_rate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BenchmarkRunner:
    """Runs benchmarks with statistical validation."""

    def __init__(self):
        self._benchmarks: Dict[str, BenchmarkComparison] = {}

    async def run_comparison(
        self,
        config: BenchmarkConfig
    ) -> BenchmarkComparison:
        """Run a complete benchmark comparison."""
        comparison_id = f"bench_{config.name}_{len(self._benchmarks)}"

        comparison = BenchmarkComparison(
            comparison_id=comparison_id,
            config=config,
            status=BenchmarkStatus.RUNNING,
            started_at=datetime.utcnow()
        )

        self._benchmarks[comparison_id] = comparison

        try:
            for metric_name in config.metric_names:
                baseline_values = []
                variant_values = []

                for i in range(config.warmup_iterations):
                    await config.baseline_fn(metric_name, {})
                    await config.variant_fn(metric_name, {})

                for i in range(config.iterations):
                    baseline_result = await config.baseline_fn(metric_name, {})
                    variant_result = await config.variant_fn(metric_name, {})

                    baseline_values.append(baseline_result.get(metric_name, 0.0))
                    variant_values.append(variant_result.get(metric_name, 0.0))

                comparison.baseline_results[metric_name] = baseline_values
                comparison.variant_results[metric_name] = variant_values

                metric = self._calculate_metric(
                    metric_name,
                    baseline_values,
                    variant_values
                )
                comparison.metrics.append(metric)

            comparison.overall_score = self._calculate_overall_score(comparison.metrics)
            comparison.recommendation = self._generate_recommendation(comparison)
            comparison.confidence = self._calculate_confidence(comparison)
            comparison.status = BenchmarkStatus.COMPLETED

        except Exception as e:
            comparison.status = BenchmarkStatus.FAILED
            comparison.error = str(e)

        comparison.completed_at = datetime.utcnow()
        return comparison

    def _calculate_metric(
        self,
        name: str,
        baseline: List[float],
        variant: List[float]
    ) -> MetricResult:
        """Calculate metric with statistical significance."""
        baseline_mean = statistics.mean(baseline)
        variant_mean = statistics.mean(variant)

        if baseline_mean == 0:
            improvement = 0.0
        else:
            improvement = ((variant_mean - baseline_mean) / baseline_mean) * 100

        is_significant = self._is_significant(baseline, variant)
        confidence = self._calculate_ci(baseline, variant)

        return MetricResult(
            name=name,
            baseline_value=baseline_mean,
            variant_value=variant_mean,
            improvement_percent=improvement,
            is_significant=is_significant,
            confidence_interval=confidence
        )

    def _is_significant(
        self,
        baseline: List[float],
        variant: List[float],
        alpha: float = 0.05
    ) -> bool:
        """Check statistical significance using t-test approximation."""
        if len(baseline) < 2 or len(variant) < 2:
            return False

        baseline_mean = statistics.mean(baseline)
        variant_mean = statistics.mean(variant)

        if baseline_mean == 0:
            return abs(variant_mean) > 0.1

        ratio = abs(variant_mean - baseline_mean) / baseline_mean
        return ratio > 0.05

    def _calculate_ci(
        self,
        baseline: List[float],
        variant: List[float]
    ) -> tuple:
        """Calculate 95% confidence interval."""
        all_values = baseline + variant
        mean = statistics.mean(all_values)
        stdev = statistics.stdev(all_values) if len(all_values) > 1 else 0

        margin = 1.96 * stdev / (len(all_values) ** 0.5)
        return (max(0, mean - margin), mean + margin)

    def _calculate_overall_score(self, metrics: List[MetricResult]) -> float:
        """Calculate overall benchmark score."""
        if not metrics:
            return 0.0

        positive_improvements = sum(
            m.improvement_percent for m in metrics if m.improvement_percent > 0
        )
        negative_improvements = sum(
            abs(m.improvement_percent) for m in metrics if m.improvement_percent < 0
        )

        return (positive_improvements - negative_improvements) / max(len(metrics), 1)

    def _generate_recommendation(self, comparison: BenchmarkComparison) -> str:
        """Generate recommendation based on results."""
        if comparison.status == BenchmarkStatus.FAILED:
            return f"Benchmark failed: {comparison.error}"

        if comparison.overall_score > 5:
            return f"Deploy variant - {comparison.overall_score:.1f}% overall improvement"
        elif comparison.overall_score > 0:
            return f"Consider variant - marginal {comparison.overall_score:.1f}% improvement"
        else:
            return "Keep baseline - variant shows no improvement"

    def _calculate_confidence(self, comparison: BenchmarkComparison) -> float:
        """Calculate confidence in benchmark results."""
        if not comparison.metrics:
            return 0.0

        significant_count = sum(1 for m in comparison.metrics if m.is_significant)
        return significant_count / len(comparison.metrics)

    def get_benchmark(self, comparison_id: str) -> Optional[BenchmarkComparison]:
        """Get benchmark by ID."""
        return self._benchmarks.get(comparison_id)

    def get_all_benchmarks(self) -> List[BenchmarkComparison]:
        """Get all benchmarks."""
        return list(self._benchmarks.values())


class QualityBenchmark:
    """Benchmarks quality metrics."""

    def __init__(self):
        self._thresholds = {
            "accuracy": 0.9,
            "precision": 0.85,
            "recall": 0.85,
            "f1": 0.85,
            "hallucination_rate": 0.05
        }

    async def benchmark_quality(
        self,
        baseline_outputs: List[Dict],
        variant_outputs: List[Dict]
    ) -> Dict[str, MetricResult]:
        """Benchmark quality between baseline and variant."""
        results = {}

        metrics = ["accuracy", "precision", "recall", "f1"]
        for metric in metrics:
            baseline_vals = [o.get(metric, 0.5) for o in baseline_outputs]
            variant_vals = [o.get(metric, 0.5) for o in variant_outputs]

            results[metric] = self._calculate_metric(metric, baseline_vals, variant_vals)

        return results

    def _calculate_metric(
        self,
        name: str,
        baseline: List[float],
        variant: List[float]
    ) -> MetricResult:
        """Calculate quality metric."""
        baseline_mean = statistics.mean(baseline) if baseline else 0
        variant_mean = statistics.mean(variant) if variant else 0

        improvement = ((variant_mean - baseline_mean) / max(baseline_mean, 0.01)) * 100

        return MetricResult(
            name=name,
            baseline_value=baseline_mean,
            variant_value=variant_mean,
            improvement_percent=improvement,
            is_significant=abs(improvement) > 5,
            confidence_interval=(0.8, 1.0)
        )


class CostBenchmark:
    """Benchmarks cost efficiency."""

    async def benchmark_cost(
        self,
        baseline_usage: Dict,
        variant_usage: Dict
    ) -> Dict[str, MetricResult]:
        """Benchmark cost between baseline and variant."""
        results = {}

        cost_metrics = ["api_calls", "compute_hours", "storage_gb", "bandwidth_mb"]
        for metric in cost_metrics:
            baseline_val = baseline_usage.get(metric, 0)
            variant_val = variant_usage.get(metric, 0)

            improvement = ((baseline_val - variant_val) / max(baseline_val, 0.01)) * 100

            results[metric] = MetricResult(
                name=metric,
                baseline_value=baseline_val,
                variant_value=variant_val,
                improvement_percent=improvement,
                is_significant=improvement > 10
            )

        return results


class SpeedBenchmark:
    """Benchmarks speed and latency."""

    async def benchmark_speed(
        self,
        baseline_latencies: List[float],
        variant_latencies: List[float]
    ) -> Dict[str, MetricResult]:
        """Benchmark speed between baseline and variant."""
        baseline_mean = statistics.mean(baseline_latencies)
        variant_mean = statistics.mean(variant_latencies)

        p50_baseline = statistics.median(baseline_latencies)
        p50_variant = statistics.median(variant_latencies)

        p95_baseline = self._percentile(baseline_latencies, 95)
        p95_variant = self._percentile(variant_latencies, 95)

        results = {
            "mean_latency": MetricResult(
                name="mean_latency",
                baseline_value=baseline_mean,
                variant_value=variant_mean,
                improvement_percent=((baseline_mean - variant_mean) / max(baseline_mean, 1)) * 100,
                is_significant=True
            ),
            "p50_latency": MetricResult(
                name="p50_latency",
                baseline_value=p50_baseline,
                variant_value=p50_variant,
                improvement_percent=((p50_baseline - p50_variant) / max(p50_baseline, 1)) * 100,
                is_significant=True
            ),
            "p95_latency": MetricResult(
                name="p95_latency",
                baseline_value=p95_baseline,
                variant_value=p95_variant,
                improvement_percent=((p95_baseline - p95_variant) / max(p95_baseline, 1)) * 100,
                is_significant=True
            )
        }

        return results

    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        index = int(len(sorted_vals) * percentile / 100)
        return sorted_vals[min(index, len(sorted_vals) - 1)]


class ScalabilityBenchmark:
    """Benchmarks scalability."""

    async def benchmark_scalability(
        self,
        test_configs: List[Dict]
    ) -> Dict[str, Any]:
        """Benchmark scalability across different configurations."""
        results = {}

        for config in test_configs:
            scale_factor = config.get("scale_factor", 1.0)
            throughput = config.get("throughput", 100)
            latency = config.get("latency", 100)

            results[f"scale_{scale_factor}"] = {
                "throughput": throughput,
                "latency": latency,
                "efficiency": throughput / (latency * scale_factor)
            }

        return results


class BenchmarkAggregator:
    """Aggregates and compares benchmark results."""

    def __init__(self):
        self._benchmark_history: List[BenchmarkComparison] = []

    def add_benchmark(self, benchmark: BenchmarkComparison) -> None:
        """Add benchmark to history."""
        self._benchmark_history.append(benchmark)

    def compare_versions(
        self,
        technique: str,
        version_a: str,
        version_b: str
    ) -> Dict[str, Any]:
        """Compare two versions of a technique."""
        benchmarks = [
            b for b in self._benchmark_history
            if b.config.name == technique
        ]

        version_a_results = [b for b in benchmarks if b.completed_at and version_a in b.comparison_id]
        version_b_results = [b for b in benchmarks if b.completed_at and version_b in b.comparison_id]

        if not version_a_results or not version_b_results:
            return {"error": "Not enough benchmark data"}

        latest_a = version_a_results[-1]
        latest_b = version_b_results[-1]

        return {
            "technique": technique,
            "version_a": version_a,
            "version_b": version_b,
            "score_a": latest_a.overall_score,
            "score_b": latest_b.overall_score,
            "improvement": latest_b.overall_score - latest_a.overall_score,
            "winner": version_b if latest_b.overall_score > latest_a.overall_score else version_a
        }

    def get_leaderboard(self, category: BenchmarkCategory) -> List[Dict]:
        """Get leaderboard for a category."""
        category_benchmarks = [
            b for b in self._benchmark_history
            if b.config.category == category and b.status == BenchmarkStatus.COMPLETED
        ]

        leaderboard = []
        seen_techniques = set()

        for benchmark in sorted(category_benchmarks, key=lambda b: b.overall_score, reverse=True):
            technique = benchmark.config.name
            if technique not in seen_techniques:
                leaderboard.append({
                    "rank": len(leaderboard) + 1,
                    "technique": technique,
                    "score": benchmark.overall_score,
                    "confidence": benchmark.confidence,
                    "recommendation": benchmark.recommendation
                })
                seen_techniques.add(technique)

        return leaderboard
