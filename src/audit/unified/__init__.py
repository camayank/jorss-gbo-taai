"""
Unified Audit System

Consolidated audit trail for the Jorss-Gbo tax platform.
Combines all audit functionality into a single coherent system.

Usage:
    from audit.unified import AuditService, AuditEventType, AuditSeverity

    # Get the audit service
    audit = AuditService.get_instance()

    # Log events
    audit.log_tax_field_change(session_id, "wages", old_value, new_value)
    audit.log_calculation(session_id, inputs, outputs)
    audit.log_pii_access(user_id, tenant_id, ["email", "ssn"], "export")
"""

from .event_types import AuditEventType, AuditSeverity, AuditSource
from .entry import UnifiedAuditEntry, ChangeRecord
from .storage import AuditStorage, SQLiteAuditStorage, InMemoryAuditStorage
from .service import AuditService, get_audit_service

__all__ = [
    # Event types
    "AuditEventType",
    "AuditSeverity",
    "AuditSource",
    # Entry model
    "UnifiedAuditEntry",
    "ChangeRecord",
    # Storage
    "AuditStorage",
    "SQLiteAuditStorage",
    "InMemoryAuditStorage",
    # Service
    "AuditService",
    "get_audit_service",
]
