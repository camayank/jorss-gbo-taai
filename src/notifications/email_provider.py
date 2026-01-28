"""
Email Provider Abstraction

SPEC-012 Critical Gap Fix: Unified interface for email delivery providers.

Supports:
- SendGrid (recommended for production)
- AWS SES (for AWS infrastructure)
- SMTP (for testing/self-hosted)
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Email delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"
    QUEUED = "queued"


@dataclass
class EmailMessage:
    """Email message to be sent."""
    to: str
    subject: str
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    headers: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Template support
    template_id: Optional[str] = None
    template_data: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """Validate message has required fields."""
        if not self.to:
            raise ValueError("Recipient email (to) is required")
        if not self.subject:
            raise ValueError("Subject is required")
        if not self.body_html and not self.body_text and not self.template_id:
            raise ValueError("Either body_html, body_text, or template_id is required")
        return True


@dataclass
class DeliveryResult:
    """Result of email delivery attempt."""
    success: bool
    status: DeliveryStatus
    message_id: Optional[str] = None
    provider: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "status": self.status.value,
            "message_id": self.message_id,
            "provider": self.provider,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "timestamp": self.timestamp.isoformat(),
        }


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name for logging."""
        pass

    @abstractmethod
    def send(self, message: EmailMessage) -> DeliveryResult:
        """
        Send an email message.

        Args:
            message: Email message to send

        Returns:
            DeliveryResult with success/failure status
        """
        pass

    @abstractmethod
    def send_batch(self, messages: List[EmailMessage]) -> List[DeliveryResult]:
        """
        Send multiple emails in batch.

        Args:
            messages: List of email messages

        Returns:
            List of delivery results
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider is properly configured."""
        pass

    def send_template(
        self,
        to: str,
        template_id: str,
        template_data: Dict[str, Any],
        subject: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> DeliveryResult:
        """
        Send email using a template.

        Args:
            to: Recipient email
            template_id: Provider-specific template ID
            template_data: Data for template variables
            subject: Subject line (if not in template)
            from_email: Sender email (optional)

        Returns:
            DeliveryResult
        """
        message = EmailMessage(
            to=to,
            subject=subject or "",
            template_id=template_id,
            template_data=template_data,
            from_email=from_email,
        )
        return self.send(message)


class NullEmailProvider(EmailProvider):
    """
    Null provider for testing/development.

    Logs emails but doesn't send them.
    """

    @property
    def provider_name(self) -> str:
        return "null"

    def send(self, message: EmailMessage) -> DeliveryResult:
        """Log email without sending."""
        message.validate()
        logger.info(
            f"[NULL PROVIDER] Would send email to {message.to}: {message.subject}"
        )
        return DeliveryResult(
            success=True,
            status=DeliveryStatus.SENT,
            message_id=f"null-{datetime.utcnow().timestamp()}",
            provider=self.provider_name,
        )

    def send_batch(self, messages: List[EmailMessage]) -> List[DeliveryResult]:
        """Log all emails without sending."""
        return [self.send(msg) for msg in messages]

    def is_configured(self) -> bool:
        """Always configured (it's a null provider)."""
        return True


# Global provider instance
_email_provider: Optional[EmailProvider] = None


def get_email_provider() -> EmailProvider:
    """
    Get the configured email provider.

    Provider selection order:
    1. SENDGRID_API_KEY → SendGrid
    2. AWS_SES_REGION → AWS SES
    3. SMTP_HOST → SMTP
    4. None → Null provider (logging only)

    Returns:
        Configured EmailProvider instance
    """
    global _email_provider

    if _email_provider is not None:
        return _email_provider

    # Check for SendGrid
    if os.environ.get("SENDGRID_API_KEY"):
        from .sendgrid_provider import SendGridProvider
        _email_provider = SendGridProvider()
        logger.info("Email provider: SendGrid")
        return _email_provider

    # Check for AWS SES
    if os.environ.get("AWS_SES_REGION") or os.environ.get("AWS_ACCESS_KEY_ID"):
        from .ses_provider import SESProvider
        _email_provider = SESProvider()
        logger.info("Email provider: AWS SES")
        return _email_provider

    # Check for SMTP
    if os.environ.get("SMTP_HOST"):
        from .smtp_provider import SMTPProvider
        _email_provider = SMTPProvider()
        logger.info("Email provider: SMTP")
        return _email_provider

    # Fallback to null provider
    logger.warning(
        "No email provider configured. Emails will be logged but not sent. "
        "Set SENDGRID_API_KEY, AWS_SES_REGION, or SMTP_HOST to enable email delivery."
    )
    _email_provider = NullEmailProvider()
    return _email_provider


def set_email_provider(provider: EmailProvider):
    """
    Set a custom email provider (for testing).

    Args:
        provider: EmailProvider instance to use
    """
    global _email_provider
    _email_provider = provider
    logger.info(f"Email provider set to: {provider.provider_name}")


def send_email(
    to: str,
    subject: str,
    body_html: Optional[str] = None,
    body_text: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    reply_to: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> DeliveryResult:
    """
    Convenience function to send an email.

    Args:
        to: Recipient email address
        subject: Email subject
        body_html: HTML body (optional)
        body_text: Plain text body (optional)
        from_email: Sender email (uses default if not provided)
        from_name: Sender name
        reply_to: Reply-to address
        tags: Tags for tracking
        metadata: Additional metadata

    Returns:
        DeliveryResult with status
    """
    message = EmailMessage(
        to=to,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        from_email=from_email,
        from_name=from_name,
        reply_to=reply_to,
        tags=tags or [],
        metadata=metadata or {},
    )

    provider = get_email_provider()
    return provider.send(message)


def send_templated_email(
    to: str,
    template_id: str,
    template_data: Dict[str, Any],
    subject: Optional[str] = None,
    from_email: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> DeliveryResult:
    """
    Send email using a template.

    Args:
        to: Recipient email
        template_id: Provider template ID
        template_data: Template variable data
        subject: Subject (if not in template)
        from_email: Sender email
        tags: Tags for tracking

    Returns:
        DeliveryResult
    """
    message = EmailMessage(
        to=to,
        subject=subject or "",
        template_id=template_id,
        template_data=template_data,
        from_email=from_email,
        tags=tags or [],
    )

    provider = get_email_provider()
    return provider.send(message)
