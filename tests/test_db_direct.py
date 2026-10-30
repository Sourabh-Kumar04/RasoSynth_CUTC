#!/usr/bin/env python3
"""Test script to verify database operations by directly importing db module."""

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import db module directly to avoid triggering orchestrator imports via core.__init__
from core.db import AsyncDB

import pytest
from core.db import AsyncDB

@pytest.mark.asyncio
async def test_database_direct(tmp_path):
    db_file = tmp_path / "test_app_direct.db"
    db = await AsyncDB.create(f"sqlite+aiosqlite:///{db_file}")
    assert db is not None

    # Test creating a job
    job_result = await db.create_job({
        "config": {"test": True},
        "status": "pending"
    })
    assert job_result is not None and "id" in job_result
    job_id = job_result["id"]

    # Test getting job status
    job_status = await db.get_job_status(job_id)
    assert job_status is not None
    assert job_status["status"] == "pending"

    # Test updating job
    await db.update_job(job_id, status="running", progress=0.5)

    # Test getting updated job
    updated_status = await db.get_job_status(job_id)
    assert updated_status["status"] == "running"
    assert updated_status["progress"] == 0.5

    # Test creating dataset
    dataset_result = await db.create_dataset(
        job_id=job_id,
        name="test_dataset",
        type="test",
        size=10,
        metadata={"test": True},
        output_path=str(tmp_path / "test_dataset.jsonl")
    )
    assert dataset_result is not None and "id" in dataset_result
    dataset_id = dataset_result["id"]

    # Test creating sample
    sample_result = await db.create_sample(
        dataset_id=dataset_id,
        data={
            "instruction": "Test instruction",
            "response": "Test response",
            "input": "",
            "metadata": {},
            "quality_score": 0.8,
            "difficulty_tier": 3
        }
    )
    assert sample_result is not None and "id" in sample_result

    # Test getting samples
    samples = await db.get_samples(dataset_id, limit=5)
    assert len(samples) == 1
    assert samples[0]["instruction"] == "Test instruction"
    assert samples[0]["quality_score"] == 0.8

    # Negative check
    missing = await db.get_job_status("non-existent-id")
    assert missing is None