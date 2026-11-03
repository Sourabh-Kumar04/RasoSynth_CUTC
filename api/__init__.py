"""AI-Native API System for RasoSynthTune with PEP 562 lazy attribute loading.

Canonical server: api/server.py (started by main.py)
"""
from __future__ import annotations

import importlib
from typing import Any, Optional

__all__ = [
    "ApplicationFactory",
    "get_app_factory",
    "create_app",
    "app",
    "get_app",
]

_SUBMODULE_MAP = {
    "ApplicationFactory": "api.factory",
    "get_app_factory": "api.factory",
    "create_app": "api.factory",
    "app": "api.server",
    "get_app": "api.server",
}


def __getattr__(name: str) -> Any:
    # Check if attribute should be imported from schemas
    if name in _SUBMODULE_MAP:
        mod = importlib.import_module(_SUBMODULE_MAP[name])
        val = getattr(mod, name)
        globals()[name] = val
        return val

    # Try importing from api.schemas
    try:
        schemas_mod = importlib.import_module("api.schemas")
        if hasattr(schemas_mod, name):
            val = getattr(schemas_mod, name)
            globals()[name] = val
            return val
    except Exception:
        pass

    # Try importing from api.validation
    try:
        val_mod = importlib.import_module("api.validation")
        if hasattr(val_mod, name):
            val = getattr(val_mod, name)
            globals()[name] = val
            return val
    except Exception:
        pass

    # Try importing from api.planning
    try:
        plan_mod = importlib.import_module("api.planning")
        if hasattr(plan_mod, name):
            val = getattr(plan_mod, name)
            globals()[name] = val
            return val
    except Exception:
        pass

    # Try importing from api.observability.metrics
    try:
        obs_mod = importlib.import_module("api.observability.metrics")
        if hasattr(obs_mod, name):
            val = getattr(obs_mod, name)
            globals()[name] = val
            return val
    except Exception:
        pass

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + list(_SUBMODULE_MAP.keys()))
