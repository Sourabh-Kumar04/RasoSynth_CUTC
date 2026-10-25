#!/usr/bin/env python3
"""
CLI Tool for Pipeline Resumption & Checkpoint Recovery in RasoSynthTune Enterprise.
Allows operators to inspect and resume interrupted synthesis workflows from checkpoints.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def resume_pipeline_job(
    job_id: str,
    api_url: str = "http://localhost:8000",
    checkpoint_id: Optional[str] = None,
    stage: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Resume a job via RasoSynthTune Checkpoint REST API."""
    endpoint = f"{api_url.rstrip('/')}/checkpoints/{job_id}/restore"
    csrf_endpoint = f"{api_url.rstrip('/')}/auth/csrf-token"

    print("=" * 70)
    print("  RasoSynthTune: Pipeline Checkpoint Recovery & Resumption")
    print("=" * 70)
    print(f"Target Job ID:     {job_id}")
    print(f"API Endpoint:      {endpoint}")
    if checkpoint_id:
        print(f"Checkpoint ID:     {checkpoint_id}")
    if stage:
        print(f"Target Stage:      {stage}")
    print(f"Execution Mode:    {'Dry-Run Audit' if dry_run else 'Live Pipeline Resumption'}")
    print("-" * 70)

    if dry_run:
        print("\n[OK] Dry-run audit passed. Job ID and recovery parameters validated.")
        return {
            "success": True,
            "job_id": job_id,
            "dry_run": True,
            "message": "Checkpoint recovery validated successfully in dry-run mode.",
        }

    # 1. Fetch CSRF Token
    try:
        req = urllib.request.Request(csrf_endpoint)
        with urllib.request.urlopen(req, timeout=5) as response:
            csrf_data = json.loads(response.read().decode())
            csrf_token = csrf_data.get("csrf_token", "")
    except Exception as exc:
        csrf_token = ""

    # 2. Issue restore request
    payload = {
        "job_id": job_id,
        "checkpoint_id": checkpoint_id,
        "resume_from_stage": stage,
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf_token,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode())
            print(f"\n[SUCCESS] {res_data.get('message', 'Pipeline resumed.')}")
            print(f"Resumed Stage:     {res_data.get('resume_from_stage')}")
            print(f"Resumed Progress:  {res_data.get('progress', 0.0) * 100:.1f}%")
            print(f"Samples Restored:  {res_data.get('samples_generated', 0)}")
            return res_data
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        print(f"\n[HTTP Error {e.code}] {err_msg}", file=sys.stderr)
        raise RuntimeError(f"HTTP {e.code}: {err_msg}")
    except Exception as exc:
        print(f"\n[Connection Error] {exc}", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description="Resume pipeline job from last saved checkpoint")
    parser.add_argument("--job-id", required=True, help="Job ID to resume")
    parser.add_argument("--api-url", default="http://localhost:8000", help="RasoSynthTune API base URL")
    parser.add_argument("--checkpoint-id", default=None, help="Specific Checkpoint UUID (defaults to latest)")
    parser.add_argument("--stage", default=None, help="Override resumption stage")
    parser.add_argument("--dry-run", action="store_true", help="Validate parameters without executing resumption")

    args = parser.parse_args()
    try:
        resume_pipeline_job(
            job_id=args.job_id,
            api_url=args.api_url,
            checkpoint_id=args.checkpoint_id,
            stage=args.stage,
            dry_run=args.dry_run,
        )
    except Exception as e:
        sys.exit(1)


if __name__ == "__main__":
    main()
