"""Tests for resilience patterns (retry and circuit breaker)."""

import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch

from resilience.retry import (
    RetryConfig,
    RetryExhausted,
    async_retry,
    sync_retry,
    RetryContext,
)
from resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitState,
    CircuitBreakerRegistry,
    get_circuit_breaker_registry,
    circuit_breaker,
)


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_multiplier == 2.0
        assert config.jitter == 0.1
        assert config.retryable_exceptions == (Exception,)
        assert config.non_retryable_exceptions == ()

    def test_calculate_delay_exponential_backoff(self):
        """Delay should increase exponentially."""
        config = RetryConfig(base_delay=1.0, backoff_multiplier=2.0, jitter=0)
        assert config.calculate_delay(1) == 1.0
        assert config.calculate_delay(2) == 2.0
        assert config.calculate_delay(3) == 4.0
        assert config.calculate_delay(4) == 8.0

    def test_calculate_delay_respects_max(self):
        """Delay should be capped at max_delay."""
        config = RetryConfig(base_delay=10.0, backoff_multiplier=2.0, max_delay=15.0, jitter=0)
        assert config.calculate_delay(1) == 10.0
        assert config.calculate_delay(2) == 15.0  # Capped
        assert config.calculate_delay(3) == 15.0  # Still capped

    def test_calculate_delay_with_jitter(self):
        """Delay should include jitter."""
        config = RetryConfig(base_delay=1.0, jitter=0.5)
        delays = [config.calculate_delay(1) for _ in range(100)]
        # With 50% jitter, delays should vary between 0.5 and 1.5
        assert all(0.0 <= d <= 2.0 for d in delays)
        # Should have some variance
        assert len(set(delays)) > 1

    def test_should_retry_retryable_exception(self):
        """Should retry for retryable exceptions."""
        config = RetryConfig(retryable_exceptions=(ValueError,))
        assert config.should_retry(ValueError("test")) is True
        assert config.should_retry(TypeError("test")) is False

    def test_should_retry_non_retryable_exception(self):
        """Should not retry for non-retryable exceptions."""
        config = RetryConfig(
            retryable_exceptions=(Exception,),
            non_retryable_exceptions=(KeyboardInterrupt,),
        )
        assert config.should_retry(ValueError("test")) is True
        assert config.should_retry(KeyboardInterrupt()) is False


class TestAsyncRetry:
    """Tests for async_retry decorator."""

    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        """Successful call should not retry."""
        call_count = 0

        @async_retry(max_attempts=3)
        async def my_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await my_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Should retry on failure."""
        call_count = 0

        @async_retry(max_attempts=3, base_delay=0.01)
        async def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"

        result = await my_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhaust_retries(self):
        """Should raise RetryExhausted when all retries fail."""
        call_count = 0

        @async_retry(max_attempts=3, base_delay=0.01)
        async def my_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent error")

        with pytest.raises(RetryExhausted) as exc_info:
            await my_func()

        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, ValueError)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        """Should not retry non-retryable exceptions."""
        call_count = 0

        @async_retry(
            max_attempts=3,
            retryable_exceptions=(ValueError,),
            base_delay=0.01,
        )
        async def my_func():
            nonlocal call_count
            call_count += 1
            raise TypeError("non-retryable")

        with pytest.raises(TypeError):
            await my_func()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Should call on_retry callback."""
        retry_calls = []

        def on_retry(attempt, exception, delay):
            retry_calls.append((attempt, type(exception).__name__, delay))

        @async_retry(max_attempts=3, base_delay=0.01, on_retry=on_retry)
        async def my_func():
            if len(retry_calls) < 2:
                raise ValueError("error")
            return "success"

        await my_func()
        assert len(retry_calls) == 2
        assert retry_calls[0][0] == 1
        assert retry_calls[1][0] == 2

    @pytest.mark.asyncio
    async def test_with_config_object(self):
        """Should work with RetryConfig object."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        call_count = 0

        @async_retry(config=config)
        async def my_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("error")

        with pytest.raises(RetryExhausted):
            await my_func()

        assert call_count == 2


class TestSyncRetry:
    """Tests for sync_retry decorator."""

    def test_successful_call_no_retry(self):
        """Successful call should not retry."""
        call_count = 0

        @sync_retry(max_attempts=3)
        def my_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = my_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure(self):
        """Should retry on failure."""
        call_count = 0

        @sync_retry(max_attempts=3, base_delay=0.01)
        def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"

        result = my_func()
        assert result == "success"
        assert call_count == 3

    def test_exhaust_retries(self):
        """Should raise RetryExhausted when all retries fail."""
        call_count = 0

        @sync_retry(max_attempts=3, base_delay=0.01)
        def my_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent error")

        with pytest.raises(RetryExhausted):
            my_func()

        assert call_count == 3


class TestRetryContext:
    """Tests for RetryContext class."""

    @pytest.mark.asyncio
    async def test_basic_usage(self):
        """Should work for basic retry loop."""
        attempt = 0

        async with RetryContext(max_attempts=3, base_delay=0.01) as ctx:
            while ctx.should_continue:
                try:
                    attempt += 1
                    if attempt < 3:
                        raise ValueError("error")
                    break
                except Exception as e:
                    await ctx.handle_exception(e)

        assert attempt == 3

    @pytest.mark.asyncio
    async def test_exhausted(self):
        """Should raise RetryExhausted when exhausted."""
        async with RetryContext(max_attempts=2, base_delay=0.01) as ctx:
            with pytest.raises(RetryExhausted):
                while ctx.should_continue:
                    try:
                        raise ValueError("error")
                    except Exception as e:
                        await ctx.handle_exception(e)


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig class."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 30.0
        assert config.failure_exceptions == (Exception,)
        assert config.excluded_exceptions == ()


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_closed(self):
        """Circuit should start in CLOSED state."""
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open

    def test_allow_request_when_closed(self):
        """Should allow requests when closed."""
        breaker = CircuitBreaker("test")
        assert breaker.allow_request() is True

    def test_opens_after_threshold_failures(self):
        """Circuit should open after reaching failure threshold."""
        breaker = CircuitBreaker("test", failure_threshold=3)

        for _ in range(3):
            breaker.record_failure(ValueError("error"))

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open

    def test_rejects_requests_when_open(self):
        """Should reject requests when open."""
        breaker = CircuitBreaker("test", failure_threshold=1)
        breaker.record_failure(ValueError("error"))

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            breaker.allow_request()

        assert exc_info.value.circuit_name == "test"

    def test_transitions_to_half_open_after_timeout(self):
        """Should transition to HALF_OPEN after timeout."""
        breaker = CircuitBreaker("test", failure_threshold=1, timeout=0.01)
        breaker.record_failure(ValueError("error"))
        assert breaker.is_open

        time.sleep(0.02)

        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.is_half_open

    def test_closes_after_success_threshold_in_half_open(self):
        """Should close after success threshold in HALF_OPEN."""
        breaker = CircuitBreaker("test", failure_threshold=1, success_threshold=2, timeout=0.01)
        breaker.record_failure(ValueError("error"))
        time.sleep(0.02)  # Go to HALF_OPEN

        assert breaker.is_half_open

        breaker.record_success()
        assert breaker.is_half_open  # Not yet closed

        breaker.record_success()
        assert breaker.is_closed  # Now closed

    def test_reopens_on_failure_in_half_open(self):
        """Should reopen on any failure in HALF_OPEN."""
        breaker = CircuitBreaker("test", failure_threshold=1, timeout=0.01)
        breaker.record_failure(ValueError("error"))
        time.sleep(0.02)  # Go to HALF_OPEN

        assert breaker.is_half_open

        breaker.record_failure(ValueError("error"))
        assert breaker.is_open

    def test_excluded_exceptions_dont_count(self):
        """Excluded exceptions should not count as failures."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            failure_exceptions=(Exception,),
            excluded_exceptions=(KeyboardInterrupt,),
        )
        breaker = CircuitBreaker("test", config=config)

        # KeyboardInterrupt should not count
        breaker.record_failure(KeyboardInterrupt())
        assert breaker.failure_count == 0

        # ValueError should count
        breaker.record_failure(ValueError("error"))
        assert breaker.failure_count == 1

    def test_reset(self):
        """reset should return circuit to CLOSED state."""
        breaker = CircuitBreaker("test", failure_threshold=1)
        breaker.record_failure(ValueError("error"))
        assert breaker.is_open

        breaker.reset()
        assert breaker.is_closed
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_decorator_async(self):
        """Should work as async decorator."""
        breaker = CircuitBreaker("test", failure_threshold=2)
        call_count = 0

        @breaker
        async def my_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await my_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_records_success(self):
        """Decorator should record success."""
        breaker = CircuitBreaker("test", failure_threshold=2)
        breaker._failure_count = 1  # Simulate previous failure

        @breaker
        async def my_func():
            return "success"

        await my_func()
        assert breaker.failure_count == 0  # Reset on success

    @pytest.mark.asyncio
    async def test_decorator_records_failure(self):
        """Decorator should record failure."""
        breaker = CircuitBreaker("test", failure_threshold=2)

        @breaker
        async def my_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await my_func()

        assert breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Should work as async context manager."""
        breaker = CircuitBreaker("test")

        async with breaker:
            pass  # Success

        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_async_context_manager_records_failure(self):
        """Context manager should record failure."""
        breaker = CircuitBreaker("test")

        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("error")

        assert breaker.failure_count == 1

    def test_sync_decorator(self):
        """Should work as sync decorator."""
        breaker = CircuitBreaker("test")
        call_count = 0

        @breaker
        def my_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = my_func()
        assert result == "success"
        assert call_count == 1

    def test_sync_context_manager(self):
        """Should work as sync context manager."""
        breaker = CircuitBreaker("test")

        with breaker:
            pass  # Success

        assert breaker.failure_count == 0

    def test_callbacks(self):
        """Should call callbacks on state transitions."""
        on_open = MagicMock()
        on_close = MagicMock()
        on_half_open = MagicMock()

        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=1,
            timeout=0.01,
            on_open=on_open,
            on_close=on_close,
            on_half_open=on_half_open,
        )
        breaker = CircuitBreaker("test", config=config)

        # Open
        breaker.record_failure(ValueError("error"))
        on_open.assert_called_once()

        # Half-open
        time.sleep(0.02)
        _ = breaker.state  # Trigger state check
        on_half_open.assert_called_once()

        # Close
        breaker.record_success()
        on_close.assert_called_once()


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""

    def test_get_creates_new_breaker(self):
        """get should create new breaker if not exists."""
        registry = CircuitBreakerRegistry()
        breaker = registry.get("test")
        assert isinstance(breaker, CircuitBreaker)
        assert breaker.name == "test"

    def test_get_returns_same_breaker(self):
        """get should return same breaker for same name."""
        registry = CircuitBreakerRegistry()
        breaker1 = registry.get("test")
        breaker2 = registry.get("test")
        assert breaker1 is breaker2

    def test_get_with_custom_config(self):
        """get should use custom config."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=10)
        breaker = registry.get("test", config)
        assert breaker.config.failure_threshold == 10

    def test_remove(self):
        """remove should remove breaker from registry."""
        registry = CircuitBreakerRegistry()
        _ = registry.get("test")
        registry.remove("test")
        # Getting again should create new instance
        breaker2 = registry.get("test")
        assert breaker2.failure_count == 0

    def test_reset_all(self):
        """reset_all should reset all breakers."""
        registry = CircuitBreakerRegistry()
        breaker1 = registry.get("test1", CircuitBreakerConfig(failure_threshold=1))
        breaker2 = registry.get("test2", CircuitBreakerConfig(failure_threshold=1))

        breaker1.record_failure(ValueError())
        breaker2.record_failure(ValueError())

        registry.reset_all()

        assert breaker1.is_closed
        assert breaker2.is_closed

    def test_get_all_stats(self):
        """get_all_stats should return stats for all breakers."""
        registry = CircuitBreakerRegistry()
        _ = registry.get("test1")
        breaker2 = registry.get("test2", CircuitBreakerConfig(failure_threshold=1))
        breaker2.record_failure(ValueError())

        stats = registry.get_all_stats()

        assert "test1" in stats
        assert "test2" in stats
        assert stats["test1"]["state"] == "closed"
        assert stats["test2"]["state"] == "open"


class TestCircuitBreakerDecorator:
    """Tests for circuit_breaker decorator function."""

    def setup_method(self):
        """Reset global registry."""
        import resilience.circuit_breaker as module
        module._registry = None

    @pytest.mark.asyncio
    async def test_decorator_uses_registry(self):
        """Decorator should use global registry."""
        @circuit_breaker("test_decorator")
        async def my_func():
            return "success"

        result = await my_func()
        assert result == "success"

        registry = get_circuit_breaker_registry()
        assert "test_decorator" in registry.get_all_stats()
