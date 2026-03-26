"""Appointments API - CRUD endpoints with SQLite persistence."""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from rbac.dependencies import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/appointments", tags=["appointments"])


class AppointmentCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    client_id: Optional[str] = None
    start_time: str
    end_time: str
    location: Optional[str] = None
    meeting_type: str = Field(default="video", pattern="^(video|phone|in_person)$")


class AppointmentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(scheduled|completed|cancelled|no_show)$")


_DB_PATH = Path(os.environ.get("DATABASE_PATH", str(Path(__file__).parent.parent.parent.parent / "data" / "platform.db")))


def _get_db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id TEXT PRIMARY KEY,
            data_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    return conn


def _save(appt_id: str, record: dict):
    now = datetime.now(timezone.utc).isoformat()
    with _get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO appointments (appointment_id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (appt_id, json.dumps(record, default=str), record.get("created_at", now), now)
        )


def _load(appt_id: str) -> Optional[dict]:
    with _get_db() as conn:
        row = conn.execute("SELECT data_json FROM appointments WHERE appointment_id = ?", (appt_id,)).fetchone()
        return json.loads(row[0]) if row else None


def _load_all() -> list:
    with _get_db() as conn:
        rows = conn.execute("SELECT data_json FROM appointments ORDER BY created_at DESC").fetchall()
        return [json.loads(r[0]) for r in rows]


def _delete(appt_id: str):
    with _get_db() as conn:
        conn.execute("DELETE FROM appointments WHERE appointment_id = ?", (appt_id,))


@router.get("")
async def list_appointments(status: Optional[str] = None, ctx=Depends(require_auth)):
    appts = _load_all()
    if status:
        appts = [a for a in appts if a.get("status") == status]
    return {"appointments": appts, "total": len(appts)}


@router.post("", status_code=201)
async def create_appointment(appt: AppointmentCreate, ctx=Depends(require_auth)):
    appt_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "appointment_id": appt_id,
        **appt.model_dump(),
        "status": "scheduled",
        "created_by": str(ctx.user_id) if ctx.user_id else None,
        "created_at": now,
        "updated_at": now,
    }
    _save(appt_id, record)
    return record


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, ctx=Depends(require_auth)):
    record = _load(appointment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return record


@router.patch("/{appointment_id}")
async def update_appointment(appointment_id: str, updates: AppointmentUpdate, ctx=Depends(require_auth)):
    record = _load(appointment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Appointment not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        record[key] = value
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(appointment_id, record)
    return record


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(appointment_id: str, ctx=Depends(require_auth)):
    record = _load(appointment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _delete(appointment_id)
