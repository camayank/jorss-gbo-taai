"""
Notification Delivery System

Production-ready email delivery and notification triggers.

Provides:
- Multi-provider email delivery (SendGrid, AWS SES, SMTP)
- Unified notification interface
- Comprehensive email triggers for all platform events
- Template rendering
- Delivery tracking and retry logic

Usage:
    from notifications import send_email, email_triggers

    # Send using configured provider
    result = send_email(
        to="user@example.com",
        subject="Your Tax Return",
        body_html="<p>Ready for review</p>",
        body_text="Ready for review",
    )

    # Use email triggers for standard notifications
    await email_triggers.send_appointment_booked(
        recipient_email="client@example.com",
        recipient_name="John Doe",
        appointment_time=datetime.now(),
        appointment_type="tax_consultation",
        cpa_name="Jane CPA",
        confirmation_code="ABC123",
    )
"""

from .email_provider import (
    EmailProvider,
    EmailMessage,
    DeliveryResult,
    DeliveryStatus,
    get_email_provider,
    send_email,
)

from .sendgrid_provider import SendGridProvider
from .ses_provider import SESProvider
from .smtp_provider import SMTPProvider

from .email_triggers import (
    EmailTriggerService,
    EmailTriggerType,
    email_triggers,
    send_appointment_booked,
    send_appointment_reminder,
    send_task_assigned,
    send_deadline_reminder,
    send_document_request,
    send_ticket_update,
    send_welcome_email,
    send_invitation_email,
)

__all__ = [
    # Core interfaces
    "EmailProvider",
    "EmailMessage",
    "DeliveryResult",
    "DeliveryStatus",
    "get_email_provider",
    "send_email",
    # Providers
    "SendGridProvider",
    "SESProvider",
    "SMTPProvider",
    # Email triggers
    "EmailTriggerService",
    "EmailTriggerType",
    "email_triggers",
    "send_appointment_booked",
    "send_appointment_reminder",
    "send_task_assigned",
    "send_deadline_reminder",
    "send_document_request",
    "send_ticket_update",
    "send_welcome_email",
    "send_invitation_email",
]
