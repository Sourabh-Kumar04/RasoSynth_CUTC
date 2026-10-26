#!/usr/bin/env python3
"""Test the download endpoint's DB fallback when the file doesn't exist on disk."""

import asyncio
import os
import sys
import io
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Settings
from core.db import AsyncDB
from core.orchestrator_core import DatasetOrchestrator, Job, JobStatus
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone


class MockSample:
    def __init__(self, instruction, response, input="", metadata=None,
                 quality_score=0.8, difficulty_tier=3):
        self.instruction = instruction
        self.response = response
        self.input = input
        self.metadata_ = metadata or {}
        self.quality_score = quality_score
        self.difficulty_tier = difficulty_tier


async def test_download_from_db():
    print("=== Testing Download from Database Fallback ===")

    try:
        settings = Settings()
        db = await AsyncDB.create(settings.postgres_url)
        print("✓ Database initialized")

        # Create test job and dataset without creating a file
        job_result = await db.create_job({
            "config": {"target_domain": "ml", "dataset_size": 2},
            "status": "completed"
        })
        job_id = job_result["id"]
        print(f"✓ Created job: {job_id}")

        # Create dataset and samples in DB only (no file on disk)
        ds = await db.create_dataset(
            job_id=job_id,
            name="test_db_only",
            type="jsonl",
            size=3,
            metadata={"test": True},
            output_path="/nonexistent_path.jsonl"
        )
        ds_id = ds["id"]
        print(f"✓ Created dataset in DB: {ds_id}")

        await db.create_samples(ds_id, [
            {"instruction": "Q1", "response": "A1", "input": "", "metadata": {}, "quality_score": 0.9, "difficulty_tier": 3},
            {"instruction": "Q2", "response": "A2", "input": "", "metadata": {}, "quality_score": 0.8, "difficulty_tier": 2},
            {"instruction": "Q3", "response": "A3", "input": "", "metadata": {}, "quality_score": 0.7, "difficulty_tier": 1},
        ])
        print("✓ Created 3 samples in DB")

        # Simulate the export node creating the dataset record
        mock_router = Mock()
        mock_router.initialize = AsyncMock(return_value={"initialized": [], "failed": []})
        orchestrator = DatasetOrchestrator(settings.model_dump(), mock_router, db=db)

        # Trigger export node
        state = {
            "job": {"id": job_id, "status": "completed", "config": {"target_domain": "ml"}},
            "constructed_samples": [
                MockSample("Q1", "A1", quality_score=0.9, difficulty_tier=3),
                MockSample("Q2", "A2", quality_score=0.8, difficulty_tier=2),
                MockSample("Q3", "A3", quality_score=0.7, difficulty_tier=1),
            ],
            "messages": [], "warnings": [], "errors": [],
            "should_retry": False, "human_approval_needed": False,
            "human_approved": False, "current_stage": "construct",
            "progress": 0.7, "constraint_analysis": None,
            "low_resource_mode": False, "multilingual_mode": False,
            "adaptation_notes": [], "sources": [], "extracted_content": [],
            "filtered_samples": [],
        }

        orchestrator.active_jobs[job_id] = Job(
            id=job_id, status=JobStatus.RUNNING,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
            current_stage="export", progress=0.9, config={},
        )

        with patch("pipeline.export.ExportPipeline") as MockExport:
            mock_exporter = Mock()
            mock_exporter.export = AsyncMock(return_value={"dataset": "/nonexistent.jsonl"})
            MockExport.return_value = mock_exporter
            result = await orchestrator._export_node(state)

        print("✓ Export node completed (DB only, no file on disk)")

        # Now simulate what the download endpoint does
        # The key test: when file doesn't exist, the endpoint generates from DB
        datasets = await db.get_datasets_by_job(job_id)
        assert len(datasets) > 0, "No datasets found for the job"
        print(f"✓ Found {len(datasets)} dataset(s) linked to job")

        # Generate the download content from DB (simulating the endpoint logic)
        buffer = io.StringIO()
        for ds in datasets:
            samples = await db.get_samples(ds["id"], limit=100000)
            for sample in samples:
                record = {
                    "instruction": sample.get("instruction", ""),
                    "response": sample.get("response", ""),
                    "input": sample.get("input", ""),
                    "metadata": sample.get("metadata", {}),
                    "quality_score": sample.get("quality_score"),
                    "difficulty_tier": sample.get("difficulty_tier"),
                }
                buffer.write(json.dumps(record, ensure_ascii=False) + "\n")

        content = buffer.getvalue()
        lines = [line for line in content.strip().split("\n") if line]
        print(f"✓ Generated {len(lines)} lines from database records")

        # Parse each line as JSON
        records = [json.loads(line) for line in lines]
        assert len(records) >= 3, f"Expected at least 3 records, got {len(records)}"
        print(f"✓ Successfully parsed {len(records)} records")

        for i, r in enumerate(records[:3]):
            print(f"  Record {i}: {r['instruction'][:30]}... (quality: {r['quality_score']})")

        print("\n✅ Download from database fallback: PASSED")

        # Test multi-format generation: CSV, XML, JSON
        print("\n=== Testing Multi-Format Dynamic Generation (CSV, XML, JSON) ===")
        # CSV check
        csv_buffer = io.StringIO()
        import csv
        writer = csv.writer(csv_buffer)
        writer.writerow(["instruction", "input", "response", "quality_score", "difficulty_tier"])
        for s in samples:
            writer.writerow([s.get("instruction", ""), s.get("input", ""), s.get("response", ""), s.get("quality_score", ""), s.get("difficulty_tier", "")])
        csv_content = csv_buffer.getvalue()
        assert "instruction,input,response" in csv_content
        print("✓ Generated valid CSV format from database records")

        # XML check
        import xml.sax.saxutils as xml_escape
        xml_buffer = io.StringIO()
        xml_buffer.write('<?xml version="1.0" encoding="UTF-8"?>\n<dataset>\n')
        for s in samples:
            inst = xml_escape.escape(str(s.get("instruction", "")))
            resp = xml_escape.escape(str(s.get("response", "")))
            xml_buffer.write(f'  <sample>\n    <instruction>{inst}</instruction>\n    <response>{resp}</response>\n  </sample>\n')
        xml_buffer.write('</dataset>\n')
        xml_content = xml_buffer.getvalue()
        assert "<dataset>" in xml_content and "<sample>" in xml_content
        print("✓ Generated valid XML format from database records")

        # JSON array check
        json_arr_content = json.dumps([{"instruction": s.get("instruction"), "response": s.get("response")} for s in samples])
        parsed_json_arr = json.loads(json_arr_content)
        assert len(parsed_json_arr) == len(samples)
        print("✓ Generated valid JSON array format from database records")

        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_download_from_db())
    sys.exit(0 if success else 1)
