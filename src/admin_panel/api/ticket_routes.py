"""
Support Ticket Routes

API endpoints for support ticket management.
"""

import logging
from collections import defaultdict
from typing import Iterable, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from rbac import Role

from ..auth.rbac import TenantContext, get_current_user
from ..support.ticket_models import Ticket
from ..support.ticket_service import (
    TicketCategory,
    TicketPriority,
    TicketStatus,
    ticket_service,
)

logger = logging.getLogger(__name__)

ticket_router = APIRouter(prefix="/tickets", tags=["Support Tickets"])

_PLATFORM_ROLE_VALUES = {
    Role.SUPER_ADMIN.value,
    Role.PLATFORM_ADMIN.value,
    Role.SUPPORT.value,
    Role.BILLING.value,
}
_READ_ROLE_VALUES = _PLATFORM_ROLE_VALUES | {
    Role.PARTNER.value,
    Role.STAFF.value,
}
_WRITE_ROLE_VALUES = {
    Role.SUPER_ADMIN.value,
    Role.PLATFORM_ADMIN.value,
    Role.SUPPORT.value,
    Role.PARTNER.value,
    Role.STAFF.value,
}


def _role_value(user: TenantContext) -> str:
    raw_role = getattr(user, "role", "")
    return raw_role.value if hasattr(raw_role, "value") else str(raw_role)


def _is_platform_user(user: TenantContext) -> bool:
    if hasattr(user, "is_platform"):
        try:
            return bool(user.is_platform)
        except Exception:
            pass
    return _role_value(user) in _PLATFORM_ROLE_VALUES


def _current_firm_id(user: TenantContext) -> Optional[UUID]:
    firm_id = getattr(user, "firm_id", None)
    if firm_id is None:
        return None
    return _coerce_uuid(firm_id, "firm_id")


def _coerce_uuid(value: Optional[object], field_name: str) -> Optional[UUID]:
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")


def _require_allowed_role(user: TenantContext, allowed_roles: set[str], action: str) -> None:
    if _role_value(user) not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Role is not allowed to {action}",
        )


def _require_ticket_reader(user: TenantContext = Depends(get_current_user)) -> TenantContext:
    _require_allowed_role(user, _READ_ROLE_VALUES, "view tickets")
    return user


def _require_ticket_writer(user: TenantContext = Depends(get_current_user)) -> TenantContext:
    _require_allowed_role(user, _WRITE_ROLE_VALUES, "modify tickets")
    return user


def _resolve_requested_firm_scope(
    user: TenantContext,
    requested_firm_id: Optional[UUID],
) -> Optional[UUID]:
    if _is_platform_user(user):
        return requested_firm_id

    user_firm_id = _current_firm_id(user)
    if not user_firm_id:
        raise HTTPException(status_code=403, detail="Firm context required")

    if requested_firm_id and requested_firm_id != user_firm_id:
        raise HTTPException(status_code=403, detail="Access denied to this firm")

    return user_firm_id


def _get_ticket_or_404(ticket_id: str) -> Ticket:
    try:
        ticket = ticket_service.get_ticket(UUID(ticket_id))
    except ValueError:
        ticket = ticket_service.get_ticket_by_number(ticket_id)

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _enforce_ticket_scope(user: TenantContext, ticket: Ticket) -> None:
    if _is_platform_user(user):
        return

    user_firm_id = _current_firm_id(user)
    if not user_firm_id:
        raise HTTPException(status_code=403, detail="Firm context required")

    if not ticket.firm_id or ticket.firm_id != user_firm_id:
        raise HTTPException(status_code=403, detail="Access denied to this ticket")


def _filter_tickets_for_user(user: TenantContext, tickets: Iterable[Ticket]) -> List[Ticket]:
    if _is_platform_user(user):
        return list(tickets)

    user_firm_id = _current_firm_id(user)
    if not user_firm_id:
        return []

    return [ticket for ticket in tickets if ticket.firm_id == user_firm_id]


def _build_ticket_summary(tickets: List[Ticket]) -> dict:
    by_status: dict[str, int] = defaultdict(int)
    by_category: dict[str, int] = defaultdict(int)
    by_priority: dict[str, int] = defaultdict(int)

    total_response_time = 0.0
    total_resolution_time = 0.0
    response_count = 0
    resolution_count = 0
    total_satisfaction = 0
    satisfaction_count = 0

    sla_response_breached = 0
    sla_resolution_breached = 0
    sla_at_risk = 0
    unassigned = 0

    for ticket in tickets:
        by_status[ticket.status.value] += 1
        by_category[ticket.category.value] += 1
        by_priority[ticket.priority.value] += 1

        if ticket.sla_response_breached:
            sla_response_breached += 1
        if ticket.sla_resolution_breached:
            sla_resolution_breached += 1
        if ticket.is_sla_response_at_risk or ticket.is_sla_resolution_at_risk:
            sla_at_risk += 1
        if not ticket.assigned_to:
            unassigned += 1

        if ticket.time_to_first_response is not None:
            total_response_time += ticket.time_to_first_response
            response_count += 1
        if ticket.resolution_time is not None:
            total_resolution_time += ticket.resolution_time
            resolution_count += 1
        if ticket.satisfaction_rating is not None:
            total_satisfaction += ticket.satisfaction_rating
            satisfaction_count += 1

    return {
        "total": len(tickets),
        "open": len(
            [
                ticket
                for ticket in tickets
                if ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
            ]
        ),
        "unassigned": unassigned,
        "sla_at_risk": sla_at_risk,
        "sla_response_breached": sla_response_breached,
        "sla_resolution_breached": sla_resolution_breached,
        "by_status": dict(by_status),
        "by_category": dict(by_category),
        "by_priority": dict(by_priority),
        "avg_response_time_hours": (total_response_time / response_count) if response_count else None,
        "avg_resolution_time_hours": (total_resolution_time / resolution_count) if resolution_count else None,
        "avg_satisfaction": (total_satisfaction / satisfaction_count) if satisfaction_count else None,
        "satisfaction_count": satisfaction_count,
    }


def _build_agent_performance(tickets: List[Ticket]) -> dict:
    resolved = [
        ticket
        for ticket in tickets
        if ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
    ]
    open_tickets = [
        ticket
        for ticket in tickets
        if ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
    ]

    total_response_time = 0.0
    total_resolution_time = 0.0
    total_satisfaction = 0
    response_count = 0
    resolution_count = 0
    satisfaction_count = 0
    sla_breached = 0

    for ticket in tickets:
        if ticket.time_to_first_response is not None:
            total_response_time += ticket.time_to_first_response
            response_count += 1
        if ticket.resolution_time is not None:
            total_resolution_time += ticket.resolution_time
            resolution_count += 1
        if ticket.satisfaction_rating is not None:
            total_satisfaction += ticket.satisfaction_rating
            satisfaction_count += 1
        if ticket.sla_response_breached or ticket.sla_resolution_breached:
            sla_breached += 1

    return {
        "total_assigned": len(tickets),
        "open": len(open_tickets),
        "resolved": len(resolved),
        "sla_breached": sla_breached,
        "avg_response_time_hours": (total_response_time / response_count) if response_count else None,
        "avg_resolution_time_hours": (total_resolution_time / resolution_count) if resolution_count else None,
        "avg_satisfaction": (total_satisfaction / satisfaction_count) if satisfaction_count else None,
        "satisfaction_count": satisfaction_count,
    }


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
async def create_ticket(
    request: CreateTicketRequest,
    user: TenantContext = Depends(_require_ticket_writer),
):
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

    requested_firm_id = _coerce_uuid(request.firm_id, "firm_id")
    scoped_firm_id = _resolve_requested_firm_scope(user, requested_firm_id)
    customer_id = _coerce_uuid(request.customer_id, "customer_id")

    ticket = ticket_service.create_ticket(
        subject=request.subject,
        description=request.description,
        customer_email=request.customer_email,
        customer_name=request.customer_name,
        category=category,
        priority=priority,
        firm_id=scoped_firm_id,
        customer_id=customer_id,
        source=request.source,
        tags=request.tags,
    )

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get a specific ticket by ID."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.put("/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    request: UpdateTicketRequest,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Update a ticket."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

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
        ticket_id=ticket.id,
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
async def delete_ticket(
    ticket_id: str,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Delete a ticket."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    success = ticket_service.delete_ticket(ticket.id)
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
async def assign_ticket(
    ticket_id: str,
    request: AssignTicketRequest,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Assign a ticket to an agent."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    agent_id = _coerce_uuid(request.agent_id, "agent_id")
    ticket = ticket_service.assign_ticket(
        ticket_id=ticket.id,
        agent_id=agent_id,
        agent_name=request.agent_name or "",
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.post("/{ticket_id}/unassign")
async def unassign_ticket(
    ticket_id: str,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Remove assignment from a ticket."""
    existing = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, existing)

    ticket = ticket_service.unassign_ticket(existing.id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.post("/{ticket_id}/reassign")
async def reassign_ticket(
    ticket_id: str,
    request: ReassignTicketRequest,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Reassign a ticket to a different agent."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    new_agent_id = _coerce_uuid(request.new_agent_id, "new_agent_id")
    ticket = ticket_service.reassign_ticket(
        ticket_id=ticket.id,
        new_agent_id=new_agent_id,
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
async def update_status(
    ticket_id: str,
    request: UpdateStatusRequest,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Update ticket status."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    try:
        status = TicketStatus(request.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {request.status}")

    ticket = ticket_service.update_status(
        ticket_id=ticket.id,
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
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Resolve a ticket."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    resolved_by = _coerce_uuid(agent_id, "agent_id") if agent_id else _coerce_uuid(
        getattr(user, "user_id", None),
        "user_id",
    )

    ticket = ticket_service.resolve_ticket(
        ticket_id=ticket.id,
        resolved_by=resolved_by,
        resolution_notes=request.resolution_notes,
    )

    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.post("/{ticket_id}/close")
async def close_ticket(
    ticket_id: str,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Close a ticket."""
    existing = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, existing)

    ticket = ticket_service.close_ticket(existing.id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    return {
        "success": True,
        "ticket": ticket.to_dict(),
    }


@ticket_router.post("/{ticket_id}/reopen")
async def reopen_ticket(
    ticket_id: str,
    request: ReopenTicketRequest,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Reopen a closed ticket."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    ticket = ticket_service.reopen_ticket(
        ticket_id=ticket.id,
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
async def add_customer_message(
    ticket_id: str,
    request: AddMessageRequest,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Add a customer message to a ticket."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    message = ticket_service.add_customer_message(
        ticket_id=ticket.id,
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
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Add an agent reply to a ticket."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    reply_agent_id = _coerce_uuid(agent_id, "agent_id")
    message = ticket_service.add_agent_reply(
        ticket_id=ticket.id,
        content=request.content,
        agent_id=reply_agent_id,
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
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Add an internal note (not visible to customer)."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    author_id = _coerce_uuid(agent_id, "agent_id")
    message = ticket_service.add_internal_note(
        ticket_id=ticket.id,
        content=request.content,
        author_id=author_id,
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
async def rate_satisfaction(
    ticket_id: str,
    request: RateSatisfactionRequest,
    user: TenantContext = Depends(_require_ticket_writer),
):
    """Rate customer satisfaction for a ticket."""
    ticket = _get_ticket_or_404(ticket_id)
    _enforce_ticket_scope(user, ticket)

    ticket = ticket_service.rate_satisfaction(
        ticket_id=ticket.id,
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
    user: TenantContext = Depends(_require_ticket_reader),
):
    """List tickets with optional filters."""
    try:
        status_filter = TicketStatus(status) if status else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    try:
        category_filter = TicketCategory(category) if category else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    try:
        priority_filter = TicketPriority(priority) if priority else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    assigned_to_uuid = _coerce_uuid(assigned_to, "assigned_to")
    requested_firm_id = _coerce_uuid(firm_id, "firm_id")
    customer_id_uuid = _coerce_uuid(customer_id, "customer_id")
    scoped_firm_id = _resolve_requested_firm_scope(user, requested_firm_id)

    tickets = ticket_service.get_tickets(
        status=status_filter,
        category=category_filter,
        priority=priority_filter,
        assigned_to=assigned_to_uuid,
        firm_id=scoped_firm_id,
        customer_id=customer_id_uuid,
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
async def get_unassigned_tickets(
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get tickets without assignment."""
    tickets = _filter_tickets_for_user(user, ticket_service.get_unassigned_tickets())

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


@ticket_router.get("/my-tickets")
async def get_my_tickets(
    agent_id: str = Query(..., description="Agent user ID"),
    include_closed: bool = Query(False),
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get tickets assigned to the current agent."""
    agent_uuid = _coerce_uuid(agent_id, "agent_id")
    if (
        not _is_platform_user(user)
        and _role_value(user) == Role.STAFF.value
        and str(getattr(user, "user_id", "")) != str(agent_uuid)
    ):
        raise HTTPException(status_code=403, detail="Staff can only view their own tickets")

    tickets = ticket_service.get_my_tickets(
        agent_id=agent_uuid,
        include_closed=include_closed,
    )
    tickets = _filter_tickets_for_user(user, tickets)

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


@ticket_router.get("/firm/{firm_id}")
async def get_firm_tickets(
    firm_id: str,
    include_closed: bool = Query(False),
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get tickets for a specific firm."""
    requested_firm_id = _coerce_uuid(firm_id, "firm_id")
    scoped_firm_id = _resolve_requested_firm_scope(user, requested_firm_id)

    tickets = ticket_service.get_tickets_by_firm(
        firm_id=scoped_firm_id,
        include_closed=include_closed,
    )

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


@ticket_router.get("/sla-at-risk")
async def get_sla_at_risk_tickets(
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get tickets at risk of SLA breach."""
    tickets = _filter_tickets_for_user(user, ticket_service.get_sla_at_risk_tickets())

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


@ticket_router.get("/overdue")
async def get_overdue_tickets(
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get tickets that have breached SLA."""
    tickets = _filter_tickets_for_user(user, ticket_service.get_overdue_tickets())

    return {
        "success": True,
        "tickets": [t.to_dict(include_messages=False) for t in tickets],
        "total": len(tickets),
    }


# =============================================================================
# ANALYTICS
# =============================================================================

@ticket_router.get("/summary")
async def get_ticket_summary(
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get summary statistics for tickets."""
    if _is_platform_user(user):
        summary = ticket_service.get_ticket_summary()
    else:
        firm_id = _current_firm_id(user)
        if not firm_id:
            raise HTTPException(status_code=403, detail="Firm context required")
        summary = _build_ticket_summary(
            ticket_service.get_tickets(firm_id=firm_id, include_closed=True)
        )

    return {
        "success": True,
        **summary,
    }


@ticket_router.get("/agent/{agent_id}/performance")
async def get_agent_performance(
    agent_id: str,
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get performance metrics for an agent."""
    agent_uuid = _coerce_uuid(agent_id, "agent_id")
    if (
        not _is_platform_user(user)
        and _role_value(user) == Role.STAFF.value
        and str(getattr(user, "user_id", "")) != str(agent_uuid)
    ):
        raise HTTPException(
            status_code=403,
            detail="Staff can only view their own performance metrics",
        )

    if _is_platform_user(user):
        performance = ticket_service.get_agent_performance(agent_uuid)
    else:
        firm_id = _current_firm_id(user)
        if not firm_id:
            raise HTTPException(status_code=403, detail="Firm context required")
        scoped_tickets = ticket_service.get_tickets(
            assigned_to=agent_uuid,
            firm_id=firm_id,
            include_closed=True,
        )
        performance = _build_agent_performance(scoped_tickets)

    return {
        "success": True,
        **performance,
    }


# =============================================================================
# REFERENCE DATA
# =============================================================================

@ticket_router.get("/categories")
async def get_categories(
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get list of ticket categories."""
    return {
        "success": True,
        "categories": [
            {"value": c.value, "label": c.value.replace("_", " ").title()}
            for c in TicketCategory
        ],
    }


@ticket_router.get("/statuses")
async def get_statuses(
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get list of ticket statuses."""
    return {
        "success": True,
        "statuses": [
            {"value": s.value, "label": s.value.replace("_", " ").title()}
            for s in TicketStatus
        ],
    }


@ticket_router.get("/priorities")
async def get_priorities(
    user: TenantContext = Depends(_require_ticket_reader),
):
    """Get list of ticket priorities."""
    return {
        "success": True,
        "priorities": [
            {"value": p.value, "label": p.value.title()}
            for p in TicketPriority
        ],
    }
