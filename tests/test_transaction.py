"""Tests for transaction management module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from database.transaction import (
    TransactionManager,
    NestedTransaction,
    transaction,
    read_only_session,
    transactional,
    TransactionContext,
)


class TestTransactionManager:
    """Tests for TransactionManager class."""

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

    def test_init_without_session(self):
        """Should initialize without a session."""
        tm = TransactionManager()
        assert tm._session is None
        assert tm._owns_session is True
        assert tm._is_active is False

    def test_init_with_session(self):
        """Should initialize with provided session."""
        mock_session = MagicMock(spec=AsyncSession)
        tm = TransactionManager(session=mock_session)
        assert tm._session is mock_session
        assert tm._owns_session is False

    @pytest.mark.asyncio
    async def test_begin_creates_session(self):
        """Begin should create a session if none provided."""
        tm = TransactionManager()
        session = await tm.begin()
        assert session is not None
        assert tm._is_active is True
        await tm.close()

    @pytest.mark.asyncio
    async def test_begin_raises_if_already_active(self):
        """Begin should raise if transaction already active."""
        tm = TransactionManager()
        await tm.begin()
        with pytest.raises(RuntimeError, match="Transaction already active"):
            await tm.begin()
        await tm.close()

    @pytest.mark.asyncio
    async def test_commit(self):
        """Commit should commit the session."""
        tm = TransactionManager()
        await tm.begin()
        await tm.commit()
        await tm.close()

    @pytest.mark.asyncio
    async def test_commit_raises_if_not_active(self):
        """Commit should raise if no active transaction."""
        tm = TransactionManager()
        with pytest.raises(RuntimeError, match="No active transaction"):
            await tm.commit()

    @pytest.mark.asyncio
    async def test_rollback(self):
        """Rollback should rollback the session."""
        tm = TransactionManager()
        await tm.begin()
        await tm.rollback()
        await tm.close()

    @pytest.mark.asyncio
    async def test_rollback_safe_if_not_active(self):
        """Rollback should be safe if no active transaction."""
        tm = TransactionManager()
        # Should not raise
        await tm.rollback()

    @pytest.mark.asyncio
    async def test_close_cleans_up(self):
        """Close should clean up resources."""
        tm = TransactionManager()
        await tm.begin()
        assert tm._is_active is True
        await tm.close()
        assert tm._is_active is False

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """Context manager should commit on success."""
        async with TransactionManager() as session:
            assert session is not None
        # No exception means success

    @pytest.mark.asyncio
    async def test_context_manager_rollback_on_error(self):
        """Context manager should rollback on error."""
        with pytest.raises(ValueError):
            async with TransactionManager() as session:
                raise ValueError("Test error")

    def test_session_property(self):
        """Session property should return the session."""
        mock_session = MagicMock(spec=AsyncSession)
        tm = TransactionManager(session=mock_session)
        assert tm.session is mock_session

    def test_is_active_property(self):
        """is_active property should return correct state."""
        tm = TransactionManager()
        assert tm.is_active is False


class TestNestedTransaction:
    """Tests for NestedTransaction class."""

    @pytest.mark.asyncio
    async def test_creates_savepoint(self):
        """Should create a savepoint on enter."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_savepoint = AsyncMock()
        mock_session.begin_nested = AsyncMock(return_value=mock_savepoint)

        async with NestedTransaction(mock_session) as session:
            assert session is mock_session
            mock_session.begin_nested.assert_called_once()

    @pytest.mark.asyncio
    async def test_commits_savepoint_on_success(self):
        """Should commit savepoint on successful exit."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_savepoint = AsyncMock()
        mock_session.begin_nested = AsyncMock(return_value=mock_savepoint)

        async with NestedTransaction(mock_session):
            pass

        mock_savepoint.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_savepoint_on_error(self):
        """Should rollback savepoint on error."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_savepoint = AsyncMock()
        mock_session.begin_nested = AsyncMock(return_value=mock_savepoint)

        with pytest.raises(ValueError):
            async with NestedTransaction(mock_session):
                raise ValueError("Test error")

        mock_savepoint.rollback.assert_called_once()


class TestTransactionContextManager:
    """Tests for transaction() context manager function."""

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
    async def test_yields_session(self):
        """Should yield an AsyncSession."""
        async with transaction() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        """Should commit on successful exit."""
        async with transaction() as session:
            pass
        # No exception means success

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self):
        """Should rollback on exception."""
        with pytest.raises(ValueError):
            async with transaction() as session:
                raise ValueError("Test error")


class TestReadOnlySession:
    """Tests for read_only_session() context manager."""

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
    async def test_yields_session(self):
        """Should yield an AsyncSession."""
        async with read_only_session() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_always_rollback(self):
        """Should always rollback, never commit."""
        async with read_only_session() as session:
            pass
        # Session is rolled back, not committed


class TestTransactionalDecorator:
    """Tests for @transactional decorator."""

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
    async def test_provides_session_if_not_given(self):
        """Should provide session if not given in kwargs."""
        @transactional
        async def my_func(value: int, session: AsyncSession = None) -> int:
            assert session is not None
            return value * 2

        result = await my_func(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_uses_provided_session(self):
        """Should use provided session if given."""
        mock_session = AsyncMock(spec=AsyncSession)

        @transactional
        async def my_func(value: int, session: AsyncSession = None) -> int:
            return value * 2

        result = await my_func(5, session=mock_session)
        assert result == 10

    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self):
        """Decorator should preserve function metadata."""
        @transactional
        async def my_documented_func(x: int) -> int:
            """This is my docstring."""
            return x

        assert my_documented_func.__name__ == "my_documented_func"
        assert "docstring" in my_documented_func.__doc__


class TestTransactionContext:
    """Tests for TransactionContext class."""

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

    def test_init(self):
        """Should initialize with no session."""
        ctx = TransactionContext()
        assert ctx._session is None
        assert ctx._transaction_manager is None

    @pytest.mark.asyncio
    async def test_get_session_creates_session(self):
        """get_session should create a session on first call."""
        ctx = TransactionContext()
        session = await ctx.get_session()
        assert session is not None
        assert ctx._session is not None
        await ctx.close()

    @pytest.mark.asyncio
    async def test_get_session_returns_same_session(self):
        """get_session should return same session on subsequent calls."""
        ctx = TransactionContext()
        session1 = await ctx.get_session()
        session2 = await ctx.get_session()
        assert session1 is session2
        await ctx.close()

    @pytest.mark.asyncio
    async def test_commit(self):
        """commit should commit the transaction."""
        ctx = TransactionContext()
        await ctx.get_session()
        await ctx.commit()
        await ctx.close()

    @pytest.mark.asyncio
    async def test_rollback(self):
        """rollback should rollback the transaction."""
        ctx = TransactionContext()
        await ctx.get_session()
        await ctx.rollback()
        await ctx.close()

    @pytest.mark.asyncio
    async def test_close_cleans_up(self):
        """close should clean up resources."""
        ctx = TransactionContext()
        await ctx.get_session()
        assert ctx._session is not None
        await ctx.close()
        assert ctx._session is None
        assert ctx._transaction_manager is None

    @pytest.mark.asyncio
    async def test_context_manager_commits_on_success(self):
        """Context manager should commit on success."""
        async with TransactionContext() as ctx:
            session = await ctx.get_session()
            assert session is not None

    @pytest.mark.asyncio
    async def test_context_manager_rollback_on_error(self):
        """Context manager should rollback on error."""
        with pytest.raises(ValueError):
            async with TransactionContext() as ctx:
                await ctx.get_session()
                raise ValueError("Test error")
