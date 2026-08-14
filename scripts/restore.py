#!/usr/bin/env python3
"""
Restore Script for RasoDataset-Agent.

Supports restoring from backups created by scripts/backup.py.

Usage:
    python scripts/restore.py backups/backup_20260523_120000.tar.gz
    python scripts/restore.py backups/backup_20260523_120000.tar.gz --db-only
    python scripts/restore.py backups/backup_20260523_120000.tar.gz --data-only
    python scripts/restore.py backups/backup_20260523_120000.tar.gz --dry-run
    python scripts/restore.py --list  # List available backups
"""
import argparse
import json
import logging
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("restore")


class RestoreError(Exception):
    """Raised when a restore operation fails."""
    pass


class RestoreManager:
    """Manages restoration of database and data from backups."""

    def __init__(
        self,
        db_url: Optional[str] = None,
        data_dir: str = "outputs",
        dry_run: bool = False,
    ):
        self.db_url = db_url or ""
        self.data_dir = Path(data_dir)
        self.dry_run = dry_run

    def list_backups(self, backup_dir: str = "backups") -> list[dict]:
        """List available backups with metadata."""
        backups = []
        path = Path(backup_dir)
        if not path.exists():
            return backups

        for f in sorted(path.glob("backup_*.tar.gz")):
            info = {"path": str(f), "size_bytes": f.stat().st_size, "modified": f.stat().st_mtime}
            # Try to extract manifest info
            try:
                with tarfile.open(f, "r:gz") as tar:
                    for m in tar.getmembers():
                        if m.name.endswith("manifest.json"):
                            manifest_file = tar.extractfile(m)
                            if manifest_file:
                                manifest = json.loads(manifest_file.read().decode())
                                info["timestamp"] = manifest.get("backup_timestamp")
                                info["artifact_count"] = len(manifest.get("artifacts", {}))
                                break
            except Exception:
                pass
            backups.append(info)

        return backups

    def restore(self, backup_path: str, restore_db: bool = True, restore_data: bool = True) -> dict:
        """Restore from a backup archive.

        Args:
            backup_path: Path to the backup tar.gz archive
            restore_db: Whether to restore the database
            restore_data: Whether to restore data directories

        Returns:
            dict with status, restored_artifacts, and errors
        """
        path = Path(backup_path)
        if not path.exists():
            raise RestoreError(f"Backup not found: {backup_path}")

        logger.info("Starting restore from %s", backup_path)
        if self.dry_run:
            logger.info("DRY RUN — no changes will be made")

        extract_dir = Path(tempfile.mkdtemp(prefix="restore_"))
        results = {"status": "success", "restored": [], "skipped": []}

        try:
            with tarfile.open(path, "r:gz") as tar:
                tar.extractall(path=extract_dir)

            # Find the backup directory within the extraction
            backup_contents = list(extract_dir.iterdir())
            if not backup_contents:
                raise RestoreError("Empty backup archive")
            backup_content_dir = backup_contents[0]  # The backup_<timestamp> dir

            # Check manifest
            manifest_path = backup_content_dir / "manifest.json"
            manifest = {}
            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
                logger.info("Backup manifest: %s", manifest.get("backup_timestamp", "unknown"))

            # Restore database
            if restore_db:
                db_files = list(backup_content_dir.glob("database_*"))
                if db_files:
                    db_file = db_files[0]
                    result = self._restore_database(db_file)
                    results["restored"].append(result)
                else:
                    results["skipped"].append({"artifact": "database", "reason": "not found in backup"})

            # Restore data
            if restore_data:
                data_files = list(backup_content_dir.glob("data_*"))
                if data_files:
                    data_file = data_files[0]
                    result = self._restore_data(data_file)
                    results["restored"].append(result)
                else:
                    results["skipped"].append({"artifact": "data", "reason": "not found in backup"})

            logger.info("Restore complete")
            return results

        except Exception as e:
            logger.error("Restore failed: %s", e, exc_info=True)
            return {"status": "failed", "error": str(e)}

        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)

    def _restore_database(self, db_file: Path) -> dict:
        """Restore the database from a backup file."""
        if self.dry_run:
            return {"artifact": "database", "file": str(db_file), "action": "skipped (dry run)"}

        if db_file.suffix == ".sqlite":
            dest = Path(self.db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite:///", ""))
            shutil.copy2(db_file, dest)
            logger.info("SQLite database restored: %s -> %s", db_file, dest)
            return {"artifact": "database", "file": str(db_file), "action": "restored", "type": "sqlite"}

        if db_file.suffix == ".sql":
            clean_url = self.db_url.replace("+asyncpg", "").replace("+psycopg2", "")
            psql_path = shutil.which("psql")
            if not psql_path:
                raise RestoreError("psql not found — cannot restore PostgreSQL database")

            result = subprocess.run(
                [psql_path, "--quiet", "--file", str(db_file), clean_url],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                raise RestoreError(f"psql restore failed: {result.stderr}")

            logger.info("PostgreSQL database restored from %s", db_file)
            return {"artifact": "database", "file": str(db_file), "action": "restored", "type": "postgresql"}

        return {"artifact": "database", "file": str(db_file), "action": "skipped", "reason": f"unknown format: {db_file.suffix}"}

    def _restore_data(self, data_file: Path) -> dict:
        """Restore data directories from a backup archive."""
        if self.dry_run:
            return {"artifact": "data", "file": str(data_file), "action": "skipped (dry run)"}

        self.data_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(data_file, "r:gz") as tar:
            tar.extractall(path=self.data_dir.parent)

        logger.info("Data restored from %s to %s", data_file, self.data_dir)
        return {"artifact": "data", "file": str(data_file), "action": "restored"}


def main():
    parser = argparse.ArgumentParser(description="RasoDataset-Agent Restore Tool")
    parser.add_argument("backup_path", nargs="?", help="Path to backup archive")
    parser.add_argument("--db-only", action="store_true", help="Restore database only")
    parser.add_argument("--data-only", action="store_true", help="Restore data only")
    parser.add_argument("--dry-run", action="store_true", help="Preview restore without changes")
    parser.add_argument("--list", action="store_true", help="List available backups")

    args = parser.parse_args()

    manager = RestoreManager(dry_run=args.dry_run)

    if args.list:
        backups = manager.list_backups()
        if not backups:
            print("No backups found")
            sys.exit(0)
        print(f"{'Backup Path':<60} {'Size':>10} {'Timestamp':<20}")
        print("-" * 90)
        for b in backups:
            size_mb = b["size_bytes"] / (1024 * 1024)
            ts = b.get("timestamp", "unknown")
            print(f"{b['path']:<60} {size_mb:>8.1f}MB {ts:<20}")
        sys.exit(0)

    if not args.backup_path:
        parser.print_help()
        sys.exit(1)

    try:
        result = manager.restore(
            backup_path=args.backup_path,
            restore_db=not args.data_only,
            restore_data=not args.db_only,
        )
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("status") == "success" else 1)
    except Exception as e:
        logger.error("Restore failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()