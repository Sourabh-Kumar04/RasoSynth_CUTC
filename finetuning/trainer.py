"""
Fine-tuning engine — PEFT/LoRA training with HuggingFace Transformers.

Supported base models:
  Llama-3    unsloth/llama-3-8b, unsloth/llama-3-8b-Instruct
  Mistral    unsloth/mistral-7b-v0.3
  Phi-3      microsoft/Phi-3-mini-4k-instruct
  Gemma-2    unsloth/gemma-2-9b
  Qwen-2.5   Qwen/Qwen2.5-7B-Instruct
  SmolLM2    HuggingFaceTB/SmolLM2-1.7B-Instruct

Unsloth is used when available (NVIDIA GPU). Falls back to plain transformers+PEFT.
"""

from __future__ import annotations

import json
import logging
import os
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

MAX_DATASET_SAMPLES = int(os.environ.get("FINETUNE_MAX_SAMPLES", "500000"))


# ── Optional imports ─────────────────────────────────────────────────────────

def _try_import_unsloth():
    try:
        from unsloth import FastLanguageModel  # type: ignore
        return FastLanguageModel
    except ImportError:
        return None


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class FineTuneConfig:
    """All knobs for a fine-tuning run."""

    # Dataset
    dataset_path: str = ""
    dataset_id: str = ""

    # Model
    base_model: str = "unsloth/llama-3-8b"
    max_seq_length: int = 2048

    # LoRA
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: list[str] = field(
        default_factory=lambda: [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ]
    )

    # Training
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    fp16: bool = False
    bf16: bool = True
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    max_steps: int = -1

    # Output
    output_dir: str = "outputs/finetune"
    output_model_name: str = ""

    # HuggingFace Hub
    push_to_hub: bool = False
    hf_token: str = ""
    hf_org: str = ""

    # Quantisation
    load_in_4bit: bool = True

    # Prompt template
    chat_template: str = "alpaca"

    def validate(self) -> None:
        """Raise ValueError on invalid config combinations."""
        if self.fp16 and self.bf16:
            raise ValueError("fp16 and bf16 cannot both be True — pick one.")
        if self.lora_r <= 0:
            raise ValueError(f"lora_r must be > 0, got {self.lora_r}")
        if self.lora_alpha <= 0:
            raise ValueError(f"lora_alpha must be > 0, got {self.lora_alpha}")
        if self.num_train_epochs <= 0 and self.max_steps <= 0:
            raise ValueError("Either num_train_epochs > 0 or max_steps > 0 is required.")
        if not self.dataset_path and not self.dataset_id:
            raise ValueError("Either dataset_path or dataset_id must be set.")

    @classmethod
    def from_dict(cls, d: dict) -> "FineTuneConfig":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)


# ── Prompt formatting ─────────────────────────────────────────────────────────

ALPACA_TEMPLATE = (
    "Below is an instruction that describes a task. "
    "Write a response that appropriately completes the request.\n\n"
    "### Instruction:\n{instruction}\n\n"
    "### Input:\n{input}\n\n"
    "### Response:\n{response}"
)

CHATML_TEMPLATE = (
    "<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n"
    "<|im_start|>user\n{instruction}<|im_end|>\n"
    "<|im_start|>assistant\n{response}<|im_end|>"
)

LLAMA3_TEMPLATE = (
    "<|begin_of_text|>"
    "<|start_header_id|>system<|end_header_id|>\n\nYou are a helpful assistant.<|eot_id|>"
    "<|start_header_id|>user<|end_header_id|>\n\n{instruction}<|eot_id|>"
    "<|start_header_id|>assistant<|end_header_id|>\n\n{response}<|eot_id|>"
)

TEMPLATES = {"alpaca": ALPACA_TEMPLATE, "chatml": CHATML_TEMPLATE, "llama3": LLAMA3_TEMPLATE}


def format_sample(sample: dict, template: str = "alpaca") -> str:
    tmpl = TEMPLATES.get(template, ALPACA_TEMPLATE)
    return tmpl.format(
        instruction=sample.get("instruction", ""),
        input=sample.get("input", ""),
        response=sample.get("response", sample.get("output", "")),
    )


# Backwards-compat alias
format_prompt = format_sample


# ── Trainer ───────────────────────────────────────────────────────────────────

class Trainer:
    """
    PEFT/LoRA fine-tuning wrapper.

    Usage:
        config = FineTuneConfig(dataset_path="outputs/my.jsonl", ...)
        async for event in Trainer(config).train():
            print(event)
    """

    def __init__(self, config: FineTuneConfig):
        self.config = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    async def train(self) -> AsyncGenerator[dict, None]:
        """Async generator of training events."""
        try:
            self.config.validate()
        except ValueError as exc:
            yield {"type": "error", "message": str(exc)}
            return

        try:
            async for event in self._run():
                if self._cancelled:
                    yield {"type": "cancelled", "message": "Cancelled by user"}
                    return
                yield event
        except Exception as exc:
            logger.exception("Fine-tuning failed: %s", exc)
            yield {"type": "error", "message": str(exc)}

    async def _run(self) -> AsyncGenerator[dict, None]:
        """
        Run blocking training in a thread executor.
        Events are posted to an asyncio.Queue shared between the thread and
        this coroutine, avoiding the anti-pattern of creating a new event loop
        inside a thread.
        """
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1024)
        loop = asyncio.get_running_loop()

        def _blocking():
            """Runs in the thread pool; calls the sync training path."""
            import concurrent.futures
            # We cannot use `await` here, so we schedule coroutines via the
            # loop that owns the queue.
            def _put(event: dict):
                loop.call_soon_threadsafe(queue.put_nowait, event)

            try:
                self._train_blocking(_put)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(exc)})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "_done"})

        future = loop.run_in_executor(None, _blocking)

        while True:
            event = await queue.get()
            if event.get("type") == "_done":
                break
            yield event
            if event.get("type") in ("completed", "error", "cancelled"):
                break

        # Drain any remaining events
        while not queue.empty():
            event = queue.get_nowait()
            if event.get("type") not in ("_done",):
                yield event

        # Propagate thread exceptions
        try:
            await asyncio.wrap_future(future)
        except Exception:
            pass  # Already yielded as error event

    def _train_blocking(self, put: callable) -> None:
        """Blocking training — runs inside a thread executor."""
        cfg = self.config
        samples = self._load_dataset(cfg.dataset_path)
        put({"type": "start", "base_model": cfg.base_model, "dataset_samples": len(samples)})

        if not samples:
            put({"type": "error", "message": "Dataset is empty — cannot fine-tune."})
            return

        try:
            import transformers  # noqa
        except ImportError:
            put({"type": "error", "message": "transformers not installed. Run: pip install transformers peft datasets trl"})
            return

        output_dir = Path(cfg.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        unsloth = _try_import_unsloth()
        if unsloth is not None:
            self._train_unsloth(cfg, samples, put, unsloth, output_dir)
        else:
            self._train_hf(cfg, samples, put, output_dir)

    # ── Unsloth path ──────────────────────────────────────────────────────────

    def _train_unsloth(self, cfg, samples, put, FastLanguageModel, output_dir):
        try:
            from trl import SFTTrainer  # type: ignore
            from transformers import TrainingArguments
            from datasets import Dataset as HFDataset  # type: ignore

            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=cfg.base_model,
                max_seq_length=cfg.max_seq_length,
                load_in_4bit=cfg.load_in_4bit,
                token=cfg.hf_token or os.environ.get("HF_TOKEN"),
            )
            model = FastLanguageModel.get_peft_model(
                model,
                r=cfg.lora_r,
                target_modules=cfg.lora_target_modules,
                lora_alpha=cfg.lora_alpha,
                lora_dropout=cfg.lora_dropout,
                bias="none",
                use_gradient_checkpointing="unsloth",
                random_state=42,
            )
            texts = [format_sample(s, cfg.chat_template) + tokenizer.eos_token for s in samples]
            hf_dataset = HFDataset.from_dict({"text": texts})
            cb = _ProgressCallback(put, cfg.num_train_epochs)

            trainer = SFTTrainer(
                model=model,
                tokenizer=tokenizer,
                train_dataset=hf_dataset,
                dataset_text_field="text",
                max_seq_length=cfg.max_seq_length,
                args=TrainingArguments(
                    output_dir=str(output_dir),
                    num_train_epochs=cfg.num_train_epochs,
                    per_device_train_batch_size=cfg.per_device_train_batch_size,
                    gradient_accumulation_steps=cfg.gradient_accumulation_steps,
                    learning_rate=cfg.learning_rate,
                    warmup_ratio=cfg.warmup_ratio,
                    lr_scheduler_type=cfg.lr_scheduler_type,
                    fp16=cfg.fp16 and not cfg.bf16,
                    bf16=cfg.bf16,
                    logging_steps=cfg.logging_steps,
                    save_steps=cfg.save_steps,
                    report_to="none",
                    max_steps=cfg.max_steps if cfg.max_steps > 0 else -1,
                ),
                callbacks=[cb],
            )
            try:
                trainer.train()
            except Exception as exc:
                put({"type": "error", "message": f"Training error: {exc}"})
                raise
            self._save_and_push(cfg, model, tokenizer, output_dir, put)
        except Exception as exc:
            put({"type": "error", "message": str(exc)})

    # ── Plain HF path ─────────────────────────────────────────────────────────

    def _train_hf(self, cfg, samples, put, output_dir):
        try:
            from peft import LoraConfig, get_peft_model, TaskType  # type: ignore
            from trl import SFTTrainer  # type: ignore
            from transformers import (  # type: ignore
                AutoModelForCausalLM, AutoTokenizer, TrainingArguments, BitsAndBytesConfig,
            )
            from datasets import Dataset as HFDataset  # type: ignore
            import torch

            bnb_config = None
            try:
                import bitsandbytes  # noqa
                if cfg.load_in_4bit and torch.cuda.is_available():
                    bnb_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.bfloat16,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                    )
            except ImportError:
                pass

            token = cfg.hf_token or os.environ.get("HF_TOKEN")
            tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, token=token)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                cfg.base_model,
                quantization_config=bnb_config,
                device_map="auto",
                token=token,
            )
            lora_config = LoraConfig(
                r=cfg.lora_r,
                lora_alpha=cfg.lora_alpha,
                target_modules=cfg.lora_target_modules,
                lora_dropout=cfg.lora_dropout,
                bias="none",
                task_type=TaskType.CAUSAL_LM,
            )
            model = get_peft_model(model, lora_config)

            texts = [format_sample(s, cfg.chat_template) + tokenizer.eos_token for s in samples]
            hf_dataset = HFDataset.from_dict({"text": texts})
            cb = _ProgressCallback(put, cfg.num_train_epochs)

            trainer = SFTTrainer(
                model=model,
                tokenizer=tokenizer,
                train_dataset=hf_dataset,
                dataset_text_field="text",
                max_seq_length=cfg.max_seq_length,
                args=TrainingArguments(
                    output_dir=str(output_dir),
                    num_train_epochs=cfg.num_train_epochs,
                    per_device_train_batch_size=cfg.per_device_train_batch_size,
                    gradient_accumulation_steps=cfg.gradient_accumulation_steps,
                    learning_rate=cfg.learning_rate,
                    warmup_ratio=cfg.warmup_ratio,
                    lr_scheduler_type=cfg.lr_scheduler_type,
                    fp16=cfg.fp16 and not cfg.bf16,
                    bf16=cfg.bf16,
                    logging_steps=cfg.logging_steps,
                    save_steps=cfg.save_steps,
                    report_to="none",
                    max_steps=cfg.max_steps if cfg.max_steps > 0 else -1,
                ),
                callbacks=[cb],
            )
            try:
                trainer.train()
            except Exception as exc:
                put({"type": "error", "message": f"Training error: {exc}"})
                raise
            self._save_and_push(cfg, model, tokenizer, output_dir, put)
        except Exception as exc:
            put({"type": "error", "message": str(exc)})

    # ── Save + push ───────────────────────────────────────────────────────────

    def _save_and_push(self, cfg, model, tokenizer, output_dir, put):
        model.save_pretrained(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))
        put({"type": "saved", "path": str(output_dir)})

        hf_url = None
        if cfg.push_to_hub and cfg.output_model_name:
            token = cfg.hf_token or os.environ.get("HF_TOKEN", "")
            repo = f"{cfg.hf_org}/{cfg.output_model_name}" if cfg.hf_org else cfg.output_model_name
            try:
                model.push_to_hub(repo, token=token)
                tokenizer.push_to_hub(repo, token=token)
                hf_url = f"https://huggingface.co/{repo}"
                put({"type": "pushed", "url": hf_url})
            except Exception as push_err:
                put({"type": "push_failed", "message": str(push_err)})

        put({"type": "completed", "output_path": str(output_dir), "hf_repo_url": hf_url})

    # ── Dataset loader ────────────────────────────────────────────────────────

    def _load_dataset(self, path: str) -> list[dict]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")
        samples: list[dict] = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(samples) >= MAX_DATASET_SAMPLES:
                    logger.warning(
                        "Dataset capped at %d samples (set FINETUNE_MAX_SAMPLES to change)",
                        MAX_DATASET_SAMPLES,
                    )
                    break
        return samples


# ── HuggingFace TrainerCallback ───────────────────────────────────────────────

class _ProgressCallback:
    """
    TrainerCallback subclass that forwards training events to a thread-safe
    put() callable (which calls loop.call_soon_threadsafe internally).
    """

    def __init__(self, put: callable, total_epochs: int):
        self._put = put
        self._total_epochs = total_epochs

    # The HF trainer duck-types callbacks — these method names are the hooks.

    def on_log(self, args, state, control, logs=None, **_):
        if not logs or "loss" not in logs:
            return
        total = state.max_steps or 1
        step = state.global_step or 0
        self._put({
            "type": "progress",
            "epoch": round(float(state.epoch or 0), 2),
            "step": step,
            "loss": round(logs["loss"], 4),
            "progress": round(min(step / total, 1.0) * 100, 1),
            "lr": logs.get("learning_rate"),
        })

    def on_evaluate(self, args, state, control, metrics=None, **_):
        if metrics and "eval_loss" in metrics:
            self._put({
                "type": "eval",
                "epoch": round(float(state.epoch or 0), 2),
                "eval_loss": round(metrics["eval_loss"], 4),
            })

    def on_save(self, args, state, control, **_):
        self._put({"type": "checkpoint", "step": state.global_step, "path": args.output_dir})


# ── Supported model catalogue ─────────────────────────────────────────────────

SUPPORTED_MODELS: list[dict] = [
    {"id": "unsloth/llama-3-8b", "name": "Llama 3 8B (Unsloth)", "family": "llama3", "params": "8B", "recommended_template": "llama3", "requires_gpu": True},
    {"id": "unsloth/llama-3-8b-Instruct", "name": "Llama 3 8B Instruct (Unsloth)", "family": "llama3", "params": "8B", "recommended_template": "llama3", "requires_gpu": True},
    {"id": "unsloth/mistral-7b-v0.3", "name": "Mistral 7B v0.3 (Unsloth)", "family": "mistral", "params": "7B", "recommended_template": "chatml", "requires_gpu": True},
    {"id": "microsoft/Phi-3-mini-4k-instruct", "name": "Phi-3 Mini 4K Instruct", "family": "phi3", "params": "3.8B", "recommended_template": "chatml", "requires_gpu": False},
    {"id": "unsloth/gemma-2-9b", "name": "Gemma 2 9B (Unsloth)", "family": "gemma2", "params": "9B", "recommended_template": "chatml", "requires_gpu": True},
    {"id": "Qwen/Qwen2.5-7B-Instruct", "name": "Qwen 2.5 7B Instruct", "family": "qwen2.5", "params": "7B", "recommended_template": "chatml", "requires_gpu": True},
    {"id": "HuggingFaceTB/SmolLM2-1.7B-Instruct", "name": "SmolLM2 1.7B Instruct", "family": "smollm2", "params": "1.7B", "recommended_template": "chatml", "requires_gpu": False},
]
