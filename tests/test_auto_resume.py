"""Tests for the Auto-Resume System (core/auto_resume.py).

Uses mock objects to avoid requiring a real database.
Covers: recovery detection, checkpoint restore, stale job handling, edge cases.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from core.auto_resume import AutoResumeManager, JobRecoveryState


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.list_jobs = AsyncMock(return_value=[])
    db.get_job_status = AsyncMock()
    db.update_job = AsyncMock()
    return db


@pytest.fixture
def mock_orchestrator():
    orch = AsyncMock()
    orch.run = AsyncMock()
    return orch


@pytest.fixture
def mock_checkpoint_manager():
    cm = AsyncMock()
    cm.get_latest_checkpoint = AsyncMock()
    cm.resume_from_checkpoint = AsyncMock()
    return cm


@pytest.fixture
def resume_manager(mock_db, mock_orchestrator, mock_checkpoint_manager):
    return AutoResumeManager(
        db=mock_db,
        orchestrator=mock_orchestrator,
        checkpoint_manager=mock_checkpoint_manager,
    )


class TestAutoResumeManager:
    """Test suite for AutoResumeManager recovery logic."""

    # ── Recovery Detection ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_no_incomplete_jobs(self, resume_manager, mock_db):
        """Should handle clean state with no jobs to recover."""
        mock_db.list_jobs.return_value = []
        result = await resume_manager.recover_all()

        assert result["total"] == 0
        assert result["recovered"] == 0
        assert result["skipped"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_recover_pending_job(self, resume_manager, mock_db, mock_orchestrator):
        """Pending job should be restarted from scratch."""
        mock_db.list_jobs.side_effect = lambda status=None, limit=None, **kw: (
            [{"id": "job-001", "job_id": "job-001", "status": "pending", "config": {"target_domain": "test"}}]
            if status == "pending" else []
        )
        mock_db.get_job_status.return_value = {
            "id": "job-001",
            "status": "pending",
            "config": {"target_domain": "test"},
            "created_at": datetime.utcnow().isoformat(),
        }

        result = await resume_manager.recover_all()

        assert result["total"] == 1
        assert result["recovered"] == 1
        assert mock_db.update_job.called
        assert mock_orchestrator.run.called

    @pytest.mark.asyncio
    async def test_recover_running_job_no_checkpoint(self, resume_manager, mock_db, mock_orchestrator, mock_checkpoint_manager):
        """Running job without checkpoint should fall back to full restart."""
        mock_db.list_jobs.side_effect = lambda status=None, limit=None, **kw: (
            [{"id": "job-002", "job_id": "job-002", "status": "running", "config": {}}]
            if status == "running" else []
        )
        mock_db.get_job_status.return_value = {
            "id": "job-002",
            "status": "running",
            "config": {},
            "created_at": datetime.utcnow().isoformat(),
        }
        mock_checkpoint_manager.get_latest_checkpoint.return_value = None

        result = await resume_manager.recover_all()

        assert result["recovered"] == 1
        assert mock_checkpoint_manager.get_latest_checkpoint.called
        assert mock_orchestrator.run.called  # Falls back to full restart

    @pytest.mark.asyncio
    async def test_recover_running_job_with_checkpoint(self, resume_manager, mock_db, mock_orchestrator, mock_checkpoint_manager):
        """Running job with checkpoint should restore from checkpoint."""
        mock_db.list_jobs.side_effect = lambda status=None, limit=None, **kw: (
            [{"id": "job-003", "job_id": "job-003", "status": "running", "config": {}}]
            if status == "running" else []
        )
        mock_db.get_job_status.return_value = {
            "id": "job-003",
            "status": "running",
            "config": {},
            "created_at": datetime.utcnow().isoformat(),
        }
        mock_checkpoint_manager.get_latest_checkpoint.return_value = {
            "checkpoint_id": "cp-test",
            "workflow_id": "job-003",
            "stage": "extract",
            "state": {"sources": []},
            "version": 1,
            "event_ids": [],
        }
        mock_checkpoint_manager.resume_from_checkpoint.return_value = {
            "resume_from_stage": "extract",
            "progress": 0.3,
            "samples_generated": 0,
            "checkpoint": {"checkpoint_id": "cp-test"},
        }

        result = await resume_manager.recover_all()

        assert result["recovered"] == 1
        assert mock_checkpoint_manager.resume_from_checkpoint.called

    # ── Edge Cases ───────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_stale_job_skipped(self, resume_manager, mock_db):
        """Jobs older than 24h should be marked as stale and skipped."""
        mock_db.list_jobs.side_effect = lambda status=None, limit=None, **kw: (
            [{"id": "job-stale", "job_id": "job-stale", "status": "running", "config": {}}]
            if status == "running" else []
        )
        stale_time = (datetime.utcnow() - timedelta(hours=48)).isoformat()
        mock_db.get_job_status.return_value = {
            "id": "job-stale",
            "status": "running",
            "config": {},
            "created_at": stale_time,
        }

        result = await resume_manager.recover_all()

        assert result["skipped"] == 1
        # Should mark as failed
        update_calls = [c for c in mock_db.update_job.call_args_list]
        assert len(update_calls) > 0

    @pytest.mark.asyncio
    async def test_no_db_available(self, resume_manager):
        """Should gracefully handle missing database."""
        resume_manager._db = None
        result = await resume_manager.recover_all()

        assert result["total"] == 0
        assert "DB not available" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_checkpoint_validation_valid(self):
        """Valid checkpoint passes validation."""
        valid = {
            "checkpoint_id": "cp-001",
            "stage": "extract",
            "state": {"sources": []},
            "version": 1,
            "event_ids": ["evt-1", "evt-2"],
        }
        is_valid, reason = AutoResumeManager._validate_checkpoint(valid)
        assert is_valid is True
        assert reason == "valid"

    @pytest.mark.asyncio
    async def test_checkpoint_validation_invalid(self):
        """Invalid checkpoints are detected."""
        cases = [
            ({}, False),  # empty
            ({"checkpoint_id": "cp-1"}, False),  # missing stage
            ({"checkpoint_id": "cp-1", "stage": "extract", "state": "not-a-dict"}, False),  # bad state
        ]
        for checkpoint, should_be_valid in cases:
            is_valid, _ = AutoResumeManager._validate_checkpoint(checkpoint)
            assert is_valid is should_be_valid

    @pytest.mark.asyncio
    async def test_multiple_jobs_recovered(self, resume_manager, mock_db, mock_orchestrator):
        """Multiple incomplete jobs are all recovered."""
        mock_db.list_jobs.side_effect = lambda status=None, limit=None, **kw: (
            [{"id": f"job-{i}", "job_id": f"job-{i}", "status": "pending", "config": {}}
             for i in range(5)]
            if status == "pending" else
            [{"id": f"job-{i}", "job_id": f"job-{i}", "status": "running", "config": {}}
             for i in range(5, 8)]
            if status == "running" else []
        )
        mock_db.get_job_status.return_value = {
            "id": "test", "status": "pending", "config": {},
            "created_at": datetime.utcnow().isoformat(),
        }

        result = await resume_manager.recover_all()

        assert result["total"] == 8
        assert result["recovered"] == 8

    @pytest.mark.asyncio
    async def test_recovery_summary(self, resume_manager, mock_db):
        """Recovery summary should be accurate after recovery."""
        result = await resume_manager.recover_all()
        summary = await resume_manager.get_recovery_summary()
        assert summary["total_jobs_checked"] == result["total"]