"""
Admin Panel Authentication & Authorization

Provides:
- JWT-based authentication for firm users and platform admins
- Role-Based Access Control (RBAC) middleware
- Permission decorators for route protection
- Multi-tenant context management
"""

from .jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenPayload,
    TokenType,
)
from .rbac import (
    require_permission,
    require_role,
    require_firm_admin,
    require_platform_admin,
    get_current_user,
    get_current_firm,
    TenantContext,
)
from .password import (
    hash_password,
    verify_password,
    validate_password_strength,
)

__all__ = [
    # JWT
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "TokenPayload",
    "TokenType",
    # RBAC
    "require_permission",
    "require_role",
    "require_firm_admin",
    "require_platform_admin",
    "get_current_user",
    "get_current_firm",
    "TenantContext",
    # Password
    "hash_password",
    "verify_password",
    "validate_password_strength",
]
