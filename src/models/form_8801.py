"""
Form 8801 - Credit for Prior Year Minimum Tax - Individuals, Estates, and Trusts

Implements IRS Form 8801 per IRC Section 53 for claiming credit for prior year
Alternative Minimum Tax (AMT) paid on deferral items.

Key Concepts:
- Minimum Tax Credit (MTC) allows recovery of AMT paid on "deferral" items
- Deferral items: Create timing differences (ISO exercise, depreciation)
- Exclusion items: Permanent differences (PAB interest) - NO credit generated
- MTC can reduce regular tax, but not below tentative minimum tax (TMT)
- Unused credit carries forward indefinitely

How the Credit Works:
1. Prior year AMT paid on deferral items generates MTC
2. Current year: MTC can offset regular tax exceeding TMT
3. Unused MTC carries forward to future years

Form Structure:
- Part I: Net Minimum Tax on Exclusion Items
- Part II: Minimum Tax Credit and Carryforward
- Part III: Tax Computation Using Maximum Capital Gains Rates

IRC References:
- Section 53: Credit for prior year minimum tax liability
- Section 53(d): Definitions of deferral and exclusion items
- Section 55-59: Alternative minimum tax rules

2025 Thresholds (same as Form 6251):
- Single: Exemption $88,100, Phaseout at $626,350
- MFJ/QW: Exemption $137,000, Phaseout at $1,252,700
- MFS: Exemption $68,500, Phaseout at $626,350
- HOH: Exemption $88,100, Phaseout at $626,350
"""

from typing import Optional, List, Dict, ClassVar
from pydantic import BaseModel, Field
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class AMTItemType(str, Enum):
    """
    Classification of AMT adjustment items.

    Deferral items generate MTC; exclusion items do not.
    """
    # DEFERRAL ITEMS - Generate MTC (timing differences that reverse)
    ISO_EXERCISE = "iso_exercise"  # Incentive stock option spread
    DEPRECIATION = "depreciation"  # Post-1986 depreciation adjustment
    PASSIVE_ACTIVITY = "passive_activity"  # Passive activity loss adjustment
    LOSS_LIMITATIONS = "loss_limitations"  # Loss limitation adjustment
    LONG_TERM_CONTRACTS = "long_term_contracts"  # Long-term contract adjustment
    MINING_COSTS = "mining_costs"  # Mining exploration costs
    RESEARCH_COSTS = "research_costs"  # Research and experimental costs
    CIRCULATION_COSTS = "circulation_costs"  # Circulation expenditures
    INSTALLMENT_SALE = "installment_sale"  # Installment sale adjustment

    # EXCLUSION ITEMS - Do NOT generate MTC (permanent differences)
    PRIVATE_ACTIVITY_BOND = "private_activity_bond"  # Tax-exempt PAB interest
    DEPLETION = "depletion"  # Excess depletion
    INTANGIBLE_DRILLING = "intangible_drilling"  # Intangible drilling costs
    TAX_SHELTER_FARM = "tax_shelter_farm"  # Tax shelter farm activities


class PriorYearAMTDetail(BaseModel):
    """
    Detail of AMT paid in a prior year for MTC tracking.

    Tracks the breakdown between deferral and exclusion items
    to determine how much MTC was generated.
    """
    tax_year: int = Field(description="Year AMT was paid")

    # Total AMT paid that year
    total_amt_paid: float = Field(ge=0, description="Total AMT paid")

    # AMT breakdown by item type
    amt_from_iso: float = Field(default=0.0, ge=0, description="AMT from ISO exercises")
    amt_from_depreciation: float = Field(default=0.0, ge=0, description="AMT from depreciation")
    amt_from_passive_activities: float = Field(default=0.0, ge=0)
    amt_from_long_term_contracts: float = Field(default=0.0, ge=0)
    amt_from_other_deferral: float = Field(default=0.0, ge=0, description="Other deferral items")

    # Exclusion items (do not generate MTC)
    amt_from_pab_interest: float = Field(default=0.0, ge=0, description="AMT from PAB interest")
    amt_from_depletion: float = Field(default=0.0, ge=0, description="AMT from excess depletion")
    amt_from_other_exclusion: float = Field(default=0.0, ge=0, description="Other exclusion items")

    def get_deferral_amt(self) -> float:
        """Get AMT attributable to deferral items (generates MTC)."""
        return (
            self.amt_from_iso +
            self.amt_from_depreciation +
            self.amt_from_passive_activities +
            self.amt_from_long_term_contracts +
            self.amt_from_other_deferral
        )

    def get_exclusion_amt(self) -> float:
        """Get AMT attributable to exclusion items (no MTC)."""
        return (
            self.amt_from_pab_interest +
            self.amt_from_depletion +
            self.amt_from_other_exclusion
        )

    def get_mtc_generated(self) -> float:
        """
        Calculate MTC generated from this year's AMT.

        MTC = AMT from deferral items only.
        """
        return self.get_deferral_amt()


class MTCCarryforward(BaseModel):
    """
    Minimum Tax Credit carryforward tracking.

    Tracks MTC available from each prior year and usage.
    """
    # Original year the credit was generated
    origin_year: int = Field(description="Year MTC was generated")

    # Original amount of MTC from that year
    original_amount: float = Field(ge=0, description="Original MTC amount")

    # Amount used in subsequent years
    amount_used: float = Field(default=0.0, ge=0, description="Amount used to date")

    # Remaining available
    @property
    def remaining(self) -> float:
        return max(0, self.original_amount - self.amount_used)

    def use_credit(self, amount: float) -> float:
        """
        Use credit and return amount actually used.

        Args:
            amount: Amount to use

        Returns:
            Amount actually used (limited to remaining)
        """
        available = self.remaining
        used = min(amount, available)
        self.amount_used += used
        return used


class Form8801(BaseModel):
    """
    IRS Form 8801 - Credit for Prior Year Minimum Tax

    Calculates the Minimum Tax Credit (MTC) that can be claimed
    in the current year to recover AMT paid on deferral items
    in prior years.

    The credit can reduce regular tax, but not below the
    tentative minimum tax (TMT).

    Form Parts:
    - Part I: Net Minimum Tax on Exclusion Items (Lines 1-17)
    - Part II: Minimum Tax Credit and Carryforward (Lines 18-26)
    - Part III: Tax Computation Using Maximum Capital Gains Rates
    """

    # Tax year
    tax_year: int = Field(default=2025)
    filing_status: str = Field(default="single")

    # ========== Current Year Tax Figures ==========

    # From Form 1040 / Form 6251
    current_year_regular_tax: float = Field(
        default=0.0, ge=0,
        description="Regular tax liability before credits (Form 1040)"
    )
    current_year_tmt: float = Field(
        default=0.0, ge=0,
        description="Tentative minimum tax (Form 6251)"
    )
    current_year_amt: float = Field(
        default=0.0, ge=0,
        description="Alternative minimum tax (Form 6251)"
    )

    # ========== Part I: Net Minimum Tax on Exclusion Items ==========

    # Line 1: Combined amount from Form 6251 line 4 and Schedule I line 24
    line_1_amti: float = Field(
        default=0.0,
        description="Alternative minimum taxable income (AMTI)"
    )

    # Exclusion item adjustments (reduce AMTI for Part I calculation)
    # Line 2: SALT adjustment (if any - usually not exclusion)
    line_2_salt_adjustment: float = Field(default=0.0)

    # Line 3: Tax refund adjustment
    line_3_tax_refund: float = Field(default=0.0)

    # Line 4: Investment interest expense
    line_4_investment_interest: float = Field(default=0.0)

    # Line 5: Post-1986 depreciation (deferral item - enters negative)
    line_5_depreciation: float = Field(default=0.0)

    # Line 6: Adjusted gain or loss (deferral)
    line_6_adjusted_gain_loss: float = Field(default=0.0)

    # Line 7: Incentive stock options (deferral - enters negative)
    line_7_iso: float = Field(default=0.0)

    # Line 8: Other adjustments (mix)
    line_8_other: float = Field(default=0.0)

    # ========== Prior Year Information ==========

    # Prior year AMT details (for calculating MTC generated)
    prior_year_amt_details: List[PriorYearAMTDetail] = Field(
        default_factory=list,
        description="AMT details from prior years"
    )

    # MTC carryforwards from prior years
    mtc_carryforwards: List[MTCCarryforward] = Field(
        default_factory=list,
        description="MTC carryforward amounts by year"
    )

    # Simple aggregate: Total MTC available from all prior years
    total_mtc_carryforward: float = Field(
        default=0.0, ge=0,
        description="Total MTC available from prior years"
    )

    # ========== Capital Gains Information (Part III) ==========

    net_capital_gain: float = Field(default=0.0, ge=0)
    qualified_dividends: float = Field(default=0.0, ge=0)
    unrecaptured_1250_gain: float = Field(default=0.0, ge=0)

    # ========== 2025 Thresholds (same as Form 6251) ==========

    EXEMPTION_2025: ClassVar[Dict[str, float]] = {
        "single": 88100.0,
        "married_joint": 137000.0,
        "married_separate": 68500.0,
        "head_of_household": 88100.0,
        "qualifying_widow": 137000.0,
    }

    PHASEOUT_START_2025: ClassVar[Dict[str, float]] = {
        "single": 626350.0,
        "married_joint": 1252700.0,
        "married_separate": 626350.0,
        "head_of_household": 626350.0,
        "qualifying_widow": 1252700.0,
    }

    THRESHOLD_28_2025: ClassVar[Dict[str, float]] = {
        "single": 232600.0,
        "married_joint": 232600.0,
        "married_separate": 116300.0,
        "head_of_household": 232600.0,
        "qualifying_widow": 232600.0,
    }

    RATE_26: ClassVar[float] = 0.26
    RATE_28: ClassVar[float] = 0.28
    PHASEOUT_RATE: ClassVar[float] = 0.25

    def _get_exemption_base(self) -> float:
        """Get base exemption for filing status."""
        return self.EXEMPTION_2025.get(self.filing_status, 88100.0)

    def _get_phaseout_threshold(self) -> float:
        """Get phaseout threshold for filing status."""
        return self.PHASEOUT_START_2025.get(self.filing_status, 626350.0)

    def _get_28_threshold(self) -> float:
        """Get 28% rate threshold for filing status."""
        return self.THRESHOLD_28_2025.get(self.filing_status, 232600.0)

    def calculate_part_i(self) -> dict:
        """
        Calculate Part I - Net Minimum Tax on Exclusion Items.

        This recalculates AMT considering only exclusion items
        (permanent differences). The difference from actual AMT
        is the MTC-generating portion.

        Returns:
            Dict with exclusion-only AMT calculation
        """
        result = {
            'line_1_amti': self.line_1_amti,
            # Lines 2-8: Adjustments to remove deferral items
            'line_2_salt': self.line_2_salt_adjustment,
            'line_3_tax_refund': self.line_3_tax_refund,
            'line_4_investment_interest': self.line_4_investment_interest,
            'line_5_depreciation': self.line_5_depreciation,
            'line_6_adjusted_gain_loss': self.line_6_adjusted_gain_loss,
            'line_7_iso': self.line_7_iso,
            'line_8_other': self.line_8_other,
            'line_9_total_adjustments': 0.0,
            'line_10_exclusion_amti': 0.0,
            'line_11_exemption': 0.0,
            'line_12_amt_taxable': 0.0,
            'line_13_exclusion_tmt': 0.0,
            'line_17_net_min_tax_exclusion': 0.0,
        }

        # Line 9: Total adjustments (removing deferral items)
        # Negative adjustments remove deferral items from AMTI
        total_adjustments = (
            self.line_2_salt_adjustment +
            self.line_3_tax_refund +
            self.line_4_investment_interest +
            self.line_5_depreciation +  # Negative to remove deferral
            self.line_6_adjusted_gain_loss +
            self.line_7_iso +  # Negative to remove deferral
            self.line_8_other
        )
        result['line_9_total_adjustments'] = total_adjustments

        # Line 10: AMTI for exclusion items only
        exclusion_amti = self.line_1_amti + total_adjustments
        result['line_10_exclusion_amti'] = exclusion_amti

        # Line 11: Exemption (same calculation as Form 6251)
        exemption_base = self._get_exemption_base()
        phaseout_start = self._get_phaseout_threshold()

        exemption = exemption_base
        if exclusion_amti > phaseout_start:
            excess = exclusion_amti - phaseout_start
            reduction = excess * self.PHASEOUT_RATE
            exemption = max(0, exemption_base - reduction)
        result['line_11_exemption'] = exemption

        # Line 12: AMT taxable income (exclusion items only)
        amt_taxable = max(0, exclusion_amti - exemption)
        result['line_12_amt_taxable'] = amt_taxable

        # Line 13-16: TMT calculation at 26%/28% rates
        threshold_28 = self._get_28_threshold()
        if amt_taxable <= threshold_28:
            tmt = amt_taxable * self.RATE_26
        else:
            tmt = (threshold_28 * self.RATE_26) + \
                  ((amt_taxable - threshold_28) * self.RATE_28)
        result['line_13_exclusion_tmt'] = float(money(tmt))

        # Line 17: Net minimum tax on exclusion items
        # This is the TMT attributable only to exclusion items
        result['line_17_net_min_tax_exclusion'] = float(money(tmt))

        return result

    def calculate_part_ii(self) -> dict:
        """
        Calculate Part II - Minimum Tax Credit and Carryforward.

        Determines how much MTC can be used in current year
        and the carryforward to next year.

        Returns:
            Dict with credit calculation and carryforward
        """
        part_i = self.calculate_part_i()

        result = {
            # Line 18: Net minimum tax on exclusion items (from Part I)
            'line_18_net_exclusion_tax': part_i['line_17_net_min_tax_exclusion'],

            # Line 19: Tentative minimum tax from Form 6251
            'line_19_tmt': self.current_year_tmt,

            # Line 20: Smaller of line 18 or line 19
            'line_20_smaller': 0.0,

            # Line 21: MTC carryforward from prior year
            'line_21_prior_mtc': 0.0,

            # Line 22: Current year minimum tax credit
            'line_22_current_year_mtc': 0.0,

            # Line 23: Add lines 21 and 22
            'line_23_total_mtc': 0.0,

            # Line 24: Regular tax before credits
            'line_24_regular_tax': self.current_year_regular_tax,

            # Line 25: Tentative minimum tax (same as line 19)
            'line_25_tmt': self.current_year_tmt,

            # Line 26: Subtract line 25 from line 24 (credit limit)
            'line_26_credit_limit': 0.0,

            # Credit allowed and carryforward
            'credit_allowed': 0.0,
            'carryforward_to_next_year': 0.0,
        }

        # Line 20: Smaller of exclusion TMT or actual TMT
        result['line_20_smaller'] = min(
            part_i['line_17_net_min_tax_exclusion'],
            self.current_year_tmt
        )

        # Line 21: MTC from prior years
        # Use detailed carryforwards if available, otherwise aggregate
        if self.mtc_carryforwards:
            prior_mtc = sum(cf.remaining for cf in self.mtc_carryforwards)
        else:
            prior_mtc = self.total_mtc_carryforward
        result['line_21_prior_mtc'] = prior_mtc

        # Line 22: Current year MTC generated
        # This is the AMT from deferral items in prior year
        # For simplicity, we calculate from prior year details
        current_year_mtc = 0.0
        for detail in self.prior_year_amt_details:
            if detail.tax_year == self.tax_year - 1:
                current_year_mtc = detail.get_mtc_generated()
                break
        result['line_22_current_year_mtc'] = current_year_mtc

        # Line 23: Total MTC available
        total_mtc = prior_mtc + current_year_mtc
        result['line_23_total_mtc'] = total_mtc

        # Line 26: Credit limit (regular tax - TMT)
        # Credit can only reduce regular tax to TMT, not below
        credit_limit = max(0, self.current_year_regular_tax - self.current_year_tmt)
        result['line_26_credit_limit'] = credit_limit

        # Credit allowed is lesser of total MTC or credit limit
        credit_allowed = min(total_mtc, credit_limit)
        result['credit_allowed'] = float(money(credit_allowed))

        # Carryforward is unused MTC
        result['carryforward_to_next_year'] = float(money(total_mtc - credit_allowed))

        return result

    def calculate_credit(self) -> dict:
        """
        Calculate the minimum tax credit for current year.

        Main method that computes:
        1. MTC available from prior years
        2. Credit limit (regular tax - TMT)
        3. Credit allowed
        4. Carryforward to next year

        Returns:
            Complete Form 8801 calculation
        """
        part_i = self.calculate_part_i()
        part_ii = self.calculate_part_ii()

        result = {
            # Credit amounts
            'minimum_tax_credit': part_ii['credit_allowed'],
            'credit_limit': part_ii['line_26_credit_limit'],
            'total_mtc_available': part_ii['line_23_total_mtc'],
            'carryforward': part_ii['carryforward_to_next_year'],

            # Current year figures
            'regular_tax': self.current_year_regular_tax,
            'tmt': self.current_year_tmt,
            'amt': self.current_year_amt,

            # Tax after credit
            'tax_after_credit': max(
                self.current_year_tmt,
                self.current_year_regular_tax - part_ii['credit_allowed']
            ),

            # Breakdown
            'from_prior_years': part_ii['line_21_prior_mtc'],
            'from_current_year_deferral': part_ii['line_22_current_year_mtc'],

            # Part I details
            'exclusion_tmt': part_i['line_17_net_min_tax_exclusion'],
            'exclusion_amti': part_i['line_10_exclusion_amti'],

            # Full part details
            'part_i': part_i,
            'part_ii': part_ii,
        }

        return result

    def get_credit_summary(self) -> dict:
        """Get simplified credit summary."""
        calc = self.calculate_credit()

        return {
            'credit_available': calc['total_mtc_available'],
            'credit_allowed': calc['minimum_tax_credit'],
            'credit_limit': calc['credit_limit'],
            'carryforward': calc['carryforward'],
            'regular_tax': self.current_year_regular_tax,
            'tmt': self.current_year_tmt,
            'has_credit': calc['minimum_tax_credit'] > 0,
            'has_carryforward': calc['carryforward'] > 0,
        }


# ============== Helper Functions ==============

def calculate_mtc_from_amt(
    total_amt: float,
    iso_adjustment: float = 0.0,
    depreciation_adjustment: float = 0.0,
    pab_interest: float = 0.0,
    other_deferral: float = 0.0,
    other_exclusion: float = 0.0,
) -> dict:
    """
    Calculate MTC generated from an AMT payment.

    Only AMT attributable to deferral items generates MTC.

    Args:
        total_amt: Total AMT paid
        iso_adjustment: AMT from ISO exercises (deferral)
        depreciation_adjustment: AMT from depreciation (deferral)
        pab_interest: AMT from PAB interest (exclusion - no MTC)
        other_deferral: Other deferral items
        other_exclusion: Other exclusion items

    Returns:
        Dict with MTC calculation
    """
    # Deferral items generate MTC
    deferral_total = iso_adjustment + depreciation_adjustment + other_deferral

    # Exclusion items do not generate MTC
    exclusion_total = pab_interest + other_exclusion

    # If we know the breakdown, calculate proportionally
    if deferral_total + exclusion_total > 0:
        total_adjustments = deferral_total + exclusion_total
        deferral_portion = deferral_total / total_adjustments
        mtc_generated = total_amt * deferral_portion
    else:
        # If no breakdown, assume all deferral (conservative)
        mtc_generated = total_amt

    return {
        'total_amt': total_amt,
        'deferral_portion': deferral_total,
        'exclusion_portion': exclusion_total,
        'mtc_generated': float(money(mtc_generated)),
        'deferral_percentage': round(deferral_total / (deferral_total + exclusion_total) * 100, 1) if (deferral_total + exclusion_total) > 0 else 100.0,
    }


def calculate_credit_limit(
    regular_tax: float,
    tmt: float,
) -> float:
    """
    Calculate the credit limit for Form 8801.

    The minimum tax credit can only reduce regular tax to
    the tentative minimum tax, not below.

    Args:
        regular_tax: Regular tax before credits
        tmt: Tentative minimum tax

    Returns:
        Maximum credit that can be used
    """
    return max(0, regular_tax - tmt)


def track_mtc_carryforward(
    prior_carryforwards: List[MTCCarryforward],
    current_year_mtc: float,
    credit_used: float,
    current_year: int,
) -> List[MTCCarryforward]:
    """
    Track MTC carryforwards using FIFO (oldest credits first).

    Args:
        prior_carryforwards: Existing carryforward records
        current_year_mtc: New MTC generated this year
        credit_used: Total credit used this year
        current_year: Current tax year

    Returns:
        Updated list of carryforwards
    """
    # Sort by year (oldest first) for FIFO usage
    carryforwards = sorted(prior_carryforwards, key=lambda x: x.origin_year)

    # Add current year's MTC if any
    if current_year_mtc > 0:
        carryforwards.append(MTCCarryforward(
            origin_year=current_year - 1,  # From prior year's AMT
            original_amount=current_year_mtc,
            amount_used=0.0,
        ))

    # Apply credit usage in FIFO order
    remaining_to_use = credit_used
    for cf in carryforwards:
        if remaining_to_use <= 0:
            break
        used = cf.use_credit(remaining_to_use)
        remaining_to_use -= used

    # Filter out fully used carryforwards
    return [cf for cf in carryforwards if cf.remaining > 0]


def estimate_mtc_benefit(
    mtc_available: float,
    expected_regular_tax: float,
    expected_tmt: float,
) -> dict:
    """
    Estimate MTC benefit for planning purposes.

    Args:
        mtc_available: Total MTC available
        expected_regular_tax: Expected regular tax
        expected_tmt: Expected TMT

    Returns:
        Estimated credit usage and carryforward
    """
    credit_limit = calculate_credit_limit(expected_regular_tax, expected_tmt)
    credit_usable = min(mtc_available, credit_limit)
    carryforward = mtc_available - credit_usable

    return {
        'mtc_available': mtc_available,
        'credit_limit': credit_limit,
        'credit_usable': credit_usable,
        'carryforward': carryforward,
        'tax_savings': credit_usable,
        'effective_rate': round(credit_usable / mtc_available * 100, 1) if mtc_available > 0 else 0.0,
        'years_to_use': (
            "All used this year" if carryforward == 0
            else f"~{int(carryforward / credit_usable) + 1} more years" if credit_usable > 0
            else "Credit limit is $0"
        ),
    }


def reconcile_amt_to_mtc(
    prior_year_amti: float,
    prior_year_adjustments: Dict[str, float],
    prior_year_exemption: float,
    prior_year_regular_tax: float,
    filing_status: str = "single",
) -> dict:
    """
    Reconcile prior year AMT to determine MTC generated.

    This is a detailed calculation that determines exactly
    how much MTC was generated from a prior year's AMT.

    Args:
        prior_year_amti: AMTI from prior year
        prior_year_adjustments: Dict of adjustment amounts by type
        prior_year_exemption: AMT exemption used
        prior_year_regular_tax: Regular tax in prior year
        filing_status: Filing status

    Returns:
        Detailed MTC calculation
    """
    # Separate deferral and exclusion items
    deferral_items = [
        'iso_exercise', 'depreciation', 'passive_activity',
        'long_term_contracts', 'mining_costs', 'research_costs',
        'circulation_costs', 'installment_sale',
    ]
    exclusion_items = [
        'private_activity_bond', 'depletion', 'intangible_drilling',
        'tax_shelter_farm',
    ]

    deferral_total = sum(
        prior_year_adjustments.get(item, 0.0) for item in deferral_items
    )
    exclusion_total = sum(
        prior_year_adjustments.get(item, 0.0) for item in exclusion_items
    )

    total_adjustments = deferral_total + exclusion_total

    # Calculate exclusion-only AMTI
    exclusion_amti = prior_year_amti - deferral_total

    # Calculate exclusion-only TMT
    threshold_28 = Form8801.THRESHOLD_28_2025.get(filing_status, 232600.0)
    exclusion_taxable = max(0, exclusion_amti - prior_year_exemption)

    if exclusion_taxable <= threshold_28:
        exclusion_tmt = exclusion_taxable * 0.26
    else:
        exclusion_tmt = (threshold_28 * 0.26) + ((exclusion_taxable - threshold_28) * 0.28)

    # Calculate total TMT
    total_taxable = max(0, prior_year_amti - prior_year_exemption)
    if total_taxable <= threshold_28:
        total_tmt = total_taxable * 0.26
    else:
        total_tmt = (threshold_28 * 0.26) + ((total_taxable - threshold_28) * 0.28)

    # AMT = TMT - Regular Tax (if positive)
    total_amt = max(0, total_tmt - prior_year_regular_tax)
    exclusion_amt = max(0, exclusion_tmt - prior_year_regular_tax)

    # MTC = Total AMT - Exclusion AMT
    mtc_generated = max(0, total_amt - exclusion_amt)

    return {
        'prior_year_amti': prior_year_amti,
        'deferral_adjustments': deferral_total,
        'exclusion_adjustments': exclusion_total,
        'exclusion_amti': exclusion_amti,
        'total_tmt': float(money(total_tmt)),
        'exclusion_tmt': float(money(exclusion_tmt)),
        'total_amt': float(money(total_amt)),
        'exclusion_amt': float(money(exclusion_amt)),
        'mtc_generated': float(money(mtc_generated)),
    }
