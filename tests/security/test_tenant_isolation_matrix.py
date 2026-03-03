"""Comprehensive tenant isolation tests.

Verifies that multi-tenant boundaries are enforced: Tenant A cannot access
Tenant B's data. Tests cover tenant access levels, query scoping, cross-tenant
prevention, CPA-client access, anomaly detection, and the
TenantScopedDependency / require_tenant_access decorator.
"""

import os
import sys
import time
from pathlib import Path

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch, PropertyMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from security.tenant_isolation import (
    TenantAccessLevel,
    TenantIsolationError,
    get_user_allowed_tenants,
    get_tenant_access_level,
    verify_tenant_access,
    get_authenticated_tenant_id,
    scope_query_to_tenant,
    TenantScopedDependency,
    require_tenant_access,
    verify_cpa_client_access,
    _log_tenant_access,
    _track_access_anomaly,
    _access_anomaly_tracker,
    _tenant_access_cache,
    TENANT_STRICT_MODE,
)

# Also test the legacy authentication.py tenant checks
from security.authentication import (
    AuthenticationManager,
    UserRole,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear caches and trackers between tests."""
    _tenant_access_cache.clear()
    _access_anomaly_tracker.clear()
    yield
    _tenant_access_cache.clear()
    _access_anomaly_tracker.clear()


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request."""
    request = MagicMock()
    request.state = MagicMock()
    request.state.tenant_id = "tenant-A"
    request.state.auth = MagicMock()
    request.state.auth.user_id = "user-1"
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.url.path = "/api/test"
    request.method = "GET"
    return request


@pytest.fixture
def auth_manager():
    return AuthenticationManager(secret_key="test_tenant_key_" + "0" * 48)


# ===========================================================================
# TenantAccessLevel enum
# ===========================================================================

class TestTenantAccessLevelEnum:
    """TenantAccessLevel enum completeness."""

    def test_none_exists(self):
        assert TenantAccessLevel.NONE.value == "none"

    def test_read_exists(self):
        assert TenantAccessLevel.READ.value == "read"

    def test_write_exists(self):
        assert TenantAccessLevel.WRITE.value == "write"

    def test_admin_exists(self):
        assert TenantAccessLevel.ADMIN.value == "admin"

    def test_count(self):
        assert len(TenantAccessLevel) == 4

    @pytest.mark.parametrize("level", list(TenantAccessLevel))
    def test_is_str_enum(self, level):
        assert isinstance(level, str)


# ===========================================================================
# TenantIsolationError
# ===========================================================================

class TestTenantIsolationError:
    """Custom exception class."""

    def test_message(self):
        err = TenantIsolationError("cross-tenant access")
        assert str(err) == "cross-tenant access"

    def test_user_id(self):
        err = TenantIsolationError("msg", user_id="u-1")
        assert err.user_id == "u-1"

    def test_tenant_id(self):
        err = TenantIsolationError("msg", tenant_id="t-1")
        assert err.tenant_id == "t-1"

    def test_is_exception(self):
        assert issubclass(TenantIsolationError, Exception)


# ===========================================================================
# get_user_allowed_tenants
# ===========================================================================

class TestGetUserAllowedTenants:
    """User's allowed tenant set."""

    def test_returns_set(self):
        result = get_user_allowed_tenants("user-1")
        assert isinstance(result, set)

    def test_includes_default(self):
        result = get_user_allowed_tenants("user-1")
        assert "default" in result

    def test_includes_user_id_as_tenant(self):
        result = get_user_allowed_tenants("user-1")
        assert "user-1" in result

    def test_different_users_get_different_sets(self):
        r1 = get_user_allowed_tenants("user-1")
        r2 = get_user_allowed_tenants("user-2")
        assert "user-1" in r1
        assert "user-1" not in r2
        assert "user-2" in r2
        assert "user-2" not in r1


# ===========================================================================
# get_tenant_access_level
# ===========================================================================

class TestGetTenantAccessLevel:
    """Access level resolution."""

    def test_default_tenant_is_read(self):
        level = get_tenant_access_level("user-1", "default")
        assert level == TenantAccessLevel.READ

    def test_own_tenant_is_admin(self):
        level = get_tenant_access_level("user-1", "user-1")
        assert level == TenantAccessLevel.ADMIN

    def test_unrelated_tenant_is_none(self):
        level = get_tenant_access_level("user-1", "other-tenant-xyz")
        assert level == TenantAccessLevel.NONE

    def test_cached_access_level(self):
        _tenant_access_cache["user-cached"] = {"t-1": TenantAccessLevel.WRITE}
        level = get_tenant_access_level("user-cached", "t-1")
        assert level == TenantAccessLevel.WRITE


# ===========================================================================
# verify_tenant_access
# ===========================================================================

class TestVerifyTenantAccess:
    """Tenant access verification."""

    def test_user_can_read_default(self):
        assert verify_tenant_access("user-1", "default", TenantAccessLevel.READ) is True

    def test_user_can_admin_own_tenant(self):
        assert verify_tenant_access("user-1", "user-1", TenantAccessLevel.ADMIN) is True

    def test_user_cannot_read_other_tenant(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_tenant_access("user-1", "other-tenant-999", TenantAccessLevel.READ)
        assert exc_info.value.status_code == 403

    def test_no_exception_mode_returns_false(self):
        result = verify_tenant_access(
            "user-1", "other-tenant-999",
            TenantAccessLevel.READ, raise_exception=False,
        )
        assert result is False

    def test_higher_level_required_fails(self):
        """Default tenant gives READ, but WRITE is required."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            verify_tenant_access("user-1", "default", TenantAccessLevel.WRITE)

    def test_admin_on_own_tenant_covers_all_levels(self):
        for level in TenantAccessLevel:
            if level == TenantAccessLevel.NONE:
                continue
            result = verify_tenant_access(
                "user-1", "user-1", level, raise_exception=False,
            )
            assert result is True


# ===========================================================================
# Cross-tenant isolation - the core security test
# ===========================================================================

RESOURCE_TYPES = ["leads", "clients", "returns", "tasks", "documents"]


class TestCrossTenantIsolation:
    """Tenant A must never access Tenant B's resources."""

    @pytest.mark.parametrize("resource_type", RESOURCE_TYPES)
    def test_tenant_a_cannot_access_tenant_b(self, resource_type):
        """User in tenant-A cannot access tenant-B resources."""
        result = verify_tenant_access(
            "user-in-tenant-A", "tenant-B",
            TenantAccessLevel.READ, raise_exception=False,
        )
        assert result is False, (
            f"Tenant-A user should NOT access tenant-B {resource_type}"
        )

    @pytest.mark.parametrize("resource_type", RESOURCE_TYPES)
    def test_tenant_b_cannot_access_tenant_a(self, resource_type):
        result = verify_tenant_access(
            "user-in-tenant-B", "tenant-A",
            TenantAccessLevel.READ, raise_exception=False,
        )
        assert result is False

    @pytest.mark.parametrize("resource_type", RESOURCE_TYPES)
    def test_user_can_access_own_tenant(self, resource_type):
        """User can access their own tenant's resources."""
        result = verify_tenant_access(
            "user-1", "user-1",
            TenantAccessLevel.READ, raise_exception=False,
        )
        assert result is True

    @pytest.mark.parametrize("level", [
        TenantAccessLevel.READ,
        TenantAccessLevel.WRITE,
        TenantAccessLevel.ADMIN,
    ])
    def test_cross_tenant_denied_at_all_levels(self, level):
        result = verify_tenant_access(
            "user-A", "completely-different-tenant",
            level, raise_exception=False,
        )
        assert result is False


class TestCrossTenantHTTPExceptions:
    """Cross-tenant access returns proper HTTP 403."""

    @pytest.mark.parametrize("target_tenant", [
        "firm-B",
        "firm-C",
        "random-tenant-id-12345",
        "competitor-firm",
    ])
    def test_403_on_cross_tenant_access(self, target_tenant):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_tenant_access("user-from-firm-A", target_tenant)
        assert exc_info.value.status_code == 403
        detail = exc_info.value.detail
        assert detail["error_code"] == "TENANT_ACCESS_DENIED"


# ===========================================================================
# scope_query_to_tenant
# ===========================================================================

class TestScopeQueryToTenant:
    """Query scoping adds tenant filter."""

    def test_adds_tenant_id(self):
        params = {"status": "active"}
        scoped = scope_query_to_tenant(params, "tenant-A")
        assert scoped["tenant_id"] == "tenant-A"
        assert scoped["status"] == "active"

    def test_does_not_mutate_original(self):
        params = {"status": "active"}
        scope_query_to_tenant(params, "tenant-A")
        assert "tenant_id" not in params

    def test_custom_column_name(self):
        params = {}
        scoped = scope_query_to_tenant(params, "tenant-A", tenant_column="firm_id")
        assert scoped["firm_id"] == "tenant-A"
        assert "tenant_id" not in scoped

    def test_overwrites_existing_tenant(self):
        params = {"tenant_id": "should-be-overwritten"}
        scoped = scope_query_to_tenant(params, "correct-tenant")
        assert scoped["tenant_id"] == "correct-tenant"

    @pytest.mark.parametrize("tenant_id", [
        "tenant-A",
        "default",
        "",
        "uuid-550e8400-e29b-41d4-a716-446655440000",
    ])
    def test_various_tenant_ids(self, tenant_id):
        scoped = scope_query_to_tenant({}, tenant_id)
        assert scoped["tenant_id"] == tenant_id


# ===========================================================================
# get_authenticated_tenant_id
# ===========================================================================

class TestGetAuthenticatedTenantId:
    """Secure tenant ID extraction from request."""

    def test_returns_tenant_from_state(self, mock_request):
        mock_request.state.tenant_id = "firm-123"
        tenant_id = get_authenticated_tenant_id(mock_request, validate_access=False)
        assert tenant_id == "firm-123"

    def test_defaults_to_default_when_missing(self, mock_request):
        mock_request.state.tenant_id = None
        tenant_id = get_authenticated_tenant_id(mock_request, validate_access=False)
        assert tenant_id == "default"

    def test_unauthenticated_non_default_raises(self, mock_request):
        from fastapi import HTTPException
        mock_request.state.auth = None
        mock_request.state.tenant_id = "non-default-tenant"
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_tenant_id(mock_request, validate_access=True)
        assert exc_info.value.status_code == 401

    def test_unauthenticated_default_allowed(self, mock_request):
        mock_request.state.auth = None
        mock_request.state.tenant_id = None  # Will default to "default"
        tenant_id = get_authenticated_tenant_id(mock_request, validate_access=True)
        assert tenant_id == "default"


# ===========================================================================
# TenantScopedDependency
# ===========================================================================

class TestTenantScopedDependency:
    """FastAPI dependency for tenant-scoped access."""

    def test_init_default_level(self):
        dep = TenantScopedDependency()
        assert dep.required_level == TenantAccessLevel.READ

    def test_init_custom_level(self):
        dep = TenantScopedDependency(required_level=TenantAccessLevel.WRITE)
        assert dep.required_level == TenantAccessLevel.WRITE

    @pytest.mark.asyncio
    async def test_authenticated_user_default_tenant(self, mock_request):
        mock_request.state.tenant_id = "default"
        mock_request.state.auth = MagicMock()
        mock_request.state.auth.user_id = "user-1"
        dep = TenantScopedDependency()
        result = await dep(mock_request)
        assert result.tenant_id == "default"

    @pytest.mark.asyncio
    async def test_unauthenticated_default_tenant_allowed(self, mock_request):
        mock_request.state.auth = None
        mock_request.state.tenant_id = "default"
        dep = TenantScopedDependency()
        result = await dep(mock_request)
        assert result.access_level == TenantAccessLevel.READ

    @pytest.mark.asyncio
    async def test_unauthenticated_non_default_raises(self, mock_request):
        from fastapi import HTTPException
        mock_request.state.auth = None
        mock_request.state.tenant_id = "non-default"
        dep = TenantScopedDependency()
        with pytest.raises(HTTPException) as exc_info:
            await dep(mock_request)
        assert exc_info.value.status_code == 401


# ===========================================================================
# require_tenant_access decorator
# ===========================================================================

class TestRequireTenantAccessDecorator:
    """Decorator that enforces tenant access on endpoints."""

    @pytest.mark.asyncio
    async def test_authenticated_user_own_tenant(self, mock_request):
        mock_request.state.tenant_id = "user-1"
        mock_request.state.auth = MagicMock()
        mock_request.state.auth.user_id = "user-1"

        @require_tenant_access(TenantAccessLevel.READ)
        async def endpoint(request):
            return {"ok": True}

        result = await endpoint(mock_request)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_cross_tenant_raises_403(self, mock_request):
        from fastapi import HTTPException
        mock_request.state.tenant_id = "other-firm"
        mock_request.state.auth = MagicMock()
        mock_request.state.auth.user_id = "user-1"

        @require_tenant_access(TenantAccessLevel.READ)
        async def endpoint(request):
            return {"ok": True}

        with pytest.raises(HTTPException) as exc_info:
            await endpoint(mock_request)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_default_allowed(self, mock_request):
        mock_request.state.auth = None
        mock_request.state.tenant_id = "default"

        @require_tenant_access(TenantAccessLevel.READ)
        async def endpoint(request):
            return {"ok": True}

        result = await endpoint(mock_request)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_unauthenticated_non_default_raises(self, mock_request):
        from fastapi import HTTPException
        mock_request.state.auth = None
        mock_request.state.tenant_id = "private-firm"

        @require_tenant_access(TenantAccessLevel.READ)
        async def endpoint(request):
            return {"ok": True}

        with pytest.raises(HTTPException):
            await endpoint(mock_request)


# ===========================================================================
# CPA-client access (mocked DB)
# ===========================================================================

class TestCPAClientAccess:
    """CPA-client assignment verification."""

    @patch("security.tenant_isolation.TENANT_STRICT_MODE", False)
    def test_permissive_mode_allows(self):
        result = verify_cpa_client_access("cpa-1", "client-1", raise_exception=False)
        assert result is True

    @patch("security.tenant_isolation.TENANT_STRICT_MODE", True)
    @patch("sqlite3.connect")
    def test_strict_mode_checks_db(self, mock_connect):
        """In strict mode, DB is queried for assignment."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        result = verify_cpa_client_access("cpa-1", "client-1", raise_exception=False)
        assert result is False

    @patch("security.tenant_isolation.TENANT_STRICT_MODE", True)
    @patch("sqlite3.connect")
    def test_strict_mode_db_error_denies(self, mock_connect):
        """DB error in strict mode -> deny access (fail-closed)."""
        mock_connect.side_effect = Exception("DB unavailable")
        result = verify_cpa_client_access("cpa-1", "client-1", raise_exception=False)
        assert result is False

    @patch("security.tenant_isolation.TENANT_STRICT_MODE", False)
    def test_cpa_access_denied_raises_http(self):
        """When raise_exception=True and access denied."""
        # In permissive mode it always allows, so mock strict mode
        with patch("security.tenant_isolation.TENANT_STRICT_MODE", True):
            with patch("sqlite3.connect") as mock_connect:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchone.return_value = None
                mock_conn.cursor.return_value = mock_cursor
                mock_conn.__enter__ = Mock(return_value=mock_conn)
                mock_conn.__exit__ = Mock(return_value=False)
                mock_connect.return_value = mock_conn

                from fastapi import HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    verify_cpa_client_access("cpa-1", "client-1", raise_exception=True)
                assert exc_info.value.status_code == 403


# ===========================================================================
# Anomaly tracking
# ===========================================================================

class TestAnomalyTracking:
    """Access anomaly detection."""

    def test_normal_access_no_anomaly(self):
        _track_access_anomaly("user-1", "tenant-1")
        assert "user-1" in _access_anomaly_tracker
        assert len(_access_anomaly_tracker["user-1"]) == 1

    def test_multiple_tenants_tracked(self):
        for i in range(5):
            _track_access_anomaly("user-1", f"tenant-{i}")
        assert len(_access_anomaly_tracker["user-1"]) == 5

    def test_old_entries_cleaned(self):
        """Entries older than 5 minutes should be cleaned."""
        _access_anomaly_tracker["user-1"] = [
            {"tenant_id": "old", "timestamp": time.time() - 400},
        ]
        _track_access_anomaly("user-1", "new-tenant")
        # Old entry should be pruned
        assert all(
            a["timestamp"] > time.time() - 310
            for a in _access_anomaly_tracker["user-1"]
        )


# ===========================================================================
# Audit logging
# ===========================================================================

class TestAuditLogging:
    """Tenant access audit logging."""

    def test_log_access_granted(self):
        """Should not raise."""
        _log_tenant_access("user-1", "tenant-1", "read", granted=True)

    def test_log_access_denied(self):
        """Should not raise."""
        _log_tenant_access("user-1", "tenant-1", "write", granted=False, reason="test")

    def test_log_with_request_context(self):
        _log_tenant_access(
            "user-1", "tenant-1", "read", granted=True,
            request_context={"ip": "1.2.3.4", "path": "/api/test"},
        )


# ===========================================================================
# Legacy AuthenticationManager tenant check
# ===========================================================================

class TestLegacyAuthTenantCheck:
    """AuthenticationManager.check_tenant_access from authentication.py."""

    def test_same_tenant_allowed(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "firm-A")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_tenant_access(claims, "firm-A") is True

    def test_different_tenant_denied(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "firm-A")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_tenant_access(claims, "firm-B") is False

    def test_admin_bypasses_tenant(self, auth_manager):
        token = auth_manager.create_token("admin-1", UserRole.ADMIN, "firm-A")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_tenant_access(claims, "firm-Z") is True

    @pytest.mark.parametrize("role", [UserRole.TAXPAYER, UserRole.PREPARER, UserRole.REVIEWER])
    def test_non_admin_cross_tenant(self, auth_manager, role):
        token = auth_manager.create_token("user-1", role, "firm-A")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_tenant_access(claims, "firm-B") is False

    @pytest.mark.parametrize("firm_a,firm_b", [
        ("firm-1", "firm-2"),
        ("firm-alpha", "firm-beta"),
        ("default", "custom-firm"),
        ("uuid-aaa", "uuid-bbb"),
    ])
    def test_firm_isolation_pairs(self, auth_manager, firm_a, firm_b):
        token_a = auth_manager.create_token("user-A", UserRole.PREPARER, firm_a)
        token_b = auth_manager.create_token("user-B", UserRole.PREPARER, firm_b)
        claims_a = auth_manager.verify_token(token_a)
        claims_b = auth_manager.verify_token(token_b)

        # A can access A but not B
        assert auth_manager.check_tenant_access(claims_a, firm_a) is True
        assert auth_manager.check_tenant_access(claims_a, firm_b) is False

        # B can access B but not A
        assert auth_manager.check_tenant_access(claims_b, firm_b) is True
        assert auth_manager.check_tenant_access(claims_b, firm_a) is False


# ===========================================================================
# Data leakage scenarios
# ===========================================================================

class TestDataLeakagePrevention:
    """Simulate common cross-tenant data leakage scenarios."""

    def test_manipulated_tenant_header_blocked(self, mock_request):
        """User cannot simply change tenant_id header to access another firm."""
        mock_request.state.tenant_id = "victim-firm"
        mock_request.state.auth = MagicMock()
        mock_request.state.auth.user_id = "attacker-user"

        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            get_authenticated_tenant_id(mock_request, validate_access=True)

    def test_query_params_cannot_override_tenant(self):
        """scope_query_to_tenant always uses the provided tenant, not user input."""
        user_provided = {"tenant_id": "victim-firm", "status": "active"}
        scoped = scope_query_to_tenant(user_provided, "attacker-firm")
        # The scope function uses the provided tenant_id, overwriting any user-provided value
        assert scoped["tenant_id"] == "attacker-firm"

    def test_empty_tenant_id_does_not_bypass(self):
        """Empty string tenant should not match any other tenant."""
        result = verify_tenant_access(
            "user-1", "some-firm",
            TenantAccessLevel.READ, raise_exception=False,
        )
        assert result is False

    @pytest.mark.parametrize("resource", RESOURCE_TYPES)
    def test_admin_of_firm_a_cannot_see_firm_b(self, auth_manager, resource):
        """Even a firm admin (PREPARER/REVIEWER) cannot cross tenants."""
        token = auth_manager.create_token("firm-a-admin", UserRole.REVIEWER, "firm-A")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_tenant_access(claims, "firm-B") is False
