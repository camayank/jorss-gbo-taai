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


@router.get("/summary")
async def deadline_summary(ctx=Depends(require_auth)):
    """Count of overdue, due-soon, this-month, and completed deadlines."""
    today = datetime.now(timezone.utc).date()
    all_dl = [
        {**d, "deadline_id": f"irs-{i}", "completed": False}
        for i, d in enumerate(IRS_DEADLINES)
    ] + _load_all_dl()

    overdue = due_soon = this_month = completed = 0
    for d in all_dl:
        if d.get("completed"):
            completed += 1
            continue
        try:
            dl_date = datetime.strptime(d["date"][:10], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        delta = (dl_date - today).days
        if delta < 0:
            overdue += 1
        elif delta <= 14:
            due_soon += 1
        elif dl_date.month == today.month and dl_date.year == today.year:
            this_month += 1

    return {"overdue": overdue, "due_soon": due_soon, "this_month": this_month, "completed": completed}


@router.get("/calendar/{year}/{month}")
async def deadline_calendar(year: int, month: int, ctx=Depends(require_auth)):
    """Return deadlines grouped by date for a calendar month."""
    all_dl = [
        {**d, "deadline_id": f"irs-{i}", "completed": False}
        for i, d in enumerate(IRS_DEADLINES)
    ] + _load_all_dl()

    by_date: dict = {}
    for d in all_dl:
        try:
            dl_date = datetime.strptime(d["date"][:10], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        if dl_date.year == year and dl_date.month == month:
            key = dl_date.isoformat()
            by_date.setdefault(key, []).append(d)

    return {"year": year, "month": month, "days": by_date}


@router.post("/{deadline_id}/complete")
async def complete_deadline(deadline_id: str, ctx=Depends(require_auth)):
    record = _load_dl(deadline_id)
    if not record:
        raise HTTPException(status_code=404, detail="Deadline not found")
    record["completed"] = True
    record["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_dl(deadline_id, record)
    return record


class ExtensionRequest(BaseModel):
    new_date: str
    reason: Optional[str] = None


@router.post("/{deadline_id}/extension")
async def extend_deadline(deadline_id: str, body: ExtensionRequest, ctx=Depends(require_auth)):
    record = _load_dl(deadline_id)
    if not record:
        raise HTTPException(status_code=404, detail="Deadline not found")
    record["original_date"] = record.get("date")
    record["date"] = body.new_date
    record["extension_reason"] = body.reason
    record["extended_at"] = datetime.now(timezone.utc).isoformat()
    _save_dl(deadline_id, record)
    return record


class GenerateStandardRequest(BaseModel):
    tax_year: int = 2025
    client_ids: list = []


@router.post("/generate-standard")
async def generate_standard_deadlines(body: GenerateStandardRequest, ctx=Depends(require_auth)):
    """Seed standard IRS deadlines for the given tax year."""
    year = body.tax_year
    next_year = year + 1
    standard = [
        {"title": "W-2 / 1099 Distribution Deadline",   "date": f"{next_year}-01-31", "category": "irs", "form": "W-2/1099"},
        {"title": "Individual Tax Return (Form 1040)",   "date": f"{next_year}-04-15", "category": "irs", "form": "1040"},
        {"title": "Extension Deadline (Form 4868)",      "date": f"{next_year}-04-15", "category": "irs", "form": "4868"},
        {"title": "Q1 Estimated Tax Payment",            "date": f"{next_year}-04-15", "category": "irs", "form": "1040-ES"},
        {"title": "Q2 Estimated Tax Payment",            "date": f"{next_year}-06-15", "category": "irs", "form": "1040-ES"},
        {"title": "Q3 Estimated Tax Payment",            "date": f"{next_year}-09-15", "category": "irs", "form": "1040-ES"},
        {"title": "Extended Return Deadline",            "date": f"{next_year}-10-15", "category": "irs", "form": "1040"},
        {"title": "Q4 Estimated Tax Payment",            "date": f"{next_year+1}-01-15", "category": "irs", "form": "1040-ES"},
    ]
    created = []
    now = datetime.now(timezone.utc).isoformat()
    for d in standard:
        dl_id = str(uuid4())
        record = {**d, "deadline_id": dl_id, "completed": False, "tax_year": year,
                  "created_by": str(ctx.user_id) if ctx.user_id else None, "created_at": now}
        _save_dl(dl_id, record)
        created.append(record)
    return {"created": len(created), "deadlines": created}
