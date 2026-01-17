"""Pytest configuration and fixtures for test suite."""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture(autouse=True)
def reset_database_globals():
    """Reset database module globals before each test."""
    yield
    # Clean up after test
    try:
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None
    except ImportError:
        pass


@pytest.fixture
def mock_async_session():
    """Provide a mock async session for testing."""
    from unittest.mock import AsyncMock
    return AsyncMock()


@pytest.fixture
def mock_redis_client():
    """Provide a mock Redis client for testing."""
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=True)
    client.exists = AsyncMock(return_value=False)
    client.is_connected = True
    return client
