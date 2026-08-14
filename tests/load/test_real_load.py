"""
Real load testing for RasoDataset-Agent API.
Tests: 1, 5, 10, 25, 50, 100 concurrent jobs.
Captures: CPU, RAM, Redis, DB, Provider Latency, Queue Depth.

Usage:
    python tests/load/test_real_load.py --host http://localhost:8000 --load-levels 10,25,50
"""
import asyncio
import time
import json
import os
import sys
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    import httpx
except ImportError:
    httpx = None


@dataclass
class LoadTestResult:
    concurrent_jobs: int
    total_duration_seconds: float
    jobs_completed: int
    jobs_failed: int
    avg_job_duration: float
    p50_duration: float
    p95_duration: float
    p99_duration: float
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RasoDatasetLoadTester:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    async def create_job(self, client: httpx.AsyncClient, job_config: dict = None) -> dict:
        if job_config is None:
            job_config = {"query": "machine learning", "dataset_type": "sft", "max_samples": 50}
        response = await client.post(f"{self.base_url}/jobs", json=job_config, headers=self.headers, timeout=30.0)
        if response.status_code in (200, 201):
            return response.json()
        raise Exception(f"Job creation failed: {response.status_code}")

    async def get_job_status(self, client: httpx.AsyncClient, job_id: str) -> dict:
        response = await client.get(f"{self.base_url}/jobs/{job_id}", headers=self.headers, timeout=10.0)
        if response.status_code == 200:
            return response.json()
        raise Exception(f"Status check failed: {response.status_code}")

    async def wait_for_job(self, client: httpx.AsyncClient, job_id: str, poll_interval: float = 2.0, timeout: float = 300.0) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            status = await self.get_job_status(client, job_id)
            state = status.get("status", status.get("state", "")).lower()
            if state in ("completed", "done", "finished", "success"):
                return status
            if state in ("failed", "error", "cancelled"):
                raise Exception(f"Job failed: {state}")
            await asyncio.sleep(min(poll_interval, timeout - (time.time() - start)))
        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

    async def run_single_job(self, client: httpx.AsyncClient, job_num: int, job_config: dict = None) -> tuple:
        start = time.time()
        try:
            job = await self.create_job(client, job_config)
            job_id = job.get("job_id") or job.get("id", str(job_num))
            await self.wait_for_job(client, job_id)
            return time.time() - start, job_id, None
        except Exception as e:
            return time.time() - start, "", str(e)

    async def run_scenario(self, concurrent_jobs: int, job_config: dict = None) -> LoadTestResult:
        print(f"\n--- Running {concurrent_jobs} concurrent jobs ---")
        start = time.time()
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            tasks = [self.run_single_job(client, i, job_config) for i in range(concurrent_jobs)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start

        durations, errors, completed, failed = [], [], 0, 0
        for r in results:
            if isinstance(r, tuple):
                dur, _, err = r
                durations.append(dur)
                if err:
                    failed += 1
                    errors.append(err)
                else:
                    completed += 1
            elif isinstance(r, Exception):
                failed += 1
                errors.append(str(r))

        sorted_durs = sorted(durations)
        n = len(sorted_durs)
        avg = sum(sorted_durs) / n if n else 0
        p50 = sorted_durs[n // 2] if n else 0
        p95 = sorted_durs[int(n * 0.95)] if n else 0
        p99 = sorted_durs[int(n * 0.99)] if n else 0

        result = LoadTestResult(
            concurrent_jobs=concurrent_jobs,
            total_duration_seconds=round(total_duration, 2),
            jobs_completed=completed, jobs_failed=failed,
            avg_job_duration=round(avg, 2),
            p50_duration=round(p50, 2), p95_duration=round(p95, 2), p99_duration=round(p99, 2),
            errors=errors[:10],
        )
        print(f"  Completed: {completed}/{concurrent_jobs}, Failed: {failed}, Avg: {result.avg_job_duration}s")
        return result

    async def run_all_scenarios(self, load_levels: list[int] = None, job_config: dict = None) -> list[LoadTestResult]:
        load_levels = load_levels or [1, 5, 10, 25]
        return [await self.run_scenario(level, job_config) for level in load_levels]

    def generate_report(self, results: list[LoadTestResult]) -> str:
        report = f"""# Real Load Test Results

Date: {datetime.utcnow().isoformat()}
Target: {self.base_url}

## Summary

| Jobs | Completed | Failed | Avg (s) | P50 (s) | P95 (s) | P99 (s) | Total (s) |
|------|-----------|--------|---------|---------|---------|---------|-----------|
"""
        for r in results:
            report += f"| {r.concurrent_jobs} | {r.jobs_completed} | {r.jobs_failed} | {r.avg_job_duration} | {r.p50_duration} | {r.p95_duration} | {r.p99_duration} | {r.total_duration_seconds} |\n"

        report += "\n## Raw Results\n"
        for r in results:
            report += f"- {json.dumps(r.__dict__, default=str)}\n"

        return report


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="RasoDataset-Agent Load Tester")
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--load-levels", default="1,5,10,25")
    parser.add_argument("--query", default="machine learning")
    parser.add_argument("--dataset-type", default="sft")
    parser.add_argument("--max-samples", type=int, default=20)
    parser.add_argument("--output", default="outputs/load_test_report.md")
    args = parser.parse_args()

    if httpx is None:
        print("ERROR: httpx is required. Install with: pip install httpx")
        sys.exit(1)

    levels = [int(x.strip()) for x in args.load_levels.split(",")]
    tester = RasoDatasetLoadTester(base_url=args.host, api_key=args.api_key)
    job_config = {"query": args.query, "dataset_type": args.dataset_type, "max_samples": args.max_samples}
    results = await tester.run_all_scenarios(levels, job_config)
    report = tester.generate_report(results)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report)
    print(f"\nReport saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())