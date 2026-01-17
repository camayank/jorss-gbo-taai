"""
Schedule B (Form 1040) - Interest and Ordinary Dividends

IRS Form for reporting:
- Part I: Interest income over $1,500
- Part II: Ordinary dividends over $1,500
- Part III: Foreign accounts and trusts (FBAR/FATCA triggers)

Thresholds:
- Must file Schedule B if interest or dividends exceed $1,500
- Must file if had foreign account with aggregate value > $10,000
- Triggers Form 8938 (FATCA) at higher thresholds
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class InterestType(str, Enum):
    """Type of interest income."""
    TAXABLE = "taxable"  # Fully taxable interest
    TAX_EXEMPT = "tax_exempt"  # Municipal bond interest
    US_SAVINGS_BOND = "us_savings_bond"  # Series EE/I bonds
    SELLER_FINANCED = "seller_financed"  # Seller-financed mortgage
    OID = "oid"  # Original Issue Discount


class DividendType(str, Enum):
    """Type of dividend income."""
    ORDINARY = "ordinary"  # Ordinary dividends (taxed as ordinary income)
    QUALIFIED = "qualified"  # Qualified dividends (preferential rate)
    CAPITAL_GAIN = "capital_gain"  # Capital gain distributions
    NONDIVIDEND = "nondividend"  # Nondividend distributions (return of capital)
    SECTION_199A = "section_199a"  # Section 199A dividends (REIT/PTP)


class InterestPayer(BaseModel):
    """Interest income from a single payer."""
    payer_name: str = Field(description="Name of interest payer (bank, etc.)")
    payer_ein: str = Field(default="", description="Payer's EIN from Form 1099-INT")
    interest_type: InterestType = Field(
        default=InterestType.TAXABLE,
        description="Type of interest"
    )
    amount: float = Field(ge=0, description="Interest amount received")
    early_withdrawal_penalty: float = Field(
        default=0.0, ge=0,
        description="Early withdrawal penalty (deductible)"
    )
    tax_exempt_interest: float = Field(
        default=0.0, ge=0,
        description="Tax-exempt interest (informational)"
    )
    us_savings_bond_interest: float = Field(
        default=0.0, ge=0,
        description="US savings bond interest"
    )
    foreign_tax_paid: float = Field(
        default=0.0, ge=0,
        description="Foreign tax paid on interest"
    )


class DividendPayer(BaseModel):
    """Dividend income from a single payer."""
    payer_name: str = Field(description="Name of dividend payer")
    payer_ein: str = Field(default="", description="Payer's EIN from Form 1099-DIV")
    ordinary_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 1a: Total ordinary dividends"
    )
    qualified_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 1b: Qualified dividends (subset of ordinary)"
    )
    capital_gain_distributions: float = Field(
        default=0.0, ge=0,
        description="Box 2a: Total capital gain distributions"
    )
    unrecaptured_1250_gain: float = Field(
        default=0.0, ge=0,
        description="Box 2b: Unrecaptured Section 1250 gain"
    )
    section_1202_gain: float = Field(
        default=0.0, ge=0,
        description="Box 2c: Section 1202 gain"
    )
    collectibles_28_gain: float = Field(
        default=0.0, ge=0,
        description="Box 2d: Collectibles (28%) gain"
    )
    nondividend_distributions: float = Field(
        default=0.0, ge=0,
        description="Box 3: Nondividend distributions"
    )
    federal_tax_withheld: float = Field(
        default=0.0, ge=0,
        description="Box 4: Federal income tax withheld"
    )
    section_199a_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 5: Section 199A dividends"
    )
    investment_expenses: float = Field(
        default=0.0, ge=0,
        description="Box 6: Investment expenses"
    )
    foreign_tax_paid: float = Field(
        default=0.0, ge=0,
        description="Box 7: Foreign tax paid"
    )
    foreign_country: str = Field(
        default="",
        description="Box 8: Foreign country or US possession"
    )
    exempt_interest_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 12: Exempt-interest dividends"
    )


class ForeignAccount(BaseModel):
    """Foreign financial account information."""
    country: str = Field(description="Country where account is located")
    account_type: str = Field(default="bank", description="Type of account")
    maximum_value: float = Field(
        ge=0,
        description="Maximum value during year (USD)"
    )
    institution_name: str = Field(default="", description="Name of financial institution")


class ScheduleB(BaseModel):
    """
    Schedule B (Form 1040) - Interest and Ordinary Dividends

    Complete model for IRS Schedule B with Parts I, II, and III.
    Tracks interest payers, dividend payers, and foreign account reporting.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Part I: Interest
    interest_payers: List[InterestPayer] = Field(
        default_factory=list,
        description="List of interest payers"
    )
    nominee_interest: float = Field(
        default=0.0, ge=0,
        description="Interest received as nominee (excluded)"
    )
    accrued_interest_adjustment: float = Field(
        default=0.0, ge=0,
        description="Accrued interest on bonds purchased between interest dates"
    )
    oid_adjustment: float = Field(
        default=0.0,
        description="OID adjustment (can be negative)"
    )
    us_savings_bond_exclusion: float = Field(
        default=0.0, ge=0,
        description="US savings bond interest excluded for education"
    )

    # Part II: Dividends
    dividend_payers: List[DividendPayer] = Field(
        default_factory=list,
        description="List of dividend payers"
    )
    nominee_dividends: float = Field(
        default=0.0, ge=0,
        description="Dividends received as nominee (excluded)"
    )

    # Part III: Foreign Accounts and Trusts
    has_foreign_accounts: bool = Field(
        default=False,
        description="Had financial interest in or signature authority over foreign account"
    )
    foreign_accounts: List[ForeignAccount] = Field(
        default_factory=list,
        description="List of foreign accounts"
    )
    received_foreign_trust_distribution: bool = Field(
        default=False,
        description="Received distribution from or was grantor of foreign trust"
    )

    # Filing threshold
    FILING_THRESHOLD: float = 1500.0  # Must file if interest or dividends > $1,500
    FBAR_THRESHOLD: float = 10000.0  # Must file FBAR if foreign accounts > $10,000

    def calculate_part_i_interest(self) -> Dict[str, Any]:
        """
        Calculate Part I - Interest income.

        Returns breakdown of taxable and tax-exempt interest.
        """
        total_taxable = 0.0
        total_tax_exempt = 0.0
        total_us_bonds = 0.0
        total_early_withdrawal = 0.0
        total_foreign_tax = 0.0

        payer_details = []
        for payer in self.interest_payers:
            if payer.interest_type == InterestType.TAX_EXEMPT:
                total_tax_exempt += payer.amount
            else:
                total_taxable += payer.amount

            total_tax_exempt += payer.tax_exempt_interest
            total_us_bonds += payer.us_savings_bond_interest
            total_early_withdrawal += payer.early_withdrawal_penalty
            total_foreign_tax += payer.foreign_tax_paid

            payer_details.append({
                'name': payer.payer_name,
                'amount': payer.amount,
                'type': payer.interest_type.value,
            })

        # Adjustments
        adjusted_taxable = (
            total_taxable -
            self.nominee_interest -
            self.accrued_interest_adjustment +
            self.oid_adjustment -
            self.us_savings_bond_exclusion
        )

        return {
            'payer_count': len(self.interest_payers),
            'payers': payer_details,
            'line_1_total_interest': round(total_taxable, 2),
            'line_2_nominee_interest': self.nominee_interest,
            'line_3_subtotal': round(total_taxable - self.nominee_interest, 2),
            'line_4_us_bond_exclusion': self.us_savings_bond_exclusion,
            'taxable_interest': round(max(0, adjusted_taxable), 2),
            'tax_exempt_interest': round(total_tax_exempt, 2),
            'us_savings_bond_interest': round(total_us_bonds, 2),
            'early_withdrawal_penalty': round(total_early_withdrawal, 2),
            'foreign_tax_paid': round(total_foreign_tax, 2),
            'requires_schedule_b': total_taxable > self.FILING_THRESHOLD,
        }

    def calculate_part_ii_dividends(self) -> Dict[str, Any]:
        """
        Calculate Part II - Ordinary Dividends.

        Returns breakdown of ordinary, qualified, and capital gain dividends.
        """
        total_ordinary = 0.0
        total_qualified = 0.0
        total_capital_gain = 0.0
        total_section_199a = 0.0
        total_foreign_tax = 0.0
        total_withheld = 0.0
        total_exempt = 0.0

        payer_details = []
        for payer in self.dividend_payers:
            total_ordinary += payer.ordinary_dividends
            total_qualified += payer.qualified_dividends
            total_capital_gain += payer.capital_gain_distributions
            total_section_199a += payer.section_199a_dividends
            total_foreign_tax += payer.foreign_tax_paid
            total_withheld += payer.federal_tax_withheld
            total_exempt += payer.exempt_interest_dividends

            payer_details.append({
                'name': payer.payer_name,
                'ordinary': payer.ordinary_dividends,
                'qualified': payer.qualified_dividends,
            })

        # Adjustments
        adjusted_ordinary = total_ordinary - self.nominee_dividends

        return {
            'payer_count': len(self.dividend_payers),
            'payers': payer_details,
            'line_5_total_ordinary': round(total_ordinary, 2),
            'line_6_nominee_dividends': self.nominee_dividends,
            'ordinary_dividends': round(max(0, adjusted_ordinary), 2),
            'qualified_dividends': round(total_qualified, 2),
            'capital_gain_distributions': round(total_capital_gain, 2),
            'section_199a_dividends': round(total_section_199a, 2),
            'exempt_interest_dividends': round(total_exempt, 2),
            'foreign_tax_paid': round(total_foreign_tax, 2),
            'federal_tax_withheld': round(total_withheld, 2),
            'requires_schedule_b': total_ordinary > self.FILING_THRESHOLD,
        }

    def calculate_part_iii_foreign(self) -> Dict[str, Any]:
        """
        Calculate Part III - Foreign Accounts and Trusts.

        Determines FBAR and Form 8938 filing requirements.
        """
        total_foreign_value = sum(
            account.maximum_value for account in self.foreign_accounts
        )

        requires_fbar = total_foreign_value > self.FBAR_THRESHOLD

        countries = sorted(set(
            account.country for account in self.foreign_accounts
        ))  # Deterministic order

        return {
            'has_foreign_accounts': self.has_foreign_accounts or len(self.foreign_accounts) > 0,
            'account_count': len(self.foreign_accounts),
            'countries': countries,
            'total_maximum_value': round(total_foreign_value, 2),
            'requires_fbar': requires_fbar,
            'fbar_threshold': self.FBAR_THRESHOLD,
            'received_foreign_trust': self.received_foreign_trust_distribution,
            'line_7a_answer': 'Yes' if (self.has_foreign_accounts or len(self.foreign_accounts) > 0) else 'No',
            'line_7b_countries': ', '.join(countries) if countries else 'N/A',
            'line_8_answer': 'Yes' if self.received_foreign_trust_distribution else 'No',
        }

    def calculate_schedule_b(self) -> Dict[str, Any]:
        """
        Calculate complete Schedule B with all parts.

        Returns comprehensive breakdown for Form 1040 lines 2b, 3b.
        """
        part_i = self.calculate_part_i_interest()
        part_ii = self.calculate_part_ii_dividends()
        part_iii = self.calculate_part_iii_foreign()

        requires_filing = (
            part_i['requires_schedule_b'] or
            part_ii['requires_schedule_b'] or
            part_iii['has_foreign_accounts']
        )

        return {
            'tax_year': self.tax_year,

            # Form 1040 lines
            'form_1040_line_2b_taxable_interest': part_i['taxable_interest'],
            'form_1040_line_2a_tax_exempt_interest': part_i['tax_exempt_interest'],
            'form_1040_line_3b_ordinary_dividends': part_ii['ordinary_dividends'],
            'form_1040_line_3a_qualified_dividends': part_ii['qualified_dividends'],

            # Additional amounts
            'capital_gain_distributions': part_ii['capital_gain_distributions'],
            'section_199a_dividends': part_ii['section_199a_dividends'],
            'early_withdrawal_penalty': part_i['early_withdrawal_penalty'],
            'total_foreign_tax_paid': part_i['foreign_tax_paid'] + part_ii['foreign_tax_paid'],
            'total_federal_withheld': part_ii['federal_tax_withheld'],

            # Filing requirements
            'schedule_b_required': requires_filing,
            'fbar_required': part_iii['requires_fbar'],

            # Part breakdowns
            'part_i_interest': part_i,
            'part_ii_dividends': part_ii,
            'part_iii_foreign': part_iii,
        }

    def get_schedule_b_summary(self) -> Dict[str, float]:
        """Get a concise summary of Schedule B totals."""
        result = self.calculate_schedule_b()
        return {
            'taxable_interest': result['form_1040_line_2b_taxable_interest'],
            'tax_exempt_interest': result['form_1040_line_2a_tax_exempt_interest'],
            'ordinary_dividends': result['form_1040_line_3b_ordinary_dividends'],
            'qualified_dividends': result['form_1040_line_3a_qualified_dividends'],
            'capital_gain_distributions': result['capital_gain_distributions'],
        }


def create_schedule_b(
    interest_income: float = 0.0,
    tax_exempt_interest: float = 0.0,
    ordinary_dividends: float = 0.0,
    qualified_dividends: float = 0.0,
    capital_gain_distributions: float = 0.0,
    has_foreign_accounts: bool = False,
    foreign_account_value: float = 0.0,
    foreign_country: str = "",
) -> Dict[str, Any]:
    """
    Convenience function to create and calculate Schedule B.

    Args:
        interest_income: Total taxable interest
        tax_exempt_interest: Tax-exempt interest (municipal bonds)
        ordinary_dividends: Total ordinary dividends
        qualified_dividends: Qualified dividends (subset of ordinary)
        capital_gain_distributions: Capital gain distributions
        has_foreign_accounts: Whether taxpayer has foreign accounts
        foreign_account_value: Maximum value of foreign accounts
        foreign_country: Country of foreign account

    Returns:
        Dictionary with Schedule B calculation results
    """
    interest_payers = []
    if interest_income > 0:
        interest_payers.append(InterestPayer(
            payer_name="Various Financial Institutions",
            amount=interest_income,
            tax_exempt_interest=tax_exempt_interest,
        ))

    dividend_payers = []
    if ordinary_dividends > 0:
        dividend_payers.append(DividendPayer(
            payer_name="Various Investments",
            ordinary_dividends=ordinary_dividends,
            qualified_dividends=qualified_dividends,
            capital_gain_distributions=capital_gain_distributions,
        ))

    foreign_accounts = []
    if has_foreign_accounts and foreign_account_value > 0:
        foreign_accounts.append(ForeignAccount(
            country=foreign_country or "Unknown",
            maximum_value=foreign_account_value,
        ))

    schedule_b = ScheduleB(
        interest_payers=interest_payers,
        dividend_payers=dividend_payers,
        has_foreign_accounts=has_foreign_accounts,
        foreign_accounts=foreign_accounts,
    )

    return schedule_b.calculate_schedule_b()
