"""
Comprehensive tests for Web Middleware — Rate Limiter (Redis + InMemory),
Circuit Breaker, Idempotency middleware, and request hashing.
"""
import os
import sys
import time
import hashlib
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from web.rate_limiter import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    RedisRateLimitMiddleware,
)
from web.idempotency import (
    IdempotencyRecord,
    IdempotencyStore,
    IdempotencyMiddleware,
    compute_request_hash,
    IDEMPOTENCY_KEY_HEADER,
    DEFAULT_TTL_HOURS,
    require_idempotency_key,
    generate_idempotency_key,
)
from resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)


# ===================================================================
# IN-MEMORY RATE LIMITER
# ===================================================================

class TestInMemoryRateLimiter:

    def test_default_init(self):
        limiter = InMemoryRateLimiter()
        assert limiter.default_limit == 60
        assert limiter.default_window_seconds == 60

    @pytest.mark.parametrize("limit,window", [
        (10, 30),
        (100, 120),
        (1, 1),
        (1000, 3600),
    ])
    def test_custom_init(self, limit, window):
        limiter = InMemoryRateLimiter(default_limit=limit, default_window_seconds=window)
        assert limiter.default_limit == limit
        assert limiter.default_window_seconds == window

    def test_first_request_allowed(self):
        limiter = InMemoryRateLimiter(default_limit=10)
        allowed, remaining, retry = limiter.is_allowed("client-1")
        assert allowed is True
        assert remaining == 9
        assert retry == 0

    def test_multiple_requests_allowed(self):
        limiter = InMemoryRateLimiter(default_limit=5)
        for i in range(5):
            allowed, remaining, _ = limiter.is_allowed("client-1")
            assert allowed is True
            assert remaining == 4 - i

    def test_exceeds_limit(self):
        limiter = InMemoryRateLimiter(default_limit=3, default_window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("client-1")
        allowed, remaining, retry = limiter.is_allowed("client-1")
        assert allowed is False
        assert remaining == 0
        assert retry > 0

    def test_different_clients_independent(self):
        limiter = InMemoryRateLimiter(default_limit=2)
        limiter.is_allowed("client-a")
        limiter.is_allowed("client-a")
        allowed_a, _, _ = limiter.is_allowed("client-a")
        allowed_b, _, _ = limiter.is_allowed("client-b")
        assert allowed_a is False
        assert allowed_b is True

    def test_different_window_names_independent(self):
        limiter = InMemoryRateLimiter(default_limit=1)
        allowed1, _, _ = limiter.is_allowed("client-1", window_name="minute")
        allowed2, _, _ = limiter.is_allowed("client-1", window_name="hour")
        assert allowed1 is True
        assert allowed2 is True

    def test_custom_limit_override(self):
        limiter = InMemoryRateLimiter(default_limit=100)
        allowed, remaining, _ = limiter.is_allowed("c1", limit=5)
        assert allowed is True
        assert remaining == 4

    def test_custom_window_override(self):
        limiter = InMemoryRateLimiter(default_limit=10, default_window_seconds=3600)
        allowed, _, _ = limiter.is_allowed("c1", window_seconds=1)
        assert allowed is True

    def test_retry_after_positive_when_blocked(self):
        limiter = InMemoryRateLimiter(default_limit=1, default_window_seconds=60)
        limiter.is_allowed("c1")
        _, _, retry = limiter.is_allowed("c1")
        assert retry > 0
        assert retry <= 61

    def test_cleanup_old_entries(self):
        limiter = InMemoryRateLimiter(default_limit=1, default_window_seconds=1)
        limiter.is_allowed("c1")
        # Manually age out entries
        key = "default:c1"
        limiter.buckets[key] = [time.time() - 10]
        allowed, _, _ = limiter.is_allowed("c1")
        assert allowed is True

    def test_cleanup_if_needed_interval(self):
        limiter = InMemoryRateLimiter()
        limiter.last_cleanup = time.time() - 400  # Exceed 300s cleanup interval
        limiter.is_allowed("c1")
        # After cleanup_if_needed, last_cleanup should be updated
        assert time.time() - limiter.last_cleanup < 5

    def test_cleanup_all_removes_empty_buckets(self):
        limiter = InMemoryRateLimiter()
        limiter.buckets["old:c1"] = [time.time() - 7200]
        limiter._cleanup_all()
        assert "old:c1" not in limiter.buckets

    def test_empty_buckets_dict_initially(self):
        limiter = InMemoryRateLimiter()
        assert len(limiter.buckets) == 0

    @pytest.mark.parametrize("num_clients", [5, 10, 50])
    def test_many_clients(self, num_clients):
        limiter = InMemoryRateLimiter(default_limit=100)
        for i in range(num_clients):
            allowed, _, _ = limiter.is_allowed(f"client-{i}")
            assert allowed is True

    def test_remaining_decrements(self):
        limiter = InMemoryRateLimiter(default_limit=5)
        remainders = []
        for _ in range(5):
            _, remaining, _ = limiter.is_allowed("c1")
            remainders.append(remaining)
        assert remainders == [4, 3, 2, 1, 0]

    @pytest.mark.parametrize("limit", [1, 2, 5, 10, 100])
    def test_exact_limit_boundary(self, limit):
        limiter = InMemoryRateLimiter(default_limit=limit)
        for _ in range(limit):
            allowed, _, _ = limiter.is_allowed("c1")
            assert allowed is True
        allowed, _, _ = limiter.is_allowed("c1")
        assert allowed is False


# ===================================================================
# REDIS RATE LIMITER
# ===================================================================

class TestRedisRateLimiter:

    def _mock_redis(self):
        redis = Mock()
        pipe = Mock()
        pipe.execute.return_value = [None, 0, None, None]
        redis.pipeline.return_value = pipe
        redis.zrange.return_value = []
        redis.zrem.return_value = None
        redis.zremrangebyscore.return_value = None
        redis.zcard.return_value = 0
        redis.delete.return_value = 1
        return redis, pipe

    def test_init_defaults(self):
        redis, _ = self._mock_redis()
        limiter = RedisRateLimiter(redis)
        assert limiter.default_limit == 60
        assert limiter.default_window_seconds == 60
        assert limiter.key_prefix == "rate_limit:"

    def test_custom_key_prefix(self):
        redis, _ = self._mock_redis()
        limiter = RedisRateLimiter(redis, key_prefix="custom:")
        assert limiter.key_prefix == "custom:"

    def test_get_key_format(self):
        redis, _ = self._mock_redis()
        limiter = RedisRateLimiter(redis, key_prefix="rl:")
        key = limiter._get_key("192.168.1.1", "minute")
        assert key == "rl:minute:192.168.1.1"

    def test_is_allowed_under_limit(self):
        redis, pipe = self._mock_redis()
        pipe.execute.return_value = [None, 2, None, None]  # 2 current
        limiter = RedisRateLimiter(redis, default_limit=10)
        allowed, remaining, retry = limiter.is_allowed("c1")
        assert allowed is True
        assert remaining == 7
        assert retry == 0

    def test_is_allowed_at_limit(self):
        redis, pipe = self._mock_redis()
        pipe.execute.return_value = [None, 10, None, None]
        redis.zrange.return_value = [(b"entry", time.time() - 30)]
        limiter = RedisRateLimiter(redis, default_limit=10)
        allowed, remaining, retry = limiter.is_allowed("c1")
        assert allowed is False
        assert remaining == 0
        assert retry > 0

    def test_redis_error_fails_open(self):
        redis, pipe = self._mock_redis()
        pipe.execute.side_effect = Exception("Redis down")
        limiter = RedisRateLimiter(redis, default_limit=10)
        allowed, remaining, retry = limiter.is_allowed("c1")
        assert allowed is True

    def test_get_current_count(self):
        redis, _ = self._mock_redis()
        redis.zcard.return_value = 5
        limiter = RedisRateLimiter(redis)
        count = limiter.get_current_count("c1")
        assert count == 5

    def test_get_current_count_redis_error(self):
        redis, _ = self._mock_redis()
        redis.zremrangebyscore.side_effect = Exception("Redis error")
        limiter = RedisRateLimiter(redis)
        count = limiter.get_current_count("c1")
        assert count == 0

    def test_reset(self):
        redis, _ = self._mock_redis()
        limiter = RedisRateLimiter(redis)
        result = limiter.reset("c1")
        assert result is True
        redis.delete.assert_called_once()

    def test_reset_redis_error(self):
        redis, _ = self._mock_redis()
        redis.delete.side_effect = Exception("Redis error")
        limiter = RedisRateLimiter(redis)
        result = limiter.reset("c1")
        assert result is False

    @pytest.mark.parametrize("window_name", ["minute", "hour", "custom"])
    def test_different_window_names(self, window_name):
        redis, pipe = self._mock_redis()
        pipe.execute.return_value = [None, 0, None, None]
        limiter = RedisRateLimiter(redis)
        allowed, _, _ = limiter.is_allowed("c1", window_name=window_name)
        assert allowed is True


# ===================================================================
# RATE LIMIT MIDDLEWARE
# ===================================================================

class TestRedisRateLimitMiddleware:

    def test_default_exempt_paths(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app, requests_per_minute=60)
            assert "/health" in mw.exempt_paths
            assert "/api/health" in mw.exempt_paths
            assert "/metrics" in mw.exempt_paths

    def test_custom_exempt_paths(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app, exempt_paths={"/custom"})
            assert "/custom" in mw.exempt_paths

    def test_is_exempt_true(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app)
            assert mw._is_exempt("/health") is True
            assert mw._is_exempt("/api/health") is True

    def test_is_exempt_false(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app)
            assert mw._is_exempt("/api/advisor") is False

    @pytest.mark.parametrize("path,exempt", [
        ("/health", True),
        ("/health/check", True),
        ("/api/health", True),
        ("/metrics", True),
        ("/api/advisor", False),
        ("/api/scenarios", False),
    ])
    def test_exempt_path_patterns(self, path, exempt):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app)
            assert mw._is_exempt(path) == exempt

    def test_default_get_identifier_from_client(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app)
            request = Mock()
            request.headers = {}
            request.client.host = "192.168.1.1"
            assert mw._default_get_identifier(request) == "192.168.1.1"

    def test_get_identifier_from_forwarded_header(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app)
            request = Mock()
            request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}
            assert mw._default_get_identifier(request) == "10.0.0.1"

    def test_get_identifier_from_real_ip(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app)
            request = Mock()
            request.headers = {"X-Real-IP": "172.16.0.1"}
            assert mw._default_get_identifier(request) == "172.16.0.1"

    def test_get_identifier_no_client(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app)
            request = Mock()
            request.headers = {}
            request.client = None
            assert mw._default_get_identifier(request) == "unknown"

    def test_memory_limiter_always_created(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app, requests_per_minute=30)
            assert mw.memory_limiter is not None
            assert mw.memory_limiter.default_limit == 30

    def test_requests_per_minute_stored(self):
        app = Mock()
        with patch.object(RedisRateLimitMiddleware, '_init_redis'):
            mw = RedisRateLimitMiddleware(app, requests_per_minute=100, requests_per_hour=2000)
            assert mw.requests_per_minute == 100
            assert mw.requests_per_hour == 2000


# ===================================================================
# CIRCUIT BREAKER — STATE TRANSITIONS
# ===================================================================

class TestCircuitBreakerStates:

    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True

    def test_state_enum_values(self):
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_state_enum_count(self):
        assert len(CircuitState) == 3

    def test_transitions_to_open_after_failures(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=3))
        for _ in range(3):
            cb.record_failure(Exception("fail"))
        assert cb.state == CircuitState.OPEN
        assert cb.is_open is True

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=5))
        for _ in range(4):
            cb.record_failure(Exception("fail"))
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_closed_on_successes(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=2, success_threshold=2, timeout=0.01
        ))
        cb.record_failure(Exception())
        cb.record_failure(Exception())
        assert cb.is_open is True
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=1, timeout=0.01
        ))
        cb.record_failure(Exception())
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure(Exception())
        assert cb.state == CircuitState.OPEN

    def test_reset_returns_to_closed(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure(Exception())
        assert cb.is_open is True
        cb.reset()
        assert cb.is_closed is True
        assert cb.failure_count == 0

    def test_success_resets_failure_count_in_closed(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=5))
        cb.record_failure(Exception())
        cb.record_failure(Exception())
        assert cb.failure_count == 2
        cb.record_success()
        assert cb.failure_count == 0


# ===================================================================
# CIRCUIT BREAKER — CONFIGURATION
# ===================================================================

class TestCircuitBreakerConfig:

    def test_default_config(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 30.0

    @pytest.mark.parametrize("threshold", [1, 3, 5, 10, 100])
    def test_custom_failure_threshold(self, threshold):
        config = CircuitBreakerConfig(failure_threshold=threshold)
        assert config.failure_threshold == threshold

    @pytest.mark.parametrize("threshold", [1, 2, 5, 10])
    def test_custom_success_threshold(self, threshold):
        config = CircuitBreakerConfig(success_threshold=threshold)
        assert config.success_threshold == threshold

    @pytest.mark.parametrize("timeout", [1.0, 10.0, 30.0, 60.0, 300.0])
    def test_custom_timeout(self, timeout):
        config = CircuitBreakerConfig(timeout=timeout)
        assert config.timeout == timeout

    def test_custom_failure_exceptions(self):
        config = CircuitBreakerConfig(failure_exceptions=(ConnectionError, TimeoutError))
        assert ConnectionError in config.failure_exceptions

    def test_excluded_exceptions(self):
        config = CircuitBreakerConfig(excluded_exceptions=(ValueError,))
        assert ValueError in config.excluded_exceptions

    def test_callbacks(self):
        on_open = Mock()
        on_close = Mock()
        on_half_open = Mock()
        config = CircuitBreakerConfig(
            on_open=on_open, on_close=on_close, on_half_open=on_half_open
        )
        assert config.on_open is on_open
        assert config.on_close is on_close
        assert config.on_half_open is on_half_open


# ===================================================================
# CIRCUIT BREAKER — ALLOW REQUEST
# ===================================================================

class TestCircuitBreakerAllowRequest:

    def test_allow_when_closed(self):
        cb = CircuitBreaker("test")
        assert cb.allow_request() is True

    def test_reject_when_open(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1, timeout=60))
        cb.record_failure(Exception())
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            cb.allow_request()
        assert exc_info.value.circuit_name == "test"
        assert exc_info.value.time_remaining > 0

    def test_allow_when_half_open(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1, timeout=0.01))
        cb.record_failure(Exception())
        time.sleep(0.02)
        assert cb.allow_request() is True

    def test_circuit_breaker_open_exception_attributes(self):
        exc = CircuitBreakerOpen("msg", circuit_name="test_cb", time_remaining=30.0)
        assert exc.circuit_name == "test_cb"
        assert exc.time_remaining == 30.0
        assert str(exc) == "msg"


# ===================================================================
# CIRCUIT BREAKER — EXCLUDED EXCEPTIONS
# ===================================================================

class TestCircuitBreakerExcludedExceptions:

    def test_excluded_exception_not_counted(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=2, excluded_exceptions=(ValueError,)
        ))
        cb.record_failure(ValueError("not a real failure"))
        cb.record_failure(ValueError("still not"))
        assert cb.state == CircuitState.CLOSED

    def test_non_excluded_exception_counted(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=2, excluded_exceptions=(ValueError,)
        ))
        cb.record_failure(ConnectionError("real failure"))
        cb.record_failure(ConnectionError("another"))
        assert cb.state == CircuitState.OPEN


# ===================================================================
# CIRCUIT BREAKER — CALLBACKS
# ===================================================================

class TestCircuitBreakerCallbacks:

    def test_on_open_callback(self):
        on_open = Mock()
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=1, on_open=on_open
        ))
        cb.record_failure(Exception())
        on_open.assert_called_once_with(cb)

    def test_on_close_callback(self):
        on_close = Mock()
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=1, success_threshold=1, timeout=0.01, on_close=on_close
        ))
        cb.record_failure(Exception())
        time.sleep(0.02)
        _ = cb.state  # trigger half_open
        cb.record_success()
        on_close.assert_called_once_with(cb)

    def test_on_half_open_callback(self):
        on_half_open = Mock()
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(
            failure_threshold=1, timeout=0.01, on_half_open=on_half_open
        ))
        cb.record_failure(Exception())
        time.sleep(0.02)
        _ = cb.state
        on_half_open.assert_called_once_with(cb)


# ===================================================================
# CIRCUIT BREAKER — DECORATOR
# ===================================================================

class TestCircuitBreakerDecorator:

    def test_sync_function_decorator(self):
        cb = CircuitBreaker("test")

        @cb
        def my_func():
            return 42

        assert my_func() == 42

    def test_sync_function_records_success(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=5))
        cb.record_failure(Exception())
        assert cb.failure_count == 1

        @cb
        def my_func():
            return "ok"

        my_func()
        assert cb.failure_count == 0  # reset on success

    def test_sync_function_records_failure(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=5))

        @cb
        def my_func():
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError):
            my_func()
        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_async_function_decorator(self):
        cb = CircuitBreaker("test")

        @cb
        async def my_async_func():
            return 42

        result = await my_async_func()
        assert result == 42

    @pytest.mark.asyncio
    async def test_async_function_records_failure(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=5))

        @cb
        async def my_async_func():
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError):
            await my_async_func()
        assert cb.failure_count == 1


# ===================================================================
# CIRCUIT BREAKER — CONTEXT MANAGER
# ===================================================================

class TestCircuitBreakerContextManager:

    def test_sync_context_success(self):
        cb = CircuitBreaker("test")
        with cb:
            pass  # success
        assert cb.is_closed

    def test_sync_context_failure(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(ValueError):
            with cb:
                raise ValueError("fail")
        assert cb.is_open

    @pytest.mark.asyncio
    async def test_async_context_success(self):
        cb = CircuitBreaker("test")
        async with cb:
            pass
        assert cb.is_closed

    @pytest.mark.asyncio
    async def test_async_context_failure(self):
        cb = CircuitBreaker("test", config=CircuitBreakerConfig(failure_threshold=1))
        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("fail")
        assert cb.is_open


# ===================================================================
# CIRCUIT BREAKER REGISTRY
# ===================================================================

class TestCircuitBreakerRegistry:

    def test_create_registry(self):
        registry = CircuitBreakerRegistry()
        assert registry._breakers == {}

    def test_get_creates_new_breaker(self):
        registry = CircuitBreakerRegistry()
        breaker = registry.get("api")
        assert isinstance(breaker, CircuitBreaker)
        assert breaker.name == "api"

    def test_get_returns_same_breaker(self):
        registry = CircuitBreakerRegistry()
        b1 = registry.get("api")
        b2 = registry.get("api")
        assert b1 is b2

    def test_get_with_custom_config(self):
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=10)
        breaker = registry.get("api", config=config)
        assert breaker.config.failure_threshold == 10

    def test_remove_breaker(self):
        registry = CircuitBreakerRegistry()
        registry.get("api")
        registry.remove("api")
        assert "api" not in registry._breakers

    def test_remove_nonexistent_no_error(self):
        registry = CircuitBreakerRegistry()
        registry.remove("nonexistent")  # Should not raise

    def test_reset_all(self):
        registry = CircuitBreakerRegistry()
        b1 = registry.get("api1", CircuitBreakerConfig(failure_threshold=1))
        b2 = registry.get("api2", CircuitBreakerConfig(failure_threshold=1))
        b1.record_failure(Exception())
        b2.record_failure(Exception())
        assert b1.is_open
        assert b2.is_open
        registry.reset_all()
        assert b1.is_closed
        assert b2.is_closed

    def test_get_all_stats(self):
        registry = CircuitBreakerRegistry()
        registry.get("api1")
        registry.get("api2")
        stats = registry.get_all_stats()
        assert "api1" in stats
        assert "api2" in stats
        assert stats["api1"]["state"] == "closed"

    def test_get_all_stats_with_open_breaker(self):
        registry = CircuitBreakerRegistry()
        b = registry.get("api", CircuitBreakerConfig(failure_threshold=1))
        b.record_failure(Exception())
        stats = registry.get_all_stats()
        assert stats["api"]["state"] == "open"
        assert stats["api"]["is_open"] is True

    def test_global_registry(self):
        registry = get_circuit_breaker_registry()
        assert isinstance(registry, CircuitBreakerRegistry)


# ===================================================================
# IDEMPOTENCY RECORD
# ===================================================================

class TestIdempotencyRecord:

    def test_record_creation(self):
        record = IdempotencyRecord(
            idempotency_key="key-123",
            request_hash="abc123",
            response_status=200,
            response_body='{"result": "ok"}',
            response_headers={"Content-Type": "application/json"},
            created_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(hours=24)).isoformat(),
        )
        assert record.idempotency_key == "key-123"
        assert record.response_status == 200

    @pytest.mark.parametrize("status", [200, 201, 202, 400, 404, 500])
    def test_record_status_codes(self, status):
        record = IdempotencyRecord(
            idempotency_key="k",
            request_hash="h",
            response_status=status,
            response_body="{}",
            response_headers={},
            created_at="2025-01-01T00:00:00",
            expires_at="2025-01-02T00:00:00",
        )
        assert record.response_status == status

    def test_record_with_empty_headers(self):
        record = IdempotencyRecord(
            idempotency_key="k", request_hash="h", response_status=200,
            response_body="{}", response_headers={},
            created_at="now", expires_at="later"
        )
        assert record.response_headers == {}


# ===================================================================
# IDEMPOTENCY STORE
# ===================================================================

class TestIdempotencyStore:

    @pytest.fixture
    def store(self, tmp_path):
        db_path = tmp_path / "test_idempotency.db"
        return IdempotencyStore(db_path=db_path, ttl_hours=1)

    def test_table_created(self, store):
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='idempotency_records'"
            )
            assert cursor.fetchone() is not None

    def test_set_and_get(self, store):
        store.set("key-1", "hash-1", 200, '{"ok":true}')
        record = store.get("key-1")
        assert record is not None
        assert record.idempotency_key == "key-1"
        assert record.request_hash == "hash-1"
        assert record.response_status == 200

    def test_get_nonexistent_key(self, store):
        record = store.get("no-such-key")
        assert record is None

    def test_get_expired_record(self, store):
        store.set("key-expired", "hash", 200, "{}")
        # Manually update to expired
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "UPDATE idempotency_records SET expires_at = ? WHERE idempotency_key = ?",
                ("2020-01-01T00:00:00", "key-expired")
            )
            conn.commit()
        record = store.get("key-expired")
        assert record is None

    def test_set_with_headers(self, store):
        headers = {"X-Custom": "value"}
        store.set("key-h", "hash", 200, "{}", response_headers=headers)
        record = store.get("key-h")
        assert record.response_headers == {"X-Custom": "value"}

    def test_set_overwrite_existing(self, store):
        store.set("key-1", "hash-1", 200, '{"v":1}')
        store.set("key-1", "hash-2", 201, '{"v":2}')
        record = store.get("key-1")
        assert record.request_hash == "hash-2"
        assert record.response_status == 201

    def test_delete_existing(self, store):
        store.set("key-del", "hash", 200, "{}")
        result = store.delete("key-del")
        assert result is True
        assert store.get("key-del") is None

    def test_delete_nonexistent(self, store):
        result = store.delete("no-such-key")
        assert result is False

    def test_cleanup_expired(self, store):
        store.set("key-1", "hash", 200, "{}")
        store.set("key-2", "hash", 200, "{}")
        # Expire key-1
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "UPDATE idempotency_records SET expires_at = ? WHERE idempotency_key = ?",
                ("2020-01-01T00:00:00", "key-1")
            )
            conn.commit()
        removed = store.cleanup_expired()
        assert removed == 1
        assert store.get("key-1") is None
        assert store.get("key-2") is not None

    @pytest.mark.parametrize("ttl_hours", [1, 12, 24, 48])
    def test_ttl_configuration(self, tmp_path, ttl_hours):
        db_path = tmp_path / f"test_ttl_{ttl_hours}.db"
        store = IdempotencyStore(db_path=db_path, ttl_hours=ttl_hours)
        assert store.ttl_hours == ttl_hours

    def test_multiple_records(self, store):
        for i in range(10):
            store.set(f"key-{i}", f"hash-{i}", 200, f'{{"i":{i}}}')
        for i in range(10):
            record = store.get(f"key-{i}")
            assert record is not None
            assert record.idempotency_key == f"key-{i}"


# ===================================================================
# COMPUTE REQUEST HASH
# ===================================================================

class TestComputeRequestHash:

    def test_hash_deterministic(self):
        h1 = compute_request_hash("POST", "/api/submit", b'{"a":1}')
        h2 = compute_request_hash("POST", "/api/submit", b'{"a":1}')
        assert h1 == h2

    def test_hash_is_sha256(self):
        h = compute_request_hash("POST", "/api/submit", b'{"a":1}')
        assert len(h) == 64  # SHA-256 hex digest

    def test_different_methods_different_hash(self):
        h1 = compute_request_hash("POST", "/api/submit", b'{}')
        h2 = compute_request_hash("PUT", "/api/submit", b'{}')
        assert h1 != h2

    def test_different_paths_different_hash(self):
        h1 = compute_request_hash("POST", "/api/a", b'{}')
        h2 = compute_request_hash("POST", "/api/b", b'{}')
        assert h1 != h2

    def test_different_bodies_different_hash(self):
        h1 = compute_request_hash("POST", "/api/submit", b'{"a":1}')
        h2 = compute_request_hash("POST", "/api/submit", b'{"a":2}')
        assert h1 != h2

    def test_empty_body(self):
        h = compute_request_hash("GET", "/api", b"")
        assert len(h) == 64

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    def test_all_http_methods(self, method):
        h = compute_request_hash(method, "/api", b"")
        assert isinstance(h, str)
        assert len(h) == 64


# ===================================================================
# IDEMPOTENCY HEADER CONSTANT
# ===================================================================

class TestIdempotencyConstants:

    def test_header_name(self):
        assert IDEMPOTENCY_KEY_HEADER == "X-Idempotency-Key"

    def test_default_ttl(self):
        assert DEFAULT_TTL_HOURS == 24


# ===================================================================
# REQUIRE IDEMPOTENCY KEY
# ===================================================================

class TestRequireIdempotencyKey:

    def test_returns_key_when_present(self):
        request = Mock()
        headers = MagicMock()
        headers.get = Mock(return_value="my-key-123")
        request.headers = headers
        key = require_idempotency_key(request)
        assert key == "my-key-123"

    def test_raises_when_missing(self):
        request = Mock()
        headers = MagicMock()
        headers.get = Mock(return_value=None)
        request.headers = headers
        with pytest.raises(ValueError):
            require_idempotency_key(request)


# ===================================================================
# GENERATE IDEMPOTENCY KEY
# ===================================================================

class TestGenerateIdempotencyKey:

    def test_generates_string(self):
        key = generate_idempotency_key()
        assert isinstance(key, str)

    def test_generates_uuid_format(self):
        key = generate_idempotency_key()
        parts = key.split("-")
        assert len(parts) == 5

    def test_unique_keys(self):
        keys = {generate_idempotency_key() for _ in range(100)}
        assert len(keys) == 100
