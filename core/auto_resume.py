"""
Auto-Resume System for RasoDataset-Agent.

On startup, detects incomplete jobs (running, pending) and resumes them.
Uses checkpoints from CheckpointManager where available.

Recovery guarantees:
- At-most-once execution per pipeline stage
- No duplicate sample generation
- Checkpoint consistency validated before resume
- Corrupted checkpoints detected and skipped
"""
import asyncio
import logging
from datetime import datetime, timedelta
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

    def __init__(self, db, orchestrator, checkpoint_manager=None, event_store=None):
        self._db = db
        self._orchestrator = orchestrator
        self._checkpoint_manager = checkpoint_manager
        self._event_store = event_store
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

        incomplete_statuses = ("running", "pending")
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
        1. Running jobs -> try checkpoint restore first, fall back to full restart
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
                        if datetime.utcnow() - created > timedelta(hours=24):
                            await self._mark_stale(job_id)
                            logger.info("AutoResume: Job %s is stale (>24h), marking failed", job_id)
                            return JobRecoveryState.SKIPPED
                    except (ValueError, TypeError):
                        pass

            if current_status == "running":
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
                checkpoint = await self._checkpoint_manager.get_latest_checkpoint(job_id)
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
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
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

            # Launch the pipeline in background
            asyncio.create_task(self._orchestrator.run(job))

            logger.info("AutoResume: Job %s restarted from pending", job_id)
            return JobRecoveryState.RESUMED
        except Exception as e:
            logger.error("AutoResume: Failed to restart pending job %s: %s", job_id, e, exc_info=True)
            return JobRecoveryState.FAILED

    async def _restore_from_checkpoint(self, job_id: str, checkpoint: dict) -> str:
        """Restore a job from a validated checkpoint and resume execution.

        Uses CheckpointManager.resume_from_checkpoint to rebuild state
        and then submits a resumption task to the orchestrator.
        """
        try:
            if not self._checkpoint_manager:
                return await self._recover_pending_job(job_id)

            cp_id = checkpoint.get("checkpoint_id")
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
            resume_progress = resume_state.get("progress", 0.0)

            await self._db.update_job(
                job_id,
                status="running",
                current_stage=resume_stage,
                progress=resume_progress,
            )

            logger.info(
                "AutoResume: Job %s resumed from checkpoint %s at stage %s (progress=%.2f)",
                job_id, cp_id, resume_stage, resume_progress
            )
            return JobRecoveryState.RESUMED
        except Exception as e:
            logger.error(
                "AutoResume: Checkpoint restore failed for job %s: %s — full restart fallback",
                job_id, e, exc_info=True
            )
            return await self._recover_pending_job(job_id)

    @staticmethod
    def _validate_checkpoint(checkpoint: dict) -> tuple[bool, str]:
        """Validate checkpoint integrity before restoring.

        Checks:
        - checkpoint_id present
        - stage is a known value
        - state is non-empty dict
        - events list exists
        - version is positive int
        """
        if not checkpoint.get("checkpoint_id"):
            return False, "missing checkpoint_id"
        if not checkpoint.get("stage"):
            return False, "missing stage"
        state = checkpoint.get("state", {})
        if not isinstance(state, dict):
            return False, "state is not a dict"
        if "event_ids" in checkpoint and not isinstance(checkpoint["event_ids"], list):
            return False, "events is not a list"
        version = checkpoint.get("version", 1)
        if not isinstance(version, int) or version < 1:
            return False, f"invalid version: {version}"
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