"""Circuit Breaker pattern for fault tolerance.

Implements the circuit breaker pattern to prevent cascading failures
when calling external services. The circuit has three states:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests are rejected immediately
- HALF_OPEN: Testing if service has recovered
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from threading import Lock
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
ExceptionTypes = Union[Type[Exception], Tuple[Type[Exception], ...]]


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""

    def __init__(
        self,
        message: str,
        circuit_name: str,
        time_remaining: float,
    ):
        super().__init__(message)
        self.circuit_name = circuit_name
        self.time_remaining = time_remaining


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker.

    Attributes:
        failure_threshold: Number of failures before opening circuit.
        success_threshold: Number of successes in half-open to close.
        timeout: Seconds to wait before trying half-open.
        failure_exceptions: Exceptions that count as failures.
        excluded_exceptions: Exceptions that don't count as failures.
        on_open: Callback when circuit opens.
        on_close: Callback when circuit closes.
        on_half_open: Callback when circuit goes half-open.
    """
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 30.0
    failure_exceptions: ExceptionTypes = (Exception,)
    excluded_exceptions: ExceptionTypes = ()
    on_open: Optional[Callable[["CircuitBreaker"], None]] = None
    on_close: Optional[Callable[["CircuitBreaker"], None]] = None
    on_half_open: Optional[Callable[["CircuitBreaker"], None]] = None


class CircuitBreaker:
    """Circuit breaker for fault tolerance.

    Usage:
        # As decorator
        breaker = CircuitBreaker(name="external_api")

        @breaker
        async def call_api():
            ...

        # As context manager
        async with breaker:
            await call_api()

        # Manual usage
        if breaker.allow_request():
            try:
                result = await call_api()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure(e)
                raise

    State transitions:
        CLOSED -> OPEN: failure_threshold failures reached
        OPEN -> HALF_OPEN: timeout elapsed
        HALF_OPEN -> CLOSED: success_threshold successes
        HALF_OPEN -> OPEN: any failure
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        **kwargs: Any,
    ):
        """Initialize circuit breaker.

        Args:
            name: Unique identifier for this circuit.
            config: CircuitBreakerConfig or kwargs for it.
        """
        self.name = name
        self.config = config or CircuitBreakerConfig(**kwargs)

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._get_state()

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)."""
        return self.state == CircuitState.HALF_OPEN

    def _get_state(self) -> CircuitState:
        """Get state with automatic transition check."""
        if self._state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.config.timeout:
                    self._transition_to_half_open()
        return self._state

    def _transition_to_open(self) -> None:
        """Transition to open state."""
        self._state = CircuitState.OPEN
        self._last_failure_time = time.time()
        logger.warning(f"Circuit breaker '{self.name}' OPENED")

        if self.config.on_open:
            self.config.on_open(self)

    def _transition_to_closed(self) -> None:
        """Transition to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        logger.info(f"Circuit breaker '{self.name}' CLOSED")

        if self.config.on_close:
            self.config.on_close(self)

    def _transition_to_half_open(self) -> None:
        """Transition to half-open state."""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        logger.info(f"Circuit breaker '{self.name}' HALF-OPEN")

        if self.config.on_half_open:
            self.config.on_half_open(self)

    def _is_failure_exception(self, exception: Exception) -> bool:
        """Check if exception should count as failure."""
        # Check excluded first
        if self.config.excluded_exceptions:
            if isinstance(exception, self.config.excluded_exceptions):
                return False

        return isinstance(exception, self.config.failure_exceptions)

    def allow_request(self) -> bool:
        """Check if a request should be allowed.

        Returns:
            True if request should proceed.

        Raises:
            CircuitBreakerOpen: If circuit is open.
        """
        with self._lock:
            state = self._get_state()

            if state == CircuitState.CLOSED:
                return True

            if state == CircuitState.HALF_OPEN:
                return True

            # OPEN state
            time_remaining = 0.0
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                time_remaining = max(0, self.config.timeout - elapsed)

            raise CircuitBreakerOpen(
                f"Circuit breaker '{self.name}' is open",
                circuit_name=self.name,
                time_remaining=time_remaining,
            )

    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                self._failure_count = 0

    def record_failure(self, exception: Exception) -> None:
        """Record a failed operation.

        Args:
            exception: The exception that occurred.
        """
        if not self._is_failure_exception(exception):
            return

        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                self._transition_to_open()

            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to_open()

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        with self._lock:
            self._transition_to_closed()

    def __call__(
        self,
        func: Callable[..., T],
    ) -> Callable[..., T]:
        """Use circuit breaker as decorator.

        Args:
            func: Function to wrap.

        Returns:
            Wrapped function with circuit breaker.
        """
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                self.allow_request()  # May raise CircuitBreakerOpen
                try:
                    result = await func(*args, **kwargs)
                    self.record_success()
                    return result
                except Exception as e:
                    self.record_failure(e)
                    raise

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> T:
                self.allow_request()
                try:
                    result = func(*args, **kwargs)
                    self.record_success()
                    return result
                except Exception as e:
                    self.record_failure(e)
                    raise

            return sync_wrapper

    async def __aenter__(self) -> "CircuitBreaker":
        """Enter async context."""
        self.allow_request()  # May raise CircuitBreakerOpen
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit async context."""
        if exc_type is None:
            self.record_success()
        elif exc_val is not None:
            self.record_failure(exc_val)
        return False  # Don't suppress exceptions

    def __enter__(self) -> "CircuitBreaker":
        """Enter sync context."""
        self.allow_request()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit sync context."""
        if exc_type is None:
            self.record_success()
        elif exc_val is not None:
            self.record_failure(exc_val)
        return False


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers.

    Usage:
        registry = CircuitBreakerRegistry()

        # Get or create circuit breaker
        breaker = registry.get("external_api")

        # Get stats for all breakers
        stats = registry.get_all_stats()
    """

    def __init__(
        self,
        default_config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize registry.

        Args:
            default_config: Default config for new circuit breakers.
        """
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._default_config = default_config or CircuitBreakerConfig()
        self._lock = Lock()

    def get(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker.

        Args:
            name: Circuit breaker name.
            config: Optional config (uses default if not provided).

        Returns:
            CircuitBreaker instance.
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    config=config or self._default_config,
                )
            return self._breakers[name]

    def remove(self, name: str) -> None:
        """Remove a circuit breaker.

        Args:
            name: Circuit breaker name.
        """
        with self._lock:
            self._breakers.pop(name, None)

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers.

        Returns:
            Dict mapping names to stats.
        """
        with self._lock:
            return {
                name: {
                    "state": breaker.state.value,
                    "failure_count": breaker.failure_count,
                    "is_open": breaker.is_open,
                }
                for name, breaker in self._breakers.items()
            }


# Global registry instance
_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry.

    Returns:
        Global CircuitBreakerRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry


def circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to apply circuit breaker from registry.

    Usage:
        @circuit_breaker("external_api")
        async def call_api():
            ...

    Args:
        name: Circuit breaker name.
        config: Optional configuration.

    Returns:
        Decorator function.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker = get_circuit_breaker_registry().get(name, config)
        return breaker(func)

    return decorator
