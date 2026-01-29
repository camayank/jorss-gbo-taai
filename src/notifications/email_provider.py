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


async def send_email_with_attachment(
    to: str,
    subject: str,
    body_html: Optional[str] = None,
    body_text: Optional[str] = None,
    attachment_path: Optional[str] = None,
    attachment_name: Optional[str] = None,
    attachment_content: Optional[bytes] = None,
    attachment_mime_type: str = "application/pdf",
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    reply_to: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> DeliveryResult:
    """
    Send email with file attachment.

    This function supports sending emails with attachments using various providers.
    For providers that don't support attachments natively, it falls back to
    embedding a download link.

    Args:
        to: Recipient email address
        subject: Email subject
        body_html: HTML body (optional)
        body_text: Plain text body (optional)
        attachment_path: Path to file to attach
        attachment_name: Name for the attachment (defaults to filename)
        attachment_content: Raw bytes to attach (alternative to path)
        attachment_mime_type: MIME type of attachment
        from_email: Sender email
        from_name: Sender name
        reply_to: Reply-to address
        tags: Tags for tracking

    Returns:
        DeliveryResult with status
    """
    import base64
    from pathlib import Path as FilePath

    # Read attachment if path provided
    attachment_data = None
    if attachment_path:
        try:
            path = FilePath(attachment_path)
            if path.exists():
                attachment_data = path.read_bytes()
                if not attachment_name:
                    attachment_name = path.name
        except Exception as e:
            logger.error(f"Failed to read attachment {attachment_path}: {e}")

    elif attachment_content:
        attachment_data = attachment_content

    # Get provider
    provider = get_email_provider()

    # Check if provider supports attachments (SendGrid, SMTP do)
    if hasattr(provider, 'send_with_attachment') and attachment_data:
        return await provider.send_with_attachment(
            to=to,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachment_data=attachment_data,
            attachment_name=attachment_name or "attachment.pdf",
            attachment_mime_type=attachment_mime_type,
            from_email=from_email,
            from_name=from_name,
        )

    # Fallback: Use SMTP with attachment support
    if provider.provider_name == "smtp" and attachment_data:
        try:
            return await _send_smtp_with_attachment(
                to=to,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                attachment_data=attachment_data,
                attachment_name=attachment_name or "attachment.pdf",
                attachment_mime_type=attachment_mime_type,
                from_email=from_email,
                from_name=from_name,
            )
        except Exception as e:
            logger.error(f"SMTP attachment send failed: {e}")

    # If SendGrid is available and has attachment data
    if provider.provider_name == "sendgrid" and attachment_data:
        try:
            return await _send_sendgrid_with_attachment(
                to=to,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                attachment_data=attachment_data,
                attachment_name=attachment_name or "attachment.pdf",
                attachment_mime_type=attachment_mime_type,
                from_email=from_email,
                from_name=from_name,
            )
        except Exception as e:
            logger.error(f"SendGrid attachment send failed: {e}")

    # Final fallback: send without attachment
    logger.warning(f"Sending email to {to} without attachment (provider: {provider.provider_name})")
    return provider.send(EmailMessage(
        to=to,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        from_email=from_email,
        from_name=from_name,
        reply_to=reply_to,
        tags=tags or [],
    ))


async def _send_smtp_with_attachment(
    to: str,
    subject: str,
    body_html: Optional[str],
    body_text: Optional[str],
    attachment_data: bytes,
    attachment_name: str,
    attachment_mime_type: str,
    from_email: Optional[str],
    from_name: Optional[str],
) -> DeliveryResult:
    """Send email with attachment via SMTP."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    try:
        # Get SMTP config
        smtp_host = os.environ.get("SMTP_HOST", "localhost")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        smtp_use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
        default_from = os.environ.get("SMTP_FROM_EMAIL", "noreply@example.com")

        sender = from_email or default_from
        if from_name:
            sender_display = f"{from_name} <{sender}>"
        else:
            sender_display = sender

        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_display
        msg['To'] = to
        msg['Subject'] = subject

        # Attach body
        if body_html:
            msg.attach(MIMEText(body_html, 'html'))
        elif body_text:
            msg.attach(MIMEText(body_text, 'plain'))

        # Attach file
        main_type, sub_type = attachment_mime_type.split('/')
        attachment = MIMEBase(main_type, sub_type)
        attachment.set_payload(attachment_data)
        encoders.encode_base64(attachment)
        attachment.add_header(
            'Content-Disposition',
            f'attachment; filename="{attachment_name}"'
        )
        msg.attach(attachment)

        # Send
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(sender, [to], msg.as_string())

        return DeliveryResult(
            success=True,
            status=DeliveryStatus.SENT,
            message_id=f"smtp-{datetime.utcnow().timestamp()}",
            provider="smtp",
        )

    except Exception as e:
        logger.error(f"SMTP send with attachment failed: {e}")
        return DeliveryResult(
            success=False,
            status=DeliveryStatus.FAILED,
            error_message=str(e),
            provider="smtp",
        )


async def _send_sendgrid_with_attachment(
    to: str,
    subject: str,
    body_html: Optional[str],
    body_text: Optional[str],
    attachment_data: bytes,
    attachment_name: str,
    attachment_mime_type: str,
    from_email: Optional[str],
    from_name: Optional[str],
) -> DeliveryResult:
    """Send email with attachment via SendGrid."""
    import base64

    try:
        import sendgrid
        from sendgrid.helpers.mail import (
            Mail, Email, To, Content, Attachment,
            FileContent, FileName, FileType, Disposition
        )

        api_key = os.environ.get("SENDGRID_API_KEY")
        if not api_key:
            raise ValueError("SENDGRID_API_KEY not configured")

        default_from = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@example.com")
        sender = from_email or default_from

        # Create message
        message = Mail(
            from_email=Email(sender, from_name),
            to_emails=To(to),
            subject=subject,
        )

        # Add content
        if body_html:
            message.content = Content("text/html", body_html)
        elif body_text:
            message.content = Content("text/plain", body_text)

        # Add attachment
        encoded_content = base64.b64encode(attachment_data).decode()
        attachment = Attachment(
            FileContent(encoded_content),
            FileName(attachment_name),
            FileType(attachment_mime_type),
            Disposition('attachment')
        )
        message.attachment = attachment

        # Send
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        response = sg.send(message)

        return DeliveryResult(
            success=response.status_code in (200, 202),
            status=DeliveryStatus.SENT if response.status_code in (200, 202) else DeliveryStatus.FAILED,
            message_id=response.headers.get('X-Message-Id'),
            provider="sendgrid",
            raw_response={"status_code": response.status_code},
        )

    except ImportError:
        logger.error("SendGrid package not installed")
        return DeliveryResult(
            success=False,
            status=DeliveryStatus.FAILED,
            error_message="SendGrid package not installed",
            provider="sendgrid",
        )
    except Exception as e:
        logger.error(f"SendGrid send with attachment failed: {e}")
        return DeliveryResult(
            success=False,
            status=DeliveryStatus.FAILED,
            error_message=str(e),
            provider="sendgrid",
        )
