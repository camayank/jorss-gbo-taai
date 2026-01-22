"""Audit Trail and Record Keeping Module.

Comprehensive audit functionality for:
- Change tracking and history
- Filing records and confirmations
- Document retention
- Calculation snapshots
- Compliance reporting
- Tax data change tracking (new)
"""

from audit.audit_trail import (
    AuditTrail,
    AuditEntry,
    AuditEventType,
    ChangeRecord,
)
from audit.filing_records import (
    FilingRecord,
    FilingStatus,
    FilingRecordManager,
    AmendmentRecord,
)
from audit.document_retention import (
    DocumentRecord,
    RetentionPolicy,
    DocumentRetentionManager,
)
from audit.calculation_snapshot import (
    CalculationSnapshot,
    SnapshotComparison,
    SnapshotManager,
)
from audit.compliance_reporter import (
    ComplianceReport,
    ComplianceReporter,
    AuditPackage,
)
from audit.audit_logger import (
    AuditLogger,
    AuditSeverity,
    AuditEvent,
    get_audit_logger,
    audit_tax_return_action,
    audit_document_access,
    audit_login,
)
from audit.audit_models import (
    AuditAction,
    AuditSource,
)
from audit.audit_storage import (
    SQLiteAuditStorage,
    InMemoryAuditStorage,
)

__all__ = [
    # Core audit trail
    "AuditTrail",
    "AuditEntry",
    "AuditEventType",
    "ChangeRecord",
    # Filing records
    "FilingRecord",
    "FilingStatus",
    "FilingRecordManager",
    "AmendmentRecord",
    # Document retention
    "DocumentRecord",
    "RetentionPolicy",
    "DocumentRetentionManager",
    # Calculation snapshots
    "CalculationSnapshot",
    "SnapshotComparison",
    "SnapshotManager",
    # Compliance reporting
    "ComplianceReport",
    "ComplianceReporter",
    "AuditPackage",
    # Audit logger
    "AuditLogger",
    "AuditSeverity",
    "AuditEvent",
    "get_audit_logger",
    "audit_tax_return_action",
    "audit_document_access",
    "audit_login",
    # Tax data audit
    "AuditAction",
    "AuditSource",
    "SQLiteAuditStorage",
    "InMemoryAuditStorage",
]
