"""
Core RBAC middleware (lightweight, compatibility-focused).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from rbac.jwt import decode_token_safe
from rbac.roles import ROLES, Role

from .dependencies import RBACContext


@dataclass
class RBACMiddlewareConfig:
    """Configuration for RBAC middleware."""

    public_paths: Set[str] = field(default_factory=set)
    public_path_prefixes: Set[str] = field(default_factory=set)
    rbac_v2_enabled: bool = True
    fallback_to_legacy: bool = True


def _build_context_from_token_payload(payload: dict) -> Optional[RBACContext]:
    role_raw = payload.get("role")
    if not role_raw:
        return None

    try:
        role = Role(role_raw)
    except ValueError:
        return None

    user_id = payload.get("sub")
    firm_id = payload.get("firm_id")
    permissions: set[str] = set()
    # Token may include explicit permissions in some auth paths.
    token_permissions = payload.get("permissions") or []
    permissions.update(str(p) for p in token_permissions)

    # Infer defaults by role when explicit permissions absent.
    if not permissions:
        from rbac.permissions import ROLE_PERMISSIONS

        permissions = {p.value for p in ROLE_PERMISSIONS.get(role, frozenset())}

    if role in {Role.SUPER_ADMIN, Role.PLATFORM_ADMIN, Role.SUPPORT, Role.BILLING}:
        tier = "enterprise"
    elif role in {Role.PARTNER, Role.STAFF}:
        tier = "professional"
    else:
        tier = "starter"

    return RBACContext(
        user_id=UUID(str(user_id)) if user_id else None,
        email=payload.get("email", ""),
        primary_role=role.value,
        firm_id=UUID(str(firm_id)) if firm_id else None,
        permissions=permissions,
        subscription_tier=tier,
        hierarchy_level=ROLES[role].level.value if role in ROLES else 2,
        is_authenticated=bool(user_id),
    )


class RBACMiddleware(BaseHTTPMiddleware):
    """
    Attach RBAC context to request state.

    This middleware is intentionally conservative:
    - It does not override route-level auth dependencies.
    - It only hard-fails unauthenticated requests when fallback_to_legacy=False.
    """

    def __init__(
        self,
        app,
        config: Optional[RBACMiddlewareConfig] = None,
        get_db_session=None,
        get_cache=None,
    ):
        super().__init__(app)
        self.config = config or RBACMiddlewareConfig()
        self.get_db_session = get_db_session
        self.get_cache = get_cache

    def _is_public_path(self, path: str) -> bool:
        if path in self.config.public_paths:
            return True
        return any(path.startswith(prefix) for prefix in self.config.public_path_prefixes)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self._is_public_path(path) or not self.config.rbac_v2_enabled:
            return await call_next(request)

        if hasattr(request.state, "rbac"):
            return await call_next(request)

        if hasattr(request.state, "auth_context"):
            auth = request.state.auth_context
            role_value = getattr(getattr(auth, "role", None), "value", None)
            permissions = {
                p.value if hasattr(p, "value") else str(p)
                for p in getattr(auth, "permissions", set())
            }
            request.state.rbac = RBACContext(
                user_id=getattr(auth, "user_id", None),
                email=getattr(auth, "email", ""),
                primary_role=role_value or "",
                firm_id=getattr(auth, "firm_id", None),
                permissions=permissions,
                subscription_tier=getattr(request.state, "subscription_tier", "starter"),
                hierarchy_level=ROLES.get(getattr(auth, "role", None)).level.value
                if getattr(auth, "role", None) in ROLES
                else 2,
                is_authenticated=bool(getattr(auth, "is_authenticated", False)),
            )
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            payload = decode_token_safe(auth_header[7:])
            if payload:
                ctx = _build_context_from_token_payload(payload)
                if ctx:
                    request.state.rbac = ctx
                    return await call_next(request)

        if self.config.fallback_to_legacy:
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
        )

