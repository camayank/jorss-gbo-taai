"""Tests for async database engine module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from config.database import DatabaseSettings


class TestCreateEngine:
    """Tests for create_engine function."""

    def test_creates_async_engine_with_sqlite(self):
        """Should create an AsyncEngine instance for SQLite."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import create_engine
                settings = DatabaseSettings()
                engine = create_engine(settings)

                assert mock_create.called
                assert engine is mock_engine

    def test_sqlite_uses_null_pool(self):
        """SQLite should use NullPool."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import create_engine
                from sqlalchemy.pool import NullPool

                settings = DatabaseSettings()
                create_engine(settings)

                call_kwargs = mock_create.call_args[1]
                assert call_kwargs['poolclass'] is NullPool

    def test_postgres_uses_queue_pool(self):
        """PostgreSQL should use QueuePool."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import create_engine
                from sqlalchemy.pool import QueuePool

                settings = DatabaseSettings(
                    driver="postgresql+asyncpg",
                    host="localhost",
                    port=5432,
                    name="testdb",
                )
                create_engine(settings)

                call_kwargs = mock_create.call_args[1]
                assert call_kwargs['poolclass'] is QueuePool

    def test_engine_url_matches_settings(self):
        """Engine URL should match settings."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import create_engine

                settings = DatabaseSettings()
                create_engine(settings)

                call_args = mock_create.call_args[0]
                assert "sqlite+aiosqlite" in call_args[0]

    def test_echo_sql_propagates(self):
        """Echo SQL setting should propagate to engine."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import create_engine

                settings = DatabaseSettings(echo_sql=True)
                create_engine(settings)

                call_kwargs = mock_create.call_args[1]
                assert call_kwargs['echo'] is True


class TestGetSessionFactory:
    """Tests for get_session_factory function."""

    def test_returns_session_maker(self):
        """Should return an async_sessionmaker."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            mock_engine = MagicMock()
            mock_engine.sync_engine = MagicMock()
            mock_create.return_value = mock_engine

            from database.async_engine import get_session_factory
            from sqlalchemy.ext.asyncio import async_sessionmaker

            settings = DatabaseSettings()
            factory = get_session_factory(mock_engine, settings)

            assert isinstance(factory, async_sessionmaker)

    def test_factory_bound_to_engine(self):
        """Factory should be bound to the engine."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            mock_engine = MagicMock()
            mock_engine.sync_engine = MagicMock()
            mock_create.return_value = mock_engine

            from database.async_engine import get_session_factory

            factory = get_session_factory(mock_engine)

            # Sessionmaker stores the bind in kw
            assert factory.kw.get('bind') is mock_engine

    def test_session_config(self):
        """Sessions should have correct config."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            mock_engine = MagicMock()
            mock_engine.sync_engine = MagicMock()
            mock_create.return_value = mock_engine

            from database.async_engine import get_session_factory

            factory = get_session_factory(mock_engine)

            # Check session factory configuration
            assert factory.kw.get('autoflush') is False
            assert factory.kw.get('autocommit') is False
            assert factory.kw.get('expire_on_commit') is False


class TestGetAsyncEngine:
    """Tests for get_async_engine function."""

    def setup_method(self):
        """Reset global state before each test."""
        import database.async_engine as module
        module._async_engine = None

    def teardown_method(self):
        """Clean up after each test."""
        import database.async_engine as module
        module._async_engine = None

    def test_returns_async_engine(self):
        """Should return an AsyncEngine."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import get_async_engine

                engine = get_async_engine()
                assert engine is mock_engine

    def test_lazy_initialization(self):
        """Engine should be lazily initialized."""
        import database.async_engine as module
        assert module._async_engine is None

        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import get_async_engine
                engine = get_async_engine()

                assert module._async_engine is not None
                assert module._async_engine is engine

    def test_returns_same_instance(self):
        """Should return the same engine instance."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import get_async_engine

                engine1 = get_async_engine()
                engine2 = get_async_engine()
                assert engine1 is engine2
                # Should only create once
                assert mock_create.call_count == 1


class TestGetAsyncSessionFactory:
    """Tests for get_async_session_factory function."""

    def setup_method(self):
        """Reset global state before each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    def teardown_method(self):
        """Clean up after each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    def test_returns_session_factory(self):
        """Should return an async_sessionmaker."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import get_async_session_factory
                from sqlalchemy.ext.asyncio import async_sessionmaker

                factory = get_async_session_factory()
                assert isinstance(factory, async_sessionmaker)

    def test_returns_same_instance(self):
        """Should return the same factory instance."""
        with patch('database.async_engine.create_async_engine') as mock_create:
            with patch('database.async_engine._setup_engine_events'):
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                from database.async_engine import get_async_session_factory

                factory1 = get_async_session_factory()
                factory2 = get_async_session_factory()
                assert factory1 is factory2


class TestGetAsyncSession:
    """Tests for get_async_session context manager."""

    def setup_method(self):
        """Reset global state before each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    def teardown_method(self):
        """Clean up after each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    @pytest.mark.asyncio
    async def test_yields_async_session(self):
        """Should yield an AsyncSession."""
        mock_session = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        with patch('database.async_engine.get_async_session_factory', return_value=mock_factory):
            from database.async_engine import get_async_session

            async with get_async_session() as session:
                assert session is mock_session

    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        """Should commit on successful exit."""
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        with patch('database.async_engine.get_async_session_factory', return_value=mock_factory):
            from database.async_engine import get_async_session

            async with get_async_session():
                pass

            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self):
        """Should rollback on exception."""
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        with patch('database.async_engine.get_async_session_factory', return_value=mock_factory):
            from database.async_engine import get_async_session

            with pytest.raises(ValueError):
                async with get_async_session():
                    raise ValueError("Test error")

            mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_closes_on_exit(self):
        """Session should be closed after context exit."""
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        with patch('database.async_engine.get_async_session_factory', return_value=mock_factory):
            from database.async_engine import get_async_session

            async with get_async_session():
                pass

            mock_session.close.assert_called_once()


class TestCheckDatabaseConnection:
    """Tests for check_database_connection function."""

    def setup_method(self):
        """Reset global state before each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    def teardown_method(self):
        """Clean up after each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    @pytest.mark.asyncio
    async def test_returns_true_for_healthy_db(self):
        """Should return True for healthy database."""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_connect():
            yield mock_conn

        mock_engine = MagicMock()
        mock_engine.connect = mock_connect

        with patch('database.async_engine.get_async_engine', return_value=mock_engine):
            from database.async_engine import check_database_connection

            result = await check_database_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_error(self):
        """Should return False on connection error."""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_connect():
            raise Exception("Connection failed")
            yield  # Never reached

        mock_engine = MagicMock()
        mock_engine.connect = mock_connect

        with patch('database.async_engine.get_async_engine', return_value=mock_engine):
            from database.async_engine import check_database_connection

            result = await check_database_connection()
            assert result is False


class TestInitDatabase:
    """Tests for init_database function."""

    def setup_method(self):
        """Reset global state before each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    def teardown_method(self):
        """Clean up after each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    @pytest.mark.asyncio
    async def test_initializes_sqlite_database(self):
        """Should initialize SQLite database without error."""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_begin():
            yield mock_conn

        mock_engine = MagicMock()
        mock_engine.begin = mock_begin

        with patch('database.async_engine.get_async_engine', return_value=mock_engine):
            with patch('database.async_engine.get_database_settings') as mock_settings:
                mock_settings.return_value = DatabaseSettings()

                from database.async_engine import init_database

                await init_database()

                # Verify create_all was attempted via run_sync
                mock_conn.run_sync.assert_called_once()


class TestCloseDatabase:
    """Tests for close_database function."""

    def setup_method(self):
        """Reset global state before each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    def teardown_method(self):
        """Clean up after each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    @pytest.mark.asyncio
    async def test_closes_engine(self):
        """Should close the engine and clear global state."""
        import database.async_engine as module

        mock_engine = AsyncMock()
        module._async_engine = mock_engine

        from database.async_engine import close_database

        await close_database()

        mock_engine.dispose.assert_called_once()
        assert module._async_engine is None
        assert module._async_session_factory is None

    @pytest.mark.asyncio
    async def test_safe_to_call_without_engine(self):
        """Should be safe to call when no engine exists."""
        import database.async_engine as module
        module._async_engine = None

        from database.async_engine import close_database

        # Should not raise
        await close_database()


class TestDatabaseHealth:
    """Tests for DatabaseHealth utility class."""

    def setup_method(self):
        """Reset global state before each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    def teardown_method(self):
        """Clean up after each test."""
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None

    @pytest.mark.asyncio
    async def test_check_returns_healthy_status(self):
        """Should return healthy status for working database."""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_connect():
            yield mock_conn

        mock_engine = MagicMock()
        mock_engine.connect = mock_connect

        with patch('database.async_engine.get_async_engine', return_value=mock_engine):
            from database.async_engine import DatabaseHealth

            health = DatabaseHealth()
            result = await health.check()

            assert result["status"] == "healthy"
            assert "database" in result

    @pytest.mark.asyncio
    async def test_check_returns_unhealthy_on_error(self):
        """Should return unhealthy status on connection error."""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_connect():
            raise Exception("Connection failed")
            yield  # Never reached

        mock_engine = MagicMock()
        mock_engine.connect = mock_connect

        with patch('database.async_engine.get_async_engine', return_value=mock_engine):
            from database.async_engine import DatabaseHealth

            health = DatabaseHealth()
            result = await health.check()

            assert result["status"] == "unhealthy"
            assert "error" in result
