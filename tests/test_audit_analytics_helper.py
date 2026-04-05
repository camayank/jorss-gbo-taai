"""Tests for audit analytics helper."""

import pytest
from datetime import datetime, timezone, timedelta
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


def test_get_return_processing_metrics_no_events():
    """Test return metrics with no events."""
    mock_service = type('MockService', (), {
        'query': lambda *args, **kwargs: []
    })()

    helper = AuditAnalyticsHelper()
    helper._audit_service = mock_service

    result = helper.get_return_processing_metrics(tenant_id="test")

    assert result.total_returns == 0
    assert result.acceptance_rate == 0
    assert result.avg_processing_days == 0


def test_get_return_processing_metrics_with_submissions():
    """Test return processing time from submit to acceptance."""
    from audit.unified import AuditEventType
    from audit.unified.entry import UnifiedAuditEntry

    # Create mock entries for return submission and acceptance
    now = datetime.now(timezone.utc)
    submit_time = now - timedelta(days=5)
    accept_time = now - timedelta(days=2)  # 3 days processing

    submit_entry = UnifiedAuditEntry(
        event_type=AuditEventType.TAX_RETURN_SUBMIT,
        session_id="return_1",
        tenant_id="tenant_1",
        user_id="user_1",
        resource_type="return",
        resource_id="return_1",
        action="submit_return",
        timestamp=submit_time,
    )
    submit_entry.return_id = "return_1"

    accept_entry = UnifiedAuditEntry(
        event_type=AuditEventType.TAX_RETURN_ACCEPTED,
        session_id="return_1",
        tenant_id="tenant_1",
        user_id="reviewer_1",
        resource_type="return",
        resource_id="return_1",
        action="accept_return",
        timestamp=accept_time,
    )
    accept_entry.return_id = "return_1"

    # Mock the audit service
    call_count = 0
    def mock_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # First call for SUBMIT events
            return [submit_entry]
        elif call_count == 2:  # Second call for ACCEPTED events
            return [accept_entry]
        return []

    mock_service = type('MockService', (), {'query': mock_query})()

    helper = AuditAnalyticsHelper()
    helper._audit_service = mock_service

    result = helper.get_return_processing_metrics(tenant_id="tenant_1")

    assert result.total_returns == 1
    assert result.submitted_count == 1
    assert result.accepted_count == 1
    assert result.acceptance_rate == 100.0
    assert result.avg_processing_days == 3  # 5 - 2 = 3 days


def test_get_lead_conversion_funnel_no_events():
    """Test conversion funnel with no events."""
    mock_service = type('MockService', (), {
        'query': lambda *args, **kwargs: []
    })()

    helper = AuditAnalyticsHelper()
    helper._audit_service = mock_service

    result = helper.get_lead_conversion_funnel(tenant_id="test")

    assert result["magnet_leads"] == 0
    assert result["assigned_clients"] == 0
    assert result["conversion_rate"] == 0


def test_get_lead_conversion_funnel_with_assignments():
    """Test lead conversion from created to assigned."""
    from audit.unified import AuditEventType
    from audit.unified.entry import UnifiedAuditEntry

    # Create mock entries for lead creation and client assignment
    now = datetime.now(timezone.utc)

    # Simulated lead creation events (from magnet source)
    lead_entries = []
    for i in range(10):
        entry = UnifiedAuditEntry(
            event_type=AuditEventType.TAX_RETURN_CREATE,
            session_id=f"lead_{i}",
            tenant_id="tenant_1",
            user_id="system",
            resource_type="lead",
            resource_id=f"lead_{i}",
            action="create_lead",
            metadata={"source": "magnet", "lead_type": "magnet"},
            timestamp=now - timedelta(days=30 - i),
        )
        lead_entries.append(entry)

    # Client assignments (only 6 of 10 leads)
    assign_entries = []
    for i in range(6):
        entry = UnifiedAuditEntry(
            event_type=AuditEventType.CPA_CLIENT_ASSIGN,
            session_id=f"lead_{i}",
            tenant_id="tenant_1",
            user_id="user_1",
            resource_type="lead",
            resource_id=f"lead_{i}",
            action="assign_client",
            timestamp=now - timedelta(days=20 - i),
        )
        entry.return_id = f"client_{i}"
        assign_entries.append(entry)

    # Mock service with different events for different calls
    call_sequence = [lead_entries, assign_entries]
    call_count = [0]

    def mock_query(*args, **kwargs):
        result = call_sequence[call_count[0]]
        call_count[0] += 1
        return result

    mock_service = type('MockService', (), {'query': mock_query})()

    helper = AuditAnalyticsHelper()
    helper._audit_service = mock_service

    result = helper.get_lead_conversion_funnel(tenant_id="tenant_1")

    assert result["magnet_leads"] == 10
    assert result["assigned_clients"] == 6
    assert result["conversion_rate"] == 60.0  # 6/10 * 100
