"""Async Redis client wrapper.

Provides a high-level async interface to Redis with connection pooling,
serialization, and error handling.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Union,
)

try:
    import redis.asyncio as redis
    from redis.asyncio import ConnectionPool, Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    ConnectionPool = None
    Redis = None

from config.settings import RedisSettings, get_settings

logger = logging.getLogger(__name__)

# Global client instance
_redis_client: Optional["RedisClient"] = None


class RedisClient:
    """Async Redis client with connection pooling.

    Provides a simplified interface for common Redis operations
    with automatic serialization/deserialization and error handling.

    Usage:
        client = RedisClient()
        await client.connect()

        # String operations
        await client.set("key", {"data": "value"}, ttl=3600)
        data = await client.get("key")

        # Hash operations
        await client.hset("hash", "field", "value")
        value = await client.hget("hash", "field")

        await client.close()
    """

    def __init__(self, settings: Optional[RedisSettings] = None):
        """Initialize Redis client.

        Args:
            settings: Redis settings. Uses default if not provided.
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package is not installed. "
                "Install it with: pip install redis[hiredis]"
            )

        self.settings = settings or get_settings().redis
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._client is not None

    async def connect(self) -> None:
        """Establish connection to Redis.

        Creates a connection pool and tests connectivity.
        """
        if self._connected:
            return

        try:
            self._pool = ConnectionPool.from_url(
                self.settings.url,
                max_connections=self.settings.max_connections,
                decode_responses=True,
                socket_timeout=self.settings.socket_timeout,
                socket_connect_timeout=self.settings.socket_connect_timeout,
            )
            self._client = Redis(connection_pool=self._pool)

            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info(
                f"Connected to Redis at {self.settings.host}:{self.settings.port}"
            )

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

        if self._pool:
            await self._pool.disconnect()
            self._pool = None

        self._connected = False
        logger.info("Redis connection closed")

    async def ping(self) -> bool:
        """Check Redis connectivity.

        Returns:
            True if Redis is responsive.
        """
        if not self._client:
            return False

        try:
            return await self._client.ping()
        except Exception:
            return False

    def _serialize(self, value: Any) -> str:
        """Serialize value for storage.

        Args:
            value: Value to serialize.

        Returns:
            JSON string.
        """
        return json.dumps(value, default=str)

    def _deserialize(self, data: Optional[str]) -> Any:
        """Deserialize value from storage.

        Args:
            data: JSON string or None.

        Returns:
            Deserialized value or None.
        """
        if data is None:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data

    # String operations

    async def get(self, key: str) -> Any:
        """Get a value by key.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found.
        """
        if not self._client:
            return None

        try:
            prefix = self.settings.key_prefix
            full_key = f"{prefix}{key}" if prefix else key
            data = await self._client.get(full_key)
            return self._deserialize(data)
        except Exception as e:
            logger.warning(f"Redis GET error for {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """Set a value with optional TTL.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time-to-live in seconds or timedelta.

        Returns:
            True if successful.
        """
        if not self._client:
            return False

        try:
            prefix = self.settings.key_prefix
            full_key = f"{prefix}{key}" if prefix else key
            serialized = self._serialize(value)

            if ttl is None:
                ttl = self.settings.default_ttl

            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())

            await self._client.set(full_key, serialized, ex=ttl)
            return True

        except Exception as e:
            logger.warning(f"Redis SET error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key: Cache key.

        Returns:
            True if key was deleted.
        """
        if not self._client:
            return False

        try:
            prefix = self.settings.key_prefix
            full_key = f"{prefix}{key}" if prefix else key
            result = await self._client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.warning(f"Redis DELETE error for {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists.

        Args:
            key: Cache key.

        Returns:
            True if key exists.
        """
        if not self._client:
            return False

        try:
            prefix = self.settings.key_prefix
            full_key = f"{prefix}{key}" if prefix else key
            return await self._client.exists(full_key) > 0
        except Exception as e:
            logger.warning(f"Redis EXISTS error for {key}: {e}")
            return False

    async def expire(self, key: str, ttl: Union[int, timedelta]) -> bool:
        """Set TTL on existing key.

        Args:
            key: Cache key.
            ttl: Time-to-live in seconds or timedelta.

        Returns:
            True if TTL was set.
        """
        if not self._client:
            return False

        try:
            prefix = self.settings.key_prefix
            full_key = f"{prefix}{key}" if prefix else key

            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())

            return await self._client.expire(full_key, ttl)
        except Exception as e:
            logger.warning(f"Redis EXPIRE error for {key}: {e}")
            return False

    # Hash operations

    async def hget(self, name: str, key: str) -> Any:
        """Get a field from a hash.

        Args:
            name: Hash name.
            key: Field key.

        Returns:
            Field value or None.
        """
        if not self._client:
            return None

        try:
            prefix = self.settings.key_prefix
            full_name = f"{prefix}{name}" if prefix else name
            data = await self._client.hget(full_name, key)
            return self._deserialize(data)
        except Exception as e:
            logger.warning(f"Redis HGET error for {name}:{key}: {e}")
            return None

    async def hset(self, name: str, key: str, value: Any) -> bool:
        """Set a field in a hash.

        Args:
            name: Hash name.
            key: Field key.
            value: Field value.

        Returns:
            True if successful.
        """
        if not self._client:
            return False

        try:
            prefix = self.settings.key_prefix
            full_name = f"{prefix}{name}" if prefix else name
            serialized = self._serialize(value)
            await self._client.hset(full_name, key, serialized)
            return True
        except Exception as e:
            logger.warning(f"Redis HSET error for {name}:{key}: {e}")
            return False

    async def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all fields from a hash.

        Args:
            name: Hash name.

        Returns:
            Dict of field names to values.
        """
        if not self._client:
            return {}

        try:
            prefix = self.settings.key_prefix
            full_name = f"{prefix}{name}" if prefix else name
            data = await self._client.hgetall(full_name)
            return {k: self._deserialize(v) for k, v in data.items()}
        except Exception as e:
            logger.warning(f"Redis HGETALL error for {name}: {e}")
            return {}

    async def hdel(self, name: str, *keys: str) -> int:
        """Delete fields from a hash.

        Args:
            name: Hash name.
            *keys: Field keys to delete.

        Returns:
            Number of fields deleted.
        """
        if not self._client or not keys:
            return 0

        try:
            prefix = self.settings.key_prefix
            full_name = f"{prefix}{name}" if prefix else name
            return await self._client.hdel(full_name, *keys)
        except Exception as e:
            logger.warning(f"Redis HDEL error for {name}: {e}")
            return 0

    # Bulk operations

    async def mget(self, *keys: str) -> List[Any]:
        """Get multiple keys.

        Args:
            *keys: Cache keys.

        Returns:
            List of values (None for missing keys).
        """
        if not self._client or not keys:
            return [None] * len(keys)

        try:
            prefix = self.settings.key_prefix
            full_keys = [f"{prefix}{k}" if prefix else k for k in keys]
            data = await self._client.mget(full_keys)
            return [self._deserialize(d) for d in data]
        except Exception as e:
            logger.warning(f"Redis MGET error: {e}")
            return [None] * len(keys)

    async def mset(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """Set multiple keys.

        Args:
            mapping: Dict of key-value pairs.
            ttl: Optional TTL for all keys.

        Returns:
            True if successful.
        """
        if not self._client or not mapping:
            return False

        try:
            prefix = self.settings.key_prefix
            serialized = {
                f"{prefix}{k}" if prefix else k: self._serialize(v)
                for k, v in mapping.items()
            }
            await self._client.mset(serialized)

            # Set TTL if provided
            if ttl is not None:
                if isinstance(ttl, timedelta):
                    ttl = int(ttl.total_seconds())
                for key in serialized:
                    await self._client.expire(key, ttl)

            return True

        except Exception as e:
            logger.warning(f"Redis MSET error: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Glob-style pattern (e.g., "calc:*").

        Returns:
            Number of keys deleted.
        """
        if not self._client:
            return 0

        try:
            prefix = self.settings.key_prefix
            full_pattern = f"{prefix}{pattern}" if prefix else pattern

            deleted = 0
            async for key in self._client.scan_iter(match=full_pattern):
                await self._client.delete(key)
                deleted += 1

            return deleted

        except Exception as e:
            logger.warning(f"Redis DELETE PATTERN error for {pattern}: {e}")
            return 0

    async def flush_all(self) -> bool:
        """Flush all data (use with caution!).

        Returns:
            True if successful.
        """
        if not self._client:
            return False

        try:
            await self._client.flushdb()
            logger.warning("Redis database flushed")
            return True
        except Exception as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            return False


async def get_redis_client() -> RedisClient:
    """Get or create the global Redis client.

    Returns:
        Connected RedisClient instance.
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()

    return _redis_client


async def close_redis_client() -> None:
    """Close the global Redis client."""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None


async def redis_health_check() -> Dict[str, Any]:
    """Perform Redis health check.

    Returns:
        Health check result dict.
    """
    try:
        client = await get_redis_client()
        is_healthy = await client.ping()

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "connected": client.is_connected,
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }


@asynccontextmanager
async def redis_connection() -> AsyncGenerator[RedisClient, None]:
    """Context manager for Redis connection.

    Usage:
        async with redis_connection() as client:
            await client.set("key", "value")

    Yields:
        Connected RedisClient.
    """
    client = await get_redis_client()
    try:
        yield client
    finally:
        pass  # Don't close global client
