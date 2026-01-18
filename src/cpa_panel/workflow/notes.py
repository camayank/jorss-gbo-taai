"""
CPA Notes Manager

Manages review notes and documentation for tax returns:
- Internal CPA notes
- Client-facing notes
- Audit-trailed note history
"""

import json
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class NoteCategory(str, Enum):
    """Categories for CPA notes."""
    GENERAL = "general"
    REVIEW = "review"
    QUESTION = "question"
    RECOMMENDATION = "recommendation"
    WARNING = "warning"
    APPROVAL = "approval"
    CORRECTION = "correction"


@dataclass
class CPANote:
    """A CPA review note."""
    id: str
    text: str
    category: NoteCategory
    cpa_id: str
    cpa_name: str
    timestamp: datetime
    is_internal: bool = False
    parent_note_id: Optional[str] = None  # For threaded discussions

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "category": self.category.value,
            "cpa_id": self.cpa_id,
            "cpa_name": self.cpa_name,
            "timestamp": self.timestamp.isoformat(),
            "is_internal": self.is_internal,
            "parent_note_id": self.parent_note_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CPANote":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            text=data.get("text", ""),
            category=NoteCategory(data.get("category", "general")),
            cpa_id=data.get("cpa_id", ""),
            cpa_name=data.get("cpa_name", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.utcnow(),
            is_internal=data.get("is_internal", False),
            parent_note_id=data.get("parent_note_id"),
        )


class NotesManager:
    """
    Manages CPA notes for tax returns.

    CPA Compliance:
    - Notes are timestamped and attributed
    - Internal vs client-facing separation
    - Full audit trail integration
    """

    def __init__(self, persistence=None, audit_logger=None):
        """
        Initialize notes manager.

        Args:
            persistence: Database persistence layer
            audit_logger: Audit trail logging function
        """
        self._persistence = persistence
        self._audit_logger = audit_logger

    def _get_persistence(self):
        """Get or create persistence layer."""
        if self._persistence is None:
            from database.session_persistence import get_session_persistence
            self._persistence = get_session_persistence()
        return self._persistence

    def _load_notes(self, session_id: str) -> List[CPANote]:
        """Load notes from persistence."""
        persistence = self._get_persistence()
        status_record = persistence.get_return_status(session_id)

        if not status_record or not status_record.get("review_notes"):
            return []

        try:
            notes_data = json.loads(status_record["review_notes"])
            if isinstance(notes_data, list):
                return [CPANote.from_dict(n) for n in notes_data]
            else:
                # Legacy format - single note string
                return [CPANote(
                    id="legacy",
                    text=str(notes_data),
                    category=NoteCategory.GENERAL,
                    cpa_id="",
                    cpa_name="",
                    timestamp=datetime.utcnow(),
                )]
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse notes: {e}")
            return []

    def _save_notes(self, session_id: str, notes: List[CPANote]) -> None:
        """Save notes to persistence."""
        persistence = self._get_persistence()
        status_record = persistence.get_return_status(session_id)

        notes_json = json.dumps([n.to_dict() for n in notes])

        persistence.set_return_status(
            session_id=session_id,
            status=status_record["status"] if status_record else "DRAFT",
            review_notes=notes_json,
        )

    def add_note(
        self,
        session_id: str,
        text: str,
        cpa_id: str,
        cpa_name: str,
        category: NoteCategory = NoteCategory.GENERAL,
        is_internal: bool = False,
        parent_note_id: Optional[str] = None,
    ) -> CPANote:
        """
        Add a new CPA note.

        Args:
            session_id: Session/return identifier
            text: Note content
            cpa_id: CPA identifier
            cpa_name: CPA name
            category: Note category
            is_internal: Whether note is internal-only
            parent_note_id: Parent note ID for replies

        Returns:
            Created CPANote
        """
        note = CPANote(
            id=str(uuid.uuid4())[:8],
            text=text,
            category=category,
            cpa_id=cpa_id,
            cpa_name=cpa_name,
            timestamp=datetime.utcnow(),
            is_internal=is_internal,
            parent_note_id=parent_note_id,
        )

        notes = self._load_notes(session_id)
        notes.append(note)
        self._save_notes(session_id, notes)

        # Log audit event
        if self._audit_logger:
            self._audit_logger(
                session_id=session_id,
                event_type="NOTE_ADDED",
                description=f"CPA note added: {category.value}",
                metadata={
                    "note_id": note.id,
                    "category": category.value,
                    "is_internal": is_internal,
                    "cpa_id": cpa_id,
                    "cpa_name": cpa_name,
                }
            )

        return note

    def get_notes(
        self,
        session_id: str,
        include_internal: bool = False,
        category: Optional[NoteCategory] = None,
    ) -> List[CPANote]:
        """
        Get notes for a return.

        Args:
            session_id: Session/return identifier
            include_internal: Whether to include internal notes
            category: Filter by category

        Returns:
            List of CPANote
        """
        notes = self._load_notes(session_id)

        # Filter internal notes
        if not include_internal:
            notes = [n for n in notes if not n.is_internal]

        # Filter by category
        if category:
            notes = [n for n in notes if n.category == category]

        # Sort by timestamp (newest first)
        notes.sort(key=lambda n: n.timestamp, reverse=True)

        return notes

    def get_note_by_id(self, session_id: str, note_id: str) -> Optional[CPANote]:
        """
        Get a specific note by ID.

        Args:
            session_id: Session/return identifier
            note_id: Note identifier

        Returns:
            CPANote if found, None otherwise
        """
        notes = self._load_notes(session_id)
        for note in notes:
            if note.id == note_id:
                return note
        return None

    def update_note(
        self,
        session_id: str,
        note_id: str,
        text: Optional[str] = None,
        category: Optional[NoteCategory] = None,
    ) -> Optional[CPANote]:
        """
        Update an existing note.

        Args:
            session_id: Session/return identifier
            note_id: Note identifier
            text: New text (optional)
            category: New category (optional)

        Returns:
            Updated CPANote if found, None otherwise
        """
        notes = self._load_notes(session_id)

        for i, note in enumerate(notes):
            if note.id == note_id:
                if text is not None:
                    note.text = text
                if category is not None:
                    note.category = category

                notes[i] = note
                self._save_notes(session_id, notes)

                # Log audit event
                if self._audit_logger:
                    self._audit_logger(
                        session_id=session_id,
                        event_type="NOTE_UPDATED",
                        description=f"CPA note updated: {note_id}",
                        metadata={
                            "note_id": note_id,
                            "updated_text": text is not None,
                            "updated_category": category.value if category else None,
                        }
                    )

                return note

        return None

    def delete_note(self, session_id: str, note_id: str) -> bool:
        """
        Delete a note.

        Args:
            session_id: Session/return identifier
            note_id: Note identifier

        Returns:
            True if deleted, False if not found
        """
        notes = self._load_notes(session_id)
        original_count = len(notes)

        notes = [n for n in notes if n.id != note_id]

        if len(notes) < original_count:
            self._save_notes(session_id, notes)

            # Log audit event
            if self._audit_logger:
                self._audit_logger(
                    session_id=session_id,
                    event_type="NOTE_DELETED",
                    description=f"CPA note deleted: {note_id}",
                    metadata={"note_id": note_id}
                )

            return True

        return False

    def get_note_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get summary of notes for a return.

        Args:
            session_id: Session/return identifier

        Returns:
            Summary dict with counts by category
        """
        notes = self._load_notes(session_id)

        by_category = {}
        for note in notes:
            cat = note.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        internal_count = sum(1 for n in notes if n.is_internal)
        client_count = len(notes) - internal_count

        return {
            "total_notes": len(notes),
            "internal_notes": internal_count,
            "client_visible_notes": client_count,
            "by_category": by_category,
            "last_note": notes[0].to_dict() if notes else None,
        }

    def get_conversation_thread(
        self,
        session_id: str,
        parent_note_id: Optional[str] = None,
    ) -> List[CPANote]:
        """
        Get a conversation thread (note and replies).

        Args:
            session_id: Session/return identifier
            parent_note_id: Parent note ID (None for top-level notes)

        Returns:
            List of notes in thread order
        """
        notes = self._load_notes(session_id)

        if parent_note_id:
            # Get parent and all replies
            thread = [n for n in notes if n.id == parent_note_id or n.parent_note_id == parent_note_id]
        else:
            # Get top-level notes only
            thread = [n for n in notes if n.parent_note_id is None]

        # Sort by timestamp (oldest first for conversation flow)
        thread.sort(key=lambda n: n.timestamp)

        return thread
