"""Global RBAC Tables

Revision ID: 20260118_0002
Revises: 20260118_0001
Create Date: 2026-01-18

Creates tables for the global Role-Based Access Control system:
- permissions: Permission definitions (system catalog)
- role_templates: Role definitions (system + custom)
- role_permissions: Role-to-permission mappings
- user_role_assignments: User-to-role assignments
- user_permission_overrides: Per-user permission grants/revokes
- rbac_audit_log: Permission check audit trail
- permission_cache_versions: Cache invalidation tracking
- partners: White-label partner organizations
- partner_firms: Partner-firm relationships
- partner_admins: Partner organization admins
- client_access_grants: Resource-level client access (Phase 2)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260118_0002'
down_revision = '20260118_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # PARTNERS TABLE (White-Label Support)
    # =========================================================================
    op.create_table(
        'partners',
        sa.Column('partner_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('legal_name', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(7), server_default='#059669'),
        sa.Column('secondary_color', sa.String(7), server_default='#1e40af'),
        sa.Column('custom_domain', sa.String(255), nullable=True, unique=True),
        sa.Column('login_page_url', sa.String(500), nullable=True),
        sa.Column('api_enabled', sa.Boolean, server_default='false'),
        sa.Column('api_key_hash', sa.String(64), nullable=True),
        sa.Column('api_rate_limit', sa.Integer, server_default='1000'),
        sa.Column('is_active', sa.Boolean, server_default='true', index=True),
        sa.Column('contract_start_date', sa.DateTime, nullable=True),
        sa.Column('contract_end_date', sa.DateTime, nullable=True),
        sa.Column('billing_email', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('settings', postgresql.JSONB, server_default='{}'),
    )
    op.create_index('ix_partner_active', 'partners', ['is_active'])

    # =========================================================================
    # PERMISSIONS TABLE
    # =========================================================================
    op.create_table(
        'permissions',
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String(50), nullable=False, index=True),
        sa.Column('min_hierarchy_level', sa.Integer, nullable=False, server_default='2'),
        sa.Column('tier_restriction', postgresql.JSONB, server_default='["starter", "professional", "enterprise"]'),
        sa.Column('is_enabled', sa.Boolean, server_default='true', index=True),
        sa.Column('is_system', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            'min_hierarchy_level >= 0 AND min_hierarchy_level <= 4',
            name='ck_permission_hierarchy'
        ),
    )
    op.create_index('ix_permission_category_enabled', 'permissions', ['category', 'is_enabled'])

    # =========================================================================
    # ROLE TEMPLATES TABLE
    # =========================================================================
    op.create_table(
        'role_templates',
        sa.Column('role_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(100), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('hierarchy_level', sa.Integer, nullable=False, server_default='2', index=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('partner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('partners.partner_id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('parent_role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('role_templates.role_id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_system', sa.Boolean, server_default='false', index=True),
        sa.Column('is_active', sa.Boolean, server_default='true', index=True),
        sa.Column('is_assignable', sa.Boolean, server_default='true'),
        sa.Column('display_order', sa.Integer, server_default='100'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint('code', 'firm_id', 'partner_id', name='uq_role_code_scope'),
        sa.CheckConstraint(
            'hierarchy_level >= 0 AND hierarchy_level <= 4',
            name='ck_role_hierarchy'
        ),
        sa.CheckConstraint(
            '(firm_id IS NULL OR partner_id IS NULL)',
            name='ck_role_scope'
        ),
    )
    op.create_index('ix_role_hierarchy_active', 'role_templates', ['hierarchy_level', 'is_active'])
    op.create_index('ix_role_firm_active', 'role_templates', ['firm_id', 'is_active'])

    # =========================================================================
    # ROLE PERMISSIONS TABLE
    # =========================================================================
    op.create_table(
        'role_permissions',
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('role_templates.role_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('permissions.permission_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('granted_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('granted_by', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_role_permission_role', 'role_permissions', ['role_id'])
    op.create_index('ix_role_permission_permission', 'role_permissions', ['permission_id'])

    # =========================================================================
    # USER ROLE ASSIGNMENTS TABLE
    # =========================================================================
    op.create_table(
        'user_role_assignments',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('role_templates.role_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('is_primary', sa.Boolean, server_default='false', index=True),
        sa.Column('assigned_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
    )
    op.create_index('ix_user_role_user', 'user_role_assignments', ['user_id'])
    op.create_index('ix_user_role_role', 'user_role_assignments', ['role_id'])
    op.create_index('ix_user_role_primary', 'user_role_assignments', ['user_id', 'is_primary'])

    # =========================================================================
    # USER PERMISSION OVERRIDES TABLE
    # =========================================================================
    op.create_table(
        'user_permission_overrides',
        sa.Column('override_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('permissions.permission_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('action', sa.String(20), nullable=False),  # 'grant' or 'revoke'
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint('user_id', 'permission_id', 'resource_type', 'resource_id', name='uq_user_permission_override'),
        sa.CheckConstraint("action IN ('grant', 'revoke')", name='ck_override_action'),
    )
    op.create_index('ix_override_user_action', 'user_permission_overrides', ['user_id', 'action'])
    op.create_index('ix_override_resource', 'user_permission_overrides', ['resource_type', 'resource_id'])

    # =========================================================================
    # RBAC AUDIT LOG TABLE
    # =========================================================================
    op.create_table(
        'rbac_audit_log',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime, server_default=sa.func.now(), nullable=False, index=True),
        sa.Column('action', sa.String(50), nullable=False, index=True),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('actor_type', sa.String(50), server_default='user'),
        sa.Column('target_user_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('target_role_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_permission_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('success', sa.Boolean, server_default='true'),
        sa.Column('denial_reason', sa.Text, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('request_id', sa.String(64), nullable=True, index=True),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
    )
    op.create_index('ix_rbac_audit_actor_time', 'rbac_audit_log', ['actor_id', 'timestamp'])
    op.create_index('ix_rbac_audit_target_time', 'rbac_audit_log', ['target_user_id', 'timestamp'])
    op.create_index('ix_rbac_audit_firm_time', 'rbac_audit_log', ['firm_id', 'timestamp'])
    op.create_index('ix_rbac_audit_action_success', 'rbac_audit_log', ['action', 'success'])

    # =========================================================================
    # PERMISSION CACHE VERSIONS TABLE
    # =========================================================================
    op.create_table(
        'permission_cache_versions',
        sa.Column('version_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scope', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('update_reason', sa.String(200), nullable=True),
    )

    # =========================================================================
    # PARTNER FIRMS TABLE
    # =========================================================================
    op.create_table(
        'partner_firms',
        sa.Column('partner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('partners.partner_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('joined_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('revenue_share_percent', sa.Integer, server_default='0'),
        sa.Column('notes', sa.Text, nullable=True),
    )
    op.create_index('ix_partner_firm_partner', 'partner_firms', ['partner_id'])
    op.create_index('ix_partner_firm_firm', 'partner_firms', ['firm_id'])

    # =========================================================================
    # PARTNER ADMINS TABLE
    # =========================================================================
    op.create_table(
        'partner_admins',
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('partner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('partners.partner_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('role', sa.String(50), server_default='partner_admin'),
        sa.Column('is_active', sa.Boolean, server_default='true', index=True),
        sa.Column('mfa_enabled', sa.Boolean, server_default='false'),
        sa.Column('mfa_secret', sa.String(100), nullable=True),
        sa.Column('last_login_at', sa.DateTime, nullable=True),
        sa.Column('last_login_ip', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_partner_admin_partner', 'partner_admins', ['partner_id', 'is_active'])

    # =========================================================================
    # CLIENT ACCESS GRANTS TABLE (Phase 2 - Resource-Level Access)
    # Note: client_id FK removed - clients table will be created in separate migration
    # =========================================================================
    op.create_table(
        'client_access_grants',
        sa.Column('grant_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),  # FK will be added when clients table exists
        sa.Column('access_level', sa.String(20), server_default='read'),
        sa.Column('granted_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('granted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('reason', sa.Text, nullable=True),
        sa.UniqueConstraint('user_id', 'client_id', name='uq_client_access_grant'),
        sa.CheckConstraint("access_level IN ('read', 'write', 'manage')", name='ck_access_level'),
    )
    op.create_index('ix_client_access_user', 'client_access_grants', ['user_id'])
    op.create_index('ix_client_access_client', 'client_access_grants', ['client_id'])

    # =========================================================================
    # ADD PARTNER_ID TO FIRMS TABLE
    # =========================================================================
    op.add_column('firms', sa.Column('partner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('partners.partner_id', ondelete='SET NULL'), nullable=True))
    op.add_column('firms', sa.Column('custom_roles_enabled', sa.Boolean, server_default='true'))
    op.add_column('firms', sa.Column('permission_version', sa.Integer, server_default='1'))
    op.create_index('ix_firm_partner', 'firms', ['partner_id'])


def downgrade() -> None:
    # Drop indexes and columns added to firms
    op.drop_index('ix_firm_partner', table_name='firms')
    op.drop_column('firms', 'permission_version')
    op.drop_column('firms', 'custom_roles_enabled')
    op.drop_column('firms', 'partner_id')

    # Drop tables in reverse order
    op.drop_table('client_access_grants')
    op.drop_table('partner_admins')
    op.drop_table('partner_firms')
    op.drop_table('permission_cache_versions')
    op.drop_table('rbac_audit_log')
    op.drop_table('user_permission_overrides')
    op.drop_table('user_role_assignments')
    op.drop_table('role_permissions')
    op.drop_table('role_templates')
    op.drop_table('permissions')
    op.drop_table('partners')
