"""
Feature Page Routes - Wires orphaned templates to URL routes.

Routes for features that have templates but were missing URL endpoints:
- Documents (library, viewer)
- Support (tickets, create, detail)
- Tasks (list, kanban, detail)
- Appointments (calendar, booking, settings)
- Deadlines (list, calendar)
- Settings (notifications)
- Admin impersonation
- Computation worksheet
- Capital gains calculator
- K-1 basis tracker
- Rental depreciation schedule
- Draft forms viewer
- Filing package export
- Admin refund management
"""

import os
import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Feature Pages"])

# Templates directory
_templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_templates_dir)


# =============================================================================
# AUTH HELPERS
# =============================================================================

try:
    from security.auth_decorators import get_user_from_request
except ImportError:
    get_user_from_request = lambda r: None

_ADMIN_UI_ROLES = {"super_admin", "platform_admin", "admin", "support", "billing"}


async def _require_page_auth(request: Request) -> dict:
    """Require any authenticated user. Raises 401 -> login redirect via exception handler."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def _require_admin_page(request: Request) -> dict:
    """Require admin role. Raises 401/403."""
    user = await _require_page_auth(request)
    role = (user.get("role") or "").lower()
    if role not in _ADMIN_UI_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# =============================================================================
# DOCUMENTS
# =============================================================================

@router.get("/documents/library", response_class=HTMLResponse)
def documents_library(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Document library - browse and manage uploaded documents."""
    return templates.TemplateResponse(
        "documents/library.html",
        {"request": request, "user": current_user, "page_title": "Document Library"}
    )


@router.get("/documents/{document_id}/view", response_class=HTMLResponse)
def documents_viewer(request: Request, document_id: str, current_user: dict = Depends(_require_page_auth)):
    """Document viewer - view a specific document."""
    return templates.TemplateResponse(
        "documents/viewer.html",
        {"request": request, "user": current_user, "document_id": document_id, "page_title": "Document Viewer"}
    )


# =============================================================================
# SUPPORT TICKETS
# =============================================================================

@router.get("/support", response_class=HTMLResponse)
@router.get("/support/tickets", response_class=HTMLResponse)
def support_tickets(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Support tickets list - view all support tickets."""
    return templates.TemplateResponse(
        "support/tickets.html",
        {"request": request, "user": current_user, "page_title": "Support Tickets"}
    )


@router.get("/support/new", response_class=HTMLResponse)
def support_create(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Create new support ticket."""
    return templates.TemplateResponse(
        "support/create.html",
        {"request": request, "user": current_user, "page_title": "Create Support Ticket"}
    )


@router.get("/support/tickets/{ticket_id}", response_class=HTMLResponse)
def support_detail(request: Request, ticket_id: str, current_user: dict = Depends(_require_page_auth)):
    """Support ticket detail view."""
    return templates.TemplateResponse(
        "support/detail.html",
        {"request": request, "user": current_user, "ticket_id": ticket_id, "page_title": "Support Ticket"}
    )


# =============================================================================
# TASKS
# =============================================================================

@router.get("/tasks", response_class=HTMLResponse)
def tasks_list(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Task list - view all tasks."""
    return templates.TemplateResponse(
        "tasks/list.html",
        {"request": request, "user": current_user, "page_title": "Tasks"}
    )


@router.get("/tasks/kanban", response_class=HTMLResponse)
def tasks_kanban(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Task kanban board - visual task management."""
    return templates.TemplateResponse(
        "tasks/kanban.html",
        {"request": request, "user": current_user, "page_title": "Task Board"}
    )


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
def tasks_detail(request: Request, task_id: str, current_user: dict = Depends(_require_page_auth)):
    """Task detail view."""
    return templates.TemplateResponse(
        "tasks/detail.html",
        {"request": request, "user": current_user, "task_id": task_id, "page_title": "Task Detail"}
    )


# =============================================================================
# APPOINTMENTS
# =============================================================================

@router.get("/appointments", response_class=HTMLResponse)
@router.get("/appointments/calendar", response_class=HTMLResponse)
def appointments_calendar(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Appointment calendar - view and manage appointments."""
    return templates.TemplateResponse(
        "appointments/calendar.html",
        {"request": request, "user": current_user, "page_title": "Appointments"}
    )


@router.get("/appointments/book", response_class=HTMLResponse)
def appointments_booking(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Book a new appointment."""
    return templates.TemplateResponse(
        "appointments/booking.html",
        {"request": request, "user": current_user, "page_title": "Book Appointment"}
    )


@router.get("/appointments/settings", response_class=HTMLResponse)
def appointments_settings(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Appointment settings - configure scheduling preferences."""
    return templates.TemplateResponse(
        "appointments/settings.html",
        {"request": request, "user": current_user, "page_title": "Appointment Settings"}
    )


# =============================================================================
# DEADLINES
# =============================================================================

@router.get("/deadlines", response_class=HTMLResponse)
def deadlines_list(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Deadline list - view upcoming tax deadlines."""
    return templates.TemplateResponse(
        "deadlines/list.html",
        {"request": request, "user": current_user, "page_title": "Deadlines"}
    )


@router.get("/deadlines/calendar", response_class=HTMLResponse)
def deadlines_calendar(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Deadline calendar - visual deadline tracker."""
    return templates.TemplateResponse(
        "deadlines/calendar.html",
        {"request": request, "user": current_user, "page_title": "Deadline Calendar"}
    )


# =============================================================================
# SETTINGS
# =============================================================================

@router.get("/settings/notifications", response_class=HTMLResponse)
def settings_notifications(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Notification settings - configure email and push notifications."""
    return templates.TemplateResponse(
        "settings/notifications.html",
        {"request": request, "user": current_user, "page_title": "Notification Settings"}
    )


# =============================================================================
# ADMIN IMPERSONATION (admin-only)
# =============================================================================

@router.get("/admin/impersonation", response_class=HTMLResponse)
def admin_impersonation(request: Request, current_user: dict = Depends(_require_admin_page)):
    """Admin impersonation - view as another user for support purposes."""
    return templates.TemplateResponse(
        "admin_impersonation.html",
        {"request": request, "user": current_user, "page_title": "User Impersonation"}
    )


# =============================================================================
# COMPUTATION WORKSHEET
# =============================================================================

@router.get("/computation-worksheet", response_class=HTMLResponse)
def computation_worksheet(request: Request, current_user: dict = Depends(_require_page_auth)):
    """IRS-style tax computation worksheet with live calculations."""
    return templates.TemplateResponse(
        "computation_worksheet.html",
        {"request": request, "user": current_user, "page_title": "Computation Worksheet"}
    )


# =============================================================================
# CAPITAL GAINS
# =============================================================================

@router.get("/capital-gains", response_class=HTMLResponse)
def capital_gains(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Capital gains calculator - Form 8949 and Schedule D."""
    return templates.TemplateResponse(
        "capital_gains.html",
        {"request": request, "user": current_user, "page_title": "Capital Gains"}
    )


# =============================================================================
# K-1 BASIS TRACKER
# =============================================================================

@router.get("/k1-basis", response_class=HTMLResponse)
def k1_basis(request: Request, current_user: dict = Depends(_require_page_auth)):
    """K-1 basis tracker - partnership, S-Corp, and trust basis worksheets."""
    return templates.TemplateResponse(
        "k1_basis.html",
        {"request": request, "user": current_user, "page_title": "K-1 Basis Tracker"}
    )


# =============================================================================
# RENTAL DEPRECIATION
# =============================================================================

@router.get("/rental-depreciation", response_class=HTMLResponse)
def rental_depreciation(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Rental property depreciation schedule calculator."""
    return templates.TemplateResponse(
        "rental_depreciation.html",
        {"request": request, "user": current_user, "page_title": "Rental Depreciation"}
    )


# =============================================================================
# DRAFT FORMS
# =============================================================================

@router.get("/draft-forms", response_class=HTMLResponse)
def draft_forms(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Draft tax forms viewer - preview generated IRS forms."""
    return templates.TemplateResponse(
        "draft_forms.html",
        {"request": request, "user": current_user, "page_title": "Draft Forms"}
    )


# =============================================================================
# FILING PACKAGE
# =============================================================================

@router.get("/filing-package", response_class=HTMLResponse)
def filing_package(request: Request, current_user: dict = Depends(_require_page_auth)):
    """Filing package export - generate and download complete tax filing packages."""
    return templates.TemplateResponse(
        "filing_package.html",
        {"request": request, "user": current_user, "page_title": "Filing Package"}
    )


# =============================================================================
# ADMIN REFUNDS (admin-only)
# =============================================================================

@router.get("/admin/refunds", response_class=HTMLResponse)
def admin_refunds(request: Request, current_user: dict = Depends(_require_admin_page)):
    """Admin refund management - review and process client refund requests."""
    return templates.TemplateResponse(
        "admin_refunds.html",
        {"request": request, "user": current_user, "page_title": "Refund Management"}
    )
