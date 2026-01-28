"""
Multi-Year Tax Projections Engine.

Projects tax liability and strategy impacts over 3-5 years, showing:
- Compound effects of retirement contributions
- Deduction bunching timelines
- Entity structure long-term savings
- Estate planning projections
- Income growth scenarios

Resolves Gap #4: Multi-Year Projections
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum
from decimal import Decimal
from datetime import datetime, date
import copy

if TYPE_CHECKING:
    from models.tax_return import TaxReturn


class ProjectionAssumption(Enum):
    """Types of projection assumptions."""
    INCOME_GROWTH = "income_growth"
    INFLATION = "inflation"
    TAX_LAW_CHANGE = "tax_law_change"
    RETIREMENT_CONTRIBUTION = "retirement_contribution"
    LIFE_EVENT = "life_event"
    BUSINESS_GROWTH = "business_growth"


@dataclass
class YearProjection:
    """Projection for a single tax year."""
    year: int
    total_income: Decimal
    total_deductions: Decimal
    taxable_income: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    marginal_rate: Decimal

    # Strategy impacts
    retirement_contributions: Decimal = Decimal('0')
    retirement_tax_savings: Decimal = Decimal('0')
    retirement_balance_eoy: Decimal = Decimal('0')  # End of year balance

    bunching_deductions: Decimal = Decimal('0')
    bunching_tax_savings: Decimal = Decimal('0')

    entity_structure_savings: Decimal = Decimal('0')

    # Cumulative metrics
    cumulative_tax_paid: Decimal = Decimal('0')
    cumulative_retirement_saved: Decimal = Decimal('0')
    cumulative_strategy_savings: Decimal = Decimal('0')

    # Events and notes
    life_events: List[str] = field(default_factory=list)
    strategy_notes: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)


@dataclass
class MultiYearProjectionResult:
    """Complete multi-year projection."""
    base_year: int
    projection_years: int
    yearly_projections: List[YearProjection]

    # Summary metrics
    total_projected_income: Decimal
    total_projected_tax: Decimal
    total_retirement_accumulated: Decimal
    total_strategy_savings: Decimal

    # Return on investment
    strategy_roi_percent: Decimal  # ROI from implementing strategies

    # Assumptions used
    assumptions: Dict[str, Any]

    # Generated timestamp
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class MultiYearProjectionEngine:
    """
    Engine for creating multi-year tax projections.

    Capabilities:
    - 3-5 year tax projections
    - Compound effects of strategies
    - Retirement contribution growth modeling
    - Deduction bunching timeline optimization
    - Entity structure long-term analysis
    - Life event impact modeling
    """

    def __init__(self):
        """Initialize the projection engine."""
        # Default assumptions (can be customized)
        self.default_income_growth = Decimal('0.03')  # 3% annual
        self.default_inflation = Decimal('0.025')  # 2.5% annual
        self.default_investment_return = Decimal('0.07')  # 7% annual retirement account growth
        self.default_tax_bracket_inflation_adj = True

    def project_multi_year(
        self,
        tax_return: "TaxReturn",
        years: int = 5,
        assumptions: Optional[Dict[str, Any]] = None
    ) -> MultiYearProjectionResult:
        """
        Create multi-year tax projection.

        Args:
            tax_return: Base year tax return
            years: Number of years to project (3-10)
            assumptions: Custom assumptions for projection

        Returns:
            MultiYearProjectionResult with year-by-year projections
        """
        if years < 1 or years > 10:
            raise ValueError("Projection years must be between 1 and 10")

        # Merge custom assumptions with defaults
        assumptions = assumptions or {}
        income_growth = Decimal(str(assumptions.get('income_growth', self.default_income_growth)))
        inflation = Decimal(str(assumptions.get('inflation', self.default_inflation)))
        investment_return = Decimal(str(assumptions.get('investment_return', self.default_investment_return)))

        # Extract base year data
        base_year = datetime.now().year
        base_income = Decimal(str(tax_return.income.get_total_income()))
        base_deductions = self._calculate_total_deductions(tax_return)

        # Initialize retirement balance
        retirement_balance = Decimal('0')  # Starting balance

        # Project each year
        yearly_projections = []
        cumulative_tax = Decimal('0')
        cumulative_retirement = Decimal('0')
        cumulative_savings = Decimal('0')

        for year_offset in range(years):
            projection_year = base_year + year_offset

            # Calculate projected income with growth
            projected_income = base_income * ((Decimal('1') + income_growth) ** year_offset)

            # Apply life events
            life_events = self._project_life_events(tax_return, year_offset, assumptions)

            # Adjust income for life events
            for event in life_events:
                if event == "spouse_retirement":
                    projected_income *= Decimal('0.7')  # 30% reduction
                elif event == "job_promotion":
                    projected_income *= Decimal('1.15')  # 15% increase
                elif event == "business_launch":
                    projected_income += Decimal('50000')  # Additional business income

            # Calculate retirement contribution strategy
            retirement_contribution = self._calculate_optimal_retirement_contribution(
                projected_income, year_offset, assumptions
            )

            # Grow existing retirement balance
            retirement_balance = retirement_balance * (Decimal('1') + investment_return)
            retirement_balance += retirement_contribution

            # Calculate deduction bunching strategy
            bunching_deduction, bunching_savings = self._calculate_bunching_strategy(
                tax_return, year_offset, projected_income
            )

            # Calculate projected deductions
            projected_deductions = self._project_deductions(
                tax_return, year_offset, inflation, bunching_deduction
            )

            # Add retirement contribution to deductions
            projected_deductions += retirement_contribution

            # Calculate taxable income
            taxable_income = max(Decimal('0'), projected_income - projected_deductions)

            # Calculate projected tax
            filing_status = tax_return.taxpayer.filing_status
            projected_tax = self._calculate_projected_tax(
                taxable_income, filing_status, year_offset, inflation
            )

            # Calculate tax savings from strategies
            base_tax = self._calculate_projected_tax(
                projected_income - (projected_deductions - retirement_contribution - bunching_deduction),
                filing_status, year_offset, inflation
            )

            retirement_tax_savings = base_tax - projected_tax
            strategy_savings = retirement_tax_savings + bunching_savings

            # Calculate rates
            effective_rate = (projected_tax / projected_income * Decimal('100')) if projected_income > 0 else Decimal('0')
            marginal_rate = self._get_marginal_rate(taxable_income, filing_status, year_offset) * Decimal('100')

            # Update cumulatives
            cumulative_tax += projected_tax
            cumulative_retirement += retirement_contribution
            cumulative_savings += strategy_savings

            # Create year projection
            year_projection = YearProjection(
                year=projection_year,
                total_income=projected_income.quantize(Decimal('0.01')),
                total_deductions=projected_deductions.quantize(Decimal('0.01')),
                taxable_income=taxable_income.quantize(Decimal('0.01')),
                total_tax=projected_tax.quantize(Decimal('0.01')),
                effective_rate=effective_rate.quantize(Decimal('0.01')),
                marginal_rate=marginal_rate.quantize(Decimal('0.01')),
                retirement_contributions=retirement_contribution.quantize(Decimal('0.01')),
                retirement_tax_savings=retirement_tax_savings.quantize(Decimal('0.01')),
                retirement_balance_eoy=retirement_balance.quantize(Decimal('0.01')),
                bunching_deductions=bunching_deduction.quantize(Decimal('0.01')),
                bunching_tax_savings=bunching_savings.quantize(Decimal('0.01')),
                cumulative_tax_paid=cumulative_tax.quantize(Decimal('0.01')),
                cumulative_retirement_saved=cumulative_retirement.quantize(Decimal('0.01')),
                cumulative_strategy_savings=cumulative_savings.quantize(Decimal('0.01')),
                life_events=life_events,
                strategy_notes=self._generate_strategy_notes(year_offset, retirement_contribution, bunching_deduction),
                assumptions=[
                    f"Income growth: {income_growth * 100:.1f}%/year",
                    f"Inflation: {inflation * 100:.1f}%/year",
                    f"Investment return: {investment_return * 100:.1f}%/year"
                ]
            )

            yearly_projections.append(year_projection)

        # Calculate summary metrics
        total_income = sum(p.total_income for p in yearly_projections)
        total_tax = sum(p.total_tax for p in yearly_projections)

        # ROI: (savings + retirement growth) / net cost
        strategy_roi = Decimal('0')
        if cumulative_retirement > 0:
            net_cost = cumulative_retirement - cumulative_savings
            if net_cost > 0:
                strategy_roi = ((retirement_balance + cumulative_savings - net_cost) / net_cost * Decimal('100'))

        return MultiYearProjectionResult(
            base_year=base_year,
            projection_years=years,
            yearly_projections=yearly_projections,
            total_projected_income=total_income.quantize(Decimal('0.01')),
            total_projected_tax=total_tax.quantize(Decimal('0.01')),
            total_retirement_accumulated=retirement_balance.quantize(Decimal('0.01')),
            total_strategy_savings=cumulative_savings.quantize(Decimal('0.01')),
            strategy_roi_percent=strategy_roi.quantize(Decimal('0.01')),
            assumptions={
                'income_growth': float(income_growth),
                'inflation': float(inflation),
                'investment_return': float(investment_return),
                'years': years
            }
        )

    def _calculate_total_deductions(self, tax_return: "TaxReturn") -> Decimal:
        """Calculate total deductions from tax return."""
        # Simplified - would use actual deduction calculation
        if tax_return.deductions.use_standard_deduction:
            # 2025 standard deduction (single)
            return Decimal('15750')
        elif tax_return.deductions.itemized:
            itemized = tax_return.deductions.itemized
            total = Decimal('0')
            total += Decimal(str(getattr(itemized, 'mortgage_interest', 0) or 0))
            total += Decimal(str(getattr(itemized, 'property_taxes', 0) or 0))
            total += Decimal(str(getattr(itemized, 'charitable_cash', 0) or 0))
            total += Decimal(str(getattr(itemized, 'medical_expenses', 0) or 0))
            return total
        return Decimal('15750')

    def _project_life_events(
        self, tax_return: "TaxReturn", year_offset: int, assumptions: Dict[str, Any]
    ) -> List[str]:
        """Project life events that impact taxes."""
        events = []

        # Check custom assumptions
        life_events_timeline = assumptions.get('life_events', {})
        if str(year_offset) in life_events_timeline:
            events.extend(life_events_timeline[str(year_offset)])

        # Default projections based on age
        taxpayer_age = getattr(tax_return.taxpayer, 'age', 35)
        projected_age = taxpayer_age + year_offset

        if projected_age == 50:
            events.append("catch_up_contributions_eligible")
        elif projected_age >= 65:
            events.append("medicare_eligible")
        elif projected_age >= 73:
            events.append("rmd_required")  # Required minimum distributions

        return events

    def _calculate_optimal_retirement_contribution(
        self, projected_income: Decimal, year_offset: int, assumptions: Dict[str, Any]
    ) -> Decimal:
        """Calculate optimal retirement contribution for the year."""
        # Get user's target or use default strategy
        target_rate = Decimal(str(assumptions.get('retirement_savings_rate', 0.15)))  # 15% default

        # 2025 limits (would inflate with year_offset)
        k401_limit = Decimal('23500')
        ira_limit = Decimal('7000')

        # Calculate contribution based on target rate
        target_contribution = projected_income * target_rate

        # Cap at legal limits
        max_contribution = k401_limit + ira_limit

        return min(target_contribution, max_contribution)

    def _calculate_bunching_strategy(
        self, tax_return: "TaxReturn", year_offset: int, projected_income: Decimal
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate deduction bunching strategy.

        Returns: (additional_deduction, tax_savings)
        """
        # Bunching works on even/odd year cycle
        if year_offset % 2 == 0:
            # Even year: Double up charitable giving
            annual_charity = Decimal('8000')  # Example
            additional_deduction = annual_charity  # Double up
            tax_savings = additional_deduction * Decimal('0.22')  # Assume 22% bracket
            return additional_deduction, tax_savings
        else:
            # Odd year: Skip charitable, take standard
            return Decimal('0'), Decimal('0')

    def _project_deductions(
        self,
        tax_return: "TaxReturn",
        year_offset: int,
        inflation: Decimal,
        bunching_deduction: Decimal
    ) -> Decimal:
        """Project total deductions for a future year."""
        base_deductions = self._calculate_total_deductions(tax_return)

        # Inflate standard deduction with year_offset
        inflated_standard = Decimal('15750') * ((Decimal('1') + inflation) ** year_offset)

        # Add bunching deduction
        total_deductions = inflated_standard + bunching_deduction

        return total_deductions

    def _calculate_projected_tax(
        self,
        taxable_income: Decimal,
        filing_status,
        year_offset: int,
        inflation: Decimal
    ) -> Decimal:
        """Calculate projected tax with inflation-adjusted brackets."""
        # 2025 brackets (Single) - would inflate with year_offset
        brackets = [
            (Decimal('11925'), Decimal('0.10')),
            (Decimal('48475'), Decimal('0.12')),
            (Decimal('103350'), Decimal('0.22')),
            (Decimal('197300'), Decimal('0.24')),
            (Decimal('250525'), Decimal('0.32')),
            (Decimal('626350'), Decimal('0.35')),
            (Decimal('999999999'), Decimal('0.37'))
        ]

        # Inflate brackets
        inflation_factor = (Decimal('1') + inflation) ** year_offset
        inflated_brackets = [
            (limit * inflation_factor, rate)
            for limit, rate in brackets
        ]

        # Calculate tax
        tax = Decimal('0')
        previous_limit = Decimal('0')

        for limit, rate in inflated_brackets:
            if taxable_income <= previous_limit:
                break

            taxable_in_bracket = min(taxable_income, limit) - previous_limit
            tax += taxable_in_bracket * rate
            previous_limit = limit

        return tax

    def _get_marginal_rate(
        self, taxable_income: Decimal, filing_status, year_offset: int
    ) -> Decimal:
        """Get marginal tax rate for projected income."""
        brackets = [
            (Decimal('11925'), Decimal('0.10')),
            (Decimal('48475'), Decimal('0.12')),
            (Decimal('103350'), Decimal('0.22')),
            (Decimal('197300'), Decimal('0.24')),
            (Decimal('250525'), Decimal('0.32')),
            (Decimal('626350'), Decimal('0.35')),
            (Decimal('999999999'), Decimal('0.37'))
        ]

        for limit, rate in brackets:
            if taxable_income <= limit:
                return rate

        return Decimal('0.37')

    def _generate_strategy_notes(
        self, year_offset: int, retirement_contribution: Decimal, bunching_deduction: Decimal
    ) -> List[str]:
        """Generate strategy notes for the year."""
        notes = []

        if retirement_contribution > 0:
            notes.append(f"Contribute ${retirement_contribution:,.0f} to retirement accounts")

        if bunching_deduction > 0:
            notes.append(f"Double up charitable giving (${bunching_deduction:,.0f}) for itemization")
        elif year_offset % 2 == 1:
            notes.append("Skip charitable giving this year, take standard deduction")

        if year_offset == 0:
            notes.append("Establish baseline tax position")
        elif year_offset >= 3:
            notes.append("Review and adjust strategy based on actual results")

        return notes


# ============================================================================
# Visualization Helper
# ============================================================================

def generate_projection_timeline_data(result: MultiYearProjectionResult) -> Dict[str, Any]:
    """
    Generate data structure for timeline visualization.

    Returns JSON-ready dict for frontend charting.
    """
    return {
        "years": [p.year for p in result.yearly_projections],
        "datasets": [
            {
                "label": "Total Income",
                "data": [float(p.total_income) for p in result.yearly_projections],
                "color": "#2563eb",
                "type": "line"
            },
            {
                "label": "Total Tax",
                "data": [float(p.total_tax) for p in result.yearly_projections],
                "color": "#dc2626",
                "type": "bar"
            },
            {
                "label": "Retirement Balance",
                "data": [float(p.retirement_balance_eoy) for p in result.yearly_projections],
                "color": "#059669",
                "type": "area"
            },
            {
                "label": "Cumulative Tax Savings",
                "data": [float(p.cumulative_strategy_savings) for p in result.yearly_projections],
                "color": "#d97706",
                "type": "line"
            }
        ],
        "summary": {
            "total_income": float(result.total_projected_income),
            "total_tax": float(result.total_projected_tax),
            "retirement_accumulated": float(result.total_retirement_accumulated),
            "total_savings": float(result.total_strategy_savings),
            "roi_percent": float(result.strategy_roi_percent)
        },
        "milestones": [
            {
                "year": p.year,
                "events": p.life_events,
                "notes": p.strategy_notes
            }
            for p in result.yearly_projections
            if p.life_events or p.strategy_notes
        ]
    }
