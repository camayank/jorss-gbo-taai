"""
Alert Service - AI-driven alerts and notifications.

Handles:
- Alert generation and management
- Smart notification routing
- Alert prioritization
- Digest compilation
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
from enum import Enum
import logging

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Types of alerts."""
    DEADLINE = "deadline"
    COMPLIANCE = "compliance"
    USAGE = "usage"
    SECURITY = "security"
    BILLING = "billing"
    PERFORMANCE = "performance"
    SYSTEM = "system"
    CLIENT = "client"
    OPPORTUNITY = "opportunity"


class AlertPriority(str, Enum):
    """Alert priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    """Alert statuses."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"


class AlertService:
    """Service for alert management and AI-driven notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._alerts_cache: Dict[str, List[Dict]] = {}  # In-memory for demo

    # =========================================================================
    # ALERT CRUD
    # =========================================================================

    async def create_alert(
        self,
        firm_id: str,
        alert_type: str,
        priority: str,
        title: str,
        message: str,
        metadata: Optional[Dict] = None,
        user_id: Optional[str] = None,
        client_id: Optional[str] = None,
        action_url: Optional[str] = None,
        auto_resolve_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Create a new alert."""
        alert_id = str(uuid4())
        now = datetime.utcnow()

        alert = {
            "alert_id": alert_id,
            "firm_id": firm_id,
            "alert_type": alert_type,
            "priority": priority,
            "status": AlertStatus.ACTIVE.value,
            "title": title,
            "message": message,
            "metadata": metadata or {},
            "user_id": user_id,
            "client_id": client_id,
            "action_url": action_url,
            "auto_resolve_at": auto_resolve_at.isoformat() if auto_resolve_at else None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # Store alert (would be DB in production)
        if firm_id not in self._alerts_cache:
            self._alerts_cache[firm_id] = []
        self._alerts_cache[firm_id].append(alert)

        logger.info(f"Created alert {alert_id}: {title}")

        return alert

    async def get_alerts(
        self,
        firm_id: str,
        status_filter: Optional[List[str]] = None,
        type_filter: Optional[List[str]] = None,
        priority_filter: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get alerts for a firm with filtering."""
        alerts = self._alerts_cache.get(firm_id, [])

        # Apply filters
        if status_filter:
            alerts = [a for a in alerts if a["status"] in status_filter]
        if type_filter:
            alerts = [a for a in alerts if a["alert_type"] in type_filter]
        if priority_filter:
            alerts = [a for a in alerts if a["priority"] in priority_filter]
        if user_id:
            alerts = [a for a in alerts if a.get("user_id") == user_id or a.get("user_id") is None]

        # Sort by priority then created_at
        priority_order = {
            AlertPriority.CRITICAL.value: 0,
            AlertPriority.HIGH.value: 1,
            AlertPriority.MEDIUM.value: 2,
            AlertPriority.LOW.value: 3,
            AlertPriority.INFO.value: 4,
        }
        alerts.sort(key=lambda x: (priority_order.get(x["priority"], 5), x["created_at"]), reverse=True)

        return alerts[offset:offset + limit]

    async def get_alert(
        self,
        firm_id: str,
        alert_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a specific alert."""
        alerts = self._alerts_cache.get(firm_id, [])
        for alert in alerts:
            if alert["alert_id"] == alert_id:
                return alert
        return None

    async def acknowledge_alert(
        self,
        firm_id: str,
        alert_id: str,
        user_id: str,
    ) -> bool:
        """Acknowledge an alert."""
        alerts = self._alerts_cache.get(firm_id, [])
        for alert in alerts:
            if alert["alert_id"] == alert_id:
                alert["status"] = AlertStatus.ACKNOWLEDGED.value
                alert["acknowledged_by"] = user_id
                alert["acknowledged_at"] = datetime.utcnow().isoformat()
                alert["updated_at"] = datetime.utcnow().isoformat()
                return True
        return False

    async def resolve_alert(
        self,
        firm_id: str,
        alert_id: str,
        user_id: Optional[str] = None,
        resolution_note: Optional[str] = None,
    ) -> bool:
        """Resolve an alert."""
        alerts = self._alerts_cache.get(firm_id, [])
        for alert in alerts:
            if alert["alert_id"] == alert_id:
                alert["status"] = AlertStatus.RESOLVED.value
                alert["resolved_by"] = user_id
                alert["resolved_at"] = datetime.utcnow().isoformat()
                alert["resolution_note"] = resolution_note
                alert["updated_at"] = datetime.utcnow().isoformat()
                return True
        return False

    async def dismiss_alert(
        self,
        firm_id: str,
        alert_id: str,
        user_id: str,
    ) -> bool:
        """Dismiss an alert."""
        alerts = self._alerts_cache.get(firm_id, [])
        for alert in alerts:
            if alert["alert_id"] == alert_id:
                alert["status"] = AlertStatus.DISMISSED.value
                alert["dismissed_by"] = user_id
                alert["dismissed_at"] = datetime.utcnow().isoformat()
                alert["updated_at"] = datetime.utcnow().isoformat()
                return True
        return False

    async def snooze_alert(
        self,
        firm_id: str,
        alert_id: str,
        user_id: str,
        snooze_until: datetime,
    ) -> bool:
        """Snooze an alert until a specified time."""
        alerts = self._alerts_cache.get(firm_id, [])
        for alert in alerts:
            if alert["alert_id"] == alert_id:
                alert["status"] = AlertStatus.SNOOZED.value
                alert["snoozed_by"] = user_id
                alert["snoozed_until"] = snooze_until.isoformat()
                alert["updated_at"] = datetime.utcnow().isoformat()
                return True
        return False

    # =========================================================================
    # ALERT GENERATION (AI-DRIVEN)
    # =========================================================================

    async def generate_deadline_alerts(self, firm_id: str) -> List[Dict[str, Any]]:
        """Generate alerts for upcoming deadlines."""
        created = []
        now = datetime.utcnow()

        # Example deadline alerts (would query actual data)
        upcoming_deadlines = [
            {
                "client_name": "Acme Corp",
                "deadline_type": "Tax Return",
                "due_date": now + timedelta(days=3),
                "client_id": "client-1",
            },
            {
                "client_name": "Smith Family Trust",
                "deadline_type": "Estimated Payment",
                "due_date": now + timedelta(days=7),
                "client_id": "client-2",
            },
        ]

        for deadline in upcoming_deadlines:
            days_until = (deadline["due_date"] - now).days

            if days_until <= 3:
                priority = AlertPriority.HIGH.value
            elif days_until <= 7:
                priority = AlertPriority.MEDIUM.value
            else:
                priority = AlertPriority.LOW.value

            alert = await self.create_alert(
                firm_id=firm_id,
                alert_type=AlertType.DEADLINE.value,
                priority=priority,
                title=f"Upcoming: {deadline['deadline_type']} for {deadline['client_name']}",
                message=f"Due in {days_until} days on {deadline['due_date'].strftime('%B %d, %Y')}",
                client_id=deadline["client_id"],
                metadata={"deadline_type": deadline["deadline_type"]},
                auto_resolve_at=deadline["due_date"] + timedelta(days=1),
            )
            created.append(alert)

        return created

    async def generate_compliance_alerts(self, firm_id: str) -> List[Dict[str, Any]]:
        """Generate compliance-related alerts."""
        created = []

        # Example compliance checks (would analyze actual data)
        compliance_issues = [
            {
                "issue": "Missing W-9 forms",
                "client_count": 5,
                "severity": "medium",
            },
            {
                "issue": "Unsigned engagement letters",
                "client_count": 3,
                "severity": "high",
            },
        ]

        for issue in compliance_issues:
            priority = AlertPriority.HIGH.value if issue["severity"] == "high" else AlertPriority.MEDIUM.value

            alert = await self.create_alert(
                firm_id=firm_id,
                alert_type=AlertType.COMPLIANCE.value,
                priority=priority,
                title=f"Compliance: {issue['issue']}",
                message=f"{issue['client_count']} clients affected. Review and resolve to maintain compliance.",
                metadata={"affected_count": issue["client_count"]},
                action_url="/admin/compliance",
            )
            created.append(alert)

        return created

    async def generate_usage_alerts(self, firm_id: str) -> List[Dict[str, Any]]:
        """Generate usage threshold alerts."""
        created = []

        # Example usage thresholds (would check actual usage)
        usage_warnings = [
            {"resource": "team_members", "current": 9, "limit": 10, "percentage": 90},
            {"resource": "clients", "current": 450, "limit": 500, "percentage": 90},
        ]

        for warning in usage_warnings:
            if warning["percentage"] >= 90:
                priority = AlertPriority.HIGH.value
                title = f"Usage Alert: {warning['resource'].replace('_', ' ').title()} at {warning['percentage']}%"
            else:
                continue

            alert = await self.create_alert(
                firm_id=firm_id,
                alert_type=AlertType.USAGE.value,
                priority=priority,
                title=title,
                message=f"You're using {warning['current']} of {warning['limit']} {warning['resource'].replace('_', ' ')}. Consider upgrading your plan.",
                metadata=warning,
                action_url="/admin/billing/upgrade",
            )
            created.append(alert)

        return created

    async def generate_opportunity_alerts(self, firm_id: str) -> List[Dict[str, Any]]:
        """Generate AI-identified opportunity alerts."""
        created = []

        # Example opportunities (would use AI analysis)
        opportunities = [
            {
                "client_name": "Tech Startup Inc",
                "opportunity": "R&D Tax Credit eligible",
                "potential_savings": 45000,
                "confidence": 0.85,
                "client_id": "client-5",
            },
            {
                "client_name": "Real Estate Holdings LLC",
                "opportunity": "Cost segregation study candidate",
                "potential_savings": 120000,
                "confidence": 0.78,
                "client_id": "client-8",
            },
        ]

        for opp in opportunities:
            alert = await self.create_alert(
                firm_id=firm_id,
                alert_type=AlertType.OPPORTUNITY.value,
                priority=AlertPriority.MEDIUM.value,
                title=f"Opportunity: {opp['opportunity']}",
                message=f"{opp['client_name']} may benefit from {opp['opportunity']}. Estimated savings: ${opp['potential_savings']:,}",
                client_id=opp["client_id"],
                metadata={
                    "potential_savings": opp["potential_savings"],
                    "confidence": opp["confidence"],
                },
                action_url=f"/clients/{opp['client_id']}/opportunities",
            )
            created.append(alert)

        return created

    # =========================================================================
    # ALERT ANALYTICS
    # =========================================================================

    async def get_alert_summary(self, firm_id: str) -> Dict[str, Any]:
        """Get summary of alerts for dashboard."""
        alerts = self._alerts_cache.get(firm_id, [])
        active_alerts = [a for a in alerts if a["status"] == AlertStatus.ACTIVE.value]

        by_priority = {}
        by_type = {}

        for alert in active_alerts:
            priority = alert["priority"]
            alert_type = alert["alert_type"]

            by_priority[priority] = by_priority.get(priority, 0) + 1
            by_type[alert_type] = by_type.get(alert_type, 0) + 1

        return {
            "total_active": len(active_alerts),
            "by_priority": by_priority,
            "by_type": by_type,
            "critical_count": by_priority.get(AlertPriority.CRITICAL.value, 0),
            "high_count": by_priority.get(AlertPriority.HIGH.value, 0),
        }

    async def get_alert_trends(
        self,
        firm_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get alert trends over time."""
        alerts = self._alerts_cache.get(firm_id, [])
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        recent_alerts = [a for a in alerts if a["created_at"] >= cutoff]

        # Group by day
        daily_counts = {}
        for alert in recent_alerts:
            date = alert["created_at"][:10]  # YYYY-MM-DD
            daily_counts[date] = daily_counts.get(date, 0) + 1

        # Resolution metrics
        resolved = [a for a in recent_alerts if a["status"] == AlertStatus.RESOLVED.value]
        avg_resolution_time = 0
        if resolved:
            # Calculate average resolution time (placeholder)
            avg_resolution_time = 24  # hours

        return {
            "period_days": days,
            "total_created": len(recent_alerts),
            "total_resolved": len(resolved),
            "resolution_rate": len(resolved) / len(recent_alerts) * 100 if recent_alerts else 0,
            "avg_resolution_hours": avg_resolution_time,
            "daily_counts": daily_counts,
        }

    # =========================================================================
    # DIGEST & NOTIFICATIONS
    # =========================================================================

    async def compile_daily_digest(self, firm_id: str) -> Dict[str, Any]:
        """Compile daily alert digest for email/notification."""
        alerts = await self.get_alerts(
            firm_id=firm_id,
            status_filter=[AlertStatus.ACTIVE.value],
        )

        critical = [a for a in alerts if a["priority"] == AlertPriority.CRITICAL.value]
        high = [a for a in alerts if a["priority"] == AlertPriority.HIGH.value]
        other = [a for a in alerts if a["priority"] not in [AlertPriority.CRITICAL.value, AlertPriority.HIGH.value]]

        return {
            "firm_id": firm_id,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total": len(alerts),
                "critical": len(critical),
                "high": len(high),
                "other": len(other),
            },
            "critical_alerts": critical[:5],  # Top 5
            "high_priority_alerts": high[:10],  # Top 10
            "requires_action": len(critical) > 0 or len(high) > 0,
        }

    # In-memory preference storage keyed by "firm_id:user_id"
    _notification_prefs: Dict[str, Dict[str, Any]] = {}

    def _prefs_key(self, firm_id: str, user_id: str) -> str:
        return f"{firm_id or 'none'}:{user_id or 'none'}"

    async def get_notification_preferences(
        self,
        firm_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get notification preferences for a user."""
        defaults = {
            "email_enabled": True,
            "email_digest": "daily",
            "push_enabled": True,
            "sms_enabled": False,
            "quiet_hours": {
                "enabled": True,
                "start": "22:00",
                "end": "07:00",
            },
            "alert_types": {
                AlertType.CRITICAL.value: {"email": True, "push": True, "sms": True},
                AlertType.HIGH.value: {"email": True, "push": True, "sms": False},
                AlertType.MEDIUM.value: {"email": True, "push": False, "sms": False},
                AlertType.LOW.value: {"email": False, "push": False, "sms": False},
            },
        }

        # Merge stored overrides
        key = self._prefs_key(firm_id, user_id)
        stored = AlertService._notification_prefs.get(key, {})
        defaults.update(stored)
        return defaults

    async def update_notification_preferences(
        self,
        firm_id: str,
        user_id: str,
        preferences: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update notification preferences for a user."""
        key = self._prefs_key(firm_id, user_id)
        if key not in AlertService._notification_prefs:
            AlertService._notification_prefs[key] = {}
        AlertService._notification_prefs[key].update(preferences)
        return AlertService._notification_prefs[key]
