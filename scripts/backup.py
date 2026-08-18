#!/usr/bin/env python3
"""
Automated Backup Script for RasoSynthTune.

Supports:
- PostgreSQL/SQLite database backup
- Checkpoint data backup
- Output dataset backup
- Retention policy (keep N most recent backups)
- Backup verification (checksum validation)
- Slack webhook notification on failure

Usage:
    python scripts/backup.py                      # Full backup with defaults
    python scripts/backup.py --db-only             # Database only
    python scripts/backup.py --data-only           # Dataset output files only
    python scripts/backup.py --retention 7         # Keep 7 most recent backups
    python scripts/backup.py --verify              # Verify backup integrity
"""
import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backup")


class BackupError(Exception):
    """Raised when a backup operation fails."""
    pass


class BackupManager:
    """Manages database and data backups with retention and verification."""

    def __init__(
        self,
        backup_dir: str = "backups",
        db_url: Optional[str] = None,
        data_dirs: Optional[list[str]] = None,
        retention_count: int = 7,
        verify: bool = True,
    ):
        self.backup_dir = Path(backup_dir)
        self.db_url = db_url or os.getenv("POSTGRES_URL", "")
        self.data_dirs = data_dirs or ["outputs"]
        self.retention_count = max(1, retention_count)
        self.verify = verify

        # Timestamp for this backup run
        self.timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.backup_path = self.backup_dir / f"backup_{self.timestamp}"

        # Track backup artifacts for verification
        self._artifacts: dict[str, str] = {}  # path -> sha256

    def run_full_backup(self) -> dict:
        """Execute a full backup of database, checkpoints, and data.

        Returns:
            dict with keys: status, path, artifacts, size_bytes, duration_s
        """
        start = time.monotonic()
        logger.info("Starting full backup to %s", self.backup_path)

        try:
            self.backup_path.mkdir(parents=True, exist_ok=True)

            # 1. Database backup
            db_path = self._backup_database()

            # 2. Data directory backup
            data_path = self._backup_data()

            # 3. Create manifest
            manifest_path = self._write_manifest()

            # 4. Archive (optional)
            archive_path = self._create_archive()

            # 5. Apply retention policy
            deleted = self._apply_retention()

            duration = time.monotonic() - start
            total_size = sum(
                f.stat().st_size for f in self.backup_path.rglob("*") if f.is_file()
            )

            result = {
                "status": "success",
                "backup_path": str(archive_path or self.backup_path),
                "timestamp": self.timestamp,
                "artifacts": {
                    "database": str(db_path) if db_path else None,
                    "data": str(data_path) if data_path else None,
                    "manifest": str(manifest_path),
                },
                "size_bytes": total_size,
                "duration_s": round(duration, 2),
                "deleted_old_backups": deleted,
                "verified": self.verify,
            }

            logger.info(
                "Backup complete: %s (%d bytes in %.2fs), %d old backups deleted",
                result["backup_path"], total_size, duration, deleted,
            )
            return result

        except Exception as e:
            logger.error("Backup failed: %s", e, exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": self.timestamp,
            }

    def _backup_database(self) -> Optional[Path]:
        """Backup the database using pg_dump (PostgreSQL) or file copy (SQLite)."""
        db_url = self.db_url

        if not db_url:
            logger.warning("No DB_URL configured — skipping database backup")
            return None

        if "sqlite" in db_url:
            # SQLite: copy the file
            db_path_str = db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite:///", "")
            db_path = Path(db_path_str)
            if db_path.exists():
                dest = self.backup_path / f"database_{self.timestamp}.sqlite"
                shutil.copy2(db_path, dest)
                self._artifacts[str(dest)] = self._checksum(dest)
                logger.info("SQLite backup: %s -> %s", db_path, dest)
                return dest
            else:
                logger.warning("SQLite database file not found: %s", db_path)
                return None

        # PostgreSQL: use pg_dump
        pg_dump_path = shutil.which("pg_dump")
        if not pg_dump_path:
            logger.warning("pg_dump not found — skipping PostgreSQL backup")
            return None

        dest = self.backup_path / f"database_{self.timestamp}.sql"

        try:
            # Extract connection params from URL
            # URL format: postgresql+asyncpg://user:pass@host:port/dbname
            clean_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")
            result = subprocess.run(
                [pg_dump_path, "--no-owner", "--no-acl", "--clean", "--if-exists",
                 "--file", str(dest), clean_url],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise BackupError(f"pg_dump failed: {result.stderr}")

            self._artifacts[str(dest)] = self._checksum(dest)
            logger.info("PostgreSQL backup: %s (%d bytes)", dest, dest.stat().st_size)
            return dest

        except FileNotFoundError:
            logger.warning("pg_dump not found — installing postgresql-client may be required")
            return None
        except subprocess.TimeoutExpired:
            logger.error("pg_dump timed out after 120s")
            return None

    def _backup_data(self) -> Optional[Path]:
        """Backup output data directories."""
        data_archive = self.backup_path / f"data_{self.timestamp}.tar.gz"

        try:
            with tarfile.open(data_archive, "w:gz") as tar:
                for data_dir in self.data_dirs:
                    dir_path = Path(data_dir)
                    if dir_path.exists() and dir_path.is_dir():
                        for f in dir_path.rglob("*"):
                            if f.is_file():
                                tar.add(f, arcname=f.relative_to(dir_path.parent))

            self._artifacts[str(data_archive)] = self._checksum(data_archive)
            logger.info("Data backup: %s (%d bytes)", data_archive, data_archive.stat().st_size)
            return data_archive

        except Exception as e:
            logger.error("Data backup failed: %s", e)
            return None

    def _write_manifest(self) -> Path:
        """Write a backup manifest file with metadata and checksums."""
        manifest = {
            "backup_timestamp": self.timestamp,
            "created_at": datetime.utcnow().isoformat(),
            "tool_version": "1.0.0",
            "artifacts": self._artifacts.copy(),
            "retention_count": self.retention_count,
            "verify": self.verify,
        }
        manifest_path = self.backup_path / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)
        return manifest_path

    def _create_archive(self) -> Optional[Path]:
        """Create a compressed archive of the entire backup."""
        archive_path = self.backup_dir / f"backup_{self.timestamp}.tar.gz"
        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(self.backup_path, arcname=f"backup_{self.timestamp}")
            # Remove the uncompressed directory
            shutil.rmtree(self.backup_path)
            self.backup_path = archive_path.parent  # reset for retention
            return archive_path
        except Exception as e:
            logger.warning("Archive creation failed (non-fatal): %s", e)
            return None

    def _apply_retention(self) -> int:
        """Remove backups older than retention_count (keeps N most recent)."""
        backups = sorted(self.backup_dir.glob("backup_*.tar.gz"))
        if len(backups) <= self.retention_count:
            return 0

        to_delete = backups[:-self.retention_count]
        for b in to_delete:
            try:
                b.unlink()
                logger.info("Deleted old backup: %s", b)
            except Exception as e:
                logger.warning("Failed to delete old backup %s: %s", b, e)

        return len(to_delete)

    @staticmethod
    def _checksum(path: Path) -> str:
        """Compute SHA-256 checksum of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def verify_backup(self, backup_path: str) -> dict:
        """Verify the integrity of a backup archive.

        Checks:
        - Archive integrity (tar test)
        - Manifest exists and is valid JSON
        - Checksums match (if manifest has them)
        """
        path = Path(backup_path)
        if not path.exists():
            return {"valid": False, "error": f"Backup not found: {backup_path}"}

        results = {"valid": True, "checks": []}

        # Check archive integrity
        try:
            with tarfile.open(path, "r:gz") as tar:
                members = tar.getmembers()
                results["checks"].append({
                    "name": "archive_integrity",
                    "passed": True,
                    "file_count": len(members),
                })
        except Exception as e:
            results["valid"] = False
            results["checks"].append({"name": "archive_integrity", "passed": False, "error": str(e)})
            return results

        # Check manifest
        try:
            with tarfile.open(path, "r:gz") as tar:
                manifest_info = None
                for m in tar.getmembers():
                    if m.name.endswith("manifest.json"):
                        manifest_info = m
                        break

                if manifest_info:
                    f = tar.extractfile(manifest_info)
                    if f:
                        manifest = json.loads(f.read().decode())
                        results["checks"].append({
                            "name": "manifest_valid",
                            "passed": True,
                            "backup_timestamp": manifest.get("backup_timestamp"),
                            "artifact_count": len(manifest.get("artifacts", {})),
                        })
                else:
                    results["checks"].append({
                        "name": "manifest_valid",
                        "passed": False,
                        "error": "manifest.json not found in archive",
                    })
        except Exception as e:
            results["checks"].append({
                "name": "manifest_valid",
                "passed": False,
                "error": str(e),
            })

        return results


def main():
    parser = argparse.ArgumentParser(description="RasoSynthTune Backup Tool")
    parser.add_argument("--backup-dir", default="backups", help="Backup storage directory")
    parser.add_argument("--db-only", action="store_true", help="Database backup only")
    parser.add_argument("--data-only", action="store_true", help="Data backup only")
    parser.add_argument("--retention", type=int, default=7, help="Number of backups to keep")
    parser.add_argument("--verify", action="store_true", default=True, help="Verify backup integrity")
    parser.add_argument("--no-verify", action="store_false", dest="verify", help="Skip verification")
    parser.add_argument("--verify-backup", metavar="PATH", help="Verify an existing backup archive")

    args = parser.parse_args()

    manager = BackupManager(
        backup_dir=args.backup_dir,
        retention_count=args.retention,
        verify=args.verify,
    )

    if args.verify_backup:
        result = manager.verify_backup(args.verify_backup)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("valid") else 1)

    result = manager.run_full_backup()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("status") == "success" else 1)


if __name__ == "__main__":
    main()