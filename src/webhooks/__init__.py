"""
Webhooks Module

Provides real-time event notifications for external integrations.
Available to ENTERPRISE and WHITE_LABEL tier subscribers.

Features:
- Webhook endpoint registration with event filtering
- Secure delivery with HMAC-SHA256 signatures
- Automatic retry with exponential backoff
- Delivery logging and monitoring

Events:
- client.created, client.updated, client.deleted
- return.created, return.status_changed, return.submitted, return.accepted, return.rejected
- document.uploaded, document.processed
- engagement.created, engagement.signed
- scenario.created, scenario.completed
- recommendation.generated
"""

from .models import WebhookEndpoint, WebhookDelivery, WebhookEvent
from .service import WebhookService, get_webhook_service
from .events import (
    WebhookEventType,
    emit_webhook_event,
    CLIENT_EVENTS,
    RETURN_EVENTS,
    DOCUMENT_EVENTS,
    ENGAGEMENT_EVENTS,
    SCENARIO_EVENTS,
    ALL_EVENTS,
)

__all__ = [
    # Models
    "WebhookEndpoint",
    "WebhookDelivery",
    "WebhookEvent",
    # Service
    "WebhookService",
    "get_webhook_service",
    # Events
    "WebhookEventType",
    "emit_webhook_event",
    "CLIENT_EVENTS",
    "RETURN_EVENTS",
    "DOCUMENT_EVENTS",
    "ENGAGEMENT_EVENTS",
    "SCENARIO_EVENTS",
    "ALL_EVENTS",
]
