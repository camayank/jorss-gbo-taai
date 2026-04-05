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
