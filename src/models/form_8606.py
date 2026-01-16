"""
Form 8606: Nondeductible IRAs

IRS Form 8606 tracks:
- Part I: Nondeductible contributions to Traditional IRAs and distributions
- Part II: Conversions from Traditional/SEP/SIMPLE IRAs to Roth IRAs
- Part III: Distributions from Roth IRAs

Key Concepts:
- Basis: Cumulative nondeductible contributions (already taxed money)
- Pro-rata rule: Can't withdraw just basis; taxable portion based on ratio
- 5-year rules: For Roth conversions and contributions

References:
- IRS Form 8606 Instructions
- IRS Publication 590-A (Contributions)
- IRS Publication 590-B (Distributions)
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import date


class IRAType(str, Enum):
    """Types of IRAs for Form 8606 tracking."""
    TRADITIONAL = "traditional"
    SEP = "sep"
    SIMPLE = "simple"
    ROTH = "roth"
    INHERITED_TRADITIONAL = "inherited_traditional"
    INHERITED_ROTH = "inherited_roth"


class DistributionCode(str, Enum):
    """
    1099-R Distribution codes for Box 7.
    Per IRS 1099-R Instructions.
    """
    EARLY_NO_EXCEPTION = "1"  # Early distribution, no known exception
    EARLY_WITH_EXCEPTION = "2"  # Early distribution, exception applies
    DISABILITY = "3"  # Disability
    DEATH = "4"  # Death
    PROHIBITED_TRANSACTION = "5"  # Prohibited transaction
    SECTION_1035_EXCHANGE = "6"  # Section 1035 exchange
    NORMAL = "7"  # Normal distribution (age 59½+)
    EXCESS_CONTRIBUTION = "8"  # Excess contributions plus earnings
    PS_58_COST = "9"  # Cost of current life insurance protection
    SUBSTANTIALLY_EQUAL = "A"  # 72(t) substantially equal periodic payments
    RMD = "B"  # Designated Roth account distribution for RMD
    PLAN_TERMINATION = "E"  # Distributions from SIMPLE IRA in first 2 years
    CHARITABLE_GIFT = "F"  # Charitable gift annuity
    DIRECT_ROLLOVER_ROTH = "G"  # Direct rollover to Roth IRA
    DIRECT_ROLLOVER_QUALIFIED = "H"  # Direct rollover to qualified plan
    ROTH_CONVERSION = "J"  # Early Roth conversion
    ROTH_DISTRIBUTION_EXCEPTION = "T"  # Roth IRA, exception applies
    DIVIDEND_ESOP = "U"  # Dividend distribution from ESOP
    OTHER = "other"


class RothConversion(BaseModel):
    """
    Tracks a Roth IRA conversion from Traditional/SEP/SIMPLE IRA.

    Form 8606 Part II tracks conversions and calculates taxable portion.
    The 5-year rule applies separately to each conversion for early withdrawal.
    """
    conversion_date: str = Field(
        ...,
        description="Date of conversion (YYYY-MM-DD)"
    )
    conversion_amount: float = Field(
        ...,
        ge=0,
        description="Total amount converted to Roth IRA"
    )
    taxable_amount: float = Field(
        default=0.0,
        ge=0,
        description="Taxable portion of conversion (calculated)"
    )
    nontaxable_amount: float = Field(
        default=0.0,
        ge=0,
        description="Non-taxable portion (from basis)"
    )
    source_ira_type: IRAType = Field(
        default=IRAType.TRADITIONAL,
        description="Type of IRA converted from"
    )

    @field_validator('conversion_date')
    @classmethod
    def validate_date_format(cls, v):
        """Validate date format."""
        if v:
            try:
                date.fromisoformat(v)
            except ValueError:
                raise ValueError("conversion_date must be in YYYY-MM-DD format")
        return v

    def get_conversion_year(self) -> int:
        """Get the year of conversion for 5-year rule tracking."""
        return int(self.conversion_date[:4])


class RothContributionYear(BaseModel):
    """
    Tracks Roth IRA contributions by year for ordering rules.

    Roth distributions follow ordering rules:
    1. Regular contributions (tax-free, no penalty anytime)
    2. Conversion contributions (tax-free, 5-year rule for penalty)
    3. Earnings (taxable and 10% penalty if non-qualified)
    """
    tax_year: int = Field(..., description="Tax year of contribution")
    contribution_amount: float = Field(
        default=0.0,
        ge=0,
        description="Regular Roth IRA contributions for this year"
    )
    conversion_amount: float = Field(
        default=0.0,
        ge=0,
        description="Conversion amounts for this year (from Form 8606 Part II)"
    )

    def is_contribution_qualified(self, current_year: int) -> bool:
        """
        Check if contribution has met 5-year holding period.

        The 5-year period starts January 1 of the year of the first
        Roth IRA contribution (not the conversion).
        """
        return current_year >= self.tax_year + 5


class IRADistribution(BaseModel):
    """
    Tracks an IRA distribution from Form 1099-R.

    Used for calculating taxable portion of Traditional IRA distributions
    (Form 8606 Part I) and Roth IRA distributions (Form 8606 Part III).
    """
    ira_type: IRAType = Field(
        default=IRAType.TRADITIONAL,
        description="Type of IRA the distribution came from"
    )
    gross_distribution: float = Field(
        ...,
        ge=0,
        description="Box 1: Gross distribution amount"
    )
    taxable_amount: float = Field(
        default=None,
        description="Box 2a: Taxable amount (if known)"
    )
    taxable_amount_not_determined: bool = Field(
        default=True,
        description="Box 2b: Taxable amount not determined"
    )
    distribution_code: DistributionCode = Field(
        default=DistributionCode.NORMAL,
        description="Box 7: Distribution code"
    )
    is_ira_sep_simple: bool = Field(
        default=True,
        description="Box 7: IRA/SEP/SIMPLE checkbox"
    )
    federal_withholding: float = Field(
        default=0.0,
        ge=0,
        description="Box 4: Federal income tax withheld"
    )
    state_withholding: float = Field(
        default=0.0,
        ge=0,
        description="Box 14: State income tax withheld"
    )

    # For Roth distributions
    first_roth_contribution_year: Optional[int] = Field(
        default=None,
        description="Year of first Roth contribution (for 5-year rule)"
    )

    def is_early_distribution(self) -> bool:
        """Check if this is an early distribution (before age 59½)."""
        return self.distribution_code in [
            DistributionCode.EARLY_NO_EXCEPTION,
            DistributionCode.EARLY_WITH_EXCEPTION,
            DistributionCode.ROTH_CONVERSION,
        ]

    def is_qualified_roth_distribution(self, taxpayer_age: int, current_year: int) -> bool:
        """
        Check if Roth distribution is qualified (tax-free).

        A qualified distribution requires:
        1. 5-year holding period met (from first Roth contribution)
        2. AND one of: age 59½+, disability, death, first-time home ($10k max)
        """
        if self.ira_type != IRAType.ROTH:
            return False

        # Check 5-year rule
        if self.first_roth_contribution_year:
            five_year_met = current_year >= self.first_roth_contribution_year + 5
        else:
            five_year_met = False

        # Check qualifying event
        qualifying_event = (
            taxpayer_age >= 59 or
            self.distribution_code == DistributionCode.DISABILITY or
            self.distribution_code == DistributionCode.DEATH
        )

        return five_year_met and qualifying_event


class Form8606(BaseModel):
    """
    IRS Form 8606: Nondeductible IRAs

    This form tracks basis in Traditional IRAs and calculates taxable
    portions of distributions and Roth conversions.

    Part I: Nondeductible Contributions to Traditional IRAs
    Part II: Conversions to Roth IRAs
    Part III: Distributions from Roth IRAs
    """

    # ========== Part I: Traditional IRA Basis ==========

    # Line 1: Nondeductible contributions made this year
    nondeductible_contributions_current_year: float = Field(
        default=0.0,
        ge=0,
        description="Line 1: Nondeductible Traditional IRA contributions this year"
    )

    # Line 2: Total basis in Traditional IRAs (prior years)
    total_basis_prior_years: float = Field(
        default=0.0,
        ge=0,
        description="Line 2: Total basis from prior Form 8606 Line 14"
    )

    # Line 6: Value of ALL Traditional, SEP, and SIMPLE IRAs at year-end
    # Plus any outstanding rollovers
    year_end_value_all_traditional_iras: float = Field(
        default=0.0,
        ge=0,
        description="Line 6: Year-end value of all Traditional/SEP/SIMPLE IRAs"
    )

    # Line 7: Distributions from Traditional, SEP, and SIMPLE IRAs this year
    traditional_ira_distributions: float = Field(
        default=0.0,
        ge=0,
        description="Line 7: Total distributions from Traditional/SEP/SIMPLE IRAs"
    )

    # Line 8: Net amount converted to Roth IRA (goes to Part II)
    roth_conversion_amount: float = Field(
        default=0.0,
        ge=0,
        description="Line 8: Amount converted to Roth IRA this year"
    )

    # Detailed distribution tracking
    distributions: List[IRADistribution] = Field(
        default_factory=list,
        description="Detailed 1099-R distribution records"
    )

    # ========== Part II: Roth Conversions ==========

    roth_conversions: List[RothConversion] = Field(
        default_factory=list,
        description="Roth conversion history for 5-year tracking"
    )

    # ========== Part III: Roth IRA Distributions ==========

    # Roth contribution tracking for ordering rules
    roth_contribution_history: List[RothContributionYear] = Field(
        default_factory=list,
        description="Roth contribution history by year"
    )

    # Total Roth IRA contributions (regular, not conversions)
    total_roth_contributions: float = Field(
        default=0.0,
        ge=0,
        description="Line 19: Total regular Roth IRA contributions"
    )

    # Total Roth conversion contributions
    total_roth_conversions: float = Field(
        default=0.0,
        ge=0,
        description="Line 20: Total Roth conversion contributions"
    )

    # Roth IRA distributions this year
    roth_ira_distributions: float = Field(
        default=0.0,
        ge=0,
        description="Line 19: Total Roth IRA distributions this year"
    )

    # Year of first Roth contribution (for 5-year rule)
    first_roth_contribution_year: Optional[int] = Field(
        default=None,
        description="Year of first-ever Roth IRA contribution (for 5-year rule)"
    )

    # Taxpayer information for qualified distribution determination
    taxpayer_age: int = Field(
        default=0,
        ge=0,
        description="Taxpayer age at end of tax year"
    )

    is_disabled: bool = Field(
        default=False,
        description="Taxpayer is disabled per IRC 72(m)(7)"
    )

    is_beneficiary_distribution: bool = Field(
        default=False,
        description="Distribution is to beneficiary after owner's death"
    )

    # First-time homebuyer (up to $10,000 lifetime)
    first_time_homebuyer_amount: float = Field(
        default=0.0,
        ge=0,
        le=10000,
        description="Qualified first-time homebuyer distribution (max $10,000)"
    )

    # ========== Calculation Methods ==========

    def calculate_total_basis(self) -> float:
        """
        Calculate total basis in Traditional IRAs.

        Form 8606 Line 3:
        Total basis = Prior year basis + Current year nondeductible contributions
        """
        return self.total_basis_prior_years + self.nondeductible_contributions_current_year

    def calculate_nontaxable_percentage(self) -> float:
        """
        Calculate the non-taxable percentage for Traditional IRA distributions.

        Form 8606 Line 10 (percentage):
        Nontaxable % = Total Basis / (Year-end Value + Distributions + Conversions)

        This is the pro-rata rule - you cannot choose to withdraw only basis.
        """
        total_basis = self.calculate_total_basis()

        if total_basis <= 0:
            return 0.0

        # Line 9: Total value for pro-rata calculation
        # = Year-end value + Distributions + Conversions
        total_value = (
            self.year_end_value_all_traditional_iras +
            self.traditional_ira_distributions +
            self.roth_conversion_amount
        )

        if total_value <= 0:
            return 0.0

        # Cannot exceed 100%
        percentage = min(total_basis / total_value, 1.0)
        return round(percentage, 6)  # Keep 6 decimal places for accuracy

    def calculate_part_i(self) -> dict:
        """
        Calculate Form 8606 Part I: Traditional IRA distributions.

        Returns breakdown of taxable vs nontaxable portions.
        """
        # Line 3: Total basis
        total_basis = self.calculate_total_basis()

        # Line 7+8: Total distributions and conversions
        total_withdrawn = self.traditional_ira_distributions + self.roth_conversion_amount

        if total_withdrawn <= 0:
            return {
                'line_1_nondeductible_contributions': self.nondeductible_contributions_current_year,
                'line_2_prior_basis': self.total_basis_prior_years,
                'line_3_total_basis': total_basis,
                'line_6_year_end_value': self.year_end_value_all_traditional_iras,
                'line_7_distributions': self.traditional_ira_distributions,
                'line_8_conversions': self.roth_conversion_amount,
                'line_9_total_value': self.year_end_value_all_traditional_iras,
                'line_10_nontaxable_percentage': 0.0,
                'line_11_nontaxable_amount': 0.0,
                'line_13_taxable_amount': 0.0,
                'line_14_remaining_basis': total_basis,
            }

        # Line 9: Total value
        total_value = (
            self.year_end_value_all_traditional_iras +
            total_withdrawn
        )

        # Line 10: Nontaxable percentage
        if total_value > 0 and total_basis > 0:
            nontaxable_pct = min(total_basis / total_value, 1.0)
        else:
            nontaxable_pct = 0.0

        # Line 11: Nontaxable portion of distributions
        # (Line 7 + Line 8) × Line 10 percentage
        nontaxable_amount = round(total_withdrawn * nontaxable_pct, 2)

        # Line 13: Taxable portion
        taxable_amount = round(total_withdrawn - nontaxable_amount, 2)

        # Line 14: Remaining basis for next year
        remaining_basis = round(total_basis - nontaxable_amount, 2)

        return {
            'line_1_nondeductible_contributions': self.nondeductible_contributions_current_year,
            'line_2_prior_basis': self.total_basis_prior_years,
            'line_3_total_basis': total_basis,
            'line_6_year_end_value': self.year_end_value_all_traditional_iras,
            'line_7_distributions': self.traditional_ira_distributions,
            'line_8_conversions': self.roth_conversion_amount,
            'line_9_total_value': total_value,
            'line_10_nontaxable_percentage': round(nontaxable_pct * 100, 4),
            'line_11_nontaxable_amount': nontaxable_amount,
            'line_13_taxable_amount': taxable_amount,
            'line_14_remaining_basis': remaining_basis,
        }

    def calculate_part_ii_conversion(self) -> dict:
        """
        Calculate Form 8606 Part II: Roth Conversion taxable amount.

        The taxable portion of a Roth conversion is calculated using
        the same pro-rata rule as Part I distributions.
        """
        if self.roth_conversion_amount <= 0:
            return {
                'conversion_amount': 0.0,
                'taxable_conversion': 0.0,
                'nontaxable_conversion': 0.0,
            }

        # Use Part I calculation to get nontaxable percentage
        nontaxable_pct = self.calculate_nontaxable_percentage()

        # Calculate portions
        nontaxable_conversion = round(self.roth_conversion_amount * nontaxable_pct, 2)
        taxable_conversion = round(self.roth_conversion_amount - nontaxable_conversion, 2)

        return {
            'conversion_amount': self.roth_conversion_amount,
            'nontaxable_percentage': round(nontaxable_pct * 100, 4),
            'taxable_conversion': taxable_conversion,
            'nontaxable_conversion': nontaxable_conversion,
        }

    def calculate_part_iii_roth(self, current_year: int = 2025) -> dict:
        """
        Calculate Form 8606 Part III: Roth IRA distributions.

        Roth distributions follow ordering rules:
        1. Regular contributions (always tax-free and penalty-free)
        2. Conversion amounts (tax-free, but 5-year rule for penalty)
        3. Earnings (taxable and 10% penalty if non-qualified)

        Qualified distributions (5-year + age 59½/disability/death) are
        completely tax-free including earnings.
        """
        if self.roth_ira_distributions <= 0:
            return {
                'total_distribution': 0.0,
                'from_contributions': 0.0,
                'from_conversions': 0.0,
                'from_earnings': 0.0,
                'taxable_amount': 0.0,
                'penalty_amount': 0.0,
                'is_qualified': False,
            }

        # Check if distribution is qualified
        is_qualified = self._is_roth_distribution_qualified(current_year)

        if is_qualified:
            # Qualified distribution - entirely tax-free
            return {
                'total_distribution': self.roth_ira_distributions,
                'from_contributions': self.roth_ira_distributions,
                'from_conversions': 0.0,
                'from_earnings': 0.0,
                'taxable_amount': 0.0,
                'penalty_amount': 0.0,
                'is_qualified': True,
            }

        # Non-qualified distribution - apply ordering rules
        remaining = self.roth_ira_distributions
        from_contributions = 0.0
        from_conversions = 0.0
        from_earnings = 0.0
        penalty_amount = 0.0

        # Step 1: Regular contributions come out first (tax-free, no penalty)
        if remaining > 0 and self.total_roth_contributions > 0:
            from_contributions = min(remaining, self.total_roth_contributions)
            remaining -= from_contributions

        # Step 2: Conversion amounts (tax-free, but may have penalty)
        if remaining > 0 and self.total_roth_conversions > 0:
            from_conversions = min(remaining, self.total_roth_conversions)
            remaining -= from_conversions

            # Check 5-year rule for each conversion
            # Simplified: if any conversion is within 5 years, 10% penalty applies
            if self._has_recent_conversion(current_year):
                # 10% penalty on conversion amount if under 59½
                if self.taxpayer_age < 59:
                    penalty_amount += round(from_conversions * 0.10, 2)

        # Step 3: Earnings (taxable and 10% penalty if non-qualified)
        if remaining > 0:
            from_earnings = remaining

            # 10% penalty on earnings if under 59½
            if self.taxpayer_age < 59 and not self._has_penalty_exception():
                penalty_amount += round(from_earnings * 0.10, 2)

        return {
            'total_distribution': self.roth_ira_distributions,
            'from_contributions': from_contributions,
            'from_conversions': from_conversions,
            'from_earnings': from_earnings,
            'taxable_amount': from_earnings,  # Only earnings are taxable
            'penalty_amount': penalty_amount,
            'is_qualified': False,
        }

    def _is_roth_distribution_qualified(self, current_year: int) -> bool:
        """
        Check if Roth distribution is qualified.

        Requirements:
        1. 5-year holding period met (from first Roth contribution year)
        2. One of: age 59½+, disability, death, first-time home ($10k)
        """
        # Check 5-year rule
        if self.first_roth_contribution_year:
            five_year_met = current_year >= self.first_roth_contribution_year + 5
        else:
            five_year_met = False

        if not five_year_met:
            return False

        # Check qualifying event
        qualifying_event = (
            self.taxpayer_age >= 59 or
            self.is_disabled or
            self.is_beneficiary_distribution or
            self.first_time_homebuyer_amount > 0
        )

        return qualifying_event

    def _has_recent_conversion(self, current_year: int) -> bool:
        """Check if there are any conversions within the 5-year period."""
        for conversion in self.roth_conversions:
            if current_year < conversion.get_conversion_year() + 5:
                return True
        return False

    def _has_penalty_exception(self) -> bool:
        """Check if an exception to the 10% early withdrawal penalty applies."""
        return (
            self.is_disabled or
            self.is_beneficiary_distribution or
            self.first_time_homebuyer_amount > 0
        )

    def calculate_taxable_traditional_distribution(self) -> float:
        """
        Calculate taxable portion of Traditional IRA distributions.

        Returns the amount to include in taxable income (Form 1040 Line 4b).
        """
        result = self.calculate_part_i()
        return result['line_13_taxable_amount']

    def calculate_taxable_roth_distribution(self, current_year: int = 2025) -> float:
        """
        Calculate taxable portion of Roth IRA distributions.

        Only non-qualified earnings distributions are taxable.
        """
        result = self.calculate_part_iii_roth(current_year)
        return result['taxable_amount']

    def calculate_early_withdrawal_penalty(self, current_year: int = 2025) -> float:
        """
        Calculate 10% early withdrawal penalty.

        Applies to:
        - Traditional IRA distributions before age 59½ (unless exception)
        - Roth earnings before qualified (unless exception)
        - Roth conversions within 5 years before age 59½
        """
        total_penalty = 0.0

        # Traditional IRA early withdrawal penalty
        if self.taxpayer_age < 59 and not self._has_penalty_exception():
            if self.traditional_ira_distributions > 0:
                # 10% on taxable portion
                taxable = self.calculate_taxable_traditional_distribution()
                total_penalty += round(taxable * 0.10, 2)

        # Roth IRA penalties (from Part III calculation)
        roth_result = self.calculate_part_iii_roth(current_year)
        total_penalty += roth_result['penalty_amount']

        return total_penalty

    def get_remaining_basis(self) -> float:
        """
        Get remaining basis for next year's Form 8606.

        This becomes Line 2 on next year's Form 8606.
        """
        result = self.calculate_part_i()
        return result['line_14_remaining_basis']

    def generate_form_8606_summary(self, current_year: int = 2025) -> dict:
        """
        Generate complete Form 8606 summary for all three parts.
        """
        part_i = self.calculate_part_i()
        part_ii = self.calculate_part_ii_conversion()
        part_iii = self.calculate_part_iii_roth(current_year)

        return {
            'tax_year': current_year,
            'part_i_traditional_ira': part_i,
            'part_ii_roth_conversion': part_ii,
            'part_iii_roth_distribution': part_iii,
            'total_taxable_ira_income': (
                part_i['line_13_taxable_amount'] +
                part_ii['taxable_conversion'] +
                part_iii['taxable_amount']
            ),
            'total_early_withdrawal_penalty': self.calculate_early_withdrawal_penalty(current_year),
            'basis_carryforward': part_i['line_14_remaining_basis'],
        }


class IRAInfo(BaseModel):
    """
    Comprehensive IRA information for tax return.

    Consolidates Traditional and Roth IRA data needed for:
    - Contribution deductions (Schedule 1)
    - Distribution taxation (Form 1040, Form 8606)
    - Early withdrawal penalties (Form 5329)
    """

    # Form 8606 data
    form_8606: Optional[Form8606] = Field(
        default=None,
        description="Form 8606 basis and distribution tracking"
    )

    # Contribution information (ties to Deductions model)
    traditional_ira_contribution: float = Field(
        default=0.0,
        ge=0,
        description="Traditional IRA contributions for current year"
    )

    roth_ira_contribution: float = Field(
        default=0.0,
        ge=0,
        description="Roth IRA contributions for current year"
    )

    # Deductible portion (calculated based on phaseouts)
    deductible_traditional_contribution: float = Field(
        default=0.0,
        ge=0,
        description="Deductible portion of Traditional IRA contribution"
    )

    # Rollover information
    had_rollover: bool = Field(
        default=False,
        description="Had a rollover from qualified plan to IRA"
    )

    rollover_amount: float = Field(
        default=0.0,
        ge=0,
        description="Amount rolled over (not taxable)"
    )

    def get_nondeductible_contribution(self) -> float:
        """
        Calculate nondeductible Traditional IRA contribution.

        This is the amount that must be reported on Form 8606 Part I.
        """
        return max(0.0, self.traditional_ira_contribution - self.deductible_traditional_contribution)

    def get_taxable_distribution(self, current_year: int = 2025) -> float:
        """Get total taxable IRA distribution amount."""
        if not self.form_8606:
            return 0.0

        return (
            self.form_8606.calculate_taxable_traditional_distribution() +
            self.form_8606.calculate_taxable_roth_distribution(current_year)
        )

    def get_early_withdrawal_penalty(self, current_year: int = 2025) -> float:
        """Get 10% early withdrawal penalty amount."""
        if not self.form_8606:
            return 0.0

        return self.form_8606.calculate_early_withdrawal_penalty(current_year)

    def get_roth_conversion_taxable(self) -> float:
        """Get taxable amount from Roth conversions."""
        if not self.form_8606:
            return 0.0

        result = self.form_8606.calculate_part_ii_conversion()
        return result['taxable_conversion']
