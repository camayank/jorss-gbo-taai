"""
RBAC FastAPI Dependencies - Dependency injection for authorization.

Provides:
- RBACContext dependency for routes
- Permission checker dependencies
- Role checker dependencies
- Backward-compatible aliases
"""

from functools import wraps
from typing import Optional, List, Set, Union, Callable, Any
from uuid import UUID
import logging

from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .middleware import RBACContextData
from .models import HierarchyLevel

logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY NOTE
# =============================================================================
# Authentication is ALWAYS enforced. There is no bypass mechanism.
#
# For testing, use proper dependency injection with test fixtures:
#
#   @pytest.fixture
#   def mock_rbac_context():
#       return RBACContext(
#           user_id=uuid4(),
#           email="test@example.com",
#           is_authenticated=True,
#           permissions={"read_clients", "write_clients"},
#           ...
#       )
#
#   async def test_endpoint(mock_rbac_context):
#       app.dependency_overrides[get_rbac_context] = lambda: mock_rbac_context
#       # run test
#       app.dependency_overrides.clear()
#
# =============================================================================

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


# =============================================================================
# RBAC CONTEXT - Primary Interface
# =============================================================================

class RBACContext(RBACContextData):
    """
    Extended RBAC context for use in routes.

    Inherits from RBACContextData and adds helper methods
    for common authorization patterns.
    """

    @classmethod
    def from_request(cls, request: Request) -> "RBACContext":
        """Create RBACContext from request state."""
        rbac_data = getattr(request.state, "rbac", None)
        if rbac_data is None:
            return cls()

        if isinstance(rbac_data, RBACContext):
            return rbac_data

        # Convert RBACContextData to RBACContext
        ctx = cls()
        for attr in [
            "user_id", "email", "firm_id", "partner_id",
            "roles", "primary_role", "hierarchy_level",
            "permissions", "is_authenticated", "is_platform_admin",
            "is_partner_admin", "is_firm_admin", "token_type",
            "token_jti", "token_exp", "subscription_tier",
            "feature_flags", "request_id", "request_start_time",
        ]:
            if hasattr(rbac_data, attr):
                setattr(ctx, attr, getattr(rbac_data, attr))

        return ctx

    def require_authenticated(self) -> None:
        """Raise 401 if not authenticated."""
        if not self.is_authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def require_permission(self, permission: str) -> None:
        """Raise 403 if permission not granted."""
        if not self.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )

    def require_any_permission(self, permissions: List[str]) -> None:
        """Raise 403 if none of the permissions are granted."""
        if not self.has_any_permission(permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: One of [{', '.join(permissions)}] required",
            )

    def require_all_permissions(self, permissions: List[str]) -> None:
        """Raise 403 if any permission is not granted."""
        if not self.has_all_permissions(permissions):
            missing = [p for p in permissions if p not in self.permissions]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: Missing [{', '.join(missing)}]",
            )

    def require_role(self, role: str) -> None:
        """Raise 403 if role not assigned."""
        if not self.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role denied: {role} required",
            )

    def require_any_role(self, roles: List[str]) -> None:
        """Raise 403 if none of the roles are assigned."""
        if not self.has_any_role(roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role denied: One of [{', '.join(roles)}] required",
            )

    def require_hierarchy_level(self, max_level: int) -> None:
        """Raise 403 if hierarchy level is below required."""
        if self.hierarchy_level > max_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privilege level",
            )

    def require_firm_access(self, firm_id: UUID) -> None:
        """Raise 403 if user cannot access firm."""
        if not self.can_access_firm(firm_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this firm",
            )


# =============================================================================
# DEPENDENCY FUNCTIONS
# =============================================================================

async def get_rbac_context(request: Request) -> RBACContext:
    """
    FastAPI dependency to get RBAC context.

    Usage:
        @router.get("/protected")
        async def protected_route(ctx: RBACContext = Depends(get_rbac_context)):
            return {"user_id": ctx.user_id}
    """
    return RBACContext.from_request(request)


async def get_authenticated_context(request: Request) -> RBACContext:
    """
    FastAPI dependency that requires authentication.

    Raises 401 if not authenticated.

    Usage:
        @router.get("/protected")
        async def protected_route(ctx: RBACContext = Depends(get_authenticated_context)):
            ...
    """
    ctx = RBACContext.from_request(request)
    ctx.require_authenticated()
    return ctx


async def get_firm_context(request: Request) -> RBACContext:
    """
    FastAPI dependency that requires firm context.

    Raises 401 if not authenticated, 403 if no firm association.

    Usage:
        @router.get("/firm-data")
        async def firm_data(ctx: RBACContext = Depends(get_firm_context)):
            firm_id = ctx.firm_id  # Guaranteed not None
    """
    ctx = RBACContext.from_request(request)
    ctx.require_authenticated()

    if not ctx.firm_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires firm context",
        )

    return ctx


# Alias for backward compatibility
require_firm_context = get_firm_context


# =============================================================================
# PERMISSION CHECKER CLASSES
# =============================================================================

class RequirePermission:
    """
    Dependency class for permission checking.

    Usage:
        @router.post("/clients")
        async def create_client(
            ctx: RBACContext = Depends(get_rbac_context),
            _: None = Depends(RequirePermission("create_client"))
        ):
            ...

    Or with multiple permissions (any):
        _: None = Depends(RequirePermission(["create_client", "manage_client"]))
    """

    def __init__(
        self,
        permission: Union[str, List[str]],
        require_all: bool = False,
    ):
        if isinstance(permission, str):
            self.permissions = [permission]
        else:
            self.permissions = permission
        self.require_all = require_all

    async def __call__(self, ctx: RBACContext = Depends(get_rbac_context)) -> None:
        ctx.require_authenticated()

        if self.require_all:
            ctx.require_all_permissions(self.permissions)
        else:
            if len(self.permissions) == 1:
                ctx.require_permission(self.permissions[0])
            else:
                ctx.require_any_permission(self.permissions)


class RequireRole:
    """
    Dependency class for role checking.

    Usage:
        @router.delete("/team/{user_id}")
        async def delete_user(
            user_id: str,
            ctx: RBACContext = Depends(get_rbac_context),
            _: None = Depends(RequireRole("firm_admin"))
        ):
            ...

    Or with multiple roles:
        _: None = Depends(RequireRole(["firm_admin", "senior_preparer"]))
    """

    def __init__(self, roles: Union[str, List[str]]):
        if isinstance(roles, str):
            self.roles = [roles]
        else:
            self.roles = roles

    async def __call__(self, ctx: RBACContext = Depends(get_rbac_context)) -> None:
        ctx.require_authenticated()

        if len(self.roles) == 1:
            ctx.require_role(self.roles[0])
        else:
            ctx.require_any_role(self.roles)


class RequireHierarchyLevel:
    """
    Dependency class for hierarchy level checking.

    Usage:
        @router.get("/platform/metrics")
        async def platform_metrics(
            ctx: RBACContext = Depends(get_rbac_context),
            _: None = Depends(RequireHierarchyLevel(HierarchyLevel.PLATFORM))
        ):
            ...
    """

    def __init__(self, max_level: Union[int, HierarchyLevel]):
        if isinstance(max_level, HierarchyLevel):
            self.max_level = max_level.value
        else:
            self.max_level = max_level

    async def __call__(self, ctx: RBACContext = Depends(get_rbac_context)) -> None:
        ctx.require_authenticated()
        ctx.require_hierarchy_level(self.max_level)


# =============================================================================
# CONVENIENCE DEPENDENCIES
# =============================================================================

async def require_platform_admin(ctx: RBACContext = Depends(get_rbac_context)) -> RBACContext:
    """
    Dependency that requires platform admin access.

    Usage:
        @router.get("/superadmin/firms")
        async def list_all_firms(ctx: RBACContext = Depends(require_platform_admin)):
            ...
    """
    ctx.require_authenticated()

    if not ctx.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )

    return ctx


async def require_partner_admin(ctx: RBACContext = Depends(get_rbac_context)) -> RBACContext:
    """
    Dependency that requires partner admin access.

    Usage:
        @router.get("/partner/firms")
        async def list_partner_firms(ctx: RBACContext = Depends(require_partner_admin)):
            ...
    """
    ctx.require_authenticated()

    if not ctx.is_partner_admin and not ctx.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Partner admin access required",
        )

    return ctx


async def require_firm_admin(ctx: RBACContext = Depends(get_firm_context)) -> RBACContext:
    """
    Dependency that requires firm admin access.

    Usage:
        @router.put("/settings")
        async def update_settings(ctx: RBACContext = Depends(require_firm_admin)):
            ...
    """
    if not ctx.is_firm_admin and not ctx.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firm admin access required",
        )

    return ctx


# =============================================================================
# DECORATOR FACTORIES
# =============================================================================

def require_permissions(*permissions: str, require_all: bool = False):
    """
    Decorator factory for permission checking.

    Usage:
        @router.post("/team/invite")
        @require_permissions("invite_users")
        async def invite_user(ctx: RBACContext = Depends(get_rbac_context)):
            ...

        @router.delete("/team/{user_id}")
        @require_permissions("manage_team", "invite_users", require_all=True)
        async def delete_user(ctx: RBACContext = Depends(get_rbac_context)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find RBACContext in kwargs
            ctx = None
            for v in kwargs.values():
                if isinstance(v, RBACContext):
                    ctx = v
                    break

            if ctx is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="RBAC context not found. Ensure get_rbac_context dependency is used.",
                )

            ctx.require_authenticated()

            if require_all:
                ctx.require_all_permissions(list(permissions))
            elif len(permissions) == 1:
                ctx.require_permission(permissions[0])
            else:
                ctx.require_any_permission(list(permissions))

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_permission(*permissions: str):
    """
    Decorator that requires any of the specified permissions.

    Usage:
        @router.get("/clients")
        @require_any_permission("view_client", "view_all_clients")
        async def list_clients(ctx: RBACContext = Depends(get_rbac_context)):
            ...
    """
    return require_permissions(*permissions, require_all=False)


def require_all_permissions(*permissions: str):
    """
    Decorator that requires all of the specified permissions.

    Usage:
        @router.delete("/clients/{id}")
        @require_all_permissions("manage_client", "archive_client")
        async def delete_client(ctx: RBACContext = Depends(get_rbac_context)):
            ...
    """
    return require_permissions(*permissions, require_all=True)


# =============================================================================
# BACKWARD COMPATIBILITY - Legacy TenantContext Support
# =============================================================================

def get_tenant_context_adapter(ctx: RBACContext = Depends(get_rbac_context)):
    """
    Adapter to support legacy TenantContext interface.

    Creates a TenantContext-compatible object from RBACContext.

    Usage (for legacy code migration):
        from core.rbac import get_tenant_context_adapter as get_current_user

        @router.get("/protected")
        async def protected_route(user: TenantContext = Depends(get_current_user)):
            ...
    """
    from admin_panel.auth.rbac import TenantContext
    from admin_panel.auth.jwt_handler import TokenPayload, TokenType

    # Create a minimal TokenPayload for compatibility
    token_payload = TokenPayload(
        sub=str(ctx.user_id) if ctx.user_id else "",
        email=ctx.email or "",
        type=TokenType.ACCESS,
        firm_id=str(ctx.firm_id) if ctx.firm_id else None,
        role=ctx.primary_role,
        permissions=list(ctx.permissions),
        is_platform_admin=ctx.is_platform_admin,
        exp=ctx.token_exp,
        jti=ctx.token_jti,
    )

    return TenantContext(
        user_id=str(ctx.user_id) if ctx.user_id else "",
        email=ctx.email or "",
        firm_id=str(ctx.firm_id) if ctx.firm_id else None,
        role=ctx.primary_role,
        permissions=ctx.permissions,
        is_platform_admin=ctx.is_platform_admin,
        token_payload=token_payload,
    )


# Alias for gradual migration
get_current_user = get_tenant_context_adapter


# =============================================================================
# FEATURE FLAG DEPENDENCIES
# =============================================================================

class RequireFeatureFlag:
    """
    Dependency class for feature flag checking.

    Usage:
        @router.get("/beta/feature")
        async def beta_feature(
            ctx: RBACContext = Depends(get_rbac_context),
            _: None = Depends(RequireFeatureFlag("beta_feature"))
        ):
            ...
    """

    def __init__(self, flag: str):
        self.flag = flag

    async def __call__(self, ctx: RBACContext = Depends(get_rbac_context)) -> None:
        if self.flag not in ctx.feature_flags:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature not available: {self.flag}",
            )


# =============================================================================
# SUBSCRIPTION TIER DEPENDENCIES
# =============================================================================

class RequireSubscriptionTier:
    """
    Dependency class for subscription tier checking.

    Usage:
        @router.post("/api/custom-roles")
        async def create_custom_role(
            ctx: RBACContext = Depends(get_rbac_context),
            _: None = Depends(RequireSubscriptionTier(["professional", "enterprise"]))
        ):
            ...
    """

    TIER_ORDER = ["starter", "professional", "enterprise"]

    def __init__(self, min_tier: Union[str, List[str]]):
        if isinstance(min_tier, str):
            self.allowed_tiers = self._tiers_at_or_above(min_tier)
        else:
            self.allowed_tiers = set(min_tier)

    def _tiers_at_or_above(self, tier: str) -> Set[str]:
        """Get all tiers at or above the specified tier."""
        try:
            idx = self.TIER_ORDER.index(tier)
            return set(self.TIER_ORDER[idx:])
        except ValueError:
            return {tier}

    async def __call__(self, ctx: RBACContext = Depends(get_firm_context)) -> None:
        if ctx.subscription_tier not in self.allowed_tiers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {', '.join(self.allowed_tiers)} tier",
            )
