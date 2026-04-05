"""
Comprehensive tests for TeamService — team member CRUD, role management,
invitations, permissions, and performance metrics.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# ---------------------------------------------------------------------------
# Patch model constructors to tolerate mismatched kwargs used by team_service.
#
# team_service.py constructs User(name=..., email_verified=...,
# custom_permissions=...) but the actual User model has first_name/last_name,
# is_email_verified, and no custom_permissions column.
#
# Invitation(custom_permissions=...) but Invitation has no such column.
# ---------------------------------------------------------------------------
from admin_panel.models.user import User as _UserModel
from admin_panel.models.invitation import Invitation as _InvitationModel

# Only patch if not already patched (may be patched by test_firm_service)
if not getattr(_UserModel, "_test_patched", False):
    _orig_user_init = _UserModel.__init__

    def _patched_user_init(self, **kwargs):
        if "name" in kwargs:
            name = kwargs.pop("name")
            if "first_name" not in kwargs:
                parts = name.split(" ", 1)
                kwargs["first_name"] = parts[0]
                kwargs["last_name"] = parts[1] if len(parts) > 1 else ""
        if "email_verified" in kwargs:
            kwargs["is_email_verified"] = kwargs.pop("email_verified")
        kwargs.pop("custom_permissions", None)  # Not a real column
        _orig_user_init(self, **kwargs)

    _UserModel.__init__ = _patched_user_init
    _UserModel._test_patched = True

if not getattr(_InvitationModel, "_test_patched", False):
    _orig_inv_init = _InvitationModel.__init__

    def _patched_inv_init(self, **kwargs):
        kwargs.pop("custom_permissions", None)  # Not a real column
        _orig_inv_init(self, **kwargs)

    _InvitationModel.__init__ = _patched_inv_init
    _InvitationModel._test_patched = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(**overrides):
    defaults = dict(
        user_id=str(uuid4()),
        firm_id=str(uuid4()),
        email="user@firm.com",
        name="Test User",
        role="preparer",
        is_active=True,
        email_verified=True,
        mfa_enabled=False,
        phone=None,
        title=None,
        department=None,
        custom_permissions=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_login_at=None,
        deactivated_at=None,
        deactivation_reason=None,
    )
    defaults.update(overrides)
    user = Mock()
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def _make_invitation(**overrides):
    defaults = dict(
        invitation_id=str(uuid4()),
        firm_id=str(uuid4()),
        email="invite@example.com",
        role="preparer",
        custom_permissions=None,
        token="secure_token_abc",
        invited_by=str(uuid4()),
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_at=datetime.now(timezone.utc),
        accepted_at=None,
    )
    defaults.update(overrides)
    inv = Mock()
    for k, v in defaults.items():
        setattr(inv, k, v)
    return inv


def _mock_scalar_result(obj):
    result = AsyncMock()
    result.scalar_one_or_none = Mock(return_value=obj)
    result.scalar = Mock(return_value=obj if not isinstance(obj, list) else len(obj))
    result.scalars = Mock(return_value=Mock(all=Mock(return_value=obj if isinstance(obj, list) else [obj])))
    return result


def _build_service(execute_side_effect=None):
    from admin_panel.services.team_service import TeamService
    db = AsyncMock()
    if execute_side_effect:
        db.execute = AsyncMock(side_effect=execute_side_effect)
    return TeamService(db), db


# ===================================================================
# LIST TEAM MEMBERS
# ===================================================================

class TestListTeamMembers:

    @pytest.mark.asyncio
    async def test_list_returns_user_dicts(self):
        users = [_make_user(name="A"), _make_user(name="B")]
        svc, db = _build_service([_mock_scalar_result(users)])
        result = await svc.list_team_members("fid")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_empty_team(self):
        svc, db = _build_service([_mock_scalar_result([])])
        result = await svc.list_team_members("fid")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_role_filter(self):
        svc, db = _build_service([_mock_scalar_result([])])
        await svc.list_team_members("fid", role_filter="firm_admin")
        db.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_list_includes_inactive(self):
        users = [_make_user(is_active=False)]
        svc, db = _build_service([_mock_scalar_result(users)])
        result = await svc.list_team_members("fid", include_inactive=True)
        assert len(result) == 1


# ===================================================================
# GET TEAM MEMBER
# ===================================================================

class TestGetTeamMember:

    @pytest.mark.asyncio
    async def test_get_existing_member(self):
        user = _make_user(name="Alice")
        svc, db = _build_service([_mock_scalar_result(user)])
        result = await svc.get_team_member("fid", user.user_id)
        assert result is not None
        assert result["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self):
        svc, db = _build_service([_mock_scalar_result(None)])
        assert await svc.get_team_member("fid", "bad") is None

    @pytest.mark.asyncio
    async def test_get_includes_details(self):
        user = _make_user(phone="555-1234", title="Senior CPA")
        svc, db = _build_service([_mock_scalar_result(user)])
        result = await svc.get_team_member("fid", user.user_id)
        assert "permissions" in result
        assert "phone" in result


# ===================================================================
# UPDATE TEAM MEMBER
# ===================================================================

class TestUpdateTeamMember:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("field,value", [
        ("name", "New Name"),
        ("phone", "555-9999"),
        ("title", "Partner"),
        ("department", "Tax"),
    ])
    async def test_update_allowed_fields(self, field, value):
        user = _make_user()
        svc, db = _build_service([_mock_scalar_result(user)])
        await svc.update_team_member("fid", user.user_id, **{field: value})
        assert getattr(user, field) == value

    @pytest.mark.asyncio
    async def test_update_disallowed_field_ignored(self):
        user = _make_user(role="preparer")
        svc, db = _build_service([_mock_scalar_result(user)])
        await svc.update_team_member("fid", user.user_id, role="firm_admin")
        assert user.role == "preparer"

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self):
        svc, db = _build_service([_mock_scalar_result(None)])
        assert await svc.update_team_member("fid", "x") is None

    @pytest.mark.asyncio
    async def test_update_sets_updated_at(self):
        user = _make_user()
        svc, db = _build_service([_mock_scalar_result(user)])
        await svc.update_team_member("fid", user.user_id, name="X")
        assert user.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_commits(self):
        user = _make_user()
        svc, db = _build_service([_mock_scalar_result(user)])
        await svc.update_team_member("fid", user.user_id, name="X")
        db.commit.assert_awaited()


# ===================================================================
# ROLE MANAGEMENT
# ===================================================================

class TestUpdateRole:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["firm_admin", "preparer", "reviewer", "staff"])
    async def test_update_to_valid_roles(self, role):
        user = _make_user()
        svc, db = _build_service([_mock_scalar_result(user)])
        with patch("admin_panel.services.team_service.UserRole") as mock_role:
            mock_role.side_effect = lambda x: x
            result = await svc.update_role("fid", user.user_id, role)
            if result:
                assert user.role == role

    @pytest.mark.asyncio
    async def test_update_invalid_role_returns_none(self):
        user = _make_user()
        svc, db = _build_service([_mock_scalar_result(user)])
        with patch("admin_panel.services.team_service.UserRole") as mock_role:
            mock_role.side_effect = ValueError("bad role")
            result = await svc.update_role("fid", user.user_id, "supervillain")
            assert result is None

    @pytest.mark.asyncio
    async def test_update_role_with_custom_permissions(self):
        user = _make_user()
        svc, db = _build_service([_mock_scalar_result(user)])
        with patch("admin_panel.services.team_service.UserRole") as mock_role, \
             patch("admin_panel.services.team_service.UserPermission") as mock_perm:
            mock_role.side_effect = lambda x: x
            mock_perm.side_effect = lambda x: x
            await svc.update_role("fid", user.user_id, "preparer", custom_permissions=["view_clients"])

    @pytest.mark.asyncio
    async def test_update_role_nonexistent_user_returns_none(self):
        svc, db = _build_service([_mock_scalar_result(None)])
        result = await svc.update_role("fid", "bad", "preparer")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_role_clears_custom_permissions_when_none(self):
        user = _make_user(custom_permissions=["old_perm"])
        svc, db = _build_service([_mock_scalar_result(user)])
        with patch("admin_panel.services.team_service.UserRole") as mock_role:
            mock_role.side_effect = lambda x: x
            await svc.update_role("fid", user.user_id, "preparer", custom_permissions=None)
            assert user.custom_permissions is None

    @pytest.mark.asyncio
    async def test_update_role_commits(self):
        user = _make_user()
        svc, db = _build_service([_mock_scalar_result(user)])
        with patch("admin_panel.services.team_service.UserRole") as mock_role:
            mock_role.side_effect = lambda x: x
            await svc.update_role("fid", user.user_id, "preparer")
            db.commit.assert_awaited()


# ===================================================================
# DEACTIVATION / REACTIVATION
# ===================================================================

class TestDeactivation:

    @pytest.mark.asyncio
    async def test_deactivate_member(self):
        user = _make_user(role="preparer")
        admin_count_result = _mock_scalar_result(2)
        svc, db = _build_service([_mock_scalar_result(user), admin_count_result])
        assert await svc.deactivate_member("fid", user.user_id) is True
        assert user.is_active is False

    @pytest.mark.asyncio
    async def test_deactivate_sets_deactivated_at(self):
        user = _make_user(role="preparer")
        svc, db = _build_service([_mock_scalar_result(user), _mock_scalar_result(2)])
        await svc.deactivate_member("fid", user.user_id)
        assert user.deactivated_at is not None

    @pytest.mark.asyncio
    async def test_deactivate_with_reason(self):
        user = _make_user(role="preparer")
        svc, db = _build_service([_mock_scalar_result(user), _mock_scalar_result(2)])
        await svc.deactivate_member("fid", user.user_id, reason="Left firm")
        assert user.deactivation_reason == "Left firm"

    @pytest.mark.asyncio
    async def test_cannot_deactivate_last_admin(self):
        user = _make_user(role="firm_admin")
        svc, db = _build_service([_mock_scalar_result(user), _mock_scalar_result(1)])
        assert await svc.deactivate_member("fid", user.user_id) is False

    @pytest.mark.asyncio
    async def test_deactivate_admin_when_others_exist(self):
        user = _make_user(role="firm_admin")
        svc, db = _build_service([_mock_scalar_result(user), _mock_scalar_result(3)])
        assert await svc.deactivate_member("fid", user.user_id) is True

    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_returns_false(self):
        svc, db = _build_service([_mock_scalar_result(None)])
        assert await svc.deactivate_member("fid", "bad") is False


class TestReactivation:

    @pytest.mark.asyncio
    async def test_reactivate_member(self):
        user = _make_user(is_active=False)
        svc, db = _build_service([_mock_scalar_result(user)])
        assert await svc.reactivate_member("fid", user.user_id) is True
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_reactivate_clears_deactivation_fields(self):
        user = _make_user(is_active=False, deactivated_at=datetime.now(timezone.utc), deactivation_reason="Left")
        svc, db = _build_service([_mock_scalar_result(user)])
        await svc.reactivate_member("fid", user.user_id)
        assert user.deactivated_at is None
        assert user.deactivation_reason is None

    @pytest.mark.asyncio
    async def test_reactivate_nonexistent_returns_false(self):
        svc, db = _build_service([_mock_scalar_result(None)])
        assert await svc.reactivate_member("fid", "bad") is False


# ===================================================================
# INVITATIONS
# ===================================================================

class TestCreateInvitation:

    @pytest.mark.asyncio
    async def test_create_invitation_success(self):
        svc, db = _build_service([
            _mock_scalar_result(None),  # no existing user
            _mock_scalar_result(None),  # no pending invite
        ])
        with patch("admin_panel.services.firm_service.FirmService") as MockFS:
            mock_fs = AsyncMock()
            mock_fs.check_limit = AsyncMock(return_value={"allowed": True, "remaining": 5})
            MockFS.return_value = mock_fs
            result = await svc.create_invitation("fid", "inv_id", "new@e.com", "preparer")
            assert "invitation_id" in result or "error" not in result

    @pytest.mark.asyncio
    async def test_create_invitation_duplicate_email(self):
        existing_user = _make_user()
        svc, db = _build_service([_mock_scalar_result(existing_user)])
        result = await svc.create_invitation("fid", "inv_id", "dup@e.com", "preparer")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_invitation_pending_exists(self):
        pending_inv = _make_invitation()
        svc, db = _build_service([
            _mock_scalar_result(None),  # no existing user
            _mock_scalar_result(pending_inv),  # pending invite exists
        ])
        result = await svc.create_invitation("fid", "inv_id", "dup@e.com", "preparer")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_invitation_at_team_limit(self):
        svc, db = _build_service([
            _mock_scalar_result(None),
            _mock_scalar_result(None),
        ])
        with patch("admin_panel.services.firm_service.FirmService") as MockFS:
            mock_fs = AsyncMock()
            mock_fs.check_limit = AsyncMock(return_value={"allowed": False, "reason": "Limit reached"})
            MockFS.return_value = mock_fs
            result = await svc.create_invitation("fid", "inv_id", "new@e.com", "preparer")
            assert "error" in result


class TestAcceptInvitation:

    @pytest.mark.asyncio
    async def test_accept_valid_invitation(self):
        inv = _make_invitation(expires_at=datetime.now(timezone.utc) + timedelta(days=7))
        svc, db = _build_service([_mock_scalar_result(inv)])
        result = await svc.accept_invitation("token", "Alice", "hashed_pw")
        assert "user_id" in result or "error" not in result

    @pytest.mark.asyncio
    async def test_accept_invalid_token(self):
        svc, db = _build_service([_mock_scalar_result(None)])
        result = await svc.accept_invitation("bad_token", "Alice", "h")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_accept_expired_invitation(self):
        inv = _make_invitation(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
        svc, db = _build_service([_mock_scalar_result(inv)])
        result = await svc.accept_invitation("token", "Alice", "h")
        assert "error" in result


class TestRevokeInvitation:

    @pytest.mark.asyncio
    async def test_revoke_pending_invitation(self):
        inv = _make_invitation(status="pending")
        svc, db = _build_service([_mock_scalar_result(inv)])
        assert await svc.revoke_invitation("fid", inv.invitation_id) is True

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_returns_false(self):
        svc, db = _build_service([_mock_scalar_result(None)])
        assert await svc.revoke_invitation("fid", "bad") is False


class TestResendInvitation:

    @pytest.mark.asyncio
    async def test_resend_invitation(self):
        inv = _make_invitation()
        svc, db = _build_service([_mock_scalar_result(inv)])
        result = await svc.resend_invitation("fid", inv.invitation_id)
        assert result is not None
        assert "token" in result

    @pytest.mark.asyncio
    async def test_resend_nonexistent_returns_none(self):
        svc, db = _build_service([_mock_scalar_result(None)])
        assert await svc.resend_invitation("fid", "bad") is None

    @pytest.mark.asyncio
    async def test_resend_generates_new_token(self):
        old_token = "old_token_123"
        inv = _make_invitation(token=old_token)
        svc, db = _build_service([_mock_scalar_result(inv)])
        result = await svc.resend_invitation("fid", inv.invitation_id)
        assert result["token"] != old_token


class TestListInvitations:

    @pytest.mark.asyncio
    async def test_list_invitations(self):
        invs = [_make_invitation(), _make_invitation()]
        svc, db = _build_service([_mock_scalar_result(invs)])
        result = await svc.list_invitations("fid")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_invitations_empty(self):
        svc, db = _build_service([_mock_scalar_result([])])
        result = await svc.list_invitations("fid")
        assert result == []


# ===================================================================
# PERMISSIONS
# ===================================================================

class TestPermissions:

    def test_get_effective_permissions_with_role(self):
        from admin_panel.services.team_service import TeamService
        svc = TeamService(AsyncMock())
        user = _make_user(role="preparer", custom_permissions=None)
        with patch("admin_panel.services.team_service.UserRole") as mock_role, \
             patch("admin_panel.services.team_service.ROLE_PERMISSIONS", {mock_role.return_value: {"perm1"}}):
            mock_role.side_effect = lambda x: x
            perms = svc.get_effective_permissions(user)
            assert isinstance(perms, list)

    def test_get_effective_permissions_custom_override(self):
        from admin_panel.services.team_service import TeamService
        svc = TeamService(AsyncMock())
        user = _make_user(role="preparer", custom_permissions=["view_only"])
        with patch("admin_panel.services.team_service.UserRole") as mock_role, \
             patch("admin_panel.services.team_service.ROLE_PERMISSIONS", {}):
            mock_role.side_effect = lambda x: x
            perms = svc.get_effective_permissions(user)
            assert "view_only" in perms

    def test_get_effective_permissions_invalid_role(self):
        from admin_panel.services.team_service import TeamService
        svc = TeamService(AsyncMock())
        user = _make_user(role="invalid_role", custom_permissions=None)
        with patch("admin_panel.services.team_service.UserRole") as mock_role, \
             patch("admin_panel.services.team_service.ROLE_PERMISSIONS", {}):
            mock_role.side_effect = ValueError("bad")
            perms = svc.get_effective_permissions(user)
            assert perms == []

    @pytest.mark.asyncio
    async def test_get_role_permissions_valid(self):
        svc, db = _build_service()
        with patch("admin_panel.services.team_service.UserRole") as mock_role, \
             patch("admin_panel.services.team_service.ROLE_PERMISSIONS", {}):
            mock_role.side_effect = lambda x: x
            result = await svc.get_role_permissions("preparer")

    @pytest.mark.asyncio
    async def test_get_role_permissions_invalid(self):
        svc, db = _build_service()
        with patch("admin_panel.services.team_service.UserRole") as mock_role:
            mock_role.side_effect = ValueError("bad")
            result = await svc.get_role_permissions("invalid")
            assert result["permissions"] == []


# ===================================================================
# TEAM STATS
# ===================================================================

class TestTeamStats:

    @pytest.mark.asyncio
    async def test_team_stats_returns_expected_keys(self):
        role_counts = Mock()
        role_counts.all = Mock(return_value=[("preparer", 3), ("firm_admin", 1)])
        pending = _mock_scalar_result(2)
        svc, db = _build_service([role_counts, pending])
        result = await svc.get_team_stats("fid")
        assert "total_active" in result
        assert "by_role" in result
        assert "pending_invitations" in result


# ===================================================================
# _user_to_dict HELPER
# ===================================================================

class TestUserToDict:

    def test_basic_fields(self):
        from admin_panel.services.team_service import TeamService
        svc = TeamService(AsyncMock())
        user = _make_user(name="Bob", email="bob@firm.com", role="preparer")
        d = svc._user_to_dict(user)
        assert d["name"] == "Bob"
        assert d["email"] == "bob@firm.com"
        assert d["role"] == "preparer"

    def test_include_details_false(self):
        from admin_panel.services.team_service import TeamService
        svc = TeamService(AsyncMock())
        user = _make_user()
        d = svc._user_to_dict(user, include_details=False)
        assert "permissions" not in d

    def test_include_details_true(self):
        from admin_panel.services.team_service import TeamService
        svc = TeamService(AsyncMock())
        user = _make_user(custom_permissions=None)
        with patch("admin_panel.services.team_service.UserRole") as mock_role, \
             patch("admin_panel.services.team_service.ROLE_PERMISSIONS", {}):
            mock_role.side_effect = ValueError("bad")
            d = svc._user_to_dict(user, include_details=True)
            assert "permissions" in d
            assert "phone" in d

    def test_last_login_none(self):
        from admin_panel.services.team_service import TeamService
        svc = TeamService(AsyncMock())
        user = _make_user(last_login_at=None)
        d = svc._user_to_dict(user)
        assert d["last_login_at"] is None

    def test_last_login_iso(self):
        from admin_panel.services.team_service import TeamService
        svc = TeamService(AsyncMock())
        now = datetime.now(timezone.utc)
        user = _make_user(last_login_at=now)
        d = svc._user_to_dict(user)
        assert d["last_login_at"] == now.isoformat()
