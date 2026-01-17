"""
Tests for SQLite to PostgreSQL migration scripts.

Tests both the migration engine and verification tools.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_sqlite_db(tmp_path):
    """Create a temporary SQLite database with test data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tax_returns table
    cursor.execute("""
        CREATE TABLE tax_returns (
            return_id TEXT PRIMARY KEY,
            client_id TEXT,
            tax_year INTEGER,
            filing_status TEXT,
            return_data TEXT,
            gross_income REAL,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # Create clients table
    cursor.execute("""
        CREATE TABLE clients (
            client_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            preferences TEXT,
            is_active INTEGER,
            created_at TEXT
        )
    """)

    # Create scenarios table
    cursor.execute("""
        CREATE TABLE scenarios (
            scenario_id TEXT PRIMARY KEY,
            return_id TEXT,
            name TEXT,
            base_snapshot TEXT,
            modifications TEXT,
            result TEXT,
            created_at TEXT
        )
    """)

    # Create events table
    cursor.execute("""
        CREATE TABLE events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT,
            event_data TEXT,
            metadata TEXT,
            occurred_at TEXT
        )
    """)

    # Insert test data
    cursor.execute("""
        INSERT INTO tax_returns (
            return_id, client_id, tax_year, filing_status, return_data,
            gross_income, created_at, updated_at
        ) VALUES (
            '550e8400-e29b-41d4-a716-446655440000',
            '550e8400-e29b-41d4-a716-446655440001',
            2024, 'married_joint',
            '{"wages": 100000, "interest": 500}',
            100500.0,
            '2024-01-15T10:30:00',
            '2024-01-15T10:30:00'
        )
    """)

    cursor.execute("""
        INSERT INTO tax_returns (
            return_id, client_id, tax_year, filing_status, return_data,
            gross_income, created_at, updated_at
        ) VALUES (
            '550e8400-e29b-41d4-a716-446655440002',
            '550e8400-e29b-41d4-a716-446655440003',
            2024, 'single',
            '{"wages": 75000}',
            75000.0,
            '2024-02-20T14:00:00',
            '2024-02-20T14:00:00'
        )
    """)

    cursor.execute("""
        INSERT INTO clients (
            client_id, first_name, last_name, email, preferences,
            is_active, created_at
        ) VALUES (
            '550e8400-e29b-41d4-a716-446655440001',
            'John', 'Smith', 'john@example.com',
            '{"newsletter": true}',
            1,
            '2024-01-01T00:00:00'
        )
    """)

    cursor.execute("""
        INSERT INTO scenarios (
            scenario_id, return_id, name, base_snapshot, modifications, result, created_at
        ) VALUES (
            '550e8400-e29b-41d4-a716-446655440010',
            '550e8400-e29b-41d4-a716-446655440000',
            'Test Scenario',
            '{"agi": 100000}',
            '{"add_deduction": 5000}',
            '{"tax_saved": 1200}',
            '2024-01-16T09:00:00'
        )
    """)

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def mock_postgres_settings():
    """Create mock PostgreSQL settings."""
    settings = MagicMock()
    settings.sync_url = "postgresql://user:pass@localhost:5432/testdb"
    settings.is_postgres = True
    settings.host = "localhost"
    settings.name = "testdb"
    return settings


@pytest.fixture
def mock_sqlite_settings():
    """Create mock SQLite settings (for fallback)."""
    settings = MagicMock()
    settings.sync_url = "sqlite:///test.db"
    settings.is_postgres = False
    settings.host = None
    settings.name = "test.db"
    return settings


# =============================================================================
# MIGRATION STATS TESTS
# =============================================================================


class TestMigrationStats:
    """Tests for MigrationStats dataclass."""

    def test_duration_seconds_with_times(self):
        """Duration calculated correctly when times are set."""
        from migrate_sqlite_to_postgres import MigrationStats

        stats = MigrationStats(table_name="test")
        stats.started_at = datetime(2024, 1, 1, 10, 0, 0)
        stats.completed_at = datetime(2024, 1, 1, 10, 0, 30)

        assert stats.duration_seconds == 30.0

    def test_duration_seconds_without_times(self):
        """Duration is 0 when times are not set."""
        from migrate_sqlite_to_postgres import MigrationStats

        stats = MigrationStats(table_name="test")
        assert stats.duration_seconds == 0

    def test_success_rate_full(self):
        """Success rate is 100% when all records migrated."""
        from migrate_sqlite_to_postgres import MigrationStats

        stats = MigrationStats(
            table_name="test",
            source_count=100,
            migrated_count=100,
        )

        assert stats.success_rate == 100.0

    def test_success_rate_partial(self):
        """Success rate calculated correctly for partial migration."""
        from migrate_sqlite_to_postgres import MigrationStats

        stats = MigrationStats(
            table_name="test",
            source_count=100,
            migrated_count=75,
        )

        assert stats.success_rate == 75.0

    def test_success_rate_empty(self):
        """Success rate is 100% when source is empty."""
        from migrate_sqlite_to_postgres import MigrationStats

        stats = MigrationStats(
            table_name="test",
            source_count=0,
            migrated_count=0,
        )

        assert stats.success_rate == 100.0


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_total_records_migrated(self):
        """Total records summed correctly."""
        from migrate_sqlite_to_postgres import MigrationResult, MigrationStats

        result = MigrationResult(success=True)
        result.stats["table1"] = MigrationStats(table_name="table1", migrated_count=50)
        result.stats["table2"] = MigrationStats(table_name="table2", migrated_count=30)

        assert result.total_records_migrated == 80

    def test_total_errors(self):
        """Total errors summed correctly."""
        from migrate_sqlite_to_postgres import MigrationResult, MigrationStats

        result = MigrationResult(success=True)
        result.stats["table1"] = MigrationStats(table_name="table1", error_count=2)
        result.stats["table2"] = MigrationStats(table_name="table2", error_count=1)

        assert result.total_errors == 3


# =============================================================================
# SQLITE TO POSTGRES MIGRATION TESTS
# =============================================================================


class TestSQLiteToPostgresMigration:
    """Tests for SQLiteToPostgresMigration class."""

    def test_init(self, temp_sqlite_db, mock_postgres_settings):
        """Migration initializes with correct settings."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
            batch_size=500,
            continue_on_error=False,
        )

        assert migration.sqlite_path == temp_sqlite_db
        assert migration.batch_size == 500
        assert migration.continue_on_error is False

    def test_connect_sqlite_success(self, temp_sqlite_db, mock_postgres_settings):
        """SQLite connection succeeds with valid path."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        conn = migration.connect_sqlite()
        assert conn is not None
        conn.close()

    def test_connect_sqlite_not_found(self, tmp_path, mock_postgres_settings):
        """SQLite connection fails with invalid path."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=tmp_path / "nonexistent.db",
            postgres_settings=mock_postgres_settings,
        )

        with pytest.raises(FileNotFoundError):
            migration.connect_sqlite()

    def test_get_sqlite_tables(self, temp_sqlite_db, mock_postgres_settings):
        """SQLite tables retrieved correctly."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        tables = migration.get_sqlite_tables()

        assert "tax_returns" in tables
        assert "clients" in tables
        assert "scenarios" in tables
        assert "events" in tables

    def test_get_sqlite_table_count(self, temp_sqlite_db, mock_postgres_settings):
        """SQLite table count is correct."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        count = migration.get_sqlite_table_count("tax_returns")
        assert count == 2

        count = migration.get_sqlite_table_count("clients")
        assert count == 1

    def test_read_sqlite_batch(self, temp_sqlite_db, mock_postgres_settings):
        """SQLite batch read returns correct records."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        batch = migration.read_sqlite_batch("tax_returns", offset=0, limit=10)

        assert len(batch) == 2
        assert batch[0]["tax_year"] == 2024
        assert "return_data" in batch[0]

    def test_read_sqlite_batch_with_offset(self, temp_sqlite_db, mock_postgres_settings):
        """SQLite batch read respects offset."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        batch = migration.read_sqlite_batch("tax_returns", offset=1, limit=10)

        assert len(batch) == 1

    def test_transform_record_json_columns(self, temp_sqlite_db, mock_postgres_settings):
        """JSON columns are parsed correctly."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        record = {
            "return_id": "550e8400-e29b-41d4-a716-446655440000",
            "return_data": '{"wages": 100000}',
            "preferences": '{"newsletter": true}',
            "created_at": "2024-01-15T10:30:00",
        }

        transformed = migration.transform_record("tax_returns", record)

        assert transformed["return_data"] == {"wages": 100000}
        assert transformed["preferences"] == {"newsletter": True}

    def test_transform_record_uuid_columns(self, temp_sqlite_db, mock_postgres_settings):
        """UUID columns are preserved."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        record = {
            "return_id": "550e8400-e29b-41d4-a716-446655440000",
            "client_id": "550e8400-e29b-41d4-a716-446655440001",
        }

        transformed = migration.transform_record("tax_returns", record)

        assert transformed["return_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert transformed["client_id"] == "550e8400-e29b-41d4-a716-446655440001"

    def test_transform_record_datetime_columns(self, temp_sqlite_db, mock_postgres_settings):
        """Datetime columns are parsed correctly."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        record = {
            "return_id": "test",
            "created_at": "2024-01-15T10:30:00",
            "updated_at": "2024-01-15T10:30:00Z",
        }

        transformed = migration.transform_record("tax_returns", record)

        assert isinstance(transformed["created_at"], datetime)
        assert transformed["created_at"].year == 2024
        assert transformed["created_at"].month == 1
        assert transformed["created_at"].day == 15

    def test_transform_record_boolean_columns(self, temp_sqlite_db, mock_postgres_settings):
        """Boolean columns are converted correctly."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        record = {
            "client_id": "test",
            "is_active": 1,
            "is_recommended": 0,
        }

        transformed = migration.transform_record("clients", record)

        assert transformed["is_active"] is True
        assert transformed["is_recommended"] is False

    def test_transform_record_null_values(self, temp_sqlite_db, mock_postgres_settings):
        """NULL values are handled correctly."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        record = {
            "return_id": "test",
            "return_data": None,
            "created_at": None,
            "is_active": None,
        }

        transformed = migration.transform_record("tax_returns", record)

        assert transformed["return_data"] is None
        assert transformed["created_at"] is None
        assert transformed["is_active"] is None

    def test_transform_record_numeric_columns(self, temp_sqlite_db, mock_postgres_settings):
        """Numeric columns are converted correctly."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        record = {
            "return_id": "test",
            "gross_income": "100000.50",
            "adjusted_gross_income": 95000,
        }

        transformed = migration.transform_record("tax_returns", record)

        assert transformed["gross_income"] == 100000.50
        assert transformed["adjusted_gross_income"] == 95000

    def test_migrate_table_dry_run(self, temp_sqlite_db, mock_postgres_settings):
        """Dry run doesn't write to PostgreSQL."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        # Mock connect_postgres to track calls
        with patch.object(migration, "insert_postgres_batch") as mock_insert:
            stats = migration.migrate_table("tax_returns", dry_run=True)

            # Should not call insert in dry run
            mock_insert.assert_not_called()

            # Stats should reflect successful "migration"
            assert stats.source_count == 2
            assert stats.migrated_count == 2
            assert stats.error_count == 0

    def test_migrate_table_empty(self, temp_sqlite_db, mock_postgres_settings):
        """Empty table migration succeeds."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        stats = migration.migrate_table("events", dry_run=True)

        assert stats.source_count == 0
        assert stats.migrated_count == 0
        assert stats.error_count == 0

    @patch("migrate_sqlite_to_postgres.create_engine")
    def test_run_dry_run(self, mock_create_engine, temp_sqlite_db, mock_postgres_settings):
        """Full dry run processes all tables."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        result = migration.run(dry_run=True)

        assert result.success is True
        assert "tax_returns" in result.tables_migrated
        assert "clients" in result.tables_migrated
        assert result.total_records_migrated >= 3

    @patch("migrate_sqlite_to_postgres.create_engine")
    def test_run_specific_tables(self, mock_create_engine, temp_sqlite_db, mock_postgres_settings):
        """Specific tables can be migrated."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        result = migration.run(tables=["tax_returns"], dry_run=True)

        assert result.success is True
        assert "tax_returns" in result.tables_migrated
        assert "clients" not in result.tables_migrated


# =============================================================================
# MIGRATION VERIFIER TESTS
# =============================================================================


class TestMigrationVerifier:
    """Tests for MigrationVerifier class."""

    def test_connect_sqlite(self, temp_sqlite_db, mock_postgres_settings):
        """SQLite connection works."""
        from migrate_sqlite_to_postgres import MigrationVerifier

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        conn = verifier.connect_sqlite()
        assert conn is not None
        conn.close()

    @patch("migrate_sqlite_to_postgres.create_engine")
    def test_compare_counts(self, mock_create_engine, temp_sqlite_db, mock_postgres_settings):
        """Count comparison returns correct structure."""
        from migrate_sqlite_to_postgres import MigrationVerifier

        # Mock PostgreSQL to return matching counts
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 2  # Same as SQLite tax_returns
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn
        mock_create_engine.return_value = mock_engine

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        results = verifier.compare_counts()

        assert len(results) >= 1
        # Each result is (table_name, sqlite_count, pg_count, match)
        for table_name, sqlite_count, pg_count, match in results:
            assert isinstance(table_name, str)
            assert isinstance(sqlite_count, int)

    @patch("migrate_sqlite_to_postgres.create_engine")
    def test_run_verification(self, mock_create_engine, temp_sqlite_db, mock_postgres_settings):
        """Full verification returns proper structure."""
        from migrate_sqlite_to_postgres import MigrationVerifier

        # Mock PostgreSQL
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 2
        mock_result.fetchone.return_value = None  # No matching rows
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn
        mock_create_engine.return_value = mock_engine

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        results = verifier.run_verification()

        assert "timestamp" in results
        assert "count_comparison" in results
        assert "sample_differences" in results
        assert "overall_status" in results


# =============================================================================
# VERIFY MIGRATION SCRIPT TESTS
# =============================================================================


class TestVerifyMigrationScript:
    """Tests for verify_migration.py script components."""

    def test_table_verification_dataclass(self):
        """TableVerification dataclass works correctly."""
        from verify_migration import TableVerification

        result = TableVerification(
            table_name="test_table",
            sqlite_count=100,
            postgres_count=100,
            count_match=True,
        )

        assert result.table_name == "test_table"
        assert result.count_match is True
        assert result.error is None

    def test_verification_report_dataclass(self):
        """VerificationReport dataclass works correctly."""
        from verify_migration import VerificationReport, TableVerification

        report = VerificationReport()
        report.tables_verified = 5
        report.tables_passed = 4
        report.tables_failed = 1
        report.total_sqlite_records = 1000
        report.total_postgres_records = 990

        table_result = TableVerification(
            table_name="test",
            sqlite_count=100,
            postgres_count=100,
            count_match=True,
        )
        report.table_results.append(table_result)

        assert report.tables_verified == 5
        assert len(report.table_results) == 1

    def test_verification_report_to_dict(self):
        """VerificationReport converts to dict correctly."""
        from verify_migration import VerificationReport, TableVerification

        report = VerificationReport(
            sqlite_path="/path/to/sqlite.db",
            postgres_host="localhost",
            overall_status="pass",
        )
        report.tables_verified = 2
        report.tables_passed = 2

        result = report.to_dict()

        assert result["sqlite_path"] == "/path/to/sqlite.db"
        assert result["postgres_host"] == "localhost"
        assert result["overall_status"] == "pass"
        assert "summary" in result
        assert result["summary"]["tables_verified"] == 2

    def test_migration_verifier_init(self, temp_sqlite_db, mock_postgres_settings):
        """MigrationVerifier initializes correctly."""
        from verify_migration import MigrationVerifier

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
            sample_size=20,
        )

        assert verifier.sqlite_path == temp_sqlite_db
        assert verifier.sample_size == 20

    def test_migration_verifier_get_tables(self, temp_sqlite_db, mock_postgres_settings):
        """MigrationVerifier gets tables correctly."""
        from verify_migration import MigrationVerifier

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        tables = verifier.get_tables()

        assert "tax_returns" in tables
        assert "clients" in tables

    def test_migration_verifier_compute_json_checksum(self, temp_sqlite_db, mock_postgres_settings):
        """JSON checksum is consistent."""
        from verify_migration import MigrationVerifier

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        # Same data should produce same checksum
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}  # Different order, same content

        checksum1 = verifier.compute_json_checksum(data1)
        checksum2 = verifier.compute_json_checksum(data2)

        assert checksum1 == checksum2

    def test_migration_verifier_compute_json_checksum_string(self, temp_sqlite_db, mock_postgres_settings):
        """JSON checksum handles string input."""
        from verify_migration import MigrationVerifier

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        json_str = '{"a": 1, "b": 2}'
        data = {"a": 1, "b": 2}

        checksum_str = verifier.compute_json_checksum(json_str)
        checksum_dict = verifier.compute_json_checksum(data)

        assert checksum_str == checksum_dict

    def test_migration_verifier_compare_values_none(self, temp_sqlite_db, mock_postgres_settings):
        """Value comparison handles None correctly."""
        from verify_migration import MigrationVerifier

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        assert verifier.compare_values(None, None) is True
        assert verifier.compare_values(None, "value") is False
        assert verifier.compare_values("value", None) is False

    def test_migration_verifier_compare_values_json(self, temp_sqlite_db, mock_postgres_settings):
        """Value comparison handles JSON correctly."""
        from verify_migration import MigrationVerifier

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        # JSON string vs dict
        sqlite_val = '{"a": 1}'
        pg_val = {"a": 1}

        assert verifier.compare_values(sqlite_val, pg_val, is_json=True) is True

    def test_migration_verifier_compare_values_numeric(self, temp_sqlite_db, mock_postgres_settings):
        """Value comparison handles numerics correctly."""
        from verify_migration import MigrationVerifier

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        # Small floating point differences should match
        assert verifier.compare_values(100.0, 100.0001) is True
        assert verifier.compare_values(100, 100.0) is True

        # Large differences should not match
        assert verifier.compare_values(100.0, 101.0) is False

    def test_migration_verifier_compare_values_boolean(self, temp_sqlite_db, mock_postgres_settings):
        """Value comparison handles booleans correctly."""
        from verify_migration import MigrationVerifier

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        # SQLite stores booleans as integers
        assert verifier.compare_values(1, True) is True
        assert verifier.compare_values(0, False) is True
        assert verifier.compare_values(1, False) is False

    @patch("verify_migration.create_engine")
    def test_migration_verifier_verify_counts(self, mock_create_engine, temp_sqlite_db, mock_postgres_settings):
        """Count verification works."""
        from verify_migration import MigrationVerifier

        # Mock PostgreSQL
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 2  # Same as SQLite
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()
        mock_create_engine.return_value = mock_engine

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        sqlite_count, pg_count = verifier.verify_counts("tax_returns")

        assert sqlite_count == 2
        assert pg_count == 2

    @patch("verify_migration.create_engine")
    def test_migration_verifier_verify_table(self, mock_create_engine, temp_sqlite_db, mock_postgres_settings):
        """Table verification returns correct structure."""
        from verify_migration import MigrationVerifier

        # Mock PostgreSQL
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 2
        mock_conn.execute.return_value = mock_result
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value = mock_conn
        mock_engine.dispose = MagicMock()
        mock_create_engine.return_value = mock_engine

        verifier = MigrationVerifier(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        result = verifier.verify_table("tax_returns", detailed=False)

        assert result.table_name == "tax_returns"
        assert result.sqlite_count == 2
        assert result.postgres_count == 2
        assert result.count_match is True


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestMigrationIntegration:
    """Integration tests for the migration process."""

    def test_full_migration_dry_run(self, temp_sqlite_db, mock_postgres_settings):
        """Full migration dry run completes successfully."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
            batch_size=100,
        )

        result = migration.run(dry_run=True)

        assert result.success is True
        assert result.total_records_migrated >= 3
        assert result.total_errors == 0
        assert result.started_at is not None
        assert result.completed_at is not None

    def test_transformation_pipeline(self, temp_sqlite_db, mock_postgres_settings):
        """Full transformation pipeline works correctly."""
        from migrate_sqlite_to_postgres import SQLiteToPostgresMigration

        migration = SQLiteToPostgresMigration(
            sqlite_path=temp_sqlite_db,
            postgres_settings=mock_postgres_settings,
        )

        # Read actual records
        batch = migration.read_sqlite_batch("tax_returns", offset=0, limit=10)

        # Transform each record
        for record in batch:
            transformed = migration.transform_record("tax_returns", record)

            # Verify transformations
            assert "return_id" in transformed

            # JSON should be parsed
            if transformed.get("return_data"):
                assert isinstance(transformed["return_data"], dict)

            # Datetime should be parsed
            if transformed.get("created_at"):
                assert isinstance(transformed["created_at"], datetime)


# =============================================================================
# CLI TESTS
# =============================================================================


class TestMigrationCLI:
    """Tests for migration script CLI."""

    def test_migration_order_defined(self):
        """Migration order is properly defined."""
        from migrate_sqlite_to_postgres import MIGRATION_ORDER

        assert "tax_returns" in MIGRATION_ORDER
        assert "clients" in MIGRATION_ORDER
        assert "scenarios" in MIGRATION_ORDER

    @patch("migrate_sqlite_to_postgres.get_database_settings")
    @patch("migrate_sqlite_to_postgres.SQLiteToPostgresMigration")
    def test_main_dry_run(self, mock_migration_class, mock_get_settings, temp_sqlite_db):
        """CLI dry run mode works."""
        from migrate_sqlite_to_postgres import main, MigrationResult

        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.is_postgres = True
        mock_settings.name = "testdb"
        mock_get_settings.return_value = mock_settings

        mock_migration = MagicMock()
        mock_result = MigrationResult(success=True)
        mock_migration.run.return_value = mock_result
        mock_migration_class.return_value = mock_migration

        # Run with --dry-run
        with patch("sys.argv", ["script", "--sqlite-path", str(temp_sqlite_db), "--dry-run"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0
