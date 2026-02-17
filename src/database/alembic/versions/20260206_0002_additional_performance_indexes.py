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
import sqlalchemy as sa
from typing import Dict, Optional


# revision identifiers, used by Alembic.
revision = '20260206_0002'
down_revision = '20260206_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add additional performance indexes."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    def create_index_if_available(
        index_name: str,
        table_name: str,
        columns: list[str],
        *,
        unique: bool = False,
        postgresql_ops: Optional[Dict[str, str]] = None,
    ) -> None:
        if table_name not in existing_tables:
            return

        existing_indexes = {ix["name"] for ix in inspector.get_indexes(table_name)}
        if index_name in existing_indexes:
            return

        table_columns = {col["name"] for col in inspector.get_columns(table_name)}
        if not all(column in table_columns for column in columns):
            return

        kwargs = {"unique": unique}
        if postgresql_ops:
            kwargs["postgresql_ops"] = postgresql_ops
        op.create_index(
            index_name,
            table_name,
            columns,
            **kwargs,
        )

    # ==========================================================================
    # USERS - Login and lookup performance
    # ==========================================================================

    # Email lookup for login (if not already indexed)
    # Supports: "Find user by email for authentication"
    create_index_if_available(
        'idx_users_email_lower',
        'users',
        ['email'],
        unique=True,
        postgresql_ops={'email': 'text_pattern_ops'},
    )

    # User status for active user queries
    create_index_if_available(
        'idx_users_active_firm',
        'users',
        ['firm_id', 'is_active'],
    )

    # ==========================================================================
    # SESSION STATES - Cleanup and expiration
    # ==========================================================================

    # Expiration index for session cleanup jobs
    # Supports: "Find all expired sessions for cleanup"
    create_index_if_available(
        'idx_session_states_expires',
        'session_states',
        ['expires_at'],
    )

    # User session lookup
    create_index_if_available(
        'idx_session_states_user',
        'session_states',
        ['user_id', 'tenant_id'],
    )

    # ==========================================================================
    # LEADS - CPA lead management
    # ==========================================================================

    # Lead status for pipeline queries
    create_index_if_available(
        'idx_leads_status_created',
        'leads',
        ['status', 'created_at'],
    )

    # Lead assignment for CPA workload
    create_index_if_available(
        'idx_leads_assigned_cpa',
        'leads',
        ['assigned_cpa_id', 'status'],
    )

    # ==========================================================================
    # MFA CREDENTIALS - Security lookup performance
    # ==========================================================================

    # Already covered in 20260206_0001, but add if missing
    create_index_if_available(
        'idx_mfa_creds_user_active',
        'mfa_credentials',
        ['user_id', 'is_active'],
    )

    # ==========================================================================
    # DOCUMENT PROCESSING - OCR queue performance
    # ==========================================================================

    # Document status for processing queue
    create_index_if_available(
        'idx_doc_processing_status',
        'document_processing',
        ['status', 'created_at'],
    )

    # ==========================================================================
    # AUDIT TRAILS - Compliance queries
    # ==========================================================================

    # Return-based audit lookups
    create_index_if_available(
        'idx_audit_log_return',
        'audit_logs',
        ['return_id', 'timestamp'],
    )


def downgrade() -> None:
    """Remove additional performance indexes."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

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
        if table_name not in inspector.get_table_names():
            continue
        table_indexes = {ix["name"] for ix in inspector.get_indexes(table_name)}
        if index_name in table_indexes:
            op.drop_index(index_name, table_name=table_name)
