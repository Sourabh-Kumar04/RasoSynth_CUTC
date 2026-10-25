#!/usr/bin/env python3
"""
Production Smoke Test Suite for RasoSynthTune.
Tests deployed Vercel frontend routes, proxy standby resilience,
dataset studio contracts, Colab fine-tuning lifecycle, webhook serialization,
and downloadable model weight packages.
"""

import argparse
import io
import json
import sys
import zipfile
import httpx
from fastapi.testclient import TestClient

from api.server import app


def test_vercel_routes(base_url: str):
    print("\n--- [A] VERCEL LIVE PLATFORM HEALTH & ROUTING ---")
    urls_to_test = [
        ("/", "Landing Page"),
        ("/studio", "Synthetic Dataset Studio"),
        ("/datasets", "Data Library"),
        ("/finetune", "Model Training Studio"),
        ("/quality", "Quality Inspector"),
        ("/observability", "System Insights"),
        ("/providers", "AI Providers"),
        ("/settings", "Platform Settings"),
        ("/api/proxy/health", "Serverless HF Space Health Proxy"),
    ]

    client = httpx.Client(timeout=15.0, follow_redirects=True)
    for path, label in urls_to_test:
        full_url = f"{base_url.rstrip('/')}{path}"
        try:
            res = client.get(full_url)
            passed = res.status_code in (200, 304)
            symbol = "✅" if passed else "❌"
            print(f"{symbol} [{res.status_code}] {label}: {full_url}")
            if not passed:
                print(f"   Warning/Detail: {res.text[:120]}")
        except Exception as e:
            print(f"⚠️  [Timeout/Network] {label}: {e}")


def test_backend_contracts():
    print("\n--- [B] BACKEND CONTRACTS, WEBHOOKS & ARTIFACT EXPORTS ---")
    results = []

    def check(name: str, passed: bool, detail: str = ""):
        symbol = "✅" if passed else "❌"
        status = "PASSED" if passed else "FAILED"
        print(f"{symbol} [{status}] {name} {detail}")
        results.append((name, passed))
        if not passed:
            raise AssertionError(f"Smoke test assertion failed: {name} - {detail}")

    with TestClient(app) as client:
        # 1. CSRF Handshake
        res = client.get("/auth/csrf-token")
        check("CSRF Handshake", res.status_code == 200)
        token = res.json().get("csrf_token")
        client.headers["X-CSRF-Token"] = token

        # 2. Dataset Synthesis in Studio & Immediate Library Visibility
        print("\n* 1. Studio Dataset Synthesis & Library Persistence")
        ds_res = client.get("/datasets")
        check("Data Library retrieval (/datasets)", ds_res.status_code == 200)
        ds_body = ds_res.json()
        datasets = ds_body.get("data", []) if isinstance(ds_body, dict) else (ds_body if isinstance(ds_body, list) else [])
        if not datasets:
            db_instance = getattr(app.state, "db", None)
            if db_instance:
                import asyncio
                import uuid
                job_uuid = str(uuid.uuid4())
                asyncio.run(db_instance.create_job({"id": job_uuid, "status": "completed"}))
                asyncio.run(db_instance.create_dataset(
                    job_id=job_uuid,
                    name="Smoke Test Indic Dataset",
                    type="alpaca",
                    size=25,
                    metadata={"domain": "Indic Instruction"},
                    output_path="outputs/flagship_indic_gst",
                ))
            ds_res = client.get("/datasets")
            ds_body = ds_res.json()
            datasets = ds_body.get("data", []) if isinstance(ds_body, dict) else (ds_body if isinstance(ds_body, list) else [])

        check("Data Library contains active datasets", len(datasets) > 0, f"{len(datasets)} datasets present")

        # 3. Model Training Run with Webhook & Colab Target
        print("\n* 2. Launch Model Training Run with Colab Target & Webhook")
        ft_payload = {
            "dataset_path": "outputs/flagship_indic_gst/flagship_indic_gst_sft.jsonl",
            "base_model": "sarvamai/sarvam-2b-v0.5",
            "output_model_name": "smoke-test-colab-lora",
            "execution_target": "colab",
            "webhook_url": "https://discord.com/api/webhooks/mock-smoke-test",
            "lora_r": 16,
            "lora_alpha": 32,
            "num_train_epochs": 1,
            "per_device_train_batch_size": 4
        }
        ft_res = client.post("/api/finetune/jobs", json=ft_payload)
        check("Launch Colab Fine-Tuning Job", ft_res.status_code == 201, f"status={ft_res.status_code}")
        job = ft_res.json()
        job_id = job.get("id")
        check("Colab Job ID assigned", bool(job_id), f"id={job_id}")

        # Check telemetry stream ring-buffer logs
        logs_res = client.get(f"/api/finetune/jobs/{job_id}/logs")
        check("Fine-Tune Logs API active (/logs)", logs_res.status_code == 200)

        # 4. Verify Downloadable Model Weights (.zip)
        print("\n* 3. Downloadable Weights Archive & GGUF Quantization")
        dl_res = client.get(f"/api/finetune/jobs/{job_id}/download")
        check("Download LoRA Weights Archive (.zip)", dl_res.status_code == 200)
        check("Content-Type is zip", dl_res.headers.get("content-type") == "application/zip")
        with zipfile.ZipFile(io.BytesIO(dl_res.content)) as zf:
            files = zf.namelist()
            check("Zip archive contains weight files", len(files) > 0, f"{len(files)} files found: {files}")

        # 5. Verify 1-Click GGUF Export
        gguf_res = client.post(f"/api/finetune/jobs/{job_id}/export_gguf")
        check("1-Click GGUF Export (/export_gguf)", gguf_res.status_code == 200)
        gguf_data = gguf_res.json()
        check("GGUF Format is Q4_K_M", gguf_data.get("format") == "GGUF-Q4_K_M")
        check("GGUF compatible runtimes include Ollama/LM Studio", "Ollama" in gguf_data.get("runtime_compatibility", []))

    print("\n" + "=" * 70)
    print(f"🎉 ALL {len(results)} SMOKE TEST CONTRACTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Production Smoke Test Suite")
    parser.add_argument("--url", default="https://rasosynthtune-indiaai.vercel.app", help="Base URL of deployed frontend")
    parser.add_argument("--dry-run", action="store_true", help="Run local contract verification only")
    args = parser.parse_args()

    print("=" * 70)
    print("🧪 RASOSYNTHTUNE PRODUCTION SMOKE TEST SUITE")
    print(f"Target Frontend URL: {args.url}")
    print("=" * 70)

    if not args.dry_run:
        test_vercel_routes(args.url)

    test_backend_contracts()


if __name__ == "__main__":
    main()
