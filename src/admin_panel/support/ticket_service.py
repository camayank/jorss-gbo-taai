"""
Support Ticket Service

Business logic for support ticket management.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from collections import defaultdict

from .ticket_models import (
    Ticket,
    TicketMessage,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    MessageType,
)

logger = logging.getLogger(__name__)


class TicketService:
    """
    Service for managing support tickets.

    Provides:
    - Ticket CRUD operations
    - Assignment and escalation
    - SLA tracking
    - Customer communication
    - Analytics and reporting
    """

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._tickets: Dict[UUID, Ticket] = {}
        self._ticket_counter = 0

    # =========================================================================
    # TICKET CRUD
    # =========================================================================

    def create_ticket(
        self,
        subject: str,
        description: str,
        customer_email: str,
        customer_name: str = "",
        category: TicketCategory = TicketCategory.OTHER,
        priority: TicketPriority = TicketPriority.NORMAL,
        firm_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        source: str = "web",
        tags: Optional[List[str]] = None,
    ) -> Ticket:
        """
        Create a new support ticket.

        Args:
            subject: Ticket subject
            description: Detailed description
            customer_email: Customer's email
            customer_name: Customer's name
            category: Ticket category
            priority: Ticket priority
            firm_id: Associated firm (for CPA customers)
            customer_id: Customer/user ID
            source: Source of ticket (web, email, api, phone)
            tags: Tags for filtering

        Returns:
            Created Ticket object
        """
        self._ticket_counter += 1
        ticket_number = f"TKT-{datetime.utcnow().year}-{self._ticket_counter:04d}"

        ticket = Ticket(
            ticket_number=ticket_number,
            firm_id=firm_id,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_email=customer_email,
            subject=subject,
            description=description,
            category=category,
            priority=priority,
            source=source,
            tags=tags or [],
        )

        # Add initial description as first message
        ticket.add_message(
            content=description,
            message_type=MessageType.CUSTOMER,
            author_name=customer_name,
            author_email=customer_email,
        )

        self._tickets[ticket.id] = ticket
        logger.info(f"Created ticket: {ticket.ticket_number} - {ticket.subject}")

        return ticket

    def get_ticket(self, ticket_id: UUID) -> Optional[Ticket]:
        """Get a ticket by ID."""
        return self._tickets.get(ticket_id)

    def get_ticket_by_number(self, ticket_number: str) -> Optional[Ticket]:
        """Get a ticket by ticket number."""
        for ticket in self._tickets.values():
            if ticket.ticket_number == ticket_number:
                return ticket
        return None

    def update_ticket(
        self,
        ticket_id: UUID,
        subject: Optional[str] = None,
        category: Optional[TicketCategory] = None,
        priority: Optional[TicketPriority] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Ticket]:
        """Update ticket details."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        if subject is not None:
            ticket.subject = subject
        if category is not None:
            ticket.category = category
        if priority is not None:
            ticket.priority = priority
            # Recalculate SLA for priority change
            ticket._calculate_sla()
        if tags is not None:
            ticket.tags = tags

        ticket.updated_at = datetime.utcnow()
        logger.info(f"Updated ticket: {ticket.ticket_number}")

        return ticket

    def delete_ticket(self, ticket_id: UUID) -> bool:
        """Delete a ticket (soft delete in production)."""
        if ticket_id in self._tickets:
            del self._tickets[ticket_id]
            logger.info(f"Deleted ticket: {ticket_id}")
            return True
        return False

    # =========================================================================
    # ASSIGNMENT
    # =========================================================================

    def assign_ticket(
        self,
        ticket_id: UUID,
        agent_id: UUID,
        agent_name: str = "",
    ) -> Optional[Ticket]:
        """Assign ticket to an agent."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        ticket.assign(agent_id, agent_name)

        # Add system message
        ticket.add_message(
            content=f"Ticket assigned to {agent_name or agent_id}",
            message_type=MessageType.SYSTEM,
            is_internal=True,
        )

        logger.info(f"Assigned ticket {ticket.ticket_number} to {agent_name or agent_id}")
        return ticket

    def unassign_ticket(self, ticket_id: UUID) -> Optional[Ticket]:
        """Remove assignment from a ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        old_assignee = ticket.assigned_to_name or str(ticket.assigned_to)
        ticket.assigned_to = None
        ticket.assigned_to_name = None
        ticket.updated_at = datetime.utcnow()

        ticket.add_message(
            content=f"Ticket unassigned from {old_assignee}",
            message_type=MessageType.SYSTEM,
            is_internal=True,
        )

        return ticket

    def reassign_ticket(
        self,
        ticket_id: UUID,
        new_agent_id: UUID,
        new_agent_name: str = "",
        reason: str = "",
    ) -> Optional[Ticket]:
        """Reassign ticket to a different agent."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        old_assignee = ticket.assigned_to_name or str(ticket.assigned_to)
        ticket.assign(new_agent_id, new_agent_name)

        message = f"Ticket reassigned from {old_assignee} to {new_agent_name or new_agent_id}"
        if reason:
            message += f". Reason: {reason}"

        ticket.add_message(
            content=message,
            message_type=MessageType.SYSTEM,
            is_internal=True,
        )

        return ticket

    # =========================================================================
    # STATUS MANAGEMENT
    # =========================================================================

    def update_status(
        self,
        ticket_id: UUID,
        new_status: TicketStatus,
        updated_by: Optional[UUID] = None,
    ) -> Optional[Ticket]:
        """Update ticket status."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        old_status = ticket.status
        ticket.status = new_status
        ticket.updated_at = datetime.utcnow()

        ticket.add_message(
            content=f"Status changed from {old_status.value} to {new_status.value}",
            message_type=MessageType.SYSTEM,
            is_internal=True,
        )

        logger.info(f"Ticket {ticket.ticket_number}: {old_status.value} -> {new_status.value}")
        return ticket

    def resolve_ticket(
        self,
        ticket_id: UUID,
        resolved_by: UUID = None,
        resolution_notes: str = "",
    ) -> Optional[Ticket]:
        """Resolve a ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        ticket.resolve(resolved_by, resolution_notes)

        if resolution_notes:
            ticket.add_message(
                content=f"Resolution: {resolution_notes}",
                message_type=MessageType.AGENT,
                author_id=resolved_by,
            )

        logger.info(f"Resolved ticket: {ticket.ticket_number}")
        return ticket

    def close_ticket(self, ticket_id: UUID) -> Optional[Ticket]:
        """Close a ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        ticket.close()
        logger.info(f"Closed ticket: {ticket.ticket_number}")
        return ticket

    def reopen_ticket(self, ticket_id: UUID, reason: str = "") -> Optional[Ticket]:
        """Reopen a closed ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        ticket.reopen()

        message = "Ticket reopened"
        if reason:
            message += f": {reason}"

        ticket.add_message(
            content=message,
            message_type=MessageType.SYSTEM,
            is_internal=True,
        )

        logger.info(f"Reopened ticket: {ticket.ticket_number}")
        return ticket

    # =========================================================================
    # MESSAGES
    # =========================================================================

    def add_customer_message(
        self,
        ticket_id: UUID,
        content: str,
        author_name: str = "",
        author_email: str = "",
    ) -> Optional[TicketMessage]:
        """Add a customer message to a ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        message = ticket.add_message(
            content=content,
            message_type=MessageType.CUSTOMER,
            author_name=author_name,
            author_email=author_email,
        )

        return message

    def add_agent_reply(
        self,
        ticket_id: UUID,
        content: str,
        agent_id: UUID,
        agent_name: str = "",
    ) -> Optional[TicketMessage]:
        """Add an agent reply to a ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        message = ticket.add_message(
            content=content,
            message_type=MessageType.AGENT,
            author_id=agent_id,
            author_name=agent_name,
        )

        return message

    def add_internal_note(
        self,
        ticket_id: UUID,
        content: str,
        author_id: UUID,
        author_name: str = "",
    ) -> Optional[TicketMessage]:
        """Add an internal note (not visible to customer)."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        message = ticket.add_message(
            content=content,
            message_type=MessageType.INTERNAL_NOTE,
            author_id=author_id,
            author_name=author_name,
            is_internal=True,
        )

        return message

    # =========================================================================
    # SATISFACTION
    # =========================================================================

    def rate_satisfaction(
        self,
        ticket_id: UUID,
        rating: int,
        feedback: str = "",
    ) -> Optional[Ticket]:
        """Rate customer satisfaction for a ticket."""
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None

        ticket.rate_satisfaction(rating, feedback)
        return ticket

    # =========================================================================
    # TICKET QUERIES
    # =========================================================================

    def get_tickets(
        self,
        status: Optional[TicketStatus] = None,
        category: Optional[TicketCategory] = None,
        priority: Optional[TicketPriority] = None,
        assigned_to: Optional[UUID] = None,
        firm_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        include_closed: bool = False,
        sla_at_risk: bool = False,
        search_query: Optional[str] = None,
    ) -> List[Ticket]:
        """Get tickets with optional filters."""
        tickets = []

        for ticket in self._tickets.values():
            # Apply filters
            if status and ticket.status != status:
                continue
            if category and ticket.category != category:
                continue
            if priority and ticket.priority != priority:
                continue
            if assigned_to and ticket.assigned_to != assigned_to:
                continue
            if firm_id and ticket.firm_id != firm_id:
                continue
            if customer_id and ticket.customer_id != customer_id:
                continue
            if not include_closed and ticket.status == TicketStatus.CLOSED:
                continue
            if sla_at_risk and not (ticket.is_sla_response_at_risk or ticket.is_sla_resolution_at_risk):
                continue
            if search_query:
                query_lower = search_query.lower()
                if not (
                    query_lower in ticket.subject.lower() or
                    query_lower in ticket.description.lower() or
                    query_lower in ticket.ticket_number.lower() or
                    query_lower in ticket.customer_email.lower()
                ):
                    continue

            tickets.append(ticket)

        # Sort by priority and creation date
        priority_order = {
            TicketPriority.CRITICAL: 0,
            TicketPriority.URGENT: 1,
            TicketPriority.HIGH: 2,
            TicketPriority.NORMAL: 3,
            TicketPriority.LOW: 4,
        }
        tickets.sort(key=lambda t: (
            priority_order.get(t.priority, 3),
            t.created_at,
        ))

        return tickets

    def get_unassigned_tickets(self) -> List[Ticket]:
        """Get tickets without assignment."""
        return [
            t for t in self._tickets.values()
            if t.assigned_to is None and t.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
        ]

    def get_my_tickets(self, agent_id: UUID, include_closed: bool = False) -> List[Ticket]:
        """Get tickets assigned to a specific agent."""
        return self.get_tickets(
            assigned_to=agent_id,
            include_closed=include_closed,
        )

    def get_tickets_by_firm(self, firm_id: UUID, include_closed: bool = False) -> List[Ticket]:
        """Get tickets for a specific firm."""
        return self.get_tickets(
            firm_id=firm_id,
            include_closed=include_closed,
        )

    def get_sla_at_risk_tickets(self) -> List[Ticket]:
        """Get tickets at risk of SLA breach."""
        return self.get_tickets(sla_at_risk=True)

    def get_overdue_tickets(self) -> List[Ticket]:
        """Get tickets that have breached SLA."""
        return [
            t for t in self._tickets.values()
            if (t.sla_response_breached or t.sla_resolution_breached)
            and t.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]
        ]

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_ticket_summary(self) -> Dict[str, Any]:
        """Get summary statistics for tickets."""
        all_tickets = list(self._tickets.values())

        by_status = defaultdict(int)
        by_category = defaultdict(int)
        by_priority = defaultdict(int)

        total_response_time = 0
        total_resolution_time = 0
        response_count = 0
        resolution_count = 0
        total_satisfaction = 0
        satisfaction_count = 0

        sla_response_breached = 0
        sla_resolution_breached = 0
        sla_at_risk = 0
        unassigned = 0

        for ticket in all_tickets:
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

            if ticket.time_to_first_response:
                total_response_time += ticket.time_to_first_response
                response_count += 1
            if ticket.resolution_time:
                total_resolution_time += ticket.resolution_time
                resolution_count += 1
            if ticket.satisfaction_rating:
                total_satisfaction += ticket.satisfaction_rating
                satisfaction_count += 1

        return {
            "total": len(all_tickets),
            "open": len([t for t in all_tickets if t.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]]),
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

    def get_agent_performance(self, agent_id: UUID) -> Dict[str, Any]:
        """Get performance metrics for an agent."""
        agent_tickets = [t for t in self._tickets.values() if t.assigned_to == agent_id]

        resolved = [t for t in agent_tickets if t.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]]
        open_tickets = [t for t in agent_tickets if t.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]]

        total_response_time = 0
        total_resolution_time = 0
        total_satisfaction = 0
        response_count = 0
        resolution_count = 0
        satisfaction_count = 0
        sla_breached = 0

        for ticket in agent_tickets:
            if ticket.time_to_first_response:
                total_response_time += ticket.time_to_first_response
                response_count += 1
            if ticket.resolution_time:
                total_resolution_time += ticket.resolution_time
                resolution_count += 1
            if ticket.satisfaction_rating:
                total_satisfaction += ticket.satisfaction_rating
                satisfaction_count += 1
            if ticket.sla_response_breached or ticket.sla_resolution_breached:
                sla_breached += 1

        return {
            "total_assigned": len(agent_tickets),
            "open": len(open_tickets),
            "resolved": len(resolved),
            "sla_breached": sla_breached,
            "avg_response_time_hours": (total_response_time / response_count) if response_count else None,
            "avg_resolution_time_hours": (total_resolution_time / resolution_count) if resolution_count else None,
            "avg_satisfaction": (total_satisfaction / satisfaction_count) if satisfaction_count else None,
            "satisfaction_count": satisfaction_count,
        }


# Global service instance
ticket_service = TicketService()
