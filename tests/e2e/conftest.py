"""
E2E Test Fixtures

Provides test client, CSRF bypass headers, auth mocking, and session helpers
for end-to-end user journey tests.
"""

import os
import sys
import uuid
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

# Ensure src/ is on path
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# =============================================================================
# DATABASE
# =============================================================================

@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    old = os.environ.get("DATABASE_PATH")
    os.environ["DATABASE_PATH"] = db_path
    yield db_path
    if old:
        os.environ["DATABASE_PATH"] = old
    else:
        os.environ.pop("DATABASE_PATH", None)
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(scope="function")
def test_db(temp_db):
    """Initialize minimal schema for E2E tests."""
    import sqlite3
    conn = sqlite3.connect(temp_db)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS tax_returns (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
        tax_year INTEGER DEFAULT 2025, status TEXT DEFAULT 'DRAFT',
        return_data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY, tenant_id TEXT DEFAULT 'default',
        session_type TEXT DEFAULT 'tax_return', data TEXT, metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()
    yield temp_db


# =============================================================================
# TEST CLIENT
# =============================================================================

@pytest.fixture(scope="function")
def client(test_db):
    """FastAPI TestClient for E2E tests."""
    from web.app import app
    return TestClient(app)


# =============================================================================
# HEADERS
# =============================================================================

CSRF_HEADERS = {
    "Authorization": "Bearer test_token_for_csrf_bypass",
    "Origin": "http://localhost:8000",
    "Content-Type": "application/json",
}


@pytest.fixture
def headers():
    """CSRF bypass headers."""
    return CSRF_HEADERS.copy()


@pytest.fixture
def consumer_jwt_payload():
    """JWT payload for a consumer/taxpayer user."""
    return {
        "sub": "consumer-e2e-001",
        "email": "taxpayer@example.com",
        "name": "Jane Taxpayer",
        "role": "consumer",
        "firm_id": None,
        "exp": 9999999999,
        "type": "access",
    }


@pytest.fixture
def cpa_jwt_payload():
    """JWT payload for a CPA staff user."""
    return {
        "sub": "cpa-e2e-001",
        "email": "cpa@taxfirm.com",
        "name": "Sarah Mitchell",
        "role": "cpa_staff",
        "firm_id": "firm-e2e-001",
        "exp": 9999999999,
        "type": "access",
    }


@pytest.fixture
def admin_jwt_payload():
    """JWT payload for a firm admin."""
    return {
        "sub": "admin-e2e-001",
        "email": "admin@taxfirm.com",
        "name": "Admin User",
        "role": "partner",
        "firm_id": "firm-e2e-001",
        "exp": 9999999999,
        "type": "access",
    }


@pytest.fixture
def superadmin_jwt_payload():
    """JWT payload for a platform superadmin."""
    return {
        "sub": "superadmin-e2e-001",
        "email": "superadmin@platform.com",
        "name": "Platform Admin",
        "role": "platform_admin",
        "firm_id": None,
        "exp": 9999999999,
        "type": "access",
    }


@pytest.fixture
def cpa_b_jwt_payload():
    """JWT payload for a second CPA (different firm) — used in multi-tenancy tests."""
    return {
        "sub": "cpa-e2e-002",
        "email": "other-cpa@otherfirm.com",
        "name": "Bob Other-CPA",
        "role": "cpa_staff",
        "firm_id": "firm-e2e-002",
        "exp": 9999999999,
        "type": "access",
    }


# =============================================================================
# AUTH HELPERS
# =============================================================================

def auth_headers(token="test_token_for_csrf_bypass", csrf=None):
    """Build authorization headers with optional CSRF token."""
    h = {
        "Authorization": f"Bearer {token}",
        "Origin": "http://localhost:8000",
        "Content-Type": "application/json",
    }
    if csrf:
        h["X-CSRF-Token"] = csrf
    return h


def session_headers(session_token, base_headers=None):
    """Build headers with X-Session-Token for advisor endpoints."""
    h = (base_headers or CSRF_HEADERS).copy()
    h["X-Session-Token"] = session_token
    return h


# =============================================================================
# ADVISOR SESSION HELPERS
# =============================================================================

@pytest.fixture
def advisor_session(client):
    """Create an advisor session directly in chat_engine and return (session_id, session_token)."""
    from web.intelligent_advisor_api import chat_engine
    from security.session_token import SESSION_TOKEN_KEY, generate_session_token

    session_id = str(uuid.uuid4())
    token = generate_session_token()
    # Directly populate the session store — avoids async/event loop issues
    chat_engine.sessions[session_id] = {
        SESSION_TOKEN_KEY: token,
        "session_id": session_id,
        "messages": [],
        "profile": {},
        "turn_count": 0,
    }
    return session_id, token


# =============================================================================
# CLEANUP
# =============================================================================

@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global state before and after each test."""
    try:
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None
    except (ImportError, AttributeError):
        pass
    yield
    try:
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None
    except (ImportError, AttributeError):
        pass
