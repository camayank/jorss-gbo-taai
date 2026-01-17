"""Application settings using Pydantic Settings.

Centralized configuration for the tax platform.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for signing"
    )
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


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings instance.

    Returns:
        Settings: Cached settings loaded from environment.
    """
    return Settings()
