"""
Form 3115 - Application for Change in Accounting Method

Complete IRS Form 3115 implementation for accounting method changes:

Key concepts:
- Overall accounting method changes (cash to accrual, etc.)
- Inventory method changes
- Depreciation method changes
- Revenue/expense recognition timing changes

Section 481(a) Adjustment:
- Required to prevent income duplications/omissions when changing methods
- Positive adjustment: Increases taxable income
- Negative adjustment: Decreases taxable income

Automatic vs. Non-Automatic Changes:
- Automatic: Listed in Rev. Proc. 2023-34, no IRS consent needed, no user fee
- Non-Automatic: Requires advance IRS consent and user fee

Spread Period (IRC Section 481(a)):
- Negative adjustment: Taken entirely in year of change
- Positive adjustment: Spread over 4 years (25% per year)
- Small positive adjustment (<$50,000): May elect 1-year recognition

Designated Change Numbers (DCN):
- Each automatic change has a specific DCN
- Examples: DCN 7 (cash to accrual), DCN 184 (depreciation)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field, model_validator
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class ChangeType(str, Enum):
    """Type of accounting method change."""
    AUTOMATIC = "automatic"  # Listed in Rev. Proc., no IRS consent needed
    NON_AUTOMATIC = "non_automatic"  # Requires IRS consent and user fee


class AccountingMethodCategory(str, Enum):
    """Categories of accounting method changes."""
    OVERALL_METHOD = "overall_method"  # Cash/accrual overall method
    INVENTORY = "inventory"  # Inventory valuation methods
    DEPRECIATION = "depreciation"  # Depreciation/amortization
    REVENUE_RECOGNITION = "revenue_recognition"  # Timing of income
    EXPENSE_RECOGNITION = "expense_recognition"  # Timing of deductions
    BAD_DEBTS = "bad_debts"  # Bad debt methods
    LONG_TERM_CONTRACTS = "long_term_contracts"  # Contract accounting
    CAPITALIZATION = "capitalization"  # Sec. 263A UNICAP
    OTHER = "other"


class OverallMethod(str, Enum):
    """Overall accounting methods."""
    CASH = "cash"  # Cash receipts and disbursements
    ACCRUAL = "accrual"  # Accrual method
    HYBRID = "hybrid"  # Combination of cash and accrual


class InventoryMethod(str, Enum):
    """Inventory valuation methods."""
    FIFO = "fifo"  # First-in, first-out
    LIFO = "lifo"  # Last-in, first-out
    AVERAGE_COST = "average_cost"  # Weighted average
    SPECIFIC_ID = "specific_id"  # Specific identification
    LOWER_COST_MARKET = "lower_cost_market"  # Lower of cost or market
    RETAIL = "retail"  # Retail method


class DepreciationMethod(str, Enum):
    """Depreciation methods."""
    STRAIGHT_LINE = "straight_line"
    MACRS_GDS = "macrs_gds"  # General Depreciation System
    MACRS_ADS = "macrs_ads"  # Alternative Depreciation System
    DECLINING_BALANCE_150 = "declining_balance_150"  # 150% DB
    DECLINING_BALANCE_200 = "declining_balance_200"  # 200% DB
    UNITS_OF_PRODUCTION = "units_of_production"
    SECTION_179 = "section_179"
    BONUS_DEPRECIATION = "bonus_depreciation"


class FilingMethod(str, Enum):
    """Method of filing Form 3115."""
    WITH_RETURN = "with_return"  # Filed with tax return
    DUPLICATE_COPY = "duplicate_copy"  # National office copy
    ADVANCE_CONSENT = "advance_consent"  # Non-automatic request


class EntityType(str, Enum):
    """Type of entity filing."""
    INDIVIDUAL = "individual"
    CORPORATION = "corporation"
    S_CORPORATION = "s_corporation"
    PARTNERSHIP = "partnership"
    TRUST = "trust"
    ESTATE = "estate"
    TAX_EXEMPT = "tax_exempt"


class DesignatedChangeNumber(BaseModel):
    """
    Designated Change Number (DCN) for automatic changes.

    Each automatic accounting method change has a specific DCN
    listed in the current Revenue Procedure.
    """
    dcn: int = Field(description="Designated Change Number")
    description: str = Field(description="Description of the change")
    category: AccountingMethodCategory = Field(description="Category of change")
    spread_period: int = Field(default=4, description="Default spread period for positive 481(a)")

    # Common DCN numbers (Rev. Proc. 2023-34 and updates)
    @classmethod
    def cash_to_accrual(cls) -> "DesignatedChangeNumber":
        """DCN 7: Change from cash to accrual method."""
        return cls(
            dcn=7,
            description="Change from overall cash method to overall accrual method",
            category=AccountingMethodCategory.OVERALL_METHOD
        )

    @classmethod
    def accrual_to_cash(cls) -> "DesignatedChangeNumber":
        """DCN 8: Change from accrual to cash method (qualifying small business)."""
        return cls(
            dcn=8,
            description="Change from overall accrual method to overall cash method",
            category=AccountingMethodCategory.OVERALL_METHOD
        )

    @classmethod
    def depreciation_change(cls) -> "DesignatedChangeNumber":
        """DCN 7: Depreciation method change."""
        return cls(
            dcn=184,
            description="Change in depreciation method, recovery period, or convention",
            category=AccountingMethodCategory.DEPRECIATION
        )

    @classmethod
    def inventory_capitalization(cls) -> "DesignatedChangeNumber":
        """DCN 12: UNICAP method change."""
        return cls(
            dcn=12,
            description="Change to comply with Section 263A (UNICAP)",
            category=AccountingMethodCategory.CAPITALIZATION
        )

    @classmethod
    def bad_debt_reserve_to_direct(cls) -> "DesignatedChangeNumber":
        """DCN 166: Bad debt method change."""
        return cls(
            dcn=166,
            description="Change from reserve method to direct write-off for bad debts",
            category=AccountingMethodCategory.BAD_DEBTS
        )

    @classmethod
    def advance_payment_deferral(cls) -> "DesignatedChangeNumber":
        """DCN 21: Advance payment deferral."""
        return cls(
            dcn=21,
            description="Change to deferral method for advance payments (Rev. Proc. 2004-34)",
            category=AccountingMethodCategory.REVENUE_RECOGNITION
        )

    @classmethod
    def prepaid_expense(cls) -> "DesignatedChangeNumber":
        """DCN 15: Prepaid expense treatment."""
        return cls(
            dcn=15,
            description="Change in treatment of prepaid expenses",
            category=AccountingMethodCategory.EXPENSE_RECOGNITION
        )


class Section481aAdjustment(BaseModel):
    """
    Section 481(a) Adjustment Calculation

    The 481(a) adjustment ensures that no item of income or deduction
    is duplicated or omitted when changing accounting methods.
    """
    # Adjustment amount (positive = income, negative = deduction)
    gross_adjustment: float = Field(
        default=0.0,
        description="Total Section 481(a) adjustment before spread"
    )

    # Year of change
    year_of_change: int = Field(default=2025, description="Tax year of change")

    # Spread election
    elect_one_year: bool = Field(
        default=False,
        description="Elect to recognize entire positive adjustment in year of change"
    )

    # Small taxpayer threshold for 1-year recognition
    small_adjustment_threshold: float = Field(
        default=50000.0,
        description="Threshold for electing 1-year recognition"
    )

    @computed_field
    @property
    def is_positive(self) -> bool:
        """Check if adjustment increases income."""
        return self.gross_adjustment > 0

    @computed_field
    @property
    def is_negative(self) -> bool:
        """Check if adjustment decreases income."""
        return self.gross_adjustment < 0

    @computed_field
    @property
    def spread_period(self) -> int:
        """
        Determine spread period for 481(a) adjustment.

        Rules:
        - Negative adjustment: 1 year (year of change)
        - Positive adjustment: 4 years (unless small or elected 1-year)
        """
        if self.is_negative:
            return 1

        if self.elect_one_year:
            return 1

        if abs(self.gross_adjustment) <= self.small_adjustment_threshold:
            # Small positive adjustments can be taken in 1 year
            return 1

        return 4

    @computed_field
    @property
    def annual_adjustment(self) -> float:
        """Amount of adjustment to recognize each year."""
        if self.spread_period == 0:
            return 0.0
        return float(money(self.gross_adjustment / self.spread_period))

    def get_adjustment_for_year(self, tax_year: int) -> float:
        """
        Get the 481(a) adjustment amount for a specific tax year.

        Args:
            tax_year: The tax year to get adjustment for

        Returns:
            Adjustment amount for that year (0 if outside spread period)
        """
        if tax_year < self.year_of_change:
            return 0.0

        year_number = tax_year - self.year_of_change + 1

        if year_number > self.spread_period:
            return 0.0

        return self.annual_adjustment

    def get_spread_schedule(self) -> Dict[int, float]:
        """Get the full spread schedule for the 481(a) adjustment."""
        schedule = {}
        for year_offset in range(self.spread_period):
            year = self.year_of_change + year_offset
            schedule[year] = self.annual_adjustment
        return schedule


class Form3115PartI(BaseModel):
    """
    Form 3115 Part I - Information For Automatic Change Request

    Basic information about the applicant and the change.
    """
    # Applicant information
    applicant_name: str = Field(description="Name of applicant")
    applicant_ein: Optional[str] = Field(None, description="Employer Identification Number")
    applicant_ssn: Optional[str] = Field(None, description="Social Security Number (individuals)")

    entity_type: EntityType = Field(
        default=EntityType.INDIVIDUAL,
        description="Type of entity"
    )

    # Contact information
    contact_name: str = Field(default="", description="Contact person name")
    contact_phone: str = Field(default="", description="Contact phone number")

    # Principal business activity
    principal_business: str = Field(default="", description="Principal business activity")
    naics_code: Optional[str] = Field(None, description="NAICS code")

    # Year of change
    tax_year_of_change_begin: date = Field(description="Beginning of tax year of change")
    tax_year_of_change_end: date = Field(description="End of tax year of change")

    @computed_field
    @property
    def tax_year(self) -> int:
        """Tax year of change."""
        return self.tax_year_of_change_end.year


class Form3115PartII(BaseModel):
    """
    Form 3115 Part II - Information For All Requests

    Details about the accounting method change.
    """
    # Change details
    change_type: ChangeType = Field(
        default=ChangeType.AUTOMATIC,
        description="Automatic or non-automatic change"
    )

    dcn_number: Optional[int] = Field(
        None,
        description="Designated Change Number (for automatic changes)"
    )

    category: AccountingMethodCategory = Field(
        default=AccountingMethodCategory.OVERALL_METHOD,
        description="Category of accounting method change"
    )

    # Present method
    present_method_description: str = Field(
        default="",
        description="Description of present accounting method"
    )

    # Proposed method
    proposed_method_description: str = Field(
        default="",
        description="Description of proposed accounting method"
    )

    # Item(s) being changed
    items_being_changed: str = Field(
        default="",
        description="Description of item(s) being changed"
    )

    # Has this change been made before?
    change_made_within_5_years: bool = Field(
        default=False,
        description="Has this change been made within the last 5 years?"
    )

    # Is the change for a trade or business?
    is_trade_or_business: bool = Field(
        default=True,
        description="Is the change for a trade or business activity?"
    )

    # IRS audit status
    under_examination: bool = Field(
        default=False,
        description="Is the applicant under IRS examination?"
    )

    # Appeals or litigation
    in_appeals: bool = Field(
        default=False,
        description="Is there a pending appeal for any tax year?"
    )

    in_litigation: bool = Field(
        default=False,
        description="Is there pending litigation for any tax year?"
    )


class Form3115PartIV(BaseModel):
    """
    Form 3115 Part IV - Section 481(a) Adjustment

    Calculation and reporting of the 481(a) adjustment.
    """
    # Pre-change method amounts
    income_under_present_method: float = Field(
        default=0.0,
        description="Income/gain under present method"
    )
    deductions_under_present_method: float = Field(
        default=0.0,
        description="Deductions under present method"
    )

    # Post-change method amounts
    income_under_proposed_method: float = Field(
        default=0.0,
        description="Income/gain under proposed method"
    )
    deductions_under_proposed_method: float = Field(
        default=0.0,
        description="Deductions under proposed method"
    )

    @computed_field
    @property
    def net_present_method(self) -> float:
        """Net income under present method."""
        return self.income_under_present_method - self.deductions_under_present_method

    @computed_field
    @property
    def net_proposed_method(self) -> float:
        """Net income under proposed method."""
        return self.income_under_proposed_method - self.deductions_under_proposed_method

    @computed_field
    @property
    def section_481a_adjustment(self) -> float:
        """
        Section 481(a) adjustment amount.

        Calculated as the difference between:
        - What would have been reported under proposed method, and
        - What was actually reported under present method

        Positive = income increase, Negative = income decrease
        """
        return self.net_proposed_method - self.net_present_method


class Form3115ScheduleA(BaseModel):
    """
    Form 3115 Schedule A - Change in Overall Method of Accounting

    For changes between cash and accrual methods.
    """
    # Present overall method
    present_method: OverallMethod = Field(
        default=OverallMethod.CASH,
        description="Present overall accounting method"
    )

    # Proposed overall method
    proposed_method: OverallMethod = Field(
        default=OverallMethod.ACCRUAL,
        description="Proposed overall accounting method"
    )

    # Accounts receivable adjustment
    accounts_receivable: float = Field(
        default=0.0, ge=0,
        description="Accounts receivable at year end"
    )

    # Accounts payable adjustment
    accounts_payable: float = Field(
        default=0.0, ge=0,
        description="Accounts payable at year end"
    )

    # Prepaid expenses
    prepaid_expenses: float = Field(
        default=0.0, ge=0,
        description="Prepaid expenses at year end"
    )

    # Accrued expenses
    accrued_expenses: float = Field(
        default=0.0, ge=0,
        description="Accrued expenses at year end"
    )

    # Deferred revenue
    deferred_revenue: float = Field(
        default=0.0, ge=0,
        description="Deferred/unearned revenue at year end"
    )

    # Inventory adjustment (if applicable)
    inventory_adjustment: float = Field(
        default=0.0,
        description="Inventory adjustment for method change"
    )

    @computed_field
    @property
    def income_items_adjustment(self) -> float:
        """
        Adjustment for income items (cash to accrual).

        Add: Accounts receivable (income earned but not received)
        Less: Deferred revenue (cash received but not earned)
        """
        if self.present_method == OverallMethod.CASH and self.proposed_method == OverallMethod.ACCRUAL:
            return self.accounts_receivable - self.deferred_revenue
        elif self.present_method == OverallMethod.ACCRUAL and self.proposed_method == OverallMethod.CASH:
            return -(self.accounts_receivable - self.deferred_revenue)
        return 0.0

    @computed_field
    @property
    def expense_items_adjustment(self) -> float:
        """
        Adjustment for expense items (cash to accrual).

        Add: Prepaid expenses (cash paid but not yet deductible)
        Less: Accrued expenses (deductible but not yet paid)
        """
        if self.present_method == OverallMethod.CASH and self.proposed_method == OverallMethod.ACCRUAL:
            return self.prepaid_expenses - self.accrued_expenses
        elif self.present_method == OverallMethod.ACCRUAL and self.proposed_method == OverallMethod.CASH:
            return -(self.prepaid_expenses - self.accrued_expenses)
        return 0.0

    @computed_field
    @property
    def net_481a_adjustment(self) -> float:
        """
        Net Section 481(a) adjustment for overall method change.

        For cash to accrual:
        + Accounts receivable (add income)
        - Deferred revenue (reduce income)
        - Accrued expenses (add deductions)
        + Prepaid expenses (reduce deductions)
        """
        return self.income_items_adjustment - self.expense_items_adjustment + self.inventory_adjustment


class Form3115ScheduleD(BaseModel):
    """
    Form 3115 Schedule D - Change in Treatment of Depreciation

    For changes in depreciation method, recovery period, or convention.
    """
    # Asset information
    asset_description: str = Field(default="", description="Description of asset(s)")
    date_placed_in_service: Optional[date] = Field(None, description="Date placed in service")

    # Present depreciation method
    present_depreciation_method: DepreciationMethod = Field(
        default=DepreciationMethod.MACRS_GDS,
        description="Present depreciation method"
    )
    present_recovery_period: int = Field(
        default=0, ge=0,
        description="Present recovery period (years)"
    )
    present_convention: str = Field(
        default="half_year",
        description="Present convention (half_year, mid_month, mid_quarter)"
    )

    # Proposed depreciation method
    proposed_depreciation_method: DepreciationMethod = Field(
        default=DepreciationMethod.MACRS_GDS,
        description="Proposed depreciation method"
    )
    proposed_recovery_period: int = Field(
        default=0, ge=0,
        description="Proposed recovery period (years)"
    )
    proposed_convention: str = Field(
        default="half_year",
        description="Proposed convention"
    )

    # Basis and depreciation information
    original_basis: float = Field(
        default=0.0, ge=0,
        description="Original basis of asset"
    )
    depreciation_claimed: float = Field(
        default=0.0, ge=0,
        description="Total depreciation claimed under present method"
    )
    depreciation_allowable: float = Field(
        default=0.0, ge=0,
        description="Total depreciation allowable under proposed method"
    )

    @computed_field
    @property
    def section_481a_adjustment(self) -> float:
        """
        Section 481(a) adjustment for depreciation change.

        Adjustment = Depreciation claimed - Depreciation allowable
        Positive = Over-depreciated (income adjustment)
        Negative = Under-depreciated (deduction adjustment)
        """
        return self.depreciation_claimed - self.depreciation_allowable

    @computed_field
    @property
    def adjusted_basis_present(self) -> float:
        """Adjusted basis under present method."""
        return self.original_basis - self.depreciation_claimed

    @computed_field
    @property
    def adjusted_basis_proposed(self) -> float:
        """Adjusted basis under proposed method."""
        return self.original_basis - self.depreciation_allowable


class Form3115ScheduleE(BaseModel):
    """
    Form 3115 Schedule E - Change in Inventory Method

    For changes in inventory valuation or costing methods.
    """
    # Present inventory method
    present_method: InventoryMethod = Field(
        default=InventoryMethod.FIFO,
        description="Present inventory method"
    )

    # Proposed inventory method
    proposed_method: InventoryMethod = Field(
        default=InventoryMethod.FIFO,
        description="Proposed inventory method"
    )

    # Inventory values
    beginning_inventory_present: float = Field(
        default=0.0, ge=0,
        description="Beginning inventory under present method"
    )
    ending_inventory_present: float = Field(
        default=0.0, ge=0,
        description="Ending inventory under present method"
    )

    beginning_inventory_proposed: float = Field(
        default=0.0, ge=0,
        description="Beginning inventory under proposed method"
    )
    ending_inventory_proposed: float = Field(
        default=0.0, ge=0,
        description="Ending inventory under proposed method"
    )

    # UNICAP adjustment (Section 263A)
    unicap_adjustment: float = Field(
        default=0.0,
        description="Section 263A UNICAP adjustment"
    )

    @computed_field
    @property
    def inventory_adjustment(self) -> float:
        """
        Inventory method change adjustment.

        Based on difference in ending inventory values.
        """
        return self.ending_inventory_proposed - self.ending_inventory_present

    @computed_field
    @property
    def section_481a_adjustment(self) -> float:
        """Total Section 481(a) adjustment for inventory change."""
        return self.inventory_adjustment + self.unicap_adjustment


class Form3115(BaseModel):
    """
    IRS Form 3115 - Application for Change in Accounting Method

    Complete form for requesting accounting method changes.

    Usage:
        # Cash to accrual method change
        form = Form3115(
            tax_year=2025,
            change_type=ChangeType.AUTOMATIC,
            dcn=DesignatedChangeNumber.cash_to_accrual(),
            schedule_a=Form3115ScheduleA(
                present_method=OverallMethod.CASH,
                proposed_method=OverallMethod.ACCRUAL,
                accounts_receivable=50000,
                accrued_expenses=30000
            )
        )

        print(f"481(a) adjustment: ${form.section_481a_adjustment}")
        print(f"Spread period: {form.spread_period} years")
    """
    tax_year: int = Field(default=2025, description="Tax year of change")

    # Change type and identification
    change_type: ChangeType = Field(
        default=ChangeType.AUTOMATIC,
        description="Automatic or non-automatic change"
    )

    dcn: Optional[DesignatedChangeNumber] = Field(
        None,
        description="Designated Change Number for automatic changes"
    )

    # Form sections
    part_i: Optional[Form3115PartI] = Field(
        None,
        description="Part I - Applicant Information"
    )

    part_ii: Optional[Form3115PartII] = Field(
        None,
        description="Part II - Change Details"
    )

    part_iv: Optional[Form3115PartIV] = Field(
        None,
        description="Part IV - Section 481(a) Adjustment"
    )

    # Schedules (use applicable schedule based on change type)
    schedule_a: Optional[Form3115ScheduleA] = Field(
        None,
        description="Schedule A - Overall Method Change"
    )

    schedule_d: Optional[Form3115ScheduleD] = Field(
        None,
        description="Schedule D - Depreciation Change"
    )

    schedule_e: Optional[Form3115ScheduleE] = Field(
        None,
        description="Schedule E - Inventory Method Change"
    )

    # Filing information
    filing_method: FilingMethod = Field(
        default=FilingMethod.WITH_RETURN,
        description="Method of filing"
    )

    # User fee (for non-automatic changes)
    user_fee_paid: float = Field(
        default=0.0, ge=0,
        description="User fee paid (non-automatic changes)"
    )

    # Elections
    elect_one_year_spread: bool = Field(
        default=False,
        description="Elect to recognize entire positive 481(a) in year of change"
    )

    # Audit protection
    audit_protection_applies: bool = Field(
        default=True,
        description="Audit protection applies to automatic changes"
    )

    @computed_field
    @property
    def is_automatic(self) -> bool:
        """Check if this is an automatic change."""
        return self.change_type == ChangeType.AUTOMATIC

    @computed_field
    @property
    def category(self) -> AccountingMethodCategory:
        """Get the category of change."""
        if self.dcn:
            return self.dcn.category
        if self.schedule_a:
            return AccountingMethodCategory.OVERALL_METHOD
        if self.schedule_d:
            return AccountingMethodCategory.DEPRECIATION
        if self.schedule_e:
            return AccountingMethodCategory.INVENTORY
        return AccountingMethodCategory.OTHER

    @computed_field
    @property
    def section_481a_adjustment(self) -> float:
        """
        Calculate the total Section 481(a) adjustment.

        Sources:
        - Part IV explicit calculation
        - Schedule A (overall method)
        - Schedule D (depreciation)
        - Schedule E (inventory)
        """
        total = 0.0

        if self.part_iv:
            total += self.part_iv.section_481a_adjustment

        if self.schedule_a:
            total += self.schedule_a.net_481a_adjustment

        if self.schedule_d:
            total += self.schedule_d.section_481a_adjustment

        if self.schedule_e:
            total += self.schedule_e.section_481a_adjustment

        return float(money(total))

    @computed_field
    @property
    def is_positive_adjustment(self) -> bool:
        """Check if 481(a) adjustment is positive (income increase)."""
        return self.section_481a_adjustment > 0

    @computed_field
    @property
    def is_negative_adjustment(self) -> bool:
        """Check if 481(a) adjustment is negative (income decrease)."""
        return self.section_481a_adjustment < 0

    @computed_field
    @property
    def spread_period(self) -> int:
        """
        Determine the spread period for the 481(a) adjustment.

        Rules:
        - Negative: 1 year
        - Positive <=50,000: 1 year (or elect)
        - Positive >50,000: 4 years (unless elect 1-year)
        """
        if self.is_negative_adjustment:
            return 1

        if self.elect_one_year_spread:
            return 1

        if abs(self.section_481a_adjustment) <= 50000:
            return 1

        return 4

    @computed_field
    @property
    def annual_481a_amount(self) -> float:
        """Annual amount of 481(a) adjustment to recognize."""
        if self.spread_period == 0:
            return 0.0
        return float(money(self.section_481a_adjustment / self.spread_period))

    def get_481a_schedule(self) -> Dict[int, float]:
        """Get the full 481(a) spread schedule by year."""
        schedule = {}
        for year_offset in range(self.spread_period):
            year = self.tax_year + year_offset
            schedule[year] = self.annual_481a_amount
        return schedule

    @computed_field
    @property
    def user_fee_required(self) -> float:
        """User fee required for non-automatic changes (2025 rates)."""
        if self.is_automatic:
            return 0.0
        # Standard user fee for Form 3115 (Rev. Proc. 2024-1)
        return 12500.0  # May vary based on gross income

    @computed_field
    @property
    def requires_national_office_copy(self) -> bool:
        """Check if national office copy is required."""
        # Automatic changes require duplicate copy to national office
        return self.is_automatic

    def get_present_method_description(self) -> str:
        """Get description of present method."""
        if self.schedule_a:
            return f"Overall {self.schedule_a.present_method.value} method"
        if self.schedule_d:
            return f"{self.schedule_d.present_depreciation_method.value} depreciation"
        if self.schedule_e:
            return f"{self.schedule_e.present_method.value} inventory method"
        if self.part_ii:
            return self.part_ii.present_method_description
        return "See attached"

    def get_proposed_method_description(self) -> str:
        """Get description of proposed method."""
        if self.schedule_a:
            return f"Overall {self.schedule_a.proposed_method.value} method"
        if self.schedule_d:
            return f"{self.schedule_d.proposed_depreciation_method.value} depreciation"
        if self.schedule_e:
            return f"{self.schedule_e.proposed_method.value} inventory method"
        if self.part_ii:
            return self.part_ii.proposed_method_description
        return "See attached"

    def to_dict(self) -> Dict[str, Any]:
        """Convert form to dictionary for reporting."""
        result = {
            "tax_year": self.tax_year,
            "change_type": self.change_type.value,
            "is_automatic": self.is_automatic,
            "category": self.category.value,

            "present_method": self.get_present_method_description(),
            "proposed_method": self.get_proposed_method_description(),

            "section_481a_adjustment": self.section_481a_adjustment,
            "is_positive_adjustment": self.is_positive_adjustment,
            "spread_period": self.spread_period,
            "annual_481a_amount": self.annual_481a_amount,
            "spread_schedule": self.get_481a_schedule(),

            "user_fee_required": self.user_fee_required,
            "audit_protection_applies": self.audit_protection_applies,
            "requires_national_office_copy": self.requires_national_office_copy
        }

        if self.dcn:
            result["dcn"] = self.dcn.dcn
            result["dcn_description"] = self.dcn.description

        return result

    def to_form_1040(self) -> Dict[str, float]:
        """Generate adjustment amounts for tax return."""
        adjustment = self.annual_481a_amount

        return {
            "section_481a_adjustment": adjustment,
            "other_income_481a": adjustment if adjustment > 0 else 0,
            "other_deduction_481a": abs(adjustment) if adjustment < 0 else 0
        }


def calculate_cash_to_accrual_adjustment(
    accounts_receivable: float,
    accounts_payable: float = 0.0,
    prepaid_expenses: float = 0.0,
    accrued_expenses: float = 0.0,
    deferred_revenue: float = 0.0,
    inventory_adjustment: float = 0.0
) -> Dict[str, Any]:
    """
    Calculate Section 481(a) adjustment for cash to accrual conversion.

    Args:
        accounts_receivable: Outstanding A/R at year end
        accounts_payable: Outstanding A/P at year end (not directly used in 481a)
        prepaid_expenses: Prepaid expenses at year end
        accrued_expenses: Accrued expenses at year end
        deferred_revenue: Deferred/unearned revenue at year end
        inventory_adjustment: Any inventory-related adjustment

    Returns:
        Dictionary with adjustment details
    """
    schedule_a = Form3115ScheduleA(
        present_method=OverallMethod.CASH,
        proposed_method=OverallMethod.ACCRUAL,
        accounts_receivable=accounts_receivable,
        accounts_payable=accounts_payable,
        prepaid_expenses=prepaid_expenses,
        accrued_expenses=accrued_expenses,
        deferred_revenue=deferred_revenue,
        inventory_adjustment=inventory_adjustment
    )

    form = Form3115(
        tax_year=2025,
        change_type=ChangeType.AUTOMATIC,
        dcn=DesignatedChangeNumber.cash_to_accrual(),
        schedule_a=schedule_a
    )

    return form.to_dict()


def calculate_depreciation_adjustment(
    original_basis: float,
    depreciation_claimed: float,
    depreciation_allowable: float,
    asset_description: str = "Fixed assets"
) -> Dict[str, Any]:
    """
    Calculate Section 481(a) adjustment for depreciation method change.

    Args:
        original_basis: Original cost basis of asset(s)
        depreciation_claimed: Total depreciation claimed under present method
        depreciation_allowable: Total depreciation allowable under proposed method
        asset_description: Description of asset(s)

    Returns:
        Dictionary with adjustment details
    """
    schedule_d = Form3115ScheduleD(
        asset_description=asset_description,
        original_basis=original_basis,
        depreciation_claimed=depreciation_claimed,
        depreciation_allowable=depreciation_allowable
    )

    form = Form3115(
        tax_year=2025,
        change_type=ChangeType.AUTOMATIC,
        dcn=DesignatedChangeNumber.depreciation_change(),
        schedule_d=schedule_d
    )

    return form.to_dict()


def calculate_inventory_adjustment(
    ending_inventory_present: float,
    ending_inventory_proposed: float,
    present_method: InventoryMethod = InventoryMethod.FIFO,
    proposed_method: InventoryMethod = InventoryMethod.AVERAGE_COST,
    unicap_adjustment: float = 0.0
) -> Dict[str, Any]:
    """
    Calculate Section 481(a) adjustment for inventory method change.

    Args:
        ending_inventory_present: Ending inventory under present method
        ending_inventory_proposed: Ending inventory under proposed method
        present_method: Current inventory method
        proposed_method: Proposed inventory method
        unicap_adjustment: Any Section 263A adjustment

    Returns:
        Dictionary with adjustment details
    """
    schedule_e = Form3115ScheduleE(
        present_method=present_method,
        proposed_method=proposed_method,
        ending_inventory_present=ending_inventory_present,
        ending_inventory_proposed=ending_inventory_proposed,
        unicap_adjustment=unicap_adjustment
    )

    form = Form3115(
        tax_year=2025,
        change_type=ChangeType.AUTOMATIC,
        schedule_e=schedule_e
    )

    return form.to_dict()
