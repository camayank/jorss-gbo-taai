"""
Partner Service - Partner organization management.

Provides:
- Partner CRUD operations
- Partner-firm relationship management
- Partner admin management
- Cross-firm aggregation for partner reporting
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import hashlib
import secrets
import logging

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session, selectinload

from core.rbac.models import Partner, PartnerFirm, PartnerAdmin

logger = logging.getLogger(__name__)


# =============================================================================
# RESULT TYPES
# =============================================================================

@dataclass
class PartnerCreateResult:
    """Result of partner creation."""
    success: bool
    message: str
    partner_id: Optional[UUID] = None
    api_key: Optional[str] = None  # Only returned on creation
    errors: List[str] = field(default_factory=list)


@dataclass
class FirmAssignResult:
    """Result of firm assignment to partner."""
    success: bool
    message: str
    errors: List[str] = field(default_factory=list)


@dataclass
class PartnerAdminCreateResult:
    """Result of partner admin creation."""
    success: bool
    message: str
    admin_id: Optional[UUID] = None
    errors: List[str] = field(default_factory=list)


# =============================================================================
# PARTNER SERVICE
# =============================================================================

class PartnerService:
    """
    Partner management service.

    Handles:
    - Partner organization CRUD
    - Partner-firm relationships
    - Partner admin management
    - API key generation
    """

    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------------------
    # Partner CRUD
    # -------------------------------------------------------------------------

    async def get_partner_by_id(self, partner_id: UUID) -> Optional[Partner]:
        """Get partner by ID."""
        stmt = (
            select(Partner)
            .options(
                selectinload(Partner.partner_firms),
                selectinload(Partner.partner_admins),
            )
            .where(Partner.partner_id == partner_id)
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_partner_by_code(self, code: str) -> Optional[Partner]:
        """Get partner by code."""
        stmt = select(Partner).where(Partner.code == code)
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_partner_by_domain(self, domain: str) -> Optional[Partner]:
        """Get partner by custom domain."""
        stmt = select(Partner).where(Partner.custom_domain == domain)
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_partners(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Partner]:
        """List all partners."""
        conditions = []
        if active_only:
            conditions.append(Partner.is_active == True)

        stmt = select(Partner)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Partner.name).limit(limit).offset(offset)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_partner(
        self,
        code: str,
        name: str,
        created_by: UUID,
        legal_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        custom_domain: Optional[str] = None,
        api_enabled: bool = False,
    ) -> PartnerCreateResult:
        """
        Create a new partner organization.

        If api_enabled is True, generates an API key.
        """
        # Validate code uniqueness
        existing = await self.get_partner_by_code(code)
        if existing:
            return PartnerCreateResult(
                success=False,
                message=f"Partner code '{code}' already exists",
                errors=["Choose a different partner code"],
            )

        # Validate domain uniqueness if provided
        if custom_domain:
            existing_domain = await self.get_partner_by_domain(custom_domain)
            if existing_domain:
                return PartnerCreateResult(
                    success=False,
                    message=f"Custom domain '{custom_domain}' already in use",
                    errors=["Choose a different domain"],
                )

        # Generate API key if enabled
        api_key = None
        api_key_hash = None
        if api_enabled:
            api_key = secrets.token_urlsafe(32)
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Create partner
        partner = Partner(
            code=code,
            name=name,
            legal_name=legal_name,
            email=email,
            phone=phone,
            website=website,
            custom_domain=custom_domain,
            api_enabled=api_enabled,
            api_key_hash=api_key_hash,
            is_active=True,
            created_by=created_by,
        )
        self.db.add(partner)
        self.db.commit()

        logger.info(f"Created partner: {code} (ID: {partner.partner_id})")

        return PartnerCreateResult(
            success=True,
            message=f"Partner '{name}' created successfully",
            partner_id=partner.partner_id,
            api_key=api_key,  # Only returned once, not stored in plain text
        )

    async def update_partner(
        self,
        partner_id: UUID,
        updated_by: UUID,
        name: Optional[str] = None,
        legal_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        website: Optional[str] = None,
        logo_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        custom_domain: Optional[str] = None,
        login_page_url: Optional[str] = None,
    ) -> PartnerCreateResult:
        """Update partner details."""
        partner = await self.get_partner_by_id(partner_id)
        if not partner:
            return PartnerCreateResult(
                success=False,
                message="Partner not found",
            )

        # Update fields if provided
        if name is not None:
            partner.name = name
        if legal_name is not None:
            partner.legal_name = legal_name
        if email is not None:
            partner.email = email
        if phone is not None:
            partner.phone = phone
        if website is not None:
            partner.website = website
        if logo_url is not None:
            partner.logo_url = logo_url
        if primary_color is not None:
            partner.primary_color = primary_color
        if secondary_color is not None:
            partner.secondary_color = secondary_color
        if custom_domain is not None:
            # Check uniqueness
            if custom_domain:
                existing = await self.get_partner_by_domain(custom_domain)
                if existing and existing.partner_id != partner_id:
                    return PartnerCreateResult(
                        success=False,
                        message="Domain already in use",
                    )
            partner.custom_domain = custom_domain
        if login_page_url is not None:
            partner.login_page_url = login_page_url

        partner.updated_at = datetime.utcnow()
        self.db.commit()

        return PartnerCreateResult(
            success=True,
            message="Partner updated",
            partner_id=partner_id,
        )

    async def regenerate_api_key(self, partner_id: UUID) -> PartnerCreateResult:
        """Regenerate API key for a partner."""
        partner = await self.get_partner_by_id(partner_id)
        if not partner:
            return PartnerCreateResult(
                success=False,
                message="Partner not found",
            )

        if not partner.api_enabled:
            return PartnerCreateResult(
                success=False,
                message="API not enabled for this partner",
            )

        # Generate new API key
        api_key = secrets.token_urlsafe(32)
        partner.api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        partner.updated_at = datetime.utcnow()
        self.db.commit()

        logger.info(f"Regenerated API key for partner: {partner.code}")

        return PartnerCreateResult(
            success=True,
            message="API key regenerated",
            partner_id=partner_id,
            api_key=api_key,
        )

    async def validate_api_key(self, partner_code: str, api_key: str) -> Optional[Partner]:
        """Validate API key and return partner if valid."""
        partner = await self.get_partner_by_code(partner_code)
        if not partner or not partner.is_active or not partner.api_enabled:
            return None

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        if key_hash == partner.api_key_hash:
            return partner

        return None

    # -------------------------------------------------------------------------
    # Partner-Firm Relationships
    # -------------------------------------------------------------------------

    async def get_partner_firms(self, partner_id: UUID) -> List[PartnerFirm]:
        """Get all firms under a partner."""
        stmt = (
            select(PartnerFirm)
            .where(PartnerFirm.partner_id == partner_id)
            .order_by(PartnerFirm.joined_at)
        )
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    async def assign_firm_to_partner(
        self,
        partner_id: UUID,
        firm_id: UUID,
        revenue_share_percent: int = 0,
        notes: Optional[str] = None,
    ) -> FirmAssignResult:
        """Assign a firm to a partner."""
        # Verify partner exists
        partner = await self.get_partner_by_id(partner_id)
        if not partner:
            return FirmAssignResult(
                success=False,
                message="Partner not found",
            )

        # Check if already assigned
        existing = self.db.execute(
            select(PartnerFirm).where(
                and_(
                    PartnerFirm.partner_id == partner_id,
                    PartnerFirm.firm_id == firm_id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            return FirmAssignResult(
                success=False,
                message="Firm already assigned to this partner",
            )

        # Create assignment
        pf = PartnerFirm(
            partner_id=partner_id,
            firm_id=firm_id,
            status="active",
            revenue_share_percent=revenue_share_percent,
            notes=notes,
        )
        self.db.add(pf)

        # Update firm's partner_id
        from admin_panel.models.firm import Firm
        firm = self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        ).scalar_one_or_none()

        if firm:
            firm.partner_id = partner_id

        self.db.commit()

        logger.info(f"Assigned firm {firm_id} to partner {partner.code}")

        return FirmAssignResult(
            success=True,
            message="Firm assigned to partner",
        )

    async def remove_firm_from_partner(
        self,
        partner_id: UUID,
        firm_id: UUID,
    ) -> FirmAssignResult:
        """Remove a firm from a partner."""
        existing = self.db.execute(
            select(PartnerFirm).where(
                and_(
                    PartnerFirm.partner_id == partner_id,
                    PartnerFirm.firm_id == firm_id,
                )
            )
        ).scalar_one_or_none()

        if not existing:
            return FirmAssignResult(
                success=False,
                message="Firm not assigned to this partner",
            )

        self.db.delete(existing)

        # Update firm's partner_id
        from admin_panel.models.firm import Firm
        firm = self.db.execute(
            select(Firm).where(Firm.firm_id == firm_id)
        ).scalar_one_or_none()

        if firm:
            firm.partner_id = None

        self.db.commit()

        return FirmAssignResult(
            success=True,
            message="Firm removed from partner",
        )

    # -------------------------------------------------------------------------
    # Partner Admins
    # -------------------------------------------------------------------------

    async def get_partner_admins(self, partner_id: UUID) -> List[PartnerAdmin]:
        """Get all admins for a partner."""
        stmt = (
            select(PartnerAdmin)
            .where(PartnerAdmin.partner_id == partner_id)
            .order_by(PartnerAdmin.name)
        )
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_partner_admin(
        self,
        partner_id: UUID,
        email: str,
        password_hash: str,
        name: str,
        role: str = "partner_admin",
        phone: Optional[str] = None,
    ) -> PartnerAdminCreateResult:
        """Create a partner admin."""
        # Verify partner exists
        partner = await self.get_partner_by_id(partner_id)
        if not partner:
            return PartnerAdminCreateResult(
                success=False,
                message="Partner not found",
            )

        # Check email uniqueness
        existing = self.db.execute(
            select(PartnerAdmin).where(PartnerAdmin.email == email)
        ).scalar_one_or_none()

        if existing:
            return PartnerAdminCreateResult(
                success=False,
                message="Email already in use",
            )

        # Create admin
        admin = PartnerAdmin(
            partner_id=partner_id,
            email=email,
            password_hash=password_hash,
            name=name,
            role=role,
            phone=phone,
            is_active=True,
        )
        self.db.add(admin)
        self.db.commit()

        logger.info(f"Created partner admin: {email} for partner {partner.code}")

        return PartnerAdminCreateResult(
            success=True,
            message="Partner admin created",
            admin_id=admin.admin_id,
        )

    async def get_partner_admin_by_email(self, email: str) -> Optional[PartnerAdmin]:
        """Get partner admin by email."""
        stmt = (
            select(PartnerAdmin)
            .options(selectinload(PartnerAdmin.partner))
            .where(PartnerAdmin.email == email)
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Aggregation / Reporting
    # -------------------------------------------------------------------------

    async def get_partner_stats(self, partner_id: UUID) -> Dict[str, Any]:
        """Get aggregate statistics for a partner."""
        from admin_panel.models.firm import Firm

        # Get firm count
        firm_count = self.db.execute(
            select(func.count(PartnerFirm.firm_id)).where(
                PartnerFirm.partner_id == partner_id
            )
        ).scalar() or 0

        # Get admin count
        admin_count = self.db.execute(
            select(func.count(PartnerAdmin.admin_id)).where(
                and_(
                    PartnerAdmin.partner_id == partner_id,
                    PartnerAdmin.is_active == True,
                )
            )
        ).scalar() or 0

        return {
            "firm_count": firm_count,
            "admin_count": admin_count,
        }


# =============================================================================
# SERVICE FACTORY
# =============================================================================

def get_partner_service(db: Session) -> PartnerService:
    """Get partner service instance."""
    return PartnerService(db)
