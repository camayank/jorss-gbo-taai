"""
Schedule A (Form 1040) - Itemized Deductions

IRS Form for claiming itemized deductions instead of the standard deduction.
Includes medical expenses, taxes paid, interest paid, charitable contributions,
casualty/theft losses, and other itemized deductions.

Key TCJA Changes (2018+):
- SALT deduction capped at $10,000 ($5,000 MFS)
- Mortgage interest limited to $750,000 acquisition debt (grandfathered at $1M)
- Miscellaneous itemized deductions eliminated (2% AGI floor items)
- Casualty losses limited to federally declared disasters
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MortgageType(str, Enum):
    """Type of mortgage for interest deduction purposes."""
    ACQUISITION = "acquisition"  # To buy, build, or improve home
    HOME_EQUITY = "home_equity"  # Home equity loan/line of credit
    GRANDFATHERED = "grandfathered"  # Pre-12/16/2017 mortgage


class CharitableContributionType(str, Enum):
    """Type of charitable contribution."""
    CASH = "cash"
    PROPERTY = "property"
    APPRECIATED_PROPERTY = "appreciated_property"
    VEHICLE = "vehicle"
    QUALIFIED_CONSERVATION = "qualified_conservation"


class MortgageInterestInfo(BaseModel):
    """Information about mortgage interest paid."""
    lender_name: str = Field(default="", description="Name of mortgage lender")
    lender_ein: str = Field(default="", description="Lender's EIN from Form 1098")
    mortgage_type: MortgageType = Field(
        default=MortgageType.ACQUISITION,
        description="Type of mortgage"
    )
    original_loan_amount: float = Field(default=0.0, ge=0, description="Original loan principal")
    outstanding_balance: float = Field(default=0.0, ge=0, description="Outstanding mortgage balance")
    interest_paid: float = Field(default=0.0, ge=0, description="Interest paid during tax year")
    points_paid: float = Field(default=0.0, ge=0, description="Points paid (if applicable)")
    is_grandfathered: bool = Field(
        default=False,
        description="Mortgage originated before 12/16/2017 (grandfathered at $1M limit)"
    )
    is_qualified_residence: bool = Field(
        default=True,
        description="Secured by qualified residence (main or second home)"
    )


class CharitableContribution(BaseModel):
    """Individual charitable contribution."""
    organization_name: str = Field(description="Name of charitable organization")
    contribution_type: CharitableContributionType = Field(
        default=CharitableContributionType.CASH,
        description="Type of contribution"
    )
    amount: float = Field(ge=0, description="Amount or FMV of contribution")
    date_contributed: str = Field(default="", description="Date of contribution")
    has_written_acknowledgment: bool = Field(
        default=False,
        description="Has written acknowledgment for $250+ contributions"
    )
    is_50_pct_org: bool = Field(
        default=True,
        description="Contribution to 50% limit organization (most common)"
    )
    cost_basis: float = Field(
        default=0.0, ge=0,
        description="Cost basis for property contributions"
    )


class ScheduleA(BaseModel):
    """
    Schedule A (Form 1040) - Itemized Deductions

    Complete model for IRS Schedule A with all line items and calculations.
    Implements TCJA limitations including SALT cap and mortgage interest limits.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Line 1: Medical and Dental Expenses
    medical_expenses_total: float = Field(
        default=0.0, ge=0,
        description="Total medical and dental expenses"
    )
    agi_for_medical: float = Field(
        default=0.0, ge=0,
        description="AGI for calculating 7.5% floor"
    )

    # Lines 5-7: Taxes You Paid
    state_income_tax: float = Field(
        default=0.0, ge=0,
        description="State and local income taxes paid"
    )
    state_sales_tax: float = Field(
        default=0.0, ge=0,
        description="State and local sales taxes (alternative to income tax)"
    )
    real_estate_taxes: float = Field(
        default=0.0, ge=0,
        description="Real estate taxes paid"
    )
    personal_property_taxes: float = Field(
        default=0.0, ge=0,
        description="Personal property taxes paid"
    )
    other_taxes: float = Field(
        default=0.0, ge=0,
        description="Other deductible taxes"
    )
    use_sales_tax: bool = Field(
        default=False,
        description="Elect to deduct sales tax instead of income tax"
    )

    # Lines 8-10: Interest You Paid
    mortgages: List[MortgageInterestInfo] = Field(
        default_factory=list,
        description="Mortgage interest information"
    )
    investment_interest: float = Field(
        default=0.0, ge=0,
        description="Investment interest expense (limited by Form 4952)"
    )

    # Lines 11-14: Gifts to Charity
    charitable_contributions: List[CharitableContribution] = Field(
        default_factory=list,
        description="Charitable contributions"
    )
    carryover_from_prior_year: float = Field(
        default=0.0, ge=0,
        description="Charitable contribution carryover from prior year"
    )

    # Line 15: Casualty and Theft Losses
    casualty_loss_amount: float = Field(
        default=0.0, ge=0,
        description="Casualty/theft loss from federally declared disaster (Form 4684)"
    )

    # Line 16: Other Itemized Deductions
    other_deductions: float = Field(
        default=0.0, ge=0,
        description="Other itemized deductions (gambling losses, etc.)"
    )
    gambling_losses: float = Field(
        default=0.0, ge=0,
        description="Gambling losses (limited to gambling winnings)"
    )
    gambling_winnings: float = Field(
        default=0.0, ge=0,
        description="Gambling winnings (for loss limitation)"
    )

    # Configuration
    filing_status: str = Field(
        default="single",
        description="Filing status for SALT cap determination"
    )
    salt_cap: float = Field(
        default=10000.0,
        description="SALT deduction cap ($10k or $5k MFS)"
    )
    mortgage_limit: float = Field(
        default=750000.0,
        description="Mortgage debt limit for interest deduction"
    )
    grandfathered_mortgage_limit: float = Field(
        default=1000000.0,
        description="Grandfathered mortgage limit (pre-12/16/2017)"
    )

    def calculate_medical_deduction(self) -> Dict[str, float]:
        """
        Calculate deductible medical expenses (Line 1-4).

        Medical expenses are deductible to extent they exceed 7.5% of AGI.
        """
        floor_amount = self.agi_for_medical * 0.075
        deductible = max(0, self.medical_expenses_total - floor_amount)

        return {
            'total_expenses': self.medical_expenses_total,
            'agi': self.agi_for_medical,
            'floor_percentage': 0.075,
            'floor_amount': round(floor_amount, 2),
            'deductible_amount': round(deductible, 2)
        }

    def calculate_taxes_paid_deduction(self) -> Dict[str, float]:
        """
        Calculate deductible taxes paid (Lines 5-7).

        SALT deduction is capped at $10,000 ($5,000 for MFS).
        Taxpayer elects either income tax OR sales tax, not both.
        """
        # Choose income tax or sales tax
        state_local_tax = self.state_sales_tax if self.use_sales_tax else self.state_income_tax

        # Total before cap
        total_salt = (
            state_local_tax +
            self.real_estate_taxes +
            self.personal_property_taxes +
            self.other_taxes
        )

        # Apply SALT cap
        cap = 5000.0 if self.filing_status == "married_separate" else self.salt_cap
        deductible = min(total_salt, cap)

        return {
            'state_local_tax': state_local_tax,
            'real_estate_taxes': self.real_estate_taxes,
            'personal_property_taxes': self.personal_property_taxes,
            'other_taxes': self.other_taxes,
            'total_before_cap': round(total_salt, 2),
            'salt_cap': cap,
            'deductible_amount': round(deductible, 2),
            'amount_over_cap': round(max(0, total_salt - cap), 2)
        }

    def calculate_interest_deduction(self) -> Dict[str, float]:
        """
        Calculate deductible interest paid (Lines 8-10).

        Mortgage interest limited based on debt amount:
        - $750,000 for mortgages after 12/15/2017
        - $1,000,000 for grandfathered mortgages
        """
        total_mortgage_interest = 0.0
        total_points = 0.0
        grandfathered_debt = 0.0
        new_debt = 0.0

        for mortgage in self.mortgages:
            if not mortgage.is_qualified_residence:
                continue

            if mortgage.is_grandfathered or mortgage.mortgage_type == MortgageType.GRANDFATHERED:
                grandfathered_debt += mortgage.outstanding_balance
            else:
                new_debt += mortgage.outstanding_balance

            total_mortgage_interest += mortgage.interest_paid
            total_points += mortgage.points_paid

        # Calculate limitation ratio
        total_debt = grandfathered_debt + new_debt

        if total_debt <= 0:
            deductible_interest = 0.0
            deductible_points = 0.0
        else:
            # Apply limits
            allowed_grandfathered = min(grandfathered_debt, self.grandfathered_mortgage_limit)
            remaining_limit = max(0, self.mortgage_limit - allowed_grandfathered)
            allowed_new = min(new_debt, remaining_limit)
            total_allowed_debt = allowed_grandfathered + allowed_new

            if total_debt > 0:
                ratio = min(1.0, total_allowed_debt / total_debt)
            else:
                ratio = 1.0

            deductible_interest = total_mortgage_interest * ratio
            deductible_points = total_points * ratio

        total_deductible = deductible_interest + deductible_points + self.investment_interest

        return {
            'mortgage_interest': round(total_mortgage_interest, 2),
            'points': round(total_points, 2),
            'investment_interest': self.investment_interest,
            'grandfathered_debt': round(grandfathered_debt, 2),
            'new_debt': round(new_debt, 2),
            'total_debt': round(total_debt, 2),
            'deductible_mortgage_interest': round(deductible_interest, 2),
            'deductible_points': round(deductible_points, 2),
            'total_deductible': round(total_deductible, 2)
        }

    def calculate_charitable_deduction(self) -> Dict[str, float]:
        """
        Calculate deductible charitable contributions (Lines 11-14).

        Limitations:
        - Cash to 50% orgs: 60% of AGI
        - Property to 50% orgs: 50% of AGI
        - Appreciated property: 30% of AGI
        - Contributions to 30% orgs: 30% of AGI
        """
        cash_contributions = 0.0
        property_contributions = 0.0
        appreciated_contributions = 0.0

        for contribution in self.charitable_contributions:
            if contribution.contribution_type == CharitableContributionType.CASH:
                cash_contributions += contribution.amount
            elif contribution.contribution_type == CharitableContributionType.APPRECIATED_PROPERTY:
                appreciated_contributions += contribution.amount
            else:
                property_contributions += contribution.amount

        total_contributions = cash_contributions + property_contributions + appreciated_contributions
        total_with_carryover = total_contributions + self.carryover_from_prior_year

        # Apply AGI limitations (simplified - full calculation is complex)
        # 60% limit for cash, 50% for other property, 30% for appreciated
        max_cash = self.agi_for_medical * 0.60
        max_property = self.agi_for_medical * 0.50
        max_appreciated = self.agi_for_medical * 0.30

        deductible_cash = min(cash_contributions, max_cash)
        deductible_property = min(property_contributions, max_property)
        deductible_appreciated = min(appreciated_contributions, max_appreciated)

        total_deductible = deductible_cash + deductible_property + deductible_appreciated
        total_deductible = min(total_deductible + self.carryover_from_prior_year,
                              self.agi_for_medical * 0.60)  # Overall 60% cap

        carryforward = max(0, total_with_carryover - total_deductible)

        return {
            'cash_contributions': round(cash_contributions, 2),
            'property_contributions': round(property_contributions, 2),
            'appreciated_contributions': round(appreciated_contributions, 2),
            'total_contributions': round(total_contributions, 2),
            'carryover_used': round(min(self.carryover_from_prior_year, total_deductible), 2),
            'deductible_amount': round(total_deductible, 2),
            'new_carryforward': round(carryforward, 2)
        }

    def calculate_other_deductions(self) -> Dict[str, float]:
        """
        Calculate other itemized deductions (Lines 15-16).

        Includes casualty losses (federally declared disasters only)
        and gambling losses (limited to winnings).
        """
        # Gambling losses limited to winnings
        deductible_gambling = min(self.gambling_losses, self.gambling_winnings)

        total_other = self.casualty_loss_amount + deductible_gambling + self.other_deductions

        return {
            'casualty_loss': self.casualty_loss_amount,
            'gambling_losses': self.gambling_losses,
            'gambling_winnings': self.gambling_winnings,
            'deductible_gambling_losses': round(deductible_gambling, 2),
            'other_deductions': self.other_deductions,
            'total_other': round(total_other, 2)
        }

    def calculate_schedule_a(self) -> Dict[str, Any]:
        """
        Calculate complete Schedule A with all line items.

        Returns total itemized deductions and breakdown by category.
        """
        medical = self.calculate_medical_deduction()
        taxes = self.calculate_taxes_paid_deduction()
        interest = self.calculate_interest_deduction()
        charitable = self.calculate_charitable_deduction()
        other = self.calculate_other_deductions()

        total_itemized = (
            medical['deductible_amount'] +
            taxes['deductible_amount'] +
            interest['total_deductible'] +
            charitable['deductible_amount'] +
            other['total_other']
        )

        return {
            'tax_year': self.tax_year,
            'filing_status': self.filing_status,

            # Line items
            'line_1_medical_dental': medical['total_expenses'],
            'line_2_agi': medical['agi'],
            'line_3_agi_times_075': medical['floor_amount'],
            'line_4_medical_deduction': medical['deductible_amount'],

            'line_5a_state_local_tax': taxes['state_local_tax'],
            'line_5b_real_estate_tax': taxes['real_estate_taxes'],
            'line_5c_personal_property_tax': taxes['personal_property_taxes'],
            'line_5d_total_before_cap': taxes['total_before_cap'],
            'line_5e_salt_deduction': taxes['deductible_amount'],

            'line_8a_mortgage_interest': interest['deductible_mortgage_interest'],
            'line_8b_points': interest['deductible_points'],
            'line_9_investment_interest': interest['investment_interest'],
            'line_10_interest_total': interest['total_deductible'],

            'line_11_cash_contributions': charitable['cash_contributions'],
            'line_12_other_contributions': charitable['property_contributions'] + charitable['appreciated_contributions'],
            'line_13_carryover': charitable['carryover_used'],
            'line_14_charitable_total': charitable['deductible_amount'],

            'line_15_casualty_loss': other['casualty_loss'],
            'line_16_other_deductions': other['total_other'],

            'line_17_total_itemized': round(total_itemized, 2),

            # Breakdown summaries
            'medical_breakdown': medical,
            'taxes_breakdown': taxes,
            'interest_breakdown': interest,
            'charitable_breakdown': charitable,
            'other_breakdown': other,

            # Comparison
            'total_itemized_deductions': round(total_itemized, 2),
        }

    def get_schedule_a_summary(self) -> Dict[str, Any]:
        """Get a concise summary of Schedule A."""
        result = self.calculate_schedule_a()
        return {
            'total_itemized': result['total_itemized_deductions'],
            'medical': result['line_4_medical_deduction'],
            'taxes_paid': result['line_5e_salt_deduction'],
            'interest': result['line_10_interest_total'],
            'charitable': result['line_14_charitable_total'],
            'other': result['line_16_other_deductions'],
        }


def create_schedule_a(
    agi: float,
    medical_expenses: float = 0.0,
    state_income_tax: float = 0.0,
    real_estate_taxes: float = 0.0,
    mortgage_interest: float = 0.0,
    mortgage_balance: float = 0.0,
    charitable_cash: float = 0.0,
    charitable_property: float = 0.0,
    filing_status: str = "single",
) -> Dict[str, Any]:
    """
    Convenience function to calculate Schedule A itemized deductions.

    Args:
        agi: Adjusted Gross Income
        medical_expenses: Total medical/dental expenses
        state_income_tax: State and local income taxes paid
        real_estate_taxes: Real estate taxes paid
        mortgage_interest: Home mortgage interest paid
        mortgage_balance: Outstanding mortgage balance
        charitable_cash: Cash charitable contributions
        charitable_property: Property charitable contributions
        filing_status: Filing status for SALT cap

    Returns:
        Dictionary with Schedule A calculation results
    """
    mortgages = []
    if mortgage_interest > 0:
        mortgages.append(MortgageInterestInfo(
            lender_name="Primary Mortgage",
            interest_paid=mortgage_interest,
            outstanding_balance=mortgage_balance,
        ))

    contributions = []
    if charitable_cash > 0:
        contributions.append(CharitableContribution(
            organization_name="Various Charities",
            contribution_type=CharitableContributionType.CASH,
            amount=charitable_cash,
        ))
    if charitable_property > 0:
        contributions.append(CharitableContribution(
            organization_name="Various Charities",
            contribution_type=CharitableContributionType.PROPERTY,
            amount=charitable_property,
        ))

    schedule_a = ScheduleA(
        agi_for_medical=agi,
        medical_expenses_total=medical_expenses,
        state_income_tax=state_income_tax,
        real_estate_taxes=real_estate_taxes,
        mortgages=mortgages,
        charitable_contributions=contributions,
        filing_status=filing_status,
    )

    return schedule_a.calculate_schedule_a()
