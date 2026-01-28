"""
Enhanced RBAC Permission System

Crystal-clear permission definitions for white-labeling platform.
Every permission is explicitly defined with clear scope and ownership rules.

Permission Naming Convention:
    {SCOPE}_{RESOURCE}_{ACTION}

    Example: TENANT_BRANDING_EDIT
    - SCOPE: TENANT (who it applies to)
    - RESOURCE: BRANDING (what it applies to)
    - ACTION: EDIT (what can be done)
"""

from enum import Enum
from dataclasses import dataclass
from typing import Set, Dict, List, Optional
from datetime import datetime


class PermissionScope(Enum):
    """Permission scope - defines WHO the permission applies to"""
    PLATFORM = "platform"      # Platform-wide (all tenants)
    TENANT = "tenant"          # Tenant-specific (single CPA firm)
    CPA = "cpa"               # CPA-specific (individual CPA)
    CLIENT = "client"          # Client-specific (individual client)
    SELF = "self"             # User's own data only


class ResourceType(Enum):
    """Resource types that can be accessed"""
    # Tenant Management
    TENANT = "tenant"
    TENANT_BRANDING = "tenant_branding"
    TENANT_FEATURES = "tenant_features"
    TENANT_USERS = "tenant_users"
    TENANT_SETTINGS = "tenant_settings"
    TENANT_STATS = "tenant_stats"
    TENANT_BILLING = "tenant_billing"

    # CPA Management
    CPA_PROFILE = "cpa_profile"
    CPA_BRANDING = "cpa_branding"
    CPA_CLIENTS = "cpa_clients"
    CPA_RETURNS = "cpa_returns"
    CPA_SCHEDULE = "cpa_schedule"

    # Tax Returns
    TAX_RETURN = "tax_return"
    TAX_RETURN_REVIEW = "tax_return_review"
    TAX_RETURN_APPROVAL = "tax_return_approval"
    TAX_RETURN_EFILE = "tax_return_efile"  # NOTE: Actually "filing_package" - platform does NOT e-file with IRS
    FILING_PACKAGE = "tax_return_efile"  # Alias - same as TAX_RETURN_EFILE

    # Documents
    DOCUMENT = "document"
    DOCUMENT_VAULT = "document_vault"

    # Client Management
    CLIENT_PROFILE = "client_profile"
    CLIENT_PORTAL = "client_portal"
    CLIENT_COMMUNICATION = "client_communication"

    # Workflows
    EXPRESS_LANE = "express_lane"
    SMART_TAX = "smart_tax"
    AI_CHAT = "ai_chat"
    SCENARIOS = "scenarios"
    PROJECTIONS = "projections"

    # Features
    INTEGRATIONS = "integrations"
    REPORTS = "reports"
    ANALYTICS = "analytics"
    API_ACCESS = "api_access"

    # System
    AUDIT_LOG = "audit_log"
    SYSTEM_SETTINGS = "system_settings"
    PERMISSIONS = "permissions"


class PermissionAction(Enum):
    """Actions that can be performed on resources"""
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    ASSIGN = "assign"
    UNASSIGN = "unassign"
    EXPORT = "export"
    IMPORT = "import"
    CONFIGURE = "configure"
    EXECUTE = "execute"


@dataclass(frozen=True)
class Permission:
    """
    Granular permission definition.

    Attributes:
        code: Unique permission code (e.g., "tenant.branding.edit")
        name: Human-readable name
        description: What this permission allows
        scope: Who this permission applies to
        resource: What resource it applies to
        action: What action can be performed
        requires_ownership: Whether user must own the resource
        requires_assignment: Whether user must be assigned to the resource
    """
    code: str
    name: str
    description: str
    scope: PermissionScope
    resource: ResourceType
    action: PermissionAction
    requires_ownership: bool = False
    requires_assignment: bool = False

    def __hash__(self):
        return hash(self.code)


# =============================================================================
# PERMISSION DEFINITIONS
# =============================================================================

class Permissions:
    """
    All platform permissions explicitly defined.

    Organized by scope and resource for clarity.
    """

    # =========================================================================
    # PLATFORM-LEVEL PERMISSIONS (Platform Admin only)
    # =========================================================================

    # Tenant Management
    PLATFORM_TENANT_VIEW_ALL = Permission(
        code="platform.tenant.view_all",
        name="View All Tenants",
        description="View all tenants and their details",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.TENANT,
        action=PermissionAction.VIEW
    )

    PLATFORM_TENANT_CREATE = Permission(
        code="platform.tenant.create",
        name="Create Tenant",
        description="Create new tenants (CPA firms)",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.TENANT,
        action=PermissionAction.CREATE
    )

    PLATFORM_TENANT_EDIT = Permission(
        code="platform.tenant.edit",
        name="Edit Tenant",
        description="Edit any tenant's basic information",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.TENANT,
        action=PermissionAction.EDIT
    )

    PLATFORM_TENANT_DELETE = Permission(
        code="platform.tenant.delete",
        name="Delete Tenant",
        description="Delete tenants (WARNING: Destructive)",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.TENANT,
        action=PermissionAction.DELETE
    )

    PLATFORM_TENANT_BRANDING_EDIT = Permission(
        code="platform.tenant.branding_edit",
        name="Edit Tenant Branding",
        description="Modify any tenant's branding and theme",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.TENANT_BRANDING,
        action=PermissionAction.EDIT
    )

    PLATFORM_TENANT_FEATURES_EDIT = Permission(
        code="platform.tenant.features_edit",
        name="Edit Tenant Features",
        description="Enable/disable features and set limits for tenants",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.TENANT_FEATURES,
        action=PermissionAction.EDIT
    )

    PLATFORM_TENANT_BILLING_MANAGE = Permission(
        code="platform.tenant.billing_manage",
        name="Manage Tenant Billing",
        description="Manage subscription tiers and billing for tenants",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.TENANT_BILLING,
        action=PermissionAction.CONFIGURE
    )

    # System Management
    PLATFORM_SYSTEM_CONFIGURE = Permission(
        code="platform.system.configure",
        name="Configure System",
        description="Modify platform-wide system settings",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.SYSTEM_SETTINGS,
        action=PermissionAction.CONFIGURE
    )

    PLATFORM_AUDIT_VIEW = Permission(
        code="platform.audit.view",
        name="View Audit Logs",
        description="View all platform audit logs",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.AUDIT_LOG,
        action=PermissionAction.VIEW
    )

    PLATFORM_PERMISSIONS_MANAGE = Permission(
        code="platform.permissions.manage",
        name="Manage Permissions",
        description="Assign/revoke permissions and roles",
        scope=PermissionScope.PLATFORM,
        resource=ResourceType.PERMISSIONS,
        action=PermissionAction.CONFIGURE
    )

    # =========================================================================
    # TENANT-LEVEL PERMISSIONS (Partner, Staff within tenant)
    # =========================================================================

    # Tenant Settings (within own tenant)
    TENANT_BRANDING_VIEW = Permission(
        code="tenant.branding.view",
        name="View Tenant Branding",
        description="View own tenant's branding settings",
        scope=PermissionScope.TENANT,
        resource=ResourceType.TENANT_BRANDING,
        action=PermissionAction.VIEW
    )

    TENANT_BRANDING_EDIT = Permission(
        code="tenant.branding.edit",
        name="Edit Tenant Branding",
        description="Edit own tenant's branding (Partner only)",
        scope=PermissionScope.TENANT,
        resource=ResourceType.TENANT_BRANDING,
        action=PermissionAction.EDIT,
        requires_ownership=True
    )

    TENANT_SETTINGS_VIEW = Permission(
        code="tenant.settings.view",
        name="View Tenant Settings",
        description="View own tenant's settings",
        scope=PermissionScope.TENANT,
        resource=ResourceType.TENANT_SETTINGS,
        action=PermissionAction.VIEW
    )

    TENANT_SETTINGS_EDIT = Permission(
        code="tenant.settings.edit",
        name="Edit Tenant Settings",
        description="Edit own tenant's settings (Partner only)",
        scope=PermissionScope.TENANT,
        resource=ResourceType.TENANT_SETTINGS,
        action=PermissionAction.EDIT,
        requires_ownership=True
    )

    # User Management (within tenant)
    TENANT_USERS_VIEW = Permission(
        code="tenant.users.view",
        name="View Tenant Users",
        description="View all users in own tenant",
        scope=PermissionScope.TENANT,
        resource=ResourceType.TENANT_USERS,
        action=PermissionAction.VIEW
    )

    TENANT_USERS_CREATE = Permission(
        code="tenant.users.create",
        name="Create Tenant Users",
        description="Add new CPAs/staff to tenant",
        scope=PermissionScope.TENANT,
        resource=ResourceType.TENANT_USERS,
        action=PermissionAction.CREATE
    )

    TENANT_USERS_EDIT = Permission(
        code="tenant.users.edit",
        name="Edit Tenant Users",
        description="Edit user roles and permissions within tenant",
        scope=PermissionScope.TENANT,
        resource=ResourceType.TENANT_USERS,
        action=PermissionAction.EDIT
    )

    TENANT_USERS_DELETE = Permission(
        code="tenant.users.delete",
        name="Delete Tenant Users",
        description="Remove users from tenant",
        scope=PermissionScope.TENANT,
        resource=ResourceType.TENANT_USERS,
        action=PermissionAction.DELETE
    )

    # Analytics & Reports
    TENANT_ANALYTICS_VIEW = Permission(
        code="tenant.analytics.view",
        name="View Tenant Analytics",
        description="View analytics and reports for tenant",
        scope=PermissionScope.TENANT,
        resource=ResourceType.ANALYTICS,
        action=PermissionAction.VIEW
    )

    TENANT_STATS_VIEW = Permission(
        code="tenant.stats.view",
        name="View Tenant Statistics",
        description="View usage statistics for tenant",
        scope=PermissionScope.TENANT,
        resource=ResourceType.TENANT_STATS,
        action=PermissionAction.VIEW
    )

    # =========================================================================
    # CPA-LEVEL PERMISSIONS (Staff, Partner)
    # =========================================================================

    # CPA Profile & Branding
    CPA_PROFILE_VIEW_SELF = Permission(
        code="cpa.profile.view_self",
        name="View Own CPA Profile",
        description="View own CPA profile",
        scope=PermissionScope.SELF,
        resource=ResourceType.CPA_PROFILE,
        action=PermissionAction.VIEW,
        requires_ownership=True
    )

    CPA_PROFILE_EDIT_SELF = Permission(
        code="cpa.profile.edit_self",
        name="Edit Own CPA Profile",
        description="Edit own CPA profile information",
        scope=PermissionScope.SELF,
        resource=ResourceType.CPA_PROFILE,
        action=PermissionAction.EDIT,
        requires_ownership=True
    )

    CPA_BRANDING_VIEW_SELF = Permission(
        code="cpa.branding.view_self",
        name="View Own CPA Branding",
        description="View own CPA branding settings",
        scope=PermissionScope.SELF,
        resource=ResourceType.CPA_BRANDING,
        action=PermissionAction.VIEW,
        requires_ownership=True
    )

    CPA_BRANDING_EDIT_SELF = Permission(
        code="cpa.branding.edit_self",
        name="Edit Own CPA Branding",
        description="Customize own CPA branding within tenant theme",
        scope=PermissionScope.SELF,
        resource=ResourceType.CPA_BRANDING,
        action=PermissionAction.EDIT,
        requires_ownership=True
    )

    # Client Management
    CPA_CLIENTS_VIEW = Permission(
        code="cpa.clients.view",
        name="View CPA Clients",
        description="View own assigned clients",
        scope=PermissionScope.CPA,
        resource=ResourceType.CPA_CLIENTS,
        action=PermissionAction.VIEW,
        requires_assignment=True
    )

    CPA_CLIENTS_CREATE = Permission(
        code="cpa.clients.create",
        name="Create Clients",
        description="Add new clients to own roster",
        scope=PermissionScope.CPA,
        resource=ResourceType.CPA_CLIENTS,
        action=PermissionAction.CREATE
    )

    CPA_CLIENTS_ASSIGN = Permission(
        code="cpa.clients.assign",
        name="Assign Clients",
        description="Assign clients to self or other CPAs (Partner only)",
        scope=PermissionScope.TENANT,
        resource=ResourceType.CPA_CLIENTS,
        action=PermissionAction.ASSIGN
    )

    # Tax Return Management
    CPA_RETURNS_VIEW = Permission(
        code="cpa.returns.view",
        name="View Tax Returns",
        description="View tax returns for assigned clients",
        scope=PermissionScope.CPA,
        resource=ResourceType.CPA_RETURNS,
        action=PermissionAction.VIEW,
        requires_assignment=True
    )

    CPA_RETURNS_EDIT = Permission(
        code="cpa.returns.edit",
        name="Edit Tax Returns",
        description="Edit tax returns for assigned clients",
        scope=PermissionScope.CPA,
        resource=ResourceType.CPA_RETURNS,
        action=PermissionAction.EDIT,
        requires_assignment=True
    )

    CPA_RETURNS_REVIEW = Permission(
        code="cpa.returns.review",
        name="Review Tax Returns",
        description="Review and provide feedback on tax returns",
        scope=PermissionScope.CPA,
        resource=ResourceType.TAX_RETURN_REVIEW,
        action=PermissionAction.EXECUTE,
        requires_assignment=True
    )

    CPA_RETURNS_APPROVE = Permission(
        code="cpa.returns.approve",
        name="Approve Tax Returns",
        description="Approve tax returns for filing",
        scope=PermissionScope.CPA,
        resource=ResourceType.TAX_RETURN_APPROVAL,
        action=PermissionAction.APPROVE,
        requires_assignment=True
    )

    CPA_RETURNS_GENERATE_FILING_PACKAGE = Permission(
        code="cpa.returns.generate_filing_package",
        name="Generate Filing Package",
        description="Generate filing package for external e-filing (platform does NOT e-file with IRS)",
        scope=PermissionScope.CPA,
        resource=ResourceType.TAX_RETURN_EFILE,  # Resource type kept for compatibility
        action=PermissionAction.EXECUTE,
        requires_assignment=True
    )

    # Backward compatibility alias
    CPA_RETURNS_EFILE = CPA_RETURNS_GENERATE_FILING_PACKAGE

    # =========================================================================
    # CLIENT-LEVEL PERMISSIONS (All clients are CPA's clients)
    # NOTE: No distinction between "direct" and "firm" clients - all same
    # =========================================================================

    # Own Profile
    CLIENT_PROFILE_VIEW_SELF = Permission(
        code="client.profile.view_self",
        name="View Own Profile",
        description="View own client profile",
        scope=PermissionScope.SELF,
        resource=ResourceType.CLIENT_PROFILE,
        action=PermissionAction.VIEW,
        requires_ownership=True
    )

    CLIENT_PROFILE_EDIT_SELF = Permission(
        code="client.profile.edit_self",
        name="Edit Own Profile",
        description="Edit own client profile information",
        scope=PermissionScope.SELF,
        resource=ResourceType.CLIENT_PROFILE,
        action=PermissionAction.EDIT,
        requires_ownership=True
    )

    # Own Returns
    CLIENT_RETURNS_VIEW_SELF = Permission(
        code="client.returns.view_self",
        name="View Own Returns",
        description="View own tax returns",
        scope=PermissionScope.SELF,
        resource=ResourceType.TAX_RETURN,
        action=PermissionAction.VIEW,
        requires_ownership=True
    )

    CLIENT_RETURNS_EDIT_SELF = Permission(
        code="client.returns.edit_self",
        name="Edit Own Returns",
        description="Edit own tax returns (DRAFT status only)",
        scope=PermissionScope.SELF,
        resource=ResourceType.TAX_RETURN,
        action=PermissionAction.EDIT,
        requires_ownership=True
    )

    CLIENT_RETURNS_CREATE = Permission(
        code="client.returns.create",
        name="Create Tax Returns",
        description="Start new tax returns",
        scope=PermissionScope.SELF,
        resource=ResourceType.TAX_RETURN,
        action=PermissionAction.CREATE,
        requires_ownership=True
    )

    # Documents
    CLIENT_DOCUMENTS_VIEW_SELF = Permission(
        code="client.documents.view_self",
        name="View Own Documents",
        description="View own uploaded documents",
        scope=PermissionScope.SELF,
        resource=ResourceType.DOCUMENT,
        action=PermissionAction.VIEW,
        requires_ownership=True
    )

    CLIENT_DOCUMENTS_UPLOAD = Permission(
        code="client.documents.upload",
        name="Upload Documents",
        description="Upload documents to own account",
        scope=PermissionScope.SELF,
        resource=ResourceType.DOCUMENT,
        action=PermissionAction.CREATE,
        requires_ownership=True
    )

    # Client Portal
    CLIENT_PORTAL_ACCESS = Permission(
        code="client.portal.access",
        name="Access Client Portal",
        description="Access the client portal",
        scope=PermissionScope.SELF,
        resource=ResourceType.CLIENT_PORTAL,
        action=PermissionAction.VIEW
    )

    CLIENT_COMMUNICATION_SEND = Permission(
        code="client.communication.send",
        name="Send Messages",
        description="Send messages to assigned CPA",
        scope=PermissionScope.CLIENT,
        resource=ResourceType.CLIENT_COMMUNICATION,
        action=PermissionAction.CREATE
    )

    # =========================================================================
    # FEATURE-SPECIFIC PERMISSIONS
    # =========================================================================

    # Express Lane
    FEATURE_EXPRESS_LANE_USE = Permission(
        code="feature.express_lane.use",
        name="Use Express Lane",
        description="Access Express Lane workflow",
        scope=PermissionScope.TENANT,
        resource=ResourceType.EXPRESS_LANE,
        action=PermissionAction.EXECUTE
    )

    # Smart Tax
    FEATURE_SMART_TAX_USE = Permission(
        code="feature.smart_tax.use",
        name="Use Smart Tax",
        description="Access Smart Tax workflow",
        scope=PermissionScope.TENANT,
        resource=ResourceType.SMART_TAX,
        action=PermissionAction.EXECUTE
    )

    # AI Chat
    FEATURE_AI_CHAT_USE = Permission(
        code="feature.ai_chat.use",
        name="Use AI Chat",
        description="Access AI Chat assistant",
        scope=PermissionScope.TENANT,
        resource=ResourceType.AI_CHAT,
        action=PermissionAction.EXECUTE
    )

    # Scenarios
    FEATURE_SCENARIOS_USE = Permission(
        code="feature.scenarios.use",
        name="Use Scenario Explorer",
        description="Access scenario explorer for what-if analysis",
        scope=PermissionScope.TENANT,
        resource=ResourceType.SCENARIOS,
        action=PermissionAction.EXECUTE
    )

    # Projections
    FEATURE_PROJECTIONS_USE = Permission(
        code="feature.projections.use",
        name="Use Tax Projections",
        description="Access 5-year tax projections",
        scope=PermissionScope.TENANT,
        resource=ResourceType.PROJECTIONS,
        action=PermissionAction.EXECUTE
    )

    # Integrations
    FEATURE_INTEGRATIONS_CONFIGURE = Permission(
        code="feature.integrations.configure",
        name="Configure Integrations",
        description="Set up QuickBooks, Plaid, etc. (Partner only)",
        scope=PermissionScope.TENANT,
        resource=ResourceType.INTEGRATIONS,
        action=PermissionAction.CONFIGURE
    )

    # API Access
    FEATURE_API_USE = Permission(
        code="feature.api.use",
        name="Use API",
        description="Access platform API programmatically",
        scope=PermissionScope.TENANT,
        resource=ResourceType.API_ACCESS,
        action=PermissionAction.EXECUTE
    )


# =============================================================================
# PERMISSION SETS (Collections of permissions)
# =============================================================================

class PermissionSets:
    """Pre-defined permission sets for common use cases"""

    # Platform Admin - Full access
    PLATFORM_ADMIN_PERMISSIONS = frozenset({
        # All platform permissions
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

        # All tenant permissions (for any tenant)
        Permissions.TENANT_BRANDING_VIEW,
        Permissions.TENANT_SETTINGS_VIEW,
        Permissions.TENANT_USERS_VIEW,
        Permissions.TENANT_ANALYTICS_VIEW,
        Permissions.TENANT_STATS_VIEW,
    })

    # Partner - Tenant admin
    PARTNER_PERMISSIONS = frozenset({
        # Tenant management
        Permissions.TENANT_BRANDING_VIEW,
        Permissions.TENANT_BRANDING_EDIT,
        Permissions.TENANT_SETTINGS_VIEW,
        Permissions.TENANT_SETTINGS_EDIT,
        Permissions.TENANT_USERS_VIEW,
        Permissions.TENANT_USERS_CREATE,
        Permissions.TENANT_USERS_EDIT,
        Permissions.TENANT_USERS_DELETE,
        Permissions.TENANT_ANALYTICS_VIEW,
        Permissions.TENANT_STATS_VIEW,

        # CPA capabilities
        Permissions.CPA_PROFILE_VIEW_SELF,
        Permissions.CPA_PROFILE_EDIT_SELF,
        Permissions.CPA_BRANDING_VIEW_SELF,
        Permissions.CPA_BRANDING_EDIT_SELF,
        Permissions.CPA_CLIENTS_VIEW,
        Permissions.CPA_CLIENTS_CREATE,
        Permissions.CPA_CLIENTS_ASSIGN,
        Permissions.CPA_RETURNS_VIEW,
        Permissions.CPA_RETURNS_EDIT,
        Permissions.CPA_RETURNS_REVIEW,
        Permissions.CPA_RETURNS_APPROVE,
        Permissions.CPA_RETURNS_GENERATE_FILING_PACKAGE,  # Generate filing package (NOT e-file)

        # Features
        Permissions.FEATURE_EXPRESS_LANE_USE,
        Permissions.FEATURE_SMART_TAX_USE,
        Permissions.FEATURE_AI_CHAT_USE,
        Permissions.FEATURE_SCENARIOS_USE,
        Permissions.FEATURE_PROJECTIONS_USE,
        Permissions.FEATURE_INTEGRATIONS_CONFIGURE,
        Permissions.FEATURE_API_USE,
    })

    # Staff - CPA capabilities
    STAFF_PERMISSIONS = frozenset({
        # View only tenant info
        Permissions.TENANT_BRANDING_VIEW,
        Permissions.TENANT_SETTINGS_VIEW,
        Permissions.TENANT_USERS_VIEW,

        # CPA capabilities
        Permissions.CPA_PROFILE_VIEW_SELF,
        Permissions.CPA_PROFILE_EDIT_SELF,
        Permissions.CPA_BRANDING_VIEW_SELF,
        Permissions.CPA_BRANDING_EDIT_SELF,
        Permissions.CPA_CLIENTS_VIEW,
        Permissions.CPA_CLIENTS_CREATE,
        Permissions.CPA_RETURNS_VIEW,
        Permissions.CPA_RETURNS_EDIT,
        Permissions.CPA_RETURNS_REVIEW,
        Permissions.CPA_RETURNS_APPROVE,
        Permissions.CPA_RETURNS_GENERATE_FILING_PACKAGE,  # Generate filing package (NOT e-file)

        # Features
        Permissions.FEATURE_EXPRESS_LANE_USE,
        Permissions.FEATURE_SMART_TAX_USE,
        Permissions.FEATURE_AI_CHAT_USE,
        Permissions.FEATURE_SCENARIOS_USE,
        Permissions.FEATURE_PROJECTIONS_USE,
    })

    # Client Permissions - All clients are CPA's clients (no distinction)
    # NOTE: Platform is B2B only. All clients access through CPA's portal.
    CLIENT_PERMISSIONS = frozenset({
        # Self profile
        Permissions.CLIENT_PROFILE_VIEW_SELF,
        Permissions.CLIENT_PROFILE_EDIT_SELF,

        # Own returns
        Permissions.CLIENT_RETURNS_VIEW_SELF,
        Permissions.CLIENT_RETURNS_EDIT_SELF,
        Permissions.CLIENT_RETURNS_CREATE,

        # Documents
        Permissions.CLIENT_DOCUMENTS_VIEW_SELF,
        Permissions.CLIENT_DOCUMENTS_UPLOAD,

        # Portal
        Permissions.CLIENT_PORTAL_ACCESS,
        Permissions.CLIENT_COMMUNICATION_SEND,

        # Features
        Permissions.FEATURE_EXPRESS_LANE_USE,
        Permissions.FEATURE_SMART_TAX_USE,
        Permissions.FEATURE_SCENARIOS_USE,
        Permissions.FEATURE_PROJECTIONS_USE,
    })

    # Aliases for backward compatibility - ALL clients treated the same
    FIRM_CLIENT_PERMISSIONS = CLIENT_PERMISSIONS
    DIRECT_CLIENT_PERMISSIONS = CLIENT_PERMISSIONS  # DEPRECATED: Same as FIRM_CLIENT

    # Anonymous - Not logged in
    ANONYMOUS_PERMISSIONS = frozenset({
        Permissions.CLIENT_RETURNS_CREATE,  # Can start return
        Permissions.FEATURE_EXPRESS_LANE_USE,  # Can use express lane
    })


def get_permissions_for_role(role_name: str) -> Set[Permission]:
    """Get permission set for a role"""
    role_map = {
        'PLATFORM_ADMIN': PermissionSets.PLATFORM_ADMIN_PERMISSIONS,
        'PARTNER': PermissionSets.PARTNER_PERMISSIONS,
        'STAFF': PermissionSets.STAFF_PERMISSIONS,
        'FIRM_CLIENT': PermissionSets.FIRM_CLIENT_PERMISSIONS,
        'DIRECT_CLIENT': PermissionSets.DIRECT_CLIENT_PERMISSIONS,
        'ANONYMOUS': PermissionSets.ANONYMOUS_PERMISSIONS,
    }
    return role_map.get(role_name, set())


def has_permission(
    user_permissions: Set[Permission],
    required_permission: Permission,
    user_id: str = None,
    resource_owner_id: str = None,
    assigned_cpa_id: str = None
) -> bool:
    """
    Check if user has a specific permission.

    Args:
        user_permissions: Set of permissions the user has
        required_permission: Permission being checked
        user_id: ID of the user performing the action
        resource_owner_id: ID of the resource owner
        assigned_cpa_id: ID of the assigned CPA (for client resources)

    Returns:
        True if user has permission, False otherwise
    """
    # Check if user has the permission
    if required_permission not in user_permissions:
        return False

    # Check ownership requirement
    if required_permission.requires_ownership:
        if user_id is None or resource_owner_id is None:
            return False
        if user_id != resource_owner_id:
            return False

    # Check assignment requirement
    if required_permission.requires_assignment:
        if user_id is None or assigned_cpa_id is None:
            return False
        if user_id != assigned_cpa_id:
            return False

    return True
