"""
Checkpoint System for Resumable Orchestration

Provides persistent checkpoint storage and retrieval for workflow state,
enabling jobs to resume from exact checkpoints without restarting.
"""

import asyncio
import json
import logging
import os
from typing import Any, Optional, List, Dict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from uuid import uuid4
import asyncpg
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class CheckpointStage(str, Enum):
    """Orchestration stages that can be checkpointed."""
    DISCOVERY = "discovery"
    EXTRACTION = "extraction"
    FILTERING = "filtering"
    CONSTRUCTION = "construction"
    EXPORT = "export"
    COMPLETED = "completed"


@dataclass
class ProviderContext:
    """Provider state at checkpoint time."""
    provider_name: str
    model: str
    api_key_hash: str  # For security, store hash not actual key
    base_url: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    cost_accumulated: float = 0.0


@dataclass
class Checkpoint:
    """
    Complete workflow checkpoint.

    Stores all state needed to resume orchestration from this point.
    """
    checkpoint_id: str = field(default_factory=lambda: str(uuid4()))
    job_id: str = ""
    stage: CheckpointStage = CheckpointStage.DISCOVERY
    progress: float = 0.0  # 0.0 - 1.0

    # Data state
    sources_discovered: int = 0
    sources_extracted: int = 0
    samples_filtered: int = 0
    samples_generated: int = 0

    # Provider context
    provider_context: Optional[ProviderContext] = None
    fallback_provider: Optional[str] = None

    # Serialized data (for resumable state)
    extracted_content: List[Dict[str, Any]] = field(default_factory=list)
    filtered_samples: List[Dict[str, Any]] = field(default_factory=list)
    constructed_samples: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Temporal
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['stage'] = self.stage.value
        data['created_at'] = self.created_at.isoformat()
        if self.provider_context:
            data['provider_context'] = asdict(self.provider_context)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create from dictionary."""
        if 'provider_context' in data and data['provider_context']:
            data['provider_context'] = ProviderContext(**data['provider_context'])
        data['stage'] = CheckpointStage(data['stage'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


class CheckpointStore:
    """
    Persistent checkpoint storage with PostgreSQL and Redis.

    - PostgreSQL: Long-term persistence, queryable history
    - Redis: Fast state access, real-time updates
    """

    def __init__(
        self,
        postgres_url: Optional[str] = None,
        redis_url: Optional[str] = None,
        checkpoint_ttl_seconds: int = 86400 * 7,  # 7 days
    ):
        self.postgres_url = (postgres_url or "").replace("postgresql+asyncpg://", "postgresql://", 1)
        self.redis_url = redis_url or ""
        self.checkpoint_ttl = checkpoint_ttl_seconds
        self._pool: Optional[asyncpg.Pool] = None
        self._redis: Optional[redis.Redis] = None
        self._in_memory_store: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """Alias for connect() to initialize store."""
        await self.connect()

    async def connect(self) -> None:
        """Initialize connections with graceful in-memory fallback."""
        if self.postgres_url.startswith("postgresql://"):
            try:
                self._pool = await asyncpg.create_pool(
                    self.postgres_url,
                    min_size=2,
                    max_size=10,
                    statement_cache_size=0,
                )
                await self._ensure_tables()
                logger.info("Checkpoint store connected to PostgreSQL")
            except Exception as e:
                logger.warning(f"Could not connect to PostgreSQL pool ({e}); using memory fallback")
                self._pool = None
                self._in_memory_store = {}
        else:
            self._pool = None
            self._in_memory_store = {}
            logger.info("Checkpoint store using in-memory mode (non-PostgreSQL URL)")

        if self.redis_url and self.redis_url.startswith("redis://"):
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                )
            except Exception:
                self._redis = None
        else:
            self._redis = None

    async def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orchestration_checkpoints (
                    checkpoint_id UUID PRIMARY KEY,
                    job_id VARCHAR(255) NOT NULL,
                    stage VARCHAR(50) NOT NULL,
                    progress FLOAT NOT NULL,
                    sources_discovered INT DEFAULT 0,
                    sources_extracted INT DEFAULT 0,
                    samples_filtered INT DEFAULT 0,
                    samples_generated INT DEFAULT 0,
                    provider_context JSONB,
                    fallback_provider VARCHAR(100),
                    extracted_content JSONB DEFAULT '[]',
                    filtered_samples JSONB DEFAULT '[]',
                    constructed_samples JSONB DEFAULT '[]',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    version INT DEFAULT 1
                );
                CREATE INDEX IF NOT EXISTS idx_checkpoints_job_id
                    ON orchestration_checkpoints(job_id);
                CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at
                    ON orchestration_checkpoints(created_at DESC);
            """)

    async def save(self, checkpoint: Checkpoint) -> str:
        """Save checkpoint to both PostgreSQL and Redis."""
        # Save to PostgreSQL for persistence if connected
        if self._pool:
            created_at = checkpoint.created_at
            if created_at and getattr(created_at, "tzinfo", None) is not None:
                created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
            async with self._pool.acquire() as conn:
                await conn.execute("""
                INSERT INTO orchestration_checkpoints (
                    checkpoint_id, job_id, stage, progress,
                    sources_discovered, sources_extracted, samples_filtered, samples_generated,
                    provider_context, fallback_provider,
                    extracted_content, filtered_samples, constructed_samples,
                    metadata, created_at, version
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
                ) ON CONFLICT (checkpoint_id) DO UPDATE SET
                    progress = EXCLUDED.progress,
                    samples_generated = EXCLUDED.samples_generated,
                    provider_context = EXCLUDED.provider_context,
                    extracted_content = EXCLUDED.extracted_content,
                    filtered_samples = EXCLUDED.filtered_samples,
                    constructed_samples = EXCLUDED.constructed_samples,
                    metadata = EXCLUDED.metadata,
                    version = EXCLUDED.version + 1
                """,
                checkpoint.checkpoint_id,
                checkpoint.job_id,
                checkpoint.stage.value,
                checkpoint.progress,
                checkpoint.sources_discovered,
                checkpoint.sources_extracted,
                checkpoint.samples_filtered,
                checkpoint.samples_generated,
                json.dumps(asdict(checkpoint.provider_context)) if checkpoint.provider_context else None,
                checkpoint.fallback_provider,
                json.dumps(checkpoint.extracted_content),
                json.dumps(checkpoint.filtered_samples),
                json.dumps(checkpoint.constructed_samples),
                json.dumps(checkpoint.metadata),
                created_at,
                checkpoint.version,
            )
        else:
            if not hasattr(self, "_in_memory_store"):
                self._in_memory_store = {}
            self._in_memory_store[str(checkpoint.checkpoint_id)] = checkpoint
            self._in_memory_store[f"{checkpoint.job_id}:latest"] = checkpoint
            h_list = self._in_memory_store.setdefault(f"{checkpoint.job_id}:history", [])
            h_list.insert(0, checkpoint)

        # Save to Redis for fast access. PostgreSQL remains authoritative.
        redis_key = f"checkpoint:{checkpoint.job_id}:latest"
        try:
            payload = json.dumps(checkpoint.to_dict())
            if self._redis:
                await self._redis.setex(redis_key, self.checkpoint_ttl, payload)
                history_key = f"checkpoint:{checkpoint.job_id}:{checkpoint.checkpoint_id}"
                await self._redis.setex(history_key, self.checkpoint_ttl, payload)
        except Exception as exc:
            logger.warning("Checkpoint cached only in PostgreSQL: %s", exc)

        logger.info(f"Checkpoint saved: {checkpoint.checkpoint_id} for job {checkpoint.job_id}")
        return checkpoint.checkpoint_id

    async def get_latest(self, job_id: str) -> Optional[Checkpoint]:
        """Get latest checkpoint for a job from Redis (fast path) or persistent store."""
        redis_key = f"checkpoint:{job_id}:latest"
        try:
            if self._redis:
                data = await self._redis.get(redis_key)
                if data:
                    return Checkpoint.from_dict(json.loads(data))
        except Exception as exc:
            logger.warning("Checkpoint Redis lookup failed; reading storage: %s", exc)

        if self._pool:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM orchestration_checkpoints WHERE job_id = $1 ORDER BY created_at DESC LIMIT 1",
                    job_id,
                )
            return self._row_to_checkpoint(row) if row else None
        else:
            return getattr(self, "_in_memory_store", {}).get(f"{job_id}:latest")

    async def get_by_id(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get specific checkpoint by ID."""
        if self._pool:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM orchestration_checkpoints
                    WHERE checkpoint_id = $1
                """, checkpoint_id)
            if row:
                return self._row_to_checkpoint(row)
            return None
        else:
            return getattr(self, "_in_memory_store", {}).get(str(checkpoint_id))

    async def get_history(self, job_id: str, limit: int = 10) -> List[Checkpoint]:
        """Get checkpoint history for a job."""
        if self._pool:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM orchestration_checkpoints
                    WHERE job_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, job_id, limit)
            return [self._row_to_checkpoint(row) for row in rows]
        else:
            h_list = getattr(self, "_in_memory_store", {}).get(f"{job_id}:history", [])
            return h_list[:limit]

    async def delete_old_checkpoints(self, job_id: str, keep_count: int = 5) -> int:
        """Delete old checkpoints, keeping latest N."""
        if not self._pool:
            return 0
        async with self._pool.acquire() as conn:
            # Get IDs to delete
            to_delete = await conn.fetch("""
                SELECT checkpoint_id FROM orchestration_checkpoints
                WHERE job_id = $1
                ORDER BY created_at DESC
                OFFSET $2
            """, job_id, keep_count)

            if to_delete:
                ids = [r['checkpoint_id'] for r in to_delete]
                await conn.execute("""
                    DELETE FROM orchestration_checkpoints
                    WHERE checkpoint_id = ANY($1)
                """, ids)

                # Clean up Redis cache entries. PostgreSQL deletion already
                # succeeded, so a cache error should not fail the operation.
                for cid in ids:
                    try:
                        await self._redis.delete(f"checkpoint:{job_id}:{cid}")
                    except Exception as exc:
                        logger.warning("Could not remove checkpoint cache entry %s: %s", cid, exc)

                logger.info(f"Deleted {len(ids)} old checkpoints for job {job_id}")
                return len(ids)
        return 0

    def _row_to_checkpoint(self, row: dict) -> Checkpoint:
        """Convert database row to Checkpoint."""
        return Checkpoint(
            checkpoint_id=str(row['checkpoint_id']),
            job_id=row['job_id'],
            stage=CheckpointStage(row['stage']),
            progress=row['progress'],
            sources_discovered=row['sources_discovered'],
            sources_extracted=row['sources_extracted'],
            samples_filtered=row['samples_filtered'],
            samples_generated=row['samples_generated'],
            provider_context=ProviderContext(**json.loads(row['provider_context'])) if row['provider_context'] else None,
            fallback_provider=row['fallback_provider'],
            extracted_content=json.loads(row['extracted_content']),
            filtered_samples=json.loads(row['filtered_samples']),
            constructed_samples=json.loads(row['constructed_samples']),
            metadata=json.loads(row['metadata']),
            created_at=row['created_at'],
            version=row['version'],
        )

    async def close(self) -> None:
        """Close connections."""
        if self._pool:
            await self._pool.close()
        if self._redis:
            if hasattr(self._redis, "aclose"):
                await self._redis.aclose()
            else:
                await self._redis.close()
        logger.info("Checkpoint store closed")


class CheckpointManager:
    """
    High-level checkpoint management.

    Coordinates checkpoint creation, retrieval, and cleanup.
    """

    def __init__(self, store: CheckpointStore, db: Any = None):
        self.store = store
        self.db = db

    async def create_checkpoint(
        self,
        job_id: str,
        stage: CheckpointStage,
        progress: float,
        sources_discovered: int = 0,
        sources_extracted: int = 0,
        samples_filtered: int = 0,
        samples_generated: int = 0,
        provider_context: Optional[ProviderContext] = None,
        extracted_content: Optional[List] = None,
        filtered_samples: Optional[List] = None,
        constructed_samples: Optional[List] = None,
        metadata: Optional[Dict] = None,
    ) -> Checkpoint:
        """Create a new checkpoint."""
        checkpoint = Checkpoint(
            job_id=job_id,
            stage=stage,
            progress=progress,
            sources_discovered=sources_discovered,
            sources_extracted=sources_extracted,
            samples_filtered=samples_filtered,
            samples_generated=samples_generated,
            provider_context=provider_context,
            extracted_content=extracted_content or [],
            filtered_samples=filtered_samples or [],
            constructed_samples=constructed_samples or [],
            metadata=metadata or {},
        )

        await self.store.save(checkpoint)

        # Clean up old checkpoints
        await self.store.delete_old_checkpoints(job_id, keep_count=5)

        return checkpoint

    async def get_resume_checkpoint(self, job_id: str) -> Optional[Checkpoint]:
        """Get checkpoint to resume from (latest with progress)."""
        checkpoint = await self.store.get_latest(job_id)
        if checkpoint and checkpoint.progress < 1.0:
            return checkpoint
        return None

    async def resume_from_checkpoint(
        self,
        job_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get state needed to resume from checkpoint.

        Returns dict with:
        - checkpoint data
        - provider context
        - pending work
        - progress
        """
        if checkpoint_id:
            checkpoint = await self.store.get_by_id(checkpoint_id)
        else:
            checkpoint = await self.get_resume_checkpoint(job_id)

        if not checkpoint:
            return None

        return {
            "checkpoint": checkpoint,
            "resume_from_stage": checkpoint.stage,
            "progress": checkpoint.progress,
            "samples_generated": checkpoint.samples_generated,
            "provider_context": checkpoint.provider_context,
            "extracted_content": checkpoint.extracted_content,
            "filtered_samples": checkpoint.filtered_samples,
            "constructed_samples": checkpoint.constructed_samples,
            "metadata": checkpoint.metadata,
        }


@dataclass
class WorkerLease:
    """Distributed worker lease for resilient zero-downtime execution."""
    job_id: str
    worker_id: str
    lease_id: str = field(default_factory=lambda: str(uuid4()))
    acquired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    heartbeat_count: int = 0
    is_active: bool = True

    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return now > exp

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "worker_id": self.worker_id,
            "lease_id": self.lease_id,
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "heartbeat_count": self.heartbeat_count,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerLease":
        return cls(
            job_id=data["job_id"],
            worker_id=data["worker_id"],
            lease_id=data.get("lease_id", str(uuid4())),
            acquired_at=datetime.fromisoformat(data["acquired_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            heartbeat_count=data.get("heartbeat_count", 0),
            is_active=data.get("is_active", True),
        )


class WorkerLeaseManager:
    """
    Distributed worker lease and heartbeat coordinator.
    Coordinates exclusive job execution, heartbeat emission,
    lease expiry detection, and orphaned job recovery.
    """

    def __init__(self, store: Optional[CheckpointStore] = None, worker_id: Optional[str] = None):
        self.store = store
        self.worker_id = worker_id or f"worker-{os.getpid()}-{uuid4().hex[:6]}"
        self._local_leases: dict[str, WorkerLease] = {}
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    @property
    def _leases(self) -> dict[str, WorkerLease]:
        if self.store is not None:
            if not hasattr(self.store, "_in_memory_leases"):
                self.store._in_memory_leases = {}
            return self.store._in_memory_leases
        return self._local_leases

    async def acquire_lease(self, job_id: str, ttl_seconds: int = 30) -> Optional[WorkerLease]:
        """Attempt to acquire or steal an expired execution lease for job_id."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        async with self._lock:
            # Fast-path Redis lease coordination if available
            if self.store and self.store._redis:
                key = f"rasosynth:lease:{job_id}"
                try:
                    payload = json.dumps({
                        "job_id": job_id,
                        "worker_id": self.worker_id,
                        "lease_id": str(uuid4()),
                        "acquired_at": now.isoformat(),
                        "expires_at": expires_at.isoformat(),
                        "heartbeat_count": 0,
                        "is_active": True,
                    })
                    acquired = await self.store._redis.set(key, payload, ex=ttl_seconds, nx=True)
                    if acquired:
                        lease = WorkerLease(job_id=job_id, worker_id=self.worker_id, expires_at=expires_at)
                        self._leases[job_id] = lease
                        self._start_heartbeat(job_id, ttl_seconds)
                        return lease

                    existing_raw = await self.store._redis.get(key)
                    if existing_raw:
                        data = json.loads(existing_raw)
                        existing_lease = WorkerLease.from_dict(data)
                        if existing_lease.is_expired() or existing_lease.worker_id == self.worker_id:
                            await self.store._redis.set(key, payload, ex=ttl_seconds)
                            lease = WorkerLease(job_id=job_id, worker_id=self.worker_id, expires_at=expires_at)
                            self._leases[job_id] = lease
                            self._start_heartbeat(job_id, ttl_seconds)
                            return lease
                    return None
                except Exception as e:
                    logger.warning(f"Redis lease acquisition error ({e}); using memory fallback")

            # In-memory store fallback
            current = self._leases.get(job_id)
            if current and not current.is_expired() and current.worker_id != self.worker_id and current.is_active:
                logger.warning(f"Job {job_id} already locked by worker {current.worker_id}")
                return None

            lease = WorkerLease(
                job_id=job_id,
                worker_id=self.worker_id,
                acquired_at=now,
                expires_at=expires_at,
                is_active=True,
            )
            self._leases[job_id] = lease
            self._start_heartbeat(job_id, ttl_seconds)
            return lease

    def _start_heartbeat(self, job_id: str, ttl_seconds: int) -> None:
        """Start background heartbeat loop to renew lease."""
        if job_id in self._heartbeat_tasks and not self._heartbeat_tasks[job_id].done():
            return

        interval = max(1.0, ttl_seconds / 3.0)

        async def _loop():
            try:
                while True:
                    await asyncio.sleep(interval)
                    renewed = await self.renew_lease(job_id, ttl_seconds)
                    if not renewed:
                        break
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"Heartbeat loop stopped for job {job_id}: {e}")

        self._heartbeat_tasks[job_id] = asyncio.create_task(_loop())

    async def renew_lease(self, job_id: str, ttl_seconds: int = 30) -> bool:
        """Renew active lease and extend expiration timestamp."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        async with self._lock:
            if self.store and self.store._redis:
                key = f"rasosynth:lease:{job_id}"
                try:
                    raw = await self.store._redis.get(key)
                    if raw:
                        data = json.loads(raw)
                        if data.get("worker_id") == self.worker_id:
                            data["expires_at"] = expires_at.isoformat()
                            data["heartbeat_count"] = data.get("heartbeat_count", 0) + 1
                            await self.store._redis.setex(key, ttl_seconds, json.dumps(data))
                            if job_id in self._leases:
                                self._leases[job_id].expires_at = expires_at
                                self._leases[job_id].heartbeat_count += 1
                            return True
                except Exception as e:
                    logger.debug(f"Redis lease renewal error: {e}")

            if job_id in self._leases and self._leases[job_id].worker_id == self.worker_id:
                self._leases[job_id].expires_at = expires_at
                self._leases[job_id].heartbeat_count += 1
                return True
            return False

    async def release_lease(self, job_id: str) -> bool:
        """Release worker lease and cancel heartbeat loop."""
        async with self._lock:
            task = self._heartbeat_tasks.pop(job_id, None)
            if task and not task.done():
                task.cancel()

            if self.store and self.store._redis:
                try:
                    await self.store._redis.delete(f"rasosynth:lease:{job_id}")
                except Exception:
                    pass

            if job_id in self._leases:
                self._leases[job_id].is_active = False
                del self._leases[job_id]
                return True
            return False

    async def detect_orphaned_jobs(self, running_job_ids: list[str]) -> list[str]:
        """Identify running jobs whose worker leases expired."""
        orphans = []
        now = datetime.now(timezone.utc)

        for jid in running_job_ids:
            if self.store and self.store._redis:
                try:
                    raw = await self.store._redis.get(f"rasosynth:lease:{jid}")
                    if not raw:
                        orphans.append(jid)
                        continue
                    data = json.loads(raw)
                    exp = datetime.fromisoformat(data["expires_at"])
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    if now > exp:
                        orphans.append(jid)
                        continue
                except Exception:
                    pass

            lease = self._leases.get(jid)
            if not lease or lease.is_expired():
                orphans.append(jid)
        return orphans
