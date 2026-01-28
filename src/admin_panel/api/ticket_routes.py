"""
Support Ticket Routes

API endpoints for support ticket management.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from uuid import UUID
import logging

from ..support.ticket_service import (
    ticket_service,
    TicketStatus,
    TicketPriority,
    TicketCategory,
)

logger = logging.getLogger(__name__)

ticket_router = APIRouter(prefix="/tickets", tags=["Support Tickets"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateTicketRequest(BaseModel):
    """Request to create a new support ticket."""
    subject: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    customer_email: EmailStr
    customer_name: str = Field("", max_length=255)
    category: str = Field("other", description="Ticket category")
    priority: str = Field("normal", description="Ticket priority")
    firm_id: Optional[str] = None
    customer_id: Optional[str] = None
    source: str = Field("web", description="web, email, api, phone")
    tags: Optional[List[str]] = None


class UpdateTicketRequest(BaseModel):
    """Request to update a ticket."""
    subject: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None


class AssignTicketRequest(BaseModel):
    """Request to assign a ticket."""
    agent_id: str = Field(..., description="Agent user ID")
    agent_name: Optional[str] = None


class ReassignTicketRequest(BaseModel):
    """Request to reassign a ticket."""
    new_agent_id: str = Field(..., description="New agent user ID")
    new_agent_name: Optional[str] = None
    reason: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    """Request to update ticket status."""
    status: str = Field(..., description="New status")


class ResolveTicketRequest(BaseModel):
    """Request to resolve a ticket."""
    resolution_notes: str = Field("", description="Resolution notes")


class ReopenTicketRequest(BaseModel):
    """Request to reopen a ticket."""
    reason: str = Field("", description="Reason for reopening")


class AddMessageRequest(BaseModel):
    """Request to add a message."""
    content: str = Field(..., min_length=1)
    author_name: Optional[str] = None
    author_email: Optional[str] = None


class AddAgentReplyRequest(BaseModel):
    """Request to add an agent reply."""
    content: str = Field(..., min_length=1)
    agent_name: Optional[str] = None


class AddInternalNoteRequest(BaseModel):
    """Request to add an internal note."""
    content: str = Field(..., min_length=1)
    author_name: Optional[str] = None


class RateSatisfactionRequest(BaseModel):
    """Request to rate satisfaction."""
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = None


# =============================================================================
# TICKET CRUD
# =============================================================================

@ticket_router.post("")
async def create_ticket(request: CreateTicketRequest):
    """
    Create a new support ticket.

    Creates a ticket with automatic SLA calculation based on priority.
    """
    try:
        category = TicketCategory(request.category)
    except ValueError:
        raise HTTPException(400, f"Invalid category: {request.category}")

    try:
        priority = TicketPriority(request.priority)
    except ValueError:
        raise HTTPException(400, f"Invalid priority: {request.priority}")

    ticket = ticket_service.create_ticket(
        subject=request.subject,
        description=request.description,
        customer_email=request.customer_email,
        customer_name=request.customer_name,
        category=category,
        priority=priority,
        firm_id=UUID(request.firm_id) if request.firm_id else None,
        customer_id=UUID(request.customer_id) if request.customer_id else None,
        source=request.source,
        tags=request.tags,
    )

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.get("/{ticket_id}")
async def get_ticket(ticket_id: str):
    """Get a specific ticket by ID."""
    try:
        ticket = ticket_service.get_ticket(UUID(ticket_id))
    except ValueError:
        # Try by ticket number
        ticket = ticket_service.get_ticket_by_number(ticket_id)

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.put("/{ticket_id}")
async def update_ticket(ticket_id: str, request: UpdateTicketRequest):
    """Update a ticket."""
    category = None
    priority = None

    if request.category:
        try:
            category = TicketCategory(request.category)
        except ValueError:
            raise HTTPException(400, f"Invalid category: {request.category}")

    if request.priority:
        try:
            priority = TicketPriority(request.priority)
        except ValueError:
            raise HTTPException(400, f"Invalid priority: {request.priority}")

    ticket = ticket_service.update_ticket(
        ticket_id=UUID(ticket_id),
        subject=request.subject,
        category=category,
        priority=priority,
        tags=request.tags,
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.delete("/{ticket_id}")
async def delete_ticket(ticket_id: str):
    """Delete a ticket."""
    success = ticket_service.delete_ticket(UUID(ticket_id))
    if not success:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "message": "Ticket deleted",
    }


# =============================================================================
# ASSIGNMENT
# =============================================================================

@ticket_router.post("/{ticket_id}/assign")
async def assign_ticket(ticket_id: str, request: AssignTicketRequest):
    """Assign a ticket to an agent."""
    ticket = ticket_service.assign_ticket(
        ticket_id=UUID(ticket_id),
        agent_id=UUID(request.agent_id),
        agent_name=request.agent_name or "",
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.post("/{ticket_id}/unassign")
async def unassign_ticket(ticket_id: str):
    """Remove assignment from a ticket."""
    ticket = ticket_service.unassign_ticket(UUID(ticket_id))
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.post("/{ticket_id}/reassign")
async def reassign_ticket(ticket_id: str, request: ReassignTicketRequest):
    """Reassign a ticket to a different agent."""
    ticket = ticket_service.reassign_ticket(
        ticket_id=UUID(ticket_id),
        new_agent_id=UUID(request.new_agent_id),
        new_agent_name=request.new_agent_name or "",
        reason=request.reason or "",
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


# =============================================================================
# STATUS MANAGEMENT
# =============================================================================

@ticket_router.post("/{ticket_id}/status")
async def update_status(ticket_id: str, request: UpdateStatusRequest):
    """Update ticket status."""
    try:
        status = TicketStatus(request.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {request.status}")

    ticket = ticket_service.update_status(
        ticket_id=UUID(ticket_id),
        new_status=status,
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.post("/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: str,
    request: ResolveTicketRequest,
    agent_id: Optional[str] = Query(None),
):
    """Resolve a ticket."""
    ticket = ticket_service.resolve_ticket(
        ticket_id=UUID(ticket_id),
        resolved_by=UUID(agent_id) if agent_id else None,
        resolution_notes=request.resolution_notes,
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.post("/{ticket_id}/close")
async def close_ticket(ticket_id: str):
    """Close a ticket."""
    ticket = ticket_service.close_ticket(UUID(ticket_id))
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.post("/{ticket_id}/reopen")
async def reopen_ticket(ticket_id: str, request: ReopenTicketRequest):
    """Reopen a closed ticket."""
    ticket = ticket_service.reopen_ticket(
        ticket_id=UUID(ticket_id),
        reason=request.reason,
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


# =============================================================================
# MESSAGES
# =============================================================================

@ticket_router.post("/{ticket_id}/messages/customer")
async def add_customer_message(ticket_id: str, request: AddMessageRequest):
    """Add a customer message to a ticket."""
    message = ticket_service.add_customer_message(
        ticket_id=UUID(ticket_id),
        content=request.content,
        author_name=request.author_name or "",
        author_email=request.author_email or "",
    )

    if not message:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "message": message.to_dict(),
    }


@ticket_router.post("/{ticket_id}/messages/reply")
async def add_agent_reply(
    ticket_id: str,
    request: AddAgentReplyRequest,
    agent_id: str = Query(..., description="Agent user ID"),
):
    """Add an agent reply to a ticket."""
    message = ticket_service.add_agent_reply(
        ticket_id=UUID(ticket_id),
        content=request.content,
        agent_id=UUID(agent_id),
        agent_name=request.agent_name or "",
    )

    if not message:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "message": message.to_dict(),
    }


@ticket_router.post("/{ticket_id}/messages/internal")
async def add_internal_note(
    ticket_id: str,
    request: AddInternalNoteRequest,
    agent_id: str = Query(..., description="Agent user ID"),
):
    """Add an internal note (not visible to customer)."""
    message = ticket_service.add_internal_note(
        ticket_id=UUID(ticket_id),
        content=request.content,
        author_id=UUID(agent_id),
        author_name=request.author_name or "",
    )

    if not message:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "message": message.to_dict(),
    }


# =============================================================================
# SATISFACTION
# =============================================================================

@ticket_router.post("/{ticket_id}/satisfaction")
async def rate_satisfaction(ticket_id: str, request: RateSatisfactionRequest):
    """Rate customer satisfaction for a ticket."""
    ticket = ticket_service.rate_satisfaction(
        ticket_id=UUID(ticket_id),
        rating=request.rating,
        feedback=request.feedback or "",
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


# =============================================================================
# TICKET QUERIES
# =============================================================================

@ticket_router.get("")
async def list_tickets(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    firm_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    include_closed: bool = Query(False),
    sla_at_risk: bool = Query(False),
    search: Optional[str] = Query(None),
):
    """List tickets with optional filters."""
    status_filter = TicketStatus(status) if status else None
    category_filter = TicketCategory(category) if category else None
    priority_filter = TicketPriority(priority) if priority else None

    tickets = ticket_service.get_tickets(
        status=status_filter,
        category=category_filter,
        priority=priority_filter,
        assigned_to=UUID(assigned_to) if assigned_to else None,
        firm_id=UUID(firm_id) if firm_id else None,
        customer_id=UUID(customer_id) if customer_id else None,
        include_closed=include_closed,
        sla_at_risk=sla_at_risk,
        search_query=search,
    )

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


@ticket_router.get("/unassigned")
async def get_unassigned_tickets():
    """Get tickets without assignment."""
    tickets = ticket_service.get_unassigned_tickets()

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


@ticket_router.get("/my-tickets")
async def get_my_tickets(
    agent_id: str = Query(..., description="Agent user ID"),
    include_closed: bool = Query(False),
):
    """Get tickets assigned to the current agent."""
    tickets = ticket_service.get_my_tickets(
        agent_id=UUID(agent_id),
        include_closed=include_closed,
    )

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


@ticket_router.get("/firm/{firm_id}")
async def get_firm_tickets(
    firm_id: str,
    include_closed: bool = Query(False),
):
    """Get tickets for a specific firm."""
    tickets = ticket_service.get_tickets_by_firm(
        firm_id=UUID(firm_id),
        include_closed=include_closed,
    )

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


@ticket_router.get("/sla-at-risk")
async def get_sla_at_risk_tickets():
    """Get tickets at risk of SLA breach."""
    tickets = ticket_service.get_sla_at_risk_tickets()

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


@ticket_router.get("/overdue")
async def get_overdue_tickets():
    """Get tickets that have breached SLA."""
    tickets = ticket_service.get_overdue_tickets()

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@ticket_router.get("/summary")
async def get_ticket_summary():
    """Get summary statistics for tickets."""
    summary = ticket_service.get_ticket_summary()

    return {
        "success": True,
        **summary,
    }


@ticket_router.get("/agent/{agent_id}/performance")
async def get_agent_performance(agent_id: str):
    """Get performance metrics for an agent."""
    performance = ticket_service.get_agent_performance(UUID(agent_id))

    return {
        "success": True,
        **performance,
    }


# =============================================================================
# REFERENCE DATA
# =============================================================================

@ticket_router.get("/categories")
async def get_categories():
    """Get list of ticket categories."""
    return {
        "success": True,
        "categories": [
            {"value": c.value, "label": c.value.replace("_", " ").title()}
            for c in TicketCategory
        ],
    }


@ticket_router.get("/statuses")
async def get_statuses():
    """Get list of ticket statuses."""
    return {
        "success": True,
        "statuses": [
            {"value": s.value, "label": s.value.replace("_", " ").title()}
            for s in TicketStatus
        ],
    }


@ticket_router.get("/priorities")
async def get_priorities():
    """Get list of ticket priorities."""
    return {
        "success": True,
        "priorities": [
            {"value": p.value, "label": p.value.title()}
            for p in TicketPriority
        ],
    }
