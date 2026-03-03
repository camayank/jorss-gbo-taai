"""Add firm_id and client_id columns to tax_returns table for firm isolation.

Revision ID: 20260304_0002
Revises: 20260304_0001
Create Date: 2026-03-04

Adds firm_id and client_id to tax_returns so returns can be directly scoped
to a firm/client without joining through client_sessions.  Backfills from
client_sessions joined to clients.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "20260304_0002"
down_revision = "20260304_0001"
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

    if not _table_exists(inspector, "tax_returns"):
        return

    # --- 1. Add columns (nullable, no FK yet) --------------------------------
    _add_column_if_missing(
        inspector,
        "tax_returns",
        sa.Column("firm_id", UUID(as_uuid=True), nullable=True),
    )
    _add_column_if_missing(
        inspector,
        "tax_returns",
        sa.Column("client_id", UUID(as_uuid=True), nullable=True),
    )
    inspector = sa.inspect(bind)

    # --- 2. Backfill from client_sessions + clients ---------------------------
    if _table_exists(inspector, "client_sessions") and _table_exists(inspector, "clients"):
        op.execute(
            sa.text(
                "UPDATE tax_returns tr "
                "SET client_id = cs.client_id, firm_id = c.firm_id "
                "FROM client_sessions cs "
                "JOIN clients c ON cs.client_id = c.client_id "
                "WHERE cs.return_id = tr.return_id "
                "AND tr.client_id IS NULL"
            )
        )

    # --- 3. Create indexes ----------------------------------------------------
    _create_index_if_missing(inspector, "tax_returns", "ix_tax_returns_firm_id", ["firm_id"])
    _create_index_if_missing(inspector, "tax_returns", "ix_tax_returns_client_id", ["client_id"])

    # --- 4. Add FK constraints ------------------------------------------------
    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("tax_returns")
        if fk.get("name")
    }
    if "fk_tax_returns_firm_id" not in existing_fks:
        op.create_foreign_key(
            "fk_tax_returns_firm_id",
            "tax_returns",
            "firms",
            ["firm_id"],
            ["firm_id"],
            ondelete="SET NULL",
        )
    if "fk_tax_returns_client_id" not in existing_fks:
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

    if not _table_exists(inspector, "tax_returns"):
        return

    # Drop FK constraints
    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("tax_returns")
        if fk.get("name")
    }
    if "fk_tax_returns_client_id" in existing_fks:
        op.drop_constraint("fk_tax_returns_client_id", "tax_returns", type_="foreignkey")
    if "fk_tax_returns_firm_id" in existing_fks:
        op.drop_constraint("fk_tax_returns_firm_id", "tax_returns", type_="foreignkey")

    # Drop indexes
    if "ix_tax_returns_client_id" in _index_names(inspector, "tax_returns"):
        op.drop_index("ix_tax_returns_client_id", table_name="tax_returns")
    if "ix_tax_returns_firm_id" in _index_names(inspector, "tax_returns"):
        op.drop_index("ix_tax_returns_firm_id", table_name="tax_returns")

    # Drop columns
    if "client_id" in _column_names(inspector, "tax_returns"):
        op.drop_column("tax_returns", "client_id")
    if "firm_id" in _column_names(inspector, "tax_returns"):
        op.drop_column("tax_returns", "firm_id")
