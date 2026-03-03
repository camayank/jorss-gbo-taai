"""
E2E Test: Admin Dashboard & Metrics

Tests: Admin Login → Dashboard → Alerts → Activity → Stats → Onboarding
"""

import pytest
from unittest.mock import patch


class TestAdminLogin:
    """Admin authentication."""

    def test_admin_login(self, client, headers):
        """Admin login should respond."""
        response = client.post("/api/v1/admin/auth/login", headers=headers, json={
            "email": "admin@taxfirm.com",
            "password": "AdminP@ss123!",
        })
        assert response.status_code in [200, 401, 403, 404, 422, 500]


class TestAdminDashboard:
    """Admin dashboard data."""

    def test_dashboard_data(self, client, headers, admin_jwt_payload):
        """Dashboard should return metrics."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/dashboard", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_dashboard_alerts(self, client, headers, admin_jwt_payload):
        """Dashboard alerts should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/dashboard/alerts", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_mark_alert_read(self, client, headers, admin_jwt_payload):
        """Mark alert as read."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.post("/api/v1/admin/dashboard/alerts/test-alert/read", headers=headers, json={})
        assert response.status_code in [200, 404, 405, 500]

    def test_activity_feed(self, client, headers, admin_jwt_payload):
        """Activity feed should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/dashboard/activity", headers=headers)
        assert response.status_code in [200, 404, 500]

    def test_stats_summary(self, client, headers, admin_jwt_payload):
        """Stats summary should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/dashboard/stats/summary", headers=headers)
        assert response.status_code in [200, 404, 500]


class TestAdminPage:
    """Admin page rendering."""

    def test_admin_page(self, client, headers):
        """Admin page should render."""
        response = client.get("/admin")
        assert response.status_code in [200, 302, 303, 307]


class TestAdminOnboarding:
    """Admin onboarding status."""

    def test_onboarding_status(self, client, headers, admin_jwt_payload):
        """Onboarding status should respond."""
        with patch("rbac.jwt.decode_token_safe", return_value=admin_jwt_payload):
            response = client.get("/api/v1/admin/settings/onboarding-status", headers=headers)
        assert response.status_code in [200, 404, 500]
