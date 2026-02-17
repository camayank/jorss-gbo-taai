# P0 Launch Blocker Checklist (Environment/Setup + Access Control)

## Scope
This checklist resolves the highest-risk launch blockers found in the route/access audit.

## Blocker 1: Duplicate route auth conflicts (critical)
### Problem
Protected legacy endpoints in `src/web/app.py` overlap with unprotected modular endpoints in `src/web/routers/*`.

### Impact
Requests may hit unprotected handlers first, bypassing role checks.

### Files in scope
- `src/web/app.py`
- `src/web/routers/returns.py`
- `src/web/routers/documents.py`
- `src/web/routers/calculations.py`

### Required fix
1. Choose a single owner for each overlapping route family.
2. Prefer modular routers as owner.
3. Apply equivalent auth/role guards to modular handlers.
4. Remove or disable overlapping legacy handlers in `src/web/app.py`.
5. Keep route contracts backward-compatible.

### Acceptance checks
- No duplicate method+path entries with conflicting auth for:
  - `/api/returns/*`
  - `/api/upload*`, `/api/documents*`
  - `/api/calculate*`, `/api/optimize*`
- Unauthorized requests return `401/403` consistently.

---

## Blocker 2: Open internal CPA Panel modules (critical)
### Problem
Most `src/cpa_panel/api/*_routes.py` modules are exposed without route-level auth dependency.

### Impact
Internal practice APIs are publicly callable.

### Files in scope (primary)
- `src/cpa_panel/api/router.py`
- `src/cpa_panel/api/task_routes.py`
- `src/cpa_panel/api/deadline_routes.py`
- `src/cpa_panel/api/appointment_routes.py`
- `src/cpa_panel/api/workflow_routes.py`
- `src/cpa_panel/api/analysis_routes.py`
- `src/cpa_panel/api/lead_routes.py`
- `src/cpa_panel/api/report_routes.py`
- `src/cpa_panel/api/*_routes.py` (all non-portal modules)

### Required fix
1. Add default auth dependency for CPA panel internal routers.
2. Keep `client_portal_routes.py` isolated with client token auth.
3. Keep webhook-like endpoints explicitly documented if intentionally public.
4. Add explicit role checks for CPA-only mutations.

### Acceptance checks
- All internal `/api/cpa/*` endpoints require auth.
- Anonymous requests to internal CPA routes return `401/403`.
- Client portal routes still work with client token flow.

---

## Blocker 3: Open Admin ticket routes (critical)
### Problem
`src/admin_panel/api/ticket_routes.py` has no auth/role dependency.

### Impact
Support ticket admin operations are publicly callable.

### Files in scope
- `src/admin_panel/api/ticket_routes.py`
- `src/admin_panel/api/router.py`

### Required fix
1. Add `Depends(get_current_user)` baseline auth.
2. Add permission/role gates for create/update/assign/delete actions.
3. Restrict cross-firm visibility.

### Acceptance checks
- `/api/v1/admin/tickets*` endpoints are authenticated.
- Role/permission mismatch returns `403`.

---

## Blocker 4: Partial auth gaps in CPA notifications (high)
### Problem
Some notification endpoints do not call auth helper consistently.

### Impact
State-changing operations can run without validated user context.

### Files in scope
- `src/cpa_panel/api/notification_routes.py`

### Required fix
1. Ensure every endpoint calls `_get_authenticated_cpa_email(request)` or equivalent dependency.
2. Bind update operations to authenticated principal.

### Acceptance checks
- Unauthenticated calls to notification write endpoints return `401`.
- Users cannot mutate another CPA's notifications/reminders.

---

## Blocker 5: Admin RBAC route prefix duplication (high)
### Problem
RBAC router path likely resolves to `/api/v1/admin/admin/rbac/*`.

### Files in scope
- `src/admin_panel/api/rbac_routes.py`
- `src/admin_panel/api/router.py`

### Required fix
1. Normalize prefixing to one `/admin/rbac` segment.
2. Keep existing clients working via temporary alias if needed.

### Acceptance checks
- Canonical path is exactly one of:
  - `/api/v1/admin/rbac/*` or
  - `/api/v1/admin/<...>` (single admin segment)
- OpenAPI docs reflect canonical path only.

---

## Blocker 6: Guardrail tests (required for launch)
### Files to add/update
- `tests/security/*`
- `tests/integration/*`

### Required tests
1. Auth required tests for all internal route groups.
2. Permission matrix smoke tests by persona.
3. Duplicate route detection test (method+path + auth metadata).
4. Regression tests for client portal token flow.

### Acceptance checks
- Security/auth test suite passes.
- No newly introduced unguarded internal endpoints.

---

## Execution Order (do not reorder)
1. Duplicate route ownership + auth parity (`web/app.py` + `web/routers/*`).
2. CPA panel baseline auth hardening.
3. Admin tickets auth hardening.
4. Notification auth consistency.
5. RBAC prefix normalization.
6. Security regression tests + CI gate.

---

## Launch Go/No-Go Criteria
Go only if all are true:
- No P0/P1 open access findings remain.
- All internal admin/CPA route families reject anonymous calls.
- Duplicate route conflicts removed or explicitly aliased without weaker auth.
- Security regression tests pass in CI.
