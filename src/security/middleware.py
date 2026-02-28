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

# Trusted proxy IPs - only trust X-Forwarded-For from these sources
TRUSTED_PROXIES = set(
    ip.strip()
    for ip in os.environ.get("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
    if ip.strip()
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.

    Headers:
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Content-Security-Policy (with nonce support)
    - Referrer-Policy
    - Permissions-Policy

    SECURITY: Uses nonce-based CSP to eliminate 'unsafe-inline' for scripts.
    The nonce is generated per-request and stored in request.state.csp_nonce.
    Templates can access this via {{ request.state.csp_nonce }}.
    """

    def __init__(
        self,
        app,
        hsts_max_age: int = 31536000,  # 1 year
        frame_options: str = "DENY",
        content_security_policy: Optional[str] = None,
        use_nonce: bool = True,  # Enable nonce-based CSP by default
    ):
        super().__init__(app)
        self.hsts_max_age = hsts_max_age
        self.frame_options = frame_options
        self.use_nonce = use_nonce
        self._static_csp = content_security_policy  # User-provided static CSP

    def _generate_nonce(self) -> str:
        """Generate a cryptographically secure nonce for CSP."""
        return secrets.token_urlsafe(32)

    def _build_csp(self, nonce: Optional[str] = None) -> str:
        """
        Build Content-Security-Policy with optional nonce.

        HARDENED CSP includes:
        - Nonce-based script protection (when available)
        - object-src 'none' - prevents plugin exploitation (Flash, Java)
        - upgrade-insecure-requests - forces HTTPS for all subresources
        - worker-src 'self' - restricts service workers
        - manifest-src 'self' - restricts PWA manifests
        - Explicit frame-src 'none' - prevents iframe embedding of content

        Args:
            nonce: Per-request nonce for script/style-src

        Returns:
            CSP header value
        """
        if self._static_csp:
            # User provided static CSP - use as-is (might contain their own nonce)
            return self._static_csp

        # Build nonce-based CSP
        if nonce and self.use_nonce:
            # SECURITY: Use nonce instead of 'unsafe-inline' for scripts
            # This prevents XSS attacks from injecting arbitrary scripts
            script_src = f"script-src 'self' 'nonce-{nonce}' https://unpkg.com https://cdn.jsdelivr.net"
            # Note: We still need 'unsafe-inline' for styles due to Alpine.js/inline styles
            # This is a known limitation - inline styles are lower risk than inline scripts
            style_src = "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com"
        else:
            # Fallback for non-HTML responses or when nonce is disabled
            script_src = "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net"
            style_src = "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com"

        # Build hardened CSP directives
        directives = [
            "default-src 'self'",
            script_src,
            style_src,
            "img-src 'self' data: https:",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self'",
            # HARDENING: Prevent framing attacks
            "frame-ancestors 'none'",
            "frame-src 'none'",
            # HARDENING: Prevent plugin exploitation
            "object-src 'none'",
            # HARDENING: Restrict base URI to prevent base tag injection
            "base-uri 'self'",
            # HARDENING: Restrict form submission targets
            "form-action 'self'",
            # HARDENING: Restrict service workers and web workers
            "worker-src 'self'",
            # HARDENING: Restrict PWA manifest
            "manifest-src 'self'",
            # HARDENING: Force HTTPS for all subresources
            "upgrade-insecure-requests",
        ]

        return "; ".join(directives)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate nonce for this request
        nonce = self._generate_nonce() if self.use_nonce else None

        # Store nonce in request state for template access
        if nonce:
            request.state.csp_nonce = nonce

        response = await call_next(request)

        # Determine if this is an HTML response that needs nonce-based CSP
        content_type = response.headers.get("content-type", "")
        is_html = "text/html" in content_type

        # Build CSP with nonce for HTML responses
        csp = self._build_csp(nonce if is_html else None)

        # Add security headers
        response.headers["Strict-Transport-Security"] = f"max-age={self.hsts_max_age}; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = self.frame_options
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = csp
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Remove potentially dangerous headers
        if "Server" in response.headers:
            del response.headers["Server"]

        return response


class CSRFCookieMiddleware(BaseHTTPMiddleware):
    """
    Middleware to ensure CSRF token cookie is set on HTML responses.

    SECURITY: This middleware solves the CSRF token persistence problem by:
    1. Generating a CSRF token if no valid cookie exists
    2. Setting the token cookie on HTML responses
    3. Storing the token in request.state for template access
    4. Using the same token across requests (persistence)

    The cookie is:
    - httponly=False (must be readable by JavaScript for AJAX)
    - secure=True in production (HTTPS only)
    - samesite="lax" (prevents cross-site request attacks)
    - max_age=604800 (7 days - aligned with refresh token and CSRFMiddleware rotation)
    """

    def __init__(
        self,
        app,
        secret_key: bytes,
        cookie_name: str = "csrf_token",
        cookie_max_age: int = 604800,  # 7 days — aligned with CSRFMiddleware rotation
        secure: bool = True,
    ):
        super().__init__(app)
        self.secret_key = secret_key
        self.cookie_name = cookie_name
        self.cookie_max_age = cookie_max_age
        self.secure = secure

    def _generate_token(self) -> str:
        """Generate a signed CSRF token."""
        token_data = secrets.token_hex(32)
        signature = hmac.new(self.secret_key, token_data.encode(), hashlib.sha256).hexdigest()
        return f"{token_data}:{signature}"

    def _validate_token(self, token: str) -> bool:
        """Validate a CSRF token signature."""
        if not token or ":" not in token:
            return False
        try:
            token_data, signature = token.split(":", 1)
            expected_sig = hmac.new(self.secret_key, token_data.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(signature, expected_sig)
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"CSRF token validation error: {e}")
            return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check for existing valid CSRF token in cookie
        existing_token = request.cookies.get(self.cookie_name)
        token_valid = self._validate_token(existing_token) if existing_token else False

        # Use existing token if valid, otherwise generate new one
        csrf_token = existing_token if token_valid else self._generate_token()

        # Store token in request.state for template access
        request.state.csrf_token = csrf_token

        # Process the request
        response = await call_next(request)

        # Set CSRF cookie on HTML responses (or if cookie was missing/invalid)
        content_type = response.headers.get("content-type", "")
        is_html = "text/html" in content_type

        if is_html or not token_valid:
            # Set the CSRF token cookie
            response.set_cookie(
                key=self.cookie_name,
                value=csrf_token,
                httponly=False,  # Must be readable by JavaScript
                secure=self.secure,
                samesite="lax",
                max_age=self.cookie_max_age,
                path="/",  # Available for all paths
            )
            logger.debug(f"[CSRF] Set cookie on {'HTML' if is_html else 'non-HTML'} response")

        return response


class RateLimitBackend:
    """Abstract base class for rate limit storage backends."""

    def check_rate_limit(self, client_ip: str, requests_per_minute: int, burst_size: int) -> bool:
        """Check if request is within rate limit. Returns True if allowed."""
        raise NotImplementedError


class InMemoryRateLimitBackend(RateLimitBackend):
    """In-memory rate limit storage (for development/single-instance)."""

    def __init__(self):
        self._buckets: Dict[str, Dict] = defaultdict(
            lambda: {"tokens": 10, "last_update": time.time()}
        )

    def check_rate_limit(self, client_ip: str, requests_per_minute: int, burst_size: int) -> bool:
        """Check rate limit using token bucket algorithm."""
        now = time.time()
        bucket = self._buckets[client_ip]

        # Initialize bucket with correct burst_size if first request
        if "initialized" not in bucket:
            bucket["tokens"] = burst_size
            bucket["initialized"] = True

        # Refill tokens based on time passed
        time_passed = now - bucket["last_update"]
        tokens_to_add = time_passed * (requests_per_minute / 60)
        bucket["tokens"] = min(burst_size, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = now

        # Check if we have tokens available
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True

        return False


class RedisRateLimitBackend(RateLimitBackend):
    """
    Redis-based rate limit storage (for production/multi-instance).

    Uses Redis for persistent, shared rate limiting across multiple workers.
    Implements token bucket algorithm with Redis EVAL for atomicity.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._redis = None
        self._initialized = False

        # Lua script for atomic token bucket operation
        self._lua_script = """
            local key = KEYS[1]
            local requests_per_minute = tonumber(ARGV[1])
            local burst_size = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])

            -- Get current bucket state
            local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
            local tokens = tonumber(bucket[1]) or burst_size
            local last_update = tonumber(bucket[2]) or now

            -- Refill tokens based on time passed
            local time_passed = now - last_update
            local tokens_to_add = time_passed * (requests_per_minute / 60)
            tokens = math.min(burst_size, tokens + tokens_to_add)

            -- Check if we have tokens
            if tokens >= 1 then
                tokens = tokens - 1
                redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
                redis.call('EXPIRE', key, 300)  -- 5 minute TTL
                return 1  -- Allowed
            else
                redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
                redis.call('EXPIRE', key, 300)
                return 0  -- Rate limited
            end
        """
        self._script_sha = None

    def _get_redis(self):
        """Lazy initialization of Redis connection."""
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                # Test connection
                self._redis.ping()
                # Load Lua script
                self._script_sha = self._redis.script_load(self._lua_script)
                self._initialized = True
                logger.info("Redis rate limit backend initialized")
            except ImportError:
                logger.warning("redis package not installed - falling back to in-memory")
                return None
            except Exception as e:
                logger.warning(f"Redis connection failed: {e} - falling back to in-memory")
                return None
        return self._redis

    def check_rate_limit(self, client_ip: str, requests_per_minute: int, burst_size: int) -> bool:
        """Check rate limit using Redis with Lua script for atomicity."""
        redis_client = self._get_redis()
        if redis_client is None:
            return self._fallback_check(client_ip, requests_per_minute)

        try:
            key = f"rate_limit:{client_ip}"
            now = time.time()

            # Execute atomic Lua script
            result = redis_client.evalsha(
                self._script_sha,
                1,  # Number of keys
                key,
                requests_per_minute,
                burst_size,
                now
            )
            return result == 1

        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            return self._fallback_check(client_ip, requests_per_minute)

    def _fallback_check(self, client_ip: str, requests_per_minute: int) -> bool:
        """In-memory token bucket fallback when Redis is unavailable."""
        now = time.time()
        fallback_rpm = min(requests_per_minute, 30)  # Stricter limit during fallback

        if not hasattr(self, "_fallback_buckets"):
            self._fallback_buckets: Dict[str, list] = {}

        # Clean old entries
        if client_ip in self._fallback_buckets:
            self._fallback_buckets[client_ip] = [
                ts for ts in self._fallback_buckets[client_ip]
                if now - ts < 60
            ]
        else:
            self._fallback_buckets[client_ip] = []

        if len(self._fallback_buckets[client_ip]) >= fallback_rpm:
            return False

        self._fallback_buckets[client_ip].append(now)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.

    Limits requests per IP address within a time window.
    Supports both in-memory and Redis backends for production use.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        exempt_paths: Optional[Set[str]] = None,
        disable_in_testing: bool = True,
        backend: Optional[RateLimitBackend] = None,
        use_redis: bool = False,
        redis_url: Optional[str] = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.exempt_paths = exempt_paths or {"/health", "/metrics"}
        self.disable_in_testing = disable_in_testing

        # Initialize backend
        if backend:
            self._backend = backend
        elif use_redis or os.environ.get("USE_REDIS_RATE_LIMIT", "").lower() in ("true", "1", "yes"):
            self._backend = RedisRateLimitBackend(redis_url)
            # Fallback to in-memory if Redis not available
            self._fallback_backend = InMemoryRateLimitBackend()
        else:
            self._backend = InMemoryRateLimitBackend()
            self._fallback_backend = None

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

        # Determine rate limit key and limit based on auth status
        client_ip = self._get_client_ip(request)
        rbac_ctx = getattr(getattr(request, 'state', None), 'rbac', None)

        if rbac_ctx and getattr(rbac_ctx, 'is_authenticated', False):
            rate_key = f"user:{rbac_ctx.user_id}"
            rate_limit = self.requests_per_minute * 2  # 2x limit for authenticated
        else:
            rate_key = f"ip:{client_ip}"
            rate_limit = self.requests_per_minute

        # Check rate limit
        allowed = self._backend.check_rate_limit(
            rate_key, rate_limit, self.burst_size
        )

        if not allowed:
            logger.warning(f"Rate limit exceeded for {rate_key}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, only trusting proxy headers from known proxies."""
        direct_ip = request.client.host if request.client else "unknown"

        if direct_ip in TRUSTED_PROXIES:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                # Use rightmost non-trusted IP (secure against spoofed headers)
                ips = [ip.strip() for ip in forwarded.split(",")]
                for ip in reversed(ips):
                    if ip not in TRUSTED_PROXIES:
                        return ip
                return ips[0]  # Fallback to leftmost if all trusted
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip

        return direct_ip


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
        allowed_origins: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.secret_key = secret_key.encode("utf-8")
        self.token_name = token_name
        self.header_name = header_name
        self.safe_methods = safe_methods or {"GET", "HEAD", "OPTIONS", "TRACE"}
        self.exempt_paths = exempt_paths or {"/api/health", "/api/webhook"}

        # SPEC-004: Production safety - environment detection
        environment = os.environ.get("APP_ENVIRONMENT", "development")
        self._is_production = environment in ("production", "prod", "staging")

        # Allowed origins for Bearer auth requests (CSRF bypass security)
        # SPEC-004: In production, localhost origins are not allowed
        if allowed_origins:
            self.allowed_origins = allowed_origins
        elif self._is_production:
            # Production: Only allow the actual application domain
            # This should be configured via CORS_ORIGINS environment variable
            cors_origins = os.environ.get("CORS_ORIGINS", "").split(",")
            self.allowed_origins = [o.strip() for o in cors_origins if o.strip() and "localhost" not in o.lower() and "127.0.0.1" not in o]
            if not self.allowed_origins:
                logger.warning("[CSRF] No production origins configured - CORS_ORIGINS should be set")
        else:
            # Development: Allow localhost
            self.allowed_origins = [
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
            ]

        # CSRF metrics tracking
        self._csrf_failures = 0
        self._csrf_successes = 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip CSRF for safe methods
        if request.method in self.safe_methods:
            return await call_next(request)

        # Skip exempt paths (supports both exact matches and prefix matches ending with /)
        path = request.url.path
        for exempt_path in self.exempt_paths:
            if exempt_path.endswith('/'):
                # Prefix match for paths ending with /
                if path.startswith(exempt_path) or path == exempt_path.rstrip('/'):
                    return await call_next(request)
            else:
                # Exact match
                if path == exempt_path:
                    return await call_next(request)

        # Skip API endpoints that use Bearer auth - but verify origin first
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # SECURITY FIX: Verify origin to prevent CSRF bypass attacks
            if self._verify_origin(request):
                return await call_next(request)
            else:
                logger.warning(f"CSRF: Bearer auth with untrusted origin for {request.url.path}")
                # Continue to CSRF validation if origin not trusted

        # Validate CSRF token
        session_token = request.cookies.get(self.token_name)
        request_token = (
            request.headers.get(self.header_name) or
            (await self._get_form_token(request))
        )

        if not session_token or not request_token:
            self._csrf_failures += 1
            logger.warning(
                f"[CSRF] Token missing | path={request.url.path} | "
                f"method={request.method} | failures={self._csrf_failures}"
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing"},
            )

        if not self._verify_token(session_token, request_token):
            self._csrf_failures += 1
            logger.warning(
                f"[CSRF] Token invalid | path={request.url.path} | "
                f"method={request.method} | failures={self._csrf_failures}"
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token invalid"},
            )

        self._csrf_successes += 1
        response = await call_next(request)

        # Rotate CSRF token after successful state-changing requests
        # SECURITY FIX: Align with refresh token expiration (7 days)
        if request.method in ("POST", "PUT", "DELETE", "PATCH") and 200 <= response.status_code < 300:
            new_token = self.generate_token()
            response.set_cookie(
                key=self.token_name,
                value=new_token,
                httponly=False,
                samesite="lax",
                path="/",
                max_age=604800,  # 7 days - aligned with refresh token expiration
            )
            response.headers["X-CSRF-Token"] = new_token

        return response

    async def _get_form_token(self, request: Request) -> Optional[str]:
        """Extract CSRF token from form data."""
        try:
            if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
                form = await request.form()
                return form.get(self.token_name)
        except (ValueError, RuntimeError, KeyError) as e:
            logger.debug(f"Form token extraction failed: {e}")
        return None

    def _verify_token(self, session_token: str, request_token: str) -> bool:
        """Verify CSRF token."""
        return hmac.compare_digest(session_token, request_token)

    def _verify_origin(self, request: Request) -> bool:
        """
        Verify request origin for Bearer auth CSRF bypass.

        Checks Origin header first, falls back to Referer.
        Returns True if origin is trusted, False otherwise.
        """
        # Check Origin header (preferred)
        origin = request.headers.get("Origin")
        if origin:
            # Normalize origin (remove trailing slash)
            origin = origin.rstrip("/")
            if origin in self.allowed_origins or self._is_same_origin(request, origin):
                return True
            return False

        # Fall back to Referer header
        referer = request.headers.get("Referer")
        if referer:
            # Extract origin from referer URL
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            referer_origin = f"{parsed.scheme}://{parsed.netloc}"
            if referer_origin in self.allowed_origins or self._is_same_origin(request, referer_origin):
                return True
            return False

        # No Origin or Referer - require Bearer authentication for CSRF bypass
        # This prevents CSRF attacks while allowing legitimate API clients
        auth_header = request.headers.get("Authorization", "")
        content_type = request.headers.get("Content-Type", "")

        # SECURITY FIX: Only bypass CSRF if Bearer token is present
        # Bearer tokens prove the request is from a legitimate API client
        if auth_header.startswith("Bearer ") and len(auth_header) > 10:
            # Has Bearer token - API client with authentication
            logger.debug("[CSRF] Bypassing CSRF check for authenticated API request")
            return True

        # For JSON requests without Bearer token, require a valid API key header
        api_key = request.headers.get("X-API-Key", "")
        if "application/json" in content_type and api_key:
            logger.debug("[CSRF] Bypassing CSRF check for API key authenticated request")
            return True

        # Log suspicious requests without proper authentication
        user_agent = request.headers.get("User-Agent", "")
        if "application/json" in content_type:
            logger.warning(
                f"[CSRF] JSON request without authentication | "
                f"path={request.url.path} | ua={user_agent[:50]}"
            )

        # Otherwise, require Origin or Referer
        return False

    def _is_same_origin(self, request: Request, origin: str) -> bool:
        """Check if origin matches the request's host."""
        from urllib.parse import urlparse
        parsed = urlparse(origin)

        # Get request host
        request_host = request.headers.get("Host", "")

        # Compare netloc (host:port)
        return parsed.netloc == request_host

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


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    IP Whitelist middleware for tenant-level access control.

    When enabled for a tenant, only requests from whitelisted IPs are allowed.
    Platform admins and public routes bypass this check.
    """

    # Routes that bypass IP whitelist (public access)
    PUBLIC_PATHS = {
        "/health",
        "/api/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/static",
        "/favicon.ico",
    }

    def __init__(self, app, get_tenant_whitelist: Optional[Callable] = None):
        """
        Initialize IP Whitelist middleware.

        Args:
            app: FastAPI application
            get_tenant_whitelist: Callable that takes tenant_id and returns list of allowed IPs
        """
        super().__init__(app)
        self.get_tenant_whitelist = get_tenant_whitelist or self._default_get_whitelist

    def _default_get_whitelist(self, tenant_id: str) -> Optional[List[str]]:
        """Default whitelist lookup from database."""
        try:
            from database.tenant_persistence import get_tenant_persistence
            persistence = get_tenant_persistence()
            tenant = persistence.get_tenant(tenant_id)
            if tenant and hasattr(tenant, 'ip_whitelist'):
                return tenant.ip_whitelist
            return None
        except Exception as e:
            logger.warning(f"[IP_WHITELIST] Failed to get whitelist for tenant {tenant_id}: {e}")
            return None

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, handling proxies (rightmost non-trusted from XFF)."""
        direct_ip = request.client.host if request.client else "unknown"
        if direct_ip in TRUSTED_PROXIES:
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                ips = [ip.strip() for ip in forwarded_for.split(",")]
                for ip in reversed(ips):
                    if ip not in TRUSTED_PROXIES:
                        return ip
                return ips[0]

        # Check X-Real-IP
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return "unknown"

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (bypasses whitelist)."""
        for public_path in self.PUBLIC_PATHS:
            if path.startswith(public_path):
                return True
        return False

    def _ip_matches(self, client_ip: str, whitelist: List[str]) -> bool:
        """Check if client IP matches any entry in whitelist."""
        import ipaddress

        try:
            client = ipaddress.ip_address(client_ip)

            for entry in whitelist:
                entry = entry.strip()
                if not entry:
                    continue

                try:
                    # Check if it's a network (CIDR notation)
                    if "/" in entry:
                        network = ipaddress.ip_network(entry, strict=False)
                        if client in network:
                            return True
                    else:
                        # Single IP address
                        if client == ipaddress.ip_address(entry):
                            return True
                except ValueError:
                    logger.warning(f"[IP_WHITELIST] Invalid whitelist entry: {entry}")
                    continue

            return False
        except ValueError:
            logger.warning(f"[IP_WHITELIST] Invalid client IP: {client_ip}")
            return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip check for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Get tenant ID from request (various sources)
        tenant_id = None

        # Try from auth context (JWT claims)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from rbac.jwt import decode_token_safe
                payload = decode_token_safe(auth_header[7:])
                if payload:
                    tenant_id = payload.get("firm_id") or payload.get("tenant_id")
                    # Platform admins bypass IP whitelist
                    role = payload.get("role", "")
                    if role in ("super_admin", "platform_admin", "support"):
                        return await call_next(request)
            except (ImportError, ValueError, KeyError) as e:
                logger.debug(f"JWT decode failed for IP whitelist: {e}")

        # Try from session cookie
        if not tenant_id:
            session_id = request.cookies.get("tax_session_id")
            if session_id:
                try:
                    from database.session_persistence import get_session_persistence
                    persistence = get_session_persistence()
                    session = persistence.load_session(session_id)
                    if session:
                        tenant_id = session.tenant_id
                except (ImportError, AttributeError, ValueError) as e:
                    logger.debug(f"Session lookup failed for IP whitelist: {e}")

        # No tenant context, allow request (public access)
        if not tenant_id:
            return await call_next(request)

        # Get whitelist for tenant
        whitelist = self.get_tenant_whitelist(tenant_id)

        # No whitelist configured, allow all
        if not whitelist:
            return await call_next(request)

        # Check if client IP is in whitelist
        client_ip = self._get_client_ip(request)

        if self._ip_matches(client_ip, whitelist):
            return await call_next(request)

        # IP not in whitelist - deny access
        logger.warning(
            f"[IP_WHITELIST] Access denied | tenant={tenant_id} | ip={client_ip} | path={request.url.path}"
        )

        return JSONResponse(
            status_code=403,
            content={
                "detail": "Access denied: IP address not in whitelist",
                "error_code": "IP_NOT_WHITELISTED",
            },
        )


def configure_security_middleware(
    app: FastAPI,
    secret_key: str,
    cors_origins: List[str] = None,
    enable_csrf: bool = True,
    enable_rate_limit: bool = True,
    use_redis_rate_limit: bool = False,
    redis_url: Optional[str] = None,
) -> None:
    """
    Configure all security middleware for a FastAPI application.

    Args:
        app: FastAPI application
        secret_key: Secret key for signing
        cors_origins: Allowed CORS origins
        enable_csrf: Enable CSRF protection
        enable_rate_limit: Enable rate limiting
        use_redis_rate_limit: Use Redis for rate limiting (recommended for production)
        redis_url: Redis URL for rate limiting (defaults to REDIS_URL env var)
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
            use_redis=use_redis_rate_limit,
            redis_url=redis_url,
        )

    # CSRF protection
    if enable_csrf:
        app.add_middleware(
            CSRFMiddleware,
            secret_key=secret_key,
            exempt_paths={
                "/api/health",
                "/api/webhook",
                "/api/chat",
                "/api/ai-chat/",
                "/api/cpa/lead-magnet/",  # Lead magnet funnel - public API
                "/api/lead-magnet/",       # Lead magnet - public API
                "/api/advisor/",           # AI advisor - public API
                "/api/sessions/",          # Session management - public API
            },
            allowed_origins=cors_origins or ["http://localhost:3000", "http://localhost:8000"],
        )

    logger.info("Security middleware configured")


# =============================================================================
# ENDPOINT-SPECIFIC RATE LIMITING
# =============================================================================

class EndpointRateLimiter:
    """
    Endpoint-specific rate limiter for fine-grained control.

    Use this for endpoints that need stricter limits than the global rate limit.

    Example:
        estimates_limiter = EndpointRateLimiter(max_requests=10, window_seconds=60)

        @router.post("/quick-estimate")
        async def quick_estimate(request: Request):
            await estimates_limiter.check(request)
            # ... endpoint logic
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: int = 60,
        key_func: Optional[Callable[[Request], str]] = None,
        use_redis: bool = False,
        redis_url: Optional[str] = None,
    ):
        """
        Initialize endpoint rate limiter.

        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            key_func: Function to extract rate limit key from request (default: client IP)
            use_redis: Use Redis for distributed rate limiting
            redis_url: Redis URL (defaults to REDIS_URL env var)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or self._default_key_func

        # Initialize backend
        if use_redis or os.environ.get("USE_REDIS_RATE_LIMIT", "").lower() in ("true", "1", "yes"):
            self._backend = RedisRateLimitBackend(redis_url)
        else:
            self._backend = InMemoryRateLimitBackend()

    def _default_key_func(self, request: Request) -> str:
        """Default key function: use client IP (rightmost non-trusted from XFF)."""
        direct_ip = request.client.host if request.client else "unknown"

        if direct_ip in TRUSTED_PROXIES:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ips = [ip.strip() for ip in forwarded.split(",")]
                for ip in reversed(ips):
                    if ip not in TRUSTED_PROXIES:
                        return ip
                return ips[0]
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip

        return direct_ip

    async def check(self, request: Request) -> None:
        """
        Check rate limit and raise HTTPException if exceeded.

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        key = self.key_func(request)
        requests_per_minute = int(self.max_requests * (60 / self.window_seconds))

        allowed = self._backend.check_rate_limit(
            client_ip=key,
            requests_per_minute=requests_per_minute,
            burst_size=self.max_requests,
        )

        if not allowed:
            logger.warning(f"Endpoint rate limit exceeded for key: {key}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests. Limit: {self.max_requests} per {self.window_seconds} seconds.",
                    "retry_after": self.window_seconds,
                },
                headers={"Retry-After": str(self.window_seconds)},
            )


# Pre-configured rate limiters for common use cases
from fastapi import HTTPException

# Lead estimates: 10 per minute
ESTIMATES_RATE_LIMITER = EndpointRateLimiter(max_requests=10, window_seconds=60)

# Contact capture: 5 per minute
CONTACT_RATE_LIMITER = EndpointRateLimiter(max_requests=5, window_seconds=60)

# Signal processing: 30 per minute
SIGNALS_RATE_LIMITER = EndpointRateLimiter(max_requests=30, window_seconds=60)

# API-heavy operations: 100 per minute
API_RATE_LIMITER = EndpointRateLimiter(max_requests=100, window_seconds=60)
