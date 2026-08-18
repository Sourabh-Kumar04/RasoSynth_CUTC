"""Database management with SQLAlchemy supporting both PostgreSQL and SQLite."""
import uuid
import os
from datetime import datetime
from typing import Optional
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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

    datasets = relationship("Dataset", back_populates="job", cascade="all, delete-orphan")


class Dataset(Base):
    """Dataset model for storing generated datasets."""
    __tablename__ = "datasets"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(PG_UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    name = Column(String, nullable=False)
    type = Column(String)
    size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column("metadata", JSON)
    output_path = Column(String)

    job = relationship("Job", back_populates="datasets")
    samples = relationship("Sample", back_populates="dataset", cascade="all, delete-orphan")


class Sample(Base):
    """Sample model for individual training samples."""
    __tablename__ = "samples"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(PG_UUID(as_uuid=False), ForeignKey("datasets.id", ondelete="CASCADE"))
    instruction = Column(Text)
    response = Column(Text)
    input = Column(Text)
    metadata_ = Column("metadata", JSON)
    quality_score = Column(Float)
    difficulty_tier = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

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
    discovered_at = Column(DateTime, default=datetime.utcnow)
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
    evaluated_at = Column(DateTime, default=datetime.utcnow)

    sample = relationship("Sample", back_populates="quality_scores")


class FineTuneJob(Base):
    """Fine-tuning job model — tracks PEFT/LoRA training runs."""
    __tablename__ = "finetune_jobs"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(PG_UUID(as_uuid=False), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True)
    # job metadata
    status = Column(String, nullable=False, default="pending", index=True)  # pending/running/completed/failed/cancelled
    base_model = Column(String, nullable=False)          # e.g. "unsloth/llama-3-8b"
    output_model_name = Column(String)                   # HF Hub repo or local path
    # config payload – lora_r, lora_alpha, epochs, batch_size, lr, push_to_hub, etc.
    config = Column(JSON, default=dict)
    # results
    progress = Column(Float, default=0.0)
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, default=1)
    train_loss = Column(Float)
    eval_loss = Column(Float)
    error = Column(Text)
    output_path = Column(String)                         # local checkpoint dir
    hf_repo_url = Column(String)                         # HF Hub URL if pushed
    # timing
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    # timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DatabaseManager:
    """Database manager for async SQLAlchemy operations."""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
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
            await conn.run_sync(Base.metadata.create_all)

            # ── Safe schema migration for existing deployments ─────────
            from sqlalchemy import text

            if "sqlite" in database_url:
                for col in ("sources_discovered", "sources_extracted", "samples_filtered"):
                    try:
                        await conn.execute(
                            text(f"ALTER TABLE jobs ADD COLUMN {col} INTEGER DEFAULT 0")
                        )
                    except Exception:
                        pass  # Column already exists
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

            # ── Performance indexes for scale ─────────────────────────
            indexes = [
                ("ix_jobs_status", "jobs", "status"),
                ("ix_jobs_created_at", "jobs", "created_at"),
                ("ix_datasets_job_id", "datasets", "job_id"),
                ("ix_datasets_created_at", "datasets", "created_at"),
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

    async def create_job(self, config: dict) -> Job:
        """Create a new job."""
        async with self.session_maker() as session:
            job_id = config.get("id")
            if job_id:
                job = Job(id=job_id, config=config, status=config.get("status", "pending"))
            else:
                job = Job(config=config, status=config.get("status", "pending"))
            session.add(job)
            await self._commit_with_retry(session)
            _ = (job.id, job.status, job.created_at, job.updated_at, job.config, job.progress, job.current_stage)
            return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        async with self.session_maker() as session:
            job = await session.get(Job, job_id)
            if job:
                _ = (job.id, job.status, job.created_at, job.updated_at, job.config, job.progress, job.current_stage)
            return job

    async def update_job(self, job_id: str, **kwargs):
        """Update job fields."""
        async with self.session_maker() as session:
            job = await session.get(Job, job_id)
            if job:
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                await self._commit_with_retry(session)

    async def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> list[Job]:
        """List jobs with optional status filter."""
        from sqlalchemy import select
        async with self.session_maker() as session:
            stmt = select(Job).order_by(Job.created_at.desc())
            if status:
                stmt = stmt.where(Job.status == status)
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

    async def create_dataset(self, job_id: str, name: str, type: str, size: int, metadata: dict, output_path: str) -> Dataset:
        """Create a new dataset."""
        async with self.session_maker() as session:
            dataset = Dataset(
                job_id=job_id,
                name=name,
                type=type,
                size=size,
                metadata=metadata,
                output_path=output_path
            )
            session.add(dataset)
            await self._commit_with_retry(session)
            _ = (dataset.id, dataset.job_id, dataset.name, dataset.type, dataset.size, dataset.created_at, dataset.output_path)
            return dataset

    async def list_datasets(self, limit: int = 100) -> list[Dataset]:
        """List all datasets ordered by creation date."""
        async with self.session_maker() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Dataset).order_by(Dataset.created_at.desc()).limit(limit)
            )
            datasets = list(result.scalars().all())
            for d in datasets:
                _ = (d.id, d.job_id, d.name, d.type, d.size, d.created_at, d.output_path)
            return datasets

    async def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get a dataset by ID."""
        async with self.session_maker() as session:
            dataset = await session.get(Dataset, dataset_id)
            if dataset:
                _ = (dataset.id, dataset.job_id, dataset.name, dataset.type, dataset.size, dataset.created_at, dataset.output_path)
            return dataset

    async def get_datasets_by_job(self, job_id: str) -> list[Dataset]:
        """Get all datasets for a specific job."""
        async with self.session_maker() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Dataset).filter(Dataset.job_id == job_id)
            )
            datasets = list(result.scalars().all())
            for d in datasets:
                _ = (d.id, d.job_id, d.name, d.type, d.size, d.created_at, d.output_path)
            return datasets

    async def create_sample(self, dataset_id: str, data: dict) -> Sample:
        """Create a new sample."""
        async with self.session_maker() as session:
            sample = Sample(dataset_id=dataset_id, **data)
            session.add(sample)
            await self._commit_with_retry(session)
            _ = (sample.id, sample.dataset_id, sample.instruction, sample.response, sample.quality_score)
            return sample

    async def get_samples(self, dataset_id: str, limit: int = 1000) -> list[Sample]:
        """Get samples for a dataset."""
        async with self.session_maker() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Sample)
                .filter(Sample.dataset_id == dataset_id)
                .limit(limit)
            )
            samples = list(result.scalars().all())
            for s in samples:
                _ = (s.id, s.dataset_id, s.instruction, s.response, s.quality_score)
            return samples

    async def create_source(self, url: str, source_type: str, title: str, metadata: dict, license: Optional[str] = None) -> Source:
        """Create a new source."""
        async with self.session_maker() as session:
            source = Source(
                url=url,
                source_type=source_type,
                title=title,
                metadata=metadata,
                license=license
            )
            session.add(source)
            await self._commit_with_retry(session)
            _ = (source.id, source.url, source.source_type, source.title)
            return source

    # ── Fine-tune job helpers ─────────────────────────────────────────────

    async def create_finetune_job(self, data: dict) -> "FineTuneJob":
        """Persist a new FineTuneJob row."""
        from sqlalchemy import text as _text  # noqa – already imported above but safe
        async with self.session_maker() as session:
            fj = FineTuneJob(**data)
            session.add(fj)
            await self._commit_with_retry(session)
            _ = fj.id
            return fj

    async def get_finetune_job(self, job_id: str) -> Optional["FineTuneJob"]:
        async with self.session_maker() as session:
            return await session.get(FineTuneJob, job_id)

    async def update_finetune_job(self, job_id: str, **kwargs) -> None:
        async with self.session_maker() as session:
            fj = await session.get(FineTuneJob, job_id)
            if fj:
                for k, v in kwargs.items():
                    if hasattr(fj, k):
                        setattr(fj, k, v)
                await self._commit_with_retry(session)

    async def list_finetune_jobs(self, limit: int = 100) -> list["FineTuneJob"]:
        from sqlalchemy import select
        async with self.session_maker() as session:
            result = await session.execute(
                select(FineTuneJob).order_by(FineTuneJob.created_at.desc()).limit(limit)
            )
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
    ) -> tuple[list["ReviewQueueItem"], int]:
        """Return (items, total_count) with optional filters and pagination."""
        from sqlalchemy import select, func
        async with self.session_maker() as session:
            base_q = select(ReviewQueueItem)
            if status:
                base_q = base_q.where(ReviewQueueItem.review_status == status)
            if job_id:
                base_q = base_q.where(ReviewQueueItem.job_id == job_id)

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
        async with self.session_maker() as session:
            job = await session.get(Job, job_id)
            if job:
                await session.delete(job)
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
            from db.migration_safety import SafeMigrationManager, BUILTIN_MIGRATIONS

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

    async def create_job(self, config: dict) -> dict:
        """Create a new job and return its ID."""
        job = await self.db.create_job(config)
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
            "cost_usd": job.cost_usd,
            "error": job.error,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "config": job.config,
        }

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return await self.db.get_job(job_id)

    async def update_job(self, job_id: str, **kwargs):
        """Update job fields."""
        await self.db.update_job(job_id, **kwargs)

    async def list_jobs(self, status: Optional[str] = None, limit: int = 50, cursor: Optional[str] = None) -> list[dict]:
        """List all jobs with complete configuration and domain metadata."""
        jobs = await self.db.list_jobs(status=status, limit=limit)
        result = []
        for job in jobs:
            config = getattr(job, 'config', {}) or {}
            if isinstance(config, str):
                import json
                try:
                    config = json.loads(config)
                except Exception:
                    config = {}
            job_dict = {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "cost_usd": job.cost_usd,
                "samples_generated": job.samples_generated,
                "current_stage": job.current_stage,
                "created_at": job.created_at,
                "updated_at": getattr(job, 'updated_at', job.created_at),
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

    async def create_dataset(self, job_id: str, name: str, type: str, size: int, metadata: dict, output_path: str) -> dict:
        """Create a new dataset and return its ID."""
        dataset = await self.db.create_dataset(job_id, name, type, size, metadata, output_path)
        return {"id": dataset.id, "job_id": dataset.job_id}

    async def list_datasets(self, limit: int = 100) -> list[dict]:
        """List all datasets ordered by creation date."""
        datasets = await self.db.list_datasets(limit)
        return [
            {
                "id": ds.id,
                "job_id": ds.job_id,
                "name": ds.name,
                "type": ds.type,
                "size": ds.size,
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
                "created_at": ds.created_at.isoformat() if ds.created_at else None,
                "metadata": ds.metadata_,
                "output_path": ds.output_path,
            }
            for ds in datasets
        ]

    async def create_sample(self, dataset_id: str, data: dict) -> dict:
        """Create a new sample and return its ID."""
        sample = await self.db.create_sample(dataset_id, data)
        return {"id": sample.id, "dataset_id": sample.dataset_id}

    async def get_samples(self, dataset_id: str, limit: int = 1000) -> list[dict]:
        """Get samples for a dataset."""
        samples = await self.db.get_samples(dataset_id, limit)
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
            for sample_data in samples_data:
                sample = Sample(dataset_id=dataset_id, **sample_data)
                session.add(sample)
                samples.append(sample)
            await self.db._commit_with_retry(session)
            for sample in samples:
                await session.refresh(sample)
            return [{"id": s.id, "dataset_id": s.dataset_id} for s in samples]