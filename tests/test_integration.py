#!/usr/bin/env python3
"""Integration test for the RasoDataset-Agent system."""

import asyncio
import os
import sys
import uuid
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Settings
from core.provider_router import ProviderRouter
from core.orchestrator_core import DatasetOrchestrator, JobStatus
from core.db import AsyncDB

async def test_integration():
    """Test the complete integration."""
    try:
        # Load settings
        settings = Settings()
        print(f"POSTGRES_URL: {settings.postgres_url}")
        print(f"Environment: {settings.environment}")

        # Initialize database
        db = await AsyncDB.create(settings.postgres_url)
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
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
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
        print(f"Found {len(jobs)} jobs in database")

        print("Integration test completed!")
        return True

    except Exception as e:
        print(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Change to the correct directory
    os.chdir("/mnt/d/00_Academics/RasoDataset-Agent Agent/ai-dataset-engineer")
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)