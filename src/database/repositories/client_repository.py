"""Async Client Repository Implementation.

Implements IClientRepository using SQLAlchemy async sessions.
Provides CRUD operations for client profiles with proper transaction support.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.repositories import IClientRepository
from domain.aggregates import ClientProfile
from domain.value_objects import PriorYearCarryovers

logger = logging.getLogger(__name__)


class ClientRepository(IClientRepository):
    """
    Async implementation of IClientRepository.

    Uses SQLAlchemy async sessions with the existing clients table.
    Extends the base client record with profile data stored as JSONB.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with a session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def get(self, id: UUID) -> Optional[ClientProfile]:
        """
        Get a client profile by ID.

        Args:
            id: Client identifier.

        Returns:
            ClientProfile object or None if not found.
        """
        query = text("""
            SELECT client_id, preparer_id, external_id, ssn_hash,
                   first_name, last_name, email, phone,
                   street_address, city, state, zip_code,
                   is_active, profile_data, created_at, updated_at
            FROM clients WHERE client_id = :client_id
        """)
        result = await self._session.execute(query, {"client_id": str(id)})
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_profile(row)

    async def save(self, entity: ClientProfile) -> None:
        """
        Save a client profile (upsert).

        Args:
            entity: ClientProfile to save.
        """
        exists = await self.exists(entity.client_id)
        now = datetime.utcnow().isoformat()

        # Serialize the profile data to JSON (preferences, carryovers, etc.)
        profile_data = entity.model_dump_json()

        if exists:
            query = text("""
                UPDATE clients SET
                    external_id = :external_id,
                    ssn_hash = :ssn_hash,
                    first_name = :first_name,
                    last_name = :last_name,
                    email = :email,
                    phone = :phone,
                    street_address = :street_address,
                    city = :city,
                    state = :state,
                    zip_code = :zip_code,
                    is_active = :is_active,
                    profile_data = :profile_data,
                    updated_at = :updated_at
                WHERE client_id = :client_id
            """)
        else:
            query = text("""
                INSERT INTO clients (
                    client_id, preparer_id, external_id, ssn_hash,
                    first_name, last_name, email, phone,
                    street_address, city, state, zip_code,
                    is_active, profile_data, created_at, updated_at
                ) VALUES (
                    :client_id, :preparer_id, :external_id, :ssn_hash,
                    :first_name, :last_name, :email, :phone,
                    :street_address, :city, :state, :zip_code,
                    :is_active, :profile_data, :created_at, :updated_at
                )
            """)

        # Note: preparer_id would need to be provided in the entity or via context
        params = {
            "client_id": str(entity.client_id),
            "preparer_id": None,  # Would be set from context in real usage
            "external_id": entity.external_id,
            "ssn_hash": entity.ssn_hash,
            "first_name": entity.first_name,
            "last_name": entity.last_name,
            "email": entity.email,
            "phone": entity.phone,
            "street_address": entity.street_address,
            "city": entity.city,
            "state": entity.state,
            "zip_code": entity.zip_code,
            "is_active": entity.is_active,
            "profile_data": profile_data,
            "created_at": now,
            "updated_at": now,
        }

        await self._session.execute(query, params)
        logger.debug(f"Saved client profile: {entity.client_id}")

    async def delete(self, id: UUID) -> bool:
        """
        Delete a client profile.

        Args:
            id: Client identifier.

        Returns:
            True if deleted, False if not found.
        """
        query = text("DELETE FROM clients WHERE client_id = :client_id")
        result = await self._session.execute(query, {"client_id": str(id)})

        deleted = result.rowcount > 0
        if deleted:
            logger.debug(f"Deleted client: {id}")
        return deleted

    async def exists(self, id: UUID) -> bool:
        """Check if a client exists."""
        query = text("SELECT 1 FROM clients WHERE client_id = :client_id LIMIT 1")
        result = await self._session.execute(query, {"client_id": str(id)})
        return result.fetchone() is not None

    async def get_by_external_id(self, external_id: str) -> Optional[ClientProfile]:
        """
        Get a client by their external ID.

        Args:
            external_id: CPA's client number.

        Returns:
            Client profile if found.
        """
        query = text("""
            SELECT client_id, preparer_id, external_id, ssn_hash,
                   first_name, last_name, email, phone,
                   street_address, city, state, zip_code,
                   is_active, profile_data, created_at, updated_at
            FROM clients WHERE external_id = :external_id
            LIMIT 1
        """)
        result = await self._session.execute(query, {"external_id": external_id})
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_profile(row)

    async def get_by_ssn_hash(self, ssn_hash: str) -> Optional[ClientProfile]:
        """
        Get a client by their SSN hash.

        Args:
            ssn_hash: Hashed SSN.

        Returns:
            Client profile if found.
        """
        query = text("""
            SELECT client_id, preparer_id, external_id, ssn_hash,
                   first_name, last_name, email, phone,
                   street_address, city, state, zip_code,
                   is_active, profile_data, created_at, updated_at
            FROM clients WHERE ssn_hash = :ssn_hash
            LIMIT 1
        """)
        result = await self._session.execute(query, {"ssn_hash": ssn_hash})
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_profile(row)

    async def search(
        self,
        query: str,
        limit: int = 20
    ) -> List[ClientProfile]:
        """
        Search clients by name or external ID.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            Matching clients.
        """
        search_pattern = f"%{query}%"
        sql = text("""
            SELECT client_id, preparer_id, external_id, ssn_hash,
                   first_name, last_name, email, phone,
                   street_address, city, state, zip_code,
                   is_active, profile_data, created_at, updated_at
            FROM clients
            WHERE (
                first_name ILIKE :pattern
                OR last_name ILIKE :pattern
                OR external_id ILIKE :pattern
                OR email ILIKE :pattern
            )
            AND is_active = true
            ORDER BY last_name, first_name
            LIMIT :limit
        """)
        result = await self._session.execute(
            sql,
            {"pattern": search_pattern, "limit": limit}
        )
        return [self._row_to_profile(row) for row in result.fetchall()]

    async def get_active_clients(self, limit: int = 100) -> List[ClientProfile]:
        """
        Get active clients.

        Args:
            limit: Maximum results.

        Returns:
            List of active clients.
        """
        query = text("""
            SELECT client_id, preparer_id, external_id, ssn_hash,
                   first_name, last_name, email, phone,
                   street_address, city, state, zip_code,
                   is_active, profile_data, created_at, updated_at
            FROM clients
            WHERE is_active = true
            ORDER BY last_name, first_name
            LIMIT :limit
        """)
        result = await self._session.execute(query, {"limit": limit})
        return [self._row_to_profile(row) for row in result.fetchall()]

    async def update_carryovers(
        self,
        client_id: UUID,
        carryovers: PriorYearCarryovers
    ) -> bool:
        """
        Update client carryover balances.

        Args:
            client_id: Client identifier.
            carryovers: New carryover balances.

        Returns:
            True if updated.
        """
        profile = await self.get(client_id)
        if profile is None:
            return False

        profile.update_carryovers(carryovers)
        await self.save(profile)
        logger.debug(f"Updated carryovers for client: {client_id}")
        return True

    def _row_to_profile(self, row) -> ClientProfile:
        """Convert a database row to a ClientProfile object."""
        if row is None:
            return None

        # If profile_data exists, use it to create the full profile
        profile_data = json.loads(row[13]) if row[13] else {}

        if profile_data:
            # Use the stored profile data
            return ClientProfile.model_validate(profile_data)

        # Fall back to building from columns
        return ClientProfile(
            client_id=UUID(row[0]) if row[0] else uuid4(),
            external_id=row[2],
            ssn_hash=row[3],
            first_name=row[4] or "",
            last_name=row[5] or "",
            email=row[6],
            phone=row[7],
            street_address=row[8],
            city=row[9],
            state=row[10],
            zip_code=row[11],
            is_active=row[12] if row[12] is not None else True,
        )
