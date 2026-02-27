"""
Email Service - Transactional Email Support

Provides email delivery for:
- Password reset links
- Magic link login
- Email verification
- Welcome emails
- Notifications

Supports multiple backends:
- SMTP (Gmail, SendGrid, etc.)
- Mock (development/testing)
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from datetime import datetime
from abc import ABC, abstractmethod

from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class EmailConfig:
    """Email service configuration."""

    # SMTP Settings
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    # Sender Settings
    FROM_EMAIL = os.environ.get("EMAIL_FROM", "noreply@taxadvisor.com")
    FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Tax Advisor")

    # App Settings
    APP_URL = os.environ.get("APP_URL", "http://localhost:8000")
    APP_NAME = os.environ.get("APP_NAME", "Tax Advisor")

    # Mode (smtp, mock, auto)
    # SECURITY: In production, defaults to 'smtp' if configured, 'mock' otherwise with warning
    _EMAIL_MODE_RAW = os.environ.get("EMAIL_MODE", "auto")

    @classmethod
    def is_smtp_configured(cls) -> bool:
        """Check if SMTP is configured."""
        return bool(cls.SMTP_USERNAME and cls.SMTP_PASSWORD)

    @classmethod
    def get_email_mode(cls) -> str:
        """
        Get email mode with safe defaults.

        - If EMAIL_MODE is explicitly set, use that
        - If 'auto' (default): use 'smtp' if configured, 'mock' with warning otherwise
        """
        if cls._EMAIL_MODE_RAW != "auto":
            return cls._EMAIL_MODE_RAW

        # Auto-detect mode
        if cls.is_smtp_configured():
            return "smtp"

        # SECURITY: Warn in production if emails will be mocked
        env = os.environ.get("APP_ENVIRONMENT", "development")
        if env.lower() in ("production", "prod", "staging"):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "[SECURITY] EMAIL_MODE not set and SMTP not configured. "
                "Emails will be MOCKED in production! Set EMAIL_MODE=smtp and configure SMTP."
            )
        return "mock"

    # For backwards compatibility
    EMAIL_MODE = _EMAIL_MODE_RAW  # Use get_email_mode() for safe access


# =============================================================================
# EMAIL MODELS
# =============================================================================

class EmailMessage(BaseModel):
    """Email message model."""
    to: str
    subject: str
    html_body: str
    text_body: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    headers: Dict[str, str] = {}


class EmailResult(BaseModel):
    """Email send result."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# EMAIL BACKENDS
# =============================================================================

class EmailBackend(ABC):
    """Abstract email backend."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> EmailResult:
        """Send an email message."""
        pass


class MockEmailBackend(EmailBackend):
    """Mock email backend for development/testing."""

    def __init__(self):
        self.sent_emails: List[EmailMessage] = []

    async def send(self, message: EmailMessage) -> EmailResult:
        """Log email instead of sending."""
        self.sent_emails.append(message)
        message_id = f"mock-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        logger.info(f"[MOCK EMAIL] To: {message.to}")
        logger.info(f"[MOCK EMAIL] Subject: {message.subject}")
        logger.info(f"[MOCK EMAIL] Body preview: {message.text_body[:100] if message.text_body else message.html_body[:100]}...")

        return EmailResult(
            success=True,
            message_id=message_id
        )


class SMTPEmailBackend(EmailBackend):
    """SMTP email backend."""

    def __init__(self, config: EmailConfig = None):
        self.config = config or EmailConfig()

    # SECURITY FIX: Add timeout for SMTP connections
    # Email sends should complete within 30 seconds
    SMTP_TIMEOUT = 30

    async def send(self, message: EmailMessage) -> EmailResult:
        """Send email via SMTP with timeout and error handling."""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = f"{message.from_name or self.config.FROM_NAME} <{message.from_email or self.config.FROM_EMAIL}>"
            msg["To"] = message.to

            if message.reply_to:
                msg["Reply-To"] = message.reply_to

            # Add custom headers (sanitize against CRLF injection)
            for key, value in message.headers.items():
                if any(c in str(key) + str(value) for c in ('\r', '\n')):
                    logger.warning(f"Rejected email header with CRLF: {key!r}")
                    continue
                msg[key] = value

            # Add body parts
            if message.text_body:
                msg.attach(MIMEText(message.text_body, "plain"))
            msg.attach(MIMEText(message.html_body, "html"))

            # Send via SMTP with timeout
            with smtplib.SMTP(self.config.SMTP_HOST, self.config.SMTP_PORT, timeout=self.SMTP_TIMEOUT) as server:
                if self.config.SMTP_USE_TLS:
                    server.starttls()
                if self.config.SMTP_USERNAME:
                    server.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
                server.sendmail(
                    message.from_email or self.config.FROM_EMAIL,
                    [message.to],
                    msg.as_string()
                )

            message_id = f"smtp-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            logger.info(f"Email sent to {message.to}: {message.subject}")

            return EmailResult(
                success=True,
                message_id=message_id
            )

        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"SMTP server disconnected while sending to {message.to}: {e}")
            return EmailResult(
                success=False,
                error=f"Email server disconnected: {e}"
            )
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return EmailResult(
                success=False,
                error="Email authentication failed. Check SMTP credentials."
            )
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipients refused for {message.to}: {e}")
            return EmailResult(
                success=False,
                error=f"Recipient refused: {message.to}"
            )
        except TimeoutError as e:
            logger.error(f"SMTP timeout sending to {message.to}: {e}")
            return EmailResult(
                success=False,
                error="Email send timed out. Please try again."
            )
        except Exception as e:
            logger.error(f"Failed to send email to {message.to}: {e}")
            return EmailResult(
                success=False,
                error=str(e)
            )


# =============================================================================
# EMAIL SERVICE
# =============================================================================

class EmailService:
    """
    High-level email service with templated emails.

    Handles:
    - Password reset emails
    - Magic link emails
    - Email verification
    - Welcome emails
    """

    def __init__(self, config: EmailConfig = None):
        self.config = config or EmailConfig()

        # Select backend based on mode (use get_email_mode for safe defaults)
        email_mode = self.config.get_email_mode()
        if email_mode == "smtp" and self.config.is_smtp_configured():
            self._backend = SMTPEmailBackend(self.config)
            logger.info("Email service initialized with SMTP backend")
        else:
            self._backend = MockEmailBackend()
            logger.info(f"Email service initialized with MOCK backend (mode={email_mode})")

    async def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: str = ""
    ) -> EmailResult:
        """Send password reset email."""
        reset_url = f"{self.config.APP_URL}/reset-password?token={reset_token}"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #0c1b2f; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .logo {{ font-size: 24px; font-weight: 700; color: #1e3a5f; }}
        .content {{ background: #f7fafc; border-radius: 12px; padding: 30px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #1e3a5f 0%, #5387c1 100%); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #718096; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">{self.config.APP_NAME}</div>
        </div>
        <div class="content">
            <h2>Reset Your Password</h2>
            <p>Hi{' ' + user_name if user_name else ''},</p>
            <p>We received a request to reset your password. Click the button below to create a new password:</p>
            <p style="text-align: center;">
                <a href="{reset_url}" class="button">Reset Password</a>
            </p>
            <p>This link will expire in 15 minutes for security reasons.</p>
            <p>If you didn't request this, you can safely ignore this email. Your password will remain unchanged.</p>
        </div>
        <div class="footer">
            <p>This is an automated message from {self.config.APP_NAME}.</p>
            <p>If the button doesn't work, copy and paste this link into your browser:</p>
            <p style="word-break: break-all;">{reset_url}</p>
        </div>
    </div>
</body>
</html>
"""

        text_body = f"""
Reset Your Password

Hi{' ' + user_name if user_name else ''},

We received a request to reset your password. Visit the link below to create a new password:

{reset_url}

This link will expire in 15 minutes for security reasons.

If you didn't request this, you can safely ignore this email. Your password will remain unchanged.

---
{self.config.APP_NAME}
"""

        message = EmailMessage(
            to=to_email,
            subject=f"Reset your {self.config.APP_NAME} password",
            html_body=html_body,
            text_body=text_body
        )

        return await self._backend.send(message)

    async def send_magic_link_email(
        self,
        to_email: str,
        magic_token: str,
        user_name: str = ""
    ) -> EmailResult:
        """Send magic link login email."""
        login_url = f"{self.config.APP_URL}/api/core/auth/magic-link/verify?token={magic_token}"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #0c1b2f; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .logo {{ font-size: 24px; font-weight: 700; color: #1e3a5f; }}
        .content {{ background: #f7fafc; border-radius: 12px; padding: 30px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #1e3a5f 0%, #5387c1 100%); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #718096; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">{self.config.APP_NAME}</div>
        </div>
        <div class="content">
            <h2>Sign in to {self.config.APP_NAME}</h2>
            <p>Hi{' ' + user_name if user_name else ''},</p>
            <p>Click the button below to sign in to your account. No password needed!</p>
            <p style="text-align: center;">
                <a href="{login_url}" class="button">Sign In</a>
            </p>
            <p>This link will expire in 15 minutes for security reasons.</p>
            <p>If you didn't request this link, you can safely ignore this email.</p>
        </div>
        <div class="footer">
            <p>This is an automated message from {self.config.APP_NAME}.</p>
        </div>
    </div>
</body>
</html>
"""

        text_body = f"""
Sign in to {self.config.APP_NAME}

Hi{' ' + user_name if user_name else ''},

Click the link below to sign in to your account. No password needed!

{login_url}

This link will expire in 15 minutes for security reasons.

If you didn't request this link, you can safely ignore this email.

---
{self.config.APP_NAME}
"""

        message = EmailMessage(
            to=to_email,
            subject=f"Sign in to {self.config.APP_NAME}",
            html_body=html_body,
            text_body=text_body
        )

        return await self._backend.send(message)

    async def send_welcome_email(
        self,
        to_email: str,
        user_name: str = ""
    ) -> EmailResult:
        """Send welcome email to new users."""
        dashboard_url = f"{self.config.APP_URL}/advisor"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #0c1b2f; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .logo {{ font-size: 24px; font-weight: 700; color: #1e3a5f; }}
        .content {{ background: #f7fafc; border-radius: 12px; padding: 30px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #1e3a5f 0%, #5387c1 100%); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .features {{ margin: 20px 0; }}
        .feature {{ display: flex; align-items: center; margin: 10px 0; }}
        .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #718096; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">{self.config.APP_NAME}</div>
        </div>
        <div class="content">
            <h2>Welcome to {self.config.APP_NAME}!</h2>
            <p>Hi{' ' + user_name if user_name else ''},</p>
            <p>Thank you for joining {self.config.APP_NAME}. We're excited to help you maximize your tax savings!</p>
            <p>Here's what you can do:</p>
            <ul>
                <li>Get personalized tax-saving recommendations</li>
                <li>Chat with our AI tax advisor</li>
                <li>Track your potential savings</li>
                <li>Plan for future tax years</li>
            </ul>
            <p style="text-align: center;">
                <a href="{dashboard_url}" class="button">Get Started</a>
            </p>
        </div>
        <div class="footer">
            <p>Questions? Reply to this email - we're here to help!</p>
            <p>{self.config.APP_NAME}</p>
        </div>
    </div>
</body>
</html>
"""

        text_body = f"""
Welcome to {self.config.APP_NAME}!

Hi{' ' + user_name if user_name else ''},

Thank you for joining {self.config.APP_NAME}. We're excited to help you maximize your tax savings!

Here's what you can do:
- Get personalized tax-saving recommendations
- Chat with our AI tax advisor
- Track your potential savings
- Plan for future tax years

Get started: {dashboard_url}

Questions? Reply to this email - we're here to help!

---
{self.config.APP_NAME}
"""

        message = EmailMessage(
            to=to_email,
            subject=f"Welcome to {self.config.APP_NAME}!",
            html_body=html_body,
            text_body=text_body
        )

        return await self._backend.send(message)


# =============================================================================
# SERVICE SINGLETON
# =============================================================================

_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get the singleton email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
