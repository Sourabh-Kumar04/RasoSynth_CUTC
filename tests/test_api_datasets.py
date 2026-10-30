#!/usr/bin/env python3
"""Test the new /datasets API endpoints."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Settings
from core.db import AsyncDB


async def test_api_datasets():
    """Test the datasets API endpoints."""
    print("=== Testing /datasets API Endpoints ===")

    settings = Settings()
    db_url = settings.postgres_url or "sqlite+aiosqlite:///:memory:"
    db = await AsyncDB.create(db_url)

    # Create a job
    job_result = await db.create_job({
        "config": {
            "target_domain": "machine learning",
            "dataset_size": 2,
            "export_format": "jsonl",
            "cost_budget_usd": 1.0
        },
        "status": "completed"
    })
    job_id = job_result["id"]
    assert job_id is not None

    # Create a dataset linked to the job
    dataset_result = await db.create_dataset(
        job_id=job_id,
        name="test_dataset_ml",
        type="jsonl",
        size=2,
        metadata={"test": True},
        output_path="/tmp/test.jsonl"
    )
    dataset_id = dataset_result["id"]
    assert dataset_id is not None

    # Create samples
    samples = await db.create_samples(dataset_id, [
        {
            "instruction": "Sample instruction 1",
            "response": "Sample response 1",
            "input": "",
            "metadata": {"key": "value"},
            "quality_score": 0.85,
            "difficulty_tier": 3
        },
        {
            "instruction": "Sample instruction 2",
            "response": "Sample response 2",
            "input": "",
            "metadata": {"key": "value2"},
            "quality_score": 0.92,
            "difficulty_tier": 4
        }
    ])
    assert len(samples) == 2

    # Test list_datasets
    datasets = await db.list_datasets(limit=10)
    assert len(datasets) >= 1
    found_ds = any(ds["id"] == dataset_id for ds in datasets)
    assert found_ds is True

    # Test get_dataset
    dataset = await db.get_dataset(dataset_id)
    assert dataset is not None
    assert dataset["name"] == "test_dataset_ml"
    assert dataset["job_id"] == job_id

    # Test get_datasets_by_job
    job_datasets = await db.get_datasets_by_job(job_id)
    assert len(job_datasets) == 1
    assert job_datasets[0]["id"] == dataset_id

    # Test get_samples
    retrieved_samples = await db.get_samples(dataset_id, limit=10)
    assert len(retrieved_samples) == 2
    assert retrieved_samples[0]["instruction"] == "Sample instruction 1"

    # Negative assertion
    non_existent = await db.get_dataset("invalid-dataset-id-uuid")
    assert non_existent is None


if __name__ == "__main__":
    success = asyncio.run(test_api_datasets())
    sys.exit(0 if success else 1)
