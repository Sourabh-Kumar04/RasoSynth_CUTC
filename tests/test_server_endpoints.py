#!/usr/bin/env python3
"""Test the FastAPI server endpoints for datasets.

Uses lifespan context to initialize DB and a fresh DB per test.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Security: Ensure JWT_SECRET is set before server imports (for _validate_security_config)
os.environ.setdefault(
    "JWT_SECRET",
    os.getenv("JWT_SECRET") or "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6A"
)

from fastapi.testclient import TestClient
from api.server import app, lifespan
from contextlib import asynccontextmanager
from core.config import Settings
from core.db import AsyncDB


async def setup_test_data():
    """Set up test data in the database."""
    settings = Settings()
    db = await AsyncDB.create(settings.postgres_url)

    # Clean up
    await db.clear_all_jobs()

    # Create job
    job = await db.create_job({
        "config": {"target_domain": "test", "dataset_size": 3, "export_format": "jsonl"},
        "status": "completed"
    })
    job_id = job["id"]

    # Create dataset
    ds = await db.create_dataset(
        job_id=job_id,
        name="test_dataset",
        type="jsonl",
        size=3,
        metadata={"test": True},
        output_path="/tmp/test.jsonl"
    )
    ds_id = ds["id"]

    # Create samples
    await db.create_samples(ds_id, [
        {"instruction": "Q1", "response": "A1", "input": "", "metadata": {}, "quality_score": 0.9, "difficulty_tier": 3},
        {"instruction": "Q2", "response": "A2", "input": "", "metadata": {}, "quality_score": 0.8, "difficulty_tier": 2},
        {"instruction": "Q3", "response": "A3", "input": "", "metadata": {}, "quality_score": 0.7, "difficulty_tier": 1},
    ])

    return job_id, ds_id


def test_datasets_endpoint():
    print("=== Testing Server /datasets Endpoints ===")

    # Use TestClient with lifespan events enabled
    import httpx

    with TestClient(app) as client:
        # Create test data
        job_id, ds_id = asyncio.run(setup_test_data())
        print(f"✓ Created test data: job={job_id}, dataset={ds_id}")

        # Debug: check job status before download
        resp = client.get(f"/jobs/{job_id}")
        if resp.status_code == 200:
            job_data = resp.json()
            print(f"DEBUG: Job status from /jobs/{job_id}: {job_data.get('status')}")
        else:
            print(f"DEBUG: /jobs/{job_id} returned {resp.status_code}")

        # Test GET /datasets
        print("\n--- GET /datasets ---")
        resp = client.get("/datasets?limit=10")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "data" in data, f"Missing 'data' key: {data}"
        print(f"✓ /datasets returned {len(data['data'])} dataset(s)")
        for ds in data["data"]:
            print(f"  - {ds['name']} (type={ds['type']}, size={ds['size']}, job_id={ds['job_id']})")

        # Test GET /datasets/{id}
        print(f"\n--- GET /datasets/{ds_id} ---")
        resp = client.get(f"/datasets/{ds_id}")
        assert resp.status_code == 200
        ds = resp.json()
        print(f"✓ /datasets/{ds_id} returned: {ds['name']}")
        assert ds["size"] == 3, f"Expected size=3, got {ds['size']}"
        print(f"  - size={ds['size']}, type={ds['type']}")

        # Test GET /datasets/{id}/records
        print(f"\n--- GET /datasets/{ds_id}/records ---")
        resp = client.get(f"/datasets/{ds_id}/records?limit=10")
        assert resp.status_code == 200
        records = resp.json()
        assert "records" in records
        print(f"✓ /datasets/{ds_id}/records returned {records['count']} record(s)")
        for i, r in enumerate(records["records"][:3]):
            print(f"  - {r['instruction']}: {r['response']}")

        # Test GET /jobs/{id}/records (should read from DB)
        print(f"\n--- GET /jobs/{job_id}/records ---")
        resp = client.get(f"/jobs/{job_id}/records?limit=10")
        assert resp.status_code == 200
        recs = resp.json()
        print(f"✓ /jobs/{job_id}/records returned {recs['count']} record(s) from {recs.get('source', 'unknown')}")

        # Test GET /jobs/{id}/download (should generate from DB since file doesn't exist)
        print(f"\n--- GET /jobs/{job_id}/download ---")
        resp = client.get(f"/jobs/{job_id}/download")
        assert resp.status_code == 200, f"Download failed: {resp.status_code} - {resp.text}"
        content = resp.content.decode("utf-8")
        lines = [l for l in content.split("\n") if l.strip()]
        print(f"✓ Download returned {len(lines)} lines")
        import json
        for i, line in enumerate(lines[:3]):
            rec = json.loads(line)
            print(f"  Line {i}: {rec['instruction']}")

    print("\n✅ All server endpoints PASSED")
    return True


if __name__ == "__main__":
    try:
        test_datasets_endpoint()
        sys.exit(0)
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
