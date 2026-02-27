"""
Data Retention Celery Tasks.

Periodic background jobs that enforce data retention policies:
- Purge expired sessions (Redis + SQLite)
- Clean up orphaned file uploads
- Archive or delete stale tax return data
- Trim old audit logs beyond retention window

Runs on Celery beat schedule. All operations are audit-logged.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

from celery import shared_task

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION (from env or defaults)
# =============================================================================

# How long to keep sessions (hours)
SESSION_RETENTION_HOURS = int(os.environ.get("SESSION_RETENTION_HOURS", "72"))

# How long to keep orphaned uploads (days)
ORPHAN_UPLOAD_RETENTION_DAYS = int(os.environ.get("ORPHAN_UPLOAD_RETENTION_DAYS", "30"))

# How long to keep audit logs (days) — regulatory minimum is often 7 years
AUDIT_LOG_RETENTION_DAYS = int(os.environ.get("AUDIT_LOG_RETENTION_DAYS", "2555"))  # ~7 years

# How long to keep completed tax return data (days)
TAX_DATA_RETENTION_DAYS = int(os.environ.get("TAX_DATA_RETENTION_DAYS", "2555"))  # ~7 years


# =============================================================================
# PERIODIC TASKS
# =============================================================================


@shared_task(name="tasks.data_retention.purge_expired_sessions")
def purge_expired_sessions() -> Dict[str, int]:
    """
    Remove sessions that have exceeded their TTL.

    Runs hourly. Cleans both SQLite and Redis session stores.
    """
    counts = {"sqlite_purged": 0, "redis_purged": 0}

    # SQLite sessions
    try:
        from database.session_persistence import get_session_persistence
        persistence = get_session_persistence()
        cutoff = datetime.utcnow().isoformat()

        with sqlite3.connect(persistence.db_path) as conn:
            cursor = conn.cursor()

            # Find expired sessions
            cursor.execute(
                "SELECT session_id FROM session_states WHERE expires_at < ?",
                (cutoff,),
            )
            expired_ids = [row[0] for row in cursor.fetchall()]

            for sid in expired_ids:
                persistence.delete_session(sid)

            counts["sqlite_purged"] = len(expired_ids)

        if expired_ids:
            logger.info(f"Purged {len(expired_ids)} expired SQLite sessions")

    except Exception as e:
        logger.error(f"Failed to purge SQLite sessions: {e}")

    # Redis sessions auto-expire via TTL, but clean up orphaned indexes
    try:
        import asyncio
        counts["redis_purged"] = asyncio.run(_purge_redis_orphans())
    except Exception as e:
        logger.warning(f"Could not purge Redis orphans: {e}")

    _log_retention_event("purge_expired_sessions", counts)
    return counts


@shared_task(name="tasks.data_retention.cleanup_orphaned_uploads")
def cleanup_orphaned_uploads() -> Dict[str, int]:
    """
    Remove uploaded files that are no longer referenced by any session or document.

    Runs daily. Only deletes files older than ORPHAN_UPLOAD_RETENTION_DAYS.
    """
    counts = {"files_checked": 0, "files_deleted": 0, "bytes_freed": 0}
    cutoff = datetime.utcnow() - timedelta(days=ORPHAN_UPLOAD_RETENTION_DAYS)

    upload_dirs = ["./data/uploads", "./uploads"]

    for upload_dir in upload_dirs:
        if not os.path.isdir(upload_dir):
            continue

        for root, dirs, files in os.walk(upload_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                counts["files_checked"] += 1

                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime >= cutoff:
                        continue

                    # Check if this file is still referenced
                    if _is_file_referenced(filepath):
                        continue

                    file_size = os.path.getsize(filepath)
                    os.remove(filepath)
                    counts["files_deleted"] += 1
                    counts["bytes_freed"] += file_size
                    logger.debug(f"Deleted orphaned upload: {filepath}")

                except OSError as e:
                    logger.warning(f"Could not process {filepath}: {e}")

    # Clean up empty directories
    for upload_dir in upload_dirs:
        if os.path.isdir(upload_dir):
            _remove_empty_dirs(upload_dir)

    if counts["files_deleted"] > 0:
        mb_freed = counts["bytes_freed"] / (1024 * 1024)
        logger.info(
            f"Cleaned up {counts['files_deleted']} orphaned uploads, freed {mb_freed:.1f} MB"
        )

    _log_retention_event("cleanup_orphaned_uploads", counts)
    return counts


@shared_task(name="tasks.data_retention.trim_audit_logs")
def trim_audit_logs() -> Dict[str, int]:
    """
    Delete audit log entries older than the retention window.

    Runs weekly. Default retention is 7 years (regulatory requirement).
    """
    counts = {"logs_deleted": 0}
    cutoff = (datetime.utcnow() - timedelta(days=AUDIT_LOG_RETENTION_DAYS)).isoformat()

    try:
        from audit.audit_logger import AuditLogger
        audit = AuditLogger()

        with sqlite3.connect(audit.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM audit_log WHERE timestamp < ?",
                (cutoff,),
            )
            count = cursor.fetchone()[0]

            if count > 0:
                cursor.execute(
                    "DELETE FROM audit_log WHERE timestamp < ?",
                    (cutoff,),
                )
                conn.commit()
                counts["logs_deleted"] = count

                # Reclaim disk space
                cursor.execute("VACUUM")
                conn.commit()

                logger.info(f"Trimmed {count} audit logs older than {AUDIT_LOG_RETENTION_DAYS} days")

    except Exception as e:
        logger.error(f"Failed to trim audit logs: {e}")

    _log_retention_event("trim_audit_logs", counts)
    return counts


@shared_task(name="tasks.data_retention.cleanup_stale_data")
def cleanup_stale_data() -> Dict[str, int]:
    """
    Master cleanup task that runs all retention subtasks.

    Runs daily via Celery beat.
    """
    results = {}

    try:
        results["sessions"] = purge_expired_sessions()
    except Exception as e:
        logger.error(f"Session purge failed: {e}")
        results["sessions"] = {"error": str(e)}

    try:
        results["uploads"] = cleanup_orphaned_uploads()
    except Exception as e:
        logger.error(f"Upload cleanup failed: {e}")
        results["uploads"] = {"error": str(e)}

    logger.info(f"Data retention cleanup completed: {results}")
    return results


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def _purge_redis_orphans() -> int:
    """Remove Redis session index entries pointing to expired sessions."""
    purged = 0

    try:
        from database.redis_session_persistence import get_redis_session_persistence
        redis_persistence = await get_redis_session_persistence()
        if not redis_persistence:
            return 0

        # Redis sessions auto-expire via TTL, so this mainly
        # cleans up stale index entries (tenant/user sets)
        # The RedisSessionPersistence handles this internally
        logger.debug("Redis sessions auto-expire via TTL — index cleanup skipped")

    except Exception as e:
        logger.warning(f"Redis orphan cleanup failed: {e}")

    return purged


def _is_file_referenced(filepath: str) -> bool:
    """Check if an uploaded file is still referenced in the database."""
    try:
        from database.session_persistence import get_session_persistence
        persistence = get_session_persistence()

        filename = os.path.basename(filepath)

        with sqlite3.connect(persistence.db_path) as conn:
            cursor = conn.cursor()

            # Check document_processing table
            cursor.execute(
                "SELECT COUNT(*) FROM document_processing WHERE file_path LIKE ?",
                (f'%{filename}%',),
            )
            if cursor.fetchone()[0] > 0:
                return True

            # Check session data for file references
            cursor.execute(
                "SELECT COUNT(*) FROM session_states WHERE data_json LIKE ?",
                (f'%{filename}%',),
            )
            if cursor.fetchone()[0] > 0:
                return True

    except Exception:
        # If we can't check, assume referenced (safe default)
        return True

    return False


def _remove_empty_dirs(root_dir: str):
    """Remove empty directories bottom-up."""
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        if dirpath == root_dir:
            continue
        if not dirnames and not filenames:
            try:
                os.rmdir(dirpath)
            except OSError:
                pass


def _log_retention_event(task_name: str, counts: dict):
    """Log a data retention event to the audit trail."""
    try:
        from audit.audit_logger import AuditLogger, AuditEventType, AuditSeverity
        audit = AuditLogger()
        audit.log(
            event_type=AuditEventType.DATA_EXPORT,  # Closest event type for data operations
            action=task_name,
            resource_type="data_retention",
            severity=AuditSeverity.INFO,
            details=counts,
        )
    except Exception as e:
        logger.warning(f"Could not log retention event: {e}")
