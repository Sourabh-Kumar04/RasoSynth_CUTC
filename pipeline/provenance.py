"""Minimal, portable provenance records for generated training examples."""

from __future__ import annotations

import hashlib
from typing import Any


def attach_provenance(sample: dict[str, Any]) -> dict[str, Any]:
    """Normalize source evidence without retaining more source text than needed.

    The current storage layer keeps an excerpt on the sample. This creates a
    stable evidence identifier and a citation span over that excerpt, so export
    and review code have one predictable provenance contract.
    """
    metadata = sample.setdefault("metadata", {})
    existing = metadata.get("provenance")
    if isinstance(existing, dict):
        return existing

    source_url = str(metadata.get("source_url") or sample.get("source_url") or "").strip()
    source_text = str(sample.get("source_text") or "")
    source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest() if source_text else ""
    license_name = str(metadata.get("license") or sample.get("license") or "").strip()

    if source_url:
        record = {
            "kind": "source",
            "source_url": source_url,
            "source_hash": source_hash,
            "license": license_name or None,
            "citations": ([{"start": 0, "end": len(source_text)}] if source_text else []),
        }
    elif metadata.get("anchor_sample"):
        record = {"kind": "user_anchor", "source_hash": source_hash, "citations": []}
    else:
        record = {"kind": "synthetic", "source_hash": source_hash or None, "citations": []}

    metadata["provenance"] = record
    return record


def has_reference_provenance(sample: dict[str, Any]) -> bool:
    """Whether an example has a usable external source and citation span."""
    provenance = attach_provenance(sample)
    return bool(
        provenance.get("kind") == "source"
        and provenance.get("source_url")
        and provenance.get("citations")
    )
