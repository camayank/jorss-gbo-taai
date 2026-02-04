"""
Form 5498 - IRA Contribution Information

Complete IRS Form 5498 implementation for reporting IRA activity:

Reported by IRA trustees/custodians to IRS and account holders.
Reports contributions, rollovers, conversions, and FMV.

Key boxes:
- Box 1: IRA contributions (Traditional)
- Box 2: Rollover contributions
- Box 3: Roth IRA conversion amount
- Box 4: Recharacterized contributions
- Box 5: Fair market value (Dec 31)
- Box 7: IRA type (Traditional, Roth, SEP, SIMPLE)
- Box 8: SEP contributions
- Box 9: SIMPLE contributions
- Box 10: Roth IRA contributions
- Box 11: RMD required next year
- Box 12a-12b: RMD date and amount

2025 Contribution Limits:
- Traditional/Roth IRA: $7,000 ($8,000 if 50+)
- SEP IRA: 25% of compensation, max $69,000
- SIMPLE IRA: $16,000 ($19,500 if 50+)

Integration with:
- Form 1040 (IRA deduction)
- Form 8606 (nondeductible contributions)
- Schedule 1 (IRA deduction)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field, field_validator
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class IRAType(str, Enum):
    """Type of IRA account."""
    TRADITIONAL = "traditional"
    ROTH = "roth"
    SEP = "sep"
    SIMPLE = "simple"
    INHERITED_TRADITIONAL = "inherited_traditional"
    INHERITED_ROTH = "inherited_roth"


class ContributionType(str, Enum):
    """Type of IRA contribution."""
    REGULAR = "regular"  # Annual contribution
    ROLLOVER = "rollover"  # From another plan
    CONVERSION = "conversion"  # Traditional to Roth
    RECHARACTERIZATION = "recharacterization"  # Undo contribution type
    EMPLOYER_SEP = "employer_sep"  # SEP employer contribution
    EMPLOYER_SIMPLE = "employer_simple"  # SIMPLE employer contribution
    CATCH_UP = "catch_up"  # Age 50+ additional


class Form5498(BaseModel):
    """
    Form 5498 - IRA Contribution Information

    Reports IRA contributions, rollovers, and fair market value.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Trustee/Issuer Information
    trustee_name: str = Field(default="", description="Trustee/issuer name")
    trustee_tin: str = Field(default="", description="Trustee TIN/EIN")
    trustee_address: str = Field(default="", description="Trustee address")

    # Participant Information
    participant_name: str = Field(default="", description="Participant name")
    participant_tin: str = Field(default="", description="Participant SSN")
    account_number: str = Field(default="", description="Account number")

    # Box 1: IRA contributions (Traditional IRA)
    box_1_ira_contributions: float = Field(
        default=0.0, ge=0,
        description="Box 1: Traditional IRA contributions"
    )

    # Box 2: Rollover contributions
    box_2_rollover_contributions: float = Field(
        default=0.0, ge=0,
        description="Box 2: Rollover contributions"
    )

    # Box 3: Roth IRA conversion amount
    box_3_roth_conversion: float = Field(
        default=0.0, ge=0,
        description="Box 3: Roth IRA conversion amount"
    )

    # Box 4: Recharacterized contributions
    box_4_recharacterized: float = Field(
        default=0.0, ge=0,
        description="Box 4: Recharacterized contributions"
    )

    # Box 5: Fair market value of account (Dec 31)
    box_5_fmv: float = Field(
        default=0.0, ge=0,
        description="Box 5: Fair market value"
    )

    # Box 6: Life insurance cost included in box 1
    box_6_life_insurance: float = Field(
        default=0.0, ge=0,
        description="Box 6: Life insurance cost"
    )

    # Box 7: IRA type checkboxes
    box_7_ira_type: IRAType = Field(
        default=IRAType.TRADITIONAL,
        description="Box 7: Type of IRA"
    )

    # Box 8: SEP contributions
    box_8_sep_contributions: float = Field(
        default=0.0, ge=0,
        description="Box 8: SEP contributions"
    )

    # Box 9: SIMPLE contributions
    box_9_simple_contributions: float = Field(
        default=0.0, ge=0,
        description="Box 9: SIMPLE contributions"
    )

    # Box 10: Roth IRA contributions
    box_10_roth_contributions: float = Field(
        default=0.0, ge=0,
        description="Box 10: Roth IRA contributions"
    )

    # Box 11: Check if RMD required for next year
    box_11_rmd_required: bool = Field(
        default=False,
        description="Box 11: RMD required next year"
    )

    # Box 12a: RMD date
    box_12a_rmd_date: Optional[date] = Field(
        default=None,
        description="Box 12a: RMD date"
    )

    # Box 12b: RMD amount
    box_12b_rmd_amount: float = Field(
        default=0.0, ge=0,
        description="Box 12b: RMD amount"
    )

    # Box 13a: Postponed/late contribution for prior year
    box_13a_postponed_contribution: float = Field(
        default=0.0, ge=0,
        description="Box 13a: Postponed contribution"
    )

    # Box 13b: Year the postponed contribution was for
    box_13b_postponed_year: Optional[int] = Field(
        default=None,
        description="Box 13b: Year for postponed contribution"
    )

    # Box 13c: Repayment code
    box_13c_repayment_code: str = Field(
        default="",
        description="Box 13c: Repayment code"
    )

    # Box 14a: FMV of certain specified assets
    box_14a_specified_assets_fmv: float = Field(
        default=0.0, ge=0,
        description="Box 14a: FMV of specified assets"
    )

    # Box 14b: Code for specified assets
    box_14b_specified_assets_code: str = Field(
        default="",
        description="Box 14b: Specified assets code"
    )

    # Box 15a: FMV of all IRA assets
    box_15a_total_fmv: float = Field(
        default=0.0, ge=0,
        description="Box 15a: Total FMV of IRA assets"
    )

    # Box 15b: Code
    box_15b_code: str = Field(
        default="",
        description="Box 15b: Code"
    )

    @computed_field
    @property
    def total_contributions(self) -> float:
        """Total contributions for the year."""
        return (
            self.box_1_ira_contributions +
            self.box_8_sep_contributions +
            self.box_9_simple_contributions +
            self.box_10_roth_contributions
        )

    @computed_field
    @property
    def is_traditional(self) -> bool:
        """Check if this is a Traditional IRA."""
        return self.box_7_ira_type in [IRAType.TRADITIONAL, IRAType.INHERITED_TRADITIONAL]

    @computed_field
    @property
    def is_roth(self) -> bool:
        """Check if this is a Roth IRA."""
        return self.box_7_ira_type in [IRAType.ROTH, IRAType.INHERITED_ROTH]

    @computed_field
    @property
    def is_employer_plan(self) -> bool:
        """Check if this is an employer-sponsored IRA (SEP/SIMPLE)."""
        return self.box_7_ira_type in [IRAType.SEP, IRAType.SIMPLE]


class IRAContributionLimits(BaseModel):
    """
    IRA contribution limits for a tax year.

    Limits vary by age, type of IRA, and income.
    """
    tax_year: int = Field(default=2025, description="Tax year")

    # Traditional/Roth IRA limits
    ira_limit: float = Field(
        default=7000.0,
        description="Traditional/Roth IRA limit"
    )
    ira_catch_up: float = Field(
        default=1000.0,
        description="Catch-up contribution (age 50+)"
    )

    # SEP IRA limits
    sep_limit: float = Field(
        default=69000.0,
        description="SEP IRA maximum contribution"
    )
    sep_percentage: float = Field(
        default=0.25,
        description="SEP percentage of compensation"
    )

    # SIMPLE IRA limits
    simple_limit: float = Field(
        default=16000.0,
        description="SIMPLE IRA employee limit"
    )
    simple_catch_up: float = Field(
        default=3500.0,
        description="SIMPLE catch-up (age 50+)"
    )

    # Roth IRA income phase-out (single filer)
    roth_phaseout_single_start: float = Field(
        default=150000.0,
        description="Roth phase-out start (single)"
    )
    roth_phaseout_single_end: float = Field(
        default=165000.0,
        description="Roth phase-out end (single)"
    )

    # Roth IRA income phase-out (MFJ)
    roth_phaseout_mfj_start: float = Field(
        default=236000.0,
        description="Roth phase-out start (MFJ)"
    )
    roth_phaseout_mfj_end: float = Field(
        default=246000.0,
        description="Roth phase-out end (MFJ)"
    )

    # Traditional IRA deduction phase-out (single, with retirement plan)
    trad_phaseout_single_start: float = Field(
        default=77000.0,
        description="Traditional phase-out start (single)"
    )
    trad_phaseout_single_end: float = Field(
        default=87000.0,
        description="Traditional phase-out end (single)"
    )

    # Traditional IRA deduction phase-out (MFJ, with retirement plan)
    trad_phaseout_mfj_start: float = Field(
        default=123000.0,
        description="Traditional phase-out start (MFJ)"
    )
    trad_phaseout_mfj_end: float = Field(
        default=143000.0,
        description="Traditional phase-out end (MFJ)"
    )

    def get_max_contribution(
        self,
        ira_type: IRAType,
        age: int,
        compensation: float = 0.0,
    ) -> float:
        """
        Get maximum contribution for given IRA type and age.

        Args:
            ira_type: Type of IRA
            age: Account holder's age
            compensation: Earned income/compensation

        Returns:
            Maximum allowable contribution
        """
        is_catch_up_eligible = age >= 50

        if ira_type == IRAType.SEP:
            # 25% of compensation or limit, whichever is less
            return min(compensation * self.sep_percentage, self.sep_limit)

        elif ira_type == IRAType.SIMPLE:
            base = self.simple_limit
            if is_catch_up_eligible:
                base += self.simple_catch_up
            return min(base, compensation) if compensation > 0 else base

        else:  # Traditional or Roth
            base = self.ira_limit
            if is_catch_up_eligible:
                base += self.ira_catch_up
            # Cannot contribute more than earned income
            if compensation > 0:
                return min(base, compensation)
            return base

    def calculate_roth_limit(
        self,
        magi: float,
        filing_status: str,
        age: int,
    ) -> float:
        """
        Calculate Roth IRA contribution limit after income phase-out.

        Args:
            magi: Modified AGI
            filing_status: Filing status
            age: Account holder's age

        Returns:
            Allowable Roth contribution
        """
        base_limit = self.ira_limit
        if age >= 50:
            base_limit += self.ira_catch_up

        # Get phase-out range
        if filing_status.lower() in ['mfj', 'married_filing_jointly']:
            start = self.roth_phaseout_mfj_start
            end = self.roth_phaseout_mfj_end
        else:
            start = self.roth_phaseout_single_start
            end = self.roth_phaseout_single_end

        if magi <= start:
            return base_limit
        elif magi >= end:
            return 0.0
        else:
            # Pro-rata reduction
            reduction_pct = (magi - start) / (end - start)
            reduced = base_limit * (1 - reduction_pct)
            # Round up to nearest $10
            return max(0, float(to_decimal(reduced).quantize(Decimal("10"), rounding=ROUND_HALF_UP)))

    def calculate_traditional_deduction_limit(
        self,
        magi: float,
        filing_status: str,
        has_retirement_plan: bool,
        age: int,
    ) -> float:
        """
        Calculate deductible Traditional IRA contribution limit.

        Args:
            magi: Modified AGI
            filing_status: Filing status
            has_retirement_plan: Covered by employer retirement plan
            age: Account holder's age

        Returns:
            Deductible contribution limit
        """
        base_limit = self.ira_limit
        if age >= 50:
            base_limit += self.ira_catch_up

        # No phase-out if not covered by retirement plan
        if not has_retirement_plan:
            return base_limit

        # Get phase-out range
        if filing_status.lower() in ['mfj', 'married_filing_jointly']:
            start = self.trad_phaseout_mfj_start
            end = self.trad_phaseout_mfj_end
        else:
            start = self.trad_phaseout_single_start
            end = self.trad_phaseout_single_end

        if magi <= start:
            return base_limit
        elif magi >= end:
            return 0.0
        else:
            reduction_pct = (magi - start) / (end - start)
            reduced = base_limit * (1 - reduction_pct)
            return max(0, float(to_decimal(reduced).quantize(Decimal("10"), rounding=ROUND_HALF_UP)))


class IRASummary(BaseModel):
    """
    Summary of all IRA activity for a taxpayer.

    Aggregates multiple Form 5498s and calculates totals.
    """
    tax_year: int = Field(default=2025, description="Tax year")
    forms: List[Form5498] = Field(
        default_factory=list,
        description="All Form 5498s received"
    )

    # Taxpayer information for limit calculations
    age: int = Field(default=0, ge=0, description="Taxpayer age")
    magi: float = Field(default=0.0, ge=0, description="Modified AGI")
    filing_status: str = Field(default="single", description="Filing status")
    has_retirement_plan: bool = Field(
        default=False,
        description="Covered by employer retirement plan"
    )
    earned_income: float = Field(default=0.0, ge=0, description="Earned income")

    def add_form(self, form: Form5498) -> None:
        """Add a Form 5498 to the summary."""
        self.forms.append(form)

    @computed_field
    @property
    def total_traditional_contributions(self) -> float:
        """Total Traditional IRA contributions."""
        return sum(f.box_1_ira_contributions for f in self.forms)

    @computed_field
    @property
    def total_roth_contributions(self) -> float:
        """Total Roth IRA contributions."""
        return sum(f.box_10_roth_contributions for f in self.forms)

    @computed_field
    @property
    def total_sep_contributions(self) -> float:
        """Total SEP IRA contributions."""
        return sum(f.box_8_sep_contributions for f in self.forms)

    @computed_field
    @property
    def total_simple_contributions(self) -> float:
        """Total SIMPLE IRA contributions."""
        return sum(f.box_9_simple_contributions for f in self.forms)

    @computed_field
    @property
    def total_rollovers(self) -> float:
        """Total rollover contributions."""
        return sum(f.box_2_rollover_contributions for f in self.forms)

    @computed_field
    @property
    def total_conversions(self) -> float:
        """Total Roth conversions."""
        return sum(f.box_3_roth_conversion for f in self.forms)

    @computed_field
    @property
    def total_fmv(self) -> float:
        """Total fair market value of all IRAs."""
        return sum(f.box_5_fmv for f in self.forms)

    @computed_field
    @property
    def total_rmd_required(self) -> float:
        """Total RMD required for next year."""
        return sum(f.box_12b_rmd_amount for f in self.forms if f.box_11_rmd_required)

    @computed_field
    @property
    def accounts_requiring_rmd(self) -> int:
        """Number of accounts requiring RMD."""
        return sum(1 for f in self.forms if f.box_11_rmd_required)

    def get_deductible_ira_contribution(self) -> float:
        """Calculate deductible Traditional IRA contribution."""
        limits = IRAContributionLimits(tax_year=self.tax_year)
        max_deductible = limits.calculate_traditional_deduction_limit(
            magi=self.magi,
            filing_status=self.filing_status,
            has_retirement_plan=self.has_retirement_plan,
            age=self.age,
        )
        return min(self.total_traditional_contributions, max_deductible)

    def get_nondeductible_ira_contribution(self) -> float:
        """Calculate nondeductible Traditional IRA contribution (Form 8606)."""
        deductible = self.get_deductible_ira_contribution()
        return max(0, self.total_traditional_contributions - deductible)

    def to_schedule_1(self) -> Dict[str, float]:
        """Get amounts for Schedule 1 (IRA deduction)."""
        return {
            "line_20_ira_deduction": self.get_deductible_ira_contribution(),
            "line_16_sep_deduction": self.total_sep_contributions,
            "line_15_simple_deduction": self.total_simple_contributions,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tax_year": self.tax_year,
            "account_count": len(self.forms),
            "contributions": {
                "traditional": self.total_traditional_contributions,
                "roth": self.total_roth_contributions,
                "sep": self.total_sep_contributions,
                "simple": self.total_simple_contributions,
                "rollovers": self.total_rollovers,
                "conversions": self.total_conversions,
            },
            "deduction": {
                "deductible": self.get_deductible_ira_contribution(),
                "nondeductible": self.get_nondeductible_ira_contribution(),
            },
            "fmv": {
                "total": self.total_fmv,
            },
            "rmd": {
                "required_next_year": self.total_rmd_required,
                "accounts_affected": self.accounts_requiring_rmd,
            },
        }


def calculate_ira_contribution_limit(
    ira_type: str,
    age: int,
    earned_income: float,
    magi: float = 0.0,
    filing_status: str = "single",
    has_retirement_plan: bool = False,
    tax_year: int = 2025,
) -> Dict[str, Any]:
    """
    Convenience function to calculate IRA contribution limits.

    Args:
        ira_type: Type of IRA (traditional, roth, sep, simple)
        age: Account holder's age
        earned_income: Earned income/compensation
        magi: Modified AGI (for Roth/Traditional phase-out)
        filing_status: Tax filing status
        has_retirement_plan: Covered by employer plan
        tax_year: Tax year

    Returns:
        Dictionary with contribution limits and phase-out details
    """
    limits = IRAContributionLimits(tax_year=tax_year)
    ira_enum = IRAType(ira_type.lower())

    max_contribution = limits.get_max_contribution(
        ira_type=ira_enum,
        age=age,
        compensation=earned_income,
    )

    result = {
        "ira_type": ira_type,
        "age": age,
        "catch_up_eligible": age >= 50,
        "max_contribution": max_contribution,
    }

    if ira_type.lower() == "roth":
        roth_limit = limits.calculate_roth_limit(magi, filing_status, age)
        result["after_phaseout"] = roth_limit
        result["phaseout_applied"] = roth_limit < max_contribution

    elif ira_type.lower() == "traditional":
        deductible = limits.calculate_traditional_deduction_limit(
            magi, filing_status, has_retirement_plan, age
        )
        result["deductible_limit"] = deductible
        result["nondeductible_allowed"] = max_contribution - deductible
        result["has_retirement_plan"] = has_retirement_plan

    return result


def calculate_rmd(
    account_balance: float,
    owner_age: int,
    account_type: str = "traditional",
) -> Dict[str, Any]:
    """
    Calculate Required Minimum Distribution.

    Uses Uniform Lifetime Table for most cases.

    Args:
        account_balance: Account balance as of Dec 31 prior year
        owner_age: Owner's age in distribution year
        account_type: Type of account

    Returns:
        Dictionary with RMD calculation
    """
    # Uniform Lifetime Table (simplified for common ages)
    # Full table has entries for ages 72-120
    life_expectancy_table = {
        72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6,
        76: 23.7, 77: 22.9, 78: 22.0, 79: 21.1,
        80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7,
        84: 16.8, 85: 16.0, 86: 15.2, 87: 14.4,
        88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5,
        92: 10.8, 93: 10.1, 94: 9.5, 95: 8.9,
    }

    # RMD not required until age 73 (SECURE 2.0)
    if owner_age < 73:
        return {
            "rmd_required": False,
            "rmd_amount": 0.0,
            "reason": "Under RMD age (73)",
        }

    # Roth IRAs don't require RMDs for original owner
    if account_type.lower() == "roth":
        return {
            "rmd_required": False,
            "rmd_amount": 0.0,
            "reason": "Roth IRA - no RMD for original owner",
        }

    # Get life expectancy factor
    factor = life_expectancy_table.get(owner_age, 10.0)  # Default for very old

    rmd_amount = account_balance / factor

    return {
        "rmd_required": True,
        "account_balance": account_balance,
        "age": owner_age,
        "life_expectancy_factor": factor,
        "rmd_amount": float(money(rmd_amount)),
        "deadline": "April 1 (first year) or December 31",
    }
