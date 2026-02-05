"""Add session persistence tables

Revision ID: 20260205_0002
Revises: 20260205_0001
Create Date: 2026-02-05

Creates the 5 session-related tables that were previously managed via
CREATE TABLE IF NOT EXISTS in session_persistence.py. This migration
makes Alembic the single source of truth for schema.

Tables:
  - session_states
  - document_processing
  - session_tax_returns
  - audit_trails
  - return_status
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260205_0002'
down_revision = '20260205_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # session_states — core session storage
    # =========================================================================
    op.create_table(
        'session_states',
        sa.Column('session_id', sa.Text, primary_key=True),
        sa.Column('tenant_id', sa.Text, nullable=False, server_default='default'),
        sa.Column('session_type', sa.Text, nullable=False, server_default='agent'),
        sa.Column('created_at', sa.Text, nullable=False),
        sa.Column('last_activity', sa.Text, nullable=False),
        sa.Column('expires_at', sa.Text, nullable=False),
        sa.Column('data_json', sa.Text, nullable=False, server_default='{}'),
        sa.Column('metadata_json', sa.Text, nullable=False, server_default='{}'),
        sa.Column('agent_state_blob', sa.LargeBinary, nullable=True),
        sa.Column('user_id', sa.Text, nullable=True),
        sa.Column('is_anonymous', sa.Integer, server_default='1'),
        sa.Column('workflow_type', sa.Text, nullable=True),
        sa.Column('return_id', sa.Text, nullable=True),
        # Avoid failure if table already exists from runtime CREATE TABLE IF NOT EXISTS
        if_not_exists=True,
    )
    op.create_index('idx_session_tenant', 'session_states', ['tenant_id'], if_not_exists=True)
    op.create_index('idx_session_expires', 'session_states', ['expires_at'], if_not_exists=True)

    # =========================================================================
    # document_processing — OCR / document results
    # =========================================================================
    op.create_table(
        'document_processing',
        sa.Column('document_id', sa.Text, primary_key=True),
        sa.Column('session_id', sa.Text, nullable=False),
        sa.Column('tenant_id', sa.Text, nullable=False, server_default='default'),
        sa.Column('created_at', sa.Text, nullable=False),
        sa.Column('document_type', sa.Text, nullable=True),
        sa.Column('status', sa.Text, nullable=False, server_default='pending'),
        sa.Column('result_json', sa.Text, nullable=False, server_default='{}'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['session_states.session_id']),
        if_not_exists=True,
    )
    op.create_index('idx_doc_session', 'document_processing', ['session_id'], if_not_exists=True)
    op.create_index('idx_doc_tenant', 'document_processing', ['tenant_id'], if_not_exists=True)

    # =========================================================================
    # session_tax_returns — tax return data per session
    # =========================================================================
    op.create_table(
        'session_tax_returns',
        sa.Column('session_id', sa.Text, primary_key=True),
        sa.Column('tenant_id', sa.Text, nullable=False, server_default='default'),
        sa.Column('created_at', sa.Text, nullable=False),
        sa.Column('updated_at', sa.Text, nullable=False),
        sa.Column('tax_year', sa.Integer, nullable=False, server_default='2025'),
        sa.Column('return_data_json', sa.Text, nullable=False, server_default='{}'),
        sa.Column('calculated_results_json', sa.Text, nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['session_states.session_id']),
        if_not_exists=True,
    )

    # =========================================================================
    # audit_trails — CPA compliance audit log
    # =========================================================================
    op.create_table(
        'audit_trails',
        sa.Column('session_id', sa.Text, primary_key=True),
        sa.Column('tenant_id', sa.Text, nullable=False, server_default='default'),
        sa.Column('created_at', sa.Text, nullable=False),
        sa.Column('updated_at', sa.Text, nullable=False),
        sa.Column('trail_json', sa.Text, nullable=False),
        sa.Column('entry_count', sa.Integer, nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['session_id'], ['session_states.session_id']),
        if_not_exists=True,
    )
    op.create_index('idx_audit_tenant', 'audit_trails', ['tenant_id'], if_not_exists=True)
    op.create_index('idx_audit_updated', 'audit_trails', ['updated_at'], if_not_exists=True)

    # =========================================================================
    # return_status — CPA approval workflow
    # =========================================================================
    op.create_table(
        'return_status',
        sa.Column('session_id', sa.Text, primary_key=True),
        sa.Column('tenant_id', sa.Text, nullable=False, server_default='default'),
        sa.Column('status', sa.Text, nullable=False, server_default='DRAFT'),
        sa.Column('created_at', sa.Text, nullable=False),
        sa.Column('updated_at', sa.Text, nullable=False),
        sa.Column('last_status_change', sa.Text, nullable=False),
        sa.Column('cpa_reviewer_id', sa.Text, nullable=True),
        sa.Column('cpa_reviewer_name', sa.Text, nullable=True),
        sa.Column('review_notes', sa.Text, nullable=True),
        sa.Column('approval_timestamp', sa.Text, nullable=True),
        sa.Column('approval_signature_hash', sa.Text, nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['session_states.session_id']),
        if_not_exists=True,
    )
    op.create_index('idx_return_status_tenant', 'return_status', ['tenant_id'], if_not_exists=True)
    op.create_index('idx_return_status_status', 'return_status', ['status'], if_not_exists=True)


def downgrade() -> None:
    op.drop_table('return_status')
    op.drop_table('audit_trails')
    op.drop_table('session_tax_returns')
    op.drop_table('document_processing')
    op.drop_table('session_states')
