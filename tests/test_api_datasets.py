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

    try:
        settings = Settings()
        print(f"Using database: {settings.postgres_url}")

        db = await AsyncDB.create(settings.postgres_url)
        print("✓ Database initialized")

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
        print(f"✓ Created job: {job_id}")

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
        print(f"✓ Created dataset: {dataset_id}")

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
        print(f"✓ Created {len(samples)} samples")

        # Test list_datasets
        datasets = await db.list_datasets(limit=10)
        print(f"✓ list_datasets returned {len(datasets)} dataset(s)")
        for ds in datasets:
            print(f"  - {ds['name']} ({ds['type']}, {ds['size']} samples)")

        # Test get_dataset
        dataset = await db.get_dataset(dataset_id)
        if dataset:
            print(f"✓ get_dataset returned: {dataset['name']}")
        else:
            print("✗ get_dataset returned None")
            return False

        # Test get_datasets_by_job
        job_datasets = await db.get_datasets_by_job(job_id)
        print(f"✓ get_datasets_by_job returned {len(job_datasets)} dataset(s)")

        # Test get_samples
        retrieved_samples = await db.get_samples(dataset_id, limit=10)
        print(f"✓ get_samples returned {len(retrieved_samples)} sample(s)")
        for s in retrieved_samples:
            print(f"  - {s['instruction']} (quality: {s['quality_score']})")

        print("\n✅ All /datasets API tests PASSED")
        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_api_datasets())
    sys.exit(0 if success else 1)
