"""
User Model - Team members within a CPA firm.

Uses the new RBAC system from src/rbac/ with 8 roles:
- Platform: super_admin, platform_admin, support, billing
- Firm: partner, staff
- Client: direct_client, firm_client
"""

from datetime import datetime
from typing import Optional, List, Set
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.models import Base, JSONB

# Import from new RBAC system
from rbac import Role, Permission


class User(Base):
    """
    User - Team member within a CPA firm.

    For CPA firm employees (partner, staff roles).
    Linked to a firm with role-based access control.
    """
    __tablename__ = "users"

    # Primary Key
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key to Firm
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Identity
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=True, comment="bcrypt hash")

    # Profile
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    job_title = Column(String(100), nullable=True)

    # Role (uses new RBAC system)
    # For firm users: 'partner' or 'staff'
    role = Column(String(50), nullable=False, default="staff", index=True)

    # Professional Credentials
    credentials = Column(JSONB, default=list, comment="['CPA', 'EA', 'CFP']")
    license_state = Column(String(2), nullable=True)
    license_number = Column(String(50), nullable=True)
    license_expiry = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime, nullable=True)

    # Security
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(100), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)
    must_change_password = Column(Boolean, default=False)

    # Session Management
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    last_activity_at = Column(DateTime, nullable=True)
    current_session_id = Column(String(64), nullable=True)

    # Notification Preferences
    notification_preferences = Column(JSONB, default=dict)

    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)

    # Relationships
    firm = relationship("Firm", back_populates="users")
    inviter = relationship("User", remote_side=[user_id], foreign_keys=[invited_by])
    feature_usage = relationship("FeatureUsage", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_user_firm_role", "firm_id", "role"),
        Index("ix_user_firm_active", "firm_id", "is_active"),
        Index("ix_user_last_activity", "last_activity_at"),
        CheckConstraint("failed_login_attempts >= 0", name="ck_user_login_attempts"),
    )

    def __repr__(self):
        return f"<User(id={self.user_id}, email={self.email}, role={self.role})>"

    @property
    def full_name(self) -> str:
        """Return full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_partner(self) -> bool:
        """Check if user is a partner (firm owner)."""
        return self.role == Role.PARTNER.value

    @property
    def is_staff(self) -> bool:
        """Check if user is staff."""
        return self.role == Role.STAFF.value

    @property
    def is_locked(self) -> bool:
        """Check if user account is locked."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def get_role(self) -> Role:
        """Get the Role enum for this user."""
        try:
            return Role(self.role)
        except ValueError:
            return Role.STAFF  # Default to staff

    def get_permissions(self) -> Set[Permission]:
        """Get all permissions for this user's role."""
        from rbac.permissions import ROLE_PERMISSIONS
        return set(ROLE_PERMISSIONS.get(self.get_role(), frozenset()))

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in self.get_permissions()

    def record_login(self, ip_address: str, session_id: str) -> None:
        """Record successful login."""
        self.last_login_at = datetime.utcnow()
        self.last_login_ip = ip_address
        self.last_activity_at = datetime.utcnow()
        self.current_session_id = session_id
        self.failed_login_attempts = 0
        self.locked_until = None

    def record_failed_login(self, max_attempts: int = 5, lockout_minutes: int = 30) -> None:
        """Record failed login attempt."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            from datetime import timedelta
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)


# =============================================================================
# BACKWARD COMPATIBILITY (deprecated, use rbac.Role instead)
# =============================================================================

from enum import Enum as PyEnum


class UserRole(str, PyEnum):
    """
    DEPRECATED: Use rbac.Role instead.

    Kept for backward compatibility with existing code.
    Maps to the new roles:
    - FIRM_ADMIN -> Role.PARTNER
    - SENIOR_PREPARER -> Role.PARTNER (elevated staff)
    - PREPARER -> Role.STAFF
    - REVIEWER -> Role.STAFF
    """
    FIRM_ADMIN = "partner"
    SENIOR_PREPARER = "partner"
    PREPARER = "staff"
    REVIEWER = "staff"


class UserPermission(str, PyEnum):
    """
    DEPRECATED: Use rbac.Permission instead.

    Kept for backward compatibility.
    """
    # Team Management
    MANAGE_TEAM = "team_manage"
    INVITE_USERS = "team_invite"
    VIEW_TEAM_PERFORMANCE = "team_view"

    # Client Management
    VIEW_CLIENT = "client_view_own"
    VIEW_ALL_CLIENTS = "client_view_all"
    CREATE_CLIENT = "client_create"
    EDIT_CLIENT = "client_edit"
    MANAGE_CLIENT = "client_edit"
    ARCHIVE_CLIENT = "client_archive"
    ASSIGN_CLIENTS = "client_assign"

    # Return Operations
    VIEW_RETURNS = "return_view_own"
    CREATE_RETURN = "return_create"
    EDIT_RETURNS = "return_edit"
    EDIT_RETURN = "return_edit"
    MANAGE_RETURNS = "return_edit"
    SUBMIT_FOR_REVIEW = "return_submit"
    REVIEW_RETURNS = "return_review"
    APPROVE_RETURN = "return_approve"
    REJECT_RETURN = "return_approve"

    # Scenarios & Analysis
    RUN_SCENARIOS = "return_run_scenarios"
    VIEW_OPTIMIZATION = "return_run_scenarios"
    GENERATE_REPORTS = "return_generate_advisory"

    # Billing & Admin
    VIEW_BILLING = "firm_view_billing"
    UPDATE_PAYMENT = "firm_manage_billing"
    CHANGE_PLAN = "firm_manage_billing"
    UPDATE_BRANDING = "firm_manage_branding"
