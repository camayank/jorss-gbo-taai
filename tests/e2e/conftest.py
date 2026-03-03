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
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

# Ensure src/ is on path
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# =============================================================================
# JWT SECRET FOR TESTS
# =============================================================================
# Set a known JWT secret BEFORE any app imports so that tokens we generate
# here can be verified by the application's auth stack (rbac.jwt, rbac.dependencies,
# core.rbac.middleware, security.auth_decorators).
_TEST_JWT_SECRET = "e2e-test-secret-key-that-is-at-least-32-chars-long"
os.environ["JWT_SECRET"] = _TEST_JWT_SECRET


# =============================================================================
# STABLE TEST UUIDs
# =============================================================================
CONSUMER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
CPA_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
ADMIN_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
SUPERADMIN_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
CPA_B_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")
FIRM_ID_1 = uuid.UUID("00000000-0000-0000-0000-0000000000f1")
FIRM_ID_2 = uuid.UUID("00000000-0000-0000-0000-0000000000f2")


# =============================================================================
# TOKEN GENERATION HELPER
# =============================================================================
def _make_test_token(
    user_id,
    email,
    name,
    role,
    user_type,
    firm_id=None,
    firm_name=None,
):
    """Create a real JWT token that the application's auth stack will accept."""
    import jwt as pyjwt

    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "role": role,
        "user_type": user_type,
        "jti": str(uuid.uuid4()),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "type": "access",
    }
    if firm_id:
        payload["firm_id"] = str(firm_id)
    if firm_name:
        payload["firm_name"] = firm_name
    return pyjwt.encode(payload, _TEST_JWT_SECRET, algorithm="HS256")


# Pre-generate tokens at module load so they are available for CSRF_HEADERS
_CONSUMER_TOKEN = _make_test_token(
    CONSUMER_USER_ID, "taxpayer@example.com", "Jane Taxpayer",
    "firm_client", "client",
)
_CPA_TOKEN = _make_test_token(
    CPA_USER_ID, "cpa@taxfirm.com", "Sarah Mitchell",
    "staff", "firm_user",
    firm_id=FIRM_ID_1, firm_name="E2E Tax Firm",
)
_ADMIN_TOKEN = _make_test_token(
    ADMIN_USER_ID, "admin@taxfirm.com", "Admin User",
    "partner", "firm_user",
    firm_id=FIRM_ID_1, firm_name="E2E Tax Firm",
)
_SUPERADMIN_TOKEN = _make_test_token(
    SUPERADMIN_USER_ID, "superadmin@platform.com", "Platform Admin",
    "platform_admin", "platform_admin",
)
_CPA_B_TOKEN = _make_test_token(
    CPA_B_USER_ID, "other-cpa@otherfirm.com", "Bob Other-CPA",
    "staff", "firm_user",
    firm_id=FIRM_ID_2, firm_name="Other Firm",
)


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
    # Reset the cached JWT secret so it picks up our test value
    import rbac.jwt as jwt_module
    jwt_module._jwt_secret_cache = None

    from web.app import app

    # Patch the RBACMiddleware token revocation check.
    # In tests there is no Redis, so _is_token_revoked would fail-closed
    # and reject every valid token with 401.  We also patch
    # core.rbac.middleware.decode_token_safe so the middleware's module-level
    # import resolves tokens using our test JWT_SECRET.
    _revoke_patch = patch(
        "core.rbac.middleware.RBACMiddleware._is_token_revoked",
        new_callable=AsyncMock,
        return_value=False,
    )
    _revoke_patch.start()

    client = TestClient(app)
    yield client

    _revoke_patch.stop()


# =============================================================================
# HEADERS
# =============================================================================

# Default headers use a real CPA token so most endpoints pass auth
CSRF_HEADERS = {
    "Authorization": f"Bearer {_CPA_TOKEN}",
    "Origin": "http://localhost:8000",
    "Content-Type": "application/json",
}


@pytest.fixture
def headers():
    """Headers with valid CPA auth token (default for most tests)."""
    return CSRF_HEADERS.copy()


@pytest.fixture
def consumer_headers():
    """Headers with valid consumer/taxpayer auth token."""
    return {
        "Authorization": f"Bearer {_CONSUMER_TOKEN}",
        "Origin": "http://localhost:8000",
        "Content-Type": "application/json",
    }


@pytest.fixture
def cpa_headers():
    """Headers with valid CPA staff auth token."""
    return {
        "Authorization": f"Bearer {_CPA_TOKEN}",
        "Origin": "http://localhost:8000",
        "Content-Type": "application/json",
    }


@pytest.fixture
def admin_headers():
    """Headers with valid firm admin (partner) auth token."""
    return {
        "Authorization": f"Bearer {_ADMIN_TOKEN}",
        "Origin": "http://localhost:8000",
        "Content-Type": "application/json",
    }


@pytest.fixture
def superadmin_headers():
    """Headers with valid platform admin auth token."""
    return {
        "Authorization": f"Bearer {_SUPERADMIN_TOKEN}",
        "Origin": "http://localhost:8000",
        "Content-Type": "application/json",
    }


@pytest.fixture
def cpa_b_headers():
    """Headers with valid CPA staff auth token for a second firm."""
    return {
        "Authorization": f"Bearer {_CPA_B_TOKEN}",
        "Origin": "http://localhost:8000",
        "Content-Type": "application/json",
    }


# =============================================================================
# JWT PAYLOAD FIXTURES (kept for backward compatibility with existing tests
# that use `with patch("rbac.jwt.decode_token_safe", return_value=payload)`)
# =============================================================================
# NOTE: Role values must match the rbac.roles.Role enum:
#   staff, partner, platform_admin, firm_client, direct_client, etc.
# The sub field must be a valid UUID string for rbac.dependencies to parse.

@pytest.fixture
def consumer_jwt_payload():
    """JWT payload for a consumer/taxpayer user."""
    return {
        "sub": str(CONSUMER_USER_ID),
        "email": "taxpayer@example.com",
        "name": "Jane Taxpayer",
        "role": "firm_client",
        "user_type": "client",
        "firm_id": None,
        "jti": str(uuid.uuid4()),
        "exp": 9999999999,
        "type": "access",
    }


@pytest.fixture
def cpa_jwt_payload():
    """JWT payload for a CPA staff user."""
    return {
        "sub": str(CPA_USER_ID),
        "email": "cpa@taxfirm.com",
        "name": "Sarah Mitchell",
        "role": "staff",
        "user_type": "firm_user",
        "firm_id": str(FIRM_ID_1),
        "jti": str(uuid.uuid4()),
        "exp": 9999999999,
        "type": "access",
    }


@pytest.fixture
def admin_jwt_payload():
    """JWT payload for a firm admin."""
    return {
        "sub": str(ADMIN_USER_ID),
        "email": "admin@taxfirm.com",
        "name": "Admin User",
        "role": "partner",
        "user_type": "firm_user",
        "firm_id": str(FIRM_ID_1),
        "jti": str(uuid.uuid4()),
        "exp": 9999999999,
        "type": "access",
    }


@pytest.fixture
def superadmin_jwt_payload():
    """JWT payload for a platform superadmin."""
    return {
        "sub": str(SUPERADMIN_USER_ID),
        "email": "superadmin@platform.com",
        "name": "Platform Admin",
        "role": "platform_admin",
        "user_type": "platform_admin",
        "firm_id": None,
        "jti": str(uuid.uuid4()),
        "exp": 9999999999,
        "type": "access",
    }


@pytest.fixture
def cpa_b_jwt_payload():
    """JWT payload for a second CPA (different firm) -- used in multi-tenancy tests."""
    return {
        "sub": str(CPA_B_USER_ID),
        "email": "other-cpa@otherfirm.com",
        "name": "Bob Other-CPA",
        "role": "staff",
        "user_type": "firm_user",
        "firm_id": str(FIRM_ID_2),
        "jti": str(uuid.uuid4()),
        "exp": 9999999999,
        "type": "access",
    }


# =============================================================================
# AUTH HELPERS
# =============================================================================

def auth_headers(token=_CPA_TOKEN, csrf=None):
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
    # Directly populate the session store -- avoids async/event loop issues
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
    # Reset JWT secret cache so tests always use the test secret
    try:
        import rbac.jwt as jwt_module
        jwt_module._jwt_secret_cache = None
    except (ImportError, AttributeError):
        pass
    try:
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None
    except (ImportError, AttributeError):
        pass
    yield
    try:
        import rbac.jwt as jwt_module
        jwt_module._jwt_secret_cache = None
    except (ImportError, AttributeError):
        pass
    try:
        import database.async_engine as module
        module._async_engine = None
        module._async_session_factory = None
    except (ImportError, AttributeError):
        pass
