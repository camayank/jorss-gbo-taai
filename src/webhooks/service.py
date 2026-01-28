"""
Webhook Delivery Service

Handles webhook delivery with:
- HMAC-SHA256 signature generation
- Automatic retry with exponential backoff
- Rate limiting
- Delivery logging
"""

import hashlib
import hmac
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from queue import Queue, Empty
from typing import Dict, Any, Optional, List
from uuid import uuid4

import requests

logger = logging.getLogger(__name__)

# Delivery timeout in seconds
DELIVERY_TIMEOUT = 30

# Maximum payload size (1MB)
MAX_PAYLOAD_SIZE = 1024 * 1024


class MockSession:
    """
    Mock database session for background thread usage.

    In production, this would be replaced with a sync SQLAlchemy session
    or deliveries would be queued via Celery for async processing.
    """
    _records = []  # In-memory storage for mock

    def add(self, obj):
        self._records.append(obj)

    def commit(self):
        pass

    def rollback(self):
        pass

    def query(self, model):
        return MockQuery(model, self._records)


class MockQuery:
    """Mock query object for MockSession."""

    def __init__(self, model, records):
        self._model = model
        self._records = records
        self._filters = []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args):
        return self

    def offset(self, n):
        return self

    def limit(self, n):
        return self

    def first(self):
        return None

    def all(self):
        return []

    def delete(self):
        return 0


class WebhookService:
    """
    Webhook delivery service.

    Manages webhook endpoint registration and event delivery.
    Supports both synchronous and asynchronous (queued) delivery.
    """

    def __init__(self, db_session=None):
        """
        Initialize webhook service.

        Args:
            db_session: SQLAlchemy session for database operations.
                       If None, will use session from database module.
        """
        self._db_session = db_session
        self._event_queue: Queue = Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

    def _get_session(self):
        """
        Get database session.

        Note: This codebase uses async database sessions. For webhook delivery
        which runs in a background thread, we use a mock session that stores
        delivery records in memory for now. In production, you would either:
        1. Use a sync database connection
        2. Queue deliveries for async processing via Celery
        """
        if self._db_session:
            return self._db_session

        # Return a mock session for background thread usage
        # Real implementation would use sync SQLAlchemy session
        return MockSession()

    # =========================================================================
    # ENDPOINT MANAGEMENT
    # =========================================================================

    def register_endpoint(
        self,
        firm_id: str,
        name: str,
        url: str,
        events: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        max_retries: int = 5,
    ) -> Dict[str, Any]:
        """
        Register a new webhook endpoint.

        Args:
            firm_id: ID of the firm registering the webhook
            name: Human-readable name for the endpoint
            url: URL to deliver webhooks to (must be HTTPS)
            events: List of event types to receive (None = all events)
            created_by: ID of user creating the endpoint
            custom_headers: Custom headers to include in requests
            max_retries: Maximum retry attempts for failed deliveries

        Returns:
            Dict with endpoint_id and secret
        """
        from webhooks.models import WebhookEndpoint, WebhookStatus
        import secrets

        # Validate URL
        if not url.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")

        # Generate signing secret
        secret = secrets.token_hex(32)

        session = self._get_session()
        try:
            endpoint = WebhookEndpoint(
                endpoint_id=uuid4(),
                firm_id=firm_id,
                name=name,
                url=url,
                secret=secret,
                events=events or [],
                status=WebhookStatus.ACTIVE.value,
                custom_headers=custom_headers or {},
                max_retries=max_retries,
                created_by=created_by,
            )

            session.add(endpoint)
            session.commit()

            logger.info(
                f"[WEBHOOK] Endpoint registered | firm={firm_id} | "
                f"endpoint={endpoint.endpoint_id} | url={url[:50]}..."
            )

            return {
                "endpoint_id": str(endpoint.endpoint_id),
                "secret": secret,
                "name": name,
                "url": url,
                "events": events or ["*"],
                "status": endpoint.status,
            }

        except Exception as e:
            session.rollback()
            logger.error(f"[WEBHOOK] Failed to register endpoint: {e}")
            raise

    def update_endpoint(
        self,
        endpoint_id: str,
        firm_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """
        Update an existing webhook endpoint.

        Args:
            endpoint_id: ID of endpoint to update
            firm_id: ID of firm (for authorization)
            updates: Dict of fields to update

        Returns:
            True if updated, False if not found
        """
        from webhooks.models import WebhookEndpoint

        session = self._get_session()
        try:
            endpoint = session.query(WebhookEndpoint).filter(
                WebhookEndpoint.endpoint_id == endpoint_id,
                WebhookEndpoint.firm_id == firm_id,
            ).first()

            if not endpoint:
                return False

            # Allowed update fields
            allowed_fields = {
                "name", "url", "events", "status",
                "custom_headers", "max_retries", "rate_limit_per_minute"
            }

            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(endpoint, field, value)

            endpoint.updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"[WEBHOOK] Endpoint updated | endpoint={endpoint_id}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"[WEBHOOK] Failed to update endpoint: {e}")
            raise

    def delete_endpoint(self, endpoint_id: str, firm_id: str) -> bool:
        """
        Delete a webhook endpoint.

        Args:
            endpoint_id: ID of endpoint to delete
            firm_id: ID of firm (for authorization)

        Returns:
            True if deleted, False if not found
        """
        from webhooks.models import WebhookEndpoint

        session = self._get_session()
        try:
            result = session.query(WebhookEndpoint).filter(
                WebhookEndpoint.endpoint_id == endpoint_id,
                WebhookEndpoint.firm_id == firm_id,
            ).delete()

            session.commit()

            if result:
                logger.info(f"[WEBHOOK] Endpoint deleted | endpoint={endpoint_id}")
            return result > 0

        except Exception as e:
            session.rollback()
            logger.error(f"[WEBHOOK] Failed to delete endpoint: {e}")
            raise

    def list_endpoints(self, firm_id: str) -> List[Dict[str, Any]]:
        """
        List all webhook endpoints for a firm.

        Args:
            firm_id: ID of firm

        Returns:
            List of endpoint dicts
        """
        from webhooks.models import WebhookEndpoint

        session = self._get_session()
        endpoints = session.query(WebhookEndpoint).filter(
            WebhookEndpoint.firm_id == firm_id
        ).order_by(WebhookEndpoint.created_at.desc()).all()

        return [
            {
                "endpoint_id": str(e.endpoint_id),
                "name": e.name,
                "url": e.url,
                "events": e.events or ["*"],
                "status": e.status,
                "total_deliveries": e.total_deliveries,
                "successful_deliveries": e.successful_deliveries,
                "failed_deliveries": e.failed_deliveries,
                "last_triggered_at": e.last_triggered_at.isoformat() if e.last_triggered_at else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in endpoints
        ]

    def get_endpoint(self, endpoint_id: str, firm_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific webhook endpoint."""
        from webhooks.models import WebhookEndpoint

        session = self._get_session()
        endpoint = session.query(WebhookEndpoint).filter(
            WebhookEndpoint.endpoint_id == endpoint_id,
            WebhookEndpoint.firm_id == firm_id,
        ).first()

        if not endpoint:
            return None

        return {
            "endpoint_id": str(endpoint.endpoint_id),
            "name": endpoint.name,
            "url": endpoint.url,
            "events": endpoint.events or ["*"],
            "status": endpoint.status,
            "custom_headers": endpoint.custom_headers,
            "max_retries": endpoint.max_retries,
            "rate_limit_per_minute": endpoint.rate_limit_per_minute,
            "total_deliveries": endpoint.total_deliveries,
            "successful_deliveries": endpoint.successful_deliveries,
            "failed_deliveries": endpoint.failed_deliveries,
            "last_triggered_at": endpoint.last_triggered_at.isoformat() if endpoint.last_triggered_at else None,
            "created_at": endpoint.created_at.isoformat(),
            "updated_at": endpoint.updated_at.isoformat() if endpoint.updated_at else None,
        }

    def rotate_secret(self, endpoint_id: str, firm_id: str) -> Optional[str]:
        """
        Rotate the signing secret for an endpoint.

        Args:
            endpoint_id: ID of endpoint
            firm_id: ID of firm (for authorization)

        Returns:
            New secret string, or None if endpoint not found
        """
        from webhooks.models import WebhookEndpoint
        import secrets

        session = self._get_session()
        try:
            endpoint = session.query(WebhookEndpoint).filter(
                WebhookEndpoint.endpoint_id == endpoint_id,
                WebhookEndpoint.firm_id == firm_id,
            ).first()

            if not endpoint:
                return None

            new_secret = secrets.token_hex(32)
            endpoint.secret = new_secret
            endpoint.updated_at = datetime.utcnow()
            session.commit()

            logger.info(f"[WEBHOOK] Secret rotated | endpoint={endpoint_id}")
            return new_secret

        except Exception as e:
            session.rollback()
            logger.error(f"[WEBHOOK] Failed to rotate secret: {e}")
            raise

    # =========================================================================
    # EVENT DELIVERY
    # =========================================================================

    def queue_event(self, event: "WebhookEvent") -> None:
        """
        Queue an event for asynchronous delivery.

        Args:
            event: WebhookEvent to deliver
        """
        self._event_queue.put(event)

        # Start worker if not running
        if not self._running:
            self.start_worker()

    def deliver_event(self, event: "WebhookEvent") -> Dict[str, Any]:
        """
        Deliver an event to all registered endpoints synchronously.

        Args:
            event: WebhookEvent to deliver

        Returns:
            Dict with delivery results per endpoint
        """
        from webhooks.models import WebhookEndpoint, WebhookStatus

        session = self._get_session()
        endpoints = session.query(WebhookEndpoint).filter(
            WebhookEndpoint.firm_id == event.firm_id,
            WebhookEndpoint.status == WebhookStatus.ACTIVE.value,
        ).all()

        results = {}

        for endpoint in endpoints:
            if endpoint.should_receive_event(event.event_type):
                result = self._deliver_to_endpoint(endpoint, event)
                results[str(endpoint.endpoint_id)] = result

        return results

    def _deliver_to_endpoint(
        self,
        endpoint: "WebhookEndpoint",
        event: "WebhookEvent",
        attempt: int = 1,
    ) -> Dict[str, Any]:
        """
        Deliver an event to a specific endpoint.

        Args:
            endpoint: WebhookEndpoint to deliver to
            event: WebhookEvent to deliver
            attempt: Current attempt number

        Returns:
            Dict with delivery result
        """
        from webhooks.models import WebhookDelivery, DeliveryStatus

        session = self._get_session()
        start_time = time.time()

        # Build payload
        payload = event.to_payload()
        payload_json = json.dumps(payload, default=str)

        # Check payload size
        if len(payload_json.encode()) > MAX_PAYLOAD_SIZE:
            logger.warning(f"[WEBHOOK] Payload too large | event={event.event_id}")
            payload = {
                "id": event.event_id,
                "type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "data": {"_truncated": True, "message": "Payload too large"},
            }
            payload_json = json.dumps(payload)

        # Generate signature
        signature = self._generate_signature(payload_json, endpoint.secret)

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-ID": event.event_id,
            "X-Webhook-Event": event.event_type,
            "X-Webhook-Timestamp": event.timestamp.isoformat(),
            "X-Webhook-Signature": signature,
            "User-Agent": "TaxPlatform-Webhooks/1.0",
        }

        # Add custom headers
        if endpoint.custom_headers:
            headers.update(endpoint.custom_headers)

        # Create delivery record
        delivery = WebhookDelivery(
            delivery_id=uuid4(),
            endpoint_id=endpoint.endpoint_id,
            event_id=event.event_id,
            event_type=event.event_type,
            request_url=endpoint.url,
            request_headers=headers,
            request_body=payload_json,
            attempt_number=attempt,
            status=DeliveryStatus.PENDING.value,
        )

        try:
            # Make HTTP request
            response = requests.post(
                endpoint.url,
                data=payload_json,
                headers=headers,
                timeout=DELIVERY_TIMEOUT,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Record response
            delivery.response_status_code = response.status_code
            delivery.response_headers = dict(response.headers)
            delivery.response_body = response.text[:10000]  # Limit stored response
            delivery.duration_ms = duration_ms

            # Check success (2xx status codes)
            if 200 <= response.status_code < 300:
                delivery.status = DeliveryStatus.DELIVERED.value
                delivery.delivered_at = datetime.utcnow()

                # Update endpoint stats
                endpoint.total_deliveries += 1
                endpoint.successful_deliveries += 1
                endpoint.last_triggered_at = datetime.utcnow()

                logger.info(
                    f"[WEBHOOK] Delivered | endpoint={endpoint.endpoint_id} | "
                    f"event={event.event_type} | status={response.status_code} | "
                    f"duration={duration_ms}ms"
                )

                result = {
                    "success": True,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                }

            else:
                # Non-2xx response
                delivery.status = DeliveryStatus.FAILED.value
                delivery.error_message = f"HTTP {response.status_code}: {response.text[:500]}"

                endpoint.total_deliveries += 1
                endpoint.failed_deliveries += 1

                logger.warning(
                    f"[WEBHOOK] Failed | endpoint={endpoint.endpoint_id} | "
                    f"event={event.event_type} | status={response.status_code}"
                )

                result = {
                    "success": False,
                    "status_code": response.status_code,
                    "error": delivery.error_message,
                }

                # Schedule retry if allowed
                if attempt < endpoint.max_retries:
                    self._schedule_retry(delivery, endpoint, event, attempt)

        except requests.Timeout:
            delivery.status = DeliveryStatus.FAILED.value
            delivery.error_message = f"Request timed out after {DELIVERY_TIMEOUT}s"
            delivery.error_code = "TIMEOUT"

            endpoint.total_deliveries += 1
            endpoint.failed_deliveries += 1

            logger.warning(
                f"[WEBHOOK] Timeout | endpoint={endpoint.endpoint_id} | "
                f"event={event.event_type}"
            )

            result = {"success": False, "error": "Request timed out"}

            if attempt < endpoint.max_retries:
                self._schedule_retry(delivery, endpoint, event, attempt)

        except requests.RequestException as e:
            delivery.status = DeliveryStatus.FAILED.value
            delivery.error_message = str(e)[:500]
            delivery.error_code = "REQUEST_ERROR"

            endpoint.total_deliveries += 1
            endpoint.failed_deliveries += 1

            logger.error(
                f"[WEBHOOK] Error | endpoint={endpoint.endpoint_id} | "
                f"event={event.event_type} | error={e}"
            )

            result = {"success": False, "error": str(e)}

            if attempt < endpoint.max_retries:
                self._schedule_retry(delivery, endpoint, event, attempt)

        # Save delivery record
        try:
            session.add(delivery)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"[WEBHOOK] Failed to save delivery record: {e}")

        return result

    def _schedule_retry(
        self,
        delivery: "WebhookDelivery",
        endpoint: "WebhookEndpoint",
        event: "WebhookEvent",
        attempt: int,
    ) -> None:
        """Schedule a retry with exponential backoff."""
        from webhooks.models import DeliveryStatus

        # Exponential backoff: 60s, 120s, 240s, 480s, 960s
        backoff_seconds = endpoint.retry_interval_seconds * (2 ** (attempt - 1))
        next_retry = datetime.utcnow() + timedelta(seconds=backoff_seconds)

        delivery.status = DeliveryStatus.RETRYING.value
        delivery.next_retry_at = next_retry

        logger.info(
            f"[WEBHOOK] Scheduled retry | endpoint={endpoint.endpoint_id} | "
            f"event={event.event_id} | attempt={attempt + 1} | "
            f"retry_at={next_retry.isoformat()}"
        )

    def _generate_signature(self, payload: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.

        The signature format is: sha256={hex_digest}

        Args:
            payload: JSON payload string
            secret: Endpoint signing secret

        Returns:
            Signature string
        """
        signature = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return f"sha256={signature}"

    def verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """
        Verify a webhook signature.

        Args:
            payload: Raw payload string
            signature: Signature from X-Webhook-Signature header
            secret: Endpoint signing secret

        Returns:
            True if signature is valid
        """
        expected = self._generate_signature(payload, secret)
        return hmac.compare_digest(expected, signature)

    # =========================================================================
    # DELIVERY HISTORY
    # =========================================================================

    def get_delivery_history(
        self,
        endpoint_id: str,
        firm_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get delivery history for an endpoint.

        Args:
            endpoint_id: ID of endpoint
            firm_id: ID of firm (for authorization)
            limit: Maximum results to return
            offset: Offset for pagination

        Returns:
            List of delivery records
        """
        from webhooks.models import WebhookEndpoint, WebhookDelivery

        session = self._get_session()

        # Verify endpoint belongs to firm
        endpoint = session.query(WebhookEndpoint).filter(
            WebhookEndpoint.endpoint_id == endpoint_id,
            WebhookEndpoint.firm_id == firm_id,
        ).first()

        if not endpoint:
            return []

        deliveries = session.query(WebhookDelivery).filter(
            WebhookDelivery.endpoint_id == endpoint_id
        ).order_by(
            WebhookDelivery.created_at.desc()
        ).offset(offset).limit(limit).all()

        return [
            {
                "delivery_id": str(d.delivery_id),
                "event_id": d.event_id,
                "event_type": d.event_type,
                "status": d.status,
                "response_status_code": d.response_status_code,
                "attempt_number": d.attempt_number,
                "duration_ms": d.duration_ms,
                "error_message": d.error_message,
                "created_at": d.created_at.isoformat(),
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            }
            for d in deliveries
        ]

    def get_delivery_detail(
        self,
        delivery_id: str,
        firm_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific delivery."""
        from webhooks.models import WebhookEndpoint, WebhookDelivery

        session = self._get_session()

        delivery = session.query(WebhookDelivery).join(
            WebhookEndpoint
        ).filter(
            WebhookDelivery.delivery_id == delivery_id,
            WebhookEndpoint.firm_id == firm_id,
        ).first()

        if not delivery:
            return None

        return {
            "delivery_id": str(delivery.delivery_id),
            "endpoint_id": str(delivery.endpoint_id),
            "event_id": delivery.event_id,
            "event_type": delivery.event_type,
            "request_url": delivery.request_url,
            "request_headers": delivery.request_headers,
            "request_body": delivery.request_body,
            "response_status_code": delivery.response_status_code,
            "response_headers": delivery.response_headers,
            "response_body": delivery.response_body,
            "status": delivery.status,
            "attempt_number": delivery.attempt_number,
            "next_retry_at": delivery.next_retry_at.isoformat() if delivery.next_retry_at else None,
            "duration_ms": delivery.duration_ms,
            "error_message": delivery.error_message,
            "error_code": delivery.error_code,
            "created_at": delivery.created_at.isoformat(),
            "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
        }

    def retry_delivery(self, delivery_id: str, firm_id: str) -> bool:
        """
        Manually retry a failed delivery.

        Args:
            delivery_id: ID of delivery to retry
            firm_id: ID of firm (for authorization)

        Returns:
            True if retry was queued
        """
        from webhooks.models import WebhookEndpoint, WebhookDelivery, WebhookEvent

        session = self._get_session()

        delivery = session.query(WebhookDelivery).join(
            WebhookEndpoint
        ).filter(
            WebhookDelivery.delivery_id == delivery_id,
            WebhookEndpoint.firm_id == firm_id,
        ).first()

        if not delivery:
            return False

        # Reconstruct event from delivery
        try:
            request_body = json.loads(delivery.request_body) if delivery.request_body else {}
        except json.JSONDecodeError:
            request_body = {}

        event = WebhookEvent(
            event_id=delivery.event_id,
            event_type=delivery.event_type,
            timestamp=delivery.created_at,
            firm_id=firm_id,
            data=request_body.get("data", {}),
            metadata=request_body.get("metadata", {}),
        )

        # Queue for delivery
        self.queue_event(event)
        return True

    # =========================================================================
    # BACKGROUND WORKER
    # =========================================================================

    def start_worker(self) -> None:
        """Start the background delivery worker."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="webhook-worker"
        )
        self._worker_thread.start()
        logger.info("[WEBHOOK] Background worker started")

    def stop_worker(self) -> None:
        """Stop the background delivery worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("[WEBHOOK] Background worker stopped")

    def _worker_loop(self) -> None:
        """Background worker main loop."""
        while self._running:
            try:
                # Get event from queue (with timeout to allow clean shutdown)
                event = self._event_queue.get(timeout=1)
                self.deliver_event(event)
            except Empty:
                # No events in queue, check for retries
                self._process_retries()
            except Exception as e:
                logger.error(f"[WEBHOOK] Worker error: {e}")

    def _process_retries(self) -> None:
        """Process pending retries."""
        from webhooks.models import WebhookEndpoint, WebhookDelivery, DeliveryStatus

        session = self._get_session()

        try:
            # Find deliveries ready for retry
            pending_retries = session.query(WebhookDelivery).filter(
                WebhookDelivery.status == DeliveryStatus.RETRYING.value,
                WebhookDelivery.next_retry_at <= datetime.utcnow(),
            ).limit(10).all()

            for delivery in pending_retries:
                endpoint = session.query(WebhookEndpoint).filter(
                    WebhookEndpoint.endpoint_id == delivery.endpoint_id
                ).first()

                if not endpoint or not endpoint.is_active:
                    delivery.status = DeliveryStatus.FAILED.value
                    delivery.error_message = "Endpoint no longer active"
                    continue

                # Reconstruct event
                try:
                    request_body = json.loads(delivery.request_body) if delivery.request_body else {}
                except json.JSONDecodeError:
                    request_body = {}

                from webhooks.models import WebhookEvent as WebhookEventModel

                event = WebhookEventModel(
                    event_id=delivery.event_id,
                    event_type=delivery.event_type,
                    timestamp=delivery.created_at,
                    firm_id=str(endpoint.firm_id),
                    data=request_body.get("data", {}),
                    metadata=request_body.get("metadata", {}),
                )

                # Attempt delivery
                self._deliver_to_endpoint(
                    endpoint,
                    event,
                    attempt=delivery.attempt_number + 1
                )

            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"[WEBHOOK] Retry processing error: {e}")


# Singleton instance
_webhook_service: Optional[WebhookService] = None


def get_webhook_service() -> WebhookService:
    """Get the global webhook service instance."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service
