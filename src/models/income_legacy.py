from typing import Optional, List, Tuple
from pydantic import BaseModel, Field
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal

from models.schedule_c import ScheduleCBusiness
from models.form_8949 import SecuritiesPortfolio, WashSaleInfo
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
    ALIMONY = "alimony"
    ANNUITY = "annuity"
    STOCK_COMPENSATION = "stock_compensation"
    DEBT_CANCELLATION = "debt_cancellation"
    OTHER = "other"


class Form1099RDistributionCode(str, Enum):
    """
    IRS Form 1099-R Distribution Codes (Box 7).

    These codes indicate the type of distribution and its tax treatment.
    """
    CODE_1 = "1"  # Early distribution, no known exception
    CODE_2 = "2"  # Early distribution, exception applies
    CODE_3 = "3"  # Disability
    CODE_4 = "4"  # Death
    CODE_5 = "5"  # Prohibited transaction
    CODE_6 = "6"  # Section 1035 exchange
    CODE_7 = "7"  # Normal distribution
    CODE_8 = "8"  # Excess contributions plus earnings/excess deferrals
    CODE_9 = "9"  # Cost of current life insurance protection (PS 58 costs)
    CODE_A = "A"  # May be eligible for 10-year tax option
    CODE_B = "B"  # Designated Roth account distribution
    CODE_C = "C"  # Reportable death benefits (Section 6050Y)
    CODE_D = "D"  # Annuity payments from nonqualified annuities
    CODE_E = "E"  # Distributions under EPCRS
    CODE_F = "F"  # Charitable gift annuity
    CODE_G = "G"  # Direct rollover
    CODE_H = "H"  # Direct rollover of designated Roth
    CODE_J = "J"  # Early distribution from Roth IRA, no exception
    CODE_K = "K"  # Distribution of IRA assets not having RLH
    CODE_L = "L"  # Loans treated as distributions
    CODE_M = "M"  # Qualified plan loan offset
    CODE_N = "N"  # Recharacterized IRA contribution
    CODE_P = "P"  # Excess contributions plus earnings (prior year)
    CODE_Q = "Q"  # Qualified distribution from Roth IRA
    CODE_R = "R"  # Recharacterized IRA contribution (prior year)
    CODE_S = "S"  # Early distribution from SIMPLE IRA (first 2 years)
    CODE_T = "T"  # Roth IRA distribution, exception applies
    CODE_U = "U"  # Dividend distribution from ESOP
    CODE_W = "W"  # Charges or payments for LTC contracts


class StockCompensationType(str, Enum):
    """Types of equity-based compensation."""
    ISO = "iso"  # Incentive Stock Options (Form 3921)
    NSO = "nso"  # Non-Qualified Stock Options
    RSA = "rsa"  # Restricted Stock Awards (Section 83(b))
    RSU = "rsu"  # Restricted Stock Units
    ESPP = "espp"  # Employee Stock Purchase Plan (Form 3922)
    SAR = "sar"  # Stock Appreciation Rights
    PHANTOM_STOCK = "phantom_stock"  # Phantom Stock/Stock Units


class DebtCancellationType(str, Enum):
    """Types of canceled debt per Form 1099-C Box 6."""
    BANKRUPTCY = "A"  # Bankruptcy
    FORECLOSURE = "B"  # Foreclosure
    STUDENT_LOAN = "C"  # Student loan
    DEBT_RELIEF = "D"  # Debt relief
    DECEASED = "E"  # Deceased
    IDENTITY_THEFT = "F"  # Identity theft
    PRESCRIPTION = "G"  # Prescription expiration
    OTHER = "H"  # Other


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


class Form1099R(BaseModel):
    """
    Form 1099-R: Distributions from Pensions, Annuities, Retirement, IRAs, etc.

    Reports distributions from:
    - Pensions and annuities
    - 401(k), 403(b), 457 plans
    - IRAs (Traditional, Roth, SEP, SIMPLE)
    - Life insurance contracts
    - Profit-sharing plans
    """
    payer_name: str = Field(description="Name of payer (Box)")
    payer_ein: Optional[str] = Field(None, description="Payer's TIN")

    # Box 1: Gross Distribution
    gross_distribution: float = Field(default=0.0, ge=0, description="Box 1: Gross distribution")

    # Box 2a: Taxable Amount
    taxable_amount: float = Field(default=0.0, ge=0, description="Box 2a: Taxable amount")
    taxable_amount_not_determined: bool = Field(default=False, description="Box 2b: Taxable amount not determined")
    total_distribution: bool = Field(default=False, description="Box 2b: Total distribution")

    # Box 3: Capital Gain (included in Box 2a)
    capital_gain: float = Field(default=0.0, ge=0, description="Box 3: Capital gain (included in Box 2a)")

    # Box 4: Federal Income Tax Withheld
    federal_tax_withheld: float = Field(default=0.0, ge=0, description="Box 4: Federal income tax withheld")

    # Box 5: Employee Contributions/Insurance Premiums
    employee_contributions: float = Field(default=0.0, ge=0, description="Box 5: Employee contributions/designated Roth contributions or insurance premiums")

    # Box 6: Net Unrealized Appreciation (NUA)
    nua_employer_securities: float = Field(default=0.0, ge=0, description="Box 6: Net unrealized appreciation in employer's securities")

    # Box 7: Distribution Code(s)
    distribution_code_1: Optional[Form1099RDistributionCode] = Field(None, description="Box 7: Distribution code 1")
    distribution_code_2: Optional[Form1099RDistributionCode] = Field(None, description="Box 7: Distribution code 2")
    ira_sep_simple: bool = Field(default=False, description="Box 7: IRA/SEP/SIMPLE checkbox")

    # Box 8: Other (for annuity contracts)
    other_amount: float = Field(default=0.0, ge=0, description="Box 8: Other")
    other_percentage: float = Field(default=0.0, ge=0, le=100, description="Box 8: Your percentage of total distribution")

    # Box 9a-9b: Total Employee Contributions
    total_employee_contributions: float = Field(default=0.0, ge=0, description="Box 9a: Total employee contributions")

    # Box 10: Amount Allocable to IRR
    amount_allocable_irr: float = Field(default=0.0, ge=0, description="Box 10: Amount allocable to IRR within 5 years")

    # Box 11: First Year of Designated Roth Contributions
    first_year_roth: Optional[int] = Field(None, description="Box 11: 1st year of designated Roth contributions")

    # State tax information (Boxes 12-17)
    state_code: Optional[str] = Field(None, description="Box 13: State")
    state_id_number: Optional[str] = Field(None, description="Box 14: State payer's ID no.")
    state_distribution: float = Field(default=0.0, ge=0, description="Box 15: State distribution")
    state_tax_withheld: float = Field(default=0.0, ge=0, description="Box 12: State tax withheld")

    # Local tax information
    local_tax_withheld: float = Field(default=0.0, ge=0, description="Box 16: Local tax withheld")
    local_distribution: float = Field(default=0.0, ge=0, description="Box 18: Local distribution")
    locality_name: Optional[str] = Field(None, description="Box 19: Name of locality")

    # Additional tracking
    is_annuity: bool = Field(default=False, description="Distribution from annuity contract")
    is_qualified_plan: bool = Field(default=True, description="From qualified retirement plan")
    account_type: Optional[str] = Field(None, description="Account type: 401k, IRA, Pension, Annuity, etc.")

    def is_early_distribution(self) -> bool:
        """Check if this is an early distribution (potentially subject to 10% penalty)."""
        early_codes = [Form1099RDistributionCode.CODE_1, Form1099RDistributionCode.CODE_J, Form1099RDistributionCode.CODE_S]
        return self.distribution_code_1 in early_codes

    def is_rollover(self) -> bool:
        """Check if this is a rollover (not taxable)."""
        rollover_codes = [Form1099RDistributionCode.CODE_G, Form1099RDistributionCode.CODE_H]
        return self.distribution_code_1 in rollover_codes


class StockCompensationEvent(BaseModel):
    """
    Stock compensation event (ISO, NSO, RSA, RSU, ESPP).

    Tracks equity compensation tax events including:
    - Grant, vest, exercise, and sale events
    - FMV at various dates for income calculation
    - AMT adjustments for ISOs
    - Section 83(b) elections for RSAs
    """
    compensation_type: StockCompensationType
    company_name: str = Field(description="Employer company name")
    company_ein: Optional[str] = Field(None, description="Employer EIN")

    # Grant information
    grant_date: Optional[str] = Field(None, description="Date of grant (YYYY-MM-DD)")
    shares_granted: float = Field(default=0.0, ge=0, description="Number of shares granted")
    grant_price: float = Field(default=0.0, ge=0, description="Grant/strike price per share")

    # Vest information
    vest_date: Optional[str] = Field(None, description="Date of vesting (YYYY-MM-DD)")
    shares_vested: float = Field(default=0.0, ge=0, description="Number of shares vested")
    fmv_at_vest: float = Field(default=0.0, ge=0, description="Fair market value per share at vest")

    # Exercise information (for options)
    exercise_date: Optional[str] = Field(None, description="Date of exercise (YYYY-MM-DD)")
    shares_exercised: float = Field(default=0.0, ge=0, description="Number of shares exercised")
    fmv_at_exercise: float = Field(default=0.0, ge=0, description="FMV per share at exercise")
    exercise_price_paid: float = Field(default=0.0, ge=0, description="Total exercise price paid")

    # Sale information
    sale_date: Optional[str] = Field(None, description="Date of sale (YYYY-MM-DD)")
    shares_sold: float = Field(default=0.0, ge=0, description="Number of shares sold")
    sale_price: float = Field(default=0.0, ge=0, description="Sale price per share")
    sale_proceeds: float = Field(default=0.0, ge=0, description="Total sale proceeds")

    # Section 83(b) election (for RSA)
    made_83b_election: bool = Field(default=False, description="Made Section 83(b) election within 30 days of grant")
    fmv_at_grant_83b: float = Field(default=0.0, ge=0, description="FMV at grant (for 83(b) election)")

    # ESPP specific fields
    espp_discount_percentage: float = Field(default=0.0, ge=0, le=100, description="ESPP discount percentage")
    espp_purchase_price: float = Field(default=0.0, ge=0, description="ESPP purchase price per share")
    espp_offering_period_start: Optional[str] = Field(None, description="ESPP offering period start date")

    # Withholding
    federal_tax_withheld: float = Field(default=0.0, ge=0, description="Federal income tax withheld")
    state_tax_withheld: float = Field(default=0.0, ge=0, description="State income tax withheld")

    # Form references
    form_3921_received: bool = Field(default=False, description="Received Form 3921 (ISO)")
    form_3922_received: bool = Field(default=False, description="Received Form 3922 (ESPP)")

    def calculate_ordinary_income(self) -> float:
        """
        Calculate ordinary income from the stock compensation event.

        NSO: Spread at exercise = (FMV at exercise - exercise price) × shares
        RSU: FMV at vest × shares vested
        RSA (no 83b): FMV at vest × shares vested
        RSA (83b): FMV at grant × shares granted (recognized at grant)
        ESPP: Discount portion on disqualifying disposition
        ISO: No ordinary income at exercise (but AMT preference)
        """
        if self.compensation_type == StockCompensationType.NSO:
            if self.exercise_date and self.fmv_at_exercise > 0:
                spread = self.fmv_at_exercise - self.grant_price
                return max(0, spread * self.shares_exercised)
        elif self.compensation_type == StockCompensationType.RSU:
            if self.vest_date and self.fmv_at_vest > 0:
                return self.fmv_at_vest * self.shares_vested
        elif self.compensation_type == StockCompensationType.RSA:
            if self.made_83b_election:
                return self.fmv_at_grant_83b * self.shares_granted
            elif self.vest_date and self.fmv_at_vest > 0:
                return self.fmv_at_vest * self.shares_vested
        elif self.compensation_type == StockCompensationType.ESPP:
            # Ordinary income on disqualifying disposition
            if self.sale_date and self.espp_purchase_price > 0:
                discount = self.fmv_at_vest - self.espp_purchase_price
                return max(0, discount * self.shares_sold)
        return 0.0

    def calculate_amt_preference(self) -> float:
        """
        Calculate AMT preference amount (ISO only).

        ISO spread at exercise is an AMT preference item.
        """
        if self.compensation_type == StockCompensationType.ISO:
            if self.exercise_date and self.fmv_at_exercise > 0:
                spread = self.fmv_at_exercise - self.grant_price
                return max(0, spread * self.shares_exercised)
        return 0.0

    def is_qualifying_disposition(self) -> bool:
        """
        Check if this is a qualifying disposition (ISO/ESPP).

        Qualifying disposition requires holding:
        - ISO: >2 years from grant AND >1 year from exercise
        - ESPP: >2 years from offering AND >1 year from purchase
        """
        if not self.sale_date:
            return False
        from datetime import datetime
        sale = datetime.strptime(self.sale_date, "%Y-%m-%d")

        if self.compensation_type == StockCompensationType.ISO:
            if self.grant_date and self.exercise_date:
                grant = datetime.strptime(self.grant_date, "%Y-%m-%d")
                exercise = datetime.strptime(self.exercise_date, "%Y-%m-%d")
                years_from_grant = (sale - grant).days / 365
                years_from_exercise = (sale - exercise).days / 365
                return years_from_grant > 2 and years_from_exercise > 1
        elif self.compensation_type == StockCompensationType.ESPP:
            if self.espp_offering_period_start and self.vest_date:
                offering_start = datetime.strptime(self.espp_offering_period_start, "%Y-%m-%d")
                purchase = datetime.strptime(self.vest_date, "%Y-%m-%d")
                years_from_offering = (sale - offering_start).days / 365
                years_from_purchase = (sale - purchase).days / 365
                return years_from_offering > 2 and years_from_purchase > 1
        return False


class Form1099C(BaseModel):
    """
    Form 1099-C: Cancellation of Debt.

    Reports cancellation of debt of $600 or more. Generally taxable as income
    unless an exclusion applies (bankruptcy, insolvency, qualified farm/business
    real property, qualified principal residence indebtedness, etc.).
    """
    creditor_name: str = Field(description="Name of creditor")
    creditor_tin: Optional[str] = Field(None, description="Creditor's TIN")

    # Box 1: Date of identifiable event
    date_canceled: str = Field(description="Box 1: Date of identifiable event (YYYY-MM-DD)")

    # Box 2: Amount of debt canceled
    amount_canceled: float = Field(ge=0, description="Box 2: Amount of debt discharged/canceled")

    # Box 3: Interest if included in Box 2
    interest_included: float = Field(default=0.0, ge=0, description="Box 3: Interest included in Box 2")

    # Box 4: Debt description
    debt_description: Optional[str] = Field(None, description="Box 4: Description of debt")

    # Box 5: Was borrower personally liable
    personally_liable: bool = Field(default=True, description="Box 5: Borrower was personally liable")

    # Box 6: Identifiable event code
    event_code: DebtCancellationType = Field(default=DebtCancellationType.OTHER, description="Box 6: Identifiable event code")

    # Box 7: Fair market value of property
    fmv_of_property: float = Field(default=0.0, ge=0, description="Box 7: FMV of property (foreclosures)")

    # Form 982 Exclusions (Reduction of Tax Attributes)
    excluded_bankruptcy: float = Field(default=0.0, ge=0, description="Amount excluded due to bankruptcy (Title 11)")
    excluded_insolvency: float = Field(default=0.0, ge=0, description="Amount excluded due to insolvency")
    excluded_farm_debt: float = Field(default=0.0, ge=0, description="Amount excluded as qualified farm debt")
    excluded_real_property: float = Field(default=0.0, ge=0, description="Amount excluded as qualified real property business debt")
    excluded_principal_residence: float = Field(default=0.0, ge=0, description="Amount excluded as qualified principal residence indebtedness")
    excluded_student_loan: float = Field(default=0.0, ge=0, description="Amount excluded as student loan discharge")

    # Insolvency calculation
    total_liabilities_before: float = Field(default=0.0, ge=0, description="Total liabilities immediately before cancellation")
    total_assets_fmv_before: float = Field(default=0.0, ge=0, description="Total FMV of assets immediately before cancellation")

    def get_taxable_amount(self) -> float:
        """Calculate the taxable amount of canceled debt after exclusions."""
        total_excluded = (
            self.excluded_bankruptcy +
            self.excluded_insolvency +
            self.excluded_farm_debt +
            self.excluded_real_property +
            self.excluded_principal_residence +
            self.excluded_student_loan
        )
        return max(0, self.amount_canceled - total_excluded)

    def calculate_insolvency_exclusion(self) -> float:
        """
        Calculate insolvency exclusion amount.

        Exclusion limited to the extent taxpayer was insolvent.
        Insolvency = Liabilities exceed FMV of assets.
        """
        if self.total_liabilities_before > self.total_assets_fmv_before:
            insolvency_amount = self.total_liabilities_before - self.total_assets_fmv_before
            return min(insolvency_amount, self.amount_canceled)
        return 0.0


class AlimonyInfo(BaseModel):
    """
    Alimony income/expense tracking.

    IMPORTANT: Tax treatment depends on divorce/separation date:
    - Pre-2019 agreements: Deductible by payor, taxable to recipient
    - 2019+ agreements: NOT deductible by payor, NOT taxable to recipient

    For modifications: Original agreement date controls unless modified
    agreement specifically adopts new rules.
    """
    recipient_name: Optional[str] = Field(None, description="Name of alimony recipient")
    recipient_ssn: Optional[str] = Field(None, description="SSN of recipient (required for deduction)")
    payor_name: Optional[str] = Field(None, description="Name of alimony payor")
    payor_ssn: Optional[str] = Field(None, description="SSN of payor")

    # Agreement information
    agreement_date: str = Field(description="Date of divorce/separation agreement (YYYY-MM-DD)")
    is_pre_2019_agreement: bool = Field(default=False, description="Agreement executed before 2019")
    was_modified_post_2018: bool = Field(default=False, description="Agreement modified after 2018")
    modification_adopts_new_rules: bool = Field(default=False, description="Modification specifically adopts post-2018 rules")

    # Amounts
    alimony_received: float = Field(default=0.0, ge=0, description="Total alimony received during year")
    alimony_paid: float = Field(default=0.0, ge=0, description="Total alimony paid during year")

    # Recapture rules (IRC Section 71(f)) - applies to first 3 years
    year_1_payments: float = Field(default=0.0, ge=0, description="First year alimony payments")
    year_2_payments: float = Field(default=0.0, ge=0, description="Second year alimony payments")
    year_3_payments: float = Field(default=0.0, ge=0, description="Third year alimony payments")

    def is_taxable_to_recipient(self) -> bool:
        """Determine if alimony is taxable to recipient."""
        if not self.is_pre_2019_agreement:
            return False
        if self.was_modified_post_2018 and self.modification_adopts_new_rules:
            return False
        return True

    def is_deductible_by_payor(self) -> bool:
        """Determine if alimony is deductible by payor."""
        return self.is_taxable_to_recipient()  # Same rules apply

    def calculate_recapture(self) -> float:
        """
        Calculate alimony recapture amount (IRC Section 71(f)).

        Applies if payments decrease significantly in years 1-3.
        Recapture = excess front-loading that must be added back to income.
        """
        if not self.is_pre_2019_agreement:
            return 0.0

        # Year 3 recapture
        year_3_recapture = max(0, self.year_2_payments - self.year_3_payments - 15000)

        # Year 2 recapture
        adjusted_year_2 = self.year_2_payments - year_3_recapture
        avg_year_2_3 = (adjusted_year_2 + self.year_3_payments) / 2
        year_2_recapture = max(0, self.year_1_payments - avg_year_2_3 - 15000)

        return year_2_recapture + year_3_recapture


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


class Form1099QAccountType(str, Enum):
    """Type of qualified education program for Form 1099-Q."""
    QTP_529 = "529"  # Qualified Tuition Program (529 Plan)
    COVERDELL_ESA = "coverdell"  # Coverdell Education Savings Account


class Form1099Q(BaseModel):
    """
    Form 1099-Q: Payments from Qualified Education Programs.

    Reports distributions from:
    - 529 Qualified Tuition Programs (QTP)
    - Coverdell Education Savings Accounts (ESA)

    Tax Treatment:
    - Distributions used for qualified education expenses: NOT taxable
    - Distributions NOT used for qualified expenses: Earnings taxable + 10% penalty
    - Basis (contributions) is NEVER taxable
    - Coordinated with AOTC/LLC education credits (can't double-dip)
    """
    payer_name: str = Field(description="Name of plan/program")
    payer_tin: Optional[str] = Field(None, description="Payer's TIN")
    account_type: Form1099QAccountType = Field(
        default=Form1099QAccountType.QTP_529,
        description="Type of qualified education program"
    )

    # Box 1: Gross Distribution
    gross_distribution: float = Field(default=0.0, ge=0, description="Box 1: Gross distribution")

    # Box 2: Earnings
    earnings: float = Field(default=0.0, ge=0, description="Box 2: Earnings (taxable portion if not used for education)")

    # Box 3: Basis
    basis: float = Field(default=0.0, ge=0, description="Box 3: Basis (contributions, never taxable)")

    # Box 4: Trustee-to-trustee transfer
    is_trustee_to_trustee: bool = Field(default=False, description="Box 4: Trustee-to-trustee transfer")

    # Box 5: Check if recipient is not designated beneficiary
    recipient_not_designated_beneficiary: bool = Field(
        default=False,
        description="Box 5: Recipient is NOT the designated beneficiary"
    )

    # Box 6: Check if distribution is from a Coverdell ESA
    is_coverdell: bool = Field(default=False, description="Box 6: Coverdell ESA distribution")

    # Qualified education expenses tracking
    qualified_education_expenses: float = Field(
        default=0.0, ge=0,
        description="Qualified education expenses paid (tuition, fees, books, supplies, equipment)"
    )
    room_and_board: float = Field(
        default=0.0, ge=0,
        description="Room and board expenses (only for students enrolled at least half-time)"
    )

    # Coordination with other education benefits
    # Must reduce QEE by tax-free scholarships, AOTC/LLC expenses, etc.
    tax_free_scholarships: float = Field(
        default=0.0, ge=0,
        description="Tax-free scholarships and grants received"
    )
    expenses_used_for_aotc_llc: float = Field(
        default=0.0, ge=0,
        description="Expenses used for AOTC or LLC credit (can't double-dip)"
    )

    # Student information
    beneficiary_name: Optional[str] = Field(None, description="Name of beneficiary/student")
    beneficiary_ssn: Optional[str] = Field(None, description="SSN of beneficiary")

    def get_adjusted_qualified_expenses(self) -> float:
        """
        Calculate adjusted qualified education expenses.

        Must reduce QEE by:
        - Tax-free scholarships and grants
        - Expenses used for AOTC/LLC
        """
        total_qee = self.qualified_education_expenses + self.room_and_board
        adjustments = self.tax_free_scholarships + self.expenses_used_for_aotc_llc
        return max(0, total_qee - adjustments)

    def get_taxable_amount(self) -> float:
        """
        Calculate taxable portion of distribution.

        Only the earnings portion is taxable, and only if the distribution
        exceeds adjusted qualified education expenses.

        Formula:
        - If distribution <= adjusted QEE: $0 taxable
        - If distribution > adjusted QEE: (excess / gross) * earnings = taxable
        """
        if self.is_trustee_to_trustee:
            return 0.0  # Trustee-to-trustee transfers are not taxable

        adjusted_qee = self.get_adjusted_qualified_expenses()

        if self.gross_distribution <= adjusted_qee:
            return 0.0  # Fully used for qualified expenses

        # Calculate taxable portion of earnings
        excess_distribution = self.gross_distribution - adjusted_qee
        if self.gross_distribution > 0:
            taxable_ratio = excess_distribution / self.gross_distribution
            return float(money(self.earnings * taxable_ratio))
        return 0.0

    def get_penalty_amount(self, penalty_rate: float = 0.10) -> float:
        """
        Calculate 10% additional tax (penalty) on taxable earnings.

        The 10% penalty applies to the taxable earnings portion of
        distributions not used for qualified education expenses.

        Exceptions to penalty (not implemented here):
        - Death of beneficiary
        - Disability of beneficiary
        - Scholarship (reduces QEE but no penalty on that portion)
        - Attendance at US military academy
        """
        taxable = self.get_taxable_amount()
        return float(money(taxable * penalty_rate))


class StateTaxRefund(BaseModel):
    """
    State/Local Tax Refund Recovery (Form 1099-G Box 2).

    Per the Tax Benefit Rule (IRC Section 111):
    - State tax refunds are taxable ONLY if the taxpayer:
      1. Itemized deductions in the prior year, AND
      2. Deducted state/local taxes (SALT), AND
      3. Received a tax benefit from that deduction

    If the taxpayer took the standard deduction in the prior year,
    the state refund is NOT taxable.
    """
    # State information
    state_code: str = Field(description="Two-letter state code (e.g., CA, NY)")
    tax_year_of_refund: int = Field(description="Tax year the refund relates to (prior year)")

    # Box 2: State or Local Income Tax Refunds, Credits, or Offsets
    refund_amount: float = Field(default=0.0, ge=0, description="Box 2: State/local refund amount")

    # Prior year information needed to determine taxability
    prior_year_itemized: bool = Field(
        default=False,
        description="Did taxpayer itemize deductions in the prior year?"
    )
    prior_year_salt_deducted: float = Field(
        default=0.0, ge=0,
        description="State/local taxes deducted in prior year (Schedule A Line 5d)"
    )
    prior_year_standard_deduction: float = Field(
        default=0.0, ge=0,
        description="Standard deduction that WOULD have applied in prior year"
    )
    prior_year_itemized_total: float = Field(
        default=0.0, ge=0,
        description="Total itemized deductions claimed in prior year"
    )

    # SALT cap consideration (post-TCJA: $10,000 limit)
    salt_cap_applied: bool = Field(
        default=True,
        description="Was the $10,000 SALT cap in effect? (True for 2018+)"
    )

    def get_taxable_amount(self) -> float:
        """
        Calculate taxable portion of state refund per Tax Benefit Rule.

        The refund is taxable only to the extent the SALT deduction
        provided a tax benefit in the prior year.

        Scenarios:
        1. Took standard deduction: $0 taxable
        2. Itemized but itemized < standard: Taxable = itemized - standard (if positive)
        3. Itemized and itemized > standard: Fully taxable (up to refund amount)
        """
        # If didn't itemize, refund is not taxable
        if not self.prior_year_itemized:
            return 0.0

        # If itemized total was less than or equal to standard deduction,
        # the SALT deduction provided no benefit
        if self.prior_year_itemized_total <= self.prior_year_standard_deduction:
            return 0.0

        # Calculate tax benefit received from SALT deduction
        # Tax benefit = amount by which itemized exceeded standard
        excess_over_standard = self.prior_year_itemized_total - self.prior_year_standard_deduction

        # Taxable refund is limited to:
        # 1. The actual refund amount
        # 2. The SALT amount deducted
        # 3. The tax benefit (excess over standard)
        taxable = min(
            self.refund_amount,
            self.prior_year_salt_deducted,
            excess_over_standard
        )

        return max(0, taxable)

    def is_taxable(self) -> bool:
        """Check if any portion of the refund is taxable."""
        return self.get_taxable_amount() > 0


class Form1099OID(BaseModel):
    """
    Form 1099-OID: Original Issue Discount.

    Reports OID on bonds, CDs, and other debt instruments issued at a discount.
    OID is the difference between the stated redemption price at maturity
    and the issue price. This discount is treated as interest income and
    must be reported annually even if not received.

    Reference: IRS Publication 550, IRC Section 1272
    """
    payer_name: str = Field(description="Name of issuer/payer")
    payer_tin: Optional[str] = Field(None, description="Payer's TIN")

    # Box 1: Original Issue Discount
    original_issue_discount: float = Field(
        default=0.0, ge=0,
        description="Box 1: OID for the year (taxable as interest)"
    )

    # Box 2: Other periodic interest
    other_periodic_interest: float = Field(
        default=0.0, ge=0,
        description="Box 2: Stated interest paid (in addition to OID)"
    )

    # Box 3: Early withdrawal penalty
    early_withdrawal_penalty: float = Field(
        default=0.0, ge=0,
        description="Box 3: Penalty for early withdrawal (deductible)"
    )

    # Box 4: Federal income tax withheld
    federal_tax_withheld: float = Field(
        default=0.0, ge=0,
        description="Box 4: Federal income tax withheld"
    )

    # Box 5: Market discount
    market_discount: float = Field(
        default=0.0, ge=0,
        description="Box 5: Market discount (may be ordinary income on sale)"
    )

    # Box 6: Acquisition premium
    acquisition_premium: float = Field(
        default=0.0, ge=0,
        description="Box 6: Acquisition premium (reduces OID)"
    )

    # Box 8: OID on U.S. Treasury obligations
    treasury_oid: float = Field(
        default=0.0, ge=0,
        description="Box 8: OID on U.S. Treasury obligations"
    )

    # Box 11: Tax-exempt OID
    tax_exempt_oid: float = Field(
        default=0.0, ge=0,
        description="Box 11: Tax-exempt OID (municipal bonds)"
    )

    # CUSIP number for identification
    cusip_number: Optional[str] = Field(None, description="CUSIP number of instrument")
    description: Optional[str] = Field(None, description="Description of debt instrument")

    def get_taxable_oid(self) -> float:
        """
        Calculate taxable OID after adjustments.

        Taxable OID = Box 1 - Box 6 (acquisition premium reduces OID)
        Treasury OID is included in total but may have state exemption.
        """
        adjusted_oid = self.original_issue_discount - self.acquisition_premium
        return max(0, adjusted_oid)

    def get_total_taxable_interest(self) -> float:
        """Get total taxable interest (OID + other periodic interest)."""
        return self.get_taxable_oid() + self.other_periodic_interest


class Form1099PATR(BaseModel):
    """
    Form 1099-PATR: Taxable Distributions Received From Cooperatives.

    Reports patronage dividends and other distributions from cooperatives
    such as agricultural co-ops, rural electric co-ops, credit unions, etc.

    Reference: IRS Publication 225, IRC Section 1385
    """
    payer_name: str = Field(description="Name of cooperative")
    payer_tin: Optional[str] = Field(None, description="Cooperative's TIN")

    # Box 1: Patronage dividends
    patronage_dividends: float = Field(
        default=0.0, ge=0,
        description="Box 1: Patronage dividends (taxable)"
    )

    # Box 2: Nonpatronage distributions
    nonpatronage_distributions: float = Field(
        default=0.0, ge=0,
        description="Box 2: Nonpatronage distributions"
    )

    # Box 3: Per-unit retain allocations
    per_unit_retain_allocations: float = Field(
        default=0.0, ge=0,
        description="Box 3: Per-unit retain allocations"
    )

    # Box 4: Federal income tax withheld
    federal_tax_withheld: float = Field(
        default=0.0, ge=0,
        description="Box 4: Federal income tax withheld"
    )

    # Box 5: Redemption of nonqualified notices
    redemption_nonqualified: float = Field(
        default=0.0, ge=0,
        description="Box 5: Redemption of nonqualified notices"
    )

    # Box 6: Section 199A(g) deduction
    section_199a_deduction: float = Field(
        default=0.0, ge=0,
        description="Box 6: Section 199A(g) qualified payments deduction"
    )

    # Box 7: Qualified payments (Section 199A(a))
    qualified_payments: float = Field(
        default=0.0, ge=0,
        description="Box 7: Qualified payments for Section 199A(a) deduction"
    )

    def get_total_taxable(self) -> float:
        """Get total taxable distributions from cooperative."""
        return (
            self.patronage_dividends +
            self.nonpatronage_distributions +
            self.per_unit_retain_allocations +
            self.redemption_nonqualified
        )


class Form1099LTC(BaseModel):
    """
    Form 1099-LTC: Long-Term Care and Accelerated Death Benefits.

    Reports payments from long-term care insurance contracts and
    accelerated death benefits from life insurance policies.

    Per-diem payments: Taxable only if exceeds $420/day (2025) or actual costs
    Reimbursement payments: Generally not taxable if for qualified expenses

    Reference: IRS Publication 525, IRC Section 7702B
    """
    payer_name: str = Field(description="Name of insurance company")
    payer_tin: Optional[str] = Field(None, description="Payer's TIN")
    policyholder_name: Optional[str] = Field(None, description="Policyholder name")
    insured_name: Optional[str] = Field(None, description="Name of insured person")

    # Box 1: Gross long-term care benefits paid
    gross_ltc_benefits: float = Field(
        default=0.0, ge=0,
        description="Box 1: Gross long-term care benefits paid"
    )

    # Box 2: Accelerated death benefits paid
    accelerated_death_benefits: float = Field(
        default=0.0, ge=0,
        description="Box 2: Accelerated death benefits paid"
    )

    # Box 3: Per diem or reimbursement
    is_per_diem: bool = Field(
        default=False,
        description="Box 3: Check if per diem (vs reimbursement)"
    )

    # Tracking for taxability calculation
    qualified_ltc_expenses: float = Field(
        default=0.0, ge=0,
        description="Qualified long-term care expenses incurred"
    )
    days_of_care: int = Field(
        default=0, ge=0,
        description="Number of days of qualified long-term care"
    )

    # 2025 per-diem limit (indexed annually)
    per_diem_limit: float = Field(
        default=420.0,
        description="Daily per-diem exclusion limit (2025: $420)"
    )

    def get_taxable_amount(self) -> float:
        """
        Calculate taxable portion of LTC benefits.

        Per-diem: Taxable = Benefits - max(per_diem_limit * days, actual_expenses)
        Reimbursement: Generally $0 if for qualified expenses
        Accelerated death benefits: Generally excluded if terminally ill
        """
        if not self.is_per_diem:
            # Reimbursement - not taxable if for qualified expenses
            excess = self.gross_ltc_benefits - self.qualified_ltc_expenses
            return max(0, excess)

        # Per-diem calculation
        per_diem_exclusion = self.per_diem_limit * self.days_of_care
        max_exclusion = max(per_diem_exclusion, self.qualified_ltc_expenses)
        taxable = self.gross_ltc_benefits - max_exclusion
        return max(0, taxable)


class FormRRB1099(BaseModel):
    """
    Form RRB-1099: Payments by the Railroad Retirement Board.

    Reports Social Security equivalent benefits (SSEB) paid to railroad
    employees, similar to Social Security but administered separately.

    Taxability follows Social Security rules:
    - Up to 50% taxable if income between base amounts
    - Up to 85% taxable if income exceeds upper thresholds

    Reference: IRS Publication 915, Railroad Retirement Act
    """
    # Box 3: Employee contributions (nontaxable)
    employee_contributions: float = Field(
        default=0.0, ge=0,
        description="Box 3: Employee contributions (not taxable)"
    )

    # Box 4: Contributory amount paid
    contributory_amount: float = Field(
        default=0.0, ge=0,
        description="Box 4: Contributory amount paid"
    )

    # Box 5: Social Security Equivalent Benefit (SSEB)
    sseb_gross: float = Field(
        default=0.0, ge=0,
        description="Box 5: Gross SSEB portion"
    )

    # Box 7: Federal income tax withheld
    federal_tax_withheld: float = Field(
        default=0.0, ge=0,
        description="Box 7: Federal income tax withheld"
    )

    # Box 9: Medicare premium deducted
    medicare_premium: float = Field(
        default=0.0, ge=0,
        description="Box 9: Medicare premium deducted"
    )

    # For taxability calculation
    vested_dual_benefit: float = Field(
        default=0.0, ge=0,
        description="Vested dual benefit (from Form RRB-1099-R)"
    )

    def get_net_sseb(self) -> float:
        """Get net SSEB (gross minus employee contributions)."""
        return max(0, self.sseb_gross - self.employee_contributions)

    def calculate_taxable_sseb(
        self,
        modified_agi: float,
        filing_status: str = "single"
    ) -> float:
        """
        Calculate taxable SSEB using Social Security taxation rules.

        Same thresholds as Social Security:
        Single: $25,000 base, $34,000 upper
        MFJ: $32,000 base, $44,000 upper
        """
        net_sseb = self.get_net_sseb()
        if net_sseb <= 0:
            return 0.0

        # Base and upper thresholds by filing status
        if filing_status in ["married_filing_jointly", "qualifying_widow"]:
            base_amount = 32000
            upper_amount = 44000
        elif filing_status == "married_filing_separately":
            # MFS living with spouse: 85% always taxable
            return net_sseb * 0.85
        else:  # single, head_of_household
            base_amount = 25000
            upper_amount = 34000

        # Provisional income = MAGI + 50% of SSEB
        provisional_income = modified_agi + (net_sseb * 0.5)

        if provisional_income <= base_amount:
            return 0.0
        elif provisional_income <= upper_amount:
            # Up to 50% taxable
            taxable = min(
                (provisional_income - base_amount) * 0.5,
                net_sseb * 0.5
            )
            return taxable
        else:
            # Up to 85% taxable
            base_taxable = min((upper_amount - base_amount) * 0.5, net_sseb * 0.5)
            additional = (provisional_income - upper_amount) * 0.85
            taxable = min(base_taxable + additional, net_sseb * 0.85)
            return taxable


class Form4137(BaseModel):
    """
    Form 4137: Social Security and Medicare Tax on Unreported Tip Income.

    Reports cash tips not reported to employer and calculates
    the employee's share of Social Security and Medicare taxes.

    Tips must be reported if $20+ in a month from a single employer.
    Employee owes both income tax AND Social Security/Medicare tax on tips.

    Reference: IRS Publication 531
    """
    employer_name: str = Field(description="Name of employer")
    employer_ein: Optional[str] = Field(None, description="Employer's EIN")

    # Unreported tip income
    total_cash_tips: float = Field(
        default=0.0, ge=0,
        description="Total cash tips received"
    )
    tips_reported_to_employer: float = Field(
        default=0.0, ge=0,
        description="Tips already reported to employer (on W-2)"
    )

    # For Social Security tax calculation
    wages_subject_to_ss: float = Field(
        default=0.0, ge=0,
        description="W-2 wages already subject to Social Security tax"
    )

    # Tax rates (2025)
    ss_tax_rate: float = Field(default=0.062, description="Social Security tax rate")
    medicare_tax_rate: float = Field(default=0.0145, description="Medicare tax rate")
    ss_wage_base: float = Field(default=176100.0, description="2025 SS wage base")

    def get_unreported_tips(self) -> float:
        """Calculate unreported tip income."""
        return max(0, self.total_cash_tips - self.tips_reported_to_employer)

    def calculate_ss_tax(self) -> float:
        """Calculate Social Security tax on unreported tips."""
        unreported = self.get_unreported_tips()
        if unreported <= 0:
            return 0.0

        # SS tax only applies up to wage base
        ss_room = max(0, self.ss_wage_base - self.wages_subject_to_ss)
        taxable_for_ss = min(unreported, ss_room)
        return float(money(taxable_for_ss * self.ss_tax_rate))

    def calculate_medicare_tax(self) -> float:
        """Calculate Medicare tax on unreported tips (no wage cap)."""
        unreported = self.get_unreported_tips()
        return float(money(unreported * self.medicare_tax_rate))

    def get_total_tax(self) -> float:
        """Get total Social Security + Medicare tax on unreported tips."""
        return self.calculate_ss_tax() + self.calculate_medicare_tax()


class ClergyHousingAllowance(BaseModel):
    """
    Clergy Housing Allowance (Parsonage Allowance) - IRC Section 107.

    Ministers can exclude from gross income:
    1. The fair rental value of a home provided by the church, OR
    2. A housing allowance designated by the church

    The exclusion is limited to the LOWEST of:
    - Amount designated by the church
    - Actual housing expenses
    - Fair rental value of the home (furnished, including utilities)

    Note: Still subject to self-employment tax even if excluded from income tax.

    Reference: IRS Publication 517
    """
    minister_name: Optional[str] = Field(None, description="Name of minister")

    # Designation by church
    designated_allowance: float = Field(
        default=0.0, ge=0,
        description="Housing allowance designated by church"
    )

    # Actual expenses
    actual_housing_expenses: float = Field(
        default=0.0, ge=0,
        description="Actual housing expenses (rent/mortgage, utilities, insurance, etc.)"
    )

    # Fair rental value
    fair_rental_value: float = Field(
        default=0.0, ge=0,
        description="Fair rental value of home (furnished, with utilities)"
    )

    # Provided parsonage (alternative to allowance)
    parsonage_provided: bool = Field(
        default=False,
        description="Church provides a parsonage (home)"
    )
    parsonage_fair_rental_value: float = Field(
        default=0.0, ge=0,
        description="Fair rental value of parsonage if provided"
    )

    # For SE tax calculation
    is_ordained_minister: bool = Field(
        default=True,
        description="Is an ordained, licensed, or commissioned minister"
    )
    opted_out_of_se_tax: bool = Field(
        default=False,
        description="Filed Form 4361 to opt out of SE tax (rare)"
    )

    def get_excludable_amount(self) -> float:
        """
        Calculate excludable housing allowance.

        Exclusion = LOWEST of:
        1. Designated amount
        2. Actual expenses
        3. Fair rental value
        """
        if self.parsonage_provided:
            # Parsonage FRV is fully excludable
            return self.parsonage_fair_rental_value

        # Cash allowance - limited to lowest of three
        return min(
            self.designated_allowance,
            self.actual_housing_expenses,
            self.fair_rental_value
        )

    def get_taxable_excess(self) -> float:
        """Get amount of allowance that exceeds exclusion (taxable)."""
        if self.parsonage_provided:
            return 0.0
        excludable = self.get_excludable_amount()
        return max(0, self.designated_allowance - excludable)

    def get_se_tax_amount(self) -> float:
        """
        Get amount subject to self-employment tax.

        Housing allowance is STILL subject to SE tax even if
        excluded from income tax (unless Form 4361 filed).
        """
        if self.opted_out_of_se_tax:
            return 0.0
        return self.get_excludable_amount()


class MilitaryCombatPay(BaseModel):
    """
    Military Combat Zone Pay Exclusion - IRC Section 112.

    Military personnel serving in designated combat zones can exclude
    combat pay from gross income. Exclusion limits vary by rank.

    Enlisted: All combat pay excluded
    Officers: Excluded up to highest enlisted pay + imminent danger pay

    Can also elect to include combat pay in earned income for EITC purposes.

    Reference: IRS Publication 3
    """
    service_member_name: Optional[str] = Field(None, description="Service member name")
    military_branch: Optional[str] = Field(None, description="Branch of service")

    # Combat zone information
    combat_zone: Optional[str] = Field(None, description="Designated combat zone")
    months_in_combat_zone: int = Field(
        default=0, ge=0, le=12,
        description="Months served in combat zone during tax year"
    )

    # Pay amounts
    total_military_pay: float = Field(
        default=0.0, ge=0,
        description="Total military pay for the year"
    )
    combat_zone_pay: float = Field(
        default=0.0, ge=0,
        description="Pay attributable to combat zone service"
    )

    # Rank for exclusion limit
    is_enlisted: bool = Field(
        default=True,
        description="True if enlisted, False if commissioned officer"
    )
    officer_exclusion_limit: float = Field(
        default=11980.80,  # 2025 estimate: highest enlisted pay + imminent danger
        description="Monthly exclusion limit for officers"
    )

    # EITC election
    elect_combat_pay_for_eitc: bool = Field(
        default=False,
        description="Elect to include combat pay in earned income for EITC"
    )

    # Hospitalization extension
    hospitalization_months: int = Field(
        default=0, ge=0,
        description="Months hospitalized from combat zone wounds"
    )

    def get_excludable_combat_pay(self) -> float:
        """
        Calculate excludable combat zone pay.

        Enlisted: All combat pay excluded
        Officers: Limited to monthly cap × months
        """
        if self.is_enlisted:
            return self.combat_zone_pay

        # Officer exclusion capped
        total_months = self.months_in_combat_zone + self.hospitalization_months
        max_exclusion = self.officer_exclusion_limit * total_months
        return min(self.combat_zone_pay, max_exclusion)

    def get_taxable_military_pay(self) -> float:
        """Get taxable portion of military pay after combat exclusion."""
        exclusion = self.get_excludable_combat_pay()
        return max(0, self.total_military_pay - exclusion)

    def get_eitc_earned_income(self) -> float:
        """
        Get earned income for EITC purposes.

        If elected, combat pay is included in earned income for EITC
        even though excluded from gross income.
        """
        taxable = self.get_taxable_military_pay()
        if self.elect_combat_pay_for_eitc:
            return taxable + self.get_excludable_combat_pay()
        return taxable


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

    # ==========================================================================
    # NEW INCOME TYPES - Comprehensive Coverage
    # ==========================================================================

    # Alimony Income (Pre-2019 agreements only - taxable to recipient)
    alimony_info: Optional[AlimonyInfo] = Field(
        default=None,
        description="Alimony income/expense tracking with agreement date rules"
    )
    alimony_received: float = Field(
        default=0.0, ge=0,
        description="Simple alimony received field (pre-2019 agreements only)"
    )

    # Form 1099-R Distributions (Pensions, Annuities, IRAs, 401k)
    form_1099r_distributions: List[Form1099R] = Field(
        default_factory=list,
        description="Form 1099-R distributions from retirement plans and annuities"
    )

    # Stock Compensation (ISO, NSO, RSA, RSU, ESPP)
    stock_compensation_events: List[StockCompensationEvent] = Field(
        default_factory=list,
        description="Equity compensation events (options, restricted stock, ESPP)"
    )

    # Discharge of Debt (Form 1099-C)
    form_1099c_debt_cancellation: List[Form1099C] = Field(
        default_factory=list,
        description="Form 1099-C canceled debt income"
    )

    # Prizes and Awards (non-gambling)
    prizes_and_awards: float = Field(
        default=0.0, ge=0,
        description="Prizes, awards, and contest winnings (non-gambling)"
    )

    # Scholarship/Fellowship Income (taxable portion)
    taxable_scholarship: float = Field(
        default=0.0, ge=0,
        description="Taxable scholarship/fellowship (amounts exceeding qualified education expenses)"
    )

    # Jury Duty Pay
    jury_duty_pay: float = Field(
        default=0.0, ge=0,
        description="Jury duty compensation received"
    )
    jury_duty_remitted_to_employer: float = Field(
        default=0.0, ge=0,
        description="Jury duty pay remitted to employer (deductible)"
    )

    # Form 1099-Q (529 Plans and Coverdell ESA distributions)
    form_1099q_distributions: List[Form1099Q] = Field(
        default_factory=list,
        description="Form 1099-Q distributions from 529 plans and Coverdell ESAs"
    )

    # State Tax Refund Recovery (Form 1099-G Box 2)
    state_tax_refunds: List[StateTaxRefund] = Field(
        default_factory=list,
        description="State/local tax refunds that may be taxable (Form 1099-G)"
    )

    # Form 1099-OID (Original Issue Discount)
    form_1099oid: List[Form1099OID] = Field(
        default_factory=list,
        description="Form 1099-OID original issue discount on bonds/CDs"
    )

    # Form 1099-PATR (Patronage Dividends from Cooperatives)
    form_1099patr: List[Form1099PATR] = Field(
        default_factory=list,
        description="Form 1099-PATR patronage dividends from cooperatives"
    )

    # Form 1099-LTC (Long-Term Care Benefits)
    form_1099ltc: List[Form1099LTC] = Field(
        default_factory=list,
        description="Form 1099-LTC long-term care and accelerated death benefits"
    )

    # Form RRB-1099 (Railroad Retirement Benefits)
    form_rrb1099: List[FormRRB1099] = Field(
        default_factory=list,
        description="Form RRB-1099 railroad retirement benefits"
    )

    # Form 4137 (Unreported Tip Income)
    form_4137_tips: List[Form4137] = Field(
        default_factory=list,
        description="Form 4137 unreported tip income"
    )

    # Clergy Housing Allowance (Section 107)
    clergy_housing: Optional[ClergyHousingAllowance] = Field(
        default=None,
        description="Clergy housing/parsonage allowance (IRC Section 107)"
    )

    # Military Combat Pay Exclusion
    military_combat_pay: Optional[MilitaryCombatPay] = Field(
        default=None,
        description="Military combat zone pay exclusion (IRC Section 112)"
    )

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
        """
        Calculate total federal tax withheld from all sources.

        Includes:
        - W-2 wages
        - Gambling winnings (W-2G)
        - Form 1099-R distributions (pensions, IRAs, annuities)
        - Stock compensation events (RSU, NSO vesting/exercise)
        - Form 1099-OID (Original Issue Discount)
        - Form 1099-PATR (Patronage Dividends)
        - Form RRB-1099 (Railroad Retirement)
        """
        w2_withholding = sum(w2.federal_tax_withheld for w2 in self.w2_forms)
        gambling_withholding = sum(g.federal_tax_withheld for g in self.gambling_winnings)
        form_1099r_withholding = sum(dist.federal_tax_withheld for dist in self.form_1099r_distributions)
        stock_comp_withholding = sum(event.federal_tax_withheld for event in self.stock_compensation_events)
        form_1099oid_withholding = self.get_total_1099oid_withholding()
        form_1099patr_withholding = self.get_total_1099patr_withholding()
        form_rrb1099_withholding = self.get_total_rrb1099_withholding()
        return (
            w2_withholding + gambling_withholding + form_1099r_withholding +
            stock_comp_withholding + form_1099oid_withholding +
            form_1099patr_withholding + form_rrb1099_withholding
        )

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
        Check if taxpayer has any income from a Specified Service Trade or Business (SSTB).

        Checks both:
        1. Schedule C sole proprietorship businesses
        2. Schedule K-1 partnership/S-corp income

        SSTBs include businesses in health, law, accounting, actuarial science,
        performing arts, consulting, athletics, financial services, brokerage,
        or any trade where the principal asset is the reputation/skill of employees.

        SSTB income is subject to additional QBI deduction phase-out above the threshold
        per IRC §199A(d)(2).

        Returns:
            True if any business activity is classified as SSTB, False otherwise
        """
        # Check Schedule C businesses
        if self.schedule_c_businesses:
            if any(biz.get_sstb_classification() for biz in self.schedule_c_businesses):
                return True

        # Check K-1 forms from partnerships/S-corps
        if any(k1.is_sstb for k1 in self.schedule_k1_forms):
            return True

        return False

    def get_k1_foreign_tax_paid(self) -> float:
        """Get foreign taxes paid from K-1 forms."""
        return sum(k1.foreign_tax_paid for k1 in self.schedule_k1_forms)

    def get_total_income(self) -> float:
        """
        Calculate total income from all sources.

        Includes:
        - W-2 wages
        - 1099 income (MISC, NEC, etc.)
        - Self-employment (Schedule C)
        - Interest and dividends
        - Capital gains/losses
        - Rental income (Schedule E Part I)
        - Retirement income (pensions, IRAs)
        - Unemployment compensation
        - Social Security (taxable portion)
        - Gambling winnings
        - Virtual currency income
        - K-1 pass-through income
        - Form 1099-R distributions (pensions, annuities)
        - Stock compensation (NSO, RSU, RSA, ESPP)
        - Alimony received (pre-2019 agreements)
        - Debt cancellation (Form 1099-C)
        - Prizes/awards, scholarships, jury duty
        """
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

        # =====================================================================
        # New Income Types (comprehensive coverage)
        # =====================================================================

        # Form 1099-R distributions (pensions, annuities, IRAs, 401k)
        # Note: retirement_income field may overlap; 1099-R is more detailed
        total += self.get_total_1099r_taxable()

        # Stock compensation ordinary income (NSO, RSU, RSA, ESPP)
        # Note: Often included in W-2 Box 1, but track separately for analysis
        total += self.get_total_stock_compensation_income()

        # Alimony received (taxable only for pre-2019 agreements)
        total += self.get_taxable_alimony_received()

        # Debt cancellation income (Form 1099-C, net of exclusions)
        total += self.get_total_debt_cancellation_income()

        # Other miscellaneous income
        total += self.prizes_and_awards
        total += self.taxable_scholarship
        total += self.get_net_jury_duty_pay()

        # Form 1099-Q (529/Coverdell) - taxable non-qualified distributions
        total += self.get_total_1099q_taxable()

        # State tax refund recovery (taxable if itemized prior year)
        total += self.get_total_taxable_state_refunds()

        # Form 1099-OID (Original Issue Discount) - taxed as interest
        total += self.get_total_1099oid_taxable()

        # Form 1099-PATR (Patronage Dividends from Cooperatives)
        total += self.get_total_1099patr_taxable()

        # Form 1099-LTC (Long-Term Care Benefits) - taxable portion only
        total += self.get_total_1099ltc_taxable()

        # Form 4137 (Unreported Tips) - added to income
        total += self.get_total_unreported_tips()

        # Clergy housing allowance - only taxable excess (excludable portion excluded)
        total += self.get_clergy_housing_taxable()

        # Military combat pay - only taxable portion (combat exclusion applied)
        total += self.get_military_taxable_pay()

        # Note: RRB-1099 taxable amount requires MAGI calculation, so it's
        # handled in the calculator engine similar to Social Security benefits.
        # The gross amount is NOT added here; taxable portion calculated later.

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

    def detect_wash_sales(self) -> List[WashSaleInfo]:
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

    # =========================================================================
    # New Income Types Helper Methods
    # =========================================================================

    def get_total_1099r_taxable(self) -> float:
        """
        Get total taxable amount from all Form 1099-R distributions.

        Includes pensions, annuities, IRAs, 401(k), etc.
        Excludes rollovers (codes G, H) as they are not taxable.
        """
        total = 0.0
        for dist in self.form_1099r_distributions:
            # Skip rollovers - not taxable
            if dist.is_rollover():
                continue
            total += dist.taxable_amount
        return total

    def get_total_1099r_withholding(self) -> float:
        """Get total federal tax withheld from all Form 1099-R distributions."""
        return sum(dist.federal_tax_withheld for dist in self.form_1099r_distributions)

    def get_total_1099r_state_withholding(self) -> float:
        """Get total state tax withheld from all Form 1099-R distributions."""
        return sum(dist.state_tax_withheld for dist in self.form_1099r_distributions)

    def get_1099r_early_distribution_penalty(self, penalty_rate: float = 0.10) -> float:
        """
        Calculate 10% early distribution penalty on Form 1099-R distributions.

        Only applies to early distributions (code 1, J, S) without exception.
        """
        total_penalty = 0.0
        for dist in self.form_1099r_distributions:
            if dist.is_early_distribution():
                total_penalty += dist.taxable_amount * penalty_rate
        return total_penalty

    def get_total_stock_compensation_income(self) -> float:
        """
        Get total ordinary income from all stock compensation events.

        Includes:
        - NSO: Spread at exercise
        - RSU: FMV at vest
        - RSA: FMV at vest (or grant if 83(b) election)
        - ESPP: Discount on disqualifying disposition
        """
        return sum(event.calculate_ordinary_income() for event in self.stock_compensation_events)

    def get_total_stock_compensation_withholding(self) -> float:
        """Get total federal tax withheld from stock compensation events."""
        return sum(event.federal_tax_withheld for event in self.stock_compensation_events)

    def get_total_stock_compensation_state_withholding(self) -> float:
        """Get total state tax withheld from stock compensation events."""
        return sum(event.state_tax_withheld for event in self.stock_compensation_events)

    def get_total_stock_compensation_amt_preference(self) -> float:
        """
        Get total AMT preference amount from ISO exercises.

        ISO spread at exercise is an AMT preference item even though
        it's not taxed for regular tax purposes.
        """
        return sum(event.calculate_amt_preference() for event in self.stock_compensation_events)

    def get_total_debt_cancellation_income(self) -> float:
        """
        Get total taxable debt cancellation income from Form 1099-C.

        Amount is reduced by applicable exclusions (bankruptcy, insolvency,
        qualified principal residence, etc.) per Form 982.
        """
        return sum(debt.get_taxable_amount() for debt in self.form_1099c_debt_cancellation)

    def get_taxable_alimony_received(self) -> float:
        """
        Get taxable alimony received.

        Only alimony from pre-2019 divorce agreements is taxable to recipient.
        Post-2018 agreements: alimony is NOT taxable to recipient.
        """
        # Check detailed alimony info first
        if self.alimony_info:
            if self.alimony_info.is_taxable_to_recipient():
                return self.alimony_info.alimony_received
            return 0.0
        # Fall back to simple field (assumes pre-2019 if using this field)
        return self.alimony_received

    def get_net_jury_duty_pay(self) -> float:
        """
        Get net jury duty pay (after remittance to employer).

        If employer paid wages during jury duty and employee remitted
        jury pay to employer, the remitted amount is deductible.
        """
        return max(0, self.jury_duty_pay - self.jury_duty_remitted_to_employer)

    def get_total_other_income(self) -> float:
        """
        Get total of miscellaneous income sources.

        Includes prizes/awards, taxable scholarships, and net jury duty pay.
        """
        return (
            self.prizes_and_awards +
            self.taxable_scholarship +
            self.get_net_jury_duty_pay()
        )

    # =========================================================================
    # Form 1099-Q (529/Coverdell) Helper Methods
    # =========================================================================

    def get_total_1099q_taxable(self) -> float:
        """
        Get total taxable amount from all Form 1099-Q distributions.

        Only the earnings portion of non-qualified distributions is taxable.
        Distributions used for qualified education expenses are tax-free.
        """
        return sum(dist.get_taxable_amount() for dist in self.form_1099q_distributions)

    def get_total_1099q_penalty(self) -> float:
        """
        Get total 10% penalty on non-qualified 529/Coverdell distributions.

        Penalty applies to the taxable earnings portion.
        """
        return sum(dist.get_penalty_amount() for dist in self.form_1099q_distributions)

    def get_1099q_summary(self) -> dict:
        """
        Get summary of all Form 1099-Q distributions.

        Returns breakdown of gross distributions, earnings, basis,
        qualified expenses, taxable amounts, and penalties.
        """
        if not self.form_1099q_distributions:
            return {}

        total_gross = sum(d.gross_distribution for d in self.form_1099q_distributions)
        total_earnings = sum(d.earnings for d in self.form_1099q_distributions)
        total_basis = sum(d.basis for d in self.form_1099q_distributions)
        total_qee = sum(d.get_adjusted_qualified_expenses() for d in self.form_1099q_distributions)
        total_taxable = self.get_total_1099q_taxable()
        total_penalty = self.get_total_1099q_penalty()

        return {
            'distribution_count': len(self.form_1099q_distributions),
            'total_gross_distribution': total_gross,
            'total_earnings': total_earnings,
            'total_basis': total_basis,
            'total_qualified_expenses': total_qee,
            'total_taxable': total_taxable,
            'total_penalty': total_penalty,
        }

    # =========================================================================
    # State Tax Refund Recovery Helper Methods
    # =========================================================================

    def get_total_taxable_state_refunds(self) -> float:
        """
        Get total taxable state/local tax refunds.

        Refunds are only taxable if the taxpayer itemized in the prior year
        and received a tax benefit from the SALT deduction (Tax Benefit Rule).
        """
        return sum(refund.get_taxable_amount() for refund in self.state_tax_refunds)

    def get_state_refund_summary(self) -> dict:
        """
        Get summary of state tax refund taxability.

        Returns breakdown of total refunds, taxable amounts, and
        which states' refunds are taxable.
        """
        if not self.state_tax_refunds:
            return {}

        total_refunds = sum(r.refund_amount for r in self.state_tax_refunds)
        total_taxable = self.get_total_taxable_state_refunds()
        taxable_states = [r.state_code for r in self.state_tax_refunds if r.is_taxable()]

        return {
            'refund_count': len(self.state_tax_refunds),
            'total_refund_amount': total_refunds,
            'total_taxable_amount': total_taxable,
            'taxable_states': taxable_states,
        }

    # =========================================================================
    # Form 1099-OID (Original Issue Discount) Helper Methods
    # =========================================================================

    def get_total_1099oid_taxable(self) -> float:
        """
        Get total taxable OID from all Form 1099-OID.

        OID is treated as interest income and taxed annually even if not received.
        Acquisition premium reduces the taxable amount.
        """
        return sum(oid.get_total_taxable_interest() for oid in self.form_1099oid)

    def get_total_1099oid_withholding(self) -> float:
        """Get total federal tax withheld from Form 1099-OID."""
        return sum(oid.federal_tax_withheld for oid in self.form_1099oid)

    def get_total_1099oid_early_withdrawal_penalty(self) -> float:
        """Get total early withdrawal penalties from Form 1099-OID (deductible)."""
        return sum(oid.early_withdrawal_penalty for oid in self.form_1099oid)

    def get_1099oid_summary(self) -> dict:
        """Get summary of all Form 1099-OID."""
        if not self.form_1099oid:
            return {}

        return {
            'count': len(self.form_1099oid),
            'total_oid': sum(o.original_issue_discount for o in self.form_1099oid),
            'total_other_interest': sum(o.other_periodic_interest for o in self.form_1099oid),
            'total_taxable': self.get_total_1099oid_taxable(),
            'total_early_withdrawal_penalty': self.get_total_1099oid_early_withdrawal_penalty(),
            'total_withholding': self.get_total_1099oid_withholding(),
            'total_tax_exempt_oid': sum(o.tax_exempt_oid for o in self.form_1099oid),
        }

    # =========================================================================
    # Form 1099-PATR (Patronage Dividends) Helper Methods
    # =========================================================================

    def get_total_1099patr_taxable(self) -> float:
        """Get total taxable distributions from cooperatives (Form 1099-PATR)."""
        return sum(patr.get_total_taxable() for patr in self.form_1099patr)

    def get_total_1099patr_withholding(self) -> float:
        """Get total federal tax withheld from Form 1099-PATR."""
        return sum(patr.federal_tax_withheld for patr in self.form_1099patr)

    def get_total_1099patr_section_199a(self) -> float:
        """Get total Section 199A(g) deduction from cooperatives."""
        return sum(patr.section_199a_deduction for patr in self.form_1099patr)

    def get_1099patr_summary(self) -> dict:
        """Get summary of all Form 1099-PATR patronage dividends."""
        if not self.form_1099patr:
            return {}

        return {
            'count': len(self.form_1099patr),
            'total_patronage_dividends': sum(p.patronage_dividends for p in self.form_1099patr),
            'total_nonpatronage': sum(p.nonpatronage_distributions for p in self.form_1099patr),
            'total_taxable': self.get_total_1099patr_taxable(),
            'total_section_199a_deduction': self.get_total_1099patr_section_199a(),
            'total_withholding': self.get_total_1099patr_withholding(),
        }

    # =========================================================================
    # Form 1099-LTC (Long-Term Care Benefits) Helper Methods
    # =========================================================================

    def get_total_1099ltc_taxable(self) -> float:
        """
        Get total taxable LTC benefits from all Form 1099-LTC.

        Per-diem payments are taxable only to extent exceeding daily limit or actual costs.
        Reimbursement payments for qualified expenses are not taxable.
        """
        return sum(ltc.get_taxable_amount() for ltc in self.form_1099ltc)

    def get_total_1099ltc_gross(self) -> float:
        """Get total gross LTC benefits received."""
        return sum(ltc.gross_ltc_benefits for ltc in self.form_1099ltc)

    def get_total_accelerated_death_benefits(self) -> float:
        """Get total accelerated death benefits (generally tax-free if terminally ill)."""
        return sum(ltc.accelerated_death_benefits for ltc in self.form_1099ltc)

    def get_1099ltc_summary(self) -> dict:
        """Get summary of all Form 1099-LTC."""
        if not self.form_1099ltc:
            return {}

        return {
            'count': len(self.form_1099ltc),
            'total_gross_benefits': self.get_total_1099ltc_gross(),
            'total_accelerated_death_benefits': self.get_total_accelerated_death_benefits(),
            'total_taxable': self.get_total_1099ltc_taxable(),
            'per_diem_count': sum(1 for ltc in self.form_1099ltc if ltc.is_per_diem),
            'reimbursement_count': sum(1 for ltc in self.form_1099ltc if not ltc.is_per_diem),
        }

    # =========================================================================
    # Form RRB-1099 (Railroad Retirement Benefits) Helper Methods
    # =========================================================================

    def get_total_rrb1099_gross_sseb(self) -> float:
        """Get total gross SSEB from all Form RRB-1099."""
        return sum(rrb.sseb_gross for rrb in self.form_rrb1099)

    def get_total_rrb1099_net_sseb(self) -> float:
        """Get total net SSEB (gross minus employee contributions)."""
        return sum(rrb.get_net_sseb() for rrb in self.form_rrb1099)

    def get_total_rrb1099_taxable(self, modified_agi: float, filing_status: str = "single") -> float:
        """
        Calculate total taxable SSEB from railroad retirement.

        Uses same taxation thresholds as Social Security benefits.
        """
        return sum(
            rrb.calculate_taxable_sseb(modified_agi, filing_status)
            for rrb in self.form_rrb1099
        )

    def get_total_rrb1099_withholding(self) -> float:
        """Get total federal tax withheld from Form RRB-1099."""
        return sum(rrb.federal_tax_withheld for rrb in self.form_rrb1099)

    def get_rrb1099_summary(self, modified_agi: float = 0.0, filing_status: str = "single") -> dict:
        """Get summary of all Form RRB-1099 railroad retirement benefits."""
        if not self.form_rrb1099:
            return {}

        return {
            'count': len(self.form_rrb1099),
            'total_gross_sseb': self.get_total_rrb1099_gross_sseb(),
            'total_net_sseb': self.get_total_rrb1099_net_sseb(),
            'total_taxable': self.get_total_rrb1099_taxable(modified_agi, filing_status),
            'total_withholding': self.get_total_rrb1099_withholding(),
            'total_medicare_premium': sum(rrb.medicare_premium for rrb in self.form_rrb1099),
        }

    # =========================================================================
    # Form 4137 (Unreported Tip Income) Helper Methods
    # =========================================================================

    def get_total_unreported_tips(self) -> float:
        """Get total unreported tip income from all Form 4137."""
        return sum(tips.get_unreported_tips() for tips in self.form_4137_tips)

    def get_total_form4137_ss_tax(self) -> float:
        """Get total Social Security tax due on unreported tips."""
        return sum(tips.calculate_ss_tax() for tips in self.form_4137_tips)

    def get_total_form4137_medicare_tax(self) -> float:
        """Get total Medicare tax due on unreported tips."""
        return sum(tips.calculate_medicare_tax() for tips in self.form_4137_tips)

    def get_total_form4137_tax(self) -> float:
        """Get total SS + Medicare tax due on unreported tips."""
        return sum(tips.get_total_tax() for tips in self.form_4137_tips)

    def get_form4137_summary(self) -> dict:
        """Get summary of all Form 4137 unreported tip income."""
        if not self.form_4137_tips:
            return {}

        return {
            'count': len(self.form_4137_tips),
            'total_cash_tips': sum(t.total_cash_tips for t in self.form_4137_tips),
            'total_reported_tips': sum(t.tips_reported_to_employer for t in self.form_4137_tips),
            'total_unreported_tips': self.get_total_unreported_tips(),
            'total_ss_tax': self.get_total_form4137_ss_tax(),
            'total_medicare_tax': self.get_total_form4137_medicare_tax(),
            'total_tax': self.get_total_form4137_tax(),
        }

    # =========================================================================
    # Clergy Housing Allowance (Section 107) Helper Methods
    # =========================================================================

    def get_clergy_housing_excludable(self) -> float:
        """Get excludable clergy housing allowance (not subject to income tax)."""
        if not self.clergy_housing:
            return 0.0
        return self.clergy_housing.get_excludable_amount()

    def get_clergy_housing_taxable(self) -> float:
        """Get taxable excess of clergy housing allowance over exclusion limit."""
        if not self.clergy_housing:
            return 0.0
        return self.clergy_housing.get_taxable_excess()

    def get_clergy_housing_se_amount(self) -> float:
        """
        Get amount subject to self-employment tax.

        Housing allowance is excluded from income tax but STILL subject to SE tax.
        """
        if not self.clergy_housing:
            return 0.0
        return self.clergy_housing.get_se_tax_amount()

    def get_clergy_housing_summary(self) -> dict:
        """Get summary of clergy housing allowance."""
        if not self.clergy_housing:
            return {}

        ch = self.clergy_housing
        return {
            'designated_allowance': ch.designated_allowance,
            'actual_expenses': ch.actual_housing_expenses,
            'fair_rental_value': ch.fair_rental_value,
            'parsonage_provided': ch.parsonage_provided,
            'excludable_amount': self.get_clergy_housing_excludable(),
            'taxable_excess': self.get_clergy_housing_taxable(),
            'se_tax_amount': self.get_clergy_housing_se_amount(),
            'is_ordained': ch.is_ordained_minister,
            'opted_out_se': ch.opted_out_of_se_tax,
        }

    # =========================================================================
    # Military Combat Pay Exclusion (Section 112) Helper Methods
    # =========================================================================

    def get_military_combat_pay_exclusion(self) -> float:
        """Get excludable combat zone pay."""
        if not self.military_combat_pay:
            return 0.0
        return self.military_combat_pay.get_excludable_combat_pay()

    def get_military_taxable_pay(self) -> float:
        """Get taxable military pay after combat exclusion."""
        if not self.military_combat_pay:
            return 0.0
        return self.military_combat_pay.get_taxable_military_pay()

    def get_military_eitc_earned_income(self) -> float:
        """
        Get military earned income for EITC.

        Can elect to include combat pay in earned income for EITC even
        though it's excluded from gross income.
        """
        if not self.military_combat_pay:
            return 0.0
        return self.military_combat_pay.get_eitc_earned_income()

    def get_military_combat_pay_summary(self) -> dict:
        """Get summary of military combat pay exclusion."""
        if not self.military_combat_pay:
            return {}

        mcp = self.military_combat_pay
        return {
            'total_military_pay': mcp.total_military_pay,
            'combat_zone_pay': mcp.combat_zone_pay,
            'excludable_amount': self.get_military_combat_pay_exclusion(),
            'taxable_pay': self.get_military_taxable_pay(),
            'is_enlisted': mcp.is_enlisted,
            'months_in_combat_zone': mcp.months_in_combat_zone,
            'elect_for_eitc': mcp.elect_combat_pay_for_eitc,
            'eitc_earned_income': self.get_military_eitc_earned_income(),
        }
