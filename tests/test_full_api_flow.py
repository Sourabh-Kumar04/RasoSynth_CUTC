#!/usr/bin/env python3
"""Full end-to-end flow: create job -> run export -> query API -> verify in DB."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Settings
from core.db import AsyncDB
from core.orchestrator_core import DatasetOrchestrator, Job, JobStatus


class MockSample:
    def __init__(self, instruction, response, input="", metadata=None,
                 quality_score=0.8, difficulty_tier=3):
        self.instruction = instruction
        self.response = response
        self.input = input
        self.metadata_ = metadata or {}
        self.quality_score = quality_score
        self.difficulty_tier = difficulty_tier


async def test_full_flow():
    print("=== Full End-to-End Flow Test ===")

    try:
        settings = Settings()
        db = await AsyncDB.create(settings.postgres_url)
        print("✓ Database initialized")

        # 1. Create a job in the database
        job_result = await db.create_job({
            "config": {
                "target_domain": "machine learning",
                "dataset_size": 2,
                "export_format": "jsonl",
                "cost_budget_usd": 1.0
            },
            "status": "running"
        })
        job_id = job_result["id"]
        print(f"✓ Created job: {job_id}")

        # 2. Simulate the pipeline creating mock samples
        mock_samples = [
            MockSample(
                instruction="What is machine learning?",
                response="ML is a subset of AI...",
                metadata={"topic": "AI"},
                quality_score=0.85,
                difficulty_tier=3,
            ),
            MockSample(
                instruction="Explain neural networks",
                response="NN are computing systems...",
                metadata={"topic": "deep learning"},
                quality_score=0.92,
                difficulty_tier=4,
            ),
        ]

        # 3. Simulate export node: call _export_node directly
        from unittest.mock import Mock, AsyncMock, patch

        mock_router = Mock()
        mock_router.initialize = AsyncMock(return_value={'initialized': [], 'failed': []})

        config = settings.model_dump()
        orchestrator = DatasetOrchestrator(config, mock_router, db=db)
        print("✓ Orchestrator initialized")

        # Register job in active_jobs (like the real pipeline does)
        from datetime import datetime
        orchestrator.active_jobs[job_id] = Job(
            id=job_id,
            status=JobStatus.RUNNING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            current_stage="export",
            progress=0.9,
            config={"target_domain": "machine learning"},
        )

        # Build state
        state = {
            "job": {
                "id": job_id,
                "status": "running",
                "config": {
                    "target_domain": "machine learning",
                    "dataset_size": 2,
                    "export_format": "jsonl",
                    "cost_budget_usd": 1.0
                },
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

        with patch('pipeline.export.ExportPipeline') as MockExport:
            mock_exporter_instance = Mock()
            mock_exporter_instance.export = AsyncMock(return_value={"dataset": "/tmp/test.jsonl"})
            MockExport.return_value = mock_exporter_instance

            result = await orchestrator._export_node(state)
            print("✓ Export node completed")

        # 4. Query the database via the "API" (AsyncDB methods)
        print("\n--- Verifying via API calls ---")

        # list_datasets
        datasets = await db.list_datasets(limit=10)
        print(f"✓ /datasets -> {len(datasets)} dataset(s)")

        if not datasets:
            print("✗ No datasets found")
            return False

        dataset = datasets[0]
        print(f"  - Name: {dataset['name']}")
        print(f"  - Type: {dataset['type']}")
        print(f"  - Size: {dataset['size']} samples")
        print(f"  - Job ID: {dataset['job_id']}")
        print(f"  - Output path: {dataset['output_path']}")

        # get_dataset
        ds_detail = await db.get_dataset(dataset["id"])
        print(f"\n✓ /datasets/{dataset['id']}:")
        print(f"  - Name: {ds_detail['name']}")
        print(f"  - Type: {ds_detail['type']}")
        print(f"  - Size: {ds_detail['size']}")

        # get_datasets_by_job
        job_datasets = await db.get_datasets_by_job(job_id)
        print(f"\n✓ /jobs/{job_id}/datasets: {len(job_datasets)} dataset(s)")

        # get_samples
        samples = await db.get_samples(dataset["id"], limit=10)
        print(f"\n✓ /datasets/{dataset['id']}/records: {len(samples)} sample(s)")
        for s in samples:
            print(f"  - {s['instruction'][:40]}... (quality: {s['quality_score']})")

        # get_job_status
        job = await db.get_job(job_id)
        if job:
            print(f"\n✓ /jobs/{job_id}:")
            print(f"  Status: {job.status}")
            print(f"  Current stage: {job.current_stage}")
            print(f"  Progress: {job.progress}")
            print(f"  Samples generated: {job.samples_generated}")

        print("\n✅ Full end-to-end flow: PASSED")
        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_full_flow())
    sys.exit(0 if success else 1)
