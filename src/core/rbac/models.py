"""
Core RBAC ORM models.

These models back platform-level RBAC management for admin APIs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.models import Base, JSONB


class HierarchyLevel(int, Enum):
    """Hierarchy levels for RBAC scope and role authority."""

    PLATFORM = 0
    FIRM = 1
    CLIENT = 2


class PermissionCategory(str, Enum):
    """Permission category."""

    PLATFORM = "platform"
    FIRM = "firm"
    TEAM = "team"
    CLIENT = "client"
    RETURN = "return"
    DOCUMENT = "document"
    SELF = "self"


class OverrideAction(str, Enum):
    """User permission override action."""

    GRANT = "grant"
    REVOKE = "revoke"


class Permission(Base):
    """RBAC permission catalog."""

    __tablename__ = "permissions"

    permission_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    code = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)
    min_hierarchy_level = Column(Integer, nullable=False, default=HierarchyLevel.CLIENT.value)
    tier_restriction = Column(JSONB, default=list)
    is_enabled = Column(Boolean, default=True, index=True)
    is_system = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    role_permissions = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "min_hierarchy_level >= 0 AND min_hierarchy_level <= 4",
            name="ck_permission_hierarchy",
        ),
        Index("ix_permission_category_enabled", "category", "is_enabled"),
    )


class RoleTemplate(Base):
    """Role template (system or custom role)."""

    __tablename__ = "role_templates"

    role_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    code = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    hierarchy_level = Column(Integer, nullable=False, default=HierarchyLevel.CLIENT.value, index=True)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.firm_id", ondelete="CASCADE"), nullable=True, index=True)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.partner_id", ondelete="CASCADE"), nullable=True, index=True)
    parent_role_id = Column(UUID(as_uuid=True), ForeignKey("role_templates.role_id", ondelete="SET NULL"), nullable=True)
    is_system = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    is_assignable = Column(Boolean, default=True)
    display_order = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    role_permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )
    user_assignments = relationship(
        "UserRoleAssignment",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("code", "firm_id", "partner_id", name="uq_role_code_scope"),
        CheckConstraint("hierarchy_level >= 0 AND hierarchy_level <= 4", name="ck_role_hierarchy"),
        CheckConstraint("(firm_id IS NULL OR partner_id IS NULL)", name="ck_role_scope"),
        Index("ix_role_hierarchy_active", "hierarchy_level", "is_active"),
        Index("ix_role_firm_active", "firm_id", "is_active"),
    )


class RolePermission(Base):
    """Role to permission mapping."""

    __tablename__ = "role_permissions"

    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("role_templates.role_id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permissions.permission_id", ondelete="CASCADE"),
        primary_key=True,
    )
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(UUID(as_uuid=True), nullable=True)

    role = relationship("RoleTemplate", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    __table_args__ = (
        Index("ix_role_permission_role", "role_id"),
        Index("ix_role_permission_permission", "permission_id"),
    )


class UserRoleAssignment(Base):
    """User role assignment."""

    __tablename__ = "user_role_assignments"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("role_templates.role_id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary = Column(Boolean, default=False, index=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(UUID(as_uuid=True), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    role = relationship("RoleTemplate", back_populates="user_assignments")

    __table_args__ = (
        Index("ix_user_role_user", "user_id"),
        Index("ix_user_role_role", "role_id"),
        Index("ix_user_role_primary", "user_id", "is_primary"),
    )


class UserPermissionOverride(Base):
    """Per-user permission override."""

    __tablename__ = "user_permission_overrides"

    override_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permissions.permission_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = Column(String(20), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    permission = relationship("Permission")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "permission_id",
            "resource_type",
            "resource_id",
            name="uq_user_permission_override",
        ),
        CheckConstraint("action IN ('grant', 'revoke')", name="ck_override_action"),
        Index("ix_override_user_action", "user_id", "action"),
        Index("ix_override_resource", "resource_type", "resource_id"),
    )


class RBACAuditLog(Base):
    """RBAC action audit log."""

    __tablename__ = "rbac_audit_log"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    actor_type = Column(String(50), default="user")
    target_user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    target_role_id = Column(UUID(as_uuid=True), nullable=True)
    target_permission_id = Column(UUID(as_uuid=True), nullable=True)
    firm_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    success = Column(Boolean, default=True)
    denial_reason = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)
    metadata_json = Column("metadata", JSONB, default=dict)

    __table_args__ = (
        Index("ix_rbac_audit_actor_time", "actor_id", "timestamp"),
        Index("ix_rbac_audit_target_time", "target_user_id", "timestamp"),
        Index("ix_rbac_audit_firm_time", "firm_id", "timestamp"),
        Index("ix_rbac_audit_action_success", "action", "success"),
    )


class PermissionCacheVersion(Base):
    """Cache versioning for permission invalidation."""

    __tablename__ = "permission_cache_versions"

    version_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    scope = Column(String(50), nullable=False, unique=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    update_reason = Column(String(200), nullable=True)


class Partner(Base):
    """White-label partner organization."""

    __tablename__ = "partners"

    partner_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    website = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#059669")
    secondary_color = Column(String(7), default="#1e40af")
    custom_domain = Column(String(255), nullable=True, unique=True)
    login_page_url = Column(String(500), nullable=True)
    api_enabled = Column(Boolean, default=False)
    api_key_hash = Column(String(64), nullable=True)
    api_rate_limit = Column(Integer, default=1000)
    is_active = Column(Boolean, default=True, index=True)
    contract_start_date = Column(DateTime, nullable=True)
    contract_end_date = Column(DateTime, nullable=True)
    billing_email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    settings = Column(JSONB, default=dict)

    partner_firms = relationship("PartnerFirm", back_populates="partner", cascade="all, delete-orphan")
    partner_admins = relationship("PartnerAdmin", back_populates="partner", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_partner_active", "is_active"),
    )


class PartnerFirm(Base):
    """Partner to firm assignment."""

    __tablename__ = "partner_firms"

    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("partners.partner_id", ondelete="CASCADE"),
        primary_key=True,
    )
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        primary_key=True,
    )
    joined_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="active")
    revenue_share_percent = Column(Integer, default=0)
    notes = Column(Text, nullable=True)

    partner = relationship("Partner", back_populates="partner_firms")

    __table_args__ = (
        Index("ix_partner_firm_partner", "partner_id"),
        Index("ix_partner_firm_firm", "firm_id"),
    )


class PartnerAdmin(Base):
    """Partner administrator account."""

    __tablename__ = "partner_admins"

    admin_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("partners.partner_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(String(50), default="partner_admin")
    is_active = Column(Boolean, default=True, index=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(100), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    partner = relationship("Partner", back_populates="partner_admins")

    __table_args__ = (
        Index("ix_partner_admin_partner", "partner_id", "is_active"),
    )


class ClientAccessGrant(Base):
    """User-level client access grants."""

    __tablename__ = "client_access_grants"

    grant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    access_level = Column(String(20), default="read")
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(UUID(as_uuid=True), nullable=True)


# Backward compatibility alias expected by core/__init__.py
RBACauditLog = RBACAuditLog
