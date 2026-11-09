"""
Test Worker Lease & Zero-Downtime Crash Recovery Loop.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import pytest

from core.orchestrator_pkg.checkpoints import (
    Checkpoint,
    CheckpointStage,
    CheckpointStore,
    CheckpointManager,
    WorkerLease,
    WorkerLeaseManager,
)
from core.orchestrator_pkg.orchestrator import DatasetOrchestrator


@pytest.mark.asyncio
async def test_worker_lease_lifecycle():
    store = CheckpointStore()
    await store.connect()

    manager1 = WorkerLeaseManager(store=store, worker_id="worker-node-1")
    manager2 = WorkerLeaseManager(store=store, worker_id="worker-node-2")

    job_id = "test-job-resilience-001"

    # Worker 1 acquires lease
    lease1 = await manager1.acquire_lease(job_id, ttl_seconds=2)
    assert lease1 is not None
    assert lease1.worker_id == "worker-node-1"
    assert not lease1.is_expired()

    # Worker 2 attempts to acquire same job -> should be rejected
    lease2 = await manager2.acquire_lease(job_id, ttl_seconds=2)
    assert lease2 is None

    # Worker 1 renews lease
    renewed = await manager1.renew_lease(job_id, ttl_seconds=5)
    assert renewed is True
    assert lease1.heartbeat_count >= 1

    # Worker 1 releases lease
    released = await manager1.release_lease(job_id)
    assert released is True

    # Now Worker 2 can acquire lease
    lease2_after = await manager2.acquire_lease(job_id, ttl_seconds=5)
    assert lease2_after is not None
    assert lease2_after.worker_id == "worker-node-2"

    await manager2.release_lease(job_id)
    await store.close()


@pytest.mark.asyncio
async def test_expired_lease_stealing_and_orphan_detection():
    store = CheckpointStore()
    await store.connect()

    manager1 = WorkerLeaseManager(store=store, worker_id="crashed-worker")
    manager2 = WorkerLeaseManager(store=store, worker_id="standby-worker")

    job_id = "test-job-crashed-002"

    # Acquire lease with 0 second TTL (immediately expired)
    now = datetime.now(timezone.utc) - timedelta(seconds=10)
    lease_expired = WorkerLease(
        job_id=job_id,
        worker_id="crashed-worker",
        acquired_at=now,
        expires_at=now + timedelta(seconds=1),
        is_active=True,
    )
    manager1._leases[job_id] = lease_expired
    manager2._leases[job_id] = lease_expired

    # Detect orphaned jobs
    orphans = await manager2.detect_orphaned_jobs([job_id])
    assert job_id in orphans

    # Standby worker should be able to steal the expired lease
    stolen_lease = await manager2.acquire_lease(job_id, ttl_seconds=10)
    assert stolen_lease is not None
    assert stolen_lease.worker_id == "standby-worker"

    await manager2.release_lease(job_id)
    await store.close()


@pytest.mark.asyncio
async def test_orchestrator_job_recovery_from_checkpoint():
    store = CheckpointStore()
    await store.connect()
    checkpoint_mgr = CheckpointManager(store=store)

    job_id = "test-job-recover-003"

    # Create an intermediate checkpoint
    await checkpoint_mgr.create_checkpoint(
        job_id=job_id,
        stage=CheckpointStage.CONSTRUCTION,
        progress=0.75,
        samples_generated=42,
        constructed_samples=[{"instruction": f"I{i}", "response": f"R{i}"} for i in range(42)],
    )

    class MockRouter:
        def get_stats(self):
            return {}

    orchestrator = DatasetOrchestrator(
        config={},
        router=MockRouter(),
        checkpoint_manager=checkpoint_mgr,
    )

    # Recover the job using standby worker
    recovery_data = await orchestrator.recover_job(job_id, new_worker_id="standby-worker-42")
    assert recovery_data is not None
    assert recovery_data["resume_from_stage"] == CheckpointStage.CONSTRUCTION
    assert recovery_data["progress"] == 0.75
    assert recovery_data["samples_generated"] == 42
    assert len(recovery_data["constructed_samples"]) == 42
    assert orchestrator.lease_manager.worker_id == "standby-worker-42"

    # Clean up
    await orchestrator.lease_manager.release_lease(job_id)
    await store.close()
