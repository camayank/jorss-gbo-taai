"""Database backup task.

Runs nightly via Celery beat to create PostgreSQL backups.
Alerts on failure via Sentry.
"""

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

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

    backup_dir = os.environ.get("BACKUP_DIR", "/app/data/backups")
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

        # Offsite upload to S3 if configured
        local_file_path = Path(backup_file)
        s3_bucket = os.environ.get("BACKUP_S3_BUCKET")
        if s3_bucket and local_file_path.exists():
            try:
                import boto3
                s3 = boto3.client(
                    "s3",
                    region_name=os.environ.get("AWS_S3_REGION", "us-east-1")
                )
                s3_key = (
                    f"backups/{datetime.now().strftime('%Y/%m/%d')}/"
                    f"{local_file_path.name}"
                )
                s3.upload_file(
                    str(local_file_path),
                    s3_bucket,
                    s3_key
                )
                logger.info(
                    f"Backup uploaded to s3://{s3_bucket}/{s3_key}"
                )

                # Delete local file after successful S3 upload
                # only if explicitly configured
                if os.environ.get(
                    "BACKUP_DELETE_LOCAL_AFTER_UPLOAD", "false"
                ).lower() == "true":
                    local_file_path.unlink()
                    logger.info("Local backup deleted after S3 upload")

            except ImportError:
                logger.warning(
                    "boto3 not installed — skipping S3 backup upload"
                )
            except Exception as e:
                logger.critical(
                    f"S3 backup upload FAILED: {e} — "
                    f"local backup retained at {local_file_path}"
                )
                # Never fail the backup task because of S3 failure

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
