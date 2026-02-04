"""
Middleware for FastAPI application

Provides:
- Rate limiting
- Request timeout protection
- Request ID injection
- Error tracking
- Performance monitoring
"""

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta
from typing import Dict, Optional
import time
import logging
import asyncio

logger = logging.getLogger(__name__)


# =============================================================================
# Rate Limiting Middleware
# =============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory rate limiting middleware (FALLBACK).

    NOTE: This is the fallback rate limiter for when Redis is unavailable.
    For production deployments, use RedisRateLimitMiddleware from web.rate_limiter
    which provides distributed rate limiting across multiple app instances.

    Features:
    - Per-IP rate limiting
    - Per-endpoint rate limiting
    - Configurable limits and windows
    - Automatic cleanup of old records

    Limitations:
    - In-memory only (not shared across instances)
    - State lost on restart
    """

    def __init__(self, app, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # In-memory storage (use Redis in production)
        self.minute_buckets: Dict[str, list] = {}
        self.hour_buckets: Dict[str, list] = {}

        # Last cleanup time
        self.last_cleanup = datetime.now()

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""

        # Skip rate limiting for health checks
        if request.url.path in ["/api/health", "/health", "/api/health/ready"]:
            return await call_next(request)

        # Get client identifier (IP address)
        client_ip = request.client.host if request.client else "unknown"
        now = datetime.now()

        # Cleanup old records every 5 minutes
        if (now - self.last_cleanup).total_seconds() > 300:
            self._cleanup_old_records()
            self.last_cleanup = now

        # Check rate limits
        try:
            self._check_rate_limit(client_ip, now)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error_type": "RateLimitExceeded",
                    "user_message": "Too many requests. Please slow down and try again in a minute.",
                    "retry_after": 60
                }
            )

        # Record request
        self._record_request(client_ip, now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            self._get_remaining_requests(client_ip, "minute")
        )

        return response

    def _check_rate_limit(self, client_ip: str, now: datetime):
        """Check if request exceeds rate limits."""

        # Check minute bucket
        minute_key = f"{client_ip}:minute"
        if minute_key in self.minute_buckets:
            recent_requests = [
                ts for ts in self.minute_buckets[minute_key]
                if (now - ts).total_seconds() < 60
            ]

            if len(recent_requests) >= self.requests_per_minute:
                logger.warning(f"Rate limit exceeded (minute): {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests per minute"
                )

        # Check hour bucket
        hour_key = f"{client_ip}:hour"
        if hour_key in self.hour_buckets:
            recent_requests = [
                ts for ts in self.hour_buckets[hour_key]
                if (now - ts).total_seconds() < 3600
            ]

            if len(recent_requests) >= self.requests_per_hour:
                logger.warning(f"Rate limit exceeded (hour): {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests per hour"
                )

    def _record_request(self, client_ip: str, now: datetime):
        """Record request timestamp."""

        minute_key = f"{client_ip}:minute"
        hour_key = f"{client_ip}:hour"

        if minute_key not in self.minute_buckets:
            self.minute_buckets[minute_key] = []
        self.minute_buckets[minute_key].append(now)

        if hour_key not in self.hour_buckets:
            self.hour_buckets[hour_key] = []
        self.hour_buckets[hour_key].append(now)

    def _get_remaining_requests(self, client_ip: str, window: str) -> int:
        """Get remaining requests for client."""

        now = datetime.now()
        key = f"{client_ip}:{window}"
        limit = self.requests_per_minute if window == "minute" else self.requests_per_hour
        seconds = 60 if window == "minute" else 3600

        if key not in (self.minute_buckets if window == "minute" else self.hour_buckets):
            return limit

        bucket = self.minute_buckets if window == "minute" else self.hour_buckets
        recent_requests = [ts for ts in bucket[key] if (now - ts).total_seconds() < seconds]

        return max(0, limit - len(recent_requests))

    def _cleanup_old_records(self):
        """Remove old request records to prevent memory leaks."""

        now = datetime.now()

        # Clean minute buckets
        for key in list(self.minute_buckets.keys()):
            self.minute_buckets[key] = [
                ts for ts in self.minute_buckets[key]
                if (now - ts).total_seconds() < 120  # Keep last 2 minutes
            ]
            if not self.minute_buckets[key]:
                del self.minute_buckets[key]

        # Clean hour buckets
        for key in list(self.hour_buckets.keys()):
            self.hour_buckets[key] = [
                ts for ts in self.hour_buckets[key]
                if (now - ts).total_seconds() < 7200  # Keep last 2 hours
            ]
            if not self.hour_buckets[key]:
                del self.hour_buckets[key]

        logger.info(f"Rate limit cleanup complete: {len(self.minute_buckets)} minute buckets, {len(self.hour_buckets)} hour buckets")


# =============================================================================
# Request Timeout Middleware
# =============================================================================

class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Request timeout middleware to prevent long-running requests.

    Features:
    - Configurable timeout per endpoint
    - Automatic request cancellation
    - Timeout error responses
    """

    def __init__(self, app, default_timeout: int = 30):
        super().__init__(app)
        self.default_timeout = default_timeout

        # Custom timeouts for specific endpoints
        self.endpoint_timeouts = {
            "/api/ocr/process": 60,  # OCR can take longer
            "/api/tax-returns/express-lane": 45,  # Tax calculation
            "/api/scenarios/": 20,  # Quick calculations
        }

    async def dispatch(self, request: Request, call_next):
        """Process request with timeout."""

        # Determine timeout for this endpoint
        timeout = self._get_timeout(request.url.path)

        try:
            # Process request with timeout
            response = await asyncio.wait_for(
                call_next(request),
                timeout=timeout
            )
            return response

        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {request.url.path} (limit: {timeout}s)")
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={
                    "error_type": "RequestTimeout",
                    "user_message": f"Request took too long to process (>{timeout}s). Please try again or simplify your request.",
                    "timeout_seconds": timeout
                }
            )

    def _get_timeout(self, path: str) -> int:
        """Get timeout for specific endpoint."""

        # Check for exact match
        if path in self.endpoint_timeouts:
            return self.endpoint_timeouts[path]

        # Check for prefix match
        for endpoint_path, timeout in self.endpoint_timeouts.items():
            if path.startswith(endpoint_path):
                return timeout

        return self.default_timeout


# =============================================================================
# Request ID Middleware
# =============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Inject request ID into all requests for tracing.

    Features:
    - Unique request ID generation
    - Request ID in response headers
    - Request ID in logs
    """

    async def dispatch(self, request: Request, call_next):
        """Add request ID to request."""

        # Generate unique request ID
        request_id = f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # Add to request state
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


# =============================================================================
# Performance Monitoring Middleware
# =============================================================================

class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Monitor request performance.

    Features:
    - Response time tracking
    - Slow request logging
    - Performance metrics
    """

    def __init__(self, app, slow_request_threshold: float = 2.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold

    async def dispatch(self, request: Request, call_next):
        """Monitor request performance."""

        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time = time.time() - start_time

        # Add performance headers
        response.headers["X-Response-Time"] = f"{response_time:.3f}s"

        # Log slow requests
        if response_time > self.slow_request_threshold:
            logger.warning(f"Slow request: {request.method} {request.url.path} - {response_time:.3f}s", extra={
                "path": request.url.path,
                "method": request.method,
                "response_time": response_time,
                "status_code": response.status_code
            })

        # Log all requests
        logger.info(f"{request.method} {request.url.path} - {response.status_code} - {response_time:.3f}s", extra={
            "path": request.url.path,
            "method": request.method,
            "response_time": response_time,
            "status_code": response.status_code,
            "request_id": getattr(request.state, 'request_id', 'unknown')
        })

        return response


# =============================================================================
# Error Tracking Middleware
# =============================================================================

class ErrorTrackingMiddleware(BaseHTTPMiddleware):
    """
    Track and log errors for monitoring.

    Features:
    - Error categorization
    - Error rate tracking
    - Integration with error tracking services (Sentry, etc.)
    """

    def __init__(self, app):
        super().__init__(app)
        self.error_counts: Dict[str, int] = {}

    async def dispatch(self, request: Request, call_next):
        """Track errors."""

        try:
            response = await call_next(request)

            # Track error responses
            if response.status_code >= 400:
                self._record_error(request.url.path, response.status_code)

            return response

        except Exception as e:
            # Log unhandled exception
            logger.error(f"Unhandled exception: {request.method} {request.url.path}", exc_info=True, extra={
                "path": request.url.path,
                "method": request.method,
                "error": str(e),
                "request_id": getattr(request.state, 'request_id', 'unknown')
            })

            # Record error
            self._record_error(request.url.path, 500)

            # Return generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "error_type": "UnhandledError",
                    "user_message": "An unexpected error occurred. Our team has been notified.",
                    "request_id": getattr(request.state, 'request_id', 'unknown')
                }
            )

    def _record_error(self, path: str, status_code: int):
        """Record error for tracking."""

        key = f"{path}:{status_code}"
        self.error_counts[key] = self.error_counts.get(key, 0) + 1

        # Log if error count is high
        if self.error_counts[key] % 10 == 0:
            logger.warning(f"High error count for {path}: {status_code} - {self.error_counts[key]} errors")


# =============================================================================
# CORS Middleware (if needed)
# =============================================================================

from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app, origins: list = None):
    """
    Setup CORS middleware.

    Args:
        app: FastAPI application
        origins: List of allowed origins (default: localhost only)
    """

    if origins is None:
        origins = [
            "http://localhost",
            "http://localhost:8000",
            "http://localhost:3000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# =============================================================================
# Setup All Middleware
# =============================================================================

def setup_middleware(app, enable_rate_limiting: bool = True, enable_timeout: bool = True):
    """
    Setup all middleware for the application.

    Args:
        app: FastAPI application
        enable_rate_limiting: Enable rate limiting (default: True)
        enable_timeout: Enable request timeouts (default: True)
    """

    # Add middleware in reverse order (last added = first executed)

    # 1. Error tracking (outermost - catch all errors)
    app.add_middleware(ErrorTrackingMiddleware)

    # 2. Performance monitoring
    app.add_middleware(PerformanceMiddleware, slow_request_threshold=2.0)

    # 3. Request ID injection
    app.add_middleware(RequestIDMiddleware)

    # 4. Request timeout
    if enable_timeout:
        app.add_middleware(TimeoutMiddleware, default_timeout=30)

    # 5. Rate limiting (prefer Redis-backed for distributed deployments)
    if enable_rate_limiting:
        try:
            from web.rate_limiter import RedisRateLimitMiddleware
            app.add_middleware(
                RedisRateLimitMiddleware,
                requests_per_minute=60,
                requests_per_hour=1000,
                exempt_paths={"/health", "/api/health", "/metrics", "/static"},
            )
            logger.info("Redis rate limiter enabled (with in-memory fallback)")
        except ImportError:
            # Fallback to in-memory rate limiter
            app.add_middleware(
                RateLimitMiddleware,
                requests_per_minute=60,
                requests_per_hour=1000
            )
            logger.info("In-memory rate limiter enabled")

    logger.info("Middleware setup complete")
