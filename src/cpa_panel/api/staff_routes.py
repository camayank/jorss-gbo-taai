"""
Staff Assignment API Routes

Lightweight staff assignment endpoints.

SCOPE BOUNDARIES:
- Assign/reassign: YES
- Filter by assignee: YES
- Bulk reassign: YES
- Staff list: YES

NOT IN SCOPE:
- Task management
- Workload dashboards
- Capacity planning
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List, Optional
import logging

from ..staff import StaffAssignmentService
from ..staff.assignment_service import get_assignment_service
from .common import format_success_response, format_error_response, get_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/staff", tags=["staff"])


@router.post("/members")
async def register_staff_member(
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Register a staff member.

    Required:
    - staff_id: Unique identifier
    - name: Display name
    - email: Email address

    Optional:
    - role: "preparer", "reviewer", or "partner" (default: preparer)
    """
    tenant_id = get_tenant_id(request)

    required = ["staff_id", "name", "email"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    service = get_assignment_service()
    member = service.register_staff(
        tenant_id=tenant_id,
        staff_id=body["staff_id"],
        name=body["name"],
        email=body["email"],
        role=body.get("role", "preparer"),
    )

    return format_success_response({
        "member": member.to_dict(),
    })


@router.get("/members")
async def list_staff_members(
    request: Request,
) -> Dict[str, Any]:
    """Get all staff members for the tenant."""
    tenant_id = get_tenant_id(request)

    service = get_assignment_service()
    members = service.get_staff(tenant_id)

    # Include assignment counts
    counts = service.get_assignment_counts(tenant_id)

    return format_success_response({
        "members": [
            {
                **m.to_dict(),
                "assignment_count": counts.get(m.staff_id, 0),
            }
            for m in members
        ],
        "total": len(members),
    })


@router.post("/assignments")
async def assign_return(
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Assign a return to a staff member.

    Required:
    - session_id: Return session ID
    - assign_to: Staff ID to assign to
    - assigned_by: Staff ID of person making assignment
    """
    tenant_id = get_tenant_id(request)

    required = ["session_id", "assign_to", "assigned_by"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    service = get_assignment_service()
    assignment = service.assign(
        session_id=body["session_id"],
        tenant_id=tenant_id,
        assign_to=body["assign_to"],
        assigned_by=body["assigned_by"],
    )

    return format_success_response({
        "assignment": assignment.to_dict(),
        "action": "reassigned" if assignment.previous_assignee else "assigned",
    })


@router.delete("/assignments/{session_id}")
async def unassign_return(
    request: Request,
    session_id: str,
    unassigned_by: str,
) -> Dict[str, Any]:
    """Remove assignment from a return."""
    service = get_assignment_service()
    removed = service.unassign(session_id, unassigned_by)

    if not removed:
        raise HTTPException(status_code=404, detail="No assignment found for this session")

    return format_success_response({
        "session_id": session_id,
        "unassigned": True,
    })


@router.get("/assignments/{session_id}")
async def get_assignment(
    request: Request,
    session_id: str,
) -> Dict[str, Any]:
    """Get assignment for a specific session."""
    tenant_id = get_tenant_id(request)

    service = get_assignment_service()
    assignment = service.get_assignment(session_id)

    if not assignment or assignment.tenant_id != tenant_id:
        return format_success_response({
            "session_id": session_id,
            "assigned": False,
            "assignment": None,
        })

    # Get assignee info
    assignee = service.get_staff_member(tenant_id, assignment.assigned_to)

    return format_success_response({
        "session_id": session_id,
        "assigned": True,
        "assignment": assignment.to_dict(),
        "assignee": assignee.to_dict() if assignee else None,
    })


@router.get("/assignments/by-staff/{staff_id}")
async def get_assignments_for_staff(
    request: Request,
    staff_id: str,
) -> Dict[str, Any]:
    """Get all assignments for a staff member."""
    tenant_id = get_tenant_id(request)

    service = get_assignment_service()
    assignments = service.get_assignments_for_staff(tenant_id, staff_id)

    return format_success_response({
        "staff_id": staff_id,
        "assignments": [a.to_dict() for a in assignments],
        "count": len(assignments),
    })


@router.post("/assignments/bulk")
async def bulk_reassign(
    request: Request,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Bulk reassign multiple returns.

    Required:
    - session_ids: List of session IDs
    - assign_to: Staff ID to assign to
    - assigned_by: Staff ID of person making assignment
    """
    tenant_id = get_tenant_id(request)

    required = ["session_ids", "assign_to", "assigned_by"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    session_ids = body["session_ids"]
    if not isinstance(session_ids, list) or len(session_ids) == 0:
        raise HTTPException(status_code=400, detail="session_ids must be a non-empty list")

    if len(session_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 sessions per bulk operation")

    service = get_assignment_service()
    assignments = service.bulk_reassign(
        session_ids=session_ids,
        tenant_id=tenant_id,
        assign_to=body["assign_to"],
        assigned_by=body["assigned_by"],
    )

    return format_success_response({
        "reassigned_count": len(assignments),
        "assign_to": body["assign_to"],
        "session_ids": session_ids,
    })


@router.get("/assignment-counts")
async def get_assignment_counts(
    request: Request,
) -> Dict[str, Any]:
    """Get assignment counts per staff member."""
    tenant_id = get_tenant_id(request)

    service = get_assignment_service()
    counts = service.get_assignment_counts(tenant_id)
    members = service.get_staff(tenant_id)

    # Build response with staff names
    results = []
    for member in members:
        results.append({
            "staff_id": member.staff_id,
            "name": member.name,
            "role": member.role,
            "assignment_count": counts.get(member.staff_id, 0),
        })

    # Sort by count descending
    results.sort(key=lambda x: x["assignment_count"], reverse=True)

    return format_success_response({
        "counts": results,
        "total_assigned": sum(counts.values()),
    })
