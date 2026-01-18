"""
Audit Service - Compliance and audit trail management.

Handles:
- Audit log recording
- Compliance tracking
- Activity monitoring
- Reporting for auditors
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
from enum import Enum
import logging
import hashlib
import json

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Types of auditable actions."""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"

    # User Management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    USER_REACTIVATED = "user_reactivated"
    ROLE_CHANGED = "role_changed"
    INVITATION_SENT = "invitation_sent"
    INVITATION_ACCEPTED = "invitation_accepted"

    # Client Management
    CLIENT_CREATED = "client_created"
    CLIENT_UPDATED = "client_updated"
    CLIENT_DELETED = "client_deleted"
    CLIENT_ACCESSED = "client_accessed"

    # Document Management
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    DOCUMENT_DELETED = "document_deleted"

    # Tax Operations
    RETURN_CREATED = "return_created"
    RETURN_UPDATED = "return_updated"
    RETURN_SUBMITTED = "return_submitted"
    RETURN_APPROVED = "return_approved"

    # Billing
    SUBSCRIPTION_CHANGED = "subscription_changed"
    PAYMENT_PROCESSED = "payment_processed"

    # Settings
    SETTINGS_UPDATED = "settings_updated"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"

    # Admin
    IMPERSONATION_STARTED = "impersonation_started"
    IMPERSONATION_ENDED = "impersonation_ended"
    DATA_EXPORTED = "data_exported"


class AuditService:
    """Service for audit logging and compliance tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._audit_logs: List[Dict] = []  # In-memory for demo

    # =========================================================================
    # AUDIT LOGGING
    # =========================================================================

    async def log_action(
        self,
        firm_id: str,
        user_id: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        impersonator_id: Optional[str] = None,
    ) -> str:
        """
        Log an auditable action.

        Returns the audit log ID for reference.
        """
        log_id = str(uuid4())
        now = datetime.utcnow()

        # Create hash for integrity verification
        log_data = {
            "log_id": log_id,
            "firm_id": firm_id,
            "user_id": user_id,
            "action": action,
            "timestamp": now.isoformat(),
        }
        integrity_hash = hashlib.sha256(
            json.dumps(log_data, sort_keys=True).encode()
        ).hexdigest()

        audit_entry = {
            "log_id": log_id,
            "firm_id": firm_id,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "impersonator_id": impersonator_id,
            "integrity_hash": integrity_hash,
            "timestamp": now.isoformat(),
        }

        self._audit_logs.append(audit_entry)
        logger.debug(f"Audit log: {action} by {user_id} on {resource_type}:{resource_id}")

        return log_id

    async def get_audit_logs(
        self,
        firm_id: str,
        user_id: Optional[str] = None,
        action_filter: Optional[List[str]] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query audit logs with filtering."""
        logs = [log for log in self._audit_logs if log["firm_id"] == firm_id]

        if user_id:
            logs = [log for log in logs if log["user_id"] == user_id]
        if action_filter:
            logs = [log for log in logs if log["action"] in action_filter]
        if resource_type:
            logs = [log for log in logs if log["resource_type"] == resource_type]
        if resource_id:
            logs = [log for log in logs if log["resource_id"] == resource_id]
        if start_date:
            logs = [log for log in logs if log["timestamp"] >= start_date.isoformat()]
        if end_date:
            logs = [log for log in logs if log["timestamp"] <= end_date.isoformat()]

        # Sort by timestamp descending
        logs.sort(key=lambda x: x["timestamp"], reverse=True)

        return logs[offset:offset + limit]

    async def get_audit_log(
        self,
        firm_id: str,
        log_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a specific audit log entry."""
        for log in self._audit_logs:
            if log["firm_id"] == firm_id and log["log_id"] == log_id:
                return log
        return None

    # =========================================================================
    # ACTIVITY TRACKING
    # =========================================================================

    async def get_user_activity(
        self,
        firm_id: str,
        user_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get activity summary for a user."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        logs = [
            log for log in self._audit_logs
            if log["firm_id"] == firm_id
            and log["user_id"] == user_id
            and log["timestamp"] >= cutoff
        ]

        # Group by action type
        action_counts = {}
        for log in logs:
            action = log["action"]
            action_counts[action] = action_counts.get(action, 0) + 1

        # Get last login
        logins = [log for log in logs if log["action"] == AuditAction.LOGIN.value]
        last_login = logins[0]["timestamp"] if logins else None

        return {
            "user_id": user_id,
            "period_days": days,
            "total_actions": len(logs),
            "action_breakdown": action_counts,
            "last_login": last_login,
            "most_common_action": max(action_counts, key=action_counts.get) if action_counts else None,
        }

    async def get_firm_activity_summary(
        self,
        firm_id: str,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get activity summary for entire firm."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        logs = [
            log for log in self._audit_logs
            if log["firm_id"] == firm_id
            and log["timestamp"] >= cutoff
        ]

        # Group by day
        daily_counts = {}
        for log in logs:
            date = log["timestamp"][:10]
            daily_counts[date] = daily_counts.get(date, 0) + 1

        # Group by user
        user_counts = {}
        for log in logs:
            user = log["user_id"]
            user_counts[user] = user_counts.get(user, 0) + 1

        # Most active users
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "firm_id": firm_id,
            "period_days": days,
            "total_actions": len(logs),
            "daily_counts": daily_counts,
            "top_users": [{"user_id": u, "count": c} for u, c in top_users],
            "unique_users": len(user_counts),
        }

    async def get_recent_activity(
        self,
        firm_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent activity feed for dashboard."""
        logs = [log for log in self._audit_logs if log["firm_id"] == firm_id]
        logs.sort(key=lambda x: x["timestamp"], reverse=True)

        # Enrich with readable descriptions
        feed = []
        for log in logs[:limit]:
            feed.append({
                "log_id": log["log_id"],
                "action": log["action"],
                "description": self._get_action_description(log),
                "user_id": log["user_id"],
                "resource_type": log["resource_type"],
                "resource_id": log["resource_id"],
                "timestamp": log["timestamp"],
            })

        return feed

    # =========================================================================
    # COMPLIANCE REPORTING
    # =========================================================================

    async def generate_compliance_report(
        self,
        firm_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Generate compliance report for auditors."""
        logs = await self.get_audit_logs(
            firm_id=firm_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        # Security events
        security_events = [
            log for log in logs
            if log["action"] in [
                AuditAction.LOGIN_FAILED.value,
                AuditAction.PASSWORD_CHANGED.value,
                AuditAction.MFA_ENABLED.value,
                AuditAction.MFA_DISABLED.value,
                AuditAction.API_KEY_CREATED.value,
                AuditAction.API_KEY_REVOKED.value,
            ]
        ]

        # Data access events
        data_access_events = [
            log for log in logs
            if log["action"] in [
                AuditAction.CLIENT_ACCESSED.value,
                AuditAction.DOCUMENT_DOWNLOADED.value,
                AuditAction.DATA_EXPORTED.value,
            ]
        ]

        # User management events
        user_events = [
            log for log in logs
            if log["action"] in [
                AuditAction.USER_CREATED.value,
                AuditAction.USER_DEACTIVATED.value,
                AuditAction.ROLE_CHANGED.value,
            ]
        ]

        # Impersonation events (platform admin access)
        impersonation_events = [
            log for log in logs
            if log.get("impersonator_id") is not None
        ]

        return {
            "firm_id": firm_id,
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_events": len(logs),
                "security_events": len(security_events),
                "data_access_events": len(data_access_events),
                "user_management_events": len(user_events),
                "impersonation_events": len(impersonation_events),
            },
            "security_events": security_events[:100],
            "data_access_events": data_access_events[:100],
            "user_events": user_events[:100],
            "impersonation_events": impersonation_events,
            "compliance_flags": self._check_compliance_flags(logs),
        }

    async def generate_access_report(
        self,
        firm_id: str,
        resource_type: str,
        resource_id: str,
    ) -> Dict[str, Any]:
        """Generate access history for a specific resource."""
        logs = await self.get_audit_logs(
            firm_id=firm_id,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=1000,
        )

        # Unique users who accessed
        users = set()
        for log in logs:
            users.add(log["user_id"])

        return {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "total_accesses": len(logs),
            "unique_users": len(users),
            "first_access": logs[-1]["timestamp"] if logs else None,
            "last_access": logs[0]["timestamp"] if logs else None,
            "access_history": logs[:50],
        }

    # =========================================================================
    # DATA RETENTION
    # =========================================================================

    async def get_retention_policy(self, firm_id: str) -> Dict[str, Any]:
        """Get data retention policy for a firm."""
        # Default retention policies (would be configurable)
        return {
            "audit_logs": {
                "retention_days": 2555,  # 7 years for tax compliance
                "archive_after_days": 365,
            },
            "client_data": {
                "retention_days": 2555,
                "anonymize_after_days": 2920,  # 8 years
            },
            "session_data": {
                "retention_days": 90,
            },
        }

    async def check_retention_compliance(self, firm_id: str) -> Dict[str, Any]:
        """Check if firm is compliant with retention policies."""
        # Placeholder - would check actual data
        return {
            "is_compliant": True,
            "checks": [
                {"policy": "audit_log_retention", "status": "compliant"},
                {"policy": "client_data_retention", "status": "compliant"},
                {"policy": "document_retention", "status": "compliant"},
            ],
            "next_review_date": (datetime.utcnow() + timedelta(days=90)).isoformat(),
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_action_description(self, log: Dict) -> str:
        """Generate human-readable description for an action."""
        action = log["action"]
        resource_type = log.get("resource_type", "")
        resource_id = log.get("resource_id", "")

        descriptions = {
            AuditAction.LOGIN.value: "Logged in",
            AuditAction.LOGOUT.value: "Logged out",
            AuditAction.LOGIN_FAILED.value: "Failed login attempt",
            AuditAction.PASSWORD_CHANGED.value: "Changed password",
            AuditAction.MFA_ENABLED.value: "Enabled two-factor authentication",
            AuditAction.MFA_DISABLED.value: "Disabled two-factor authentication",
            AuditAction.USER_CREATED.value: f"Created user {resource_id}",
            AuditAction.USER_UPDATED.value: f"Updated user {resource_id}",
            AuditAction.USER_DEACTIVATED.value: f"Deactivated user {resource_id}",
            AuditAction.ROLE_CHANGED.value: f"Changed role for user {resource_id}",
            AuditAction.CLIENT_CREATED.value: f"Created client {resource_id}",
            AuditAction.CLIENT_ACCESSED.value: f"Accessed client {resource_id}",
            AuditAction.DOCUMENT_UPLOADED.value: f"Uploaded document to {resource_type}",
            AuditAction.DOCUMENT_DOWNLOADED.value: f"Downloaded document from {resource_type}",
            AuditAction.SETTINGS_UPDATED.value: "Updated settings",
            AuditAction.SUBSCRIPTION_CHANGED.value: "Changed subscription plan",
        }

        return descriptions.get(action, f"Performed {action}")

    def _check_compliance_flags(self, logs: List[Dict]) -> List[Dict]:
        """Check for compliance issues in logs."""
        flags = []

        # Check for multiple failed logins
        failed_logins = [log for log in logs if log["action"] == AuditAction.LOGIN_FAILED.value]
        if len(failed_logins) > 10:
            flags.append({
                "type": "security",
                "severity": "warning",
                "message": f"High number of failed login attempts: {len(failed_logins)}",
            })

        # Check for MFA disabled
        mfa_disabled = [log for log in logs if log["action"] == AuditAction.MFA_DISABLED.value]
        if mfa_disabled:
            flags.append({
                "type": "security",
                "severity": "info",
                "message": f"MFA was disabled {len(mfa_disabled)} time(s)",
            })

        # Check for impersonation
        impersonations = [log for log in logs if log.get("impersonator_id")]
        if impersonations:
            flags.append({
                "type": "audit",
                "severity": "info",
                "message": f"Platform admin impersonation occurred {len(impersonations)} time(s)",
            })

        return flags

    async def verify_log_integrity(self, log_id: str) -> bool:
        """Verify integrity of an audit log entry."""
        for log in self._audit_logs:
            if log["log_id"] == log_id:
                # Recalculate hash
                log_data = {
                    "log_id": log["log_id"],
                    "firm_id": log["firm_id"],
                    "user_id": log["user_id"],
                    "action": log["action"],
                    "timestamp": log["timestamp"],
                }
                expected_hash = hashlib.sha256(
                    json.dumps(log_data, sort_keys=True).encode()
                ).hexdigest()

                return log["integrity_hash"] == expected_hash

        return False
