"""Seed subscription_plans with Starter, Professional, Enterprise tiers.

Revision ID: 20260331_0001
Revises: 20260319_0001
Create Date: 2026-03-31

Inserts the three canonical subscription plans if they do not already exist.
Uses ON CONFLICT DO NOTHING on the unique code column so this migration is
safe to re-run (idempotent).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260331_0001"
down_revision = "20260319_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Guard: table must exist before we seed it
    if "subscription_plans" not in inspector.get_table_names():
        op.execute(
            sa.text("""
                CREATE TABLE IF NOT EXISTS subscription_plans (
                    plan_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    code        VARCHAR(64)  NOT NULL UNIQUE,
                    name        VARCHAR(128) NOT NULL,
                    price_monthly  INTEGER NOT NULL,
                    price_annual   INTEGER NOT NULL,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        )

    # Insert plans — skip silently if the code already exists
    op.execute(
        sa.text("""
            INSERT INTO subscription_plans
                (plan_id, code, name, price_monthly, price_annual)
            VALUES
                (gen_random_uuid(), 'starter',      'Starter',      199,  1990),
                (gen_random_uuid(), 'professional', 'Professional', 499,  4990),
                (gen_random_uuid(), 'enterprise',   'Enterprise',   999,  9990)
            ON CONFLICT (code) DO NOTHING
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
            DELETE FROM subscription_plans
            WHERE code IN ('starter', 'professional', 'enterprise')
        """)
    )
