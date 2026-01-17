#!/usr/bin/env python3
"""
Migration Verification Script.

Verifies data integrity between SQLite and PostgreSQL databases after migration.
Performs:
- Row count comparison
- Sample data comparison
- Data type validation
- Checksum verification for JSON data

Usage:
    # Basic verification
    python scripts/verify_migration.py

    # Detailed verification with sample comparison
    python scripts/verify_migration.py --detailed

    # Generate JSON report
    python scripts/verify_migration.py --output report.json

    # Verify specific tables
    python scripts/verify_migration.py --tables tax_returns,clients
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import text, create_engine

from config.database import DatabaseSettings, get_database_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class TableVerification:
    """Verification result for a single table."""
    table_name: str
    sqlite_count: int = 0
    postgres_count: int = 0
    count_match: bool = False
    sample_size: int = 0
    sample_matches: int = 0
    sample_mismatches: int = 0
    missing_in_postgres: int = 0
    field_differences: List[Dict[str, Any]] = field(default_factory=list)
    checksum_match: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class VerificationReport:
    """Complete verification report."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sqlite_path: str = ""
    postgres_host: str = ""
    overall_status: str = "pending"
    tables_verified: int = 0
    tables_passed: int = 0
    tables_failed: int = 0
    total_sqlite_records: int = 0
    total_postgres_records: int = 0
    table_results: List[TableVerification] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "sqlite_path": self.sqlite_path,
            "postgres_host": self.postgres_host,
            "overall_status": self.overall_status,
            "summary": {
                "tables_verified": self.tables_verified,
                "tables_passed": self.tables_passed,
                "tables_failed": self.tables_failed,
                "total_sqlite_records": self.total_sqlite_records,
                "total_postgres_records": self.total_postgres_records,
            },
            "tables": [asdict(t) for t in self.table_results],
            "errors": self.errors,
        }


class MigrationVerifier:
    """
    Verifies data integrity between SQLite and PostgreSQL databases.
    """

    # Primary key columns by table
    PRIMARY_KEYS = {
        "tax_returns": "return_id",
        "clients": "client_id",
        "scenarios": "scenario_id",
        "scenario_comparisons": "comparison_id",
        "advisory_plans": "plan_id",
        "recommendations": "recommendation_id",
        "events": "event_id",
        "schema_migrations": "version",
    }

    # JSON columns by table
    JSON_COLUMNS = {
        "tax_returns": ["return_data"],
        "clients": ["preferences", "prior_year_carryovers", "prior_year_summary"],
        "scenarios": ["base_snapshot", "modifications", "result"],
        "scenario_comparisons": ["scenario_ids", "comparison_data"],
        "advisory_plans": [],
        "recommendations": ["action_steps", "irs_references"],
        "events": ["event_data", "metadata"],
    }

    def __init__(
        self,
        sqlite_path: Path,
        postgres_settings: DatabaseSettings,
        sample_size: int = 10,
    ):
        self.sqlite_path = sqlite_path
        self.postgres_settings = postgres_settings
        self.sample_size = sample_size

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

    def get_tables(self) -> List[str]:
        """Get list of tables to verify."""
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

    def verify_counts(self, table_name: str) -> Tuple[int, int]:
        """Get row counts for both databases."""
        sqlite_conn = self.connect_sqlite()
        pg_engine = self.connect_postgres()

        try:
            # SQLite count
            cursor = sqlite_conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            sqlite_count = cursor.fetchone()[0]

            # PostgreSQL count
            try:
                with pg_engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    pg_count = result.scalar()
            except Exception:
                pg_count = -1

            return sqlite_count, pg_count

        finally:
            sqlite_conn.close()
            pg_engine.dispose()

    def compute_json_checksum(self, data: Any) -> str:
        """Compute checksum for JSON data."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                pass

        # Sort keys for consistent hashing
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()

    def compare_values(self, sqlite_val: Any, pg_val: Any, is_json: bool = False) -> bool:
        """Compare two values, handling type differences."""
        # Handle None
        if sqlite_val is None and pg_val is None:
            return True
        if sqlite_val is None or pg_val is None:
            return False

        # Handle JSON
        if is_json:
            sqlite_data = sqlite_val
            pg_data = pg_val

            if isinstance(sqlite_val, str):
                try:
                    sqlite_data = json.loads(sqlite_val)
                except json.JSONDecodeError:
                    sqlite_data = sqlite_val

            if isinstance(pg_val, str):
                try:
                    pg_data = json.loads(pg_val)
                except json.JSONDecodeError:
                    pg_data = pg_val

            return self.compute_json_checksum(sqlite_data) == self.compute_json_checksum(pg_data)

        # Handle numeric
        if isinstance(sqlite_val, (int, float)) and isinstance(pg_val, (int, float)):
            return abs(float(sqlite_val) - float(pg_val)) < 0.001

        # Handle boolean
        if isinstance(pg_val, bool):
            return bool(sqlite_val) == pg_val

        # String comparison
        return str(sqlite_val) == str(pg_val)

    def verify_sample(
        self,
        table_name: str,
    ) -> Tuple[int, int, int, List[Dict[str, Any]]]:
        """
        Compare sample records between databases.

        Returns:
            (matches, mismatches, missing_in_pg, differences)
        """
        sqlite_conn = self.connect_sqlite()
        pg_engine = self.connect_postgres()

        matches = 0
        mismatches = 0
        missing = 0
        differences = []

        try:
            cursor = sqlite_conn.cursor()

            # Get primary key column
            pk_col = self.PRIMARY_KEYS.get(table_name, "id")

            # Get JSON columns
            json_cols = self.JSON_COLUMNS.get(table_name, [])

            # Get sample records
            cursor.execute(f"SELECT * FROM {table_name} LIMIT ?", (self.sample_size,))
            columns = [desc[0] for desc in cursor.description]

            for row in cursor.fetchall():
                sqlite_record = dict(zip(columns, row))
                record_id = sqlite_record.get(pk_col)

                # Get PostgreSQL record
                with pg_engine.connect() as conn:
                    result = conn.execute(
                        text(f"SELECT * FROM {table_name} WHERE {pk_col} = :id"),
                        {"id": record_id}
                    )
                    pg_row = result.fetchone()

                if not pg_row:
                    missing += 1
                    differences.append({
                        "id": record_id,
                        "issue": "missing_in_postgres",
                    })
                    continue

                pg_record = dict(pg_row._mapping)

                # Compare each column
                record_match = True
                for col in columns:
                    sqlite_val = sqlite_record[col]
                    pg_val = pg_record.get(col)

                    is_json = col in json_cols
                    if not self.compare_values(sqlite_val, pg_val, is_json):
                        record_match = False
                        differences.append({
                            "id": record_id,
                            "column": col,
                            "sqlite": str(sqlite_val)[:100],
                            "postgres": str(pg_val)[:100],
                        })

                if record_match:
                    matches += 1
                else:
                    mismatches += 1

            return matches, mismatches, missing, differences

        finally:
            sqlite_conn.close()
            pg_engine.dispose()

    def verify_table(self, table_name: str, detailed: bool = False) -> TableVerification:
        """Verify a single table."""
        result = TableVerification(table_name=table_name)

        try:
            # Verify counts
            result.sqlite_count, result.postgres_count = self.verify_counts(table_name)
            result.count_match = result.sqlite_count == result.postgres_count

            if result.postgres_count == -1:
                result.error = "Table does not exist in PostgreSQL"
                return result

            # Sample comparison if requested
            if detailed and result.sqlite_count > 0:
                result.sample_size = min(self.sample_size, result.sqlite_count)
                matches, mismatches, missing, diffs = self.verify_sample(table_name)
                result.sample_matches = matches
                result.sample_mismatches = mismatches
                result.missing_in_postgres = missing
                result.field_differences = diffs[:10]  # Limit stored differences

        except Exception as e:
            result.error = str(e)

        return result

    def run(
        self,
        tables: Optional[List[str]] = None,
        detailed: bool = False,
    ) -> VerificationReport:
        """
        Run verification.

        Args:
            tables: List of tables to verify (None for all)
            detailed: Whether to do sample comparison

        Returns:
            VerificationReport with results
        """
        report = VerificationReport(
            sqlite_path=str(self.sqlite_path),
            postgres_host=self.postgres_settings.host if self.postgres_settings.is_postgres else "sqlite",
        )

        # Get tables to verify
        available_tables = self.get_tables()
        if tables:
            tables_to_verify = [t for t in tables if t in available_tables]
        else:
            tables_to_verify = available_tables

        logger.info(f"Verifying {len(tables_to_verify)} tables...")

        all_passed = True
        for table_name in tables_to_verify:
            logger.info(f"  Verifying {table_name}...")
            result = self.verify_table(table_name, detailed=detailed)
            report.table_results.append(result)
            report.tables_verified += 1
            report.total_sqlite_records += result.sqlite_count
            report.total_postgres_records += max(0, result.postgres_count)

            if result.count_match and not result.error:
                report.tables_passed += 1
                if result.missing_in_postgres == 0 and result.sample_mismatches == 0:
                    logger.info(f"    ✓ {table_name}: OK ({result.sqlite_count} records)")
                else:
                    logger.warning(
                        f"    ⚠ {table_name}: Counts match but {result.sample_mismatches} sample mismatches"
                    )
                    all_passed = False
            else:
                report.tables_failed += 1
                all_passed = False
                if result.error:
                    logger.error(f"    ✗ {table_name}: {result.error}")
                    report.errors.append(f"{table_name}: {result.error}")
                else:
                    logger.error(
                        f"    ✗ {table_name}: Count mismatch "
                        f"(SQLite: {result.sqlite_count}, PostgreSQL: {result.postgres_count})"
                    )

        report.overall_status = "pass" if all_passed else "fail"
        return report


def main():
    parser = argparse.ArgumentParser(
        description="Verify migration from SQLite to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "tax_returns.db",
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Perform detailed sample comparison",
    )
    parser.add_argument(
        "--tables",
        type=str,
        help="Comma-separated list of tables to verify",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10,
        help="Number of records to sample for comparison (default: 10)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON report file",
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
    except Exception as e:
        logger.error(f"Failed to get database settings: {e}")
        sys.exit(1)

    # Parse tables
    tables = None
    if args.tables:
        tables = [t.strip() for t in args.tables.split(",")]

    # Check SQLite exists
    if not args.sqlite_path.exists():
        logger.error(f"SQLite database not found: {args.sqlite_path}")
        sys.exit(1)

    print("=" * 60)
    print("Migration Verification")
    print("=" * 60)
    print(f"Source: {args.sqlite_path}")
    print(f"Target: {postgres_settings.host if postgres_settings.is_postgres else 'sqlite'}:{postgres_settings.name}")
    print(f"Mode:   {'Detailed' if args.detailed else 'Basic'}")
    print("=" * 60)

    # Run verification
    verifier = MigrationVerifier(
        sqlite_path=args.sqlite_path,
        postgres_settings=postgres_settings,
        sample_size=args.sample_size,
    )

    report = verifier.run(tables=tables, detailed=args.detailed)

    # Print summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"Tables Verified: {report.tables_verified}")
    print(f"Tables Passed:   {report.tables_passed}")
    print(f"Tables Failed:   {report.tables_failed}")
    print(f"Total Records:   SQLite={report.total_sqlite_records}, PostgreSQL={report.total_postgres_records}")
    print(f"Overall Status:  {report.overall_status.upper()}")

    if report.errors:
        print("\nErrors:")
        for error in report.errors:
            print(f"  - {error}")

    # Save report if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nReport saved to: {args.output}")

    sys.exit(0 if report.overall_status == "pass" else 1)


if __name__ == "__main__":
    main()
