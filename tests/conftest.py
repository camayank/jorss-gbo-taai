"""Pytest configuration and fixtures for test suite."""

import os
import sys
from pathlib import Path

import pytest

# Set test environment BEFORE any other imports
# This ensures auth decorators use fail-open mode for tests
os.environ.setdefault("APP_ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("DB_DRIVER", "sqlite+aiosqlite")

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def _reset_db_modules():
    """Reset database module globals to ensure clean state."""
    try:
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def reset_database_globals():
    """Reset database module globals before and after each test."""
    _reset_db_modules()
    yield
    _reset_db_modules()


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


# =============================================================================
# CSRF BYPASS HELPERS FOR TESTING
# =============================================================================

# Default headers that bypass CSRF validation in tests
# Uses Bearer auth from a trusted origin (localhost:8000)
CSRF_BYPASS_HEADERS = {
    "Authorization": "Bearer test_token_for_csrf_bypass",
    "Origin": "http://localhost:8000",
}


@pytest.fixture
def csrf_headers():
    """
    Provide headers that bypass CSRF protection for testing.

    Usage:
        def test_my_endpoint(csrf_headers):
            client = TestClient(app)
            response = client.post("/api/endpoint", headers=csrf_headers)
    """
    return CSRF_BYPASS_HEADERS.copy()


@pytest.fixture
def authenticated_client():
    """
    Provide a TestClient with CSRF bypass headers pre-configured.

    Usage:
        def test_my_endpoint(authenticated_client):
            response = authenticated_client.post("/api/endpoint", json={...})
    """
    from fastapi.testclient import TestClient
    from web.app import app

    # Create client with default headers for CSRF bypass
    client = TestClient(app)

    # Wrap request methods to include CSRF bypass headers
    original_request = client.request

    def request_with_csrf(*args, **kwargs):
        headers = kwargs.get("headers") or {}
        headers.update(CSRF_BYPASS_HEADERS)
        kwargs["headers"] = headers
        return original_request(*args, **kwargs)

    client.request = request_with_csrf
    return client
