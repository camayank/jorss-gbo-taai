"""
Form 4952 - Investment Interest Expense Deduction

Implements the investment interest expense deduction limitation per
IRC Section 163(d). Investment interest is interest paid on money borrowed
to purchase or carry investment property.

Who Must File Form 4952:
1. Claiming deduction for investment interest expense
2. Have disallowed investment interest from prior year
3. Making election to treat qualified dividends/capital gains as investment income

Investment Interest Includes:
- Margin interest on brokerage accounts
- Interest on loans to buy investment property
- Interest on loans secured by investment property (other than home equity)

Investment Interest Does NOT Include:
- Home mortgage interest (Schedule A)
- Passive activity interest (Form 8582)
- Interest on tax-exempt securities
- Personal interest

Investment Income:
- Interest income
- Ordinary dividends (not qualified)
- Annuity/royalty income from investment property
- Short-term capital gains
- Long-term gains/qualified dividends ONLY if elect to forego lower rates

Key Rule: Investment interest deduction is LIMITED to net investment income.
Excess is carried forward to future years.

Per IRS Form 4952 Instructions, Publication 550, and IRC Section 163(d).
"""

from typing import Optional, List, Dict, Any, ClassVar
from pydantic import BaseModel, Field
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class InvestmentIncomeElection(BaseModel):
    """
    Election to treat capital gains/qualified dividends as investment income.

    Taxpayer can elect to include net long-term capital gains and/or
    qualified dividends as investment income, but then they're taxed at
    ordinary rates instead of preferential rates.
    """
    elect_capital_gains: bool = Field(
        default=False,
        description="Elect to treat net LTCG as investment income"
    )
    capital_gains_amount: float = Field(
        default=0.0,
        ge=0,
        description="Amount of net LTCG to treat as investment income"
    )

    elect_qualified_dividends: bool = Field(
        default=False,
        description="Elect to treat qualified dividends as investment income"
    )
    qualified_dividends_amount: float = Field(
        default=0.0,
        ge=0,
        description="Amount of qualified dividends to treat as investment income"
    )


class Form4952(BaseModel):
    """
    Form 4952 - Investment Interest Expense Deduction.

    Calculates the allowable investment interest deduction, limited to
    net investment income. Excess is carried forward.

    Key Concepts:
    - Investment interest = interest paid on debt to buy/carry investments
    - Investment income = gross income from investment property
    - Net investment income = investment income - investment expenses
    - Deduction limited to net investment income
    """

    # Part I: Investment Interest Expense
    # Line 1: Total investment interest paid or accrued in current year
    investment_interest_paid: float = Field(
        default=0.0,
        ge=0,
        description="Line 1: Investment interest paid this year"
    )

    # Line 2: Disallowed investment interest from prior year Form 4952 Line 7
    prior_year_carryforward: float = Field(
        default=0.0,
        ge=0,
        description="Line 2: Disallowed interest carried from prior year"
    )

    # Part II: Investment Income
    # Line 4a: Gross income from property held for investment
    # (interest, ordinary dividends, annuities, royalties)
    gross_investment_income: float = Field(
        default=0.0,
        ge=0,
        description="Line 4a: Gross investment income"
    )

    # Line 4b: Qualified dividends included in Line 4a
    qualified_dividends_in_line_4a: float = Field(
        default=0.0,
        ge=0,
        description="Line 4b: Qualified dividends in gross investment income"
    )

    # Line 4c: Subtract 4b from 4a (gross income minus qualified dividends)
    # (calculated field)

    # Line 4d: Net gain from Form 4797 Part II (investment property)
    net_gain_form_4797: float = Field(
        default=0.0,
        ge=0,
        description="Line 4d: Net gain from Form 4797 Part II"
    )

    # Line 4e: Net capital gain from investment property (Schedule D)
    net_capital_gain_investment: float = Field(
        default=0.0,
        ge=0,
        description="Line 4e: Net capital gain from Schedule D"
    )

    # Line 4f: Net capital gain included in Line 4e from collectibles
    capital_gain_collectibles: float = Field(
        default=0.0,
        ge=0,
        description="Line 4f: Capital gain from collectibles (28% rate)"
    )

    # Part III: Investment Expenses
    # Line 5: Investment expenses other than interest
    # (allocable expenses from Schedule A Line 23)
    investment_expenses: float = Field(
        default=0.0,
        ge=0,
        description="Line 5: Investment expenses (not interest)"
    )

    # Election to treat gains/qualified dividends as investment income
    election: InvestmentIncomeElection = Field(
        default_factory=InvestmentIncomeElection,
        description="Election for capital gains/qualified dividends"
    )

    # For tracking
    description: str = Field(
        default="",
        description="Description of investment interest source"
    )

    def calculate_gross_investment_income_after_qualified(self) -> float:
        """Line 4c: Gross investment income minus qualified dividends."""
        return max(0.0, self.gross_investment_income - self.qualified_dividends_in_line_4a)

    def calculate_elected_capital_gains(self) -> float:
        """Amount of capital gains elected to be treated as investment income."""
        if not self.election.elect_capital_gains:
            return 0.0

        # Limited to actual net capital gain minus collectibles (which are already at 28%)
        max_electable = max(0.0, self.net_capital_gain_investment - self.capital_gain_collectibles)
        return min(self.election.capital_gains_amount, max_electable)

    def calculate_elected_qualified_dividends(self) -> float:
        """Amount of qualified dividends elected to be treated as investment income."""
        if not self.election.elect_qualified_dividends:
            return 0.0

        # Limited to actual qualified dividends
        return min(self.election.qualified_dividends_amount, self.qualified_dividends_in_line_4a)

    def calculate_investment_income(self) -> dict:
        """
        Calculate Part II - Total Investment Income.

        Investment income includes:
        - Gross income from investments (minus qualified dividends unless elected)
        - Net gain from Form 4797 Part II
        - Elected capital gains (taxed at ordinary rates)
        - Elected qualified dividends (taxed at ordinary rates)
        """
        result = {
            'line_4a_gross_income': self.gross_investment_income,
            'line_4b_qualified_dividends': self.qualified_dividends_in_line_4a,
            'line_4c_income_less_qualified': 0.0,
            'line_4d_form_4797_gain': self.net_gain_form_4797,
            'line_4e_capital_gain': self.net_capital_gain_investment,
            'line_4f_collectibles': self.capital_gain_collectibles,
            'line_4g_elected_capital_gains': 0.0,
            'line_4h_elected_qualified_dividends': 0.0,
            'total_investment_income': 0.0,
        }

        # Line 4c: Gross minus qualified dividends
        line_4c = self.calculate_gross_investment_income_after_qualified()
        result['line_4c_income_less_qualified'] = line_4c

        # Line 4g: Elected capital gains
        elected_cg = self.calculate_elected_capital_gains()
        result['line_4g_elected_capital_gains'] = elected_cg

        # Line 4h: Elected qualified dividends
        elected_qd = self.calculate_elected_qualified_dividends()
        result['line_4h_elected_qualified_dividends'] = elected_qd

        # Total investment income
        # = Line 4c + Line 4d + Line 4g + Line 4h
        # Note: Line 4e and 4f are informational; actual gain from 4g
        total = (
            line_4c +
            self.net_gain_form_4797 +
            elected_cg +
            elected_qd
        )
        result['total_investment_income'] = float(money(total))

        return result

    def calculate_net_investment_income(self) -> dict:
        """
        Calculate net investment income (Line 6).

        Net investment income = Investment income - Investment expenses
        """
        income = self.calculate_investment_income()

        result = {
            'gross_investment_income': income['total_investment_income'],
            'investment_expenses': self.investment_expenses,
            'net_investment_income': 0.0,
        }

        net = max(0.0, income['total_investment_income'] - self.investment_expenses)
        result['net_investment_income'] = float(money(net))

        return result

    def calculate_deduction(self) -> dict:
        """
        Complete Form 4952 calculation.

        Returns:
        - Total investment interest (current year + carryforward)
        - Net investment income
        - Allowable deduction (limited to net investment income)
        - Disallowed interest (carryforward to next year)
        """
        result = {
            # Part I: Investment Interest Expense
            'line_1_current_year_interest': self.investment_interest_paid,
            'line_2_prior_year_carryforward': self.prior_year_carryforward,
            'line_3_total_investment_interest': 0.0,

            # Part II: Investment Income
            'investment_income_breakdown': {},
            'gross_investment_income': 0.0,

            # Part III: Net Investment Income
            'line_5_investment_expenses': self.investment_expenses,
            'line_6_net_investment_income': 0.0,

            # Deduction and Carryforward
            'line_7_disallowed_interest': 0.0,
            'line_8_allowable_deduction': 0.0,

            # Elections
            'elected_capital_gains': 0.0,
            'elected_qualified_dividends': 0.0,

            # Summary
            'carryforward_to_next_year': 0.0,
        }

        # Line 3: Total investment interest
        total_interest = self.investment_interest_paid + self.prior_year_carryforward
        result['line_3_total_investment_interest'] = float(money(total_interest))

        # Investment income breakdown
        income = self.calculate_investment_income()
        result['investment_income_breakdown'] = income
        result['gross_investment_income'] = income['total_investment_income']
        result['elected_capital_gains'] = income['line_4g_elected_capital_gains']
        result['elected_qualified_dividends'] = income['line_4h_elected_qualified_dividends']

        # Net investment income
        net_income = self.calculate_net_investment_income()
        result['line_6_net_investment_income'] = net_income['net_investment_income']

        # Allowable deduction (limited to net investment income)
        net_inv_income = net_income['net_investment_income']
        allowable = min(total_interest, net_inv_income)
        result['line_8_allowable_deduction'] = float(money(allowable))

        # Disallowed (carryforward)
        disallowed = max(0.0, total_interest - net_inv_income)
        result['line_7_disallowed_interest'] = float(money(disallowed))
        result['carryforward_to_next_year'] = float(money(disallowed))

        return result

    def get_form_4952_summary(self) -> dict:
        """Get summary suitable for tax return integration."""
        calc = self.calculate_deduction()
        return {
            'total_investment_interest': calc['line_3_total_investment_interest'],
            'net_investment_income': calc['line_6_net_investment_income'],
            'allowable_deduction': calc['line_8_allowable_deduction'],
            'carryforward': calc['carryforward_to_next_year'],
            'elected_capital_gains': calc['elected_capital_gains'],
            'elected_qualified_dividends': calc['elected_qualified_dividends'],
        }


def calculate_investment_interest_deduction(
    interest_paid: float,
    prior_carryforward: float = 0.0,
    gross_investment_income: float = 0.0,
    investment_expenses: float = 0.0,
    qualified_dividends: float = 0.0,
    capital_gains: float = 0.0,
    elect_capital_gains: bool = False,
    elect_qualified_dividends: bool = False,
) -> dict:
    """
    Convenience function to calculate investment interest deduction.

    Args:
        interest_paid: Investment interest paid this year
        prior_carryforward: Disallowed interest from prior year
        gross_investment_income: Gross income from investment property
        investment_expenses: Investment expenses other than interest
        qualified_dividends: Qualified dividends (if electing to include)
        capital_gains: Net capital gains (if electing to include)
        elect_capital_gains: True to treat capital gains as investment income
        elect_qualified_dividends: True to treat qualified divs as investment income

    Returns:
        Form 4952 calculation results
    """
    election = InvestmentIncomeElection(
        elect_capital_gains=elect_capital_gains,
        capital_gains_amount=capital_gains if elect_capital_gains else 0.0,
        elect_qualified_dividends=elect_qualified_dividends,
        qualified_dividends_amount=qualified_dividends if elect_qualified_dividends else 0.0,
    )

    form = Form4952(
        investment_interest_paid=interest_paid,
        prior_year_carryforward=prior_carryforward,
        gross_investment_income=gross_investment_income,
        qualified_dividends_in_line_4a=qualified_dividends,
        net_capital_gain_investment=capital_gains,
        investment_expenses=investment_expenses,
        election=election,
    )

    return form.calculate_deduction()
