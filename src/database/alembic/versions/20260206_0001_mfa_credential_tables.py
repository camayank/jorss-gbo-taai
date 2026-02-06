"""Add MFA credential tables for secure persistence

Revision ID: 20260206_0001
Revises: 20260205_0002
Create Date: 2026-02-06

Creates secure storage tables for MFA credentials:
  - mfa_credentials: Stores TOTP secrets and backup codes (encrypted)
  - mfa_pending_setups: Temporary storage for MFA setup in progress

Security Notes:
  - All sensitive data (TOTP secrets, backup codes) are encrypted with AES-256-GCM
  - Backup codes are hashed before encryption for extra security
  - Pending setups expire after 15 minutes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '20260206_0001'
down_revision = '20260205_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # mfa_credentials - Secure storage for MFA secrets and backup codes
    # =========================================================================
    op.create_table(
        'mfa_credentials',
        sa.Column('credential_id', sa.Text, primary_key=True),
        sa.Column('user_id', sa.String(100), nullable=False, index=True),
        sa.Column('tenant_id', sa.String(100), nullable=True, index=True),
        sa.Column('mfa_type', sa.String(20), nullable=False, server_default='totp'),
        sa.Column('secret_encrypted', sa.String(512), nullable=True,
                  comment='AES-256-GCM encrypted TOTP secret'),
        sa.Column('backup_codes_encrypted', sa.Text, nullable=True,
                  comment='AES-256-GCM encrypted backup codes JSON'),
        sa.Column('is_verified', sa.Boolean, server_default='0', nullable=False),
        sa.Column('verified_at', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='1', nullable=False),
        sa.Column('last_used_at', sa.DateTime, nullable=True),
        sa.Column('use_count', sa.Integer, server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        if_not_exists=True,
    )

    # Indexes for efficient queries
    op.create_index('ix_mfa_user_type', 'mfa_credentials', ['user_id', 'mfa_type'], if_not_exists=True)
    op.create_index('ix_mfa_user_active', 'mfa_credentials', ['user_id', 'is_active'], if_not_exists=True)
    op.create_index('ix_mfa_verified', 'mfa_credentials', ['is_verified'], if_not_exists=True)

    # Unique constraint: one active MFA per type per user per tenant
    op.create_unique_constraint(
        'uq_mfa_user_type_tenant',
        'mfa_credentials',
        ['user_id', 'mfa_type', 'tenant_id']
    )

    # =========================================================================
    # mfa_pending_setups - Temporary storage for MFA setup in progress
    # =========================================================================
    op.create_table(
        'mfa_pending_setups',
        sa.Column('setup_id', sa.Text, primary_key=True),
        sa.Column('user_id', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('tenant_id', sa.String(100), nullable=True),
        sa.Column('secret_encrypted', sa.String(512), nullable=False,
                  comment='AES-256-GCM encrypted TOTP secret'),
        sa.Column('backup_codes_encrypted', sa.Text, nullable=False,
                  comment='AES-256-GCM encrypted backup codes'),
        sa.Column('expires_at', sa.DateTime, nullable=False, index=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        if_not_exists=True,
    )

    # Index for cleanup queries (expired setups)
    op.create_index('ix_mfa_pending_expires', 'mfa_pending_setups', ['expires_at'], if_not_exists=True)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('mfa_pending_setups')
    op.drop_table('mfa_credentials')
