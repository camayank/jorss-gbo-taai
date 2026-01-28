"""
AWS SES Email Provider

Amazon Simple Email Service integration for email delivery.
Best for AWS-hosted infrastructure with existing AWS credentials.

Configuration:
    AWS_SES_REGION: AWS region for SES (e.g., us-east-1)
    AWS_ACCESS_KEY_ID: AWS access key (or use IAM role)
    AWS_SECRET_ACCESS_KEY: AWS secret key (or use IAM role)
    AWS_SES_FROM_EMAIL: Default sender email (must be verified in SES)
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


class SESProvider(EmailProvider):
    """
    AWS Simple Email Service provider.

    Features:
    - High deliverability
    - IAM role support
    - Template support (SES templates)
    - Delivery notifications via SNS
    """

    def __init__(
        self,
        region: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        """
        Initialize SES provider.

        Args:
            region: AWS region (or AWS_SES_REGION env var)
            from_email: Default sender email (must be verified)
            from_name: Default sender name
            access_key_id: AWS access key (or use env/IAM)
            secret_access_key: AWS secret key (or use env/IAM)
        """
        self.region = region or os.environ.get("AWS_SES_REGION", "us-east-1")
        self.from_email = from_email or os.environ.get(
            "AWS_SES_FROM_EMAIL", "noreply@example.com"
        )
        self.from_name = from_name or os.environ.get(
            "AWS_SES_FROM_NAME", "Tax Filing Platform"
        )
        self.access_key_id = access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")
        self.secret_access_key = secret_access_key or os.environ.get("AWS_SECRET_ACCESS_KEY")
        self._client = None

    @property
    def provider_name(self) -> str:
        return "ses"

    def _get_client(self):
        """Lazy-load boto3 SES client."""
        if self._client is None:
            try:
                import boto3

                kwargs = {"region_name": self.region}
                if self.access_key_id and self.secret_access_key:
                    kwargs["aws_access_key_id"] = self.access_key_id
                    kwargs["aws_secret_access_key"] = self.secret_access_key

                self._client = boto3.client("ses", **kwargs)
            except ImportError:
                raise ImportError(
                    "boto3 library not installed. Run: pip install boto3"
                )
        return self._client

    def is_configured(self) -> bool:
        """Check if SES is properly configured."""
        # SES can use IAM roles, so we just need a region
        return bool(self.region)

    def send(self, message: EmailMessage) -> DeliveryResult:
        """
        Send email via AWS SES.

        Args:
            message: Email message to send

        Returns:
            DeliveryResult with SES message ID
        """
        if not self.is_configured():
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message="AWS SES not configured",
                error_code="NOT_CONFIGURED",
            )

        message.validate()

        try:
            client = self._get_client()

            # Build source address
            from_addr = message.from_email or self.from_email
            from_name = message.from_name or self.from_name
            source = f"{from_name} <{from_addr}>" if from_name else from_addr

            # Build destination
            destination = {"ToAddresses": [message.to]}
            if message.cc:
                destination["CcAddresses"] = message.cc
            if message.bcc:
                destination["BccAddresses"] = message.bcc

            # Check if using template
            if message.template_id:
                import json

                response = client.send_templated_email(
                    Source=source,
                    Destination=destination,
                    Template=message.template_id,
                    TemplateData=json.dumps(message.template_data or {}),
                    ReplyToAddresses=[message.reply_to] if message.reply_to else [],
                )
            else:
                # Build message body
                body = {}
                if message.body_text:
                    body["Text"] = {"Data": message.body_text, "Charset": "UTF-8"}
                if message.body_html:
                    body["Html"] = {"Data": message.body_html, "Charset": "UTF-8"}

                email_message = {
                    "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                    "Body": body,
                }

                kwargs = {
                    "Source": source,
                    "Destination": destination,
                    "Message": email_message,
                }

                if message.reply_to:
                    kwargs["ReplyToAddresses"] = [message.reply_to]

                response = client.send_email(**kwargs)

            message_id = response.get("MessageId", "")
            logger.info(f"SES: Email sent to {message.to}, message_id={message_id}")

            return DeliveryResult(
                success=True,
                status=DeliveryStatus.SENT,
                message_id=message_id,
                provider=self.provider_name,
                raw_response=response,
            )

        except ImportError as e:
            logger.error(f"SES import error: {e}")
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message=f"boto3 library error: {e}",
                error_code="IMPORT_ERROR",
            )
        except Exception as e:
            error_code = "SEND_ERROR"
            error_message = str(e)

            # Parse AWS error codes
            if hasattr(e, "response"):
                error_code = e.response.get("Error", {}).get("Code", error_code)
                error_message = e.response.get("Error", {}).get("Message", error_message)

            logger.exception(f"SES send error: {error_message}")
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                provider=self.provider_name,
                error_message=error_message,
                error_code=error_code,
            )

    def send_batch(self, messages: List[EmailMessage]) -> List[DeliveryResult]:
        """
        Send multiple emails.

        Note: SES has send_bulk_templated_email for templates.
        For non-template emails, we send individually.
        """
        results = []
        for message in messages:
            result = self.send(message)
            results.append(result)
        return results

    def verify_email_identity(self, email: str) -> bool:
        """
        Request verification for an email address.

        SES requires sender addresses to be verified.

        Args:
            email: Email address to verify

        Returns:
            True if verification request was sent
        """
        try:
            client = self._get_client()
            client.verify_email_identity(EmailAddress=email)
            logger.info(f"SES: Verification email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"SES verify error: {e}")
            return False
