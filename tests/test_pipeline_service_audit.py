"""Tests for pipeline service."""

import pytest
from cpa_panel.services.pipeline_service import LeadPipelineService


def test_pipeline_service_has_audit_methods():
    """Test that pipeline service includes audit analytics methods."""
    service = LeadPipelineService()

    # Verify methods exist
    assert hasattr(service, 'get_tax_savings_metrics')
    assert hasattr(service, 'get_return_processing_metrics')
    assert hasattr(service, 'get_lead_conversion_funnel_audit')
    assert hasattr(service, 'get_recommendation_acceptance_metrics')

    assert callable(service.get_tax_savings_metrics)
    assert callable(service.get_return_processing_metrics)
    assert callable(service.get_lead_conversion_funnel_audit)
    assert callable(service.get_recommendation_acceptance_metrics)


def test_pipeline_service_tax_savings_integration():
    """Test tax savings method integration."""
    service = LeadPipelineService()
    result = service.get_tax_savings_metrics(tenant_id="test")

    assert "total_savings" in result
    assert "by_client" in result
    assert "avg_savings" in result
