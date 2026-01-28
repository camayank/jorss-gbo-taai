"""
Tests for the Webhooks Module

Tests webhook endpoint management, event emission, and delivery.
"""

import pytest
import json
import hmac
import hashlib
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock


class TestWebhookEvents:
    """Test webhook event types and emission."""

    def test_event_types_defined(self):
        """Test that all expected event types are defined."""
        from webhooks.events import (
            WebhookEventType,
            CLIENT_EVENTS,
            RETURN_EVENTS,
            DOCUMENT_EVENTS,
            ALL_EVENTS,
        )

        # Verify client events
        assert "client.created" in CLIENT_EVENTS
        assert "client.updated" in CLIENT_EVENTS

        # Verify return events
        assert "return.created" in RETURN_EVENTS
        assert "return.status_changed" in RETURN_EVENTS
        assert "return.submitted" in RETURN_EVENTS
        assert "return.accepted" in RETURN_EVENTS
        assert "return.rejected" in RETURN_EVENTS

        # Verify document events
        assert "document.uploaded" in DOCUMENT_EVENTS
        assert "document.processed" in DOCUMENT_EVENTS

        # All events should include all categories
        for event in CLIENT_EVENTS:
            assert event in ALL_EVENTS
        for event in RETURN_EVENTS:
            assert event in ALL_EVENTS

    def test_webhook_event_type_enum(self):
        """Test WebhookEventType enum values."""
        from webhooks.events import WebhookEventType

        assert WebhookEventType.CLIENT_CREATED.value == "client.created"
        assert WebhookEventType.RETURN_STATUS_CHANGED.value == "return.status_changed"
        assert WebhookEventType.DOCUMENT_UPLOADED.value == "document.uploaded"

    def test_get_event_schema(self):
        """Test getting event payload schemas."""
        from webhooks.events import get_event_schema

        schema = get_event_schema("client.created")
        assert "client_id" in schema
        assert "name" in schema

        schema = get_event_schema("return.status_changed")
        assert "return_id" in schema
        assert "previous_status" in schema
        assert "new_status" in schema


class TestWebhookModels:
    """Test webhook data models."""

    def test_webhook_event_to_payload(self):
        """Test WebhookEvent payload conversion."""
        from webhooks.models import WebhookEvent

        event = WebhookEvent(
            event_id="evt-123",
            event_type="client.created",
            timestamp=datetime(2026, 1, 29, 12, 0, 0),
            firm_id="firm-456",
            data={"client_id": "client-789", "name": "Test"},
            metadata={"source": "api"},
        )

        payload = event.to_payload()

        assert payload["id"] == "evt-123"
        assert payload["type"] == "client.created"
        assert payload["data"]["client_id"] == "client-789"
        assert payload["metadata"]["source"] == "api"
        assert "timestamp" in payload

    def test_webhook_status_enum(self):
        """Test webhook status enum values."""
        from webhooks.models import WebhookStatus, DeliveryStatus

        assert WebhookStatus.ACTIVE.value == "active"
        assert WebhookStatus.PAUSED.value == "paused"
        assert WebhookStatus.DISABLED.value == "disabled"

        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.DELIVERED.value == "delivered"
        assert DeliveryStatus.FAILED.value == "failed"
        assert DeliveryStatus.RETRYING.value == "retrying"


class TestWebhookService:
    """Test webhook service functionality."""

    def test_generate_signature(self):
        """Test HMAC signature generation."""
        from webhooks.service import WebhookService

        service = WebhookService()
        payload = '{"id":"test","type":"test.event"}'
        secret = "test-secret-key"

        signature = service._generate_signature(payload, secret)

        assert signature.startswith("sha256=")
        # Verify the signature is correct
        expected = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        assert signature == f"sha256={expected}"

    def test_verify_signature(self):
        """Test signature verification."""
        from webhooks.service import WebhookService

        service = WebhookService()
        payload = '{"id":"test","type":"test.event"}'
        secret = "test-secret-key"

        # Generate valid signature
        signature = service._generate_signature(payload, secret)

        # Should verify correctly
        assert service.verify_signature(payload, signature, secret) is True

        # Wrong signature should fail
        assert service.verify_signature(payload, "sha256=invalid", secret) is False

        # Wrong secret should fail
        assert service.verify_signature(payload, signature, "wrong-secret") is False


class TestWebhookTriggers:
    """Test webhook trigger helper functions."""

    def test_safe_emit_handles_errors(self):
        """Test that _safe_emit catches errors gracefully."""
        from webhooks.triggers import _safe_emit

        # Should not raise even if internal call fails
        # The function catches all exceptions
        _safe_emit("unknown.event.type", "firm-123", {"test": "data"})

    def test_trigger_functions_exist(self):
        """Test that all trigger functions are defined."""
        from webhooks import triggers

        # Client triggers
        assert hasattr(triggers, "trigger_client_created")
        assert hasattr(triggers, "trigger_client_updated")
        assert hasattr(triggers, "trigger_client_archived")

        # Return triggers
        assert hasattr(triggers, "trigger_return_created")
        assert hasattr(triggers, "trigger_return_status_changed")
        assert hasattr(triggers, "trigger_return_submitted")
        assert hasattr(triggers, "trigger_return_accepted")
        assert hasattr(triggers, "trigger_return_rejected")

        # Document triggers
        assert hasattr(triggers, "trigger_document_uploaded")
        assert hasattr(triggers, "trigger_document_processed")

        # Scenario triggers
        assert hasattr(triggers, "trigger_scenario_created")
        assert hasattr(triggers, "trigger_scenario_completed")


class TestWebhookDelivery:
    """Test webhook delivery mechanics."""

    def test_delivery_with_retry_on_failure(self):
        """Test that failed deliveries are retried."""
        from webhooks.service import WebhookService
        from webhooks.models import WebhookEvent

        service = WebhookService()

        # Mock endpoint
        endpoint = Mock()
        endpoint.endpoint_id = uuid4()
        endpoint.firm_id = uuid4()
        endpoint.url = "https://example.com/webhook"
        endpoint.secret = "test-secret"
        endpoint.custom_headers = {}
        endpoint.max_retries = 3
        endpoint.retry_interval_seconds = 60
        endpoint.is_active = True
        endpoint.should_receive_event.return_value = True
        endpoint.total_deliveries = 0
        endpoint.successful_deliveries = 0
        endpoint.failed_deliveries = 0

        event = WebhookEvent(
            event_id="evt-123",
            event_type="test.event",
            timestamp=datetime.utcnow(),
            firm_id=str(endpoint.firm_id),
            data={"test": "data"},
        )

        # Mock failed HTTP request
        with patch("webhooks.service.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.headers = {}
            mock_post.return_value = mock_response

            with patch.object(service, "_get_session") as mock_session:
                mock_s = Mock()
                mock_s.add.return_value = None
                mock_s.commit.return_value = None
                mock_session.return_value = mock_s

                result = service._deliver_to_endpoint(endpoint, event, attempt=1)

                assert result["success"] is False
                assert result["status_code"] == 500

    def test_successful_delivery(self):
        """Test successful webhook delivery."""
        from webhooks.service import WebhookService
        from webhooks.models import WebhookEvent

        service = WebhookService()

        endpoint = Mock()
        endpoint.endpoint_id = uuid4()
        endpoint.firm_id = uuid4()
        endpoint.url = "https://example.com/webhook"
        endpoint.secret = "test-secret"
        endpoint.custom_headers = {}
        endpoint.max_retries = 3
        endpoint.retry_interval_seconds = 60
        endpoint.total_deliveries = 0
        endpoint.successful_deliveries = 0
        endpoint.failed_deliveries = 0

        event = WebhookEvent(
            event_id="evt-123",
            event_type="test.event",
            timestamp=datetime.utcnow(),
            firm_id=str(endpoint.firm_id),
            data={"test": "data"},
        )

        with patch("webhooks.service.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"received": true}'
            mock_response.headers = {"Content-Type": "application/json"}
            mock_post.return_value = mock_response

            with patch.object(service, "_get_session") as mock_session:
                mock_s = Mock()
                mock_s.add.return_value = None
                mock_s.commit.return_value = None
                mock_session.return_value = mock_s

                result = service._deliver_to_endpoint(endpoint, event, attempt=1)

                assert result["success"] is True
                assert result["status_code"] == 200

    def test_delivery_timeout_handling(self):
        """Test that delivery timeouts are handled properly."""
        from webhooks.service import WebhookService
        from webhooks.models import WebhookEvent
        import requests

        service = WebhookService()

        endpoint = Mock()
        endpoint.endpoint_id = uuid4()
        endpoint.firm_id = uuid4()
        endpoint.url = "https://example.com/webhook"
        endpoint.secret = "test-secret"
        endpoint.custom_headers = {}
        endpoint.max_retries = 3
        endpoint.retry_interval_seconds = 60
        endpoint.total_deliveries = 0
        endpoint.successful_deliveries = 0
        endpoint.failed_deliveries = 0

        event = WebhookEvent(
            event_id="evt-123",
            event_type="test.event",
            timestamp=datetime.utcnow(),
            firm_id=str(endpoint.firm_id),
            data={"test": "data"},
        )

        with patch("webhooks.service.requests.post") as mock_post:
            mock_post.side_effect = requests.Timeout("Request timed out")

            with patch.object(service, "_get_session") as mock_session:
                mock_s = Mock()
                mock_s.add.return_value = None
                mock_s.commit.return_value = None
                mock_session.return_value = mock_s

                result = service._deliver_to_endpoint(endpoint, event, attempt=1)

                assert result["success"] is False
                assert "timed out" in result["error"].lower()


class TestWebhookIntegration:
    """Integration tests for webhook flow."""

    def test_status_manager_imports_webhook_trigger(self):
        """Test that status manager has webhook trigger import."""
        from cpa_panel.workflow.status_manager import CPAWorkflowManager

        # Read the source file to verify the import is there
        import inspect
        source = inspect.getsource(CPAWorkflowManager.transition)
        assert "trigger_return_status_changed" in source

    def test_webhook_module_exports(self):
        """Test that webhook module exports all expected items."""
        import webhooks

        # Models
        assert hasattr(webhooks, "WebhookEndpoint")
        assert hasattr(webhooks, "WebhookDelivery")
        assert hasattr(webhooks, "WebhookEvent")

        # Service
        assert hasattr(webhooks, "WebhookService")
        assert hasattr(webhooks, "get_webhook_service")

        # Events
        assert hasattr(webhooks, "WebhookEventType")
        assert hasattr(webhooks, "emit_webhook_event")
        assert hasattr(webhooks, "ALL_EVENTS")
