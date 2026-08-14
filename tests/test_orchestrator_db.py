#!/usr/bin/env python3
"""Test orchestrator with database persistence."""

import asyncio
import os
import sys
import uuid
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import core modules directly to avoid chain imports
from core.config import Settings
from core.provider_router import ProviderRouter
from core.db import AsyncDB

async def test_orchestrator_with_db():
    """Test orchestrator initialization with database."""
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

        # Test creating a job through database
        job_result = await db.create_job({
            "config": {"test": True, "target_domain": "machine learning"},
            "status": "pending"
        })
        print(f"Created job via DB: {job_result}")

        # Test getting job status
        job_status = await db.get_job_status(job_result["id"])
        print(f"Job status from DB: {job_status}")

        # Test creating dataset
        dataset_result = await db.create_dataset(
            job_id=job_result["id"],
            name="test_ml_dataset",
            type="jsonl",
            size=5,
            metadata={"source": "test"},
            output_path="/tmp/test_dataset.jsonl"
        )
        print(f"Created dataset via DB: {dataset_result}")

        # Test creating samples
        samples_data = [
            {
                "instruction": "What is machine learning?",
                "response": "Machine learning is a subset of AI...",
                "input": "",
                "metadata": {"topic": "AI"},
                "quality_score": 0.8,
                "difficulty_tier": 3
            },
            {
                "instruction": "Explain neural networks",
                "response": "Neural networks are computing systems...",
                "input": "",
                "metadata": {"topic": "deep learning"},
                "quality_score": 0.9,
                "difficulty_tier": 4
            }
        ]

        samples_result = await db.create_samples(dataset_result["id"], samples_data)
        print(f"Created {len(samples_result)} samples via DB")

        # Test getting samples
        samples = await db.get_samples(dataset_result["id"], limit=10)
        print(f"Retrieved {len(samples)} samples from DB:")
        for sample in samples:
            print(f"  - {sample['instruction'][:50]}... (score: {sample['quality_score']})")

        print("\nOrchestrator-DB integration test passed!")
        return True

    except Exception as e:
        print(f"Orchestrator-DB integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Change to the correct directory
    os.chdir("/mnt/d/00_Academics/RasoDataset-Agent Agent/ai-dataset-engineer")
    success = asyncio.run(test_orchestrator_with_db())
    sys.exit(0 if success else 1)