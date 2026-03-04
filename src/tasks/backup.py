"""Database backup task.

Runs nightly via Celery beat to create PostgreSQL backups.
Alerts on failure via Sentry.
"""

import logging
import os
import subprocess
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _get_celery_app():
    """Lazy import to avoid circular dependencies."""
    from tasks.celery_app import celery_app
    return celery_app


celery_app = _get_celery_app()


@celery_app.task(name="tasks.backup.run_database_backup", bind=True, max_retries=2)
def run_database_backup(self):
    """Run database backup using pg_dump.

    Creates a compressed SQL dump of the production database.
    Reports success/failure metrics.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set — cannot run backup")
        return {"status": "error", "message": "DATABASE_URL not configured"}

    backup_dir = os.environ.get("BACKUP_DIR", "/tmp/backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"taxplatform_{timestamp}.sql.gz")

    try:
        # Run pg_dump with compression
        result = subprocess.run(
            [
                "pg_dump",
                database_url,
                "--no-owner",
                "--no-privileges",
                "--compress=9",
                f"--file={backup_file}",
            ],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        if result.returncode != 0:
            error_msg = f"pg_dump failed: {result.stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Get file size
        file_size = os.path.getsize(backup_file)
        logger.info(
            "Database backup completed: file=%s, size=%d bytes",
            backup_file,
            file_size,
        )

        return {
            "status": "success",
            "file": backup_file,
            "size_bytes": file_size,
            "timestamp": timestamp,
        }

    except subprocess.TimeoutExpired:
        logger.error("Database backup timed out after 600 seconds")
        return {"status": "error", "message": "Backup timed out"}
    except Exception as exc:
        logger.error("Database backup failed: %s", exc, exc_info=True)
        # Retry with exponential backoff
        try:
            self.retry(countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.critical("Database backup failed after all retries")
            return {"status": "error", "message": str(exc)}
