"""Deadlines API - Tax deadline tracking endpoints."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from rbac.dependencies import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deadlines", tags=["deadlines"])

IRS_DEADLINES = [
    {"title": "W-2 / 1099 Distribution Deadline", "date": "2026-01-31", "category": "irs", "form": "W-2/1099"},
    {"title": "Individual Tax Return (Form 1040)", "date": "2026-04-15", "category": "irs", "form": "1040"},
    {"title": "Extension Deadline (Form 4868)", "date": "2026-04-15", "category": "irs", "form": "4868"},
    {"title": "Q1 Estimated Tax Payment", "date": "2026-04-15", "category": "irs", "form": "1040-ES"},
    {"title": "Q2 Estimated Tax Payment", "date": "2026-06-15", "category": "irs", "form": "1040-ES"},
    {"title": "Q3 Estimated Tax Payment", "date": "2026-09-15", "category": "irs", "form": "1040-ES"},
    {"title": "Extended Return Deadline", "date": "2026-10-15", "category": "irs", "form": "1040"},
    {"title": "Q4 Estimated Tax Payment", "date": "2027-01-15", "category": "irs", "form": "1040-ES"},
]


class DeadlineCreate(BaseModel):
    title: str = Field(..., max_length=255)
    date: str
    category: str = Field(default="custom", pattern="^(irs|state|custom|client)$")
    client_id: Optional[str] = None
    notes: Optional[str] = None


class DeadlineUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    date: Optional[str] = None
    notes: Optional[str] = None
    completed: Optional[bool] = None


# SQLite-backed persistence (replaces in-memory dict)
import sqlite3, json, os
from pathlib import Path

_DB_PATH = Path(os.environ.get("DATABASE_PATH", str(Path(__file__).parent.parent.parent.parent / "data" / "platform.db")))

def _get_db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS custom_deadlines (
        deadline_id TEXT PRIMARY KEY, data_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    return conn

def _save_dl(dl_id, record):
    with _get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO custom_deadlines (deadline_id, data_json, created_at) VALUES (?, ?, ?)",
                     (dl_id, json.dumps(record, default=str), record.get("created_at", "")))

def _load_dl(dl_id):
    with _get_db() as conn:
        row = conn.execute("SELECT data_json FROM custom_deadlines WHERE deadline_id = ?", (dl_id,)).fetchone()
        return json.loads(row[0]) if row else None

def _load_all_dl():
    with _get_db() as conn:
        return [json.loads(r[0]) for r in conn.execute("SELECT data_json FROM custom_deadlines").fetchall()]

def _delete_dl(dl_id):
    with _get_db() as conn:
        conn.execute("DELETE FROM custom_deadlines WHERE deadline_id = ?", (dl_id,))


@router.get("")
async def list_deadlines(category: Optional[str] = None, ctx=Depends(require_auth)):
    deadlines = [
        {**d, "deadline_id": f"irs-{i}", "completed": False}
        for i, d in enumerate(IRS_DEADLINES)
    ]
    deadlines.extend(_load_all_dl())
    if category:
        deadlines = [d for d in deadlines if d.get("category") == category]
    deadlines.sort(key=lambda d: d.get("date", ""))
    return {"deadlines": deadlines, "total": len(deadlines)}


@router.post("", status_code=201)
async def create_deadline(deadline: DeadlineCreate, ctx=Depends(require_auth)):
    dl_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {"deadline_id": dl_id, **deadline.model_dump(), "completed": False, "created_by": str(ctx.user_id) if ctx.user_id else None, "created_at": now}
    _save_dl(dl_id, record)
    return record


@router.patch("/{deadline_id}")
async def update_deadline(deadline_id: str, updates: DeadlineUpdate, ctx=Depends(require_auth)):
    record = _load_dl(deadline_id)
    if not record:
        raise HTTPException(status_code=404, detail="Deadline not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        record[key] = value
    _save_dl(deadline_id, record)
    return record


@router.delete("/{deadline_id}", status_code=204)
async def delete_deadline(deadline_id: str, ctx=Depends(require_auth)):
    record = _load_dl(deadline_id)
    if not record:
        raise HTTPException(status_code=404, detail="Deadline not found")
    _delete_dl(deadline_id)
