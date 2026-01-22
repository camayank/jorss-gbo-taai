"""
Circuit Breaker Pattern

Prevents cascading failures by failing fast when external services are down.

Usage:
    breaker = CircuitBreaker(name="ocr_service", failure_threshold=5, timeout=60)

    try:
        result = await breaker.call(ocr_service.process, document)
    except CircuitBreakerOpen:
        # Handle gracefully - use fallback or cached data
        result = fallback_processing(document)
"""

from typing import Callable, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import asyncio

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing - reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation.

    States:
    - CLOSED: Normal operation, track failures
    - OPEN: Service is down, fail fast
    - HALF_OPEN: Test if service recovered

    Args:
        name: Name of the service
        failure_threshold: Number of failures before opening
        timeout: Seconds to wait before trying again (half-open)
        success_threshold: Successes needed in half-open to close
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: int = 60,
        success_threshold: int = 2
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold

        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change = datetime.now()

        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result from function

        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        self.total_calls += 1

        # Check if circuit should transition to half-open
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker {self.name}: Transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                logger.warning(f"Circuit breaker {self.name}: OPEN - failing fast")
                raise CircuitBreakerOpen(
                    f"Circuit breaker {self.name} is OPEN. Service unavailable."
                )

        # Execute function
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        """Handle successful call"""
        self.total_successes += 1
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1

            if self.success_count >= self.success_threshold:
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED (service recovered)")
                self.state = CircuitState.CLOSED
                self.success_count = 0
                self.last_state_change = datetime.now()

    def _on_failure(self, exception: Exception):
        """Handle failed call"""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        logger.warning(f"Circuit breaker {self.name}: Failure {self.failure_count}/{self.failure_threshold} - {type(exception).__name__}")

        if self.state == CircuitState.HALF_OPEN:
            # Immediately open on failure in half-open state
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (service still failing)")
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.now()

        elif self.failure_count >= self.failure_threshold:
            logger.error(f"Circuit breaker {self.name}: CLOSED -> OPEN (threshold reached)")
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.now()

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open"""
        if self.last_failure_time is None:
            return True

        time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.timeout

    def reset(self):
        """Manually reset circuit breaker"""
        logger.info(f"Circuit breaker {self.name}: Manual reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()

    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "success_rate": f"{(self.total_successes / max(self.total_calls, 1)) * 100:.1f}%",
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_state_change": self.last_state_change.isoformat()
        }


# =============================================================================
# Global Circuit Breakers
# =============================================================================

# Circuit breakers for external services
_circuit_breakers = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout: int = 60,
    success_threshold: int = 2
) -> CircuitBreaker:
    """
    Get or create a circuit breaker for a service.

    Args:
        name: Service name
        failure_threshold: Failures before opening
        timeout: Seconds before attempting reset
        success_threshold: Successes needed to close

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            timeout=timeout,
            success_threshold=success_threshold
        )

    return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict:
    """Get status of all circuit breakers"""
    return {
        name: breaker.get_status()
        for name, breaker in _circuit_breakers.items()
    }


def reset_circuit_breaker(name: str):
    """Reset a specific circuit breaker"""
    if name in _circuit_breakers:
        _circuit_breakers[name].reset()


def reset_all_circuit_breakers():
    """Reset all circuit breakers"""
    for breaker in _circuit_breakers.values():
        breaker.reset()


# =============================================================================
# Example Usage
# =============================================================================

async def example_usage():
    """Example of using circuit breaker"""

    # Get circuit breaker for OCR service
    ocr_breaker = get_circuit_breaker("ocr_service", failure_threshold=3, timeout=30)

    # Simulated OCR function
    async def process_document(doc):
        # This might fail if OCR service is down
        # raise Exception("OCR service unavailable")
        return {"text": "extracted text"}

    try:
        # Call through circuit breaker
        result = await ocr_breaker.call(process_document, "document.pdf")
        print("OCR Success:", result)

    except CircuitBreakerOpen:
        # Circuit is open - use fallback
        print("OCR unavailable, using manual entry")
        result = {"text": ""}

    except Exception as e:
        # Other errors
        print(f"OCR error: {e}")
        result = {"text": ""}

    # Check status
    print("Circuit status:", ocr_breaker.get_status())
