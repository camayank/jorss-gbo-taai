"""
Impersonation Service

Handles firm/user impersonation for platform support.
Manages session lifecycle and audit logging.
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from .impersonation_models import (
    ImpersonationSession,
    ImpersonationAction,
    ImpersonationStatus,
    ImpersonationType,
    ImpersonationReason,
    DEFAULT_SESSION_DURATION,
    MAX_SESSION_DURATION,
)

logger = logging.getLogger(__name__)


class ImpersonationService:
    """
    Service for managing impersonation sessions.

    Provides:
    - Session creation and validation
    - JWT token generation for impersonation
    - Action logging during impersonation
    - Session lifecycle management
    - Audit trail
    """

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._sessions: Dict[UUID, ImpersonationSession] = {}
        self._sessions_by_token: Dict[str, UUID] = {}
        self._actions: Dict[UUID, List[ImpersonationAction]] = {}

    def start_firm_impersonation(
        self,
        admin_id: UUID,
        admin_email: str,
        admin_name: str,
        firm_id: UUID,
        firm_name: str,
        reason: ImpersonationReason,
        reason_detail: str = "",
        ticket_id: Optional[str] = None,
        duration_seconds: int = DEFAULT_SESSION_DURATION,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ImpersonationSession:
        """
        Start a firm impersonation session.

        Args:
            admin_id: Platform admin's user ID
            admin_email: Platform admin's email
            admin_name: Platform admin's display name
            firm_id: Target firm to impersonate
            firm_name: Target firm's name
            reason: Reason for impersonation
            reason_detail: Additional details
            ticket_id: Associated support ticket
            duration_seconds: Session duration
            ip_address: Admin's IP address
            user_agent: Admin's user agent

        Returns:
            ImpersonationSession with token

        Raises:
            ValueError: If admin already has active session for this firm
        """
        # Check for existing active session
        existing = self.get_active_session_for_admin(admin_id)
        if existing and existing.firm_id == firm_id:
            logger.warning(f"Admin {admin_email} already has active session for firm {firm_id}")
            return existing

        # End any other active sessions for this admin
        if existing:
            self.end_session(existing.id, admin_email, "Starting new impersonation")

        # Validate duration
        duration_seconds = min(duration_seconds, MAX_SESSION_DURATION)

        # Generate session token
        session_token = self._generate_session_token()

        # Create session
        session = ImpersonationSession(
            admin_id=admin_id,
            admin_email=admin_email,
            admin_name=admin_name,
            impersonation_type=ImpersonationType.FIRM,
            firm_id=firm_id,
            firm_name=firm_name,
            reason=reason,
            reason_detail=reason_detail,
            ticket_id=ticket_id,
            expires_at=datetime.utcnow() + timedelta(seconds=duration_seconds),
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Store session
        self._sessions[session.id] = session
        self._sessions_by_token[session_token] = session.id
        self._actions[session.id] = []

        logger.info(
            f"[IMPERSONATION] Started | admin={admin_email} | firm={firm_name} ({firm_id}) | "
            f"reason={reason.value} | ticket={ticket_id}"
        )

        return session

    def start_user_impersonation(
        self,
        admin_id: UUID,
        admin_email: str,
        admin_name: str,
        user_id: UUID,
        user_email: str,
        firm_id: UUID,
        firm_name: str,
        reason: ImpersonationReason,
        reason_detail: str = "",
        ticket_id: Optional[str] = None,
        duration_seconds: int = DEFAULT_SESSION_DURATION,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ImpersonationSession:
        """
        Start a user impersonation session.

        Similar to firm impersonation but targets a specific user.
        """
        # Check for existing active session
        existing = self.get_active_session_for_admin(admin_id)
        if existing and existing.user_id == user_id:
            return existing

        if existing:
            self.end_session(existing.id, admin_email, "Starting new impersonation")

        # Validate duration
        duration_seconds = min(duration_seconds, MAX_SESSION_DURATION)

        # Generate session token
        session_token = self._generate_session_token()

        # Create session
        session = ImpersonationSession(
            admin_id=admin_id,
            admin_email=admin_email,
            admin_name=admin_name,
            impersonation_type=ImpersonationType.USER,
            firm_id=firm_id,
            firm_name=firm_name,
            user_id=user_id,
            user_email=user_email,
            reason=reason,
            reason_detail=reason_detail,
            ticket_id=ticket_id,
            expires_at=datetime.utcnow() + timedelta(seconds=duration_seconds),
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Store session
        self._sessions[session.id] = session
        self._sessions_by_token[session_token] = session.id
        self._actions[session.id] = []

        logger.info(
            f"[IMPERSONATION] Started user impersonation | admin={admin_email} | "
            f"user={user_email} | firm={firm_name} | reason={reason.value}"
        )

        return session

    def get_session(self, session_id: UUID) -> Optional[ImpersonationSession]:
        """Get session by ID."""
        session = self._sessions.get(session_id)
        if session and session.status == ImpersonationStatus.ACTIVE and session.is_expired:
            session.status = ImpersonationStatus.EXPIRED
        return session

    def get_session_by_token(self, token: str) -> Optional[ImpersonationSession]:
        """Get session by token."""
        session_id = self._sessions_by_token.get(token)
        if session_id:
            return self.get_session(session_id)
        return None

    def validate_session(self, token: str) -> Optional[ImpersonationSession]:
        """
        Validate a session token.

        Returns the session if valid and active, None otherwise.
        """
        session = self.get_session_by_token(token)
        if session and session.is_active:
            return session
        return None

    def get_active_session_for_admin(self, admin_id: UUID) -> Optional[ImpersonationSession]:
        """Get active impersonation session for an admin."""
        for session in self._sessions.values():
            if session.admin_id == admin_id and session.is_active:
                return session
        return None

    def get_active_sessions(self) -> List[ImpersonationSession]:
        """Get all active impersonation sessions."""
        active = []
        for session in self._sessions.values():
            if session.status == ImpersonationStatus.ACTIVE:
                if session.is_expired:
                    session.status = ImpersonationStatus.EXPIRED
                else:
                    active.append(session)
        return active

    def get_sessions_for_firm(
        self,
        firm_id: UUID,
        include_ended: bool = False,
    ) -> List[ImpersonationSession]:
        """Get impersonation sessions for a firm."""
        sessions = []
        for session in self._sessions.values():
            if session.firm_id == firm_id:
                if include_ended or session.is_active:
                    sessions.append(session)
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def end_session(
        self,
        session_id: UUID,
        ended_by: str,
        reason: str = "Manual end",
    ) -> Optional[ImpersonationSession]:
        """
        End an impersonation session.

        Args:
            session_id: Session to end
            ended_by: Email of person ending the session
            reason: Reason for ending

        Returns:
            Updated session or None if not found
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        if session.status != ImpersonationStatus.ACTIVE:
            return session

        session.end_session(f"Ended by {ended_by}: {reason}")

        # Remove from token lookup
        if session.session_token in self._sessions_by_token:
            del self._sessions_by_token[session.session_token]

        logger.info(
            f"[IMPERSONATION] Ended | admin={session.admin_email} | firm={session.firm_name} | "
            f"duration={session.duration_seconds}s | actions={session.actions_count}"
        )

        return session

    def revoke_session(
        self,
        session_id: UUID,
        revoked_by: str,
    ) -> Optional[ImpersonationSession]:
        """
        Revoke an impersonation session (force end).

        Used by security or when detecting suspicious activity.
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        session.revoke(revoked_by)

        # Remove from token lookup
        if session.session_token in self._sessions_by_token:
            del self._sessions_by_token[session.session_token]

        logger.warning(
            f"[IMPERSONATION] REVOKED | admin={session.admin_email} | firm={session.firm_name} | "
            f"revoked_by={revoked_by}"
        )

        return session

    def extend_session(
        self,
        session_id: UUID,
        additional_seconds: int = DEFAULT_SESSION_DURATION,
    ) -> Optional[ImpersonationSession]:
        """
        Extend an active session.

        Cannot exceed MAX_SESSION_DURATION from original start.
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return None

        session.extend(additional_seconds)

        logger.info(
            f"[IMPERSONATION] Extended | admin={session.admin_email} | firm={session.firm_name} | "
            f"new_expiry={session.expires_at.isoformat()}"
        )

        return session

    def log_action(
        self,
        session_id: UUID,
        action_type: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        method: str = "GET",
        path: str = "",
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> Optional[ImpersonationAction]:
        """
        Log an action taken during impersonation.

        All actions during impersonation are logged for audit.
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        action = ImpersonationAction(
            session_id=session_id,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            method=method,
            path=path,
            success=success,
            error_message=error_message,
        )

        if session_id not in self._actions:
            self._actions[session_id] = []
        self._actions[session_id].append(action)

        session.record_action()

        return action

    def get_session_actions(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ImpersonationAction]:
        """Get actions for a session."""
        actions = self._actions.get(session_id, [])
        return sorted(actions, key=lambda a: a.created_at, reverse=True)[offset:offset + limit]

    def get_session_history(
        self,
        admin_id: Optional[UUID] = None,
        firm_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ImpersonationSession]:
        """
        Get impersonation session history.

        For audit and reporting purposes.
        """
        sessions = []
        for session in self._sessions.values():
            if admin_id and session.admin_id != admin_id:
                continue
            if firm_id and session.firm_id != firm_id:
                continue
            if start_date and session.created_at < start_date:
                continue
            if end_date and session.created_at > end_date:
                continue
            sessions.append(session)

        # Sort by created_at descending
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[offset:offset + limit]

    def get_session_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get summary statistics for impersonation sessions."""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        total = 0
        active = 0
        by_reason = {}
        by_admin = {}
        total_duration = 0
        total_actions = 0

        for session in self._sessions.values():
            if session.created_at < start_date or session.created_at > end_date:
                continue

            total += 1
            if session.is_active:
                active += 1

            reason = session.reason.value
            by_reason[reason] = by_reason.get(reason, 0) + 1

            admin = session.admin_email
            by_admin[admin] = by_admin.get(admin, 0) + 1

            total_duration += session.duration_seconds
            total_actions += session.actions_count

        return {
            "total_sessions": total,
            "active_sessions": active,
            "by_reason": by_reason,
            "by_admin": by_admin,
            "avg_duration_seconds": total_duration // total if total > 0 else 0,
            "total_actions": total_actions,
            "avg_actions_per_session": total_actions // total if total > 0 else 0,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
        }

    def _generate_session_token(self) -> str:
        """Generate a secure session token."""
        return f"imp_{secrets.token_urlsafe(32)}"

    def cleanup_expired(self) -> int:
        """
        Cleanup expired sessions.

        Returns number of sessions cleaned up.
        """
        count = 0
        for session in list(self._sessions.values()):
            if session.status == ImpersonationStatus.ACTIVE and session.is_expired:
                session.status = ImpersonationStatus.EXPIRED
                if session.session_token in self._sessions_by_token:
                    del self._sessions_by_token[session.session_token]
                count += 1
        return count


# Singleton instance
impersonation_service = ImpersonationService()
