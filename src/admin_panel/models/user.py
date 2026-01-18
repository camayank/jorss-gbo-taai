"""
User Model - Team members within a firm.

Users have role-based access control (RBAC) with the following hierarchy:
- firm_admin: Full firm access, team management, billing
- senior_preparer: Complex returns, mentor juniors, quality review
- preparer: Return preparation, scenario analysis
- reviewer: Approve/reject returns, quality assurance
"""

from datetime import datetime
from typing import Optional, List, Set
from uuid import uuid4
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Index, CheckConstraint, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.models import Base, JSONB


class UserRole(str, PyEnum):
    """User roles within a firm."""
    FIRM_ADMIN = "firm_admin"
    SENIOR_PREPARER = "senior_preparer"
    PREPARER = "preparer"
    REVIEWER = "reviewer"


class UserPermission(str, PyEnum):
    """
    Granular permissions for fine-grained access control.

    Can be used to override role defaults.
    """
    # Team Management
    MANAGE_TEAM = "manage_team"
    INVITE_USERS = "invite_users"
    VIEW_TEAM_PERFORMANCE = "view_team_performance"

    # Client Management
    VIEW_CLIENT = "view_client"
    VIEW_ALL_CLIENTS = "view_all_clients"
    CREATE_CLIENT = "create_client"
    EDIT_CLIENT = "edit_client"
    MANAGE_CLIENT = "manage_client"
    ARCHIVE_CLIENT = "archive_client"
    ASSIGN_CLIENTS = "assign_clients"

    # Return Operations
    VIEW_RETURNS = "view_returns"
    CREATE_RETURN = "create_return"
    EDIT_RETURNS = "edit_returns"
    EDIT_RETURN = "edit_return"
    MANAGE_RETURNS = "manage_returns"
    SUBMIT_FOR_REVIEW = "submit_for_review"
    REVIEW_RETURNS = "review_returns"
    APPROVE_RETURN = "approve_return"
    REJECT_RETURN = "reject_return"

    # Scenarios & Analysis
    RUN_SCENARIOS = "run_scenarios"
    VIEW_OPTIMIZATION = "view_optimization"
    GENERATE_REPORTS = "generate_reports"

    # Compliance & Audit
    VIEW_COMPLIANCE = "view_compliance"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    EXPORT_AUDIT_TRAIL = "export_audit_trail"
    GDPR_REQUESTS = "gdpr_requests"

    # Billing & Admin
    VIEW_BILLING = "view_billing"
    UPDATE_PAYMENT = "update_payment"
    CHANGE_PLAN = "change_plan"
    UPDATE_BRANDING = "update_branding"
    MANAGE_API_KEYS = "manage_api_keys"
    CONFIGURE_INTEGRATIONS = "configure_integrations"


# Role to default permissions mapping
ROLE_PERMISSIONS: dict[UserRole, Set[UserPermission]] = {
    UserRole.FIRM_ADMIN: {
        # All permissions
        UserPermission.MANAGE_TEAM,
        UserPermission.INVITE_USERS,
        UserPermission.VIEW_TEAM_PERFORMANCE,
        UserPermission.VIEW_CLIENT,
        UserPermission.VIEW_ALL_CLIENTS,
        UserPermission.CREATE_CLIENT,
        UserPermission.EDIT_CLIENT,
        UserPermission.MANAGE_CLIENT,
        UserPermission.ARCHIVE_CLIENT,
        UserPermission.ASSIGN_CLIENTS,
        UserPermission.VIEW_RETURNS,
        UserPermission.CREATE_RETURN,
        UserPermission.EDIT_RETURNS,
        UserPermission.EDIT_RETURN,
        UserPermission.MANAGE_RETURNS,
        UserPermission.REVIEW_RETURNS,
        UserPermission.APPROVE_RETURN,
        UserPermission.REJECT_RETURN,
        UserPermission.VIEW_COMPLIANCE,
        UserPermission.VIEW_AUDIT_LOGS,
        UserPermission.EXPORT_AUDIT_TRAIL,
        UserPermission.GDPR_REQUESTS,
        UserPermission.VIEW_BILLING,
        UserPermission.UPDATE_PAYMENT,
        UserPermission.CHANGE_PLAN,
        UserPermission.UPDATE_BRANDING,
        UserPermission.MANAGE_API_KEYS,
        UserPermission.CONFIGURE_INTEGRATIONS,
        UserPermission.RUN_SCENARIOS,
        UserPermission.VIEW_OPTIMIZATION,
        UserPermission.GENERATE_REPORTS,
    },
    UserRole.SENIOR_PREPARER: {
        UserPermission.VIEW_TEAM_PERFORMANCE,
        UserPermission.VIEW_CLIENT,
        UserPermission.VIEW_ALL_CLIENTS,
        UserPermission.CREATE_CLIENT,
        UserPermission.EDIT_CLIENT,
        UserPermission.MANAGE_CLIENT,
        UserPermission.ASSIGN_CLIENTS,
        UserPermission.VIEW_RETURNS,
        UserPermission.CREATE_RETURN,
        UserPermission.EDIT_RETURNS,
        UserPermission.EDIT_RETURN,
        UserPermission.MANAGE_RETURNS,
        UserPermission.SUBMIT_FOR_REVIEW,
        UserPermission.RUN_SCENARIOS,
        UserPermission.VIEW_OPTIMIZATION,
        UserPermission.GENERATE_REPORTS,
        UserPermission.VIEW_COMPLIANCE,
        UserPermission.VIEW_AUDIT_LOGS,
    },
    UserRole.PREPARER: {
        UserPermission.VIEW_CLIENT,
        UserPermission.CREATE_CLIENT,
        UserPermission.VIEW_RETURNS,
        UserPermission.CREATE_RETURN,
        UserPermission.EDIT_RETURNS,
        UserPermission.EDIT_RETURN,
        UserPermission.SUBMIT_FOR_REVIEW,
        UserPermission.RUN_SCENARIOS,
        UserPermission.VIEW_OPTIMIZATION,
        UserPermission.GENERATE_REPORTS,
    },
    UserRole.REVIEWER: {
        UserPermission.VIEW_TEAM_PERFORMANCE,
        UserPermission.VIEW_CLIENT,
        UserPermission.VIEW_RETURNS,
        UserPermission.REVIEW_RETURNS,
        UserPermission.APPROVE_RETURN,
        UserPermission.REJECT_RETURN,
        UserPermission.VIEW_COMPLIANCE,
        UserPermission.VIEW_AUDIT_LOGS,
        UserPermission.VIEW_OPTIMIZATION,
    },
}


class User(Base):
    """
    User - Team member within a firm.

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

    # Role & Permissions
    role = Column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.PREPARER,
        index=True
    )
    custom_permissions = Column(
        JSONB,
        default=list,
        comment="Custom permission overrides (add/remove from role defaults)"
    )

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
    def is_firm_admin(self) -> bool:
        """Check if user is a firm admin."""
        return self.role == UserRole.FIRM_ADMIN

    @property
    def is_locked(self) -> bool:
        """Check if user account is locked."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def get_permissions(self) -> Set[str]:
        """
        Get effective permissions for this user.

        Combines role default permissions with custom overrides.
        """
        # Start with role defaults
        base_permissions = ROLE_PERMISSIONS.get(self.role, set())
        permissions = {p.value for p in base_permissions}

        # Apply custom overrides
        custom = self.custom_permissions or []
        for override in custom:
            if isinstance(override, dict):
                action = override.get("action")
                permission = override.get("permission")
                if action == "add" and permission:
                    permissions.add(permission)
                elif action == "remove" and permission:
                    permissions.discard(permission)

        return permissions

    def has_permission(self, permission: UserPermission) -> bool:
        """Check if user has a specific permission."""
        return permission.value in self.get_permissions()

    def can_access_client(self, client_id: str, assigned_clients: List[str]) -> bool:
        """
        Check if user can access a specific client.

        Firm admins and senior preparers can access all clients.
        Preparers can only access assigned clients.
        Reviewers can access clients in review queue.
        """
        if self.role in (UserRole.FIRM_ADMIN, UserRole.SENIOR_PREPARER):
            return True
        if self.role == UserRole.PREPARER:
            return client_id in assigned_clients
        # Reviewers have queue-based access (handled at service level)
        return False

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
