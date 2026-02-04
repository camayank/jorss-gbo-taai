"""
Form 1116 - Foreign Tax Credit

Calculates the Foreign Tax Credit (FTC) to prevent double taxation on
income earned in foreign countries.

Key IRS Rules:
- FTC = min(Foreign Taxes Paid, FTC Limitation)
- FTC Limitation = Total Tax × (Foreign Source Taxable Income / Total Taxable Income)
- Separate calculation required for each income category (passive, general, etc.)
- Carryback: 1 year
- Carryforward: 10 years (FIFO ordering)
- Simplified method: No Form 1116 needed if foreign taxes ≤ $300 ($600 MFJ)
  and all income is passive from qualified payee statements

Income Categories (Form 1116, Line 1):
- Category A (Section 951A): GILTI income
- Category B (Foreign Branch): Foreign branch income
- Category C (Passive): Dividends, interest, rents, royalties
- Category D (General): Wages, business income, other
- Category E (Section 901(j)): Sanctioned countries
- Category F (Lump-sum): Certain retirement distributions

Per IRC Section 901, 904, and related regulations.
"""

from typing import Optional, List, Dict, Any, ClassVar
from pydantic import BaseModel, Field
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class ForeignIncomeCategory(str, Enum):
    """
    Income categories for Form 1116 separate limitation.
    Each category requires its own Form 1116.
    """
    SECTION_951A = "section_951a"  # Category A: GILTI inclusion
    FOREIGN_BRANCH = "foreign_branch"  # Category B: Foreign branch income
    PASSIVE = "passive"  # Category C: Passive income (dividends, interest, etc.)
    GENERAL = "general"  # Category D: General category (wages, business, etc.)
    SECTION_901J = "section_901j"  # Category E: Sanctioned countries
    LUMP_SUM = "lump_sum"  # Category F: Lump-sum distributions
    TREATY_RESOURCED = "treaty_resourced"  # Treaty-resourced income


class ForeignTaxType(str, Enum):
    """Type of foreign tax paid."""
    INCOME_TAX = "income_tax"  # Foreign income tax
    WITHHOLDING_TAX = "withholding_tax"  # Tax withheld at source
    WAR_PROFITS_TAX = "war_profits_tax"  # War profits tax
    EXCESS_PROFITS_TAX = "excess_profits_tax"  # Excess profits tax
    IN_LIEU_TAX = "in_lieu_tax"  # Tax paid in lieu of income tax


class ForeignTaxAccrualMethod(str, Enum):
    """Method for reporting foreign taxes."""
    PAID = "paid"  # Cash method - taxes actually paid
    ACCRUED = "accrued"  # Accrual method - taxes accrued


class ForeignCountryTax(BaseModel):
    """
    Foreign taxes paid to a specific country.
    Form 1116 Part II, Column (a)-(h).
    """
    country_code: str = Field(
        description="Two-letter country code (ISO 3166-1 alpha-2)"
    )
    country_name: str = Field(
        description="Name of foreign country or U.S. possession"
    )

    # Income earned in this country
    gross_income: float = Field(
        default=0.0,
        ge=0,
        description="Gross income from sources in this country"
    )

    # Deductions allocated to foreign income
    definitely_related_expenses: float = Field(
        default=0.0,
        ge=0,
        description="Expenses definitely related to foreign income"
    )

    # Foreign taxes paid or accrued
    taxes_paid_in_foreign_currency: float = Field(
        default=0.0,
        ge=0,
        description="Taxes paid in foreign currency (for conversion)"
    )
    exchange_rate: float = Field(
        default=1.0,
        gt=0,
        description="Exchange rate to USD (default 1.0 if paid in USD)"
    )
    taxes_paid_usd: float = Field(
        default=0.0,
        ge=0,
        description="Taxes paid or accrued in USD"
    )

    # Tax type and date
    tax_type: ForeignTaxType = Field(
        default=ForeignTaxType.INCOME_TAX,
        description="Type of foreign tax"
    )
    date_paid: Optional[str] = Field(
        None,
        description="Date taxes were paid (YYYY-MM-DD)"
    )

    # Withholding details (for passive income)
    is_qualified_dividend_tax: bool = Field(
        default=False,
        description="Tax on qualified dividends"
    )
    is_interest_withholding: bool = Field(
        default=False,
        description="Tax withheld on interest income"
    )

    def get_net_foreign_income(self) -> float:
        """Calculate net foreign income after deductions."""
        return max(0.0, self.gross_income - self.definitely_related_expenses)


class FTCCarryover(BaseModel):
    """
    Foreign Tax Credit carryover from prior/future years.
    FTC can be carried back 1 year and forward 10 years.
    """
    tax_year: int = Field(
        description="Tax year the unused credit originated"
    )
    category: ForeignIncomeCategory = Field(
        description="Income category for the carryover"
    )
    original_amount: float = Field(
        ge=0,
        description="Original unused credit amount"
    )
    remaining_amount: float = Field(
        ge=0,
        description="Amount still available after prior usage"
    )
    is_carryback: bool = Field(
        default=False,
        description="True if this is a carryback from future year"
    )

    def years_remaining(self, current_year: int) -> int:
        """Calculate years remaining for carryforward."""
        if self.is_carryback:
            # Carryback expires after 1 year
            return max(0, 1 - (current_year - self.tax_year))
        else:
            # Carryforward expires after 10 years
            return max(0, 10 - (current_year - self.tax_year))


class Form1116Category(BaseModel):
    """
    Form 1116 calculation for a single income category.
    Each category has its own limitation calculation.
    """
    category: ForeignIncomeCategory = Field(
        default=ForeignIncomeCategory.PASSIVE,
        description="Income category for this Form 1116"
    )

    # Part I: Taxable Income From Sources Outside U.S.
    gross_foreign_income: float = Field(
        default=0.0,
        ge=0,
        description="Line 1a: Gross income from foreign sources"
    )

    # Deductions definitely related to foreign income
    foreign_income_deductions: float = Field(
        default=0.0,
        ge=0,
        description="Lines 2-6: Deductions related to foreign income"
    )

    # Pro-rata share of other deductions
    home_mortgage_interest_allocated: float = Field(
        default=0.0,
        ge=0,
        description="Line 3b: Home mortgage interest (allocated share)"
    )
    other_interest_allocated: float = Field(
        default=0.0,
        ge=0,
        description="Line 3c: Other interest expense (allocated)"
    )
    state_local_taxes_allocated: float = Field(
        default=0.0,
        ge=0,
        description="Line 4: State/local taxes (allocated)"
    )
    other_deductions_allocated: float = Field(
        default=0.0,
        ge=0,
        description="Line 5: Other deductions (allocated)"
    )

    # Foreign losses from other categories
    foreign_losses_other_categories: float = Field(
        default=0.0,
        ge=0,
        description="Line 6: Loss from other Form 1116 categories"
    )

    # Part II: Foreign Taxes Paid or Accrued
    country_taxes: List[ForeignCountryTax] = Field(
        default_factory=list,
        description="Taxes paid to each country"
    )

    accrual_method: ForeignTaxAccrualMethod = Field(
        default=ForeignTaxAccrualMethod.PAID,
        description="Method for reporting foreign taxes"
    )

    # Part III: Credit Limitation
    # (Calculated values - set by calculate methods)

    # Carryovers for this category
    carryovers: List[FTCCarryover] = Field(
        default_factory=list,
        description="Carryforward/carryback credits for this category"
    )

    def get_total_foreign_taxes(self) -> float:
        """Sum of all foreign taxes paid for this category."""
        return sum(ct.taxes_paid_usd for ct in self.country_taxes)

    def get_total_allocated_deductions(self) -> float:
        """Sum of allocated deductions."""
        return (
            self.foreign_income_deductions +
            self.home_mortgage_interest_allocated +
            self.other_interest_allocated +
            self.state_local_taxes_allocated +
            self.other_deductions_allocated
        )

    def get_net_foreign_income(self) -> float:
        """Calculate net foreign source taxable income."""
        return max(
            0.0,
            self.gross_foreign_income -
            self.get_total_allocated_deductions() -
            self.foreign_losses_other_categories
        )

    def get_available_carryovers(self, current_year: int) -> float:
        """Get total available carryover credits (not expired)."""
        return sum(
            c.remaining_amount
            for c in self.carryovers
            if c.years_remaining(current_year) > 0
        )


class Form1116(BaseModel):
    """
    Complete Form 1116 - Foreign Tax Credit calculation.

    This form prevents double taxation on foreign income by providing
    a credit for foreign taxes paid. The credit is limited to the
    U.S. tax that would have been owed on the foreign income.

    Key Formula:
    FTC Limitation = Total U.S. Tax × (Foreign Source Taxable Income / Total Taxable Income)

    The actual credit is the lesser of:
    - Foreign taxes paid
    - FTC limitation

    Separate calculations required for each income category.
    """

    # Class-level constants
    SIMPLIFIED_THRESHOLD_SINGLE: ClassVar[float] = 300.0  # $300 for single
    SIMPLIFIED_THRESHOLD_MFJ: ClassVar[float] = 600.0  # $600 for MFJ
    CARRYBACK_YEARS: ClassVar[int] = 1
    CARRYFORWARD_YEARS: ClassVar[int] = 10

    # Category-specific Form 1116s
    categories: List[Form1116Category] = Field(
        default_factory=list,
        description="Form 1116 for each income category"
    )

    # Simplified method fields (when Form 1116 not required)
    use_simplified_method: bool = Field(
        default=False,
        description="Using simplified method (no Form 1116 required)"
    )
    simplified_foreign_taxes: float = Field(
        default=0.0,
        ge=0,
        description="Foreign taxes for simplified method"
    )

    # Tax information needed for limitation calculation
    total_taxable_income: float = Field(
        default=0.0,
        description="Total taxable income (Form 1040 Line 15)"
    )
    total_tax_before_credits: float = Field(
        default=0.0,
        ge=0,
        description="Total tax before credits"
    )

    # AMT Foreign Tax Credit (Form 6251)
    calculate_amt_ftc: bool = Field(
        default=False,
        description="Calculate AMT foreign tax credit"
    )
    amt_foreign_source_income: float = Field(
        default=0.0,
        ge=0,
        description="Foreign source AMTI"
    )
    tentative_minimum_tax: float = Field(
        default=0.0,
        ge=0,
        description="TMT before AMT FTC"
    )

    # High tax kickout election
    high_tax_kickout_election: bool = Field(
        default=False,
        description="Elect to treat high-taxed income as general category"
    )

    def get_or_create_category(
        self,
        category: ForeignIncomeCategory
    ) -> Form1116Category:
        """Get existing category or create a new one."""
        for cat in self.categories:
            if cat.category == category:
                return cat

        new_cat = Form1116Category(category=category)
        self.categories.append(new_cat)
        return new_cat

    def can_use_simplified_method(self, filing_status: str) -> bool:
        """
        Check if taxpayer can use simplified FTC method.

        Simplified method allowed if:
        1. All foreign income is passive (dividends, interest, etc.)
        2. All foreign taxes reported on Form 1099-DIV, 1099-INT, or K-1
        3. Total foreign taxes ≤ $300 single / $600 MFJ
        """
        total_taxes = sum(cat.get_total_foreign_taxes() for cat in self.categories)

        # Add simplified method taxes
        total_taxes += self.simplified_foreign_taxes

        threshold = (
            self.SIMPLIFIED_THRESHOLD_MFJ
            if filing_status == "married_joint"
            else self.SIMPLIFIED_THRESHOLD_SINGLE
        )

        if total_taxes > threshold:
            return False

        # Check if all income is passive
        for cat in self.categories:
            if cat.category not in [
                ForeignIncomeCategory.PASSIVE,
                ForeignIncomeCategory.SECTION_951A
            ]:
                if cat.get_total_foreign_taxes() > 0:
                    return False

        return True

    def get_total_foreign_source_income(self) -> float:
        """Get combined foreign source income across all categories."""
        return sum(cat.get_net_foreign_income() for cat in self.categories)

    def get_total_foreign_taxes_paid(self) -> float:
        """Get total foreign taxes paid across all categories."""
        return (
            sum(cat.get_total_foreign_taxes() for cat in self.categories) +
            self.simplified_foreign_taxes
        )

    def calculate_category_limitation(
        self,
        category: Form1116Category
    ) -> dict:
        """
        Calculate FTC limitation for a single category.

        Limitation = Total Tax × (Category Foreign Income / Total Taxable Income)

        Returns breakdown with limitation amount and allowable credit.
        """
        result = {
            'category': category.category.value,
            'gross_foreign_income': category.gross_foreign_income,
            'net_foreign_income': 0.0,
            'foreign_taxes_paid': 0.0,
            'limitation': 0.0,
            'credit_before_carryover': 0.0,
            'carryover_used': 0.0,
            'credit_allowed': 0.0,
            'excess_taxes': 0.0,  # For carryforward
            'excess_limitation': 0.0,  # For using carryovers
        }

        # Calculate net foreign income for this category
        net_income = category.get_net_foreign_income()
        result['net_foreign_income'] = float(money(net_income))

        # Get foreign taxes paid
        taxes_paid = category.get_total_foreign_taxes()
        result['foreign_taxes_paid'] = float(money(taxes_paid))

        if net_income <= 0 or self.total_taxable_income <= 0:
            # No limitation if no foreign income or total income
            result['excess_taxes'] = taxes_paid
            return result

        if self.total_tax_before_credits <= 0:
            # No tax means no credit (but taxes carry forward)
            result['excess_taxes'] = taxes_paid
            return result

        # Calculate limitation ratio
        # Foreign income ratio cannot exceed 100%
        income_ratio = min(1.0, net_income / self.total_taxable_income)

        # Limitation = Total Tax × Ratio
        limitation = self.total_tax_before_credits * income_ratio
        result['limitation'] = float(money(limitation))

        # Credit is lesser of taxes paid or limitation
        credit_before_carryover = min(taxes_paid, limitation)
        result['credit_before_carryover'] = float(money(credit_before_carryover))

        # Calculate excess limitation (room for carryovers)
        excess_limitation = max(0.0, limitation - taxes_paid)
        result['excess_limitation'] = float(money(excess_limitation))

        # Apply carryovers (FIFO - oldest first)
        current_year = 2025  # Would be passed in production
        carryover_used = 0.0

        if excess_limitation > 0:
            # Sort carryovers by year (oldest first for FIFO)
            sorted_carryovers = sorted(
                [c for c in category.carryovers if c.years_remaining(current_year) > 0],
                key=lambda c: c.tax_year
            )

            remaining_limitation = excess_limitation
            for carryover in sorted_carryovers:
                if remaining_limitation <= 0:
                    break
                use_amount = min(carryover.remaining_amount, remaining_limitation)
                carryover_used += use_amount
                remaining_limitation -= use_amount

        result['carryover_used'] = float(money(carryover_used))

        # Total credit allowed
        credit_allowed = credit_before_carryover + carryover_used
        result['credit_allowed'] = float(money(credit_allowed))

        # Calculate excess taxes for carryforward
        if taxes_paid > limitation:
            result['excess_taxes'] = float(money(taxes_paid - limitation))

        return result

    def calculate_all_categories(self) -> dict:
        """
        Calculate FTC for all income categories.

        Returns combined results with breakdown by category.
        """
        result = {
            'total_foreign_taxes_paid': 0.0,
            'total_limitation': 0.0,
            'total_credit_allowed': 0.0,
            'total_carryover_used': 0.0,
            'total_excess_for_carryforward': 0.0,
            'categories': [],
            'simplified_method_used': False,
        }

        # Check for simplified method
        if self.use_simplified_method:
            result['simplified_method_used'] = True
            result['total_foreign_taxes_paid'] = self.simplified_foreign_taxes
            result['total_credit_allowed'] = self.simplified_foreign_taxes
            return result

        # Calculate each category
        for category in self.categories:
            cat_result = self.calculate_category_limitation(category)
            result['categories'].append(cat_result)

            result['total_foreign_taxes_paid'] += cat_result['foreign_taxes_paid']
            result['total_limitation'] += cat_result['limitation']
            result['total_credit_allowed'] += cat_result['credit_allowed']
            result['total_carryover_used'] += cat_result['carryover_used']
            result['total_excess_for_carryforward'] += cat_result['excess_taxes']

        # Round totals
        for key in result:
            if isinstance(result[key], float):
                result[key] = float(money(result[key]))

        return result

    def calculate_amt_foreign_tax_credit(self) -> dict:
        """
        Calculate AMT Foreign Tax Credit (for Form 6251).

        Similar to regular FTC but uses:
        - AMTI instead of taxable income
        - TMT instead of regular tax

        The AMT FTC reduces TMT but cannot reduce it below zero.
        """
        result = {
            'amt_foreign_source_income': self.amt_foreign_source_income,
            'total_amti': 0.0,  # Would be set from Form 6251
            'tentative_minimum_tax': self.tentative_minimum_tax,
            'amt_ftc_limitation': 0.0,
            'foreign_taxes_available': 0.0,
            'amt_foreign_tax_credit': 0.0,
        }

        if not self.calculate_amt_ftc:
            return result

        # Get total foreign taxes
        foreign_taxes = self.get_total_foreign_taxes_paid()
        result['foreign_taxes_available'] = foreign_taxes

        if self.amt_foreign_source_income <= 0 or self.tentative_minimum_tax <= 0:
            return result

        # AMT FTC limitation uses same formula
        # Would need AMTI passed in for full calculation
        # For now, use same ratio as regular FTC
        if self.total_taxable_income > 0:
            income_ratio = min(
                1.0,
                self.amt_foreign_source_income / self.total_taxable_income
            )
            amt_limitation = self.tentative_minimum_tax * income_ratio
            result['amt_ftc_limitation'] = float(money(amt_limitation))
            result['amt_foreign_tax_credit'] = float(money(
                min(foreign_taxes, amt_limitation)
            ))

        return result

    def calculate_ftc(
        self,
        filing_status: str = "single",
        current_year: int = 2025
    ) -> dict:
        """
        Complete Form 1116 calculation.

        Returns comprehensive breakdown including:
        - All category results
        - Total credit allowed
        - Carryforward amounts
        - AMT FTC if applicable
        """
        result = {
            # Summary
            'filing_status': filing_status,
            'tax_year': current_year,
            'can_use_simplified': False,
            'using_simplified': self.use_simplified_method,

            # Totals
            'total_foreign_source_income': 0.0,
            'total_taxable_income': self.total_taxable_income,
            'total_tax_before_credits': self.total_tax_before_credits,
            'total_foreign_taxes_paid': 0.0,
            'total_ftc_limitation': 0.0,
            'total_ftc_allowed': 0.0,
            'total_carryover_used': 0.0,
            'new_carryforward': 0.0,

            # Category breakdown
            'category_results': [],

            # AMT FTC (Form 6251)
            'amt_ftc': 0.0,
            'amt_ftc_breakdown': {},
        }

        # Check simplified method eligibility
        result['can_use_simplified'] = self.can_use_simplified_method(filing_status)

        # If using simplified method
        if self.use_simplified_method and result['can_use_simplified']:
            result['total_foreign_taxes_paid'] = self.simplified_foreign_taxes
            result['total_ftc_allowed'] = self.simplified_foreign_taxes
            return result

        # Calculate all categories
        all_categories = self.calculate_all_categories()

        result['total_foreign_source_income'] = self.get_total_foreign_source_income()
        result['total_foreign_taxes_paid'] = all_categories['total_foreign_taxes_paid']
        result['total_ftc_limitation'] = all_categories['total_limitation']
        result['total_ftc_allowed'] = all_categories['total_credit_allowed']
        result['total_carryover_used'] = all_categories['total_carryover_used']
        result['new_carryforward'] = all_categories['total_excess_for_carryforward']
        result['category_results'] = all_categories['categories']

        # Calculate AMT FTC if applicable
        if self.calculate_amt_ftc:
            amt_result = self.calculate_amt_foreign_tax_credit()
            result['amt_ftc'] = amt_result['amt_foreign_tax_credit']
            result['amt_ftc_breakdown'] = amt_result

        return result


def create_passive_income_category(
    dividend_income: float = 0.0,
    interest_income: float = 0.0,
    foreign_taxes_on_dividends: float = 0.0,
    foreign_taxes_on_interest: float = 0.0,
    country_code: str = "XX",
    country_name: str = "Various"
) -> Form1116Category:
    """
    Helper to create a passive income category Form 1116.

    Common for taxpayers with foreign dividends/interest and
    associated withholding taxes reported on Form 1099-DIV/INT.
    """
    category = Form1116Category(
        category=ForeignIncomeCategory.PASSIVE,
        gross_foreign_income=dividend_income + interest_income,
    )

    if foreign_taxes_on_dividends > 0 or foreign_taxes_on_interest > 0:
        country_tax = ForeignCountryTax(
            country_code=country_code,
            country_name=country_name,
            gross_income=dividend_income + interest_income,
            taxes_paid_usd=foreign_taxes_on_dividends + foreign_taxes_on_interest,
            is_qualified_dividend_tax=foreign_taxes_on_dividends > 0,
            is_interest_withholding=foreign_taxes_on_interest > 0,
        )
        category.country_taxes.append(country_tax)

    return category


def create_general_income_category(
    wages_income: float = 0.0,
    business_income: float = 0.0,
    foreign_taxes_paid: float = 0.0,
    country_code: str = "XX",
    country_name: str = "Various"
) -> Form1116Category:
    """
    Helper to create a general income category Form 1116.

    For wages earned abroad or foreign business income.
    """
    category = Form1116Category(
        category=ForeignIncomeCategory.GENERAL,
        gross_foreign_income=wages_income + business_income,
    )

    if foreign_taxes_paid > 0:
        country_tax = ForeignCountryTax(
            country_code=country_code,
            country_name=country_name,
            gross_income=wages_income + business_income,
            taxes_paid_usd=foreign_taxes_paid,
        )
        category.country_taxes.append(country_tax)

    return category
