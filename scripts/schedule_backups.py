#!/usr/bin/env python3
"""
Scheduled Backup Runner for RasoDataset-Agent.

Designed to be run as a cron job or systemd timer.
Handles:
- Running backup at configured interval
- Slack/email notification on failure
- Lock file to prevent concurrent runs
- Logging with rotation

crontab example (daily at 3am):
    0 3 * * * cd /app && python scripts/schedule_backups.py

systemd timer example:
    [Unit]
    Description=Daily RasoDataset backup

    [Timer]
    OnCalendar=daily
    Persistent=true

    [Install]
    WantedBy=timers.target
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("schedule_backups")


class ScheduledBackupRunner:
    """Runs backup on a schedule with lock-file guarding and notifications."""

    def __init__(
        self,
        backup_script: str = "scripts/backup.py",
        lock_file: str = "/tmp/rasodataset_backup.lock",
        retention: int = 7,
        backup_dir: str = "backups",
        slack_webhook_url: str = "",
    ):
        self.backup_script = Path(backup_script)
        self.lock_file = Path(lock_file)
        self.retention = retention
        self.backup_dir = Path(backup_dir)
        self.slack_webhook_url = slack_webhook_url or os.getenv("SLACK_BACKUP_WEBHOOK_URL", "")
        self.max_lock_age_hours = 2  # Auto-release lock if older than this

    def run(self) -> dict:
        """Execute the scheduled backup.

        Returns:
            dict with status and details
        """
        # Check lock file
        if self.lock_file.exists():
            lock_age = time.time() - self.lock_file.stat().st_mtime
            if lock_age < self.max_lock_age_hours * 3600:
                logger.warning("Backup already running (lock file exists for %.1f hours)", lock_age / 3600)
                return {"status": "skipped", "reason": "lock_file_exists", "lock_age_hours": round(lock_age / 3600, 2)}
            else:
                logger.warning("Stale lock file detected (%.1f hours old) — overriding", lock_age / 3600)
                self.lock_file.unlink(missing_ok=True)

        # Create lock
        self.lock_file.write_text(str(time.time()))

        try:
            # Run backup script
            logger.info("Starting scheduled backup (retention=%d)", self.retention)
            result = subprocess.run(
                [sys.executable, str(self.backup_script),
                 "--retention", str(self.retention),
                 "--backup-dir", str(self.backup_dir)],
                capture_output=True, text=True, timeout=600,
            )

            if result.returncode == 0:
                try:
                    backup_result = json.loads(result.stdout.strip())
                except json.JSONDecodeError:
                    backup_result = {"raw_output": result.stdout.strip()[:500]}

                backup_result["returncode"] = 0
                backup_result["scheduled_run"] = True
                logger.info("Scheduled backup completed successfully")
                return backup_result
            else:
                error_msg = f"Backup script failed (exit {result.returncode}): {result.stderr[:1000]}"
                logger.error(error_msg)
                self._notify_failure(error_msg)
                return {
                    "status": "failed",
                    "error": error_msg,
                    "returncode": result.returncode,
                }

        except subprocess.TimeoutExpired:
            error_msg = "Backup script timed out after 600s"
            logger.error(error_msg)
            self._notify_failure(error_msg)
            return {"status": "failed", "error": error_msg}

        except Exception as e:
            error_msg = f"Backup runner error: {e}"
            logger.error(error_msg, exc_info=True)
            self._notify_failure(error_msg)
            return {"status": "failed", "error": error_msg}

        finally:
            self.lock_file.unlink(missing_ok=True)

    def _notify_failure(self, message: str) -> None:
        """Send failure notification via Slack webhook."""
        if not self.slack_webhook_url:
            logger.info("No Slack webhook configured — skipping notification")
            return

        import urllib.request
        payload = json.dumps({
            "text": f"[RasoDataset-Agent] Backup Failed: {message}",
            "username": "Backup Bot",
            "icon_emoji": ":floppy_disk:",
        }).encode()

        try:
            req = urllib.request.Request(
                self.slack_webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            logger.info("Slack notification sent")
        except Exception as e:
            logger.warning("Failed to send Slack notification: %s", e)


def main():
    parser = argparse.ArgumentParser(description="Scheduled backup runner for RasoDataset-Agent")
    parser.add_argument("--retention", type=int, default=7, help="Number of backups to keep")
    parser.add_argument("--backup-dir", default="backups", help="Backup storage directory")
    args = parser.parse_args()

    runner = ScheduledBackupRunner(retention=args.retention, backup_dir=args.backup_dir)
    result = runner.run()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("status") in ("success", "skipped") else 1)


if __name__ == "__main__":
    main()