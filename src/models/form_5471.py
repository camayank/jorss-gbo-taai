"""
Form 5471 - Information Return of U.S. Persons With Respect To Certain Foreign Corporations

This form is used by U.S. persons who are officers, directors, or shareholders of
certain foreign corporations to report information about the foreign corporation.

Who Must File:
Category 1: U.S. shareholder of specified foreign corporation (SFC) that is a CFC
Category 2: Officer or director of foreign corporation with U.S. person as 10%+ shareholder
Category 3: U.S. person who acquires stock bringing ownership to 10%+ or additional 10%
Category 4: U.S. person with "control" of foreign corporation for 30+ uninterrupted days
Category 5: 10%+ shareholder of controlled foreign corporation (CFC)

Key Concepts:
- Controlled Foreign Corporation (CFC): >50% owned by U.S. shareholders (10%+ each)
- Passive Foreign Investment Company (PFIC): >75% passive income or >50% passive assets
- Subpart F Income: Certain income of CFC taxable to U.S. shareholders currently
- GILTI: Global Intangible Low-Taxed Income (Section 951A)
- Section 965: Transition tax on deferred foreign earnings

Per IRS Form 5471 Instructions and IRC Sections 951, 951A, 957, 958.
"""

from typing import Optional, List, Dict, Any, ClassVar
from pydantic import BaseModel, Field
from enum import Enum
from datetime import date
from decimal import Decimal


class FilingCategory(str, Enum):
    """Categories of Form 5471 filers."""
    CATEGORY_1 = "category_1"  # U.S. shareholder of SFC that is CFC
    CATEGORY_2 = "category_2"  # Officer/director with 10%+ U.S. shareholder
    CATEGORY_3 = "category_3"  # Acquires 10%+ stock or additional 10%
    CATEGORY_4 = "category_4"  # Control for 30+ days
    CATEGORY_5 = "category_5"  # 10%+ shareholder of CFC


class ForeignCorporationType(str, Enum):
    """Types of foreign corporations."""
    CFC = "cfc"  # Controlled Foreign Corporation
    PFIC = "pfic"  # Passive Foreign Investment Company
    SFC = "sfc"  # Specified Foreign Corporation
    OTHER = "other"


class SubpartFIncomeType(str, Enum):
    """Types of Subpart F income."""
    INSURANCE_INCOME = "insurance_income"
    FOREIGN_BASE_COMPANY_INCOME = "foreign_base_company_income"
    INTERNATIONAL_BOYCOTT_INCOME = "international_boycott_income"
    ILLEGAL_BRIBES = "illegal_bribes"
    INCOME_FROM_SECTION_901J_COUNTRIES = "section_901j_countries"


class ForeignCorporationInfo(BaseModel):
    """Basic information about the foreign corporation."""
    name: str = Field(default="", description="Name of foreign corporation")
    address: str = Field(default="", description="Address")
    country_of_incorporation: str = Field(default="", description="Country code")
    date_of_incorporation: Optional[date] = Field(default=None)
    ein_or_reference_id: str = Field(default="", description="EIN or reference ID")

    # Functional currency
    functional_currency: str = Field(default="USD", description="Functional currency code")
    exchange_rate_to_usd: float = Field(default=1.0, gt=0, description="Exchange rate to USD")

    # Corporation type
    corporation_type: ForeignCorporationType = Field(
        default=ForeignCorporationType.CFC,
        description="Type of foreign corporation"
    )
    is_cfc: bool = Field(default=False, description="Is a Controlled Foreign Corporation")
    is_pfic: bool = Field(default=False, description="Is a Passive Foreign Investment Company")

    # Tax year
    tax_year_begin: Optional[date] = Field(default=None)
    tax_year_end: Optional[date] = Field(default=None)

    # Principal business activity
    principal_business_activity: str = Field(default="")
    principal_business_activity_code: str = Field(default="")


class ShareholderInfo(BaseModel):
    """Information about U.S. shareholder."""
    name: str = Field(default="", description="Shareholder name")
    identifying_number: str = Field(default="", description="SSN or EIN")
    address: str = Field(default="")

    # Ownership
    direct_ownership_percent: float = Field(
        default=0.0, ge=0, le=100,
        description="Direct ownership percentage"
    )
    indirect_ownership_percent: float = Field(
        default=0.0, ge=0, le=100,
        description="Indirect ownership percentage"
    )
    constructive_ownership_percent: float = Field(
        default=0.0, ge=0, le=100,
        description="Constructive ownership percentage"
    )

    # Stock information
    shares_held_directly: int = Field(default=0, ge=0)
    shares_held_indirectly: int = Field(default=0, ge=0)
    value_of_stock: float = Field(default=0.0, ge=0)

    # Filing category
    filing_categories: List[FilingCategory] = Field(
        default_factory=list,
        description="Filing categories applicable to this shareholder"
    )

    def total_ownership_percent(self) -> float:
        """Total ownership including direct, indirect, and constructive."""
        return min(100.0,
            self.direct_ownership_percent +
            self.indirect_ownership_percent +
            self.constructive_ownership_percent
        )


class ScheduleC_IncomeStatement(BaseModel):
    """Schedule C - Income Statement of the Foreign Corporation."""
    # Gross income
    gross_receipts_or_sales: float = Field(default=0.0)
    returns_and_allowances: float = Field(default=0.0)
    cost_of_goods_sold: float = Field(default=0.0)
    dividends: float = Field(default=0.0)
    interest: float = Field(default=0.0)
    gross_rents: float = Field(default=0.0)
    gross_royalties: float = Field(default=0.0)
    net_capital_gain: float = Field(default=0.0)
    other_income: float = Field(default=0.0)

    # Deductions
    compensation_of_officers: float = Field(default=0.0)
    salaries_and_wages: float = Field(default=0.0)
    repairs: float = Field(default=0.0)
    bad_debts: float = Field(default=0.0)
    rents: float = Field(default=0.0)
    taxes: float = Field(default=0.0)
    interest_expense: float = Field(default=0.0)
    depreciation: float = Field(default=0.0)
    depletion: float = Field(default=0.0)
    advertising: float = Field(default=0.0)
    other_deductions: float = Field(default=0.0)

    def gross_income(self) -> float:
        """Calculate gross income."""
        return (
            self.gross_receipts_or_sales -
            self.returns_and_allowances -
            self.cost_of_goods_sold +
            self.dividends +
            self.interest +
            self.gross_rents +
            self.gross_royalties +
            self.net_capital_gain +
            self.other_income
        )

    def total_deductions(self) -> float:
        """Calculate total deductions."""
        return (
            self.compensation_of_officers +
            self.salaries_and_wages +
            self.repairs +
            self.bad_debts +
            self.rents +
            self.taxes +
            self.interest_expense +
            self.depreciation +
            self.depletion +
            self.advertising +
            self.other_deductions
        )

    def net_income(self) -> float:
        """Calculate net income before taxes."""
        return self.gross_income() - self.total_deductions()


class ScheduleE_ForeignTaxes(BaseModel):
    """Schedule E - Income, War Profits, and Excess Profits Taxes Paid or Accrued."""
    # Taxes paid directly
    foreign_income_taxes_paid: float = Field(default=0.0, ge=0)
    foreign_income_taxes_accrued: float = Field(default=0.0, ge=0)

    # By country
    taxes_by_country: Dict[str, float] = Field(
        default_factory=dict,
        description="Foreign taxes by country code"
    )

    # Tax deemed paid (Section 960)
    section_960_deemed_paid: float = Field(default=0.0, ge=0)

    def total_foreign_taxes(self) -> float:
        """Total foreign taxes paid or accrued."""
        return self.foreign_income_taxes_paid + self.foreign_income_taxes_accrued


class ScheduleF_BalanceSheet(BaseModel):
    """Schedule F - Balance Sheet."""
    # Assets
    cash: float = Field(default=0.0, ge=0)
    accounts_receivable: float = Field(default=0.0, ge=0)
    inventories: float = Field(default=0.0, ge=0)
    investments_in_stock: float = Field(default=0.0, ge=0)
    other_current_assets: float = Field(default=0.0, ge=0)
    loans_to_shareholders: float = Field(default=0.0, ge=0)
    buildings_and_equipment: float = Field(default=0.0, ge=0)
    less_accumulated_depreciation: float = Field(default=0.0, ge=0)
    intangible_assets: float = Field(default=0.0, ge=0)
    other_assets: float = Field(default=0.0, ge=0)

    # Liabilities
    accounts_payable: float = Field(default=0.0, ge=0)
    other_current_liabilities: float = Field(default=0.0, ge=0)
    loans_from_shareholders: float = Field(default=0.0, ge=0)
    long_term_debt: float = Field(default=0.0, ge=0)
    other_liabilities: float = Field(default=0.0, ge=0)

    # Equity
    capital_stock: float = Field(default=0.0, ge=0)
    paid_in_capital: float = Field(default=0.0, ge=0)
    retained_earnings: float = Field(default=0.0)

    def total_assets(self) -> float:
        """Calculate total assets."""
        return (
            self.cash +
            self.accounts_receivable +
            self.inventories +
            self.investments_in_stock +
            self.other_current_assets +
            self.loans_to_shareholders +
            self.buildings_and_equipment -
            self.less_accumulated_depreciation +
            self.intangible_assets +
            self.other_assets
        )

    def total_liabilities(self) -> float:
        """Calculate total liabilities."""
        return (
            self.accounts_payable +
            self.other_current_liabilities +
            self.loans_from_shareholders +
            self.long_term_debt +
            self.other_liabilities
        )

    def total_equity(self) -> float:
        """Calculate total equity."""
        return self.capital_stock + self.paid_in_capital + self.retained_earnings


class ScheduleH_EarningsAndProfits(BaseModel):
    """Schedule H - Current Earnings and Profits (E&P)."""
    # Starting point
    net_income_per_books: float = Field(default=0.0)

    # Additions
    federal_income_tax_expense: float = Field(default=0.0)
    income_not_on_books: float = Field(default=0.0)
    depreciation_book_tax_diff: float = Field(default=0.0)
    other_additions: float = Field(default=0.0)

    # Subtractions
    income_on_books_not_taxable: float = Field(default=0.0)
    deductions_not_on_books: float = Field(default=0.0)
    other_subtractions: float = Field(default=0.0)

    def current_ep(self) -> float:
        """Calculate current year E&P."""
        additions = (
            self.federal_income_tax_expense +
            self.income_not_on_books +
            self.depreciation_book_tax_diff +
            self.other_additions
        )
        subtractions = (
            self.income_on_books_not_taxable +
            self.deductions_not_on_books +
            self.other_subtractions
        )
        return self.net_income_per_books + additions - subtractions


class ScheduleI1_GILTI(BaseModel):
    """Schedule I-1 - Information for Global Intangible Low-Taxed Income."""
    # Tested income
    gross_tested_income: float = Field(default=0.0, ge=0)

    # QBAI - Qualified Business Asset Investment
    qbai_at_year_end: float = Field(default=0.0, ge=0)

    # Tested loss
    tested_loss: float = Field(default=0.0, ge=0)

    # Interest expense
    tested_interest_expense: float = Field(default=0.0, ge=0)
    tested_interest_income: float = Field(default=0.0, ge=0)

    # Tested income after adjustments
    def net_tested_income(self) -> float:
        """Net tested income for GILTI."""
        return max(0.0, self.gross_tested_income - self.tested_loss)

    def deemed_tangible_income_return(self) -> float:
        """10% of QBAI (deemed tangible income return)."""
        return self.qbai_at_year_end * 0.10


class SubpartFIncome(BaseModel):
    """Subpart F income components."""
    # Foreign base company income
    foreign_personal_holding_company_income: float = Field(default=0.0, ge=0)
    foreign_base_company_sales_income: float = Field(default=0.0, ge=0)
    foreign_base_company_services_income: float = Field(default=0.0, ge=0)

    # Insurance income
    insurance_income: float = Field(default=0.0, ge=0)

    # Other Subpart F
    international_boycott_income: float = Field(default=0.0, ge=0)
    illegal_bribes_etc: float = Field(default=0.0, ge=0)
    section_901j_income: float = Field(default=0.0, ge=0)

    # Exclusions and limitations
    high_tax_exception_amount: float = Field(default=0.0, ge=0)
    de_minimis_exclusion: float = Field(default=0.0, ge=0)
    same_country_exclusion: float = Field(default=0.0, ge=0)

    def gross_subpart_f_income(self) -> float:
        """Calculate gross Subpart F income."""
        return (
            self.foreign_personal_holding_company_income +
            self.foreign_base_company_sales_income +
            self.foreign_base_company_services_income +
            self.insurance_income +
            self.international_boycott_income +
            self.illegal_bribes_etc +
            self.section_901j_income
        )

    def net_subpart_f_income(self) -> float:
        """Calculate net Subpart F income after exclusions."""
        gross = self.gross_subpart_f_income()
        exclusions = (
            self.high_tax_exception_amount +
            self.de_minimis_exclusion +
            self.same_country_exclusion
        )
        return max(0.0, gross - exclusions)


class Form5471(BaseModel):
    """
    Form 5471 - Information Return of U.S. Persons With Respect To Certain Foreign Corporations.

    This is primarily an information return, but it also calculates amounts
    that affect the U.S. shareholder's tax return (Subpart F income, GILTI, etc.).
    """

    # Thresholds
    CFC_OWNERSHIP_THRESHOLD: ClassVar[float] = 10.0  # 10% for CFC shareholder
    CONTROL_THRESHOLD: ClassVar[float] = 50.0  # 50% for control

    # Filer information
    filer_name: str = Field(default="")
    filer_identifying_number: str = Field(default="")
    filer_address: str = Field(default="")

    # Foreign corporation
    foreign_corporation: ForeignCorporationInfo = Field(
        default_factory=ForeignCorporationInfo
    )

    # Shareholder information
    shareholder_info: ShareholderInfo = Field(
        default_factory=ShareholderInfo
    )

    # Filing categories
    filing_categories: List[FilingCategory] = Field(
        default_factory=list,
        description="Filing categories for this Form 5471"
    )

    # Schedules
    schedule_c: Optional[ScheduleC_IncomeStatement] = Field(default=None)
    schedule_e: Optional[ScheduleE_ForeignTaxes] = Field(default=None)
    schedule_f: Optional[ScheduleF_BalanceSheet] = Field(default=None)
    schedule_h: Optional[ScheduleH_EarningsAndProfits] = Field(default=None)
    schedule_i1: Optional[ScheduleI1_GILTI] = Field(default=None)

    # Subpart F income
    subpart_f_income: Optional[SubpartFIncome] = Field(default=None)

    # Pro-rata share calculations
    pro_rata_share_subpart_f: float = Field(default=0.0, ge=0)
    pro_rata_share_gilti: float = Field(default=0.0, ge=0)

    # Previously taxed earnings and profits (PTEP)
    ptep_groups: Dict[str, float] = Field(
        default_factory=dict,
        description="Previously taxed E&P by group"
    )

    def is_cfc(self) -> bool:
        """Determine if foreign corporation is a CFC."""
        return self.foreign_corporation.is_cfc

    def shareholder_ownership_percent(self) -> float:
        """Get shareholder's total ownership percentage."""
        return self.shareholder_info.total_ownership_percent()

    def is_10_percent_shareholder(self) -> bool:
        """Determine if shareholder owns 10% or more."""
        return self.shareholder_ownership_percent() >= self.CFC_OWNERSHIP_THRESHOLD

    def calculate_subpart_f_inclusion(self) -> dict:
        """
        Calculate Subpart F income inclusion for U.S. shareholder.

        U.S. shareholder includes their pro-rata share of CFC's Subpart F
        income in gross income, even if not distributed.
        """
        result = {
            'is_cfc': self.is_cfc(),
            'is_10_percent_shareholder': self.is_10_percent_shareholder(),
            'ownership_percent': self.shareholder_ownership_percent(),
            'subpart_f_applicable': False,
            'gross_subpart_f_income': 0.0,
            'net_subpart_f_income': 0.0,
            'pro_rata_share': 0.0,
            'inclusion_in_income': 0.0,
        }

        if not self.is_cfc() or not self.is_10_percent_shareholder():
            return result

        result['subpart_f_applicable'] = True

        if self.subpart_f_income:
            result['gross_subpart_f_income'] = self.subpart_f_income.gross_subpart_f_income()
            result['net_subpart_f_income'] = self.subpart_f_income.net_subpart_f_income()

            # Pro-rata share based on ownership
            ownership_decimal = self.shareholder_ownership_percent() / 100
            result['pro_rata_share'] = round(
                result['net_subpart_f_income'] * ownership_decimal, 2
            )
            result['inclusion_in_income'] = result['pro_rata_share']

        return result

    def calculate_gilti_inclusion(self) -> dict:
        """
        Calculate GILTI (Global Intangible Low-Taxed Income) inclusion.

        GILTI = Net CFC Tested Income - Net Deemed Tangible Income Return
        """
        result = {
            'is_cfc': self.is_cfc(),
            'is_10_percent_shareholder': self.is_10_percent_shareholder(),
            'gilti_applicable': False,
            'gross_tested_income': 0.0,
            'qbai': 0.0,
            'deemed_tangible_return': 0.0,
            'net_tested_income': 0.0,
            'gilti_before_deduction': 0.0,
            'section_250_deduction': 0.0,
            'net_gilti_inclusion': 0.0,
        }

        if not self.is_cfc() or not self.is_10_percent_shareholder():
            return result

        result['gilti_applicable'] = True

        if self.schedule_i1:
            result['gross_tested_income'] = self.schedule_i1.gross_tested_income
            result['qbai'] = self.schedule_i1.qbai_at_year_end
            result['deemed_tangible_return'] = self.schedule_i1.deemed_tangible_income_return()
            result['net_tested_income'] = self.schedule_i1.net_tested_income()

            # GILTI = Net Tested Income - Deemed Tangible Return
            gilti = max(0.0, result['net_tested_income'] - result['deemed_tangible_return'])

            # Pro-rata share
            ownership_decimal = self.shareholder_ownership_percent() / 100
            result['gilti_before_deduction'] = round(gilti * ownership_decimal, 2)

            # Section 250 deduction (50% for C-corps, 37.5% for 2026+)
            # For individuals, there's no Section 250 deduction
            result['section_250_deduction'] = 0.0  # Individuals don't get this

            result['net_gilti_inclusion'] = result['gilti_before_deduction']

        return result

    def calculate_form_5471(self) -> dict:
        """
        Complete Form 5471 calculation.

        Returns information return data plus tax impact calculations.
        """
        result = {
            # Identification
            'filer_name': self.filer_name,
            'foreign_corporation_name': self.foreign_corporation.name,
            'country_of_incorporation': self.foreign_corporation.country_of_incorporation,
            'functional_currency': self.foreign_corporation.functional_currency,

            # Classification
            'is_cfc': self.is_cfc(),
            'is_pfic': self.foreign_corporation.is_pfic,
            'filing_categories': [cat.value for cat in self.filing_categories],

            # Ownership
            'direct_ownership': self.shareholder_info.direct_ownership_percent,
            'indirect_ownership': self.shareholder_info.indirect_ownership_percent,
            'total_ownership': self.shareholder_ownership_percent(),
            'is_10_percent_shareholder': self.is_10_percent_shareholder(),

            # Financial data (from schedules)
            'gross_income': 0.0,
            'net_income': 0.0,
            'total_assets': 0.0,
            'total_equity': 0.0,
            'current_ep': 0.0,
            'foreign_taxes_paid': 0.0,

            # Tax inclusions
            'subpart_f_inclusion': {},
            'gilti_inclusion': {},

            # Total income inclusion for U.S. tax
            'total_income_inclusion': 0.0,
            'total_foreign_tax_credit': 0.0,
        }

        # Populate schedule data
        if self.schedule_c:
            result['gross_income'] = self.schedule_c.gross_income()
            result['net_income'] = self.schedule_c.net_income()

        if self.schedule_f:
            result['total_assets'] = self.schedule_f.total_assets()
            result['total_equity'] = self.schedule_f.total_equity()

        if self.schedule_h:
            result['current_ep'] = self.schedule_h.current_ep()

        if self.schedule_e:
            result['foreign_taxes_paid'] = self.schedule_e.total_foreign_taxes()

        # Calculate tax inclusions
        subpart_f = self.calculate_subpart_f_inclusion()
        result['subpart_f_inclusion'] = subpart_f

        gilti = self.calculate_gilti_inclusion()
        result['gilti_inclusion'] = gilti

        # Total income inclusion
        result['total_income_inclusion'] = (
            subpart_f.get('inclusion_in_income', 0.0) +
            gilti.get('net_gilti_inclusion', 0.0)
        )

        return result

    def get_form_5471_summary(self) -> dict:
        """Get summary suitable for tax return integration."""
        calc = self.calculate_form_5471()
        return {
            'foreign_corporation': calc['foreign_corporation_name'],
            'is_cfc': calc['is_cfc'],
            'ownership_percent': calc['total_ownership'],
            'subpart_f_inclusion': calc['subpart_f_inclusion'].get('inclusion_in_income', 0.0),
            'gilti_inclusion': calc['gilti_inclusion'].get('net_gilti_inclusion', 0.0),
            'total_income_inclusion': calc['total_income_inclusion'],
            'foreign_taxes_paid': calc['foreign_taxes_paid'],
        }


def calculate_cfc_income_inclusion(
    ownership_percent: float,
    subpart_f_income: float = 0.0,
    tested_income: float = 0.0,
    qbai: float = 0.0,
) -> dict:
    """
    Convenience function to calculate CFC income inclusion.

    Args:
        ownership_percent: U.S. shareholder's ownership percentage
        subpart_f_income: CFC's net Subpart F income
        tested_income: CFC's tested income for GILTI
        qbai: Qualified Business Asset Investment

    Returns:
        Income inclusion amounts for U.S. shareholder
    """
    result = {
        'ownership_percent': ownership_percent,
        'is_10_percent_shareholder': ownership_percent >= 10.0,
        'subpart_f_pro_rata': 0.0,
        'gilti_pro_rata': 0.0,
        'total_inclusion': 0.0,
    }

    if ownership_percent < 10.0:
        return result

    ownership_decimal = ownership_percent / 100

    # Subpart F inclusion
    result['subpart_f_pro_rata'] = round(subpart_f_income * ownership_decimal, 2)

    # GILTI inclusion
    deemed_tangible_return = qbai * 0.10
    gilti = max(0.0, tested_income - deemed_tangible_return)
    result['gilti_pro_rata'] = round(gilti * ownership_decimal, 2)

    result['total_inclusion'] = result['subpart_f_pro_rata'] + result['gilti_pro_rata']

    return result
