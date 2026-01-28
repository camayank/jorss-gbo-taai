"""
SendGrid Email Provider

Production-ready SendGrid integration for email delivery.
Recommended for most deployments due to reliability and features.

Configuration:
    SENDGRID_API_KEY: Your SendGrid API key (required)
    SENDGRID_FROM_EMAIL: Default sender email (optional)
    SENDGRID_FROM_NAME: Default sender name (optional)
"""

import logging
import os
from typing import List, Optional

from .email_provider import (
    EmailProvider,
    EmailMessage,
    DeliveryResult,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)


class SendGridProvider(EmailProvider):
    """
    SendGrid email provider.

    Features:
    - Template support (dynamic templates)
    - Batch sending
    - Click/open tracking
    - Delivery webhooks
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ):
        """
        Initialize SendGrid provider.

        Args:
            api_key: SendGrid API key (or SENDGRID_API_KEY env var)
            from_email: Default sender email
            from_name: Default sender name
        """
        self.api_key = api_key or os.environ.get("SENDGRID_API_KEY")
        self.from_email = from_email or os.environ.get(
            "SENDGRID_FROM_EMAIL", "noreply@example.com"
        )
        self.from_name = from_name or os.environ.get(
            "SENDGRID_FROM_NAME", "Tax Filing Platform"
        )
        self._client = None

    @property
    def provider_name(self) -> str:
        return "sendgrid"

    def _get_client(self):
        """Lazy-load SendGrid client."""
        if self._client is None:
            try:
                from sendgrid import SendGridAPIClient
                self._client = SendGridAPIClient(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "SendGrid library not installed. Run: pip install sendgrid"
                )
        return self._client

    def is_configured(self) -> bool:
        """Check if SendGrid is properly configured."""
        return bool(self.api_key)

    def send(self, message: EmailMessage) -> DeliveryResult:
        """
        Send email via SendGrid.

        Args:
            message: Email message to send

        Returns:
            DeliveryResult with SendGrid message ID
        """
        if not self.is_configured():
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message="SendGrid API key not configured",
                error_code="NOT_CONFIGURED",
            )

        message.validate()

        try:
            from sendgrid.helpers.mail import (
                Mail,
                Email,
                To,
                Content,
                HtmlContent,
                Personalization,
            )

            # Build mail object
            from_email = Email(
                message.from_email or self.from_email,
                message.from_name or self.from_name,
            )
            to_email = To(message.to)

            mail = Mail()
            mail.from_email = from_email
            mail.subject = message.subject

            # Add recipients
            personalization = Personalization()
            personalization.add_to(to_email)

            if message.cc:
                for cc_email in message.cc:
                    from sendgrid.helpers.mail import Cc
                    personalization.add_cc(Cc(cc_email))

            if message.bcc:
                for bcc_email in message.bcc:
                    from sendgrid.helpers.mail import Bcc
                    personalization.add_bcc(Bcc(bcc_email))

            # Add template data if using templates
            if message.template_id:
                mail.template_id = message.template_id
                if message.template_data:
                    personalization.dynamic_template_data = message.template_data
            else:
                # Add content
                if message.body_text:
                    mail.add_content(Content("text/plain", message.body_text))
                if message.body_html:
                    mail.add_content(Content("text/html", message.body_html))

            mail.add_personalization(personalization)

            # Add reply-to
            if message.reply_to:
                from sendgrid.helpers.mail import ReplyTo
                mail.reply_to = ReplyTo(message.reply_to)

            # Add custom headers
            if message.headers:
                for key, value in message.headers.items():
                    from sendgrid.helpers.mail import Header
                    mail.add_header(Header(key, value))

            # Add categories/tags
            if message.tags:
                from sendgrid.helpers.mail import Category
                for tag in message.tags[:10]:  # SendGrid max 10 categories
                    mail.add_category(Category(tag))

            # Send
            client = self._get_client()
            response = client.send(mail)

            # Parse response
            if response.status_code in (200, 201, 202):
                message_id = response.headers.get("X-Message-Id", "")
                logger.info(
                    f"SendGrid: Email sent to {message.to}, "
                    f"message_id={message_id}"
                )
                return DeliveryResult(
                    success=True,
                    status=DeliveryStatus.SENT,
                    message_id=message_id,
                    provider=self.provider_name,
                    raw_response={"status_code": response.status_code},
                )
            else:
                error_msg = f"SendGrid returned status {response.status_code}"
                logger.error(f"SendGrid error: {error_msg}, body={response.body}")
                return DeliveryResult(
                    success=False,
                    status=DeliveryStatus.FAILED,
                    provider=self.provider_name,
                    error_message=error_msg,
                    error_code=str(response.status_code),
                    raw_response={
                        "status_code": response.status_code,
                        "body": response.body.decode() if response.body else None,
                    },
                )

        except ImportError as e:
            logger.error(f"SendGrid import error: {e}")
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message=f"SendGrid library error: {e}",
                error_code="IMPORT_ERROR",
            )
        except Exception as e:
            logger.exception(f"SendGrid send error: {e}")
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message=str(e),
                error_code="SEND_ERROR",
            )

    def send_batch(self, messages: List[EmailMessage]) -> List[DeliveryResult]:
        """
        Send multiple emails.

        Note: SendGrid supports true batch sending for templates.
        For non-template emails, we send individually.
        """
        results = []
        for message in messages:
            result = self.send(message)
            results.append(result)
        return results
