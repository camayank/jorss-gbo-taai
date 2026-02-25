"""
Audit Trail Data Models

Defines the core data structures for audit logging including
audit entries, action types, and data sources.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class AuditAction(str, Enum):
    """Types of auditable actions in the system."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CALCULATE = "calculate"
    EXTRACT = "extract"
    REVIEW = "review"
    APPROVE = "approve"
    SUBMIT = "submit"
    IMPORT = "import"
    EXPORT = "export"
    LOGIN = "login"
    LOGOUT = "logout"
    VIEW = "view"
    DOWNLOAD = "download"
    UPLOAD = "upload"


class AuditSource(str, Enum):
    """Source of the data change or action."""
    USER_INPUT = "user_input"
    OCR_EXTRACTION = "ocr_extraction"
    AI_CHATBOT = "ai_chatbot"
    CALCULATION_ENGINE = "calculation_engine"
    SYSTEM_AUTO = "system_auto"
    API_IMPORT = "api_import"
    MANUAL_OVERRIDE = "manual_override"
    PRIOR_YEAR_IMPORT = "prior_year_import"
    THIRD_PARTY_SYNC = "third_party_sync"


@dataclass
class AuditEntry:
    """
    Represents a single audit log entry.

    Captures comprehensive information about every data change,
    calculation, or user action in the system.
    """
    # Core identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Action details
    action: AuditAction = AuditAction.UPDATE
    entity_type: str = ""  # e.g., "income", "deduction", "form_w2", "tax_calculation"
    entity_id: Optional[str] = None
    field_name: Optional[str] = None  # Specific field changed

    # Value tracking
    old_value: Any = None
    new_value: Any = None

    # Source and context
    source: AuditSource = AuditSource.USER_INPUT
    confidence: Optional[float] = None  # For OCR/AI extractions
    reason: Optional[str] = None  # Explanation for change

    # User context
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Calculation context (for tax calculations)
    calculation_version: Optional[str] = None
    tax_year: Optional[int] = None

    # Metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert audit entry to dictionary for storage/serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "field_name": self.field_name,
            "old_value": self._serialize_value(self.old_value),
            "new_value": self._serialize_value(self.new_value),
            "source": self.source.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "calculation_version": self.calculation_version,
            "tax_year": self.tax_year,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEntry":
        """Create audit entry from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            session_id=data.get("session_id", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else data.get("timestamp", datetime.utcnow()),
            action=AuditAction(data["action"]) if isinstance(data.get("action"), str) else data.get("action", AuditAction.UPDATE),
            entity_type=data.get("entity_type", ""),
            entity_id=data.get("entity_id"),
            field_name=data.get("field_name"),
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            source=AuditSource(data["source"]) if isinstance(data.get("source"), str) else data.get("source", AuditSource.USER_INPUT),
            confidence=data.get("confidence"),
            reason=data.get("reason"),
            user_id=data.get("user_id"),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            calculation_version=data.get("calculation_version"),
            tax_year=data.get("tax_year"),
            metadata=data.get("metadata", {})
        )

    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for storage."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        # For complex objects, convert to string representation
        return str(value)

    def get_change_summary(self) -> str:
        """Generate human-readable summary of the change."""
        action_verb = {
            AuditAction.CREATE: "Created",
            AuditAction.UPDATE: "Updated",
            AuditAction.DELETE: "Deleted",
            AuditAction.CALCULATE: "Calculated",
            AuditAction.EXTRACT: "Extracted",
            AuditAction.REVIEW: "Reviewed",
            AuditAction.APPROVE: "Approved",
            AuditAction.SUBMIT: "Submitted",
            AuditAction.IMPORT: "Imported",
            AuditAction.EXPORT: "Exported"
        }.get(self.action, str(self.action.value).capitalize())

        field_info = f".{self.field_name}" if self.field_name else ""
        value_info = ""

        if self.old_value is not None and self.new_value is not None:
            value_info = f": {self.old_value} → {self.new_value}"
        elif self.new_value is not None:
            value_info = f": {self.new_value}"

        source_info = f" (via {self.source.value.replace('_', ' ')})"

        return f"{action_verb} {self.entity_type}{field_info}{value_info}{source_info}"


@dataclass
class AIResponseAuditEvent:
    """
    Audit event for AI advisory responses.

    Captures comprehensive information about AI-generated advice
    for compliance and debugging purposes.
    """
    # Core identification
    session_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None

    # AI tracking
    model_version: str = ""
    prompt_hash: str = ""
    response_type: str = ""  # greeting, question, calculation, strategy

    # Confidence tracking
    profile_completeness: float = 0.0
    response_confidence: str = "high"  # high, medium, low
    confidence_reason: Optional[str] = None

    # Input/output tracking
    user_message: str = ""
    extracted_fields: dict = field(default_factory=dict)
    calculation_inputs: Optional[dict] = None
    response_summary: str = ""
    citations_included: list = field(default_factory=list)
    warnings_triggered: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert audit event to dictionary for storage/serialization."""
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "model_version": self.model_version,
            "prompt_hash": self.prompt_hash,
            "response_type": self.response_type,
            "profile_completeness": self.profile_completeness,
            "response_confidence": self.response_confidence,
            "confidence_reason": self.confidence_reason,
            "user_message": self.user_message,
            "extracted_fields": self.extracted_fields,
            "calculation_inputs": self.calculation_inputs,
            "response_summary": self.response_summary,
            "citations_included": self.citations_included,
            "warnings_triggered": self.warnings_triggered
        }
