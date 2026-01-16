"""
Simple persistence layer for tax returns using SQLite.

Provides save/load functionality for tax returns using JSON serialization.
This approach works with the existing Pydantic models without requiring
complex ORM mapping or PostgreSQL.
"""

import sqlite3
import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"


@dataclass
class SavedReturn:
    """Metadata about a saved tax return."""
    return_id: str
    session_id: str
    taxpayer_name: str
    tax_year: int
    filing_status: str
    state_code: Optional[str]
    gross_income: float
    tax_liability: float
    refund_or_owed: float
    status: str
    created_at: str
    updated_at: str


class TaxReturnPersistence:
    """
    Simple persistence layer for tax returns.

    Uses SQLite with JSON serialization for flexibility and simplicity.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize persistence layer.

        Args:
            db_path: Path to SQLite database file. Defaults to data/tax_returns.db
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create database and tables if they don't exist."""
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create tax_returns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tax_returns (
                    return_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    taxpayer_ssn_hash TEXT,
                    taxpayer_name TEXT,
                    tax_year INTEGER NOT NULL DEFAULT 2025,
                    filing_status TEXT,
                    state_code TEXT,
                    gross_income REAL DEFAULT 0,
                    adjusted_gross_income REAL DEFAULT 0,
                    taxable_income REAL DEFAULT 0,
                    federal_tax_liability REAL DEFAULT 0,
                    state_tax_liability REAL DEFAULT 0,
                    combined_tax_liability REAL DEFAULT 0,
                    federal_refund_or_owed REAL DEFAULT 0,
                    state_refund_or_owed REAL DEFAULT 0,
                    combined_refund_or_owed REAL DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    return_data JSON NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Create index on session_id for quick lookup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id
                ON tax_returns(session_id)
            """)

            # Create index on taxpayer_ssn_hash for returning user lookup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ssn_hash
                ON tax_returns(taxpayer_ssn_hash)
            """)

            # Create index on tax_year
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tax_year
                ON tax_returns(tax_year)
            """)

            conn.commit()

    def save_return(
        self,
        session_id: str,
        tax_return_data: Dict[str, Any],
        return_id: Optional[str] = None
    ) -> str:
        """
        Save or update a tax return.

        Args:
            session_id: Session identifier
            tax_return_data: Complete tax return data as dictionary
            return_id: Optional return ID for updates

        Returns:
            return_id of saved return
        """
        now = datetime.utcnow().isoformat()

        # Generate or use provided return_id
        if not return_id:
            return_id = str(uuid.uuid4())

        # Extract key fields for indexing
        taxpayer = tax_return_data.get("taxpayer", {})
        income = tax_return_data.get("income", {})

        taxpayer_name = f"{taxpayer.get('first_name', '')} {taxpayer.get('last_name', '')}".strip()
        ssn = taxpayer.get("ssn", "")
        ssn_hash = hashlib.sha256(ssn.replace("-", "").encode()).hexdigest() if ssn else None

        # Get computed values
        gross_income = tax_return_data.get("adjusted_gross_income", 0) or 0
        if not gross_income and income:
            # Sum up income if AGI not set
            wages = sum(w.get("wages", 0) for w in income.get("w2_forms", []))
            gross_income = wages + income.get("interest_income", 0) + income.get("dividend_income", 0)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if return exists
            cursor.execute(
                "SELECT return_id, created_at FROM tax_returns WHERE return_id = ?",
                (return_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing return
                cursor.execute("""
                    UPDATE tax_returns SET
                        session_id = ?,
                        taxpayer_ssn_hash = ?,
                        taxpayer_name = ?,
                        tax_year = ?,
                        filing_status = ?,
                        state_code = ?,
                        gross_income = ?,
                        adjusted_gross_income = ?,
                        taxable_income = ?,
                        federal_tax_liability = ?,
                        state_tax_liability = ?,
                        combined_tax_liability = ?,
                        federal_refund_or_owed = ?,
                        state_refund_or_owed = ?,
                        combined_refund_or_owed = ?,
                        status = ?,
                        return_data = ?,
                        updated_at = ?
                    WHERE return_id = ?
                """, (
                    session_id,
                    ssn_hash,
                    taxpayer_name or "Anonymous",
                    tax_return_data.get("tax_year", 2025),
                    taxpayer.get("filing_status", "single"),
                    tax_return_data.get("state_of_residence"),
                    gross_income,
                    tax_return_data.get("adjusted_gross_income", 0) or 0,
                    tax_return_data.get("taxable_income", 0) or 0,
                    tax_return_data.get("tax_liability", 0) or 0,
                    tax_return_data.get("state_tax_liability", 0) or 0,
                    tax_return_data.get("combined_tax_liability", 0) or 0,
                    tax_return_data.get("refund_or_owed", 0) or 0,
                    tax_return_data.get("state_refund_or_owed", 0) or 0,
                    tax_return_data.get("combined_refund_or_owed", 0) or 0,
                    "in_progress",
                    json.dumps(tax_return_data, default=str),
                    now,
                    return_id
                ))
            else:
                # Insert new return
                cursor.execute("""
                    INSERT INTO tax_returns (
                        return_id, session_id, taxpayer_ssn_hash, taxpayer_name,
                        tax_year, filing_status, state_code,
                        gross_income, adjusted_gross_income, taxable_income,
                        federal_tax_liability, state_tax_liability, combined_tax_liability,
                        federal_refund_or_owed, state_refund_or_owed, combined_refund_or_owed,
                        status, return_data, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    return_id,
                    session_id,
                    ssn_hash,
                    taxpayer_name or "Anonymous",
                    tax_return_data.get("tax_year", 2025),
                    taxpayer.get("filing_status", "single"),
                    tax_return_data.get("state_of_residence"),
                    gross_income,
                    tax_return_data.get("adjusted_gross_income", 0) or 0,
                    tax_return_data.get("taxable_income", 0) or 0,
                    tax_return_data.get("tax_liability", 0) or 0,
                    tax_return_data.get("state_tax_liability", 0) or 0,
                    tax_return_data.get("combined_tax_liability", 0) or 0,
                    tax_return_data.get("refund_or_owed", 0) or 0,
                    tax_return_data.get("state_refund_or_owed", 0) or 0,
                    tax_return_data.get("combined_refund_or_owed", 0) or 0,
                    "draft",
                    json.dumps(tax_return_data, default=str),
                    now,
                    now
                ))

            conn.commit()

        return return_id

    def load_return(self, return_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a tax return by ID.

        Args:
            return_id: The return ID

        Returns:
            Tax return data dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT return_data FROM tax_returns WHERE return_id = ?",
                (return_id,)
            )
            row = cursor.fetchone()

            if row:
                return json.loads(row[0])
            return None

    def load_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load the most recent tax return for a session.

        Args:
            session_id: Session identifier

        Returns:
            Tax return data dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT return_id, return_data FROM tax_returns
                   WHERE session_id = ?
                   ORDER BY updated_at DESC
                   LIMIT 1""",
                (session_id,)
            )
            row = cursor.fetchone()

            if row:
                data = json.loads(row[1])
                data["_return_id"] = row[0]
                return data
            return None

    def list_returns(
        self,
        tax_year: Optional[int] = None,
        limit: int = 50
    ) -> List[SavedReturn]:
        """
        List saved tax returns.

        Args:
            tax_year: Optional filter by tax year
            limit: Maximum number of returns to return

        Returns:
            List of SavedReturn metadata objects
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if tax_year:
                cursor.execute(
                    """SELECT return_id, session_id, taxpayer_name, tax_year,
                              filing_status, state_code, gross_income,
                              combined_tax_liability, combined_refund_or_owed,
                              status, created_at, updated_at
                       FROM tax_returns
                       WHERE tax_year = ?
                       ORDER BY updated_at DESC
                       LIMIT ?""",
                    (tax_year, limit)
                )
            else:
                cursor.execute(
                    """SELECT return_id, session_id, taxpayer_name, tax_year,
                              filing_status, state_code, gross_income,
                              combined_tax_liability, combined_refund_or_owed,
                              status, created_at, updated_at
                       FROM tax_returns
                       ORDER BY updated_at DESC
                       LIMIT ?""",
                    (limit,)
                )

            returns = []
            for row in cursor.fetchall():
                returns.append(SavedReturn(
                    return_id=row[0],
                    session_id=row[1],
                    taxpayer_name=row[2],
                    tax_year=row[3],
                    filing_status=row[4],
                    state_code=row[5],
                    gross_income=row[6] or 0,
                    tax_liability=row[7] or 0,
                    refund_or_owed=row[8] or 0,
                    status=row[9],
                    created_at=row[10],
                    updated_at=row[11]
                ))

            return returns

    def delete_return(self, return_id: str) -> bool:
        """
        Delete a tax return.

        Args:
            return_id: The return ID to delete

        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM tax_returns WHERE return_id = ?",
                (return_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_return_metadata(self, return_id: str) -> Optional[SavedReturn]:
        """
        Get metadata for a specific return.

        Args:
            return_id: The return ID

        Returns:
            SavedReturn metadata or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT return_id, session_id, taxpayer_name, tax_year,
                          filing_status, state_code, gross_income,
                          combined_tax_liability, combined_refund_or_owed,
                          status, created_at, updated_at
                   FROM tax_returns
                   WHERE return_id = ?""",
                (return_id,)
            )
            row = cursor.fetchone()

            if row:
                return SavedReturn(
                    return_id=row[0],
                    session_id=row[1],
                    taxpayer_name=row[2],
                    tax_year=row[3],
                    filing_status=row[4],
                    state_code=row[5],
                    gross_income=row[6] or 0,
                    tax_liability=row[7] or 0,
                    refund_or_owed=row[8] or 0,
                    status=row[9],
                    created_at=row[10],
                    updated_at=row[11]
                )
            return None


# Global instance for convenience
_persistence: Optional[TaxReturnPersistence] = None


def get_persistence() -> TaxReturnPersistence:
    """Get the global persistence instance."""
    global _persistence
    if _persistence is None:
        _persistence = TaxReturnPersistence()
    return _persistence


def save_tax_return(session_id: str, tax_return_data: Dict[str, Any], return_id: Optional[str] = None) -> str:
    """Save a tax return."""
    return get_persistence().save_return(session_id, tax_return_data, return_id)


def load_tax_return(return_id: str) -> Optional[Dict[str, Any]]:
    """Load a tax return by ID."""
    return get_persistence().load_return(return_id)


def load_session_return(session_id: str) -> Optional[Dict[str, Any]]:
    """Load the most recent tax return for a session."""
    return get_persistence().load_by_session(session_id)


def list_tax_returns(tax_year: Optional[int] = None, limit: int = 50) -> List[SavedReturn]:
    """List saved tax returns."""
    return get_persistence().list_returns(tax_year, limit)
