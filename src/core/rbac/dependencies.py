"""
Core RBAC dependencies and request context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from rbac import AuthContext, Role, require_auth
from rbac.roles import ROLES, PLATFORM_ROLES


_TIER_RANK = {"starter": 0, "professional": 1, "enterprise": 2}
_PERMISSION_ALIAS_MAP = {
    "manage_custom_roles": {"team_manage", "platform_manage_admins"},
    "assign_roles": {"team_manage", "team_invite", "platform_manage_admins"},
    "view_team_performance": {"team_view", "firm_view_analytics", "platform_view_metrics"},
}


def _normalize_tier(value: Optional[str]) -> str:
    tier = (value or "").strip().lower()
    if tier in _TIER_RANK:
        return tier
    return "starter"


def _infer_subscription_tier(ctx: AuthContext, request: Optional[Request]) -> str:
    if request is not None:
        candidate = getattr(request.state, "subscription_tier", None)
        if candidate:
            return _normalize_tier(candidate)

    if ctx.role in PLATFORM_ROLES:
        return "enterprise"
    if ctx.role in {Role.PARTNER, Role.STAFF}:
        return "professional"
    return "starter"


@dataclass
class RBACContext:
    """RBAC context used by admin/core APIs."""

    user_id: Optional[UUID]
    email: str
    primary_role: str
    firm_id: Optional[UUID] = None
    permissions: set[str] = field(default_factory=set)
    subscription_tier: str = "starter"
    hierarchy_level: int = 2
    is_authenticated: bool = False

    @property
    def is_platform_admin(self) -> bool:
        return self.primary_role in {role.value for role in PLATFORM_ROLES}

    def require_authenticated(self) -> None:
        if not self.is_authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )


def _has_permission(ctx: RBACContext, permission_code: str) -> bool:
    if ctx.is_platform_admin:
        return True
    if permission_code in ctx.permissions:
        return True
    aliases = _PERMISSION_ALIAS_MAP.get(permission_code, set())
    return bool(aliases & ctx.permissions)


async def get_rbac_context(
    request: Request,
    auth_ctx: AuthContext = Depends(require_auth),
) -> RBACContext:
    """Build RBAC context from authenticated request."""
    role = auth_ctx.role if isinstance(auth_ctx.role, Role) else Role(str(auth_ctx.role))
    permission_codes = {
        permission.value if hasattr(permission, "value") else str(permission)
        for permission in getattr(auth_ctx, "permissions", set())
    }

    ctx = RBACContext(
        user_id=auth_ctx.user_id,
        email=auth_ctx.email,
        primary_role=role.value,
        firm_id=auth_ctx.firm_id,
        permissions=permission_codes,
        subscription_tier=_infer_subscription_tier(auth_ctx, request),
        hierarchy_level=ROLES.get(role).level.value if role in ROLES else 2,
        is_authenticated=bool(auth_ctx.is_authenticated),
    )
    request.state.rbac = ctx
    return ctx


async def require_platform_admin(
    ctx: RBACContext = Depends(get_rbac_context),
) -> RBACContext:
    """Require platform admin access."""
    ctx.require_authenticated()
    if not ctx.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return ctx


async def require_firm_admin(
    ctx: RBACContext = Depends(get_rbac_context),
) -> RBACContext:
    """Require firm admin/partner access."""
    ctx.require_authenticated()
    if ctx.primary_role != Role.PARTNER.value and not ctx.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firm admin access required",
        )
    return ctx


def require_permissions(permission_codes: Iterable[str]):
    """Require all specified permissions."""
    required = set(permission_codes)

    async def dependency(ctx: RBACContext = Depends(get_rbac_context)) -> RBACContext:
        missing = [code for code in required if not _has_permission(ctx, code)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(sorted(missing))}",
            )
        return ctx

    return dependency


def require_any_permission(permission_codes: Iterable[str]):
    """Require at least one permission."""
    required = set(permission_codes)

    async def dependency(ctx: RBACContext = Depends(get_rbac_context)) -> RBACContext:
        if not any(_has_permission(ctx, code) for code in required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(sorted(required))}",
            )
        return ctx

    return dependency


class RequirePermission:
    """Class-based dependency for a single permission."""

    def __init__(self, permission_code: str):
        self.permission_code = permission_code

    async def __call__(self, ctx: RBACContext = Depends(get_rbac_context)) -> None:
        if not _has_permission(ctx, self.permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required permission: {self.permission_code}",
            )


class RequireSubscriptionTier:
    """Class-based dependency to enforce minimum subscription tier."""

    def __init__(self, minimum_tier: str):
        self.minimum_tier = _normalize_tier(minimum_tier)

    async def __call__(self, ctx: RBACContext = Depends(get_rbac_context)) -> None:
        required_rank = _TIER_RANK.get(self.minimum_tier, 0)
        actual_rank = _TIER_RANK.get(_normalize_tier(ctx.subscription_tier), 0)
        if actual_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {self.minimum_tier} tier",
            )

