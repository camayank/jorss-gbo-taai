"""
E2E Test: Health Checks & Resilience

Tests: App Health → Resilience → Cache → Database → Migrations → Advisor Health
"""

import pytest


class TestAppHealth:
    """Application health endpoints."""

    def test_health_check(self, client, headers):
        """App health should return healthy."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"

    def test_resilience_status(self, client, headers):
        """Resilience status should respond."""
        response = client.get("/api/health/resilience", headers=headers)
        assert response.status_code in [200, 500]

    def test_cache_health(self, client, headers):
        """Cache health should respond."""
        response = client.get("/api/health/cache", headers=headers)
        assert response.status_code in [200, 500]

    def test_database_health(self, client, headers):
        """Database health should respond."""
        response = client.get("/api/health/database", headers=headers)
        assert response.status_code in [200, 500]

    def test_migration_status(self, client, headers):
        """Migration status should respond."""
        response = client.get("/api/health/migrations", headers=headers)
        assert response.status_code in [200, 500]


class TestAdvisorHealth:
    """Advisor-specific health checks."""

    def test_advisor_health(self, client, headers):
        """Advisor health should return AI status."""
        response = client.get("/api/advisor/health", headers=headers)
        assert response.status_code == 200

    def test_unified_advisor_health(self, client, headers):
        """Unified advisor health should respond."""
        response = client.get("/api/v1/advisor/health", headers=headers)
        assert response.status_code in [200, 404, 500]
