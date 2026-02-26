# Full Platform Remediation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix every security, RBAC, infrastructure, and UX issue found in the 4-dimensional platform audit — then install automated checks so they never regress.

**Architecture:** Six phases in dependency order: (1) Critical security patches, (2) Auth system consolidation, (3) Data persistence migration, (4) RBAC permission enforcement, (5) Code quality & hygiene, (6) Automated verification scripts. Each phase is independently committable and deployable.

**Tech Stack:** Python 3.11+, FastAPI/Starlette, Jinja2, SQLAlchemy 2.x, Redis (aioredis), Pydantic v2, pytest

---

## Phase 1: Critical Security Patches (BLOCKER — fix before any production traffic)

### Task 1: Fix SQL injection in dynamic UPDATE queries

**Files:**
- Modify: `src/core/api/tax_returns_routes.py:566`
- Modify: `src/admin_panel/api/team_routes.py:456`
- Modify: `src/admin_panel/api/workflow_routes.py:826`
- Modify: `src/admin_panel/api/settings_routes.py:400`

**Problem:** All four files build `UPDATE ... SET` clauses via f-string interpolation. Even though WHERE clauses use `:param`, the SET column names come from code that constructs field lists from user-supplied data.

**Step 1:** In each file, add a column whitelist constant at module level:

```python
# tax_returns_routes.py — add near top imports
_RETURN_UPDATABLE_COLUMNS = frozenset({
    "gross_income", "adjusted_gross_income", "taxable_income",
    "total_tax", "filing_status", "status", "notes",
})
```

```python
# team_routes.py
_USER_UPDATABLE_COLUMNS = frozenset({
    "name", "email", "role", "is_active", "phone",
})
```

```python
# workflow_routes.py
_TASK_UPDATABLE_COLUMNS = frozenset({
    "status", "assigned_to", "priority", "due_date", "notes",
})
```

```python
# settings_routes.py
_FIRM_UPDATABLE_COLUMNS = frozenset({
    "firm_name", "phone", "address", "city", "state", "zip_code",
    "website", "logo_url", "timezone", "billing_email",
})
```

**Step 2:** In each file's update handler, validate columns before building the query:

```python
# Example for tax_returns_routes.py — replace the f-string UPDATE block (~line 566)
# BEFORE:
#   update_query = text(f"UPDATE returns SET {', '.join(updates)} WHERE return_id = :return_id")
# AFTER:
for col in requested_columns:
    if col not in _RETURN_UPDATABLE_COLUMNS:
        raise HTTPException(status_code=400, detail=f"Invalid field: {col}")

updates = [f"{col} = :{col}" for col in requested_columns]
update_query = text(f"UPDATE returns SET {', '.join(updates)} WHERE return_id = :return_id")
```

Apply the same pattern to all 4 files. The key change: validate every column name against the whitelist BEFORE building the query string.

**Step 3:** Commit

```bash
git add src/core/api/tax_returns_routes.py src/admin_panel/api/team_routes.py \
        src/admin_panel/api/workflow_routes.py src/admin_panel/api/settings_routes.py
git commit -m "security: add column whitelist to prevent SQL injection in UPDATE queries"
```

---

### Task 2: Fix token revocation to fail CLOSED

**Files:**
- Modify: `src/core/rbac/middleware.py:100-114`

**Problem:** `_is_token_revoked()` returns `False` on Redis failure — revoked tokens pass through when Redis is down.

**Step 1:** Change the except clause:

```python
# src/core/rbac/middleware.py — _is_token_revoked method
# BEFORE (line ~114):
#     except Exception:
#         return False
# AFTER:
        except Exception as e:
            logger.error(f"Redis revocation check failed: {e} - DENYING access (fail-closed)")
            return True  # SECURITY: fail closed — deny if we can't verify
```

**Step 2:** Commit

```bash
git add src/core/rbac/middleware.py
git commit -m "security: token revocation now fails closed when Redis is unavailable"
```

---

### Task 3: Protect session endpoints (save, restore, check-active)

**Files:**
- Modify: `src/web/sessions_api.py:115-151` (check_active_session)
- Modify: `src/web/sessions_api.py:448-456` (save_session_progress)
- Modify: `src/web/sessions_api.py:516-522` (restore_session)

**Problem:** These three endpoints have NO authentication. An attacker can enumerate user sessions, read session data, and write malicious data to any session.

**Step 1:** Add auth imports at top of `sessions_api.py`:

```python
from rbac.dependencies import require_auth, optional_auth
from rbac.context import AuthContext
from fastapi import Depends
```

**Step 2:** Protect `check_active_session` — require auth, restrict user_id to self:

```python
# Replace check_active_session signature (~line 115-120):
@router.get("/check-active", response_model=CheckActiveResponse)
async def check_active_session(
    ctx: AuthContext = Depends(require_auth),
    session_id: Optional[str] = None,
):
    """Check for active sessions — restricted to the authenticated user."""
    user_id = str(ctx.user_id)  # Always use authenticated user, never accept from query
    result = persistence.check_active_session(
        user_id=user_id,
        session_id=session_id,
    )
```

**Step 3:** Protect `save_session_progress` — use optional auth; if authenticated, verify ownership:

```python
# Replace save_session_progress signature (~line 448-456):
@router.post("/{session_id}/save")
async def save_session_progress(
    session_id: str,
    request: SaveSessionRequest,
    ctx: Optional[AuthContext] = Depends(optional_auth),
):
    """Save session progress — anonymous sessions still allowed but scoped."""
    # If authenticated, attach user_id to session
    user_id = str(ctx.user_id) if ctx else None

    # Load existing session and verify ownership if it has an owner
    existing = persistence.load_unified_session(session_id)
    if existing and existing.user_id and user_id and existing.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your session")
```

**Step 4:** Protect `restore_session` — same optional auth + ownership check:

```python
# Replace restore_session signature (~line 516-522):
@router.get("/{session_id}/restore", response_model=RestoreSessionResponse)
async def restore_session(
    session_id: str,
    ctx: Optional[AuthContext] = Depends(optional_auth),
):
    """Restore session — verify ownership for authenticated users."""
    session = persistence.load_unified_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_id = str(ctx.user_id) if ctx else None
    if session.user_id and user_id and session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your session")
```

**Step 5:** Commit

```bash
git add src/web/sessions_api.py
git commit -m "security: add auth + ownership checks to session save/restore/check endpoints"
```

---

### Task 4: Restrict cleanup endpoint to admin permission

**Files:**
- Modify: `src/web/sessions_api.py:327-354`

**Problem:** Any authenticated user can trigger `cleanup_expired_sessions`. This is an admin operation.

**Step 1:** Change the dependency:

```python
# Add import at top:
from rbac.dependencies import require_platform_admin

# Replace cleanup_expired_sessions (~line 327-330):
@router.post("/cleanup-expired")
async def cleanup_expired_sessions(ctx: AuthContext = Depends(require_platform_admin)):
    """Cleanup expired sessions — admin only."""
```

**Step 2:** Commit

```bash
git add src/web/sessions_api.py
git commit -m "security: restrict session cleanup to platform admins"
```

---

### Task 5: Fix CPA dashboard auth import fallback

**Files:**
- Modify: `src/web/cpa_dashboard_pages.py:25-38`

**Problem:** If `security.auth_decorators` import fails, the entire CPA dashboard runs WITHOUT authentication — a catastrophic security bypass.

**Step 1:** Remove the try/except and make the import mandatory:

```python
# BEFORE (~line 25-38):
# try:
#     from security.auth_decorators import get_user_from_request, Role
#     AUTH_AVAILABLE = True
# except ImportError:
#     AUTH_AVAILABLE = False
#     ...

# AFTER:
from security.auth_decorators import get_user_from_request, Role
```

**Step 2:** Remove all `if AUTH_AVAILABLE:` conditional checks — always enforce auth.

Search for every `if AUTH_AVAILABLE` and `if not AUTH_AVAILABLE` in the file and remove the condition, keeping only the auth-enforced branch.

**Step 3:** Commit

```bash
git add src/web/cpa_dashboard_pages.py
git commit -m "security: make auth import mandatory for CPA dashboard — remove silent fallback"
```

---

### Task 6: Fix session resume IDOR for anonymous sessions

**Files:**
- Modify: `src/web/sessions_api.py:158-206`

**Problem:** When `session.user_id` is None (anonymous session), the ownership check `session.user_id != str(ctx.user_id)` evaluates to `None != "uuid-string"` which is True → 403. But the inverse is also a problem: if an anonymous user created the session and now an authenticated user tries to resume it, there's no binding.

**Step 1:** Replace the ownership check in `resume_session`:

```python
# Replace the ownership check (~line 179):
# BEFORE:
#     if session.user_id != str(ctx.user_id):
#         raise HTTPException(status_code=403, detail="...")

# AFTER:
if session.user_id is None:
    # Anonymous session — bind it to this authenticated user on first resume
    session.user_id = str(ctx.user_id)
    # Persist the binding
    persistence.update_session_owner(session_id, str(ctx.user_id))
elif session.user_id != str(ctx.user_id):
    raise HTTPException(status_code=403, detail="Not authorized to access this session")
```

**Step 2:** If `persistence.update_session_owner` doesn't exist, add it as a simple UPDATE query on the session record. Check the persistence module first.

**Step 3:** Commit

```bash
git add src/web/sessions_api.py
git commit -m "security: fix IDOR — bind anonymous sessions on first authenticated resume"
```

---

### Task 7: Enforce secrets at startup in production

**Files:**
- Modify: `src/config/settings.py:381-384`
- Modify: `src/rbac/jwt.py:44-53`
- Modify: `src/security/ssn_hash.py:71-88`
- Modify: `src/core/services/auth_service.py:48-100`

**Problem:** Multiple modules fall back to insecure development secrets instead of failing fast in production.

**Step 1:** In `settings.py`, change HTTPS enforcement from warning to hard error:

```python
# ~line 381-384 BEFORE:
#     errors.append("APP_ENFORCE_HTTPS: Should be True...")
# AFTER:
if not self.enforce_https:
    raise ValueError("FATAL: APP_ENFORCE_HTTPS must be True in production")
```

**Step 2:** In `jwt.py`, fail hard in production:

```python
# ~line 44-53 — REPLACE the development fallback:
import os
env = os.environ.get("APP_ENVIRONMENT", "").lower()
if env in ("production", "prod", "staging"):
    raise RuntimeError("FATAL: JWT_SECRET must be set in production. Cannot start.")
# Development only — generate ephemeral secret
import warnings, secrets as _secrets
warnings.warn("JWT_SECRET not set — using generated development secret")
return f"DEV-ONLY-{_secrets.token_hex(32)}"
```

**Step 3:** Apply the same pattern to `ssn_hash.py` and `auth_service.py` — check `APP_ENVIRONMENT` and raise RuntimeError in production instead of falling back to dev secrets.

**Step 4:** Commit

```bash
git add src/config/settings.py src/rbac/jwt.py src/security/ssn_hash.py src/core/services/auth_service.py
git commit -m "security: fail-fast on missing secrets in production — no dev fallbacks"
```

---

### Task 8: Fix datetime timezone handling in JWT

**Files:**
- Modify: `src/rbac/jwt.py:107-108,143`

**Problem:** Uses deprecated `datetime.utcnow()` which returns naive datetime objects.

**Step 1:** Replace all `datetime.utcnow()` calls:

```python
# Add at top of file:
from datetime import datetime, timezone

# Replace (~lines 107-108):
# BEFORE: expire = datetime.utcnow() + expires_delta
# AFTER:
expire = datetime.now(timezone.utc) + expires_delta
issued_at = datetime.now(timezone.utc)

# Same for refresh token (~line 143):
# BEFORE: expire = datetime.utcnow() + timedelta(days=...)
# AFTER:
expire = datetime.now(timezone.utc) + timedelta(days=...)
```

**Step 2:** Commit

```bash
git add src/rbac/jwt.py
git commit -m "fix: use timezone-aware datetime in JWT token generation"
```

---

## Phase 2: Auth System Consolidation

### Task 9: Audit and map all enforce=False usages

**Files:**
- Search: all files under `src/` for `enforce=False`
- Modify: any file using `@require_auth(enforce=False)`

**Step 1:** Find all usages:

```bash
grep -rn "enforce=False" src/ --include="*.py"
```

**Step 2:** For each occurrence, determine if the endpoint truly needs to bypass auth:
- If it's a public endpoint (login, signup, landing) — leave it but add a comment explaining why
- If it's NOT public — remove `enforce=False` so auth is enforced

**Step 3:** In `src/security/auth_decorators.py`, add a deprecation warning when `enforce=False` is used in production:

```python
# In _determine_enforcement (~line 30), add:
if enforce is False:
    env = os.environ.get("APP_ENVIRONMENT", "").lower()
    if env in ("production", "prod", "staging"):
        logger.warning(
            f"SECURITY: enforce=False used in {context} — "
            "this disables auth in production!"
        )
```

**Step 4:** Commit

```bash
git add -u
git commit -m "security: audit enforce=False usages, add production warning"
```

---

### Task 10: Map dual auth systems and bridge Role enums

**Files:**
- Modify: `src/security/auth_decorators.py:71-78` (old Role enum)
- Modify: `src/rbac/roles.py:28-103` (new Role enum)
- Modify: `src/web/routers/scenarios.py:23,118`
- Modify: `src/web/app.py:5144-5145`

**Problem:** Two incompatible Role enums. The old one (5 roles: TAXPAYER, CPA, ADMIN, PREPARER, GUEST) is used by `@require_auth(roles=[...])` decorator. The new one (8 roles) is used by the RBAC system. They don't map to each other.

**Step 1:** Add a mapping function in `auth_decorators.py`:

```python
# After the old Role enum (~line 78), add:
_LEGACY_TO_RBAC_ROLE = {
    Role.ADMIN: "super_admin",       # or "platform_admin"
    Role.CPA: "partner",             # CPA firm partner
    Role.PREPARER: "staff",          # CPA firm staff
    Role.TAXPAYER: "firm_client",    # Client of a firm
    Role.GUEST: None,                # No RBAC equivalent
}

def legacy_role_to_rbac(legacy_role: Role) -> Optional[str]:
    """Map legacy auth_decorators Role to rbac.roles Role value."""
    return _LEGACY_TO_RBAC_ROLE.get(legacy_role)
```

**Step 2:** In `scenarios.py:118` and `app.py:5144`, replace old Role references with RBAC role checks or use the mapping.

**Step 3:** Commit

```bash
git add src/security/auth_decorators.py src/web/routers/scenarios.py src/web/app.py
git commit -m "refactor: bridge legacy Role enum to RBAC roles with mapping function"
```

---

### Task 11: Remove hardcoded mock users from auth service

**Files:**
- Modify: `src/core/services/auth_service.py:225-307`

**Problem:** Hardcoded test users with known credentials in the auth service. Even with the `USE_DATABASE` flag, these are accessible in the codebase.

**Step 1:** Wrap mock users in a strict dev-only check:

```python
# Replace the mock user block (~lines 225-307):
if USE_DATABASE:
    self._users_db = {}  # Will load from database
else:
    env = os.environ.get("APP_ENVIRONMENT", "").lower()
    if env in ("production", "prod", "staging"):
        raise RuntimeError(
            "FATAL: AUTH_USE_DATABASE must be 'true' in production. "
            "Cannot use mock users."
        )
    # Development only — mock users for local testing
    self._users_db = {
        # ... existing mock users ...
    }
```

**Step 2:** Commit

```bash
git add src/core/services/auth_service.py
git commit -m "security: block mock auth users in production — require database mode"
```

---

## Phase 3: Data Persistence Migration (In-Memory → Redis)

### Task 12: Migrate refresh tokens to Redis

**Files:**
- Modify: `src/core/services/auth_service.py:210-213,374-379`

**Problem:** Refresh tokens stored in `self._refresh_tokens: Dict` — lost on restart, not shared across workers.

**Step 1:** Add Redis helper methods:

```python
import os
from cache.redis_client import get_redis_client

class AuthService:
    def __init__(self, ...):
        # Replace: self._refresh_tokens: Dict[str, Dict] = {}
        self._redis = get_redis_client()
        self._REFRESH_PREFIX = "refresh_token:"

    async def _store_refresh_token(self, token: str, data: dict, ttl: int):
        """Store refresh token in Redis with TTL."""
        if self._redis:
            import json
            await self._redis.setex(
                f"{self._REFRESH_PREFIX}{token}",
                ttl,
                json.dumps(data, default=str),
            )
        else:
            # Fallback for dev — log warning
            logger.warning("Redis unavailable — refresh token stored in-memory only")
            self._refresh_tokens[token] = data

    async def _get_refresh_token(self, token: str) -> Optional[dict]:
        """Retrieve refresh token from Redis."""
        if self._redis:
            import json
            raw = await self._redis.get(f"{self._REFRESH_PREFIX}{token}")
            return json.loads(raw) if raw else None
        return self._refresh_tokens.get(token)

    async def _delete_refresh_token(self, token: str):
        """Revoke refresh token."""
        if self._redis:
            await self._redis.delete(f"{self._REFRESH_PREFIX}{token}")
        self._refresh_tokens.pop(token, None)
```

**Step 2:** Update `_generate_refresh_token` to use the new helper.

**Step 3:** Update logout to use `_delete_refresh_token`.

**Step 4:** Commit

```bash
git add src/core/services/auth_service.py
git commit -m "feat: migrate refresh tokens from in-memory to Redis with TTL"
```

---

### Task 13: Migrate password reset tokens to Redis

**Files:**
- Modify: `src/core/api/auth_routes.py:423-461`

**Problem:** `_reset_tokens: dict = {}` fallback means tokens lost on restart and not shared across workers.

**Step 1:** Make Redis mandatory for reset tokens in production:

```python
# Replace _store_reset_token (~line 430-445):
def _store_reset_token(token: str, data: dict, ttl_seconds: int = 900):
    """Store password reset token — requires Redis in production."""
    if redis_client:
        import json
        redis_client.setex(
            f"reset_token:{token}",
            ttl_seconds,
            json.dumps(data, default=str),
        )
    else:
        env = os.environ.get("APP_ENVIRONMENT", "").lower()
        if env in ("production", "prod", "staging"):
            raise RuntimeError("Redis required for password reset tokens in production")
        logger.warning("Redis unavailable — using in-memory reset tokens (dev only)")
        _reset_tokens[token] = {**data, "_expires": time.time() + ttl_seconds}
```

**Step 2:** Same pattern for `_get_reset_token` and `_delete_reset_token`.

**Step 3:** Commit

```bash
git add src/core/api/auth_routes.py
git commit -m "feat: enforce Redis for password reset tokens in production"
```

---

### Task 14: Migrate magic link tokens to Redis

**Files:**
- Modify: `src/core/services/auth_service.py:386-391`

**Problem:** Same in-memory issue as refresh tokens.

**Step 1:** Apply the same Redis helper pattern as Task 12, but with `magic_link:` key prefix and appropriate TTL (15 minutes).

**Step 2:** Commit

```bash
git add src/core/services/auth_service.py
git commit -m "feat: migrate magic link tokens to Redis with TTL"
```

---

## Phase 4: RBAC Permission Enforcement

### Task 15: Wire require_permission to remaining critical endpoints

**Files:**
- Modify: `src/web/app.py` (multiple route handlers)
- Reference: `src/rbac/permissions.py` (Permission enum)
- Reference: `src/rbac/dependencies.py` (require_permission)

**Problem:** 34+ permissions defined but only ~15 enforced at route level. Key gaps:

**Step 1:** Add permission checks to these route groups (one at a time):

| Endpoint Pattern | Permission | Current Auth |
|---|---|---|
| `POST /api/clients` | `Permission.CLIENT_CREATE` | `_require_any_auth` only |
| `PUT /api/clients/{id}` | `Permission.CLIENT_EDIT` | `_require_any_auth` only |
| `DELETE /api/clients/{id}` | `Permission.CLIENT_DELETE` | `_require_any_auth` only |
| `GET /api/teams` | `Permission.TEAM_VIEW` | `_require_any_auth` only |
| `POST /api/teams` | `Permission.TEAM_MANAGE` | `_require_any_auth` only |
| `GET /api/firms/{id}/billing` | `Permission.FIRM_VIEW_BILLING` | `_require_any_auth` only |
| `PUT /api/firms/{id}/billing` | `Permission.FIRM_MANAGE_BILLING` | `_require_any_auth` only |
| `GET /api/audit-logs` | `Permission.PLATFORM_VIEW_AUDIT_LOGS` | `_require_any_auth` only |

For each: add `Depends(require_permission(Permission.XXX))` as a parameter, or use the decorator pattern already established in the codebase.

**Step 2:** Commit after each batch of related endpoints (e.g., all client endpoints together).

```bash
git commit -m "rbac: enforce CLIENT_CREATE/EDIT/DELETE permissions on client endpoints"
git commit -m "rbac: enforce TEAM_VIEW/MANAGE permissions on team endpoints"
git commit -m "rbac: enforce billing and audit log permissions"
```

---

### Task 16: Fix admin impersonation to use real database

**Files:**
- Modify: `src/web/routers/admin_impersonation_api.py:111-120`

**Problem:** Uses `_mock_users` dict instead of real database lookup.

**Step 1:** Replace `_get_user_info()` to use the database:

```python
# BEFORE (~line 111-120):
# _mock_users = { "user-001": {...}, ... }

# AFTER:
async def _get_user_info(user_id: str) -> Optional[dict]:
    """Look up user from database."""
    from database.session import get_db_session
    async with get_db_session() as db:
        result = await db.execute(
            text("SELECT user_id, email, role, firm_id FROM users WHERE user_id = :uid"),
            {"uid": user_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "user_id": row.user_id,
            "email": row.email,
            "role": row.role,
            "firm_id": row.firm_id,
        }
```

**Step 2:** Replace `_sessions: dict` with Redis-backed storage for impersonation sessions.

**Step 3:** Commit

```bash
git add src/web/routers/admin_impersonation_api.py
git commit -m "feat: replace mock users with real database in admin impersonation"
```

---

### Task 17: Fix permission enum validation — reject invalid strings

**Files:**
- Modify: `src/rbac/dependencies.py:203-212`

**Problem:** `_coerce_permission` returns raw string if Permission enum lookup fails, silently causing 403 on valid users.

**Step 1:** Make it raise instead of returning invalid string:

```python
# BEFORE (~line 210-212):
#     except (TypeError, ValueError):
#         return raw  # RETURNS INVALID STRING!

# AFTER:
    except (TypeError, ValueError):
        logger.error(f"Invalid permission value: {raw!r} — not in Permission enum")
        raise ValueError(f"Invalid permission: {raw!r}")
```

**Step 2:** Commit

```bash
git add src/rbac/dependencies.py
git commit -m "fix: reject invalid permission strings instead of silently returning 403"
```

---

## Phase 5: Code Quality & Hygiene

### Task 18: Update outdated dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1:** Update the most critical packages:

```
# Priority updates (security patches):
fastapi>=0.115.0
pydantic>=2.8.0
pydantic-settings>=2.4.0
sqlalchemy[asyncio]>=2.0.30
cryptography>=43.0.0
bcrypt>=4.2.0

# Feature updates (new capabilities):
langchain>=0.3.0
langchain-openai>=0.2.0
openai>=1.50.0
```

**Step 2:** Run `pip install -r requirements.txt` and fix any import breakages.

**Step 3:** Commit

```bash
git add requirements.txt
git commit -m "chore: upgrade critical dependencies (fastapi, pydantic, cryptography, langchain)"
```

---

### Task 19: Add backend CAPTCHA validation for lead magnet

**Files:**
- Modify: `src/web/app.py` (lead magnet/create endpoints near line 282-314)

**Problem:** Lead magnet endpoints are CSRF-exempt with frontend-only CAPTCHA — easily bypassed by bots.

**Step 1:** Add server-side CAPTCHA verification:

```python
import httpx

async def _verify_captcha(token: str) -> bool:
    """Verify reCAPTCHA/hCaptcha token server-side."""
    secret = os.environ.get("CAPTCHA_SECRET_KEY")
    if not secret:
        env = os.environ.get("APP_ENVIRONMENT", "").lower()
        if env in ("production", "prod"):
            logger.error("CAPTCHA_SECRET_KEY not set in production!")
            return False
        return True  # Skip in dev

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": secret, "response": token},
        )
        result = resp.json()
        return result.get("success", False)
```

**Step 2:** Call `_verify_captcha()` at the top of each lead creation endpoint.

**Step 3:** Commit

```bash
git add src/web/app.py
git commit -m "security: add server-side CAPTCHA validation for lead magnet endpoints"
```

---

### Task 20: Fix financial data validation with Decimal types

**Files:**
- Modify: `src/core/api/tax_returns_routes.py:69-74`

**Problem:** Uses `float` for financial data — allows Infinity, NaN, and lacks precision.

**Step 1:** Replace the Pydantic model:

```python
from decimal import Decimal
from pydantic import Field

class TaxReturn(BaseModel):
    gross_income: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))
    adjusted_gross_income: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))
    taxable_income: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))
    total_tax: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("999999999.99"))
```

**Step 2:** Commit

```bash
git add src/core/api/tax_returns_routes.py
git commit -m "fix: use Decimal with range validation for financial data fields"
```

---

### Task 21: Fix X-Forwarded-For parsing (rightmost trusted IP)

**Files:**
- Modify: `src/security/middleware.py:485-497`

**Problem:** Takes first IP in X-Forwarded-For chain — easily spoofed.

**Step 1:** Fix the IP extraction:

```python
# BEFORE:
#     return forwarded.split(",")[0].strip()

# AFTER:
# Use rightmost IP not in TRUSTED_PROXIES (standard secure approach)
ips = [ip.strip() for ip in forwarded.split(",")]
# Walk from right to left, skip trusted proxies
for ip in reversed(ips):
    if ip not in TRUSTED_PROXIES:
        return ip
return ips[0]  # Fallback to leftmost if all trusted
```

**Step 2:** Commit

```bash
git add src/security/middleware.py
git commit -m "security: fix X-Forwarded-For parsing — use rightmost non-trusted IP"
```

---

### Task 22: Remove deprecated files

**Files:**
- Delete: `src/web/templates/_deprecated/` (entire directory)
- Delete: `src/web/static/css/_deprecated/` (entire directory)
- Delete: `src/web/static/js/_deprecated/` (entire directory)
- Delete: `src/web/circuit_breaker.py` (duplicate of `src/resilience/circuit_breaker.py`)
- Delete: `tmp_route_audit.json`, `tmp_route_audit_flat.json`, `tmp_route_audit_sitemap.md`

**Step 1:** Verify nothing imports from these files:

```bash
grep -rn "_deprecated" src/ --include="*.py" --include="*.html"
grep -rn "circuit_breaker" src/web/ --include="*.py"
```

**Step 2:** Delete and commit:

```bash
rm -rf src/web/templates/_deprecated/
rm -rf src/web/static/css/_deprecated/
rm -rf src/web/static/js/_deprecated/
rm -f src/web/circuit_breaker.py
rm -f tmp_route_audit.json tmp_route_audit_flat.json tmp_route_audit_sitemap.md
git add -A
git commit -m "chore: remove deprecated templates, CSS, JS, duplicate circuit breaker, temp files"
```

---

### Task 23: Fix error page javascript: protocol URLs

**Files:**
- Modify: `src/web/templates/errors/404.html:120`
- Modify: `src/web/templates/errors/500.html:120`

**Step 1:** Replace javascript: hrefs with proper buttons:

```html
<!-- 404.html — replace ~line 120 -->
<!-- BEFORE: <a href="javascript:history.back()" class="btn btn-secondary">Go Back</a> -->
<!-- AFTER: -->
<button onclick="history.back()" class="btn btn-secondary">Go Back</button>

<!-- 500.html — replace ~line 120 -->
<!-- BEFORE: <a href="javascript:location.reload()" class="btn btn-secondary">Try Again</a> -->
<!-- AFTER: -->
<button onclick="location.reload()" class="btn btn-secondary">Try Again</button>
```

**Step 2:** Commit

```bash
git add src/web/templates/errors/404.html src/web/templates/errors/500.html
git commit -m "fix: replace javascript: protocol URLs with buttons in error pages"
```

---

### Task 24: Wire startup security validation in app init

**Files:**
- Modify: `src/web/app.py` (app startup/lifespan)
- Reference: `src/config/settings.py` (`get_validated_settings`)

**Problem:** `settings.py` provides `get_validated_settings()` but app.py never calls it.

**Step 1:** Add validation call in the app startup/lifespan:

```python
# In app.py startup (lifespan or on_event("startup")):
from config.settings import get_validated_settings

@app.on_event("startup")
async def startup_validation():
    settings = get_validated_settings()
    if settings is None:
        logger.critical("Settings validation failed — check configuration")
        # In production, this should prevent startup
        env = os.environ.get("APP_ENVIRONMENT", "").lower()
        if env in ("production", "prod"):
            raise RuntimeError("Cannot start: settings validation failed")
```

**Step 2:** Commit

```bash
git add src/web/app.py
git commit -m "feat: wire startup security validation — block production start with invalid config"
```

---

## Phase 6: Automated Verification (Ensuring No Hidden Issues Remain)

### Task 25: Comprehensive auth audit script

**Files:**
- Modify: `scripts/audit_routes.py`

**Step 1:** Add these new audit checks to the existing script:

**A. Session endpoint auth check:**
```python
def check_session_endpoints():
    """Verify all /api/sessions/ endpoints have auth."""
    issues = []
    # Parse sessions_api.py for route handlers
    # Check each has Depends(require_auth) or Depends(optional_auth)
    # Flag any that have neither
    return issues
```

**B. SQL injection pattern scanner:**
```python
def check_sql_injection_patterns():
    """Scan for f-string SQL patterns without column whitelists."""
    issues = []
    for py_file in glob.glob("src/**/*.py", recursive=True):
        content = open(py_file).read()
        # Look for: text(f"...UPDATE...SET {
        if re.search(r'text\(f["\'].*(?:UPDATE|INSERT|DELETE).*\{', content):
            # Check if a _*_UPDATABLE_COLUMNS whitelist exists in same file
            if '_UPDATABLE_COLUMNS' not in content and '_ALLOWED_COLUMNS' not in content:
                issues.append(f"CRITICAL: {py_file} has dynamic SQL without column whitelist")
    return issues
```

**C. In-memory storage scanner:**
```python
def check_in_memory_stores():
    """Find global dicts/lists used as data stores."""
    issues = []
    patterns = [
        (r'^\s*_\w+:\s*(?:Dict|dict)\s*=\s*\{\}', "global dict store"),
        (r'^\s*_\w+:\s*(?:List|list)\s*=\s*\[\]', "global list store"),
        (r'self\._\w+:\s*Dict\[.*\]\s*=\s*\{\}', "instance dict store"),
    ]
    # Scan all Python files, flag matches outside test files
    return issues
```

**D. Secret fallback scanner:**
```python
def check_secret_fallbacks():
    """Ensure no dev secret fallbacks exist without production guards."""
    issues = []
    # Scan for patterns like: secrets.token_hex, token_urlsafe, token_bytes
    # Verify they're guarded by APP_ENVIRONMENT check
    return issues
```

**E. Dead router detection (already partially implemented):**
```python
def check_dead_routers():
    """Find router files not registered in app."""
    # Already exists from previous plan — extend to check sessions_api, etc.
    pass
```

**Step 2:** Add a summary report function that outputs a scorecard:

```python
def run_full_audit():
    """Run all audit checks and print remediation status."""
    checks = [
        ("Route Auth Gaps", check_route_auth_gaps),
        ("SQL Injection Patterns", check_sql_injection_patterns),
        ("Session Endpoint Auth", check_session_endpoints),
        ("In-Memory Stores", check_in_memory_stores),
        ("Secret Fallbacks", check_secret_fallbacks),
        ("Dead Routers", check_dead_routers),
        ("CPA Namespace Auth", check_cpa_namespace_auth),
        ("Redirect Chain", check_redirect_chains),
    ]

    total_issues = 0
    for name, check_fn in checks:
        issues = check_fn()
        status = "PASS" if not issues else f"FAIL ({len(issues)} issues)"
        print(f"  [{status}] {name}")
        total_issues += len(issues)
        for issue in issues:
            print(f"         {issue}")

    print(f"\n{'ALL CHECKS PASSED' if total_issues == 0 else f'{total_issues} ISSUES FOUND'}")
    return total_issues
```

**Step 3:** Commit

```bash
git add scripts/audit_routes.py
git commit -m "feat: comprehensive audit script — SQL injection, auth gaps, in-memory stores, secrets"
```

---

### Task 26: Dependency vulnerability scanner script

**Files:**
- Create: `scripts/audit_dependencies.py`

**Step 1:** Write a script that checks for known vulnerabilities:

```python
#!/usr/bin/env python3
"""Scan requirements.txt for outdated/vulnerable packages."""
import subprocess
import sys
import json

def main():
    # Use pip-audit if available, otherwise use pip list --outdated
    try:
        result = subprocess.run(
            ["pip-audit", "--format=json", "-r", "requirements.txt"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            vulns = json.loads(result.stdout)
            if vulns:
                print(f"FAIL: {len(vulns)} vulnerabilities found")
                for v in vulns:
                    print(f"  {v['name']}=={v['version']}: {v.get('description', 'N/A')}")
                return 1
            print("PASS: No known vulnerabilities")
            return 0
    except FileNotFoundError:
        print("WARNING: pip-audit not installed. Run: pip install pip-audit")

    # Fallback: check for outdated packages
    result = subprocess.run(
        ["pip", "list", "--outdated", "--format=json"],
        capture_output=True, text=True
    )
    outdated = json.loads(result.stdout)
    if outdated:
        print(f"INFO: {len(outdated)} outdated packages")
        for pkg in outdated:
            print(f"  {pkg['name']}: {pkg['version']} -> {pkg['latest_version']}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Step 2:** Commit

```bash
git add scripts/audit_dependencies.py
git commit -m "feat: add dependency vulnerability scanner script"
```

---

### Task 27: RBAC completeness audit script

**Files:**
- Create: `scripts/audit_rbac.py`

**Step 1:** Write a script that cross-references all defined permissions against actual enforcement:

```python
#!/usr/bin/env python3
"""Audit RBAC permission enforcement completeness."""
import ast
import glob
import re
import sys

def get_defined_permissions():
    """Read all Permission enum values from permissions.py."""
    with open("src/rbac/permissions.py") as f:
        content = f.read()
    # Parse Permission enum members
    permissions = set()
    for match in re.finditer(r'(\w+)\s*=\s*"(\w+)"', content):
        name, value = match.groups()
        if name.isupper():
            permissions.add(name)
    return permissions

def get_enforced_permissions():
    """Scan all route files for require_permission() calls."""
    enforced = set()
    for py_file in glob.glob("src/**/*.py", recursive=True):
        with open(py_file) as f:
            content = f.read()
        for match in re.finditer(r'require_permission\(Permission\.(\w+)', content):
            enforced.add(match.group(1))
    return enforced

def main():
    defined = get_defined_permissions()
    enforced = get_enforced_permissions()
    unenforced = defined - enforced

    print(f"Defined permissions: {len(defined)}")
    print(f"Enforced at routes:  {len(enforced)}")
    print(f"Unenforced:          {len(unenforced)}")

    if unenforced:
        print(f"\nWARNING: {len(unenforced)} permissions defined but never enforced:")
        for p in sorted(unenforced):
            print(f"  - Permission.{p}")
        return 1

    print("\nPASS: All defined permissions are enforced at route level")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Step 2:** Commit

```bash
git add scripts/audit_rbac.py
git commit -m "feat: add RBAC permission enforcement audit script"
```

---

### Task 28: Master audit runner

**Files:**
- Create: `scripts/audit_all.py`

**Step 1:** Create a unified runner:

```python
#!/usr/bin/env python3
"""Run ALL platform audit checks and produce a readiness scorecard."""
import subprocess
import sys

AUDITS = [
    ("Route & Auth Audit", "python3 scripts/audit_routes.py"),
    ("RBAC Completeness", "python3 scripts/audit_rbac.py"),
    ("Dependency Vulnerabilities", "python3 scripts/audit_dependencies.py"),
]

def main():
    print("=" * 60)
    print("  JORSS-GBO PLATFORM READINESS AUDIT")
    print("=" * 60)

    results = []
    for name, cmd in AUDITS:
        print(f"\n--- {name} ---")
        result = subprocess.run(cmd, shell=True)
        passed = result.returncode == 0
        results.append((name, passed))

    print("\n" + "=" * 60)
    print("  SCORECARD")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for _, p in results if p)
    for name, p in results:
        status = "PASS" if p else "FAIL"
        print(f"  [{status}] {name}")

    score = int((passed / total) * 100) if total else 0
    print(f"\n  Overall: {passed}/{total} checks passed ({score}%)")

    if score == 100:
        print("  STATUS: PRODUCTION READY")
    elif score >= 80:
        print("  STATUS: NEAR READY — fix remaining issues")
    else:
        print("  STATUS: NOT READY — critical issues remain")

    return 0 if score == 100 else 1

if __name__ == "__main__":
    sys.exit(main())
```

**Step 2:** Commit

```bash
git add scripts/audit_all.py
git commit -m "feat: add master audit runner with readiness scorecard"
```

---

## Verification Checklist

After all tasks complete, run:

```bash
python3 scripts/audit_all.py
```

Expected output: ALL CHECKS PASSED, PRODUCTION READY

### Manual Verification Traces:

1. **SQL injection blocked:** Try sending a field name like `"; DROP TABLE returns; --` in an UPDATE body → should get 400 "Invalid field"
2. **Token revocation fail-closed:** Stop Redis → revoked tokens should be REJECTED (not accepted)
3. **Session auth:** `GET /api/sessions/check-active` without cookie → 401
4. **Session IDOR:** Authenticated user A tries to restore user B's session → 403
5. **Cleanup restricted:** Non-admin calls `POST /api/sessions/cleanup-expired` → 403
6. **CPA dashboard auth:** Remove `security.auth_decorators` module temporarily → app should CRASH (not silently serve without auth)
7. **Production secrets:** Set `APP_ENVIRONMENT=production` without `JWT_SECRET` → startup fails with RuntimeError
8. **Lead magnet CAPTCHA:** `POST /api/leads/create` without captcha token → rejected
9. **Financial validation:** Submit `gross_income: Infinity` → 422 validation error
10. **X-Forwarded-For:** Send spoofed header from non-trusted IP → rate limit uses real IP

---

## Files Modified Summary

| Phase | Files Changed | Key Change |
|-------|--------------|------------|
| 1 | 11 files | SQL injection, fail-closed tokens, session auth, secrets |
| 2 | 5 files | Role enum bridge, enforce=False audit, mock users blocked |
| 3 | 2 files | Refresh tokens, reset tokens, magic links → Redis |
| 4 | 4 files | Permission enforcement, impersonation DB, enum validation |
| 5 | 8 files | Dependencies, CAPTCHA, Decimal, XFF, dead code, error pages |
| 6 | 4 files | 3 audit scripts + master runner |

**Total: ~34 files across 28 tasks**
