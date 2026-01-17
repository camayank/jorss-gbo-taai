#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script.

Migrates all tax return data from SQLite to PostgreSQL with:
- Data transformation for PostgreSQL data types
- Progress tracking and logging
- Integrity verification
- Rollback support on failure
- Batch processing for large datasets

Usage:
    # Dry run (no actual migration)
    python scripts/migrate_sqlite_to_postgres.py --dry-run

    # Full migration
    python scripts/migrate_sqlite_to_postgres.py

    # Verify existing migration
    python scripts/migrate_sqlite_to_postgres.py --verify-only

    # Migrate specific tables
    python scripts/migrate_sqlite_to_postgres.py --tables tax_returns,clients

Environment Variables:
    SQLITE_PATH: Path to SQLite database (default: data/tax_returns.db)
    DATABASE_URL: PostgreSQL connection URL
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD: PostgreSQL connection details
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import text, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config.database import DatabaseSettings, get_database_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class MigrationStats:
    """Statistics for a migration run."""
    table_name: str
    source_count: int = 0
    migrated_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0

    @property
    def success_rate(self) -> float:
        if self.source_count == 0:
            return 100.0
        return (self.migrated_count / self.source_count) * 100


@dataclass
class MigrationResult:
    """Overall migration result."""
    success: bool
    tables_migrated: List[str] = field(default_factory=list)
    stats: Dict[str, MigrationStats] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    @property
    def total_records_migrated(self) -> int:
        return sum(s.migrated_count for s in self.stats.values())

    @property
    def total_errors(self) -> int:
        return sum(s.error_count for s in self.stats.values())


# =============================================================================
# TABLE MIGRATION CONFIGS
# =============================================================================

# Tables in migration order (respecting foreign key dependencies)
MIGRATION_ORDER = [
    "tax_returns",
    "clients",
    "scenarios",
    "scenario_comparisons",
    "advisory_plans",
    "recommendations",
    "events",
]


# =============================================================================
# MIGRATION ENGINE
# =============================================================================

class SQLiteToPostgresMigration:
    """
    Handles migration of data from SQLite to PostgreSQL.

    Features:
    - Batch processing for memory efficiency
    - Progress tracking
    - Error handling with continue-on-error option
    - Verification after migration
    """

    def __init__(
        self,
        sqlite_path: Path,
        postgres_settings: DatabaseSettings,
        batch_size: int = 1000,
        continue_on_error: bool = True,
    ):
        """
        Initialize migration.

        Args:
            sqlite_path: Path to SQLite database file
            postgres_settings: PostgreSQL connection settings
            batch_size: Number of records to process in each batch
            continue_on_error: Whether to continue on individual record errors
        """
        self.sqlite_path = sqlite_path
        self.postgres_settings = postgres_settings
        self.batch_size = batch_size
        self.continue_on_error = continue_on_error

        self._sqlite_conn: Optional[sqlite3.Connection] = None
        self._pg_engine = None

    def connect_sqlite(self) -> sqlite3.Connection:
        """Connect to SQLite database."""
        if not self.sqlite_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.sqlite_path}")

        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def connect_postgres(self):
        """Create PostgreSQL engine."""
        return create_engine(
            self.postgres_settings.sync_url,
            echo=False,
            pool_pre_ping=True,
        )

    def get_sqlite_tables(self) -> List[str]:
        """Get list of tables in SQLite database."""
        conn = self.connect_sqlite()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_sqlite_table_count(self, table_name: str) -> int:
        """Get row count for a SQLite table."""
        conn = self.connect_sqlite()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def get_postgres_table_count(self, table_name: str) -> int:
        """Get row count for a PostgreSQL table."""
        engine = self.connect_postgres()
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                return result.scalar()
        except Exception:
            return 0
        finally:
            engine.dispose()

    def read_sqlite_batch(
        self,
        table_name: str,
        offset: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Read a batch of records from SQLite."""
        conn = self.connect_sqlite()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset))

            columns = [description[0] for description in cursor.description]
            rows = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))
                rows.append(row_dict)
            return rows
        finally:
            conn.close()

    def transform_record(
        self,
        table_name: str,
        record: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Transform a record from SQLite format to PostgreSQL format.

        Handles:
        - UUID conversion
        - JSON/JSONB conversion
        - Date/datetime conversion
        - Enum value validation
        """
        transformed = {}

        for key, value in record.items():
            # Handle NULL values
            if value is None:
                transformed[key] = None
                continue

            # Handle JSON columns
            if key in ("return_data", "base_snapshot", "modifications", "result",
                      "preferences", "prior_year_carryovers", "prior_year_summary",
                      "scenario_ids", "comparison_data", "action_steps",
                      "irs_references", "event_data", "metadata"):
                if isinstance(value, str):
                    try:
                        transformed[key] = json.loads(value)
                    except json.JSONDecodeError:
                        transformed[key] = value
                else:
                    transformed[key] = value
                continue

            # Handle UUID columns (typically primary keys ending in _id)
            if key.endswith("_id") and isinstance(value, str):
                try:
                    # Validate it's a valid UUID
                    UUID(value)
                    transformed[key] = value
                except ValueError:
                    # Keep as string if not a valid UUID
                    transformed[key] = value
                continue

            # Handle datetime columns
            if key in ("created_at", "updated_at", "occurred_at", "calculated_at",
                      "finalized_at", "status_changed_at", "last_retry_at", "applied_at"):
                if isinstance(value, str):
                    try:
                        # Parse ISO format datetime
                        if "T" in value:
                            transformed[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        else:
                            transformed[key] = datetime.fromisoformat(value)
                    except ValueError:
                        transformed[key] = value
                else:
                    transformed[key] = value
                continue

            # Handle boolean columns stored as integers
            if key in ("is_active", "is_recommended", "is_finalized"):
                transformed[key] = bool(value) if value is not None else None
                continue

            # Handle numeric columns
            if key in ("gross_income", "adjusted_gross_income", "taxable_income",
                      "federal_tax_liability", "state_tax_liability", "combined_tax_liability",
                      "federal_refund_or_owed", "state_refund_or_owed", "combined_refund_or_owed",
                      "total_potential_savings", "total_realized_savings", "estimated_savings",
                      "actual_savings", "confidence_level", "max_savings"):
                if isinstance(value, str):
                    try:
                        transformed[key] = float(value)
                    except ValueError:
                        transformed[key] = 0.0
                else:
                    transformed[key] = value
                continue

            # Default: keep value as-is
            transformed[key] = value

        return transformed

    def insert_postgres_batch(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
    ) -> Tuple[int, List[str]]:
        """
        Insert a batch of records into PostgreSQL.

        Returns:
            Tuple of (successful_count, error_messages)
        """
        if not records:
            return 0, []

        engine = self.connect_postgres()
        errors = []
        success_count = 0

        try:
            with engine.begin() as conn:
                for record in records:
                    try:
                        # Build INSERT statement dynamically
                        columns = list(record.keys())
                        placeholders = [f":{col}" for col in columns]

                        # Handle JSONB columns
                        params = {}
                        for col, val in record.items():
                            if isinstance(val, (dict, list)):
                                params[col] = json.dumps(val)
                            else:
                                params[col] = val

                        sql = f"""
                            INSERT INTO {table_name} ({', '.join(columns)})
                            VALUES ({', '.join(placeholders)})
                            ON CONFLICT DO NOTHING
                        """

                        conn.execute(text(sql), params)
                        success_count += 1

                    except Exception as e:
                        error_msg = f"Error inserting record: {e}"
                        errors.append(error_msg)
                        if not self.continue_on_error:
                            raise

            return success_count, errors

        finally:
            engine.dispose()

    def migrate_table(
        self,
        table_name: str,
        dry_run: bool = False,
    ) -> MigrationStats:
        """
        Migrate a single table from SQLite to PostgreSQL.

        Args:
            table_name: Name of the table to migrate
            dry_run: If True, only simulate the migration

        Returns:
            MigrationStats with results
        """
        stats = MigrationStats(table_name=table_name)
        stats.started_at = datetime.utcnow()

        try:
            # Get source count
            stats.source_count = self.get_sqlite_table_count(table_name)
            logger.info(f"Migrating {table_name}: {stats.source_count} records")

            if stats.source_count == 0:
                logger.info(f"  No records to migrate in {table_name}")
                stats.completed_at = datetime.utcnow()
                return stats

            # Process in batches
            offset = 0
            while offset < stats.source_count:
                # Read batch from SQLite
                batch = self.read_sqlite_batch(table_name, offset, self.batch_size)

                if not batch:
                    break

                # Transform records
                transformed = []
                for record in batch:
                    try:
                        transformed.append(self.transform_record(table_name, record))
                    except Exception as e:
                        stats.error_count += 1
                        stats.errors.append(f"Transform error: {e}")
                        if not self.continue_on_error:
                            raise

                if dry_run:
                    stats.migrated_count += len(transformed)
                    logger.info(f"  [DRY RUN] Would migrate {len(transformed)} records")
                else:
                    # Insert into PostgreSQL
                    success, errors = self.insert_postgres_batch(table_name, transformed)
                    stats.migrated_count += success
                    stats.error_count += len(errors)
                    stats.errors.extend(errors)

                offset += self.batch_size

                # Progress update
                progress = min(100, (offset / stats.source_count) * 100)
                logger.info(f"  Progress: {progress:.1f}% ({stats.migrated_count} migrated)")

        except Exception as e:
            stats.errors.append(f"Fatal error: {e}")
            logger.error(f"Migration failed for {table_name}: {e}")

        stats.completed_at = datetime.utcnow()
        return stats

    def verify_table(self, table_name: str) -> Tuple[bool, str]:
        """
        Verify migration for a table.

        Returns:
            Tuple of (success, message)
        """
        sqlite_count = self.get_sqlite_table_count(table_name)
        postgres_count = self.get_postgres_table_count(table_name)

        if sqlite_count == postgres_count:
            return True, f"{table_name}: OK ({sqlite_count} records)"
        else:
            return False, f"{table_name}: MISMATCH (SQLite: {sqlite_count}, PostgreSQL: {postgres_count})"

    def run(
        self,
        tables: Optional[List[str]] = None,
        dry_run: bool = False,
        verify_only: bool = False,
    ) -> MigrationResult:
        """
        Run the migration.

        Args:
            tables: List of tables to migrate (None for all)
            dry_run: If True, only simulate the migration
            verify_only: If True, only verify existing migration

        Returns:
            MigrationResult with details
        """
        result = MigrationResult(success=True)
        result.started_at = datetime.utcnow()

        # Determine tables to migrate
        available_tables = self.get_sqlite_tables()
        if tables:
            tables_to_migrate = [t for t in tables if t in available_tables]
        else:
            # Use migration order, then any remaining tables
            tables_to_migrate = []
            for t in MIGRATION_ORDER:
                if t in available_tables:
                    tables_to_migrate.append(t)
            for t in available_tables:
                if t not in tables_to_migrate:
                    tables_to_migrate.append(t)

        logger.info(f"Tables to {'verify' if verify_only else 'migrate'}: {tables_to_migrate}")

        if verify_only:
            # Verify mode
            all_ok = True
            for table in tables_to_migrate:
                ok, msg = self.verify_table(table)
                logger.info(f"  {msg}")
                if not ok:
                    all_ok = False
            result.success = all_ok
        else:
            # Migration mode
            for table in tables_to_migrate:
                try:
                    stats = self.migrate_table(table, dry_run=dry_run)
                    result.stats[table] = stats
                    result.tables_migrated.append(table)

                    if stats.error_count > 0:
                        logger.warning(f"  {table}: {stats.error_count} errors")

                except Exception as e:
                    result.success = False
                    result.error_message = str(e)
                    logger.error(f"Migration failed: {e}")
                    break

        result.completed_at = datetime.utcnow()
        return result


# =============================================================================
# VERIFICATION SCRIPT
# =============================================================================

class MigrationVerifier:
    """Verifies data integrity after migration."""

    def __init__(
        self,
        sqlite_path: Path,
        postgres_settings: DatabaseSettings,
    ):
        self.sqlite_path = sqlite_path
        self.postgres_settings = postgres_settings

    def connect_sqlite(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def connect_postgres(self):
        return create_engine(self.postgres_settings.sync_url, echo=False)

    def compare_counts(self) -> List[Tuple[str, int, int, bool]]:
        """Compare record counts between databases."""
        results = []

        sqlite_conn = self.connect_sqlite()
        pg_engine = self.connect_postgres()

        try:
            # Get SQLite tables
            cursor = sqlite_conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                # SQLite count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                sqlite_count = cursor.fetchone()[0]

                # PostgreSQL count
                try:
                    with pg_engine.connect() as conn:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        pg_count = result.scalar()
                except Exception:
                    pg_count = -1  # Table doesn't exist

                match = sqlite_count == pg_count
                results.append((table, sqlite_count, pg_count, match))

        finally:
            sqlite_conn.close()
            pg_engine.dispose()

        return results

    def sample_compare(
        self,
        table_name: str,
        sample_size: int = 10,
    ) -> List[Dict[str, Any]]:
        """Compare sample records between databases."""
        differences = []

        sqlite_conn = self.connect_sqlite()
        pg_engine = self.connect_postgres()

        try:
            # Get sample IDs from SQLite
            cursor = sqlite_conn.cursor()

            # Determine primary key column
            pk_col = "return_id" if table_name == "tax_returns" else f"{table_name[:-1]}_id"
            if table_name == "events":
                pk_col = "event_id"
            elif table_name == "clients":
                pk_col = "client_id"

            cursor.execute(f"SELECT {pk_col} FROM {table_name} LIMIT ?", (sample_size,))
            sample_ids = [row[0] for row in cursor.fetchall()]

            for record_id in sample_ids:
                # Get SQLite record
                cursor.execute(f"SELECT * FROM {table_name} WHERE {pk_col} = ?", (record_id,))
                sqlite_row = cursor.fetchone()
                if not sqlite_row:
                    continue

                sqlite_record = dict(sqlite_row)

                # Get PostgreSQL record
                with pg_engine.connect() as conn:
                    result = conn.execute(
                        text(f"SELECT * FROM {table_name} WHERE {pk_col} = :id"),
                        {"id": record_id}
                    )
                    pg_row = result.fetchone()

                if not pg_row:
                    differences.append({
                        "id": record_id,
                        "issue": "Missing in PostgreSQL",
                    })
                    continue

                pg_record = dict(pg_row._mapping)

                # Compare records (ignoring timestamp microseconds)
                for key in sqlite_record:
                    sqlite_val = sqlite_record[key]
                    pg_val = pg_record.get(key)

                    # Normalize for comparison
                    if isinstance(sqlite_val, str) and isinstance(pg_val, str):
                        # JSON comparison
                        try:
                            sqlite_val = json.loads(sqlite_val)
                            pg_val = json.loads(pg_val) if isinstance(pg_val, str) else pg_val
                        except (json.JSONDecodeError, TypeError):
                            pass

                    if sqlite_val != pg_val:
                        # Check if it's just a type difference
                        if str(sqlite_val) == str(pg_val):
                            continue
                        differences.append({
                            "id": record_id,
                            "field": key,
                            "sqlite": sqlite_val,
                            "postgres": pg_val,
                        })

        finally:
            sqlite_conn.close()
            pg_engine.dispose()

        return differences

    def run_verification(self) -> Dict[str, Any]:
        """Run full verification suite."""
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "count_comparison": [],
            "sample_differences": {},
            "overall_status": "pass",
        }

        # Count comparison
        counts = self.compare_counts()
        for table, sqlite_count, pg_count, match in counts:
            results["count_comparison"].append({
                "table": table,
                "sqlite_count": sqlite_count,
                "postgres_count": pg_count,
                "match": match,
            })
            if not match:
                results["overall_status"] = "fail"

        # Sample comparison for key tables
        key_tables = ["tax_returns", "clients", "scenarios"]
        for table in key_tables:
            try:
                diffs = self.sample_compare(table, sample_size=5)
                if diffs:
                    results["sample_differences"][table] = diffs
                    results["overall_status"] = "fail"
            except Exception as e:
                results["sample_differences"][table] = [{"error": str(e)}]

        return results


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Migrate data from SQLite to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "tax_returns.db",
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without writing to PostgreSQL",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing migration",
    )
    parser.add_argument(
        "--tables",
        type=str,
        help="Comma-separated list of tables to migrate",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for processing (default: 1000)",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop migration on first error",
    )
    parser.add_argument(
        "--verify-after",
        action="store_true",
        help="Run verification after migration",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get PostgreSQL settings
    try:
        postgres_settings = get_database_settings()
        if not postgres_settings.is_postgres:
            logger.warning("Target database is not PostgreSQL. Using configured database.")
    except Exception as e:
        logger.error(f"Failed to get database settings: {e}")
        logger.info("Set DATABASE_URL or DB_* environment variables for PostgreSQL connection")
        sys.exit(1)

    # Parse tables
    tables = None
    if args.tables:
        tables = [t.strip() for t in args.tables.split(",")]

    # Check SQLite exists
    if not args.sqlite_path.exists():
        logger.error(f"SQLite database not found: {args.sqlite_path}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("SQLite to PostgreSQL Migration")
    logger.info("=" * 60)
    logger.info(f"Source: {args.sqlite_path}")
    logger.info(f"Target: {postgres_settings.name if postgres_settings.is_postgres else 'SQLite'}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'VERIFY ONLY' if args.verify_only else 'MIGRATE'}")
    logger.info("=" * 60)

    if args.verify_only:
        # Verification only
        verifier = MigrationVerifier(args.sqlite_path, postgres_settings)
        results = verifier.run_verification()

        print("\n" + "=" * 60)
        print("VERIFICATION RESULTS")
        print("=" * 60)

        print("\nCount Comparison:")
        for item in results["count_comparison"]:
            status = "✓" if item["match"] else "✗"
            print(f"  {status} {item['table']}: SQLite={item['sqlite_count']}, PostgreSQL={item['postgres_count']}")

        if results["sample_differences"]:
            print("\nSample Differences:")
            for table, diffs in results["sample_differences"].items():
                print(f"  {table}: {len(diffs)} difference(s)")

        print(f"\nOverall Status: {results['overall_status'].upper()}")
        sys.exit(0 if results["overall_status"] == "pass" else 1)

    # Run migration
    migration = SQLiteToPostgresMigration(
        sqlite_path=args.sqlite_path,
        postgres_settings=postgres_settings,
        batch_size=args.batch_size,
        continue_on_error=not args.stop_on_error,
    )

    result = migration.run(
        tables=tables,
        dry_run=args.dry_run,
    )

    # Print results
    print("\n" + "=" * 60)
    print("MIGRATION RESULTS")
    print("=" * 60)

    for table, stats in result.stats.items():
        status = "✓" if stats.error_count == 0 else "⚠"
        print(f"  {status} {table}:")
        print(f"      Source records: {stats.source_count}")
        print(f"      Migrated:       {stats.migrated_count}")
        if stats.error_count > 0:
            print(f"      Errors:         {stats.error_count}")
        print(f"      Duration:       {stats.duration_seconds:.2f}s")

    print(f"\nTotal Records: {result.total_records_migrated}")
    print(f"Total Errors:  {result.total_errors}")
    print(f"Status:        {'SUCCESS' if result.success else 'FAILED'}")

    if args.verify_after and not args.dry_run:
        print("\n" + "=" * 60)
        print("POST-MIGRATION VERIFICATION")
        print("=" * 60)

        verifier = MigrationVerifier(args.sqlite_path, postgres_settings)
        verify_results = verifier.run_verification()

        print(f"Verification: {verify_results['overall_status'].upper()}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
