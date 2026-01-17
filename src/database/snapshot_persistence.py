"""
Persistence layer for calculation snapshots using SQLite.

Snapshots capture the input state and calculation result for tax calculations.
Recalculation is skipped when an identical input hash already exists.

Design principles:
- Every calculation creates a snapshot
- Scenarios reference snapshots (not store results directly)
- Recalculation only happens when inputs change (detected via input_hash)
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import uuid4

from .migrations import run_migrations

# Default database path (same as other persistence modules)
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"


def compute_input_hash(input_data: Dict[str, Any]) -> str:
    """
    Compute a deterministic hash of input data.

    The hash is used to detect when inputs have changed and
    recalculation is needed.

    Args:
        input_data: The tax return input data

    Returns:
        SHA-256 hash as hex string
    """
    # Normalize the data by sorting keys and using consistent formatting
    normalized = json.dumps(input_data, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


class SnapshotPersistence:
    """
    Persistence layer for calculation snapshots.

    Uses SQLite with JSON serialization. Snapshots are immutable -
    once created, they are never modified.

    Schema:
        - snapshot_id: Primary key
        - return_id: Reference to base return
        - input_hash: SHA-256 of normalized input (unique)
        - input_data: Frozen input state as JSON
        - result_data: CalculationBreakdown as JSON
        - tax_year, filing_status, total_tax, effective_rate: Indexed fields
        - created_at: Timestamp
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize snapshot persistence.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure database and schema exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Run migrations first
        run_migrations(self.db_path)
        # Then ensure snapshots table exists
        self._create_snapshots_table()

    def _create_snapshots_table(self):
        """Create the calculation_snapshots table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS calculation_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    return_id TEXT NOT NULL,
                    input_hash TEXT NOT NULL UNIQUE,
                    input_data JSON NOT NULL,
                    result_data JSON NOT NULL,
                    tax_year INTEGER NOT NULL,
                    filing_status TEXT NOT NULL,
                    total_tax REAL NOT NULL,
                    effective_rate REAL NOT NULL,
                    taxable_income REAL DEFAULT 0,
                    total_credits REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    FOREIGN KEY (return_id) REFERENCES tax_returns(return_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_input_hash
                    ON calculation_snapshots(input_hash);
                CREATE INDEX IF NOT EXISTS idx_snapshots_return_id
                    ON calculation_snapshots(return_id);
                CREATE INDEX IF NOT EXISTS idx_snapshots_tax_year
                    ON calculation_snapshots(return_id, tax_year);
            """)
            conn.commit()

    def get_snapshot_by_hash(self, input_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get an existing snapshot by input hash.

        This is the key method for avoiding recalculation - if a snapshot
        with the same input hash exists, we reuse it.

        Args:
            input_hash: SHA-256 hash of input data

        Returns:
            Snapshot dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM calculation_snapshots WHERE input_hash = ?",
                (input_hash,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def save_snapshot(
        self,
        return_id: str,
        input_data: Dict[str, Any],
        result_data: Dict[str, Any],
        tax_year: int,
        filing_status: str,
        total_tax: float,
        effective_rate: float,
        taxable_income: float = 0,
        total_credits: float = 0,
    ) -> Dict[str, Any]:
        """
        Save a new calculation snapshot.

        If a snapshot with the same input_hash already exists, returns
        the existing snapshot instead of creating a duplicate.

        Args:
            return_id: Reference to base return
            input_data: Frozen input state
            result_data: CalculationBreakdown as dict
            tax_year: Tax year
            filing_status: Filing status used
            total_tax: Total tax liability
            effective_rate: Effective tax rate
            taxable_income: Taxable income
            total_credits: Total credits applied

        Returns:
            Snapshot dictionary (new or existing)
        """
        input_hash = compute_input_hash(input_data)

        # Check for existing snapshot with same input hash
        existing = self.get_snapshot_by_hash(input_hash)
        if existing:
            return existing

        # Create new snapshot
        snapshot_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO calculation_snapshots (
                    snapshot_id, return_id, input_hash, input_data, result_data,
                    tax_year, filing_status, total_tax, effective_rate,
                    taxable_income, total_credits, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id,
                return_id,
                input_hash,
                json.dumps(input_data, default=str),
                json.dumps(result_data, default=str),
                tax_year,
                filing_status,
                total_tax,
                effective_rate,
                taxable_income,
                total_credits,
                now,
                1
            ))
            conn.commit()

        return {
            "snapshot_id": snapshot_id,
            "return_id": return_id,
            "input_hash": input_hash,
            "input_data": input_data,
            "result_data": result_data,
            "tax_year": tax_year,
            "filing_status": filing_status,
            "total_tax": total_tax,
            "effective_rate": effective_rate,
            "taxable_income": taxable_income,
            "total_credits": total_credits,
            "created_at": now,
            "version": 1,
        }

    def load_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a snapshot by ID.

        Args:
            snapshot_id: The snapshot ID

        Returns:
            Snapshot dictionary or None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM calculation_snapshots WHERE snapshot_id = ?",
                (snapshot_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def load_snapshots_for_return(self, return_id: str) -> List[Dict[str, Any]]:
        """
        Load all snapshots for a return.

        Args:
            return_id: The return ID

        Returns:
            List of snapshot dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM calculation_snapshots
                   WHERE return_id = ?
                   ORDER BY created_at DESC""",
                (return_id,)
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_or_create_snapshot(
        self,
        return_id: str,
        input_data: Dict[str, Any],
        calculate_fn,
    ) -> Dict[str, Any]:
        """
        Get existing snapshot or create new one via calculation.

        This is the main entry point for snapshot-based calculations.
        It checks if a snapshot with the same input exists, and only
        calls the calculate function if needed.

        Args:
            return_id: Reference to base return
            input_data: Tax return input data
            calculate_fn: Function to call if calculation needed.
                          Should return (result_dict, breakdown_fields)

        Returns:
            Snapshot dictionary
        """
        input_hash = compute_input_hash(input_data)

        # Check for existing snapshot
        existing = self.get_snapshot_by_hash(input_hash)
        if existing:
            return existing

        # Calculate new result
        result_data, breakdown = calculate_fn(input_data)

        # Save snapshot
        return self.save_snapshot(
            return_id=return_id,
            input_data=input_data,
            result_data=result_data,
            tax_year=breakdown.get("tax_year", 2025),
            filing_status=breakdown.get("filing_status", "single"),
            total_tax=breakdown.get("total_tax", 0),
            effective_rate=breakdown.get("effective_rate", 0),
            taxable_income=breakdown.get("taxable_income", 0),
            total_credits=breakdown.get("total_credits", 0),
        )

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """
        Delete a snapshot.

        Note: Snapshots are generally immutable, but this is provided
        for cleanup purposes.

        Args:
            snapshot_id: The snapshot ID

        Returns:
            True if deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM calculation_snapshots WHERE snapshot_id = ?",
                (snapshot_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to snapshot dictionary."""
        return {
            "snapshot_id": row["snapshot_id"],
            "return_id": row["return_id"],
            "input_hash": row["input_hash"],
            "input_data": json.loads(row["input_data"]) if row["input_data"] else {},
            "result_data": json.loads(row["result_data"]) if row["result_data"] else {},
            "tax_year": row["tax_year"],
            "filing_status": row["filing_status"],
            "total_tax": row["total_tax"],
            "effective_rate": row["effective_rate"],
            "taxable_income": row["taxable_income"],
            "total_credits": row["total_credits"],
            "created_at": row["created_at"],
            "version": row["version"],
        }


# Global instance
_snapshot_persistence: Optional[SnapshotPersistence] = None


def get_snapshot_persistence() -> SnapshotPersistence:
    """Get the global snapshot persistence instance."""
    global _snapshot_persistence
    if _snapshot_persistence is None:
        _snapshot_persistence = SnapshotPersistence()
    return _snapshot_persistence
