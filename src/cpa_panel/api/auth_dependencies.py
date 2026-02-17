"""
Shared authentication dependencies for CPA panel routes.

Keeping this in a standalone module avoids circular imports between
`router.py` and domain route modules that need per-endpoint auth guards.
"""

from typing import Optional, Any

from fastapi import Depends, HTTPException, status

from core.api.auth_routes import get_optional_user
from rbac.dependencies import optional_auth


def _normalize_auth_value(value: Any) -> str:
    """Normalize enum/string auth values into lowercase strings."""
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    return str(value).strip().lower()


def _is_allowed_core_principal(core_user: Any) -> bool:
    """
    Allow only internal CPA principals from unified core auth contexts.

    Internal: cpa_team, platform_admin
    Rejected: consumer, cpa_client
    """
    user_type = _normalize_auth_value(getattr(core_user, "user_type", None))
    if user_type in {"cpa_team", "platform_admin"}:
        return True
    if user_type:
        return False

    # Legacy fallback: if cpa_role exists, treat as internal CPA team principal.
    cpa_role = _normalize_auth_value(getattr(core_user, "cpa_role", None))
    return bool(cpa_role)


def _is_allowed_rbac_principal(rbac_ctx: Any) -> bool:
    """
    Allow only internal CPA/platform principals from RBAC contexts.

    Internal: firm_user, platform_admin, partner/staff/support/billing/super_admin roles
    Rejected: client, firm_client, direct_client
    """
    user_type = _normalize_auth_value(getattr(rbac_ctx, "user_type", None))
    if user_type in {"firm_user", "platform_admin"}:
        return True
    if user_type in {"client"}:
        return False

    role = _normalize_auth_value(getattr(rbac_ctx, "role", None))
    if role in {"partner", "staff", "super_admin", "platform_admin", "support", "billing"}:
        return True
    if role in {"firm_client", "direct_client"}:
        return False
    return False


async def require_internal_cpa_auth(
    core_user: Optional[Any] = Depends(get_optional_user),
    rbac_ctx: Optional[Any] = Depends(optional_auth),
) -> Any:
    """
    Require internal CPA/platform authentication for CPA panel internal routes.

    Accepts either:
    - Core auth context (cpa_team/platform_admin only), or
    - RBAC auth context (firm/platform roles only).
    """
    if core_user is not None and _is_allowed_core_principal(core_user):
        return core_user
    if rbac_ctx is not None and _is_allowed_rbac_principal(rbac_ctx):
        return rbac_ctx

    if core_user is not None or rbac_ctx is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CPA panel access requires internal CPA credentials",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


INTERNAL_ROUTE_DEPENDENCIES = [Depends(require_internal_cpa_auth)]
