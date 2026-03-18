# Developer QA Walkthrough Guide

**Date:** 2026-03-18
**Purpose:** Step-by-step guide for verifying every screen, button, and feature after go-live readiness fixes.

---

## How to Use This Guide

1. Start the app: `cd src && python3 -m uvicorn web.app:app --reload --port 8000`
2. Open browser to `http://localhost:8000`
3. Walk through each section below in order
4. Mark each checkpoint PASS/FAIL
5. Report any FAIL items with screenshot + browser console output

---

## SECTION 1: Public / Anonymous User Flow

### 1.1 Landing Page
| URL | `/` or `/landing` |
|-----|-----|
| **What to see** | Marketing landing page with CTA buttons |
| **Why it matters** | First impression, SEO entry point |
| **Check** | All links work, images load, no console errors |

### 1.2 Legal Pages
| Page | URL | What Changed (Go-Live Fix) |
|------|-----|---------------------------|
| **Privacy Policy** | `/privacy` | New Section 4.3 "AI Processing Providers" — must list Anthropic (Claude) and OpenAI. New GDPR Art. 22 disclosure about automated decision-making. |
| **Terms of Service** | `/terms` | New "AI-Powered Analysis" bullet in Section 2 — mentions Anthropic and OpenAI. |
| **Cookie Policy** | `/cookies` | No changes — verify it loads. |
| **Disclaimer** | `/disclaimer` | No changes — verify it loads. |

**Checkpoints:**
- [ ] Privacy page shows "4.3 AI Processing Providers" section
- [ ] Privacy page shows GDPR Art. 22 automated decision-making disclosure
- [ ] Terms page shows "AI-Powered Analysis" bullet
- [ ] All 4 legal pages render without errors

### 1.3 Lead Magnet Funnel (Anonymous → Lead Capture)
| Step | URL | What to See |
|------|-----|-------------|
| CPA Landing | `/cpa-landing` or `/for-cpas` | CPA-branded landing with lead magnet |
| Quick Estimate | `/quick-estimate` or `/estimate` | Tax estimate calculator |
| Lead Magnet Landing | Lead magnet pages (CPA-specific URLs) | Tier 1 free report, Tier 2 locked |

**Why:** This is the CPA's client acquisition funnel. The schema bridge (`lead_magnet_report_builder.py`) now converts lead magnet income ranges into full `TaxProfileInput` for advisory reports.

**Checkpoints:**
- [ ] Quick estimate form accepts inputs and returns results
- [ ] Lead capture form appears when score >= 60
- [ ] **NEW: Lead consent dialog appears BEFORE sending data to CPA** (was automatic before, now requires user opt-in)

---

## SECTION 2: Intelligent Advisor (Core Product)

### 2.1 Advisor Main Screen
| URL | `/file` or `/intelligent-advisor` |
|-----|-----|
| **Template** | `intelligent_advisor.html` |
| **JS Entry** | `static/js/advisor/modules/index.js` → loads 5 sub-modules |

**What to see on load:**
1. Consent modal appears first
2. **FIX VERIFIED:** Consent modal says "Auto-Deleted After **24 Hours**" (was incorrectly "30 Days")
3. After accepting consent, chat interface loads with quick-action buttons
4. Connection status indicator (top right) shows green/online
5. Dark mode toggle works in header

**Checkpoints:**
- [ ] Consent modal renders with correct "24 Hours" text
- [ ] Quick action buttons visible: "Start Filing", "Upload Document", etc.
- [ ] Dark mode toggle works (click sun/moon icon)
- [ ] **FIX VERIFIED:** No `ReferenceError: getIcon is not defined` in console when toggling theme
- [ ] Connection status shows "Online" with green indicator

### 2.2 Chat Flow — Gathering Tax Profile
| Action | What Happens | Go-Live Fix |
|--------|-------------|-------------|
| Click "Start Filing" | Bot asks for name | — |
| Enter name | Bot asks for email | — |
| Enter email | Bot asks for filing status | — |
| Select filing status | Bot asks for income | — |
| Enter income | Bot asks for state | — |
| Enter state | **Bot asks about dependents** | **CRITICAL FIX:** Was NEVER asking this question due to `&&` vs `==` null bug in `advisor-flow.js:347` |
| Answer dependents | Bot continues to deductions | — |

**Checkpoints:**
- [ ] **CRITICAL: Dependents question IS asked** (type a state like "IL", then verify next question is about dependents)
- [ ] All quick-action buttons in chat messages are clickable
- [ ] Chat messages render with proper HTML (no raw tags)
- [ ] Input field accepts Enter key to send

### 2.3 Document Upload
| Action | What to See |
|--------|-------------|
| Click upload icon | Upload options modal appears |
| Select "File Upload" | File picker opens |
| Select a PDF/image | File preview modal shows |
| Click "Upload" | Progress indicator, then success message |
| Select "Camera Capture" | Camera interface opens (requires HTTPS or localhost) |

**Checkpoints:**
- [ ] Upload modal opens/closes cleanly
- [ ] File preview shows before upload
- [ ] Upload progress indicator works
- [ ] Camera option available (may need HTTPS)

### 2.4 Report Generation
| Action | What to See | Go-Live Fix |
|--------|-------------|-------------|
| Click "Generate Report" or bot suggests it | Report generation starts | — |
| Report renders | **AI-Generated badge visible** | **NEW:** "AI-Generated Analysis — Verify with a licensed tax professional" badge on narrative sections |
| Click "Download PDF" | PDF downloads | **FIX:** Tier check now uses `get_effective_access_level()` — free users get 403 |
| Click "Email Report" | Email dialog | **FIX:** CAN-SPAM compliant (physical address, unsubscribe link, sender ID) |

**Checkpoints:**
- [ ] Report preview page loads (`/advisory-report-preview`)
- [ ] **NEW: AI-Generated badge visible** on narrative sections
- [ ] **NEW: IRS Circular 230 disclaimer** visible at bottom of report preview (non-dismissible)
- [ ] PDF download works (if user has Basic+ tier)
- [ ] Free tier users see 403 error on PDF download attempt
- [ ] Email report includes unsubscribe link and physical address

### 2.5 Premium / Lead Capture Features
| Action | What to See |
|--------|-------------|
| "Unlock Premium Strategies" button in chat | Lead capture form appears |
| Submit lead capture form | **NEW:** Consent dialog before sending to CPA |
| Dismiss lead capture | Form closes cleanly |

**Checkpoints:**
- [ ] Premium unlock button works in dynamically-rendered chat messages
- [ ] Lead capture submit triggers consent dialog
- [ ] Dismiss button works without errors

### 2.6 Offline / Network Resilience
| Action | What to See | Go-Live Fix |
|--------|-------------|-------------|
| Disable network (DevTools → Network → Offline) | Status changes to "Offline" | — |
| Send a message while offline | Message queued, shown as pending | **FIX:** Offline queue now works — `_setProcessAIResponse` bridge was not wired |
| Re-enable network | Queued messages sent automatically | — |

**Checkpoints:**
- [ ] Offline indicator appears when network disabled
- [ ] **FIX VERIFIED:** Messages sent offline are queued and replayed when back online
- [ ] No unhandled promise rejections in console

### 2.7 Session Persistence
| Action | What to See |
|--------|-------------|
| Complete a partial chat | Session auto-saves |
| Reload page | Resume banner appears |
| Click "Resume" | Previous conversation restored |
| Click "Dismiss" | Fresh start |

**Checkpoints:**
- [ ] Auto-save fires periodically (check Network tab for save requests)
- [ ] Resume banner appears on reload if session exists
- [ ] Session restore loads previous messages

---

## SECTION 3: CPA Dashboard

### 3.1 CPA Dashboard Home
| URL | `/cpa/dashboard` (via CPA login) |
|-----|-----|
| **Template** | `cpa/dashboard.html` |

**Screens to verify:**
| Page | URL Pattern | What to See |
|------|-------------|-------------|
| Dashboard | `/cpa/dashboard` | Overview metrics, recent leads |
| Clients | `/cpa/clients` | Client list |
| Leads List | `/cpa/leads` | Lead pipeline |
| Leads Pipeline | `/cpa/leads/pipeline` | Kanban-style pipeline |
| Lead Detail | `/cpa/leads/{id}` | Individual lead info |
| Return Queue | `/cpa/returns/queue` | Returns awaiting review |
| Return Review | `/cpa/returns/{id}/review` | Individual return review |
| Team | `/cpa/team` | Team members |
| Appointments | `/cpa/appointments` | Calendar view |
| Deadlines | `/cpa/deadlines` | Tax deadline tracker |
| Tasks | `/cpa/tasks` | Task management |
| Messaging | `/cpa/messaging` | Client messages |
| Analytics | `/cpa/analytics` | Practice analytics |

### 3.2 CPA Settings
| Page | URL | Go-Live Fix |
|------|-----|-------------|
| **Branding** | `/cpa/settings/branding` | **FIX:** Logo upload no longer accepts SVG (XSS risk). Upload validates file type via `validate_upload()` |
| **Payments** | `/cpa/settings/payments` | Note: Uses Tailwind CDN (known, non-blocking) |
| **Profile** | `/cpa/profile` | — |
| **Billing** | `/cpa/billing` | — |

**Checkpoints:**
- [ ] All 13+ CPA dashboard pages load without errors
- [ ] Logo upload rejects SVG files
- [ ] Logo upload rejects files > size limit
- [ ] Branding changes reflect in client-facing reports
- [ ] Payment settings page loads (Tailwind CDN warning is expected)

---

## SECTION 4: Admin Panel

### 4.1 Admin Dashboard
| URL | `/admin` |
|-----|-----|
| **Template** | `admin_dashboard.html` |

**Admin sub-pages:**

| Page | URL | What to See |
|------|-----|-------------|
| User Management | `/admin/users` | List, edit, role assignment |
| Tenant Management | `/admin/tenants` | Multi-tenant config |
| API Keys | `/admin/api-keys` | Key management, rotation |
| Compliance | `/admin/compliance` | Compliance reports, alerts |
| Refunds | `/admin/refunds` | Refund approval queue |
| Impersonation | `/admin/impersonate` | Support impersonation |
| System Hub | `/hub` or `/system-hub` | System-wide overview |
| Workflow Hub | `/workflow` or `/workflow-hub` | Workflow management |

**Checkpoints:**
- [ ] Admin dashboard loads with metrics grid
- [ ] User management shows user list with roles
- [ ] API key rotation works
- [ ] Compliance alerts list renders
- [ ] GDPR erasure endpoint accessible (`POST /api/gdpr/erasure`)

---

## SECTION 5: Tax Calculation Screens

### 5.1 Specialized Tax Forms
| Screen | URL | What to See |
|--------|-----|-------------|
| Capital Gains | `/capital-gains` | Transaction entry, wash sale detection, Form 8949, Schedule D |
| K-1 Basis | `/k1-basis` | K-1 records, basis worksheets |
| Rental Depreciation | `/rental-depreciation` | Property entry, depreciation schedules |
| Draft Forms | `/draft-forms` | Form 1040 generation |
| Filing Package | `/filing-package` | Package download (PDF/ZIP) |
| Computation Worksheet | `/computation-worksheet` | Detailed computation |
| Scenarios | `/scenarios` or `/projections` | What-if analysis |
| Results | `/results` | Calculation results |

**Checkpoints:**
- [ ] Each page loads without 500 errors
- [ ] Forms accept input and return calculations
- [ ] PDF exports work on applicable pages

### 5.2 Document Management
| Screen | URL | What to See |
|--------|-----|-------------|
| Document Library | `/documents/library` | Uploaded documents list |
| Document Viewer | `/documents/{id}/view` | Individual document view |

---

## SECTION 6: Health & Monitoring Endpoints

### 6.1 Health Checks
| Endpoint | URL | What to See | Go-Live Fix |
|----------|-----|-------------|-------------|
| Liveness | `GET /api/health/` | `{"status": "healthy"}` | — |
| Readiness | `GET /api/health/ready` | Dependencies list with status | **FIX:** `psutil` wrapped in try/except, `calculator` import path fixed |
| Metrics | `GET /api/health/metrics` | CPU, memory, disk, connections | Works even if psutil not installed (returns 0s) |
| Dependencies | `GET /api/health/dependencies` | Database, Redis, OCR, Tax Calculator, **AI Providers** | **NEW:** AI provider health check registered |

**Checkpoints:**
- [ ] `/api/health/` returns 200 with `"healthy"`
- [ ] `/api/health/ready` returns dependency list (no import errors)
- [ ] `/api/health/dependencies` includes `ai_providers` entry
- [ ] Database shows "up" with table count
- [ ] Redis shows status (up or degraded with fallback message)
- [ ] OCR shows available engines (or graceful degradation message)

### 6.2 Alternative Health Endpoints
| Endpoint | URL | Purpose |
|----------|-----|---------|
| `/health` | Root health | Basic status |
| `/health/live` | Liveness probe | K8s liveness |
| `/health/ready` | Readiness probe | K8s readiness |
| `/metrics` | Prometheus-style | Monitoring |

---

## SECTION 7: Auth Pages

| Screen | URL(s) | What to See |
|--------|--------|-------------|
| Login | `/login`, `/signin`, `/auth/login` | Login form |
| Signup | `/signup`, `/register`, `/auth/register` | Registration form |
| Forgot Password | `/forgot-password` | Email input |
| Reset Password | `/reset-password` | New password form |
| MFA Setup | `/auth/mfa-setup` | QR code for authenticator |
| MFA Verify | `/auth/mfa-verify` | OTP input |
| Client Login | `/client/login` | Client-specific login |

**Checkpoints:**
- [ ] All auth pages render without errors
- [ ] Login form validates input
- [ ] Signup form validates input
- [ ] Forgot password sends email
- [ ] MFA setup shows QR code

---

## SECTION 8: Support & Task Management

| Screen | URL | What to See |
|--------|-----|-------------|
| Support Tickets | `/support` or `/support/tickets` | Ticket list |
| Create Ticket | `/support/new` | Ticket form |
| Ticket Detail | `/support/tickets/{id}` | Messages, status |
| Task List | `/tasks` | Task list view |
| Task Kanban | `/tasks/kanban` | Kanban board |
| Task Detail | `/tasks/{id}` | Task details |
| Appointments | `/appointments` | Calendar |
| Book Appointment | `/appointments/book` | Booking form |
| Deadlines | `/deadlines` | Deadline list |
| Deadline Calendar | `/deadlines/calendar` | Calendar view |
| Notification Settings | `/settings/notifications` | Notification preferences |

---

## SECTION 9: API Smoke Tests (via curl or Postman)

Run these from terminal to verify backend APIs:

```bash
BASE=http://localhost:8000

# 1. Health
curl -s $BASE/api/health/ | python3 -m json.tool

# 2. Readiness (all dependencies)
curl -s $BASE/api/health/ready | python3 -m json.tool

# 3. Chat (Intelligent Advisor)
curl -s -X POST $BASE/api/advisor/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "session_id": "test-123"}' | python3 -m json.tool

# 4. Tax Calculation
curl -s -X POST $BASE/api/calculate-tax \
  -H "Content-Type: application/json" \
  -d '{"filing_status": "single", "income": 75000, "state": "CA"}' | python3 -m json.tool

# 5. Input Validation (should reject invalid state)
curl -s -X POST $BASE/api/advisor/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "tax_profile": {"state": "INVALID"}}' | python3 -m json.tool
```

**Checkpoints:**
- [ ] Health returns 200
- [ ] Chat endpoint responds (may need valid AI keys for full response)
- [ ] Invalid input (state="INVALID") returns 422 validation error
- [ ] Message > 4000 chars returns 422

---

## SECTION 10: Security Fixes to Verify

| Fix | How to Verify |
|-----|--------------|
| **PII Scrubbing** | In server logs during report generation, check that AI prompts do NOT contain SSN, email, phone, address, or exact dollar amounts (rounded to nearest $1000) |
| **Input Validators** | Send `state: "XYZ"` → should get 422. Send `age: 200` → should get 422. Send message > 4000 chars → should get 422. |
| **Thread-safe singletons** | Under load, AI narrative/summarizer instances don't create duplicates (check logs for "Creating new instance" — should appear only once) |
| **Redis reconnection** | If Redis goes down and comes back, health check should auto-reconnect (no stale singleton) |
| **Session no-autocreate** | `GET /api/advisor/report?session_id=nonexistent` → should return 404, NOT create a new session |
| **CORS in production** | Set `APP_ENVIRONMENT=production` without `CORS_ORIGINS` → should log critical warning |
| **SVG upload blocked** | Upload an SVG file as CPA logo → should be rejected |
| **Consent persistence** | After accepting advisor consent, check database `consent_audit_log` table has a new row |

---

## SECTION 11: Go-Live Fix Summary (What Changed and Where)

| # | Fix | File(s) | Severity |
|---|-----|---------|----------|
| 1 | AGI÷0 → AGI÷0 safe | `report_generator.py`, `recommendation_engine.py` | CRITICAL |
| 2 | Null taxpayer guard | `report_generator.py` | CRITICAL |
| 3 | Dependents question never asked | `advisor-flow.js:347` | CRITICAL |
| 4 | Offline queue not wired | `index.js` | CRITICAL |
| 5 | Hardcoded tax_year=2025 | `recommendation_engine.py` | HIGH |
| 6 | Thread-safe AI singletons | `ai_narrative_generator.py`, `report_summarizer.py` | HIGH |
| 7 | Redis encryption type mismatch | `redis_session_persistence.py` | HIGH |
| 8 | Email import path wrong | `report_generation.py` | HIGH |
| 9 | PDF hardcoded platform name | `advisory_pdf_exporter.py` | MEDIUM |
| 10 | Input validators missing | `models.py` | HIGH |
| 11 | SVG upload allowed | `report_generation.py` | HIGH |
| 12 | Session auto-create on reports | `intelligent_advisor_api.py` | MEDIUM |
| 13 | PDF tier not enforced | `report_routes.py` | HIGH |
| 14 | Consent not persisted to DB | `intelligent_advisor_api.py` + migration | HIGH |
| 15 | Lead sent without consent | `advisor-data.js`, `advisor-display.js` | HIGH |
| 16 | Privacy missing AI disclosure | `privacy.html` | HIGH |
| 17 | Email not CAN-SPAM compliant | `report_generation.py` | HIGH |
| 18 | AI content not labeled | `ai_narrative_generator.py`, `advisory_report_preview.html` | HIGH |
| 19 | Consent says "30 days" (actual: 24h) | `intelligent_advisor.html` | MEDIUM |
| 20 | Terms missing AI disclosure | `terms.html` | MEDIUM |
| 21 | Circular 230 missing from preview | `advisory_report_preview.html` | MEDIUM |
| 22 | PII sent to AI providers | New `pii_scrubber.py` | HIGH |
| 23 | Report generation no timeout | `report_generator.py` | MEDIUM |
| 24 | Redis singleton stale | `redis_session_persistence.py` | MEDIUM |
| 25 | AI health check missing | `health_checks.py` | LOW |
| 26 | Nginx proxy timeout missing | `nginx.production.conf` | MEDIUM |
| 27 | Recommendation crash not caught | `report_generator.py` | MEDIUM |
| 28 | getIcon ReferenceError | `advisor-core.js` | MEDIUM |
| 29 | CPA branding NameError in email | `report_generation.py` | MEDIUM |
| 30 | psutil ImportError | `health_checks.py` | LOW |
| 31 | Calculator import path wrong | `health_checks.py` | LOW |
| 32 | dashboard.css 404 | New `dashboard.css` | LOW |
| 33 | Perplexity no timeout | `unified_ai_service.py` | MEDIUM |
| 34 | Budget alerts missing | `metrics_service.py` | LOW |
| 35 | Unified gating model | `tier_control.py` | MEDIUM |
| 36 | Schema bridge missing | New `lead_magnet_report_builder.py` | MEDIUM |
| 37 | CORS not validated in prod | `middleware_setup.py` | MEDIUM |
| 38 | GDPR Art. 22 missing | `privacy.html` | MEDIUM |
| 39 | Unhandled promise rejection | `advisor-data.js` | LOW |

---

## Quick Reference: All URLs by Role

### Public (No Login)
```
/                          Landing
/landing                   Landing (alt)
/quick-estimate            Quick estimate
/estimate                  Estimate (alt)
/privacy                   Privacy policy
/terms                     Terms of service
/cookies                   Cookie policy
/disclaimer                Disclaimer
/login                     Login
/signup                    Signup
/forgot-password           Forgot password
/for-cpas                  CPA marketing
```

### Authenticated User
```
/file                      Intelligent Advisor (main product)
/intelligent-advisor       Intelligent Advisor (alt)
/dashboard                 User dashboard
/profile                   Profile settings
/documents/library         Document library
/scenarios                 What-if scenarios
/results                   Calculation results
/capital-gains             Capital gains tracker
/k1-basis                  K-1 basis tracking
/rental-depreciation       Rental depreciation
/draft-forms               Form 1040 drafts
/filing-package            Filing package download
/computation-worksheet     Computation details
/advisory-report-preview   Report preview
/support                   Support tickets
/tasks                     Task list
/appointments              Appointments
/deadlines                 Tax deadlines
```

### CPA Users
```
/cpa/dashboard             CPA dashboard
/cpa/clients               Client management
/cpa/leads                 Lead pipeline
/cpa/returns/queue         Return queue
/cpa/team                  Team management
/cpa/appointments          CPA appointments
/cpa/deadlines             CPA deadlines
/cpa/tasks                 CPA tasks
/cpa/messaging             Client messaging
/cpa/analytics             Practice analytics
/cpa/settings/branding     Firm branding
/cpa/settings/payments     Payment settings
/cpa/profile               CPA profile
/cpa/billing               Billing
```

### Admin Users
```
/admin                     Admin dashboard
/admin/users               User management
/admin/tenants             Tenant management
/admin/api-keys            API key management
/admin/compliance          Compliance reports
/admin/refunds             Refund approval
/hub                       System hub
/workflow                  Workflow hub
```

### API Health (No Auth)
```
/api/health/               Liveness probe
/api/health/ready           Readiness probe
/api/health/metrics         System metrics
/api/health/dependencies    Dependency status
```
