"""
Staff Assignment Module

Lightweight staff assignment for CPA firms.

SCOPE BOUNDARIES (ENFORCED):
- Assign return to staff: YES
- Reassign return: YES
- Filter by assignee: YES
- Bulk reassignment: YES

NOT IN SCOPE (DO NOT ADD):
- Task management
- Subtasks
- Kanban boards
- Time tracking
- Performance metrics
- Workload capacity planning
"""

from .assignment_service import (
    StaffAssignmentService,
    StaffAssignment,
)

__all__ = [
    "StaffAssignmentService",
    "StaffAssignment",
]
