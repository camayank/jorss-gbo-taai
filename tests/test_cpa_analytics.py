"""Tests for CPA analytics dashboard."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request
from fastapi.testclient import TestClient


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user."""
    return {
        "user_id": "user_123",
        "cpa_id": "cpa_123",
        "tenant_id": "tenant_123",
        "roles": ["cpa"],
    }


def test_cpa_analytics_includes_audit_metrics_in_context(mock_auth_user):
    """Test that analytics route passes audit metrics to template context."""
    from web.cpa_dashboard_pages import cpa_analytics

    # Create mock request
    mock_request = Mock(spec=Request)
    mock_request.state = Mock()
    mock_request.state.csp_nonce = "test_nonce"

    # Mock dependencies
    with patch("web.cpa_dashboard_pages.require_cpa_auth") as mock_auth:
        mock_auth.return_value = mock_auth_user

        with patch("web.cpa_dashboard_pages.get_cpa_profile_from_context") as mock_profile:
            mock_profile.return_value = {
                "cpa_id": "cpa_123",
                "display_name": "Test CPA",
            }

            with patch("web.cpa_dashboard_pages.get_dashboard_stats") as mock_stats:
                mock_stats.return_value = {
                    "total_leads": 100,
                    "conversion_rate": 25.0,
                    "new_leads": 10,
                    "evaluating": 5,
                    "advisory_ready": 3,
                    "high_leverage": 2,
                    "total_revenue": 50000,
                }

                with patch("cpa_panel.services.pipeline_service.get_pipeline_service") as mock_service:
                    service_instance = Mock()
                    mock_service.return_value = service_instance

                    # Mock audit metrics
                    service_instance.get_conversion_metrics.return_value = {"conversion_rate": 25.0}
                    service_instance.get_velocity_metrics.return_value = {"avg_days_to_convert": 7}
                    service_instance.get_lead_trends.return_value = {"new_leads": [1, 2, 3], "dates": ["2024-01-01", "2024-01-02", "2024-01-03"]}
                    service_instance.get_tax_savings_metrics.return_value = {
                        "total_savings": 50000.0,
                        "by_client": [],
                        "avg_savings": 5000.0,
                        "count": 10,
                    }
                    service_instance.get_return_processing_metrics.return_value = {
                        "total_returns": 15,
                        "avg_processing_days": 5.0,
                        "submitted_count": 15,
                        "accepted_count": 14,
                        "acceptance_rate": 93.3,
                    }
                    service_instance.get_lead_conversion_funnel_audit.return_value = {
                        "magnet_leads": 100,
                        "assigned_clients": 60,
                        "conversion_rate": 60.0,
                    }
                    service_instance.get_recommendation_acceptance_metrics.return_value = {
                        "total_recommendations": 40,
                        "accepted_count": 32,
                        "acceptance_rate": 80.0,
                    }

                    # Call the async function
                    import asyncio
                    response = asyncio.run(cpa_analytics(mock_request, mock_auth_user))

                    # Verify response is a TemplateResponse
                    assert response.status_code == 200

                    # Verify audit metrics are in the context
                    context = response.context
                    assert "audit_tax_savings" in context
                    assert "audit_return_metrics" in context
                    assert "audit_lead_funnel" in context
                    assert "audit_recommendations" in context

                    # Verify the values are passed correctly
                    assert context["audit_tax_savings"]["total_savings"] == 50000.0
                    assert context["audit_tax_savings"]["count"] == 10

                    assert context["audit_return_metrics"]["avg_processing_days"] == 5.0
                    assert context["audit_return_metrics"]["acceptance_rate"] == 93.3

                    assert context["audit_lead_funnel"]["conversion_rate"] == 60.0
                    assert context["audit_lead_funnel"]["assigned_clients"] == 60

                    assert context["audit_recommendations"]["acceptance_rate"] == 80.0
                    assert context["audit_recommendations"]["accepted_count"] == 32


def test_cpa_analytics_audit_metrics_defaults_on_error(mock_auth_user):
    """Test that audit metrics have sensible defaults when service fails."""
    from web.cpa_dashboard_pages import cpa_analytics

    # Create mock request
    mock_request = Mock(spec=Request)
    mock_request.state = Mock()
    mock_request.state.csp_nonce = "test_nonce"

    # Mock dependencies
    with patch("web.cpa_dashboard_pages.require_cpa_auth") as mock_auth:
        mock_auth.return_value = mock_auth_user

        with patch("web.cpa_dashboard_pages.get_cpa_profile_from_context") as mock_profile:
            mock_profile.return_value = {
                "cpa_id": "cpa_123",
                "display_name": "Test CPA",
            }

            with patch("web.cpa_dashboard_pages.get_dashboard_stats") as mock_stats:
                mock_stats.return_value = {
                    "total_leads": 100,
                    "conversion_rate": 25.0,
                    "new_leads": 10,
                    "evaluating": 5,
                    "advisory_ready": 3,
                    "high_leverage": 2,
                    "total_revenue": 50000,
                }

                with patch("cpa_panel.services.pipeline_service.get_pipeline_service") as mock_service:
                    # Simulate service failure
                    mock_service.side_effect = Exception("Service error")

                    # Call the async function
                    import asyncio
                    response = asyncio.run(cpa_analytics(mock_request, mock_auth_user))

                    # Verify response is a TemplateResponse
                    assert response.status_code == 200

                    # Verify audit metrics have defaults
                    context = response.context
                    assert context["audit_tax_savings"]["total_savings"] == 0
                    assert context["audit_return_metrics"]["total_returns"] == 0
                    assert context["audit_lead_funnel"]["magnet_leads"] == 0
                    assert context["audit_recommendations"]["total_recommendations"] == 0
