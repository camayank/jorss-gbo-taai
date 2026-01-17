"""
Form 2210 - Underpayment of Estimated Tax by Individuals, Estates, and Trusts

Complete IRS Form 2210 implementation for estimated tax underpayment penalty:

Key concepts:
- Penalty applies when underpayment exceeds $1,000 after subtracting withholding/credits
- Calculated quarterly (Apr 15, Jun 15, Sep 15, Jan 15)
- Uses 8% annual penalty rate for 2025

Safe Harbor Rules (avoid penalty if payments >= smaller of):
1. 90% of current year tax, OR
2. 100% of prior year tax (110% if prior AGI > $150,000)

Special provisions:
- Farmers/Fishermen: 66⅔% safe harbor (instead of 90%)
- Casualty/disaster waiver available
- First year filer exemption scenarios

Penalty calculation:
- Rate: ~8% annual (varies quarterly per IRS)
- Formula: Underpayment × Rate × (Days / 365)

Note: This implements the SHORT METHOD (most taxpayers).
The REGULAR METHOD with quarterly compounding is available for complex cases.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field, model_validator
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


class PenaltyWaiverReason(str, Enum):
    """Reasons for waiving underpayment penalty (Part II, Box A-D)."""
    CASUALTY_DISASTER = "casualty_disaster"  # Box A: Casualty, disaster, or unusual circumstance
    RETIRED_DISABLED = "retired_disabled"  # Box B: Retired after age 62 or became disabled
    ANNUALIZED_INCOME = "annualized_income"  # Box C: Income varied substantially during year
    PRIOR_YEAR_TAX_ZERO = "prior_year_tax_zero"  # No prior year tax liability


class FilingStatus(str, Enum):
    """Filing status for Form 2210."""
    SINGLE = "single"
    MARRIED_JOINT = "married_joint"
    MARRIED_SEPARATE = "married_separate"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_WIDOW = "qualifying_widow"


class QuarterlyPayment(BaseModel):
    """Quarterly estimated tax payment details for Form 2210."""
    quarter: int = Field(ge=1, le=4, description="Payment quarter (1-4)")
    due_date: date = Field(description="Quarterly due date")
    payment_date: Optional[date] = Field(default=None, description="Actual payment date")
    required_payment: float = Field(default=0.0, ge=0, description="Required quarterly payment")
    amount_paid: float = Field(default=0.0, ge=0, description="Amount actually paid")
    withholding_allocated: float = Field(default=0.0, ge=0, description="Withholding allocated to quarter")

    @computed_field
    @property
    def total_payment(self) -> float:
        """Total payment including withholding."""
        return self.amount_paid + self.withholding_allocated

    @computed_field
    @property
    def underpayment(self) -> float:
        """Underpayment for this quarter."""
        return max(0, self.required_payment - self.total_payment)

    @computed_field
    @property
    def overpayment(self) -> float:
        """Overpayment for this quarter (carries to next)."""
        return max(0, self.total_payment - self.required_payment)

    @computed_field
    @property
    def is_on_time(self) -> bool:
        """Check if payment was made on time."""
        if not self.payment_date:
            return False
        return self.payment_date <= self.due_date

    @computed_field
    @property
    def days_late(self) -> int:
        """Days between due date and payment date."""
        if not self.payment_date:
            # Assume paid at filing deadline if not specified
            return 0
        if self.payment_date <= self.due_date:
            return 0
        return (self.payment_date - self.due_date).days


class Form2210Part1(BaseModel):
    """
    Form 2210 Part I - Required Annual Payment

    Determines if penalty applies and calculates required payment.
    """
    # Line 1: Current year tax (from Form 1040, line 24)
    line_1_current_year_tax: float = Field(
        default=0.0, ge=0,
        description="Line 1: Current year tax after credits"
    )

    # Line 2: Other taxes (self-employment, Medicare surtax, etc.)
    line_2_other_taxes: float = Field(
        default=0.0, ge=0,
        description="Line 2: Other taxes (SE tax, NIIT, etc.)"
    )

    # Line 3: Refundable credits
    line_3_refundable_credits: float = Field(
        default=0.0, ge=0,
        description="Line 3: Refundable credits"
    )

    # Line 4: Current year tax liability
    @computed_field
    @property
    def line_4_current_year_tax_liability(self) -> float:
        """Line 4: Total tax minus refundable credits."""
        return max(0, self.line_1_current_year_tax + self.line_2_other_taxes - self.line_3_refundable_credits)

    # Line 5: Multiply line 4 by 90%
    @computed_field
    @property
    def line_5_90_percent(self) -> float:
        """Line 5: 90% of current year tax."""
        return self.line_4_current_year_tax_liability * 0.90

    # Line 6: Withholding and estimated tax payments
    line_6_withholding: float = Field(
        default=0.0, ge=0,
        description="Line 6: Federal income tax withheld"
    )

    line_6_estimated_payments: float = Field(
        default=0.0, ge=0,
        description="Line 6: Estimated tax payments made"
    )

    @computed_field
    @property
    def line_6_total_payments(self) -> float:
        """Line 6: Total withholding plus estimated payments."""
        return self.line_6_withholding + self.line_6_estimated_payments

    # Line 7: Underpayment before threshold
    @computed_field
    @property
    def line_7_underpayment(self) -> float:
        """Line 7: Underpayment (line 4 - line 6)."""
        return max(0, self.line_4_current_year_tax_liability - self.line_6_total_payments)

    # Line 8: Prior year tax
    line_8_prior_year_tax: float = Field(
        default=0.0, ge=0,
        description="Line 8: Prior year total tax"
    )

    # Line 9: Prior year AGI (for 110% threshold determination)
    line_9_prior_year_agi: float = Field(
        default=0.0, ge=0,
        description="Line 9: Prior year AGI"
    )

    @computed_field
    @property
    def requires_110_percent(self) -> bool:
        """Check if 110% safe harbor applies (prior AGI > $150,000)."""
        return self.line_9_prior_year_agi > 150000

    @computed_field
    @property
    def safe_harbor_prior_year_pct(self) -> float:
        """Safe harbor percentage of prior year tax."""
        return 1.10 if self.requires_110_percent else 1.00

    @computed_field
    @property
    def line_10_safe_harbor_amount(self) -> float:
        """Line 10: Safe harbor amount (100% or 110% of prior year)."""
        return self.line_8_prior_year_tax * self.safe_harbor_prior_year_pct

    @computed_field
    @property
    def line_11_required_annual_payment(self) -> float:
        """Line 11: Required annual payment (smaller of 90% current or prior year safe harbor)."""
        if self.line_8_prior_year_tax == 0:
            # First year filer - use 90% of current year
            return self.line_5_90_percent
        return min(self.line_5_90_percent, self.line_10_safe_harbor_amount)


class Form2210Part2(BaseModel):
    """
    Form 2210 Part II - Reasons for Filing

    Determine filing requirements and waiver eligibility.
    """
    # Box A: Waiver for casualty/disaster
    box_a_casualty_waiver: bool = Field(
        default=False,
        description="Box A: Request waiver due to casualty, disaster, or unusual circumstances"
    )

    # Box B: Waiver for retirement/disability
    box_b_retired_disabled: bool = Field(
        default=False,
        description="Box B: Retired after age 62 or became disabled during tax year"
    )

    # Box C: Annualized income installment method
    box_c_annualized: bool = Field(
        default=False,
        description="Box C: Using annualized income installment method"
    )

    # Box D: Penalty waived based on prior year
    box_d_prior_year_waiver: bool = Field(
        default=False,
        description="Box D: Penalty waived because prior year tax was zero"
    )

    # Box E: Penalty using regular method
    box_e_regular_method: bool = Field(
        default=False,
        description="Box E: Calculate penalty using regular method"
    )

    @computed_field
    @property
    def requesting_waiver(self) -> bool:
        """Check if any waiver is being requested."""
        return self.box_a_casualty_waiver or self.box_b_retired_disabled or self.box_d_prior_year_waiver


class Form2210ShortMethod(BaseModel):
    """
    Form 2210 Part III - Short Method

    Simplified penalty calculation for most taxpayers.
    """
    # Line 12: Enter underpayment from Part I
    line_12_underpayment: float = Field(
        default=0.0, ge=0,
        description="Line 12: Underpayment from Part I, line 7"
    )

    # Line 13: Enter the amount paid after April 15
    line_13_amount_after_april: float = Field(
        default=0.0, ge=0,
        description="Line 13: Amount paid after April 15 through filing"
    )

    # Line 14: Enter the amount paid after June 15
    line_14_amount_after_june: float = Field(
        default=0.0, ge=0,
        description="Line 14: Amount paid after June 15 through filing"
    )

    # Line 15: Enter the amount paid after September 15
    line_15_amount_after_sept: float = Field(
        default=0.0, ge=0,
        description="Line 15: Amount paid after September 15 through filing"
    )

    # Penalty rate (8% for 2025)
    penalty_rate: float = Field(
        default=0.08,
        description="Annual penalty rate"
    )

    @computed_field
    @property
    def line_16_penalty(self) -> float:
        """
        Line 16: Penalty calculation using short method.

        Formula: Underpayment × rate × (number of days / 365)
        Simplified: Uses average days late approximation.
        """
        # Short method approximates using factor based on payment timing
        # Average: 6 months underpayment = 0.04 penalty factor (8% × 0.5 year)
        # Full year underpayment factor: 0.08

        # Calculate weighted penalty
        # Q1 underpayment for ~12 months
        # Q2 underpayment for ~9 months
        # Q3 underpayment for ~6 months
        # Q4 underpayment for ~3 months

        # Simplified short method: underpayment × rate × (days / 365)
        # Assume average of 183 days for simple calculation
        if self.line_12_underpayment <= 0:
            return 0.0

        # IRS short method uses simplified factor
        # Approximate: 0.04 for half-year average underpayment
        return round(self.line_12_underpayment * self.penalty_rate * 0.5, 2)


class Form2210RegularMethod(BaseModel):
    """
    Form 2210 Part IV - Regular Method (Schedule AI)

    Quarterly penalty calculation for complex situations.
    """
    quarters: List[QuarterlyPayment] = Field(
        default_factory=list,
        description="Quarterly payment details"
    )

    penalty_rate: float = Field(
        default=0.08,
        description="Annual penalty rate"
    )

    filing_deadline: date = Field(
        default_factory=lambda: date(2026, 4, 15),
        description="Tax filing deadline"
    )

    @computed_field
    @property
    def total_required_payment(self) -> float:
        """Total required payment across all quarters."""
        return sum(q.required_payment for q in self.quarters)

    @computed_field
    @property
    def total_underpayment(self) -> float:
        """Total underpayment across all quarters."""
        return sum(q.underpayment for q in self.quarters)

    def calculate_quarterly_penalty(self, quarter: QuarterlyPayment) -> float:
        """Calculate penalty for a single quarter."""
        if quarter.underpayment <= 0:
            return 0.0

        # Days from due date to filing deadline (or payment date if earlier)
        end_date = self.filing_deadline
        if quarter.payment_date and quarter.payment_date < end_date:
            end_date = quarter.payment_date

        days = (end_date - quarter.due_date).days
        if days <= 0:
            return 0.0

        # Penalty = underpayment × rate × (days / 365)
        penalty = quarter.underpayment * self.penalty_rate * (days / 365)
        return round(penalty, 2)

    @computed_field
    @property
    def total_penalty(self) -> float:
        """Total penalty using regular method."""
        return sum(self.calculate_quarterly_penalty(q) for q in self.quarters)


class Form2210(BaseModel):
    """
    IRS Form 2210 - Underpayment of Estimated Tax

    Complete form for calculating estimated tax underpayment penalty.

    Usage:
        form = Form2210(
            tax_year=2025,
            filing_status=FilingStatus.MARRIED_JOINT,
            current_year_tax=50000,
            withholding=30000,
            estimated_payments=10000,
            prior_year_tax=45000,
            prior_year_agi=200000
        )

        if form.penalty_applies:
            print(f"Penalty: ${form.penalty_amount}")
        else:
            print(f"Safe harbor met: {form.safe_harbor_reason}")
    """
    tax_year: int = Field(default=2025, description="Tax year")
    filing_status: FilingStatus = Field(
        default=FilingStatus.SINGLE,
        description="Filing status"
    )

    # Current year tax information
    current_year_tax: float = Field(
        default=0.0, ge=0,
        description="Current year total tax (after credits)"
    )
    other_taxes: float = Field(
        default=0.0, ge=0,
        description="Other taxes (self-employment, NIIT, etc.)"
    )
    refundable_credits: float = Field(
        default=0.0, ge=0,
        description="Refundable credits (EITC, child tax credit refundable portion, etc.)"
    )

    # Payments made
    withholding: float = Field(
        default=0.0, ge=0,
        description="Federal income tax withheld"
    )
    estimated_payments: float = Field(
        default=0.0, ge=0,
        description="Total estimated tax payments made"
    )
    amount_paid_with_extension: float = Field(
        default=0.0, ge=0,
        description="Amount paid with extension request"
    )

    # Prior year information
    prior_year_tax: float = Field(
        default=0.0, ge=0,
        description="Prior year total tax liability"
    )
    prior_year_agi: float = Field(
        default=0.0, ge=0,
        description="Prior year AGI"
    )

    # Special statuses
    is_farmer_or_fisherman: bool = Field(
        default=False,
        description="Qualifies for farmer/fisherman 66⅔% safe harbor"
    )
    is_first_year_filer: bool = Field(
        default=False,
        description="First year filer (no prior year return)"
    )

    # Waiver requests
    waiver_reason: Optional[PenaltyWaiverReason] = Field(
        default=None,
        description="Reason for requesting penalty waiver"
    )

    # Penalty calculation method
    use_regular_method: bool = Field(
        default=False,
        description="Use regular method instead of short method"
    )

    # Quarterly details (for regular method)
    quarterly_payments: List[QuarterlyPayment] = Field(
        default_factory=list,
        description="Quarterly payment details"
    )

    # Configuration
    underpayment_threshold: float = Field(
        default=1000.0,
        description="Minimum underpayment for penalty ($1,000)"
    )
    penalty_rate: float = Field(
        default=0.08,
        description="Annual penalty rate (8% for 2025)"
    )
    high_income_threshold: float = Field(
        default=150000.0,
        description="AGI threshold for 110% safe harbor"
    )

    @computed_field
    @property
    def total_tax_liability(self) -> float:
        """Total current year tax liability."""
        return max(0, self.current_year_tax + self.other_taxes - self.refundable_credits)

    @computed_field
    @property
    def total_payments(self) -> float:
        """Total payments (withholding + estimated + extension)."""
        return self.withholding + self.estimated_payments + self.amount_paid_with_extension

    @computed_field
    @property
    def underpayment_amount(self) -> float:
        """Gross underpayment amount."""
        return max(0, self.total_tax_liability - self.total_payments)

    @computed_field
    @property
    def requires_110_percent(self) -> bool:
        """Check if 110% safe harbor applies."""
        return self.prior_year_agi > self.high_income_threshold

    @computed_field
    @property
    def safe_harbor_current_year(self) -> float:
        """90% of current year tax (or 66⅔% for farmers)."""
        if self.is_farmer_or_fisherman:
            return self.total_tax_liability * 0.6667
        return self.total_tax_liability * 0.90

    @computed_field
    @property
    def safe_harbor_prior_year(self) -> float:
        """100% or 110% of prior year tax."""
        if self.is_first_year_filer or self.prior_year_tax == 0:
            return float('inf')  # No prior year requirement
        multiplier = 1.10 if self.requires_110_percent else 1.00
        return self.prior_year_tax * multiplier

    @computed_field
    @property
    def required_annual_payment(self) -> float:
        """Minimum required payment to avoid penalty."""
        if self.is_first_year_filer or self.prior_year_tax == 0:
            return self.safe_harbor_current_year
        return min(self.safe_harbor_current_year, self.safe_harbor_prior_year)

    @computed_field
    @property
    def safe_harbor_met(self) -> bool:
        """Check if safe harbor was met."""
        return self.total_payments >= self.required_annual_payment

    @computed_field
    @property
    def safe_harbor_reason(self) -> Optional[str]:
        """Explanation of which safe harbor was met."""
        if not self.safe_harbor_met:
            return None

        if self.total_payments >= self.total_tax_liability:
            return "Payments equal or exceed current year tax"

        if self.total_payments >= self.safe_harbor_current_year:
            if self.is_farmer_or_fisherman:
                return "Met 66⅔% farmer/fisherman safe harbor"
            return "Met 90% of current year tax safe harbor"

        if self.total_payments >= self.safe_harbor_prior_year:
            pct = "110%" if self.requires_110_percent else "100%"
            return f"Met {pct} of prior year tax safe harbor"

        return None

    @computed_field
    @property
    def under_threshold(self) -> bool:
        """Check if underpayment is under $1,000 threshold."""
        return self.underpayment_amount < self.underpayment_threshold

    @computed_field
    @property
    def penalty_applies(self) -> bool:
        """Check if penalty applies."""
        # No penalty if safe harbor met
        if self.safe_harbor_met:
            return False

        # No penalty if underpayment under $1,000
        if self.under_threshold:
            return False

        # No penalty if waiver granted
        if self.waiver_reason is not None:
            return False

        # No penalty if prior year tax was zero (and taxpayer was U.S. citizen)
        if self.prior_year_tax == 0 and not self.is_first_year_filer:
            return False

        return True

    @computed_field
    @property
    def penalty_amount(self) -> float:
        """Calculate estimated tax penalty."""
        if not self.penalty_applies:
            return 0.0

        # Calculate shortfall from required payment
        shortfall = max(0, self.required_annual_payment - self.total_payments)

        if shortfall <= 0:
            return 0.0

        if self.use_regular_method and self.quarterly_payments:
            # Use regular method with quarterly compounding
            regular = Form2210RegularMethod(
                quarters=self.quarterly_payments,
                penalty_rate=self.penalty_rate
            )
            return regular.total_penalty

        # Short method: simplified annual calculation
        # Average underpayment period is approximately 6 months
        penalty = shortfall * self.penalty_rate * 0.5
        return round(penalty, 2)

    @computed_field
    @property
    def penalty_per_quarter(self) -> float:
        """Approximate penalty if evenly distributed across quarters."""
        if not self.penalty_applies:
            return 0.0
        return round(self.penalty_amount / 4, 2)

    @computed_field
    @property
    def exemption_reason(self) -> Optional[str]:
        """Reason why penalty doesn't apply (if exempt)."""
        if self.safe_harbor_met:
            return self.safe_harbor_reason

        if self.under_threshold:
            return f"Underpayment ${self.underpayment_amount:.2f} is under $1,000 threshold"

        if self.waiver_reason:
            waiver_descriptions = {
                PenaltyWaiverReason.CASUALTY_DISASTER: "Casualty, disaster, or unusual circumstance waiver",
                PenaltyWaiverReason.RETIRED_DISABLED: "Retired after age 62 or became disabled",
                PenaltyWaiverReason.ANNUALIZED_INCOME: "Income varied substantially (annualized method)",
                PenaltyWaiverReason.PRIOR_YEAR_TAX_ZERO: "Prior year tax was zero"
            }
            return waiver_descriptions.get(self.waiver_reason, "Waiver granted")

        if self.prior_year_tax == 0 and not self.is_first_year_filer:
            return "Prior year tax was zero"

        return None

    def get_part1(self) -> Form2210Part1:
        """Generate Part I of Form 2210."""
        return Form2210Part1(
            line_1_current_year_tax=self.current_year_tax,
            line_2_other_taxes=self.other_taxes,
            line_3_refundable_credits=self.refundable_credits,
            line_6_withholding=self.withholding,
            line_6_estimated_payments=self.estimated_payments,
            line_8_prior_year_tax=self.prior_year_tax,
            line_9_prior_year_agi=self.prior_year_agi
        )

    def get_short_method(self) -> Form2210ShortMethod:
        """Generate short method calculation."""
        return Form2210ShortMethod(
            line_12_underpayment=self.underpayment_amount,
            penalty_rate=self.penalty_rate
        )

    def get_regular_method(self) -> Form2210RegularMethod:
        """Generate regular method calculation."""
        return Form2210RegularMethod(
            quarters=self.quarterly_payments,
            penalty_rate=self.penalty_rate
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert form to dictionary for reporting."""
        return {
            "tax_year": self.tax_year,
            "filing_status": self.filing_status.value,

            # Tax liability
            "current_year_tax": self.current_year_tax,
            "other_taxes": self.other_taxes,
            "refundable_credits": self.refundable_credits,
            "total_tax_liability": self.total_tax_liability,

            # Payments
            "withholding": self.withholding,
            "estimated_payments": self.estimated_payments,
            "total_payments": self.total_payments,

            # Prior year
            "prior_year_tax": self.prior_year_tax,
            "prior_year_agi": self.prior_year_agi,
            "requires_110_percent": self.requires_110_percent,

            # Safe harbor
            "safe_harbor_current_year": round(self.safe_harbor_current_year, 2),
            "safe_harbor_prior_year": round(self.safe_harbor_prior_year, 2) if self.safe_harbor_prior_year != float('inf') else None,
            "required_annual_payment": round(self.required_annual_payment, 2),
            "safe_harbor_met": self.safe_harbor_met,
            "safe_harbor_reason": self.safe_harbor_reason,

            # Underpayment
            "underpayment_amount": round(self.underpayment_amount, 2),
            "under_threshold": self.under_threshold,

            # Penalty
            "penalty_applies": self.penalty_applies,
            "penalty_amount": self.penalty_amount,
            "exemption_reason": self.exemption_reason,

            # Special statuses
            "is_farmer_or_fisherman": self.is_farmer_or_fisherman,
            "is_first_year_filer": self.is_first_year_filer,
            "waiver_reason": self.waiver_reason.value if self.waiver_reason else None
        }

    def to_form_1040(self) -> Dict[str, float]:
        """Generate values for Form 1040 Schedule."""
        return {
            "estimated_tax_penalty": self.penalty_amount
        }


class AnnualizedIncomeInstallment(BaseModel):
    """
    Schedule AI - Annualized Income Installment Method

    For taxpayers whose income varied substantially during the year.
    Allows quarterly payments based on actual income received in each period.
    """
    # Annualization periods
    # Period 1: Jan 1 - Mar 31 (annualize by 4)
    # Period 2: Jan 1 - May 31 (annualize by 2.4)
    # Period 3: Jan 1 - Aug 31 (annualize by 1.5)
    # Period 4: Jan 1 - Dec 31 (annualize by 1)

    period_1_income: float = Field(
        default=0.0,
        description="Income for Jan 1 - Mar 31"
    )
    period_2_income: float = Field(
        default=0.0,
        description="Income for Jan 1 - May 31"
    )
    period_3_income: float = Field(
        default=0.0,
        description="Income for Jan 1 - Aug 31"
    )
    period_4_income: float = Field(
        default=0.0,
        description="Income for full year"
    )

    deductions: float = Field(
        default=0.0, ge=0,
        description="Standard or itemized deductions"
    )

    exemptions: float = Field(
        default=0.0, ge=0,
        description="Exemption amount"
    )

    # Annualization factors
    FACTOR_1: float = 4.0
    FACTOR_2: float = 2.4
    FACTOR_3: float = 1.5
    FACTOR_4: float = 1.0

    @computed_field
    @property
    def annualized_income_p1(self) -> float:
        """Annualized income for period 1."""
        return self.period_1_income * self.FACTOR_1

    @computed_field
    @property
    def annualized_income_p2(self) -> float:
        """Annualized income for period 2."""
        return self.period_2_income * self.FACTOR_2

    @computed_field
    @property
    def annualized_income_p3(self) -> float:
        """Annualized income for period 3."""
        return self.period_3_income * self.FACTOR_3

    @computed_field
    @property
    def annualized_income_p4(self) -> float:
        """Annualized income for period 4 (full year)."""
        return self.period_4_income * self.FACTOR_4

    def calculate_required_payment(self, period: int, tax_rate: float = 0.22) -> float:
        """
        Calculate required payment for a period.

        Args:
            period: Period number (1-4)
            tax_rate: Estimated marginal tax rate
        """
        annualized = {
            1: self.annualized_income_p1,
            2: self.annualized_income_p2,
            3: self.annualized_income_p3,
            4: self.annualized_income_p4
        }.get(period, 0)

        taxable = max(0, annualized - self.deductions - self.exemptions)
        estimated_tax = taxable * tax_rate

        # Cumulative payment percentages
        cumulative_pct = {1: 0.25, 2: 0.50, 3: 0.75, 4: 1.00}
        return estimated_tax * cumulative_pct.get(period, 0)


def calculate_form_2210(
    current_year_tax: float,
    withholding: float,
    estimated_payments: float,
    prior_year_tax: float,
    prior_year_agi: float,
    other_taxes: float = 0.0,
    refundable_credits: float = 0.0,
    is_farmer_or_fisherman: bool = False,
    filing_status: FilingStatus = FilingStatus.SINGLE
) -> Dict[str, Any]:
    """
    Convenience function to calculate Form 2210 penalty.

    Args:
        current_year_tax: Current year total tax
        withholding: Federal income tax withheld
        estimated_payments: Total estimated payments made
        prior_year_tax: Prior year total tax
        prior_year_agi: Prior year AGI
        other_taxes: Self-employment tax, NIIT, etc.
        refundable_credits: EITC, refundable child credit, etc.
        is_farmer_or_fisherman: Qualifies for 66⅔% safe harbor
        filing_status: Filing status

    Returns:
        Dictionary with penalty calculation results
    """
    form = Form2210(
        current_year_tax=current_year_tax,
        withholding=withholding,
        estimated_payments=estimated_payments,
        prior_year_tax=prior_year_tax,
        prior_year_agi=prior_year_agi,
        other_taxes=other_taxes,
        refundable_credits=refundable_credits,
        is_farmer_or_fisherman=is_farmer_or_fisherman,
        filing_status=filing_status
    )

    return form.to_dict()


def check_safe_harbor(
    total_payments: float,
    current_year_tax: float,
    prior_year_tax: float,
    prior_year_agi: float,
    is_farmer_or_fisherman: bool = False
) -> Dict[str, Any]:
    """
    Quick check if safe harbor is met.

    Args:
        total_payments: Total withholding + estimated payments
        current_year_tax: Current year total tax liability
        prior_year_tax: Prior year total tax
        prior_year_agi: Prior year AGI
        is_farmer_or_fisherman: Qualifies for 66⅔% safe harbor

    Returns:
        Dictionary with safe harbor status
    """
    # Calculate thresholds
    current_year_pct = 0.6667 if is_farmer_or_fisherman else 0.90
    current_year_threshold = current_year_tax * current_year_pct

    prior_year_pct = 1.10 if prior_year_agi > 150000 else 1.00
    prior_year_threshold = prior_year_tax * prior_year_pct if prior_year_tax > 0 else float('inf')

    required_payment = min(current_year_threshold, prior_year_threshold)
    safe_harbor_met = total_payments >= required_payment

    return {
        "safe_harbor_met": safe_harbor_met,
        "total_payments": total_payments,
        "required_payment": round(required_payment, 2),
        "current_year_threshold": round(current_year_threshold, 2),
        "prior_year_threshold": round(prior_year_threshold, 2) if prior_year_threshold != float('inf') else None,
        "prior_year_pct": prior_year_pct * 100,
        "shortfall": max(0, round(required_payment - total_payments, 2)),
        "excess": max(0, round(total_payments - required_payment, 2))
    }
