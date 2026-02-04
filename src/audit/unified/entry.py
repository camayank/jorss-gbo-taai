"""
Unified Audit Entry Model

Consolidates AuditEntry from audit_trail.py, AuditEvent from
audit_logger.py, and AuditEntry from audit_models.py.

Features:
- Cryptographic hash for integrity verification (from audit_trail.py)
- Session and tenant context (from audit_logger.py)
- Source tracking with confidence (from audit_models.py)
- PII field tracking (compliance requirement)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import hashlib
import hmac
import json
import os
import uuid

from .event_types import AuditEventType, AuditSeverity, AuditSource


# HMAC key for signature verification
_is_production = os.environ.get("APP_ENVIRONMENT", "").lower() in ("production", "prod", "staging")


def _get_hmac_key() -> bytes:
    """Get HMAC key from environment. Required in production."""
    key = os.environ.get("AUDIT_HMAC_KEY")
    if key:
        if len(key) < 32:
            raise ValueError("AUDIT_HMAC_KEY must be at least 32 characters")
        return key.encode("utf-8")

    if _is_production:
        raise RuntimeError(
            "CRITICAL: AUDIT_HMAC_KEY environment variable is required in production. "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    import warnings
    warnings.warn(
        "AUDIT_HMAC_KEY not set - using insecure development default. "
        "Set AUDIT_HMAC_KEY for production.",
        UserWarning
    )
    return b"audit-trail-dev-only-insecure-key"


@dataclass
class ChangeRecord:
    """
    Records a specific data change.

    Tracks old and new values for a specific field path.
    """
    field_path: str  # e.g., "income.wages" or "deductions.mortgage_interest"
    old_value: Any = None
    new_value: Any = None
    change_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "field_path": self.field_path,
            "old_value": self._serialize_value(self.old_value),
            "new_value": self._serialize_value(self.new_value),
            "change_reason": self.change_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChangeRecord":
        """Create from dictionary."""
        return cls(
            field_path=data["field_path"],
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            change_reason=data.get("change_reason"),
        )

    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for storage."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool, list, dict)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def get_summary(self) -> str:
        """Get human-readable change summary."""
        if self.old_value is not None and self.new_value is not None:
            return f"{self.field_path}: {self.old_value} -> {self.new_value}"
        elif self.new_value is not None:
            return f"{self.field_path}: set to {self.new_value}"
        elif self.old_value is not None:
            return f"{self.field_path}: cleared (was {self.old_value})"
        return f"{self.field_path}: unchanged"


@dataclass
class UnifiedAuditEntry:
    """
    Unified audit entry combining all previous implementations.

    Core fields from audit_trail.py:
    - entry_id, timestamp, event_type, signature_hash

    Context fields from audit_logger.py:
    - user_id, user_role, tenant_id, ip_address, user_agent

    Source tracking from audit_models.py:
    - source, confidence, calculation_version
    """

    # Core identification
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Event classification
    event_type: AuditEventType = AuditEventType.TAX_DATA_FIELD_CHANGE
    severity: AuditSeverity = AuditSeverity.INFO

    # Session context
    session_id: Optional[str] = None
    return_id: Optional[str] = None  # Tax return ID
    tenant_id: Optional[str] = None

    # User context
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_role: Optional[str] = None

    # Request context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_path: Optional[str] = None

    # Action details
    action: str = ""  # Human-readable action description
    resource_type: str = ""  # e.g., "tax_return", "income", "document"
    resource_id: Optional[str] = None

    # Change tracking
    description: str = ""
    changes: List[ChangeRecord] = field(default_factory=list)
    old_value: Optional[Dict[str, Any]] = None  # For simple changes
    new_value: Optional[Dict[str, Any]] = None  # For simple changes

    # Source tracking
    source: AuditSource = AuditSource.USER_INPUT
    confidence: Optional[float] = None  # 0.0-1.0 for OCR/AI extractions

    # Calculation context
    calculation_version: Optional[str] = None
    tax_year: Optional[int] = None

    # PII tracking (compliance requirement)
    pii_fields_accessed: List[str] = field(default_factory=list)
    pii_access_reason: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Result tracking
    success: bool = True
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    # Integrity verification
    signature_hash: Optional[str] = None
    previous_hash: Optional[str] = None  # For chain verification

    def __post_init__(self):
        """Generate signature hash after initialization."""
        # Auto-set severity from event type if not explicitly set
        if self.severity == AuditSeverity.INFO:
            self.severity = AuditSeverity.from_event_type(self.event_type)

        # Generate signature if not provided
        if not self.signature_hash:
            self.signature_hash = self._generate_signature()

    def _generate_signature(self) -> str:
        """Generate HMAC signature for integrity verification."""
        data = {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "return_id": self.return_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "changes": [c.to_dict() for c in self.changes],
            "old_value": self.old_value,
            "new_value": self.new_value,
            "previous_hash": self.previous_hash,
        }
        content = json.dumps(data, sort_keys=True, default=str)
        return hmac.new(
            _get_hmac_key(),
            content.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify the entry has not been tampered with."""
        expected = self._generate_signature()
        return hmac.compare_digest(self.signature_hash or "", expected)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "session_id": self.session_id,
            "return_id": self.return_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_role": self.user_role,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_path": self.request_path,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "changes": [c.to_dict() for c in self.changes],
            "old_value": self.old_value,
            "new_value": self.new_value,
            "source": self.source.value,
            "confidence": self.confidence,
            "calculation_version": self.calculation_version,
            "tax_year": self.tax_year,
            "pii_fields_accessed": self.pii_fields_accessed,
            "pii_access_reason": self.pii_access_reason,
            "metadata": self.metadata,
            "success": self.success,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "signature_hash": self.signature_hash,
            "previous_hash": self.previous_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedAuditEntry":
        """Create from dictionary."""
        changes = [
            ChangeRecord.from_dict(c)
            for c in data.get("changes", [])
        ]

        return cls(
            entry_id=data.get("entry_id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else data.get("timestamp", datetime.utcnow()),
            event_type=AuditEventType(data["event_type"]) if isinstance(data.get("event_type"), str) else data.get("event_type", AuditEventType.TAX_DATA_FIELD_CHANGE),
            severity=AuditSeverity(data["severity"]) if isinstance(data.get("severity"), str) else data.get("severity", AuditSeverity.INFO),
            session_id=data.get("session_id"),
            return_id=data.get("return_id"),
            tenant_id=data.get("tenant_id"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            user_role=data.get("user_role"),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            request_path=data.get("request_path"),
            action=data.get("action", ""),
            resource_type=data.get("resource_type", ""),
            resource_id=data.get("resource_id"),
            description=data.get("description", ""),
            changes=changes,
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            source=AuditSource(data["source"]) if isinstance(data.get("source"), str) else data.get("source", AuditSource.USER_INPUT),
            confidence=data.get("confidence"),
            calculation_version=data.get("calculation_version"),
            tax_year=data.get("tax_year"),
            pii_fields_accessed=data.get("pii_fields_accessed", []),
            pii_access_reason=data.get("pii_access_reason"),
            metadata=data.get("metadata", {}),
            success=data.get("success", True),
            error_message=data.get("error_message"),
            error_code=data.get("error_code"),
            signature_hash=data.get("signature_hash"),
            previous_hash=data.get("previous_hash"),
        )

    def get_summary(self) -> str:
        """Generate human-readable summary of the entry."""
        parts = [
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}]",
            f"{self.event_type.value}",
        ]

        if self.user_name:
            parts.append(f"by {self.user_name}")
        elif self.user_id:
            parts.append(f"by user:{self.user_id}")

        if self.description:
            parts.append(f"- {self.description}")
        elif self.action:
            parts.append(f"- {self.action}")

        if self.changes:
            parts.append(f"({len(self.changes)} changes)")

        return " ".join(parts)
