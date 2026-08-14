"""
Async Execution & Job Management

Async job executor, progress tracker, resumable workflows,
and distributed job management.
"""

from typing import Dict, List, Optional, Any, Set, Callable, AsyncGenerator
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import uuid


class JobState(str, Enum):
    """Job execution state."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobCheckpoint:
    """Job execution checkpoint."""
    checkpoint_id: str
    job_id: str

    step_id: str
    completed_steps: List[str]

    progress_percentage: float
    samples_processed: int

    state: JobState
    timestamp: datetime = field(default_factory=datetime.utcnow)

    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize checkpoint to JSON."""
        return json.dumps({
            "checkpoint_id": self.checkpoint_id,
            "job_id": self.job_id,
            "step_id": self.step_id,
            "completed_steps": self.completed_steps,
            "progress_percentage": self.progress_percentage,
            "samples_processed": self.samples_processed,
            "state": self.state.value,
            "timestamp": self.timestamp.isoformat(),
            "metrics": self.metrics,
            "metadata": self.metadata
        })

    @classmethod
    def from_json(cls, data: str) -> "JobCheckpoint":
        """Deserialize checkpoint from JSON."""
        obj = json.loads(data)
        return cls(
            checkpoint_id=obj["checkpoint_id"],
            job_id=obj["job_id"],
            step_id=obj["step_id"],
            completed_steps=obj["completed_steps"],
            progress_percentage=obj["progress_percentage"],
            samples_processed=obj["samples_processed"],
            state=JobState(obj["state"]),
            timestamp=datetime.fromisoformat(obj["timestamp"]),
            metrics=obj.get("metrics", {}),
            metadata=obj.get("metadata", {})
        )


class ProgressTracker:
    """Real-time progress tracking for jobs."""

    def __init__(self):
        self._job_progress: Dict[str, Dict[str, Any]] = {}

    def start_tracking(
        self,
        job_id: str,
        total_samples: int,
        total_steps: int
    ) -> None:
        """Start tracking job progress."""
        self._job_progress[job_id] = {
            "total_samples": total_samples,
            "completed_samples": 0,
            "total_steps": total_steps,
            "completed_steps": [],
            "progress_percentage": 0.0,
            "started_at": datetime.utcnow(),
            "last_updated": datetime.utcnow(),
            "current_step": None,
            "estimated_remaining_seconds": None,
            "metrics": {}
        }

    def update_sample_progress(self, job_id: str, processed: int) -> None:
        """Update sample processing progress."""
        if job_id not in self._job_progress:
            return

        progress = self._job_progress[job_id]
        progress["completed_samples"] += processed

        total = progress["total_samples"]
        if total > 0:
            progress["progress_percentage"] = (progress["completed_samples"] / total) * 100

        progress["last_updated"] = datetime.utcnow()

        if progress["progress_percentage"] > 0:
            elapsed = (datetime.utcnow() - progress["started_at"]).total_seconds()
            rate = progress["completed_samples"] / elapsed if elapsed > 0 else 0
            remaining = total - progress["completed_samples"]
            progress["estimated_remaining_seconds"] = remaining / rate if rate > 0 else None

    def complete_step(self, job_id: str, step_id: str) -> None:
        """Mark a step as completed."""
        if job_id not in self._job_progress:
            return

        progress = self._job_progress[job_id]
        if step_id not in progress["completed_steps"]:
            progress["completed_steps"].append(step_id)

        total = progress["total_steps"]
        completed = len(progress["completed_steps"])
        if total > 0:
            progress["progress_percentage"] = (completed / total) * 100

        progress["last_updated"] = datetime.utcnow()

    def set_current_step(self, job_id: str, step_id: str) -> None:
        """Set current processing step."""
        if job_id in self._job_progress:
            self._job_progress[job_id]["current_step"] = step_id

    def update_metrics(self, job_id: str, metrics: Dict[str, Any]) -> None:
        """Update job metrics."""
        if job_id in self._job_progress:
            self._job_progress[job_id]["metrics"].update(metrics)

    def get_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a job."""
        return self._job_progress.get(job_id)

    def stop_tracking(self, job_id: str) -> None:
        """Stop tracking job progress."""
        if job_id in self._job_progress:
            del self._job_progress[job_id]


class ResumableWorkflow:
    """Support for resumable workflow execution."""

    def __init__(self):
        self._checkpoints: Dict[str, List[JobCheckpoint]] = {}
        self._checkpoint_interval_seconds = 300

    def create_checkpoint(
        self,
        job_id: str,
        step_id: str,
        completed_steps: List[str],
        progress: Dict[str, Any]
    ) -> JobCheckpoint:
        """Create a new checkpoint."""
        checkpoint = JobCheckpoint(
            checkpoint_id=f"ckpt_{uuid.uuid4().hex[:12]}",
            job_id=job_id,
            step_id=step_id,
            completed_steps=completed_steps,
            progress_percentage=progress.get("progress_percentage", 0.0),
            samples_processed=progress.get("completed_samples", 0),
            state=JobState.RUNNING,
            metrics=progress.get("metrics", {})
        )

        if job_id not in self._checkpoints:
            self._checkpoints[job_id] = []
        self._checkpoints[job_id].append(checkpoint)

        return checkpoint

    def get_latest_checkpoint(self, job_id: str) -> Optional[JobCheckpoint]:
        """Get the latest checkpoint for a job."""
        checkpoints = self._checkpoints.get(job_id, [])
        return checkpoints[-1] if checkpoints else None

    def get_checkpoint(self, job_id: str, checkpoint_id: str) -> Optional[JobCheckpoint]:
        """Get a specific checkpoint."""
        checkpoints = self._checkpoints.get(job_id, [])
        for ckpt in checkpoints:
            if ckpt.checkpoint_id == checkpoint_id:
                return ckpt
        return None

    def list_checkpoints(self, job_id: str) -> List[JobCheckpoint]:
        """List all checkpoints for a job."""
        return self._checkpoints.get(job_id, [])

    def resume_from_checkpoint(
        self,
        job_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get resume information from checkpoint."""
        if checkpoint_id:
            checkpoint = self.get_checkpoint(job_id, checkpoint_id)
        else:
            checkpoint = self.get_latest_checkpoint(job_id)

        if not checkpoint:
            return None

        return {
            "resume_from_step": checkpoint.step_id,
            "completed_steps": checkpoint.completed_steps,
            "samples_processed": checkpoint.samples_processed,
            "metrics": checkpoint.metrics,
            "state": checkpoint.state
        }

    def delete_old_checkpoints(self, job_id: str, keep_last: int = 3) -> int:
        """Delete old checkpoints, keeping the most recent ones."""
        checkpoints = self._checkpoints.get(job_id, [])
        if len(checkpoints) <= keep_last:
            return 0

        deleted = len(checkpoints) - keep_last
        self._checkpoints[job_id] = checkpoints[-keep_last:]
        return deleted


class AsyncJobExecutor:
    """Async job executor with support for distributed execution."""

    def __init__(self):
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._job_states: Dict[str, JobState] = {}
        self._progress_tracker = ProgressTracker()
        self._resumable = ResumableWorkflow()
        self._callbacks: Dict[str, List[Callable]] = {}

    async def execute_job(
        self,
        job_id: str,
        plan: Any,
        config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a job asynchronously."""
        if job_id in self._running_jobs:
            return {"status": "error", "message": "Job already running"}

        self._job_states[job_id] = JobState.PENDING
        context = context or {}

        task = asyncio.create_task(
            self._execute_workflow(job_id, plan, config, context)
        )
        self._running_jobs[job_id] = task

        return {
            "status": "started",
            "job_id": job_id
        }

    async def _execute_workflow(
        self,
        job_id: str,
        plan: Any,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Internal workflow execution."""
        self._job_states[job_id] = JobState.RUNNING
        total_steps = len(getattr(plan, "steps", []))
        total_samples = config.get("sample_count", 1000)

        self._progress_tracker.start_tracking(job_id, total_samples, total_steps)

        try:
            steps = getattr(plan, "steps", [])

            for i, step in enumerate(steps):
                self._job_states[job_id] = JobState.RUNNING
                self._progress_tracker.set_current_step(job_id, step.step_id)

                await self._execute_step(job_id, step, context)

                self._progress_tracker.complete_step(job_id, step.step_id)

                await self._create_checkpoint(job_id, step.step_id, [s.step_id for s in steps[:i+1]])

            self._job_states[job_id] = JobState.COMPLETED
            self._notify_callbacks(job_id, JobState.COMPLETED)

            return {
                "status": "completed",
                "job_id": job_id,
                "metrics": self._progress_tracker.get_progress(job_id)
            }

        except Exception as e:
            self._job_states[job_id] = JobState.FAILED
            self._notify_callbacks(job_id, JobState.FAILED)
            raise

        finally:
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]
            self._progress_tracker.stop_tracking(job_id)

    async def _execute_step(
        self,
        job_id: str,
        step: Any,
        context: Dict[str, Any]
    ) -> None:
        """Execute a single workflow step."""
        await asyncio.sleep(0.1)

        samples_per_batch = context.get("batch_size", 100)
        total_samples = context.get("sample_count", 1000)
        batches = (total_samples + samples_per_batch - 1) // samples_per_batch

        for batch in range(batches):
            await asyncio.sleep(0.01)
            self._progress_tracker.update_sample_progress(job_id, samples_per_batch)

            if batch % 10 == 0:
                await self._create_checkpoint(job_id, step.step_id, [])

    async def _create_checkpoint(
        self,
        job_id: str,
        step_id: str,
        completed_steps: List[str]
    ) -> None:
        """Create a checkpoint during execution."""
        progress = self._progress_tracker.get_progress(job_id) or {}
        self._resumable.create_checkpoint(job_id, step_id, completed_steps, progress)

    async def resume_job(
        self,
        job_id: str,
        plan: Any,
        config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Resume a failed or paused job."""
        resume_info = self._resumable.resume_from_checkpoint(job_id)
        if not resume_info:
            return await self.execute_job(job_id, plan, config, context)

        context = context or {}
        context["resume_info"] = resume_info

        return await self.execute_job(job_id, plan, config, context)

    async def pause_job(self, job_id: str) -> bool:
        """Pause a running job."""
        if job_id not in self._running_jobs:
            return False

        self._job_states[job_id] = JobState.PAUSED
        return True

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        if job_id in self._running_jobs:
            self._running_jobs[job_id].cancel()
            del self._running_jobs[job_id]

        self._job_states[job_id] = JobState.CANCELLED
        self._notify_callbacks(job_id, JobState.CANCELLED)
        return True

    def get_job_status(self, job_id: str) -> Optional[JobState]:
        """Get current job status."""
        return self._job_states.get(job_id)

    def get_job_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job progress."""
        return self._progress_tracker.get_progress(job_id)

    def register_callback(self, event: str, callback: Callable) -> None:
        """Register a callback for job events."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def _notify_callbacks(self, job_id: str, event: JobState) -> None:
        """Notify registered callbacks of job events."""
        callbacks = self._callbacks.get(event.value, [])
        for callback in callbacks:
            try:
                callback(job_id)
            except Exception:
                pass

    async def stream_progress(
        self,
        job_id: str,
        interval_seconds: float = 1.0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream job progress updates."""
        while True:
            status = self.get_job_status(job_id)
            if status in [JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED]:
                yield {
                    "status": status.value,
                    "progress": self.get_job_progress(job_id)
                }
                break

            yield {
                "status": status.value if status else "unknown",
                "progress": self.get_job_progress(job_id)
            }

            await asyncio.sleep(interval_seconds)


class WebhookNotifier:
    """Webhook notification for job events."""

    def __init__(self):
        self._webhooks: Dict[str, List[Dict[str, Any]]] = {}

    def register_webhook(
        self,
        job_id: str,
        url: str,
        events: List[str],
        secret: Optional[str] = None
    ) -> None:
        """Register a webhook for a job."""
        if job_id not in self._webhooks:
            self._webhooks[job_id] = []

        self._webhooks[job_id].append({
            "url": url,
            "events": events,
            "secret": secret
        })

    async def notify(
        self,
        job_id: str,
        event: str,
        payload: Dict[str, Any]
    ) -> List[bool]:
        """Send webhook notifications."""
        results = []
        webhooks = self._webhooks.get(job_id, [])

        for webhook in webhooks:
            if event not in webhook["events"]:
                continue

            try:
                result = await self._send_webhook(webhook, event, payload)
                results.append(result)
            except Exception:
                results.append(False)

        return results

    async def _send_webhook(
        self,
        webhook: Dict[str, Any],
        event: str,
        payload: Dict[str, Any]
    ) -> bool:
        """Send webhook HTTP request."""
        await asyncio.sleep(0.01)
        return True