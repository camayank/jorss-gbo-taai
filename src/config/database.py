"""Database configuration using Pydantic Settings.

Supports both PostgreSQL (production) and SQLite (development/testing).
Configuration is loaded from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import Optional
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """
    Database configuration settings.

    Supports PostgreSQL for production and SQLite for development.
    All settings can be overridden via environment variables with DB_ prefix.

    Example environment variables:
        DB_DRIVER=postgresql+asyncpg
        DB_HOST=localhost
        DB_PORT=5432
        DB_NAME=tax_platform
        DB_USER=taxuser
        DB_PASSWORD=secret
    """

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database driver: postgresql+asyncpg (production) or sqlite+aiosqlite (dev)
    driver: str = Field(
        default="sqlite+aiosqlite",
        description="Database driver (postgresql+asyncpg or sqlite+aiosqlite)"
    )

    # PostgreSQL settings
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="tax_platform", description="Database name")
    user: str = Field(default="", description="Database user")
    password: str = Field(default="", description="Database password")

    # SQLite settings (for development/testing)
    sqlite_path: Path = Field(
        default=Path("data/tax_returns.db"),
        description="Path to SQLite database file"
    )

    # Connection pool settings
    pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of connections to keep in the pool"
    )
    max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Max connections above pool_size"
    )
    pool_timeout: int = Field(
        default=30,
        ge=1,
        description="Seconds to wait for a connection from the pool"
    )
    pool_recycle: int = Field(
        default=1800,
        ge=60,
        description="Seconds after which a connection is recycled"
    )
    pool_pre_ping: bool = Field(
        default=True,
        description="Test connections before using them"
    )

    # SSL settings (PostgreSQL production)
    ssl_mode: str = Field(
        default="prefer",
        description="SSL mode: disable, allow, prefer, require, verify-ca, verify-full"
    )
    ssl_ca_cert: Optional[str] = Field(
        default=None,
        description="Path to CA certificate for SSL verification"
    )

    # Query settings
    echo_sql: bool = Field(
        default=False,
        description="Log all SQL statements (for debugging)"
    )
    query_timeout: int = Field(
        default=30,
        ge=1,
        description="Default query timeout in seconds"
    )

    @computed_field
    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite."""
        return "sqlite" in self.driver.lower()

    @computed_field
    @property
    def is_postgres(self) -> bool:
        """Check if using PostgreSQL."""
        return "postgresql" in self.driver.lower() or "postgres" in self.driver.lower()

    @computed_field
    @property
    def async_url(self) -> str:
        """
        Get the async database URL.

        Returns:
            Database URL for async connections.
        """
        if self.is_sqlite:
            # Ensure parent directory exists
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{self.sqlite_path.absolute()}"

        # PostgreSQL URL
        auth = ""
        if self.user:
            auth = f"{self.user}"
            if self.password:
                auth += f":{self.password}"
            auth += "@"

        return f"{self.driver}://{auth}{self.host}:{self.port}/{self.name}"

    @computed_field
    @property
    def sync_url(self) -> str:
        """
        Get the sync database URL (for Alembic migrations).

        Returns:
            Database URL for sync connections.
        """
        if self.is_sqlite:
            return f"sqlite:///{self.sqlite_path.absolute()}"

        # PostgreSQL sync URL (using psycopg2)
        auth = ""
        if self.user:
            auth = f"{self.user}"
            if self.password:
                auth += f":{self.password}"
            auth += "@"

        sync_driver = "postgresql+psycopg2"
        return f"{sync_driver}://{auth}{self.host}:{self.port}/{self.name}"

    def get_connect_args(self) -> dict:
        """
        Get database-specific connection arguments.

        Returns:
            Dictionary of connection arguments for SQLAlchemy.
        """
        if self.is_sqlite:
            return {
                "check_same_thread": False,
                "timeout": self.query_timeout,
            }

        # PostgreSQL connection arguments
        args = {
            "command_timeout": self.query_timeout,
        }

        # SSL configuration
        if self.ssl_mode != "disable":
            ssl_context = self._build_ssl_context()
            if ssl_context:
                args["ssl"] = ssl_context

        return args

    def _build_ssl_context(self):
        """Build SSL context for PostgreSQL connections."""
        import ssl

        if self.ssl_mode == "disable":
            return None

        if self.ssl_mode == "require":
            return ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        if self.ssl_mode in ("verify-ca", "verify-full"):
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            if self.ssl_ca_cert:
                context.load_verify_locations(self.ssl_ca_cert)
            if self.ssl_mode == "verify-full":
                context.check_hostname = True
            return context

        # prefer/allow - use default context without strict verification
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """
    Get cached database settings instance.

    Returns:
        DatabaseSettings: Cached settings loaded from environment.
    """
    return DatabaseSettings()
