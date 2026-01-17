"""Transaction management for async database operations.

Provides context managers for handling database transactions with
proper commit/rollback semantics and nested transaction support.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Any, Callable, TypeVar
from functools import wraps

from sqlalchemy.ext.asyncio import AsyncSession

from database.async_engine import get_async_session_factory

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TransactionManager:
    """
    Manages database transactions with automatic commit/rollback.

    Provides a clean interface for executing database operations within
    a transaction boundary. Supports nested transactions via savepoints.

    Usage:
        async with TransactionManager() as session:
            await session.execute(...)
            # Auto-commits on success, auto-rollbacks on exception

        # Or with explicit transaction control:
        tm = TransactionManager()
        session = await tm.begin()
        try:
            await session.execute(...)
            await tm.commit()
        except:
            await tm.rollback()
            raise
        finally:
            await tm.close()
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        """
        Initialize transaction manager.

        Args:
            session: Optional existing session to use.
        """
        self._session: Optional[AsyncSession] = session
        self._owns_session: bool = session is None
        self._is_active: bool = False

    async def begin(self) -> AsyncSession:
        """
        Begin a new transaction.

        Returns:
            AsyncSession: The database session for this transaction.
        """
        if self._is_active:
            raise RuntimeError("Transaction already active")

        if self._session is None:
            session_factory = get_async_session_factory()
            self._session = session_factory()
            self._owns_session = True

        self._is_active = True
        logger.debug("Transaction started")
        return self._session

    async def commit(self) -> None:
        """Commit the current transaction."""
        if not self._is_active:
            raise RuntimeError("No active transaction to commit")

        if self._session is not None:
            await self._session.commit()
            logger.debug("Transaction committed")

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        if not self._is_active:
            return  # No-op if not active

        if self._session is not None:
            await self._session.rollback()
            logger.debug("Transaction rolled back")

    async def close(self) -> None:
        """Close the session if we own it."""
        self._is_active = False

        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
            logger.debug("Transaction session closed")

    @property
    def session(self) -> Optional[AsyncSession]:
        """Get the current session."""
        return self._session

    @property
    def is_active(self) -> bool:
        """Check if a transaction is active."""
        return self._is_active

    async def __aenter__(self) -> AsyncSession:
        """Enter the transaction context."""
        return await self.begin()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the transaction context with auto commit/rollback."""
        try:
            if exc_type is not None:
                await self.rollback()
                logger.debug(f"Transaction rolled back due to: {exc_type.__name__}")
            else:
                await self.commit()
        finally:
            await self.close()

        # Don't suppress exceptions
        return False


class NestedTransaction:
    """
    Manages nested transactions using savepoints.

    Allows for nested transaction boundaries within a parent transaction.
    Uses database savepoints for proper isolation.

    Usage:
        async with TransactionManager() as session:
            # Main transaction
            await session.execute(...)

            async with NestedTransaction(session) as nested:
                # Nested transaction (savepoint)
                await nested.execute(...)
                # If exception here, only this nested part rolls back
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize nested transaction.

        Args:
            session: Parent session to create savepoint in.
        """
        self._session = session
        self._savepoint = None

    async def __aenter__(self) -> AsyncSession:
        """Enter nested transaction (create savepoint)."""
        self._savepoint = await self._session.begin_nested()
        logger.debug("Nested transaction (savepoint) started")
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit nested transaction with savepoint commit/rollback."""
        if exc_type is not None:
            await self._savepoint.rollback()
            logger.debug(f"Nested transaction rolled back: {exc_type.__name__}")
        else:
            await self._savepoint.commit()
            logger.debug("Nested transaction committed")

        return False


@asynccontextmanager
async def transaction(
    session: Optional[AsyncSession] = None
) -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database transactions.

    A simpler alternative to TransactionManager for one-off transactions.

    Usage:
        async with transaction() as session:
            await session.execute(...)

    Args:
        session: Optional existing session to use.

    Yields:
        AsyncSession: Database session with transaction.
    """
    tm = TransactionManager(session)
    try:
        yield await tm.begin()
        await tm.commit()
    except Exception:
        await tm.rollback()
        raise
    finally:
        await tm.close()


@asynccontextmanager
async def read_only_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for read-only database operations.

    Creates a session that will always rollback, suitable for
    read-only queries where no changes should be persisted.

    Usage:
        async with read_only_session() as session:
            result = await session.execute(select(Model))
            # Session will rollback at the end (no changes persisted)

    Yields:
        AsyncSession: Read-only database session.
    """
    session_factory = get_async_session_factory()
    session = session_factory()

    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


def transactional(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to wrap an async function in a transaction.

    The decorated function will receive a 'session' keyword argument
    if not already provided.

    Usage:
        @transactional
        async def create_user(name: str, session: AsyncSession) -> User:
            user = User(name=name)
            session.add(user)
            return user

        # Call without session - decorator provides one
        user = await create_user("Alice")

        # Or provide your own session
        async with transaction() as session:
            user = await create_user("Bob", session=session)

    Args:
        func: Async function to wrap.

    Returns:
        Wrapped function with transaction support.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        # Check if session was provided
        if "session" in kwargs and kwargs["session"] is not None:
            # Use provided session
            return await func(*args, **kwargs)

        # Create new transaction
        async with transaction() as session:
            kwargs["session"] = session
            return await func(*args, **kwargs)

    return wrapper


class TransactionContext:
    """
    Stores transaction context for request-scoped sessions.

    Useful for maintaining a single session across multiple
    operations within a single request/task.
    """

    def __init__(self):
        self._session: Optional[AsyncSession] = None
        self._transaction_manager: Optional[TransactionManager] = None

    async def get_session(self) -> AsyncSession:
        """
        Get or create the request-scoped session.

        Returns:
            AsyncSession: The session for this context.
        """
        if self._session is None:
            self._transaction_manager = TransactionManager()
            self._session = await self._transaction_manager.begin()
        return self._session

    async def commit(self) -> None:
        """Commit the context's transaction."""
        if self._transaction_manager:
            await self._transaction_manager.commit()

    async def rollback(self) -> None:
        """Rollback the context's transaction."""
        if self._transaction_manager:
            await self._transaction_manager.rollback()

    async def close(self) -> None:
        """Close the context's session."""
        if self._transaction_manager:
            await self._transaction_manager.close()
            self._session = None
            self._transaction_manager = None

    async def __aenter__(self) -> "TransactionContext":
        """Enter the context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the context with commit/rollback."""
        try:
            if exc_type is not None:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self.close()
        return False
