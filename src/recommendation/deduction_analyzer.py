"""Deduction Analyzer.

Analyzes and recommends the optimal deduction strategy (standard vs itemized)
based on the taxpayer's specific deductions and filing status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from models.tax_return import TaxReturn
    from calculator.tax_calculator import TaxCalculator


class DeductionStrategy(Enum):
    """Deduction strategy options."""
    STANDARD = "standard"
    ITEMIZED = "itemized"


@dataclass
class ItemizedDeductionBreakdown:
    """Detailed breakdown of itemized deductions."""
    # Medical and Dental
    medical_expenses_total: float = 0.0
    medical_agi_threshold: float = 0.0  # 7.5% of AGI
    medical_deduction_allowed: float = 0.0

    # Taxes Paid (SALT)
    state_local_income_tax: float = 0.0
    property_tax: float = 0.0
    real_estate_tax: float = 0.0
    personal_property_tax: float = 0.0
    salt_total: float = 0.0
    salt_cap: float = 10000.0  # $10,000 SALT cap
    salt_deduction_allowed: float = 0.0

    # Interest Paid
    mortgage_interest: float = 0.0
    mortgage_points: float = 0.0
    investment_interest: float = 0.0
    total_interest_deduction: float = 0.0

    # Charitable Contributions
    cash_contributions: float = 0.0
    non_cash_contributions: float = 0.0
    carryover_contributions: float = 0.0
    charitable_limit_percent: float = 60.0  # 60% of AGI for most
    charitable_deduction_allowed: float = 0.0

    # Casualty and Theft Losses
    casualty_losses_federally_declared: float = 0.0

    # Other Itemized
    gambling_losses: float = 0.0  # Limited to gambling winnings
    other_deductions: float = 0.0

    # Totals
    total_itemized_deductions: float = 0.0

    def calculate_totals(self, agi: float, gambling_winnings: float = 0.0) -> None:
        """Calculate all totals and limits based on AGI."""
        # Medical (only amounts exceeding 7.5% of AGI)
        self.medical_agi_threshold = agi * 0.075
        self.medical_deduction_allowed = max(0.0, self.medical_expenses_total - self.medical_agi_threshold)

        # SALT (capped at $10,000)
        self.salt_total = (self.state_local_income_tax + self.property_tax +
                         self.real_estate_tax + self.personal_property_tax)
        self.salt_deduction_allowed = min(self.salt_total, self.salt_cap)

        # Interest
        self.total_interest_deduction = (self.mortgage_interest +
                                        self.mortgage_points +
                                        self.investment_interest)

        # Charitable (capped at percentage of AGI)
        total_charitable = (self.cash_contributions +
                          self.non_cash_contributions +
                          self.carryover_contributions)
        charitable_limit = agi * (self.charitable_limit_percent / 100)
        self.charitable_deduction_allowed = min(total_charitable, charitable_limit)

        # Gambling losses limited to winnings
        self.gambling_losses = min(self.gambling_losses, gambling_winnings)

        # Total itemized deductions
        self.total_itemized_deductions = (
            self.medical_deduction_allowed +
            self.salt_deduction_allowed +
            self.total_interest_deduction +
            self.charitable_deduction_allowed +
            self.casualty_losses_federally_declared +
            self.gambling_losses +
            self.other_deductions
        )


@dataclass
class DeductionAnalysis:
    """Analysis comparing standard vs itemized deductions."""
    filing_status: str
    adjusted_gross_income: float

    # Standard deduction info
    standard_deduction_base: float
    additional_standard_deduction: float  # Age 65+ or blind
    total_standard_deduction: float

    # Itemized breakdown
    itemized_breakdown: ItemizedDeductionBreakdown
    total_itemized_deductions: float

    # Recommendation
    recommended_strategy: str
    deduction_difference: float  # Positive = itemized saves more
    tax_savings_estimate: float  # Estimated tax savings from optimal choice

    # Details
    marginal_rate: float
    itemized_categories: Dict[str, float] = field(default_factory=dict)
    optimization_opportunities: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class DeductionRecommendation:
    """Complete deduction recommendation with strategies."""
    analysis: DeductionAnalysis
    recommended_strategy: str
    confidence_score: float  # 0-100
    explanation: str

    # Actionable recommendations
    current_year_actions: List[str] = field(default_factory=list)
    next_year_planning: List[str] = field(default_factory=list)
    bunching_strategy: Optional[Dict[str, Any]] = None


class DeductionAnalyzer:
    """
    Analyzes deduction strategies and recommends optimal approach.

    This analyzer compares standard vs itemized deductions, identifies
    optimization opportunities, and provides actionable recommendations
    including multi-year bunching strategies.
    """

    # 2025 Standard Deduction amounts (IRS Rev. Proc. 2024-40)
    STANDARD_DEDUCTIONS_2025 = {
        "single": 15750,
        "married_joint": 31500,
        "married_separate": 15750,
        "head_of_household": 23625,
        "qualifying_widow": 31500,
    }

    # Additional standard deduction for age 65+ or blind (2025 amounts)
    ADDITIONAL_STANDARD_2025 = {
        "single": 1950,
        "married_joint": 1550,
        "married_separate": 1550,
        "head_of_household": 1950,
        "qualifying_widow": 1550,
    }

    def __init__(self, calculator: Optional["TaxCalculator"] = None):
        """Initialize the analyzer with an optional calculator."""
        self._calculator = calculator

    def analyze(self, tax_return: "TaxReturn") -> DeductionRecommendation:
        """
        Analyze deduction options and provide recommendation.

        Args:
            tax_return: The tax return to analyze

        Returns:
            DeductionRecommendation with analysis and strategies
        """
        filing_status = self._normalize_filing_status(
            tax_return.taxpayer.filing_status.value
        )
        agi = tax_return.adjusted_gross_income or 0.0

        # Calculate standard deduction
        standard_base = self.STANDARD_DEDUCTIONS_2025.get(filing_status, 15750)
        additional_standard = self._calculate_additional_standard(
            tax_return, filing_status
        )
        total_standard = standard_base + additional_standard

        # Calculate itemized deductions
        itemized_breakdown = self._calculate_itemized(tax_return, agi)
        total_itemized = itemized_breakdown.total_itemized_deductions

        # Determine recommended strategy
        deduction_difference = total_itemized - total_standard
        if deduction_difference > 0:
            recommended_strategy = DeductionStrategy.ITEMIZED.value
        else:
            recommended_strategy = DeductionStrategy.STANDARD.value

        # Get marginal rate for tax savings calculation
        marginal_rate = self._get_marginal_rate(filing_status, agi)
        tax_savings = abs(deduction_difference) * (marginal_rate / 100)

        # Build category breakdown
        categories = self._build_categories(itemized_breakdown)

        # Generate optimization opportunities
        opportunities = self._find_opportunities(
            tax_return, itemized_breakdown, total_standard, agi
        )

        # Generate warnings
        warnings = self._generate_warnings(tax_return, itemized_breakdown)

        # Create analysis
        analysis = DeductionAnalysis(
            filing_status=filing_status,
            adjusted_gross_income=agi,
            standard_deduction_base=standard_base,
            additional_standard_deduction=additional_standard,
            total_standard_deduction=total_standard,
            itemized_breakdown=itemized_breakdown,
            total_itemized_deductions=total_itemized,
            recommended_strategy=recommended_strategy,
            deduction_difference=round(deduction_difference, 2),
            tax_savings_estimate=round(tax_savings, 2),
            marginal_rate=marginal_rate,
            itemized_categories=categories,
            optimization_opportunities=opportunities,
            warnings=warnings,
        )

        # Calculate confidence
        confidence = self._calculate_confidence(deduction_difference, total_standard)

        # Generate explanation
        explanation = self._generate_explanation(analysis)

        # Generate action items
        current_actions = self._generate_current_actions(analysis)
        next_year = self._generate_next_year_planning(analysis, tax_return)

        # Check bunching strategy viability
        bunching = self._evaluate_bunching_strategy(analysis, tax_return)

        return DeductionRecommendation(
            analysis=analysis,
            recommended_strategy=recommended_strategy,
            confidence_score=confidence,
            explanation=explanation,
            current_year_actions=current_actions,
            next_year_planning=next_year,
            bunching_strategy=bunching,
        )

    def _normalize_filing_status(self, status: str) -> str:
        """Normalize filing status string."""
        status_map = {
            "single": "single",
            "married_joint": "married_joint",
            "married_filing_jointly": "married_joint",
            "married_separate": "married_separate",
            "married_filing_separately": "married_separate",
            "head_of_household": "head_of_household",
            "qualifying_widow": "qualifying_widow",
            "qualifying_surviving_spouse": "qualifying_widow",
        }
        return status_map.get(status.lower(), "single")

    def _calculate_additional_standard(
        self, tax_return: "TaxReturn", filing_status: str
    ) -> float:
        """Calculate additional standard deduction for age/blindness."""
        additional = 0.0
        additional_amount = self.ADDITIONAL_STANDARD_2025.get(filing_status, 1600)

        taxpayer = tax_return.taxpayer

        # Check primary taxpayer age (65+)
        if hasattr(taxpayer, 'age') and taxpayer.age >= 65:
            additional += additional_amount
        elif hasattr(taxpayer, 'birth_date'):
            # Calculate age from birth date if available
            from datetime import date
            today = date(2025, 12, 31)  # End of tax year
            age = (today - taxpayer.birth_date).days // 365
            if age >= 65:
                additional += additional_amount

        # Check if blind
        if hasattr(taxpayer, 'is_blind') and taxpayer.is_blind:
            additional += additional_amount

        # Check spouse for married filing jointly
        if filing_status in ("married_joint", "qualifying_widow"):
            if hasattr(taxpayer, 'spouse_age') and taxpayer.spouse_age >= 65:
                additional += additional_amount
            if hasattr(taxpayer, 'spouse_is_blind') and taxpayer.spouse_is_blind:
                additional += additional_amount

        return additional

    def _calculate_itemized(
        self, tax_return: "TaxReturn", agi: float
    ) -> ItemizedDeductionBreakdown:
        """Calculate itemized deductions from tax return data."""
        breakdown = ItemizedDeductionBreakdown()
        deductions = tax_return.deductions
        income = tax_return.income

        # Medical expenses
        if hasattr(deductions, 'medical_expenses'):
            breakdown.medical_expenses_total = deductions.medical_expenses or 0.0

        # SALT components
        if hasattr(deductions, 'state_local_taxes'):
            breakdown.state_local_income_tax = deductions.state_local_taxes or 0.0
        if hasattr(deductions, 'property_taxes'):
            breakdown.property_tax = deductions.property_taxes or 0.0
        if hasattr(deductions, 'real_estate_taxes'):
            breakdown.real_estate_tax = deductions.real_estate_taxes or 0.0

        # Mortgage interest
        if hasattr(deductions, 'mortgage_interest'):
            breakdown.mortgage_interest = deductions.mortgage_interest or 0.0
        if hasattr(deductions, 'mortgage_points'):
            breakdown.mortgage_points = deductions.mortgage_points or 0.0

        # Charitable contributions
        if hasattr(deductions, 'charitable_cash'):
            breakdown.cash_contributions = deductions.charitable_cash or 0.0
        if hasattr(deductions, 'charitable_noncash'):
            breakdown.non_cash_contributions = deductions.charitable_noncash or 0.0

        # Investment interest
        if hasattr(deductions, 'investment_interest'):
            breakdown.investment_interest = deductions.investment_interest or 0.0

        # Casualty losses (federally declared disasters only)
        if hasattr(deductions, 'casualty_losses'):
            breakdown.casualty_losses_federally_declared = deductions.casualty_losses or 0.0

        # Gambling losses
        if hasattr(deductions, 'gambling_losses'):
            breakdown.gambling_losses = deductions.gambling_losses or 0.0

        # Other deductions
        if hasattr(deductions, 'other_itemized'):
            breakdown.other_deductions = deductions.other_itemized or 0.0

        # Get gambling winnings for limit calculation
        gambling_winnings = 0.0
        if hasattr(income, 'gambling_winnings'):
            gambling_winnings = income.gambling_winnings or 0.0

        # Calculate all totals with limits applied
        breakdown.calculate_totals(agi, gambling_winnings)

        return breakdown

    def _get_marginal_rate(self, filing_status: str, agi: float) -> float:
        """Get marginal tax rate for the filing status and income level."""
        # 2025 Federal Tax Brackets
        brackets = {
            "single": [
                (11925, 10), (48475, 12), (103350, 22),
                (197300, 24), (250525, 32), (626350, 35), (float('inf'), 37)
            ],
            "married_joint": [
                (23850, 10), (96950, 12), (206700, 22),
                (394600, 24), (501050, 32), (751600, 35), (float('inf'), 37)
            ],
            "married_separate": [
                (11925, 10), (48475, 12), (103350, 22),
                (197300, 24), (250525, 32), (375800, 35), (float('inf'), 37)
            ],
            "head_of_household": [
                (17000, 10), (64850, 12), (103350, 22),
                (197300, 24), (250500, 32), (626350, 35), (float('inf'), 37)
            ],
            "qualifying_widow": [
                (23850, 10), (96950, 12), (206700, 22),
                (394600, 24), (501050, 32), (751600, 35), (float('inf'), 37)
            ],
        }

        status_brackets = brackets.get(filing_status, brackets["single"])
        for threshold, rate in status_brackets:
            if agi <= threshold:
                return float(rate)
        return 37.0

    def _build_categories(self, breakdown: ItemizedDeductionBreakdown) -> Dict[str, float]:
        """Build itemized deduction categories for display."""
        return {
            "medical_dental": breakdown.medical_deduction_allowed,
            "taxes_paid_salt": breakdown.salt_deduction_allowed,
            "interest_paid": breakdown.total_interest_deduction,
            "charitable_contributions": breakdown.charitable_deduction_allowed,
            "casualty_theft_losses": breakdown.casualty_losses_federally_declared,
            "other_deductions": breakdown.gambling_losses + breakdown.other_deductions,
        }

    def _find_opportunities(
        self,
        tax_return: "TaxReturn",
        breakdown: ItemizedDeductionBreakdown,
        standard: float,
        agi: float
    ) -> List[str]:
        """Identify deduction optimization opportunities."""
        opportunities = []
        gap = standard - breakdown.total_itemized_deductions

        # Check if close to itemizing threshold
        if 0 < gap < 3000:
            opportunities.append(
                f"You're ${gap:,.0f} away from itemizing. Consider bunching "
                "charitable donations or prepaying property taxes."
            )

        # Medical expense opportunity
        medical_floor = agi * 0.075
        if breakdown.medical_expenses_total > 0 and breakdown.medical_expenses_total < medical_floor:
            needed = medical_floor - breakdown.medical_expenses_total
            opportunities.append(
                f"Medical expenses must exceed ${medical_floor:,.0f} (7.5% of AGI). "
                f"You need ${needed:,.0f} more in medical expenses to deduct any."
            )

        # SALT cap warning
        if breakdown.salt_total > breakdown.salt_cap:
            lost = breakdown.salt_total - breakdown.salt_cap
            opportunities.append(
                f"${lost:,.0f} in state/local taxes exceeds the $10,000 SALT cap. "
                "Consider tax planning strategies for future years."
            )

        # Charitable contribution opportunity
        if breakdown.cash_contributions == 0 and breakdown.non_cash_contributions == 0:
            if breakdown.total_itemized_deductions > 0:
                opportunities.append(
                    "No charitable contributions recorded. Donations could help "
                    "exceed the standard deduction threshold."
                )

        # Mortgage interest
        if breakdown.mortgage_interest == 0:
            if breakdown.total_itemized_deductions > standard * 0.5:
                opportunities.append(
                    "No mortgage interest deduction. If you own a home, "
                    "ensure mortgage interest is captured."
                )

        # Investment interest
        if breakdown.investment_interest > 0:
            opportunities.append(
                "Investment interest deduction is limited to net investment income. "
                "Excess can be carried forward."
            )

        return opportunities

    def _generate_warnings(
        self, tax_return: "TaxReturn", breakdown: ItemizedDeductionBreakdown
    ) -> List[str]:
        """Generate warnings about deduction issues."""
        warnings = []

        # Large charitable contribution warning
        agi = tax_return.adjusted_gross_income or 1.0
        total_charitable = (breakdown.cash_contributions +
                          breakdown.non_cash_contributions)
        if total_charitable > agi * 0.30:
            warnings.append(
                "Large charitable contributions may require additional documentation. "
                "Keep detailed records and receipts."
            )

        # Non-cash contribution warning
        if breakdown.non_cash_contributions > 500:
            warnings.append(
                "Non-cash contributions over $500 require Form 8283. "
                "Items over $5,000 may need appraisal."
            )

        # Casualty loss documentation
        if breakdown.casualty_losses_federally_declared > 0:
            warnings.append(
                "Casualty losses are only deductible for federally declared disasters. "
                "Ensure proper documentation and FEMA declaration reference."
            )

        # Gambling losses
        if breakdown.gambling_losses > 0:
            warnings.append(
                "Gambling losses require detailed records: dates, types of wagers, "
                "names of establishments, and amounts won/lost."
            )

        return warnings

    def _calculate_confidence(self, difference: float, standard: float) -> float:
        """Calculate confidence score for the recommendation."""
        # Very clear if difference is large
        abs_diff = abs(difference)

        if abs_diff > standard * 0.20:  # >20% difference
            return 95.0
        elif abs_diff > standard * 0.10:  # >10% difference
            return 85.0
        elif abs_diff > standard * 0.05:  # >5% difference
            return 75.0
        elif abs_diff > 1000:  # >$1,000 difference
            return 65.0
        else:
            return 55.0  # Close call, review recommended

    def _generate_explanation(self, analysis: DeductionAnalysis) -> str:
        """Generate human-readable explanation of the recommendation."""
        if analysis.recommended_strategy == "itemized":
            return (
                f"Itemizing deductions saves you ${abs(analysis.deduction_difference):,.0f} "
                f"more than the standard deduction (${analysis.total_standard_deduction:,.0f}). "
                f"Your total itemized deductions are ${analysis.total_itemized_deductions:,.0f}. "
                f"This results in approximately ${analysis.tax_savings_estimate:,.0f} in tax savings "
                f"at your {analysis.marginal_rate}% marginal rate."
            )
        else:
            return (
                f"The standard deduction (${analysis.total_standard_deduction:,.0f}) "
                f"is ${abs(analysis.deduction_difference):,.0f} more than your itemized "
                f"deductions (${analysis.total_itemized_deductions:,.0f}). "
                f"Using the standard deduction simplifies your return and "
                f"provides a larger tax benefit."
            )

    def _generate_current_actions(self, analysis: DeductionAnalysis) -> List[str]:
        """Generate actionable items for current tax year."""
        actions = []
        breakdown = analysis.itemized_breakdown

        if analysis.recommended_strategy == "standard":
            # Close to itemizing
            gap = analysis.total_standard_deduction - analysis.total_itemized_deductions
            if gap < 5000:
                actions.append(
                    f"Consider making additional charitable contributions before year-end "
                    f"to potentially exceed the standard deduction by ${gap:,.0f}."
                )
                if breakdown.medical_expenses_total > 0:
                    actions.append(
                        "Schedule medical procedures or purchase medical equipment "
                        "before year-end if needed."
                    )
        else:
            # Already itemizing
            actions.append(
                "Ensure all itemized deductions are documented with receipts and records."
            )
            if breakdown.charitable_deduction_allowed > 0:
                actions.append(
                    "Verify all charitable organization receipts include date, "
                    "amount, and organization's tax-exempt status."
                )

        # SALT prepayment consideration
        if breakdown.salt_total < breakdown.salt_cap:
            room = breakdown.salt_cap - breakdown.salt_total
            if room > 1000:
                actions.append(
                    f"You have ${room:,.0f} remaining under the SALT cap. "
                    "Consider prepaying Q1 property taxes before year-end."
                )

        return actions

    def _generate_next_year_planning(
        self, analysis: DeductionAnalysis, tax_return: "TaxReturn"
    ) -> List[str]:
        """Generate planning recommendations for next year."""
        planning = []

        gap = abs(analysis.deduction_difference)

        if gap < 5000 and analysis.recommended_strategy == "standard":
            planning.append(
                "Consider 'bunching' deductions by alternating between standard "
                "and itemized deductions every other year."
            )
            planning.append(
                "Bunch charitable contributions into alternating years to "
                "maximize itemized deductions when you itemize."
            )

        # Retirement contribution recommendation
        if hasattr(tax_return.income, 'retirement_contributions'):
            planning.append(
                "Maximize retirement contributions (401(k), IRA) to reduce AGI, "
                "which affects the 7.5% medical expense floor."
            )

        # HSA recommendation if applicable
        if hasattr(tax_return, 'health_insurance') and tax_return.health_insurance:
            planning.append(
                "Consider a Health Savings Account (HSA) for triple tax benefits: "
                "tax-deductible contributions, tax-free growth, tax-free withdrawals "
                "for medical expenses."
            )

        # Charitable giving strategies
        if analysis.itemized_breakdown.cash_contributions > 1000:
            planning.append(
                "Consider a Donor-Advised Fund (DAF) for bunching multiple years "
                "of charitable contributions with a single-year deduction."
            )
            planning.append(
                "If over 70½, consider Qualified Charitable Distributions (QCD) "
                "directly from IRA to charity (up to $105,000 for 2025)."
            )

        return planning

    def _evaluate_bunching_strategy(
        self, analysis: DeductionAnalysis, tax_return: "TaxReturn"
    ) -> Optional[Dict[str, Any]]:
        """Evaluate if bunching strategy would be beneficial."""
        breakdown = analysis.itemized_breakdown
        standard = analysis.total_standard_deduction

        # Get controllable deductions (those that can be timed)
        controllable = (
            breakdown.charitable_deduction_allowed +
            min(breakdown.property_tax, 5000)  # Portion of SALT that can be timed
        )

        # Fixed deductions (those that can't easily be timed)
        fixed = (
            breakdown.mortgage_interest +
            breakdown.state_local_income_tax
        )

        # If not enough controllable deductions for effective bunching
        if controllable < 3000:
            return None

        # Calculate bunching scenario
        # Year 1: Bunch deductions (double controllable)
        year1_itemized = fixed + (controllable * 2)
        year1_benefit = max(year1_itemized, standard)

        # Year 2: Standard deduction (minimal controllable)
        year2_benefit = standard

        # Two-year bunching total
        bunching_total = year1_benefit + year2_benefit

        # No bunching scenario (split evenly)
        no_bunch_year1 = max(fixed + controllable, standard)
        no_bunch_year2 = max(fixed + controllable, standard)
        no_bunching_total = no_bunch_year1 + no_bunch_year2

        two_year_savings = bunching_total - no_bunching_total

        if two_year_savings <= 0:
            return None

        return {
            "is_beneficial": True,
            "two_year_savings": round(two_year_savings, 2),
            "recommended_approach": "bunching",
            "year1_strategy": "itemized",
            "year1_deductions": round(year1_itemized, 2),
            "year2_strategy": "standard",
            "year2_deductions": round(standard, 2),
            "controllable_deductions": round(controllable, 2),
            "explanation": (
                f"Bunching strategy could save ${two_year_savings:,.0f} over two years. "
                f"In Year 1, double your charitable giving and prepay property taxes "
                f"to itemize at ${year1_itemized:,.0f}. In Year 2, take the standard "
                f"deduction of ${standard:,.0f}."
            ),
        }
