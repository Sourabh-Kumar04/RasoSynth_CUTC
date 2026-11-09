import pytest
import asyncio
from core.orchestrator_pkg.distributed_worker import DistributedTaskWorkerPool, TaskChunk


@pytest.mark.asyncio
async def test_worker_registration_and_selection():
    pool = DistributedTaskWorkerPool(heartbeat_timeout_sec=5.0)

    w1 = pool.register_worker("worker-gpu-1", capacity=2)
    w2 = pool.register_worker("worker-gpu-2", capacity=4)

    stats = pool.get_cluster_stats()
    assert stats["total_registered_workers"] == 2
    assert stats["healthy_workers"] == 2
    assert stats["total_capacity_slots"] == 6

    # Select best worker (w2 has 4 slots vs w1 with 2)
    best = pool.select_best_worker()
    assert best is not None
    assert best.worker_id == "worker-gpu-2"


@pytest.mark.asyncio
async def test_worker_dispatch_and_mapping():
    pool = DistributedTaskWorkerPool(heartbeat_timeout_sec=10.0)
    pool.register_worker("w1", capacity=4)
    pool.register_worker("w2", capacity=4)

    async def mock_handler(chunk: TaskChunk):
        await asyncio.sleep(0.01)
        return f"Synthesized output for {chunk.data['topic']}"

    items = [
        {"topic": "Cardiology"},
        {"topic": "Neurology"},
        {"topic": "Oncology"},
    ]

    results = await pool.map_chunks("job-synth-100", items, mock_handler)
    assert len(results) == 3
    for r in results:
        assert r.status == "completed"
        assert "Synthesized output for" in r.result

    # All active tasks should have returned to 0
    assert pool.get_cluster_stats()["active_tasks"] == 0


@pytest.mark.asyncio
async def test_worker_stale_reaping():
    pool = DistributedTaskWorkerPool(heartbeat_timeout_sec=0.05)
    pool.register_worker("w-stale", capacity=2)

    await asyncio.sleep(0.06)
    reaped = pool.reap_stale_workers()
    assert "w-stale" in reaped
    assert len(pool.get_healthy_workers()) == 0
