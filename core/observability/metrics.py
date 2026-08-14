"""
Metrics Collection System

Comprehensive metrics collection with Prometheus support, time-series
analytics, and distributed infrastructure monitoring.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json


class MetricTypes(Enum):
    """Metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    metric_type: MetricTypes
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class GaugeMetrics:
    """Gauge metric that can go up and down."""
    name: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def set(self, value: float) -> None:
        """Set gauge value."""
        self.value = value
        self.last_updated = datetime.utcnow()

    def increment(self, delta: float = 1.0) -> None:
        """Increment gauge."""
        self.value += delta
        self.last_updated = datetime.utcnow()

    def decrement(self, delta: float = 1.0) -> None:
        """Decrement gauge."""
        self.value -= delta
        self.last_updated = datetime.utcnow()


@dataclass
class CounterMetrics:
    """Counter metric that only increases."""
    name: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    total: float = 0.0

    def increment(self, delta: float = 1.0) -> None:
        """Increment counter."""
        self.value += delta
        self.total += delta

    def reset(self) -> None:
        """Reset counter value."""
        self.value = 0.0


@dataclass
class HistogramMetrics:
    """Histogram metric for distributions."""
    name: str
    values: List[float] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    bucket_boundaries: List[float] = field(default_factory=list)
    max_size: int = 10000

    def observe(self, value: float) -> None:
        """Observe a value."""
        self.values.append(value)
        if len(self.values) > self.max_size:
            self.values = self.values[-self.max_size:]

    def get_stats(self) -> Dict[str, float]:
        """Get histogram statistics."""
        if not self.values:
            return {}

        sorted_vals = sorted(self.values)
        n = len(sorted_vals)

        return {
            "count": n,
            "sum": sum(sorted_vals),
            "avg": sum(sorted_vals) / n,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "p50": sorted_vals[int(n * 0.5)],
            "p90": sorted_vals[int(n * 0.9)],
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[int(n * 0.99)] if n > 1 else sorted_vals[-1],
        }


class MetricsCollector:
    """Comprehensive metrics collector."""

    def __init__(self):
        self._gauges: Dict[str, GaugeMetrics] = {}
        self._counters: Dict[str, CounterMetrics] = {}
        self._histograms: Dict[str, HistogramMetrics] = {}
        self._series: Dict[str, List[MetricPoint]] = {}
        self._exporters: List[Callable] = []
        self._aggregation_interval_seconds = 60

    def gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        unit: str = ""
    ) -> None:
        """Record a gauge metric."""
        key = self._make_key(name, labels or {})
        if key not in self._gauges:
            self._gauges[key] = GaugeMetrics(name=name, labels=labels or {})
        self._gauges[key].set(value)

        self._record_point(name, value, MetricTypes.GAUGE, labels or {}, unit)

    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter."""
        key = self._make_key(name, labels or {})
        if key not in self._counters:
            self._counters[key] = CounterMetrics(name=name, labels=labels or {})
        self._counters[key].increment(value)

        self._record_point(name, self._counters[key].total, MetricTypes.COUNTER, labels or {})

    def histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe a histogram value."""
        key = self._make_key(name, labels or {})
        if key not in self._histograms:
            self._histograms[key] = HistogramMetrics(name=name, labels=labels or {})
        self._histograms[key].observe(value)

        self._record_point(name, value, MetricTypes.HISTOGRAM, labels or {})

    def _make_key(self, name: str, labels: Dict[str, str]) -> str:
        """Make metric key from name and labels."""
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}" if label_str else name

    def _record_point(
        self,
        name: str,
        value: float,
        metric_type: MetricTypes,
        labels: Dict[str, str],
        unit: str = ""
    ) -> None:
        """Record a metric point."""
        point = MetricPoint(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=datetime.utcnow(),
            labels=labels,
            unit=unit
        )

        if name not in self._series:
            self._series[name] = []
        self._series[name].append(point)

        # Trim old points (keep last hour)
        cutoff = datetime.utcnow() - timedelta(hours=1)
        self._series[name] = [p for p in self._series[name] if p.timestamp > cutoff]

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get current gauge value."""
        key = self._make_key(name, labels or {})
        return self._gauges.get(key, {}).value if key in self._gauges else None

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get counter total."""
        key = self._make_key(name, labels or {})
        return self._counters.get(key, CounterMetrics(name=name)).total

    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, labels or {})
        if key in self._histograms:
            return self._histograms[key].get_stats()
        return {}

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        return {
            "gauges": {
                k: v.value for k, v in self._gauges.items()
            },
            "counters": {
                k: v.total for k, v in self._counters.items()
            },
            "histograms": {
                k: v.get_stats() for k, v in self._histograms.items()
            }
        }

    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        # Gauges
        for key, gauge in self._gauges.items():
            lines.append(f"# HELP {gauge.name} Gauge metric")
            lines.append(f"# TYPE {gauge.name} gauge")
            label_str = ",".join(f'{k}="{v}"' for k, v in gauge.labels.items())
            lines.append(f"{gauge.name}{{{label_str}}} {gauge.value}")

        # Counters
        for key, counter in self._counters.items():
            lines.append(f"# HELP {counter.name} Counter metric")
            lines.append(f"# TYPE {counter.name} counter")
            label_str = ",".join(f'{k}="{v}"' for k, v in counter.labels.items())
            lines.append(f"{counter.name}_total{{{label_str}}} {counter.total}")

        # Histograms
        for key, histogram in self._histograms.items():
            lines.append(f"# HELP {histogram.name} Histogram metric")
            lines.append(f"# TYPE {histogram.name} histogram")
            label_str = ",".join(f'{k}="{v}"' for k, v in histogram.labels.items())
            stats = histogram.get_stats()
            for bucket in ["0.5", "0.9", "0.95", "0.99", "1.0"]:
                pkey = bucket.replace("0.", "p")
                if pkey in stats:
                    bucket_value = stats[pkey]
                    lines.append(f'{histogram.name}_bucket{{le="{bucket}",{label_str}}} {bucket_value}')

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics."""
        self._gauges.clear()
        self._counters.clear()
        self._histograms.clear()
        self._series.clear()


class InfrastructureMetrics:
    """Infrastructure-specific metrics."""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    def record_request(
        self,
        provider: str,
        model: str,
        latency_ms: float,
        tokens: int,
        cost_usd: float,
        status: str
    ) -> None:
        """Record API request metrics."""
        labels = {"provider": provider, "model": model, "status": status}

        self.collector.histogram("api_request_latency_ms", latency_ms, labels)
        self.collector.gauge("api_request_last_latency_ms", latency_ms, labels)
        self.collector.counter("api_requests_total", 1.0, labels)
        self.collector.counter("api_tokens_total", float(tokens), labels)
        self.collector.gauge("api_cost_usd", cost_usd, labels)

    def record_gpu_usage(
        self,
        gpu_id: str,
        utilization_percent: float,
        memory_used_gb: float,
        memory_total_gb: float
    ) -> None:
        """Record GPU metrics."""
        labels = {"gpu_id": gpu_id}

        self.collector.gauge("gpu_utilization_percent", utilization_percent, labels)
        self.collector.gauge("gpu_memory_used_gb", memory_used_gb, labels)
        self.collector.gauge("gpu_memory_percent", (memory_used_gb / memory_total_gb) * 100 if memory_total_gb > 0 else 0, labels)

    def record_cache_operation(
        self,
        operation: str,
        category: str,
        hit: bool,
        latency_ms: float
    ) -> None:
        """Record cache metrics."""
        labels = {"operation": operation, "category": category, "result": "hit" if hit else "miss"}

        self.collector.counter("cache_operations_total", 1.0, labels)
        self.collector.histogram("cache_latency_ms", latency_ms, {"operation": operation})

    def record_agent_execution(
        self,
        agent_type: str,
        agent_id: str,
        duration_ms: float,
        success: bool
    ) -> None:
        """Record agent execution metrics."""
        labels = {"agent_type": agent_type, "success": str(success)}

        self.collector.histogram("agent_execution_duration_ms", duration_ms, labels)
        self.collector.counter("agent_executions_total", 1.0, labels)


class CostMetrics:
    """Cost tracking metrics."""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self._provider_costs: Dict[str, float] = {}
        self._provider_tokens: Dict[str, int] = {}

    def record_cost(
        self,
        provider: str,
        model: str,
        cost_usd: float,
        tokens_used: int
    ) -> None:
        """Record API cost."""
        self._provider_costs[provider] = self._provider_costs.get(provider, 0) + cost_usd
        self._provider_tokens[provider] = self._provider_tokens.get(provider, 0) + tokens_used

        self.collector.gauge("cost_total_usd", sum(self._provider_costs.values()))
        self.collector.gauge(f"cost_{provider}_usd", self._provider_costs[provider])
        self.collector.gauge(f"tokens_{provider}_total", self._provider_tokens[provider])

    def get_provider_costs(self) -> Dict[str, float]:
        """Get costs by provider."""
        return dict(self._provider_costs)

    def get_total_cost(self) -> float:
        """Get total cost."""
        return sum(self._provider_costs.values())