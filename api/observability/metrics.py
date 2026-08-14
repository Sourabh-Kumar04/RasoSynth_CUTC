"""
API Observability & Metrics

API metrics, validation metrics, and orchestration metrics
for monitoring and observability.
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio
import time


@dataclass
class MetricPoint:
    """Individual metric data point."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class APIMetrics:
    """API-level metrics collector."""

    def __init__(self):
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._request_latencies: Dict[str, List[float]] = defaultdict(list)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._response_sizes: Dict[str, List[int]] = defaultdict(list)

        self._validation_counts: Dict[str, int] = defaultdict(int)
        self._validation_latencies: List[float] = []

        self._start_time = datetime.utcnow()

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        response_size: Optional[int] = None
    ) -> None:
        """Record API request metrics."""
        key = f"{method}:{endpoint}"
        self._request_counts[key] += 1
        self._request_latencies[key].append(latency_ms)

        if status_code >= 400:
            self._error_counts[key] += 1

        if response_size is not None:
            self._response_sizes[key].append(response_size)

    def record_validation(self, duration_ms: float, result: str) -> None:
        """Record validation metrics."""
        self._validation_latencies.append(duration_ms)
        self._validation_counts[result] += 1

    def get_request_rate(self, endpoint: Optional[str] = None) -> float:
        """Get requests per second."""
        uptime = (datetime.utcnow() - self._start_time).total_seconds()
        if uptime == 0:
            return 0.0

        if endpoint:
            total = self._request_counts.get(endpoint, 0)
        else:
            total = sum(self._request_counts.values())

        return total / uptime

    def get_avg_latency(self, endpoint: Optional[str] = None) -> float:
        """Get average request latency."""
        if endpoint:
            latencies = self._request_latencies.get(endpoint, [])
        else:
            latencies = [l for latencies in self._request_latencies.values() for l in latencies]

        return sum(latencies) / len(latencies) if latencies else 0.0

    def get_p50_latency(self, endpoint: Optional[str] = None) -> float:
        """Get P50 latency."""
        latencies = self._get_latencies(endpoint)
        if not latencies:
            return 0.0

        sorted_latencies = sorted(latencies)
        idx = int(len(sorted_latencies) * 0.5)
        return sorted_latencies[idx]

    def get_p95_latency(self, endpoint: Optional[str] = None) -> float:
        """Get P95 latency."""
        latencies = self._get_latencies(endpoint)
        if not latencies:
            return 0.0

        sorted_latencies = sorted(latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx]

    def get_p99_latency(self, endpoint: Optional[str] = None) -> float:
        """Get P99 latency."""
        latencies = self._get_latencies(endpoint)
        if not latencies:
            return 0.0

        sorted_latencies = sorted(latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx]

    def _get_latencies(self, endpoint: Optional[str] = None) -> List[float]:
        """Get latencies for endpoint or all endpoints."""
        if endpoint:
            return self._request_latencies.get(endpoint, [])
        return [l for latencies in self._request_latencies.values() for l in latencies]

    def get_error_rate(self, endpoint: Optional[str] = None) -> float:
        """Get error rate percentage."""
        if endpoint:
            errors = self._error_counts.get(endpoint, 0)
            total = self._request_counts.get(endpoint, 0)
        else:
            errors = sum(self._error_counts.values())
            total = sum(self._request_counts.values())

        return (errors / total * 100) if total > 0 else 0.0

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "total_requests": sum(self._request_counts.values()),
            "total_errors": sum(self._error_counts.values()),
            "error_rate_percent": self.get_error_rate(),
            "avg_latency_ms": self.get_avg_latency(),
            "p50_latency_ms": self.get_p50_latency(),
            "p95_latency_ms": self.get_p95_latency(),
            "p99_latency_ms": self.get_p99_latency(),
            "requests_per_second": self.get_request_rate(),
            "validation_stats": {
                "total_validations": sum(self._validation_counts.values()),
                "validation_errors": self._validation_counts.get("error", 0),
                "validation_warnings": self._validation_counts.get("warning", 0),
                "avg_validation_ms": sum(self._validation_latencies) / len(self._validation_latencies) if self._validation_latencies else 0
            }
        }


class ValidationMetrics:
    """Metrics for validation operations."""

    def __init__(self):
        self._constraint_checks: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._conflict_detections: Dict[str, int] = defaultdict(int)
        self._feasibility_scores: List[float] = []
        self._validation_issues: Dict[str, int] = defaultdict(int)

        self._semantic_analysis_times: List[float] = []
        self._constraint_inference_count = 0

    def record_constraint_check(
        self,
        constraint_type: str,
        result: str
    ) -> None:
        """Record constraint check result."""
        self._constraint_checks[constraint_type][result] += 1

    def record_conflict(self, conflict_type: str) -> None:
        """Record detected constraint conflict."""
        self._conflict_detections[conflict_type] += 1

    def record_feasibility(
        self,
        score: float,
        level: str
    ) -> None:
        """Record feasibility evaluation."""
        self._feasibility_scores.append(score)
        self._validation_issues[f"feasibility_{level}"] += 1

    def record_validation_issue(
        self,
        severity: str,
        issue_type: str
    ) -> None:
        """Record validation issue."""
        key = f"{severity}_{issue_type}"
        self._validation_issues[key] += 1

    def record_semantic_analysis_time(self, duration_ms: float) -> None:
        """Record semantic analysis duration."""
        self._semantic_analysis_times.append(duration_ms)

    def record_constraint_inference(self) -> None:
        """Record constraint inference."""
        self._constraint_inference_count += 1

    def get_constraint_success_rate(self, constraint_type: str) -> float:
        """Get success rate for a constraint type."""
        checks = self._constraint_checks.get(constraint_type, {})
        total = sum(checks.values())
        if total == 0:
            return 0.0

        return checks.get("success", 0) / total * 100

    def get_avg_feasibility_score(self) -> float:
        """Get average feasibility score."""
        return sum(self._feasibility_scores) / len(self._feasibility_scores) if self._feasibility_scores else 0.0

    def get_summary(self) -> Dict[str, Any]:
        """Get validation metrics summary."""
        return {
            "total_constraint_checks": sum(
                sum(checks.values()) for checks in self._constraint_checks.values()
            ),
            "total_conflicts_detected": sum(self._conflict_detections.values()),
            "avg_feasibility_score": self.get_avg_feasibility_score(),
            "total_issues": sum(self._validation_issues.values()),
            "issue_breakdown": dict(self._validation_issues),
            "conflict_breakdown": dict(self._conflict_detections),
            "avg_semantic_analysis_ms": (
                sum(self._semantic_analysis_times) / len(self._semantic_analysis_times)
                if self._semantic_analysis_times else 0
            ),
            "constraint_inferences": self._constraint_inference_count
        }


class OrchestrationMetrics:
    """Metrics for orchestration and workflow execution."""

    def __init__(self):
        self._workflow_counts: Dict[str, int] = defaultdict(int)
        self._workflow_durations: Dict[str, List[float]] = defaultdict(list)
        self._workflow_costs: Dict[str, List[float]] = defaultdict(list)
        self._step_durations: Dict[str, List[float]] = defaultdict(list)

        self._task_counts: Dict[str, int] = defaultdict(int)
        self._task_success_rates: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        self._provider_usage: Dict[str, int] = defaultdict(int)
        self._provider_latencies: Dict[str, List[float]] = defaultdict(list)
        self._provider_errors: Dict[str, int] = defaultdict(int)

        self._gpu_utilization: List[float] = []
        self._memory_utilization: List[float] = []

    def record_workflow(
        self,
        workflow_id: str,
        duration_seconds: float,
        cost_usd: float
    ) -> None:
        """Record workflow execution."""
        self._workflow_counts[workflow_id] += 1
        self._workflow_durations[workflow_id].append(duration_seconds)
        self._workflow_costs[workflow_id].append(cost_usd)

    def record_step(
        self,
        step_id: str,
        duration_seconds: float
    ) -> None:
        """Record workflow step execution."""
        self._step_durations[step_id].append(duration_seconds)

    def record_task(
        self,
        task_id: str,
        success: bool,
        duration_seconds: Optional[float] = None
    ) -> None:
        """Record task execution."""
        self._task_counts[task_id] += 1
        result = "success" if success else "failure"
        self._task_success_rates[task_id][result] += 1

    def record_provider_usage(
        self,
        provider: str,
        latency_ms: float,
        success: bool
    ) -> None:
        """Record provider usage."""
        self._provider_usage[provider] += 1
        self._provider_latencies[provider].append(latency_ms)
        if not success:
            self._provider_errors[provider] += 1

    def record_resource_utilization(
        self,
        gpu_percent: float,
        memory_percent: float
    ) -> None:
        """Record resource utilization."""
        self._gpu_utilization.append(gpu_percent)
        self._memory_utilization.append(memory_percent)

    def get_workflow_success_rate(self, workflow_id: str) -> float:
        """Get success rate for a workflow."""
        rates = self._task_success_rates.get(workflow_id, {})
        total = sum(rates.values())
        if total == 0:
            return 0.0

        return rates.get("success", 0) / total * 100

    def get_provider_success_rate(self, provider: str) -> float:
        """Get success rate for a provider."""
        total = self._provider_usage[provider]
        errors = self._provider_errors[provider]
        if total == 0:
            return 0.0

        return ((total - errors) / total) * 100

    def get_avg_provider_latency(self, provider: str) -> float:
        """Get average latency for a provider."""
        latencies = self._provider_latencies.get(provider, [])
        return sum(latencies) / len(latencies) if latencies else 0.0

    def get_resource_utilization_stats(self) -> Dict[str, Any]:
        """Get resource utilization statistics."""
        return {
            "avg_gpu_percent": sum(self._gpu_utilization) / len(self._gpu_utilization) if self._gpu_utilization else 0,
            "avg_memory_percent": sum(self._memory_utilization) / len(self._memory_utilization) if self._memory_utilization else 0,
            "peak_gpu_percent": max(self._gpu_utilization) if self._gpu_utilization else 0,
            "peak_memory_percent": max(self._memory_utilization) if self._memory_utilization else 0
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get orchestration metrics summary."""
        return {
            "total_workflows": sum(self._workflow_counts.values()),
            "total_tasks": sum(self._task_counts.values()),
            "total_provider_requests": sum(self._provider_usage.values()),
            "total_provider_errors": sum(self._provider_errors.values()),
            "provider_breakdown": dict(self._provider_usage),
            "avg_workflow_duration": (
                sum(d for durations in self._workflow_durations.values() for d in durations) /
                max(1, sum(len(d) for d in self._workflow_durations.values()))
            ),
            "resource_utilization": self.get_resource_utilization_stats()
        }


class MetricsCollector:
    """Centralized metrics collection."""

    def __init__(self):
        self.api_metrics = APIMetrics()
        self.validation_metrics = ValidationMetrics()
        self.orchestration_metrics = OrchestrationMetrics()

        self._export_interval_seconds = 60
        self._last_export = datetime.utcnow()

    async def export_metrics(self) -> Dict[str, Any]:
        """Export all metrics."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "api": self.api_metrics.get_summary(),
            "validation": self.validation_metrics.get_summary(),
            "orchestration": self.orchestration_metrics.get_summary()
        }

    def record_request_metrics(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float
    ) -> None:
        """Record all request-related metrics."""
        self.api_metrics.record_request(endpoint, method, status_code, latency_ms)

    def record_validation_metrics(
        self,
        duration_ms: float,
        result: str,
        constraint_type: Optional[str] = None
    ) -> None:
        """Record validation metrics."""
        self.api_metrics.record_validation(duration_ms, result)
        if constraint_type:
            self.validation_metrics.record_constraint_check(constraint_type, result)

    def record_workflow_metrics(
        self,
        workflow_id: str,
        duration_seconds: float,
        cost_usd: float,
        success: bool
    ) -> None:
        """Record workflow metrics."""
        self.orchestration_metrics.record_workflow(workflow_id, duration_seconds, cost_usd)
        self.orchestration_metrics.record_task(workflow_id, success, duration_seconds)