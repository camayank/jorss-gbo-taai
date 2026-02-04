"""
Form 6251 - Alternative Minimum Tax - Individuals

Implements IRS Form 6251 per IRC Sections 55-59 for calculating the
Alternative Minimum Tax (AMT).

Key Concepts:
- AMT is a parallel tax system designed to ensure high-income taxpayers
  pay a minimum amount of tax regardless of deductions and credits
- Tentative Minimum Tax (TMT) = (AMTI - Exemption) × AMT rates
- AMT = max(0, TMT - Regular Tax)
- AMT exemption phases out at 25 cents per dollar over threshold

AMT Rates (2025):
- 26% on first $232,600 of AMT taxable income ($116,300 if MFS)
- 28% on amounts over the threshold

Exemption Amounts (2025):
- Single: $88,100 (phases out at $626,350)
- MFJ/QW: $137,000 (phases out at $1,252,700)
- MFS: $68,500 (phases out at $626,350)
- HOH: $88,100 (phases out at $626,350)

IRC References:
- Section 55: Alternative minimum tax imposed
- Section 56: Adjustments in computing AMTI
- Section 57: Items of tax preference
- Section 58: Denial of certain losses
- Section 59: Other definitions and special rules
"""

from typing import Optional, List, Dict, ClassVar
from pydantic import BaseModel, Field
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class AMTAdjustmentType(str, Enum):
    """Types of AMT adjustments per Form 6251 Part I."""
    # Line 2a - Taxes (SALT deduction add-back)
    TAXES_SALT = "taxes_salt"

    # Line 2b - Tax refund (if reported as income, adjust)
    TAX_REFUND = "tax_refund"

    # Line 2c - Investment interest expense
    INVESTMENT_INTEREST = "investment_interest"

    # Line 2d - Depletion
    DEPLETION = "depletion"

    # Line 2e - Net operating loss deduction
    NOL_DEDUCTION = "nol_deduction"

    # Line 2f - Alternative tax net operating loss deduction
    ATNOL_DEDUCTION = "atnol_deduction"

    # Line 2g - Interest from specified private activity bonds
    PRIVATE_ACTIVITY_BOND_INTEREST = "private_activity_bond_interest"

    # Line 2h - Qualified small business stock (Section 1202)
    QSBS_EXCLUSION = "qsbs_exclusion"

    # Line 2i - Incentive stock options
    ISO_EXERCISE = "iso_exercise"

    # Line 2j - Estates and trusts
    ESTATES_TRUSTS = "estates_trusts"

    # Line 2k - Disposition of property
    PROPERTY_DISPOSITION = "property_disposition"

    # Line 2l - Depreciation
    DEPRECIATION = "depreciation"

    # Line 2m - Passive activities
    PASSIVE_ACTIVITIES = "passive_activities"

    # Line 2n - Loss limitations
    LOSS_LIMITATIONS = "loss_limitations"

    # Line 2o - Circulation costs
    CIRCULATION_COSTS = "circulation_costs"

    # Line 2p - Long-term contracts
    LONG_TERM_CONTRACTS = "long_term_contracts"

    # Line 2q - Mining costs
    MINING_COSTS = "mining_costs"

    # Line 2r - Research and experimental costs
    RESEARCH_EXPERIMENTAL = "research_experimental"

    # Line 2s - Section 1202 exclusion
    SECTION_1202_EXCLUSION = "section_1202_exclusion"

    # Line 2t - Section 1291 PFIC
    SECTION_1291_PFIC = "section_1291_pfic"

    # Line 2u - Section 965 inclusion
    SECTION_965 = "section_965"

    # Line 2v - Section 250 deduction
    SECTION_250_DEDUCTION = "section_250_deduction"

    # Line 3 - Other adjustments
    OTHER = "other"


class AMTPreferenceType(str, Enum):
    """Tax preference items under Section 57."""
    # Excess depletion (cost depletion vs percentage depletion)
    EXCESS_DEPLETION = "excess_depletion"

    # Intangible drilling costs
    INTANGIBLE_DRILLING_COSTS = "intangible_drilling_costs"

    # Tax-exempt interest from private activity bonds
    TAX_EXEMPT_PAB_INTEREST = "tax_exempt_pab_interest"

    # Accelerated depreciation on real property (pre-1987)
    ACCELERATED_DEPRECIATION_REAL = "accelerated_depreciation_real"

    # Accelerated depreciation on personal property (pre-1987)
    ACCELERATED_DEPRECIATION_PERSONAL = "accelerated_depreciation_personal"


class AMTAdjustment(BaseModel):
    """Individual AMT adjustment item."""
    adjustment_type: AMTAdjustmentType = Field(description="Type of adjustment")
    description: str = Field(default="", description="Description of adjustment")
    amount: float = Field(default=0.0, description="Adjustment amount (positive adds to AMTI)")
    form_6251_line: str = Field(default="", description="Corresponding Form 6251 line")


class ISOExercise(BaseModel):
    """
    Incentive Stock Option (ISO) exercise details.

    The AMT adjustment is the "spread" - difference between
    fair market value and exercise price at exercise.
    """
    company_name: str = Field(description="Company name")
    exercise_date: str = Field(description="Date of exercise")
    shares_exercised: int = Field(ge=0, description="Number of shares exercised")
    exercise_price_per_share: float = Field(ge=0, description="Exercise price per share")
    fmv_per_share_at_exercise: float = Field(ge=0, description="FMV per share at exercise")

    # If shares were sold in same year (disqualifying disposition)
    same_year_sale: bool = Field(default=False, description="Sold in same calendar year")
    sale_price_per_share: Optional[float] = Field(
        default=None, ge=0,
        description="Sale price if sold same year"
    )

    def get_spread(self) -> float:
        """Calculate bargain element (spread) per share."""
        return max(0, self.fmv_per_share_at_exercise - self.exercise_price_per_share)

    def get_total_spread(self) -> float:
        """Calculate total spread for all shares."""
        return self.shares_exercised * self.get_spread()

    def get_amt_adjustment(self) -> float:
        """
        Calculate AMT adjustment from ISO exercise.

        If same-year disqualifying disposition, no AMT adjustment needed
        (gain/loss reported as ordinary income on regular return).
        """
        if self.same_year_sale:
            # Disqualifying disposition - no AMT preference
            return 0.0
        return self.get_total_spread()


class PrivateActivityBond(BaseModel):
    """
    Private activity bond interest details.

    Tax-exempt interest from private activity bonds issued after
    August 7, 1986 is an AMT preference item.
    """
    bond_name: str = Field(description="Bond name/description")
    cusip: Optional[str] = Field(default=None, description="CUSIP identifier")
    interest_received: float = Field(ge=0, description="Tax-exempt interest received")
    issue_date: Optional[str] = Field(default=None, description="Bond issue date")
    is_post_1986: bool = Field(
        default=True,
        description="Bond issued after August 7, 1986"
    )

    def get_amt_adjustment(self) -> float:
        """Get AMT preference amount."""
        if self.is_post_1986:
            return self.interest_received
        return 0.0


class DepreciationAdjustment(BaseModel):
    """
    AMT depreciation adjustment details.

    For AMT, certain assets must use ADS (Alternative Depreciation System)
    instead of MACRS. The difference is an AMT adjustment.
    """
    asset_description: str = Field(description="Asset description")
    regular_depreciation: float = Field(ge=0, description="MACRS depreciation claimed")
    amt_depreciation: float = Field(ge=0, description="ADS depreciation for AMT")

    def get_adjustment(self) -> float:
        """
        Calculate depreciation adjustment.

        Positive if regular > AMT (add back to AMTI)
        Negative if AMT > regular (subtract from AMTI)
        """
        return self.regular_depreciation - self.amt_depreciation


class Form6251(BaseModel):
    """
    IRS Form 6251 - Alternative Minimum Tax - Individuals

    Calculates AMT by:
    1. Starting with taxable income (or AGI if itemizing certain items)
    2. Adding AMT adjustments and preferences (Part I)
    3. Subtracting AMT exemption with phaseout (Part II)
    4. Calculating Tentative Minimum Tax at 26%/28% rates
    5. Comparing to regular tax - excess is AMT

    Form Structure:
    - Part I: Alternative Minimum Taxable Income (Lines 1-4)
    - Part II: Alternative Minimum Tax (Lines 5-11)
    - Part III: Tax Computation Using Maximum Capital Gains Rates
    """

    # Tax year
    tax_year: int = Field(default=2025)

    # Filing status for exemption lookup
    filing_status: str = Field(default="single")

    # ========== Part I: Alternative Minimum Taxable Income ==========

    # Line 1: Taxable income (from Form 1040)
    # If less than zero, enter as negative
    taxable_income: float = Field(default=0.0, description="Taxable income from Form 1040")

    # Line 2a: Taxes (SALT add-back if itemizing)
    line_2a_taxes: float = Field(default=0.0, ge=0, description="State/local taxes add-back")

    # Line 2b: Tax refund (adjustment if reported as income)
    line_2b_tax_refund: float = Field(default=0.0, description="Tax refund adjustment")

    # Line 2c: Investment interest expense adjustment
    line_2c_investment_interest: float = Field(default=0.0, description="Investment interest adjustment")

    # Line 2d: Depletion adjustment
    line_2d_depletion: float = Field(default=0.0, description="Depletion adjustment")

    # Line 2e: Net operating loss deduction
    line_2e_nol: float = Field(default=0.0, ge=0, description="NOL deduction add-back")

    # Line 2f: Alternative tax NOL deduction (enter as negative)
    line_2f_atnol: float = Field(default=0.0, le=0, description="ATNOL deduction")

    # Line 2g: Private activity bond interest
    line_2g_pab_interest: float = Field(default=0.0, ge=0, description="Private activity bond interest")

    # Line 2h: Qualified small business stock (Section 1202)
    line_2h_qsbs: float = Field(default=0.0, ge=0, description="QSBS exclusion adjustment")

    # Line 2i: Incentive stock options
    line_2i_iso: float = Field(default=0.0, ge=0, description="ISO exercise spread")

    # Line 2j: Estates and trusts
    line_2j_estates_trusts: float = Field(default=0.0, description="Estates/trusts adjustment")

    # Line 2k: Disposition of property
    line_2k_property_disposition: float = Field(default=0.0, description="Property disposition adjustment")

    # Line 2l: Depreciation on assets placed in service after 1986
    line_2l_depreciation: float = Field(default=0.0, description="Depreciation adjustment")

    # Line 2m: Passive activities
    line_2m_passive_activities: float = Field(default=0.0, description="Passive activity adjustment")

    # Line 2n: Loss limitations
    line_2n_loss_limitations: float = Field(default=0.0, description="Loss limitations adjustment")

    # Line 2o: Circulation costs
    line_2o_circulation: float = Field(default=0.0, description="Circulation costs")

    # Line 2p: Long-term contracts
    line_2p_long_term_contracts: float = Field(default=0.0, description="Long-term contracts adjustment")

    # Line 2q: Mining costs
    line_2q_mining: float = Field(default=0.0, description="Mining costs")

    # Line 2r: Research and experimental costs
    line_2r_research: float = Field(default=0.0, description="Research/experimental costs")

    # Line 2s: Section 1202 exclusion (7% of excluded gain)
    line_2s_section_1202: float = Field(default=0.0, ge=0, description="Section 1202 exclusion")

    # Line 2t: Section 1291 (PFIC)
    line_2t_pfic: float = Field(default=0.0, description="PFIC adjustment")

    # Line 2u: Section 965 inclusion
    line_2u_section_965: float = Field(default=0.0, description="Section 965 adjustment")

    # Line 2v: Section 250 deduction
    line_2v_section_250: float = Field(default=0.0, description="Section 250 deduction")

    # Line 3: Other adjustments
    line_3_other: float = Field(default=0.0, description="Other adjustments")

    # ========== Detailed Tracking ==========

    # ISO exercises for detailed tracking
    iso_exercises: List[ISOExercise] = Field(
        default_factory=list,
        description="ISO exercise details"
    )

    # Private activity bonds
    private_activity_bonds: List[PrivateActivityBond] = Field(
        default_factory=list,
        description="Private activity bond holdings"
    )

    # Depreciation adjustments
    depreciation_adjustments: List[DepreciationAdjustment] = Field(
        default_factory=list,
        description="Depreciation adjustment details"
    )

    # Generic adjustments list
    adjustments: List[AMTAdjustment] = Field(
        default_factory=list,
        description="List of AMT adjustments"
    )

    # ========== Part II Configuration ==========

    # AMT exemption (from config, but can override)
    exemption_amount: Optional[float] = Field(
        default=None,
        description="AMT exemption (None = use config based on filing status)"
    )

    # Phaseout threshold (from config, but can override)
    phaseout_threshold: Optional[float] = Field(
        default=None,
        description="Exemption phaseout threshold (None = use config)"
    )

    # 28% rate threshold
    threshold_28_percent: Optional[float] = Field(
        default=None,
        description="Threshold where 28% rate begins (None = use config)"
    )

    # ========== Part III: Capital Gains ==========

    # Long-term capital gains and qualified dividends
    # (for applying preferential rates under AMT)
    net_capital_gain: float = Field(
        default=0.0, ge=0,
        description="Net capital gain (long-term gains less short-term losses)"
    )

    qualified_dividends: float = Field(
        default=0.0, ge=0,
        description="Qualified dividends"
    )

    unrecaptured_section_1250_gain: float = Field(
        default=0.0, ge=0,
        description="Unrecaptured Section 1250 gain (25% max rate)"
    )

    # 28% rate gain (collectibles, Section 1202 exclusion portion)
    collectibles_gain: float = Field(
        default=0.0, ge=0,
        description="28% rate capital gain (collectibles)"
    )

    # ========== Prior Year AMT Credit ==========

    prior_year_amt_credit: float = Field(
        default=0.0, ge=0,
        description="Minimum tax credit carryforward (Form 8801)"
    )

    # ========== 2025 Default Thresholds (ClassVar) ==========

    # Exemption amounts by filing status
    EXEMPTION_2025: ClassVar[Dict[str, float]] = {
        "single": 88100.0,
        "married_joint": 137000.0,
        "married_separate": 68500.0,
        "head_of_household": 88100.0,
        "qualifying_widow": 137000.0,
    }

    # Phaseout thresholds
    PHASEOUT_START_2025: ClassVar[Dict[str, float]] = {
        "single": 626350.0,
        "married_joint": 1252700.0,
        "married_separate": 626350.0,
        "head_of_household": 626350.0,
        "qualifying_widow": 1252700.0,
    }

    # 28% rate threshold (above exemption)
    THRESHOLD_28_2025: ClassVar[Dict[str, float]] = {
        "single": 232600.0,
        "married_joint": 232600.0,
        "married_separate": 116300.0,
        "head_of_household": 232600.0,
        "qualifying_widow": 232600.0,
    }

    # AMT rates
    RATE_26: ClassVar[float] = 0.26
    RATE_28: ClassVar[float] = 0.28
    PHASEOUT_RATE: ClassVar[float] = 0.25  # 25 cents per dollar

    def _get_exemption_base(self) -> float:
        """Get base exemption amount for filing status."""
        if self.exemption_amount is not None:
            return self.exemption_amount
        return self.EXEMPTION_2025.get(self.filing_status, 88100.0)

    def _get_phaseout_threshold(self) -> float:
        """Get phaseout threshold for filing status."""
        if self.phaseout_threshold is not None:
            return self.phaseout_threshold
        return self.PHASEOUT_START_2025.get(self.filing_status, 626350.0)

    def _get_28_threshold(self) -> float:
        """Get 28% rate threshold for filing status."""
        if self.threshold_28_percent is not None:
            return self.threshold_28_percent
        return self.THRESHOLD_28_2025.get(self.filing_status, 232600.0)

    def calculate_part_i(self) -> dict:
        """
        Calculate Part I - Alternative Minimum Taxable Income (AMTI).

        Starts with taxable income and adds AMT adjustments.

        Returns:
            Dict with AMTI calculation details
        """
        result = {
            'line_1_taxable_income': self.taxable_income,
            'adjustments': {},
            'line_4_amti': 0.0,
        }

        # Calculate ISO adjustment from detailed records if available
        iso_from_records = sum(
            iso.get_amt_adjustment() for iso in self.iso_exercises
        )
        total_iso = self.line_2i_iso + iso_from_records

        # Calculate PAB interest from detailed records if available
        pab_from_records = sum(
            pab.get_amt_adjustment() for pab in self.private_activity_bonds
        )
        total_pab = self.line_2g_pab_interest + pab_from_records

        # Calculate depreciation from detailed records if available
        depreciation_from_records = sum(
            dep.get_adjustment() for dep in self.depreciation_adjustments
        )
        total_depreciation = self.line_2l_depreciation + depreciation_from_records

        # Collect all adjustments
        adjustments = {
            'line_2a_taxes': self.line_2a_taxes,
            'line_2b_tax_refund': self.line_2b_tax_refund,
            'line_2c_investment_interest': self.line_2c_investment_interest,
            'line_2d_depletion': self.line_2d_depletion,
            'line_2e_nol': self.line_2e_nol,
            'line_2f_atnol': self.line_2f_atnol,
            'line_2g_pab_interest': total_pab,
            'line_2h_qsbs': self.line_2h_qsbs,
            'line_2i_iso': total_iso,
            'line_2j_estates_trusts': self.line_2j_estates_trusts,
            'line_2k_property_disposition': self.line_2k_property_disposition,
            'line_2l_depreciation': total_depreciation,
            'line_2m_passive_activities': self.line_2m_passive_activities,
            'line_2n_loss_limitations': self.line_2n_loss_limitations,
            'line_2o_circulation': self.line_2o_circulation,
            'line_2p_long_term_contracts': self.line_2p_long_term_contracts,
            'line_2q_mining': self.line_2q_mining,
            'line_2r_research': self.line_2r_research,
            'line_2s_section_1202': self.line_2s_section_1202,
            'line_2t_pfic': self.line_2t_pfic,
            'line_2u_section_965': self.line_2u_section_965,
            'line_2v_section_250': self.line_2v_section_250,
            'line_3_other': self.line_3_other,
        }

        # Add adjustments from the generic list
        for adj in self.adjustments:
            key = f'adjustment_{adj.adjustment_type.value}'
            adjustments[key] = adjustments.get(key, 0.0) + adj.amount

        result['adjustments'] = adjustments

        # Calculate total adjustments
        total_adjustments = sum(adjustments.values())
        result['total_adjustments'] = total_adjustments

        # Line 4: AMTI = Taxable Income + Adjustments
        amti = self.taxable_income + total_adjustments
        result['line_4_amti'] = amti

        return result

    def calculate_part_ii(self, amti: Optional[float] = None) -> dict:
        """
        Calculate Part II - Alternative Minimum Tax.

        Args:
            amti: AMTI from Part I (if None, calculates from Part I)

        Returns:
            Dict with exemption, TMT, and AMT calculation
        """
        if amti is None:
            part_i = self.calculate_part_i()
            amti = part_i['line_4_amti']

        exemption_base = self._get_exemption_base()
        phaseout_start = self._get_phaseout_threshold()
        threshold_28 = self._get_28_threshold()

        result = {
            'line_4_amti': amti,
            'line_5_exemption_base': exemption_base,
            'line_6_phaseout_threshold': phaseout_start,
            'line_6_excess_over_threshold': 0.0,
            'line_7_exemption_reduction': 0.0,
            'line_7_exemption_after_phaseout': exemption_base,
            'line_8_amt_taxable_income': 0.0,
            'line_9_tmt_before_foreign_tax_credit': 0.0,
            'line_10_amt_foreign_tax_credit': 0.0,
            'line_11_tentative_minimum_tax': 0.0,
        }

        # Calculate exemption with phaseout
        exemption = exemption_base
        if amti > phaseout_start:
            excess = amti - phaseout_start
            result['line_6_excess_over_threshold'] = excess

            # Reduce exemption by 25 cents per dollar over threshold
            reduction = excess * self.PHASEOUT_RATE
            result['line_7_exemption_reduction'] = reduction

            exemption = max(0, exemption_base - reduction)

        result['line_7_exemption_after_phaseout'] = exemption

        # AMT taxable income = AMTI - Exemption
        amt_taxable = max(0, amti - exemption)
        result['line_8_amt_taxable_income'] = amt_taxable

        # Calculate Tentative Minimum Tax at 26%/28% rates
        if amt_taxable <= threshold_28:
            tmt = amt_taxable * self.RATE_26
        else:
            tmt = (threshold_28 * self.RATE_26) + \
                  ((amt_taxable - threshold_28) * self.RATE_28)

        result['line_9_tmt_before_foreign_tax_credit'] = float(money(tmt))

        # For now, no FTC calculation (would need Form 1116 integration)
        result['line_11_tentative_minimum_tax'] = float(money(tmt))

        return result

    def calculate_part_iii(
        self,
        amt_taxable_income: float,
        regular_tax_capital_gains: float = 0.0
    ) -> dict:
        """
        Calculate Part III - Tax Using Maximum Capital Gains Rates.

        This allows AMT to benefit from preferential capital gains rates.

        Args:
            amt_taxable_income: From Part II Line 8
            regular_tax_capital_gains: Capital gains tax from regular tax

        Returns:
            Dict with capital gains tax calculation under AMT
        """
        # Total preferential income
        preferential_income = self.net_capital_gain + self.qualified_dividends

        result = {
            'net_capital_gain': self.net_capital_gain,
            'qualified_dividends': self.qualified_dividends,
            'total_preferential_income': preferential_income,
            'unrecaptured_1250': self.unrecaptured_section_1250_gain,
            'collectibles_28_rate': self.collectibles_gain,
            'amt_on_ordinary_income': 0.0,
            'amt_on_capital_gains': 0.0,
            'total_amt': 0.0,
            'uses_part_iii': False,
        }

        if preferential_income <= 0:
            # No preferential income, use Part II calculation
            return result

        result['uses_part_iii'] = True

        # AMT ordinary income (subtract preferential from AMT taxable)
        amt_ordinary = max(0, amt_taxable_income - preferential_income)

        # Tax on AMT ordinary income at 26%/28% rates
        threshold_28 = self._get_28_threshold()
        if amt_ordinary <= threshold_28:
            amt_on_ordinary = amt_ordinary * self.RATE_26
        else:
            amt_on_ordinary = (threshold_28 * self.RATE_26) + \
                            ((amt_ordinary - threshold_28) * self.RATE_28)

        result['amt_on_ordinary_income'] = float(money(amt_on_ordinary))

        # Capital gains taxed at preferential rates (0%/15%/20%)
        # Plus 25% on unrecaptured 1250 and 28% on collectibles
        # Simplified: use same rates as regular tax
        result['amt_on_capital_gains'] = float(money(regular_tax_capital_gains))

        result['total_amt'] = float(money(amt_on_ordinary + regular_tax_capital_gains))

        return result

    def calculate_amt(
        self,
        regular_tax: float,
        regular_tax_capital_gains: float = 0.0
    ) -> dict:
        """
        Calculate complete AMT per Form 6251.

        AMT = max(0, Tentative Minimum Tax - Regular Tax)

        Args:
            regular_tax: Regular tax liability (before credits)
            regular_tax_capital_gains: Capital gains portion of regular tax

        Returns:
            Complete AMT calculation breakdown
        """
        # Calculate AMTI (Part I)
        part_i = self.calculate_part_i()
        amti = part_i['line_4_amti']

        # Calculate TMT (Part II)
        part_ii = self.calculate_part_ii(amti)
        tmt = part_ii['line_11_tentative_minimum_tax']

        # Check if Part III applies (capital gains)
        has_preferential = (self.net_capital_gain + self.qualified_dividends) > 0
        part_iii = None

        if has_preferential:
            part_iii = self.calculate_part_iii(
                part_ii['line_8_amt_taxable_income'],
                regular_tax_capital_gains
            )
            # Use lower of Part II or Part III TMT
            if part_iii['uses_part_iii'] and part_iii['total_amt'] < tmt:
                tmt = part_iii['total_amt']

        # AMT = excess of TMT over regular tax
        amt = max(0, tmt - regular_tax)

        # Apply prior year AMT credit
        amt_after_credit = max(0, amt - self.prior_year_amt_credit)
        credit_used = amt - amt_after_credit

        result = {
            # Summary
            'amt': float(money(amt)),
            'amt_after_credit': float(money(amt_after_credit)),
            'prior_year_credit_used': float(money(credit_used)),

            # Key figures
            'amti': amti,
            'exemption_base': part_ii['line_5_exemption_base'],
            'exemption_after_phaseout': part_ii['line_7_exemption_after_phaseout'],
            'amt_taxable_income': part_ii['line_8_amt_taxable_income'],
            'tentative_minimum_tax': tmt,
            'regular_tax': regular_tax,

            # Detailed breakdowns
            'part_i': part_i,
            'part_ii': part_ii,
            'part_iii': part_iii,

            # AMT adjustments summary
            'total_adjustments': part_i['total_adjustments'],
            'salt_addback': part_i['adjustments'].get('line_2a_taxes', 0.0),
            'iso_spread': part_i['adjustments'].get('line_2i_iso', 0.0),
            'pab_interest': part_i['adjustments'].get('line_2g_pab_interest', 0.0),
            'depreciation_adjustment': part_i['adjustments'].get('line_2l_depreciation', 0.0),

            # Status flags
            'has_amt_liability': amt > 0,
            'exemption_fully_phased_out': part_ii['line_7_exemption_after_phaseout'] == 0,
            'uses_capital_gains_rates': part_iii['uses_part_iii'] if part_iii else False,
        }

        return result

    def get_amt_summary(self) -> dict:
        """
        Get a simplified AMT summary without full calculation.

        Useful for quick checks and display.
        """
        part_i = self.calculate_part_i()

        return {
            'amti': part_i['line_4_amti'],
            'total_adjustments': part_i['total_adjustments'],
            'major_adjustments': {
                'salt_addback': self.line_2a_taxes,
                'iso_spread': self.line_2i_iso,
                'pab_interest': self.line_2g_pab_interest,
                'depreciation': self.line_2l_depreciation,
            },
            'exemption_base': self._get_exemption_base(),
            'phaseout_threshold': self._get_phaseout_threshold(),
            'may_owe_amt': part_i['line_4_amti'] > self._get_phaseout_threshold(),
        }


# ============== Helper Functions ==============

def calculate_amt_exemption_phaseout(
    amti: float,
    filing_status: str,
    exemption_base: Optional[float] = None,
    phaseout_start: Optional[float] = None
) -> dict:
    """
    Calculate AMT exemption with phaseout.

    Args:
        amti: Alternative Minimum Taxable Income
        filing_status: Filing status for threshold lookup
        exemption_base: Override exemption (None = use 2025 default)
        phaseout_start: Override phaseout threshold (None = use 2025 default)

    Returns:
        Dict with exemption calculation details
    """
    if exemption_base is None:
        exemption_base = Form6251.EXEMPTION_2025.get(filing_status, 88100.0)
    if phaseout_start is None:
        phaseout_start = Form6251.PHASEOUT_START_2025.get(filing_status, 626350.0)

    exemption = exemption_base
    reduction = 0.0

    if amti > phaseout_start:
        excess = amti - phaseout_start
        reduction = excess * Form6251.PHASEOUT_RATE
        exemption = max(0, exemption_base - reduction)

    return {
        'amti': amti,
        'exemption_base': exemption_base,
        'phaseout_start': phaseout_start,
        'excess_over_threshold': max(0, amti - phaseout_start),
        'reduction': reduction,
        'exemption_after_phaseout': exemption,
        'fully_phased_out': exemption == 0,
    }


def calculate_tentative_minimum_tax(
    amt_taxable_income: float,
    filing_status: str,
    threshold_28: Optional[float] = None
) -> dict:
    """
    Calculate Tentative Minimum Tax at 26%/28% rates.

    Args:
        amt_taxable_income: AMT taxable income (AMTI - exemption)
        filing_status: Filing status for threshold lookup
        threshold_28: Override 28% threshold (None = use 2025 default)

    Returns:
        Dict with TMT calculation details
    """
    if threshold_28 is None:
        threshold_28 = Form6251.THRESHOLD_28_2025.get(filing_status, 232600.0)

    if amt_taxable_income <= 0:
        return {
            'amt_taxable_income': 0.0,
            'tax_at_26': 0.0,
            'tax_at_28': 0.0,
            'tmt': 0.0,
        }

    if amt_taxable_income <= threshold_28:
        tax_26 = amt_taxable_income * Form6251.RATE_26
        tax_28 = 0.0
    else:
        tax_26 = threshold_28 * Form6251.RATE_26
        tax_28 = (amt_taxable_income - threshold_28) * Form6251.RATE_28

    return {
        'amt_taxable_income': amt_taxable_income,
        'threshold_28': threshold_28,
        'income_at_26': min(amt_taxable_income, threshold_28),
        'income_at_28': max(0, amt_taxable_income - threshold_28),
        'tax_at_26': float(money(tax_26)),
        'tax_at_28': float(money(tax_28)),
        'tmt': float(money(tax_26 + tax_28)),
    }


def check_amt_likely(
    taxable_income: float,
    salt_deduction: float,
    iso_spread: float = 0.0,
    pab_interest: float = 0.0,
    filing_status: str = "single"
) -> dict:
    """
    Quick check if AMT is likely.

    This is a simplified screening - actual AMT requires full calculation.

    Args:
        taxable_income: Regular taxable income
        salt_deduction: State/local tax deduction claimed
        iso_spread: ISO exercise spread
        pab_interest: Private activity bond interest
        filing_status: Filing status

    Returns:
        Dict with AMT likelihood assessment
    """
    # Estimate AMTI
    estimated_amti = taxable_income + salt_deduction + iso_spread + pab_interest

    # Get thresholds
    exemption = Form6251.EXEMPTION_2025.get(filing_status, 88100.0)
    phaseout = Form6251.PHASEOUT_START_2025.get(filing_status, 626350.0)

    # Risk factors
    risk_factors = []
    if salt_deduction > 10000:
        risk_factors.append("High SALT deduction (capped at $10k, full amount added for AMT)")
    if iso_spread > 0:
        risk_factors.append(f"ISO exercise spread of ${iso_spread:,.0f}")
    if pab_interest > 0:
        risk_factors.append(f"Private activity bond interest of ${pab_interest:,.0f}")
    if estimated_amti > phaseout:
        risk_factors.append("AMTI exceeds exemption phaseout threshold")

    # Estimate AMT taxable income
    est_amt_taxable = max(0, estimated_amti - exemption)

    # Rough TMT estimate
    threshold_28 = Form6251.THRESHOLD_28_2025.get(filing_status, 232600.0)
    if est_amt_taxable <= threshold_28:
        est_tmt = est_amt_taxable * 0.26
    else:
        est_tmt = threshold_28 * 0.26 + (est_amt_taxable - threshold_28) * 0.28

    return {
        'estimated_amti': estimated_amti,
        'exemption': exemption,
        'estimated_amt_taxable': est_amt_taxable,
        'estimated_tmt': float(money(est_tmt)),
        'risk_factors': risk_factors,
        'likely_amt': len(risk_factors) >= 2 or (iso_spread > 50000),
        'recommendation': (
            "Consider Form 6251 calculation" if risk_factors
            else "AMT unlikely based on inputs"
        ),
    }
