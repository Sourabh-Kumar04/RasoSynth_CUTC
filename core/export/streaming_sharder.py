"""Streaming Multi-File Dataset Sharder & Compression Engine.

Partitions high-volume synthetic datasets into standard Hugging Face/PyTorch
sharded chunks with SHA-256 checksums and dataset_info manifest metadata.
"""

import gzip
import hashlib
import json
import math
from typing import Any, Dict, List, Optional


def shard_dataset_records(
    samples: List[Dict[str, Any]],
    shard_size: int = 1000,
    prefix: str = "train",
    compress: bool = False,
) -> Dict[str, Any]:
    """Partition dataset into numbered shards with integrity checksums."""
    if not samples:
        return {
            "total_samples": 0,
            "shard_count": 0,
            "shards": [],
            "manifest": {},
        }

    total_samples = len(samples)
    num_shards = max(1, math.ceil(total_samples / shard_size))
    shards_meta = []

    for s_idx in range(num_shards):
        start = s_idx * shard_size
        end = min(start + shard_size, total_samples)
        chunk = samples[start:end]

        shard_filename = f"{prefix}-{s_idx:05d}-of-{num_shards:05d}.jsonl"
        if compress:
            shard_filename += ".gz"

        # Serialize chunk to JSONL
        jsonl_lines = [json.dumps(rec, ensure_ascii=False) for rec in chunk]
        raw_bytes = ("\n".join(jsonl_lines) + "\n").encode("utf-8")

        if compress:
            payload_bytes = gzip.compress(raw_bytes)
        else:
            payload_bytes = raw_bytes

        sha256 = hashlib.sha256(payload_bytes).hexdigest()

        shards_meta.append({
            "shard_index": s_idx,
            "filename": shard_filename,
            "record_count": len(chunk),
            "byte_size": len(payload_bytes),
            "sha256_checksum": sha256,
            "is_compressed": compress,
        })

    manifest = {
        "dataset_name": f"{prefix}_sharded_corpus",
        "total_records": total_samples,
        "total_shards": num_shards,
        "shard_size_target": shard_size,
        "format": "jsonl.gz" if compress else "jsonl",
        "total_bytes": sum(s["byte_size"] for s in shards_meta),
        "files": [s["filename"] for s in shards_meta],
    }

    return {
        "total_samples": total_samples,
        "shard_count": num_shards,
        "shards": shards_meta,
        "manifest": manifest,
    }
