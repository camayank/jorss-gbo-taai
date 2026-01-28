"""
Task Management Routes

API endpoints for managing tasks.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from uuid import UUID
import logging

from ..tasks.task_service import task_service, TaskStatus, TaskPriority, TaskCategory

logger = logging.getLogger(__name__)

task_router = APIRouter(prefix="/tasks", tags=["Tasks"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateTaskRequest(BaseModel):
    """Request to create a new task."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field("custom", description="Task category")
    client_id: Optional[str] = None
    session_id: Optional[str] = None
    deadline_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    priority: str = Field("normal", description="low, normal, high, urgent")
    due_date: Optional[date] = None
    estimated_hours: Optional[float] = None
    tags: Optional[List[str]] = None
    checklist: Optional[List[str]] = None


class UpdateTaskRequest(BaseModel):
    """Request to update a task."""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    estimated_hours: Optional[float] = None
    tags: Optional[List[str]] = None


class AssignTaskRequest(BaseModel):
    """Request to assign a task."""
    assigned_to: str = Field(..., description="User ID to assign to")
    assigned_to_name: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    """Request to update task status."""
    status: str = Field(..., description="New status")


class BlockTaskRequest(BaseModel):
    """Request to block a task."""
    reason: str = Field(..., min_length=1, description="Reason for blocking")


class AddCommentRequest(BaseModel):
    """Request to add a comment."""
    content: str = Field(..., min_length=1)
    is_internal: bool = Field(True, description="Internal = not visible to client")


class AddChecklistItemRequest(BaseModel):
    """Request to add a checklist item."""
    text: str = Field(..., min_length=1)


class CreateFromTemplateRequest(BaseModel):
    """Request to create task from template."""
    template_id: str = Field(..., description="Template ID")
    client_id: Optional[str] = None
    session_id: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None


class CreateTemplateRequest(BaseModel):
    """Request to create a task template."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field("custom")
    default_priority: str = Field("normal")
    default_due_days: Optional[int] = Field(None, ge=1, le=365)
    checklist_template: Optional[List[str]] = None
    tags: Optional[List[str]] = None


# =============================================================================
# TASK CRUD
# =============================================================================

@task_router.post("")
async def create_task(
    request: CreateTaskRequest,
    firm_id: str = Query(..., description="Firm ID"),
    user_id: Optional[str] = Query(None, description="Creating user ID"),
    user_name: Optional[str] = Query(None, description="Creating user name"),
):
    """Create a new task."""
    try:
        category = TaskCategory(request.category)
    except ValueError:
        raise HTTPException(400, f"Invalid category: {request.category}")

    try:
        priority = TaskPriority(request.priority)
    except ValueError:
        raise HTTPException(400, f"Invalid priority: {request.priority}")

    task = task_service.create_task(
        firm_id=UUID(firm_id),
        title=request.title,
        description=request.description,
        category=category,
        client_id=UUID(request.client_id) if request.client_id else None,
        session_id=request.session_id,
        deadline_id=UUID(request.deadline_id) if request.deadline_id else None,
        parent_task_id=UUID(request.parent_task_id) if request.parent_task_id else None,
        assigned_to=UUID(request.assigned_to) if request.assigned_to else None,
        assigned_to_name=request.assigned_to_name,
        priority=priority,
        due_date=request.due_date,
        estimated_hours=request.estimated_hours,
        tags=request.tags,
        checklist=request.checklist,
        created_by=UUID(user_id) if user_id else None,
        created_by_name=user_name,
    )

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.post("/from-template")
async def create_task_from_template(
    request: CreateFromTemplateRequest,
    firm_id: str = Query(..., description="Firm ID"),
    user_id: Optional[str] = Query(None, description="Creating user ID"),
):
    """Create a task from a template."""
    task = task_service.create_from_template(
        template_id=UUID(request.template_id),
        firm_id=UUID(firm_id),
        client_id=UUID(request.client_id) if request.client_id else None,
        session_id=request.session_id,
        assigned_to=UUID(request.assigned_to) if request.assigned_to else None,
        due_date=request.due_date,
        created_by=UUID(user_id) if user_id else None,
    )

    if not task:
        raise HTTPException(404, "Template not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.get("/{task_id}")
async def get_task(task_id: str):
    """Get a specific task by ID."""
    task = task_service.get_task(UUID(task_id))
    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.put("/{task_id}")
async def update_task(task_id: str, request: UpdateTaskRequest):
    """Update a task."""
    category = None
    priority = None

    if request.category:
        try:
            category = TaskCategory(request.category)
        except ValueError:
            raise HTTPException(400, f"Invalid category: {request.category}")

    if request.priority:
        try:
            priority = TaskPriority(request.priority)
        except ValueError:
            raise HTTPException(400, f"Invalid priority: {request.priority}")

    task = task_service.update_task(
        task_id=UUID(task_id),
        title=request.title,
        description=request.description,
        category=category,
        priority=priority,
        due_date=request.due_date,
        estimated_hours=request.estimated_hours,
        tags=request.tags,
    )

    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a task."""
    success = task_service.delete_task(UUID(task_id))
    if not success:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "message": "Task deleted",
    }


# =============================================================================
# ASSIGNMENT
# =============================================================================

@task_router.post("/{task_id}/assign")
async def assign_task(task_id: str, request: AssignTaskRequest):
    """Assign a task to a staff member."""
    task = task_service.assign_task(
        task_id=UUID(task_id),
        assigned_to=UUID(request.assigned_to),
        assigned_to_name=request.assigned_to_name,
    )

    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.post("/{task_id}/unassign")
async def unassign_task(task_id: str):
    """Remove assignment from a task."""
    task = task_service.unassign_task(UUID(task_id))
    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.post("/{task_id}/reassign")
async def reassign_task(
    task_id: str,
    request: AssignTaskRequest,
    user_id: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
):
    """Reassign a task to a different staff member."""
    task = task_service.reassign_task(
        task_id=UUID(task_id),
        new_assignee=UUID(request.assigned_to),
        new_assignee_name=request.assigned_to_name,
        reassigned_by=UUID(user_id) if user_id else None,
        reassigned_by_name=user_name,
    )

    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


# =============================================================================
# STATUS MANAGEMENT
# =============================================================================

@task_router.post("/{task_id}/status")
async def update_status(
    task_id: str,
    request: UpdateStatusRequest,
    user_id: Optional[str] = Query(None),
):
    """Update task status."""
    try:
        status = TaskStatus(request.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {request.status}")

    task = task_service.update_status(
        task_id=UUID(task_id),
        new_status=status,
        updated_by=UUID(user_id) if user_id else None,
    )

    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.post("/{task_id}/start")
async def start_task(task_id: str, user_id: Optional[str] = Query(None)):
    """Mark task as in progress."""
    task = task_service.start_task(UUID(task_id), UUID(user_id) if user_id else None)
    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.post("/{task_id}/complete")
async def complete_task(task_id: str, user_id: Optional[str] = Query(None)):
    """Mark task as completed."""
    task = task_service.complete_task(UUID(task_id), UUID(user_id) if user_id else None)
    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.post("/{task_id}/block")
async def block_task(
    task_id: str,
    request: BlockTaskRequest,
    user_id: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
):
    """Mark task as blocked."""
    task = task_service.block_task(
        task_id=UUID(task_id),
        reason=request.reason,
        blocked_by=UUID(user_id) if user_id else None,
        blocked_by_name=user_name,
    )

    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


@task_router.post("/{task_id}/unblock")
async def unblock_task(
    task_id: str,
    user_id: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
):
    """Unblock a task."""
    task = task_service.unblock_task(
        task_id=UUID(task_id),
        unblocked_by=UUID(user_id) if user_id else None,
        unblocked_by_name=user_name,
    )

    if not task:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "task": task.to_dict(),
    }


# =============================================================================
# COMMENTS
# =============================================================================

@task_router.post("/{task_id}/comments")
async def add_comment(
    task_id: str,
    request: AddCommentRequest,
    user_id: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
):
    """Add a comment to a task."""
    comment = task_service.add_comment(
        task_id=UUID(task_id),
        content=request.content,
        author_id=UUID(user_id) if user_id else None,
        author_name=user_name,
        is_internal=request.is_internal,
    )

    if not comment:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "comment": comment.to_dict(),
    }


@task_router.delete("/{task_id}/comments/{comment_id}")
async def delete_comment(task_id: str, comment_id: str):
    """Delete a comment from a task."""
    success = task_service.delete_comment(UUID(task_id), UUID(comment_id))
    if not success:
        raise HTTPException(404, "Task or comment not found")

    return {
        "success": True,
        "message": "Comment deleted",
    }


# =============================================================================
# CHECKLIST
# =============================================================================

@task_router.post("/{task_id}/checklist")
async def add_checklist_item(task_id: str, request: AddChecklistItemRequest):
    """Add an item to task checklist."""
    item = task_service.add_checklist_item(UUID(task_id), request.text)
    if not item:
        raise HTTPException(404, "Task not found")

    return {
        "success": True,
        "item": item,
    }


@task_router.post("/{task_id}/checklist/{item_id}/toggle")
async def toggle_checklist_item(task_id: str, item_id: str):
    """Toggle a checklist item."""
    success = task_service.toggle_checklist_item(UUID(task_id), item_id)
    if not success:
        raise HTTPException(404, "Task or checklist item not found")

    return {
        "success": True,
        "message": "Checklist item toggled",
    }


@task_router.delete("/{task_id}/checklist/{item_id}")
async def delete_checklist_item(task_id: str, item_id: str):
    """Delete a checklist item."""
    success = task_service.delete_checklist_item(UUID(task_id), item_id)
    if not success:
        raise HTTPException(404, "Task or checklist item not found")

    return {
        "success": True,
        "message": "Checklist item deleted",
    }


# =============================================================================
# TASK QUERIES
# =============================================================================

@task_router.get("")
async def list_tasks(
    firm_id: str = Query(..., description="Firm ID"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    include_completed: bool = Query(False),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
):
    """List tasks with optional filters."""
    status_filter = TaskStatus(status) if status else None
    category_filter = TaskCategory(category) if category else None
    priority_filter = TaskPriority(priority) if priority else None
    tag_list = tags.split(",") if tags else None

    tasks = task_service.get_tasks_for_firm(
        firm_id=UUID(firm_id),
        status=status_filter,
        category=category_filter,
        priority=priority_filter,
        assigned_to=UUID(assigned_to) if assigned_to else None,
        client_id=UUID(client_id) if client_id else None,
        session_id=session_id,
        include_completed=include_completed,
        tags=tag_list,
    )

    return {
        "success": True,
        "tasks": [t.to_dict() for t in tasks],
        "total": len(tasks),
    }


@task_router.get("/my-tasks")
async def get_my_tasks(
    firm_id: str = Query(..., description="Firm ID"),
    user_id: str = Query(..., description="User ID"),
    include_completed: bool = Query(False),
):
    """Get tasks assigned to the current user."""
    tasks = task_service.get_my_tasks(
        firm_id=UUID(firm_id),
        user_id=UUID(user_id),
        include_completed=include_completed,
    )

    return {
        "success": True,
        "tasks": [t.to_dict() for t in tasks],
        "total": len(tasks),
    }


@task_router.get("/unassigned")
async def get_unassigned_tasks(firm_id: str = Query(..., description="Firm ID")):
    """Get tasks without assignment."""
    tasks = task_service.get_unassigned_tasks(UUID(firm_id))

    return {
        "success": True,
        "tasks": [t.to_dict() for t in tasks],
        "total": len(tasks),
    }


@task_router.get("/overdue")
async def get_overdue_tasks(firm_id: str = Query(..., description="Firm ID")):
    """Get all overdue tasks."""
    tasks = task_service.get_overdue_tasks(UUID(firm_id))

    return {
        "success": True,
        "tasks": [t.to_dict() for t in tasks],
        "total": len(tasks),
    }


@task_router.get("/client/{client_id}")
async def get_client_tasks(
    client_id: str,
    firm_id: str = Query(..., description="Firm ID"),
    include_completed: bool = Query(False),
):
    """Get all tasks for a client."""
    tasks = task_service.get_tasks_for_client(
        firm_id=UUID(firm_id),
        client_id=UUID(client_id),
        include_completed=include_completed,
    )

    return {
        "success": True,
        "tasks": [t.to_dict() for t in tasks],
        "total": len(tasks),
    }


@task_router.get("/session/{session_id}")
async def get_session_tasks(
    session_id: str,
    include_completed: bool = Query(False),
):
    """Get all tasks for a tax return session."""
    tasks = task_service.get_tasks_for_session(session_id, include_completed)

    return {
        "success": True,
        "tasks": [t.to_dict() for t in tasks],
        "total": len(tasks),
    }


@task_router.get("/{task_id}/subtasks")
async def get_subtasks(task_id: str):
    """Get subtasks of a parent task."""
    tasks = task_service.get_subtasks(UUID(task_id))

    return {
        "success": True,
        "tasks": [t.to_dict() for t in tasks],
        "total": len(tasks),
    }


# =============================================================================
# TEMPLATES
# =============================================================================

@task_router.get("/templates")
async def get_templates(
    firm_id: Optional[str] = Query(None, description="Firm ID for custom templates"),
    category: Optional[str] = Query(None),
):
    """Get available task templates."""
    category_filter = TaskCategory(category) if category else None

    templates = task_service.get_templates(
        firm_id=UUID(firm_id) if firm_id else None,
        category=category_filter,
    )

    return {
        "success": True,
        "templates": [t.to_dict() for t in templates],
        "total": len(templates),
    }


@task_router.post("/templates")
async def create_template(
    request: CreateTemplateRequest,
    firm_id: str = Query(..., description="Firm ID"),
):
    """Create a custom task template."""
    try:
        category = TaskCategory(request.category)
    except ValueError:
        raise HTTPException(400, f"Invalid category: {request.category}")

    try:
        priority = TaskPriority(request.default_priority)
    except ValueError:
        raise HTTPException(400, f"Invalid priority: {request.default_priority}")

    template = task_service.create_template(
        firm_id=UUID(firm_id),
        name=request.name,
        description=request.description,
        category=category,
        default_priority=priority,
        default_due_days=request.default_due_days,
        checklist_template=request.checklist_template,
        tags=request.tags,
    )

    return {
        "success": True,
        "template": template.to_dict(),
    }


# =============================================================================
# ANALYTICS & VIEWS
# =============================================================================

@task_router.get("/summary")
async def get_task_summary(firm_id: str = Query(..., description="Firm ID")):
    """Get summary statistics for tasks."""
    summary = task_service.get_task_summary(UUID(firm_id))

    return {
        "success": True,
        **summary,
    }


@task_router.get("/workload")
async def get_team_workload(firm_id: str = Query(..., description="Firm ID")):
    """Get workload distribution across team members."""
    workload = task_service.get_team_workload(UUID(firm_id))

    return {
        "success": True,
        "workload": workload,
    }


@task_router.get("/kanban")
async def get_kanban_view(firm_id: str = Query(..., description="Firm ID")):
    """Get tasks organized for kanban board display."""
    kanban = task_service.get_kanban_view(UUID(firm_id))

    return {
        "success": True,
        "columns": kanban,
    }


# =============================================================================
# REFERENCE DATA
# =============================================================================

@task_router.get("/categories")
async def get_categories():
    """Get list of task categories."""
    return {
        "success": True,
        "categories": [
            {"value": c.value, "label": c.value.replace("_", " ").title()}
            for c in TaskCategory
        ],
    }


@task_router.get("/statuses")
async def get_statuses():
    """Get list of task statuses."""
    return {
        "success": True,
        "statuses": [
            {"value": s.value, "label": s.value.replace("_", " ").title()}
            for s in TaskStatus
        ],
    }


@task_router.get("/priorities")
async def get_priorities():
    """Get list of task priorities."""
    return {
        "success": True,
        "priorities": [
            {"value": p.value, "label": p.value.title()}
            for p in TaskPriority
        ],
    }
