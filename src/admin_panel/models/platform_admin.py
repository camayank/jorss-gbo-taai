"""
Platform Admin Models - Internal platform administration.

Platform admins are internal team members with elevated privileges:
- Super Admin: Full platform access
- Support: Firm impersonation, issue resolution
- Billing: Subscription management, invoice adjustments
- Compliance: Audit log access, GDPR requests
"""

from datetime import datetime
from typing import Optional, Set
from uuid import uuid4
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Index, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.models import Base, JSONB


class AdminRole(str, PyEnum):
    """Platform admin roles."""
    SUPER_ADMIN = "super_admin"
    SUPPORT = "support"
    BILLING = "billing"
    COMPLIANCE = "compliance"
    ENGINEERING = "engineering"


# Admin role permissions
ADMIN_ROLE_PERMISSIONS: dict[AdminRole, Set[str]] = {
    AdminRole.SUPER_ADMIN: {
        "view_all_firms", "manage_firms", "impersonate_firm",
        "manage_subscriptions", "adjust_billing", "process_refunds",
        "manage_feature_flags", "view_system_health", "manage_platform_admins",
        "view_audit_logs", "process_gdpr_requests", "export_data",
        "manage_announcements", "configure_system",
    },
    AdminRole.SUPPORT: {
        "view_all_firms", "impersonate_firm",
        "view_subscriptions", "view_audit_logs",
    },
    AdminRole.BILLING: {
        "view_all_firms", "view_subscriptions",
        "manage_subscriptions", "adjust_billing", "process_refunds",
        "view_audit_logs",
    },
    AdminRole.COMPLIANCE: {
        "view_all_firms", "view_subscriptions",
        "view_audit_logs", "process_gdpr_requests", "export_data",
    },
    AdminRole.ENGINEERING: {
        "view_all_firms", "manage_feature_flags",
        "view_system_health", "view_audit_logs",
    },
}


class PlatformAdmin(Base):
    """
    Platform Admin - Internal team member with elevated privileges.

    Separate from firm users to maintain clear separation of concerns.
    """
    __tablename__ = "platform_admins"

    # Primary Key
    admin_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Identity
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Profile
    name = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    department = Column(String(100), nullable=True)

    # Role & Permissions
    role = Column(Enum(AdminRole), nullable=False, default=AdminRole.SUPPORT)
    custom_permissions = Column(JSONB, default=list, comment="Additional permissions")

    # Security (MFA required for all platform admins)
    mfa_enabled = Column(Boolean, default=True, nullable=False)
    mfa_secret = Column(String(100), nullable=True)
    mfa_backup_codes = Column(JSONB, nullable=True, comment="Encrypted backup codes")

    # Session Security
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, index=True)
    deactivated_at = Column(DateTime, nullable=True)
    deactivated_reason = Column(String(255), nullable=True)

    # Tracking
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    last_activity_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("platform_admins.admin_id"), nullable=True)

    # Relationships
    audit_logs = relationship("AdminAuditLog", back_populates="admin", foreign_keys="AdminAuditLog.admin_id")

    __table_args__ = (
        Index("ix_platform_admin_role", "role"),
        Index("ix_platform_admin_active", "is_active"),
    )

    def __repr__(self):
        return f"<PlatformAdmin(email={self.email}, role={self.role})>"

    def get_permissions(self) -> Set[str]:
        """Get effective permissions including custom overrides."""
        base_permissions = ADMIN_ROLE_PERMISSIONS.get(self.role, set())
        permissions = set(base_permissions)

        # Add custom permissions
        for perm in (self.custom_permissions or []):
            if isinstance(perm, str):
                permissions.add(perm)

        return permissions

    def has_permission(self, permission: str) -> bool:
        """Check if admin has a specific permission."""
        return permission in self.get_permissions()

    def can_impersonate(self) -> bool:
        """Check if admin can impersonate firms."""
        return self.has_permission("impersonate_firm")


class AdminAuditLog(Base):
    """
    Admin Audit Log - Tracks all platform admin actions.

    Required for compliance and security monitoring.
    All admin actions are immutable and logged.
    """
    __tablename__ = "admin_audit_log"

    # Primary Key
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Admin Reference
    admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("platform_admins.admin_id"),
        nullable=False,
        index=True
    )

    # Action Details
    action = Column(String(100), nullable=False, index=True)
    action_category = Column(String(50), nullable=True, comment="firm, subscription, feature, system")

    # Target Resource
    resource_type = Column(String(50), nullable=True, comment="firm, user, subscription, feature_flag")
    resource_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Change Tracking
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)

    # Request Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(64), nullable=True, comment="Correlation ID")

    # Impersonation Context
    impersonating_firm_id = Column(UUID(as_uuid=True), nullable=True)
    impersonating_user_id = Column(UUID(as_uuid=True), nullable=True)

    # Additional Context
    description = Column(Text, nullable=True)
    extra_data = Column(JSONB, nullable=True)

    # Timestamp (immutable)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    admin = relationship("PlatformAdmin", back_populates="audit_logs", foreign_keys=[admin_id])

    __table_args__ = (
        Index("ix_admin_audit_action", "action", "created_at"),
        Index("ix_admin_audit_resource", "resource_type", "resource_id"),
        Index("ix_admin_audit_category", "action_category", "created_at"),
    )

    def __repr__(self):
        return f"<AdminAuditLog(action={self.action}, admin={self.admin_id})>"

    @classmethod
    def log_action(
        cls,
        admin_id,
        action: str,
        resource_type: str = None,
        resource_id = None,
        old_values: dict = None,
        new_values: dict = None,
        ip_address: str = None,
        user_agent: str = None,
        description: str = None,
        **kwargs
    ) -> "AdminAuditLog":
        """Factory method to create audit log entry."""
        return cls(
            admin_id=admin_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            description=description,
            metadata=kwargs.get("metadata"),
            action_category=kwargs.get("action_category"),
            impersonating_firm_id=kwargs.get("impersonating_firm_id"),
            impersonating_user_id=kwargs.get("impersonating_user_id"),
            request_id=kwargs.get("request_id"),
        )
