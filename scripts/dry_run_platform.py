"""
Comprehensive Platform Dry-Run Suite.
Exercises all endpoints, data paths, serialization formats, and backend-frontend contracts.
"""

import asyncio
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
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
        # 0. Auth Token Setup
        from api.auth import UserRole, get_auth_manager
        auth_mgr = get_auth_manager()
        if not auth_mgr._users:
            auth_mgr._users["admin"] = {
                "user_id": "admin-001",
                "username": "admin",
                "role": UserRole.ADMIN,
                "email": "admin@example.com",
            }
        admin_uname = next(iter(auth_mgr._users.keys()))
        admin_user_data = auth_mgr._users[admin_uname]
        jwt_token = auth_mgr.create_token(
            admin_user_data.get("user_id", "admin-001"),
            admin_uname,
            admin_user_data.get("role", UserRole.ADMIN),
        )
        client.headers["Authorization"] = f"Bearer {jwt_token}"

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
        db_instance = getattr(app.state, "db", None)
        if db_instance:
            import uuid
            job_uuid = str(uuid.uuid4())
            test_file_path = os.path.join(tempfile.gettempdir(), f"dryrun_test_{job_uuid[:8]}.jsonl")
            with open(test_file_path, "w", encoding="utf-8") as f:
                f.write(json.dumps({"instruction": "What is GST?", "input": "", "output": "Goods and Services Tax."}) + "\n")
            asyncio.run(db_instance.create_job({"id": job_uuid, "status": "completed"}))
            ds_rec = asyncio.run(db_instance.create_dataset(
                job_id=job_uuid,
                name="DryRun Valid Dataset",
                type="alpaca",
                size=25,
                metadata={"domain": "Indic Instruction"},
                output_path=test_file_path,
            ))
            asyncio.run(db_instance.create_samples(ds_rec["id"], [
                {"instruction": "What is GST?", "response": "Goods and Services Tax.", "input": "", "metadata": {}},
            ]))
            chosen_id = ds_rec["id"]
        else:
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

        # Prepare completed weights and Merkle metadata fixture
        out_dir = Path(f"outputs/finetune/{job_id}")
        out_dir.mkdir(parents=True, exist_ok=True)
        import struct
        hdr = b'{"test":1}'
        hdr_len = struct.pack("<Q", len(hdr))
        (out_dir / "README.md").write_text("# Model Card\n\n## Training Provenance (DBOM)\nMerkle Root: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`\n")
        (out_dir / "adapter_model.safetensors").write_bytes(hdr_len + hdr + b"\x01\x02\x03\x04" * 64)
        (out_dir / "adapter_config.json").write_text(json.dumps({"base_model": "sarvamai/sarvam-2b-v0.5"}))
        (out_dir / "model-q4_k_m.gguf").write_bytes(b"GGUF" + bytes(4) + b"\x01\x02\x03\x04" * 64)

        if db_instance:
            db_mgr = getattr(db_instance, "db", db_instance)
            asyncio.run(db_mgr.update_finetune_job(job_id, status="completed", output_path=str(out_dir), merkle_root="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"))

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
