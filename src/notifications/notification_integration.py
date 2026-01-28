"""
Notification Service Integration

SPEC-012 Critical Gap Fix: Connects notification services to email providers.

This module provides the integration layer between:
- State-based notifications (tax return workflow)
- Lead magnet notifications
- Email delivery providers (SendGrid, SES, SMTP)

Usage:
    from notifications.notification_integration import (
        setup_notification_delivery,
        NotificationDeliveryService,
    )

    # Setup email delivery for all notifications
    setup_notification_delivery()

    # Or use the service directly
    service = NotificationDeliveryService()
    service.send_notification(notification_event)
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Callable

from .email_provider import (
    get_email_provider,
    EmailMessage,
    DeliveryResult,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)


class NotificationDeliveryService:
    """
    Unified notification delivery service.

    Handles email delivery for all notification types using
    the configured email provider.
    """

    def __init__(self):
        """Initialize delivery service."""
        self._provider = None
        self._delivery_log = []

    @property
    def provider(self):
        """Lazy-load email provider."""
        if self._provider is None:
            self._provider = get_email_provider()
        return self._provider

    def send_workflow_notification(
        self,
        recipient_email: str,
        recipient_name: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        notification_type: str = "workflow",
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeliveryResult:
        """
        Send a workflow notification (tax return state changes).

        Args:
            recipient_email: Recipient email address
            recipient_name: Recipient name
            subject: Email subject
            body_text: Plain text body
            body_html: HTML body (optional)
            notification_type: Type of notification
            session_id: Related session ID
            tenant_id: Tenant context
            metadata: Additional metadata

        Returns:
            DeliveryResult with delivery status
        """
        message = EmailMessage(
            to=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            tags=[f"notification:{notification_type}", f"session:{session_id}"] if session_id else [],
            metadata={
                "notification_type": notification_type,
                "recipient_name": recipient_name,
                "session_id": session_id,
                "tenant_id": tenant_id,
                **(metadata or {}),
            },
        )

        result = self.provider.send(message)

        # Log delivery attempt
        self._log_delivery(
            notification_type=notification_type,
            recipient=recipient_email,
            subject=subject,
            result=result,
            session_id=session_id,
            tenant_id=tenant_id,
        )

        return result

    def send_lead_notification(
        self,
        notification_type: str,
        recipient_email: str,
        recipient_name: Optional[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> DeliveryResult:
        """
        Send a lead magnet notification.

        Args:
            notification_type: Type (new_lead, hot_lead, report_ready, etc.)
            recipient_email: Recipient email
            recipient_name: Recipient name
            subject: Email subject
            body: Plain text body
            html_body: HTML body
            data: Additional notification data

        Returns:
            DeliveryResult with delivery status
        """
        message = EmailMessage(
            to=recipient_email,
            subject=subject,
            body_text=body,
            body_html=html_body,
            tags=[f"lead:{notification_type}"],
            metadata={
                "notification_type": notification_type,
                "recipient_name": recipient_name,
                **(data or {}),
            },
        )

        result = self.provider.send(message)

        # Log delivery
        self._log_delivery(
            notification_type=f"lead_{notification_type}",
            recipient=recipient_email,
            subject=subject,
            result=result,
        )

        return result

    def send_cpa_assignment_notification(
        self,
        cpa_email: str,
        cpa_name: str,
        client_name: str,
        tax_year: int,
        session_id: str,
        complexity_tier: str,
        tenant_id: Optional[str] = None,
    ) -> DeliveryResult:
        """
        Send CPA assignment notification (missing feature identified in audit).

        Args:
            cpa_email: CPA email address
            cpa_name: CPA name
            client_name: Client name
            tax_year: Tax year
            session_id: Session ID
            complexity_tier: Return complexity tier
            tenant_id: Tenant context

        Returns:
            DeliveryResult
        """
        subject = f"New Client Assignment: {client_name} ({tax_year})"

        body_text = f"""
Hello {cpa_name},

You have been assigned a new tax return for review.

Client: {client_name}
Tax Year: {tax_year}
Complexity: {complexity_tier}
Session ID: {session_id}

Please log in to your CPA dashboard to begin the review.

Thank you,
Tax Filing Platform
        """.strip()

        body_html = f"""
<p>Hello {cpa_name},</p>

<p>You have been assigned a new tax return for review.</p>

<table style="border-collapse: collapse; margin: 20px 0; border: 1px solid #ddd;">
    <tr>
        <td style="padding: 8px 16px; background: #f9fafb; font-weight: bold;">Client</td>
        <td style="padding: 8px 16px;">{client_name}</td>
    </tr>
    <tr>
        <td style="padding: 8px 16px; background: #f9fafb; font-weight: bold;">Tax Year</td>
        <td style="padding: 8px 16px;">{tax_year}</td>
    </tr>
    <tr>
        <td style="padding: 8px 16px; background: #f9fafb; font-weight: bold;">Complexity</td>
        <td style="padding: 8px 16px;">{complexity_tier}</td>
    </tr>
    <tr>
        <td style="padding: 8px 16px; background: #f9fafb; font-weight: bold;">Session ID</td>
        <td style="padding: 8px 16px; font-family: monospace;">{session_id}</td>
    </tr>
</table>

<p>Please log in to your CPA dashboard to begin the review.</p>

<p>Thank you,<br>Tax Filing Platform</p>
        """

        return self.send_workflow_notification(
            recipient_email=cpa_email,
            recipient_name=cpa_name,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            notification_type="cpa_assignment",
            session_id=session_id,
            tenant_id=tenant_id,
            metadata={
                "client_name": client_name,
                "tax_year": tax_year,
                "complexity_tier": complexity_tier,
            },
        )

    def _log_delivery(
        self,
        notification_type: str,
        recipient: str,
        subject: str,
        result: DeliveryResult,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        """Log delivery attempt for tracking."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": notification_type,
            "recipient": recipient,
            "subject": subject,
            "success": result.success,
            "status": result.status.value,
            "message_id": result.message_id,
            "provider": result.provider,
            "error": result.error_message,
            "session_id": session_id,
            "tenant_id": tenant_id,
        }

        self._delivery_log.append(log_entry)

        # Keep last 1000 entries
        if len(self._delivery_log) > 1000:
            self._delivery_log = self._delivery_log[-1000:]

        # Log to standard logger
        if result.success:
            logger.info(
                f"Email delivered: {notification_type} to {recipient} "
                f"[{result.provider}:{result.message_id}]"
            )
        else:
            logger.error(
                f"Email delivery failed: {notification_type} to {recipient} "
                f"[{result.provider}:{result.error_code}] {result.error_message}"
            )

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get delivery statistics."""
        if not self._delivery_log:
            return {"total": 0, "success": 0, "failed": 0, "success_rate": 0.0}

        total = len(self._delivery_log)
        success = sum(1 for e in self._delivery_log if e["success"])
        failed = total - success

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": round(success / total * 100, 2) if total > 0 else 0.0,
            "by_type": self._count_by_type(),
        }

    def _count_by_type(self) -> Dict[str, int]:
        """Count deliveries by notification type."""
        counts = {}
        for entry in self._delivery_log:
            ntype = entry.get("notification_type", "unknown")
            counts[ntype] = counts.get(ntype, 0) + 1
        return counts


# Global delivery service instance
_delivery_service: Optional[NotificationDeliveryService] = None


def get_delivery_service() -> NotificationDeliveryService:
    """Get the global notification delivery service."""
    global _delivery_service
    if _delivery_service is None:
        _delivery_service = NotificationDeliveryService()
    return _delivery_service


def create_notification_callback() -> Callable:
    """
    Create a callback function for the state-based notification service.

    Returns:
        Callback function compatible with NotificationService.register_send_callback()
    """
    service = get_delivery_service()

    def send_callback(event) -> bool:
        """
        Send callback for NotificationEvent objects.

        Args:
            event: NotificationEvent from state-based notification service

        Returns:
            True if sent successfully
        """
        try:
            result = service.send_workflow_notification(
                recipient_email=event.recipient_email,
                recipient_name=event.recipient_name,
                subject=event.subject,
                body_text=event.body_text,
                body_html=event.body_html,
                notification_type=event.trigger.value if hasattr(event, 'trigger') else "workflow",
                session_id=event.session_id,
                tenant_id=event.tenant_id,
            )
            return result.success
        except Exception as e:
            logger.exception(f"Notification callback error: {e}")
            return False

    return send_callback


def setup_notification_delivery():
    """
    Setup email delivery for all notification services.

    This function registers the email delivery callback with
    the state-based notification service.

    Should be called during application startup.
    """
    try:
        # Register callback with state-based notification service
        from cpa_panel.notifications.notification_service import NotificationService

        callback = create_notification_callback()
        notification_service = NotificationService()
        notification_service.register_send_callback(callback)

        logger.info("Notification delivery setup complete")

    except ImportError as e:
        logger.warning(f"Could not setup notification delivery: {e}")
    except Exception as e:
        logger.exception(f"Error setting up notification delivery: {e}")
