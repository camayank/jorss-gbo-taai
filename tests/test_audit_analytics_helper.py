"""Tests for audit analytics helper."""

import pytest
from datetime import datetime, timezone
from cpa_panel.services.audit_analytics_helper import (
    AuditAnalyticsHelper,
    get_audit_analytics_helper,
    TaxSavingsMetric,
    ReturnProcessingMetric,
)


def test_audit_analytics_helper_singleton():
    """Test that helper uses singleton pattern."""
    helper1 = get_audit_analytics_helper()
    helper2 = get_audit_analytics_helper()
    assert helper1 is helper2


def test_audit_analytics_helper_has_audit_service():
    """Test that helper initializes audit service."""
    helper = get_audit_analytics_helper()
    assert helper.audit_service is not None


def test_tax_savings_metric_creation():
    """Test TaxSavingsMetric dataclass."""
    metric = TaxSavingsMetric(
        client_id="client_123",
        client_name="Acme Corp",
        total_savings=5000.0,
        num_returns=2,
        avg_savings_per_return=2500.0,
        latest_calc_date=datetime.now(timezone.utc),
    )
    assert metric.client_id == "client_123"
    assert metric.total_savings == 5000.0


def test_get_tax_savings_by_client_no_events():
    """Test tax savings with no audit events."""
    mock_service = type('MockService', (), {
        'query': lambda *args, **kwargs: []
    })()

    helper = AuditAnalyticsHelper()
    helper._audit_service = mock_service

    result = helper.get_tax_savings_by_client(tenant_id="test")

    assert result["total_savings"] == 0
    assert result["by_client"] == []
    assert result["avg_savings"] == 0


def test_get_tax_savings_by_client_with_events():
    """Test tax savings calculation from TAX_CALC_RUN events."""
    from audit.unified import AuditEventType
    from audit.unified.entry import UnifiedAuditEntry

    # Create mock audit entries with tax calculation data
    entry1 = UnifiedAuditEntry(
        event_type=AuditEventType.TAX_CALC_RUN,
        session_id="session_1",
        tenant_id="tenant_1",
        user_id="user_1",
        resource_type="calculation",
        resource_id="calc_1",
        action="calculate_federal",
        old_value={"outputs": {"total_tax_liability": 50000}},
        new_value={"outputs": {"total_tax_liability": 45000}},  # $5k savings
    )

    entry1.session_id = "session_1"
    entry1.return_id = "return_1"
    entry1.metadata = {"client_id": "client_123", "client_name": "Acme Corp"}

    mock_service = type('MockService', (), {
        'query': lambda self, *args, **kwargs: [entry1]
    })()

    helper = AuditAnalyticsHelper()
    helper._audit_service = mock_service

    result = helper.get_tax_savings_by_client(tenant_id="tenant_1")

    assert result["total_savings"] == 5000
    assert len(result["by_client"]) == 1
    assert result["by_client"][0].client_id == "client_123"
    assert result["by_client"][0].total_savings == 5000
