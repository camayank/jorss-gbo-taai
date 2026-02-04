"""
Form 1040-X - Amended U.S. Individual Income Tax Return

Used to correct errors on previously filed Form 1040, 1040-SR, or 1040-NR.

When to File Form 1040-X:
- Report income you didn't report
- Correct income that was reported incorrectly
- Change filing status
- Add or remove dependents
- Claim credits/deductions you didn't claim
- Correct credits/deductions that were calculated incorrectly

Time Limits:
- Generally within 3 years from original due date
- Within 2 years from date tax was paid (if later)
- For refund claims, later of 3 years from filing or 2 years from payment

What You Can't Amend:
- Math errors (IRS corrects automatically)
- Missing schedules (IRS will request)

Per IRS Form 1040-X Instructions and IRC Section 6511.
"""

from typing import Optional, List, Dict, Any, ClassVar
from pydantic import BaseModel, Field
from enum import Enum
from datetime import date
from models._decimal_utils import money


class FilingStatusChange(BaseModel):
    """Change in filing status from original to amended."""
    original_status: str = Field(default="", description="Original filing status")
    amended_status: str = Field(default="", description="Amended filing status")
    status_changed: bool = Field(default=False)


class DependentChange(BaseModel):
    """Change in dependents from original to amended."""
    dependent_name: str = Field(default="")
    dependent_ssn: Optional[str] = Field(default=None)
    relationship: str = Field(default="")
    action: str = Field(default="add", description="add, remove, or correct")


class Form1040X_Line(BaseModel):
    """
    Represents a line item on Form 1040-X with original, change, and corrected amounts.

    Column A: Original amount from original return
    Column B: Net change (increase or decrease)
    Column C: Corrected amount (A + B if increase, A - B if decrease)
    """
    line_number: str = Field(default="", description="Line number on form")
    description: str = Field(default="", description="Description of line item")
    original_amount: float = Field(default=0.0, description="Column A: Original amount")
    net_change: float = Field(default=0.0, description="Column B: Net change (+/-)")

    @property
    def corrected_amount(self) -> float:
        """Column C: Calculate corrected amount."""
        return self.original_amount + self.net_change


class AmendmentReason(str, Enum):
    """Common reasons for filing Form 1040-X."""
    MISSED_INCOME = "missed_income"
    INCORRECT_INCOME = "incorrect_income"
    FILING_STATUS_CHANGE = "filing_status_change"
    DEPENDENT_CHANGE = "dependent_change"
    MISSED_DEDUCTION = "missed_deduction"
    INCORRECT_DEDUCTION = "incorrect_deduction"
    MISSED_CREDIT = "missed_credit"
    INCORRECT_CREDIT = "incorrect_credit"
    CARRYBACK_CLAIM = "carryback_claim"
    IRS_ADJUSTMENT_RESPONSE = "irs_adjustment_response"
    OTHER = "other"


class Form1040X(BaseModel):
    """
    Form 1040-X - Amended U.S. Individual Income Tax Return.

    Tracks changes between original and corrected amounts for all
    affected line items, calculates refund or additional tax owed.
    """

    # Time limits
    REFUND_CLAIM_YEARS: ClassVar[int] = 3
    PAYMENT_CLAIM_YEARS: ClassVar[int] = 2

    # Taxpayer identification
    taxpayer_name: str = Field(default="", description="Taxpayer name")
    taxpayer_ssn: str = Field(default="", description="SSN")
    spouse_name: Optional[str] = Field(default=None)
    spouse_ssn: Optional[str] = Field(default=None)

    # Tax year being amended
    tax_year: int = Field(description="Tax year being amended")
    original_return_filed_date: Optional[date] = Field(default=None)
    amendment_filed_date: Optional[date] = Field(default=None)

    # Filing status
    filing_status_change: FilingStatusChange = Field(
        default_factory=FilingStatusChange
    )

    # Dependents changes
    dependent_changes: List[DependentChange] = Field(default_factory=list)

    # Part I: Exemptions and Dependents (legacy, but still used for tracking)
    original_dependents_count: int = Field(default=0, ge=0)
    corrected_dependents_count: int = Field(default=0, ge=0)

    # Part II: Presidential Election Campaign Fund
    # (rarely changes, omitted for simplicity)

    # Income Section (Lines 1-8)
    line_1_agi: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="1",
            description="Adjusted gross income"
        )
    )

    # Deductions Section
    line_2_itemized_or_standard: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="2",
            description="Itemized deductions or standard deduction"
        )
    )
    line_3_qbi_deduction: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="3",
            description="Qualified business income deduction"
        )
    )
    line_4_taxable_income: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="4",
            description="Taxable income"
        )
    )

    # Tax and Credits Section
    line_5_tax: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="5",
            description="Tax (from Tax Table or other method)"
        )
    )
    line_6_nonrefundable_credits: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="6",
            description="Nonrefundable credits"
        )
    )
    line_7_tax_after_credits: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="7",
            description="Tax after nonrefundable credits"
        )
    )
    line_8_other_taxes: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="8",
            description="Other taxes (SE tax, AMT, etc.)"
        )
    )
    line_9_total_tax: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="9",
            description="Total tax"
        )
    )

    # Payments Section
    line_10_withholding: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="10",
            description="Federal income tax withheld"
        )
    )
    line_11_estimated_payments: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="11",
            description="Estimated tax payments"
        )
    )
    line_12_refundable_credits: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="12",
            description="Refundable credits"
        )
    )
    line_13_total_payments: Form1040X_Line = Field(
        default_factory=lambda: Form1040X_Line(
            line_number="13",
            description="Total payments and refundable credits"
        )
    )

    # Overpayment/Amount Owed
    line_14_overpayment_original: float = Field(
        default=0.0,
        description="Overpayment shown on original return"
    )
    line_15_refund_received: float = Field(
        default=0.0,
        description="Refund already received"
    )
    line_16_applied_to_estimated: float = Field(
        default=0.0,
        description="Amount applied to estimated taxes"
    )
    line_17_amount_owed_original: float = Field(
        default=0.0,
        description="Amount owed shown on original return"
    )
    line_18_tax_paid_with_original: float = Field(
        default=0.0,
        description="Tax paid with original return or after"
    )

    # Part III: Explanation of Changes
    amendment_reasons: List[AmendmentReason] = Field(
        default_factory=list,
        description="Reasons for amendment"
    )
    explanation: str = Field(
        default="",
        description="Detailed explanation of changes"
    )

    # Supporting schedules attached
    schedules_attached: List[str] = Field(
        default_factory=list,
        description="List of schedules attached (e.g., Schedule A, C, etc.)"
    )

    def calculate_line_4_taxable_income(self) -> None:
        """Calculate Line 4 (Taxable Income) from components."""
        # Original
        original_taxable = (
            self.line_1_agi.original_amount -
            self.line_2_itemized_or_standard.original_amount -
            self.line_3_qbi_deduction.original_amount
        )
        self.line_4_taxable_income.original_amount = max(0.0, original_taxable)

        # Corrected
        corrected_taxable = (
            self.line_1_agi.corrected_amount -
            self.line_2_itemized_or_standard.corrected_amount -
            self.line_3_qbi_deduction.corrected_amount
        )
        corrected = max(0.0, corrected_taxable)

        # Net change
        self.line_4_taxable_income.net_change = corrected - self.line_4_taxable_income.original_amount

    def calculate_line_7_tax_after_credits(self) -> None:
        """Calculate Line 7 (Tax after nonrefundable credits)."""
        # Original
        original = max(0.0,
            self.line_5_tax.original_amount -
            self.line_6_nonrefundable_credits.original_amount
        )
        self.line_7_tax_after_credits.original_amount = original

        # Corrected
        corrected = max(0.0,
            self.line_5_tax.corrected_amount -
            self.line_6_nonrefundable_credits.corrected_amount
        )

        # Net change
        self.line_7_tax_after_credits.net_change = corrected - original

    def calculate_line_9_total_tax(self) -> None:
        """Calculate Line 9 (Total tax)."""
        # Original
        original = (
            self.line_7_tax_after_credits.original_amount +
            self.line_8_other_taxes.original_amount
        )
        self.line_9_total_tax.original_amount = original

        # Corrected
        corrected = (
            self.line_7_tax_after_credits.corrected_amount +
            self.line_8_other_taxes.corrected_amount
        )

        # Net change
        self.line_9_total_tax.net_change = corrected - original

    def calculate_line_13_total_payments(self) -> None:
        """Calculate Line 13 (Total payments)."""
        # Original
        original = (
            self.line_10_withholding.original_amount +
            self.line_11_estimated_payments.original_amount +
            self.line_12_refundable_credits.original_amount
        )
        self.line_13_total_payments.original_amount = original

        # Corrected
        corrected = (
            self.line_10_withholding.corrected_amount +
            self.line_11_estimated_payments.corrected_amount +
            self.line_12_refundable_credits.corrected_amount
        )

        # Net change
        self.line_13_total_payments.net_change = corrected - original

    def calculate_refund_or_amount_owed(self) -> dict:
        """
        Calculate the refund due or additional amount owed.

        Compares corrected total tax to corrected total payments,
        accounting for any refunds already received or taxes already paid.
        """
        result = {
            # Corrected amounts
            'corrected_total_tax': self.line_9_total_tax.corrected_amount,
            'corrected_total_payments': self.line_13_total_payments.corrected_amount,

            # Original amounts already settled
            'refund_already_received': self.line_15_refund_received,
            'applied_to_estimated': self.line_16_applied_to_estimated,
            'tax_already_paid': self.line_18_tax_paid_with_original,

            # Net position
            'net_tax_change': 0.0,
            'refund_due': 0.0,
            'amount_owed': 0.0,
        }

        # Corrected overpayment/underpayment
        corrected_difference = (
            result['corrected_total_payments'] -
            result['corrected_total_tax']
        )

        # What's already been settled
        already_settled = (
            result['refund_already_received'] +
            result['applied_to_estimated'] -
            result['tax_already_paid']
        )

        # Net position after accounting for prior settlements
        net_position = corrected_difference - already_settled
        result['net_tax_change'] = float(money(net_position))

        if net_position > 0:
            result['refund_due'] = float(money(net_position))
        elif net_position < 0:
            result['amount_owed'] = float(money(abs(net_position)))

        return result

    def calculate_amended_return(self) -> dict:
        """
        Complete Form 1040-X calculation.

        Returns comprehensive breakdown of all changes and final
        refund due or amount owed.
        """
        # Recalculate derived lines
        self.calculate_line_4_taxable_income()
        self.calculate_line_7_tax_after_credits()
        self.calculate_line_9_total_tax()
        self.calculate_line_13_total_payments()

        result = {
            'taxpayer_name': self.taxpayer_name,
            'tax_year': self.tax_year,
            'filing_status_changed': self.filing_status_change.status_changed,

            # Summary of changes
            'agi_change': self.line_1_agi.net_change,
            'deduction_change': self.line_2_itemized_or_standard.net_change,
            'taxable_income_change': self.line_4_taxable_income.net_change,
            'total_tax_change': self.line_9_total_tax.net_change,
            'payments_change': self.line_13_total_payments.net_change,

            # Original amounts
            'original_agi': self.line_1_agi.original_amount,
            'original_taxable_income': self.line_4_taxable_income.original_amount,
            'original_total_tax': self.line_9_total_tax.original_amount,
            'original_total_payments': self.line_13_total_payments.original_amount,

            # Corrected amounts
            'corrected_agi': self.line_1_agi.corrected_amount,
            'corrected_taxable_income': self.line_4_taxable_income.corrected_amount,
            'corrected_total_tax': self.line_9_total_tax.corrected_amount,
            'corrected_total_payments': self.line_13_total_payments.corrected_amount,

            # Final calculation
            'refund_or_owed': {},

            # Explanation
            'amendment_reasons': [r.value for r in self.amendment_reasons],
            'explanation': self.explanation,
        }

        # Calculate refund or amount owed
        result['refund_or_owed'] = self.calculate_refund_or_amount_owed()

        return result

    def get_form_1040x_summary(self) -> dict:
        """Get summary suitable for tracking amendments."""
        calc = self.calculate_amended_return()
        return {
            'tax_year': calc['tax_year'],
            'agi_change': calc['agi_change'],
            'tax_change': calc['total_tax_change'],
            'refund_due': calc['refund_or_owed'].get('refund_due', 0.0),
            'amount_owed': calc['refund_or_owed'].get('amount_owed', 0.0),
        }


def create_amended_return(
    tax_year: int,
    original_agi: float,
    original_tax: float,
    original_payments: float,
    corrected_agi: float,
    corrected_tax: float,
    corrected_payments: float,
    refund_received: float = 0.0,
    tax_paid: float = 0.0,
    original_deductions: float = 0.0,
    corrected_deductions: float = 0.0,
    explanation: str = "",
) -> dict:
    """
    Convenience function to create Form 1040-X calculation.

    Args:
        tax_year: Year being amended
        original_agi: Original AGI from filed return
        original_tax: Original total tax
        original_payments: Original total payments
        corrected_agi: Corrected AGI
        corrected_tax: Corrected total tax
        corrected_payments: Corrected total payments
        refund_received: Refund already received from original
        tax_paid: Additional tax paid with/after original
        original_deductions: Original deductions
        corrected_deductions: Corrected deductions
        explanation: Explanation of changes

    Returns:
        Amended return calculation results
    """
    # Set up all lines properly so recalculation works correctly
    # Line 5 (tax) feeds into line 7, which feeds into line 9
    form = Form1040X(
        tax_year=tax_year,
        line_1_agi=Form1040X_Line(
            line_number="1",
            description="AGI",
            original_amount=original_agi,
            net_change=corrected_agi - original_agi,
        ),
        line_2_itemized_or_standard=Form1040X_Line(
            line_number="2",
            description="Deductions",
            original_amount=original_deductions,
            net_change=corrected_deductions - original_deductions,
        ),
        # Set line 5 (tax before credits) to match total tax for simplicity
        line_5_tax=Form1040X_Line(
            line_number="5",
            description="Tax",
            original_amount=original_tax,
            net_change=corrected_tax - original_tax,
        ),
        # Line 7 will be calculated from line 5 - line 6 (credits=0)
        # Line 9 will be calculated from line 7 + line 8 (other taxes=0)
        line_10_withholding=Form1040X_Line(
            line_number="10",
            description="Withholding",
            original_amount=original_payments,
            net_change=corrected_payments - original_payments,
        ),
        # Line 13 will be calculated from line 10 + 11 + 12
        line_15_refund_received=refund_received,
        line_18_tax_paid_with_original=tax_paid,
        explanation=explanation,
    )

    return form.calculate_amended_return()
