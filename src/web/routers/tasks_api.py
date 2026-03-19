"""Tasks API - CRUD endpoints for task management."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from rbac.dependencies import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    status: str = Field(default="todo", pattern="^(todo|in_progress|done)$")
    assigned_to: Optional[str] = None
    client_id: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    status: Optional[str] = Field(None, pattern="^(todo|in_progress|done)$")
    assigned_to: Optional[str] = None


_tasks: dict[str, dict] = {}


@router.get("")
async def list_tasks(status: Optional[str] = None, priority: Optional[str] = None, ctx=Depends(require_auth)):
    tasks = list(_tasks.values())
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if priority:
        tasks = [t for t in tasks if t["priority"] == priority]
    return {"tasks": tasks, "total": len(tasks)}


@router.post("", status_code=201)
async def create_task(task: TaskCreate, ctx=Depends(require_auth)):
    task_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {"task_id": task_id, **task.model_dump(), "created_by": str(ctx.user_id) if ctx.user_id else None, "created_at": now, "updated_at": now}
    _tasks[task_id] = record
    return record


@router.get("/{task_id}")
async def get_task(task_id: str, ctx=Depends(require_auth)):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]


@router.patch("/{task_id}")
async def update_task(task_id: str, updates: TaskUpdate, ctx=Depends(require_auth)):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        _tasks[task_id][key] = value
    _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _tasks[task_id]


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, ctx=Depends(require_auth)):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    del _tasks[task_id]
