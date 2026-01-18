"""
Practice Intelligence Service

READ-ONLY portfolio analytics for CPA firms.

SCOPE BOUNDARIES (ENFORCED - 3 METRICS ONLY):
1. Advisory vs Compliance Mix
2. Complexity Tier Distribution
3. YoY Value Surface

FORBIDDEN (DO NOT ADD):
- Time tracking
- Staff productivity
- Revenue per staff
- Utilization metrics
- Any PMS features

This is an ANALYTICS module, not a MANAGEMENT module.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EngagementType(str, Enum):
    """Types of tax engagements."""
    TAX_PREPARATION = "tax_preparation"      # Compliance
    TAX_ADVISORY = "tax_advisory"            # Advisory
    TAX_PLANNING = "tax_planning"            # Advisory
    AMENDED_RETURN = "amended_return"        # Compliance
    AUDIT_REPRESENTATION = "audit_representation"  # Advisory


class ComplexityTier(str, Enum):
    """Return complexity tiers (from pricing module)."""
    TIER_1_SIMPLE = "tier_1_simple"
    TIER_2_MODERATE = "tier_2_moderate"
    TIER_3_COMPLEX = "tier_3_complex"
    TIER_4_HIGH_NET_WORTH = "tier_4_high_net_worth"
    TIER_5_ULTRA_COMPLEX = "tier_5_ultra_complex"


@dataclass
class AdvisoryComplianceMix:
    """
    Metric 1: Advisory vs Compliance Mix

    Shows the distribution of engagement types to help
    CPA firms understand their practice composition.
    """
    advisory_count: int
    compliance_count: int
    advisory_percentage: float
    compliance_percentage: float
    breakdown: Dict[str, int]  # EngagementType -> count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "advisory_count": self.advisory_count,
            "compliance_count": self.compliance_count,
            "advisory_percentage": round(self.advisory_percentage, 1),
            "compliance_percentage": round(self.compliance_percentage, 1),
            "breakdown": self.breakdown,
            "insight": self._generate_insight(),
        }

    def _generate_insight(self) -> str:
        """Generate insight about the mix."""
        if self.advisory_percentage >= 40:
            return "Strong advisory practice - positioned well for premium pricing"
        elif self.advisory_percentage >= 20:
            return "Balanced practice - opportunity to grow advisory services"
        else:
            return "Compliance-heavy practice - consider adding tax planning services"


@dataclass
class ComplexityDistribution:
    """
    Metric 2: Complexity Tier Distribution

    Shows the count of returns by complexity tier.
    """
    distribution: Dict[str, int]  # ComplexityTier -> count
    total_returns: int
    average_complexity_score: float  # 1.0 to 5.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "distribution": self.distribution,
            "total_returns": self.total_returns,
            "average_complexity_score": round(self.average_complexity_score, 2),
            "percentages": self._calculate_percentages(),
            "insight": self._generate_insight(),
        }

    def _calculate_percentages(self) -> Dict[str, float]:
        """Calculate percentage for each tier."""
        if self.total_returns == 0:
            return {}
        return {
            tier: round((count / self.total_returns) * 100, 1)
            for tier, count in self.distribution.items()
        }

    def _generate_insight(self) -> str:
        """Generate insight about complexity distribution."""
        if self.average_complexity_score >= 4.0:
            return "High-complexity practice - ensure adequate review processes"
        elif self.average_complexity_score >= 2.5:
            return "Mixed complexity portfolio - good diversification"
        else:
            return "Lower complexity portfolio - efficient for volume processing"


@dataclass
class YoYValueSurface:
    """
    Metric 3: Year-over-Year Value Surface

    Compares key metrics between tax years to surface trends.
    NOT for revenue tracking - for TAX VALUE comparisons.
    """
    current_year: int
    prior_year: int

    # Tax-related metrics (NOT revenue)
    avg_refund_current: float
    avg_refund_prior: float
    avg_tax_liability_current: float
    avg_tax_liability_prior: float
    avg_deductions_current: float
    avg_deductions_prior: float

    # Volume metrics
    returns_current: int
    returns_prior: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_year": self.current_year,
            "prior_year": self.prior_year,
            "refund_comparison": {
                "current_avg": round(self.avg_refund_current, 2),
                "prior_avg": round(self.avg_refund_prior, 2),
                "change_pct": self._safe_pct_change(
                    self.avg_refund_current, self.avg_refund_prior
                ),
            },
            "tax_liability_comparison": {
                "current_avg": round(self.avg_tax_liability_current, 2),
                "prior_avg": round(self.avg_tax_liability_prior, 2),
                "change_pct": self._safe_pct_change(
                    self.avg_tax_liability_current, self.avg_tax_liability_prior
                ),
            },
            "deductions_comparison": {
                "current_avg": round(self.avg_deductions_current, 2),
                "prior_avg": round(self.avg_deductions_prior, 2),
                "change_pct": self._safe_pct_change(
                    self.avg_deductions_current, self.avg_deductions_prior
                ),
            },
            "volume_comparison": {
                "current": self.returns_current,
                "prior": self.returns_prior,
                "change_pct": self._safe_pct_change(
                    self.returns_current, self.returns_prior
                ),
            },
            "insights": self._generate_insights(),
        }

    def _safe_pct_change(self, current: float, prior: float) -> Optional[float]:
        """Calculate percentage change safely."""
        if prior == 0:
            return None
        return round(((current - prior) / prior) * 100, 1)

    def _generate_insights(self) -> List[str]:
        """Generate YoY insights."""
        insights = []

        # Refund trend
        refund_change = self._safe_pct_change(
            self.avg_refund_current, self.avg_refund_prior
        )
        if refund_change is not None:
            if refund_change > 10:
                insights.append(
                    f"Average refunds up {refund_change}% - clients benefiting from tax planning"
                )
            elif refund_change < -10:
                insights.append(
                    f"Average refunds down {abs(refund_change)}% - review withholding guidance"
                )

        # Tax liability trend
        liability_change = self._safe_pct_change(
            self.avg_tax_liability_current, self.avg_tax_liability_prior
        )
        if liability_change is not None:
            if liability_change > 15:
                insights.append(
                    f"Tax liabilities up {liability_change}% - opportunity for tax planning"
                )

        # Deductions trend
        deductions_change = self._safe_pct_change(
            self.avg_deductions_current, self.avg_deductions_prior
        )
        if deductions_change is not None:
            if deductions_change < -10:
                insights.append(
                    f"Average deductions down {abs(deductions_change)}% - ensure all deductions captured"
                )

        return insights if insights else ["No significant YoY variances detected"]


@dataclass
class PortfolioMetrics:
    """
    Complete portfolio metrics for a tenant.

    Contains ONLY the 3 allowed metrics:
    1. Advisory vs Compliance Mix
    2. Complexity Tier Distribution
    3. YoY Value Surface
    """
    tenant_id: str
    as_of: datetime
    advisory_mix: AdvisoryComplianceMix
    complexity_distribution: ComplexityDistribution
    yoy_surface: Optional[YoYValueSurface]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "as_of": self.as_of.isoformat(),
            "metrics": {
                "advisory_compliance_mix": self.advisory_mix.to_dict(),
                "complexity_distribution": self.complexity_distribution.to_dict(),
                "yoy_value_surface": self.yoy_surface.to_dict() if self.yoy_surface else None,
            },
            "scope_notice": (
                "This dashboard provides portfolio analytics only. "
                "For practice management features (time tracking, billing, etc.), "
                "integrate with your PMS (Karbon, Canopy, Jetpack)."
            ),
        }


class PracticeIntelligenceService:
    """
    Service for practice intelligence analytics.

    SCOPE: 3 metrics ONLY.

    1. Advisory vs Compliance Mix
    2. Complexity Tier Distribution
    3. YoY Value Surface

    This is NOT a practice management service.
    DO NOT ADD: time tracking, staff productivity, revenue metrics.
    """

    # Classification of engagement types
    ADVISORY_TYPES = {
        EngagementType.TAX_ADVISORY,
        EngagementType.TAX_PLANNING,
        EngagementType.AUDIT_REPRESENTATION,
    }

    COMPLIANCE_TYPES = {
        EngagementType.TAX_PREPARATION,
        EngagementType.AMENDED_RETURN,
    }

    # Complexity tier scoring (1-5)
    TIER_SCORES = {
        ComplexityTier.TIER_1_SIMPLE: 1.0,
        ComplexityTier.TIER_2_MODERATE: 2.0,
        ComplexityTier.TIER_3_COMPLEX: 3.0,
        ComplexityTier.TIER_4_HIGH_NET_WORTH: 4.0,
        ComplexityTier.TIER_5_ULTRA_COMPLEX: 5.0,
    }

    def __init__(self):
        """Initialize intelligence service."""
        pass  # Stateless service

    def calculate_advisory_mix(
        self,
        engagements: List[Dict[str, Any]],
    ) -> AdvisoryComplianceMix:
        """
        Metric 1: Calculate advisory vs compliance mix.

        Args:
            engagements: List of engagement records with 'engagement_type' field

        Returns:
            AdvisoryComplianceMix with distribution data
        """
        breakdown: Dict[str, int] = {}
        advisory_count = 0
        compliance_count = 0

        for eng in engagements:
            eng_type = eng.get("engagement_type", "tax_preparation")
            breakdown[eng_type] = breakdown.get(eng_type, 0) + 1

            # Classify as advisory or compliance
            try:
                engagement_enum = EngagementType(eng_type)
                if engagement_enum in self.ADVISORY_TYPES:
                    advisory_count += 1
                else:
                    compliance_count += 1
            except ValueError:
                # Unknown type defaults to compliance
                compliance_count += 1

        total = advisory_count + compliance_count
        advisory_pct = (advisory_count / total * 100) if total > 0 else 0
        compliance_pct = (compliance_count / total * 100) if total > 0 else 0

        return AdvisoryComplianceMix(
            advisory_count=advisory_count,
            compliance_count=compliance_count,
            advisory_percentage=advisory_pct,
            compliance_percentage=compliance_pct,
            breakdown=breakdown,
        )

    def calculate_complexity_distribution(
        self,
        returns: List[Dict[str, Any]],
    ) -> ComplexityDistribution:
        """
        Metric 2: Calculate complexity tier distribution.

        Args:
            returns: List of return records with 'complexity_tier' field

        Returns:
            ComplexityDistribution with tier counts
        """
        distribution: Dict[str, int] = {
            tier.value: 0 for tier in ComplexityTier
        }

        total_score = 0.0

        for ret in returns:
            tier_value = ret.get("complexity_tier", ComplexityTier.TIER_2_MODERATE.value)

            # Increment count
            if tier_value in distribution:
                distribution[tier_value] += 1
            else:
                distribution[ComplexityTier.TIER_2_MODERATE.value] += 1
                tier_value = ComplexityTier.TIER_2_MODERATE.value

            # Add to score
            try:
                tier_enum = ComplexityTier(tier_value)
                total_score += self.TIER_SCORES.get(tier_enum, 2.0)
            except ValueError:
                total_score += 2.0  # Default to moderate

        total_returns = len(returns)
        avg_score = total_score / total_returns if total_returns > 0 else 2.0

        return ComplexityDistribution(
            distribution=distribution,
            total_returns=total_returns,
            average_complexity_score=avg_score,
        )

    def calculate_yoy_surface(
        self,
        current_year_returns: List[Dict[str, Any]],
        prior_year_returns: List[Dict[str, Any]],
        current_year: int,
        prior_year: int,
    ) -> YoYValueSurface:
        """
        Metric 3: Calculate year-over-year value surface.

        Args:
            current_year_returns: Returns for current tax year
            prior_year_returns: Returns for prior tax year
            current_year: Current tax year (e.g., 2024)
            prior_year: Prior tax year (e.g., 2023)

        Returns:
            YoYValueSurface with comparison data
        """
        def avg_field(returns: List[Dict[str, Any]], field: str) -> float:
            values = [r.get(field, 0) for r in returns if r.get(field) is not None]
            return sum(values) / len(values) if values else 0

        return YoYValueSurface(
            current_year=current_year,
            prior_year=prior_year,
            avg_refund_current=avg_field(current_year_returns, "refund_amount"),
            avg_refund_prior=avg_field(prior_year_returns, "refund_amount"),
            avg_tax_liability_current=avg_field(current_year_returns, "total_tax"),
            avg_tax_liability_prior=avg_field(prior_year_returns, "total_tax"),
            avg_deductions_current=avg_field(current_year_returns, "total_deductions"),
            avg_deductions_prior=avg_field(prior_year_returns, "total_deductions"),
            returns_current=len(current_year_returns),
            returns_prior=len(prior_year_returns),
        )

    def get_portfolio_metrics(
        self,
        tenant_id: str,
        engagements: List[Dict[str, Any]],
        current_year_returns: List[Dict[str, Any]],
        prior_year_returns: Optional[List[Dict[str, Any]]] = None,
        current_year: int = 2024,
        prior_year: int = 2023,
    ) -> PortfolioMetrics:
        """
        Get complete portfolio metrics.

        This method returns ONLY the 3 allowed metrics.

        Args:
            tenant_id: Tenant identifier
            engagements: List of engagement records
            current_year_returns: Returns for current tax year
            prior_year_returns: Returns for prior tax year (optional)
            current_year: Current tax year
            prior_year: Prior tax year

        Returns:
            PortfolioMetrics with all 3 metrics
        """
        advisory_mix = self.calculate_advisory_mix(engagements)
        complexity_dist = self.calculate_complexity_distribution(current_year_returns)

        yoy_surface = None
        if prior_year_returns:
            yoy_surface = self.calculate_yoy_surface(
                current_year_returns=current_year_returns,
                prior_year_returns=prior_year_returns,
                current_year=current_year,
                prior_year=prior_year,
            )

        return PortfolioMetrics(
            tenant_id=tenant_id,
            as_of=datetime.utcnow(),
            advisory_mix=advisory_mix,
            complexity_distribution=complexity_dist,
            yoy_surface=yoy_surface,
        )


# Singleton instance
_intelligence_service: Optional[PracticeIntelligenceService] = None


def get_intelligence_service() -> PracticeIntelligenceService:
    """Get the global practice intelligence service instance."""
    global _intelligence_service
    if _intelligence_service is None:
        _intelligence_service = PracticeIntelligenceService()
    return _intelligence_service
