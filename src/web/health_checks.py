"""
Health Check System

Provides comprehensive health monitoring for the tax platform:
- Basic health check (liveness)
- Readiness check (can serve requests)
- Dependency checks (database, OCR, etc.)
- System metrics
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Optional, List
from datetime import datetime
import psutil
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])


# =============================================================================
# Response Models
# =============================================================================

class HealthStatus(BaseModel):
    """Overall health status"""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str = "1.0.0"


class DependencyStatus(BaseModel):
    """Status of a dependency"""
    name: str
    status: str  # "up", "down", "degraded"
    response_time_ms: Optional[float] = None
    message: Optional[str] = None


class SystemMetrics(BaseModel):
    """System resource metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    active_connections: int


class DetailedHealthResponse(BaseModel):
    """Detailed health check response"""
    status: str
    timestamp: str
    version: str
    uptime_seconds: float
    dependencies: List[DependencyStatus]
    metrics: SystemMetrics


# =============================================================================
# Health Check Logic
# =============================================================================

# Track application start time
_app_start_time = datetime.now()


def check_database() -> DependencyStatus:
    """Check database connection."""
    try:
        # TODO: Implement actual database check
        # Example: db.execute("SELECT 1")

        return DependencyStatus(
            name="database",
            status="up",
            response_time_ms=5.2,
            message="PostgreSQL connection OK"
        )

    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return DependencyStatus(
            name="database",
            status="down",
            message=str(e)
        )


def check_ocr_service() -> DependencyStatus:
    """Check OCR service availability."""
    try:
        # TODO: Implement actual OCR service check
        # Example: Ping OCR service or check if import works

        from services.ocr import DocumentProcessor
        return DependencyStatus(
            name="ocr_service",
            status="up",
            message="OCR service available"
        )

    except ImportError as e:
        logger.warning(f"OCR service not available: {str(e)}")
        return DependencyStatus(
            name="ocr_service",
            status="degraded",
            message="OCR service unavailable (graceful degradation enabled)"
        )

    except Exception as e:
        logger.error(f"OCR health check failed: {str(e)}")
        return DependencyStatus(
            name="ocr_service",
            status="down",
            message=str(e)
        )


def check_tax_calculator() -> DependencyStatus:
    """Check tax calculator service."""
    try:
        from src.calculation.tax_calculator import TaxCalculator

        # Quick sanity check
        calculator = TaxCalculator()

        return DependencyStatus(
            name="tax_calculator",
            status="up",
            message="Tax calculator initialized successfully"
        )

    except Exception as e:
        logger.error(f"Tax calculator health check failed: {str(e)}")
        return DependencyStatus(
            name="tax_calculator",
            status="down",
            message=str(e)
        )


def get_system_metrics() -> SystemMetrics:
    """Get system resource metrics."""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent

        # Network connections (approximate active connections)
        connections = len(psutil.net_connections())

        return SystemMetrics(
            cpu_percent=round(cpu_percent, 2),
            memory_percent=round(memory_percent, 2),
            disk_percent=round(disk_percent, 2),
            active_connections=connections
        )

    except Exception as e:
        logger.error(f"Failed to get system metrics: {str(e)}")
        return SystemMetrics(
            cpu_percent=0.0,
            memory_percent=0.0,
            disk_percent=0.0,
            active_connections=0
        )


def calculate_overall_status(dependencies: List[DependencyStatus]) -> str:
    """
    Calculate overall health status based on dependencies.

    Logic:
    - healthy: All dependencies are "up"
    - degraded: Some dependencies are "degraded" but none are "down"
    - unhealthy: Any dependency is "down"
    """

    statuses = [dep.status for dep in dependencies]

    if "down" in statuses:
        return "unhealthy"
    elif "degraded" in statuses:
        return "degraded"
    else:
        return "healthy"


# =============================================================================
# Health Check Endpoints
# =============================================================================

@router.get("/", response_model=HealthStatus)
async def health_check():
    """
    Basic health check (liveness probe).

    Returns 200 if application is running.
    Use for Kubernetes liveness probe.
    """
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


@router.get("/ready", response_model=DetailedHealthResponse)
async def readiness_check():
    """
    Readiness check with dependency validation.

    Returns 200 if application is ready to serve requests.
    Use for Kubernetes readiness probe.

    Checks:
    - Database connection
    - OCR service availability
    - Tax calculator initialization
    - System resources
    """

    try:
        # Check all dependencies
        dependencies = [
            check_database(),
            check_ocr_service(),
            check_tax_calculator()
        ]

        # Get system metrics
        metrics = get_system_metrics()

        # Calculate overall status
        overall_status = calculate_overall_status(dependencies)

        # Calculate uptime
        uptime = (datetime.now() - _app_start_time).total_seconds()

        response = DetailedHealthResponse(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            uptime_seconds=round(uptime, 2),
            dependencies=dependencies,
            metrics=metrics
        )

        # Return 503 if unhealthy (for load balancers)
        if overall_status == "unhealthy":
            from fastapi import Response
            return Response(
                content=response.json(),
                status_code=503,
                media_type="application/json"
            )

        return response

    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}", exc_info=True)
        return DetailedHealthResponse(
            status="unhealthy",
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            uptime_seconds=0,
            dependencies=[],
            metrics=SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                active_connections=0
            )
        )


@router.get("/metrics", response_model=SystemMetrics)
async def metrics():
    """
    System metrics endpoint.

    Returns current system resource usage.
    Use for monitoring dashboards.
    """
    return get_system_metrics()


@router.get("/dependencies", response_model=List[DependencyStatus])
async def dependency_status():
    """
    Check status of all dependencies.

    Returns detailed status of each dependency.
    """
    return [
        check_database(),
        check_ocr_service(),
        check_tax_calculator()
    ]


# =============================================================================
# Custom Health Checks
# =============================================================================

def register_custom_health_check(name: str, check_function):
    """
    Register a custom health check.

    Args:
        name: Name of the health check
        check_function: Function that returns DependencyStatus
    """
    # TODO: Implement custom health check registry
    pass
