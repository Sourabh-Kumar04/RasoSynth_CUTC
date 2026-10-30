#!/usr/bin/env python3
"""Test the full export node flow: create job, run export, verify DB persistence."""

import asyncio
import os
import sys
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Settings
from core.db import AsyncDB, Dataset


class MockSample:
    """Mock sample to simulate pipeline output."""
    def __init__(self, instruction, response, input="", metadata=None,
                 quality_score=0.8, difficulty_tier=3, curriculum_order=0):
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


async def test_export_node_with_db():
    """Test full flow: DB job creation -> export node -> DB verification."""
    settings = Settings()
    print(f"Using database: {settings.postgres_url}")

    # Initialize database
    db_url = settings.postgres_url or "sqlite+aiosqlite:///:memory:"
    db = await AsyncDB.create(db_url)
    print("✓ Database initialized")

    # Create a test job in the database (this is what the API does)
    job_data = {
        "config": {
            "target_domain": "machine learning",
            "dataset_size": 2,
            "export_format": "jsonl",
            "cost_budget_usd": 1.0
        },
        "status": "pending"
    }
    job_result = await db.create_job(job_data)
    job_id = job_result["id"]
    print(f"✓ Created job in database: {job_id}")

    # Create mock samples
    mock_samples = [
        MockSample(
            instruction="What is machine learning?",
            response="Machine learning is a subset of artificial intelligence...",
            metadata={"topic": "AI", "source": "test"},
            quality_score=0.85,
            difficulty_tier=3,
        ),
        MockSample(
            instruction="Explain neural networks",
            response="Neural networks are computing systems inspired by biological neural networks...",
            metadata={"topic": "deep learning", "source": "test"},
            quality_score=0.92,
            difficulty_tier=4,
        ),
    ]

    from core.orchestrator_core import DatasetOrchestrator

    # Create mock router
    mock_router = Mock()
    mock_router.initialize = AsyncMock(
        return_value={'initialized': [], 'failed': []}
    )

    # Create orchestrator with DB
    config = settings.model_dump()
    orchestrator = DatasetOrchestrator(config, mock_router, db=db)
    print("✓ Orchestrator initialized with database")

    # Add the job to active_jobs so _update_job_status works
    from core.orchestrator_core import Job as OrchestratorJob, JobStatus
    orchestrator.active_jobs[job_id] = OrchestratorJob(
        id=job_id,
        status=JobStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        current_stage="export",
        progress=0.9,
        config=job_data["config"],
    )

    # Build state that _export_node expects
    state = {
        "job": {
            "id": job_id,
            "status": "running",
            "config": job_data["config"],
        },
        "constructed_samples": mock_samples,
        "messages": ["Ready for export"],
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
        "filtered_samples": [],
    }

    # Mock the ExportPipeline to avoid actual file I/O
    with patch('pipeline.export.ExportPipeline') as MockExport:
        mock_exporter_instance = Mock()
        mock_exporter_instance.export = AsyncMock(
            return_value={"dataset": "/tmp/test_dataset.jsonl"}
        )
        MockExport.return_value = mock_exporter_instance

        print("✓ Calling _export_node with mocked exporter...")
        result = await orchestrator._export_node(state)

    print("✓ Export node completed without errors")

    # Use a fresh SQLAlchemy query to find the dataset for this job
    from sqlalchemy import select
    async with db.db.session_maker() as session:
        result_query = await session.execute(
            select(Dataset).where(Dataset.job_id == job_id)
        )
        datasets = list(result_query.scalars().all())

    assert len(datasets) > 0, "No dataset found in database for this job"
    dataset = datasets[0]
    assert dataset.size == len(mock_samples)

    # Verify samples were created
    samples = await db.get_samples(dataset.id, limit=10)
    assert samples is not None
    assert len(samples) == len(mock_samples)

    # Verify job was updated in database
    job_record = await db.get_job(job_id)
    assert job_record is not None
    assert job_record.status == "running"  # _export_node is one pipeline stage; it does not mark the job completed

    # Negative assertion
    missing = await db.get_job("non-existent-uuid")
    assert missing is None


if __name__ == "__main__":
    success = asyncio.run(test_export_node_with_db())
    sys.exit(0 if success else 1)
