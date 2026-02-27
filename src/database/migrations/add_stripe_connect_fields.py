#!/usr/bin/env python3
"""
Migration: Add Stripe Connect fields to cpa_profiles table.

Run with: python src/database/migrations/add_stripe_connect_fields.py
"""

import re
import sqlite3
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_db_path() -> str:
    """Get database path."""
    return os.environ.get(
        "DATABASE_PATH",
        str(Path(__file__).parent.parent / "jorss_gbo.db")
    )


def run_migration():
    """Run migration to add Stripe Connect fields."""
    db_path = get_db_path()
    print(f"Database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(cpa_profiles)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        columns_to_add = [
            ("stripe_account_id", "TEXT"),
            ("stripe_connected_at", "TEXT"),
            ("payment_settings", "TEXT"),  # JSON field
        ]

        _safe_ident = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
        for column_name, column_type in columns_to_add:
            if not _safe_ident.match(column_name):
                raise ValueError(f"Invalid column name: {column_name!r}")
            if column_name not in existing_columns:
                print(f"Adding column: {column_name} ({column_type})")
                cursor.execute(f"ALTER TABLE cpa_profiles ADD COLUMN {column_name} {column_type}")
            else:
                print(f"Column already exists: {column_name}")

        # Create stripe_connect_states table for OAuth state tokens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stripe_connect_states (
                state_token TEXT PRIMARY KEY,
                cpa_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (cpa_id) REFERENCES cpa_profiles(cpa_id)
            )
        """)
        print("Created table: stripe_connect_states")

        # Create cpa_payments table for tracking payments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cpa_payments (
                payment_id TEXT PRIMARY KEY,
                cpa_id TEXT NOT NULL,
                client_id TEXT,
                stripe_payment_intent_id TEXT,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                platform_fee REAL DEFAULT 0,
                net_amount REAL,
                status TEXT DEFAULT 'pending',
                description TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (cpa_id) REFERENCES cpa_profiles(cpa_id)
            )
        """)
        print("Created table: cpa_payments")

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cpa_payments_cpa_id
            ON cpa_payments(cpa_id, created_at DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cpa_payments_client
            ON cpa_payments(client_id)
        """)
        print("Created indexes for cpa_payments")

        conn.commit()
        print("\nMigration completed successfully!")

    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
