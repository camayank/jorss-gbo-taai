"""Async database engine with connection pooling.

Provides async SQLAlchemy engine configuration for PostgreSQL (production)
and SQLite (development). Includes connection pooling, health checks,
and proper session management.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import event, text

from config.database import DatabaseSettings, get_database_settings

logger = logging.getLogger(__name__)


# Global engine instance (lazy initialization)
_async_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def create_engine(settings: Optional[DatabaseSettings] = None) -> AsyncEngine:
    """
    Create an async SQLAlchemy engine with connection pooling.

    Args:
        settings: Database settings. If None, loads from environment.

    Returns:
        AsyncEngine: Configured async engine instance.
    """
    settings = settings or get_database_settings()

    logger.info(
        f"Creating async database engine",
        extra={
            "driver": settings.driver,
            "database": settings.name if settings.is_postgres else str(settings.sqlite_path),
            "pool_size": settings.pool_size,
        }
    )

    # Pool configuration differs for SQLite vs PostgreSQL
    if settings.is_sqlite:
        # SQLite doesn't support connection pooling in the traditional sense
        pool_class = NullPool
        pool_kwargs = {}
    else:
        # PostgreSQL uses QueuePool for connection pooling
        pool_class = QueuePool
        pool_kwargs = {
            "pool_size": settings.pool_size,
            "max_overflow": settings.max_overflow,
            "pool_timeout": settings.pool_timeout,
            "pool_recycle": settings.pool_recycle,
            "pool_pre_ping": settings.pool_pre_ping,
        }

    engine = create_async_engine(
        settings.async_url,
        echo=settings.echo_sql,
        poolclass=pool_class,
        connect_args=settings.get_connect_args(),
        **pool_kwargs,
    )

    # Register engine event listeners
    _setup_engine_events(engine, settings)

    return engine


def _setup_engine_events(engine: AsyncEngine, settings: DatabaseSettings) -> None:
    """
    Set up SQLAlchemy engine event listeners.

    Args:
        engine: The async engine instance.
        settings: Database settings.
    """
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "connect")
    def on_connect(dbapi_connection, connection_record):
        """Called when a new connection is established."""
        logger.debug("Database connection established")

        # SQLite-specific optimizations
        if settings.is_sqlite:
            cursor = dbapi_connection.cursor()
            # Enable foreign key support
            cursor.execute("PRAGMA foreign_keys=ON")
            # WAL mode for better concurrent access
            cursor.execute("PRAGMA journal_mode=WAL")
            # Improve write performance
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    @event.listens_for(sync_engine, "checkout")
    def on_checkout(dbapi_connection, connection_record, connection_proxy):
        """Called when a connection is retrieved from the pool."""
        logger.debug("Database connection checked out from pool")

    @event.listens_for(sync_engine, "checkin")
    def on_checkin(dbapi_connection, connection_record):
        """Called when a connection is returned to the pool."""
        logger.debug("Database connection returned to pool")


def get_session_factory(
    engine: Optional[AsyncEngine] = None,
    settings: Optional[DatabaseSettings] = None
) -> async_sessionmaker[AsyncSession]:
    """
    Create or get an async session factory.

    Args:
        engine: Optional engine instance.
        settings: Optional database settings.

    Returns:
        async_sessionmaker: Factory for creating async sessions.
    """
    engine = engine or get_async_engine(settings)

    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


def get_async_engine(settings: Optional[DatabaseSettings] = None) -> AsyncEngine:
    """
    Get or create the global async engine instance.

    This uses lazy initialization to create the engine on first use.

    Args:
        settings: Optional database settings.

    Returns:
        AsyncEngine: The global async engine instance.
    """
    global _async_engine

    if _async_engine is None:
        _async_engine = create_engine(settings)

    return _async_engine


def get_async_session_factory(
    settings: Optional[DatabaseSettings] = None
) -> async_sessionmaker[AsyncSession]:
    """
    Get or create the global async session factory.

    Args:
        settings: Optional database settings.

    Returns:
        async_sessionmaker: The global session factory.
    """
    global _async_session_factory

    if _async_session_factory is None:
        _async_session_factory = get_session_factory(
            get_async_engine(settings),
            settings
        )

    return _async_session_factory


@asynccontextmanager
async def get_async_session(
    settings: Optional[DatabaseSettings] = None
) -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session as a context manager.

    Usage:
        async with get_async_session() as session:
            result = await session.execute(query)

    Args:
        settings: Optional database settings.

    Yields:
        AsyncSession: Database session that auto-commits/rollbacks.
    """
    session_factory = get_async_session_factory(settings)
    session = session_factory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_database_connection(
    settings: Optional[DatabaseSettings] = None
) -> bool:
    """
    Check if the database is accessible.

    Args:
        settings: Optional database settings.

    Returns:
        bool: True if database is accessible, False otherwise.
    """
    try:
        engine = get_async_engine(settings)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection check passed")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def init_database(settings: Optional[DatabaseSettings] = None) -> None:
    """
    Initialize the database (create tables if needed for SQLite).

    For PostgreSQL, use Alembic migrations instead.

    Args:
        settings: Optional database settings.
    """
    settings = settings or get_database_settings()

    if settings.is_sqlite:
        logger.info("Initializing SQLite database")
        engine = get_async_engine(settings)

        # Import models to ensure they're registered
        from database.models import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("SQLite database initialized")
    else:
        logger.info("PostgreSQL detected - use Alembic migrations for schema management")


async def close_database() -> None:
    """
    Close the database engine and cleanup connections.

    Should be called during application shutdown.
    """
    global _async_engine, _async_session_factory

    if _async_engine is not None:
        logger.info("Closing database engine")
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None
        logger.info("Database engine closed")


class DatabaseHealth:
    """Database health check utility."""

    def __init__(self, settings: Optional[DatabaseSettings] = None):
        self.settings = settings or get_database_settings()

    async def check(self) -> dict:
        """
        Perform a database health check.

        Returns:
            dict: Health check result with status and details.
        """
        try:
            engine = get_async_engine(self.settings)

            async with engine.connect() as conn:
                # Run a simple query
                result = await conn.execute(text("SELECT 1"))
                result.fetchone()

            # Get pool statistics (PostgreSQL only)
            pool_stats = {}
            if self.settings.is_postgres:
                pool = engine.pool
                pool_stats = {
                    "pool_size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                }

            return {
                "status": "healthy",
                "database": self.settings.name if self.settings.is_postgres else "sqlite",
                "driver": self.settings.driver,
                "pool": pool_stats,
            }

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }
