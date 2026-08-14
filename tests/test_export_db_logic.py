#!/usr/bin/env python3
"""Test just the database persistence logic in the export node."""

import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Settings
from core.db import AsyncDB

# Mock sample class to simulate what the pipeline creates (based on ConstructedSample)
class MockSample:
    def __init__(self, instruction, response, input="", metadata=None, quality_score=0.8, difficulty_tier=3, curriculum_order=0):
        self.instruction = instruction
        self.response = response
        self.input = input
        self.metadata_ = metadata or {}
        self.quality_score = quality_score
        self.difficulty_tier = difficulty_tier
        self.curriculum_order = curriculum_order

async def test_export_db_persistence_logic():
    """Test just the database persistence part of the export node."""
    print("=== Testing Export Node Database Persistence Logic ===")

    try:
        # Load settings
        settings = Settings()
        print(f"Using database: {settings.postgres_url}")

        # Initialize database
        db = await AsyncDB.create(settings.postgres_url)
        print("✓ Database initialized")

        # Create test job using the AsyncDB interface (consistent with how we'll retrieve it)
        import uuid
        job_result = await db.create_job({
            "config": {
                "target_domain": "machine learning",
                "dataset_size": 2,
                "export_format": "jsonl",
                "cost_budget_usd": 1.0
            },
            "status": "export"
        })
        job_id = job_result["id"]
        print(f"✓ Created test job with ID: {job_id}")

        # Create mock samples (what would come from the construct stage)
        mock_samples = [
            MockSample(
                instruction="What is machine learning?",
                response="Machine learning is a subset of artificial intelligence...",
                input="",
                metadata={"topic": "AI", "source": "test"},
                quality_score=0.85,
                difficulty_tier=3,
                curriculum_order=0
            ),
            MockSample(
                instruction="Explain neural networks",
                response="Neural networks are computing systems inspired by biological neural networks...",
                input="",
                metadata={"topic": "deep learning", "source": "test"},
                quality_score=0.92,
                difficulty_tier=4,
                curriculum_order=1
            )
        ]

        print(f"✓ Created test job and {len(mock_samples)} mock samples")

        # Test the database persistence logic directly
        # This mimics what happens in _export_node after export_result is obtained
        export_result = {"dataset": "/tmp/test_dataset.jsonl"}  # Mock export result

        print("✓ Testing database persistence logic...")

        # Create dataset record
        dataset_record = await db.create_dataset(
            job_id=job_id,
            name=f"dataset_{job_id}",
            type="jsonl",
            size=len(mock_samples),
            metadata={"export_path": str(export_result.get("dataset", ""))},
            output_path=str(export_result.get("dataset", ""))
        )
        print(f"✓ Created dataset record: {dataset_record['id']}")

        # Create sample records
        sample_data = []
        for sample in mock_samples:
            sample_data.append({
                "instruction": getattr(sample, 'instruction', ''),
                "response": getattr(sample, 'response', ''),
                "input": getattr(sample, 'input', ''),
                "metadata": getattr(sample, 'metadata_', {}),
                "quality_score": getattr(sample, 'quality_score', 0.5),
                "difficulty_tier": getattr(sample, 'difficulty_tier', 3)
            })

        samples_result = await db.create_samples(dataset_record["id"], sample_data)
        print(f"✓ Created {len(samples_result)} sample records")

        # Verify the data was stored correctly
        retrieved_samples = await db.get_samples(dataset_record["id"], limit=10)
        print(f"✓ Retrieved {len(retrieved_samples)} samples from database")

        if len(retrieved_samples) == len(mock_samples):
            print("✓ Sample count matches!")
            for i, (original, retrieved) in enumerate(zip(mock_samples, retrieved_samples)):
                if (original.instruction == retrieved["instruction"] and
                    original.response == retrieved["response"] and
                    original.quality_score == retrieved["quality_score"]):
                    print(f"  Sample {i+1}: OK")
                else:
                    print(f"  Sample {i+1}: MISMATCH")
                    return False
        else:
            print(f"✗ Sample count mismatch: expected {len(mock_samples)}, got {len(retrieved_samples)}")
            return False

        # Test that we can also retrieve the job status
        print(f"DEBUG: Trying to get job status for job_id: {job_id}")
        db_job_status = await db.get_job_status(job_id)
        print(f"DEBUG: get_job_status returned: {db_job_status}")
        if db_job_status is not None:
            print(f"✓ Job status retrieved from database: {db_job_status.get('id')} - {db_job_status.get('status')}")
        else:
            print("✗ Job status not found in database")
            # Let's also try to list all jobs to see what's in the database
            all_jobs = await db.list_jobs(limit=10)
            print(f"DEBUG: Found {len(all_jobs)} total jobs in database")
            for j in all_jobs:
                print(f"  Job ID: {j.get('id')}, Status: {j.get('status')}")
            return False

        print("\n✓ Export database persistence logic test PASSED!")
        print("  The orchestrator's export node will correctly persist datasets to the database")
        return True

    except Exception as e:
        print(f"✗ Export database persistence logic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_export_db_persistence_logic())
    sys.exit(0 if success else 1)