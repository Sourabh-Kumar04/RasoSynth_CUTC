"""
Distributed Fine-Tuning Engine: FSDP & DeepSpeed ZeRO-2/3.

Provides:
- build_deepspeed_config: Dynamic DeepSpeed JSON configuration for ZeRO-2 or ZeRO-3.
- build_fsdp_config: PyTorch FSDP (Fully Sharded Data Parallel) dictionary config
  with mixed precision, CPU offloading, and activation checkpointing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DistributedTrainingOptions:
    backend: str = "deepspeed"  # 'deepspeed' | 'fsdp'
    zero_stage: int = 2          # 2 or 3 for DeepSpeed
    cpu_offload: bool = False
    gradient_clipping: float = 1.0
    fp16: bool = False
    bf16: bool = True


def build_deepspeed_config(
    batch_size: int = 4,
    grad_accum_steps: int = 4,
    learning_rate: float = 2e-4,
    zero_stage: int = 2,
    cpu_offload: bool = False,
    bf16: bool = True,
    fp16: bool = False,
) -> Dict[str, Any]:
    """Generate DeepSpeed JSON configuration dictionary for HF Trainer."""
    config: Dict[str, Any] = {
        "train_batch_size": "auto",
        "train_micro_batch_size_per_gpu": batch_size,
        "gradient_accumulation_steps": grad_accum_steps,
        "gradient_clipping": 1.0,
        "optimizer": {
            "type": "AdamW",
            "params": {
                "lr": learning_rate,
                "betas": [0.9, 0.999],
                "eps": 1e-8,
                "weight_decay": 0.01,
            },
        },
        "scheduler": {
            "type": "WarmupCosineLR",
            "params": {
                "warmup_min_lr": 0,
                "warmup_max_lr": learning_rate,
                "warmup_num_steps": "auto",
            },
        },
        "zero_optimization": {
            "stage": zero_stage,
            "allgather_partitions": True,
            "allgather_bucket_size": 2e8,
            "overlap_comm": True,
            "reduce_scatter": True,
            "reduce_bucket_size": 2e8,
        },
    }

    if bf16:
        config["bf16"] = {"enabled": True}
    elif fp16:
        config["fp16"] = {"enabled": True}

    if cpu_offload:
        config["zero_optimization"]["offload_optimizer"] = {
            "device": "cpu",
            "pin_memory": True,
        }
        if zero_stage == 3:
            config["zero_optimization"]["offload_param"] = {
                "device": "cpu",
                "pin_memory": True,
            }

    return config


def build_fsdp_config(
    sharding_strategy: str = "FULL_SHARD",
    cpu_offload: bool = False,
    backward_prefetch: str = "BACKWARD_PRE",
) -> Dict[str, Any]:
    """Generate PyTorch FSDP configuration dictionary for Accelerate / HF Trainer."""
    return {
        "fsdp": f"{sharding_strategy.lower()}",
        "fsdp_config": {
            "fsdp_min_num_params": 1e6,
            "fsdp_offload_params": cpu_offload,
            "fsdp_backward_prefetch": backward_prefetch,
            "fsdp_state_dict_type": "FULL_STATE_DICT",
            "fsdp_activation_checkpointing": True,
        },
    }
