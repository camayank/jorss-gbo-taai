"""
AI Metrics and Monitoring Service.

Comprehensive tracking of AI usage across all providers:
- Per-request metrics (tokens, latency, cost)
- Aggregated usage by provider, model, capability
- Cost management and budget alerts
- Performance monitoring
- Usage trends and analytics

Usage:
    from services.ai.metrics_service import get_ai_metrics_service

    metrics = get_ai_metrics_service()

    # Record a usage event
    metrics.record_usage(provider, model, tokens_in, tokens_out, latency_ms, cost)

    # Get usage summary
    summary = metrics.get_usage_summary(days=30)

    # Check budget
    budget_status = metrics.check_budget(monthly_limit=1000.0)
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json
import os

from config.ai_providers import AIProvider, ModelCapability, COST_PER_1K_TOKENS

logger = logging.getLogger(__name__)


class MetricPeriod(str, Enum):
    """Time periods for aggregation."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    ALL_TIME = "all_time"


@dataclass
class UsageRecord:
    """Single AI usage record."""
    timestamp: datetime
    provider: AIProvider
    model: str
    capability: Optional[ModelCapability]
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    cost: float
    success: bool
    error: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_type: Optional[str] = None  # "chat", "research", "reasoning", "extraction"


@dataclass
class UsageSummary:
    """Aggregated usage summary."""
    period: MetricPeriod
    start_date: datetime
    end_date: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    average_latency_ms: float
    by_provider: Dict[str, Dict[str, Any]]
    by_model: Dict[str, Dict[str, Any]]
    by_capability: Dict[str, Dict[str, Any]]
    by_request_type: Dict[str, Dict[str, Any]]
    top_users: List[Tuple[str, float]]  # (user_id, cost)


@dataclass
class BudgetStatus:
    """Budget monitoring status."""
    period: str
    budget_limit: float
    current_spend: float
    remaining: float
    usage_percentage: float
    projected_end_of_period: float
    is_over_budget: bool
    alert_level: str  # "normal", "warning", "critical"
    recommendations: List[str]


@dataclass
class PerformanceMetrics:
    """Performance metrics for a provider/model."""
    provider: str
    model: str
    period: MetricPeriod
    request_count: int
    success_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_tokens_per_request: float
    error_rate: float
    common_errors: List[Tuple[str, int]]


# =============================================================================
# AI METRICS SERVICE
# =============================================================================

class AIMetricsService:
    """
    Comprehensive AI usage metrics and monitoring.

    Features:
    - Real-time usage tracking
    - Cost aggregation and budgeting
    - Performance monitoring
    - Usage analytics
    - Alerting thresholds
    """

    def __init__(self, persist_path: Optional[str] = None):
        self._records: List[UsageRecord] = []
        self._persist_path = persist_path
        self._budget_alerts: List[Dict[str, Any]] = []
        self._max_records = 100000  # Keep last 100k records in memory

        # Load persisted data if available
        if persist_path and os.path.exists(persist_path):
            self._load_persisted_data()

    def record_usage(
        self,
        provider: AIProvider,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        cost: float,
        success: bool = True,
        error: Optional[str] = None,
        capability: Optional[ModelCapability] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_type: Optional[str] = None
    ):
        """
        Record an AI usage event.

        Args:
            provider: AI provider used
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
            latency_ms: Request latency in milliseconds
            cost: Estimated cost in USD
            success: Whether request succeeded
            error: Error message if failed
            capability: Model capability used
            user_id: Optional user identifier
            session_id: Optional session identifier
            request_type: Type of request (chat, research, etc.)
        """
        record = UsageRecord(
            timestamp=datetime.now(),
            provider=provider,
            model=model,
            capability=capability,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            cost=cost,
            success=success,
            error=error,
            user_id=user_id,
            session_id=session_id,
            request_type=request_type
        )

        self._records.append(record)

        # Trim old records if needed
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

        # Check budget alerts
        self._check_budget_alerts()

        # Log significant events
        if not success:
            logger.warning(f"AI request failed: {provider.value}/{model} - {error}")
        elif cost > 0.10:  # Log requests over 10 cents
            logger.info(f"High-cost AI request: ${cost:.4f} ({provider.value}/{model})")

    def get_usage_summary(
        self,
        period: MetricPeriod = MetricPeriod.MONTH,
        days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> UsageSummary:
        """
        Get aggregated usage summary.

        Args:
            period: Aggregation period
            days: Number of days (overrides period)
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            UsageSummary with aggregated metrics
        """
        now = datetime.now()

        # Determine date range
        if start_date and end_date:
            pass  # Use provided dates
        elif days:
            end_date = now
            start_date = now - timedelta(days=days)
        else:
            # Use period
            if period == MetricPeriod.HOUR:
                start_date = now - timedelta(hours=1)
            elif period == MetricPeriod.DAY:
                start_date = now - timedelta(days=1)
            elif period == MetricPeriod.WEEK:
                start_date = now - timedelta(weeks=1)
            elif period == MetricPeriod.MONTH:
                start_date = now - timedelta(days=30)
            else:
                start_date = datetime.min
            end_date = now

        # Filter records
        filtered = [r for r in self._records if start_date <= r.timestamp <= end_date]

        if not filtered:
            return UsageSummary(
                period=period,
                start_date=start_date,
                end_date=end_date,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                total_tokens=0,
                total_input_tokens=0,
                total_output_tokens=0,
                total_cost=0.0,
                average_latency_ms=0.0,
                by_provider={},
                by_model={},
                by_capability={},
                by_request_type={},
                top_users=[]
            )

        # Aggregate metrics
        total_requests = len(filtered)
        successful = sum(1 for r in filtered if r.success)
        failed = total_requests - successful
        total_tokens = sum(r.total_tokens for r in filtered)
        input_tokens = sum(r.input_tokens for r in filtered)
        output_tokens = sum(r.output_tokens for r in filtered)
        total_cost = sum(r.cost for r in filtered)
        avg_latency = sum(r.latency_ms for r in filtered) / len(filtered)

        # Aggregate by provider
        by_provider = self._aggregate_by_field(filtered, lambda r: r.provider.value)

        # Aggregate by model
        by_model = self._aggregate_by_field(filtered, lambda r: r.model)

        # Aggregate by capability
        by_capability = self._aggregate_by_field(
            filtered,
            lambda r: r.capability.value if r.capability else "unknown"
        )

        # Aggregate by request type
        by_request_type = self._aggregate_by_field(
            filtered,
            lambda r: r.request_type or "unknown"
        )

        # Top users by cost
        user_costs = defaultdict(float)
        for r in filtered:
            if r.user_id:
                user_costs[r.user_id] += r.cost
        top_users = sorted(user_costs.items(), key=lambda x: x[1], reverse=True)[:10]

        return UsageSummary(
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_requests=total_requests,
            successful_requests=successful,
            failed_requests=failed,
            total_tokens=total_tokens,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_cost=total_cost,
            average_latency_ms=avg_latency,
            by_provider=by_provider,
            by_model=by_model,
            by_capability=by_capability,
            by_request_type=by_request_type,
            top_users=top_users
        )

    def _aggregate_by_field(
        self,
        records: List[UsageRecord],
        field_getter
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate records by a field."""
        result = defaultdict(lambda: {
            "requests": 0,
            "tokens": 0,
            "cost": 0.0,
            "avg_latency_ms": 0.0,
            "success_rate": 0.0,
        })

        for r in records:
            key = field_getter(r)
            result[key]["requests"] += 1
            result[key]["tokens"] += r.total_tokens
            result[key]["cost"] += r.cost

        # Calculate averages
        for key in result:
            matching = [r for r in records if field_getter(r) == key]
            if matching:
                result[key]["avg_latency_ms"] = sum(r.latency_ms for r in matching) / len(matching)
                result[key]["success_rate"] = sum(1 for r in matching if r.success) / len(matching)

        return dict(result)

    def check_budget(
        self,
        monthly_limit: float,
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.95
    ) -> BudgetStatus:
        """
        Check budget status against limit.

        Args:
            monthly_limit: Monthly budget limit in USD
            warning_threshold: Percentage to trigger warning (0-1)
            critical_threshold: Percentage to trigger critical alert (0-1)

        Returns:
            BudgetStatus with current status and projections
        """
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get this month's usage
        monthly_records = [r for r in self._records if r.timestamp >= month_start]
        current_spend = sum(r.cost for r in monthly_records)

        remaining = monthly_limit - current_spend
        usage_pct = current_spend / monthly_limit if monthly_limit > 0 else 0

        # Project end-of-month spend
        days_elapsed = (now - month_start).days + 1
        days_in_month = 30  # Simplified
        daily_rate = current_spend / days_elapsed if days_elapsed > 0 else 0
        projected = daily_rate * days_in_month

        # Determine alert level
        if usage_pct >= critical_threshold:
            alert_level = "critical"
        elif usage_pct >= warning_threshold:
            alert_level = "warning"
        else:
            alert_level = "normal"

        # Generate recommendations
        recommendations = []
        if alert_level == "critical":
            recommendations.append("Consider switching to lower-cost models (GPT-4o-mini, Claude Haiku)")
            recommendations.append("Review high-usage users and sessions")
            recommendations.append("Enable stricter rate limiting")
        elif alert_level == "warning":
            recommendations.append("Monitor usage closely for the rest of the month")
            recommendations.append("Consider caching frequent queries")

        if projected > monthly_limit * 1.2:
            recommendations.append(f"Projected overspend: ${projected:.2f} (${monthly_limit:.2f} budget)")

        return BudgetStatus(
            period="monthly",
            budget_limit=monthly_limit,
            current_spend=current_spend,
            remaining=remaining,
            usage_percentage=usage_pct * 100,
            projected_end_of_period=projected,
            is_over_budget=current_spend > monthly_limit,
            alert_level=alert_level,
            recommendations=recommendations
        )

    def get_performance_metrics(
        self,
        provider: Optional[AIProvider] = None,
        model: Optional[str] = None,
        period: MetricPeriod = MetricPeriod.DAY
    ) -> List[PerformanceMetrics]:
        """
        Get performance metrics for providers/models.

        Args:
            provider: Filter by provider
            model: Filter by model
            period: Time period for metrics

        Returns:
            List of PerformanceMetrics
        """
        now = datetime.now()

        # Determine date range
        if period == MetricPeriod.HOUR:
            start = now - timedelta(hours=1)
        elif period == MetricPeriod.DAY:
            start = now - timedelta(days=1)
        elif period == MetricPeriod.WEEK:
            start = now - timedelta(weeks=1)
        else:
            start = now - timedelta(days=30)

        # Filter records
        filtered = [r for r in self._records if r.timestamp >= start]
        if provider:
            filtered = [r for r in filtered if r.provider == provider]
        if model:
            filtered = [r for r in filtered if r.model == model]

        # Group by provider/model
        groups = defaultdict(list)
        for r in filtered:
            key = (r.provider.value, r.model)
            groups[key].append(r)

        results = []
        for (prov, mod), records in groups.items():
            if not records:
                continue

            latencies = sorted([r.latency_ms for r in records])
            errors = [r.error for r in records if r.error]
            error_counts = defaultdict(int)
            for e in errors:
                error_counts[e] += 1

            results.append(PerformanceMetrics(
                provider=prov,
                model=mod,
                period=period,
                request_count=len(records),
                success_rate=sum(1 for r in records if r.success) / len(records),
                avg_latency_ms=sum(latencies) / len(latencies),
                p50_latency_ms=latencies[len(latencies) // 2] if latencies else 0,
                p95_latency_ms=latencies[int(len(latencies) * 0.95)] if latencies else 0,
                p99_latency_ms=latencies[int(len(latencies) * 0.99)] if latencies else 0,
                avg_tokens_per_request=sum(r.total_tokens for r in records) / len(records),
                error_rate=len(errors) / len(records),
                common_errors=sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ))

        return results

    def get_cost_breakdown(
        self,
        days: int = 30,
        group_by: str = "provider"  # "provider", "model", "capability", "user"
    ) -> Dict[str, float]:
        """
        Get cost breakdown by category.

        Args:
            days: Number of days to analyze
            group_by: Grouping dimension

        Returns:
            Dict mapping category to cost
        """
        start = datetime.now() - timedelta(days=days)
        filtered = [r for r in self._records if r.timestamp >= start]

        result = defaultdict(float)

        for r in filtered:
            if group_by == "provider":
                key = r.provider.value
            elif group_by == "model":
                key = r.model
            elif group_by == "capability":
                key = r.capability.value if r.capability else "unknown"
            elif group_by == "user":
                key = r.user_id or "anonymous"
            else:
                key = "total"

            result[key] += r.cost

        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def get_usage_trends(
        self,
        days: int = 30,
        granularity: str = "day"  # "hour", "day", "week"
    ) -> List[Dict[str, Any]]:
        """
        Get usage trends over time.

        Args:
            days: Number of days to analyze
            granularity: Time granularity

        Returns:
            List of time-series data points
        """
        start = datetime.now() - timedelta(days=days)
        filtered = [r for r in self._records if r.timestamp >= start]

        # Group by time bucket
        buckets = defaultdict(lambda: {
            "requests": 0,
            "tokens": 0,
            "cost": 0.0,
            "errors": 0
        })

        for r in filtered:
            if granularity == "hour":
                key = r.timestamp.replace(minute=0, second=0, microsecond=0)
            elif granularity == "day":
                key = r.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            else:  # week
                key = r.timestamp - timedelta(days=r.timestamp.weekday())
                key = key.replace(hour=0, minute=0, second=0, microsecond=0)

            buckets[key]["requests"] += 1
            buckets[key]["tokens"] += r.total_tokens
            buckets[key]["cost"] += r.cost
            if not r.success:
                buckets[key]["errors"] += 1

        return [
            {
                "timestamp": ts.isoformat(),
                **data
            }
            for ts, data in sorted(buckets.items())
        ]

    def _check_budget_alerts(self):
        """Check and record budget alerts."""
        # This would typically integrate with alerting system
        pass

    def _load_persisted_data(self):
        """Load persisted metrics data."""
        try:
            with open(self._persist_path, 'r') as f:
                data = json.load(f)
                # Convert to UsageRecord objects
                for item in data:
                    item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                    item['provider'] = AIProvider(item['provider'])
                    if item.get('capability'):
                        item['capability'] = ModelCapability(item['capability'])
                    self._records.append(UsageRecord(**item))
        except Exception as e:
            logger.warning(f"Failed to load persisted metrics: {e}")

    def persist(self):
        """Persist current metrics to disk."""
        if not self._persist_path:
            return

        try:
            data = []
            for r in self._records[-10000:]:  # Keep last 10k for persistence
                data.append({
                    'timestamp': r.timestamp.isoformat(),
                    'provider': r.provider.value,
                    'model': r.model,
                    'capability': r.capability.value if r.capability else None,
                    'input_tokens': r.input_tokens,
                    'output_tokens': r.output_tokens,
                    'total_tokens': r.total_tokens,
                    'latency_ms': r.latency_ms,
                    'cost': r.cost,
                    'success': r.success,
                    'error': r.error,
                    'user_id': r.user_id,
                    'session_id': r.session_id,
                    'request_type': r.request_type,
                })

            with open(self._persist_path, 'w') as f:
                json.dump(data, f)

        except Exception as e:
            logger.error(f"Failed to persist metrics: {e}")

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive data for a metrics dashboard.

        Returns:
            Dict with all key metrics for visualization
        """
        hourly = self.get_usage_summary(MetricPeriod.HOUR)
        daily = self.get_usage_summary(MetricPeriod.DAY)
        monthly = self.get_usage_summary(MetricPeriod.MONTH)

        return {
            "current": {
                "last_hour": {
                    "requests": hourly.total_requests,
                    "cost": hourly.total_cost,
                    "tokens": hourly.total_tokens,
                    "success_rate": hourly.successful_requests / hourly.total_requests if hourly.total_requests else 1.0,
                },
                "today": {
                    "requests": daily.total_requests,
                    "cost": daily.total_cost,
                    "tokens": daily.total_tokens,
                    "success_rate": daily.successful_requests / daily.total_requests if daily.total_requests else 1.0,
                },
                "this_month": {
                    "requests": monthly.total_requests,
                    "cost": monthly.total_cost,
                    "tokens": monthly.total_tokens,
                    "success_rate": monthly.successful_requests / monthly.total_requests if monthly.total_requests else 1.0,
                },
            },
            "by_provider": monthly.by_provider,
            "by_model": monthly.by_model,
            "trends": self.get_usage_trends(days=7, granularity="hour"),
            "performance": [
                {
                    "provider": m.provider,
                    "model": m.model,
                    "avg_latency_ms": m.avg_latency_ms,
                    "success_rate": m.success_rate,
                }
                for m in self.get_performance_metrics(period=MetricPeriod.DAY)
            ],
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_ai_metrics_service: Optional[AIMetricsService] = None


def get_ai_metrics_service() -> AIMetricsService:
    """Get the singleton AI metrics service instance."""
    global _ai_metrics_service
    if _ai_metrics_service is None:
        _ai_metrics_service = AIMetricsService()
    return _ai_metrics_service


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AIMetricsService",
    "UsageRecord",
    "UsageSummary",
    "BudgetStatus",
    "PerformanceMetrics",
    "MetricPeriod",
    "get_ai_metrics_service",
]
