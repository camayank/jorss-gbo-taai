"""
Domain Aggregates for Tax Decision Intelligence Platform.

Aggregates are clusters of domain objects that are treated as a single unit
for data changes. Each aggregate has a root entity that controls access to
other entities within the boundary.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from enum import Enum

from .value_objects import (
    ScenarioModification,
    ScenarioResult,
    RecommendationAction,
    PriorYearCarryovers,
    PriorYearSummary,
)


# =============================================================================
# SCENARIO AGGREGATE
# =============================================================================

class ScenarioType(str, Enum):
    """Types of tax scenarios for what-if analysis."""
    FILING_STATUS = "filing_status"  # Compare different filing statuses
    WHAT_IF = "what_if"  # Generic what-if modifications
    ENTITY_STRUCTURE = "entity_structure"  # S-Corp vs LLC vs Sole Prop
    DEDUCTION_BUNCHING = "deduction_bunching"  # Charitable/medical bunching
    RETIREMENT = "retirement"  # Retirement contribution scenarios
    MULTI_YEAR = "multi_year"  # Multi-year projections
    ROTH_CONVERSION = "roth_conversion"  # Roth conversion analysis
    CAPITAL_GAINS = "capital_gains"  # Capital gains timing/harvesting
    ESTIMATED_TAX = "estimated_tax"  # Estimated tax planning


class ScenarioStatus(str, Enum):
    """Status of a scenario."""
    DRAFT = "draft"  # Being configured
    CALCULATED = "calculated"  # Calculation complete
    APPLIED = "applied"  # Applied to return
    ARCHIVED = "archived"  # No longer active


class Scenario(BaseModel):
    """
    Scenario Aggregate Root.

    Represents a tax scenario for what-if analysis. Contains a frozen snapshot
    of the base return state and a list of modifications to apply.

    Invariants:
    - Must have valid return_id reference
    - Modifications must be valid field paths
    - Result computed only after modifications applied
    """

    # Identity
    scenario_id: UUID = Field(default_factory=uuid4)
    return_id: UUID = Field(description="Reference to the base tax return")

    # Descriptive
    name: str = Field(description="User-friendly scenario name")
    description: Optional[str] = Field(default=None)
    scenario_type: ScenarioType = Field(default=ScenarioType.WHAT_IF)
    status: ScenarioStatus = Field(default=ScenarioStatus.DRAFT)

    # Base state (frozen snapshot of return at scenario creation)
    base_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Frozen copy of original return state at scenario creation"
    )

    # Modifications to apply
    modifications: List[ScenarioModification] = Field(
        default_factory=list,
        description="List of modifications to apply to the base"
    )

    # Result (populated after calculation)
    result: Optional[ScenarioResult] = Field(
        default=None,
        description="Calculation result for this scenario"
    )

    # Comparison metrics
    is_recommended: bool = Field(
        default=False,
        description="Whether this is the recommended scenario"
    )
    recommendation_reason: Optional[str] = Field(
        default=None,
        description="Reason why this scenario is recommended"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None)
    calculated_at: Optional[datetime] = Field(default=None)
    version: int = Field(default=1, description="Optimistic locking version")

    class Config:
        """Pydantic configuration."""
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}

    def add_modification(self, modification: ScenarioModification) -> None:
        """Add a modification to this scenario."""
        # Check for duplicate field path and update if exists
        for i, existing in enumerate(self.modifications):
            if existing.field_path == modification.field_path:
                self.modifications[i] = modification
                return
        self.modifications.append(modification)

    def remove_modification(self, field_path: str) -> bool:
        """Remove a modification by field path."""
        for i, mod in enumerate(self.modifications):
            if mod.field_path == field_path:
                self.modifications.pop(i)
                return True
        return False

    def clear_modifications(self) -> None:
        """Clear all modifications."""
        self.modifications.clear()
        self.result = None
        self.status = ScenarioStatus.DRAFT

    def set_result(self, result: ScenarioResult) -> None:
        """Set the calculation result."""
        self.result = result
        self.status = ScenarioStatus.CALCULATED
        self.calculated_at = datetime.utcnow()

    def mark_as_recommended(self, reason: str) -> None:
        """Mark this scenario as the recommended option."""
        self.is_recommended = True
        self.recommendation_reason = reason

    def get_savings(self) -> float:
        """Get savings compared to base scenario."""
        if self.result:
            return self.result.savings
        return 0.0

    def to_comparison_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for comparison display."""
        return {
            "scenario_id": str(self.scenario_id),
            "name": self.name,
            "type": self.scenario_type.value,
            "modifications_count": len(self.modifications),
            "total_tax": self.result.total_tax if self.result else None,
            "effective_rate": self.result.effective_rate if self.result else None,
            "savings": self.result.savings if self.result else None,
            "is_recommended": self.is_recommended,
        }


# =============================================================================
# ADVISORY AGGREGATE
# =============================================================================

class RecommendationCategory(str, Enum):
    """Categories of tax recommendations."""
    RETIREMENT = "retirement"  # 401k, IRA, etc.
    DEDUCTION = "deduction"  # Itemized deductions, bunching
    CREDIT = "credit"  # Tax credits
    INCOME_TIMING = "income_timing"  # Income deferral/acceleration
    ENTITY_STRUCTURE = "entity_structure"  # Business structure
    INVESTMENT = "investment"  # Investment strategies
    ESTATE = "estate"  # Estate planning
    CHARITABLE = "charitable"  # Charitable giving
    HEALTHCARE = "healthcare"  # HSA, FSA, medical
    EDUCATION = "education"  # 529, education credits
    REAL_ESTATE = "real_estate"  # Real estate strategies
    STATE_TAX = "state_tax"  # State tax optimization


class RecommendationPriority(str, Enum):
    """Priority/urgency of recommendations."""
    IMMEDIATE = "immediate"  # Must act before a deadline (e.g., Dec 31)
    CURRENT_YEAR = "current_year"  # Should implement this tax year
    LONG_TERM = "long_term"  # Strategic planning for future years


class RecommendationStatus(str, Enum):
    """Status of a recommendation."""
    PROPOSED = "proposed"  # Generated, awaiting review
    ACCEPTED = "accepted"  # Client accepted
    IMPLEMENTED = "implemented"  # Action taken
    DECLINED = "declined"  # Client declined
    NOT_APPLICABLE = "not_applicable"  # No longer applies


class Recommendation(BaseModel):
    """
    A specific tax optimization recommendation.

    Part of the Advisory aggregate, representing actionable tax advice.
    """

    # Identity
    recommendation_id: UUID = Field(default_factory=uuid4)

    # Classification
    category: RecommendationCategory
    priority: RecommendationPriority

    # Content
    title: str = Field(description="Short title for the recommendation")
    summary: str = Field(description="Brief summary of the recommendation")
    detailed_explanation: Optional[str] = Field(
        default=None,
        description="Detailed explanation with IRS references"
    )

    # Impact
    estimated_savings: float = Field(
        default=0.0, ge=0,
        description="Estimated tax savings"
    )
    confidence_level: float = Field(
        default=0.8, ge=0, le=1,
        description="Confidence in the savings estimate (0-1)"
    )
    complexity: str = Field(
        default="medium",
        description="Implementation complexity (low, medium, high)"
    )

    # Actions
    action_steps: List[RecommendationAction] = Field(
        default_factory=list,
        description="Concrete steps to implement"
    )

    # Status tracking
    status: RecommendationStatus = Field(default=RecommendationStatus.PROPOSED)
    status_changed_at: Optional[datetime] = Field(default=None)
    status_changed_by: Optional[str] = Field(default=None)
    decline_reason: Optional[str] = Field(default=None)

    # Outcome tracking (after implementation)
    actual_savings: Optional[float] = Field(
        default=None,
        description="Actual savings realized (tracked after implementation)"
    )
    outcome_notes: Optional[str] = Field(default=None)

    # Related scenario
    related_scenario_id: Optional[UUID] = Field(
        default=None,
        description="Scenario that demonstrates this recommendation"
    )

    # IRS/Legal references
    irs_references: List[str] = Field(
        default_factory=list,
        description="IRS form/publication/IRC section references"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}

    def update_status(self, new_status: RecommendationStatus, changed_by: str, reason: Optional[str] = None) -> None:
        """Update the recommendation status."""
        self.status = new_status
        self.status_changed_at = datetime.utcnow()
        self.status_changed_by = changed_by
        if new_status == RecommendationStatus.DECLINED:
            self.decline_reason = reason

    def record_outcome(self, actual_savings: float, notes: Optional[str] = None) -> None:
        """Record the actual outcome after implementation."""
        self.actual_savings = actual_savings
        self.outcome_notes = notes
        self.status = RecommendationStatus.IMPLEMENTED

    def get_savings_accuracy(self) -> Optional[float]:
        """Calculate accuracy of savings estimate vs actual."""
        if self.actual_savings is not None and self.estimated_savings > 0:
            return self.actual_savings / self.estimated_savings
        return None


class AdvisoryPlan(BaseModel):
    """
    Advisory Plan Aggregate Root.

    Contains comprehensive tax advisory recommendations for a client/return.

    Invariants:
    - Recommendations must reference valid return
    - Cannot mark implemented without evidence
    - Outcome tracking requires implementation first
    """

    # Identity
    plan_id: UUID = Field(default_factory=uuid4)
    client_id: UUID = Field(description="Reference to the client")
    return_id: UUID = Field(description="Reference to the tax return")
    tax_year: int = Field(description="Tax year for this plan")

    # Plan content
    recommendations: List[Recommendation] = Field(
        default_factory=list,
        description="List of recommendations"
    )

    # Computation statement (Big4-style documentation)
    computation_statement: Optional[str] = Field(
        default=None,
        description="Detailed computation statement with methodology"
    )

    # Summary metrics
    total_potential_savings: float = Field(
        default=0.0, ge=0,
        description="Total potential savings across all recommendations"
    )
    total_realized_savings: float = Field(
        default=0.0, ge=0,
        description="Total realized savings from implemented recommendations"
    )

    # Plan status
    is_finalized: bool = Field(
        default=False,
        description="Whether the plan is finalized for client delivery"
    )
    finalized_at: Optional[datetime] = Field(default=None)
    finalized_by: Optional[str] = Field(default=None)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1)

    class Config:
        """Pydantic configuration."""
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}

    def add_recommendation(self, recommendation: Recommendation) -> None:
        """Add a recommendation to the plan."""
        self.recommendations.append(recommendation)
        self._recalculate_totals()
        self.updated_at = datetime.utcnow()

    def remove_recommendation(self, recommendation_id: UUID) -> bool:
        """Remove a recommendation from the plan."""
        for i, rec in enumerate(self.recommendations):
            if rec.recommendation_id == recommendation_id:
                self.recommendations.pop(i)
                self._recalculate_totals()
                self.updated_at = datetime.utcnow()
                return True
        return False

    def get_recommendation(self, recommendation_id: UUID) -> Optional[Recommendation]:
        """Get a specific recommendation by ID."""
        for rec in self.recommendations:
            if rec.recommendation_id == recommendation_id:
                return rec
        return None

    def _recalculate_totals(self) -> None:
        """Recalculate total savings metrics."""
        self.total_potential_savings = sum(
            r.estimated_savings for r in self.recommendations
            if r.status not in [RecommendationStatus.DECLINED, RecommendationStatus.NOT_APPLICABLE]
        )
        self.total_realized_savings = sum(
            r.actual_savings or 0 for r in self.recommendations
            if r.status == RecommendationStatus.IMPLEMENTED
        )

    def get_by_priority(self, priority: RecommendationPriority) -> List[Recommendation]:
        """Get recommendations by priority."""
        return [r for r in self.recommendations if r.priority == priority]

    def get_by_category(self, category: RecommendationCategory) -> List[Recommendation]:
        """Get recommendations by category."""
        return [r for r in self.recommendations if r.category == category]

    def get_by_status(self, status: RecommendationStatus) -> List[Recommendation]:
        """Get recommendations by status."""
        return [r for r in self.recommendations if r.status == status]

    def finalize(self, finalized_by: str) -> None:
        """Finalize the plan for client delivery."""
        self.is_finalized = True
        self.finalized_at = datetime.utcnow()
        self.finalized_by = finalized_by
        self.updated_at = datetime.utcnow()

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the advisory plan."""
        return {
            "plan_id": str(self.plan_id),
            "tax_year": self.tax_year,
            "total_recommendations": len(self.recommendations),
            "total_potential_savings": self.total_potential_savings,
            "total_realized_savings": self.total_realized_savings,
            "by_priority": {
                "immediate": len(self.get_by_priority(RecommendationPriority.IMMEDIATE)),
                "current_year": len(self.get_by_priority(RecommendationPriority.CURRENT_YEAR)),
                "long_term": len(self.get_by_priority(RecommendationPriority.LONG_TERM)),
            },
            "by_status": {
                "proposed": len(self.get_by_status(RecommendationStatus.PROPOSED)),
                "accepted": len(self.get_by_status(RecommendationStatus.ACCEPTED)),
                "implemented": len(self.get_by_status(RecommendationStatus.IMPLEMENTED)),
                "declined": len(self.get_by_status(RecommendationStatus.DECLINED)),
            },
            "is_finalized": self.is_finalized,
        }


# =============================================================================
# CLIENT PROFILE AGGREGATE
# =============================================================================

class RiskTolerance(str, Enum):
    """Client's risk tolerance for tax strategies."""
    CONSERVATIVE = "conservative"  # Only well-established strategies
    MODERATE = "moderate"  # Standard optimization
    AGGRESSIVE = "aggressive"  # More aggressive planning


class CommunicationPreference(str, Enum):
    """Client's preferred communication method."""
    EMAIL = "email"
    PHONE = "phone"
    TEXT = "text"
    PORTAL = "portal"


class ClientPreferences(BaseModel):
    """
    Client preferences for tax planning and communication.
    """
    risk_tolerance: RiskTolerance = Field(default=RiskTolerance.MODERATE)
    communication_preference: CommunicationPreference = Field(default=CommunicationPreference.EMAIL)

    # Planning goals
    planning_goals: List[str] = Field(
        default_factory=list,
        description="Client's tax planning goals"
    )

    # Constraints
    max_retirement_contribution: Optional[float] = Field(
        default=None,
        description="Maximum retirement contribution client can afford"
    )
    prefers_standard_deduction: bool = Field(
        default=False,
        description="Client prefers simplicity of standard deduction"
    )
    has_state_tax_concerns: bool = Field(
        default=False,
        description="Client has specific state tax concerns"
    )

    # Notifications
    notify_of_deadlines: bool = Field(default=True)
    notify_of_opportunities: bool = Field(default=True)


class ClientProfile(BaseModel):
    """
    Client Profile Aggregate Root.

    Represents a client/taxpayer with their history and preferences.

    Invariants:
    - SSN must be unique across clients
    - Cannot delete client with active returns
    """

    # Identity
    client_id: UUID = Field(default_factory=uuid4)
    external_id: Optional[str] = Field(
        default=None,
        description="CPA's client number/ID"
    )

    # Identity (encrypted/hashed in storage)
    ssn_hash: Optional[str] = Field(
        default=None,
        description="Hashed SSN for lookup"
    )
    first_name: str = Field(description="Client's first name")
    last_name: str = Field(description="Client's last name")
    email: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)

    # Address
    street_address: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    zip_code: Optional[str] = Field(default=None)

    # Tax history references
    tax_return_ids: List[UUID] = Field(
        default_factory=list,
        description="References to tax returns by year"
    )
    tax_return_years: Dict[int, UUID] = Field(
        default_factory=dict,
        description="Mapping of tax year to return ID"
    )

    # Preferences
    preferences: ClientPreferences = Field(default_factory=ClientPreferences)

    # Prior year data (for quick access)
    prior_year_carryovers: Optional[PriorYearCarryovers] = Field(
        default=None,
        description="Current carryover balances"
    )
    prior_year_summary: Optional[PriorYearSummary] = Field(
        default=None,
        description="Summary of most recent prior year return"
    )

    # Status
    is_active: bool = Field(default=True)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1)

    class Config:
        """Pydantic configuration."""
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}

    def add_tax_return(self, return_id: UUID, tax_year: int) -> None:
        """Add a tax return reference."""
        if return_id not in self.tax_return_ids:
            self.tax_return_ids.append(return_id)
        self.tax_return_years[tax_year] = return_id
        self.updated_at = datetime.utcnow()

    def get_return_for_year(self, tax_year: int) -> Optional[UUID]:
        """Get return ID for a specific year."""
        return self.tax_return_years.get(tax_year)

    def get_prior_year_return(self, current_year: int) -> Optional[UUID]:
        """Get the prior year return ID."""
        return self.tax_return_years.get(current_year - 1)

    def update_carryovers(self, carryovers: PriorYearCarryovers) -> None:
        """Update carryover balances."""
        self.prior_year_carryovers = carryovers
        self.updated_at = datetime.utcnow()

    def update_prior_year_summary(self, summary: PriorYearSummary) -> None:
        """Update prior year summary."""
        self.prior_year_summary = summary
        self.updated_at = datetime.utcnow()

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}"

    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary."""
        return {
            "client_id": str(self.client_id),
            "external_id": self.external_id,
            "name": self.full_name,
            "email": self.email,
            "state": self.state,
            "tax_years_on_file": list(self.tax_return_years.keys()),
            "is_active": self.is_active,
            "has_carryovers": self.prior_year_carryovers.has_carryovers() if self.prior_year_carryovers else False,
        }
