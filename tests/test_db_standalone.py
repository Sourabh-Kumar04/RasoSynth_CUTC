#!/usr/bin/env python3
"""Standalone test for database functionality using SQLAlchemy directly."""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from typing import Optional, List

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text, ForeignKey, delete, select

# Define models
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

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, nullable=False, default="pending")
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


class Dataset(Base):
    """Dataset model for storing generated datasets."""
    __tablename__ = "datasets"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(PG_UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    type = Column(String)
    size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_ = Column("metadata", JSON)
    output_path = Column(String)


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


class DatabaseManager:
    """Database manager for async SQLAlchemy operations."""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
        self.session_maker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def create_tables(self):
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create_job(self, config: dict) -> dict:
        """Create a new job and return its data."""
        async with self.session_maker() as session:
            job_id = config.get("id")
            if job_id:
                job = Job(id=job_id, config=config, status=config.get("status", "pending"))
            else:
                job = Job(config=config)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return {"id": job.id, "status": job.status}

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Get a job by ID."""
        async with self.session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                return {
                    "id": job.id,
                    "status": job.status,
                    "progress": job.progress,
                    "current_stage": job.current_stage,
                    "samples_processed": job.samples_processed,
                    "samples_generated": job.samples_generated,
                    "cost_usd": job.cost_usd,
                    "error": job.error,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                    "config": job.config
                }
            return None

    async def update_job(self, job_id: str, **kwargs):
        """Update job fields."""
        async with self.session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                await session.commit()

    async def create_dataset(self, job_id: str, name: str, type: str, size: int, metadata: dict, output_path: str) -> dict:
        """Create a new dataset and return its data."""
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
            await session.commit()
            await session.refresh(dataset)
            return {"id": dataset.id, "job_id": dataset.job_id}

    async def create_sample(self, dataset_id: str, data: dict) -> dict:
        """Create a new sample and return its data."""
        async with self.session_maker() as session:
            sample = Sample(dataset_id=dataset_id, **data)
            session.add(sample)
            await session.commit()
            await session.refresh(sample)
            return {"id": sample.id, "dataset_id": sample.dataset_id}

    async def create_samples(self, dataset_id: str, samples_data: list[dict]) -> list[dict]:
        """Create multiple samples for a dataset."""
        samples = []
        async with self.session_maker() as session:
            for sample_data in samples_data:
                sample = Sample(dataset_id=dataset_id, **sample_data)
                session.add(sample)
                samples.append(sample)
            await session.commit()
            for sample in samples:
                await session.refresh(sample)
            return [{"id": s.id, "dataset_id": s.dataset_id} for s in samples]

    async def get_samples(self, dataset_id: str, limit: int = 1000) -> list[dict]:
        """Get samples for a dataset."""
        async with self.session_maker() as session:
            result = await session.execute(
                select(Sample)
                .filter(Sample.dataset_id == dataset_id)
                .limit(limit)
            )
            samples = result.scalars().all()
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


async def test_database():
    """Test database operations."""
    try:
        # Initialize database with SQLite URL
        db_manager = DatabaseManager("sqlite+aiosqlite:///./data/app.db")
        await db_manager.create_tables()
        print("Database initialized successfully")

        # Test creating a job
        job_result = await db_manager.create_job({
            "config": {"test": True},
            "status": "pending"
        })
        print(f"Created job: {job_result}")

        # Test getting job status
        job_status = await db_manager.get_job(job_result["id"])
        print(f"Job status: {job_status}")

        # Test updating job
        await db_manager.update_job(job_result["id"], status="running", progress=0.5)
        print("Updated job status")

        # Test getting updated job
        updated_status = await db_manager.get_job(job_result["id"])
        print(f"Updated job status: {updated_status}")

        # Test creating dataset
        dataset_result = await db_manager.create_dataset(
            job_id=job_result["id"],
            name="test_dataset",
            type="test",
            size=10,
            metadata={"test": True},
            output_path="/tmp/test_dataset.jsonl"
        )
        print(f"Created dataset: {dataset_result}")

        # Test creating sample
        sample_result = await db_manager.create_sample(
            dataset_id=dataset_result["id"],
            data={
                "instruction": "Test instruction",
                "response": "Test response",
                "input": "",
                "metadata": {},
                "quality_score": 0.8,
                "difficulty_tier": 3
            }
        )
        print(f"Created sample: {sample_result}")

        # Test creating multiple samples
        samples_data = [
            {
                "instruction": f"Test instruction {i}",
                "response": f"Test response {i}",
                "input": "",
                "metadata": {"index": i},
                "quality_score": 0.7 + (i * 0.05),
                "difficulty_tier": 2 + (i % 2)
            }
            for i in range(3)
        ]
        multi_samples = await db_manager.create_samples(dataset_result["id"], samples_data)
        print(f"Created {len(multi_samples)} additional samples")

        # Test getting samples
        samples = await db_manager.get_samples(dataset_result["id"], limit=5)
        print(f"Retrieved {len(samples)} samples:")
        for i, sample in enumerate(samples):
            print(f"  Sample {i}: {sample['instruction'][:30]}... (quality: {sample['quality_score']})")

        print("\nAll database tests passed!")
        return True

    except Exception as e:
        print(f"Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Change to the correct directory
    os.chdir("/mnt/d/00_Academics/RasoSynthTune Agent/ai-dataset-engineer")
    success = asyncio.run(test_database())
    sys.exit(0 if success else 1)