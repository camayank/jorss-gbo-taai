"""
Audit Trail and Record Keeping Module.

Comprehensive audit functionality for:
- Change tracking and history
- Filing records and confirmations
- Document retention
- Calculation snapshots
- Compliance reporting
- Tax data change tracking

RECOMMENDED: Use the unified audit system for new code:

    from audit.unified import AuditService, AuditEventType

    audit = AuditService.get_instance()
    audit.log_tax_field_change(session_id, "wages", old_val, new_val)

The unified system consolidates all audit functionality into a single,
consistent interface with HMAC-based integrity verification.
"""

# =============================================================================
# UNIFIED AUDIT SYSTEM (RECOMMENDED)
# =============================================================================
from audit.unified import (
    # Event types
    AuditEventType as UnifiedEventType,
    AuditSeverity as UnifiedSeverity,
    AuditSource as UnifiedSource,
    # Entry model
    UnifiedAuditEntry,
    ChangeRecord as UnifiedChangeRecord,
    # Storage
    AuditStorage,
    SQLiteAuditStorage as UnifiedSQLiteStorage,
    InMemoryAuditStorage as UnifiedInMemoryStorage,
    # Service
    AuditService,
    get_audit_service,
)

# =============================================================================
# LEGACY IMPORTS (BACKWARDS COMPATIBILITY)
# =============================================================================
# These imports maintain compatibility with existing code.
# New code should use the unified system above.

from audit.audit_trail import (
    AuditTrail,
    AuditEntry,
    AuditEventType,  # Legacy enum (fewer event types)
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
    # Tax data audit convenience functions
    audit_tax_field_change,
    audit_income_change,
    audit_deduction_change,
    audit_form_import,
    audit_tax_calculation,
    audit_capital_gain,
    audit_k1_import,
    audit_k1_basis_adjustment,
    audit_depreciation,
    get_session_audit_trail,
    export_session_audit_report,
    # PII audit (compliance mandatory)
    audit_pii_access,
    audit_pii_unencrypted_detection,
    get_pii_access_report,
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
    # ==========================================================================
    # UNIFIED SYSTEM (RECOMMENDED FOR NEW CODE)
    # ==========================================================================
    "AuditService",
    "get_audit_service",
    "UnifiedAuditEntry",
    "UnifiedEventType",
    "UnifiedSeverity",
    "UnifiedSource",
    "UnifiedChangeRecord",
    "AuditStorage",
    "UnifiedSQLiteStorage",
    "UnifiedInMemoryStorage",

    # ==========================================================================
    # LEGACY: Core audit trail
    # ==========================================================================
    "AuditTrail",
    "AuditEntry",
    "AuditEventType",
    "ChangeRecord",

    # ==========================================================================
    # Filing records
    # ==========================================================================
    "FilingRecord",
    "FilingStatus",
    "FilingRecordManager",
    "AmendmentRecord",

    # ==========================================================================
    # Document retention
    # ==========================================================================
    "DocumentRecord",
    "RetentionPolicy",
    "DocumentRetentionManager",

    # ==========================================================================
    # Calculation snapshots
    # ==========================================================================
    "CalculationSnapshot",
    "SnapshotComparison",
    "SnapshotManager",

    # ==========================================================================
    # Compliance reporting
    # ==========================================================================
    "ComplianceReport",
    "ComplianceReporter",
    "AuditPackage",

    # ==========================================================================
    # LEGACY: Audit logger and convenience functions
    # ==========================================================================
    "AuditLogger",
    "AuditSeverity",
    "AuditEvent",
    "get_audit_logger",
    "audit_tax_return_action",
    "audit_document_access",
    "audit_login",
    # Tax data audit
    "audit_tax_field_change",
    "audit_income_change",
    "audit_deduction_change",
    "audit_form_import",
    "audit_tax_calculation",
    "audit_capital_gain",
    "audit_k1_import",
    "audit_k1_basis_adjustment",
    "audit_depreciation",
    "get_session_audit_trail",
    "export_session_audit_report",
    # PII audit
    "audit_pii_access",
    "audit_pii_unencrypted_detection",
    "get_pii_access_report",

    # ==========================================================================
    # LEGACY: Models and storage
    # ==========================================================================
    "AuditAction",
    "AuditSource",
    "SQLiteAuditStorage",
    "InMemoryAuditStorage",
]
