"""Cache layer for the tax platform.

Provides Redis-based caching for expensive calculations
and frequently accessed data.
"""

from .redis_client import (
    RedisClient,
    get_redis_client,
    close_redis_client,
    redis_health_check,
)

from .calculation_cache import (
    CalculationCache,
    get_calculation_cache,
    cached_calculation,
    CacheInvalidator,
    DEFAULT_CALCULATION_TTL,
)

__all__ = [
    # Redis Client
    "RedisClient",
    "get_redis_client",
    "close_redis_client",
    "redis_health_check",
    # Calculation Cache
    "CalculationCache",
    "get_calculation_cache",
    "cached_calculation",
    "CacheInvalidator",
    "DEFAULT_CALCULATION_TTL",
]
