"""
Core Module - Shared infrastructure for cross-cutting concerns.

This module provides:
- Global RBAC (Role-Based Access Control) system
- Partner management for white-label support
- Shared caching infrastructure
- Cross-module authentication
- Unified Platform API for all user types
- Unified user models and services
"""

# Core Platform API
from .api import core_router, API_TAGS
from .models.user import (
    UserType,
    CPARole,
    UnifiedUser,
    UserProfile,
    UserPreferences,
    UserContext,
)
from .services import (
    CoreAuthService,
    get_auth_service,
    CoreUserService,
    get_user_service,
)

# Optional RBAC exports (module may not exist in this workspace build)
_RBAC_EXPORTS = []
try:
    from .rbac import (
        # Models
        Permission,
        RoleTemplate,
        RolePermission,
        UserRoleAssignment,
        UserPermissionOverride,
        RBACauditLog,
        PermissionCacheVersion,
        # Enums
        HierarchyLevel,
        PermissionCategory,
        OverrideAction,
        # Permission Service
        PermissionService,
        get_permission_service,
        # Role Service
        RoleService,
        get_role_service,
        # Cache
        PermissionCache,
        get_permission_cache,
        # Middleware
        RBACMiddleware,
        # Dependencies
        get_rbac_context,
        RBACContext,
        require_permissions,
        require_any_permission,
        RequirePermission,
    )

    _RBAC_EXPORTS = [
        "Permission",
        "RoleTemplate",
        "RolePermission",
        "UserRoleAssignment",
        "UserPermissionOverride",
        "RBACauditLog",
        "PermissionCacheVersion",
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
        "get_rbac_context",
        "RBACContext",
        "require_permissions",
        "require_any_permission",
        "RequirePermission",
    ]
except ImportError:
    pass

__all__ = [
    # Core Platform API
    "core_router",
    "API_TAGS",
    # Unified User Models
    "UserType",
    "CPARole",
    "UnifiedUser",
    "UserProfile",
    "UserPreferences",
    "UserContext",
    # Core Services
    "CoreAuthService",
    "get_auth_service",
    "CoreUserService",
    "get_user_service",
] + _RBAC_EXPORTS
