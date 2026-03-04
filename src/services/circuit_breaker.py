"""Circuit breaker pattern for external service calls.

Implements a three-state circuit breaker (closed/open/half-open) to prevent
cascading failures when external services (OpenAI, etc.) are unavailable.
"""

import hashlib
import json
import logging
import time
import threading
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker with configurable thresholds.

    Usage:
        breaker = CircuitBreaker(name="openai", failure_threshold=5, recovery_timeout=60)

        try:
            result = await breaker.call(some_async_function, *args, **kwargs)
        except CircuitOpenError:
            # Use fallback
            result = get_cached_response(...)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exceptions: tuple = (Exception,),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_successes = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and (
                time.time() - self._last_failure_time > self.recovery_timeout
            ):
                self._state = CircuitState.HALF_OPEN
                self._half_open_successes = 0
                logger.info("Circuit breaker '%s' transitioning to HALF_OPEN", self.name)
        return self._state

    def _record_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= 3:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker '%s' CLOSED (recovered)", self.name)
            else:
                self._failure_count = 0

    def _record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s' OPEN after %d failures",
                    self.name,
                    self._failure_count,
                )

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute function through the circuit breaker.

        Raises:
            CircuitOpenError: If circuit is open and recovery timeout hasn't elapsed.
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit breaker '{self.name}' is OPEN — service unavailable"
            )

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exceptions as exc:
            self._record_failure()
            raise

    def reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            logger.info("Circuit breaker '%s' manually reset", self.name)


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open."""
    pass


# Response cache for AI calls
class ResponseCache:
    """Simple in-memory cache for AI responses.

    For production, back with Redis.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self._cache: dict = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()

    @staticmethod
    def _make_key(prompt: str, **kwargs) -> str:
        content = json.dumps({"prompt": prompt, **kwargs}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, prompt: str, **kwargs) -> Optional[Any]:
        key = self._make_key(prompt, **kwargs)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.time() > expiry:
                del self._cache[key]
                return None
            return value

    def set(self, prompt: str, value: Any, ttl: Optional[int] = None, **kwargs):
        key = self._make_key(prompt, **kwargs)
        expiry = time.time() + (ttl or self._default_ttl)
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evict oldest entries
                oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            self._cache[key] = (value, expiry)


# Global instances
ai_circuit_breaker = CircuitBreaker(
    name="openai",
    failure_threshold=5,
    recovery_timeout=60,
)
ai_response_cache = ResponseCache(max_size=1000, default_ttl=3600)
