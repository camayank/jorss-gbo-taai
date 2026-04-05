"""
Tax Opportunity Detector - AI-Powered Tax Savings Identification.

Proactively identifies tax-saving opportunities based on taxpayer profile.
This implements multi-function AI routing for intelligent analysis.

Resolves Audit Finding: "AI is Severely Underutilized (Biggest Opportunity)"
"""

from __future__ import annotations

import asyncio
import os
import json
import logging
from contextvars import ContextVar
from functools import lru_cache
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from datetime import datetime

from services.ai import get_ai_service, run_async
from services.ai.metrics_service import get_ai_metrics_service
from services.irs_rag import get_irs_rag
from services.opportunity_scorer import get_opportunity_scorer
from config.ai_providers import ModelCapability, get_available_providers
from recommendation.tax_rules_engine import TaxRulesEngine
from rules.tax_rule_definitions import RuleCategory, RuleSeverity
from calculator.engine import FederalTaxEngine, TaxReturn, CalculationBreakdown
from calculator.state.state_tax_engine import StateTaxEngine
from models.taxpayer import TaxpayerInfo, FilingStatus, Dependent
from models.income_legacy import Income, W2Info
from models.deductions import Deductions, ItemizedDeductions
from models.credits import TaxCredits

logger = logging.getLogger(__name__)

# Per-call engine result caches using ContextVar — one dict per async task / thread.
# This replaces module-level dicts which were unsafe under concurrent requests
# (id(profile) reuse, no thread isolation).
#
# Usage: set at start of detect_opportunities(), reset in finally block.
# Sub-methods read via _engine_ctx.get({}) — returns {} (empty) if not in a call.
_engine_ctx: ContextVar[Dict[int, Any]] = ContextVar("_engine_ctx", default=None)
_state_ctx: ContextVar[Dict[int, Any]] = ContextVar("_state_ctx", default=None)


def _count_opp_fields(opp: "TaxOpportunity") -> int:
    """Count populated fields in a TaxOpportunity."""
    count = 0
    if opp.title:
        count += 1
    if opp.description:
        count += 1
    if opp.estimated_savings is not None:
        count += 1
    if opp.action_required:
        count += 1
    if opp.confidence is not None:
        count += 1
    if opp.irs_reference:
        count += 1
    return count


class OpportunityCategory(Enum):
    """Categories of tax-saving opportunities."""
    DEDUCTION = "deduction"
    CREDIT = "credit"
    RETIREMENT = "retirement"
    BUSINESS = "business"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    REAL_ESTATE = "real_estate"
    INVESTMENT = "investment"
    TIMING = "timing"
    FILING_STATUS = "filing_status"


class OpportunityPriority(Enum):
    """Priority levels for opportunities."""
    HIGH = "high"  # Immediate action, high savings
    MEDIUM = "medium"  # Good savings, worth exploring
    LOW = "low"  # Minor savings, nice to have


@dataclass
class TaxOpportunity:
    """A detected tax-saving opportunity."""
    id: str
    title: str
    description: str
    category: OpportunityCategory
    priority: OpportunityPriority
    estimated_savings: Optional[Decimal] = None
    savings_range: Optional[Tuple[Decimal, Decimal]] = None  # (min, max)
    action_required: str = ""
    irs_reference: Optional[str] = None  # IRS pub or form reference
    deadline: Optional[str] = None  # If time-sensitive
    confidence: float = 0.8  # 0-1 confidence score
    prerequisites: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)
    scenario_ids: List[str] = field(default_factory=list)  # ScenarioService template IDs
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaxpayerProfile:
    """Taxpayer profile for opportunity analysis."""
    # Basic info
    filing_status: str = "single"
    age: int = 35
    spouse_age: Optional[int] = None

    # Income
    w2_wages: Decimal = Decimal("0")
    self_employment_income: Decimal = Decimal("0")
    business_income: Decimal = Decimal("0")
    interest_income: Decimal = Decimal("0")
    dividend_income: Decimal = Decimal("0")
    capital_gains: Decimal = Decimal("0")
    rental_income: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")

    # Withholding
    federal_withheld: Decimal = Decimal("0")

    # Deductions already claimed
    mortgage_interest: Decimal = Decimal("0")
    property_taxes: Decimal = Decimal("0")
    state_local_taxes: Decimal = Decimal("0")
    charitable_contributions: Decimal = Decimal("0")
    medical_expenses: Decimal = Decimal("0")
    student_loan_interest: Decimal = Decimal("0")

    # Retirement
    traditional_401k: Decimal = Decimal("0")
    roth_401k: Decimal = Decimal("0")
    traditional_ira: Decimal = Decimal("0")
    roth_ira: Decimal = Decimal("0")
    hsa_contribution: Decimal = Decimal("0")

    # Family
    num_dependents: int = 0
    has_children_under_17: bool = False
    has_children_under_13: bool = False
    has_college_students: bool = False

    # Home
    owns_home: bool = False
    home_purchase_year: Optional[int] = None
    has_home_office: bool = False

    # Health
    has_hdhp: bool = False  # High Deductible Health Plan

    # Business
    has_business: bool = False
    business_type: Optional[str] = None
    is_sstb: Optional[bool] = None  # Specified Service Trade or Business
    business_net_income: Decimal = Decimal("0")

    # Education
    education_expenses: Decimal = Decimal("0")

    # Life events this year
    got_married: bool = False
    had_baby: bool = False
    bought_home: bool = False
    started_business: bool = False
    changed_jobs: bool = False
    got_divorced: bool = False
    spouse_died: bool = False
    retired_this_year: bool = False

    # Additional income sources
    social_security_income: Decimal = Decimal("0")
    pension_income: Decimal = Decimal("0")
    rmd_amount: Decimal = Decimal("0")          # Required Minimum Distributions
    k1_income: Decimal = Decimal("0")           # Partnership / S-Corp K-1 pass-through
    crypto_gains: Decimal = Decimal("0")        # Net cryptocurrency gains
    crypto_losses: Decimal = Decimal("0")       # Net cryptocurrency losses
    unemployment_income: Decimal = Decimal("0")
    alimony_received: Decimal = Decimal("0")    # Pre-2019 divorce only

    # Above-the-line deductions (Schedule 1 Part II)
    se_health_insurance: Decimal = Decimal("0")     # Self-employed health insurance premiums
    alimony_paid: Decimal = Decimal("0")            # Pre-2019 divorce only
    sep_ira_contribution: Decimal = Decimal("0")
    solo_401k_contribution: Decimal = Decimal("0")

    # Retirement account balances (for conversion analysis)
    ira_balance: Decimal = Decimal("0")
    roth_ira_balance: Decimal = Decimal("0")
    passive_losses_carryforward: Decimal = Decimal("0")

    # Healthcare additions
    dependent_care_expenses: Decimal = Decimal("0")
    has_dependent_care_fsa: bool = False
    dependent_care_fsa_amount: Decimal = Decimal("0")

    # Vehicle (for business use deduction)
    vehicle_business_miles: int = 0
    vehicle_personal_miles: int = 0

    # Energy / clean vehicle
    has_ev_purchase: bool = False               # Purchased qualifying EV this year
    ev_purchase_price: Decimal = Decimal("0")
    has_solar: bool = False
    solar_cost: Decimal = Decimal("0")
    has_home_energy_improvements: bool = False  # Heat pumps, insulation, etc.

    # Education savings
    has_529_plan: bool = False
    plan_529_contributions: Decimal = Decimal("0")

    # State
    state: str = ""                             # 2-letter state code (e.g. "CA", "NY")

    # Estimated / withholding
    es_payments_ytd: Decimal = Decimal("0")    # Quarterly estimated tax payments made

    # Charitable giving
    has_donor_advised_fund: bool = False
    appreciated_stock_held: bool = False        # Has long-term appreciated securities

    # ISO / equity comp
    has_iso_options: bool = False               # Incentive Stock Options exercised
    iso_exercises_ytd: Decimal = Decimal("0")
    has_nso_options: bool = False               # Non-qualified stock options
    has_rsu: bool = False                       # RSUs vested this year
    rsu_vested_value: Decimal = Decimal("0")
    has_espp: bool = False                      # Employee Stock Purchase Plan
    espp_income: Decimal = Decimal("0")
    has_company_stock_in_401k: bool = False     # For NUA strategy

    # Capital gain detail
    short_term_gains: Decimal = Decimal("0")   # Taxed at ordinary income rates
    long_term_gains: Decimal = Decimal("0")    # Taxed at 0/15/20%
    qualified_dividends: Decimal = Decimal("0") # Taxed at preferential rates

    # Rental real estate detail
    is_real_estate_professional: bool = False  # 750+ hours / material participation
    rental_active_participation: bool = False  # Active (not passive) investor
    str_rental_days: int = 0                   # Short-term rental (Airbnb) days rented
    str_personal_days: int = 0                 # Personal use days

    # Debt / financial events
    has_cod_income: bool = False               # Cancellation of debt (Form 1099-C)
    cod_amount: Decimal = Decimal("0")
    is_insolvent: bool = False                 # For COD exclusion

    # Business losses
    has_nol_carryforward: bool = False
    nol_amount: Decimal = Decimal("0")
    hobby_income: Decimal = Decimal("0")       # Income from hobby/unclear activity
    is_gig_worker: bool = False                # Uber, DoorDash, TaskRabbit, etc.

    # Household
    has_household_employee: bool = False       # Nanny, housekeeper, etc.
    household_employee_wages: Decimal = Decimal("0")

    # Miscellaneous income
    gambling_winnings: Decimal = Decimal("0")
    gambling_losses: Decimal = Decimal("0")
    educator_expenses: Decimal = Decimal("0")  # K-12 teachers: up to $300 deduction
    foreign_income: Decimal = Decimal("0")
    foreign_taxes_paid: Decimal = Decimal("0")
    has_fbar_requirement: bool = False          # Foreign accounts > $10K

    # Insurance / protection
    has_long_term_care_insurance: bool = False
    ltc_premiums_paid: Decimal = Decimal("0")

    # Opportunity zone
    has_opportunity_zone_investment: bool = False
    opportunity_zone_gain_deferred: Decimal = Decimal("0")

    # SECURE Act 2.0 / inherited IRA
    has_inherited_ira: bool = False
    inherited_ira_balance: Decimal = Decimal("0")
    inherited_ira_original_owner_dob: Optional[int] = None  # Year of original owner's death

    @property
    def total_income(self) -> Decimal:
        """Calculate total gross income including all sources."""
        return (
            self.w2_wages + self.self_employment_income + self.business_income +
            self.interest_income + self.dividend_income + self.capital_gains +
            self.rental_income + self.other_income +
            self.social_security_income + self.pension_income + self.rmd_amount +
            self.k1_income + self.crypto_gains + self.unemployment_income +
            self.alimony_received
        )

    @property
    def agi_estimate(self) -> Decimal:
        """Estimate AGI including all major above-the-line deductions (Schedule 1)."""
        se_tax_deduction = (
            self.self_employment_income * Decimal("0.9235") * Decimal("0.153") * Decimal("0.5")
        )
        above_line_deductions = (
            self.traditional_401k + self.traditional_ira +
            self.hsa_contribution + self.student_loan_interest +
            se_tax_deduction + self.se_health_insurance +
            self.alimony_paid + self.sep_ira_contribution +
            self.solo_401k_contribution
        )
        return max(Decimal("0"), self.total_income - above_line_deductions)


@lru_cache(maxsize=4)
def _get_rules_engine(tax_year: int) -> "TaxRulesEngine":
    """Cached TaxRulesEngine — avoids parsing 880+ rules on every request."""
    return TaxRulesEngine(tax_year=tax_year)


class TaxOpportunityDetector:
    """
    AI-powered tax opportunity detector.

    Uses multi-function calling to:
    1. Analyze taxpayer profile
    2. Identify missed deductions
    3. Find eligible credits
    4. Recommend tax-saving strategies
    5. Provide personalized action items
    """

    # 2025 Tax Constants
    TAX_YEAR = 2025

    # 2025 Federal ordinary income brackets (floor, rate) — used for exact marginal-rate savings estimates
    # Source: Rev. Proc. 2024-40 (IRS inflation adjustments for 2025)
    ORDINARY_BRACKETS: Dict[str, List[tuple]] = {
        "single": [
            (0,       0.10),
            (11925,   0.12),
            (48475,   0.22),
            (103350,  0.24),
            (197300,  0.32),
            (250525,  0.35),
            (626350,  0.37),
        ],
        "married_filing_jointly": [
            (0,       0.10),
            (23850,   0.12),
            (96950,   0.22),
            (206700,  0.24),
            (394600,  0.32),
            (501050,  0.35),
            (751600,  0.37),
        ],
        "married_filing_separately": [
            (0,       0.10),
            (11925,   0.12),
            (48475,   0.22),
            (103350,  0.24),
            (197300,  0.32),
            (250525,  0.35),
            (375800,  0.37),
        ],
        "head_of_household": [
            (0,       0.10),
            (17000,   0.12),
            (64850,   0.22),
            (103350,  0.24),
            (197300,  0.32),
            (250500,  0.35),
            (626350,  0.37),
        ],
        "qualifying_widow": [
            (0,       0.10),
            (23850,   0.12),
            (96950,   0.22),
            (206700,  0.24),
            (394600,  0.32),
            (501050,  0.35),
            (751600,  0.37),
        ],
    }

    # Standard deductions 2025 — per OBBBA (signed July 2025)
    STANDARD_DEDUCTION = {
        "single": Decimal("15750"),
        "married_filing_jointly": Decimal("31500"),
        "married_filing_separately": Decimal("15750"),
        "head_of_household": Decimal("23625"),
        "qualifying_widow": Decimal("31500"),
    }

    # Contribution limits 2025
    CONTRIB_LIMITS = {
        "401k": Decimal("23500"),
        "401k_catchup": Decimal("7500"),  # Age 50+
        "ira": Decimal("7000"),
        "ira_catchup": Decimal("1000"),  # Age 50+
        "hsa_individual": Decimal("4300"),
        "hsa_family": Decimal("8550"),
        "hsa_catchup": Decimal("1000"),  # Age 55+
    }

    # SALT cap — OBBBA (July 2025) raised to $40,000 (for AGI ≤ $500,000); was $10,000
    SALT_CAP = Decimal("40000")

    # Child Tax Credit
    CHILD_TAX_CREDIT = Decimal("2500")  # Per child under 17 — OBBBA 2025 (was $2,000)
    ACTC_MAX_PER_CHILD = Decimal("1700")  # Refundable portion 2025

    # EITC thresholds vary by children — 2025 per Rev. Proc. 2024-40
    EITC_MAX = {
        0: Decimal("649"),
        1: Decimal("4328"),
        2: Decimal("7152"),
        3: Decimal("8046"),  # 3 or more
    }

    # IRS standard mileage rate 2025
    MILEAGE_RATE_BUSINESS = Decimal("0.70")   # $0.70/mile

    # Net Investment Income Tax (NIIT) — 3.8% on investment income above threshold
    NIIT_THRESHOLD = {
        "married_filing_jointly": Decimal("250000"),
        "married_filing_separately": Decimal("125000"),
        "single": Decimal("200000"),
        "head_of_household": Decimal("200000"),
        "qualifying_widow": Decimal("250000"),
    }
    NIIT_RATE = Decimal("0.038")

    # EV / Clean Vehicle Credit (IRA 2022)
    EV_CREDIT_MAX = Decimal("7500")
    EV_INCOME_LIMIT_SINGLE = Decimal("150000")
    EV_INCOME_LIMIT_MFJ = Decimal("300000")

    # Residential Clean Energy Credit (solar)
    SOLAR_CREDIT_RATE = Decimal("0.30")   # 30% of cost through 2032

    # Home Energy Improvement Credit (heat pumps, insulation, windows)
    HOME_ENERGY_CREDIT_MAX = Decimal("3200")

    # Social Security combined income thresholds
    SS_COMBINED_50PCT = {"single": Decimal("25000"), "married_filing_jointly": Decimal("32000")}
    SS_COMBINED_85PCT = {"single": Decimal("34000"), "married_filing_jointly": Decimal("44000")}

    # Roth IRA income phase-outs 2025
    ROTH_PHASEOUT_START = {
        "single": Decimal("150000"),
        "married_filing_jointly": Decimal("236000"),
        "head_of_household": Decimal("150000"),
        "married_filing_separately": Decimal("0"),
    }
    ROTH_PHASEOUT_END = {
        "single": Decimal("165000"),
        "married_filing_jointly": Decimal("246000"),
        "head_of_household": Decimal("165000"),
        "married_filing_separately": Decimal("10000"),
    }

    # S-Corp SE tax break-even (roughly)
    SCORP_BREAKEVEN_SE_INCOME = Decimal("40000")

    # Medicare IRMAA surcharge starts at MAGI
    IRMAA_THRESHOLD_SINGLE = Decimal("103000")
    IRMAA_THRESHOLD_MFJ = Decimal("206000")

    # 529 contribution (gift tax annual exclusion) — 2025 per Rev. Proc. 2024-40
    ANNUAL_GIFT_EXCLUSION = Decimal("19000")  # 2025 (was $18,000 in 2024)
    SUPERFUNDING_MAX = Decimal("95000")        # 5-year election (5 × $19,000)

    # Qualified Charitable Distribution (QCD) — age 70½+
    QCD_MAX = Decimal("108000")  # 2025 per Rev. Proc. 2024-40 (up from $105,000 in 2024)

    # Additional Medicare Tax — 0.9% on wages above threshold
    ADD_MEDICARE_THRESHOLD = {
        "married_filing_jointly": Decimal("250000"),
        "single": Decimal("200000"),
        "head_of_household": Decimal("200000"),
        "married_filing_separately": Decimal("125000"),
    }

    # Long-term capital gains tax brackets 2025 (single / MFJ / HoH)
    LTCG_0PCT_SINGLE   = Decimal("48350")
    LTCG_15PCT_SINGLE  = Decimal("533400")
    LTCG_0PCT_MFJ      = Decimal("96700")
    LTCG_15PCT_MFJ     = Decimal("600050")

    # AMT exemption 2025
    AMT_EXEMPTION = {
        "single": Decimal("88100"),
        "married_filing_jointly": Decimal("137000"),
        "married_filing_separately": Decimal("68500"),
    }
    AMT_EXEMPTION_PHASEOUT_START = {
        "single": Decimal("626350"),
        "married_filing_jointly": Decimal("1252700"),
    }

    # Educator expense deduction
    EDUCATOR_EXPENSE_MAX = Decimal("300")

    # Long-term care insurance deduction limits by age 2025
    LTC_DEDUCTION_LIMITS = {
        40:  Decimal("480"),
        50:  Decimal("900"),
        60:  Decimal("1800"),
        70:  Decimal("4770"),
        99:  Decimal("5960"),
    }

    # States with no income tax (informational)
    NO_INCOME_TAX_STATES = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}

    # High-tax states (SALT planning is more urgent)
    HIGH_TAX_STATES = {"CA", "NY", "NJ", "MA", "OR", "MN", "IL", "CT", "WI", "VT"}

    # Qualified Opportunity Zone deferral deadline
    QOZ_DEFERRAL_YEAR = 2026

    # QSBS exclusion (§1202)
    QSBS_EXCLUSION_PCT = Decimal("0.50")  # 50% for pre-2010; 100% for 2010+

    # Nanny tax threshold 2025
    HOUSEHOLD_EMPLOYEE_THRESHOLD = Decimal("2700")

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        engine: Optional[Any] = None,
        state_engine: Optional[Any] = None,
        ai_service: Optional[Any] = None,
        irs_rag: Optional[Any] = None,
        skip_ai: bool = False,
    ):
        """
        Initialize detector.

        Keyword-only injection args allow unit tests to swap in mocks:
            engine      — FederalTaxEngine (or a mock with .calculate())
            state_engine — StateTaxEngine (or a mock with .calculate())
            ai_service  — AIService (or a mock with .extract())
            irs_rag     — IRSRag (or a mock with .format_multi())
            skip_ai     — Force-disable AI passes (useful in tests/CI)

        Example test usage:
            det = TaxOpportunityDetector(engine=MockEngine(), skip_ai=True)
        """
        self._ai_available = (not skip_ai) and len(get_available_providers()) > 0
        if not self._ai_available and not skip_ai:
            logger.warning("No AI providers configured - running in rule-based mode only")
        self._engine = engine or FederalTaxEngine()
        self._state_engine = state_engine or StateTaxEngine(tax_year=self.TAX_YEAR)
        self._irs_rag = irs_rag or get_irs_rag()
        self._injected_ai_service = ai_service  # None → use get_ai_service() lazily

    # =========================================================================
    # FEDERAL TAX ENGINE: profile → TaxReturn conversion
    # =========================================================================

    # Map TaxpayerProfile.filing_status strings → FilingStatus enum values
    _FS_MAP = {
        "single":                   "single",
        "married_filing_jointly":   "married_joint",
        "married_filing_separately":"married_separate",
        "head_of_household":        "head_of_household",
        "qualifying_widow":         "qualifying_widow",
    }

    # All TaxpayerProfile income-bearing fields that are mapped to TaxReturn.
    # Any field added to TaxpayerProfile that affects liability MUST appear here.
    _MAPPED_INCOME_FIELDS: frozenset = frozenset({
        "w2_wages", "self_employment_income", "business_income",
        "interest_income", "dividend_income", "qualified_dividends",
        "capital_gains", "short_term_gains", "long_term_gains", "rental_income",
        "social_security_income", "pension_income", "other_income", "k1_income",
        "unemployment_income", "alimony_received", "gambling_losses",
        "federal_withheld", "traditional_401k", "roth_401k",
    })

    def _profile_to_tax_return(self, profile: "TaxpayerProfile") -> TaxReturn:
        """
        Convert a TaxpayerProfile snapshot into a FederalTaxEngine TaxReturn.

        Only the fields that materially affect tax liability are populated.
        Anything not present in the profile defaults to zero / False.
        """
        # Warn about any income-type fields added to TaxpayerProfile but not
        # mapped here — they would silently become $0 in the engine calculation.
        all_fields = {f for f in vars(profile) if not f.startswith("_")}
        candidate_unmapped = {
            f for f in all_fields
            if ("income" in f or "gains" in f or "wages" in f or "withheld" in f)
            and f not in self._MAPPED_INCOME_FIELDS
            and getattr(profile, f, 0)  # only warn when non-zero
        }
        if candidate_unmapped:
            logger.warning(
                "_profile_to_tax_return: possibly unmapped income fields (will be $0): %s",
                candidate_unmapped,
            )
        fs_str = self._FS_MAP.get(profile.filing_status, "single")
        fs_enum = FilingStatus(fs_str)

        # Build dependents from profile flags
        deps: List[Dependent] = []
        if profile.has_children_under_13:
            for i in range(min(profile.num_dependents, 4)):
                deps.append(Dependent(
                    name=f"Child {i+1}", relationship="child",
                    age=8, months_lived_with_taxpayer=12,
                    is_us_citizen=True, lives_with_you=True,
                ))
        elif profile.has_children_under_17:
            for i in range(min(profile.num_dependents, 4)):
                deps.append(Dependent(
                    name=f"Child {i+1}", relationship="child",
                    age=14, months_lived_with_taxpayer=12,
                    is_us_citizen=True, lives_with_you=True,
                ))
        elif profile.num_dependents > 0 and not deps:
            for i in range(min(profile.num_dependents, 4)):
                deps.append(Dependent(
                    name=f"Dependent {i+1}", relationship="other",
                    age=20, months_lived_with_taxpayer=12,
                    is_us_citizen=True, lives_with_you=True,
                ))

        taxpayer = TaxpayerInfo(
            first_name="Taxpayer", last_name="Profile",
            filing_status=fs_enum,
            state=profile.state or None,
            dependents=deps,
            is_over_65=(profile.age >= 65),
            is_age_50_plus=(profile.age >= 50),
            spouse_is_over_65=(
                profile.spouse_age is not None and profile.spouse_age >= 65
            ),
        )

        w2_list = []
        if profile.w2_wages > 0:
            w2_list.append(W2Info(
                employer_name="Employer",
                wages=float(profile.w2_wages),
                federal_tax_withheld=float(profile.federal_withheld),
                retirement_plan_contributions=float(
                    profile.traditional_401k + profile.roth_401k
                ),
            ))

        income = Income(
            w2_forms=w2_list,
            self_employment_income=float(profile.self_employment_income + profile.business_income),
            interest_income=float(profile.interest_income),
            dividend_income=float(profile.dividend_income),
            qualified_dividends=float(profile.qualified_dividends),
            short_term_capital_gains=float(
                profile.short_term_gains
                if (profile.short_term_gains != 0 or profile.long_term_gains != 0)
                else profile.short_term_gains + profile.capital_gains / 2
            ),
            long_term_capital_gains=float(
                profile.long_term_gains
                if (profile.short_term_gains != 0 or profile.long_term_gains != 0)
                else profile.long_term_gains + profile.capital_gains / 2
            ),
            rental_income=float(profile.rental_income),
            social_security_benefits=float(profile.social_security_income),
            other_income=float(profile.pension_income + profile.other_income + profile.k1_income),
            unemployment_compensation=float(profile.unemployment_income),
            gambling_losses=float(profile.gambling_losses),
            alimony_received=float(profile.alimony_received),
        )

        itemized = ItemizedDeductions(
            medical_expenses=float(profile.medical_expenses),
            state_local_income_tax=float(profile.state_local_taxes),
            real_estate_tax=float(profile.property_taxes),
            mortgage_interest=float(profile.mortgage_interest),
            charitable_cash=float(profile.charitable_contributions),
        )

        deductions = Deductions(
            use_standard_deduction=True,   # engine picks whichever is higher
            itemized=itemized,
            student_loan_interest=float(profile.student_loan_interest),
            hsa_contributions=float(profile.hsa_contribution),
            ira_contributions=float(profile.traditional_ira),
            self_employed_se_health=float(profile.se_health_insurance),
            self_employed_sep_simple=float(
                profile.sep_ira_contribution + profile.solo_401k_contribution
            ),
            alimony_paid=float(profile.alimony_paid),
        )

        credits = TaxCredits()

        return TaxReturn(
            tax_year=self.TAX_YEAR,
            taxpayer=taxpayer,
            income=income,
            deductions=deductions,
            credits=credits,
            state_of_residence=profile.state or None,
        )

    def _run_engine(self, profile: "TaxpayerProfile") -> Optional["CalculationBreakdown"]:
        """
        Run FederalTaxEngine + StateTaxEngine on the profile.
        Returns None on any error (callers fall back to _marginal_rate()).
        State result is stored in _state_cache keyed by id(profile).
        """
        try:
            tax_return = self._profile_to_tax_return(profile)
            bd = self._engine.calculate(tax_return)
            # Also compute state tax if state is set
            if profile.state:
                try:
                    state_bd = self._state_engine.calculate(tax_return, profile.state)
                    (_state_ctx.get() or {})[id(profile)] = state_bd
                except Exception as state_exc:
                    logger.debug("StateTaxEngine failed for %s: %s", profile.state, state_exc)
                    (_state_ctx.get() or {})[id(profile)] = None
            return bd
        except Exception as exc:  # noqa: BLE001
            logger.debug("FederalTaxEngine failed (%s) — falling back to bracket approx", exc)
            return None

    # =========================================================================
    # EXACT MARGINAL RATE HELPERS
    # =========================================================================

    def _marginal_rate(self, profile: "TaxpayerProfile") -> Decimal:
        """
        Return the taxpayer's actual federal marginal rate as a Decimal.

        Prefers the FederalTaxEngine result (exact Form 1040) when available;
        falls back to bracket lookup on the estimated AGI otherwise.
        """
        breakdown = (_engine_ctx.get() or {}).get(id(profile))
        if breakdown is not None and breakdown.taxable_income > 0:
            # marginal_tax_rate: engine stores as percentage (e.g. 24.0) when taxable_income > 0
            rate = Decimal(str(round(breakdown.marginal_tax_rate / 100, 4)))
            if rate > Decimal("0.01"):  # sanity: must be at least 1%
                return rate

        std = self.STANDARD_DEDUCTION.get(profile.filing_status, Decimal("15000"))
        salt = min(profile.state_local_taxes + profile.property_taxes, self.SALT_CAP)
        itemized = profile.mortgage_interest + salt + profile.charitable_contributions + profile.medical_expenses
        deduction = max(std, itemized)
        taxable_income = float(max(Decimal("0"), profile.agi_estimate - deduction))

        brackets = self.ORDINARY_BRACKETS.get(
            profile.filing_status,
            self.ORDINARY_BRACKETS["single"],
        )
        marginal = Decimal("0.10")
        for floor, rate in brackets:
            if taxable_income > floor:
                marginal = Decimal(str(rate))
        return marginal

    def _savings(self, profile: "TaxpayerProfile", deduction_amount: Decimal) -> Decimal:
        """Estimate federal tax savings from a deduction using the exact marginal rate."""
        return deduction_amount * self._marginal_rate(profile)

    def _delta_tax(
        self,
        profile: "TaxpayerProfile",
        modify_fn: "Callable[[TaxReturn], None]",
    ) -> Optional[Decimal]:
        """
        Compute exact tax savings by running FederalTaxEngine twice.

        Calls modify_fn(tax_return) to apply the optimization being tested
        (e.g. increase IRA contribution, add deduction), then returns:
            baseline_total_tax - modified_total_tax

        Returns None when the engine is unavailable or the savings are ≤ 0
        (i.e. the modification costs money rather than saving it).
        """
        baseline = (_engine_ctx.get() or {}).get(id(profile))
        if baseline is None:
            return None
        try:
            modified_tr = self._profile_to_tax_return(profile)
            modify_fn(modified_tr)
            modified_bd = self._engine.calculate(modified_tr)
            delta = baseline.total_tax - modified_bd.total_tax
            return Decimal(str(round(delta, 2))) if delta > 0.50 else None
        except Exception as exc:
            logger.debug("_delta_tax failed (%s)", exc)
            return None

    def _delta_deduction(self, profile: "TaxpayerProfile", amount: float) -> Optional[Decimal]:
        """Exact savings from adding `amount` to above-the-line adjustments (other_adjustments)."""
        def _mod(tr: TaxReturn) -> None:
            tr.deductions.other_adjustments = tr.deductions.other_adjustments + amount
        return self._delta_tax(profile, _mod)

    def _delta_ira(self, profile: "TaxpayerProfile", amount: float) -> Optional[Decimal]:
        """Exact savings from adding `amount` to traditional IRA contributions."""
        def _mod(tr: TaxReturn) -> None:
            tr.deductions.ira_contributions = tr.deductions.ira_contributions + amount
        return self._delta_tax(profile, _mod)

    def _delta_hsa(self, profile: "TaxpayerProfile", amount: float) -> Optional[Decimal]:
        """Exact savings from adding `amount` to HSA contributions."""
        def _mod(tr: TaxReturn) -> None:
            tr.deductions.hsa_contributions = tr.deductions.hsa_contributions + amount
        return self._delta_tax(profile, _mod)

    def _delta_sep(self, profile: "TaxpayerProfile", amount: float) -> Optional[Decimal]:
        """Exact savings from adding `amount` to SEP-IRA / Solo 401(k)."""
        def _mod(tr: TaxReturn) -> None:
            tr.deductions.self_employed_sep_simple = tr.deductions.self_employed_sep_simple + amount
        return self._delta_tax(profile, _mod)

    def _combined_rate(self, profile: "TaxpayerProfile") -> Decimal:
        """Federal marginal rate + rough SE tax rate (for SE filers)."""
        fed = self._marginal_rate(profile)
        se_rate = (
            Decimal("0.1413")   # ~14.13% net SE tax on additional SE income
            if profile.self_employment_income > Decimal("5000")
            else Decimal("0")
        )
        return fed + se_rate

    def detect_opportunities(self, profile: TaxpayerProfile, max_results: Optional[int] = 25) -> List[TaxOpportunity]:
        """
        Detect all tax-saving opportunities for a taxpayer.

        Uses FederalTaxEngine for exact savings figures, then rule-based
        detection and AI analysis.
        """
        opportunities = []

        # ── Per-call isolated caches (thread-safe via ContextVar) ────────────
        _call_engine: Dict[int, Any] = {}
        _call_state: Dict[int, Any] = {}
        _tok_engine = _engine_ctx.set(_call_engine)
        _tok_state = _state_ctx.set(_call_state)

        # ── Run FederalTaxEngine once (exact Form 1040 + state calculation) ──
        breakdown: Optional[CalculationBreakdown] = self._run_engine(profile)
        if breakdown:
            _call_engine[id(profile)] = breakdown
            logger.debug(
                "FederalTaxEngine: AGI=$%.0f  taxable=$%.0f  marginal=%.0f%%  "
                "total_tax=$%.0f  effective=%.1f%%  AMT=$%.0f  NIIT=$%.0f  state_tax=$%.0f",
                breakdown.agi, breakdown.taxable_income,
                breakdown.marginal_tax_rate,
                breakdown.total_tax, breakdown.effective_tax_rate,
                breakdown.alternative_minimum_tax,
                breakdown.net_investment_income_tax,
                getattr(breakdown, "state_tax_liability", 0) or 0,
            )

        # Rule-based detection (fast, reliable)
        rule_opps = []
        rule_opps.extend(self._detect_retirement_opportunities(profile))
        rule_opps.extend(self._detect_advanced_retirement_opportunities(profile))
        rule_opps.extend(self._detect_deduction_opportunities(profile))
        rule_opps.extend(self._detect_advanced_deductions(profile))
        rule_opps.extend(self._detect_credit_opportunities(profile))
        rule_opps.extend(self._detect_advanced_credits(profile))
        rule_opps.extend(self._detect_hsa_opportunities(profile))
        rule_opps.extend(self._detect_business_opportunities(profile))
        rule_opps.extend(self._detect_se_advanced_opportunities(profile))
        rule_opps.extend(self._detect_real_estate_advanced_opportunities(profile))
        rule_opps.extend(self._detect_investment_tax_opportunities(profile))
        rule_opps.extend(self._detect_education_opportunities(profile))
        rule_opps.extend(self._detect_filing_status_opportunities(profile))
        rule_opps.extend(self._detect_timing_opportunities(profile))
        rule_opps.extend(self._detect_senior_tax_planning(profile))
        rule_opps.extend(self._detect_estimated_tax(profile))
        rule_opps.extend(self._detect_energy_credits(profile))
        rule_opps.extend(self._detect_vehicle_deduction(profile))
        rule_opps.extend(self._detect_equity_comp(profile))
        rule_opps.extend(self._detect_capital_gain_optimization(profile))
        rule_opps.extend(self._detect_rental_advanced(profile))
        rule_opps.extend(self._detect_special_situations(profile))
        rule_opps.extend(self._detect_household_employer(profile))
        rule_opps.extend(self._detect_miscellaneous(profile))
        rule_opps.extend(self._detect_advanced_special(profile))
        rule_opps.extend(self._detect_state_guidance(profile))
        rule_opps.extend(self._detect_deadline_and_penalty_rules(profile))
        rule_opps.extend(self._detect_via_rules_engine(profile))
        rule_opps.extend(self._detect_engine_insights(profile))
        rule_opps.extend(self._detect_multiyear_planning(profile))
        for opp in rule_opps:
            opp.metadata["_source"] = "rules"
        opportunities.extend(rule_opps)

        # AI-powered analysis for nuanced opportunities
        if self._ai_available:
            ai_opportunities = self._ai_detect_opportunities(profile)
            for opp in ai_opportunities:
                opp.metadata["_source"] = "ai"
            opportunities.extend(ai_opportunities)

        # Score, rank, deduplicate → return top max_results most actionable
        # Pass max_results=None to get all (used by tests and bulk export).
        ranked = get_opportunity_scorer().score_and_rank(opportunities, profile, top_k=max_results)

        # Record quality once per opportunity actually returned (post-deduplication),
        # so quality record count matches the returned opportunity count.
        metrics = get_ai_metrics_service()
        for opp in ranked:
            metrics.record_response_quality(
                service="opportunity_detector",
                source=opp.metadata.get("_source", "rules"),
                response_fields_populated=_count_opp_fields(opp),
                total_fields=6,
            )

        # Reset context vars — caches are GC'd when refs drop to zero
        _engine_ctx.reset(_tok_engine)
        _state_ctx.reset(_tok_state)

        return ranked

    def _detect_retirement_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect retirement contribution opportunities."""
        opportunities = []

        # 401(k) under-contribution
        max_401k = self.CONTRIB_LIMITS["401k"]
        if profile.age >= 50:
            max_401k += self.CONTRIB_LIMITS["401k_catchup"]

        current_401k = profile.traditional_401k + profile.roth_401k
        if current_401k < max_401k and profile.total_income > Decimal("50000"):
            room = max_401k - current_401k
            estimated_savings = (
                self._delta_deduction(profile, float(room))
                or room * self._marginal_rate(profile)
            )

            opportunities.append(TaxOpportunity(
                id="retirement_401k_room",
                title="Maximize 401(k) Contribution",
                description=f"You have ${room:,.0f} in unused 401(k) contribution room for {self.TAX_YEAR}. "
                           f"Contributing the maximum reduces your taxable income.",
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=estimated_savings,
                action_required="Increase 401(k) contribution through your employer's payroll",
                irs_reference="IRS Publication 560",
                deadline=f"December 31, {self.TAX_YEAR}",
                confidence=0.95,
                scenario_ids=["max_401k", "all_retirement"],
                follow_up_questions=[
                    "Does your employer offer a 401(k) match?",
                    "What percentage are you currently contributing?"
                ]
            ))

        # IRA opportunity
        max_ira = self.CONTRIB_LIMITS["ira"]
        if profile.age >= 50:
            max_ira += self.CONTRIB_LIMITS["ira_catchup"]

        current_ira = profile.traditional_ira + profile.roth_ira
        if current_ira < max_ira and profile.total_income > Decimal("30000"):
            room = max_ira - current_ira
            estimated_savings = (
                self._delta_ira(profile, float(room))
                or room * self._marginal_rate(profile)
            )

            opportunities.append(TaxOpportunity(
                id="retirement_ira_room",
                title="Contribute to IRA",
                description=f"You can contribute up to ${max_ira:,.0f} to an IRA for {self.TAX_YEAR}. "
                           f"Traditional IRA contributions may be tax-deductible.",
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH if room > Decimal("5000") else OpportunityPriority.MEDIUM,
                estimated_savings=estimated_savings,
                action_required="Open or contribute to an IRA before the tax filing deadline",
                irs_reference="IRS Publication 590-A",
                deadline=f"April 15, {self.TAX_YEAR + 1}",
                confidence=0.90,
                scenario_ids=["max_ira", "all_retirement"],
                prerequisites=["Must have earned income"],
                follow_up_questions=[
                    "Do you already have an IRA?",
                    "Traditional or Roth - which is better for your situation?"
                ]
            ))

        return opportunities

    def _detect_hsa_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect HSA contribution opportunities."""
        opportunities = []

        if profile.has_hdhp:
            # Determine HSA limit based on coverage type
            is_family = profile.filing_status in ["married_filing_jointly", "head_of_household"] or profile.num_dependents > 0
            max_hsa = self.CONTRIB_LIMITS["hsa_family"] if is_family else self.CONTRIB_LIMITS["hsa_individual"]

            if profile.age >= 55:
                max_hsa += self.CONTRIB_LIMITS["hsa_catchup"]

            if profile.hsa_contribution < max_hsa:
                room = max_hsa - profile.hsa_contribution
                # HSA: exact delta (federal + FICA) or ~30% combined fallback
                estimated_savings = (
                    self._delta_hsa(profile, float(room))
                    or room * (self._marginal_rate(profile) + Decimal("0.0765"))
                )

                opportunities.append(TaxOpportunity(
                    id="hsa_maximize",
                    title="Maximize HSA Contribution",
                    description=f"HSAs offer triple tax advantages: tax-deductible, tax-free growth, and tax-free withdrawals for medical expenses. "
                               f"You have ${room:,.0f} in unused contribution room.",
                    category=OpportunityCategory.HEALTHCARE,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=estimated_savings,
                    action_required="Contribute to your HSA before year-end or by April 15 for prior year",
                    irs_reference="IRS Publication 969",
                    deadline=f"April 15, {self.TAX_YEAR + 1}",
                    confidence=0.95,
                    scenario_ids=["max_hsa", "all_retirement"],
                    follow_up_questions=["Do you have an HSA account set up?"]
                ))
        elif profile.total_income > Decimal("40000") and profile.age < 65:
            # Suggest HDHP + HSA if they don't have one (Medicare enrollees 65+ cannot contribute to HSAs)
            opportunities.append(TaxOpportunity(
                id="hsa_consider",
                title="Consider High-Deductible Health Plan with HSA",
                description="If eligible, an HDHP with HSA can provide significant tax savings through "
                           "tax-deductible contributions and tax-free growth.",
                category=OpportunityCategory.HEALTHCARE,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("1000"), Decimal("3000")),
                action_required="Review health plan options during open enrollment",
                irs_reference="IRS Publication 969",
                confidence=0.70,
                follow_up_questions=[
                    "What type of health insurance do you currently have?",
                    "Do you have significant medical expenses?"
                ]
            ))

        return opportunities

    def _detect_deduction_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect missed deduction opportunities."""
        opportunities = []

        # Standard vs. Itemized analysis
        standard = self.STANDARD_DEDUCTION.get(profile.filing_status, Decimal("15000"))

        current_itemized = (
            profile.mortgage_interest +
            min(profile.property_taxes + profile.state_local_taxes, self.SALT_CAP) +
            profile.charitable_contributions +
            max(Decimal("0"), profile.medical_expenses - profile.agi_estimate * Decimal("0.075"))
        )

        itemized_benefit = current_itemized - standard

        if itemized_benefit > Decimal("0"):
            opportunities.append(TaxOpportunity(
                id="itemize_deductions",
                title="Consider Itemizing Deductions",
                description=f"Your itemized deductions (${current_itemized:,.0f}) exceed the standard deduction "
                           f"(${standard:,.0f}) by ${itemized_benefit:,.0f}. Itemizing will reduce your taxes.",
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.HIGH,
                estimated_savings=itemized_benefit * self._marginal_rate(profile),
                action_required="File Schedule A with itemized deductions",
                irs_reference="Schedule A (Form 1040)",
                confidence=0.95
            ))
        elif itemized_benefit > Decimal("-2000") and profile.charitable_contributions > 0:
            # Close to itemizing - bunching strategy
            gap = standard - current_itemized
            opportunities.append(TaxOpportunity(
                id="deduction_bunching",
                title="Deduction Bunching Strategy",
                description=f"You're ${gap:,.0f} away from itemizing. Consider 'bunching' deductions - "
                           f"prepaying property taxes or making charitable contributions before year-end to itemize this year.",
                category=OpportunityCategory.TIMING,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=gap * self._marginal_rate(profile),
                action_required="Prepay deductible expenses before December 31",
                irs_reference="IRS Publication 17",
                deadline=f"December 31, {self.TAX_YEAR}",
                confidence=0.80,
                follow_up_questions=[
                    "Can you prepay your property taxes?",
                    "Do you plan to make any charitable contributions?"
                ]
            ))

        # Student loan interest (above the line) — phase-out $80K–$95K single, up to $195K MFJ
        # Use $110K as reminder threshold to account for SE deductions not captured in agi_estimate
        _sli_limit = Decimal("195000") if profile.filing_status == "married_filing_jointly" else Decimal("110000")
        if profile.student_loan_interest == 0 and profile.agi_estimate < _sli_limit:
            opportunities.append(TaxOpportunity(
                id="student_loan_interest",
                title="Student Loan Interest Deduction",
                description="If you paid student loan interest this year, you may deduct up to $2,500. "
                           "This is an 'above-the-line' deduction, meaning you can claim it even with the standard deduction.",
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("100"), Decimal("550")),
                action_required="Report student loan interest from Form 1098-E",
                irs_reference="IRS Publication 970",
                confidence=0.60,
                follow_up_questions=["Do you have student loans?", "Did you pay any interest this year?"]
            ))

        return opportunities

    def _detect_credit_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect tax credit opportunities."""
        opportunities = []

        # Child Tax Credit
        if profile.has_children_under_17:
            estimated_credit = self.CHILD_TAX_CREDIT * profile.num_dependents
            opportunities.append(TaxOpportunity(
                id="child_tax_credit",
                title="Child Tax Credit",
                description=f"You may qualify for up to ${self.CHILD_TAX_CREDIT:,.0f} per qualifying child under 17. "
                           f"With {profile.num_dependents} children, potential credit: ${estimated_credit:,.0f}.",
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=estimated_credit,
                action_required="Claim on Form 1040 and Schedule 8812 if applicable",
                irs_reference="IRS Publication 972",
                confidence=0.90,
                prerequisites=["Children must have SSN", "Income limits apply"]
            ))

        # Child and Dependent Care Credit
        if profile.has_children_under_13 and (profile.w2_wages > 0 or profile.self_employment_income > 0):
            max_credit = Decimal("1050") if profile.num_dependents == 1 else Decimal("2100")
            opportunities.append(TaxOpportunity(
                id="dependent_care_credit",
                title="Child and Dependent Care Credit",
                description="If you paid for childcare to work or look for work, you may claim a credit "
                           f"of up to ${max_credit:,.0f}.",
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=max_credit,
                action_required="File Form 2441 with your tax return",
                irs_reference="IRS Publication 503",
                confidence=0.85,
                follow_up_questions=[
                    "Did you pay for daycare or after-school care?",
                    "Do you have receipts with the provider's tax ID?"
                ]
            ))

        # EITC — 2025 income limits per Rev. Proc. 2024-40 (3+ children phaseout end)
        eitc_income_limit = {
            "single": Decimal("59899"),
            "married_filing_jointly": Decimal("66819"),
            "head_of_household": Decimal("59899"),
        }

        if profile.filing_status in eitc_income_limit:
            limit = eitc_income_limit[profile.filing_status]
            if profile.agi_estimate < limit and (profile.w2_wages > 0 or profile.self_employment_income > 0):
                children_key = min(profile.num_dependents, 3)
                max_eitc = self.EITC_MAX[children_key]

                opportunities.append(TaxOpportunity(
                    id="eitc",
                    title="Earned Income Tax Credit (EITC)",
                    description=f"Based on your income and family size, you may qualify for EITC of up to ${max_eitc:,.0f}. "
                               f"This is a refundable credit - you can get it even if you owe no tax.",
                    category=OpportunityCategory.CREDIT,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=max_eitc,
                    action_required="File Schedule EIC with your tax return",
                    irs_reference="IRS Publication 596",
                    confidence=0.75,
                    prerequisites=["Must have earned income", "Investment income limit applies"]
                ))

        # Saver's Credit — 2025 income thresholds per Rev. Proc. 2024-40
        _savers_limit = {
            "married_filing_jointly": Decimal("79000"),
            "head_of_household": Decimal("59250"),
        }.get(profile.filing_status, Decimal("39500"))  # single / MFS
        if profile.agi_estimate < _savers_limit:
            if profile.traditional_401k + profile.roth_401k + profile.traditional_ira + profile.roth_ira > 0:
                max_credit = Decimal("2000") if profile.filing_status == "married_filing_jointly" else Decimal("1000")
                opportunities.append(TaxOpportunity(
                    id="savers_credit",
                    title="Saver's Credit",
                    description="You may qualify for a credit of up to 50% of your retirement contributions "
                               f"(max ${max_credit:,.0f}) based on your income level.",
                    category=OpportunityCategory.RETIREMENT,
                    priority=OpportunityPriority.MEDIUM,
                    estimated_savings=max_credit,
                    action_required="File Form 8880 with your tax return",
                    irs_reference="IRS Form 8880",
                    confidence=0.80
                ))

        return opportunities

    def _detect_business_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect business-related opportunities."""
        opportunities = []

        if not profile.has_business and profile.self_employment_income == 0:
            return opportunities

        # QBI Deduction (Section 199A)
        qbi_eligible_income = profile.business_net_income or profile.self_employment_income
        if qbi_eligible_income > 0:
            # SSTB limitation check
            if profile.is_sstb and profile.agi_estimate > Decimal("197300"):  # 2025 single threshold per Rev. Proc. 2024-40
                opportunities.append(TaxOpportunity(
                    id="qbi_sstb_warning",
                    title="QBI Deduction Phase-Out (SSTB)",
                    description="As a Specified Service Trade or Business (SSTB), your QBI deduction "
                               "begins to phase out at your income level. Consider strategies to stay below the threshold.",
                    category=OpportunityCategory.BUSINESS,
                    priority=OpportunityPriority.MEDIUM,
                    action_required="Consider timing income/expenses to manage AGI",
                    irs_reference="IRC Section 199A",
                    confidence=0.85
                ))
            else:
                qbi_deduction = qbi_eligible_income * Decimal("0.20")
                opportunities.append(TaxOpportunity(
                    id="qbi_deduction",
                    title="Qualified Business Income (QBI) Deduction",
                    description=f"You may be eligible for a 20% deduction on qualified business income. "
                               f"Estimated deduction: ${qbi_deduction:,.0f}.",
                    category=OpportunityCategory.BUSINESS,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=qbi_deduction * self._marginal_rate(profile),
                    action_required="This is calculated automatically on Form 8995 or 8995-A",
                    irs_reference="IRS Form 8995",
                    confidence=0.90
                ))

        # Home Office Deduction
        if profile.has_home_office or profile.has_business:
            opportunities.append(TaxOpportunity(
                id="home_office",
                title="Home Office Deduction",
                description="If you use part of your home regularly and exclusively for business, "
                           "you can deduct home office expenses. Simplified method: $5/sq ft up to 300 sq ft ($1,500 max).",
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("500"), Decimal("1500")),
                action_required="Calculate using Form 8829 or simplified method",
                irs_reference="IRS Publication 587",
                confidence=0.75,
                follow_up_questions=[
                    "What is the square footage of your home office?",
                    "Is this space used exclusively for business?"
                ]
            ))

        # Self-Employment Tax Deduction
        if profile.self_employment_income > Decimal("400"):
            se_tax = profile.self_employment_income * Decimal("0.153")
            deduction = se_tax * Decimal("0.5")
            opportunities.append(TaxOpportunity(
                id="se_tax_deduction",
                title="Self-Employment Tax Deduction",
                description=f"You can deduct 50% of your self-employment tax (${deduction:,.0f}) "
                           "as an above-the-line deduction.",
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=deduction * self._marginal_rate(profile),
                action_required="This is calculated automatically on Schedule SE and Form 1040",
                irs_reference="Schedule SE",
                confidence=0.95
            ))

        # SEP-IRA for Self-Employed
        if profile.self_employment_income > Decimal("10000"):
            max_sep = min(profile.self_employment_income * Decimal("0.25"), Decimal("70000"))
            if profile.traditional_401k == 0:  # No employer 401k
                opportunities.append(TaxOpportunity(
                    id="sep_ira",
                    title="SEP-IRA for Self-Employed",
                    description=f"As a self-employed individual, you can contribute up to 25% of net self-employment "
                               f"earnings (max ${max_sep:,.0f}) to a SEP-IRA, reducing your taxable income.",
                    category=OpportunityCategory.RETIREMENT,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=(
                        self._delta_sep(profile, float(max_sep))
                        or max_sep * self._marginal_rate(profile)
                    ),
                    action_required="Open SEP-IRA and contribute by tax filing deadline (with extensions)",
                    irs_reference="IRS Publication 560",
                    deadline=f"October 15, {self.TAX_YEAR + 1} (with extension)",
                    confidence=0.90
                ))

        # ── Augusta Rule (IRC §280A(g)) ───────────────────────────────────────
        if (profile.has_business or profile.self_employment_income > 0) and profile.owns_home:
            daily_rate = Decimal("500")
            savings_low = daily_rate * 7
            savings_high = daily_rate * 14
            opportunities.append(TaxOpportunity(
                id="augusta_rule",
                title="Augusta Rule — Tax-Free Home Rental to Your Business (IRC §280A(g))",
                description=(
                    "Rent your home to your business for up to 14 days/year. "
                    "The rental income is completely tax-free to you personally, "
                    "and the business deducts the full rental cost. "
                    f"Estimated savings: ${savings_low:,.0f}–${savings_high:,.0f}."
                ),
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=savings_low,
                savings_range=(savings_low, savings_high),
                action_required=(
                    "1. Get home appraised for daily rental value. "
                    "2. Have business formally rent home for meetings/events (14 days max). "
                    "3. Document with rental agreement and meeting minutes. "
                    "4. Business deducts rental cost; personal rental income is tax-free."
                ),
                irs_reference="IRC §280A(g)",
                confidence=0.85,
                prerequisites=["Must own home", "Must have qualifying business"],
                follow_up_questions=[
                    "Do you host business meetings, board meetings, or events at your home?",
                    "What is the fair market daily rental rate for your home?",
                ],
                metadata={"cpa_required": True},
            ))

        # ── Defined Benefit / Cash Balance Plan ──────────────────────────────
        if (profile.self_employment_income > 0 or profile.has_business) and \
                profile.total_income > Decimal("150000") and profile.age >= 40:
            marginal_rate = (
                Decimal("0.37") if profile.total_income > Decimal("500000")
                else Decimal("0.32") if profile.total_income > Decimal("200000")
                else Decimal("0.24")
            )
            max_contribution = min(profile.total_income * Decimal("0.30"), Decimal("300000"))
            db_savings = max_contribution * marginal_rate
            opportunities.append(TaxOpportunity(
                id="defined_benefit_plan",
                title="Defined Benefit / Cash Balance Plan — $100K–$300K Annual Deduction",
                description=(
                    "As a high-earning self-employed individual age 45+, you can establish "
                    "a defined benefit or cash balance pension plan allowing contributions "
                    f"of $100K–$300K/year — all fully tax-deductible. "
                    f"Estimated first-year savings: ${db_savings:,.0f}."
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=db_savings,
                savings_range=(Decimal("15000"), Decimal("45000")),
                action_required=(
                    "1. Engage actuary to design plan. "
                    "2. Establish trust document before year-end. "
                    "3. Make annual contributions (required once established). "
                    "4. Deduct full contribution on Schedule C/K-1."
                ),
                irs_reference="IRS Publication 560 / IRC §412",
                deadline=f"December 31, {self.TAX_YEAR} (plan must be established by year-end)",
                confidence=0.88,
                prerequisites=[
                    "Must be self-employed or have business income",
                    "Income > $150K",
                    "Age 45+ recommended for maximum benefit",
                ],
                follow_up_questions=[
                    "Do you have other employees? (Affects plan design and cost)",
                    "Are you willing to commit to annual contributions?",
                ],
                metadata={"cpa_required": True},
            ))

        # ── IRC §179 + Bonus Depreciation ─────────────────────────────────────
        if profile.has_business or profile.self_employment_income > 0:
            opportunities.append(TaxOpportunity(
                id="section_179_bonus_depreciation",
                title="IRC §179 + 100% Bonus Depreciation — Full Immediate Equipment Expensing",
                description=(
                    "Immediately expense up to $1.25M of equipment, vehicles, and software "
                    "in the year of purchase (IRC §179), plus 100% bonus depreciation on the "
                    "remainder (OBBBA 2025 restored full immediate expensing). "
                    "Converts a multi-year depreciation schedule into an immediate first-year deduction."
                ),
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("5000"), Decimal("30000")),
                action_required=(
                    "1. List all equipment, vehicles, software purchased for business. "
                    "2. Elect §179 on Form 4562. "
                    "3. Claim bonus depreciation on remaining basis. "
                    "4. Track separately for state taxes (many states don't conform)."
                ),
                irs_reference="IRC §179 / IRC §168(k) / Form 4562",
                deadline=f"December 31, {self.TAX_YEAR}",
                confidence=0.80,
                follow_up_questions=[
                    "Did you purchase any equipment, vehicles, or software for your business?",
                    "What was the total cost of business asset purchases this year?",
                ],
                metadata={"cpa_required": False},
            ))

        # ── Work Opportunity Tax Credit (WOTC) ────────────────────────────────
        # Only fire for entity types that employ W-2 workers; sole props rarely have qualifying hires
        _entity_has_employees = (
            profile.has_business
            and profile.business_type is not None
            and "sole" not in (profile.business_type or "")
        )
        if _entity_has_employees:
            opportunities.append(TaxOpportunity(
                id="wotc_credit",
                title="Work Opportunity Tax Credit (WOTC) — $2,400–$9,600 per Qualifying Hire",
                description=(
                    "Dollar-for-dollar tax credit of $2,400–$9,600 per qualifying new hire "
                    "(veterans, SNAP recipients, ex-felons, long-term unemployed, etc.). "
                    "No limit on the number of qualifying hires."
                ),
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("2400"), Decimal("9600")),
                action_required=(
                    "1. Screen new hires for WOTC eligibility on IRS Form 8850. "
                    "2. Submit to state workforce agency within 28 days of hire. "
                    "3. Claim credit on Form 5884."
                ),
                irs_reference="IRC §51 / Form 5884 / Form 8850",
                confidence=0.75,
                prerequisites=["Must have qualifying new hires", "Must submit Form 8850 within 28 days of hire"],
                follow_up_questions=[
                    "Did you hire new employees this year?",
                    "Do any new hires qualify (veterans, SNAP, ex-felons, long-term unemployed)?",
                ],
                metadata={"cpa_required": False},
            ))

        # ── R&D Tax Credits (IRC §41) ─────────────────────────────────────────
        business_type_lower = (profile.business_type or "").lower()
        _rd_sectors = ("software", "tech", "technology", "manufacturing", "biotech", "pharma", "research")
        if (profile.has_business or profile.self_employment_income > 0) and \
                any(s in business_type_lower for s in _rd_sectors):
            opportunities.append(TaxOpportunity(
                id="rd_tax_credit",
                title="R&D Tax Credit (IRC §41) — 20% Credit on Qualified Research Expenses",
                description=(
                    "20% federal credit on qualified research expenses (wages, supplies, contractor costs). "
                    "Small businesses under $5M revenue can offset up to $500K/year in payroll taxes "
                    "instead of income tax — available even without income tax liability."
                ),
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                savings_range=(Decimal("10000"), Decimal("50000")),
                action_required=(
                    "1. Document all qualified research activities. "
                    "2. Track employee time on R&D. "
                    "3. Claim on Form 6765. "
                    "4. Small businesses (<$5M revenue, <5 years): offset $500K/year payroll tax."
                ),
                irs_reference="IRC §41 / Form 6765",
                confidence=0.82,
                prerequisites=[
                    "Must have qualified research expenses",
                    "Research must meet 4-part test: technological in nature, uncertainty, experimentation, new/improved product",
                ],
                follow_up_questions=[
                    "Do you develop software, products, or processes?",
                    "What percentage of employee time is spent on R&D activities?",
                ],
                metadata={"cpa_required": True},
            ))

        return opportunities

    def _detect_real_estate_advanced_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect advanced real estate strategies (cost segregation)."""
        opportunities = []

        if profile.rental_income > Decimal("0"):
            # Estimate property value as 10x annual rental income (rough proxy)
            estimated_value = profile.rental_income * Decimal("10")
            if estimated_value >= Decimal("500000"):
                marginal_rate = (
                    Decimal("0.35") if profile.total_income > Decimal("200000")
                    else Decimal("0.24")
                )
                estimated_savings = max(
                    estimated_value * Decimal("0.25") * Decimal("0.35") * marginal_rate,
                    Decimal("15000"),
                )
                opportunities.append(TaxOpportunity(
                    id="cost_segregation",
                    title="Cost Segregation Study — Accelerate $15K–$50K+ in Depreciation",
                    description=(
                        "A cost segregation engineering study reclassifies 20–40% of your building "
                        "cost into 5/7/15-year property, accelerating depreciation by 10–15 years. "
                        f"Estimated first-year savings: ${estimated_savings:,.0f}–$50,000+. "
                        "Study cost ($5K–$15K) typically has a 10:1 ROI."
                    ),
                    category=OpportunityCategory.REAL_ESTATE,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=estimated_savings,
                    savings_range=(Decimal("15000"), Decimal("50000")),
                    action_required=(
                        "1. Hire cost segregation engineering firm. "
                        "2. Study cost: $5K–$15K but ROI is typically 10:1. "
                        "3. Reclassify components on Form 4562. "
                        "4. Can be done retroactively via accounting method change (Form 3115)."
                    ),
                    irs_reference="IRC §168 / Form 4562 / Form 3115",
                    confidence=0.85,
                    prerequisites=[
                        "Must own commercial or rental real estate worth $500K+",
                        "Works on new acquisitions and properties owned for years (retroactive via Form 3115)",
                    ],
                    follow_up_questions=[
                        "What is the purchase price or current value of your rental/commercial property?",
                        "When did you purchase the property?",
                    ],
                    metadata={"cpa_required": True},
                ))

        return opportunities

    def _detect_education_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect education-related opportunities."""
        opportunities = []

        if profile.has_college_students or profile.education_expenses > 0:
            # American Opportunity Credit
            opportunities.append(TaxOpportunity(
                id="aotc",
                title="American Opportunity Tax Credit",
                description="For the first 4 years of college, you may claim up to $2,500 per eligible student. "
                           "40% ($1,000) is refundable even if you owe no tax.",
                category=OpportunityCategory.EDUCATION,
                priority=OpportunityPriority.HIGH,
                estimated_savings=Decimal("2500"),
                action_required="File Form 8863 with your tax return",
                irs_reference="IRS Publication 970",
                confidence=0.85,
                prerequisites=["Student must be in first 4 years of higher education", "Income limits apply"],
                follow_up_questions=[
                    "What year of college is your student in?",
                    "Do you have Form 1098-T from the school?"
                ]
            ))

            # Lifetime Learning Credit
            opportunities.append(TaxOpportunity(
                id="llc",
                title="Lifetime Learning Credit",
                description="If not eligible for AOTC, you may claim up to $2,000 per tax return for "
                           "post-secondary education expenses.",
                category=OpportunityCategory.EDUCATION,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=Decimal("2000"),
                action_required="File Form 8863 (choose either AOTC or LLC, not both for same student)",
                irs_reference="IRS Publication 970",
                confidence=0.75
            ))

        return opportunities

    def _detect_filing_status_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect filing status optimization opportunities."""
        opportunities = []

        # Head of Household analysis
        if profile.filing_status == "single" and profile.num_dependents > 0:
            standard_single = self.STANDARD_DEDUCTION["single"]
            standard_hoh = self.STANDARD_DEDUCTION["head_of_household"]
            benefit = standard_hoh - standard_single

            opportunities.append(TaxOpportunity(
                id="consider_hoh",
                title="Consider Head of Household Status",
                description=f"If you're unmarried and pay more than half the cost of keeping up a home for a qualifying person, "
                           f"you may file as Head of Household. This gives you a ${benefit:,.0f} higher standard deduction "
                           f"and more favorable tax brackets.",
                category=OpportunityCategory.FILING_STATUS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=benefit * self._marginal_rate(profile),
                action_required="Review Head of Household requirements",
                irs_reference="IRS Publication 501",
                confidence=0.70,
                follow_up_questions=[
                    "Did you pay more than half the cost of keeping up your home?",
                    "Does a qualifying person live with you?"
                ]
            ))

        # MFJ vs MFS analysis — show for both MFJ (confirm joint is optimal) and MFS (confirm separate is optimal)
        if profile.filing_status in ("married_filing_jointly", "married_filing_separately") and (profile.spouse_age or profile.filing_status == "married_filing_separately"):
            opportunities.append(TaxOpportunity(
                id="mfj_vs_mfs",
                title="Compare Joint vs. Separate Filing",
                description="In most cases, Married Filing Jointly is better. However, filing separately may help "
                           "if you have income-based student loan payments, medical expenses >7.5% of AGI, "
                           "or want to separate liability.",
                category=OpportunityCategory.FILING_STATUS,
                priority=OpportunityPriority.LOW,
                action_required="Calculate taxes both ways to compare",
                irs_reference="IRS Publication 501",
                confidence=0.60,
                follow_up_questions=[
                    "Are you on an income-driven student loan repayment plan?",
                    "Do either of you have significant medical expenses?"
                ]
            ))

        return opportunities

    def _detect_timing_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Detect timing-related opportunities."""
        opportunities = []
        current_month = datetime.now().month

        # Tax-loss harvesting — actionable year-round (wash-sale window closes Dec 31)
        if profile.capital_gains > Decimal("3000"):
            _tlh_urgency = "Review portfolio now — year-end deadline applies to offset this year's gains." if current_month >= 10 else "Review portfolio periodically to harvest losses and offset capital gains."
            _tlh_savings = int(float(profile.capital_gains) * 0.20)
            opportunities.append(TaxOpportunity(
                id="tax_loss_harvest",
                title="Tax-Loss Harvesting",
                description="If you have investments with losses, consider selling them to offset "
                           f"your ${profile.capital_gains:,.0f} in capital gains. You can deduct up to $3,000 "
                           "in excess losses against ordinary income.",
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=_tlh_savings,
                action_required=_tlh_urgency,
                deadline=f"December 31, {self.TAX_YEAR}",
                irs_reference="IRS Publication 550",
                confidence=0.75,
                follow_up_questions=["Do you have any investments currently at a loss?"]
            ))

        # Charitable giving reminder — year-round (December deadline is last chance)
        if profile.charitable_contributions == 0 and profile.agi_estimate > Decimal("75000"):
            opportunities.append(TaxOpportunity(
                id="charitable_yearend",
                title="Year-End Charitable Giving",
                description="Charitable contributions before December 31 can reduce this year's taxes. "
                           "Consider donating appreciated stock to avoid capital gains tax.",
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.MEDIUM,
                action_required="Make donations before year-end and keep receipts",
                deadline=f"December 31, {self.TAX_YEAR}",
                irs_reference="IRS Publication 526",
                confidence=0.70
            ))

        return opportunities

    # =========================================================================
    # ADVANCED RETIREMENT OPPORTUNITIES
    # =========================================================================

    def _detect_advanced_retirement_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Roth conversion, backdoor Roth, spousal IRA, Solo 401k, RMD, QCD."""
        opportunities = []

        # ── Roth Conversion Strategy ────────────────────────────────────────
        roth_start = self.ROTH_PHASEOUT_START.get(profile.filing_status, Decimal("150000"))
        in_low_bracket = profile.agi_estimate < roth_start * Decimal("0.80")
        has_pre_tax = (
            profile.ira_balance > Decimal("10000") or
            profile.traditional_401k > Decimal("5000") or
            profile.traditional_ira > Decimal("5000")
        )
        if has_pre_tax and (in_low_bracket or profile.retired_this_year):
            opportunities.append(TaxOpportunity(
                id="roth_conversion",
                title="Roth Conversion Opportunity",
                description=(
                    "You may be in a lower tax bracket this year — ideal for converting pre-tax "
                    "IRA/401(k) funds to Roth. Converted amounts grow tax-free forever and avoid "
                    "future RMDs. Strategy: convert up to the top of your current bracket."
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                savings_range=(Decimal("2000"), Decimal("20000")),
                action_required="Instruct IRA custodian to do a partial Roth conversion; pay tax now at lower rate",
                irs_reference="IRS Publication 590-A / Form 8606",
                confidence=0.80,
                follow_up_questions=[
                    "Do you have a traditional IRA or old 401(k)?",
                    "What do you expect your tax bracket to be in retirement?",
                ],
                metadata={"cpa_required": True},
            ))

        # ── Backdoor Roth IRA ───────────────────────────────────────────────
        roth_end = self.ROTH_PHASEOUT_END.get(profile.filing_status, Decimal("165000"))
        if profile.agi_estimate > roth_end:
            max_ira = self.CONTRIB_LIMITS["ira"] + (
                self.CONTRIB_LIMITS["ira_catchup"] if profile.age >= 50 else Decimal("0")
            )
            current_ira = profile.traditional_ira + profile.roth_ira
            if current_ira < max_ira:
                opportunities.append(TaxOpportunity(
                    id="backdoor_roth",
                    title="Backdoor Roth IRA",
                    description=(
                        f"Your income (${profile.agi_estimate:,.0f}) exceeds the Roth IRA limit. "
                        f"Use the backdoor strategy: contribute ${max_ira:,.0f} to a non-deductible "
                        "traditional IRA, then convert to Roth. Tax-free growth with no income limit."
                    ),
                    category=OpportunityCategory.RETIREMENT,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=max_ira * self._marginal_rate(profile),
                    action_required=(
                        "1. Contribute to non-deductible traditional IRA (Form 8606). "
                        "2. Convert to Roth IRA immediately. "
                        "3. Beware pro-rata rule if you have other traditional IRA balances."
                    ),
                    irs_reference="IRS Form 8606",
                    deadline=f"April 15, {self.TAX_YEAR + 1}",
                    confidence=0.85,
                    follow_up_questions=[
                        "Do you have any existing traditional IRA balances? (Pro-rata rule applies)",
                    ],
                ))

        # ── Spousal IRA ─────────────────────────────────────────────────────
        if (profile.filing_status == "married_filing_jointly" and
                profile.spouse_age and
                profile.w2_wages + profile.self_employment_income > 0):
            # If spouse has no earned income but household does, spousal IRA is available
            max_ira = self.CONTRIB_LIMITS["ira"] + (
                self.CONTRIB_LIMITS["ira_catchup"] if (profile.spouse_age or 0) >= 50 else Decimal("0")
            )
            opportunities.append(TaxOpportunity(
                id="spousal_ira",
                title="Spousal IRA Contribution",
                description=(
                    f"Even if your spouse has no earned income, you can contribute up to "
                    f"${max_ira:,.0f} to a spousal IRA based on your earned income. "
                    "This doubles your household IRA tax shelter."
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=max_ira * self._marginal_rate(profile),
                action_required="Open an IRA in spouse's name and contribute based on your earned income",
                irs_reference="IRS Publication 590-A",
                deadline=f"April 15, {self.TAX_YEAR + 1}",
                confidence=0.85,
            ))

        # ── Solo 401(k) vs SEP-IRA comparison ──────────────────────────────
        if profile.self_employment_income > Decimal("30000") and profile.traditional_401k == 0:
            net_se = profile.self_employment_income * Decimal("0.9235")
            sep_max = min(net_se * Decimal("0.25"), Decimal("70000"))
            solo_employee = min(self.CONTRIB_LIMITS["401k"], net_se)
            if profile.age >= 50:
                solo_employee += self.CONTRIB_LIMITS["401k_catchup"]
            solo_employer = min(net_se * Decimal("0.25"), Decimal("70000") - solo_employee)
            solo_max = min(solo_employee + solo_employer, Decimal("70000"))
            if solo_max > sep_max * Decimal("1.10"):  # Solo 401k meaningfully better
                opportunities.append(TaxOpportunity(
                    id="solo_401k_vs_sep",
                    title="Solo 401(k) Beats SEP-IRA for Your Income Level",
                    description=(
                        f"A Solo 401(k) allows up to ${solo_max:,.0f} in contributions vs. "
                        f"${sep_max:,.0f} for a SEP-IRA at your income. The difference is "
                        f"${solo_max - sep_max:,.0f} in additional tax-deferred savings. "
                        "Plus: Roth option and loan provision available with Solo 401(k)."
                    ),
                    category=OpportunityCategory.RETIREMENT,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=(solo_max - sep_max) * self._marginal_rate(profile),
                    action_required=(
                        "Open Solo 401(k) by December 31 (plan establishment deadline). "
                        "Employee contributions due December 31; employer by tax filing deadline."
                    ),
                    irs_reference="IRS Publication 560",
                    deadline=f"December 31, {self.TAX_YEAR} (plan establishment)",
                    confidence=0.88,
                ))

        # ── Required Minimum Distribution (RMD) ────────────────────────────
        if profile.age >= 73 and (profile.ira_balance > 0 or profile.traditional_401k > 0):
            est_rmd = (profile.ira_balance + profile.traditional_401k * Decimal("10")) / Decimal("26.5")
            opportunities.append(TaxOpportunity(
                id="rmd_reminder",
                title="Required Minimum Distribution (RMD) Due",
                description=(
                    f"At age {profile.age}, you must take Required Minimum Distributions from "
                    f"traditional IRAs and 401(k)s. Estimated RMD: ${est_rmd:,.0f}. "
                    "Failure to take RMD results in a 25% excise tax on the missed amount."
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                action_required="Contact IRA custodian to calculate and take RMD by December 31",
                irs_reference="IRS Publication 590-B",
                deadline=f"December 31, {self.TAX_YEAR}",
                confidence=0.90,
            ))

        # ── Qualified Charitable Distribution (QCD) ─────────────────────────
        # QCD requires age 70½+. Using integer age >= 71 to avoid false positives
        # for taxpayers who turned 70 but haven't reached the half-year mark.
        if profile.age >= 71 and (profile.ira_balance > 0 or profile.traditional_ira > 0):
            opportunities.append(TaxOpportunity(
                id="qcd_strategy",
                title="Qualified Charitable Distribution (QCD) — Tax-Free from IRA",
                description=(
                    f"At age 70½+, you can transfer up to ${self.QCD_MAX:,.0f}/year directly "
                    "from your IRA to charity. The distribution is excluded from gross income "
                    "entirely — even better than a deduction — and satisfies your RMD obligation."
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=Decimal("5000") * self._marginal_rate(profile),
                action_required=(
                    "Direct IRA custodian to transfer funds directly to qualifying charity (501(c)(3)). "
                    "Do NOT take the distribution yourself first."
                ),
                irs_reference="IRS Publication 590-B / QCD rules",
                deadline=f"December 31, {self.TAX_YEAR}",
                confidence=0.85,
                prerequisites=["Age 70½ or older", "Must be direct transfer from IRA to charity"],
            ))

        return opportunities

    # =========================================================================
    # ADVANCED DEDUCTIONS
    # =========================================================================

    def _detect_advanced_deductions(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """SE health insurance, donor-advised fund, charitable stock, alimony."""
        opportunities = []

        # ── SE Health Insurance Deduction ───────────────────────────────────
        if profile.self_employment_income > Decimal("5000") and profile.se_health_insurance == 0:
            opportunities.append(TaxOpportunity(
                id="se_health_insurance",
                title="Self-Employed Health Insurance Deduction",
                description=(
                    "Self-employed individuals can deduct 100% of health, dental, and vision "
                    "insurance premiums for themselves, spouse, and dependents as an above-the-line "
                    "deduction — available even with the standard deduction. "
                    "Average deduction: $8,000–$24,000/year."
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.HIGH,
                savings_range=(Decimal("1760"), Decimal("5280")),
                action_required="Report health insurance premiums on Schedule 1, Line 17",
                irs_reference="IRC §162(l) / IRS Publication 535",
                confidence=0.85,
                follow_up_questions=[
                    "Do you pay for your own health insurance premiums?",
                    "How much did you pay in health/dental/vision premiums this year?",
                ],
            ))

        # ── Donor-Advised Fund (DAF) strategy ───────────────────────────────
        if profile.agi_estimate > Decimal("100000") and profile.charitable_contributions > 0:
            opportunities.append(TaxOpportunity(
                id="donor_advised_fund",
                title="Donor-Advised Fund — Bunch Charitable Giving for a Bigger Deduction",
                description=(
                    "A Donor-Advised Fund (DAF) lets you make a large, immediately deductible "
                    "contribution now, then distribute to charities over multiple years. "
                    "Ideal for bunching multiple years of giving into one tax year to clear "
                    "the standard deduction threshold."
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("2000"), Decimal("15000")),
                action_required=(
                    "Open DAF account (Fidelity Charitable, Schwab Charitable, or Vanguard Charitable). "
                    "Contribute cash or appreciated stock. Deduct in the year contributed."
                ),
                irs_reference="IRS Publication 526",
                confidence=0.75,
            ))

        # ── Appreciated stock gifting ────────────────────────────────────────
        if profile.appreciated_stock_held and profile.capital_gains > Decimal("5000"):
            opportunities.append(TaxOpportunity(
                id="appreciated_stock_gift",
                title="Donate Appreciated Stock — Avoid Capital Gains Tax on Charitable Giving",
                description=(
                    "Instead of selling appreciated stock and donating cash, donate the stock "
                    "directly to charity. You deduct the full fair market value AND avoid "
                    "capital gains tax on the appreciation — a double tax benefit."
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.HIGH,
                savings_range=(Decimal("1000"), Decimal("20000")),
                action_required=(
                    "Instruct brokerage to transfer shares directly to charity's brokerage account. "
                    "Get a written acknowledgment for deductions over $250."
                ),
                irs_reference="IRS Publication 526 / Form 8283",
                confidence=0.85,
            ))

        return opportunities

    # =========================================================================
    # ADVANCED CREDITS
    # =========================================================================

    def _detect_advanced_credits(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """ACA Premium Tax Credit, Additional CTC, dependent care FSA analysis."""
        opportunities = []

        # ── Additional Child Tax Credit (ACTC) — refundable portion ─────────
        if profile.has_children_under_17 and profile.num_dependents > 0:
            # ACTC = refundable up to $1,700 per child for 2025
            actc = min(
                self.ACTC_MAX_PER_CHILD * profile.num_dependents,
                (profile.w2_wages + profile.self_employment_income) * Decimal("0.15"),
            )
            if actc > 0:
                opportunities.append(TaxOpportunity(
                    id="additional_ctc",
                    title="Additional Child Tax Credit (Refundable)",
                    description=(
                        f"Up to ${self.ACTC_MAX_PER_CHILD:,.0f} per child is refundable even if "
                        f"you owe no tax. Estimated refundable ACTC: ${actc:,.0f}. "
                        "This is in addition to the $2,000 non-refundable CTC."
                    ),
                    category=OpportunityCategory.CREDIT,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=actc,
                    action_required="Automatically calculated on Schedule 8812 (Form 1040)",
                    irs_reference="Schedule 8812 / IRS Publication 972",
                    confidence=0.90,
                ))

        # ── ACA Premium Tax Credit (PTC) ─────────────────────────────────────
        # Self-employed without employer coverage, income 100–400% FPL
        federal_poverty_level = Decimal("15060")  # 2025 FPL for single
        if profile.filing_status == "married_filing_jointly":
            federal_poverty_level = Decimal("20440")
        fpl_400 = federal_poverty_level * 4
        if (
            profile.self_employment_income > 0 or profile.w2_wages == 0
        ) and profile.agi_estimate < fpl_400 and not profile.has_hdhp:
            opportunities.append(TaxOpportunity(
                id="aca_premium_tax_credit",
                title="ACA Premium Tax Credit (Health Insurance Subsidy)",
                description=(
                    "Self-employed individuals and those without employer coverage may qualify "
                    "for Premium Tax Credit subsidies on ACA marketplace plans. "
                    "Income under 400% FPL qualifies; subsidies can be $3,000–$15,000+/year."
                ),
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                savings_range=(Decimal("3000"), Decimal("15000")),
                action_required=(
                    "Shop healthcare.gov during open enrollment. "
                    "Apply for APTC (advance payments). "
                    "Reconcile on Form 8962 at tax time."
                ),
                irs_reference="IRS Form 8962 / IRC §36B",
                confidence=0.70,
                follow_up_questions=[
                    "Do you buy your own health insurance?",
                    "Did you receive advance premium credits?",
                ],
            ))

        # ── Dependent Care FSA vs. Credit comparison ─────────────────────────
        if profile.has_children_under_13 and profile.dependent_care_expenses > 0:
            if not profile.has_dependent_care_fsa:
                fsa_savings = min(
                    profile.dependent_care_expenses, Decimal("5000")
                ) * self._marginal_rate(profile)
                opportunities.append(TaxOpportunity(
                    id="dependent_care_fsa",
                    title="Dependent Care FSA — Save $1,100+ on Childcare",
                    description=(
                        "A Dependent Care FSA (DC-FSA) lets you pay up to $5,000/year ($2,500 MFS) "
                        "in childcare with pre-tax dollars — saving FICA and income tax. "
                        f"Estimated savings vs. after-tax: ${fsa_savings:,.0f}. "
                        "Often better than the Child Care Credit for higher-income families."
                    ),
                    category=OpportunityCategory.CREDIT,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=fsa_savings,
                    action_required=(
                        "Enroll in DC-FSA through employer during open enrollment. "
                        "Election change allowed for qualifying life events."
                    ),
                    irs_reference="IRC §129 / IRS Publication 503",
                    confidence=0.80,
                    follow_up_questions=[
                        "Does your employer offer a Dependent Care FSA?",
                        "How much did you pay in childcare/daycare this year?",
                    ],
                ))

        # ── Net Investment Income Tax (NIIT) warning + strategy ─────────────
        niit_threshold = self.NIIT_THRESHOLD.get(profile.filing_status, Decimal("200000"))
        investment_income = (
            profile.interest_income + profile.dividend_income +
            profile.capital_gains + profile.rental_income
        )
        if profile.agi_estimate > niit_threshold and investment_income > 0:
            niit_liability = investment_income * self.NIIT_RATE
            opportunities.append(TaxOpportunity(
                id="niit_strategy",
                title="Net Investment Income Tax (NIIT) — 3.8% Surtax Alert",
                description=(
                    f"Your income exceeds the NIIT threshold (${niit_threshold:,.0f}). "
                    f"You face a 3.8% surtax on ${investment_income:,.0f} of investment income "
                    f"— estimated NIIT: ${niit_liability:,.0f}. "
                    "Strategies: municipal bonds (NIIT-free), tax-deferred accounts, real estate losses."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=niit_liability * Decimal("0.30"),
                action_required=(
                    "Review investment income sources. "
                    "Consider tax-exempt municipal bonds for fixed income. "
                    "Maximize tax-deferred account contributions."
                ),
                irs_reference="IRS Form 8960 / IRC §1411",
                confidence=0.88,
            ))

        # ── Additional Medicare Tax (0.9%) ───────────────────────────────────
        add_med_threshold = self.ADD_MEDICARE_THRESHOLD.get(profile.filing_status, Decimal("200000"))
        earned_income = profile.w2_wages + profile.self_employment_income
        if earned_income > add_med_threshold:
            add_tax = (earned_income - add_med_threshold) * Decimal("0.009")
            opportunities.append(TaxOpportunity(
                id="additional_medicare_tax",
                title="Additional 0.9% Medicare Tax — Plan Pre-tax Contributions",
                description=(
                    f"You owe an additional 0.9% Medicare tax on wages/SE income above "
                    f"${add_med_threshold:,.0f}. Estimated: ${add_tax:,.0f}. "
                    "Maximize pre-tax retirement contributions to reduce the base."
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=Decimal("500"),
                action_required="Reported on Form 8959; ensure withholding is adequate",
                irs_reference="IRS Form 8959 / IRC §3101(b)(2)",
                confidence=0.90,
            ))

        return opportunities

    # =========================================================================
    # SELF-EMPLOYMENT ADVANCED OPPORTUNITIES
    # =========================================================================

    def _detect_se_advanced_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """S-Corp recommendation, reasonable compensation, estimated tax for SE."""
        opportunities = []

        if profile.self_employment_income < Decimal("1000"):
            return opportunities

        # ── S-Corp Election recommendation ──────────────────────────────────
        # At ~$40K+ SE net income an S-Corp starts saving SE tax
        if (profile.self_employment_income > self.SCORP_BREAKEVEN_SE_INCOME and
                (profile.business_type or "").lower() not in ("s_corp", "scorp")):
            se_tax_savings = profile.self_employment_income * Decimal("0.9235") * Decimal("0.153")
            # Rough S-Corp savings: SE tax on distribution portion (~40% of income)
            savings_est = se_tax_savings * Decimal("0.40")
            opportunities.append(TaxOpportunity(
                id="scorp_election",
                title="S-Corp Election — Save SE Tax on Business Income",
                description=(
                    f"With ${profile.self_employment_income:,.0f} in self-employment income, "
                    "converting to an S-Corp and paying yourself a reasonable salary can eliminate "
                    "self-employment tax on the remaining profit distributions. "
                    f"Estimated annual savings: ${savings_est:,.0f}–${savings_est * Decimal('1.5'):,.0f}."
                ),
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=savings_est,
                action_required=(
                    "1. Form LLC or corporation in your state. "
                    "2. File IRS Form 2553 for S-Corp election (by March 15 for current year). "
                    "3. Set reasonable W-2 salary. "
                    "4. Take remaining profit as S-Corp distributions (no SE tax)."
                ),
                irs_reference="IRC §1362 / IRS Form 2553",
                confidence=0.80,
                prerequisites=["Net SE income > $40,000", "Willing to maintain payroll"],
                follow_up_questions=[
                    "Are you currently operating as a sole proprietor or single-member LLC?",
                    "What is your expected net profit this year?",
                ],
                metadata={"cpa_required": True},
            ))

        # ── Crypto gains/losses ──────────────────────────────────────────────
        if profile.crypto_gains > 0 or profile.crypto_losses > 0:
            net_crypto = profile.crypto_gains - profile.crypto_losses
            opportunities.append(TaxOpportunity(
                id="crypto_tax_reporting",
                title="Cryptocurrency Tax Reporting & Loss Harvesting",
                description=(
                    f"You have crypto gains of ${profile.crypto_gains:,.0f} and losses of "
                    f"${profile.crypto_losses:,.0f} (net: ${net_crypto:,.0f}). "
                    "Unlike stocks, crypto is NOT subject to the wash-sale rule — you can "
                    "sell at a loss and immediately repurchase to realize the loss."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH if net_crypto > Decimal("5000") else OpportunityPriority.MEDIUM,
                action_required=(
                    "1. Use crypto tax software (Koinly, CoinTracker) to generate Form 8949. "
                    "2. Harvest losses by selling and immediately repurchasing. "
                    "3. Report all transactions — IRS asks about crypto on Form 1040."
                ),
                irs_reference="IRS Notice 2014-21 / Form 8949 / Schedule D",
                confidence=0.85,
            ))

        return opportunities

    # =========================================================================
    # INVESTMENT TAX OPPORTUNITIES
    # =========================================================================

    def _detect_investment_tax_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """NIIT, 1031 exchange, passive activity losses, wash sale warning."""
        opportunities = []

        # ── 1031 Like-Kind Exchange ──────────────────────────────────────────
        if profile.rental_income > Decimal("20000"):
            opportunities.append(TaxOpportunity(
                id="like_kind_exchange_1031",
                title="IRC §1031 Like-Kind Exchange — Defer Capital Gains on Property Sale",
                description=(
                    "If you plan to sell rental property, a 1031 exchange defers ALL capital gains "
                    "and depreciation recapture tax indefinitely. Must identify replacement property "
                    "within 45 days and close within 180 days. "
                    "Potential tax deferral: $50,000–$500,000+."
                ),
                category=OpportunityCategory.REAL_ESTATE,
                priority=OpportunityPriority.HIGH,
                savings_range=(Decimal("15000"), Decimal("150000")),
                action_required=(
                    "1. Engage qualified intermediary BEFORE selling (mandatory). "
                    "2. Never take constructive receipt of sale proceeds. "
                    "3. Identify replacement within 45 days; close within 180 days."
                ),
                irs_reference="IRC §1031 / IRS Publication 544",
                confidence=0.75,
                prerequisites=["Must be investment/business property (not primary home)", "Must use qualified intermediary"],
                follow_up_questions=[
                    "Are you planning to sell any rental or investment real estate?",
                    "Do you want to reinvest in different property?",
                ],
                metadata={"cpa_required": True},
            ))

        # ── Passive Activity Loss (PAL) ──────────────────────────────────────
        if profile.rental_income > 0 and profile.passive_losses_carryforward > Decimal("5000"):
            opportunities.append(TaxOpportunity(
                id="passive_loss_utilization",
                title="Passive Activity Loss (PAL) — Unlock Suspended Losses",
                description=(
                    f"You have ${profile.passive_losses_carryforward:,.0f} in suspended passive "
                    "activity losses. These can offset passive income, or be fully released when "
                    "you sell the passive activity (rental property). "
                    "Real estate professionals (750+ hours/year) can deduct against ordinary income."
                ),
                category=OpportunityCategory.REAL_ESTATE,
                priority=OpportunityPriority.HIGH,
                estimated_savings=profile.passive_losses_carryforward * self._marginal_rate(profile),
                action_required=(
                    "Track on Form 8582. Consider disposing of passive activity to release all losses at once."
                ),
                irs_reference="IRC §469 / Form 8582",
                confidence=0.80,
            ))

        # ── K-1 passive/active income ─────────────────────────────────────
        if profile.k1_income > 0:
            opportunities.append(TaxOpportunity(
                id="k1_qbi_deduction",
                title="K-1 Qualified Business Income (QBI) Deduction",
                description=(
                    f"Your K-1 income of ${profile.k1_income:,.0f} from partnerships/S-Corps "
                    "may qualify for the 20% QBI deduction (Section 199A). "
                    "This reduces taxable income on pass-through earnings significantly."
                ),
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=profile.k1_income * Decimal("0.20") * self._marginal_rate(profile),
                action_required="Claim on Form 8995 or 8995-A using K-1 Box 20 code Z amounts",
                irs_reference="IRS Form 8995 / IRC §199A",
                confidence=0.85,
            ))

        return opportunities

    # =========================================================================
    # SENIOR TAX PLANNING
    # =========================================================================

    def _detect_senior_tax_planning(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Social Security taxation, Medicare IRMAA, RMD, senior-specific strategies."""
        opportunities = []

        if profile.age < 60:
            return opportunities

        # ── Social Security taxation optimization ────────────────────────────
        if profile.social_security_income > 0:
            combined_income = profile.agi_estimate - profile.social_security_income + (
                profile.social_security_income * Decimal("0.5")
            )
            threshold_85 = self.SS_COMBINED_85PCT.get(profile.filing_status, Decimal("34000"))
            if combined_income > threshold_85:
                taxable_ss = profile.social_security_income * Decimal("0.85")
                opportunities.append(TaxOpportunity(
                    id="social_security_taxation",
                    title="Reduce Social Security Taxation — Up to 85% Is Taxable",
                    description=(
                        f"Up to 85% of your Social Security (${taxable_ss:,.0f}) is taxable "
                        "based on your combined income. Strategies to reduce: Roth conversions in "
                        "pre-SS years, timing other income, municipal bond income (not counted)."
                    ),
                    category=OpportunityCategory.RETIREMENT,
                    priority=OpportunityPriority.HIGH,
                    action_required=(
                        "Consider converting IRA to Roth before claiming SS to reduce future combined income."
                    ),
                    irs_reference="IRS Publication 915",
                    confidence=0.80,
                ))

        # ── Medicare IRMAA surcharge warning ────────────────────────────────
        irmaa_thresh = (
            self.IRMAA_THRESHOLD_MFJ
            if profile.filing_status == "married_filing_jointly"
            else self.IRMAA_THRESHOLD_SINGLE
        )
        if profile.age >= 65 and profile.agi_estimate > irmaa_thresh * Decimal("0.90"):
            opportunities.append(TaxOpportunity(
                id="medicare_irmaa",
                title="Medicare IRMAA Surcharge Risk",
                description=(
                    f"Your MAGI is approaching the Medicare IRMAA threshold (${irmaa_thresh:,.0f}). "
                    "Exceeding it triggers $69–$419/month in additional Medicare Part B+D premiums. "
                    "IRMAA uses 2-year-old tax returns, so 2025 income affects 2027 premiums."
                ),
                category=OpportunityCategory.HEALTHCARE,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Stay below threshold via tax-deferred contributions, capital gain timing, "
                    "or QCD distributions. File Form SSA-44 if income drop was a life event."
                ),
                irs_reference="SSA-44 (for IRMAA appeals)",
                confidence=0.80,
                follow_up_questions=["Are you currently enrolled in Medicare?"],
            ))

        # ── Standard deduction additional for seniors ────────────────────────
        if profile.age >= 65:
            add_std = Decimal("1600") if profile.filing_status == "single" else Decimal("1300")
            opportunities.append(TaxOpportunity(
                id="senior_standard_deduction",
                title="Additional Standard Deduction for Age 65+",
                description=(
                    f"Taxpayers 65 or older receive an additional ${add_std:,.0f} standard "
                    "deduction per person. If both spouses are 65+, add $2,600 total. "
                    "This is automatic — ensure your tax software applies it."
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=add_std * self._marginal_rate(profile),
                action_required="Verify tax software correctly marks your age on Form 1040",
                irs_reference="IRS Publication 554",
                confidence=0.95,
            ))

        return opportunities

    # =========================================================================
    # ESTIMATED TAX PLANNING
    # =========================================================================

    def _detect_estimated_tax(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Quarterly estimated tax reminders for self-employed and investors."""
        opportunities = []

        se_and_business = profile.self_employment_income + profile.business_income + profile.k1_income
        investment_income = profile.interest_income + profile.dividend_income + profile.capital_gains

        if se_and_business + investment_income < Decimal("10000"):
            return opportunities

        # Rough tax liability estimate
        rough_tax = profile.agi_estimate * Decimal("0.20")
        withheld = profile.federal_withheld + profile.es_payments_ytd
        expected_shortfall = rough_tax - withheld

        if expected_shortfall > Decimal("1000"):
            opportunities.append(TaxOpportunity(
                id="estimated_tax_payments",
                title="Quarterly Estimated Tax Payments Due",
                description=(
                    "Self-employed individuals and investors with significant unwithheld income "
                    "must make quarterly estimated tax payments to avoid underpayment penalties. "
                    f"Estimated shortfall: ${expected_shortfall:,.0f}. "
                    "Safe harbor: pay 100% (or 110% if AGI > $150K) of prior year's tax."
                ),
                category=OpportunityCategory.TIMING,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Pay via IRS Direct Pay (irs.gov/payments). "
                    "Due dates: April 15, June 15, September 15, January 15."
                ),
                irs_reference="IRS Form 1040-ES",
                confidence=0.80,
                follow_up_questions=[
                    "Are you making quarterly estimated tax payments?",
                    "What did you pay in federal tax last year?",
                ],
            ))

        return opportunities

    # =========================================================================
    # ENERGY & CLEAN VEHICLE CREDITS
    # =========================================================================

    def _detect_energy_credits(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """EV tax credit, residential solar, home energy improvement credits."""
        opportunities = []

        # ── Clean Vehicle Credit (EV) ────────────────────────────────────────
        ev_income_limit = (
            self.EV_INCOME_LIMIT_MFJ
            if profile.filing_status == "married_filing_jointly"
            else self.EV_INCOME_LIMIT_SINGLE
        )
        if profile.has_ev_purchase and profile.agi_estimate < ev_income_limit:
            credit = min(self.EV_CREDIT_MAX, profile.ev_purchase_price * Decimal("0.30"))
            opportunities.append(TaxOpportunity(
                id="ev_tax_credit",
                title=f"Clean Vehicle Tax Credit — Up to ${self.EV_CREDIT_MAX:,.0f}",
                description=(
                    f"Your EV purchase may qualify for up to ${credit:,.0f} federal tax credit. "
                    "Vehicle must be on IRS's qualified vehicle list. Income limit applies. "
                    "Credit is non-refundable but can reduce tax to zero."
                ),
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=credit,
                action_required="Claim on Form 8936. Verify vehicle qualifies at fueleconomy.gov",
                irs_reference="IRS Form 8936 / IRC §30D",
                confidence=0.80,
                follow_up_questions=["What is the make/model of your electric vehicle?"],
            ))

        # ── Residential Solar Credit ─────────────────────────────────────────
        if profile.has_solar and profile.solar_cost > Decimal("5000"):
            credit = profile.solar_cost * self.SOLAR_CREDIT_RATE
            opportunities.append(TaxOpportunity(
                id="solar_tax_credit",
                title=f"Residential Clean Energy Credit — 30% of Solar Cost",
                description=(
                    f"Your solar installation (${profile.solar_cost:,.0f}) qualifies for a "
                    f"30% federal tax credit: ${credit:,.0f}. "
                    "Credit is non-refundable but unused amounts carry forward to future years."
                ),
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=credit,
                action_required="Claim on Form 5695. Keep installer invoice as documentation",
                irs_reference="IRS Form 5695 / IRC §25D",
                confidence=0.90,
            ))

        # ── Home Energy Improvement Credit ───────────────────────────────────
        if profile.has_home_energy_improvements:
            opportunities.append(TaxOpportunity(
                id="home_energy_improvement_credit",
                title=f"Energy Efficient Home Improvement Credit — Up to ${self.HOME_ENERGY_CREDIT_MAX:,.0f}",
                description=(
                    "Qualifying improvements (heat pumps, insulation, windows, doors, water heaters) "
                    f"earn a 30% credit, capped at ${self.HOME_ENERGY_CREDIT_MAX:,.0f}/year. "
                    "Heat pumps and heat pump water heaters: $2,000 sub-cap. "
                    "Credit resets each year — plan improvements over multiple years."
                ),
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=self.HOME_ENERGY_CREDIT_MAX,
                action_required="Claim on Form 5695. Keep all receipts and manufacturer certifications",
                irs_reference="IRS Form 5695 / IRC §25C",
                confidence=0.85,
                follow_up_questions=[
                    "What energy improvements did you make? (heat pump, insulation, windows?)",
                    "What were the total costs?",
                ],
            ))

        # ── 529 Plan contribution reminder ───────────────────────────────────
        if not profile.has_529_plan and profile.has_college_students:
            opportunities.append(TaxOpportunity(
                id="529_plan",
                title="529 College Savings Plan — State Tax Deduction + Tax-Free Growth",
                description=(
                    "529 plans offer state income tax deductions (in most states), "
                    "tax-free growth, and tax-free withdrawals for qualified education expenses. "
                    f"Superfunding: contribute up to ${self.SUPERFUNDING_MAX:,.0f} ($90K) at once "
                    "using 5-year gift tax election."
                ),
                category=OpportunityCategory.EDUCATION,
                priority=OpportunityPriority.MEDIUM,
                savings_range=(Decimal("500"), Decimal("5000")),
                action_required=(
                    "Open 529 account in your state (often at direct plan website). "
                    "Check your state's deduction limit — many states offer $10K–$20K deduction."
                ),
                irs_reference="IRC §529 / IRS Publication 970",
                confidence=0.75,
                follow_up_questions=["What state do you live in?", "How old are your children?"],
            ))

        return opportunities

    # =========================================================================
    # VEHICLE DEDUCTION
    # =========================================================================

    def _detect_vehicle_deduction(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Business vehicle standard mileage vs. actual expense comparison."""
        opportunities = []

        if profile.vehicle_business_miles < 100:
            return opportunities

        mileage_deduction = Decimal(str(profile.vehicle_business_miles)) * self.MILEAGE_RATE_BUSINESS
        if mileage_deduction > Decimal("500"):
            opportunities.append(TaxOpportunity(
                id="vehicle_business_deduction",
                title=f"Business Vehicle Deduction — ${mileage_deduction:,.0f} Standard Mileage",
                description=(
                    f"You drove {profile.vehicle_business_miles:,} business miles. "
                    f"At the {self.MILEAGE_RATE_BUSINESS * 100:.0f}¢/mile IRS rate, "
                    f"that's a ${mileage_deduction:,.0f} deduction. "
                    "Alternatively, track actual expenses (gas, insurance, depreciation) and compare — "
                    "use whichever method gives a higher deduction."
                ),
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=mileage_deduction * self._marginal_rate(profile),
                action_required=(
                    "Keep a mileage log (date, destination, business purpose, miles). "
                    "IRS-compliant apps: MileIQ, Everlance. "
                    "Claim on Schedule C (sole prop) or Form 2106 (employees)."
                ),
                irs_reference="IRS Publication 463",
                confidence=0.90,
                follow_up_questions=[
                    "Did you track your mileage throughout the year?",
                    "Do you know your actual vehicle expenses for the year?",
                ],
            ))

        return opportunities

    # =========================================================================
    # EQUITY COMPENSATION
    # =========================================================================

    def _detect_equity_comp(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """RSU vesting, ISO AMT risk, ESPP, NUA strategy for company stock in 401(k)."""
        opportunities = []

        # ── RSU ordinary income recognition ─────────────────────────────────
        if profile.has_rsu and profile.rsu_vested_value > Decimal("5000"):
            opportunities.append(TaxOpportunity(
                id="rsu_tax_planning",
                title="RSU Vesting Income — Tax Planning Opportunity",
                description=(
                    f"You have ${profile.rsu_vested_value:,.0f} in RSU vesting income this year, "
                    "taxed as ordinary income at vesting. Key strategies: (1) elect withholding "
                    "at your marginal rate (not just 22%), (2) consider selling shares immediately "
                    "at vesting (locks in zero capital gain), (3) if holding, track cost basis "
                    "= FMV at vest date."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Verify employer withheld at correct rate. Supplement with estimated tax "
                    "payment if withheld at flat 22% but you're in a higher bracket."
                ),
                irs_reference="IRS Publication 525",
                confidence=0.90,
                follow_up_questions=["What was the per-share FMV when your RSUs vested?"],
            ))

        # ── ESPP income & disqualifying disposition ──────────────────────────
        if profile.has_espp and profile.espp_income > Decimal("1000"):
            opportunities.append(TaxOpportunity(
                id="espp_tax_treatment",
                title="ESPP Disqualifying vs. Qualifying Disposition",
                description=(
                    f"ESPP income of ${profile.espp_income:,.0f} may be ordinary income "
                    "(disqualifying disposition if sold < 2 years from grant or < 1 year from purchase). "
                    "Qualifying dispositions only recognize bargain element as ordinary income; "
                    "the rest is LTCG. Review your 1099-B and W-2 carefully — ESPP is the most "
                    "frequently mis-reported equity form."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Cross-check Form 3922 (received from employer) against 1099-B. "
                    "Adjust cost basis on 1099-B if employer already reported ordinary income on W-2."
                ),
                irs_reference="IRS Form 3922 / Publication 525",
                confidence=0.85,
            ))

        # ── ISO & Alternative Minimum Tax (AMT) ─────────────────────────────
        if profile.has_iso_options and profile.iso_exercises_ytd > Decimal("10000"):
            amt_pref = profile.iso_exercises_ytd  # Spread is AMT preference item
            amt_exemption = self.AMT_EXEMPTION.get(profile.filing_status, Decimal("88100"))
            if amt_pref > amt_exemption * Decimal("0.30"):
                opportunities.append(TaxOpportunity(
                    id="iso_amt_risk",
                    title="ISO Exercise — Alternative Minimum Tax (AMT) Exposure",
                    description=(
                        f"You exercised ISOs with spread of ${profile.iso_exercises_ytd:,.0f}. "
                        "This spread is an AMT preference item and could trigger significant "
                        "AMT liability (26–28% on the spread). "
                        "Key: AMT does NOT apply if you sell the shares in the same calendar year "
                        "(disqualifying disposition eliminates AMT but creates ordinary income). "
                        f"AMT exemption for {profile.filing_status}: ${amt_exemption:,.0f}."
                    ),
                    category=OpportunityCategory.INVESTMENT,
                    priority=OpportunityPriority.HIGH,
                    action_required=(
                        "Run Form 6251 projection BEFORE year-end. Consider same-year sale "
                        "if AMT liability exceeds capital gain benefit. Consult CPA immediately."
                    ),
                    irs_reference="IRS Form 6251 / IRC §56",
                    confidence=0.85,
                    metadata={"cpa_required": True},
                ))

        # ── NSO ordinary income ──────────────────────────────────────────────
        if profile.has_nso_options:
            opportunities.append(TaxOpportunity(
                id="nso_tax_planning",
                title="NSO Exercise — Ordinary Income + Payroll Tax at Exercise",
                description=(
                    "Non-qualified stock options (NSOs) trigger ordinary income AND payroll "
                    "taxes on the spread at exercise. Unlike ISOs, no AMT concern, but income "
                    "is reported on W-2 (employees) or 1099-NEC (contractors). "
                    "Post-exercise holding period determines capital gain treatment on future appreciation."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.MEDIUM,
                action_required=(
                    "Verify W-2 Box 12 code V reflects NSO income. Ensure proper withholding. "
                    "Track grant date, exercise date, FMV at exercise as cost basis."
                ),
                irs_reference="IRS Publication 525",
                confidence=0.80,
            ))

        # ── Net Unrealized Appreciation (NUA) ────────────────────────────────
        if profile.has_company_stock_in_401k:
            opportunities.append(TaxOpportunity(
                id="nua_strategy",
                title="Net Unrealized Appreciation (NUA) — Convert 401(k) Stock to LTCG Rates",
                description=(
                    "If you hold highly appreciated employer stock in your 401(k), the NUA "
                    "strategy lets you take a lump-sum distribution: pay ordinary income only "
                    "on your original cost basis, and the appreciation (NUA) is taxed at "
                    "long-term capital gains rates (0/15/20%) when you sell. "
                    "Can save tens of thousands vs. all-ordinary-income RMD approach."
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                savings_range=(Decimal("10000"), Decimal("100000")),
                action_required=(
                    "Compare: (a) NUA strategy at separation/retirement vs. "
                    "(b) rolling to IRA and paying ordinary rates. "
                    "Requires lump-sum distribution in single tax year."
                ),
                irs_reference="IRS Publication 575 / IRC §402(e)(4)",
                confidence=0.70,
                prerequisites=["Must be leaving employer or reaching age 59½", "Must take lump-sum distribution"],
                metadata={"cpa_required": True},
            ))

        return opportunities

    # =========================================================================
    # CAPITAL GAIN OPTIMIZATION
    # =========================================================================

    def _detect_capital_gain_optimization(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """LTCG 0% bracket harvesting, qualified dividends, ST vs LT timing."""
        opportunities = []

        agi = profile.agi_estimate

        # ── 0% LTCG bracket harvesting ────────────────────────────────────
        if profile.filing_status in ("single", "head_of_household"):
            ltcg_0pct_top = self.LTCG_0PCT_SINGLE
        elif profile.filing_status == "married_filing_jointly":
            ltcg_0pct_top = self.LTCG_0PCT_MFJ
        else:
            ltcg_0pct_top = self.LTCG_0PCT_SINGLE

        room_in_0pct = ltcg_0pct_top - agi
        if room_in_0pct > Decimal("5000") and (profile.long_term_gains > 0 or profile.capital_gains > 0):
            opportunities.append(TaxOpportunity(
                id="ltcg_0pct_harvesting",
                title="0% Capital Gains Rate — Harvest Gains Tax-Free",
                description=(
                    f"Your income leaves ${room_in_0pct:,.0f} of room in the 0% long-term "
                    "capital gains bracket. You can sell appreciated positions, realize that "
                    "gain tax-free, and immediately repurchase (no wash-sale rule for gains). "
                    "This resets your cost basis higher, reducing future tax."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=room_in_0pct * Decimal("0.15"),  # vs. 15% rate next year
                action_required=(
                    "Before Dec 31: sell appreciated long-term positions up to "
                    f"${room_in_0pct:,.0f} in gains. Immediately repurchase to maintain exposure."
                ),
                irs_reference="IRC §1(h) / IRS Publication 550",
                confidence=0.85,
                deadline=f"December 31, {self.TAX_YEAR}",
            ))

        # ── Short-term vs. long-term holding period ───────────────────────
        if profile.short_term_gains > Decimal("5000") and profile.short_term_gains > profile.long_term_gains:
            potential_savings = profile.short_term_gains * Decimal("0.15")  # ~15% rate difference
            opportunities.append(TaxOpportunity(
                id="stcg_to_ltcg_conversion",
                title="Convert Short-Term Gains to Long-Term — Save 15–20%",
                description=(
                    f"You have ${profile.short_term_gains:,.0f} in short-term capital gains "
                    "taxed at ordinary income rates (up to 37%). "
                    "Holding positions more than 12 months converts to long-term rates (0/15/20%). "
                    f"Estimated tax saved by converting to LTCG: ~${potential_savings:,.0f}."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=potential_savings,
                action_required=(
                    "Identify positions held 10–11 months: delay sale past 12-month mark. "
                    "Track purchase dates carefully to avoid short-term treatment."
                ),
                irs_reference="IRS Publication 550",
                confidence=0.80,
            ))

        # ── Qualified dividends verification ─────────────────────────────
        if profile.qualified_dividends > Decimal("2000"):
            estimated_savings = profile.qualified_dividends * Decimal("0.13")  # 22% vs 15% rate
            opportunities.append(TaxOpportunity(
                id="qualified_dividends_verification",
                title="Verify Qualified Dividends Classification",
                description=(
                    f"You have ${profile.qualified_dividends:,.0f} in dividends reported as "
                    "qualified (taxed at 0/15/20% rates). Non-qualified dividends are taxed "
                    "as ordinary income — ensure your broker correctly classifies them. "
                    "Holding period requirement: stock must be held > 60 days around ex-dividend date."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=estimated_savings,
                action_required=(
                    "Review 1099-DIV Box 1a (total) vs Box 1b (qualified). "
                    "Foreign dividends may not qualify — check 1099-DIV footnotes."
                ),
                irs_reference="IRS Publication 550",
                confidence=0.85,
            ))

        # ── Crypto wash sale warning (not covered by IRS wash-sale rule yet) ─
        if profile.crypto_gains > 0 or profile.crypto_losses > Decimal("1000"):
            net_crypto = profile.crypto_gains - profile.crypto_losses
            opportunities.append(TaxOpportunity(
                id="crypto_tax_optimization",
                title="Crypto Tax Planning — Loss Harvesting & FIFO vs HIFO",
                description=(
                    "Cryptocurrency is property — every sale, swap, or conversion is a taxable "
                    "event. Unlike stocks, the wash-sale rule does NOT currently apply to crypto "
                    f"(sell at a loss and immediately repurchase). Net crypto P&L: ${net_crypto:,.0f}. "
                    "Using HIFO (highest cost basis first) accounting can minimize gains. "
                    "Use crypto tax software: Koinly, CoinTracker, or TaxBit."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Export transaction history from all exchanges. "
                    "Consider harvesting unrealized losses before Dec 31. "
                    "Report on Form 8949 / Schedule D."
                ),
                irs_reference="IRS Notice 2014-21 / Form 8949",
                confidence=0.85,
                deadline=f"December 31, {self.TAX_YEAR}",
            ))

        return opportunities

    # =========================================================================
    # ADVANCED RENTAL / REAL ESTATE
    # =========================================================================

    def _detect_rental_advanced(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Real estate professional status, $25K passive loss allowance, STR rules."""
        opportunities = []

        if profile.rental_income == 0 and profile.str_rental_days == 0:
            return opportunities

        # ── Real Estate Professional Status (REPS) ──────────────────────────
        if not profile.is_real_estate_professional and profile.rental_income > Decimal("10000"):
            opportunities.append(TaxOpportunity(
                id="real_estate_professional_status",
                title="Real Estate Professional Status — Unlock Unlimited Loss Deductions",
                description=(
                    "If you spend 750+ hours/year on real estate activities AND that represents "
                    "more than half your working time, you qualify as a Real Estate Professional "
                    "(REPS). This reclassifies rental losses from passive to active — "
                    "allowing unlimited deductions against ordinary income. "
                    "Can save $20,000–$100,000+ for high earners with rental losses."
                ),
                category=OpportunityCategory.REAL_ESTATE,
                priority=OpportunityPriority.HIGH,
                savings_range=(Decimal("5000"), Decimal("50000")),
                action_required=(
                    "Document hours with a contemporaneous log (date, property, activity, hours). "
                    "Elect to aggregate all rental activities (once made, irrevocable). "
                    "File Form 8582 and attach election statement."
                ),
                irs_reference="IRC §469(c)(7) / IRS Publication 527",
                confidence=0.65,
                prerequisites=["750+ hours in real estate activities", "More than 50% of work hours in real estate"],
                metadata={"cpa_required": True},
            ))

        # ── $25K passive loss allowance (active participation) ───────────────
        if (profile.rental_active_participation
                and profile.passive_losses_carryforward > 0
                and profile.agi_estimate < Decimal("150000")):
            allowance = Decimal("25000") if profile.agi_estimate < Decimal("100000") else (
                (Decimal("150000") - profile.agi_estimate) / Decimal("2")
            )
            if allowance > 0:
                opportunities.append(TaxOpportunity(
                    id="rental_passive_loss_25k",
                    title="Rental Passive Loss — $25,000 Active Participation Allowance",
                    description=(
                        f"Active participants in rental real estate can deduct up to $25,000 "
                        "in rental losses against ordinary income — even if you don't qualify "
                        "as a real estate professional. "
                        f"Phase-out: $100K–$150K AGI (you qualify for ~${allowance:,.0f}). "
                        "Requires 'active participation' (approving tenants, leases, repairs)."
                    ),
                    category=OpportunityCategory.REAL_ESTATE,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=allowance * self._marginal_rate(profile),
                    action_required=(
                        "Document active participation. Report losses on Form 8582. "
                        "Check IRS definition of 'active participation' (less than REPS)."
                    ),
                    irs_reference="IRC §469(i) / Form 8582",
                    confidence=0.80,
                ))

        # ── Short-Term Rental (STR) material participation ────────────────────
        if profile.str_rental_days > 0:
            avg_rental_days = profile.str_rental_days
            is_str = avg_rental_days <= 7  # Average rental period ≤ 7 days = not passive
            if is_str and profile.str_personal_days < profile.str_rental_days * 0.1:
                opportunities.append(TaxOpportunity(
                    id="str_material_participation",
                    title="Short-Term Rental — Non-Passive with Material Participation",
                    description=(
                        f"Your rental averages ≤7 days (STR — Airbnb/VRBO). "
                        "STRs are NOT subject to passive activity rules if you materially participate "
                        "(500+ hours, or >100 hours and no one else works more). "
                        "Material participation allows losses to offset ANY income — "
                        "a major advantage over traditional long-term rentals."
                    ),
                    category=OpportunityCategory.REAL_ESTATE,
                    priority=OpportunityPriority.HIGH,
                    savings_range=(Decimal("5000"), Decimal("30000")),
                    action_required=(
                        "Track hours managing the STR property. "
                        "Meet material participation test (IRS Reg §1.469-5T). "
                        "Keep guest logs as proof of average rental period."
                    ),
                    irs_reference="IRC §469 / Reg §1.469-1T(e)(3)",
                    confidence=0.75,
                    metadata={"cpa_required": True},
                ))

            # Personal use day warning
            if profile.str_personal_days > profile.str_rental_days * 0.1 and profile.str_personal_days > 14:
                opportunities.append(TaxOpportunity(
                    id="str_personal_use_limit",
                    title="Short-Term Rental Personal Use Days — Expense Allocation Required",
                    description=(
                        f"Personal use days ({profile.str_personal_days}) exceed the greater of "
                        "14 days or 10% of rental days. This converts the property to a "
                        "'personal/rental mix' — expenses must be allocated between personal "
                        "and rental use. Rental loss deduction is limited."
                    ),
                    category=OpportunityCategory.REAL_ESTATE,
                    priority=OpportunityPriority.MEDIUM,
                    action_required=(
                        "Track all expenses and allocate by (rental days / total days). "
                        "Consider reducing personal use below 14 days or 10% threshold next year."
                    ),
                    irs_reference="IRC §280A / IRS Publication 527",
                    confidence=0.80,
                ))

        return opportunities

    # =========================================================================
    # SPECIAL SITUATIONS
    # =========================================================================

    def _detect_special_situations(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """COD income/insolvency, NOL carryforward, hobby loss, gig economy."""
        opportunities = []

        # ── Cancellation of Debt (COD) Income ────────────────────────────────
        if profile.has_cod_income and profile.cod_amount > Decimal("600"):
            if profile.is_insolvent:
                opportunities.append(TaxOpportunity(
                    id="cod_insolvency_exclusion",
                    title="COD Income — Insolvency Exclusion May Eliminate Tax",
                    description=(
                        f"You have ${profile.cod_amount:,.0f} in cancelled debt (Form 1099-C). "
                        "Normally this is taxable income — BUT if you were insolvent (liabilities "
                        "exceeded assets) immediately before the cancellation, you can exclude "
                        "the cancelled debt income up to the amount of insolvency. "
                        "This can eliminate thousands in unexpected tax."
                    ),
                    category=OpportunityCategory.DEDUCTION,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=profile.cod_amount * self._marginal_rate(profile),
                    action_required=(
                        "Complete Form 982 (Reduction of Tax Attributes). "
                        "Document insolvency: list all assets and liabilities at date of cancellation. "
                        "CPA review strongly recommended."
                    ),
                    irs_reference="IRC §108 / Form 982",
                    confidence=0.80,
                    metadata={"cpa_required": True},
                ))
            else:
                opportunities.append(TaxOpportunity(
                    id="cod_income_reporting",
                    title="Cancelled Debt Income — Must Be Reported (Form 1099-C)",
                    description=(
                        f"You have ${profile.cod_amount:,.0f} in cancelled debt. "
                        "This is taxable ordinary income unless an exclusion applies "
                        "(insolvency, bankruptcy, qualified farm/real estate debt). "
                        "Failure to report is a common audit trigger."
                    ),
                    category=OpportunityCategory.DEDUCTION,
                    priority=OpportunityPriority.HIGH,
                    action_required=(
                        "Report 1099-C income on Schedule 1. Review whether any exclusion applies. "
                        "Check if the debt was for a primary residence (Qualified Principal Residence Indebtedness)."
                    ),
                    irs_reference="IRC §61(a)(11) / Form 982",
                    confidence=0.90,
                ))

        # ── NOL Carryforward ─────────────────────────────────────────────────
        if profile.has_nol_carryforward and profile.nol_amount > Decimal("5000"):
            # Under TCJA, NOLs carry forward indefinitely, offset up to 80% of taxable income
            potential_offset = min(profile.nol_amount, profile.agi_estimate * Decimal("0.80"))
            if potential_offset > Decimal("1000"):
                opportunities.append(TaxOpportunity(
                    id="nol_carryforward_utilization",
                    title=f"NOL Carryforward — ${profile.nol_amount:,.0f} Available to Offset Income",
                    description=(
                        f"You have a Net Operating Loss (NOL) carryforward of ${profile.nol_amount:,.0f}. "
                        "Under TCJA rules, NOLs can offset up to 80% of taxable income each year "
                        f"and carry forward indefinitely. Potential offset this year: ${potential_offset:,.0f}."
                    ),
                    category=OpportunityCategory.DEDUCTION,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=potential_offset * self._marginal_rate(profile),
                    action_required=(
                        "Apply on Schedule 1 Line 8a. Track NOL origin year and amount. "
                        "Pre-2018 NOLs carry back 2 years / forward 20 years at 100% offset."
                    ),
                    irs_reference="IRC §172 / IRS Publication 536",
                    confidence=0.85,
                ))

        # ── Hobby Loss Rules (IRC §183) ──────────────────────────────────────
        if profile.hobby_income > Decimal("3000"):
            opportunities.append(TaxOpportunity(
                id="hobby_loss_rules",
                title="Hobby vs. Business Classification — Protect Deductions",
                description=(
                    f"You have ${profile.hobby_income:,.0f} in income from an activity that "
                    "may be classified as a hobby. Under IRC §183, hobby expenses are NOT "
                    "deductible. If the activity qualifies as a business (profit in 3 of 5 years, "
                    "conducted in businesslike manner), all ordinary business expenses are deductible. "
                    "IRS scrutinizes 'hobby losses' closely."
                ),
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Document business intent: separate bank account, business plan, "
                    "track time/effort, advertise, consult experts. "
                    "Consider making a §183(e) election to extend presumption period."
                ),
                irs_reference="IRC §183 / IRS Publication 535",
                confidence=0.80,
            ))

        # ── Gig Economy / 1099-NEC guidance ─────────────────────────────────
        if profile.is_gig_worker and profile.self_employment_income > Decimal("5000"):
            opportunities.append(TaxOpportunity(
                id="gig_economy_deductions",
                title="Gig Worker Deductions — Platform Fees, Equipment, Phone, Mileage",
                description=(
                    "Gig workers (Uber, DoorDash, TaskRabbit, Instacart) can deduct ALL "
                    "ordinary and necessary business expenses on Schedule C: "
                    "(1) mileage at $0.70/mile, (2) platform service fees, "
                    "(3) phone/data plan (business %), (4) equipment/supplies, "
                    "(5) 50% SE tax deduction, (6) SE health insurance premiums. "
                    "Many gig workers over-report income by not claiming these deductions."
                ),
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Collect all 1099-NEC/1099-K forms. Track mileage with app. "
                    "Download expense reports from each platform. "
                    "Allocate phone plan by business-use percentage."
                ),
                irs_reference="IRS Publication 334 / Schedule C",
                confidence=0.90,
            ))

        return opportunities

    # =========================================================================
    # HOUSEHOLD EMPLOYER (NANNY TAX)
    # =========================================================================

    def _detect_household_employer(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Schedule H nanny/household employee payroll tax obligations."""
        opportunities = []

        if not profile.has_household_employee:
            return opportunities

        if profile.household_employee_wages >= self.HOUSEHOLD_EMPLOYEE_THRESHOLD:
            fica_owed = profile.household_employee_wages * Decimal("0.0765")  # Employer FICA share
            opportunities.append(TaxOpportunity(
                id="household_employer_schedule_h",
                title="Nanny/Household Employee Tax — Schedule H Required",
                description=(
                    f"You paid ${profile.household_employee_wages:,.0f} to a household employee "
                    f"(>= ${self.HOUSEHOLD_EMPLOYEE_THRESHOLD:,.0f} threshold). "
                    "You must: (1) withhold and pay Social Security + Medicare taxes (7.65% each), "
                    "(2) possibly pay FUTA, (3) file Schedule H with your Form 1040. "
                    f"Employer FICA due: ~${fica_owed:,.0f}. "
                    "Failure to comply = IRS penalties + back taxes."
                ),
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=-fica_owed,  # This is a liability, not savings
                action_required=(
                    "1. Get EIN (IRS.gov). 2. Provide employee Form W-2 by Jan 31. "
                    "3. Withhold employee's share from wages. 4. File Schedule H with Form 1040. "
                    "5. Consider HomeWork Solutions or HomePay for compliance."
                ),
                irs_reference="IRS Schedule H / Publication 926",
                confidence=0.95,
                deadline=f"January 31, {self.TAX_YEAR + 1} (W-2 due)",
                metadata={"is_obligation": True},
            ))

        return opportunities

    # =========================================================================
    # MISCELLANEOUS DEDUCTIONS & COMPLIANCE
    # =========================================================================

    def _detect_miscellaneous(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """Gambling, educator expense, foreign tax credit, FBAR, LTC insurance."""
        opportunities = []

        # ── Gambling Winnings and Losses ─────────────────────────────────────
        if profile.gambling_winnings > Decimal("600"):
            opportunities.append(TaxOpportunity(
                id="gambling_income_losses",
                title="Gambling Winnings Must Be Reported + Losses Offset (if Itemizing)",
                description=(
                    f"You have ${profile.gambling_winnings:,.0f} in gambling winnings — "
                    "fully taxable and reported on Schedule 1. "
                    f"Good news: gambling losses of ${profile.gambling_losses:,.0f} can offset "
                    "winnings — BUT only if you itemize deductions (not available for standard deduction). "
                    "Keep gambling logs: date, casino, game, wins/losses."
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Report all W-2G forms. If itemizing, deduct losses up to winnings on Schedule A. "
                    "Maintain session-by-session gambling diary."
                ),
                irs_reference="IRS Publication 529 / Schedule A",
                confidence=0.90,
            ))

        # ── Educator Expense Deduction ───────────────────────────────────────
        if profile.educator_expenses > Decimal("50"):
            deductible = min(profile.educator_expenses, self.EDUCATOR_EXPENSE_MAX)
            opportunities.append(TaxOpportunity(
                id="educator_expense_deduction",
                title=f"Educator Expense Deduction — Up to ${self.EDUCATOR_EXPENSE_MAX:,.0f}",
                description=(
                    f"K-12 educators can deduct up to ${self.EDUCATOR_EXPENSE_MAX:,.0f} for "
                    "out-of-pocket classroom supplies — even if you take the standard deduction. "
                    f"Your eligible expenses: ${profile.educator_expenses:,.0f} → "
                    f"deduction: ${deductible:,.0f}."
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=deductible * self._marginal_rate(profile),
                action_required=(
                    "Claim on Schedule 1, Line 11. Keep all receipts. "
                    "Eligible: books, supplies, computer equipment, software, professional development."
                ),
                irs_reference="IRC §62(a)(2)(D) / Schedule 1",
                confidence=0.90,
                prerequisites=["Must be K-12 teacher, instructor, counselor, principal, or aide"],
            ))

        # ── Foreign Tax Credit ───────────────────────────────────────────────
        if profile.foreign_taxes_paid > Decimal("300"):
            opportunities.append(TaxOpportunity(
                id="foreign_tax_credit",
                title="Foreign Tax Credit — Avoid Double Taxation on Foreign Income",
                description=(
                    f"You paid ${profile.foreign_taxes_paid:,.0f} in foreign taxes. "
                    "The Foreign Tax Credit (Form 1116) provides a dollar-for-dollar credit "
                    "against US tax — generally better than the foreign tax deduction. "
                    "De minimis: if total foreign taxes ≤ $300 (single) / $600 (MFJ) and "
                    "all from 1099-DIV, you can claim without Form 1116."
                ),
                category=OpportunityCategory.CREDIT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=profile.foreign_taxes_paid,
                action_required=(
                    "File Form 1116 (or claim directly on Schedule 3 if ≤$300/$600). "
                    "Check 1099-DIV Box 7 for foreign taxes withheld by mutual funds."
                ),
                irs_reference="IRS Form 1116 / Publication 514",
                confidence=0.85,
            ))

        # ── FBAR Compliance Warning ──────────────────────────────────────────
        if profile.has_fbar_requirement or profile.foreign_income > Decimal("10000"):
            opportunities.append(TaxOpportunity(
                id="fbar_fatca_compliance",
                title="FBAR + FATCA — Foreign Account Reporting Required",
                description=(
                    "If you have foreign bank accounts with aggregate value > $10,000 at any "
                    "point during the year, you must file FinCEN Form 114 (FBAR) by April 15 "
                    "(auto-extended to Oct 15). FATCA (Form 8938) required for higher thresholds. "
                    "Penalties: up to $10,000/year for non-willful violation; "
                    "$100,000+ or 50% of account for willful violations."
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "File FBAR at BSA E-Filing System (bsaefiling.fincen.treas.gov). "
                    "File Form 8938 with tax return if FATCA thresholds met. "
                    "Consider Streamlined Filing Compliance Procedures if previously non-compliant."
                ),
                irs_reference="FinCEN Form 114 / IRS Form 8938 / FATCA",
                confidence=0.90,
                deadline=f"April 15, {self.TAX_YEAR + 1} (auto-extended to Oct 15)",
                metadata={"is_obligation": True},
            ))

        # ── Long-Term Care Insurance Deduction ───────────────────────────────
        if profile.has_long_term_care_insurance and profile.ltc_premiums_paid > Decimal("200"):
            # Find deduction limit by age bracket
            ltc_limit = Decimal("0")
            for age_threshold, limit in sorted(self.LTC_DEDUCTION_LIMITS.items()):
                if profile.age <= age_threshold:
                    ltc_limit = limit
                    break
            if ltc_limit == Decimal("0"):
                ltc_limit = self.LTC_DEDUCTION_LIMITS[99]
            deductible_ltc = min(profile.ltc_premiums_paid, ltc_limit)
            if deductible_ltc > Decimal("200"):
                opportunities.append(TaxOpportunity(
                    id="ltc_insurance_deduction",
                    title=f"Long-Term Care Insurance Premium Deduction — ${deductible_ltc:,.0f}",
                    description=(
                        f"Qualifying LTC insurance premiums are deductible as medical expenses "
                        f"(Schedule A). Age-based limit for age {profile.age}: ${ltc_limit:,.0f}/year. "
                        f"Your deductible amount: ${deductible_ltc:,.0f}. "
                        "Must exceed 7.5% AGI floor combined with other medical expenses."
                    ),
                    category=OpportunityCategory.HEALTHCARE,
                    priority=OpportunityPriority.MEDIUM,
                    estimated_savings=deductible_ltc * self._marginal_rate(profile),
                    action_required=(
                        "Add to Schedule A medical expenses. Policy must be 'qualified' LTC contract. "
                        "Self-employed: deduct 100% above-the-line without the 7.5% floor."
                    ),
                    irs_reference="IRC §213 / IRS Publication 502",
                    confidence=0.80,
                ))

        return opportunities

    # =========================================================================
    # ADVANCED SPECIAL SITUATIONS
    # =========================================================================

    def _detect_advanced_special(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """QOZ deferral, QSBS §1202, inherited IRA SECURE 2.0, AMT planning."""
        opportunities = []

        # ── Qualified Opportunity Zone (QOZ) ─────────────────────────────────
        if profile.has_opportunity_zone_investment and profile.opportunity_zone_gain_deferred > 0:
            opportunities.append(TaxOpportunity(
                id="qoz_gain_deferral",
                title="Qualified Opportunity Zone — Deferred Gain Recognition",
                description=(
                    f"You deferred ${profile.opportunity_zone_gain_deferred:,.0f} of capital "
                    f"gain via a Qualified Opportunity Fund. Deferred gain is recognized on the "
                    f"earlier of QOF sale or December 31, {self.QOZ_DEFERRAL_YEAR}. "
                    "Key benefit: appreciation in the QOF itself is tax-free if held 10+ years. "
                    "Ensure timely reporting on Form 8997 each year."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    f"File Form 8997 annually. Plan for {self.QOZ_DEFERRAL_YEAR} inclusion event. "
                    "Consider QOF distributions and their impact on exit basis."
                ),
                irs_reference="IRC §1400Z-2 / Form 8997",
                confidence=0.85,
                deadline=f"December 31, {self.QOZ_DEFERRAL_YEAR}",
            ))

        # ── QSBS §1202 Exclusion ──────────────────────────────────────────────
        if profile.has_iso_options or profile.has_nso_options or profile.has_rsu:
            opportunities.append(TaxOpportunity(
                id="qsbs_1202_exclusion",
                title="Qualified Small Business Stock (§1202) — Up to 100% Gain Exclusion",
                description=(
                    "If you hold stock in a C-corp with assets < $50M at time of issuance, "
                    "acquired after August 10, 1993, and held 5+ years, "
                    "IRC §1202 may exclude 50–100% of capital gains (up to $10M or 10x basis). "
                    "Potentially the largest tax break in the tax code for startup founders and investors. "
                    "100% exclusion for stock acquired after September 27, 2010."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                savings_range=(Decimal("50000"), Decimal("2000000")),
                action_required=(
                    "Verify stock meets QSBS requirements: C-corp, active business, "
                    "original issuance, held 5+ years. Get confirmation from company/counsel. "
                    "Do not sell before 5-year mark without confirming §1202 status."
                ),
                irs_reference="IRC §1202 / IRS Notice 2023-75",
                confidence=0.65,
                prerequisites=["Original issuance (not secondary market)", "C-corporation", "Held 5+ years"],
                metadata={"cpa_required": True},
            ))

        # ── Inherited IRA — SECURE Act 2.0 10-Year Rule ──────────────────────
        if profile.has_inherited_ira and profile.inherited_ira_balance > Decimal("10000"):
            opportunities.append(TaxOpportunity(
                id="inherited_ira_10yr_rule",
                title="Inherited IRA — SECURE 2.0 10-Year Distribution Rule",
                description=(
                    f"You have an inherited IRA with balance ${profile.inherited_ira_balance:,.0f}. "
                    "Under SECURE Act 2.0, most non-spouse beneficiaries must empty the account "
                    "within 10 years of the original owner's death. "
                    "If the original owner had begun RMDs, you may also owe annual RMDs in years 1–9. "
                    "Strategy: spread distributions to minimize tax bracket impact — "
                    "large forced distributions in year 10 can push you into 32–37% bracket."
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Calculate optimal annual withdrawal schedule to fill lower brackets. "
                    "Consider partial Roth conversion strategy. "
                    "Consult CPA for year-of-death RMD obligation and beneficiary rules."
                ),
                irs_reference="IRC §401(a)(9) / SECURE Act 2.0 / IRS Notice 2022-53",
                confidence=0.85,
                metadata={"cpa_required": True},
            ))

        # ── AMT Planning (general) ────────────────────────────────────────────
        if profile.agi_estimate > Decimal("200000") or (profile.has_iso_options and profile.iso_exercises_ytd > 0):
            amt_exemption = self.AMT_EXEMPTION.get(profile.filing_status, Decimal("88100"))
            phaseout_start = self.AMT_EXEMPTION_PHASEOUT_START.get(profile.filing_status, Decimal("626350"))
            if profile.agi_estimate > phaseout_start * Decimal("0.60"):
                opportunities.append(TaxOpportunity(
                    id="amt_planning",
                    title="Alternative Minimum Tax (AMT) Risk Assessment",
                    description=(
                        "Your income level or ISO exercises create AMT exposure. "
                        f"AMT exemption: ${amt_exemption:,.0f} (phases out above ${phaseout_start:,.0f}). "
                        "AMT 'preference items' include: ISO spread, SALT deduction, "
                        "accelerated depreciation, certain tax-exempt interest. "
                        "AMT rate: 26% on first $220,700 of AMTI; 28% above."
                    ),
                    category=OpportunityCategory.INVESTMENT,
                    priority=OpportunityPriority.HIGH,
                    action_required=(
                        "Run Form 6251 projection. Identify preference items. "
                        "Strategies to reduce: accelerate income into AMT year, "
                        "defer preference items, time ISO exercises carefully."
                    ),
                    irs_reference="IRS Form 6251 / IRC §55",
                    confidence=0.75,
                    metadata={"cpa_required": True},
                ))

        return opportunities

    # =========================================================================
    # STATE-SPECIFIC GUIDANCE
    # =========================================================================

    def _detect_state_guidance(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """State income tax planning, SALT, no-income-tax state opportunities."""
        opportunities = []

        state = profile.state.upper()
        if not state:
            return opportunities

        # ── No income tax state — 529 / retirement contribution timing ───────
        if state in self.NO_INCOME_TAX_STATES:
            opportunities.append(TaxOpportunity(
                id="no_income_tax_state",
                title=f"{state} Has No State Income Tax — Federal-Only Filing",
                description=(
                    f"You live in {state}, which has no state income tax. "
                    "This simplifies state filing but also means state-level deductions "
                    "(529 state deduction, state charitable deduction) are not available. "
                    "Focus tax planning on federal strategies exclusively."
                ),
                category=OpportunityCategory.FILING_STATUS,
                priority=OpportunityPriority.LOW,
                action_required="No state income tax return required. Confirm with state tax authority.",
                confidence=0.95,
            ))

        # ── High tax state — SALT cap planning ───────────────────────────────
        if state in self.HIGH_TAX_STATES:
            salt_paid = min(profile.state_local_taxes + profile.property_taxes, Decimal("100000"))
            capped_salt = min(salt_paid, self.SALT_CAP)
            uncapped_salt = salt_paid - capped_salt
            if uncapped_salt > Decimal("3000"):
                opportunities.append(TaxOpportunity(
                    id="high_tax_state_salt_planning",
                    title=f"High-Tax State ({state}) — SALT Cap Limits Your Deduction",
                    description=(
                        f"You're in {state}, one of the highest-tax states. "
                        f"Your state/local taxes of ${salt_paid:,.0f} are capped at ${self.SALT_CAP:,.0f} "
                        f"(${uncapped_salt:,.0f} of taxes is non-deductible at federal level). "
                        "Strategies: PTET (Pass-Through Entity Tax) election for business owners "
                        "avoids the individual SALT cap. "
                        "Deduct state taxes in the year paid — accelerate year-end state estimate payment."
                    ),
                    category=OpportunityCategory.DEDUCTION,
                    priority=OpportunityPriority.HIGH,
                    action_required=(
                        "Business owners: ask CPA about PTET election (available in CA, NY, NJ, IL, etc.). "
                        "Pay Q4 state estimate by Dec 31 (not Jan) to deduct this year. "
                        "Note: OBBBA raised SALT cap to $40K (AGI ≤ $500K) — verify with CPA for your situation."
                    ),
                    irs_reference="IRC §164 / IRS Notice 2020-75 (PTET)",
                    confidence=0.85,
                ))

        # ── State 529 deduction reminder ─────────────────────────────────────
        if profile.has_529_plan and state not in self.NO_INCOME_TAX_STATES:
            opportunities.append(TaxOpportunity(
                id="state_529_deduction",
                title=f"{state} 529 State Income Tax Deduction",
                description=(
                    f"Most states (including {state}) offer a state income tax deduction "
                    "for 529 contributions. Many states require you to contribute to "
                    "YOUR state's plan to get the deduction. "
                    "Some states (NY, PA, CO, UT, SC) offer full deductibility with high limits. "
                    f"Others (CA, DE, NH, NJ) offer no state deduction."
                ),
                category=OpportunityCategory.EDUCATION,
                priority=OpportunityPriority.MEDIUM,
                action_required=(
                    f"Verify {state}'s 529 deduction rules. If your state offers a deduction, "
                    "maximize contributions to the state plan before Dec 31."
                ),
                irs_reference="State tax code varies — check your state's 529 plan website",
                confidence=0.70,
            ))

        return opportunities

    # =========================================================================
    # DEADLINE & PENALTY RULES
    # =========================================================================

    def _detect_deadline_and_penalty_rules(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """
        April 15 filing deadline, extension (Oct 15), underpayment penalty safe harbors,
        late-filing vs. late-payment penalty distinctions, and FBAR deadlines.
        """
        opportunities = []
        next_year = self.TAX_YEAR + 1

        # ── Failure to File vs. Failure to Pay ───────────────────────────────
        # Always warn — applies to all taxpayers with a balance due
        estimated_tax = profile.agi_estimate * Decimal("0.20")
        estimated_balance = max(Decimal("0"), estimated_tax - profile.federal_withheld - profile.es_payments_ytd)

        if estimated_balance > Decimal("500"):
            opportunities.append(TaxOpportunity(
                id="filing_extension_strategy",
                title="April 15 Deadline — Extension vs. Payment Strategy",
                description=(
                    f"Your estimated balance due: ~${estimated_balance:,.0f}. "
                    f"Key deadlines for tax year {self.TAX_YEAR}:\n"
                    f"• April 15, {next_year}: File return OR extension (Form 4868). Pay tax owed.\n"
                    f"• October 15, {next_year}: Extended filing deadline (if extension filed).\n\n"
                    "CRITICAL DISTINCTION:\n"
                    "• Extension = more time to FILE (not more time to PAY).\n"
                    "• If you owe and don't pay by April 15: Failure-to-Pay penalty "
                    "= 0.5%/month of unpaid tax (max 25%).\n"
                    "• Failure-to-File penalty = 5%/month (max 25%). Filing an extension "
                    "eliminates the failure-to-file penalty but NOT failure-to-pay."
                ),
                category=OpportunityCategory.TIMING,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    f"By April 15, {next_year}: File Form 4868 extension AND pay estimated balance. "
                    "Pay via IRS Direct Pay, EFTPS, or credit card."
                ),
                irs_reference="IRS Form 4868 / IRS Publication 505",
                confidence=0.90,
                deadline=f"April 15, {next_year}",
            ))

        # ── Underpayment Penalty Safe Harbor ─────────────────────────────────
        se_and_investment = (profile.self_employment_income + profile.business_income +
                             profile.capital_gains + profile.interest_income + profile.dividend_income)
        if se_and_investment > Decimal("10000") or estimated_balance > Decimal("1000"):
            safe_harbor_pct = "110%" if profile.agi_estimate > Decimal("150000") else "100%"
            opportunities.append(TaxOpportunity(
                id="underpayment_penalty_safe_harbor",
                title="Avoid Underpayment Penalty — Safe Harbor Rules",
                description=(
                    "The IRS charges an underpayment penalty (currently ~8% annualized) if "
                    "you underpay taxes during the year. Avoid it by meeting a safe harbor:\n"
                    f"• Safe Harbor 1: Pay {safe_harbor_pct} of your PRIOR YEAR tax liability "
                    f"({'110%' if safe_harbor_pct == '110%' else '100%'} required because AGI > $150K).\n"
                    "• Safe Harbor 2: Pay 90% of CURRENT YEAR tax liability.\n"
                    "• Safe Harbor 3: Owe less than $1,000 after withholding/credits.\n"
                    "Quarterly due dates: April 15, June 15, September 15, January 15."
                ),
                category=OpportunityCategory.TIMING,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Calculate prior year tax from your prior return. "
                    "Divide by 4; pay each quarter via IRS Direct Pay. "
                    "Use Form 2210 to verify or request penalty waiver."
                ),
                irs_reference="IRS Form 2210 / IRC §6654",
                confidence=0.85,
                deadline=f"January 15, {next_year} (final quarterly payment)",
            ))

        # ── First-Time Penalty Abatement ─────────────────────────────────────
        opportunities.append(TaxOpportunity(
            id="first_time_penalty_abatement",
            title="First-Time Penalty Abatement — Waive Late Filing/Payment Penalty",
            description=(
                "If you have a clean compliance history (no penalties in prior 3 years), "
                "the IRS will waive your first failure-to-file, failure-to-pay, or "
                "failure-to-deposit penalty — automatically, just by asking. "
                "Call IRS at 1-800-829-1040 or write a request letter after paying tax owed. "
                "Also available: 'reasonable cause' abatement for medical emergencies, "
                "natural disasters, or erroneous IRS advice."
            ),
            category=OpportunityCategory.TIMING,
            priority=OpportunityPriority.MEDIUM,
            action_required=(
                "After filing and paying, call IRS or send CP2000 response requesting FTA. "
                "Say: 'I am requesting first-time abatement under IRM 20.1.1.3.6.1.' "
                "Keep a record of the IRS rep's name and ID number."
            ),
            irs_reference="IRM 20.1.1.3.6.1 / IRS Form 843",
            confidence=0.80,
        ))

        # ── IRA/HSA contribution deadline (April 15) ─────────────────────────
        # Contributions to IRA and HSA can be made UP TO April 15 for the prior tax year
        max_ira = self.CONTRIB_LIMITS["ira"]
        if profile.age >= 50:
            max_ira += self.CONTRIB_LIMITS["ira_catchup"]
        current_ira = profile.traditional_ira + profile.roth_ira
        if current_ira < max_ira:
            opportunities.append(TaxOpportunity(
                id="ira_hsa_april15_deadline",
                title=f"IRA & HSA Contribution Deadline — April 15, {next_year}",
                description=(
                    f"You can still contribute to an IRA and/or HSA for tax year {self.TAX_YEAR} "
                    f"until April 15, {next_year} — even after the year ends. "
                    f"IRA room remaining: ${max_ira - current_ira:,.0f}. "
                    "Traditional IRA contributions may be tax-deductible and reduce your {self.TAX_YEAR} AGI retroactively. "
                    "HSA contributions also reduce AGI for the year designated."
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    f"Contribute by April 15, {next_year}. Designate as '{self.TAX_YEAR}' contribution. "
                    "Do NOT wait until you file — you can contribute today and file later."
                ),
                irs_reference="IRS Publication 590-A / 969",
                confidence=0.90,
                deadline=f"April 15, {next_year}",
            ))

        # ── Solo 401(k) / SEP-IRA employer contribution deadline ──────────────
        if profile.self_employment_income > Decimal("20000") or profile.has_business:
            opportunities.append(TaxOpportunity(
                id="sep_solo401k_extended_deadline",
                title=f"SEP-IRA / Solo 401(k) Employer Contribution Deadline",
                description=(
                    f"Self-employed individuals can contribute to a SEP-IRA up to the extended "
                    f"due date of the return (October 15, {next_year} if extension filed). "
                    "Solo 401(k) employee deferral must be elected by December 31 of the tax year, "
                    "but employer profit-sharing contribution can be made by the extended due date. "
                    "SEP-IRA limit: 25% of net SE income, up to $70,000 for {self.TAX_YEAR}."
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "File Form 4868 extension to preserve Oct 15 deadline. "
                    "SEP: Open account and fund by extended due date. "
                    "Solo 401(k): Employee deferral election must be made by Dec 31."
                ),
                irs_reference="IRS Publication 560 / IRC §404(h)",
                confidence=0.85,
                deadline=f"October 15, {next_year} (if extension filed)",
            ))

        # ── Amended return window ─────────────────────────────────────────────
        opportunities.append(TaxOpportunity(
            id="amended_return_3yr_window",
            title="Amended Return (Form 1040-X) — 3-Year Window for Refunds",
            description=(
                "If you made errors on prior returns, you have 3 years from the original "
                "filing date (or 2 years from tax payment, whichever is later) to file "
                "Form 1040-X and claim a refund. Common reasons to amend: "
                "missed credits (EITC, CTC, education credits), wrong filing status, "
                "omitted deductions, corrected W-2/1099. "
                "You can now e-file amended returns."
            ),
            category=OpportunityCategory.TIMING,
            priority=OpportunityPriority.MEDIUM,
            action_required=(
                f"Review returns for {self.TAX_YEAR - 2}, {self.TAX_YEAR - 1}, {self.TAX_YEAR}. "
                "File Form 1040-X within 3 years of original due date."
            ),
            irs_reference="IRS Form 1040-X / IRC §6511",
            confidence=0.80,
        ))

        # ── Installment Agreement option ──────────────────────────────────────
        if estimated_balance > Decimal("2000"):
            opportunities.append(TaxOpportunity(
                id="installment_agreement_option",
                title="IRS Installment Agreement — Pay Balance Over Time",
                description=(
                    f"If you cannot pay your estimated balance of ${estimated_balance:,.0f} in full "
                    "by April 15, an IRS Installment Agreement lets you pay monthly. "
                    "Online IA (≤$50K balance): apply at IRS.gov — immediate approval. "
                    "Penalty continues to accrue (0.5%/month) but prevents collection actions. "
                    "Offer in Compromise (OIC): settle for less if genuinely unable to pay full amount."
                ),
                category=OpportunityCategory.TIMING,
                priority=OpportunityPriority.HIGH,
                action_required=(
                    "Apply at IRS.gov/OPA for Online Payment Agreement. "
                    "Or call 1-800-829-1040. Fee: $31 (online/direct debit) to $130 (check). "
                    "Waived if low income."
                ),
                irs_reference="IRS Form 9465 / IRC §6159",
                confidence=0.85,
                deadline=f"April 15, {next_year}",
            ))

        return opportunities

    def _detect_engine_insights(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """
        Surface insights directly from the FederalTaxEngine CalculationBreakdown
        that no rule-based detector can catch without running the full calc graph.

        Covers:
        - AMT exposure warnings with exact dollar amount
        - NIIT (3.8%) exposure on investment income
        - Effective rate vs marginal rate spread (over-withholding / opportunity)
        - State tax liability surfaced alongside federal
        - Refund vs balance-due guidance
        """
        opportunities: List[TaxOpportunity] = []
        breakdown = (_engine_ctx.get() or {}).get(id(profile))
        if breakdown is None:
            return opportunities

        next_year = self.TAX_YEAR + 1

        # ── AMT Exposure ────────────────────────────────────────────────────
        if breakdown.alternative_minimum_tax > 500:
            amt = Decimal(str(round(breakdown.alternative_minimum_tax, 2)))
            opportunities.append(TaxOpportunity(
                id="engine_amt_exposure",
                title=f"Alternative Minimum Tax — You Owe ${amt:,.0f} AMT",
                description=(
                    f"The FederalTaxEngine calculates ${amt:,.0f} in Alternative Minimum Tax "
                    f"for {self.TAX_YEAR}. AMT is triggered by:\n"
                    "• ISO stock option exercises (spread is an AMT preference item)\n"
                    "• Large miscellaneous itemized deductions\n"
                    "• Private activity bond interest\n"
                    "• High depreciation deductions\n\n"
                    "Planning opportunities: defer ISO exercises to a lower-income year, "
                    "bundle ISO exercises with capital losses, or use regular-tax deductions "
                    "strategically to reduce AMTI."
                ),
                category=OpportunityCategory.TIMING,
                priority=OpportunityPriority.HIGH,
                estimated_savings=amt,
                action_required="File Form 6251. Review ISO exercise timing with a CPA.",
                irs_reference="IRC §55 / Form 6251",
                confidence=0.99,
            ))

        # ── NIIT 3.8% on Net Investment Income ──────────────────────────────
        if breakdown.net_investment_income_tax > 200:
            niit = Decimal(str(round(breakdown.net_investment_income_tax, 2)))
            opportunities.append(TaxOpportunity(
                id="engine_niit_exposure",
                title=f"Net Investment Income Tax — ${niit:,.0f} NIIT at 3.8%",
                description=(
                    f"You owe ${niit:,.0f} in Net Investment Income Tax (3.8% surtax on "
                    "investment income above the threshold: $200K single / $250K MFJ).\n\n"
                    "Strategies to reduce NIIT:\n"
                    "• Increase 401(k)/IRA contributions to reduce MAGI below threshold\n"
                    "• Move investments into tax-exempt bonds or tax-deferred accounts\n"
                    "• Real Estate Professional status removes rental income from NIIT\n"
                    "• Opportunity Zone investments defer and potentially exclude gains\n"
                    "• Qualified Opportunity Fund investment reduces current NII"
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=niit,
                action_required="Review investment income reduction strategies before year-end.",
                irs_reference="IRC §1411 / Form 8960",
                confidence=0.99,
            ))

        # ── Marginal vs Effective Rate Spread ───────────────────────────────
        marginal_pct = breakdown.marginal_tax_rate  # percentage, e.g. 24.0
        eff_pct = breakdown.effective_tax_rate       # percentage, e.g. 18.0
        spread = marginal_pct - eff_pct
        if spread >= 8 and marginal_pct >= 22:
            spread_d = Decimal(str(round(spread, 1)))
            opportunities.append(TaxOpportunity(
                id="engine_rate_spread",
                title=f"Marginal {marginal_pct:.0f}% vs Effective {eff_pct:.0f}% — {spread_d:.0f}pt Spread",
                description=(
                    f"Your marginal rate ({marginal_pct:.0f}%) is {spread_d:.0f} points above your "
                    f"effective rate ({eff_pct:.0f}%). This large spread means every dollar of "
                    "NEW deductions saves you at the HIGH marginal rate while your average "
                    "burden is much lower. You are in the prime zone for:\n"
                    f"• Retirement contributions (each $1 saves ${marginal_pct/100:.2f})\n"
                    "• Bunching charitable deductions into this year\n"
                    "• Accelerating deductible business expenses\n"
                    "• Converting income from ordinary to capital gains rates"
                ),
                category=OpportunityCategory.TIMING,
                priority=OpportunityPriority.MEDIUM,
                action_required="Maximize deductible contributions before December 31.",
                irs_reference="IRS Publication 505",
                confidence=0.95,
            ))

        # ── State Tax Liability (from StateTaxEngine) ───────────────────────
        state_bd = (_state_ctx.get() or {}).get(id(profile))
        state_tax = state_bd.state_tax_liability if state_bd else 0
        if state_tax and state_tax > 500 and profile.state:
            st = Decimal(str(round(state_tax, 2)))
            eff_state = (
                f" (eff. {state_bd.state_tax_liability / state_bd.federal_agi * 100:.1f}%)"
                if state_bd and state_bd.federal_agi > 0 else ""
            )
            opportunities.append(TaxOpportunity(
                id="engine_state_tax_liability",
                title=f"{profile.state} State Tax: ${st:,.0f} Owed{eff_state} — Reduction Strategies",
                description=(
                    f"StateTaxEngine calculates ${st:,.0f} in {profile.state} state income tax. "
                    "State-specific reduction strategies:\n"
                    "• 529 plan contributions (many states allow deduction)\n"
                    "• PTET election for pass-through income (bypasses $10K SALT cap)\n"
                    "• State pension/SS exclusions (varies by state)\n"
                    "• Residency planning if considering relocation\n"
                    "• State NOL carryforward if business had losses\n"
                    f"• {profile.state}-specific credits (research credits, low-income credits)"
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=st * Decimal("0.15"),  # avg reduction potential ~15%
                action_required=f"Review {profile.state} state return for all available deductions and credits.",
                irs_reference=f"{profile.state} Department of Revenue",
                confidence=0.85,
            ))

        # ── Refund / Balance Due Alert ──────────────────────────────────────
        refund = getattr(breakdown, "refund_or_owed", None)
        if refund is not None:
            if refund > 2000:
                opportunities.append(TaxOpportunity(
                    id="engine_large_refund",
                    title=f"Large Refund Expected (${refund:,.0f}) — Adjust Withholding",
                    description=(
                        f"You are projected to receive a ${refund:,.0f} federal refund. "
                        "A large refund means you gave the IRS an interest-free loan all year.\n\n"
                        "Action: File a new W-4 with your employer to reduce withholding. "
                        f"If you redirected ${refund:,.0f} into a Roth IRA or index fund "
                        "throughout the year, you'd capture growth on that money instead."
                    ),
                    category=OpportunityCategory.TIMING,
                    priority=OpportunityPriority.LOW,
                    action_required="Submit updated W-4 to employer (use IRS Tax Withholding Estimator).",
                    irs_reference="IRS Form W-4 / Publication 505",
                    confidence=0.90,
                ))
            elif refund < -1000:
                balance = Decimal(str(abs(round(refund, 2))))
                opportunities.append(TaxOpportunity(
                    id="engine_balance_due",
                    title=f"Balance Due ${balance:,.0f} — Adjust Withholding Now",
                    description=(
                        f"You are projected to owe ${balance:,.0f} at filing. "
                        "To avoid underpayment penalties:\n"
                        "• Increase W-4 withholding with employer\n"
                        "• Make an estimated tax payment now via IRS Direct Pay\n"
                        f"• Safe harbor: pay 100%/110% of {self.TAX_YEAR - 1} tax liability in equal installments"
                    ),
                    category=OpportunityCategory.TIMING,
                    priority=OpportunityPriority.HIGH,
                    estimated_savings=balance * Decimal("0.08"),  # avoid ~8% underpayment penalty
                    action_required="Increase withholding or pay estimated tax immediately.",
                    irs_reference="IRS Form 2210 / IRC §6654",
                    deadline=f"January 15, {next_year}",
                    confidence=0.92,
                ))

        return opportunities

    def _detect_multiyear_planning(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """
        Multi-year tax planning opportunities that cross tax year boundaries.

        Covers:
        - Roth conversion window analysis
        - Capital gain harvesting at 0% LTCG rate
        - Income bunching / deduction bunching
        - NOL carryforward application timing
        - Bracket management before RMD years
        """
        opportunities: List[TaxOpportunity] = []
        breakdown = (_engine_ctx.get() or {}).get(id(profile))
        agi = profile.agi_estimate
        next_year = self.TAX_YEAR + 1

        # ── Roth Conversion Window ───────────────────────────────────────────
        # Best window: income is temporarily low (gap years, early retirement, before SS starts)
        ira_balance = profile.ira_balance
        if ira_balance > Decimal("50000") and agi < Decimal("400000"):
            # Calculate how much room exists to the top of the 22% bracket
            bracket_tops = {
                "single": Decimal("103350"),
                "married_filing_jointly": Decimal("206700"),
                "head_of_household": Decimal("103350"),
                "married_filing_separately": Decimal("51675"),
                "qualifying_widow": Decimal("206700"),
            }
            top = bracket_tops.get(profile.filing_status, Decimal("103350"))
            std = self.STANDARD_DEDUCTION.get(profile.filing_status, Decimal("15000"))
            taxable_income_est = max(Decimal("0"), agi - std)
            room_to_top_22 = max(Decimal("0"), top - taxable_income_est)
            if room_to_top_22 > Decimal("5000"):
                conversion_amount = min(room_to_top_22, ira_balance)
                rate = self._marginal_rate(profile)
                roth_cost = conversion_amount * rate
                future_savings = conversion_amount * Decimal("0.05")  # 5yr tax-free growth est
                opportunities.append(TaxOpportunity(
                    id="multiyear_roth_conversion",
                    title="Roth Conversion Window — Convert Now at Lower Rate",
                    description=(
                        f"You have ${room_to_top_22:,.0f} of room to the top of the "
                        f"{rate:.0%} bracket. Converting ${conversion_amount:,.0f} "
                        f"from Traditional IRA (balance: ${ira_balance:,.0f}) to Roth now "
                        f"costs ${roth_cost:,.0f} in taxes but avoids future RMDs, grows "
                        "tax-free forever, and is inherited tax-free by beneficiaries.\n\n"
                        "Best for: low-income years before RMDs start (age 73), "
                        "between retirement and Social Security, after large deduction year."
                    ),
                    category=OpportunityCategory.RETIREMENT,
                    priority=OpportunityPriority.HIGH if room_to_top_22 > Decimal("20000") else OpportunityPriority.MEDIUM,
                    estimated_savings=future_savings,
                    action_required=f"Initiate Roth conversion of up to ${conversion_amount:,.0f} before December 31, {self.TAX_YEAR}.",
                    irs_reference="IRC §408A / IRS Publication 590-B",
                    deadline=f"December 31, {self.TAX_YEAR}",
                    confidence=0.88,
                    scenario_ids=["max_ira"],
                ))

        # ── 0% Capital Gains Harvesting ─────────────────────────────────────
        ltcg_0_threshold = self.LTCG_0PCT_MFJ if profile.filing_status == "married_filing_jointly" else self.LTCG_0PCT_SINGLE
        std = self.STANDARD_DEDUCTION.get(profile.filing_status, Decimal("15000"))
        taxable_inc = max(Decimal("0"), agi - std)
        room_at_0pct = max(Decimal("0"), ltcg_0_threshold - taxable_inc)

        if room_at_0pct > Decimal("2000") and profile.long_term_gains == Decimal("0"):
            opportunities.append(TaxOpportunity(
                id="multiyear_harvest_gains_0pct",
                title=f"Harvest ${room_at_0pct:,.0f} of Capital Gains at 0% Federal Rate",
                description=(
                    f"You have ${room_at_0pct:,.0f} of room in the 0% long-term capital gains "
                    f"bracket. Selling appreciated securities now and immediately re-buying "
                    "(step-up in basis) locks in a higher cost basis — future gains on "
                    "this amount will NEVER be taxed.\n\n"
                    "Rules: gains must be long-term (held >12 months). Sell before "
                    f"December 31, {self.TAX_YEAR}. No wash-sale rule for gains."
                ),
                category=OpportunityCategory.INVESTMENT,
                priority=OpportunityPriority.HIGH,
                estimated_savings=room_at_0pct * Decimal("0.15"),  # avoiding future 15% LTCG
                action_required=f"Identify long-term appreciated positions. Sell up to ${room_at_0pct:,.0f} gain before year-end.",
                irs_reference="IRC §1(h) / IRS Publication 550",
                deadline=f"December 31, {self.TAX_YEAR}",
                confidence=0.92,
            ))

        # ── Deduction Bunching ───────────────────────────────────────────────
        std_d = self.STANDARD_DEDUCTION.get(profile.filing_status, Decimal("15000"))
        current_itemized_approx = (
            profile.mortgage_interest +
            min(profile.state_local_taxes + profile.property_taxes, self.SALT_CAP) +
            profile.charitable_contributions +
            profile.medical_expenses
        )
        bunching_gap = std_d - current_itemized_approx
        if Decimal("500") < bunching_gap < Decimal("40000"):
            opportunities.append(TaxOpportunity(
                id="multiyear_deduction_bunching",
                title=f"Deduction Bunching — ${bunching_gap:,.0f} Gap to Itemizing",
                description=(
                    f"You're ${bunching_gap:,.0f} below the standard deduction (${std_d:,.0f}). "
                    "Bunching strategy: push 2 years of deductible expenses into 1 year:\n"
                    f"• Pay January {next_year} mortgage payment in December\n"
                    "• Pre-pay January property taxes in December (if allowed by state)\n"
                    f"• Double charitable giving this year (use Donor-Advised Fund)\n"
                    "• Schedule elective medical procedures this year\n\n"
                    "Year 1: itemize (big deduction). Year 2: take standard deduction. "
                    "Net result: more total deductions over 2 years."
                ),
                category=OpportunityCategory.DEDUCTION,
                priority=OpportunityPriority.MEDIUM,
                estimated_savings=bunching_gap * self._marginal_rate(profile),
                action_required=f"Bundle charitable/medical/mortgage expenses before December 31, {self.TAX_YEAR}.",
                irs_reference="IRS Publication 526 / 936",
                deadline=f"December 31, {self.TAX_YEAR}",
                confidence=0.85,
                scenario_ids=["charitable_bunching", "daf_contribution"],
            ))

        # ── NOL Carryforward Application ─────────────────────────────────────
        if profile.has_nol_carryforward and profile.nol_amount > Decimal("10000"):
            nol_savings = self._savings(profile, profile.nol_amount)
            opportunities.append(TaxOpportunity(
                id="multiyear_nol_carryforward",
                title=f"Apply ${profile.nol_amount:,.0f} NOL Carryforward — ${nol_savings:,.0f} Savings",
                description=(
                    f"You have ${profile.nol_amount:,.0f} in Net Operating Loss (NOL) "
                    f"carryforward. Applying it this year saves ${nol_savings:,.0f} in federal tax.\n\n"
                    "TCJA rules (post-2017 NOLs):\n"
                    "• Can only carry forward (no 2-year carryback for most taxpayers)\n"
                    "• Can offset up to 80% of taxable income in any single year\n"
                    "• No expiration for federal NOLs (indefinite carryforward)\n"
                    "• Farm losses: 2-year carryback still available"
                ),
                category=OpportunityCategory.BUSINESS,
                priority=OpportunityPriority.HIGH,
                estimated_savings=nol_savings,
                action_required="Attach NOL carryforward schedule to Form 1040. Use Form 1045 to track.",
                irs_reference="IRC §172 / IRS Publication 536",
                confidence=0.90,
            ))

        # ── Pre-RMD Bracket Management ───────────────────────────────────────
        if profile.age in range(62, 73) and ira_balance > Decimal("100000"):
            opportunities.append(TaxOpportunity(
                id="multiyear_pre_rmd_window",
                title="Pre-RMD Window (Age 62–72) — Reduce Future RMD Tax Bomb",
                description=(
                    f"At age {profile.age}, you are in the pre-RMD window. "
                    f"Your IRA balance (${ira_balance:,.0f}) will generate Required Minimum "
                    "Distributions starting at age 73, potentially pushing you into a higher "
                    "bracket and increasing Medicare IRMAA surcharges.\n\n"
                    "Actions NOW:\n"
                    "• Roth conversions to reduce traditional IRA balance\n"
                    "• Delay Social Security to maximize 0% RMD years\n"
                    "• QCDs (age 70½+) to satisfy RMD with charitable intent\n"
                    "• Consider Roth 401(k) for future contributions (no RMDs)"
                ),
                category=OpportunityCategory.RETIREMENT,
                priority=OpportunityPriority.HIGH,
                action_required="Model RMD projections through age 85. Build Roth conversion plan.",
                irs_reference="IRS Publication 590-B / IRC §401(a)(9)",
                confidence=0.88,
            ))

        return opportunities

    # ── Category → OpportunityCategory mapping ────────────────────────────
    _RULE_CAT_MAP: Dict[RuleCategory, OpportunityCategory] = {
        RuleCategory.INCOME:             OpportunityCategory.INVESTMENT,
        RuleCategory.DEDUCTION:          OpportunityCategory.DEDUCTION,
        RuleCategory.CREDIT:             OpportunityCategory.CREDIT,
        RuleCategory.FILING_STATUS:      OpportunityCategory.FILING_STATUS,
        RuleCategory.SELF_EMPLOYMENT:    OpportunityCategory.BUSINESS,
        RuleCategory.INVESTMENT:         OpportunityCategory.INVESTMENT,
        RuleCategory.RETIREMENT:         OpportunityCategory.RETIREMENT,
        RuleCategory.HEALTHCARE:         OpportunityCategory.HEALTHCARE,
        RuleCategory.EDUCATION:          OpportunityCategory.EDUCATION,
        RuleCategory.REAL_ESTATE:        OpportunityCategory.REAL_ESTATE,
        RuleCategory.BUSINESS:           OpportunityCategory.BUSINESS,
        RuleCategory.CHARITABLE:         OpportunityCategory.DEDUCTION,
        RuleCategory.FAMILY:             OpportunityCategory.DEDUCTION,
        RuleCategory.STATE_TAX:          OpportunityCategory.DEDUCTION,
        RuleCategory.INTERNATIONAL:      OpportunityCategory.INVESTMENT,
        RuleCategory.AMT:                OpportunityCategory.TIMING,
        RuleCategory.PENALTY:            OpportunityCategory.TIMING,
        RuleCategory.TIMING:             OpportunityCategory.TIMING,
        RuleCategory.DOCUMENTATION:      OpportunityCategory.TIMING,
        RuleCategory.VIRTUAL_CURRENCY:   OpportunityCategory.INVESTMENT,
        RuleCategory.HOUSEHOLD_EMPLOYMENT: OpportunityCategory.BUSINESS,
        RuleCategory.K1_TRUST:           OpportunityCategory.INVESTMENT,
        RuleCategory.CASUALTY_LOSS:      OpportunityCategory.DEDUCTION,
        RuleCategory.ALIMONY:            OpportunityCategory.DEDUCTION,
    }

    # ── Severity → OpportunityPriority mapping ────────────────────────────
    _RULE_SEV_MAP: Dict[RuleSeverity, OpportunityPriority] = {
        RuleSeverity.CRITICAL: OpportunityPriority.HIGH,
        RuleSeverity.HIGH:     OpportunityPriority.HIGH,
        RuleSeverity.MEDIUM:   OpportunityPriority.MEDIUM,
        RuleSeverity.LOW:      OpportunityPriority.LOW,
        RuleSeverity.INFO:     OpportunityPriority.LOW,
    }

    def _detect_via_rules_engine(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """
        Wire the comprehensive TaxRulesEngine (880+ rules) directly into the
        opportunity pipeline.

        Each eligible TaxRule becomes a TaxOpportunity. Savings are estimated
        from the rule's threshold/limit/rate fields combined with the taxpayer's
        real marginal rate, so every figure is bracket-accurate.
        """
        opportunities: List[TaxOpportunity] = []

        # Derive flags the engine needs from the profile
        agi = float(profile.agi_estimate)
        has_se = (profile.self_employment_income > Decimal("400") or
                  profile.has_business or profile.is_gig_worker)
        has_investments = (profile.capital_gains > Decimal("0") or
                           profile.dividend_income > Decimal("0") or
                           profile.crypto_gains > Decimal("0") or
                           profile.k1_income > Decimal("0"))
        has_children = (profile.has_children_under_17 or
                        profile.has_children_under_13 or
                        profile.num_dependents > 0)
        std = float(self.STANDARD_DEDUCTION.get(profile.filing_status, Decimal("15000")))
        salt = min(float(profile.state_local_taxes + profile.property_taxes), 10000.0)
        itemized = float(profile.mortgage_interest) + salt + float(profile.charitable_contributions) + float(profile.medical_expenses)
        itemizes = itemized > std
        high_income = agi > 200_000

        engine = _get_rules_engine(self.TAX_YEAR)
        applicable = engine.get_applicable_rules(
            filing_status=profile.filing_status,
            has_self_employment=has_se,
            has_investments=has_investments,
            has_children=has_children,
            itemizes=itemizes,
            high_income=high_income,
        )

        # Profile-aware pruning: drop rule categories where the profile has
        # no matching situation. This reduces 800+ rules to a focused set
        # without modifying the rules engine itself.
        # Only prune on hard negatives — we keep "aspirational" categories
        # (e.g. BUSINESS for a W2 worker who might want to start one).
        skip_categories: set = set()
        has_rental = profile.rental_income > Decimal("0")
        has_foreign = profile.foreign_income > Decimal("0")
        has_crypto = profile.crypto_gains > Decimal("0") or profile.crypto_losses > Decimal("0")
        has_k1 = profile.k1_income > Decimal("0")
        has_alimony = profile.alimony_received > Decimal("0") or profile.alimony_paid > Decimal("0")
        has_household_emp = profile.has_household_employee

        if not has_foreign:
            skip_categories.add(RuleCategory.INTERNATIONAL)
        if not has_crypto:
            skip_categories.add(RuleCategory.VIRTUAL_CURRENCY)
        if not (has_k1 or profile.has_company_stock_in_401k):
            skip_categories.add(RuleCategory.K1_TRUST)
        if not has_alimony:
            skip_categories.add(RuleCategory.ALIMONY)
        if not has_household_emp:
            skip_categories.add(RuleCategory.HOUSEHOLD_EMPLOYMENT)
        if not has_rental and not profile.owns_home:
            skip_categories.add(RuleCategory.REAL_ESTATE)

        if skip_categories:
            applicable = [r for r in applicable if r.category not in skip_categories]

        marginal = self._marginal_rate(profile)
        # Cap rule-derived deductibles to a realistic slice of AGI so maximum
        # rule limits (e.g. $10M QSBS, $1.25M §179) don't produce absurd numbers.
        agi_decimal = profile.agi_estimate if profile.agi_estimate > Decimal("0") else Decimal("50000")
        _max_deductible = min(agi_decimal, Decimal("100000"))

        import re as _re

        for rule in applicable:
            # ── Estimate savings ────────────────────────────────────────────
            savings: Optional[Decimal] = None
            if rule.potential_savings:
                nums = _re.findall(r"\d+", rule.potential_savings.replace(",", ""))
                if nums:
                    try:
                        savings = Decimal(nums[0]) * marginal
                    except Exception:
                        savings = None

            if savings is None:
                # Use threshold / limit from the rule as the deductible amount
                deductible_amount: Optional[Decimal] = None
                if rule.thresholds_by_status:
                    tval = rule.thresholds_by_status.get(profile.filing_status)
                    if tval is None:
                        fs_map = {
                            "married_filing_jointly": "married_joint",
                            "married_filing_separately": "married_separate",
                            "head_of_household": "head_of_household",
                            "single": "single",
                        }
                        tval = rule.thresholds_by_status.get(fs_map.get(profile.filing_status, ""))
                    if tval:
                        deductible_amount = Decimal(str(tval))
                elif rule.limit is not None:
                    deductible_amount = Decimal(str(rule.limit))
                elif rule.threshold is not None:
                    deductible_amount = Decimal(str(rule.threshold))

                if deductible_amount and deductible_amount > Decimal("0"):
                    # Cap to realistic taxpayer scale
                    deductible_amount = min(deductible_amount, _max_deductible)
                    if rule.rate is not None:
                        savings = deductible_amount * Decimal(str(rule.rate))
                    elif rule.category in (RuleCategory.CREDIT, RuleCategory.PENALTY):
                        savings = deductible_amount
                    else:
                        savings = self._savings(profile, deductible_amount)

            # ── Build action text ────────────────────────────────────────────
            action = rule.recommendation or (
                f"Review {rule.irs_reference} and apply rule {rule.rule_id} "
                "to your current situation."
            )

            # ── Map categories / severity ────────────────────────────────────
            opp_cat = self._RULE_CAT_MAP.get(rule.category, OpportunityCategory.TIMING)
            opp_pri = self._RULE_SEV_MAP.get(rule.severity, OpportunityPriority.MEDIUM)

            # Skip pure INFO-level documentation rules with no monetary impact
            if rule.severity == RuleSeverity.INFO and savings is None:
                continue

            opportunities.append(TaxOpportunity(
                id=f"re_{rule.rule_id.lower()}",
                title=rule.name,
                description=rule.description,
                category=opp_cat,
                priority=opp_pri,
                estimated_savings=savings,
                action_required=action,
                irs_reference=rule.irs_reference,
                confidence=0.85 if rule.severity in (RuleSeverity.CRITICAL, RuleSeverity.HIGH) else 0.75,
            ))

        return opportunities

    def _ai_detect_opportunities(self, profile: TaxpayerProfile) -> List[TaxOpportunity]:
        """
        AI-powered deep analysis that covers the full US tax code.

        Strategy:
        - Passes ALL 80+ profile fields to the AI (not just 12)
        - Runs 3 specialized passes: broad scan, edge cases, state/penalty
        - Deduplicates against rule-based IDs already generated
        - Targets 15-20 NEW opportunities per run beyond the rule-based set
        """
        opportunities = []

        if not self._ai_available:
            return opportunities

        extraction_schema = {
            "type": "object",
            "properties": {
                "opportunities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id":          {"type": "string"},
                            "title":       {"type": "string"},
                            "description": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": ["deduction", "credit", "retirement", "business",
                                         "education", "healthcare", "real_estate",
                                         "investment", "timing", "filing_status"]
                            },
                            "priority":              {"type": "string", "enum": ["high", "medium", "low"]},
                            "estimated_savings_min": {"type": "number"},
                            "estimated_savings_max": {"type": "number"},
                            "action_required":       {"type": "string"},
                            "irs_reference":         {"type": "string"},
                            "deadline":              {"type": "string"},
                            "confidence":            {"type": "number", "minimum": 0, "maximum": 1}
                        },
                        "required": ["id", "title", "description", "category", "priority", "action_required"]
                    }
                }
            },
            "required": ["opportunities"]
        }

        def _build_full_profile_block() -> str:
            """Serialize the complete TaxpayerProfile for the AI prompt."""
            p = profile
            return f"""
TAX YEAR: {self.TAX_YEAR}
FILING STATUS: {p.filing_status}
AGE: {p.age}  |  SPOUSE AGE: {p.spouse_age or 'N/A'}

── INCOME ──────────────────────────────────────────────────
W-2 wages:               ${p.w2_wages:>12,.0f}
Self-employment:         ${p.self_employment_income:>12,.0f}
Business income (K-1):   ${p.business_income:>12,.0f}
K-1 pass-through:        ${p.k1_income:>12,.0f}
Interest:                ${p.interest_income:>12,.0f}
Dividends (total):       ${p.dividend_income:>12,.0f}
  Qualified dividends:   ${p.qualified_dividends:>12,.0f}
Capital gains (gross):   ${p.capital_gains:>12,.0f}
  Short-term gains:      ${p.short_term_gains:>12,.0f}
  Long-term gains:       ${p.long_term_gains:>12,.0f}
Rental income:           ${p.rental_income:>12,.0f}
Social Security:         ${p.social_security_income:>12,.0f}
Pension/annuity:         ${p.pension_income:>12,.0f}
RMD amount:              ${p.rmd_amount:>12,.0f}
Crypto gains:            ${p.crypto_gains:>12,.0f}
Crypto losses:           ${p.crypto_losses:>12,.0f}
Unemployment:            ${p.unemployment_income:>12,.0f}
Alimony received:        ${p.alimony_received:>12,.0f}
Gambling winnings:       ${p.gambling_winnings:>12,.0f}
Gambling losses:         ${p.gambling_losses:>12,.0f}
Foreign income:          ${p.foreign_income:>12,.0f}
Hobby income:            ${p.hobby_income:>12,.0f}
Other income:            ${p.other_income:>12,.0f}
TOTAL INCOME:            ${p.total_income:>12,.0f}
ESTIMATED AGI:           ${p.agi_estimate:>12,.0f}
Federal withheld:        ${p.federal_withheld:>12,.0f}
ES payments YTD:         ${p.es_payments_ytd:>12,.0f}

── DEDUCTIONS ALREADY CLAIMED ───────────────────────────────
Traditional 401(k):      ${p.traditional_401k:>12,.0f}
Roth 401(k):             ${p.roth_401k:>12,.0f}
Traditional IRA:         ${p.traditional_ira:>12,.0f}
Roth IRA:                ${p.roth_ira:>12,.0f}
HSA contribution:        ${p.hsa_contribution:>12,.0f}
SEP-IRA contribution:    ${p.sep_ira_contribution:>12,.0f}
Solo 401(k):             ${p.solo_401k_contribution:>12,.0f}
SE health insurance:     ${p.se_health_insurance:>12,.0f}
Student loan interest:   ${p.student_loan_interest:>12,.0f}
Alimony paid:            ${p.alimony_paid:>12,.0f}
Mortgage interest:       ${p.mortgage_interest:>12,.0f}
Property taxes:          ${p.property_taxes:>12,.0f}
State/local taxes:       ${p.state_local_taxes:>12,.0f}
Charitable contributions:${p.charitable_contributions:>12,.0f}
Medical expenses:        ${p.medical_expenses:>12,.0f}
Educator expenses:       ${p.educator_expenses:>12,.0f}
Foreign taxes paid:      ${p.foreign_taxes_paid:>12,.0f}
LTC premiums paid:       ${p.ltc_premiums_paid:>12,.0f}

── BALANCES / CARRYFORWARDS ─────────────────────────────────
IRA balance:             ${p.ira_balance:>12,.0f}
Roth IRA balance:        ${p.roth_ira_balance:>12,.0f}
Passive loss carryfwd:   ${p.passive_losses_carryforward:>12,.0f}
NOL amount:              ${p.nol_amount:>12,.0f}  (has_nol={p.has_nol_carryforward})
OZ gain deferred:        ${p.opportunity_zone_gain_deferred:>12,.0f}
Inherited IRA balance:   ${p.inherited_ira_balance:>12,.0f}

── FAMILY / HOUSEHOLD ───────────────────────────────────────
Dependents: {p.num_dependents}
Children under 17: {p.has_children_under_17}  |  Under 13: {p.has_children_under_13}
College students: {p.has_college_students}
Dependent care expenses: ${p.dependent_care_expenses:>12,.0f}
Has dep. care FSA: {p.has_dependent_care_fsa}  FSA amt: ${p.dependent_care_fsa_amount:,.0f}
Household employee: {p.has_household_employee}  Wages: ${p.household_employee_wages:,.0f}

── HOME / REAL ESTATE ───────────────────────────────────────
Owns home: {p.owns_home}  |  Purchased year: {p.home_purchase_year or 'N/A'}
Has home office: {p.has_home_office}
Rental active participation: {p.rental_active_participation}
Is real estate professional: {p.is_real_estate_professional}
STR rental days: {p.str_rental_days}  |  STR personal use days: {p.str_personal_days}

── BUSINESS / SELF-EMPLOYMENT ───────────────────────────────
Has business: {p.has_business}  |  Type: {p.business_type or 'N/A'}
Is SSTB: {p.is_sstb}  |  Business net income: ${p.business_net_income:,.0f}
Is gig worker: {p.is_gig_worker}
Vehicle business miles: {p.vehicle_business_miles:,}  |  Personal miles: {p.vehicle_personal_miles:,}

── HEALTH ───────────────────────────────────────────────────
Has HDHP: {p.has_hdhp}
Has LTC insurance: {p.has_long_term_care_insurance}
FBAR requirement: {p.has_fbar_requirement}

── EQUITY COMPENSATION ──────────────────────────────────────
Has ISO options: {p.has_iso_options}  ISO exercised: ${p.iso_exercises_ytd:,.0f}
Has NSO options: {p.has_nso_options}
Has RSU: {p.has_rsu}  RSU vested value: ${p.rsu_vested_value:,.0f}
Has ESPP: {p.has_espp}  ESPP income: ${p.espp_income:,.0f}
Company stock in 401k (NUA): {p.has_company_stock_in_401k}

── INVESTMENTS / SPECIAL ────────────────────────────────────
Donor advised fund: {p.has_donor_advised_fund}
Appreciated stock held: {p.appreciated_stock_held}
Has 529 plan: {p.has_529_plan}  529 contributions: ${p.plan_529_contributions:,.0f}
Has EV purchase: {p.has_ev_purchase}  EV price: ${p.ev_purchase_price:,.0f}
Has solar: {p.has_solar}  Solar cost: ${p.solar_cost:,.0f}
Home energy improvements: {p.has_home_energy_improvements}
QOZ investment: {p.has_opportunity_zone_investment}
QSBS/ISO/startup stock: {p.has_iso_options or p.has_nso_options}
Inherited IRA: {p.has_inherited_ira}
COD income: {p.has_cod_income}  COD amount: ${p.cod_amount:,.0f}  Insolvent: {p.is_insolvent}

── LIFE EVENTS ──────────────────────────────────────────────
Got married: {p.got_married}  |  Got divorced: {p.got_divorced}
Had baby: {p.had_baby}  |  Spouse died: {p.spouse_died}
Bought home: {p.bought_home}  |  Started business: {p.started_business}
Changed jobs: {p.changed_jobs}  |  Retired this year: {p.retired_this_year}

── STATE ─────────────────────────────────────────────────────
State: {p.state or 'Unknown'}
"""

        def _parse_ai_response(result: dict, id_prefix: str, existing_ids: set) -> List[TaxOpportunity]:
            """Convert raw AI JSON into TaxOpportunity objects, deduplicating."""
            parsed = []
            for opp_data in result.get("opportunities", []):
                raw_id = opp_data.get("id", "")
                opp_id = f"ai_{id_prefix}_{raw_id or hash(opp_data['title']) % 100000}"
                # Skip if AI generated a duplicate of a rule-based ID
                if opp_id in existing_ids or raw_id in existing_ids:
                    continue

                savings = None
                savings_range = None
                s_min = opp_data.get("estimated_savings_min")
                s_max = opp_data.get("estimated_savings_max")
                if s_min and s_max:
                    savings_range = (Decimal(str(s_min)), Decimal(str(s_max)))
                    savings = (savings_range[0] + savings_range[1]) / 2
                elif s_min:
                    savings = Decimal(str(s_min))

                try:
                    parsed.append(TaxOpportunity(
                        id=opp_id,
                        title=opp_data["title"],
                        description=opp_data["description"],
                        category=OpportunityCategory(opp_data.get("category", "deduction")),
                        priority=OpportunityPriority(opp_data.get("priority", "medium")),
                        estimated_savings=savings,
                        savings_range=savings_range,
                        action_required=opp_data.get("action_required", "Consult a tax professional."),
                        irs_reference=opp_data.get("irs_reference"),
                        deadline=opp_data.get("deadline"),
                        confidence=float(opp_data.get("confidence", 0.72)),
                    ))
                    existing_ids.add(opp_id)
                except (KeyError, ValueError):
                    continue
            return parsed

        profile_block = _build_full_profile_block()
        existing_rule_ids: set = set()  # populated below before AI calls
        ai = self._injected_ai_service or get_ai_service()

        # ── IRS Publication Context (RAG) — per-profile queries ────────────────
        agi = float(profile.agi_estimate)
        state = profile.state or ""
        rag = self._irs_rag

        def _irs_ctx(*queries: str) -> str:
            """Retrieve IRS guidance for a set of queries and format for prompt."""
            ctx = rag.format_multi(list(queries), top_k_per_query=2)
            return ("\n" + ctx + "\n") if ctx else ""

        # ── PASS 1: Broad deep scan — find the top 20 unique opportunities ────
        pass1_prompt = f"""You are a senior US CPA and EA with 30 years of experience preparing complex individual
federal and state tax returns. Your task is to identify SPECIFIC, ACTIONABLE tax-saving
opportunities for this taxpayer that are NOT obvious and that rule-based software commonly misses.

{profile_block}
{_irs_ctx(
    "standard deduction itemized deduction 2025",
    "ira 401k contribution limit 2025",
    "capital gains rates 2025",
    "NIIT net investment income tax",
    "SALT deduction cap",
)}
INSTRUCTIONS:
1. Return 15–20 distinct opportunities covering deductions, credits, retirement, investments,
   business strategies, and timing moves.
2. Each must cite a specific IRS code section, publication, or form number (irs_reference).
3. Each must have a concrete estimated_savings_min and estimated_savings_max in dollars.
4. The `id` field must be a unique snake_case identifier (e.g. "medical_mileage_deduction").
5. Do NOT include generic advice like "consult a CPA" as an opportunity.
6. Focus on 2025 tax year rules (TCJA, SECURE 2.0, IRA/IPA 2022).
7. Cover edge cases: AMT exposure, phase-out cliffs, basis step-up, recapture, state conformity.
8. Highlight any URGENT year-end or April-15 actions.

Return valid JSON matching the schema exactly.
"""

        # ── PASS 2: Specialized scan for life events + multi-year planning ────
        pass2_prompt = f"""You are a US tax strategist specializing in multi-year planning and life-event tax impacts.

{profile_block}
{_irs_ctx(
    "Roth conversion bracket fill",
    "RMD required minimum distribution",
    "LTCG 0% rate harvest window",
    "NOL net operating loss carryforward",
    "Medicare IRMAA surcharge",
)}
INSTRUCTIONS:
1. Return 8–12 MULTI-YEAR and LIFE-EVENT driven opportunities not covered by a single-year scan.
   Examples: Roth conversion ladder, bracket-filling strategy over retirement years,
   inherited IRA 10-year distribution optimization, basis harvesting, NOL timing,
   divorce/death-of-spouse filing status change impacts, year-of-death RMD rules,
   529 account re-contribution after refund, 5-year Roth aging rules.
2. Each must have a unique snake_case `id` (prefix with "multi_").
3. Include estimated_savings_min and estimated_savings_max over the planning horizon.
4. Cite IRS references.

Return valid JSON matching the schema exactly.
"""

        # ── PASS 3: Compliance risks that represent hidden savings ─────────────
        pass3_prompt = f"""You are a US tax compliance expert. Review this taxpayer profile and identify
COMPLIANCE RISKS and MISSED FILINGS that could cause penalties if ignored — AND where
correcting them could also unlock refunds or avoid future costs.

{profile_block}
{_irs_ctx(
    "wash sale rule capital loss",
    "passive activity loss rental",
    "AMT alternative minimum tax",
    "self-employment SE tax FICA",
)}
INSTRUCTIONS:
1. Return 5–8 compliance risk items (prefix `id` with "compliance_").
2. Examples: basis tracking for stock/crypto, wash-sale violations, passive activity
   grouping elections, at-risk limitation (Form 6198), self-rental rules, S-Corp
   reasonable salary IRS scrutiny, 1099 filing obligations, depreciation recapture
   on rental sale, PFIC reporting, Form 3115 accounting method change.
3. Frame each as: "if you don't address this, you face X risk AND miss Y opportunity."
4. Include estimated dollar impact (savings or avoided penalty) as estimated_savings_min/max.
5. Cite IRS form/publication.

Return valid JSON matching the schema exactly.
"""

        # ── PASS 4: Retirement specialist ──────────────────────────────────────
        pass4_prompt = f"""You are a US retirement tax specialist (CPA/CFP).

{profile_block}
{_irs_ctx(
    "traditional IRA contribution deduction limit",
    "Roth IRA contribution phase-out",
    "SEP IRA self-employed contribution",
    "solo 401k self-employed",
    "RMD required minimum distribution age 73",
    "Roth conversion taxable income",
)}
Focus ONLY on retirement-related tax opportunities. Return 6–10 unique items (prefix id with "ret_"):
- Roth conversion ladder opportunity and optimal bracket-fill amount
- QCD (Qualified Charitable Distribution) from IRA if age 70½+
- Still-working exception to RMD
- 72(t) SEPP if early access needed without 10% penalty
- Net Unrealized Appreciation (NUA) for employer stock in 401(k)
- SECURE 2.0: starter 401(k), auto-enrollment, employer match on student loans
- 10-year inherited IRA distribution optimization
- Solo 401(k) vs SEP-IRA comparison for self-employed
- Backdoor Roth or Mega Backdoor Roth if income-limited
- Roth five-year aging rule implications

Return valid JSON matching the schema exactly."""

        # ── PASS 5: Business/SE specialist ────────────────────────────────────
        pass5_prompt = f"""You are a US small business and self-employment tax specialist.

{profile_block}
{_irs_ctx(
    "QBI 199A qualified business income deduction",
    "section 179 bonus depreciation",
    "home office business use",
    "vehicle mileage business",
    "self-employment SE tax deduction",
)}
Focus ONLY on business and self-employment tax opportunities. Return 6–10 unique items (prefix id with "biz_"):
- S-Corp election timing and reasonable salary optimization
- Home office deduction (regular/simplified method comparison)
- Section 179 and bonus depreciation on business assets
- Augusta Rule (IRC §280A(g)) — 14-day home rental to own business
- Qualified Business Income (QBI) deduction optimization and SSTB rules
- Business entity structure optimization (sole prop → LLC → S-Corp)
- Hire family members (children, spouse) — FICA savings
- Accountable plan for reimbursed expenses
- Vehicle: actual expense vs standard mileage, luxury auto limits
- De minimis safe harbor elections and capitalization policy

Return valid JSON matching the schema exactly."""

        # ── PASS 6: Investment specialist ─────────────────────────────────────
        pass6_prompt = f"""You are a US investment and capital gains tax specialist.

{profile_block}
{_irs_ctx(
    "long-term capital gains rates 0% 15% 20%",
    "NIIT net investment income tax 3.8%",
    "wash sale rule loss disallowance",
    "donor advised fund appreciated stock",
    "charitable contribution deduction limit",
    "opportunity zone QOZ capital gains deferral",
)}
Focus ONLY on investment tax opportunities. Return 6–10 unique items (prefix id with "inv_"):
- Tax-loss harvesting opportunities (wash-sale safe harbor timing)
- 0% LTCG bracket filling (realize gains at 0% rate)
- Short-term → long-term conversion (hold >12 months)
- Opportunity Zone (QOZ) deferral for recent large capital gains
- QSBS §1202 exclusion (gain up to $10M tax-free on qualifying small business stock)
- Crypto specific-identification lot accounting to minimize gains
- Installment sale strategy for large asset dispositions
- Depreciation recapture planning for rental sale (unrecaptured §1250 at 25%)
- Donor-Advised Fund with appreciated securities (avoid capital gains + get deduction)
- Net Investment Income Tax (NIIT) 3.8% planning — threshold management

Return valid JSON matching the schema exactly."""

        # ── PASS 7: State tax specialist ──────────────────────────────────────
        pass7_prompt = f"""You are a US state and local tax (SALT) specialist.

{profile_block}
{_irs_ctx(
    "SALT state local tax deduction cap 10000",
    "529 plan state deduction",
    "rental income state deduction",
) if state else ""}
Focus ONLY on state tax opportunities. Return 4–8 unique items (prefix id with "state_"):
- PTET (Pass-Through Entity Tax) election if taxpayer has partnership/S-Corp K-1 income — workaround to $10K SALT cap
- 529 plan state deduction (if state permits — list the state's deduction limit)
- State-specific retirement income exclusions (pensions, SS, military pay)
- Residency change planning: partial-year resident issues, domicile establishment
- No-income-tax state advantages (TX, FL, WA, NV, TN, SD, WY) if applicable
- Community property state implications for MFS filers
- State AMT where applicable (CA, NY)
- Remote worker nexus issues — multiple state returns required?

Return valid JSON matching the schema exactly."""

        # ── Run all 7 passes CONCURRENTLY via asyncio.gather ─────────────────
        # Sequential execution took ~60s; concurrent takes ~10s (slowest pass).
        all_passes = [
            (pass1_prompt,  "deep",       "Broad deep scan"),
            (pass2_prompt,  "multi",      "Multi-year planning"),
            (pass3_prompt,  "compliance", "Compliance risks"),
            (pass4_prompt,  "ret",        "Retirement specialist"),
            (pass5_prompt,  "biz",        "Business/SE specialist"),
            (pass6_prompt,  "inv",        "Investment specialist"),
            (pass7_prompt,  "state",      "State tax specialist"),
        ]

        async def _run_pass_async(prompt: str, id_prefix: str, label: str, pass_num: int) -> List[TaxOpportunity]:
            try:
                result = await ai.extract(prompt, extraction_schema)
                new_opps = _parse_ai_response(result, id_prefix, set(existing_rule_ids))
                logger.info(
                    "AI pass %d (%s) completed — %d new opportunities",
                    pass_num, label, len(new_opps),
                    extra={"service": "opportunity_detector"},
                )
                return new_opps
            except Exception as e:
                logger.warning(
                    "AI pass %d (%s) failed — continuing with other passes",
                    pass_num, label,
                    extra={"service": "opportunity_detector", "reason": str(e)},
                )
                return []

        async def _gather_all_passes() -> List[TaxOpportunity]:
            tasks = [
                _run_pass_async(prompt, prefix, label, i)
                for i, (prompt, prefix, label) in enumerate(all_passes, 1)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            combined: List[TaxOpportunity] = []
            for r in results:
                if isinstance(r, list):
                    combined.extend(r)
            return combined

        opportunities.extend(run_async(_gather_all_passes()))
        return opportunities

    def get_opportunity_summary(self, opportunities: List[TaxOpportunity]) -> Dict[str, Any]:
        """Get summary of detected opportunities."""
        total_savings = Decimal("0")
        min_savings = Decimal("0")
        max_savings = Decimal("0")

        by_category = {}
        by_priority = {"high": [], "medium": [], "low": []}

        for opp in opportunities:
            # Aggregate savings
            if opp.estimated_savings:
                total_savings += opp.estimated_savings
            if opp.savings_range:
                min_savings += opp.savings_range[0]
                max_savings += opp.savings_range[1]

            # Group by category
            cat = opp.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(opp.title)

            # Group by priority
            by_priority[opp.priority.value].append(opp.title)

        return {
            "total_opportunities": len(opportunities),
            "estimated_total_savings": float(total_savings),
            "savings_range": {
                "min": float(min_savings),
                "max": float(max_savings)
            },
            "high_priority_count": len(by_priority["high"]),
            "by_category": by_category,
            "by_priority": by_priority,
            "top_opportunities": [
                {"title": o.title, "savings": float(o.estimated_savings or 0)}
                for o in opportunities[:5]
            ]
        }

    def format_opportunities_for_chat(self, opportunities: List[TaxOpportunity], limit: int = 5) -> str:
        """Format opportunities for display in chat interface."""
        if not opportunities:
            return "No specific tax-saving opportunities identified based on your current information."

        lines = ["**💰 Tax-Saving Opportunities Detected:**\n"]

        # Show top opportunities
        for i, opp in enumerate(opportunities[:limit], 1):
            priority_emoji = "🔴" if opp.priority == OpportunityPriority.HIGH else "🟡" if opp.priority == OpportunityPriority.MEDIUM else "🟢"

            savings_str = ""
            if opp.estimated_savings:
                savings_str = f" (Est. savings: ${opp.estimated_savings:,.0f})"
            elif opp.savings_range:
                savings_str = f" (Est. savings: ${opp.savings_range[0]:,.0f}-${opp.savings_range[1]:,.0f})"

            lines.append(f"{i}. {priority_emoji} **{opp.title}**{savings_str}")
            lines.append(f"   {opp.description[:150]}...")
            lines.append(f"   → Action: {opp.action_required}")
            lines.append("")

        if len(opportunities) > limit:
            lines.append(f"*...and {len(opportunities) - limit} more opportunities identified.*")

        return "\n".join(lines)


def create_profile_from_tax_return(tax_return) -> TaxpayerProfile:
    """Create a TaxpayerProfile from a TaxReturn object."""
    profile = TaxpayerProfile()

    # Filing status
    if tax_return.taxpayer and tax_return.taxpayer.filing_status:
        profile.filing_status = tax_return.taxpayer.filing_status.value

    # Age
    if hasattr(tax_return.taxpayer, 'date_of_birth') and tax_return.taxpayer.date_of_birth:
        try:
            birth_date = datetime.strptime(str(tax_return.taxpayer.date_of_birth), "%Y-%m-%d")
            profile.age = (datetime.now() - birth_date).days // 365
        except (ValueError, TypeError):
            pass

    # Income from W-2s
    if tax_return.income and tax_return.income.w2_forms:
        for w2 in tax_return.income.w2_forms:
            profile.w2_wages += Decimal(str(w2.wages or 0))
            profile.federal_withheld += Decimal(str(w2.federal_tax_withheld or 0))

    # Other income
    if tax_return.income:
        profile.self_employment_income = Decimal(str(tax_return.income.self_employment_income or 0))
        profile.business_income = Decimal(str(tax_return.income.business_income or 0))
        profile.interest_income = Decimal(str(tax_return.income.interest_income or 0))
        profile.dividend_income = Decimal(str(tax_return.income.dividend_income or 0))
        profile.capital_gains = Decimal(str(tax_return.income.capital_gains or 0))
        profile.rental_income = Decimal(str(tax_return.income.rental_income or 0))
        profile.other_income = Decimal(str(tax_return.income.other_income or 0))

    # Deductions
    if tax_return.deductions:
        profile.mortgage_interest = Decimal(str(tax_return.deductions.mortgage_interest or 0))
        profile.property_taxes = Decimal(str(tax_return.deductions.property_tax or 0))
        profile.state_local_taxes = Decimal(str(tax_return.deductions.state_local_tax or 0))
        profile.charitable_contributions = Decimal(str(tax_return.deductions.charitable_contributions or 0))
        profile.student_loan_interest = Decimal(str(tax_return.deductions.student_loan_interest or 0))
        profile.hsa_contribution = Decimal(str(tax_return.deductions.hsa_contribution or 0))
        profile.traditional_401k = Decimal(str(tax_return.deductions.retirement_401k or 0))
        profile.traditional_ira = Decimal(str(tax_return.deductions.traditional_ira or 0))

    # Dependents
    if tax_return.taxpayer and hasattr(tax_return.taxpayer, 'dependents') and tax_return.taxpayer.dependents:
        profile.num_dependents = len(tax_return.taxpayer.dependents)
        for dep in tax_return.taxpayer.dependents:
            if hasattr(dep, 'birth_date') and dep.birth_date:
                try:
                    birth_date = datetime.strptime(str(dep.birth_date), "%Y-%m-%d")
                    age = (datetime.now() - birth_date).days // 365
                    if age < 17:
                        profile.has_children_under_17 = True
                    if age < 13:
                        profile.has_children_under_13 = True
                except (ValueError, TypeError):
                    pass

    # Home ownership
    profile.owns_home = profile.mortgage_interest > 0 or profile.property_taxes > 0

    # Business
    profile.has_business = profile.self_employment_income > 0 or profile.business_income > 0
    profile.business_net_income = profile.self_employment_income + profile.business_income

    return profile


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_tax_opportunity_detector() -> TaxOpportunityDetector:
    """Return the singleton TaxOpportunityDetector for production use.

    Use this instead of TaxOpportunityDetector() in API handlers to avoid
    re-creating FederalTaxEngine / StateTaxEngine on every request.
    """
    return TaxOpportunityDetector()
