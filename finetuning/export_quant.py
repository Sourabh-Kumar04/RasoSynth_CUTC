"""Edge Quantization and Multi-Format Packaging Engine (GGUF, AWQ, GPTQ).

Generates automated quantization recipes, conversion manifests, and hardware
footprint estimations for edge runtime serving via llama.cpp, Ollama, and vLLM.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Standard parameter size to FP16 memory lookup table (in GB)
_MODEL_FP16_VRAM = {
    "1b": 2.2,
    "2b": 4.5,
    "3b": 6.8,
    "7b": 14.5,
    "8b": 16.2,
    "13b": 27.0,
    "14b": 29.0,
    "70b": 140.0,
}

_QUANT_MULTIPLIERS = {
    "fp16": 1.0,
    "q8_0": 0.54,
    "q5_k_m": 0.38,
    "q4_k_m": 0.30,
    "q3_k_m": 0.24,
    "awq_4bit": 0.28,
    "gptq_4bit": 0.28,
}


@dataclass
class QuantizationPlan:
    model_name: str
    target_format: str
    quant_type: str
    fp16_vram_gb: float
    quant_vram_gb: float
    reduction_pct: float
    conversion_command: str
    serving_command: str
    files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "target_format": self.target_format,
            "quant_type": self.quant_type,
            "fp16_vram_gb": round(self.fp16_vram_gb, 2),
            "quant_vram_gb": round(self.quant_vram_gb, 2),
            "reduction_pct": round(self.reduction_pct, 1),
            "conversion_command": self.conversion_command,
            "serving_command": self.serving_command,
            "files": self.files,
            "metadata": self.metadata,
        }


class QuantizationExporter:
    """Manages quantization recipe creation and deployment packaging."""

    @staticmethod
    def _estimate_base_vram(model_name: str) -> float:
        name_lower = model_name.lower()
        for key, vram in _MODEL_FP16_VRAM.items():
            if f"-{key}" in name_lower or f"_{key}" in name_lower or f"{key}" in name_lower:
                return vram
        return 4.5  # default 2B parameter estimate

    @classmethod
    def generate_plan(
        cls,
        model_name: str,
        output_dir: str | Path,
        target_format: str = "gguf",
        quant_type: str = "q4_k_m",
    ) -> QuantizationPlan:
        """Create a complete quantization plan with execution commands and VRAM estimates."""
        out_path = Path(output_dir)
        fp16_vram = cls._estimate_base_vram(model_name)
        mult = _QUANT_MULTIPLIERS.get(quant_type.lower(), 0.30)
        quant_vram = fp16_vram * mult
        reduction_pct = (1.0 - mult) * 100.0

        if target_format.lower() in ("gguf", "llama.cpp", "ollama"):
            gguf_filename = f"{model_name}-{quant_type.upper()}.gguf"
            conv_cmd = (
                f"python llama.cpp/convert_hf_to_gguf.py {out_path}/merged --outfile {out_path}/{gguf_filename} --outtype f16 && "
                f"llama-quantize {out_path}/{gguf_filename} {out_path}/{gguf_filename.replace('f16', quant_type)} {quant_type.upper()}"
            )
            serve_cmd = f"llama-server -m {out_path}/{gguf_filename} -c 2048 --port 8080"
            files = [gguf_filename, "Modelfile"]
        elif target_format.lower() in ("awq", "vllm"):
            conv_cmd = (
                f"python -m autoawq.cli.quantize --model {out_path}/merged "
                f"--output {out_path}/awq-4bit --q_group_size 128 --w_bit 4"
            )
            serve_cmd = f"vllm serve {out_path}/awq-4bit --quantization awq --port 8000"
            files = ["quant_config.json", "model.safetensors"]
        else:
            # GPTQ
            conv_cmd = (
                f"python -m auto_gptq --model {out_path}/merged "
                f"--output {out_path}/gptq-4bit --bits 4 --group_size 128"
            )
            serve_cmd = f"vllm serve {out_path}/gptq-4bit --quantization gptq --port 8000"
            files = ["quantize_config.json"]

        return QuantizationPlan(
            model_name=model_name,
            target_format=target_format,
            quant_type=quant_type,
            fp16_vram_gb=fp16_vram,
            quant_vram_gb=quant_vram,
            reduction_pct=reduction_pct,
            conversion_command=conv_cmd,
            serving_command=serve_cmd,
            files=files,
            metadata={"recommended_context_tokens": 2048, "target_architecture": "arm64/x86_64"},
        )

    @classmethod
    def write_conversion_bundle(
        cls,
        model_name: str,
        output_dir: str | Path,
        target_format: str = "gguf",
        quant_type: str = "q4_k_m",
    ) -> Dict[str, Any]:
        """Write out conversion runner script and metadata manifest to disk."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        plan = cls.generate_plan(model_name, out, target_format, quant_type)

        script_path = out / "run_quantization.sh"
        script_content = (
            f"#!/usr/bin/env bash\n"
            f"set -euo pipefail\n"
            f"# RasoSynthTune Automated Edge Quantization Recipe\n"
            f"# Target Model: {model_name} ({target_format.upper()} - {quant_type.upper()})\n"
            f"# Projected VRAM: {plan.quant_vram_gb:.2f} GB (Savings: {plan.reduction_pct:.1f}%)\n\n"
            f"echo \"==> Executing conversion...\"\n"
            f"{plan.conversion_command}\n\n"
            f"echo \"==> Quantization complete. Serve with:\"\n"
            f"echo \"    {plan.serving_command}\"\n"
        )
        script_path.write_text(script_content, encoding="utf-8")

        manifest_path = out / "quant_manifest.json"
        manifest_path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")

        # Automatically synthesize Ollama Modelfile if format is GGUF or Ollama
        if target_format.lower() in ("gguf", "llama.cpp", "ollama"):
            gguf_name = f"{model_name}-{quant_type.upper()}.gguf"
            modelfile_path = out / "Modelfile"
            modelfile_content = cls.generate_ollama_modelfile(
                model_name=model_name,
                gguf_file=gguf_name,
            )
            modelfile_path.write_text(modelfile_content, encoding="utf-8")

        return {
            "plan": plan.to_dict(),
            "script_path": str(script_path),
            "manifest_path": str(manifest_path),
        }

    @classmethod
    def generate_ollama_modelfile(
        cls,
        model_name: str,
        gguf_file: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        num_ctx: int = 4096,
        stop_tokens: Optional[List[str]] = None,
    ) -> str:
        """Generate a production-ready Ollama Modelfile definition for local LLM deployment."""
        stops = stop_tokens or ["<|eot_id|>", "<|im_end|>", "</s>"]
        stop_lines = "\n".join(f'PARAMETER stop "{s}"' for s in stops)
        sys_block = (
            f'SYSTEM """{system_prompt}"""'
            if system_prompt
            else 'SYSTEM """You are a specialized domain assistant fine-tuned with RasoSynthTune."""'
        )

        return (
            f"FROM ./{gguf_file}\n\n"
            f"PARAMETER temperature {temperature}\n"
            f"PARAMETER num_ctx {num_ctx}\n"
            f"{stop_lines}\n\n"
            f"{sys_block}\n"
        )
