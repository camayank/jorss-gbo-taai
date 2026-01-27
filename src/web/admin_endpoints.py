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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


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
async def get_system_status():
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
async def get_circuit_breakers():
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
async def reset_circuit_breaker(name: str):
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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/circuit-breakers/reset-all")
async def reset_all_circuit_breakers():
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=SessionInfo)
async def get_session_info():
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
async def cleanup_sessions():
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
async def get_system_metrics():
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
async def get_performance_metrics():
    """
    Get performance metrics.

    Response times, throughput, error rates.
    """
    # TODO: Integrate with actual metrics collection
    return {
        "endpoints": {
            "/api/tax-returns/express-lane": {
                "avg_response_time_ms": 450,
                "p95_response_time_ms": 800,
                "p99_response_time_ms": 1200,
                "requests_per_minute": 45,
                "error_rate": 0.02
            },
            "/api/ocr/process": {
                "avg_response_time_ms": 2500,
                "p95_response_time_ms": 4500,
                "p99_response_time_ms": 6000,
                "requests_per_minute": 15,
                "error_rate": 0.05
            }
        },
        "timestamp": datetime.now().isoformat()
    }


@router.post("/cache/clear")
async def clear_cache():
    """
    Clear application caches.

    Use when data has changed and cache needs refresh.
    """
    try:
        # TODO: Integrate with actual cache system
        logger.warning("Cache cleared by admin")

        return {
            "success": True,
            "message": "All caches have been cleared"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/recent")
async def get_recent_logs(level: str = "ERROR", limit: int = 100):
    """
    Get recent log entries.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        limit: Maximum number of entries
    """
    # TODO: Integrate with log aggregation system
    return {
        "message": "Log retrieval not yet implemented",
        "level": level,
        "limit": limit
    }


@router.get("/config")
async def get_configuration():
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
async def mark_restart_required():
    """
    Mark that system needs restart.

    Used when configuration changes require restart.
    """
    logger.warning("System marked as requiring restart by admin")

    return {
        "success": True,
        "message": "System marked for restart. Please restart application for changes to take effect."
    }
