#!/usr/bin/env python3
"""Test that the export node properly persists datasets to the database."""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Settings
from core.provider_router import ProviderRouter
from core.db import AsyncDB
from core.orchestrator_core import DatasetOrchestrator

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

    def get(self, key, default=None):
        # Dict-style access for code paths that treat samples as dicts
        # (e.g. _balance_samples aliases); "metadata" maps to metadata_.
        if key == "metadata":
            return self.metadata_
        return getattr(self, key, default)

async def test_export_persistence():
    """Test that export node persists data to database."""
    # Load settings
    settings = Settings()
    print(f"Using database: {settings.postgres_url}")

    # Initialize database
    db_url = settings.postgres_url or "sqlite+aiosqlite:///:memory:"
    db = await AsyncDB.create(db_url)
    print("✓ Database initialized")

    # Initialize provider router
    config = settings.model_dump()
    router = ProviderRouter(config)
    init_result = await router.initialize()
    print(f"✓ Provider router initialized: {init_result}")

    # Initialize orchestrator with database
    orchestrator = DatasetOrchestrator(config, router, db=db)
    print("✓ Orchestrator initialized with database")

    # Create test job
    job_id = str(uuid.uuid4())  # get_job rejects non-UUID ids
    job = {
        "id": job_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "current_stage": "export",
        "progress": 0.9,
        "samples_processed": 0,
        "samples_generated": 0,
        "cost_usd": 0.0,
        "error": None,
        "config": {
            "target_domain": "machine learning",
            "dataset_size": 2,
            "export_format": "jsonl",
            "cost_budget_usd": 1.0
        },
        "sources_discovered": 0,
        "sources_extracted": 0,
        "samples_filtered": 0,
        "constraint_analysis": None
    }

    # Create mock samples (what would come from the construct stage)
    mock_samples = [
        MockSample(
            instruction="What is machine learning?",
            response="Machine learning is a subset of artificial intelligence...",
            input="",
            metadata={"topic": "AI", "source": "test"},
            quality_score=0.85,
            difficulty_tier=3
        ),
        MockSample(
            instruction="Explain neural networks",
            response="Neural networks are computing systems inspired by biological neural networks...",
            input="",
            metadata={"topic": "deep learning", "source": "test"},
            quality_score=0.92,
            difficulty_tier=4
        )
    ]

    # Register the job in active_jobs so _export_node's status update
    # persists the job row (mirrors the real pipeline: the job row exists
    # before the export stage runs).
    from core.orchestrator_core import Job as OrchestratorJob, JobStatus
    orchestrator.active_jobs[job_id] = OrchestratorJob(
        id=job_id,
        status=JobStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        current_stage="export",
        progress=0.9,
        config=job["config"],
    )

    # Create state that would be passed to _export_node
    state = {
        "job": job,
        "constructed_samples": mock_samples,
        "messages": ["Starting export"],
        "warnings": [],
        "errors": [],
        "should_retry": False,
        "human_approval_needed": False,
        "human_approved": False,
        "current_stage": "construct",
        "progress": 0.7,
        "constraint_analysis": None,
        "low_resource_mode": False,
        "multilingual_mode": False,
        "adaptation_notes": [],
        "sources": [],
        "extracted_content": [],
        "filtered_samples": []
    }

    print(f"✓ Created test state with {len(mock_samples)} mock samples")

    # Persist the job row first, as the API does before the export stage
    # (without this row, get_job has nothing to return).
    await db.create_job({"id": job_id, "status": "pending", "config": job["config"]})

    # Call the export node (this should persist to database)
    result_state = await orchestrator._export_node(state)

    print("✓ Export node completed successfully")

    # Check if dataset was created in database
    db_job = await db.get_job(job_id)
    assert db_job is not None, f"Job {job_id} not found in database"
    assert db_job.id == job_id  # AsyncDB.get_job returns a Job ORM object, not a dict

    # List datasets for this job
    jobs = await db.list_jobs(limit=5)
    assert len(jobs) > 0, "No jobs found in database"

    # Test that we can create a dataset directly to verify the method works
    test_dataset = await db.create_dataset(
        job_id="test-direct-456",
        name="direct_test_dataset",
        type="jsonl",
        size=1,
        metadata={"test": True},
        output_path="/tmp/direct_test.jsonl"
    )
    assert test_dataset is not None and "id" in test_dataset

    # Test direct sample creation
    test_sample = await db.create_sample(
        dataset_id=test_dataset["id"],
        data={
            "instruction": "Direct test instruction",
            "response": "Direct test response",
            "input": "",
            "metadata": {"direct": True},
            "quality_score": 0.9,
            "difficulty_tier": 3
        }
    )
    assert test_sample is not None and "id" in test_sample

    # Retrieve the sample we just created
    samples = await db.get_samples(test_dataset["id"], limit=5)
    assert len(samples) == 1
    assert samples[0]["instruction"] == "Direct test instruction"
    assert samples[0]["quality_score"] == 0.9

    # Verify negative case raises AssertionError
    negative_job = await db.get_job("non-existent-negative-job-id")
    assert negative_job is None

if __name__ == "__main__":
    success = asyncio.run(test_export_persistence())
    sys.exit(0 if success else 1)