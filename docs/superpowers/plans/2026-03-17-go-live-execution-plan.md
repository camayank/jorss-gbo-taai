# Jorss-GBO Go-Live Execution Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take Jorss-GBO from current ~85% ready state to production launch by merging critical worktrees, fixing remaining gaps, and running final verification.

**Architecture:** The platform is built (FastAPI + Jinja2 + Alpine.js + PostgreSQL + Redis). Most go-live workstreams (WS1-WS6) from the reverse PRD are DONE. Remaining work is: merge 3 feature branches, clean up 6 stale worktrees, fix CSP, remove dead pages, and run pre-launch verification.

**Tech Stack:** Python 3.11/FastAPI, Alpine.js, PostgreSQL 16, Redis 7, Docker, Render.com

---

## Phase 0: Situational Awareness

**Current state of worktrees (9 active, all prunable):**

| Worktree | Branch | Commits ahead | Status | Action |
|----------|--------|---------------|--------|--------|
| `critical-bug-fixes` | `fix/critical-advisor-bugs` | 6 | Critical fixes (XSS, rate limiting, imports, session, property paths, streaming) | **MERGE** |
| `frontend-wiring` | `feature/frontend-ai-wiring` | 2 | AI-enhanced fields, scenario cards, anomaly checks | **MERGE** |
| `report-enhancement` | `feature/report-system-enhancement` | 3 | AI content in reports, health monitoring | **MERGE** |
| `advisor-rebuild` | `feature/advisor-rebuild` | 3+ | V2 advisor behind feature flag | **DEFER** (post-launch) |
| `advisory-report-dashboard` | `feature/advisory-report-dashboard` | 0 | No divergent commits | **PRUNE** |
| `cpa-dashboard-fixes` | `feature/cpa-dashboard-10-fixes` | 0 | No divergent commits | **PRUNE** |
| `fsm-advisor` | `feature/fsm-advisor-redesign` | 0 | No divergent commits | **PRUNE** |
| `swot-remediation` | `feature/swot-remediation` | 0 | No divergent commits | **PRUNE** |
| `vps-deployment` | `feature/vps-deployment` | 0 | Already merged (d900f2d) | **PRUNE** |

**From reverse PRD — already DONE:** WS1.1-WS1.5, WS2.1-WS2.4, WS3.1-WS3.5, WS4.1-WS4.2, WS4.5, WS5.1-WS5.2, WS6.1-WS6.4, WS7.2-WS7.3

**Still open:**
- 5 critical bugs (plan exists, worktree has 6 fix commits)
- Journey orchestrator frontend wiring (partially done in frontend-wiring worktree)
- Advisory report dashboard route wiring
- CSP `unsafe-inline` migration
- 14+ dead/orphaned pages
- Pre-launch checklist (WS7.1)
- Post-launch monitoring (WS8.x)

---

## Phase 1: Merge Critical Bug Fixes (P0)

> **Skill:** `superpowers:requesting-code-review` before merge, `superpowers:verification-before-completion` after

### Task 1: Review and merge critical-bug-fixes worktree

**Files:**
- Review: all files changed in `fix/critical-advisor-bugs` branch (6 commits)
- Test: `tests/` (full suite)

- [ ] **Step 1: Review the 6 commits in the critical-bug-fixes branch**

```bash
git log main..fix/critical-advisor-bugs --oneline --stat
```

Review each commit for correctness:
1. `b872bd0` — XSS sanitization during streaming display
2. `d7f5048` — Property path fixes in savings guard, quick edit, summary, assessment
3. `e97c571` — Phase detection property path fix
4. `a462f83` — Session prefix guard + secureFetch for session recovery
5. `e6d9631` — Try/except wrapping for AI/ML imports
6. `dc04c98` — Chat rate limiting + sub-router failure logging

- [ ] **Step 2: Check for merge conflicts**

```bash
git merge --no-commit --no-ff fix/critical-advisor-bugs
# If conflicts, resolve them
# If clean, abort and proceed to actual merge
git merge --abort
```

- [ ] **Step 3: Merge the branch**

```bash
git merge fix/critical-advisor-bugs --no-ff -m "merge: critical advisor bug fixes (C1-C5 + XSS + rate limiting)

Fixes: DOMPurify stripping inline handlers, timer variable scoping,
missing CSRF tokens, health endpoint crash, XSS in streaming,
property path errors, session prefix guard, AI import resilience,
chat rate limiting."
```

- [ ] **Step 4: Run full test suite**

```bash
cd src && python -m pytest ../tests/ --tb=short -q 2>&1 | tail -20
```

Expected: All tests pass (4,100+)

- [ ] **Step 5: Verify JS syntax**

```bash
node --check src/web/static/js/pages/intelligent-advisor.js
```

Expected: No output (clean)

- [ ] **Step 6: Verify Python syntax**

```bash
python -m py_compile src/web/intelligent_advisor_api.py
```

Expected: No output (clean)

---

### Task 2: Review and merge frontend-wiring worktree

**Files:**
- Review: all files changed in `feature/frontend-ai-wiring` branch (2 commits)

- [ ] **Step 1: Review the 2 commits**

```bash
git log main..feature/frontend-ai-wiring --oneline --stat
```

Review:
1. `94e7ab9` — Wire AI-enhanced fields, enrich strategy cards, render urgency/warnings
2. `ee8c34b` — Multi-year/estate buttons, anomaly safety check, DRY scenario cards

- [ ] **Step 2: Check for merge conflicts with updated main (post-Task 1)**

```bash
git merge --no-commit --no-ff feature/frontend-ai-wiring
git merge --abort  # if clean
```

- [ ] **Step 3: Merge the branch**

```bash
git merge feature/frontend-ai-wiring --no-ff -m "merge: frontend AI wiring — enhanced fields, scenario cards, anomaly checks"
```

- [ ] **Step 4: Run test suite**

```bash
cd src && python -m pytest ../tests/ --tb=short -q 2>&1 | tail -20
```

---

### Task 3: Review and merge report-enhancement worktree

**Files:**
- Review: all files changed in `feature/report-system-enhancement` branch (3 commits)

- [ ] **Step 1: Review the 3 commits**

```bash
git log main..feature/report-system-enhancement --oneline --stat
```

Review:
1. `f34cea9` — AI-generated content in Tier 1/2 report templates
2. `635903a` — AI health monitoring endpoint in lead magnet routes
3. `2547d81` — Code review findings for AI integration

- [ ] **Step 2: Check for conflicts and merge**

```bash
git merge --no-commit --no-ff feature/report-system-enhancement
git merge --abort  # if clean
git merge feature/report-system-enhancement --no-ff -m "merge: report system enhancement — AI content in reports, health monitoring"
```

- [ ] **Step 3: Run test suite**

```bash
cd src && python -m pytest ../tests/ --tb=short -q 2>&1 | tail -20
```

---

## Phase 2: Clean Up Stale Worktrees

> **Skill:** `superpowers:finishing-a-development-branch`

### Task 4: Prune empty/merged worktrees

**Files:** None (git operations only)

- [ ] **Step 1: Remove the 5 stale worktrees**

```bash
git worktree remove .worktrees/advisory-report-dashboard --force 2>/dev/null
git worktree remove .worktrees/cpa-dashboard-fixes --force 2>/dev/null
git worktree remove .worktrees/fsm-advisor --force 2>/dev/null
git worktree remove .worktrees/swot-remediation --force 2>/dev/null
git worktree remove .worktrees/vps-deployment --force 2>/dev/null
```

Note: These are in `/Users/rakeshanita/Desktop/MAYANK-HQ/60_Code/jorss-gbo/.worktrees/` — may need to use full paths.

- [ ] **Step 2: Remove merged worktrees (after Phase 1 merges)**

```bash
git worktree remove .worktrees/critical-bug-fixes --force 2>/dev/null
git worktree remove .worktrees/frontend-wiring --force 2>/dev/null
git worktree remove .worktrees/report-enhancement --force 2>/dev/null
```

- [ ] **Step 3: Prune worktree metadata**

```bash
git worktree prune
git worktree list  # Should show only main worktree
```

- [ ] **Step 4: Clean up merged branches**

```bash
git branch -d fix/critical-advisor-bugs
git branch -d feature/frontend-ai-wiring
git branch -d feature/report-system-enhancement
git branch -d feature/advisory-report-dashboard
git branch -d feature/cpa-dashboard-10-fixes
git branch -d feature/fsm-advisor-redesign
git branch -d feature/swot-remediation
git branch -d feature/vps-deployment
```

Keep `feature/advisor-rebuild` (deferred to post-launch).

- [ ] **Step 5: Commit any cleanup**

```bash
git status  # Should be clean after worktree removal
```

---

## Phase 3: Wire Advisory Report Dashboard (P1)

> **Skills:** `feature-dev:feature-dev`, `superpowers:test-driven-development`

### Task 5: Wire the report preview route

**Files:**
- Modify: `src/web/advisor/report_routes.py` (add GET /report-preview/{session_id})
- Verify: `src/web/templates/advisory_report_dashboard.html` (already exists)

- [ ] **Step 1: Check if the template already exists**

```bash
ls -la src/web/templates/advisory_report_dashboard.html
```

- [ ] **Step 2: Check if the route already exists**

```bash
grep -n "report-preview" src/web/advisor/report_routes.py
```

- [ ] **Step 3: If route missing, add it per the advisory report dashboard plan**

Add the `GET /report-preview/{session_id}` endpoint from `docs/plans/2026-03-06-advisory-report-dashboard-plan.md` Task 1.

- [ ] **Step 4: Add the dashboard CSS if missing**

```bash
ls -la src/web/static/css/pages/report-dashboard.css
```

If missing, create it per the plan Task 3.

- [ ] **Step 5: Verify route loads**

```bash
cd src && python -c "from web.advisor.report_routes import _report_router; print([r.path for r in _report_router.routes])"
```

Expected: Includes `/report-preview/{session_id}`

- [ ] **Step 6: Commit**

```bash
git add src/web/advisor/report_routes.py src/web/static/css/pages/report-dashboard.css
git commit -m "feat: wire advisory report preview dashboard route and CSS"
```

---

## Phase 4: Security Hardening (P1)

> **Skills:** `superpowers:dispatching-parallel-agents` (Tasks 6-8 are independent)

### Task 6: Migrate CSP from unsafe-inline to nonces

**Files:**
- Modify: `src/security/middleware.py` (CSP header generation)
- Modify: `src/web/templates/base_modern.html` (add nonce to inline scripts)
- Modify: Any templates with inline `<script>` or `<style>` tags

- [ ] **Step 1: Audit inline scripts in templates**

```bash
grep -rn '<script' src/web/templates/ | grep -v 'src=' | grep -v 'vendor' | head -30
```

- [ ] **Step 2: Audit inline styles in templates**

```bash
grep -rn '<style' src/web/templates/ | head -20
```

- [ ] **Step 3: Add nonce generation middleware**

In `src/security/middleware.py`, add a middleware that generates a random nonce per request and stores it in `request.state.csp_nonce`:

```python
import secrets

class CSPNonceMiddleware:
    async def __call__(self, request, call_next):
        request.state.csp_nonce = secrets.token_urlsafe(16)
        response = await call_next(request)
        # Update CSP header to use nonce
        csp = response.headers.get("Content-Security-Policy", "")
        nonce = request.state.csp_nonce
        csp = csp.replace("'unsafe-inline'", f"'nonce-{nonce}'")
        response.headers["Content-Security-Policy"] = csp
        return response
```

- [ ] **Step 4: Add nonce attribute to all inline scripts in templates**

Update `<script>` tags in templates to use `nonce="{{ request.state.csp_nonce }}"`.

- [ ] **Step 5: Test that pages still load with new CSP**

Start dev server, open browser console, verify no CSP violations.

- [ ] **Step 6: Commit**

```bash
git add src/security/middleware.py src/web/templates/
git commit -m "security: migrate CSP from unsafe-inline to nonce-based policy"
```

---

### Task 7: Remove committed .db files

**Files:**
- Delete: `*.db` files in repo root
- Modify: `.gitignore` (add `*.db`)

- [ ] **Step 1: Find all .db files**

```bash
find . -name "*.db" -not -path "./.git/*" -not -path "./node_modules/*"
```

- [ ] **Step 2: Check if .db is in .gitignore**

```bash
grep '\.db' .gitignore
```

- [ ] **Step 3: Add *.db to .gitignore if missing**

```bash
echo "*.db" >> .gitignore
```

- [ ] **Step 4: Remove .db files from tracking**

```bash
git rm --cached *.db 2>/dev/null
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: remove test databases and ignore .db files"
```

---

### Task 8: Audit and remove dead/orphaned pages

**Files:**
- Audit: `src/web/templates/` (14+ pages flagged as dead)
- Modify: Router files that reference dead templates

- [ ] **Step 1: List all templates**

```bash
find src/web/templates -name "*.html" | wc -l
```

- [ ] **Step 2: Find templates not referenced by any Python file**

```bash
for tmpl in $(find src/web/templates -name "*.html" -exec basename {} \;); do
  count=$(grep -rl "$tmpl" src/ --include="*.py" | wc -l)
  if [ "$count" -eq "0" ]; then
    echo "ORPHAN: $tmpl"
  fi
done
```

- [ ] **Step 3: Review orphans — confirm they're truly dead**

Check each orphan: is it included by another template via `{% include %}` or `{% extends %}`?

```bash
for tmpl in $(echo "ORPHAN_LIST_HERE"); do
  grep -rl "$tmpl" src/web/templates/ | head -3
done
```

- [ ] **Step 4: Remove confirmed dead templates**

```bash
git rm src/web/templates/documents/viewer.html  # example
# ... repeat for each confirmed dead template
```

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: remove 14 orphaned/dead templates

Removed templates with no route or include reference:
- documents/viewer.html
- tasks/*.html
- appointments/*.html
- (list all removed)"
```

---

## Phase 5: Journey Orchestrator Frontend Wiring (P1)

> **Skills:** `feature-dev:feature-dev`, `frontend-design`

### Task 9: Register Alpine journey store in base template

**Files:**
- Verify: `src/web/static/js/alpine/stores/journey.js` (already exists)
- Modify: `src/web/templates/base_modern.html` (add script include)

- [ ] **Step 1: Verify the journey store exists**

```bash
head -30 src/web/static/js/alpine/stores/journey.js
```

- [ ] **Step 2: Check if it's already included in base template**

```bash
grep -n "journey" src/web/templates/base_modern.html
```

- [ ] **Step 3: If not included, add script tag before Alpine init**

Find the Alpine.js script tag in `base_modern.html` and add the journey store before it:

```html
<script src="/static/js/alpine/stores/journey.js"></script>
```

- [ ] **Step 4: Verify store registers on page load**

Start dev server, open browser console, type `Alpine.store('journey')` — should return the store object.

- [ ] **Step 5: Commit**

```bash
git add src/web/templates/base_modern.html
git commit -m "feat: register Alpine journey store in base template"
```

---

### Task 10: Add journey progress bar partial to sidebar

**Files:**
- Verify: Journey progress bar template exists (check `src/web/templates/partials/`)
- Modify: `src/web/templates/base_modern.html` (include progress bar partial)

- [ ] **Step 1: Find the journey progress bar template**

```bash
find src/web/templates -name "*journey*" -o -name "*progress*"
```

- [ ] **Step 2: Include it in the sidebar of base_modern.html**

Add `{% include 'partials/journey_progress.html' %}` in the sidebar section.

- [ ] **Step 3: Add the next-step CTA banner**

```bash
find src/web/templates -name "*next*step*" -o -name "*cta*" -o -name "*banner*"
```

Include the banner partial in the main content area.

- [ ] **Step 4: Verify visually**

Start dev server, navigate to advisor page, confirm progress bar shows in sidebar and updates as you progress through the journey stages.

- [ ] **Step 5: Commit**

```bash
git add src/web/templates/
git commit -m "feat: wire journey progress bar and next-step banners into base template"
```

---

## Phase 6: CI Verification & Pre-Launch (P0 Gate)

> **Skills:** `superpowers:verification-before-completion`, `superpowers:requesting-code-review`

### Task 11: Run full CI pipeline locally

**Files:** None (verification only)

- [ ] **Step 1: Run Ruff linter**

```bash
cd src && python -m ruff check . --select E,F,W,I
```

Expected: 0 errors (or only pre-existing warnings)

- [ ] **Step 2: Run Bandit security scan**

```bash
cd src && python -m bandit -r . -l --format json -o ../bandit-report.json
```

Expected: No high-severity findings

- [ ] **Step 3: Run pip-audit**

```bash
pip-audit -r requirements.lock
```

Expected: No known vulnerabilities

- [ ] **Step 4: Run full test suite with coverage**

```bash
cd src && python -m pytest ../tests/ --cov=. --cov-report=term-missing --cov-fail-under=70 -q
```

Expected: All tests pass, coverage >= 70%

- [ ] **Step 5: Run frontend checks**

```bash
npx stylelint "src/web/static/css/**/*.css" --allow-empty-input
npx vitest run --reporter=verbose 2>&1 | tail -20
```

Expected: All pass

- [ ] **Step 6: Run preflight launch script**

```bash
python scripts/preflight_launch.py --mode development
```

Expected: All checks pass

- [ ] **Step 7: Run smoke test against local**

```bash
# Start server in background first
python scripts/smoke_test.py http://localhost:8000
```

Expected: All 6 endpoints return 200

---

### Task 12: Execute pre-launch checklist (WS7.1)

**Files:** None (manual verification)

- [ ] **Step 1: Security checks**

Verify all items from WS7.1 Security section in the reverse PRD:
- All secrets unique and rotated
- HTTPS enforced (HSTS header)
- CORS set to production domain only
- CSRF protection active
- Rate limiting configured
- CSP headers set (nonce-based after Task 6)

- [ ] **Step 2: Database checks**

- PostgreSQL (Neon) connected and healthy
- Migrations run successfully
- Backup/restore tested
- Connection pool sized

- [ ] **Step 3: Redis checks**

- Upstash Redis connected
- Session persistence working
- Rate limiter using Redis
- Token revocation working

- [ ] **Step 4: Application checks**

- Health endpoints return 200
- Landing page loads
- Login/registration works
- Tax calculation correct
- AI advisor responds
- Document upload works
- Report PDF generates

- [ ] **Step 5: Email checks**

- Password reset email sends
- Welcome email sends on registration

---

## Phase 7: Deploy to Production

> **Skill:** `superpowers:executing-plans`

### Task 13: Deploy to Render

**Files:** None (ops steps)

- [ ] **Step 1: Set up external services**

1. Create Neon PostgreSQL database → get `DATABASE_URL`
2. Create Upstash Redis instance → get `REDIS_URL`
3. Get OpenAI API key → `OPENAI_API_KEY`

- [ ] **Step 2: Generate production secrets**

```bash
python scripts/generate_secrets.py --env > .env.production
# Fill in: DATABASE_URL, REDIS_URL, OPENAI_API_KEY, CORS_ORIGINS
python scripts/generate_secrets.py --verify --env-file .env.production
```

- [ ] **Step 3: Deploy via Render**

1. Connect GitHub repo to Render
2. Set all env vars from `.env.production` in Render dashboard
3. Set `RENDER_DEPLOY_HOOK_URL` in GitHub secrets
4. Push to `main` → CI runs → deploy triggers

- [ ] **Step 4: Run post-deploy smoke test**

```bash
python scripts/smoke_test.py https://your-app.onrender.com
```

- [ ] **Step 5: Verify health endpoints**

```bash
curl https://your-app.onrender.com/api/health
curl https://your-app.onrender.com/health/ready
```

Expected: Both return 200 with all dependencies healthy

- [ ] **Step 6: Seed initial data**

```bash
# On Render console or via SSH
python scripts/setup_platform_admin.py
python scripts/seed_demo_data.py  # Optional for demo
```

---

## Phase 8: Post-Launch Monitoring Setup

> **Skills:** `superpowers:dispatching-parallel-agents` (all independent)

### Task 14: Set up monitoring (WS8.1-WS8.3)

- [ ] **Step 1: Configure Sentry**

Set `SENTRY_DSN` in Render dashboard. Verify error tracking with a test error.

- [ ] **Step 2: Set up UptimeRobot**

Create monitors for:
- `GET /api/health` → expect 200 (5-min interval)
- `GET /health/ready` → expect 200 (5-min interval)

Configure email alerts.

- [ ] **Step 3: Enable Sentry Performance**

Set trace sample rate to 20% in `app.py` Sentry config.

- [ ] **Step 4: Set up log viewing**

Use Render's built-in log viewer initially. Set up Papertrail/Logtail if needed.

---

### Task 15: Post-launch hardening (WS8.4-WS8.5)

- [ ] **Step 1: Implement account lockout (WS8.4)**

Add max 5 failed attempts with 15-minute lockout to `auth_service.py`.

- [ ] **Step 2: Plan RBAC unification (WS8.5)**

Create a plan to bridge advisor session tokens with the main RBAC system.

- [ ] **Step 3: Plan E2E tests (WS4.3)**

Install Playwright, write 6 critical flow tests, add to CI.

- [ ] **Step 4: Plan load testing (WS4.4)**

Install k6, create load test scenarios, establish performance baseline.

---

## Execution Strategy: How Skills Are Used

### Parallel Agent Dispatch (Phase 1 + Phase 2)

Using `superpowers:dispatching-parallel-agents`:

```
Agent 1: Review + merge critical-bug-fixes (Task 1)
Agent 2: Review + merge frontend-wiring (Task 2) — after Agent 1
Agent 3: Review + merge report-enhancement (Task 3) — after Agent 2
Agent 4: Clean up worktrees (Task 4) — after Agents 1-3
```

Tasks 1-3 must be sequential (each merge changes main). Task 4 runs after all merges.

### Parallel Agent Dispatch (Phase 4)

Using `superpowers:dispatching-parallel-agents`:

```
Agent A: CSP nonce migration (Task 6)
Agent B: Remove .db files (Task 7)
Agent C: Audit dead pages (Task 8)
```

All three are independent — run in parallel.

### Parallel Agent Dispatch (Phase 5)

```
Agent X: Register Alpine store (Task 9)
Agent Y: Wire progress bar (Task 10) — after Agent X
```

Task 10 depends on Task 9.

### Sequential Execution (Phases 6-8)

Using `superpowers:executing-plans`:

Tasks 11-15 run sequentially — each phase gates the next.

### Code Review Checkpoints

Using `superpowers:requesting-code-review` at these gates:

1. After Phase 1 (all merges complete) — review merged main
2. After Phase 4 (security hardening) — review CSP changes
3. After Phase 6 (CI passes) — final review before deploy

### Verification Points

Using `superpowers:verification-before-completion`:

1. After each merge — run tests
2. After CSP migration — check browser console for violations
3. After full CI — all checks pass
4. After deploy — smoke test + health endpoints
5. After 24 hours — health checks stable

---

## Timeline Estimate

| Phase | Tasks | Parallelizable | Depends On |
|-------|-------|----------------|------------|
| Phase 1: Merge branches | 1-3 | Sequential | — |
| Phase 2: Clean worktrees | 4 | After Phase 1 | Phase 1 |
| Phase 3: Dashboard wiring | 5 | Independent | — |
| Phase 4: Security hardening | 6-8 | All parallel | — |
| Phase 5: Journey wiring | 9-10 | Sequential | — |
| Phase 6: CI verification | 11 | After 1-5 | Phases 1-5 |
| Phase 7: Pre-launch + Deploy | 12-13 | Sequential | Phase 6 |
| Phase 8: Post-launch | 14-15 | Parallel | Phase 7 |

**Phases 1-5 can run in parallel groups. Phase 6 is the gate. Phase 7 is deploy. Phase 8 is ongoing.**

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Merge conflicts between 3 branches | Merge in dependency order: critical-bug-fixes first (most fundamental), then frontend-wiring, then report-enhancement |
| CSP nonces break inline scripts | Test each template individually; keep `unsafe-inline` fallback ready to revert |
| Dead page removal breaks includes | Grep for `{% include %}` and `{% extends %}` references before deleting |
| Tests fail after merges | Run test suite after each merge, not just at the end |
| Render deploy fails | Have VPS deployment (docker-compose.production.yml) as fallback |
| Journey store not registering | Check Alpine.js version compatibility; verify store registration order |
