"""
Rate Limiting Utility for API Endpoints.

Provides rate limiting for expensive operations like PDF generation
to prevent abuse and ensure system stability.
"""

import time
import logging
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from functools import wraps
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    # Maximum requests per window
    max_requests: int = 10

    # Time window in seconds
    window_seconds: int = 60

    # Cooldown period after limit exceeded (seconds)
    cooldown_seconds: int = 30

    # Whether to apply per-session or global limits
    per_session: bool = True


@dataclass
class RateLimitState:
    """State tracking for rate limiting."""
    requests: list = field(default_factory=list)
    cooldown_until: float = 0


class RateLimiter:
    """
    Rate limiter for API endpoints.

    Usage:
        limiter = RateLimiter(RateLimitConfig(max_requests=5, window_seconds=60))

        # Check if request is allowed
        if limiter.is_allowed(session_id):
            # Process request
            limiter.record_request(session_id)
        else:
            # Return rate limit error
            raise RateLimitExceeded()

        # Or use as decorator
        @limiter.limit
        async def generate_pdf(session_id: str):
            ...
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter with configuration."""
        self.config = config or RateLimitConfig()
        self._states: Dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._global_state = RateLimitState()
        self._lock = Lock()

        logger.info(
            f"Rate limiter initialized: {self.config.max_requests} requests "
            f"per {self.config.window_seconds}s window"
        )

    def _get_state(self, identifier: str) -> RateLimitState:
        """Get state for identifier (session or global)."""
        if self.config.per_session:
            return self._states[identifier]
        return self._global_state

    def _cleanup_old_requests(self, state: RateLimitState) -> None:
        """Remove requests outside the current window."""
        current_time = time.time()
        cutoff = current_time - self.config.window_seconds
        state.requests = [t for t in state.requests if t > cutoff]

    def is_allowed(self, identifier: str = "global") -> bool:
        """
        Check if a request is allowed under rate limits.

        Args:
            identifier: Session ID or other identifier for per-session limits

        Returns:
            True if request is allowed, False if rate limited
        """
        with self._lock:
            current_time = time.time()
            state = self._get_state(identifier)

            # Check if in cooldown period
            if current_time < state.cooldown_until:
                remaining = state.cooldown_until - current_time
                logger.warning(
                    f"Rate limit cooldown active for {identifier}: "
                    f"{remaining:.1f}s remaining"
                )
                return False

            # Cleanup old requests
            self._cleanup_old_requests(state)

            # Check if under limit
            if len(state.requests) < self.config.max_requests:
                return True

            # Limit exceeded - start cooldown
            state.cooldown_until = current_time + self.config.cooldown_seconds
            logger.warning(
                f"Rate limit exceeded for {identifier}: "
                f"{len(state.requests)} requests in {self.config.window_seconds}s"
            )
            return False

    def record_request(self, identifier: str = "global") -> None:
        """
        Record a request for rate limiting.

        Args:
            identifier: Session ID or other identifier
        """
        with self._lock:
            state = self._get_state(identifier)
            state.requests.append(time.time())

    def get_remaining(self, identifier: str = "global") -> int:
        """
        Get remaining requests in current window.

        Args:
            identifier: Session ID or other identifier

        Returns:
            Number of remaining requests allowed
        """
        with self._lock:
            state = self._get_state(identifier)
            self._cleanup_old_requests(state)
            return max(0, self.config.max_requests - len(state.requests))

    def get_reset_time(self, identifier: str = "global") -> float:
        """
        Get seconds until rate limit resets.

        Args:
            identifier: Session ID or other identifier

        Returns:
            Seconds until oldest request expires from window
        """
        with self._lock:
            state = self._get_state(identifier)
            self._cleanup_old_requests(state)

            if not state.requests:
                return 0

            oldest = min(state.requests)
            reset_at = oldest + self.config.window_seconds
            return max(0, reset_at - time.time())

    def reset(self, identifier: str = "global") -> None:
        """
        Reset rate limit state for identifier.

        Args:
            identifier: Session ID or other identifier
        """
        with self._lock:
            if self.config.per_session:
                if identifier in self._states:
                    del self._states[identifier]
            else:
                self._global_state = RateLimitState()

    def limit(self, func: Callable) -> Callable:
        """
        Decorator to apply rate limiting to a function.

        The decorated function must have 'session_id' as first argument
        or accept **kwargs with 'session_id'.

        Usage:
            @limiter.limit
            async def generate_pdf(session_id: str):
                ...
        """
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract session_id from args or kwargs
            session_id = kwargs.get('session_id') or (args[0] if args else 'global')

            if not self.is_allowed(session_id):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": "Too many PDF generation requests. Please wait before trying again.",
                        "retry_after": self.config.cooldown_seconds,
                        "remaining": self.get_remaining(session_id),
                    }
                )

            self.record_request(session_id)
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            session_id = kwargs.get('session_id') or (args[0] if args else 'global')

            if not self.is_allowed(session_id):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": "Too many PDF generation requests. Please wait before trying again.",
                        "retry_after": self.config.cooldown_seconds,
                        "remaining": self.get_remaining(session_id),
                    }
                )

            self.record_request(session_id)
            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper


# =============================================================================
# PRE-CONFIGURED RATE LIMITERS
# =============================================================================

# PDF generation: 5 PDFs per minute per session
pdf_rate_limiter = RateLimiter(RateLimitConfig(
    max_requests=5,
    window_seconds=60,
    cooldown_seconds=30,
    per_session=True,
))

# Report generation: 20 reports per minute per session
report_rate_limiter = RateLimiter(RateLimitConfig(
    max_requests=20,
    window_seconds=60,
    cooldown_seconds=10,
    per_session=True,
))

# Global PDF limit: 100 PDFs per minute across all users
global_pdf_limiter = RateLimiter(RateLimitConfig(
    max_requests=100,
    window_seconds=60,
    cooldown_seconds=60,
    per_session=False,
))


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 30,
        remaining: int = 0
    ):
        self.message = message
        self.retry_after = retry_after
        self.remaining = remaining
        super().__init__(self.message)
