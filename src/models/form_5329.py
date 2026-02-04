"""
Form 5329: Additional Taxes on Qualified Plans (Including IRAs) and Other Tax-Favored Accounts

This form calculates additional taxes on:
- Part I: Early distributions from qualified retirement plans (10% penalty)
- Part II: Excess contributions to Traditional IRAs (6% excise tax)
- Part III: Excess contributions to Roth IRAs (6% excise tax)
- Part IV: Excess contributions to Coverdell ESAs (6% excise tax)
- Part V: Excess contributions to Archer MSAs (6% excise tax)
- Part VI: Excess contributions to HSAs (6% excise tax)
- Part VII: Excess contributions to ABLE accounts (6% excise tax)
- Part VIII: Additional tax on excess accumulations (RMD failure - 25%/10%)
- Part IX: Additional tax on excess contributions to Section 529 plans (6%)

References:
- IRS Form 5329 and Instructions
- IRS Publication 590-B (Distributions from IRAs)
- IRC Section 72(t) - Early withdrawal penalty exceptions
- IRC Section 4973 - Excess contribution penalties
- IRC Section 4974 - RMD failure penalty
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class EarlyDistributionExceptionCode(str, Enum):
    """
    Exception codes for the 10% early distribution penalty.

    Per IRC Section 72(t) and Form 5329 instructions.
    """
    # No exception
    NO_EXCEPTION = "00"

    # Separation from service after age 55 (employer plans only)
    SEPARATION_AFTER_55 = "01"

    # Substantially equal periodic payments (SEPP / 72(t))
    SEPP = "02"

    # Disability (IRC 72(m)(7))
    DISABILITY = "03"

    # Death (to beneficiary or estate)
    DEATH = "04"

    # Medical expenses exceeding 7.5% of AGI
    MEDICAL_EXPENSES = "05"

    # Health insurance premiums while unemployed
    HEALTH_INSURANCE_UNEMPLOYED = "06"

    # Higher education expenses
    HIGHER_EDUCATION = "07"

    # First-time homebuyer ($10,000 lifetime limit)
    FIRST_HOME = "08"

    # IRS levy
    IRS_LEVY = "09"

    # Qualified reservist distribution
    RESERVIST = "10"

    # Roth IRA - return of contributions
    ROTH_CONTRIBUTIONS = "11"

    # Qualified birth or adoption distribution (up to $5,000)
    BIRTH_ADOPTION = "12"

    # Qualified disaster distribution
    DISASTER = "13"

    # Domestic abuse victim distribution (SECURE 2.0)
    DOMESTIC_ABUSE = "14"

    # Terminal illness
    TERMINAL_ILLNESS = "15"

    # Emergency personal expense distribution (SECURE 2.0 - $1,000/year)
    EMERGENCY_EXPENSE = "16"

    # Federal disaster distribution (SECURE 2.0)
    FEDERAL_DISASTER = "17"

    # Corrective distribution of excess contributions
    EXCESS_CONTRIBUTION_CORRECTION = "18"

    # Separation from service in year turning 55 (public safety employees: 50)
    SEPARATION_PUBLIC_SAFETY_50 = "19"


class EarlyDistribution(BaseModel):
    """
    Tracks an early distribution subject to potential 10% penalty.

    Used for Form 5329 Part I calculations.
    """
    distribution_amount: float = Field(
        ...,
        ge=0,
        description="Total early distribution amount from 1099-R Box 1"
    )
    taxable_amount: Optional[float] = Field(
        default=None,
        description="Taxable portion (Box 2a). If None, equals distribution_amount"
    )
    exception_code: EarlyDistributionExceptionCode = Field(
        default=EarlyDistributionExceptionCode.NO_EXCEPTION,
        description="Exception code from Form 5329 or 1099-R Box 7"
    )
    exception_amount: float = Field(
        default=0.0,
        ge=0,
        description="Amount qualifying for exception (may be partial)"
    )
    source_plan_type: str = Field(
        default="IRA",
        description="Type of plan: IRA, 401k, 403b, etc."
    )

    def get_taxable_amount(self) -> float:
        """Get taxable amount, defaulting to full distribution if not specified."""
        if self.taxable_amount is not None:
            return self.taxable_amount
        return self.distribution_amount

    def get_amount_subject_to_penalty(self) -> float:
        """Calculate amount subject to 10% penalty after exceptions."""
        taxable = self.get_taxable_amount()

        # If exception covers entire taxable amount
        if self.exception_code != EarlyDistributionExceptionCode.NO_EXCEPTION:
            if self.exception_amount >= taxable:
                return 0.0
            return max(0.0, taxable - self.exception_amount)

        return taxable


class ExcessContribution(BaseModel):
    """
    Tracks excess contributions to tax-advantaged accounts.

    Excess contributions are subject to 6% excise tax each year
    they remain in the account.
    """
    account_type: str = Field(
        ...,
        description="Type: traditional_ira, roth_ira, coverdell_esa, archer_msa, hsa, able, 529"
    )

    # Current year excess
    current_year_contributions: float = Field(
        default=0.0,
        ge=0,
        description="Total contributions made this year"
    )
    contribution_limit: float = Field(
        default=0.0,
        ge=0,
        description="Maximum allowable contribution for this year"
    )

    # Prior year excess carryover
    prior_year_excess: float = Field(
        default=0.0,
        ge=0,
        description="Excess contributions from prior years not yet corrected"
    )

    # Corrections made this year
    excess_withdrawn: float = Field(
        default=0.0,
        ge=0,
        description="Excess contributions withdrawn before tax filing deadline"
    )
    earnings_on_excess_withdrawn: float = Field(
        default=0.0,
        ge=0,
        description="Earnings on excess contributions also withdrawn"
    )
    recharacterized_amount: float = Field(
        default=0.0,
        ge=0,
        description="Amount recharacterized to another IRA type"
    )

    # Applied to prior year
    applied_to_prior_year: float = Field(
        default=0.0,
        ge=0,
        description="Amount applied as prior year contribution (if under prior limit)"
    )

    def calculate_current_year_excess(self) -> float:
        """Calculate excess contributions made this year."""
        excess = max(0.0, self.current_year_contributions - self.contribution_limit)
        return excess

    def calculate_total_excess(self) -> float:
        """
        Calculate total excess subject to 6% penalty.

        Formula:
        Total Excess = Prior Year Excess + Current Year Excess
                      - Excess Withdrawn - Recharacterized - Applied to Prior
        """
        current_excess = self.calculate_current_year_excess()

        total_excess = (
            self.prior_year_excess +
            current_excess -
            self.excess_withdrawn -
            self.recharacterized_amount -
            self.applied_to_prior_year
        )

        return max(0.0, total_excess)

    def calculate_excise_tax(self, rate: float = 0.06) -> float:
        """Calculate 6% excise tax on excess contributions."""
        excess = self.calculate_total_excess()
        return float(money(excess * rate))


class RMDFailure(BaseModel):
    """
    Tracks Required Minimum Distribution (RMD) failures.

    Per IRC Section 4974, failure to take RMD results in:
    - 25% excise tax on the shortfall
    - Reduced to 10% if corrected during the "correction window"
      (by end of 2nd year after the year of the failure)
    """
    required_minimum_distribution: float = Field(
        ...,
        ge=0,
        description="RMD amount that should have been taken"
    )
    actual_distribution: float = Field(
        default=0.0,
        ge=0,
        description="Actual distribution taken"
    )
    account_type: str = Field(
        default="traditional_ira",
        description="Type of account: traditional_ira, 401k, 403b, etc."
    )
    rmd_year: int = Field(
        ...,
        description="Year for which RMD was required"
    )

    # Correction status
    is_corrected_timely: bool = Field(
        default=False,
        description="RMD shortfall corrected within correction window (10% rate)"
    )
    reasonable_cause_waiver_requested: bool = Field(
        default=False,
        description="Request penalty waiver for reasonable cause"
    )

    def calculate_shortfall(self) -> float:
        """Calculate RMD shortfall."""
        return max(0.0, self.required_minimum_distribution - self.actual_distribution)

    def calculate_excise_tax(self) -> float:
        """
        Calculate excise tax on RMD failure.

        - 25% standard rate
        - 10% if corrected timely
        - 0% if reasonable cause waiver granted (must request on Form 5329)
        """
        shortfall = self.calculate_shortfall()

        if shortfall <= 0:
            return 0.0

        if self.reasonable_cause_waiver_requested:
            # Waiver request - taxpayer includes 0 on line and attaches explanation
            return 0.0

        rate = 0.10 if self.is_corrected_timely else 0.25
        return float(money(shortfall * rate))


class Form5329(BaseModel):
    """
    IRS Form 5329: Additional Taxes on Qualified Plans and Other Tax-Favored Accounts

    Calculates all additional taxes/penalties on retirement and tax-advantaged accounts.
    """

    # Taxpayer information
    taxpayer_age: int = Field(
        default=0,
        ge=0,
        description="Taxpayer age at end of tax year (for 59½ determination)"
    )
    tax_year: int = Field(
        default=2025,
        description="Tax year for the form"
    )

    # ========== Part I: Early Distributions ==========

    early_distributions: List[EarlyDistribution] = Field(
        default_factory=list,
        description="All early distributions from qualified plans and IRAs"
    )

    # Total from 1099-R forms
    total_early_distributions_from_1099r: float = Field(
        default=0.0,
        ge=0,
        description="Line 1: Total early distributions from Form 1099-R"
    )

    # ========== Part II: Traditional IRA Excess Contributions ==========

    traditional_ira_excess: Optional[ExcessContribution] = Field(
        default=None,
        description="Traditional IRA excess contribution details"
    )

    # ========== Part III: Roth IRA Excess Contributions ==========

    roth_ira_excess: Optional[ExcessContribution] = Field(
        default=None,
        description="Roth IRA excess contribution details"
    )

    # ========== Part IV: Coverdell ESA Excess Contributions ==========

    coverdell_esa_excess: Optional[ExcessContribution] = Field(
        default=None,
        description="Coverdell ESA excess contribution details"
    )

    # ========== Part V: Archer MSA Excess Contributions ==========

    archer_msa_excess: Optional[ExcessContribution] = Field(
        default=None,
        description="Archer MSA excess contribution details"
    )

    # ========== Part VI: HSA Excess Contributions ==========

    hsa_excess: Optional[ExcessContribution] = Field(
        default=None,
        description="HSA excess contribution details"
    )

    # ========== Part VII: ABLE Account Excess Contributions ==========

    able_excess: Optional[ExcessContribution] = Field(
        default=None,
        description="ABLE account excess contribution details"
    )

    # ========== Part VIII: RMD Failures ==========

    rmd_failures: List[RMDFailure] = Field(
        default_factory=list,
        description="Required minimum distribution failures"
    )

    # ========== Part IX: Section 529 Excess Contributions ==========

    section_529_excess: Optional[ExcessContribution] = Field(
        default=None,
        description="Section 529 plan excess contribution details"
    )

    # ========== Calculation Methods ==========

    def calculate_part_i_early_distribution_penalty(self) -> dict:
        """
        Calculate Part I: Additional Tax on Early Distributions.

        10% penalty on taxable early distributions unless an exception applies.
        """
        total_distributions = 0.0
        total_exceptions = 0.0
        exception_details = []

        for dist in self.early_distributions:
            taxable = dist.get_taxable_amount()
            total_distributions += taxable

            if dist.exception_code != EarlyDistributionExceptionCode.NO_EXCEPTION:
                exception_amount = min(dist.exception_amount, taxable)
                if dist.exception_amount == 0:
                    # Full exception
                    exception_amount = taxable
                total_exceptions += exception_amount
                exception_details.append({
                    'code': dist.exception_code.value,
                    'amount': exception_amount,
                    'description': dist.exception_code.name,
                })

        # If we have 1099-R total but no detailed distributions, use that
        if not self.early_distributions and self.total_early_distributions_from_1099r > 0:
            total_distributions = self.total_early_distributions_from_1099r

        amount_subject_to_penalty = max(0.0, total_distributions - total_exceptions)
        penalty = float(money(amount_subject_to_penalty * 0.10))

        return {
            'line_1_total_distributions': float(money(total_distributions)),
            'line_2_exceptions': float(money(total_exceptions)),
            'line_3_subject_to_penalty': float(money(amount_subject_to_penalty)),
            'line_4_penalty': penalty,
            'exception_details': exception_details,
        }

    def calculate_part_ii_traditional_ira_excess(self) -> dict:
        """Calculate Part II: Traditional IRA excess contribution penalty."""
        if not self.traditional_ira_excess:
            return {
                'excess_amount': 0.0,
                'excise_tax': 0.0,
            }

        excess = self.traditional_ira_excess.calculate_total_excess()
        tax = self.traditional_ira_excess.calculate_excise_tax()

        return {
            'prior_year_excess': self.traditional_ira_excess.prior_year_excess,
            'current_year_contributions': self.traditional_ira_excess.current_year_contributions,
            'contribution_limit': self.traditional_ira_excess.contribution_limit,
            'current_year_excess': self.traditional_ira_excess.calculate_current_year_excess(),
            'corrections': (
                self.traditional_ira_excess.excess_withdrawn +
                self.traditional_ira_excess.recharacterized_amount +
                self.traditional_ira_excess.applied_to_prior_year
            ),
            'excess_amount': float(money(excess)),
            'excise_tax': tax,
        }

    def calculate_part_iii_roth_ira_excess(self) -> dict:
        """Calculate Part III: Roth IRA excess contribution penalty."""
        if not self.roth_ira_excess:
            return {
                'excess_amount': 0.0,
                'excise_tax': 0.0,
            }

        excess = self.roth_ira_excess.calculate_total_excess()
        tax = self.roth_ira_excess.calculate_excise_tax()

        return {
            'prior_year_excess': self.roth_ira_excess.prior_year_excess,
            'current_year_contributions': self.roth_ira_excess.current_year_contributions,
            'contribution_limit': self.roth_ira_excess.contribution_limit,
            'current_year_excess': self.roth_ira_excess.calculate_current_year_excess(),
            'corrections': (
                self.roth_ira_excess.excess_withdrawn +
                self.roth_ira_excess.recharacterized_amount
            ),
            'excess_amount': float(money(excess)),
            'excise_tax': tax,
        }

    def calculate_part_iv_coverdell_excess(self) -> dict:
        """Calculate Part IV: Coverdell ESA excess contribution penalty."""
        if not self.coverdell_esa_excess:
            return {'excess_amount': 0.0, 'excise_tax': 0.0}

        return {
            'excess_amount': float(money(self.coverdell_esa_excess.calculate_total_excess())),
            'excise_tax': self.coverdell_esa_excess.calculate_excise_tax(),
        }

    def calculate_part_v_archer_msa_excess(self) -> dict:
        """Calculate Part V: Archer MSA excess contribution penalty."""
        if not self.archer_msa_excess:
            return {'excess_amount': 0.0, 'excise_tax': 0.0}

        return {
            'excess_amount': float(money(self.archer_msa_excess.calculate_total_excess())),
            'excise_tax': self.archer_msa_excess.calculate_excise_tax(),
        }

    def calculate_part_vi_hsa_excess(self) -> dict:
        """Calculate Part VI: HSA excess contribution penalty."""
        if not self.hsa_excess:
            return {'excess_amount': 0.0, 'excise_tax': 0.0}

        return {
            'excess_amount': float(money(self.hsa_excess.calculate_total_excess())),
            'excise_tax': self.hsa_excess.calculate_excise_tax(),
        }

    def calculate_part_vii_able_excess(self) -> dict:
        """Calculate Part VII: ABLE account excess contribution penalty."""
        if not self.able_excess:
            return {'excess_amount': 0.0, 'excise_tax': 0.0}

        return {
            'excess_amount': float(money(self.able_excess.calculate_total_excess())),
            'excise_tax': self.able_excess.calculate_excise_tax(),
        }

    def calculate_part_viii_rmd_penalty(self) -> dict:
        """
        Calculate Part VIII: Additional Tax on Excess Accumulations (RMD failure).

        - 25% penalty on RMD shortfall
        - 10% if corrected during correction window
        """
        total_shortfall = 0.0
        total_penalty = 0.0
        failure_details = []

        for failure in self.rmd_failures:
            shortfall = failure.calculate_shortfall()
            penalty = failure.calculate_excise_tax()

            total_shortfall += shortfall
            total_penalty += penalty

            failure_details.append({
                'account_type': failure.account_type,
                'rmd_year': failure.rmd_year,
                'required': failure.required_minimum_distribution,
                'actual': failure.actual_distribution,
                'shortfall': shortfall,
                'is_corrected_timely': failure.is_corrected_timely,
                'waiver_requested': failure.reasonable_cause_waiver_requested,
                'penalty': penalty,
            })

        return {
            'total_shortfall': float(money(total_shortfall)),
            'total_penalty': float(money(total_penalty)),
            'failure_details': failure_details,
        }

    def calculate_part_ix_529_excess(self) -> dict:
        """Calculate Part IX: Section 529 excess contribution penalty."""
        if not self.section_529_excess:
            return {'excess_amount': 0.0, 'excise_tax': 0.0}

        return {
            'excess_amount': float(money(self.section_529_excess.calculate_total_excess())),
            'excise_tax': self.section_529_excess.calculate_excise_tax(),
        }

    def calculate_total_additional_tax(self) -> float:
        """Calculate total additional tax from all parts of Form 5329."""
        total = 0.0

        # Part I: Early distribution penalty
        part_i = self.calculate_part_i_early_distribution_penalty()
        total += part_i['line_4_penalty']

        # Part II: Traditional IRA excess
        part_ii = self.calculate_part_ii_traditional_ira_excess()
        total += part_ii['excise_tax']

        # Part III: Roth IRA excess
        part_iii = self.calculate_part_iii_roth_ira_excess()
        total += part_iii['excise_tax']

        # Part IV: Coverdell ESA excess
        part_iv = self.calculate_part_iv_coverdell_excess()
        total += part_iv['excise_tax']

        # Part V: Archer MSA excess
        part_v = self.calculate_part_v_archer_msa_excess()
        total += part_v['excise_tax']

        # Part VI: HSA excess
        part_vi = self.calculate_part_vi_hsa_excess()
        total += part_vi['excise_tax']

        # Part VII: ABLE excess
        part_vii = self.calculate_part_vii_able_excess()
        total += part_vii['excise_tax']

        # Part VIII: RMD penalty
        part_viii = self.calculate_part_viii_rmd_penalty()
        total += part_viii['total_penalty']

        # Part IX: 529 excess
        part_ix = self.calculate_part_ix_529_excess()
        total += part_ix['excise_tax']

        return float(money(total))

    def generate_form_5329_summary(self) -> dict:
        """Generate complete Form 5329 summary."""
        part_i = self.calculate_part_i_early_distribution_penalty()
        part_ii = self.calculate_part_ii_traditional_ira_excess()
        part_iii = self.calculate_part_iii_roth_ira_excess()
        part_iv = self.calculate_part_iv_coverdell_excess()
        part_v = self.calculate_part_v_archer_msa_excess()
        part_vi = self.calculate_part_vi_hsa_excess()
        part_vii = self.calculate_part_vii_able_excess()
        part_viii = self.calculate_part_viii_rmd_penalty()
        part_ix = self.calculate_part_ix_529_excess()

        return {
            'tax_year': self.tax_year,
            'taxpayer_age': self.taxpayer_age,
            'part_i_early_distribution': part_i,
            'part_ii_traditional_ira_excess': part_ii,
            'part_iii_roth_ira_excess': part_iii,
            'part_iv_coverdell_esa_excess': part_iv,
            'part_v_archer_msa_excess': part_v,
            'part_vi_hsa_excess': part_vi,
            'part_vii_able_excess': part_vii,
            'part_viii_rmd_failure': part_viii,
            'part_ix_529_excess': part_ix,
            'total_additional_tax': self.calculate_total_additional_tax(),
        }

    # ========== Helper Methods for Common Scenarios ==========

    def add_early_distribution(
        self,
        amount: float,
        taxable_amount: float = None,
        exception_code: EarlyDistributionExceptionCode = EarlyDistributionExceptionCode.NO_EXCEPTION,
        exception_amount: float = 0.0,
        source_plan_type: str = "IRA",
    ) -> None:
        """Add an early distribution to the form."""
        dist = EarlyDistribution(
            distribution_amount=amount,
            taxable_amount=taxable_amount,
            exception_code=exception_code,
            exception_amount=exception_amount,
            source_plan_type=source_plan_type,
        )
        self.early_distributions.append(dist)

    def add_traditional_ira_excess(
        self,
        contributions: float,
        limit: float,
        prior_year_excess: float = 0.0,
        withdrawn: float = 0.0,
    ) -> None:
        """Add Traditional IRA excess contribution."""
        self.traditional_ira_excess = ExcessContribution(
            account_type="traditional_ira",
            current_year_contributions=contributions,
            contribution_limit=limit,
            prior_year_excess=prior_year_excess,
            excess_withdrawn=withdrawn,
        )

    def add_roth_ira_excess(
        self,
        contributions: float,
        limit: float,
        prior_year_excess: float = 0.0,
        withdrawn: float = 0.0,
    ) -> None:
        """Add Roth IRA excess contribution."""
        self.roth_ira_excess = ExcessContribution(
            account_type="roth_ira",
            current_year_contributions=contributions,
            contribution_limit=limit,
            prior_year_excess=prior_year_excess,
            excess_withdrawn=withdrawn,
        )

    def add_rmd_failure(
        self,
        required_amount: float,
        actual_amount: float,
        rmd_year: int,
        account_type: str = "traditional_ira",
        is_corrected: bool = False,
        waiver_requested: bool = False,
    ) -> None:
        """Add an RMD failure."""
        failure = RMDFailure(
            required_minimum_distribution=required_amount,
            actual_distribution=actual_amount,
            account_type=account_type,
            rmd_year=rmd_year,
            is_corrected_timely=is_corrected,
            reasonable_cause_waiver_requested=waiver_requested,
        )
        self.rmd_failures.append(failure)


# ========== IRA Contribution Limits for Reference ==========

IRA_CONTRIBUTION_LIMITS_2025 = {
    'traditional_ira_base': 7000.0,
    'traditional_ira_catchup_50_plus': 1000.0,
    'roth_ira_base': 7000.0,
    'roth_ira_catchup_50_plus': 1000.0,
    'coverdell_esa': 2000.0,
    'able_account_base': 18000.0,  # Same as gift tax exclusion
    'able_account_employed': 14580.0,  # Additional for employed beneficiaries
}

ROTH_IRA_MAGI_LIMITS_2025 = {
    'single': {'phaseout_start': 150000.0, 'phaseout_end': 165000.0},
    'married_joint': {'phaseout_start': 236000.0, 'phaseout_end': 246000.0},
    'married_separate': {'phaseout_start': 0.0, 'phaseout_end': 10000.0},
}


def calculate_roth_contribution_limit(
    magi: float,
    filing_status: str,
    is_age_50_plus: bool = False,
) -> float:
    """
    Calculate allowed Roth IRA contribution based on MAGI phaseout.

    Returns the maximum Roth IRA contribution allowed.
    """
    base_limit = IRA_CONTRIBUTION_LIMITS_2025['roth_ira_base']
    if is_age_50_plus:
        base_limit += IRA_CONTRIBUTION_LIMITS_2025['roth_ira_catchup_50_plus']

    limits = ROTH_IRA_MAGI_LIMITS_2025.get(filing_status, ROTH_IRA_MAGI_LIMITS_2025['single'])
    phaseout_start = limits['phaseout_start']
    phaseout_end = limits['phaseout_end']

    if magi <= phaseout_start:
        return base_limit
    elif magi >= phaseout_end:
        return 0.0
    else:
        # Linear phaseout
        phaseout_range = phaseout_end - phaseout_start
        excess = magi - phaseout_start
        reduction_ratio = excess / phaseout_range
        reduced = base_limit * (1 - reduction_ratio)
        # Round to nearest $10, minimum $200
        if reduced > 0 and reduced < 200:
            return 200.0
        return float(to_decimal(reduced).quantize(Decimal("10"), rounding=ROUND_HALF_UP))
