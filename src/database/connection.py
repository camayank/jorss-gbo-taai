"""
Database Connection Module

Provides unified database session management for both sync and async contexts.
This module re-exports async sessions and provides sync session support.

Usage:
    # Async context (FastAPI async routes)
    async with get_async_session() as session:
        result = await session.execute(query)

    # Sync context (background tasks, CLI tools)
    with get_db_session() as session:
        result = session.execute(query)
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

# Re-export async session for backward compatibility
from database.async_engine import (
    get_async_session,
    get_async_engine,
    get_async_session_factory,
    check_database_connection,
    close_database,
    DatabaseHealth,
)

from config.database import DatabaseSettings, get_database_settings

logger = logging.getLogger(__name__)

# Global sync engine and session factory (lazy initialization)
_sync_engine = None
_sync_session_factory = None


def get_sync_engine(settings: Optional[DatabaseSettings] = None):
    """
    Get or create a synchronous SQLAlchemy engine.

    Args:
        settings: Database settings. If None, loads from environment.

    Returns:
        Engine: Synchronous SQLAlchemy engine.
    """
    global _sync_engine

    if _sync_engine is None:
        settings = settings or get_database_settings()

        logger.info(
            f"Creating sync database engine",
            extra={
                "driver": settings.driver,
                "database": settings.name if settings.is_postgres else str(settings.sqlite_path),
            }
        )

        # Pool configuration differs for SQLite vs PostgreSQL
        if settings.is_sqlite:
            pool_class = NullPool
            pool_kwargs = {}
        else:
            pool_class = QueuePool
            pool_kwargs = {
                "pool_size": settings.pool_size,
                "max_overflow": settings.max_overflow,
                "pool_timeout": settings.pool_timeout,
                "pool_recycle": settings.pool_recycle,
                "pool_pre_ping": settings.pool_pre_ping,
            }

        _sync_engine = create_engine(
            settings.sync_url,
            echo=settings.echo_sql,
            poolclass=pool_class,
            **pool_kwargs,
        )

    return _sync_engine


def get_sync_session_factory(
    settings: Optional[DatabaseSettings] = None
) -> sessionmaker:
    """
    Get or create the sync session factory.

    Args:
        settings: Optional database settings.

    Returns:
        sessionmaker: Factory for creating sync sessions.
    """
    global _sync_session_factory

    if _sync_session_factory is None:
        engine = get_sync_engine(settings)
        _sync_session_factory = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    return _sync_session_factory


@contextmanager
def get_db_session(
    settings: Optional[DatabaseSettings] = None
) -> Generator[Session, None, None]:
    """
    Get a synchronous database session as a context manager.

    Usage:
        with get_db_session() as session:
            result = session.execute(query)
            session.add(new_record)

    Args:
        settings: Optional database settings.

    Yields:
        Session: SQLAlchemy session that auto-commits on success, rollbacks on error.
    """
    session_factory = get_sync_session_factory(settings)
    session = session_factory()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_sync_engine() -> None:
    """
    Close the sync database engine and cleanup connections.

    Should be called during application shutdown.
    """
    global _sync_engine, _sync_session_factory

    if _sync_engine is not None:
        logger.info("Closing sync database engine")
        _sync_engine.dispose()
        _sync_engine = None
        _sync_session_factory = None
        logger.info("Sync database engine closed")


# Convenience aliases for FastAPI dependency injection
def get_session():
    """FastAPI dependency for sync sessions."""
    with get_db_session() as session:
        yield session


async def get_session_async():
    """FastAPI dependency for async sessions."""
    async with get_async_session() as session:
        yield session
