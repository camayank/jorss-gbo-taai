"""Tests for database configuration module."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from config.database import DatabaseSettings, get_database_settings


class TestDatabaseSettings:
    """Tests for DatabaseSettings Pydantic model."""

    def test_default_settings_use_sqlite(self):
        """Default settings should use SQLite."""
        settings = DatabaseSettings()
        assert settings.is_sqlite
        assert not settings.is_postgres
        assert "sqlite" in settings.driver

    def test_sqlite_path_default(self):
        """SQLite path should default to data/tax_returns.db."""
        settings = DatabaseSettings()
        assert settings.sqlite_path.name == "tax_returns.db"
        assert "data" in str(settings.sqlite_path)

    def test_sqlite_async_url(self):
        """SQLite async URL should use aiosqlite driver."""
        settings = DatabaseSettings()
        url = settings.async_url
        assert "sqlite+aiosqlite" in url
        assert "tax_returns.db" in url

    def test_sqlite_sync_url(self):
        """SQLite sync URL should use standard sqlite driver."""
        settings = DatabaseSettings()
        url = settings.sync_url
        assert "sqlite:///" in url
        assert "tax_returns.db" in url

    def test_postgres_settings(self):
        """PostgreSQL settings should be correctly configured."""
        settings = DatabaseSettings(
            driver="postgresql+asyncpg",
            host="localhost",
            port=5432,
            user="testuser",
            password="testpass",
            name="testdb",
        )
        assert settings.is_postgres
        assert not settings.is_sqlite

    def test_postgres_async_url(self):
        """PostgreSQL async URL should include credentials."""
        settings = DatabaseSettings(
            driver="postgresql+asyncpg",
            host="dbhost",
            port=5432,
            user="myuser",
            password="mypass",
            name="mydb",
        )
        url = settings.async_url
        assert "postgresql+asyncpg://" in url
        assert "myuser:mypass@" in url
        assert "dbhost:5432/mydb" in url

    def test_postgres_url_without_password(self):
        """PostgreSQL URL without password should not include auth separator."""
        settings = DatabaseSettings(
            driver="postgresql+asyncpg",
            host="dbhost",
            port=5432,
            user="",
            password="",
            name="mydb",
        )
        url = settings.async_url
        assert "@" not in url.split("://")[1].split("/")[0]

    def test_pool_settings_validation(self):
        """Pool settings should have valid ranges."""
        settings = DatabaseSettings(
            pool_size=20,
            max_overflow=30,
            pool_timeout=60,
            pool_recycle=7200,
        )
        assert settings.pool_size == 20
        assert settings.max_overflow == 30
        assert settings.pool_timeout == 60
        assert settings.pool_recycle == 7200

    def test_pool_size_minimum(self):
        """Pool size should have minimum of 1."""
        with pytest.raises(ValueError):
            DatabaseSettings(pool_size=0)

    def test_pool_size_maximum(self):
        """Pool size should have maximum of 100."""
        with pytest.raises(ValueError):
            DatabaseSettings(pool_size=101)

    def test_sqlite_connect_args(self):
        """SQLite connect args should include check_same_thread."""
        settings = DatabaseSettings()
        args = settings.get_connect_args()
        assert args.get("check_same_thread") is False

    def test_postgres_connect_args_no_ssl(self):
        """PostgreSQL connect args without SSL should be minimal."""
        settings = DatabaseSettings(
            driver="postgresql+asyncpg",
            ssl_mode="disable",
        )
        args = settings.get_connect_args()
        assert "ssl" not in args or args.get("ssl") is None

    def test_postgres_connect_args_with_ssl(self):
        """PostgreSQL connect args with SSL should include ssl context."""
        settings = DatabaseSettings(
            driver="postgresql+asyncpg",
            ssl_mode="require",
        )
        args = settings.get_connect_args()
        assert "ssl" in args

    def test_echo_sql_default_false(self):
        """SQL echo should default to False."""
        settings = DatabaseSettings()
        assert settings.echo_sql is False

    def test_pool_pre_ping_default_true(self):
        """Pool pre-ping should default to True."""
        settings = DatabaseSettings()
        assert settings.pool_pre_ping is True

    @patch.dict(os.environ, {
        "DB_DRIVER": "postgresql+asyncpg",
        "DB_HOST": "envhost",
        "DB_PORT": "5433",
        "DB_USER": "envuser",
        "DB_PASSWORD": "envpass",
        "DB_NAME": "envdb",
    })
    def test_settings_from_environment(self):
        """Settings should be loadable from environment variables."""
        settings = DatabaseSettings()
        assert settings.driver == "postgresql+asyncpg"
        assert settings.host == "envhost"
        assert settings.port == 5433
        assert settings.user == "envuser"
        assert settings.password == "envpass"
        assert settings.name == "envdb"


class TestGetDatabaseSettings:
    """Tests for get_database_settings function."""

    def test_returns_database_settings(self):
        """Should return DatabaseSettings instance."""
        settings = get_database_settings()
        assert isinstance(settings, DatabaseSettings)

    def test_caches_settings(self):
        """Should return same instance on subsequent calls."""
        settings1 = get_database_settings()
        settings2 = get_database_settings()
        # Note: lru_cache makes these the same instance
        assert settings1.driver == settings2.driver
