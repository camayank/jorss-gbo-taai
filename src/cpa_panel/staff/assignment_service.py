"""
Staff Assignment Service

Simple assignment of returns to staff members.

SCOPE BOUNDARIES (ENFORCED):
- Assign: YES
- Reassign: YES
- Filter by assignee: YES
- Bulk reassign: YES
- Assignment history: YES (simple)

NOT IN SCOPE:
- Task management
- Workload tracking
- Capacity planning
- Performance metrics
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class StaffMember:
    """A staff member who can be assigned returns."""
    staff_id: str
    name: str
    email: str
    role: str  # "preparer", "reviewer", "partner"
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "staff_id": self.staff_id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
        }


@dataclass
class StaffAssignment:
    """Assignment of a return to a staff member."""
    session_id: str
    tenant_id: str
    assigned_to: str  # staff_id
    assigned_by: str  # staff_id of who made assignment
    assigned_at: datetime
    previous_assignee: Optional[str] = None  # For reassignment tracking

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "assigned_to": self.assigned_to,
            "assigned_by": self.assigned_by,
            "assigned_at": self.assigned_at.isoformat(),
            "previous_assignee": self.previous_assignee,
        }


class StaffAssignmentService:
    """
    Service for managing staff assignments.

    Lightweight. No tasks. No workload tracking.
    Just: who is assigned to what.
    """

    def __init__(self):
        """Initialize assignment service."""
        # In-memory storage (replace with DB in production)
        self._assignments: Dict[str, StaffAssignment] = {}  # session_id -> assignment
        self._staff: Dict[str, Dict[str, StaffMember]] = {}  # tenant_id -> {staff_id -> member}

    def register_staff(
        self,
        tenant_id: str,
        staff_id: str,
        name: str,
        email: str,
        role: str = "preparer",
    ) -> StaffMember:
        """Register a staff member for a tenant."""
        if tenant_id not in self._staff:
            self._staff[tenant_id] = {}

        member = StaffMember(
            staff_id=staff_id,
            name=name,
            email=email,
            role=role,
        )
        self._staff[tenant_id][staff_id] = member

        logger.info(f"Registered staff {staff_id} ({name}) for tenant {tenant_id}")
        return member

    def get_staff(self, tenant_id: str) -> List[StaffMember]:
        """Get all staff members for a tenant."""
        return list(self._staff.get(tenant_id, {}).values())

    def get_staff_member(self, tenant_id: str, staff_id: str) -> Optional[StaffMember]:
        """Get a specific staff member."""
        return self._staff.get(tenant_id, {}).get(staff_id)

    def assign(
        self,
        session_id: str,
        tenant_id: str,
        assign_to: str,
        assigned_by: str,
    ) -> StaffAssignment:
        """
        Assign a return to a staff member.

        Args:
            session_id: Tax return session ID
            tenant_id: Tenant identifier
            assign_to: Staff ID to assign to
            assigned_by: Staff ID of person making assignment

        Returns:
            StaffAssignment record
        """
        # Check for existing assignment (reassignment case)
        previous_assignee = None
        if session_id in self._assignments:
            previous_assignee = self._assignments[session_id].assigned_to

        assignment = StaffAssignment(
            session_id=session_id,
            tenant_id=tenant_id,
            assigned_to=assign_to,
            assigned_by=assigned_by,
            assigned_at=datetime.utcnow(),
            previous_assignee=previous_assignee,
        )

        self._assignments[session_id] = assignment

        action = "reassigned" if previous_assignee else "assigned"
        logger.info(f"Return {session_id} {action} to {assign_to} by {assigned_by}")

        return assignment

    def unassign(self, session_id: str, unassigned_by: str) -> bool:
        """
        Remove assignment from a return.

        Args:
            session_id: Tax return session ID
            unassigned_by: Staff ID of person removing assignment

        Returns:
            True if was assigned and now unassigned
        """
        if session_id in self._assignments:
            del self._assignments[session_id]
            logger.info(f"Return {session_id} unassigned by {unassigned_by}")
            return True
        return False

    def get_assignment(self, session_id: str) -> Optional[StaffAssignment]:
        """Get assignment for a session."""
        return self._assignments.get(session_id)

    def get_assignments_for_staff(
        self,
        tenant_id: str,
        staff_id: str,
    ) -> List[StaffAssignment]:
        """Get all assignments for a staff member."""
        return [
            a for a in self._assignments.values()
            if a.tenant_id == tenant_id and a.assigned_to == staff_id
        ]

    def get_unassigned_sessions(
        self,
        tenant_id: str,
        session_ids: List[str],
    ) -> List[str]:
        """Get session IDs that are not assigned to anyone."""
        return [
            sid for sid in session_ids
            if sid not in self._assignments or self._assignments[sid].tenant_id != tenant_id
        ]

    def bulk_reassign(
        self,
        session_ids: List[str],
        tenant_id: str,
        assign_to: str,
        assigned_by: str,
    ) -> List[StaffAssignment]:
        """
        Bulk reassign multiple returns to a staff member.

        Args:
            session_ids: List of session IDs to reassign
            tenant_id: Tenant identifier
            assign_to: Staff ID to assign to
            assigned_by: Staff ID of person making assignment

        Returns:
            List of StaffAssignment records
        """
        assignments = []
        for session_id in session_ids:
            assignment = self.assign(
                session_id=session_id,
                tenant_id=tenant_id,
                assign_to=assign_to,
                assigned_by=assigned_by,
            )
            assignments.append(assignment)

        logger.info(f"Bulk reassigned {len(assignments)} returns to {assign_to}")
        return assignments

    def get_assignment_counts(self, tenant_id: str) -> Dict[str, int]:
        """
        Get count of assignments per staff member.

        Returns dict of staff_id -> count.
        """
        counts: Dict[str, int] = {}

        for assignment in self._assignments.values():
            if assignment.tenant_id == tenant_id:
                staff_id = assignment.assigned_to
                counts[staff_id] = counts.get(staff_id, 0) + 1

        return counts


# Singleton instance
_assignment_service: Optional[StaffAssignmentService] = None


def get_assignment_service() -> StaffAssignmentService:
    """Get the global staff assignment service instance."""
    global _assignment_service
    if _assignment_service is None:
        _assignment_service = StaffAssignmentService()
    return _assignment_service
