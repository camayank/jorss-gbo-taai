"""Appointments API - CRUD endpoints for appointment scheduling."""

import logging
from datetime import datetime, timezone
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


_appointments: dict[str, dict] = {}


@router.get("")
async def list_appointments(status: Optional[str] = None, ctx=Depends(require_auth)):
    appts = list(_appointments.values())
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
    _appointments[appt_id] = record
    return record


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, ctx=Depends(require_auth)):
    if appointment_id not in _appointments:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return _appointments[appointment_id]


@router.patch("/{appointment_id}")
async def update_appointment(appointment_id: str, updates: AppointmentUpdate, ctx=Depends(require_auth)):
    if appointment_id not in _appointments:
        raise HTTPException(status_code=404, detail="Appointment not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        _appointments[appointment_id][key] = value
    _appointments[appointment_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _appointments[appointment_id]


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(appointment_id: str, ctx=Depends(require_auth)):
    if appointment_id not in _appointments:
        raise HTTPException(status_code=404, detail="Appointment not found")
    del _appointments[appointment_id]
