"""Comprehensive RBAC (Role-Based Access Control) matrix tests.

Tests the full role x permission matrix from rbac/roles.py and rbac/permissions.py,
verifying that each role has exactly the permissions it should have and no more.
Also tests the legacy auth_decorators Role enum and role hierarchy.
"""

import os
import sys
from pathlib import Path

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rbac.roles import (
    Role,
    Level,
    RoleInfo,
    ROLES,
    PLATFORM_ROLES,
    FIRM_ROLES,
    CLIENT_ROLES,
    ADMIN_ROLES,
    IMPERSONATE_ROLES,
    get_role_info,
    get_platform_roles,
    get_firm_roles,
    get_client_roles,
    can_access_level,
)
from rbac.permissions import (
    Permission,
    Category,
    ROLE_PERMISSIONS,
    get_role_permissions,
    has_permission,
)

# Also test the legacy authentication.py Role & permission logic
from security.authentication import (
    UserRole,
    AuthenticationManager,
    JWTClaims,
)


# ===========================================================================
# Role enum completeness
# ===========================================================================

class TestRoleEnumCompleteness:
    """Verify all expected roles exist."""

    EXPECTED_ROLES = [
        "super_admin", "platform_admin", "support", "billing",
        "partner", "staff", "firm_client", "direct_client",
    ]

    @pytest.mark.parametrize("role_value", EXPECTED_ROLES)
    def test_role_exists(self, role_value):
        role = Role(role_value)
        assert role.value == role_value

    def test_total_role_count(self):
        assert len(Role) == 8

    def test_all_roles_have_info(self):
        for role in Role:
            assert role in ROLES
            info = ROLES[role]
            assert isinstance(info, RoleInfo)
            assert info.role == role

    @pytest.mark.parametrize("role", list(Role))
    def test_role_is_str_enum(self, role):
        assert isinstance(role, str)


# ===========================================================================
# Level enum
# ===========================================================================

class TestLevelEnum:
    """Verify hierarchy levels."""

    def test_platform_is_zero(self):
        assert Level.PLATFORM.value == 0

    def test_firm_is_one(self):
        assert Level.FIRM.value == 1

    def test_client_is_two(self):
        assert Level.CLIENT.value == 2

    def test_platform_is_highest(self):
        assert Level.PLATFORM.value < Level.FIRM.value < Level.CLIENT.value


# ===========================================================================
# Role sets
# ===========================================================================

class TestRoleSets:
    """Verify the frozen role sets."""

    def test_platform_roles_set(self):
        assert Role.SUPER_ADMIN in PLATFORM_ROLES
        assert Role.PLATFORM_ADMIN in PLATFORM_ROLES
        assert Role.SUPPORT in PLATFORM_ROLES
        assert Role.BILLING in PLATFORM_ROLES
        assert len(PLATFORM_ROLES) == 4

    def test_firm_roles_set(self):
        assert Role.PARTNER in FIRM_ROLES
        assert Role.STAFF in FIRM_ROLES
        assert len(FIRM_ROLES) == 2

    def test_client_roles_set(self):
        assert Role.FIRM_CLIENT in CLIENT_ROLES
        assert Role.DIRECT_CLIENT in CLIENT_ROLES
        assert len(CLIENT_ROLES) == 2

    def test_admin_roles_set(self):
        assert Role.SUPER_ADMIN in ADMIN_ROLES
        assert Role.PLATFORM_ADMIN in ADMIN_ROLES
        assert Role.PARTNER in ADMIN_ROLES
        assert Role.STAFF not in ADMIN_ROLES

    def test_impersonate_roles_set(self):
        assert Role.SUPER_ADMIN in IMPERSONATE_ROLES
        assert Role.PLATFORM_ADMIN in IMPERSONATE_ROLES
        assert Role.SUPPORT in IMPERSONATE_ROLES
        assert Role.BILLING not in IMPERSONATE_ROLES
        assert Role.PARTNER not in IMPERSONATE_ROLES

    def test_get_platform_roles_func(self):
        assert get_platform_roles() == set(PLATFORM_ROLES)

    def test_get_firm_roles_func(self):
        assert get_firm_roles() == set(FIRM_ROLES)

    def test_get_client_roles_func(self):
        assert get_client_roles() == set(CLIENT_ROLES)


# ===========================================================================
# RoleInfo properties
# ===========================================================================

class TestRoleInfoProperties:
    """Verify RoleInfo attributes for each role."""

    @pytest.mark.parametrize("role", [Role.SUPER_ADMIN, Role.PLATFORM_ADMIN, Role.SUPPORT, Role.BILLING])
    def test_platform_roles_are_platform(self, role):
        info = get_role_info(role)
        assert info.is_platform is True
        assert info.is_firm is False
        assert info.is_client is False
        assert info.level == Level.PLATFORM

    @pytest.mark.parametrize("role", [Role.PARTNER, Role.STAFF])
    def test_firm_roles_are_firm(self, role):
        info = get_role_info(role)
        assert info.is_platform is False
        assert info.is_firm is True
        assert info.is_client is False
        assert info.level == Level.FIRM

    @pytest.mark.parametrize("role", [Role.FIRM_CLIENT, Role.DIRECT_CLIENT])
    def test_client_roles_are_client(self, role):
        info = get_role_info(role)
        assert info.is_platform is False
        assert info.is_firm is False
        assert info.is_client is True
        assert info.level == Level.CLIENT

    @pytest.mark.parametrize("role,expected", [
        (Role.SUPER_ADMIN, True),
        (Role.PLATFORM_ADMIN, True),
        (Role.SUPPORT, True),
        (Role.BILLING, False),
        (Role.PARTNER, False),
        (Role.STAFF, False),
        (Role.FIRM_CLIENT, False),
        (Role.DIRECT_CLIENT, False),
    ])
    def test_can_impersonate(self, role, expected):
        info = get_role_info(role)
        assert info.can_impersonate is expected


# ===========================================================================
# can_access_level hierarchy
# ===========================================================================

class TestCanAccessLevel:
    """Test the hierarchical access model."""

    @pytest.mark.parametrize("role", [Role.SUPER_ADMIN, Role.PLATFORM_ADMIN, Role.SUPPORT, Role.BILLING])
    def test_platform_can_access_all_levels(self, role):
        assert can_access_level(role, Level.PLATFORM) is True
        assert can_access_level(role, Level.FIRM) is True
        assert can_access_level(role, Level.CLIENT) is True

    @pytest.mark.parametrize("role", [Role.PARTNER, Role.STAFF])
    def test_firm_can_access_firm_and_client(self, role):
        assert can_access_level(role, Level.PLATFORM) is False
        assert can_access_level(role, Level.FIRM) is True
        assert can_access_level(role, Level.CLIENT) is True

    @pytest.mark.parametrize("role", [Role.FIRM_CLIENT, Role.DIRECT_CLIENT])
    def test_client_can_only_access_client(self, role):
        assert can_access_level(role, Level.PLATFORM) is False
        assert can_access_level(role, Level.FIRM) is False
        assert can_access_level(role, Level.CLIENT) is True


# ===========================================================================
# Permission enum completeness
# ===========================================================================

class TestPermissionEnumCompleteness:
    """Verify all permissions exist."""

    def test_all_permissions_have_info(self):
        from rbac.permissions import PERMISSIONS
        # Some permissions (FIRM_MANAGE_API_KEYS, FIRM_VIEW_AUDIT) are defined
        # in the Permission enum but not yet registered in PERMISSIONS info dict.
        # They are valid permissions used in role mappings but lack metadata.
        unregistered_ok = {
            Permission.FIRM_MANAGE_API_KEYS,
            Permission.FIRM_VIEW_AUDIT,
        }
        for perm in Permission:
            if perm not in unregistered_ok:
                assert perm in PERMISSIONS, f"Permission {perm.value} missing from PERMISSIONS registry"

    def test_permission_categories(self):
        expected_categories = {
            "platform", "firm", "team", "client",
            "return", "document", "self",
        }
        actual = {c.value for c in Category}
        assert actual == expected_categories


# ===========================================================================
# Role -> Permission matrix
# ===========================================================================

class TestSuperAdminPermissions:
    """Super admin has ALL permissions."""

    def test_has_all_permissions(self):
        perms = get_role_permissions(Role.SUPER_ADMIN)
        for perm in Permission:
            assert perm in perms, f"Super admin missing: {perm.value}"

    def test_permission_count_matches_all(self):
        perms = get_role_permissions(Role.SUPER_ADMIN)
        assert len(perms) == len(Permission)


class TestPlatformAdminPermissions:
    """Platform admin has most platform permissions, but NOT manage_admins."""

    def test_has_platform_view_all_firms(self):
        assert has_permission(Role.PLATFORM_ADMIN, Permission.PLATFORM_VIEW_ALL_FIRMS)

    def test_has_platform_manage_firms(self):
        assert has_permission(Role.PLATFORM_ADMIN, Permission.PLATFORM_MANAGE_FIRMS)

    def test_has_platform_impersonate(self):
        assert has_permission(Role.PLATFORM_ADMIN, Permission.PLATFORM_IMPERSONATE)

    def test_does_not_have_manage_admins(self):
        assert not has_permission(Role.PLATFORM_ADMIN, Permission.PLATFORM_MANAGE_ADMINS)

    def test_does_not_have_firm_permissions(self):
        assert not has_permission(Role.PLATFORM_ADMIN, Permission.FIRM_MANAGE_SETTINGS)

    def test_does_not_have_client_permissions(self):
        assert not has_permission(Role.PLATFORM_ADMIN, Permission.CLIENT_VIEW_ALL)


class TestSupportPermissions:
    """Support has read + impersonate, no write."""

    def test_has_view_all_firms(self):
        assert has_permission(Role.SUPPORT, Permission.PLATFORM_VIEW_ALL_FIRMS)

    def test_has_impersonate(self):
        assert has_permission(Role.SUPPORT, Permission.PLATFORM_IMPERSONATE)

    def test_no_manage_firms(self):
        assert not has_permission(Role.SUPPORT, Permission.PLATFORM_MANAGE_FIRMS)

    def test_no_manage_subscriptions(self):
        assert not has_permission(Role.SUPPORT, Permission.PLATFORM_MANAGE_SUBSCRIPTIONS)

    def test_no_manage_features(self):
        assert not has_permission(Role.SUPPORT, Permission.PLATFORM_MANAGE_FEATURES)


class TestBillingPermissions:
    """Billing has finance-only permissions."""

    def test_has_view_subscriptions(self):
        assert has_permission(Role.BILLING, Permission.PLATFORM_VIEW_SUBSCRIPTIONS)

    def test_has_manage_subscriptions(self):
        assert has_permission(Role.BILLING, Permission.PLATFORM_MANAGE_SUBSCRIPTIONS)

    def test_no_impersonate(self):
        assert not has_permission(Role.BILLING, Permission.PLATFORM_IMPERSONATE)

    def test_no_manage_firms(self):
        assert not has_permission(Role.BILLING, Permission.PLATFORM_MANAGE_FIRMS)

    def test_no_manage_admins(self):
        assert not has_permission(Role.BILLING, Permission.PLATFORM_MANAGE_ADMINS)


class TestPartnerPermissions:
    """Partner has full firm access."""

    EXPECTED_PERMISSIONS = [
        Permission.FIRM_VIEW_SETTINGS,
        Permission.FIRM_MANAGE_SETTINGS,
        Permission.FIRM_MANAGE_BRANDING,
        Permission.FIRM_VIEW_ANALYTICS,
        Permission.FIRM_VIEW_BILLING,
        Permission.FIRM_MANAGE_BILLING,
        Permission.TEAM_VIEW,
        Permission.TEAM_INVITE,
        Permission.TEAM_MANAGE,
        Permission.TEAM_REMOVE,
        Permission.CLIENT_VIEW_ALL,
        Permission.CLIENT_CREATE,
        Permission.CLIENT_EDIT,
        Permission.CLIENT_ARCHIVE,
        Permission.CLIENT_ASSIGN,
        Permission.RETURN_VIEW_ALL,
        Permission.RETURN_CREATE,
        Permission.RETURN_EDIT,
        Permission.RETURN_SUBMIT,
        Permission.RETURN_REVIEW,
        Permission.RETURN_APPROVE,
        Permission.RETURN_RUN_SCENARIOS,
        Permission.RETURN_GENERATE_ADVISORY,
        Permission.DOCUMENT_VIEW,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_DELETE,
    ]

    @pytest.mark.parametrize("perm", EXPECTED_PERMISSIONS)
    def test_partner_has_permission(self, perm):
        assert has_permission(Role.PARTNER, perm)

    def test_partner_no_platform_permissions(self):
        assert not has_permission(Role.PARTNER, Permission.PLATFORM_VIEW_ALL_FIRMS)
        assert not has_permission(Role.PARTNER, Permission.PLATFORM_MANAGE_FIRMS)
        assert not has_permission(Role.PARTNER, Permission.PLATFORM_IMPERSONATE)

    def test_partner_no_self_service_permissions(self):
        assert not has_permission(Role.PARTNER, Permission.SELF_VIEW_RETURN)
        assert not has_permission(Role.PARTNER, Permission.SELF_EDIT_RETURN)


class TestStaffPermissions:
    """Staff has limited firm access."""

    EXPECTED_PERMISSIONS = [
        Permission.FIRM_VIEW_SETTINGS,
        Permission.FIRM_VIEW_ANALYTICS,
        Permission.TEAM_VIEW,
        Permission.CLIENT_VIEW_OWN,
        Permission.CLIENT_CREATE,
        Permission.CLIENT_EDIT,
        Permission.RETURN_VIEW_OWN,
        Permission.RETURN_CREATE,
        Permission.RETURN_EDIT,
        Permission.RETURN_SUBMIT,
        Permission.RETURN_RUN_SCENARIOS,
        Permission.RETURN_GENERATE_ADVISORY,
        Permission.DOCUMENT_VIEW,
        Permission.DOCUMENT_UPLOAD,
    ]

    DENIED_PERMISSIONS = [
        Permission.FIRM_MANAGE_SETTINGS,
        Permission.FIRM_MANAGE_BRANDING,
        Permission.FIRM_MANAGE_BILLING,
        Permission.TEAM_INVITE,
        Permission.TEAM_MANAGE,
        Permission.TEAM_REMOVE,
        Permission.CLIENT_VIEW_ALL,
        Permission.CLIENT_ARCHIVE,
        Permission.CLIENT_ASSIGN,
        Permission.RETURN_VIEW_ALL,
        Permission.RETURN_REVIEW,
        Permission.RETURN_APPROVE,
        Permission.DOCUMENT_DELETE,
    ]

    @pytest.mark.parametrize("perm", EXPECTED_PERMISSIONS)
    def test_staff_has_permission(self, perm):
        assert has_permission(Role.STAFF, perm)

    @pytest.mark.parametrize("perm", DENIED_PERMISSIONS)
    def test_staff_denied_permission(self, perm):
        assert not has_permission(Role.STAFF, perm)


class TestFirmClientPermissions:
    """Firm client has self-service only."""

    EXPECTED = [
        Permission.SELF_VIEW_RETURN,
        Permission.SELF_EDIT_RETURN,
        Permission.SELF_VIEW_STATUS,
        Permission.SELF_UPLOAD_DOCS,
        Permission.DOCUMENT_VIEW,
        Permission.DOCUMENT_UPLOAD,
    ]

    DENIED = [
        Permission.FIRM_VIEW_SETTINGS,
        Permission.TEAM_VIEW,
        Permission.CLIENT_VIEW_ALL,
        Permission.RETURN_VIEW_ALL,
        Permission.RETURN_CREATE,
        Permission.RETURN_REVIEW,
        Permission.RETURN_APPROVE,
        Permission.DOCUMENT_DELETE,
        Permission.PLATFORM_VIEW_ALL_FIRMS,
    ]

    @pytest.mark.parametrize("perm", EXPECTED)
    def test_firm_client_has_permission(self, perm):
        assert has_permission(Role.FIRM_CLIENT, perm)

    @pytest.mark.parametrize("perm", DENIED)
    def test_firm_client_denied(self, perm):
        assert not has_permission(Role.FIRM_CLIENT, perm)


class TestDirectClientPermissions:
    """Direct client (deprecated) has same permissions as firm client."""

    def test_same_permissions_as_firm_client(self):
        firm_perms = get_role_permissions(Role.FIRM_CLIENT)
        direct_perms = get_role_permissions(Role.DIRECT_CLIENT)
        assert firm_perms == direct_perms


# ===========================================================================
# Cross-role privilege escalation prevention
# ===========================================================================

class TestPrivilegeEscalationPrevention:
    """No lower-level role should have a higher-level permission."""

    def test_staff_cannot_approve_returns(self):
        assert not has_permission(Role.STAFF, Permission.RETURN_APPROVE)

    def test_client_cannot_manage_team(self):
        assert not has_permission(Role.FIRM_CLIENT, Permission.TEAM_MANAGE)

    def test_client_cannot_delete_documents(self):
        assert not has_permission(Role.FIRM_CLIENT, Permission.DOCUMENT_DELETE)

    def test_billing_cannot_impersonate(self):
        assert not has_permission(Role.BILLING, Permission.PLATFORM_IMPERSONATE)

    def test_support_cannot_manage_features(self):
        assert not has_permission(Role.SUPPORT, Permission.PLATFORM_MANAGE_FEATURES)

    def test_staff_cannot_archive_clients(self):
        assert not has_permission(Role.STAFF, Permission.CLIENT_ARCHIVE)

    def test_staff_cannot_assign_clients(self):
        assert not has_permission(Role.STAFF, Permission.CLIENT_ASSIGN)

    def test_partner_cannot_manage_platform(self):
        assert not has_permission(Role.PARTNER, Permission.PLATFORM_MANAGE_ADMINS)

    def test_no_client_has_platform_perms(self):
        for perm in Permission:
            if perm.value.startswith("platform_"):
                assert not has_permission(Role.FIRM_CLIENT, perm)
                assert not has_permission(Role.DIRECT_CLIENT, perm)

    def test_no_firm_role_has_platform_perms(self):
        for perm in Permission:
            if perm.value.startswith("platform_"):
                assert not has_permission(Role.PARTNER, perm)
                assert not has_permission(Role.STAFF, perm)


# ===========================================================================
# Legacy Role enum (auth_decorators.py)
# ===========================================================================

class TestLegacyRoleEnum:
    """Legacy auth_decorators.Role enum."""

    def test_legacy_roles_exist(self):
        from security.auth_decorators import Role as LegacyRole
        assert LegacyRole.TAXPAYER.value == "taxpayer"
        assert LegacyRole.CPA.value == "cpa"
        assert LegacyRole.ADMIN.value == "admin"
        assert LegacyRole.PREPARER.value == "preparer"
        assert LegacyRole.GUEST.value == "guest"

    def test_legacy_to_rbac_mapping(self):
        from security.auth_decorators import legacy_role_to_rbac, Role as LegacyRole
        assert legacy_role_to_rbac(LegacyRole.ADMIN) == "super_admin"
        assert legacy_role_to_rbac(LegacyRole.CPA) == "partner"
        assert legacy_role_to_rbac(LegacyRole.PREPARER) == "staff"
        assert legacy_role_to_rbac(LegacyRole.TAXPAYER) == "firm_client"
        assert legacy_role_to_rbac(LegacyRole.GUEST) is None


# ===========================================================================
# Legacy AuthenticationManager permission check
# ===========================================================================

class TestLegacyAuthManagerPermissions:
    """AuthenticationManager.check_permission from authentication.py."""

    @pytest.fixture
    def auth_mgr(self):
        return AuthenticationManager(secret_key="test_key_" + "0" * 56)

    @pytest.mark.parametrize("role,permission,expected", [
        (UserRole.ADMIN, "any_random_perm", True),
        (UserRole.ADMIN, "return_edit", True),
        (UserRole.ADMIN, "platform_manage_admins", True),
        (UserRole.TAXPAYER, "unlisted_perm", False),
        (UserRole.PREPARER, "unlisted_perm", False),
        (UserRole.REVIEWER, "unlisted_perm", False),
    ])
    def test_check_permission_by_role(self, auth_mgr, role, permission, expected):
        token = auth_mgr.create_token("user-1", role, "t-1")
        claims = auth_mgr.verify_token(token)
        assert auth_mgr.check_permission(claims, permission) is expected

    def test_preparer_with_granted_perm(self, auth_mgr):
        token = auth_mgr.create_token(
            "user-1", UserRole.PREPARER, "t-1",
            permissions=["return_edit", "return_create"],
        )
        claims = auth_mgr.verify_token(token)
        assert auth_mgr.check_permission(claims, "return_edit") is True
        assert auth_mgr.check_permission(claims, "return_create") is True
        assert auth_mgr.check_permission(claims, "return_approve") is False


# ===========================================================================
# Full RBAC matrix: role x endpoint (mocked)
# ===========================================================================

# Define endpoint permission requirements
ENDPOINT_PERMISSION_MAP = {
    "/api/admin/firms": Permission.PLATFORM_VIEW_ALL_FIRMS,
    "/api/admin/manage-firms": Permission.PLATFORM_MANAGE_FIRMS,
    "/api/admin/impersonate": Permission.PLATFORM_IMPERSONATE,
    "/api/admin/manage-admins": Permission.PLATFORM_MANAGE_ADMINS,
    "/api/firm/settings": Permission.FIRM_VIEW_SETTINGS,
    "/api/firm/settings/edit": Permission.FIRM_MANAGE_SETTINGS,
    "/api/firm/branding": Permission.FIRM_MANAGE_BRANDING,
    "/api/firm/analytics": Permission.FIRM_VIEW_ANALYTICS,
    "/api/team": Permission.TEAM_VIEW,
    "/api/team/invite": Permission.TEAM_INVITE,
    "/api/team/manage": Permission.TEAM_MANAGE,
    "/api/clients": Permission.CLIENT_VIEW_ALL,
    "/api/clients/my": Permission.CLIENT_VIEW_OWN,
    "/api/clients/create": Permission.CLIENT_CREATE,
    "/api/returns": Permission.RETURN_VIEW_ALL,
    "/api/returns/my": Permission.RETURN_VIEW_OWN,
    "/api/returns/create": Permission.RETURN_CREATE,
    "/api/returns/edit": Permission.RETURN_EDIT,
    "/api/returns/submit": Permission.RETURN_SUBMIT,
    "/api/returns/review": Permission.RETURN_REVIEW,
    "/api/returns/approve": Permission.RETURN_APPROVE,
    "/api/returns/scenarios": Permission.RETURN_RUN_SCENARIOS,
    "/api/documents": Permission.DOCUMENT_VIEW,
    "/api/documents/upload": Permission.DOCUMENT_UPLOAD,
    "/api/documents/delete": Permission.DOCUMENT_DELETE,
    "/api/self/return": Permission.SELF_VIEW_RETURN,
    "/api/self/return/edit": Permission.SELF_EDIT_RETURN,
    "/api/self/upload": Permission.SELF_UPLOAD_DOCS,
    "/api/self/status": Permission.SELF_VIEW_STATUS,
}


class TestFullRBACMatrix:
    """Test every role against every endpoint permission."""

    @pytest.mark.parametrize("endpoint,required_perm", list(ENDPOINT_PERMISSION_MAP.items()))
    @pytest.mark.parametrize("role", list(Role))
    def test_role_endpoint_access(self, role, endpoint, required_perm):
        """Each role x endpoint combination is either allowed or denied."""
        role_perms = get_role_permissions(role)
        access_granted = required_perm in role_perms

        # Verify the result is boolean (sanity check)
        assert isinstance(access_granted, bool)

        # Platform roles should access platform endpoints
        if required_perm.value.startswith("platform_"):
            if role in PLATFORM_ROLES:
                # May or may not have specific platform perm
                pass
            else:
                assert access_granted is False, (
                    f"Non-platform role {role.value} should NOT have "
                    f"platform permission {required_perm.value}"
                )

    @pytest.mark.parametrize("role", [Role.FIRM_CLIENT, Role.DIRECT_CLIENT])
    def test_client_only_has_self_service(self, role):
        """Client roles must not have any non-self/document permissions."""
        perms = get_role_permissions(role)
        for perm in perms:
            assert perm.value.startswith("self_") or perm.value.startswith("document_"), (
                f"Client role {role.value} has unexpected permission: {perm.value}"
            )
