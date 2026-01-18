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
            "adjusted_gross_income": round(self.adjusted_gross_income, 2),
            "taxable_income": round(self.taxable_income, 2),
            "tax_liability": round(self.tax_liability, 2),
            "total_credits": round(self.total_credits, 2),
            "total_payments": round(self.total_payments, 2),
            "refund_or_owed": round(self.refund_or_owed, 2),
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
            "agi_change": round(self.agi_change, 2),
            "taxable_change": round(self.taxable_change, 2),
            "liability_change": round(self.liability_change, 2),
            "credits_change": round(self.credits_change, 2),
            "refund_change": round(self.refund_change, 2),
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
            "liability_pct": round(self.liability_pct, 2),
            "refund_pct": round(self.refund_pct, 2),
            "agi_pct": round(self.agi_pct, 2),
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
            "estimated_tax_change": round(tax_change, 2),
            "new_estimated_liability": round(current_liability + tax_change, 2),
            "marginal_rate_used": marginal_rate,
            "is_beneficial": tax_change < 0,
        }
