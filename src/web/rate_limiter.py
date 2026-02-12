"""
Redis-based Rate Limiter

Provides distributed rate limiting using Redis sorted sets for sliding window.
Falls back to in-memory rate limiting when Redis is unavailable.

Features:
- Sliding window algorithm (more accurate than fixed window)
- Distributed state (works across multiple app instances)
- Automatic fallback to in-memory when Redis unavailable
- Configurable limits and windows
- Health check endpoint exemptions

Usage:
    from web.rate_limiter import RedisRateLimitMiddleware

    app.add_middleware(
        RedisRateLimitMiddleware,
        requests_per_minute=60,
        requests_per_hour=1000,
        exempt_paths={"/health", "/metrics"},
    )
"""

import os
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Set, Callable, Union
from collections import defaultdict

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets.

    Each request is stored as a member of a sorted set with the timestamp as score.
    To check the rate, we count members within the sliding window.

    This approach:
    - Provides accurate sliding window (no burst at window boundaries)
    - Uses O(log N) operations for add/count
    - Automatically expires old entries via ZREMRANGEBYSCORE
    """

    def __init__(
        self,
        redis_client,
        key_prefix: str = "rate_limit:",
        default_limit: int = 60,
        default_window_seconds: int = 60,
    ):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.default_limit = default_limit
        self.default_window_seconds = default_window_seconds

    def _get_key(self, identifier: str, window_name: str) -> str:
        """Generate Redis key for rate limit bucket."""
        return f"{self.key_prefix}{window_name}:{identifier}"

    def is_allowed(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        window_name: str = "default",
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.

        Args:
            identifier: Client identifier (e.g., IP address)
            limit: Max requests allowed in window
            window_seconds: Window size in seconds
            window_name: Name for this limit (for multiple limit tiers)

        Returns:
            Tuple of (is_allowed, remaining_requests, retry_after_seconds)
        """
        limit = limit or self.default_limit
        window_seconds = window_seconds or self.default_window_seconds

        key = self._get_key(identifier, window_name)
        now = time.time()
        window_start = now - window_seconds

        try:
            pipe = self.redis.pipeline()

            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current entries
            pipe.zcard(key)

            # Add current request (we'll remove if over limit)
            request_id = f"{now}:{id(self)}"
            pipe.zadd(key, {request_id: now})

            # Set expiry on key
            pipe.expire(key, window_seconds + 10)

            results = pipe.execute()
            current_count = results[1]  # zcard result

            if current_count >= limit:
                # Over limit - remove the request we just added
                self.redis.zrem(key, request_id)

                # Calculate retry-after (when oldest entry expires)
                oldest = self.redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry_after = int(oldest[0][1] + window_seconds - now) + 1
                else:
                    retry_after = window_seconds

                return False, 0, retry_after

            remaining = limit - current_count - 1
            return True, remaining, 0

        except Exception as e:
            logger.warning(f"Redis rate limit error: {e}")
            # On Redis error, allow request (fail open)
            return True, limit - 1, 0

    def get_current_count(
        self,
        identifier: str,
        window_seconds: Optional[int] = None,
        window_name: str = "default",
    ) -> int:
        """Get current request count for identifier."""
        window_seconds = window_seconds or self.default_window_seconds
        key = self._get_key(identifier, window_name)
        now = time.time()
        window_start = now - window_seconds

        try:
            # Clean and count in one operation
            self.redis.zremrangebyscore(key, 0, window_start)
            return self.redis.zcard(key)
        except Exception as e:
            logger.warning(f"Redis count error: {e}")
            return 0

    def reset(self, identifier: str, window_name: str = "default") -> bool:
        """Reset rate limit for an identifier."""
        key = self._get_key(identifier, window_name)
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis reset error: {e}")
            return False


class InMemoryRateLimiter:
    """
    In-memory fallback rate limiter.

    Uses the same sliding window algorithm but stores data in memory.
    Not suitable for distributed deployments but works for single-instance.
    """

    def __init__(
        self,
        default_limit: int = 60,
        default_window_seconds: int = 60,
    ):
        self.default_limit = default_limit
        self.default_window_seconds = default_window_seconds
        self.buckets: Dict[str, list] = defaultdict(list)
        self.last_cleanup = time.time()

    def _cleanup_if_needed(self):
        """Periodically clean up old entries."""
        now = time.time()
        if now - self.last_cleanup > 300:  # Every 5 minutes
            self._cleanup_all()
            self.last_cleanup = now

    def _cleanup_all(self):
        """Remove all expired entries."""
        now = time.time()
        cutoff = now - 3600  # Keep last hour

        for key in list(self.buckets.keys()):
            self.buckets[key] = [t for t in self.buckets[key] if t > cutoff]
            if not self.buckets[key]:
                del self.buckets[key]

    def is_allowed(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        window_name: str = "default",
    ) -> tuple[bool, int, int]:
        """Check if request is allowed under rate limit."""
        self._cleanup_if_needed()

        limit = limit or self.default_limit
        window_seconds = window_seconds or self.default_window_seconds

        key = f"{window_name}:{identifier}"
        now = time.time()
        window_start = now - window_seconds

        # Remove expired entries for this key
        self.buckets[key] = [t for t in self.buckets[key] if t > window_start]

        current_count = len(self.buckets[key])

        if current_count >= limit:
            # Calculate retry-after
            if self.buckets[key]:
                oldest = min(self.buckets[key])
                retry_after = int(oldest + window_seconds - now) + 1
            else:
                retry_after = window_seconds

            return False, 0, retry_after

        # Record this request
        self.buckets[key].append(now)

        remaining = limit - current_count - 1
        return True, remaining, 0


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting with Redis backend.

    Automatically falls back to in-memory rate limiting when Redis
    is unavailable, ensuring the application remains functional.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        exempt_paths: Optional[Set[str]] = None,
        get_identifier: Optional[Callable[[Request], str]] = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.exempt_paths = exempt_paths or {"/health", "/api/health", "/metrics"}
        self.get_identifier = get_identifier or self._default_get_identifier

        # Try to initialize Redis limiter
        self.redis_limiter = None
        self.memory_limiter = InMemoryRateLimiter(
            default_limit=requests_per_minute,
            default_window_seconds=60,
        )

        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection if available."""
        try:
            import redis

            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", 6379))
            redis_password = os.environ.get("REDIS_PASSWORD")
            redis_db = int(os.environ.get("REDIS_RATE_LIMIT_DB", 0))

            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=redis_db,
                decode_responses=True,
                socket_timeout=1,
                socket_connect_timeout=1,
            )

            # Test connection
            client.ping()

            self.redis_limiter = RedisRateLimiter(
                redis_client=client,
                default_limit=self.requests_per_minute,
                default_window_seconds=60,
            )
            logger.info("Redis rate limiter initialized successfully")

        except ImportError:
            logger.info("Redis not installed, using in-memory rate limiter")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), using in-memory rate limiter")

    def _default_get_identifier(self, request: Request) -> str:
        """Get client identifier from request."""
        # Check for forwarded headers (behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting."""
        for exempt in self.exempt_paths:
            if path.startswith(exempt):
                return True
        return False

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""

        # Skip rate limiting for exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)

        identifier = self.get_identifier(request)

        # Use Redis if available, otherwise fallback to memory
        limiter = self.redis_limiter or self.memory_limiter

        # Check minute limit
        allowed, remaining_minute, retry_after = limiter.is_allowed(
            identifier=identifier,
            limit=self.requests_per_minute,
            window_seconds=60,
            window_name="minute",
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error_type": "RateLimitExceeded",
                    "user_message": "Too many requests. Please slow down and try again.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                },
            )

        # Check hour limit
        allowed_hour, remaining_hour, retry_after_hour = limiter.is_allowed(
            identifier=identifier,
            limit=self.requests_per_hour,
            window_seconds=3600,
            window_name="hour",
        )

        if not allowed_hour:
            return JSONResponse(
                status_code=429,
                content={
                    "error_type": "RateLimitExceeded",
                    "user_message": "Hourly request limit exceeded. Please try again later.",
                    "retry_after": retry_after_hour,
                },
                headers={
                    "Retry-After": str(retry_after_hour),
                    "X-RateLimit-Limit": str(self.requests_per_hour),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after_hour),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(remaining_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(remaining_hour)

        return response


# Convenience function for standalone rate limit checks
def create_rate_limiter() -> Union[RedisRateLimiter, InMemoryRateLimiter]:
    """
    Create a rate limiter instance.

    Returns Redis limiter if available, otherwise in-memory limiter.
    """
    try:
        import redis

        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        redis_password = os.environ.get("REDIS_PASSWORD")

        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True,
            socket_timeout=1,
        )
        client.ping()

        return RedisRateLimiter(redis_client=client)

    except Exception:
        return InMemoryRateLimiter()
