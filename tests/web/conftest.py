"""
Fixtures for Web API tests.
Provides TestClient, auth mocking, and CSRF bypass headers.
"""
import os
import sys
from pathlib import Path

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

CSRF_HEADERS = {
    "Authorization": "Bearer test_token_for_csrf_bypass",
    "Origin": "http://localhost:8000",
}


@pytest.fixture
def csrf_headers():
    """Standard CSRF bypass headers for testing."""
    return CSRF_HEADERS.copy()


@pytest.fixture
def auth_headers():
    """Auth headers including CSRF bypass."""
    return {
        **CSRF_HEADERS,
        "Content-Type": "application/json",
    }


@pytest.fixture
def mock_auth_context():
    """Mock authentication context."""
    ctx = Mock()
    ctx.user_id = "test-user-123"
    ctx.role = "partner"
    ctx.firm_id = "test-firm-123"
    return ctx


@pytest.fixture
def mock_session_persistence():
    """Mock session persistence layer."""
    persistence = Mock()
    persistence.get_session = Mock(return_value=None)
    persistence.save_session = Mock()
    return persistence
