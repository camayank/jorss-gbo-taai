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
import sqlalchemy as sa
from typing import Optional


# revision identifiers, used by Alembic.
revision = '20260203_0001'
down_revision = '20260129_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance indexes for common query patterns."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    def create_index_if_available(
        index_name: str,
        table_name: str,
        columns: list[str],
        *,
        postgresql_where: Optional[str] = None,
    ) -> None:
        if table_name not in existing_tables:
            return
        table_columns = {col["name"] for col in inspector.get_columns(table_name)}
        if not all(column in table_columns for column in columns):
            return
        op.create_index(
            index_name,
            table_name,
            columns,
            unique=False,
            postgresql_where=postgresql_where,
        )

    # ==========================================================================
    # TAX RETURNS - Dashboard filtering and status queries
    # ==========================================================================

    # Index for dashboard queries filtering by status and tax year
    # Supports: "Show all 2025 returns in review status"
    create_index_if_available(
        'idx_returns_status_year',
        'tax_returns',
        ['status', 'tax_year', 'created_at'],
    )

    # Index for preparer workload queries
    # Supports: "Show all returns assigned to preparer X"
    create_index_if_available(
        'idx_returns_preparer_status',
        'tax_returns',
        ['preparer_id', 'status'],
        postgresql_where="preparer_id IS NOT NULL",
    )

    # Index for client return lookups
    # Supports: "Show all returns for taxpayer X"
    create_index_if_available(
        'idx_returns_taxpayer_year',
        'tax_returns',
        ['taxpayer_id', 'tax_year'],
    )

    # ==========================================================================
    # INCOME RECORDS - Income summaries and aggregation
    # ==========================================================================

    # Index for income aggregation by return and source
    # Supports: "Sum all W-2 income for return X"
    create_index_if_available(
        'idx_income_return_source',
        'income_records',
        ['return_id', 'source_type', 'gross_amount'],
    )

    # ==========================================================================
    # W2 RECORDS - State tax calculations
    # ==========================================================================

    # Index for state-specific W-2 queries
    # Supports: "Get all CA W-2s for return X"
    create_index_if_available(
        'idx_w2_return_state',
        'w2_records',
        ['return_id', 'state_code'],
    )

    # ==========================================================================
    # AUDIT LOGS - Compliance and analysis queries
    # ==========================================================================

    # Index for audit log time-based queries
    # Supports: "Show all login events in the last 24 hours"
    create_index_if_available(
        'idx_audit_timestamp_type',
        'audit_logs',
        ['timestamp', 'event_type'],
    )

    # Index for user-specific audit queries
    # Supports: "Show all actions by user X"
    create_index_if_available(
        'idx_audit_user_timestamp',
        'audit_logs',
        ['user_id', 'timestamp'],
        postgresql_where="user_id IS NOT NULL",
    )

    # ==========================================================================
    # CLIENT SESSIONS - Workload management
    # ==========================================================================

    # Index for active session queries by preparer
    # Supports: "Show all active sessions for preparer X"
    create_index_if_available(
        'idx_sessions_status_preparer',
        'client_sessions',
        ['status', 'preparer_id', 'last_accessed_at'],
    )

    # Index for session timeout cleanup
    # Supports: "Find all sessions not accessed in 30 days"
    create_index_if_available(
        'idx_sessions_last_accessed',
        'client_sessions',
        ['last_accessed_at'],
    )

    # ==========================================================================
    # DOCUMENTS - Document retrieval and status
    # ==========================================================================

    # Index for document listing with status
    # Supports: "Show all pending documents for session X"
    create_index_if_available(
        'idx_documents_session_status',
        'documents',
        ['session_id', 'status', 'created_at'],
    )


def downgrade() -> None:
    """Remove performance indexes."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def drop_index_if_exists(index_name: str, table_name: str) -> None:
        if table_name not in inspector.get_table_names():
            return
        table_indexes = {ix["name"] for ix in inspector.get_indexes(table_name)}
        if index_name in table_indexes:
            op.drop_index(index_name, table_name=table_name)

    # Documents
    drop_index_if_exists('idx_documents_session_status', 'documents')

    # Client sessions
    drop_index_if_exists('idx_sessions_last_accessed', 'client_sessions')
    drop_index_if_exists('idx_sessions_status_preparer', 'client_sessions')

    # Audit logs
    drop_index_if_exists('idx_audit_user_timestamp', 'audit_logs')
    drop_index_if_exists('idx_audit_timestamp_type', 'audit_logs')

    # W2 records
    drop_index_if_exists('idx_w2_return_state', 'w2_records')

    # Income records
    drop_index_if_exists('idx_income_return_source', 'income_records')

    # Tax returns
    drop_index_if_exists('idx_returns_taxpayer_year', 'tax_returns')
    drop_index_if_exists('idx_returns_preparer_status', 'tax_returns')
    drop_index_if_exists('idx_returns_status_year', 'tax_returns')
