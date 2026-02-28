# Jorss-GBO Go-Live Reverse PRD

**Date:** 2026-02-28
**Status:** Draft
**Target:** Production launch readiness
**Platform:** Render + Neon PostgreSQL + Upstash Redis

---

## Executive Summary

Jorss-GBO is an AI-powered tax advisory platform with 49+ IRS forms, multi-tenant CPA portals, and a tiered conversion funnel. The core application is **~80% production-ready** with strong security, comprehensive tax logic, and AI integrations. This document maps every gap between current state and go-live, organized by workstream with dependencies.

### What's Built (Strong)
- FastAPI async backend with 146 routes, 30+ routers
- 49+ IRS form calculations with decimal precision
- 8-role RBAC with 50+ permissions, tenant isolation
- JWT auth with token revocation, OAuth (Google/Microsoft)
- AES-256 encryption for PII, HMAC audit trail
- AI advisory: 4 LLM providers, 25+ AI service methods wired
- Tiered conversion funnel with strategy locking/unlocking
- Docker multi-stage builds, Nginx reverse proxy, CI pipeline
- Kubernetes-ready health probes (/health/live, /health/ready)
- 4,742 tests across 208 test files

### What's Missing (This Document)
- ~~Secrets leaked in `.env`~~ **RESOLVED** — `.env` was never committed to git (`.gitignore` protected it). Local dev secrets rotated 2026-02-28. Production secret generation script created.
- No dependency lock files
- No static asset optimization (4,249 files served raw)
- Incomplete email integration
- MFA not implemented (fields exist, code doesn't)
- No E2E tests, no load tests
- No log aggregation or alerting
- No backup/restore procedures tested
- No CDN for static assets

---

## Workstream Map

```
WS1: Security Hardening ──────────────────── BLOCKS EVERYTHING
  │
  ├── WS2: Database & Persistence ─────────── BLOCKS WS5, WS7
  │     │
  │     └── WS5: Email & Notifications ────── BLOCKS WS8
  │
  ├── WS3: Infrastructure & Deployment ────── BLOCKS WS7
  │     │
  │     └── WS6: Static Assets & Frontend ─── BLOCKS WS7
  │
  ├── WS4: Testing & Quality ─────────────── BLOCKS WS7
  │
  └── WS7: Launch Verification ────────────── BLOCKS WS8
        │
        └── WS8: Post-Launch & Monitoring
```

---

## WS1: Security Hardening (CRITICAL — Blocks Everything)

**Owner:** Security Lead
**Priority:** P0 — Must complete first
**Estimated effort:** 3-5 days

### WS1.1 — Rotate All Secrets ~~(Day 1)~~ COMPLETED 2026-02-28

**~~Problem:~~ Resolved:** Initial audit flagged `.env` as committed to git. Verification confirmed `.env` was **never committed** — `.gitignore` has protected it since project creation. The file contains auto-generated bootstrap secrets for local development only.

**What was done:**
1. Verified `.env` not in git: `git log --all --full-history -- .env` returns empty
2. Verified no real API keys in tracked files (only test fixture `sk-1234567890abcdefghij` in `test_secure_logger.py`)
3. Rotated all 9 local dev secrets with fresh `secrets.token_hex()` values
4. Changed local `.env` from `APP_ENVIRONMENT=production` to `APP_ENVIRONMENT=development`
5. Created `scripts/generate_secrets.py` with 3 output modes:
   - `--env` format for .env files
   - `--json` format for programmatic use
   - `--verify` mode to validate existing secrets
6. Updated `.env.production.example` with missing variables:
   - Added `SERIALIZER_SECRET_KEY`, `AUDIT_HMAC_KEY`
   - Added `REDIS_URL` (connection string format for Upstash)
   - Fixed `CORS_ORIGINS` (was `APP_CORS_ORIGINS` — wrong var name)
   - Added `SENDGRID_API_KEY` (was SMTP-only)
   - Added `AI_CHAT_ENABLED`, `AI_SAFETY_CHECKS` feature flags
   - Added `DB_PERSISTENCE`, `UNIFIED_FILING` flags
   - Added OAuth and Stripe optional sections
   - Updated setup instructions to reference `scripts/generate_secrets.py`

**For production deployment:**
```bash
python3 scripts/generate_secrets.py --env > .env.production
# Then fill in: DATABASE_URL, REDIS_URL, OPENAI_API_KEY, CORS_ORIGINS
python3 scripts/generate_secrets.py --verify --env-file .env.production
```

**Status:** COMPLETE

---

### WS1.2 — Secrets Management

**Problem:** No secrets management system. Secrets are in environment variables with no rotation strategy.

**Actions:**
1. Choose secrets provider:
   - **Render:** Use Render's built-in secret environment variables (free)
   - **Optional upgrade:** HashiCorp Vault, AWS Secrets Manager, or Doppler
2. Document secret rotation procedure (quarterly minimum)
3. Add secret strength validation to `scripts/preflight_launch.py` (partially exists)
4. Create `scripts/rotate_secrets.py` utility

**Dependencies:** WS1.1
**Verification:** `python scripts/preflight_launch.py` passes all checks

---

### WS1.3 — MFA Implementation

**Problem:** `mfa_enabled` and `mfa_secret` fields exist in User model and database (`MFACredential`, `MFAPendingSetup` tables), but no code implements the TOTP flow. `pyotp` is in requirements.

**Current state:**
- Files: `src/core/models/user.py` has `mfa_enabled: bool`, `mfa_secret: str`
- Database: `MFACredential` and `MFAPendingSetup` models in `src/database/models.py`
- Templates: `auth/mfa-setup.html` and `auth/mfa-verify.html` exist
- Library: `pyotp==2.9.0` in requirements.txt
- Routes: `GET /auth/mfa-setup` and `GET /auth/mfa-verify` serve templates

**Actions:**
1. Implement TOTP setup flow: generate secret → show QR code → verify first code
2. Implement TOTP verification on login (after password check)
3. Add backup codes generation and storage
4. Wire to existing templates and routes
5. Enable for CPA roles (PARTNER, STAFF) — optional for consumers

**Dependencies:** WS1.1 (need stable auth before adding MFA layer)
**Verification:** CPA can enable MFA, login requires 6-digit TOTP code

---

### WS1.4 — OAuth State Token Persistence

**Problem:** OAuth state tokens stored in-memory `Dict`. In distributed deployment (multiple workers/instances), state validation will fail because the token was stored in a different worker's memory.

**Current state:**
- File: `src/core/api/oauth_routes.py`
- Pattern: `state_tokens: Dict[str, str] = {}` (module-level dict)
- Works with 1 worker, breaks with 2+

**Actions:**
1. Move state token storage to Redis with 10-minute TTL
2. Use `REDIS_URL` connection (already configured)
3. Fallback to in-memory for development (no Redis)

**Dependencies:** WS2.2 (Redis must be configured)
**Verification:** OAuth login works with `--workers 4` (multiple Gunicorn workers)

---

### WS1.5 — CSRF Cookie/Token Expiry Alignment — COMPLETED 2026-02-28

**~~Problem:~~ Resolved:** Three CSRF cookie locations had mismatched `max_age` values:
- `CSRFCookieMiddleware` config: 604800 (7 days)
- `CSRFMiddleware` rotation: 604800 (7 days)
- `set_csrf_cookie()` utility: **3600 (1 hour)** — mismatch!
- `CSRFCookieMiddleware` class default: **86400 (24 hours)** — stale default

**What was done:**
1. Fixed `set_csrf_cookie()` max_age: 3600 → 604800 (7 days)
2. Fixed `CSRFCookieMiddleware` class default: 86400 → 604800 (7 days)
3. Updated docstring to reflect actual 7-day duration
4. Added alignment comments to prevent future drift

**Status:** COMPLETE

---

## WS2: Database & Persistence

**Owner:** Backend Lead
**Priority:** P0
**Estimated effort:** 3-4 days

### WS2.1 — Dependency Lock File ✅ DONE (2026-02-28)

**Problem:** No `requirements.lock` or `poetry.lock`. Production installs may get different package versions than development, causing unpredictable behavior.

**Resolution:**
1. Synced venv to `requirements.txt` — installed 6 missing production deps (redis, asyncpg, gunicorn, sentry-sdk, itsdangerous, aiofiles) and upgraded langchain-community 0.0.20→0.3.31 to fix dependency conflicts. `pip check` passes clean.
2. Generated `requirements.lock` — 107 exact-pinned production packages (pytest excluded). Header documents regeneration procedure.
3. Updated `Dockerfile` — builder stage now installs from `requirements.lock` instead of `requirements.txt`.
4. Generated root `package-lock.json` — locks Storybook/stylelint devtools.

**Dependencies:** None
**Verification:** `pip install -r requirements.lock` resolves all 107 packages; `pip check` reports no broken requirements

---

### WS2.2 — Redis Production Configuration

**Problem:** Redis is required for sessions, caching, rate limiting, Celery, and token revocation — but no connection health monitoring or failover.

**Current state:**
- File: `src/cache/redis_client.py` — connection with timeout, SSL support
- Used by: rate limiter, session persistence, Celery broker, token revocation
- Fallback: in-memory for rate limiting, SQLite for sessions
- Production target: Upstash (free tier, Redis-compatible)

**Actions:**
1. Set up Upstash Redis instance (per `PRODUCTION_LAUNCH_GUIDE.md`)
2. Add Redis health check to `/health/ready` endpoint (currently missing)
3. Verify all fallback paths work when Redis is unavailable
4. Document connection string format for Upstash (TLS required)
5. Test Celery worker connectivity to Upstash

**Dependencies:** WS1.1 (Redis password must be rotated if leaked)
**Verification:** `GET /health/ready` includes Redis status; app degrades gracefully without Redis

---

### WS2.3 — Database Migration Strategy

**Problem:** Alembic is configured (`alembic.ini`) but no managed migrations exist in `src/database/alembic/`. Current migrations are hand-written SQL files in `/migrations/`.

**Current state:**
- 8 migration files in `/migrations/` (SQL + Python)
- `alembic.ini` points to `src/database/alembic` (empty)
- `scripts/build.sh` runs `alembic upgrade head` (silently succeeds with no migrations)
- ORM models in `src/database/models.py` (19 tables, 63KB)

**Actions:**
1. Initialize Alembic: `alembic init src/database/alembic`
2. Generate initial migration from current models: `alembic revision --autogenerate -m "initial"`
3. Mark existing database as migrated: `alembic stamp head`
4. Test migration on empty database: create → migrate → verify schema
5. Add migration test to CI: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
6. Document rollback procedure

**Dependencies:** WS2.2 (test against PostgreSQL, not just SQLite)
**Verification:** `alembic upgrade head` creates correct schema on empty Neon database

---

### WS2.4 — Database Backup Strategy

**Problem:** No automated backup or restore procedure documented.

**Actions:**
1. Enable Neon's point-in-time recovery (built into free tier, 7-day retention)
2. Document manual backup: `pg_dump` command with connection string
3. Create `scripts/backup_database.sh` utility
4. Test restore procedure: backup → destroy → restore → verify data
5. Add backup verification to weekly checklist

**Dependencies:** WS2.3 (need stable schema first)
**Verification:** Can restore from backup and all data is intact

---

## WS3: Infrastructure & Deployment

**Owner:** DevOps / Platform Lead
**Priority:** P1
**Estimated effort:** 5-7 days

### WS3.1 — Render Deployment

**Problem:** `render.yaml` blueprint exists but has never been deployed and validated end-to-end.

**Current state:**
- File: `render.yaml` — web service, free tier, Oregon region
- Build: `./scripts/build.sh`
- Start: `gunicorn src.web.app:app --workers 2 --worker-class uvicorn.workers.UvicornWorker`
- Health check: `/api/health`
- `PRODUCTION_LAUNCH_GUIDE.md` has step-by-step instructions

**Actions:**
1. Follow `PRODUCTION_LAUNCH_GUIDE.md` steps 1-4:
   - Step 1: Set up Neon PostgreSQL
   - Step 2: Set up Upstash Redis
   - Step 3: Deploy to Render
   - Step 4: Configure environment variables
2. Verify build completes successfully on Render
3. Verify health check passes: `curl https://your-app.onrender.com/api/health`
4. Test auto-sleep/wake cycle (Render free tier sleeps after 15 min)
5. Configure custom domain (if applicable)

**Dependencies:** WS1.1, WS2.1, WS2.2
**Verification:** `curl https://your-app.onrender.com/api/health` returns `{"status": "healthy"}`

---

### WS3.2 — SSL/TLS Certificate

**Problem:** Nginx config references SSL certificates at `/etc/nginx/ssl/` but no certificates are provided or auto-provisioned.

**Current state:**
- File: `nginx/nginx.conf` — TLS 1.2/1.3, strong ciphers, HSTS
- Render handles SSL automatically on `*.onrender.com` domains
- Custom domain requires DNS + Let's Encrypt (Render auto-provisions)

**Actions:**
1. For Render deployment: SSL is automatic — no action needed
2. For custom domain: configure DNS CNAME → Render, enable auto-SSL
3. For self-hosted (Docker + Nginx): set up certbot/Let's Encrypt
4. Verify HSTS header: `curl -I https://your-domain.com`

**Dependencies:** WS3.1 (need running deployment first)
**Verification:** `curl -I` shows `Strict-Transport-Security: max-age=63072000`

---

### WS3.3 — `.dockerignore` File ✅ DONE (2026-02-28)

**Problem:** No `.dockerignore` file. Docker build copies everything including `.git`, `node_modules`, test files, docs.

**Resolution:** Created comprehensive `.dockerignore` excluding secrets, `.git`, tests, docs, virtual envs, IDE files, databases, frontend tooling, deploy configs, non-source directories, and temp files. Only `requirements.txt`, `src/`, and `database/` (the three paths the Dockerfile COPY commands reference) pass through to the build context.

**Dependencies:** None
**Verification:** Confirmed all 3 Dockerfile COPY targets included; all non-essential files excluded

---

### WS3.4 — CI/CD Pipeline: Add Deployment Step

**Problem:** `.github/workflows/ci.yml` has linting, security scanning, and tests — but no deployment step. Deployments are manual.

**Current state:**
- CI runs: Ruff lint, Bandit security scan, Safety dep check, pytest
- No CD: no auto-deploy to Render on merge to main

**Actions:**
1. Add Render deploy hook to CI (Render provides a deploy webhook URL)
2. Or use Render's GitHub auto-deploy (connect repo, auto-deploy on push to main)
3. Add deployment smoke test after deploy:
   ```yaml
   deploy:
     needs: [backend-tests, frontend-tests]
     runs-on: ubuntu-latest
     steps:
       - run: curl -f https://your-app.onrender.com/api/health
   ```
4. Add coverage reporting: `pytest --cov=src --cov-report=xml`

**Dependencies:** WS3.1 (need Render deployment first)
**Verification:** Push to main → auto-deploy → health check passes

---

### WS3.5 — Environment Validation on Startup

**Problem:** App can start with missing or weak security secrets. `preflight_launch.py` exists but isn't enforced.

**Current state:**
- File: `scripts/preflight_launch.py` — validates env vars, checks secret strength
- File: `scripts/build.sh` — calls preflight checks
- App warns but continues with empty secrets

**Actions:**
1. Make preflight checks fail-fast in production (exit 1, not warning)
2. Add Redis connectivity check to preflight
3. Add database connectivity check to preflight
4. Ensure `scripts/build.sh` runs preflight and fails build if checks fail

**Dependencies:** WS1.1
**Verification:** Deploy with missing `JWT_SECRET` → build fails with clear error message

---

## WS4: Testing & Quality

**Owner:** QA Lead / Full Team
**Priority:** P1
**Estimated effort:** 5-8 days

### WS4.1 — Fix Test Collection Errors ✅ DONE (2026-02-28)

**Problem:** 6 import errors during `pytest --collect-only`. Tests won't run cleanly.

**Resolution:** Three fixes:
1. `src/security/auth_decorators.py:97` — changed `str | None` → `Optional[str]` (Python 3.9 compatibility)
2. `src/rbac/permissions.py` — added `FIRM_MANAGE_API_KEYS = "firm_manage_api_keys"` (used by admin panel API key routes)
3. `src/rbac/permissions.py` — added `FIRM_VIEW_AUDIT = "firm_view_audit"` (used by admin panel compliance/audit routes)

sentry-sdk was already in requirements.txt and now installed via WS2.1 lock file sync.

**Dependencies:** None
**Verification:** `pytest --collect-only` reports 0 errors, 4,776 tests collected (78 tests recovered from 6 broken files)

---

### WS4.2 — Test Coverage Configuration

**Problem:** No `.coveragerc`, no coverage metrics tracked, no coverage threshold enforced.

**Actions:**
1. Create `.coveragerc`:
   ```ini
   [run]
   branch = true
   source = src
   omit = */tests/*, */migrations/*, */__pycache__/*

   [report]
   precision = 2
   show_missing = true
   fail_under = 70

   [html]
   directory = htmlcov
   ```
2. Add to CI: `pytest --cov=src --cov-report=xml --cov-report=html`
3. Set initial threshold at 70% (increase to 80% over time)

**Dependencies:** WS4.1
**Verification:** CI reports coverage percentage; fails if below 70%

---

### WS4.3 — E2E Tests (Critical User Flows)

**Problem:** No end-to-end tests. User journeys not verified programmatically.

**Critical flows to test:**
1. Landing → Login → Dashboard
2. Start Tax Return → Enter Income → Calculate → View Results
3. AI Advisor → Guided Analysis → Strategy Display → Report Generation
4. Document Upload → OCR Processing → Data Extraction → Apply to Return
5. OAuth Login (Google) → Dashboard
6. CPA Login → Client List → Review Return → Approve

**Actions:**
1. Install Playwright or Cypress
2. Write 6 E2E tests covering flows above
3. Add to CI as separate job (runs after unit tests pass)
4. Use test database with seed data (`scripts/seed_demo_data.py`)

**Dependencies:** WS4.1, WS3.1 (need running app to test against)
**Verification:** All 6 E2E tests pass in CI

---

### WS4.4 — Load Testing

**Problem:** No performance baseline. Unknown capacity — how many concurrent users can the platform handle?

**Actions:**
1. Install k6 or Locust
2. Create load test scenarios:
   - 100 concurrent users browsing (GET endpoints)
   - 50 concurrent tax calculations (POST /api/calculate-tax)
   - 20 concurrent AI chat sessions (POST /api/advisor/chat)
   - 10 concurrent document uploads (POST /api/upload)
3. Establish baseline metrics:
   - p50, p95, p99 response times
   - Max concurrent users before errors
   - Database connection pool utilization
4. Document results and capacity limits

**Dependencies:** WS3.1 (need deployment to test against)
**Verification:** Load test report with response time percentiles and max capacity

---

### WS4.5 — Security Scanning in CI

**Problem:** Bandit runs in CI but only checks low-level issues. No dependency vulnerability scanning beyond `safety`.

**Actions:**
1. Upgrade Bandit to check all severity levels (currently low only)
2. Add `pip-audit` for dependency vulnerability scanning
3. Add Docker image scanning (Trivy) if using Docker deployment
4. Add OWASP dependency check
5. Create security scan summary report

**Dependencies:** None
**Verification:** CI security job runs all scanners; no high/critical findings

---

## WS5: Email & Notifications

**Owner:** Backend Lead
**Priority:** P1
**Estimated effort:** 3-4 days

### WS5.1 — Email Provider Integration

**Problem:** Email framework exists (`src/core/services/email_service.py`, `src/notifications/sendgrid_provider.py`) but sending is not fully wired. Password reset and magic link emails may not deliver.

**Current state:**
- SendGrid provider: code exists, needs API key
- SMTP provider: code exists, needs SMTP credentials
- AWS SES provider: code exists, needs region + verified sender
- Mock mode: emails logged but not sent (development default)
- Templates: password reset, magic link, welcome email templates exist

**Actions:**
1. Set up SendGrid account (free tier: 100 emails/day)
2. Configure sender domain verification (SPF, DKIM, DMARC)
3. Set `SENDGRID_API_KEY` and `SENDGRID_FROM_EMAIL` in production env
4. Test email delivery chain:
   - Password reset → email arrives → link works → password changed
   - Magic link login → email arrives → link works → user logged in
   - Welcome email → email arrives on registration
5. Set up email bounce/complaint handling
6. Test fallback: disable SendGrid → SMTP fallback works

**Dependencies:** WS1.1 (need new API keys), WS3.1 (need running deployment)
**Verification:** Send test email from production → arrives in inbox (not spam)

---

### WS5.2 — CPA Lead Notification Email

**Problem:** Tiered conversion design (doc: `2026-02-27-tiered-conversion-design.md`) specifies `POST /api/advisor/report/email` to send reports to users and notify CPA team. Endpoint referenced but not implemented.

**Actions:**
1. Implement `/api/advisor/report/email` endpoint:
   - Generate PDF report from session data
   - Send to user's email with report attached
   - Send internal notification to CPA team with lead data
2. Wire to unlock flow in `intelligent-advisor.js` (lead capture modal)
3. Use `AIReportSummarizer.generate_summary_for_email()` (already wired in Round 8)

**Dependencies:** WS5.1 (email must work first)
**Verification:** User enters email in unlock flow → receives report → CPA team notified

---

## WS6: Static Assets & Frontend

**Owner:** Frontend Lead
**Priority:** P2
**Estimated effort:** 3-5 days

### WS6.1 — Static File Optimization

**Problem:** 4,249 static files (CSS + JS) served raw with no minification, bundling, or cache-busting. Poor performance for users.

**Current state:**
- CSS: 50+ files in `/src/web/static/css/` (core, components, pages)
- JS: 40+ files in `/src/web/static/js/` (core, pages, alpine stores)
- No minification (whitespace, comments preserved)
- No bundling (each file = separate HTTP request)
- No content hashing (cache invalidation relies on browser cache)
- Storybook and Vite configured but not used for main build

**Actions:**
1. Add CSS minification: PostCSS with cssnano
2. Add JS minification: esbuild or terser
3. Add content hashing to filenames (e.g., `main.a1b2c3.css`)
4. Update Jinja2 templates to reference hashed filenames (asset manifest)
5. Or: serve through Nginx with `gzip_static` (already configured in nginx.conf)
6. Add to `scripts/build.sh`

**Dependencies:** None
**Verification:** Page load waterfall shows fewer, smaller files; Lighthouse performance score > 80

---

### WS6.2 — CDN for Static Assets

**Problem:** Static files served by application server. Every request for CSS/JS/images goes through Python.

**Actions:**
1. Option A (simple): Let Render serve static files with built-in CDN headers
2. Option B (better): Set up Cloudflare in front of Render (free tier)
   - DNS through Cloudflare
   - Static asset caching at edge
   - DDoS protection included
3. Configure cache headers: `Cache-Control: public, max-age=2592000, immutable` for hashed assets
4. Nginx config already has static caching rules (30 days) — verify they apply

**Dependencies:** WS3.1, WS6.1
**Verification:** Static assets served from CDN edge; `X-Cache: HIT` header present

---

### WS6.3 — Fix Pre-existing JS Error ✅ DONE (2026-02-28)

**Problem:** `showOfflineBanner` and `hideOfflineBanner` had duplicate declarations at lines ~11331/11342 in `intelligent-advisor.js`.

**Resolution:** Removed duplicate `showOfflineBanner` (dynamic-create version) and `hideOfflineBanner` (fade-remove version) at lines 11331-11348. Kept the original declarations at lines 1835/1842 which correctly toggle the existing HTML `#offlineBanner` element. The `window.addEventListener` event handlers (offline/online) that called these functions were preserved. Verified zero duplicate function names remain across 110+ functions in the file.

**Dependencies:** None
**Verification:** Single declaration per function; all 4 call sites reference the surviving definition

---

### WS6.4 — DOMPurify Self-Hosted

**Problem:** DOMPurify loaded from CDN (`cdn.jsdelivr.net`). If CDN is down, XSS protection fails silently.

**Current state:**
- `<script src="https://cdn.jsdelivr.net/npm/dompurify@3.2.4/dist/purify.min.js"></script>`
- Same for Alpine.js: loaded from jsdelivr CDN

**Actions:**
1. Download DOMPurify and Alpine.js to `/src/web/static/js/vendor/`
2. Update templates to reference local copies
3. Add SRI (Subresource Integrity) hash if keeping CDN as primary
4. Implement fallback: local copy if CDN fails

**Dependencies:** None
**Verification:** App works with CDN blocked (disable network to jsdelivr)

---

## WS7: Launch Verification

**Owner:** Full Team
**Priority:** P0 (gate before launch)
**Estimated effort:** 2-3 days

### WS7.1 — Pre-Launch Checklist

Run through every item before going live:

**Security:**
- [ ] All secrets rotated (WS1.1)
- [ ] `.env` removed from git history
- [ ] HTTPS enforced (HSTS header present)
- [ ] CORS_ORIGINS set to production domain only
- [ ] CSRF protection active on all state-changing endpoints
- [ ] Rate limiting configured (60 req/min general, 5 req/min login)
- [ ] CSP headers set correctly
- [ ] No `str(e)` leaking internal errors to API responses

**Database:**
- [ ] PostgreSQL (Neon) connected and healthy
- [ ] Migrations run successfully
- [ ] Backup/restore tested
- [ ] Connection pool sized appropriately

**Redis:**
- [ ] Upstash Redis connected and healthy
- [ ] Session persistence working
- [ ] Rate limiter using Redis (not in-memory)
- [ ] Token revocation working

**Application:**
- [ ] `GET /api/health` returns 200
- [ ] `GET /health/ready` returns 200 (all dependencies healthy)
- [ ] Landing page loads correctly
- [ ] Login/registration flow works
- [ ] Tax calculation produces correct results
- [ ] AI advisor responds (test with sample message)
- [ ] Document upload works (PDF + image)
- [ ] Report generation produces valid PDF

**Email:**
- [ ] Password reset email sends and link works
- [ ] Welcome email sends on registration

**Monitoring:**
- [ ] Sentry configured and receiving test error
- [ ] Health check endpoint monitored (UptimeRobot or similar)

---

### WS7.2 — Smoke Test Suite

**Problem:** No automated smoke test for production environment.

**Actions:**
1. Create `scripts/smoke_test.py` that hits critical endpoints:
   ```python
   GET  /                      → 200
   GET  /api/health            → 200, {"status": "healthy"}
   GET  /health/ready          → 200
   GET  /login                 → 200
   GET  /intelligent-advisor   → 200
   POST /api/calculate-tax     → 200 (with sample data)
   GET  /static/css/core/variables.css → 200
   ```
2. Run after every deployment
3. Add to CI as post-deploy step

**Dependencies:** WS3.1
**Verification:** `python scripts/smoke_test.py https://your-app.onrender.com` passes

---

### WS7.3 — Data Seeding

**Problem:** Production database will be empty. Need demo data for testing and initial setup.

**Current state:**
- File: `scripts/seed_demo_data.py` exists
- File: `scripts/setup_platform_admin.py` exists

**Actions:**
1. Run `scripts/setup_platform_admin.py` to create first admin user
2. Verify admin can log in and access `/admin` dashboard
3. Optionally seed demo data for testing (remove before real launch)
4. Verify demo CPA firm can be created and configured

**Dependencies:** WS2.3 (migrations must be complete)
**Verification:** Admin login works; admin dashboard shows system status

---

## WS8: Post-Launch & Monitoring

**Owner:** Platform Lead
**Priority:** P2 (after launch)
**Estimated effort:** Ongoing

### WS8.1 — Log Aggregation

**Problem:** Logs go to stdout in JSON format. No centralized log viewing, searching, or alerting.

**Current state:**
- JSON logging configured for production
- PII sanitization in logs (good)
- No log forwarding to any service

**Actions:**
1. Option A (free): Use Render's built-in log viewer (limited retention)
2. Option B (better): Set up Papertrail or Logtail (free tiers available)
3. Option C (best): Set up Datadog or ELK stack
4. Configure log retention: 30 days minimum
5. Set up alerts for: error rate spikes, 5xx responses, auth failures

**Dependencies:** WS3.1
**Verification:** Can search logs by request ID; alert fires on test error

---

### WS8.2 — Uptime Monitoring

**Problem:** No external monitoring. If the app goes down, nobody knows.

**Actions:**
1. Set up UptimeRobot (free: 50 monitors, 5-min intervals)
   - Monitor `GET /api/health` → expect 200
   - Monitor `GET /health/ready` → expect 200
2. Configure alerts: email + Slack/Discord
3. Set up status page (optional): UptimeRobot public status page

**Dependencies:** WS3.1
**Verification:** Take app down → alert received within 5 minutes

---

### WS8.3 — Performance Monitoring

**Problem:** No APM (Application Performance Monitoring). Can't identify slow endpoints or bottlenecks.

**Current state:**
- Sentry configured for error tracking (not APM)
- Basic `/metrics` endpoint with request counts and latencies
- No Prometheus/Grafana

**Actions:**
1. Enable Sentry Performance (free tier includes performance monitoring)
2. Set trace sample rate to 20% for production
3. Monitor: p50/p95 response times, throughput, error rates
4. Set up performance alerts: p95 > 3s for any endpoint

**Dependencies:** WS3.1
**Verification:** Sentry performance dashboard shows transaction traces

---

### WS8.4 — Account Lockout Policy

**Problem:** Failed login attempts tracked but no account lockout implemented.

**Actions:**
1. Add max failed attempts (5) with 15-minute lockout
2. Log lockout events for security monitoring
3. Add admin unlock capability

**Dependencies:** WS1.1
**Verification:** 5 wrong passwords → account locked → unlocks after 15 min

---

### WS8.5 — RBAC Auth Unification

**Problem:** Two separate auth systems exist — `verify_session_token` for advisor API and `@require_auth(roles=[Role.ADMIN])` for main app. Admin endpoints in advisor API have a TODO for RBAC integration.

**Current state:**
- Advisor API: simple session token verification (no role checks)
- Main app: full RBAC with 8 roles, 50+ permissions
- TODO in code: unify advisor sessions with main auth system

**Actions:**
1. Create auth adapter that bridges advisor sessions to RBAC system
2. Add role-based access to admin-only advisor endpoints (`/ai-metrics`, `/ai-routing-stats`)
3. Ensure CPA users can access advisor on behalf of clients (tenant isolation)

**Dependencies:** WS7.1 (launch first, unify post-launch)
**Verification:** Only admin users can access `/ai-metrics`; CPA users see only their clients

---

## Dependency Graph (Execution Order)

```
Week 1 (Parallel):
├── WS1.1  Rotate secrets                    [Security Lead]  ✅ DONE
├── WS1.5  CSRF alignment                    [Backend]        ✅ DONE
├── WS2.1  Lock file                         [Backend]        ✅ DONE
├── WS3.3  .dockerignore                     [DevOps]         ✅ DONE
├── WS4.1  Fix test collection               [QA]             ✅ DONE
├── WS6.3  Fix duplicate JS function         [Frontend]       ✅ DONE
└── WS6.4  Self-host CDN dependencies        [Frontend]

Week 2 (Depends on Week 1):
├── WS1.2  Secrets management                [Security Lead]  ← WS1.1
├── WS2.2  Redis configuration               [Backend]        ← WS1.1
├── WS2.3  Alembic migrations                [Backend]        ← WS2.1
├── WS3.5  Startup validation                [DevOps]         ← WS1.1
├── WS4.2  Coverage configuration            [QA]             ← WS4.1
├── WS4.5  Security scanning CI              [QA]
└── WS6.1  Static file optimization          [Frontend]

Week 3 (Depends on Week 2):
├── WS1.3  MFA implementation                [Security Lead]  ← WS1.1
├── WS1.4  OAuth state to Redis              [Backend]        ← WS2.2
├── WS2.4  Backup strategy                   [Backend]        ← WS2.3
├── WS3.1  Render deployment                 [DevOps]         ← WS1.1, WS2.1, WS2.2
├── WS5.1  Email provider                    [Backend]        ← WS1.1, WS3.1
└── WS6.2  CDN setup                         [Frontend]       ← WS3.1, WS6.1

Week 4 (Depends on Week 3):
├── WS3.2  SSL verification                  [DevOps]         ← WS3.1
├── WS3.4  CI/CD deploy step                 [DevOps]         ← WS3.1
├── WS4.3  E2E tests                         [QA]             ← WS4.1, WS3.1
├── WS4.4  Load testing                      [QA]             ← WS3.1
├── WS5.2  CPA lead notification             [Backend]        ← WS5.1
├── WS7.2  Smoke test suite                  [DevOps]         ← WS3.1
└── WS7.3  Data seeding                      [Backend]        ← WS2.3

Week 5 (Launch Gate):
├── WS7.1  Pre-launch checklist              [Full Team]      ← ALL above
└── 🚀 GO LIVE

Post-Launch:
├── WS8.1  Log aggregation                   [DevOps]
├── WS8.2  Uptime monitoring                 [DevOps]
├── WS8.3  Performance monitoring            [DevOps]
├── WS8.4  Account lockout                   [Security Lead]
└── WS8.5  RBAC unification                  [Backend]
```

---

## External Accounts Required

| Service | Purpose | Tier | Cost | Sign-up URL |
|---------|---------|------|------|-------------|
| **Render** | App hosting | Free | $0/mo | render.com |
| **Neon** | PostgreSQL | Free | $0/mo | neon.tech |
| **Upstash** | Redis | Free | $0/mo | upstash.com |
| **OpenAI** | AI/LLM | Pay-as-you-go | ~$5-50/mo | platform.openai.com |
| **SendGrid** | Email | Free (100/day) | $0/mo | sendgrid.com |
| **Sentry** | Error tracking | Free (5K events) | $0/mo | sentry.io |
| **GitHub** | Repository | Free | $0/mo | github.com |
| **UptimeRobot** | Monitoring | Free (50 monitors) | $0/mo | uptimerobot.com |
| **Cloudflare** | CDN/DNS (optional) | Free | $0/mo | cloudflare.com |
| **Google Cloud** | OAuth (optional) | Free | $0 | console.cloud.google.com |
| **Microsoft Azure** | OAuth (optional) | Free | $0 | portal.azure.com |
| **Stripe** | Payments (optional) | Pay-as-you-go | 2.9%+$0.30 | stripe.com |

**Minimum viable launch:** Render + Neon + Upstash + OpenAI + GitHub = ~$5-10/mo

---

## Environment Variables Checklist

### Required (app won't start without these):
```bash
APP_ENVIRONMENT=production
APP_SECRET_KEY=<64-char hex>
JWT_SECRET=<64-char hex>
AUTH_SECRET_KEY=<64-char hex>
CSRF_SECRET_KEY=<64-char hex>
PASSWORD_SALT=<32-char hex>
ENCRYPTION_MASTER_KEY=<64-char hex>
SSN_HASH_SECRET=<64-char hex>
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
CORS_ORIGINS=https://your-domain.com
```

### Required for AI features:
```bash
OPENAI_API_KEY=sk-...
AI_CHAT_ENABLED=true
AI_SAFETY_CHECKS=true
```

### Recommended:
```bash
SENTRY_DSN=https://...@sentry.io/...
SENDGRID_API_KEY=SG....
SENDGRID_FROM_EMAIL=noreply@your-domain.com
```

### Optional:
```bash
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
STRIPE_SECRET_KEY=sk_live_...
GOOGLE_ANALYTICS_ID=G-...
```

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| ~~Leaked secrets in git history~~ | ~~Critical~~ | ~~Confirmed~~ | RESOLVED — `.env` was never committed. Local dev secrets rotated. |
| Render free tier sleeps after 15 min | High (UX) | Certain | Upgrade to paid ($7/mo) or accept 5s cold start |
| Neon free tier 0.5GB limit | Medium | Medium | Monitor usage; upgrade when approaching limit |
| OpenAI API outage | High | Low | Anthropic/Google fallback chain already implemented |
| No MFA → account takeover | High | Low | WS1.3 — implement before CPA onboarding |
| No load testing → unknown capacity | Medium | High | WS4.4 — test before marketing push |
| Email deliverability issues | Medium | Medium | WS5.1 — verify domain, test SPF/DKIM |
| Single region (Oregon) → latency for East Coast | Low | Certain | Accept for MVP; add region later |

---

## Success Criteria

**Launch is successful when:**
1. App accessible at production URL with < 3s page load
2. User can complete full tax advisory flow (login → advisor → report)
3. AI chat responds correctly to tax questions
4. Document upload and OCR extraction works
5. Report PDF generates and downloads
6. No critical security vulnerabilities (Bandit + Safety clean)
7. Health checks passing continuously for 24 hours
8. Sentry receiving and tracking errors
9. At least one test email delivered successfully
10. Admin can log in and view system status
