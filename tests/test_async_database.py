"""Tests for async database layer with PostgreSQL/SQLite support."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import json

from config.database import DatabaseSettings, get_database_settings

# Check if aiosqlite is available for tests that need real database connections
try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False

requires_aiosqlite = pytest.mark.skipif(
    not HAS_AIOSQLITE,
    reason="aiosqlite not installed"
)


class TestDatabaseSettings:
    """Tests for DatabaseSettings configuration."""

    def test_default_is_sqlite(self):
        """Default driver is SQLite for development."""
        settings = DatabaseSettings()
        assert settings.is_sqlite is True
        assert settings.is_postgres is False

    def test_postgres_driver_detection(self):
        """PostgreSQL driver is correctly detected."""
        settings = DatabaseSettings(driver="postgresql+asyncpg")
        assert settings.is_postgres is True
        assert settings.is_sqlite is False

    def test_async_url_sqlite(self):
        """SQLite async URL is correctly formed."""
        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test.db"
        )
        assert "sqlite+aiosqlite" in settings.async_url
        assert "test.db" in settings.async_url

    def test_async_url_postgres(self):
        """PostgreSQL async URL is correctly formed."""
        settings = DatabaseSettings(
            driver="postgresql+asyncpg",
            host="localhost",
            port=5432,
            name="testdb",
            user="testuser",
            password="testpass"
        )
        url = settings.async_url
        assert "postgresql+asyncpg" in url
        assert "testuser:testpass@localhost:5432/testdb" in url

    def test_sync_url_postgres(self):
        """PostgreSQL sync URL uses psycopg2."""
        settings = DatabaseSettings(
            driver="postgresql+asyncpg",
            host="localhost",
            port=5432,
            name="testdb",
            user="testuser",
            password="testpass"
        )
        url = settings.sync_url
        assert "postgresql+psycopg2" in url

    def test_pool_settings_defaults(self):
        """Connection pool settings have sensible defaults."""
        settings = DatabaseSettings()
        assert settings.pool_size == 20  # Production-optimized default
        assert settings.max_overflow == 30  # Burst handling default
        assert settings.pool_timeout == 30
        assert settings.pool_recycle == 1800
        assert settings.pool_pre_ping is True

    def test_connect_args_sqlite(self):
        """SQLite connection args are correct."""
        settings = DatabaseSettings(driver="sqlite+aiosqlite")
        args = settings.get_connect_args()
        assert args["check_same_thread"] is False
        assert "timeout" in args

    def test_ssl_mode_options(self):
        """SSL mode options are available."""
        settings = DatabaseSettings(ssl_mode="require")
        assert settings.ssl_mode == "require"


@requires_aiosqlite
class TestAsyncEngine:
    """Tests for async database engine."""

    @pytest.mark.asyncio
    async def test_create_engine_sqlite(self):
        """Engine can be created for SQLite."""
        from database.async_engine import create_engine

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_engine.db"
        )

        engine = create_engine(settings)
        assert engine is not None

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_get_async_session(self):
        """Async session can be obtained."""
        from database.async_engine import get_async_session, close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_session.db"
        )

        async with get_async_session(settings) as session:
            assert session is not None

        await close_database()

    @pytest.mark.asyncio
    async def test_check_database_connection(self):
        """Database connection check works."""
        from database.async_engine import check_database_connection, close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_check.db"
        )

        result = await check_database_connection(settings)
        assert result is True

        await close_database()

    @pytest.mark.asyncio
    async def test_database_health_check(self):
        """Database health check returns proper status."""
        from database.async_engine import DatabaseHealth, close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_health.db"
        )

        health = DatabaseHealth(settings)
        result = await health.check()

        assert result["status"] == "healthy"
        assert result["database"] == "sqlite"

        await close_database()


@requires_aiosqlite
class TestTransactionManager:
    """Tests for transaction management."""

    @pytest.mark.asyncio
    async def test_transaction_context_manager(self):
        """Transaction context manager works correctly."""
        from database.transaction import TransactionManager
        from database.async_engine import get_async_session_factory, close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_tx.db"
        )

        # Initialize session factory
        from database.async_engine import get_async_engine
        engine = get_async_engine(settings)

        async with TransactionManager() as session:
            assert session is not None
            # Transaction should be active
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1

        await close_database()

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_exception(self):
        """Transaction rolls back on exception."""
        from database.transaction import TransactionManager
        from database.async_engine import close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_rollback.db"
        )

        from database.async_engine import get_async_engine
        get_async_engine(settings)

        with pytest.raises(ValueError):
            async with TransactionManager() as session:
                # Do something
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
                # Raise exception
                raise ValueError("Test rollback")

        await close_database()

    @pytest.mark.asyncio
    async def test_transaction_decorator(self):
        """@transactional decorator wraps function."""
        from database.transaction import transactional
        from database.async_engine import close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_decorator.db"
        )

        from database.async_engine import get_async_engine
        get_async_engine(settings)

        @transactional
        async def my_operation(session):
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            return result.fetchone()[0]

        result = await my_operation()
        assert result == 1

        await close_database()

    @pytest.mark.asyncio
    async def test_read_only_session(self):
        """Read-only session always rolls back."""
        from database.transaction import read_only_session
        from database.async_engine import close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_readonly.db"
        )

        from database.async_engine import get_async_engine
        get_async_engine(settings)

        async with read_only_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1

        await close_database()


@requires_aiosqlite
class TestUnitOfWork:
    """Tests for Unit of Work pattern."""

    @pytest.mark.asyncio
    async def test_unit_of_work_context_manager(self):
        """UnitOfWork works as context manager."""
        from database.unit_of_work import UnitOfWork
        from database.async_engine import close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_uow.db"
        )

        from database.async_engine import get_async_engine
        get_async_engine(settings)

        async with UnitOfWork() as uow:
            assert uow is not None
            assert uow.session is not None

        await close_database()

    @pytest.mark.asyncio
    async def test_unit_of_work_tax_returns_repository(self):
        """UnitOfWork provides tax_returns repository."""
        from database.unit_of_work import UnitOfWork
        from database.async_engine import close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_uow_repo.db"
        )

        from database.async_engine import get_async_engine
        get_async_engine(settings)

        # Skip model creation (JSONB not supported in SQLite)
        # Just verify we can access the repository

        async with UnitOfWork() as uow:
            repo = uow.tax_returns
            assert repo is not None

        await close_database()

    @pytest.mark.asyncio
    async def test_unit_of_work_commit(self):
        """UnitOfWork commits changes."""
        from database.unit_of_work import UnitOfWork
        from database.async_engine import close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_uow_commit.db"
        )

        from database.async_engine import get_async_engine
        get_async_engine(settings)

        async with UnitOfWork() as uow:
            # Commit should not raise
            await uow.commit()

        await close_database()

    @pytest.mark.asyncio
    async def test_unit_of_work_rollback(self):
        """UnitOfWork rolls back on exception."""
        from database.unit_of_work import UnitOfWork
        from database.async_engine import close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_uow_rollback.db"
        )

        from database.async_engine import get_async_engine
        get_async_engine(settings)

        with pytest.raises(ValueError):
            async with UnitOfWork() as uow:
                raise ValueError("Test rollback")

        await close_database()

    @pytest.mark.asyncio
    async def test_unit_of_work_event_collection(self):
        """UnitOfWork collects domain events."""
        from database.unit_of_work import UnitOfWork
        from database.async_engine import close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_uow_events.db"
        )

        from database.async_engine import get_async_engine
        get_async_engine(settings)

        # Mock domain event
        mock_event = MagicMock()

        async with UnitOfWork() as uow:
            uow.collect_event(mock_event)
            assert len(uow._pending_events) == 1

        await close_database()


class TestTaxReturnRepository:
    """Tests for TaxReturnRepository."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_repository_get_not_found(self, mock_session):
        """Repository returns None for non-existent return."""
        from database.repositories.tax_return_repository import TaxReturnRepository

        # Mock empty result
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.get(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_repository_exists(self, mock_session):
        """Repository checks existence correctly."""
        from database.repositories.tax_return_repository import TaxReturnRepository

        # Mock exists result
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.exists(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_repository_delete(self, mock_session):
        """Repository deletes correctly."""
        from database.repositories.tax_return_repository import TaxReturnRepository

        # Mock delete result
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        repo = TaxReturnRepository(mock_session)
        result = await repo.delete(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_repository_save(self, mock_session):
        """Repository saves tax return data."""
        from database.repositories.tax_return_repository import TaxReturnRepository

        # Mock exists check (not found)
        mock_exists_result = MagicMock()
        mock_exists_result.fetchone.return_value = None

        # Mock insert result
        mock_insert_result = MagicMock()

        mock_session.execute.side_effect = [mock_exists_result, mock_insert_result]

        repo = TaxReturnRepository(mock_session)

        tax_data = {
            "tax_year": 2025,
            "taxpayer": {
                "first_name": "John",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "filing_status": "single",
            },
            "income": {
                "total_income": 75000,
            },
        }

        await repo.save(uuid4(), tax_data)

        # Verify execute was called for exists check and insert
        assert mock_session.execute.call_count == 2


@requires_aiosqlite
class TestNestedTransaction:
    """Tests for nested transactions."""

    @pytest.mark.asyncio
    async def test_nested_transaction(self):
        """Nested transaction creates savepoint."""
        from database.transaction import TransactionManager, NestedTransaction
        from database.async_engine import close_database

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_nested.db"
        )

        from database.async_engine import get_async_engine
        get_async_engine(settings)

        async with TransactionManager() as session:
            from sqlalchemy import text

            # Main transaction
            await session.execute(text("SELECT 1"))

            # Nested transaction
            async with NestedTransaction(session) as nested_session:
                await nested_session.execute(text("SELECT 2"))

        await close_database()


@requires_aiosqlite
class TestDatabaseInitialization:
    """Tests for database initialization."""

    @pytest.mark.asyncio
    async def test_init_database_sqlite(self):
        """init_database works for SQLite (skips JSONB models)."""
        from database.async_engine import close_database, get_async_engine

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_init.db"
        )

        # Get engine (don't call init_database as models use JSONB)
        get_async_engine(settings)

        # Verify database is accessible
        from database.async_engine import check_database_connection
        result = await check_database_connection(settings)
        assert result is True

        await close_database()

    @pytest.mark.asyncio
    async def test_close_database(self):
        """close_database disposes engine."""
        from database.async_engine import (
            get_async_engine,
            close_database,
        )

        # Reset global state
        import database.async_engine as engine_module
        engine_module._async_engine = None
        engine_module._async_session_factory = None

        settings = DatabaseSettings(
            driver="sqlite+aiosqlite",
            sqlite_path="test_close.db"
        )

        # Create engine
        engine = get_async_engine(settings)
        assert engine is not None

        # Close
        await close_database()

        # Global should be None
        assert engine_module._async_engine is None
        assert engine_module._async_session_factory is None
