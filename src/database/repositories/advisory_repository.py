"""Async Advisory Repository Implementation.

Implements IAdvisoryRepository using SQLAlchemy async sessions.
Provides CRUD operations for advisory plans with proper transaction support.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.repositories import IAdvisoryRepository
from domain.aggregates import AdvisoryPlan, RecommendationStatus

logger = logging.getLogger(__name__)


class AdvisoryRepository(IAdvisoryRepository):
    """
    Async implementation of IAdvisoryRepository.

    Uses SQLAlchemy async sessions with JSONB storage for advisory plans.
    Plans are stored as serialized JSON with indexed metadata columns.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with a session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def get(self, id: UUID) -> Optional[AdvisoryPlan]:
        """
        Get an advisory plan by ID.

        Args:
            id: Plan identifier.

        Returns:
            AdvisoryPlan object or None if not found.
        """
        query = text("""
            SELECT plan_id, client_id, return_id, tax_year, is_finalized,
                   total_potential_savings, total_realized_savings,
                   plan_data, created_at, updated_at
            FROM advisory_plans WHERE plan_id = :plan_id
        """)
        result = await self._session.execute(query, {"plan_id": str(id)})
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_plan(row)

    async def save(self, entity: AdvisoryPlan) -> None:
        """
        Save an advisory plan (upsert).

        Args:
            entity: AdvisoryPlan to save.
        """
        exists = await self.exists(entity.plan_id)
        now = datetime.utcnow().isoformat()

        # Serialize the plan to JSON
        plan_data = entity.model_dump_json()

        if exists:
            query = text("""
                UPDATE advisory_plans SET
                    client_id = :client_id,
                    return_id = :return_id,
                    tax_year = :tax_year,
                    is_finalized = :is_finalized,
                    total_potential_savings = :total_potential_savings,
                    total_realized_savings = :total_realized_savings,
                    plan_data = :plan_data,
                    updated_at = :updated_at
                WHERE plan_id = :plan_id
            """)
        else:
            query = text("""
                INSERT INTO advisory_plans (
                    plan_id, client_id, return_id, tax_year, is_finalized,
                    total_potential_savings, total_realized_savings,
                    plan_data, created_at, updated_at
                ) VALUES (
                    :plan_id, :client_id, :return_id, :tax_year, :is_finalized,
                    :total_potential_savings, :total_realized_savings,
                    :plan_data, :created_at, :updated_at
                )
            """)

        params = {
            "plan_id": str(entity.plan_id),
            "client_id": str(entity.client_id),
            "return_id": str(entity.return_id),
            "tax_year": entity.tax_year,
            "is_finalized": entity.is_finalized,
            "total_potential_savings": entity.total_potential_savings,
            "total_realized_savings": entity.total_realized_savings,
            "plan_data": plan_data,
            "created_at": now,
            "updated_at": now,
        }

        await self._session.execute(query, params)
        logger.debug(f"Saved advisory plan: {entity.plan_id}")

    async def delete(self, id: UUID) -> bool:
        """
        Delete an advisory plan.

        Args:
            id: Plan identifier.

        Returns:
            True if deleted, False if not found.
        """
        query = text("DELETE FROM advisory_plans WHERE plan_id = :plan_id")
        result = await self._session.execute(query, {"plan_id": str(id)})

        deleted = result.rowcount > 0
        if deleted:
            logger.debug(f"Deleted advisory plan: {id}")
        return deleted

    async def exists(self, id: UUID) -> bool:
        """Check if an advisory plan exists."""
        query = text("SELECT 1 FROM advisory_plans WHERE plan_id = :plan_id LIMIT 1")
        result = await self._session.execute(query, {"plan_id": str(id)})
        return result.fetchone() is not None

    async def get_by_client(self, client_id: UUID) -> List[AdvisoryPlan]:
        """
        Get all advisory plans for a client.

        Args:
            client_id: Client identifier.

        Returns:
            List of advisory plans.
        """
        query = text("""
            SELECT plan_id, client_id, return_id, tax_year, is_finalized,
                   total_potential_savings, total_realized_savings,
                   plan_data, created_at, updated_at
            FROM advisory_plans
            WHERE client_id = :client_id
            ORDER BY tax_year DESC
        """)
        result = await self._session.execute(query, {"client_id": str(client_id)})
        return [self._row_to_plan(row) for row in result.fetchall()]

    async def get_by_return(self, return_id: UUID) -> Optional[AdvisoryPlan]:
        """
        Get the advisory plan for a specific return.

        Args:
            return_id: Return identifier.

        Returns:
            Advisory plan if found.
        """
        query = text("""
            SELECT plan_id, client_id, return_id, tax_year, is_finalized,
                   total_potential_savings, total_realized_savings,
                   plan_data, created_at, updated_at
            FROM advisory_plans
            WHERE return_id = :return_id
            LIMIT 1
        """)
        result = await self._session.execute(query, {"return_id": str(return_id)})
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_plan(row)

    async def get_by_year(self, client_id: UUID, tax_year: int) -> Optional[AdvisoryPlan]:
        """
        Get the advisory plan for a specific year.

        Args:
            client_id: Client identifier.
            tax_year: Tax year.

        Returns:
            Advisory plan if found.
        """
        query = text("""
            SELECT plan_id, client_id, return_id, tax_year, is_finalized,
                   total_potential_savings, total_realized_savings,
                   plan_data, created_at, updated_at
            FROM advisory_plans
            WHERE client_id = :client_id AND tax_year = :tax_year
            LIMIT 1
        """)
        result = await self._session.execute(
            query,
            {"client_id": str(client_id), "tax_year": tax_year}
        )
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_plan(row)

    async def save_recommendation(
        self,
        plan_id: UUID,
        recommendation: Dict[str, Any]
    ) -> UUID:
        """
        Save or update a recommendation.

        Args:
            plan_id: Plan identifier.
            recommendation: Recommendation data.

        Returns:
            Recommendation ID.
        """
        # Get the existing plan
        plan = await self.get(plan_id)
        if plan is None:
            raise ValueError(f"Advisory plan not found: {plan_id}")

        # Find or create recommendation ID
        rec_id = recommendation.get("recommendation_id") or str(uuid4())
        recommendation["recommendation_id"] = rec_id

        # Find existing recommendation to update
        found = False
        for i, rec in enumerate(plan.recommendations):
            if str(rec.recommendation_id) == str(rec_id):
                # Update existing - need to convert dict to Recommendation
                from domain.aggregates import Recommendation
                plan.recommendations[i] = Recommendation.model_validate(recommendation)
                found = True
                break

        if not found:
            # Add new recommendation
            from domain.aggregates import Recommendation
            plan.add_recommendation(Recommendation.model_validate(recommendation))

        # Save the updated plan
        await self.save(plan)
        logger.debug(f"Saved recommendation {rec_id} to plan {plan_id}")

        return UUID(rec_id) if isinstance(rec_id, str) else rec_id

    async def get_recommendations_by_status(
        self,
        plan_id: UUID,
        status: str
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations by status.

        Args:
            plan_id: Plan identifier.
            status: Status to filter by.

        Returns:
            List of matching recommendations.
        """
        plan = await self.get(plan_id)
        if plan is None:
            return []

        return [
            rec.model_dump() for rec in plan.recommendations
            if rec.status.value == status
        ]

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
            recommendation_id: Recommendation identifier.
            status: New status.
            changed_by: Who made the change.
            reason: Reason for change (especially for declined).

        Returns:
            True if updated, False if not found.
        """
        # Find the plan containing this recommendation
        query = text("""
            SELECT plan_id, plan_data FROM advisory_plans
            WHERE plan_data::text LIKE :rec_id_pattern
        """)
        result = await self._session.execute(
            query,
            {"rec_id_pattern": f"%{str(recommendation_id)}%"}
        )
        row = result.fetchone()

        if row is None:
            return False

        plan = await self.get(UUID(row[0]))
        if plan is None:
            return False

        # Find and update the recommendation
        for rec in plan.recommendations:
            if rec.recommendation_id == recommendation_id:
                rec.update_status(
                    RecommendationStatus(status),
                    changed_by,
                    reason
                )
                await self.save(plan)
                logger.debug(f"Updated recommendation {recommendation_id} status to {status}")
                return True

        return False

    def _row_to_plan(self, row) -> AdvisoryPlan:
        """Convert a database row to an AdvisoryPlan object."""
        if row is None:
            return None

        # Parse the JSON plan data
        plan_data = json.loads(row[7]) if row[7] else {}

        # Create AdvisoryPlan from the JSON data
        return AdvisoryPlan.model_validate(plan_data)
