"""
Form 1099-INT (Interest Income) and Form 1099-DIV (Dividends and Distributions)

Complete IRS-compliant models for investment income reporting:

Form 1099-INT:
- Box 1: Interest income (taxable)
- Box 2: Early withdrawal penalty
- Box 3: Interest on US Savings Bonds and Treasury obligations
- Box 4: Federal income tax withheld
- Box 5: Investment expenses (IRC 212)
- Box 6: Foreign tax paid
- Box 7: Foreign country or US possession
- Box 8: Tax-exempt interest
- Box 9: Specified private activity bond interest (AMT)
- Box 10: Market discount
- Box 11: Bond premium
- Box 12: Bond premium on Treasury obligations
- Box 13: Bond premium on tax-exempt bonds
- Box 14: Tax-exempt and tax credit bond CUSIP number
- Box 15-17: State tax information

Form 1099-DIV:
- Box 1a: Total ordinary dividends
- Box 1b: Qualified dividends
- Box 2a: Total capital gain distributions
- Box 2b: Unrecaptured Section 1250 gain
- Box 2c: Section 1202 gain
- Box 2d: Collectibles (28%) gain
- Box 2e: Section 897 ordinary dividends
- Box 2f: Section 897 capital gain
- Box 3: Nondividend distributions
- Box 4: Federal income tax withheld
- Box 5: Section 199A dividends
- Box 6: Investment expenses
- Box 7: Foreign tax paid
- Box 8: Foreign country or US possession
- Box 9: Cash liquidation distributions
- Box 10: Noncash liquidation distributions
- Box 11: FATCA filing requirement
- Box 12: Exempt-interest dividends
- Box 13: Specified private activity bond interest dividends (AMT)
- Box 14-16: State tax information

These flow to:
- Schedule B (Interest and Dividends)
- Schedule D (Capital Gains)
- Form 6251 (AMT - private activity bond interest)
- Form 1116 (Foreign Tax Credit)
- Form 8960 (NIIT)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field, field_validator
from datetime import date


class AccountType(str, Enum):
    """Types of accounts that receive 1099-INT/DIV."""
    INDIVIDUAL = "individual"
    JOINT = "joint"
    IRA = "ira"
    ROTH_IRA = "roth_ira"
    TRUST = "trust"
    ESTATE = "estate"
    CORPORATION = "corporation"
    PARTNERSHIP = "partnership"
    OTHER = "other"


class BondType(str, Enum):
    """Types of bonds for interest classification."""
    CORPORATE = "corporate"
    MUNICIPAL = "municipal"  # Tax-exempt
    US_TREASURY = "us_treasury"
    US_SAVINGS_BOND = "us_savings_bond"
    AGENCY = "agency"  # Fannie Mae, Freddie Mac, etc.
    PRIVATE_ACTIVITY = "private_activity"  # AMT preference
    ZERO_COUPON = "zero_coupon"
    CD = "cd"  # Certificate of Deposit
    MONEY_MARKET = "money_market"
    OTHER = "other"


class DividendType(str, Enum):
    """Types of dividend income."""
    ORDINARY = "ordinary"  # Taxed at ordinary income rates
    QUALIFIED = "qualified"  # Taxed at preferential rates
    RETURN_OF_CAPITAL = "return_of_capital"  # Not taxable, reduces basis
    LIQUIDATING = "liquidating"  # Liquidation distribution


class StateInfo(BaseModel):
    """State tax information for multi-state reporting."""
    state_code: str = Field(max_length=2, description="Two-letter state code")
    state_id_number: str = Field(default="", description="Payer's state ID number")
    state_tax_withheld: float = Field(default=0.0, ge=0, description="State tax withheld")


class Form1099INT(BaseModel):
    """
    Form 1099-INT: Interest Income

    Complete model mapping to all IRS Form 1099-INT boxes.
    Used to report interest income from banks, bonds, and other sources.
    """
    # Payer Information
    payer_name: str = Field(description="Name of payer (financial institution)")
    payer_tin: str = Field(default="", description="Payer's TIN (EIN or SSN)")
    payer_address: str = Field(default="", description="Payer's address")
    payer_phone: str = Field(default="", description="Payer's telephone number")

    # Recipient Information
    recipient_name: str = Field(default="", description="Recipient's name")
    recipient_tin: str = Field(default="", description="Recipient's TIN (SSN)")
    recipient_address: str = Field(default="", description="Recipient's address")
    account_number: str = Field(default="", description="Account number")
    account_type: AccountType = Field(
        default=AccountType.INDIVIDUAL,
        description="Type of account"
    )

    # Box 1: Interest income
    box_1_interest_income: float = Field(
        default=0.0, ge=0,
        description="Box 1: Taxable interest income"
    )

    # Box 2: Early withdrawal penalty
    box_2_early_withdrawal_penalty: float = Field(
        default=0.0, ge=0,
        description="Box 2: Early withdrawal penalty (deductible)"
    )

    # Box 3: Interest on US Savings Bonds and Treasury obligations
    box_3_us_savings_bonds_treasury: float = Field(
        default=0.0, ge=0,
        description="Box 3: Interest on US Savings Bonds and Treasury obligations"
    )

    # Box 4: Federal income tax withheld
    box_4_federal_tax_withheld: float = Field(
        default=0.0, ge=0,
        description="Box 4: Federal income tax withheld"
    )

    # Box 5: Investment expenses
    box_5_investment_expenses: float = Field(
        default=0.0, ge=0,
        description="Box 5: Investment expenses (IRC 212 deductions)"
    )

    # Box 6: Foreign tax paid
    box_6_foreign_tax_paid: float = Field(
        default=0.0, ge=0,
        description="Box 6: Foreign tax paid"
    )

    # Box 7: Foreign country or US possession
    box_7_foreign_country: str = Field(
        default="",
        description="Box 7: Foreign country or US possession"
    )

    # Box 8: Tax-exempt interest
    box_8_tax_exempt_interest: float = Field(
        default=0.0, ge=0,
        description="Box 8: Tax-exempt interest (municipal bonds)"
    )

    # Box 9: Specified private activity bond interest
    box_9_private_activity_bond_interest: float = Field(
        default=0.0, ge=0,
        description="Box 9: Specified private activity bond interest (AMT preference)"
    )

    # Box 10: Market discount
    box_10_market_discount: float = Field(
        default=0.0, ge=0,
        description="Box 10: Market discount"
    )

    # Box 11: Bond premium
    box_11_bond_premium: float = Field(
        default=0.0, ge=0,
        description="Box 11: Bond premium (can offset interest)"
    )

    # Box 12: Bond premium on Treasury obligations
    box_12_bond_premium_treasury: float = Field(
        default=0.0, ge=0,
        description="Box 12: Bond premium on Treasury obligations"
    )

    # Box 13: Bond premium on tax-exempt bonds
    box_13_bond_premium_tax_exempt: float = Field(
        default=0.0, ge=0,
        description="Box 13: Bond premium on tax-exempt bonds"
    )

    # Box 14: Tax-exempt and tax credit bond CUSIP
    box_14_cusip: str = Field(
        default="",
        description="Box 14: Tax-exempt and tax credit bond CUSIP number"
    )

    # Boxes 15-17: State information
    state_info: List[StateInfo] = Field(
        default_factory=list,
        description="State tax information (up to 2 states)"
    )

    # Additional tracking
    bond_type: BondType = Field(
        default=BondType.OTHER,
        description="Type of bond generating interest"
    )
    is_oid: bool = Field(
        default=False,
        description="Is Original Issue Discount (OID) bond"
    )
    oid_amount: float = Field(
        default=0.0, ge=0,
        description="OID amount if applicable"
    )
    acquisition_premium: float = Field(
        default=0.0, ge=0,
        description="Acquisition premium for OID bonds"
    )

    @computed_field
    @property
    def total_taxable_interest(self) -> float:
        """
        Total taxable interest income.
        Box 1 + OID - Bond premium adjustments.
        """
        taxable = self.box_1_interest_income + self.oid_amount
        # Bond premium can offset taxable interest
        if self.box_11_bond_premium > 0:
            taxable = max(0, taxable - self.box_11_bond_premium)
        return taxable

    @computed_field
    @property
    def total_tax_exempt_interest(self) -> float:
        """Total tax-exempt interest (Box 8)."""
        return self.box_8_tax_exempt_interest

    @computed_field
    @property
    def amt_preference_interest(self) -> float:
        """
        Interest that is an AMT preference item (Box 9).
        Private activity bond interest is tax-exempt for regular tax
        but taxable for AMT.
        """
        return self.box_9_private_activity_bond_interest

    @computed_field
    @property
    def has_foreign_tax(self) -> bool:
        """Check if foreign tax was paid (eligible for credit or deduction)."""
        return self.box_6_foreign_tax_paid > 0

    @computed_field
    @property
    def schedule_b_interest(self) -> float:
        """Amount to report on Schedule B Part I."""
        return self.box_1_interest_income

    def to_schedule_b_entry(self) -> Dict[str, Any]:
        """Convert to Schedule B interest payer entry."""
        return {
            "payer_name": self.payer_name,
            "payer_ein": self.payer_tin,
            "amount": self.box_1_interest_income,
            "early_withdrawal_penalty": self.box_2_early_withdrawal_penalty,
            "tax_exempt_interest": self.box_8_tax_exempt_interest,
            "us_savings_bond_interest": self.box_3_us_savings_bonds_treasury,
            "foreign_tax_paid": self.box_6_foreign_tax_paid,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "payer_name": self.payer_name,
            "payer_tin": self.payer_tin,
            "box_1_interest_income": self.box_1_interest_income,
            "box_2_early_withdrawal_penalty": self.box_2_early_withdrawal_penalty,
            "box_3_us_savings_bonds_treasury": self.box_3_us_savings_bonds_treasury,
            "box_4_federal_tax_withheld": self.box_4_federal_tax_withheld,
            "box_5_investment_expenses": self.box_5_investment_expenses,
            "box_6_foreign_tax_paid": self.box_6_foreign_tax_paid,
            "box_7_foreign_country": self.box_7_foreign_country,
            "box_8_tax_exempt_interest": self.box_8_tax_exempt_interest,
            "box_9_private_activity_bond_interest": self.box_9_private_activity_bond_interest,
            "box_10_market_discount": self.box_10_market_discount,
            "box_11_bond_premium": self.box_11_bond_premium,
            "total_taxable_interest": self.total_taxable_interest,
            "total_tax_exempt_interest": self.total_tax_exempt_interest,
            "amt_preference_interest": self.amt_preference_interest,
        }


class Form1099DIV(BaseModel):
    """
    Form 1099-DIV: Dividends and Distributions

    Complete model mapping to all IRS Form 1099-DIV boxes.
    Used to report dividend income from stocks, mutual funds, and other investments.
    """
    # Payer Information
    payer_name: str = Field(description="Name of payer (fund/company name)")
    payer_tin: str = Field(default="", description="Payer's TIN (EIN)")
    payer_address: str = Field(default="", description="Payer's address")

    # Recipient Information
    recipient_name: str = Field(default="", description="Recipient's name")
    recipient_tin: str = Field(default="", description="Recipient's TIN (SSN)")
    recipient_address: str = Field(default="", description="Recipient's address")
    account_number: str = Field(default="", description="Account number")
    account_type: AccountType = Field(
        default=AccountType.INDIVIDUAL,
        description="Type of account"
    )

    # Box 1a: Total ordinary dividends
    box_1a_ordinary_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 1a: Total ordinary dividends"
    )

    # Box 1b: Qualified dividends (subset of 1a)
    box_1b_qualified_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 1b: Qualified dividends (taxed at preferential rates)"
    )

    # Box 2a: Total capital gain distributions
    box_2a_capital_gain_distributions: float = Field(
        default=0.0, ge=0,
        description="Box 2a: Total capital gain distributions (long-term)"
    )

    # Box 2b: Unrecaptured Section 1250 gain
    box_2b_unrecaptured_1250_gain: float = Field(
        default=0.0, ge=0,
        description="Box 2b: Unrecaptured Section 1250 gain (25% rate)"
    )

    # Box 2c: Section 1202 gain (QSBS)
    box_2c_section_1202_gain: float = Field(
        default=0.0, ge=0,
        description="Box 2c: Section 1202 gain (QSBS - partially excludable)"
    )

    # Box 2d: Collectibles (28%) gain
    box_2d_collectibles_gain: float = Field(
        default=0.0, ge=0,
        description="Box 2d: Collectibles (28%) gain"
    )

    # Box 2e: Section 897 ordinary dividends (FIRPTA)
    box_2e_section_897_ordinary: float = Field(
        default=0.0, ge=0,
        description="Box 2e: Section 897 ordinary dividends (REIT/US real property)"
    )

    # Box 2f: Section 897 capital gain (FIRPTA)
    box_2f_section_897_capital_gain: float = Field(
        default=0.0, ge=0,
        description="Box 2f: Section 897 capital gain (REIT/US real property)"
    )

    # Box 3: Nondividend distributions
    box_3_nondividend_distributions: float = Field(
        default=0.0, ge=0,
        description="Box 3: Nondividend distributions (return of capital)"
    )

    # Box 4: Federal income tax withheld
    box_4_federal_tax_withheld: float = Field(
        default=0.0, ge=0,
        description="Box 4: Federal income tax withheld"
    )

    # Box 5: Section 199A dividends (QBI from REITs/PTPs)
    box_5_section_199a_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 5: Section 199A dividends (REIT/PTP - 20% deduction eligible)"
    )

    # Box 6: Investment expenses
    box_6_investment_expenses: float = Field(
        default=0.0, ge=0,
        description="Box 6: Investment expenses"
    )

    # Box 7: Foreign tax paid
    box_7_foreign_tax_paid: float = Field(
        default=0.0, ge=0,
        description="Box 7: Foreign tax paid"
    )

    # Box 8: Foreign country or US possession
    box_8_foreign_country: str = Field(
        default="",
        description="Box 8: Foreign country or US possession"
    )

    # Box 9: Cash liquidation distributions
    box_9_cash_liquidation: float = Field(
        default=0.0, ge=0,
        description="Box 9: Cash liquidation distributions"
    )

    # Box 10: Noncash liquidation distributions
    box_10_noncash_liquidation: float = Field(
        default=0.0, ge=0,
        description="Box 10: Noncash liquidation distributions"
    )

    # Box 11: FATCA filing requirement
    box_11_fatca_filing: bool = Field(
        default=False,
        description="Box 11: FATCA filing requirement checkbox"
    )

    # Box 12: Exempt-interest dividends
    box_12_exempt_interest_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 12: Exempt-interest dividends (from municipal bond funds)"
    )

    # Box 13: Specified private activity bond interest dividends
    box_13_pab_interest_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 13: Specified private activity bond interest dividends (AMT)"
    )

    # Boxes 14-16: State information
    state_info: List[StateInfo] = Field(
        default_factory=list,
        description="State tax information (up to 2 states)"
    )

    # Additional tracking fields
    security_description: str = Field(
        default="",
        description="Description of security (fund name, stock symbol)"
    )
    cusip: str = Field(
        default="",
        description="CUSIP number of security"
    )
    is_reit: bool = Field(
        default=False,
        description="Is from a Real Estate Investment Trust (REIT)"
    )
    is_mlp: bool = Field(
        default=False,
        description="Is from a Master Limited Partnership (MLP/PTP)"
    )
    cost_basis: float = Field(
        default=0.0, ge=0,
        description="Cost basis for shares (for return of capital tracking)"
    )

    @field_validator('box_1b_qualified_dividends')
    @classmethod
    def qualified_cannot_exceed_ordinary(cls, v, info):
        """Qualified dividends cannot exceed ordinary dividends."""
        if 'box_1a_ordinary_dividends' in info.data:
            if v > info.data['box_1a_ordinary_dividends']:
                raise ValueError('Qualified dividends cannot exceed ordinary dividends')
        return v

    @computed_field
    @property
    def nonqualified_dividends(self) -> float:
        """
        Nonqualified dividends (taxed at ordinary income rates).
        Box 1a - Box 1b.
        """
        return max(0, self.box_1a_ordinary_dividends - self.box_1b_qualified_dividends)

    @computed_field
    @property
    def total_taxable_dividends(self) -> float:
        """
        Total taxable dividends for Form 1040.
        Ordinary dividends (Box 1a) are fully taxable.
        """
        return self.box_1a_ordinary_dividends

    @computed_field
    @property
    def schedule_d_capital_gains(self) -> float:
        """
        Capital gain distributions for Schedule D.
        Box 2a flows to Schedule D Line 13.
        """
        return self.box_2a_capital_gain_distributions

    @computed_field
    @property
    def qbi_eligible_dividends(self) -> float:
        """
        Dividends eligible for Section 199A QBI deduction.
        Box 5 (REIT/PTP dividends).
        """
        return self.box_5_section_199a_dividends

    @computed_field
    @property
    def amt_preference_amount(self) -> float:
        """
        Amount that is an AMT preference item.
        Private activity bond interest dividends (Box 13).
        """
        return self.box_13_pab_interest_dividends

    @computed_field
    @property
    def total_tax_exempt(self) -> float:
        """Total tax-exempt dividends (Box 12)."""
        return self.box_12_exempt_interest_dividends

    @computed_field
    @property
    def has_foreign_tax(self) -> bool:
        """Check if foreign tax was paid (eligible for credit or deduction)."""
        return self.box_7_foreign_tax_paid > 0

    @computed_field
    @property
    def has_return_of_capital(self) -> bool:
        """Check if there's a return of capital (reduces cost basis)."""
        return self.box_3_nondividend_distributions > 0

    @computed_field
    @property
    def total_liquidation(self) -> float:
        """Total liquidation distributions (cash + noncash)."""
        return self.box_9_cash_liquidation + self.box_10_noncash_liquidation

    def to_schedule_b_entry(self) -> Dict[str, Any]:
        """Convert to Schedule B dividend payer entry."""
        return {
            "payer_name": self.payer_name,
            "payer_ein": self.payer_tin,
            "ordinary_dividends": self.box_1a_ordinary_dividends,
            "qualified_dividends": self.box_1b_qualified_dividends,
            "capital_gain_distributions": self.box_2a_capital_gain_distributions,
            "unrecaptured_1250_gain": self.box_2b_unrecaptured_1250_gain,
            "section_1202_gain": self.box_2c_section_1202_gain,
            "collectibles_28_gain": self.box_2d_collectibles_gain,
            "nondividend_distributions": self.box_3_nondividend_distributions,
            "federal_tax_withheld": self.box_4_federal_tax_withheld,
            "section_199a_dividends": self.box_5_section_199a_dividends,
            "investment_expenses": self.box_6_investment_expenses,
            "foreign_tax_paid": self.box_7_foreign_tax_paid,
            "foreign_country": self.box_8_foreign_country,
            "exempt_interest_dividends": self.box_12_exempt_interest_dividends,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "payer_name": self.payer_name,
            "payer_tin": self.payer_tin,
            "security_description": self.security_description,
            "box_1a_ordinary_dividends": self.box_1a_ordinary_dividends,
            "box_1b_qualified_dividends": self.box_1b_qualified_dividends,
            "box_2a_capital_gain_distributions": self.box_2a_capital_gain_distributions,
            "box_2b_unrecaptured_1250_gain": self.box_2b_unrecaptured_1250_gain,
            "box_2c_section_1202_gain": self.box_2c_section_1202_gain,
            "box_2d_collectibles_gain": self.box_2d_collectibles_gain,
            "box_3_nondividend_distributions": self.box_3_nondividend_distributions,
            "box_4_federal_tax_withheld": self.box_4_federal_tax_withheld,
            "box_5_section_199a_dividends": self.box_5_section_199a_dividends,
            "box_6_investment_expenses": self.box_6_investment_expenses,
            "box_7_foreign_tax_paid": self.box_7_foreign_tax_paid,
            "box_8_foreign_country": self.box_8_foreign_country,
            "box_9_cash_liquidation": self.box_9_cash_liquidation,
            "box_12_exempt_interest_dividends": self.box_12_exempt_interest_dividends,
            "box_13_pab_interest_dividends": self.box_13_pab_interest_dividends,
            "is_reit": self.is_reit,
            "is_mlp": self.is_mlp,
            "nonqualified_dividends": self.nonqualified_dividends,
            "total_taxable_dividends": self.total_taxable_dividends,
            "schedule_d_capital_gains": self.schedule_d_capital_gains,
            "qbi_eligible_dividends": self.qbi_eligible_dividends,
        }


class InvestmentIncomeSummary(BaseModel):
    """
    Aggregated investment income from all 1099-INT and 1099-DIV forms.

    Provides totals for:
    - Schedule B reporting
    - Form 1040 income lines
    - Schedule D capital gains
    - Form 1116 foreign tax credit
    - Form 6251 AMT preferences
    - Form 8960 NIIT calculation
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Source forms
    forms_1099_int: List[Form1099INT] = Field(
        default_factory=list,
        description="All Form 1099-INT documents"
    )
    forms_1099_div: List[Form1099DIV] = Field(
        default_factory=list,
        description="All Form 1099-DIV documents"
    )

    @computed_field
    @property
    def total_taxable_interest(self) -> float:
        """Total taxable interest (Schedule B Part I total)."""
        return sum(f.total_taxable_interest for f in self.forms_1099_int)

    @computed_field
    @property
    def total_tax_exempt_interest(self) -> float:
        """Total tax-exempt interest (Form 1040 Line 2a)."""
        return (
            sum(f.total_tax_exempt_interest for f in self.forms_1099_int) +
            sum(f.total_tax_exempt for f in self.forms_1099_div)
        )

    @computed_field
    @property
    def total_ordinary_dividends(self) -> float:
        """Total ordinary dividends (Schedule B Part II total, Form 1040 Line 3b)."""
        return sum(f.box_1a_ordinary_dividends for f in self.forms_1099_div)

    @computed_field
    @property
    def total_qualified_dividends(self) -> float:
        """Total qualified dividends (Form 1040 Line 3a)."""
        return sum(f.box_1b_qualified_dividends for f in self.forms_1099_div)

    @computed_field
    @property
    def total_capital_gain_distributions(self) -> float:
        """Total capital gain distributions (Schedule D Line 13)."""
        return sum(f.box_2a_capital_gain_distributions for f in self.forms_1099_div)

    @computed_field
    @property
    def total_unrecaptured_1250_gain(self) -> float:
        """Total unrecaptured Section 1250 gain (28% rate portion)."""
        return sum(f.box_2b_unrecaptured_1250_gain for f in self.forms_1099_div)

    @computed_field
    @property
    def total_section_199a_dividends(self) -> float:
        """Total Section 199A dividends (REIT/PTP QBI eligible)."""
        return sum(f.box_5_section_199a_dividends for f in self.forms_1099_div)

    @computed_field
    @property
    def total_nondividend_distributions(self) -> float:
        """Total nondividend distributions (return of capital)."""
        return sum(f.box_3_nondividend_distributions for f in self.forms_1099_div)

    @computed_field
    @property
    def total_federal_withholding(self) -> float:
        """Total federal income tax withheld."""
        return (
            sum(f.box_4_federal_tax_withheld for f in self.forms_1099_int) +
            sum(f.box_4_federal_tax_withheld for f in self.forms_1099_div)
        )

    @computed_field
    @property
    def total_foreign_tax_paid(self) -> float:
        """Total foreign tax paid (for Form 1116 or deduction)."""
        return (
            sum(f.box_6_foreign_tax_paid for f in self.forms_1099_int) +
            sum(f.box_7_foreign_tax_paid for f in self.forms_1099_div)
        )

    @computed_field
    @property
    def total_early_withdrawal_penalty(self) -> float:
        """Total early withdrawal penalties (Schedule 1 adjustment)."""
        return sum(f.box_2_early_withdrawal_penalty for f in self.forms_1099_int)

    @computed_field
    @property
    def total_amt_preference(self) -> float:
        """
        Total AMT preference items.
        Private activity bond interest from both 1099-INT and 1099-DIV.
        """
        return (
            sum(f.amt_preference_interest for f in self.forms_1099_int) +
            sum(f.amt_preference_amount for f in self.forms_1099_div)
        )

    @computed_field
    @property
    def total_investment_income_niit(self) -> float:
        """
        Total investment income for NIIT calculation (Form 8960).
        Includes interest, dividends, and capital gain distributions.
        """
        return (
            self.total_taxable_interest +
            self.total_ordinary_dividends +
            self.total_capital_gain_distributions
        )

    @computed_field
    @property
    def requires_schedule_b(self) -> bool:
        """
        Check if Schedule B is required.
        Required if interest OR dividends exceed $1,500.
        """
        return (
            self.total_taxable_interest > 1500 or
            self.total_ordinary_dividends > 1500
        )

    @computed_field
    @property
    def foreign_tax_credit_eligible(self) -> bool:
        """Check if eligible for foreign tax credit election."""
        return self.total_foreign_tax_paid > 0

    @computed_field
    @property
    def form_1116_required(self) -> bool:
        """
        Check if Form 1116 is required.
        Required if foreign tax > $300 single / $600 MFJ.
        (Simplified: checking if > $300)
        """
        return self.total_foreign_tax_paid > 300

    def get_schedule_b_totals(self) -> Dict[str, float]:
        """Get totals for Schedule B."""
        return {
            "part_i_interest_total": self.total_taxable_interest,
            "part_ii_dividend_total": self.total_ordinary_dividends,
            "qualified_dividends": self.total_qualified_dividends,
        }

    def get_form_1040_amounts(self) -> Dict[str, float]:
        """Get amounts for Form 1040 lines."""
        return {
            "line_2a_tax_exempt_interest": self.total_tax_exempt_interest,
            "line_2b_taxable_interest": self.total_taxable_interest,
            "line_3a_qualified_dividends": self.total_qualified_dividends,
            "line_3b_ordinary_dividends": self.total_ordinary_dividends,
        }

    def get_schedule_d_amounts(self) -> Dict[str, float]:
        """Get amounts for Schedule D."""
        return {
            "line_13_capital_gain_distributions": self.total_capital_gain_distributions,
            "unrecaptured_1250_gain": self.total_unrecaptured_1250_gain,
        }

    def get_foreign_tax_credit_info(self) -> Dict[str, Any]:
        """Get information for foreign tax credit calculation."""
        foreign_sources = []

        for f in self.forms_1099_int:
            if f.has_foreign_tax:
                foreign_sources.append({
                    "payer": f.payer_name,
                    "country": f.box_7_foreign_country,
                    "foreign_tax": f.box_6_foreign_tax_paid,
                    "gross_income": f.box_1_interest_income,
                    "type": "interest"
                })

        for f in self.forms_1099_div:
            if f.has_foreign_tax:
                foreign_sources.append({
                    "payer": f.payer_name,
                    "country": f.box_8_foreign_country,
                    "foreign_tax": f.box_7_foreign_tax_paid,
                    "gross_income": f.box_1a_ordinary_dividends,
                    "type": "dividends"
                })

        return {
            "total_foreign_tax": self.total_foreign_tax_paid,
            "sources": foreign_sources,
            "form_1116_required": self.form_1116_required,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.tax_year,
            "form_count_1099_int": len(self.forms_1099_int),
            "form_count_1099_div": len(self.forms_1099_div),
            "total_taxable_interest": self.total_taxable_interest,
            "total_tax_exempt_interest": self.total_tax_exempt_interest,
            "total_ordinary_dividends": self.total_ordinary_dividends,
            "total_qualified_dividends": self.total_qualified_dividends,
            "total_capital_gain_distributions": self.total_capital_gain_distributions,
            "total_section_199a_dividends": self.total_section_199a_dividends,
            "total_federal_withholding": self.total_federal_withholding,
            "total_foreign_tax_paid": self.total_foreign_tax_paid,
            "total_early_withdrawal_penalty": self.total_early_withdrawal_penalty,
            "total_amt_preference": self.total_amt_preference,
            "total_investment_income_niit": self.total_investment_income_niit,
            "requires_schedule_b": self.requires_schedule_b,
            "form_1116_required": self.form_1116_required,
        }
