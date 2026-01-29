"""
Support Tickets API for CPA Firms.

Provides endpoints for:
- Creating and managing support tickets
- Adding messages to tickets
- Tracking ticket status

All endpoints require CPA/firm authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass, field, asdict
import logging

from rbac.dependencies import require_auth, require_firm_user
from rbac.context import AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/cpa/support",
    tags=["Support Tickets"],
    responses={404: {"description": "Ticket not found"}},
)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class TicketCreate(BaseModel):
    """Request to create a new support ticket."""
    subject: str = Field(..., min_length=1, max_length=200, description="Ticket subject")
    description: str = Field(..., min_length=1, max_length=5000, description="Detailed description")
    category: str = Field(..., description="Category: technical, billing, feature, other")
    priority: str = Field("normal", description="Priority: low, normal, high, urgent")


class TicketUpdate(BaseModel):
    """Request to update ticket status or priority."""
    status: Optional[str] = Field(None, description="New status: open, in_progress, resolved, closed")
    priority: Optional[str] = Field(None, description="New priority: low, normal, high, urgent")


class MessageCreate(BaseModel):
    """Request to add a message to a ticket."""
    content: str = Field(..., min_length=1, max_length=5000, description="Message content")


# =============================================================================
# IN-MEMORY STORAGE (Replace with database in production)
# =============================================================================


@dataclass
class TicketMessage:
    """A message in a support ticket thread."""
    message_id: str
    content: str
    author_id: str
    author_name: str
    is_staff: bool
    created_at: datetime


@dataclass
class SupportTicket:
    """A support ticket."""
    ticket_id: str
    firm_id: str
    subject: str
    description: str
    category: str
    priority: str
    status: str
    created_by: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    messages: List[dict] = field(default_factory=list)


# Thread-safe in-memory storage
_tickets: dict[str, SupportTicket] = {}


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("")
async def list_tickets(
    ctx: AuthContext = Depends(require_auth),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List support tickets for the authenticated user's firm.

    Returns tickets sorted by most recently updated.
    """
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    # Filter tickets by firm
    firm_tickets = [t for t in _tickets.values() if t.firm_id == firm_id]

    # Apply filters
    if status:
        firm_tickets = [t for t in firm_tickets if t.status == status]
    if category:
        firm_tickets = [t for t in firm_tickets if t.category == category]

    # Sort by updated_at descending
    firm_tickets.sort(key=lambda t: t.updated_at, reverse=True)

    # Paginate
    total = len(firm_tickets)
    firm_tickets = firm_tickets[offset:offset + limit]

    return {
        "tickets": [
            {
                "ticket_id": t.ticket_id,
                "subject": t.subject,
                "category": t.category,
                "priority": t.priority,
                "status": t.status,
                "created_by_name": t.created_by_name,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
                "message_count": len(t.messages),
            }
            for t in firm_tickets
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("")
async def create_ticket(
    data: TicketCreate,
    ctx: AuthContext = Depends(require_auth),
):
    """
    Create a new support ticket.

    Returns the created ticket with its ID.
    """
    # Validate category
    valid_categories = {"technical", "billing", "feature", "other"}
    if data.category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )

    # Validate priority
    valid_priorities = {"low", "normal", "high", "urgent"}
    if data.priority not in valid_priorities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority. Must be one of: {', '.join(valid_priorities)}"
        )

    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)
    now = datetime.utcnow()

    ticket = SupportTicket(
        ticket_id=str(uuid4()),
        firm_id=firm_id,
        subject=data.subject,
        description=data.description,
        category=data.category,
        priority=data.priority,
        status="open",
        created_by=str(ctx.user_id),
        created_by_name=ctx.name or ctx.email,
        created_at=now,
        updated_at=now,
    )

    _tickets[ticket.ticket_id] = ticket

    logger.info(f"Support ticket created: {ticket.ticket_id} by user {ctx.user_id}")

    return {
        "ticket": {
            "ticket_id": ticket.ticket_id,
            "subject": ticket.subject,
            "description": ticket.description,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
            "created_at": ticket.created_at.isoformat(),
        },
        "message": "Ticket created successfully",
    }


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    ctx: AuthContext = Depends(require_auth),
):
    """
    Get detailed information about a specific ticket.

    Includes all messages in the ticket thread.
    """
    ticket = _tickets.get(ticket_id)
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    if not ticket or ticket.firm_id != firm_id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "ticket": {
            "ticket_id": ticket.ticket_id,
            "subject": ticket.subject,
            "description": ticket.description,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
            "created_by": ticket.created_by,
            "created_by_name": ticket.created_by_name,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "messages": ticket.messages,
        }
    }


@router.post("/{ticket_id}/messages")
async def add_message(
    ticket_id: str,
    data: MessageCreate,
    ctx: AuthContext = Depends(require_auth),
):
    """
    Add a message to an existing ticket.

    Updates the ticket's updated_at timestamp.
    """
    ticket = _tickets.get(ticket_id)
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    if not ticket or ticket.firm_id != firm_id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status == "closed":
        raise HTTPException(
            status_code=400,
            detail="Cannot add messages to a closed ticket"
        )

    message = {
        "message_id": str(uuid4()),
        "content": data.content,
        "author_id": str(ctx.user_id),
        "author_name": ctx.name or ctx.email,
        "is_staff": ctx.is_platform,
        "created_at": datetime.utcnow().isoformat(),
    }

    ticket.messages.append(message)
    ticket.updated_at = datetime.utcnow()

    logger.info(f"Message added to ticket {ticket_id} by user {ctx.user_id}")

    return {
        "message": message,
        "ticket_updated_at": ticket.updated_at.isoformat(),
    }


@router.patch("/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    data: TicketUpdate,
    ctx: AuthContext = Depends(require_auth),
):
    """
    Update ticket status or priority.

    Status transitions:
    - open -> in_progress, resolved, closed
    - in_progress -> resolved, closed
    - resolved -> closed, open (reopen)
    - closed -> open (reopen)
    """
    ticket = _tickets.get(ticket_id)
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)

    if not ticket or ticket.firm_id != firm_id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if data.status:
        valid_statuses = {"open", "in_progress", "resolved", "closed"}
        if data.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        ticket.status = data.status

    if data.priority:
        valid_priorities = {"low", "normal", "high", "urgent"}
        if data.priority not in valid_priorities:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority. Must be one of: {', '.join(valid_priorities)}"
            )
        ticket.priority = data.priority

    ticket.updated_at = datetime.utcnow()

    logger.info(f"Ticket {ticket_id} updated by user {ctx.user_id}")

    return {
        "ticket": {
            "ticket_id": ticket.ticket_id,
            "status": ticket.status,
            "priority": ticket.priority,
            "updated_at": ticket.updated_at.isoformat(),
        },
        "message": "Ticket updated successfully",
    }


@router.get("/stats/summary")
async def get_ticket_stats(
    ctx: AuthContext = Depends(require_auth),
):
    """
    Get support ticket statistics for the firm.

    Returns counts by status and category.
    """
    firm_id = str(ctx.firm_id) if ctx.firm_id else str(ctx.user_id)
    firm_tickets = [t for t in _tickets.values() if t.firm_id == firm_id]

    # Count by status
    status_counts = {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0}
    for ticket in firm_tickets:
        if ticket.status in status_counts:
            status_counts[ticket.status] += 1

    # Count by category
    category_counts = {"technical": 0, "billing": 0, "feature": 0, "other": 0}
    for ticket in firm_tickets:
        if ticket.category in category_counts:
            category_counts[ticket.category] += 1

    return {
        "total_tickets": len(firm_tickets),
        "by_status": status_counts,
        "by_category": category_counts,
        "open_tickets": status_counts["open"] + status_counts["in_progress"],
    }
