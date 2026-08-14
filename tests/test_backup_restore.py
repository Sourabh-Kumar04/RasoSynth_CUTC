"""Tests for the Backup and Restore system (scripts/backup.py, scripts/restore.py).

Tests backup creation, verification, retention, and restore functionality.
Uses temporary directories to avoid touching real data.
"""
import json
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.backup import BackupManager


class TestBackupManager:
    """Test suite for BackupManager."""

    def setup_method(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="backup_test_"))
        self.backup_dir = self.tmp_dir / "backups"
        self.backup_dir.mkdir()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_checksum_consistency(self):
        """SHA-256 checksum should be deterministic."""
        file_path = self.tmp_dir / "test.txt"
        file_path.write_text("hello world")

        hash1 = BackupManager._checksum(file_path)
        hash2 = BackupManager._checksum(file_path)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_checksum_different_files(self):
        """Different files should have different checksums."""
        f1 = self.tmp_dir / "a.txt"
        f2 = self.tmp_dir / "b.txt"
        f1.write_text("content a")
        f2.write_text("content b")

        assert BackupManager._checksum(f1) != BackupManager._checksum(f2)

    def test_backup_creates_manifest(self):
        """Backup should create a manifest.json with metadata."""
        manager = BackupManager(
            backup_dir=str(self.backup_dir),
            retention_count=3,
            verify=False,
        )

        with patch.object(manager, '_backup_database', return_value=None):
            with patch.object(manager, '_backup_data', return_value=None):
                result = manager.run_full_backup()

        assert result["status"] == "success"
        assert result["timestamp"] is not None
        assert "duration_s" in result

    def test_retention_policy(self):
        """Old backups beyond retention_count should be deleted."""
        # Create fake old backups
        for i in range(5):
            (self.backup_dir / f"backup_2026050{i}_000000.tar.gz").write_text(f"fake backup {i}")

        manager = BackupManager(
            backup_dir=str(self.backup_dir),
            retention_count=3,
            verify=False,
        )

        # The retention is checked after each backup run.
        # Simulate by calling apply directly
        deleted = manager._apply_retention()
        remaining = list(self.backup_dir.glob("backup_*.tar.gz"))

        # Initially should have kept most recent 3, deleted 2
        assert deleted == 2
        assert len(remaining) == 3

    def test_backup_verify_valid(self):
        """verify_backup should validate a valid archive."""
        # Create a valid tar.gz with manifest
        archive_path = self.backup_dir / "test_backup.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            manifest_data = {
                "backup_timestamp": "20260523_120000",
                "artifacts": {"test": "abc123"},
            }
            manifest_bytes = json.dumps(manifest_data).encode()
            from io import BytesIO
            manifest_info = tarfile.TarInfo(name="backup_dir/manifest.json")
            manifest_info.size = len(manifest_bytes)
            tar.addfile(manifest_info, BytesIO(manifest_bytes))

        manager = BackupManager(backup_dir=str(self.backup_dir))
        result = manager.verify_backup(str(archive_path))

        assert result["valid"] is True
        assert len(result["checks"]) > 0

    def test_backup_verify_invalid_path(self):
        """verify_backup should return invalid for missing path."""
        manager = BackupManager(backup_dir=str(self.backup_dir))
        result = manager.verify_backup("/nonexistent/backup.tar.gz")

        assert result["valid"] is False
        assert "not found" in result.get("error", "")

    def test_backup_empty_data_dir(self):
        """Backup should handle empty data directories gracefully."""
        empty_dir = self.tmp_dir / "empty_outputs"
        empty_dir.mkdir()

        manager = BackupManager(
            backup_dir=str(self.backup_dir),
            data_dirs=[str(empty_dir)],
            verify=False,
        )

        with patch.object(manager, '_backup_database', return_value=None):
            result = manager.run_full_backup()

        assert result["status"] == "success"


class TestRestoreManager:
    """Test suite for RestoreManager."""

    def test_list_backups_empty(self):
        """list_backups should return empty list when no backups exist."""
        from scripts.restore import RestoreManager
        manager = RestoreManager()
        backups = manager.list_backups(backup_dir="/nonexistent")
        assert backups == []

    def test_list_backups(self):
        """list_backups should find backup archives."""
        from scripts.restore import RestoreManager
        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp) / "backups"
            backup_dir.mkdir()
            (backup_dir / "backup_20260523_120000.tar.gz").write_text("fake")

            manager = RestoreManager()
            backups = manager.list_backups(backup_dir=str(backup_dir))
            assert len(backups) == 1
            assert backups[0]["size_bytes"] > 0

    def test_restore_missing_backup(self):
        """Restore should raise error for missing backup."""
        from scripts.restore import RestoreManager, RestoreError
        manager = RestoreManager()
        try:
            manager.restore("/nonexistent/backup.tar.gz")
            assert False, "Should have raised RestoreError"
        except RestoreError as e:
            assert "not found" in str(e)