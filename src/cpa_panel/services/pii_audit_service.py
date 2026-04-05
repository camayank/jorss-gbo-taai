"""
PII Audit Logging Service

Logs all SSN/PII access for compliance audit trail.
Records: user, role, timestamp, field accessed, last 4 digits, operation type.

GDPR + IRS Publication 4600 compliance.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import AuditLogRecord
from cpa_panel.security.pii_masking import AccessAuditEntry

logger = logging.getLogger(__name__)


class PIIAuditService:
    """
    Logs PII access events to database for compliance audit trail.

    SECURITY:
    - Records user ID, role, timestamp, field type, last 4 digits
    - Never stores full SSN in audit log
    - Immutable: audit logs cannot be modified or deleted
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize audit service with optional database session.

        Args:
            session: SQLAlchemy session (optional)
        """
        self.session = session

    def log_pii_access(
        self,
        entry: AccessAuditEntry,
        firm_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[str]:
        """
        Log PII access event to audit trail.

        Args:
            entry: AccessAuditEntry with access details
            firm_id: Firm ID for multi-tenancy (optional)
            ip_address: IP address of requester (optional)
            user_agent: User agent string (optional)

        Returns:
            Log ID if successful, None if logging failed
        """
        if not self.session:
            logger.warning("No database session available - audit log not recorded")
            return None

        try:
            log_record = AuditLogRecord(
                log_id=uuid4(),
                firm_id=firm_id,
                return_id=None,  # PII audit logs are not specific to returns
                event_type="PII_ACCESS",
                event_category="COMPLIANCE",
                severity="info",
                timestamp=entry.timestamp,
                user_id=entry.user_id,
                user_role=entry.user_role,
                ip_address=ip_address,
                user_agent=user_agent,
                field_name=entry.field_type,
                change_type="READ",
                change_details={
                    "operation": entry.operation,
                    "resource_type": entry.resource_type,
                    "last_4_digits": entry.full_value_last4,
                    "timestamp_utc": entry.timestamp.isoformat(),
                },
            )

            self.session.add(log_record)
            self.session.commit()

            logger.info(
                f"PII access logged: user={entry.user_id} "
                f"role={entry.user_role} field={entry.field_type} "
                f"operation={entry.operation}"
            )

            return str(log_record.log_id)

        except Exception as e:
            logger.error(f"Failed to log PII access: {e}", exc_info=True)
            try:
                self.session.rollback()
            except Exception:
                pass
            return None

    def get_pii_access_logs(
        self,
        user_id: Optional[str] = None,
        firm_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditLogRecord]:
        """
        Retrieve PII access logs for compliance audit.

        Args:
            user_id: Filter by user ID (optional)
            firm_id: Filter by firm ID (optional)
            start_time: Filter by start timestamp (optional)
            end_time: Filter by end timestamp (optional)
            limit: Max results to return (default: 100)

        Returns:
            List of audit log records
        """
        if not self.session:
            logger.warning("No database session available - cannot retrieve logs")
            return []

        try:
            query = self.session.query(AuditLogRecord).filter(
                AuditLogRecord.event_type == "PII_ACCESS"
            )

            if user_id:
                query = query.filter(AuditLogRecord.user_id == user_id)

            if firm_id:
                query = query.filter(AuditLogRecord.firm_id == firm_id)

            if start_time:
                query = query.filter(AuditLogRecord.timestamp >= start_time)

            if end_time:
                query = query.filter(AuditLogRecord.timestamp <= end_time)

            return query.order_by(AuditLogRecord.timestamp.desc()).limit(limit).all()

        except Exception as e:
            logger.error(f"Failed to retrieve PII access logs: {e}", exc_info=True)
            return []

    def is_admin_access_only(
        self,
        user_id: str,
        firm_id: Optional[str] = None,
        hours: int = 24,
    ) -> bool:
        """
        Check if a user has only accessed PII as admin in recent period.

        Args:
            user_id: User to check
            firm_id: Firm to check (optional)
            hours: Time period to check (default: 24 hours)

        Returns:
            True if all accesses were admin-level, False otherwise
        """
        if not self.session:
            return False

        try:
            start_time = datetime.now(timezone.utc)
            # Calculate start_time as 'hours' ago
            from datetime import timedelta

            start_time = start_time - timedelta(hours=hours)

            query = self.session.query(AuditLogRecord).filter(
                AuditLogRecord.event_type == "PII_ACCESS",
                AuditLogRecord.user_id == user_id,
                AuditLogRecord.timestamp >= start_time,
            )

            if firm_id:
                query = query.filter(AuditLogRecord.firm_id == firm_id)

            logs = query.all()

            if not logs:
                return True  # No access = no violations

            # Check if all accesses are admin-level
            admin_roles = {"super_admin", "platform_admin", "partner"}
            for log in logs:
                if log.user_role not in admin_roles:
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to check admin-only access: {e}", exc_info=True)
            return False


# Global audit service instance
_global_audit_service: Optional[PIIAuditService] = None


def get_pii_audit_service(session: Optional[Session] = None) -> PIIAuditService:
    """Get or create global PII audit service."""
    global _global_audit_service
    if _global_audit_service is None:
        _global_audit_service = PIIAuditService(session=session)
    return _global_audit_service


def set_pii_audit_service(service: PIIAuditService) -> None:
    """Set global PII audit service (for testing)."""
    global _global_audit_service
    _global_audit_service = service
