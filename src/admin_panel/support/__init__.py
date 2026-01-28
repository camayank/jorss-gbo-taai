"""
Support Module for Admin Panel

Provides:
1. Customer Support Ticket Management
   - Ticket creation and tracking
   - Priority and SLA management
   - Assignment to support staff
   - Status workflow
   - Customer communication

2. Firm Impersonation (Support Mode)
   - Secure session-based impersonation
   - Full audit logging
   - Session lifecycle management
"""

from .ticket_service import TicketService, TicketStatus, TicketPriority, TicketCategory
from .ticket_models import Ticket, TicketMessage, TicketAttachment
from .impersonation_service import (
    ImpersonationService,
    impersonation_service,
)
from .impersonation_models import (
    ImpersonationSession,
    ImpersonationAction,
    ImpersonationStatus,
    ImpersonationType,
    ImpersonationReason,
)

__all__ = [
    # Tickets
    "TicketService",
    "TicketStatus",
    "TicketPriority",
    "TicketCategory",
    "Ticket",
    "TicketMessage",
    "TicketAttachment",
    # Impersonation
    "ImpersonationService",
    "impersonation_service",
    "ImpersonationSession",
    "ImpersonationAction",
    "ImpersonationStatus",
    "ImpersonationType",
    "ImpersonationReason",
]
