"""Middleware components for the tax platform.

Provides:
- Request correlation ID tracking
- Logging context enrichment
"""

from .correlation import (
    CorrelationIdMiddleware,
    get_correlation_id,
    set_correlation_id,
    correlation_id_context,
)

__all__ = [
    "CorrelationIdMiddleware",
    "get_correlation_id",
    "set_correlation_id",
    "correlation_id_context",
]
