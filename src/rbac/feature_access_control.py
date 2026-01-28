"""
Feature Access Control System

Comprehensive system for controlling feature access based on:
- User roles (RBAC)
- Tenant subscription tiers
- Feature flags
- Permission grants/denials

Provides decorators, middleware, and utilities for feature gating.
"""

from typing import Optional, Dict, Any, Set, List
from enum import Enum
from dataclasses import dataclass
from fastapi import HTTPException, Request
from functools import wraps
import inspect

from .enhanced_permissions import Permission, Permissions, get_permissions_for_role
from .dependencies import AuthContext
from ..database.tenant_persistence import get_tenant_persistence
from ..database.tenant_models import SubscriptionTier


# =============================================================================
# FEATURE DEFINITIONS
# =============================================================================

class FeatureCategory(Enum):
    """Feature categories for organization"""
    CORE = "core"  # Basic features available to all
    FILING = "filing"  # Tax filing features
    AUTOMATION = "automation"  # Automated workflows
    AI = "ai"  # AI-powered features
    COLLABORATION = "collaboration"  # Team features
    INTEGRATION = "integration"  # External integrations
    REPORTING = "reporting"  # Reports and analytics
    ADMIN = "admin"  # Administrative features
    WHITE_LABEL = "white_label"  # White-labeling features


@dataclass(frozen=True)
class Feature:
    """
    Defines a platform feature with access control requirements.

    Features can be gated by:
    - Minimum subscription tier
    - Required permission
    - Feature flag in tenant config
    - User role requirements
    """
    code: str  # Unique identifier (e.g., "express_lane")
    name: str  # Display name
    description: str
    category: FeatureCategory

    # Access requirements
    min_tier: SubscriptionTier = SubscriptionTier.FREE
    required_permission: Optional[Permission] = None
    feature_flag_name: Optional[str] = None  # Name in TenantFeatureFlags
    allowed_roles: Optional[Set[str]] = None  # If None, all roles allowed

    # UI/UX
    ui_icon: str = "✨"
    ui_color: str = "#667eea"
    upgrade_message: str = ""  # Message shown when feature is locked


class Features:
    """
    Registry of all platform features.

    Each feature defines its access requirements and presentation.
    """

    # =============================================================================
    # CORE FEATURES (Available to all tiers)
    # =============================================================================

    DASHBOARD = Feature(
        code="dashboard",
        name="Dashboard",
        description="Overview dashboard with key metrics",
        category=FeatureCategory.CORE,
        min_tier=SubscriptionTier.FREE,
        ui_icon="📊"
    )

    DOCUMENT_UPLOAD = Feature(
        code="document_upload",
        name="Document Upload",
        description="Upload tax documents for processing",
        category=FeatureCategory.CORE,
        min_tier=SubscriptionTier.FREE,
        ui_icon="📤"
    )

    BASIC_CALCULATIONS = Feature(
        code="basic_calculations",
        name="Tax Calculations",
        description="Basic tax calculation engine",
        category=FeatureCategory.CORE,
        min_tier=SubscriptionTier.FREE,
        ui_icon="🔢"
    )

    # =============================================================================
    # FILING FEATURES
    # =============================================================================

    EXPRESS_LANE = Feature(
        code="express_lane",
        name="Express Lane Filing",
        description="3-minute document-first tax filing",
        category=FeatureCategory.FILING,
        min_tier=SubscriptionTier.FREE,
        required_permission=Permissions.FEATURE_EXPRESS_LANE_USE,
        feature_flag_name="express_lane_enabled",
        ui_icon="⚡",
        ui_color="#48bb78"
    )

    SMART_TAX = Feature(
        code="smart_tax",
        name="Smart Tax Assistant",
        description="Adaptive question-based filing with OCR",
        category=FeatureCategory.FILING,
        min_tier=SubscriptionTier.STARTER,
        required_permission=Permissions.FEATURE_SMART_TAX_USE,
        feature_flag_name="smart_tax_enabled",
        ui_icon="🧠",
        ui_color="#667eea",
        upgrade_message="Upgrade to Starter to access Smart Tax Assistant"
    )

    GUIDED_FILING = Feature(
        code="guided_filing",
        name="Guided Tax Filing",
        description="Step-by-step guided tax preparation",
        category=FeatureCategory.FILING,
        min_tier=SubscriptionTier.FREE,
        ui_icon="🎯"
    )

    FILING_PACKAGE = Feature(
        code="filing_package",
        name="Filing Package Export",
        description="Generate comprehensive filing packages to support external e-filing (platform does NOT e-file directly with IRS)",
        category=FeatureCategory.FILING,
        min_tier=SubscriptionTier.STARTER,
        allowed_roles={"PARTNER", "STAFF"},
        ui_icon="📦",
        upgrade_message="Upgrade to Starter to generate filing packages"
    )

    # =============================================================================
    # AI FEATURES
    # =============================================================================

    AI_CHAT = Feature(
        code="ai_chat",
        name="AI Tax Chat",
        description="Chat with AI tax assistant",
        category=FeatureCategory.AI,
        min_tier=SubscriptionTier.PROFESSIONAL,
        required_permission=Permissions.FEATURE_AI_CHAT_USE,
        feature_flag_name="ai_chat_enabled",
        ui_icon="💬",
        ui_color="#805ad5",
        upgrade_message="Upgrade to Professional to access AI Chat"
    )

    INTELLIGENT_SUGGESTIONS = Feature(
        code="intelligent_suggestions",
        name="AI Suggestions",
        description="AI-powered tax optimization suggestions",
        category=FeatureCategory.AI,
        min_tier=SubscriptionTier.PROFESSIONAL,
        ui_icon="💡",
        upgrade_message="Upgrade to Professional for AI suggestions"
    )

    DOCUMENT_AI = Feature(
        code="document_ai",
        name="Advanced Document AI",
        description="AI-powered document classification and extraction",
        category=FeatureCategory.AI,
        min_tier=SubscriptionTier.PROFESSIONAL,
        ui_icon="🔍"
    )

    # =============================================================================
    # SCENARIO & PROJECTION FEATURES
    # =============================================================================

    SCENARIO_EXPLORER = Feature(
        code="scenario_explorer",
        name="Scenario Explorer",
        description="What-if tax scenario analysis",
        category=FeatureCategory.REPORTING,
        min_tier=SubscriptionTier.STARTER,
        required_permission=Permissions.FEATURE_SCENARIOS_USE,
        feature_flag_name="scenario_explorer_enabled",
        ui_icon="🔮",
        upgrade_message="Upgrade to Starter for scenario analysis"
    )

    TAX_PROJECTIONS = Feature(
        code="tax_projections",
        name="Tax Projections",
        description="5-year tax projections and planning",
        category=FeatureCategory.REPORTING,
        min_tier=SubscriptionTier.STARTER,
        required_permission=Permissions.FEATURE_PROJECTIONS_USE,
        feature_flag_name="tax_projections_enabled",
        ui_icon="📈",
        upgrade_message="Upgrade to Starter for tax projections"
    )

    # =============================================================================
    # INTEGRATION FEATURES
    # =============================================================================

    QUICKBOOKS_INTEGRATION = Feature(
        code="quickbooks",
        name="QuickBooks Integration",
        description="Sync with QuickBooks Online",
        category=FeatureCategory.INTEGRATION,
        min_tier=SubscriptionTier.PROFESSIONAL,
        required_permission=Permissions.FEATURE_INTEGRATIONS_CONFIGURE,
        feature_flag_name="quickbooks_integration",
        ui_icon="📚",
        upgrade_message="Upgrade to Professional for QuickBooks integration"
    )

    API_ACCESS = Feature(
        code="api_access",
        name="API Access",
        description="REST API for integrations",
        category=FeatureCategory.INTEGRATION,
        min_tier=SubscriptionTier.ENTERPRISE,
        required_permission=Permissions.FEATURE_API_USE,
        feature_flag_name="api_access_enabled",
        ui_icon="🔌",
        upgrade_message="Upgrade to Enterprise for API access"
    )

    WEBHOOKS = Feature(
        code="webhooks",
        name="Webhooks",
        description="Real-time event notifications",
        category=FeatureCategory.INTEGRATION,
        min_tier=SubscriptionTier.ENTERPRISE,
        ui_icon="⚡",
        upgrade_message="Upgrade to Enterprise for webhooks"
    )

    # =============================================================================
    # COLLABORATION FEATURES
    # =============================================================================

    CLIENT_PORTAL = Feature(
        code="client_portal",
        name="Client Portal",
        description="Self-service client portal",
        category=FeatureCategory.COLLABORATION,
        min_tier=SubscriptionTier.STARTER,
        ui_icon="👥"
    )

    TEAM_COLLABORATION = Feature(
        code="team_collaboration",
        name="Team Collaboration",
        description="Internal notes and task assignment",
        category=FeatureCategory.COLLABORATION,
        min_tier=SubscriptionTier.PROFESSIONAL,
        allowed_roles={"PARTNER", "STAFF"},
        ui_icon="🤝",
        upgrade_message="Upgrade to Professional for team features"
    )

    CLIENT_MESSAGING = Feature(
        code="client_messaging",
        name="Client Messaging",
        description="Secure messaging with clients",
        category=FeatureCategory.COLLABORATION,
        min_tier=SubscriptionTier.PROFESSIONAL,
        ui_icon="💌",
        upgrade_message="Upgrade to Professional for client messaging"
    )

    # =============================================================================
    # REPORTING FEATURES
    # =============================================================================

    BASIC_REPORTS = Feature(
        code="basic_reports",
        name="Basic Reports",
        description="Standard tax reports",
        category=FeatureCategory.REPORTING,
        min_tier=SubscriptionTier.FREE,
        ui_icon="📄"
    )

    ADVANCED_ANALYTICS = Feature(
        code="advanced_analytics",
        name="Advanced Analytics",
        description="Detailed analytics and insights",
        category=FeatureCategory.REPORTING,
        min_tier=SubscriptionTier.PROFESSIONAL,
        ui_icon="📊",
        upgrade_message="Upgrade to Professional for advanced analytics"
    )

    CUSTOM_REPORTS = Feature(
        code="custom_reports",
        name="Custom Reports",
        description="Build custom reports and dashboards",
        category=FeatureCategory.REPORTING,
        min_tier=SubscriptionTier.ENTERPRISE,
        ui_icon="📝",
        upgrade_message="Upgrade to Enterprise for custom reports"
    )

    # =============================================================================
    # WHITE-LABELING FEATURES
    # =============================================================================

    CUSTOM_BRANDING = Feature(
        code="custom_branding",
        name="Custom Branding",
        description="Customize colors, logo, and messaging",
        category=FeatureCategory.WHITE_LABEL,
        min_tier=SubscriptionTier.PROFESSIONAL,
        required_permission=Permissions.TENANT_BRANDING_EDIT,
        ui_icon="🎨",
        upgrade_message="Upgrade to Professional for custom branding"
    )

    CUSTOM_DOMAIN = Feature(
        code="custom_domain",
        name="Custom Domain",
        description="Use your own domain (e.g., taxes.yourfirm.com)",
        category=FeatureCategory.WHITE_LABEL,
        min_tier=SubscriptionTier.ENTERPRISE,
        feature_flag_name="custom_domain_enabled",
        ui_icon="🌐",
        upgrade_message="Upgrade to Enterprise for custom domain"
    )

    REMOVE_BRANDING = Feature(
        code="remove_branding",
        name="Remove Platform Branding",
        description="Completely white-label the platform",
        category=FeatureCategory.WHITE_LABEL,
        min_tier=SubscriptionTier.WHITE_LABEL,
        feature_flag_name="remove_branding",
        ui_icon="🏷️",
        upgrade_message="Upgrade to White Label tier to remove our branding"
    )

    # =============================================================================
    # ADMIN FEATURES
    # =============================================================================

    USER_MANAGEMENT = Feature(
        code="user_management",
        name="User Management",
        description="Manage users and permissions",
        category=FeatureCategory.ADMIN,
        min_tier=SubscriptionTier.STARTER,
        required_permission=Permissions.TENANT_USERS_EDIT,
        allowed_roles={"PLATFORM_ADMIN", "PARTNER"},
        ui_icon="👤"
    )

    AUDIT_LOGS = Feature(
        code="audit_logs",
        name="Audit Logs",
        description="View security and compliance audit logs",
        category=FeatureCategory.ADMIN,
        min_tier=SubscriptionTier.PROFESSIONAL,
        allowed_roles={"PLATFORM_ADMIN", "PARTNER"},
        ui_icon="📋",
        upgrade_message="Upgrade to Professional for audit logs"
    )

    ADVANCED_SECURITY = Feature(
        code="advanced_security",
        name="Advanced Security",
        description="2FA, IP whitelisting, SSO",
        category=FeatureCategory.ADMIN,
        min_tier=SubscriptionTier.ENTERPRISE,
        ui_icon="🔒",
        upgrade_message="Upgrade to Enterprise for advanced security"
    )


# =============================================================================
# FEATURE ACCESS CHECKING
# =============================================================================

class FeatureAccessDenied(HTTPException):
    """Exception raised when feature access is denied"""

    def __init__(
        self,
        feature: Feature,
        reason: str,
        upgrade_tier: Optional[str] = None,
        missing_permission: Optional[str] = None
    ):
        detail = {
            "error": "Feature Not Available",
            "feature_code": feature.code,
            "feature_name": feature.name,
            "reason": reason,
            "upgrade_message": feature.upgrade_message
        }

        if upgrade_tier:
            detail["required_tier"] = upgrade_tier
            detail["upgrade_url"] = f"/billing/upgrade?tier={upgrade_tier}"

        if missing_permission:
            detail["missing_permission"] = missing_permission

        super().__init__(status_code=403, detail=detail)


def check_feature_access(
    feature: Feature,
    ctx: AuthContext,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check if user has access to a feature.

    Returns dict with:
        - allowed: bool
        - reason: str (if not allowed)
        - upgrade_tier: str (if tier upgrade needed)
        - missing_permission: str (if permission missing)
    """
    result = {
        "allowed": False,
        "reason": "",
        "feature": feature.code
    }

    # Check role restrictions
    if feature.allowed_roles and ctx.role.name not in feature.allowed_roles:
        result["reason"] = f"This feature requires one of these roles: {', '.join(feature.allowed_roles)}"
        return result

    # Check permission if required
    if feature.required_permission:
        user_permissions = get_permissions_for_role(ctx.role.name)
        if feature.required_permission not in user_permissions:
            result["reason"] = f"Missing permission: {feature.required_permission.name}"
            result["missing_permission"] = feature.required_permission.code
            return result

    # Check tenant subscription tier (AuthContext uses firm_id for tenant)
    tenant_id = tenant_id or (str(ctx.firm_id) if ctx.firm_id else None)
    if tenant_id:
        persistence = get_tenant_persistence()
        tenant = persistence.get_tenant(tenant_id)

        if not tenant:
            result["reason"] = "Tenant not found"
            return result

        # Check tier
        tier_levels = {
            SubscriptionTier.FREE: 0,
            SubscriptionTier.STARTER: 1,
            SubscriptionTier.PROFESSIONAL: 2,
            SubscriptionTier.ENTERPRISE: 3,
            SubscriptionTier.WHITE_LABEL: 4
        }

        current_tier_level = tier_levels.get(tenant.subscription_tier, 0)
        required_tier_level = tier_levels.get(feature.min_tier, 0)

        if current_tier_level < required_tier_level:
            result["reason"] = f"Feature requires {feature.min_tier.value} tier or higher"
            result["upgrade_tier"] = feature.min_tier.value
            result["current_tier"] = tenant.subscription_tier.value
            return result

        # Check feature flag if specified
        if feature.feature_flag_name:
            flag_value = getattr(tenant.features, feature.feature_flag_name, False)
            if not flag_value:
                result["reason"] = f"Feature disabled for this tenant"
                result["upgrade_tier"] = feature.min_tier.value
                return result

    # All checks passed
    result["allowed"] = True
    result["reason"] = ""
    return result


def require_feature(feature: Feature):
    """
    Decorator to require feature access for an endpoint.

    Usage:
        @require_feature(Features.AI_CHAT)
        async def ai_chat_endpoint(ctx: AuthContext = Depends(require_auth)):
            ...

    Raises FeatureAccessDenied if user doesn't have access.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get auth context from kwargs
            ctx: Optional[AuthContext] = kwargs.get('ctx')

            if not ctx:
                # Try to get from args
                for arg in args:
                    if isinstance(arg, AuthContext):
                        ctx = arg
                        break

            if not ctx:
                raise HTTPException(401, "Authentication required")

            # Check feature access
            access = check_feature_access(feature, ctx)

            if not access["allowed"]:
                raise FeatureAccessDenied(
                    feature,
                    reason=access["reason"],
                    upgrade_tier=access.get("upgrade_tier"),
                    missing_permission=access.get("missing_permission")
                )

            # Call original function
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper
    return decorator


def get_user_features(ctx: AuthContext) -> Dict[str, Any]:
    """
    Get all features and their availability for a user.

    Returns dict mapping feature codes to access info.
    """
    all_features = [
        getattr(Features, attr) for attr in dir(Features)
        if isinstance(getattr(Features, attr), Feature)
    ]

    features_dict = {}

    for feature in all_features:
        access = check_feature_access(feature, ctx)
        features_dict[feature.code] = {
            "name": feature.name,
            "description": feature.description,
            "category": feature.category.value,
            "icon": feature.ui_icon,
            "color": feature.ui_color,
            "allowed": access["allowed"],
            "reason": access.get("reason", ""),
            "upgrade_tier": access.get("upgrade_tier"),
            "upgrade_message": feature.upgrade_message if not access["allowed"] else ""
        }

    return features_dict


def get_features_by_category(ctx: AuthContext, category: FeatureCategory) -> List[Dict[str, Any]]:
    """Get all features in a category with access status"""
    all_features = get_user_features(ctx)

    return [
        {**info, "code": code}
        for code, info in all_features.items()
        if info["category"] == category.value
    ]


# =============================================================================
# REQUEST HELPERS
# =============================================================================

def inject_feature_flags(request: Request, ctx: AuthContext) -> None:
    """
    Inject feature availability into request for template rendering.

    Call this in route handlers to make features available in templates.
    """
    request.state.features = get_user_features(ctx)
    request.state.feature_categories = {
        cat.value: get_features_by_category(ctx, cat)
        for cat in FeatureCategory
    }


# =============================================================================
# ADMIN FEATURE MANAGEMENT
# =============================================================================

def enable_feature_for_tenant(
    tenant_id: str,
    feature: Feature,
    admin_user_id: str
) -> bool:
    """
    Enable a feature for a specific tenant.

    Updates the tenant's feature flags.
    Logs the change to audit log.
    """
    if not feature.feature_flag_name:
        raise ValueError(f"Feature {feature.code} has no feature flag")

    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")

    # Update feature flag
    setattr(tenant.features, feature.feature_flag_name, True)

    # Save
    success = persistence.update_tenant_features(tenant_id, tenant.features)

    if success:
        # Audit log
        from ..audit.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
        logger = get_audit_logger()
        logger.log(
            event_type=AuditEventType.TENANT_FEATURES_UPDATE,
            action="enable_feature",
            resource_type="tenant_features",
            resource_id=tenant_id,
            user_id=admin_user_id,
            details={
                "feature_code": feature.code,
                "feature_name": feature.name,
                "feature_flag": feature.feature_flag_name
            },
            severity=AuditSeverity.INFO
        )

    return success


def disable_feature_for_tenant(
    tenant_id: str,
    feature: Feature,
    admin_user_id: str
) -> bool:
    """Disable a feature for a specific tenant"""
    if not feature.feature_flag_name:
        raise ValueError(f"Feature {feature.code} has no feature flag")

    persistence = get_tenant_persistence()
    tenant = persistence.get_tenant(tenant_id)

    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")

    # Update feature flag
    setattr(tenant.features, feature.feature_flag_name, False)

    # Save
    success = persistence.update_tenant_features(tenant_id, tenant.features)

    if success:
        # Audit log
        from ..audit.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
        logger = get_audit_logger()
        logger.log(
            event_type=AuditEventType.TENANT_FEATURES_UPDATE,
            action="disable_feature",
            resource_type="tenant_features",
            resource_id=tenant_id,
            user_id=admin_user_id,
            details={
                "feature_code": feature.code,
                "feature_name": feature.name,
                "feature_flag": feature.feature_flag_name
            },
            severity=AuditSeverity.WARNING
        )

    return success
