"""
Role-Based Access Control (RBAC) - Permission enforcement for API routes.

Provides:
- Permission decorators for route protection
- Multi-tenant context management
- Current user/firm dependency injection

NOTE: This module is being deprecated in favor of core.rbac.
New code should use core.rbac.dependencies instead.
This module provides backward-compatible aliases.
"""

import os
from functools import wraps
from typing import Optional, Callable, List, Set, Union
from dataclasses import dataclass
import logging

from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .jwt_handler import decode_token, TokenPayload, TokenType
from ..models.user import UserRole, UserPermission

logger = logging.getLogger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)

# Feature flag for new RBAC system
# Set to True to enable the new core.rbac system
RBAC_V2_ENABLED = True

# =============================================================================
# TESTING MODE CONFIGURATION
# =============================================================================
# Testing mode bypasses authentication for end-to-end testing.
#
# SECURITY: Testing mode requires BOTH conditions:
#   1. TESTING_MODE=true environment variable
#   2. ENVIRONMENT must be 'development', 'test', or 'local' (NOT 'production' or 'staging')

def _is_testing_mode_allowed() -> bool:
    """
    Determine if testing mode can be safely enabled.

    Testing mode is ONLY allowed when:
    1. TESTING_MODE environment variable is explicitly set to "true"
    2. ENVIRONMENT is NOT production or staging
    3. Optional: TESTING_MODE_SECRET matches (for additional security)
    """
    testing_requested = os.environ.get("TESTING_MODE", "false").lower() == "true"

    if not testing_requested:
        return False

    # Check environment - block testing mode in production/staging
    environment = os.environ.get("ENVIRONMENT", "development").lower()
    production_environments = {"production", "prod", "staging", "stage", "live"}

    if environment in production_environments:
        logger.critical(
            "SECURITY ALERT: Admin TESTING_MODE=true attempted in %s environment. "
            "This is BLOCKED for security. Remove TESTING_MODE from environment.",
            environment
        )
        return False

    # Optional additional security: require a secret key for testing mode
    testing_secret = os.environ.get("TESTING_MODE_SECRET", "")
    expected_secret = os.environ.get("TESTING_MODE_EXPECTED_SECRET", "")

    if expected_secret and testing_secret != expected_secret:
        logger.warning(
            "Admin TESTING_MODE requested but TESTING_MODE_SECRET does not match. "
            "Testing mode DISABLED."
        )
        return False

    return True


TESTING_MODE = _is_testing_mode_allowed()

if TESTING_MODE:
    logger.warning("=" * 70)
    logger.warning("Admin RBAC TESTING MODE ENABLED - Authentication bypassed")
    logger.warning("This should ONLY be used in development/test environments!")
    logger.warning("Set ENVIRONMENT=production to disable testing mode.")
    logger.warning("=" * 70)


@dataclass
class TenantContext:
    """
    Multi-tenant context for the current request.

    Contains authenticated user info and firm context.
    """
    user_id: str
    email: str
    firm_id: Optional[str]
    role: Optional[str]
    permissions: Set[str]
    is_platform_admin: bool
    token_payload: TokenPayload

    @property
    def is_firm_admin(self) -> bool:
        """Check if user is a firm admin."""
        return self.role == UserRole.FIRM_ADMIN.value

    def has_permission(self, permission: Union[str, UserPermission]) -> bool:
        """Check if user has a specific permission."""
        perm_value = permission.value if isinstance(permission, UserPermission) else permission
        return perm_value in self.permissions

    def has_any_permission(self, permissions: List[Union[str, UserPermission]]) -> bool:
        """Check if user has any of the specified permissions."""
        for perm in permissions:
            if self.has_permission(perm):
                return True
        return False

    def has_all_permissions(self, permissions: List[Union[str, UserPermission]]) -> bool:
        """Check if user has all specified permissions."""
        for perm in permissions:
            if not self.has_permission(perm):
                return False
        return True


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> TenantContext:
    """
    FastAPI dependency to get current authenticated user.

    Extracts and validates JWT from Authorization header.

    Usage:
        @router.get("/protected")
        async def protected_route(user: TenantContext = Depends(get_current_user)):
            return {"user_id": user.user_id}
    """
    # Testing mode: return mock admin context
    if TESTING_MODE:
        mock_payload = TokenPayload(
            sub="test-admin-user",
            email="admin@test.local",
            type=TokenType.ACCESS,
            firm_id="test-firm-001",
            role=UserRole.FIRM_ADMIN.value,
            permissions=[p.value for p in UserPermission],  # All permissions
            is_platform_admin=True,
            exp=0,
            jti="test-token",
        )
        return TenantContext(
            user_id="test-admin-user",
            email="admin@test.local",
            firm_id="test-firm-001",
            role=UserRole.FIRM_ADMIN.value,
            permissions=set(p.value for p in UserPermission),  # All permissions
            is_platform_admin=True,
            token_payload=mock_payload,
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token = credentials.credentials
        payload = decode_token(token, verify_type=TokenType.ACCESS)

        return TenantContext(
            user_id=payload.sub,
            email=payload.email,
            firm_id=payload.firm_id,
            role=payload.role,
            permissions=set(payload.permissions or []),
            is_platform_admin=payload.is_platform_admin,
            token_payload=payload,
        )

    except Exception as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_firm(user: TenantContext = Depends(get_current_user)) -> str:
    """
    FastAPI dependency to get current firm ID.

    Raises 403 if user is not associated with a firm.

    Usage:
        @router.get("/firm-data")
        async def firm_data(firm_id: str = Depends(get_current_firm)):
            return {"firm_id": firm_id}
    """
    if not user.firm_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires firm context",
        )
    return user.firm_id


def require_permission(permission: Union[str, UserPermission]):
    """
    Decorator to require a specific permission.

    Usage:
        @router.post("/team/invite")
        @require_permission(UserPermission.INVITE_USERS)
        async def invite_user(user: TenantContext = Depends(get_current_user)):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find TenantContext in kwargs
            user = kwargs.get("user") or kwargs.get("current_user")
            if user is None:
                # Try to find it by type
                for v in kwargs.values():
                    if isinstance(v, TenantContext):
                        user = v
                        break

            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="User context not found. Ensure get_current_user dependency is used.",
                )

            # Platform admins bypass permission checks
            if user.is_platform_admin:
                return await func(*args, **kwargs)

            if not user.has_permission(permission):
                perm_name = permission.value if isinstance(permission, UserPermission) else permission
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {perm_name} required",
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(roles: Union[UserRole, List[UserRole]]):
    """
    Decorator to require specific role(s).

    Usage:
        @router.delete("/team/{user_id}")
        @require_role([UserRole.FIRM_ADMIN])
        async def delete_user(user_id: str, user: TenantContext = Depends(get_current_user)):
            ...
    """
    if isinstance(roles, UserRole):
        roles = [roles]

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get("user") or kwargs.get("current_user")
            if user is None:
                for v in kwargs.values():
                    if isinstance(v, TenantContext):
                        user = v
                        break

            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="User context not found",
                )

            # Platform admins bypass role checks
            if user.is_platform_admin:
                return await func(*args, **kwargs)

            if user.role not in [r.value for r in roles]:
                role_names = ", ".join([r.value for r in roles])
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role denied: One of [{role_names}] required",
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_firm_admin(func: Callable):
    """
    Decorator to require firm admin role.

    Shorthand for @require_role(UserRole.FIRM_ADMIN)

    Usage:
        @router.put("/settings")
        @require_firm_admin
        async def update_settings(user: TenantContext = Depends(get_current_user)):
            ...
    """
    return require_role(UserRole.FIRM_ADMIN)(func)


def require_platform_admin(func: Callable):
    """
    Decorator to require platform admin access.

    Usage:
        @router.get("/superadmin/firms")
        @require_platform_admin
        async def list_all_firms(user: TenantContext = Depends(get_current_user)):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        user = kwargs.get("user") or kwargs.get("current_user")
        if user is None:
            for v in kwargs.values():
                if isinstance(v, TenantContext):
                    user = v
                    break

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User context not found",
            )

        if not user.is_platform_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform admin access required",
            )

        return await func(*args, **kwargs)
    return wrapper


class PermissionChecker:
    """
    Dependency class for permission checking.

    Usage:
        @router.post("/clients")
        async def create_client(
            user: TenantContext = Depends(get_current_user),
            _: None = Depends(PermissionChecker(UserPermission.CREATE_CLIENT))
        ):
            ...
    """
    def __init__(self, permission: Union[str, UserPermission]):
        self.permission = permission

    async def __call__(self, user: TenantContext = Depends(get_current_user)) -> None:
        if user.is_platform_admin:
            return

        if not user.has_permission(self.permission):
            perm_name = self.permission.value if isinstance(self.permission, UserPermission) else self.permission
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {perm_name} required",
            )


class RoleChecker:
    """
    Dependency class for role checking.

    Usage:
        @router.get("/team")
        async def get_team(
            user: TenantContext = Depends(get_current_user),
            _: None = Depends(RoleChecker([UserRole.FIRM_ADMIN, UserRole.SENIOR_PREPARER]))
        ):
            ...
    """
    def __init__(self, roles: Union[UserRole, List[UserRole]]):
        self.roles = [roles] if isinstance(roles, UserRole) else roles

    async def __call__(self, user: TenantContext = Depends(get_current_user)) -> None:
        if user.is_platform_admin:
            return

        if user.role not in [r.value for r in self.roles]:
            role_names = ", ".join([r.value for r in self.roles])
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role denied: One of [{role_names}] required",
            )


def verify_firm_access(user: TenantContext, firm_id: str) -> bool:
    """
    Verify user has access to a specific firm.

    Platform admins have access to all firms.
    Firm users only have access to their own firm.
    """
    if user.is_platform_admin:
        return True
    return user.firm_id == firm_id


def verify_client_access(
    user: TenantContext,
    client_id: str,
    assigned_clients: List[str],
) -> bool:
    """
    Verify user has access to a specific client.

    Firm admins and senior preparers have access to all clients.
    Preparers only have access to assigned clients.
    """
    if user.is_platform_admin or user.is_firm_admin:
        return True

    if user.role in (UserRole.FIRM_ADMIN.value, UserRole.SENIOR_PREPARER.value):
        return True

    if user.role == UserRole.PREPARER.value:
        return client_id in assigned_clients

    # Reviewers have queue-based access (handled at service level)
    return False


# =============================================================================
# BACKWARD COMPATIBILITY - New RBAC System Integration
# =============================================================================

def get_unified_context(request: Request) -> TenantContext:
    """
    Get context from either legacy or new RBAC system.

    This is a transitional helper for gradual migration.
    """
    if RBAC_V2_ENABLED:
        try:
            from core.rbac.dependencies import RBACContext

            rbac_ctx = getattr(request.state, "rbac", None)
            if rbac_ctx and isinstance(rbac_ctx, RBACContext) and rbac_ctx.is_authenticated:
                # Convert to TenantContext for backward compatibility
                token_payload = TokenPayload(
                    sub=str(rbac_ctx.user_id) if rbac_ctx.user_id else "",
                    email=rbac_ctx.email or "",
                    type=TokenType.ACCESS,
                    firm_id=str(rbac_ctx.firm_id) if rbac_ctx.firm_id else None,
                    role=rbac_ctx.primary_role,
                    permissions=list(rbac_ctx.permissions),
                    is_platform_admin=rbac_ctx.is_platform_admin,
                    exp=rbac_ctx.token_exp,
                    jti=rbac_ctx.token_jti,
                )
                return TenantContext(
                    user_id=str(rbac_ctx.user_id) if rbac_ctx.user_id else "",
                    email=rbac_ctx.email or "",
                    firm_id=str(rbac_ctx.firm_id) if rbac_ctx.firm_id else None,
                    role=rbac_ctx.primary_role,
                    permissions=rbac_ctx.permissions,
                    is_platform_admin=rbac_ctx.is_platform_admin,
                    token_payload=token_payload,
                )
        except ImportError:
            logger.warning("core.rbac not available, using legacy RBAC")

    # Fall back to legacy behavior
    return None


# Alias for migration - new code should use this
def get_current_user_v2(request: Request) -> TenantContext:
    """
    Get current user with new RBAC system support.

    Tries new system first, falls back to legacy.
    Use this for new code that needs to work with both systems.
    """
    unified = get_unified_context(request)
    if unified:
        return unified

    # Delegate to original implementation
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Use get_current_user dependency instead",
    )


# =============================================================================
# MIGRATION HELPERS
# =============================================================================

def permission_to_code(permission: UserPermission) -> str:
    """Convert UserPermission enum to permission code string."""
    return permission.value


def role_to_code(role: UserRole) -> str:
    """Convert UserRole enum to role code string."""
    return role.value


# Map old permission names to new ones (if any changes)
PERMISSION_CODE_MAP = {
    # No changes currently, but allows for future migration
    # "old_permission": "new_permission",
}


def map_permission_code(code: str) -> str:
    """Map legacy permission code to new code."""
    return PERMISSION_CODE_MAP.get(code, code)
