"""Admin Panel Tables

Revision ID: 20260118_0001
Revises: 001
Create Date: 2026-01-18

Creates tables for the Admin Panel module:
- firms: CPA firm/tenant records
- firm_settings: Extended firm configuration
- users: Firm team members with RBAC
- invitations: Team member invitations
- subscription_plans: Pricing tiers
- subscriptions: Firm subscriptions
- invoices: Billing invoices
- usage_metrics: Platform usage tracking
- feature_flags: Feature flag management
- feature_usage: Feature usage tracking
- platform_admins: Internal admin users
- admin_audit_log: Admin action audit trail
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260118_0001'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # FIRMS TABLE
    # =========================================================================
    op.create_table(
        'firms',
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('legal_name', sa.String(255), nullable=True),
        sa.Column('ein', sa.String(20), nullable=True, unique=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('address_line1', sa.String(255), nullable=True),
        sa.Column('address_line2', sa.String(255), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(2), nullable=True),
        sa.Column('zip_code', sa.String(10), nullable=True),
        sa.Column('country', sa.String(50), server_default='USA'),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(7), server_default='#059669'),
        sa.Column('secondary_color', sa.String(7), server_default='#1e40af'),
        sa.Column('custom_domain', sa.String(255), nullable=True, unique=True),
        sa.Column('subscription_tier', sa.String(20), server_default='starter', index=True),
        sa.Column('subscription_status', sa.String(20), server_default='trial', index=True),
        sa.Column('trial_ends_at', sa.DateTime, nullable=True),
        sa.Column('max_team_members', sa.Integer, server_default='3'),
        sa.Column('max_clients', sa.Integer, server_default='100'),
        sa.Column('max_scenarios_per_month', sa.Integer, server_default='50'),
        sa.Column('max_api_calls_per_month', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='true', index=True),
        sa.Column('is_verified', sa.Boolean, server_default='false'),
        sa.Column('verification_date', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('onboarded_at', sa.DateTime, nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('settings', postgresql.JSONB, server_default='{}'),
        sa.CheckConstraint(
            "subscription_tier IN ('starter', 'professional', 'enterprise')",
            name='ck_firm_tier'
        ),
        sa.CheckConstraint(
            "subscription_status IN ('trial', 'active', 'past_due', 'cancelled', 'suspended')",
            name='ck_firm_status'
        ),
    )
    op.create_index('ix_firm_subscription', 'firms', ['subscription_tier', 'subscription_status'])
    op.create_index('ix_firm_created', 'firms', ['created_at'])

    # =========================================================================
    # FIRM SETTINGS TABLE
    # =========================================================================
    op.create_table(
        'firm_settings',
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('default_tax_year', sa.Integer, server_default='2025'),
        sa.Column('default_state', sa.String(2), nullable=True),
        sa.Column('timezone', sa.String(50), server_default='America/New_York'),
        sa.Column('date_format', sa.String(20), server_default='MM/DD/YYYY'),
        sa.Column('currency_display', sa.String(10), server_default='USD'),
        sa.Column('mfa_required', sa.Boolean, server_default='false'),
        sa.Column('session_timeout_minutes', sa.Integer, server_default='60'),
        sa.Column('ip_whitelist', postgresql.JSONB, server_default='[]'),
        sa.Column('password_expiry_days', sa.Integer, server_default='90'),
        sa.Column('email_notifications', sa.Boolean, server_default='true'),
        sa.Column('notification_preferences', postgresql.JSONB, server_default='{}'),
        sa.Column('auto_archive_days', sa.Integer, server_default='365'),
        sa.Column('require_reviewer_approval', sa.Boolean, server_default='true'),
        sa.Column('allow_self_review', sa.Boolean, server_default='false'),
        sa.Column('client_portal_enabled', sa.Boolean, server_default='true'),
        sa.Column('client_document_upload', sa.Boolean, server_default='true'),
        sa.Column('client_can_view_scenarios', sa.Boolean, server_default='false'),
        sa.Column('email_signature', sa.Text, nullable=True),
        sa.Column('disclaimer_text', sa.Text, nullable=True),
        sa.Column('welcome_message', sa.Text, nullable=True),
        sa.Column('integrations', postgresql.JSONB, server_default='{}'),
        sa.Column('webhook_url', sa.String(500), nullable=True),
        sa.Column('api_key_enabled', sa.Boolean, server_default='false'),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # =========================================================================
    # USERS TABLE
    # =========================================================================
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('job_title', sa.String(100), nullable=True),
        sa.Column('role', sa.String(20), nullable=False, index=True),
        sa.Column('custom_permissions', postgresql.JSONB, server_default='[]'),
        sa.Column('credentials', postgresql.JSONB, server_default='[]'),
        sa.Column('license_state', sa.String(2), nullable=True),
        sa.Column('license_number', sa.String(50), nullable=True),
        sa.Column('license_expiry', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='true', index=True),
        sa.Column('is_email_verified', sa.Boolean, server_default='false'),
        sa.Column('email_verified_at', sa.DateTime, nullable=True),
        sa.Column('mfa_enabled', sa.Boolean, server_default='false'),
        sa.Column('mfa_secret', sa.String(100), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer, server_default='0'),
        sa.Column('locked_until', sa.DateTime, nullable=True),
        sa.Column('password_changed_at', sa.DateTime, nullable=True),
        sa.Column('must_change_password', sa.Boolean, server_default='false'),
        sa.Column('last_login_at', sa.DateTime, nullable=True),
        sa.Column('last_login_ip', sa.String(45), nullable=True),
        sa.Column('last_activity_at', sa.DateTime, nullable=True),
        sa.Column('current_session_id', sa.String(64), nullable=True),
        sa.Column('notification_preferences', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=True),
        sa.CheckConstraint('failed_login_attempts >= 0', name='ck_user_login_attempts'),
    )
    op.create_index('ix_user_firm_role', 'users', ['firm_id', 'role'])
    op.create_index('ix_user_firm_active', 'users', ['firm_id', 'is_active'])
    op.create_index('ix_user_last_activity', 'users', ['last_activity_at'])

    # =========================================================================
    # INVITATIONS TABLE
    # =========================================================================
    op.create_table(
        'invitations',
        sa.Column('invitation_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('email', sa.String(255), nullable=False, index=True),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('token', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False, index=True),
        sa.Column('personal_message', sa.String(500), nullable=True),
        sa.Column('invited_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('accepted_at', sa.DateTime, nullable=True),
        sa.Column('accepted_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('revoked_at', sa.DateTime, nullable=True),
        sa.Column('revoked_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('email_sent_at', sa.DateTime, nullable=True),
        sa.Column('email_opened_at', sa.DateTime, nullable=True),
        sa.Column('link_clicked_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_invitation_token', 'invitations', ['token'])
    op.create_index('ix_invitation_firm_status', 'invitations', ['firm_id', 'status'])
    op.create_index('ix_invitation_email_firm', 'invitations', ['email', 'firm_id'])

    # =========================================================================
    # SUBSCRIPTION PLANS TABLE
    # =========================================================================
    op.create_table(
        'subscription_plans',
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('monthly_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('annual_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), server_default='USD'),
        sa.Column('max_team_members', sa.Integer, nullable=True),
        sa.Column('max_clients', sa.Integer, nullable=True),
        sa.Column('max_scenarios_per_month', sa.Integer, nullable=True),
        sa.Column('max_api_calls_per_month', sa.Integer, nullable=True),
        sa.Column('max_document_storage_gb', sa.Integer, server_default='10'),
        sa.Column('features', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean, server_default='true', index=True),
        sa.Column('is_public', sa.Boolean, server_default='true'),
        sa.Column('display_order', sa.Integer, server_default='0'),
        sa.Column('highlight_text', sa.String(50), nullable=True),
        sa.Column('stripe_price_id_monthly', sa.String(255), nullable=True),
        sa.Column('stripe_price_id_annual', sa.String(255), nullable=True),
        sa.Column('stripe_product_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint('monthly_price >= 0', name='ck_plan_monthly_price'),
        sa.CheckConstraint('annual_price >= 0', name='ck_plan_annual_price'),
    )
    op.create_index('ix_plan_code', 'subscription_plans', ['code'])
    op.create_index('ix_plan_active_public', 'subscription_plans', ['is_active', 'is_public'])

    # =========================================================================
    # SUBSCRIPTIONS TABLE
    # =========================================================================
    op.create_table(
        'subscriptions',
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscription_plans.plan_id'), nullable=False),
        sa.Column('billing_cycle', sa.String(20), server_default='monthly'),
        sa.Column('current_period_start', sa.DateTime, nullable=True),
        sa.Column('current_period_end', sa.DateTime, nullable=True),
        sa.Column('next_billing_date', sa.DateTime, nullable=True),
        sa.Column('status', sa.String(20), server_default='trialing', nullable=False, index=True),
        sa.Column('trial_end', sa.DateTime, nullable=True),
        sa.Column('cancelled_at', sa.DateTime, nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean, server_default='false'),
        sa.Column('cancel_reason', sa.Text, nullable=True),
        sa.Column('cancelled_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('payment_method_type', sa.String(20), nullable=True),
        sa.Column('payment_method_last4', sa.String(4), nullable=True),
        sa.Column('payment_method_brand', sa.String(20), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True, unique=True),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_subscription_firm_status', 'subscriptions', ['firm_id', 'status'])
    op.create_index('ix_subscription_next_billing', 'subscriptions', ['next_billing_date'])
    op.create_index('ix_subscription_stripe', 'subscriptions', ['stripe_subscription_id'])

    # =========================================================================
    # INVOICES TABLE
    # =========================================================================
    op.create_table(
        'invoices',
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.subscription_id'), nullable=True),
        sa.Column('invoice_number', sa.String(50), nullable=False, unique=True),
        sa.Column('subtotal', sa.Numeric(10, 2), nullable=False),
        sa.Column('tax', sa.Numeric(10, 2), server_default='0'),
        sa.Column('discount', sa.Numeric(10, 2), server_default='0'),
        sa.Column('amount_due', sa.Numeric(10, 2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(10, 2), server_default='0'),
        sa.Column('currency', sa.String(3), server_default='USD'),
        sa.Column('period_start', sa.DateTime, nullable=True),
        sa.Column('period_end', sa.DateTime, nullable=True),
        sa.Column('status', sa.String(20), server_default='draft', nullable=False, index=True),
        sa.Column('due_date', sa.DateTime, nullable=True),
        sa.Column('paid_at', sa.DateTime, nullable=True),
        sa.Column('voided_at', sa.DateTime, nullable=True),
        sa.Column('line_items', postgresql.JSONB, server_default='[]'),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('payment_intent_id', sa.String(255), nullable=True),
        sa.Column('stripe_invoice_id', sa.String(255), nullable=True, unique=True),
        sa.Column('invoice_pdf_url', sa.String(500), nullable=True),
        sa.Column('hosted_invoice_url', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('internal_notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint('amount_due >= 0', name='ck_invoice_amount_due'),
        sa.CheckConstraint('amount_paid >= 0', name='ck_invoice_amount_paid'),
    )
    op.create_index('ix_invoice_firm_status', 'invoices', ['firm_id', 'status'])
    op.create_index('ix_invoice_due_date', 'invoices', ['due_date'])
    op.create_index('ix_invoice_stripe', 'invoices', ['stripe_invoice_id'])

    # =========================================================================
    # USAGE METRICS TABLE
    # =========================================================================
    op.create_table(
        'usage_metrics',
        sa.Column('metric_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('period_start', sa.Date, nullable=False, index=True),
        sa.Column('period_end', sa.Date, nullable=False),
        sa.Column('period_type', sa.String(20), server_default='monthly'),
        sa.Column('returns_created', sa.Integer, server_default='0'),
        sa.Column('returns_filed', sa.Integer, server_default='0'),
        sa.Column('returns_amended', sa.Integer, server_default='0'),
        sa.Column('scenarios_analyzed', sa.Integer, server_default='0'),
        sa.Column('optimization_runs', sa.Integer, server_default='0'),
        sa.Column('reports_generated', sa.Integer, server_default='0'),
        sa.Column('documents_uploaded', sa.Integer, server_default='0'),
        sa.Column('documents_processed', sa.Integer, server_default='0'),
        sa.Column('ocr_pages_processed', sa.Integer, server_default='0'),
        sa.Column('storage_used_bytes', sa.Integer, server_default='0'),
        sa.Column('api_calls', sa.Integer, server_default='0'),
        sa.Column('api_errors', sa.Integer, server_default='0'),
        sa.Column('active_team_members', sa.Integer, server_default='0'),
        sa.Column('total_logins', sa.Integer, server_default='0'),
        sa.Column('unique_users_active', sa.Integer, server_default='0'),
        sa.Column('active_clients', sa.Integer, server_default='0'),
        sa.Column('new_clients', sa.Integer, server_default='0'),
        sa.Column('clients_archived', sa.Integer, server_default='0'),
        sa.Column('tier1_returns', sa.Integer, server_default='0'),
        sa.Column('tier2_returns', sa.Integer, server_default='0'),
        sa.Column('tier3_returns', sa.Integer, server_default='0'),
        sa.Column('tier4_returns', sa.Integer, server_default='0'),
        sa.Column('tier5_returns', sa.Integer, server_default='0'),
        sa.Column('leads_generated', sa.Integer, server_default='0'),
        sa.Column('leads_converted', sa.Integer, server_default='0'),
        sa.Column('engagement_letters_sent', sa.Integer, server_default='0'),
        sa.Column('engagement_letters_signed', sa.Integer, server_default='0'),
        sa.Column('breakdown', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('firm_id', 'period_start', 'period_end', name='uq_usage_firm_period'),
    )
    op.create_index('ix_usage_firm_period', 'usage_metrics', ['firm_id', 'period_start'])
    op.create_index('ix_usage_period_type', 'usage_metrics', ['period_type', 'period_start'])

    # =========================================================================
    # FEATURE FLAGS TABLE
    # =========================================================================
    op.create_table(
        'feature_flags',
        sa.Column('flag_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('feature_key', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String(50), nullable=True, index=True),
        sa.Column('is_enabled_globally', sa.Boolean, server_default='false', index=True),
        sa.Column('min_tier', sa.String(20), nullable=True),
        sa.Column('rollout_percentage', sa.Integer, server_default='0'),
        sa.Column('enabled_firm_ids', postgresql.JSONB, server_default='[]'),
        sa.Column('disabled_firm_ids', postgresql.JSONB, server_default='[]'),
        sa.Column('owner', sa.String(100), nullable=True),
        sa.Column('jira_ticket', sa.String(50), nullable=True),
        sa.Column('documentation_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('deprecated_at', sa.DateTime, nullable=True),
        sa.Column('removal_date', sa.DateTime, nullable=True),
    )

    # =========================================================================
    # FEATURE USAGE TABLE
    # =========================================================================
    op.create_table(
        'feature_usage',
        sa.Column('usage_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('firms.firm_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('feature_key', sa.String(100), sa.ForeignKey('feature_flags.feature_key', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('used_at', sa.DateTime, server_default=sa.func.now(), nullable=False, index=True),
        sa.Column('context', postgresql.JSONB, nullable=True),
    )
    op.create_index('ix_feature_usage_firm_key', 'feature_usage', ['firm_id', 'feature_key'])
    op.create_index('ix_feature_usage_date', 'feature_usage', ['used_at'])

    # =========================================================================
    # PLATFORM ADMINS TABLE
    # =========================================================================
    op.create_table(
        'platform_admins',
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, index=True),
        sa.Column('custom_permissions', postgresql.JSONB, server_default='[]'),
        sa.Column('mfa_enabled', sa.Boolean, server_default='true', nullable=False),
        sa.Column('mfa_secret', sa.String(100), nullable=True),
        sa.Column('mfa_backup_codes', postgresql.JSONB, nullable=True),
        sa.Column('failed_login_attempts', sa.Integer, server_default='0'),
        sa.Column('locked_until', sa.DateTime, nullable=True),
        sa.Column('password_changed_at', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='true', index=True),
        sa.Column('deactivated_at', sa.DateTime, nullable=True),
        sa.Column('deactivated_reason', sa.String(255), nullable=True),
        sa.Column('last_login_at', sa.DateTime, nullable=True),
        sa.Column('last_login_ip', sa.String(45), nullable=True),
        sa.Column('last_activity_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('platform_admins.admin_id'), nullable=True),
    )

    # =========================================================================
    # ADMIN AUDIT LOG TABLE
    # =========================================================================
    op.create_table(
        'admin_audit_log',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('platform_admins.admin_id'), nullable=False, index=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('action_category', sa.String(50), nullable=True),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('old_values', postgresql.JSONB, nullable=True),
        sa.Column('new_values', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('request_id', sa.String(64), nullable=True),
        sa.Column('impersonating_firm_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('impersonating_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False, index=True),
    )
    op.create_index('ix_admin_audit_action', 'admin_audit_log', ['action', 'created_at'])
    op.create_index('ix_admin_audit_resource', 'admin_audit_log', ['resource_type', 'resource_id'])
    op.create_index('ix_admin_audit_category', 'admin_audit_log', ['action_category', 'created_at'])

    # =========================================================================
    # SEED DEFAULT SUBSCRIPTION PLANS
    # =========================================================================
    op.execute("""
        INSERT INTO subscription_plans (plan_id, name, code, description, monthly_price, annual_price,
            max_team_members, max_clients, max_scenarios_per_month, max_api_calls_per_month,
            features, is_active, is_public, display_order)
        VALUES
        (gen_random_uuid(), 'Starter', 'starter', 'Perfect for solo practitioners', 199.00, 1990.00,
            3, 100, 50, NULL,
            '{"scenario_analysis": true, "multi_state": false, "api_access": false, "white_label": false, "priority_support": false, "custom_domain": false, "sso": false, "audit_log_export": false}',
            true, true, 1),
        (gen_random_uuid(), 'Professional', 'professional', 'For growing practices', 499.00, 4990.00,
            10, 500, 500, NULL,
            '{"scenario_analysis": true, "multi_state": true, "api_access": false, "white_label": false, "priority_support": true, "custom_domain": false, "sso": false, "audit_log_export": true}',
            true, true, 2),
        (gen_random_uuid(), 'Enterprise', 'enterprise', 'For large firms', 999.00, 9990.00,
            NULL, NULL, NULL, 100000,
            '{"scenario_analysis": true, "multi_state": true, "api_access": true, "white_label": true, "priority_support": true, "custom_domain": true, "sso": true, "audit_log_export": true}',
            true, true, 3)
    """)


def downgrade() -> None:
    op.drop_table('admin_audit_log')
    op.drop_table('platform_admins')
    op.drop_table('feature_usage')
    op.drop_table('feature_flags')
    op.drop_table('usage_metrics')
    op.drop_table('invoices')
    op.drop_table('subscriptions')
    op.drop_table('subscription_plans')
    op.drop_table('invitations')
    op.drop_table('users')
    op.drop_table('firm_settings')
    op.drop_table('firms')
