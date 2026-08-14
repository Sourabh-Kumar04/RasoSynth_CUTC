"""
Checkpoint System for Resumable Orchestration

Provides persistent checkpoint storage and retrieval for workflow state,
enabling jobs to resume from exact checkpoints without restarting.
"""

import asyncio
import json
import logging
from typing import Any, Optional, List, Dict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from uuid import uuid4
import asyncio
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
    created_at: datetime = field(default_factory=datetime.utcnow)
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
        postgres_url: str,
        redis_url: str,
        checkpoint_ttl_seconds: int = 86400 * 7,  # 7 days
    ):
        self.postgres_url = postgres_url
        self.redis_url = redis_url
        self.checkpoint_ttl = checkpoint_ttl_seconds
        self._pool: Optional[asyncpg.Pool] = None
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Initialize connections."""
        self._pool = await asyncpg.create_pool(
            self.postgres_url,
            min_size=2,
            max_size=10,
        )
        self._redis = redis.from_url(self.redis_url, decode_responses=True)
        await self._ensure_tables()
        logger.info("Checkpoint store connected")

    async def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
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
        # Save to PostgreSQL for persistence
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
                checkpoint.created_at,
                checkpoint.version,
            )

        # Save to Redis for fast access
        redis_key = f"checkpoint:{checkpoint.job_id}:latest"
        await self._redis.setex(
            redis_key,
            self.checkpoint_ttl,
            json.dumps(checkpoint.to_dict())
        )

        # Also save with checkpoint ID for history
        history_key = f"checkpoint:{checkpoint.job_id}:{checkpoint.checkpoint_id}"
        await self._redis.setex(history_key, self.checkpoint_ttl, json.dumps(checkpoint.to_dict()))

        logger.info(f"Checkpoint saved: {checkpoint.checkpoint_id} for job {checkpoint.job_id}")
        return checkpoint.checkpoint_id

    async def get_latest(self, job_id: str) -> Optional[Checkpoint]:
        """Get latest checkpoint for a job from Redis (fast path)."""
        redis_key = f"checkpoint:{job_id}:latest"
        data = await self._redis.get(redis_key)
        if data:
            return Checkpoint.from_dict(json.loads(data))
        return None

    async def get_by_id(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get specific checkpoint by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM orchestration_checkpoints
                WHERE checkpoint_id = $1
            """, checkpoint_id)
        if row:
            return self._row_to_checkpoint(row)
        return None

    async def get_history(self, job_id: str, limit: int = 10) -> List[Checkpoint]:
        """Get checkpoint history for a job."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM orchestration_checkpoints
                WHERE job_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, job_id, limit)
        return [self._row_to_checkpoint(row) for row in rows]

    async def delete_old_checkpoints(self, job_id: str, keep_count: int = 5) -> int:
        """Delete old checkpoints, keeping latest N."""
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

                # Clean up Redis
                for cid in ids:
                    await self._redis.delete(f"checkpoint:{job_id}:{cid}")

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
            await self._redis.close()
        logger.info("Checkpoint store closed")


class CheckpointManager:
    """
    High-level checkpoint management.

    Coordinates checkpoint creation, retrieval, and cleanup.
    """

    def __init__(self, store: CheckpointStore):
        self.store = store

    async def create_checkpoint(
        self,
        job_id: str,
        stage: CheckpointStage,
        progress: float,
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