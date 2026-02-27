"""
Health Check and Monitoring Endpoints

Provides:
1. /health - Full health check for all services
2. /health/live - Simple liveness probe (for k8s)
3. /health/ready - Readiness probe (for k8s)
4. /metrics - Basic application metrics
5. /metrics/requests - Request counts per endpoint
6. /metrics/calculations - Calculation pipeline metrics
"""

import os
import time
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from collections import defaultdict
import threading

from fastapi import APIRouter, Response, Request
from fastapi.responses import JSONResponse
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

# Application start time for uptime calculation
_start_time = datetime.utcnow()

# Thread-safe request metrics tracking
_metrics_lock = threading.Lock()
_request_counts: Dict[str, int] = defaultdict(int)
_request_latencies: Dict[str, list] = defaultdict(list)  # Store last 100 latencies per endpoint
_calculation_metrics: Dict[str, Any] = {
    "total_calculations": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "validation_errors": 0,
    "validation_warnings": 0,
    "average_calculation_ms": 0.0,
    "calculations_by_filing_status": defaultdict(int),
}


def record_request(endpoint: str, latency_ms: float = 0.0):
    """
    Record a request to an endpoint for metrics tracking.

    Call this from middleware or directly in endpoints:
        from web.routers.health import record_request
        record_request("/api/calculate", latency_ms=150.5)

    Args:
        endpoint: The endpoint path (e.g., "/api/calculate")
        latency_ms: Request latency in milliseconds
    """
    _MAX_TRACKED_ENDPOINTS = 500
    with _metrics_lock:
        # Prevent unbounded growth from unique path params (e.g., /documents/{id})
        if endpoint not in _request_counts and len(_request_counts) >= _MAX_TRACKED_ENDPOINTS:
            return
        _request_counts[endpoint] += 1
        if latency_ms > 0:
            # Keep only last 100 latencies per endpoint
            latencies = _request_latencies[endpoint]
            latencies.append(latency_ms)
            if len(latencies) > 100:
                _request_latencies[endpoint] = latencies[-100:]


def record_calculation(cache_hit: bool = False, validation_errors: int = 0,
                       validation_warnings: int = 0, latency_ms: float = 0.0,
                       filing_status: str = "unknown"):
    """
    Record calculation metrics.

    Call this after a tax calculation completes:
        from web.routers.health import record_calculation
        record_calculation(cache_hit=True, latency_ms=50.0, filing_status="married_joint")

    Args:
        cache_hit: Whether the calculation was served from cache
        validation_errors: Number of validation errors encountered
        validation_warnings: Number of validation warnings encountered
        latency_ms: Calculation time in milliseconds
        filing_status: The filing status used in the calculation
    """
    with _metrics_lock:
        _calculation_metrics["total_calculations"] += 1
        if cache_hit:
            _calculation_metrics["cache_hits"] += 1
        else:
            _calculation_metrics["cache_misses"] += 1
        _calculation_metrics["validation_errors"] += validation_errors
        _calculation_metrics["validation_warnings"] += validation_warnings
        _calculation_metrics["calculations_by_filing_status"][filing_status] += 1

        # Update running average
        total = _calculation_metrics["total_calculations"]
        current_avg = _calculation_metrics["average_calculation_ms"]
        _calculation_metrics["average_calculation_ms"] = (
            (current_avg * (total - 1) + latency_ms) / total
        )


def get_request_metrics() -> Dict[str, Any]:
    """Get current request metrics (thread-safe)."""
    with _metrics_lock:
        # Calculate average latencies
        avg_latencies = {}
        for endpoint, latencies in _request_latencies.items():
            if latencies:
                avg_latencies[endpoint] = float(money(sum(latencies) / len(latencies)))

        return {
            "request_counts": dict(_request_counts),
            "average_latencies_ms": avg_latencies,
            "total_requests": sum(_request_counts.values()),
        }


def get_calculation_metrics() -> Dict[str, Any]:
    """Get current calculation metrics (thread-safe)."""
    with _metrics_lock:
        metrics = dict(_calculation_metrics)
        metrics["calculations_by_filing_status"] = dict(
            _calculation_metrics["calculations_by_filing_status"]
        )
        # Calculate cache hit rate
        total = metrics["total_calculations"]
        if total > 0:
            metrics["cache_hit_rate"] = float(money(
                metrics["cache_hits"] / total * 100
            ))
        else:
            metrics["cache_hit_rate"] = 0.0
        return metrics


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
            "latency_ms": float(money(latency_ms)),
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
    encryption_value = os.environ.get("ENCRYPTION_KEY") or os.environ.get("ENCRYPTION_MASTER_KEY")
    required_keys = [
        ("ENCRYPTION_KEY", encryption_value),
        ("JWT_SECRET", os.environ.get("JWT_SECRET")),
        ("APP_SECRET_KEY", os.environ.get("APP_SECRET_KEY")),
    ]

    env_name = (
        os.environ.get("APP_ENVIRONMENT")
        or os.environ.get("ENVIRONMENT")
        or "development"
    ).lower()
    is_production = env_name in {"production", "prod", "staging"}

    missing = []
    weak = []

    for name, value in required_keys:
        if not value:
            if is_production:
                missing.append(name)
        elif len(value) < 32:
            weak.append(name)

    if missing:
        logger.error(f"Missing required encryption keys: {', '.join(missing)}")
        return {
            "status": "unhealthy",
            "error": "Security configuration incomplete",
        }

    if weak:
        logger.warning(f"Weak encryption keys (< 32 chars): {', '.join(weak)}")
        return {
            "status": "warning",
            "message": "Security configuration needs strengthening",
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
                        "db_size_mb": float(money(db_size_mb)),
                    }

                return {
                    "status": "healthy",
                    "usage_percent": round(usage_percent, 1),
                    "available_mb": round(available_mb, 0),
                    "db_size_mb": float(money(db_size_mb)),
                }
            except (OSError, AttributeError):
                # Windows or other OS without statvfs
                return {
                    "status": "healthy",
                    "db_size_mb": float(money(db_size_mb)),
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
        "environment": os.environ.get("APP_ENVIRONMENT")
        or os.environ.get("ENVIRONMENT", "development"),
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

    # Get request and calculation metrics
    request_metrics = get_request_metrics()
    calc_metrics = get_calculation_metrics()

    metrics = {
        "uptime_seconds": round(uptime_seconds, 0),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "version": os.environ.get("APP_VERSION", "development"),
        "database": {
            "lead_count": db_check.get("lead_count", 0),
            "tables": db_check.get("tables", 0),
        },
        "requests": {
            "total": request_metrics["total_requests"],
            "top_endpoints": dict(
                sorted(request_metrics["request_counts"].items(),
                       key=lambda x: x[1], reverse=True)[:10]
            ),
        },
        "calculations": {
            "total": calc_metrics["total_calculations"],
            "cache_hit_rate": calc_metrics["cache_hit_rate"],
            "average_ms": float(money(calc_metrics["average_calculation_ms"])),
        },
        "collected_at": datetime.utcnow().isoformat() + "Z",
    }

    return JSONResponse(content=metrics)


@router.get("/metrics/requests")
async def request_metrics() -> JSONResponse:
    """
    Detailed request metrics per endpoint.

    Returns:
    - Request counts per endpoint
    - Average latencies per endpoint
    - Total request count
    """
    metrics = get_request_metrics()
    metrics["collected_at"] = datetime.utcnow().isoformat() + "Z"
    return JSONResponse(content=metrics)


@router.get("/metrics/calculations")
async def calculation_metrics() -> JSONResponse:
    """
    Detailed calculation pipeline metrics.

    Returns:
    - Total calculations performed
    - Cache hit/miss counts and rate
    - Validation error/warning counts
    - Average calculation time
    - Breakdown by filing status
    """
    metrics = get_calculation_metrics()
    metrics["collected_at"] = datetime.utcnow().isoformat() + "Z"
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
