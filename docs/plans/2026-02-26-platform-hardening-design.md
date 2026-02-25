# Platform Hardening Design — Security, RBAC, UX

**Date**: 2026-02-26
**Context**: US-only B2B SaaS for CPAs. Full hardening pass — security + RBAC + UX.
**Approach**: Wire existing infrastructure (Approach A). Most systems already built but not connected.

---

## Key Discovery: What Already Exists

| Component | Location | Status |
|-----------|----------|--------|
| Token refresh endpoint | `POST /auth/refresh` at `auth_routes.py:312` | Built, no client interceptor |
| showToast() | `core/utils.js:380`, global `window.TaxUtils.showToast()` | Built, unused (54 alert() calls) |
| Error pages 403/404/500 | `templates/errors/{code}.html` | Built, handler already wires to them |
| Skeleton macros | `components/feedback/loading.html` (5 types) | Built, no template imports them |
| Permission dependencies | `rbac/dependencies.py:435-512` `require_permission()` | Built, no route uses it |
| Redis | Rate limiting + caching backend | Running |
| API client w/ CSRF | `core/api.js` centralized fetch | Built |
| Toast container | `foot_scripts.html:85` on all pages | Wired |
| jti extraction | `dependencies.py` reads `payload.get("jti")` | Prepared, but tokens lack jti |

---

## Section 1: Security Wiring

### 1A. Client-Side 401 → Token Refresh Interceptor

**File**: `src/web/static/js/core/api.js`

In the `request()` function error path, before redirecting to login on 401:
1. Attempt `POST /api/v1/auth/refresh` with refresh token from `auth_refresh_token` cookie
2. If 200: update access token cookie, retry original request once
3. If fail: redirect to `/login?next={current_path}`
4. Flag to prevent infinite refresh loops (`_isRefreshing`)

### 1B. Token Revocation via jti + Redis Blacklist

**Files**: `src/rbac/jwt.py`, `src/core/rbac/middleware.py`, `src/core/api/auth_routes.py`

- Add `"jti": str(uuid4())` to access + refresh token payloads in jwt.py
- In RBAC middleware dispatch(), after decode: `SISMEMBER revoked_jtis {jti}` → reject if found
- In logout endpoint: `SADD revoked_jtis {jti}` with EXPIRE matching remaining token TTL
- Graceful fallback: if Redis unavailable, skip revocation check (don't block auth)

### 1C. Narrow CSRF Exemptions

**File**: `src/web/app.py` (~line 280)

Remove from exempt list:
- `/api/health/resilience/reset` (state-changing admin op)
- `/api/health/cache/flush` (state-changing admin op)

Add `_require_admin_page_access` guard to both handlers if missing.

### 1D. Per-User Rate Limiting

**File**: `src/security/middleware.py` (RateLimitMiddleware)

After IP extraction, check `request.state.rbac`:
- If authenticated: key = `user:{user_id}`, limit = 120 req/min
- If anonymous: key = `ip:{client_ip}`, limit = 60 req/min
- Use existing Redis backend with same sliding window algorithm

---

## Section 2: RBAC Hardening

### 2A. Permission Enforcement on Critical Endpoints

**File**: `src/web/app.py`

Add `Depends(require_permission(Permission.X))` to:
- `POST /api/returns/{id}/approve` → `RETURN_APPROVE`
- `POST /api/returns/{id}/submit-for-review` → `RETURN_SUBMIT`
- `DELETE /api/returns/{id}` → `RETURN_EDIT`
- `DELETE /api/documents/{id}` → `DOCUMENT_DELETE`
- `POST /api/returns/{id}/notes` → `RETURN_REVIEW`

These endpoints already have `@require_auth(roles=[...])`. Permission check is additive — role check passes first, then permission granularity.

### 2B. Tenant Isolation on Document Endpoints

**File**: `src/web/app.py`

Apply the returns IDOR pattern (lines 4827-4841) to:
- `GET /api/documents/{id}` — verify requesting user's firm_id matches document's
- `GET /api/documents` — filter results by authenticated user's firm_id
- `GET /api/returns/{id}/notes` — verify session ownership before returning

Note: Public calculation endpoints (estimate, entity-comparison, interview) are intentionally stateless — no tenant isolation needed.

---

## Section 3: UX Polish

### 3A. Replace alert() → showToast()

54 templates use `alert()`. `showToast(msg, type, duration)` is globally available.

Mapping:
- `alert("Error: ...")` / `alert("Failed...")` → `showToast("...", "error")`
- `alert("Success...")` / `alert("Saved...")` → `showToast("...", "success")`
- `alert("...")` generic → `showToast("...", "info")`

Batch by group: CPA templates (12 files), lead magnet (4 files), admin (3 files), feature pages (8 files), other (27 files).

### 3B. Wire Skeleton Loading into Data Pages

**Files**: 4 high-traffic templates

Add `{% from 'components/feedback/loading.html' import skeleton %}` and wrap data sections:

- `cpa/dashboard.html` — skeleton cards for stats
- `cpa/leads_list.html` — skeleton table-row for leads table
- `cpa/clients.html` — skeleton table-row for clients table
- `client_portal.html` — skeleton cards for portal widgets

Pattern: Alpine.js `x-show="!dataLoaded"` shows skeleton, `x-show="dataLoaded"` shows real content.

### 3C. Verify Error Page Rendering

Confirm `errors/403.html`, `404.html`, `500.html` render via Jinja2 (not fallback inline HTML). These are standalone HTML files — verify they don't need template context to render.

---

## Task Summary

| # | Task | Type | Risk | Est |
|---|------|------|------|-----|
| 1A | 401→refresh interceptor | Wire | Low | JS only |
| 1B | jti + token revocation | Build | Med | 3 files |
| 1C | Narrow CSRF exemptions | Wire | Low | 1 file |
| 1D | Per-user rate limiting | Wire | Med | 1 file |
| 2A | Permission enforcement | Wire | Low | 1 file |
| 2B | Tenant isolation docs | Wire | Low | 1 file |
| 3A | alert() → showToast() | Wire | Low | 54 files |
| 3B | Skeleton loading states | Wire | Low | 4 files |
| 3C | Error page verification | Test | None | 3 files |
