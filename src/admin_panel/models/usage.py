"""
Usage Metrics Model - Tracks platform usage per firm.

Used for:
- Billing (usage-based features)
- Analytics dashboards
- Capacity planning
- Identifying upgrade opportunities
"""

from datetime import datetime, date
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.models import Base, JSONB
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal


class UsageMetrics(Base):
    """
    Usage Metrics - Aggregated usage data per firm per period.

    Captures key metrics for billing, analytics, and capacity planning.
    Metrics are aggregated daily/monthly for efficient querying.
    """
    __tablename__ = "usage_metrics"

    # Primary Key
    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign Key
    firm_id = Column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Time Period
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False)
    period_type = Column(String(20), default="monthly", comment="daily, weekly, monthly")

    # Return Metrics
    returns_created = Column(Integer, default=0)
    returns_filed = Column(Integer, default=0)
    returns_amended = Column(Integer, default=0)

    # Analysis Metrics
    scenarios_analyzed = Column(Integer, default=0)
    optimization_runs = Column(Integer, default=0)
    reports_generated = Column(Integer, default=0)

    # Document Metrics
    documents_uploaded = Column(Integer, default=0)
    documents_processed = Column(Integer, default=0)
    ocr_pages_processed = Column(Integer, default=0)
    storage_used_bytes = Column(Integer, default=0)

    # API Metrics (Enterprise)
    api_calls = Column(Integer, default=0)
    api_errors = Column(Integer, default=0)

    # Team Metrics
    active_team_members = Column(Integer, default=0)
    total_logins = Column(Integer, default=0)
    unique_users_active = Column(Integer, default=0)

    # Client Metrics
    active_clients = Column(Integer, default=0)
    new_clients = Column(Integer, default=0)
    clients_archived = Column(Integer, default=0)

    # Complexity Distribution (returns by tier)
    tier1_returns = Column(Integer, default=0, comment="Simple returns")
    tier2_returns = Column(Integer, default=0, comment="Standard returns")
    tier3_returns = Column(Integer, default=0, comment="Complex returns")
    tier4_returns = Column(Integer, default=0, comment="Very complex returns")
    tier5_returns = Column(Integer, default=0, comment="Enterprise/HNW returns")

    # Lead Metrics
    leads_generated = Column(Integer, default=0)
    leads_converted = Column(Integer, default=0)

    # Engagement Metrics
    engagement_letters_sent = Column(Integer, default=0)
    engagement_letters_signed = Column(Integer, default=0)

    # Detailed Breakdown (JSON for flexibility)
    breakdown = Column(JSONB, default=dict)
    # Example breakdown:
    # {
    #     "scenarios_by_type": {"filing_status": 10, "entity": 5, "what_if": 15},
    #     "documents_by_type": {"w2": 50, "1099": 30, "other": 20},
    #     "api_calls_by_endpoint": {"/analysis": 100, "/scenarios": 50}
    # }

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    firm = relationship("Firm", back_populates="usage_metrics")

    __table_args__ = (
        UniqueConstraint("firm_id", "period_start", "period_end", name="uq_usage_firm_period"),
        Index("ix_usage_firm_period", "firm_id", "period_start"),
        Index("ix_usage_period_type", "period_type", "period_start"),
    )

    def __repr__(self):
        return f"<UsageMetrics(firm={self.firm_id}, period={self.period_start})>"

    @property
    def total_returns(self) -> int:
        """Total returns by complexity tier."""
        return (
            self.tier1_returns +
            self.tier2_returns +
            self.tier3_returns +
            self.tier4_returns +
            self.tier5_returns
        )

    @property
    def storage_used_gb(self) -> float:
        """Storage used in GB."""
        return self.storage_used_bytes / (1024 * 1024 * 1024)

    @property
    def avg_complexity(self) -> float:
        """Average complexity tier."""
        total = self.total_returns
        if total == 0:
            return 0.0
        weighted = (
            self.tier1_returns * 1 +
            self.tier2_returns * 2 +
            self.tier3_returns * 3 +
            self.tier4_returns * 4 +
            self.tier5_returns * 5
        )
        return weighted / total

    @property
    def lead_conversion_rate(self) -> float:
        """Lead conversion rate percentage."""
        if self.leads_generated == 0:
            return 0.0
        return (self.leads_converted / self.leads_generated) * 100

    def increment(self, metric: str, amount: int = 1) -> None:
        """Increment a metric by the specified amount."""
        current = getattr(self, metric, 0) or 0
        setattr(self, metric, current + amount)

    def to_summary_dict(self) -> dict:
        """Return summary for dashboard display."""
        return {
            "period": {
                "start": self.period_start.isoformat() if self.period_start else None,
                "end": self.period_end.isoformat() if self.period_end else None,
            },
            "returns": {
                "created": self.returns_created,
                "filed": self.returns_filed,
                "total_by_complexity": self.total_returns,
                "avg_complexity": float(money(self.avg_complexity)),
            },
            "analysis": {
                "scenarios": self.scenarios_analyzed,
                "optimizations": self.optimization_runs,
                "reports": self.reports_generated,
            },
            "team": {
                "active_members": self.active_team_members,
                "total_logins": self.total_logins,
            },
            "clients": {
                "active": self.active_clients,
                "new": self.new_clients,
            },
            "leads": {
                "generated": self.leads_generated,
                "converted": self.leads_converted,
                "conversion_rate": round(self.lead_conversion_rate, 1),
            },
        }
