"""Add consent_audit_log table for compliance tracking.

Revision ID: 20260318_0001
Revises: 20260304_0004
Create Date: 2026-03-18

Stores timestamped records of user consent acknowledgments
for Circular 230, privacy policy, and lead transmission consent.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260318_0001"
down_revision = "20260304_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consent_audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(255), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(255), nullable=True),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("consent_version", sa.String(50), nullable=False),
        sa.Column("consent_text_hash", sa.String(64), nullable=True),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_audit_log_user_id", "consent_audit_log", ["user_id"])
    op.create_index(
        "ix_consent_audit_log_acknowledged_at",
        "consent_audit_log",
        ["acknowledged_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_consent_audit_log_acknowledged_at", table_name="consent_audit_log")
    op.drop_index("ix_consent_audit_log_user_id", table_name="consent_audit_log")
    op.drop_table("consent_audit_log")
