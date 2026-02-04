# System Architecture: Tax Decision Intelligence Platform

## Architecture Philosophy

```
DESIGN PRINCIPLES:
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  BACKEND: Robust, Testable, Observable                             │
│  ─────────────────────────────────────                             │
│  • Domain-Driven Design (DDD) with clear bounded contexts          │
│  • Event-driven for audit trails and async processing              │
│  • Repository pattern for data access                              │
│  • Service layer for business logic orchestration                  │
│  • CQRS-lite: Separate read/write paths where beneficial           │
│                                                                     │
│  FRONTEND: Smart, Minimalistic, Decision-Focused                   │
│  ─────────────────────────────────────────────────                 │
│  • Progressive disclosure (show complexity only when needed)       │
│  • Decision-first UI (not form-first)                              │
│  • Real-time feedback loops                                        │
│  • Mobile-responsive, accessibility-first                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   Web UI        │  │   API Gateway   │  │  Webhook/Events │             │
│  │   (React/Vue)   │  │   (FastAPI)     │  │   (Async)       │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
└───────────┼────────────────────┼────────────────────┼───────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        SERVICE ORCHESTRATORS                         │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ TaxReturn    │  │ Scenario     │  │ Advisory     │              │   │
│  │  │ Service      │  │ Service      │  │ Service      │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ Intake       │  │ Document     │  │ Export       │              │   │
│  │  │ Service      │  │ Service      │  │ Service      │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DOMAIN LAYER                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         DOMAIN SERVICES                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │  │
│  │  │ Calculation │ │ Optimization│ │ Validation  │ │ Rules       │    │  │
│  │  │ Engine      │ │ Engine      │ │ Engine      │ │ Engine      │    │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         DOMAIN MODELS                                 │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │  │
│  │  │ TaxReturn   │ │ Scenario    │ │ Taxpayer    │ │ Advisory    │    │  │
│  │  │ Aggregate   │ │ Aggregate   │ │ Aggregate   │ │ Aggregate   │    │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Repository  │ │ Event Store │ │ Cache       │ │ External    │          │
│  │ (SQLite/PG) │ │ (Audit)     │ │ (Redis)     │ │ Services    │          │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Building Block #1: Core Domain Models

### 1.1 Aggregate: TaxReturn (Root)

```
┌─────────────────────────────────────────────────────────────────┐
│                    TAX RETURN AGGREGATE                         │
│                                                                 │
│  TaxReturn (Root Entity)                                        │
│  ├── return_id: UUID                                           │
│  ├── version: int (optimistic locking)                         │
│  ├── status: ReturnStatus                                      │
│  │                                                              │
│  ├── Taxpayer (Entity)                                         │
│  │   ├── personal_info                                         │
│  │   ├── spouse_info (optional)                                │
│  │   └── dependents[]                                          │
│  │                                                              │
│  ├── Income (Value Object Collection)                          │
│  │   ├── w2_income[]                                           │
│  │   ├── self_employment[]                                     │
│  │   ├── investments[]                                         │
│  │   └── other_income[]                                        │
│  │                                                              │
│  ├── Deductions (Value Object)                                 │
│  │   ├── standard_or_itemized                                  │
│  │   └── itemized_details                                      │
│  │                                                              │
│  ├── Credits (Value Object)                                    │
│  │   └── credit_claims[]                                       │
│  │                                                              │
│  ├── PriorYearData (Value Object) ← NEW                       │
│  │   ├── carryovers                                            │
│  │   └── summary                                               │
│  │                                                              │
│  └── CalculationResult (Value Object)                          │
│      ├── federal_breakdown                                     │
│      ├── state_breakdown                                       │
│      └── computed_at: timestamp                                │
│                                                                 │
│  INVARIANTS:                                                    │
│  • Cannot calculate without taxpayer info                      │
│  • Cannot file without calculation                             │
│  • Cannot amend without original                               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Aggregate: Scenario

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCENARIO AGGREGATE                           │
│                                                                 │
│  Scenario (Root Entity)                                         │
│  ├── scenario_id: UUID                                         │
│  ├── return_id: UUID (reference to TaxReturn)                  │
│  ├── name: string                                              │
│  ├── type: ScenarioType                                        │
│  │   └── FILING_STATUS | WHAT_IF | ENTITY | MULTI_YEAR        │
│  │                                                              │
│  ├── BaseSnapshot (Value Object)                               │
│  │   └── frozen copy of original return state                  │
│  │                                                              │
│  ├── Modifications (Value Object Collection)                   │
│  │   └── [{ path: "income.retirement", value: 23000 }]        │
│  │                                                              │
│  ├── Result (Value Object)                                     │
│  │   ├── total_tax                                             │
│  │   ├── effective_rate                                        │
│  │   ├── savings_vs_base                                       │
│  │   └── breakdown                                             │
│  │                                                              │
│  └── Metadata                                                   │
│      ├── created_at                                            │
│      ├── created_by                                            │
│      └── is_recommended: bool                                  │
│                                                                 │
│  INVARIANTS:                                                    │
│  • Must have valid return_id reference                         │
│  • Modifications must be valid paths                           │
│  • Result computed only after modifications applied            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Aggregate: Advisory

```
┌─────────────────────────────────────────────────────────────────┐
│                    ADVISORY AGGREGATE                           │
│                                                                 │
│  AdvisoryPlan (Root Entity)                                     │
│  ├── plan_id: UUID                                             │
│  ├── client_id: UUID                                           │
│  ├── tax_year: int                                             │
│  │                                                              │
│  ├── Recommendations (Entity Collection)                       │
│  │   ├── recommendation_id                                     │
│  │   ├── category: StrategyCategory                            │
│  │   ├── priority: immediate | current_year | long_term       │
│  │   ├── estimated_savings: Money                              │
│  │   ├── action_steps[]                                        │
│  │   ├── status: proposed | accepted | implemented | declined │
│  │   └── outcome: ActualSavings (after implementation)        │
│  │                                                              │
│  ├── ComputationStatement (Value Object)                       │
│  │   └── Big4-style documentation                              │
│  │                                                              │
│  └── AuditTrail (Event Collection)                             │
│      └── all changes, decisions, signatures                    │
│                                                                 │
│  INVARIANTS:                                                    │
│  • Recommendations must reference valid return                 │
│  • Cannot mark implemented without evidence                    │
│  • Outcome tracking requires implementation first              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 Aggregate: Client/Taxpayer Profile

```
┌─────────────────────────────────────────────────────────────────┐
│                 CLIENT PROFILE AGGREGATE                        │
│                                                                 │
│  ClientProfile (Root Entity)                                    │
│  ├── client_id: UUID                                           │
│  ├── external_id: string (CPA's client number)                │
│  │                                                              │
│  ├── Identity (Value Object)                                   │
│  │   ├── name, ssn_hash, dob                                   │
│  │   └── contact_info                                          │
│  │                                                              │
│  ├── TaxHistory (Entity Collection)                            │
│  │   └── return_id references by year                          │
│  │                                                              │
│  ├── Preferences (Value Object)                                │
│  │   ├── communication_preference                              │
│  │   ├── risk_tolerance                                        │
│  │   └── planning_goals                                        │
│  │                                                              │
│  └── Documents (Reference Collection)                          │
│      └── uploaded document references                          │
│                                                                 │
│  INVARIANTS:                                                    │
│  • SSN must be unique across clients                           │
│  • Cannot delete client with active returns                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Building Block #2: Service Layer

### 2.1 Service Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SERVICE LAYER                                   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    APPLICATION SERVICES                          │   │
│  │         (Orchestrate use cases, no business logic)               │   │
│  │                                                                   │   │
│  │  TaxReturnService          ScenarioService                       │   │
│  │  ├── create_return()       ├── create_scenario()                │   │
│  │  ├── update_return()       ├── compare_scenarios()              │   │
│  │  ├── calculate()           ├── get_filing_status_scenarios()    │   │
│  │  ├── get_return()          └── apply_scenario()                 │   │
│  │  └── delete_return()                                             │   │
│  │                                                                   │   │
│  │  AdvisoryService           IntakeService                         │   │
│  │  ├── generate_plan()       ├── start_session()                  │   │
│  │  ├── update_status()       ├── process_message()                │   │
│  │  ├── track_outcome()       ├── extract_data()                   │   │
│  │  └── export_report()       └── validate_completeness()          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    DOMAIN SERVICES                               │   │
│  │         (Complex business logic spanning aggregates)             │   │
│  │                                                                   │   │
│  │  CalculationEngine         OptimizationEngine                    │   │
│  │  ├── calculate_federal()   ├── optimize_filing_status()         │   │
│  │  ├── calculate_state()     ├── optimize_deductions()            │   │
│  │  ├── calculate_credits()   ├── optimize_credits()               │   │
│  │  └── apply_carryovers()    └── find_opportunities()             │   │
│  │                                                                   │   │
│  │  ValidationEngine          RulesEngine                           │   │
│  │  ├── validate_input()      ├── evaluate_rule()                  │   │
│  │  ├── validate_output()     ├── get_applicable_rules()           │   │
│  │  ├── check_consistency()   └── explain_rule()                   │   │
│  │  └── get_warnings()                                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Service Contracts (Interfaces)

```python
# Building Block: Service Interfaces

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

class ITaxReturnService(ABC):
    """Tax return lifecycle management."""

    @abstractmethod
    async def create(self, taxpayer_id: UUID, tax_year: int) -> TaxReturn:
        """Create new tax return."""

    @abstractmethod
    async def get(self, return_id: UUID) -> Optional[TaxReturn]:
        """Retrieve tax return."""

    @abstractmethod
    async def calculate(self, return_id: UUID) -> CalculationResult:
        """Perform full calculation."""

    @abstractmethod
    async def save(self, tax_return: TaxReturn) -> None:
        """Persist tax return."""


class IScenarioService(ABC):
    """Scenario management for what-if analysis."""

    @abstractmethod
    async def create_scenario(
        self,
        return_id: UUID,
        name: str,
        modifications: List[Modification]
    ) -> Scenario:
        """Create and calculate a scenario."""

    @abstractmethod
    async def compare(
        self,
        scenario_ids: List[UUID]
    ) -> ScenarioComparison:
        """Compare multiple scenarios."""

    @abstractmethod
    async def get_filing_status_scenarios(
        self,
        return_id: UUID
    ) -> List[Scenario]:
        """Auto-generate all filing status scenarios."""


class IAdvisoryService(ABC):
    """Advisory and recommendation management."""

    @abstractmethod
    async def generate_recommendations(
        self,
        return_id: UUID
    ) -> AdvisoryPlan:
        """Generate comprehensive recommendations."""

    @abstractmethod
    async def apply_recommendation(
        self,
        recommendation_id: UUID
    ) -> ApplyResult:
        """Apply a recommendation to the return."""

    @abstractmethod
    async def export_advisory_report(
        self,
        plan_id: UUID,
        format: ExportFormat
    ) -> bytes:
        """Export client-facing advisory report."""


class IIntakeService(ABC):
    """AI-powered data intake."""

    @abstractmethod
    async def process_message(
        self,
        session_id: UUID,
        message: str
    ) -> IntakeResponse:
        """Process user message and extract data."""

    @abstractmethod
    async def get_next_questions(
        self,
        session_id: UUID
    ) -> List[Question]:
        """Get intelligent follow-up questions."""

    @abstractmethod
    async def validate_completeness(
        self,
        session_id: UUID
    ) -> CompletenessReport:
        """Check if intake is complete."""
```

---

## Building Block #3: Repository Pattern

### 3.1 Repository Interfaces

```python
# Building Block: Repository Interfaces

class IRepository(ABC, Generic[T]):
    """Base repository interface."""

    @abstractmethod
    async def get(self, id: UUID) -> Optional[T]:
        pass

    @abstractmethod
    async def save(self, entity: T) -> None:
        pass

    @abstractmethod
    async def delete(self, id: UUID) -> None:
        pass


class ITaxReturnRepository(IRepository[TaxReturn]):
    """Tax return specific repository."""

    @abstractmethod
    async def get_by_client(self, client_id: UUID) -> List[TaxReturn]:
        """Get all returns for a client."""

    @abstractmethod
    async def get_by_year(self, client_id: UUID, year: int) -> Optional[TaxReturn]:
        """Get return for specific year."""

    @abstractmethod
    async def get_prior_year(self, return_id: UUID) -> Optional[TaxReturn]:
        """Get prior year return."""


class IScenarioRepository(IRepository[Scenario]):
    """Scenario specific repository."""

    @abstractmethod
    async def get_by_return(self, return_id: UUID) -> List[Scenario]:
        """Get all scenarios for a return."""

    @abstractmethod
    async def get_comparisons(self, return_id: UUID) -> List[ScenarioComparison]:
        """Get scenario comparisons."""


class IEventStore(ABC):
    """Event store for audit trail."""

    @abstractmethod
    async def append(self, stream_id: str, event: DomainEvent) -> None:
        """Append event to stream."""

    @abstractmethod
    async def get_events(
        self,
        stream_id: str,
        from_version: int = 0
    ) -> List[DomainEvent]:
        """Get events from stream."""
```

### 3.2 Database Schema

```sql
-- Building Block: Database Schema

-- Core Tables
CREATE TABLE clients (
    client_id UUID PRIMARY KEY,
    external_id VARCHAR(50),
    ssn_hash VARCHAR(64) UNIQUE,
    name_encrypted BYTEA,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tax_returns (
    return_id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients(client_id),
    tax_year INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    return_data JSONB NOT NULL,
    calculation_result JSONB,
    prior_return_id UUID REFERENCES tax_returns(return_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, tax_year)
);

-- Scenario Tables
CREATE TABLE scenarios (
    scenario_id UUID PRIMARY KEY,
    return_id UUID REFERENCES tax_returns(return_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    scenario_type VARCHAR(30) NOT NULL,
    base_snapshot JSONB NOT NULL,
    modifications JSONB NOT NULL,
    result JSONB,
    savings_vs_base DECIMAL(12,2),
    is_recommended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scenario_comparisons (
    comparison_id UUID PRIMARY KEY,
    return_id UUID REFERENCES tax_returns(return_id) ON DELETE CASCADE,
    name VARCHAR(100),
    scenario_ids UUID[] NOT NULL,
    winner_scenario_id UUID,
    comparison_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Advisory Tables
CREATE TABLE advisory_plans (
    plan_id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients(client_id),
    return_id UUID REFERENCES tax_returns(return_id),
    tax_year INTEGER NOT NULL,
    total_savings_identified DECIMAL(12,2),
    plan_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE recommendations (
    recommendation_id UUID PRIMARY KEY,
    plan_id UUID REFERENCES advisory_plans(plan_id) ON DELETE CASCADE,
    category VARCHAR(30) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    estimated_savings DECIMAL(12,2),
    status VARCHAR(20) DEFAULT 'proposed',
    outcome_actual_savings DECIMAL(12,2),
    recommendation_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Event Store (Audit Trail)
CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    stream_id VARCHAR(100) NOT NULL,
    stream_type VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    metadata JSONB,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stream_id, version)
);

CREATE INDEX idx_events_stream ON events(stream_id, version);
CREATE INDEX idx_tax_returns_client ON tax_returns(client_id, tax_year);
CREATE INDEX idx_scenarios_return ON scenarios(return_id);
```

---

## Building Block #4: Event System

### 4.1 Domain Events

```python
# Building Block: Domain Events

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Any, Dict

@dataclass
class DomainEvent:
    """Base domain event."""
    event_id: UUID
    occurred_at: datetime
    metadata: Dict[str, Any]

# Tax Return Events
@dataclass
class TaxReturnCreated(DomainEvent):
    return_id: UUID
    client_id: UUID
    tax_year: int

@dataclass
class TaxReturnCalculated(DomainEvent):
    return_id: UUID
    total_tax: float
    effective_rate: float
    calculation_duration_ms: int

@dataclass
class TaxReturnUpdated(DomainEvent):
    return_id: UUID
    changed_fields: Dict[str, Any]
    previous_values: Dict[str, Any]

# Scenario Events
@dataclass
class ScenarioCreated(DomainEvent):
    scenario_id: UUID
    return_id: UUID
    scenario_type: str
    modifications: Dict[str, Any]

@dataclass
class ScenarioCompared(DomainEvent):
    comparison_id: UUID
    scenario_ids: list
    winner_id: UUID
    max_savings: float

# Advisory Events
@dataclass
class RecommendationGenerated(DomainEvent):
    plan_id: UUID
    return_id: UUID
    recommendation_count: int
    total_potential_savings: float

@dataclass
class RecommendationStatusChanged(DomainEvent):
    recommendation_id: UUID
    old_status: str
    new_status: str
    changed_by: str

# Intake Events
@dataclass
class IntakeSessionStarted(DomainEvent):
    session_id: UUID
    client_id: UUID

@dataclass
class DataExtracted(DomainEvent):
    session_id: UUID
    field_path: str
    extracted_value: Any
    confidence: float
```

### 4.2 Event Bus

```python
# Building Block: Event Bus

from typing import Callable, Dict, List, Type

class EventBus:
    """Simple in-process event bus."""

    def __init__(self):
        self._handlers: Dict[Type[DomainEvent], List[Callable]] = {}

    def subscribe(
        self,
        event_type: Type[DomainEvent],
        handler: Callable[[DomainEvent], None]
    ):
        """Subscribe to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent):
        """Publish an event to all subscribers."""
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            await handler(event)

# Event Handlers
class AuditEventHandler:
    """Persists all events to event store."""

    def __init__(self, event_store: IEventStore):
        self._store = event_store

    async def handle(self, event: DomainEvent):
        stream_id = self._get_stream_id(event)
        await self._store.append(stream_id, event)

class LoggingEventHandler:
    """Logs events for observability."""

    async def handle(self, event: DomainEvent):
        logger.info(f"Event: {type(event).__name__}", extra={
            "event_id": str(event.event_id),
            "event_type": type(event).__name__,
            "data": event.__dict__
        })
```

---

## Building Block #5: API Layer

### 5.1 API Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                       API ENDPOINTS                             │
│                                                                 │
│  /api/v1/                                                       │
│  │                                                              │
│  ├── /returns                                                   │
│  │   ├── POST   /              → Create return                 │
│  │   ├── GET    /{id}          → Get return                    │
│  │   ├── PUT    /{id}          → Update return                 │
│  │   ├── DELETE /{id}          → Delete return                 │
│  │   ├── POST   /{id}/calculate → Calculate taxes              │
│  │   └── GET    /{id}/summary   → Get summary                  │
│  │                                                              │
│  ├── /scenarios                                                 │
│  │   ├── POST   /              → Create scenario               │
│  │   ├── GET    /return/{id}   → List scenarios for return    │
│  │   ├── POST   /compare       → Compare scenarios             │
│  │   ├── GET    /filing-status/{return_id} → Filing status    │
│  │   ├── POST   /entity        → Entity comparison             │
│  │   └── POST   /{id}/apply    → Apply scenario to return     │
│  │                                                              │
│  ├── /advisory                                                  │
│  │   ├── POST   /generate      → Generate recommendations      │
│  │   ├── GET    /{plan_id}     → Get advisory plan            │
│  │   ├── PUT    /recommendation/{id}/status → Update status   │
│  │   └── GET    /{plan_id}/export → Export report             │
│  │                                                              │
│  ├── /intake                                                    │
│  │   ├── POST   /session       → Start intake session          │
│  │   ├── POST   /message       → Process message               │
│  │   ├── GET    /questions     → Get next questions            │
│  │   └── GET    /completeness  → Check completeness            │
│  │                                                              │
│  ├── /documents                                                 │
│  │   ├── POST   /upload        → Upload document               │
│  │   ├── GET    /{id}          → Get document                  │
│  │   └── POST   /{id}/extract  → Extract data from doc        │
│  │                                                              │
│  └── /export                                                    │
│      ├── GET    /pdf/{return_id}     → Export PDF              │
│      ├── GET    /json/{return_id}    → Export JSON             │
│      └── GET    /advisory/{plan_id}  → Export advisory report  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 API Request/Response Models

```python
# Building Block: API Models

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

# === Scenario API ===

class CreateScenarioRequest(BaseModel):
    return_id: UUID
    name: str
    scenario_type: str  # what_if, filing_status, entity
    modifications: Dict[str, Any]

class ScenarioResponse(BaseModel):
    scenario_id: UUID
    name: str
    base_tax: float
    scenario_tax: float
    savings: float
    effective_rate: float
    effective_rate_change: float
    is_recommended: bool

class CompareRequest(BaseModel):
    return_id: UUID
    scenario_ids: List[UUID]

class ComparisonResponse(BaseModel):
    comparison_id: UUID
    scenarios: List[ScenarioResponse]
    recommended: Optional[UUID]
    max_savings: float
    summary: str

# === Advisory API ===

class GenerateAdvisoryRequest(BaseModel):
    return_id: UUID
    include_categories: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    recommendation_id: UUID
    category: str
    priority: str
    title: str
    estimated_savings: float
    description: str
    action_steps: List[str]
    complexity: str
    status: str

class AdvisoryPlanResponse(BaseModel):
    plan_id: UUID
    tax_year: int
    total_potential_savings: float
    immediate_actions: List[RecommendationResponse]
    current_year: List[RecommendationResponse]
    long_term: List[RecommendationResponse]
    confidence_score: float
    generated_at: datetime

# === Intake API ===

class IntakeMessageRequest(BaseModel):
    session_id: UUID
    message: str

class ExtractedData(BaseModel):
    field: str
    value: Any
    confidence: float

class IntakeResponse(BaseModel):
    response_message: str
    extracted_data: List[ExtractedData]
    next_questions: List[str]
    completeness: float
    stage: str
```

---

## Building Block #6: Calculation Pipeline

### 6.1 Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CALCULATION PIPELINE                                │
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │  VALIDATE   │ →  │  PREPARE    │ →  │  CALCULATE  │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
│        │                  │                  │                          │
│        ▼                  ▼                  ▼                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │ Input       │    │ Load prior  │    │ Federal tax │                │
│  │ validation  │    │ year data   │    │ calculation │                │
│  │             │    │             │    │             │                │
│  │ Required    │    │ Apply       │    │ State tax   │                │
│  │ fields      │    │ carryovers  │    │ calculation │                │
│  │             │    │             │    │             │                │
│  │ Sanity      │    │ Prepare     │    │ Credits &   │                │
│  │ checks      │    │ breakdown   │    │ payments    │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
│                                              │                          │
│                                              ▼                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │  STORE      │ ←  │  VALIDATE   │ ←  │  FINALIZE   │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
│        │                  │                  │                          │
│        ▼                  ▼                  ▼                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │ Save result │    │ Output      │    │ Compute     │                │
│  │ to return   │    │ validation  │    │ refund/owed │                │
│  │             │    │             │    │             │                │
│  │ Emit events │    │ Sanity      │    │ Generate    │                │
│  │             │    │ checks      │    │ breakdown   │                │
│  │             │    │             │    │             │                │
│  │ Update      │    │ Add         │    │ Add         │                │
│  │ audit trail │    │ warnings    │    │ explanations│                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Pipeline Implementation

```python
# Building Block: Calculation Pipeline

from dataclasses import dataclass
from typing import List, Optional
from abc import ABC, abstractmethod

@dataclass
class PipelineContext:
    """Context passed through pipeline."""
    tax_return: TaxReturn
    prior_year: Optional[TaxReturn]
    breakdown: CalculationBreakdown
    warnings: List[str]
    errors: List[str]
    metadata: dict

class PipelineStep(ABC):
    """Base pipeline step."""

    @abstractmethod
    async def execute(self, context: PipelineContext) -> PipelineContext:
        pass

class ValidationStep(PipelineStep):
    """Validate inputs before calculation."""

    async def execute(self, context: PipelineContext) -> PipelineContext:
        validator = CalculationValidator()
        result = validator.validate_inputs(context.tax_return)

        if not result.is_valid:
            context.errors.extend(result.errors)
        context.warnings.extend(result.warnings)

        return context

class PrepareStep(PipelineStep):
    """Load prior year and prepare carryovers."""

    def __init__(self, return_repo: ITaxReturnRepository):
        self._repo = return_repo

    async def execute(self, context: PipelineContext) -> PipelineContext:
        # Load prior year if available
        if context.tax_return.prior_return_id:
            context.prior_year = await self._repo.get(
                context.tax_return.prior_return_id
            )

        # Apply carryovers
        if context.prior_year and context.tax_return.prior_year_carryovers:
            self._apply_carryovers(context)

        return context

class FederalCalculationStep(PipelineStep):
    """Calculate federal taxes."""

    def __init__(self, engine: FederalTaxEngine):
        self._engine = engine

    async def execute(self, context: PipelineContext) -> PipelineContext:
        context.breakdown = self._engine.calculate(context.tax_return)
        return context

class StateCalculationStep(PipelineStep):
    """Calculate state taxes."""

    def __init__(self, engine: StateTaxEngine):
        self._engine = engine

    async def execute(self, context: PipelineContext) -> PipelineContext:
        state_code = context.tax_return.state_of_residence
        if state_code:
            state_result = self._engine.calculate(context.tax_return, state_code)
            context.breakdown.state_result = state_result
        return context

class OutputValidationStep(PipelineStep):
    """Validate calculation outputs."""

    async def execute(self, context: PipelineContext) -> PipelineContext:
        validator = CalculationValidator()
        result = validator.validate_outputs(context.breakdown)
        context.warnings.extend(result.warnings)
        return context

class CalculationPipeline:
    """Orchestrates calculation pipeline."""

    def __init__(self, steps: List[PipelineStep]):
        self._steps = steps

    async def execute(self, tax_return: TaxReturn) -> CalculationResult:
        context = PipelineContext(
            tax_return=tax_return,
            prior_year=None,
            breakdown=CalculationBreakdown(),
            warnings=[],
            errors=[],
            metadata={}
        )

        for step in self._steps:
            context = await step.execute(context)
            if context.errors:
                break  # Stop on errors

        return CalculationResult(
            breakdown=context.breakdown,
            warnings=context.warnings,
            errors=context.errors
        )
```

---

## Building Block #7: UI/UX Architecture

### 7.1 Design Philosophy: Decision-First, Not Form-First

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     UI/UX DESIGN PRINCIPLES                             │
│                                                                         │
│  TRADITIONAL TAX SOFTWARE:        OUR APPROACH:                        │
│  ─────────────────────────        ─────────────                        │
│  Form-first                   →   Decision-first                       │
│  "Fill out Schedule C"            "Should you form an S-Corp?"        │
│                                                                         │
│  Data entry focus             →   Insight focus                        │
│  "Enter your wages"               "You're leaving $2,400 on the table" │
│                                                                         │
│  Sequential workflow          →   Exploratory workflow                 │
│  "Step 1, Step 2, Step 3"         "What if... Compare... Decide"       │
│                                                                         │
│  Show everything              →   Progressive disclosure               │
│  "Here's 100 fields"              "Here's what matters now"            │
│                                                                         │
│  Technical language           →   Plain language                       │
│  "AGI exceeds §68 threshold"      "Your income is high enough that..." │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Core UI Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      UI COMPONENT HIERARCHY                             │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      PAGE LAYOUTS                                │   │
│  │                                                                   │   │
│  │  Dashboard        Intake         Scenarios       Advisory        │   │
│  │  ┌─────────┐      ┌─────────┐    ┌─────────┐    ┌─────────┐     │   │
│  │  │ Summary │      │  Chat   │    │ Compare │    │ Plan    │     │   │
│  │  │ Cards   │      │  +      │    │ Table   │    │ +       │     │   │
│  │  │         │      │ Progress│    │         │    │ Actions │     │   │
│  │  └─────────┘      └─────────┘    └─────────┘    └─────────┘     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      SMART COMPONENTS                            │   │
│  │                                                                   │   │
│  │  TaxInsightCard       ScenarioSlider      RecommendationCard    │   │
│  │  ┌───────────────┐    ┌───────────────┐   ┌───────────────┐     │   │
│  │  │ 💡 Insight    │    │ ◀──●──────▶   │   │ ⭐ Save $2.4k │     │   │
│  │  │ Save $2,400   │    │ $0    $23,500 │   │ Max 401k      │     │   │
│  │  │ [See how →]   │    │ Tax: $22,100  │   │ [Apply]       │     │   │
│  │  └───────────────┘    └───────────────┘   └───────────────┘     │   │
│  │                                                                   │   │
│  │  ComparisonTable      ProgressIndicator   ValidationAlert       │   │
│  │  ┌───────────────┐    ┌───────────────┐   ┌───────────────┐     │   │
│  │  │ Option │ Tax  │    │ ████████░░ 80%│   │ ⚠️ Missing    │     │   │
│  │  │ MFJ    │ $24k │    │ Income done   │   │ W-2 info      │     │   │
│  │  │ HOH✓   │ $22k │    │               │   │ [Add now]     │     │   │
│  │  └───────────────┘    └───────────────┘   └───────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      BASE COMPONENTS                             │   │
│  │                                                                   │   │
│  │  Button  Input  Card  Table  Modal  Toast  Tooltip  Badge       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Key Screens

#### Screen 1: Decision Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TaxPro Intelligence                              John Smith │ 2025    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  YOUR TAX SNAPSHOT                                                      │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Federal Tax         State Tax          Total Owed                │ │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐           │ │
│  │  │   $18,450   │    │    $4,200   │    │   -$2,350   │           │ │
│  │  │  18.5% rate │    │   CA 4.2%   │    │   REFUND    │           │ │
│  │  └─────────────┘    └─────────────┘    └─────────────┘           │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  OPPORTUNITIES FOUND                                     View all →     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 💡 Maximize 401k              │ 💡 Filing Status Change        │   │
│  │    Save $2,400/year           │    Save $1,200 this year       │   │
│  │    [Explore →]                │    [Compare →]                 │   │
│  ├───────────────────────────────┼─────────────────────────────────┤   │
│  │ 💡 HSA Contribution           │ 💡 Charitable Bunching         │   │
│  │    Save $1,100/year           │    Save $650 over 2 years      │   │
│  │    [Explore →]                │    [Explore →]                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  QUICK ACTIONS                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │  📊 Compare  │  │  📄 Export   │  │  🤖 Ask AI   │                 │
│  │  Scenarios   │  │  Report      │  │  Questions   │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Screen 2: Scenario Comparison

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard           COMPARE FILING STATUSES                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Drag to compare                                                │   │
│  │  ┌─────────────────────────────────────────────────────────┐   │   │
│  │  │                    YOUR SAVINGS                          │   │   │
│  │  │     MFJ          Single         HOH (✓ Best)            │   │   │
│  │  │   $24,500       $26,200         $22,800                 │   │   │
│  │  │                                  Save $1,700            │   │   │
│  │  └─────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  BREAKDOWN                                                              │
│  ┌────────────────┬───────────┬───────────┬───────────┐               │
│  │                │    MFJ    │   Single  │    HOH    │               │
│  ├────────────────┼───────────┼───────────┼───────────┤               │
│  │ Federal Tax    │  $18,500  │  $20,200  │  $17,300  │               │
│  │ State Tax      │   $6,000  │   $6,000  │   $5,500  │               │
│  │ Effective Rate │   18.5%   │   20.2%   │   17.3%   │               │
│  │ Std Deduction  │  $30,000  │  $15,000  │  $22,500  │               │
│  └────────────────┴───────────┴───────────┴───────────┘               │
│                                                                         │
│  ⚠️ HOH requires: Unmarried + paid >50% household costs + qualifying  │
│     person lived with you.  [Verify eligibility →]                     │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  [Cancel]                              [Apply HOH to My Return]   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Screen 3: AI Intake

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TaxPro Intelligence                        Progress: ████████░░ 75%   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                                                                   │   │
│  │  🤖  I see you have income from Acme Corp ($85,000).             │   │
│  │      Did you have any other employers in 2025?                   │   │
│  │                                                                   │   │
│  │      ┌──────────────────────────────────────────────────────┐   │   │
│  │      │  [No, just Acme Corp]  [Yes, I had another job]      │   │   │
│  │      └──────────────────────────────────────────────────────┘   │   │
│  │                                                                   │   │
│  │  ─────────────────────────────────────────────────────────────   │   │
│  │                                                                   │   │
│  │  👤  No, Acme was my only employer                               │   │
│  │                                                                   │   │
│  │  ─────────────────────────────────────────────────────────────   │   │
│  │                                                                   │   │
│  │  🤖  Got it! I noticed your W-2 shows $0 for 401k contributions  │   │
│  │      (Box 12, code D). Does Acme offer a 401k plan?              │   │
│  │                                                                   │   │
│  │      💡 If they do, you could save up to $5,400 in taxes by      │   │
│  │         contributing to it.                                       │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Type your response...                              [Send →]     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  DATA COLLECTED                                                         │
│  ✓ Personal Info  ✓ W-2 Income  ○ Other Income  ○ Deductions          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Screen 4: Advisory Report

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ← Back                        YOUR 2025 TAX PLAN           [Export ↓] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  POTENTIAL SAVINGS IDENTIFIED                                     │ │
│  │                                                                    │ │
│  │     $8,450                    5 Actions                           │ │
│  │     Total Savings             Recommended                         │ │
│  │                                                                    │ │
│  │     ██████████████████░░░░░░  2 Immediate │ 2 This Year │ 1 Long │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ⚡ IMMEDIATE ACTIONS (Before Dec 31)                                  │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │ 1. Maximize 401k Contribution              Save $2,400/yr  │ │ │
│  │  │    Contribute additional $8,500 before Dec 31              │ │ │
│  │  │    [Mark Done]  [View Details]  [Skip]                     │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │  ┌─────────────────────────────────────────────────────────────┐ │ │
│  │  │ 2. Open & Fund HSA                         Save $1,100/yr  │ │ │
│  │  │    Contribute $4,300 to HSA before April 15                │ │ │
│  │  │    [Mark Done]  [View Details]  [Skip]                     │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  📅 THIS YEAR                                          [Expand ↓]      │
│  📈 LONG-TERM                                          [Expand ↓]      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Building Block #8: Infrastructure

### 8.1 Observability Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      OBSERVABILITY INFRASTRUCTURE                       │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │    LOGGING      │  │    METRICS      │  │    TRACING      │        │
│  │                 │  │                 │  │                 │        │
│  │  Structured     │  │  Prometheus/    │  │  OpenTelemetry  │        │
│  │  JSON logs      │  │  StatsD         │  │  Jaeger         │        │
│  │                 │  │                 │  │                 │        │
│  │  - Calculation  │  │  - Calc time    │  │  - Request flow │        │
│  │    events       │  │  - API latency  │  │  - Service deps │        │
│  │  - Audit trail  │  │  - Error rates  │  │  - Bottlenecks  │        │
│  │  - Errors       │  │  - Usage stats  │  │                 │        │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘        │
│           │                   │                   │                    │
│           ▼                   ▼                   ▼                    │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                     UNIFIED DASHBOARD                            │  │
│  │                     (Grafana / DataDog)                          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Configuration Management

```python
# Building Block: Configuration

from pydantic_settings import BaseSettings
from typing import Optional

class DatabaseConfig(BaseSettings):
    """Database configuration."""
    driver: str = "sqlite"
    host: str = "localhost"
    port: int = 5432
    name: str = "taxpro"
    user: Optional[str] = None
    password: Optional[str] = None

    class Config:
        env_prefix = "DB_"

class AIConfig(BaseSettings):
    """AI/LLM configuration."""
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 1000

    class Config:
        env_prefix = "AI_"

class AppConfig(BaseSettings):
    """Application configuration."""
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    tax_year: int = 2025

    database: DatabaseConfig = DatabaseConfig()
    ai: AIConfig = AIConfig()

    class Config:
        env_prefix = "APP_"
```

---

## Building Block #9: Security

### 9.1 Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      SECURITY ARCHITECTURE                              │
│                                                                         │
│  DATA AT REST                    DATA IN TRANSIT                       │
│  ─────────────                   ───────────────                       │
│  • SSN: Hashed (SHA-256)         • TLS 1.3 everywhere                  │
│  • PII: Encrypted (AES-256)      • Certificate pinning                 │
│  • Keys: Vault/KMS               • API authentication                  │
│                                                                         │
│  ACCESS CONTROL                  AUDIT                                 │
│  ──────────────                  ─────                                 │
│  • Role-based (RBAC)             • All access logged                   │
│  • Firm → Preparer → Client      • Event sourcing                      │
│  • API key scoping               • Tamper-evident trails               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    DATA CLASSIFICATION                           │   │
│  │                                                                   │   │
│  │  SENSITIVE (Encrypt)    CONFIDENTIAL (Protect)   INTERNAL       │   │
│  │  • SSN                  • Name, Address          • Calculations  │   │
│  │  • Bank accounts        • Income amounts         • Scenarios     │   │
│  │  • Tax ID               • Filing status          • Metadata      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Sequence

### Phase 1: Core Foundation (Week 1-2)

```
DELIVERABLES:
├── Domain Models
│   ├── PriorYearData model
│   ├── Scenario aggregate
│   └── Advisory aggregate
│
├── Repository Layer
│   ├── ITaxReturnRepository
│   ├── IScenarioRepository
│   └── Database migrations
│
└── Event System
    ├── Domain events
    ├── Event bus
    └── Event store (audit)
```

### Phase 2: Service Layer (Week 3-4)

```
DELIVERABLES:
├── Application Services
│   ├── TaxReturnService
│   ├── ScenarioService
│   └── AdvisoryService
│
├── Domain Services
│   ├── CalculationPipeline
│   ├── ValidationEngine
│   └── OptimizationEngine
│
└── Logging Infrastructure
    ├── Structured logging
    └── Calculation audit trail
```

### Phase 3: API Layer (Week 5-6)

```
DELIVERABLES:
├── Scenario API
│   ├── Create/Get/List endpoints
│   ├── Compare endpoint
│   └── Apply endpoint
│
├── Advisory API
│   ├── Generate endpoint
│   ├── Status update endpoint
│   └── Export endpoint
│
└── Enhanced Intake API
    ├── Intelligent questions
    └── Completeness check
```

### Phase 4: UI Foundation (Week 7-8)

```
DELIVERABLES:
├── Component Library
│   ├── Base components
│   └── Smart components
│
├── Core Screens
│   ├── Dashboard
│   ├── Scenario comparison
│   └── Advisory view
│
└── State Management
    ├── API integration
    └── Real-time updates
```

---

## Summary: Building Blocks Checklist

### Backend Building Blocks

| # | Block | Purpose | Status |
|---|-------|---------|--------|
| 1 | Domain Models | Core data structures | 🔨 Enhance |
| 2 | Service Layer | Business logic orchestration | 🔨 Build |
| 3 | Repository Pattern | Data access abstraction | 🔨 Build |
| 4 | Event System | Audit trail, async processing | 🔨 Build |
| 5 | Calculation Pipeline | Structured tax calculation | 🔨 Enhance |
| 6 | Validation Engine | Input/output validation | 🔨 Build |
| 7 | Logging Infrastructure | Observability | 🔨 Build |
| 8 | Configuration | Externalized settings | 🔨 Build |

### Frontend Building Blocks

| # | Block | Purpose | Status |
|---|-------|---------|--------|
| 1 | Component Library | Reusable UI elements | 🔨 Build |
| 2 | Dashboard View | Decision-first home | 🔨 Build |
| 3 | Scenario Comparison | What-if exploration | 🔨 Build |
| 4 | AI Intake | Conversational data entry | 🔨 Build |
| 5 | Advisory View | Recommendation management | 🔨 Build |
| 6 | State Management | API integration | 🔨 Build |

---

*Document Version: 1.0*
*Architecture Date: January 2025*
