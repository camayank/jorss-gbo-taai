"""
Webhook Events

Defines all webhook event types and provides the emit_webhook_event function
for triggering webhooks from application code.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


class WebhookEventType(str, Enum):
    """
    All supported webhook event types.

    Naming convention: {resource}.{action}
    """
    # Client Events
    CLIENT_CREATED = "client.created"
    CLIENT_UPDATED = "client.updated"
    CLIENT_DELETED = "client.deleted"
    CLIENT_ARCHIVED = "client.archived"

    # Tax Return Events
    RETURN_CREATED = "return.created"
    RETURN_UPDATED = "return.updated"
    RETURN_STATUS_CHANGED = "return.status_changed"
    RETURN_SUBMITTED = "return.submitted"
    RETURN_ACCEPTED = "return.accepted"
    RETURN_REJECTED = "return.rejected"
    RETURN_AMENDED = "return.amended"

    # Document Events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_DELETED = "document.deleted"

    # Engagement Letter Events
    ENGAGEMENT_CREATED = "engagement.created"
    ENGAGEMENT_SENT = "engagement.sent"
    ENGAGEMENT_VIEWED = "engagement.viewed"
    ENGAGEMENT_SIGNED = "engagement.signed"
    ENGAGEMENT_DECLINED = "engagement.declined"

    # Tax Scenario Events
    SCENARIO_CREATED = "scenario.created"
    SCENARIO_COMPLETED = "scenario.completed"
    SCENARIO_COMPARED = "scenario.compared"

    # Advisory Events
    RECOMMENDATION_GENERATED = "recommendation.generated"
    REPORT_GENERATED = "report.generated"

    # User Events (firm-level)
    USER_INVITED = "user.invited"
    USER_JOINED = "user.joined"
    USER_DEACTIVATED = "user.deactivated"

    # Billing Events
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"


# Event groupings for easy subscription
CLIENT_EVENTS = [
    WebhookEventType.CLIENT_CREATED.value,
    WebhookEventType.CLIENT_UPDATED.value,
    WebhookEventType.CLIENT_DELETED.value,
    WebhookEventType.CLIENT_ARCHIVED.value,
]

RETURN_EVENTS = [
    WebhookEventType.RETURN_CREATED.value,
    WebhookEventType.RETURN_UPDATED.value,
    WebhookEventType.RETURN_STATUS_CHANGED.value,
    WebhookEventType.RETURN_SUBMITTED.value,
    WebhookEventType.RETURN_ACCEPTED.value,
    WebhookEventType.RETURN_REJECTED.value,
    WebhookEventType.RETURN_AMENDED.value,
]

DOCUMENT_EVENTS = [
    WebhookEventType.DOCUMENT_UPLOADED.value,
    WebhookEventType.DOCUMENT_PROCESSED.value,
    WebhookEventType.DOCUMENT_DELETED.value,
]

ENGAGEMENT_EVENTS = [
    WebhookEventType.ENGAGEMENT_CREATED.value,
    WebhookEventType.ENGAGEMENT_SENT.value,
    WebhookEventType.ENGAGEMENT_VIEWED.value,
    WebhookEventType.ENGAGEMENT_SIGNED.value,
    WebhookEventType.ENGAGEMENT_DECLINED.value,
]

SCENARIO_EVENTS = [
    WebhookEventType.SCENARIO_CREATED.value,
    WebhookEventType.SCENARIO_COMPLETED.value,
    WebhookEventType.SCENARIO_COMPARED.value,
]

ADVISORY_EVENTS = [
    WebhookEventType.RECOMMENDATION_GENERATED.value,
    WebhookEventType.REPORT_GENERATED.value,
]

USER_EVENTS = [
    WebhookEventType.USER_INVITED.value,
    WebhookEventType.USER_JOINED.value,
    WebhookEventType.USER_DEACTIVATED.value,
]

BILLING_EVENTS = [
    WebhookEventType.SUBSCRIPTION_CREATED.value,
    WebhookEventType.SUBSCRIPTION_UPDATED.value,
    WebhookEventType.SUBSCRIPTION_CANCELLED.value,
    WebhookEventType.PAYMENT_SUCCEEDED.value,
    WebhookEventType.PAYMENT_FAILED.value,
]

ALL_EVENTS = (
    CLIENT_EVENTS +
    RETURN_EVENTS +
    DOCUMENT_EVENTS +
    ENGAGEMENT_EVENTS +
    SCENARIO_EVENTS +
    ADVISORY_EVENTS +
    USER_EVENTS +
    BILLING_EVENTS
)


def emit_webhook_event(
    event_type: WebhookEventType,
    firm_id: str,
    data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    async_delivery: bool = True,
) -> Optional[str]:
    """
    Emit a webhook event for delivery to registered endpoints.

    This is the primary function to call from application code when
    an event occurs that should trigger webhooks.

    Args:
        event_type: Type of event (from WebhookEventType enum)
        firm_id: ID of the firm this event belongs to
        data: Event payload data (will be included in webhook body)
        metadata: Optional metadata about the event
        async_delivery: If True, queue for async delivery. If False, deliver synchronously.

    Returns:
        Event ID string if queued successfully, None if failed

    Example:
        emit_webhook_event(
            event_type=WebhookEventType.CLIENT_CREATED,
            firm_id="abc-123",
            data={
                "client_id": "client-456",
                "name": "John Smith",
                "email": "john@example.com",
            }
        )
    """
    from webhooks.models import WebhookEvent

    event_id = str(uuid4())
    timestamp = datetime.utcnow()

    event = WebhookEvent(
        event_id=event_id,
        event_type=event_type.value if isinstance(event_type, WebhookEventType) else event_type,
        timestamp=timestamp,
        firm_id=str(firm_id),
        data=data,
        metadata=metadata or {},
    )

    logger.info(
        f"[WEBHOOK] Event emitted | type={event.event_type} | "
        f"firm={event.firm_id} | event_id={event_id}"
    )

    try:
        from webhooks.service import get_webhook_service

        service = get_webhook_service()

        if async_delivery:
            # Queue for background delivery
            service.queue_event(event)
        else:
            # Deliver immediately (blocking)
            service.deliver_event(event)

        return event_id

    except Exception as e:
        logger.error(f"[WEBHOOK] Failed to emit event: {e}")
        return None


def get_event_schema(event_type: str) -> Dict[str, Any]:
    """
    Get the expected payload schema for an event type.

    Useful for documentation and validation.
    """
    schemas = {
        WebhookEventType.CLIENT_CREATED.value: {
            "client_id": "string (required)",
            "name": "string (required)",
            "email": "string (optional)",
            "phone": "string (optional)",
            "created_at": "ISO 8601 timestamp",
        },
        WebhookEventType.RETURN_CREATED.value: {
            "return_id": "string (required)",
            "client_id": "string (required)",
            "tax_year": "integer (required)",
            "filing_status": "string (required)",
            "status": "string (required)",
            "created_at": "ISO 8601 timestamp",
        },
        WebhookEventType.RETURN_STATUS_CHANGED.value: {
            "return_id": "string (required)",
            "previous_status": "string (required)",
            "new_status": "string (required)",
            "changed_by": "string (optional)",
            "changed_at": "ISO 8601 timestamp",
        },
        WebhookEventType.DOCUMENT_UPLOADED.value: {
            "document_id": "string (required)",
            "client_id": "string (optional)",
            "return_id": "string (optional)",
            "filename": "string (required)",
            "file_type": "string (required)",
            "file_size": "integer (bytes)",
            "uploaded_at": "ISO 8601 timestamp",
        },
        WebhookEventType.ENGAGEMENT_SIGNED.value: {
            "engagement_id": "string (required)",
            "client_id": "string (required)",
            "signed_by": "string (required)",
            "signed_at": "ISO 8601 timestamp",
            "ip_address": "string (optional)",
        },
    }

    return schemas.get(event_type, {"data": "Event-specific payload"})
