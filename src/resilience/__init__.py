"""Resilience patterns for robust service communication.

Provides retry logic with exponential backoff and circuit breakers
for fault tolerance when calling external services.
"""

from .retry import (
    async_retry,
    sync_retry,
    RetryConfig,
    RetryContext,
    RetryExhausted,
)

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_breaker,
    get_circuit_breaker_registry,
)

__all__ = [
    # Retry
    "async_retry",
    "sync_retry",
    "RetryConfig",
    "RetryContext",
    "RetryExhausted",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpen",
    "CircuitBreakerRegistry",
    "CircuitState",
    "circuit_breaker",
    "get_circuit_breaker_registry",
]
