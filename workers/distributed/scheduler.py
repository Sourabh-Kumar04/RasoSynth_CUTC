"""
GPU-Aware Dynamic Scheduling & Resource Optimization

Handles workload scheduling, resource allocation, and autoscaling.
"""

import asyncio
from typing import Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import heapq


class SchedulingStrategy(Enum):
    """Task scheduling strategies."""
    FIFO = "fifo"
    PRIORITY = "priority"
    FAIR_SHARE = "fair_share"
    GPU_AWARE = "gpu_aware"
    LOAD_BALANCED = "load_balanced"


@dataclass
class GPUSlot:
    """Represents a GPU slot for scheduling."""
    gpu_id: int
    node_id: str
    available_memory_gb: float
    utilization_percent: float
    locked: bool = False
    locked_by_task: Optional[str] = None
    locked_until: Optional[datetime] = None


@dataclass
class ScheduledTask:
    """A task scheduled for execution."""
    task_id: str
    scheduled_at: datetime
    assigned_node: Optional[str] = None
    assigned_gpu: Optional[int] = None
    priority: int = 5
    estimated_duration: float = 60.0
    actual_duration: float = 0.0
    status: str = "pending"


class PriorityQueue:
    """Priority-based task queue."""

    def __init__(self, max_size: int = 10000):
        self._queue: List[tuple[int, float, str, dict]] = []  # (priority, timestamp, task_id, task_data)
        self._max_size = max_size
        self._task_data: dict[str, dict] = {}
        self._scheduled: dict[str, ScheduledTask] = {}

    def enqueue(
        self,
        task_id: str,
        priority: int,
        task_data: dict,
        estimated_duration: float = 60.0
    ) -> bool:
        """Add task to queue."""
        if len(self._queue) >= self._max_size:
            return False

        timestamp = datetime.utcnow().timestamp()
        heapq.heappush(self._queue, (priority, -timestamp, task_id, task_data))

        self._task_data[task_id] = task_data
        self._scheduled[task_id] = ScheduledTask(
            task_id=task_id,
            scheduled_at=datetime.utcnow(),
            priority=priority,
            estimated_duration=estimated_duration,
        )

        return True

    def dequeue(self) -> Optional[tuple[str, dict]]:
        """Remove and return highest priority task."""
        if not self._queue:
            return None

        priority, _, task_id, task_data = heapq.heappop(self._queue)
        del self._task_data[task_id]

        if task_id in self._scheduled:
            self._scheduled[task_id].status = "executing"

        return task_id, task_data

    def peek(self) -> Optional[tuple[str, dict]]:
        """View highest priority task without removing."""
        if not self._queue:
            return None

        priority, _, task_id, task_data = self._queue[0]
        return task_id, task_data

    def update_priority(self, task_id: str, new_priority: int) -> bool:
        """Update priority of a queued task."""
        if task_id not in self._task_data:
            return False

        # Remove old entry
        new_queue = []
        for p, t, tid, td in self._queue:
            if tid != task_id:
                new_queue.append((p, t, tid, td))
        self._queue = new_queue
        heapq.heapify(self._queue)

        # Re-add with new priority
        return self.enqueue(task_id, new_priority, self._task_data[task_id])

    def remove(self, task_id: str) -> bool:
        """Remove a task from queue."""
        if task_id not in self._task_data:
            return False

        new_queue = []
        for p, t, tid, td in self._queue:
            if tid != task_id:
                new_queue.append((p, t, tid, td))

        self._queue = new_queue
        heapq.heapify(self._queue)
        del self._task_data[task_id]
        return True

    def size(self) -> int:
        """Get queue size."""
        return len(self._queue)

    def get_task_status(self, task_id: str) -> Optional[ScheduledTask]:
        """Get status of a scheduled task."""
        return self._scheduled.get(task_id)


class GPUScheduler:
    """GPU-aware task scheduler."""

    def __init__(self, strategy: SchedulingStrategy = SchedulingStrategy.GPU_AWARE):
        self.strategy = strategy
        self._gpu_slots: dict[int, GPUSlot] = {}
        self._task_gpu_assignment: dict[str, int] = {}
        self._gpu_usage_history: List[dict] = []

    def register_gpu(
        self,
        gpu_id: int,
        node_id: str,
        memory_gb: float
    ) -> None:
        """Register a GPU for scheduling."""
        self._gpu_slots[gpu_id] = GPUSlot(
            gpu_id=gpu_id,
            node_id=node_id,
            available_memory_gb=memory_gb,
            utilization_percent=0.0,
        )

    def unregister_gpu(self, gpu_id: int) -> None:
        """Unregister a GPU."""
        if gpu_id in self._gpu_slots:
            del self._gpu_slots[gpu_id]

    def allocate_gpu(
        self,
        task_id: str,
        required_memory_gb: float,
        preferred_node: Optional[str] = None
    ) -> Optional[int]:
        """Allocate a GPU for a task."""
        candidates = []

        for gpu_id, slot in self._gpu_slots.items():
            if slot.locked:
                continue

            if slot.available_memory_gb >= required_memory_gb:
                if preferred_node and slot.node_id != preferred_node:
                    continue

                candidates.append((gpu_id, slot))

        if not candidates:
            # Try without node preference
            for gpu_id, slot in self._gpu_slots.items():
                if slot.available_memory_gb >= required_memory_gb and not slot.locked:
                    candidates.append((gpu_id, slot))

        if not candidates:
            return None

        # Select best GPU based on strategy
        if self.strategy == SchedulingStrategy.GPU_AWARE:
            # Prefer GPU with most available memory
            candidates.sort(key=lambda x: x[1].available_memory_gb, reverse=True)
        elif self.strategy == SchedulingStrategy.FAIR_SHARE:
            # Prefer GPU with lowest utilization
            candidates.sort(key=lambda x: x[1].utilization_percent)
        else:
            candidates.sort(key=lambda x: x[0])  # Round-robin by ID

        selected_gpu = candidates[0][0]
        self._task_gpu_assignment[task_id] = selected_gpu
        self._gpu_slots[selected_gpu].locked = True
        self._gpu_slots[selected_gpu].locked_by_task = task_id

        return selected_gpu

    def release_gpu(self, task_id: str, memory_released_gb: float) -> None:
        """Release GPU back to pool."""
        if task_id in self._task_gpu_assignment:
            gpu_id = self._task_gpu_assignment[task_id]

            if gpu_id in self._gpu_slots:
                slot = self._gpu_slots[gpu_id]
                slot.available_memory_gb += memory_released_gb
                slot.locked = False
                slot.locked_by_task = None

                # Record usage
                self._gpu_usage_history.append({
                    "gpu_id": gpu_id,
                    "task_id": task_id,
                    "memory_gb": memory_released_gb,
                    "timestamp": datetime.utcnow().isoformat(),
                })

            del self._task_gpu_assignment[task_id]

    def get_gpu_stats(self) -> dict:
        """Get GPU allocation statistics."""
        total_gpus = len(self._gpu_slots)
        locked_gpus = sum(1 for s in self._gpu_slots.values() if s.locked)

        total_memory = sum(s.available_memory_gb for s in self._gpu_slots.values())
        avg_utilization = sum(s.utilization_percent for s in self._gpu_slots.values()) / max(total_gpus, 1)

        return {
            "total_gpus": total_gpus,
            "locked_gpus": locked_gpus,
            "available_gpus": total_gpus - locked_gpus,
            "total_available_memory_gb": total_memory,
            "avg_utilization_percent": avg_utilization,
        }

    def get_gpu_for_task(self, task_id: str) -> Optional[int]:
        """Get GPU assigned to task."""
        return self._task_gpu_assignment.get(task_id)


class WorkloadBalancer:
    """Balances workload across nodes."""

    def __init__(self):
        self._node_loads: dict[str, float] = {}
        self._node_capacities: dict[str, dict] = {}

    def register_node(
        self,
        node_id: str,
        cpu_cores: int,
        gpu_count: int,
        memory_gb: float
    ) -> None:
        """Register a node with its capacity."""
        self._node_capacities[node_id] = {
            "cpu_cores": cpu_cores,
            "gpu_count": gpu_count,
            "memory_gb": memory_gb,
        }
        self._node_loads[node_id] = 0.0

    def get_best_node(self, requirements: dict) -> Optional[str]:
        """Get best node for requirements."""
        candidates = []

        for node_id, capacity in self._node_capacities.items():
            load = self._node_loads.get(node_id, 0.0)

            # Check if node meets requirements
            if requirements.get("gpu_count", 0) > capacity.get("gpu_count", 0):
                continue

            if requirements.get("cpu_cores", 0) > capacity.get("cpu_cores", 0):
                continue

            # Score node (lower load is better)
            score = load
            candidates.append((score, node_id))

        if not candidates:
            return None

        candidates.sort()
        return candidates[0][1]

    def update_load(self, node_id: str, delta: float) -> None:
        """Update node load."""
        if node_id in self._node_loads:
            self._node_loads[node_id] = max(0.0, self._node_loads[node_id] + delta)

    def get_loads(self) -> dict[str, float]:
        """Get current loads."""
        return self._node_loads.copy()


class ResourceAllocator:
    """Dynamic resource allocation with autoscaling."""

    def __init__(
        self,
        min_workers: int = 1,
        max_workers: int = 100,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.2
    ):
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold

        self._active_workers: dict[str, dict] = {}
        self._pending_tasks: int = 0
        self._autoscaling_enabled: bool = True

    def add_worker(self, worker_id: str, capacity: dict) -> None:
        """Add a worker."""
        self._active_workers[worker_id] = {
            "capacity": capacity,
            "current_load": 0.0,
            "status": "active",
            "tasks_completed": 0,
            "added_at": datetime.utcnow(),
        }

    def remove_worker(self, worker_id: str) -> bool:
        """Remove a worker."""
        if worker_id in self._active_workers:
            del self._active_workers[worker_id]
            return True
        return False

    def allocate_resources(self, requirements: dict) -> Optional[dict]:
        """Allocate resources for task."""
        for worker_id, worker in self._active_workers.items():
            if worker["status"] != "active":
                continue

            # Check capacity
            if worker["current_load"] > self.scale_up_threshold:
                continue

            # Check requirements
            if requirements.get("gpu") and worker["capacity"].get("gpu_count", 0) < requirements["gpu"]:
                continue

            # Allocate
            worker["current_load"] += requirements.get("load", 0.1)
            return {"worker_id": worker_id, "allocation": requirements}

        return None

    def release_resources(self, worker_id: str, resources: dict) -> None:
        """Release resources."""
        if worker_id in self._active_workers:
            self._active_workers[worker_id]["current_load"] -= resources.get("load", 0.1)

    def should_scale_up(self) -> bool:
        """Check if should scale up."""
        if not self._autoscaling_enabled:
            return False

        if len(self._active_workers) >= self.max_workers:
            return False

        avg_load = sum(w["current_load"] for w in self._active_workers.values()) / max(len(self._active_workers), 1)

        return avg_load > self.scale_up_threshold

    def should_scale_down(self) -> bool:
        """Check if should scale down."""
        if not self._autoscaling_enabled:
            return False

        if len(self._active_workers) <= self.min_workers:
            return False

        avg_load = sum(w["current_load"] for w in self._active_workers.values()) / max(len(self._active_workers), 1)

        return avg_load < self.scale_down_threshold

    def get_status(self) -> dict:
        """Get allocator status."""
        total_load = sum(w["current_load"] for w in self._active_workers.values())
        avg_load = total_load / max(len(self._active_workers), 1)

        return {
            "active_workers": len(self._active_workers),
            "min_workers": self.min_workers,
            "max_workers": self.max_workers,
            "avg_load": avg_load,
            "should_scale_up": self.should_scale_up(),
            "should_scale_down": self.should_scale_down(),
            "autoscaling_enabled": self._autoscaling_enabled,
        }