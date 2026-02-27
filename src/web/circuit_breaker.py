"""
Circuit Breaker — re-exports from src/resilience/circuit_breaker.py.

This module provides backward-compatible functions for admin_endpoints.py.
All circuit breaker logic lives in resilience.circuit_breaker.
"""

from resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)

# Re-export the CircuitBreakerOpen exception
try:
    from resilience.circuit_breaker import CircuitBreakerOpen
except ImportError:
    class CircuitBreakerOpen(Exception):
        """Raised when circuit breaker is open."""
        pass


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout: int = 60,
    success_threshold: int = 2,
) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    registry = get_circuit_breaker_registry()
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        recovery_timeout=float(timeout),
        success_threshold=success_threshold,
    )
    return registry.get(name, config)


def get_all_circuit_breakers() -> dict:
    """Get status of all circuit breakers."""
    registry = get_circuit_breaker_registry()
    return registry.get_all_stats()


def reset_circuit_breaker(name: str):
    """Reset a specific circuit breaker."""
    registry = get_circuit_breaker_registry()
    breaker = registry._breakers.get(name)
    if breaker:
        breaker.reset()


def reset_all_circuit_breakers():
    """Reset all circuit breakers."""
    registry = get_circuit_breaker_registry()
    registry.reset_all()
