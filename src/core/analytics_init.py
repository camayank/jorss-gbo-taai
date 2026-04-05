"""
Analytics Service Initialization

Wire up the AnalyticsEventService at application startup to enable
persistent event storage for CPA dashboard analytics.

Usage:
    from core.analytics_init import initialize_analytics_service
    from database.async_engine import get_async_session_factory

    # In FastAPI lifespan or startup handler:
    session_factory = get_async_session_factory()
    initialize_analytics_service(session_factory)
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.services.analytics_event_service import AnalyticsEventService

logger = logging.getLogger(__name__)

# Global analytics service instance
_analytics_service: Optional[AnalyticsEventService] = None


def initialize_analytics_service(session_factory: async_sessionmaker) -> AnalyticsEventService:
    """Initialize and register the analytics event service.

    Args:
        session_factory: Async SQLAlchemy session factory

    Returns:
        Initialized AnalyticsEventService instance
    """
    global _analytics_service

    if _analytics_service is None:
        _analytics_service = AnalyticsEventService(session_factory)
        _analytics_service.register_handlers()
        logger.info("[Analytics] Event persistence service initialized")
    else:
        logger.warning("[Analytics] Service already initialized, skipping")

    return _analytics_service


def get_analytics_service() -> Optional[AnalyticsEventService]:
    """Get the global analytics service instance."""
    return _analytics_service
