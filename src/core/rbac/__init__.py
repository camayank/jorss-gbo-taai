"""
Core RBAC package exports.
"""

from .cache import PermissionCache, get_permission_cache
from .dependencies import (
    RBACContext,
    RequirePermission,
    RequireSubscriptionTier,
    get_rbac_context,
    require_any_permission,
    require_firm_admin,
    require_permissions,
    require_platform_admin,
)
from .middleware import RBACMiddleware, RBACMiddlewareConfig
from .models import (
    ClientAccessGrant,
    HierarchyLevel,
    OverrideAction,
    Partner,
    PartnerAdmin,
    PartnerFirm,
    Permission,
    PermissionCacheVersion,
    PermissionCategory,
    RBACAuditLog,
    RBACauditLog,
    RolePermission,
    RoleTemplate,
    UserPermissionOverride,
    UserRoleAssignment,
)
from .services import PermissionService, RoleService, get_permission_service, get_role_service

__all__ = [
    "Permission",
    "RoleTemplate",
    "RolePermission",
    "UserRoleAssignment",
    "UserPermissionOverride",
    "RBACAuditLog",
    "RBACauditLog",
    "PermissionCacheVersion",
    "Partner",
    "PartnerFirm",
    "PartnerAdmin",
    "ClientAccessGrant",
    "HierarchyLevel",
    "PermissionCategory",
    "OverrideAction",
    "PermissionService",
    "get_permission_service",
    "RoleService",
    "get_role_service",
    "PermissionCache",
    "get_permission_cache",
    "RBACMiddleware",
    "RBACMiddlewareConfig",
    "get_rbac_context",
    "RBACContext",
    "require_permissions",
    "require_any_permission",
    "RequirePermission",
    "RequireSubscriptionTier",
    "require_firm_admin",
    "require_platform_admin",
]

