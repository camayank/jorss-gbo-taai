"""
DEPRECATED: Role-Based Access Control (RBAC)

This module is deprecated. Use src/rbac/ instead.

For backward compatibility, this re-exports from the new RBAC module.

New code should use:
    from rbac import Role, Permission, AuthContext, require_auth, require_permission
"""

# Re-export from new RBAC module for backward compatibility
from rbac import (
    Role,
    Permission,
    AuthContext,
    get_auth_context,
    require_auth,
    require_role,
    require_permission,
    require_platform_admin,
)

# Backward compatibility aliases
TenantContext = AuthContext
get_current_user = require_auth
require_firm_admin = require_role(Role.PARTNER)

__all__ = [
    "Role",
    "Permission",
    "AuthContext",
    "TenantContext",  # Deprecated alias
    "get_auth_context",
    "get_current_user",  # Deprecated alias
    "require_auth",
    "require_role",
    "require_permission",
    "require_platform_admin",
    "require_firm_admin",  # Deprecated alias
]
