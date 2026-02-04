"""
AI Provider Rate Limiter.

Simple in-memory token bucket rate limiter keyed by provider name.
Enforces the rate_limit_rpm configured per provider.
"""

import time
import threading
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class AIRateLimiter:
    """In-memory token bucket rate limiter for AI providers."""

    def __init__(self):
        self._buckets: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def check_rate_limit(self, provider: str, rpm: int) -> bool:
        """
        Check if a request to the given provider is allowed.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")
            rpm: Requests per minute limit

        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()

        with self._lock:
            if provider not in self._buckets:
                self._buckets[provider] = {
                    "tokens": rpm,
                    "last_update": now,
                    "rpm": rpm,
                }

            bucket = self._buckets[provider]

            # Refill tokens based on elapsed time
            elapsed = now - bucket["last_update"]
            tokens_to_add = elapsed * (rpm / 60.0)
            bucket["tokens"] = min(rpm, bucket["tokens"] + tokens_to_add)
            bucket["last_update"] = now

            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True

            return False

    def wait_time(self, provider: str, rpm: int) -> float:
        """Return seconds to wait before next request is allowed."""
        with self._lock:
            bucket = self._buckets.get(provider)
            if bucket is None or bucket["tokens"] >= 1:
                return 0.0
            # Time to refill 1 token
            return 60.0 / rpm


class RateLimitExceededError(Exception):
    """Raised when an AI provider's rate limit is exceeded."""

    def __init__(self, provider: str, retry_after: float):
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for provider '{provider}'. "
            f"Retry after {retry_after:.1f}s."
        )


# Singleton instance
_rate_limiter = AIRateLimiter()


def get_ai_rate_limiter() -> AIRateLimiter:
    """Get the singleton rate limiter instance."""
    return _rate_limiter
