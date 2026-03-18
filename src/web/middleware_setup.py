"""
Middleware configuration for the FastAPI application.

Extracts all middleware setup from app.py into a single
`configure_middleware(app)` function for clarity and maintainability.
"""

import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# Environment detection
_environment = os.environ.get("APP_ENVIRONMENT", "production")
_is_dev = _environment not in ("production", "prod", "staging")
_is_production = not _is_dev


def configure_middleware(app: FastAPI) -> dict:
    """
    Configure all middleware on the FastAPI app instance.

    Middleware is added in reverse execution order (last added = first executed).

    Returns a dict with:
      - csrf_secret_key: bytes or None (needed by CSRF token generation helpers)
    """
    result = {"csrf_secret_key": None}

    # =========================================================================
    # CORS MIDDLEWARE CONFIGURATION
    # =========================================================================
    cors_origins_str = os.environ.get("CORS_ORIGINS", "")
    cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

    if _is_dev:
        dev_origins = [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        cors_origins = list(set(cors_origins + dev_origins))
        logger.warning(
            "CORS: Dev origins active (APP_ENVIRONMENT=%s). "
            "Set APP_ENVIRONMENT=production for prod.",
            _environment,
        )
    elif not cors_origins:
        if _is_production:
            logger.error(
                "CORS: No origins configured in production! Set CORS_ORIGINS env var. "
                "Requests with Origin headers will be rejected."
            )
        else:
            logger.warning(
                "CORS: No origins configured. Set CORS_ORIGINS env var for your production domain(s)."
            )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Authorization",
            "Content-Type",
            "Content-Length",
            "Origin",
            "X-Requested-With",
            "X-CSRF-Token",
            "X-Request-ID",
            "X-Correlation-ID",
            "X-Tenant-ID",
            "X-Session-Token",
            "X-Preparer-ID",
        ],
        expose_headers=["X-Request-ID", "X-Correlation-ID", "X-RateLimit-Remaining-Minute"],
    )
    logger.info(f"CORS middleware enabled for {len(cors_origins)} origin(s) [env={_environment}]")

    # =========================================================================
    # SECURITY MIDDLEWARE (ORDER MATTERS - Last added = First executed)
    # =========================================================================
    from security.middleware import (
        SecurityHeadersMiddleware,
        CSRFCookieMiddleware,
        RateLimitMiddleware,
        RequestValidationMiddleware,
        CSRFMiddleware,
    )
    from security.tenant_isolation_middleware import TenantIsolationMiddleware

    # GZip compression
    from starlette.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # 0. HTTPS Redirect (production/staging only)
    if _is_production:
        try:
            from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
            app.add_middleware(HTTPSRedirectMiddleware)
            logger.info("HTTPS redirect middleware enabled (production)")
        except Exception as e:
            logger.error(f"Failed to add HTTPS redirect middleware: {e}")

    # 1. Security Headers (HSTS, CSP, X-Frame-Options, etc.)
    try:
        app.add_middleware(SecurityHeadersMiddleware)
        logger.info("Security headers middleware enabled")
    except Exception as e:
        if _is_production:
            raise RuntimeError(f"CRITICAL: Security headers middleware failed to load: {e}")
        logger.warning(f"Security headers middleware failed: {e}")

    # 2. Rate Limiting (60 requests/minute per IP)
    try:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=60,
            burst_size=20,
            exempt_paths={"/health", "/metrics", "/static"},
        )
        logger.info("Rate limiting middleware enabled")
    except Exception as e:
        if _is_production:
            raise RuntimeError(f"CRITICAL: Rate limiting middleware failed to load: {e}")
        logger.warning(f"Rate limiting middleware failed: {e}")

    # 3. Request Validation (size limits, content type)
    try:
        app.add_middleware(
            RequestValidationMiddleware,
            max_content_length=50 * 1024 * 1024,  # 50MB for document uploads
        )
        logger.info("Request validation middleware enabled")
    except Exception as e:
        if _is_production:
            raise RuntimeError(f"CRITICAL: Request validation middleware failed to load: {e}")
        logger.warning(f"Request validation middleware failed: {e}")

    # 4. CSRF Protection (for state-changing operations)
    try:
        csrf_secret = os.environ.get("CSRF_SECRET_KEY")

        if not csrf_secret:
            if _is_production:
                raise RuntimeError(
                    "CRITICAL: CSRF_SECRET_KEY environment variable is required in production. "
                    'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
            import secrets
            csrf_secret = secrets.token_hex(32)
            logger.warning("CSRF_SECRET_KEY not set, using generated key (not persistent across restarts)")

        # SPEC-004: CSRF Exempt Paths Documentation
        csrf_exempt_paths = {
            # Embeddable Advisor (uses session token auth instead of CSRF)
            "/advisor-embed",
            # Read-Only Endpoints (Safe - No State Changes)
            "/api/health",
            "/api/sessions/check-active",
            "/api/validate/fields",
            "/api/calculate-tax",
            "/api/estimate",
            "/api/v1/admin/health",
            # Bearer Auth Protected (Alternative Security)
            "/api/chat",
            "/api/advisor/",
            "/api/ai-chat/chat",
            "/api/ai-chat/upload",
            "/api/ai-chat/analyze-document",
            "/api/v1/auth/",
            "/api/core/auth/",
            "/api/v1/admin/auth/",
            "/api/v1/advisory-reports/",
            # Session-Based with Alternative Protection
            "/api/sessions/",
            "/api/sessions/create-session",
            # Webhook Endpoints (Signature Validation)
            "/api/webhook",
            # Public Lead Capture (Rate Limited)
            "/api/leads/create",
            "/api/cpa/lead-magnet/",
            "/api/lead-magnet/",
        }

        app.add_middleware(
            CSRFMiddleware,
            secret_key=csrf_secret,
            exempt_paths=csrf_exempt_paths,
        )
        logger.info("CSRF protection middleware enabled")

        _csrf_secret_key = csrf_secret.encode("utf-8")

        # 5. CSRF Cookie Persistence
        csrf_cookie_max_age = 7 * 24 * 60 * 60  # 7 days
        app.add_middleware(
            CSRFCookieMiddleware,
            secret_key=_csrf_secret_key,
            cookie_name="csrf_token",
            cookie_max_age=csrf_cookie_max_age,
            secure=_is_production,
        )
        logger.info("CSRF cookie persistence middleware enabled")
        result["csrf_secret_key"] = _csrf_secret_key
    except Exception as e:
        logger.warning(f"CSRF middleware failed: {e}")

    # =========================================================================
    # IDEMPOTENCY MIDDLEWARE (duplicate submission prevention)
    # =========================================================================
    try:
        from web.idempotency import IdempotencyMiddleware
        app.add_middleware(IdempotencyMiddleware)
        logger.info("Idempotency middleware enabled (POST/PUT/PATCH duplicate protection)")
    except ImportError:
        logger.warning("Idempotency middleware not available")

    # =========================================================================
    # ADDITIONAL MIDDLEWARE
    # =========================================================================

    # Correlation ID middleware for request tracing
    try:
        from middleware.correlation import CorrelationIdMiddleware
        app.add_middleware(CorrelationIdMiddleware)
        logger.info("Correlation ID middleware enabled")
    except ImportError:
        logger.warning("Correlation ID middleware not available")

    # =========================================================================
    # GLOBAL RBAC MIDDLEWARE (Feature-flagged)
    # =========================================================================
    RBAC_V2_ENABLED = True

    if RBAC_V2_ENABLED:
        try:
            from core.rbac.middleware import RBACMiddleware, RBACMiddlewareConfig

            rbac_config = RBACMiddlewareConfig(
                public_paths={
                    "/",
                    "/health",
                    "/metrics",
                    "/login",
                    "/signin",
                    "/signup",
                    "/register",
                    "/auth/login",
                    "/auth/register",
                    "/forgot-password",
                    "/reset-password",
                    "/mfa-verify",
                    "/auth/mfa-verify",
                    "/landing",
                    "/quick-estimate",
                    "/estimate",
                    "/advisor-embed",
                    "/client/login",
                    "/api/v1/auth/login",
                    "/api/v1/auth/register",
                    "/api/v1/auth/forgot-password",
                    "/api/v1/auth/reset-password",
                    "/api/v1/auth/verify-email",
                    "/api/mfa/validate",
                    "/docs",
                    "/redoc",
                    "/openapi.json",
                },
                public_path_prefixes={
                    "/static/",
                    "/assets/",
                    "/api/core/auth/",
                },
                rbac_v2_enabled=True,
                fallback_to_legacy=True,
            )

            def get_db_session_factory():
                try:
                    from database import get_async_session_factory
                    return get_async_session_factory()
                except ImportError:
                    return None

            def get_cache_factory():
                try:
                    from core.rbac.cache import get_permission_cache
                    return get_permission_cache
                except ImportError:
                    return None

            app.add_middleware(
                RBACMiddleware,
                config=rbac_config,
                get_db_session=get_db_session_factory(),
                get_cache=get_cache_factory(),
            )
            logger.info("Global RBAC v2 middleware enabled")
        except ImportError as e:
            logger.warning(f"Global RBAC middleware not available: {e}")
    else:
        logger.info("Global RBAC v2 middleware disabled (feature flag off)")

    # =========================================================================
    # TENANT ISOLATION MIDDLEWARE
    # =========================================================================
    app.add_middleware(
        TenantIsolationMiddleware,
        strict_mode=not _is_dev,
        audit_all_access=True,
        detect_anomalies=True,
        exempt_paths={
            "/", "/health", "/healthz", "/ready", "/metrics",
            "/api/v1/auth/login", "/api/v1/auth/register",
            "/api/v1/auth/forgot-password", "/api/v1/auth/reset-password",
            "/docs", "/openapi.json", "/redoc",
        },
    )
    logger.info("Tenant isolation middleware enabled (strict_mode=%s)", not _is_dev)

    return result
