"""
Repository Interfaces for Tax Decision Intelligence Platform.

Repository interfaces define the contract for data access, following the
Repository pattern from Domain-Driven Design. Implementations are provided
in the infrastructure layer.

This abstraction allows:
1. Swapping storage backends (SQLite -> PostgreSQL)
2. Testing with in-memory implementations
3. Clear separation between domain and infrastructure
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Generic, TypeVar
from uuid import UUID
from datetime import datetime

from .events import DomainEvent
from .aggregates import Scenario, AdvisoryPlan, ClientProfile
from .value_objects import PriorYearCarryovers


# Generic type for repository entities
T = TypeVar('T')


class IRepository(ABC, Generic[T]):
    """
    Base repository interface.

    Provides standard CRUD operations for aggregate roots.
    """

    @abstractmethod
    async def get(self, id: UUID) -> Optional[T]:
        """
        Retrieve an entity by ID.

        Args:
            id: Unique identifier of the entity

        Returns:
            The entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def save(self, entity: T) -> None:
        """
        Save an entity (create or update).

        Args:
            entity: The entity to save
        """
        pass

    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """
        Delete an entity by ID.

        Args:
            id: Unique identifier of the entity

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, id: UUID) -> bool:
        """
        Check if an entity exists.

        Args:
            id: Unique identifier to check

        Returns:
            True if exists, False otherwise
        """
        pass


class ITaxReturnRepository(ABC):
    """
    Tax Return Repository Interface.

    Provides access to tax return data with specialized query methods.
    Note: Uses Dict[str, Any] for tax returns since they use the existing
    Pydantic models from src/models/tax_return.py
    """

    @abstractmethod
    async def get(self, return_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a tax return by ID."""
        pass

    @abstractmethod
    async def save(self, return_id: UUID, tax_return_data: Dict[str, Any]) -> None:
        """Save a tax return."""
        pass

    @abstractmethod
    async def delete(self, return_id: UUID) -> bool:
        """Delete a tax return."""
        pass

    @abstractmethod
    async def get_by_client(self, client_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all tax returns for a client.

        Args:
            client_id: Client identifier

        Returns:
            List of tax returns for the client
        """
        pass

    @abstractmethod
    async def get_by_year(self, client_id: UUID, tax_year: int) -> Optional[Dict[str, Any]]:
        """
        Get a tax return for a specific year.

        Args:
            client_id: Client identifier
            tax_year: Tax year

        Returns:
            Tax return for that year if found
        """
        pass

    @abstractmethod
    async def get_prior_year(self, return_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get the prior year tax return.

        Args:
            return_id: Current return ID

        Returns:
            Prior year return if available
        """
        pass

    @abstractmethod
    async def list_returns(
        self,
        tax_year: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List tax returns with optional filters.

        Args:
            tax_year: Filter by tax year
            status: Filter by status
            limit: Maximum number to return
            offset: Offset for pagination

        Returns:
            List of matching tax returns
        """
        pass

    @abstractmethod
    async def get_calculation_result(self, return_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get the calculation result for a return.

        Args:
            return_id: Return identifier

        Returns:
            Calculation result if available
        """
        pass


class IScenarioRepository(IRepository[Scenario]):
    """
    Scenario Repository Interface.

    Provides access to scenario data with specialized query methods.
    """

    @abstractmethod
    async def get_by_return(self, return_id: UUID) -> List[Scenario]:
        """
        Get all scenarios for a tax return.

        Args:
            return_id: Return identifier

        Returns:
            List of scenarios for the return
        """
        pass

    @abstractmethod
    async def get_by_type(self, return_id: UUID, scenario_type: str) -> List[Scenario]:
        """
        Get scenarios of a specific type.

        Args:
            return_id: Return identifier
            scenario_type: Type of scenario

        Returns:
            List of matching scenarios
        """
        pass

    @abstractmethod
    async def get_recommended(self, return_id: UUID) -> Optional[Scenario]:
        """
        Get the recommended scenario for a return.

        Args:
            return_id: Return identifier

        Returns:
            The recommended scenario if one is marked
        """
        pass

    @abstractmethod
    async def delete_by_return(self, return_id: UUID) -> int:
        """
        Delete all scenarios for a return.

        Args:
            return_id: Return identifier

        Returns:
            Number of scenarios deleted
        """
        pass

    @abstractmethod
    async def save_comparison(
        self,
        return_id: UUID,
        scenario_ids: List[UUID],
        winner_id: Optional[UUID],
        comparison_data: Dict[str, Any]
    ) -> UUID:
        """
        Save a scenario comparison.

        Args:
            return_id: Return identifier
            scenario_ids: IDs of compared scenarios
            winner_id: ID of winning scenario
            comparison_data: Comparison details

        Returns:
            Comparison ID
        """
        pass

    @abstractmethod
    async def get_comparisons(self, return_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all scenario comparisons for a return.

        Args:
            return_id: Return identifier

        Returns:
            List of comparisons
        """
        pass


class IAdvisoryRepository(IRepository[AdvisoryPlan]):
    """
    Advisory Repository Interface.

    Provides access to advisory plan and recommendation data.
    """

    @abstractmethod
    async def get_by_client(self, client_id: UUID) -> List[AdvisoryPlan]:
        """
        Get all advisory plans for a client.

        Args:
            client_id: Client identifier

        Returns:
            List of advisory plans
        """
        pass

    @abstractmethod
    async def get_by_return(self, return_id: UUID) -> Optional[AdvisoryPlan]:
        """
        Get the advisory plan for a specific return.

        Args:
            return_id: Return identifier

        Returns:
            Advisory plan if found
        """
        pass

    @abstractmethod
    async def get_by_year(self, client_id: UUID, tax_year: int) -> Optional[AdvisoryPlan]:
        """
        Get the advisory plan for a specific year.

        Args:
            client_id: Client identifier
            tax_year: Tax year

        Returns:
            Advisory plan if found
        """
        pass

    @abstractmethod
    async def save_recommendation(
        self,
        plan_id: UUID,
        recommendation: Dict[str, Any]
    ) -> UUID:
        """
        Save or update a recommendation.

        Args:
            plan_id: Plan identifier
            recommendation: Recommendation data

        Returns:
            Recommendation ID
        """
        pass

    @abstractmethod
    async def get_recommendations_by_status(
        self,
        plan_id: UUID,
        status: str
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations by status.

        Args:
            plan_id: Plan identifier
            status: Status to filter by

        Returns:
            List of matching recommendations
        """
        pass

    @abstractmethod
    async def update_recommendation_status(
        self,
        recommendation_id: UUID,
        status: str,
        changed_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Update recommendation status.

        Args:
            recommendation_id: Recommendation identifier
            status: New status
            changed_by: Who made the change
            reason: Reason for change (especially for declined)

        Returns:
            True if updated, False if not found
        """
        pass


class IClientRepository(IRepository[ClientProfile]):
    """
    Client Repository Interface.

    Provides access to client profile data.
    """

    @abstractmethod
    async def get_by_external_id(self, external_id: str) -> Optional[ClientProfile]:
        """
        Get a client by their external ID.

        Args:
            external_id: CPA's client number

        Returns:
            Client profile if found
        """
        pass

    @abstractmethod
    async def get_by_ssn_hash(self, ssn_hash: str) -> Optional[ClientProfile]:
        """
        Get a client by their SSN hash.

        Args:
            ssn_hash: Hashed SSN

        Returns:
            Client profile if found
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 20
    ) -> List[ClientProfile]:
        """
        Search clients by name or external ID.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching clients
        """
        pass

    @abstractmethod
    async def get_active_clients(self, limit: int = 100) -> List[ClientProfile]:
        """
        Get active clients.

        Args:
            limit: Maximum results

        Returns:
            List of active clients
        """
        pass

    @abstractmethod
    async def update_carryovers(
        self,
        client_id: UUID,
        carryovers: PriorYearCarryovers
    ) -> bool:
        """
        Update client carryover balances.

        Args:
            client_id: Client identifier
            carryovers: New carryover balances

        Returns:
            True if updated
        """
        pass


class IEventStore(ABC):
    """
    Event Store Interface.

    Provides event sourcing capabilities for complete audit trails.
    """

    @abstractmethod
    async def append(self, stream_id: str, event: DomainEvent) -> None:
        """
        Append an event to a stream.

        Args:
            stream_id: Stream identifier (typically aggregate_type:aggregate_id)
            event: The event to append
        """
        pass

    @abstractmethod
    async def append_batch(self, stream_id: str, events: List[DomainEvent]) -> None:
        """
        Append multiple events to a stream atomically.

        Args:
            stream_id: Stream identifier
            events: Events to append
        """
        pass

    @abstractmethod
    async def get_events(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: Optional[int] = None
    ) -> List[DomainEvent]:
        """
        Get events from a stream.

        Args:
            stream_id: Stream identifier
            from_version: Start version (inclusive)
            to_version: End version (inclusive), None for all

        Returns:
            List of events in order
        """
        pass

    @abstractmethod
    async def get_events_by_type(
        self,
        event_type: str,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[DomainEvent]:
        """
        Get events of a specific type.

        Args:
            event_type: Type of events to get
            since: Only events after this time
            limit: Maximum events to return

        Returns:
            List of matching events
        """
        pass

    @abstractmethod
    async def get_events_by_aggregate(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        since: Optional[datetime] = None
    ) -> List[DomainEvent]:
        """
        Get all events for an aggregate.

        Args:
            aggregate_type: Type of aggregate
            aggregate_id: Aggregate identifier
            since: Only events after this time

        Returns:
            List of events for the aggregate
        """
        pass

    @abstractmethod
    async def get_stream_version(self, stream_id: str) -> int:
        """
        Get the current version of a stream.

        Args:
            stream_id: Stream identifier

        Returns:
            Current version number, 0 if stream doesn't exist
        """
        pass

    @abstractmethod
    async def get_all_streams(self) -> List[str]:
        """
        Get all stream IDs.

        Returns:
            List of stream identifiers
        """
        pass


class IUnitOfWork(ABC):
    """
    Unit of Work Interface.

    Coordinates multiple repository operations as a single transaction.
    """

    @property
    @abstractmethod
    def tax_returns(self) -> ITaxReturnRepository:
        """Tax return repository."""
        pass

    @property
    @abstractmethod
    def scenarios(self) -> IScenarioRepository:
        """Scenario repository."""
        pass

    @property
    @abstractmethod
    def advisory(self) -> IAdvisoryRepository:
        """Advisory repository."""
        pass

    @property
    @abstractmethod
    def clients(self) -> IClientRepository:
        """Client repository."""
        pass

    @property
    @abstractmethod
    def events(self) -> IEventStore:
        """Event store."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit all changes."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback all changes."""
        pass

    @abstractmethod
    async def __aenter__(self) -> 'IUnitOfWork':
        """Enter async context."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context (commit or rollback)."""
        pass
