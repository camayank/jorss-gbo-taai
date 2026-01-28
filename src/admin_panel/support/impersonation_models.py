"""
Impersonation Models

Data models for firm impersonation (support mode) functionality.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
from uuid import UUID, uuid4


class ImpersonationStatus(str, Enum):
    """Status of an impersonation session."""
    ACTIVE = "active"
    EXPIRED = "expired"
    ENDED = "ended"
    REVOKED = "revoked"


class ImpersonationType(str, Enum):
    """Type of impersonation."""
    FIRM = "firm"
    USER = "user"


class ImpersonationReason(str, Enum):
    """Standard reasons for impersonation."""
    SUPPORT_REQUEST = "support_request"
    BUG_INVESTIGATION = "bug_investigation"
    FEATURE_DEMO = "feature_demo"
    CONFIGURATION_HELP = "configuration_help"
    BILLING_ISSUE = "billing_issue"
    SECURITY_AUDIT = "security_audit"
    OTHER = "other"


# Default session duration in seconds (30 minutes)
DEFAULT_SESSION_DURATION = 1800

# Maximum session duration in seconds (2 hours)
MAX_SESSION_DURATION = 7200


@dataclass
class ImpersonationSession:
    """
    Represents an active impersonation session.

    Tracks when platform admins access firms for support.
    All actions during impersonation are logged.
    """
    id: UUID = field(default_factory=uuid4)

    # Admin who initiated the impersonation
    admin_id: UUID = None
    admin_email: str = ""
    admin_name: str = ""

    # Target of impersonation
    impersonation_type: ImpersonationType = ImpersonationType.FIRM
    firm_id: Optional[UUID] = None
    firm_name: str = ""
    user_id: Optional[UUID] = None  # For user impersonation
    user_email: Optional[str] = None

    # Reason and notes
    reason: ImpersonationReason = ImpersonationReason.SUPPORT_REQUEST
    reason_detail: str = ""
    ticket_id: Optional[str] = None  # Link to support ticket

    # Session timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = None
    ended_at: Optional[datetime] = None

    # Status
    status: ImpersonationStatus = ImpersonationStatus.ACTIVE

    # Session token (JWT reference)
    session_token: str = ""

    # Activity tracking
    actions_count: int = 0
    last_action_at: Optional[datetime] = None

    # Audit
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def __post_init__(self):
        """Set default expiration if not provided."""
        if self.expires_at is None:
            self.expires_at = datetime.utcnow() + timedelta(seconds=DEFAULT_SESSION_DURATION)

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_active(self) -> bool:
        """Check if session is currently active."""
        return self.status == ImpersonationStatus.ACTIVE and not self.is_expired

    @property
    def remaining_seconds(self) -> int:
        """Get remaining seconds until expiration."""
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))

    @property
    def duration_seconds(self) -> int:
        """Get total session duration in seconds."""
        end = self.ended_at or datetime.utcnow()
        return int((end - self.created_at).total_seconds())

    def end_session(self, reason: str = "Manual end"):
        """End the impersonation session."""
        self.status = ImpersonationStatus.ENDED
        self.ended_at = datetime.utcnow()
        self.reason_detail = f"{self.reason_detail} | Ended: {reason}"

    def revoke(self, revoked_by: str = "System"):
        """Revoke the session (force end)."""
        self.status = ImpersonationStatus.REVOKED
        self.ended_at = datetime.utcnow()
        self.reason_detail = f"{self.reason_detail} | Revoked by: {revoked_by}"

    def record_action(self):
        """Record an action during impersonation."""
        self.actions_count += 1
        self.last_action_at = datetime.utcnow()

    def extend(self, additional_seconds: int = DEFAULT_SESSION_DURATION):
        """Extend the session duration."""
        new_expiry = self.expires_at + timedelta(seconds=additional_seconds)
        max_allowed = self.created_at + timedelta(seconds=MAX_SESSION_DURATION)
        self.expires_at = min(new_expiry, max_allowed)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "admin_id": str(self.admin_id) if self.admin_id else None,
            "admin_email": self.admin_email,
            "admin_name": self.admin_name,
            "impersonation_type": self.impersonation_type.value,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "firm_name": self.firm_name,
            "user_id": str(self.user_id) if self.user_id else None,
            "user_email": self.user_email,
            "reason": self.reason.value,
            "reason_detail": self.reason_detail,
            "ticket_id": self.ticket_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status.value,
            "is_active": self.is_active,
            "remaining_seconds": self.remaining_seconds,
            "duration_seconds": self.duration_seconds,
            "actions_count": self.actions_count,
            "last_action_at": self.last_action_at.isoformat() if self.last_action_at else None,
            "ip_address": self.ip_address,
        }

    def to_audit_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "session_id": str(self.id),
            "admin_id": str(self.admin_id) if self.admin_id else None,
            "admin_email": self.admin_email,
            "impersonation_type": self.impersonation_type.value,
            "firm_id": str(self.firm_id) if self.firm_id else None,
            "firm_name": self.firm_name,
            "user_id": str(self.user_id) if self.user_id else None,
            "reason": self.reason.value,
            "ticket_id": self.ticket_id,
            "status": self.status.value,
            "actions_count": self.actions_count,
            "duration_seconds": self.duration_seconds,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


@dataclass
class ImpersonationAction:
    """
    Represents an action taken during impersonation.

    All actions during impersonation are logged for audit.
    """
    id: UUID = field(default_factory=uuid4)
    session_id: UUID = None

    # Action details
    action_type: str = ""  # e.g., "view_return", "edit_client"
    resource_type: str = ""  # e.g., "tax_return", "client"
    resource_id: Optional[str] = None

    # Request info
    method: str = ""  # GET, POST, PUT, DELETE
    path: str = ""

    # Result
    success: bool = True
    error_message: Optional[str] = None

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id) if self.session_id else None,
            "action_type": self.action_type,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "method": self.method,
            "path": self.path,
            "success": self.success,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
        }
