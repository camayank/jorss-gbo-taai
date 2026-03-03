"""Create tenant_firm_mapping table for tenant_id to firm_id resolution.

Revision ID: 20260304_0003
Revises: 20260304_0002
Create Date: 2026-03-04

Maps string tenant slugs (used in SQLite / lead-magnet flows) to PostgreSQL
firm UUIDs so that leads can be linked back to the correct firm.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "20260304_0003"
down_revision = "20260304_0002"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- 1. Create table if it doesn't already exist -------------------------
    if not _table_exists(inspector, "tenant_firm_mapping"):
        op.create_table(
            "tenant_firm_mapping",
            sa.Column("tenant_id", sa.String(255), primary_key=True),
            sa.Column(
                "firm_id",
                UUID(as_uuid=True),
                sa.ForeignKey("firms.firm_id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
            ),
        )

    # --- 2. Backfill from cpa_profiles if it exists --------------------------
    inspector = sa.inspect(bind)
    if (
        _table_exists(inspector, "cpa_profiles")
        and _table_exists(inspector, "users")
        and _table_exists(inspector, "tenant_firm_mapping")
    ):
        op.execute(
            sa.text(
                "INSERT INTO tenant_firm_mapping (tenant_id, firm_id) "
                "SELECT DISTINCT cp.cpa_slug, u.firm_id "
                "FROM cpa_profiles cp "
                "JOIN users u ON cp.user_id = u.user_id "
                "WHERE cp.cpa_slug IS NOT NULL "
                "AND u.firm_id IS NOT NULL "
                "ON CONFLICT DO NOTHING"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "tenant_firm_mapping"):
        op.drop_table("tenant_firm_mapping")
