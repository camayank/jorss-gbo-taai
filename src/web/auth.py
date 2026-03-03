"""
Shared page-auth helpers for HTML page routes.

Provides require_page_auth / require_admin_page so that pages.py and
feature_pages.py can import a single implementation instead of duplicating.
"""

from fastapi import HTTPException, Request

try:
    from security.auth_decorators import get_user_from_request
except ImportError:
    get_user_from_request = lambda r: None

from web.constants import ADMIN_UI_ROLES


async def require_page_auth(request: Request) -> dict:
    """Require any authenticated user. Raises 401 -> login redirect via exception handler."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin_page(request: Request) -> dict:
    """Require admin role. Raises 401/403."""
    user = await require_page_auth(request)
    role = (user.get("role") or "").lower()
    if role not in ADMIN_UI_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
