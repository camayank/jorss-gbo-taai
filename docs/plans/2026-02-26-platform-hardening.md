# Platform Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire existing built-but-unconnected security, RBAC, and UX infrastructure into a fully hardened platform.

**Architecture:** Approach A — Wire Everything. Most components (refresh endpoint, showToast, skeleton macros, error pages, permission dependencies) already exist. We connect them. One small build (jti + revocation). 54-file UX sweep for alert→toast.

**Tech Stack:** FastAPI/Starlette, JWT (HS256), Redis, Jinja2, Alpine.js, vanilla JS (api.js/utils.js)

---

## Task 1: 401 → Token Refresh Interceptor

**Files:**
- Modify: `src/web/static/js/core/api.js:242-246`

**Step 1: Add refresh interceptor logic**

In `api.js`, replace the current 4xx catch-all at line 242-246:

```javascript
// Current (line 242-246):
if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
  // Loading state already handled in response.ok check
  throw error;
}
```

Replace with:

```javascript
if (error instanceof ApiError) {
  // Attempt token refresh on 401 before giving up
  if (error.status === 401 && !options._isRetryAfterRefresh) {
    try {
      const refreshResp = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
      });
      if (refreshResp.ok) {
        // Retry the original request once
        return request(url, { ...options, _isRetryAfterRefresh: true });
      }
    } catch (_) {
      // Refresh failed — fall through to login redirect
    }
    // Redirect to login with return URL
    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    return;
  }

  if (error.status >= 400 && error.status < 500) {
    throw error;
  }
}
```

**Step 2: Verify no regressions**

Run: Manual test — open browser devtools, confirm no JS syntax errors. Verify existing API calls still work.

**Step 3: Commit**

```bash
git add src/web/static/js/core/api.js
git commit -m "feat(auth): wire 401→refresh token interceptor in api.js"
```

---

## Task 2: Token Revocation via jti + Redis Blacklist

**Files:**
- Modify: `src/rbac/jwt.py:110-118` (access token payload) and `src/rbac/jwt.py:144-148` (refresh token payload)
- Modify: `src/core/rbac/middleware.py:128-135` (dispatch token check)
- Modify: `src/core/api/auth_routes.py:334-344` (logout endpoint)

### Step 1: Add jti to token payloads

**File:** `src/rbac/jwt.py`

Add `from uuid import uuid4` to existing imports (line 10, alongside `from uuid import UUID`).

In `create_access_token`, add `"jti"` to payload dict (line 110-119):

```python
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "role": role.value,
        "user_type": user_type,
        "jti": str(uuid4()),
        "iat": issued_at,
        "exp": expire,
        "type": "access",
    }
```

In `create_refresh_token`, add `"jti"` to payload dict (line 144-149):

```python
    payload = {
        "sub": str(user_id),
        "user_type": user_type,
        "jti": str(uuid4()),
        "exp": expire,
        "type": "refresh",
    }
```

### Step 2: Add jti blacklist check in middleware

**File:** `src/core/rbac/middleware.py`

After token decode at line 130-135, add Redis blacklist check:

```python
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            payload = decode_token_safe(auth_header[7:])
            if payload:
                # Check jti revocation blacklist
                jti = payload.get("jti")
                if jti and await self._is_token_revoked(jti):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Token has been revoked"},
                    )
                ctx = _build_context_from_token_payload(payload)
                if ctx:
                    request.state.rbac = ctx
                    return await call_next(request)
```

Add the helper method to `RBACMiddleware` class:

```python
    async def _is_token_revoked(self, jti: str) -> bool:
        """Check if token jti is in Redis revocation blacklist."""
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(
                os.environ.get("REDIS_URL", "redis://localhost:6379"),
                decode_responses=True,
            )
            result = await r.sismember("revoked_jtis", jti)
            await r.aclose()
            return bool(result)
        except Exception:
            # Graceful fallback: if Redis unavailable, skip revocation check
            return False
```

Add `import os` to the top of the file.

### Step 3: Add jti revocation on logout

**File:** `src/core/api/auth_routes.py`

The logout endpoint is at line 334. We need to add token revocation before the existing logic. Find the `logout` function and add jti extraction + Redis SADD:

After `async def logout(...)` (line 335), before `return await auth_service.logout(refresh_token)`, add:

```python
    # Revoke current token jtis via Redis blacklist
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
        if refresh_token:
            from rbac.jwt import decode_token_safe
            payload = decode_token_safe(refresh_token)
            if payload and payload.get("jti"):
                ttl = max(int(payload.get("exp", 0) - __import__("time").time()), 0)
                if ttl > 0:
                    await r.sadd("revoked_jtis", payload["jti"])
                    await r.expire("revoked_jtis", ttl)
        await r.aclose()
    except Exception:
        pass  # Graceful fallback — don't block logout if Redis is down
```

### Step 4: Commit

```bash
git add src/rbac/jwt.py src/core/rbac/middleware.py src/core/api/auth_routes.py
git commit -m "feat(auth): add jti claim + Redis revocation blacklist for token logout"
```

---

## Task 3: Narrow CSRF Exemptions

**Files:**
- Modify: `src/web/app.py:280-313` (CSRF exempt paths)
- Modify: `src/web/app.py:3209-3230` (resilience reset handler)
- Modify: `src/web/app.py:3273-3290` (cache flush handler)

### Step 1: Remove state-changing endpoints from CSRF exempt list

Currently NOT in the exempt list — verify these are NOT exempt. The health endpoints `/api/health/resilience/reset` and `/api/health/cache/flush` are POST endpoints. Check if they match any prefix in the exempt list.

Looking at line 282: `/api/health` is in the exempt list as a read-only endpoint. But the POST sub-paths `/api/health/resilience/reset` and `/api/health/cache/flush` match this prefix via CSRFMiddleware path matching.

**Fix:** Replace the broad `/api/health` exempt entry with specific read-only paths:

```python
        "/api/health",                  # Read-only: System health status (GET only)
```

Change to:

```python
        "/api/health/status",           # Read-only: GET health check
```

Wait — need to check how CSRFMiddleware matches paths (exact vs prefix).

### Step 2: Check CSRFMiddleware matching logic

Read `src/security/middleware.py` CSRFMiddleware to understand if `/api/health` is exact match or prefix match.

### Step 3: Add admin auth guard to health mutation endpoints

**File:** `src/web/app.py`

Add `_require_admin_page_access` check to both POST handlers:

At line 3209, `reset_circuit_breakers`:
```python
@app.post("/api/health/resilience/reset")
async def reset_circuit_breakers(request: Request):
    """Reset all circuit breakers. Admin only."""
    redirect = _require_admin_page_access(request)
    if redirect:
        return JSONResponse(status_code=403, content={"detail": "Admin access required"})
    # ... existing logic
```

At line 3273, `flush_cache`:
```python
@app.post("/api/health/cache/flush")
async def flush_cache(request: Request):
    """Flush caches. Admin only."""
    redirect = _require_admin_page_access(request)
    if redirect:
        return JSONResponse(status_code=403, content={"detail": "Admin access required"})
    # ... existing logic
```

### Step 4: Commit

```bash
git add src/web/app.py
git commit -m "fix(security): add admin auth to health mutation endpoints"
```

---

## Task 4: Per-User Rate Limiting

**Files:**
- Modify: `src/security/middleware.py:450-475` (RateLimitMiddleware.dispatch)

### Step 1: Add user-aware rate limit key

In `RateLimitMiddleware.dispatch()` at line 460, after `client_ip = self._get_client_ip(request)`, add user-aware key logic:

Replace lines 460-464:

```python
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit
        allowed = self._backend.check_rate_limit(
            client_ip, self.requests_per_minute, self.burst_size
        )
```

With:

```python
        # Determine rate limit key and limit based on auth status
        client_ip = self._get_client_ip(request)
        rbac_ctx = getattr(getattr(request, 'state', None), 'rbac', None)

        if rbac_ctx and getattr(rbac_ctx, 'is_authenticated', False):
            rate_key = f"user:{rbac_ctx.user_id}"
            rate_limit = self.requests_per_minute * 2  # 120/min for authenticated
        else:
            rate_key = f"ip:{client_ip}"
            rate_limit = self.requests_per_minute  # 60/min for anonymous

        # Check rate limit
        allowed = self._backend.check_rate_limit(
            rate_key, rate_limit, self.burst_size
        )
```

### Step 2: Commit

```bash
git add src/security/middleware.py
git commit -m "feat(security): add per-user rate limiting with 2x limit for authenticated users"
```

---

## Task 5: Permission Enforcement on Critical Endpoints

**Files:**
- Modify: `src/web/app.py` (5 endpoint handlers)

### Step 1: Add import for require_permission and Permission

At `src/web/app.py` line 138-144, add to the existing import block:

```python
from security.auth_decorators import (
    require_auth,
    require_session_owner,
    rate_limit,
    Role,
    get_user_from_request,
)
from rbac.dependencies import require_permission
from rbac.permissions import Permission
```

### Step 2: Add permission decorators to 5 endpoints

**Endpoint 1:** `POST /api/returns/{session_id}/approve` (line 5226)

Add after `@require_auth`:
```python
@app.post("/api/returns/{session_id}/approve", operation_id="approve_return_cpa_signoff")
@require_auth(roles=[Role.CPA])
@require_permission(Permission.RETURN_APPROVE)
@require_session_owner(session_param="session_id")
async def approve_return_cpa_signoff(session_id: str, request: Request):
```

**Endpoint 2:** `POST /api/returns/{session_id}/submit-for-review` — search for this endpoint.

**Endpoint 3:** `DELETE /api/returns/{return_id}` (line 5020)

Add after `@require_auth`:
```python
@app.delete("/api/returns/{return_id}")
@require_auth(roles=[Role.TAXPAYER, Role.CPA, Role.ADMIN])
@require_permission(Permission.RETURN_EDIT)
async def delete_saved_return(return_id: str, request: Request):
```

**Endpoint 4:** `DELETE /api/documents/{document_id}` (line 3125)

Add after `@require_auth`:
```python
@app.delete("/api/documents/{document_id}")
@require_auth(roles=[Role.TAXPAYER, Role.CPA, Role.PREPARER])
@require_permission(Permission.DOCUMENT_DELETE)
async def delete_document(document_id: str, request: Request):
```

**Endpoint 5:** `POST /api/returns/{session_id}/notes` (line 5573)

Add after `@require_auth`:
```python
@app.post("/api/returns/{session_id}/notes")
@require_auth(roles=[Role.CPA, Role.PREPARER, Role.ADMIN])
@require_permission(Permission.RETURN_REVIEW)
@require_session_owner(session_param="session_id")
async def add_cpa_note(session_id: str, request: Request):
```

### Step 3: Commit

```bash
git add src/web/app.py
git commit -m "feat(rbac): enforce granular permissions on 5 critical endpoints"
```

---

## Task 6: Tenant Isolation on Document Endpoints

**Files:**
- Modify: `src/web/app.py` (document GET endpoints)

### Step 1: Find document GET endpoints

Search for `GET /api/documents` endpoints in `app.py`. Apply the IDOR pattern from lines 4827-4841 (used on returns):

For `GET /api/documents/{document_id}`: After fetching the document, verify the requesting user's firm_id matches the document's tenant/firm_id. If mismatch and not admin, return 403.

For `GET /api/documents`: Filter query results by the authenticated user's firm_id.

For `GET /api/returns/{session_id}/notes`: Already has `@require_session_owner` — verify this is sufficient (it should be since session ownership implies tenant access).

### Step 2: Add firm_id check to document GET

Apply the same pattern as the returns IDOR check:

```python
    # SECURITY: Tenant isolation — verify document belongs to user's firm
    user = _request_user_dict(request)
    if user:
        user_role = str(user.get("role") or "").lower()
        is_admin = user_role == Role.ADMIN.value
        user_firm = str(user.get("firm_id") or "")
        doc_firm = str(doc_record.get("firm_id") or doc_record.get("tenant_id") or "")
        if doc_firm and user_firm and doc_firm != user_firm and not is_admin:
            raise HTTPException(status_code=403, detail="Access denied")
```

### Step 3: Commit

```bash
git add src/web/app.py
git commit -m "fix(security): add tenant isolation to document GET endpoints"
```

---

## Task 7: Replace alert() → showToast()

**Files:**
- Modify: ~31 template files in `src/web/templates/`

### Step 1: Batch replacement

`showToast(msg, type, duration)` is globally available as `window.TaxUtils.showToast()` on every page (loaded via `foot_scripts.html:18`).

Mapping rules:
- `alert("Error: ...")` / `alert("Failed...")` → `showToast("...", "error")`
- `alert("Success...")` / `alert("Saved...")` / `alert("Done...")` → `showToast("...", "success")`
- `alert("...")` generic/info → `showToast("...", "info")`

Process each template file:
1. Find all `alert(` calls
2. Classify by error/success/info based on message content
3. Replace with appropriate `showToast()` call
4. Verify the `showToast` function signature: `showToast(message, type='info', duration=3000)`

### Step 2: Commit per batch

```bash
# CPA templates
git add src/web/templates/cpa/
git commit -m "refactor(ux): replace alert() with showToast() in CPA templates"

# Admin templates
git add src/web/templates/admin/
git commit -m "refactor(ux): replace alert() with showToast() in admin templates"

# Remaining templates
git add src/web/templates/
git commit -m "refactor(ux): replace alert() with showToast() in remaining templates"
```

---

## Task 8: Wire Skeleton Loading into Data Pages

**Files:**
- Modify: `src/web/templates/cpa/dashboard.html`
- Modify: `src/web/templates/cpa/leads_list.html`
- Modify: `src/web/templates/cpa/clients.html`
- Modify: `src/web/templates/client_portal.html`

### Step 1: Import skeleton macro

Add at the top of each template's block content:

```jinja2
{% from 'components/feedback/loading.html' import skeleton %}
```

### Step 2: Wrap data sections

Pattern: Alpine.js `x-show` toggle:

```html
<!-- Skeleton placeholder -->
<div x-show="!dataLoaded" x-cloak>
  {{ skeleton(type="card", count=3) }}
</div>

<!-- Real content -->
<div x-show="dataLoaded" x-cloak>
  <!-- existing content -->
</div>
```

Apply to:
- `cpa/dashboard.html` — stats cards section → `skeleton(type="card", count=4)`
- `cpa/leads_list.html` — leads table → `skeleton(type="table-row", count=5)`
- `cpa/clients.html` — clients table → `skeleton(type="table-row", count=5)`
- `client_portal.html` — portal widgets → `skeleton(type="card", count=3)`

### Step 3: Commit

```bash
git add src/web/templates/cpa/dashboard.html src/web/templates/cpa/leads_list.html src/web/templates/cpa/clients.html src/web/templates/client_portal.html
git commit -m "feat(ux): wire skeleton loading states into 4 data-heavy pages"
```

---

## Task 9: Verify Error Page Rendering

**Files:**
- Verify: `src/web/templates/errors/403.html`
- Verify: `src/web/templates/errors/404.html`
- Verify: `src/web/templates/errors/500.html`

### Step 1: Check error pages are standalone

Read each error page template. Verify they:
1. Don't extend a base template that requires auth context (would fail on unauthenticated errors)
2. Have complete HTML structure (doctype, head, body)
3. Include appropriate styling (inline or linked)

### Step 2: Check error handler wiring

Verify `app.py` error handlers at ~line 829-872 render these templates via Jinja2 (not inline HTML fallback).

### Step 3: Fix any issues found

If error pages extend base.html that requires user context, make them standalone.

### Step 4: Commit (only if changes needed)

```bash
git add src/web/templates/errors/
git commit -m "fix(ux): ensure error pages render without auth context"
```

---

## Execution Order & Dependencies

| Task | Depends On | Risk |
|------|-----------|------|
| 1 (refresh interceptor) | None | Low — JS only |
| 2 (jti revocation) | None | Med — 3 files, Redis |
| 3 (CSRF narrow) | None | Low — config only |
| 4 (rate limiting) | None | Med — middleware change |
| 5 (permissions) | None | Low — additive |
| 6 (tenant isolation) | None | Low — additive |
| 7 (alert→toast) | None | Low — template-only |
| 8 (skeleton loading) | None | Low — template-only |
| 9 (error pages) | None | None — verification |

All tasks are independent. Tasks 1-6 are security/RBAC. Tasks 7-9 are UX. Can be parallelized.

## Verification

After all tasks:
1. `python3 scripts/audit_routes.py` — 0 auth gaps, 0 new warnings
2. Browser: trigger 401 → verify refresh attempt → retry or login redirect
3. Browser: logout → verify old token is rejected (jti blacklisted)
4. Browser: non-admin POST to `/api/health/resilience/reset` → 403
5. Browser: client role → `/api/returns/{id}/approve` → 403 (missing RETURN_APPROVE)
6. Browser: wrong firm → `GET /api/documents/{id}` → 403
7. Browser: any action that used alert() → now shows toast notification
8. Browser: CPA dashboard load → skeleton cards visible briefly → real content
9. Browser: navigate to `/nonexistent-page` → styled 404 page
