"""
Partner Management Module - White-label partner support.

Provides:
- Partner organization management
- Partner-firm relationships
- Partner admin authentication
- Cross-firm reporting for partners
"""

from .service import (
    PartnerService,
    get_partner_service,
    PartnerCreateResult,
    FirmAssignResult,
)

__all__ = [
    "PartnerService",
    "get_partner_service",
    "PartnerCreateResult",
    "FirmAssignResult",
]
