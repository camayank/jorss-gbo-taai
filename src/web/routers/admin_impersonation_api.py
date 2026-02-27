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
# SESSION MODEL + REDIS-BACKED STORAGE
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
        """Convert to dictionary for API responses and Redis storage."""
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
            "actions_performed": self.actions_performed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ImpersonationSession":
        """Reconstruct from dictionary (Redis deserialization)."""
        session = cls.__new__(cls)
        session.session_id = data["session_id"]
        session.admin_id = data["admin_id"]
        session.admin_email = data["admin_email"]
        session.target_user_id = data["target_user_id"]
        session.target_user_email = data["target_user_email"]
        session.reason = data["reason"]
        session.started_at = datetime.fromisoformat(data["started_at"])
        session.expires_at = datetime.fromisoformat(data["expires_at"])
        session.ended_at = datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None
        session.actions_performed = data.get("actions_performed", [])
        return session


# In-memory cache (populated from Redis, serves as fallback)
_sessions: dict[str, ImpersonationSession] = {}

# Redis key constants
_IMPERSONATION_PREFIX = "impersonation:session:"
_IMPERSONATION_INDEX = "impersonation:sessions"


async def _get_redis():
    """Get Redis client, returns None if unavailable."""
    try:
        from cache.redis_client import get_redis_client
        client = await get_redis_client()
        if client and await client.ping():
            return client
    except Exception:
        pass
    return None


async def _store_session(session: ImpersonationSession) -> None:
    """Store impersonation session in Redis with in-memory cache."""
    _sessions[session.session_id] = session
    redis = await _get_redis()
    if redis:
        try:
            key = f"{_IMPERSONATION_PREFIX}{session.session_id}"
            # Keep in Redis for 90 days (audit history) or until expiry + 24h buffer
            ttl = max(
                int((session.expires_at - datetime.utcnow()).total_seconds()) + 86400,
                90 * 86400,
            )
            await redis.set(key, session.to_dict(), ttl=ttl)
            await redis._client.sadd(_IMPERSONATION_INDEX, session.session_id)
            await redis._client.expire(_IMPERSONATION_INDEX, 90 * 86400)
        except Exception as e:
            logger.warning(f"Failed to store impersonation session in Redis: {e}")


async def _load_session(session_id: str) -> Optional[ImpersonationSession]:
    """Load impersonation session from in-memory cache or Redis."""
    if session_id in _sessions:
        return _sessions[session_id]
    redis = await _get_redis()
    if redis:
        try:
            key = f"{_IMPERSONATION_PREFIX}{session_id}"
            data = await redis.get(key)
            if data and isinstance(data, dict):
                session = ImpersonationSession.from_dict(data)
                _sessions[session_id] = session
                return session
        except Exception as e:
            logger.warning(f"Failed to load impersonation session from Redis: {e}")
    return None


async def _sync_all_sessions() -> list[ImpersonationSession]:
    """Sync all sessions from Redis into in-memory cache and return them."""
    redis = await _get_redis()
    if redis:
        try:
            session_ids = await redis._client.smembers(_IMPERSONATION_INDEX)
            if session_ids:
                for sid in session_ids:
                    if sid not in _sessions:
                        key = f"{_IMPERSONATION_PREFIX}{sid}"
                        data = await redis.get(key)
                        if data and isinstance(data, dict):
                            _sessions[sid] = ImpersonationSession.from_dict(data)
                        else:
                            await redis._client.srem(_IMPERSONATION_INDEX, sid)
        except Exception as e:
            logger.warning(f"Failed to sync impersonation sessions from Redis: {e}")
    return list(_sessions.values())


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
    all_sessions = await _sync_all_sessions()
    active_sessions = [
        s for s in all_sessions
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
    await _store_session(session)

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
    session = await _load_session(data.session_id)

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
    await _store_session(session)

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
    all_sessions = await _sync_all_sessions()

    if ctx.role == Role.SUPER_ADMIN:
        active = [
            s.to_dict() for s in all_sessions
            if s.is_active
        ]
    else:
        active = [
            s.to_dict() for s in all_sessions
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
    all_sessions = await _sync_all_sessions()

    if ctx.role == Role.SUPER_ADMIN:
        sessions = [
            s.to_dict() for s in all_sessions
            if s.started_at >= cutoff
        ]
    else:
        sessions = [
            s.to_dict() for s in all_sessions
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
    session = await _load_session(session_id)

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
    session = await _load_session(session_id)

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
    await _store_session(session)

    logger.info(
        f"[AUDIT] Impersonation action | session={session_id} | action={action}"
    )

    return {
        "logged": True,
        "action_count": len(session.actions_performed),
    }
