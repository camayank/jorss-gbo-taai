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
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260128_0001'
down_revision = '20260119_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Index on tax_returns.original_return_id for amendment lookups
    # This FK links amended returns to their original
    if 'tax_returns' in existing_tables:
        tax_return_columns = {col["name"] for col in inspector.get_columns("tax_returns")}
        if 'original_return_id' in tax_return_columns:
            op.create_index(
                'ix_tax_returns_original_return_id',
                'tax_returns',
                ['original_return_id'],
                unique=False,
                postgresql_where="original_return_id IS NOT NULL"
            )

    # Index on client_sessions.return_id for session-to-return joins
    # This FK links client sessions to their associated tax return
    if 'client_sessions' in existing_tables:
        client_session_columns = {col["name"] for col in inspector.get_columns("client_sessions")}
        if 'return_id' in client_session_columns:
            op.create_index(
                'ix_client_sessions_return_id',
                'client_sessions',
                ['return_id'],
                unique=False,
                postgresql_where="return_id IS NOT NULL"
            )

    # Index on documents.return_id for document queries by return
    # This FK links documents to their associated tax return
    if 'documents' in existing_tables:
        document_columns = {col["name"] for col in inspector.get_columns("documents")}
        if 'return_id' in document_columns:
            op.create_index(
                'ix_documents_return_id',
                'documents',
                ['return_id'],
                unique=False,
                postgresql_where="return_id IS NOT NULL"
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'documents' in inspector.get_table_names():
        document_indexes = {ix["name"] for ix in inspector.get_indexes("documents")}
        if 'ix_documents_return_id' in document_indexes:
            op.drop_index('ix_documents_return_id', table_name='documents')

    if 'client_sessions' in inspector.get_table_names():
        session_indexes = {ix["name"] for ix in inspector.get_indexes("client_sessions")}
        if 'ix_client_sessions_return_id' in session_indexes:
            op.drop_index('ix_client_sessions_return_id', table_name='client_sessions')

    if 'tax_returns' in inspector.get_table_names():
        tax_return_indexes = {ix["name"] for ix in inspector.get_indexes("tax_returns")}
        if 'ix_tax_returns_original_return_id' in tax_return_indexes:
            op.drop_index('ix_tax_returns_original_return_id', table_name='tax_returns')
