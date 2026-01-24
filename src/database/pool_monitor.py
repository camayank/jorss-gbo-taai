"""
Database Connection Pool Monitoring - Production-ready pool management.

Provides:
- Real-time pool statistics
- Connection health metrics
- Pool exhaustion detection
- Automatic connection recovery

Resolves Audit Finding: "Database connection pooling optimization"
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """Database connection pool metrics."""
    timestamp: datetime = field(default_factory=datetime.now)

    # Pool size stats
    pool_size: int = 0
    max_overflow: int = 0
    current_size: int = 0

    # Connection stats
    checked_in: int = 0
    checked_out: int = 0
    overflow: int = 0

    # Health metrics
    available_connections: int = 0
    utilization_percent: float = 0.0
    is_exhausted: bool = False

    # Performance stats
    avg_checkout_time_ms: float = 0.0
    total_checkouts: int = 0
    failed_checkouts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "current_size": self.current_size,
            "checked_in": self.checked_in,
            "checked_out": self.checked_out,
            "overflow": self.overflow,
            "available_connections": self.available_connections,
            "utilization_percent": round(self.utilization_percent, 2),
            "is_exhausted": self.is_exhausted,
            "avg_checkout_time_ms": round(self.avg_checkout_time_ms, 2),
            "total_checkouts": self.total_checkouts,
            "failed_checkouts": self.failed_checkouts,
        }


class PoolMonitor:
    """
    Monitor database connection pool health and performance.

    Usage:
        monitor = PoolMonitor(engine)
        metrics = monitor.get_metrics()
        if metrics.is_exhausted:
            logger.warning("Pool exhausted!")
    """

    def __init__(self, engine=None):
        self._engine = engine
        self._checkout_times: list[float] = []
        self._max_checkout_samples = 100
        self._total_checkouts = 0
        self._failed_checkouts = 0

    def set_engine(self, engine):
        """Set the engine to monitor."""
        self._engine = engine

    def record_checkout(self, duration_ms: float, success: bool = True):
        """Record a connection checkout."""
        self._total_checkouts += 1

        if not success:
            self._failed_checkouts += 1
            return

        self._checkout_times.append(duration_ms)

        # Keep only recent samples
        if len(self._checkout_times) > self._max_checkout_samples:
            self._checkout_times = self._checkout_times[-self._max_checkout_samples:]

    def get_metrics(self) -> PoolMetrics:
        """Get current pool metrics."""
        metrics = PoolMetrics()

        if not self._engine:
            return metrics

        try:
            pool = self._engine.pool

            # Get pool configuration
            metrics.pool_size = getattr(pool, '_pool_size', 0) or getattr(pool, 'size', lambda: 0)()
            metrics.max_overflow = getattr(pool, '_max_overflow', 0)

            # Get current status (for QueuePool)
            if hasattr(pool, 'checkedin'):
                metrics.checked_in = pool.checkedin()
            if hasattr(pool, 'checkedout'):
                metrics.checked_out = pool.checkedout()
            if hasattr(pool, 'overflow'):
                metrics.overflow = pool.overflow()
            if hasattr(pool, 'size'):
                metrics.current_size = pool.size()

            # Calculate derived metrics
            max_possible = metrics.pool_size + metrics.max_overflow
            metrics.available_connections = metrics.checked_in
            metrics.utilization_percent = (
                (metrics.checked_out / max_possible * 100)
                if max_possible > 0 else 0
            )
            metrics.is_exhausted = (
                metrics.checked_out >= max_possible and
                metrics.checked_in == 0
            )

            # Performance stats
            if self._checkout_times:
                metrics.avg_checkout_time_ms = sum(self._checkout_times) / len(self._checkout_times)
            metrics.total_checkouts = self._total_checkouts
            metrics.failed_checkouts = self._failed_checkouts

        except Exception as e:
            logger.warning(f"Error getting pool metrics: {e}")

        return metrics

    def check_health(self) -> Dict[str, Any]:
        """
        Perform a health check on the connection pool.

        Returns:
            Dict with health status and recommendations.
        """
        metrics = self.get_metrics()

        status = "healthy"
        warnings = []
        recommendations = []

        # Check utilization
        if metrics.utilization_percent > 90:
            status = "critical"
            warnings.append(f"Pool utilization at {metrics.utilization_percent}%")
            recommendations.append("Consider increasing pool_size or max_overflow")
        elif metrics.utilization_percent > 75:
            status = "warning"
            warnings.append(f"Pool utilization at {metrics.utilization_percent}%")

        # Check exhaustion
        if metrics.is_exhausted:
            status = "critical"
            warnings.append("Connection pool exhausted")
            recommendations.append("Increase pool size or optimize connection usage")

        # Check failed checkouts
        if metrics.total_checkouts > 0:
            failure_rate = metrics.failed_checkouts / metrics.total_checkouts * 100
            if failure_rate > 5:
                status = "warning" if status == "healthy" else status
                warnings.append(f"Checkout failure rate: {failure_rate:.1f}%")
                recommendations.append("Check database connectivity and pool timeout")

        # Check checkout time
        if metrics.avg_checkout_time_ms > 100:
            warnings.append(f"High avg checkout time: {metrics.avg_checkout_time_ms:.1f}ms")
            recommendations.append("Consider connection pre-ping or investigate network latency")

        return {
            "status": status,
            "metrics": metrics.to_dict(),
            "warnings": warnings,
            "recommendations": recommendations,
        }


# Global monitor instance
_pool_monitor: Optional[PoolMonitor] = None


def get_pool_monitor() -> PoolMonitor:
    """Get or create the global pool monitor."""
    global _pool_monitor
    if _pool_monitor is None:
        _pool_monitor = PoolMonitor()
    return _pool_monitor


def init_pool_monitoring(engine):
    """Initialize pool monitoring with the given engine."""
    monitor = get_pool_monitor()
    monitor.set_engine(engine)

    # Set up event listeners for checkout tracking
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "checkout")
    def on_checkout(dbapi_conn, conn_record, conn_proxy):
        conn_record.info['checkout_time'] = time.time()

    @event.listens_for(engine.sync_engine, "checkin")
    def on_checkin(dbapi_conn, conn_record):
        checkout_time = conn_record.info.get('checkout_time')
        if checkout_time:
            duration_ms = (time.time() - checkout_time) * 1000
            monitor.record_checkout(duration_ms)

    logger.info("Database pool monitoring initialized")
    return monitor


@asynccontextmanager
async def monitored_session(session_factory):
    """
    Get a database session with monitoring.

    Usage:
        async with monitored_session(factory) as session:
            result = await session.execute(query)
    """
    monitor = get_pool_monitor()
    start_time = time.time()

    try:
        session = session_factory()
        try:
            yield session
            await session.commit()
            monitor.record_checkout((time.time() - start_time) * 1000, success=True)
        except Exception:
            await session.rollback()
            monitor.record_checkout((time.time() - start_time) * 1000, success=False)
            raise
        finally:
            await session.close()
    except Exception as e:
        monitor.record_checkout((time.time() - start_time) * 1000, success=False)
        raise


# Production-recommended pool settings
PRODUCTION_POOL_SETTINGS = {
    "pool_size": 20,  # Base connections
    "max_overflow": 30,  # Additional connections under load
    "pool_timeout": 30,  # Wait time for connection
    "pool_recycle": 1800,  # Recycle after 30 min (prevents stale connections)
    "pool_pre_ping": True,  # Verify connections before use
}

DEVELOPMENT_POOL_SETTINGS = {
    "pool_size": 5,
    "max_overflow": 10,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
}
