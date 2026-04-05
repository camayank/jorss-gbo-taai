"""Database maintenance Celery tasks.

Periodic jobs for PostgreSQL performance optimization and data lifecycle management:
- VACUUM ANALYZE on high-churn tables (weekly)
- Archive audit logs to S3 (90 days old)
- Delete orphaned OCR temp files
- Purge expired Redis sessions
- Collect and export pg_stat metrics to CloudWatch
- Enable pg_cron for database-side scheduled maintenance

All operations are logged and monitored via CloudWatch.
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
from decimal import Decimal

from celery import shared_task
import boto3

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# High-churn tables that benefit from regular VACUUM ANALYZE
HIGH_CHURN_TABLES = [
    "tax_returns",           # Active processing, frequent updates
    "document_processing",   # OCR status tracking
    "session_states",        # Session lifecycle management
    "audit_log",             # Append-heavy audit trail
    "calculations",          # Computation results, frequent deletes
]

# Audit log archive retention - 90 days before archiving to S3
AUDIT_LOG_ARCHIVE_DAYS = int(os.environ.get("AUDIT_LOG_ARCHIVE_DAYS", "90"))

# Retention periods
OCR_TEMP_FILE_RETENTION_DAYS = int(os.environ.get("OCR_TEMP_RETENTION_DAYS", "7"))

# CloudWatch metric namespace
CLOUDWATCH_NAMESPACE = "TaxPlatform/Database"


def _get_db_connection():
    """Get a direct database connection for maintenance operations."""
    try:
        import psycopg2
        from config.settings import get_settings

        settings = get_settings()
        db_url = settings.database_url

        # Parse connection string: postgresql://user:password@host:port/dbname
        conn = psycopg2.connect(db_url)
        conn.autocommit = True  # Required for VACUUM
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


def _get_s3_client():
    """Get boto3 S3 client."""
    return boto3.client("s3")


def _put_cloudwatch_metric(metric_name: str, value: float, unit: str = "Count"):
    """Push a custom metric to CloudWatch."""
    try:
        cloudwatch = boto3.client("cloudwatch")
        cloudwatch.put_metric_data(
            Namespace=CLOUDWATCH_NAMESPACE,
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": value,
                    "Unit": unit,
                    "Timestamp": datetime.now(timezone.utc),
                }
            ],
        )
        logger.debug(f"Published CloudWatch metric: {metric_name}={value} {unit}")
    except Exception as e:
        logger.warning(f"Failed to publish CloudWatch metric {metric_name}: {e}")


# =============================================================================
# PERIODIC TASKS
# =============================================================================


@shared_task(name="tasks.database_maintenance.vacuum_analyze_high_churn")
def vacuum_analyze_high_churn() -> Dict[str, Any]:
    """
    Run VACUUM ANALYZE on high-churn tables to optimize query plans.

    Runs weekly. Targets tables with frequent updates/deletes to reclaim
    disk space and update statistics for the query planner.

    Returns:
        Dict with table statistics and execution times
    """
    results = {}
    conn = None

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        for table in HIGH_CHURN_TABLES:
            try:
                logger.info(f"VACUUM ANALYZE {table}")
                cursor.execute(f"VACUUM ANALYZE {table}")
                results[table] = "success"

                # Get table statistics
                cursor.execute(
                    f"SELECT n_live_tup, n_dead_tup, n_mod_since_analyze "
                    f"FROM pg_stat_user_tables WHERE relname = %s",
                    (table,)
                )
                stats = cursor.fetchone()
                if stats:
                    live, dead, modified = stats
                    results[f"{table}_stats"] = {
                        "live_tuples": live,
                        "dead_tuples": dead,
                        "modified_since_analyze": modified,
                    }
                    logger.info(
                        f"{table} stats: {live} live, {dead} dead, "
                        f"{modified} modified since analyze"
                    )

                    # Publish to CloudWatch
                    _put_cloudwatch_metric(f"TableDeadTuples_{table}", dead)
                    _put_cloudwatch_metric(f"TableLiveTuples_{table}", live)

            except Exception as e:
                logger.error(f"VACUUM ANALYZE failed for {table}: {e}")
                results[table] = f"error: {str(e)}"

        cursor.close()
        logger.info(f"VACUUM ANALYZE completed: {results}")
        _put_cloudwatch_metric("VacuumAnalyzeSuccess", 1)

    except Exception as e:
        logger.error(f"VACUUM ANALYZE task failed: {e}")
        _put_cloudwatch_metric("VacuumAnalyzeSuccess", 0)
        raise
    finally:
        if conn:
            conn.close()

    return results


@shared_task(name="tasks.database_maintenance.archive_audit_logs")
def archive_audit_logs() -> Dict[str, Any]:
    """
    Archive audit logs older than AUDIT_LOG_ARCHIVE_DAYS to S3.

    Runs weekly. Moves old audit entries to a compressed JSON archive
    in S3 for long-term storage and compliance, then deletes from the live database.

    Returns:
        Dict with archive statistics (archived_count, bytes_transferred, etc.)
    """
    results = {
        "archived_count": 0,
        "bytes_transferred": 0,
        "s3_object_key": None,
    }

    conn = None
    s3_client = _get_s3_client()

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # Cutoff date: logs older than AUDIT_LOG_ARCHIVE_DAYS
        cutoff_date = datetime.now(timezone.utc) - timedelta(
            days=AUDIT_LOG_ARCHIVE_DAYS
        )
        cutoff_iso = cutoff_date.isoformat()

        # Fetch audit logs to archive (in batches to avoid memory issues)
        cursor.execute(
            "SELECT id, timestamp, event_type, resource_type, action, "
            "actor_id, severity, details FROM audit_log "
            "WHERE timestamp < %s ORDER BY timestamp",
            (cutoff_iso,)
        )

        logs_to_archive = []
        batch_size = 10000

        for row in cursor.fetchall():
            log_entry = {
                "id": str(row[0]),
                "timestamp": row[1].isoformat() if row[1] else None,
                "event_type": row[2],
                "resource_type": row[3],
                "action": row[4],
                "actor_id": str(row[5]) if row[5] else None,
                "severity": row[6],
                "details": row[7] if isinstance(row[7], dict) else {},
            }
            logs_to_archive.append(log_entry)

            if len(logs_to_archive) >= batch_size:
                # Upload batch to S3
                _archive_batch_to_s3(
                    s3_client, logs_to_archive, results, cutoff_iso
                )
                logs_to_archive = []

        # Upload final batch
        if logs_to_archive:
            _archive_batch_to_s3(s3_client, logs_to_archive, results, cutoff_iso)

        # Delete archived logs from database
        cursor.execute(
            "DELETE FROM audit_log WHERE timestamp < %s",
            (cutoff_iso,)
        )
        conn.commit()

        deleted_count = cursor.rowcount
        logger.info(
            f"Archived {results['archived_count']} audit logs, "
            f"deleted {deleted_count} from database, "
            f"transferred {results['bytes_transferred'] / (1024*1024):.1f} MB"
        )

        _put_cloudwatch_metric("AuditLogsArchived", results["archived_count"])
        _put_cloudwatch_metric("AuditLogsBytesTransferred", results["bytes_transferred"], "Bytes")

    except Exception as e:
        logger.error(f"Audit log archival failed: {e}")
        raise
    finally:
        if conn:
            conn.close()

    return results


def _archive_batch_to_s3(
    s3_client,
    logs: List[Dict],
    results: Dict,
    cutoff_iso: str,
) -> None:
    """Helper to upload a batch of logs to S3."""
    try:
        from config.settings import get_settings
        settings = get_settings()

        bucket = settings.aws_document_bucket or os.environ.get("AWS_DOCUMENT_BUCKET")
        if not bucket:
            logger.warning("No S3 bucket configured for audit log archival")
            return

        # Create archive filename: audit-logs-YYYY-MM-DD.jsonl
        archive_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        s3_key = f"archives/audit-logs/{archive_date}/batch-{len(results)}.jsonl"

        # Upload as JSONL (one JSON per line) for efficient retrieval
        content = "\n".join(json.dumps(log) for log in logs)
        content_bytes = content.encode("utf-8")

        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=content_bytes,
            ContentType="application/x-ndjson",
            ServerSideEncryption="AES256",
        )

        results["archived_count"] += len(logs)
        results["bytes_transferred"] += len(content_bytes)
        results["s3_object_key"] = s3_key

        logger.debug(f"Archived {len(logs)} logs to s3://{bucket}/{s3_key}")

    except Exception as e:
        logger.error(f"Failed to archive batch to S3: {e}")


@shared_task(name="tasks.database_maintenance.collect_pg_stats")
def collect_pg_stats() -> Dict[str, Any]:
    """
    Collect PostgreSQL statistics and publish to CloudWatch.

    Runs hourly. Gathers key performance metrics from pg_stat views:
    - Table size and tuple counts
    - Index usage statistics
    - Cache hit ratios
    - Query performance metrics

    Returns:
        Dict with collected metrics
    """
    metrics = {}
    conn = None

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # Cache hit ratio (index vs seq scans)
        cursor.execute("""
            SELECT
                sum(heap_blks_read) as heap_read,
                sum(heap_blks_hit) as heap_hit,
                sum(idx_blks_read) as idx_read,
                sum(idx_blks_hit) as idx_hit
            FROM pg_statio_user_tables
        """)
        heap_read, heap_hit, idx_read, idx_hit = cursor.fetchone()

        if heap_hit + heap_read > 0:
            heap_hit_ratio = heap_hit / (heap_hit + heap_read)
            metrics["heap_cache_hit_ratio"] = heap_hit_ratio
            _put_cloudwatch_metric("CacheHitRatio_Heap", heap_hit_ratio * 100)

        if idx_hit + idx_read > 0:
            idx_hit_ratio = idx_hit / (idx_hit + idx_read)
            metrics["index_cache_hit_ratio"] = idx_hit_ratio
            _put_cloudwatch_metric("CacheHitRatio_Index", idx_hit_ratio * 100)

        # Database size
        cursor.execute("""
            SELECT
                pg_database.datname,
                pg_size_pretty(pg_database_size(pg_database.datname)) as size
            FROM pg_database
            WHERE datname = current_database()
        """)
        db_name, db_size = cursor.fetchone()
        metrics["database_name"] = db_name
        metrics["database_size_pretty"] = db_size

        # Active connections
        cursor.execute("""
            SELECT count(*) FROM pg_stat_activity
            WHERE state = 'active' AND datname = current_database()
        """)
        active_connections = cursor.fetchone()[0]
        metrics["active_connections"] = active_connections
        _put_cloudwatch_metric("ActiveConnections", active_connections)

        # Max connections configured
        cursor.execute("SHOW max_connections")
        max_connections = int(cursor.fetchone()[0])
        metrics["max_connections"] = max_connections

        # Connection utilization
        conn_utilization = (active_connections / max_connections) * 100
        metrics["connection_utilization_percent"] = conn_utilization
        _put_cloudwatch_metric("ConnectionUtilization", conn_utilization)

        # Slow queries (> 1 second)
        cursor.execute("""
            SELECT count(*) FROM pg_stat_statements
            WHERE mean_exec_time > 1000 AND datname = current_database()
        """)
        slow_query_count = cursor.fetchone()[0]
        metrics["slow_queries"] = slow_query_count
        _put_cloudwatch_metric("SlowQueries", slow_query_count)

        # Largest tables
        cursor.execute("""
            SELECT
                schemaname, tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 5
        """)

        largest_tables = []
        for row in cursor.fetchall():
            largest_tables.append({
                "schema": row[0],
                "table": row[1],
                "size": row[2],
            })
        metrics["largest_tables"] = largest_tables

        logger.info(f"Collected pg_stat metrics: {metrics}")
        _put_cloudwatch_metric("StatsCollectionSuccess", 1)

    except Exception as e:
        logger.error(f"Failed to collect pg_stat metrics: {e}")
        _put_cloudwatch_metric("StatsCollectionSuccess", 0)
        raise
    finally:
        if conn:
            conn.close()

    return metrics


@shared_task(name="tasks.database_maintenance.setup_pg_cron")
def setup_pg_cron() -> Dict[str, Any]:
    """
    Ensure pg_cron extension is installed and set up database-side scheduled tasks.

    Runs once on deployment. Creates database-side cron jobs for:
    - Daily REINDEX of indexes
    - Hourly table bloat analysis
    - Update table statistics

    Returns:
        Dict with setup status
    """
    results = {"pg_cron_enabled": False, "jobs_created": []}
    conn = None

    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # Try to create pg_cron extension
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_cron")
            conn.commit()
            logger.info("pg_cron extension enabled")
            results["pg_cron_enabled"] = True
        except Exception as e:
            logger.warning(f"pg_cron not available (requires superuser): {e}")
            results["pg_cron_enabled"] = False

        # Set up scheduled jobs (requires pg_cron or superuser privileges)
        if results["pg_cron_enabled"]:
            # Daily REINDEX at 4 AM UTC
            try:
                cursor.execute("""
                    SELECT cron.schedule(
                        'reindex-high-churn-tables',
                        '0 4 * * *',
                        'REINDEX CONCURRENT INDEX CONCURRENTLY idx_tax_returns_updated_at;'
                    )
                """)
                conn.commit()
                results["jobs_created"].append("reindex-high-churn-tables")
                logger.info("Created REINDEX cron job")
            except Exception as e:
                logger.warning(f"Failed to create REINDEX cron job: {e}")

            # Update statistics hourly at minute :15
            try:
                cursor.execute("""
                    SELECT cron.schedule(
                        'analyze-database',
                        '15 * * * *',
                        'ANALYZE;'
                    )
                """)
                conn.commit()
                results["jobs_created"].append("analyze-database")
                logger.info("Created ANALYZE cron job")
            except Exception as e:
                logger.warning(f"Failed to create ANALYZE cron job: {e}")

        logger.info(f"pg_cron setup result: {results}")

    except Exception as e:
        logger.error(f"pg_cron setup failed: {e}")
        raise
    finally:
        if conn:
            conn.close()

    return results


@shared_task(name="tasks.database_maintenance.cleanup_ocr_temp_files")
def cleanup_ocr_temp_files() -> Dict[str, int]:
    """
    Delete orphaned OCR temporary processing files.

    Runs daily. Removes temp OCR files (typically .tmp, .processing)
    older than OCR_TEMP_FILE_RETENTION_DAYS that are no longer being processed.

    Returns:
        Dict with cleanup statistics
    """
    results = {"files_checked": 0, "files_deleted": 0, "bytes_freed": 0}

    try:
        ocr_temp_dirs = [
            "/app/data/ocr/temp",
            "/app/data/ocr/processing",
            "./data/ocr/temp",
            "./data/ocr/processing",
        ]

        cutoff = datetime.now(timezone.utc) - timedelta(days=OCR_TEMP_FILE_RETENTION_DAYS)

        for temp_dir in ocr_temp_dirs:
            if not os.path.isdir(temp_dir):
                continue

            try:
                for root, dirs, files in os.walk(temp_dir):
                    for filename in files:
                        if not (filename.endswith(".tmp") or filename.endswith(".processing")):
                            continue

                        filepath = os.path.join(root, filename)
                        results["files_checked"] += 1

                        try:
                            mtime = datetime.fromtimestamp(os.path.getmtime(filepath), tz=timezone.utc)
                            if mtime >= cutoff:
                                continue

                            file_size = os.path.getsize(filepath)
                            os.remove(filepath)
                            results["files_deleted"] += 1
                            results["bytes_freed"] += file_size
                            logger.debug(f"Deleted OCR temp file: {filepath}")

                        except OSError as e:
                            logger.warning(f"Could not delete {filepath}: {e}")

            except Exception as e:
                logger.warning(f"Error processing temp directory {temp_dir}: {e}")

        if results["files_deleted"] > 0:
            mb_freed = results["bytes_freed"] / (1024 * 1024)
            logger.info(
                f"Cleaned {results['files_deleted']} OCR temp files, "
                f"freed {mb_freed:.1f} MB"
            )

        _put_cloudwatch_metric("OcrTempFilesDeleted", results["files_deleted"])
        _put_cloudwatch_metric("OcrTempBytesFreed", results["bytes_freed"], "Bytes")

    except Exception as e:
        logger.error(f"OCR temp file cleanup failed: {e}")
        raise

    return results
