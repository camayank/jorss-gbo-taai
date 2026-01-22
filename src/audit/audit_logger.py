"""
Audit Logging System

Comprehensive audit trail for security and compliance.
Logs all sensitive actions with full context.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from enum import Enum
from dataclasses import dataclass


class AuditEventType(Enum):
    """Types of events that get audited"""

    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED_LOGIN = "auth.failed_login"
    AUTH_TOKEN_REFRESH = "auth.token_refresh"

    # Tenant Management
    TENANT_CREATE = "tenant.create"
    TENANT_UPDATE = "tenant.update"
    TENANT_DELETE = "tenant.delete"
    TENANT_BRANDING_UPDATE = "tenant.branding_update"
    TENANT_FEATURES_UPDATE = "tenant.features_update"
    TENANT_STATUS_CHANGE = "tenant.status_change"

    # User Management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role_change"
    USER_PERMISSIONS_CHANGE = "user.permissions_change"

    # CPA Branding
    CPA_BRANDING_UPDATE = "cpa.branding_update"
    CPA_PROFILE_UPDATE = "cpa.profile_update"

    # Tax Returns
    TAX_RETURN_CREATE = "tax_return.create"
    TAX_RETURN_UPDATE = "tax_return.update"
    TAX_RETURN_DELETE = "tax_return.delete"
    TAX_RETURN_SUBMIT = "tax_return.submit"
    TAX_RETURN_APPROVE = "tax_return.approve"
    TAX_RETURN_REJECT = "tax_return.reject"
    TAX_RETURN_EFILE = "tax_return.efile"

    # Tax Data Changes (for detailed field-level tracking)
    TAX_DATA_FIELD_CHANGE = "tax_data.field_change"
    TAX_DATA_INCOME_CHANGE = "tax_data.income_change"
    TAX_DATA_DEDUCTION_CHANGE = "tax_data.deduction_change"
    TAX_DATA_CREDIT_CHANGE = "tax_data.credit_change"
    TAX_DATA_FORM_IMPORT = "tax_data.form_import"
    TAX_DATA_OCR_EXTRACT = "tax_data.ocr_extract"
    TAX_DATA_AI_SUGGESTION = "tax_data.ai_suggestion"
    TAX_DATA_USER_OVERRIDE = "tax_data.user_override"
    TAX_DATA_CALCULATION = "tax_data.calculation"
    TAX_DATA_VALIDATION = "tax_data.validation"

    # Capital Gains (Form 8949)
    TAX_CAPITAL_GAIN_ADD = "tax_data.capital_gain_add"
    TAX_CAPITAL_GAIN_UPDATE = "tax_data.capital_gain_update"
    TAX_CAPITAL_GAIN_DELETE = "tax_data.capital_gain_delete"

    # K-1 Tracking
    TAX_K1_IMPORT = "tax_data.k1_import"
    TAX_K1_BASIS_ADJUST = "tax_data.k1_basis_adjust"

    # Depreciation
    TAX_DEPRECIATION_ADD = "tax_data.depreciation_add"
    TAX_DEPRECIATION_CALCULATE = "tax_data.depreciation_calculate"

    # Documents
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_VIEW = "document.view"
    DOCUMENT_DELETE = "document.delete"
    DOCUMENT_DOWNLOAD = "document.download"

    # Client Management
    CLIENT_CREATE = "client.create"
    CLIENT_ASSIGN = "client.assign"
    CLIENT_UNASSIGN = "client.unassign"

    # Feature Access
    FEATURE_ACCESSED = "feature.accessed"
    FEATURE_DENIED = "feature.denied"

    # Permission Changes
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    PERMISSION_DENIED = "permission.denied"

    # Data Access
    DATA_EXPORT = "data.export"
    DATA_IMPORT = "data.import"

    # Security
    SECURITY_SUSPICIOUS_ACTIVITY = "security.suspicious"
    SECURITY_RATE_LIMIT_EXCEEDED = "security.rate_limit"


class AuditSeverity(Enum):
    """Severity levels for audit events"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event record"""
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: datetime

    # Who performed the action
    user_id: Optional[str]
    user_role: Optional[str]
    tenant_id: Optional[str]

    # What was the action
    action: str
    resource_type: str
    resource_id: Optional[str]

    # Context
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_path: Optional[str]

    # Details
    details: Dict[str, Any]
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None

    # Result
    success: bool = True
    error_message: Optional[str] = None


class AuditLogger:
    """
    Audit logging system with database persistence.

    Logs all sensitive operations for security and compliance.
    """

    def __init__(self, db_path: str = "./data/audit_log.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _initialize_schema(self):
        """Create audit log table"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    timestamp TEXT NOT NULL,

                    user_id TEXT,
                    user_role TEXT,
                    tenant_id TEXT,

                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,

                    ip_address TEXT,
                    user_agent TEXT,
                    request_path TEXT,

                    details JSON,
                    old_value JSON,
                    new_value JSON,

                    success INTEGER NOT NULL,
                    error_message TEXT
                )
            """)

            # Indexes for querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_log(tenant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id)")

            conn.commit()

    def log(
        self,
        event_type: AuditEventType,
        action: str,
        resource_type: str,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_path: Optional[str] = None,
    ) -> str:
        """
        Log an audit event.

        Returns: event_id
        """
        import uuid

        event_id = str(uuid.uuid4())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO audit_log (
                    event_id, event_type, severity, timestamp,
                    user_id, user_role, tenant_id,
                    action, resource_type, resource_id,
                    ip_address, user_agent, request_path,
                    details, old_value, new_value,
                    success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                event_type.value,
                severity.value,
                datetime.now().isoformat(),
                user_id,
                user_role,
                tenant_id,
                action,
                resource_type,
                resource_id,
                ip_address,
                user_agent,
                request_path,
                json.dumps(details) if details else None,
                json.dumps(old_value) if old_value else None,
                json.dumps(new_value) if new_value else None,
                1 if success else 0,
                error_message
            ))

            conn.commit()

        return event_id

    def query(
        self,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Query audit log with filters"""

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM audit_log WHERE 1=1"
            params = []

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)

            if tenant_id:
                query += " AND tenant_id = ?"
                params.append(tenant_id)

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)

            if resource_type:
                query += " AND resource_type = ?"
                params.append(resource_type)

            if resource_id:
                query += " AND resource_id = ?"
                params.append(resource_id)

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            if severity:
                query += " AND severity = ?"
                params.append(severity.value)

            if success_only is not None:
                query += " AND success = ?"
                params.append(1 if success_only else 0)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            columns = [col[0] for col in cursor.description]

            results = []
            for row in rows:
                record = dict(zip(columns, row))

                # Parse JSON fields
                if record['details']:
                    record['details'] = json.loads(record['details'])
                if record['old_value']:
                    record['old_value'] = json.loads(record['old_value'])
                if record['new_value']:
                    record['new_value'] = json.loads(record['new_value'])

                record['success'] = bool(record['success'])

                results.append(record)

            return results

    def get_user_activity(self, user_id: str, days: int = 30) -> List[Dict]:
        """Get recent activity for a user"""
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)

        return self.query(user_id=user_id, start_date=start_date)

    def get_tenant_activity(self, tenant_id: str, days: int = 30) -> List[Dict]:
        """Get recent activity for a tenant"""
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)

        return self.query(tenant_id=tenant_id, start_date=start_date)

    def get_failed_logins(self, hours: int = 24) -> List[Dict]:
        """Get recent failed login attempts"""
        from datetime import timedelta

        start_date = datetime.now() - timedelta(hours=hours)

        return self.query(
            event_type=AuditEventType.AUTH_FAILED_LOGIN,
            start_date=start_date,
            success_only=False
        )

    def get_security_events(self, days: int = 7) -> List[Dict]:
        """Get recent security-related events"""
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)

        return self.query(
            severity=AuditSeverity.CRITICAL,
            start_date=start_date
        )

    def get_permission_denials(self, user_id: str = None, days: int = 7) -> List[Dict]:
        """Get permission denial events"""
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)

        return self.query(
            user_id=user_id,
            event_type=AuditEventType.PERMISSION_DENIED,
            start_date=start_date
        )


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(db_path: str = "./data/audit_log.db") -> AuditLogger:
    """Get global audit logger instance"""
    global _audit_logger

    if _audit_logger is None:
        _audit_logger = AuditLogger(db_path)

    return _audit_logger


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def audit_tenant_change(
    tenant_id: str,
    action: str,
    user_id: str,
    user_role: str,
    old_value: Dict = None,
    new_value: Dict = None,
    details: Dict = None
):
    """Audit tenant configuration change"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.TENANT_UPDATE,
        action=action,
        resource_type="tenant",
        resource_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
        tenant_id=tenant_id,
        old_value=old_value,
        new_value=new_value,
        details=details,
        severity=AuditSeverity.INFO
    )


def audit_permission_change(
    user_id: str,
    changed_by: str,
    role: str,
    action: str,
    old_permissions: List[str] = None,
    new_permissions: List[str] = None
):
    """Audit permission/role change"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.USER_PERMISSIONS_CHANGE,
        action=action,
        resource_type="user_permissions",
        resource_id=user_id,
        user_id=changed_by,
        user_role=role,
        old_value={'permissions': old_permissions} if old_permissions else None,
        new_value={'permissions': new_permissions} if new_permissions else None,
        severity=AuditSeverity.WARNING
    )


def audit_permission_denial(
    user_id: str,
    user_role: str,
    permission_code: str,
    resource_type: str,
    resource_id: str = None,
    reason: str = None
):
    """Audit permission denial (important for security)"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.PERMISSION_DENIED,
        action="permission_check",
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        user_role=user_role,
        details={
            'permission_code': permission_code,
            'reason': reason
        },
        success=False,
        severity=AuditSeverity.WARNING
    )


def audit_tax_return_action(
    action: str,
    return_id: str,
    user_id: str,
    user_role: str,
    tenant_id: str,
    old_status: str = None,
    new_status: str = None
):
    """Audit tax return actions"""
    logger = get_audit_logger()

    event_type_map = {
        'create': AuditEventType.TAX_RETURN_CREATE,
        'update': AuditEventType.TAX_RETURN_UPDATE,
        'submit': AuditEventType.TAX_RETURN_SUBMIT,
        'approve': AuditEventType.TAX_RETURN_APPROVE,
        'reject': AuditEventType.TAX_RETURN_REJECT,
        'efile': AuditEventType.TAX_RETURN_EFILE,
    }

    logger.log(
        event_type=event_type_map.get(action, AuditEventType.TAX_RETURN_UPDATE),
        action=action,
        resource_type="tax_return",
        resource_id=return_id,
        user_id=user_id,
        user_role=user_role,
        tenant_id=tenant_id,
        old_value={'status': old_status} if old_status else None,
        new_value={'status': new_status} if new_status else None,
        severity=AuditSeverity.INFO
    )


def audit_document_access(
    action: str,
    document_id: str,
    user_id: str,
    user_role: str,
    tenant_id: str,
    filename: str = None
):
    """Audit document access (view/download/delete)"""
    logger = get_audit_logger()

    event_type_map = {
        'upload': AuditEventType.DOCUMENT_UPLOAD,
        'view': AuditEventType.DOCUMENT_VIEW,
        'download': AuditEventType.DOCUMENT_DOWNLOAD,
        'delete': AuditEventType.DOCUMENT_DELETE,
    }

    logger.log(
        event_type=event_type_map.get(action, AuditEventType.DOCUMENT_VIEW),
        action=action,
        resource_type="document",
        resource_id=document_id,
        user_id=user_id,
        user_role=user_role,
        tenant_id=tenant_id,
        details={'filename': filename} if filename else None,
        severity=AuditSeverity.INFO
    )


def audit_login(
    user_id: str,
    user_role: str,
    success: bool,
    ip_address: str = None,
    user_agent: str = None,
    error_message: str = None
):
    """Audit login attempt"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.AUTH_LOGIN if success else AuditEventType.AUTH_FAILED_LOGIN,
        action="login",
        resource_type="auth",
        resource_id=user_id,
        user_id=user_id if success else None,
        user_role=user_role if success else None,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        error_message=error_message,
        severity=AuditSeverity.INFO if success else AuditSeverity.WARNING
    )


# =============================================================================
# TAX DATA AUDIT FUNCTIONS
# =============================================================================

def audit_tax_field_change(
    session_id: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    source: str = "user_input",
    confidence: float = None,
    reason: str = None,
    user_id: str = None
):
    """
    Audit a change to a tax data field.

    Args:
        session_id: Tax filing session ID
        field_name: Name of the field changed (e.g., "wages", "business_income")
        old_value: Previous value
        new_value: New value
        source: Source of change ("user_input", "ocr_extraction", "ai_chatbot", "calculation")
        confidence: Confidence score for OCR/AI extractions (0.0-1.0)
        reason: Explanation for the change
        user_id: User who made the change
    """
    logger = get_audit_logger()

    # Map source to event type
    event_type_map = {
        "user_input": AuditEventType.TAX_DATA_FIELD_CHANGE,
        "ocr_extraction": AuditEventType.TAX_DATA_OCR_EXTRACT,
        "ai_chatbot": AuditEventType.TAX_DATA_AI_SUGGESTION,
        "calculation": AuditEventType.TAX_DATA_CALCULATION,
        "manual_override": AuditEventType.TAX_DATA_USER_OVERRIDE,
    }

    logger.log(
        event_type=event_type_map.get(source, AuditEventType.TAX_DATA_FIELD_CHANGE),
        action=f"change_{field_name}",
        resource_type="tax_data",
        resource_id=session_id,
        user_id=user_id,
        old_value={field_name: old_value},
        new_value={field_name: new_value},
        details={
            "field_name": field_name,
            "source": source,
            "confidence": confidence,
            "reason": reason,
        },
        severity=AuditSeverity.INFO
    )


def audit_income_change(
    session_id: str,
    income_type: str,
    old_value: float,
    new_value: float,
    source: str = "user_input",
    form_source: str = None,
    user_id: str = None
):
    """Audit a change to income data (wages, business, investment, etc.)"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.TAX_DATA_INCOME_CHANGE,
        action=f"change_{income_type}",
        resource_type="income",
        resource_id=session_id,
        user_id=user_id,
        old_value={"amount": old_value, "type": income_type},
        new_value={"amount": new_value, "type": income_type},
        details={
            "income_type": income_type,
            "source": source,
            "form_source": form_source,
            "change_amount": new_value - old_value if old_value and new_value else None,
        },
        severity=AuditSeverity.INFO
    )


def audit_deduction_change(
    session_id: str,
    deduction_type: str,
    old_value: float,
    new_value: float,
    source: str = "user_input",
    user_id: str = None
):
    """Audit a change to deduction data"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.TAX_DATA_DEDUCTION_CHANGE,
        action=f"change_{deduction_type}",
        resource_type="deduction",
        resource_id=session_id,
        user_id=user_id,
        old_value={"amount": old_value, "type": deduction_type},
        new_value={"amount": new_value, "type": deduction_type},
        details={
            "deduction_type": deduction_type,
            "source": source,
        },
        severity=AuditSeverity.INFO
    )


def audit_form_import(
    session_id: str,
    form_type: str,
    form_id: str,
    extracted_data: Dict,
    document_name: str = None,
    ocr_confidence: float = None,
    user_id: str = None
):
    """Audit import of a tax form (W-2, 1099, K-1, etc.)"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.TAX_DATA_FORM_IMPORT,
        action=f"import_{form_type}",
        resource_type=form_type,
        resource_id=form_id,
        user_id=user_id,
        new_value=extracted_data,
        details={
            "form_type": form_type,
            "document_name": document_name,
            "ocr_confidence": ocr_confidence,
            "fields_extracted": len(extracted_data) if isinstance(extracted_data, dict) else None,
        },
        severity=AuditSeverity.INFO
    )


def audit_tax_calculation(
    session_id: str,
    calculation_type: str,
    inputs: Dict,
    result: Any,
    calculation_version: str = None,
    user_id: str = None
):
    """Audit a tax calculation (tax liability, refund, credits, etc.)"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.TAX_DATA_CALCULATION,
        action=f"calculate_{calculation_type}",
        resource_type="calculation",
        resource_id=session_id,
        user_id=user_id,
        old_value=inputs,
        new_value={"result": result, "type": calculation_type},
        details={
            "calculation_type": calculation_type,
            "calculation_version": calculation_version,
        },
        severity=AuditSeverity.INFO
    )


def audit_capital_gain(
    session_id: str,
    action: str,
    transaction_id: str,
    transaction_data: Dict,
    old_data: Dict = None,
    user_id: str = None
):
    """Audit capital gains transaction (Form 8949)"""
    logger = get_audit_logger()

    event_type_map = {
        "add": AuditEventType.TAX_CAPITAL_GAIN_ADD,
        "update": AuditEventType.TAX_CAPITAL_GAIN_UPDATE,
        "delete": AuditEventType.TAX_CAPITAL_GAIN_DELETE,
    }

    logger.log(
        event_type=event_type_map.get(action, AuditEventType.TAX_CAPITAL_GAIN_UPDATE),
        action=f"capital_gain_{action}",
        resource_type="capital_gain",
        resource_id=transaction_id,
        user_id=user_id,
        old_value=old_data,
        new_value=transaction_data,
        details={
            "session_id": session_id,
            "holding_period": transaction_data.get("holding_period"),
            "gain_loss": transaction_data.get("gain_loss"),
        },
        severity=AuditSeverity.INFO
    )


def audit_k1_import(
    session_id: str,
    k1_id: str,
    k1_data: Dict,
    entity_name: str = None,
    entity_ein: str = None,
    user_id: str = None
):
    """Audit K-1 import with basis tracking"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.TAX_K1_IMPORT,
        action="import_k1",
        resource_type="k1",
        resource_id=k1_id,
        user_id=user_id,
        new_value=k1_data,
        details={
            "session_id": session_id,
            "entity_name": entity_name,
            "entity_ein": entity_ein,
            "ordinary_income": k1_data.get("ordinary_income"),
            "distributions": k1_data.get("distributions"),
        },
        severity=AuditSeverity.INFO
    )


def audit_k1_basis_adjustment(
    session_id: str,
    k1_id: str,
    adjustment_type: str,
    old_basis: float,
    new_basis: float,
    reason: str = None,
    user_id: str = None
):
    """Audit K-1 basis adjustments"""
    logger = get_audit_logger()

    logger.log(
        event_type=AuditEventType.TAX_K1_BASIS_ADJUST,
        action=f"k1_basis_{adjustment_type}",
        resource_type="k1_basis",
        resource_id=k1_id,
        user_id=user_id,
        old_value={"basis": old_basis},
        new_value={"basis": new_basis},
        details={
            "session_id": session_id,
            "adjustment_type": adjustment_type,
            "adjustment_amount": new_basis - old_basis,
            "reason": reason,
        },
        severity=AuditSeverity.INFO
    )


def audit_depreciation(
    session_id: str,
    asset_id: str,
    action: str,
    asset_data: Dict,
    depreciation_amount: float = None,
    user_id: str = None
):
    """Audit depreciation entries (rental property, business assets)"""
    logger = get_audit_logger()

    event_type = AuditEventType.TAX_DEPRECIATION_ADD if action == "add" else AuditEventType.TAX_DEPRECIATION_CALCULATE

    logger.log(
        event_type=event_type,
        action=f"depreciation_{action}",
        resource_type="depreciation",
        resource_id=asset_id,
        user_id=user_id,
        new_value=asset_data,
        details={
            "session_id": session_id,
            "asset_type": asset_data.get("asset_type"),
            "depreciation_method": asset_data.get("method"),
            "depreciation_amount": depreciation_amount,
            "useful_life": asset_data.get("useful_life"),
        },
        severity=AuditSeverity.INFO
    )


def get_session_audit_trail(session_id: str) -> List[Dict]:
    """
    Get complete audit trail for a tax filing session.

    Returns all audit events related to the session, sorted chronologically.
    """
    logger = get_audit_logger()

    return logger.query(
        resource_id=session_id,
        limit=1000
    )


def export_session_audit_report(session_id: str) -> Dict:
    """
    Export a comprehensive audit report for a session.

    Returns a structured report suitable for compliance review.
    """
    logger = get_audit_logger()

    events = logger.query(resource_id=session_id, limit=10000)

    # Categorize events
    income_changes = [e for e in events if e.get("event_type", "").startswith("tax_data.income")]
    deduction_changes = [e for e in events if e.get("event_type", "").startswith("tax_data.deduction")]
    calculations = [e for e in events if "calculation" in e.get("event_type", "")]
    form_imports = [e for e in events if "import" in e.get("event_type", "")]
    user_overrides = [e for e in events if "override" in e.get("event_type", "")]

    return {
        "session_id": session_id,
        "total_events": len(events),
        "summary": {
            "income_changes": len(income_changes),
            "deduction_changes": len(deduction_changes),
            "calculations": len(calculations),
            "form_imports": len(form_imports),
            "user_overrides": len(user_overrides),
        },
        "timeline": events,
        "first_event": events[-1] if events else None,
        "last_event": events[0] if events else None,
        "generated_at": datetime.now().isoformat(),
    }
