"""Add firm_id column to clients table for direct firm-scoped queries.

Revision ID: 20260304_0001
Revises: 20260217_0001
Create Date: 2026-03-04

Adds firm_id to clients so admin-panel queries no longer need to JOIN
through users to resolve the firm.  Backfills from users (direct match
on preparer_id = user_id) and from preparers (email match).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "20260304_0001"
down_revision = "20260217_0001"
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

    if not _table_exists(inspector, "clients"):
        return

    # --- 1. Add the column (nullable, no FK yet) ----------------------------
    _add_column_if_missing(
        inspector,
        "clients",
        sa.Column("firm_id", UUID(as_uuid=True), nullable=True),
    )
    inspector = sa.inspect(bind)

    # --- 2. Backfill firm_id from users (preparer_id == user_id) ------------
    op.execute(
        sa.text(
            "UPDATE clients c "
            "SET firm_id = u.firm_id "
            "FROM users u "
            "WHERE c.preparer_id = u.user_id "
            "AND c.firm_id IS NULL"
        )
    )

    # --- 3. Backfill via preparers email match ------------------------------
    if _table_exists(inspector, "preparers") and _table_exists(inspector, "users"):
        op.execute(
            sa.text(
                "UPDATE clients c "
                "SET firm_id = u.firm_id "
                "FROM preparers p "
                "JOIN users u ON LOWER(p.email) = LOWER(u.email) "
                "WHERE c.preparer_id = p.preparer_id "
                "AND c.firm_id IS NULL"
            )
        )

    # --- 4. Create index ----------------------------------------------------
    _create_index_if_missing(inspector, "clients", "ix_clients_firm_id", ["firm_id"])

    # --- 5. Add FK constraint -----------------------------------------------
    # Check existing FK constraints to avoid duplicates
    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("clients")
        if fk.get("name")
    }
    if "fk_clients_firm_id" not in existing_fks:
        op.create_foreign_key(
            "fk_clients_firm_id",
            "clients",
            "firms",
            ["firm_id"],
            ["firm_id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "clients"):
        return

    # Drop FK constraint
    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("clients")
        if fk.get("name")
    }
    if "fk_clients_firm_id" in existing_fks:
        op.drop_constraint("fk_clients_firm_id", "clients", type_="foreignkey")

    # Drop index
    if "ix_clients_firm_id" in _index_names(inspector, "clients"):
        op.drop_index("ix_clients_firm_id", table_name="clients")

    # Drop column
    if "firm_id" in _column_names(inspector, "clients"):
        op.drop_column("clients", "firm_id")
