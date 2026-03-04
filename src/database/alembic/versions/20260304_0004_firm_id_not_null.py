"""Make firm_id NOT NULL on clients and tax_returns with backfill.

Revision ID: 20260304_0004
Revises: 20260304_0003
Create Date: 2026-03-04

Ensures every client and tax_return has a firm_id:
1. Backfills any remaining NULLs from related tables
2. Alters columns to NOT NULL
3. Changes FK ondelete from SET NULL to CASCADE
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "20260304_0004"
down_revision = "20260304_0003"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_names(inspector, table_name: str) -> set:
    if not _table_exists(inspector, table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _fk_names(inspector, table_name: str) -> set:
    if not _table_exists(inspector, table_name):
        return set()
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # =========================================================================
    # CLIENTS TABLE
    # =========================================================================
    if _table_exists(inspector, "clients") and "firm_id" in _column_names(inspector, "clients"):
        # Backfill: clients -> preparers -> users (email match)
        if _table_exists(inspector, "preparers") and _table_exists(inspector, "users"):
            op.execute(sa.text(
                "UPDATE clients c "
                "SET firm_id = u.firm_id "
                "FROM preparers p "
                "JOIN users u ON LOWER(p.email) = LOWER(u.email) "
                "WHERE c.preparer_id = p.preparer_id "
                "AND c.firm_id IS NULL "
                "AND u.firm_id IS NOT NULL"
            ))

        # Backfill: clients -> users (direct preparer_id = user_id)
        if _table_exists(inspector, "users"):
            op.execute(sa.text(
                "UPDATE clients c "
                "SET firm_id = u.firm_id "
                "FROM users u "
                "WHERE c.preparer_id = u.user_id "
                "AND c.firm_id IS NULL "
                "AND u.firm_id IS NOT NULL"
            ))

        # Backfill: any remaining NULLs get the first firm (safety net)
        op.execute(sa.text(
            "UPDATE clients "
            "SET firm_id = (SELECT firm_id FROM firms LIMIT 1) "
            "WHERE firm_id IS NULL"
        ))

        # Drop old FK, alter column, add new FK with CASCADE
        fks = _fk_names(inspector, "clients")
        if "fk_clients_firm_id" in fks:
            op.drop_constraint("fk_clients_firm_id", "clients", type_="foreignkey")

        op.alter_column("clients", "firm_id", nullable=False, existing_type=UUID(as_uuid=True))

        op.create_foreign_key(
            "fk_clients_firm_id",
            "clients", "firms",
            ["firm_id"], ["firm_id"],
            ondelete="CASCADE",
        )

    # =========================================================================
    # TAX_RETURNS TABLE
    # =========================================================================
    if _table_exists(inspector, "tax_returns") and "firm_id" in _column_names(inspector, "tax_returns"):
        # Backfill: tax_returns -> clients (get firm_id from the client)
        if _table_exists(inspector, "clients"):
            op.execute(sa.text(
                "UPDATE tax_returns tr "
                "SET firm_id = c.firm_id "
                "FROM clients c "
                "WHERE tr.client_id = c.client_id "
                "AND tr.firm_id IS NULL "
                "AND c.firm_id IS NOT NULL"
            ))

        # Backfill: remaining NULLs get first firm (safety net)
        op.execute(sa.text(
            "UPDATE tax_returns "
            "SET firm_id = (SELECT firm_id FROM firms LIMIT 1) "
            "WHERE firm_id IS NULL"
        ))

        # Drop old FK, alter column, add new FK with CASCADE
        fks = _fk_names(inspector, "tax_returns")
        # Find any existing firm_id FK
        for fk in inspector.get_foreign_keys("tax_returns"):
            if fk.get("name") and "firm" in fk.get("name", ""):
                op.drop_constraint(fk["name"], "tax_returns", type_="foreignkey")

        op.alter_column("tax_returns", "firm_id", nullable=False, existing_type=UUID(as_uuid=True))

        op.create_foreign_key(
            "fk_tax_returns_firm_id",
            "tax_returns", "firms",
            ["firm_id"], ["firm_id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Revert tax_returns
    if _table_exists(inspector, "tax_returns") and "firm_id" in _column_names(inspector, "tax_returns"):
        fks = _fk_names(inspector, "tax_returns")
        if "fk_tax_returns_firm_id" in fks:
            op.drop_constraint("fk_tax_returns_firm_id", "tax_returns", type_="foreignkey")
        op.alter_column("tax_returns", "firm_id", nullable=True, existing_type=UUID(as_uuid=True))
        op.create_foreign_key(
            "fk_tax_returns_firm_id",
            "tax_returns", "firms",
            ["firm_id"], ["firm_id"],
            ondelete="SET NULL",
        )

    # Revert clients
    if _table_exists(inspector, "clients") and "firm_id" in _column_names(inspector, "clients"):
        fks = _fk_names(inspector, "clients")
        if "fk_clients_firm_id" in fks:
            op.drop_constraint("fk_clients_firm_id", "clients", type_="foreignkey")
        op.alter_column("clients", "firm_id", nullable=True, existing_type=UUID(as_uuid=True))
        op.create_foreign_key(
            "fk_clients_firm_id",
            "clients", "firms",
            ["firm_id"], ["firm_id"],
            ondelete="SET NULL",
        )
