"""Database management with SQLAlchemy supporting both PostgreSQL and SQLite."""
import uuid
import os
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional

def utc_now() -> datetime:
    """Return naive UTC datetime compatible with PostgreSQL asyncpg and SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _is_valid_uuid(val: any) -> bool:
    """Check if value is a valid UUID string or UUID object."""
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text, ForeignKey, delete

Base = declarative_base()

# Use appropriate UUID type based on database
try:
    # Try to import PostgreSQL UUID first
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
except ImportError:
    # Fallback to standard UUID for SQLite
    from sqlalchemy.types import UUID as PG_UUID


class Job(Base):
    """Job model for tracking dataset generation jobs."""
    __tablename__ = "jobs"
    __table_args__ = (
        # Index for filtering jobs by status (common query pattern)
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    config = Column(JSON)
    progress = Column(Float, default=0.0)
    current_stage = Column(String)
    samples_processed = Column(Integer, default=0)
    samples_generated = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    error = Column(Text)
    sources_discovered = Column(Integer, default=0)
    sources_extracted = Column(Integer, default=0)
    samples_filtered = Column(Integer, default=0)
    quality_score = Column(Float, nullable=True)
    merkle_root = Column(String, nullable=True)
    owner = Column(String(255), nullable=True, index=True)

    datasets = relationship("Dataset", back_populates="job", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        q = self.quality_score
        if q is None and self.datasets:
            meta = self.datasets[0].metadata_ or {}
            q = meta.get("quality_score") or (meta.get("quality_breakdown") or {}).get("composite")
        return {
            "id": str(self.id),
            "status": self.status,
            "config": self.config or {},
            "progress": self.progress,
            "current_stage": self.current_stage,
            "quality_score": q,
            "merkle_root": self.merkle_root or (self.datasets[0].metadata_.get("merkle_root_hash") if self.datasets and self.datasets[0].metadata_ else None),
            "owner": getattr(self, "owner", None),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Dataset(Base):
    """Dataset model for storing generated datasets."""
    __tablename__ = "datasets"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(PG_UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    name = Column(String, nullable=False)
    type = Column(String)
    size = Column(Integer)
    created_at = Column(DateTime, default=utc_now)
    metadata_ = Column("metadata", JSON)
    output_path = Column(String)
    owner = Column(String(255), nullable=True, index=True)

    job = relationship("Job", back_populates="datasets")
    samples = relationship("Sample", back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(Base):
    """Immutable, trainable snapshot of a dataset and its provenance manifest."""
    __tablename__ = "dataset_versions"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(PG_UUID(as_uuid=False), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="approved", index=True)
    sample_count = Column(Integer, nullable=False, default=0)
    content_hash = Column(String(64), nullable=False, index=True)
    manifest = Column(JSON, default=dict)
    output_path = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "dataset_id": self.dataset_id, "version": self.version,
            "status": self.status, "sample_count": self.sample_count,
            "content_hash": self.content_hash, "manifest": self.manifest or {},
            "output_path": self.output_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ContextBundle(Base):
    """Persisted evidence window used to construct a dataset and audit it later."""
    __tablename__ = "context_bundles"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(PG_UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    content_hash = Column(String(64), nullable=False, index=True)
    source_count = Column(Integer, default=0)
    evidence = Column(JSON, default=list)
    created_at = Column(DateTime, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "job_id": self.job_id, "content_hash": self.content_hash,
            "source_count": self.source_count, "evidence": self.evidence or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ReviewCalibrationReport(Base):
    """Immutable record of automated-review alignment with human decisions."""
    __tablename__ = "review_calibration_reports"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    report = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utc_now, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "report": self.report or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WorkflowSchedule(Base):
    """Durable definition for periodic refresh, recrawl, or retraining work."""
    __tablename__ = "workflow_schedules"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    workflow_type = Column(String(64), nullable=False, index=True)
    interval_seconds = Column(Integer, nullable=False)
    workflow_config = Column(JSON, default=dict)
    enabled = Column(Integer, nullable=False, default=1, index=True)
    next_run_at = Column(DateTime, nullable=False, index=True)
    last_run_at = Column(DateTime)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "workflow_type": self.workflow_type,
            "interval_seconds": self.interval_seconds, "workflow_config": self.workflow_config or {},
            "enabled": bool(self.enabled),
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WorkflowScheduleRun(Base):
    """Immutable execution history for a schedule occurrence."""
    __tablename__ = "workflow_schedule_runs"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    schedule_id = Column(PG_UUID(as_uuid=False), ForeignKey("workflow_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(PG_UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    detail = Column(JSON, default=dict)
    started_at = Column(DateTime, default=utc_now)
    finished_at = Column(DateTime)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "schedule_id": self.schedule_id, "job_id": self.job_id,
            "status": self.status, "detail": self.detail or {},
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class SourceSnapshot(Base):
    """Immutable source capture, including retrieval metadata and raw content."""
    __tablename__ = "source_snapshots"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(PG_UUID(as_uuid=False), ForeignKey("sources.id", ondelete="SET NULL"), index=True)
    job_id = Column(PG_UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    content_type = Column(String(128))
    license = Column(String)
    content = Column(Text, nullable=False, default="")
    metadata_ = Column("metadata", JSON, default=dict)
    retrieved_at = Column(DateTime, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "source_id": self.source_id, "job_id": self.job_id,
            "url": self.url, "content_hash": self.content_hash, "content_type": self.content_type,
            "license": self.license, "metadata": self.metadata_ or {},
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
        }


class EvidenceChunk(Base):
    """Auditable chunk from a source snapshot used by context/synthesis stages."""
    __tablename__ = "evidence_chunks"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id = Column(PG_UUID(as_uuid=False), ForeignKey("source_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "snapshot_id": self.snapshot_id, "chunk_index": self.chunk_index,
            "content_hash": self.content_hash, "content": self.content,
            "metadata": self.metadata_ or {},
        }


class Sample(Base):
    """Sample model for individual training samples."""
    __tablename__ = "samples"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(PG_UUID(as_uuid=False), ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    instruction = Column(Text)
    response = Column(Text)
    input = Column(Text)
    metadata_ = Column("metadata", JSON)
    quality_score = Column(Float, index=True)
    difficulty_tier = Column(Integer)
    created_at = Column(DateTime, default=utc_now, index=True)

    dataset = relationship("Dataset", back_populates="samples")
    quality_scores = relationship("QualityScore", back_populates="sample", cascade="all, delete-orphan")


class Source(Base):
    """Source model for tracking discovered data sources."""
    __tablename__ = "sources"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String)
    source_type = Column(String)
    title = Column(String)
    metadata_ = Column("metadata", JSON)
    discovered_at = Column(DateTime, default=utc_now)
    license = Column(String)


class QualityScore(Base):
    """Quality score model for sample evaluation."""
    __tablename__ = "quality_scores"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    sample_id = Column(PG_UUID(as_uuid=False), ForeignKey("samples.id", ondelete="CASCADE"))
    relevance = Column(Float)
    toxicity = Column(Float)
    hallucination = Column(Float)
    overall = Column(Float)
    evaluated_at = Column(DateTime, default=utc_now)

    sample = relationship("Sample", back_populates="quality_scores")


class FineTuneJob(Base):
    """Fine-tuning job model — tracks PEFT/LoRA training runs."""
    __tablename__ = "finetune_jobs"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String(255), nullable=True, index=True)
    # job metadata
    status = Column(String(32), nullable=False, default="pending", index=True)  # pending/running/completed/failed/cancelled
    base_model = Column(String(255), nullable=False)          # e.g. "unsloth/llama-3-8b"
    output_model_name = Column(String(255))                   # HF Hub repo or local path
    # config payload – lora_r, lora_alpha, epochs, batch_size, lr, push_to_hub, etc.
    config = Column(JSON, default=dict)
    # results
    progress = Column(Float, default=0.0)
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, default=1)
    train_loss = Column(Float)
    eval_loss = Column(Float)
    error = Column(Text)
    output_path = Column(String(512))                         # local checkpoint dir
    hf_repo_url = Column(String(512))                         # HF Hub URL if pushed
    owner = Column(String(255), nullable=True, index=True)
    # timing
    created_at = Column(DateTime, default=utc_now)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "status": self.status,
            "base_model": self.base_model,
            "output_model_name": self.output_model_name,
            "config": self.config or {},
            "progress": self.progress,
            "current_epoch": self.current_epoch,
            "total_epochs": self.total_epochs,
            "train_loss": self.train_loss,
            "eval_loss": self.eval_loss,
            "error": self.error,
            "output_path": self.output_path,
            "hf_repo_url": self.hf_repo_url,
            "owner": getattr(self, "owner", None),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ReviewQueueItem(Base):
    """Persistent human-review queue item."""
    __tablename__ = "review_queue"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, nullable=False, index=True)
    dataset_id = Column(String, default="")
    instruction = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    source_url = Column(String, default="")
    source_text = Column(Text, default="")
    # quality signals
    quality_score = Column(Float, default=0.0)
    hallucination_risk = Column(Float, default=0.0)
    duplicate_score = Column(Float, default=0.0)
    diversity_score = Column(Float, default=0.0)
    # review state
    review_status = Column(String, default="pending", index=True)   # pending/in_review/approved/rejected/flagged
    review_decision = Column(String)                                  # approve/reject/edit
    review_notes = Column(Text, default="")
    reviewed_by = Column(String, default="")
    review_timestamp = Column(DateTime)
    edited_instruction = Column(Text)
    edited_response = Column(Text)
    review_version = Column(Integer, default=0)
    extra_metadata = Column(JSON, default=dict)
    owner = Column(String(255), nullable=True, index=True)
    # timestamps
    created_at = Column(DateTime, default=utc_now, index=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "dataset_id": self.dataset_id,
            "instruction": self.instruction,
            "response": self.response,
            "source_url": self.source_url,
            "source_text": (self.source_text or "")[:200],
            "quality_score": self.quality_score,
            "hallucination_risk": self.hallucination_risk,
            "duplicate_score": self.duplicate_score,
            "diversity_score": self.diversity_score,
            "review_status": self.review_status,
            "review_decision": self.review_decision,
            "review_notes": self.review_notes,
            "reviewed_by": self.reviewed_by,
            "review_timestamp": self.review_timestamp.isoformat() if self.review_timestamp else None,
            "edited_instruction": self.edited_instruction,
            "edited_response": self.edited_response,
            "review_version": self.review_version,
            "metadata": self.extra_metadata or {},
            "owner": getattr(self, "owner", None),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DatabaseManager:
    """Database manager for async SQLAlchemy operations."""

    def __init__(self, database_url: str):
        connect_args = {}
        if "postgresql" in database_url:
            if "sslmode=" in database_url:
                database_url = database_url.replace("sslmode=", "ssl=")
            # Disable prepared statement caching for Supabase Connection Pooler / pgbouncer
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_cache_size"] = 0
        self.engine = create_async_engine(database_url, echo=False, connect_args=connect_args)
        self.session_maker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def close(self):
        """Dispose the database engine and release connections."""
        import logging
        logger = logging.getLogger(__name__)
        try:
            if self.engine:
                await self.engine.dispose()
                logger.info('Database engine disposed')
        except Exception as e:
            logger.warning(f'Error disposing engine: {e}')

    async def create_tables(self):
        """Create all database tables, apply safe schema migrations, and
        set performance-oriented SQLite pragmas."""
        async with self.engine.begin() as conn:
            # ── SQLite performance / durability settings ──────────────
            database_url = str(self.engine.url)
            if "sqlite" in database_url:
                try:
                    await conn.execute(text("PRAGMA journal_mode=WAL"))
                    await conn.execute(text("PRAGMA busy_timeout=5000"))
                    await conn.execute(text("PRAGMA foreign_keys=ON"))
                except Exception:
                    pass

            # ── Create all tables declared via core.db.Base ───────────
            try:
                await conn.run_sync(Base.metadata.create_all)
            except Exception as e:
                if "already exists" in str(e).lower():
                    pass
                else:
                    raise

            # ── Safe schema migration for existing deployments ─────────
            from sqlalchemy import text

            if "sqlite" in database_url:
                for col, coltype in (
                    ("sources_discovered", "INTEGER DEFAULT 0"),
                    ("sources_extracted", "INTEGER DEFAULT 0"),
                    ("samples_filtered", "INTEGER DEFAULT 0"),
                    # Job.quality_score / Job.merkle_root exist in the model
                    # (core/db.py Job) but pre-date the persistent SQLite
                    # fallback DB (outputs/rasosynthtune.db); without these
                    # the SELECT of all Job columns fails with
                    # "no such column: jobs.quality_score".
                    ("quality_score", "FLOAT"),
                    ("merkle_root", "VARCHAR"),
                    ("owner", "VARCHAR(255)"),
                ):
                    try:
                        await conn.execute(
                            text(f"ALTER TABLE jobs ADD COLUMN {col} {coltype}")
                        )
                    except Exception:
                        pass  # Column already exists
                for tbl in ("datasets", "finetune_jobs", "review_queue"):
                    try:
                        await conn.execute(
                            text(f"ALTER TABLE {tbl} ADD COLUMN owner VARCHAR(255)")
                        )
                    except Exception:
                        pass
            else:
                await conn.execute(
                    text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS sources_discovered INTEGER DEFAULT 0")
                )
                await conn.execute(
                    text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS sources_extracted INTEGER DEFAULT 0")
                )
                await conn.execute(
                    text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS samples_filtered INTEGER DEFAULT 0")
                )
                await conn.execute(
                    text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS quality_score FLOAT")
                )
                await conn.execute(
                    text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS merkle_root VARCHAR")
                )
                await conn.execute(
                    text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS owner VARCHAR(255)")
                )
                await conn.execute(
                    text("ALTER TABLE datasets ADD COLUMN IF NOT EXISTS owner VARCHAR(255)")
                )
                await conn.execute(
                    text("ALTER TABLE finetune_jobs ADD COLUMN IF NOT EXISTS owner VARCHAR(255)")
                )
                await conn.execute(
                    text("ALTER TABLE review_queue ADD COLUMN IF NOT EXISTS owner VARCHAR(255)")
                )
                try:
                    await conn.execute(
                        text("""
                        DO $$
                        BEGIN
                            ALTER TABLE finetune_jobs DROP CONSTRAINT IF EXISTS finetune_jobs_dataset_id_fkey;
                            ALTER TABLE finetune_jobs ALTER COLUMN dataset_id TYPE VARCHAR(255) USING dataset_id::varchar;
                        EXCEPTION
                            WHEN OTHERS THEN NULL;
                        END $$;
                        """)
                    )
                except Exception:
                    pass

            # ── Performance indexes for scale ─────────────────────────
            indexes = [
                ("ix_jobs_owner", "jobs", "owner"),
                ("ix_datasets_owner", "datasets", "owner"),
                ("ix_finetune_jobs_owner", "finetune_jobs", "owner"),
                ("ix_review_queue_owner", "review_queue", "owner"),
                ("ix_jobs_status", "jobs", "status"),
                ("ix_jobs_created_at", "jobs", "created_at"),
                ("ix_datasets_job_id", "datasets", "job_id"),
                ("ix_datasets_created_at", "datasets", "created_at"),
                ("ix_dataset_versions_dataset_id", "dataset_versions", "dataset_id"),
                ("ix_context_bundles_job_id", "context_bundles", "job_id"),
                ("ix_review_calibration_reports_created_at", "review_calibration_reports", "created_at"),
                ("ix_workflow_schedules_due", "workflow_schedules", "next_run_at"),
                ("ix_workflow_schedule_runs_schedule_id", "workflow_schedule_runs", "schedule_id"),
                ("ix_source_snapshots_job_id", "source_snapshots", "job_id"),
                ("ix_evidence_chunks_snapshot_id", "evidence_chunks", "snapshot_id"),
                ("ix_samples_dataset_id", "samples", "dataset_id"),
                ("ix_finetune_jobs_status", "finetune_jobs", "status"),
                ("ix_finetune_jobs_dataset_id", "finetune_jobs", "dataset_id"),
                ("ix_review_queue_job_id", "review_queue", "job_id"),
                ("ix_review_queue_status", "review_queue", "review_status"),
                ("ix_review_queue_created_at", "review_queue", "created_at"),
            ]
            for idx_name, table, column in indexes:
                try:
                    await conn.execute(
                        text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
                    )
                except Exception:
                    pass  # Index may already exist

    async def drop_tables(self):
        """Drop all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def _commit_with_retry(self, session, max_retries=5, initial_delay=0.1):
        """Commit a session with exponential backoff and jitter for transactional resilience."""
        import random
        import asyncio
        from sqlalchemy.exc import OperationalError, DBAPIError
        
        for attempt in range(max_retries):
            try:
                await session.commit()
                return
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if attempt == max_retries - 1:
                    raise e
                delay = initial_delay * (2 ** attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)
            except Exception as e:
                await session.rollback()
                raise e

    async def create_job(self, config: dict, owner: Optional[str] = None) -> Job:
        """Create a new job."""
        async with self.session_maker() as session:
            job_id = config.get("id") or str(uuid.uuid4())
            resolved_owner = owner or config.get("owner")
            job = Job(id=job_id, config=config, status=config.get("status", "pending"), owner=resolved_owner)
            session.add(job)
            await self._commit_with_retry(session)
            _ = (job.id, job.status, job.created_at, job.updated_at, job.config, job.progress, job.current_stage)
            return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        if not _is_valid_uuid(job_id):
            return None
        async with self.session_maker() as session:
            job = await session.get(Job, job_id)
            if job:
                _ = (job.id, job.status, job.created_at, job.updated_at, job.config, job.progress, job.current_stage)
            return job

    async def update_job(self, job_id: str, status_data: Optional[dict] = None, **kwargs):
        """Update job fields safely accepting either a dict or keyword arguments."""
        if not _is_valid_uuid(job_id):
            return
        fields = dict(status_data or {})
        fields.update(kwargs)
        async with self.session_maker() as session:
            job = await session.get(Job, job_id)
            if job:
                for key, value in fields.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                await self._commit_with_retry(session)

    async def list_jobs(self, status: Optional[str] = None, limit: int = 100, owner: Optional[str] = None) -> list[Job]:
        """List jobs with optional status and owner filters."""
        from sqlalchemy import select
        async with self.session_maker() as session:
            stmt = select(Job).order_by(Job.created_at.desc())
            if status:
                stmt = stmt.where(Job.status == status)
            if owner is not None:
                stmt = stmt.where(Job.owner == owner)
            result = await session.execute(stmt.limit(limit))
            jobs = list(result.scalars().all())
            for j in jobs:
                _ = (j.id, j.status, j.created_at, j.updated_at, j.config, j.progress, j.current_stage)
            return jobs

    async def clear_all_jobs(self):
        """Delete all jobs from database."""
        async with self.session_maker() as session:
            await session.execute(delete(Job))
            await self._commit_with_retry(session)

    async def create_dataset(self, job_id: str, name: str, type: str, size: int, metadata: dict, output_path: str, owner: Optional[str] = None) -> Dataset:
        """Create a new dataset."""
        async with self.session_maker() as session:
            ds_id = str(uuid.uuid4())
            resolved_owner = owner or (metadata or {}).get("owner")
            if not resolved_owner and job_id:
                try:
                    parent_job = await session.get(Job, job_id)
                    if parent_job and parent_job.owner:
                        resolved_owner = parent_job.owner
                except Exception:
                    pass
            dataset = Dataset(
                id=ds_id,
                job_id=job_id,
                name=name,
                type=type,
                size=size,
                metadata_=metadata,
                output_path=output_path,
                owner=resolved_owner,
            )
            session.add(dataset)
            await self._commit_with_retry(session)
            _ = (dataset.id, dataset.job_id, dataset.name, dataset.type, dataset.size, dataset.created_at, dataset.output_path, dataset.metadata_)
            return dataset

    async def create_dataset_version(
        self, dataset_id: str, version: str, sample_count: int, content_hash: str,
        manifest: dict, output_path: str, status: str = "approved",
    ) -> DatasetVersion:
        async with self.session_maker() as session:
            record = DatasetVersion(
                dataset_id=dataset_id, version=version, sample_count=sample_count,
                content_hash=content_hash, manifest=manifest, output_path=output_path,
                status=status,
            )
            session.add(record)
            await self._commit_with_retry(session)
            _ = record.id
            return record

    async def get_dataset_version(self, version_id: str) -> Optional[DatasetVersion]:
        if not _is_valid_uuid(version_id):
            return None
        async with self.session_maker() as session:
            record = await session.get(DatasetVersion, version_id)
            if record:
                _ = record.id
            return record

    async def create_context_bundle(self, job_id: str, content_hash: str, evidence: list[dict]) -> ContextBundle:
        async with self.session_maker() as session:
            record = ContextBundle(
                job_id=job_id, content_hash=content_hash,
                source_count=len(evidence), evidence=evidence,
            )
            session.add(record)
            await self._commit_with_retry(session)
            _ = record.id
            return record

    async def create_review_calibration_report(self, report: dict) -> ReviewCalibrationReport:
        async with self.session_maker() as session:
            record = ReviewCalibrationReport(report=report)
            session.add(record)
            await self._commit_with_retry(session)
            _ = record.id
            return record

    async def list_datasets(self, limit: int = 100, owner: Optional[str] = None) -> list[Dataset]:
        """List all datasets ordered by creation date, optionally filtered by owner."""
        async with self.session_maker() as session:
            from sqlalchemy import select
            stmt = select(Dataset).order_by(Dataset.created_at.desc())
            if owner is not None:
                stmt = stmt.where(Dataset.owner == owner)
            result = await session.execute(stmt.limit(limit))
            datasets = list(result.scalars().all())
            for d in datasets:
                _ = (d.id, d.job_id, d.name, d.type, d.size, d.created_at, d.output_path, d.metadata_)
            return datasets

    async def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get a dataset by ID."""
        if not _is_valid_uuid(dataset_id):
            return None
        async with self.session_maker() as session:
            dataset = await session.get(Dataset, dataset_id)
            if dataset:
                _ = (dataset.id, dataset.job_id, dataset.name, dataset.type, dataset.size, dataset.created_at, dataset.output_path, dataset.metadata_)
            return dataset

    async def get_datasets_by_job(self, job_id: str) -> list[Dataset]:
        """Get all datasets for a specific job."""
        if not _is_valid_uuid(job_id):
            return []
        async with self.session_maker() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Dataset).filter(Dataset.job_id == job_id)
            )
            datasets = list(result.scalars().all())
            for d in datasets:
                _ = (d.id, d.job_id, d.name, d.type, d.size, d.created_at, d.output_path, d.metadata_)
            return datasets

    async def create_sample(self, dataset_id: str, data: dict) -> Sample:
        """Create a new sample."""
        sample_dict = dict(data)
        if "metadata" in sample_dict and "metadata_" not in sample_dict:
            sample_dict["metadata_"] = sample_dict.pop("metadata")
        async with self.session_maker() as session:
            sample = Sample(dataset_id=dataset_id, **sample_dict)
            session.add(sample)
            await self._commit_with_retry(session)
            _ = (sample.id, sample.dataset_id, sample.instruction, sample.response, sample.quality_score, sample.metadata_)
            return sample

    async def get_samples(self, dataset_id: str, limit: int = 1000, offset: int = 0) -> list[Sample]:
        """Get samples for a dataset."""
        async with self.session_maker() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Sample)
                .filter(Sample.dataset_id == dataset_id)
                .order_by(Sample.created_at, Sample.id)
                .offset(max(0, offset))
                .limit(limit)
            )
            samples = list(result.scalars().all())
            for s in samples:
                _ = (s.id, s.dataset_id, s.instruction, s.response, s.quality_score, s.metadata_)
            return samples

    async def create_source(self, url: str, source_type: str, title: str, metadata: dict, license: Optional[str] = None) -> Source:
        """Create a new source."""
        async with self.session_maker() as session:
            source = Source(
                url=url,
                source_type=source_type,
                title=title,
                metadata_=metadata,
                license=license
            )
            session.add(source)
            await self._commit_with_retry(session)
            _ = (source.id, source.url, source.source_type, source.title)
            return source

    async def create_source_snapshot(
        self, job_id: str, source: dict, content: str = "", content_type: Optional[str] = None,
    ) -> SourceSnapshot:
        """Persist a discovery/extraction capture without overwriting past evidence."""
        source_metadata = source.get("metadata") or {}
        url = str(source.get("url") or source_metadata.get("source_url") or "").strip()
        if not url:
            raise ValueError("source snapshot requires a URL")
        text = str(content or source.get("content") or "")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        async with self.session_maker() as session:
            source_row = Source(
                url=url,
                source_type=str(source.get("source_type") or "web"),
                title=str(source.get("title") or source_metadata.get("source_title") or ""),
                metadata_=source_metadata,
                license=source.get("license") or source_metadata.get("license"),
            )
            session.add(source_row)
            await session.flush()
            snapshot = SourceSnapshot(
                source_id=source_row.id, job_id=job_id, url=url, content_hash=digest,
                content_type=content_type or source.get("content_type"),
                license=source_row.license, content=text, metadata_=source_metadata,
            )
            session.add(snapshot)
            await self._commit_with_retry(session)
            _ = snapshot.id
            return snapshot

    async def create_evidence_chunks(self, snapshot_id: str, chunks: list[dict]) -> list[EvidenceChunk]:
        """Persist immutable, content-addressed chunks for a source capture."""
        async with self.session_maker() as session:
            records = []
            for index, chunk in enumerate(chunks):
                content = str(chunk.get("content") or "").strip()
                if not content:
                    continue
                record = EvidenceChunk(
                    snapshot_id=snapshot_id, chunk_index=int(chunk.get("chunk_index", index)),
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    content=content, metadata_=chunk.get("metadata") or {},
                )
                session.add(record)
                records.append(record)
            await self._commit_with_retry(session)
            return records

    async def create_workflow_schedule(
        self, name: str, workflow_type: str, interval_seconds: int, workflow_config: dict,
        next_run_at: Optional[datetime] = None,
    ) -> WorkflowSchedule:
        if interval_seconds < 60:
            raise ValueError("schedule interval must be at least 60 seconds")
        async with self.session_maker() as session:
            record = WorkflowSchedule(
                name=name, workflow_type=workflow_type, interval_seconds=interval_seconds,
                workflow_config=workflow_config, next_run_at=next_run_at or utc_now(),
            )
            session.add(record)
            await self._commit_with_retry(session)
            return record

    async def claim_due_workflow_schedules(self, limit: int = 20) -> list[WorkflowSchedule]:
        """Atomically claim due schedules by advancing their next occurrence."""
        from sqlalchemy import select
        now = utc_now()
        async with self.session_maker() as session:
            stmt = (
                select(WorkflowSchedule)
                .where(WorkflowSchedule.enabled == 1, WorkflowSchedule.next_run_at <= now)
                .order_by(WorkflowSchedule.next_run_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            records = list((await session.execute(stmt)).scalars().all())
            for record in records:
                record.last_run_at = now
                record.next_run_at = now + timedelta(seconds=record.interval_seconds)
            await self._commit_with_retry(session)
            return records

    async def create_workflow_schedule_run(self, schedule_id: str, job_id: Optional[str], detail: dict) -> WorkflowScheduleRun:
        async with self.session_maker() as session:
            record = WorkflowScheduleRun(schedule_id=schedule_id, job_id=job_id, detail=detail)
            session.add(record)
            await self._commit_with_retry(session)
            return record

    async def list_workflow_schedules(self, limit: int = 100) -> list[WorkflowSchedule]:
        from sqlalchemy import select
        async with self.session_maker() as session:
            return list((await session.execute(
                select(WorkflowSchedule).order_by(WorkflowSchedule.next_run_at).limit(limit)
            )).scalars().all())

    async def list_workflow_schedule_runs(self, schedule_id: str, limit: int = 100) -> list[WorkflowScheduleRun]:
        from sqlalchemy import select
        async with self.session_maker() as session:
            return list((await session.execute(
                select(WorkflowScheduleRun)
                .where(WorkflowScheduleRun.schedule_id == schedule_id)
                .order_by(WorkflowScheduleRun.started_at.desc()).limit(limit)
            )).scalars().all())

    async def finish_workflow_schedule_run(self, run_id: str, status: str, detail: Optional[dict] = None) -> None:
        async with self.session_maker() as session:
            record = await session.get(WorkflowScheduleRun, run_id)
            if record:
                record.status = status
                record.detail = detail or record.detail
                record.finished_at = utc_now()
                await self._commit_with_retry(session)

    # ── Fine-tune job helpers ─────────────────────────────────────────────

    async def create_finetune_job(self, data: dict) -> "FineTuneJob":
        """Persist a new FineTuneJob row."""
        from sqlalchemy import text as _text
        async with self.session_maker() as session:
            fj = FineTuneJob(**data)
            session.add(fj)
            await self._commit_with_retry(session)
            _ = fj.id
            return fj

    async def get_finetune_job(self, job_id: str) -> Optional["FineTuneJob"]:
        async with self.session_maker() as session:
            try:
                import uuid as _uuid
                clean_id = str(_uuid.UUID(str(job_id)))
                fj = await session.get(FineTuneJob, clean_id)
                if fj is not None:
                    return fj
            except Exception:
                pass
            try:
                from sqlalchemy import select, text
                stmt = select(FineTuneJob).where(
                    text("CAST(finetune_jobs.id AS TEXT) = :jid")
                ).params(jid=str(job_id))
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
            except Exception:
                return None

    async def update_finetune_job(self, job_id: str, **kwargs) -> None:
        async with self.session_maker() as session:
            fj = None
            try:
                import uuid as _uuid
                clean_id = str(_uuid.UUID(str(job_id)))
                fj = await session.get(FineTuneJob, clean_id)
            except Exception:
                pass
            if fj is None:
                try:
                    from sqlalchemy import select, text
                    stmt = select(FineTuneJob).where(
                        text("CAST(finetune_jobs.id AS TEXT) = :jid")
                    ).params(jid=str(job_id))
                    result = await session.execute(stmt)
                    fj = result.scalar_one_or_none()
                except Exception:
                    pass
            if fj:
                for k, v in kwargs.items():
                    if hasattr(fj, k):
                        setattr(fj, k, v)
                await self._commit_with_retry(session)

    async def list_finetune_jobs(self, limit: int = 100, owner: Optional[str] = None) -> list["FineTuneJob"]:
        from sqlalchemy import select
        async with self.session_maker() as session:
            stmt = select(FineTuneJob).order_by(FineTuneJob.created_at.desc())
            if owner is not None:
                stmt = stmt.where(FineTuneJob.owner == owner)
            result = await session.execute(stmt.limit(limit))
            jobs = list(result.scalars().all())
            for j in jobs:
                _ = j.id
            return jobs

    # ── Review queue helpers ──────────────────────────────────────────────

    async def create_review_item(self, data: dict) -> "ReviewQueueItem":
        async with self.session_maker() as session:
            item = ReviewQueueItem(**data)
            session.add(item)
            await self._commit_with_retry(session)
            _ = item.id
            return item

    async def get_review_item(self, item_id: str) -> Optional["ReviewQueueItem"]:
        async with self.session_maker() as session:
            return await session.get(ReviewQueueItem, item_id)

    async def get_review_item_for_job_sample(
        self, job_id: str, dataset_id: str
    ) -> Optional["ReviewQueueItem"]:
        """Find an existing review item for a deterministic job/sample key."""
        from sqlalchemy import select
        async with self.session_maker() as session:
            result = await session.execute(
                select(ReviewQueueItem)
                .where(ReviewQueueItem.job_id == job_id)
                .where(ReviewQueueItem.dataset_id == dataset_id)
                .order_by(ReviewQueueItem.created_at.asc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def update_review_item(self, item_id: str, **kwargs) -> Optional["ReviewQueueItem"]:
        async with self.session_maker() as session:
            item = await session.get(ReviewQueueItem, item_id)
            if item:
                for k, v in kwargs.items():
                    if hasattr(item, k):
                        setattr(item, k, v)
                await self._commit_with_retry(session)
            return item

    async def list_review_items(
        self,
        status: Optional[str] = None,
        job_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        owner: Optional[str] = None,
    ) -> tuple[list["ReviewQueueItem"], int]:
        """Return (items, total_count) with optional filters and pagination."""
        from sqlalchemy import select, func
        async with self.session_maker() as session:
            base_q = select(ReviewQueueItem)
            if status:
                base_q = base_q.where(ReviewQueueItem.review_status == status)
            if job_id:
                base_q = base_q.where(ReviewQueueItem.job_id == job_id)
            if owner is not None:
                base_q = base_q.where(ReviewQueueItem.owner == owner)

            count_result = await session.execute(
                select(func.count()).select_from(base_q.subquery())
            )
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            data_result = await session.execute(
                base_q.order_by(ReviewQueueItem.created_at.desc()).offset(offset).limit(page_size)
            )
            items = list(data_result.scalars().all())
            for i in items:
                _ = i.id
            return items, total

    async def review_stats(self) -> dict:
        from sqlalchemy import select, func
        async with self.session_maker() as session:
            result = await session.execute(
                select(ReviewQueueItem.review_status, func.count().label("cnt"))
                .group_by(ReviewQueueItem.review_status)
            )
            rows = result.all()
        counts: dict[str, int] = {r[0]: r[1] for r in rows}
        total = sum(counts.values())
        return {
            "total": total,
            "pending": counts.get("pending", 0),
            "in_review": counts.get("in_review", 0),
            "approved": counts.get("approved", 0),
            "rejected": counts.get("rejected", 0),
            "flagged": counts.get("flagged", 0),
            "approval_rate": round(counts.get("approved", 0) / max(total, 1) * 100, 1),
            "rejection_rate": round(counts.get("rejected", 0) / max(total, 1) * 100, 1),
        }

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job and all associated data."""
        if not _is_valid_uuid(job_id):
            return False
        async with self.session_maker() as session:
            job = await session.get(Job, job_id)
            if job:
                await session.delete(job)
                await self._commit_with_retry(session)
                return True
            return False

    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset and all associated samples and quality scores."""
        if not _is_valid_uuid(dataset_id):
            return False
        async with self.session_maker() as session:
            ds = await session.get(Dataset, dataset_id)
            if ds:
                await session.delete(ds)
                await self._commit_with_retry(session)
                return True
            return False


class AsyncDB:
    """High-level async database interface."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def close(self) -> None:
        """Close database connections gracefully."""
        import logging
        logger = logging.getLogger(__name__)
        try:
            await self.db.close()
            logger.info('AsyncDB connection closed')
        except Exception as e:
            logger.warning(f'Error closing AsyncDB: {e}')

    @classmethod
    async def create(cls, database_url: str) -> "AsyncDB":
        """Create AsyncDB instance with database initialization.

        Applies safe schema migrations via the Migration Safety system.
        """
        db_manager = DatabaseManager(database_url)
        await db_manager.create_tables()

        # Apply safe migrations
        try:
            from core.migration_safety import SafeMigrationManager, BUILTIN_MIGRATIONS

            migration_mgr = SafeMigrationManager(
                session_factory=db_manager.session_maker,
                db_manager=db_manager,
            )

            for migration_id, steps in BUILTIN_MIGRATIONS.items():
                result = await migration_mgr.apply_migration(migration_id, steps)
                if result.success:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info("Migration %s applied: %d steps", migration_id, result.steps_succeeded)
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        "Migration %s: %s (%d/%d steps)",
                        migration_id, result.error or "unknown",
                        result.steps_succeeded, result.steps_attempted,
                    )
        except ImportError:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Migration safety system not available — skipping safe migrations")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Safe migrations skipped: %s", e)

        return cls(db_manager)

    async def create_job(self, config: dict, owner: Optional[str] = None) -> dict:
        """Create a new job and return its ID."""
        job = await self.db.create_job(config, owner=owner)
        return {
            "id": getattr(job, "id", None) or config.get("id"),
            "status": getattr(job, "status", "pending"),
            "config": config,
            "progress": getattr(job, "progress", 0.0),
            "current_stage": getattr(job, "current_stage", "initializing"),
        }

    async def get_job_status(self, job_id: str) -> Optional[dict]:
        """Get job status and progress."""
        job = await self.db.get_job(job_id)
        if not job:
            return None
        q = getattr(job, "quality_score", None)
        root = getattr(job, "merkle_root", None)
        meta = {}
        if job.datasets:
            meta = job.datasets[0].metadata_ or {}
            if q is None:
                q = meta.get("quality_score") or (meta.get("quality_breakdown") or {}).get("composite")
            if not root:
                root = meta.get("merkle_root_hash")
        return {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "current_stage": job.current_stage,
            "samples_processed": job.samples_processed,
            "samples_generated": job.samples_generated,
            "sources_discovered": getattr(job, "sources_discovered", 0),
            "sources_extracted": getattr(job, "sources_extracted", 0),
            "samples_filtered": getattr(job, "samples_filtered", 0),
            "quality_score": q,
            "merkle_root": root,
            "metadata": meta,
            "cost_usd": job.cost_usd,
            "error": job.error,
            "owner": getattr(job, "owner", None),
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "config": job.config,
        }

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return await self.db.get_job(job_id)

    async def update_job(self, job_id: str, status_data: Optional[dict] = None, **kwargs):
        """Update job fields safely accepting either a dict or keyword arguments."""
        await self.db.update_job(job_id, status_data, **kwargs)

    async def list_jobs(self, status: Optional[str] = None, limit: int = 50, cursor: Optional[str] = None, owner: Optional[str] = None) -> list[dict]:
        """List all jobs with complete configuration and domain metadata."""
        jobs = await self.db.list_jobs(status=status, limit=limit, owner=owner)
        result = []
        for job in jobs:
            config = getattr(job, 'config', {}) or {}
            if isinstance(config, str):
                import json
                try:
                    config = json.loads(config)
                except Exception:
                    config = {}
            q = getattr(job, "quality_score", None)
            root = getattr(job, "merkle_root", None)
            meta = {}
            if job.datasets:
                meta = job.datasets[0].metadata_ or {}
                if q is None:
                    q = meta.get("quality_score") or (meta.get("quality_breakdown") or {}).get("composite")
                if not root:
                    root = meta.get("merkle_root_hash")
            job_dict = {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "cost_usd": job.cost_usd,
                "samples_generated": job.samples_generated,
                "current_stage": job.current_stage,
                "quality_score": q,
                "merkle_root": root,
                "metadata": meta,
                "created_at": job.created_at,
                "updated_at": getattr(job, 'updated_at', job.created_at),
                "owner": getattr(job, 'owner', None),
                "config": config,
                "target_domain": config.get('target_domain') or getattr(job, 'target_domain', 'Custom'),
                "dataset_type": config.get('dataset_type') or getattr(job, 'dataset_type', 'sft'),
                "dataset_size": config.get('dataset_size') or getattr(job, 'dataset_size', 100),
            }
            result.append(job_dict)
        return result

    async def create_tables(self):
        """Ensure all database tables exist."""
        await self.db.create_tables()

    async def clear_all_jobs(self):
        """Delete all jobs from database."""
        await self.db.clear_all_jobs()

    async def update_job_status(self, job_id: str, status_data: dict):
        """Update job status fields."""
        await self.db.update_job(job_id, status_data)

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return await self.db.get_job(job_id)

    async def create_dataset(self, job_id: str, name: str, type: str, size: int, metadata: dict, output_path: str, owner: Optional[str] = None) -> dict:
        """Create a new dataset and return its ID."""
        dataset = await self.db.create_dataset(job_id, name, type, size, metadata, output_path, owner=owner)
        return {"id": dataset.id, "job_id": dataset.job_id}

    async def create_dataset_version(self, **kwargs) -> dict:
        record = await self.db.create_dataset_version(**kwargs)
        return record.to_dict()

    async def get_dataset_version(self, version_id: str) -> Optional[dict]:
        record = await self.db.get_dataset_version(version_id)
        return record.to_dict() if record else None

    async def create_context_bundle(self, job_id: str, content_hash: str, evidence: list[dict]) -> dict:
        record = await self.db.create_context_bundle(job_id, content_hash, evidence)
        return record.to_dict()

    async def create_review_calibration_report(self, report: dict) -> dict:
        record = await self.db.create_review_calibration_report(report)
        return record.to_dict()

    async def create_source_snapshot(self, job_id: str, source: dict, content: str = "", content_type: Optional[str] = None) -> dict:
        record = await self.db.create_source_snapshot(job_id, source, content, content_type)
        return record.to_dict()

    async def create_evidence_chunks(self, snapshot_id: str, chunks: list[dict]) -> list[dict]:
        records = await self.db.create_evidence_chunks(snapshot_id, chunks)
        return [record.to_dict() for record in records]

    async def create_workflow_schedule(self, **kwargs) -> dict:
        record = await self.db.create_workflow_schedule(**kwargs)
        return record.to_dict()

    async def claim_due_workflow_schedules(self, limit: int = 20) -> list[dict]:
        records = await self.db.claim_due_workflow_schedules(limit)
        return [record.to_dict() for record in records]

    async def create_workflow_schedule_run(self, schedule_id: str, job_id: Optional[str], detail: dict) -> dict:
        record = await self.db.create_workflow_schedule_run(schedule_id, job_id, detail)
        return record.to_dict()

    async def finish_workflow_schedule_run(self, run_id: str, status: str, detail: Optional[dict] = None) -> None:
        await self.db.finish_workflow_schedule_run(run_id, status, detail)

    async def list_workflow_schedules(self, limit: int = 100) -> list[dict]:
        return [record.to_dict() for record in await self.db.list_workflow_schedules(limit)]

    async def list_workflow_schedule_runs(self, schedule_id: str, limit: int = 100) -> list[dict]:
        return [record.to_dict() for record in await self.db.list_workflow_schedule_runs(schedule_id, limit)]

    async def list_datasets(self, limit: int = 100, owner: Optional[str] = None) -> list[dict]:
        """List all datasets ordered by creation date."""
        datasets = await self.db.list_datasets(limit, owner=owner)
        return [
            {
                "id": ds.id,
                "job_id": ds.job_id,
                "name": ds.name,
                "type": ds.type,
                "size": ds.size,
                "owner": getattr(ds, "owner", None),
                "created_at": ds.created_at.isoformat() if ds.created_at else None,
                "metadata": ds.metadata_,
                "output_path": ds.output_path,
            }
            for ds in datasets
        ]

    async def get_dataset(self, dataset_id: str) -> Optional[dict]:
        """Get a dataset by ID."""
        ds = await self.db.get_dataset(dataset_id)
        if not ds:
            return None
        return {
            "id": ds.id,
            "job_id": ds.job_id,
            "name": ds.name,
            "type": ds.type,
            "size": ds.size,
            "owner": getattr(ds, "owner", None),
            "created_at": ds.created_at.isoformat() if ds.created_at else None,
            "metadata": ds.metadata_,
            "output_path": ds.output_path,
        }

    async def get_datasets_by_job(self, job_id: str) -> list[dict]:
        """Get all datasets for a specific job."""
        datasets = await self.db.get_datasets_by_job(job_id)
        return [
            {
                "id": ds.id,
                "job_id": ds.job_id,
                "name": ds.name,
                "type": ds.type,
                "size": ds.size,
                "owner": getattr(ds, "owner", None),
                "created_at": ds.created_at.isoformat() if ds.created_at else None,
                "metadata": ds.metadata_,
                "output_path": ds.output_path,
            }
            for ds in datasets
        ]

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job and its associated datasets/samples."""
        return await self.db.delete_job(job_id)

    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset and its associated samples."""
        return await self.db.delete_dataset(dataset_id)

    async def create_sample(self, dataset_id: str, data: dict) -> dict:
        """Create a new sample and return its ID."""
        sample = await self.db.create_sample(dataset_id, data)
        return {"id": sample.id, "dataset_id": sample.dataset_id}

    async def get_samples(self, dataset_id: str, limit: int = 1000, offset: int = 0) -> list[dict]:
        """Get samples for a dataset."""
        samples = await self.db.get_samples(dataset_id, limit, offset)
        return [
            {
                "id": sample.id,
                "dataset_id": sample.dataset_id,
                "instruction": sample.instruction,
                "response": sample.response,
                "input": sample.input,
                "metadata": sample.metadata_,
                "quality_score": sample.quality_score,
                "difficulty_tier": sample.difficulty_tier,
                "created_at": sample.created_at.isoformat() if sample.created_at else None
            }
            for sample in samples
        ]

    async def create_samples(self, dataset_id: str, samples_data: list[dict]) -> list[dict]:
        """Create multiple samples for a dataset."""
        samples = []
        async with self.db.session_maker() as session:
            for raw_sample_data in samples_data:
                sample_data = dict(raw_sample_data)
                if "metadata" in sample_data and "metadata_" not in sample_data:
                    sample_data["metadata_"] = sample_data.pop("metadata")
                if "id" not in sample_data:
                    sample_data["id"] = str(uuid.uuid4())
                sample = Sample(dataset_id=dataset_id, **sample_data)
                session.add(sample)
                samples.append(sample)
            await self.db._commit_with_retry(session)
            return [{"id": s.id, "dataset_id": s.dataset_id} for s in samples]
