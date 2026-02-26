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


class EmailSettings(BaseSettings):
    """
    Email delivery configuration.

    SPEC-012 Critical Gap Fix: Production email configuration.

    Supports three providers (in priority order):
    1. SendGrid - Set SENDGRID_API_KEY
    2. AWS SES - Set AWS_SES_REGION (and AWS credentials)
    3. SMTP - Set SMTP_HOST

    If no provider is configured, emails are logged but not sent.
    """

    model_config = SettingsConfigDict(
        extra="ignore",
    )

    # SendGrid configuration (recommended for production)
    sendgrid_api_key: Optional[str] = Field(
        default=None,
        description="SendGrid API key for email delivery",
        json_schema_extra={"env": "SENDGRID_API_KEY"},
    )
    sendgrid_from_email: str = Field(
        default="noreply@example.com",
        description="Default sender email for SendGrid",
        json_schema_extra={"env": "SENDGRID_FROM_EMAIL"},
    )
    sendgrid_from_name: str = Field(
        default="Tax Filing Platform",
        description="Default sender name for SendGrid",
        json_schema_extra={"env": "SENDGRID_FROM_NAME"},
    )

    # AWS SES configuration (for AWS infrastructure)
    aws_ses_region: Optional[str] = Field(
        default=None,
        description="AWS region for SES (e.g., us-east-1)",
        json_schema_extra={"env": "AWS_SES_REGION"},
    )
    aws_ses_from_email: str = Field(
        default="noreply@example.com",
        description="Default sender email for SES (must be verified)",
        json_schema_extra={"env": "AWS_SES_FROM_EMAIL"},
    )

    # SMTP configuration (for self-hosted/testing)
    smtp_host: Optional[str] = Field(
        default=None,
        description="SMTP server hostname",
        json_schema_extra={"env": "SMTP_HOST"},
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port",
        json_schema_extra={"env": "SMTP_PORT"},
    )
    smtp_username: Optional[str] = Field(
        default=None,
        description="SMTP authentication username",
        json_schema_extra={"env": "SMTP_USERNAME"},
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="SMTP authentication password",
        json_schema_extra={"env": "SMTP_PASSWORD"},
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use STARTTLS for SMTP",
        json_schema_extra={"env": "SMTP_USE_TLS"},
    )
    smtp_from_email: str = Field(
        default="noreply@example.com",
        description="Default sender email for SMTP",
        json_schema_extra={"env": "SMTP_FROM_EMAIL"},
    )

    @property
    def provider(self) -> str:
        """Get the configured email provider name."""
        if self.sendgrid_api_key:
            return "sendgrid"
        elif self.aws_ses_region:
            return "ses"
        elif self.smtp_host:
            return "smtp"
        return "null"

    @property
    def is_configured(self) -> bool:
        """Check if any email provider is configured."""
        return self.provider != "null"


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
    secret_key: Optional[str] = Field(
        default=None,
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

    # Nested settings (cached to avoid creating new instances on every access)
    _redis_cached: Optional[RedisSettings] = None
    _celery_cached: Optional[CelerySettings] = None
    _resilience_cached: Optional[ResilienceSettings] = None
    _email_cached: Optional[EmailSettings] = None

    @property
    def redis(self) -> RedisSettings:
        if self._redis_cached is None:
            object.__setattr__(self, "_redis_cached", RedisSettings())
        return self._redis_cached

    @property
    def celery(self) -> CelerySettings:
        if self._celery_cached is None:
            object.__setattr__(self, "_celery_cached", CelerySettings())
        return self._celery_cached

    @property
    def resilience(self) -> ResilienceSettings:
        if self._resilience_cached is None:
            object.__setattr__(self, "_resilience_cached", ResilienceSettings())
        return self._resilience_cached

    @property
    def email(self) -> EmailSettings:
        if self._email_cached is None:
            object.__setattr__(self, "_email_cached", EmailSettings())
        return self._email_cached

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
        if not self.secret_key:
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

        # Check SSN_HASH_SECRET (Phase 1 Security Fix: HMAC-SHA256 for SSN hashing)
        ssn_hash_secret = os.environ.get("SSN_HASH_SECRET")
        if not ssn_hash_secret:
            errors.append(
                "SSN_HASH_SECRET: Required in production for secure SSN hashing. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        elif len(ssn_hash_secret) < 32:
            errors.append("SSN_HASH_SECRET: Must be at least 32 characters")

        # Check HTTPS enforcement — hard requirement for production
        if not self.enforce_https:
            errors.append(
                "APP_ENFORCE_HTTPS: MUST be True in production — cannot serve over plain HTTP"
            )

        # Check email configuration (warning only, not blocking)
        email_settings = self.email
        if not email_settings.is_configured:
            logger.warning(
                "EMAIL: No email provider configured. Set SENDGRID_API_KEY, "
                "AWS_SES_REGION, or SMTP_HOST to enable email notifications."
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
