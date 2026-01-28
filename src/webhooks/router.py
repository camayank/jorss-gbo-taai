"""
Webhook API Endpoints

REST API for webhook management:
- Register/update/delete webhook endpoints
- View delivery history
- Rotate secrets
- Test webhook delivery
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel, HttpUrl, Field
import logging

from rbac.feature_access_control import require_feature, Features
from security.auth_decorators import require_auth, Role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# =============================================================================
# SCHEMAS
# =============================================================================

class WebhookEndpointCreate(BaseModel):
    """Schema for creating a webhook endpoint."""
    name: str = Field(..., min_length=1, max_length=100, description="Display name for the endpoint")
    url: HttpUrl = Field(..., description="HTTPS URL to receive webhooks")
    events: Optional[List[str]] = Field(default=None, description="Event types to subscribe to (null = all)")
    custom_headers: Optional[dict] = Field(default=None, description="Custom headers to include")
    max_retries: int = Field(default=5, ge=0, le=10, description="Maximum retry attempts")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Production Webhook",
                "url": "https://api.example.com/webhooks/tax-platform",
                "events": ["client.created", "return.submitted", "return.accepted"],
                "max_retries": 5
            }
        }


class WebhookEndpointUpdate(BaseModel):
    """Schema for updating a webhook endpoint."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    status: Optional[str] = Field(None, pattern="^(active|paused|disabled)$")
    custom_headers: Optional[dict] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)


class WebhookEndpointResponse(BaseModel):
    """Schema for webhook endpoint response."""
    endpoint_id: str
    name: str
    url: str
    events: List[str]
    status: str
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    last_triggered_at: Optional[str]
    created_at: str


class WebhookEndpointDetail(WebhookEndpointResponse):
    """Detailed webhook endpoint response including settings."""
    custom_headers: Optional[dict]
    max_retries: int
    rate_limit_per_minute: int
    updated_at: Optional[str]


class WebhookEndpointCreateResponse(BaseModel):
    """Response after creating a webhook endpoint."""
    endpoint_id: str
    secret: str
    name: str
    url: str
    events: List[str]
    status: str
    message: str = "Webhook endpoint created successfully. Save the secret - it won't be shown again."


class WebhookSecretRotateResponse(BaseModel):
    """Response after rotating webhook secret."""
    endpoint_id: str
    new_secret: str
    message: str = "Secret rotated successfully. Update your webhook receiver with the new secret."


class WebhookDeliveryResponse(BaseModel):
    """Schema for webhook delivery record."""
    delivery_id: str
    event_id: str
    event_type: str
    status: str
    response_status_code: Optional[int]
    attempt_number: int
    duration_ms: Optional[int]
    error_message: Optional[str]
    created_at: str
    delivered_at: Optional[str]


class WebhookDeliveryDetail(WebhookDeliveryResponse):
    """Detailed webhook delivery including request/response."""
    endpoint_id: str
    request_url: str
    request_headers: dict
    request_body: Optional[str]
    response_headers: Optional[dict]
    response_body: Optional[str]
    next_retry_at: Optional[str]
    error_code: Optional[str]


class WebhookTestRequest(BaseModel):
    """Schema for testing a webhook endpoint."""
    event_type: str = Field(default="test.ping", description="Event type to send")
    data: Optional[dict] = Field(default=None, description="Custom payload data")


class EventTypeInfo(BaseModel):
    """Information about a webhook event type."""
    event_type: str
    description: str
    category: str


# =============================================================================
# HELPERS
# =============================================================================

def get_firm_id_from_request(request: Request) -> str:
    """Extract firm_id from authenticated request."""
    # In a real implementation, this would come from the JWT/session
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "firm_id"):
        return str(user.firm_id)
    # For demo/testing
    return request.headers.get("X-Firm-ID", "demo-firm")


def get_user_id_from_request(request: Request) -> Optional[str]:
    """Extract user_id from authenticated request."""
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "user_id"):
        return str(user.user_id)
    return None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "",
    response_model=WebhookEndpointCreateResponse,
    summary="Register Webhook Endpoint",
    description="Register a new webhook endpoint to receive event notifications."
)
@require_feature(Features.WEBHOOKS)
async def create_webhook_endpoint(
    request: Request,
    endpoint_data: WebhookEndpointCreate,
):
    """
    Register a new webhook endpoint.

    The response includes a `secret` that will be used to sign all webhook
    payloads. **Save this secret securely - it will not be shown again.**

    To verify webhooks, check the `X-Webhook-Signature` header using HMAC-SHA256
    with the secret as the key and the raw request body as the message.
    """
    from webhooks.service import get_webhook_service

    firm_id = get_firm_id_from_request(request)
    user_id = get_user_id_from_request(request)

    service = get_webhook_service()

    try:
        result = service.register_endpoint(
            firm_id=firm_id,
            name=endpoint_data.name,
            url=str(endpoint_data.url),
            events=endpoint_data.events,
            created_by=user_id,
            custom_headers=endpoint_data.custom_headers,
            max_retries=endpoint_data.max_retries,
        )

        logger.info(f"[WEBHOOK API] Endpoint created | firm={firm_id} | endpoint={result['endpoint_id']}")

        return WebhookEndpointCreateResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[WEBHOOK API] Create endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create webhook endpoint")


@router.get(
    "",
    response_model=List[WebhookEndpointResponse],
    summary="List Webhook Endpoints",
    description="List all webhook endpoints for your firm."
)
@require_feature(Features.WEBHOOKS)
async def list_webhook_endpoints(request: Request):
    """List all webhook endpoints for the authenticated firm."""
    from webhooks.service import get_webhook_service

    firm_id = get_firm_id_from_request(request)
    service = get_webhook_service()

    endpoints = service.list_endpoints(firm_id)
    return endpoints


@router.get(
    "/events",
    response_model=List[EventTypeInfo],
    summary="List Available Event Types",
    description="Get a list of all available webhook event types."
)
async def list_event_types():
    """
    List all available webhook event types.

    Use these event types when registering a webhook endpoint
    to filter which events you want to receive.
    """
    from webhooks.events import (
        CLIENT_EVENTS, RETURN_EVENTS, DOCUMENT_EVENTS,
        ENGAGEMENT_EVENTS, SCENARIO_EVENTS, ADVISORY_EVENTS,
        USER_EVENTS, BILLING_EVENTS
    )

    events = []

    event_descriptions = {
        "client.created": "Fired when a new client is added",
        "client.updated": "Fired when client information is updated",
        "client.deleted": "Fired when a client is deleted",
        "client.archived": "Fired when a client is archived",
        "return.created": "Fired when a new tax return is created",
        "return.updated": "Fired when a tax return is updated",
        "return.status_changed": "Fired when return status changes",
        "return.submitted": "Fired when a return is submitted for filing",
        "return.accepted": "Fired when IRS accepts a return",
        "return.rejected": "Fired when IRS rejects a return",
        "return.amended": "Fired when an amended return is filed",
        "document.uploaded": "Fired when a document is uploaded",
        "document.processed": "Fired when document processing completes",
        "document.deleted": "Fired when a document is deleted",
        "engagement.created": "Fired when an engagement letter is created",
        "engagement.sent": "Fired when an engagement letter is sent",
        "engagement.viewed": "Fired when client views engagement letter",
        "engagement.signed": "Fired when client signs engagement letter",
        "engagement.declined": "Fired when client declines engagement letter",
        "scenario.created": "Fired when a tax scenario is created",
        "scenario.completed": "Fired when scenario analysis completes",
        "scenario.compared": "Fired when scenarios are compared",
        "recommendation.generated": "Fired when advisory recommendations are generated",
        "report.generated": "Fired when a report is generated",
        "user.invited": "Fired when a team member is invited",
        "user.joined": "Fired when an invited user accepts",
        "user.deactivated": "Fired when a user is deactivated",
        "subscription.created": "Fired when a subscription is created",
        "subscription.updated": "Fired when a subscription is updated",
        "subscription.cancelled": "Fired when a subscription is cancelled",
        "payment.succeeded": "Fired when a payment succeeds",
        "payment.failed": "Fired when a payment fails",
    }

    categories = {
        "client": CLIENT_EVENTS,
        "return": RETURN_EVENTS,
        "document": DOCUMENT_EVENTS,
        "engagement": ENGAGEMENT_EVENTS,
        "scenario": SCENARIO_EVENTS,
        "advisory": ADVISORY_EVENTS,
        "user": USER_EVENTS,
        "billing": BILLING_EVENTS,
    }

    for category, event_list in categories.items():
        for event_type in event_list:
            events.append(EventTypeInfo(
                event_type=event_type,
                description=event_descriptions.get(event_type, ""),
                category=category,
            ))

    return events


@router.get(
    "/{endpoint_id}",
    response_model=WebhookEndpointDetail,
    summary="Get Webhook Endpoint",
    description="Get details of a specific webhook endpoint."
)
@require_feature(Features.WEBHOOKS)
async def get_webhook_endpoint(
    request: Request,
    endpoint_id: str,
):
    """Get detailed information about a webhook endpoint."""
    from webhooks.service import get_webhook_service

    firm_id = get_firm_id_from_request(request)
    service = get_webhook_service()

    endpoint = service.get_endpoint(endpoint_id, firm_id)

    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    return endpoint


@router.patch(
    "/{endpoint_id}",
    response_model=WebhookEndpointDetail,
    summary="Update Webhook Endpoint",
    description="Update a webhook endpoint's configuration."
)
@require_feature(Features.WEBHOOKS)
async def update_webhook_endpoint(
    request: Request,
    endpoint_id: str,
    updates: WebhookEndpointUpdate,
):
    """Update a webhook endpoint."""
    from webhooks.service import get_webhook_service

    firm_id = get_firm_id_from_request(request)
    service = get_webhook_service()

    # Convert URL to string if present
    update_dict = updates.dict(exclude_unset=True)
    if "url" in update_dict and update_dict["url"]:
        update_dict["url"] = str(update_dict["url"])

    success = service.update_endpoint(endpoint_id, firm_id, update_dict)

    if not success:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    # Return updated endpoint
    endpoint = service.get_endpoint(endpoint_id, firm_id)
    return endpoint


@router.delete(
    "/{endpoint_id}",
    summary="Delete Webhook Endpoint",
    description="Delete a webhook endpoint and all its delivery history."
)
@require_feature(Features.WEBHOOKS)
async def delete_webhook_endpoint(
    request: Request,
    endpoint_id: str,
):
    """Delete a webhook endpoint."""
    from webhooks.service import get_webhook_service

    firm_id = get_firm_id_from_request(request)
    service = get_webhook_service()

    success = service.delete_endpoint(endpoint_id, firm_id)

    if not success:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    logger.info(f"[WEBHOOK API] Endpoint deleted | firm={firm_id} | endpoint={endpoint_id}")

    return {"message": "Webhook endpoint deleted successfully"}


@router.post(
    "/{endpoint_id}/rotate-secret",
    response_model=WebhookSecretRotateResponse,
    summary="Rotate Webhook Secret",
    description="Generate a new signing secret for the webhook endpoint."
)
@require_feature(Features.WEBHOOKS)
async def rotate_webhook_secret(
    request: Request,
    endpoint_id: str,
):
    """
    Rotate the signing secret for a webhook endpoint.

    The old secret will immediately stop working. Make sure to update
    your webhook receiver with the new secret before it receives any events.
    """
    from webhooks.service import get_webhook_service

    firm_id = get_firm_id_from_request(request)
    service = get_webhook_service()

    new_secret = service.rotate_secret(endpoint_id, firm_id)

    if not new_secret:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    logger.info(f"[WEBHOOK API] Secret rotated | firm={firm_id} | endpoint={endpoint_id}")

    return WebhookSecretRotateResponse(
        endpoint_id=endpoint_id,
        new_secret=new_secret,
    )


@router.post(
    "/{endpoint_id}/test",
    summary="Test Webhook Endpoint",
    description="Send a test event to verify the webhook endpoint is working."
)
@require_feature(Features.WEBHOOKS)
async def test_webhook_endpoint(
    request: Request,
    endpoint_id: str,
    test_data: Optional[WebhookTestRequest] = None,
):
    """
    Send a test event to verify the webhook endpoint configuration.

    This will send a `test.ping` event (or custom event type if specified)
    to the webhook URL and return the delivery result.
    """
    from webhooks.service import get_webhook_service
    from webhooks.models import WebhookEvent
    from datetime import datetime
    from uuid import uuid4

    firm_id = get_firm_id_from_request(request)
    service = get_webhook_service()

    # Verify endpoint exists
    endpoint = service.get_endpoint(endpoint_id, firm_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    # Create test event
    event_type = test_data.event_type if test_data else "test.ping"
    test_payload = test_data.data if test_data and test_data.data else {
        "message": "This is a test webhook from the Tax Platform",
        "endpoint_id": endpoint_id,
        "timestamp": datetime.utcnow().isoformat(),
    }

    event = WebhookEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        timestamp=datetime.utcnow(),
        firm_id=firm_id,
        data=test_payload,
        metadata={"test": True},
    )

    # Deliver synchronously
    results = service.deliver_event(event)

    result = results.get(endpoint_id, {"success": False, "error": "Delivery failed"})

    if result.get("success"):
        return {
            "success": True,
            "message": "Test webhook delivered successfully",
            "status_code": result.get("status_code"),
            "duration_ms": result.get("duration_ms"),
        }
    else:
        return {
            "success": False,
            "message": "Test webhook delivery failed",
            "error": result.get("error"),
        }


@router.get(
    "/{endpoint_id}/deliveries",
    response_model=List[WebhookDeliveryResponse],
    summary="Get Delivery History",
    description="Get the delivery history for a webhook endpoint."
)
@require_feature(Features.WEBHOOKS)
async def get_delivery_history(
    request: Request,
    endpoint_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Get delivery history for a webhook endpoint."""
    from webhooks.service import get_webhook_service

    firm_id = get_firm_id_from_request(request)
    service = get_webhook_service()

    deliveries = service.get_delivery_history(
        endpoint_id=endpoint_id,
        firm_id=firm_id,
        limit=limit,
        offset=offset,
    )

    return deliveries


@router.get(
    "/{endpoint_id}/deliveries/{delivery_id}",
    response_model=WebhookDeliveryDetail,
    summary="Get Delivery Details",
    description="Get detailed information about a specific webhook delivery."
)
@require_feature(Features.WEBHOOKS)
async def get_delivery_detail(
    request: Request,
    endpoint_id: str,
    delivery_id: str,
):
    """Get detailed information about a webhook delivery attempt."""
    from webhooks.service import get_webhook_service

    firm_id = get_firm_id_from_request(request)
    service = get_webhook_service()

    delivery = service.get_delivery_detail(delivery_id, firm_id)

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if delivery["endpoint_id"] != endpoint_id:
        raise HTTPException(status_code=404, detail="Delivery not found for this endpoint")

    return delivery


@router.post(
    "/{endpoint_id}/deliveries/{delivery_id}/retry",
    summary="Retry Delivery",
    description="Manually retry a failed webhook delivery."
)
@require_feature(Features.WEBHOOKS)
async def retry_delivery(
    request: Request,
    endpoint_id: str,
    delivery_id: str,
):
    """Manually retry a failed webhook delivery."""
    from webhooks.service import get_webhook_service

    firm_id = get_firm_id_from_request(request)
    service = get_webhook_service()

    # Verify delivery belongs to endpoint
    delivery = service.get_delivery_detail(delivery_id, firm_id)
    if not delivery or delivery["endpoint_id"] != endpoint_id:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if delivery["status"] == "delivered":
        raise HTTPException(status_code=400, detail="Delivery already succeeded")

    success = service.retry_delivery(delivery_id, firm_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to queue retry")

    logger.info(f"[WEBHOOK API] Manual retry queued | delivery={delivery_id}")

    return {"message": "Retry queued successfully"}
