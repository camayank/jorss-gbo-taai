"""
Domain Value Objects for Tax Decision Intelligence Platform.

Value objects are immutable objects that describe characteristics of a thing,
but have no conceptual identity. They are defined by their attributes.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class PriorYearSummary(BaseModel):
    """
    Summary of prior year tax return for reference and analysis.

    Used for year-over-year comparisons and safe harbor calculations.
    """
    tax_year: int = Field(description="The prior tax year")

    # Key metrics
    total_income: float = Field(default=0.0, description="Gross income from prior year")
    adjusted_gross_income: float = Field(default=0.0, description="AGI from prior year")
    taxable_income: float = Field(default=0.0, description="Taxable income from prior year")
    total_tax: float = Field(default=0.0, description="Total tax liability from prior year")
    effective_rate: float = Field(default=0.0, description="Effective tax rate from prior year")

    # Filing details
    filing_status: str = Field(default="single", description="Filing status used")
    state_of_residence: Optional[str] = Field(default=None, description="State of residence")

    # Deduction details
    used_standard_deduction: bool = Field(default=True, description="Whether standard deduction was used")
    total_deduction: float = Field(default=0.0, description="Total deduction amount")

    # Payments
    total_withholding: float = Field(default=0.0, description="Total withholding from prior year")
    estimated_payments: float = Field(default=0.0, description="Estimated tax payments made")

    # Results
    refund_or_owed: float = Field(default=0.0, description="Refund (positive) or amount owed (negative)")


class PriorYearCarryovers(BaseModel):
    """
    Comprehensive prior year carryforward amounts.

    Consolidates all tax attributes that carry forward from prior years,
    including capital losses, charitable contributions, NOLs, credits, etc.

    IRS References:
    - Capital losses: IRC Section 1212
    - Charitable contributions: IRC Section 170(d)
    - NOLs: IRC Section 172
    - AMT credit: IRC Section 53
    - Foreign tax credit: IRC Section 904
    - General business credit: IRC Section 39
    """

    # =========================================================================
    # Capital Loss Carryovers (IRC Section 1212)
    # =========================================================================
    short_term_capital_loss_carryover: float = Field(
        default=0.0, ge=0,
        description="Short-term capital loss carryforward from prior year"
    )
    long_term_capital_loss_carryover: float = Field(
        default=0.0, ge=0,
        description="Long-term capital loss carryforward from prior year"
    )

    # =========================================================================
    # Charitable Contribution Carryovers (IRC Section 170(d))
    # =========================================================================
    # 60% AGI limit contributions (cash to public charities)
    charitable_cash_60pct_carryover: float = Field(
        default=0.0, ge=0,
        description="Carryover of cash contributions subject to 60% AGI limit"
    )
    # 50% AGI limit contributions (cash to private foundations)
    charitable_cash_50pct_carryover: float = Field(
        default=0.0, ge=0,
        description="Carryover of cash contributions subject to 50% AGI limit"
    )
    # 30% AGI limit contributions (capital gain property to public charities)
    charitable_property_30pct_carryover: float = Field(
        default=0.0, ge=0,
        description="Carryover of property contributions subject to 30% AGI limit"
    )
    # 20% AGI limit contributions (capital gain property to private foundations)
    charitable_property_20pct_carryover: float = Field(
        default=0.0, ge=0,
        description="Carryover of property contributions subject to 20% AGI limit"
    )
    # Years remaining for charitable carryover (5-year limit)
    charitable_carryover_year_originated: Optional[int] = Field(
        default=None,
        description="Tax year when charitable carryover originated (expires after 5 years)"
    )

    # =========================================================================
    # Net Operating Loss (NOL) Carryovers (IRC Section 172)
    # =========================================================================
    nol_carryover: float = Field(
        default=0.0, ge=0,
        description="Net operating loss carryforward from prior years"
    )
    # Post-2017 NOLs are limited to 80% of taxable income
    nol_carryover_post_2017: float = Field(
        default=0.0, ge=0,
        description="NOL carryforward from tax years after 2017 (80% limitation applies)"
    )
    # Pre-2018 NOLs (no percentage limitation, but have expiration)
    nol_carryover_pre_2018: float = Field(
        default=0.0, ge=0,
        description="NOL carryforward from tax years before 2018 (20-year expiration)"
    )
    nol_carryover_expiration_year: Optional[int] = Field(
        default=None,
        description="Expiration year for oldest pre-2018 NOL"
    )

    # =========================================================================
    # Alternative Minimum Tax (AMT) Credit Carryover (IRC Section 53)
    # =========================================================================
    amt_credit_carryover: float = Field(
        default=0.0, ge=0,
        description="Minimum tax credit carryforward from prior years (Form 8801)"
    )
    # Detailed breakdown by year for Form 8801
    amt_credit_by_year: Dict[int, float] = Field(
        default_factory=dict,
        description="AMT credit carryforward broken down by origin year"
    )

    # =========================================================================
    # Foreign Tax Credit Carryovers (IRC Section 904)
    # =========================================================================
    foreign_tax_credit_carryover: float = Field(
        default=0.0, ge=0,
        description="Total foreign tax credit carryforward"
    )
    # FTC can be carried back 1 year or forward 10 years
    ftc_carryover_by_year: Dict[int, float] = Field(
        default_factory=dict,
        description="Foreign tax credit carryforward by origin year (10-year carryforward)"
    )
    ftc_carryover_by_category: Dict[str, float] = Field(
        default_factory=dict,
        description="Foreign tax credit carryforward by income category (general, passive, etc.)"
    )

    # =========================================================================
    # General Business Credit Carryovers (IRC Section 39)
    # =========================================================================
    general_business_credit_carryover: float = Field(
        default=0.0, ge=0,
        description="General business credit carryforward (1-year back, 20-year forward)"
    )
    gbc_carryover_by_component: Dict[str, float] = Field(
        default_factory=dict,
        description="GBC carryforward by credit component (R&D, investment, etc.)"
    )

    # =========================================================================
    # Passive Activity Loss Carryovers (IRC Section 469)
    # =========================================================================
    passive_activity_loss_carryover: float = Field(
        default=0.0, ge=0,
        description="Suspended passive activity losses from prior years"
    )
    passive_loss_by_activity: Dict[str, float] = Field(
        default_factory=dict,
        description="Suspended passive losses by activity"
    )

    # =========================================================================
    # Investment Interest Expense Carryover (IRC Section 163(d))
    # =========================================================================
    investment_interest_carryover: float = Field(
        default=0.0, ge=0,
        description="Disallowed investment interest expense carryforward"
    )

    # =========================================================================
    # Section 179 Carryover
    # =========================================================================
    section_179_carryover: float = Field(
        default=0.0, ge=0,
        description="Section 179 deduction carryforward (limited by taxable income)"
    )

    # =========================================================================
    # At-Risk Loss Carryover (IRC Section 465)
    # =========================================================================
    at_risk_loss_carryover: float = Field(
        default=0.0, ge=0,
        description="Suspended at-risk losses from prior years"
    )

    # =========================================================================
    # Home Office Carryover
    # =========================================================================
    home_office_carryover: float = Field(
        default=0.0, ge=0,
        description="Home office deduction carryforward (simplified method limit)"
    )

    # =========================================================================
    # IRA Basis (Form 8606)
    # =========================================================================
    traditional_ira_basis: float = Field(
        default=0.0, ge=0,
        description="Cumulative nondeductible Traditional IRA contributions (Form 8606)"
    )

    # =========================================================================
    # Installment Sale Deferred Gain
    # =========================================================================
    installment_sale_deferred_gain: float = Field(
        default=0.0, ge=0,
        description="Deferred gain from installment sales to be recognized"
    )

    # =========================================================================
    # Form 2210 Safe Harbor Data
    # =========================================================================
    prior_year_total_tax: float = Field(
        default=0.0, ge=0,
        description="Prior year total tax liability for Form 2210 safe harbor"
    )
    prior_year_agi: float = Field(
        default=0.0, ge=0,
        description="Prior year AGI for 110% safe harbor threshold determination"
    )

    def get_total_capital_loss_carryover(self) -> float:
        """Get total capital loss carryover (short-term + long-term)."""
        return self.short_term_capital_loss_carryover + self.long_term_capital_loss_carryover

    def get_total_charitable_carryover(self) -> float:
        """Get total charitable contribution carryover."""
        return (
            self.charitable_cash_60pct_carryover +
            self.charitable_cash_50pct_carryover +
            self.charitable_property_30pct_carryover +
            self.charitable_property_20pct_carryover
        )

    def get_total_nol_carryover(self) -> float:
        """Get total NOL carryover."""
        return self.nol_carryover_post_2017 + self.nol_carryover_pre_2018

    def has_carryovers(self) -> bool:
        """Check if there are any carryovers to apply."""
        return (
            self.get_total_capital_loss_carryover() > 0 or
            self.get_total_charitable_carryover() > 0 or
            self.get_total_nol_carryover() > 0 or
            self.amt_credit_carryover > 0 or
            self.foreign_tax_credit_carryover > 0 or
            self.passive_activity_loss_carryover > 0 or
            self.investment_interest_carryover > 0 or
            self.section_179_carryover > 0
        )


class ScenarioModification(BaseModel):
    """
    A single modification to apply in a scenario.

    Represents a change to a specific field in the tax return,
    allowing for "what-if" analysis.
    """
    field_path: str = Field(
        description="Dot-notation path to the field (e.g., 'income.retirement_contributions')"
    )
    original_value: Any = Field(
        description="The original value before modification"
    )
    new_value: Any = Field(
        description="The new value to use in the scenario"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this modification"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "field_path": self.field_path,
            "original_value": self.original_value,
            "new_value": self.new_value,
            "description": self.description,
        }


class ScenarioResult(BaseModel):
    """
    Result of calculating a scenario.

    Contains the tax calculation results and comparison metrics.
    """
    # Core results
    total_tax: float = Field(description="Total tax liability in this scenario")
    federal_tax: float = Field(description="Federal tax liability")
    state_tax: float = Field(default=0.0, description="State tax liability")

    # Rate analysis
    effective_rate: float = Field(description="Effective tax rate (total_tax / gross_income)")
    marginal_rate: float = Field(default=0.0, description="Marginal tax rate")

    # Comparison metrics
    base_tax: float = Field(description="Tax from base scenario for comparison")
    savings: float = Field(description="Savings compared to base (positive = better)")
    savings_percent: float = Field(description="Percentage savings compared to base")

    # Breakdown
    taxable_income: float = Field(description="Taxable income in this scenario")
    total_deductions: float = Field(default=0.0, description="Total deductions")
    total_credits: float = Field(default=0.0, description="Total credits applied")

    # Detailed breakdown for analysis
    breakdown: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed calculation breakdown"
    )

    # Computation metadata
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    computation_time_ms: Optional[int] = Field(default=None)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage and API responses."""
        try:
            data = self.model_dump(mode="python")  # Pydantic v2
        except AttributeError:
            data = self.dict()  # Pydantic v1 fallback

        # Ensure datetime is JSON-serializable in all runtimes.
        computed_at = data.get("computed_at")
        if isinstance(computed_at, datetime):
            data["computed_at"] = computed_at.isoformat()

        return data


class RecommendationAction(BaseModel):
    """
    A specific action step within a recommendation.

    Provides concrete, actionable guidance for implementing a tax strategy.
    """
    step_number: int = Field(ge=1, description="Order of this step")
    action: str = Field(description="The action to take")
    details: Optional[str] = Field(default=None, description="Additional details")
    deadline: Optional[str] = Field(default=None, description="Deadline for this action")
    responsible_party: Optional[str] = Field(
        default=None,
        description="Who should take this action (taxpayer, employer, advisor)"
    )
    estimated_time: Optional[str] = Field(
        default=None,
        description="Estimated time to complete (e.g., '30 minutes', '1-2 hours')"
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Prerequisites that must be completed first"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_number": self.step_number,
            "action": self.action,
            "details": self.details,
            "deadline": self.deadline,
            "responsible_party": self.responsible_party,
            "estimated_time": self.estimated_time,
            "prerequisites": self.prerequisites,
        }
