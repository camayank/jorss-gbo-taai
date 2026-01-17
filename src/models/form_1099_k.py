"""
Form 1099-K - Payment Card and Third Party Network Transactions

Complete IRS Form 1099-K implementation for reporting payments received through:
- Payment card transactions (credit/debit cards)
- Third party network transactions (PayPal, Venmo, eBay, Etsy, etc.)

Key threshold changes:
- Pre-2022: $20,000 AND 200+ transactions
- 2022-2023: Transitional period
- 2024+: $600 threshold (any number of transactions)

Important: Gross amounts reported may include:
- Fees retained by PSE (not net to seller)
- Refunds/returns already processed
- Amounts that aren't taxable income

This form is crucial for:
- E-commerce sellers
- Gig economy workers (Uber, Lyft, DoorDash)
- Freelancers accepting card payments
- Anyone using payment platforms
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field, field_validator
from datetime import date


class TransactionType(str, Enum):
    """Type of transactions reported on 1099-K."""
    PAYMENT_CARD = "payment_card"  # Credit/debit card transactions
    THIRD_PARTY_NETWORK = "third_party_network"  # PayPal, Venmo, etc.


class PayerType(str, Enum):
    """Type of Payment Settlement Entity (PSE)."""
    MERCHANT_ACQUIRER = "merchant_acquirer"  # Card processor
    THIRD_PARTY_PSE = "third_party_pse"  # PayPal, Stripe, Square
    ELECTRONIC_PAYMENT_FACILITATOR = "epf"  # E-commerce platforms


class Form1099K(BaseModel):
    """
    Form 1099-K - Payment Card and Third Party Network Transactions

    Reports gross payment card and third party network transactions.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Payer (PSE) Information
    payer_name: str = Field(default="", description="Name of PSE")
    payer_tin: str = Field(default="", description="PSE TIN/EIN")
    payer_type: PayerType = Field(
        default=PayerType.THIRD_PARTY_PSE,
        description="Type of Payment Settlement Entity"
    )

    # Payee (Recipient) Information
    payee_name: str = Field(default="", description="Recipient name")
    payee_tin: str = Field(default="", description="Recipient TIN/SSN")
    account_number: str = Field(default="", description="PSE account number")

    # Transaction Type
    transaction_type: TransactionType = Field(
        default=TransactionType.THIRD_PARTY_NETWORK,
        description="Type of transactions"
    )

    # Box 1a: Gross amount of payment card/third party network transactions
    box_1a_gross_amount: float = Field(
        default=0.0, ge=0,
        description="Box 1a: Gross amount of all transactions"
    )

    # Box 1b: Card Not Present transactions (online/phone/mail)
    box_1b_card_not_present: float = Field(
        default=0.0, ge=0,
        description="Box 1b: Card not present transactions"
    )

    # Box 2: Merchant category code (MCC)
    box_2_merchant_category_code: str = Field(
        default="",
        description="Box 2: Merchant category code"
    )

    # Box 3: Number of payment transactions
    box_3_transaction_count: int = Field(
        default=0, ge=0,
        description="Box 3: Number of transactions"
    )

    # Box 4: Federal income tax withheld (backup withholding)
    box_4_federal_tax_withheld: float = Field(
        default=0.0, ge=0,
        description="Box 4: Federal income tax withheld"
    )

    # Box 5a-5l: Gross amount by month
    box_5a_january: float = Field(default=0.0, ge=0, description="January gross")
    box_5b_february: float = Field(default=0.0, ge=0, description="February gross")
    box_5c_march: float = Field(default=0.0, ge=0, description="March gross")
    box_5d_april: float = Field(default=0.0, ge=0, description="April gross")
    box_5e_may: float = Field(default=0.0, ge=0, description="May gross")
    box_5f_june: float = Field(default=0.0, ge=0, description="June gross")
    box_5g_july: float = Field(default=0.0, ge=0, description="July gross")
    box_5h_august: float = Field(default=0.0, ge=0, description="August gross")
    box_5i_september: float = Field(default=0.0, ge=0, description="September gross")
    box_5j_october: float = Field(default=0.0, ge=0, description="October gross")
    box_5k_november: float = Field(default=0.0, ge=0, description="November gross")
    box_5l_december: float = Field(default=0.0, ge=0, description="December gross")

    # Box 6: State information
    box_6_state: str = Field(default="", description="Box 6: State")
    box_6_state_id: str = Field(default="", description="State ID number")
    box_6_state_tax_withheld: float = Field(
        default=0.0, ge=0,
        description="Box 6: State income tax withheld"
    )

    @computed_field
    @property
    def monthly_gross_total(self) -> float:
        """Sum of all monthly amounts (should equal Box 1a)."""
        return (
            self.box_5a_january + self.box_5b_february + self.box_5c_march +
            self.box_5d_april + self.box_5e_may + self.box_5f_june +
            self.box_5g_july + self.box_5h_august + self.box_5i_september +
            self.box_5j_october + self.box_5k_november + self.box_5l_december
        )

    @computed_field
    @property
    def monthly_amounts(self) -> Dict[str, float]:
        """Monthly breakdown of gross amounts."""
        return {
            "january": self.box_5a_january,
            "february": self.box_5b_february,
            "march": self.box_5c_march,
            "april": self.box_5d_april,
            "may": self.box_5e_may,
            "june": self.box_5f_june,
            "july": self.box_5g_july,
            "august": self.box_5h_august,
            "september": self.box_5i_september,
            "october": self.box_5j_october,
            "november": self.box_5k_november,
            "december": self.box_5l_december,
        }

    @computed_field
    @property
    def average_monthly_gross(self) -> float:
        """Average monthly gross amount."""
        active_months = sum(1 for v in self.monthly_amounts.values() if v > 0)
        if active_months == 0:
            return 0.0
        return round(self.box_1a_gross_amount / active_months, 2)

    @computed_field
    @property
    def average_transaction_amount(self) -> float:
        """Average amount per transaction."""
        if self.box_3_transaction_count == 0:
            return 0.0
        return round(self.box_1a_gross_amount / self.box_3_transaction_count, 2)

    @computed_field
    @property
    def card_present_transactions(self) -> float:
        """Card present (in-person) transactions."""
        return self.box_1a_gross_amount - self.box_1b_card_not_present

    @computed_field
    @property
    def card_present_percentage(self) -> float:
        """Percentage of in-person transactions."""
        if self.box_1a_gross_amount == 0:
            return 0.0
        return round((self.card_present_transactions / self.box_1a_gross_amount) * 100, 2)


class Form1099KAdjustments(BaseModel):
    """
    Adjustments to convert 1099-K gross amount to taxable income.

    The 1099-K reports GROSS amounts which often differ from taxable income.
    """
    # The 1099-K gross amount
    gross_1099k_amount: float = Field(
        default=0.0, ge=0,
        description="Gross amount from 1099-K"
    )

    # Refunds and returns (subtract)
    refunds_and_returns: float = Field(
        default=0.0, ge=0,
        description="Refunds issued to customers"
    )

    # Chargebacks (subtract)
    chargebacks: float = Field(
        default=0.0, ge=0,
        description="Chargebacks deducted"
    )

    # Processing fees (already deducted in net deposit but gross on 1099-K)
    processing_fees: float = Field(
        default=0.0, ge=0,
        description="Payment processing fees"
    )

    # Platform fees (eBay, Etsy, Amazon seller fees)
    platform_fees: float = Field(
        default=0.0, ge=0,
        description="Platform/marketplace fees"
    )

    # Non-taxable amounts (personal payments, reimbursements)
    non_taxable_amounts: float = Field(
        default=0.0, ge=0,
        description="Non-taxable amounts included in gross"
    )

    # Sales tax collected (pass-through, not income)
    sales_tax_collected: float = Field(
        default=0.0, ge=0,
        description="Sales tax collected and remitted"
    )

    # Tips reported separately
    tips_already_reported: float = Field(
        default=0.0, ge=0,
        description="Tips already reported on W-2 or other forms"
    )

    # Cost of goods sold (for product sellers)
    cost_of_goods_sold: float = Field(
        default=0.0, ge=0,
        description="COGS for product sales"
    )

    # Other deductible business expenses
    other_deductible_expenses: float = Field(
        default=0.0, ge=0,
        description="Other business expenses"
    )

    @computed_field
    @property
    def total_adjustments(self) -> float:
        """Total adjustments to gross amount."""
        return (
            self.refunds_and_returns +
            self.chargebacks +
            self.processing_fees +
            self.platform_fees +
            self.non_taxable_amounts +
            self.sales_tax_collected +
            self.tips_already_reported
        )

    @computed_field
    @property
    def adjusted_gross_receipts(self) -> float:
        """Adjusted gross receipts (before COGS)."""
        return max(0, self.gross_1099k_amount - self.total_adjustments)

    @computed_field
    @property
    def net_profit_before_expenses(self) -> float:
        """Net profit before other business expenses."""
        return max(0, self.adjusted_gross_receipts - self.cost_of_goods_sold)

    @computed_field
    @property
    def net_taxable_income(self) -> float:
        """Final net taxable income after all adjustments."""
        return max(0, self.net_profit_before_expenses - self.other_deductible_expenses)


class Form1099KSummary(BaseModel):
    """
    Summary of all 1099-K forms received in a tax year.

    Aggregates multiple 1099-Ks from different payment processors.
    """
    tax_year: int = Field(default=2025, description="Tax year")
    forms: List[Form1099K] = Field(
        default_factory=list,
        description="All 1099-K forms received"
    )
    adjustments: Form1099KAdjustments = Field(
        default_factory=Form1099KAdjustments,
        description="Adjustments to arrive at taxable income"
    )

    @computed_field
    @property
    def total_gross_receipts(self) -> float:
        """Total gross receipts from all 1099-Ks."""
        return sum(f.box_1a_gross_amount for f in self.forms)

    @computed_field
    @property
    def total_federal_tax_withheld(self) -> float:
        """Total federal backup withholding."""
        return sum(f.box_4_federal_tax_withheld for f in self.forms)

    @computed_field
    @property
    def total_state_tax_withheld(self) -> float:
        """Total state tax withheld."""
        return sum(f.box_6_state_tax_withheld for f in self.forms)

    @computed_field
    @property
    def total_transactions(self) -> int:
        """Total number of transactions."""
        return sum(f.box_3_transaction_count for f in self.forms)

    @computed_field
    @property
    def number_of_forms(self) -> int:
        """Number of 1099-K forms received."""
        return len(self.forms)

    def add_form(self, form: Form1099K) -> None:
        """Add a 1099-K form to the summary."""
        self.forms.append(form)
        # Update adjustments with new gross amount
        if self.adjustments.gross_1099k_amount == 0:
            self.adjustments = Form1099KAdjustments(
                gross_1099k_amount=self.total_gross_receipts
            )
        else:
            self.adjustments = Form1099KAdjustments(
                **{
                    **self.adjustments.model_dump(
                        exclude={'gross_1099k_amount'}
                    ),
                    'gross_1099k_amount': self.total_gross_receipts
                }
            )

    def by_payer_type(self) -> Dict[str, float]:
        """Group gross amounts by payer type."""
        result = {}
        for form in self.forms:
            payer_type = form.payer_type.value
            result[payer_type] = result.get(payer_type, 0) + form.box_1a_gross_amount
        return result

    def to_schedule_c(self) -> Dict[str, float]:
        """Get amounts for Schedule C reporting."""
        # Start with adjusted gross, not raw 1099-K totals
        self.adjustments = Form1099KAdjustments(
            **{
                **self.adjustments.model_dump(
                    exclude={'gross_1099k_amount'}
                ),
                'gross_1099k_amount': self.total_gross_receipts
            }
        )

        return {
            "line_1_gross_receipts": self.adjustments.adjusted_gross_receipts,
            "line_2_returns_allowances": self.adjustments.refunds_and_returns,
            "line_4_cogs": self.adjustments.cost_of_goods_sold,
            "line_1099k_gross": self.total_gross_receipts,
            "reconciliation_adjustment": self.adjustments.total_adjustments,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.tax_year,
            "form_count": self.number_of_forms,
            "total_gross_receipts": self.total_gross_receipts,
            "total_transactions": self.total_transactions,
            "total_federal_withheld": self.total_federal_tax_withheld,
            "total_state_withheld": self.total_state_tax_withheld,
            "by_payer_type": self.by_payer_type(),
            "adjustments": {
                "total_adjustments": self.adjustments.total_adjustments,
                "adjusted_gross": self.adjustments.adjusted_gross_receipts,
                "net_taxable": self.adjustments.net_taxable_income,
            },
            "forms": [
                {
                    "payer": f.payer_name,
                    "gross_amount": f.box_1a_gross_amount,
                    "transactions": f.box_3_transaction_count,
                }
                for f in self.forms
            ]
        }


def calculate_1099k_taxable_income(
    gross_1099k: float,
    refunds: float = 0.0,
    processing_fees: float = 0.0,
    platform_fees: float = 0.0,
    sales_tax: float = 0.0,
    cogs: float = 0.0,
    other_expenses: float = 0.0,
) -> Dict[str, Any]:
    """
    Convenience function to calculate taxable income from 1099-K.

    Args:
        gross_1099k: Gross amount reported on 1099-K(s)
        refunds: Refunds/returns issued
        processing_fees: Payment processing fees
        platform_fees: Marketplace/platform fees
        sales_tax: Sales tax collected and remitted
        cogs: Cost of goods sold
        other_expenses: Other deductible business expenses

    Returns:
        Dictionary with breakdown and taxable income
    """
    adjustments = Form1099KAdjustments(
        gross_1099k_amount=gross_1099k,
        refunds_and_returns=refunds,
        processing_fees=processing_fees,
        platform_fees=platform_fees,
        sales_tax_collected=sales_tax,
        cost_of_goods_sold=cogs,
        other_deductible_expenses=other_expenses,
    )

    return {
        "gross_1099k": gross_1099k,
        "total_adjustments": adjustments.total_adjustments,
        "adjusted_gross_receipts": adjustments.adjusted_gross_receipts,
        "gross_profit": adjustments.net_profit_before_expenses,
        "net_taxable_income": adjustments.net_taxable_income,
        "effective_rate": round(
            adjustments.net_taxable_income / gross_1099k * 100, 2
        ) if gross_1099k > 0 else 0,
    }


def reconcile_1099k_to_deposits(
    gross_1099k: float,
    actual_deposits: float,
    refunds: float = 0.0,
    processing_fees: float = 0.0,
    platform_fees: float = 0.0,
    chargebacks: float = 0.0,
) -> Dict[str, Any]:
    """
    Reconcile 1099-K gross amount to actual bank deposits.

    Useful for verifying 1099-K accuracy and identifying discrepancies.

    Args:
        gross_1099k: Amount reported on 1099-K
        actual_deposits: Actual amount deposited to bank
        refunds: Refunds issued
        processing_fees: Fees deducted before deposit
        platform_fees: Platform fees deducted
        chargebacks: Chargebacks deducted

    Returns:
        Dictionary with reconciliation analysis
    """
    expected_deposit = (
        gross_1099k -
        refunds -
        processing_fees -
        platform_fees -
        chargebacks
    )

    difference = actual_deposits - expected_deposit
    matches = abs(difference) < 1.00  # Within $1 tolerance

    return {
        "gross_1099k": gross_1099k,
        "expected_deposit": expected_deposit,
        "actual_deposit": actual_deposits,
        "difference": difference,
        "reconciles": matches,
        "breakdown": {
            "refunds": refunds,
            "processing_fees": processing_fees,
            "platform_fees": platform_fees,
            "chargebacks": chargebacks,
        },
        "action_needed": None if matches else (
            "Review 1099-K for accuracy" if difference > 0 else
            "Identify missing deductions"
        ),
    }
