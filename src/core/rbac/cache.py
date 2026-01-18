"""
Permission Cache - Multi-layer caching for permission resolution.

Three-Layer Cache Strategy:
1. Request-level: request.state (no serialization overhead)
2. Process-level: LRU cache (1000 entries, 5-min TTL)
3. Redis: Distributed cache (15-min TTL) - optional

Cache Invalidation:
- Version-based invalidation (increment on change)
- Scope-based: user, firm, or global invalidation
- Redis pub/sub for cross-worker notification
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum as PyEnum
from functools import lru_cache
from typing import Optional, Dict, Set, Any, List, Callable
from uuid import UUID
import logging
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =============================================================================
# CACHE CONFIGURATION
# =============================================================================

class CacheScope(str, PyEnum):
    """Cache invalidation scopes."""
    GLOBAL = "global"
    FIRM = "firm"
    USER = "user"


@dataclass
class CacheConfig:
    """Cache configuration settings."""
    # Process-level cache
    process_cache_size: int = 1000
    process_cache_ttl_seconds: int = 300  # 5 minutes

    # Redis cache (if available)
    redis_cache_ttl_seconds: int = 900  # 15 minutes
    redis_enabled: bool = False
    redis_prefix: str = "rbac:perms:"

    # Invalidation
    invalidation_channel: str = "rbac:invalidate"


DEFAULT_CONFIG = CacheConfig()


# =============================================================================
# CACHE ENTRY
# =============================================================================

@dataclass
class CacheEntry:
    """Cached permission data."""
    permissions: Set[str]
    roles: List[str]
    primary_role: Optional[str]
    hierarchy_level: int
    version: int
    cached_at: float
    expires_at: float

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for Redis."""
        return {
            "permissions": list(self.permissions),
            "roles": self.roles,
            "primary_role": self.primary_role,
            "hierarchy_level": self.hierarchy_level,
            "version": self.version,
            "cached_at": self.cached_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Deserialize from dictionary."""
        return cls(
            permissions=set(data["permissions"]),
            roles=data["roles"],
            primary_role=data.get("primary_role"),
            hierarchy_level=data["hierarchy_level"],
            version=data["version"],
            cached_at=data["cached_at"],
            expires_at=data["expires_at"],
        )


# =============================================================================
# PROCESS-LEVEL CACHE (LRU with TTL)
# =============================================================================

class TTLCache:
    """
    Thread-safe LRU cache with TTL expiration.

    Provides process-level caching without Redis dependency.
    """

    def __init__(self, maxsize: int = 1000, ttl_seconds: int = 300):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry from cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            if entry.is_expired():
                self._remove(key)
                return None

            # Move to end (LRU)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            return entry

    def set(self, key: str, entry: CacheEntry) -> None:
        """Set entry in cache."""
        with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.maxsize:
                if self._access_order:
                    oldest = self._access_order.pop(0)
                    self._cache.pop(oldest, None)
                else:
                    break

            self._cache[key] = entry
            if key not in self._access_order:
                self._access_order.append(key)

    def invalidate(self, key: str) -> None:
        """Remove entry from cache."""
        with self._lock:
            self._remove(key)

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all entries matching prefix."""
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                self._remove(key)
            return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def _remove(self, key: str) -> None:
        """Remove a key (must hold lock)."""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "maxsize": self.maxsize,
                "ttl_seconds": self.ttl_seconds,
            }


# =============================================================================
# REDIS CACHE ADAPTER
# =============================================================================

class RedisCacheAdapter:
    """
    Redis cache adapter for distributed caching.

    Optional - falls back gracefully if Redis unavailable.
    """

    def __init__(
        self,
        redis_client: Any = None,
        prefix: str = "rbac:perms:",
        ttl_seconds: int = 900,
    ):
        self.redis = redis_client
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds
        self._enabled = redis_client is not None

    @property
    def enabled(self) -> bool:
        """Check if Redis is available."""
        return self._enabled

    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry from Redis."""
        if not self._enabled:
            return None

        try:
            full_key = f"{self.prefix}{key}"
            data = self.redis.get(full_key)
            if data:
                return CacheEntry.from_dict(json.loads(data))
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

        return None

    def set(self, key: str, entry: CacheEntry) -> None:
        """Set entry in Redis."""
        if not self._enabled:
            return

        try:
            full_key = f"{self.prefix}{key}"
            data = json.dumps(entry.to_dict())
            self.redis.setex(full_key, self.ttl_seconds, data)
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

    def invalidate(self, key: str) -> None:
        """Remove entry from Redis."""
        if not self._enabled:
            return

        try:
            full_key = f"{self.prefix}{key}"
            self.redis.delete(full_key)
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")

    def invalidate_pattern(self, pattern: str) -> int:
        """Remove entries matching pattern."""
        if not self._enabled:
            return 0

        try:
            full_pattern = f"{self.prefix}{pattern}"
            keys = self.redis.keys(full_pattern)
            if keys:
                return self.redis.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis pattern delete error: {e}")

        return 0

    def publish_invalidation(self, scope: str, scope_id: str) -> None:
        """Publish invalidation message for cross-worker notification."""
        if not self._enabled:
            return

        try:
            message = json.dumps({"scope": scope, "scope_id": scope_id, "ts": time.time()})
            self.redis.publish("rbac:invalidate", message)
        except Exception as e:
            logger.warning(f"Redis publish error: {e}")


# =============================================================================
# VERSION TRACKER
# =============================================================================

class VersionTracker:
    """
    Tracks cache versions for invalidation.

    Versions are stored in database and checked on cache read.
    """

    def __init__(self, db_session_factory: Callable[[], Session]):
        self._session_factory = db_session_factory
        self._local_versions: Dict[str, int] = {}
        self._lock = threading.RLock()

    def get_version(self, scope: str) -> int:
        """Get current version for a scope."""
        from .models import PermissionCacheVersion

        try:
            with self._session_factory() as db:
                stmt = select(PermissionCacheVersion.version).where(
                    PermissionCacheVersion.scope == scope
                )
                result = db.execute(stmt)
                version = result.scalar_one_or_none()
                return version or 0
        except Exception as e:
            logger.warning(f"Error getting cache version: {e}")
            return 0

    def get_local_version(self, scope: str) -> int:
        """Get locally cached version."""
        with self._lock:
            return self._local_versions.get(scope, 0)

    def set_local_version(self, scope: str, version: int) -> None:
        """Update local version cache."""
        with self._lock:
            self._local_versions[scope] = version

    def is_stale(self, scope: str, cached_version: int) -> bool:
        """Check if cached version is stale."""
        current = self.get_version(scope)
        return cached_version < current


# =============================================================================
# PERMISSION CACHE SERVICE
# =============================================================================

class PermissionCache:
    """
    Multi-layer permission cache.

    Layer 1: Request-level (request.state) - instant, no lookup
    Layer 2: Process-level (TTLCache) - fast, process-local
    Layer 3: Redis (optional) - distributed, cross-worker

    Cache keys: "user:{user_id}:firm:{firm_id}:tier:{tier}"
    """

    def __init__(
        self,
        config: Optional[CacheConfig] = None,
        redis_client: Any = None,
        db_session_factory: Optional[Callable[[], Session]] = None,
    ):
        self.config = config or DEFAULT_CONFIG

        # Process-level cache
        self._process_cache = TTLCache(
            maxsize=self.config.process_cache_size,
            ttl_seconds=self.config.process_cache_ttl_seconds,
        )

        # Redis cache (optional)
        self._redis_cache = RedisCacheAdapter(
            redis_client=redis_client,
            prefix=self.config.redis_prefix,
            ttl_seconds=self.config.redis_cache_ttl_seconds,
        ) if redis_client else None

        # Version tracker
        self._version_tracker = VersionTracker(db_session_factory) if db_session_factory else None

    def get_cache_key(
        self,
        user_id: UUID,
        firm_id: Optional[UUID] = None,
        subscription_tier: str = "starter",
    ) -> str:
        """Generate cache key for user permissions."""
        parts = [f"user:{user_id}"]
        if firm_id:
            parts.append(f"firm:{firm_id}")
        parts.append(f"tier:{subscription_tier}")
        return ":".join(parts)

    def get(
        self,
        user_id: UUID,
        firm_id: Optional[UUID] = None,
        subscription_tier: str = "starter",
    ) -> Optional[CacheEntry]:
        """
        Get cached permissions.

        Checks layers in order: process → Redis
        Validates version to ensure not stale.
        """
        key = self.get_cache_key(user_id, firm_id, subscription_tier)

        # Layer 2: Process-level cache
        entry = self._process_cache.get(key)
        if entry:
            # Version check
            if self._is_entry_valid(entry, user_id, firm_id):
                return entry
            # Stale - invalidate
            self._process_cache.invalidate(key)

        # Layer 3: Redis cache
        if self._redis_cache and self._redis_cache.enabled:
            entry = self._redis_cache.get(key)
            if entry and not entry.is_expired():
                if self._is_entry_valid(entry, user_id, firm_id):
                    # Populate process cache
                    self._process_cache.set(key, entry)
                    return entry
                # Stale - invalidate
                self._redis_cache.invalidate(key)

        return None

    def set(
        self,
        user_id: UUID,
        permissions: Set[str],
        roles: List[str],
        primary_role: Optional[str],
        hierarchy_level: int,
        firm_id: Optional[UUID] = None,
        subscription_tier: str = "starter",
    ) -> None:
        """Cache resolved permissions."""
        key = self.get_cache_key(user_id, firm_id, subscription_tier)
        now = time.time()

        # Get current versions
        user_version = self._get_scope_version(f"user:{user_id}")
        firm_version = self._get_scope_version(f"firm:{firm_id}") if firm_id else 0
        version = max(user_version, firm_version)

        entry = CacheEntry(
            permissions=permissions,
            roles=roles,
            primary_role=primary_role,
            hierarchy_level=hierarchy_level,
            version=version,
            cached_at=now,
            expires_at=now + self.config.process_cache_ttl_seconds,
        )

        # Layer 2: Process cache
        self._process_cache.set(key, entry)

        # Layer 3: Redis cache
        if self._redis_cache and self._redis_cache.enabled:
            entry.expires_at = now + self.config.redis_cache_ttl_seconds
            self._redis_cache.set(key, entry)

    def invalidate_user(self, user_id: UUID) -> int:
        """Invalidate all cache entries for a user."""
        pattern = f"user:{user_id}:*"
        count = self._process_cache.invalidate_prefix(pattern)

        if self._redis_cache and self._redis_cache.enabled:
            count += self._redis_cache.invalidate_pattern(f"{pattern}*")
            self._redis_cache.publish_invalidation("user", str(user_id))

        logger.debug(f"Invalidated {count} cache entries for user {user_id}")
        return count

    def invalidate_firm(self, firm_id: UUID) -> int:
        """Invalidate all cache entries for a firm."""
        pattern = f"*firm:{firm_id}:*"
        count = self._process_cache.invalidate_prefix(pattern)

        if self._redis_cache and self._redis_cache.enabled:
            count += self._redis_cache.invalidate_pattern(f"*firm:{firm_id}:*")
            self._redis_cache.publish_invalidation("firm", str(firm_id))

        logger.debug(f"Invalidated {count} cache entries for firm {firm_id}")
        return count

    def invalidate_global(self) -> int:
        """Invalidate all cache entries."""
        self._process_cache.clear()
        count = self._process_cache.stats()["size"]

        if self._redis_cache and self._redis_cache.enabled:
            count += self._redis_cache.invalidate_pattern("*")
            self._redis_cache.publish_invalidation("global", "*")

        logger.info(f"Invalidated all RBAC cache entries")
        return count

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "process_cache": self._process_cache.stats(),
            "redis_enabled": self._redis_cache.enabled if self._redis_cache else False,
        }

    def _is_entry_valid(
        self,
        entry: CacheEntry,
        user_id: UUID,
        firm_id: Optional[UUID],
    ) -> bool:
        """Check if cache entry is still valid based on version."""
        if not self._version_tracker:
            return True  # No version tracking, assume valid

        # Check user version
        user_scope = f"user:{user_id}"
        current_user_version = self._version_tracker.get_local_version(user_scope)
        if entry.version < current_user_version:
            return False

        # Check firm version
        if firm_id:
            firm_scope = f"firm:{firm_id}"
            current_firm_version = self._version_tracker.get_local_version(firm_scope)
            if entry.version < current_firm_version:
                return False

        return True

    def _get_scope_version(self, scope: str) -> int:
        """Get version for a scope."""
        if self._version_tracker:
            return self._version_tracker.get_version(scope)
        return 0


# =============================================================================
# SINGLETON
# =============================================================================

_permission_cache: Optional[PermissionCache] = None


def get_permission_cache(
    redis_client: Any = None,
    db_session_factory: Optional[Callable[[], Session]] = None,
) -> PermissionCache:
    """Get singleton permission cache instance."""
    global _permission_cache
    if _permission_cache is None:
        _permission_cache = PermissionCache(
            redis_client=redis_client,
            db_session_factory=db_session_factory,
        )
    return _permission_cache


def reset_permission_cache() -> None:
    """Reset singleton (for testing)."""
    global _permission_cache
    _permission_cache = None
