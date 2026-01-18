"""
RBAC Database Models - SQLAlchemy ORM models for the global RBAC system.

Tables:
- permissions: Permission definitions (system-managed catalog)
- role_templates: Role definitions (system + custom per firm/partner)
- role_permissions: Role-to-permission mappings
- user_role_assignments: User-to-role assignments
- user_permission_overrides: Per-user permission grants/revokes
- rbac_audit_log: Permission check audit trail
- permission_cache_versions: Cache invalidation tracking
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, Set
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Index, CheckConstraint, UniqueConstraint, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

# Import base from existing database module
from database.models import Base, JSONB


# =============================================================================
# ENUMERATIONS
# =============================================================================

class HierarchyLevel(int, PyEnum):
    """
    Access control hierarchy levels.

    Lower numbers = higher privilege.
    Users can only manage roles at their level or below.
    """
    PLATFORM = 0    # Internal admins (super_admin, support, billing, etc.)
    PARTNER = 1     # White-label partner admins
    FIRM = 2        # CPA firm roles (firm_admin, senior_preparer, etc.)
    USER = 3        # Per-user overrides
    RESOURCE = 4    # Resource-level access (client, return, document)


class PermissionCategory(str, PyEnum):
    """Permission categories for grouping in UI."""
    TEAM = "team"                    # Team/user management
    CLIENT = "client"                # Client management
    RETURN = "return"                # Tax return operations
    SCENARIO = "scenario"            # Scenario analysis
    COMPLIANCE = "compliance"        # Audit, compliance, GDPR
    BILLING = "billing"              # Billing and subscription
    SETTINGS = "settings"            # Firm settings, branding
    PLATFORM = "platform"            # Platform administration
    PARTNER = "partner"              # Partner management
    WORKFLOW = "workflow"            # Workflow operations
    DOCUMENT = "document"            # Document management
    REPORT = "report"                # Reporting


class OverrideAction(str, PyEnum):
    """Action for permission overrides."""
    GRANT = "grant"      # Add permission not in role
    REVOKE = "revoke"    # Remove permission from role


class AuditAction(str, PyEnum):
    """Actions logged in RBAC audit trail."""
    PERMISSION_CHECK = "permission_check"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"
    ACCESS_DENIED = "access_denied"
    CACHE_INVALIDATED = "cache_invalidated"


# =============================================================================
# PERMISSION MODEL
# =============================================================================

class Permission(Base):
    """
    Permission definitions - System-managed catalog of all permissions.

    Permissions are identified by their code (e.g., "manage_team").
    This table is seeded from code and not user-editable.
    """
    __tablename__ = "permissions"

    # Primary Key
    permission_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Permission Identity
    code = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Categorization
    category = Column(Enum(PermissionCategory), nullable=False, index=True)

    # Hierarchy - minimum level required to grant this permission
    min_hierarchy_level = Column(
        Integer,
        nullable=False,
        default=HierarchyLevel.FIRM.value,
        comment="Minimum level required to grant this permission"
    )

    # Tier restrictions
    tier_restriction = Column(
        JSONB,
        default=list,
        comment="List of tiers where this permission is available: ['starter', 'professional', 'enterprise']"
    )

    # Feature flag - can be disabled globally
    is_enabled = Column(Boolean, default=True, index=True)

    # System flag - cannot be deleted or modified
    is_system = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    role_permissions = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_permission_category_enabled", "category", "is_enabled"),
        CheckConstraint(
            "min_hierarchy_level >= 0 AND min_hierarchy_level <= 4",
            name="ck_permission_hierarchy"
        ),
    )

    def __repr__(self):
        return f"<Permission(code={self.code}, category={self.category})>"


# =============================================================================
# ROLE TEMPLATE MODEL
# =============================================================================

class RoleTemplate(Base):
    """
    Role definitions - System roles and custom firm/partner roles.

    System roles (is_system=True) are seeded from code.
    Custom roles can be created by firm admins within tier limits.
    """
    __tablename__ = "role_templates"

    # Primary Key
    role_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Role Identity
    code = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Hierarchy Level
    hierarchy_level = Column(
        Integer,
        nullable=False,
        default=HierarchyLevel.FIRM.value,
        index=True
    )

    # Ownership - NULL for system roles, firm_id for custom roles
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("partners.partner_id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Inheritance - parent role for permission inheritance
    parent_role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("role_templates.role_id", ondelete="SET NULL"),
        nullable=True
    )

    # System flag
    is_system = Column(Boolean, default=False, index=True)

    # Active flag
    is_active = Column(Boolean, default=True, index=True)

    # Can this role be assigned to users?
    is_assignable = Column(Boolean, default=True)

    # Display order for UI
    display_order = Column(Integer, default=100)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    role_permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan"
    )
    parent_role = relationship(
        "RoleTemplate",
        remote_side=[role_id],
        foreign_keys=[parent_role_id]
    )
    user_assignments = relationship(
        "UserRoleAssignment",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        # System roles have unique codes globally
        # Custom roles have unique codes within a firm/partner
        UniqueConstraint(
            "code", "firm_id", "partner_id",
            name="uq_role_code_scope"
        ),
        Index("ix_role_hierarchy_active", "hierarchy_level", "is_active"),
        Index("ix_role_firm_active", "firm_id", "is_active"),
        CheckConstraint(
            "hierarchy_level >= 0 AND hierarchy_level <= 4",
            name="ck_role_hierarchy"
        ),
        # Either firm_id or partner_id can be set, not both
        CheckConstraint(
            "(firm_id IS NULL OR partner_id IS NULL)",
            name="ck_role_scope"
        ),
    )

    def __repr__(self):
        return f"<RoleTemplate(code={self.code}, level={self.hierarchy_level})>"


# =============================================================================
# ROLE-PERMISSION MAPPING
# =============================================================================

class RolePermission(Base):
    """
    Role-to-Permission mapping.

    Links roles to their granted permissions.
    """
    __tablename__ = "role_permissions"

    # Composite Primary Key
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("role_templates.role_id", ondelete="CASCADE"),
        primary_key=True
    )
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permissions.permission_id", ondelete="CASCADE"),
        primary_key=True
    )

    # Metadata
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    granted_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    role = relationship("RoleTemplate", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    __table_args__ = (
        Index("ix_role_permission_role", "role_id"),
        Index("ix_role_permission_permission", "permission_id"),
    )

    def __repr__(self):
        return f"<RolePermission(role={self.role_id}, permission={self.permission_id})>"


# =============================================================================
# USER ROLE ASSIGNMENT
# =============================================================================

class UserRoleAssignment(Base):
    """
    User-to-Role assignment.

    Users can have multiple roles. One role is marked as primary.
    Replaces the single `role` column on User model.
    """
    __tablename__ = "user_role_assignments"

    # Composite Primary Key
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    )
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("role_templates.role_id", ondelete="CASCADE"),
        primary_key=True
    )

    # Primary role flag - only one per user
    is_primary = Column(Boolean, default=False, index=True)

    # Assignment metadata
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_by = Column(UUID(as_uuid=True), nullable=True)
    expires_at = Column(DateTime, nullable=True, comment="Optional role expiration")

    # Assignment context
    notes = Column(Text, nullable=True)

    # Relationships
    role = relationship("RoleTemplate", back_populates="user_assignments")

    __table_args__ = (
        Index("ix_user_role_user", "user_id"),
        Index("ix_user_role_role", "role_id"),
        Index("ix_user_role_primary", "user_id", "is_primary"),
    )

    def __repr__(self):
        return f"<UserRoleAssignment(user={self.user_id}, role={self.role_id}, primary={self.is_primary})>"


# =============================================================================
# USER PERMISSION OVERRIDE
# =============================================================================

class UserPermissionOverride(Base):
    """
    Per-user permission grants/revokes.

    Allows fine-grained permission control beyond role defaults.
    Grants add permissions, revokes remove them.
    """
    __tablename__ = "user_permission_overrides"

    # Primary Key
    override_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # User
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Permission
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permissions.permission_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Action
    action = Column(Enum(OverrideAction), nullable=False)

    # Optional resource-level scope
    resource_type = Column(
        String(50),
        nullable=True,
        comment="Optional: 'client', 'return', 'document'"
    )
    resource_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Optional: specific resource ID"
    )

    # Expiration
    expires_at = Column(DateTime, nullable=True)

    # Metadata
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        # Unique constraint per user/permission/resource combination
        UniqueConstraint(
            "user_id", "permission_id", "resource_type", "resource_id",
            name="uq_user_permission_override"
        ),
        Index("ix_override_user_action", "user_id", "action"),
        Index("ix_override_resource", "resource_type", "resource_id"),
    )

    def __repr__(self):
        return f"<UserPermissionOverride(user={self.user_id}, action={self.action})>"


# =============================================================================
# RBAC AUDIT LOG
# =============================================================================

class RBACauditLog(Base):
    """
    RBAC audit trail for permission checks and changes.

    Logs sensitive permission operations for compliance.
    """
    __tablename__ = "rbac_audit_log"

    # Primary Key
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Action
    action = Column(Enum(AuditAction), nullable=False, index=True)

    # Actor
    actor_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    actor_type = Column(
        String(50),
        nullable=False,
        default="user",
        comment="'user', 'platform_admin', 'system'"
    )

    # Target
    target_user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    target_role_id = Column(UUID(as_uuid=True), nullable=True)
    target_permission_id = Column(UUID(as_uuid=True), nullable=True)

    # Context
    firm_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)

    # Result
    success = Column(Boolean, default=True)
    denial_reason = Column(Text, nullable=True)

    # Request context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)

    # Additional data
    event_metadata = Column(JSONB, default=dict)

    __table_args__ = (
        Index("ix_rbac_audit_actor_time", "actor_id", "timestamp"),
        Index("ix_rbac_audit_target_time", "target_user_id", "timestamp"),
        Index("ix_rbac_audit_firm_time", "firm_id", "timestamp"),
        Index("ix_rbac_audit_action_success", "action", "success"),
    )

    def __repr__(self):
        return f"<RBACauditLog(action={self.action}, actor={self.actor_id})>"


# =============================================================================
# PERMISSION CACHE VERSION
# =============================================================================

class PermissionCacheVersion(Base):
    """
    Cache invalidation tracking.

    Tracks version numbers for permission cache at various scopes.
    Increment version to invalidate cached permissions.
    """
    __tablename__ = "permission_cache_versions"

    # Primary Key
    version_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Scope - what cache entries should be invalidated
    scope = Column(
        String(50),
        nullable=False,
        index=True,
        comment="'global', 'firm:{id}', 'user:{id}'"
    )

    # Version number - incremented on changes
    version = Column(Integer, nullable=False, default=1)

    # Last update
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    update_reason = Column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("scope", name="uq_cache_version_scope"),
    )

    def __repr__(self):
        return f"<PermissionCacheVersion(scope={self.scope}, version={self.version})>"


# =============================================================================
# PARTNER MODELS (White-Label Support)
# =============================================================================

class Partner(Base):
    """
    White-label partner organization.

    Partners can have multiple firms under their management
    with custom branding and separate login portals.
    """
    __tablename__ = "partners"

    # Primary Key
    partner_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Partner Identity
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)

    # Contact
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    website = Column(String(255), nullable=True)

    # White-Label Branding
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#059669")
    secondary_color = Column(String(7), default="#1e40af")
    custom_domain = Column(String(255), nullable=True, unique=True)
    login_page_url = Column(String(500), nullable=True)

    # API Access
    api_enabled = Column(Boolean, default=False)
    api_key_hash = Column(String(64), nullable=True)
    api_rate_limit = Column(Integer, default=1000, comment="Requests per hour")

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Contract/Billing
    contract_start_date = Column(DateTime, nullable=True)
    contract_end_date = Column(DateTime, nullable=True)
    billing_email = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Settings
    settings = Column(JSONB, default=dict)

    # Relationships
    partner_firms = relationship(
        "PartnerFirm",
        back_populates="partner",
        cascade="all, delete-orphan"
    )
    partner_admins = relationship(
        "PartnerAdmin",
        back_populates="partner",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_partner_active", "is_active"),
    )

    def __repr__(self):
        return f"<Partner(code={self.code}, name={self.name})>"


class PartnerFirm(Base):
    """
    Partner-Firm relationship.

    Links firms to their managing partner organization.
    """
    __tablename__ = "partner_firms"

    # Composite Primary Key
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("partners.partner_id", ondelete="CASCADE"),
        primary_key=True
    )
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        primary_key=True
    )

    # Relationship metadata
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(
        String(20),
        default="active",
        comment="active, suspended, pending"
    )

    # Revenue sharing / billing
    revenue_share_percent = Column(Integer, default=0)

    # Notes
    notes = Column(Text, nullable=True)

    # Relationships
    partner = relationship("Partner", back_populates="partner_firms")

    __table_args__ = (
        Index("ix_partner_firm_partner", "partner_id"),
        Index("ix_partner_firm_firm", "firm_id"),
    )

    def __repr__(self):
        return f"<PartnerFirm(partner={self.partner_id}, firm={self.firm_id})>"


class PartnerAdmin(Base):
    """
    Partner organization administrators.

    Users who can manage firms under a partner organization.
    """
    __tablename__ = "partner_admins"

    # Primary Key
    admin_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Partner link
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("partners.partner_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Admin Identity
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)

    # Role within partner org
    role = Column(
        String(50),
        nullable=False,
        default="partner_admin",
        comment="partner_admin, partner_manager, partner_support"
    )

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Security
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(100), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    partner = relationship("Partner", back_populates="partner_admins")

    __table_args__ = (
        Index("ix_partner_admin_partner", "partner_id", "is_active"),
    )

    def __repr__(self):
        return f"<PartnerAdmin(email={self.email}, partner={self.partner_id})>"


# =============================================================================
# CLIENT ACCESS GRANTS (Deferred to Phase 2)
# =============================================================================

class ClientAccessGrant(Base):
    """
    Resource-level client access grants.

    Allows specific users access to specific clients
    beyond their role-based access.

    Deferred to Phase 2 - placeholder for schema.
    """
    __tablename__ = "client_access_grants"

    # Primary Key
    grant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # User being granted access
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Client being accessed
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Access level
    access_level = Column(
        String(20),
        nullable=False,
        default="read",
        comment="read, write, manage"
    )

    # Grant metadata
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    granted_by = Column(UUID(as_uuid=True), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_client_access_grant"),
        Index("ix_client_access_user", "user_id"),
        Index("ix_client_access_client", "client_id"),
        CheckConstraint(
            "access_level IN ('read', 'write', 'manage')",
            name="ck_access_level"
        ),
    )

    def __repr__(self):
        return f"<ClientAccessGrant(user={self.user_id}, client={self.client_id}, level={self.access_level})>"
