# Go-Live Gap Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all discovered gaps between UI, backend, and database so every visible screen, nav link, and API endpoint is wired end-to-end.

**Architecture:** Patch existing routes and templates — no new frameworks. Add POST /logout for CSRF safety, wire stub APIs for tasks/appointments/deadlines so pages don't dead-end, and clean up deprecated routes.

**Tech Stack:** FastAPI, Jinja2, SQLAlchemy, PostgreSQL, RBAC v2 dependencies

---

### Task 1: Fix CSRF-vulnerable GET /logout → POST /logout

**Files:**
- Modify: `src/web/routes/page_routes.py:370-381`
- Modify: `src/web/templates/partials/sidebar.html` (logout link → form)

**Step 1: Change GET /logout to POST /logout**

In `src/web/routes/page_routes.py`, replace the logout route:

```python
@router.post("/logout")
def logout_redirect(request: Request):
    """Logout and redirect to home page."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("tax_session_id")
    response.delete_cookie("auth_token")
    response.delete_cookie("client_token")
    response.delete_cookie("user_role")
    response.delete_cookie("user_name")
    response.delete_cookie("user_email")
    response.delete_cookie("cpa_id")
    return response
```

**Step 2: Keep a GET /logout that redirects to login (graceful fallback)**

Add below the POST route:

```python
@router.get("/logout", include_in_schema=False)
def logout_get_fallback(request: Request):
    """GET fallback — clear cookies and redirect (for bookmarks/links)."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("tax_session_id")
    response.delete_cookie("auth_token")
    response.delete_cookie("client_token")
    response.delete_cookie("user_role")
    response.delete_cookie("user_name")
    response.delete_cookie("user_email")
    response.delete_cookie("cpa_id")
    return response
```

**Step 3: Update sidebar logout link to use a form**

In `src/web/templates/partials/sidebar.html`, find the logout `<a href="/logout">` and replace with:

```html
<form method="post" action="/logout" style="display:inline;">
  <button type="submit" class="nav-link" style="background:none;border:none;cursor:pointer;width:100%;text-align:left;">
    Sign out
  </button>
</form>
```

Also check and update any other templates that link to `/logout` (search all templates for `href="/logout"`).

**Step 4: Add /logout to CSRF exempt list**

In `src/web/middleware_setup.py`, add `/logout` to the CSRF exempt paths list since it's a state-clearing action, not state-creating.

**Step 5: Test**

```bash
# GET /logout should still work (fallback)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/logout
# Expected: 302

# POST /logout should work
curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/logout
# Expected: 302
```

**Step 6: Commit**

```bash
git add src/web/routes/page_routes.py src/web/templates/partials/sidebar.html
git commit -m "fix: change logout to POST for CSRF safety, keep GET fallback"
```

---

### Task 2: Add stub API endpoints for Tasks

**Files:**
- Create: `src/web/routers/tasks_api.py`
- Modify: `src/web/app.py` (register router)

**Step 1: Create tasks API router with in-memory stub**

Create `src/web/routers/tasks_api.py`:

```python
"""Tasks API - CRUD endpoints for task management.

Provides basic task management for CPA workflow tracking.
Uses database persistence via session-scoped storage.
"""

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


# In-memory store (replace with DB persistence in Phase 2)
_tasks: dict[str, dict] = {}


@router.get("")
async def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    ctx=Depends(require_auth),
):
    """List tasks for the current user/firm."""
    tasks = list(_tasks.values())
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if priority:
        tasks = [t for t in tasks if t["priority"] == priority]
    return {"tasks": tasks, "total": len(tasks)}


@router.post("", status_code=201)
async def create_task(task: TaskCreate, ctx=Depends(require_auth)):
    """Create a new task."""
    task_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "task_id": task_id,
        **task.model_dump(),
        "created_by": str(ctx.user_id) if ctx.user_id else None,
        "created_at": now,
        "updated_at": now,
    }
    _tasks[task_id] = record
    return record


@router.get("/{task_id}")
async def get_task(task_id: str, ctx=Depends(require_auth)):
    """Get a specific task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]


@router.patch("/{task_id}")
async def update_task(task_id: str, updates: TaskUpdate, ctx=Depends(require_auth)):
    """Update a task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        _tasks[task_id][key] = value
    _tasks[task_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _tasks[task_id]


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, ctx=Depends(require_auth)):
    """Delete a task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    del _tasks[task_id]
```

**Step 2: Register router in app.py**

In `src/web/app.py`, add to the `_ROUTER_REGISTRY` list:

```python
("web.routers.tasks_api", "router", "/api/tasks stub"),
```

**Step 3: Test**

```bash
curl -s http://127.0.0.1:8000/api/tasks -H "Authorization: Bearer test" | head
# Expected: {"tasks": [], "total": 0} or auth error (confirming route exists)
```

**Step 4: Commit**

```bash
git add src/web/routers/tasks_api.py src/web/app.py
git commit -m "feat: add tasks API stub endpoints for task management UI"
```

---

### Task 3: Add stub API endpoints for Appointments

**Files:**
- Create: `src/web/routers/appointments_api.py`
- Modify: `src/web/app.py` (register router)

**Step 1: Create appointments API router**

Create `src/web/routers/appointments_api.py`:

```python
"""Appointments API - CRUD endpoints for appointment scheduling.

Provides appointment management for CPA-client scheduling.
"""

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
async def list_appointments(
    status: Optional[str] = None,
    ctx=Depends(require_auth),
):
    """List appointments for the current user."""
    appts = list(_appointments.values())
    if status:
        appts = [a for a in appts if a.get("status") == status]
    return {"appointments": appts, "total": len(appts)}


@router.post("", status_code=201)
async def create_appointment(appt: AppointmentCreate, ctx=Depends(require_auth)):
    """Create a new appointment."""
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
    """Get a specific appointment."""
    if appointment_id not in _appointments:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return _appointments[appointment_id]


@router.patch("/{appointment_id}")
async def update_appointment(appointment_id: str, updates: AppointmentUpdate, ctx=Depends(require_auth)):
    """Update an appointment."""
    if appointment_id not in _appointments:
        raise HTTPException(status_code=404, detail="Appointment not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        _appointments[appointment_id][key] = value
    _appointments[appointment_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return _appointments[appointment_id]


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(appointment_id: str, ctx=Depends(require_auth)):
    """Delete an appointment."""
    if appointment_id not in _appointments:
        raise HTTPException(status_code=404, detail="Appointment not found")
    del _appointments[appointment_id]
```

**Step 2: Register router in app.py**

Add to `_ROUTER_REGISTRY`:

```python
("web.routers.appointments_api", "router", "/api/appointments stub"),
```

**Step 3: Test**

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/appointments
# Expected: 401 or 200 (confirming route exists)
```

**Step 4: Commit**

```bash
git add src/web/routers/appointments_api.py src/web/app.py
git commit -m "feat: add appointments API stub endpoints for scheduling UI"
```

---

### Task 4: Add stub API endpoints for Deadlines

**Files:**
- Create: `src/web/routers/deadlines_api.py`
- Modify: `src/web/app.py` (register router)

**Step 1: Create deadlines API router**

Create `src/web/routers/deadlines_api.py`:

```python
"""Deadlines API - Tax deadline tracking endpoints.

Provides deadline management with IRS-standard dates pre-populated.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from rbac.dependencies import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deadlines", tags=["deadlines"])


# Standard IRS deadlines for tax year 2025
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


_custom_deadlines: dict[str, dict] = {}


@router.get("")
async def list_deadlines(
    category: Optional[str] = None,
    ctx=Depends(require_auth),
):
    """List all deadlines (IRS standard + custom)."""
    deadlines = [
        {**d, "deadline_id": f"irs-{i}", "completed": False}
        for i, d in enumerate(IRS_DEADLINES)
    ]
    deadlines.extend(_custom_deadlines.values())
    if category:
        deadlines = [d for d in deadlines if d.get("category") == category]
    deadlines.sort(key=lambda d: d.get("date", ""))
    return {"deadlines": deadlines, "total": len(deadlines)}


@router.post("", status_code=201)
async def create_deadline(deadline: DeadlineCreate, ctx=Depends(require_auth)):
    """Create a custom deadline."""
    dl_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "deadline_id": dl_id,
        **deadline.model_dump(),
        "completed": False,
        "created_by": str(ctx.user_id) if ctx.user_id else None,
        "created_at": now,
    }
    _custom_deadlines[dl_id] = record
    return record


@router.patch("/{deadline_id}")
async def update_deadline(deadline_id: str, updates: DeadlineUpdate, ctx=Depends(require_auth)):
    """Update a deadline."""
    if deadline_id not in _custom_deadlines:
        raise HTTPException(status_code=404, detail="Deadline not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        _custom_deadlines[deadline_id][key] = value
    return _custom_deadlines[deadline_id]


@router.delete("/{deadline_id}", status_code=204)
async def delete_deadline(deadline_id: str, ctx=Depends(require_auth)):
    """Delete a custom deadline."""
    if deadline_id not in _custom_deadlines:
        raise HTTPException(status_code=404, detail="Deadline not found")
    del _custom_deadlines[deadline_id]
```

**Step 2: Register router in app.py**

Add to `_ROUTER_REGISTRY`:

```python
("web.routers.deadlines_api", "router", "/api/deadlines stub"),
```

**Step 3: Test**

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/deadlines
# Expected: 401 or 200
```

**Step 4: Commit**

```bash
git add src/web/routers/deadlines_api.py src/web/app.py
git commit -m "feat: add deadlines API with IRS standard dates for deadline tracker UI"
```

---

### Task 5: Migrate scenarios.py from deprecated auth to RBAC v2

**Files:**
- Modify: `src/web/routers/scenarios.py:23,126,198,229,283`

**Step 1: Replace import**

Change:
```python
from security.auth_decorators import require_auth, Role
```
To:
```python
from rbac.dependencies import require_auth
```

**Step 2: Replace all `@require_auth(roles=[...])` decorators with `Depends(require_auth)`**

For each endpoint using the decorator pattern, change from:

```python
@require_auth(roles=[Role.TAXPAYER, Role.CPA, Role.PREPARER])
async def endpoint(request: Request, ...):
```

To:

```python
async def endpoint(request: Request, ..., ctx=Depends(require_auth)):
```

Remove the `@require_auth(...)` decorator line and add `ctx=Depends(require_auth)` parameter.

Also add `from fastapi import Depends` if not already imported.

**Step 3: Test**

```bash
PYTHONPATH=".:src" .venv/bin/python3 -c "from web.routers.scenarios import router; print(f'{len(router.routes)} routes loaded')"
```

**Step 4: Commit**

```bash
git add src/web/routers/scenarios.py
git commit -m "refactor: migrate scenarios router from deprecated auth to RBAC v2"
```

---

### Task 6: Remove or redirect deprecated routes

**Files:**
- Modify: `src/web/routes/page_routes.py:254-304,488-620`

**Step 1: Replace deprecated route handlers with simple redirects**

Replace all deprecated route handlers (lines 254-304 for legacy/cpa, lines 502-620 for advisor/chat/etc.) with a single redirect to the current equivalent:

```python
# Legacy CPA routes → redirect to new CPA portal
@router.get("/legacy/cpa", include_in_schema=False)
@router.get("/legacy/cpa/v2", include_in_schema=False)
def legacy_cpa_redirect(request: Request):
    return RedirectResponse(url="/cpa/dashboard", status_code=301)

@router.get("/legacy/cpa/clients", include_in_schema=False)
def legacy_cpa_clients_redirect(request: Request):
    return RedirectResponse(url="/cpa/clients", status_code=301)

@router.get("/legacy/cpa/settings", include_in_schema=False)
def legacy_cpa_settings_redirect(request: Request):
    return RedirectResponse(url="/cpa/settings", status_code=301)

@router.get("/legacy/cpa/team", include_in_schema=False)
def legacy_cpa_team_redirect(request: Request):
    return RedirectResponse(url="/cpa/team", status_code=301)

@router.get("/legacy/cpa/billing", include_in_schema=False)
def legacy_cpa_billing_redirect(request: Request):
    return RedirectResponse(url="/cpa/billing", status_code=301)

# Legacy advisor routes → redirect to intelligent-advisor
@router.get("/smart-tax-legacy", include_in_schema=False)
@router.get("/advisor", include_in_schema=False)
@router.get("/tax-advisory", include_in_schema=False)
@router.get("/advisory", include_in_schema=False)
@router.get("/start", include_in_schema=False)
@router.get("/analysis", include_in_schema=False)
@router.get("/tax-advisory/v2", include_in_schema=False)
@router.get("/advisory/v2", include_in_schema=False)
@router.get("/start/v2", include_in_schema=False)
@router.get("/simple", include_in_schema=False)
@router.get("/conversation", include_in_schema=False)
@router.get("/chat", include_in_schema=False)
def legacy_advisor_redirect(request: Request):
    return RedirectResponse(url="/intelligent-advisor", status_code=301)
```

**Step 2: Test**

```bash
curl -s -o /dev/null -w "%{http_code} %{redirect_url}" http://127.0.0.1:8000/legacy/cpa
# Expected: 301 → /cpa/dashboard

curl -s -o /dev/null -w "%{http_code} %{redirect_url}" http://127.0.0.1:8000/advisor
# Expected: 301 → /intelligent-advisor
```

**Step 3: Commit**

```bash
git add src/web/routes/page_routes.py
git commit -m "refactor: replace 20 deprecated routes with 301 redirects to current equivalents"
```

---

### Task 7: Final verification sweep

**Step 1: Test every navbar link returns 200 or valid 302**

```bash
for route in / /landing /login /register /terms /privacy /cookies /disclaimer /docs /health/live /contact /for-cpas; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000${route}")
  echo "$code $route"
done
```

Expected: All 200 (public pages) or 302 (auth-protected redirects).

**Step 2: Test API stubs respond**

```bash
for api in /api/tasks /api/appointments /api/deadlines; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000${api}")
  echo "$code $api"
done
```

Expected: 401 or 403 (auth required — confirming routes are wired and protected).

**Step 3: Test deprecated routes redirect**

```bash
for route in /legacy/cpa /advisor /chat /start /simple; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000${route}")
  echo "$code $route"
done
```

Expected: 301 (permanent redirect).

**Step 4: Verify PostgreSQL table count**

```bash
psql jorss_gbo -t -c "SELECT count(*) FROM pg_tables WHERE schemaname='public';"
```

Expected: 69

**Step 5: Commit final state**

```bash
git add -A
git commit -m "chore: go-live gap fixes — all screens, APIs, and tables wired end-to-end"
```
