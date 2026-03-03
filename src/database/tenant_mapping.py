"""Resolves tenant_id (string slug) <-> firm_id (UUID) bidirectionally."""

from typing import Optional
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


async def get_firm_id_for_tenant(db: AsyncSession, tenant_id: str) -> Optional[UUID]:
    """Convert a tenant slug to a firm UUID."""
    result = await db.execute(
        text("SELECT firm_id FROM tenant_firm_mapping WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    return row[0] if row else None


async def get_tenant_id_for_firm(db: AsyncSession, firm_id: UUID) -> Optional[str]:
    """Convert a firm UUID to a tenant slug."""
    result = await db.execute(
        text("SELECT tenant_id FROM tenant_firm_mapping WHERE firm_id = :fid"),
        {"fid": str(firm_id)},
    )
    row = result.fetchone()
    return row[0] if row else None


async def register_mapping(db: AsyncSession, tenant_id: str, firm_id: UUID) -> None:
    """Register or update a tenant_id <-> firm_id mapping."""
    await db.execute(
        text(
            "INSERT INTO tenant_firm_mapping (tenant_id, firm_id) "
            "VALUES (:tid, :fid) "
            "ON CONFLICT (tenant_id) DO UPDATE SET firm_id = :fid"
        ),
        {"tid": tenant_id, "fid": str(firm_id)},
    )
    await db.commit()
