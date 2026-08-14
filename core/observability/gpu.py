"""
GPU & Distributed Infrastructure Monitoring

Deep GPU observability, VRAM tracking, inference metrics, and
distributed Ray cluster monitoring.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio


class GPUStatus(Enum):
    """GPU status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class GPUInfo:
    """GPU information."""
    gpu_id: int
    name: str = ""
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    utilization_percent: float = 0.0
    temperature_celsius: float = 0.0
    power_watts: float = 0.0
    status: GPUStatus = GPUStatus.UNKNOWN
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def memory_percent(self) -> float:
        """Calculate memory usage percentage."""
        if self.memory_total_gb == 0:
            return 0.0
        return (self.memory_used_gb / self.memory_total_gb) * 100


@dataclass
class InferenceMetrics:
    """Inference performance metrics."""
    model_name: str
    gpu_id: int
    batch_size: int
    input_tokens: int
    output_tokens: int
    inference_time_ms: float
    throughput_tokens_per_sec: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VRAMAllocation:
    """VRAM allocation tracking."""
    task_id: str
    agent_id: str
    allocated_gb: float
    requested_gb: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


class GPUMonitor:
    """Comprehensive GPU monitoring."""

    def __init__(self):
        self._gpus: Dict[int, GPUInfo] = {}
        self._allocations: Dict[int, List[VRAMAllocation]] = {i: [] for i in range(8)}
        self._inference_history: List[InferenceMetrics] = []
        self._max_history = 10000
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
                await self.collect_metrics()
            except Exception:
                pass
            await asyncio.sleep(5)  # Collect every 5 seconds

    async def collect_metrics(self) -> Dict[int, GPUInfo]:
        """Collect GPU metrics."""
        try:
            import torch

            if not torch.cuda.is_available():
                return self._gpus

            for i in range(torch.cuda.device_count()):
                try:
                    props = torch.cuda.get_device_properties(i)
                    memory_allocated = torch.cuda.memory_allocated(i) / 1e9
                    memory_reserved = torch.cuda.memory_reserved(i) / 1e9

                    gpu_info = GPUInfo(
                        gpu_id=i,
                        name=props.name,
                        memory_total_gb=props.total_memory / 1e9,
                        memory_used_gb=memory_allocated,
                        utilization_percent=0,  # Would use nvidia-smi
                        temperature_celsius=0,    # Would use nvidia-smi
                        power_watts=0,           # Would use nvidia-smi
                        status=self._calculate_status(memory_allocated, props.total_memory / 1e9),
                        last_updated=datetime.utcnow()
                    )

                    self._gpus[i] = gpu_info

                except Exception:
                    pass

        except ImportError:
            pass

        return self._gpus

    def _calculate_status(self, memory_used: float, memory_total: float) -> GPUStatus:
        """Calculate GPU status."""
        if memory_total == 0:
            return GPUStatus.UNKNOWN

        usage_percent = (memory_used / memory_total) * 100

        if usage_percent > 95:
            return GPUStatus.CRITICAL
        elif usage_percent > 80:
            return GPUStatus.DEGRADED
        else:
            return GPUStatus.HEALTHY

    def get_gpu(self, gpu_id: int) -> Optional[GPUInfo]:
        """Get GPU info."""
        return self._gpus.get(gpu_id)

    def get_all_gpus(self) -> Dict[int, GPUInfo]:
        """Get all GPU info."""
        return dict(self._gpus)

    def get_summary(self) -> Dict[str, Any]:
        """Get GPU cluster summary."""
        if not self._gpus:
            return {"status": "no_gpus"}

        total_memory = sum(g.memory_total_gb for g in self._gpus.values())
        used_memory = sum(g.memory_used_gb for g in self._gpus.values())
        avg_utilization = sum(g.utilization_percent for g in self._gpus.values()) / len(self._gpus)

        healthy = sum(1 for g in self._gpus.values() if g.status == GPUStatus.HEALTHY)
        degraded = sum(1 for g in self._gpus.values() if g.status == GPUStatus.DEGRADED)
        critical = sum(1 for g in self._gpus.values() if g.status == GPUStatus.CRITICAL)

        return {
            "total_gpus": len(self._gpus),
            "total_memory_gb": total_memory,
            "used_memory_gb": used_memory,
            "utilization_percent": avg_utilization,
            "healthy_gpus": healthy,
            "degraded_gpus": degraded,
            "critical_gpus": critical,
            "overall_status": "healthy" if critical == 0 else "degraded" if degraded > 0 else "critical"
        }


class GPUCollector:
    """Collects detailed GPU metrics."""

    def __init__(self, monitor: GPUMonitor):
        self.monitor = monitor
        self._metrics_queue: List[Dict] = []

    async def record_inference(
        self,
        model_name: str,
        gpu_id: int,
        batch_size: int,
        input_tokens: int,
        output_tokens: int,
        inference_time_ms: float
    ) -> None:
        """Record inference metrics."""
        metrics = InferenceMetrics(
            model_name=model_name,
            gpu_id=gpu_id,
            batch_size=batch_size,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            inference_time_ms=inference_time_ms,
            throughput_tokens_per_sec=(input_tokens + output_tokens) / (inference_time_ms / 1000) if inference_time_ms > 0 else 0
        )

        self.monitor._inference_history.append(metrics)
        if len(self.monitor._inference_history) > self.monitor._max_history:
            self.monitor._inference_history = self.monitor._inference_history[-self.monitor._max_history:]

    def get_inference_stats(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get inference statistics."""
        history = self.monitor._inference_history
        if model_name:
            history = [m for m in history if m.model_name == model_name]

        if not history:
            return {}

        inference_times = [m.inference_time_ms for m in history]
        throughputs = [m.throughput_tokens_per_sec for m in history]

        return {
            "total_inferences": len(history),
            "avg_inference_time_ms": sum(inference_times) / len(inference_times),
            "min_inference_time_ms": min(inference_times),
            "max_inference_time_ms": max(inference_times),
            "avg_throughput_tokens_per_sec": sum(throughputs) / len(throughputs),
        }


class VRAMTracker:
    """Tracks VRAM allocations."""

    def __init__(self, monitor: GPUMonitor):
        self.monitor = monitor

    async def allocate(
        self,
        gpu_id: int,
        task_id: str,
        agent_id: str,
        requested_gb: float
    ) -> bool:
        """Request VRAM allocation."""
        gpu = self.monitor.get_gpu(gpu_id)
        if not gpu:
            return False

        available = gpu.memory_total_gb - gpu.memory_used_gb
        if requested_gb > available:
            return False

        allocation = VRAMAllocation(
            task_id=task_id,
            agent_id=agent_id,
            allocated_gb=min(requested_gb, available),
            requested_gb=requested_gb
        )

        self.monitor._allocations[gpu_id].append(allocation)
        gpu.memory_used_gb += allocation.allocated_gb

        return True

    async def release(
        self,
        gpu_id: int,
        task_id: str
    ) -> float:
        """Release VRAM allocation."""
        allocations = self.monitor._allocations.get(gpu_id, [])
        released = 0.0

        self.monitor._allocations[gpu_id] = [
            a for a in allocations if a.task_id != task_id
        ]

        # Recalculate used memory
        gpu = self.monitor.get_gpu(gpu_id)
        if gpu:
            gpu.memory_used_gb = sum(
                a.allocated_gb for a in self.monitor._allocations.get(gpu_id, [])
            )
            released = gpu.memory_used_gb

        return released

    def get_allocations(self, gpu_id: int) -> List[VRAMAllocation]:
        """Get allocations for GPU."""
        return list(self.monitor._allocations.get(gpu_id, []))

    def get_total_allocated(self, gpu_id: int) -> float:
        """Get total allocated VRAM."""
        return sum(a.allocated_gb for a in self.monitor._allocations.get(gpu_id, []))


class RayClusterMonitor:
    """Monitors Ray distributed cluster."""

    def __init__(self):
        self._nodes: Dict[str, Dict] = {}
        self._actors: Dict[str, Dict] = {}
        self._tasks: Dict[str, Dict] = {}

    async def get_cluster_status(self) -> Dict[str, Any]:
        """Get cluster status."""
        return {
            "total_nodes": len(self._nodes),
            "active_nodes": sum(1 for n in self._nodes.values() if n.get("alive")),
            "total_actors": len(self._actors),
            "active_tasks": len(self._tasks),
        }

    async def get_node_metrics(self, node_id: str) -> Dict[str, Any]:
        """Get metrics for a specific node."""
        node = self._nodes.get(node_id, {})
        return {
            "node_id": node_id,
            "cpu_percent": node.get("cpu_percent", 0),
            "memory_percent": node.get("memory_percent", 0),
            "gpu_metrics": node.get("gpus", []),
        }


class DistributedWorkerMonitor:
    """Monitors distributed workers."""

    def __init__(self):
        self._workers: Dict[str, Dict] = {}
        self._task_queue: Dict[str, List] = {}

    async def register_worker(
        self,
        worker_id: str,
        capabilities: List[str],
        resources: Dict
    ) -> None:
        """Register a worker."""
        self._workers[worker_id] = {
            "worker_id": worker_id,
            "capabilities": capabilities,
            "resources": resources,
            "status": "idle",
            "current_task": None,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "last_heartbeat": datetime.utcnow()
        }

    async def heartbeat(self, worker_id: str) -> None:
        """Worker heartbeat."""
        if worker_id in self._workers:
            self._workers[worker_id]["last_heartbeat"] = datetime.utcnow()

    def get_idle_workers(self) -> List[str]:
        """Get idle workers."""
        return [
            w["worker_id"] for w in self._workers.values()
            if w["status"] == "idle"
        ]

    def get_worker_status(self, worker_id: str) -> Optional[Dict]:
        """Get worker status."""
        return self._workers.get(worker_id)

    def get_cluster_load(self) -> Dict[str, Any]:
        """Get cluster load metrics."""
        total_workers = len(self._workers)
        idle_workers = sum(1 for w in self._workers.values() if w["status"] == "idle")
        busy_workers = total_workers - idle_workers

        return {
            "total_workers": total_workers,
            "idle_workers": idle_workers,
            "busy_workers": busy_workers,
            "utilization_percent": (busy_workers / max(total_workers, 1)) * 100
        }