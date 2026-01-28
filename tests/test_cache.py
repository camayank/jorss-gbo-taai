"""Tests for cache layer (Redis client and calculation cache)."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import timedelta


class TestRedisClientImport:
    """Tests for Redis client import handling."""

    def test_redis_available_flag(self):
        """Should have REDIS_AVAILABLE flag."""
        from cache.redis_client import REDIS_AVAILABLE
        # Flag should be a boolean
        assert isinstance(REDIS_AVAILABLE, bool)


class TestRedisClientInit:
    """Tests for RedisClient initialization."""

    def test_raises_without_redis_package(self):
        """Should raise ImportError if redis not installed."""
        with patch('cache.redis_client.REDIS_AVAILABLE', False):
            from cache.redis_client import RedisClient
            # Need to reload to pick up the patch
            with pytest.raises(ImportError, match="redis package is not installed"):
                RedisClient()

    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    def test_init_with_default_settings(self):
        """Should initialize with default settings."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_redis_settings = MagicMock()
            mock_settings.return_value.redis = mock_redis_settings

            from cache.redis_client import RedisClient
            client = RedisClient()

            assert client.settings is mock_redis_settings
            assert client._pool is None
            assert client._client is None
            assert client._connected is False

    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    def test_init_with_custom_settings(self):
        """Should initialize with custom settings."""
        custom_settings = MagicMock()

        from cache.redis_client import RedisClient
        client = RedisClient(settings=custom_settings)

        assert client.settings is custom_settings


class TestRedisClientConnection:
    """Tests for RedisClient connection methods."""

    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    def test_is_connected_returns_false_initially(self):
        """is_connected should return False before connect."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            assert client.is_connected is False

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_connect_creates_pool(self):
        """connect should create connection pool and client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_redis_settings = MagicMock()
            mock_redis_settings.url = "redis://localhost:6379/0"
            mock_redis_settings.max_connections = 10
            mock_redis_settings.socket_timeout = 5.0
            mock_redis_settings.socket_connect_timeout = 5.0
            mock_redis_settings.host = "localhost"
            mock_redis_settings.port = 6379
            mock_settings.return_value.redis = mock_redis_settings

            with patch('cache.redis_client.ConnectionPool') as mock_pool_class:
                with patch('cache.redis_client.Redis') as mock_redis_class:
                    mock_pool = MagicMock()
                    mock_pool_class.from_url.return_value = mock_pool

                    mock_redis = AsyncMock()
                    mock_redis.ping.return_value = True
                    mock_redis_class.return_value = mock_redis

                    from cache.redis_client import RedisClient
                    client = RedisClient()

                    await client.connect()

                    assert client._connected is True
                    mock_pool_class.from_url.assert_called_once()
                    mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_connect_is_idempotent(self):
        """connect should be idempotent."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_redis_settings = MagicMock()
            mock_settings.return_value.redis = mock_redis_settings

            from cache.redis_client import RedisClient
            client = RedisClient()
            client._connected = True

            # Should return early without doing anything
            await client.connect()

            assert client._connected is True

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_close_cleans_up(self):
        """close should clean up resources."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            mock_redis = AsyncMock()
            mock_pool = AsyncMock()

            client._client = mock_redis
            client._pool = mock_pool
            client._connected = True

            await client.close()

            mock_redis.aclose.assert_called_once()  # aclose() is the non-deprecated method
            mock_pool.disconnect.assert_called_once()
            assert client._connected is False
            assert client._client is None
            assert client._pool is None

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_ping_returns_false_without_client(self):
        """ping should return False without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.ping()

            assert result is False


class TestRedisClientSerialization:
    """Tests for RedisClient serialization methods."""

    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    def test_serialize_dict(self):
        """Should serialize dict to JSON."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            data = {"key": "value", "number": 42}
            result = client._serialize(data)

            assert result == json.dumps(data, default=str)

    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    def test_deserialize_json(self):
        """Should deserialize JSON string."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            data = '{"key": "value"}'
            result = client._deserialize(data)

            assert result == {"key": "value"}

    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    def test_deserialize_none(self):
        """Should return None for None input."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = client._deserialize(None)

            assert result is None

    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    def test_deserialize_invalid_json(self):
        """Should return raw string for invalid JSON."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = client._deserialize("not-json")

            assert result == "not-json"


class TestRedisClientOperations:
    """Tests for RedisClient data operations."""

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_get_returns_none_without_client(self):
        """get should return None without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.get("key")

            assert result is None

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_set_returns_false_without_client(self):
        """set should return False without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.set("key", "value")

            assert result is False

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_delete_returns_false_without_client(self):
        """delete should return False without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.delete("key")

            assert result is False

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_exists_returns_false_without_client(self):
        """exists should return False without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.exists("key")

            assert result is False

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_get_with_prefix(self):
        """get should apply key prefix."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_redis_settings = MagicMock()
            mock_redis_settings.key_prefix = "test:"
            mock_settings.return_value.redis = mock_redis_settings

            from cache.redis_client import RedisClient
            client = RedisClient()

            mock_redis = AsyncMock()
            mock_redis.get.return_value = '{"data": "value"}'
            client._client = mock_redis

            result = await client.get("mykey")

            mock_redis.get.assert_called_with("test:mykey")
            assert result == {"data": "value"}

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_set_with_ttl(self):
        """set should accept TTL parameter."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_redis_settings = MagicMock()
            mock_redis_settings.key_prefix = ""
            mock_redis_settings.default_ttl = 3600
            mock_settings.return_value.redis = mock_redis_settings

            from cache.redis_client import RedisClient
            client = RedisClient()

            mock_redis = AsyncMock()
            client._client = mock_redis

            await client.set("key", {"data": "value"}, ttl=300)

            mock_redis.set.assert_called_once()
            call_kwargs = mock_redis.set.call_args[1]
            assert call_kwargs["ex"] == 300

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_set_with_timedelta_ttl(self):
        """set should convert timedelta TTL to seconds."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_redis_settings = MagicMock()
            mock_redis_settings.key_prefix = ""
            mock_redis_settings.default_ttl = 3600
            mock_settings.return_value.redis = mock_redis_settings

            from cache.redis_client import RedisClient
            client = RedisClient()

            mock_redis = AsyncMock()
            client._client = mock_redis

            await client.set("key", "value", ttl=timedelta(hours=1))

            call_kwargs = mock_redis.set.call_args[1]
            assert call_kwargs["ex"] == 3600


class TestRedisClientHashOperations:
    """Tests for Redis hash operations."""

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_hget_returns_none_without_client(self):
        """hget should return None without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.hget("hash", "field")

            assert result is None

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_hset_returns_false_without_client(self):
        """hset should return False without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.hset("hash", "field", "value")

            assert result is False

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_hgetall_returns_empty_without_client(self):
        """hgetall should return empty dict without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.hgetall("hash")

            assert result == {}


class TestRedisClientBulkOperations:
    """Tests for Redis bulk operations."""

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_mget_returns_nones_without_client(self):
        """mget should return list of Nones without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.mget("key1", "key2", "key3")

            assert result == [None, None, None]

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_mset_returns_false_without_client(self):
        """mset should return False without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.mset({"key1": "value1", "key2": "value2"})

            assert result is False

    @pytest.mark.asyncio
    @patch('cache.redis_client.REDIS_AVAILABLE', True)
    async def test_delete_pattern_returns_zero_without_client(self):
        """delete_pattern should return 0 without client."""
        with patch('cache.redis_client.get_settings') as mock_settings:
            mock_settings.return_value.redis = MagicMock()

            from cache.redis_client import RedisClient
            client = RedisClient()

            result = await client.delete_pattern("pattern:*")

            assert result == 0


class TestCalculationCacheInit:
    """Tests for CalculationCache initialization."""

    def test_init_with_defaults(self):
        """Should initialize with default values."""
        from cache.calculation_cache import CalculationCache, DEFAULT_CALCULATION_TTL

        cache = CalculationCache()

        assert cache._client is None
        assert cache._ttl == DEFAULT_CALCULATION_TTL

    def test_init_with_custom_client(self):
        """Should accept custom client."""
        from cache.calculation_cache import CalculationCache

        mock_client = MagicMock()
        cache = CalculationCache(client=mock_client)

        assert cache._client is mock_client

    def test_init_with_custom_ttl(self):
        """Should accept custom TTL."""
        from cache.calculation_cache import CalculationCache

        cache = CalculationCache(ttl=7200)

        assert cache._ttl == 7200


class TestCalculationCacheConnection:
    """Tests for CalculationCache connection handling."""

    @pytest.mark.asyncio
    async def test_connect_gets_redis_client(self):
        """connect should get global Redis client."""
        from cache.calculation_cache import CalculationCache

        with patch('cache.calculation_cache.get_redis_client') as mock_get:
            mock_client = AsyncMock()
            mock_get.return_value = mock_client

            cache = CalculationCache()
            await cache.connect()

            mock_get.assert_called_once()
            assert cache._client is mock_client

    def test_client_property_raises_without_connect(self):
        """client property should raise if not connected."""
        from cache.calculation_cache import CalculationCache

        cache = CalculationCache()

        with pytest.raises(RuntimeError, match="Cache not connected"):
            _ = cache.client

    def test_client_property_returns_client(self):
        """client property should return client when connected."""
        from cache.calculation_cache import CalculationCache

        mock_client = MagicMock()
        cache = CalculationCache(client=mock_client)

        assert cache.client is mock_client


class TestCalculationCacheKeyMethods:
    """Tests for cache key generation methods."""

    def test_make_calc_key(self):
        """Should generate calculation cache key."""
        from cache.calculation_cache import CalculationCache, CALC_PREFIX

        cache = CalculationCache()
        key = cache._make_calc_key("return-123")

        assert key == f"{CALC_PREFIX}return-123"

    def test_make_return_key(self):
        """Should generate return data cache key."""
        from cache.calculation_cache import CalculationCache, RETURN_PREFIX

        cache = CalculationCache()
        key = cache._make_return_key("return-456")

        assert key == f"{RETURN_PREFIX}return-456"

    def test_make_scenario_key(self):
        """Should generate scenario cache key."""
        from cache.calculation_cache import CalculationCache, SCENARIO_PREFIX

        cache = CalculationCache()
        key = cache._make_scenario_key("return-123", "scenario-abc")

        assert key == f"{SCENARIO_PREFIX}return-123:scenario-abc"

    def test_hash_context(self):
        """Should hash context dict deterministically."""
        from cache.calculation_cache import CalculationCache

        cache = CalculationCache()

        ctx1 = {"filing_status": "single", "income": 50000}
        ctx2 = {"income": 50000, "filing_status": "single"}  # Same but different order

        hash1 = cache._hash_context(ctx1)
        hash2 = cache._hash_context(ctx2)

        # Should produce same hash regardless of key order
        assert hash1 == hash2
        assert len(hash1) == 16


class TestCalculationCacheOperations:
    """Tests for calculation cache operations."""

    @pytest.mark.asyncio
    async def test_get_calculation_hit(self):
        """Should return cached calculation on hit."""
        from cache.calculation_cache import CalculationCache

        mock_client = AsyncMock()
        mock_client.get.return_value = {"total_tax": 15000}

        cache = CalculationCache(client=mock_client)

        result = await cache.get_calculation("return-123")

        assert result == {"total_tax": 15000}

    @pytest.mark.asyncio
    async def test_get_calculation_miss(self):
        """Should return None on cache miss."""
        from cache.calculation_cache import CalculationCache

        mock_client = AsyncMock()
        mock_client.get.return_value = None

        cache = CalculationCache(client=mock_client)

        result = await cache.get_calculation("return-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_calculation_with_context_hash(self):
        """Should include context hash in key."""
        from cache.calculation_cache import CalculationCache, CALC_PREFIX

        mock_client = AsyncMock()
        mock_client.get.return_value = None

        cache = CalculationCache(client=mock_client)

        await cache.get_calculation("return-123", context_hash="abc123")

        mock_client.get.assert_called_with(f"{CALC_PREFIX}return-123:abc123")

    @pytest.mark.asyncio
    async def test_set_calculation(self):
        """Should cache calculation result."""
        from cache.calculation_cache import CalculationCache, CALC_PREFIX

        mock_client = AsyncMock()
        mock_client.set.return_value = True

        cache = CalculationCache(client=mock_client, ttl=3600)

        result = await cache.set_calculation("return-123", {"total_tax": 15000})

        assert result is True
        mock_client.set.assert_called_with(
            f"{CALC_PREFIX}return-123",
            {"total_tax": 15000},
            ttl=3600,
        )

    @pytest.mark.asyncio
    async def test_set_calculation_custom_ttl(self):
        """Should use custom TTL when provided."""
        from cache.calculation_cache import CalculationCache

        mock_client = AsyncMock()
        mock_client.set.return_value = True

        cache = CalculationCache(client=mock_client, ttl=3600)

        await cache.set_calculation("return-123", {"data": "value"}, ttl=7200)

        call_kwargs = mock_client.set.call_args[1]
        assert call_kwargs["ttl"] == 7200

    @pytest.mark.asyncio
    async def test_invalidate_calculation(self):
        """Should delete calculation cache entries."""
        from cache.calculation_cache import CalculationCache, CALC_PREFIX

        mock_client = AsyncMock()
        mock_client.delete_pattern.return_value = 3

        cache = CalculationCache(client=mock_client)

        result = await cache.invalidate_calculation("return-123")

        assert result is True
        mock_client.delete_pattern.assert_called_with(f"{CALC_PREFIX}return-123*")


class TestCalculationCacheReturnData:
    """Tests for return data caching."""

    @pytest.mark.asyncio
    async def test_get_return_data(self):
        """Should get cached return data."""
        from cache.calculation_cache import CalculationCache

        mock_client = AsyncMock()
        mock_client.get.return_value = {"taxpayer": {"name": "John"}}

        cache = CalculationCache(client=mock_client)

        result = await cache.get_return_data("return-123")

        assert result == {"taxpayer": {"name": "John"}}

    @pytest.mark.asyncio
    async def test_set_return_data(self):
        """Should cache return data."""
        from cache.calculation_cache import CalculationCache

        mock_client = AsyncMock()
        mock_client.set.return_value = True

        cache = CalculationCache(client=mock_client)

        result = await cache.set_return_data("return-123", {"data": "value"})

        assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_return(self):
        """Should invalidate all cache entries for return."""
        from cache.calculation_cache import CalculationCache

        mock_client = AsyncMock()
        mock_client.delete_pattern.return_value = 1
        mock_client.delete.return_value = True

        cache = CalculationCache(client=mock_client)

        result = await cache.invalidate_return("return-123")

        # Should call invalidate for calculations, return data, and scenarios
        assert result >= 1


class TestCalculationCacheScenarios:
    """Tests for scenario caching."""

    @pytest.mark.asyncio
    async def test_get_scenario_calculation(self):
        """Should get cached scenario calculation."""
        from cache.calculation_cache import CalculationCache

        mock_client = AsyncMock()
        mock_client.get.return_value = {"scenario_tax": 12000}

        cache = CalculationCache(client=mock_client)

        result = await cache.get_scenario_calculation("return-123", "scenario-abc")

        assert result == {"scenario_tax": 12000}

    @pytest.mark.asyncio
    async def test_set_scenario_calculation(self):
        """Should cache scenario calculation."""
        from cache.calculation_cache import CalculationCache

        mock_client = AsyncMock()
        mock_client.set.return_value = True

        cache = CalculationCache(client=mock_client)

        result = await cache.set_scenario_calculation(
            "return-123",
            "scenario-abc",
            {"scenario_tax": 12000}
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_scenarios(self):
        """Should invalidate all scenarios for a return."""
        from cache.calculation_cache import CalculationCache, SCENARIO_PREFIX

        mock_client = AsyncMock()
        mock_client.delete_pattern.return_value = 5

        cache = CalculationCache(client=mock_client)

        result = await cache.invalidate_scenarios("return-123")

        assert result == 5
        mock_client.delete_pattern.assert_called_with(f"{SCENARIO_PREFIX}return-123:*")


class TestCalculationCacheBulkOperations:
    """Tests for bulk cache operations."""

    @pytest.mark.asyncio
    async def test_warmup_return(self):
        """Should cache both return data and calculation."""
        from cache.calculation_cache import CalculationCache

        mock_client = AsyncMock()
        mock_client.set.return_value = True

        cache = CalculationCache(client=mock_client)

        result = await cache.warmup_return(
            "return-123",
            {"taxpayer": {"name": "John"}},
            {"total_tax": 15000}
        )

        assert result is True
        assert mock_client.set.call_count == 2

    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """Should return cache statistics."""
        from cache.calculation_cache import CalculationCache

        mock_client = MagicMock()
        mock_client.is_connected = True

        cache = CalculationCache(client=mock_client, ttl=3600)

        result = await cache.get_cache_stats()

        assert result["connected"] is True
        assert result["ttl_seconds"] == 3600


class TestCacheInvalidator:
    """Tests for CacheInvalidator class."""

    @pytest.mark.asyncio
    async def test_on_return_updated(self):
        """Should invalidate cache on return update."""
        from cache.calculation_cache import CacheInvalidator, CalculationCache

        mock_cache = AsyncMock(spec=CalculationCache)
        invalidator = CacheInvalidator(cache=mock_cache)

        await invalidator.on_return_updated("return-123")

        mock_cache.invalidate_return.assert_called_once_with("return-123")

    @pytest.mark.asyncio
    async def test_on_return_deleted(self):
        """Should invalidate cache on return deletion."""
        from cache.calculation_cache import CacheInvalidator, CalculationCache

        mock_cache = AsyncMock(spec=CalculationCache)
        invalidator = CacheInvalidator(cache=mock_cache)

        await invalidator.on_return_deleted("return-123")

        mock_cache.invalidate_return.assert_called_once_with("return-123")

    @pytest.mark.asyncio
    async def test_on_config_changed(self):
        """Should invalidate all calculations on config change."""
        from cache.calculation_cache import CacheInvalidator, CalculationCache, CALC_PREFIX

        mock_client = AsyncMock()
        mock_client.delete_pattern.return_value = 100

        mock_cache = AsyncMock(spec=CalculationCache)
        mock_cache.client = mock_client

        invalidator = CacheInvalidator(cache=mock_cache)

        await invalidator.on_config_changed()

        mock_client.delete_pattern.assert_called_once_with(f"{CALC_PREFIX}*")

    @pytest.mark.asyncio
    async def test_on_prior_year_updated(self):
        """Should invalidate current year calculation when prior year changes."""
        from cache.calculation_cache import CacheInvalidator, CalculationCache

        mock_cache = AsyncMock(spec=CalculationCache)
        invalidator = CacheInvalidator(cache=mock_cache)

        await invalidator.on_prior_year_updated("return-2025", "return-2024")

        mock_cache.invalidate_calculation.assert_called_once_with("return-2025")


class TestCachedCalculationDecorator:
    """Tests for @cached_calculation decorator."""

    @pytest.mark.asyncio
    async def test_decorator_returns_cached_value(self):
        """Should return cached value when available."""
        from cache.calculation_cache import cached_calculation, get_calculation_cache

        mock_cache = AsyncMock()
        mock_cache.get_calculation.return_value = {"cached": True}
        mock_cache.set_calculation.return_value = True

        with patch('cache.calculation_cache.get_calculation_cache', return_value=mock_cache):
            @cached_calculation()
            async def my_calculation(return_id: str) -> dict:
                return {"computed": True}

            result = await my_calculation("test-123")

            assert result == {"cached": True}

    @pytest.mark.asyncio
    async def test_decorator_computes_on_miss(self):
        """Should compute and cache on cache miss."""
        from cache.calculation_cache import cached_calculation

        mock_cache = AsyncMock()
        mock_cache.get_calculation.return_value = None  # Cache miss
        mock_cache.set_calculation.return_value = True

        with patch('cache.calculation_cache.get_calculation_cache', return_value=mock_cache):
            @cached_calculation()
            async def my_calculation(return_id: str) -> dict:
                return {"computed": True}

            result = await my_calculation("test-123")

            assert result == {"computed": True}
            mock_cache.set_calculation.assert_called_once()

    @pytest.mark.asyncio
    async def test_decorator_with_custom_key_func(self):
        """Should use custom key function."""
        from cache.calculation_cache import cached_calculation

        mock_cache = AsyncMock()
        mock_cache.get_calculation.return_value = None
        mock_cache.set_calculation.return_value = True

        def custom_key(return_id: str, year: int) -> str:
            return f"{return_id}:{year}"

        with patch('cache.calculation_cache.get_calculation_cache', return_value=mock_cache):
            @cached_calculation(key_func=custom_key)
            async def my_calculation(return_id: str, year: int) -> dict:
                return {"computed": True}

            await my_calculation("test-123", 2025)

            mock_cache.get_calculation.assert_called_with("test-123:2025")

    @pytest.mark.asyncio
    async def test_decorator_with_custom_ttl(self):
        """Should use custom TTL."""
        from cache.calculation_cache import cached_calculation

        mock_cache = AsyncMock()
        mock_cache.get_calculation.return_value = None
        mock_cache.set_calculation.return_value = True

        with patch('cache.calculation_cache.get_calculation_cache', return_value=mock_cache):
            @cached_calculation(ttl=7200)
            async def my_calculation(return_id: str) -> dict:
                return {"computed": True}

            await my_calculation("test-123")

            call_kwargs = mock_cache.set_calculation.call_args[1]
            assert call_kwargs["ttl"] == 7200
