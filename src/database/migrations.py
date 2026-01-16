"""
Database migrations for Tax Decision Intelligence Platform.

This module provides schema migrations for adding domain model tables:
- clients: Client profiles
- scenarios: Tax scenarios for what-if analysis
- scenario_comparisons: Scenario comparison records
- advisory_plans: Advisory plans
- recommendations: Tax recommendations
- events: Domain event store for audit trails

Migration Version: 2025.01.001
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


# Schema version tracking
CURRENT_VERSION = "2025.01.001"


@dataclass
class Migration:
    """Represents a database migration."""
    version: str
    description: str
    up_sql: str
    down_sql: str


# =============================================================================
# MIGRATION DEFINITIONS
# =============================================================================

MIGRATIONS: List[Migration] = [
    # Migration 1: Add client_id and prior_return_id to tax_returns
    Migration(
        version="2025.01.001",
        description="Add domain model tables for scenarios, advisory, clients, and events",
        up_sql="""
-- ===========================================================================
-- CLIENTS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    external_id TEXT,
    ssn_hash TEXT UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    street_address TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    preferences JSON,
    prior_year_carryovers JSON,
    prior_year_summary JSON,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_clients_external_id ON clients(external_id);
CREATE INDEX IF NOT EXISTS idx_clients_ssn_hash ON clients(ssn_hash);
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(last_name, first_name);

-- ===========================================================================
-- ALTER TAX_RETURNS TABLE
-- ===========================================================================
-- Add client_id foreign key and prior_return_id for carryovers
-- Note: SQLite doesn't support ADD COLUMN IF NOT EXISTS, so we check first

-- ===========================================================================
-- SCENARIOS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    scenario_type TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    base_snapshot JSON NOT NULL,
    modifications JSON NOT NULL,
    result JSON,
    is_recommended INTEGER DEFAULT 0,
    recommendation_reason TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT,
    calculated_at TEXT,
    version INTEGER DEFAULT 1,
    FOREIGN KEY (return_id) REFERENCES tax_returns(return_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scenarios_return_id ON scenarios(return_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_type ON scenarios(return_id, scenario_type);
CREATE INDEX IF NOT EXISTS idx_scenarios_recommended ON scenarios(return_id, is_recommended);

-- ===========================================================================
-- SCENARIO COMPARISONS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS scenario_comparisons (
    comparison_id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL,
    name TEXT,
    scenario_ids JSON NOT NULL,
    winner_scenario_id TEXT,
    max_savings REAL DEFAULT 0,
    comparison_data JSON,
    created_at TEXT NOT NULL,
    FOREIGN KEY (return_id) REFERENCES tax_returns(return_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comparisons_return_id ON scenario_comparisons(return_id);

-- ===========================================================================
-- ADVISORY PLANS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS advisory_plans (
    plan_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    return_id TEXT NOT NULL,
    tax_year INTEGER NOT NULL,
    computation_statement TEXT,
    total_potential_savings REAL DEFAULT 0,
    total_realized_savings REAL DEFAULT 0,
    is_finalized INTEGER DEFAULT 0,
    finalized_at TEXT,
    finalized_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (return_id) REFERENCES tax_returns(return_id)
);

CREATE INDEX IF NOT EXISTS idx_advisory_client_id ON advisory_plans(client_id);
CREATE INDEX IF NOT EXISTS idx_advisory_return_id ON advisory_plans(return_id);
CREATE INDEX IF NOT EXISTS idx_advisory_year ON advisory_plans(client_id, tax_year);

-- ===========================================================================
-- RECOMMENDATIONS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    detailed_explanation TEXT,
    estimated_savings REAL DEFAULT 0,
    confidence_level REAL DEFAULT 0.8,
    complexity TEXT DEFAULT 'medium',
    action_steps JSON,
    status TEXT DEFAULT 'proposed',
    status_changed_at TEXT,
    status_changed_by TEXT,
    decline_reason TEXT,
    actual_savings REAL,
    outcome_notes TEXT,
    related_scenario_id TEXT,
    irs_references JSON,
    created_at TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES advisory_plans(plan_id) ON DELETE CASCADE,
    FOREIGN KEY (related_scenario_id) REFERENCES scenarios(scenario_id)
);

CREATE INDEX IF NOT EXISTS idx_recommendations_plan_id ON recommendations(plan_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON recommendations(plan_id, status);
CREATE INDEX IF NOT EXISTS idx_recommendations_category ON recommendations(plan_id, category);
CREATE INDEX IF NOT EXISTS idx_recommendations_priority ON recommendations(plan_id, priority);

-- ===========================================================================
-- EVENTS TABLE (Event Store for Audit Trail)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    stream_id TEXT NOT NULL,
    stream_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data JSON NOT NULL,
    metadata JSON,
    version INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_stream ON events(stream_id, version);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_aggregate ON events(stream_type, stream_id);

-- ===========================================================================
-- SCHEMA VERSION TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    description TEXT,
    applied_at TEXT NOT NULL
);
        """,
        down_sql="""
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS recommendations;
DROP TABLE IF EXISTS advisory_plans;
DROP TABLE IF EXISTS scenario_comparisons;
DROP TABLE IF EXISTS scenarios;
DROP TABLE IF EXISTS clients;
DROP TABLE IF EXISTS schema_migrations;
        """
    ),
]


# =============================================================================
# MIGRATION RUNNER
# =============================================================================

class MigrationRunner:
    """
    Runs database migrations.

    Tracks applied migrations and applies new ones in order.
    """

    def __init__(self, db_path: Path):
        """Initialize with database path."""
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_applied_versions(self) -> List[str]:
        """Get list of applied migration versions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if migrations table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_migrations'
            """)
            if not cursor.fetchone():
                return []

            cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
            return [row[0] for row in cursor.fetchall()]

    def get_pending_migrations(self) -> List[Migration]:
        """Get migrations that haven't been applied."""
        applied = set(self.get_applied_versions())
        return [m for m in MIGRATIONS if m.version not in applied]

    def apply_migration(self, migration: Migration) -> bool:
        """
        Apply a single migration.

        Args:
            migration: Migration to apply

        Returns:
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                # Execute migration SQL
                cursor.executescript(migration.up_sql)

                # Record migration
                cursor.execute("""
                    INSERT INTO schema_migrations (version, description, applied_at)
                    VALUES (?, ?, ?)
                """, (migration.version, migration.description, datetime.utcnow().isoformat()))

                conn.commit()
                print(f"Applied migration {migration.version}: {migration.description}")
                return True

            except Exception as e:
                conn.rollback()
                print(f"Failed to apply migration {migration.version}: {e}")
                raise

    def rollback_migration(self, migration: Migration) -> bool:
        """
        Rollback a single migration.

        Args:
            migration: Migration to rollback

        Returns:
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                # Execute rollback SQL
                cursor.executescript(migration.down_sql)

                # Remove migration record
                cursor.execute(
                    "DELETE FROM schema_migrations WHERE version = ?",
                    (migration.version,)
                )

                conn.commit()
                print(f"Rolled back migration {migration.version}")
                return True

            except Exception as e:
                conn.rollback()
                print(f"Failed to rollback migration {migration.version}: {e}")
                raise

    def migrate(self) -> int:
        """
        Apply all pending migrations.

        Returns:
            Number of migrations applied
        """
        pending = self.get_pending_migrations()

        if not pending:
            print("No pending migrations")
            return 0

        print(f"Found {len(pending)} pending migration(s)")

        for migration in pending:
            self.apply_migration(migration)

        return len(pending)

    def rollback(self, steps: int = 1) -> int:
        """
        Rollback the last N migrations.

        Args:
            steps: Number of migrations to rollback

        Returns:
            Number of migrations rolled back
        """
        applied = self.get_applied_versions()

        if not applied:
            print("No migrations to rollback")
            return 0

        # Get migrations to rollback in reverse order
        to_rollback = applied[-steps:][::-1]
        migration_map = {m.version: m for m in MIGRATIONS}

        count = 0
        for version in to_rollback:
            if version in migration_map:
                self.rollback_migration(migration_map[version])
                count += 1

        return count

    def get_status(self) -> dict:
        """
        Get migration status.

        Returns:
            Status dictionary with applied and pending info
        """
        applied = self.get_applied_versions()
        pending = self.get_pending_migrations()

        return {
            "current_version": applied[-1] if applied else None,
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied_versions": applied,
            "pending_versions": [m.version for m in pending],
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def run_migrations(db_path: Optional[Path] = None) -> int:
    """
    Run all pending migrations.

    Args:
        db_path: Path to database, defaults to data/tax_returns.db

    Returns:
        Number of migrations applied
    """
    if db_path is None:
        db_path = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"

    runner = MigrationRunner(db_path)
    return runner.migrate()


def rollback_migrations(steps: int = 1, db_path: Optional[Path] = None) -> int:
    """
    Rollback migrations.

    Args:
        steps: Number of migrations to rollback
        db_path: Path to database

    Returns:
        Number of migrations rolled back
    """
    if db_path is None:
        db_path = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"

    runner = MigrationRunner(db_path)
    return runner.rollback(steps)


def get_migration_status(db_path: Optional[Path] = None) -> dict:
    """
    Get migration status.

    Args:
        db_path: Path to database

    Returns:
        Status dictionary
    """
    if db_path is None:
        db_path = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"

    runner = MigrationRunner(db_path)
    return runner.get_status()


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python migrations.py [migrate|rollback|status]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "migrate":
        count = run_migrations()
        print(f"\nApplied {count} migration(s)")

    elif command == "rollback":
        steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        count = rollback_migrations(steps)
        print(f"\nRolled back {count} migration(s)")

    elif command == "status":
        status = get_migration_status()
        print(f"\nMigration Status:")
        print(f"  Current Version: {status['current_version']}")
        print(f"  Applied: {status['applied_count']}")
        print(f"  Pending: {status['pending_count']}")
        if status['pending_versions']:
            print(f"  Pending Versions: {', '.join(status['pending_versions'])}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
