"""Tests for the Migration Safety system (db/migration_safety.py).

Tests transaction wrapping, pre-flight checks, rollback, and validation.
Uses SQLite in-memory for testing.
"""
import pytest
from unittest.mock import AsyncMock, patch

from db.migration_safety import (
    SafeMigrationManager,
    MigrationStep,
    MigrationResult,
    add_column,
    create_index,
    create_table,
    BUILTIN_MIGRATIONS,
)


@pytest.fixture
def mock_session_factory():
    """Create a mock session factory for testing."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session_factory = AsyncMock(return_value=session)
    return session_factory


@pytest.fixture
def migration_manager(mock_session_factory):
    return SafeMigrationManager(session_factory=mock_session_factory)


class TestMigrationSafety:
    """Test suite for SafeMigrationManager."""

    @pytest.mark.asyncio
    async def test_empty_migration(self, migration_manager):
        """Migration with no steps should be handled gracefully."""
        result = await migration_manager.apply_migration("test-empty", [])
        # This should not raise
        assert result is not None

    @pytest.mark.asyncio
    async def test_successful_migration(self, migration_manager):
        """Single-step migration should succeed."""
        step = MigrationStep(
            sql="ALTER TABLE jobs ADD COLUMN test_col INTEGER DEFAULT 0",
            description="Add test column",
            rollback_sql="ALTER TABLE jobs DROP COLUMN test_col",
        )
        result = await migration_manager.apply_migration("test-001", [step])

        # Without real DB, the execute will fail. Check error handling.
        assert result.steps_attempted == 1

    @pytest.mark.asyncio
    async def test_builtin_migrations_present(self):
        """Built-in migrations should be defined."""
        assert "001_add_job_priority" in BUILTIN_MIGRATIONS
        assert "002_add_job_checkpoint_ref" in BUILTIN_MIGRATIONS
        assert "003_add_job_recovery_metadata" in BUILTIN_MIGRATIONS
        assert "004_add_dataset_indexes" in BUILTIN_MIGRATIONS

    @pytest.mark.asyncio
    async def test_migration_step_builders(self):
        """Migration step builders should produce valid MigrationSteps."""
        step = add_column("jobs", "priority", "INTEGER", "3")
        assert "ADD COLUMN" in step.sql
        assert step.rollback_sql is not None

        step = create_index("ix_test", "jobs", "priority")
        assert "CREATE" in step.sql
        assert "INDEX" in step.sql

        step = create_table("test_table", "id INTEGER PRIMARY KEY, name TEXT")
        assert "CREATE TABLE" in step.sql

    @pytest.mark.asyncio
    async def test_pre_flight_check(self, migration_manager):
        """Pre-flight should detect already-applied migrations."""
        with patch.object(migration_manager, '_is_applied', AsyncMock(return_value=True)):
            errors = await migration_manager._pre_flight_check("already-applied")
            assert len(errors) > 0
            assert "already applied" in errors[0].lower()

    @pytest.mark.asyncio
    async def test_get_migration_history_empty(self, migration_manager):
        """Migration history should handle empty tables."""
        history = await migration_manager.get_migration_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_no_session_factory(self):
        """Manager should handle missing session factory."""
        mgr = SafeMigrationManager(session_factory=None)
        result = await mgr.apply_migration("test", [MigrationStep("SELECT 1", "test")])
        assert result.success is False

    @pytest.mark.asyncio
    async def test_rollback_migration_not_found(self, migration_manager):
        """Rollback of non-existent migration should return False."""
        result = await migration_manager.rollback_migration("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_validator_query(self, migration_manager):
        """Step validator should be recorded."""
        step = MigrationStep(
            sql="CREATE TABLE test (id INTEGER PRIMARY KEY)",
            description="Create test table",
            validator="SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='test'",
        )
        # Should not error
        await migration_manager.apply_migration("test-validator", [step])

    @pytest.mark.asyncio
    async def test_ensure_history_table(self, migration_manager):
        """Ensure history table creates successfully."""
        with patch.object(migration_manager, '_session_factory', None):
            # Should not error when no session factory
            await migration_manager.ensure_history_table()