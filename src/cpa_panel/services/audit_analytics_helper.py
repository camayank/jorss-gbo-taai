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
