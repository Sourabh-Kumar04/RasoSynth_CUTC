"""
Compatibility shim for the historical db package name.

Canonical home of these modules is core (core.async_db,
core.migration_safety). This package re-exports the identical objects
so existing imports keep working unchanged.
"""
from core.migration_safety import (
    SafeMigrationManager,
    MigrationStep,
    MigrationResult,
    add_column,
    create_index,
    create_table,
    BUILTIN_MIGRATIONS,
)
from core.async_db import AsyncDatabaseManager, DatabaseConfig

__all__ = [
    "SafeMigrationManager",
    "MigrationStep",
    "MigrationResult",
    "add_column",
    "create_index",
    "create_table",
    "BUILTIN_MIGRATIONS",
    "AsyncDatabaseManager",
    "DatabaseConfig",
]
