"""Canonical environment resolution for RasoSynthTune.

Resolves the active runtime environment using ENVIRONMENT as the canonical
variable, with AI_DATASET_ENVIRONMENT supported only as a deprecated fallback
alias that emits a warning.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

CANONICAL_ENV_VAR = "ENVIRONMENT"
DEPRECATED_ENV_VAR = "AI_DATASET_ENVIRONMENT"


def get_current_environment(default: str = "development") -> str:
    """Return the normalized runtime environment string (e.g. 'development', 'production', 'staging').

    ENVIRONMENT is the canonical environment variable.
    If only AI_DATASET_ENVIRONMENT is set, a deprecation warning is logged
    and its value is used to preserve backwards compatibility.
    """
    canonical_val = os.getenv(CANONICAL_ENV_VAR)
    if canonical_val is not None and canonical_val.strip():
        return canonical_val.strip().lower()

    deprecated_val = os.getenv(DEPRECATED_ENV_VAR)
    if deprecated_val is not None and deprecated_val.strip():
        logger.warning(
            "Deprecated environment variable %s is set (%r). "
            "Please migrate to canonical %s.",
            DEPRECATED_ENV_VAR,
            deprecated_val,
            CANONICAL_ENV_VAR,
        )
        return deprecated_val.strip().lower()

    return default.strip().lower()


def is_production() -> bool:
    """Return True if running in production or production-like environment."""
    return get_current_environment() in ("production", "gpu_cluster", "staging")
