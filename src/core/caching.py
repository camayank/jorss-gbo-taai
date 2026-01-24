"""
Simple In-Memory Cache for Performance Optimization

Provides:
1. Time-based expiration
2. Automatic cleanup
3. Thread-safe operations
4. Optional Redis backend (for production scaling)

Usage:
    from core.caching import cache, cached

    # Manual cache operations
    cache.set("key", value, ttl=60)
    value = cache.get("key")

    # Decorator for automatic caching
    @cached(ttl=300)
    def get_dashboard_stats(cpa_id):
        return expensive_query()
"""

from __future__ import annotations

import time
import threading
import functools
import hashlib
import json
import logging
from typing import Optional, Any, Dict, Callable, TypeVar
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheEntry:
    """A cached value with expiration."""

    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expires_at = time.time() + ttl
        self.created_at = time.time()
        self.hits = 0

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def touch(self):
        """Record a cache hit."""
        self.hits += 1


class MemoryCache:
    """
    Thread-safe in-memory cache with TTL.

    Good for single-instance deployments. For multi-instance,
    use Redis backend.
    """

    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds (5 min)
            max_size: Maximum number of entries before cleanup
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found or expired

        Returns:
            Cached value or default
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats["misses"] += 1
                return default

            if entry.is_expired():
                del self._cache[key]
                self._stats["misses"] += 1
                return default

            entry.touch()
            self._stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        if ttl is None:
            ttl = self._default_ttl

        with self._lock:
            # Cleanup if at max size
            if len(self._cache) >= self._max_size:
                self._cleanup()

            self._cache[key] = CacheEntry(value, ttl)
            self._stats["sets"] += 1

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Returns:
            True if key existed, False otherwise
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        """
        Clear all cached entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern.

        Args:
            pattern: Prefix to match (e.g., "dashboard:" invalidates all dashboard keys)

        Returns:
            Number of keys invalidated
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    def _cleanup(self) -> int:
        """Remove expired entries and oldest entries if still at max size."""
        now = time.time()
        expired = []
        oldest = []

        # Find expired entries
        for key, entry in self._cache.items():
            if entry.is_expired():
                expired.append(key)
            else:
                oldest.append((key, entry.created_at))

        # Remove expired
        for key in expired:
            del self._cache[key]
            self._stats["evictions"] += 1

        # If still at max, remove oldest 10%
        if len(self._cache) >= self._max_size:
            oldest.sort(key=lambda x: x[1])
            to_remove = oldest[:max(1, len(oldest) // 10)]
            for key, _ in to_remove:
                del self._cache[key]
                self._stats["evictions"] += 1

        return len(expired) + len(oldest)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0

            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self._max_size,
                "hit_rate_percent": round(hit_rate, 2),
            }


# Global cache instance
cache = MemoryCache()


def make_cache_key(*args, **kwargs) -> str:
    """
    Generate a cache key from function arguments.

    Uses JSON serialization for consistent key generation.
    """
    key_data = {
        "args": args,
        "kwargs": sorted(kwargs.items()),
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()[:16]


def cached(
    ttl: int = 300,
    key_prefix: Optional[str] = None,
    skip_args: int = 0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for automatic function result caching.

    Args:
        ttl: Time-to-live in seconds (default 5 min)
        key_prefix: Optional prefix for cache key (defaults to function name)
        skip_args: Number of initial args to skip in key generation
                   (useful for skipping 'self' in methods)

    Usage:
        @cached(ttl=60)
        def get_user(user_id: str):
            return db.query(User).get(user_id)

        @cached(ttl=300, key_prefix="dashboard")
        def get_dashboard_stats(cpa_id: str):
            return calculate_stats(cpa_id)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        prefix = key_prefix or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Generate cache key
            cache_args = args[skip_args:]
            cache_key = f"{prefix}:{make_cache_key(*cache_args, **kwargs)}"

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)

            return result

        # Add cache control methods
        wrapper.invalidate = lambda *a, **kw: cache.delete(
            f"{prefix}:{make_cache_key(*a, **kw)}"
        )
        wrapper.invalidate_all = lambda: cache.invalidate_pattern(f"{prefix}:")

        return wrapper

    return decorator


def cached_method(
    ttl: int = 300,
    key_prefix: Optional[str] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for caching instance method results.

    Automatically skips 'self' in key generation.

    Usage:
        class DashboardService:
            @cached_method(ttl=60)
            def get_stats(self, cpa_id: str):
                return self.calculate_stats(cpa_id)
    """
    return cached(ttl=ttl, key_prefix=key_prefix, skip_args=1)


# Cache invalidation helpers for common patterns

def invalidate_lead_cache(lead_id: str) -> None:
    """Invalidate all cache entries related to a lead."""
    cache.invalidate_pattern(f"lead:{lead_id}")
    cache.invalidate_pattern("dashboard:")  # Dashboard stats may include this lead
    cache.invalidate_pattern("leads:")  # Lead list caches


def invalidate_cpa_cache(cpa_id: str) -> None:
    """Invalidate all cache entries for a CPA."""
    cache.invalidate_pattern(f"cpa:{cpa_id}")
    cache.invalidate_pattern(f"dashboard:{cpa_id}")
    cache.invalidate_pattern(f"leads:{cpa_id}")


def invalidate_tenant_cache(tenant_id: str) -> None:
    """Invalidate all cache entries for a tenant."""
    cache.invalidate_pattern(f"tenant:{tenant_id}")
