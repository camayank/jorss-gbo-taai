"""Cache-aside pattern for tax calculations.

Provides caching for expensive tax calculations with automatic
invalidation triggers.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
)

from .redis_client import RedisClient, get_redis_client

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default TTL for cached calculations (1 hour)
DEFAULT_CALCULATION_TTL = 3600

# Cache key prefixes
CALC_PREFIX = "calc:"
RETURN_PREFIX = "return:"
SCENARIO_PREFIX = "scenario:"


class CalculationCache:
    """Cache for tax calculation results.

    Implements cache-aside pattern with automatic invalidation
    for tax return calculations.

    Usage:
        cache = CalculationCache()
        await cache.connect()

        # Cache a calculation result
        await cache.set_calculation(return_id, calculation_result)

        # Get cached result
        result = await cache.get_calculation(return_id)

        # Invalidate on data change
        await cache.invalidate_return(return_id)
    """

    def __init__(
        self,
        client: Optional[RedisClient] = None,
        ttl: int = DEFAULT_CALCULATION_TTL,
    ):
        """Initialize calculation cache.

        Args:
            client: Redis client (creates new if not provided).
            ttl: Default TTL for cached calculations in seconds.
        """
        self._client = client
        self._ttl = ttl

    async def connect(self) -> None:
        """Ensure Redis connection is established."""
        if self._client is None:
            self._client = await get_redis_client()

    @property
    def client(self) -> RedisClient:
        """Get Redis client."""
        if self._client is None:
            raise RuntimeError(
                "Cache not connected. Call connect() first."
            )
        return self._client

    def _make_calc_key(self, return_id: str) -> str:
        """Make cache key for calculation result."""
        return f"{CALC_PREFIX}{return_id}"

    def _make_return_key(self, return_id: str) -> str:
        """Make cache key for return data."""
        return f"{RETURN_PREFIX}{return_id}"

    def _make_scenario_key(self, return_id: str, scenario_id: str) -> str:
        """Make cache key for scenario calculation."""
        return f"{SCENARIO_PREFIX}{return_id}:{scenario_id}"

    def _hash_context(self, context: Dict[str, Any]) -> str:
        """Create hash of context for cache key.

        Args:
            context: Context dict to hash.

        Returns:
            Hex hash string.
        """
        # Sort keys for consistent hashing
        serialized = json.dumps(context, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    # Calculation caching

    async def get_calculation(
        self,
        return_id: str,
        context_hash: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get cached calculation result.

        Args:
            return_id: Tax return ID.
            context_hash: Optional context hash for versioning.

        Returns:
            Cached calculation result or None.
        """
        await self.connect()

        key = self._make_calc_key(return_id)
        if context_hash:
            key = f"{key}:{context_hash}"

        result = await self.client.get(key)

        if result:
            logger.debug(f"Cache HIT for calculation {return_id}")
        else:
            logger.debug(f"Cache MISS for calculation {return_id}")

        return result

    async def set_calculation(
        self,
        return_id: str,
        calculation: Dict[str, Any],
        context_hash: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache a calculation result.

        Args:
            return_id: Tax return ID.
            calculation: Calculation result to cache.
            context_hash: Optional context hash for versioning.
            ttl: Optional TTL override.

        Returns:
            True if cached successfully.
        """
        await self.connect()

        key = self._make_calc_key(return_id)
        if context_hash:
            key = f"{key}:{context_hash}"

        success = await self.client.set(
            key,
            calculation,
            ttl=ttl or self._ttl,
        )

        if success:
            logger.debug(f"Cached calculation for {return_id}")

        return success

    async def invalidate_calculation(self, return_id: str) -> bool:
        """Invalidate cached calculation.

        Args:
            return_id: Tax return ID.

        Returns:
            True if invalidated.
        """
        await self.connect()

        # Delete main calculation and any versioned entries
        pattern = f"{CALC_PREFIX}{return_id}*"
        deleted = await self.client.delete_pattern(pattern)

        if deleted > 0:
            logger.info(
                f"Invalidated {deleted} cached calculations for {return_id}"
            )

        return deleted > 0

    # Return data caching

    async def get_return_data(
        self,
        return_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get cached return data.

        Args:
            return_id: Tax return ID.

        Returns:
            Cached return data or None.
        """
        await self.connect()
        return await self.client.get(self._make_return_key(return_id))

    async def set_return_data(
        self,
        return_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache return data.

        Args:
            return_id: Tax return ID.
            data: Return data to cache.
            ttl: Optional TTL override.

        Returns:
            True if cached successfully.
        """
        await self.connect()
        return await self.client.set(
            self._make_return_key(return_id),
            data,
            ttl=ttl or self._ttl,
        )

    async def invalidate_return(self, return_id: str) -> int:
        """Invalidate all cached data for a return.

        This invalidates:
        - Calculation results
        - Return data
        - All scenario calculations

        Args:
            return_id: Tax return ID.

        Returns:
            Number of cache entries invalidated.
        """
        await self.connect()

        deleted = 0

        # Invalidate calculation
        if await self.invalidate_calculation(return_id):
            deleted += 1

        # Invalidate return data
        if await self.client.delete(self._make_return_key(return_id)):
            deleted += 1

        # Invalidate scenarios
        pattern = f"{SCENARIO_PREFIX}{return_id}:*"
        deleted += await self.client.delete_pattern(pattern)

        logger.info(f"Invalidated {deleted} cache entries for return {return_id}")
        return deleted

    # Scenario caching

    async def get_scenario_calculation(
        self,
        return_id: str,
        scenario_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get cached scenario calculation.

        Args:
            return_id: Tax return ID.
            scenario_id: Scenario ID.

        Returns:
            Cached scenario result or None.
        """
        await self.connect()
        return await self.client.get(
            self._make_scenario_key(return_id, scenario_id)
        )

    async def set_scenario_calculation(
        self,
        return_id: str,
        scenario_id: str,
        calculation: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache a scenario calculation.

        Args:
            return_id: Tax return ID.
            scenario_id: Scenario ID.
            calculation: Calculation result.
            ttl: Optional TTL override.

        Returns:
            True if cached successfully.
        """
        await self.connect()
        return await self.client.set(
            self._make_scenario_key(return_id, scenario_id),
            calculation,
            ttl=ttl or self._ttl,
        )

    async def invalidate_scenarios(self, return_id: str) -> int:
        """Invalidate all scenarios for a return.

        Args:
            return_id: Tax return ID.

        Returns:
            Number of scenarios invalidated.
        """
        await self.connect()
        pattern = f"{SCENARIO_PREFIX}{return_id}:*"
        return await self.client.delete_pattern(pattern)

    # Bulk operations

    async def warmup_return(
        self,
        return_id: str,
        return_data: Dict[str, Any],
        calculation: Dict[str, Any],
    ) -> bool:
        """Warm up cache with return data and calculation.

        Args:
            return_id: Tax return ID.
            return_data: Return data to cache.
            calculation: Calculation result to cache.

        Returns:
            True if all cached successfully.
        """
        await self.connect()

        success = True
        success = success and await self.set_return_data(return_id, return_data)
        success = success and await self.set_calculation(return_id, calculation)

        return success

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache stats.
        """
        await self.connect()

        # This is a simplified version - in production you'd want
        # more detailed stats from Redis INFO command
        return {
            "connected": self.client.is_connected,
            "ttl_seconds": self._ttl,
        }


# Global cache instance
_calculation_cache: Optional[CalculationCache] = None


async def get_calculation_cache() -> CalculationCache:
    """Get or create global calculation cache.

    Returns:
        Connected CalculationCache instance.
    """
    global _calculation_cache

    if _calculation_cache is None:
        _calculation_cache = CalculationCache()
        await _calculation_cache.connect()

    return _calculation_cache


def cached_calculation(
    ttl: Optional[int] = None,
    key_func: Optional[Callable[..., str]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for caching calculation functions.

    Usage:
        @cached_calculation(ttl=3600)
        async def calculate_tax(return_id: str, data: dict) -> dict:
            # Expensive calculation
            return result

    Args:
        ttl: Cache TTL in seconds.
        key_func: Optional function to generate cache key from args.

    Returns:
        Decorator function.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            cache = await get_calculation_cache()

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: use first positional arg as return_id
                cache_key = str(args[0]) if args else "default"

            # Check cache
            cached = await cache.get_calculation(cache_key)
            if cached is not None:
                return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            if result is not None:
                await cache.set_calculation(
                    cache_key,
                    result,
                    ttl=ttl,
                )

            return result

        return wrapper
    return decorator


class CacheInvalidator:
    """Helper for triggering cache invalidation.

    Used to invalidate caches when data changes occur.

    Usage:
        invalidator = CacheInvalidator()

        # In service layer when data changes
        async def update_return(self, return_id: str, data: dict):
            await self.repository.save(return_id, data)
            await invalidator.on_return_updated(return_id)
    """

    def __init__(self, cache: Optional[CalculationCache] = None):
        """Initialize invalidator.

        Args:
            cache: Cache instance (uses global if not provided).
        """
        self._cache = cache

    async def get_cache(self) -> CalculationCache:
        """Get cache instance."""
        if self._cache is None:
            self._cache = await get_calculation_cache()
        return self._cache

    async def on_return_updated(self, return_id: str) -> None:
        """Handle return data update.

        Invalidates calculation cache for the return.

        Args:
            return_id: Updated return ID.
        """
        cache = await self.get_cache()
        await cache.invalidate_return(return_id)
        logger.debug(f"Cache invalidated for return update: {return_id}")

    async def on_return_deleted(self, return_id: str) -> None:
        """Handle return deletion.

        Args:
            return_id: Deleted return ID.
        """
        cache = await self.get_cache()
        await cache.invalidate_return(return_id)
        logger.debug(f"Cache invalidated for return deletion: {return_id}")

    async def on_config_changed(self) -> None:
        """Handle configuration change (e.g., tax brackets).

        Invalidates all calculation caches.
        """
        cache = await self.get_cache()
        # Delete all calculation caches
        deleted = await cache.client.delete_pattern(f"{CALC_PREFIX}*")
        logger.warning(f"Config changed: invalidated {deleted} calculation caches")

    async def on_prior_year_updated(
        self,
        return_id: str,
        prior_year_return_id: str,
    ) -> None:
        """Handle prior year data update.

        Some calculations depend on prior year data, so we invalidate
        when prior year changes.

        Args:
            return_id: Current year return ID.
            prior_year_return_id: Prior year return ID.
        """
        cache = await self.get_cache()
        await cache.invalidate_calculation(return_id)
        logger.debug(
            f"Cache invalidated for prior year update: "
            f"{return_id} (prior: {prior_year_return_id})"
        )
