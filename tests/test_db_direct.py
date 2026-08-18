#!/usr/bin/env python3
"""Test script to verify database operations by directly importing db module."""

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import db module directly to avoid triggering orchestrator imports via core.__init__
from core.db import AsyncDB

async def test_database():
    try:
        # Initialize database with SQLite URL from .env
        db = await AsyncDB.create("sqlite+aiosqlite:///./data/app.db")
        print("Database initialized successfully")

        # Test creating a job
        job_result = await db.create_job({
            "config": {"test": True},
            "status": "pending"
        })
        print(f"Created job: {job_result}")

        # Test getting job status
        job_status = await db.get_job_status(job_result["id"])
        print(f"Job status: {job_status}")

        # Test updating job
        await db.update_job(job_result["id"], status="running", progress=0.5)
        print("Updated job status")

        # Test getting updated job
        updated_status = await db.get_job_status(job_result["id"])
        print(f"Updated job status: {updated_status}")

        # Test creating dataset
        dataset_result = await db.create_dataset(
            job_id=job_result["id"],
            name="test_dataset",
            type="test",
            size=10,
            metadata={"test": True},
            output_path="/tmp/test_dataset.jsonl"
        )
        print(f"Created dataset: {dataset_result}")

        # Test creating sample
        sample_result = await db.create_sample(
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

        # Test getting samples
        samples = await db.get_samples(dataset_result["id"], limit=5)
        print(f"Retrieved {len(samples)} samples")

        print("All database tests passed!")
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