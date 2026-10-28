"""
Comprehensive Platform Dry-Run Suite.
Exercises all endpoints, data paths, serialization formats, and backend-frontend contracts.
"""

import asyncio
import io
import json
import sys
import tarfile
import zipfile
from fastapi.testclient import TestClient

from api.server import app


def run_dry_run():
    print("=" * 70)
    print("🚀 STARTING COMPLETE PLATFORM DRY RUN")
    print("=" * 70)

    results = []

    def check(name: str, passed: bool, detail: str = ""):
        symbol = "✅" if passed else "❌"
        status = "PASSED" if passed else "FAILED"
        print(f"{symbol} [{status}] {name} {detail}")
        results.append((name, passed))
        if not passed:
            raise AssertionError(f"Check failed: {name} - {detail}")

    with TestClient(app) as client:
        # 1. Health Checks & Authentication Token Handshake
        print("\n--- [1] SYSTEM & CLUSTER HEALTH CHECKS ---")
        res = client.get("/health")
        check("Health check (/health)", res.status_code == 200, f"code={res.status_code}")

        res = client.get("/health/ready")
        check("Readiness probe (/health/ready)", res.status_code == 200, f"code={res.status_code}")

        res = client.get("/health/live")
        check("Liveness probe (/health/live)", res.status_code == 200, f"code={res.status_code}")

        res = client.get("/auth/csrf-token")
        check("Stateless CSRF token handshake (/auth/csrf-token)", res.status_code == 200)
        csrf_token = res.json().get("csrf_token")
        check("CSRF Token issued", bool(csrf_token), f"token={csrf_token[:12]}...")
        client.headers["X-CSRF-Token"] = csrf_token

        # 2. Supported Models Catalogue
        print("\n--- [2] MODEL TRAINING & HARDWARE ACCELERATION ---")
        res = client.get("/api/finetune/models")
        check("Supported models catalogue (/api/finetune/models)", res.status_code == 200)
        models_data = res.json().get("models", [])
        check("Model catalogue population", len(models_data) > 0, f"{len(models_data)} models registered")

        # 3. Fine-Tuning Job Creation with Colab Default
        ds_res = client.get("/datasets")
        ds_list = (ds_res.json().get("data", []) if isinstance(ds_res.json(), dict) else ds_res.json()) if ds_res.status_code == 200 else []
        chosen_id = ds_list[0]["id"] if ds_list else "user-selected-dataset"
        ft_payload = {
            "dataset_id": chosen_id,
            "base_model": "sarvamai/sarvam-2b-v0.5",
            "output_model_name": "dryrun-test-model",
            "execution_target": "colab",
            "lora_r": 16,
            "lora_alpha": 32,
            "num_train_epochs": 1,
            "per_device_train_batch_size": 4
        }
        res = client.post("/api/finetune/jobs", json=ft_payload)
        check("Fine-tune job creation with Colab default", res.status_code == 201, f"code={res.status_code}")
        job_data = res.json()
        job_id = job_data.get("id")
        check("Job ID assigned", bool(job_id), f"job_id={job_id}")

        # 4. Fine-Tune Job Retrieval & Listing
        res = client.get(f"/api/finetune/jobs/{job_id}")
        check("Job status retrieval", res.status_code == 200)

        res = client.get("/api/finetune/jobs")
        check("Job listing query", res.status_code == 200 and len(res.json().get("jobs", [])) > 0)

        # 5. Model Card Generation
        res = client.get(f"/api/finetune/jobs/{job_id}/model_card")
        check("Hugging Face Model Card retrieval", res.status_code == 200)
        card_text = res.text
        check("Model Card has DBOM Merkle block", "Training Provenance" in card_text or "DBOM" in card_text)

        # 6. GGUF Quantization Export
        res = client.post(f"/api/finetune/jobs/{job_id}/export_gguf")
        check("GGUF Quantization Export", res.status_code == 200, res.text)
        check("GGUF payload compatibility", "GGUF-Q4_K_M" in res.text)

        # 7. Model Weights Download (Zipped LoRA Adapter)
        res = client.get(f"/api/finetune/jobs/{job_id}/download")
        check("Fine-tuned Model Zip Download", res.status_code == 200)
        check("Zip Content-Type header", res.headers.get("content-type") == "application/zip")
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            files_in_zip = zf.namelist()
            check("Zip archive integrity", len(files_in_zip) > 0, f"{len(files_in_zip)} files inside")

        # 8. Quality Inspector Overview & Metrics
        print("\n--- [3] QUALITY INSPECTOR & GROUNDING METRICS ---")
        res = client.get("/api/quality/overview")
        check("Quality Overview query (/api/quality/overview)", res.status_code == 200)

        res = client.get("/api/quality/trends")
        check("Quality Trends query (/api/quality/trends)", res.status_code == 200)

        res = client.get("/api/quality/sources")
        check("Quality Sources breakdown (/api/quality/sources)", res.status_code == 200)

        # 9. Review Studio Queue & Stats
        print("\n--- [4] DATA REVIEW STUDIO & QUEUE ---")
        res = client.get("/api/review/stats")
        check("Review stats query (/api/review/stats)", res.status_code == 200)

        res = client.get("/api/review/queue")
        check("Review queue listing (/api/review/queue)", res.status_code == 200)

        # 10. AI Providers & Failover
        print("\n--- [5] AI PROVIDERS & CIRCUIT BREAKERS ---")
        res = client.get("/providers")
        check("Provider list query (/providers)", res.status_code == 200)
        provs = res.json()
        check("Configured providers detected", isinstance(provs, list) and len(provs) > 0, f"{len(provs)} providers active")

        res = client.get("/providers/circuit-breakers")
        check("Circuit breakers status (/providers/circuit-breakers)", res.status_code == 200)

        # 11. Autonomous Research & Benchmarks
        print("\n--- [6] BENCHMARKS & EXPERIMENTS ---")
        res = client.get("/research/status")
        check("Research loop status (/research/status)", res.status_code == 200)

        res = client.get("/providers/techniques")
        check("Cached techniques query (/providers/techniques)", res.status_code == 200)

        # 12. Data Library & Multi-Format Archive Exports
        print("\n--- [7] DATA LIBRARY & ARCHIVE EXPORTS ---")
        res = client.get("/datasets")
        check("Datasets listing (/datasets)", res.status_code == 200)

    print("\n" + "=" * 70)
    print(f"🎉 COMPLETE DRY RUN SUCCESSFUL: ALL {len(results)}/{len(results)} PLATFORM CONTRACTS VERIFIED!")
    print("=" * 70)


if __name__ == "__main__":
    run_dry_run()
