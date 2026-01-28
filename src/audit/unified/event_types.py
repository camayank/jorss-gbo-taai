"""
Unified Audit Event Types

Consolidates event types from audit_trail.py (32 types) and
audit_logger.py (70+ types) into a single hierarchical system.

Organization uses dotted notation for clarity:
- auth.* - Authentication events
- tenant.* - Tenant management
- user.* - User management
- tax.* - Tax return and data events
- document.* - Document operations
- security.* - Security events
- pii.* - PII access (compliance mandatory)
"""

from enum import Enum


class AuditEventType(str, Enum):
    """
    Comprehensive audit event types.

    Organized hierarchically by category.
    """

    # =========================================================================
    # AUTHENTICATION (auth.*)
    # =========================================================================
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED_LOGIN = "auth.failed_login"
    AUTH_TOKEN_REFRESH = "auth.token_refresh"
    AUTH_PASSWORD_CHANGE = "auth.password_change"
    AUTH_PASSWORD_RESET = "auth.password_reset"
    AUTH_MFA_ENABLED = "auth.mfa_enabled"
    AUTH_MFA_DISABLED = "auth.mfa_disabled"

    # =========================================================================
    # TENANT MANAGEMENT (tenant.*)
    # =========================================================================
    TENANT_CREATE = "tenant.create"
    TENANT_UPDATE = "tenant.update"
    TENANT_DELETE = "tenant.delete"
    TENANT_BRANDING_UPDATE = "tenant.branding_update"
    TENANT_FEATURES_UPDATE = "tenant.features_update"
    TENANT_STATUS_CHANGE = "tenant.status_change"

    # =========================================================================
    # USER MANAGEMENT (user.*)
    # =========================================================================
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role_change"
    USER_PERMISSIONS_CHANGE = "user.permissions_change"
    USER_ACCESS_GRANTED = "user.access_granted"
    USER_ACCESS_REVOKED = "user.access_revoked"

    # =========================================================================
    # CPA MANAGEMENT (cpa.*)
    # =========================================================================
    CPA_BRANDING_UPDATE = "cpa.branding_update"
    CPA_PROFILE_UPDATE = "cpa.profile_update"
    CPA_CLIENT_ASSIGN = "cpa.client_assign"
    CPA_CLIENT_UNASSIGN = "cpa.client_unassign"

    # =========================================================================
    # TAX RETURN LIFECYCLE (tax.return.*)
    # =========================================================================
    TAX_RETURN_CREATE = "tax.return.create"
    TAX_RETURN_OPEN = "tax.return.open"
    TAX_RETURN_SAVE = "tax.return.save"
    TAX_RETURN_CLOSE = "tax.return.close"
    TAX_RETURN_DELETE = "tax.return.delete"
    TAX_RETURN_ARCHIVE = "tax.return.archive"
    TAX_RETURN_SUBMIT = "tax.return.submit"
    TAX_RETURN_APPROVE = "tax.return.approve"
    TAX_RETURN_REJECT = "tax.return.reject"
    TAX_RETURN_EFILE = "tax.return.efile"
    TAX_RETURN_ACCEPTED = "tax.return.accepted"
    TAX_RETURN_REJECTED = "tax.return.rejected"
    TAX_RETURN_AMEND = "tax.return.amend"

    # =========================================================================
    # TAX DATA CHANGES (tax.data.*)
    # =========================================================================
    TAX_DATA_FIELD_CHANGE = "tax.data.field_change"
    TAX_DATA_INCOME_CHANGE = "tax.data.income_change"
    TAX_DATA_DEDUCTION_CHANGE = "tax.data.deduction_change"
    TAX_DATA_CREDIT_CHANGE = "tax.data.credit_change"
    TAX_DATA_IMPORT = "tax.data.import"
    TAX_DATA_EXPORT = "tax.data.export"
    TAX_DATA_OCR_EXTRACT = "tax.data.ocr_extract"
    TAX_DATA_AI_SUGGESTION = "tax.data.ai_suggestion"
    TAX_DATA_USER_OVERRIDE = "tax.data.user_override"
    TAX_DATA_BULK_UPDATE = "tax.data.bulk_update"

    # =========================================================================
    # TAX CALCULATIONS (tax.calc.*)
    # =========================================================================
    TAX_CALC_RUN = "tax.calc.run"
    TAX_CALC_VERIFIED = "tax.calc.verified"
    TAX_CALC_OVERRIDE = "tax.calc.override"
    TAX_CALC_SNAPSHOT = "tax.calc.snapshot"

    # =========================================================================
    # TAX FORMS (tax.form.*)
    # =========================================================================
    TAX_FORM_W2_IMPORT = "tax.form.w2_import"
    TAX_FORM_1099_IMPORT = "tax.form.1099_import"
    TAX_FORM_K1_IMPORT = "tax.form.k1_import"
    TAX_FORM_K1_BASIS_ADJUST = "tax.form.k1_basis_adjust"
    TAX_FORM_8949_ENTRY = "tax.form.8949_entry"
    TAX_FORM_DEPRECIATION = "tax.form.depreciation"

    # =========================================================================
    # TAX REVIEW (tax.review.*)
    # =========================================================================
    TAX_REVIEW_START = "tax.review.start"
    TAX_REVIEW_COMPLETE = "tax.review.complete"
    TAX_REVIEW_COMMENT = "tax.review.comment"
    TAX_SIGN_PREPARER = "tax.sign.preparer"
    TAX_SIGN_TAXPAYER = "tax.sign.taxpayer"
    TAX_SIGN_SPOUSE = "tax.sign.spouse"

    # =========================================================================
    # DOCUMENTS (document.*)
    # =========================================================================
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_VIEW = "document.view"
    DOCUMENT_DOWNLOAD = "document.download"
    DOCUMENT_DELETE = "document.delete"
    DOCUMENT_VERIFIED = "document.verified"

    # =========================================================================
    # PERMISSIONS (permission.*)
    # =========================================================================
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    PERMISSION_DENIED = "permission.denied"
    FEATURE_ACCESSED = "feature.accessed"
    FEATURE_DENIED = "feature.denied"

    # =========================================================================
    # SECURITY (security.*)
    # =========================================================================
    SECURITY_SUSPICIOUS = "security.suspicious"
    SECURITY_RATE_LIMIT = "security.rate_limit"
    SECURITY_VIOLATION = "security.violation"

    # =========================================================================
    # PII ACCESS - MANDATORY FOR COMPLIANCE (pii.*)
    # =========================================================================
    PII_ACCESS_READ = "pii.access.read"
    PII_ACCESS_DECRYPT = "pii.access.decrypt"
    PII_ACCESS_EXPORT = "pii.access.export"
    PII_MODIFICATION = "pii.modification"
    PII_DELETION = "pii.deletion"
    PII_UNENCRYPTED_DETECTED = "pii.unencrypted_detected"

    # =========================================================================
    # SYSTEM (system.*)
    # =========================================================================
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    SYSTEM_VALIDATION_ERROR = "system.validation_error"
    SYSTEM_SNAPSHOT_CREATE = "system.snapshot.create"
    SYSTEM_SNAPSHOT_VERIFY = "system.snapshot.verify"

    @classmethod
    def get_category(cls, event_type: "AuditEventType") -> str:
        """Get the category prefix for an event type."""
        return event_type.value.split(".")[0]

    @classmethod
    def is_pii_event(cls, event_type: "AuditEventType") -> bool:
        """Check if event type is PII-related (requires special handling)."""
        return event_type.value.startswith("pii.")

    @classmethod
    def is_security_event(cls, event_type: "AuditEventType") -> bool:
        """Check if event type is security-related."""
        return event_type.value.startswith("security.") or event_type == cls.AUTH_FAILED_LOGIN


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @classmethod
    def from_event_type(cls, event_type: AuditEventType) -> "AuditSeverity":
        """Get default severity for an event type."""
        # Critical events
        if event_type in (
            AuditEventType.PII_UNENCRYPTED_DETECTED,
            AuditEventType.SECURITY_VIOLATION,
        ):
            return cls.CRITICAL

        # Warning events
        if event_type in (
            AuditEventType.AUTH_FAILED_LOGIN,
            AuditEventType.PERMISSION_DENIED,
            AuditEventType.SECURITY_SUSPICIOUS,
            AuditEventType.SECURITY_RATE_LIMIT,
            AuditEventType.TAX_RETURN_REJECTED,
            AuditEventType.USER_PERMISSIONS_CHANGE,
        ):
            return cls.WARNING

        # Error events
        if event_type in (
            AuditEventType.SYSTEM_ERROR,
            AuditEventType.SYSTEM_VALIDATION_ERROR,
        ):
            return cls.ERROR

        return cls.INFO


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
    FORM_IMPORT = "form_import"
