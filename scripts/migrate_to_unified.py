#!/usr/bin/env python3
"""
Unified Filing Platform - Database Migration Script

This script applies the database migration for the unified filing platform:
1. Backs up the existing database (optional)
2. Applies schema changes from migrations/20260121_001_unified_filing_sessions.sql
3. Verifies the migration was successful

Usage:
    python scripts/migrate_to_unified.py                    # Interactive mode
    python scripts/migrate_to_unified.py --auto-approve     # Skip confirmations
    python scripts/migrate_to_unified.py --no-backup        # Skip backup (not recommended)
    python scripts/migrate_to_unified.py --dry-run          # Preview changes only

WARNING: Run this during a low-traffic window
"""

import sqlite3
import sys
import os
import shutil
from datetime import datetime
from pathlib import Path
import argparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "tax_returns.db"
MIGRATION_FILE = PROJECT_ROOT / "migrations" / "20260121_001_unified_filing_sessions.sql"
BACKUP_DIR = PROJECT_ROOT / "backups"


def create_backup(db_path: Path) -> Path:
    """
    Create a backup of the database.

    Args:
        db_path: Path to database file

    Returns:
        Path to backup file
    """
    if not db_path.exists():
        logger.warning(f"Database {db_path} does not exist, skipping backup")
        return None

    # Create backups directory
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Generate backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"tax_returns_backup_{timestamp}.db"

    # Copy database
    logger.info(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)

    # Verify backup
    if not backup_path.exists():
        raise Exception("Backup file was not created")

    backup_size = backup_path.stat().st_size
    original_size = db_path.stat().st_size

    if backup_size != original_size:
        raise Exception(f"Backup size mismatch: {backup_size} vs {original_size}")

    logger.info(f"✓ Backup created successfully ({backup_size} bytes)")
    return backup_path


def load_migration_sql(migration_file: Path) -> str:
    """
    Load migration SQL from file.

    Args:
        migration_file: Path to migration file

    Returns:
        SQL content
    """
    if not migration_file.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_file}")

    with open(migration_file, 'r') as f:
        sql = f.read()

    logger.info(f"✓ Loaded migration SQL ({len(sql)} chars)")
    return sql


def apply_migration(db_path: Path, sql: str, dry_run: bool = False) -> None:
    """
    Apply migration SQL to database.

    Args:
        db_path: Path to database
        sql: SQL to execute
        dry_run: If True, don't actually modify database
    """
    if dry_run:
        logger.info("=== DRY RUN MODE ===")
        logger.info("Would execute the following SQL:")
        logger.info("-" * 80)
        logger.info(sql)
        logger.info("-" * 80)
        return

    # Ensure database directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect and apply migration
    logger.info(f"Applying migration to {db_path}")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Split SQL into statements (simple split on semicolon)
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

        for i, statement in enumerate(statements, 1):
            try:
                logger.debug(f"Executing statement {i}/{len(statements)}")
                cursor.execute(statement)
            except sqlite3.OperationalError as e:
                # Ignore "duplicate column" errors (already migrated)
                if "duplicate column name" in str(e).lower():
                    logger.warning(f"Column already exists (skipping): {e}")
                    continue
                # Ignore "already exists" for tables/indexes
                elif "already exists" in str(e).lower():
                    logger.warning(f"Object already exists (skipping): {e}")
                    continue
                else:
                    raise

        conn.commit()
        logger.info(f"✓ Migration applied successfully ({len(statements)} statements)")


def verify_migration(db_path: Path) -> bool:
    """
    Verify migration was successful by checking for new columns/tables.

    Args:
        db_path: Path to database

    Returns:
        True if verification passed
    """
    logger.info("Verifying migration...")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check for new columns in session_states
        cursor.execute("PRAGMA table_info(session_states)")
        columns = {row[1] for row in cursor.fetchall()}

        required_columns = {"user_id", "is_anonymous", "workflow_type", "return_id"}
        missing = required_columns - columns

        if missing:
            logger.error(f"✗ Missing columns in session_states: {missing}")
            return False

        logger.info(f"✓ All required columns present in session_states")

        # Check for new table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='session_transfers'
        """)
        if not cursor.fetchone():
            logger.error("✗ session_transfers table not found")
            return False

        logger.info("✓ session_transfers table exists")

        # Check for indexes
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_session_user'
        """)
        if not cursor.fetchone():
            logger.warning("⚠ idx_session_user index not found (performance may be affected)")
        else:
            logger.info("✓ Indexes created")

        logger.info("✓ Migration verification passed")
        return True


def get_database_stats(db_path: Path) -> dict:
    """Get statistics about the database."""
    if not db_path.exists():
        return {}

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        stats = {}

        # Count sessions
        cursor.execute("SELECT COUNT(*) FROM session_states")
        stats["total_sessions"] = cursor.fetchone()[0]

        # Count sessions with user_id
        cursor.execute("SELECT COUNT(*) FROM session_states WHERE user_id IS NOT NULL")
        stats["authenticated_sessions"] = cursor.fetchone()[0]

        # Count sessions by workflow type
        cursor.execute("""
            SELECT workflow_type, COUNT(*)
            FROM session_states
            WHERE workflow_type IS NOT NULL
            GROUP BY workflow_type
        """)
        stats["by_workflow"] = dict(cursor.fetchall())

        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Apply unified filing platform database migration"
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip confirmation prompts"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup (not recommended)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_PATH,
        help=f"Path to database file (default: {DB_PATH})"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("UNIFIED FILING PLATFORM - DATABASE MIGRATION")
    logger.info("=" * 80)

    # Display current stats
    if args.db_path.exists():
        logger.info("\nCurrent database stats:")
        stats = get_database_stats(args.db_path)
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
    else:
        logger.info("\nNo existing database found - will create new database")

    # Confirm migration
    if not args.auto_approve and not args.dry_run:
        logger.info("\nThis will modify your database.")
        response = input("Continue? [y/N]: ")
        if response.lower() != 'y':
            logger.info("Migration cancelled")
            return 1

    try:
        # Step 1: Backup
        backup_path = None
        if not args.no_backup and not args.dry_run:
            backup_path = create_backup(args.db_path)

        # Step 2: Load migration SQL
        sql = load_migration_sql(MIGRATION_FILE)

        # Step 3: Apply migration
        apply_migration(args.db_path, sql, dry_run=args.dry_run)

        if args.dry_run:
            logger.info("\n✓ Dry run completed - no changes made")
            return 0

        # Step 4: Verify
        if not verify_migration(args.db_path):
            logger.error("\n✗ Migration verification failed!")
            if backup_path:
                logger.info(f"You can restore from backup: {backup_path}")
            return 1

        # Success!
        logger.info("\n" + "=" * 80)
        logger.info("✓ MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)

        if backup_path:
            logger.info(f"\nBackup saved to: {backup_path}")

        # Display new stats
        logger.info("\nUpdated database stats:")
        stats = get_database_stats(args.db_path)
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")

        logger.info("\nNext steps:")
        logger.info("1. Restart your web application")
        logger.info("2. Monitor logs for any errors")
        logger.info("3. Test the unified filing flow")

        return 0

    except Exception as e:
        logger.error(f"\n✗ Migration failed: {e}")
        logger.exception(e)

        if backup_path:
            logger.info(f"\nTo restore from backup:")
            logger.info(f"  cp {backup_path} {args.db_path}")

        return 1


if __name__ == "__main__":
    sys.exit(main())
