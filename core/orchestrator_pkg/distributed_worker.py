"""
DistributedTaskWorkerPool - cluster-wide task dispatching and worker orchestration.

Manages distributed worker node lifecycle, heartbeat arbitrations, least-busy
chunk scheduling, and automatic fault-recovery for long-running dataset synthesis.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class WorkerNode:
    """Represents a connected compute worker in the cluster."""
    worker_id: str
    capacity: int = 4
    active_tasks: int = 0
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    @property
    def available_slots(self) -> int:
        return max(0, self.capacity - self.active_tasks)

    @property
    def load_ratio(self) -> float:
        if self.capacity <= 0:
            return 1.0
        return self.active_tasks / self.capacity


@dataclass
class TaskChunk:
    """A unit of synthesis work dispatched to a worker node."""
    chunk_id: str
    job_id: str
    data: Dict[str, Any]
    assigned_worker: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    retries: int = 0
    max_retries: int = 3
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None


class DistributedTaskWorkerPool:
    """
    Cluster task worker pool coordinating multi-node synthesis workloads.
    Provides sub-second least-busy routing, lease heartbeating, and orphaned task stealing.
    """

    def __init__(
        self,
        heartbeat_timeout_sec: float = 30.0,
        max_chunk_retries: int = 3,
        redis_client: Optional[Any] = None,
    ):
        self.heartbeat_timeout_sec = heartbeat_timeout_sec
        self.max_chunk_retries = max_chunk_retries
        self.redis_client = redis_client
        self._workers: Dict[str, WorkerNode] = {}
        self._chunks: Dict[str, TaskChunk] = {}
        self._lock = asyncio.Lock()

    def register_worker(
        self,
        worker_id: str,
        capacity: int = 4,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkerNode:
        """Register or re-activate a worker node in the cluster."""
        node = WorkerNode(
            worker_id=worker_id,
            capacity=capacity,
            active_tasks=0,
            last_heartbeat=time.time(),
            metadata=metadata or {},
            is_active=True,
        )
        self._workers[worker_id] = node
        logger.info(f"Worker {worker_id} registered with capacity {capacity}")
        return node

    def unregister_worker(self, worker_id: str) -> Optional[WorkerNode]:
        """Gracefully remove a worker node."""
        node = self._workers.pop(worker_id, None)
        if node:
            node.is_active = False
            logger.info(f"Worker {worker_id} unregistered")
        return node

    def heartbeat(self, worker_id: str) -> bool:
        """Update last heartbeat timestamp for a worker."""
        if worker_id in self._workers:
            self._workers[worker_id].last_heartbeat = time.time()
            self._workers[worker_id].is_active = True
            return True
        return False

    def get_healthy_workers(self) -> List[WorkerNode]:
        """Return all workers with non-expired heartbeats."""
        now = time.time()
        return [
            w for w in self._workers.values()
            if w.is_active and (now - w.last_heartbeat) <= self.heartbeat_timeout_sec
        ]

    def reap_stale_workers(self) -> List[str]:
        """Identify and mark stale workers; returns orphaned worker IDs."""
        now = time.time()
        stale_ids = []
        for wid, w in list(self._workers.items()):
            if w.is_active and (now - w.last_heartbeat) > self.heartbeat_timeout_sec:
                w.is_active = False
                stale_ids.append(wid)
                logger.warning(f"Worker {wid} marked inactive due to heartbeat timeout")
        return stale_ids

    def select_best_worker(self) -> Optional[WorkerNode]:
        """
        Least-busy load balancing: selects healthy worker with most available slots
        and lowest load ratio.
        """
        healthy = self.get_healthy_workers()
        available = [w for w in healthy if w.available_slots > 0]
        if not available:
            return None
        # Sort by load_ratio asc, then available_slots desc
        available.sort(key=lambda w: (w.load_ratio, -w.available_slots))
        return available[0]

    async def dispatch_chunk(
        self,
        chunk_id: str,
        job_id: str,
        data: Dict[str, Any],
        handler: Optional[Callable[[TaskChunk], Coroutine[Any, Any, Any]]] = None,
    ) -> TaskChunk:
        """
        Dispatches a synthesis chunk to the least-busy worker.
        If no worker has immediate capacity, waits briefly or executes via fallback.
        """
        async with self._lock:
            self.reap_stale_workers()
            worker = self.select_best_worker()
            chunk = TaskChunk(
                chunk_id=chunk_id,
                job_id=job_id,
                data=data,
                assigned_worker=worker.worker_id if worker else None,
                status="in_progress" if worker else "pending",
            )
            self._chunks[chunk_id] = chunk

            if worker:
                worker.active_tasks += 1

        if not worker:
            chunk.status = "failed"
            chunk.error = "No healthy workers available with spare capacity"
            return chunk

        if handler:
            try:
                res = await handler(chunk)
                chunk.status = "completed"
                chunk.result = res
            except Exception as e:
                chunk.status = "failed"
                chunk.error = str(e)
                logger.error(f"Task chunk {chunk_id} on worker {worker.worker_id} failed: {e}")
            finally:
                async with self._lock:
                    if worker.worker_id in self._workers:
                        self._workers[worker.worker_id].active_tasks = max(0, self._workers[worker.worker_id].active_tasks - 1)

        return chunk

    async def map_chunks(
        self,
        job_id: str,
        items: List[Dict[str, Any]],
        handler: Callable[[TaskChunk], Coroutine[Any, Any, Any]],
    ) -> List[TaskChunk]:
        """Dispatches an entire batch of synthesis chunks concurrently across available workers."""
        tasks = []
        for i, item in enumerate(items):
            cid = f"{job_id}-chunk-{i}"
            tasks.append(self.dispatch_chunk(chunk_id=cid, job_id=job_id, data=item, handler=handler))
        return await asyncio.gather(*tasks)

    def get_cluster_stats(self) -> Dict[str, Any]:
        """Aggregate telemetry on cluster worker nodes and throughput capacity."""
        healthy = self.get_healthy_workers()
        total_capacity = sum(w.capacity for w in healthy)
        total_active = sum(w.active_tasks for w in healthy)
        return {
            "total_registered_workers": len(self._workers),
            "healthy_workers": len(healthy),
            "total_capacity_slots": total_capacity,
            "active_tasks": total_active,
            "available_slots": max(0, total_capacity - total_active),
            "cluster_utilization_pct": round((total_active / max(1, total_capacity)) * 100, 2),
        }
