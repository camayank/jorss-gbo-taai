"""Unit of Work Pattern Implementation.

Coordinates multiple repository operations as a single transaction.
Provides transactional guarantees across aggregate boundaries.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Type
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from domain.repositories import (
    IUnitOfWork,
    ITaxReturnRepository,
    IScenarioRepository,
    IAdvisoryRepository,
    IClientRepository,
    IEventStore,
)
from domain.events import DomainEvent
from database.async_engine import get_async_session_factory
from database.repositories.tax_return_repository import TaxReturnRepository

logger = logging.getLogger(__name__)


class UnitOfWork(IUnitOfWork):
    """
    Unit of Work implementation using SQLAlchemy async sessions.

    Coordinates multiple repository operations within a single database
    transaction. Automatically commits on success or rolls back on failure.

    Usage:
        async with UnitOfWork() as uow:
            await uow.tax_returns.save(return_id, data)
            await uow.commit()

    The context manager automatically handles:
    - Creating a database session
    - Beginning a transaction
    - Committing on clean exit
    - Rolling back on exception
    - Closing the session
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        """
        Initialize the unit of work.

        Args:
            session: Optional existing session. If None, creates a new one.
        """
        self._session: Optional[AsyncSession] = session
        self._owns_session: bool = session is None
        self._committed: bool = False

        # Lazy-initialized repositories
        self._tax_returns: Optional[TaxReturnRepository] = None
        self._scenarios: Optional[IScenarioRepository] = None
        self._advisory: Optional[IAdvisoryRepository] = None
        self._clients: Optional[IClientRepository] = None
        self._events: Optional[IEventStore] = None

        # Collected domain events
        self._pending_events: List[DomainEvent] = []

    @property
    def tax_returns(self) -> ITaxReturnRepository:
        """Get the tax return repository."""
        if self._tax_returns is None:
            if self._session is None:
                raise RuntimeError("UnitOfWork not initialized. Use 'async with' context.")
            self._tax_returns = TaxReturnRepository(self._session)
        return self._tax_returns

    @property
    def scenarios(self) -> IScenarioRepository:
        """Get the scenario repository."""
        if self._scenarios is None:
            # TODO: Implement ScenarioRepository
            raise NotImplementedError("ScenarioRepository not yet implemented")
        return self._scenarios

    @property
    def advisory(self) -> IAdvisoryRepository:
        """Get the advisory repository."""
        if self._advisory is None:
            # TODO: Implement AdvisoryRepository
            raise NotImplementedError("AdvisoryRepository not yet implemented")
        return self._advisory

    @property
    def clients(self) -> IClientRepository:
        """Get the client repository."""
        if self._clients is None:
            # TODO: Implement ClientRepository
            raise NotImplementedError("ClientRepository not yet implemented")
        return self._clients

    @property
    def events(self) -> IEventStore:
        """Get the event store."""
        if self._events is None:
            # TODO: Implement EventStore
            raise NotImplementedError("EventStore not yet implemented")
        return self._events

    @property
    def session(self) -> AsyncSession:
        """Get the underlying session."""
        if self._session is None:
            raise RuntimeError("UnitOfWork not initialized")
        return self._session

    def collect_event(self, event: DomainEvent) -> None:
        """
        Collect a domain event for publishing after commit.

        Args:
            event: Domain event to publish.
        """
        self._pending_events.append(event)

    def collect_events(self, events: List[DomainEvent]) -> None:
        """
        Collect multiple domain events.

        Args:
            events: List of domain events to publish.
        """
        self._pending_events.extend(events)

    async def commit(self) -> None:
        """
        Commit all changes.

        Flushes all pending operations to the database and commits
        the transaction. After commit, publishes collected domain events.
        """
        if self._session is None:
            raise RuntimeError("UnitOfWork not initialized")

        if self._committed:
            return

        await self._session.commit()
        self._committed = True
        logger.debug("UnitOfWork committed")

        # Publish events after successful commit
        await self._publish_events()

    async def rollback(self) -> None:
        """
        Rollback all changes.

        Discards all pending changes and clears collected events.
        """
        if self._session is None:
            return

        await self._session.rollback()
        self._pending_events.clear()
        logger.debug("UnitOfWork rolled back")

    async def _publish_events(self) -> None:
        """Publish collected domain events."""
        if not self._pending_events:
            return

        from domain.event_bus import publish_event

        for event in self._pending_events:
            try:
                publish_event(event)
            except Exception as e:
                logger.error(f"Failed to publish event {event.__class__.__name__}: {e}")

        self._pending_events.clear()

    async def __aenter__(self) -> "UnitOfWork":
        """Enter the async context."""
        if self._session is None:
            session_factory = get_async_session_factory()
            self._session = session_factory()
            self._owns_session = True

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit the async context.

        Commits if no exception, rolls back otherwise.
        Always closes the session if we own it.
        """
        try:
            if exc_type is not None:
                await self.rollback()
                logger.debug(f"UnitOfWork rolled back due to: {exc_type.__name__}")
            elif not self._committed:
                await self.commit()
        finally:
            if self._owns_session and self._session is not None:
                await self._session.close()
                self._session = None


@asynccontextmanager
async def unit_of_work():
    """
    Context manager for creating a unit of work.

    Usage:
        async with unit_of_work() as uow:
            await uow.tax_returns.save(return_id, data)
            # Auto-commits on clean exit

    Yields:
        UnitOfWork: A new unit of work instance.
    """
    async with UnitOfWork() as uow:
        yield uow


class UnitOfWorkFactory:
    """
    Factory for creating unit of work instances.

    Useful for dependency injection in services.
    """

    def create(self) -> UnitOfWork:
        """Create a new unit of work."""
        return UnitOfWork()

    @asynccontextmanager
    async def __call__(self):
        """Allow factory to be used as a context manager."""
        async with UnitOfWork() as uow:
            yield uow


# FastAPI dependency
async def get_unit_of_work() -> UnitOfWork:
    """
    FastAPI dependency for getting a unit of work.

    Usage in endpoints:
        @app.post("/api/returns")
        async def create_return(
            uow: UnitOfWork = Depends(get_unit_of_work)
        ):
            async with uow:
                ...

    Returns:
        UnitOfWork: A new unit of work instance.
    """
    return UnitOfWork()
