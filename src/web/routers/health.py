"""
Health Check and Monitoring Endpoints

Provides:
1. /health - Full health check for all services
2. /health/live - Simple liveness probe (for k8s)
3. /health/ready - Readiness probe (for k8s)
4. /metrics - Basic application metrics
"""

import os
import time
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

# Application start time for uptime calculation
_start_time = datetime.utcnow()

# Simple request counter (for basic metrics)
_request_counts: Dict[str, int] = {}


def _get_db_path() -> str:
    """Get database path from environment or default."""
    return os.environ.get(
        "DATABASE_PATH",
        str(Path(__file__).parent.parent.parent / "database" / "jorss_gbo.db")
    )


async def _check_database() -> Dict[str, Any]:
    """Check database connectivity and basic stats."""
    try:
        db_path = _get_db_path()
        start = time.time()

        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Basic connectivity check
        cursor.execute("SELECT 1")
        cursor.fetchone()

        # Get table counts for monitoring
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]

        # Check if lead_magnet_leads exists and get count
        lead_count = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM lead_magnet_leads")
            lead_count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            pass  # Table may not exist

        conn.close()
        latency_ms = (time.time() - start) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "tables": table_count,
            "lead_count": lead_count,
        }

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


def _check_encryption_key() -> Dict[str, Any]:
    """Check if encryption key is properly configured."""
    # Check for required encryption keys
    required_keys = [
        ("ENCRYPTION_KEY", os.environ.get("ENCRYPTION_KEY")),
        ("JWT_SECRET", os.environ.get("JWT_SECRET")),
        ("APP_SECRET_KEY", os.environ.get("APP_SECRET_KEY")),
    ]

    is_production = os.environ.get("ENVIRONMENT", "development").lower() == "production"

    missing = []
    weak = []

    for name, value in required_keys:
        if not value:
            if is_production:
                missing.append(name)
        elif len(value) < 32:
            weak.append(name)

    if missing:
        return {
            "status": "unhealthy",
            "error": f"Missing required keys: {', '.join(missing)}",
        }

    if weak:
        return {
            "status": "warning",
            "message": f"Weak keys (< 32 chars): {', '.join(weak)}",
        }

    return {"status": "healthy"}


def _check_disk_space() -> Dict[str, Any]:
    """Check available disk space."""
    try:
        db_path = Path(_get_db_path())
        if db_path.exists():
            # Get database size
            db_size_mb = db_path.stat().st_size / (1024 * 1024)

            # Check disk usage (Unix only)
            try:
                statvfs = os.statvfs(db_path.parent)
                available_mb = (statvfs.f_frsize * statvfs.f_bavail) / (1024 * 1024)
                total_mb = (statvfs.f_frsize * statvfs.f_blocks) / (1024 * 1024)
                usage_percent = ((total_mb - available_mb) / total_mb) * 100

                if usage_percent > 90:
                    return {
                        "status": "warning",
                        "usage_percent": round(usage_percent, 1),
                        "available_mb": round(available_mb, 0),
                        "db_size_mb": round(db_size_mb, 2),
                    }

                return {
                    "status": "healthy",
                    "usage_percent": round(usage_percent, 1),
                    "available_mb": round(available_mb, 0),
                    "db_size_mb": round(db_size_mb, 2),
                }
            except (OSError, AttributeError):
                # Windows or other OS without statvfs
                return {
                    "status": "healthy",
                    "db_size_mb": round(db_size_mb, 2),
                }

        return {"status": "healthy", "db_size_mb": 0}

    except Exception as e:
        return {"status": "warning", "error": str(e)}


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Comprehensive health check endpoint.

    Checks:
    - Database connectivity
    - Encryption keys configuration
    - Disk space availability
    - Application uptime

    Returns 200 if all checks pass, 503 if any critical check fails.
    """
    db_check = await _check_database()
    encryption_check = _check_encryption_key()
    disk_check = _check_disk_space()

    # Calculate uptime
    uptime = datetime.utcnow() - _start_time
    uptime_str = str(uptime).split(".")[0]  # Remove microseconds

    checks = {
        "database": db_check,
        "encryption": encryption_check,
        "disk": disk_check,
    }

    # Determine overall status
    statuses = [c.get("status", "unknown") for c in checks.values()]
    if "unhealthy" in statuses:
        overall_status = "unhealthy"
        status_code = 503
    elif "warning" in statuses:
        overall_status = "degraded"
        status_code = 200
    else:
        overall_status = "healthy"
        status_code = 200

    response = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime": uptime_str,
        "version": os.environ.get("APP_VERSION", "development"),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "checks": checks,
    }

    return JSONResponse(content=response, status_code=status_code)


@router.get("/health/live")
async def liveness_probe() -> Response:
    """
    Kubernetes liveness probe.

    Simple check - if the server responds, it's alive.
    Returns 200 OK if alive.
    """
    return Response(content="OK", media_type="text/plain")


@router.get("/health/ready")
async def readiness_probe() -> JSONResponse:
    """
    Kubernetes readiness probe.

    Checks if the application is ready to receive traffic.
    Returns 200 if ready, 503 if not.
    """
    db_check = await _check_database()

    if db_check.get("status") == "healthy":
        return JSONResponse(
            content={"status": "ready", "database": "connected"},
            status_code=200
        )
    else:
        return JSONResponse(
            content={"status": "not_ready", "reason": db_check.get("error", "Database unavailable")},
            status_code=503
        )


@router.get("/metrics")
async def basic_metrics() -> JSONResponse:
    """
    Basic application metrics.

    For production, consider integrating with Prometheus.
    """
    uptime_seconds = (datetime.utcnow() - _start_time).total_seconds()

    # Get database metrics
    db_check = await _check_database()

    metrics = {
        "uptime_seconds": round(uptime_seconds, 0),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "version": os.environ.get("APP_VERSION", "development"),
        "database": {
            "lead_count": db_check.get("lead_count", 0),
            "tables": db_check.get("tables", 0),
        },
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }

    return JSONResponse(content=metrics)


@router.get("/health/info")
async def application_info() -> JSONResponse:
    """
    Application information endpoint.

    Returns non-sensitive application metadata.
    """
    return JSONResponse({
        "name": "Jorss-Gbo CPA Lead Platform",
        "version": os.environ.get("APP_VERSION", "development"),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "python_version": os.sys.version.split()[0],
        "started_at": _start_time.isoformat() + "Z",
    })
