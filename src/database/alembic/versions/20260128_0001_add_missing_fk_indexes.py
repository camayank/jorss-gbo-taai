"""Add Missing FK Indexes

Revision ID: 20260128_0001
Revises: 20260119_0001
Create Date: 2026-01-28

Adds indexes on foreign key columns that were missing:
- tax_returns.original_return_id (amendment lookups)
- client_sessions.return_id (session-to-return joins)
- documents.return_id (document queries by return)

These indexes improve JOIN performance and cascade operations.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '20260128_0001'
down_revision = '20260119_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Index on tax_returns.original_return_id for amendment lookups
    # This FK links amended returns to their original
    op.create_index(
        'ix_tax_returns_original_return_id',
        'tax_returns',
        ['original_return_id'],
        unique=False,
        postgresql_where="original_return_id IS NOT NULL"
    )

    # Index on client_sessions.return_id for session-to-return joins
    # This FK links client sessions to their associated tax return
    op.create_index(
        'ix_client_sessions_return_id',
        'client_sessions',
        ['return_id'],
        unique=False,
        postgresql_where="return_id IS NOT NULL"
    )

    # Index on documents.return_id for document queries by return
    # This FK links documents to their associated tax return
    op.create_index(
        'ix_documents_return_id',
        'documents',
        ['return_id'],
        unique=False,
        postgresql_where="return_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index('ix_documents_return_id', table_name='documents')
    op.drop_index('ix_client_sessions_return_id', table_name='client_sessions')
    op.drop_index('ix_tax_returns_original_return_id', table_name='tax_returns')
