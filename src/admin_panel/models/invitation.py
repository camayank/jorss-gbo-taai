"""
Invitation Model - Team member invitation management.

Handles email-based invitation flow for adding team members to a firm.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4
from enum import Enum as PyEnum
import secrets

from sqlalchemy import (
    Column, String, Boolean, DateTime,
    ForeignKey, Index, CheckConstraint, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.models import Base
from .user import UserRole


class InvitationStatus(str, PyEnum):
    """Status of an invitation."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


def generate_invitation_token() -> str:
    """Generate a secure invitation token."""
    return secrets.token_urlsafe(32)


class Invitation(Base):
    """
    Invitation - Pending team member invitation.

    Workflow:
    1. Firm admin creates invitation with email and role
    2. System sends email with invitation link
    3. Recipient clicks link, creates account
    4. Invitation marked as accepted, user linked to firm
    """
    __tablename__ = "invitations"

    # Primary Key
    invitation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key to Firm
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Invitation Details
    email = Column(String(255), nullable=False, index=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.PREPARER)

    # Token for verification
    token = Column(String(64), unique=True, nullable=False, default=generate_invitation_token)

    # Expiration (default: 7 days)
    expires_at = Column(DateTime, nullable=False)

    # Status
    status = Column(
        Enum(InvitationStatus),
        default=InvitationStatus.PENDING,
        nullable=False,
        index=True
    )

    # Personalization
    personal_message = Column(String(500), nullable=True, comment="Custom message from inviter")

    # Tracking
    invited_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False
    )
    accepted_at = Column(DateTime, nullable=True)
    accepted_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
        comment="User created from this invitation"
    )
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)

    # Email tracking
    email_sent_at = Column(DateTime, nullable=True)
    email_opened_at = Column(DateTime, nullable=True)
    link_clicked_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    firm = relationship("Firm", back_populates="invitations")
    inviter = relationship("User", foreign_keys=[invited_by])
    accepted_user = relationship("User", foreign_keys=[accepted_by_user_id])
    revoker = relationship("User", foreign_keys=[revoked_by])

    __table_args__ = (
        Index("ix_invitation_token", "token"),
        Index("ix_invitation_firm_status", "firm_id", "status"),
        Index("ix_invitation_email_firm", "email", "firm_id"),
        Index("ix_invitation_invited_by", "invited_by"),
        Index("ix_invitation_accepted_by", "accepted_by_user_id"),
        Index("ix_invitation_revoked_by", "revoked_by"),
    )

    def __init__(self, **kwargs):
        """Initialize invitation with default expiration."""
        if "expires_at" not in kwargs:
            kwargs["expires_at"] = datetime.utcnow() + timedelta(days=7)
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<Invitation(id={self.invitation_id}, email={self.email}, status={self.status})>"

    @property
    def is_pending(self) -> bool:
        """Check if invitation is still pending."""
        return self.status == InvitationStatus.PENDING

    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        if self.status == InvitationStatus.EXPIRED:
            return True
        if self.status == InvitationStatus.PENDING:
            return datetime.utcnow() > self.expires_at
        return False

    @property
    def is_valid(self) -> bool:
        """Check if invitation is valid (pending and not expired)."""
        return self.is_pending and not self.is_expired

    def accept(self, user_id) -> None:
        """Mark invitation as accepted."""
        self.status = InvitationStatus.ACCEPTED
        self.accepted_at = datetime.utcnow()
        self.accepted_by_user_id = user_id

    def revoke(self, revoked_by_user_id) -> None:
        """Revoke the invitation."""
        self.status = InvitationStatus.REVOKED
        self.revoked_at = datetime.utcnow()
        self.revoked_by = revoked_by_user_id

    def mark_expired(self) -> None:
        """Mark invitation as expired."""
        self.status = InvitationStatus.EXPIRED

    def regenerate_token(self, extend_days: int = 7) -> str:
        """Regenerate token and extend expiration."""
        self.token = generate_invitation_token()
        self.expires_at = datetime.utcnow() + timedelta(days=extend_days)
        self.status = InvitationStatus.PENDING
        return self.token
