"""
Fault Tolerance & Recovery System

Checkpointing, retry policies, dead-letter queues, and recovery management.
"""

import asyncio
import json
import time
from typing import Optional, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import pickle
import os


class RetryStrategy(Enum):
    """Retry strategies."""
    IMMEDIATE = "immediate"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"


@dataclass
class TaskRetryPolicy:
    """Configuration for task retry behavior."""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True
    jitter_percent: float = 0.1
    retry_on_errors: List[str] = field(default_factory=lambda: ["TimeoutError", "ConnectionError"])
    retry_on_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        if self.strategy == RetryStrategy.IMMEDIATE:
            delay = self.base_delay_seconds
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay_seconds * attempt
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay_seconds * (2 ** (attempt - 1))
        elif self.strategy == RetryStrategy.FIBONACCI:
            delay = self.base_delay_seconds * self._fibonacci(attempt)
        else:
            delay = self.base_delay_seconds

        # Cap at max delay
        delay = min(delay, self.max_delay_seconds)

        # Add jitter
        if self.jitter:
            jitter_range = delay * self.jitter_percent
            delay += (time.time() % jitter_range * 2) - jitter_range

        return delay

    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number."""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if should retry based on error."""
        if attempt >= self.max_retries:
            return False

        error_type = type(error).__name__
        if error_type in self.retry_on_errors:
            return True

        return False


@dataclass
class Checkpoint:
    """Checkpoint data for task recovery."""
    task_id: str
    pipeline_id: str
    stage: str
    timestamp: datetime
    progress: float
    data: dict
    metadata: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "task_id": self.task_id,
            "pipeline_id": self.pipeline_id,
            "stage": self.stage,
            "timestamp": self.timestamp.isoformat(),
            "progress": self.progress,
            "data": self.data,
            "metadata": self.metadata,
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'Checkpoint':
        data = json.loads(json_str)
        return cls(
            task_id=data["task_id"],
            pipeline_id=data["pipeline_id"],
            stage=data["stage"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            progress=data["progress"],
            data=data["data"],
            metadata=data.get("metadata", {}),
        )


class CheckpointManager:
    """Manages checkpointing for fault tolerance."""

    def __init__(self, checkpoint_dir: str = "/tmp/checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        self._checkpoints: dict[str, Checkpoint] = {}
        self._interval_seconds: float = 60.0
        self._last_checkpoint: dict[str, datetime] = {}

        os.makedirs(checkpoint_dir, exist_ok=True)

    def set_interval(self, seconds: float) -> None:
        """Set checkpoint interval."""
        self._interval_seconds = seconds

    async def save_checkpoint(
        self,
        task_id: str,
        pipeline_id: str,
        stage: str,
        progress: float,
        data: dict,
        metadata: dict = None
    ) -> str:
        """Save a checkpoint."""
        checkpoint = Checkpoint(
            task_id=task_id,
            pipeline_id=pipeline_id,
            stage=stage,
            timestamp=datetime.utcnow(),
            progress=progress,
            data=data,
            metadata=metadata or {},
        )

        # Store in memory
        key = f"{pipeline_id}:{task_id}:{stage}"
        self._checkpoints[key] = checkpoint
        self._last_checkpoint[task_id] = datetime.utcnow()

        # Save to disk
        filepath = os.path.join(self.checkpoint_dir, f"{key.replace(':', '_')}.json")
        with open(filepath, 'w') as f:
            f.write(checkpoint.to_json())

        return key

    async def load_checkpoint(
        self,
        task_id: str,
        pipeline_id: str,
        stage: str
    ) -> Optional[Checkpoint]:
        """Load a checkpoint."""
        key = f"{pipeline_id}:{task_id}:{stage}"

        # Try memory first
        if key in self._checkpoints:
            return self._checkpoints[key]

        # Try disk
        filepath = os.path.join(self.checkpoint_dir, f"{key.replace(':', '_')}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return Checkpoint.from_json(f.read())

        return None

    async def load_latest(self, task_id: str) -> Optional[Checkpoint]:
        """Load latest checkpoint for task."""
        # Search all checkpoints for this task
        matching = [cp for key, cp in self._checkpoints.items() if key.startswith(task_id)]
        if matching:
            return max(matching, key=lambda x: x.timestamp)

        # Check disk
        for filename in os.listdir(self.checkpoint_dir):
            if filename.startswith(task_id.replace(':', '_')):
                filepath = os.path.join(self.checkpoint_dir, filename)
                with open(filepath, 'r') as f:
                    return Checkpoint.from_json(f.read())

        return None

    def delete_checkpoint(self, task_id: str, pipeline_id: str, stage: str) -> bool:
        """Delete a checkpoint."""
        key = f"{pipeline_id}:{task_id}:{stage}"

        if key in self._checkpoints:
            del self._checkpoints[key]

        filepath = os.path.join(self.checkpoint_dir, f"{key.replace(':', '_')}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            return True

        return False

    def should_checkpoint(self, task_id: str) -> bool:
        """Check if enough time has passed for a new checkpoint."""
        last = self._last_checkpoint.get(task_id)
        if not last:
            return True

        return (datetime.utcnow() - last).total_seconds() >= self._interval_seconds


@dataclass
class DeadLetterItem:
    """Item in dead letter queue."""
    task_id: str
    task_type: str
    error: str
    error_type: str
    failed_at: datetime
    retry_count: int = 0
    original_payload: dict = field(default_factory=dict)
    stack_trace: str = ""


class DeadLetterQueue:
    """Queue for failed tasks that can't be retried."""

    def __init__(self, storage_path: str = "/tmp/dlq"):
        self.storage_path = storage_path
        self._queue: List[DeadLetterItem] = []
        os.makedirs(storage_path, exist_ok=True)

    def add(
        self,
        task_id: str,
        task_type: str,
        error: Exception,
        payload: dict
    ) -> None:
        """Add a failed task to dead letter queue."""
        item = DeadLetterItem(
            task_id=task_id,
            task_type=task_type,
            error=str(error),
            error_type=type(error).__name__,
            failed_at=datetime.utcnow(),
            original_payload=payload,
            stack_trace=self._get_stack_trace(error),
        )

        self._queue.append(item)
        self._save_to_disk(item)

    def _get_stack_trace(self, error: Exception) -> str:
        """Get stack trace from exception."""
        import traceback
        return ''.join(traceback.format_exception(type(error), error, error.__traceback__))

    def _save_to_disk(self, item: DeadLetterItem) -> None:
        """Save item to disk."""
        filepath = os.path.join(self.storage_path, f"{item.task_id}.json")
        with open(filepath, 'w') as f:
            json.dump({
                "task_id": item.task_id,
                "task_type": item.task_type,
                "error": item.error,
                "error_type": item.error_type,
                "failed_at": item.failed_at.isoformat(),
                "retry_count": item.retry_count,
                "original_payload": item.original_payload,
                "stack_trace": item.stack_trace,
            }, f, indent=2)

    def get_failed_tasks(self) -> List[DeadLetterItem]:
        """Get all failed tasks."""
        return self._queue.copy()

    def retry_task(self, task_id: str) -> Optional[dict]:
        """Mark task for retry from DLQ."""
        for i, item in enumerate(self._queue):
            if item.task_id == task_id:
                item.retry_count += 1
                # Remove from DLQ
                self._queue.pop(i)

                # Remove from disk
                filepath = os.path.join(self.storage_path, f"{task_id}.json")
                if os.path.exists(filepath):
                    os.remove(filepath)

                return item.original_payload

        return None

    def clear(self) -> None:
        """Clear dead letter queue."""
        self._queue.clear()
        for filename in os.listdir(self.storage_path):
            os.remove(os.path.join(self.storage_path, filename))


class RecoveryManager:
    """Manages recovery from failures."""

    def __init__(
        self,
        checkpoint_manager: CheckpointManager,
        dead_letter_queue: DeadLetterQueue
    ):
        self.checkpoint_manager = checkpoint_manager
        self.dlq = dead_letter_queue
        self._recovery_handlers: dict[str, Callable] = {}

    def register_handler(self, stage_type: str, handler: Callable) -> None:
        """Register recovery handler for stage type."""
        self._recovery_handlers[stage_type] = handler

    async def recover_task(
        self,
        task_id: str,
        pipeline_id: str,
        stage: str,
        retry_policy: TaskRetryPolicy
    ) -> Optional[Any]:
        """Attempt to recover a failed task."""
        # Load checkpoint
        checkpoint = await self.checkpoint_manager.load_checkpoint(task_id, pipeline_id, stage)

        if not checkpoint:
            return None

        # Get handler
        handler = self._recovery_handlers.get(stage)
        if not handler:
            return None

        # Execute recovery
        try:
            result = await handler(checkpoint.data, checkpoint.metadata)
            return result
        except Exception as e:
            return None

    async def recover_pipeline(
        self,
        pipeline_id: str,
        completed_stages: List[str],
        failed_stage: str
    ) -> dict:
        """Recover a failed pipeline."""
        recovery_plan = {
            "pipeline_id": pipeline_id,
            "failed_stage": failed_stage,
            "action": "restart_from_checkpoint",
            "checkpoint_available": False,
        }

        # Find checkpoint for failed stage
        # In real implementation, would iterate through stages and find checkpoint

        return recovery_plan

    async def replay_tasks(
        self,
        task_ids: List[str],
        executor: Callable
    ) -> dict[str, Any]:
        """Replay failed tasks."""
        results = {}

        for task_id in task_ids:
            try:
                result = await executor(task_id)
                results[task_id] = {"success": True, "result": result}
            except Exception as e:
                results[task_id] = {"success": False, "error": str(e)}

        return results


class CircuitBreaker:
    """Prevents cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._failures: int = 0
        self._last_failure_time: Optional[datetime] = None
        self._state: str = "closed"  # closed, open, half_open"
        self._half_open_calls: int = 0

    def record_success(self) -> None:
        """Record successful call."""
        self._failures = 0
        self._state = "closed"
        self._half_open_calls = 0

    def record_failure(self) -> None:
        """Record failed call."""
        self._failures += 1
        self._last_failure_time = datetime.utcnow()

        if self._failures >= self.failure_threshold:
            self._state = "open"

    def can_execute(self) -> bool:
        """Check if can execute."""
        if self._state == "closed":
            return True

        if self._state == "open":
            if self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._state = "half_open"
                    self._half_open_calls = 0
                    return True
            return False

        if self._state == "half_open":
            return self._half_open_calls < self.half_open_max_calls

        return False

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with circuit breaker."""
        if not self.can_execute():
            raise Exception("Circuit breaker open")

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()

            if self._state == "half_open":
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    if self._failures >= self.failure_threshold:
                        self._state = "open"

            raise e

    def get_state(self) -> dict:
        """Get circuit breaker state."""
        return {
            "state": self._state,
            "failures": self._failures,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
        }