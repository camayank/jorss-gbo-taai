"""
Delta Analyzer for Before/After Impact Visualization

CPA AHA MOMENT: "One click, see the difference"

Shows instant impact of any change to help CPAs understand
the tax implications of adjustments.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of changes that can be analyzed."""
    INCOME = "income"
    WAGES = "wages"
    DEDUCTION = "deduction"
    CREDIT = "credit"
    RETIREMENT_CONTRIBUTION = "retirement_contribution"
    FILING_STATUS = "filing_status"
    DEPENDENTS = "dependents"
    STATE = "state"
    OTHER = "other"
    YEAR_OVER_YEAR = "year_over_year"  # P0: Prior year comparison


@dataclass
class TaxMetrics:
    """Tax metrics snapshot."""
    adjusted_gross_income: float = 0
    taxable_income: float = 0
    tax_liability: float = 0
    total_credits: float = 0
    total_payments: float = 0
    refund_or_owed: float = 0
    effective_rate: float = 0
    marginal_rate: float = 0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "adjusted_gross_income": float(money(self.adjusted_gross_income)),
            "taxable_income": float(money(self.taxable_income)),
            "tax_liability": float(money(self.tax_liability)),
            "total_credits": float(money(self.total_credits)),
            "total_payments": float(money(self.total_payments)),
            "refund_or_owed": float(money(self.refund_or_owed)),
            "effective_rate": round(self.effective_rate, 4),
            "marginal_rate": round(self.marginal_rate, 4),
        }


@dataclass
class DeltaMetrics:
    """Change in tax metrics."""
    agi_change: float = 0
    taxable_change: float = 0
    liability_change: float = 0
    credits_change: float = 0
    refund_change: float = 0
    effective_rate_change: float = 0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "agi_change": float(money(self.agi_change)),
            "taxable_change": float(money(self.taxable_change)),
            "liability_change": float(money(self.liability_change)),
            "credits_change": float(money(self.credits_change)),
            "refund_change": float(money(self.refund_change)),
            "effective_rate_change": round(self.effective_rate_change, 4),
        }

    @property
    def is_beneficial(self) -> bool:
        """Check if the change results in lower taxes."""
        return self.liability_change < 0 or self.refund_change > 0


@dataclass
class PercentageChanges:
    """Percentage changes in metrics."""
    liability_pct: float = 0
    refund_pct: float = 0
    agi_pct: float = 0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "liability_pct": float(money(self.liability_pct)),
            "refund_pct": float(money(self.refund_pct)),
            "agi_pct": float(money(self.agi_pct)),
        }


@dataclass
class DeltaResult:
    """Complete result of delta analysis."""
    session_id: str
    change_type: ChangeType
    field: str
    old_value: Any
    new_value: Any
    before: TaxMetrics
    after: TaxMetrics
    delta: DeltaMetrics
    percentage_changes: PercentageChanges
    marginal_rate_used: float
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)
    insights: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "change": {
                "type": self.change_type.value,
                "field": self.field,
                "old_value": self.old_value,
                "new_value": self.new_value,
                "delta": float(self.new_value) - float(self.old_value) if isinstance(self.new_value, (int, float)) else None,
            },
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "delta_metrics": self.delta.to_dict(),
            "percentage_changes": self.percentage_changes.to_dict(),
            "marginal_rate_used": self.marginal_rate_used,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "insights": self.insights,
            "is_beneficial": self.delta.is_beneficial,
            "visualization": {
                "type": "bar_comparison",
                "metrics": ["tax_liability", "refund_or_owed"],
                "highlight_change": True,
            }
        }


class DeltaAnalyzer:
    """
    Analyzes the impact of changes on tax outcomes.

    CPA AHA MOMENT: Shows instant before/after comparison
    to help CPAs understand the impact of any adjustment.
    """

    # Marginal rate lookup by taxable income (2025 single filer)
    MARGINAL_RATES = [
        (11925, 0.10),
        (48475, 0.12),
        (103350, 0.22),
        (197300, 0.24),
        (250500, 0.32),
        (626350, 0.35),
        (float('inf'), 0.37),
    ]

    def __init__(self):
        """Initialize delta analyzer."""
        pass

    def _get_marginal_rate(self, taxable_income: float, filing_status: str = "single") -> float:
        """
        Get marginal tax rate for given taxable income.

        Args:
            taxable_income: Taxable income amount
            filing_status: Filing status (affects brackets)

        Returns:
            Marginal tax rate as decimal
        """
        # Simplified - uses single filer brackets
        # In production, would adjust for filing status
        for threshold, rate in self.MARGINAL_RATES:
            if taxable_income <= threshold:
                return rate
        return 0.37

    def _calculate_effective_rate(self, tax_liability: float, agi: float) -> float:
        """Calculate effective tax rate."""
        if agi <= 0:
            return 0
        return tax_liability / agi

    def analyze_change(
        self,
        session_id: str,
        tax_return: Any,
        change_type: ChangeType,
        field: str,
        old_value: Any,
        new_value: Any,
    ) -> DeltaResult:
        """
        Analyze the impact of a proposed change.

        Args:
            session_id: Session/return identifier
            tax_return: Current TaxReturn object
            change_type: Type of change
            field: Field being changed
            old_value: Current value
            new_value: Proposed new value

        Returns:
            DeltaResult with complete analysis
        """
        # Extract current metrics from tax return
        current_agi = float(tax_return.adjusted_gross_income or 0)
        current_taxable = float(tax_return.taxable_income or 0)
        current_liability = float(tax_return.tax_liability or 0)
        current_credits = float(tax_return.total_credits or 0)
        current_payments = float(tax_return.total_payments or 0)
        current_refund = float(tax_return.refund_or_owed or 0)

        marginal_rate = self._get_marginal_rate(current_taxable)
        effective_rate = self._calculate_effective_rate(current_liability, current_agi)

        before = TaxMetrics(
            adjusted_gross_income=current_agi,
            taxable_income=current_taxable,
            tax_liability=current_liability,
            total_credits=current_credits,
            total_payments=current_payments,
            refund_or_owed=current_refund,
            effective_rate=effective_rate,
            marginal_rate=marginal_rate,
        )

        # Calculate estimated impact based on change type
        delta_amount = 0
        if isinstance(new_value, (int, float)) and isinstance(old_value, (int, float)):
            delta_amount = float(new_value) - float(old_value)

        # Estimate new values based on change type
        new_agi = current_agi
        new_taxable = current_taxable
        new_credits = current_credits
        tax_change = 0

        if change_type in [ChangeType.INCOME, ChangeType.WAGES]:
            new_agi = current_agi + delta_amount
            new_taxable = current_taxable + delta_amount
            tax_change = delta_amount * marginal_rate

        elif change_type == ChangeType.DEDUCTION:
            new_taxable = current_taxable - delta_amount
            tax_change = -delta_amount * marginal_rate

        elif change_type == ChangeType.CREDIT:
            new_credits = current_credits + delta_amount
            tax_change = -delta_amount  # Credits are dollar-for-dollar

        elif change_type == ChangeType.RETIREMENT_CONTRIBUTION:
            new_agi = current_agi - delta_amount
            new_taxable = current_taxable - delta_amount
            tax_change = -delta_amount * marginal_rate

        new_liability = current_liability + tax_change
        new_refund = current_refund - tax_change
        new_effective_rate = self._calculate_effective_rate(new_liability, new_agi)

        after = TaxMetrics(
            adjusted_gross_income=new_agi,
            taxable_income=new_taxable,
            tax_liability=new_liability,
            total_credits=new_credits,
            total_payments=current_payments,
            refund_or_owed=new_refund,
            effective_rate=new_effective_rate,
            marginal_rate=marginal_rate,
        )

        delta = DeltaMetrics(
            agi_change=new_agi - current_agi,
            taxable_change=new_taxable - current_taxable,
            liability_change=tax_change,
            credits_change=new_credits - current_credits,
            refund_change=new_refund - current_refund,
            effective_rate_change=new_effective_rate - effective_rate,
        )

        # Calculate percentage changes
        pct_changes = PercentageChanges(
            liability_pct=(tax_change / current_liability * 100) if current_liability else 0,
            refund_pct=((new_refund - current_refund) / abs(current_refund) * 100) if current_refund else 0,
            agi_pct=((new_agi - current_agi) / current_agi * 100) if current_agi else 0,
        )

        # Generate insights
        insights = self._generate_insights(change_type, delta_amount, delta, marginal_rate)

        return DeltaResult(
            session_id=session_id,
            change_type=change_type,
            field=field,
            old_value=old_value,
            new_value=new_value,
            before=before,
            after=after,
            delta=delta,
            percentage_changes=pct_changes,
            marginal_rate_used=marginal_rate,
            insights=insights,
        )

    def _generate_insights(
        self,
        change_type: ChangeType,
        delta_amount: float,
        delta: DeltaMetrics,
        marginal_rate: float,
    ) -> List[str]:
        """Generate human-readable insights about the change."""
        insights = []

        if delta.is_beneficial:
            insights.append(f"This change would reduce your tax liability by ${abs(delta.liability_change):,.2f}")
        else:
            insights.append(f"This change would increase your tax liability by ${abs(delta.liability_change):,.2f}")

        if change_type in [ChangeType.DEDUCTION, ChangeType.RETIREMENT_CONTRIBUTION]:
            savings = abs(delta_amount) * marginal_rate
            insights.append(f"At your {int(marginal_rate * 100)}% marginal rate, this saves ${savings:,.2f} in taxes")

        if change_type == ChangeType.INCOME and delta_amount > 0:
            additional_tax = delta_amount * marginal_rate
            insights.append(f"Each additional $1,000 of income adds ${marginal_rate * 1000:,.0f} to your tax bill")

        if delta.refund_change > 0:
            insights.append(f"Your refund would increase by ${delta.refund_change:,.2f}")
        elif delta.refund_change < 0 and delta.refund_change > -delta.liability_change:
            insights.append(f"Your refund would decrease by ${abs(delta.refund_change):,.2f}")

        return insights

    def quick_estimate(
        self,
        current_liability: float,
        marginal_rate: float,
        change_type: ChangeType,
        amount: float,
    ) -> Dict[str, float]:
        """
        Quick estimate without full tax return.

        Args:
            current_liability: Current tax liability
            marginal_rate: Marginal tax rate
            change_type: Type of change
            amount: Change amount

        Returns:
            Dict with estimated impact
        """
        if change_type in [ChangeType.INCOME, ChangeType.WAGES]:
            tax_change = amount * marginal_rate
        elif change_type in [ChangeType.DEDUCTION, ChangeType.RETIREMENT_CONTRIBUTION]:
            tax_change = -amount * marginal_rate
        elif change_type == ChangeType.CREDIT:
            tax_change = -amount
        else:
            tax_change = 0

        return {
            "estimated_tax_change": float(money(tax_change)),
            "new_estimated_liability": float(money(current_liability + tax_change)),
            "marginal_rate_used": marginal_rate,
            "is_beneficial": tax_change < 0,
        }

    # =========================================================================
    # P0: PRIOR YEAR COMPARISON
    # =========================================================================

    def compare_years(
        self,
        session_id: str,
        current_year_return: Any,
        prior_year_return: Any,
    ) -> Dict[str, Any]:
        """
        Compare current year return to prior year for CPA review.

        P0 CRITICAL: CPAs need year-over-year comparison to:
        1. Identify significant changes that need explanation
        2. Spot anomalies that may indicate errors or audit risk
        3. Prepare clients for conversations about variances

        Args:
            session_id: Session identifier
            current_year_return: Current TaxReturn object
            prior_year_return: Prior year TaxReturn object

        Returns:
            Comprehensive YoY comparison with insights
        """
        # Extract metrics from current year
        current = TaxMetrics(
            adjusted_gross_income=float(current_year_return.adjusted_gross_income or 0),
            taxable_income=float(current_year_return.taxable_income or 0),
            tax_liability=float(current_year_return.tax_liability or 0),
            total_credits=float(current_year_return.total_credits or 0),
            total_payments=float(current_year_return.total_payments or 0),
            refund_or_owed=float(current_year_return.refund_or_owed or 0),
            effective_rate=self._calculate_effective_rate(
                float(current_year_return.tax_liability or 0),
                float(current_year_return.adjusted_gross_income or 0)
            ),
            marginal_rate=self._get_marginal_rate(
                float(current_year_return.taxable_income or 0)
            ),
        )

        # Extract metrics from prior year
        prior = TaxMetrics(
            adjusted_gross_income=float(prior_year_return.adjusted_gross_income or 0),
            taxable_income=float(prior_year_return.taxable_income or 0),
            tax_liability=float(prior_year_return.tax_liability or 0),
            total_credits=float(prior_year_return.total_credits or 0),
            total_payments=float(prior_year_return.total_payments or 0),
            refund_or_owed=float(prior_year_return.refund_or_owed or 0),
            effective_rate=self._calculate_effective_rate(
                float(prior_year_return.tax_liability or 0),
                float(prior_year_return.adjusted_gross_income or 0)
            ),
            marginal_rate=self._get_marginal_rate(
                float(prior_year_return.taxable_income or 0)
            ),
        )

        # Calculate deltas
        delta = DeltaMetrics(
            agi_change=current.adjusted_gross_income - prior.adjusted_gross_income,
            taxable_change=current.taxable_income - prior.taxable_income,
            liability_change=current.tax_liability - prior.tax_liability,
            credits_change=current.total_credits - prior.total_credits,
            refund_change=current.refund_or_owed - prior.refund_or_owed,
            effective_rate_change=current.effective_rate - prior.effective_rate,
        )

        # Calculate percentage changes
        pct_changes = PercentageChanges(
            liability_pct=(delta.liability_change / prior.tax_liability * 100)
                if prior.tax_liability else 0,
            refund_pct=(delta.refund_change / abs(prior.refund_or_owed) * 100)
                if prior.refund_or_owed else 0,
            agi_pct=(delta.agi_change / prior.adjusted_gross_income * 100)
                if prior.adjusted_gross_income else 0,
        )

        # Generate YoY-specific insights
        insights = self._generate_yoy_insights(current, prior, delta, pct_changes)

        # Identify significant variances (>10% change flagged)
        significant_variances = self._identify_significant_variances(
            current, prior, delta, pct_changes
        )

        # Generate audit risk indicators
        audit_flags = self._assess_yoy_audit_risk(current, prior, delta, pct_changes)

        current_year = getattr(current_year_return, 'tax_year', 2025)
        prior_year = getattr(prior_year_return, 'tax_year', current_year - 1)

        return {
            "session_id": session_id,
            "comparison_type": "year_over_year",
            "current_year": current_year,
            "prior_year": prior_year,
            "current_year_metrics": current.to_dict(),
            "prior_year_metrics": prior.to_dict(),
            "delta_metrics": delta.to_dict(),
            "percentage_changes": pct_changes.to_dict(),
            "is_beneficial": delta.is_beneficial,
            "insights": insights,
            "significant_variances": significant_variances,
            "audit_risk_indicators": audit_flags,
            "cpa_review_required": len(significant_variances) > 0 or len(audit_flags) > 0,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "visualization": {
                "type": "yoy_bar_comparison",
                "metrics": ["tax_liability", "adjusted_gross_income", "refund_or_owed"],
                "highlight_variances": True,
            },
        }

    def _generate_yoy_insights(
        self,
        current: TaxMetrics,
        prior: TaxMetrics,
        delta: DeltaMetrics,
        pct: PercentageChanges,
    ) -> List[str]:
        """Generate year-over-year insights for CPA review."""
        insights = []

        # Income changes
        if abs(pct.agi_pct) > 10:
            direction = "increased" if delta.agi_change > 0 else "decreased"
            insights.append(
                f"AGI {direction} by ${abs(delta.agi_change):,.0f} ({abs(pct.agi_pct):.1f}%) year-over-year"
            )

        # Tax liability changes
        if abs(pct.liability_pct) > 10:
            direction = "increased" if delta.liability_change > 0 else "decreased"
            insights.append(
                f"Tax liability {direction} by ${abs(delta.liability_change):,.0f} ({abs(pct.liability_pct):.1f}%)"
            )

        # Effective rate changes
        if abs(delta.effective_rate_change) > 0.02:  # 2 percentage points
            direction = "higher" if delta.effective_rate_change > 0 else "lower"
            insights.append(
                f"Effective tax rate is {direction} ({current.effective_rate*100:.1f}% vs {prior.effective_rate*100:.1f}% last year)"
            )

        # Marginal rate bracket changes
        if current.marginal_rate != prior.marginal_rate:
            direction = "higher" if current.marginal_rate > prior.marginal_rate else "lower"
            insights.append(
                f"Taxpayer moved to a {direction} marginal bracket ({int(current.marginal_rate*100)}% vs {int(prior.marginal_rate*100)}%)"
            )

        # Credit changes
        if abs(delta.credits_change) > 500:
            direction = "increased" if delta.credits_change > 0 else "decreased"
            insights.append(
                f"Total credits {direction} by ${abs(delta.credits_change):,.0f}"
            )

        # Refund/owed changes
        if current.refund_or_owed > 0 and prior.refund_or_owed < 0:
            insights.append(
                f"Position changed from owing ${abs(prior.refund_or_owed):,.0f} to refund of ${current.refund_or_owed:,.0f}"
            )
        elif current.refund_or_owed < 0 and prior.refund_or_owed > 0:
            insights.append(
                f"Position changed from refund of ${prior.refund_or_owed:,.0f} to owing ${abs(current.refund_or_owed):,.0f}"
            )

        return insights

    def _identify_significant_variances(
        self,
        current: TaxMetrics,
        prior: TaxMetrics,
        delta: DeltaMetrics,
        pct: PercentageChanges,
    ) -> List[Dict[str, Any]]:
        """Identify significant variances requiring CPA explanation."""
        variances = []

        # >25% AGI change is very significant
        if abs(pct.agi_pct) > 25:
            variances.append({
                "metric": "adjusted_gross_income",
                "severity": "high",
                "change_pct": round(pct.agi_pct, 1),
                "change_amount": float(money(delta.agi_change)),
                "recommendation": "Document reason for significant income change",
            })
        elif abs(pct.agi_pct) > 10:
            variances.append({
                "metric": "adjusted_gross_income",
                "severity": "medium",
                "change_pct": round(pct.agi_pct, 1),
                "change_amount": float(money(delta.agi_change)),
                "recommendation": "Note income change for client discussion",
            })

        # >50% liability change
        if abs(pct.liability_pct) > 50:
            variances.append({
                "metric": "tax_liability",
                "severity": "high",
                "change_pct": round(pct.liability_pct, 1),
                "change_amount": float(money(delta.liability_change)),
                "recommendation": "Review all changes that drove liability variance",
            })
        elif abs(pct.liability_pct) > 20:
            variances.append({
                "metric": "tax_liability",
                "severity": "medium",
                "change_pct": round(pct.liability_pct, 1),
                "change_amount": float(money(delta.liability_change)),
                "recommendation": "Verify liability change aligns with income changes",
            })

        # Large credit changes
        if abs(delta.credits_change) > 2000:
            variances.append({
                "metric": "total_credits",
                "severity": "medium",
                "change_amount": float(money(delta.credits_change)),
                "recommendation": "Verify credit eligibility requirements are met",
            })

        return variances

    def _assess_yoy_audit_risk(
        self,
        current: TaxMetrics,
        prior: TaxMetrics,
        delta: DeltaMetrics,
        pct: PercentageChanges,
    ) -> List[Dict[str, Any]]:
        """Assess audit risk indicators based on YoY changes."""
        flags = []

        # Large AGI drop with same filing status could trigger scrutiny
        if delta.agi_change < -50000 and pct.agi_pct < -30:
            flags.append({
                "indicator": "significant_income_drop",
                "risk_level": "elevated",
                "description": "Large income decrease may trigger IRS inquiry",
                "recommendation": "Document job loss, retirement, or other reason for income drop",
            })

        # Large deduction increase relative to income
        deduction_increase = delta.agi_change - delta.taxable_change
        if deduction_increase > 20000 and current.adjusted_gross_income > 0:
            deduction_pct_of_income = deduction_increase / current.adjusted_gross_income * 100
            if deduction_pct_of_income > 15:
                flags.append({
                    "indicator": "deduction_spike",
                    "risk_level": "moderate",
                    "description": f"Deductions increased significantly ({deduction_pct_of_income:.0f}% of AGI)",
                    "recommendation": "Ensure all deductions are well-documented",
                })

        # Effective rate significantly below expected
        expected_min_rate = 0.10 if current.adjusted_gross_income > 50000 else 0.05
        if current.effective_rate < expected_min_rate and current.adjusted_gross_income > 30000:
            flags.append({
                "indicator": "low_effective_rate",
                "risk_level": "moderate",
                "description": f"Effective rate ({current.effective_rate*100:.1f}%) is below typical range",
                "recommendation": "Review credits and deductions for accuracy",
            })

        return flags
