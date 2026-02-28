"""
CA4CPA GLOBAL LLC - Permission Definitions

Permissions are organized by category and mapped to roles.

Categories:
    - PLATFORM: CA4CPA internal operations
    - FIRM: CPA firm management
    - TEAM: Team/user management within a firm
    - CLIENT: Client management
    - RETURN: Tax return operations
    - DOCUMENT: Document management
    - BILLING: Subscription and payments
"""

from enum import Enum
from dataclasses import dataclass
from typing import Set, FrozenSet

from .roles import Role, PLATFORM_ROLES, FIRM_ROLES


class Permission(str, Enum):
    """
    All permissions in the system.

    Naming: category_action (e.g., firm_view, return_edit)
    """

    # =========================================================================
    # PLATFORM PERMISSIONS (CA4CPA Internal Only)
    # =========================================================================

    # Firm Management (by CA4CPA)
    PLATFORM_VIEW_ALL_FIRMS = "platform_view_all_firms"
    PLATFORM_MANAGE_FIRMS = "platform_manage_firms"
    PLATFORM_IMPERSONATE = "platform_impersonate"

    # Subscription Management
    PLATFORM_VIEW_SUBSCRIPTIONS = "platform_view_subscriptions"
    PLATFORM_MANAGE_SUBSCRIPTIONS = "platform_manage_subscriptions"

    # Platform Operations
    PLATFORM_VIEW_METRICS = "platform_view_metrics"
    PLATFORM_MANAGE_FEATURES = "platform_manage_features"
    PLATFORM_VIEW_AUDIT_LOGS = "platform_view_audit_logs"
    PLATFORM_MANAGE_ADMINS = "platform_manage_admins"

    # =========================================================================
    # FIRM PERMISSIONS (CPA Firm Level)
    # =========================================================================

    # Firm Settings
    FIRM_VIEW_SETTINGS = "firm_view_settings"
    FIRM_MANAGE_SETTINGS = "firm_manage_settings"
    FIRM_MANAGE_BRANDING = "firm_manage_branding"
    FIRM_VIEW_ANALYTICS = "firm_view_analytics"

    # Firm Billing
    FIRM_VIEW_BILLING = "firm_view_billing"
    FIRM_MANAGE_BILLING = "firm_manage_billing"

    # Firm API Keys
    FIRM_MANAGE_API_KEYS = "firm_manage_api_keys"

    # Firm Audit
    FIRM_VIEW_AUDIT = "firm_view_audit"

    # =========================================================================
    # TEAM PERMISSIONS (Within a Firm)
    # =========================================================================

    TEAM_VIEW = "team_view"
    TEAM_INVITE = "team_invite"
    TEAM_MANAGE = "team_manage"
    TEAM_REMOVE = "team_remove"

    # =========================================================================
    # CLIENT PERMISSIONS (CPA's Clients)
    # =========================================================================

    CLIENT_VIEW_OWN = "client_view_own"          # View own assigned clients
    CLIENT_VIEW_ALL = "client_view_all"          # View all firm's clients
    CLIENT_CREATE = "client_create"
    CLIENT_EDIT = "client_edit"
    CLIENT_ARCHIVE = "client_archive"
    CLIENT_ASSIGN = "client_assign"              # Assign clients to staff

    # =========================================================================
    # TAX RETURN PERMISSIONS
    # =========================================================================

    RETURN_VIEW_OWN = "return_view_own"          # View own/assigned returns
    RETURN_VIEW_ALL = "return_view_all"          # View all firm's returns
    RETURN_CREATE = "return_create"
    RETURN_EDIT = "return_edit"
    RETURN_SUBMIT = "return_submit"
    RETURN_REVIEW = "return_review"
    RETURN_APPROVE = "return_approve"

    # Scenarios and Analysis
    RETURN_RUN_SCENARIOS = "return_run_scenarios"
    RETURN_GENERATE_ADVISORY = "return_generate_advisory"

    # =========================================================================
    # DOCUMENT PERMISSIONS
    # =========================================================================

    DOCUMENT_VIEW = "document_view"
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DELETE = "document_delete"

    # =========================================================================
    # SELF-SERVICE PERMISSIONS (All Clients)
    # NOTE: All clients are CPA's clients (no B2C channel). These permissions
    # apply to all clients equally - there is no DIRECT_CLIENT distinction.
    # =========================================================================

    SELF_VIEW_RETURN = "self_view_return"
    SELF_EDIT_RETURN = "self_edit_return"
    SELF_UPLOAD_DOCS = "self_upload_docs"
    SELF_VIEW_STATUS = "self_view_status"


class Category(str, Enum):
    """Permission categories."""
    PLATFORM = "platform"
    FIRM = "firm"
    TEAM = "team"
    CLIENT = "client"
    RETURN = "return"
    DOCUMENT = "document"
    SELF = "self"


@dataclass(frozen=True)
class PermissionInfo:
    """Complete information about a permission."""
    permission: Permission
    name: str
    description: str
    category: Category


# =============================================================================
# PERMISSION REGISTRY
# =============================================================================

PERMISSIONS: dict[Permission, PermissionInfo] = {
    # Platform Permissions
    Permission.PLATFORM_VIEW_ALL_FIRMS: PermissionInfo(
        Permission.PLATFORM_VIEW_ALL_FIRMS,
        "View All Firms",
        "View all CPA firms on the platform",
        Category.PLATFORM,
    ),
    Permission.PLATFORM_MANAGE_FIRMS: PermissionInfo(
        Permission.PLATFORM_MANAGE_FIRMS,
        "Manage Firms",
        "Create, edit, suspend CPA firms",
        Category.PLATFORM,
    ),
    Permission.PLATFORM_IMPERSONATE: PermissionInfo(
        Permission.PLATFORM_IMPERSONATE,
        "Impersonate",
        "Impersonate firms/users for support",
        Category.PLATFORM,
    ),
    Permission.PLATFORM_VIEW_SUBSCRIPTIONS: PermissionInfo(
        Permission.PLATFORM_VIEW_SUBSCRIPTIONS,
        "View Subscriptions",
        "View all subscription data",
        Category.PLATFORM,
    ),
    Permission.PLATFORM_MANAGE_SUBSCRIPTIONS: PermissionInfo(
        Permission.PLATFORM_MANAGE_SUBSCRIPTIONS,
        "Manage Subscriptions",
        "Modify subscriptions, process refunds",
        Category.PLATFORM,
    ),
    Permission.PLATFORM_VIEW_METRICS: PermissionInfo(
        Permission.PLATFORM_VIEW_METRICS,
        "View Metrics",
        "View platform-wide metrics and analytics",
        Category.PLATFORM,
    ),
    Permission.PLATFORM_MANAGE_FEATURES: PermissionInfo(
        Permission.PLATFORM_MANAGE_FEATURES,
        "Manage Features",
        "Control feature flags and rollouts",
        Category.PLATFORM,
    ),
    Permission.PLATFORM_VIEW_AUDIT_LOGS: PermissionInfo(
        Permission.PLATFORM_VIEW_AUDIT_LOGS,
        "View Audit Logs",
        "View platform-wide audit logs",
        Category.PLATFORM,
    ),
    Permission.PLATFORM_MANAGE_ADMINS: PermissionInfo(
        Permission.PLATFORM_MANAGE_ADMINS,
        "Manage Admins",
        "Add/remove platform admins",
        Category.PLATFORM,
    ),

    # Firm Permissions
    Permission.FIRM_VIEW_SETTINGS: PermissionInfo(
        Permission.FIRM_VIEW_SETTINGS,
        "View Firm Settings",
        "View firm configuration",
        Category.FIRM,
    ),
    Permission.FIRM_MANAGE_SETTINGS: PermissionInfo(
        Permission.FIRM_MANAGE_SETTINGS,
        "Manage Firm Settings",
        "Edit firm configuration",
        Category.FIRM,
    ),
    Permission.FIRM_MANAGE_BRANDING: PermissionInfo(
        Permission.FIRM_MANAGE_BRANDING,
        "Manage Branding",
        "Update logo, colors, white-label settings",
        Category.FIRM,
    ),
    Permission.FIRM_VIEW_ANALYTICS: PermissionInfo(
        Permission.FIRM_VIEW_ANALYTICS,
        "View Analytics",
        "View firm analytics and reports",
        Category.FIRM,
    ),
    Permission.FIRM_VIEW_BILLING: PermissionInfo(
        Permission.FIRM_VIEW_BILLING,
        "View Billing",
        "View invoices and payment history",
        Category.FIRM,
    ),
    Permission.FIRM_MANAGE_BILLING: PermissionInfo(
        Permission.FIRM_MANAGE_BILLING,
        "Manage Billing",
        "Update payment methods, change plan",
        Category.FIRM,
    ),

    # Team Permissions
    Permission.TEAM_VIEW: PermissionInfo(
        Permission.TEAM_VIEW,
        "View Team",
        "View team members",
        Category.TEAM,
    ),
    Permission.TEAM_INVITE: PermissionInfo(
        Permission.TEAM_INVITE,
        "Invite Team",
        "Send invitations to new team members",
        Category.TEAM,
    ),
    Permission.TEAM_MANAGE: PermissionInfo(
        Permission.TEAM_MANAGE,
        "Manage Team",
        "Edit team member roles and permissions",
        Category.TEAM,
    ),
    Permission.TEAM_REMOVE: PermissionInfo(
        Permission.TEAM_REMOVE,
        "Remove Team",
        "Remove team members",
        Category.TEAM,
    ),

    # Client Permissions
    Permission.CLIENT_VIEW_OWN: PermissionInfo(
        Permission.CLIENT_VIEW_OWN,
        "View Own Clients",
        "View assigned clients only",
        Category.CLIENT,
    ),
    Permission.CLIENT_VIEW_ALL: PermissionInfo(
        Permission.CLIENT_VIEW_ALL,
        "View All Clients",
        "View all firm clients",
        Category.CLIENT,
    ),
    Permission.CLIENT_CREATE: PermissionInfo(
        Permission.CLIENT_CREATE,
        "Create Client",
        "Add new clients",
        Category.CLIENT,
    ),
    Permission.CLIENT_EDIT: PermissionInfo(
        Permission.CLIENT_EDIT,
        "Edit Client",
        "Update client information",
        Category.CLIENT,
    ),
    Permission.CLIENT_ARCHIVE: PermissionInfo(
        Permission.CLIENT_ARCHIVE,
        "Archive Client",
        "Archive/unarchive clients",
        Category.CLIENT,
    ),
    Permission.CLIENT_ASSIGN: PermissionInfo(
        Permission.CLIENT_ASSIGN,
        "Assign Client",
        "Assign clients to staff members",
        Category.CLIENT,
    ),

    # Return Permissions
    Permission.RETURN_VIEW_OWN: PermissionInfo(
        Permission.RETURN_VIEW_OWN,
        "View Own Returns",
        "View assigned returns only",
        Category.RETURN,
    ),
    Permission.RETURN_VIEW_ALL: PermissionInfo(
        Permission.RETURN_VIEW_ALL,
        "View All Returns",
        "View all firm returns",
        Category.RETURN,
    ),
    Permission.RETURN_CREATE: PermissionInfo(
        Permission.RETURN_CREATE,
        "Create Return",
        "Start new tax returns",
        Category.RETURN,
    ),
    Permission.RETURN_EDIT: PermissionInfo(
        Permission.RETURN_EDIT,
        "Edit Return",
        "Edit tax return data",
        Category.RETURN,
    ),
    Permission.RETURN_SUBMIT: PermissionInfo(
        Permission.RETURN_SUBMIT,
        "Submit Return",
        "Submit returns for review",
        Category.RETURN,
    ),
    Permission.RETURN_REVIEW: PermissionInfo(
        Permission.RETURN_REVIEW,
        "Review Return",
        "Review submitted returns",
        Category.RETURN,
    ),
    Permission.RETURN_APPROVE: PermissionInfo(
        Permission.RETURN_APPROVE,
        "Approve Return",
        "Approve returns for filing",
        Category.RETURN,
    ),
    Permission.RETURN_RUN_SCENARIOS: PermissionInfo(
        Permission.RETURN_RUN_SCENARIOS,
        "Run Scenarios",
        "Run tax scenario analysis",
        Category.RETURN,
    ),
    Permission.RETURN_GENERATE_ADVISORY: PermissionInfo(
        Permission.RETURN_GENERATE_ADVISORY,
        "Generate Advisory",
        "Generate advisory reports",
        Category.RETURN,
    ),

    # Document Permissions
    Permission.DOCUMENT_VIEW: PermissionInfo(
        Permission.DOCUMENT_VIEW,
        "View Documents",
        "View uploaded documents",
        Category.DOCUMENT,
    ),
    Permission.DOCUMENT_UPLOAD: PermissionInfo(
        Permission.DOCUMENT_UPLOAD,
        "Upload Documents",
        "Upload new documents",
        Category.DOCUMENT,
    ),
    Permission.DOCUMENT_DELETE: PermissionInfo(
        Permission.DOCUMENT_DELETE,
        "Delete Documents",
        "Delete uploaded documents",
        Category.DOCUMENT,
    ),

    # Self-Service Permissions
    Permission.SELF_VIEW_RETURN: PermissionInfo(
        Permission.SELF_VIEW_RETURN,
        "View Own Return",
        "View own tax return",
        Category.SELF,
    ),
    Permission.SELF_EDIT_RETURN: PermissionInfo(
        Permission.SELF_EDIT_RETURN,
        "Edit Own Return",
        "Edit own tax return",
        Category.SELF,
    ),
    Permission.SELF_UPLOAD_DOCS: PermissionInfo(
        Permission.SELF_UPLOAD_DOCS,
        "Upload Own Docs",
        "Upload documents for own return",
        Category.SELF,
    ),
    Permission.SELF_VIEW_STATUS: PermissionInfo(
        Permission.SELF_VIEW_STATUS,
        "View Status",
        "View return status and progress",
        Category.SELF,
    ),
}


def get_permission_info(permission: Permission) -> PermissionInfo:
    """Get information about a permission."""
    return PERMISSIONS[permission]


# =============================================================================
# ROLE -> PERMISSION MAPPING
# =============================================================================

ROLE_PERMISSIONS: dict[Role, FrozenSet[Permission]] = {
    # -------------------------------------------------------------------------
    # SUPER_ADMIN: Everything
    # -------------------------------------------------------------------------
    Role.SUPER_ADMIN: frozenset(Permission),  # All permissions

    # -------------------------------------------------------------------------
    # PLATFORM_ADMIN: Platform operations (no admin management)
    # -------------------------------------------------------------------------
    Role.PLATFORM_ADMIN: frozenset({
        # Platform
        Permission.PLATFORM_VIEW_ALL_FIRMS,
        Permission.PLATFORM_MANAGE_FIRMS,
        Permission.PLATFORM_IMPERSONATE,
        Permission.PLATFORM_VIEW_SUBSCRIPTIONS,
        Permission.PLATFORM_MANAGE_SUBSCRIPTIONS,
        Permission.PLATFORM_VIEW_METRICS,
        Permission.PLATFORM_MANAGE_FEATURES,
        Permission.PLATFORM_VIEW_AUDIT_LOGS,
        # No PLATFORM_MANAGE_ADMINS - only super_admin can do that
    }),

    # -------------------------------------------------------------------------
    # SUPPORT: Read + Impersonate (no write)
    # -------------------------------------------------------------------------
    Role.SUPPORT: frozenset({
        Permission.PLATFORM_VIEW_ALL_FIRMS,
        Permission.PLATFORM_IMPERSONATE,
        Permission.PLATFORM_VIEW_SUBSCRIPTIONS,
        Permission.PLATFORM_VIEW_METRICS,
        Permission.PLATFORM_VIEW_AUDIT_LOGS,
    }),

    # -------------------------------------------------------------------------
    # BILLING: Finance operations only
    # -------------------------------------------------------------------------
    Role.BILLING: frozenset({
        Permission.PLATFORM_VIEW_ALL_FIRMS,
        Permission.PLATFORM_VIEW_SUBSCRIPTIONS,
        Permission.PLATFORM_MANAGE_SUBSCRIPTIONS,
        Permission.PLATFORM_VIEW_METRICS,
    }),

    # -------------------------------------------------------------------------
    # PARTNER: Full access to their firm
    # -------------------------------------------------------------------------
    Role.PARTNER: frozenset({
        # Firm
        Permission.FIRM_VIEW_SETTINGS,
        Permission.FIRM_MANAGE_SETTINGS,
        Permission.FIRM_MANAGE_BRANDING,
        Permission.FIRM_VIEW_ANALYTICS,
        Permission.FIRM_VIEW_BILLING,
        Permission.FIRM_MANAGE_BILLING,
        # Team
        Permission.TEAM_VIEW,
        Permission.TEAM_INVITE,
        Permission.TEAM_MANAGE,
        Permission.TEAM_REMOVE,
        # Client
        Permission.CLIENT_VIEW_ALL,
        Permission.CLIENT_CREATE,
        Permission.CLIENT_EDIT,
        Permission.CLIENT_ARCHIVE,
        Permission.CLIENT_ASSIGN,
        # Return
        Permission.RETURN_VIEW_ALL,
        Permission.RETURN_CREATE,
        Permission.RETURN_EDIT,
        Permission.RETURN_SUBMIT,
        Permission.RETURN_REVIEW,
        Permission.RETURN_APPROVE,
        Permission.RETURN_RUN_SCENARIOS,
        Permission.RETURN_GENERATE_ADVISORY,
        # Document
        Permission.DOCUMENT_VIEW,
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_DELETE,
    }),

    # -------------------------------------------------------------------------
    # STAFF: Work on assigned clients, limited admin
    # -------------------------------------------------------------------------
    Role.STAFF: frozenset({
        # Firm (view only)
        Permission.FIRM_VIEW_SETTINGS,
        Permission.FIRM_VIEW_ANALYTICS,
        # Team (view only)
        Permission.TEAM_VIEW,
        # Client (assigned only + create)
        Permission.CLIENT_VIEW_OWN,
        Permission.CLIENT_CREATE,
        Permission.CLIENT_EDIT,
        # Return (assigned)
        Permission.RETURN_VIEW_OWN,
        Permission.RETURN_CREATE,
        Permission.RETURN_EDIT,
        Permission.RETURN_SUBMIT,
        Permission.RETURN_RUN_SCENARIOS,
        Permission.RETURN_GENERATE_ADVISORY,
        # Document
        Permission.DOCUMENT_VIEW,
        Permission.DOCUMENT_UPLOAD,
    }),

    # -------------------------------------------------------------------------
    # CLIENT PERMISSIONS (All clients treated the same)
    # NOTE: This platform is B2B only. All clients belong to CPA firms.
    # DIRECT_CLIENT and FIRM_CLIENT have IDENTICAL permissions.
    # -------------------------------------------------------------------------
    Role.FIRM_CLIENT: frozenset({
        Permission.SELF_VIEW_RETURN,
        Permission.SELF_EDIT_RETURN,
        Permission.SELF_VIEW_STATUS,
        Permission.SELF_UPLOAD_DOCS,
        Permission.DOCUMENT_VIEW,
        Permission.DOCUMENT_UPLOAD,
    }),

    # DEPRECATED: Use FIRM_CLIENT - kept for backward compatibility only
    # All clients are treated the same regardless of how they were created
    Role.DIRECT_CLIENT: frozenset({
        Permission.SELF_VIEW_RETURN,
        Permission.SELF_EDIT_RETURN,
        Permission.SELF_VIEW_STATUS,
        Permission.SELF_UPLOAD_DOCS,
        Permission.DOCUMENT_VIEW,
        Permission.DOCUMENT_UPLOAD,
    }),
}


def get_role_permissions(role: Role) -> FrozenSet[Permission]:
    """Get all permissions for a role."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: Role, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
