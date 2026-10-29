"""
Compatibility shim for db.migration_safety.

Canonical implementation lives in core.migration_safety; this module
re-exports the identical objects.
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

__all__ = [
    "SafeMigrationManager",
    "MigrationStep",
    "MigrationResult",
    "add_column",
    "create_index",
    "create_table",
    "BUILTIN_MIGRATIONS",
]
