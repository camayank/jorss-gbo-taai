from typing import Optional, List, Tuple
from pydantic import BaseModel, Field
from enum import Enum

from models.schedule_c import ScheduleCBusiness
from models.form_8949 import SecuritiesPortfolio
from models.form_8889 import Form8889, HSAInfo, HSACoverageType
from models.form_8606 import Form8606, IRAInfo, IRAType
from models.form_5329 import Form5329, EarlyDistributionExceptionCode
from models.form_4797 import Form4797, BusinessPropertySale, PropertyType, Section1231LookbackLoss
from models.form_6252 import Form6252, InstallmentObligation, InstallmentPayment
from models.form_8582 import Form8582, PassiveActivity, RealEstateProfessional, ActivityType
from models.form_6251 import Form6251, ISOExercise, PrivateActivityBond, DepreciationAdjustment
from models.form_8801 import Form8801, PriorYearAMTDetail, MTCCarryforward
from models.form_1116 import Form1116, Form1116Category, ForeignIncomeCategory, FTCCarryover
from models.form_8615 import Form8615, ParentTaxInfo, ParentFilingStatus
from models.form_2555 import Form2555, QualificationTest, ForeignHousingExpenses
from models.schedule_h import ScheduleH, HouseholdEmployee, HouseholdEmployeeType
from models.form_4952 import Form4952, InvestmentIncomeElection
from models.form_5471 import Form5471, FilingCategory, ForeignCorporationInfo
from models.form_1040x import Form1040X, AmendmentReason
from models.schedule_a import ScheduleA
from models.schedule_b import ScheduleB
from models.schedule_d import ScheduleD
from models.schedule_e import ScheduleE
from models.schedule_f import ScheduleF
from models.form_6781 import Form6781
from models.form_8814 import Form8814
from models.form_8995 import Form8995


class IncomeSource(str, Enum):
    """Types of income sources"""
    W2_WAGES = "w2_wages"
    SELF_EMPLOYMENT = "self_employment"
    INTEREST = "interest"
    DIVIDENDS = "dividends"
    RENTAL = "rental"
    RETIREMENT = "retirement"
    UNEMPLOYMENT = "unemployment"
    SOCIAL_SECURITY = "social_security"
    GAMBLING = "gambling"
    VIRTUAL_CURRENCY = "virtual_currency"
    K1_INCOME = "k1_income"
    OTHER = "other"


class GamblingType(str, Enum):
    """Types of gambling activities for reporting purposes."""
    CASINO = "casino"
    LOTTERY = "lottery"
    HORSE_RACING = "horse_racing"
    POKER = "poker"
    SPORTS_BETTING = "sports_betting"
    FANTASY_SPORTS = "fantasy_sports"
    BINGO = "bingo"
    SLOT_MACHINES = "slot_machines"
    OTHER = "other"


class K1SourceType(str, Enum):
    """Types of K-1 forms."""
    PARTNERSHIP = "partnership"  # Form 1065 Schedule K-1
    S_CORPORATION = "s_corporation"  # Form 1120-S Schedule K-1
    TRUST_ESTATE = "trust_estate"  # Form 1041 Schedule K-1


class ScheduleK1(BaseModel):
    """
    Schedule K-1 pass-through income from Partnerships, S-Corps, or Trusts/Estates.

    K-1 forms report the taxpayer's share of income, deductions, and credits from:
    - Partnerships (Form 1065)
    - S-Corporations (Form 1120-S)
    - Trusts/Estates (Form 1041)

    Each line item flows to a specific place on the individual tax return.
    """
    # Entity information
    k1_type: K1SourceType
    entity_name: str
    entity_ein: Optional[str] = None
    entity_address: Optional[str] = None

    # Ownership/Beneficiary information
    ownership_percentage: float = Field(default=0.0, ge=0, le=100, description="Ownership percentage at year end")
    beginning_capital: float = Field(default=0.0, description="Beginning capital account")
    ending_capital: float = Field(default=0.0, description="Ending capital account")

    # Part III - Partner's/Shareholder's Share of Current Year Income
    # Box 1 - Ordinary business income (loss) - Schedule E Part II
    ordinary_business_income: float = Field(default=0.0, description="Box 1: Ordinary business income (loss)")

    # Box 2 - Net rental real estate income (loss) - Schedule E Part II
    net_rental_real_estate: float = Field(default=0.0, description="Box 2: Net rental real estate income")

    # Box 3 - Other net rental income (loss) - Schedule E Part II
    other_rental_income: float = Field(default=0.0, description="Box 3: Other net rental income")

    # Box 4 - Guaranteed payments (Partnership only) - Schedule E Part II
    guaranteed_payments: float = Field(default=0.0, description="Box 4: Guaranteed payments")

    # Box 5 - Interest income - Schedule B
    interest_income: float = Field(default=0.0, description="Box 5: Interest income")

    # Box 6a - Ordinary dividends - Schedule B
    ordinary_dividends: float = Field(default=0.0, description="Box 6a: Ordinary dividends")

    # Box 6b - Qualified dividends - Schedule B
    qualified_dividends: float = Field(default=0.0, description="Box 6b: Qualified dividends")

    # Box 7 - Royalties - Schedule E Part I
    royalties: float = Field(default=0.0, description="Box 7: Royalties")

    # Box 8 - Net short-term capital gain (loss) - Schedule D
    net_short_term_capital_gain: float = Field(default=0.0, description="Box 8: Net short-term capital gain (loss)")

    # Box 9a - Net long-term capital gain (loss) - Schedule D
    net_long_term_capital_gain: float = Field(default=0.0, description="Box 9a: Net long-term capital gain (loss)")

    # Box 9b - Collectibles (28%) gain - Schedule D
    collectibles_gain: float = Field(default=0.0, description="Box 9b: Collectibles (28%) gain")

    # Box 9c - Unrecaptured section 1250 gain
    unrecaptured_1250_gain: float = Field(default=0.0, description="Box 9c: Unrecaptured section 1250 gain")

    # Box 10 - Net section 1231 gain (loss) - Form 4797
    net_section_1231_gain: float = Field(default=0.0, description="Box 10: Net section 1231 gain (loss)")

    # Box 11 - Other income (loss) - See instructions for placement
    other_income: float = Field(default=0.0, description="Box 11: Other income (loss)")

    # Section 199A (QBI) Information
    # Box 17 codes for QBI deduction
    qbi_ordinary_income: float = Field(default=0.0, description="Section 199A qualified business income")
    w2_wages_for_qbi: float = Field(default=0.0, description="W-2 wages for QBI limitation")
    ubia_for_qbi: float = Field(default=0.0, description="UBIA of qualified property for QBI")
    is_sstb: bool = Field(default=False, description="Specified Service Trade or Business")

    # Credits (Box 13-15)
    foreign_tax_paid: float = Field(default=0.0, description="Box 16: Foreign taxes paid/accrued")
    low_income_housing_credit: float = Field(default=0.0, description="Low-income housing credit")
    rehabilitation_credit: float = Field(default=0.0, description="Rehabilitation credit")
    other_credits: float = Field(default=0.0, description="Other credits")

    # Self-Employment (Partnership only)
    # Box 14 - Self-employment earnings (loss)
    self_employment_earnings: float = Field(default=0.0, description="Box 14: Self-employment earnings")

    # Distribution information
    distributions: float = Field(default=0.0, ge=0, description="Total distributions received")

    # At-risk and passive activity information
    at_risk_amount: Optional[float] = Field(None, description="At-risk amount at year end")
    is_passive_activity: bool = Field(default=True, description="Whether this is a passive activity")
    material_participation_hours: float = Field(default=0.0, ge=0, description="Hours of material participation")

    def get_total_income(self) -> float:
        """Calculate total income from this K-1."""
        return (
            self.ordinary_business_income +
            self.net_rental_real_estate +
            self.other_rental_income +
            self.guaranteed_payments +
            self.interest_income +
            self.ordinary_dividends +
            self.royalties +
            self.net_short_term_capital_gain +
            self.net_long_term_capital_gain +
            self.net_section_1231_gain +
            self.other_income
        )

    def get_ordinary_income(self) -> float:
        """Get ordinary income components (taxed at ordinary rates)."""
        return (
            self.ordinary_business_income +
            self.guaranteed_payments +
            self.interest_income +
            (self.ordinary_dividends - self.qualified_dividends) +  # Non-qualified dividends
            self.royalties +
            self.net_short_term_capital_gain +
            self.other_income
        )

    def get_preferential_income(self) -> float:
        """Get income taxed at preferential rates."""
        return (
            self.qualified_dividends +
            self.net_long_term_capital_gain +
            self.net_section_1231_gain
        )


class VirtualCurrencyTransactionType(str, Enum):
    """Types of virtual currency transactions for tax reporting."""
    PURCHASE = "purchase"  # Acquiring crypto with fiat (not taxable)
    SALE = "sale"  # Selling crypto for fiat (taxable capital gain/loss)
    EXCHANGE = "exchange"  # Trading one crypto for another (taxable)
    MINING = "mining"  # Mining rewards (ordinary income)
    STAKING = "staking"  # Staking rewards (ordinary income)
    AIRDROP = "airdrop"  # Airdrops (ordinary income at FMV)
    HARD_FORK = "hard_fork"  # Hard fork tokens (ordinary income when dominion)
    GIFT_RECEIVED = "gift_received"  # Gift (inherits donor's basis)
    GIFT_GIVEN = "gift_given"  # Gift (not taxable to giver)
    DONATION = "donation"  # Charitable donation (deductible)
    INCOME_PAYMENT = "income_payment"  # Paid in crypto (ordinary income)
    GOODS_SERVICES = "goods_services"  # Purchasing goods/services (taxable)


class CostBasisMethod(str, Enum):
    """Cost basis methods for virtual currency."""
    FIFO = "fifo"  # First In, First Out
    LIFO = "lifo"  # Last In, First Out
    HIFO = "hifo"  # Highest In, First Out
    SPECIFIC_ID = "specific_id"  # Specific Identification
    AVERAGE_COST = "average_cost"  # Average Cost (not always allowed)


class VirtualCurrencyTransaction(BaseModel):
    """
    Virtual currency/digital asset transaction for tax reporting.

    Per IRS Notice 2014-21 and subsequent guidance:
    - Virtual currency is treated as property for tax purposes
    - Sales/exchanges are capital transactions (Form 8949)
    - Mining/staking/airdrops are ordinary income at FMV when received
    - Must report on Form 1040 checkbox if any crypto activity
    """
    transaction_type: VirtualCurrencyTransactionType
    asset_name: str = Field(description="e.g., Bitcoin, Ethereum, etc.")
    asset_symbol: Optional[str] = Field(None, description="e.g., BTC, ETH")

    # Transaction details
    date_acquired: Optional[str] = None  # YYYY-MM-DD
    date_sold: Optional[str] = None  # YYYY-MM-DD for dispositions
    quantity: float = Field(ge=0, description="Amount of cryptocurrency")

    # Values
    cost_basis: float = Field(default=0.0, ge=0, description="Original purchase price in USD")
    proceeds: float = Field(default=0.0, ge=0, description="Sale price or FMV in USD")
    fair_market_value: float = Field(default=0.0, ge=0, description="FMV at time of transaction")

    # Calculated fields
    gain_loss: Optional[float] = None
    is_long_term: bool = Field(default=False, description="Held > 1 year")

    # Tracking
    exchange_name: Optional[str] = None
    transaction_id: Optional[str] = None
    wallet_address: Optional[str] = None
    cost_basis_method: CostBasisMethod = CostBasisMethod.FIFO

    # Form 8949 reporting code
    form_8949_code: Optional[str] = Field(
        None,
        description="A/D=short-term reported on 1099-B, B/E=short-term not reported, C/F=long-term"
    )

    def calculate_gain_loss(self) -> float:
        """Calculate capital gain or loss from the transaction."""
        if self.transaction_type in [
            VirtualCurrencyTransactionType.SALE,
            VirtualCurrencyTransactionType.EXCHANGE,
            VirtualCurrencyTransactionType.GOODS_SERVICES,
        ]:
            return self.proceeds - self.cost_basis
        return 0.0

    def determine_holding_period(self) -> bool:
        """Determine if long-term (held > 1 year)."""
        if not self.date_acquired or not self.date_sold:
            return False
        from datetime import datetime
        acquired = datetime.strptime(self.date_acquired, "%Y-%m-%d")
        sold = datetime.strptime(self.date_sold, "%Y-%m-%d")
        days_held = (sold - acquired).days
        return days_held > 365


class GamblingWinnings(BaseModel):
    """
    Gambling winnings record (W-2G or session tracking).

    Per IRS rules, gambling winnings are reported on Form W-2G when:
    - Slot machines/bingo: $1,200+ (no withholding required)
    - Keno: $1,500+ after deducting wager
    - Poker tournaments: $5,000+ (net of buy-in)
    - Other gambling: $600+ if at least 300x the wager
    - Any winnings subject to backup withholding

    All gambling winnings are taxable regardless of whether a W-2G is issued.
    """
    gambling_type: GamblingType = GamblingType.OTHER
    payer_name: Optional[str] = None
    payer_ein: Optional[str] = None
    gross_winnings: float = Field(ge=0, description="Total gambling winnings")
    federal_tax_withheld: float = Field(default=0.0, ge=0, description="Box 4 of W-2G")
    state_tax_withheld: float = Field(default=0.0, ge=0, description="State tax withheld")
    wager_amount: float = Field(default=0.0, ge=0, description="Amount wagered (for net calculation)")
    date_won: Optional[str] = None
    has_w2g: bool = Field(default=False, description="Whether W-2G was issued")
    session_based: bool = Field(default=False, description="Part of session-based tracking")


class W2Info(BaseModel):
    """W-2 form information"""
    employer_name: str
    employer_ein: Optional[str] = None
    wages: float = Field(ge=0, description="Box 1: Wages, tips, other compensation")
    federal_tax_withheld: float = Field(ge=0, description="Box 2: Federal income tax withheld")
    social_security_wages: Optional[float] = Field(None, ge=0, description="Box 3")
    social_security_tax_withheld: Optional[float] = Field(None, ge=0, description="Box 4")
    medicare_wages: Optional[float] = Field(None, ge=0, description="Box 5")
    medicare_tax_withheld: Optional[float] = Field(None, ge=0, description="Box 6")
    state_wages: Optional[float] = Field(None, ge=0, description="State wages")
    state_tax_withheld: Optional[float] = Field(None, ge=0, description="State tax withheld")

    # Box 12 items (selected codes)
    employer_hsa_contribution: float = Field(
        default=0.0, ge=0,
        description="Box 12 code W: Employer contributions to HSA"
    )
    retirement_plan_contributions: float = Field(
        default=0.0, ge=0,
        description="Box 12 code D/E/etc: Elective deferrals to retirement plans"
    )


class Form1099Info(BaseModel):
    """1099 form information (various types)"""
    payer_name: str
    payer_tin: Optional[str] = None
    form_type: str = Field(default="1099-MISC", description="1099-MISC, 1099-INT, 1099-DIV, etc.")
    amount: float = Field(ge=0)
    description: Optional[str] = None


class MACRSPropertyClass(str, Enum):
    """
    MACRS Property Classes (IRC Section 168) - Recovery Periods.

    Each class determines the number of years over which an asset is depreciated.
    """
    YEAR_3 = "3"  # Certain manufacturing tools, racehorses
    YEAR_5 = "5"  # Computers, office equipment, autos, trucks, research equipment
    YEAR_7 = "7"  # Office furniture, fixtures, most machinery, single-purpose agricultural structures
    YEAR_10 = "10"  # Water transportation equipment, single-purpose horticultural structures
    YEAR_15 = "15"  # Land improvements (sidewalks, roads, bridges), retail motor fuel outlets
    YEAR_20 = "20"  # Farm buildings, municipal sewers
    YEAR_27_5 = "27.5"  # Residential rental property
    YEAR_39 = "39"  # Nonresidential real property (commercial buildings)


class MACRSConvention(str, Enum):
    """
    MACRS Conventions - Determines how much depreciation in first/last year.
    """
    HALF_YEAR = "half_year"  # Default: Asset placed in service at mid-year
    MID_QUARTER = "mid_quarter"  # If >40% placed in service in Q4
    MID_MONTH = "mid_month"  # Real property (27.5 and 39-year)


class DepreciableAsset(BaseModel):
    """
    Depreciable asset for MACRS depreciation (Form 4562).

    Tracks business/rental assets subject to depreciation including:
    - Property class (recovery period)
    - Convention (half-year, mid-quarter, mid-month)
    - Section 179 expensing election
    - Bonus depreciation election
    - Accumulated depreciation
    """
    # Asset identification
    description: str = Field(description="Description of the asset")
    asset_type: str = Field(default="equipment", description="Type: equipment, vehicle, building, improvement, etc.")

    # Acquisition information
    date_placed_in_service: str = Field(description="Date asset placed in service (YYYY-MM-DD)")
    cost_basis: float = Field(ge=0, description="Original cost or other basis")

    # MACRS classification
    property_class: MACRSPropertyClass = Field(
        default=MACRSPropertyClass.YEAR_7,
        description="MACRS property class (recovery period)"
    )
    convention: MACRSConvention = Field(
        default=MACRSConvention.HALF_YEAR,
        description="MACRS convention for first/last year"
    )

    # Special elections
    section_179_amount: float = Field(
        default=0.0, ge=0,
        description="Section 179 expense elected for this asset"
    )
    bonus_depreciation_amount: float = Field(
        default=0.0, ge=0,
        description="Bonus depreciation elected for this asset"
    )
    opted_out_bonus: bool = Field(
        default=False,
        description="Elected out of bonus depreciation for this property class"
    )

    # Depreciation tracking
    prior_depreciation: float = Field(
        default=0.0, ge=0,
        description="Accumulated depreciation from prior years"
    )
    current_year_depreciation: float = Field(
        default=0.0, ge=0,
        description="Calculated depreciation for current year (computed)"
    )

    # Asset status
    is_listed_property: bool = Field(
        default=False,
        description="Listed property (autos, entertainment, computers for home use)"
    )
    business_use_percentage: float = Field(
        default=100.0, ge=0, le=100,
        description="Percentage of business/investment use (vs. personal)"
    )

    # Disposal information
    disposed: bool = Field(default=False, description="Asset disposed of during year")
    disposal_date: Optional[str] = Field(None, description="Date of disposal (YYYY-MM-DD)")
    disposal_amount: float = Field(default=0.0, ge=0, description="Amount received on disposal")

    def get_depreciable_basis(self) -> float:
        """Calculate the basis for depreciation after Section 179 and bonus."""
        # Start with cost basis adjusted for business use
        adjusted_basis = self.cost_basis * (self.business_use_percentage / 100)
        # Subtract Section 179 expense
        adjusted_basis -= self.section_179_amount
        # Subtract bonus depreciation
        adjusted_basis -= self.bonus_depreciation_amount
        return max(0.0, adjusted_basis)

    def get_remaining_basis(self) -> float:
        """Calculate remaining basis (for gain/loss on disposal)."""
        return max(0.0, self.cost_basis - self.prior_depreciation - self.current_year_depreciation)


class Income(BaseModel):
    """Comprehensive income information"""
    # W-2 wages
    w2_forms: List[W2Info] = Field(default_factory=list)
    
    # 1099 forms
    form_1099: List[Form1099Info] = Field(default_factory=list)
    
    # Other income sources
    self_employment_income: float = Field(default=0.0, ge=0)
    self_employment_expenses: float = Field(default=0.0, ge=0)

    # Schedule C Businesses (detailed self-employment tracking)
    # If schedule_c_businesses is populated, it takes precedence over
    # the simple self_employment_income/expenses fields above
    schedule_c_businesses: List[ScheduleCBusiness] = Field(
        default_factory=list,
        description="List of Schedule C sole proprietorship businesses"
    )

    interest_income: float = Field(default=0.0, ge=0)
    dividend_income: float = Field(default=0.0, ge=0)
    qualified_dividends: float = Field(default=0.0, ge=0)
    # Capital gains and losses
    short_term_capital_gains: float = Field(default=0.0, ge=0, description="Short-term capital gains (ordinary rates)")
    short_term_capital_losses: float = Field(default=0.0, ge=0, description="Short-term capital losses")
    long_term_capital_gains: float = Field(default=0.0, ge=0, description="Long-term capital gains (preferential rates)")
    long_term_capital_losses: float = Field(default=0.0, ge=0, description="Long-term capital losses")
    # Capital loss carryforward from prior year (IRC Section 1212)
    short_term_loss_carryforward: float = Field(
        default=0.0, ge=0,
        description="Short-term capital loss carryforward from prior year"
    )
    long_term_loss_carryforward: float = Field(
        default=0.0, ge=0,
        description="Long-term capital loss carryforward from prior year"
    )

    # Form 8949 Securities Portfolio (detailed transaction tracking)
    # If securities_portfolio is populated, it takes precedence over
    # the simple short_term/long_term_capital_gains/losses fields above
    securities_portfolio: Optional[SecuritiesPortfolio] = Field(
        default=None,
        description="Detailed Form 8949 securities transactions"
    )

    # Form 8889 HSA (Health Savings Account) tracking
    # If hsa_info is populated, it provides detailed Form 8889 calculation
    hsa_info: Optional[Form8889] = Field(
        default=None,
        description="Detailed Form 8889 HSA contributions and distributions"
    )

    # Form 8606 IRA (Nondeductible IRAs) tracking
    # Tracks basis in Traditional IRAs and Roth conversion/distribution calculations
    ira_info: Optional[Form8606] = Field(
        default=None,
        description="Detailed Form 8606 IRA basis and distribution tracking"
    )

    # Form 5329 Additional Taxes on IRAs and Retirement Plans
    # Tracks early distribution penalties, excess contributions, RMD failures
    form_5329: Optional[Form5329] = Field(
        default=None,
        description="Form 5329 additional taxes on retirement accounts"
    )

    # Form 4797 Sales of Business Property
    # Tracks Section 1231 gains/losses, depreciation recapture (1245/1250)
    form_4797: Optional[Form4797] = Field(
        default=None,
        description="Form 4797 sales of business property and depreciation recapture"
    )

    # Form 6252 Installment Sale Income
    # Tracks installment sales where payments are received over multiple years
    form_6252: Optional[Form6252] = Field(
        default=None,
        description="Form 6252 installment sale income tracking"
    )

    # Form 8582 Passive Activity Loss Limitations
    # Tracks passive activities, material participation, and loss limitations
    form_8582: Optional[Form8582] = Field(
        default=None,
        description="Form 8582 passive activity loss limitations"
    )

    # Form 6251 Alternative Minimum Tax
    # Tracks AMT adjustments and preferences for comprehensive AMT calculation
    form_6251: Optional[Form6251] = Field(
        default=None,
        description="Form 6251 alternative minimum tax calculations"
    )

    # Form 8801 Credit for Prior Year Minimum Tax
    # Tracks minimum tax credit carryforward and current year usage
    form_8801: Optional[Form8801] = Field(
        default=None,
        description="Form 8801 minimum tax credit calculations"
    )

    # Form 1116 Foreign Tax Credit
    # Tracks foreign taxes paid and FTC limitation by income category
    form_1116: Optional[Form1116] = Field(
        default=None,
        description="Form 1116 foreign tax credit calculations"
    )

    # Form 8615 Kiddie Tax
    # Tax for children with unearned income above threshold at parent's rate
    form_8615: Optional[Form8615] = Field(
        default=None,
        description="Form 8615 kiddie tax calculations"
    )

    # Form 2555 Foreign Earned Income Exclusion
    # For US citizens/residents living and working abroad
    form_2555: Optional[Form2555] = Field(
        default=None,
        description="Form 2555 foreign earned income exclusion"
    )

    # Schedule H Household Employment Taxes
    # For employers of domestic workers (nannies, housekeepers, etc.)
    schedule_h: Optional[ScheduleH] = Field(
        default=None,
        description="Schedule H household employment taxes"
    )

    # Form 4952 Investment Interest Expense Deduction
    # For investment interest expense (margin interest, etc.)
    form_4952: Optional[Form4952] = Field(
        default=None,
        description="Form 4952 investment interest expense deduction"
    )

    # Form 5471 Foreign Corporation Information Return
    # For U.S. persons with interests in certain foreign corporations
    form_5471_list: List[Form5471] = Field(
        default_factory=list,
        description="Form 5471 foreign corporation information returns"
    )

    # Form 1040-X Amended Return (for tracking amendments)
    form_1040x: Optional[Form1040X] = Field(
        default=None,
        description="Form 1040-X amended return"
    )

    # Schedule A Itemized Deductions
    schedule_a: Optional[ScheduleA] = Field(
        default=None,
        description="Schedule A itemized deductions"
    )

    # Schedule B Interest and Dividends
    schedule_b: Optional[ScheduleB] = Field(
        default=None,
        description="Schedule B interest and ordinary dividends"
    )

    # Schedule D Capital Gains and Losses
    schedule_d: Optional[ScheduleD] = Field(
        default=None,
        description="Schedule D capital gains and losses"
    )

    # Schedule E Supplemental Income and Loss
    schedule_e: Optional[ScheduleE] = Field(
        default=None,
        description="Schedule E rental, royalty, partnership, S-corp, estate/trust"
    )

    # Schedule F Profit or Loss From Farming
    schedule_f: Optional[ScheduleF] = Field(
        default=None,
        description="Schedule F farm profit or loss"
    )

    # Form 6781 Section 1256 Contracts and Straddles
    form_6781: Optional[Form6781] = Field(
        default=None,
        description="Form 6781 gains/losses from Section 1256 contracts and straddles"
    )

    # Form 8814 Parent's Election to Report Child's Interest and Dividends
    form_8814: Optional[Form8814] = Field(
        default=None,
        description="Form 8814 parent's election to report child's income"
    )

    # Form 8995 Qualified Business Income Deduction
    form_8995: Optional[Form8995] = Field(
        default=None,
        description="Form 8995 QBI deduction (Section 199A)"
    )

    # Tax-exempt interest (used for Social Security provisional income)
    tax_exempt_interest: float = Field(default=0.0, ge=0)
    rental_income: float = Field(default=0.0, ge=0)
    rental_expenses: float = Field(default=0.0, ge=0)

    # Passive Activity Loss (PAL) - Form 8582 / IRC Section 469
    # Rental real estate activity tracking
    is_active_participant_rental: bool = Field(
        default=True,
        description="Active participation in rental (qualifies for $25k loss allowance)"
    )
    is_real_estate_professional: bool = Field(
        default=False,
        description="Real estate professional status (750+ hrs, >50% time in RE)"
    )
    real_estate_professional_hours: float = Field(
        default=0.0, ge=0,
        description="Total hours in real property trades/businesses"
    )
    # Suspended losses from prior years
    suspended_passive_loss_carryforward: float = Field(
        default=0.0, ge=0,
        description="Suspended passive activity losses from prior years (Form 8582)"
    )
    suspended_rental_loss_carryforward: float = Field(
        default=0.0, ge=0,
        description="Suspended rental loss carryforward from prior years"
    )
    # Non-rental passive activities (business investments, limited partnerships)
    passive_business_income: float = Field(
        default=0.0, ge=0,
        description="Passive income from business activities (non-rental)"
    )
    passive_business_losses: float = Field(
        default=0.0, ge=0,
        description="Passive losses from business activities (non-rental)"
    )
    # Property disposition tracking (triggers suspended loss release)
    passive_activity_dispositions: float = Field(
        default=0.0,
        description="Gain/loss from complete disposition of passive activities (releases suspended losses)"
    )

    retirement_income: float = Field(default=0.0, ge=0)
    unemployment_compensation: float = Field(default=0.0, ge=0)
    social_security_benefits: float = Field(default=0.0, ge=0)
    taxable_social_security: float = Field(default=0.0, ge=0)
    other_income: float = Field(default=0.0, ge=0)
    other_income_description: Optional[str] = None

    # Additional investment income for NIIT calculation
    royalty_income: float = Field(default=0.0, ge=0, description="Royalty income (Schedule E)")
    other_investment_income: float = Field(default=0.0, ge=0, description="Other investment income (passive income, etc.)")

    # Gambling income and losses (BR-0501 to BR-0510)
    gambling_winnings: List[GamblingWinnings] = Field(
        default_factory=list,
        description="W-2G forms and other gambling winnings"
    )
    gambling_losses: float = Field(
        default=0.0,
        ge=0,
        description="Total gambling losses (deductible up to winnings amount)"
    )
    is_professional_gambler: bool = Field(
        default=False,
        description="If True, gambling treated as business income (Schedule C)"
    )

    # Virtual Currency / Digital Assets (BR-0601 to BR-0620)
    # Per IRS Notice 2014-21 and Form 1040 checkbox requirement
    virtual_currency_transactions: List[VirtualCurrencyTransaction] = Field(
        default_factory=list,
        description="All virtual currency/digital asset transactions"
    )
    had_virtual_currency_activity: bool = Field(
        default=False,
        description="Form 1040 checkbox: Did you receive, sell, exchange, or dispose of digital assets?"
    )
    crypto_cost_basis_method: CostBasisMethod = Field(
        default=CostBasisMethod.FIFO,
        description="Default cost basis method for crypto transactions"
    )

    # Schedule K-1 Pass-Through Income (BR-0701 to BR-0730)
    schedule_k1_forms: List[ScheduleK1] = Field(
        default_factory=list,
        description="Schedule K-1 forms from partnerships, S-corps, and trusts/estates"
    )

    # Payments and withholdings
    estimated_tax_payments: float = Field(default=0.0, ge=0, description="Estimated tax payments made")
    amount_paid_with_extension: float = Field(default=0.0, ge=0, description="Amount paid with extension request")
    excess_social_security_withholding: float = Field(default=0.0, ge=0, description="Excess SS withholding from multiple employers")

    # Prior year information for estimated tax safe harbor (Form 2210)
    prior_year_tax: float = Field(default=0.0, ge=0, description="Prior year total tax for safe harbor calculation")
    prior_year_agi: float = Field(default=0.0, ge=0, description="Prior year AGI for 110% safe harbor threshold")
    is_farmer_or_fisherman: bool = Field(default=False, description="Qualifies for 66⅔% safe harbor rule")

    # AMT Preference Items (Form 6251) - IRC Sections 56-59
    # These items are added back to taxable income to compute AMTI
    amt_iso_exercise_spread: float = Field(
        default=0.0, ge=0,
        description="Incentive Stock Option (ISO) exercise spread - bargain element (Form 6251, Line 2i)"
    )
    amt_private_activity_bond_interest: float = Field(
        default=0.0, ge=0,
        description="Tax-exempt interest from private activity bonds (Form 6251, Line 2g)"
    )
    amt_depletion_excess: float = Field(
        default=0.0, ge=0,
        description="Excess depletion over cost basis (Form 6251, Line 2p)"
    )
    amt_intangible_drilling_costs: float = Field(
        default=0.0, ge=0,
        description="Intangible drilling costs preference (Form 6251, Line 2l)"
    )
    amt_circulation_expenditures: float = Field(
        default=0.0, ge=0,
        description="Circulation costs preference (Form 6251, Line 2n)"
    )
    amt_mining_exploration_costs: float = Field(
        default=0.0, ge=0,
        description="Mining exploration and development costs (Form 6251, Line 2m)"
    )
    amt_research_experimental_costs: float = Field(
        default=0.0, ge=0,
        description="Research and experimental expenditures (Form 6251, Line 2o)"
    )
    amt_depreciation_adjustment: float = Field(
        default=0.0,
        description="Post-1986 depreciation adjustment (MACRS vs ADS difference - Form 6251, Line 2a)"
    )
    amt_passive_activity_adjustment: float = Field(
        default=0.0,
        description="Passive activity loss adjustment for AMT (Form 6251, Line 2e)"
    )
    amt_loss_limitations_adjustment: float = Field(
        default=0.0,
        description="Loss limitations adjustment for AMT (Form 6251, Line 2d)"
    )
    amt_long_term_contracts: float = Field(
        default=0.0,
        description="Long-term contract income adjustment (Form 6251, Line 2s)"
    )
    amt_other_adjustments: float = Field(
        default=0.0,
        description="Other AMT adjustments (Form 6251, Line 2t)"
    )

    # Prior year AMT credit (Form 8801)
    prior_year_amt_credit: float = Field(
        default=0.0, ge=0,
        description="Minimum tax credit carryforward from prior years (Form 8801)"
    )

    # Depreciation - Form 4562 / MACRS (Modified Accelerated Cost Recovery System)
    # Assets placed in service subject to depreciation
    depreciable_assets: List["DepreciableAsset"] = Field(
        default_factory=list,
        description="Business/rental assets subject to MACRS depreciation"
    )
    # Section 179 election (IRC Section 179) - immediate expensing
    section_179_elected: float = Field(
        default=0.0, ge=0,
        description="Total Section 179 expense elected for current year"
    )
    # Bonus depreciation (100% through 2026, then phases down)
    bonus_depreciation_elected: float = Field(
        default=0.0, ge=0,
        description="Bonus depreciation amount elected (Form 4562, Part II)"
    )
    # Depreciation from prior years (for tracking adjusted basis)
    total_prior_depreciation: float = Field(
        default=0.0, ge=0,
        description="Accumulated depreciation from prior tax years"
    )

    # State-specific income fields
    state_income_adjustments: float = Field(default=0.0, description="State-specific income adjustments")

    @property
    def federal_withholding(self) -> float:
        """Total federal tax withheld from all sources."""
        return self.get_total_federal_withholding()

    def get_total_wages(self) -> float:
        """Calculate total W-2 wages"""
        return sum(w2.wages for w2 in self.w2_forms)

    def get_total_federal_withholding(self) -> float:
        """Calculate total federal tax withheld from all sources including gambling."""
        w2_withholding = sum(w2.federal_tax_withheld for w2 in self.w2_forms)
        gambling_withholding = sum(g.federal_tax_withheld for g in self.gambling_winnings)
        return w2_withholding + gambling_withholding

    def get_total_gambling_winnings(self) -> float:
        """
        Calculate total gambling winnings.

        Per IRS rules, all gambling winnings are taxable and must be reported,
        regardless of whether a W-2G was issued.
        """
        return sum(g.gross_winnings for g in self.gambling_winnings)

    def get_deductible_gambling_losses(self) -> float:
        """
        Calculate deductible gambling losses (itemized deduction).

        IRS Rule: Gambling losses are ONLY deductible up to the amount of
        gambling winnings. You cannot deduct more losses than winnings.

        For professional gamblers (Schedule C), different rules apply.
        """
        total_winnings = self.get_total_gambling_winnings()
        return min(self.gambling_losses, total_winnings)

    def get_gambling_withholding(self) -> float:
        """Get total federal tax withheld from gambling winnings (W-2G Box 4)."""
        return sum(g.federal_tax_withheld for g in self.gambling_winnings)

    def get_gambling_state_withholding(self) -> float:
        """Get total state tax withheld from gambling winnings."""
        return sum(g.state_tax_withheld for g in self.gambling_winnings)

    # Virtual Currency Helper Methods

    def get_crypto_ordinary_income(self) -> float:
        """
        Calculate ordinary income from virtual currency activities.

        Ordinary income includes:
        - Mining rewards (at FMV when received)
        - Staking rewards (at FMV when received)
        - Airdrops (at FMV when dominion/control established)
        - Hard fork tokens (at FMV when dominion/control)
        - Payment for goods/services in crypto (at FMV)
        """
        ordinary_types = [
            VirtualCurrencyTransactionType.MINING,
            VirtualCurrencyTransactionType.STAKING,
            VirtualCurrencyTransactionType.AIRDROP,
            VirtualCurrencyTransactionType.HARD_FORK,
            VirtualCurrencyTransactionType.INCOME_PAYMENT,
        ]
        return sum(
            tx.fair_market_value
            for tx in self.virtual_currency_transactions
            if tx.transaction_type in ordinary_types
        )

    def get_crypto_short_term_gains(self) -> float:
        """
        Calculate short-term capital gains from crypto (held <= 1 year).

        Taxed at ordinary income rates.
        """
        capital_types = [
            VirtualCurrencyTransactionType.SALE,
            VirtualCurrencyTransactionType.EXCHANGE,
            VirtualCurrencyTransactionType.GOODS_SERVICES,
        ]
        gains = 0.0
        for tx in self.virtual_currency_transactions:
            if tx.transaction_type in capital_types:
                gain = tx.calculate_gain_loss()
                is_long = tx.is_long_term or tx.determine_holding_period()
                if not is_long and gain > 0:
                    gains += gain
        return gains

    def get_crypto_short_term_losses(self) -> float:
        """Calculate short-term capital losses from crypto."""
        capital_types = [
            VirtualCurrencyTransactionType.SALE,
            VirtualCurrencyTransactionType.EXCHANGE,
            VirtualCurrencyTransactionType.GOODS_SERVICES,
        ]
        losses = 0.0
        for tx in self.virtual_currency_transactions:
            if tx.transaction_type in capital_types:
                gain = tx.calculate_gain_loss()
                is_long = tx.is_long_term or tx.determine_holding_period()
                if not is_long and gain < 0:
                    losses += abs(gain)
        return losses

    def get_crypto_long_term_gains(self) -> float:
        """
        Calculate long-term capital gains from crypto (held > 1 year).

        Taxed at preferential rates (0%, 15%, 20%).
        """
        capital_types = [
            VirtualCurrencyTransactionType.SALE,
            VirtualCurrencyTransactionType.EXCHANGE,
            VirtualCurrencyTransactionType.GOODS_SERVICES,
        ]
        gains = 0.0
        for tx in self.virtual_currency_transactions:
            if tx.transaction_type in capital_types:
                gain = tx.calculate_gain_loss()
                is_long = tx.is_long_term or tx.determine_holding_period()
                if is_long and gain > 0:
                    gains += gain
        return gains

    def get_crypto_long_term_losses(self) -> float:
        """Calculate long-term capital losses from crypto."""
        capital_types = [
            VirtualCurrencyTransactionType.SALE,
            VirtualCurrencyTransactionType.EXCHANGE,
            VirtualCurrencyTransactionType.GOODS_SERVICES,
        ]
        losses = 0.0
        for tx in self.virtual_currency_transactions:
            if tx.transaction_type in capital_types:
                gain = tx.calculate_gain_loss()
                is_long = tx.is_long_term or tx.determine_holding_period()
                if is_long and gain < 0:
                    losses += abs(gain)
        return losses

    def get_total_crypto_capital_gains_losses(self) -> tuple[float, float, float, float]:
        """
        Get all crypto capital gains and losses.

        Returns:
            Tuple of (st_gains, st_losses, lt_gains, lt_losses)
        """
        return (
            self.get_crypto_short_term_gains(),
            self.get_crypto_short_term_losses(),
            self.get_crypto_long_term_gains(),
            self.get_crypto_long_term_losses(),
        )

    def get_net_crypto_capital_gain(self) -> float:
        """Calculate net capital gain from crypto (can be negative for loss)."""
        st_gains = self.get_crypto_short_term_gains()
        st_losses = self.get_crypto_short_term_losses()
        lt_gains = self.get_crypto_long_term_gains()
        lt_losses = self.get_crypto_long_term_losses()

        return (st_gains - st_losses) + (lt_gains - lt_losses)

    def has_virtual_currency_activity(self) -> bool:
        """
        Check if taxpayer had any virtual currency activity (for Form 1040 checkbox).

        IRS requires answering "Yes" if you:
        - Received digital assets as payment
        - Received digital assets as reward/award
        - Received new digital assets from mining/staking/similar
        - Received digital assets from hard fork
        - Sold, exchanged, or otherwise disposed of digital assets
        - Transferred digital assets for free (not to yourself)
        """
        if self.had_virtual_currency_activity:
            return True
        return len(self.virtual_currency_transactions) > 0

    # Schedule K-1 Helper Methods

    def get_total_k1_income(self) -> float:
        """Get total income from all Schedule K-1 forms."""
        return sum(k1.get_total_income() for k1 in self.schedule_k1_forms)

    def get_k1_ordinary_income(self) -> float:
        """Get ordinary income from all K-1 forms."""
        return sum(k1.get_ordinary_income() for k1 in self.schedule_k1_forms)

    def get_k1_preferential_income(self) -> float:
        """Get preferential income (qualified dividends + LTCG) from K-1 forms."""
        return sum(k1.get_preferential_income() for k1 in self.schedule_k1_forms)

    def get_k1_qualified_dividends(self) -> float:
        """Get qualified dividends from K-1 forms."""
        return sum(k1.qualified_dividends for k1 in self.schedule_k1_forms)

    def get_k1_interest_income(self) -> float:
        """Get interest income from K-1 forms."""
        return sum(k1.interest_income for k1 in self.schedule_k1_forms)

    def get_k1_rental_income(self) -> float:
        """Get rental income from K-1 forms."""
        return sum(
            k1.net_rental_real_estate + k1.other_rental_income
            for k1 in self.schedule_k1_forms
        )

    def get_k1_capital_gains(self) -> tuple[float, float]:
        """
        Get capital gains from K-1 forms.

        Returns:
            Tuple of (short_term_gain, long_term_gain)
        """
        short_term = sum(k1.net_short_term_capital_gain for k1 in self.schedule_k1_forms)
        long_term = sum(
            k1.net_long_term_capital_gain + k1.net_section_1231_gain
            for k1 in self.schedule_k1_forms
        )
        return short_term, long_term

    def calculate_net_capital_gain_loss(
        self,
        filing_status: str,
        capital_loss_limit: float = 3000.0,
        capital_loss_limit_mfs: float = 1500.0
    ) -> Tuple[float, float, float, float, float, float]:
        """
        Calculate net capital gain/loss per IRC Sections 1211 and 1212.

        IRS Netting Rules:
        1. Short-term losses offset short-term gains first, then long-term gains
        2. Long-term losses offset long-term gains first, then short-term gains
        3. Net capital loss limited to $3,000/year ($1,500 MFS)
        4. Unused losses carry forward INDEFINITELY maintaining character
        5. Carryforward cannot be carried back (forward only)

        Args:
            filing_status: Taxpayer's filing status
            capital_loss_limit: Annual loss limit ($3,000)
            capital_loss_limit_mfs: MFS limit ($1,500)

        Returns:
            Tuple of:
            - net_gain_for_tax: Net capital gain to add to taxable income (if positive)
            - allowable_loss_deduction: Loss deduction against ordinary income (max $3k/$1.5k)
            - new_st_carryforward: Short-term loss to carry to next year
            - new_lt_carryforward: Long-term loss to carry to next year
            - net_short_term: Net short-term result (for Schedule D)
            - net_long_term: Net long-term result (for Schedule D)
        """
        # Step 1: Aggregate all short-term gains and losses
        st_gains = self.short_term_capital_gains
        st_losses = self.short_term_capital_losses  # Include direct capital losses

        # Form 8949 Securities Portfolio (takes precedence if populated)
        if self.securities_portfolio:
            securities_summary = self.securities_portfolio.calculate_summary()
            st_securities = securities_summary.get_total_short_term_gain_loss()
            if st_securities >= 0:
                st_gains += st_securities
            else:
                st_losses += abs(st_securities)

        # K-1 pass-through (can be negative for losses)
        for k1 in self.schedule_k1_forms:
            if k1.net_short_term_capital_gain >= 0:
                st_gains += k1.net_short_term_capital_gain
            else:
                st_losses += abs(k1.net_short_term_capital_gain)

        # Crypto transactions
        st_gains += self.get_crypto_short_term_gains()
        st_losses += self.get_crypto_short_term_losses()

        # Prior year carryforward (stored as positive value)
        # Use securities_portfolio carryforward if available, otherwise use direct field
        if self.securities_portfolio:
            st_losses += self.securities_portfolio.short_term_loss_carryforward
        else:
            st_losses += self.short_term_loss_carryforward

        # Step 2: Aggregate all long-term gains and losses
        lt_gains = self.long_term_capital_gains
        lt_losses = self.long_term_capital_losses  # Include direct capital losses

        # Form 8949 Securities Portfolio
        if self.securities_portfolio:
            lt_securities = securities_summary.get_total_long_term_gain_loss()
            if lt_securities >= 0:
                lt_gains += lt_securities
            else:
                lt_losses += abs(lt_securities)

        # K-1 pass-through (including Section 1231)
        for k1 in self.schedule_k1_forms:
            lt_total = k1.net_long_term_capital_gain + k1.net_section_1231_gain
            if lt_total >= 0:
                lt_gains += lt_total
            else:
                lt_losses += abs(lt_total)

        # Crypto transactions
        lt_gains += self.get_crypto_long_term_gains()
        lt_losses += self.get_crypto_long_term_losses()

        # Prior year carryforward (stored as positive value)
        if self.securities_portfolio:
            lt_losses += self.securities_portfolio.long_term_loss_carryforward
        else:
            lt_losses += self.long_term_loss_carryforward

        # Step 3: Net within each category first
        net_short_term = st_gains - st_losses
        net_long_term = lt_gains - lt_losses

        # Step 4: Calculate overall net position
        overall_net = net_short_term + net_long_term

        # Step 5: Determine annual limit based on filing status
        annual_limit = capital_loss_limit_mfs if filing_status == "married_separate" else capital_loss_limit

        # Step 6: Calculate results based on overall position
        if overall_net >= 0:
            # Net gain position - no loss deduction, no carryforward
            return (overall_net, 0.0, 0.0, 0.0, net_short_term, net_long_term)

        # Net loss position - apply annual limit
        total_loss = abs(overall_net)
        allowable_loss = min(total_loss, annual_limit)
        excess_loss = total_loss - allowable_loss

        # Step 7: Allocate carryforward maintaining character (per IRS rules)
        # The character of the carryforward depends on which type created the excess
        new_st_carryforward = 0.0
        new_lt_carryforward = 0.0

        if excess_loss > 0:
            # Carryforward allocation per IRS Schedule D instructions:
            # - If both ST and LT are losses, ST absorbs the annual limit first
            # - Remaining excess maintains character

            if net_short_term < 0 and net_long_term < 0:
                # Both are losses
                st_loss_amount = abs(net_short_term)
                lt_loss_amount = abs(net_long_term)

                # ST losses are used first against the annual limit
                if st_loss_amount >= annual_limit:
                    # All of limit comes from ST, remainder is ST carryforward
                    new_st_carryforward = st_loss_amount - annual_limit
                    new_lt_carryforward = lt_loss_amount
                else:
                    # ST fully used, some LT used for limit
                    lt_used_for_limit = annual_limit - st_loss_amount
                    new_st_carryforward = 0.0
                    new_lt_carryforward = lt_loss_amount - lt_used_for_limit
            elif net_short_term < 0:
                # Only ST is a loss (LT is gain or zero but overall is loss)
                # All excess must be ST character
                new_st_carryforward = excess_loss
            else:
                # Only LT is a loss (ST is gain or zero but overall is loss)
                # All excess must be LT character
                new_lt_carryforward = excess_loss

        # Return: net_gain_for_tax is 0 when we have a net loss
        return (0.0, allowable_loss, new_st_carryforward, new_lt_carryforward, net_short_term, net_long_term)

    def get_k1_self_employment_income(self) -> float:
        """
        Get self-employment earnings from Partnership K-1s.

        Only partnerships (not S-corps) generate self-employment income.
        """
        return sum(
            k1.self_employment_earnings
            for k1 in self.schedule_k1_forms
            if k1.k1_type == K1SourceType.PARTNERSHIP
        )

    def get_schedule_c_net_profit(self) -> float:
        """
        Get total net profit/loss from all Schedule C businesses.

        If schedule_c_businesses is populated, uses the detailed calculations.
        Otherwise falls back to the simple self_employment_income - expenses.

        Returns:
            Net profit (positive) or loss (negative) from all Schedule C businesses.
        """
        if self.schedule_c_businesses:
            return sum(biz.calculate_net_profit_loss() for biz in self.schedule_c_businesses)
        else:
            return self.self_employment_income - self.self_employment_expenses

    def get_schedule_c_se_income(self) -> float:
        """
        Get self-employment income from Schedule C for SE tax calculation.

        Excludes statutory employees (who don't pay SE tax).
        """
        if self.schedule_c_businesses:
            return sum(biz.get_se_income() for biz in self.schedule_c_businesses)
        else:
            return self.self_employment_income - self.self_employment_expenses

    def get_schedule_c_qbi(self) -> float:
        """
        Get qualified business income from Schedule C businesses.

        Used for Section 199A deduction calculation.
        """
        if self.schedule_c_businesses:
            return sum(biz.get_qbi_income() for biz in self.schedule_c_businesses)
        else:
            net = self.self_employment_income - self.self_employment_expenses
            return net if net > 0 else net  # QBI can be negative (reduces other QBI)

    def get_schedule_c_summary(self) -> List[dict]:
        """Get summary of all Schedule C businesses."""
        if not self.schedule_c_businesses:
            if self.self_employment_income > 0 or self.self_employment_expenses > 0:
                return [{
                    'business_name': 'Self-Employment (Simple)',
                    'gross_receipts': self.self_employment_income,
                    'total_expenses': self.self_employment_expenses,
                    'net_profit_or_loss': self.self_employment_income - self.self_employment_expenses,
                }]
            return []
        return [biz.generate_summary() for biz in self.schedule_c_businesses]

    def get_k1_qbi_income(self) -> float:
        """Get qualified business income for Section 199A deduction from K-1s."""
        return sum(k1.qbi_ordinary_income for k1 in self.schedule_k1_forms)

    def get_total_qbi(self) -> float:
        """
        Get total qualified business income from all sources for Section 199A.

        QBI includes:
        - Schedule C net profit (self-employment income - expenses)
        - Schedule K-1 QBI amounts from partnerships/S-corps

        Note: Rental income can qualify as QBI if it rises to the level of
        a trade or business, but this simplified calculation excludes it.
        """
        qbi = 0.0

        # Schedule C QBI (includes detailed or simple self-employment)
        schedule_c_qbi = self.get_schedule_c_qbi()
        qbi += schedule_c_qbi

        # K-1 QBI from partnerships and S-corps
        qbi += self.get_k1_qbi_income()

        return qbi

    def get_qbi_w2_wages(self) -> float:
        """
        Get total W-2 wages paid by QBI businesses for Section 199A limitation.

        The W-2 wage limitation is one of two tests for the QBI deduction
        when taxpayer income exceeds the threshold.
        """
        return sum(k1.w2_wages_for_qbi for k1 in self.schedule_k1_forms)

    def get_qbi_ubia(self) -> float:
        """
        Get total UBIA (Unadjusted Basis Immediately After Acquisition)
        of qualified property for Section 199A limitation.

        UBIA is used in the alternative wage limitation test:
        25% of W-2 wages + 2.5% of UBIA
        """
        return sum(k1.ubia_for_qbi for k1 in self.schedule_k1_forms)

    def has_sstb_income(self) -> bool:
        """
        Check if any K-1 is from a Specified Service Trade or Business (SSTB).

        SSTBs include businesses in health, law, accounting, actuarial science,
        performing arts, consulting, athletics, financial services, brokerage,
        or any trade where the principal asset is the reputation/skill of employees.

        SSTB income is subject to additional phase-out above the QBI threshold.
        """
        return any(k1.is_sstb for k1 in self.schedule_k1_forms)

    def get_k1_foreign_tax_paid(self) -> float:
        """Get foreign taxes paid from K-1 forms."""
        return sum(k1.foreign_tax_paid for k1 in self.schedule_k1_forms)

    def get_total_income(self) -> float:
        """Calculate total income from all sources including crypto and K-1s."""
        total = self.get_total_wages()
        total += sum(form.amount for form in self.form_1099)
        total += self.get_schedule_c_net_profit()  # Uses Schedule C or simple SE
        total += self.interest_income
        total += self.dividend_income
        total += self.short_term_capital_gains
        total += self.long_term_capital_gains
        total += self.rental_income - self.rental_expenses
        total += self.retirement_income
        total += self.unemployment_compensation
        total += self.taxable_social_security
        total += self.other_income

        # Add gambling winnings (non-professional)
        if not self.is_professional_gambler:
            total += self.get_total_gambling_winnings()

        # Add virtual currency income
        # - Ordinary income (mining, staking, airdrops, etc.)
        total += self.get_crypto_ordinary_income()
        # - Capital gains/losses are already included via short_term_capital_gains
        #   and long_term_capital_gains fields, but we add crypto-specific gains
        total += self.get_crypto_short_term_gains()
        total += self.get_crypto_long_term_gains()
        # Subtract crypto losses (limited to $3,000 annual max with carryforward)
        # Note: Full loss calculation handled in engine with carryforward rules

        # Add Schedule K-1 pass-through income (BR-0701 to BR-0730)
        total += self.get_total_k1_income()

        return total
    
    def get_adjusted_gross_income(self) -> float:
        """Calculate Adjusted Gross Income (AGI)"""
        # AGI is total income minus certain adjustments
        # For now, we'll use total income (adjustments handled separately)
        return self.get_total_income()

    def get_state_wages(self, state_code: Optional[str] = None) -> float:
        """
        Get total wages for a specific state.

        Args:
            state_code: Two-letter state code. If None, returns all wages.

        Returns:
            Total wages for the specified state
        """
        if state_code is None:
            return self.get_total_wages()

        total = 0.0
        for w2 in self.w2_forms:
            # Use state_wages if available, otherwise fall back to federal wages
            if w2.state_wages is not None:
                total += w2.state_wages
            else:
                total += w2.wages
        return total

    def get_state_withholding(self, state_code: Optional[str] = None) -> float:
        """
        Get total state tax withheld.

        Args:
            state_code: Two-letter state code. If None, returns all state withholding.

        Returns:
            Total state tax withheld
        """
        return sum(
            w2.state_tax_withheld or 0.0
            for w2 in self.w2_forms
        )

    # ========== Form 8949 Securities Methods ==========

    def get_form_8949_summary(self, filing_status: str = "single") -> Optional[dict]:
        """
        Get Form 8949 summary from securities portfolio.

        Returns None if no securities portfolio is populated.
        """
        if not self.securities_portfolio:
            return None
        return self.securities_portfolio.calculate_summary(filing_status).__dict__

    def get_securities_schedule_d_amounts(self) -> Optional[dict]:
        """
        Get Schedule D amounts from securities portfolio.

        Returns None if no securities portfolio is populated.
        """
        if not self.securities_portfolio:
            return None
        return self.securities_portfolio.get_schedule_d_amounts()

    def get_form_8949_report(self) -> Optional[dict]:
        """
        Get complete Form 8949 report with all transactions by box.

        Returns None if no securities portfolio is populated.
        """
        if not self.securities_portfolio:
            return None
        return self.securities_portfolio.generate_form_8949_report()

    def get_securities_net_gain_loss(self) -> Tuple[float, float]:
        """
        Get net short-term and long-term gains/losses from securities.

        Returns tuple of (net_short_term, net_long_term).
        Returns (0.0, 0.0) if no securities portfolio.
        """
        if not self.securities_portfolio:
            return (0.0, 0.0)
        return (
            self.securities_portfolio.get_net_short_term_gain_loss(),
            self.securities_portfolio.get_net_long_term_gain_loss()
        )

    def detect_wash_sales(self) -> List[dict]:
        """
        Detect potential wash sales in securities portfolio.

        Returns empty list if no securities portfolio or no wash sales detected.
        """
        if not self.securities_portfolio:
            return []
        return self.securities_portfolio.detect_wash_sales()

    def get_total_wash_sale_disallowed(self) -> float:
        """Get total wash sale loss disallowed amount."""
        if not self.securities_portfolio:
            return 0.0
        summary = self.securities_portfolio.calculate_summary()
        return summary.total_wash_sale_disallowed

    def get_section_1244_ordinary_loss(self, filing_status: str = "single") -> float:
        """
        Get Section 1244 ordinary loss from small business stock.

        Section 1244 allows up to $50k ($100k MFJ) of qualifying
        small business stock loss to be treated as ordinary loss.
        """
        if not self.securities_portfolio:
            return 0.0
        summary = self.securities_portfolio.calculate_summary(filing_status)
        return summary.total_section_1244_ordinary_loss

    def get_qsbs_exclusion(self, filing_status: str = "single") -> float:
        """
        Get Section 1202 QSBS gain exclusion.

        Qualified Small Business Stock may exclude 50%, 75%, or 100%
        of gain depending on when acquired.
        """
        if not self.securities_portfolio:
            return 0.0
        summary = self.securities_portfolio.calculate_summary(filing_status)
        return summary.total_qsbs_exclusion

    # ========== Form 8889 HSA Methods ==========

    def get_employer_hsa_contributions(self) -> float:
        """Get total employer HSA contributions from all W-2s."""
        return sum(w2.employer_hsa_contribution for w2 in self.w2_forms)

    def get_hsa_deduction(
        self,
        self_only_limit: float = 4300.0,
        family_limit: float = 8550.0,
        catchup_amount: float = 1000.0,
    ) -> float:
        """
        Calculate HSA deduction (Form 8889 Line 13).

        Uses hsa_info if populated, otherwise returns 0.
        """
        if not self.hsa_info:
            return 0.0

        result = self.hsa_info.calculate_deduction(
            self_only_limit, family_limit, catchup_amount
        )
        return result['hsa_deduction']

    def get_hsa_taxable_distributions(self) -> float:
        """Get taxable HSA distributions (Form 8889 Line 16)."""
        if not self.hsa_info:
            return 0.0
        return self.hsa_info.get_taxable_distributions()

    def get_hsa_additional_tax(self, penalty_rate: float = 0.20) -> float:
        """Get HSA additional tax (20% penalty on non-qualified distributions)."""
        if not self.hsa_info:
            return 0.0
        result = self.hsa_info.calculate_additional_tax(penalty_rate)
        return result['total_additional_tax']

    def get_form_8889_summary(
        self,
        self_only_limit: float = 4300.0,
        family_limit: float = 8550.0,
        catchup_amount: float = 1000.0,
    ) -> Optional[dict]:
        """
        Get complete Form 8889 summary.

        Returns None if no HSA info is populated.
        """
        if not self.hsa_info:
            return None
        return self.hsa_info.generate_form_8889_summary(
            self_only_limit, family_limit, catchup_amount
        )

    def get_hsa_excess_contributions(
        self,
        self_only_limit: float = 4300.0,
        family_limit: float = 8550.0,
        catchup_amount: float = 1000.0,
    ) -> float:
        """Get excess HSA contributions subject to 6% excise tax."""
        if not self.hsa_info:
            return 0.0
        result = self.hsa_info.calculate_deduction(
            self_only_limit, family_limit, catchup_amount
        )
        return result['excess_contributions']

    # ========== Form 8606 IRA Methods ==========

    def get_ira_taxable_distribution(self, current_year: int = 2025) -> float:
        """
        Get taxable IRA distribution amount (Form 8606).

        Includes:
        - Taxable portion of Traditional IRA distributions (pro-rata rule)
        - Taxable portion of Roth conversions
        - Taxable earnings from non-qualified Roth distributions
        """
        if not self.ira_info:
            return 0.0

        return (
            self.ira_info.calculate_taxable_traditional_distribution() +
            self.ira_info.calculate_taxable_roth_distribution(current_year)
        )

    def get_ira_early_withdrawal_penalty(self, current_year: int = 2025) -> float:
        """
        Get 10% early withdrawal penalty on IRA distributions.

        Applies to Traditional IRA distributions before age 59½ and
        non-qualified Roth distributions (earnings and recent conversions).
        """
        if not self.ira_info:
            return 0.0

        return self.ira_info.calculate_early_withdrawal_penalty(current_year)

    def get_roth_conversion_taxable(self) -> float:
        """Get taxable amount from Roth IRA conversions."""
        if not self.ira_info:
            return 0.0

        result = self.ira_info.calculate_part_ii_conversion()
        return result['taxable_conversion']

    def get_ira_basis_carryforward(self) -> float:
        """
        Get remaining IRA basis for next year's Form 8606.

        This becomes Line 2 on next year's Form 8606.
        """
        if not self.ira_info:
            return 0.0

        return self.ira_info.get_remaining_basis()

    def get_form_8606_summary(self, current_year: int = 2025) -> Optional[dict]:
        """
        Get complete Form 8606 summary.

        Returns None if no IRA info is populated.
        """
        if not self.ira_info:
            return None
        return self.ira_info.generate_form_8606_summary(current_year)

    def get_total_ira_distributions(self) -> float:
        """Get total gross IRA distributions (Traditional + Roth)."""
        if not self.ira_info:
            return 0.0

        return (
            self.ira_info.traditional_ira_distributions +
            self.ira_info.roth_ira_distributions
        )

    def get_nontaxable_ira_distribution(self, current_year: int = 2025) -> float:
        """
        Get non-taxable portion of IRA distributions.

        This is the return of basis (already-taxed nondeductible contributions).
        """
        total = self.get_total_ira_distributions()
        taxable = self.get_ira_taxable_distribution(current_year)
        return max(0.0, total - taxable)

    # ========== Form 5329 Additional Tax Methods ==========

    def get_form_5329_early_distribution_penalty(self) -> float:
        """
        Get 10% early distribution penalty from Form 5329 Part I.

        This is more comprehensive than the Form 8606 penalty as it handles
        all exception codes and multiple distributions.
        """
        if not self.form_5329:
            return 0.0
        result = self.form_5329.calculate_part_i_early_distribution_penalty()
        return result['line_4_penalty']

    def get_form_5329_excess_contribution_tax(self) -> float:
        """
        Get 6% excise tax on excess contributions from Form 5329 Parts II-VII.

        Includes excess contributions to:
        - Traditional IRA (Part II)
        - Roth IRA (Part III)
        - Coverdell ESA (Part IV)
        - Archer MSA (Part V)
        - HSA (Part VI)
        - ABLE accounts (Part VII)
        """
        if not self.form_5329:
            return 0.0

        total = 0.0
        total += self.form_5329.calculate_part_ii_traditional_ira_excess()['excise_tax']
        total += self.form_5329.calculate_part_iii_roth_ira_excess()['excise_tax']
        total += self.form_5329.calculate_part_iv_coverdell_excess()['excise_tax']
        total += self.form_5329.calculate_part_v_archer_msa_excess()['excise_tax']
        total += self.form_5329.calculate_part_vi_hsa_excess()['excise_tax']
        total += self.form_5329.calculate_part_vii_able_excess()['excise_tax']
        return total

    def get_form_5329_rmd_penalty(self) -> float:
        """
        Get penalty for RMD failures from Form 5329 Part VIII.

        25% penalty on RMD shortfall (10% if corrected timely).
        """
        if not self.form_5329:
            return 0.0
        result = self.form_5329.calculate_part_viii_rmd_penalty()
        return result['total_penalty']

    def get_form_5329_529_excess_tax(self) -> float:
        """Get 6% excise tax on excess Section 529 contributions."""
        if not self.form_5329:
            return 0.0
        result = self.form_5329.calculate_part_ix_529_excess()
        return result['excise_tax']

    def get_form_5329_total_additional_tax(self) -> float:
        """Get total additional tax from Form 5329."""
        if not self.form_5329:
            return 0.0
        return self.form_5329.calculate_total_additional_tax()

    def get_form_5329_summary(self) -> Optional[dict]:
        """Get complete Form 5329 summary."""
        if not self.form_5329:
            return None
        return self.form_5329.generate_form_5329_summary()

    # ========== Form 4797 Sales of Business Property Methods ==========

    def get_form_4797_ordinary_income(self, current_year: int = 2025) -> float:
        """
        Get ordinary income from Form 4797 (Part II).

        Includes:
        - Short-term gains on business property
        - Depreciation recapture (Section 1245, Section 1250 additional)
        - Section 179/280F recapture
        """
        if not self.form_4797:
            return 0.0
        return self.form_4797.get_ordinary_income(current_year)

    def get_form_4797_section_1231_gain(self, current_year: int = 2025) -> float:
        """
        Get Section 1231 gain for Schedule D (as long-term capital gain).

        Section 1231 gain is treated as LTCG after:
        - Netting all Section 1231 gains/losses
        - Applying 5-year lookback rule for prior losses
        """
        if not self.form_4797:
            return 0.0
        return self.form_4797.get_section_1231_gain_for_schedule_d(current_year)

    def get_form_4797_section_1231_loss(self, current_year: int = 2025) -> float:
        """
        Get Section 1231 loss (treated as ordinary loss).

        Net Section 1231 losses are fully deductible as ordinary losses.
        """
        if not self.form_4797:
            return 0.0
        return self.form_4797.get_section_1231_loss_for_schedule_d(current_year)

    def get_form_4797_unrecaptured_1250_gain(self) -> float:
        """
        Get unrecaptured Section 1250 gain (taxed at max 25%).

        Unrecaptured 1250 gain is the depreciation on real property
        that is recaptured at a maximum 25% rate (not ordinary income).
        """
        if not self.form_4797:
            return 0.0
        return self.form_4797.get_unrecaptured_1250_gain()

    def get_form_4797_depreciation_recapture(self, current_year: int = 2025) -> float:
        """
        Get total depreciation recapture (ordinary income portion).

        Includes:
        - Section 1245 recapture (100% of depreciation on personal property)
        - Section 1250 additional depreciation (excess over straight-line)
        """
        if not self.form_4797:
            return 0.0
        result = self.form_4797.calculate_part_iii()
        return result['total_ordinary_income']

    def get_form_4797_summary(self, current_year: int = 2025) -> Optional[dict]:
        """Get complete Form 4797 summary."""
        if not self.form_4797:
            return None
        return self.form_4797.generate_form_4797_summary(current_year)

    # ========== Form 6252 Installment Sale Income Methods ==========

    def get_form_6252_installment_income(self) -> float:
        """
        Get total installment sale income from Form 6252.

        This is the capital gain portion recognized in the current year
        based on payments received × gross profit percentage.
        """
        if not self.form_6252:
            return 0.0
        return self.form_6252.get_total_installment_income()

    def get_form_6252_interest_income(self) -> float:
        """
        Get total interest income from installment sales.

        Interest on installment notes is ordinary income.
        """
        if not self.form_6252:
            return 0.0
        return self.form_6252.get_total_interest_income()

    def get_form_6252_depreciation_recapture(self) -> float:
        """
        Get depreciation recapture from installment sales.

        Depreciation recapture is recognized in year of sale,
        NOT deferred under installment method.
        """
        if not self.form_6252:
            return 0.0
        return self.form_6252.get_total_depreciation_recapture()

    def get_form_6252_capital_gain(self) -> float:
        """
        Get total capital gain from installment sales.

        Capital gain component of installment payments.
        """
        if not self.form_6252:
            return 0.0
        return self.form_6252.get_total_capital_gain()

    def get_form_6252_ordinary_income(self) -> float:
        """
        Get total ordinary income from installment sales.

        Includes interest, depreciation recapture, and related party acceleration.
        """
        if not self.form_6252:
            return 0.0
        return self.form_6252.get_total_ordinary_income()

    def get_form_6252_unrecaptured_1250_gain(self) -> float:
        """
        Get unrecaptured Section 1250 gain from installment sales.

        This portion is taxed at a maximum 25% rate.
        """
        if not self.form_6252:
            return 0.0
        return self.form_6252.get_unrecaptured_1250_gain()

    def get_form_6252_section_453a_interest(self) -> float:
        """
        Get Section 453A interest charge for large installment sales.

        Applies to sales exceeding $5,000,000 threshold.
        """
        if not self.form_6252:
            return 0.0
        return self.form_6252.get_section_453a_interest_charge()

    def get_form_6252_summary(self) -> Optional[dict]:
        """Get complete Form 6252 summary."""
        if not self.form_6252:
            return None
        return self.form_6252.generate_form_6252_summary()

    # ========== Form 8582 Passive Activity Loss Methods ==========

    def get_form_8582_passive_loss_allowed(self) -> float:
        """
        Get total passive activity loss allowed for current year.

        This is the amount of passive losses that can be deducted,
        including the $25k rental allowance and losses against passive income.
        """
        if not self.form_8582:
            return 0.0
        return self.form_8582.get_total_passive_loss_allowed()

    def get_form_8582_suspended_loss(self) -> float:
        """
        Get suspended passive loss to carry forward.

        These are losses that exceed passive income and the special
        rental allowance, carried forward to future years.
        """
        if not self.form_8582:
            return 0.0
        return self.form_8582.get_suspended_loss_carryforward()

    def get_form_8582_rental_allowance(self) -> float:
        """
        Get $25,000 rental real estate loss allowance used.

        This is the amount of rental losses allowed against non-passive
        income under the active participation exception.
        """
        if not self.form_8582:
            return 0.0
        return self.form_8582.get_rental_allowance_used()

    def get_form_8582_net_passive_income(self) -> float:
        """
        Get net passive income (if positive).

        If passive income exceeds passive losses, this is the net amount.
        """
        if not self.form_8582:
            return 0.0
        return self.form_8582.get_net_passive_income()

    def get_form_8582_summary(self) -> Optional[dict]:
        """Get complete Form 8582 summary."""
        if not self.form_8582:
            return None
        return self.form_8582.generate_form_8582_summary()

    # ========== Form 6251 - Alternative Minimum Tax Helpers ==========

    def get_form_6251_total_adjustments(self) -> float:
        """
        Get total AMT adjustments from Form 6251.

        Returns the sum of all AMT adjustments and preferences
        including SALT add-back, ISO spread, PAB interest, etc.
        """
        if self.form_6251:
            part_i = self.form_6251.calculate_part_i()
            return part_i.get('total_adjustments', 0.0)

        # Fall back to individual AMT fields
        return (
            self.amt_iso_exercise_spread +
            self.amt_private_activity_bond_interest +
            self.amt_depletion_excess +
            self.amt_intangible_drilling_costs +
            self.amt_circulation_expenditures +
            self.amt_mining_exploration_costs +
            self.amt_research_experimental_costs +
            self.amt_depreciation_adjustment +
            self.amt_passive_activity_adjustment +
            self.amt_loss_limitations_adjustment +
            self.amt_long_term_contracts +
            self.amt_other_adjustments
        )

    def get_form_6251_iso_spread(self) -> float:
        """
        Get ISO exercise spread for AMT.

        This is the bargain element from incentive stock option exercises.
        """
        if self.form_6251:
            total_iso = self.form_6251.line_2i_iso
            # Add from detailed records
            for iso in self.form_6251.iso_exercises:
                total_iso += iso.get_amt_adjustment()
            return total_iso
        return self.amt_iso_exercise_spread

    def get_form_6251_pab_interest(self) -> float:
        """
        Get private activity bond interest for AMT.

        Tax-exempt interest from private activity bonds is an AMT preference.
        """
        if self.form_6251:
            total_pab = self.form_6251.line_2g_pab_interest
            for pab in self.form_6251.private_activity_bonds:
                total_pab += pab.get_amt_adjustment()
            return total_pab
        return self.amt_private_activity_bond_interest

    def get_form_6251_amti(self, taxable_income: float) -> float:
        """
        Calculate Alternative Minimum Taxable Income.

        Args:
            taxable_income: Regular taxable income from Form 1040

        Returns:
            AMTI (taxable income + AMT adjustments)
        """
        if self.form_6251:
            self.form_6251.taxable_income = taxable_income
            part_i = self.form_6251.calculate_part_i()
            return part_i.get('line_4_amti', taxable_income)

        # Calculate from individual fields
        adjustments = self.get_form_6251_total_adjustments()
        return taxable_income + adjustments

    def get_form_6251_summary(self) -> Optional[dict]:
        """Get Form 6251 AMT summary."""
        if not self.form_6251:
            return None
        return self.form_6251.get_amt_summary()

    def has_amt_preference_items(self) -> bool:
        """
        Check if taxpayer has any AMT preference items.

        Returns True if any of the common AMT triggers are present.
        """
        if self.form_6251:
            summary = self.form_6251.get_amt_summary()
            return summary.get('total_adjustments', 0) > 0

        return (
            self.amt_iso_exercise_spread > 0 or
            self.amt_private_activity_bond_interest > 0 or
            self.amt_depreciation_adjustment != 0 or
            self.amt_passive_activity_adjustment != 0 or
            self.amt_depletion_excess > 0 or
            self.amt_intangible_drilling_costs > 0
        )

    # ========== Form 8801 - Minimum Tax Credit Helpers ==========

    def get_form_8801_credit_available(self) -> float:
        """
        Get total minimum tax credit available from prior years.

        This is the carryforward from prior year AMT paid on deferral items.
        """
        if self.form_8801:
            part_ii = self.form_8801.calculate_part_ii()
            return part_ii.get('line_23_total_mtc', 0.0)
        return self.prior_year_amt_credit

    def get_form_8801_credit_limit(
        self,
        regular_tax: float,
        tmt: float
    ) -> float:
        """
        Calculate the credit limit for minimum tax credit.

        The MTC can only reduce regular tax to TMT, not below.

        Args:
            regular_tax: Regular tax before credits
            tmt: Tentative minimum tax

        Returns:
            Maximum MTC that can be used
        """
        return max(0, regular_tax - tmt)

    def get_form_8801_credit_allowed(
        self,
        regular_tax: float,
        tmt: float
    ) -> float:
        """
        Calculate the minimum tax credit allowed for current year.

        Args:
            regular_tax: Regular tax before credits
            tmt: Tentative minimum tax

        Returns:
            MTC that can be used this year
        """
        credit_available = self.get_form_8801_credit_available()
        credit_limit = self.get_form_8801_credit_limit(regular_tax, tmt)
        return min(credit_available, credit_limit)

    def get_form_8801_carryforward(
        self,
        regular_tax: float,
        tmt: float
    ) -> float:
        """
        Calculate the MTC carryforward to next year.

        Args:
            regular_tax: Regular tax before credits
            tmt: Tentative minimum tax

        Returns:
            Unused MTC to carry forward
        """
        credit_available = self.get_form_8801_credit_available()
        credit_allowed = self.get_form_8801_credit_allowed(regular_tax, tmt)
        return credit_available - credit_allowed

    def get_form_8801_summary(self) -> Optional[dict]:
        """Get Form 8801 minimum tax credit summary."""
        if not self.form_8801:
            return None
        return self.form_8801.get_credit_summary()

    def has_mtc_carryforward(self) -> bool:
        """Check if taxpayer has minimum tax credit carryforward."""
        if self.form_8801:
            return self.form_8801.total_mtc_carryforward > 0 or len(self.form_8801.mtc_carryforwards) > 0
        return self.prior_year_amt_credit > 0

    # =========================================================================
    # Form 1116 Helper Methods - Foreign Tax Credit
    # =========================================================================

    def get_form_1116_foreign_taxes_paid(self) -> float:
        """Get total foreign taxes paid from Form 1116."""
        if self.form_1116:
            return self.form_1116.get_total_foreign_taxes_paid()
        # Fall back to K-1 foreign taxes if available
        return self.get_k1_foreign_tax_paid()

    def get_form_1116_foreign_source_income(self) -> float:
        """Get total foreign source income from Form 1116."""
        if self.form_1116:
            return self.form_1116.get_total_foreign_source_income()
        return 0.0

    def get_form_1116_credit_allowed(
        self,
        total_taxable_income: float,
        total_tax_before_credits: float,
        filing_status: str = "single"
    ) -> float:
        """
        Calculate allowed FTC from Form 1116.

        Args:
            total_taxable_income: Total taxable income for limitation calc
            total_tax_before_credits: Tax liability before credits
            filing_status: Filing status for simplified method threshold

        Returns:
            Allowed foreign tax credit amount
        """
        if self.form_1116:
            # Update tax info for calculation
            self.form_1116.total_taxable_income = total_taxable_income
            self.form_1116.total_tax_before_credits = total_tax_before_credits
            result = self.form_1116.calculate_ftc(filing_status=filing_status)
            return result['total_ftc_allowed']
        return 0.0

    def get_form_1116_carryforward(
        self,
        total_taxable_income: float,
        total_tax_before_credits: float,
        filing_status: str = "single"
    ) -> float:
        """
        Get new FTC carryforward from Form 1116.

        Returns excess foreign taxes that can be carried forward 10 years.
        """
        if self.form_1116:
            self.form_1116.total_taxable_income = total_taxable_income
            self.form_1116.total_tax_before_credits = total_tax_before_credits
            result = self.form_1116.calculate_ftc(filing_status=filing_status)
            return result['new_carryforward']
        return 0.0

    def get_form_1116_summary(
        self,
        total_taxable_income: float,
        total_tax_before_credits: float,
        filing_status: str = "single"
    ) -> Optional[dict]:
        """Get complete Form 1116 foreign tax credit summary."""
        if not self.form_1116:
            return None
        self.form_1116.total_taxable_income = total_taxable_income
        self.form_1116.total_tax_before_credits = total_tax_before_credits
        return self.form_1116.calculate_ftc(filing_status=filing_status)

    def can_use_simplified_ftc(self, filing_status: str = "single") -> bool:
        """Check if simplified FTC method can be used (no Form 1116 required)."""
        if self.form_1116:
            return self.form_1116.can_use_simplified_method(filing_status)
        # If no Form 1116, check threshold based on K-1 foreign taxes
        threshold = 600.0 if filing_status == "married_joint" else 300.0
        return self.get_k1_foreign_tax_paid() <= threshold

    def has_foreign_tax_credit(self) -> bool:
        """Check if taxpayer has foreign taxes for potential credit."""
        if self.form_1116:
            return self.form_1116.get_total_foreign_taxes_paid() > 0
        return self.get_k1_foreign_tax_paid() > 0

    # =========================================================================
    # Form 8615 Helper Methods - Kiddie Tax
    # =========================================================================

    def get_form_8615_kiddie_tax(self) -> float:
        """Get kiddie tax amount from Form 8615."""
        if self.form_8615:
            result = self.form_8615.calculate_kiddie_tax()
            return result.get('kiddie_tax_increase', 0.0)
        return 0.0

    def get_form_8615_total_child_tax(self) -> float:
        """Get total child's tax from Form 8615."""
        if self.form_8615:
            result = self.form_8615.calculate_kiddie_tax()
            return result.get('total_child_tax', 0.0)
        return 0.0

    def is_subject_to_kiddie_tax(self) -> bool:
        """Check if child is subject to kiddie tax rules."""
        if self.form_8615:
            return self.form_8615.is_subject_to_kiddie_tax()
        return False

    def get_form_8615_summary(self) -> Optional[dict]:
        """Get complete Form 8615 kiddie tax calculation summary."""
        if not self.form_8615:
            return None
        return self.form_8615.calculate_kiddie_tax()

    def get_form_8615_net_unearned_income(self) -> float:
        """Get net unearned income subject to parent's rate."""
        if self.form_8615:
            result = self.form_8615.calculate_net_unearned_income()
            return result.get('line_5_net_unearned_income', 0.0)
        return 0.0

    # =========================================================================
    # Form 2555 Helper Methods - Foreign Earned Income Exclusion
    # =========================================================================

    def get_foreign_earned_income_exclusion(self) -> float:
        """Get foreign earned income exclusion from Form 2555."""
        if self.form_2555:
            result = self.form_2555.calculate_exclusion()
            return result.get('foreign_earned_income_exclusion', 0.0)
        return 0.0

    def get_foreign_housing_exclusion(self) -> float:
        """Get foreign housing exclusion from Form 2555."""
        if self.form_2555:
            result = self.form_2555.calculate_exclusion()
            return result.get('housing_exclusion', 0.0)
        return 0.0

    def get_foreign_housing_deduction(self) -> float:
        """Get foreign housing deduction from Form 2555."""
        if self.form_2555:
            result = self.form_2555.calculate_exclusion()
            return result.get('housing_deduction', 0.0)
        return 0.0

    def get_total_form_2555_exclusion(self) -> float:
        """Get total exclusion (FEIE + housing) from Form 2555."""
        if self.form_2555:
            result = self.form_2555.calculate_exclusion()
            return result.get('total_exclusion', 0.0)
        return 0.0

    def qualifies_for_foreign_earned_income_exclusion(self) -> bool:
        """Check if taxpayer qualifies for FEIE."""
        if self.form_2555:
            qualifies, _ = self.form_2555.qualifies_for_exclusion()
            return qualifies
        return False

    def get_form_2555_summary(self) -> Optional[dict]:
        """Get complete Form 2555 calculation summary."""
        if not self.form_2555:
            return None
        return self.form_2555.calculate_exclusion()

    # =========================================================================
    # Schedule H Helper Methods - Household Employment Taxes
    # =========================================================================

    def get_household_employment_tax(self) -> float:
        """Get total household employment tax from Schedule H."""
        if self.schedule_h:
            result = self.schedule_h.calculate_schedule_h()
            return result.get('total_household_employment_tax', 0.0)
        return 0.0

    def must_file_schedule_h(self) -> bool:
        """Check if Schedule H must be filed."""
        if self.schedule_h:
            must_file, _ = self.schedule_h.is_subject_to_household_employment_taxes()
            return must_file
        return False

    def get_schedule_h_summary(self) -> Optional[dict]:
        """Get complete Schedule H calculation summary."""
        if not self.schedule_h:
            return None
        return self.schedule_h.calculate_schedule_h()

    # =========================================================================
    # Form 4952 Helper Methods - Investment Interest Expense
    # =========================================================================

    def get_investment_interest_deduction(self) -> float:
        """Get allowable investment interest deduction from Form 4952."""
        if self.form_4952:
            result = self.form_4952.calculate_deduction()
            return result.get('line_8_allowable_deduction', 0.0)
        return 0.0

    def get_investment_interest_carryforward(self) -> float:
        """Get investment interest carryforward to next year."""
        if self.form_4952:
            result = self.form_4952.calculate_deduction()
            return result.get('carryforward_to_next_year', 0.0)
        return 0.0

    def get_form_4952_summary(self) -> Optional[dict]:
        """Get complete Form 4952 calculation summary."""
        if not self.form_4952:
            return None
        return self.form_4952.calculate_deduction()

    # =========================================================================
    # Form 5471 Helper Methods - Foreign Corporation Reporting
    # =========================================================================

    def get_total_subpart_f_income(self) -> float:
        """Get total Subpart F income inclusion from all Form 5471s."""
        total = 0.0
        for form in self.form_5471_list:
            result = form.calculate_subpart_f_inclusion()
            total += result.get('inclusion_in_income', 0.0)
        return total

    def get_total_gilti_income(self) -> float:
        """Get total GILTI income inclusion from all Form 5471s."""
        total = 0.0
        for form in self.form_5471_list:
            result = form.calculate_gilti_inclusion()
            total += result.get('net_gilti_inclusion', 0.0)
        return total

    def get_total_cfc_income_inclusion(self) -> float:
        """Get total CFC income inclusion (Subpart F + GILTI)."""
        return self.get_total_subpart_f_income() + self.get_total_gilti_income()

    def has_cfc_interests(self) -> bool:
        """Check if taxpayer has CFC interests requiring Form 5471."""
        return len(self.form_5471_list) > 0

    def get_form_5471_summaries(self) -> List[dict]:
        """Get summaries for all Form 5471s."""
        return [form.get_form_5471_summary() for form in self.form_5471_list]

    # =========================================================================
    # Form 1040-X Helper Methods - Amended Returns
    # =========================================================================

    def is_amended_return(self) -> bool:
        """Check if this is an amended return."""
        return self.form_1040x is not None

    def get_amendment_refund_due(self) -> float:
        """Get refund due from amended return."""
        if self.form_1040x:
            result = self.form_1040x.calculate_refund_or_amount_owed()
            return result.get('refund_due', 0.0)
        return 0.0

    def get_amendment_amount_owed(self) -> float:
        """Get additional amount owed from amended return."""
        if self.form_1040x:
            result = self.form_1040x.calculate_refund_or_amount_owed()
            return result.get('amount_owed', 0.0)
        return 0.0

    def get_form_1040x_summary(self) -> Optional[dict]:
        """Get complete Form 1040-X calculation summary."""
        if not self.form_1040x:
            return None
        return self.form_1040x.calculate_amended_return()

    # =========================================================================
    # Schedule A - Itemized Deductions
    # =========================================================================
    def get_schedule_a_summary(self) -> Optional[dict]:
        """Get complete Schedule A itemized deductions summary."""
        if not self.schedule_a:
            return None
        return self.schedule_a.get_schedule_a_summary()

    def get_schedule_a_total_deductions(self) -> float:
        """Get total itemized deductions from Schedule A."""
        if self.schedule_a:
            return self.schedule_a.calculate_schedule_a().get('line_17_total_itemized', 0.0)
        return 0.0

    def get_schedule_a_medical_deduction(self) -> float:
        """Get medical expense deduction (after 7.5% AGI floor)."""
        if self.schedule_a:
            return self.schedule_a.calculate_medical_deduction().get('deductible_amount', 0.0)
        return 0.0

    def get_schedule_a_salt_deduction(self) -> float:
        """Get SALT deduction (capped at $10,000)."""
        if self.schedule_a:
            return self.schedule_a.calculate_taxes_paid_deduction().get('deductible_amount', 0.0)
        return 0.0

    def get_schedule_a_charitable_deduction(self) -> float:
        """Get charitable contributions deduction."""
        if self.schedule_a:
            return self.schedule_a.calculate_charitable_deduction().get('deductible_amount', 0.0)
        return 0.0

    # =========================================================================
    # Schedule B - Interest and Ordinary Dividends
    # =========================================================================
    def get_schedule_b_summary(self) -> Optional[dict]:
        """Get complete Schedule B summary."""
        if not self.schedule_b:
            return None
        return self.schedule_b.get_schedule_b_summary()

    def get_schedule_b_total_interest(self) -> float:
        """Get total taxable interest from Schedule B."""
        if self.schedule_b:
            return self.schedule_b.calculate_schedule_b().get('form_1040_line_2b_taxable_interest', 0.0)
        return 0.0

    def get_schedule_b_total_dividends(self) -> float:
        """Get total ordinary dividends from Schedule B."""
        if self.schedule_b:
            return self.schedule_b.calculate_schedule_b().get('form_1040_line_3b_ordinary_dividends', 0.0)
        return 0.0

    def get_schedule_b_qualified_dividends(self) -> float:
        """Get qualified dividends from Schedule B."""
        if self.schedule_b:
            return self.schedule_b.calculate_schedule_b().get('form_1040_line_3a_qualified_dividends', 0.0)
        return 0.0

    def get_schedule_b_requires_part_iii(self) -> bool:
        """Check if Schedule B Part III (foreign accounts) is required."""
        if self.schedule_b:
            return self.schedule_b.has_foreign_accounts or len(self.schedule_b.foreign_accounts) > 0
        return False

    # =========================================================================
    # Schedule D - Capital Gains and Losses
    # =========================================================================
    def get_schedule_d_summary(self) -> Optional[dict]:
        """Get complete Schedule D summary."""
        if not self.schedule_d:
            return None
        return self.schedule_d.get_schedule_d_summary()

    def get_schedule_d_net_gain_loss(self) -> float:
        """Get net capital gain or loss from Schedule D."""
        if self.schedule_d:
            return self.schedule_d.calculate_schedule_d().get('net_capital_gain_loss', 0.0)
        return 0.0

    def get_schedule_d_short_term_net(self) -> float:
        """Get net short-term capital gain/loss."""
        if self.schedule_d:
            return self.schedule_d.calculate_schedule_d().get('net_short_term_gain_loss', 0.0)
        return 0.0

    def get_schedule_d_long_term_net(self) -> float:
        """Get net long-term capital gain/loss."""
        if self.schedule_d:
            return self.schedule_d.calculate_schedule_d().get('net_long_term_gain_loss', 0.0)
        return 0.0

    def get_schedule_d_loss_carryforward(self) -> Tuple[float, float]:
        """Get new loss carryforward amounts (short-term, long-term)."""
        if self.schedule_d:
            result = self.schedule_d.calculate_schedule_d()
            return (
                result.get('new_st_carryover', 0.0),
                result.get('new_lt_carryover', 0.0)
            )
        return (0.0, 0.0)

    def get_schedule_d_28_rate_gain(self) -> float:
        """Get 28% rate gain (collectibles and Section 1202)."""
        if self.schedule_d:
            part_ii = self.schedule_d.calculate_schedule_d().get('part_ii', {})
            return part_ii.get('line_18_28_pct_rate_gain', 0.0)
        return 0.0

    def get_schedule_d_unrecaptured_1250(self) -> float:
        """Get unrecaptured Section 1250 gain (25% rate)."""
        if self.schedule_d:
            part_ii = self.schedule_d.calculate_schedule_d().get('part_ii', {})
            return part_ii.get('line_19_unrecaptured_1250', 0.0)
        return 0.0

    # =========================================================================
    # Schedule E - Supplemental Income and Loss
    # =========================================================================
    def get_schedule_e_summary(self) -> Optional[dict]:
        """Get complete Schedule E summary."""
        if not self.schedule_e:
            return None
        return self.schedule_e.get_schedule_e_summary()

    def get_schedule_e_total(self) -> float:
        """Get total supplemental income/loss from Schedule E."""
        if self.schedule_e:
            return self.schedule_e.calculate_schedule_e().get('total_supplemental_income', 0.0)
        return 0.0

    def get_schedule_e_rental_income(self) -> float:
        """Get Part I rental/royalty income or loss."""
        if self.schedule_e:
            return self.schedule_e.calculate_schedule_e().get('part_i_rental_total', 0.0)
        return 0.0

    def get_schedule_e_partnership_income(self) -> float:
        """Get Part II partnership/S-corp income."""
        if self.schedule_e:
            return self.schedule_e.calculate_schedule_e().get('part_ii_partnership_total', 0.0)
        return 0.0

    def get_schedule_e_estate_trust_income(self) -> float:
        """Get Part III estate/trust income."""
        if self.schedule_e:
            return self.schedule_e.calculate_schedule_e().get('part_iii_estate_trust_total', 0.0)
        return 0.0

    def get_schedule_e_se_income(self) -> float:
        """Get self-employment income from Schedule E partnerships."""
        if self.schedule_e:
            result = self.schedule_e.calculate_part_ii_partnerships()
            return result.get('total_self_employment', 0.0)
        return 0.0

    def get_schedule_e_qbi(self) -> float:
        """Get qualified business income from Schedule E."""
        if self.schedule_e:
            result = self.schedule_e.calculate_part_ii_partnerships()
            return result.get('total_qbi', 0.0)
        return 0.0

    # =========================================================================
    # Schedule F - Profit or Loss From Farming
    # =========================================================================
    def get_schedule_f_summary(self) -> Optional[dict]:
        """Get complete Schedule F summary."""
        if not self.schedule_f:
            return None
        return self.schedule_f.get_schedule_f_summary()

    def get_schedule_f_net_profit_loss(self) -> float:
        """Get net farm profit or loss from Schedule F."""
        if self.schedule_f:
            return self.schedule_f.calculate_schedule_f().get('net_farm_profit_loss', 0.0)
        return 0.0

    def get_schedule_f_gross_income(self) -> float:
        """Get gross farm income."""
        if self.schedule_f:
            return self.schedule_f.calculate_schedule_f().get('gross_farm_income', 0.0)
        return 0.0

    def get_schedule_f_expenses(self) -> float:
        """Get total farm expenses."""
        if self.schedule_f:
            return self.schedule_f.calculate_schedule_f().get('total_farm_expenses', 0.0)
        return 0.0

    def get_schedule_f_se_income(self) -> float:
        """Get self-employment income from Schedule F (if materially participated)."""
        if self.schedule_f:
            return self.schedule_f.calculate_schedule_f().get('schedule_se_income', 0.0)
        return 0.0

    # =========================================================================
    # Form 6781 - Section 1256 Contracts and Straddles
    # =========================================================================
    def get_form_6781_summary(self) -> Optional[dict]:
        """Get complete Form 6781 summary."""
        if not self.form_6781:
            return None
        return self.form_6781.get_form_6781_summary()

    def get_form_6781_section_1256_net(self) -> float:
        """Get net Section 1256 gain/loss."""
        if self.form_6781:
            return self.form_6781.calculate_form_6781().get('section_1256_net', 0.0)
        return 0.0

    def get_form_6781_short_term(self) -> float:
        """Get 40% short-term portion of Section 1256 gain/loss."""
        if self.form_6781:
            return self.form_6781.calculate_form_6781().get('section_1256_short_term', 0.0)
        return 0.0

    def get_form_6781_long_term(self) -> float:
        """Get 60% long-term portion of Section 1256 gain/loss."""
        if self.form_6781:
            return self.form_6781.calculate_form_6781().get('section_1256_long_term', 0.0)
        return 0.0

    def get_form_6781_straddle_net(self) -> float:
        """Get net straddle gain/loss."""
        if self.form_6781:
            return self.form_6781.calculate_form_6781().get('straddle_net', 0.0)
        return 0.0

    # =========================================================================
    # Form 8814 - Parent's Election to Report Child's Interest and Dividends
    # =========================================================================
    def get_form_8814_summary(self) -> Optional[dict]:
        """Get complete Form 8814 summary."""
        if not self.form_8814:
            return None
        return self.form_8814.get_form_8814_summary()

    def get_form_8814_income_to_include(self) -> float:
        """Get child's income to include on parent's return."""
        if self.form_8814:
            return self.form_8814.calculate_form_8814().get('total_to_include_in_income', 0.0)
        return 0.0

    def get_form_8814_child_tax(self) -> float:
        """Get tax on child's income at parent's election."""
        if self.form_8814:
            return self.form_8814.calculate_form_8814().get('total_child_tax', 0.0)
        return 0.0

    def get_form_8814_qualifying_children_count(self) -> int:
        """Get count of qualifying children for Form 8814."""
        if self.form_8814:
            return self.form_8814.calculate_form_8814().get('qualifying_children', 0)
        return 0

    # =========================================================================
    # Form 8995 - Qualified Business Income Deduction
    # =========================================================================
    def get_form_8995_summary(self) -> Optional[dict]:
        """Get complete Form 8995 summary."""
        if not self.form_8995:
            return None
        return self.form_8995.get_form_8995_summary()

    def get_form_8995_deduction(self) -> float:
        """Get QBI deduction from Form 8995."""
        if self.form_8995:
            return self.form_8995.calculate_form_8995().get('qbi_deduction', 0.0)
        return 0.0

    def get_form_8995_is_below_threshold(self) -> bool:
        """Check if Form 8995 uses simplified method (below threshold)."""
        if self.form_8995:
            return self.form_8995.is_below_threshold()
        return True

    def get_form_8995_loss_carryforward(self) -> float:
        """Get new QBI loss carryforward."""
        if self.form_8995:
            result = self.form_8995.calculate_form_8995()
            return result.get('new_loss_carryforward', 0.0)
        return 0.0
