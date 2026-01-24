"""
Activity Logging Service

Comprehensive activity logging for leads:
1. Email sends (type, timestamp, status)
2. State changes (old state, new state, who changed)
3. CPA actions (view, contact, note, etc.)
4. System events (report generation, reminders)

All activities are stored for compliance and displayed in lead timeline.
"""

from __future__ import annotations

import uuid
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class ActivityType(str, Enum):
    """Types of lead activities."""
    # Lead lifecycle
    LEAD_CREATED = "lead_created"
    LEAD_CAPTURED = "lead_captured"
    STATE_CHANGE = "state_change"

    # CPA actions
    CPA_VIEWED = "cpa_viewed"
    CPA_CONTACTED = "cpa_contacted"
    CPA_ENGAGED = "cpa_engaged"
    CPA_NOTE_ADDED = "cpa_note_added"
    CPA_ASSIGNED = "cpa_assigned"

    # System events
    REPORT_GENERATED = "report_generated"
    REPORT_DELIVERED = "report_delivered"
    EMAIL_SENT = "email_sent"
    REMINDER_CREATED = "reminder_created"
    REMINDER_COMPLETED = "reminder_completed"

    # Engagement
    ENGAGEMENT_LETTER_SENT = "engagement_letter_sent"
    ENGAGEMENT_LETTER_SIGNED = "engagement_letter_signed"

    # Conversion
    LEAD_CONVERTED = "lead_converted"
    LEAD_ARCHIVED = "lead_archived"


class ActivityActor(str, Enum):
    """Who performed the activity."""
    SYSTEM = "system"
    CPA = "cpa"
    CLIENT = "client"
    ADMIN = "admin"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Activity:
    """A logged activity."""
    activity_id: str
    lead_id: str
    activity_type: ActivityType
    actor: ActivityActor
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "lead_id": self.lead_id,
            "activity_type": self.activity_type.value,
            "actor": self.actor.value,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "description": self.description,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# ACTIVITY SERVICE
# =============================================================================

class ActivityService:
    """Service for logging and retrieving lead activities."""

    _instance: Optional['ActivityService'] = None

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self._db_path = db_path
        else:
            self._db_path = str(Path(__file__).parent.parent.parent / "database" / "jorss_gbo.db")

        self._ensure_tables()

    @classmethod
    def get_instance(cls) -> 'ActivityService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        """Ensure activity tables exist."""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id TEXT UNIQUE NOT NULL,
                lead_id TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                actor_id TEXT,
                actor_name TEXT,
                description TEXT,
                metadata_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for fast lead activity queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activities_lead_id
            ON lead_activities(lead_id, created_at DESC)
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # CORE LOGGING METHODS
    # =========================================================================

    def log_activity(
        self,
        lead_id: str,
        activity_type: ActivityType,
        actor: ActivityActor = ActivityActor.SYSTEM,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Activity:
        """
        Log an activity for a lead.

        Args:
            lead_id: Lead identifier
            activity_type: Type of activity
            actor: Who performed the activity
            actor_id: ID of the actor (CPA ID, client ID, etc.)
            actor_name: Display name of the actor
            description: Human-readable description
            metadata: Additional data (old_state, new_state, email_id, etc.)

        Returns:
            Created Activity
        """
        activity_id = f"act-{uuid.uuid4().hex[:12]}"

        # Generate description if not provided
        if not description:
            description = self._generate_description(activity_type, actor_name, metadata)

        activity = Activity(
            activity_id=activity_id,
            lead_id=lead_id,
            activity_type=activity_type,
            actor=actor,
            actor_id=actor_id,
            actor_name=actor_name,
            description=description,
            metadata=metadata or {},
        )

        # Persist
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lead_activities (
                    activity_id, lead_id, activity_type, actor,
                    actor_id, actor_name, description, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                activity_id,
                lead_id,
                activity_type.value,
                actor.value,
                actor_id,
                actor_name,
                description,
                json.dumps(metadata or {}),
            ))
            conn.commit()
            conn.close()
            logger.debug(f"Logged activity {activity_id} for lead {lead_id}: {activity_type.value}")
        except Exception as e:
            logger.error(f"Failed to log activity: {e}")

        return activity

    def _generate_description(
        self,
        activity_type: ActivityType,
        actor_name: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> str:
        """Generate a human-readable description for the activity."""
        actor = actor_name or "System"
        meta = metadata or {}

        descriptions = {
            ActivityType.LEAD_CREATED: "Lead created from tax assessment",
            ActivityType.LEAD_CAPTURED: f"Contact info captured: {meta.get('email', '')}",
            ActivityType.STATE_CHANGE: f"State changed from {meta.get('old_state', '?')} to {meta.get('new_state', '?')}",
            ActivityType.CPA_VIEWED: f"{actor} viewed lead details",
            ActivityType.CPA_CONTACTED: f"{actor} marked as contacted",
            ActivityType.CPA_ENGAGED: f"{actor} engaged the lead",
            ActivityType.CPA_NOTE_ADDED: f"{actor} added a note",
            ActivityType.CPA_ASSIGNED: f"Assigned to {meta.get('assigned_to', actor)}",
            ActivityType.REPORT_GENERATED: "Tax advisory report generated",
            ActivityType.REPORT_DELIVERED: "Report delivered via email",
            ActivityType.EMAIL_SENT: f"Email sent: {meta.get('subject', 'Notification')}",
            ActivityType.REMINDER_CREATED: f"Follow-up reminder scheduled for {meta.get('due_date', 'later')}",
            ActivityType.REMINDER_COMPLETED: f"{actor} completed follow-up",
            ActivityType.ENGAGEMENT_LETTER_SENT: "Engagement letter sent",
            ActivityType.ENGAGEMENT_LETTER_SIGNED: "Engagement letter signed",
            ActivityType.LEAD_CONVERTED: f"Lead converted to client by {actor}",
            ActivityType.LEAD_ARCHIVED: f"Lead archived by {actor}",
        }

        return descriptions.get(activity_type, f"Activity: {activity_type.value}")

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def log_lead_created(self, lead_id: str, session_id: Optional[str] = None) -> Activity:
        """Log lead creation."""
        return self.log_activity(
            lead_id=lead_id,
            activity_type=ActivityType.LEAD_CREATED,
            metadata={"session_id": session_id} if session_id else {},
        )

    def log_contact_captured(
        self,
        lead_id: str,
        email: str,
        name: Optional[str] = None,
    ) -> Activity:
        """Log contact info capture."""
        return self.log_activity(
            lead_id=lead_id,
            activity_type=ActivityType.LEAD_CAPTURED,
            metadata={"email": email, "name": name},
        )

    def log_state_change(
        self,
        lead_id: str,
        old_state: str,
        new_state: str,
        changed_by: Optional[str] = None,
    ) -> Activity:
        """Log state transition."""
        return self.log_activity(
            lead_id=lead_id,
            activity_type=ActivityType.STATE_CHANGE,
            actor=ActivityActor.CPA if changed_by else ActivityActor.SYSTEM,
            actor_name=changed_by,
            metadata={"old_state": old_state, "new_state": new_state},
        )

    def log_cpa_viewed(self, lead_id: str, cpa_id: str, cpa_name: str) -> Activity:
        """Log CPA viewing lead."""
        return self.log_activity(
            lead_id=lead_id,
            activity_type=ActivityType.CPA_VIEWED,
            actor=ActivityActor.CPA,
            actor_id=cpa_id,
            actor_name=cpa_name,
        )

    def log_cpa_note(
        self,
        lead_id: str,
        cpa_id: str,
        cpa_name: str,
        note_content: str,
    ) -> Activity:
        """Log CPA adding a note."""
        return self.log_activity(
            lead_id=lead_id,
            activity_type=ActivityType.CPA_NOTE_ADDED,
            actor=ActivityActor.CPA,
            actor_id=cpa_id,
            actor_name=cpa_name,
            metadata={"note": note_content[:500]},  # Truncate for storage
        )

    def log_email_sent(
        self,
        lead_id: str,
        email_type: str,
        subject: str,
        recipient: str,
    ) -> Activity:
        """Log email sent to lead or CPA."""
        return self.log_activity(
            lead_id=lead_id,
            activity_type=ActivityType.EMAIL_SENT,
            metadata={
                "email_type": email_type,
                "subject": subject,
                "recipient": recipient,
            },
        )

    def log_engagement(
        self,
        lead_id: str,
        cpa_id: str,
        cpa_name: str,
    ) -> Activity:
        """Log CPA engaging a lead."""
        return self.log_activity(
            lead_id=lead_id,
            activity_type=ActivityType.CPA_ENGAGED,
            actor=ActivityActor.CPA,
            actor_id=cpa_id,
            actor_name=cpa_name,
        )

    def log_conversion(
        self,
        lead_id: str,
        cpa_id: str,
        cpa_name: str,
        revenue: Optional[float] = None,
    ) -> Activity:
        """Log lead conversion."""
        return self.log_activity(
            lead_id=lead_id,
            activity_type=ActivityType.LEAD_CONVERTED,
            actor=ActivityActor.CPA,
            actor_id=cpa_id,
            actor_name=cpa_name,
            metadata={"revenue": revenue} if revenue else {},
        )

    # =========================================================================
    # RETRIEVAL METHODS
    # =========================================================================

    def get_lead_activities(
        self,
        lead_id: str,
        limit: int = 50,
        activity_types: Optional[List[ActivityType]] = None,
    ) -> List[Activity]:
        """
        Get activity timeline for a lead.

        Args:
            lead_id: Lead identifier
            limit: Maximum activities to return
            activity_types: Filter by specific activity types

        Returns:
            List of activities, most recent first
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            if activity_types:
                type_placeholders = ",".join(["?" for _ in activity_types])
                cursor.execute(f"""
                    SELECT * FROM lead_activities
                    WHERE lead_id = ? AND activity_type IN ({type_placeholders})
                    ORDER BY created_at DESC
                    LIMIT ?
                """, [lead_id] + [t.value for t in activity_types] + [limit])
            else:
                cursor.execute("""
                    SELECT * FROM lead_activities
                    WHERE lead_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (lead_id, limit))

            rows = cursor.fetchall()
            conn.close()

            activities = []
            for row in rows:
                activities.append(Activity(
                    activity_id=row["activity_id"],
                    lead_id=row["lead_id"],
                    activity_type=ActivityType(row["activity_type"]),
                    actor=ActivityActor(row["actor"]),
                    actor_id=row["actor_id"],
                    actor_name=row["actor_name"],
                    description=row["description"],
                    metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
                ))

            return activities

        except Exception as e:
            logger.error(f"Failed to get lead activities: {e}")
            return []

    def get_recent_activities(
        self,
        cpa_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get recent activities across all leads (for dashboard).

        Args:
            cpa_id: Optional CPA filter
            limit: Maximum activities to return

        Returns:
            List of activity dicts with lead info
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Join with leads to get lead names
            cursor.execute("""
                SELECT a.*, l.first_name, l.email
                FROM lead_activities a
                LEFT JOIN lead_magnet_leads l ON a.lead_id = l.lead_id
                ORDER BY a.created_at DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            activities = []
            for row in rows:
                activities.append({
                    "activity_id": row["activity_id"],
                    "lead_id": row["lead_id"],
                    "lead_name": row["first_name"] if "first_name" in row.keys() else None,
                    "lead_email": row["email"] if "email" in row.keys() else None,
                    "type": row["activity_type"],
                    "description": row["description"],
                    "actor": row["actor"],
                    "actor_name": row["actor_name"],
                    "created_at": row["created_at"],
                })

            return activities

        except Exception as e:
            logger.error(f"Failed to get recent activities: {e}")
            return []


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

def get_activity_service() -> ActivityService:
    """Get the activity service singleton."""
    return ActivityService.get_instance()
