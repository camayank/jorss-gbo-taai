"""
Integration Test Fixtures

SPEC-011: Shared fixtures for integration tests.

Provides:
- test_client: FastAPI TestClient with CSRF bypass
- mock_auth_headers: Headers with mock authentication
- test_db: Isolated test database
- test_session_id: Fresh session ID for each test
"""

import os
import sys
import uuid
import tempfile
from pathlib import Path
from typing import Generator, Dict, Any
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def temp_db():
    """
    Create a temporary database for each test.

    Yields the path to the temporary database file.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Set environment variable for database
    old_db_path = os.environ.get("DATABASE_PATH")
    os.environ["DATABASE_PATH"] = db_path

    yield db_path

    # Cleanup
    if old_db_path:
        os.environ["DATABASE_PATH"] = old_db_path
    else:
        os.environ.pop("DATABASE_PATH", None)

    # Remove temp file
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(scope="function")
def test_db(temp_db):
    """
    Initialize test database with schema.

    This fixture depends on temp_db and creates the necessary tables.
    """
    import sqlite3

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Create minimal schema for tests
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_returns (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            tax_year INTEGER DEFAULT 2025,
            status TEXT DEFAULT 'DRAFT',
            return_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            tenant_id TEXT DEFAULT 'default',
            session_type TEXT DEFAULT 'tax_return',
            data TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lead_magnet_leads (
            id TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS return_status (
            session_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'DRAFT',
            cpa_reviewer_id TEXT,
            cpa_reviewer_name TEXT,
            review_notes TEXT,
            approval_signature_hash TEXT,
            approval_timestamp TIMESTAMP,
            last_status_change TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    yield temp_db


# =============================================================================
# TEST CLIENT FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def test_client(test_db):
    """
    Provide FastAPI TestClient with CSRF bypass headers.

    Uses isolated test database.
    """
    # Import after database setup
    from web.app import app

    client = TestClient(app)
    return client


@pytest.fixture
def csrf_headers():
    """
    Headers that bypass CSRF protection for testing.

    These headers simulate a request from a trusted origin with Bearer auth.
    """
    return {
        "Authorization": "Bearer test_token_for_csrf_bypass",
        "Origin": "http://localhost:8000",
        "Content-Type": "application/json",
    }


@pytest.fixture
def auth_headers():
    """
    Headers with mock JWT authentication.

    Returns headers that simulate an authenticated CPA user.
    """
    return {
        "Authorization": "Bearer mock_jwt_token_cpa_user",
        "Origin": "http://localhost:8000",
        "Content-Type": "application/json",
        "X-User-ID": "test-user-123",
        "X-User-Role": "cpa_staff",
        "X-Tenant-ID": "test-tenant-001",
    }


@pytest.fixture
def admin_headers():
    """
    Headers with mock JWT authentication for admin user.
    """
    return {
        "Authorization": "Bearer mock_jwt_token_admin_user",
        "Origin": "http://localhost:8000",
        "Content-Type": "application/json",
        "X-User-ID": "admin-user-001",
        "X-User-Role": "system_admin",
        "X-Tenant-ID": "admin",
    }


# =============================================================================
# SESSION FIXTURES
# =============================================================================

@pytest.fixture
def test_session_id():
    """Generate a fresh session ID for each test."""
    return str(uuid.uuid4())


@pytest.fixture
def test_return_id():
    """Generate a fresh return ID for each test."""
    return str(uuid.uuid4())


# =============================================================================
# MOCK FIXTURES
# =============================================================================

@pytest.fixture
def mock_jwt_decode():
    """
    Mock JWT token decoding to return test user claims.

    Use when testing authenticated endpoints without real JWT setup.
    """
    mock_payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "name": "Test User",
        "role": "cpa_staff",
        "firm_id": "test-tenant-001",
        "exp": 9999999999,
        "type": "access",
    }

    # Try multiple possible module paths for JWT decode
    try:
        with patch("rbac.jwt.decode_token_safe", return_value=mock_payload):
            yield mock_payload
    except (ModuleNotFoundError, AttributeError):
        # JWT module not available - just yield the payload
        yield mock_payload


@pytest.fixture
def mock_redis():
    """
    Mock Redis client for tests that use caching.
    """
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.delete.return_value = True
    mock_client.exists.return_value = False
    mock_client.is_connected = True

    with patch("services.cache.get_redis_client", return_value=mock_client):
        yield mock_client


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================

@pytest.fixture
def sample_tax_return_data():
    """
    Sample tax return data for testing.
    """
    return {
        "tax_year": 2025,
        "taxpayer": {
            "first_name": "John",
            "last_name": "Doe",
            "filing_status": "single",
            "ssn": "123-45-6789",
        },
        "income": {
            "wages": 75000,
            "interest": 500,
            "dividends": 1200,
        },
        "deductions": {
            "use_standard_deduction": True,
        },
        "credits": {},
    }


@pytest.fixture
def sample_document_data():
    """
    Sample document metadata for testing.
    """
    return {
        "filename": "w2_2025.pdf",
        "document_type": "W-2",
        "tax_year": 2025,
        "content_type": "application/pdf",
        "size_bytes": 102400,
    }


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================

def _reset_integration_globals():
    """Reset global state for integration tests."""
    try:
        from web.routers import returns
        returns._persistence = None
        returns._session_persistence = None
    except (ImportError, AttributeError):
        pass

    try:
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset any global state before and after tests."""
    _reset_integration_globals()
    yield
    _reset_integration_globals()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def make_request_with_retry(client, method, url, max_retries=3, **kwargs):
    """
    Make a request with retry logic for flaky tests.

    Args:
        client: TestClient instance
        method: HTTP method (get, post, etc.)
        url: Request URL
        max_retries: Maximum retry attempts
        **kwargs: Additional request arguments

    Returns:
        Response object
    """
    request_func = getattr(client, method.lower())
    last_error = None

    for attempt in range(max_retries):
        try:
            response = request_func(url, **kwargs)
            return response
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                import time
                time.sleep(0.1 * (attempt + 1))

    raise last_error
