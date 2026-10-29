"""Both DB import paths resolve to the identical objects.

Canonical: core.async_db / core.migration_safety.
Compatibility shim: db.async_db / db.migration_safety.
"""
import core.async_db
import core.migration_safety
import db.async_db
import db.migration_safety


def test_async_db_paths_identical():
    assert db.async_db.AsyncDatabaseManager is core.async_db.AsyncDatabaseManager
    assert db.async_db.DatabaseConfig is core.async_db.DatabaseConfig


def test_migration_safety_paths_identical():
    assert db.migration_safety.SafeMigrationManager is core.migration_safety.SafeMigrationManager
    assert db.migration_safety.BUILTIN_MIGRATIONS is core.migration_safety.BUILTIN_MIGRATIONS
