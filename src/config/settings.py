"""Application settings using Pydantic Settings.

Centralized configuration for the tax platform.

SECURITY: Production requires the following environment variables:
- APP_SECRET_KEY: Main application secret (min 32 chars)
- JWT_SECRET: JWT signing key (min 32 chars)
- AUTH_SECRET_KEY: Auth service secret (min 32 chars)
- PASSWORD_SALT: Password hashing salt (min 16 chars)
- ENCRYPTION_MASTER_KEY: PII encryption key (min 32 chars)

Generate secrets with: python -c "import secrets; print(secrets.token_hex(32))"
"""

import os
import sys
import logging
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class RedisSettings(BaseSettings):
    """Redis configuration for caching and Celery broker."""

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        extra="ignore",
    )

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database number")
    password: Optional[str] = Field(default=None, description="Redis password")
    ssl: bool = Field(default=False, description="Use SSL for Redis connection")

    # Connection pool settings
    max_connections: int = Field(default=50, description="Max Redis connections")
    socket_timeout: int = Field(default=5, description="Socket timeout in seconds")
    socket_connect_timeout: int = Field(default=5, description="Connection timeout")

    # Cache settings
    key_prefix: str = Field(default="tax:", description="Prefix for all cache keys")
    default_ttl: int = Field(default=3600, description="Default TTL in seconds (1 hour)")

    @property
    def url(self) -> str:
        """Get Redis URL."""
        auth = f":{self.password}@" if self.password else ""
        protocol = "rediss" if self.ssl else "redis"
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"


class CelerySettings(BaseSettings):
    """Celery task queue configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        extra="ignore",
    )

    broker_db: int = Field(default=1, description="Redis DB for Celery broker")
    result_db: int = Field(default=2, description="Redis DB for Celery results")

    task_serializer: str = Field(default="json", description="Task serialization format")
    result_serializer: str = Field(default="json", description="Result serialization format")
    accept_content: list = Field(default=["json"], description="Accepted content types")

    task_acks_late: bool = Field(default=True, description="Acknowledge tasks after completion")
    task_reject_on_worker_lost: bool = Field(default=True, description="Reject tasks if worker lost")

    worker_prefetch_multiplier: int = Field(default=1, description="Tasks to prefetch per worker")
    task_time_limit: int = Field(default=300, description="Hard task time limit in seconds")
    task_soft_time_limit: int = Field(default=240, description="Soft task time limit")


class ResilienceSettings(BaseSettings):
    """Resilience patterns configuration."""

    model_config = SettingsConfigDict(
        env_prefix="RESILIENCE_",
        extra="ignore",
    )

    # Retry settings
    retry_max_attempts: int = Field(default=3, description="Max retry attempts")
    retry_initial_delay: float = Field(default=1.0, description="Initial delay in seconds")
    retry_backoff_multiplier: float = Field(default=2.0, description="Backoff multiplier")
    retry_max_delay: float = Field(default=60.0, description="Max delay between retries")

    # Circuit breaker settings
    circuit_failure_threshold: int = Field(default=5, description="Failures to open circuit")
    circuit_recovery_timeout: int = Field(default=30, description="Seconds before half-open")
    circuit_half_open_requests: int = Field(default=3, description="Test requests in half-open")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application info
    name: str = Field(default="Tax Platform", description="Application name")
    version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment name")

    # API settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")

    # Security
    # CRITICAL: Must be set via APP_SECRET_KEY environment variable in production
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    secret_key: str = Field(
        default="change-me-in-production-INSECURE",
        description="Secret key for signing - MUST be set in production"
    )

    # Additional security settings
    jwt_secret_key: Optional[str] = Field(
        default=None,
        description="JWT signing key - auto-generated if not set (set JWT_SECRET_KEY in production)"
    )
    encryption_key: Optional[str] = Field(
        default=None,
        description="Data encryption key - auto-generated if not set (set ENCRYPTION_MASTER_KEY in production)"
    )
    serializer_key: Optional[str] = Field(
        default=None,
        description="Serialization signing key - auto-generated if not set (set SERIALIZER_SECRET_KEY in production)"
    )

    # Security enforcement
    enforce_https: bool = Field(
        default=False,
        description="Enforce HTTPS in production"
    )
    enable_rate_limiting: bool = Field(
        default=True,
        description="Enable API rate limiting"
    )

    # CORS
    cors_origins: list = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )

    # Tax year configuration
    default_tax_year: int = Field(default=2025, description="Default tax year")

    # Feature flags
    enable_caching: bool = Field(default=True, description="Enable Redis caching")
    enable_background_tasks: bool = Field(default=True, description="Enable Celery tasks")
    enable_dual_write: bool = Field(default=False, description="Enable dual-write migration")

    # Nested settings (loaded separately)
    @property
    def redis(self) -> RedisSettings:
        return RedisSettings()

    @property
    def celery(self) -> CelerySettings:
        return CelerySettings()

    @property
    def resilience(self) -> ResilienceSettings:
        return ResilienceSettings()

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment in ("production", "prod", "staging")

    def validate_production_security(self) -> List[str]:
        """
        Validate all security requirements for production.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not self.is_production:
            return errors

        # Check APP_SECRET_KEY
        if "INSECURE" in self.secret_key or self.secret_key == "change-me-in-production":
            errors.append(
                "APP_SECRET_KEY: Must be set in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        elif len(self.secret_key) < 32:
            errors.append("APP_SECRET_KEY: Must be at least 32 characters")

        # Check JWT_SECRET
        jwt_secret = os.environ.get("JWT_SECRET")
        if not jwt_secret:
            errors.append(
                "JWT_SECRET: Required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        elif len(jwt_secret) < 32:
            errors.append("JWT_SECRET: Must be at least 32 characters")

        # Check AUTH_SECRET_KEY
        auth_secret = os.environ.get("AUTH_SECRET_KEY")
        if not auth_secret:
            errors.append(
                "AUTH_SECRET_KEY: Required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        elif len(auth_secret) < 32:
            errors.append("AUTH_SECRET_KEY: Must be at least 32 characters")

        # Check PASSWORD_SALT
        password_salt = os.environ.get("PASSWORD_SALT")
        if not password_salt:
            errors.append(
                "PASSWORD_SALT: Required in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(16))\""
            )
        elif len(password_salt) < 16:
            errors.append("PASSWORD_SALT: Must be at least 16 characters")

        # Check ENCRYPTION_MASTER_KEY
        encryption_key = os.environ.get("ENCRYPTION_MASTER_KEY")
        if not encryption_key:
            errors.append(
                "ENCRYPTION_MASTER_KEY: Required in production for PII encryption. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        elif len(encryption_key) < 32:
            errors.append("ENCRYPTION_MASTER_KEY: Must be at least 32 characters")

        # Check CSRF_SECRET_KEY (SPEC-002 addition)
        csrf_secret = os.environ.get("CSRF_SECRET_KEY")
        if not csrf_secret:
            errors.append(
                "CSRF_SECRET_KEY: Required in production for CSRF protection. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        elif len(csrf_secret) < 32:
            errors.append("CSRF_SECRET_KEY: Must be at least 32 characters")

        # Check HTTPS enforcement
        if not self.enforce_https:
            errors.append(
                "APP_ENFORCE_HTTPS: Should be True in production for security"
            )

        return errors


# =============================================================================
# STARTUP VALIDATION
# =============================================================================

class StartupSecurityError(Exception):
    """Raised when security validation fails at startup."""
    pass


def validate_startup_security(settings: Settings, exit_on_failure: bool = True) -> bool:
    """
    Validate security settings at application startup.

    This function should be called early in the application startup process.
    In production, it will fail fast if critical security settings are missing.

    Args:
        settings: Application settings instance
        exit_on_failure: If True, exit the process on failure (default)

    Returns:
        True if validation passes

    Raises:
        StartupSecurityError: If validation fails and exit_on_failure is False
    """
    errors = settings.validate_production_security()

    if not errors:
        if settings.is_production:
            logger.info("Production security validation PASSED")
        return True

    # Format error message
    error_msg = (
        "\n" + "=" * 60 + "\n"
        "CRITICAL SECURITY CONFIGURATION ERROR\n"
        "=" * 60 + "\n\n"
        "The following security settings are missing or invalid:\n\n"
    )
    for i, err in enumerate(errors, 1):
        error_msg += f"  {i}. {err}\n\n"

    error_msg += (
        "=" * 60 + "\n"
        "APPLICATION CANNOT START IN PRODUCTION WITHOUT THESE SETTINGS\n"
        "=" * 60 + "\n"
    )

    logger.critical(error_msg)

    if exit_on_failure:
        print(error_msg, file=sys.stderr)
        sys.exit(1)
    else:
        raise StartupSecurityError(error_msg)


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings instance.

    Returns:
        Settings: Cached settings loaded from environment.
    """
    return Settings()


def get_validated_settings(exit_on_failure: bool = True) -> Settings:
    """
    Get settings with security validation.

    This is the recommended way to get settings in production code.
    Call this once at application startup.

    Args:
        exit_on_failure: If True, exit process on validation failure

    Returns:
        Validated Settings instance
    """
    settings = get_settings()
    validate_startup_security(settings, exit_on_failure)
    return settings
