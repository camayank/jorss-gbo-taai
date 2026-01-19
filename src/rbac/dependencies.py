"""
CA4CPA GLOBAL LLC - FastAPI Dependencies

Dependency injection helpers for route protection.

Usage:
    from rbac import require_auth, require_role, require_permission, Role, Permission

    # Require authentication
    @router.get("/profile")
    async def get_profile(ctx: AuthContext = Depends(require_auth)):
        return {"user": ctx.name}

    # Require specific role
    @router.get("/admin/dashboard")
    async def admin_dashboard(ctx: AuthContext = Depends(require_role(Role.PLATFORM_ADMIN))):
        return {"metrics": ...}

    # Require specific permission
    @router.post("/clients")
    async def create_client(ctx: AuthContext = Depends(require_permission(Permission.CLIENT_CREATE))):
        return {"client_id": ...}
"""

from typing import Optional, Set, Union, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .roles import Role, PLATFORM_ROLES
from .permissions import Permission
from .context import AuthContext, UserType


# =============================================================================
# HTTP BEARER SECURITY
# =============================================================================

security = HTTPBearer(auto_error=False)


# =============================================================================
# CORE DEPENDENCIES
# =============================================================================

async def get_auth_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AuthContext:
    """
    Get the authentication context for the current request.

    This is the base dependency that extracts user info from the JWT token.
    Does NOT enforce authentication - use require_auth for that.

    Returns:
        AuthContext: The authentication context (may be anonymous).
    """
    # Check if context is already in request state (from middleware)
    if hasattr(request.state, "auth_context"):
        return request.state.auth_context

    # No credentials = anonymous
    if credentials is None:
        return AuthContext.anonymous()

    # Parse JWT token and create context
    try:
        from .jwt import decode_token  # Import here to avoid circular imports

        token = credentials.credentials
        payload = decode_token(token)

        # Determine user type and create appropriate context
        user_type = UserType(payload.get("user_type", "client"))

        if user_type == UserType.PLATFORM_ADMIN:
            ctx = AuthContext.for_platform_admin(
                user_id=UUID(payload["sub"]),
                email=payload["email"],
                name=payload.get("name", ""),
                role=Role(payload["role"]),
                token_id=payload.get("jti"),
                token_exp=payload.get("exp"),
            )
        elif user_type == UserType.FIRM_USER:
            ctx = AuthContext.for_firm_user(
                user_id=UUID(payload["sub"]),
                email=payload["email"],
                name=payload.get("name", ""),
                role=Role(payload["role"]),
                firm_id=UUID(payload["firm_id"]) if payload.get("firm_id") else None,
                firm_name=payload.get("firm_name", ""),
                token_id=payload.get("jti"),
                token_exp=payload.get("exp"),
            )
        else:
            # Client
            is_direct = payload.get("role") == Role.DIRECT_CLIENT.value
            ctx = AuthContext.for_client(
                user_id=UUID(payload["sub"]),
                email=payload["email"],
                name=payload.get("name", ""),
                is_direct=is_direct,
                firm_id=UUID(payload["firm_id"]) if payload.get("firm_id") else None,
                firm_name=payload.get("firm_name", ""),
                token_id=payload.get("jti"),
                token_exp=payload.get("exp"),
            )

        # Store in request state for reuse
        request.state.auth_context = ctx
        return ctx

    except Exception:
        return AuthContext.anonymous()


async def require_auth(
    ctx: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """
    Require authentication.

    Raises 401 if not authenticated.

    Usage:
        @router.get("/profile")
        async def get_profile(ctx: AuthContext = Depends(require_auth)):
            return {"user": ctx.name}
    """
    if not ctx.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx


# =============================================================================
# ROLE-BASED DEPENDENCIES
# =============================================================================

def require_role(role: Union[Role, Set[Role]]) -> Callable:
    """
    Require a specific role (or any of a set of roles).

    Usage:
        @router.get("/admin")
        async def admin_only(ctx: AuthContext = Depends(require_role(Role.SUPER_ADMIN))):
            ...

        @router.get("/firm")
        async def firm_only(ctx: AuthContext = Depends(require_role({Role.PARTNER, Role.STAFF}))):
            ...
    """
    roles = {role} if isinstance(role, Role) else role

    async def dependency(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if ctx.role not in roles:
            role_names = ", ".join(r.value for r in roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {role_names}",
            )
        return ctx

    return dependency


def require_platform_admin(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
    """
    Require any platform admin role.

    Shortcut for require_role(PLATFORM_ROLES).
    """
    if ctx.role not in PLATFORM_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return ctx


def require_super_admin(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
    """
    Require super admin role.

    Strictest permission - only super_admin can access.
    """
    if ctx.role != Role.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return ctx


def require_firm_user(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
    """
    Require firm user (partner or staff).

    Also requires firm_id to be set.
    """
    if ctx.role not in {Role.PARTNER, Role.STAFF}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firm user access required",
        )
    if not ctx.firm_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firm context required",
        )
    return ctx


def require_partner(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
    """Require partner (CPA firm owner) role."""
    if ctx.role != Role.PARTNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Partner access required",
        )
    return ctx


# =============================================================================
# PERMISSION-BASED DEPENDENCIES
# =============================================================================

def require_permission(permission: Union[Permission, Set[Permission]], require_all: bool = False) -> Callable:
    """
    Require a specific permission (or any/all of a set).

    Usage:
        # Single permission
        @router.post("/clients")
        async def create_client(ctx: AuthContext = Depends(require_permission(Permission.CLIENT_CREATE))):
            ...

        # Any of multiple permissions
        @router.get("/clients")
        async def list_clients(ctx: AuthContext = Depends(require_permission(
            {Permission.CLIENT_VIEW_OWN, Permission.CLIENT_VIEW_ALL}
        ))):
            ...

        # All permissions required
        @router.delete("/clients/{id}")
        async def delete_client(ctx: AuthContext = Depends(require_permission(
            {Permission.CLIENT_EDIT, Permission.CLIENT_ARCHIVE},
            require_all=True
        ))):
            ...
    """
    permissions = {permission} if isinstance(permission, Permission) else permission

    async def dependency(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if require_all:
            if not ctx.has_all_permissions(permissions):
                missing = permissions - ctx.permissions
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permissions: {', '.join(p.value for p in missing)}",
                )
        else:
            if not ctx.has_any_permission(permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required permission: {', '.join(p.value for p in permissions)}",
                )
        return ctx

    return dependency


# =============================================================================
# FIRM ACCESS DEPENDENCIES
# =============================================================================

def require_firm_access(firm_id_param: str = "firm_id") -> Callable:
    """
    Require access to a specific firm.

    Platform admins can access any firm.
    Firm users can only access their own firm.

    Usage:
        @router.get("/firms/{firm_id}/clients")
        async def get_firm_clients(
            firm_id: UUID,
            ctx: AuthContext = Depends(require_firm_access("firm_id"))
        ):
            ...
    """
    async def dependency(
        request: Request,
        ctx: AuthContext = Depends(require_auth),
    ) -> AuthContext:
        # Get firm_id from path parameters
        firm_id = request.path_params.get(firm_id_param)
        if not firm_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing {firm_id_param} parameter",
            )

        # Platform admins can access any firm
        if ctx.is_platform:
            return ctx

        # Firm users can only access their own firm
        if ctx.firm_id and str(ctx.firm_id) == str(firm_id):
            return ctx

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this firm",
        )

    return dependency


# =============================================================================
# UTILITY DEPENDENCIES
# =============================================================================

async def get_current_firm_id(ctx: AuthContext = Depends(require_auth)) -> UUID:
    """
    Get the current firm ID.

    Raises 403 if user is not associated with a firm.
    """
    if not ctx.firm_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firm context required",
        )
    return ctx.firm_id


async def get_optional_firm_id(ctx: AuthContext = Depends(get_auth_context)) -> Optional[UUID]:
    """
    Get the current firm ID if available.

    Returns None if user is not associated with a firm (e.g., platform admin).
    """
    return ctx.firm_id


# =============================================================================
# DECORATOR HELPERS (for cleaner route definitions)
# =============================================================================

class PermissionChecker:
    """
    Dependency class for permission checking.

    Usage:
        @router.post("/clients")
        async def create_client(
            ctx: AuthContext = Depends(require_auth),
            _: None = Depends(PermissionChecker(Permission.CLIENT_CREATE))
        ):
            ...
    """
    def __init__(self, permission: Permission):
        self.permission = permission

    async def __call__(self, ctx: AuthContext = Depends(require_auth)) -> None:
        if not ctx.has_permission(self.permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.permission.value}",
            )


class RoleChecker:
    """
    Dependency class for role checking.

    Usage:
        @router.delete("/firms/{firm_id}")
        async def delete_firm(
            firm_id: UUID,
            ctx: AuthContext = Depends(require_auth),
            _: None = Depends(RoleChecker(Role.SUPER_ADMIN))
        ):
            ...
    """
    def __init__(self, role: Union[Role, Set[Role]]):
        self.roles = {role} if isinstance(role, Role) else role

    async def __call__(self, ctx: AuthContext = Depends(require_auth)) -> None:
        if ctx.role not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(r.value for r in self.roles)}",
            )
