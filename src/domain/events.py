"""
Domain Events for Tax Decision Intelligence Platform.

Domain events represent something that happened in the domain that domain
experts care about. They are immutable records of past occurrences.

Events are used for:
1. Audit trails - Complete history of all changes
2. Integration - Triggering side effects (notifications, analytics)
3. Event sourcing - Reconstructing state from events
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from enum import Enum
from dataclasses import dataclass


class EventType(str, Enum):
    """Types of domain events."""
    # Tax Return Events
    TAX_RETURN_CREATED = "tax_return.created"
    TAX_RETURN_UPDATED = "tax_return.updated"
    TAX_RETURN_CALCULATED = "tax_return.calculated"
    TAX_RETURN_DELETED = "tax_return.deleted"

    # Scenario Events
    SCENARIO_CREATED = "scenario.created"
    SCENARIO_CALCULATED = "scenario.calculated"
    SCENARIO_COMPARED = "scenario.compared"
    SCENARIO_APPLIED = "scenario.applied"
    SCENARIO_DELETED = "scenario.deleted"

    # Advisory Events
    ADVISORY_PLAN_CREATED = "advisory.plan_created"
    RECOMMENDATION_GENERATED = "advisory.recommendation_generated"
    RECOMMENDATION_STATUS_CHANGED = "advisory.recommendation_status_changed"
    ADVISORY_PLAN_FINALIZED = "advisory.plan_finalized"

    # Client Events
    CLIENT_CREATED = "client.created"
    CLIENT_UPDATED = "client.updated"
    CLIENT_CARRYOVERS_UPDATED = "client.carryovers_updated"

    # Intake Events
    INTAKE_SESSION_STARTED = "intake.session_started"
    INTAKE_DATA_EXTRACTED = "intake.data_extracted"
    INTAKE_SESSION_COMPLETED = "intake.session_completed"


class DomainEvent(BaseModel):
    """
    Base class for all domain events.

    All events are immutable and contain:
    - Unique event ID
    - When the event occurred
    - Metadata about context (user, session, etc.)
    """
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1, description="Event schema version")

    # Context metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (user_id, session_id, correlation_id, etc.)"
    )

    # Aggregate reference
    aggregate_id: Optional[UUID] = Field(
        default=None,
        description="ID of the aggregate this event belongs to"
    )
    aggregate_type: Optional[str] = Field(
        default=None,
        description="Type of aggregate (tax_return, scenario, etc.)"
    )

    class Config:
        """Pydantic configuration."""
        frozen = True  # Make events immutable
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}


# =============================================================================
# TAX RETURN EVENTS
# =============================================================================

class TaxReturnCreated(DomainEvent):
    """Event raised when a new tax return is created."""
    event_type: EventType = EventType.TAX_RETURN_CREATED
    aggregate_type: str = "tax_return"

    return_id: UUID
    client_id: Optional[UUID] = None
    tax_year: int
    filing_status: str
    state_of_residence: Optional[str] = None


class TaxReturnUpdated(DomainEvent):
    """Event raised when a tax return is updated."""
    event_type: EventType = EventType.TAX_RETURN_UPDATED
    aggregate_type: str = "tax_return"

    return_id: UUID
    changed_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Fields that changed and their new values"
    )
    previous_values: Dict[str, Any] = Field(
        default_factory=dict,
        description="Previous values of changed fields"
    )


class TaxReturnCalculated(DomainEvent):
    """Event raised when tax calculation is performed."""
    event_type: EventType = EventType.TAX_RETURN_CALCULATED
    aggregate_type: str = "tax_return"

    return_id: UUID
    tax_year: int

    # Results summary
    gross_income: float
    adjusted_gross_income: float
    taxable_income: float
    total_tax: float
    effective_rate: float
    refund_or_owed: float

    # Computation metadata
    computation_time_ms: int = Field(description="Time to calculate in milliseconds")
    forms_calculated: List[str] = Field(
        default_factory=list,
        description="List of forms that were calculated"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Calculation warnings"
    )


class TaxReturnDeleted(DomainEvent):
    """Event raised when a tax return is deleted."""
    event_type: EventType = EventType.TAX_RETURN_DELETED
    aggregate_type: str = "tax_return"

    return_id: UUID
    reason: Optional[str] = None


# =============================================================================
# SCENARIO EVENTS
# =============================================================================

class ScenarioCreated(DomainEvent):
    """Event raised when a new scenario is created."""
    event_type: EventType = EventType.SCENARIO_CREATED
    aggregate_type: str = "scenario"

    scenario_id: UUID
    return_id: UUID
    name: str
    scenario_type: str
    modifications: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of modifications in the scenario"
    )


class ScenarioCalculated(DomainEvent):
    """Event raised when a scenario is calculated."""
    event_type: EventType = EventType.SCENARIO_CALCULATED
    aggregate_type: str = "scenario"

    scenario_id: UUID
    return_id: UUID
    total_tax: float
    effective_rate: float
    savings_vs_base: float
    computation_time_ms: int


class ScenarioCompared(DomainEvent):
    """Event raised when scenarios are compared."""
    event_type: EventType = EventType.SCENARIO_COMPARED
    aggregate_type: str = "scenario"

    comparison_id: UUID = Field(default_factory=uuid4)
    return_id: UUID
    scenario_ids: List[UUID]
    winner_scenario_id: Optional[UUID] = None
    max_savings: float = 0.0
    comparison_summary: Optional[str] = None


class ScenarioApplied(DomainEvent):
    """Event raised when a scenario is applied to a return."""
    event_type: EventType = EventType.SCENARIO_APPLIED
    aggregate_type: str = "scenario"

    scenario_id: UUID
    return_id: UUID
    applied_modifications: List[Dict[str, Any]]
    tax_change: float = Field(description="Change in tax liability after applying")


class ScenarioDeleted(DomainEvent):
    """Event raised when a scenario is deleted."""
    event_type: EventType = EventType.SCENARIO_DELETED
    aggregate_type: str = "scenario"

    scenario_id: UUID
    return_id: UUID


# =============================================================================
# ADVISORY EVENTS
# =============================================================================

class AdvisoryPlanCreated(DomainEvent):
    """Event raised when a new advisory plan is created."""
    event_type: EventType = EventType.ADVISORY_PLAN_CREATED
    aggregate_type: str = "advisory"

    plan_id: UUID
    client_id: UUID
    return_id: UUID
    tax_year: int


class RecommendationGenerated(DomainEvent):
    """Event raised when recommendations are generated."""
    event_type: EventType = EventType.RECOMMENDATION_GENERATED
    aggregate_type: str = "advisory"

    plan_id: UUID
    return_id: UUID
    recommendation_count: int
    total_potential_savings: float
    categories: List[str] = Field(
        default_factory=list,
        description="Categories of recommendations generated"
    )


class RecommendationStatusChanged(DomainEvent):
    """Event raised when a recommendation status changes."""
    event_type: EventType = EventType.RECOMMENDATION_STATUS_CHANGED
    aggregate_type: str = "advisory"

    recommendation_id: UUID
    plan_id: UUID
    old_status: str
    new_status: str
    changed_by: str
    reason: Optional[str] = None


class AdvisoryPlanFinalized(DomainEvent):
    """Event raised when an advisory plan is finalized."""
    event_type: EventType = EventType.ADVISORY_PLAN_FINALIZED
    aggregate_type: str = "advisory"

    plan_id: UUID
    client_id: UUID
    total_recommendations: int
    total_potential_savings: float
    finalized_by: str


# =============================================================================
# CLIENT EVENTS
# =============================================================================

class ClientCreated(DomainEvent):
    """Event raised when a new client is created."""
    event_type: EventType = EventType.CLIENT_CREATED
    aggregate_type: str = "client"

    client_id: UUID
    external_id: Optional[str] = None


class ClientUpdated(DomainEvent):
    """Event raised when client profile is updated."""
    event_type: EventType = EventType.CLIENT_UPDATED
    aggregate_type: str = "client"

    client_id: UUID
    changed_fields: List[str]


class ClientCarryoversUpdated(DomainEvent):
    """Event raised when client carryovers are updated."""
    event_type: EventType = EventType.CLIENT_CARRYOVERS_UPDATED
    aggregate_type: str = "client"

    client_id: UUID
    from_tax_year: int
    carryover_types: List[str] = Field(
        default_factory=list,
        description="Types of carryovers that were updated"
    )
    total_carryover_amount: float


# =============================================================================
# INTAKE EVENTS
# =============================================================================

class IntakeSessionStarted(DomainEvent):
    """Event raised when an intake session starts."""
    event_type: EventType = EventType.INTAKE_SESSION_STARTED
    aggregate_type: str = "intake"

    session_id: UUID
    client_id: Optional[UUID] = None
    tax_year: int


class IntakeDataExtracted(DomainEvent):
    """Event raised when data is extracted during intake."""
    event_type: EventType = EventType.INTAKE_DATA_EXTRACTED
    aggregate_type: str = "intake"

    session_id: UUID
    field_path: str
    extracted_value: Any
    confidence: float = Field(ge=0, le=1)
    source: str = Field(description="Source of extraction (user_input, document, inference)")


class IntakeSessionCompleted(DomainEvent):
    """Event raised when an intake session completes."""
    event_type: EventType = EventType.INTAKE_SESSION_COMPLETED
    aggregate_type: str = "intake"

    session_id: UUID
    return_id: UUID
    fields_collected: int
    completeness_score: float
    duration_seconds: int


# =============================================================================
# EVENT FACTORY
# =============================================================================

def create_event(event_type: EventType, **kwargs) -> DomainEvent:
    """
    Factory function to create domain events.

    Args:
        event_type: Type of event to create
        **kwargs: Event-specific parameters

    Returns:
        The appropriate DomainEvent subclass instance
    """
    event_classes = {
        EventType.TAX_RETURN_CREATED: TaxReturnCreated,
        EventType.TAX_RETURN_UPDATED: TaxReturnUpdated,
        EventType.TAX_RETURN_CALCULATED: TaxReturnCalculated,
        EventType.TAX_RETURN_DELETED: TaxReturnDeleted,
        EventType.SCENARIO_CREATED: ScenarioCreated,
        EventType.SCENARIO_CALCULATED: ScenarioCalculated,
        EventType.SCENARIO_COMPARED: ScenarioCompared,
        EventType.SCENARIO_APPLIED: ScenarioApplied,
        EventType.SCENARIO_DELETED: ScenarioDeleted,
        EventType.ADVISORY_PLAN_CREATED: AdvisoryPlanCreated,
        EventType.RECOMMENDATION_GENERATED: RecommendationGenerated,
        EventType.RECOMMENDATION_STATUS_CHANGED: RecommendationStatusChanged,
        EventType.ADVISORY_PLAN_FINALIZED: AdvisoryPlanFinalized,
        EventType.CLIENT_CREATED: ClientCreated,
        EventType.CLIENT_UPDATED: ClientUpdated,
        EventType.CLIENT_CARRYOVERS_UPDATED: ClientCarryoversUpdated,
        EventType.INTAKE_SESSION_STARTED: IntakeSessionStarted,
        EventType.INTAKE_DATA_EXTRACTED: IntakeDataExtracted,
        EventType.INTAKE_SESSION_COMPLETED: IntakeSessionCompleted,
    }

    event_class = event_classes.get(event_type)
    if event_class is None:
        raise ValueError(f"Unknown event type: {event_type}")

    return event_class(**kwargs)
