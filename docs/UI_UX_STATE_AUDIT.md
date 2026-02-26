# UI/UX STATE AUDIT — Jorss-Gbo Platform

**Generated:** 2026-02-25
**Scope:** Complete frontend analysis across 4 user roles
**Methodology:** Static analysis of 97 templates, 25+ route files, 42 static assets

---

## 1. FRONTEND ARCHITECTURE

| Attribute | Value |
|-----------|-------|
| **Template Engine** | Jinja2 (server-rendered with Storybook design system) |
| **CSS Framework** | Custom design system — CSS variables, no Bootstrap/Tailwind |
| **JS Framework** | Alpine.js v3 (lightweight reactivity) + vanilla JS |
| **Design System** | Storybook 8.0.0 — 14 stories, 19 reusable components |
| **Total HTML Templates** | 97 |
| **Total CSS Files** | 42 (core + components + themes + pages) |
| **Total JS Files** | 28 (Alpine stores + pages + utilities) |
| **Shared Base Templates** | 3 — `v2/base.html` (public), `base_modern.html` (internal), `cpa/base.html` (CPA portal) |
| **Responsive Design** | Yes — 6 breakpoints (320px → 1536px), mobile-first, prefers-reduced-motion |
| **Accessibility** | WCAG 2.1 AA color contrast, focus states, a11y Storybook addon |
| **Theme System** | Data-attribute based (`data-theme="public"`, `"cpa"`, `"admin"`) |

### Template Hierarchy

```
v2/base.html (Public pages — 4 children)
├── v2/dashboard.html
├── v2/guided_filing.html
├── v2/results.html
└── v2/lead_magnet/landing.html

base_modern.html (Internal — 15+ children)
├── dashboard.html
├── guided_filing.html
├── admin_dashboard.html (51KB SPA)
├── admin_api_keys.html
├── admin_impersonation.html
├── settings/notifications.html
├── tasks/{list,kanban,detail}.html
├── documents/{library,viewer}.html
├── support/{tickets,detail,create}.html
├── appointments/{booking,calendar,settings}.html
└── deadlines/{calendar,list}.html

cpa/base.html (CPA portal — 17 children)
├── cpa/dashboard.html
├── cpa/leads_list.html (25KB)
├── cpa/lead_detail.html (29KB)
├── cpa/return_queue.html
├── cpa/return_review.html (22KB)
├── cpa/analytics.html
├── cpa/branding.html (21KB)
├── cpa/profile.html (15KB)
├── cpa/onboarding.html
├── cpa/clients.html
├── cpa/team.html
├── cpa/billing.html
├── cpa/settings.html
├── cpa/tasks.html
├── cpa/appointments.html
└── cpa/deadlines.html

Standalone (no parent):
├── auth/login.html (30KB)
├── auth/signup.html (32KB)
├── auth/forgot_password.html (12KB)
├── auth/reset-password.html (32KB)
├── auth/client_login.html (5KB)
├── intelligent_advisor.html (large, self-contained)
├── smart_tax.html (large, self-contained)
└── lead_magnet/*.html (8 templates)
```

### Component Library (19 reusable Jinja2 macros)

| Category | Components |
|----------|-----------|
| Feedback | `alert.html`, `empty_state.html`, `loading.html`, `toast.html` |
| Forms | `checkbox.html`, `form_group.html`, `input.html`, `select.html` |
| Data | `table.html` |
| Layout | `card.html`, `modal.html`, `navigation.html` |
| Buttons | `button.html` |
| Internal | `action_bar.html`, `metric_grid.html`, `nav_sidebar.html`, `portal_base.html`, `portal_header.html`, `workflow_selector.html` |

---

## 2. ADMIN PANEL

### Route Files
- `src/web/admin_endpoints.py` (527 lines) — System health, cache, metrics, logs
- `src/web/admin_tenant_api.py` (707 lines) — Tenant CRUD, branding, features, domains
- `src/web/admin_user_management_api.py` (649 lines) — User CRUD, roles, permissions
- `src/web/routers/admin_impersonation_api.py` (340+ lines) — User impersonation
- `src/web/routers/admin_api_keys_api.py` (330+ lines) — API key management
- `src/web/routers/admin_compliance_api.py` (350+ lines) — Compliance audits
- `src/web/routers/admin_refunds_api.py` (350+ lines) — Refund processing
- `src/admin_panel/api/` — 13 additional route modules (dashboard, team, billing, settings, RBAC, superadmin, etc.)

### Templates: 3 files

| Page/Feature | Status | File Path | Connected API | Notes |
|---|---|---|---|---|
| Admin Dashboard (SPA) | ✅ Complete | `templates/admin_dashboard.html` (51KB) | `/api/admin/*`, `/api/v1/admin/*` | Full SPA with client-side routing — Dashboard, Firms, Users, Subscriptions, Compliance, Feature Flags, RBAC, System Health |
| API Key Management | ✅ Complete | `templates/admin_api_keys.html` (754 lines) | `/api/admin/api-keys/*` | Create, list, revoke, usage stats |
| User Impersonation | ✅ Complete | `templates/admin_impersonation.html` (1027 lines) | `/api/admin/impersonation/*` | Start/end sessions, audit history |
| Tenant CRUD | ✅ API-only | No dedicated template — in SPA | `/api/admin/tenants/*` | Create, list, update, delete tenants via SPA Firms tab |
| User Management | ✅ API-only | No dedicated template — in SPA | `/api/admin/users/*` | Role changes, status, permissions via SPA Users tab |
| Feature Flag Toggles | ✅ API-only | No dedicated template — in SPA | `/api/admin/tenants/{id}/features` | Per-tenant toggles via SPA Feature Flags tab |
| Platform Metrics | ✅ In SPA | Dashboard tab in SPA | `/api/admin/metrics/*` | CPU, memory, disk, error rates |
| Subscription Management | ✅ In SPA | Subscriptions tab in SPA | `/api/v1/admin/billing/*` | MRR, churn, tier distribution |
| Compliance Audits | ✅ API + SPA | SPA tab + API | `/api/admin/compliance/*` | Trigger audits, view reports |
| Refund Processing | ✅ API-only | No template | `/api/admin/refunds/*` | Approve/reject refunds — **no UI** |
| Bulk Operations | ❌ Missing | — | — | No bulk user/tenant operations |
| Per-Tenant Feature Overrides | ⚠️ Partial | API exists, SPA shows platform-level only | `/api/admin/tenants/{id}/features` | SPA shows global flags, not per-tenant detail |

**Interactivity Level:** SPA with client-side JS routing (pushState), auto-refresh, modal dialogs, form validation, inline editing. No Alpine.js — uses vanilla JS patterns.

---

## 3. CPA DASHBOARD

### Route Files
- `src/web/cpa_dashboard_pages.py` — Main HTML page rendering (prefix: `/cpa`)
- `src/web/cpa_branding_api.py` — Branding API (prefix: `/api/cpa/branding`)
- `src/web/custom_domain_api.py` — Custom domain API (prefix: `/api/custom-domain`)
- `src/web/workspace_api.py` — Workspace/preparer management (prefix: `/api/workspace`)
- `src/cpa_panel/api/` — 20+ specialized API route files

### Templates: 17 files (all extend `cpa/base.html`)

| Page/Feature | Status | File Path | Connected API | Notes |
|---|---|---|---|---|
| CPA Dashboard | ✅ Complete | `templates/cpa/dashboard.html` | Lead service, pipeline API | Summary cards, recent leads, priority queue, quick actions, 30s auto-refresh |
| Leads List | ✅ Complete | `templates/cpa/leads_list.html` (25KB) | `/api/cpa/leads/*` | Filtering (state/temp/search), pagination, bulk actions |
| Lead Detail | ✅ Complete | `templates/cpa/lead_detail.html` (29KB) | `/api/cpa/leads/{id}/*` | Contact info, insights, engagement history |
| Return Queue | ✅ Complete | `templates/cpa/return_queue.html` (14KB) | `/api/returns/*` | Status filtering, queue management |
| Return Review | ⚠️ Partial | `templates/cpa/return_review.html` (22KB) | `/api/returns/{id}/*` | Structure complete, approve/note actions stubbed |
| Branding Customization | ✅ Complete | `templates/cpa/branding.html` (21KB) | `/api/cpa/branding/*` | Color picker, logo upload, messaging editor, live preview |
| CPA Profile | ⚠️ Stub | `templates/cpa/profile.html` (15KB) | — | Template exists, content minimal |
| Onboarding Wizard | ✅ Complete | `templates/cpa/onboarding.html` (10KB) | — | 3-step launch setup with progress |
| Analytics | ⚠️ Stub | `templates/cpa/analytics.html` (10KB) | — | Template exists, no API wiring |
| Client List | ⚠️ Stub | `templates/cpa/clients.html` | `/api/workspace/clients` | Template exists, content minimal |
| Team Management | ⚠️ Stub | `templates/cpa/team.html` | `/api/v1/admin/team/*` | Template exists, no integration |
| Billing | ⚠️ Stub | `templates/cpa/billing.html` | `/api/v1/admin/billing/*` | Template exists, no integration |
| Settings | ⚠️ Stub | `templates/cpa/settings.html` | — | Template exists, minimal |
| Tasks | ⚠️ Stub | `templates/cpa/tasks.html` | — | Template exists, no backend |
| Appointments | ⚠️ Stub | `templates/cpa/appointments.html` | — | Template exists, no backend |
| Deadlines | ⚠️ Stub | `templates/cpa/deadlines.html` | — | Template exists, no backend |
| Custom Domain | ✅ API-only | No dedicated template | `/api/custom-domain/*` | DNS verification API exists, no UI |
| Document Management | ❌ Missing | — | — | No per-client document UI |
| Lead Creation/Editing | ❌ Missing | — | — | Can view leads, cannot create/edit |

**Interactivity Level:** Alpine.js in base template, vanilla JS in page scripts. Dynamic branding (CPA colors from DB), auto-refresh on dashboard, drag-and-drop (branding logo upload).

**Sidebar Navigation:**
- Dashboard, Clients, Leads, Review Queue, Advisory Reports
- Settings: Profile, Branding, Team, Settings, Billing
- **Missing from nav:** Tasks, Appointments, Deadlines (templates exist but not linked)

---

## 4. END USER / TAXPAYER FLOW

### Route Files
- `src/web/unified_filing_api.py` — Unified filing endpoints (5 routes)
- `src/web/guided_filing_api.py` — Step-by-step wizard (6 routes)
- `src/web/express_lane_api.py` — Quick filing (4 routes)
- `src/web/intelligent_advisor_api.py` — AI advisor with citations/audit
- `src/web/ai_chat_api.py` — Chat with AI agent (4+ routes)
- `src/web/smart_tax_api.py` — Document-first workflow (8+ routes)
- `src/web/scenario_api.py` — What-if scenarios (3+ routes)
- `src/web/capital_gains_api.py`, `k1_basis_api.py`, `rental_depreciation_api.py` — Specialized calculators
- `src/web/draft_forms_api.py` — Draft IRS form generation
- `src/web/filing_package_api.py` — Export (JSON/XML/PDF)
- `src/web/lead_magnet_pages.py` — Lead generation funnel

### Templates: 12+ files

| Page/Feature | Status | File Path | Connected API | Notes |
|---|---|---|---|---|
| Landing Page | ✅ Complete | `templates/landing.html` | — | Public marketing page |
| Lead Magnet Landing | ✅ Complete | `templates/lead_magnet/landing.html` | `/lead-magnet/*` | CPA-branded, A/B variants, deadline urgency |
| Quick Estimate | ✅ Complete | `templates/quick_estimate.html` | `/api/scenarios/*` | Manual income entry → instant estimate |
| Guided Filing Wizard | ✅ Complete | `templates/guided_filing.html` | `/api/filing/guided/*` | 7-step wizard: Personal → Filing Status → Income → Deductions → Credits → Review → Complete |
| Smart Tax (Document-First) | ✅ Complete | `templates/smart_tax.html` | `/api/smart-tax/*` | 5 screens: Upload → Detect → Confirm → Report → Act. OCR + AI recommendations |
| AI Chat Advisor | ✅ Complete | `templates/intelligent_advisor.html` | `/api/advisor/*`, `/api/ai-chat/*` | Chat interface, document upload, confidence meter, Circular 230 disclaimers, tax citations |
| Tax Results | ✅ Complete | `templates/results.html` | `/api/filing/*` | Refund/owed display, summary metrics, PDF download, JSON export, next steps |
| User Dashboard | ✅ Complete | `templates/dashboard.html` | `/api/sessions/*` | Session list, resume filing, status tracking |
| Document Library | ⚠️ Exists | `templates/documents/library.html` | — | Template exists, **not wired to route** |
| Document Viewer | ⚠️ Exists | `templates/documents/viewer.html` | — | Template exists, **not wired to route** |
| Notification Settings | ⚠️ Exists | `templates/settings/notifications.html` | — | Template exists, **not wired to route** |
| Support Tickets | ⚠️ Exists | `templates/support/{tickets,detail,create}.html` | — | Templates exist, **not wired to routes** |
| Scenario Comparison UI | ❌ Missing | — | `/api/scenarios/*` | API exists (filing-status, deductions, credits), **no dedicated template** |
| Computation Worksheet View | ❌ Missing | — | `/api/sessions/{id}/computation` | API returns worksheet data, **no UI to display it** |
| Capital Gains UI | ❌ Missing | — | `/api/v1/capital-gains/*` | Full Form 8949 API, **no template** |
| K-1 Basis Tracker UI | ❌ Missing | — | `/api/v1/k1-basis/*` | Full IRC 705/704d API, **no template** |
| Rental Depreciation UI | ❌ Missing | — | `/api/v1/rental-depreciation/*` | MACRS API, **no template** |
| Draft Forms Viewer | ❌ Missing | — | `/api/v1/draft-forms/*` | IRS-style form generation API, **no template** |
| Filing Package Export UI | ❌ Missing | — | `/api/filing-package/*` | JSON/XML/PDF export API, **no template** |

**Interactivity Level:** High. Alpine.js state management, inline form validation, currency/SSN formatting, drag-and-drop file upload, progress bars, auto-save, AJAX calls, screen transitions with fade animations.

**Filing Paths (6 distinct):**
1. **Express Lane** — Upload documents → auto-extraction → instant results (~3 min)
2. **Smart Tax** — Upload → OCR detect → confirm data → AI report → choose path (~5-10 min)
3. **Guided Filing** — 7-step manual wizard → review → submit (~10-15 min)
4. **AI Chat Advisor** — Conversational tax collection with real-time calculations
5. **Quick Estimate** — Manual entry → instant estimate (lead magnet)
6. **Scenario Comparison** — What-if analysis (API only, no dedicated UI)

---

## 5. SHARED / AUTH

### Route Files
- `src/core/api/auth_routes.py` (570 lines) — Login, register, refresh, logout, password reset, OAuth
- `src/web/mfa_api.py` (910 lines) — TOTP setup, verify, disable, backup codes
- `src/web/sessions_api.py` (657 lines) — Session management, resume, anonymous transfer
- `src/web/feature_access_api.py` (266 lines) — Feature flag checks
- `src/web/routers/pages.py` (270+ lines) — Page routing and redirects

### Templates: 5 auth + shared components

| Page/Feature | Status | File Path | Connected API | Notes |
|---|---|---|---|---|
| Login Page | ✅ Complete | `templates/auth/login.html` (30KB) | `/api/core/auth/login` | Email/password, remember me, OAuth (Google/Microsoft), estimate banner, loading states |
| Registration | ✅ Complete | `templates/auth/signup.html` (32KB) | `/api/core/auth/register` | Name, email, password strength meter, terms checkbox, OAuth |
| Forgot Password | ✅ Complete | `templates/auth/forgot_password.html` (12KB) | `/api/core/auth/forgot-password` | Email form, success/error feedback, rate limiting |
| Reset Password | ✅ Complete | `templates/auth/reset-password.html` (32KB) | `/api/core/auth/reset-password` | Token-based reset, new password entry |
| Client Login | ⚠️ Partial | `templates/auth/client_login.html` (5KB) | `/api/cpa/client/login` | Template exists, **backend endpoint not confirmed** |
| MFA Setup UI | ❌ Missing | — | `/api/mfa/setup`, `/api/mfa/verify-setup` | Full TOTP API (QR code generation, backup codes), **no template** |
| MFA Verify During Login | ❌ Missing | — | `/api/mfa/validate` | API validates TOTP codes, **no login flow integration** |
| Profile/Settings Page | ❌ Missing | — | `/api/core/auth/me` | No user profile editing template |
| Notification Center | ❌ Missing | — | — | No notification inbox template |
| Error 404 Page | ❌ Missing | Inline HTML in app.py | — | No dedicated template |
| Error 403 Page | ❌ Missing | Inline HTML in app.py | — | No dedicated template |
| Error 500 Page | ❌ Missing | Inline HTML in app.py | — | No dedicated template |

**Post-Login Redirect:** No server-side role-based redirect. Defaults to `/advisor` for all roles. Role enforcement happens via:
- API-level: `@require_auth(roles=[...])` decorators
- Template-level: Jinja2 conditionals check user context
- Navigation-level: Different sidebar menus per role

**Feature Gating:** Full implementation via `/api/features/*` endpoints + `feature_access_control.py`. Features gated by subscription tier + user role + tenant flags. JS checks `features[code].allowed` to show/hide UI elements.

---

## 6. CROSS-ROLE NAVIGATION MAP

### Portal Entry Points

```
┌──────────────────────────────────────────────────────┐
│                    LOGIN (/auth/login)                │
│                                                       │
│     [All roles redirect to /advisor by default]       │
│                                                       │
│  Manual navigation required to reach role-specific:   │
│                                                       │
│  Admin → /admin          (admin_dashboard.html SPA)   │
│  CPA   → /cpa            (cpa/dashboard.html)         │
│  User  → /advisor or      (intelligent_advisor.html)   │
│          /filing/guided   (guided_filing.html)         │
└──────────────────────────────────────────────────────┘
```

### Cross-Role Link Paths

| From → To | Link Exists? | Mechanism | URL Pattern |
|-----------|-------------|-----------|-------------|
| Admin → CPA Workspace | ⚠️ Indirect | Impersonation only | `/api/admin/impersonation/` then navigate |
| Admin → Tenant Detail | ✅ Yes | SPA Firms tab | `/admin#firms/{tenant_id}` (client-side) |
| Admin → User Detail | ✅ Yes | SPA Users tab | `/admin#users/{user_id}` (client-side) |
| CPA → Client Session | ✅ Yes | Lead detail page | `/cpa/leads/{lead_id}` → session link |
| CPA → Return Review | ✅ Yes | Queue → review | `/cpa/returns/{id}/review` |
| CPA → Own Branding | ✅ Yes | Settings sidebar | `/cpa/branding` |
| User → Filing Wizard | ✅ Yes | Dashboard/advisor | `/filing/guided` or `/smart-tax` |
| User → Results | ✅ Yes | After calculation | `/results?session={id}` |
| User → PDF Download | ✅ Yes | Results page button | `/api/tax-returns/{id}/pdf` |
| Any Role → Back to Home | ⚠️ Inconsistent | Logo click in some templates | Some pages have no back link |

### Navigation Gaps

| Gap | Impact | Description |
|-----|--------|-------------|
| No role-based redirect after login | Medium | All users land on `/advisor` regardless of role |
| No breadcrumbs | Low | Deep pages lack breadcrumb trail |
| Admin can't view CPA data without impersonation | By Design | Security boundary, but adds friction |
| CPA stub pages are dead-ends | Medium | 9 CPA pages (team, billing, tasks, etc.) exist but have no working content |
| No cross-portal navigation | Medium | No link from admin → CPA portal or CPA → end-user view |

---

## 7. CRITICAL GAPS (Ranked by Impact)

### Severity: CRITICAL (Will break or mislead users)

| # | Gap | Impact | Location |
|---|-----|--------|----------|
| 1 | **5 template path mismatches** — Routes reference `legal/terms.html` but file is `terms.html`, `cpa/settings_payments.html` vs `cpa_payment_settings.html`, etc. | **500 errors** on legal pages and CPA settings | `src/web/routers/pages.py` |
| 2 | **No MFA UI** — Full TOTP backend (setup, verify, backup codes, QR generation) but zero frontend templates | MFA is **unusable** despite being fully implemented server-side | `src/web/mfa_api.py` — 910 lines with no UI |
| 3 | **7 duplicate route definitions** — Same paths defined in both `routers/pages.py` and `app.py` | Unpredictable behavior depending on registration order | `/terms`, `/privacy`, `/cookies`, `/disclaimer`, `/cpa/settings/*` |

### Severity: HIGH (Major feature gaps)

| # | Gap | Impact | Location |
|---|-----|--------|----------|
| 4 | **No error page templates** (404, 403, 500) | Users see raw HTML or blank pages on errors | `app.py` exception handlers use inline HTML |
| 5 | **No scenario comparison UI** | API with 3 endpoints (filing-status, deductions, credits) has no frontend | `src/web/scenario_api.py` |
| 6 | **No role-based post-login redirect** | Admin/CPA/User all land on `/advisor` | `templates/auth/login.html` JS |
| 7 | **9 CPA stub pages** | Sidebar links to Team, Billing, Analytics, Tasks, Appointments, Deadlines, Profile, Settings, Clients — all empty shells | `templates/cpa/*.html` |
| 8 | **No user profile/settings page** | Users cannot edit their profile or account settings | No template exists |

### Severity: MEDIUM (Functionality exists but is disconnected)

| # | Gap | Impact | Location |
|---|-----|--------|----------|
| 9 | **5 specialized calculator APIs have no UI** | Capital Gains (8949), K-1 Basis, Rental Depreciation, Draft Forms, Filing Package — all backend-only | `src/web/*_api.py` |
| 10 | **6 orphaned feature templates** (documents, support, tasks, appointments, deadlines, notifications) | Templates extend `base_modern.html` but aren't served by any route | `templates/{documents,support,tasks,appointments,deadlines,settings}/` |
| 11 | **Client login portal incomplete** | Template calls `/api/cpa/client/login` which may not exist | `templates/auth/client_login.html` |
| 12 | **Refund processing has no UI** | Full approve/reject API, no admin template | `src/web/routers/admin_refunds_api.py` |
| 13 | **Custom domain setup has no CPA UI** | DNS verification API is complete, no CPA-facing template | `src/web/custom_domain_api.py` |

---

## 8. TECH DEBT

### Orphaned Templates (Exist but not served by any route)

**Feature templates — should be wired:**
- `templates/admin_impersonation.html` — Route exists but linking unclear
- `templates/documents/library.html` — Document management
- `templates/documents/viewer.html` — Document viewing
- `templates/settings/notifications.html` — Notification preferences
- `templates/support/tickets.html` — Support ticket list
- `templates/support/detail.html` — Ticket detail
- `templates/support/create.html` — Create ticket
- `templates/tasks/list.html` — Task list
- `templates/tasks/kanban.html` — Kanban board
- `templates/tasks/detail.html` — Task detail
- `templates/appointments/booking.html` — Booking form
- `templates/appointments/calendar.html` — Calendar view
- `templates/appointments/settings.html` — Appointment settings
- `templates/deadlines/calendar.html` — Deadlines calendar
- `templates/deadlines/list.html` — Deadlines list
- `templates/advisory_report_widget.html` — Advisory widget
- `templates/v2/guided_filing.html` — V2 version of guided filing
- `templates/v2/results.html` — V2 version of results

**Component/partial templates (used via includes — NOT orphaned):**
- 23 component templates in `templates/components/`
- 3 partials (`sidebar.html`, `head_styles.html`, `foot_scripts.html`)
- 1 macro file (`macros/icons.html`)
- 3 base templates (`v2/base.html`, `base_modern.html`, `cpa/base.html`)

### Dead API Endpoints (No UI consumer)

| Endpoint | Module | Has UI? |
|----------|--------|---------|
| `/api/v1/capital-gains/*` (5+ routes) | `capital_gains_api.py` | ❌ No template |
| `/api/v1/k1-basis/*` (4+ routes) | `k1_basis_api.py` | ❌ No template |
| `/api/v1/rental-depreciation/*` (3+ routes) | `rental_depreciation_api.py` | ❌ No template |
| `/api/v1/draft-forms/*` (4+ routes) | `draft_forms_api.py` | ❌ No template |
| `/api/filing-package/*` (2+ routes) | `filing_package_api.py` | ❌ No template |
| `/api/scenarios/*` (3 routes) | `scenario_api.py` | ❌ No dedicated template |
| `/api/mfa/*` (7 routes) | `mfa_api.py` | ❌ No template |
| `/api/admin/refunds/*` (4+ routes) | `admin_refunds_api.py` | ❌ No template |
| `/api/admin/compliance/*` (3+ routes) | `admin_compliance_api.py` | ⚠️ Partial (in SPA tab) |

### Broken/Mismatched Links

| Route in Code | Expected Template | Actual File | Fix |
|---------------|-------------------|-------------|-----|
| `/terms` | `legal/terms.html` | `terms.html` | Change to `terms.html` |
| `/privacy` | `legal/privacy.html` | `privacy.html` | Change to `privacy.html` |
| `/cookies` | `legal/cookies.html` | `cookies.html` | Change to `cookies.html` |
| `/disclaimer` | `legal/disclaimer.html` | `disclaimer.html` | Change to `disclaimer.html` |
| `/cpa/settings/payments` | `cpa/settings_payments.html` | `cpa_payment_settings.html` | Fix template name |
| `/cpa/settings/branding` | `cpa/settings_branding.html` | `cpa_branding_settings.html` | Fix template name |
| `/smart-tax-legacy` | `smart_tax_app.html` | `smart_tax.html` | Fix template name |
| CPA nav → `/cpa/assignments` | No route handler | — | Add route or remove link |
| CPA nav → `/cpa/converted` | No route handler | — | Add route or remove link |

### Missing Error Pages

| Page | Status | Current Behavior |
|------|--------|-----------------|
| 404 Not Found | ❌ No template | Inline HTML in exception handler |
| 403 Forbidden | ❌ No template | Inline HTML in exception handler |
| 500 Server Error | ❌ No template | Inline HTML with minimal styling |

### Duplicate Route Registrations

| Path | Defined In | Defined In |
|------|-----------|-----------|
| `/terms` | `routers/pages.py` line 114 | `app.py` line 1649 |
| `/privacy` | `routers/pages.py` line 121 | `app.py` line 1663 |
| `/cookies` | `routers/pages.py` line 128 | `app.py` line 1674 |
| `/disclaimer` | `routers/pages.py` line 135 | `app.py` line 1687 |
| `/cpa/settings/payments` | `routers/pages.py` line 72 | `app.py` line 1579 |
| `/cpa/settings/branding` | `routers/pages.py` line 81 | `app.py` line 1593 |
| `/cpa-landing` | `routers/pages.py` line 90 | `app.py` line 1635 |

---

## 9. RECOMMENDED BUILD ORDER

Based on impact, dependency chains, and effort:

### Phase 1: Fix Breaking Issues (Immediate)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 1.1 | Fix 7 template path mismatches in `routers/pages.py` | Small | Eliminates 500 errors |
| 1.2 | Remove 7 duplicate route registrations (keep router versions, delete from app.py) | Small | Eliminates unpredictable behavior |
| 1.3 | Create dedicated error page templates (404, 403, 500) extending `base_modern.html` | Small | Professional error handling |

### Phase 2: Complete Auth Flow (High Impact)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 2.1 | Build MFA setup/verify UI (QR code display, code input, backup codes display) | Medium | Enables MFA — currently unusable |
| 2.2 | Integrate MFA into login flow (redirect to MFA page after password auth) | Medium | Completes 2FA security |
| 2.3 | Add role-based post-login redirect (Admin→`/admin`, CPA→`/cpa`, User→`/advisor`) | Small | Proper role UX |
| 2.4 | Build user profile/settings page | Medium | Users can manage their account |

### Phase 3: Wire Orphaned Templates

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 3.1 | Wire `documents/library.html` and `documents/viewer.html` to routes | Small | Document management for end users |
| 3.2 | Wire `support/tickets.html`, `support/detail.html`, `support/create.html` | Small | Support ticket system |
| 3.3 | Wire `settings/notifications.html` | Small | Notification preferences |
| 3.4 | Wire `tasks/*`, `appointments/*`, `deadlines/*` for CPA portal | Medium | CPA productivity tools |

### Phase 4: Build Missing Feature UIs

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 4.1 | Build Scenario Comparison UI (filing status, deductions, credits) | Medium | Key differentiator — helps users optimize |
| 4.2 | Complete 9 CPA stub pages (team, billing, analytics, etc.) | Large | Full CPA portal experience |
| 4.3 | Build Computation Worksheet viewer | Medium | IRS-style worksheet display |
| 4.4 | Build Capital Gains / K-1 / Rental Depreciation UIs | Large | Specialized tax form interfaces |
| 4.5 | Build Filing Package Export UI | Small | Download package for CPA import |

### Phase 5: Polish & Consistency

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 5.1 | Add breadcrumb navigation to all deep pages | Small | Navigation consistency |
| 5.2 | Build Admin refund processing UI | Medium | Complete admin feature set |
| 5.3 | Build Custom Domain setup UI for CPA portal | Medium | Self-service domain config |
| 5.4 | Build client login portal backend | Medium | CPA client self-service |
| 5.5 | Consolidate v1 and v2 template variants | Medium | Reduce maintenance burden |

---

## Appendix: API-to-UI Coverage Matrix

| API Module | Endpoints | Has Template? | Has JS Consumer? | Coverage |
|-----------|-----------|--------------|-------------------|----------|
| `unified_filing_api.py` | 5 | ✅ (multiple) | ✅ | Full |
| `guided_filing_api.py` | 6 | ✅ `guided_filing.html` | ✅ | Full |
| `express_lane_api.py` | 4 | ✅ `smart_tax.html` | ✅ | Full |
| `intelligent_advisor_api.py` | 3+ | ✅ `intelligent_advisor.html` | ✅ | Full |
| `ai_chat_api.py` | 4+ | ✅ (shared with advisor) | ✅ | Full |
| `smart_tax_api.py` | 8+ | ✅ `smart_tax.html` | ✅ | Full |
| `lead_magnet_pages.py` | 8+ | ✅ `lead_magnet/*.html` | ✅ | Full |
| `admin_endpoints.py` | 12 | ✅ `admin_dashboard.html` SPA | ✅ | Full |
| `admin_tenant_api.py` | 12 | ✅ SPA tab | ✅ | Full |
| `admin_user_management_api.py` | 8 | ✅ SPA tab | ✅ | Full |
| `cpa_dashboard_pages.py` | 17 | ✅ `cpa/*.html` | ✅ | Partial (9 stubs) |
| `cpa_branding_api.py` | 5+ | ✅ `cpa/branding.html` | ✅ | Full |
| `sessions_api.py` | 10 | ✅ `dashboard.html` | ✅ | Full |
| `auth_routes.py` | 11 | ✅ `auth/*.html` | ✅ | Full |
| `scenario_api.py` | 3 | ❌ | ❌ | **None** |
| `mfa_api.py` | 7 | ❌ | ❌ | **None** |
| `capital_gains_api.py` | 5+ | ❌ | ❌ | **None** |
| `k1_basis_api.py` | 4+ | ❌ | ❌ | **None** |
| `rental_depreciation_api.py` | 3+ | ❌ | ❌ | **None** |
| `draft_forms_api.py` | 4+ | ❌ | ❌ | **None** |
| `filing_package_api.py` | 2+ | ❌ | ❌ | **None** |
| `admin_refunds_api.py` | 4+ | ❌ | ❌ | **None** |
| `custom_domain_api.py` | 3+ | ❌ | ❌ | **None** |
| `admin_impersonation_api.py` | 4 | ⚠️ Template exists | ⚠️ | Disconnected |
| `admin_api_keys_api.py` | 5 | ✅ `admin_api_keys.html` | ✅ | Full |
| `admin_compliance_api.py` | 3+ | ⚠️ SPA partial | ⚠️ | Partial |
| `workspace_api.py` | 5+ | ⚠️ Partial via CPA | ⚠️ | Partial |
| `feature_access_api.py` | 6 | ✅ (JS feature gating) | ✅ | Full |

**Summary:** 15 API modules have full UI coverage, 4 have partial, and **8 have zero UI** (38 API endpoints with no frontend).

---

*Analysis performed on 97 templates, 25+ route files, 42 static assets, 663 Python source files.*
*No files were created, modified, or deleted during this audit.*
