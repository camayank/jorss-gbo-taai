#!/usr/bin/env python3
"""
Test script to verify database migration worked correctly.

Usage:
    python migrations/test_migration.py
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "tax_filing.db"


def test_migration():
    """Test that migration columns exist and work."""
    print("Testing database migration...")
    print(f"Database: {DB_PATH}\n")

    if not DB_PATH.exists():
        print("❌ Database not found. Please run the application first.")
        return False

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Test 1: Check session_states columns
    print("Test 1: Checking session_states schema...")
    cursor.execute("PRAGMA table_info(session_states)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    required_columns = {
        'session_id': 'TEXT',
        'user_id': 'TEXT',
        'is_anonymous': 'INTEGER',
        'workflow_type': 'TEXT',
        'return_id': 'TEXT'
    }

    all_present = True
    for col, col_type in required_columns.items():
        if col in columns:
            print(f"  ✅ {col} ({columns[col]})")
        else:
            print(f"  ❌ {col} MISSING")
            all_present = False

    if not all_present:
        print("\n❌ Migration not applied. Run: python migrations/run_migration.py")
        return False

    # Test 2: Check indexes
    print("\nTest 2: Checking indexes...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='session_states'")
    indexes = [row[0] for row in cursor.fetchall()]

    required_indexes = ['idx_session_user', 'idx_session_workflow', 'idx_session_return']
    for idx in required_indexes:
        if idx in indexes:
            print(f"  ✅ {idx}")
        else:
            print(f"  ⚠️  {idx} missing (migration may be partial)")

    # Test 3: Check session_transfers table
    print("\nTest 3: Checking session_transfers table...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_transfers'")
    if cursor.fetchone():
        print("  ✅ session_transfers table exists")
    else:
        print("  ❌ session_transfers table missing")
        return False

    # Test 4: Test insert with new columns
    print("\nTest 4: Testing insert with new columns...")
    try:
        cursor.execute("""
            INSERT INTO session_states (
                session_id, tenant_id, session_type,
                created_at, last_activity, expires_at,
                data_json, metadata_json,
                user_id, is_anonymous, workflow_type, return_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'test_session_migration',
            'default',
            'agent',
            '2026-01-21T00:00:00',
            '2026-01-21T00:00:00',
            '2026-01-22T00:00:00',
            '{}',
            '{}',
            'user_123',
            0,  # not anonymous
            'express',
            'return_456'
        ))

        # Query it back
        cursor.execute("""
            SELECT user_id, is_anonymous, workflow_type, return_id
            FROM session_states
            WHERE session_id = 'test_session_migration'
        """)
        row = cursor.fetchone()

        if row and row[0] == 'user_123' and row[1] == 0 and row[2] == 'express' and row[3] == 'return_456':
            print("  ✅ Insert and query successful")
            print(f"    user_id: {row[0]}")
            print(f"    is_anonymous: {row[1]}")
            print(f"    workflow_type: {row[2]}")
            print(f"    return_id: {row[3]}")

            # Clean up test record
            cursor.execute("DELETE FROM session_states WHERE session_id = 'test_session_migration'")
            conn.commit()
        else:
            print("  ❌ Query returned unexpected values")
            return False

    except sqlite3.Error as e:
        print(f"  ❌ Insert failed: {e}")
        return False

    # Test 5: Check version column in session_tax_returns
    print("\nTest 5: Checking session_tax_returns.version column...")
    cursor.execute("PRAGMA table_info(session_tax_returns)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    if 'version' in columns:
        print(f"  ✅ version column exists ({columns['version']})")
    else:
        print("  ❌ version column missing")
        return False

    conn.close()

    print("\n" + "="*60)
    print("✅ All migration tests passed!")
    print("="*60)
    return True


if __name__ == "__main__":
    success = test_migration()
    sys.exit(0 if success else 1)
