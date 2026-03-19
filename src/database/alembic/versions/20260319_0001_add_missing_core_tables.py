"""Add missing core tables: preparers, clients, client_sessions, advisory_reports, report_sections.

Revision ID: 20260319_0001
Revises: 20260318_0001
Create Date: 2026-03-19

These tables are defined in the ORM models but were never created by any prior
migration.  Guards prevent errors if the tables already exist.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = "20260319_0001"
down_revision = "20260318_0001"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


# Enum values for client_sessions.status
CLIENT_STATUS_ENUM = sa.Enum(
    "new", "in_progress", "ready_for_review", "reviewed", "delivered", "archived",
    name="clientstatusdb",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- 1. preparers ---------------------------------------------------------
    if not _table_exists(inspector, "preparers"):
        op.create_table(
            "preparers",
            sa.Column("preparer_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("firm_id", UUID(as_uuid=True), sa.ForeignKey("firms.firm_id", ondelete="CASCADE"), nullable=True),
            sa.Column("first_name", sa.String(100), nullable=False),
            sa.Column("last_name", sa.String(100), nullable=False),
            sa.Column("email", sa.String(255), nullable=False, unique=True),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("credentials", JSONB, nullable=True),
            sa.Column("license_state", sa.String(2), nullable=True),
            sa.Column("firm_name", sa.String(255), nullable=True),
            sa.Column("logo_url", sa.String(500), nullable=True),
            sa.Column("primary_color", sa.String(7), server_default="#2E7D32"),
            sa.Column("secondary_color", sa.String(7), server_default="#4CAF50"),
            sa.Column("default_tax_year", sa.Integer(), server_default="2025"),
            sa.Column("timezone", sa.String(50), server_default="America/New_York"),
            sa.Column("is_active", sa.Boolean(), server_default="true"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_preparer_email", "preparers", ["email"])
        op.create_index("ix_preparer_active", "preparers", ["is_active"])
        op.create_index("ix_preparer_firm", "preparers", ["firm_id"])

    # --- 2. clients -----------------------------------------------------------
    if not _table_exists(inspector, "clients"):
        op.create_table(
            "clients",
            sa.Column("client_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("preparer_id", UUID(as_uuid=True), sa.ForeignKey("preparers.preparer_id"), nullable=False),
            sa.Column("firm_id", UUID(as_uuid=True), sa.ForeignKey("firms.firm_id", ondelete="CASCADE"), nullable=False),
            sa.Column("external_id", sa.String(100), nullable=True),
            sa.Column("ssn_hash", sa.String(64), nullable=True, unique=True),
            sa.Column("first_name", sa.String(100), nullable=False),
            sa.Column("last_name", sa.String(100), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("street_address", sa.String(255), nullable=True),
            sa.Column("city", sa.String(100), nullable=True),
            sa.Column("state", sa.String(2), nullable=True),
            sa.Column("zip_code", sa.String(10), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default="true"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
        )
        op.create_index("ix_client_preparer", "clients", ["preparer_id", "is_active"])
        op.create_index("ix_client_name", "clients", ["last_name", "first_name"])
        op.create_index("ix_client_ssn_hash", "clients", ["ssn_hash"])
        op.create_index("ix_clients_firm_id", "clients", ["firm_id"])
        op.create_unique_constraint("uq_client_external_id", "clients", ["preparer_id", "external_id"])

    # --- 3. client_sessions ---------------------------------------------------
    if not _table_exists(inspector, "client_sessions"):
        op.create_table(
            "client_sessions",
            sa.Column("session_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("firm_id", UUID(as_uuid=True), sa.ForeignKey("firms.firm_id", ondelete="CASCADE"), nullable=True),
            sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.client_id"), nullable=False),
            sa.Column("preparer_id", UUID(as_uuid=True), sa.ForeignKey("preparers.preparer_id"), nullable=False),
            sa.Column("tax_year", sa.Integer(), nullable=False, server_default="2025"),
            sa.Column("status", CLIENT_STATUS_ENUM, nullable=False, server_default="new"),
            sa.Column("return_id", UUID(as_uuid=True), sa.ForeignKey("tax_returns.return_id"), nullable=True),
            sa.Column("scenario_ids", JSONB, nullable=True),
            sa.Column("recommendation_plan_id", UUID(as_uuid=True), nullable=True),
            sa.Column("document_ids", JSONB, nullable=True),
            sa.Column("documents_processed", sa.Integer(), server_default="0"),
            sa.Column("calculations_run", sa.Integer(), server_default="0"),
            sa.Column("scenarios_analyzed", sa.Integer(), server_default="0"),
            sa.Column("estimated_refund", sa.Numeric(12, 2), nullable=True),
            sa.Column("estimated_tax_owed", sa.Numeric(12, 2), nullable=True),
            sa.Column("total_income", sa.Numeric(14, 2), nullable=True),
            sa.Column("potential_savings", sa.Numeric(12, 2), nullable=True),
            sa.Column("preparer_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
            sa.Column("last_accessed_at", sa.DateTime(), server_default=sa.text("now()")),
        )
        op.create_unique_constraint("uq_client_session_year", "client_sessions", ["client_id", "tax_year"])
        op.create_index("ix_session_preparer_year", "client_sessions", ["preparer_id", "tax_year"])
        op.create_index("ix_session_status", "client_sessions", ["status", "preparer_id"])
        op.create_index("ix_session_last_accessed", "client_sessions", ["last_accessed_at"])
        op.create_index("ix_session_return_id", "client_sessions", ["return_id"])
        op.create_index("ix_client_sessions_client_id", "client_sessions", ["client_id"])
        op.create_index("ix_client_sessions_preparer_id", "client_sessions", ["preparer_id"])
        op.create_index("ix_client_sessions_firm_id", "client_sessions", ["firm_id"])

    # --- 4. advisory_reports --------------------------------------------------
    if not _table_exists(inspector, "advisory_reports"):
        op.create_table(
            "advisory_reports",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("report_id", sa.String(100), unique=True, nullable=False),
            sa.Column("session_id", sa.String(100), nullable=False),
            sa.Column("report_type", sa.String(50), nullable=False),
            sa.Column("tax_year", sa.Integer(), nullable=False),
            sa.Column("taxpayer_name", sa.String(200), nullable=False),
            sa.Column("filing_status", sa.String(50), nullable=False),
            sa.Column("current_tax_liability", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("potential_savings", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("recommendations_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("report_data", sa.JSON(), nullable=False),
            sa.Column("pdf_path", sa.String(500), nullable=True),
            sa.Column("pdf_generated", sa.Boolean(), server_default="false"),
            sa.Column("pdf_watermark", sa.String(50), nullable=True),
            sa.Column("status", sa.String(20), server_default="generating"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("generated_at", sa.DateTime(), nullable=True),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        )
        op.create_index("ix_advisory_reports_report_id", "advisory_reports", ["report_id"])
        op.create_index("ix_advisory_reports_session_id", "advisory_reports", ["session_id"])

    # --- 5. report_sections ---------------------------------------------------
    if not _table_exists(inspector, "report_sections"):
        op.create_table(
            "report_sections",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("report_id", sa.Integer(), sa.ForeignKey("advisory_reports.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section_id", sa.String(100), nullable=False),
            sa.Column("section_title", sa.String(200), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("content_data", sa.JSON(), nullable=False),
            sa.Column("generated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_report_sections_report_id", "report_sections", ["report_id"])

    # --- 6. Add FK from tax_returns.client_id -> clients (was skipped earlier)
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "clients") and _table_exists(inspector, "tax_returns"):
        existing_fks = {
            fk["name"]
            for fk in inspector.get_foreign_keys("tax_returns")
            if fk.get("name")
        }
        if "fk_tax_returns_client_id" not in existing_fks:
            cols = {c["name"] for c in inspector.get_columns("tax_returns")}
            if "client_id" in cols:
                op.create_foreign_key(
                    "fk_tax_returns_client_id",
                    "tax_returns",
                    "clients",
                    ["client_id"],
                    ["client_id"],
                    ondelete="SET NULL",
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop FK from tax_returns if it exists
    if _table_exists(inspector, "tax_returns"):
        fks = {fk["name"] for fk in inspector.get_foreign_keys("tax_returns") if fk.get("name")}
        if "fk_tax_returns_client_id" in fks:
            op.drop_constraint("fk_tax_returns_client_id", "tax_returns", type_="foreignkey")

    for table in ("report_sections", "advisory_reports", "client_sessions", "clients", "preparers"):
        if _table_exists(inspector, table):
            op.drop_table(table)

    # Drop the enum type
    CLIENT_STATUS_ENUM.drop(bind, checkfirst=True)
