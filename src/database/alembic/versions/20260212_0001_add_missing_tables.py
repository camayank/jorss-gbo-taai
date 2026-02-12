"""Add missing tables for production deployment

Revision ID: 20260212_0001
Revises: 20260206_0002
Create Date: 2026-02-12

Adds tables that were referenced in code but not created:
- scenarios: Tax scenario modeling and comparisons
- scenario_comparisons: Side-by-side scenario comparisons
- domain_events: Event sourcing for domain events
- session_transfers: Anonymous to authenticated session transfers
- staff_assignments: CPA staff to client assignments
- billing_subscriptions: Firm subscription data (replaces in-memory)
- billing_invoices: Invoice records (replaces in-memory)
- audit_logs: Audit trail records (replaces in-memory)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260212_0001'
down_revision = '20260206_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create missing tables for production."""

    # ==========================================================================
    # SCENARIOS - Tax scenario modeling
    # ==========================================================================

    op.create_table(
        'scenarios',
        sa.Column('scenario_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('scenario_type', sa.String(50), nullable=False),  # 'what_if', 'optimization', 'projection'
        sa.Column('status', sa.String(20), default='draft'),  # 'draft', 'calculated', 'saved'
        sa.Column('is_recommended', sa.Boolean, default=False),
        sa.Column('scenario_data', postgresql.JSONB, nullable=True),
        sa.Column('result_data', postgresql.JSONB, nullable=True),
        sa.Column('tax_liability', sa.Numeric(12, 2), nullable=True),
        sa.Column('refund_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=True),
    )

    op.create_index('idx_scenarios_return_id', 'scenarios', ['return_id'])
    op.create_index('idx_scenarios_tenant_id', 'scenarios', ['tenant_id'])
    op.create_index('idx_scenarios_type', 'scenarios', ['scenario_type'])

    # ==========================================================================
    # SCENARIO COMPARISONS - Side-by-side comparison
    # ==========================================================================

    op.create_table(
        'scenario_comparisons',
        sa.Column('comparison_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(50), nullable=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('scenario_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('comparison_data', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(100), nullable=True),
    )

    op.create_index('idx_scenario_comparisons_return_id', 'scenario_comparisons', ['return_id'])

    # ==========================================================================
    # DOMAIN EVENTS - Event sourcing
    # ==========================================================================

    op.create_table(
        'domain_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('stream_id', sa.String(100), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_version', sa.Integer, nullable=False, default=1),
        sa.Column('aggregate_type', sa.String(100), nullable=True),
        sa.Column('aggregate_id', sa.String(100), nullable=True),
        sa.Column('event_data', postgresql.JSONB, nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('occurred_at', sa.DateTime, nullable=False),
        sa.Column('stored_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('correlation_id', sa.String(100), nullable=True),
        sa.Column('causation_id', sa.String(100), nullable=True),
    )

    op.create_index('idx_domain_events_stream', 'domain_events', ['stream_id', 'event_version'])
    op.create_index('idx_domain_events_aggregate', 'domain_events', ['aggregate_type', 'aggregate_id'])
    op.create_index('idx_domain_events_type', 'domain_events', ['event_type'])
    op.create_index('idx_domain_events_occurred', 'domain_events', ['occurred_at'])

    # ==========================================================================
    # SESSION TRANSFERS - Anonymous to authenticated
    # ==========================================================================

    op.create_table(
        'session_transfers',
        sa.Column('transfer_id', sa.String(50), primary_key=True),
        sa.Column('session_id', sa.String(50), nullable=False),
        sa.Column('from_anonymous', sa.Boolean, default=True),
        sa.Column('to_user_id', sa.String(100), nullable=False),
        sa.Column('transferred_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
    )

    op.create_index('idx_session_transfers_session', 'session_transfers', ['session_id'])
    op.create_index('idx_session_transfers_user', 'session_transfers', ['to_user_id'])

    # ==========================================================================
    # STAFF ASSIGNMENTS - CPA staff to client/return assignments
    # ==========================================================================

    op.create_table(
        'staff_assignments',
        sa.Column('assignment_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('staff_id', sa.String(100), nullable=False),
        sa.Column('staff_name', sa.String(255), nullable=True),
        sa.Column('staff_email', sa.String(255), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('client_id', sa.String(100), nullable=True),
        sa.Column('return_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('assignment_type', sa.String(50), default='primary'),  # 'primary', 'reviewer', 'support'
        sa.Column('assigned_by', sa.String(100), nullable=True),
        sa.Column('assigned_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('unassigned_at', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('notes', sa.Text, nullable=True),
    )

    op.create_index('idx_staff_assignments_tenant', 'staff_assignments', ['tenant_id'])
    op.create_index('idx_staff_assignments_staff', 'staff_assignments', ['tenant_id', 'staff_id'])
    op.create_index('idx_staff_assignments_session', 'staff_assignments', ['session_id'])
    op.create_index('idx_staff_assignments_active', 'staff_assignments', ['tenant_id', 'is_active'])

    # ==========================================================================
    # BILLING SUBSCRIPTIONS - Replace in-memory billing storage
    # ==========================================================================

    op.create_table(
        'billing_subscriptions',
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', sa.String(50), nullable=False),
        sa.Column('plan_name', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),  # 'active', 'canceled', 'past_due', 'trialing'
        sa.Column('billing_cycle', sa.String(20), default='monthly'),  # 'monthly', 'annual'
        sa.Column('seats_included', sa.Integer, default=1),
        sa.Column('seats_used', sa.Integer, default=0),
        sa.Column('price_per_month', sa.Numeric(10, 2), nullable=True),
        sa.Column('price_per_year', sa.Numeric(10, 2), nullable=True),
        sa.Column('current_period_start', sa.DateTime, nullable=True),
        sa.Column('current_period_end', sa.DateTime, nullable=True),
        sa.Column('trial_end', sa.DateTime, nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean, default=False),
        sa.Column('canceled_at', sa.DateTime, nullable=True),
        sa.Column('stripe_subscription_id', sa.String(100), nullable=True),
        sa.Column('stripe_customer_id', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('idx_billing_subscriptions_firm', 'billing_subscriptions', ['firm_id'])
    op.create_index('idx_billing_subscriptions_status', 'billing_subscriptions', ['status'])
    op.create_index('idx_billing_subscriptions_stripe', 'billing_subscriptions', ['stripe_subscription_id'])

    # ==========================================================================
    # BILLING INVOICES - Replace in-memory invoice storage
    # ==========================================================================

    op.create_table(
        'billing_invoices',
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('invoice_number', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),  # 'draft', 'open', 'paid', 'void', 'uncollectible'
        sa.Column('currency', sa.String(3), default='USD'),
        sa.Column('subtotal', sa.Numeric(12, 2), nullable=False),
        sa.Column('tax', sa.Numeric(12, 2), default=0),
        sa.Column('total', sa.Numeric(12, 2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(12, 2), default=0),
        sa.Column('amount_due', sa.Numeric(12, 2), nullable=True),
        sa.Column('line_items', postgresql.JSONB, nullable=True),
        sa.Column('period_start', sa.DateTime, nullable=True),
        sa.Column('period_end', sa.DateTime, nullable=True),
        sa.Column('due_date', sa.DateTime, nullable=True),
        sa.Column('paid_at', sa.DateTime, nullable=True),
        sa.Column('stripe_invoice_id', sa.String(100), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(100), nullable=True),
        sa.Column('pdf_url', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('idx_billing_invoices_firm', 'billing_invoices', ['firm_id'])
    op.create_index('idx_billing_invoices_subscription', 'billing_invoices', ['subscription_id'])
    op.create_index('idx_billing_invoices_status', 'billing_invoices', ['status'])
    op.create_index('idx_billing_invoices_stripe', 'billing_invoices', ['stripe_invoice_id'])

    # ==========================================================================
    # AUDIT LOGS - Replace in-memory audit storage
    # ==========================================================================

    op.create_table(
        'platform_audit_logs',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', sa.String(50), nullable=True),
        sa.Column('user_id', sa.String(100), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('user_role', sa.String(50), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('details', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), default='success'),  # 'success', 'failure', 'error'
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('integrity_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index('idx_audit_logs_tenant', 'platform_audit_logs', ['tenant_id'])
    op.create_index('idx_audit_logs_user', 'platform_audit_logs', ['user_id'])
    op.create_index('idx_audit_logs_action', 'platform_audit_logs', ['action'])
    op.create_index('idx_audit_logs_resource', 'platform_audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_logs_created', 'platform_audit_logs', ['created_at'])
    op.create_index('idx_audit_logs_date_range', 'platform_audit_logs', ['tenant_id', 'created_at'])

    # ==========================================================================
    # IMPERSONATION SESSIONS - Replace in-memory impersonation storage
    # ==========================================================================

    op.create_table(
        'impersonation_sessions',
        sa.Column('session_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('admin_user_id', sa.String(100), nullable=False),
        sa.Column('admin_email', sa.String(255), nullable=True),
        sa.Column('target_firm_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_user_id', sa.String(100), nullable=True),
        sa.Column('target_email', sa.String(255), nullable=True),
        sa.Column('reason', sa.String(50), nullable=False),
        sa.Column('reason_details', sa.Text, nullable=True),
        sa.Column('ticket_id', sa.String(100), nullable=True),
        sa.Column('token', sa.String(255), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('ended_at', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('action_count', sa.Integer, default=0),
    )

    op.create_index('idx_impersonation_admin', 'impersonation_sessions', ['admin_user_id'])
    op.create_index('idx_impersonation_firm', 'impersonation_sessions', ['target_firm_id'])
    op.create_index('idx_impersonation_active', 'impersonation_sessions', ['is_active', 'expires_at'])
    op.create_index('idx_impersonation_token', 'impersonation_sessions', ['token'], unique=True)

    # ==========================================================================
    # CLIENT TOKENS - Replace in-memory token storage for client portal
    # ==========================================================================

    op.create_table(
        'client_auth_tokens',
        sa.Column('token_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('client_id', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('token_type', sa.String(20), default='magic_link'),  # 'magic_link', 'session'
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('used_at', sa.DateTime, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('is_valid', sa.Boolean, default=True),
    )

    op.create_index('idx_client_tokens_hash', 'client_auth_tokens', ['token_hash'])
    op.create_index('idx_client_tokens_email', 'client_auth_tokens', ['email'])
    op.create_index('idx_client_tokens_valid', 'client_auth_tokens', ['is_valid', 'expires_at'])


def downgrade() -> None:
    """Drop all created tables."""
    op.drop_table('client_auth_tokens')
    op.drop_table('impersonation_sessions')
    op.drop_table('platform_audit_logs')
    op.drop_table('billing_invoices')
    op.drop_table('billing_subscriptions')
    op.drop_table('staff_assignments')
    op.drop_table('session_transfers')
    op.drop_table('domain_events')
    op.drop_table('scenario_comparisons')
    op.drop_table('scenarios')
