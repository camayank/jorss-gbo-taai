"""
Core Module - Shared infrastructure for cross-cutting concerns.

This module provides:
- Global RBAC (Role-Based Access Control) system
- Partner management for white-label support
- Shared caching infrastructure
- Cross-module authentication
"""

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

__all__ = [
    # Models
    "Permission",
    "RoleTemplate",
    "RolePermission",
    "UserRoleAssignment",
    "UserPermissionOverride",
    "RBACauditLog",
    "PermissionCacheVersion",
    # Enums
    "HierarchyLevel",
    "PermissionCategory",
    "OverrideAction",
    # Permission Service
    "PermissionService",
    "get_permission_service",
    # Role Service
    "RoleService",
    "get_role_service",
    # Cache
    "PermissionCache",
    "get_permission_cache",
    # Middleware
    "RBACMiddleware",
    # Dependencies
    "get_rbac_context",
    "RBACContext",
    "require_permissions",
    "require_any_permission",
    "RequirePermission",
]
