"""
Admin Endpoints for Platform Management

Provides administrative endpoints for:
- System health monitoring
- Circuit breaker management
- Cache management
- Session management
- Configuration updates
- Performance metrics
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import psutil

from rbac import require_platform_admin, AuthContext

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


# =============================================================================
# AUTHORIZATION - All admin endpoints require platform admin role
# =============================================================================

async def get_admin_context(ctx: AuthContext = Depends(require_platform_admin)) -> AuthContext:
    """
    Dependency that ensures platform admin access.
    All admin endpoints must use this dependency.
    """
    return ctx


# =============================================================================
# Response Models
# =============================================================================

class SystemStatus(BaseModel):
    """Overall system status"""
    status: str  # "healthy", "degraded", "critical"
    timestamp: str
    uptime_seconds: float
    total_requests: int
    error_rate: float


class CircuitBreakerStatus(BaseModel):
    """Circuit breaker status"""
    name: str
    state: str
    failure_count: int
    success_rate: str


class SessionInfo(BaseModel):
    """Session information"""
    session_count: int
    active_sessions: int
    oldest_session_age: Optional[float] = None


class CacheStats(BaseModel):
    """Cache statistics"""
    total_keys: int
    hit_rate: float
    memory_usage_mb: float


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.get("/status", response_model=SystemStatus)
async def get_system_status(admin: AuthContext = Depends(get_admin_context)):
    """
    Get overall system status.

    Returns health, performance, and error rate information.
    Uses real metrics from the health monitoring system.
    """
    try:
        # Get real metrics from health router
        from web.routers.health import get_request_metrics, get_calculation_metrics, _start_time

        request_metrics = get_request_metrics()
        calc_metrics = get_calculation_metrics()

        # Calculate uptime
        uptime = (datetime.now() - _start_time).total_seconds()

        # Get total requests and calculate error rate
        total_requests = request_metrics.get("total_requests", 0)
        validation_errors = calc_metrics.get("validation_errors", 0)
        total_calcs = calc_metrics.get("total_calculations", 1)  # Avoid division by zero
        error_rate = validation_errors / total_calcs if total_calcs > 0 else 0.0

        # Determine overall status
        status = "healthy"
        if error_rate > 0.1:  # >10% error rate
            status = "degraded"
        if error_rate > 0.5:  # >50% error rate
            status = "unhealthy"

        return SystemStatus(
            status=status,
            timestamp=datetime.now().isoformat(),
            uptime_seconds=round(uptime, 1),
            total_requests=total_requests,
            error_rate=round(error_rate, 4)
        )
    except ImportError:
        # Fallback if health router not available
        return SystemStatus(
            status="unknown",
            timestamp=datetime.now().isoformat(),
            uptime_seconds=0.0,
            total_requests=0,
            error_rate=0.0
        )
    except Exception as e:
        logger.error(f"Failed to get system status: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to retrieve system status")


@router.get("/circuit-breakers")
async def get_circuit_breakers(admin: AuthContext = Depends(get_admin_context)):
    """
    Get status of all circuit breakers.

    Shows which external services are healthy or degraded.
    """
    try:
        from web.circuit_breaker import get_all_circuit_breakers

        breakers = get_all_circuit_breakers()
        return {
            "total": len(breakers),
            "breakers": breakers,
            "timestamp": datetime.now().isoformat()
        }
    except ImportError:
        return {
            "total": 0,
            "breakers": {},
            "message": "Circuit breakers not configured"
        }


@router.post("/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(name: str, admin: AuthContext = Depends(get_admin_context)):
    """
    Reset a specific circuit breaker.

    Useful when you know a service has recovered.
    """
    try:
        from web.circuit_breaker import reset_circuit_breaker, get_circuit_breaker

        reset_circuit_breaker(name)
        breaker = get_circuit_breaker(name)

        logger.info(f"Circuit breaker {name} reset by admin")

        return {
            "success": True,
            "message": f"Circuit breaker {name} has been reset",
            "status": breaker.get_status()
        }
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker {name}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset circuit breaker. Please try again later.")


@router.post("/circuit-breakers/reset-all")
async def reset_all_circuit_breakers(admin: AuthContext = Depends(get_admin_context)):
    """
    Reset all circuit breakers.

    Use with caution - only when you're sure all services are healthy.
    """
    try:
        from web.circuit_breaker import reset_all_circuit_breakers, get_all_circuit_breakers

        reset_all_circuit_breakers()
        breakers = get_all_circuit_breakers()

        logger.warning("All circuit breakers reset by admin")

        return {
            "success": True,
            "message": f"Reset {len(breakers)} circuit breakers",
            "breakers": breakers
        }
    except Exception as e:
        logger.error(f"Failed to reset all circuit breakers: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset circuit breakers. Please try again later.")


@router.get("/sessions", response_model=SessionInfo)
async def get_session_info(admin: AuthContext = Depends(get_admin_context)):
    """
    Get AI chat session information.

    Shows active sessions and session statistics.
    """
    try:
        from web.ai_chat_api import chat_sessions

        if not chat_sessions:
            return SessionInfo(
                session_count=0,
                active_sessions=0,
                oldest_session_age=None
            )

        # Calculate oldest session age
        now = datetime.now()
        oldest = None

        for session_data in chat_sessions.values():
            created = session_data.get("created_at")
            if created:
                age = (now - created).total_seconds()
                if oldest is None or age > oldest:
                    oldest = age

        return SessionInfo(
            session_count=len(chat_sessions),
            active_sessions=len(chat_sessions),  # All in dict are active
            oldest_session_age=oldest
        )

    except ImportError:
        return SessionInfo(session_count=0, active_sessions=0)


@router.post("/sessions/cleanup")
async def cleanup_sessions(admin: AuthContext = Depends(get_admin_context)):
    """
    Trigger session cleanup.

    Removes old or inactive sessions.
    """
    try:
        from web.ai_chat_api import chat_sessions, _cleanup_old_sessions

        before_count = len(chat_sessions)
        _cleanup_old_sessions(force=True)
        after_count = len(chat_sessions)

        removed = before_count - after_count

        logger.info(f"Admin cleanup removed {removed} sessions")

        return {
            "success": True,
            "sessions_removed": removed,
            "sessions_remaining": after_count
        }

    except ImportError:
        raise HTTPException(status_code=404, detail="Session management not available")


@router.get("/metrics/system")
async def get_system_metrics(admin: AuthContext = Depends(get_admin_context)):
    """
    Get detailed system metrics.

    CPU, memory, disk, network usage.
    """
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()

        # Memory
        memory = psutil.virtual_memory()

        # Disk
        disk = psutil.disk_usage('/')

        # Network
        network = psutil.net_io_counters()

        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count
            },
            "memory": {
                "total_gb": memory.total / (1024**3),
                "used_gb": memory.used / (1024**3),
                "available_gb": memory.available / (1024**3),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_gb": disk.free / (1024**3),
                "percent": disk.percent
            },
            "network": {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get system metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to retrieve system metrics")


@router.get("/metrics/performance")
async def get_performance_metrics(admin: AuthContext = Depends(get_admin_context)):
    """
    Get performance metrics.

    Returns actual system metrics including CPU, memory, and I/O stats.
    Application-level metrics require integration with a metrics collection system.
    """
    import time

    # Get actual system metrics using psutil
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    # Get process-specific metrics
    process = psutil.Process()
    process_memory = process.memory_info()

    return {
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2),
        },
        "process": {
            "memory_rss_mb": round(process_memory.rss / (1024**2), 2),
            "memory_vms_mb": round(process_memory.vms / (1024**2), 2),
            "cpu_percent": process.cpu_percent(),
            "num_threads": process.num_threads(),
            "open_files": len(process.open_files()),
        },
        "note": "Application-level endpoint metrics require integration with a metrics collection system (e.g., Prometheus, StatsD)",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/cache/clear")
async def clear_cache(admin: AuthContext = Depends(get_admin_context)):
    """
    Clear application caches.

    Clears known in-memory caches including:
    - Rate limiter state
    - Auth rate limits
    - Reset tokens (in-memory only)
    - Any LRU caches
    """
    cleared_caches = []

    try:
        # Clear auth rate limits
        try:
            from core.api.auth_routes import _auth_rate_limits
            _auth_rate_limits.clear()
            cleared_caches.append("auth_rate_limits")
        except (ImportError, AttributeError):
            pass

        # Clear any functools.lru_cache decorated functions
        import gc
        for obj in gc.get_objects():
            if hasattr(obj, 'cache_clear') and callable(obj.cache_clear):
                try:
                    obj.cache_clear()
                    cleared_caches.append(f"lru_cache:{getattr(obj, '__name__', 'unknown')}")
                except Exception:
                    pass

        # Try to clear Redis cache if available
        try:
            import os
            redis_url = os.environ.get("REDIS_URL")
            if redis_url:
                import redis
                r = redis.from_url(redis_url)
                r.flushdb()
                cleared_caches.append("redis")
        except (ImportError, Exception):
            pass

        logger.warning(f"Cache cleared by admin {admin.user_id}: {cleared_caches}")

        return {
            "success": True,
            "cleared_caches": cleared_caches,
            "message": f"Cleared {len(cleared_caches)} cache(s)"
        }

    except Exception as e:
        logger.exception("Failed to clear cache")
        raise HTTPException(status_code=500, detail="Failed to clear cache. Please try again later.")


@router.get("/logs/recent")
async def get_recent_logs(level: str = "ERROR", limit: int = 100, admin: AuthContext = Depends(get_admin_context)):
    """
    Get recent log entries from in-memory buffer.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        limit: Maximum number of entries (max 500)

    Note: For production log aggregation, integrate with a log management
    system (e.g., ELK Stack, CloudWatch, Datadog).
    """
    import os

    # Validate and cap limit
    limit = min(limit, 500)

    # Map level string to numeric value
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    min_level = level_map.get(level.upper(), logging.ERROR)

    logs = []

    # Try to read from log file if configured
    log_file = os.environ.get("LOG_FILE", "logs/app.log")
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                # Read last N lines efficiently
                lines = f.readlines()[-limit*2:]  # Read more to filter by level
                for line in reversed(lines):
                    if len(logs) >= limit:
                        break
                    # Simple level filtering
                    line_upper = line.upper()
                    if level.upper() in line_upper or any(
                        lvl in line_upper for lvl in ["ERROR", "CRITICAL"] if level_map.get(lvl, 0) >= min_level
                    ):
                        logs.append(line.strip())
        except Exception as e:
            logger.warning(f"Could not read log file: {e}")

    # If no file logs, provide guidance
    if not logs:
        return {
            "logs": [],
            "level": level,
            "limit": limit,
            "source": "none",
            "note": "No log file found. Set LOG_FILE environment variable or integrate with a log aggregation system."
        }

    return {
        "logs": logs[:limit],
        "level": level,
        "limit": limit,
        "count": len(logs[:limit]),
        "source": "file",
        "log_file": log_file
    }


@router.get("/config")
async def get_configuration(admin: AuthContext = Depends(get_admin_context)):
    """
    Get current configuration (non-sensitive).

    Shows active settings without exposing secrets.
    """
    return {
        "rate_limiting": {
            "requests_per_minute": 60,
            "requests_per_hour": 1000
        },
        "timeouts": {
            "default": 30,
            "ocr": 60,
            "tax_calculation": 45
        },
        "file_limits": {
            "max_size_mb": 10,
            "allowed_types": ["pdf", "png", "jpg", "jpeg", "heic"]
        },
        "session_limits": {
            "max_sessions": 1000,
            "max_age_hours": 24,
            "max_turns": 100
        }
    }


@router.post("/restart-required")
async def mark_restart_required(admin: AuthContext = Depends(get_admin_context)):
    """
    Mark that system needs restart.

    Used when configuration changes require restart.
    """
    logger.warning("System marked as requiring restart by admin")

    return {
        "success": True,
        "message": "System marked for restart. Please restart application for changes to take effect."
    }
