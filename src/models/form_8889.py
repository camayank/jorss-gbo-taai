"""
Form 8889 - Health Savings Accounts (HSAs)

Implements IRS Form 8889 for reporting HSA contributions, distributions,
and calculating the HSA deduction.

Reference: IRS Instructions for Form 8889
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
from models._decimal_utils import money, to_decimal


class HSACoverageType(str, Enum):
    """HSA-eligible HDHP coverage type."""
    SELF_ONLY = "self_only"
    FAMILY = "family"


class HDHPCoverageMonth(BaseModel):
    """
    Track HDHP coverage for each month.

    Used for pro-rata contribution limit calculation when not
    covered by an HDHP for the entire year.
    """
    month: int = Field(ge=1, le=12, description="Month number (1-12)")
    has_hdhp_coverage: bool = Field(default=True, description="Had HDHP coverage this month")
    coverage_type: HSACoverageType = Field(
        default=HSACoverageType.SELF_ONLY,
        description="Coverage type for this month"
    )


class HSADistribution(BaseModel):
    """
    Individual HSA distribution.

    Used to track distributions for qualified vs non-qualified purposes.
    """
    amount: float = Field(ge=0, description="Distribution amount")
    qualified_medical_expense: bool = Field(
        default=True,
        description="Was distribution for qualified medical expenses"
    )
    description: Optional[str] = Field(None, description="Description of expense")
    date: Optional[str] = Field(None, description="Date of distribution (YYYY-MM-DD)")

    # Special distribution types
    is_rollover_to_another_hsa: bool = Field(
        default=False,
        description="Trustee-to-trustee transfer to another HSA"
    )
    is_excess_contribution_withdrawal: bool = Field(
        default=False,
        description="Withdrawal of excess contributions before due date"
    )


class HSAContribution(BaseModel):
    """
    Individual HSA contribution.

    Tracks contributions by source (employer vs individual).
    """
    amount: float = Field(ge=0, description="Contribution amount")
    is_employer_contribution: bool = Field(
        default=False,
        description="Contribution made by employer (Box 12 code W)"
    )
    is_rollover: bool = Field(
        default=False,
        description="Rollover from another HSA or Archer MSA"
    )
    is_qualified_funding_distribution: bool = Field(
        default=False,
        description="One-time transfer from IRA (Form 8889 Line 10)"
    )
    description: Optional[str] = None


class Form8889(BaseModel):
    """
    Form 8889 - Health Savings Accounts (HSAs)

    Complete HSA tracking for contribution limits, deductions, and
    distribution taxation per IRS Form 8889.

    Key Rules:
    - Must have HDHP (High Deductible Health Plan) to contribute
    - Cannot be enrolled in Medicare
    - Cannot be claimed as dependent on another's return
    - Contribution limits: $4,300 self-only, $8,550 family (2025)
    - Catch-up contribution: $1,000 if age 55+ by year end
    - 20% penalty on non-qualified distributions (unless 65+, disabled, or deceased)
    """

    # Part I: HSA Contributions and Deduction

    # Coverage information
    coverage_type: HSACoverageType = Field(
        default=HSACoverageType.SELF_ONLY,
        description="Type of HDHP coverage"
    )

    # Monthly coverage tracking (for pro-rata calculation)
    # If not provided, assumes full-year coverage
    monthly_coverage: List[HDHPCoverageMonth] = Field(
        default_factory=list,
        description="Monthly HDHP coverage details"
    )

    # Number of months with HDHP coverage (alternative to monthly_coverage)
    months_with_hdhp_coverage: int = Field(
        default=12,
        ge=0,
        le=12,
        description="Number of months with HDHP coverage"
    )

    # Age-related
    is_age_55_or_older: bool = Field(
        default=False,
        description="Taxpayer (or spouse for family) is 55+ by year end"
    )

    # Eligibility restrictions
    is_enrolled_in_medicare: bool = Field(
        default=False,
        description="Enrolled in any part of Medicare"
    )
    can_be_claimed_as_dependent: bool = Field(
        default=False,
        description="Can be claimed as dependent on another's return"
    )

    # Contributions
    contributions: List[HSAContribution] = Field(
        default_factory=list,
        description="Individual HSA contributions"
    )

    # Simple contribution fields (alternative to detailed list)
    taxpayer_contributions: float = Field(
        default=0.0,
        ge=0,
        description="Line 2: Contributions made by taxpayer"
    )
    employer_contributions: float = Field(
        default=0.0,
        ge=0,
        description="Line 9: Employer contributions (Box 12 code W)"
    )

    # Rollovers and special contributions
    rollover_contributions: float = Field(
        default=0.0,
        ge=0,
        description="Line 10: Qualified HSA funding distribution from IRA (once per lifetime)"
    )

    # Last-month rule election
    use_last_month_rule: bool = Field(
        default=False,
        description="Elect last-month rule (covered Dec 1, treat as full year)"
    )

    # Testing period failure (if used last-month rule in prior year)
    failed_testing_period: bool = Field(
        default=False,
        description="Failed to maintain HDHP coverage during testing period"
    )
    testing_period_income: float = Field(
        default=0.0,
        ge=0,
        description="Amount to include in income for testing period failure"
    )

    # Part II: HSA Distributions

    distributions: List[HSADistribution] = Field(
        default_factory=list,
        description="Individual HSA distributions"
    )

    # Simple distribution fields (alternative to detailed list)
    total_distributions: float = Field(
        default=0.0,
        ge=0,
        description="Line 14a: Total distributions from all HSAs"
    )
    qualified_medical_expenses: float = Field(
        default=0.0,
        ge=0,
        description="Line 15: Qualified medical expenses paid"
    )

    # Distribution exemptions
    is_disabled: bool = Field(
        default=False,
        description="Taxpayer is disabled (no penalty on distributions)"
    )
    is_deceased_account: bool = Field(
        default=False,
        description="Account of deceased person (no penalty)"
    )
    is_age_65_or_older: bool = Field(
        default=False,
        description="Age 65+ (no penalty, but taxable if not for medical)"
    )

    # Form 1099-SA information (if received)
    form_1099sa_gross_distribution: float = Field(
        default=0.0,
        ge=0,
        description="Form 1099-SA Box 1: Gross distribution"
    )
    form_1099sa_earnings_on_excess: float = Field(
        default=0.0,
        ge=0,
        description="Form 1099-SA Box 2: Earnings on excess contributions"
    )

    # Archer MSA rollover
    archer_msa_rollover: float = Field(
        default=0.0,
        ge=0,
        description="Rollover from Archer MSA"
    )

    @model_validator(mode='after')
    def validate_coverage_months(self):
        """Sync months_with_hdhp_coverage with monthly_coverage if provided."""
        if self.monthly_coverage:
            covered_months = sum(1 for m in self.monthly_coverage if m.has_hdhp_coverage)
            self.months_with_hdhp_coverage = covered_months
        return self

    def get_total_taxpayer_contributions(self) -> float:
        """Get total contributions made by taxpayer (not employer)."""
        if self.contributions:
            return sum(
                c.amount for c in self.contributions
                if not c.is_employer_contribution and not c.is_rollover
            )
        return self.taxpayer_contributions

    def get_total_employer_contributions(self) -> float:
        """Get total employer contributions (Box 12 code W on W-2)."""
        if self.contributions:
            return sum(
                c.amount for c in self.contributions
                if c.is_employer_contribution
            )
        return self.employer_contributions

    def get_total_rollovers(self) -> float:
        """Get total rollover amounts."""
        if self.contributions:
            return sum(c.amount for c in self.contributions if c.is_rollover)
        return self.rollover_contributions

    def get_total_distributions(self) -> float:
        """Get total HSA distributions."""
        if self.distributions:
            return sum(d.amount for d in self.distributions)
        return max(self.total_distributions, self.form_1099sa_gross_distribution)

    def get_qualified_distributions(self) -> float:
        """Get distributions used for qualified medical expenses."""
        if self.distributions:
            return sum(
                d.amount for d in self.distributions
                if d.qualified_medical_expense
            )
        return min(self.qualified_medical_expenses, self.get_total_distributions())

    def get_taxable_distributions(self) -> float:
        """
        Calculate taxable portion of distributions.

        Taxable = Total distributions - Qualified medical expenses
        """
        total = self.get_total_distributions()
        qualified = self.get_qualified_distributions()

        # Rollovers and excess contribution withdrawals are not taxable
        if self.distributions:
            rollovers = sum(
                d.amount for d in self.distributions
                if d.is_rollover_to_another_hsa or d.is_excess_contribution_withdrawal
            )
            total -= rollovers

        return max(0, total - qualified)

    def calculate_contribution_limit(
        self,
        self_only_limit: float = 4300.0,
        family_limit: float = 8550.0,
        catchup_amount: float = 1000.0,
    ) -> float:
        """
        Calculate annual HSA contribution limit.

        Limit depends on:
        - Coverage type (self-only vs family)
        - Number of months covered by HDHP
        - Age (55+ gets additional catch-up)
        - Last-month rule election

        Returns the maximum allowable contribution for the year.
        """
        # Base limit by coverage type
        if self.coverage_type == HSACoverageType.FAMILY:
            base_limit = family_limit
        else:
            base_limit = self_only_limit

        # Add catch-up contribution if 55+
        if self.is_age_55_or_older:
            base_limit += catchup_amount

        # Pro-rate based on months of coverage
        if self.use_last_month_rule:
            # Last-month rule: If covered on Dec 1, get full year limit
            # But must remain eligible for testing period (following year)
            months = 12
        else:
            months = self.months_with_hdhp_coverage

        pro_rated_limit = base_limit * (months / 12)

        return float(money(pro_rated_limit))

    def calculate_deduction(
        self,
        self_only_limit: float = 4300.0,
        family_limit: float = 8550.0,
        catchup_amount: float = 1000.0,
    ) -> dict:
        """
        Calculate HSA deduction (Form 8889 Line 13).

        Deduction = Lesser of:
        - Total contributions (taxpayer + employer)
        - Contribution limit

        Then subtract employer contributions (already excluded from wages).

        Returns dict with calculation breakdown.
        """
        # Check eligibility
        if self.is_enrolled_in_medicare or self.can_be_claimed_as_dependent:
            return {
                'contribution_limit': 0.0,
                'taxpayer_contributions': 0.0,
                'employer_contributions': 0.0,
                'total_contributions': 0.0,
                'hsa_deduction': 0.0,
                'excess_contributions': 0.0,
                'is_eligible': False,
                'ineligibility_reason': (
                    'Enrolled in Medicare' if self.is_enrolled_in_medicare
                    else 'Can be claimed as dependent'
                ),
            }

        # Calculate limit
        limit = self.calculate_contribution_limit(
            self_only_limit, family_limit, catchup_amount
        )

        # Get contribution amounts
        taxpayer = self.get_total_taxpayer_contributions()
        employer = self.get_total_employer_contributions()
        total = taxpayer + employer

        # Limit check (Line 3 vs Line 5)
        limited_contribution = min(total, limit)

        # Deduction is limited contribution minus employer (Line 13)
        # Employer contributions are already excluded from W-2 Box 1
        deduction = max(0, limited_contribution - employer)

        # Excess contributions subject to 6% excise tax
        excess = max(0, total - limit)

        return {
            'contribution_limit': float(money(limit)),
            'taxpayer_contributions': float(money(taxpayer)),
            'employer_contributions': float(money(employer)),
            'total_contributions': float(money(total)),
            'limited_contribution': float(money(limited_contribution)),
            'hsa_deduction': float(money(deduction)),
            'excess_contributions': float(money(excess)),
            'is_eligible': True,
            'months_covered': self.months_with_hdhp_coverage,
            'used_last_month_rule': self.use_last_month_rule,
        }

    def calculate_additional_tax(
        self,
        penalty_rate: float = 0.20
    ) -> dict:
        """
        Calculate additional tax on non-qualified distributions.

        20% penalty applies unless:
        - Age 65 or older
        - Disabled
        - Deceased account holder

        Returns dict with tax calculation breakdown.
        """
        taxable = self.get_taxable_distributions()

        # Check for penalty exemptions
        is_exempt = (
            self.is_age_65_or_older or
            self.is_disabled or
            self.is_deceased_account
        )

        if is_exempt:
            penalty = 0.0
            exemption_reason = (
                'Age 65+' if self.is_age_65_or_older else
                'Disabled' if self.is_disabled else
                'Deceased account'
            )
        else:
            penalty = taxable * penalty_rate
            exemption_reason = None

        # Testing period failure income (from prior year last-month rule)
        testing_income = self.testing_period_income if self.failed_testing_period else 0.0
        testing_penalty = testing_income * penalty_rate if testing_income > 0 else 0.0

        return {
            'total_distributions': float(money(self.get_total_distributions())),
            'qualified_distributions': float(money(self.get_qualified_distributions())),
            'taxable_distributions': float(money(taxable)),
            'is_penalty_exempt': is_exempt,
            'exemption_reason': exemption_reason,
            'additional_tax_penalty': float(money(penalty)),
            'testing_period_income': float(money(testing_income)),
            'testing_period_penalty': float(money(testing_penalty)),
            'total_additional_tax': float(money(penalty + testing_penalty)),
        }

    def generate_form_8889_summary(
        self,
        self_only_limit: float = 4300.0,
        family_limit: float = 8550.0,
        catchup_amount: float = 1000.0,
    ) -> dict:
        """
        Generate complete Form 8889 summary.

        Returns all calculated values for the form.
        """
        deduction_calc = self.calculate_deduction(
            self_only_limit, family_limit, catchup_amount
        )
        tax_calc = self.calculate_additional_tax()

        return {
            # Part I - Contributions
            'part_i': {
                'line_1_coverage_type': self.coverage_type.value,
                'line_2_taxpayer_contributions': deduction_calc['taxpayer_contributions'],
                'line_3_contribution_limit': deduction_calc['contribution_limit'],
                'line_4_employer_contributions_excluded': 0.0,  # Already in limit
                'line_5_line_3_minus_line_4': deduction_calc['contribution_limit'],
                'line_6_contributions_plus_line_4': deduction_calc['total_contributions'],
                'line_7_smaller_of_5_or_6': deduction_calc['limited_contribution'],
                'line_8_not_used': 0.0,
                'line_9_employer_contributions': deduction_calc['employer_contributions'],
                'line_10_qualified_funding_distribution': self.rollover_contributions,
                'line_11_line_9_plus_10': deduction_calc['employer_contributions'] + self.rollover_contributions,
                'line_12_line_7_minus_11': max(0, deduction_calc['limited_contribution'] - deduction_calc['employer_contributions'] - self.rollover_contributions),
                'line_13_hsa_deduction': deduction_calc['hsa_deduction'],
            },
            # Part II - Distributions
            'part_ii': {
                'line_14a_total_distributions': tax_calc['total_distributions'],
                'line_14b_rollover_amount': self.archer_msa_rollover,
                'line_14c_line_14a_minus_14b': tax_calc['total_distributions'] - self.archer_msa_rollover,
                'line_15_qualified_expenses': tax_calc['qualified_distributions'],
                'line_16_taxable_distributions': tax_calc['taxable_distributions'],
                'line_17a_is_exempt': tax_calc['is_penalty_exempt'],
                'line_17b_additional_tax': tax_calc['additional_tax_penalty'],
            },
            # Part III - Testing Period
            'part_iii': {
                'line_18_testing_period_income': tax_calc['testing_period_income'],
                'line_19_testing_period_penalty': tax_calc['testing_period_penalty'],
            },
            # Summary
            'summary': {
                'hsa_deduction': deduction_calc['hsa_deduction'],
                'taxable_distributions': tax_calc['taxable_distributions'],
                'additional_tax': tax_calc['total_additional_tax'],
                'excess_contributions': deduction_calc['excess_contributions'],
                'is_eligible': deduction_calc['is_eligible'],
            }
        }


class HSAInfo(BaseModel):
    """
    Simplified HSA information for basic returns.

    Use Form8889 for detailed tracking; this is for simple cases.
    """
    coverage_type: HSACoverageType = Field(
        default=HSACoverageType.SELF_ONLY,
        description="HDHP coverage type"
    )
    taxpayer_contributions: float = Field(
        default=0.0,
        ge=0,
        description="Contributions made by taxpayer"
    )
    employer_contributions: float = Field(
        default=0.0,
        ge=0,
        description="Employer contributions (W-2 Box 12 code W)"
    )
    distributions: float = Field(
        default=0.0,
        ge=0,
        description="Total distributions"
    )
    qualified_expenses: float = Field(
        default=0.0,
        ge=0,
        description="Qualified medical expenses"
    )
    is_age_55_or_older: bool = Field(
        default=False,
        description="Age 55+ for catch-up contribution"
    )
    is_age_65_or_older: bool = Field(
        default=False,
        description="Age 65+ (no distribution penalty)"
    )
    months_covered: int = Field(
        default=12,
        ge=0,
        le=12,
        description="Months with HDHP coverage"
    )

    def to_form_8889(self) -> Form8889:
        """Convert simple HSAInfo to full Form8889."""
        return Form8889(
            coverage_type=self.coverage_type,
            taxpayer_contributions=self.taxpayer_contributions,
            employer_contributions=self.employer_contributions,
            total_distributions=self.distributions,
            qualified_medical_expenses=self.qualified_expenses,
            is_age_55_or_older=self.is_age_55_or_older,
            is_age_65_or_older=self.is_age_65_or_older,
            months_with_hdhp_coverage=self.months_covered,
        )
