"""
SMTP Email Provider

Standard SMTP integration for email delivery.
Best for self-hosted mail servers or testing.

Configuration:
    SMTP_HOST: SMTP server hostname
    SMTP_PORT: SMTP server port (default: 587)
    SMTP_USERNAME: SMTP authentication username
    SMTP_PASSWORD: SMTP authentication password
    SMTP_USE_TLS: Use TLS encryption (default: True)
    SMTP_FROM_EMAIL: Default sender email
"""

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import List, Optional

from .email_provider import (
    EmailProvider,
    EmailMessage,
    DeliveryResult,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)


class SMTPProvider(EmailProvider):
    """
    SMTP email provider.

    Features:
    - Works with any SMTP server
    - TLS/SSL support
    - Basic authentication
    - Good for testing/development
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ):
        """
        Initialize SMTP provider.

        Args:
            host: SMTP server hostname
            port: SMTP server port
            username: Authentication username
            password: Authentication password
            use_tls: Use STARTTLS (port 587)
            use_ssl: Use SSL/TLS (port 465)
            from_email: Default sender email
            from_name: Default sender name
        """
        self.host = host or os.environ.get("SMTP_HOST")
        self.port = port or int(os.environ.get("SMTP_PORT", "587"))
        self.username = username or os.environ.get("SMTP_USERNAME")
        self.password = password or os.environ.get("SMTP_PASSWORD")
        self.use_tls = use_tls if not os.environ.get("SMTP_USE_TLS") else (
            os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
        )
        self.use_ssl = use_ssl if not os.environ.get("SMTP_USE_SSL") else (
            os.environ.get("SMTP_USE_SSL", "false").lower() == "true"
        )
        self.from_email = from_email or os.environ.get(
            "SMTP_FROM_EMAIL", "noreply@example.com"
        )
        self.from_name = from_name or os.environ.get(
            "SMTP_FROM_NAME", "Tax Filing Platform"
        )

    @property
    def provider_name(self) -> str:
        return "smtp"

    def is_configured(self) -> bool:
        """Check if SMTP is properly configured."""
        return bool(self.host)

    def send(self, message: EmailMessage) -> DeliveryResult:
        """
        Send email via SMTP.

        Args:
            message: Email message to send

        Returns:
            DeliveryResult with status
        """
        if not self.is_configured():
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message="SMTP not configured (missing SMTP_HOST)",
                error_code="NOT_CONFIGURED",
            )

        message.validate()

        try:
            # Build MIME message
            msg = MIMEMultipart("alternative")

            # Set headers
            from_email = message.from_email or self.from_email
            from_name = message.from_name or self.from_name
            msg["From"] = formataddr((from_name, from_email))
            msg["To"] = message.to
            msg["Subject"] = message.subject

            if message.reply_to:
                msg["Reply-To"] = message.reply_to

            if message.cc:
                msg["Cc"] = ", ".join(message.cc)

            # Add custom headers (sanitize against CRLF injection)
            for key, value in message.headers.items():
                if any(c in str(key) + str(value) for c in ('\r', '\n')):
                    logger.warning(f"Rejected email header with CRLF: {key!r}")
                    continue
                msg[key] = value

            # Add content
            if message.body_text:
                part1 = MIMEText(message.body_text, "plain", "utf-8")
                msg.attach(part1)

            if message.body_html:
                part2 = MIMEText(message.body_html, "html", "utf-8")
                msg.attach(part2)

            # Build recipient list
            recipients = [message.to]
            if message.cc:
                recipients.extend(message.cc)
            if message.bcc:
                recipients.extend(message.bcc)

            # Send via SMTP
            if self.use_ssl:
                # SSL connection (port 465)
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=context) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(from_email, recipients, msg.as_string())
            else:
                # STARTTLS connection (port 587) or plain
                with smtplib.SMTP(self.host, self.port) as server:
                    if self.use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(from_email, recipients, msg.as_string())

            logger.info(f"SMTP: Email sent to {message.to}")

            # SMTP doesn't return a message ID, generate one
            import uuid
            message_id = f"smtp-{uuid.uuid4()}"

            return DeliveryResult(
                success=True,
                status=DeliveryStatus.SENT,
                message_id=message_id,
                provider=self.provider_name,
            )

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP auth error: {e}")
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message=f"SMTP authentication failed: {e}",
                error_code="AUTH_ERROR",
            )
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipients refused: {e}")
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.BOUNCED,
                provider=self.provider_name,
                error_message=f"Recipients refused: {e}",
                error_code="RECIPIENTS_REFUSED",
            )
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message=str(e),
                error_code="SMTP_ERROR",
            )
        except Exception as e:
            logger.exception(f"SMTP send error: {e}")
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message=str(e),
                error_code="SEND_ERROR",
            )

    def send_batch(self, messages: List[EmailMessage]) -> List[DeliveryResult]:
        """Send multiple emails (sends individually)."""
        results = []
        for message in messages:
            result = self.send(message)
            results.append(result)
        return results

    def test_connection(self) -> bool:
        """
        Test SMTP connection.

        Returns:
            True if connection successful
        """
        try:
            if self.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=context) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.noop()
            else:
                with smtplib.SMTP(self.host, self.port) as server:
                    if self.use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.noop()
            logger.info(f"SMTP connection test successful: {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False
