"""Add SSN Hash and FK Indexes for Performance

Revision ID: 20260128_0002
Revises: 20260128_0001
Create Date: 2026-01-28

Adds indexes on SSN hash columns and foreign key columns for query performance:

SSN Hash Indexes (high-severity - used for lookups):
- taxpayers.spouse_ssn_hash
- w2_records.employee_ssn_hash
- form1099_records.recipient_ssn_hash
- credit_records.student_ssn_hash
- clients.ssn_hash

Foreign Key Indexes (for JOIN and cascade performance):
- users.invited_by
- invitations.invited_by, accepted_by_user_id, revoked_by
- subscriptions.plan_id, cancelled_by
- invoices.subscription_id
- platform_admins.created_by
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260128_0002'
down_revision = '20260128_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # SSN Hash Indexes (High-Severity Performance)
    # ==========================================================================

    # Spouse SSN hash for married filing lookups
    op.create_index(
        'ix_taxpayer_spouse_ssn_hash',
        'taxpayers',
        ['spouse_ssn_hash'],
        unique=False,
        postgresql_where="spouse_ssn_hash IS NOT NULL"
    )

    # Employee SSN hash for W2 record lookups
    op.create_index(
        'ix_w2_employee_ssn_hash',
        'w2_records',
        ['employee_ssn_hash'],
        unique=False
    )

    # Recipient SSN hash for 1099 record lookups
    op.create_index(
        'ix_1099_recipient_ssn_hash',
        'form1099_records',
        ['recipient_ssn_hash'],
        unique=False
    )

    # Student SSN hash for education credit lookups
    op.create_index(
        'ix_credit_student_ssn_hash',
        'credit_records',
        ['student_ssn_hash'],
        unique=False,
        postgresql_where="student_ssn_hash IS NOT NULL"
    )

    # Client SSN hash for client lookups (only if clients table exists in this branch)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'clients' in inspector.get_table_names():
        client_columns = {col["name"] for col in inspector.get_columns("clients")}
        if 'ssn_hash' in client_columns:
            op.create_index(
                'ix_client_ssn_hash',
                'clients',
                ['ssn_hash'],
                unique=False,
                postgresql_where="ssn_hash IS NOT NULL"
            )

    # ==========================================================================
    # Foreign Key Indexes (JOIN and Cascade Performance)
    # ==========================================================================

    # Users table - invited_by FK
    op.create_index(
        'ix_user_invited_by',
        'users',
        ['invited_by'],
        unique=False,
        postgresql_where="invited_by IS NOT NULL"
    )

    # Invitations table - user reference FKs
    op.create_index(
        'ix_invitation_invited_by',
        'invitations',
        ['invited_by'],
        unique=False
    )

    op.create_index(
        'ix_invitation_accepted_by',
        'invitations',
        ['accepted_by_user_id'],
        unique=False,
        postgresql_where="accepted_by_user_id IS NOT NULL"
    )

    op.create_index(
        'ix_invitation_revoked_by',
        'invitations',
        ['revoked_by'],
        unique=False,
        postgresql_where="revoked_by IS NOT NULL"
    )

    # Subscriptions table - plan and user FKs
    op.create_index(
        'ix_subscription_plan_id',
        'subscriptions',
        ['plan_id'],
        unique=False
    )

    op.create_index(
        'ix_subscription_cancelled_by',
        'subscriptions',
        ['cancelled_by'],
        unique=False,
        postgresql_where="cancelled_by IS NOT NULL"
    )

    # Invoices table - subscription FK
    op.create_index(
        'ix_invoice_subscription_id',
        'invoices',
        ['subscription_id'],
        unique=False,
        postgresql_where="subscription_id IS NOT NULL"
    )

    # Platform admins table - created_by FK
    op.create_index(
        'ix_platform_admin_created_by',
        'platform_admins',
        ['created_by'],
        unique=False,
        postgresql_where="created_by IS NOT NULL"
    )


def downgrade() -> None:
    # Drop FK indexes
    op.drop_index('ix_platform_admin_created_by', table_name='platform_admins')
    op.drop_index('ix_invoice_subscription_id', table_name='invoices')
    op.drop_index('ix_subscription_cancelled_by', table_name='subscriptions')
    op.drop_index('ix_subscription_plan_id', table_name='subscriptions')
    op.drop_index('ix_invitation_revoked_by', table_name='invitations')
    op.drop_index('ix_invitation_accepted_by', table_name='invitations')
    op.drop_index('ix_invitation_invited_by', table_name='invitations')
    op.drop_index('ix_user_invited_by', table_name='users')

    # Drop SSN hash indexes
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'clients' in inspector.get_table_names():
        client_indexes = {ix["name"] for ix in inspector.get_indexes("clients")}
        if 'ix_client_ssn_hash' in client_indexes:
            op.drop_index('ix_client_ssn_hash', table_name='clients')
    op.drop_index('ix_credit_student_ssn_hash', table_name='credit_records')
    op.drop_index('ix_1099_recipient_ssn_hash', table_name='form1099_records')
    op.drop_index('ix_w2_employee_ssn_hash', table_name='w2_records')
    op.drop_index('ix_taxpayer_spouse_ssn_hash', table_name='taxpayers')
