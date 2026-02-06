"""Add additional performance indexes

Revision ID: 20260206_0002
Revises: 20260206_0001
Create Date: 2026-02-06

Adds additional indexes identified in production audit:
- users: email lookups for login
- session_states: expiration cleanup queries
- leads: CPA lead management queries
- mfa_credentials: MFA lookup performance

These indexes address performance gaps identified in the backend audit.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '20260206_0002'
down_revision = '20260206_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add additional performance indexes."""

    # ==========================================================================
    # USERS - Login and lookup performance
    # ==========================================================================

    # Email lookup for login (if not already indexed)
    # Supports: "Find user by email for authentication"
    try:
        op.create_index(
            'idx_users_email_lower',
            'users',
            ['email'],
            unique=True,
            postgresql_ops={'email': 'text_pattern_ops'},
            if_not_exists=True
        )
    except Exception:
        pass  # Index may already exist

    # User status for active user queries
    try:
        op.create_index(
            'idx_users_active_firm',
            'users',
            ['firm_id', 'is_active'],
            if_not_exists=True
        )
    except Exception:
        pass

    # ==========================================================================
    # SESSION STATES - Cleanup and expiration
    # ==========================================================================

    # Expiration index for session cleanup jobs
    # Supports: "Find all expired sessions for cleanup"
    try:
        op.create_index(
            'idx_session_states_expires',
            'session_states',
            ['expires_at'],
            if_not_exists=True
        )
    except Exception:
        pass

    # User session lookup
    try:
        op.create_index(
            'idx_session_states_user',
            'session_states',
            ['user_id', 'tenant_id'],
            if_not_exists=True
        )
    except Exception:
        pass

    # ==========================================================================
    # LEADS - CPA lead management
    # ==========================================================================

    # Lead status for pipeline queries
    try:
        op.create_index(
            'idx_leads_status_created',
            'leads',
            ['status', 'created_at'],
            if_not_exists=True
        )
    except Exception:
        pass  # Table may not exist

    # Lead assignment for CPA workload
    try:
        op.create_index(
            'idx_leads_assigned_cpa',
            'leads',
            ['assigned_cpa_id', 'status'],
            if_not_exists=True
        )
    except Exception:
        pass

    # ==========================================================================
    # MFA CREDENTIALS - Security lookup performance
    # ==========================================================================

    # Already covered in 20260206_0001, but add if missing
    try:
        op.create_index(
            'idx_mfa_creds_user_active',
            'mfa_credentials',
            ['user_id', 'is_active'],
            if_not_exists=True
        )
    except Exception:
        pass

    # ==========================================================================
    # DOCUMENT PROCESSING - OCR queue performance
    # ==========================================================================

    # Document status for processing queue
    try:
        op.create_index(
            'idx_doc_processing_status',
            'document_processing',
            ['status', 'created_at'],
            if_not_exists=True
        )
    except Exception:
        pass

    # ==========================================================================
    # AUDIT TRAILS - Compliance queries
    # ==========================================================================

    # Return-based audit lookups
    try:
        op.create_index(
            'idx_audit_log_return',
            'audit_logs',
            ['return_id', 'timestamp'],
            if_not_exists=True
        )
    except Exception:
        pass


def downgrade() -> None:
    """Remove additional performance indexes."""

    # Safe drops with error handling
    indexes_to_drop = [
        ('idx_audit_log_return', 'audit_logs'),
        ('idx_doc_processing_status', 'document_processing'),
        ('idx_mfa_creds_user_active', 'mfa_credentials'),
        ('idx_leads_assigned_cpa', 'leads'),
        ('idx_leads_status_created', 'leads'),
        ('idx_session_states_user', 'session_states'),
        ('idx_session_states_expires', 'session_states'),
        ('idx_users_active_firm', 'users'),
        ('idx_users_email_lower', 'users'),
    ]

    for index_name, table_name in indexes_to_drop:
        try:
            op.drop_index(index_name, table_name=table_name)
        except Exception:
            pass  # Index may not exist
