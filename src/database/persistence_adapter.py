"""
PostgreSQL-backed persistence adapter for tax returns.

Drop-in replacement for database.persistence tax return functions,
backed by the async TaxReturnRepository and PostgreSQL.

Falls back to SQLite (database.persistence) when DATABASE_URL is not
configured for PostgreSQL, preserving dev-environment compatibility.
"""

import logging
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def _use_postgres() -> bool:
    """Check if we should use the PostgreSQL backend."""
    db_url = os.environ.get("DATABASE_URL", "")
    return "postgresql" in db_url or "postgres" in db_url


if _use_postgres():
    import asyncio
    from database.async_engine import get_async_session
    from database.repositories.tax_return_repository import TaxReturnRepository

    # Re-export SavedReturn from the original module for compatibility
    from database.persistence import SavedReturn

    class TaxReturnPersistence:
        """
        PostgreSQL-backed persistence that mirrors the SQLite API.

        All methods are synchronous wrappers around the async repository,
        matching the interface of database.persistence.TaxReturnPersistence.
        """

        def _run(self, coro):
            """Run an async coroutine synchronously."""
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're inside an async context (e.g. FastAPI handler).
                # Create a new task — callers must await if needed.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, coro).result()
            else:
                return asyncio.run(coro)

        async def _save(self, session_id, tax_return_data, return_id=None):
            import uuid
            rid = return_id or str(uuid.uuid4())
            tax_return_data["session_id"] = session_id
            async with get_async_session() as session:
                repo = TaxReturnRepository(session)
                await repo.save(rid, tax_return_data)
            return rid

        async def _load(self, return_id):
            async with get_async_session() as session:
                repo = TaxReturnRepository(session)
                return await repo.get(return_id)

        async def _load_by_session(self, session_id):
            async with get_async_session() as session:
                repo = TaxReturnRepository(session)
                data = await repo.get_by_session(session_id)
                if data:
                    data["_return_id"] = data.get("return_id")
                return data

        async def _list_returns(self, tax_year=None, status=None, limit=50, offset=0):
            async with get_async_session() as session:
                repo = TaxReturnRepository(session)
                rows = await repo.list_returns(
                    tax_year=tax_year, status=status, limit=limit, offset=offset
                )
                result = []
                for r in rows:
                    result.append(SavedReturn(
                        return_id=r.get("return_id", ""),
                        session_id=r.get("session_id", ""),
                        taxpayer_name=r.get("taxpayer_name", ""),
                        tax_year=r.get("tax_year", 2025),
                        filing_status=r.get("filing_status", ""),
                        state_code=r.get("state_code"),
                        gross_income=r.get("summary", {}).get("gross_income", 0) or 0,
                        tax_liability=r.get("summary", {}).get("combined_tax_liability", 0) or 0,
                        refund_or_owed=r.get("summary", {}).get("combined_refund_or_owed", 0) or 0,
                        status=r.get("status", "draft"),
                        created_at=r.get("created_at", ""),
                        updated_at=r.get("updated_at", ""),
                    ))
                return result

        async def _delete(self, return_id):
            async with get_async_session() as session:
                repo = TaxReturnRepository(session)
                return await repo.delete(return_id)

        async def _get_metadata(self, return_id):
            async with get_async_session() as session:
                repo = TaxReturnRepository(session)
                r = await repo.get(return_id)
                if not r:
                    return None
                return SavedReturn(
                    return_id=r.get("return_id", ""),
                    session_id=r.get("session_id", ""),
                    taxpayer_name=r.get("taxpayer_name", ""),
                    tax_year=r.get("tax_year", 2025),
                    filing_status=r.get("filing_status", ""),
                    state_code=r.get("state_code"),
                    gross_income=r.get("summary", {}).get("gross_income", 0) or 0,
                    tax_liability=r.get("summary", {}).get("combined_tax_liability", 0) or 0,
                    refund_or_owed=r.get("summary", {}).get("combined_refund_or_owed", 0) or 0,
                    status=r.get("status", "draft"),
                    created_at=r.get("created_at", ""),
                    updated_at=r.get("updated_at", ""),
                )

        def save_return(self, session_id, tax_return_data, return_id=None):
            return self._run(self._save(session_id, tax_return_data, return_id))

        def load_return(self, return_id):
            return self._run(self._load(return_id))

        def load_by_session(self, session_id):
            return self._run(self._load_by_session(session_id))

        def list_returns(self, tax_year=None, status=None, limit=50, offset=0):
            return self._run(self._list_returns(tax_year, status, limit, offset))

        def delete_return(self, return_id):
            return self._run(self._delete(return_id))

        def get_return_metadata(self, return_id):
            return self._run(self._get_metadata(return_id))

    # Global instance
    _persistence: Optional[TaxReturnPersistence] = None

    def get_persistence() -> TaxReturnPersistence:
        global _persistence
        if _persistence is None:
            _persistence = TaxReturnPersistence()
        return _persistence

    def save_tax_return(session_id: str, tax_return_data: Dict[str, Any], return_id: Optional[str] = None) -> str:
        return get_persistence().save_return(session_id, tax_return_data, return_id)

    def load_tax_return(return_id: str) -> Optional[Dict[str, Any]]:
        return get_persistence().load_return(return_id)

    def load_session_return(session_id: str) -> Optional[Dict[str, Any]]:
        return get_persistence().load_by_session(session_id)

    def list_tax_returns(tax_year: Optional[int] = None, limit: int = 50) -> list:
        return get_persistence().list_returns(tax_year, limit=limit)

else:
    # Fallback: use SQLite persistence directly
    from database.persistence import (  # noqa: F401
        TaxReturnPersistence,
        SavedReturn,
        get_persistence,
        save_tax_return,
        load_tax_return,
        load_session_return,
        list_tax_returns,
    )
