"""Tests for calculation caching functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from cache.calculation_cache import (
    CalculationCache,
    CacheInvalidator,
    cached_calculation,
    CALC_PREFIX,
    RETURN_PREFIX,
    SCENARIO_PREFIX,
    DEFAULT_CALCULATION_TTL,
)


class TestCalculationCache:
    """Tests for CalculationCache class."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = AsyncMock()
        client.is_connected = True
        client.get = AsyncMock(return_value=None)
        client.set = AsyncMock(return_value=True)
        client.delete = AsyncMock(return_value=True)
        client.delete_pattern = AsyncMock(return_value=1)
        return client

    @pytest.fixture
    def cache(self, mock_redis_client):
        """Create cache with mock client."""
        cache = CalculationCache(client=mock_redis_client)
        cache._client = mock_redis_client
        return cache

    def test_init_default_ttl(self):
        """Cache initializes with default TTL."""
        cache = CalculationCache()
        assert cache._ttl == DEFAULT_CALCULATION_TTL

    def test_init_custom_ttl(self):
        """Cache can be initialized with custom TTL."""
        cache = CalculationCache(ttl=7200)
        assert cache._ttl == 7200

    def test_make_calc_key(self, cache):
        """Calculation key has correct format."""
        key = cache._make_calc_key("return-123")
        assert key == f"{CALC_PREFIX}return-123"

    def test_make_return_key(self, cache):
        """Return key has correct format."""
        key = cache._make_return_key("return-123")
        assert key == f"{RETURN_PREFIX}return-123"

    def test_make_scenario_key(self, cache):
        """Scenario key has correct format."""
        key = cache._make_scenario_key("return-123", "scenario-456")
        assert key == f"{SCENARIO_PREFIX}return-123:scenario-456"

    def test_hash_context_deterministic(self, cache):
        """Context hash is deterministic for same input."""
        context = {"tax_year": 2025, "filing_status": "single"}
        hash1 = cache._hash_context(context)
        hash2 = cache._hash_context(context)
        assert hash1 == hash2

    def test_hash_context_different_for_different_input(self, cache):
        """Context hash differs for different input."""
        context1 = {"tax_year": 2025, "filing_status": "single"}
        context2 = {"tax_year": 2025, "filing_status": "married_joint"}
        hash1 = cache._hash_context(context1)
        hash2 = cache._hash_context(context2)
        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_get_calculation_cache_miss(self, cache, mock_redis_client):
        """Get returns None on cache miss."""
        mock_redis_client.get.return_value = None

        result = await cache.get_calculation("return-123")

        assert result is None
        mock_redis_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_calculation_cache_hit(self, cache, mock_redis_client):
        """Get returns cached data on hit."""
        cached_data = {"total_tax": 5000, "agi": 75000}
        mock_redis_client.get.return_value = cached_data

        result = await cache.get_calculation("return-123")

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_get_calculation_with_context_hash(self, cache, mock_redis_client):
        """Get includes context hash in key."""
        await cache.get_calculation("return-123", context_hash="abc123")

        call_args = mock_redis_client.get.call_args[0][0]
        assert "abc123" in call_args

    @pytest.mark.asyncio
    async def test_set_calculation(self, cache, mock_redis_client):
        """Set stores calculation with TTL."""
        calculation = {"total_tax": 5000}

        result = await cache.set_calculation("return-123", calculation)

        assert result is True
        mock_redis_client.set.assert_called_once()
        call_kwargs = mock_redis_client.set.call_args[1]
        assert call_kwargs["ttl"] == DEFAULT_CALCULATION_TTL

    @pytest.mark.asyncio
    async def test_set_calculation_custom_ttl(self, cache, mock_redis_client):
        """Set uses custom TTL when provided."""
        await cache.set_calculation("return-123", {}, ttl=1800)

        call_kwargs = mock_redis_client.set.call_args[1]
        assert call_kwargs["ttl"] == 1800

    @pytest.mark.asyncio
    async def test_invalidate_calculation(self, cache, mock_redis_client):
        """Invalidate deletes calculation cache."""
        mock_redis_client.delete_pattern.return_value = 3

        result = await cache.invalidate_calculation("return-123")

        assert result is True
        mock_redis_client.delete_pattern.assert_called_once()
        pattern = mock_redis_client.delete_pattern.call_args[0][0]
        assert "return-123" in pattern

    @pytest.mark.asyncio
    async def test_invalidate_return(self, cache, mock_redis_client):
        """Invalidate return clears all related caches."""
        mock_redis_client.delete_pattern.return_value = 2
        mock_redis_client.delete.return_value = True

        result = await cache.invalidate_return("return-123")

        # Should call delete_pattern twice (calc and scenarios) and delete once (return data)
        assert result > 0

    @pytest.mark.asyncio
    async def test_get_scenario_calculation(self, cache, mock_redis_client):
        """Get scenario retrieves scenario-specific cache."""
        cached_data = {"scenario_tax": 4500}
        mock_redis_client.get.return_value = cached_data

        result = await cache.get_scenario_calculation("return-123", "scenario-456")

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_set_scenario_calculation(self, cache, mock_redis_client):
        """Set scenario stores scenario result."""
        await cache.set_scenario_calculation(
            "return-123", "scenario-456", {"scenario_tax": 4500}
        )

        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args[0][0]
        assert "scenario" in call_args
        assert "return-123" in call_args
        assert "scenario-456" in call_args

    @pytest.mark.asyncio
    async def test_warmup_return(self, cache, mock_redis_client):
        """Warmup stores both return data and calculation."""
        result = await cache.warmup_return(
            "return-123",
            return_data={"income": {"wages": 50000}},
            calculation={"total_tax": 5000},
        )

        assert result is True
        assert mock_redis_client.set.call_count == 2

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache, mock_redis_client):
        """Get stats returns cache information."""
        stats = await cache.get_cache_stats()

        assert "connected" in stats
        assert stats["connected"] is True
        assert "ttl_seconds" in stats


class TestCacheInvalidator:
    """Tests for CacheInvalidator class."""

    @pytest.fixture
    def mock_cache(self):
        """Create mock calculation cache."""
        cache = AsyncMock(spec=CalculationCache)
        cache.invalidate_return = AsyncMock()
        cache.invalidate_calculation = AsyncMock()
        cache.client = AsyncMock()
        cache.client.delete_pattern = AsyncMock(return_value=5)
        return cache

    @pytest.fixture
    def invalidator(self, mock_cache):
        """Create invalidator with mock cache."""
        return CacheInvalidator(cache=mock_cache)

    @pytest.mark.asyncio
    async def test_on_return_updated(self, invalidator, mock_cache):
        """Return update invalidates cache."""
        await invalidator.on_return_updated("return-123")

        mock_cache.invalidate_return.assert_called_once_with("return-123")

    @pytest.mark.asyncio
    async def test_on_return_deleted(self, invalidator, mock_cache):
        """Return deletion invalidates cache."""
        await invalidator.on_return_deleted("return-123")

        mock_cache.invalidate_return.assert_called_once_with("return-123")

    @pytest.mark.asyncio
    async def test_on_config_changed(self, invalidator, mock_cache):
        """Config change invalidates all calculations."""
        await invalidator.on_config_changed()

        mock_cache.client.delete_pattern.assert_called_once()
        pattern = mock_cache.client.delete_pattern.call_args[0][0]
        assert CALC_PREFIX in pattern

    @pytest.mark.asyncio
    async def test_on_prior_year_updated(self, invalidator, mock_cache):
        """Prior year update invalidates calculation."""
        await invalidator.on_prior_year_updated("return-123", "prior-456")

        mock_cache.invalidate_calculation.assert_called_once_with("return-123")


class TestCachedCalculationDecorator:
    """Tests for @cached_calculation decorator."""

    @pytest.mark.asyncio
    async def test_decorator_caches_result(self):
        """Decorator caches function result."""
        call_count = [0]

        @cached_calculation(ttl=3600)
        async def expensive_calculation(return_id: str) -> dict:
            call_count[0] += 1
            return {"result": "computed", "count": call_count[0]}

        with patch("cache.calculation_cache.get_calculation_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get_calculation = AsyncMock(return_value=None)
            mock_cache.set_calculation = AsyncMock(return_value=True)
            mock_get_cache.return_value = mock_cache

            # First call - should compute
            result1 = await expensive_calculation("return-123")
            assert result1["count"] == 1

            # Verify set_calculation was called
            mock_cache.set_calculation.assert_called_once()

    @pytest.mark.asyncio
    async def test_decorator_returns_cached_on_hit(self):
        """Decorator returns cached result on hit."""
        cached_data = {"result": "cached"}

        @cached_calculation()
        async def expensive_calculation(return_id: str) -> dict:
            return {"result": "computed"}

        with patch("cache.calculation_cache.get_calculation_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get_calculation = AsyncMock(return_value=cached_data)
            mock_get_cache.return_value = mock_cache

            result = await expensive_calculation("return-123")

            assert result == cached_data

    @pytest.mark.asyncio
    async def test_decorator_custom_key_func(self):
        """Decorator uses custom key function."""
        def custom_key(return_id: str, tax_year: int) -> str:
            return f"{return_id}:{tax_year}"

        @cached_calculation(key_func=custom_key)
        async def calculation(return_id: str, tax_year: int) -> dict:
            return {"year": tax_year}

        with patch("cache.calculation_cache.get_calculation_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get_calculation = AsyncMock(return_value=None)
            mock_cache.set_calculation = AsyncMock(return_value=True)
            mock_get_cache.return_value = mock_cache

            await calculation("return-123", 2025)

            # Verify custom key was used
            call_key = mock_cache.get_calculation.call_args[0][0]
            assert call_key == "return-123:2025"
