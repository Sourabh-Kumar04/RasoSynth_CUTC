"""
Fine-tuning API routes.

Endpoints:
  POST   /api/finetune/jobs               create a new fine-tuning job
  GET    /api/finetune/jobs               list all fine-tuning jobs
  GET    /api/finetune/jobs/{id}          get a specific job
  DELETE /api/finetune/jobs/{id}          cancel a running job
  GET    /api/finetune/jobs/{id}/logs     last N training log events (ring buffer)
  WS     /api/finetune/jobs/{id}/stream   live training event stream
  GET    /api/finetune/models             supported base model catalogue
"""

from __future__ import annotations

import glob
import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field, model_validator

from finetuning.trainer import SUPPORTED_MODELS
from api.auth import User, UserRole, get_auth_manager, get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/finetune", tags=["finetune"])


def _enforce_owner(resource: Optional[dict], current_user: User, resource_name: str = "Fine-tune job"):
    """Enforce owner check: Admin can access any row; non-admin can only access own rows.
    
    Rows with owner=None (legacy single-tenant rows) are visible only to ADMIN.
    Returns 404 (Not Found) on mismatch to prevent existence leakage.
    """
    if not resource:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")
    if current_user.role == UserRole.ADMIN:
        return
    owner = resource.get("owner")
    if not owner or owner != current_user.username:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateFineTuneJobRequest(BaseModel):
    dataset_path: str = Field("", description="Path to JSONL training file")
    dataset_id: str = Field("", description="DB Dataset ID (output_path resolved automatically)")
    dataset_version_id: str = Field("", description="Immutable approved dataset version ID")

    base_model: str = Field("sarvamai/sarvam-2b-v0.5")
    output_model_name: str = ""

    lora_r: int = Field(16, ge=4, le=128)
    lora_alpha: int = Field(32, ge=4, le=256)
    lora_dropout: float = Field(0.05, ge=0.0, le=0.5)

    num_train_epochs: int = Field(3, ge=1, le=100)
    per_device_train_batch_size: int = Field(4, ge=1, le=64)
    gradient_accumulation_steps: int = Field(4, ge=1, le=64)
    learning_rate: float = Field(2e-4, gt=0)
    max_steps: int = Field(-1)
    bf16: bool = True
    fp16: bool = False
    load_in_4bit: bool = True

    output_dir: str = "outputs/finetune"
    push_to_hub: bool = False
    hf_token: str = ""
    hf_org: str = ""
    chat_template: str = Field("alpaca", pattern="^(alpaca|chatml|llama3|sharegpt|openai_jsonl)$")
    execution_target: str = Field(
        "local",
        pattern="^(local|modal|runpod|serverless|colab|cloud_accelerated)$",
        description="Use 'local' for real PEFT/Unsloth training. 'colab'/'modal'/'runpod' may run simulated demo paths.",
    )
    webhook_url: str = Field("", description="Optional webhook URL to notify on job completion or failure (Discord, Slack, or generic HTTP)")

    @model_validator(mode="after")
    def check_dataset_source(self) -> "CreateFineTuneJobRequest":
        if not self.dataset_path and not self.dataset_id and not self.dataset_version_id:
            raise ValueError("Provide dataset_version_id, dataset_id, or dataset_path")
        if self.fp16 and self.bf16:
            raise ValueError("fp16 and bf16 cannot both be True")
        return self


# ── Dependencies ──────────────────────────────────────────────────────────────

def _manager(request: Request):
    m = getattr(request.app.state, "ft_manager", None)
    if m is None:
        raise HTTPException(status_code=503, detail="Fine-tune manager not initialised")
    return m


def _db(request: Request):
    d = getattr(request.app.state, "db", None)
    if d is None:
        raise HTTPException(status_code=503, detail="Database not initialised")
    return d


def _looks_like_real_weights(path: Path) -> bool:
    """Rigorous gate requiring real format magic + non-trivial size.

    Requires:
    - Path exists and is a regular file
    - Non-trivial file size (> 128 bytes)
    - Magic bytes header match:
      - GGUF: begins with b"GGUF"
      - SafeTensors: first 8 bytes represent unsigned 64-bit little endian JSON header length (> 0 and < 100MB),
        with valid '{' starting the header.
    - Non-zero content beyond header.
    """
    try:
        if not path.is_file():
            return False
        size = path.stat().st_size
        if size <= 128:
            return False
        with open(path, "rb") as f:
            header = f.read(16)
            if len(header) < 16:
                return False
            # Check GGUF magic
            if header.startswith(b"GGUF"):
                f.seek(8)
                sample = f.read(65536)
                return any(b != 0 for b in sample)
            # Check safetensors header length (uint64)
            import struct
            header_len = struct.unpack("<Q", header[:8])[0]
            if 0 < header_len < 100_000_000 and header[8:9] == b"{":
                sample = f.read(65536)
                return any(b != 0 for b in sample)
            return False
    except Exception:
        return False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/models")
async def list_supported_models(current_user: User = Depends(get_current_user)):
    return {"models": SUPPORTED_MODELS}


@router.post("/jobs", status_code=201)
async def create_finetune_job(
    body: CreateFineTuneJobRequest,
    request: Request,
    manager=Depends(_manager),
    db=Depends(_db),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    payload = body.model_dump()
    payload["owner"] = current_user.username

    # Validate dataset_path containment if provided by client
    if payload.get("dataset_path"):
        from core.storage.traversal import ensure_contained_path
        allowed_roots = [
            os.path.abspath("outputs"),
            os.path.abspath("data"),
            os.path.abspath(tempfile.gettempdir()),
        ]
        # Allow persistent data dir if mounted
        if os.path.isdir("/data"):
            allowed_roots.append(os.path.abspath("/data"))
        path_to_check = os.path.abspath(payload["dataset_path"])
        contained = False
        for root in allowed_roots:
            try:
                ensure_contained_path(path_to_check, root)
                contained = True
                break
            except ValueError:
                continue
        if not contained:
            raise HTTPException(
                status_code=400,
                detail=f"dataset_path {payload['dataset_path']!r} escapes allowed dataset root directories."
            )

    # Validate webhook_url SSRF/allowlist
    if payload.get("webhook_url"):
        from finetuning.job_manager import _webhook_allowed_and_safe
        ok, reason = _webhook_allowed_and_safe(payload["webhook_url"])
        if not ok:
            raise HTTPException(
                status_code=400,
                detail=f"webhook_url rejected: {reason}"
            )

    # Preferred path: resolve an immutable version. This prevents a training
    # job from silently consuming a changed "latest" export.
    version_id = str(payload.get("dataset_version_id") or "").strip()
    if version_id:
        get_version = getattr(db, "get_dataset_version", None) or (
            getattr(db.db, "get_dataset_version", None) if hasattr(db, "db") else None
        )
        version = await get_version(version_id) if get_version else None
        if version is None:
            raise HTTPException(status_code=404, detail=f"Dataset version '{version_id}' was not found")
        if (version.get("status") if isinstance(version, dict) else getattr(version, "status", None)) != "approved":
            raise HTTPException(status_code=409, detail="Only approved immutable dataset versions may be trained")
        version_path = version.get("output_path") if isinstance(version, dict) else getattr(version, "output_path", None)
        if not version_path or not os.path.isfile(version_path):
            raise HTTPException(status_code=409, detail="Dataset version artifact is unavailable; export it again before training")
        payload["dataset_path"] = version_path
        payload["dataset_id"] = version_id

    # Rate limiting: max active queued jobs check
    if manager:
        active_jobs = await manager.list_jobs(limit=100)
        running_or_pending = [
            j for j in active_jobs
            if (j.get("status") if isinstance(j, dict) else getattr(j, "status", None)) in ("pending", "running")
        ]
        if len(running_or_pending) >= 10:
            raise HTTPException(
                status_code=429,
                detail="Too many active fine-tuning jobs queued (limit: 10). Please wait for active jobs to complete."
            )

    # Auto-resolve dataset path from DB, local outputs, or samples
    if payload.get("dataset_id") and not payload.get("dataset_path"):
        raw_id = str(payload["dataset_id"]).strip()

        # 1. Query dataset by ID or by job_id
        dataset = None
        if not payload.get("dataset_path"):
            get_ds = getattr(db, "get_dataset", None) or (getattr(db.db, "get_dataset", None) if hasattr(db, "db") else None)
            if get_ds:
                dataset = await get_ds(raw_id)

            # If not found by dataset ID, check if raw_id is a job_id
            if dataset is None:
                get_ds_by_job = getattr(db, "get_datasets_by_job", None) or (getattr(db.db, "get_datasets_by_job", None) if hasattr(db, "db") else None)
                if get_ds_by_job:
                    job_datasets = await get_ds_by_job(raw_id)
                    if job_datasets:
                        dataset = job_datasets[0]

        # 3. If dataset found, try local output_path on disk
        if dataset is not None and not payload.get("dataset_path"):
            output_path = getattr(dataset, "output_path", None) or (dataset.get("output_path") if isinstance(dataset, dict) else None)
            if output_path:
                if os.path.isfile(output_path):
                    payload["dataset_path"] = output_path
                elif os.path.isdir(output_path):
                    jsonl_files = glob.glob(os.path.join(output_path, "*.jsonl"))
                    if jsonl_files:
                        payload["dataset_path"] = jsonl_files[0]

        # 4. If dataset found in DB but not on disk, dump DB samples to ephemeral JSONL
        if dataset is not None and not payload.get("dataset_path"):
            ds_id = getattr(dataset, "id", None) or (dataset.get("id") if isinstance(dataset, dict) else raw_id)
            get_samples = getattr(db, "get_samples", None) or (getattr(db.db, "get_samples", None) if hasattr(db, "db") else None)
            if get_samples:
                samples = await get_samples(str(ds_id), limit=10000)
                if samples:
                    export_dir = os.path.join(tempfile.gettempdir(), "rasosynth_datasets")
                    os.makedirs(export_dir, exist_ok=True)
                    exported_file = os.path.join(export_dir, f"{ds_id}.jsonl")
                    with open(exported_file, "w", encoding="utf-8") as f:
                        for s in samples:
                            inst = getattr(s, "instruction", None) or (s.get("instruction") if isinstance(s, dict) else "")
                            resp = getattr(s, "response", None) or (s.get("response") if isinstance(s, dict) else "")
                            inp = getattr(s, "input", None) or (s.get("input") if isinstance(s, dict) else "")
                            f.write(json.dumps({"instruction": inst, "input": inp, "output": resp}, ensure_ascii=False) + "\n")
                    payload["dataset_path"] = exported_file

        # 5. Check if raw_id is a job with output_path
        if not payload.get("dataset_path"):
            get_job_fn = getattr(db, "get_job", None) or (getattr(db.db, "get_job", None) if hasattr(db, "db") else None)
            if get_job_fn:
                job_rec = await get_job_fn(raw_id)
                if job_rec:
                    job_output = getattr(job_rec, "output_path", None) or (job_rec.get("output_path") if isinstance(job_rec, dict) else None)
                    if job_output:
                        if os.path.isfile(job_output):
                            payload["dataset_path"] = job_output
                        elif os.path.isdir(job_output):
                            j_files = glob.glob(os.path.join(job_output, "*.jsonl"))
                            if j_files:
                                payload["dataset_path"] = j_files[0]

        # 6. Fallback: search outputs/ directory for any matching jsonl
        if not payload.get("dataset_path"):
            matched_files = glob.glob(f"outputs/**/{raw_id}*.jsonl", recursive=True) + glob.glob(f"outputs/**/{raw_id}*/*.jsonl", recursive=True)
            if matched_files:
                payload["dataset_path"] = matched_files[0]

        if not payload.get("dataset_path"):
            raise HTTPException(status_code=404, detail=f"Dataset or Job ID '{raw_id}' could not be resolved to a training file.")

    try:
        job_result = await manager.create_job(payload)
        if isinstance(job_result, dict):
            job_result.pop("hf_token", None)
            if "config" in job_result and isinstance(job_result["config"], dict):
                job_result["config"].pop("hf_token", None)
        return job_result
    except Exception as exc:
        logger.exception("Failed to create fine-tune job")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/jobs")
async def list_finetune_jobs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    manager=Depends(_manager),
    current_user: User = Depends(get_current_user)):
    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.username
    all_jobs = await manager.list_jobs(limit=1000, owner=owner_filter)
    paged = all_jobs[offset : offset + limit]
    return {
        "jobs": paged,
        "total": len(all_jobs),
        "limit": limit,
        "offset": offset,
        "has_more": len(all_jobs) > offset + limit
    }


@router.get("/jobs/{job_id}")
async def get_finetune_job(job_id: str, manager=Depends(_manager),
    current_user: User = Depends(get_current_user)):
    job = await manager.get_job(job_id)
    _enforce_owner(job, current_user)
    return job


@router.delete("/jobs/{job_id}")
async def cancel_finetune_job(job_id: str, manager=Depends(_manager),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    job = await manager.get_job(job_id)
    _enforce_owner(job, current_user)
    if not await manager.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or already completed")
    return {"status": "cancelled", "job_id": job_id}


@router.get("/jobs/{job_id}/logs")
async def get_finetune_logs(
    job_id: str,
    limit: int = Query(200, ge=1, le=500),
    manager=Depends(_manager),
    current_user: User = Depends(get_current_user)):
    """Return the last N training log events from the in-memory ring buffer."""
    job = await manager.get_job(job_id)
    _enforce_owner(job, current_user)
    return {"job_id": job_id, "logs": manager.get_logs(job_id, limit=limit)}


@router.websocket("/jobs/{job_id}/stream")
async def stream_finetune_job(websocket: WebSocket, job_id: str):
    """
    WebSocket stream of live training events.
    Late subscribers receive buffered log replay before live events.
    """
    manager = getattr(websocket.app.state, "ft_manager", None)
    if manager is None:
        await websocket.close(code=1011)
        return

    # Authenticate before accept: Bearer header or ?token= query parameter.
    _ws_token = None
    _ws_auth = websocket.headers.get("authorization", "")
    if _ws_auth.startswith("Bearer "):
        _ws_token = _ws_auth[7:].strip()
    if not _ws_token:
        _ws_token = websocket.query_params.get("token")
    _ws_user = None
    if _ws_token:
        try:
            _auth_mgr = get_auth_manager()
            _token_data = _auth_mgr.verify_token(_ws_token)
            _ws_user = _auth_mgr.get_user(_token_data.username)
        except Exception:
            _ws_user = None
    if _ws_user is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    try:
        async for event in manager.subscribe(job_id):
            await websocket.send_json(event)
            if event.get("type") in ("completed", "error", "cancelled"):
                break
    except WebSocketDisconnect:
        logger.debug("WS client disconnected from fine-tune stream %s", job_id)
    except Exception as exc:
        logger.exception("WS error in fine-tune stream %s: %s", job_id, exc)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


ALLOWED_FINETUNE_ARTIFACTS = {
    "adapter_model.safetensors",
    "adapter_config.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.json",
    "merges.txt",
    "added_tokens.json",
    "README.md",
    "training_args.bin",
    "trainer_state.json",
}


@router.get("/jobs/{job_id}/download")
async def download_finetuned_model(job_id: str, manager=Depends(_manager),
    current_user: User = Depends(get_current_user)):
    """Download zipped fine-tuned LoRA adapter weights and model artifacts."""
    job = await manager.get_job(job_id)
    _enforce_owner(job, current_user)

    # Check job completion: incomplete -> 409
    job_status = getattr(job, "status", None) or (job.get("status") if isinstance(job, dict) else None)
    if job_status and job_status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Fine-tuning job '{job_id}' is not complete (status: {job_status}).",
        )

    output_path = getattr(job, "output_path", None) or (job.get("output_path") if isinstance(job, dict) else None)
    if not output_path:
        # Check standard default path
        output_path = f"outputs/finetune/{job_id}"

    out_dir = Path(output_path)
    source_dir = out_dir if out_dir.is_dir() else out_dir.parent
    if not _looks_like_real_weights(source_dir / "adapter_model.safetensors"):
        raise HTTPException(
            status_code=404,
            detail="No adapter exists for this job: no trained adapter weights were found, and none are fabricated in their place.",
        )

    zip_candidate = source_dir / "finetuned_model_lora.zip"
    with zipfile.ZipFile(zip_candidate, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith(".zip"):
                    continue
                # Strict artifact allowlist: only declared artifact files, never stray logs/files
                if file not in ALLOWED_FINETUNE_ARTIFACTS:
                    continue
                fp = Path(root) / file
                zipf.write(fp, fp.relative_to(source_dir))

    return FileResponse(
        str(zip_candidate),
        media_type="application/zip",
        filename=f"rasosynth-model-{job_id[:8]}.zip"
    )


@router.get("/jobs/{job_id}/model_card")
async def get_model_card(job_id: str, manager=Depends(_manager),
    current_user: User = Depends(get_current_user)):
    """Return Hugging Face Model Card with DBOM Merkle verification proof."""
    job = await manager.get_job(job_id)
    _enforce_owner(job, current_user)

    output_path = getattr(job, "output_path", None) or (job.get("output_path") if isinstance(job, dict) else None)
    if output_path:
        readme_path = Path(output_path) / "README.md"
        if not readme_path.exists():
            readme_path = Path(output_path).parent / "README.md"
        if readme_path.exists():
            return PlainTextResponse(readme_path.read_text(encoding="utf-8"))

    # Fallback to dynamically generated card
    import hashlib
    from core.export.huggingface_exporter import generate_hf_model_card
    base_model = getattr(job, "base_model", "HuggingFaceTB/SmolLM2-1.7B-Instruct") if not isinstance(job, dict) else job.get("base_model", "HuggingFaceTB/SmolLM2-1.7B-Instruct")
    model_name = getattr(job, "output_model_name", "") or (job.get("output_model_name") if isinstance(job, dict) else "") or f"rasosynth-{job_id[:8]}"
    dataset_id = getattr(job, "dataset_id", "") or (job.get("dataset_id") if isinstance(job, dict) else "") or "rasosynth-dataset"
    sample_count = getattr(job, "sample_count", None) or (job.get("sample_count") if isinstance(job, dict) else None)
    if not sample_count:
        sample_count = getattr(job, "dataset_size", None) or (job.get("dataset_size") if isinstance(job, dict) else None)
    if not sample_count:
        # Check database for dataset sample count
        try:
            if hasattr(manager, "db") and manager.db:
                ds = await manager.db.get_dataset(str(dataset_id))
                if ds:
                    sample_count = getattr(ds, "size", None)
        except Exception:
            pass
    # None = not recorded. Never invent a 100-sample corpus for the card.
    sample_count = int(sample_count) if sample_count else None

    train_loss = getattr(job, "final_train_loss", None) or (job.get("final_train_loss") if isinstance(job, dict) else None)
    if train_loss is None:
        # No measured loss: omit the loss lines from the card (the exporter
        # skips them when train_loss is None) instead of defaulting to 0.3870.
        train_loss = getattr(job, "train_loss", None) or (job.get("train_loss") if isinstance(job, dict) else None)
    train_loss = float(train_loss) if train_loss is not None else None

    eval_loss = getattr(job, "final_eval_loss", None) or (job.get("final_eval_loss") if isinstance(job, dict) else None)
    if eval_loss is None:
        eval_loss = getattr(job, "eval_loss", None) or (job.get("eval_loss") if isinstance(job, dict) else None)
    # No measured eval loss: omit it. Never derive eval = train * 1.04.
    eval_loss = float(eval_loss) if eval_loss is not None else None

    merkle_root = getattr(job, "merkle_root", None) or (job.get("merkle_root") if isinstance(job, dict) else None)
    # A missing root must not become sha256("dataset:{id}"): a hash of the
    # ID string is not a Merkle root over samples. Leave it absent and the
    # exporter omits the DBOM block.
    if not merkle_root:
        merkle_root = None

    model_seal = getattr(job, "model_seal", None) or (job.get("model_seal") if isinstance(job, dict) else None)
    if not model_seal:
        # Build a seal only from recorded values; omit it otherwise.
        if merkle_root and train_loss is not None and eval_loss is not None:
            model_seal = hashlib.sha256(f"{job_id}:{merkle_root}:{train_loss}:{eval_loss}".encode("utf-8")).hexdigest()
        else:
            model_seal = None

    is_simulated = bool(
        getattr(job, "is_simulated", False)
        or (job.get("is_simulated") if isinstance(job, dict) else False)
        or getattr(job, "execution_mode", "") == "simulated"
        or (job.get("execution_mode") if isinstance(job, dict) else "") == "simulated"
    )

    job_config = getattr(job, "config", {}) if not isinstance(job, dict) else job.get("config", {})
    if not isinstance(job_config, dict):
        job_config = {}
    holdout_decision = job_config.get("holdout_decision") or job_config.get("held_out_split")
    eval_report = job_config.get("eval_report")

    card = generate_hf_model_card(
        model_name=model_name,
        base_model=base_model,
        dataset_name=str(dataset_id),
        sample_count=sample_count,
        epochs=getattr(job, "num_train_epochs", 3) if not isinstance(job, dict) else job.get("num_train_epochs", 3),
        learning_rate=getattr(job, "learning_rate", 2e-4) if not isinstance(job, dict) else job.get("learning_rate", 2e-4),
        lora_r=getattr(job, "lora_r", 16) if not isinstance(job, dict) else job.get("lora_r", 16),
        lora_alpha=getattr(job, "lora_alpha", 32) if not isinstance(job, dict) else job.get("lora_alpha", 32),
        train_loss=train_loss,
        eval_loss=eval_loss,
        merkle_root=merkle_root,
        certificate_id=f"DBOM-{merkle_root[:12].upper()}" if merkle_root else None,
        holdout_decision=holdout_decision,
        eval_report=eval_report,
    )
    execution_mode = getattr(job, "execution_mode", None) or (job.get("execution_mode") if isinstance(job, dict) else None)
    seal_line = f"**DBOM Provenance Seal**: `{model_seal}`\n" if model_seal else ""
    if is_simulated:
        card += f"\n\n---\n{seal_line}**Execution Mode**: Simulated (Accelerated Container Pool) — loss curves and adapter/GGUF files are demo placeholders, not GPU-trained weights.\n"
    elif execution_mode:
        card += f"\n\n---\n{seal_line}**Execution Mode**: {execution_mode}\n"
    else:
        # Never stamp an unverified run as a hardware run.
        card += f"\n\n---\n{seal_line}**Execution Mode**: Unknown (not recorded — not verified as a hardware run)\n"
    return PlainTextResponse(card)


@router.post("/jobs/{job_id}/export_gguf")
async def export_gguf_quantization(job_id: str, manager=Depends(_manager),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.USER]))):
    """Generate 4-bit GGUF quantization (Q4_K_M) for edge and local LM deployment."""
    job = await manager.get_job(job_id)
    _enforce_owner(job, current_user)

    output_path = getattr(job, "output_path", None) or (job.get("output_path") if isinstance(job, dict) else None) or f"outputs/finetune/{job_id}"
    out_dir = Path(output_path)
    gguf_path = out_dir / "model-q4_k_m.gguf"
    # P0: a GGUF file is only "ready" when a real one exists on disk (the
    # old path wrote magic + zeroes and reported an invented size).
    # Previously fabricated zero-files are rejected by the weights check.
    if _looks_like_real_weights(gguf_path):
        return {
            "status": "ready",
            "format": "GGUF-Q4_K_M",
            "gguf_path": str(gguf_path),
            "file_size_mb": round(gguf_path.stat().st_size / 1_000_000, 2),
            "runtime_compatibility": "file present, compatibility not verified",
        }
    # No real GGUF: quantisation requires trained weights, and no
    # quantisation backend is wired into this endpoint, so it cannot
    # manufacture one from a placeholder.
    if not _looks_like_real_weights(out_dir / "adapter_model.safetensors"):
        raise HTTPException(
            status_code=404,
            detail="No adapter exists for this job; GGUF export requires trained adapter weights.",
        )
    raise HTTPException(
        status_code=501,
        detail="GGUF export is not implemented: a trained adapter exists but no quantisation backend is wired into this endpoint.",
    )


@router.get("/jobs/{job_id}/download_gguf")
async def download_gguf_file(job_id: str, manager=Depends(_manager),
    current_user: User = Depends(get_current_user)):
    """Download quantized GGUF binary for edge/local LM deployment (Ollama / LM Studio)."""
    job = await manager.get_job(job_id)
    _enforce_owner(job, current_user)

    output_path = getattr(job, "output_path", None) or (job.get("output_path") if isinstance(job, dict) else None) or f"outputs/finetune/{job_id}"
    out_dir = Path(output_path)
    gguf_path = out_dir / "model-q4_k_m.gguf"
    # P0: serve only a real GGUF file; previously fabricated magic+zero
    # files (and missing files) fail instead of being served or created.
    if not _looks_like_real_weights(gguf_path):
        raise HTTPException(
            status_code=404,
            detail="No GGUF export exists for this job.",
        )

    model_name = getattr(job, "output_model_name", None) or (job.get("output_model_name") if isinstance(job, dict) else None) or f"rasosynth-{job_id[:8]}"
    return FileResponse(
        str(gguf_path),
        media_type="application/octet-stream",
        filename=f"{model_name}-q4_k_m.gguf"
    )


@router.get("/jobs/{job_id}/modelfile")
async def get_ollama_modelfile(job_id: str, manager=Depends(_manager),
    current_user: User = Depends(get_current_user)):
    """Generate an Ollama-compatible Modelfile with optimal chat prompt template and stopping criteria."""
    job = await manager.get_job(job_id)
    _enforce_owner(job, current_user)

    model_name = getattr(job, "output_model_name", None) or (job.get("output_model_name") if isinstance(job, dict) else None) or f"rasosynth-{job_id[:8]}"
    template_type = getattr(job, "chat_template", "alpaca") or "alpaca"

    if template_type == "chatml":
        template_str = '"""{{ if .System }}<|im_start|>system\\n{{ .System }}<|im_end|>\\n{{ end }}{{ if .Prompt }}<|im_start|>user\\n{{ .Prompt }}<|im_end|>\\n{{ end }}<|im_start|>assistant\\n{{ .Response }}<|im_end|>"""'
        stop_str = 'PARAMETER stop "<|im_end|>"'
    else:
        template_str = '"""Below is an instruction that describes a task. Write a response that appropriately completes the request.\\n\\n### Instruction:\\n{{ .Prompt }}\\n\\n### Response:\\n{{ .Response }}"""'
        stop_str = 'PARAMETER stop "### Instruction:"'

    modelfile_content = f"""# Ollama Modelfile for RasoSynthTune Fine-Tuned Model
# Base Job ID: {job_id}
# Model: {model_name}

FROM ./{model_name}-q4_k_m.gguf

TEMPLATE {template_str}

PARAMETER temperature 0.3
PARAMETER top_p 0.95
{stop_str}
"""
    return PlainTextResponse(modelfile_content, media_type="text/plain")
