"""Audit Trail System.

Comprehensive tracking of all changes, actions, and events
related to tax return preparation and filing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from datetime import datetime
import json
import hashlib
import uuid
from copy import deepcopy


class AuditEventType(Enum):
    """Types of audit events."""
    # Return lifecycle
    RETURN_CREATED = "return_created"
    RETURN_OPENED = "return_opened"
    RETURN_SAVED = "return_saved"
    RETURN_CLOSED = "return_closed"
    RETURN_DELETED = "return_deleted"
    RETURN_ARCHIVED = "return_archived"

    # Data changes
    DATA_ENTERED = "data_entered"
    DATA_MODIFIED = "data_modified"
    DATA_DELETED = "data_deleted"
    DATA_IMPORTED = "data_imported"
    DATA_EXPORTED = "data_exported"

    # Calculations
    CALCULATION_RUN = "calculation_run"
    CALCULATION_VERIFIED = "calculation_verified"
    CALCULATION_OVERRIDE = "calculation_override"

    # Filing
    FILING_PREPARED = "filing_prepared"
    FILING_SUBMITTED = "filing_submitted"
    FILING_ACCEPTED = "filing_accepted"
    FILING_REJECTED = "filing_rejected"
    FILING_AMENDED = "filing_amended"

    # Documents
    DOCUMENT_ATTACHED = "document_attached"
    DOCUMENT_REMOVED = "document_removed"
    DOCUMENT_VERIFIED = "document_verified"

    # Review and approval
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"
    PREPARER_SIGNED = "preparer_signed"
    TAXPAYER_SIGNED = "taxpayer_signed"

    # Access and security
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"

    # System events
    SYSTEM_ERROR = "system_error"
    VALIDATION_ERROR = "validation_error"
    WARNING_GENERATED = "warning_generated"


@dataclass
class ChangeRecord:
    """Records a specific data change."""
    field_path: str  # e.g., "income.w2_wages" or "deductions.mortgage_interest"
    old_value: Any
    new_value: Any
    change_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'field_path': self.field_path,
            'old_value': self._serialize_value(self.old_value),
            'new_value': self._serialize_value(self.new_value),
            'change_reason': self.change_reason
        }

    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for storage."""
        if isinstance(value, (datetime,)):
            return value.isoformat()
        elif hasattr(value, '__dict__'):
            return str(value)
        return value


@dataclass
class AuditEntry:
    """A single entry in the audit trail."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: AuditEventType = AuditEventType.DATA_MODIFIED
    return_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_role: Optional[str] = None  # taxpayer, preparer, reviewer, admin
    ip_address: Optional[str] = None
    description: str = ""
    changes: List[ChangeRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature_hash: Optional[str] = None  # For integrity verification

    def __post_init__(self):
        """Generate signature hash after initialization."""
        if not self.signature_hash:
            self.signature_hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate a hash for integrity verification."""
        data = {
            'entry_id': self.entry_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'return_id': self.return_id,
            'user_id': self.user_id,
            'description': self.description,
            'changes': [c.to_dict() for c in self.changes]
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify the entry has not been tampered with."""
        expected_hash = self._generate_hash()
        return self.signature_hash == expected_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            'entry_id': self.entry_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'return_id': self.return_id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'user_role': self.user_role,
            'ip_address': self.ip_address,
            'description': self.description,
            'changes': [c.to_dict() for c in self.changes],
            'metadata': self.metadata,
            'signature_hash': self.signature_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEntry':
        """Reconstruct from dictionary."""
        changes = [
            ChangeRecord(**c) for c in data.get('changes', [])
        ]
        return cls(
            entry_id=data['entry_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            event_type=AuditEventType(data['event_type']),
            return_id=data.get('return_id'),
            user_id=data.get('user_id'),
            user_name=data.get('user_name'),
            user_role=data.get('user_role'),
            ip_address=data.get('ip_address'),
            description=data.get('description', ''),
            changes=changes,
            metadata=data.get('metadata', {}),
            signature_hash=data.get('signature_hash')
        )


class AuditTrail:
    """
    Comprehensive audit trail for tax return preparation.

    Maintains an immutable, verifiable record of all actions
    and changes made to tax returns.
    """

    def __init__(self, return_id: Optional[str] = None):
        self.return_id = return_id or str(uuid.uuid4())
        self.entries: List[AuditEntry] = []
        self.created_at = datetime.now()
        self._current_user: Optional[Dict[str, str]] = None
        self._previous_state: Dict[str, Any] = {}

    def set_current_user(
        self,
        user_id: str,
        user_name: str,
        user_role: str = "taxpayer",
        ip_address: Optional[str] = None
    ):
        """Set the current user context for audit entries."""
        self._current_user = {
            'user_id': user_id,
            'user_name': user_name,
            'user_role': user_role,
            'ip_address': ip_address
        }

    def log_event(
        self,
        event_type: AuditEventType,
        description: str,
        changes: Optional[List[ChangeRecord]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """Log an audit event."""
        entry = AuditEntry(
            event_type=event_type,
            return_id=self.return_id,
            user_id=self._current_user.get('user_id') if self._current_user else None,
            user_name=self._current_user.get('user_name') if self._current_user else None,
            user_role=self._current_user.get('user_role') if self._current_user else None,
            ip_address=self._current_user.get('ip_address') if self._current_user else None,
            description=description,
            changes=changes or [],
            metadata=metadata or {}
        )
        self.entries.append(entry)
        return entry

    def log_return_created(self, taxpayer_name: str, tax_year: int) -> AuditEntry:
        """Log return creation."""
        return self.log_event(
            AuditEventType.RETURN_CREATED,
            f"Tax return created for {taxpayer_name}, Tax Year {tax_year}",
            metadata={'taxpayer_name': taxpayer_name, 'tax_year': tax_year}
        )

    def log_data_change(
        self,
        field_path: str,
        old_value: Any,
        new_value: Any,
        reason: Optional[str] = None
    ) -> AuditEntry:
        """Log a data modification."""
        change = ChangeRecord(
            field_path=field_path,
            old_value=old_value,
            new_value=new_value,
            change_reason=reason
        )
        return self.log_event(
            AuditEventType.DATA_MODIFIED,
            f"Modified {field_path}",
            changes=[change]
        )

    def log_bulk_changes(
        self,
        changes: List[Dict[str, Any]],
        description: str = "Bulk data update"
    ) -> AuditEntry:
        """Log multiple changes at once."""
        change_records = [
            ChangeRecord(
                field_path=c['field'],
                old_value=c.get('old'),
                new_value=c.get('new'),
                change_reason=c.get('reason')
            )
            for c in changes
        ]
        return self.log_event(
            AuditEventType.DATA_MODIFIED,
            description,
            changes=change_records
        )

    def log_calculation(
        self,
        calculation_type: str,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any]
    ) -> AuditEntry:
        """Log a calculation run."""
        return self.log_event(
            AuditEventType.CALCULATION_RUN,
            f"Calculation performed: {calculation_type}",
            metadata={
                'calculation_type': calculation_type,
                'inputs_summary': {k: v for k, v in list(inputs.items())[:10]},
                'outputs': outputs
            }
        )

    def log_calculation_override(
        self,
        field_path: str,
        calculated_value: Any,
        override_value: Any,
        justification: str
    ) -> AuditEntry:
        """Log when a calculated value is manually overridden."""
        change = ChangeRecord(
            field_path=field_path,
            old_value=calculated_value,
            new_value=override_value,
            change_reason=f"Manual override: {justification}"
        )
        return self.log_event(
            AuditEventType.CALCULATION_OVERRIDE,
            f"Override of calculated value for {field_path}",
            changes=[change],
            metadata={
                'calculated_value': calculated_value,
                'override_value': override_value,
                'justification': justification
            }
        )

    def log_document_attached(
        self,
        document_type: str,
        document_name: str,
        document_hash: str
    ) -> AuditEntry:
        """Log document attachment."""
        return self.log_event(
            AuditEventType.DOCUMENT_ATTACHED,
            f"Document attached: {document_name} ({document_type})",
            metadata={
                'document_type': document_type,
                'document_name': document_name,
                'document_hash': document_hash
            }
        )

    def log_filing_submitted(
        self,
        filing_type: str,
        submission_id: str,
        destination: str
    ) -> AuditEntry:
        """Log filing submission."""
        return self.log_event(
            AuditEventType.FILING_SUBMITTED,
            f"Return submitted: {filing_type} to {destination}",
            metadata={
                'filing_type': filing_type,
                'submission_id': submission_id,
                'destination': destination
            }
        )

    def log_filing_accepted(
        self,
        confirmation_number: str,
        acceptance_timestamp: datetime
    ) -> AuditEntry:
        """Log filing acceptance."""
        return self.log_event(
            AuditEventType.FILING_ACCEPTED,
            f"Filing accepted: {confirmation_number}",
            metadata={
                'confirmation_number': confirmation_number,
                'acceptance_timestamp': acceptance_timestamp.isoformat()
            }
        )

    def log_filing_rejected(
        self,
        rejection_code: str,
        rejection_reason: str
    ) -> AuditEntry:
        """Log filing rejection."""
        return self.log_event(
            AuditEventType.FILING_REJECTED,
            f"Filing rejected: {rejection_code}",
            metadata={
                'rejection_code': rejection_code,
                'rejection_reason': rejection_reason
            }
        )

    def log_signature(
        self,
        signer_type: str,  # 'taxpayer', 'spouse', 'preparer'
        signature_method: str,
        signature_data: Optional[str] = None
    ) -> AuditEntry:
        """Log signature event."""
        event_type = (AuditEventType.TAXPAYER_SIGNED
                     if signer_type in ['taxpayer', 'spouse']
                     else AuditEventType.PREPARER_SIGNED)
        return self.log_event(
            event_type,
            f"{signer_type.title()} signed the return",
            metadata={
                'signer_type': signer_type,
                'signature_method': signature_method,
                'signature_hash': hashlib.sha256(
                    (signature_data or '').encode()
                ).hexdigest() if signature_data else None
            }
        )

    def log_import(
        self,
        source_format: str,
        source_file: Optional[str],
        fields_imported: int,
        fields_skipped: int
    ) -> AuditEntry:
        """Log data import."""
        return self.log_event(
            AuditEventType.DATA_IMPORTED,
            f"Data imported from {source_format}",
            metadata={
                'source_format': source_format,
                'source_file': source_file,
                'fields_imported': fields_imported,
                'fields_skipped': fields_skipped
            }
        )

    def log_export(
        self,
        export_format: str,
        destination: Optional[str] = None
    ) -> AuditEntry:
        """Log data export."""
        return self.log_event(
            AuditEventType.DATA_EXPORTED,
            f"Data exported to {export_format}",
            metadata={
                'export_format': export_format,
                'destination': destination
            }
        )

    def log_error(
        self,
        error_type: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """Log an error."""
        return self.log_event(
            AuditEventType.SYSTEM_ERROR,
            f"Error: {error_type} - {error_message}",
            metadata={
                'error_type': error_type,
                'error_message': error_message,
                'error_details': error_details or {}
            }
        )

    def log_validation_error(
        self,
        field_path: str,
        validation_message: str,
        severity: str = "error"
    ) -> AuditEntry:
        """Log a validation error."""
        return self.log_event(
            AuditEventType.VALIDATION_ERROR,
            f"Validation {severity}: {field_path}",
            metadata={
                'field_path': field_path,
                'validation_message': validation_message,
                'severity': severity
            }
        )

    def track_state(self, state: Dict[str, Any]):
        """Store current state for change detection."""
        self._previous_state = deepcopy(state)

    def detect_changes(self, new_state: Dict[str, Any]) -> List[ChangeRecord]:
        """Detect changes between previous and new state."""
        changes = []
        self._detect_changes_recursive(
            self._previous_state,
            new_state,
            "",
            changes
        )
        return changes

    def _detect_changes_recursive(
        self,
        old: Any,
        new: Any,
        path: str,
        changes: List[ChangeRecord]
    ):
        """Recursively detect changes in nested structures."""
        if isinstance(old, dict) and isinstance(new, dict):
            all_keys = set(old.keys()) | set(new.keys())
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key
                old_val = old.get(key)
                new_val = new.get(key)
                self._detect_changes_recursive(old_val, new_val, new_path, changes)
        elif old != new:
            changes.append(ChangeRecord(
                field_path=path,
                old_value=old,
                new_value=new
            ))

    def get_entries_by_type(self, event_type: AuditEventType) -> List[AuditEntry]:
        """Get all entries of a specific type."""
        return [e for e in self.entries if e.event_type == event_type]

    def get_entries_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[AuditEntry]:
        """Get entries within a date range."""
        return [
            e for e in self.entries
            if start_date <= e.timestamp <= end_date
        ]

    def get_entries_by_user(self, user_id: str) -> List[AuditEntry]:
        """Get all entries for a specific user."""
        return [e for e in self.entries if e.user_id == user_id]

    def get_changes_for_field(self, field_path: str) -> List[AuditEntry]:
        """Get all entries that modified a specific field."""
        return [
            e for e in self.entries
            if any(c.field_path == field_path for c in e.changes)
        ]

    def verify_trail_integrity(self) -> Tuple[bool, List[str]]:
        """Verify the integrity of the entire audit trail."""
        issues = []

        for i, entry in enumerate(self.entries):
            if not entry.verify_integrity():
                issues.append(f"Entry {i} ({entry.entry_id}): Integrity check failed")

            # Check chronological order
            if i > 0 and entry.timestamp < self.entries[i-1].timestamp:
                issues.append(f"Entry {i}: Timestamp out of order")

        return len(issues) == 0, issues

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the audit trail."""
        event_counts = {}
        for entry in self.entries:
            event_type = entry.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        users = set()
        for entry in self.entries:
            if entry.user_id:
                users.add(entry.user_id)

        return {
            'return_id': self.return_id,
            'created_at': self.created_at.isoformat(),
            'total_entries': len(self.entries),
            'event_counts': event_counts,
            'unique_users': len(users),
            'first_entry': self.entries[0].timestamp.isoformat() if self.entries else None,
            'last_entry': self.entries[-1].timestamp.isoformat() if self.entries else None,
            'integrity_verified': self.verify_trail_integrity()[0]
        }

    def to_json(self) -> str:
        """Serialize audit trail to JSON."""
        return json.dumps({
            'return_id': self.return_id,
            'created_at': self.created_at.isoformat(),
            'entries': [e.to_dict() for e in self.entries]
        }, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'AuditTrail':
        """Deserialize audit trail from JSON."""
        data = json.loads(json_str)
        trail = cls(return_id=data['return_id'])
        trail.created_at = datetime.fromisoformat(data['created_at'])
        trail.entries = [AuditEntry.from_dict(e) for e in data['entries']]
        return trail

    def generate_audit_report(self) -> str:
        """Generate a human-readable audit report."""
        lines = [
            "=" * 60,
            "AUDIT TRAIL REPORT",
            "=" * 60,
            f"Return ID: {self.return_id}",
            f"Created: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Events: {len(self.entries)}",
            "",
            "CHRONOLOGICAL EVENT LOG",
            "-" * 60
        ]

        for entry in self.entries:
            lines.append(f"\n[{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}]")
            lines.append(f"  Event: {entry.event_type.value}")
            lines.append(f"  User: {entry.user_name or 'System'} ({entry.user_role or 'N/A'})")
            lines.append(f"  Description: {entry.description}")

            if entry.changes:
                lines.append("  Changes:")
                for change in entry.changes:
                    lines.append(f"    - {change.field_path}: {change.old_value} -> {change.new_value}")
                    if change.change_reason:
                        lines.append(f"      Reason: {change.change_reason}")

        lines.extend([
            "",
            "=" * 60,
            "INTEGRITY VERIFICATION",
            "-" * 60
        ])

        is_valid, issues = self.verify_trail_integrity()
        if is_valid:
            lines.append("All entries passed integrity verification.")
        else:
            lines.append("INTEGRITY ISSUES DETECTED:")
            for issue in issues:
                lines.append(f"  - {issue}")

        lines.append("=" * 60)

        return "\n".join(lines)
