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

import logging
from typing import Any, Callable, Optional, Set, Union
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from .roles import Role, PLATFORM_ROLES
from .permissions import Permission
from .context import AuthContext, UserType

logger = logging.getLogger(__name__)


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
            # Client - All clients are CPA's clients (B2B only platform)
            # NOTE: is_direct is deprecated - all clients treated the same
            # Kept for backward compatibility with existing tokens
            is_direct = payload.get("role") == Role.DIRECT_CLIENT.value
            ctx = AuthContext.for_client(
                user_id=UUID(payload["sub"]),
                email=payload["email"],
                name=payload.get("name", ""),
                is_direct=is_direct,  # Deprecated: treated identically to firm_client
                firm_id=UUID(payload["firm_id"]) if payload.get("firm_id") else None,
                firm_name=payload.get("firm_name", ""),
                token_id=payload.get("jti"),
                token_exp=payload.get("exp"),
            )

        # Store in request state for reuse
        request.state.auth_context = ctx
        return ctx

    except jwt.ExpiredSignatureError:
        # Token expired - this is expected, return anonymous
        return AuthContext.anonymous()
    except jwt.InvalidTokenError as e:
        # Invalid token format/signature - log for monitoring
        logger.debug(f"Invalid JWT token: {e}")
        return AuthContext.anonymous()
    except (ValueError, KeyError, TypeError) as e:
        # Malformed token payload - log for debugging
        logger.debug(f"Malformed token payload: {e}")
        return AuthContext.anonymous()
    except (AttributeError, UnicodeDecodeError) as e:
        # Structural token issues not covered above
        logger.warning(f"Unexpected token structure error in auth context: {type(e).__name__}: {e}")
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


async def optional_auth(
    ctx: AuthContext = Depends(get_auth_context),
) -> Optional[AuthContext]:
    """
    Return authenticated context when available, otherwise None.

    Use this for endpoints that support both anonymous and authenticated access.
    """
    if not ctx.is_authenticated:
        return None
    return ctx


def _extract_auth_context_from_call(args: tuple, kwargs: dict) -> Optional[AuthContext]:
    """Extract AuthContext from decorator-invoked endpoint arguments."""
    for value in kwargs.values():
        if isinstance(value, AuthContext):
            return value
    for value in args:
        if isinstance(value, AuthContext):
            return value
    return None


def _require_decorator_auth_context(args: tuple, kwargs: dict) -> AuthContext:
    """Require an authenticated AuthContext for decorator-based checks."""
    ctx = _extract_auth_context_from_call(args, kwargs)
    if not ctx or not ctx.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx


def _role_to_value(role_like: Union[Role, str, Any]) -> str:
    """Normalize role-like value to comparable role string."""
    raw = role_like.value if hasattr(role_like, "value") else str(role_like)
    return raw


def _coerce_permission(permission_like: Union[Permission, str, Any]) -> Permission:
    """Normalize permission-like values to Permission enum. Raises ValueError if invalid."""
    if isinstance(permission_like, Permission):
        return permission_like

    raw = permission_like.value if hasattr(permission_like, "value") else str(permission_like)
    try:
        return Permission(raw)
    except (TypeError, ValueError):
        logger.error(f"Invalid permission value: {raw!r} — not in Permission enum")
        raise ValueError(f"Invalid permission: {raw!r}")


def _permission_to_value(permission_like: Union[Permission, str]) -> str:
    """Normalize permission to comparable string value."""
    if isinstance(permission_like, Permission):
        return permission_like.value
    return str(permission_like)


# =============================================================================
# ROLE-BASED DEPENDENCIES
# =============================================================================

def require_role(role: Union[Role, Set[Role]]) -> Callable:
    """
    Require a specific role (or any of a set of roles).

    Can be used as a decorator OR as a dependency:

    Usage as decorator (no-op):
        @router.get("/admin")
        @require_role(Role.SUPER_ADMIN)
        async def admin_only(...):
            ...

    Usage as dependency:
        @router.get("/admin")
        async def admin_only(ctx: AuthContext = Depends(require_role(Role.SUPER_ADMIN))):
            ...
    """
    import functools
    import inspect

    if isinstance(role, (set, frozenset, list, tuple)):
        roles = set(role)
    else:
        roles = {role}
    required_role_values = {_role_to_value(r) for r in roles}

    async def dependency(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if _role_to_value(ctx.role) not in required_role_values:
            role_names = ", ".join(sorted(required_role_values))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {role_names}",
            )
        return ctx

    def decorator_or_dependency(func_or_ctx=None):
        """
        When used as @require_role(role), this enforces role checks at runtime.
        When used as Depends(require_role(role)), this returns the dependency.
        """
        if func_or_ctx is not None and callable(func_or_ctx) and hasattr(func_or_ctx, "__name__"):
            if inspect.iscoroutinefunction(func_or_ctx):
                @functools.wraps(func_or_ctx)
                async def async_wrapper(*args, **kwargs):
                    ctx = _require_decorator_auth_context(args, kwargs)
                    if _role_to_value(ctx.role) not in required_role_values:
                        role_names = ", ".join(sorted(required_role_values))
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Required role: {role_names}",
                        )
                    return await func_or_ctx(*args, **kwargs)

                async_wrapper._required_roles = roles
                return async_wrapper

            @functools.wraps(func_or_ctx)
            def sync_wrapper(*args, **kwargs):
                ctx = _require_decorator_auth_context(args, kwargs)
                if _role_to_value(ctx.role) not in required_role_values:
                    role_names = ", ".join(sorted(required_role_values))
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Required role: {role_names}",
                    )
                return func_or_ctx(*args, **kwargs)

            sync_wrapper._required_roles = roles
            return sync_wrapper

        return dependency

    decorator_or_dependency.__signature__ = inspect.signature(dependency)
    return decorator_or_dependency


def _require_platform_admin_impl(ctx: AuthContext) -> AuthContext:
    """Implementation of platform admin check."""
    if ctx.role not in PLATFORM_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return ctx


def require_platform_admin(func_or_ctx=None):
    """
    Require any platform admin role.

    Can be used as a decorator:
        @router.get("/admin")
        @require_platform_admin
        async def admin_endpoint(...):

    Or as a dependency:
        async def endpoint(ctx: AuthContext = Depends(require_platform_admin)):
    """
    # If called as a decorator (func_or_ctx is the decorated function)
    if callable(func_or_ctx) and not isinstance(func_or_ctx, AuthContext):
        import functools
        import inspect

        if inspect.iscoroutinefunction(func_or_ctx):
            @functools.wraps(func_or_ctx)
            async def async_wrapper(*args, **kwargs):
                ctx = _require_decorator_auth_context(args, kwargs)
                _require_platform_admin_impl(ctx)
                return await func_or_ctx(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func_or_ctx)
        def sync_wrapper(*args, **kwargs):
            ctx = _require_decorator_auth_context(args, kwargs)
            _require_platform_admin_impl(ctx)
            return func_or_ctx(*args, **kwargs)

        return sync_wrapper

    # If called as a dependency (func_or_ctx is None or AuthContext)
    if func_or_ctx is None:
        # Being used as Depends(require_platform_admin)
        async def dependency(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
            return _require_platform_admin_impl(ctx)
        return dependency

    # func_or_ctx is an AuthContext (direct call)
    return _require_platform_admin_impl(func_or_ctx)


def _require_super_admin_impl(ctx: AuthContext) -> AuthContext:
    """Implementation of super admin check."""
    if ctx.role != Role.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return ctx


def require_super_admin(func_or_ctx=None):
    """
    Require super admin role.

    Can be used as a decorator or dependency.
    """
    if callable(func_or_ctx) and not isinstance(func_or_ctx, AuthContext):
        import functools
        import inspect

        if inspect.iscoroutinefunction(func_or_ctx):
            @functools.wraps(func_or_ctx)
            async def async_wrapper(*args, **kwargs):
                ctx = _require_decorator_auth_context(args, kwargs)
                _require_super_admin_impl(ctx)
                return await func_or_ctx(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func_or_ctx)
        def sync_wrapper(*args, **kwargs):
            ctx = _require_decorator_auth_context(args, kwargs)
            _require_super_admin_impl(ctx)
            return func_or_ctx(*args, **kwargs)

        return sync_wrapper

    if func_or_ctx is None:
        async def dependency(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
            return _require_super_admin_impl(ctx)
        return dependency

    return _require_super_admin_impl(func_or_ctx)


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

def require_permission(permission: Union[Permission, Set[Permission], str], require_all: bool = False) -> Callable:
    """
    Require a specific permission (or any/all of a set).

    Can be used as a decorator OR as a dependency:

    Usage as decorator (no-op decorator, permission info stored on function):
        @router.post("/clients")
        @require_permission(Permission.CLIENT_CREATE)
        async def create_client(...):
            ...

    Usage as dependency:
        @router.post("/clients")
        async def create_client(ctx: AuthContext = Depends(require_permission(Permission.CLIENT_CREATE))):
            ...
    """
    import functools
    import inspect

    if isinstance(permission, (str, Permission)) or hasattr(permission, "value"):
        permissions = {_coerce_permission(permission)}
    else:
        permissions = {_coerce_permission(p) for p in permission}

    required_permission_values = {_permission_to_value(p) for p in permissions}

    def _check_permissions(ctx: AuthContext) -> None:
        actual_permission_values = {_permission_to_value(p) for p in ctx.permissions}

        if require_all:
            missing_values = sorted(required_permission_values - actual_permission_values)
            if missing_values:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing permissions: {', '.join(missing_values)}",
                )
            return

        if not (actual_permission_values & required_permission_values):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required permission: {', '.join(sorted(required_permission_values))}",
            )

    async def dependency(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        _check_permissions(ctx)
        return ctx

    def decorator_or_dependency(func_or_none=None):
        """
        When used as @require_permission(perm), this enforces permission checks.
        When used as Depends(require_permission(perm)), this returns the dependency.
        """
        if func_or_none is not None and callable(func_or_none):
            if inspect.iscoroutinefunction(func_or_none):
                @functools.wraps(func_or_none)
                async def async_wrapper(*args, **kwargs):
                    ctx = _require_decorator_auth_context(args, kwargs)
                    _check_permissions(ctx)
                    return await func_or_none(*args, **kwargs)

                async_wrapper._required_permissions = permissions
                return async_wrapper

            @functools.wraps(func_or_none)
            def sync_wrapper(*args, **kwargs):
                ctx = _require_decorator_auth_context(args, kwargs)
                _check_permissions(ctx)
                return func_or_none(*args, **kwargs)

            sync_wrapper._required_permissions = permissions
            return sync_wrapper

        return dependency

    decorator_or_dependency.__signature__ = inspect.signature(dependency)
    return decorator_or_dependency


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


async def get_current_firm(ctx: AuthContext = Depends(require_auth)) -> str:
    """
    Get the current firm ID as string.

    Raises 403 if user is not associated with a firm.
    Backward compatibility alias for get_current_firm_id.
    """
    if not ctx.firm_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firm context required",
        )
    return str(ctx.firm_id)


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
