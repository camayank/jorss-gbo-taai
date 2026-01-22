"""
Security Middleware for FastAPI.

Provides comprehensive security headers, CSRF protection, and request validation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Set

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.

    Headers:
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    """

    def __init__(
        self,
        app,
        hsts_max_age: int = 31536000,  # 1 year
        frame_options: str = "DENY",
        content_security_policy: Optional[str] = None,
    ):
        super().__init__(app)
        self.hsts_max_age = hsts_max_age
        self.frame_options = frame_options
        self.csp = content_security_policy or self._default_csp()

    def _default_csp(self) -> str:
        """Default Content-Security-Policy."""
        return "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://unpkg.com",  # Allow CDN scripts
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",  # Allow Google Fonts
            "img-src 'self' data: https:",
            "font-src 'self' https: https://fonts.gstatic.com",  # Allow Google Fonts
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add security headers
        response.headers["Strict-Transport-Security"] = f"max-age={self.hsts_max_age}; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = self.frame_options
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = self.csp
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Remove potentially dangerous headers
        if "Server" in response.headers:
            del response.headers["Server"]

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.

    Limits requests per IP address within a time window.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        exempt_paths: Optional[Set[str]] = None,
        disable_in_testing: bool = True,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.exempt_paths = exempt_paths or {"/health", "/metrics"}
        self.disable_in_testing = disable_in_testing

        # Token bucket state per IP
        self._buckets: Dict[str, Dict] = defaultdict(
            lambda: {"tokens": burst_size, "last_update": time.time()}
        )

    def _is_test_environment(self, request: Request) -> bool:
        """Check if running in test environment."""
        # Check environment variable
        if os.environ.get("TESTING", "").lower() in ("true", "1", "yes"):
            return True
        # Check for pytest
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return True
        # Check for testclient (FastAPI/Starlette test client)
        client_ip = self._get_client_ip(request)
        if client_ip == "testclient":
            return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting in test environment
        if self.disable_in_testing and self._is_test_environment(request):
            return await call_next(request)

        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit using token bucket
        if not self._check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, accounting for proxies."""
        # Check X-Forwarded-For header (from reverse proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client
        return request.client.host if request.client else "unknown"

    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if request is within rate limit using token bucket."""
        now = time.time()
        bucket = self._buckets[client_ip]

        # Refill tokens based on time passed
        time_passed = now - bucket["last_update"]
        tokens_to_add = time_passed * (self.requests_per_minute / 60)
        bucket["tokens"] = min(self.burst_size, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = now

        # Check if we have tokens available
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True

        return False


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware.

    Validates CSRF tokens for state-changing requests.
    """

    def __init__(
        self,
        app,
        secret_key: str,
        token_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        safe_methods: Set[str] = None,
        exempt_paths: Set[str] = None,
    ):
        super().__init__(app)
        self.secret_key = secret_key.encode("utf-8")
        self.token_name = token_name
        self.header_name = header_name
        self.safe_methods = safe_methods or {"GET", "HEAD", "OPTIONS", "TRACE"}
        self.exempt_paths = exempt_paths or {"/api/health", "/api/webhook"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip CSRF for safe methods
        if request.method in self.safe_methods:
            return await call_next(request)

        # Skip exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Skip API endpoints that use Bearer auth
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)

        # Validate CSRF token
        session_token = request.cookies.get(self.token_name)
        request_token = (
            request.headers.get(self.header_name) or
            (await self._get_form_token(request))
        )

        if not session_token or not request_token:
            logger.warning(f"CSRF token missing for {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing"},
            )

        if not self._verify_token(session_token, request_token):
            logger.warning(f"CSRF token invalid for {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token invalid"},
            )

        return await call_next(request)

    async def _get_form_token(self, request: Request) -> Optional[str]:
        """Extract CSRF token from form data."""
        try:
            if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
                form = await request.form()
                return form.get(self.token_name)
        except Exception:
            pass
        return None

    def _verify_token(self, session_token: str, request_token: str) -> bool:
        """Verify CSRF token."""
        return hmac.compare_digest(session_token, request_token)

    def generate_token(self) -> str:
        """Generate a new CSRF token."""
        token = secrets.token_hex(32)
        signature = hmac.new(self.secret_key, token.encode(), hashlib.sha256).hexdigest()
        return f"{token}:{signature}"


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Request validation middleware.

    Validates request size, content type, and sanitizes inputs.
    """

    def __init__(
        self,
        app,
        max_content_length: int = 10 * 1024 * 1024,  # 10MB
        allowed_content_types: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.max_content_length = max_content_length
        self.allowed_content_types = allowed_content_types or {
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_content_length:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )

        # Check content type for POST/PUT/PATCH
        if request.method in {"POST", "PUT", "PATCH"}:
            content_type = request.headers.get("content-type", "").split(";")[0].strip()
            if content_type and content_type not in self.allowed_content_types:
                return JSONResponse(
                    status_code=415,
                    content={"detail": f"Unsupported content type: {content_type}"},
                )

        return await call_next(request)


def configure_security_middleware(
    app: FastAPI,
    secret_key: str,
    cors_origins: List[str] = None,
    enable_csrf: bool = True,
    enable_rate_limit: bool = True,
) -> None:
    """
    Configure all security middleware for a FastAPI application.

    Args:
        app: FastAPI application
        secret_key: Secret key for signing
        cors_origins: Allowed CORS origins
        enable_csrf: Enable CSRF protection
        enable_rate_limit: Enable rate limiting
    """
    # CORS middleware (must be added first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:3000", "http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Request validation
    app.add_middleware(RequestValidationMiddleware)

    # Rate limiting
    if enable_rate_limit:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=60,
            burst_size=20,
        )

    # CSRF protection
    if enable_csrf:
        app.add_middleware(
            CSRFMiddleware,
            secret_key=secret_key,
            exempt_paths={"/api/health", "/api/webhook", "/api/chat"},
        )

    logger.info("Security middleware configured")
