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
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, model_validator

from finetuning.trainer import SUPPORTED_MODELS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/finetune", tags=["finetune"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateFineTuneJobRequest(BaseModel):
    dataset_path: str = Field("", description="Path to JSONL training file")
    dataset_id: str = Field("", description="DB Dataset ID (output_path resolved automatically)")

    base_model: str = Field("HuggingFaceTB/SmolLM2-1.7B-Instruct")
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
    chat_template: str = Field("alpaca", pattern="^(alpaca|chatml|llama3)$")

    @model_validator(mode="after")
    def check_dataset_source(self) -> "CreateFineTuneJobRequest":
        if not self.dataset_path and not self.dataset_id:
            raise ValueError("Either dataset_path or dataset_id must be provided")
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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/models")
async def list_supported_models():
    return {"models": SUPPORTED_MODELS}


@router.post("/jobs", status_code=201)
async def create_finetune_job(
    body: CreateFineTuneJobRequest,
    request: Request,
    manager=Depends(_manager),
    db=Depends(_db),
):
    payload = body.model_dump()

    # Auto-resolve dataset path from DB
    if payload.get("dataset_id") and not payload.get("dataset_path"):
        dataset = await db.db.get_dataset(payload["dataset_id"])
        if dataset is None:
            raise HTTPException(status_code=404, detail=f"Dataset {payload['dataset_id']} not found")
        if not dataset.output_path:
            raise HTTPException(status_code=400, detail="Dataset has no output_path — re-export first")
        jsonl_files = glob.glob(os.path.join(dataset.output_path, "*.jsonl"))
        if not jsonl_files:
            raise HTTPException(status_code=400, detail="No JSONL file found in dataset output directory")
        payload["dataset_path"] = jsonl_files[0]

    try:
        return await manager.create_job(payload)
    except Exception as exc:
        logger.exception("Failed to create fine-tune job")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/jobs")
async def list_finetune_jobs(
    limit: int = Query(100, ge=1, le=500),
    manager=Depends(_manager),
):
    return {"jobs": await manager.list_jobs(limit=limit)}


@router.get("/jobs/{job_id}")
async def get_finetune_job(job_id: str, manager=Depends(_manager)):
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Fine-tune job not found")
    return job


@router.delete("/jobs/{job_id}")
async def cancel_finetune_job(job_id: str, manager=Depends(_manager)):
    if not await manager.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or already completed")
    return {"status": "cancelled", "job_id": job_id}


@router.get("/jobs/{job_id}/logs")
async def get_finetune_logs(
    job_id: str,
    limit: int = Query(200, ge=1, le=500),
    manager=Depends(_manager),
):
    """Return the last N training log events from the in-memory ring buffer."""
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
