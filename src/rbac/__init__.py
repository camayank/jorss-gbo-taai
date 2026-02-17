"""
CA4CPA GLOBAL LLC - Role-Based Access Control (RBAC)

Clean 8-role RBAC system for the tax platform.

Hierarchy:
    Level 0 - Platform (CA4CPA Internal)
        - super_admin: Full platform access (Founders, CTO)
        - platform_admin: Platform operations (Operations Manager)
        - support: Customer support (Help Desk)
        - billing: Finance operations (Finance Team)

    Level 1A - CPA Firm (B2B Customers)
        - partner: CPA firm owner/admin
        - staff: CPA firm employee

    Level 1B - Direct Consumer (B2C)
        - direct_client: Self-service taxpayer

    Level 2 - CPA's Client (B2B2C)
        - firm_client: Taxpayer working with a CPA

Usage:
    from rbac import Role, Permission, require_role, require_permission

    @router.get("/admin/firms")
    async def list_firms(ctx: AuthContext = Depends(require_role(Role.PLATFORM_ADMIN))):
        ...
"""

from .roles import Role, RoleInfo, ROLES, get_role_info
from .permissions import Permission, PermissionInfo, PERMISSIONS, ROLE_PERMISSIONS, get_permission_info
from .context import AuthContext, UserType
from .dependencies import (
    get_auth_context,
    require_auth,
    optional_auth,
    require_role,
    require_permission,
    require_platform_admin,
    require_firm_access,
    get_current_firm,
    get_current_firm_id,
)

__all__ = [
    # Roles
    "Role",
    "RoleInfo",
    "ROLES",
    "get_role_info",

    # Permissions
    "Permission",
    "PermissionInfo",
    "PERMISSIONS",
    "ROLE_PERMISSIONS",
    "get_permission_info",

    # Context
    "AuthContext",
    "UserType",

    # Dependencies
    "get_auth_context",
    "require_auth",
    "optional_auth",
    "require_role",
    "require_permission",
    "require_platform_admin",
    "require_firm_access",
    "get_current_firm",
    "get_current_firm_id",
]
