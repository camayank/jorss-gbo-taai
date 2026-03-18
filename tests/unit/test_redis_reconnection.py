"""
Tests for Redis session persistence singleton/reconnection logic.

Validates the get_redis_session_persistence() factory function behavior:
- Caches and returns existing instance when Redis ping succeeds
- Forces re-initialization when ping fails (reconnection)
- Creates new instance on first call
- Sets cached instance to None on ping failure
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import database.redis_session_persistence as redis_mod


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the module-level singleton before each test."""
    redis_mod._redis_session_persistence = None
    yield
    redis_mod._redis_session_persistence = None


@pytest.mark.asyncio
async def test_factory_returns_cached_instance_when_ping_succeeds():
    """When a cached instance exists and ping succeeds, return the same instance."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    # Pre-populate the singleton
    existing_instance = redis_mod.RedisSessionPersistence(mock_redis)
    redis_mod._redis_session_persistence = existing_instance

    result = await redis_mod.get_redis_session_persistence()

    assert result is existing_instance
    mock_redis.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_factory_creates_new_instance_when_ping_fails():
    """When cached instance exists but ping fails, discard it and create a new one."""
    # Old redis client whose ping will fail
    old_redis = AsyncMock()
    old_redis.ping = AsyncMock(side_effect=ConnectionError("connection lost"))

    old_instance = redis_mod.RedisSessionPersistence(old_redis)
    redis_mod._redis_session_persistence = old_instance

    # New redis client returned by get_redis_client
    new_redis = AsyncMock()
    new_redis.ping = AsyncMock(return_value=True)

    with patch(
        "cache.redis_client.get_redis_client",
        new_callable=AsyncMock,
        return_value=new_redis,
    ):
        result = await redis_mod.get_redis_session_persistence()

    # Should NOT be the old instance
    assert result is not old_instance
    assert result is not None
    assert isinstance(result, redis_mod.RedisSessionPersistence)
    # The new instance should use the new redis client
    assert result._redis is new_redis


@pytest.mark.asyncio
async def test_factory_creates_new_instance_on_first_call():
    """On first call (no cached instance), create and return a new instance."""
    assert redis_mod._redis_session_persistence is None

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    with patch(
        "cache.redis_client.get_redis_client",
        new_callable=AsyncMock,
        return_value=mock_redis,
    ):
        result = await redis_mod.get_redis_session_persistence()

    assert result is not None
    assert isinstance(result, redis_mod.RedisSessionPersistence)
    assert result._redis is mock_redis
    # Should be cached for next call
    assert redis_mod._redis_session_persistence is result


@pytest.mark.asyncio
async def test_ping_failure_sets_cached_instance_to_none():
    """When ping fails on the cached instance, _redis_session_persistence is set to None."""
    failing_redis = AsyncMock()
    failing_redis.ping = AsyncMock(side_effect=Exception("Redis down"))

    old_instance = redis_mod.RedisSessionPersistence(failing_redis)
    redis_mod._redis_session_persistence = old_instance

    # Make get_redis_client also fail so no new instance is created
    with patch(
        "cache.redis_client.get_redis_client",
        new_callable=AsyncMock,
        side_effect=Exception("Redis unavailable"),
    ):
        result = await redis_mod.get_redis_session_persistence()

    # No instance should be returned
    assert result is None
    # The cached singleton should have been cleared
    assert redis_mod._redis_session_persistence is None


@pytest.mark.asyncio
async def test_factory_returns_none_when_redis_client_unavailable():
    """When get_redis_client returns None, factory returns None."""
    assert redis_mod._redis_session_persistence is None

    with patch(
        "cache.redis_client.get_redis_client",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await redis_mod.get_redis_session_persistence()

    assert result is None
    assert redis_mod._redis_session_persistence is None
