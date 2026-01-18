"""
Global RBAC (Role-Based Access Control) System.

Provides unified authorization across Admin Panel, CPA Panel, and Client Portal.

Features:
- Database-driven role management
- 5-level access control hierarchy (Platform → Partner → Firm → User → Resource)
- Admin-configurable custom roles
- White-label partner support
- Multi-layer caching with real-time invalidation
- Per-user permission overrides
- Subscription tier integration

Usage:
    from core.rbac import get_rbac_context, require_permissions

    @router.get("/protected")
    async def protected_route(ctx: RBACContext = Depends(get_rbac_context)):
        if ctx.has_permission("manage_team"):
            ...

    @router.post("/admin-only")
    async def admin_route(
        ctx: RBACContext = Depends(get_rbac_context),
        _: None = Depends(RequirePermission("manage_firm"))
    ):
        ...
"""

from .models import (
    Permission,
    RoleTemplate,
    RolePermission,
    UserRoleAssignment,
    UserPermissionOverride,
    RBACauditLog,
    PermissionCacheVersion,
    HierarchyLevel,
    PermissionCategory,
    OverrideAction,
)

from .permissions import (
    PermissionService,
    get_permission_service,
    SYSTEM_PERMISSIONS,
    PermissionCatalog,
)

from .roles import (
    RoleService,
    get_role_service,
    SYSTEM_ROLES,
    RoleCatalog,
)

from .cache import (
    PermissionCache,
    get_permission_cache,
    CacheScope,
)

from .middleware import (
    RBACMiddleware,
)

from .dependencies import (
    get_rbac_context,
    RBACContext,
    require_permissions,
    require_any_permission,
    RequirePermission,
    RequireRole,
    require_firm_context,
    require_platform_admin,
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
    "SYSTEM_PERMISSIONS",
    "PermissionCatalog",
    # Role Service
    "RoleService",
    "get_role_service",
    "SYSTEM_ROLES",
    "RoleCatalog",
    # Cache
    "PermissionCache",
    "get_permission_cache",
    "CacheScope",
    # Middleware
    "RBACMiddleware",
    # Dependencies
    "get_rbac_context",
    "RBACContext",
    "require_permissions",
    "require_any_permission",
    "RequirePermission",
    "RequireRole",
    "require_firm_context",
    "require_platform_admin",
]
