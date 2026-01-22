#!/usr/bin/env python3
"""
Database Migration Runner
Applies schema migrations to the SQLite database.

Usage:
    python migrations/run_migration.py [migration_file]

If no migration_file is specified, applies all pending migrations.
"""

import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime

# Get project root and database path
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "tax_filing.db"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def get_db_connection():
    """Get SQLite database connection."""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Please run the application first to create the database.")
        sys.exit(1)

    return sqlite3.connect(str(DB_PATH))


def create_migrations_table(conn):
    """Create migrations tracking table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id TEXT PRIMARY KEY,
            migration_file TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 1,
            error_message TEXT
        )
    """)
    conn.commit()


def is_migration_applied(conn, migration_file):
    """Check if a migration has already been applied."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM schema_migrations WHERE migration_file = ? AND success = 1",
        (migration_file,)
    )
    return cursor.fetchone()[0] > 0


def apply_migration(conn, migration_file):
    """Apply a single migration file."""
    print(f"\n{'='*60}")
    print(f"Applying migration: {migration_file}")
    print(f"{'='*60}")

    migration_path = MIGRATIONS_DIR / migration_file

    if not migration_path.exists():
        print(f"ERROR: Migration file not found: {migration_path}")
        return False

    # Read migration SQL
    with open(migration_path, 'r') as f:
        sql = f.read()

    # Split into individual statements (simple split by semicolon)
    statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

    cursor = conn.cursor()
    migration_id = f"{migration_file}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        # Execute each statement
        for i, statement in enumerate(statements, 1):
            print(f"  [{i}/{len(statements)}] Executing: {statement[:60]}...")
            cursor.execute(statement)

        # Record successful migration
        cursor.execute("""
            INSERT INTO schema_migrations (migration_id, migration_file, applied_at, success)
            VALUES (?, ?, ?, 1)
        """, (migration_id, migration_file, datetime.now().isoformat()))

        conn.commit()
        print(f"\n✅ Migration {migration_file} applied successfully!")
        return True

    except sqlite3.Error as e:
        # Record failed migration
        error_msg = str(e)
        print(f"\n❌ Migration failed: {error_msg}")

        cursor.execute("""
            INSERT INTO schema_migrations (migration_id, migration_file, applied_at, success, error_message)
            VALUES (?, ?, ?, 0, ?)
        """, (migration_id, migration_file, datetime.now().isoformat(), error_msg))

        conn.commit()
        return False


def get_pending_migrations(conn):
    """Get list of pending migration files."""
    all_migrations = sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql')])

    pending = []
    for migration in all_migrations:
        if not is_migration_applied(conn, migration):
            pending.append(migration)

    return pending


def show_migration_status(conn):
    """Show status of all migrations."""
    print("\n" + "="*60)
    print("Migration Status")
    print("="*60)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT migration_file, applied_at, success, error_message
        FROM schema_migrations
        ORDER BY applied_at
    """)

    applied_migrations = cursor.fetchall()

    if applied_migrations:
        print("\nApplied Migrations:")
        for migration_file, applied_at, success, error_msg in applied_migrations:
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"  {status} {migration_file} - {applied_at}")
            if error_msg:
                print(f"    Error: {error_msg}")
    else:
        print("\nNo migrations applied yet.")

    pending = get_pending_migrations(conn)
    if pending:
        print(f"\nPending Migrations: {len(pending)}")
        for migration in pending:
            print(f"  - {migration}")
    else:
        print("\n✅ All migrations up to date!")


def main():
    """Main migration runner."""
    print("Database Migration Runner")
    print(f"Database: {DB_PATH}")

    # Get database connection
    conn = get_db_connection()

    # Create migrations tracking table
    create_migrations_table(conn)

    # Check command line arguments
    if len(sys.argv) > 1:
        # Apply specific migration
        migration_file = sys.argv[1]

        if is_migration_applied(conn, migration_file):
            print(f"\n⚠️  Migration {migration_file} has already been applied.")
            print("Use --force to reapply (WARNING: This may cause errors)")
            show_migration_status(conn)
            sys.exit(0)

        success = apply_migration(conn, migration_file)
        sys.exit(0 if success else 1)

    else:
        # Apply all pending migrations
        pending = get_pending_migrations(conn)

        if not pending:
            print("\n✅ No pending migrations. Database is up to date!")
            show_migration_status(conn)
            sys.exit(0)

        print(f"\nFound {len(pending)} pending migration(s):")
        for migration in pending:
            print(f"  - {migration}")

        # Ask for confirmation
        response = input("\nApply all pending migrations? (yes/no): ").strip().lower()

        if response != 'yes':
            print("Migration cancelled.")
            sys.exit(0)

        # Apply each migration
        all_success = True
        for migration in pending:
            success = apply_migration(conn, migration)
            if not success:
                all_success = False
                print(f"\n❌ Stopping migration process due to error in {migration}")
                break

        # Show final status
        show_migration_status(conn)

        if all_success:
            print("\n✅ All migrations applied successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some migrations failed. Please review errors above.")
            sys.exit(1)


if __name__ == "__main__":
    main()
