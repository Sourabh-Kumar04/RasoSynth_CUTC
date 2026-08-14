"""
Observability & Monitoring

Metrics collection, worker monitoring, GPU monitoring, and distributed tracing.
"""

import asyncio
import time
from typing import Optional, Any, List, Dict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import psutil


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """A single metric data point."""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    labels: dict = field(default_factory=dict)
    unit: str = ""


@dataclass
class WorkerMetrics:
    """Metrics for a worker node."""
    worker_id: str
    timestamp: datetime
    # CPU
    cpu_percent: float = 0.0
    cpu_cores_used: int = 0
    # Memory
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    memory_percent: float = 0.0
    # Tasks
    tasks_active: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    # Latency
    avg_task_duration_ms: float = 0.0
    # Network
    bytes_sent: int = 0
    bytes_recv: int = 0


@dataclass
class GPUMetrics:
    """Metrics for GPU monitoring."""
    gpu_id: int
    timestamp: datetime
    # Memory
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    memory_percent: float = 0.0
    # Compute
    utilization_percent: float = 0.0
    # Temperature
    temperature_celsius: float = 0.0
    # Power
    power_watts: float = 0.0
    # Metrics
    inference_count: int = 0
    avg_inference_time_ms: float = 0.0


class MetricsCollector:
    """Collects and aggregates metrics."""

    def __init__(self):
        self._metrics: dict[str, List[Metric]] = {}
        self._aggregations: dict[str, dict] = {}
        self._exporters: list = []

    def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: dict = None,
        unit: str = ""
    ) -> None:
        """Record a metric."""
        metric = Metric(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=datetime.utcnow(),
            labels=labels or {},
            unit=unit,
        )

        if name not in self._metrics:
            self._metrics[name] = []

        self._metrics[name].append(metric)

        # Update aggregation
        self._update_aggregation(name, value)

    def _update_aggregation(self, name: str, value: float) -> None:
        """Update aggregated statistics."""
        if name not in self._aggregations:
            self._aggregations[name] = {
                "count": 0,
                "sum": 0.0,
                "min": float('inf'),
                "max": float('-inf'),
                "avg": 0.0,
            }

        agg = self._aggregations[name]
        agg["count"] += 1
        agg["sum"] += value
        agg["min"] = min(agg["min"], value)
        agg["max"] = max(agg["max"], value)
        agg["avg"] = agg["sum"] / agg["count"]

    def get_metric(self, name: str, since: datetime = None) -> List[Metric]:
        """Get metrics for a name."""
        metrics = self._metrics.get(name, [])
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
        return metrics

    def get_aggregation(self, name: str) -> Optional[dict]:
        """Get aggregated statistics."""
        return self._aggregations.get(name)

    def get_all_metrics(self) -> dict:
        """Get all metrics with aggregations."""
        return {
            name: {
                "count": len(metrics),
                "aggregations": self._aggregations.get(name, {}),
                "recent": [m.value for m in metrics[-10:]],
            }
            for name, metrics in self._metrics.items()
        }

    def clear(self, older_than: datetime = None) -> None:
        """Clear old metrics."""
        if older_than:
            for name in self._metrics:
                self._metrics[name] = [
                    m for m in self._metrics[name]
                    if m.timestamp >= older_than
                ]
        else:
            self._metrics.clear()
            self._aggregations.clear()


class WorkerMonitor:
    """Monitors worker nodes."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self._workers: dict[str, WorkerMetrics] = {}

    async def collect_metrics(self, worker_id: str) -> WorkerMetrics:
        """Collect metrics for a worker."""
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        metrics = WorkerMetrics(
            worker_id=worker_id,
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_percent,
            cpu_cores_used=psutil.cpu_count() * cpu_percent / 100,
            memory_used_gb=memory.used / (1024**3),
            memory_total_gb=memory.total / (1024**3),
            memory_percent=memory.percent,
            tasks_active=self._get_active_tasks(worker_id),
            tasks_completed=self._get_completed_tasks(worker_id),
            tasks_failed=self._get_failed_tasks(worker_id),
        )

        self._workers[worker_id] = metrics

        # Record metrics
        self.metrics.record("worker_cpu_percent", cpu_percent, labels={"worker_id": worker_id})
        self.metrics.record("worker_memory_percent", memory.percent, labels={"worker_id": worker_id})
        self.metrics.record("worker_tasks_active", metrics.tasks_active, labels={"worker_id": worker_id})

        return metrics

    def _get_active_tasks(self, worker_id: str) -> int:
        """Get number of active tasks."""
        return 0  # Would integrate with task queue

    def _get_completed_tasks(self, worker_id: str) -> int:
        """Get number of completed tasks."""
        return 0

    def _get_failed_tasks(self, worker_id: str) -> int:
        """Get number of failed tasks."""
        return 0

    def get_worker_status(self, worker_id: str) -> Optional[dict]:
        """Get worker status."""
        metrics = self._workers.get(worker_id)
        if not metrics:
            return None

        return {
            "worker_id": worker_id,
            "status": "healthy" if metrics.cpu_percent < 90 else "degraded",
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "active_tasks": metrics.tasks_active,
        }

    def get_cluster_status(self) -> dict:
        """Get cluster-wide status."""
        if not self._workers:
            return {"status": "no_workers"}

        total_cpu = sum(w.cpu_percent for w in self._workers.values()) / len(self._workers)
        total_memory = sum(w.memory_percent for w in self._workers.values()) / len(self._workers)
        total_active = sum(w.tasks_active for w in self._workers.values())

        healthy = sum(1 for w in self._workers.values() if w.cpu_percent < 90)
        degraded = len(self._workers) - healthy

        return {
            "status": "healthy" if degraded == 0 else "degraded",
            "total_workers": len(self._workers),
            "healthy_workers": healthy,
            "degraded_workers": degraded,
            "avg_cpu_percent": total_cpu,
            "avg_memory_percent": total_memory,
            "total_active_tasks": total_active,
        }


class GPUMonitor:
    """Monitors GPU utilization."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self._gpu_metrics: dict[int, GPUMetrics] = {}
        self._monitoring_enabled = False

    async def start_monitoring(self) -> None:
        """Start GPU monitoring."""
        self._monitoring_enabled = True
        asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self) -> None:
        """Stop GPU monitoring."""
        self._monitoring_enabled = False

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self._monitoring_enabled:
            try:
                await self._collect_gpu_metrics()
            except Exception:
                pass

            await asyncio.sleep(5)  # Collect every 5 seconds

    async def _collect_gpu_metrics(self) -> None:
        """Collect GPU metrics."""
        try:
            import torch

            if not torch.cuda.is_available():
                return

            for i in range(torch.cuda.device_count()):
                memory_allocated = torch.cuda.memory_allocated(i) / 1e9
                memory_total = torch.cuda.get_device_properties(i).total_memory / 1e9

                metrics = GPUMetrics(
                    gpu_id=i,
                    timestamp=datetime.utcnow(),
                    memory_used_gb=memory_allocated,
                    memory_total_gb=memory_total,
                    memory_percent=(memory_allocated / memory_total) * 100 if memory_total > 0 else 0,
                    utilization_percent=0,  # Would use nvidia-smi
                    temperature_celsius=0,
                    power_watts=0,
                )

                self._gpu_metrics[i] = metrics

                # Record metrics
                self.metrics.record("gpu_memory_percent", metrics.memory_percent, labels={"gpu_id": str(i)})
                self.metrics.record("gpu_memory_used_gb", metrics.memory_used_gb, labels={"gpu_id": str(i)})

        except ImportError:
            pass

    def get_gpu_metrics(self, gpu_id: int) -> Optional[GPUMetrics]:
        """Get metrics for a specific GPU."""
        return self._gpu_metrics.get(gpu_id)

    def get_all_gpu_metrics(self) -> dict:
        """Get metrics for all GPUs."""
        return {
            gpu_id: {
                "memory_percent": m.memory_percent,
                "memory_used_gb": m.memory_used_gb,
                "memory_total_gb": m.memory_total_gb,
                "utilization_percent": m.utilization_percent,
            }
            for gpu_id, m in self._gpu_metrics.items()
        }

    def get_gpu_summary(self) -> dict:
        """Get GPU summary."""
        if not self._gpu_metrics:
            return {"status": "no_gpus", "total_gpus": 0}

        total_memory = sum(m.memory_total_gb for m in self._gpu_metrics.values())
        used_memory = sum(m.memory_used_gb for m in self._gpu_metrics.values())
        avg_utilization = sum(m.utilization_percent for m in self._gpu_metrics.values()) / len(self._gpu_metrics)

        return {
            "status": "healthy" if avg_utilization < 95 else "hot",
            "total_gpus": len(self._gpu_metrics),
            "total_memory_gb": total_memory,
            "used_memory_gb": used_memory,
            "avg_utilization_percent": avg_utilization,
        }


class PipelineTracer:
    """Distributed tracing for pipeline execution."""

    def __init__(self):
        self._traces: dict[str, List[dict]] = {}
        self._spans: dict[str, List[dict]] = {}

    def start_trace(self, trace_id: str, pipeline_id: str) -> None:
        """Start a new trace."""
        self._traces[trace_id] = [{
            "type": "trace_start",
            "pipeline_id": pipeline_id,
            "timestamp": datetime.utcnow().isoformat(),
        }]

    def start_span(
        self,
        trace_id: str,
        span_id: str,
        stage_name: str,
        parent_span_id: str = None
    ) -> None:
        """Start a new span."""
        if trace_id not in self._spans:
            self._spans[trace_id] = []

        self._spans[trace_id].append({
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "stage_name": stage_name,
            "start_time": datetime.utcnow().isoformat(),
            "status": "started",
        })

    def end_span(
        self,
        trace_id: str,
        span_id: str,
        status: str = "completed",
        result: dict = None
    ) -> None:
        """End a span."""
        if trace_id not in self._spans:
            return

        for span in self._spans[trace_id]:
            if span["span_id"] == span_id:
                span["end_time"] = datetime.utcnow().isoformat()
                span["status"] = status
                if result:
                    span["result"] = result

                # Calculate duration
                from datetime import datetime
                start = datetime.fromisoformat(span["start_time"])
                end = datetime.fromisoformat(span["end_time"])
                span["duration_ms"] = (end - start).total_seconds() * 1000

                break

    def add_event(
        self,
        trace_id: str,
        span_id: str,
        event_name: str,
        event_data: dict = None
    ) -> None:
        """Add an event to a span."""
        if trace_id not in self._spans:
            return

        for span in self._spans[trace_id]:
            if span["span_id"] == span_id:
                if "events" not in span:
                    span["events"] = []
                span["events"].append({
                    "name": event_name,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": event_data,
                })
                break

    def end_trace(self, trace_id: str, status: str = "completed") -> None:
        """End a trace."""
        if trace_id in self._traces:
            self._traces[trace_id].append({
                "type": "trace_end",
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
            })

    def get_trace(self, trace_id: str) -> Optional[dict]:
        """Get a complete trace."""
        if trace_id not in self._traces:
            return None

        return {
            "trace_id": trace_id,
            "spans": self._spans.get(trace_id, []),
            "events": self._traces.get(trace_id, []),
        }

    def get_trace_summary(self, trace_id: str) -> Optional[dict]:
        """Get summary of a trace."""
        trace = self.get_trace(trace_id)
        if not trace:
            return None

        spans = trace["spans"]
        total_duration = sum(s.get("duration_ms", 0) for s in spans)

        return {
            "trace_id": trace_id,
            "total_spans": len(spans),
            "total_duration_ms": total_duration,
            "avg_span_duration_ms": total_duration / max(len(spans), 1),
        }


class PrometheusExporter:
    """Export metrics to Prometheus."""

    def __init__(self, port: int = 9090):
        self.port = port
        self._collector = None

    def set_collector(self, collector: MetricsCollector) -> None:
        """Set metrics collector."""
        self._collector = collector

    def to_prometheus_format(self) -> str:
        """Convert metrics to Prometheus format."""
        if not self._collector:
            return ""

        lines = []
        for name, data in self._collector.get_all_metrics().items():
            agg = data["aggregations"]

            # Gauge metrics
            lines.append(f"# HELP {name} {name}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {agg.get('avg', 0)}")

        return "\n".join(lines)