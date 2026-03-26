"""Tasks API - CRUD endpoints for task management with SQLite persistence."""

import json
import logging
import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path
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


# SQLite-backed persistence (replaces in-memory dict)
_DB_PATH = Path(os.environ.get("DATABASE_PATH", str(Path(__file__).parent.parent.parent.parent / "data" / "platform.db")))


def _get_db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            data_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    return conn


def _save_task(task_id: str, record: dict):
    now = datetime.now(timezone.utc).isoformat()
    with _get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO tasks (task_id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (task_id, json.dumps(record, default=str), record.get("created_at", now), now)
        )


def _load_task(task_id: str) -> Optional[dict]:
    with _get_db() as conn:
        row = conn.execute("SELECT data_json FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return json.loads(row[0]) if row else None


def _load_all_tasks() -> list:
    with _get_db() as conn:
        rows = conn.execute("SELECT data_json FROM tasks ORDER BY created_at DESC").fetchall()
        return [json.loads(r[0]) for r in rows]


def _delete_task(task_id: str):
    with _get_db() as conn:
        conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))


@router.get("")
async def list_tasks(status: Optional[str] = None, priority: Optional[str] = None, ctx=Depends(require_auth)):
    tasks = _load_all_tasks()
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if priority:
        tasks = [t for t in tasks if t.get("priority") == priority]
    return {"tasks": tasks, "total": len(tasks)}


@router.post("", status_code=201)
async def create_task(task: TaskCreate, ctx=Depends(require_auth)):
    task_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {"task_id": task_id, **task.model_dump(), "created_by": str(ctx.user_id) if ctx.user_id else None, "created_at": now, "updated_at": now}
    _save_task(task_id, record)
    return record


@router.get("/{task_id}")
async def get_task(task_id: str, ctx=Depends(require_auth)):
    record = _load_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    return record


@router.patch("/{task_id}")
async def update_task(task_id: str, updates: TaskUpdate, ctx=Depends(require_auth)):
    record = _load_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        record[key] = value
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_task(task_id, record)
    return record


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, ctx=Depends(require_auth)):
    record = _load_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    _delete_task(task_id)
