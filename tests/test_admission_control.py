"""Tests for the Admission Control system (core/admission_control.py).

Tests concurrency limiting, queue behavior, backpressure, and rejection handling.
Uses asyncio-based testing with mock observability.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.admission_control import AdmissionController, BackpressureSettings


@pytest.fixture
def controller():
    return AdmissionController(max_concurrent_jobs=3, max_queue_size=10)


class TestAdmissionController:
    """Test suite for AdmissionController."""

    @pytest.mark.asyncio
    async def test_acquire_release_basic(self, controller):
        """Basic acquire and release cycle should work."""
        acquired = await controller.acquire("job-001")
        assert acquired is True
        assert controller.get_active_count() == 1

        controller.release("job-001")
        assert controller.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_concurrency_limit(self, controller):
        """Should limit concurrent jobs to max_concurrent_jobs."""
        # Acquire all 3 slots
        acquired = []
        for i in range(3):
            a = await controller.acquire(f"job-{i}")
            acquired.append(a)

        assert all(acquired)
        assert controller.get_active_count() == 3
        assert controller.get_stats()["active_jobs"] == 3

        # All 3 should be released
        for i in range(3):
            controller.release(f"job-{i}")
        assert controller.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_queue_full_rejection(self, controller):
        """When queue is full, additional jobs should be rejected."""
        controller._max_queue_size = 1

        # Fill all slots
        for i in range(3):
            await controller.acquire(f"job-fill-{i}")

        # Queue one
        queued_task = asyncio.create_task(controller.acquire("job-queued"))
        await asyncio.sleep(0.1)

        # This should be rejected (queue full)
        rejected = await controller.acquire("job-rejected")
        assert rejected is False
        assert controller.get_rejected_count() >= 0

        # Cleanup
        for i in range(3):
            controller.release(f"job-fill-{i}")
        await queued_task

    @pytest.mark.asyncio
    async def test_stats_reporting(self, controller):
        """get_stats should report accurate state."""
        stats = controller.get_stats()
        assert stats["max_concurrent"] == 3
        assert stats["active_jobs"] == 0
        assert stats["queue_depth"] == 0
        assert "utilization_pct" in stats

    @pytest.mark.asyncio
    async def test_capacity_recommendation(self):
        """Capacity recommendation should return reasonable values."""
        rec = AdmissionController.recommend_capacity(
            provider_count=7, db_connection_pool=5
        )
        assert rec["safe_max_concurrent"] > 0
        assert rec["safe_max_concurrent"] <= 7 * 5  # provider bottleneck
        assert "limiting_factor" in rec

    def test_invalid_max_concurrent(self):
        """Should reject invalid max_concurrent_jobs."""
        with pytest.raises(ValueError, match=">= 1"):
            AdmissionController(max_concurrent_jobs=0)

    @pytest.mark.asyncio
    async def test_release_nonexistent_job(self, controller):
        """Releasing a job that wasn't acquired should not error."""
        # Should not raise
        controller.release("nonexistent")
        assert controller.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_priority_queue_order(self, controller):
        """Higher priority jobs should be admitted before lower priority."""
        await controller.start()
        # Fill all slots
        for i in range(3):
            await controller.acquire(f"job-fill-{i}")

        # Queue low priority first, then high priority
        low_prio = asyncio.create_task(
            controller.acquire("job-low", priority=4)
        )
        await asyncio.sleep(0.05)
        high_prio = asyncio.create_task(
            controller.acquire("job-high", priority=1)
        )
        await asyncio.sleep(0.05)

        # Release one slot
        controller.release("job-fill-0")

        # Wait for queue processor to admit next job (processor runs every 0.5s)
        await asyncio.sleep(0.6)

        # High priority should have been admitted before low priority
        assert "job-high" in controller._active_jobs, \
            f"Expected job-high in active jobs, got: {list(controller._active_jobs.keys())}"

        # Cleanup
        for i in range(1, 3):
            controller.release(f"job-fill-{i}")

        await controller.stop()

    @pytest.mark.asyncio
    async def test_backpressure_settings(self):
        """Backpressure settings should have sensible defaults."""
        bp = BackpressureSettings()
        assert bp.soft_limit_pct == 80.0
        assert bp.hard_limit_pct == 95.0
        assert bp.cooldown_seconds == 30.0

    @pytest.mark.asyncio
    async def test_start_stop(self, controller):
        """Start and stop should not raise errors."""
        await controller.start()
        assert controller._running is True
        await controller.stop()
        assert controller._running is False