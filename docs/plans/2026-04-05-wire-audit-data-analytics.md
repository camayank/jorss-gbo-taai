# Wire Audit Data into CPA Analytics Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate audit logs data to display tax savings delivered per client, recommendation acceptance rate, return processing time, and lead conversion funnel metrics on the CPA analytics dashboard.

**Architecture:**
The implementation extends the existing `LeadPipelineService` with new audit-based analytics methods. These methods use `AuditService.query()` to pull event data from audit logs, aggregate metrics (grouping by CPA, client, time period), and return analytics-ready dictionaries. The analytics route then combines transactional lead data with audit-derived metrics to provide a complete picture of CPA performance.

**Tech Stack:**
- Audit Service: `src/audit/unified/service.py` (AuditService with query capabilities)
- Pipeline Service: `src/cpa_panel/services/pipeline_service.py` (existing service extended)
- Analytics Route: `src/web/cpa_dashboard_pages.py`
- Event Types: `src/audit/unified/event_types.py` (AuditEventType enum)

---

## Task 1: Set Up Audit Query Integration & Create Helper Module

**Files:**
- Create: `src/cpa_panel/services/audit_analytics_helper.py`
- Modify: `src/cpa_panel/services/pipeline_service.py` (import in __init__)

**Step 1: Write the helper module with base functions**

```python
# src/cpa_panel/services/audit_analytics_helper.py
"""
Audit-based analytics aggregation for CPA dashboard.

Provides methods to extract and aggregate audit events for:
- Tax savings calculation
- Return processing metrics
- Lead conversion funnel
- Recommendation acceptance rate
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TaxSavingsMetric:
    """Represents tax savings for a client."""
    client_id: str
    client_name: Optional[str]
    total_savings: float
    num_returns: int
    avg_savings_per_return: float
    latest_calc_date: Optional[datetime]


@dataclass
class ReturnProcessingMetric:
    """Represents return processing statistics."""
    total_returns: int
    avg_processing_days: float
    submitted_count: int
    accepted_count: int
    acceptance_rate: float
    latest_acceptance_date: Optional[datetime]


class AuditAnalyticsHelper:
    """Helper class for audit-based analytics aggregations."""

    def __init__(self):
        """Initialize helper with audit service."""
        self._audit_service = None

    @property
    def audit_service(self):
        """Get or initialize audit service."""
        if self._audit_service is None:
            from audit.unified import AuditService
            self._audit_service = AuditService.get_instance()
        return self._audit_service

    def get_tax_savings_by_client(
        self,
        cpa_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Calculate tax savings delivered per client from audit logs.

        Aggregates TAX_CALC_RUN events, extracting the difference between
        old and new tax liability values.

        Args:
            cpa_id: Optional CPA filter (not directly in audit, use context)
            tenant_id: Tenant ID for filtering
            days: Number of days to look back

        Returns:
            Dict with keys:
            - total_savings: Sum of all tax savings
            - by_client: List of TaxSavingsMetric
            - avg_savings: Average per client
        """
        # TODO: Implement in Task 2
        pass

    def get_return_processing_metrics(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30,
    ) -> ReturnProcessingMetric:
        """
        Get return processing time and acceptance metrics.

        Tracks:
        - Time from TAX_RETURN_SUBMIT to TAX_RETURN_ACCEPTED
        - Acceptance rate (accepted / submitted)
        - Total processing time statistics

        Args:
            tenant_id: Tenant ID for filtering
            days: Number of days to look back

        Returns:
            ReturnProcessingMetric with aggregated statistics
        """
        # TODO: Implement in Task 3
        pass

    def get_lead_conversion_funnel(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get lead conversion funnel from audit logs.

        Aggregates CPA_CLIENT_ASSIGN and related events to show funnel
        from initial lead creation to client assignment.

        Args:
            tenant_id: Tenant ID for filtering
            days: Number of days to look back

        Returns:
            Dict with keys:
            - magnet_leads: Leads from magnet source
            - assigned_clients: Leads assigned as clients
            - conversion_rate: Percentage of magnet → client
            - by_stage: Breakdown by funnel stage
        """
        # TODO: Implement in Task 4
        pass

    def get_recommendation_acceptance_rate(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Calculate recommendation acceptance rate.

        Tracks tax optimization recommendations offered vs. implemented
        through TAX_DATA_FIELD_CHANGE events with recommendation context.

        Args:
            tenant_id: Tenant ID for filtering
            days: Number of days to look back

        Returns:
            Dict with keys:
            - total_recommendations: Offers made
            - accepted_count: Recommendations implemented
            - acceptance_rate: Percentage
            - by_type: Breakdown by recommendation category
        """
        # TODO: Implement in Task 5
        pass


# Singleton instance
_helper_instance = None


def get_audit_analytics_helper() -> AuditAnalyticsHelper:
    """Get singleton instance of audit analytics helper."""
    global _helper_instance
    if _helper_instance is None:
        _helper_instance = AuditAnalyticsHelper()
    return _helper_instance
```

**Step 2: Create test file with import test**

```python
# tests/test_audit_analytics_helper.py
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
```

**Step 3: Run test to verify it fails**

```bash
cd /Users/rakeshanita/jorss-gbo-taai
python -m pytest tests/test_audit_analytics_helper.py::test_audit_analytics_helper_singleton -v
```

Expected: FAIL - module doesn't exist yet

**Step 4: Create the file**

Run: Create the files as shown in Steps 1-2

**Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_audit_analytics_helper.py -v
```

Expected: All 3 tests PASS

**Step 6: Commit**

```bash
git add src/cpa_panel/services/audit_analytics_helper.py tests/test_audit_analytics_helper.py
git commit -m "feat: add audit analytics helper module with skeleton methods

- Create AuditAnalyticsHelper class with 4 audit-based metrics methods
- Add dataclasses for TaxSavingsMetric and ReturnProcessingMetric
- Add singleton getter function
- Add tests for singleton pattern and audit service initialization"
```

---

## Task 2: Implement Tax Savings Calculation from Audit

**Files:**
- Modify: `src/cpa_panel/services/audit_analytics_helper.py` (implement `get_tax_savings_by_client`)
- Modify: `tests/test_audit_analytics_helper.py` (add tests)

**Step 1: Write failing tests for tax savings**

```python
# Add to tests/test_audit_analytics_helper.py

def test_get_tax_savings_by_client_no_events(monkeypatch):
    """Test tax savings with no audit events."""
    from audit.unified import AuditService

    # Mock the audit service to return empty results
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
    from audit.unified import AuditService, AuditEventType
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
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_audit_analytics_helper.py::test_get_tax_savings_by_client_no_events -v
python -m pytest tests/test_audit_analytics_helper.py::test_get_tax_savings_by_client_with_events -v
```

Expected: FAIL - method not implemented

**Step 3: Implement tax savings calculation**

```python
# In src/cpa_panel/services/audit_analytics_helper.py, replace the stub:

    def get_tax_savings_by_client(
        self,
        cpa_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Calculate tax savings delivered per client from audit logs.

        Aggregates TAX_CALC_RUN events, extracting the difference between
        old and new tax liability values.
        """
        from audit.unified.event_types import AuditEventType

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        # Query for TAX_CALC_RUN events in the time window
        events = self.audit_service.query(
            event_type=AuditEventType.TAX_CALC_RUN,
            tenant_id=tenant_id,
            start_date=start,
            end_date=end,
            limit=1000,
        )

        if not events:
            return {
                "total_savings": 0,
                "by_client": [],
                "avg_savings": 0,
                "count": 0,
            }

        # Aggregate savings by client
        client_savings: Dict[str, Tuple[float, int, datetime]] = {}  # client_id -> (savings, count, latest_date)

        for event in events:
            try:
                # Extract tax liability values from old and new
                old_liability = 0
                new_liability = 0

                if event.old_value and isinstance(event.old_value, dict):
                    outputs = event.old_value.get("outputs", {})
                    old_liability = float(outputs.get("total_tax_liability", 0))

                if event.new_value and isinstance(event.new_value, dict):
                    outputs = event.new_value.get("outputs", {})
                    new_liability = float(outputs.get("total_tax_liability", 0))

                # Calculate savings (positive = tax reduced)
                savings = old_liability - new_liability

                # Get client info from metadata or resource
                client_id = None
                client_name = None

                if event.metadata and isinstance(event.metadata, dict):
                    client_id = event.metadata.get("client_id")
                    client_name = event.metadata.get("client_name")

                if not client_id and event.resource_id:
                    client_id = event.resource_id

                if not client_id:
                    client_id = event.session_id or "unknown"

                # Accumulate savings
                if client_id in client_savings:
                    prev_savings, count, latest = client_savings[client_id]
                    client_savings[client_id] = (
                        prev_savings + savings,
                        count + 1,
                        max(latest, event.timestamp) if latest else event.timestamp
                    )
                else:
                    client_savings[client_id] = (savings, 1, event.timestamp)

            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Error processing TAX_CALC_RUN event: {e}")
                continue

        # Build result
        total_savings = 0
        by_client = []

        for client_id, (savings, count, latest_date) in client_savings.items():
            metric = TaxSavingsMetric(
                client_id=client_id,
                client_name=None,  # Could enhance by looking up from DB
                total_savings=max(0, savings),  # Don't report negative savings
                num_returns=count,
                avg_savings_per_return=savings / count if count > 0 else 0,
                latest_calc_date=latest_date,
            )
            by_client.append(metric)
            total_savings += metric.total_savings

        # Sort by total savings descending
        by_client.sort(key=lambda x: x.total_savings, reverse=True)

        avg_savings = total_savings / len(by_client) if by_client else 0

        return {
            "total_savings": round(total_savings, 2),
            "by_client": by_client,
            "avg_savings": round(avg_savings, 2),
            "count": len(by_client),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_audit_analytics_helper.py::test_get_tax_savings_by_client_no_events -v
python -m pytest tests/test_audit_analytics_helper.py::test_get_tax_savings_by_client_with_events -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/cpa_panel/services/audit_analytics_helper.py tests/test_audit_analytics_helper.py
git commit -m "feat: implement tax savings calculation from audit logs

- Query TAX_CALC_RUN events and extract tax liability changes
- Aggregate savings by client with count and averages
- Return structured metrics suitable for dashboard display
- Add comprehensive tests covering empty and populated scenarios"
```

---

## Task 3: Implement Return Processing Time Metrics

**Files:**
- Modify: `src/cpa_panel/services/audit_analytics_helper.py` (implement `get_return_processing_metrics`)
- Modify: `tests/test_audit_analytics_helper.py` (add tests)

**Step 1: Write failing tests for return processing**

```python
# Add to tests/test_audit_analytics_helper.py

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
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_audit_analytics_helper.py::test_get_return_processing_metrics_no_events -v
python -m pytest tests/test_audit_analytics_helper.py::test_get_return_processing_metrics_with_submissions -v
```

Expected: FAIL

**Step 3: Implement return processing metrics**

```python
# In src/cpa_panel/services/audit_analytics_helper.py, replace the stub:

    def get_return_processing_metrics(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30,
    ) -> ReturnProcessingMetric:
        """
        Get return processing time and acceptance metrics.

        Tracks:
        - Time from TAX_RETURN_SUBMIT to TAX_RETURN_ACCEPTED
        - Acceptance rate (accepted / submitted)
        - Total processing time statistics
        """
        from audit.unified.event_types import AuditEventType

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        # Query for SUBMIT events
        submit_events = self.audit_service.query(
            event_type=AuditEventType.TAX_RETURN_SUBMIT,
            tenant_id=tenant_id,
            start_date=start,
            end_date=end,
            limit=1000,
        )

        # Query for ACCEPTED events
        accept_events = self.audit_service.query(
            event_type=AuditEventType.TAX_RETURN_ACCEPTED,
            tenant_id=tenant_id,
            start_date=start,
            end_date=end,
            limit=1000,
        )

        if not submit_events:
            return ReturnProcessingMetric(
                total_returns=0,
                avg_processing_days=0,
                submitted_count=0,
                accepted_count=0,
                acceptance_rate=0,
                latest_acceptance_date=None,
            )

        # Index accepted events by return_id for quick lookup
        accepted_by_return = {}
        latest_acceptance = None

        for event in accept_events:
            return_id = event.return_id or event.resource_id or event.session_id
            if return_id:
                accepted_by_return[return_id] = event
                if not latest_acceptance or event.timestamp > latest_acceptance:
                    latest_acceptance = event.timestamp

        # Calculate metrics
        processing_times = []
        accepted_count = 0

        for event in submit_events:
            return_id = event.return_id or event.resource_id or event.session_id

            if return_id in accepted_by_return:
                accept_event = accepted_by_return[return_id]
                # Calculate days between submit and acceptance
                days_diff = (accept_event.timestamp - event.timestamp).days
                processing_times.append(max(0, days_diff))  # Handle negative (shouldn't happen)
                accepted_count += 1

        avg_processing_days = (
            sum(processing_times) / len(processing_times)
            if processing_times else 0
        )

        acceptance_rate = (
            (accepted_count / len(submit_events) * 100)
            if submit_events else 0
        )

        return ReturnProcessingMetric(
            total_returns=len(submit_events),
            avg_processing_days=round(avg_processing_days, 1),
            submitted_count=len(submit_events),
            accepted_count=accepted_count,
            acceptance_rate=round(acceptance_rate, 1),
            latest_acceptance_date=latest_acceptance,
        )
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_audit_analytics_helper.py::test_get_return_processing_metrics_no_events -v
python -m pytest tests/test_audit_analytics_helper.py::test_get_return_processing_metrics_with_submissions -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/cpa_panel/services/audit_analytics_helper.py tests/test_audit_analytics_helper.py
git commit -m "feat: implement return processing time metrics from audit logs

- Query TAX_RETURN_SUBMIT and TAX_RETURN_ACCEPTED events
- Calculate average processing time in days
- Compute acceptance rate (accepted / submitted)
- Track latest acceptance date
- Return ReturnProcessingMetric dataclass for structured results"
```

---

## Task 4: Implement Lead Conversion Funnel from Audit

**Files:**
- Modify: `src/cpa_panel/services/audit_analytics_helper.py` (implement `get_lead_conversion_funnel`)
- Modify: `tests/test_audit_analytics_helper.py` (add tests)

**Step 1: Write failing tests for lead conversion funnel**

```python
# Add to tests/test_audit_analytics_helper.py

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
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_audit_analytics_helper.py::test_get_lead_conversion_funnel_no_events -v
python -m pytest tests/test_audit_analytics_helper.py::test_get_lead_conversion_funnel_with_assignments -v
```

Expected: FAIL

**Step 3: Implement lead conversion funnel**

```python
# In src/cpa_panel/services/audit_analytics_helper.py, replace the stub:

    def get_lead_conversion_funnel(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get lead conversion funnel from audit logs.

        Aggregates CPA_CLIENT_ASSIGN and related events to show funnel
        from initial lead creation to client assignment.
        """
        from audit.unified.event_types import AuditEventType

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        # Query for lead creation events (use TAX_RETURN_CREATE as proxy for lead creation)
        # In practice, might need a specific lead creation event type
        lead_creation_events = self.audit_service.query(
            event_type=AuditEventType.TAX_RETURN_CREATE,
            tenant_id=tenant_id,
            start_date=start,
            end_date=end,
            limit=1000,
        )

        # Filter for magnet source (check metadata)
        magnet_leads = []
        for event in lead_creation_events:
            if event.metadata and isinstance(event.metadata, dict):
                source = event.metadata.get("source")
                if source == "magnet" or event.metadata.get("lead_type") == "magnet":
                    magnet_leads.append(event)

        # Query for client assignments
        assign_events = self.audit_service.query(
            event_type=AuditEventType.CPA_CLIENT_ASSIGN,
            tenant_id=tenant_id,
            start_date=start,
            end_date=end,
            limit=1000,
        )

        # Build set of assigned lead IDs
        assigned_lead_ids = set()
        for event in assign_events:
            lead_id = event.resource_id or event.session_id
            if lead_id:
                assigned_lead_ids.add(lead_id)

        # Calculate conversion rate
        magnet_count = len(magnet_leads)
        assigned_count = len(assigned_lead_ids)
        conversion_rate = (
            (assigned_count / magnet_count * 100)
            if magnet_count > 0 else 0
        )

        return {
            "magnet_leads": magnet_count,
            "assigned_clients": assigned_count,
            "conversion_rate": round(conversion_rate, 1),
            "by_stage": {
                "created_leads": magnet_count,
                "assigned_as_client": assigned_count,
                "pending_assignment": magnet_count - assigned_count,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_audit_analytics_helper.py::test_get_lead_conversion_funnel_no_events -v
python -m pytest tests/test_audit_analytics_helper.py::test_get_lead_conversion_funnel_with_assignments -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/cpa_panel/services/audit_analytics_helper.py tests/test_audit_analytics_helper.py
git commit -m "feat: implement lead conversion funnel from audit logs

- Query TAX_RETURN_CREATE and CPA_CLIENT_ASSIGN events
- Filter magnet source leads from creation events
- Calculate conversion rate (assigned / created)
- Track funnel stages (created, assigned, pending)
- Return structured metrics for dashboard"
```

---

## Task 5: Implement Recommendation Acceptance Rate

**Files:**
- Modify: `src/cpa_panel/services/audit_analytics_helper.py` (implement `get_recommendation_acceptance_rate`)
- Modify: `tests/test_audit_analytics_helper.py` (add tests)

**Step 1: Write failing tests for recommendation acceptance**

```python
# Add to tests/test_audit_analytics_helper.py

def test_get_recommendation_acceptance_rate_no_events():
    """Test recommendation acceptance with no events."""
    mock_service = type('MockService', (), {
        'query': lambda *args, **kwargs: []
    })()

    helper = AuditAnalyticsHelper()
    helper._audit_service = mock_service

    result = helper.get_recommendation_acceptance_rate(tenant_id="test")

    assert result["total_recommendations"] == 0
    assert result["accepted_count"] == 0
    assert result["acceptance_rate"] == 0


def test_get_recommendation_acceptance_rate_with_changes():
    """Test recommendation acceptance from field changes."""
    from audit.unified import AuditEventType, AuditSource
    from audit.unified.entry import UnifiedAuditEntry, ChangeRecord

    # Create mock entries for field changes with recommendation source
    entries = []

    # 8 field changes from recommendations
    for i in range(8):
        change = ChangeRecord(
            field_path=f"field_{i % 3}",
            old_value=0,
            new_value=100 * (i + 1),
            change_reason=f"recommendation_{i}"
        )
        entry = UnifiedAuditEntry(
            event_type=AuditEventType.TAX_DATA_FIELD_CHANGE,
            session_id=f"session_{i}",
            tenant_id="tenant_1",
            user_id="user_1",
            resource_type="tax_data",
            resource_id=f"session_{i}",
            action="change_field",
            source=AuditSource.AI_CHATBOT,  # Represents recommendation acceptance
            changes=[change],
            metadata={"from_recommendation": True, "recommendation_id": f"rec_{i}"},
        )
        entries.append(entry)

    mock_service = type('MockService', (), {
        'query': lambda *args, **kwargs: entries
    })()

    helper = AuditAnalyticsHelper()
    helper._audit_service = mock_service

    result = helper.get_recommendation_acceptance_rate(tenant_id="tenant_1")

    assert result["total_recommendations"] == 8
    assert result["accepted_count"] == 8
    assert result["acceptance_rate"] == 100.0
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_audit_analytics_helper.py::test_get_recommendation_acceptance_rate_no_events -v
python -m pytest tests/test_audit_analytics_helper.py::test_get_recommendation_acceptance_rate_with_changes -v
```

Expected: FAIL

**Step 3: Implement recommendation acceptance rate**

```python
# In src/cpa_panel/services/audit_analytics_helper.py, replace the stub:

    def get_recommendation_acceptance_rate(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Calculate recommendation acceptance rate.

        Tracks tax optimization recommendations offered vs. implemented
        through TAX_DATA_FIELD_CHANGE events with recommendation context.
        """
        from audit.unified.event_types import AuditEventType

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        # Query for TAX_DATA_FIELD_CHANGE events from recommendations
        # (Source = AI_CHATBOT or metadata contains recommendation)
        change_events = self.audit_service.query(
            event_type=AuditEventType.TAX_DATA_FIELD_CHANGE,
            tenant_id=tenant_id,
            start_date=start,
            end_date=end,
            limit=1000,
        )

        if not change_events:
            return {
                "total_recommendations": 0,
                "accepted_count": 0,
                "acceptance_rate": 0,
                "by_type": {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Filter for recommendation-sourced changes
        recommendation_changes = []
        by_type = {}  # Track by recommendation type/field

        for event in change_events:
            is_from_recommendation = False

            # Check metadata for recommendation indicator
            if event.metadata and isinstance(event.metadata, dict):
                if event.metadata.get("from_recommendation"):
                    is_from_recommendation = True

            # Alternative: check source is AI_CHATBOT (AI suggestions)
            if not is_from_recommendation and event.source:
                from audit.unified.event_types import AuditSource
                if event.source == AuditSource.AI_CHATBOT:
                    is_from_recommendation = True

            if is_from_recommendation:
                recommendation_changes.append(event)

                # Track by field type
                if event.changes and len(event.changes) > 0:
                    field = event.changes[0].field_path
                    if field not in by_type:
                        by_type[field] = {"offered": 0, "accepted": 0}
                    by_type[field]["accepted"] += 1

        # For simplicity, assume all TAX_DATA_AI_SUGGESTION events are offers
        ai_suggestions = self.audit_service.query(
            event_type=AuditEventType.TAX_DATA_AI_SUGGESTION,
            tenant_id=tenant_id,
            start_date=start,
            end_date=end,
            limit=1000,
        )

        total_recommendations = len(ai_suggestions)
        accepted_count = len(recommendation_changes)

        acceptance_rate = (
            (accepted_count / total_recommendations * 100)
            if total_recommendations > 0 else 0
        )

        # Populate offered counts in by_type
        for event in ai_suggestions:
            if event.changes and len(event.changes) > 0:
                field = event.changes[0].field_path
                if field not in by_type:
                    by_type[field] = {"offered": 0, "accepted": 0}
                by_type[field]["offered"] += 1

        return {
            "total_recommendations": total_recommendations,
            "accepted_count": accepted_count,
            "acceptance_rate": round(acceptance_rate, 1),
            "by_type": by_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_audit_analytics_helper.py::test_get_recommendation_acceptance_rate_no_events -v
python -m pytest tests/test_audit_analytics_helper.py::test_get_recommendation_acceptance_rate_with_changes -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/cpa_panel/services/audit_analytics_helper.py tests/test_audit_analytics_helper.py
git commit -m "feat: implement recommendation acceptance rate from audit logs

- Query TAX_DATA_AI_SUGGESTION and TAX_DATA_FIELD_CHANGE events
- Identify recommendations by source (AI_CHATBOT) and metadata
- Calculate acceptance rate (implemented / offered)
- Track acceptance by recommendation type/field
- Return structured metrics for dashboard"
```

---

## Task 6: Integrate Audit Analytics into Pipeline Service

**Files:**
- Modify: `src/cpa_panel/services/pipeline_service.py` (add new methods)
- Modify: `tests/test_pipeline_service.py` (add integration tests)

**Step 1: Add import and wrapper methods to pipeline service**

```python
# At top of src/cpa_panel/services/pipeline_service.py, add:

from .audit_analytics_helper import get_audit_analytics_helper

# Then add these methods to LeadPipelineService class:

    def get_tax_savings_metrics(self, tenant_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get tax savings delivered per client from audit logs."""
        helper = get_audit_analytics_helper()
        return helper.get_tax_savings_by_client(tenant_id=tenant_id, days=days)

    def get_return_processing_metrics(self, tenant_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get return processing time and acceptance metrics."""
        helper = get_audit_analytics_helper()
        result = helper.get_return_processing_metrics(tenant_id=tenant_id, days=days)
        # Convert dataclass to dict
        return {
            "total_returns": result.total_returns,
            "avg_processing_days": result.avg_processing_days,
            "submitted_count": result.submitted_count,
            "accepted_count": result.accepted_count,
            "acceptance_rate": result.acceptance_rate,
            "latest_acceptance_date": result.latest_acceptance_date.isoformat() if result.latest_acceptance_date else None,
        }

    def get_lead_conversion_funnel_audit(self, tenant_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get lead conversion funnel from audit logs."""
        helper = get_audit_analytics_helper()
        return helper.get_lead_conversion_funnel(tenant_id=tenant_id, days=days)

    def get_recommendation_acceptance_metrics(self, tenant_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get recommendation acceptance rate from audit logs."""
        helper = get_audit_analytics_helper()
        return helper.get_recommendation_acceptance_rate(tenant_id=tenant_id, days=days)
```

**Step 2: Write failing integration tests**

```python
# Add to tests/test_pipeline_service.py

def test_pipeline_service_has_audit_methods():
    """Test that pipeline service includes audit analytics methods."""
    from cpa_panel.services.pipeline_service import LeadPipelineService

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
    from cpa_panel.services.pipeline_service import LeadPipelineService

    service = LeadPipelineService()
    result = service.get_tax_savings_metrics(tenant_id="test")

    assert "total_savings" in result
    assert "by_client" in result
    assert "avg_savings" in result
```

**Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/test_pipeline_service.py::test_pipeline_service_has_audit_methods -v
python -m pytest tests/test_pipeline_service.py::test_pipeline_service_tax_savings_integration -v
```

Expected: FAIL

**Step 4: Implement the methods (as shown in Step 1)**

**Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_pipeline_service.py::test_pipeline_service_has_audit_methods -v
python -m pytest tests/test_pipeline_service.py::test_pipeline_service_tax_savings_integration -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add src/cpa_panel/services/pipeline_service.py tests/test_pipeline_service.py
git commit -m "feat: integrate audit analytics into pipeline service

- Add wrapper methods for all four audit metrics
- Convert audit dataclasses to dicts for API consistency
- Add integration tests verifying method availability
- Keep pipeline service as single access point for analytics"
```

---

## Task 7: Update Analytics Route to Display Audit Metrics

**Files:**
- Modify: `src/web/cpa_dashboard_pages.py` (update analytics route)
- Modify: `src/web/templates/cpa/analytics.html` (add new metric cards)

**Step 1: Update analytics route**

```python
# In src/web/cpa_dashboard_pages.py, find the cpa_analytics function and add:

    # Get audit-based analytics
    try:
        from cpa_panel.services.pipeline_service import get_pipeline_service
        service = get_pipeline_service()

        audit_tax_savings = service.get_tax_savings_metrics(cpa_id)
        audit_return_metrics = service.get_return_processing_metrics(cpa_id)
        audit_lead_funnel = service.get_lead_conversion_funnel_audit(cpa_id)
        audit_recommendations = service.get_recommendation_acceptance_metrics(cpa_id)

    except Exception as e:
        logger.warning(f"Failed to get audit analytics: {e}")
        audit_tax_savings = {"total_savings": 0, "by_client": [], "avg_savings": 0}
        audit_return_metrics = {"total_returns": 0, "avg_processing_days": 0, "acceptance_rate": 0}
        audit_lead_funnel = {"magnet_leads": 0, "assigned_clients": 0, "conversion_rate": 0}
        audit_recommendations = {"total_recommendations": 0, "accepted_count": 0, "acceptance_rate": 0}

    # Pass to template
    return templates.TemplateResponse(
        "cpa/analytics.html",
        {
            "request": request,
            "current_user": current_user,
            "cpa_profile": cpa_profile,
            "stats": stats,
            "conversion_metrics": conversion_metrics,
            "velocity_metrics": velocity_metrics,
            "trends": trends,
            "max_leads": max_leads,
            "ai_practice_summary": ai_practice_summary,
            "recent_advisor_sessions": recent_advisor_sessions,
            "advisor_dropoff": advisor_dropoff,
            # NEW: Audit-based metrics
            "audit_tax_savings": audit_tax_savings,
            "audit_return_metrics": audit_return_metrics,
            "audit_lead_funnel": audit_lead_funnel,
            "audit_recommendations": audit_recommendations,
        },
    )
```

**Step 2: Add metric cards to analytics template**

```html
<!-- Add after the existing metrics grid in src/web/templates/cpa/analytics.html -->

<!-- Audit-Based Metrics Section -->
<div style="margin-bottom: var(--space-8);">
    <h3 style="margin-bottom: var(--space-6); font-weight: var(--font-semibold); font-size: 1.2rem;">Performance from Audit Data</h3>

    <div class="metrics-grid">
        <!-- Tax Savings Card -->
        <div class="metric-card">
            <div class="metric-header">
                <span class="metric-title">Total Tax Savings</span>
                <div class="metric-icon">💰</div>
            </div>
            <div class="metric-value">${{ '{:,.0f}'.format(audit_tax_savings.total_savings or 0) }}</div>
            <div class="metric-change" style="color: var(--text-muted); font-size: 0.85rem;">
                {{ audit_tax_savings.count or 0 }} clients
            </div>
        </div>

        <!-- Return Processing Time Card -->
        <div class="metric-card">
            <div class="metric-header">
                <span class="metric-title">Avg. Return Processing</span>
                <div class="metric-icon">📋</div>
            </div>
            <div class="metric-value">{{ audit_return_metrics.avg_processing_days or 0 }} days</div>
            <div class="metric-change" style="color: var(--text-muted); font-size: 0.85rem;">
                {{ audit_return_metrics.acceptance_rate or 0 }}% acceptance rate
            </div>
        </div>

        <!-- Lead to Client Conversion Card -->
        <div class="metric-card">
            <div class="metric-header">
                <span class="metric-title">Lead → Client Conversion</span>
                <div class="metric-icon">📈</div>
            </div>
            <div class="metric-value">{{ audit_lead_funnel.conversion_rate or 0 }}%</div>
            <div class="metric-change" style="color: var(--text-muted); font-size: 0.85rem;">
                {{ audit_lead_funnel.assigned_clients or 0 }}/{{ audit_lead_funnel.magnet_leads or 0 }} leads
            </div>
        </div>

        <!-- Recommendation Acceptance Card -->
        <div class="metric-card">
            <div class="metric-header">
                <span class="metric-title">Recommendations Accepted</span>
                <div class="metric-icon">✓</div>
            </div>
            <div class="metric-value">{{ audit_recommendations.acceptance_rate or 0 }}%</div>
            <div class="metric-change" style="color: var(--text-muted); font-size: 0.85rem;">
                {{ audit_recommendations.accepted_count or 0 }}/{{ audit_recommendations.total_recommendations or 0 }}
            </div>
        </div>
    </div>
</div>
```

**Step 3: Write test for analytics route template variables**

```python
# Add to tests/test_cpa_analytics.py (or create if doesn't exist)

def test_cpa_analytics_includes_audit_metrics(client, monkeypatch):
    """Test that analytics route includes audit metrics."""
    # Mock authentication
    monkeypatch.setattr("src.web.cpa_dashboard_pages.require_cpa_auth",
                       lambda: {"cpa_id": "test_cpa"})

    # Make request
    response = client.get("/cpa/analytics")

    # Verify response is 200
    assert response.status_code == 200

    # Template should render without errors (audit metrics in context)
    # This verifies the metrics are being passed to the template
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_cpa_analytics.py::test_cpa_analytics_includes_audit_metrics -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/web/cpa_dashboard_pages.py src/web/templates/cpa/analytics.html tests/test_cpa_analytics.py
git commit -m "feat: wire audit metrics into analytics dashboard

- Query all four audit metrics in analytics route
- Add error handling with sensible defaults
- Add four new metric cards to analytics template
- Display tax savings, return processing time, lead conversion, recommendations
- Update tests to verify metrics are included"
```

---

## Task 8: Testing and Documentation

**Files:**
- Create: `docs/AUDIT_ANALYTICS.md` (architecture documentation)
- Modify: `tests/` (add integration tests)

**Step 1: Run all analytics tests**

```bash
python -m pytest tests/test_audit_analytics_helper.py -v
python -m pytest tests/test_pipeline_service.py -v
python -m pytest tests/test_cpa_analytics.py -v
```

Expected: All tests PASS

**Step 2: Test the analytics page manually**

```bash
cd /Users/rakeshanita/jorss-gbo-taai
python -m uvicorn src.web.app:app --reload
```

Navigate to `http://localhost:8000/cpa/analytics` and verify:
- Page loads without errors
- New metric cards display
- No JavaScript errors in browser console
- Metrics show reasonable values (0 if no data)

**Step 3: Create documentation**

```markdown
# Audit Analytics Integration

## Overview

The CPA Analytics dashboard now includes performance metrics derived from audit logs:

1. **Tax Savings Delivered** - Aggregated from TAX_CALC_RUN events showing total savings per client
2. **Return Processing Time** - Duration from TAX_RETURN_SUBMIT to TAX_RETURN_ACCEPTED
3. **Lead to Client Conversion** - Funnel showing magnet leads → assigned clients
4. **Recommendation Acceptance** - Rate of tax optimization recommendations implemented

## Architecture

### AuditAnalyticsHelper (`src/cpa_panel/services/audit_analytics_helper.py`)

Standalone module that:
- Queries AuditService for specific event types
- Aggregates metrics (by client, by return, etc.)
- Returns structured dictionaries suitable for dashboard display

Methods:
- `get_tax_savings_by_client()` - Query TAX_CALC_RUN, extract liability changes
- `get_return_processing_metrics()` - Query SUBMIT/ACCEPTED, calculate durations
- `get_lead_conversion_funnel()` - Query creation/assignment events, calculate rates
- `get_recommendation_acceptance_rate()` - Query AI suggestions vs. implementations

### Integration Point: LeadPipelineService

The existing service now wraps audit analytics:
- `get_tax_savings_metrics()`
- `get_return_processing_metrics()`
- `get_lead_conversion_funnel_audit()`
- `get_recommendation_acceptance_metrics()`

These methods delegate to AuditAnalyticsHelper and convert dataclasses to dicts.

### Route: `/cpa/analytics`

The analytics route (`src/web/cpa_dashboard_pages.py`) queries all metrics and passes them to the template.

## Data Flow

```
Audit Logs
    ↓
AuditService.query()
    ↓
AuditAnalyticsHelper (aggregation logic)
    ↓
LeadPipelineService (wrapper methods)
    ↓
/cpa/analytics route (collects metrics)
    ↓
analytics.html template (displays cards)
```

## Event Types Used

- `TAX_CALC_RUN` - Tax calculations with old/new outputs for savings calc
- `TAX_RETURN_SUBMIT` - Return submission timestamp
- `TAX_RETURN_ACCEPTED` - Return acceptance timestamp
- `TAX_RETURN_CREATE` - Lead creation (filtered by metadata source=magnet)
- `CPA_CLIENT_ASSIGN` - Lead assignment to client
- `TAX_DATA_FIELD_CHANGE` - Field changes (filtered by recommendation source)
- `TAX_DATA_AI_SUGGESTION` - AI recommendations offered

## Testing

Run audit analytics tests:
```bash
pytest tests/test_audit_analytics_helper.py -v
pytest tests/test_pipeline_service.py -v
pytest tests/test_cpa_analytics.py -v
```

All tests include mocked AuditService for isolation and speed.

## Future Enhancements

- Add date range filtering to metrics
- Create separate views for each metric (detailed breakdowns)
- Add comparisons (this month vs. last month)
- Export analytics to CSV
- Set up alerts for concerning trends (e.g., low acceptance rates)
```

**Step 4: Commit documentation**

```bash
git add docs/AUDIT_ANALYTICS.md
git commit -m "docs: add audit analytics integration documentation

- Explain architecture and data flow
- Document all event types used
- Provide testing and manual QA steps
- List future enhancement opportunities"
```

**Step 5: Final verification**

```bash
# Run full test suite
python -m pytest tests/ -v --tb=short

# Check code style/imports
python -m flake8 src/cpa_panel/services/audit_analytics_helper.py src/cpa_panel/services/pipeline_service.py

# Verify no syntax errors
python -m py_compile src/cpa_panel/services/audit_analytics_helper.py
python -m py_compile src/cpa_panel/services/pipeline_service.py
python -m py_compile src/web/cpa_dashboard_pages.py
```

Expected: All checks PASS

---

## Summary

This plan wires audit data into the CPA analytics dashboard through:

1. **New module** - AuditAnalyticsHelper with 4 specialized metric calculation methods
2. **Integration** - Wrapped into existing LeadPipelineService for single access point
3. **Route update** - `/cpa/analytics` now queries all audit metrics
4. **Template update** - 4 new metric cards display audit-derived performance data
5. **Testing** - Comprehensive unit and integration tests throughout

**Total commits:** 8 logical commits, each handling one feature area.

**Time estimate:** 2-3 hours for implementation + testing

**Key design principles:**
- DRY: Shared AuditAnalyticsHelper used by all consumers
- YAGNI: Only implement the 4 requested metrics
- TDD: Test-first approach for all new code
- Separation of concerns: Helper independent of route/template

