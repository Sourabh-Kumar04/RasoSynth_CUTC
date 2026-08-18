"""
Admission Control & Concurrent Job Limits for RasoSynthTune.

Provides:
- Semaphore-based concurrency limiting
- Fair queue with backpressure
- Rejection handling with informative errors
- Prometheus metrics integration
- Capacity planning recommendations

Usage::

    controller = AdmissionController(max_concurrent_jobs=5)
    async with controller.acquire("job-123"):
        # run pipeline
        pass
"""
import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


@dataclass
class QueuedJob:
    """A job waiting in the admission queue."""
    job_id: str
    enqueued_at: float
    priority: int = 3  # lower = higher priority (1=CRITICAL, 2=HIGH, 3=NORMAL, 4=LOW)
    timeout_seconds: float = 300.0  # max time to wait in queue
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class AdmissionController:
    """Controls admission of jobs based on configured concurrency limits.

    Features:
    - Semaphore-based concurrency limit (configurable pool)
    - Priority-based queue for waiting jobs
    - Configurable queue timeout (jobs expire if waiting too long)
    - Backpressure: queue size limit before rejecting
    - Metrics integration for observability
    - Dead job detection (stale semaphore releases)
    """

    def __init__(
        self,
        max_concurrent_jobs: int = 5,
        max_queue_size: int = 50,
        db=None,
        observability=None,
    ):
        if max_concurrent_jobs < 1:
            raise ValueError("max_concurrent_jobs must be >= 1")

        self._max_concurrent = max_concurrent_jobs
        self._max_queue_size = max_queue_size
        self._db = db
        self._observability = observability

        # Semaphore controls concurrent execution.
        # Start full so we count against it from the beginning.
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)

        # Priority queue: list of (priority, enqueue_time, QueuedJob)
        self._queue: list[tuple[int, float, QueuedJob]] = []
        self._queue_lock = asyncio.Lock()

        # Track active jobs for metrics and dead-job detection
        self._active_jobs: dict[str, float] = OrderedDict()
        self._rejected_count = 0
        self._total_queued = 0
        self._total_admitted = 0
        self._total_completed = 0

        # Background task for queue processing
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False

        # Callbacks
        self._on_admit_callbacks: list[Callable] = []
        self._on_reject_callbacks: list[Callable] = []

    # ── Public API ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background queue processor."""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_queue())
        logger.info(
            "AdmissionController started: max_concurrent=%d, max_queue=%d",
            self._max_concurrent, self._max_queue_size
        )

    async def stop(self) -> None:
        """Stop the background queue processor."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("AdmissionController stopped")

    async def acquire(self, job_id: str, priority: int = 3, timeout: float = 300.0) -> bool:
        """Attempt to acquire a slot for a job.

        Returns True if the job was admitted (slot acquired).
        Returns False if the job was rejected (queue full or timeout).

        Usage::

            if await controller.acquire("job-123"):
                try:
                    await run_pipeline()
                finally:
                    controller.release("job-123")
        """
        # Quick path: slot available immediately
        if self._semaphore.locked() is False and not self._queue:
            # Semaphore has no waiters and queue is empty — fast admit
            await self._semaphore.acquire()
            try:
                self._admit_job(job_id)
            except Exception as exc:
                # _admit_job raised (e.g. provider unavailable) — release slot and reject
                self._semaphore.release()
                logger.warning("admit_job failed for %s: %s", job_id, exc)
                return False
            return True

        # Slow path: queue the job
        if len(self._queue) >= self._max_queue_size:
            self._reject_job(job_id, "queue_full")
            return False

        queued = QueuedJob(
            job_id=job_id,
            enqueued_at=time.monotonic(),
            priority=priority,
            timeout_seconds=timeout,
        )

        async with self._queue_lock:
            self._queue.append((priority, queued.enqueued_at, queued))
            self._queue.sort(key=lambda x: (x[0], x[1]))  # sort by priority, then FIFO
            self._total_queued += 1

        # Wait to be admitted or cancelled
        try:
            await asyncio.wait_for(
                queued.cancel_event.wait(),
                timeout=timeout,
            )
            # cancel_event is set when admitted OR rejected
            # Check if we were admitted by checking job_id in active_jobs
            if job_id in self._active_jobs:
                return True
            return False
        except asyncio.TimeoutError:
            # Timeout waiting in queue — remove from queue and reject
            async with self._queue_lock:
                self._queue = [
                    q for q in self._queue
                    if q[2].job_id != job_id
                ]
            self._reject_job(job_id, "queue_timeout")
            return False

    def release(self, job_id: str) -> None:
        """Release the slot held by a job.

        Must be called in a ``finally`` block after ``acquire()``.
        """
        if job_id in self._active_jobs:
            del self._active_jobs[job_id]
            self._total_completed += 1
        self._semaphore.release()
        self._update_metrics()

    async def get_queue_depth(self) -> int:
        """Return the current number of jobs waiting in the queue."""
        async with self._queue_lock:
            return len(self._queue)

    def get_active_count(self) -> int:
        """Return the current number of actively running jobs."""
        return len(self._active_jobs)

    def get_rejected_count(self) -> int:
        """Return the total number of rejected jobs."""
        return self._rejected_count

    def get_stats(self) -> dict:
        """Return comprehensive admission control statistics."""
        return {
            "max_concurrent": self._max_concurrent,
            "max_queue_size": self._max_queue_size,
            "active_jobs": len(self._active_jobs),
            "queue_depth": len(self._queue),
            "total_queued": self._total_queued,
            "total_admitted": self._total_admitted,
            "total_completed": self._total_completed,
            "total_rejected": self._rejected_count,
            "utilization_pct": (len(self._active_jobs) / self._max_concurrent) * 100 if self._max_concurrent > 0 else 0,
        }

    def register_on_admit(self, callback: Callable) -> None:
        """Register a callback fired when a job is admitted."""
        self._on_admit_callbacks.append(callback)

    def register_on_reject(self, callback: Callable) -> None:
        """Register a callback fired when a job is rejected."""
        self._on_reject_callbacks.append(callback)

    @classmethod
    def recommend_capacity(cls, provider_count: int = 7, db_connection_pool: int = 5) -> dict:
        """Recommend safe concurrent limits based on infrastructure capacity.

        Returns:
            dict with keys: safe_max, provider_bottleneck, db_bottleneck, recommendation
        """
        # Provider bottleneck: each provider typically handles 5-10 concurrent requests
        provider_bottleneck = provider_count * 5

        # DB bottleneck: connection pool / 2 (each job uses ~0.5 connections on avg)
        db_bottleneck = max(1, db_connection_pool * 2)

        safe_max = min(provider_bottleneck, db_bottleneck)

        return {
            "safe_max_concurrent": safe_max,
            "provider_bottleneck": provider_bottleneck,
            "db_bottleneck": db_bottleneck,
            "limiting_factor": "providers" if provider_bottleneck < db_bottleneck else "database",
            "recommendation": f"Set max_concurrent_jobs to {safe_max} for current infrastructure",
        }

    # ── Internal methods ───────────────────────────────────────────────────

    async def _process_queue(self) -> None:
        """Background task that processes the queue and admits jobs when slots open."""
        while self._running:
            try:
                await self._try_admit_from_queue()
                await asyncio.sleep(0.5)  # poll interval
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Admission queue processor error: %s", e, exc_info=True)
                await asyncio.sleep(1)

    async def _try_admit_from_queue(self) -> None:
        """Try to admit the next job from the priority queue."""
        if not self._queue:
            return

        # Check stale queue entries
        now = time.monotonic()
        stale = []
        async with self._queue_lock:
            fresh_queue = []
            for priority, enq_time, queued in self._queue:
                if now - enq_time > queued.timeout_seconds:
                    stale.append(queued)
                else:
                    fresh_queue.append((priority, enq_time, queued))
            self._queue = fresh_queue

        for queued in stale:
            queued.cancel_event.set()  # signal timeout
            self._reject_job(queued.job_id, "queue_timeout")

        if not self._queue:
            return

        # If semaphore has available slots, admit from queue
        if not self._semaphore.locked():
            async with self._queue_lock:
                if self._queue:
                    _, _, next_job = self._queue.pop(0)
            await self._semaphore.acquire()
            self._admit_job(next_job.job_id)
            next_job.cancel_event.set()  # signal admission

    def _admit_job(self, job_id: str) -> None:
        """Track an admitted job and fire callbacks."""
        self._active_jobs[job_id] = time.monotonic()
        self._total_admitted += 1
        self._update_metrics()

        for cb in self._on_admit_callbacks:
            try:
                cb(job_id)
            except Exception as e:
                logger.warning("Admit callback failed for %s: %s", job_id, e)

        logger.info("Admitted job %s (active: %d/%d)", job_id, len(self._active_jobs), self._max_concurrent)

    def _reject_job(self, job_id: str, reason: str) -> None:
        """Track a rejected job and fire callbacks."""
        self._rejected_count += 1
        self._update_metrics()

        for cb in self._on_reject_callbacks:
            try:
                cb(job_id, reason)
            except Exception as e:
                logger.warning("Reject callback failed for %s: %s", job_id, e)

        logger.info("Rejected job %s: %s (rejected total: %d)", job_id, reason, self._rejected_count)

    def _update_metrics(self) -> None:
        """Update Prometheus metrics if observability is configured."""
        if not self._observability:
            return
        try:
            metrics = self._observability.get_metrics()
            if "active_jobs" in metrics:
                metrics["active_jobs"].set(len(self._active_jobs))
            if "queue_depth" in metrics:
                metrics["queue_depth"].labels(queue_name="admission").set(len(self._queue))
            # Track rejected count via a custom approach if metrics support it
        except Exception as e:
            logger.debug("Failed to update admission metrics: %s", e)


class BackpressureSettings:
    """Backpressure configuration for the admission controller.

    These settings determine how the system behaves under load.
    """

    def __init__(
        self,
        soft_limit_pct: float = 80.0,
        hard_limit_pct: float = 95.0,
        cooldown_seconds: float = 30.0,
    ):
        self.soft_limit_pct = soft_limit_pct  # Start slowing new submissions
        self.hard_limit_pct = hard_limit_pct  # Start rejecting submissions
        self.cooldown_seconds = cooldown_seconds  # Wait before accepting after hitting hard limit


async def get_admission_controller(app) -> Optional[AdmissionController]:
    """Get the admission controller from the FastAPI app state."""
    return getattr(app.state, "admission_controller", None)