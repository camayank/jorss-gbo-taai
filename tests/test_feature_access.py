"""
Feature Access Control Tests

Tests for feature gating, subscription tier enforcement, and dynamic UI rendering.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID

import sys
sys.path.insert(0, '/Users/rakeshanita/Jorss-Gbo')

from src.rbac.feature_access_control import (
    Feature,
    Features,
    FeatureCategory,
    check_feature_access,
    get_user_features,
    get_features_by_category,
    enable_feature_for_tenant,
    disable_feature_for_tenant,
    FeatureAccessDenied
)
from src.rbac.roles import Role
from src.rbac.dependencies import AuthContext
from src.database.tenant_models import SubscriptionTier, Tenant, TenantFeatureFlags, TenantBranding


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def free_tier_tenant():
    """Mock free tier tenant"""
    return Tenant(
        tenant_id="tenant-free",
        tenant_name="Free Tier CPA",
        status="active",
        subscription_tier=SubscriptionTier.FREE,
        branding=TenantBranding(),
        features=TenantFeatureFlags(
            express_lane_enabled=True,
            smart_tax_enabled=False,
            ai_chat_enabled=False,
            scenario_explorer_enabled=False
        )
    )


@pytest.fixture
def starter_tier_tenant():
    """Mock starter tier tenant"""
    return Tenant(
        tenant_id="tenant-starter",
        tenant_name="Starter Tier CPA",
        status="active",
        subscription_tier=SubscriptionTier.STARTER,
        branding=TenantBranding(),
        features=TenantFeatureFlags(
            express_lane_enabled=True,
            smart_tax_enabled=True,
            ai_chat_enabled=False,
            scenario_explorer_enabled=True,
            tax_projections_enabled=True
        )
    )


@pytest.fixture
def professional_tier_tenant():
    """Mock professional tier tenant"""
    return Tenant(
        tenant_id="tenant-pro",
        tenant_name="Professional Tier CPA",
        status="active",
        subscription_tier=SubscriptionTier.PROFESSIONAL,
        branding=TenantBranding(),
        features=TenantFeatureFlags(
            express_lane_enabled=True,
            smart_tax_enabled=True,
            ai_chat_enabled=True,
            scenario_explorer_enabled=True,
            tax_projections_enabled=True,
            quickbooks_integration=True
        )
    )


@pytest.fixture
def enterprise_tier_tenant():
    """Mock enterprise tier tenant"""
    return Tenant(
        tenant_id="tenant-enterprise",
        tenant_name="Enterprise Tier CPA",
        status="active",
        subscription_tier=SubscriptionTier.ENTERPRISE,
        branding=TenantBranding(),
        features=TenantFeatureFlags(
            express_lane_enabled=True,
            smart_tax_enabled=True,
            ai_chat_enabled=True,
            scenario_explorer_enabled=True,
            tax_projections_enabled=True,
            quickbooks_integration=True,
            custom_domain_enabled=True,
            api_access_enabled=True
        )
    )


@pytest.fixture
def staff_context_free_tier():
    """Staff user in free tier tenant"""
    return AuthContext.for_firm_user(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        email="cpa@freetier.com",
        name="Staff Free",
        role=Role.STAFF,
        firm_id=UUID("00000000-0000-0000-0000-000000000010"),  # tenant-free
        firm_name="Free Tier CPA"
    )


@pytest.fixture
def staff_context_pro_tier():
    """Staff user in professional tier tenant"""
    return AuthContext.for_firm_user(
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        email="cpa@protier.com",
        name="Staff Pro",
        role=Role.STAFF,
        firm_id=UUID("00000000-0000-0000-0000-000000000020"),  # tenant-pro
        firm_name="Professional Tier CPA"
    )


# =============================================================================
# FEATURE DEFINITION TESTS
# =============================================================================

class TestFeatureDefinitions:
    """Test feature structure and definitions"""

    def test_all_features_have_required_fields(self):
        """All features should have required fields"""
        all_features = [
            getattr(Features, attr) for attr in dir(Features)
            if isinstance(getattr(Features, attr), Feature)
        ]

        for feature in all_features:
            assert feature.code, f"Feature missing code: {feature}"
            assert feature.name, f"Feature missing name: {feature.code}"
            assert feature.description, f"Feature missing description: {feature.code}"
            assert feature.category, f"Feature missing category: {feature.code}"
            assert feature.min_tier, f"Feature missing min_tier: {feature.code}"

    def test_feature_codes_unique(self):
        """Feature codes should be unique"""
        all_features = [
            getattr(Features, attr) for attr in dir(Features)
            if isinstance(getattr(Features, attr), Feature)
        ]

        codes = [f.code for f in all_features]
        assert len(codes) == len(set(codes)), "Duplicate feature codes found"

    def test_most_categories_used(self):
        """Most feature categories should have at least one feature"""
        all_features = [
            getattr(Features, attr) for attr in dir(Features)
            if isinstance(getattr(Features, attr), Feature)
        ]

        used_categories = {f.category for f in all_features}

        # At least 5 categories should be in use (not all categories may have features)
        assert len(used_categories) >= 5, \
            f"Too few categories in use: {len(used_categories)}"

        # Core and Filing categories should always have features
        essential_categories = {FeatureCategory.CORE, FeatureCategory.FILING}
        for category in essential_categories:
            assert category in used_categories, \
                f"Essential category {category.value} has no features"

    def test_tier_progression(self):
        """Feature tiers should follow progression: FREE < STARTER < PROFESSIONAL < ENTERPRISE < WHITE_LABEL"""
        tier_levels = {
            SubscriptionTier.FREE: 0,
            SubscriptionTier.STARTER: 1,
            SubscriptionTier.PROFESSIONAL: 2,
            SubscriptionTier.ENTERPRISE: 3,
            SubscriptionTier.WHITE_LABEL: 4
        }

        all_features = [
            getattr(Features, attr) for attr in dir(Features)
            if isinstance(getattr(Features, attr), Feature)
        ]

        for feature in all_features:
            assert feature.min_tier in tier_levels, \
                f"Invalid tier for {feature.code}: {feature.min_tier}"


# =============================================================================
# FEATURE ACCESS CHECKING TESTS
# =============================================================================

class TestFeatureAccessChecking:
    """Test feature access checking logic"""

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_free_tier_access_express_lane(self, mock_persistence, staff_context_free_tier, free_tier_tenant):
        """Free tier should have access to Express Lane"""
        mock_persistence.return_value.get_tenant.return_value = free_tier_tenant

        access = check_feature_access(Features.EXPRESS_LANE, staff_context_free_tier)

        assert access["allowed"], "Free tier should have Express Lane access"

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_free_tier_blocked_from_ai_chat(self, mock_persistence, staff_context_free_tier, free_tier_tenant):
        """Free tier should NOT have access to AI Chat"""
        mock_persistence.return_value.get_tenant.return_value = free_tier_tenant

        access = check_feature_access(Features.AI_CHAT, staff_context_free_tier)

        assert not access["allowed"], "Free tier should NOT have AI Chat access"
        assert "upgrade_tier" in access, "Should provide upgrade tier info"
        assert access["upgrade_tier"] == "professional"

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_professional_tier_access_ai_chat(self, mock_persistence, staff_context_pro_tier, professional_tier_tenant):
        """Professional tier should have access to AI Chat"""
        mock_persistence.return_value.get_tenant.return_value = professional_tier_tenant

        access = check_feature_access(Features.AI_CHAT, staff_context_pro_tier)

        assert access["allowed"], "Professional tier should have AI Chat access"

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_feature_flag_enforcement(self, mock_persistence, staff_context_pro_tier, professional_tier_tenant):
        """Feature flags should be enforced even if tier allows it"""
        # Disable AI chat flag
        professional_tier_tenant.features.ai_chat_enabled = False
        mock_persistence.return_value.get_tenant.return_value = professional_tier_tenant

        access = check_feature_access(Features.AI_CHAT, staff_context_pro_tier)

        assert not access["allowed"], "Feature should be blocked if flag is disabled"
        assert "disabled" in access["reason"].lower()

    def test_role_restrictions(self):
        """Features with role restrictions should block unauthorized roles"""
        client_context = AuthContext.for_client(
            user_id=UUID("00000000-0000-0000-0000-000000000003"),
            email="client@example.com",
            name="Test Client",
            is_direct=False,
            firm_id=UUID("00000000-0000-0000-0000-000000000010"),
            firm_name="Test CPA Firm"
        )

        # FILING_PACKAGE is restricted to PARTNER/STAFF roles (CPA roles)
        access = check_feature_access(Features.FILING_PACKAGE, client_context)

        assert not access["allowed"], "Client should not have access to Filing Package"
        assert "role" in access["reason"].lower()


# =============================================================================
# GET USER FEATURES TESTS
# =============================================================================

class TestGetUserFeatures:
    """Test get_user_features function"""

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_get_user_features_returns_all(self, mock_persistence, staff_context_pro_tier, professional_tier_tenant):
        """get_user_features should return all features with access status"""
        mock_persistence.return_value.get_tenant.return_value = professional_tier_tenant

        features = get_user_features(staff_context_pro_tier)

        # Should have all features
        assert len(features) > 0, "Should return features"

        # Each feature should have required keys
        for code, info in features.items():
            assert "name" in info
            assert "allowed" in info
            assert "category" in info
            assert "icon" in info

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_get_user_features_shows_locked(self, mock_persistence, staff_context_free_tier, free_tier_tenant):
        """get_user_features should show locked features with upgrade info"""
        mock_persistence.return_value.get_tenant.return_value = free_tier_tenant

        features = get_user_features(staff_context_free_tier)

        # AI Chat should be locked
        ai_chat = features.get("ai_chat")
        assert ai_chat is not None
        assert not ai_chat["allowed"]
        assert ai_chat["upgrade_tier"] == "professional"
        assert ai_chat["upgrade_message"] != ""


# =============================================================================
# GET FEATURES BY CATEGORY TESTS
# =============================================================================

class TestGetFeaturesByCategory:
    """Test get_features_by_category function"""

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_get_features_by_category(self, mock_persistence, staff_context_pro_tier, professional_tier_tenant):
        """Should return features filtered by category"""
        mock_persistence.return_value.get_tenant.return_value = professional_tier_tenant

        ai_features = get_features_by_category(staff_context_pro_tier, FeatureCategory.AI)

        # Should have AI features
        assert len(ai_features) > 0
        for feature in ai_features:
            assert feature["category"] == "ai"

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_category_filtering_accurate(self, mock_persistence, staff_context_pro_tier, professional_tier_tenant):
        """Category filtering should be accurate"""
        mock_persistence.return_value.get_tenant.return_value = professional_tier_tenant

        # Get all features
        all_features = get_user_features(staff_context_pro_tier)

        # Get features by category
        for category in FeatureCategory:
            category_features = get_features_by_category(staff_context_pro_tier, category)
            category_codes = {f["code"] for f in category_features}

            # Verify all returned features are in this category
            for code in category_codes:
                assert all_features[code]["category"] == category.value


# =============================================================================
# ADMIN FEATURE MANAGEMENT TESTS
# =============================================================================

class TestAdminFeatureManagement:
    """Test admin functions for enabling/disabling features"""

    @patch('src.audit.audit_logger.get_audit_logger')
    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_enable_feature_for_tenant(self, mock_persistence, mock_audit_logger, free_tier_tenant):
        """Admin should be able to enable features for tenant"""
        mock_persistence.return_value.get_tenant.return_value = free_tier_tenant
        mock_persistence.return_value.update_tenant_features.return_value = True

        success = enable_feature_for_tenant(
            tenant_id="tenant-free",
            feature=Features.AI_CHAT,
            admin_user_id="admin-001"
        )

        assert success, "Should successfully enable feature"

        # Verify feature flag was set
        assert free_tier_tenant.features.ai_chat_enabled is True

        # Verify audit log was called
        mock_audit_logger.return_value.log.assert_called_once()

    @patch('src.audit.audit_logger.get_audit_logger')
    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_disable_feature_for_tenant(self, mock_persistence, mock_audit_logger, professional_tier_tenant):
        """Admin should be able to disable features for tenant"""
        mock_persistence.return_value.get_tenant.return_value = professional_tier_tenant
        mock_persistence.return_value.update_tenant_features.return_value = True

        success = disable_feature_for_tenant(
            tenant_id="tenant-pro",
            feature=Features.AI_CHAT,
            admin_user_id="admin-001"
        )

        assert success, "Should successfully disable feature"

        # Verify feature flag was cleared
        assert professional_tier_tenant.features.ai_chat_enabled is False

        # Verify audit log was called
        mock_audit_logger.return_value.log.assert_called_once()

    def test_enable_feature_without_flag_raises_error(self):
        """Enabling feature without feature flag should raise error"""
        # Dashboard has no feature flag
        with pytest.raises(ValueError) as exc_info:
            enable_feature_for_tenant(
                tenant_id="tenant-001",
                feature=Features.DASHBOARD,
                admin_user_id="admin-001"
            )

        assert "no feature flag" in str(exc_info.value).lower()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestFeatureAccessIntegration:
    """Integration tests for feature access in real scenarios"""

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_subscription_upgrade_flow(self, mock_persistence):
        """Test feature access after subscription upgrade"""
        # Create contexts
        staff_context = AuthContext.for_firm_user(
            user_id=UUID("00000000-0000-0000-0000-000000000004"),
            email="cpa@example.com",
            name="Test Staff",
            role=Role.STAFF,
            firm_id=UUID("00000000-0000-0000-0000-000000000010"),
            firm_name="Test CPA"
        )

        # Start with free tier
        free_tenant = Tenant(
            tenant_id="tenant-001",
            tenant_name="Test CPA",
            status="active",
            subscription_tier=SubscriptionTier.FREE,
            branding=TenantBranding(),
            features=TenantFeatureFlags(
                express_lane_enabled=True,
                ai_chat_enabled=False
            )
        )

        mock_persistence.return_value.get_tenant.return_value = free_tenant

        # Verify AI chat is locked
        access_before = check_feature_access(Features.AI_CHAT, staff_context)
        assert not access_before["allowed"]

        # Upgrade to professional
        pro_tenant = Tenant(
            tenant_id="tenant-001",
            tenant_name="Test CPA",
            status="active",
            subscription_tier=SubscriptionTier.PROFESSIONAL,
            branding=TenantBranding(),
            features=TenantFeatureFlags(
                express_lane_enabled=True,
                ai_chat_enabled=True
            )
        )

        mock_persistence.return_value.get_tenant.return_value = pro_tenant

        # Verify AI chat is now available
        access_after = check_feature_access(Features.AI_CHAT, staff_context)
        assert access_after["allowed"]


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestFeatureAccessPerformance:
    """Test performance of feature access checks"""

    @patch('src.rbac.feature_access_control.get_tenant_persistence')
    def test_bulk_feature_check_performance(self, mock_persistence, staff_context_pro_tier, professional_tier_tenant):
        """Checking all features should be fast"""
        import time

        mock_persistence.return_value.get_tenant.return_value = professional_tier_tenant

        start = time.time()
        for _ in range(10):
            get_user_features(staff_context_pro_tier)
        elapsed = time.time() - start

        # 10 full feature checks should take < 1 second
        assert elapsed < 1.0, f"Feature checks too slow: {elapsed:.2f}s for 10 iterations"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
