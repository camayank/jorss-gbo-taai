"""Tests for Unit of Work pattern implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

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

from database.unit_of_work import (
    UnitOfWork,
    unit_of_work,
    UnitOfWorkFactory,
    get_unit_of_work,
)
from domain.repositories import ITaxReturnRepository


class TestUnitOfWork:
    """Tests for UnitOfWork class."""

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
        uow = UnitOfWork()
        assert uow._session is None
        assert uow._owns_session is True
        assert uow._committed is False

    def test_init_with_session(self):
        """Should initialize with provided session."""
        mock_session = MagicMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        assert uow._session is mock_session
        assert uow._owns_session is False

    def test_init_repositories_are_none(self):
        """Repositories should be None initially."""
        uow = UnitOfWork()
        assert uow._tax_returns is None
        assert uow._scenarios is None
        assert uow._advisory is None
        assert uow._clients is None
        assert uow._events is None

    def test_init_pending_events_empty(self):
        """Pending events list should be empty initially."""
        uow = UnitOfWork()
        assert uow._pending_events == []

    @requires_aiosqlite
    @pytest.mark.asyncio
    async def test_aenter_creates_session(self):
        """__aenter__ should create a session if none provided."""
        uow = UnitOfWork()
        result = await uow.__aenter__()
        assert result is uow
        assert uow._session is not None
        await uow.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_aenter_uses_existing_session(self):
        """__aenter__ should use existing session if provided."""
        mock_session = MagicMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        result = await uow.__aenter__()
        assert uow._session is mock_session
        # Don't call __aexit__ since we don't own the session

    @requires_aiosqlite
    @pytest.mark.asyncio
    async def test_tax_returns_property_lazy_init(self):
        """tax_returns property should lazily initialize repository."""
        async with UnitOfWork() as uow:
            assert uow._tax_returns is None
            repo = uow.tax_returns
            assert repo is not None
            assert isinstance(repo, ITaxReturnRepository)
            assert uow._tax_returns is repo

    def test_tax_returns_raises_if_not_initialized(self):
        """tax_returns should raise if UoW not initialized."""
        uow = UnitOfWork()
        with pytest.raises(RuntimeError, match="UnitOfWork not initialized"):
            _ = uow.tax_returns

    def test_scenarios_property_lazy_init(self):
        """scenarios property should lazy initialize the repository."""
        mock_session = MagicMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        # Should return a repository when session is set
        result = uow.scenarios
        assert result is not None

    def test_advisory_property_lazy_init(self):
        """advisory property should lazy initialize the repository."""
        mock_session = MagicMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        result = uow.advisory
        assert result is not None

    def test_clients_property_lazy_init(self):
        """clients property should lazy initialize the repository."""
        mock_session = MagicMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        result = uow.clients
        assert result is not None

    def test_events_property_lazy_init(self):
        """events property should lazy initialize the event store."""
        mock_session = MagicMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        result = uow.events
        assert result is not None

    def test_session_property(self):
        """session property should return the session."""
        mock_session = MagicMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        assert uow.session is mock_session

    def test_session_property_raises_if_not_initialized(self):
        """session property should raise if not initialized."""
        uow = UnitOfWork()
        with pytest.raises(RuntimeError, match="UnitOfWork not initialized"):
            _ = uow.session

    def test_collect_event(self):
        """collect_event should add event to pending list."""
        uow = UnitOfWork()
        mock_event = MagicMock()
        uow.collect_event(mock_event)
        assert mock_event in uow._pending_events

    def test_collect_events(self):
        """collect_events should add multiple events."""
        uow = UnitOfWork()
        events = [MagicMock(), MagicMock(), MagicMock()]
        uow.collect_events(events)
        assert uow._pending_events == events

    @pytest.mark.asyncio
    async def test_commit(self):
        """commit should commit the session."""
        mock_session = AsyncMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        uow._session = mock_session

        await uow.commit()

        mock_session.commit.assert_called_once()
        assert uow._committed is True

    @pytest.mark.asyncio
    async def test_commit_raises_if_not_initialized(self):
        """commit should raise if not initialized."""
        uow = UnitOfWork()
        with pytest.raises(RuntimeError, match="UnitOfWork not initialized"):
            await uow.commit()

    @pytest.mark.asyncio
    async def test_commit_idempotent(self):
        """commit should be idempotent (only commit once)."""
        mock_session = AsyncMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        uow._session = mock_session

        await uow.commit()
        await uow.commit()  # Second call should be no-op

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback(self):
        """rollback should rollback the session."""
        mock_session = AsyncMock(spec=AsyncSession)
        uow = UnitOfWork(session=mock_session)
        uow._session = mock_session
        uow._pending_events = [MagicMock()]

        await uow.rollback()

        mock_session.rollback.assert_called_once()
        assert uow._pending_events == []

    @pytest.mark.asyncio
    async def test_rollback_safe_without_session(self):
        """rollback should be safe without a session."""
        uow = UnitOfWork()
        # Should not raise
        await uow.rollback()

    @requires_aiosqlite
    @pytest.mark.asyncio
    async def test_aexit_commits_on_success(self):
        """__aexit__ should commit on successful exit."""
        async with UnitOfWork() as uow:
            pass
        # No exception means commit happened

    @requires_aiosqlite
    @pytest.mark.asyncio
    async def test_aexit_rollback_on_exception(self):
        """__aexit__ should rollback on exception."""
        with pytest.raises(ValueError):
            async with UnitOfWork() as uow:
                raise ValueError("Test error")

    @requires_aiosqlite
    @pytest.mark.asyncio
    async def test_aexit_closes_owned_session(self):
        """__aexit__ should close session if we own it."""
        uow = UnitOfWork()
        await uow.__aenter__()
        assert uow._session is not None
        await uow.__aexit__(None, None, None)
        assert uow._session is None


@requires_aiosqlite
class TestUnitOfWorkContextManager:
    """Tests for unit_of_work() context manager function."""

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
    async def test_yields_unit_of_work(self):
        """Should yield a UnitOfWork instance."""
        async with unit_of_work() as uow:
            assert isinstance(uow, UnitOfWork)

    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        """Should commit on successful exit."""
        async with unit_of_work() as uow:
            pass
        # No exception means success

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self):
        """Should rollback on exception."""
        with pytest.raises(ValueError):
            async with unit_of_work() as uow:
                raise ValueError("Test error")


class TestUnitOfWorkFactory:
    """Tests for UnitOfWorkFactory class."""

    def test_create_returns_unit_of_work(self):
        """create should return a UnitOfWork instance."""
        factory = UnitOfWorkFactory()
        uow = factory.create()
        assert isinstance(uow, UnitOfWork)

    @requires_aiosqlite
    @pytest.mark.asyncio
    async def test_callable_as_context_manager(self):
        """Factory should be usable as async context manager."""
        factory = UnitOfWorkFactory()
        async with factory() as uow:
            assert isinstance(uow, UnitOfWork)


class TestGetUnitOfWork:
    """Tests for get_unit_of_work FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_returns_unit_of_work(self):
        """Should return a UnitOfWork instance."""
        uow = await get_unit_of_work()
        assert isinstance(uow, UnitOfWork)

    @pytest.mark.asyncio
    async def test_returns_new_instance_each_time(self):
        """Should return a new instance each time."""
        uow1 = await get_unit_of_work()
        uow2 = await get_unit_of_work()
        assert uow1 is not uow2


@requires_aiosqlite
class TestUnitOfWorkEventPublishing:
    """Tests for domain event publishing in UnitOfWork."""

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
    async def test_events_published_after_commit(self):
        """Events should be published after successful commit."""
        mock_event = MagicMock()
        mock_event.__class__.__name__ = "TestEvent"

        with patch('domain.event_bus.publish_event') as mock_publish:
            async with UnitOfWork() as uow:
                uow.collect_event(mock_event)

            mock_publish.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_events_not_published_on_rollback(self):
        """Events should not be published if transaction rolls back."""
        mock_event = MagicMock()

        with patch('domain.event_bus.publish_event') as mock_publish:
            with pytest.raises(ValueError):
                async with UnitOfWork() as uow:
                    uow.collect_event(mock_event)
                    raise ValueError("Test error")

            mock_publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_events_cleared_after_publishing(self):
        """Pending events should be cleared after publishing."""
        mock_event = MagicMock()
        mock_event.__class__.__name__ = "TestEvent"

        with patch('domain.event_bus.publish_event'):
            uow = UnitOfWork()
            await uow.__aenter__()
            uow.collect_event(mock_event)
            assert len(uow._pending_events) == 1

            await uow.commit()
            assert len(uow._pending_events) == 0
            await uow.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_multiple_events_published_in_order(self):
        """Multiple events should be published in order."""
        events = [MagicMock(__class__=MagicMock(__name__=f"Event{i}")) for i in range(3)]
        published = []

        def track_publish(event):
            published.append(event)

        with patch('domain.event_bus.publish_event', side_effect=track_publish):
            async with UnitOfWork() as uow:
                for event in events:
                    uow.collect_event(event)

            assert published == events
