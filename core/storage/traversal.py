"""Path traversal and identifier validation helpers for storage callers."""
import os
import re
from pathlib import Path
from typing import Union

# Whitelist safe identifier characters: alphanumerics, underscores, hyphens, and dots
SAFE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def validate_identifier(identifier: str, allow_empty: bool = False) -> str:
    """Validate and sanitize a resource identifier (job_id, dataset_id, task_id).

    Rejects paths containing '/' or '..', leading/trailing whitespace,
    and characters outside [a-zA-Z0-9_.-].
    """
    if identifier is None:
        if allow_empty:
            return ""
        raise ValueError("Identifier cannot be None")
    
    clean_id = str(identifier).strip()
    if not clean_id:
        if allow_empty:
            return ""
        raise ValueError("Identifier cannot be empty")
        
    if "/" in clean_id or "\\" in clean_id or ".." in clean_id:
        raise ValueError(f"Path traversal characters detected in identifier: {identifier!r}")
        
    if not SAFE_ID_REGEX.match(clean_id):
        raise ValueError(f"Identifier contains invalid characters: {identifier!r}")
        
    return clean_id


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing path separators and directory traversal sequences."""
    if not filename:
        raise ValueError("Filename cannot be empty")
    # Take basename first to drop any path prefix
    base = os.path.basename(str(filename).strip().replace("\\", "/"))
    # Strip any remaining .. or control chars
    base = base.replace("..", "").strip()
    if not base or base in (".", ".."):
        raise ValueError(f"Invalid filename resulting after sanitization: {filename!r}")
    return base


def ensure_contained_path(path: Union[str, Path], allowed_root: Union[str, Path]) -> Path:
    """Ensure that `path` resolves to a location within `allowed_root`.

    Raises ValueError if path attempts to escape the root boundary.
    """
    root_resolved = Path(allowed_root).resolve()
    target_resolved = Path(path).resolve()

    try:
        target_resolved.relative_to(root_resolved)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: {path!r} resolves to {target_resolved} "
            f"which is outside allowed root {root_resolved}"
        )
    return target_resolved
