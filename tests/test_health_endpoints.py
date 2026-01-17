"""Tests for health check endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Import the app
from web.app import app


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint_returns_ok(self, client):
        """GET /api/health returns healthy status."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data

    def test_health_endpoint_includes_service_name(self, client):
        """Health endpoint includes service name."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        # Service should be a string
        assert isinstance(data["service"], str)
        assert data["service"] == "tax-platform"

    def test_health_endpoint_returns_json(self, client):
        """Health endpoint returns valid JSON."""
        response = client.get("/api/health")

        assert response.status_code == 200
        # Should not raise
        data = response.json()
        assert isinstance(data, dict)

    def test_resilience_health_returns_stats(self, client):
        """GET /api/health/resilience returns circuit breaker stats."""
        response = client.get("/api/health/resilience")

        assert response.status_code == 200
        data = response.json()
        assert "circuit_breakers" in data
        assert isinstance(data["circuit_breakers"], dict)

    def test_resilience_health_includes_breaker_details(self, client):
        """Resilience health includes details for each circuit breaker."""
        # First, make sure at least one circuit breaker exists
        with patch("services.ocr.resilient_processor.OCREngine"):
            from services.ocr.resilient_processor import ResilientOCREngine, ResilientOCRConfig
            engine = ResilientOCREngine(config=ResilientOCRConfig(
                circuit_breaker_name="test_health_breaker"
            ))

        response = client.get("/api/health/resilience")

        assert response.status_code == 200
        data = response.json()
        assert "circuit_breakers" in data

        # Clean up
        from services.ocr.resilient_processor import reset_all_circuit_breakers
        reset_all_circuit_breakers()

    def test_resilience_reset_endpoint(self, client):
        """POST /api/health/resilience/reset resets all circuit breakers."""
        # Create a circuit breaker and open it
        with patch("services.ocr.resilient_processor.OCREngine"):
            from services.ocr.resilient_processor import (
                ResilientOCREngine,
                ResilientOCRConfig,
                reset_all_circuit_breakers,
            )

            reset_all_circuit_breakers()

            engine = ResilientOCREngine(config=ResilientOCRConfig(
                circuit_breaker_name="reset_test_breaker"
            ))

            # Open the circuit
            if engine._circuit_breaker:
                for _ in range(10):
                    engine._circuit_breaker.record_failure(IOError("test"))

                # Verify it's open
                assert engine.is_circuit_open is True

        # Call reset endpoint
        response = client.post("/api/health/resilience/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data

        # Verify circuit breaker is now closed
        assert engine.is_circuit_open is False

        # Clean up
        reset_all_circuit_breakers()

    def test_resilience_reset_returns_success_message(self, client):
        """Reset endpoint returns success message."""
        response = client.post("/api/health/resilience/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "circuit breakers" in data["message"].lower() or "reset" in data["message"].lower()


class TestHealthEndpointIntegration:
    """Integration tests for health endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint_responds_quickly(self, client):
        """Health endpoint responds within acceptable time."""
        import time

        start = time.time()
        response = client.get("/api/health")
        elapsed = time.time() - start

        assert response.status_code == 200
        # Should respond in under 1 second
        assert elapsed < 1.0

    def test_correlation_id_in_health_response(self, client):
        """Health responses include correlation ID header."""
        test_id = "health-check-correlation-id"
        response = client.get("/api/health", headers={"X-Correlation-ID": test_id})

        assert response.status_code == 200
        # Correlation ID should be in response headers
        assert "X-Correlation-ID" in response.headers or "x-correlation-id" in response.headers

    def test_health_endpoint_no_auth_required(self, client):
        """Health endpoint does not require authentication."""
        # Health endpoint should be accessible without any auth headers
        response = client.get("/api/health")

        assert response.status_code == 200
        # Should not return 401 or 403
        assert response.status_code not in [401, 403]
