"""
Workflow Management Routes - Return workflow and task management.

Provides:
- Workflow status overview
- Task management
- Review queue management
- Deadline tracking

All routes use database-backed queries.
"""

import json
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.rbac import (
    get_current_user,
    get_current_firm,
    TenantContext,
    require_permission,
)
from ..models.user import UserPermission
from database.async_engine import get_async_session


router = APIRouter(tags=["Workflow Management"])
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND MODELS
# =============================================================================

class WorkflowStage(str, Enum):
    """Workflow stages for returns."""
    INTAKE = "intake"
    DOCUMENT_COLLECTION = "document_collection"
    PREPARATION = "preparation"
    REVIEW = "review"
    CLIENT_REVIEW = "client_review"
    APPROVAL = "approval"
    FILING = "filing"
    COMPLETE = "complete"


class TaskPriority(str, Enum):
    """Task priority levels."""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskStatus(str, Enum):
    """Task status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkflowItem(BaseModel):
    """Workflow item for queue view."""
    return_id: str
    client_id: str
    client_name: str
    return_type: str
    tax_year: int
    stage: str
    assigned_to: Optional[str]
    assigned_name: Optional[str]
    priority: str
    deadline: Optional[datetime]
    days_in_stage: int
    blockers: List[str]
    created_at: datetime


class TaskItem(BaseModel):
    """Task item."""
    task_id: str
    title: str
    description: Optional[str]
    status: str
    priority: str
    assigned_to: Optional[str]
    assigned_name: Optional[str]
    related_to: Optional[dict]  # {type: "return", id: "xxx"}
    due_date: Optional[datetime]
    created_at: datetime


class DeadlineItem(BaseModel):
    """Deadline tracking item."""
    deadline_id: str
    deadline_type: str
    client_id: str
    client_name: str
    return_id: Optional[str]
    due_date: datetime
    days_until: int
    status: str
    assigned_to: Optional[str]


# =============================================================================
# WORKFLOW OVERVIEW ROUTES
# =============================================================================

@router.get("/workflow/overview")
@require_permission(UserPermission.VIEW_RETURNS)
async def get_workflow_overview(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get workflow pipeline overview."""
    # Get counts by stage
    stage_query = text("""
        SELECT r.workflow_stage,
               COUNT(*) as count,
               EXTRACT(DAY FROM NOW() - MIN(r.stage_entered_at)) as oldest_days
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        GROUP BY r.workflow_stage
    """)
    stage_result = await session.execute(stage_query, {"firm_id": firm_id})
    stage_rows = stage_result.fetchall()

    stages = []
    total_active = 0
    max_count_stage = None
    max_count = 0

    for row in stage_rows:
        stage_name = row[0] or "intake"
        count = row[1] or 0
        oldest_days = int(row[2]) if row[2] else None

        stages.append({
            "stage": stage_name,
            "count": count,
            "oldest_days": oldest_days,
        })

        if stage_name != "complete":
            total_active += count
            if count > max_count:
                max_count = count
                max_count_stage = stage_name

    # Get completed this month
    completed_query = text("""
        SELECT COUNT(*) FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.workflow_stage = 'complete'
        AND r.completed_at >= DATE_TRUNC('month', NOW())
    """)
    completed_result = await session.execute(completed_query, {"firm_id": firm_id})
    completed_this_month = completed_result.fetchone()[0] or 0

    # Get average completion days
    avg_query = text("""
        SELECT AVG(EXTRACT(DAY FROM r.completed_at - r.created_at))
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE u.firm_id = :firm_id
        AND r.workflow_stage = 'complete'
        AND r.completed_at >= NOW() - INTERVAL '90 days'
    """)
    avg_result = await session.execute(avg_query, {"firm_id": firm_id})
    avg_completion = avg_result.fetchone()[0]
    avg_completion_days = int(avg_completion) if avg_completion else 0

    return {
        "stages": stages,
        "total_active": total_active,
        "completed_this_month": completed_this_month,
        "avg_completion_days": avg_completion_days,
        "bottleneck_stage": max_count_stage,
    }


@router.get("/workflow/queue", response_model=List[WorkflowItem])
@require_permission(UserPermission.VIEW_RETURNS)
async def get_workflow_queue(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    stage: Optional[str] = Query(None, description="Filter by stage"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    has_blockers: Optional[bool] = Query(None, description="Filter items with blockers"),
    sort_by: str = Query("deadline", description="Sort field"),
    sort_order: str = Query("asc", description="Sort order"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get workflow queue with filtering.

    Returns list of returns in the workflow pipeline.
    """
    # Build conditions
    conditions = ["u.firm_id = :firm_id", "r.workflow_stage != 'complete'"]
    params = {"firm_id": firm_id, "limit": limit, "offset": offset}

    if stage:
        conditions.append("r.workflow_stage = :stage")
        params["stage"] = stage

    if assigned_to:
        conditions.append("r.preparer_id = :assigned_to")
        params["assigned_to"] = assigned_to

    if priority:
        conditions.append("r.priority = :priority")
        params["priority"] = priority

    if has_blockers is not None:
        if has_blockers:
            conditions.append("r.blockers IS NOT NULL AND jsonb_array_length(r.blockers) > 0")
        else:
            conditions.append("(r.blockers IS NULL OR jsonb_array_length(r.blockers) = 0)")

    where_clause = " AND ".join(conditions)

    # Validate sort field
    valid_sort_fields = {"deadline", "created_at", "priority", "stage_entered_at"}
    if sort_by not in valid_sort_fields:
        sort_by = "deadline"
    sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

    query = text(f"""
        SELECT r.return_id, r.client_id, c.first_name || ' ' || c.last_name as client_name,
               r.return_type, r.tax_year, r.workflow_stage, r.preparer_id,
               p.first_name || ' ' || p.last_name as preparer_name,
               r.priority, r.deadline, r.stage_entered_at, r.blockers, r.created_at
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        LEFT JOIN clients c ON r.client_id = c.client_id
        LEFT JOIN users p ON r.preparer_id = p.user_id
        WHERE {where_clause}
        ORDER BY r.{sort_by} {sort_dir} NULLS LAST
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    items = []
    for row in rows:
        # Parse dates
        def parse_dt(val):
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            return datetime.fromisoformat(val.replace('Z', '+00:00'))

        stage_entered = parse_dt(row[10])
        days_in_stage = (datetime.utcnow() - stage_entered).days if stage_entered else 0
        blockers = json.loads(row[11]) if row[11] else []

        items.append(WorkflowItem(
            return_id=str(row[0]),
            client_id=str(row[1]) if row[1] else "",
            client_name=row[2] or "Unknown",
            return_type=row[3] or "",
            tax_year=row[4] or datetime.utcnow().year,
            stage=row[5] or "intake",
            assigned_to=str(row[6]) if row[6] else None,
            assigned_name=row[7],
            priority=row[8] or "normal",
            deadline=parse_dt(row[9]),
            days_in_stage=days_in_stage,
            blockers=blockers,
            created_at=parse_dt(row[12]) or datetime.utcnow(),
        ))

    return items


@router.get("/workflow/item/{return_id}")
@require_permission(UserPermission.VIEW_RETURNS)
async def get_workflow_item_details(
    return_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Get detailed workflow status for a return."""
    query = text("""
        SELECT r.return_id, r.client_id, c.first_name || ' ' || c.last_name as client_name,
               r.return_type, r.tax_year, r.workflow_stage, r.stage_history,
               r.preparer_id, p.first_name || ' ' || p.last_name as preparer_name,
               r.deadline, r.priority, r.blockers, r.checklist, r.notes
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        LEFT JOIN clients c ON r.client_id = c.client_id
        LEFT JOIN users p ON r.preparer_id = p.user_id
        WHERE r.return_id = :return_id AND u.firm_id = :firm_id
    """)

    result = await session.execute(query, {"return_id": return_id, "firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Return not found",
        )

    # Parse dates
    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    stage_history = json.loads(row[6]) if row[6] else []
    blockers = json.loads(row[11]) if row[11] else []
    checklist = json.loads(row[12]) if row[12] else []
    deadline = parse_dt(row[9])

    return {
        "return_id": str(row[0]),
        "client_id": str(row[1]) if row[1] else None,
        "client_name": row[2] or "Unknown",
        "return_type": row[3] or "",
        "tax_year": row[4] or datetime.utcnow().year,
        "current_stage": row[5] or "intake",
        "stage_history": stage_history,
        "assigned_to": str(row[7]) if row[7] else None,
        "assigned_name": row[8],
        "deadline": deadline.isoformat() if deadline else None,
        "priority": row[10] or "normal",
        "blockers": blockers,
        "checklist": checklist,
        "notes": row[13],
    }


# =============================================================================
# WORKFLOW ACTIONS
# =============================================================================

@router.post("/workflow/{return_id}/advance")
@require_permission(UserPermission.EDIT_RETURNS)
async def advance_workflow_stage(
    return_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    notes: Optional[str] = Query(None, description="Notes for advancement"),
    session: AsyncSession = Depends(get_async_session),
):
    """Advance a return to the next workflow stage."""
    # Define stage progression
    stage_order = ["intake", "document_collection", "preparation", "review", "client_review", "approval", "filing", "complete"]

    # Get current stage
    query = text("""
        SELECT r.workflow_stage, r.stage_history FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE r.return_id = :return_id AND u.firm_id = :firm_id
    """)
    result = await session.execute(query, {"return_id": return_id, "firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    current_stage = row[0] or "intake"
    stage_history = json.loads(row[1]) if row[1] else []

    if current_stage == "complete":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Return is already complete")

    # Determine next stage
    current_idx = stage_order.index(current_stage) if current_stage in stage_order else 0
    next_stage = stage_order[current_idx + 1] if current_idx < len(stage_order) - 1 else "complete"

    # Update stage history
    now = datetime.utcnow()
    stage_history.append({
        "stage": current_stage,
        "exited_at": now.isoformat(),
        "user": user.user_id,
        "notes": notes,
    })

    # Update return
    update_query = text("""
        UPDATE returns SET
            workflow_stage = :new_stage,
            stage_entered_at = :entered_at,
            stage_history = :history,
            completed_at = CASE WHEN :new_stage = 'complete' THEN :entered_at ELSE completed_at END,
            updated_at = :entered_at
        WHERE return_id = :return_id
    """)
    await session.execute(update_query, {
        "return_id": return_id,
        "new_stage": next_stage,
        "entered_at": now.isoformat(),
        "history": json.dumps(stage_history),
    })
    await session.commit()

    logger.info(f"Return {return_id} advanced from {current_stage} to {next_stage} by {user.email}")

    return {
        "status": "success",
        "return_id": return_id,
        "previous_stage": current_stage,
        "new_stage": next_stage,
        "advanced_by": user.user_id,
        "advanced_at": now.isoformat(),
    }


@router.post("/workflow/{return_id}/return-to-stage")
@require_permission(UserPermission.EDIT_RETURNS)
async def return_to_previous_stage(
    return_id: str,
    target_stage: str = Query(..., description="Stage to return to"),
    reason: str = Query(..., description="Reason for returning"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Return a return to a previous stage."""
    # Validate stage
    try:
        WorkflowStage(target_stage)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage. Must be one of: {[s.value for s in WorkflowStage]}",
        )

    # Get current stage
    query = text("""
        SELECT r.workflow_stage, r.stage_history FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE r.return_id = :return_id AND u.firm_id = :firm_id
    """)
    result = await session.execute(query, {"return_id": return_id, "firm_id": firm_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    current_stage = row[0] or "intake"
    stage_history = json.loads(row[1]) if row[1] else []

    # Update stage history
    now = datetime.utcnow()
    stage_history.append({
        "stage": current_stage,
        "exited_at": now.isoformat(),
        "user": user.user_id,
        "action": "returned",
        "reason": reason,
        "target_stage": target_stage,
    })

    # Update return
    update_query = text("""
        UPDATE returns SET
            workflow_stage = :new_stage,
            stage_entered_at = :entered_at,
            stage_history = :history,
            updated_at = :entered_at
        WHERE return_id = :return_id
    """)
    await session.execute(update_query, {
        "return_id": return_id,
        "new_stage": target_stage,
        "entered_at": now.isoformat(),
        "history": json.dumps(stage_history),
    })
    await session.commit()

    logger.info(f"Return {return_id} returned from {current_stage} to {target_stage} by {user.email}")

    return {
        "status": "success",
        "return_id": return_id,
        "previous_stage": current_stage,
        "new_stage": target_stage,
        "reason": reason,
        "returned_by": user.user_id,
    }


@router.post("/workflow/{return_id}/assign")
@require_permission(UserPermission.MANAGE_RETURNS)
async def assign_return(
    return_id: str,
    user_id: str = Query(..., description="User ID to assign to"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Assign or reassign a return to a team member."""
    # Verify target user belongs to firm
    user_check = text("SELECT user_id FROM users WHERE user_id = :user_id AND firm_id = :firm_id AND is_active = true")
    user_result = await session.execute(user_check, {"user_id": user_id, "firm_id": firm_id})
    if not user_result.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    # Update return
    update_query = text("""
        UPDATE returns SET preparer_id = :preparer_id, updated_at = :updated_at
        WHERE return_id = :return_id
        AND EXISTS (SELECT 1 FROM users u WHERE u.user_id = returns.preparer_id AND u.firm_id = :firm_id)
    """)
    result = await session.execute(update_query, {
        "return_id": return_id,
        "preparer_id": user_id,
        "firm_id": firm_id,
        "updated_at": datetime.utcnow().isoformat(),
    })

    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    await session.commit()
    logger.info(f"Return {return_id} assigned to {user_id} by {user.email}")

    return {
        "status": "success",
        "return_id": return_id,
        "assigned_to": user_id,
        "assigned_by": user.user_id,
    }


@router.post("/workflow/{return_id}/priority")
@require_permission(UserPermission.MANAGE_RETURNS)
async def update_return_priority(
    return_id: str,
    priority: str = Query(..., description="New priority level"),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Update return priority."""
    # Validate priority
    try:
        TaskPriority(priority)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority. Must be one of: {[p.value for p in TaskPriority]}",
        )

    # Update return
    update_query = text("""
        UPDATE returns SET priority = :priority, updated_at = :updated_at
        WHERE return_id = :return_id
        AND EXISTS (SELECT 1 FROM users u WHERE u.user_id = returns.preparer_id AND u.firm_id = :firm_id)
    """)
    result = await session.execute(update_query, {
        "return_id": return_id,
        "priority": priority,
        "firm_id": firm_id,
        "updated_at": datetime.utcnow().isoformat(),
    })

    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    await session.commit()
    logger.info(f"Return {return_id} priority set to {priority} by {user.email}")

    return {
        "status": "success",
        "return_id": return_id,
        "new_priority": priority,
    }


# =============================================================================
# TASK MANAGEMENT ROUTES
# =============================================================================

@router.get("/tasks", response_model=List[TaskItem])
@require_permission(UserPermission.VIEW_RETURNS)
async def list_tasks(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    status_filter: Optional[str] = Query(None, alias="status"),
    assigned_to: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    due_before: Optional[str] = Query(None, description="Due before date (ISO)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List tasks with filtering."""
    # Build conditions
    conditions = ["t.firm_id = :firm_id"]
    params = {"firm_id": firm_id, "limit": limit, "offset": offset}

    if status_filter:
        conditions.append("t.status = :status")
        params["status"] = status_filter

    if assigned_to:
        conditions.append("t.assigned_to = :assigned_to")
        params["assigned_to"] = assigned_to

    if priority:
        conditions.append("t.priority = :priority")
        params["priority"] = priority

    if due_before:
        conditions.append("t.due_date <= :due_before")
        params["due_before"] = due_before

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT t.task_id, t.title, t.description, t.status, t.priority,
               t.assigned_to, u.first_name || ' ' || u.last_name as assigned_name,
               t.related_type, t.related_id, t.due_date, t.created_at
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.user_id
        WHERE {where_clause}
        ORDER BY
            CASE t.priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low' THEN 4
            END,
            t.due_date ASC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    items = []
    for row in rows:
        related_to = None
        if row[7] and row[8]:
            related_to = {"type": row[7], "id": str(row[8])}

        items.append(TaskItem(
            task_id=str(row[0]),
            title=row[1] or "",
            description=row[2],
            status=row[3] or "pending",
            priority=row[4] or "normal",
            assigned_to=str(row[5]) if row[5] else None,
            assigned_name=row[6],
            related_to=related_to,
            due_date=parse_dt(row[9]),
            created_at=parse_dt(row[10]) or datetime.utcnow(),
        ))

    return items


@router.post("/tasks")
@require_permission(UserPermission.EDIT_RETURNS)
async def create_task(
    title: str = Query(..., max_length=200),
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    description: Optional[str] = Query(None),
    priority: str = Query("normal"),
    assigned_to: Optional[str] = Query(None),
    due_date: Optional[str] = Query(None),
    related_type: Optional[str] = Query(None),
    related_id: Optional[str] = Query(None),
):
    """Create a new task."""
    # Validate priority
    try:
        TaskPriority(priority)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority. Must be one of: {[p.value for p in TaskPriority]}",
        )

    # If assigned_to provided, verify user belongs to firm
    if assigned_to:
        user_check = text("SELECT user_id FROM users WHERE user_id = :user_id AND firm_id = :firm_id AND is_active = true")
        user_result = await session.execute(user_check, {"user_id": assigned_to, "firm_id": firm_id})
        if not user_result.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned user not found")

    task_id = str(uuid4())
    now = datetime.utcnow()

    query = text("""
        INSERT INTO tasks (
            task_id, firm_id, title, description, status, priority,
            assigned_to, due_date, related_type, related_id,
            created_by, created_at, updated_at
        ) VALUES (
            :task_id, :firm_id, :title, :description, 'pending', :priority,
            :assigned_to, :due_date, :related_type, :related_id,
            :created_by, :created_at, :created_at
        )
    """)

    await session.execute(query, {
        "task_id": task_id,
        "firm_id": firm_id,
        "title": title,
        "description": description,
        "priority": priority,
        "assigned_to": assigned_to,
        "due_date": due_date,
        "related_type": related_type,
        "related_id": related_id,
        "created_by": user.user_id,
        "created_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"Task {task_id} created by {user.email}")

    return {
        "status": "success",
        "task_id": task_id,
        "title": title,
        "created_by": user.user_id,
        "created_at": now.isoformat(),
    }


@router.patch("/tasks/{task_id}")
@require_permission(UserPermission.EDIT_RETURNS)
async def update_task(
    task_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    status_update: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    due_date: Optional[str] = Query(None),
):
    """Update a task."""
    # Verify task exists and belongs to firm
    check_query = text("SELECT task_id FROM tasks WHERE task_id = :task_id AND firm_id = :firm_id")
    check_result = await session.execute(check_query, {"task_id": task_id, "firm_id": firm_id})
    if not check_result.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Build update fields
    updates = []
    params = {"task_id": task_id, "updated_at": datetime.utcnow().isoformat()}

    if status_update:
        try:
            TaskStatus(status_update)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in TaskStatus]}",
            )
        updates.append("status = :status")
        params["status"] = status_update
        if status_update == "completed":
            updates.append("completed_at = :updated_at")

    if priority:
        try:
            TaskPriority(priority)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid priority. Must be one of: {[p.value for p in TaskPriority]}",
            )
        updates.append("priority = :priority")
        params["priority"] = priority

    if assigned_to is not None:
        if assigned_to:
            user_check = text("SELECT user_id FROM users WHERE user_id = :user_id AND firm_id = :firm_id AND is_active = true")
            user_result = await session.execute(user_check, {"user_id": assigned_to, "firm_id": firm_id})
            if not user_result.fetchone():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned user not found")
        updates.append("assigned_to = :assigned_to")
        params["assigned_to"] = assigned_to if assigned_to else None

    if due_date is not None:
        updates.append("due_date = :due_date")
        params["due_date"] = due_date if due_date else None

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    updates.append("updated_at = :updated_at")
    update_clause = ", ".join(updates)

    query = text(f"UPDATE tasks SET {update_clause} WHERE task_id = :task_id")
    await session.execute(query, params)
    await session.commit()

    logger.info(f"Task {task_id} updated by {user.email}")

    return {
        "status": "success",
        "task_id": task_id,
        "updated_by": user.user_id,
        "updated_at": params["updated_at"],
    }


@router.delete("/tasks/{task_id}")
@require_permission(UserPermission.EDIT_RETURNS)
async def delete_task(
    task_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Delete a task."""
    # Soft delete by marking as cancelled
    query = text("""
        UPDATE tasks SET
            status = 'cancelled',
            updated_at = :updated_at
        WHERE task_id = :task_id AND firm_id = :firm_id
    """)
    result = await session.execute(query, {
        "task_id": task_id,
        "firm_id": firm_id,
        "updated_at": datetime.utcnow().isoformat(),
    })

    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    await session.commit()
    logger.info(f"Task {task_id} deleted by {user.email}")

    return {"status": "success", "task_id": task_id}


# =============================================================================
# DEADLINE TRACKING ROUTES
# =============================================================================

@router.get("/deadlines", response_model=List[DeadlineItem])
@require_permission(UserPermission.VIEW_RETURNS)
async def get_deadlines(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    days_ahead: int = Query(30, ge=1, le=365, description="Days to look ahead"),
    deadline_type: Optional[str] = Query(None, description="Filter by type"),
    assigned_to: Optional[str] = Query(None),
    include_completed: bool = Query(False),
):
    """Get upcoming deadlines."""
    now = datetime.utcnow()
    end_date = now + timedelta(days=days_ahead)

    # Build conditions
    conditions = [
        "u.firm_id = :firm_id",
        "r.deadline IS NOT NULL",
        "r.deadline <= :end_date",
    ]
    params = {"firm_id": firm_id, "end_date": end_date.isoformat()}

    if not include_completed:
        conditions.append("r.workflow_stage != 'complete'")

    if deadline_type:
        conditions.append("r.return_type = :deadline_type")
        params["deadline_type"] = deadline_type

    if assigned_to:
        conditions.append("r.preparer_id = :assigned_to")
        params["assigned_to"] = assigned_to

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT r.return_id as deadline_id, r.return_type, r.client_id,
               c.first_name || ' ' || c.last_name as client_name,
               r.return_id, r.deadline, r.workflow_stage, r.preparer_id
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        LEFT JOIN clients c ON r.client_id = c.client_id
        WHERE {where_clause}
        ORDER BY r.deadline ASC
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    items = []
    for row in rows:
        deadline = parse_dt(row[5])
        days_until = (deadline - now).days if deadline else 0

        # Determine status based on days_until and workflow_stage
        stage = row[6] or "intake"
        if stage == "complete":
            status_val = "completed"
        elif days_until < 0:
            status_val = "overdue"
        elif days_until <= 3:
            status_val = "at_risk"
        elif days_until <= 7:
            status_val = "urgent"
        else:
            status_val = "on_track"

        items.append(DeadlineItem(
            deadline_id=str(row[0]),
            deadline_type=row[1] or "tax_return",
            client_id=str(row[2]) if row[2] else "",
            client_name=row[3] or "Unknown",
            return_id=str(row[4]) if row[4] else None,
            due_date=deadline or datetime.utcnow(),
            days_until=days_until,
            status=status_val,
            assigned_to=str(row[7]) if row[7] else None,
        ))

    return items


@router.get("/deadlines/calendar")
@require_permission(UserPermission.VIEW_RETURNS)
async def get_deadline_calendar(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    year: int = Query(default=None, description="Year"),
    month: int = Query(default=None, ge=1, le=12, description="Month"),
):
    """Get deadlines in calendar format."""
    now = datetime.utcnow()
    target_year = year or now.year
    target_month = month or now.month

    # Calculate month boundaries
    start_date = datetime(target_year, target_month, 1)
    if target_month == 12:
        end_date = datetime(target_year + 1, 1, 1)
    else:
        end_date = datetime(target_year, target_month + 1, 1)

    # Get all deadlines for the month
    query = text("""
        SELECT EXTRACT(DAY FROM r.deadline) as day,
               r.return_type, r.return_id, r.workflow_stage,
               c.first_name || ' ' || c.last_name as client_name
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        LEFT JOIN clients c ON r.client_id = c.client_id
        WHERE u.firm_id = :firm_id
        AND r.deadline >= :start_date
        AND r.deadline < :end_date
        AND r.deadline IS NOT NULL
        ORDER BY r.deadline ASC
    """)

    result = await session.execute(query, {
        "firm_id": firm_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })
    rows = result.fetchall()

    # Group by day
    deadlines_by_day = {}
    total = 0
    on_track = 0
    at_risk = 0
    overdue = 0

    for row in rows:
        day = str(int(row[0]))
        return_type = row[1] or "tax_return"
        stage = row[3] or "intake"
        client_name = row[4] or "Unknown"

        if day not in deadlines_by_day:
            deadlines_by_day[day] = []

        # Check if deadline entry for this type already exists
        existing = next((d for d in deadlines_by_day[day] if d["type"] == return_type), None)
        if existing:
            existing["count"] += 1
        else:
            deadlines_by_day[day].append({
                "deadline_id": str(row[2]),
                "type": return_type,
                "client": client_name,
                "count": 1,
            })

        # Calculate status
        total += 1
        deadline_date = datetime(target_year, target_month, int(row[0]))
        days_until = (deadline_date - now).days

        if stage == "complete":
            pass  # Don't count completed
        elif days_until < 0:
            overdue += 1
        elif days_until <= 3:
            at_risk += 1
        else:
            on_track += 1

    return {
        "year": target_year,
        "month": target_month,
        "deadlines_by_day": deadlines_by_day,
        "summary": {
            "total_deadlines": total,
            "on_track": on_track,
            "at_risk": at_risk,
            "overdue": overdue,
        },
    }


# =============================================================================
# REVIEW QUEUE ROUTES
# =============================================================================

@router.get("/review-queue")
@require_permission(UserPermission.REVIEW_RETURNS)
async def get_review_queue(
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    reviewer_id: Optional[str] = Query(None, description="Filter by reviewer"),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get items awaiting review."""
    # Build conditions
    conditions = ["u.firm_id = :firm_id", "r.workflow_stage = 'review'"]
    params = {"firm_id": firm_id, "limit": limit}

    if reviewer_id:
        conditions.append("r.reviewer_id = :reviewer_id")
        params["reviewer_id"] = reviewer_id

    if priority:
        conditions.append("r.priority = :priority")
        params["priority"] = priority

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT r.return_id, c.first_name || ' ' || c.last_name as client_name,
               r.return_type, r.tax_year, r.preparer_id,
               p.first_name || ' ' || p.last_name as preparer_name,
               r.stage_entered_at, r.priority, r.complexity
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        LEFT JOIN clients c ON r.client_id = c.client_id
        LEFT JOIN users p ON r.preparer_id = p.user_id
        WHERE {where_clause}
        ORDER BY
            CASE r.priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low' THEN 4
            END,
            r.stage_entered_at ASC
        LIMIT :limit
    """)

    result = await session.execute(query, params)
    rows = result.fetchall()

    def parse_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(val.replace('Z', '+00:00'))

    queue = []
    total_wait_hours = 0
    now = datetime.utcnow()

    for row in rows:
        submitted = parse_dt(row[6])
        wait_hours = int((now - submitted).total_seconds() / 3600) if submitted else 0
        total_wait_hours += wait_hours

        queue.append({
            "return_id": str(row[0]),
            "client_name": row[1] or "Unknown",
            "return_type": row[2] or "",
            "tax_year": row[3] or now.year,
            "prepared_by": str(row[4]) if row[4] else None,
            "prepared_by_name": row[5] or "",
            "submitted_for_review": submitted.isoformat() if submitted else None,
            "priority": row[7] or "normal",
            "complexity": row[8] or "medium",
        })

    avg_wait = total_wait_hours // len(queue) if queue else 0

    return {
        "queue": queue,
        "total": len(queue),
        "avg_wait_hours": avg_wait,
    }


@router.post("/review-queue/{return_id}/claim")
@require_permission(UserPermission.REVIEW_RETURNS)
async def claim_for_review(
    return_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
):
    """Claim a return for review."""
    now = datetime.utcnow()

    # Verify return exists, is in review stage, and belongs to firm
    check_query = text("""
        SELECT r.return_id, r.workflow_stage, r.reviewer_id
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE r.return_id = :return_id AND u.firm_id = :firm_id
    """)
    check_result = await session.execute(check_query, {"return_id": return_id, "firm_id": firm_id})
    row = check_result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    if row[1] != "review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Return is not in review stage (current: {row[1]})",
        )

    if row[2]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Return is already claimed for review",
        )

    # Claim the return
    update_query = text("""
        UPDATE returns SET
            reviewer_id = :reviewer_id,
            review_started_at = :started_at,
            updated_at = :updated_at
        WHERE return_id = :return_id
    """)
    await session.execute(update_query, {
        "return_id": return_id,
        "reviewer_id": user.user_id,
        "started_at": now.isoformat(),
        "updated_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"Return {return_id} claimed for review by {user.email}")

    return {
        "status": "success",
        "return_id": return_id,
        "claimed_by": user.user_id,
        "claimed_at": now.isoformat(),
    }


@router.post("/review-queue/{return_id}/complete")
@require_permission(UserPermission.REVIEW_RETURNS)
async def complete_review(
    return_id: str,
    user: TenantContext = Depends(get_current_user),
    firm_id: str = Depends(get_current_firm),
    session: AsyncSession = Depends(get_async_session),
    approved: bool = Query(..., description="Whether review is approved"),
    notes: Optional[str] = Query(None),
    return_to_preparer: bool = Query(False),
):
    """Complete review of a return."""
    now = datetime.utcnow()

    # Verify return exists and is in review
    check_query = text("""
        SELECT r.return_id, r.workflow_stage, r.reviewer_id, r.stage_history
        FROM returns r
        JOIN users u ON r.preparer_id = u.user_id
        WHERE r.return_id = :return_id AND u.firm_id = :firm_id
    """)
    check_result = await session.execute(check_query, {"return_id": return_id, "firm_id": firm_id})
    row = check_result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")

    if row[1] != "review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Return is not in review stage (current: {row[1]})",
        )

    # Determine next stage
    if approved:
        next_stage = "client_review"
    elif return_to_preparer:
        next_stage = "preparation"
    else:
        next_stage = "preparation"

    # Update stage history
    stage_history = json.loads(row[3]) if row[3] else []
    stage_history.append({
        "stage": "review",
        "exited_at": now.isoformat(),
        "user": user.user_id,
        "action": "reviewed",
        "approved": approved,
        "notes": notes,
    })

    # Update return
    update_query = text("""
        UPDATE returns SET
            workflow_stage = :new_stage,
            stage_entered_at = :entered_at,
            stage_history = :history,
            reviewer_id = NULL,
            review_completed_at = :completed_at,
            updated_at = :updated_at
        WHERE return_id = :return_id
    """)
    await session.execute(update_query, {
        "return_id": return_id,
        "new_stage": next_stage,
        "entered_at": now.isoformat(),
        "history": json.dumps(stage_history),
        "completed_at": now.isoformat(),
        "updated_at": now.isoformat(),
    })
    await session.commit()

    logger.info(f"Return {return_id} review completed by {user.email}: approved={approved}")

    return {
        "status": "success",
        "return_id": return_id,
        "approved": approved,
        "reviewed_by": user.user_id,
        "next_stage": next_stage,
    }
