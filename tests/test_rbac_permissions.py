"""
RBAC Permission System Tests

Comprehensive test suite for role-based access control system.
Tests permissions, role assignments, feature access, and enforcement.
"""

import pytest
from typing import Set, Optional
from dataclasses import dataclass

# Import RBAC system
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rbac.enhanced_permissions import (
    Permission,
    Permissions,
    PermissionScope,
    ResourceType,
    PermissionAction,
    get_permissions_for_role,
    has_permission,
)
from rbac.roles import Role
from rbac.dependencies import AuthContext
from rbac.feature_access_control import (
    Features,
    check_feature_access,
    get_user_features,
    FeatureCategory
)
from database.tenant_models import SubscriptionTier


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def platform_admin_context():
    """Platform admin auth context"""
    from uuid import UUID
    from src.rbac.context import UserType
    return AuthContext.for_platform_admin(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        email="admin@platform.com",
        name="Admin User",
        role=Role.PLATFORM_ADMIN,
    )


@pytest.fixture
def partner_context():
    """Partner (tenant admin) auth context"""
    from uuid import UUID
    return AuthContext.for_firm_user(
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        email="partner@tenant1.com",
        name="Partner User",
        role=Role.PARTNER,
        firm_id=UUID("00000000-0000-0000-0000-000000000010"),
        firm_name="Test CPA Firm"
    )


@pytest.fixture
def staff_context():
    """Staff (CPA) auth context"""
    from uuid import UUID
    return AuthContext.for_firm_user(
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        email="cpa@tenant1.com",
        name="Staff User",
        role=Role.STAFF,
        firm_id=UUID("00000000-0000-0000-0000-000000000010"),
        firm_name="Test CPA Firm"
    )


@pytest.fixture
def firm_client_context():
    """Firm client auth context"""
    from uuid import UUID
    return AuthContext.for_client(
        user_id=UUID("00000000-0000-0000-0000-000000000004"),
        email="client@example.com",
        name="Firm Client",
        is_direct=False,
        firm_id=UUID("00000000-0000-0000-0000-000000000010"),
        firm_name="Test CPA Firm"
    )


@pytest.fixture
def direct_client_context():
    """Direct client (no firm) auth context"""
    from uuid import UUID
    return AuthContext.for_client(
        user_id=UUID("00000000-0000-0000-0000-000000000005"),
        email="direct@example.com",
        name="Direct Client",
        is_direct=True,
    )


# =============================================================================
# PERMISSION DEFINITION TESTS
# =============================================================================

class TestPermissionDefinitions:
    """Test permission structure and definitions"""

    def test_permission_immutability(self):
        """Permissions should be immutable (frozen dataclass)"""
        perm = Permissions.PLATFORM_TENANT_CREATE

        with pytest.raises(AttributeError):
            perm.code = "modified"

    def test_permission_code_format(self):
        """Permission codes should follow naming convention: {scope}.{resource}.{action}"""
        test_perms = [
            Permissions.PLATFORM_TENANT_CREATE,
            Permissions.TENANT_BRANDING_EDIT,
            Permissions.CPA_PROFILE_EDIT_SELF,
            Permissions.CLIENT_RETURNS_VIEW_SELF
        ]

        for perm in test_perms:
            # Codes use dot notation: e.g., "platform.tenant.create"
            parts = perm.code.split('.')
            assert len(parts) >= 2, f"Permission code should have at least 2 parts: {perm.code}"

    def test_all_scopes_covered(self):
        """All permission scopes should be represented"""
        all_perms = [getattr(Permissions, attr) for attr in dir(Permissions)
                     if isinstance(getattr(Permissions, attr), Permission)]

        scopes = {perm.scope for perm in all_perms}

        expected_scopes = {
            PermissionScope.PLATFORM,
            PermissionScope.TENANT,
            PermissionScope.CPA,
            PermissionScope.CLIENT,
            PermissionScope.SELF
        }

        assert scopes == expected_scopes, f"Missing scopes: {expected_scopes - scopes}"

    def test_all_resources_covered(self):
        """All resource types should be represented"""
        all_perms = [getattr(Permissions, attr) for attr in dir(Permissions)
                     if isinstance(getattr(Permissions, attr), Permission)]

        resources = {perm.resource for perm in all_perms}

        # Updated to match actual ResourceType enum values in implementation
        expected_resources = {
            ResourceType.TENANT,
            ResourceType.TENANT_USERS,  # Changed from USER
            ResourceType.TAX_RETURN,
            ResourceType.DOCUMENT,
            ResourceType.CLIENT_PROFILE  # Changed from CLIENT
        }

        assert expected_resources.issubset(resources), \
            f"Missing resources: {expected_resources - resources}"


# =============================================================================
# ROLE PERMISSION TESTS
# =============================================================================

class TestRolePermissions:
    """Test permission assignments for each role"""

    def test_platform_admin_has_platform_permissions(self):
        """Platform admin should have all platform-level permissions"""
        admin_perms = get_permissions_for_role('PLATFORM_ADMIN')

        # Platform admin has a specific set of platform-level permissions
        # Not ALL permissions, but all PLATFORM_ scope permissions
        platform_perms = [
            Permissions.PLATFORM_TENANT_VIEW_ALL,
            Permissions.PLATFORM_TENANT_CREATE,
            Permissions.PLATFORM_TENANT_EDIT,
            Permissions.PLATFORM_TENANT_DELETE,
            Permissions.PLATFORM_TENANT_BRANDING_EDIT,
            Permissions.PLATFORM_TENANT_FEATURES_EDIT,
            Permissions.PLATFORM_TENANT_BILLING_MANAGE,
            Permissions.PLATFORM_SYSTEM_CONFIGURE,
            Permissions.PLATFORM_AUDIT_VIEW,
            Permissions.PLATFORM_PERMISSIONS_MANAGE,
        ]

        for perm in platform_perms:
            assert perm in admin_perms, \
                f"Platform admin should have {perm.code}"

    def test_partner_has_tenant_management_perms(self):
        """Partner should have tenant management permissions within their tenant"""
        partner_perms = get_permissions_for_role('PARTNER')

        # Partner has tenant management but not platform-wide management
        assert Permissions.TENANT_BRANDING_EDIT in partner_perms
        assert Permissions.TENANT_USERS_EDIT in partner_perms
        assert Permissions.TENANT_SETTINGS_EDIT in partner_perms

        # Partner should NOT have platform-level permissions
        assert Permissions.PLATFORM_TENANT_CREATE not in partner_perms

    def test_staff_permissions_subset_of_partner(self):
        """Staff permissions should be subset of partner"""
        partner_perms = get_permissions_for_role('PARTNER')
        staff_perms = get_permissions_for_role('STAFF')

        assert staff_perms.issubset(partner_perms), \
            "Staff should not have permissions that partner doesn't have"

    def test_firm_client_cannot_manage_tenant(self):
        """Firm client should not have tenant management permissions"""
        client_perms = get_permissions_for_role('FIRM_CLIENT')

        tenant_mgmt_perms = {
            Permissions.TENANT_BRANDING_EDIT,
            Permissions.TENANT_USERS_EDIT,
            Permissions.TENANT_SETTINGS_EDIT
        }

        assert not tenant_mgmt_perms.intersection(client_perms), \
            "Firm client should not have tenant management permissions"

    def test_firm_client_can_edit_own_returns(self):
        """CRITICAL: Firm client must be able to edit their own returns"""
        client_perms = get_permissions_for_role('FIRM_CLIENT')

        # This was the bug - ensure SELF_EDIT_RETURN is included
        assert Permissions.CLIENT_RETURNS_EDIT_SELF in client_perms, \
            "FIRM_CLIENT must have CLIENT_RETURNS_EDIT_SELF permission (bug fix verification)"

    def test_staff_can_view_client_returns(self):
        """Staff should be able to view assigned client returns"""
        staff_perms = get_permissions_for_role('STAFF')

        assert Permissions.CPA_RETURNS_VIEW in staff_perms, \
            "Staff should be able to view client returns"

    def test_partner_can_manage_users(self):
        """Partner should be able to manage users in their tenant"""
        partner_perms = get_permissions_for_role('PARTNER')

        assert Permissions.TENANT_USERS_EDIT in partner_perms, \
            "Partner should be able to manage tenant users"


# =============================================================================
# PERMISSION CHECKING TESTS
# =============================================================================

class TestPermissionChecking:
    """Test permission checking logic"""

    def test_has_permission_basic(self):
        """Basic permission check should work"""
        admin_perms = get_permissions_for_role('PLATFORM_ADMIN')

        assert has_permission(
            admin_perms,
            Permissions.PLATFORM_TENANT_CREATE
        ), "Platform admin should have tenant create permission"

    def test_has_permission_ownership_required(self):
        """Permission requiring ownership should check user_id"""
        client_perms = get_permissions_for_role('FIRM_CLIENT')

        # Same user_id - should pass
        assert has_permission(
            client_perms,
            Permissions.CLIENT_RETURNS_VIEW_SELF,
            user_id="client-001",
            resource_owner_id="client-001"
        ), "Client should be able to view own returns"

        # Different user_id - should fail
        assert not has_permission(
            client_perms,
            Permissions.CLIENT_RETURNS_VIEW_SELF,
            user_id="client-001",
            resource_owner_id="client-002"
        ), "Client should not be able to view other client's returns"

    def test_has_permission_assignment_required(self):
        """Permission requiring assignment should check assigned_cpa_id"""
        staff_perms = get_permissions_for_role('STAFF')

        # Assigned CPA - should pass
        assert has_permission(
            staff_perms,
            Permissions.CPA_RETURNS_EDIT,
            user_id="staff-001",
            assigned_cpa_id="staff-001"
        ), "Staff should be able to edit assigned returns"

        # Not assigned - should fail
        assert not has_permission(
            staff_perms,
            Permissions.CPA_RETURNS_EDIT,
            user_id="staff-001",
            assigned_cpa_id="staff-002"
        ), "Staff should not be able to edit unassigned returns"

    def test_platform_admin_has_platform_view(self):
        """Platform admin should have platform-level view permissions"""
        admin_perms = get_permissions_for_role('PLATFORM_ADMIN')

        # Platform admin has view permissions for all tenants
        assert has_permission(
            admin_perms,
            Permissions.PLATFORM_TENANT_VIEW_ALL
        ), "Platform admin should have tenant view permission"


# =============================================================================
# FEATURE ACCESS CONTROL TESTS
# =============================================================================

class TestFeatureAccessControl:
    """Test feature gating and subscription tier enforcement"""

    def test_starter_tier_features(self):
        """Starter tier should have additional features"""
        # Test that Smart Tax requires Starter
        assert Features.SMART_TAX.min_tier == SubscriptionTier.STARTER

        # Test that Scenario Explorer requires Starter
        assert Features.SCENARIO_EXPLORER.min_tier == SubscriptionTier.STARTER

    def test_professional_tier_features(self):
        """Professional tier should have AI features"""
        # Test that AI Chat requires Professional
        assert Features.AI_CHAT.min_tier == SubscriptionTier.PROFESSIONAL

        # Test that QuickBooks requires Professional
        assert Features.QUICKBOOKS_INTEGRATION.min_tier == SubscriptionTier.PROFESSIONAL

    def test_enterprise_tier_features(self):
        """Enterprise tier should have advanced features"""
        # Test that API access requires Enterprise
        assert Features.API_ACCESS.min_tier == SubscriptionTier.ENTERPRISE

        # Test that custom domain requires Enterprise
        assert Features.CUSTOM_DOMAIN.min_tier == SubscriptionTier.ENTERPRISE

    def test_white_label_tier_features(self):
        """White label tier should have branding removal"""
        assert Features.REMOVE_BRANDING.min_tier == SubscriptionTier.WHITE_LABEL

    def test_role_restricted_features(self):
        """Some features should be role-restricted"""
        # Filing Package should require PARTNER/STAFF roles
        assert Features.FILING_PACKAGE.allowed_roles == {"PARTNER", "STAFF"}

        # User management should require admin roles
        assert Features.USER_MANAGEMENT.allowed_roles == {"PLATFORM_ADMIN", "PARTNER"}


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestPermissionEnforcement:
    """Test permission enforcement decorators and middleware"""

    def test_require_permission_decorator_allows_authorized(self, platform_admin_context):
        """Decorator should allow users with required permission"""
        from src.rbac.permission_enforcement import require_permission

        @require_permission(Permissions.PLATFORM_TENANT_CREATE)
        async def create_tenant(ctx: AuthContext):
            return {"success": True}

        # Should not raise exception
        import asyncio
        result = asyncio.run(create_tenant(ctx=platform_admin_context))
        assert result["success"] is True

    def test_require_permission_decorator_blocks_unauthorized(self, firm_client_context):
        """Decorator should block users without required permission"""
        from src.rbac.permission_enforcement import require_permission
        from fastapi import HTTPException

        @require_permission(Permissions.PLATFORM_TENANT_CREATE)
        async def create_tenant(ctx: AuthContext):
            return {"success": True}

        # Should raise HTTPException
        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(create_tenant(ctx=firm_client_context))

        assert exc_info.value.status_code == 403


# =============================================================================
# SECURITY TESTS
# =============================================================================

class TestSecurityBoundaries:
    """Test security boundaries and access control"""

    def test_client_cannot_view_other_client_data(self):
        """Clients should not be able to view other clients' data"""
        client_perms = get_permissions_for_role('FIRM_CLIENT')

        # Client can view own data
        assert has_permission(
            client_perms,
            Permissions.CLIENT_RETURNS_VIEW_SELF,
            user_id="client-001",
            resource_owner_id="client-001"
        )

        # Client cannot view other's data
        assert not has_permission(
            client_perms,
            Permissions.CLIENT_RETURNS_VIEW_SELF,
            user_id="client-001",
            resource_owner_id="client-002"
        )

    def test_staff_cannot_edit_unassigned_returns(self):
        """Staff should only edit returns assigned to them"""
        staff_perms = get_permissions_for_role('STAFF')

        # Can edit assigned return
        assert has_permission(
            staff_perms,
            Permissions.CPA_RETURNS_EDIT,
            user_id="staff-001",
            assigned_cpa_id="staff-001"
        )

        # Cannot edit unassigned return
        assert not has_permission(
            staff_perms,
            Permissions.CPA_RETURNS_EDIT,
            user_id="staff-001",
            assigned_cpa_id="staff-002"
        )

    def test_partner_limited_to_own_tenant(self):
        """Partner should only have access within their tenant"""
        partner_perms = get_permissions_for_role('PARTNER')

        # Partner can manage users in their tenant
        assert Permissions.TENANT_USERS_EDIT in partner_perms

        # But should not have platform-level view permissions
        assert Permissions.PLATFORM_TENANT_VIEW_ALL not in partner_perms


# =============================================================================
# REGRESSION TESTS (For Known Bugs)
# =============================================================================

class TestRegressions:
    """Tests for previously identified bugs"""

    def test_firm_client_edit_return_bug_fix(self):
        """
        REGRESSION TEST: Ensure FIRM_CLIENT can edit own returns.

        Bug: FIRM_CLIENT was missing SELF_EDIT_RETURN permission.
        This caused clients to be unable to edit their draft returns.
        """
        client_perms = get_permissions_for_role('FIRM_CLIENT')

        # Verify the bug fix
        edit_perm = Permissions.CLIENT_RETURNS_EDIT_SELF

        assert edit_perm in client_perms, \
            "FIRM_CLIENT must have CLIENT_RETURNS_EDIT_SELF permission"

        # Verify they can edit own returns
        assert has_permission(
            client_perms,
            edit_perm,
            user_id="client-001",
            resource_owner_id="client-001"
        ), "Firm client should be able to edit their own returns"


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Test performance of permission checks"""

    def test_permission_check_performance(self):
        """Permission checks should be fast (< 1ms)"""
        import time

        admin_perms = get_permissions_for_role('PLATFORM_ADMIN')

        start = time.time()
        for _ in range(1000):
            has_permission(admin_perms, Permissions.PLATFORM_TENANT_CREATE)
        elapsed = time.time() - start

        # 1000 checks should take < 100ms (< 0.1ms per check)
        assert elapsed < 0.1, f"Permission checks too slow: {elapsed*1000:.2f}ms for 1000 checks"

    def test_role_permission_loading_cached(self):
        """Role permissions should be cached, not recomputed"""
        import time

        start = time.time()
        for _ in range(100):
            get_permissions_for_role('PLATFORM_ADMIN')
        elapsed = time.time() - start

        # Should be nearly instant if cached
        assert elapsed < 0.01, f"Role permission loading not cached: {elapsed*1000:.2f}ms for 100 calls"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
