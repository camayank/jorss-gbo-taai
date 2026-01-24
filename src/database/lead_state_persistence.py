"""
Lead State Persistence Layer.

Provides database-backed persistence for lead state management,
replacing in-memory storage with durable storage.

Tables:
- leads: Core lead records with current state
- lead_signals: Signal history for each lead
- lead_transitions: State transition history

All data is scoped by tenant_id for multi-tenant isolation.

SECURITY: PII fields (email, phone, ssn) are encrypted at rest.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import logging

from .encrypted_fields import (
    encrypt_email, decrypt_email,
    encrypt_phone, decrypt_phone,
    encrypt_ssn, decrypt_ssn,
    mask_email, mask_phone, mask_ssn
)

logger = logging.getLogger(__name__)

# PII fields that should be encrypted in metadata
PII_FIELDS = {'email', 'phone', 'ssn', 'social_security_number'}

# Use same database path as main persistence
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "tax_returns.db"


@dataclass
class LeadDbRecord:
    """Persisted lead record."""
    lead_id: str
    session_id: str
    tenant_id: str
    current_state: str  # LeadState name (BROWSING, CURIOUS, etc.)
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalDbRecord:
    """Persisted signal record."""
    id: int
    lead_id: str
    signal_id: str
    tenant_id: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransitionDbRecord:
    """Persisted transition record."""
    id: int
    lead_id: str
    from_state: str
    to_state: str
    trigger_signal_id: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class LeadStatePersistence:
    """
    Database-backed persistence for lead state management.

    Provides durable storage for:
    - Lead records with current state
    - Signal history
    - State transitions

    SECURITY: PII fields are encrypted before storage.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize lead state persistence.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_tables_exist()

    def _encrypt_metadata(self, metadata: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """
        Encrypt PII fields in metadata before storage.

        Args:
            metadata: Lead metadata dictionary
            tenant_id: Tenant ID for key binding

        Returns:
            Copy of metadata with PII fields encrypted
        """
        if not metadata:
            return metadata

        encrypted = metadata.copy()

        # Encrypt email
        if 'email' in encrypted and encrypted['email']:
            original_email = encrypted['email']
            encrypted['email'] = encrypt_email(original_email, tenant_id)
            encrypted['email_masked'] = mask_email(original_email)

        # Encrypt phone
        if 'phone' in encrypted and encrypted['phone']:
            original_phone = encrypted['phone']
            encrypted['phone'] = encrypt_phone(original_phone, tenant_id)
            encrypted['phone_masked'] = mask_phone(original_phone)

        # Encrypt SSN (multiple possible field names)
        for ssn_field in ['ssn', 'social_security_number']:
            if ssn_field in encrypted and encrypted[ssn_field]:
                original_ssn = encrypted[ssn_field]
                encrypted[ssn_field] = encrypt_ssn(original_ssn, tenant_id)
                encrypted['ssn_masked'] = mask_ssn(original_ssn)

        # Mark as encrypted for migration tracking
        encrypted['_pii_encrypted'] = True

        return encrypted

    def _decrypt_metadata(self, metadata: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """
        Decrypt PII fields in metadata after retrieval.

        Args:
            metadata: Encrypted metadata dictionary
            tenant_id: Tenant ID for key binding

        Returns:
            Copy of metadata with PII fields decrypted
        """
        if not metadata:
            return metadata

        # Check if encryption was applied
        if not metadata.get('_pii_encrypted'):
            # Legacy unencrypted data - return as-is
            return metadata

        decrypted = metadata.copy()

        try:
            # Decrypt email
            if 'email' in decrypted and decrypted['email']:
                decrypted['email'] = decrypt_email(decrypted['email'], tenant_id)

            # Decrypt phone
            if 'phone' in decrypted and decrypted['phone']:
                decrypted['phone'] = decrypt_phone(decrypted['phone'], tenant_id)

            # Decrypt SSN
            for ssn_field in ['ssn', 'social_security_number']:
                if ssn_field in decrypted and decrypted[ssn_field]:
                    decrypted[ssn_field] = decrypt_ssn(decrypted[ssn_field], tenant_id)

        except Exception as e:
            logger.error(f"Failed to decrypt lead metadata: {e}")
            # Return with masked values for safety
            if 'email_masked' in decrypted:
                decrypted['email'] = decrypted['email_masked']
            if 'phone_masked' in decrypted:
                decrypted['phone'] = decrypted['phone_masked']
            if 'ssn_masked' in decrypted:
                for ssn_field in ['ssn', 'social_security_number']:
                    if ssn_field in decrypted:
                        decrypted[ssn_field] = decrypted.get('ssn_masked', '***-**-****')

        return decrypted

    def _ensure_tables_exist(self):
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Leads table - core lead records
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    lead_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    current_state TEXT NOT NULL DEFAULT 'BROWSING',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
            """)

            # Lead signals table - signal history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lead_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (lead_id) REFERENCES leads(lead_id)
                )
            """)

            # Lead transitions table - state change history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lead_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lead_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    trigger_signal_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (lead_id) REFERENCES leads(lead_id)
                )
            """)

            # Indexes for efficient lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_leads_tenant
                ON leads(tenant_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_leads_state
                ON leads(current_state)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_leads_session
                ON leads(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lead_signals_lead
                ON lead_signals(lead_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lead_signals_tenant
                ON lead_signals(tenant_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lead_transitions_lead
                ON lead_transitions(lead_id)
            """)

            conn.commit()

    # =========================================================================
    # LEAD METHODS
    # =========================================================================

    def save_lead(
        self,
        lead_id: str,
        session_id: str,
        tenant_id: str = "default",
        current_state: str = "BROWSING",
        metadata: Optional[Dict[str, Any]] = None
    ) -> LeadDbRecord:
        """
        Save or update a lead record.

        SECURITY: PII fields in metadata are encrypted before storage.

        Args:
            lead_id: Unique lead identifier
            session_id: Associated session identifier
            tenant_id: Tenant identifier for isolation
            current_state: Current lead state name
            metadata: Additional metadata (email, phone, ssn will be encrypted)

        Returns:
            Saved LeadDbRecord (with original unencrypted metadata for caller)
        """
        now = datetime.utcnow().isoformat()
        original_metadata = metadata or {}

        # Encrypt PII before storage
        encrypted_metadata = self._encrypt_metadata(original_metadata, tenant_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT lead_id, created_at FROM leads WHERE lead_id = ?",
                (lead_id,)
            )
            existing = cursor.fetchone()

            if existing:
                created_at = existing[1]
                cursor.execute("""
                    UPDATE leads SET
                        session_id = ?,
                        tenant_id = ?,
                        current_state = ?,
                        updated_at = ?,
                        metadata_json = ?
                    WHERE lead_id = ?
                """, (
                    session_id,
                    tenant_id,
                    current_state,
                    now,
                    json.dumps(encrypted_metadata, default=str),
                    lead_id
                ))
            else:
                created_at = now
                cursor.execute("""
                    INSERT INTO leads (
                        lead_id, session_id, tenant_id,
                        current_state, created_at, updated_at,
                        metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    lead_id,
                    session_id,
                    tenant_id,
                    current_state,
                    now,
                    now,
                    json.dumps(encrypted_metadata, default=str)
                ))

            conn.commit()

        # Return with original unencrypted metadata for caller convenience
        return LeadDbRecord(
            lead_id=lead_id,
            session_id=session_id,
            tenant_id=tenant_id,
            current_state=current_state,
            created_at=created_at,
            updated_at=now,
            metadata=original_metadata
        )

    def load_lead(
        self,
        lead_id: str,
        tenant_id: Optional[str] = None,
        decrypt_pii: bool = True
    ) -> Optional[LeadDbRecord]:
        """
        Load a lead by ID.

        SECURITY: PII fields are decrypted after retrieval.

        Args:
            lead_id: Lead identifier
            tenant_id: Optional tenant filter for security
            decrypt_pii: Whether to decrypt PII fields (default True)

        Returns:
            LeadDbRecord or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if tenant_id:
                cursor.execute("""
                    SELECT lead_id, session_id, tenant_id,
                           current_state, created_at, updated_at,
                           metadata_json
                    FROM leads
                    WHERE lead_id = ? AND tenant_id = ?
                """, (lead_id, tenant_id))
            else:
                cursor.execute("""
                    SELECT lead_id, session_id, tenant_id,
                           current_state, created_at, updated_at,
                           metadata_json
                    FROM leads
                    WHERE lead_id = ?
                """, (lead_id,))

            row = cursor.fetchone()
            if not row:
                return None

            lead_tenant_id = row[2]
            raw_metadata = json.loads(row[6]) if row[6] else {}

            # Decrypt PII fields if requested
            if decrypt_pii:
                metadata = self._decrypt_metadata(raw_metadata, lead_tenant_id)
            else:
                metadata = raw_metadata

            return LeadDbRecord(
                lead_id=row[0],
                session_id=row[1],
                tenant_id=lead_tenant_id,
                current_state=row[3],
                created_at=row[4],
                updated_at=row[5],
                metadata=metadata
            )

    def delete_lead(self, lead_id: str) -> bool:
        """Delete a lead and all related data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Delete signals
            cursor.execute(
                "DELETE FROM lead_signals WHERE lead_id = ?",
                (lead_id,)
            )

            # Delete transitions
            cursor.execute(
                "DELETE FROM lead_transitions WHERE lead_id = ?",
                (lead_id,)
            )

            # Delete lead
            cursor.execute(
                "DELETE FROM leads WHERE lead_id = ?",
                (lead_id,)
            )

            conn.commit()
            return cursor.rowcount > 0

    def list_leads(
        self,
        tenant_id: str = "default",
        limit: int = 100,
        offset: int = 0,
        decrypt_pii: bool = True
    ) -> List[LeadDbRecord]:
        """
        List all leads for a tenant.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of leads to return
            offset: Pagination offset
            decrypt_pii: Whether to decrypt PII fields (default True)

        Returns:
            List of LeadDbRecord
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lead_id, session_id, tenant_id,
                       current_state, created_at, updated_at,
                       metadata_json
                FROM leads
                WHERE tenant_id = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """, (tenant_id, limit, offset))

            leads = []
            for row in cursor.fetchall():
                raw_metadata = json.loads(row[6]) if row[6] else {}

                if decrypt_pii:
                    metadata = self._decrypt_metadata(raw_metadata, tenant_id)
                else:
                    metadata = raw_metadata

                leads.append(LeadDbRecord(
                    lead_id=row[0],
                    session_id=row[1],
                    tenant_id=row[2],
                    current_state=row[3],
                    created_at=row[4],
                    updated_at=row[5],
                    metadata=metadata
                ))
            return leads

    def list_leads_by_state(
        self,
        state: str,
        tenant_id: str = "default",
        limit: int = 100,
        offset: int = 0,
        decrypt_pii: bool = True
    ) -> List[LeadDbRecord]:
        """
        List leads by state for a tenant.

        Args:
            state: Lead state filter (BROWSING, CURIOUS, etc.)
            tenant_id: Tenant identifier
            limit: Maximum number of leads to return
            offset: Pagination offset
            decrypt_pii: Whether to decrypt PII fields (default True)

        Returns:
            List of LeadDbRecord
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lead_id, session_id, tenant_id,
                       current_state, created_at, updated_at,
                       metadata_json
                FROM leads
                WHERE current_state = ? AND tenant_id = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """, (state, tenant_id, limit, offset))

            leads = []
            for row in cursor.fetchall():
                raw_metadata = json.loads(row[6]) if row[6] else {}

                if decrypt_pii:
                    metadata = self._decrypt_metadata(raw_metadata, tenant_id)
                else:
                    metadata = raw_metadata

                leads.append(LeadDbRecord(
                    lead_id=row[0],
                    session_id=row[1],
                    tenant_id=row[2],
                    current_state=row[3],
                    created_at=row[4],
                    updated_at=row[5],
                    metadata=metadata
                ))
            return leads

    def get_state_counts(
        self,
        tenant_id: str = "default"
    ) -> Dict[str, int]:
        """Get count of leads in each state."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT current_state, COUNT(*) as count
                FROM leads
                WHERE tenant_id = ?
                GROUP BY current_state
            """, (tenant_id,))

            counts = {
                "BROWSING": 0,
                "CURIOUS": 0,
                "EVALUATING": 0,
                "ADVISORY_READY": 0,
                "HIGH_LEVERAGE": 0,
            }
            for row in cursor.fetchall():
                counts[row[0]] = row[1]

            return counts

    # =========================================================================
    # SIGNAL METHODS
    # =========================================================================

    def save_signal(
        self,
        lead_id: str,
        signal_id: str,
        tenant_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> SignalDbRecord:
        """
        Record a signal for a lead.

        Args:
            lead_id: Lead identifier
            signal_id: Signal identifier
            tenant_id: Tenant identifier
            metadata: Additional metadata

        Returns:
            Saved SignalDbRecord
        """
        now = datetime.utcnow().isoformat()
        metadata = metadata or {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lead_signals (
                    lead_id, signal_id, tenant_id,
                    timestamp, metadata_json
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                lead_id,
                signal_id,
                tenant_id,
                now,
                json.dumps(metadata, default=str)
            ))
            conn.commit()
            signal_record_id = cursor.lastrowid

        return SignalDbRecord(
            id=signal_record_id,
            lead_id=lead_id,
            signal_id=signal_id,
            tenant_id=tenant_id,
            timestamp=now,
            metadata=metadata
        )

    def get_signals_for_lead(
        self,
        lead_id: str,
        limit: int = 100
    ) -> List[SignalDbRecord]:
        """Get signal history for a lead."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, lead_id, signal_id, tenant_id,
                       timestamp, metadata_json
                FROM lead_signals
                WHERE lead_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (lead_id, limit))

            signals = []
            for row in cursor.fetchall():
                signals.append(SignalDbRecord(
                    id=row[0],
                    lead_id=row[1],
                    signal_id=row[2],
                    tenant_id=row[3],
                    timestamp=row[4],
                    metadata=json.loads(row[5]) if row[5] else {}
                ))
            return signals

    def get_signal_ids_for_lead(self, lead_id: str) -> List[str]:
        """Get just the signal IDs for a lead (for quick access)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT signal_id
                FROM lead_signals
                WHERE lead_id = ?
                ORDER BY timestamp ASC
            """, (lead_id,))

            return [row[0] for row in cursor.fetchall()]

    # =========================================================================
    # TRANSITION METHODS
    # =========================================================================

    def save_transition(
        self,
        lead_id: str,
        from_state: str,
        to_state: str,
        trigger_signal_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TransitionDbRecord:
        """
        Record a state transition.

        Args:
            lead_id: Lead identifier
            from_state: Previous state
            to_state: New state
            trigger_signal_id: Signal that triggered the transition
            metadata: Additional metadata

        Returns:
            Saved TransitionDbRecord
        """
        now = datetime.utcnow().isoformat()
        metadata = metadata or {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lead_transitions (
                    lead_id, from_state, to_state,
                    trigger_signal_id, timestamp, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                lead_id,
                from_state,
                to_state,
                trigger_signal_id,
                now,
                json.dumps(metadata, default=str)
            ))
            conn.commit()
            transition_id = cursor.lastrowid

        return TransitionDbRecord(
            id=transition_id,
            lead_id=lead_id,
            from_state=from_state,
            to_state=to_state,
            trigger_signal_id=trigger_signal_id,
            timestamp=now,
            metadata=metadata
        )

    def get_transitions_for_lead(
        self,
        lead_id: str,
        limit: int = 100
    ) -> List[TransitionDbRecord]:
        """Get transition history for a lead."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, lead_id, from_state, to_state,
                       trigger_signal_id, timestamp, metadata_json
                FROM lead_transitions
                WHERE lead_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (lead_id, limit))

            transitions = []
            for row in cursor.fetchall():
                transitions.append(TransitionDbRecord(
                    id=row[0],
                    lead_id=row[1],
                    from_state=row[2],
                    to_state=row[3],
                    trigger_signal_id=row[4],
                    timestamp=row[5],
                    metadata=json.loads(row[6]) if row[6] else {}
                ))
            return transitions

    # =========================================================================
    # FULL LEAD LOAD (with signals and transitions)
    # =========================================================================

    def load_full_lead(
        self,
        lead_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Load a complete lead with signals and transitions.

        Args:
            lead_id: Lead identifier
            tenant_id: Optional tenant filter

        Returns:
            Dict with lead, signals, and transitions, or None
        """
        lead = self.load_lead(lead_id, tenant_id)
        if not lead:
            return None

        signals = self.get_signals_for_lead(lead_id)
        transitions = self.get_transitions_for_lead(lead_id)

        return {
            "lead": lead,
            "signals": signals,
            "transitions": transitions,
        }


# Global instance
_lead_state_persistence: Optional[LeadStatePersistence] = None


def get_lead_state_persistence() -> LeadStatePersistence:
    """Get the global lead state persistence instance."""
    global _lead_state_persistence
    if _lead_state_persistence is None:
        _lead_state_persistence = LeadStatePersistence()
    return _lead_state_persistence
