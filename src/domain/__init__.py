"""
Domain layer for Tax Decision Intelligence Platform.

This module contains the core domain models, aggregates, value objects,
events, and repository interfaces following Domain-Driven Design principles.
"""

from .value_objects import (
    PriorYearCarryovers,
    PriorYearSummary,
    ScenarioModification,
    ScenarioResult,
    RecommendationAction,
)
from .aggregates import (
    Scenario,
    ScenarioType,
    ScenarioStatus,
    AdvisoryPlan,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    ClientProfile,
    ClientPreferences,
    RiskTolerance,
    # Multi-client management (Phase 1-2)
    Preparer,
    ClientSession,
    ClientStatus,
)
from .events import (
    DomainEvent,
    TaxReturnCreated,
    TaxReturnCalculated,
    TaxReturnUpdated,
    ScenarioCreated,
    ScenarioCompared,
    RecommendationGenerated,
    RecommendationStatusChanged,
)
from .repositories import (
    IRepository,
    ITaxReturnRepository,
    IScenarioRepository,
    IAdvisoryRepository,
    IClientRepository,
    IEventStore,
    IUnitOfWork,
)
from .event_bus import (
    EventBus,
    SQLiteEventStore,
    AuditEventHandler,
    LoggingEventHandler,
    get_event_bus,
    publish_event,
    publish_event_async,
)

__all__ = [
    # Value Objects
    "PriorYearCarryovers",
    "PriorYearSummary",
    "ScenarioModification",
    "ScenarioResult",
    "RecommendationAction",
    # Aggregates
    "Scenario",
    "ScenarioType",
    "ScenarioStatus",
    "AdvisoryPlan",
    "Recommendation",
    "RecommendationCategory",
    "RecommendationPriority",
    "RecommendationStatus",
    "ClientProfile",
    "ClientPreferences",
    "RiskTolerance",
    # Multi-client management
    "Preparer",
    "ClientSession",
    "ClientStatus",
    # Events
    "DomainEvent",
    "TaxReturnCreated",
    "TaxReturnCalculated",
    "TaxReturnUpdated",
    "ScenarioCreated",
    "ScenarioCompared",
    "RecommendationGenerated",
    "RecommendationStatusChanged",
    # Repositories
    "IRepository",
    "ITaxReturnRepository",
    "IScenarioRepository",
    "IAdvisoryRepository",
    "IClientRepository",
    "IEventStore",
    "IUnitOfWork",
    # Event Bus
    "EventBus",
    "SQLiteEventStore",
    "AuditEventHandler",
    "LoggingEventHandler",
    "get_event_bus",
    "publish_event",
    "publish_event_async",
]
