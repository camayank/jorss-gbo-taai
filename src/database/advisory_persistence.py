"""
Persistence layer for advisory plans and recommendations using SQLite.

Provides save/load functionality for advisory plans using JSON serialization.
Replaces in-memory Dict storage with database-backed persistence.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import UUID

from .migrations import run_migrations

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"


class AdvisoryPersistence:
    """
    Persistence layer for advisory plans and recommendations.

    Uses SQLite with JSON serialization.
    Schema defined in migrations.py (advisory_plans, recommendations tables).
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize advisory persistence.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure database and schema exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        run_migrations(self.db_path)

    def save_plan(self, plan_data: Dict[str, Any]) -> str:
        """
        Save or update an advisory plan with its recommendations.

        Args:
            plan_data: Plan data dictionary

        Returns:
            plan_id of saved plan
        """
        now = datetime.utcnow().isoformat()
        plan_id = str(plan_data.get("plan_id", ""))

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if exists
            cursor.execute(
                "SELECT plan_id FROM advisory_plans WHERE plan_id = ?",
                (plan_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update plan
                cursor.execute("""
                    UPDATE advisory_plans SET
                        client_id = ?,
                        return_id = ?,
                        tax_year = ?,
                        computation_statement = ?,
                        total_potential_savings = ?,
                        total_realized_savings = ?,
                        is_finalized = ?,
                        finalized_at = ?,
                        finalized_by = ?,
                        updated_at = ?,
                        version = version + 1
                    WHERE plan_id = ?
                """, (
                    str(plan_data.get("client_id", "")),
                    str(plan_data.get("return_id", "")),
                    plan_data.get("tax_year", 2025),
                    plan_data.get("computation_statement"),
                    plan_data.get("total_potential_savings", 0),
                    plan_data.get("total_realized_savings", 0),
                    1 if plan_data.get("is_finalized") else 0,
                    plan_data.get("finalized_at"),
                    plan_data.get("finalized_by"),
                    now,
                    plan_id
                ))
            else:
                # Insert plan
                cursor.execute("""
                    INSERT INTO advisory_plans (
                        plan_id, client_id, return_id, tax_year,
                        computation_statement, total_potential_savings,
                        total_realized_savings, is_finalized,
                        finalized_at, finalized_by, created_at, updated_at, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    plan_id,
                    str(plan_data.get("client_id", "")),
                    str(plan_data.get("return_id", "")),
                    plan_data.get("tax_year", 2025),
                    plan_data.get("computation_statement"),
                    plan_data.get("total_potential_savings", 0),
                    plan_data.get("total_realized_savings", 0),
                    1 if plan_data.get("is_finalized") else 0,
                    plan_data.get("finalized_at"),
                    plan_data.get("finalized_by"),
                    now,
                    now,
                    1
                ))

            # Save recommendations
            recommendations = plan_data.get("recommendations", [])
            for rec in recommendations:
                self._save_recommendation(cursor, plan_id, rec, now)

            conn.commit()

        return plan_id

    def _save_recommendation(
        self,
        cursor: sqlite3.Cursor,
        plan_id: str,
        rec_data: Dict[str, Any],
        now: str
    ):
        """Save a single recommendation."""
        rec_id = str(rec_data.get("recommendation_id", ""))

        cursor.execute(
            "SELECT recommendation_id FROM recommendations WHERE recommendation_id = ?",
            (rec_id,)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE recommendations SET
                    category = ?,
                    priority = ?,
                    title = ?,
                    summary = ?,
                    detailed_explanation = ?,
                    estimated_savings = ?,
                    confidence_level = ?,
                    complexity = ?,
                    action_steps = ?,
                    status = ?,
                    status_changed_at = ?,
                    status_changed_by = ?,
                    decline_reason = ?,
                    actual_savings = ?,
                    outcome_notes = ?,
                    related_scenario_id = ?,
                    irs_references = ?
                WHERE recommendation_id = ?
            """, (
                rec_data.get("category", ""),
                rec_data.get("priority", ""),
                rec_data.get("title", ""),
                rec_data.get("summary", ""),
                rec_data.get("detailed_explanation"),
                rec_data.get("estimated_savings", 0),
                rec_data.get("confidence_level", 0.8),
                rec_data.get("complexity", "medium"),
                json.dumps(rec_data.get("action_steps", []), default=str),
                rec_data.get("status", "proposed"),
                rec_data.get("status_changed_at"),
                rec_data.get("status_changed_by"),
                rec_data.get("decline_reason"),
                rec_data.get("actual_savings"),
                rec_data.get("outcome_notes"),
                rec_data.get("related_scenario_id"),
                json.dumps(rec_data.get("irs_references", []), default=str),
                rec_id
            ))
        else:
            cursor.execute("""
                INSERT INTO recommendations (
                    recommendation_id, plan_id, category, priority, title, summary,
                    detailed_explanation, estimated_savings, confidence_level,
                    complexity, action_steps, status, status_changed_at,
                    status_changed_by, decline_reason, actual_savings,
                    outcome_notes, related_scenario_id, irs_references, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec_id,
                plan_id,
                rec_data.get("category", ""),
                rec_data.get("priority", ""),
                rec_data.get("title", ""),
                rec_data.get("summary", ""),
                rec_data.get("detailed_explanation"),
                rec_data.get("estimated_savings", 0),
                rec_data.get("confidence_level", 0.8),
                rec_data.get("complexity", "medium"),
                json.dumps(rec_data.get("action_steps", []), default=str),
                rec_data.get("status", "proposed"),
                rec_data.get("status_changed_at"),
                rec_data.get("status_changed_by"),
                rec_data.get("decline_reason"),
                rec_data.get("actual_savings"),
                rec_data.get("outcome_notes"),
                rec_data.get("related_scenario_id"),
                json.dumps(rec_data.get("irs_references", []), default=str),
                now
            ))

    def load_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """
        Load an advisory plan with its recommendations.

        Args:
            plan_id: The plan ID

        Returns:
            Plan data dictionary or None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Load plan
            cursor.execute(
                "SELECT * FROM advisory_plans WHERE plan_id = ?",
                (plan_id,)
            )
            plan_row = cursor.fetchone()

            if not plan_row:
                return None

            # Load recommendations
            cursor.execute(
                """SELECT * FROM recommendations
                   WHERE plan_id = ?
                   ORDER BY priority, estimated_savings DESC""",
                (plan_id,)
            )
            rec_rows = cursor.fetchall()

            return self._rows_to_plan_dict(plan_row, rec_rows)

    def load_plans_for_client(self, client_id: str) -> List[Dict[str, Any]]:
        """
        Load all plans for a client.

        Args:
            client_id: The client ID

        Returns:
            List of plan dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """SELECT * FROM advisory_plans
                   WHERE client_id = ?
                   ORDER BY created_at DESC""",
                (client_id,)
            )
            plan_rows = cursor.fetchall()

            plans = []
            for plan_row in plan_rows:
                cursor.execute(
                    """SELECT * FROM recommendations
                       WHERE plan_id = ?
                       ORDER BY priority, estimated_savings DESC""",
                    (plan_row["plan_id"],)
                )
                rec_rows = cursor.fetchall()
                plans.append(self._rows_to_plan_dict(plan_row, rec_rows))

            return plans

    def delete_plan(self, plan_id: str) -> bool:
        """
        Delete a plan and its recommendations.

        Args:
            plan_id: The plan ID

        Returns:
            True if deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Recommendations will be cascade deleted
            cursor.execute(
                "DELETE FROM advisory_plans WHERE plan_id = ?",
                (plan_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_recommendation_status(
        self,
        recommendation_id: str,
        status: str,
        changed_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Update a recommendation's status.

        Args:
            recommendation_id: The recommendation ID
            status: New status
            changed_by: Who made the change
            reason: Optional reason

        Returns:
            True if updated
        """
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE recommendations SET
                    status = ?,
                    status_changed_at = ?,
                    status_changed_by = ?,
                    decline_reason = ?
                WHERE recommendation_id = ?
            """, (status, now, changed_by, reason, recommendation_id))
            conn.commit()
            return cursor.rowcount > 0

    def record_recommendation_outcome(
        self,
        recommendation_id: str,
        actual_savings: float,
        notes: Optional[str] = None
    ) -> bool:
        """
        Record actual outcome for a recommendation.

        Args:
            recommendation_id: The recommendation ID
            actual_savings: Actual savings realized
            notes: Optional notes

        Returns:
            True if updated
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE recommendations SET
                    actual_savings = ?,
                    outcome_notes = ?,
                    status = 'implemented'
                WHERE recommendation_id = ?
            """, (actual_savings, notes, recommendation_id))
            conn.commit()
            return cursor.rowcount > 0

    def _rows_to_plan_dict(
        self,
        plan_row: sqlite3.Row,
        rec_rows: List[sqlite3.Row]
    ) -> Dict[str, Any]:
        """Convert database rows to plan dictionary."""
        recommendations = []
        for rec_row in rec_rows:
            recommendations.append({
                "recommendation_id": rec_row["recommendation_id"],
                "plan_id": rec_row["plan_id"],
                "category": rec_row["category"],
                "priority": rec_row["priority"],
                "title": rec_row["title"],
                "summary": rec_row["summary"],
                "detailed_explanation": rec_row["detailed_explanation"],
                "estimated_savings": rec_row["estimated_savings"],
                "confidence_level": rec_row["confidence_level"],
                "complexity": rec_row["complexity"],
                "action_steps": json.loads(rec_row["action_steps"]) if rec_row["action_steps"] else [],
                "status": rec_row["status"],
                "status_changed_at": rec_row["status_changed_at"],
                "status_changed_by": rec_row["status_changed_by"],
                "decline_reason": rec_row["decline_reason"],
                "actual_savings": rec_row["actual_savings"],
                "outcome_notes": rec_row["outcome_notes"],
                "related_scenario_id": rec_row["related_scenario_id"],
                "irs_references": json.loads(rec_row["irs_references"]) if rec_row["irs_references"] else [],
                "created_at": rec_row["created_at"],
            })

        return {
            "plan_id": plan_row["plan_id"],
            "client_id": plan_row["client_id"],
            "return_id": plan_row["return_id"],
            "tax_year": plan_row["tax_year"],
            "computation_statement": plan_row["computation_statement"],
            "total_potential_savings": plan_row["total_potential_savings"],
            "total_realized_savings": plan_row["total_realized_savings"],
            "is_finalized": bool(plan_row["is_finalized"]),
            "finalized_at": plan_row["finalized_at"],
            "finalized_by": plan_row["finalized_by"],
            "created_at": plan_row["created_at"],
            "updated_at": plan_row["updated_at"],
            "version": plan_row["version"],
            "recommendations": recommendations,
        }


# Global instance
_advisory_persistence: Optional[AdvisoryPersistence] = None


def get_advisory_persistence() -> AdvisoryPersistence:
    """Get the global advisory persistence instance."""
    global _advisory_persistence
    if _advisory_persistence is None:
        _advisory_persistence = AdvisoryPersistence()
    return _advisory_persistence
