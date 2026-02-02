"""
RBAC Decorators for FastAPI Endpoints

Provides decorators and dependencies for enforcing status-based permissions
on tax return operations.

Usage:
    @router.post("/returns/{return_id}/edit")
    @require_return_permission("edit")
    async def edit_return(return_id: str, ctx: AuthContext = Depends(require_auth)):
        ...
"""

from functools import wraps
from typing import Optional, Callable
from fastapi import HTTPException, Depends, status

from src.rbac.permissions import Role, Permission, has_permission
from src.rbac.status_permissions import (
    ReturnStatus,
    can_edit_return,
    can_approve_return,
    can_submit_for_review,
    can_revert_status,
    can_generate_filing_package,
    can_view_return
)
from src.database.session_persistence import get_session_persistence


# Import AuthContext from your auth module
# SECURITY: Fail-fast on missing auth module - DO NOT use silent fallback
import os
import logging

_rbac_logger = logging.getLogger(__name__)

# Try multiple import paths for auth module
_AUTH_AVAILABLE = False
try:
    from src.auth.auth_context import AuthContext, require_auth
    _AUTH_AVAILABLE = True
except ImportError:
    try:
        from security.auth_decorators import require_auth
        from typing import Any as AuthContext
        _AUTH_AVAILABLE = True
    except ImportError:
        pass

if not _AUTH_AVAILABLE:
    # CRITICAL: Auth module not available
    _env = os.environ.get("APP_ENVIRONMENT", "").lower().strip()
    _dev_envs = {"development", "dev", "local", "test", "testing"}

    if _env not in _dev_envs:
        # FAIL-FAST in production/unknown environments
        raise ImportError(
            "CRITICAL SECURITY ERROR: Authentication module not available. "
            "Cannot start application without auth in production. "
            "Ensure src.auth.auth_context or security.auth_decorators is installed."
        )
    else:
        # Only allow in explicit dev environments with loud warning
        _rbac_logger.critical(
            "[SECURITY] AUTH MODULE NOT FOUND - Using placeholder auth. "
            "This is ONLY acceptable in development!"
        )
        from typing import Any as AuthContext

        def require_auth():
            """
            DEVELOPMENT ONLY placeholder auth.
            In production, this would be a critical security failure.
            """
            _rbac_logger.warning(
                "[SECURITY] Using placeholder auth - NO ACTUAL AUTHENTICATION"
            )
            return None


def get_return_status(session_id: str) -> Optional[ReturnStatus]:
    """
    Get the current status of a return.

    Args:
        session_id: Session/return identifier

    Returns:
        ReturnStatus or None if not found
    """
    persistence = get_session_persistence()
    status_record = persistence.get_return_status(session_id)

    if not status_record:
        return None

    try:
        return ReturnStatus(status_record["status"])
    except (KeyError, ValueError):
        return None


def get_return_owner_id(session_id: str) -> Optional[str]:
    """
    Get the user ID of the return owner.

    Args:
        session_id: Session/return identifier

    Returns:
        User ID or None
    """
    persistence = get_session_persistence()
    session = persistence.load_unified_session(session_id)

    if not session:
        return None

    return session.user_id


def get_assigned_cpa_id(session_id: str) -> Optional[str]:
    """
    Get the CPA assigned to this return.

    Args:
        session_id: Session/return identifier

    Returns:
        CPA user ID or None
    """
    persistence = get_session_persistence()
    status_record = persistence.get_return_status(session_id)

    if not status_record:
        return None

    return status_record.get("cpa_reviewer_id")


def require_return_permission(action: str):
    """
    Decorator for FastAPI endpoints that require status-based return permissions.

    Args:
        action: Action type - 'view', 'edit', 'approve', 'submit', 'revert', 'generate_filing_package'
                (also accepts 'efile' for backward compatibility)

    Usage:
        @router.post("/returns/{session_id}/edit")
        @require_return_permission('edit')
        async def edit_return(
            session_id: str,
            ctx: AuthContext = Depends(require_auth),
            data: dict
        ):
            # If we get here, user has permission to edit
            ...

    Raises:
        HTTPException: 403 if permission denied, 404 if return not found
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract session_id from kwargs
            session_id = kwargs.get('session_id') or kwargs.get('return_id')
            if not session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing session_id or return_id parameter"
                )

            # Extract auth context
            ctx = kwargs.get('ctx')
            if not ctx:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Get return status
            return_status = get_return_status(session_id)
            if not return_status:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "ReturnNotFound",
                        "message": f"Return {session_id} not found or has no status"
                    }
                )

            # Get ownership info
            owner_id = get_return_owner_id(session_id)
            is_owner = owner_id == str(ctx.user_id) if owner_id else False

            assigned_cpa_id = get_assigned_cpa_id(session_id)
            is_assigned_cpa = assigned_cpa_id == str(ctx.user_id) if assigned_cpa_id else False

            # Check permission based on action
            allowed = False

            if action == 'view':
                allowed = can_view_return(
                    return_status,
                    ctx.role,
                    is_owner=is_owner,
                    is_assigned_cpa=is_assigned_cpa
                )

            elif action == 'edit':
                allowed = can_edit_return(
                    return_status,
                    ctx.role,
                    is_assigned_cpa=is_assigned_cpa,
                    is_owner=is_owner
                )

            elif action == 'approve':
                allowed = can_approve_return(
                    return_status,
                    ctx.role,
                    is_assigned_cpa=is_assigned_cpa
                )

            elif action == 'submit':
                allowed = can_submit_for_review(
                    return_status,
                    ctx.role,
                    is_owner=is_owner
                )

            elif action == 'revert':
                allowed = can_revert_status(
                    return_status,
                    ctx.role,
                    is_assigned_cpa=is_assigned_cpa
                )

            elif action in ('generate_filing_package', 'efile'):  # 'efile' for backward compatibility
                allowed = can_generate_filing_package(
                    return_status,
                    ctx.role,
                    is_assigned_cpa=is_assigned_cpa
                )

            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Unknown action type: {action}"
                )

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "PermissionDenied",
                        "message": f"Cannot {action} return in {return_status} status",
                        "status": return_status.value,
                        "action": action,
                        "user_role": ctx.role.value if hasattr(ctx.role, 'value') else str(ctx.role)
                    }
                )

            # Permission granted, call the function
            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def check_return_edit_permission(
    session_id: str,
    ctx: AuthContext
) -> bool:
    """
    Dependency function to check if user can edit a return.

    Use as FastAPI dependency:
        async def edit_return(
            session_id: str,
            can_edit: bool = Depends(check_return_edit_permission),
            ...
        ):

    Args:
        session_id: Return session ID
        ctx: Auth context

    Returns:
        True if allowed

    Raises:
        HTTPException if not allowed
    """
    return_status = get_return_status(session_id)
    if not return_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Return not found"
        )

    owner_id = get_return_owner_id(session_id)
    is_owner = owner_id == str(ctx.user_id) if owner_id else False

    assigned_cpa_id = get_assigned_cpa_id(session_id)
    is_assigned_cpa = assigned_cpa_id == str(ctx.user_id) if assigned_cpa_id else False

    if not can_edit_return(return_status, ctx.role, is_assigned_cpa, is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot edit return in {return_status} status"
        )

    return True


async def check_return_view_permission(
    session_id: str,
    ctx: AuthContext
) -> bool:
    """
    Dependency function to check if user can view a return.

    Args:
        session_id: Return session ID
        ctx: Auth context

    Returns:
        True if allowed

    Raises:
        HTTPException if not allowed
    """
    return_status = get_return_status(session_id)
    if not return_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Return not found"
        )

    owner_id = get_return_owner_id(session_id)
    is_owner = owner_id == str(ctx.user_id) if owner_id else False

    assigned_cpa_id = get_assigned_cpa_id(session_id)
    is_assigned_cpa = assigned_cpa_id == str(ctx.user_id) if assigned_cpa_id else False

    if not can_view_return(return_status, ctx.role, is_owner, is_assigned_cpa):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return True
