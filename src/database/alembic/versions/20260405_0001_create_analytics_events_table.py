"""Create analytics_events table for journey event persistence.

Revision ID: 20260405_0001
Revises: 20260331_0001
Create Date: 2026-04-05

Creates analytics_events table to persist journey events for CPA dashboard analytics.
This enables moving from ephemeral in-process event bus to durable event storage.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260405_0001"
down_revision = "20260331_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create analytics_events table with wide schema for event data."""
    # Determine database dialect
    ctx = op.get_context()
    is_sqlite = ctx.dialect.name == 'sqlite'

    # Use appropriate UUID type based on database
    if is_sqlite:
        event_id_type = sa.String(36)  # UUID as string in SQLite
        firm_id_type = sa.String(36)   # UUID as string in SQLite
        firm_id_default = None
    else:
        event_id_type = postgresql.UUID(as_uuid=True)
        firm_id_type = postgresql.UUID(as_uuid=True)
        firm_id_default = sa.text("gen_random_uuid()")

    op.create_table(
        "analytics_events",
        sa.Column(
            "event_id",
            event_id_type,
            nullable=False,
            server_default=firm_id_default if is_sqlite is False else None,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("tenant_id", sa.String(100), nullable=False, index=True),
        sa.Column("user_id", sa.String(100), nullable=False, index=True),
        sa.Column(
            "firm_id",
            firm_id_type,
            sa.ForeignKey("firms.firm_id", ondelete="CASCADE") if not is_sqlite else None,
            nullable=True,
            index=True,
        ),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("session_id", sa.String(100), nullable=True, index=True),
        sa.Column("return_id", sa.String(100), nullable=True, index=True),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("scenario_id", sa.String(100), nullable=True),
        sa.Column("report_id", sa.String(100), nullable=True),
        sa.Column("lead_id", sa.String(100), nullable=True),
        sa.Column("cpa_id", sa.String(100), nullable=True),
        # Event-specific fields (wide schema)
        sa.Column("profile_completeness", sa.Numeric(5, 2), nullable=True),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(100), nullable=True),
        sa.Column("fields_extracted", sa.Integer(), nullable=True),
        sa.Column("return_completeness", sa.Numeric(5, 2), nullable=True),
        sa.Column("scenario_name", sa.String(255), nullable=True),
        sa.Column("scenario_savings", sa.Numeric(15, 2), nullable=True),
        sa.Column("review_status", sa.String(50), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("download_url", sa.String(512), nullable=True),
        sa.Column("lead_from_state", sa.String(50), nullable=True),
        sa.Column("lead_to_state", sa.String(50), nullable=True),
        sa.Column("lead_trigger", sa.String(50), nullable=True),
        sa.Column("extracted_forms", sa.Text(), nullable=True),  # JSON array
        # Audit fields
        sa.Column("data_json", sa.JSON(), nullable=True),  # Full event payload as JSON
        sa.PrimaryKeyConstraint("event_id"),
    )

    # Create indexes for common queries
    op.create_index("ix_analytics_events_received_at", "analytics_events", ["received_at"])
    op.create_index("ix_analytics_events_tenant_date", "analytics_events", ["tenant_id", "received_at"])
    op.create_index("ix_analytics_events_user_date", "analytics_events", ["user_id", "received_at"])
    op.create_index("ix_analytics_events_type", "analytics_events", ["event_type"])


def downgrade() -> None:
    """Drop analytics_events table."""
    op.drop_index("ix_analytics_events_type", table_name="analytics_events")
    op.drop_index("ix_analytics_events_user_date", table_name="analytics_events")
    op.drop_index("ix_analytics_events_tenant_date", table_name="analytics_events")
    op.drop_index("ix_analytics_events_received_at", table_name="analytics_events")
    op.drop_table("analytics_events")
