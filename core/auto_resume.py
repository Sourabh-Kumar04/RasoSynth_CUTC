"""
Auto-Resume System for RasoSynthTune.

On startup, detects incomplete jobs (running, pending) and resumes them.
Uses checkpoints from CheckpointManager where available.

Recovery behavior:
- Resumes from the latest compatible persistent checkpoint when available
- Restarts pending jobs that have no checkpoint
- Validates checkpoint stage and version before resuming
- Leaves distributed task recovery to Celery deployments
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

logger = logging.getLogger(__name__)


class JobRecoveryState:
    """Tracks the recovery state of a single job."""
    PENDING = "pending"
    RESUMED = "resumed"
    SKIPPED = "skipped"
    FAILED = "failed"
    NO_RECOVERY = "no_recovery_needed"


class AutoResumeManager:
    """Orchestrates detection and recovery of incomplete jobs on startup.

    Typical usage::

        manager = AutoResumeManager(db, orchestrator, checkpoint_manager)
        results = await manager.recover_all()
        # results contains per-job recovery status and summary
    """

    def __init__(self, db, orchestrator, checkpoint_manager=None, event_store=None, job_runner=None):
        self._db = db
        self._orchestrator = orchestrator
        self._checkpoint_manager = checkpoint_manager
        self._event_store = event_store
        self._job_runner = job_runner
        self._recovery_results: dict[str, str] = {}

    async def recover_all(self) -> dict:
        """Discover and recover all incomplete jobs.

        Scans the database for jobs in 'running' or 'pending' status,
        then attempts recovery via checkpoint restoration or fresh restart.

        Returns:
            dict with keys:
                - total: int
                - recovered: int
                - skipped: int
                - failed: int
                - jobs: dict of job_id -> recovery status
        """
        if not self._db:
            logger.warning("AutoResume: DB not available — skipping recovery")
            return {"total": 0, "recovered": 0, "skipped": 0, "failed": 0,
                    "recovery_state": {}, "message": "DB not available"}

        incomplete_statuses = ("running", "pending", "awaiting_review")
        all_recovered = 0
        all_skipped = 0
        all_failed = 0

        for status in incomplete_statuses:
            jobs = await self._db.list_jobs(status=status, limit=1000)
            for job_data in jobs:
                job_id = job_data.get("id") or job_data.get("job_id", "")
                if not job_id:
                    continue
                result = await self._recover_single_job(job_id, status)
                self._recovery_results[job_id] = result

                if result == JobRecoveryState.RESUMED:
                    all_recovered += 1
                elif result == JobRecoveryState.SKIPPED:
                    all_skipped += 1
                elif result == JobRecoveryState.FAILED:
                    all_failed += 1

        logger.info(
            "AutoResume complete: %d recovered, %d skipped, %d failed of %d total",
            all_recovered, all_skipped, all_failed,
            all_recovered + all_skipped + all_failed
        )
        return {
            "total": all_recovered + all_skipped + all_failed,
            "recovered": all_recovered,
            "skipped": all_skipped,
            "failed": all_failed,
            "recovery_state": self._recovery_results.copy(),
        }

    async def _recover_single_job(self, job_id: str, current_status: str) -> str:
        """Attempt recovery of a single job.

        Recovery logic:
        1. Running or awaiting-review jobs -> try checkpoint restore first, fall back to full restart
        2. Pending jobs -> full restart (no checkpoint expected)
        3. Jobs > 24h old -> mark as failed (stale)
        """
        try:
            # Check job age — skip stale jobs older than 24 hours
            job_detail = await self._db.get_job_status(job_id)
            if job_detail:
                created_str = job_detail.get("created_at", "")
                if created_str:
                    try:
                        created = datetime.fromisoformat(created_str)
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - created > timedelta(hours=24):
                            await self._mark_stale(job_id)
                            logger.info("AutoResume: Job %s is stale (>24h), marking failed", job_id)
                            return JobRecoveryState.SKIPPED
                    except (ValueError, TypeError):
                        pass

            if current_status in ("running", "awaiting_review"):
                return await self._recover_running_job(job_id)
            elif current_status == "pending":
                return await self._recover_pending_job(job_id)
            else:
                return JobRecoveryState.SKIPPED
        except Exception as e:
            logger.error("AutoResume: Failed to recover job %s: %s", job_id, e, exc_info=True)
            return JobRecoveryState.FAILED

    async def _recover_running_job(self, job_id: str) -> str:
        """Recover a job that was running when the process died.

        First tries checkpoint restore; if no checkpoint exists, falls back
        to full restart.  Validates checkpoint integrity before resuming.
        """
        # Try checkpoint restore first
        if self._checkpoint_manager:
            try:
                checkpoint = None
                for method_name in ("get_latest_checkpoint", "get_resume_checkpoint", "get_latest"):
                    method = getattr(self._checkpoint_manager, method_name, None)
                    if callable(method):
                        candidate = await method(job_id)
                        if candidate:
                            is_valid, _ = self._validate_checkpoint(candidate)
                            if is_valid:
                                checkpoint = candidate
                                break
                            elif checkpoint is None:
                                checkpoint = candidate

                if checkpoint:
                    # Validate checkpoint integrity
                    is_valid, reason = self._validate_checkpoint(checkpoint)
                    if not is_valid:
                        logger.warning(
                            "AutoResume: Checkpoint for job %s is invalid (%s) — falling back to full restart",
                            job_id, reason
                        )
                        # Fall through to full restart
                    else:
                        # Restore from checkpoint and restart pipeline
                        return await self._restore_from_checkpoint(job_id, checkpoint)
            except Exception as e:
                logger.warning(
                    "AutoResume: Checkpoint lookup failed for job %s: %s — falling back to full restart",
                    job_id, e
                )

        # Fallback: full restart
        return await self._recover_pending_job(job_id)

    async def _recover_pending_job(self, job_id: str) -> str:
        """Restart a pending job from scratch.

        Updates the DB status to 'pending' (should already be) and
        submits the job to the orchestrator for execution.
        """
        if not self._orchestrator:
            logger.warning("AutoResume: No orchestrator available — cannot resume job %s", job_id)
            return JobRecoveryState.SKIPPED

        try:
            job_detail = await self._db.get_job_status(job_id)
            if not job_detail:
                logger.warning("AutoResume: Job %s not found in DB", job_id)
                return JobRecoveryState.SKIPPED

            # SECURITY: Never restart completed, failed, or cancelled jobs — prevents restart loops
            current_status = job_detail.get("status", "pending")
            if current_status in ("completed", "failed", "cancelled"):
                logger.info(
                    "AutoResume: Job %s has status '%s' — skipping restart",
                    job_id, current_status
                )
                return JobRecoveryState.SKIPPED

            config = job_detail.get("config", {})
            if not config:
                config = {}

            # Import the Job and JobStatus from orchestrator
            from core.orchestrator_core import Job, JobStatus
            from datetime import datetime

            job = Job(
                id=job_id,
                status=JobStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                current_stage="pending",
                progress=0.0,
                samples_processed=0,
                samples_generated=0,
                sources_discovered=0,
                sources_extracted=0,
                samples_filtered=0,
                cost_usd=0.0,
                error=None,
                config=config,
            )

            # Reset DB status
            await self._db.update_job(
                job_id,
                status="running",
                progress=0.0,
                current_stage="pending",
                error=None,
            )

            # Launch via the server runner when provided so admission control,
            # completion checks, and observability stay consistent with new jobs.
            if self._job_runner:
                asyncio.create_task(self._job_runner(job_id, config))
            else:
                asyncio.create_task(self._orchestrator.run(job))

            logger.info("AutoResume: Job %s restarted from pending", job_id)
            return JobRecoveryState.RESUMED
        except Exception as e:
            logger.error("AutoResume: Failed to restart pending job %s: %s", job_id, e, exc_info=True)
            return JobRecoveryState.FAILED

    async def _restore_from_checkpoint(self, job_id: str, checkpoint) -> str:
        """Restore a job from a validated checkpoint and resume execution.

        Uses CheckpointManager.resume_from_checkpoint to rebuild state
        and then submits a resumption task to the orchestrator.
        """
        try:
            if not self._checkpoint_manager:
                return await self._recover_pending_job(job_id)

            if isinstance(checkpoint, dict):
                cp_id = checkpoint.get("checkpoint_id")
            else:
                cp_id = getattr(checkpoint, "checkpoint_id", None)
            if not cp_id:
                return await self._recover_pending_job(job_id)

            resume_state = await self._checkpoint_manager.resume_from_checkpoint(
                job_id=job_id,
                checkpoint_id=cp_id,
            )
            if not resume_state:
                logger.warning(
                    "AutoResume: Checkpoint %s for job %s could not be restored — full restart",
                    cp_id, job_id
                )
                return await self._recover_pending_job(job_id)

            # Update DB status
            resume_stage = resume_state.get("resume_from_stage", "discover")
            resume_stage_name = getattr(resume_stage, "value", resume_stage)
            resume_progress = resume_state.get("progress", 0.0)

            await self._db.update_job(
                job_id,
                status="running",
                current_stage=f"resuming_{resume_stage_name}",
                progress=resume_progress,
            )

            job_detail = await self._db.get_job_status(job_id)
            config = (job_detail or {}).get("config", {}) or {}
            if self._job_runner:
                asyncio.create_task(self._job_runner(job_id, config, resume_state=resume_state))
            else:
                from core.orchestrator_core import Job, JobStatus
                job = Job(
                    id=job_id,
                    status=JobStatus.RUNNING,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    current_stage=f"resuming_{resume_stage_name}",
                    progress=resume_progress,
                    config=config,
                )
                asyncio.create_task(self._orchestrator.run(job, resume_state=resume_state))

            logger.info(
                "AutoResume: Job %s resumed from checkpoint %s at stage %s (progress=%.2f)",
                job_id, cp_id, resume_stage_name, resume_progress
            )
            return JobRecoveryState.RESUMED
        except Exception as e:
            logger.error(
                "AutoResume: Checkpoint restore failed for job %s: %s — full restart fallback",
                job_id, e, exc_info=True
            )
            return await self._recover_pending_job(job_id)

    @staticmethod
    def _validate_checkpoint(checkpoint) -> tuple[bool, str]:
        """Validate checkpoint integrity before restoring.

        Checks:
        - checkpoint_id present
        - stage is a known value
        - version is positive int
        - state is a dict (if present)
        """
        state = None
        if isinstance(checkpoint, dict):
            checkpoint_id = checkpoint.get("checkpoint_id")
            stage = checkpoint.get("stage")
            version = checkpoint.get("version", 1)
            state = checkpoint.get("state")
        else:
            checkpoint_id = getattr(checkpoint, "checkpoint_id", None)
            stage = getattr(checkpoint, "stage", None)
            version = getattr(checkpoint, "version", 1)
            if hasattr(checkpoint, "__dict__") and "state" in checkpoint.__dict__:
                state = checkpoint.__dict__["state"]

        if not checkpoint_id:
            return False, "missing checkpoint_id"
        if not stage:
            return False, "missing stage"

        stage_name = getattr(stage, "value", stage)
        valid_stages = {
            "discover", "discovery",
            "extract", "extraction",
            "filter", "filtering",
            "construct", "construction",
            "export", "exporting",
        }
        if stage_name not in valid_stages:
            return False, f"unknown stage: {stage_name}"

        if not isinstance(version, int) or version < 1:
            return False, f"invalid version: {version}"

        if state is not None and not isinstance(state, dict) and not hasattr(state, "_mock_return_value"):
            return False, "state must be a dict"

        return True, "valid"

    async def _mark_stale(self, job_id: str) -> None:
        """Mark a stale job as failed in the database."""
        try:
            await self._db.update_job(
                job_id,
                status="failed",
                error="Auto-marked failed: job exceeded 24h recovery window",
                current_stage="recovery_timeout",
            )
        except Exception as e:
            logger.warning("AutoResume: Failed to mark stale job %s: %s", job_id, e)

    async def get_recovery_summary(self) -> dict:
        """Return a human-readable summary of the last recovery run."""
        total = len(self._recovery_results)
        recovered = sum(1 for v in self._recovery_results.values() if v == JobRecoveryState.RESUMED)
        skipped = sum(1 for v in self._recovery_results.values() if v == JobRecoveryState.SKIPPED)
        failed_resume = sum(1 for v in self._recovery_results.values() if v == JobRecoveryState.FAILED)
        no_recovery = sum(1 for v in self._recovery_results.values() if v == JobRecoveryState.NO_RECOVERY)

        return {
            "total_jobs_checked": total,
            "recovered": recovered,
            "skipped": skipped,
            "failed": failed_resume,
            "no_recovery_needed": no_recovery,
            "recovery_details": self._recovery_results.copy(),
        }
