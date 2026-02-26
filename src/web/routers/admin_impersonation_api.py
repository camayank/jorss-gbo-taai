"""
Admin User Impersonation API.

Provides endpoints for platform admins to:
- Start impersonation sessions (act as another user)
- End impersonation sessions
- View active impersonation sessions
- Audit impersonation history

Security considerations:
- Only platform admins with PLATFORM_IMPERSONATE permission can impersonate
- All impersonation activity is logged for audit
- Sessions have automatic expiration
- Cannot impersonate other super admins
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import logging

from rbac.dependencies import require_auth, require_platform_admin, require_permission
from rbac.context import AuthContext
from rbac.permissions import Permission
from rbac.roles import Role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/impersonation",
    tags=["Admin Impersonation"],
    responses={403: {"description": "Insufficient permissions"}},
)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class ImpersonationStartRequest(BaseModel):
    """Request to start an impersonation session."""
    user_id: str = Field(..., description="ID of the user to impersonate")
    reason: str = Field(..., min_length=10, max_length=500, description="Reason for impersonation (audit requirement)")
    duration_minutes: int = Field(30, ge=5, le=120, description="Session duration (5-120 minutes)")


class ImpersonationEndRequest(BaseModel):
    """Request to end an impersonation session."""
    session_id: str = Field(..., description="ID of the impersonation session to end")


# =============================================================================
# IN-MEMORY STORAGE (Replace with database in production)
# =============================================================================


class ImpersonationSession:
    """An active or completed impersonation session."""

    def __init__(
        self,
        session_id: str,
        admin_id: str,
        admin_email: str,
        target_user_id: str,
        target_user_email: str,
        reason: str,
        duration_minutes: int,
    ):
        self.session_id = session_id
        self.admin_id = admin_id
        self.admin_email = admin_email
        self.target_user_id = target_user_id
        self.target_user_email = target_user_email
        self.reason = reason
        self.started_at = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.ended_at: Optional[datetime] = None
        self.actions_performed: List[str] = []

    @property
    def is_active(self) -> bool:
        """Check if session is still active."""
        if self.ended_at:
            return False
        return datetime.utcnow() < self.expires_at

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "session_id": self.session_id,
            "admin_id": self.admin_id,
            "admin_email": self.admin_email,
            "target_user_id": self.target_user_id,
            "target_user_email": self.target_user_email,
            "reason": self.reason,
            "started_at": self.started_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "is_active": self.is_active,
            "actions_count": len(self.actions_performed),
        }


# TODO: Migrate _sessions to Redis for distributed deployments.
# In-memory storage is acceptable for single-instance, but will not
# survive restarts or work across multiple workers/pods.
_sessions: dict[str, ImpersonationSession] = {}


async def _get_user_info(user_id: str) -> Optional[dict]:
    """Look up user from database."""
    try:
        from database.async_engine import get_async_session
        from sqlalchemy import text

        async for session in get_async_session():
            result = await session.execute(
                text("SELECT user_id, email, role, firm_id FROM users WHERE user_id = :uid"),
                {"uid": user_id},
            )
            row = result.fetchone()
            if not row:
                return None
            return {
                "user_id": str(row[0]),
                "email": str(row[1]),
                "role": str(row[2]),
                "firm_id": str(row[3]) if row[3] else None,
            }
    except Exception as e:
        logger.error(f"Failed to lookup user {user_id}: {e}")
        return None


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/start")
async def start_impersonation(
    data: ImpersonationStartRequest,
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Start an impersonation session.

    Requires PLATFORM_IMPERSONATE permission.

    Security rules:
    - Cannot impersonate super admins
    - Reason is required for audit trail
    - Session has automatic expiration
    """
    # Check permission
    if not ctx.has_permission(Permission.PLATFORM_IMPERSONATE):
        raise HTTPException(
            status_code=403,
            detail="PLATFORM_IMPERSONATE permission required"
        )

    # Look up target user
    target_user = await _get_user_info(data.user_id)
    if not target_user:
        raise HTTPException(
            status_code=404,
            detail="Target user not found"
        )

    # Cannot impersonate super admins
    if target_user.get("role") == "super_admin":
        logger.warning(
            f"Admin {ctx.user_id} attempted to impersonate super admin {data.user_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Cannot impersonate super admin users"
        )

    # Check for existing active session
    active_sessions = [
        s for s in _sessions.values()
        if s.admin_id == str(ctx.user_id) and s.is_active
    ]
    if active_sessions:
        raise HTTPException(
            status_code=400,
            detail="You already have an active impersonation session. End it first."
        )

    # Create session
    session = ImpersonationSession(
        session_id=str(uuid4()),
        admin_id=str(ctx.user_id),
        admin_email=ctx.email,
        target_user_id=data.user_id,
        target_user_email=target_user.get("email", "unknown"),
        reason=data.reason,
        duration_minutes=data.duration_minutes,
    )
    _sessions[session.session_id] = session

    # Log for audit
    logger.info(
        f"[AUDIT] Impersonation started | admin={ctx.email} | "
        f"target={target_user.get('email')} | reason={data.reason} | "
        f"session={session.session_id} | expires={session.expires_at.isoformat()}"
    )

    return {
        "session_id": session.session_id,
        "target_user": {
            "user_id": data.user_id,
            "email": target_user.get("email"),
        },
        "expires_at": session.expires_at.isoformat(),
        "message": "Impersonation session started. Remember to end session when done.",
    }


@router.post("/end")
async def end_impersonation(
    data: ImpersonationEndRequest,
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    End an impersonation session.

    Can only end your own sessions (unless super admin).
    """
    session = _sessions.get(data.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Only the admin who started it (or super admin) can end it
    if session.admin_id != str(ctx.user_id) and ctx.role != Role.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="You can only end your own impersonation sessions"
        )

    if session.ended_at:
        return {
            "message": "Session was already ended",
            "ended_at": session.ended_at.isoformat(),
        }

    session.ended_at = datetime.utcnow()

    # Log for audit
    logger.info(
        f"[AUDIT] Impersonation ended | admin={session.admin_email} | "
        f"target={session.target_user_email} | session={session.session_id} | "
        f"duration={(session.ended_at - session.started_at).total_seconds()}s | "
        f"actions={len(session.actions_performed)}"
    )

    return {
        "session_id": session.session_id,
        "ended_at": session.ended_at.isoformat(),
        "duration_seconds": (session.ended_at - session.started_at).total_seconds(),
        "message": "Impersonation session ended successfully",
    }


@router.get("/active")
async def list_active_sessions(
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    List all active impersonation sessions.

    Super admins see all sessions.
    Other admins see only their own sessions.
    """
    now = datetime.utcnow()

    if ctx.role == Role.SUPER_ADMIN:
        # Super admins see all active sessions
        active = [
            s.to_dict() for s in _sessions.values()
            if s.is_active
        ]
    else:
        # Other admins see only their sessions
        active = [
            s.to_dict() for s in _sessions.values()
            if s.is_active and s.admin_id == str(ctx.user_id)
        ]

    return {
        "sessions": active,
        "count": len(active),
    }


@router.get("/history")
async def get_impersonation_history(
    ctx: AuthContext = Depends(require_platform_admin),
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    limit: int = Query(50, le=200, description="Maximum results"),
):
    """
    Get impersonation session history for audit.

    Super admins see all history.
    Other admins see only their own history.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    if ctx.role == Role.SUPER_ADMIN:
        sessions = [
            s.to_dict() for s in _sessions.values()
            if s.started_at >= cutoff
        ]
    else:
        sessions = [
            s.to_dict() for s in _sessions.values()
            if s.started_at >= cutoff and s.admin_id == str(ctx.user_id)
        ]

    # Sort by started_at descending
    sessions.sort(key=lambda s: s["started_at"], reverse=True)

    return {
        "sessions": sessions[:limit],
        "total": len(sessions),
        "days_back": days,
    }


@router.get("/session/{session_id}")
async def get_session_details(
    session_id: str,
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Get detailed information about a specific impersonation session.

    Includes actions performed during the session.
    """
    session = _sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Only the admin who created it (or super admin) can view details
    if session.admin_id != str(ctx.user_id) and ctx.role != Role.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied to this session"
        )

    return {
        "session": session.to_dict(),
        "actions": session.actions_performed,
    }


@router.post("/session/{session_id}/log-action")
async def log_impersonation_action(
    session_id: str,
    action: str = Query(..., min_length=1, max_length=500, description="Action description"),
    ctx: AuthContext = Depends(require_platform_admin),
):
    """
    Log an action performed during an impersonation session.

    Used for audit trail - records what the admin did while impersonating.
    """
    session = _sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.admin_id != str(ctx.user_id):
        raise HTTPException(
            status_code=403,
            detail="Can only log actions for your own sessions"
        )

    if not session.is_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot log actions for inactive sessions"
        )

    action_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
    }
    session.actions_performed.append(action_entry)

    logger.info(
        f"[AUDIT] Impersonation action | session={session_id} | action={action}"
    )

    return {
        "logged": True,
        "action_count": len(session.actions_performed),
    }
