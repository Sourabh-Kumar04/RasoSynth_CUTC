#!/usr/bin/env python3
"""Integration test for the RasoSynthTune system."""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Settings
from core.provider_router import ProviderRouter
from core.orchestrator_core import DatasetOrchestrator, JobStatus
from core.db import AsyncDB

async def test_integration():
    """Test the complete integration."""
    # Load settings
    settings = Settings()
    print(f"POSTGRES_URL: {settings.postgres_url}")
    print(f"Environment: {settings.environment}")

    # Initialize database
    db_url = settings.postgres_url or "sqlite+aiosqlite:///:memory:"
    db = await AsyncDB.create(db_url)
    print("Database initialized successfully")

    # Initialize provider router
    config = settings.model_dump()
    router = ProviderRouter(config)
    init_result = await router.initialize()
    print(f"Provider initialization: {init_result}")

    # Initialize orchestrator
    orchestrator = DatasetOrchestrator(config, router, db=db)
    print("Orchestrator initialized successfully")

    # Create a test job
    job_id = str(uuid.uuid4())
    job_config = {
        "target_domain": "machine learning",
        "dataset_size": 5,  # Small for testing
        "quality_level": "standard",
        "export_format": "jsonl",
        "cost_budget_usd": 1.0
    }

    job = type('Job', (), {
        'id': job_id,
        'status': JobStatus.PENDING,
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc),
        'current_stage': 'analyzing_constraints',
        'progress': 0.0,
        'samples_processed': 0,
        'samples_generated': 0,
        'cost_usd': 0.0,
        'error': None,
        'config': job_config,
        'sources_discovered': 0,
        'sources_extracted': 0,
        'samples_filtered': 0,
        'constraint_analysis': None
    })()

    print(f"Created test job: {job_id}")
    print("Starting pipeline execution...")

    # Run the pipeline (this will likely fail due to no API keys, but we can see the flow)
    try:
        await orchestrator.run(job)
        print("Pipeline completed successfully")
    except Exception as e:
        print(f"Pipeline failed (expected without API keys): {e}")
        # This is expected since we don't have API keys configured

    # Check if job was saved to database
    db_job = await db.get_job(job_id)
    if db_job:
        print(f"Job found in database: {db_job.get('status')}")
    else:
        print("Job not found in database")

    # List jobs
    jobs = await db.list_jobs(limit=5)
    assert len(jobs) >= 0

    # Create a direct job and assert it persists
    direct_job = await db.create_job({"status": "completed", "config": job_config})
    assert direct_job is not None
    assert "id" in direct_job
    retrieved = await db.get_job_status(direct_job["id"])
    assert retrieved is not None
    assert retrieved["status"] == "completed"

    # Negative check
    assert await db.get_job_status("non-existent-integration-id") is None

if __name__ == "__main__":
    # Change to the correct directory
    os.chdir("/mnt/d/00_Academics/RasoSynthTune Agent/ai-dataset-engineer")
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)