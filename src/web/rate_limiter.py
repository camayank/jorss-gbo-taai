"""
Redis-based Tiered Rate Limiter  (MKW-70)

Provides distributed rate limiting using Redis sorted sets for sliding window.
Falls back to in-memory rate limiting when Redis is unavailable.

Features:
- Sliding window algorithm (more accurate than fixed window)
- Distributed state (works across multiple app instances)
- Automatic fallback to in-memory when Redis unavailable
- Tier-based per-user limits (Free / Premium / Enterprise)
- Per-endpoint overrides for expensive operations
- IP-level limiting for unauthenticated requests
- Proper 429 with Retry-After + X-RateLimit-* headers
- 80% quota warning via structured log + CloudWatch metric
- Health check endpoint exemptions

Tier limits (requests per minute):
  anonymous  :    20 / min  (IP-based — prevents account enumeration)
  free       :   100 / min
  basic      :   300 / min
  premium    : 1 000 / min
  professional: 5 000 / min
  cpa_firm   :10 000 / min  (Enterprise)

Per-endpoint overrides (applied additionally to tier limits):
  /api/advisor/chat, /api/ai-chat  →  10 / min  (LLM calls are expensive)
  /api/upload, /api/filing         →   5 / min  (large files)
  /api/scenarios, /api/sessions    →  60 / min  (calculation-heavy)
"""

import os
import time
import logging
from typing import Dict, Optional, Set, Callable, Union
from collections import defaultdict

import boto3
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier rate limits
# ---------------------------------------------------------------------------

# Per-minute limits per subscription tier
TIER_LIMITS: Dict[str, int] = {
    "anonymous":    20,
    "free":        100,
    "basic":       300,
    "premium":    1_000,
    "professional": 5_000,
    "cpa_firm":  10_000,
}

# Hourly limits (roughly 40× the per-minute limit to allow some burst)
TIER_HOURLY_LIMITS: Dict[str, int] = {
    "anonymous":     300,
    "free":        2_000,
    "basic":       6_000,
    "premium":    20_000,
    "professional": 100_000,
    "cpa_firm":   200_000,
}

# ---------------------------------------------------------------------------
# Per-endpoint overrides  (limit = min(tier_limit, endpoint_limit))
# ---------------------------------------------------------------------------
# Map path *prefix* → requests-per-minute override.
# The effective limit is the LOWER of the tier limit and the endpoint limit.
ENDPOINT_OVERRIDES: Dict[str, int] = {
    "/api/advisor/chat":  10,   # LLM calls
    "/api/ai-chat":       10,   # legacy AI chat path
    "/api/chat":          10,   # direct chat endpoint
    "/api/upload":         5,   # document upload
    "/api/filing":         5,   # e-file submission
    "/api/scenarios":     60,   # calculation-heavy
    "/api/sessions":      60,   # session calculations
}

# Paths that are never rate-limited
_EXEMPT_PATHS: Set[str] = {
    "/health",
    "/healthz",
    "/ready",
    "/api/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
    "/assets",
}

# CloudWatch namespace for quota metrics (optional, skipped if boto3 unavailable)
_CW_NAMESPACE = "TaxAdvisor/RateLimit"


# ---------------------------------------------------------------------------
# Redis sliding-window limiter
# ---------------------------------------------------------------------------

class RedisRateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets.

    Each request is stored as a member of a sorted set with the timestamp
    as score.  To check the rate we count members within the sliding window.

    Operations:
    - O(log N) add / O(log N) count
    - Auto-expire old entries via ZREMRANGEBYSCORE
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
        return f"{self.key_prefix}{window_name}:{identifier}"

    def is_allowed(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        window_name: str = "default",
    ) -> tuple[bool, int, int]:
        """
        Check if a request is allowed under the rate limit.

        Returns:
            (is_allowed, remaining_requests, retry_after_seconds)
        """
        limit = limit or self.default_limit
        window_seconds = window_seconds or self.default_window_seconds

        key = self._get_key(identifier, window_name)
        now = time.time()
        window_start = now - window_seconds

        try:
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            request_id = f"{now}:{id(self)}"
            pipe.zadd(key, {request_id: now})
            pipe.expire(key, window_seconds + 10)
            results = pipe.execute()
            current_count = results[1]

            if current_count >= limit:
                self.redis.zrem(key, request_id)
                oldest = self.redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry_after = int(oldest[0][1] + window_seconds - now) + 1
                else:
                    retry_after = window_seconds
                return False, 0, retry_after

            remaining = limit - current_count - 1
            return True, remaining, 0

        except Exception as e:
            logger.warning(f"Redis rate limit error: {e}, falling back to allow")
            return True, max(0, limit - 1), 60

    def get_current_count(
        self,
        identifier: str,
        window_seconds: Optional[int] = None,
        window_name: str = "default",
    ) -> int:
        window_seconds = window_seconds or self.default_window_seconds
        key = self._get_key(identifier, window_name)
        now = time.time()
        window_start = now - window_seconds
        try:
            self.redis.zremrangebyscore(key, 0, window_start)
            return self.redis.zcard(key)
        except Exception as e:
            logger.warning(f"Redis count error: {e}")
            return 0

    def reset(self, identifier: str, window_name: str = "default") -> bool:
        key = self._get_key(identifier, window_name)
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis reset error: {e}")
            return False


# ---------------------------------------------------------------------------
# In-memory fallback
# ---------------------------------------------------------------------------

class InMemoryRateLimiter:
    """
    In-memory sliding-window fallback — single-instance only.
    Used when Redis is unavailable.
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
        now = time.time()
        if now - self.last_cleanup > 300:
            cutoff = now - 3600
            for key in list(self.buckets.keys()):
                self.buckets[key] = [t for t in self.buckets[key] if t > cutoff]
                if not self.buckets[key]:
                    del self.buckets[key]
            self.last_cleanup = now

    def is_allowed(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        window_name: str = "default",
    ) -> tuple[bool, int, int]:
        self._cleanup_if_needed()
        limit = limit or self.default_limit
        window_seconds = window_seconds or self.default_window_seconds

        key = f"{window_name}:{identifier}"
        now = time.time()
        window_start = now - window_seconds
        self.buckets[key] = [t for t in self.buckets[key] if t > window_start]
        current_count = len(self.buckets[key])

        if current_count >= limit:
            if self.buckets[key]:
                oldest = min(self.buckets[key])
                retry_after = int(oldest + window_seconds - now) + 1
            else:
                retry_after = window_seconds
            return False, 0, retry_after

        self.buckets[key].append(now)
        remaining = limit - current_count - 1
        return True, remaining, 0


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for tiered rate limiting with Redis backend.

    Supports:
    - Per-user tier-based limits (anonymous → cpa_firm)
    - Per-endpoint overrides for expensive operations
    - IP-level limits for unauthenticated traffic
    - Proper 429 with Retry-After + X-RateLimit-* headers
    - 80% quota warning via structured log
    - In-memory fallback when Redis is unavailable
    """

    def __init__(
        self,
        app,
        # Legacy flat limits kept for backward compatibility with setup_middleware()
        requests_per_minute: int = 100,
        requests_per_hour: int = 2_000,
        exempt_paths: Optional[Set[str]] = None,
        get_identifier: Optional[Callable[[Request], str]] = None,
        enable_cloudwatch: bool = False,
    ):
        super().__init__(app)
        self.default_rpm = requests_per_minute
        self.default_rph = requests_per_hour
        self.exempt_paths = exempt_paths or _EXEMPT_PATHS
        self.get_identifier = get_identifier or self._default_get_identifier
        self.enable_cloudwatch = enable_cloudwatch
        self._cw_client = None

        self.redis_limiter: Optional[RedisRateLimiter] = None
        self.memory_limiter = InMemoryRateLimiter(
            default_limit=requests_per_minute,
            default_window_seconds=60,
        )
        self._init_redis()

        if enable_cloudwatch:
            self._init_cloudwatch()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_redis(self):
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
            client.ping()
            self.redis_limiter = RedisRateLimiter(redis_client=client)
            logger.info("Redis rate limiter initialized successfully")
        except ImportError:
            logger.info("Redis not installed, using in-memory rate limiter")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), using in-memory rate limiter")

    def _init_cloudwatch(self):
        try:
            self._cw_client = boto3.client(
                "cloudwatch",
                region_name=os.environ.get("AWS_REGION", "us-east-1"),
            )
            logger.info("CloudWatch rate-limit metrics enabled")
        except Exception as e:
            logger.warning(f"CloudWatch unavailable for rate-limit metrics: {e}")
            self._cw_client = None

    # ------------------------------------------------------------------
    # Identifier + tier resolution
    # ------------------------------------------------------------------

    _TRUSTED_PROXIES = set(
        os.environ.get("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
    )

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP, respecting trusted proxy headers."""
        peer_ip = request.client.host if request.client else "unknown"
        if peer_ip in self._TRUSTED_PROXIES:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip
        return peer_ip

    def _get_user_info(self, request: Request) -> Optional[dict]:
        """
        Lightweight JWT decode to extract user_id + subscription_tier.
        Avoids DB round-trips on every request.
        Returns None for anonymous traffic.
        """
        try:
            from security.auth_decorators import get_user_from_request
            return get_user_from_request(request)
        except Exception:
            return None

    def _default_get_identifier(self, request: Request) -> str:
        """Return user_id for authenticated users, IP for anonymous."""
        user = self._get_user_info(request)
        if user and user.get("id"):
            return f"user:{user['id']}"
        return f"ip:{self._get_client_ip(request)}"

    def _get_tier(self, request: Request) -> str:
        """
        Resolve subscription tier from the request.

        Order: request.state (cached by upstream auth middleware) →
               JWT claims → anonymous.
        """
        # Check if upstream middleware already resolved it
        cached = getattr(request.state, "subscription_tier", None)
        if cached:
            return cached.lower()

        user = self._get_user_info(request)
        if not user:
            return "anonymous"

        tier = (
            user.get("subscription_tier")
            or user.get("tier")
            or user.get("plan")
            or "free"
        )
        return tier.lower()

    def _get_tier_limits(self, tier: str) -> tuple[int, int]:
        """Return (per_minute, per_hour) for the given tier."""
        rpm = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        rph = TIER_HOURLY_LIMITS.get(tier, TIER_HOURLY_LIMITS["free"])
        return rpm, rph

    def _get_endpoint_override(self, path: str) -> Optional[int]:
        """Return per-minute override for this endpoint, or None."""
        for prefix, limit in ENDPOINT_OVERRIDES.items():
            if path.startswith(prefix):
                return limit
        return None

    # ------------------------------------------------------------------
    # Quota alerting
    # ------------------------------------------------------------------

    def _maybe_alert_quota(
        self,
        identifier: str,
        tier: str,
        remaining: int,
        limit: int,
        window: str,
    ):
        """Fire warning log + optional CloudWatch metric at 80% usage."""
        if limit <= 0:
            return
        used = limit - remaining
        pct = used / limit
        if pct < 0.8:
            return

        logger.warning(
            "Rate limit quota warning",
            extra={
                "event": "rate_limit_quota_warning",
                "identifier": identifier,
                "tier": tier,
                "window": window,
                "used": used,
                "limit": limit,
                "pct_used": round(pct * 100, 1),
            },
        )

        if self._cw_client:
            try:
                self._cw_client.put_metric_data(
                    Namespace=_CW_NAMESPACE,
                    MetricData=[
                        {
                            "MetricName": "QuotaWarning",
                            "Dimensions": [
                                {"Name": "Tier", "Value": tier},
                                {"Name": "Window", "Value": window},
                            ],
                            "Value": round(pct * 100, 2),
                            "Unit": "Percent",
                        }
                    ],
                )
            except Exception as e:
                logger.debug(f"CloudWatch put_metric_data failed: {e}")

    # ------------------------------------------------------------------
    # Exempt check
    # ------------------------------------------------------------------

    def _is_exempt(self, path: str) -> bool:
        for exempt in self.exempt_paths:
            if path.startswith(exempt):
                return True
        return False

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next):
        if self._is_exempt(request.url.path):
            return await call_next(request)

        identifier = self.get_identifier(request)
        tier = self._get_tier(request)
        tier_rpm, tier_rph = self._get_tier_limits(tier)

        # Per-endpoint override: effective limit = min(tier_rpm, override)
        endpoint_override = self._get_endpoint_override(request.url.path)
        effective_rpm = (
            min(tier_rpm, endpoint_override)
            if endpoint_override is not None
            else tier_rpm
        )

        limiter = self.redis_limiter or self.memory_limiter

        # --- Check per-minute limit ---
        allowed, remaining_min, retry_after = limiter.is_allowed(
            identifier=identifier,
            limit=effective_rpm,
            window_seconds=60,
            window_name="minute",
        )

        if not allowed:
            logger.warning(
                "Rate limit exceeded (minute)",
                extra={
                    "event": "rate_limit_exceeded",
                    "identifier": identifier,
                    "tier": tier,
                    "path": request.url.path,
                    "window": "minute",
                    "limit": effective_rpm,
                },
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error_type": "RateLimitExceeded",
                    "user_message": "Too many requests. Please slow down and try again.",
                    "retry_after": retry_after,
                    "tier": tier,
                    "window": "minute",
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(effective_rpm),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                    "X-RateLimit-Policy": f"{effective_rpm};w=60",
                },
            )

        # --- Check hourly limit ---
        allowed_hour, remaining_hour, retry_after_hour = limiter.is_allowed(
            identifier=identifier,
            limit=tier_rph,
            window_seconds=3600,
            window_name="hour",
        )

        if not allowed_hour:
            logger.warning(
                "Rate limit exceeded (hour)",
                extra={
                    "event": "rate_limit_exceeded",
                    "identifier": identifier,
                    "tier": tier,
                    "path": request.url.path,
                    "window": "hour",
                    "limit": tier_rph,
                },
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error_type": "RateLimitExceeded",
                    "user_message": "Hourly request limit exceeded. Please try again later.",
                    "retry_after": retry_after_hour,
                    "tier": tier,
                    "window": "hour",
                },
                headers={
                    "Retry-After": str(retry_after_hour),
                    "X-RateLimit-Limit": str(tier_rph),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after_hour),
                    "X-RateLimit-Policy": f"{tier_rph};w=3600",
                },
            )

        # --- 80% quota warning ---
        self._maybe_alert_quota(identifier, tier, remaining_min, effective_rpm, "minute")
        self._maybe_alert_quota(identifier, tier, remaining_hour, tier_rph, "hour")

        # --- Process request ---
        response = await call_next(request)

        # Attach rate limit headers to successful response
        response.headers["X-RateLimit-Limit-Minute"] = str(effective_rpm)
        response.headers["X-RateLimit-Remaining-Minute"] = str(remaining_min)
        response.headers["X-RateLimit-Limit-Hour"] = str(tier_rph)
        response.headers["X-RateLimit-Remaining-Hour"] = str(remaining_hour)
        response.headers["X-RateLimit-Tier"] = tier

        return response


# ---------------------------------------------------------------------------
# Factory helper (used by legacy setup_middleware)
# ---------------------------------------------------------------------------

def create_rate_limiter() -> Union[RedisRateLimiter, InMemoryRateLimiter]:
    """Return a Redis rate-limiter instance, or in-memory if Redis is down."""
    try:
        import redis

        client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            password=os.environ.get("REDIS_PASSWORD"),
            decode_responses=True,
            socket_timeout=1,
        )
        client.ping()
        return RedisRateLimiter(redis_client=client)
    except Exception:
        return InMemoryRateLimiter()
