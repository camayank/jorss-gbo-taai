"""
Form 1040-ES - Estimated Tax for Individuals

Complete IRS Form 1040-ES implementation for quarterly estimated tax payments:

Key concepts:
- Pay-as-you-go system for income not subject to withholding
- Self-employment income, investment income, rental income
- Quarterly due dates: Apr 15, Jun 15, Sep 15, Jan 15

Safe Harbor Rules (avoid penalty):
1. Pay 90% of current year tax, OR
2. Pay 100% of prior year tax (110% if AGI > $150k)

Who must pay estimated taxes:
- Self-employed individuals
- Partners, S-Corp shareholders
- Investors with significant capital gains/dividends
- Retirees with pension/IRA distributions
- Anyone with insufficient withholding

Payment schedule:
- Q1 (Jan-Mar): Due April 15
- Q2 (Apr-May): Due June 15
- Q3 (Jun-Aug): Due September 15
- Q4 (Sep-Dec): Due January 15 (next year)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


class Quarter(str, Enum):
    """Estimated tax payment quarters."""
    Q1 = "Q1"  # Jan-Mar, due Apr 15
    Q2 = "Q2"  # Apr-May, due Jun 15
    Q3 = "Q3"  # Jun-Aug, due Sep 15
    Q4 = "Q4"  # Sep-Dec, due Jan 15


class PaymentMethod(str, Enum):
    """Methods for making estimated tax payments."""
    DIRECT_PAY = "direct_pay"  # IRS Direct Pay
    EFTPS = "eftps"  # Electronic Federal Tax Payment System
    CHECK = "check"  # Paper check
    CREDIT_CARD = "credit_card"  # Credit/debit card
    CASH = "cash"  # Cash at retail partner


class EstimatedTaxPayment(BaseModel):
    """Individual estimated tax payment record."""
    quarter: Quarter = Field(description="Payment quarter")
    due_date: date = Field(description="Payment due date")
    payment_date: Optional[date] = Field(default=None, description="Actual payment date")
    amount_due: float = Field(default=0.0, ge=0, description="Amount due")
    amount_paid: float = Field(default=0.0, ge=0, description="Amount paid")
    payment_method: Optional[PaymentMethod] = Field(default=None, description="Payment method")
    confirmation_number: str = Field(default="", description="Payment confirmation")

    @computed_field
    @property
    def is_paid(self) -> bool:
        """Check if payment has been made."""
        return self.amount_paid > 0

    @computed_field
    @property
    def is_on_time(self) -> bool:
        """Check if payment was made on time."""
        if not self.payment_date:
            return False
        return self.payment_date <= self.due_date

    @computed_field
    @property
    def underpayment(self) -> float:
        """Calculate underpayment amount."""
        return max(0, self.amount_due - self.amount_paid)

    @computed_field
    @property
    def overpayment(self) -> float:
        """Calculate overpayment amount."""
        return max(0, self.amount_paid - self.amount_due)

    @computed_field
    @property
    def days_late(self) -> int:
        """Calculate days late if payment was late."""
        if not self.payment_date or self.is_on_time:
            return 0
        return (self.payment_date - self.due_date).days


class Form1040ESWorksheet(BaseModel):
    """
    Form 1040-ES Estimated Tax Worksheet

    Calculates required estimated tax payments for the year.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Line 1: Adjusted gross income expected
    line_1_expected_agi: float = Field(
        default=0.0,
        description="Line 1: Expected adjusted gross income"
    )

    # Line 2: Deductions (standard or itemized)
    line_2_deductions: float = Field(
        default=0.0, ge=0,
        description="Line 2: Expected deductions"
    )

    # Line 3: Subtract line 2 from line 1
    @computed_field
    @property
    def line_3_taxable_income(self) -> float:
        """Line 3: Expected taxable income."""
        return max(0, self.line_1_expected_agi - self.line_2_deductions)

    # Line 4: Tax on line 3 (use tax tables/brackets)
    line_4_tax: float = Field(
        default=0.0, ge=0,
        description="Line 4: Tax on expected taxable income"
    )

    # Line 5: Alternative minimum tax (if applicable)
    line_5_amt: float = Field(
        default=0.0, ge=0,
        description="Line 5: Alternative minimum tax"
    )

    # Line 6: Add lines 4 and 5
    @computed_field
    @property
    def line_6_total_tax(self) -> float:
        """Line 6: Total tax."""
        return self.line_4_tax + self.line_5_amt

    # Line 7: Self-employment tax
    line_7_se_tax: float = Field(
        default=0.0, ge=0,
        description="Line 7: Self-employment tax"
    )

    # Line 8: Other taxes (NIIT, additional Medicare, etc.)
    line_8_other_taxes: float = Field(
        default=0.0, ge=0,
        description="Line 8: Other taxes"
    )

    # Line 9: Add lines 6, 7, and 8
    @computed_field
    @property
    def line_9_total_tax_liability(self) -> float:
        """Line 9: Total expected tax liability."""
        return self.line_6_total_tax + self.line_7_se_tax + self.line_8_other_taxes

    # Line 10: Credits
    line_10_credits: float = Field(
        default=0.0, ge=0,
        description="Line 10: Expected credits"
    )

    # Line 11: Subtract line 10 from line 9
    @computed_field
    @property
    def line_11_net_tax(self) -> float:
        """Line 11: Net expected tax."""
        return max(0, self.line_9_total_tax_liability - self.line_10_credits)

    # Line 12: Other payments/refundable credits
    line_12_other_payments: float = Field(
        default=0.0, ge=0,
        description="Line 12: Other payments and refundable credits"
    )

    # Line 13a: Earned income credit
    line_13a_eic: float = Field(
        default=0.0, ge=0,
        description="Line 13a: Earned income credit"
    )

    # Line 13b: Additional child tax credit
    line_13b_actc: float = Field(
        default=0.0, ge=0,
        description="Line 13b: Additional child tax credit"
    )

    # Line 13c: Other refundable credits
    line_13c_other_refundable: float = Field(
        default=0.0, ge=0,
        description="Line 13c: Other refundable credits"
    )

    # Line 14a: Total refundable credits
    @computed_field
    @property
    def line_14a_total_refundable(self) -> float:
        """Line 14a: Total refundable credits."""
        return (
            self.line_12_other_payments +
            self.line_13a_eic +
            self.line_13b_actc +
            self.line_13c_other_refundable
        )

    # Line 14b: Current year tax minus refundable credits
    @computed_field
    @property
    def line_14b_current_year_tax(self) -> float:
        """Line 14b: Current year tax after refundable credits."""
        return max(0, self.line_11_net_tax - self.line_14a_total_refundable)

    # Line 15: Withholding expected
    line_15_withholding: float = Field(
        default=0.0, ge=0,
        description="Line 15: Expected withholding"
    )

    # Line 16a: Subtract line 15 from line 14b
    @computed_field
    @property
    def line_16a_balance(self) -> float:
        """Line 16a: Balance of tax after withholding."""
        return max(0, self.line_14b_current_year_tax - self.line_15_withholding)

    # Safe Harbor Calculation
    # Line 16b: Prior year tax
    line_16b_prior_year_tax: float = Field(
        default=0.0, ge=0,
        description="Line 16b: Prior year tax liability"
    )

    # Line 16c: Prior year AGI (for 110% threshold)
    line_16c_prior_year_agi: float = Field(
        default=0.0, ge=0,
        description="Line 16c: Prior year AGI"
    )

    @computed_field
    @property
    def safe_harbor_percentage(self) -> float:
        """Safe harbor percentage based on prior year AGI."""
        # 110% if prior AGI > $150k, otherwise 100%
        if self.line_16c_prior_year_agi > 150000:
            return 1.10
        return 1.00

    @computed_field
    @property
    def safe_harbor_amount(self) -> float:
        """Safe harbor amount (prior year tax × percentage)."""
        return self.line_16b_prior_year_tax * self.safe_harbor_percentage

    @computed_field
    @property
    def required_annual_payment(self) -> float:
        """
        Required annual payment to avoid penalty.

        Smaller of:
        - 90% of current year tax
        - 100%/110% of prior year tax
        """
        current_year_90pct = self.line_14b_current_year_tax * 0.90
        prior_year_safe_harbor = self.safe_harbor_amount

        # If no prior year tax, use 90% of current
        if self.line_16b_prior_year_tax == 0:
            return current_year_90pct

        return min(current_year_90pct, prior_year_safe_harbor)

    @computed_field
    @property
    def quarterly_payment(self) -> float:
        """Required quarterly payment amount."""
        required = self.required_annual_payment - self.line_15_withholding
        if required <= 0:
            return 0.0
        return round(required / 4, 2)

    @computed_field
    @property
    def is_estimated_tax_required(self) -> bool:
        """Determine if estimated tax payments are required."""
        # Generally required if expecting to owe $1,000+
        balance = self.line_16a_balance
        return balance >= 1000


class Form1040ES(BaseModel):
    """
    Form 1040-ES - Estimated Tax for Individuals

    Complete estimated tax payment tracking and calculation.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Taxpayer information
    taxpayer_name: str = Field(default="", description="Taxpayer name")
    taxpayer_ssn: str = Field(default="", description="Taxpayer SSN")
    filing_status: str = Field(default="single", description="Filing status")

    # Worksheet
    worksheet: Form1040ESWorksheet = Field(
        default_factory=Form1040ESWorksheet,
        description="Estimated tax worksheet"
    )

    # Quarterly payments
    payments: List[EstimatedTaxPayment] = Field(
        default_factory=list,
        description="Quarterly payment records"
    )

    def get_due_dates(self) -> Dict[Quarter, date]:
        """Get due dates for each quarter."""
        year = self.tax_year
        return {
            Quarter.Q1: date(year, 4, 15),
            Quarter.Q2: date(year, 6, 15),
            Quarter.Q3: date(year, 9, 15),
            Quarter.Q4: date(year + 1, 1, 15),
        }

    def initialize_payments(self) -> None:
        """Initialize payment schedule with calculated amounts."""
        due_dates = self.get_due_dates()
        quarterly_amount = self.worksheet.quarterly_payment

        self.payments = [
            EstimatedTaxPayment(
                quarter=quarter,
                due_date=due_date,
                amount_due=quarterly_amount,
            )
            for quarter, due_date in due_dates.items()
        ]

    def record_payment(
        self,
        quarter: Quarter,
        amount: float,
        payment_date: date,
        method: Optional[PaymentMethod] = None,
        confirmation: str = ""
    ) -> None:
        """Record an estimated tax payment."""
        for payment in self.payments:
            if payment.quarter == quarter:
                payment.amount_paid = amount
                payment.payment_date = payment_date
                payment.payment_method = method
                payment.confirmation_number = confirmation
                return

        # If quarter not found, add new payment
        due_dates = self.get_due_dates()
        self.payments.append(EstimatedTaxPayment(
            quarter=quarter,
            due_date=due_dates[quarter],
            amount_due=self.worksheet.quarterly_payment,
            amount_paid=amount,
            payment_date=payment_date,
            payment_method=method,
            confirmation_number=confirmation,
        ))

    @computed_field
    @property
    def total_required(self) -> float:
        """Total required estimated tax for the year."""
        return self.worksheet.required_annual_payment

    @computed_field
    @property
    def total_paid(self) -> float:
        """Total estimated tax paid."""
        return sum(p.amount_paid for p in self.payments)

    @computed_field
    @property
    def total_underpayment(self) -> float:
        """Total underpayment across all quarters."""
        return sum(p.underpayment for p in self.payments)

    @computed_field
    @property
    def payments_on_time(self) -> int:
        """Count of payments made on time."""
        return sum(1 for p in self.payments if p.is_on_time)

    @computed_field
    @property
    def remaining_balance(self) -> float:
        """Remaining estimated tax balance."""
        required = max(0, self.worksheet.required_annual_payment - self.worksheet.line_15_withholding)
        return max(0, required - self.total_paid)

    def get_next_payment(self) -> Optional[EstimatedTaxPayment]:
        """Get the next unpaid or underpaid payment."""
        for payment in self.payments:
            if payment.underpayment > 0:
                return payment
        return None

    def calculate_annualized_income_installment(
        self,
        income_by_period: Dict[str, float],
    ) -> Dict[Quarter, float]:
        """
        Calculate required payments using annualized income method.

        Useful for taxpayers with uneven income throughout the year.

        Args:
            income_by_period: Income for each period (Q1, Q1-Q2, Q1-Q3, Q1-Q4)

        Returns:
            Required payment for each quarter
        """
        # Annualization factors
        factors = {
            Quarter.Q1: 4.0,    # 3 months × 4 = 12 months
            Quarter.Q2: 2.4,    # 5 months × 2.4 = 12 months
            Quarter.Q3: 1.5,    # 8 months × 1.5 = 12 months
            Quarter.Q4: 1.0,    # 12 months × 1 = 12 months
        }

        # Cumulative percentages
        cumulative_pct = {
            Quarter.Q1: 0.225,  # 22.5%
            Quarter.Q2: 0.45,   # 45%
            Quarter.Q3: 0.675,  # 67.5%
            Quarter.Q4: 0.90,   # 90%
        }

        required_payments = {}
        prior_required = 0.0

        for quarter in [Quarter.Q1, Quarter.Q2, Quarter.Q3, Quarter.Q4]:
            period_key = f"Q1-{quarter.value}" if quarter != Quarter.Q1 else "Q1"
            income = income_by_period.get(period_key, 0)

            # Annualize the income
            annualized = income * factors[quarter]

            # Calculate tax on annualized income (simplified)
            # In practice, would use full tax calculation
            tax_rate = 0.25  # Simplified assumption
            annualized_tax = annualized * tax_rate

            # Required cumulative payment
            cumulative_required = annualized_tax * cumulative_pct[quarter]

            # This quarter's payment
            required_payments[quarter] = max(0, cumulative_required - prior_required)
            prior_required = cumulative_required

        return required_payments

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.tax_year,
            "filing_status": self.filing_status,
            "worksheet": {
                "expected_agi": self.worksheet.line_1_expected_agi,
                "expected_tax": self.worksheet.line_14b_current_year_tax,
                "withholding": self.worksheet.line_15_withholding,
                "required_annual_payment": self.worksheet.required_annual_payment,
                "quarterly_payment": self.worksheet.quarterly_payment,
                "safe_harbor_percentage": self.worksheet.safe_harbor_percentage * 100,
                "is_required": self.worksheet.is_estimated_tax_required,
            },
            "payments": [
                {
                    "quarter": p.quarter.value,
                    "due_date": p.due_date.isoformat(),
                    "amount_due": p.amount_due,
                    "amount_paid": p.amount_paid,
                    "is_paid": p.is_paid,
                    "is_on_time": p.is_on_time,
                }
                for p in self.payments
            ],
            "summary": {
                "total_required": self.total_required,
                "total_paid": self.total_paid,
                "remaining_balance": self.remaining_balance,
                "payments_on_time": self.payments_on_time,
            },
        }


def calculate_estimated_tax(
    expected_income: float,
    expected_deductions: float,
    expected_tax: float,
    expected_withholding: float = 0.0,
    se_tax: float = 0.0,
    credits: float = 0.0,
    prior_year_tax: float = 0.0,
    prior_year_agi: float = 0.0,
) -> Dict[str, Any]:
    """
    Convenience function to calculate estimated tax requirements.

    Args:
        expected_income: Expected AGI for the year
        expected_deductions: Expected deductions
        expected_tax: Expected income tax
        expected_withholding: Expected W-2/other withholding
        se_tax: Expected self-employment tax
        credits: Expected tax credits
        prior_year_tax: Prior year total tax (for safe harbor)
        prior_year_agi: Prior year AGI (for 110% threshold)

    Returns:
        Dictionary with estimated tax calculation results
    """
    worksheet = Form1040ESWorksheet(
        line_1_expected_agi=expected_income,
        line_2_deductions=expected_deductions,
        line_4_tax=expected_tax,
        line_7_se_tax=se_tax,
        line_10_credits=credits,
        line_15_withholding=expected_withholding,
        line_16b_prior_year_tax=prior_year_tax,
        line_16c_prior_year_agi=prior_year_agi,
    )

    return {
        "taxable_income": worksheet.line_3_taxable_income,
        "total_tax": worksheet.line_14b_current_year_tax,
        "withholding": expected_withholding,
        "balance_due": worksheet.line_16a_balance,
        "safe_harbor_pct": worksheet.safe_harbor_percentage * 100,
        "safe_harbor_amount": worksheet.safe_harbor_amount,
        "required_annual": worksheet.required_annual_payment,
        "quarterly_payment": worksheet.quarterly_payment,
        "is_required": worksheet.is_estimated_tax_required,
    }


def calculate_penalty_estimate(
    required_payment: float,
    actual_payment: float,
    days_late: int = 0,
    annual_rate: float = 0.08,
) -> Dict[str, Any]:
    """
    Estimate underpayment penalty for a quarter.

    Args:
        required_payment: Required quarterly payment
        actual_payment: Actual payment made
        days_late: Days payment was late
        annual_rate: IRS underpayment rate (default 8%)

    Returns:
        Dictionary with penalty estimate
    """
    underpayment = max(0, required_payment - actual_payment)

    if underpayment == 0:
        return {
            "underpayment": 0,
            "penalty": 0,
            "days_late": days_late,
        }

    # Penalty = underpayment × rate × (days / 365)
    # Minimum period is from due date to payment date or Apr 15
    penalty_days = max(days_late, 0)
    penalty = underpayment * annual_rate * (penalty_days / 365)

    return {
        "underpayment": underpayment,
        "penalty": round(penalty, 2),
        "days_late": penalty_days,
        "annual_rate": annual_rate * 100,
    }
