"""Dynamic filesystem discovery for datasets and artifacts without path traversal."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def resolve_dynamic_disk_dataset(identifier: str) -> Optional[dict]:
    """Dynamically scan configured output directories without path traversal or substring matching."""
    raw_ident = identifier.strip()
    candidate_roots = [Path("outputs").resolve(), Path("data").resolve()]

    # If identifier is a path, ensure it is strictly contained within allowed roots
    try:
        p = Path(raw_ident).resolve()
        is_safe = any(p == root or root in p.parents for root in candidate_roots)
        if is_safe and p.exists() and p.is_file():
            ext = p.suffix.lstrip(".").lower()
            return {
                "id": p.stem,
                "name": p.stem,
                "type": ext,
                "output_path": str(p),
                "dir": p.parent,
            }
    except Exception:
        pass

    target = Path(raw_ident).name.lower()
    clean_target = Path(raw_ident).stem.lower()

    for root in candidate_roots:
        if not root.exists():
            continue
        # Direct folder or file match ONLY - strictly EXACT match, no substring matching
        for item in root.glob("*"):
            norm_name = item.name.lower()
            norm_stem = item.stem.lower()
            if target == norm_name or clean_target == norm_stem or clean_target == norm_name:
                if item.is_dir():
                    # Look for data files inside
                    for ext in ("jsonl", "parquet", "csv", "xml", "json"):
                        matches = list(item.glob(f"*.{ext}"))
                        if matches:
                            return {
                                "id": item.name,
                                "name": item.name,
                                "type": ext,
                                "output_path": str(matches[0]),
                                "dir": item,
                            }
                elif item.is_file():
                    ext = item.suffix.lstrip(".").lower()
                    return {
                        "id": item.stem,
                        "name": item.stem,
                        "type": ext,
                        "output_path": str(item),
                        "dir": item.parent,
                    }
    return None


_resolve_dynamic_disk_dataset = resolve_dynamic_disk_dataset
