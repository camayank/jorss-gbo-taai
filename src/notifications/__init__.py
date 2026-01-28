"""
Notification Delivery System

SPEC-012 Critical Gap Fix: Production-ready email delivery providers.

Provides:
- Multi-provider email delivery (SendGrid, AWS SES, SMTP)
- Unified notification interface
- Template rendering
- Delivery tracking and retry logic

Usage:
    from notifications import get_email_provider, send_email

    # Send using configured provider
    result = send_email(
        to="user@example.com",
        subject="Your Tax Return",
        body_html="<p>Ready for review</p>",
        body_text="Ready for review",
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
]
