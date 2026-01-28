"""
Unified Audit Service

Central service for all audit operations, consolidating functionality from:
- audit_logger.py (convenience functions)
- audit_trail.py (hash-verified trail)
- immutable_snapshot.py (cryptographic sealing)

Usage:
    from audit.unified import AuditService

    audit = AuditService.get_instance()
    audit.log_tax_field_change(session_id, "wages", 0, 50000)
    audit.log_calculation(session_id, inputs, outputs)
    audit.log_pii_access(user_id, tenant_id, ["email"], "export")
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .event_types import AuditEventType, AuditSeverity, AuditSource
from .entry import UnifiedAuditEntry, ChangeRecord
from .storage import AuditStorage, SQLiteAuditStorage, InMemoryAuditStorage

logger = logging.getLogger(__name__)


class AuditService:
    """
    Unified audit service for the tax platform.

    Provides:
    - Event logging with automatic chain linking
    - Convenience methods for common operations
    - PII access tracking (compliance requirement)
    - Query and reporting capabilities
    """

    _instance: Optional["AuditService"] = None

    def __init__(self, storage: Optional[AuditStorage] = None):
        """
        Initialize audit service.

        Args:
            storage: Storage backend (defaults to SQLiteAuditStorage)
        """
        self._storage = storage or SQLiteAuditStorage()
        self._current_context: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls, storage: Optional[AuditStorage] = None) -> "AuditService":
        """Get singleton instance of audit service."""
        if cls._instance is None:
            cls._instance = cls(storage)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    # =========================================================================
    # CONTEXT MANAGEMENT
    # =========================================================================

    def set_context(
        self,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        user_role: Optional[str] = None,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_path: Optional[str] = None,
    ) -> None:
        """Set context for subsequent audit entries."""
        if user_id is not None:
            self._current_context["user_id"] = user_id
        if user_name is not None:
            self._current_context["user_name"] = user_name
        if user_role is not None:
            self._current_context["user_role"] = user_role
        if tenant_id is not None:
            self._current_context["tenant_id"] = tenant_id
        if ip_address is not None:
            self._current_context["ip_address"] = ip_address
        if user_agent is not None:
            self._current_context["user_agent"] = user_agent
        if request_path is not None:
            self._current_context["request_path"] = request_path

    def clear_context(self) -> None:
        """Clear the current context."""
        self._current_context.clear()

    # =========================================================================
    # CORE LOGGING
    # =========================================================================

    def log(
        self,
        event_type: AuditEventType,
        action: str = "",
        resource_type: str = "",
        resource_id: Optional[str] = None,
        description: str = "",
        session_id: Optional[str] = None,
        return_id: Optional[str] = None,
        changes: Optional[List[ChangeRecord]] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        source: AuditSource = AuditSource.USER_INPUT,
        confidence: Optional[float] = None,
        pii_fields: Optional[List[str]] = None,
        pii_reason: Optional[str] = None,
        metadata: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        # Override context
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """
        Log an audit event.

        Returns: entry_id
        """
        # Get previous hash for chain linking
        previous_hash = None
        if session_id:
            previous_hash = self._storage.get_last_hash(session_id)

        # Build entry with context
        entry = UnifiedAuditEntry(
            event_type=event_type,
            severity=severity or AuditSeverity.from_event_type(event_type),
            session_id=session_id,
            return_id=return_id,
            tenant_id=tenant_id or self._current_context.get("tenant_id"),
            user_id=user_id or self._current_context.get("user_id"),
            user_name=self._current_context.get("user_name"),
            user_role=user_role or self._current_context.get("user_role"),
            ip_address=ip_address or self._current_context.get("ip_address"),
            user_agent=self._current_context.get("user_agent"),
            request_path=self._current_context.get("request_path"),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            changes=changes or [],
            old_value=old_value,
            new_value=new_value,
            source=source,
            confidence=confidence,
            pii_fields_accessed=pii_fields or [],
            pii_access_reason=pii_reason,
            metadata=metadata or {},
            success=success,
            error_message=error_message,
            previous_hash=previous_hash,
        )

        # Save to storage
        entry_id = self._storage.save(entry)

        # Log to standard logger for monitoring
        log_level = logging.WARNING if not success else logging.INFO
        if entry.severity == AuditSeverity.CRITICAL:
            log_level = logging.CRITICAL
        elif entry.severity == AuditSeverity.ERROR:
            log_level = logging.ERROR

        logger.log(
            log_level,
            f"AUDIT: {event_type.value} | {action} | "
            f"user={entry.user_id} | resource={resource_type}:{resource_id}"
        )

        return entry_id

    # =========================================================================
    # AUTHENTICATION EVENTS
    # =========================================================================

    def log_login(
        self,
        user_id: str,
        user_role: str,
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> str:
        """Log login attempt."""
        return self.log(
            event_type=AuditEventType.AUTH_LOGIN if success else AuditEventType.AUTH_FAILED_LOGIN,
            action="login",
            resource_type="auth",
            resource_id=user_id,
            user_id=user_id if success else None,
            user_role=user_role if success else None,
            ip_address=ip_address,
            success=success,
            error_message=error_message,
        )

    def log_logout(self, user_id: str) -> str:
        """Log user logout."""
        return self.log(
            event_type=AuditEventType.AUTH_LOGOUT,
            action="logout",
            resource_type="auth",
            resource_id=user_id,
            user_id=user_id,
        )

    # =========================================================================
    # TENANT EVENTS
    # =========================================================================

    def log_tenant_change(
        self,
        tenant_id: str,
        action: str,
        user_id: str,
        user_role: str,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        details: Optional[Dict] = None,
    ) -> str:
        """Log tenant configuration change."""
        return self.log(
            event_type=AuditEventType.TENANT_UPDATE,
            action=action,
            resource_type="tenant",
            resource_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            tenant_id=tenant_id,
            old_value=old_value,
            new_value=new_value,
            metadata=details,
        )

    # =========================================================================
    # USER/PERMISSION EVENTS
    # =========================================================================

    def log_permission_change(
        self,
        user_id: str,
        changed_by: str,
        role: str,
        action: str,
        old_permissions: Optional[List[str]] = None,
        new_permissions: Optional[List[str]] = None,
    ) -> str:
        """Log permission/role change."""
        return self.log(
            event_type=AuditEventType.USER_PERMISSIONS_CHANGE,
            action=action,
            resource_type="user_permissions",
            resource_id=user_id,
            user_id=changed_by,
            user_role=role,
            old_value={"permissions": old_permissions} if old_permissions else None,
            new_value={"permissions": new_permissions} if new_permissions else None,
            severity=AuditSeverity.WARNING,
        )

    def log_permission_denial(
        self,
        user_id: str,
        user_role: str,
        permission_code: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> str:
        """Log permission denial."""
        return self.log(
            event_type=AuditEventType.PERMISSION_DENIED,
            action="permission_check",
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            user_role=user_role,
            metadata={"permission_code": permission_code, "reason": reason},
            success=False,
            severity=AuditSeverity.WARNING,
        )

    # =========================================================================
    # TAX RETURN EVENTS
    # =========================================================================

    def log_tax_return_action(
        self,
        action: str,
        return_id: str,
        user_id: str,
        user_role: str,
        tenant_id: str,
        session_id: Optional[str] = None,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
    ) -> str:
        """Log tax return lifecycle action."""
        event_type_map = {
            "create": AuditEventType.TAX_RETURN_CREATE,
            "open": AuditEventType.TAX_RETURN_OPEN,
            "save": AuditEventType.TAX_RETURN_SAVE,
            "close": AuditEventType.TAX_RETURN_CLOSE,
            "submit": AuditEventType.TAX_RETURN_SUBMIT,
            "approve": AuditEventType.TAX_RETURN_APPROVE,
            "reject": AuditEventType.TAX_RETURN_REJECT,
            "efile": AuditEventType.TAX_RETURN_EFILE,
        }

        return self.log(
            event_type=event_type_map.get(action, AuditEventType.TAX_RETURN_SAVE),
            action=action,
            resource_type="tax_return",
            resource_id=return_id,
            session_id=session_id,
            return_id=return_id,
            user_id=user_id,
            user_role=user_role,
            tenant_id=tenant_id,
            old_value={"status": old_status} if old_status else None,
            new_value={"status": new_status} if new_status else None,
        )

    # =========================================================================
    # TAX DATA EVENTS
    # =========================================================================

    def log_tax_field_change(
        self,
        session_id: str,
        field_name: str,
        old_value: Any,
        new_value: Any,
        source: AuditSource = AuditSource.USER_INPUT,
        confidence: Optional[float] = None,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Log a change to a tax data field."""
        source_to_event = {
            AuditSource.USER_INPUT: AuditEventType.TAX_DATA_FIELD_CHANGE,
            AuditSource.OCR_EXTRACTION: AuditEventType.TAX_DATA_OCR_EXTRACT,
            AuditSource.AI_CHATBOT: AuditEventType.TAX_DATA_AI_SUGGESTION,
            AuditSource.CALCULATION_ENGINE: AuditEventType.TAX_CALC_RUN,
            AuditSource.MANUAL_OVERRIDE: AuditEventType.TAX_DATA_USER_OVERRIDE,
        }

        changes = [ChangeRecord(
            field_path=field_name,
            old_value=old_value,
            new_value=new_value,
            change_reason=reason,
        )]

        return self.log(
            event_type=source_to_event.get(source, AuditEventType.TAX_DATA_FIELD_CHANGE),
            action=f"change_{field_name}",
            resource_type="tax_data",
            resource_id=session_id,
            session_id=session_id,
            user_id=user_id,
            changes=changes,
            source=source,
            confidence=confidence,
            metadata={"field_name": field_name, "reason": reason},
        )

    def log_income_change(
        self,
        session_id: str,
        income_type: str,
        old_value: float,
        new_value: float,
        source: AuditSource = AuditSource.USER_INPUT,
        form_source: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Log income data change."""
        return self.log(
            event_type=AuditEventType.TAX_DATA_INCOME_CHANGE,
            action=f"change_{income_type}",
            resource_type="income",
            resource_id=session_id,
            session_id=session_id,
            user_id=user_id,
            old_value={"amount": old_value, "type": income_type},
            new_value={"amount": new_value, "type": income_type},
            source=source,
            metadata={
                "income_type": income_type,
                "form_source": form_source,
                "change_amount": new_value - old_value if old_value and new_value else None,
            },
        )

    def log_deduction_change(
        self,
        session_id: str,
        deduction_type: str,
        old_value: float,
        new_value: float,
        source: AuditSource = AuditSource.USER_INPUT,
        user_id: Optional[str] = None,
    ) -> str:
        """Log deduction data change."""
        return self.log(
            event_type=AuditEventType.TAX_DATA_DEDUCTION_CHANGE,
            action=f"change_{deduction_type}",
            resource_type="deduction",
            resource_id=session_id,
            session_id=session_id,
            user_id=user_id,
            old_value={"amount": old_value, "type": deduction_type},
            new_value={"amount": new_value, "type": deduction_type},
            source=source,
            metadata={"deduction_type": deduction_type},
        )

    def log_form_import(
        self,
        session_id: str,
        form_type: str,
        form_id: str,
        extracted_data: Dict,
        document_name: Optional[str] = None,
        ocr_confidence: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Log tax form import (W-2, 1099, K-1, etc.)."""
        form_to_event = {
            "W-2": AuditEventType.TAX_FORM_W2_IMPORT,
            "1099": AuditEventType.TAX_FORM_1099_IMPORT,
            "K-1": AuditEventType.TAX_FORM_K1_IMPORT,
        }

        return self.log(
            event_type=form_to_event.get(form_type, AuditEventType.TAX_DATA_IMPORT),
            action=f"import_{form_type}",
            resource_type=form_type.lower(),
            resource_id=form_id,
            session_id=session_id,
            user_id=user_id,
            new_value=extracted_data,
            source=AuditSource.FORM_IMPORT,
            confidence=ocr_confidence,
            metadata={
                "form_type": form_type,
                "document_name": document_name,
                "fields_extracted": len(extracted_data) if isinstance(extracted_data, dict) else None,
            },
        )

    def log_calculation(
        self,
        session_id: str,
        calculation_type: str,
        inputs: Dict,
        outputs: Dict,
        calculation_version: Optional[str] = None,
        user_id: Optional[str] = None,
        tax_year: Optional[int] = None,
    ) -> str:
        """Log tax calculation."""
        entry = UnifiedAuditEntry(
            event_type=AuditEventType.TAX_CALC_RUN,
            session_id=session_id,
            user_id=user_id or self._current_context.get("user_id"),
            tenant_id=self._current_context.get("tenant_id"),
            action=f"calculate_{calculation_type}",
            resource_type="calculation",
            resource_id=session_id,
            source=AuditSource.CALCULATION_ENGINE,
            calculation_version=calculation_version,
            tax_year=tax_year,
            old_value={"inputs": inputs},
            new_value={"outputs": outputs},
            metadata={"calculation_type": calculation_type},
            previous_hash=self._storage.get_last_hash(session_id),
        )

        return self._storage.save(entry)

    # =========================================================================
    # DOCUMENT EVENTS
    # =========================================================================

    def log_document_access(
        self,
        action: str,
        document_id: str,
        user_id: str,
        user_role: str,
        tenant_id: str,
        filename: Optional[str] = None,
    ) -> str:
        """Log document access (view/download/delete)."""
        event_type_map = {
            "upload": AuditEventType.DOCUMENT_UPLOAD,
            "view": AuditEventType.DOCUMENT_VIEW,
            "download": AuditEventType.DOCUMENT_DOWNLOAD,
            "delete": AuditEventType.DOCUMENT_DELETE,
        }

        return self.log(
            event_type=event_type_map.get(action, AuditEventType.DOCUMENT_VIEW),
            action=action,
            resource_type="document",
            resource_id=document_id,
            user_id=user_id,
            user_role=user_role,
            tenant_id=tenant_id,
            metadata={"filename": filename} if filename else None,
        )

    # =========================================================================
    # PII ACCESS - MANDATORY FOR COMPLIANCE
    # =========================================================================

    def log_pii_access(
        self,
        user_id: str,
        tenant_id: str,
        pii_fields: List[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        MANDATORY: Log PII field access.

        Must be called whenever PII fields are:
        - Read (decrypted for display)
        - Exported (included in reports/downloads)
        - Modified or deleted

        Required for GDPR/CCPA/SOC2 compliance.
        """
        event_type_map = {
            "read": AuditEventType.PII_ACCESS_READ,
            "decrypt": AuditEventType.PII_ACCESS_DECRYPT,
            "export": AuditEventType.PII_ACCESS_EXPORT,
            "modify": AuditEventType.PII_MODIFICATION,
            "delete": AuditEventType.PII_DELETION,
        }

        # SSN access is always high severity
        has_ssn = "ssn" in pii_fields or "social_security_number" in pii_fields
        severity = AuditSeverity.WARNING if has_ssn else AuditSeverity.INFO

        # SSN access requires a reason
        if has_ssn and not reason:
            logger.warning(
                f"[COMPLIANCE WARNING] SSN accessed without reason | "
                f"user={user_id} | resource={resource_type}:{resource_id}"
            )

        return self.log(
            event_type=event_type_map.get(action, AuditEventType.PII_ACCESS_READ),
            action=f"pii_{action}",
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            pii_fields=pii_fields,
            pii_reason=reason,
            severity=severity,
            metadata={"ssn_accessed": has_ssn},
        )

    def log_pii_violation(
        self,
        resource_type: str,
        resource_id: str,
        unencrypted_fields: List[str],
        tenant_id: Optional[str] = None,
    ) -> str:
        """
        CRITICAL: Log detection of unencrypted PII.

        Called when PII validation detects plaintext PII that should be encrypted.
        """
        logger.critical(
            f"[SECURITY VIOLATION] Unencrypted PII detected | "
            f"resource={resource_type}:{resource_id} | fields={unencrypted_fields}"
        )

        return self.log(
            event_type=AuditEventType.PII_UNENCRYPTED_DETECTED,
            action="unencrypted_pii_detected",
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tenant_id,
            pii_fields=unencrypted_fields,
            success=False,
            severity=AuditSeverity.CRITICAL,
            metadata={"violation_type": "plaintext_pii_storage"},
        )

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def get_session_trail(self, session_id: str, limit: int = 1000) -> List[UnifiedAuditEntry]:
        """Get complete audit trail for a session."""
        return self._storage.query(session_id=session_id, limit=limit)

    def get_user_activity(self, user_id: str, days: int = 30) -> List[UnifiedAuditEntry]:
        """Get recent activity for a user."""
        start_date = datetime.now() - timedelta(days=days)
        return self._storage.query(user_id=user_id, start_date=start_date)

    def get_tenant_activity(self, tenant_id: str, days: int = 30) -> List[UnifiedAuditEntry]:
        """Get recent activity for a tenant."""
        start_date = datetime.now() - timedelta(days=days)
        return self._storage.query(tenant_id=tenant_id, start_date=start_date)

    def get_failed_logins(self, hours: int = 24) -> List[UnifiedAuditEntry]:
        """Get recent failed login attempts."""
        start_date = datetime.now() - timedelta(hours=hours)
        return self._storage.query(
            event_type=AuditEventType.AUTH_FAILED_LOGIN,
            start_date=start_date,
            success_only=False,
        )

    def get_security_events(self, days: int = 7) -> List[UnifiedAuditEntry]:
        """Get recent security-related events."""
        start_date = datetime.now() - timedelta(days=days)
        return self._storage.query(
            severity=AuditSeverity.CRITICAL,
            start_date=start_date,
        )

    # =========================================================================
    # REPORTING
    # =========================================================================

    def get_session_audit_report(self, session_id: str) -> Dict:
        """Generate comprehensive audit report for a session."""
        entries = self.get_session_trail(session_id, limit=10000)

        # Categorize events
        income_changes = [e for e in entries if "income" in e.event_type.value]
        deduction_changes = [e for e in entries if "deduction" in e.event_type.value]
        calculations = [e for e in entries if "calc" in e.event_type.value]
        form_imports = [e for e in entries if "import" in e.event_type.value or "form" in e.event_type.value]
        user_overrides = [e for e in entries if "override" in e.event_type.value]

        return {
            "session_id": session_id,
            "total_events": len(entries),
            "summary": {
                "income_changes": len(income_changes),
                "deduction_changes": len(deduction_changes),
                "calculations": len(calculations),
                "form_imports": len(form_imports),
                "user_overrides": len(user_overrides),
            },
            "timeline": [e.to_dict() for e in entries],
            "first_event": entries[-1].to_dict() if entries else None,
            "last_event": entries[0].to_dict() if entries else None,
            "generated_at": datetime.now().isoformat(),
        }

    def get_pii_access_report(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict:
        """Generate PII access report for compliance review."""
        start_date = datetime.now() - timedelta(days=days)

        # Query all PII events
        pii_event_types = [
            AuditEventType.PII_ACCESS_READ,
            AuditEventType.PII_ACCESS_DECRYPT,
            AuditEventType.PII_ACCESS_EXPORT,
            AuditEventType.PII_MODIFICATION,
            AuditEventType.PII_DELETION,
            AuditEventType.PII_UNENCRYPTED_DETECTED,
        ]

        all_events = []
        for event_type in pii_event_types:
            events = self._storage.query(
                user_id=user_id,
                tenant_id=tenant_id,
                event_type=event_type,
                start_date=start_date,
                limit=10000,
            )
            all_events.extend(events)

        # Analyze
        ssn_accesses = [e for e in all_events if e.metadata.get("ssn_accessed")]
        violations = [e for e in all_events if e.event_type == AuditEventType.PII_UNENCRYPTED_DETECTED]
        unique_users = set(e.user_id for e in all_events if e.user_id)

        return {
            "period_start": start_date.isoformat(),
            "period_end": datetime.now().isoformat(),
            "total_pii_accesses": len(all_events),
            "ssn_accesses": len(ssn_accesses),
            "security_violations": len(violations),
            "unique_users": len(unique_users),
            "users": list(unique_users),
            "events_by_type": {
                "read": len([e for e in all_events if "read" in e.event_type.value]),
                "decrypt": len([e for e in all_events if "decrypt" in e.event_type.value]),
                "export": len([e for e in all_events if "export" in e.event_type.value]),
                "modify": len([e for e in all_events if "modification" in e.event_type.value]),
                "delete": len([e for e in all_events if "deletion" in e.event_type.value]),
            },
            "violations_detail": [e.to_dict() for e in violations],
            "generated_at": datetime.now().isoformat(),
        }

    def verify_session_integrity(self, session_id: str) -> tuple[bool, List[str]]:
        """Verify integrity of audit trail for a session."""
        if isinstance(self._storage, SQLiteAuditStorage):
            return self._storage.verify_chain_integrity(session_id)

        # For in-memory storage, verify entries individually
        entries = self.get_session_trail(session_id)
        issues = []

        for entry in entries:
            if not entry.verify_integrity():
                issues.append(f"Entry {entry.entry_id}: Integrity check failed")

        return len(issues) == 0, issues


# Global service accessor
_audit_service: Optional[AuditService] = None


def get_audit_service(db_path: Optional[str] = None) -> AuditService:
    """Get the global audit service instance."""
    global _audit_service

    if _audit_service is None:
        storage = SQLiteAuditStorage(db_path) if db_path else SQLiteAuditStorage()
        _audit_service = AuditService(storage)

    return _audit_service
