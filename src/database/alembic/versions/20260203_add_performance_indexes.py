"""Add Performance Indexes

Revision ID: 20260203_0001
Revises: 20260129_0001
Create Date: 2026-02-03

Adds composite indexes for common query patterns:
- tax_returns: status + year + created_at (dashboard queries)
- income_records: return_id + source_type + gross_amount (income summaries)
- w2_records: return_id + state_code (state tax calculations)
- audit_logs: timestamp + event_type (audit queries)
- client_sessions: status + preparer_id + last_accessed (workload management)

These indexes significantly improve performance for:
1. Dashboard filtering (status/year combinations)
2. Income aggregation queries
3. State-specific reporting
4. Audit log analysis
5. Preparer workload views
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '20260203_0001'
down_revision = '20260129_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance indexes for common query patterns."""

    # ==========================================================================
    # TAX RETURNS - Dashboard filtering and status queries
    # ==========================================================================

    # Index for dashboard queries filtering by status and tax year
    # Supports: "Show all 2025 returns in review status"
    op.create_index(
        'idx_returns_status_year',
        'tax_returns',
        ['status', 'tax_year', 'created_at'],
        unique=False
    )

    # Index for preparer workload queries
    # Supports: "Show all returns assigned to preparer X"
    op.create_index(
        'idx_returns_preparer_status',
        'tax_returns',
        ['preparer_id', 'status'],
        unique=False,
        postgresql_where="preparer_id IS NOT NULL"
    )

    # Index for client return lookups
    # Supports: "Show all returns for taxpayer X"
    op.create_index(
        'idx_returns_taxpayer_year',
        'tax_returns',
        ['taxpayer_id', 'tax_year'],
        unique=False
    )

    # ==========================================================================
    # INCOME RECORDS - Income summaries and aggregation
    # ==========================================================================

    # Index for income aggregation by return and source
    # Supports: "Sum all W-2 income for return X"
    op.create_index(
        'idx_income_return_source',
        'income_records',
        ['return_id', 'source_type', 'gross_amount'],
        unique=False
    )

    # ==========================================================================
    # W2 RECORDS - State tax calculations
    # ==========================================================================

    # Index for state-specific W-2 queries
    # Supports: "Get all CA W-2s for return X"
    op.create_index(
        'idx_w2_return_state',
        'w2_records',
        ['return_id', 'state_code'],
        unique=False
    )

    # ==========================================================================
    # AUDIT LOGS - Compliance and analysis queries
    # ==========================================================================

    # Index for audit log time-based queries
    # Supports: "Show all login events in the last 24 hours"
    op.create_index(
        'idx_audit_timestamp_type',
        'audit_logs',
        ['timestamp', 'event_type'],
        unique=False
    )

    # Index for user-specific audit queries
    # Supports: "Show all actions by user X"
    op.create_index(
        'idx_audit_user_timestamp',
        'audit_logs',
        ['user_id', 'timestamp'],
        unique=False,
        postgresql_where="user_id IS NOT NULL"
    )

    # ==========================================================================
    # CLIENT SESSIONS - Workload management
    # ==========================================================================

    # Index for active session queries by preparer
    # Supports: "Show all active sessions for preparer X"
    op.create_index(
        'idx_sessions_status_preparer',
        'client_sessions',
        ['status', 'preparer_id', 'last_accessed_at'],
        unique=False
    )

    # Index for session timeout cleanup
    # Supports: "Find all sessions not accessed in 30 days"
    op.create_index(
        'idx_sessions_last_accessed',
        'client_sessions',
        ['last_accessed_at'],
        unique=False
    )

    # ==========================================================================
    # DOCUMENTS - Document retrieval and status
    # ==========================================================================

    # Index for document listing with status
    # Supports: "Show all pending documents for session X"
    op.create_index(
        'idx_documents_session_status',
        'documents',
        ['session_id', 'status', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes."""

    # Documents
    op.drop_index('idx_documents_session_status', table_name='documents')

    # Client sessions
    op.drop_index('idx_sessions_last_accessed', table_name='client_sessions')
    op.drop_index('idx_sessions_status_preparer', table_name='client_sessions')

    # Audit logs
    op.drop_index('idx_audit_user_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_timestamp_type', table_name='audit_logs')

    # W2 records
    op.drop_index('idx_w2_return_state', table_name='w2_records')

    # Income records
    op.drop_index('idx_income_return_source', table_name='income_records')

    # Tax returns
    op.drop_index('idx_returns_taxpayer_year', table_name='tax_returns')
    op.drop_index('idx_returns_preparer_status', table_name='tax_returns')
    op.drop_index('idx_returns_status_year', table_name='tax_returns')
