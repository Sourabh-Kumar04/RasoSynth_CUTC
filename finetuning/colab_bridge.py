"""
Simulated fine-tune demo bridge (Colab Bridge) — DEMO ONLY.

This module does NOT train anything. It emits progress events and placeholder
artifact files so the fine-tune UI/demo flow can be exercised without a GPU.
It must never present its outputs as training results: it emits no losses
(formula losses were removed), no GPU telemetry, and no loadable weights,
and its model card carries no DBOM seal/certificate. Real training lives in
execution_target=local (finetuning/trainer.py).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.export.huggingface_exporter import generate_hf_model_card

logger = logging.getLogger(__name__)



class ColabBridgeTrainer:
    """
    Simulated demo trainer (NOT a GPU trainer).
    Emits labelled simulated progress and placeholder artifacts only; see the
    module docstring. Use execution_target=local for real PEFT/Unsloth training.
    """

    def __init__(self, config: Any, output_dir: Path):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def execute_training(
        self,
        samples: List[Dict[str, Any]],
        put_event: Callable[[Dict[str, Any]], None],
    ) -> Path:
        """
        Simulated demo run: emits labelled progress events and placeholder
        artifacts. No GPU training happens here and no losses are measured.
        """
        put_event({
            "type": "info",
            "execution_mode": "simulated",
            "is_simulated": True,
            "message": "SIMULATED run: no GPU training takes place; progress below is illustrative only."
        })
        time.sleep(0.3)

        base_model = getattr(self.config, "base_model", "HuggingFaceTB/SmolLM2-1.7B-Instruct")
        total_epochs = getattr(self.config, "num_train_epochs", 3)
        num_samples = len(samples) if samples else 100
        steps_per_epoch = max(5, num_samples // getattr(self.config, "per_device_train_batch_size", 4))
        total_steps = steps_per_epoch * total_epochs

        put_event({
            "type": "info",
            "execution_mode": "simulated",
            "is_simulated": True,
            "message": f"SIMULATED run: base architecture '{base_model}' noted for the demo only; no weights are trained or quantised."
        })
        time.sleep(0.2)

        put_event({
            "type": "info",
            "execution_mode": "simulated",
            "is_simulated": True,
            "message": f"Injected LoRA adapters into target projections: q_proj, k_proj, v_proj, o_proj (r={getattr(self.config, 'lora_r', 16)}, alpha={getattr(self.config, 'lora_alpha', 32)}). Execution Mode: Simulated Container Pool."
        })

        # P0: no formula losses and no fictional GPU telemetry are emitted.
        # Progress events carry step/progress only; a simulated run has no
        # measured loss, utilisation, VRAM, or throughput to report.
        current_step = 0

        for epoch in range(1, total_epochs + 1):
            for s in range(1, steps_per_epoch + 1):
                current_step += 1
                progress = min(1.0, current_step / total_steps)

                if s == 1 or s == steps_per_epoch or s % max(1, steps_per_epoch // 2) == 0:
                    put_event({
                        "type": "progress",
                        "execution_mode": "simulated",
                        "is_simulated": True,
                        "epoch": epoch,
                        "step": current_step,
                        "progress": round(progress * 100, 1),
                    })
                    time.sleep(0.1)

            put_event({
                "type": "eval",
                "execution_mode": "simulated",
                "is_simulated": True,
                "epoch": epoch,
                "message": "Simulated eval checkpoint (no loss measured).",
            })

        # Compute content-bound Merkle root from real dataset samples if present
        dataset_path = getattr(self.config, "dataset_path", None)
        computed_root = None
        if dataset_path and Path(dataset_path).exists():
            try:
                from core.export.dbom_attestor import compute_sample_hash, compute_merkle_root
                leaf_hashes = []
                with open(dataset_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            leaf_hashes.append(compute_sample_hash(rec))
                if leaf_hashes:
                    computed_root = compute_merkle_root(leaf_hashes)
            except Exception:
                pass

        # No samples -> no root. Never substitute sha256 of the dataset ID/path.
        # (computed_root stays None and the card omits the DBOM block.)

        # Save placeholder artifacts in output directory. Every path is named
        # as a placeholder so a placeholder can never be mistaken for (or
        # loaded as) trained weights. The dataset Merkle root below, when
        # present, attests ONLY to the input dataset samples — never to this
        # simulated run — so no seal/certificate is attached to it.
        model_name = getattr(self.config, "output_model_name", "") or "fine-tuned-model"
        job_artifacts_dir = self.output_dir / "model_weights_placeholder"
        job_artifacts_dir.mkdir(parents=True, exist_ok=True)

        self._write_model_files(job_artifacts_dir, base_model, computed_root)

        # Create downloadable zip archive of placeholders
        zip_path = self.output_dir / "finetuned_model_lora_PLACEHOLDER.zip"
        self._package_zip(job_artifacts_dir, zip_path)

        # Create GGUF export placeholder
        gguf_path = self.output_dir / f"{model_name}-q4_k_m.gguf.PLACEHOLDER"
        self._create_gguf_export(gguf_path, base_model)

        put_event({
            "type": "completed",
            "execution_mode": "simulated",
            "is_simulated": True,
            "weights_are_placeholders": True,
            "output_path": str(job_artifacts_dir),
            "download_zip": str(zip_path),
            "gguf_path": str(gguf_path),
            "merkle_root": computed_root,
            "message": (
                "SIMULATED fine-tune completed. No losses were measured and no "
                "weights were trained; adapter/GGUF files are demo placeholders. "
                "Use execution_target=local for real PEFT/Unsloth training."
            ),
        })

        return job_artifacts_dir

    def _write_model_files(self, target_dir: Path, base_model: str, merkle_root: str):
        """Write PLACEHOLDER adapter files and a demo model card (no training).

        The card reports no losses (none were measured) and carries no DBOM
        seal or certificate: a simulated run must never be sealed as if its
        losses/weights were attested. A dataset Merkle root, when computed
        from real input samples, is disclosed as input-data provenance only.
        """
        adapter_config = {
            "base_model_name_or_path": base_model,
            "bias": "none",
            "fan_in_fan_out": False,
            "inference_mode": True,
            "init_lora_weights": True,
            "lora_alpha": getattr(self.config, "lora_alpha", 32),
            "lora_dropout": getattr(self.config, "lora_dropout", 0.05),
            "modules_to_save": None,
            "peft_type": "LORA",
            "r": getattr(self.config, "lora_r", 16),
            "target_modules": [
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj"
            ],
            "task_type": "CAUSAL_LM"
        }
        with open(target_dir / "adapter_config.json", "w") as f:
            json.dump(adapter_config, f, indent=2)

        # Placeholder weights file. The .PLACEHOLDER suffix keeps it from
        # being loaded as a safetensors file; the bytes are a header plus
        # zeroes, not trained tensors.
        safetensors_path = target_dir / "adapter_model.safetensors.PLACEHOLDER"
        with open(target_dir / "PLACEHOLDER.txt", "w") as f:
            f.write(
                "PLACEHOLDER — DEMO ONLY\n"
                "These files are not trained weights. They exist so the demo "
                "download/preview flow can be exercised without a GPU. Do not "
                "load, publish, or evaluate them as a fine-tuned model.\n"
            )
        with open(safetensors_path, "wb") as f:
            # Header representation of safetensors
            header = json.dumps({"__metadata__": {"format": "pt", "lora": "peft"}}).encode("utf-8")
            header_len = len(header).to_bytes(8, byteorder="little")
            f.write(header_len)
            f.write(header)
            f.write(b"\x00" * 4096)  # Stored tensors payload

        # Tokenizer files
        tokenizer_cfg = {
            "add_bos_token": True,
            "add_eos_token": False,
            "chat_template": "{% for message in messages %}{{ message['role'] + ': ' + message['content'] + '\n' }}{% endfor %}",
            "tokenizer_class": "PreTrainedTokenizerFast"
        }
        with open(target_dir / "tokenizer_config.json", "w") as f:
            json.dump(tokenizer_cfg, f, indent=2)

        # Demo model card: no losses (none measured), no DBOM seal/certificate.
        # The exporter omits None losses. The dataset root, when present, is
        # disclosed below as input-data provenance only.
        model_name = getattr(self.config, "output_model_name", "fine-tuned-model")
        dataset_name = getattr(self.config, "dataset_id", "rasosynth-curated-dataset") or "rasosynth-curated-dataset"
        sample_count = int(getattr(self.config, "sample_count", None) or getattr(self.config, "dataset_size", 100) or 100)

        model_card = generate_hf_model_card(
            model_name=model_name,
            base_model=base_model,
            dataset_name=dataset_name,
            sample_count=sample_count,
            epochs=getattr(self.config, "num_train_epochs", 3),
            learning_rate=getattr(self.config, "learning_rate", 2e-4),
            lora_r=getattr(self.config, "lora_r", 16),
            lora_alpha=getattr(self.config, "lora_alpha", 32),
            train_loss=None,
            eval_loss=None,
            merkle_root=None,
            certificate_id=None,
        )
        disclosure = (
            "\n\n---\n"
            "**Execution Mode**: SIMULATED demo — no training ran, no losses were "
            "measured, and the adapter/GGUF files are placeholders, not trained weights.\n"
        )
        if merkle_root:
            disclosure += (
                f"**Input dataset Merkle root** (input samples only, NOT a training "
                f"attestation): `{merkle_root}`\n"
            )
        model_card += disclosure
        with open(target_dir / "README.md", "w") as f:
            f.write(model_card)

    def _package_zip(self, source_dir: Path, zip_target: Path):
        """Bundle directory into clean zip archive."""
        with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)

    def _create_gguf_export(self, gguf_path: Path, base_model: str):
        """Create a GGUF placeholder file (magic + zeroes, NOT a quantised model).

        Callers pass a *.PLACEHOLDER path so the file cannot be loaded as GGUF.
        """
        with open(gguf_path, "wb") as f:
            magic = b"GGUF\x03\x00\x00\x00"  # GGUF v3 magic header
            f.write(magic)
            f.write(b"\x00" * 2048)
