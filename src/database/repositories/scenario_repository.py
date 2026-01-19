"""Async Scenario Repository Implementation.

Implements IScenarioRepository using SQLAlchemy async sessions.
Provides CRUD operations for tax scenarios with proper transaction support.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.repositories import IScenarioRepository
from domain.aggregates import Scenario, ScenarioStatus

logger = logging.getLogger(__name__)


class ScenarioRepository(IScenarioRepository):
    """
    Async implementation of IScenarioRepository.

    Uses SQLAlchemy async sessions with JSONB storage for scenarios.
    Scenarios are stored as serialized JSON with indexed metadata columns.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with a session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def get(self, id: UUID) -> Optional[Scenario]:
        """
        Get a scenario by ID.

        Args:
            id: Scenario identifier.

        Returns:
            Scenario object or None if not found.
        """
        query = text("""
            SELECT scenario_id, return_id, name, scenario_type, status,
                   is_recommended, scenario_data, created_at, updated_at
            FROM scenarios WHERE scenario_id = :scenario_id
        """)
        result = await self._session.execute(query, {"scenario_id": str(id)})
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_scenario(row)

    async def save(self, entity: Scenario) -> None:
        """
        Save a scenario (upsert).

        Args:
            entity: Scenario to save.
        """
        exists = await self.exists(entity.scenario_id)
        now = datetime.utcnow().isoformat()

        # Serialize the scenario to JSON
        scenario_data = entity.model_dump_json()

        if exists:
            query = text("""
                UPDATE scenarios SET
                    return_id = :return_id,
                    name = :name,
                    scenario_type = :scenario_type,
                    status = :status,
                    is_recommended = :is_recommended,
                    scenario_data = :scenario_data,
                    updated_at = :updated_at
                WHERE scenario_id = :scenario_id
            """)
        else:
            query = text("""
                INSERT INTO scenarios (
                    scenario_id, return_id, name, scenario_type, status,
                    is_recommended, scenario_data, created_at, updated_at
                ) VALUES (
                    :scenario_id, :return_id, :name, :scenario_type, :status,
                    :is_recommended, :scenario_data, :created_at, :updated_at
                )
            """)

        params = {
            "scenario_id": str(entity.scenario_id),
            "return_id": str(entity.return_id),
            "name": entity.name,
            "scenario_type": entity.scenario_type.value,
            "status": entity.status.value,
            "is_recommended": entity.is_recommended,
            "scenario_data": scenario_data,
            "created_at": now,
            "updated_at": now,
        }

        await self._session.execute(query, params)
        logger.debug(f"Saved scenario: {entity.scenario_id}")

    async def delete(self, id: UUID) -> bool:
        """
        Delete a scenario.

        Args:
            id: Scenario identifier.

        Returns:
            True if deleted, False if not found.
        """
        query = text("DELETE FROM scenarios WHERE scenario_id = :scenario_id")
        result = await self._session.execute(query, {"scenario_id": str(id)})

        deleted = result.rowcount > 0
        if deleted:
            logger.debug(f"Deleted scenario: {id}")
        return deleted

    async def exists(self, id: UUID) -> bool:
        """Check if a scenario exists."""
        query = text("SELECT 1 FROM scenarios WHERE scenario_id = :scenario_id LIMIT 1")
        result = await self._session.execute(query, {"scenario_id": str(id)})
        return result.fetchone() is not None

    async def get_by_return(self, return_id: UUID) -> List[Scenario]:
        """
        Get all scenarios for a tax return.

        Args:
            return_id: Return identifier.

        Returns:
            List of scenarios for the return.
        """
        query = text("""
            SELECT scenario_id, return_id, name, scenario_type, status,
                   is_recommended, scenario_data, created_at, updated_at
            FROM scenarios
            WHERE return_id = :return_id
            ORDER BY created_at DESC
        """)
        result = await self._session.execute(query, {"return_id": str(return_id)})
        return [self._row_to_scenario(row) for row in result.fetchall()]

    async def get_by_type(self, return_id: UUID, scenario_type: str) -> List[Scenario]:
        """
        Get scenarios of a specific type.

        Args:
            return_id: Return identifier.
            scenario_type: Type of scenario.

        Returns:
            List of matching scenarios.
        """
        query = text("""
            SELECT scenario_id, return_id, name, scenario_type, status,
                   is_recommended, scenario_data, created_at, updated_at
            FROM scenarios
            WHERE return_id = :return_id AND scenario_type = :scenario_type
            ORDER BY created_at DESC
        """)
        result = await self._session.execute(
            query,
            {"return_id": str(return_id), "scenario_type": scenario_type}
        )
        return [self._row_to_scenario(row) for row in result.fetchall()]

    async def get_recommended(self, return_id: UUID) -> Optional[Scenario]:
        """
        Get the recommended scenario for a return.

        Args:
            return_id: Return identifier.

        Returns:
            The recommended scenario if one is marked.
        """
        query = text("""
            SELECT scenario_id, return_id, name, scenario_type, status,
                   is_recommended, scenario_data, created_at, updated_at
            FROM scenarios
            WHERE return_id = :return_id AND is_recommended = true
            LIMIT 1
        """)
        result = await self._session.execute(query, {"return_id": str(return_id)})
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_scenario(row)

    async def delete_by_return(self, return_id: UUID) -> int:
        """
        Delete all scenarios for a return.

        Args:
            return_id: Return identifier.

        Returns:
            Number of scenarios deleted.
        """
        query = text("DELETE FROM scenarios WHERE return_id = :return_id")
        result = await self._session.execute(query, {"return_id": str(return_id)})

        deleted = result.rowcount
        logger.debug(f"Deleted {deleted} scenarios for return: {return_id}")
        return deleted

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
            return_id: Return identifier.
            scenario_ids: IDs of compared scenarios.
            winner_id: ID of winning scenario.
            comparison_data: Comparison details.

        Returns:
            Comparison ID.
        """
        comparison_id = uuid4()
        now = datetime.utcnow().isoformat()

        query = text("""
            INSERT INTO scenario_comparisons (
                comparison_id, return_id, scenario_ids, winner_id,
                comparison_data, created_at
            ) VALUES (
                :comparison_id, :return_id, :scenario_ids, :winner_id,
                :comparison_data, :created_at
            )
        """)

        params = {
            "comparison_id": str(comparison_id),
            "return_id": str(return_id),
            "scenario_ids": json.dumps([str(sid) for sid in scenario_ids]),
            "winner_id": str(winner_id) if winner_id else None,
            "comparison_data": json.dumps(comparison_data),
            "created_at": now,
        }

        await self._session.execute(query, params)
        logger.debug(f"Saved comparison: {comparison_id}")
        return comparison_id

    async def get_comparisons(self, return_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all scenario comparisons for a return.

        Args:
            return_id: Return identifier.

        Returns:
            List of comparisons.
        """
        query = text("""
            SELECT comparison_id, return_id, scenario_ids, winner_id,
                   comparison_data, created_at
            FROM scenario_comparisons
            WHERE return_id = :return_id
            ORDER BY created_at DESC
        """)
        result = await self._session.execute(query, {"return_id": str(return_id)})

        comparisons = []
        for row in result.fetchall():
            comparisons.append({
                "comparison_id": row[0],
                "return_id": row[1],
                "scenario_ids": json.loads(row[2]) if row[2] else [],
                "winner_id": row[3],
                "comparison_data": json.loads(row[4]) if row[4] else {},
                "created_at": row[5],
            })
        return comparisons

    def _row_to_scenario(self, row) -> Scenario:
        """Convert a database row to a Scenario object."""
        if row is None:
            return None

        # Parse the JSON scenario data
        scenario_data = json.loads(row[6]) if row[6] else {}

        # Create Scenario from the JSON data
        return Scenario.model_validate(scenario_data)
