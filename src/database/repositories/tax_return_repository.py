"""Async Tax Return Repository Implementation.

Implements ITaxReturnRepository using SQLAlchemy async sessions.
Provides CRUD operations for tax returns with proper transaction support.
"""

from __future__ import annotations

import json
import logging
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from domain.repositories import ITaxReturnRepository

logger = logging.getLogger(__name__)


class TaxReturnRepository(ITaxReturnRepository):
    """
    Async implementation of ITaxReturnRepository.

    Uses SQLAlchemy async sessions with the existing tax_returns table schema.
    Supports both the new ORM models and the legacy JSON serialization approach.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with a session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def get(self, return_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get a tax return by ID.

        Args:
            return_id: Tax return identifier.

        Returns:
            Tax return data dict or None if not found.
        """
        query = """
            SELECT return_id, session_id, taxpayer_name, tax_year, filing_status,
                   state_code, gross_income, adjusted_gross_income, taxable_income,
                   federal_tax_liability, state_tax_liability, combined_tax_liability,
                   federal_refund_or_owed, state_refund_or_owed, combined_refund_or_owed,
                   status, return_data, created_at, updated_at
            FROM tax_returns WHERE return_id = :return_id
        """
        from sqlalchemy import text
        result = await self._session.execute(
            text(query),
            {"return_id": str(return_id)}
        )
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    async def save(self, return_id: UUID, tax_return_data: Dict[str, Any]) -> None:
        """
        Save a tax return (upsert).

        SECURITY (SPEC-003): SSN is never stored in plaintext.
        - SSN hash is stored for lookups
        - SSN is masked in return_data JSON (***-**-XXXX)
        - Actual SSN should be encrypted separately if needed

        Args:
            return_id: Tax return identifier.
            tax_return_data: Full tax return data dict.
        """
        import copy
        from sqlalchemy import text

        # Create a deep copy to avoid modifying the original
        sanitized_data = copy.deepcopy(tax_return_data)

        # Extract metadata from the tax return data
        taxpayer = tax_return_data.get("taxpayer", {})
        income = tax_return_data.get("income", {})
        calculation = tax_return_data.get("calculation_result", {})

        # Build taxpayer name
        first_name = taxpayer.get("first_name", "")
        last_name = taxpayer.get("last_name", "")
        taxpayer_name = f"{first_name} {last_name}".strip() or "Unknown"

        # Hash SSN for lookups (SPEC-003)
        ssn = taxpayer.get("ssn", "")
        ssn_hash = hashlib.sha256(ssn.encode()).hexdigest() if ssn else None

        # SECURITY (SPEC-003): Sanitize SSN from stored JSON data
        # Replace plaintext SSN with masked version to prevent PII exposure
        if "taxpayer" in sanitized_data and "ssn" in sanitized_data["taxpayer"]:
            raw_ssn = sanitized_data["taxpayer"]["ssn"]
            if raw_ssn:
                # Mask SSN: keep last 4 digits only
                digits = ''.join(c for c in str(raw_ssn) if c.isdigit())
                if len(digits) >= 4:
                    sanitized_data["taxpayer"]["ssn"] = f"***-**-{digits[-4:]}"
                else:
                    sanitized_data["taxpayer"]["ssn"] = "***-**-****"
            logger.debug(f"[SECURITY] SSN sanitized for return {return_id}")

        # Also sanitize spouse_ssn if present
        if "taxpayer" in sanitized_data and "spouse_ssn" in sanitized_data["taxpayer"]:
            raw_spouse_ssn = sanitized_data["taxpayer"]["spouse_ssn"]
            if raw_spouse_ssn:
                digits = ''.join(c for c in str(raw_spouse_ssn) if c.isdigit())
                if len(digits) >= 4:
                    sanitized_data["taxpayer"]["spouse_ssn"] = f"***-**-{digits[-4:]}"
                else:
                    sanitized_data["taxpayer"]["spouse_ssn"] = "***-**-****"

        # Extract financial values
        gross_income = income.get("total_income", 0) or 0
        agi = calculation.get("agi", 0) or income.get("adjusted_gross_income", 0) or 0
        taxable_income = calculation.get("taxable_income", 0) or 0
        federal_tax = calculation.get("total_tax", 0) or 0
        state_tax = calculation.get("state_tax", 0) or 0
        combined_tax = federal_tax + state_tax
        federal_refund = calculation.get("refund_or_owed", 0) or 0
        state_refund = calculation.get("state_refund_or_owed", 0) or 0
        combined_refund = federal_refund + state_refund

        now = datetime.utcnow().isoformat()

        # Check if exists
        exists = await self.exists(return_id)

        if exists:
            # Update
            query = text("""
                UPDATE tax_returns SET
                    taxpayer_ssn_hash = :ssn_hash,
                    taxpayer_name = :taxpayer_name,
                    tax_year = :tax_year,
                    filing_status = :filing_status,
                    state_code = :state_code,
                    gross_income = :gross_income,
                    adjusted_gross_income = :agi,
                    taxable_income = :taxable_income,
                    federal_tax_liability = :federal_tax,
                    state_tax_liability = :state_tax,
                    combined_tax_liability = :combined_tax,
                    federal_refund_or_owed = :federal_refund,
                    state_refund_or_owed = :state_refund,
                    combined_refund_or_owed = :combined_refund,
                    status = :status,
                    return_data = :return_data,
                    updated_at = :updated_at
                WHERE return_id = :return_id
            """)
        else:
            # Insert
            query = text("""
                INSERT INTO tax_returns (
                    return_id, session_id, taxpayer_ssn_hash, taxpayer_name,
                    tax_year, filing_status, state_code, gross_income,
                    adjusted_gross_income, taxable_income, federal_tax_liability,
                    state_tax_liability, combined_tax_liability,
                    federal_refund_or_owed, state_refund_or_owed, combined_refund_or_owed,
                    status, return_data, created_at, updated_at
                ) VALUES (
                    :return_id, :session_id, :ssn_hash, :taxpayer_name,
                    :tax_year, :filing_status, :state_code, :gross_income,
                    :agi, :taxable_income, :federal_tax,
                    :state_tax, :combined_tax,
                    :federal_refund, :state_refund, :combined_refund,
                    :status, :return_data, :created_at, :updated_at
                )
            """)

        params = {
            "return_id": str(return_id),
            "session_id": tax_return_data.get("session_id", str(return_id)),
            "ssn_hash": ssn_hash,
            "taxpayer_name": taxpayer_name,
            "tax_year": tax_return_data.get("tax_year", 2025),
            "filing_status": taxpayer.get("filing_status", "single"),
            "state_code": taxpayer.get("state_of_residence"),
            "gross_income": gross_income,
            "agi": agi,
            "taxable_income": taxable_income,
            "federal_tax": federal_tax,
            "state_tax": state_tax,
            "combined_tax": combined_tax,
            "federal_refund": federal_refund,
            "state_refund": state_refund,
            "combined_refund": combined_refund,
            "status": tax_return_data.get("status", "draft"),
            "return_data": json.dumps(sanitized_data),  # SPEC-003: Use sanitized data
            "created_at": now,
            "updated_at": now,
        }

        await self._session.execute(query, params)
        logger.debug(f"Saved tax return: {return_id}")

    async def delete(self, return_id: UUID) -> bool:
        """
        Delete a tax return.

        Args:
            return_id: Tax return identifier.

        Returns:
            True if deleted, False if not found.
        """
        from sqlalchemy import text

        query = text("DELETE FROM tax_returns WHERE return_id = :return_id")
        result = await self._session.execute(query, {"return_id": str(return_id)})

        deleted = result.rowcount > 0
        if deleted:
            logger.debug(f"Deleted tax return: {return_id}")
        return deleted

    async def exists(self, return_id: UUID) -> bool:
        """Check if a tax return exists."""
        from sqlalchemy import text

        query = text("SELECT 1 FROM tax_returns WHERE return_id = :return_id LIMIT 1")
        result = await self._session.execute(query, {"return_id": str(return_id)})
        return result.fetchone() is not None

    async def get_by_client(self, client_id: UUID) -> List[Dict[str, Any]]:
        """Get all tax returns for a client (by SSN hash)."""
        from sqlalchemy import text

        # Client ID in this context is the SSN hash
        query = text("""
            SELECT return_id, session_id, taxpayer_name, tax_year, filing_status,
                   state_code, gross_income, adjusted_gross_income, taxable_income,
                   federal_tax_liability, state_tax_liability, combined_tax_liability,
                   federal_refund_or_owed, state_refund_or_owed, combined_refund_or_owed,
                   status, return_data, created_at, updated_at
            FROM tax_returns
            WHERE taxpayer_ssn_hash = :client_id
            ORDER BY tax_year DESC
        """)
        result = await self._session.execute(query, {"client_id": str(client_id)})
        return [self._row_to_dict(row) for row in result.fetchall()]

    async def get_by_year(
        self, client_id: UUID, tax_year: int
    ) -> Optional[Dict[str, Any]]:
        """Get a tax return for a specific year."""
        from sqlalchemy import text

        query = text("""
            SELECT return_id, session_id, taxpayer_name, tax_year, filing_status,
                   state_code, gross_income, adjusted_gross_income, taxable_income,
                   federal_tax_liability, state_tax_liability, combined_tax_liability,
                   federal_refund_or_owed, state_refund_or_owed, combined_refund_or_owed,
                   status, return_data, created_at, updated_at
            FROM tax_returns
            WHERE taxpayer_ssn_hash = :client_id AND tax_year = :tax_year
            LIMIT 1
        """)
        result = await self._session.execute(
            query,
            {"client_id": str(client_id), "tax_year": tax_year}
        )
        row = result.fetchone()
        return self._row_to_dict(row) if row else None

    async def get_prior_year(self, return_id: UUID) -> Optional[Dict[str, Any]]:
        """Get the prior year tax return."""
        from sqlalchemy import text

        # First get the current return to find the taxpayer and year
        current = await self.get(return_id)
        if not current:
            return None

        tax_year = current.get("tax_year", 2025)
        prior_year = tax_year - 1

        # Look up by session_id pattern or taxpayer_ssn_hash
        ssn_hash = current.get("taxpayer_ssn_hash")
        if ssn_hash:
            return await self.get_by_year(UUID(ssn_hash), prior_year)

        return None

    async def list_returns(
        self,
        tax_year: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List tax returns with optional filters."""
        from sqlalchemy import text

        conditions = []
        params = {"limit": limit, "offset": offset}

        if tax_year is not None:
            conditions.append("tax_year = :tax_year")
            params["tax_year"] = tax_year

        if status is not None:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = text(f"""
            SELECT return_id, session_id, taxpayer_name, tax_year, filing_status,
                   state_code, gross_income, adjusted_gross_income, taxable_income,
                   federal_tax_liability, state_tax_liability, combined_tax_liability,
                   federal_refund_or_owed, state_refund_or_owed, combined_refund_or_owed,
                   status, return_data, created_at, updated_at
            FROM tax_returns
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
        """)

        result = await self._session.execute(query, params)
        return [self._row_to_dict(row) for row in result.fetchall()]

    async def get_calculation_result(
        self, return_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get the calculation result for a return."""
        tax_return = await self.get(return_id)
        if tax_return:
            return tax_return.get("calculation_result")
        return None

    async def get_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a tax return by session ID.

        Args:
            session_id: Session identifier.

        Returns:
            Tax return data or None.
        """
        from sqlalchemy import text

        query = text("""
            SELECT return_id, session_id, taxpayer_name, tax_year, filing_status,
                   state_code, gross_income, adjusted_gross_income, taxable_income,
                   federal_tax_liability, state_tax_liability, combined_tax_liability,
                   federal_refund_or_owed, state_refund_or_owed, combined_refund_or_owed,
                   status, return_data, created_at, updated_at
            FROM tax_returns
            WHERE session_id = :session_id
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        result = await self._session.execute(query, {"session_id": session_id})
        row = result.fetchone()
        return self._row_to_dict(row) if row else None

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a database row to a tax return dict."""
        if row is None:
            return None

        # Parse the JSON return_data
        return_data = json.loads(row[16]) if row[16] else {}

        # Add metadata
        return_data["return_id"] = row[0]
        return_data["session_id"] = row[1]
        return_data["taxpayer_name"] = row[2]
        return_data["tax_year"] = row[3]
        return_data["taxpayer_ssn_hash"] = row[1]  # Using session_id position
        return_data["status"] = row[15]
        return_data["created_at"] = row[17]
        return_data["updated_at"] = row[18]

        # Add summary values
        return_data["summary"] = {
            "gross_income": row[6],
            "adjusted_gross_income": row[7],
            "taxable_income": row[8],
            "federal_tax_liability": row[9],
            "state_tax_liability": row[10],
            "combined_tax_liability": row[11],
            "federal_refund_or_owed": row[12],
            "state_refund_or_owed": row[13],
            "combined_refund_or_owed": row[14],
        }

        return return_data
