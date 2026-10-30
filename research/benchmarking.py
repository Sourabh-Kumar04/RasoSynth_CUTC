"""
Benchmarking Framework

Comprehensive benchmarking for techniques, pipelines, and improvements.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio
import json
import math
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
    """Result of a single metric.

    ``confidence_interval`` is the 95% confidence interval for the
    DIFFERENCE of means (variant - baseline), from a Welch t-test — not
    an interval for either mean alone. ``p_value`` is the two-sided Welch
    p-value (None when it cannot be computed, e.g. fewer than 2 samples
    per side, or for single-observation comparisons).
    """
    name: str
    baseline_value: float
    variant_value: float
    improvement_percent: float
    is_significant: bool = False
    confidence_interval: tuple = (0.0, 0.0)
    statistical_test: str = "welch_t_test"
    p_value: Optional[float] = None


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


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    max_iter = 200
    epsilon = 3.0e-14
    fpmin = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < epsilon:
            break
    return h


def _betainc_reg(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log(1.0 - x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _t_cdf(t: float, df: float) -> float:
    """CDF of Student's t distribution with df degrees of freedom."""
    x = df / (df + t * t)
    ib = _betainc_reg(df / 2.0, 0.5, x)
    return 1.0 - 0.5 * ib if t >= 0 else 0.5 * ib


def _t_critical_95(df: float) -> float:
    """Two-sided 95% critical value of Student's t (bisection on the CDF)."""
    if df <= 0:
        return float("nan")
    lo, hi = 0.0, 1.0
    while _t_cdf(hi, df) < 0.975:
        hi *= 2.0
        if hi > 1e6:
            return hi
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if _t_cdf(mid, df) < 0.975:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def welch_t_test(baseline: List[float], variant: List[float]) -> Dict[str, Any]:
    """Welch two-sample t-test (two-sided) for the difference of means.

    Returns t_statistic, Welch-Satterthwaite df, two-sided p_value, the
    mean difference (variant - baseline), its standard error, and the 95%
    confidence interval for that difference. When either side has fewer
    than 2 samples, no test is possible: p_value is None and the interval
    is (0.0, 0.0). When both sides are constant, the p-value is 1.0 for
    equal means and 0.0 otherwise, with a zero-width interval.
    """
    nb, nv = len(baseline), len(variant)
    if nb < 2 or nv < 2:
        return {
            "t_statistic": 0.0, "df": 0.0, "p_value": None,
            "mean_diff": 0.0, "standard_error": 0.0,
            "ci_low": 0.0, "ci_high": 0.0,
        }
    mean_b = statistics.mean(baseline)
    mean_v = statistics.mean(variant)
    var_b = statistics.variance(baseline)
    var_v = statistics.variance(variant)
    diff = mean_v - mean_b
    se = math.sqrt(var_b / nb + var_v / nv)
    if se == 0.0:
        if diff == 0.0:
            return {"t_statistic": 0.0, "df": 0.0, "p_value": 1.0,
                    "mean_diff": 0.0, "standard_error": 0.0,
                    "ci_low": 0.0, "ci_high": 0.0}
        return {"t_statistic": float("inf") if diff > 0 else float("-inf"),
                "df": 0.0, "p_value": 0.0, "mean_diff": diff,
                "standard_error": 0.0, "ci_low": diff, "ci_high": diff}
    t_stat = diff / se
    num = (var_b / nb + var_v / nv) ** 2
    den = (var_b / nb) ** 2 / (nb - 1) + (var_v / nv) ** 2 / (nv - 1)
    df = num / den if den > 0 else 0.0
    p_value = 2.0 * (1.0 - _t_cdf(abs(t_stat), df)) if df > 0 else None
    if p_value is not None:
        p_value = min(1.0, max(0.0, p_value))
    t_crit = _t_critical_95(df) if df > 0 else 0.0
    margin = t_crit * se
    return {
        "t_statistic": t_stat, "df": df, "p_value": p_value,
        "mean_diff": diff, "standard_error": se,
        "ci_low": diff - margin, "ci_high": diff + margin,
    }


class BenchmarkRunner:
    """Runs benchmarks with statistical validation (real Welch t-tests).

    Significance is a two-sided Welch t-test at alpha = 0.05 and the
    confidence interval is for the difference of means. With the default
    of 5 iterations the test has low power and normality is not assessed:
    treat non-significant results as "not demonstrated", not as proof of
    no difference.
    """

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
            started_at=datetime.now(timezone.utc)
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

        comparison.completed_at = datetime.now(timezone.utc)
        return comparison

    def _calculate_metric(
        self,
        name: str,
        baseline: List[float],
        variant: List[float]
    ) -> MetricResult:
        """Calculate metric with a real Welch t-test for significance."""
        baseline_mean = statistics.mean(baseline) if baseline else 0.0
        variant_mean = statistics.mean(variant) if variant else 0.0

        if baseline_mean == 0:
            improvement = 0.0
        else:
            improvement = ((variant_mean - baseline_mean) / baseline_mean) * 100

        test = welch_t_test(baseline, variant)
        p_value = test["p_value"]
        is_significant = p_value is not None and p_value < 0.05

        return MetricResult(
            name=name,
            baseline_value=baseline_mean,
            variant_value=variant_mean,
            improvement_percent=improvement,
            is_significant=is_significant,
            confidence_interval=(test["ci_low"], test["ci_high"]),
            statistical_test="welch_t_test" if p_value is not None else "welch_t_test_insufficient_data",
            p_value=p_value,
        )

    def _is_significant(
        self,
        baseline: List[float],
        variant: List[float],
        alpha: float = 0.05
    ) -> bool:
        """Check statistical significance with a two-sided Welch t-test.

        The old implementation returned True for any >5% mean difference;
        that was not a significance test. Now: p < alpha, or False when
        the test cannot be computed.
        """
        p_value = welch_t_test(baseline, variant)["p_value"]
        return p_value is not None and p_value < alpha

    def _calculate_ci(
        self,
        baseline: List[float],
        variant: List[float]
    ) -> tuple:
        """Calculate the 95% confidence interval for the DIFFERENCE of means.

        The old implementation pooled both samples into one interval for
        their combined mean, which answers a different question and hid
        whether the variant actually differs from baseline.
        """
        test = welch_t_test(baseline, variant)
        return (test["ci_low"], test["ci_high"])

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
        """Generate recommendation based on results.

        A "Deploy variant" recommendation now requires at least one
        statistically significant metric: a large but non-significant
        mean difference is reported as not demonstrated, not deployed.
        """
        if comparison.status == BenchmarkStatus.FAILED:
            return f"Benchmark failed: {comparison.error}"

        if not comparison.metrics:
            return "No metrics - no recommendation possible"
        significant = sum(1 for m in comparison.metrics if m.is_significant)
        if significant == 0:
            return "No statistically significant difference - keep baseline on this evidence"
        if comparison.overall_score > 5:
            return f"Deploy variant - {comparison.overall_score:.1f}% overall improvement ({significant}/{len(comparison.metrics)} metrics significant)"
        elif comparison.overall_score > 0:
            return f"Consider variant - marginal {comparison.overall_score:.1f}% improvement ({significant}/{len(comparison.metrics)} metrics significant)"
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
        """Calculate quality metric with a real Welch t-test.

        The old version hardcoded the interval (0.8, 1.0) and called any
        >5% improvement "significant"; both are replaced by the Welch test
        on the per-output values.
        """
        baseline_mean = statistics.mean(baseline) if baseline else 0
        variant_mean = statistics.mean(variant) if variant else 0

        improvement = ((variant_mean - baseline_mean) / max(baseline_mean, 0.01)) * 100
        test = welch_t_test(baseline, variant)
        p_value = test["p_value"]

        return MetricResult(
            name=name,
            baseline_value=baseline_mean,
            variant_value=variant_mean,
            improvement_percent=improvement,
            is_significant=p_value is not None and p_value < 0.05,
            confidence_interval=(test["ci_low"], test["ci_high"]),
            statistical_test="welch_t_test" if p_value is not None else "welch_t_test_insufficient_data",
            p_value=p_value,
        )


class CostBenchmark:
    """Benchmarks cost efficiency."""

    async def benchmark_cost(
        self,
        baseline_usage: Dict,
        variant_usage: Dict
    ) -> Dict[str, MetricResult]:
        """Benchmark cost between baseline and variant.

        Inputs are single observations per metric, so no significance test
        or confidence interval can be computed: is_significant is always
        False and the test is labelled not-applicable. The old version
        called any >10% improvement "significant", which it was not.
        """
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
                is_significant=False,
                confidence_interval=(0.0, 0.0),
                statistical_test="not_applicable_single_observation",
                p_value=None,
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

        mean_test = welch_t_test(baseline_latencies, variant_latencies)
        mean_p = mean_test["p_value"]
        results = {
            "mean_latency": MetricResult(
                name="mean_latency",
                baseline_value=baseline_mean,
                variant_value=variant_mean,
                improvement_percent=((baseline_mean - variant_mean) / max(baseline_mean, 1)) * 100,
                is_significant=mean_p is not None and mean_p < 0.05,
                confidence_interval=(mean_test["ci_low"], mean_test["ci_high"]),
                statistical_test="welch_t_test" if mean_p is not None else "welch_t_test_insufficient_data",
                p_value=mean_p,
            ),
            "p50_latency": MetricResult(
                name="p50_latency",
                baseline_value=p50_baseline,
                variant_value=p50_variant,
                improvement_percent=((p50_baseline - p50_variant) / max(p50_baseline, 1)) * 100,
                is_significant=False,
                confidence_interval=(0.0, 0.0),
                statistical_test="not_applicable_single_observation",
                p_value=None,
            ),
            "p95_latency": MetricResult(
                name="p95_latency",
                baseline_value=p95_baseline,
                variant_value=p95_variant,
                improvement_percent=((p95_baseline - p95_variant) / max(p95_baseline, 1)) * 100,
                is_significant=False,
                confidence_interval=(0.0, 0.0),
                statistical_test="not_applicable_single_observation",
                p_value=None,
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
