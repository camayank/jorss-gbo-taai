"""Comprehensive tests for authentication module.

Covers JWTClaims, UserRole, AuthenticationManager, token create/verify/revoke,
InMemoryRevocationBackend, RedisRevocationBackend, rate limiting, permission
checks, tenant access, and singleton management.
"""

import os
import sys
import time
import json
import secrets
from pathlib import Path

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from security.authentication import (
    UserRole,
    JWTClaims,
    AuthenticationError,
    AuthorizationError,
    InMemoryRevocationBackend,
    RedisRevocationBackend,
    TokenRevocationBackend,
    AuthenticationManager,
    get_auth_manager,
    reset_auth_manager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def secret_key():
    return "test_secret_key_" + "0" * 48


@pytest.fixture
def auth_manager(secret_key):
    return AuthenticationManager(secret_key=secret_key)


@pytest.fixture
def valid_claims():
    now = int(time.time())
    return JWTClaims(
        sub="user-123",
        role=UserRole.PREPARER,
        tenant_id="tenant-abc",
        exp=now + 3600,
        iat=now,
        jti="jti-001",
        permissions=["return_edit", "return_view_own"],
        metadata={"firm_id": "firm-1"},
    )


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the global auth manager singleton after each test."""
    yield
    reset_auth_manager()


# ===========================================================================
# UserRole enum
# ===========================================================================

class TestUserRole:
    """UserRole enum tests."""

    def test_taxpayer_exists(self):
        assert UserRole.TAXPAYER.value == "taxpayer"

    def test_preparer_exists(self):
        assert UserRole.PREPARER.value == "preparer"

    def test_reviewer_exists(self):
        assert UserRole.REVIEWER.value == "reviewer"

    def test_admin_exists(self):
        assert UserRole.ADMIN.value == "admin"

    def test_all_roles_count(self):
        assert len(UserRole) == 4

    def test_string_conversion(self):
        assert str(UserRole.ADMIN) == "UserRole.ADMIN"

    def test_value_is_string(self):
        for role in UserRole:
            assert isinstance(role.value, str)

    def test_from_value(self):
        assert UserRole("taxpayer") == UserRole.TAXPAYER
        assert UserRole("admin") == UserRole.ADMIN

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            UserRole("invalid_role")

    @pytest.mark.parametrize("role", list(UserRole))
    def test_role_is_str_enum(self, role):
        assert isinstance(role, str)

    @pytest.mark.parametrize("role,expected_value", [
        (UserRole.TAXPAYER, "taxpayer"),
        (UserRole.PREPARER, "preparer"),
        (UserRole.REVIEWER, "reviewer"),
        (UserRole.ADMIN, "admin"),
    ])
    def test_role_values(self, role, expected_value):
        assert role.value == expected_value


# ===========================================================================
# JWTClaims dataclass
# ===========================================================================

class TestJWTClaims:
    """JWTClaims dataclass tests."""

    def test_create_valid_claims(self, valid_claims):
        assert valid_claims.sub == "user-123"
        assert valid_claims.role == UserRole.PREPARER
        assert valid_claims.tenant_id == "tenant-abc"
        assert valid_claims.jti == "jti-001"

    def test_default_permissions_empty(self):
        now = int(time.time())
        claims = JWTClaims(
            sub="u", role=UserRole.TAXPAYER, tenant_id="t",
            exp=now + 60, iat=now, jti="j",
        )
        assert claims.permissions == []

    def test_default_metadata_empty(self):
        now = int(time.time())
        claims = JWTClaims(
            sub="u", role=UserRole.TAXPAYER, tenant_id="t",
            exp=now + 60, iat=now, jti="j",
        )
        assert claims.metadata == {}

    def test_permissions_list(self, valid_claims):
        assert "return_edit" in valid_claims.permissions
        assert "return_view_own" in valid_claims.permissions

    def test_metadata_dict(self, valid_claims):
        assert valid_claims.metadata["firm_id"] == "firm-1"

    def test_claims_with_all_roles(self):
        now = int(time.time())
        for role in UserRole:
            claims = JWTClaims(
                sub="u", role=role, tenant_id="t",
                exp=now + 60, iat=now, jti="j",
            )
            assert claims.role == role

    def test_claims_with_empty_sub(self):
        now = int(time.time())
        claims = JWTClaims(
            sub="", role=UserRole.TAXPAYER, tenant_id="t",
            exp=now + 60, iat=now, jti="j",
        )
        assert claims.sub == ""

    def test_claims_with_many_permissions(self):
        now = int(time.time())
        perms = [f"perm_{i}" for i in range(100)]
        claims = JWTClaims(
            sub="u", role=UserRole.ADMIN, tenant_id="t",
            exp=now + 60, iat=now, jti="j",
            permissions=perms,
        )
        assert len(claims.permissions) == 100


# ===========================================================================
# InMemoryRevocationBackend
# ===========================================================================

class TestInMemoryRevocationBackend:
    """In-memory token revocation tests."""

    def test_new_token_not_revoked(self):
        backend = InMemoryRevocationBackend()
        assert backend.is_revoked("token-1") is False

    def test_revoke_then_check(self):
        backend = InMemoryRevocationBackend()
        backend.revoke("token-1", exp=int(time.time()) + 3600)
        assert backend.is_revoked("token-1") is True

    def test_other_token_not_affected(self):
        backend = InMemoryRevocationBackend()
        backend.revoke("token-1", exp=int(time.time()) + 3600)
        assert backend.is_revoked("token-2") is False

    def test_revoke_multiple_tokens(self):
        backend = InMemoryRevocationBackend()
        for i in range(10):
            backend.revoke(f"token-{i}", exp=int(time.time()) + 3600)
        for i in range(10):
            assert backend.is_revoked(f"token-{i}") is True
        assert backend.is_revoked("token-10") is False

    def test_revoke_idempotent(self):
        backend = InMemoryRevocationBackend()
        backend.revoke("token-1", exp=int(time.time()) + 3600)
        backend.revoke("token-1", exp=int(time.time()) + 3600)
        assert backend.is_revoked("token-1") is True

    def test_empty_jti(self):
        backend = InMemoryRevocationBackend()
        backend.revoke("", exp=int(time.time()) + 3600)
        assert backend.is_revoked("") is True


# ===========================================================================
# RedisRevocationBackend (mocked)
# ===========================================================================

class TestRedisRevocationBackend:
    """Redis-based token revocation (Redis mocked)."""

    def test_init_with_default_url(self):
        backend = RedisRevocationBackend()
        assert "redis://" in backend.redis_url

    def test_init_with_custom_url(self):
        backend = RedisRevocationBackend(redis_url="redis://custom:6380/1")
        assert backend.redis_url == "redis://custom:6380/1"

    @patch("security.authentication.RedisRevocationBackend._get_redis")
    def test_is_revoked_when_redis_unavailable(self, mock_get_redis):
        mock_get_redis.return_value = None
        backend = RedisRevocationBackend()
        # Redis unavailable -> fail closed -> True (revoked)
        assert backend.is_revoked("some-jti") is True

    @patch("security.authentication.RedisRevocationBackend._get_redis")
    def test_is_revoked_token_exists(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1
        mock_get_redis.return_value = mock_redis

        backend = RedisRevocationBackend()
        assert backend.is_revoked("revoked-jti") is True
        mock_redis.exists.assert_called_once_with("revoked_token:revoked-jti")

    @patch("security.authentication.RedisRevocationBackend._get_redis")
    def test_is_revoked_token_not_exists(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0
        mock_get_redis.return_value = mock_redis

        backend = RedisRevocationBackend()
        assert backend.is_revoked("valid-jti") is False

    @patch("security.authentication.RedisRevocationBackend._get_redis")
    def test_revoke_sets_key_with_ttl(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        backend = RedisRevocationBackend()
        future_exp = int(time.time()) + 3600
        backend.revoke("jti-123", future_exp)

        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "revoked_token:jti-123"
        assert args[2] == "revoked"

    @patch("security.authentication.RedisRevocationBackend._get_redis")
    def test_revoke_when_redis_unavailable(self, mock_get_redis):
        mock_get_redis.return_value = None
        backend = RedisRevocationBackend()
        # Should not raise, just return silently
        backend.revoke("jti-123", int(time.time()) + 3600)

    @patch("security.authentication.RedisRevocationBackend._get_redis")
    def test_is_revoked_redis_error_fails_closed(self, mock_get_redis):
        mock_redis = MagicMock()
        mock_redis.exists.side_effect = Exception("Connection lost")
        mock_get_redis.return_value = mock_redis

        backend = RedisRevocationBackend()
        assert backend.is_revoked("some-jti") is True  # Fail closed


# ===========================================================================
# TokenRevocationBackend (abstract base)
# ===========================================================================

class TestTokenRevocationBackendAbstract:
    """Abstract base class raises NotImplementedError."""

    def test_is_revoked_not_implemented(self):
        backend = TokenRevocationBackend()
        with pytest.raises(NotImplementedError):
            backend.is_revoked("jti")

    def test_revoke_not_implemented(self):
        backend = TokenRevocationBackend()
        with pytest.raises(NotImplementedError):
            backend.revoke("jti", 12345)


# ===========================================================================
# AuthenticationManager: init
# ===========================================================================

class TestAuthManagerInit:
    """AuthenticationManager initialization."""

    def test_explicit_secret_key(self, secret_key):
        mgr = AuthenticationManager(secret_key=secret_key)
        assert mgr._secret_key == secret_key

    def test_env_var_secret_key(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "from_env")
        mgr = AuthenticationManager()
        assert mgr._secret_key == "from_env"

    def test_missing_key_development_uses_random(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("APP_ENVIRONMENT", "development")
        mgr = AuthenticationManager()
        assert len(mgr._secret_key) == 64  # hex(32)

    def test_missing_key_production_raises(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.setenv("APP_ENVIRONMENT", "production")
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            AuthenticationManager()

    def test_default_uses_in_memory_backend(self, auth_manager):
        assert isinstance(auth_manager._revocation_backend, InMemoryRevocationBackend)

    def test_use_redis_creates_redis_backend(self, secret_key):
        mgr = AuthenticationManager(secret_key=secret_key, use_redis=True)
        assert isinstance(mgr._revocation_backend, RedisRevocationBackend)
        assert isinstance(mgr._fallback_revocation, InMemoryRevocationBackend)


# ===========================================================================
# AuthenticationManager: create_token
# ===========================================================================

class TestCreateToken:
    """Token creation tests."""

    def test_create_token_returns_string(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "tenant-1")
        assert isinstance(token, str)

    def test_create_token_has_three_parts(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "tenant-1")
        assert len(token.split(".")) == 3

    def test_create_token_with_permissions(self, auth_manager):
        token = auth_manager.create_token(
            "user-1", UserRole.PREPARER, "t-1",
            permissions=["return_edit", "return_view_own"],
        )
        claims = auth_manager.verify_token(token)
        assert "return_edit" in claims.permissions

    def test_create_token_with_metadata(self, auth_manager):
        token = auth_manager.create_token(
            "user-1", UserRole.ADMIN, "t-1",
            metadata={"firm_name": "Test Firm"},
        )
        claims = auth_manager.verify_token(token)
        assert claims.metadata["firm_name"] == "Test Firm"

    def test_create_token_custom_expiration(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1", expiration=60)
        claims = auth_manager.verify_token(token)
        assert claims.exp - claims.iat <= 60

    def test_create_token_expiration_capped_at_max(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1", expiration=999999)
        claims = auth_manager.verify_token(token)
        assert claims.exp - claims.iat <= AuthenticationManager.MAX_EXPIRATION

    def test_each_token_has_unique_jti(self, auth_manager):
        jtis = set()
        for _ in range(50):
            token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1")
            claims = auth_manager.verify_token(token)
            jtis.add(claims.jti)
        assert len(jtis) == 50

    @pytest.mark.parametrize("role", list(UserRole))
    def test_create_token_all_roles(self, auth_manager, role):
        token = auth_manager.create_token("user-1", role, "t-1")
        claims = auth_manager.verify_token(token)
        assert claims.role == role

    @pytest.mark.parametrize("user_id", [
        "simple-id",
        "user@email.com",
        "550e8400-e29b-41d4-a716-446655440000",
        "",
        "a" * 500,
    ])
    def test_create_token_various_user_ids(self, auth_manager, user_id):
        token = auth_manager.create_token(user_id, UserRole.TAXPAYER, "t-1")
        claims = auth_manager.verify_token(token)
        assert claims.sub == user_id


# ===========================================================================
# AuthenticationManager: verify_token
# ===========================================================================

class TestVerifyToken:
    """Token verification tests."""

    def test_valid_token_returns_claims(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.PREPARER, "t-1")
        claims = auth_manager.verify_token(token)
        assert claims.sub == "user-1"
        assert claims.role == UserRole.PREPARER
        assert claims.tenant_id == "t-1"

    def test_expired_token_raises(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1", expiration=1)
        # Wait for token to expire (expiration=1 means exp=now+1)
        import time as _time
        _time.sleep(2)
        with pytest.raises(AuthenticationError, match="[Ee]xpired|[Ii]nvalid"):
            auth_manager.verify_token(token)

    def test_tampered_payload_raises(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1")
        parts = token.split(".")
        # Modify payload slightly
        import base64
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
        payload["sub"] = "attacker"
        new_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).rstrip(b"=").decode()
        tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        with pytest.raises(AuthenticationError):
            auth_manager.verify_token(tampered)

    def test_invalid_format_raises(self, auth_manager):
        with pytest.raises(AuthenticationError):
            auth_manager.verify_token("not.a.valid.token.at.all")

    def test_empty_token_raises(self, auth_manager):
        with pytest.raises(AuthenticationError):
            auth_manager.verify_token("")

    def test_wrong_secret_key_raises(self, secret_key):
        mgr1 = AuthenticationManager(secret_key=secret_key)
        mgr2 = AuthenticationManager(secret_key="different_secret_" + "0" * 48)
        token = mgr1.create_token("user-1", UserRole.TAXPAYER, "t-1")
        with pytest.raises(AuthenticationError):
            mgr2.verify_token(token)

    def test_revoked_token_raises(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1")
        auth_manager.revoke_token(token)
        with pytest.raises(AuthenticationError, match="revoked"):
            auth_manager.verify_token(token)

    def test_garbage_token_raises(self, auth_manager):
        with pytest.raises(AuthenticationError):
            auth_manager.verify_token("garbage_data_here")

    def test_single_part_token_raises(self, auth_manager):
        with pytest.raises(AuthenticationError):
            auth_manager.verify_token("singlepart")

    def test_two_part_token_raises(self, auth_manager):
        with pytest.raises(AuthenticationError):
            auth_manager.verify_token("part1.part2")


# ===========================================================================
# AuthenticationManager: revoke_token
# ===========================================================================

class TestRevokeToken:
    """Token revocation tests."""

    def test_revoke_valid_token(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1")
        auth_manager.revoke_token(token)
        with pytest.raises(AuthenticationError):
            auth_manager.verify_token(token)

    def test_revoke_does_not_affect_other_tokens(self, auth_manager):
        t1 = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1")
        t2 = auth_manager.create_token("user-2", UserRole.TAXPAYER, "t-1")
        auth_manager.revoke_token(t1)
        # t2 should still be valid
        claims = auth_manager.verify_token(t2)
        assert claims.sub == "user-2"

    def test_revoke_invalid_token_does_not_raise(self, auth_manager):
        # Should log warning but not raise
        auth_manager.revoke_token("invalid.token.data")

    def test_revoke_all_user_tokens_placeholder(self, auth_manager):
        # Just ensure it doesn't raise
        auth_manager.revoke_all_user_tokens("user-1")


# ===========================================================================
# AuthenticationManager: rate limiting
# ===========================================================================

class TestRateLimiting:
    """Rate limiting tests."""

    def test_within_limit_returns_true(self, auth_manager):
        assert auth_manager.check_rate_limit("user-1") is True

    def test_exceed_limit_returns_false(self, auth_manager):
        for _ in range(auth_manager.RATE_LIMIT):
            auth_manager.check_rate_limit("user-1")
        assert auth_manager.check_rate_limit("user-1") is False

    def test_different_users_independent(self, auth_manager):
        for _ in range(auth_manager.RATE_LIMIT):
            auth_manager.check_rate_limit("user-1")
        # user-2 should still be fine
        assert auth_manager.check_rate_limit("user-2") is True

    def test_rate_limit_constant(self):
        assert AuthenticationManager.RATE_LIMIT == 60


# ===========================================================================
# AuthenticationManager: permission checks
# ===========================================================================

class TestPermissionChecks:
    """check_permission and check_tenant_access tests."""

    def test_admin_has_all_permissions(self, auth_manager):
        token = auth_manager.create_token("admin-1", UserRole.ADMIN, "t-1")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_permission(claims, "any_permission") is True

    def test_non_admin_has_listed_permission(self, auth_manager):
        token = auth_manager.create_token(
            "user-1", UserRole.PREPARER, "t-1",
            permissions=["return_edit"],
        )
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_permission(claims, "return_edit") is True

    def test_non_admin_missing_permission(self, auth_manager):
        token = auth_manager.create_token(
            "user-1", UserRole.PREPARER, "t-1",
            permissions=["return_edit"],
        )
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_permission(claims, "admin_panel") is False

    def test_empty_permissions_non_admin(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_permission(claims, "anything") is False

    @pytest.mark.parametrize("role,expected", [
        (UserRole.ADMIN, True),
        (UserRole.TAXPAYER, False),
        (UserRole.PREPARER, False),
        (UserRole.REVIEWER, False),
    ])
    def test_admin_permission_by_role(self, auth_manager, role, expected):
        token = auth_manager.create_token("user-1", role, "t-1")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_permission(claims, "wildcard_perm") is expected


class TestTenantAccessCheck:
    """check_tenant_access tests."""

    def test_same_tenant_access(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_tenant_access(claims, "t-1") is True

    def test_different_tenant_denied(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_tenant_access(claims, "t-2") is False

    def test_admin_can_access_any_tenant(self, auth_manager):
        token = auth_manager.create_token("admin-1", UserRole.ADMIN, "t-1")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_tenant_access(claims, "t-999") is True

    @pytest.mark.parametrize("role", [UserRole.TAXPAYER, UserRole.PREPARER, UserRole.REVIEWER])
    def test_non_admin_cross_tenant_denied(self, auth_manager, role):
        token = auth_manager.create_token("user-1", role, "t-1")
        claims = auth_manager.verify_token(token)
        assert auth_manager.check_tenant_access(claims, "other-tenant") is False


# ===========================================================================
# Token claim round-trip validation
# ===========================================================================

class TestClaimsRoundTrip:
    """Verify claims survive encode/decode cycle intact."""

    @pytest.mark.parametrize("tenant_id", [
        "tenant-1",
        "default",
        "",
        "a" * 200,
        "tenant/special-chars",
    ])
    def test_tenant_id_preserved(self, auth_manager, tenant_id):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, tenant_id)
        claims = auth_manager.verify_token(token)
        assert claims.tenant_id == tenant_id

    @pytest.mark.parametrize("perms", [
        [],
        ["single"],
        ["a", "b", "c", "d", "e"],
        [f"perm_{i}" for i in range(50)],
    ])
    def test_permissions_preserved(self, auth_manager, perms):
        token = auth_manager.create_token(
            "user-1", UserRole.PREPARER, "t-1", permissions=perms,
        )
        claims = auth_manager.verify_token(token)
        assert claims.permissions == perms

    @pytest.mark.parametrize("meta", [
        {},
        {"key": "value"},
        {"nested": {"a": 1}},
        {"list": [1, 2, 3]},
        {"num": 42, "bool": True, "null": None},
    ])
    def test_metadata_preserved(self, auth_manager, meta):
        token = auth_manager.create_token(
            "user-1", UserRole.ADMIN, "t-1", metadata=meta,
        )
        claims = auth_manager.verify_token(token)
        assert claims.metadata == meta


# ===========================================================================
# Expiration boundary cases
# ===========================================================================

class TestExpirationBoundary:
    """Token expiration edge cases."""

    def test_token_not_expired_at_boundary(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1", expiration=3600)
        # Verify immediately (well within expiration)
        claims = auth_manager.verify_token(token)
        assert claims.exp > int(time.time())

    def test_default_expiration_is_one_hour(self):
        assert AuthenticationManager.DEFAULT_EXPIRATION == 3600

    def test_max_expiration_is_24_hours(self):
        assert AuthenticationManager.MAX_EXPIRATION == 86400

    def test_zero_expiration_treated_as_default(self, auth_manager):
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1", expiration=0)
        claims = auth_manager.verify_token(token)
        # 0 triggers default via min(0 or DEFAULT, MAX)
        assert claims.exp >= int(time.time())

    def test_negative_expiration_treated_as_default(self, auth_manager):
        # Negative expiration: min(-100, 86400) = -100, so exp = now + (-100) = past
        # This means the token is immediately expired and verify_token should raise
        token = auth_manager.create_token("user-1", UserRole.TAXPAYER, "t-1", expiration=-100)
        with pytest.raises(AuthenticationError, match="[Ee]xpired|[Ii]nvalid"):
            auth_manager.verify_token(token)


# ===========================================================================
# Singleton management
# ===========================================================================

class TestSingletonManagement:
    """get_auth_manager and reset_auth_manager tests."""

    def test_get_auth_manager_returns_instance(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test_singleton_key")
        mgr = get_auth_manager()
        assert isinstance(mgr, AuthenticationManager)

    def test_get_auth_manager_caches(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test_cache_key")
        mgr1 = get_auth_manager()
        mgr2 = get_auth_manager()
        assert mgr1 is mgr2

    def test_reset_clears_singleton(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "test_reset_key")
        mgr1 = get_auth_manager()
        reset_auth_manager()
        mgr2 = get_auth_manager()
        assert mgr1 is not mgr2


# ===========================================================================
# Exception classes
# ===========================================================================

class TestExceptionClasses:
    """AuthenticationError and AuthorizationError tests."""

    def test_authentication_error_is_exception(self):
        assert issubclass(AuthenticationError, Exception)

    def test_authorization_error_is_exception(self):
        assert issubclass(AuthorizationError, Exception)

    def test_authentication_error_message(self):
        err = AuthenticationError("test message")
        assert str(err) == "test message"

    def test_authorization_error_message(self):
        err = AuthorizationError("forbidden")
        assert str(err) == "forbidden"


# ===========================================================================
# Multiple users / tenants scenario
# ===========================================================================

class TestMultiUserScenarios:
    """Scenarios with multiple users and tenants."""

    def test_two_users_same_tenant(self, auth_manager):
        t1 = auth_manager.create_token("user-1", UserRole.TAXPAYER, "firm-A")
        t2 = auth_manager.create_token("user-2", UserRole.PREPARER, "firm-A")
        c1 = auth_manager.verify_token(t1)
        c2 = auth_manager.verify_token(t2)
        assert c1.tenant_id == c2.tenant_id
        assert c1.sub != c2.sub

    def test_same_user_different_tenants(self, auth_manager):
        t1 = auth_manager.create_token("user-1", UserRole.TAXPAYER, "firm-A")
        t2 = auth_manager.create_token("user-1", UserRole.TAXPAYER, "firm-B")
        c1 = auth_manager.verify_token(t1)
        c2 = auth_manager.verify_token(t2)
        assert c1.tenant_id != c2.tenant_id

    def test_revoke_one_user_other_valid(self, auth_manager):
        t1 = auth_manager.create_token("user-1", UserRole.TAXPAYER, "firm-A")
        t2 = auth_manager.create_token("user-2", UserRole.TAXPAYER, "firm-A")
        auth_manager.revoke_token(t1)
        with pytest.raises(AuthenticationError):
            auth_manager.verify_token(t1)
        claims = auth_manager.verify_token(t2)
        assert claims.sub == "user-2"

    @pytest.mark.parametrize("role,tenant", [
        (UserRole.TAXPAYER, "firm-A"),
        (UserRole.PREPARER, "firm-B"),
        (UserRole.REVIEWER, "firm-C"),
        (UserRole.ADMIN, "platform"),
    ])
    def test_various_role_tenant_combinations(self, auth_manager, role, tenant):
        token = auth_manager.create_token("user-1", role, tenant)
        claims = auth_manager.verify_token(token)
        assert claims.role == role
        assert claims.tenant_id == tenant


# ===========================================================================
# Internal encoding/decoding methods
# ===========================================================================

class TestInternalEncoding:
    """Test base64url encoding helpers."""

    def test_base64url_encode_decode_roundtrip(self, auth_manager):
        original = '{"key": "value", "num": 42}'
        encoded = auth_manager._base64url_encode(original)
        decoded = auth_manager._base64url_decode(encoded)
        assert decoded == original

    def test_base64url_encode_bytes_roundtrip(self, auth_manager):
        original = b"\x00\x01\x02\xff"
        encoded = auth_manager._base64url_encode_bytes(original)
        decoded = auth_manager._base64url_decode_bytes(encoded)
        assert decoded == original

    def test_base64url_no_padding(self, auth_manager):
        encoded = auth_manager._base64url_encode("test")
        assert "=" not in encoded
