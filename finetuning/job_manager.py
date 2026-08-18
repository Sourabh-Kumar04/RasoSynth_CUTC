"""
Fine-tune job lifecycle manager.

Key improvements over v1:
- No thread-wrapping anti-pattern: Trainer.train() is a pure async generator,
  so we just `async for` over it directly.
- In-memory log ring buffer per job (capped at LOG_BUFFER_SIZE).
- `get_logs(job_id, limit)` for the /logs REST endpoint.
- `list_jobs` result cached for LIST_CACHE_TTL seconds to reduce DB load.
- Warns if MAX_CONCURRENT > 1 and CUDA is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections import deque
from datetime import datetime
from typing import AsyncGenerator, Optional

from core.db import DatabaseManager, FineTuneJob
from finetuning.trainer import FineTuneConfig, Trainer

logger = logging.getLogger(__name__)

MAX_CONCURRENT_JOBS = int(os.environ.get("FINETUNE_MAX_CONCURRENT", "1"))
LOG_BUFFER_SIZE = int(os.environ.get("FINETUNE_LOG_BUFFER", "500"))
LIST_CACHE_TTL = 2.0  # seconds


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


if MAX_CONCURRENT_JOBS > 1 and not _cuda_available():
    logger.warning(
        "FINETUNE_MAX_CONCURRENT=%d but CUDA is not available. "
        "Multiple concurrent fine-tune jobs will contend for CPU.",
        MAX_CONCURRENT_JOBS,
    )


class FinetuneJobManager:
    """
    Singleton-style manager — one instance stored on app.state.ft_manager.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
        # job_id -> asyncio.Task
        self._tasks: dict[str, asyncio.Task] = {}
        # job_id -> list[asyncio.Queue]  (one per WS subscriber)
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        # job_id -> deque[dict]  (capped ring buffer)
        self._logs: dict[str, deque] = {}
        # cached list result
        self._list_cache: Optional[list[dict]] = None
        self._list_cache_ts: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    async def create_job(self, config: dict) -> dict:
        job_id = str(uuid.uuid4())
        ft_config = FineTuneConfig.from_dict(config)
        ft_config.output_dir = str(os.path.join(ft_config.output_dir, job_id))

        total_epochs = ft_config.num_train_epochs if ft_config.max_steps <= 0 else 1

        fj = await self.db.create_finetune_job({
            "id": job_id,
            "status": "pending",
            "base_model": ft_config.base_model,
            "output_model_name": ft_config.output_model_name or job_id,
            "dataset_id": ft_config.dataset_id or None,
            "config": ft_config.to_dict(),
            "total_epochs": total_epochs,
        })

        self._logs[job_id] = deque(maxlen=LOG_BUFFER_SIZE)
        self._list_cache = None  # Invalidate cache

        task = asyncio.create_task(self._run_job(job_id, ft_config), name=f"finetune-{job_id}")
        self._tasks[job_id] = task

        logger.info("Fine-tune job %s created (model=%s)", job_id, ft_config.base_model)
        return fj.to_dict()

    async def cancel_job(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            await self.db.update_finetune_job(job_id, status="cancelled")
            await self._broadcast(job_id, {"type": "cancelled", "job_id": job_id})
            self._list_cache = None
            return True
        return False

    async def get_job(self, job_id: str) -> Optional[dict]:
        fj: Optional[FineTuneJob] = await self.db.get_finetune_job(job_id)
        return fj.to_dict() if fj else None

    async def list_jobs(self, limit: int = 100) -> list[dict]:
        """Return jobs from DB, with a short cache to reduce DB pressure."""
        import time
        now = time.monotonic()
        if self._list_cache is not None and (now - self._list_cache_ts) < LIST_CACHE_TTL:
            return self._list_cache[:limit]
        jobs = await self.db.list_finetune_jobs(limit=limit)
        result = [j.to_dict() for j in jobs]
        self._list_cache = result
        self._list_cache_ts = now
        return result

    def get_logs(self, job_id: str, limit: int = 200) -> list[dict]:
        """Return last N log events from the in-memory ring buffer."""
        buf = self._logs.get(job_id)
        if buf is None:
            return []
        entries = list(buf)
        return entries[-limit:] if limit < len(entries) else entries

    async def subscribe(self, job_id: str) -> AsyncGenerator[dict, None]:
        """Async generator of training events for a job (WebSocket use)."""
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        self._subscribers.setdefault(job_id, []).append(q)
        try:
            current = await self.get_job(job_id)
            if current:
                yield {"type": "status", "job": current}
            # Replay buffered logs so late subscribers catch up
            for entry in self.get_logs(job_id):
                yield entry
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield event
                    if event.get("type") in ("completed", "error", "cancelled"):
                        break
                except asyncio.TimeoutError:
                    yield {"type": "ping"}
        finally:
            subs = self._subscribers.get(job_id, [])
            if q in subs:
                subs.remove(q)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _run_job(self, job_id: str, config: FineTuneConfig):
        async with self._semaphore:
            await self.db.update_finetune_job(job_id, status="running", started_at=datetime.utcnow())
            self._list_cache = None
            await self._broadcast(job_id, {"type": "started", "job_id": job_id})

            trainer = Trainer(config)
            try:
                async for event in trainer.train():
                    event["job_id"] = job_id

                    # Store in ring buffer
                    buf = self._logs.setdefault(job_id, deque(maxlen=LOG_BUFFER_SIZE))
                    buf.append(event)

                    await self._broadcast(job_id, event)
                    etype = event.get("type")

                    if etype == "progress":
                        await self.db.update_finetune_job(
                            job_id,
                            progress=event.get("progress", 0),
                            current_epoch=int(event.get("epoch", 0)),
                            train_loss=event.get("loss"),
                        )
                    elif etype == "eval":
                        await self.db.update_finetune_job(job_id, eval_loss=event.get("eval_loss"))
                    elif etype == "completed":
                        await self.db.update_finetune_job(
                            job_id, status="completed", progress=100.0,
                            output_path=event.get("output_path"),
                            hf_repo_url=event.get("hf_repo_url"),
                            completed_at=datetime.utcnow(),
                        )
                        self._list_cache = None
                        logger.info("Fine-tune job %s completed", job_id)
                    elif etype == "error":
                        await self.db.update_finetune_job(
                            job_id, status="failed",
                            error=event.get("message"),
                            completed_at=datetime.utcnow(),
                        )
                        self._list_cache = None
                        logger.error("Fine-tune job %s failed: %s", job_id, event.get("message"))
                    elif etype == "cancelled":
                        await self.db.update_finetune_job(
                            job_id, status="cancelled", completed_at=datetime.utcnow()
                        )
                        self._list_cache = None

            except asyncio.CancelledError:
                trainer.cancel()
                await self.db.update_finetune_job(
                    job_id, status="cancelled", completed_at=datetime.utcnow()
                )
                await self._broadcast(job_id, {"type": "cancelled", "job_id": job_id})
                self._list_cache = None

            except Exception as exc:
                await self.db.update_finetune_job(
                    job_id, status="failed", error=str(exc), completed_at=datetime.utcnow()
                )
                await self._broadcast(job_id, {"type": "error", "job_id": job_id, "message": str(exc)})
                self._list_cache = None
                logger.exception("Unexpected error in fine-tune job %s", job_id)

            finally:
                self._tasks.pop(job_id, None)

    async def _broadcast(self, job_id: str, event: dict):
        for q in list(self._subscribers.get(job_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
