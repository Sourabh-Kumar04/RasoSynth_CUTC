"""
Compatibility shim for db.async_db.

Canonical implementation lives in core.async_db; this module
re-exports the identical objects.
"""
from core.async_db import AsyncDatabaseManager, DatabaseConfig

__all__ = ["AsyncDatabaseManager", "DatabaseConfig"]
