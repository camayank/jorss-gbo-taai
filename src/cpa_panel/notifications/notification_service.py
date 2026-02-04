"""
State-Based Email Notification Service

Sends email notifications on exactly 3 state transitions:
1. READY_FOR_REVIEW - Notify CPA that return is ready for review
2. APPROVED - Notify client that return has been approved
3. DELIVERED - Notify client that return has been delivered

SCOPE BOUNDARIES (ENFORCED):
- 3 triggers only (do not add more)
- Email only (no SMS, no push)
- Template-based (no custom messages)
- Async-ready (webhook for actual sending)

This service generates notification events.
Actual email sending is handled by external email provider (SendGrid, SES, etc.)
via webhook integration.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class NotificationTrigger(str, Enum):
    """
    The ONLY 3 notification triggers allowed.

    DO NOT ADD MORE TRIGGERS.
    """
    READY_FOR_REVIEW = "ready_for_review"  # → Notify CPA
    APPROVED = "approved"                   # → Notify Client
    DELIVERED = "delivered"                 # → Notify Client


@dataclass
class NotificationEvent:
    """A notification event to be sent."""
    event_id: str
    trigger: NotificationTrigger
    session_id: str
    tenant_id: str

    # Recipient
    recipient_email: str
    recipient_name: str
    recipient_type: str  # "cpa" or "client"

    # Content
    subject: str
    body_text: str
    body_html: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    status: str = "pending"  # pending, sent, failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trigger": self.trigger.value,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "recipient_email": self.recipient_email,
            "recipient_name": self.recipient_name,
            "recipient_type": self.recipient_type,
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "status": self.status,
        }


class NotificationService:
    """
    Service for generating state-based email notifications.

    SCOPE: 3 triggers only. Template-based. Email only.
    Actual sending is delegated to external provider via callback.
    """

    # Email templates (plain text + optional HTML)
    TEMPLATES = {
        NotificationTrigger.READY_FOR_REVIEW: {
            "subject": "Tax Return Ready for Review: {client_name} ({tax_year})",
            "body_text": """
Hello {cpa_name},

A tax return is ready for your review.

Client: {client_name}
Tax Year: {tax_year}
Complexity: {complexity_tier}
Session ID: {session_id}

Please log in to your CPA dashboard to review this return.

This is an automated notification from your tax preparation platform.
""",
            "body_html": """
<p>Hello {cpa_name},</p>

<p>A tax return is ready for your review.</p>

<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Client</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Tax Year</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{tax_year}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Complexity</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{complexity_tier}</td></tr>
</table>

<p>Please log in to your CPA dashboard to review this return.</p>

<p style="color: #666; font-size: 12px;">This is an automated notification from your tax preparation platform.</p>
""",
        },
        NotificationTrigger.APPROVED: {
            "subject": "Your {tax_year} Tax Return Has Been Approved",
            "body_text": """
Hello {client_name},

Great news! Your {tax_year} federal tax return has been reviewed and approved by {cpa_name}.

What's Next:
- Your return will be filed with the IRS
- You will receive confirmation once the IRS accepts your return
- If you have any questions, please contact your CPA

CPA Contact:
{cpa_name}
{cpa_firm}
{cpa_email}

Thank you for trusting us with your tax preparation.

This is an automated notification. Please do not reply to this email.
""",
            "body_html": """
<p>Hello {client_name},</p>

<p><strong>Great news!</strong> Your {tax_year} federal tax return has been reviewed and approved by {cpa_name}.</p>

<h3 style="color: #5387c1;">What's Next</h3>
<ul>
<li>Your return will be filed with the IRS</li>
<li>You will receive confirmation once the IRS accepts your return</li>
<li>If you have any questions, please contact your CPA</li>
</ul>

<h3 style="color: #5387c1;">CPA Contact</h3>
<p>
{cpa_name}<br>
{cpa_firm}<br>
<a href="mailto:{cpa_email}">{cpa_email}</a>
</p>

<p>Thank you for trusting us with your tax preparation.</p>

<p style="color: #666; font-size: 12px;">This is an automated notification. Please do not reply to this email.</p>
""",
        },
        NotificationTrigger.DELIVERED: {
            "subject": "Your {tax_year} Tax Return Has Been Delivered",
            "body_text": """
Hello {client_name},

Your {tax_year} federal tax return has been completed and delivered.

Summary:
- Tax Year: {tax_year}
- Filing Status: {filing_status}
- Prepared by: {cpa_name}, {cpa_firm}

Your return documents are available for download in your client portal.

If you have any questions about your return, please contact your CPA:
{cpa_name}
{cpa_email}

Thank you for choosing {cpa_firm} for your tax preparation needs.

This is an automated notification. Please do not reply to this email.
""",
            "body_html": """
<p>Hello {client_name},</p>

<p>Your {tax_year} federal tax return has been <strong>completed and delivered</strong>.</p>

<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Tax Year</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{tax_year}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Filing Status</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{filing_status}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Prepared by</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{cpa_name}, {cpa_firm}</td></tr>
</table>

<p>Your return documents are available for download in your client portal.</p>

<p>If you have any questions about your return, please contact your CPA:<br>
{cpa_name}<br>
<a href="mailto:{cpa_email}">{cpa_email}</a></p>

<p>Thank you for choosing {cpa_firm} for your tax preparation needs.</p>

<p style="color: #666; font-size: 12px;">This is an automated notification. Please do not reply to this email.</p>
""",
        },
    }

    def __init__(self):
        """Initialize notification service."""
        self._send_callbacks: List[Callable[[NotificationEvent], bool]] = []
        self._event_counter = 0

    def register_send_callback(self, callback: Callable[[NotificationEvent], bool]):
        """
        Register a callback for sending notifications.

        The callback receives a NotificationEvent and should return True if sent successfully.
        This allows integration with any email provider (SendGrid, SES, etc.)
        """
        self._send_callbacks.append(callback)

    def trigger_notification(
        self,
        trigger: NotificationTrigger,
        session_id: str,
        tenant_id: str,
        context: Dict[str, Any],
    ) -> Optional[NotificationEvent]:
        """
        Trigger a notification based on state change.

        Args:
            trigger: Which notification trigger (ONLY 3 allowed)
            session_id: Tax return session ID
            tenant_id: Tenant identifier
            context: Template variables:
                - client_name: Client's name
                - client_email: Client's email
                - cpa_name: CPA's name
                - cpa_email: CPA's email
                - cpa_firm: Firm name
                - tax_year: Tax year
                - complexity_tier: Complexity tier (for READY_FOR_REVIEW)
                - filing_status: Filing status (for DELIVERED)

        Returns:
            NotificationEvent if created, None if failed
        """
        # Validate trigger is one of the 3 allowed
        if trigger not in NotificationTrigger:
            logger.error(f"Invalid notification trigger: {trigger}")
            return None

        # Get template
        template = self.TEMPLATES.get(trigger)
        if not template:
            logger.error(f"No template for trigger: {trigger}")
            return None

        # Determine recipient
        if trigger == NotificationTrigger.READY_FOR_REVIEW:
            recipient_email = context.get("cpa_email", "")
            recipient_name = context.get("cpa_name", "")
            recipient_type = "cpa"
        else:
            recipient_email = context.get("client_email", "")
            recipient_name = context.get("client_name", "")
            recipient_type = "client"

        if not recipient_email:
            logger.warning(f"No recipient email for {trigger} notification")
            return None

        # Generate event ID
        self._event_counter += 1
        event_id = f"NOTIF-{session_id[:8]}-{self._event_counter:04d}"

        # Format templates with context
        try:
            subject = template["subject"].format(**context)
            body_text = template["body_text"].format(**context)
            body_html = template.get("body_html", "").format(**context) if template.get("body_html") else None
        except KeyError as e:
            logger.error(f"Missing context variable for notification: {e}")
            return None

        event = NotificationEvent(
            event_id=event_id,
            trigger=trigger,
            session_id=session_id,
            tenant_id=tenant_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            recipient_type=recipient_type,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

        # Send via callbacks
        sent = False
        for callback in self._send_callbacks:
            try:
                if callback(event):
                    sent = True
                    event.status = "sent"
                    event.sent_at = datetime.utcnow()
                    break
            except Exception as e:
                logger.error(f"Send callback failed: {e}")

        if not sent and self._send_callbacks:
            event.status = "failed"

        logger.info(f"Notification {event_id} ({trigger.value}) -> {recipient_email}: {event.status}")

        return event


# Singleton instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
