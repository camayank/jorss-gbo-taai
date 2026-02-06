"""
Notification Service - Lead Magnet Communication Layer

Handles all communication for the lead magnet flow:
1. Email notifications for new leads to CPA
2. Email report delivery to prospects
3. Hot lead alerts for CPAs
4. Follow-up reminders
5. Action triggers (booking, download, etc.)
"""

from __future__ import annotations

import uuid
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class NotificationType(str, Enum):
    """Types of notifications."""
    NEW_LEAD = "new_lead"  # CPA: New lead captured
    HOT_LEAD = "hot_lead"  # CPA: High-priority lead alert
    LEAD_ENGAGED = "lead_engaged"  # CPA: Lead engaged/booked
    REPORT_READY = "report_ready"  # Prospect: Report ready
    FOLLOW_UP_DUE = "follow_up_due"  # CPA: Time to follow up
    LEAD_CONVERTED = "lead_converted"  # CPA: Lead became client


class NotificationChannel(str, Enum):
    """Delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationStatus(str, Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Notification:
    """A notification to be sent."""
    notification_id: str
    notification_type: NotificationType
    channel: NotificationChannel
    recipient_email: str
    recipient_name: Optional[str] = None
    subject: str = ""
    body: str = ""
    html_body: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.PENDING
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "notification_type": self.notification_type.value,
            "channel": self.channel.value,
            "recipient_email": self.recipient_email,
            "recipient_name": self.recipient_name,
            "subject": self.subject,
            "body": self.body,
            "html_body": self.html_body,
            "data": self.data,
            "status": self.status.value,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class FollowUpReminder:
    """A follow-up reminder for CPA."""
    reminder_id: str
    lead_id: str
    cpa_email: str
    due_date: datetime
    reminder_type: str  # "first_contact", "second_contact", "proposal"
    completed: bool = False
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# NOTIFICATION SERVICE
# =============================================================================

class NotificationService:
    """Service for handling all lead magnet notifications and alerts."""

    _instance: Optional['NotificationService'] = None

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self._db_path = db_path
        else:
            self._db_path = str(Path(__file__).parent.parent.parent / "database" / "jorss_gbo.db")

        self._ensure_tables()
        self._notification_queue: List[Notification] = []

    @classmethod
    def get_instance(cls) -> 'NotificationService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        """Ensure notification tables exist."""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        # Notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id TEXT UNIQUE NOT NULL,
                notification_type TEXT NOT NULL,
                channel TEXT DEFAULT 'email',
                recipient_email TEXT NOT NULL,
                recipient_name TEXT,
                subject TEXT,
                body TEXT,
                html_body TEXT,
                data_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                scheduled_for TEXT,
                sent_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Follow-up reminders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS follow_up_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id TEXT UNIQUE NOT NULL,
                lead_id TEXT NOT NULL,
                cpa_email TEXT NOT NULL,
                due_date TEXT NOT NULL,
                reminder_type TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                completed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Notification preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cpa_email TEXT UNIQUE NOT NULL,
                email_new_leads INTEGER DEFAULT 1,
                email_hot_leads INTEGER DEFAULT 1,
                email_daily_digest INTEGER DEFAULT 1,
                email_follow_up_reminders INTEGER DEFAULT 1,
                in_app_enabled INTEGER DEFAULT 1,
                digest_time TEXT DEFAULT '08:00',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # NEW LEAD NOTIFICATIONS
    # =========================================================================

    def notify_new_lead(
        self,
        cpa_email: str,
        cpa_name: str,
        lead_data: Dict[str, Any],
    ) -> Notification:
        """
        Notify CPA of a new lead captured.

        Args:
            cpa_email: CPA's email address
            cpa_name: CPA's name
            lead_data: Lead information

        Returns:
            Created notification
        """
        lead_name = lead_data.get("first_name", "A prospect")
        lead_score = lead_data.get("lead_score", 50)
        temperature = lead_data.get("lead_temperature", "warm")
        complexity = lead_data.get("complexity", "moderate")
        savings_range = lead_data.get("savings_range", "$500 - $2,000")

        # Determine urgency
        is_hot = temperature == "hot" or lead_score >= 80

        subject = f"🔥 New HOT Lead: {lead_name}" if is_hot else f"📋 New Lead: {lead_name}"

        body = f"""
Hello {cpa_name},

A new lead has been captured through your Tax Advisory Portal!

LEAD DETAILS:
- Name: {lead_name}
- Email: {lead_data.get('email', 'N/A')}
- Phone: {lead_data.get('phone', 'Not provided')}
- Lead Score: {lead_score}/100 ({temperature.upper()})
- Tax Complexity: {complexity.capitalize()}
- Estimated Savings: {savings_range}

RECOMMENDED ACTIONS:
1. Review the lead details in your CPA Dashboard
2. Contact within 24 hours for best conversion
3. Send engagement letter if interested

View Lead: {lead_data.get('dashboard_url', '/cpa/dashboard')}

Best regards,
Tax Advisory Platform
        """.strip()

        html_body = self._generate_new_lead_html(cpa_name, lead_data, is_hot)

        notification = self._create_notification(
            notification_type=NotificationType.HOT_LEAD if is_hot else NotificationType.NEW_LEAD,
            channel=NotificationChannel.EMAIL,
            recipient_email=cpa_email,
            recipient_name=cpa_name,
            subject=subject,
            body=body,
            html_body=html_body,
            data={"lead_id": lead_data.get("lead_id"), "is_hot": is_hot}
        )

        # Schedule follow-up reminders
        self._schedule_follow_up_reminders(
            lead_id=lead_data.get("lead_id", ""),
            cpa_email=cpa_email
        )

        return notification

    def _generate_new_lead_html(
        self,
        cpa_name: str,
        lead_data: Dict[str, Any],
        is_hot: bool
    ) -> str:
        """Generate HTML email for new lead notification."""
        temperature = lead_data.get("lead_temperature", "warm")
        temp_color = {"hot": "#dc2626", "warm": "#f59e0b", "cold": "#5387c1"}.get(temperature, "#f59e0b")

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        <!-- Header -->
        <div style="background: {'linear-gradient(135deg, #dc2626, #f97316)' if is_hot else 'linear-gradient(135deg, #1e3a5f, #5387c1)'}; padding: 24px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">
                {'🔥 New HOT Lead!' if is_hot else '📋 New Lead Captured'}
            </h1>
        </div>

        <!-- Content -->
        <div style="padding: 24px;">
            <p style="color: #374151; font-size: 16px;">Hello {cpa_name},</p>
            <p style="color: #374151; font-size: 16px;">A new lead has been captured through your Tax Advisory Portal!</p>

            <!-- Lead Card -->
            <div style="background: #f9fafb; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid {temp_color};">
                <h3 style="margin: 0 0 16px 0; color: #111827;">{lead_data.get('first_name', 'Prospect')}</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Email:</td>
                        <td style="padding: 8px 0; color: #111827; font-size: 14px;"><strong>{lead_data.get('email', 'N/A')}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Phone:</td>
                        <td style="padding: 8px 0; color: #111827; font-size: 14px;">{lead_data.get('phone') or 'Not provided'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Lead Score:</td>
                        <td style="padding: 8px 0; color: #111827; font-size: 14px;">
                            <span style="background: {temp_color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                                {lead_data.get('lead_score', 50)}/100 ({temperature.upper()})
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Complexity:</td>
                        <td style="padding: 8px 0; color: #111827; font-size: 14px;">{lead_data.get('complexity', 'moderate').capitalize()}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #6b7280; font-size: 14px;">Est. Savings:</td>
                        <td style="padding: 8px 0; color: #059669; font-size: 14px; font-weight: bold;">{lead_data.get('savings_range', '$500 - $2,000')}</td>
                    </tr>
                </table>
            </div>

            <!-- CTA Button -->
            <div style="text-align: center; margin: 24px 0;">
                <a href="{lead_data.get('dashboard_url', '/cpa/dashboard')}" style="display: inline-block; background: #1e3a5f; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                    View Lead in Dashboard
                </a>
            </div>

            <p style="color: #6b7280; font-size: 14px; text-align: center;">
                {'⚡ This is a HOT lead - contact within 24 hours for best conversion!' if is_hot else 'Recommended: Contact within 48 hours'}
            </p>
        </div>

        <!-- Footer -->
        <div style="background: #f9fafb; padding: 16px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="color: #6b7280; font-size: 12px; margin: 0;">Tax Advisory Platform - Lead Magnet System</p>
        </div>
    </div>
</body>
</html>
        """

    # =========================================================================
    # REPORT DELIVERY
    # =========================================================================

    def send_report_to_prospect(
        self,
        prospect_email: str,
        prospect_name: str,
        cpa_name: str,
        cpa_firm: Optional[str],
        report_data: Dict[str, Any],
    ) -> Notification:
        """
        Send the FREE tax advisory report to the prospect.

        Args:
            prospect_email: Prospect's email
            prospect_name: Prospect's name
            cpa_name: CPA's display name
            cpa_firm: CPA's firm name
            report_data: Report information

        Returns:
            Created notification
        """
        savings_range = report_data.get("savings_range", "$500 - $2,000")
        insights_count = report_data.get("total_insights", 5)
        booking_link = report_data.get("booking_link", "#")

        subject = f"Your FREE Tax Advisory Report from {cpa_name}"

        body = f"""
Hello {prospect_name},

Thank you for using our Tax Advisory Assessment! Your personalized report is ready.

YOUR TAX SAVINGS POTENTIAL: {savings_range}

We've identified {insights_count} potential opportunities to optimize your tax situation.

To unlock your full report with detailed recommendations:
1. Schedule a consultation with {cpa_name}
2. Review your complete tax optimization opportunities
3. Get a customized action plan

Book Your Consultation: {booking_link}

Best regards,
{cpa_name}
{cpa_firm or ''}
        """.strip()

        html_body = self._generate_report_email_html(
            prospect_name, cpa_name, cpa_firm, report_data
        )

        return self._create_notification(
            notification_type=NotificationType.REPORT_READY,
            channel=NotificationChannel.EMAIL,
            recipient_email=prospect_email,
            recipient_name=prospect_name,
            subject=subject,
            body=body,
            html_body=html_body,
            data={"session_id": report_data.get("session_id")}
        )

    def _generate_report_email_html(
        self,
        prospect_name: str,
        cpa_name: str,
        cpa_firm: Optional[str],
        report_data: Dict[str, Any],
    ) -> str:
        """Generate HTML email for report delivery."""
        savings_range = report_data.get("savings_range", "$500 - $2,000")
        insights = report_data.get("insights", [])[:3]  # Show top 3
        booking_link = report_data.get("booking_link", "#")

        insights_html = ""
        for insight in insights:
            insights_html += f"""
            <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin-bottom: 12px; border-left: 4px solid #f59e0b;">
                <h4 style="margin: 0 0 8px 0; color: #111827; font-size: 14px;">{insight.get('title', '')}</h4>
                <p style="margin: 0; color: #6b7280; font-size: 13px;">{insight.get('teaser_description', insight.get('description_teaser', ''))[:100]}...</p>
            </div>
            """

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1e3a5f, #5387c1); padding: 24px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">Your FREE Tax Advisory Report</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 14px;">Prepared by {cpa_name}</p>
        </div>

        <!-- Savings Highlight -->
        <div style="background: linear-gradient(135deg, #d1fae5, #a7f3d0); padding: 24px; text-align: center;">
            <p style="color: #166534; margin: 0 0 8px 0; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em;">Your Estimated Tax Savings</p>
            <p style="color: #15803d; margin: 0; font-size: 32px; font-weight: 700;">{savings_range}</p>
        </div>

        <!-- Content -->
        <div style="padding: 24px;">
            <p style="color: #374151; font-size: 16px;">Hello {prospect_name},</p>
            <p style="color: #374151; font-size: 16px;">Based on your tax profile, we've identified several opportunities to optimize your tax situation:</p>

            <!-- Insights Preview -->
            <div style="margin: 20px 0;">
                <h3 style="color: #111827; font-size: 16px; margin-bottom: 16px;">Preview of Your Tax Opportunities:</h3>
                {insights_html}
                <p style="color: #6b7280; font-size: 13px; text-align: center; margin-top: 16px;">
                    + {report_data.get('locked_count', 5)} more insights available in your full report
                </p>
            </div>

            <!-- CTA -->
            <div style="background: #f9fafb; border-radius: 8px; padding: 24px; text-align: center; margin: 24px 0;">
                <h3 style="color: #111827; margin: 0 0 12px 0;">Unlock Your Full Analysis</h3>
                <p style="color: #6b7280; margin: 0 0 20px 0; font-size: 14px;">
                    Schedule a consultation to receive your complete tax optimization plan with exact savings amounts and action items.
                </p>
                <a href="{booking_link}" style="display: inline-block; background: #059669; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
                    Schedule Consultation
                </a>
            </div>
        </div>

        <!-- Footer -->
        <div style="background: #f9fafb; padding: 16px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="color: #374151; font-size: 14px; margin: 0 0 4px 0;"><strong>{cpa_name}</strong></p>
            <p style="color: #6b7280; font-size: 12px; margin: 0;">{cpa_firm or 'Tax Advisory Services'}</p>
        </div>
    </div>
</body>
</html>
        """

    # =========================================================================
    # FOLLOW-UP REMINDERS
    # =========================================================================

    def _schedule_follow_up_reminders(
        self,
        lead_id: str,
        cpa_email: str,
    ):
        """Schedule follow-up reminders for a new lead."""
        now = datetime.utcnow()

        reminders = [
            ("first_contact", now + timedelta(hours=24)),
            ("second_contact", now + timedelta(days=3)),
            ("proposal", now + timedelta(days=7)),
        ]

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            for reminder_type, due_date in reminders:
                reminder_id = f"rem-{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO follow_up_reminders (
                        reminder_id, lead_id, cpa_email, due_date, reminder_type
                    ) VALUES (?, ?, ?, ?, ?)
                """, (reminder_id, lead_id, cpa_email, due_date.isoformat(), reminder_type))

            conn.commit()
            conn.close()
            logger.info(f"Scheduled {len(reminders)} follow-up reminders for lead {lead_id}")
        except Exception as e:
            logger.error(f"Failed to schedule reminders: {e}")

    def get_due_reminders(self, cpa_email: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get reminders that are due."""
        now = datetime.utcnow().isoformat()

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            if cpa_email:
                cursor.execute("""
                    SELECT * FROM follow_up_reminders
                    WHERE cpa_email = ? AND completed = 0 AND due_date <= ?
                    ORDER BY due_date ASC
                """, (cpa_email, now))
            else:
                cursor.execute("""
                    SELECT * FROM follow_up_reminders
                    WHERE completed = 0 AND due_date <= ?
                    ORDER BY due_date ASC
                """, (now,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get due reminders: {e}")
            return []

    def complete_reminder(self, reminder_id: str) -> bool:
        """Mark a reminder as completed."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE follow_up_reminders
                SET completed = 1, completed_at = ?
                WHERE reminder_id = ?
            """, (datetime.utcnow().isoformat(), reminder_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to complete reminder: {e}")
            return False

    # =========================================================================
    # CORE NOTIFICATION METHODS
    # =========================================================================

    def _create_notification(
        self,
        notification_type: NotificationType,
        channel: NotificationChannel,
        recipient_email: str,
        recipient_name: Optional[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        scheduled_for: Optional[datetime] = None,
    ) -> Notification:
        """Create and persist a notification."""
        notification_id = f"notif-{uuid.uuid4().hex[:12]}"

        notification = Notification(
            notification_id=notification_id,
            notification_type=notification_type,
            channel=channel,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            body=body,
            html_body=html_body,
            data=data or {},
            scheduled_for=scheduled_for,
        )

        # Persist
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notifications (
                    notification_id, notification_type, channel,
                    recipient_email, recipient_name, subject, body, html_body,
                    data_json, status, scheduled_for
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notification_id,
                notification_type.value,
                channel.value,
                recipient_email,
                recipient_name,
                subject,
                body,
                html_body,
                json.dumps(data or {}),
                NotificationStatus.PENDING.value,
                scheduled_for.isoformat() if scheduled_for else None,
            ))
            conn.commit()
            conn.close()
            logger.info(f"Created notification {notification_id} ({notification_type.value})")
        except Exception as e:
            logger.error(f"Failed to persist notification: {e}")

        # Add to queue for sending
        self._notification_queue.append(notification)

        # Attempt to send immediately if not scheduled
        if not scheduled_for:
            self._send_notification(notification)

        return notification

    def _send_notification(self, notification: Notification) -> bool:
        """
        Send a notification.

        In production, this would integrate with:
        - SendGrid/SES for email
        - Twilio for SMS
        - WebSocket for in-app
        - Webhook for integrations
        """
        # For now, mark as sent and log
        # In production, integrate with actual email service
        try:
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()

            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notifications SET status = ?, sent_at = ?
                WHERE notification_id = ?
            """, (
                NotificationStatus.SENT.value,
                notification.sent_at.isoformat(),
                notification.notification_id
            ))
            conn.commit()
            conn.close()

            logger.info(
                f"Notification {notification.notification_id} sent to {notification.recipient_email} "
                f"(type: {notification.notification_type.value})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            notification.status = NotificationStatus.FAILED
            return False

    def get_pending_notifications(self) -> List[Notification]:
        """Get all pending notifications."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notifications
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
            rows = cursor.fetchall()
            conn.close()

            notifications = []
            for row in rows:
                notifications.append(Notification(
                    notification_id=row["notification_id"],
                    notification_type=NotificationType(row["notification_type"]),
                    channel=NotificationChannel(row["channel"]),
                    recipient_email=row["recipient_email"],
                    recipient_name=row["recipient_name"],
                    subject=row["subject"],
                    body=row["body"],
                    html_body=row["html_body"],
                    data=json.loads(row["data_json"]) if row["data_json"] else {},
                    status=NotificationStatus(row["status"]),
                ))
            return notifications
        except Exception as e:
            logger.error(f"Failed to get pending notifications: {e}")
            return []

    # =========================================================================
    # NOTIFICATION PREFERENCES
    # =========================================================================

    def get_notification_preferences(self, cpa_email: str) -> Dict[str, Any]:
        """
        Get notification preferences for a CPA.

        Returns default preferences if none are stored.
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notification_preferences
                WHERE cpa_email = ?
            """, (cpa_email,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    "email_new_leads": bool(row["email_new_leads"]),
                    "email_hot_leads": bool(row["email_hot_leads"]),
                    "email_daily_digest": bool(row["email_daily_digest"]),
                    "email_follow_up_reminders": bool(row["email_follow_up_reminders"]),
                    "in_app_enabled": bool(row["in_app_enabled"]),
                    "digest_time": row["digest_time"],
                }
            else:
                # Return defaults
                return {
                    "email_new_leads": True,
                    "email_hot_leads": True,
                    "email_daily_digest": True,
                    "email_follow_up_reminders": True,
                    "in_app_enabled": True,
                    "digest_time": "08:00",
                }
        except Exception as e:
            logger.error(f"Failed to get notification preferences: {e}")
            return {
                "email_new_leads": True,
                "email_hot_leads": True,
                "email_daily_digest": True,
                "email_follow_up_reminders": True,
                "in_app_enabled": True,
                "digest_time": "08:00",
            }

    def update_notification_preferences(
        self,
        cpa_email: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Update notification preferences for a CPA.

        Upserts preferences (creates if not exists, updates if exists).
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Check if exists
            cursor.execute("""
                SELECT 1 FROM notification_preferences
                WHERE cpa_email = ?
            """, (cpa_email,))
            exists = cursor.fetchone() is not None

            now = datetime.utcnow().isoformat()

            if exists:
                cursor.execute("""
                    UPDATE notification_preferences SET
                        email_new_leads = ?,
                        email_hot_leads = ?,
                        email_daily_digest = ?,
                        email_follow_up_reminders = ?,
                        in_app_enabled = ?,
                        digest_time = ?,
                        updated_at = ?
                    WHERE cpa_email = ?
                """, (
                    int(preferences.get("email_new_leads", True)),
                    int(preferences.get("email_hot_leads", True)),
                    int(preferences.get("email_daily_digest", True)),
                    int(preferences.get("email_follow_up_reminders", True)),
                    int(preferences.get("in_app_enabled", True)),
                    preferences.get("digest_time", "08:00"),
                    now,
                    cpa_email,
                ))
            else:
                cursor.execute("""
                    INSERT INTO notification_preferences (
                        cpa_email, email_new_leads, email_hot_leads,
                        email_daily_digest, email_follow_up_reminders,
                        in_app_enabled, digest_time, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cpa_email,
                    int(preferences.get("email_new_leads", True)),
                    int(preferences.get("email_hot_leads", True)),
                    int(preferences.get("email_daily_digest", True)),
                    int(preferences.get("email_follow_up_reminders", True)),
                    int(preferences.get("in_app_enabled", True)),
                    preferences.get("digest_time", "08:00"),
                    now,
                    now,
                ))

            conn.commit()
            conn.close()
            logger.info(f"Updated notification preferences for {cpa_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to update notification preferences: {e}")
            return False

    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Total by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM notifications
                GROUP BY status
            """)
            by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Total by type
            cursor.execute("""
                SELECT notification_type, COUNT(*) as count
                FROM notifications
                GROUP BY notification_type
            """)
            by_type = {row["notification_type"]: row["count"] for row in cursor.fetchall()}

            # Pending reminders
            cursor.execute("""
                SELECT COUNT(*) as count FROM follow_up_reminders
                WHERE completed = 0
            """)
            pending_reminders = cursor.fetchone()["count"]

            conn.close()

            return {
                "by_status": by_status,
                "by_type": by_type,
                "pending_reminders": pending_reminders,
            }
        except Exception as e:
            logger.error(f"Failed to get notification stats: {e}")
            return {}


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

def get_notification_service() -> NotificationService:
    """Get the notification service singleton."""
    return NotificationService.get_instance()
