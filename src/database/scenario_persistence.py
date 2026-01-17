"""
Persistence layer for tax scenarios using SQLite.

Provides save/load functionality for scenarios using JSON serialization.
Replaces in-memory Dict storage with database-backed persistence.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import UUID

from .migrations import run_migrations

# Default database path (same as persistence.py)
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"


class ScenarioPersistence:
    """
    Persistence layer for tax scenarios.

    Uses SQLite with JSON serialization for flexibility.
    Schema defined in migrations.py (scenarios table).
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize scenario persistence.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure database and schema exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Run migrations to ensure scenarios table exists
        run_migrations(self.db_path)

    def save_scenario(self, scenario_data: Dict[str, Any]) -> str:
        """
        Save or update a scenario.

        Args:
            scenario_data: Scenario data dictionary

        Returns:
            scenario_id of saved scenario
        """
        now = datetime.utcnow().isoformat()
        scenario_id = str(scenario_data.get("scenario_id", ""))

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if exists
            cursor.execute(
                "SELECT scenario_id FROM scenarios WHERE scenario_id = ?",
                (scenario_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update
                cursor.execute("""
                    UPDATE scenarios SET
                        return_id = ?,
                        name = ?,
                        description = ?,
                        scenario_type = ?,
                        status = ?,
                        base_snapshot = ?,
                        modifications = ?,
                        result = ?,
                        is_recommended = ?,
                        recommendation_reason = ?,
                        calculated_at = ?,
                        version = version + 1
                    WHERE scenario_id = ?
                """, (
                    str(scenario_data.get("return_id", "")),
                    scenario_data.get("name", ""),
                    scenario_data.get("description"),
                    scenario_data.get("scenario_type", "what_if"),
                    scenario_data.get("status", "draft"),
                    json.dumps(scenario_data.get("base_snapshot", {}), default=str),
                    json.dumps(scenario_data.get("modifications", []), default=str),
                    json.dumps(scenario_data.get("result"), default=str) if scenario_data.get("result") else None,
                    1 if scenario_data.get("is_recommended") else 0,
                    scenario_data.get("recommendation_reason"),
                    scenario_data.get("calculated_at"),
                    scenario_id
                ))
            else:
                # Insert
                cursor.execute("""
                    INSERT INTO scenarios (
                        scenario_id, return_id, name, description, scenario_type,
                        status, base_snapshot, modifications, result,
                        is_recommended, recommendation_reason,
                        created_at, created_by, calculated_at, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scenario_id,
                    str(scenario_data.get("return_id", "")),
                    scenario_data.get("name", ""),
                    scenario_data.get("description"),
                    scenario_data.get("scenario_type", "what_if"),
                    scenario_data.get("status", "draft"),
                    json.dumps(scenario_data.get("base_snapshot", {}), default=str),
                    json.dumps(scenario_data.get("modifications", []), default=str),
                    json.dumps(scenario_data.get("result"), default=str) if scenario_data.get("result") else None,
                    1 if scenario_data.get("is_recommended") else 0,
                    scenario_data.get("recommendation_reason"),
                    now,
                    scenario_data.get("created_by"),
                    scenario_data.get("calculated_at"),
                    1
                ))

            conn.commit()

        return scenario_id

    def load_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a scenario by ID.

        Args:
            scenario_id: The scenario ID

        Returns:
            Scenario data dictionary or None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM scenarios WHERE scenario_id = ?",
                (scenario_id,)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_dict(row)
            return None

    def load_scenarios_for_return(self, return_id: str) -> List[Dict[str, Any]]:
        """
        Load all scenarios for a return.

        Args:
            return_id: The return ID

        Returns:
            List of scenario dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM scenarios
                   WHERE return_id = ?
                   ORDER BY created_at DESC""",
                (return_id,)
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def delete_scenario(self, scenario_id: str) -> bool:
        """
        Delete a scenario.

        Args:
            scenario_id: The scenario ID

        Returns:
            True if deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM scenarios WHERE scenario_id = ?",
                (scenario_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to scenario dictionary."""
        return {
            "scenario_id": row["scenario_id"],
            "return_id": row["return_id"],
            "name": row["name"],
            "description": row["description"],
            "scenario_type": row["scenario_type"],
            "status": row["status"],
            "base_snapshot": json.loads(row["base_snapshot"]) if row["base_snapshot"] else {},
            "modifications": json.loads(row["modifications"]) if row["modifications"] else [],
            "result": json.loads(row["result"]) if row["result"] else None,
            "is_recommended": bool(row["is_recommended"]),
            "recommendation_reason": row["recommendation_reason"],
            "created_at": row["created_at"],
            "created_by": row["created_by"],
            "calculated_at": row["calculated_at"],
            "version": row["version"],
        }


# Global instance
_scenario_persistence: Optional[ScenarioPersistence] = None


def get_scenario_persistence() -> ScenarioPersistence:
    """Get the global scenario persistence instance."""
    global _scenario_persistence
    if _scenario_persistence is None:
        _scenario_persistence = ScenarioPersistence()
    return _scenario_persistence
