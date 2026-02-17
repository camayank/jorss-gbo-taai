"""Add lead-magnet persistence tables for PostgreSQL.

Revision ID: 20260217_0001
Revises: 20260212_0001
Create Date: 2026-02-17

Creates/patches the runtime tables used by the taxpayer lead-magnet flow:
- cpa_profiles
- lead_magnet_sessions
- lead_magnet_leads
- lead_magnet_events
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260217_0001"
down_revision = "20260212_0001"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_names(inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    if not _table_exists(inspector, table_name):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _add_column_if_missing(inspector, table_name: str, column: sa.Column) -> None:
    if column.name in _column_names(inspector, table_name):
        return
    op.add_column(table_name, column)


def _create_index_if_missing(
    inspector,
    table_name: str,
    index_name: str,
    columns: list[str],
    unique: bool = False,
) -> None:
    if index_name in _index_names(inspector, table_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # -------------------------------------------------------------------------
    # cpa_profiles
    # -------------------------------------------------------------------------
    if not _table_exists(inspector, "cpa_profiles"):
        op.create_table(
            "cpa_profiles",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("cpa_id", sa.String(64), nullable=False, unique=True),
            sa.Column("cpa_slug", sa.String(255), nullable=False, unique=True),
            sa.Column("first_name", sa.String(255), nullable=False),
            sa.Column("last_name", sa.String(255), nullable=False),
            sa.Column("credentials", sa.String(64), nullable=True),
            sa.Column("firm_name", sa.String(255), nullable=True),
            sa.Column("logo_url", sa.Text(), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(40), nullable=True),
            sa.Column("booking_link", sa.Text(), nullable=True),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("specialties_json", sa.Text(), nullable=True, server_default=sa.text("'[]'")),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("stripe_account_id", sa.String(255), nullable=True),
            sa.Column("stripe_connected_at", sa.DateTime(), nullable=True),
            sa.Column("payment_settings", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)
    else:
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("cpa_id", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("cpa_slug", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("first_name", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("last_name", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("credentials", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("firm_name", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("logo_url", sa.Text(), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("email", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("phone", sa.String(40), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("booking_link", sa.Text(), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("address", sa.Text(), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("bio", sa.Text(), nullable=True))
        _add_column_if_missing(
            inspector,
            "cpa_profiles",
            sa.Column("specialties_json", sa.Text(), nullable=True, server_default=sa.text("'[]'")),
        )
        _add_column_if_missing(
            inspector,
            "cpa_profiles",
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("stripe_account_id", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("stripe_connected_at", sa.DateTime(), nullable=True))
        _add_column_if_missing(inspector, "cpa_profiles", sa.Column("payment_settings", sa.Text(), nullable=True))
        _add_column_if_missing(
            inspector,
            "cpa_profiles",
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        _add_column_if_missing(
            inspector,
            "cpa_profiles",
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)

    _create_index_if_missing(inspector, "cpa_profiles", "idx_cpa_profiles_slug", ["cpa_slug"])
    _create_index_if_missing(inspector, "cpa_profiles", "idx_cpa_profiles_active", ["active"])

    # -------------------------------------------------------------------------
    # lead_magnet_sessions
    # -------------------------------------------------------------------------
    if not _table_exists(inspector, "lead_magnet_sessions"):
        op.create_table(
            "lead_magnet_sessions",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("session_id", sa.String(64), nullable=False, unique=True),
            sa.Column("cpa_id", sa.String(64), nullable=True),
            sa.Column("cpa_slug", sa.String(255), nullable=True),
            sa.Column("assessment_mode", sa.String(32), nullable=False, server_default=sa.text("'quick'")),
            sa.Column("current_screen", sa.String(64), nullable=False, server_default=sa.text("'welcome'")),
            sa.Column("privacy_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("profile_data_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("contact_captured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("last_activity", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("time_spent_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("referral_source", sa.Text(), nullable=True),
            sa.Column("variant_id", sa.String(16), nullable=True, server_default=sa.text("'A'")),
            sa.Column("utm_source", sa.String(255), nullable=True),
            sa.Column("utm_medium", sa.String(255), nullable=True),
            sa.Column("utm_campaign", sa.String(255), nullable=True),
            sa.Column("device_type", sa.String(32), nullable=True),
            sa.ForeignKeyConstraint(["cpa_id"], ["cpa_profiles.cpa_id"], name="fk_lm_sessions_cpa"),
        )
        inspector = sa.inspect(bind)
    else:
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("session_id", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("cpa_id", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("cpa_slug", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("assessment_mode", sa.String(32), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("current_screen", sa.String(64), nullable=True))
        _add_column_if_missing(
            inspector,
            "lead_magnet_sessions",
            sa.Column("privacy_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        _add_column_if_missing(
            inspector,
            "lead_magnet_sessions",
            sa.Column("profile_data_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        )
        _add_column_if_missing(
            inspector,
            "lead_magnet_sessions",
            sa.Column("contact_captured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        _add_column_if_missing(
            inspector,
            "lead_magnet_sessions",
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        _add_column_if_missing(
            inspector,
            "lead_magnet_sessions",
            sa.Column("last_activity", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("completed_at", sa.DateTime(), nullable=True))
        _add_column_if_missing(
            inspector,
            "lead_magnet_sessions",
            sa.Column("time_spent_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("referral_source", sa.Text(), nullable=True))
        _add_column_if_missing(
            inspector,
            "lead_magnet_sessions",
            sa.Column("variant_id", sa.String(16), nullable=True, server_default=sa.text("'A'")),
        )
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("utm_source", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("utm_medium", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("utm_campaign", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_sessions", sa.Column("device_type", sa.String(32), nullable=True))
        inspector = sa.inspect(bind)

    _create_index_if_missing(inspector, "lead_magnet_sessions", "idx_lm_sessions_cpa", ["cpa_id"])
    _create_index_if_missing(inspector, "lead_magnet_sessions", "idx_lm_sessions_started", ["started_at"])
    _create_index_if_missing(inspector, "lead_magnet_sessions", "idx_lm_sessions_variant", ["variant_id"])

    # -------------------------------------------------------------------------
    # lead_magnet_leads
    # -------------------------------------------------------------------------
    if not _table_exists(inspector, "lead_magnet_leads"):
        op.create_table(
            "lead_magnet_leads",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("lead_id", sa.String(64), nullable=False, unique=True),
            sa.Column("session_id", sa.String(64), nullable=False),
            sa.Column("cpa_id", sa.String(64), nullable=True),
            sa.Column("first_name", sa.String(255), nullable=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("phone", sa.String(40), nullable=True),
            sa.Column("filing_status", sa.String(64), nullable=True),
            sa.Column("complexity", sa.String(32), nullable=False, server_default=sa.text("'simple'")),
            sa.Column("income_range", sa.String(64), nullable=True),
            sa.Column("lead_score", sa.Integer(), nullable=False, server_default=sa.text("50")),
            sa.Column("lead_temperature", sa.String(32), nullable=False, server_default=sa.text("'warm'")),
            sa.Column("estimated_engagement_value", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("conversion_probability", sa.Numeric(8, 4), nullable=False, server_default=sa.text("0.5")),
            sa.Column("savings_range_low", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("savings_range_high", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("engaged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("engaged_at", sa.DateTime(), nullable=True),
            sa.Column(
                "engagement_letter_acknowledged",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("engagement_letter_acknowledged_at", sa.DateTime(), nullable=True),
            sa.Column("converted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("converted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["session_id"], ["lead_magnet_sessions.session_id"], name="fk_lm_leads_session"),
            sa.ForeignKeyConstraint(["cpa_id"], ["cpa_profiles.cpa_id"], name="fk_lm_leads_cpa"),
        )
        inspector = sa.inspect(bind)
    else:
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("lead_id", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("session_id", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("cpa_id", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("first_name", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("email", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("phone", sa.String(40), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("filing_status", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("complexity", sa.String(32), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("income_range", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("lead_score", sa.Integer(), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("lead_temperature", sa.String(32), nullable=True))
        _add_column_if_missing(
            inspector,
            "lead_magnet_leads",
            sa.Column("estimated_engagement_value", sa.Numeric(12, 2), nullable=True),
        )
        _add_column_if_missing(
            inspector,
            "lead_magnet_leads",
            sa.Column("conversion_probability", sa.Numeric(8, 4), nullable=True),
        )
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("savings_range_low", sa.Numeric(12, 2), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("savings_range_high", sa.Numeric(12, 2), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("engaged", sa.Boolean(), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("engaged_at", sa.DateTime(), nullable=True))
        _add_column_if_missing(
            inspector,
            "lead_magnet_leads",
            sa.Column("engagement_letter_acknowledged", sa.Boolean(), nullable=True),
        )
        _add_column_if_missing(
            inspector,
            "lead_magnet_leads",
            sa.Column("engagement_letter_acknowledged_at", sa.DateTime(), nullable=True),
        )
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("converted", sa.Boolean(), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("converted_at", sa.DateTime(), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_leads", sa.Column("created_at", sa.DateTime(), nullable=True))
        inspector = sa.inspect(bind)

    _create_index_if_missing(inspector, "lead_magnet_leads", "idx_lm_leads_session", ["session_id"])
    _create_index_if_missing(inspector, "lead_magnet_leads", "idx_lm_leads_cpa", ["cpa_id"])
    _create_index_if_missing(inspector, "lead_magnet_leads", "idx_lm_leads_created", ["created_at"])
    _create_index_if_missing(inspector, "lead_magnet_leads", "idx_lm_leads_temperature", ["lead_temperature"])

    # -------------------------------------------------------------------------
    # lead_magnet_events
    # -------------------------------------------------------------------------
    if not _table_exists(inspector, "lead_magnet_events"):
        op.create_table(
            "lead_magnet_events",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("event_id", sa.String(64), nullable=False, unique=True),
            sa.Column("session_id", sa.String(64), nullable=False),
            sa.Column("cpa_id", sa.String(64), nullable=True),
            sa.Column("event_name", sa.String(80), nullable=False),
            sa.Column("step", sa.String(64), nullable=True),
            sa.Column("variant_id", sa.String(16), nullable=True),
            sa.Column("utm_source", sa.String(255), nullable=True),
            sa.Column("utm_medium", sa.String(255), nullable=True),
            sa.Column("utm_campaign", sa.String(255), nullable=True),
            sa.Column("device_type", sa.String(32), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["session_id"], ["lead_magnet_sessions.session_id"], name="fk_lm_events_session"),
            sa.ForeignKeyConstraint(["cpa_id"], ["cpa_profiles.cpa_id"], name="fk_lm_events_cpa"),
        )
        inspector = sa.inspect(bind)
    else:
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("event_id", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("session_id", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("cpa_id", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("event_name", sa.String(80), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("step", sa.String(64), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("variant_id", sa.String(16), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("utm_source", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("utm_medium", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("utm_campaign", sa.String(255), nullable=True))
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("device_type", sa.String(32), nullable=True))
        _add_column_if_missing(
            inspector,
            "lead_magnet_events",
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        )
        _add_column_if_missing(inspector, "lead_magnet_events", sa.Column("created_at", sa.DateTime(), nullable=True))
        inspector = sa.inspect(bind)

    _create_index_if_missing(inspector, "lead_magnet_events", "idx_lm_events_session_created", ["session_id", "created_at"])
    _create_index_if_missing(inspector, "lead_magnet_events", "idx_lm_events_name_created", ["event_name", "created_at"])
    _create_index_if_missing(inspector, "lead_magnet_events", "idx_lm_events_variant_created", ["variant_id", "created_at"])
    _create_index_if_missing(inspector, "lead_magnet_events", "idx_lm_events_utm_source_created", ["utm_source", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for index_name, table_name in (
        ("idx_lm_events_utm_source_created", "lead_magnet_events"),
        ("idx_lm_events_variant_created", "lead_magnet_events"),
        ("idx_lm_events_name_created", "lead_magnet_events"),
        ("idx_lm_events_session_created", "lead_magnet_events"),
        ("idx_lm_leads_temperature", "lead_magnet_leads"),
        ("idx_lm_leads_created", "lead_magnet_leads"),
        ("idx_lm_leads_cpa", "lead_magnet_leads"),
        ("idx_lm_leads_session", "lead_magnet_leads"),
        ("idx_lm_sessions_variant", "lead_magnet_sessions"),
        ("idx_lm_sessions_started", "lead_magnet_sessions"),
        ("idx_lm_sessions_cpa", "lead_magnet_sessions"),
        ("idx_cpa_profiles_active", "cpa_profiles"),
        ("idx_cpa_profiles_slug", "cpa_profiles"),
    ):
        if _table_exists(inspector, table_name) and index_name in _index_names(inspector, table_name):
            op.drop_index(index_name, table_name=table_name)

    if _table_exists(inspector, "lead_magnet_events"):
        op.drop_table("lead_magnet_events")
    if _table_exists(inspector, "lead_magnet_leads"):
        op.drop_table("lead_magnet_leads")
    if _table_exists(inspector, "lead_magnet_sessions"):
        op.drop_table("lead_magnet_sessions")
    if _table_exists(inspector, "cpa_profiles"):
        op.drop_table("cpa_profiles")
