"""Filing Status Optimizer.

Analyzes and recommends the optimal filing status based on the taxpayer's
situation, comparing tax liability across all eligible filing statuses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum
from copy import deepcopy

if TYPE_CHECKING:
    from models.tax_return import TaxReturn
    from calculator.tax_calculator import TaxCalculator


class FilingStatus(Enum):
    """IRS Filing Status options."""
    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_joint"
    MARRIED_FILING_SEPARATELY = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOW = "qualifying_widow"


@dataclass
class FilingStatusAnalysis:
    """Analysis result for a single filing status."""
    filing_status: str
    federal_tax: float
    state_tax: float
    total_tax: float
    effective_rate: float
    marginal_rate: float
    refund_or_owed: float
    is_eligible: bool
    eligibility_reason: str = ""
    benefits: List[str] = field(default_factory=list)
    drawbacks: List[str] = field(default_factory=list)


@dataclass
class FilingStatusRecommendation:
    """Recommendation result comparing all filing statuses."""
    recommended_status: str
    current_status: str
    potential_savings: float
    analyses: Dict[str, FilingStatusAnalysis]
    recommendation_reason: str
    confidence_score: float  # 0-100
    warnings: List[str] = field(default_factory=list)
    additional_considerations: List[str] = field(default_factory=list)


class FilingStatusOptimizer:
    """
    Analyzes and optimizes filing status selection.

    This optimizer evaluates all eligible filing statuses for a taxpayer
    and recommends the one that minimizes total tax liability while
    considering eligibility requirements and special circumstances.
    """

    def __init__(self, calculator: Optional["TaxCalculator"] = None):
        """Initialize the optimizer with an optional calculator."""
        self._calculator = calculator

    def analyze(self, tax_return: "TaxReturn") -> FilingStatusRecommendation:
        """
        Analyze all eligible filing statuses and recommend the optimal one.

        Args:
            tax_return: The tax return to analyze

        Returns:
            FilingStatusRecommendation with comparison and recommendation
        """
        from calculator.tax_calculator import TaxCalculator

        calculator = self._calculator or TaxCalculator()
        current_status = tax_return.taxpayer.filing_status.value

        # Determine eligible filing statuses
        eligible_statuses = self._get_eligible_statuses(tax_return)

        # Analyze each eligible status
        analyses: Dict[str, FilingStatusAnalysis] = {}
        for status in eligible_statuses:
            analysis = self._analyze_status(tax_return, status, calculator)
            analyses[status] = analysis

        # Find optimal status (lowest total tax among eligible)
        eligible_analyses = {k: v for k, v in analyses.items() if v.is_eligible}

        if not eligible_analyses:
            # Fallback to current status if no eligible found
            recommended_status = current_status
            potential_savings = 0.0
            recommendation_reason = "No alternative filing statuses available."
            confidence_score = 50.0
        else:
            # Find status with lowest total tax
            optimal = min(eligible_analyses.items(), key=lambda x: x[1].total_tax)
            recommended_status = optimal[0]

            # Calculate savings compared to current status
            current_analysis = analyses.get(current_status)
            if current_analysis:
                potential_savings = current_analysis.total_tax - optimal[1].total_tax
            else:
                potential_savings = 0.0

            # Generate recommendation reason
            recommendation_reason = self._generate_recommendation_reason(
                recommended_status, current_status, potential_savings, analyses
            )

            # Calculate confidence score
            confidence_score = self._calculate_confidence(
                recommended_status, eligible_analyses
            )

        # Generate warnings and considerations
        warnings = self._generate_warnings(tax_return, recommended_status, analyses)
        considerations = self._generate_considerations(tax_return, recommended_status)

        return FilingStatusRecommendation(
            recommended_status=recommended_status,
            current_status=current_status,
            potential_savings=round(potential_savings, 2),
            analyses=analyses,
            recommendation_reason=recommendation_reason,
            confidence_score=confidence_score,
            warnings=warnings,
            additional_considerations=considerations,
        )

    def _get_eligible_statuses(self, tax_return: "TaxReturn") -> List[str]:
        """Determine which filing statuses the taxpayer is eligible for."""
        eligible = []
        taxpayer = tax_return.taxpayer
        has_dependents = len(taxpayer.dependents) > 0

        # Check marital status
        is_married = hasattr(taxpayer, 'is_married') and taxpayer.is_married

        if is_married:
            eligible.append(FilingStatus.MARRIED_FILING_JOINTLY.value)
            eligible.append(FilingStatus.MARRIED_FILING_SEPARATELY.value)
        else:
            eligible.append(FilingStatus.SINGLE.value)

            # Head of Household requires unmarried + dependent
            if has_dependents:
                eligible.append(FilingStatus.HEAD_OF_HOUSEHOLD.value)

        # Qualifying Widow(er) - spouse died within last 2 years + dependent
        if hasattr(taxpayer, 'spouse_died_year') and taxpayer.spouse_died_year:
            if has_dependents:
                eligible.append(FilingStatus.QUALIFYING_WIDOW.value)

        return eligible

    def _analyze_status(
        self,
        tax_return: "TaxReturn",
        status: str,
        calculator: "TaxCalculator"
    ) -> FilingStatusAnalysis:
        """Analyze tax liability for a specific filing status."""
        # Create a copy of the tax return with modified filing status
        test_return = self._create_test_return(tax_return, status)

        # Check eligibility
        is_eligible, eligibility_reason = self._check_eligibility(tax_return, status)

        if not is_eligible:
            return FilingStatusAnalysis(
                filing_status=status,
                federal_tax=0.0,
                state_tax=0.0,
                total_tax=0.0,
                effective_rate=0.0,
                marginal_rate=0.0,
                refund_or_owed=0.0,
                is_eligible=False,
                eligibility_reason=eligibility_reason,
            )

        # Calculate taxes
        try:
            calculated_return = calculator.calculate_complete_return(test_return)

            federal_tax = calculated_return.tax_liability or 0.0
            state_tax = calculated_return.state_tax_liability or 0.0
            total_tax = federal_tax + state_tax

            agi = calculated_return.adjusted_gross_income or 1.0
            effective_rate = (total_tax / agi * 100) if agi > 0 else 0.0

            marginal_rate = self._get_marginal_rate(status, agi)

            refund_or_owed = (calculated_return.combined_refund_or_owed or
                             calculated_return.refund_or_owed or 0.0)

            benefits = self._get_status_benefits(status, calculated_return)
            drawbacks = self._get_status_drawbacks(status, calculated_return)

            return FilingStatusAnalysis(
                filing_status=status,
                federal_tax=round(federal_tax, 2),
                state_tax=round(state_tax, 2),
                total_tax=round(total_tax, 2),
                effective_rate=round(effective_rate, 2),
                marginal_rate=marginal_rate,
                refund_or_owed=round(refund_or_owed, 2),
                is_eligible=True,
                benefits=benefits,
                drawbacks=drawbacks,
            )
        except Exception as e:
            return FilingStatusAnalysis(
                filing_status=status,
                federal_tax=0.0,
                state_tax=0.0,
                total_tax=0.0,
                effective_rate=0.0,
                marginal_rate=0.0,
                refund_or_owed=0.0,
                is_eligible=False,
                eligibility_reason=f"Calculation error: {str(e)}",
            )

    def _create_test_return(self, tax_return: "TaxReturn", status: str) -> "TaxReturn":
        """Create a copy of tax return with modified filing status."""
        from models.taxpayer import FilingStatus as TaxpayerFilingStatus

        test_return = deepcopy(tax_return)

        # Map status string to FilingStatus enum
        status_map = {
            "single": TaxpayerFilingStatus.SINGLE,
            "married_joint": TaxpayerFilingStatus.MARRIED_JOINT,
            "married_separate": TaxpayerFilingStatus.MARRIED_SEPARATE,
            "head_of_household": TaxpayerFilingStatus.HEAD_OF_HOUSEHOLD,
            "qualifying_widow": TaxpayerFilingStatus.QUALIFYING_WIDOW,
        }

        if status in status_map:
            test_return.taxpayer.filing_status = status_map[status]

        return test_return

    def _check_eligibility(self, tax_return: "TaxReturn", status: str) -> tuple:
        """Check if taxpayer is eligible for a specific filing status."""
        taxpayer = tax_return.taxpayer
        has_dependents = len(taxpayer.dependents) > 0
        is_married = hasattr(taxpayer, 'is_married') and taxpayer.is_married

        if status == "single":
            if is_married:
                return False, "Cannot file as Single if married"
            return True, ""

        elif status == "married_joint":
            if not is_married:
                return False, "Must be married to file jointly"
            return True, ""

        elif status == "married_separate":
            if not is_married:
                return False, "Must be married to file separately"
            return True, ""

        elif status == "head_of_household":
            if is_married:
                return False, "Cannot file as Head of Household if married"
            if not has_dependents:
                return False, "Head of Household requires a qualifying dependent"
            return True, ""

        elif status == "qualifying_widow":
            if not hasattr(taxpayer, 'spouse_died_year') or not taxpayer.spouse_died_year:
                return False, "Qualifying Widow(er) requires spouse to have died within 2 years"
            if not has_dependents:
                return False, "Qualifying Widow(er) requires a dependent child"
            return True, ""

        return False, f"Unknown filing status: {status}"

    def _get_marginal_rate(self, status: str, agi: float) -> float:
        """Get the marginal tax rate for the filing status and income."""
        # 2025 Federal Tax Brackets
        brackets = {
            "single": [(11925, 0.10), (48475, 0.12), (103350, 0.22),
                      (197300, 0.24), (250525, 0.32), (626350, 0.35), (float('inf'), 0.37)],
            "married_joint": [(23850, 0.10), (96950, 0.12), (206700, 0.22),
                             (394600, 0.24), (501050, 0.32), (751600, 0.35), (float('inf'), 0.37)],
            "married_separate": [(11925, 0.10), (48475, 0.12), (103350, 0.22),
                                (197300, 0.24), (250525, 0.32), (375800, 0.35), (float('inf'), 0.37)],
            "head_of_household": [(17000, 0.10), (64850, 0.12), (103350, 0.22),
                                 (197300, 0.24), (250500, 0.32), (626350, 0.35), (float('inf'), 0.37)],
            "qualifying_widow": [(23850, 0.10), (96950, 0.12), (206700, 0.22),
                                (394600, 0.24), (501050, 0.32), (751600, 0.35), (float('inf'), 0.37)],
        }

        status_brackets = brackets.get(status, brackets["single"])
        for threshold, rate in status_brackets:
            if agi <= threshold:
                return rate * 100
        return 37.0

    def _get_status_benefits(self, status: str, tax_return: "TaxReturn") -> List[str]:
        """Get benefits of a specific filing status."""
        benefits = []

        if status == "married_joint":
            benefits.append("Wider tax brackets reduce marginal rate")
            benefits.append("Higher standard deduction ($31,500)")
            benefits.append("Combined income may qualify for more credits")
            benefits.append("Can contribute to spouse's IRA")

        elif status == "head_of_household":
            benefits.append("Wider brackets than Single")
            benefits.append("Higher standard deduction ($23,625)")
            benefits.append("May qualify for additional credits")

        elif status == "qualifying_widow":
            benefits.append("Uses married filing jointly brackets")
            benefits.append("Higher standard deduction ($31,500)")

        elif status == "single":
            benefits.append("Simple filing, no need to coordinate with spouse")

        elif status == "married_separate":
            benefits.append("Separates liability from spouse")
            benefits.append("May help with income-based student loan payments")
            benefits.append("Protects from spouse's tax issues")

        return benefits

    def _get_status_drawbacks(self, status: str, tax_return: "TaxReturn") -> List[str]:
        """Get drawbacks of a specific filing status."""
        drawbacks = []

        if status == "married_separate":
            drawbacks.append("Narrower tax brackets")
            drawbacks.append("Lower or no EITC eligibility")
            drawbacks.append("Cannot claim student loan interest deduction")
            drawbacks.append("Cannot claim education credits")
            drawbacks.append("Lower IRA contribution limits")
            drawbacks.append("Higher capital gains tax threshold")

        elif status == "single":
            drawbacks.append("Narrower brackets than married joint")
            drawbacks.append("Lower standard deduction")

        return drawbacks

    def _generate_recommendation_reason(
        self,
        recommended: str,
        current: str,
        savings: float,
        analyses: Dict[str, FilingStatusAnalysis]
    ) -> str:
        """Generate explanation for the recommendation."""
        if recommended == current:
            return f"Your current filing status ({current}) is optimal for your situation."

        if savings > 0:
            return (f"Filing as {recommended} instead of {current} could save you "
                   f"${savings:,.2f} in total taxes.")
        else:
            return f"Filing as {recommended} is recommended based on your eligibility and circumstances."

    def _calculate_confidence(
        self,
        recommended: str,
        analyses: Dict[str, FilingStatusAnalysis]
    ) -> float:
        """Calculate confidence score for the recommendation."""
        if len(analyses) <= 1:
            return 100.0

        # Get recommended analysis
        rec_analysis = analyses.get(recommended)
        if not rec_analysis:
            return 50.0

        # Calculate how much better the recommended status is
        other_taxes = [a.total_tax for k, a in analyses.items() if k != recommended and a.is_eligible]
        if not other_taxes:
            return 100.0

        min_other = min(other_taxes)
        savings_pct = ((min_other - rec_analysis.total_tax) / min_other * 100) if min_other > 0 else 0

        # Higher savings = higher confidence
        confidence = min(100, 70 + savings_pct)
        return round(confidence, 1)

    def _generate_warnings(
        self,
        tax_return: "TaxReturn",
        recommended: str,
        analyses: Dict[str, FilingStatusAnalysis]
    ) -> List[str]:
        """Generate warnings about the recommendation."""
        warnings = []

        if recommended == "married_separate":
            warnings.append("WARNING: Filing separately may disqualify you from many tax credits")
            warnings.append("WARNING: Both spouses must itemize or both must take standard deduction")

        if recommended != tax_return.taxpayer.filing_status.value:
            warnings.append("Changing filing status may affect your tax planning strategy")

        return warnings

    def _generate_considerations(
        self,
        tax_return: "TaxReturn",
        recommended: str
    ) -> List[str]:
        """Generate additional considerations for the taxpayer."""
        considerations = []

        considerations.append("Consider consulting a tax professional for complex situations")

        if tax_return.income.self_employment_income > 0:
            considerations.append("Self-employment income affects EITC and other credits")

        if len(tax_return.taxpayer.dependents) > 0:
            considerations.append("Verify all dependents meet qualifying child/relative tests")

        if (tax_return.income.long_term_capital_gains + tax_return.income.short_term_capital_gains) > 0:
            considerations.append("Capital gains may affect optimal filing status calculation")

        return considerations
