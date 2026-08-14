"""
Cache Observability - Metrics, monitoring, and analytics

Prometheus/Grafana integration, OpenTelemetry support, and comprehensive
cache observability for the distributed caching layer.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import time


class MetricType(Enum):
    """Types of observability metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class CacheMetric:
    """A cache metric data point."""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class CacheHealthStatus:
    """Health status of the cache system."""
    status: str  # healthy, degraded, critical
    l1_healthy: bool = True
    l2_healthy: bool = True
    l3_healthy: bool = True
    l4_healthy: bool = True
    memory_percent: float = 0.0
    hit_rate: float = 0.0
    avg_latency_ms: float = 0.0
    issues: List[str] = field(default_factory=list)


class CacheMetricsCollector:
    """Collects comprehensive cache metrics."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client

        self._metrics: Dict[str, List[CacheMetric]] = {}
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}

    def record_hit(
        self,
        category: str = "default",
        layer: str = "l2",
        semantic: bool = False
    ) -> None:
        """Record a cache hit."""
        self._counters[f"cache_hits_{category}_{layer}"] = \
            self._counters.get(f"cache_hits_{category}_{layer}", 0) + 1

        if semantic:
            self._counters["cache_semantic_hits"] = \
                self._counters.get("cache_semantic_hits", 0) + 1

    def record_miss(
        self,
        category: str = "default",
        layer: str = "l2"
    ) -> None:
        """Record a cache miss."""
        self._counters[f"cache_misses_{category}_{layer}"] = \
            self._counters.get(f"cache_misses_{category}_{layer}", 0) + 1

    def record_write(
        self,
        category: str = "default",
        size_bytes: int = 0
    ) -> None:
        """Record a cache write."""
        self._counters[f"cache_writes_{category}"] = \
            self._counters.get(f"cache_writes_{category}", 0) + 1

        if size_bytes > 0:
            self._counters[f"cache_bytes_written_{category}"] = \
                self._counters.get(f"cache_bytes_written_{category}", 0) + size_bytes

    def record_latency(
        self,
        operation: str,
        latency_ms: float,
        layer: str = "l2"
    ) -> None:
        """Record operation latency."""
        key = f"latency_{operation}_{layer}"
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(latency_ms)

    def record_tokens_saved(self, tokens: int, category: str = "llm") -> None:
        """Record tokens saved through caching."""
        self._counters[f"tokens_saved_{category}"] = \
            self._counters.get(f"tokens_saved_{category}", 0) + tokens

    def record_cost_saved(self, cost_usd: float, category: str = "llm") -> None:
        """Record cost saved through caching."""
        self._counters[f"cost_saved_usd_{category}"] = \
            self._counters.get(f"cost_saved_usd_{category}", 0) + cost_usd

    def set_gauge(self, name: str, value: float, **labels) -> None:
        """Set a gauge value."""
        key = f"{name}:{':'.join(f'{k}={v}' for k, v in labels.items())}"
        self._gauges[key] = value

    def get_hit_rate(self, category: Optional[str] = None) -> float:
        """Calculate cache hit rate."""
        if category:
            hits = self._counters.get(f"cache_hits_{category}_l2", 0)
            misses = self._counters.get(f"cache_misses_{category}_l2", 0)
        else:
            hits = sum(v for k, v in self._counters.items() if "cache_hits" in k)
            misses = sum(v for k, v in self._counters.items() if "cache_misses" in k)

        total = hits + misses
        return hits / max(total, 1)

    def get_avg_latency(self, operation: str) -> float:
        """Get average latency for operation."""
        key = f"latency_{operation}_l2"
        values = self._histograms.get(key, [])
        return sum(values) / max(len(values), 1) if values else 0.0

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: {
                    "count": len(v),
                    "avg": sum(v) / max(len(v), 1),
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0,
                    "p50": sorted(v)[len(v) // 2] if v else 0,
                    "p95": sorted(v)[int(len(v) * 0.95)] if v else 0,
                    "p99": sorted(v)[int(len(v) * 0.99)] if v else 0,
                }
                for k, v in self._histograms.items()
            },
            "hit_rate": self.get_hit_rate(),
            "total_tokens_saved": sum(
                v for k, v in self._counters.items() if "tokens_saved" in k
            ),
            "total_cost_saved": sum(
                v for k, v in self._counters.items() if "cost_saved" in k
            )
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()

    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        # Counters
        for name, value in self._counters.items():
            safe_name = name.replace(".", "_").replace("-", "_")
            lines.append(f"# HELP {safe_name} Cache counter metric")
            lines.append(f"# TYPE {safe_name} counter")
            lines.append(f"{safe_name} {value}")

        # Gauges
        for name, value in self._gauges.items():
            safe_name = name.replace(".", "_").replace("-", "_").replace(":", "_")
            lines.append(f"# HELP {safe_name} Cache gauge metric")
            lines.append(f"# TYPE {safe_name} gauge")
            lines.append(f"{safe_name} {value}")

        return "\n".join(lines)


class CacheObservabilityManager:
    """Manages comprehensive cache observability."""

    def __init__(
        self,
        redis_client: Any,
        metrics_collector: CacheMetricsCollector
    ):
        self.redis = redis_client
        self.metrics = metrics_collector

        self._alerts: List[Dict] = []
        self._alert_thresholds = {
            "hit_rate_min": 0.7,
            "latency_max_ms": 100,
            "memory_percent_max": 85,
            "error_rate_max": 0.05
        }

    async def collect_health_status(self) -> CacheHealthStatus:
        """Collect current health status."""
        try:
            memory_info = await self.redis.info("memory")
            memory_percent = memory_info.get("used_memory_percent", 0)
        except Exception:
            memory_percent = 0

        hit_rate = self.metrics.get_hit_rate()
        avg_latency = self.metrics.get_avg_latency("get")

        issues = []
        status = "healthy"

        if hit_rate < self._alert_thresholds["hit_rate_min"]:
            issues.append(f"Low hit rate: {hit_rate:.2%}")
            status = "degraded"

        if avg_latency > self._alert_thresholds["latency_max_ms"]:
            issues.append(f"High latency: {avg_latency:.2f}ms")
            status = "degraded"

        if memory_percent > self._alert_thresholds["memory_percent_max"]:
            issues.append(f"High memory usage: {memory_percent:.1f}%")
            status = "critical"

        return CacheHealthStatus(
            status=status,
            memory_percent=memory_percent,
            hit_rate=hit_rate,
            avg_latency_ms=avg_latency,
            issues=issues
        )

    async def check_and_alert(self) -> List[Dict]:
        """Check metrics and generate alerts."""
        alerts = []
        health = await self.collect_health_status()

        if health.status == "critical":
            alerts.append({
                "level": "critical",
                "message": "Cache system is critical",
                "details": health.issues,
                "timestamp": datetime.utcnow().isoformat()
            })
        elif health.status == "degraded":
            alerts.append({
                "level": "warning",
                "message": "Cache system is degraded",
                "details": health.issues,
                "timestamp": datetime.utcnow().isoformat()
            })

        self._alerts.extend(alerts)
        return alerts

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for observability dashboard."""
        metrics = self.metrics.get_all_metrics()

        return {
            "overview": {
                "hit_rate": metrics["hit_rate"],
                "total_hits": sum(
                    v for k, v in metrics["counters"].items()
                    if "cache_hits" in k
                ),
                "total_misses": sum(
                    v for k, v in metrics["counters"].items()
                    if "cache_misses" in k
                ),
                "tokens_saved": metrics["total_tokens_saved"],
                "cost_saved_usd": metrics["total_cost_saved"],
            },
            "latency": {
                "avg_get_ms": metrics["histograms"].get("latency_get_l2", {}).get("avg", 0),
                "p95_get_ms": metrics["histograms"].get("latency_get_l2", {}).get("p95", 0),
                "avg_set_ms": metrics["histograms"].get("latency_set_l2", {}).get("avg", 0),
            },
            "categories": self._get_category_stats(),
            "layers": self._get_layer_stats(),
        }

    def _get_category_stats(self) -> Dict[str, Any]:
        """Get statistics by category."""
        categories = ["llm", "embeddings", "web", "ocr", "dedup", "validation"]
        stats = {}

        for cat in categories:
            hits = sum(
                v for k, v in self.metrics._counters.items()
                if f"cache_hits_{cat}" in k
            )
            misses = sum(
                v for k, v in self.metrics._counters.items()
                if f"cache_misses_{cat}" in k
            )

            stats[cat] = {
                "hits": hits,
                "misses": misses,
                "hit_rate": hits / max(hits + misses, 1)
            }

        return stats

    def _get_layer_stats(self) -> Dict[str, Any]:
        """Get statistics by cache layer."""
        return {
            "l1_memory": {
                "enabled": True,
                "estimated_size_mb": 50  # Would come from actual stats
            },
            "l2_redis": {
                "enabled": True,
                "keys": "N/A"  # Would come from actual Redis info
            },
            "l3_persistent": {
                "enabled": True
            },
            "l4_semantic": {
                "enabled": True,
                "entries": 0
            }
        }


class PrometheusExporter:
    """Exports cache metrics to Prometheus."""

    def __init__(self, port: int = 9090):
        self.port = port
        self._collector = None

    def set_collector(self, collector: CacheMetricsCollector) -> None:
        """Set metrics collector."""
        self._collector = collector

    def to_prometheus_format(self) -> str:
        """Convert metrics to Prometheus format."""
        if not self._collector:
            return ""

        return self._collector.to_prometheus_format()


class OpenTelemetryIntegration:
    """OpenTelemetry integration for distributed tracing."""

    def __init__(self):
        self._traces: Dict[str, List[Dict]] = {}
        self._spans: Dict[str, List[Dict]] = {}

    def start_trace(
        self,
        trace_id: str,
        operation: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Start a distributed trace."""
        self._traces[trace_id] = [{
            "type": "start",
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }]

    def add_span(
        self,
        trace_id: str,
        span_name: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict] = None
    ) -> str:
        """Add a span to a trace."""
        span_id = f"span_{len(self._spans.get(trace_id, []))}"

        span = {
            "span_id": span_id,
            "name": span_name,
            "parent_span_id": parent_span_id,
            "start_time": datetime.utcnow().isoformat(),
            "attributes": attributes or {}
        }

        if trace_id not in self._spans:
            self._spans[trace_id] = []
        self._spans[trace_id].append(span)

        return span_id

    def end_span(
        self,
        trace_id: str,
        span_id: str,
        status: str = "ok",
        result: Optional[Any] = None
    ) -> None:
        """End a span."""
        if trace_id not in self._spans:
            return

        for span in self._spans[trace_id]:
            if span["span_id"] == span_id:
                span["end_time"] = datetime.utcnow().isoformat()
                span["status"] = status
                if result:
                    span["result"] = str(result)[:100]

                from datetime import datetime
                start = datetime.fromisoformat(span["start_time"])
                end = datetime.fromisoformat(span["end_time"])
                span["duration_ms"] = (end - start).total_seconds() * 1000
                break

    def end_trace(self, trace_id: str, status: str = "ok") -> None:
        """End a trace."""
        if trace_id in self._traces:
            self._traces[trace_id].append({
                "type": "end",
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            })

    def get_trace(self, trace_id: str) -> Optional[Dict]:
        """Get a complete trace."""
        return {
            "trace_id": trace_id,
            "spans": self._spans.get(trace_id, []),
            "events": self._traces.get(trace_id, [])
        }

    def get_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        """Get trace summary."""
        trace = self.get_trace(trace_id)
        if not trace or not trace["spans"]:
            return {}

        spans = trace["spans"]
        total_duration = sum(s.get("duration_ms", 0) for s in spans)

        return {
            "trace_id": trace_id,
            "total_spans": len(spans),
            "total_duration_ms": total_duration,
            "avg_span_duration_ms": total_duration / len(spans)
        }