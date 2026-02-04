"""
Tax Drivers Analyzer - "What Drives Your Tax Outcome"

CLIENT AHA MOMENT: Clear visualization of what affects taxes most.

Helps clients understand:
- Where their income comes from
- How deductions save money
- What credits they're utilizing
- Their effective vs marginal rates
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)


class DriverDirection(str, Enum):
    """Direction of tax impact."""
    INCREASES = "increases"
    DECREASES = "decreases"
    NEUTRAL = "neutral"


@dataclass
class IncomeSource:
    """Breakdown of an income source."""
    source: str
    amount: float
    percentage_of_total: float = 0
    icon: str = "dollar-sign"
    tax_treatment: str = "ordinary"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "amount": float(money(self.amount)),
            "percentage_of_total": float(money(self.percentage_of_total)),
            "icon": self.icon,
            "tax_treatment": self.tax_treatment,
        }


@dataclass
class DeductionImpact:
    """Impact of deductions on taxes."""
    type: str  # "standard" or "itemized"
    amount: float
    tax_savings: float
    breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "amount": float(money(self.amount)),
            "tax_savings": float(money(self.tax_savings)),
            "breakdown": {k: float(money(v)) for k, v in self.breakdown.items()},
        }


@dataclass
class CreditUtilization:
    """Tax credit utilization."""
    name: str
    amount: float
    is_refundable: bool
    percentage_of_total: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "amount": float(money(self.amount)),
            "refundable": self.is_refundable,
            "percentage_of_total": float(money(self.percentage_of_total)),
        }


@dataclass
class TaxDriver:
    """A factor that drives tax outcome."""
    rank: int
    factor: str
    impact: str
    direction: DriverDirection
    dollar_amount: Optional[float] = None
    explanation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rank": self.rank,
            "factor": self.factor,
            "impact": self.impact,
            "direction": self.direction.value,
            "dollar_amount": float(money(self.dollar_amount)) if self.dollar_amount else None,
            "explanation": self.explanation,
        }


@dataclass
class TaxDriversResult:
    """Complete result of tax drivers analysis."""
    session_id: str
    summary: Dict[str, Any]
    income_breakdown: List[IncomeSource]
    deduction_impact: DeductionImpact
    credit_breakdown: List[CreditUtilization]
    top_drivers: List[TaxDriver]
    insights: Dict[str, str]
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "summary": self.summary,
            "income_breakdown": [s.to_dict() for s in self.income_breakdown],
            "deduction_impact": self.deduction_impact.to_dict(),
            "credit_breakdown": [c.to_dict() for c in self.credit_breakdown],
            "top_drivers": [d.to_dict() for d in self.top_drivers],
            "insights": self.insights,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
        }


class TaxDriversAnalyzer:
    """
    Analyzes what drives a taxpayer's tax outcome.

    CLIENT AHA MOMENT: Helps clients understand their taxes
    in clear, visual terms.
    """

    # 2025 standard deduction amounts
    STANDARD_DEDUCTIONS = {
        "single": 15750,
        "married_joint": 31500,
        "married_separate": 15750,
        "head_of_household": 23850,
        "widow": 31500,
    }

    # Income source icons
    INCOME_ICONS = {
        "wages": "briefcase",
        "interest": "percent",
        "dividends": "trending-up",
        "self_employment": "user-check",
        "capital_gains": "chart-line",
        "rental": "home",
        "social_security": "shield",
        "retirement": "piggy-bank",
        "other": "dollar-sign",
    }

    def __init__(self):
        """Initialize tax drivers analyzer."""
        pass

    def _get_marginal_rate(self, taxable_income: float, filing_status: str = "single") -> float:
        """Get marginal tax rate."""
        brackets = [
            (11925, 0.10),
            (48475, 0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250500, 0.32),
            (626350, 0.35),
            (float('inf'), 0.37),
        ]
        for threshold, rate in brackets:
            if taxable_income <= threshold:
                return rate
        return 0.37

    def analyze(self, session_id: str, tax_return: Any) -> TaxDriversResult:
        """
        Analyze tax drivers for a return.

        Args:
            session_id: Session/return identifier
            tax_return: TaxReturn object

        Returns:
            TaxDriversResult with complete analysis
        """
        # Extract income breakdown
        income_sources = self._analyze_income(tax_return)
        total_income = sum(s.amount for s in income_sources)

        # Calculate percentages
        for source in income_sources:
            if total_income > 0:
                source.percentage_of_total = (source.amount / total_income) * 100

        # Analyze deductions
        deduction_impact = self._analyze_deductions(tax_return)

        # Analyze credits
        credit_breakdown = self._analyze_credits(tax_return)

        # Calculate rates
        agi = float(tax_return.adjusted_gross_income or 0)
        taxable = float(tax_return.taxable_income or 0)
        liability = float(tax_return.tax_liability or 0)

        marginal_rate = self._get_marginal_rate(taxable)
        effective_rate = (liability / agi) if agi > 0 else 0

        # Calculate deduction tax savings
        deduction_impact.tax_savings = deduction_impact.amount * marginal_rate

        # Build summary
        summary = {
            "total_income": total_income,
            "adjusted_gross_income": agi,
            "taxable_income": taxable,
            "tax_liability": liability,
            "total_deductions": deduction_impact.amount,
            "total_credits": sum(c.amount for c in credit_breakdown),
            "effective_rate": float(money(effective_rate * 100)),
            "marginal_rate": float(money(marginal_rate * 100)),
        }

        # Generate top drivers
        top_drivers = self._generate_top_drivers(
            income_sources, deduction_impact, credit_breakdown,
            marginal_rate, tax_return
        )

        # Generate insights
        insights = self._generate_insights(
            effective_rate, marginal_rate, deduction_impact
        )

        return TaxDriversResult(
            session_id=session_id,
            summary=summary,
            income_breakdown=income_sources,
            deduction_impact=deduction_impact,
            credit_breakdown=credit_breakdown,
            top_drivers=top_drivers,
            insights=insights,
        )

    def _analyze_income(self, tax_return: Any) -> List[IncomeSource]:
        """Analyze income sources."""
        sources = []
        income = tax_return.income

        if not income:
            return sources

        # Wages from W-2s
        if income.w2_forms:
            wages = sum(w.wages for w in income.w2_forms)
            if wages > 0:
                sources.append(IncomeSource(
                    source="Wages & Salary",
                    amount=wages,
                    icon=self.INCOME_ICONS["wages"],
                    tax_treatment="ordinary",
                ))

        # Interest income
        if hasattr(income, 'interest_income') and income.interest_income:
            sources.append(IncomeSource(
                source="Interest Income",
                amount=income.interest_income,
                icon=self.INCOME_ICONS["interest"],
                tax_treatment="ordinary",
            ))

        # Dividend income
        if hasattr(income, 'dividend_income') and income.dividend_income:
            sources.append(IncomeSource(
                source="Dividend Income",
                amount=income.dividend_income,
                icon=self.INCOME_ICONS["dividends"],
                tax_treatment="qualified" if getattr(income, 'qualified_dividends', 0) else "ordinary",
            ))

        # Self-employment income
        if hasattr(income, 'self_employment_income') and income.self_employment_income:
            sources.append(IncomeSource(
                source="Self-Employment",
                amount=income.self_employment_income,
                icon=self.INCOME_ICONS["self_employment"],
                tax_treatment="se_tax",
            ))

        # Capital gains
        ltcg = getattr(income, 'long_term_capital_gains', 0) or 0
        stcg = getattr(income, 'short_term_capital_gains', 0) or 0
        if ltcg + stcg > 0:
            sources.append(IncomeSource(
                source="Capital Gains",
                amount=ltcg + stcg,
                icon=self.INCOME_ICONS["capital_gains"],
                tax_treatment="capital_gains",
            ))

        # Rental income
        rental = getattr(income, 'rental_income', 0) or 0
        if rental > 0:
            sources.append(IncomeSource(
                source="Rental Income",
                amount=rental,
                icon=self.INCOME_ICONS["rental"],
                tax_treatment="passive",
            ))

        return sources

    def _analyze_deductions(self, tax_return: Any) -> DeductionImpact:
        """Analyze deduction impact."""
        deductions = tax_return.deductions

        if not deductions:
            filing_status = tax_return.taxpayer.filing_status.value if tax_return.taxpayer else "single"
            return DeductionImpact(
                type="standard",
                amount=self.STANDARD_DEDUCTIONS.get(filing_status, 15000),
                tax_savings=0,
            )

        # Check if itemizing
        if deductions.itemized:
            itemized_total = deductions.itemized.get_total_itemized()
            if itemized_total > 0:
                return DeductionImpact(
                    type="itemized",
                    amount=itemized_total,
                    tax_savings=0,  # Calculated later with marginal rate
                    breakdown={
                        "state_local_taxes": deductions.itemized.state_local_taxes or 0,
                        "mortgage_interest": deductions.itemized.mortgage_interest or 0,
                        "charitable": (deductions.itemized.charitable_cash or 0) + (deductions.itemized.charitable_noncash or 0),
                        "medical": deductions.itemized.medical_expenses or 0,
                    }
                )

        # Standard deduction
        filing_status = tax_return.taxpayer.filing_status.value if tax_return.taxpayer else "single"
        return DeductionImpact(
            type="standard",
            amount=self.STANDARD_DEDUCTIONS.get(filing_status, 15000),
            tax_savings=0,
        )

    def _analyze_credits(self, tax_return: Any) -> List[CreditUtilization]:
        """Analyze credit utilization."""
        credits = []
        tax_credits = tax_return.credits

        if not tax_credits:
            return credits

        # Child Tax Credit
        ctc = getattr(tax_credits, 'child_tax_credit', 0) or 0
        if ctc > 0:
            credits.append(CreditUtilization(
                name="Child Tax Credit",
                amount=ctc,
                is_refundable=True,
            ))

        # Earned Income Credit
        eic = getattr(tax_credits, 'earned_income_credit', 0) or 0
        if eic > 0:
            credits.append(CreditUtilization(
                name="Earned Income Credit",
                amount=eic,
                is_refundable=True,
            ))

        # Education Credits
        edu = getattr(tax_credits, 'education_credits', 0) or 0
        if edu > 0:
            credits.append(CreditUtilization(
                name="Education Credits",
                amount=edu,
                is_refundable=False,
            ))

        # Child Care Credit
        care = getattr(tax_credits, 'child_care_credit', 0) or 0
        if care > 0:
            credits.append(CreditUtilization(
                name="Child Care Credit",
                amount=care,
                is_refundable=False,
            ))

        # Calculate percentages
        total = sum(c.amount for c in credits)
        for credit in credits:
            if total > 0:
                credit.percentage_of_total = (credit.amount / total) * 100

        return credits

    def _generate_top_drivers(
        self,
        income_sources: List[IncomeSource],
        deduction_impact: DeductionImpact,
        credit_breakdown: List[CreditUtilization],
        marginal_rate: float,
        tax_return: Any,
    ) -> List[TaxDriver]:
        """Generate top 5 tax drivers."""
        drivers = []
        rank = 1

        # #1: Primary income source
        if income_sources:
            largest = max(income_sources, key=lambda s: s.amount)
            drivers.append(TaxDriver(
                rank=rank,
                factor=f"Primary Income: {largest.source}",
                impact=f"${largest.amount:,.0f}",
                direction=DriverDirection.INCREASES,
                dollar_amount=largest.amount,
                explanation="Your largest source of taxable income",
            ))
            rank += 1

        # #2: Deduction
        if deduction_impact.amount > 0:
            drivers.append(TaxDriver(
                rank=rank,
                factor=f"{deduction_impact.type.title()} Deduction",
                impact=f"Saves ${deduction_impact.tax_savings:,.0f}",
                direction=DriverDirection.DECREASES,
                dollar_amount=-deduction_impact.tax_savings,
                explanation=f"Reduces taxable income by ${deduction_impact.amount:,.0f}",
            ))
            rank += 1

        # #3: Filing status
        if tax_return.taxpayer:
            status = tax_return.taxpayer.filing_status.value.replace('_', ' ').title()
            drivers.append(TaxDriver(
                rank=rank,
                factor=f"Filing Status: {status}",
                impact="Determines tax brackets",
                direction=DriverDirection.NEUTRAL,
                explanation="Affects standard deduction and bracket thresholds",
            ))
            rank += 1

        # #4: Credits
        total_credits = sum(c.amount for c in credit_breakdown)
        if total_credits > 0:
            drivers.append(TaxDriver(
                rank=rank,
                factor=f"Tax Credits ({len(credit_breakdown)})",
                impact=f"Saves ${total_credits:,.0f}",
                direction=DriverDirection.DECREASES,
                dollar_amount=-total_credits,
                explanation="Dollar-for-dollar reduction in taxes",
            ))
            rank += 1

        # #5: Tax bracket
        if marginal_rate > 0:
            drivers.append(TaxDriver(
                rank=rank,
                factor=f"Tax Bracket: {int(marginal_rate * 100)}%",
                impact=f"Each extra $1,000 costs ${marginal_rate * 1000:,.0f}",
                direction=DriverDirection.NEUTRAL,
                explanation="Your marginal rate affects the value of deductions",
            ))
            rank += 1

        return drivers[:5]

    def _generate_insights(
        self,
        effective_rate: float,
        marginal_rate: float,
        deduction_impact: DeductionImpact,
    ) -> Dict[str, str]:
        """Generate explanatory insights."""
        return {
            "rate_explanation": (
                f"You pay {round(effective_rate * 100, 1)}% of your income in federal taxes, "
                f"but each additional dollar earned is taxed at {round(marginal_rate * 100, 0)}%."
            ),
            "deduction_explanation": (
                f"Your {deduction_impact.type} deduction of ${deduction_impact.amount:,.0f} "
                f"saves you ${deduction_impact.tax_savings:,.0f} in taxes."
            ),
            "marginal_vs_effective": (
                f"While your marginal rate is {round(marginal_rate * 100, 0)}%, "
                f"your effective rate is only {round(effective_rate * 100, 1)}% "
                f"due to the progressive tax system and deductions."
            ),
        }
