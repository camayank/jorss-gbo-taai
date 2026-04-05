"""
Application startup and shutdown event handlers.

Extracted from app.py to keep the composition root clean.
"""

import os
import logging

logger = logging.getLogger(__name__)

_environment = os.environ.get("APP_ENVIRONMENT", "production")
_is_dev = _environment not in ("production", "prod", "staging")
_is_production = not _is_dev


async def on_startup_banner():
    """Print startup banner and validate required environment variables."""
    _app_version = os.environ.get("APP_VERSION", "1.0.0")
    _port = os.environ.get("PORT", "8000")
    _log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()

    logger.info("=" * 60)
    logger.info(f"  Jorss-GBO CPA TAI  v{_app_version}")
    logger.info(f"  Environment : {_environment}")
    logger.info(f"  Log level   : {_log_level_name}")
    logger.info(f"  Port        : {_port}")
    logger.info("=" * 60)

    # Check critical env vars
    _required_in_prod = {
        "JWT_SECRET": "Authentication tokens cannot be signed",
    }
    missing = []
    for var, reason in _required_in_prod.items():
        val = os.environ.get(var, "")
        if not val or val.startswith("REPLACE_"):
            missing.append(f"  - {var}: {reason}")

    if missing and _is_production:
        msg = "Missing required environment variables:\n" + "\n".join(missing)
        logger.error(msg)
        raise RuntimeError(msg)
    elif missing:
        logger.warning("Missing env vars (non-critical in dev):\n" + "\n".join(missing))

    from config.ai_providers import get_available_providers, validate_ai_configuration
    providers = get_available_providers()
    if not providers:
        if _is_production:
            msg = "No AI provider API keys configured. Set at least one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY"
            logger.error(msg)
            raise RuntimeError(msg)
        logger.warning(
            "No AI provider API keys configured; AI-dependent features are disabled"
        )
    else:
        # Log provider availability details
        config_status = validate_ai_configuration()
        for provider_name, status in config_status.items():
            if provider_name.startswith("_"):
                continue
            if status.get("available"):
                models = status.get("models", [])
                model_str = ", ".join(str(m.value) if hasattr(m, "value") else str(m) for m in models)
                logger.info(f"AI provider {provider_name}: available ({len(models)} capabilities: {model_str})")
            else:
                logger.info(f"AI provider {provider_name}: unavailable (no API key)")

    # Coherence check: warn if AI chat enabled but no providers available
    ai_chat_enabled = os.environ.get("AI_CHAT_ENABLED", "").lower() in ("true", "1", "yes")
    if ai_chat_enabled and not providers:
        logger.warning(
            "COHERENCE WARNING: AI_CHAT_ENABLED=true but no AI providers are available. "
            "Chat features will fall back to rule-based responses."
        )

    # Warn if JWT secret is weak
    jwt_secret = os.environ.get("JWT_SECRET", "")
    if jwt_secret and len(jwt_secret) < 32 and _is_production:
        raise RuntimeError("JWT_SECRET must be at least 32 characters in production")


async def on_startup_security_validation():
    """
    Validate security configuration at application startup.

    CRITICAL: In production, the application will fail to start if
    APP_SECRET_KEY, JWT_SECRET, AUTH_SECRET_KEY, PASSWORD_SALT,
    ENCRYPTION_MASTER_KEY, or CSRF_SECRET_KEY are missing or weak.
    """
    try:
        from config.settings import get_settings, validate_startup_security

        settings = get_settings()

        if settings.is_production:
            validate_startup_security(settings, exit_on_failure=True)
            logger.info("[SECURITY] Production security validation PASSED")
        else:
            errors = settings.validate_production_security()
            if errors:
                logger.warning(
                    f"[SECURITY] Development mode - {len(errors)} security settings "
                    "would fail in production. Set APP_ENVIRONMENT=production to enforce."
                )
    except Exception as e:
        logger.error(f"[SECURITY] Security validation failed: {e}")
        raise


async def on_startup_database():
    """Initialize database on application startup."""
    try:
        from database import init_database, check_database_connection
        from config.database import get_database_settings

        settings = get_database_settings()

        await init_database(settings)

        if await check_database_connection(settings):
            logger.info(
                f"Database initialized: {settings.driver}",
                extra={"database": settings.name if settings.is_postgres else "sqlite"}
            )
        else:
            if _is_production:
                raise RuntimeError("Database connection check failed -- cannot start in production without database")
            logger.warning("Database connection check failed during startup")

    except RuntimeError:
        raise
    except Exception as e:
        if _is_production:
            raise RuntimeError(f"Database initialization failed in production: {e}")
        logger.error(f"Database initialization failed: {e}")


async def on_startup_redis():
    """Check Redis connectivity on startup."""
    redis_url = os.environ.get("REDIS_URL", "") or os.environ.get("REDIS_HOST", "")
    if not redis_url:
        if _is_production:
            logger.warning("[REDIS] No REDIS_URL or REDIS_HOST configured -- using in-memory fallbacks")
        else:
            logger.info("[REDIS] Not configured (in-memory fallback for dev)")
        return

    try:
        from cache import redis_health_check
        health = await redis_health_check()
        if health.get("status") == "healthy":
            logger.info("[REDIS] Connection healthy")
        else:
            error = health.get("error", "unknown")
            if _is_production:
                raise RuntimeError(f"Redis connection failed in production: {error}")
            logger.warning(f"[REDIS] Connection unhealthy: {error}")
    except RuntimeError:
        raise
    except Exception as e:
        if _is_production:
            raise RuntimeError(f"Redis startup check failed in production: {e}")
        logger.warning(f"[REDIS] Startup check failed: {e}")


async def on_startup_auto_save():
    """Start auto-save manager on application startup."""
    try:
        from web.auto_save import get_auto_save_manager
        import asyncio

        auto_save = get_auto_save_manager()
        asyncio.create_task(auto_save.start())
        logger.info("Auto-save manager started (interval: 30s)")
    except Exception as e:
        logger.error(f"Auto-save initialization failed: {e}")


async def on_startup_production_readiness_check():
    """
    Check production readiness and warn about in-memory storage components.
    """
    in_memory_components = [
        ("Billing Storage", "core/api/billing_routes.py", "subscriptions and invoices"),
        ("Audit Logs", "admin_panel/services/audit_service.py", "compliance audit trail"),
        ("Staff Assignments", "cpa_panel/staff/assignment_service.py", "CPA staff assignments"),
        ("Client Tokens", "cpa_panel/api/client_portal_routes.py", "client authentication"),
        ("Impersonation", "admin_panel/support/impersonation_service.py", "support sessions"),
    ]

    if _is_production:
        logger.warning("=" * 70)
        logger.warning("  PRODUCTION READINESS WARNING")
        logger.warning("=" * 70)
        logger.warning("  The following components use IN-MEMORY storage:")
        for name, location, description in in_memory_components:
            logger.warning(f"    - {name}: {description}")
        logger.warning("  ")
        logger.warning("  Data in these components will be LOST on restart!")
        logger.warning("  For production, migrate to database storage using the")
        logger.warning("  migration: 20260212_0001_add_missing_tables.py")
        logger.warning("=" * 70)
    else:
        logger.info("Production readiness check passed (in-memory storage OK for development)")


async def on_startup_irs_rag_warmup():
    """
    Pre-warm FAISS semantic indices on application startup.

    Eliminates cold-start latency by loading indices into memory during startup.
    This is a background task that runs asynchronously and does not block app startup.
    """
    try:
        from services.irs_rag import warm_irs_indices

        # Run index warming in background (non-blocking)
        import asyncio
        asyncio.create_task(warm_irs_indices(tax_years=[2025, 2024]))
        logger.info("IRS RAG index warming started (background task)")
    except ImportError:
        logger.debug("IRS RAG service not available")
    except Exception as e:
        logger.warning(f"IRS RAG warmup initialization failed: {e}")


async def on_shutdown_database():
    """Close database connections on application shutdown."""
    try:
        from database import close_database

        await close_database()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


async def on_shutdown_auto_save():
    """Stop auto-save manager on application shutdown."""
    try:
        from web.auto_save import get_auto_save_manager

        auto_save = get_auto_save_manager()
        auto_save.stop()
        await auto_save.flush(force_all=True)
        logger.info("Auto-save manager stopped")
    except Exception as e:
        logger.error(f"Error stopping auto-save: {e}")


def register_lifecycle_events(app):
    """Register all startup and shutdown event handlers on the app."""
    app.on_event("startup")(on_startup_banner)
    app.on_event("startup")(on_startup_security_validation)
    app.on_event("startup")(on_startup_database)
    app.on_event("startup")(on_startup_redis)
    app.on_event("startup")(on_startup_auto_save)
    app.on_event("startup")(on_startup_production_readiness_check)
    app.on_event("startup")(on_startup_irs_rag_warmup)
    app.on_event("shutdown")(on_shutdown_database)
    app.on_event("shutdown")(on_shutdown_auto_save)
