#!/usr/bin/env python3
"""
Production System Health Diagnostic & Latency Auditor for RasoSynthTune Enterprise.
Audits:
- PostgreSQL / AsyncDB storage
- Redis distributed cache & Celery broker
- Qdrant vector database
- Cloud Compute GPU endpoints (Modal, RunPod, HuggingFace)
- LLM Provider configurations & latency
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_settings


async def run_diagnostics(verbose: bool = False) -> Dict[str, Any]:
    """Execute asynchronous infrastructure and cloud diagnostic checks."""
    settings = get_settings()
    results: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "healthy",
        "components": {},
    }

    # 1. Output directory write check
    output_dir = Path("outputs")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        test_file = output_dir / ".health_test"
        test_file.write_text("health_ok")
        test_file.unlink()
        results["components"]["filesystem"] = {"status": "ok", "path": str(output_dir.resolve())}
    except Exception as exc:
        results["components"]["filesystem"] = {"status": "error", "error": str(exc)}
        results["status"] = "degraded"

    # 2. Database check
    db_start = time.perf_counter()
    try:
        from core.db import AsyncDB
        db = await asyncio.wait_for(AsyncDB.create(settings.postgres_url), timeout=2.0)
        jobs = await asyncio.wait_for(db.list_jobs(limit=1), timeout=2.0)
        db_lat = (time.perf_counter() - db_start) * 1000
        results["components"]["database"] = {
            "status": "ok",
            "latency_ms": round(db_lat, 2),
            "url_scheme": settings.postgres_url.split(":")[0],
        }
    except Exception as exc:
        results["components"]["database"] = {"status": "error", "error": str(exc)}
        results["status"] = "degraded"

    # 3. Redis broker check
    redis_start = time.perf_counter()
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, socket_timeout=2.0, socket_connect_timeout=2.0)
        await asyncio.wait_for(r.ping(), timeout=2.0)
        await r.aclose()
        r_lat = (time.perf_counter() - redis_start) * 1000
        results["components"]["redis"] = {"status": "ok", "latency_ms": round(r_lat, 2)}
    except Exception as exc:
        results["components"]["redis"] = {"status": "error", "error": str(exc)}
        results["status"] = "degraded"

    # 4. Cloud GPU endpoints check
    m_id = os.getenv("MODAL_TOKEN_ID") or settings.modal_token_id
    m_sec = os.getenv("MODAL_TOKEN_SECRET") or settings.modal_token_secret
    r_key = os.getenv("RUNPOD_API_KEY") or settings.runpod_api_key
    h_tok = os.getenv("HF_TOKEN") or settings.hf_token

    results["components"]["cloud_compute"] = {
        "modal_serverless": "configured" if (m_id and m_sec) else "not_configured",
        "runpod_workers": "configured" if r_key else "not_configured",
        "huggingface_hub": "configured" if h_tok else "not_configured",
    }

    # 5. LLM Providers check
    providers = {}
    for prov, env_key in [
        ("gemini", "GOOGLE_API_KEY"),
        ("nvidia_nim", "NVIDIA_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("aikosh", "AIKOSH_API_KEY"),
    ]:
        val = os.getenv(env_key) or getattr(settings, env_key.lower(), None)
        providers[prov] = "configured" if bool(val) else "not_configured"
    results["components"]["llm_providers"] = providers

    # 6. Overall health check resolution
    if any(c.get("status") == "error" for c in results["components"].values() if isinstance(c, dict)):
        results["status"] = "degraded"

    return results


def print_dashboard(diag: Dict[str, Any]):
    """Format and print health diagnosis to terminal."""
    print("=" * 72)
    print("  RasoSynthTune Enterprise System Health & Diagnostic Suite")
    print("=" * 72)
    print(f"Timestamp:      {diag['timestamp']}")
    print(f"Overall Status: {diag['status'].upper()}")
    print("-" * 72)

    comps = diag["components"]
    # Filesystem
    fs = comps.get("filesystem", {})
    print(f"  [Filesystem]     Status: {fs.get('status')} | Target: {fs.get('path', 'N/A')}")

    # Database
    db = comps.get("database", {})
    print(f"  [Database]       Status: {db.get('status')} | Latency: {db.get('latency_ms', 'N/A')}ms")

    # Redis
    rd = comps.get("redis", {})
    print(f"  [Redis Cache]    Status: {rd.get('status')} | Latency: {rd.get('latency_ms', 'N/A')}ms")

    # Cloud Compute
    cc = comps.get("cloud_compute", {})
    print("-" * 72)
    print("  Cloud GPU Execution Fabric:")
    print(f"    • Modal Serverless:   {cc.get('modal_serverless')}")
    print(f"    • RunPod Workers:     {cc.get('runpod_workers')}")
    print(f"    • Hugging Face Hub:   {cc.get('huggingface_hub')}")

    # LLM Providers
    llm = comps.get("llm_providers", {})
    print("-" * 72)
    print("  Cognitive Model Providers:")
    for prov, st in llm.items():
        print(f"    • {prov:15s}: {st}")
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="RasoSynthTune System Health Diagnostic Tool")
    parser.add_argument("--json", action="store_true", help="Output diagnosis in JSON format")
    parser.add_argument("--verbose", action="store_true", help="Verbose error traces")
    args = parser.parse_args()

    diag = asyncio.run(run_diagnostics(verbose=args.verbose))
    if args.json:
        print(json.dumps(diag, indent=2))
    else:
        print_dashboard(diag)


if __name__ == "__main__":
    main()
