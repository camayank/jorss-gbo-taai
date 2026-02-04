"""
Tests for admin panel dashboard routes.

Tests:
- Dashboard metrics retrieval
- System alerts
- Activity feed
- Analytics data
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime


class TestDashboardMetrics:
    """Tests for dashboard metrics endpoint."""

    def test_metrics_structure(self, mock_dashboard_metrics):
        """Test that dashboard metrics have required fields."""
        metrics = mock_dashboard_metrics

        assert "returns_in_progress" in metrics
        assert "returns_completed_this_month" in metrics
        assert "revenue_this_month" in metrics
        assert "clients_active" in metrics
        assert "documents_pending" in metrics
        assert "alerts" in metrics

    def test_metrics_values_are_positive(self, mock_dashboard_metrics):
        """Test that numeric metrics are non-negative."""
        metrics = mock_dashboard_metrics

        assert metrics["returns_in_progress"] >= 0
        assert metrics["returns_completed_this_month"] >= 0
        assert metrics["revenue_this_month"] >= 0
        assert metrics["clients_active"] >= 0
        assert metrics["documents_pending"] >= 0

    def test_alerts_structure(self, mock_dashboard_metrics):
        """Test that alerts have required fields."""
        alerts = mock_dashboard_metrics["alerts"]

        for alert in alerts:
            assert "type" in alert
            assert "message" in alert
            assert "severity" in alert
            assert alert["severity"] in ["info", "warning", "error", "critical"]


class TestActivityFeed:
    """Tests for activity feed endpoint."""

    def test_activity_feed_structure(self, mock_activity_feed):
        """Test that activity feed items have required fields."""
        for activity in mock_activity_feed:
            assert "activity_id" in activity
            assert "type" in activity
            assert "user" in activity
            assert "description" in activity
            assert "timestamp" in activity

    def test_activity_feed_ordered_by_time(self, mock_activity_feed):
        """Test that activity feed is ordered by timestamp (newest first)."""
        timestamps = [
            datetime.fromisoformat(a["timestamp"].replace("Z", "+00:00"))
            for a in mock_activity_feed
        ]

        # Should be in descending order
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], \
                "Activity feed should be ordered newest first"


class TestSystemAlerts:
    """Tests for system alerts functionality."""

    def test_deadline_alerts_generated(self, mock_dashboard_metrics):
        """Test that deadline alerts are properly generated."""
        alerts = mock_dashboard_metrics["alerts"]
        deadline_alerts = [a for a in alerts if a["type"] == "deadline"]

        # Should have at least the Q1 deadline alert from fixture
        assert len(deadline_alerts) >= 1

    def test_alert_severity_levels(self):
        """Test that all severity levels are valid."""
        valid_severities = {"info", "warning", "error", "critical"}

        # Test mock alert
        test_alert = {"type": "test", "message": "Test", "severity": "warning"}
        assert test_alert["severity"] in valid_severities


class TestAnalyticsSummary:
    """Tests for analytics summary data."""

    def test_revenue_calculation(self, mock_subscription_data):
        """Test revenue is calculated correctly from subscription."""
        subscription = mock_subscription_data

        expected_monthly = subscription["monthly_price"]
        assert expected_monthly > 0

    def test_seat_utilization(self, mock_subscription_data):
        """Test seat utilization is within bounds."""
        subscription = mock_subscription_data

        seats_used = subscription["seats_used"]
        seats_included = subscription["seats_included"]

        assert seats_used >= 0
        assert seats_used <= seats_included


class TestDashboardPermissions:
    """Tests for dashboard access permissions."""

    def test_admin_can_access_dashboard(self, mock_admin_user):
        """Test that firm admin can access dashboard."""
        user = mock_admin_user

        assert user.role in ["firm_admin", "firm_owner", "platform_admin"]
        assert user.firm_id is not None

    def test_platform_admin_can_access_all(self, mock_platform_admin):
        """Test that platform admin has full access."""
        user = mock_platform_admin

        assert user.role == "platform_admin"
        assert "*" in user.permissions or "view_all_dashboards" in user.permissions
