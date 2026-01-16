"""Onboarding Benefit Estimator.

Provides real-time tax benefit estimates during the onboarding process
to keep users engaged and informed of their progress.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from onboarding.taxpayer_profile import TaxpayerProfile


class EstimateType(Enum):
    """Types of estimates."""
    REFUND = "refund"
    OWED = "owed"
    BREAK_EVEN = "break_even"


@dataclass
class TaxEstimate:
    """Tax estimate result."""
    estimate_type: EstimateType
    estimated_amount: float
    confidence: str  # low, medium, high
    estimated_federal_tax: float
    estimated_state_tax: float
    estimated_total_tax: float
    estimated_withholding: float
    effective_rate: float
    marginal_rate: float

    # Breakdown
    estimated_agi: float
    estimated_taxable_income: float
    deduction_type: str  # standard, itemized
    deduction_amount: float
    estimated_credits: float

    # Components that contributed
    income_sources: Dict[str, float] = field(default_factory=dict)
    deductions_breakdown: Dict[str, float] = field(default_factory=dict)
    credits_breakdown: Dict[str, float] = field(default_factory=dict)

    # What could change
    potential_improvements: List[str] = field(default_factory=list)
    missing_info_impact: str = ""


@dataclass
class BenefitHighlight:
    """A highlighted benefit or opportunity."""
    title: str
    description: str
    estimated_value: float
    category: str
    is_potential: bool  # True if requires action/verification
    action_required: Optional[str] = None


class OnboardingBenefitEstimator:
    """
    Provides real-time benefit estimates during onboarding.

    This estimator runs continuously as users enter data, showing them
    their estimated refund/owed amount and highlighting opportunities
    for additional savings.
    """

    # 2025 Tax Constants (IRS Rev. Proc. 2024-40)
    STANDARD_DEDUCTIONS = {
        "single": 15750,
        "married_joint": 31500,
        "married_separate": 15750,
        "head_of_household": 23625,
        "qualifying_widow": 31500,
    }

    TAX_BRACKETS = {
        "single": [
            (0, 11925, 0.10),
            (11925, 48475, 0.12),
            (48475, 103350, 0.22),
            (103350, 197300, 0.24),
            (197300, 250525, 0.32),
            (250525, 626350, 0.35),
            (626350, float('inf'), 0.37),
        ],
        "married_joint": [
            (0, 23850, 0.10),
            (23850, 96950, 0.12),
            (96950, 206700, 0.22),
            (206700, 394600, 0.24),
            (394600, 501050, 0.32),
            (501050, 751600, 0.35),
            (751600, float('inf'), 0.37),
        ],
        "married_separate": [
            (0, 11925, 0.10),
            (11925, 48475, 0.12),
            (48475, 103350, 0.22),
            (103350, 197300, 0.24),
            (197300, 250525, 0.32),
            (250525, 375800, 0.35),
            (375800, float('inf'), 0.37),
        ],
        "head_of_household": [
            (0, 17000, 0.10),
            (17000, 64850, 0.12),
            (64850, 103350, 0.22),
            (103350, 197300, 0.24),
            (197300, 250500, 0.32),
            (250500, 626350, 0.35),
            (626350, float('inf'), 0.37),
        ],
    }

    # Credit amounts
    CHILD_TAX_CREDIT = 2000
    OTHER_DEPENDENT_CREDIT = 500
    # EITC max credit by qualifying children (2025, IRS Rev. Proc. 2024-40)
    EITC_MAX = {0: 649, 1: 4328, 2: 7152, 3: 8046}

    def __init__(self):
        """Initialize the estimator."""
        self._last_estimate: Optional[TaxEstimate] = None

    def estimate_from_answers(self, answers: Dict[str, Any]) -> TaxEstimate:
        """
        Generate estimate from questionnaire answers.

        Args:
            answers: Current questionnaire answers

        Returns:
            TaxEstimate with current projection
        """
        # Determine filing status
        filing_status = self._determine_filing_status(answers)

        # Calculate income
        income_sources, total_income = self._calculate_income(answers)

        # Calculate adjustments to income
        adjustments = self._calculate_adjustments(answers)
        agi = max(0, total_income - adjustments)

        # Calculate deductions
        deduction_type, deduction_amount, deductions_breakdown = self._calculate_deductions(
            answers, filing_status, agi
        )

        # Calculate taxable income
        taxable_income = max(0, agi - deduction_amount)

        # Calculate federal tax
        federal_tax = self._calculate_federal_tax(taxable_income, filing_status)

        # Calculate credits
        credits_breakdown, total_credits = self._calculate_credits(
            answers, filing_status, agi, federal_tax
        )

        # Net federal tax
        federal_tax_after_credits = max(0, federal_tax - total_credits)

        # Add refundable credits back
        refundable_credits = self._calculate_refundable_credits(
            answers, filing_status, agi, total_income
        )

        # Estimate state tax (simplified - 5% average)
        state = answers.get("state_residence", "CA")
        state_rate = self._get_state_rate(state)
        state_tax = agi * state_rate

        # Total tax
        total_tax = federal_tax_after_credits + state_tax

        # Get withholding
        withholding = self._calculate_withholding(answers)

        # Determine refund or owed
        result = withholding + refundable_credits - total_tax

        if result > 0:
            estimate_type = EstimateType.REFUND
        elif result < 0:
            estimate_type = EstimateType.OWED
        else:
            estimate_type = EstimateType.BREAK_EVEN

        # Calculate rates
        effective_rate = (total_tax / agi * 100) if agi > 0 else 0
        marginal_rate = self._get_marginal_rate(taxable_income, filing_status)

        # Determine confidence based on data completeness
        confidence = self._assess_confidence(answers)

        # Generate potential improvements
        improvements = self._identify_improvements(answers, filing_status, agi)

        # Missing info impact
        missing_impact = self._assess_missing_info_impact(answers)

        estimate = TaxEstimate(
            estimate_type=estimate_type,
            estimated_amount=abs(round(result, 2)),
            confidence=confidence,
            estimated_federal_tax=round(federal_tax_after_credits, 2),
            estimated_state_tax=round(state_tax, 2),
            estimated_total_tax=round(total_tax, 2),
            estimated_withholding=round(withholding, 2),
            effective_rate=round(effective_rate, 2),
            marginal_rate=marginal_rate,
            estimated_agi=round(agi, 2),
            estimated_taxable_income=round(taxable_income, 2),
            deduction_type=deduction_type,
            deduction_amount=round(deduction_amount, 2),
            estimated_credits=round(total_credits + refundable_credits, 2),
            income_sources=income_sources,
            deductions_breakdown=deductions_breakdown,
            credits_breakdown=credits_breakdown,
            potential_improvements=improvements,
            missing_info_impact=missing_impact,
        )

        self._last_estimate = estimate
        return estimate

    def get_benefit_highlights(
        self, answers: Dict[str, Any], profile: Optional["TaxpayerProfile"] = None
    ) -> List[BenefitHighlight]:
        """
        Get highlighted benefits and opportunities based on current data.

        Args:
            answers: Current questionnaire answers
            profile: Optional taxpayer profile

        Returns:
            List of benefit highlights to display
        """
        highlights = []

        filing_status = self._determine_filing_status(answers)
        income_sources, total_income = self._calculate_income(answers)
        agi = total_income - self._calculate_adjustments(answers)

        # Child Tax Credit
        num_children = int(answers.get("num_children", 0) or 0)
        if num_children > 0:
            ctc_amount = num_children * self.CHILD_TAX_CREDIT
            highlights.append(BenefitHighlight(
                title="Child Tax Credit",
                description=f"${self.CHILD_TAX_CREDIT:,} credit per child under 17",
                estimated_value=ctc_amount,
                category="credits",
                is_potential=False,
            ))

        # EITC
        if self._may_qualify_eitc(answers, filing_status, agi):
            max_eitc = self.EITC_MAX.get(min(3, num_children), 649)
            highlights.append(BenefitHighlight(
                title="Earned Income Credit",
                description="Refundable credit for working families",
                estimated_value=max_eitc,
                category="credits",
                is_potential=True,
                action_required="Complete income section to verify eligibility",
            ))

        # Retirement savings
        retirement_contrib = float(answers.get("w2_401k_amount_1", 0) or 0)
        if retirement_contrib > 0:
            marginal_rate = self._get_marginal_rate(agi, filing_status)
            tax_savings = retirement_contrib * (marginal_rate / 100)
            highlights.append(BenefitHighlight(
                title="Retirement Contribution Savings",
                description=f"Your 401(k) contributions reduced taxable income",
                estimated_value=round(tax_savings, 2),
                category="deductions",
                is_potential=False,
            ))

        # Saver's Credit
        if retirement_contrib > 0 and agi < 76500:
            saver_credit = min(retirement_contrib * 0.10, 200)
            highlights.append(BenefitHighlight(
                title="Saver's Credit",
                description="Credit for retirement savings contributions",
                estimated_value=saver_credit,
                category="credits",
                is_potential=True,
                action_required="Low-income filers may qualify for additional credit",
            ))

        # Mortgage interest
        mortgage_interest = float(answers.get("mortgage_interest", 0) or 0)
        if mortgage_interest > 0:
            marginal_rate = self._get_marginal_rate(agi, filing_status)
            tax_savings = mortgage_interest * (marginal_rate / 100)
            highlights.append(BenefitHighlight(
                title="Mortgage Interest Deduction",
                description="Deduction for home mortgage interest",
                estimated_value=round(tax_savings, 2),
                category="deductions",
                is_potential=False,
            ))

        # Charitable contributions
        charity = float(answers.get("charity_cash", 0) or 0) + \
                  float(answers.get("charity_noncash", 0) or 0)
        if charity > 0:
            marginal_rate = self._get_marginal_rate(agi, filing_status)
            tax_savings = charity * (marginal_rate / 100)
            highlights.append(BenefitHighlight(
                title="Charitable Deduction",
                description="Deduction for donations to charity",
                estimated_value=round(tax_savings, 2),
                category="deductions",
                is_potential=False,
            ))

        # Education credits
        tuition = float(answers.get("tuition_paid", 0) or 0)
        if tuition > 0:
            aotc = min(2500, tuition)
            highlights.append(BenefitHighlight(
                title="Education Credit",
                description="American Opportunity or Lifetime Learning Credit",
                estimated_value=aotc,
                category="credits",
                is_potential=True,
                action_required="Complete education section to claim",
            ))

        # Self-employment deductions
        se_income = float(answers.get("business_gross_income", 0) or 0)
        se_expenses = float(answers.get("business_expenses", 0) or 0)
        if se_expenses > 0:
            se_tax_savings = se_expenses * 0.153 / 2  # Half of SE tax
            highlights.append(BenefitHighlight(
                title="Business Expense Deductions",
                description="Deductions reduce both income and self-employment tax",
                estimated_value=round(se_tax_savings, 2),
                category="deductions",
                is_potential=False,
            ))

        # QBI deduction
        if se_income > 0:
            net_se = max(0, se_income - se_expenses)
            qbi_deduction = net_se * 0.20
            marginal_rate = self._get_marginal_rate(agi, filing_status)
            qbi_savings = qbi_deduction * (marginal_rate / 100)
            highlights.append(BenefitHighlight(
                title="QBI Deduction",
                description="20% deduction for qualified business income",
                estimated_value=round(qbi_savings, 2),
                category="deductions",
                is_potential=True,
                action_required="Self-employed may qualify for additional deduction",
            ))

        # Home office
        if answers.get("home_office"):
            sqft = int(answers.get("home_office_sqft", 0) or 0)
            home_office_deduction = min(sqft * 5, 1500)
            marginal_rate = self._get_marginal_rate(agi, filing_status)
            savings = home_office_deduction * (marginal_rate / 100)
            highlights.append(BenefitHighlight(
                title="Home Office Deduction",
                description="Deduction for dedicated home workspace",
                estimated_value=round(savings, 2),
                category="deductions",
                is_potential=False,
            ))

        # EV Credit
        if answers.get("ev_purchased"):
            ev_type = answers.get("ev_type", "new")
            ev_credit = 7500 if ev_type == "new" else 4000
            highlights.append(BenefitHighlight(
                title="Clean Vehicle Credit",
                description="Credit for electric vehicle purchase",
                estimated_value=ev_credit,
                category="credits",
                is_potential=True,
                action_required="Verify vehicle qualifies for credit",
            ))

        # Solar credit
        solar_cost = float(answers.get("solar_cost", 0) or 0)
        if solar_cost > 0:
            solar_credit = solar_cost * 0.30
            highlights.append(BenefitHighlight(
                title="Residential Clean Energy Credit",
                description="30% credit for solar installation",
                estimated_value=round(solar_credit, 2),
                category="credits",
                is_potential=False,
            ))

        # Sort by value
        highlights.sort(key=lambda x: x.estimated_value, reverse=True)

        return highlights

    def get_refund_trend(self, estimates: List[TaxEstimate]) -> Dict[str, Any]:
        """
        Track refund estimate trend over the course of onboarding.

        Args:
            estimates: List of estimates taken at different points

        Returns:
            Trend analysis
        """
        if not estimates:
            return {"trend": "unknown", "change": 0}

        first = estimates[0].estimated_amount
        if estimates[0].estimate_type == EstimateType.OWED:
            first = -first

        last = estimates[-1].estimated_amount
        if estimates[-1].estimate_type == EstimateType.OWED:
            last = -last

        change = last - first

        if change > 100:
            trend = "increasing"
        elif change < -100:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "change": round(change, 2),
            "initial": round(first, 2),
            "current": round(last, 2),
            "data_points": len(estimates),
        }

    def _determine_filing_status(self, answers: Dict[str, Any]) -> str:
        """Determine filing status from answers."""
        status = answers.get("filing_status")
        if status:
            return status

        marital = answers.get("marital_status")
        if marital == "married":
            return "married_joint"
        elif marital == "single":
            has_dependents = answers.get("has_dependents", False)
            if has_dependents and answers.get("qualify_hoh", False):
                return "head_of_household"
            return "single"

        return "single"  # Default

    def _calculate_income(self, answers: Dict[str, Any]) -> tuple:
        """Calculate total income from all sources."""
        sources = {}
        total = 0.0

        # W-2 wages
        for i in range(1, 6):
            wages = float(answers.get(f"w2_wages_{i}", 0) or 0)
            if wages > 0:
                sources[f"W-2 #{i}"] = wages
                total += wages

        # 1099-NEC
        for i in range(1, 6):
            nec = float(answers.get(f"1099_amount_{i}", 0) or 0)
            if nec > 0:
                sources[f"1099-NEC #{i}"] = nec
                total += nec

        # Business income (net)
        business_gross = float(answers.get("business_gross_income", 0) or 0)
        business_expenses = float(answers.get("business_expenses", 0) or 0)
        if business_gross > 0:
            net_business = max(0, business_gross - business_expenses)
            sources["Self-Employment"] = net_business
            total += net_business

        # Investment income
        dividends = float(answers.get("dividend_income", 0) or 0)
        interest = float(answers.get("interest_income", 0) or 0)
        cap_gains = float(answers.get("capital_gain_amount", 0) or 0)
        investment = dividends + interest + cap_gains
        if investment != 0:
            sources["Investments"] = investment
            total += investment

        # Retirement income
        ss = float(answers.get("ss_total", 0) or 0) * 0.85  # Max 85% taxable
        pension = float(answers.get("pension_amount", 0) or 0)
        ira = float(answers.get("ira_distribution_amount", 0) or 0)
        retirement = ss + pension + ira
        if retirement > 0:
            sources["Retirement"] = retirement
            total += retirement

        # Other income
        gambling = float(answers.get("gambling_winnings", 0) or 0)
        other = float(answers.get("prizes_awards", 0) or 0)
        if gambling + other > 0:
            sources["Other"] = gambling + other
            total += gambling + other

        return sources, total

    def _calculate_adjustments(self, answers: Dict[str, Any]) -> float:
        """Calculate adjustments to income (above-the-line deductions)."""
        adjustments = 0.0

        # Student loan interest
        student_loan = float(answers.get("student_loan_interest_paid", 0) or 0)
        adjustments += min(student_loan, 2500)  # $2,500 max

        # HSA contributions
        hsa = float(answers.get("hsa_contribution", 0) or 0)
        adjustments += hsa

        # Self-employment tax deduction (half of SE tax)
        business_gross = float(answers.get("business_gross_income", 0) or 0)
        business_expenses = float(answers.get("business_expenses", 0) or 0)
        net_se = max(0, business_gross - business_expenses)
        se_tax = net_se * 0.9235 * 0.153  # SE tax
        adjustments += se_tax / 2

        # Traditional IRA contributions
        ira = float(answers.get("ira_contribution", 0) or 0)
        adjustments += min(ira, 7000)  # 2025 limit

        # Educator expenses
        educator = float(answers.get("educator_expenses", 0) or 0)
        adjustments += min(educator, 300)

        return adjustments

    def _calculate_deductions(
        self, answers: Dict[str, Any], filing_status: str, agi: float
    ) -> tuple:
        """Calculate standard vs itemized deductions."""
        standard = self.STANDARD_DEDUCTIONS.get(filing_status, 15750)

        # Calculate itemized
        itemized_breakdown = {}

        # Mortgage interest
        mortgage = float(answers.get("mortgage_interest", 0) or 0)
        if mortgage > 0:
            itemized_breakdown["Mortgage Interest"] = mortgage

        # SALT (capped at $10,000)
        property_tax = float(answers.get("property_taxes", 0) or 0)
        state_tax = float(answers.get("state_local_income_tax", 0) or 0)
        salt = min(property_tax + state_tax, 10000)
        if salt > 0:
            itemized_breakdown["State & Local Taxes"] = salt

        # Charitable
        charity = float(answers.get("charity_cash", 0) or 0) + \
                  float(answers.get("charity_noncash", 0) or 0)
        if charity > 0:
            itemized_breakdown["Charitable"] = charity

        # Medical (only amount over 7.5% of AGI)
        medical = float(answers.get("medical_expenses", 0) or 0)
        medical_floor = agi * 0.075
        deductible_medical = max(0, medical - medical_floor)
        if deductible_medical > 0:
            itemized_breakdown["Medical"] = deductible_medical

        total_itemized = sum(itemized_breakdown.values())

        # Choose better option
        if total_itemized > standard:
            return "itemized", total_itemized, itemized_breakdown
        else:
            return "standard", standard, {"Standard Deduction": standard}

    def _calculate_federal_tax(self, taxable_income: float, filing_status: str) -> float:
        """Calculate federal tax using brackets."""
        brackets = self.TAX_BRACKETS.get(filing_status, self.TAX_BRACKETS["single"])
        tax = 0.0

        for lower, upper, rate in brackets:
            if taxable_income > lower:
                taxable_in_bracket = min(taxable_income, upper) - lower
                tax += taxable_in_bracket * rate
            else:
                break

        return tax

    def _calculate_credits(
        self, answers: Dict[str, Any], filing_status: str, agi: float, tax: float
    ) -> tuple:
        """Calculate nonrefundable credits."""
        credits = {}

        # Child Tax Credit (nonrefundable portion)
        num_children = int(answers.get("num_children", 0) or 0)
        if num_children > 0:
            ctc = num_children * self.CHILD_TAX_CREDIT
            # Phase-out
            threshold = 400000 if filing_status == "married_joint" else 200000
            if agi > threshold:
                reduction = ((agi - threshold) // 1000) * 50
                ctc = max(0, ctc - reduction)
            ctc = min(ctc, tax)  # Nonrefundable limited to tax
            if ctc > 0:
                credits["Child Tax Credit"] = ctc

        # Other Dependent Credit
        other_deps = int(answers.get("num_other_dependents", 0) or 0)
        if other_deps > 0:
            odc = other_deps * self.OTHER_DEPENDENT_CREDIT
            odc = min(odc, tax - sum(credits.values()))
            if odc > 0:
                credits["Other Dependent Credit"] = odc

        # Child Care Credit
        care_expenses = float(answers.get("child_care_amount", 0) or 0)
        if care_expenses > 0:
            # Simplified: 20% of up to $3,000 per child
            children = min(int(answers.get("num_children", 1) or 1), 2)
            max_expense = 3000 * children
            qualified = min(care_expenses, max_expense)
            care_credit = qualified * 0.20
            care_credit = min(care_credit, tax - sum(credits.values()))
            if care_credit > 0:
                credits["Child Care Credit"] = care_credit

        # Education Credits
        tuition = float(answers.get("tuition_paid", 0) or 0)
        scholarships = float(answers.get("scholarships_received", 0) or 0)
        net_tuition = max(0, tuition - scholarships)
        if net_tuition > 0 and agi < 180000:
            if answers.get("first_four_years"):
                # AOTC: 100% first $2,000 + 25% next $2,000
                aotc = min(2000, net_tuition)
                if net_tuition > 2000:
                    aotc += min(net_tuition - 2000, 2000) * 0.25
                aotc_nonrefundable = aotc * 0.60
                aotc_nonrefundable = min(aotc_nonrefundable, tax - sum(credits.values()))
                if aotc_nonrefundable > 0:
                    credits["American Opportunity Credit"] = aotc_nonrefundable
            else:
                # LLC: 20% of first $10,000
                llc = min(net_tuition * 0.20, 2000)
                llc = min(llc, tax - sum(credits.values()))
                if llc > 0:
                    credits["Lifetime Learning Credit"] = llc

        # EV Credit
        if answers.get("ev_purchased"):
            ev_type = answers.get("ev_type", "new")
            ev_credit = 7500 if ev_type == "new" else 4000
            ev_credit = min(ev_credit, tax - sum(credits.values()))
            if ev_credit > 0:
                credits["Clean Vehicle Credit"] = ev_credit

        # Energy Credit
        solar = float(answers.get("solar_cost", 0) or 0)
        energy = float(answers.get("energy_improvement_cost", 0) or 0)
        if solar + energy > 0:
            energy_credit = (solar + energy) * 0.30
            energy_credit = min(energy_credit, tax - sum(credits.values()))
            if energy_credit > 0:
                credits["Clean Energy Credit"] = energy_credit

        total = sum(credits.values())
        return credits, total

    def _calculate_refundable_credits(
        self, answers: Dict[str, Any], filing_status: str, agi: float, earned_income: float
    ) -> float:
        """Calculate refundable credits."""
        refundable = 0.0

        # Additional Child Tax Credit (refundable portion)
        num_children = int(answers.get("num_children", 0) or 0)
        if num_children > 0 and earned_income > 2500:
            # Simplified: up to $1,700 per child
            actc = num_children * 1700
            refundable += actc

        # EITC
        if self._may_qualify_eitc(answers, filing_status, agi):
            children = min(3, num_children)
            max_eitc = self.EITC_MAX.get(children, 649)
            # Simplified estimate
            eitc_estimate = max_eitc * 0.6  # Conservative estimate
            refundable += eitc_estimate

        # Refundable portion of AOTC
        tuition = float(answers.get("tuition_paid", 0) or 0)
        if tuition > 0 and answers.get("first_four_years") and agi < 180000:
            aotc_total = min(2500, tuition)
            aotc_refundable = aotc_total * 0.40  # 40% is refundable
            refundable += aotc_refundable

        return refundable

    def _calculate_withholding(self, answers: Dict[str, Any]) -> float:
        """Calculate total withholding."""
        total = 0.0

        # Federal W-2 withholding
        for i in range(1, 6):
            withheld = float(answers.get(f"w2_federal_withheld_{i}", 0) or 0)
            total += withheld

        # 1099 withholding
        for i in range(1, 6):
            withheld = float(answers.get(f"1099_federal_withheld_{i}", 0) or 0)
            total += withheld

        # Estimated payments
        estimated = float(answers.get("estimated_payments", 0) or 0)
        total += estimated

        return total

    def _get_state_rate(self, state: str) -> float:
        """Get estimated effective state tax rate."""
        no_tax_states = ["AK", "FL", "NV", "SD", "TX", "WA", "WY", "TN", "NH"]
        if state in no_tax_states:
            return 0.0

        high_tax_states = {"CA": 0.065, "NY": 0.055, "NJ": 0.055, "OR": 0.07, "HI": 0.06}
        return high_tax_states.get(state, 0.045)  # 4.5% default

    def _get_marginal_rate(self, taxable_income: float, filing_status: str) -> float:
        """Get marginal tax rate."""
        brackets = self.TAX_BRACKETS.get(filing_status, self.TAX_BRACKETS["single"])

        for lower, upper, rate in brackets:
            if taxable_income <= upper:
                return rate * 100

        return 37.0

    def _may_qualify_eitc(self, answers: Dict[str, Any], filing_status: str, agi: float) -> bool:
        """Check if taxpayer may qualify for EITC."""
        if filing_status == "married_separate":
            return False

        num_children = min(3, int(answers.get("num_children", 0) or 0))

        limits = {
            "single": {0: 18591, 1: 49084, 2: 55768, 3: 59899},
            "married_joint": {0: 25511, 1: 56004, 2: 62688, 3: 66819},
        }

        status_key = "married_joint" if "married" in filing_status else "single"
        limit = limits[status_key].get(num_children, 18591)

        # Must have earned income
        has_earned = (
            float(answers.get("w2_wages_1", 0) or 0) > 0 or
            float(answers.get("business_gross_income", 0) or 0) > 0 or
            float(answers.get("1099_amount_1", 0) or 0) > 0
        )

        return has_earned and agi <= limit

    def _assess_confidence(self, answers: Dict[str, Any]) -> str:
        """Assess confidence level based on data completeness."""
        score = 0

        # Check income data
        if answers.get("w2_wages_1"):
            score += 3
        if answers.get("w2_federal_withheld_1"):
            score += 2

        # Check filing status
        if answers.get("filing_status") or answers.get("marital_status"):
            score += 2

        # Check dependents
        if answers.get("has_dependents") is not None:
            score += 1

        # Check deductions
        if answers.get("deduction_types"):
            score += 2

        if score >= 8:
            return "high"
        elif score >= 4:
            return "medium"
        else:
            return "low"

    def _identify_improvements(
        self, answers: Dict[str, Any], filing_status: str, agi: float
    ) -> List[str]:
        """Identify potential improvements to tax situation."""
        improvements = []

        # Retirement contributions
        current_401k = float(answers.get("w2_401k_amount_1", 0) or 0)
        if current_401k < 23500:
            room = 23500 - current_401k
            improvements.append(
                f"Increase 401(k) contributions by ${room:,.0f} to reduce taxable income"
            )

        # HSA
        hsa = float(answers.get("hsa_contribution", 0) or 0)
        if hsa == 0 and "medical" in str(answers.get("deduction_types", [])):
            improvements.append(
                "Consider HSA contributions for triple tax benefits"
            )

        # Charitable bunching
        charity = float(answers.get("charity_cash", 0) or 0)
        standard = self.STANDARD_DEDUCTIONS.get(filing_status, 15750)
        if charity > 0 and charity < standard * 0.5:
            improvements.append(
                "Consider bunching charitable donations to itemize every other year"
            )

        # IRA contribution
        if not answers.get("w2_401k_1"):
            improvements.append(
                "Consider IRA contribution (up to $7,000) for tax-advantaged savings"
            )

        return improvements[:3]  # Limit to top 3

    def _assess_missing_info_impact(self, answers: Dict[str, Any]) -> str:
        """Assess impact of missing information on estimate."""
        missing = []

        if not answers.get("w2_wages_1"):
            missing.append("W-2 income")

        if not answers.get("w2_federal_withheld_1"):
            missing.append("withholding")

        if answers.get("has_dependents") and not answers.get("num_children"):
            missing.append("dependent details")

        if not missing:
            return "All key information provided"

        return f"Estimate may change significantly once you enter: {', '.join(missing)}"
