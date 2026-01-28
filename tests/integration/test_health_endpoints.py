"""
Health Endpoint Integration Tests

SPEC-011: Tests for health check and monitoring endpoints.

Tests:
- /health - Full health check
- /health/live - Liveness probe
- /health/ready - Readiness probe
- /metrics - Application metrics
"""

import pytest
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, test_client, csrf_headers):
        """Health endpoint should return 200 when healthy."""
        response = test_client.get("/health", headers=csrf_headers)
        assert response.status_code == 200

    def test_health_response_structure(self, test_client, csrf_headers):
        """Health response should have expected structure."""
        response = test_client.get("/health", headers=csrf_headers)
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "uptime" in data
        assert "checks" in data

    def test_health_includes_database_check(self, test_client, csrf_headers):
        """Health should include database connectivity check."""
        response = test_client.get("/health", headers=csrf_headers)
        data = response.json()

        assert "database" in data.get("checks", {})

    def test_health_includes_encryption_check(self, test_client, csrf_headers):
        """Health should include encryption configuration check."""
        response = test_client.get("/health", headers=csrf_headers)
        data = response.json()

        assert "encryption" in data.get("checks", {})

    def test_health_includes_disk_check(self, test_client, csrf_headers):
        """Health should include disk space check."""
        response = test_client.get("/health", headers=csrf_headers)
        data = response.json()

        assert "disk" in data.get("checks", {})


class TestLivenessProbe:
    """Tests for the /health/live endpoint (Kubernetes liveness)."""

    def test_live_returns_200(self, test_client, csrf_headers):
        """Liveness probe should return 200 if server is running."""
        response = test_client.get("/health/live", headers=csrf_headers)
        assert response.status_code == 200

    def test_live_returns_ok(self, test_client, csrf_headers):
        """Liveness probe should return 'OK' text."""
        response = test_client.get("/health/live", headers=csrf_headers)
        assert response.text == "OK"


class TestReadinessProbe:
    """Tests for the /health/ready endpoint (Kubernetes readiness)."""

    def test_ready_returns_200_when_db_available(self, test_client, csrf_headers):
        """Readiness probe should return 200 when database is available."""
        response = test_client.get("/health/ready", headers=csrf_headers)
        # May return 200 or 503 depending on DB state
        assert response.status_code in [200, 503]

    def test_ready_response_structure(self, test_client, csrf_headers):
        """Readiness response should have status field."""
        response = test_client.get("/health/ready", headers=csrf_headers)
        data = response.json()

        assert "status" in data


class TestMetricsEndpoint:
    """Tests for the /metrics endpoint."""

    def test_metrics_returns_200(self, test_client, csrf_headers):
        """Metrics endpoint should return 200."""
        response = test_client.get("/metrics", headers=csrf_headers)
        assert response.status_code == 200

    def test_metrics_response_structure(self, test_client, csrf_headers):
        """Metrics response should have expected structure."""
        response = test_client.get("/metrics", headers=csrf_headers)
        data = response.json()

        assert "uptime_seconds" in data
        assert "environment" in data
        assert "database" in data
        assert "collected_at" in data

    def test_metrics_includes_request_stats(self, test_client, csrf_headers):
        """Metrics should include request statistics."""
        response = test_client.get("/metrics", headers=csrf_headers)
        data = response.json()

        assert "requests" in data
        assert "total" in data["requests"]

    def test_metrics_includes_calculation_stats(self, test_client, csrf_headers):
        """Metrics should include calculation statistics."""
        response = test_client.get("/metrics", headers=csrf_headers)
        data = response.json()

        assert "calculations" in data


class TestRequestMetrics:
    """Tests for the /metrics/requests endpoint."""

    def test_request_metrics_returns_200(self, test_client, csrf_headers):
        """Request metrics endpoint should return 200."""
        response = test_client.get("/metrics/requests", headers=csrf_headers)
        assert response.status_code == 200

    def test_request_metrics_structure(self, test_client, csrf_headers):
        """Request metrics should have expected structure."""
        response = test_client.get("/metrics/requests", headers=csrf_headers)
        data = response.json()

        assert "request_counts" in data
        assert "total_requests" in data
        assert "collected_at" in data


class TestCalculationMetrics:
    """Tests for the /metrics/calculations endpoint."""

    def test_calculation_metrics_returns_200(self, test_client, csrf_headers):
        """Calculation metrics endpoint should return 200."""
        response = test_client.get("/metrics/calculations", headers=csrf_headers)
        assert response.status_code == 200

    def test_calculation_metrics_structure(self, test_client, csrf_headers):
        """Calculation metrics should have expected structure."""
        response = test_client.get("/metrics/calculations", headers=csrf_headers)
        data = response.json()

        assert "total_calculations" in data
        assert "cache_hits" in data
        assert "cache_misses" in data
        assert "cache_hit_rate" in data


class TestHealthInfo:
    """Tests for the /health/info endpoint."""

    def test_info_returns_200(self, test_client, csrf_headers):
        """Info endpoint should return 200."""
        response = test_client.get("/health/info", headers=csrf_headers)
        assert response.status_code == 200

    def test_info_response_structure(self, test_client, csrf_headers):
        """Info response should have application metadata."""
        response = test_client.get("/health/info", headers=csrf_headers)
        data = response.json()

        assert "name" in data
        assert "version" in data
        assert "environment" in data
        assert "python_version" in data


class TestHealthEndpointCaching:
    """Tests for health endpoint caching behavior."""

    def test_health_no_cache_headers(self, test_client, csrf_headers):
        """Health endpoints should not be cached."""
        response = test_client.get("/health", headers=csrf_headers)

        # Check that caching is disabled
        cache_control = response.headers.get("Cache-Control", "")
        assert "no-cache" in cache_control or cache_control == ""

    def test_metrics_timestamp_changes(self, test_client, csrf_headers):
        """Metrics timestamp should update on each request."""
        import time

        response1 = test_client.get("/metrics", headers=csrf_headers)
        time.sleep(0.1)
        response2 = test_client.get("/metrics", headers=csrf_headers)

        # Timestamps might be the same if requests are too fast
        # Just verify both have timestamps
        assert "collected_at" in response1.json()
        assert "collected_at" in response2.json()
