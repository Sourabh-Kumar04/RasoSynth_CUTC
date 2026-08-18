"""Fine-tuning integration package for RasoSynthTune.

Supports PEFT/LoRA fine-tuning of open-source models using HuggingFace
Transformers and optionally Unsloth for 2-4× speed on NVIDIA GPUs.

Typical flow:
    1. A dataset generation job completes and produces a JSONL output.
    2. A FineTuneJob is created via POST /api/finetune/jobs.
    3. FinetuneJobManager spawns an async task that calls Trainer.train().
    4. Progress is streamed via WebSocket /api/finetune/jobs/{id}/stream.
    5. The checkpoint is saved locally and optionally pushed to HF Hub.
"""

from finetuning.trainer import FineTuneConfig, Trainer
from finetuning.job_manager import FinetuneJobManager

__all__ = ["FineTuneConfig", "Trainer", "FinetuneJobManager"]
