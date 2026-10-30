"""Export-time held-out stratified dataset splitting.

Carves a stratified held-out validation and test set from the approved dataset
at export time (after human-review decisions):
1. Groups/deduplicates by source first to prevent data contamination/leakage.
2. Stratifies across topic/domain, difficulty_tier, and language dimensions.
3. Splits deterministically within strata bound to job_id and seed.
4. Size-dependent floor enforcement:
   - Hard floor 1000 for automatic full-platform eval.
   - Below 1000: trains on 100% of samples, flags 'no internal eval, upload real validation examples',
     logs warning, and records exact train/val/test counts.
   - At or above floor: holds out per batch-tied formula (effective batch 16, 3 epochs).
5. Retains the primary training file path unchanged, saving val/test splits as job artifacts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Hard floor for automatic full-platform held-out evaluation
EVAL_PLATFORM_FLOOR = 1000

# Effective batch training hyperparameter constants
DEFAULT_EFFECTIVE_BATCH_SIZE = 16
DEFAULT_EPOCHS = 3
SPLIT_VERSION = "1.0.0"

NO_INTERNAL_EVAL_FLAG = "no internal eval, upload real validation examples"


def _sample_to_dict(sample: Any) -> Dict[str, Any]:
    """Normalize sample to dict format."""
    if isinstance(sample, dict):
        return sample
    if hasattr(sample, "__dict__"):
        return dict(sample.__dict__)
    return {
        "instruction": getattr(sample, "instruction", ""),
        "response": getattr(sample, "response", ""),
        "input": getattr(sample, "input", ""),
        "metadata": getattr(sample, "metadata", {}) or {},
        "difficulty_tier": getattr(sample, "difficulty_tier", 3),
    }


def _extract_source_key(sample_dict: Dict[str, Any]) -> str:
    """Extract a canonical source identifier to prevent source-level cross-split leakage."""
    meta = sample_dict.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    source_url = (meta.get("source_url") or sample_dict.get("source_url") or "").strip()
    if source_url:
        return f"url:{source_url}"

    source_id = (meta.get("source_id") or meta.get("source_hash") or "").strip()
    if source_id:
        return f"id:{source_id}"

    source_text = (sample_dict.get("source_text") or meta.get("source_text") or "").strip()
    if source_text:
        # Use content prefix hash for raw text sources
        h = hashlib.sha256(source_text[:200].encode("utf-8")).hexdigest()[:16]
        return f"text:{h}"

    # Fallback to instruction hash if no source information is present
    inst = (sample_dict.get("instruction") or "").strip().lower()
    h = hashlib.sha256(inst.encode("utf-8")).hexdigest()[:16]
    return f"inst:{h}"


def _extract_stratum_key(sample_dict: Dict[str, Any]) -> Tuple[str, str, str]:
    """Extract multi-dimensional stratification tuple (topic, difficulty, language)."""
    meta = sample_dict.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    topic = str(meta.get("topic") or meta.get("domain") or "general").strip().lower()
    difficulty = str(sample_dict.get("difficulty_tier") or meta.get("difficulty_tier") or "3")
    language = str(meta.get("language") or "en").strip().lower()
    return (topic, difficulty, language)


def _compute_samples_hash(samples: List[Dict[str, Any]]) -> str:
    """Compute deterministic SHA-256 fingerprint over samples."""
    lines = []
    for s in samples:
        inst = str(s.get("instruction", "")).strip()
        resp = str(s.get("response", "")).strip()
        lines.append(f"{inst}::{resp}")
    lines.sort()
    content = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def derive_split_seed(job_id: str, custom_seed: Optional[int | str] = None) -> int:
    """Derive a reproducible, job-bound integer seed."""
    base = f"{job_id}:{custom_seed if custom_seed is not None else 'default_eval_split_seed'}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def create_stratified_held_out_split(
    samples: List[Any],
    job_id: str,
    floor: int = EVAL_PLATFORM_FLOOR,
    val_ratio: float = 0.10,
    test_ratio: float = 0.10,
    effective_batch_size: int = DEFAULT_EFFECTIVE_BATCH_SIZE,
    epochs: int = DEFAULT_EPOCHS,
    seed: Optional[int | str] = None,
    split_version: str = SPLIT_VERSION,
) -> Dict[str, Any]:
    """Carve a stratified held-out split from approved samples.

    Rules:
    - Group and deduplicate by source first (no source leakage).
    - Stratify first, split within strata.
    - Deterministic and job-bound / seeded.
    - If total samples < floor (1000):
      train on 100% and flag 'no internal eval, upload real validation examples'.
    - If total samples >= floor (1000):
      carve val and test sets tied to batch and stratum boundaries.
    """
    normalized_samples: List[Dict[str, Any]] = [_sample_to_dict(s) for s in samples]
    total_count = len(normalized_samples)
    derived_seed = derive_split_seed(job_id, seed)

    # 1. Below training floor check (resolve hard-1000 vs 600 divergence)
    if total_count < floor:
        warning_msg = (
            f"Dataset size ({total_count}) is below the evaluation floor ({floor}). "
            f"Training on 100% of samples without internal held-out eval. "
            f"Upload real validation examples for post-training verification."
        )
        logger.warning("[%s] %s", job_id, warning_msg)

        train_hash = _compute_samples_hash(normalized_samples)
        decision = {
            "floor": floor,
            "total_samples": total_count,
            "train_count": total_count,
            "val_count": 0,
            "test_count": 0,
            "status": "below_floor_100_pct_train",
            "flag": NO_INTERNAL_EVAL_FLAG,
            "warning": warning_msg,
            "effective_batch_size": effective_batch_size,
            "epochs": epochs,
            "seed": derived_seed,
            "split_version": split_version,
            "job_id": job_id,
            "train_hash": train_hash,
            "val_hash": None,
            "test_hash": None,
        }
        return {
            "train": normalized_samples,
            "val": [],
            "test": [],
            "decision": decision,
        }

    # 2. At or above floor: Group by source first (prevent cross-split leakage)
    source_to_samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    seen_sample_hashes = set()

    for s in normalized_samples:
        # Deduplicate identical instruction/response pairs first
        inst_clean = " ".join(str(s.get("instruction", "")).strip().casefold().split())
        resp_clean = " ".join(str(s.get("response", "")).strip().casefold().split())
        pair_hash = hashlib.sha256(f"{inst_clean}::{resp_clean}".encode("utf-8")).hexdigest()
        if pair_hash in seen_sample_hashes:
            continue
        seen_sample_hashes.add(pair_hash)

        src_key = _extract_source_key(s)
        source_to_samples[src_key].append(s)

    # Group source clusters into strata
    # Key: (topic, difficulty, language) -> List[List[Dict[str, Any]]] (clusters)
    strata: Dict[Tuple[str, str, str], List[List[Dict[str, Any]]]] = defaultdict(list)

    for src_key, cluster in source_to_samples.items():
        # Stratum of cluster determined by first sample (or dominant sample)
        primary_stratum = _extract_stratum_key(cluster[0])
        strata[primary_stratum].append(cluster)

    rng = random.Random(derived_seed)

    # Batch-tied target allocations: effective batch size 16 minimum
    target_val_count = max(effective_batch_size, round(total_count * val_ratio))
    target_test_count = max(effective_batch_size, round(total_count * test_ratio))

    train_samples: List[Dict[str, Any]] = []
    val_samples: List[Dict[str, Any]] = []
    test_samples: List[Dict[str, Any]] = []

    # Sort strata deterministically by stratum key
    sorted_strata_keys = sorted(strata.keys())

    # Flatten clusters with their stratum tag for balanced allocation
    # First pass: Allocate within strata where multiple clusters exist
    unassigned_clusters: List[Tuple[Tuple[str, str, str], List[Dict[str, Any]]]] = []

    for stratum_key in sorted_strata_keys:
        clusters = strata[stratum_key]
        rng.shuffle(clusters)

        n_clusters = len(clusters)
        if n_clusters >= 3:
            # Reserve 1 for val, 1 for test, rest for train
            val_samples.extend(clusters[0])
            test_samples.extend(clusters[1])
            for c in clusters[2:]:
                train_samples.extend(c)
        elif n_clusters == 2:
            # 1 to train, 1 unassigned to balance val/test needs
            train_samples.extend(clusters[0])
            unassigned_clusters.append((stratum_key, clusters[1]))
        else:
            # 1 cluster: keep unassigned
            unassigned_clusters.append((stratum_key, clusters[0]))

    # Second pass: allocate unassigned clusters to meet target val/test counts
    rng.shuffle(unassigned_clusters)
    for stratum_key, cluster in unassigned_clusters:
        if len(val_samples) < target_val_count:
            val_samples.extend(cluster)
        elif len(test_samples) < target_test_count:
            test_samples.extend(cluster)
        else:
            train_samples.extend(cluster)

    # In extreme edge cases where train is starved, ensure train has majority
    if len(train_samples) < (total_count // 2):
        while len(val_samples) > target_val_count:
            train_samples.append(val_samples.pop())
        while len(test_samples) > target_test_count:
            train_samples.append(test_samples.pop())

    # Ensure train is not empty; if something went wrong, fall back safely
    if not train_samples:
        train_samples = normalized_samples
        val_samples = []
        test_samples = []

    # Annotate split tags and review metadata on held-out samples
    for s in train_samples:
        s["_split"] = "train"
    for s in val_samples:
        s["_split"] = "validation"
        s["_held_out"] = True
        s["_reviewed"] = True
    for s in test_samples:
        s["_split"] = "test"
        s["_held_out"] = True
        s["_reviewed"] = True

    train_hash = _compute_samples_hash(train_samples)
    val_hash = _compute_samples_hash(val_samples) if val_samples else None
    test_hash = _compute_samples_hash(test_samples) if test_samples else None

    decision = {
        "floor": floor,
        "total_samples": total_count,
        "train_count": len(train_samples),
        "val_count": len(val_samples),
        "test_count": len(test_samples),
        "status": "held_out_carved",
        "flag": None,
        "warning": None,
        "effective_batch_size": effective_batch_size,
        "epochs": epochs,
        "seed": derived_seed,
        "split_version": split_version,
        "job_id": job_id,
        "train_hash": train_hash,
        "val_hash": val_hash,
        "test_hash": test_hash,
    }

    logger.info(
        "[%s] Carved held-out split: %d train, %d val, %d test (total %d)",
        job_id,
        len(train_samples),
        len(val_samples),
        len(test_samples),
        total_count,
    )

    return {
        "train": train_samples,
        "val": val_samples,
        "test": test_samples,
        "decision": decision,
    }


def save_split_artifacts(
    split_result: Dict[str, Any],
    output_dir: Path | str,
    base_filename: str = "dataset.jsonl",
) -> Dict[str, Path]:
    """Persist train file and held-out validation/test splits as job artifacts.

    The primary train file path is kept as base_filename (e.g. dataset.jsonl),
    while val.jsonl and test.jsonl are written as artifacts alongside split_manifest.json.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts: Dict[str, Path] = {}

    # Primary train file
    train_path = out_dir / base_filename
    with open(train_path, "w", encoding="utf-8") as f:
        for s in split_result.get("train", []):
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    artifacts["train"] = train_path

    # Validation artifact
    val_samples = split_result.get("val", [])
    if val_samples:
        val_path = out_dir / "val.jsonl"
        with open(val_path, "w", encoding="utf-8") as f:
            for s in val_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        artifacts["val"] = val_path

    # Test artifact
    test_samples = split_result.get("test", [])
    if test_samples:
        test_path = out_dir / "test.jsonl"
        with open(test_path, "w", encoding="utf-8") as f:
            for s in test_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        artifacts["test"] = test_path

    # Manifest artifact
    manifest_path = out_dir / "split_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(split_result.get("decision", {}), f, indent=2)
    artifacts["manifest"] = manifest_path

    return artifacts
