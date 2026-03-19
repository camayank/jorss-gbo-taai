# Jorss-GBO Tax Platform — Reverse PRD

> Exhaustive audit of what is built, what works, what's partial, and what's missing.
> Generated 2026-03-19 from full codebase analysis.

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [What is Perfectly Working](#2-what-is-perfectly-working)
3. [What is Partially Working](#3-what-is-partially-working)
4. [What is Stub / Non-Functional](#4-what-is-stub--non-functional)
5. [What is Missing Entirely](#5-what-is-missing-entirely)
6. [Critical Bugs That Block Go-Live](#6-critical-bugs-that-block-go-live)
7. [Architecture Observations](#7-architecture-observations)
8. [Feature-by-Feature Status Matrix](#8-feature-by-feature-status-matrix)

---

## 1. Product Overview

**Jorss-GBO** is a multi-tenant B2B SaaS tax preparation platform where:
- **CPAs** use a white-label lead magnet funnel to capture taxpayer prospects, manage them through a 5-stage pipeline, and convert them to paying clients
- **Taxpayers** interact with an AI-powered tax advisor that extracts data from conversation and documents, computes federal + state taxes, and generates advisory reports
- **Platform admins** manage firms, subscriptions, feature flags, and compliance

**Tech stack:** FastAPI, PostgreSQL, Redis, SQLAlchemy, Jinja2, Alpine.js, Celery, OpenAI/Anthropic

**Database:** 69 PostgreSQL tables, 19 Alembic migrations, separate SQLite stores for admin ops and lead persistence

**Tests:** 6,937 test functions across 286 files

---

## 2. What is Perfectly Working

### 2.1 Federal Tax Calculation Engine
| Component | File | Details |
|-----------|------|---------|
| Progressive bracket calculation | `src/calculator/engine.py` | 7-bracket 2025 rates, all 5 filing statuses |
| Self-employment tax | `src/calculator/engine.py` | 92.35% net earnings, SS wage base $176,100 minus W-2 wages, Medicare uncapped |
| Additional Medicare Tax | `src/calculator/engine.py` | 0.9% over threshold ($200k single / $250k MFJ) |
| NIIT | `src/calculator/engine.py` | 3.8% on lesser of NII or MAGI over threshold |
| AMT (Form 6251) | `src/models/form_6251.py` | Full Part I-III: SALT addback, ISO spread, PAB interest, depreciation adj, phased exemption, 26%/28% two-rate TMT |
| QBI / Section 199A | `src/calculator/qbi_calculator.py` | Per-business breakdown, W-2 wage limitation (50% or 25%+2.5% UBIA), SSTB phase-out |
| Passive Activity Loss (Form 8582) | `src/models/form_8582.py` | 7 material participation tests, $25k rental allowance, phaseout $100k-$150k AGI |
| Capital gains (Schedule D) | `src/models/schedule_d.py` | 0%/15%/20% with income stacking, unrecaptured §1250, collectibles, §1202 QSBS |
| Business property sales (Form 4797) | `src/models/form_4797.py` | §1231/§1245/§1250/§1252/§1254 recapture |
| HSA (Form 8889) | `src/models/form_8889.py` | Contribution limits, catch-up, qualified distributions |
| IRA basis (Form 8606) | `src/models/form_8606.py` | Pro-rata rule, Roth conversion, early withdrawal |
| FEIE (Form 2555) | `src/models/form_2555.py` | Bona fide / physical presence, 2025 exclusion |
| Kiddie Tax (Form 8615) | `src/models/form_8615.py` | Net unearned income, parent's rate |
| Foreign Tax Credit (Form 1116) | `src/models/form_1116.py` | Per-basket limitation, carryforward/carryback |
| Installment Sales (Form 6252) | `src/models/form_6252.py` | Gross profit ratio, §453A interest |
| Like-Kind Exchange (Form 8824) | `src/models/form_8824.py` | Realized/recognized gain, boot, basis |
| COD Exclusion (Form 982) | `src/models/form_982.py` | Insolvency, bankruptcy, qualified property |
| Estimated tax penalty (Form 2210) | `src/calculator/engine.py` | Safe harbor: 90% current / 100%/110% prior year |
| Decimal arithmetic | `src/calculator/decimal_math.py` | IRS-compliant ROUND_HALF_UP, deterministic |
| 2025 tax year constants | `src/calculator/tax_year_config.py` | All brackets, thresholds, limits per Rev. Proc. 2024-40 |
| Itemized deductions (Schedule A) | `src/models/schedule_a.py` | Medical 7.5% floor, $10k SALT cap, mortgage $750k/$1M grandfathered |
| Business income (Schedule C) | `src/models/schedule_c.py` | All expense lines, vehicle, home office, Section 179 |
| Social Security taxation | `src/calculator/engine.py` | IRS Pub. 915 tier formula |

**Test coverage:** 800+ calculator-specific tests including property-based invariants and determinism checks.

### 2.2 State Tax Calculators
41 states + DC with real bracket tables. 9 no-income-tax states correctly handled.

| State | Key Features |
|-------|-------------|
| CA | 9 brackets (1%-12.3%), 1% mental health surtax >$1M, CalEITC 45%, HSA addback, renter's credit |
| NY | 9 brackets (4%-10.9%), NYC local tax brackets, NY EITC 30%, Empire State Child Credit $330 |
| IL | Flat 4.95%, retirement exclusion, IL EITC 20%, 5% property tax credit |
| PA | Flat 3.07%, starts from gross income |
| OR | 4 brackets (4.75%-9.9%), federal tax deduction up to $7,500, OR EITC 12% |
| All others | Correct bracket tables, SS exemption flags, pension exclusions, EITC percentages |

### 2.3 AI / Intelligent Tax Advisor
| Component | File | Details |
|-----------|------|---------|
| IntelligentTaxAgent | `src/agent/intelligent_tax_agent.py` | 1,993 lines. OpenAI function calling, 47-field entity extraction, per-field confidence scoring, contradiction detection, real-time running estimate via FederalTaxEngine, audit trail, SSTB classification, tax opportunity detection |
| Smart Tax orchestrator | `src/smart_tax/orchestrator.py` | Session → document → questions → report flow, UnifiedFilingSession DB persistence |
| Document processor | `src/smart_tax/document_processor.py` | Per-field confidence, 9 document types, cross-document validation |
| Deduction detector | `src/smart_tax/deduction_detector.py` | 8 deduction types, 5 credit types, standard vs. itemized comparison |
| Planning insights | `src/smart_tax/planning_insights.py` | Retirement maximization, income timing, withholding adequacy, quarterly estimates |
| Complexity router | `src/smart_tax/complexity_router.py` | 15 complexity factors, auto CPA recommendation >$500k or foreign income |
| Adaptive questions | `src/smart_tax/question_generator.py` | 20 templates, skips when documents present, AI-informed prioritization |
| Advisory report generator | `src/advisory/report_generator.py` | 7-section report, concurrent generation, Circular 230 disclaimer |
| AI narrative generator | `src/advisory/ai_narrative_generator.py` | Claude-preferred, tone personalization, SHA-256 cached, static fallback |
| PII scrubber | `src/advisory/pii_scrubber.py` | Three-pass: direct identifiers, name replacement, financial rounding |
| Recommendation engine | `src/recommendation/recommendation_engine.py` | 1,006 lines. 4 sub-analyzers, IRS references, what-if scenarios |
| Real-time estimator | `src/recommendation/realtime_estimator.py` | 656 lines. Instant W-2 estimate, multi-document aggregation, confidence bands |
| Recommendation validator | `src/recommendation/validation.py` | Field validation, value ranges, IRS reference regex |
| ML ensemble classifier | `src/ml/classifiers/ensemble_classifier.py` | 3-tier cascade: OpenAI → TF-IDF → Regex, weighted voting |
| Document parser (OCR) | `src/parser/document_parser.py` | Tesseract + pdfplumber, W-2/1099 field extraction |

### 2.4 Lead Magnet Funnel (End-to-End)
| Step | Route | Template | Backend |
|------|-------|----------|---------|
| Landing | `GET /lead-magnet?cpa=<slug>` | `lead_magnet/landing.html` | CPA branding, A/B variant (5 variants), OG share card SVG |
| Quick estimate | `GET /lead-magnet/estimate` | `quick_estimate.html` | 4-question complexity form |
| Savings teaser | `GET /lead-magnet/teaser` | `savings_teaser.html` | Pre-gate savings range |
| Contact capture | `GET /lead-magnet/contact` | `contact_capture.html` | Lead creation, PII encrypted at rest, rate limited 5/hr |
| Tier 1 report | `GET /lead-magnet/report` | `tier1_report.html` | Free teaser insights |
| Engagement letter | `GET /lead-magnet/engagement-letter` | `engagement_letter.html` | Legal acknowledgment tracked |
| Tier 2 analysis | `GET /lead-magnet/analysis` | `tier2_analysis.html` / `tier2_locked.html` | Gated by engagement letter |

### 2.5 Lead State Machine
5-state forward-only machine: `BROWSING` → `CURIOUS` → `EVALUATING` → `ADVISORY_READY` → `HIGH_LEVERAGE`. Signal-driven transitions. SQLite persistence with PII encryption. Tenant-isolated.

### 2.6 CPA Dashboard
| Page | Route | Status |
|------|-------|--------|
| Dashboard home | `GET /cpa/dashboard` | Working — pipeline stats, activity feed, lead counts |
| Leads list | `GET /cpa/leads` | Working — filtered by state, searchable |
| Pipeline kanban | `GET /cpa/leads/pipeline` | Working — drag-and-drop state transitions |
| Lead detail | `GET /cpa/leads/{id}` | Working — session + report + anomaly detection |
| Analytics | `GET /cpa/analytics` | Working — conversion metrics, velocity, trends, AI narrative |
| Onboarding wizard | `GET /cpa/onboarding` | Working — profile setup |
| Profile | `GET /cpa/profile` | Working |
| Branding | `GET /cpa/branding` | Working — CRUD API with file uploads |
| Settings | `GET /cpa/settings` | Working |
| Team | `GET /cpa/team` | Working — invite + list |
| Clients | `GET /cpa/clients` | Working — lists converted leads |
| Converted | `GET /cpa/converted` | Working |

### 2.7 Authentication & Security
| Component | Status | Details |
|-----------|--------|---------|
| JWT login (email/password) | Working | CoreAuthService → UserAuthRepository → bcrypt verify → JWT token pair |
| Registration | Working | Rejects platform admin self-registration |
| Forgot/reset password | Working | Redis-backed token (15 min TTL), bcrypt rehash |
| Token refresh | Working | Redis-backed refresh tokens |
| Token revocation | Working | JTI added to Redis `revoked_jtis` set, checked by RBACMiddleware |
| RBAC v2 | Working | 8 roles, 40+ permissions, tier-gated features |
| CSRF protection | Working | Cookie + header validation, 24 documented exemptions |
| Security headers | Working | HSTS, CSP with nonce, X-Frame-Options |
| Rate limiting | Working | 60 req/min/IP, 2x for authenticated, token bucket |
| Tenant isolation | Working | Middleware-enforced, strict in production |
| Session ownership tokens | Working | HMAC-based, constant-time comparison |
| API key auth | Partial | SHA-256 hashed, but `api_partner` role not in RBAC enum |
| Audit logging | Working | Hash-chained entries, PII access tracking, session integrity |

### 2.8 Infrastructure
| Component | File | Status |
|-----------|------|--------|
| Circuit breaker | `src/resilience/circuit_breaker.py` | Working — 3-state, async/sync, registry singleton |
| Retry with backoff | `src/resilience/retry.py` | Working — exponential + jitter, non-retryable exclusion |
| Redis cache | `src/cache/redis_client.py` | Working — async, connection pool, graceful degradation |
| Calculation cache | `src/cache/calculation_cache.py` | Working — SHA-256 versioned keys, `@cached_calculation` decorator |
| Celery tasks | `src/tasks/celery_app.py` | Working — 4 task modules, beat schedule, dead letter queue |
| WebSocket real-time | `src/realtime/` | Working — JWT auth, user/firm/session broadcast, heartbeat |
| Email notifications | `src/notifications/` | Working — SendGrid, SES, SMTP providers, 30+ trigger types |
| Webhook delivery | `src/webhooks/service.py` | Working — HMAC-SHA256 signatures, exponential retry, 1MB cap |
| Admin impersonation | `src/web/routers/admin_impersonation_api.py` | Working — Redis-backed, super admin protection |
| Admin API keys | `src/web/routers/admin_api_keys_api.py` | Working — SHA-256 hashed, rotation, 9 scopes |
| Configuration validation | `src/config/settings.py` | Working — Pydantic BaseSettings, production security enforcement |

### 2.9 Database
- **69 PostgreSQL tables** via 19 Alembic migrations
- All ORM models have matching database tables
- PII encrypted at rest (AES-256 Fernet)
- SSN hashed (HMAC-SHA256)
- Audit trail with hash-chaining for tamper detection

---

## 3. What is Partially Working

### 3.1 Scenarios Page — BROKEN API CONTRACT
The `/scenarios` UI is polished but **cannot function**:
- `GET /api/scenarios` requires `return_id` query param — JS sends none → HTTP 422
- `POST /api/scenarios` expects `{return_id, name, scenario_type, modifications[]}` — JS sends `{name, description, filing_status, adjustments[]}` → 422
- Quick analysis cards POST empty bodies to endpoints requiring `return_id`
- **Fix:** Make `return_id` optional with session-cookie fallback, or wire frontend to pass session's return ID

### 3.2 API Calculation Layer vs Engine Gap
`POST /api/calculate/complete` uses a simplified path — NOT the full `FederalTaxEngine`. AMT, QBI, SE tax, NIIT, PAL, EITC phase-in, and all specialty forms are bypassed in the REST API. The full engine runs only internally (agent, test suite, services).

### 3.3 MFA System
- Templates, routes, API, TOTP logic all exist and work
- **Critical bug:** `complete_mfa_login()` in `CoreAuthService` looks up users only in `_users_db` dict, not the database, even when `AUTH_USE_DATABASE=true`. MFA-enabled users in the real database will fail post-MFA token issuance.

### 3.4 Billing / Stripe
- Database schema exists (subscription_plans, subscriptions, invoices with Stripe ID columns)
- Manual payment recording works
- **No Stripe SDK calls exist anywhere** — all billing is pure DB operations
- CPA Stripe Connect OAuth scaffolding exists but Connect flow not wired
- Two conflicting pricing tables: `platform_billing_config.py` ($99/$199/$499) vs `subscription.py` comments ($199/$499/$999)

### 3.5 BillingService Runtime Bugs
- `SubscriptionStatus.CANCELED` should be `.CANCELLED` (enum name mismatch)
- `SubscriptionPlan.tier` should be `.code` (column name mismatch)
- `InvoiceStatus.PENDING` doesn't exist (should be `.OPEN`)
- `subscription.trial_ends_at` should be `.trial_end`

### 3.6 FirmService Runtime Bugs
- `User(name=admin_name)` should be `User(first_name=..., last_name=...)`
- `firm.current_client_count` doesn't exist on the Firm model
- Settings column name mismatches (`branding_primary_color` vs actual column names)

### 3.7 Return Queue & Review
- Return queue loads sessions but `counts` dict (pending_review, in_review, etc.) is always zero — never populated from real data
- Return review falls back to hardcoded demo data on any exception

### 3.8 CPA Branding File Uploads
- Full CRUD API works
- Files write to local disk (`./uploads/`) — no S3/CDN. Lost on container restart without volume mount.

### 3.9 State Tax Gaps
- Most states' `calculate_state_additions()` return 0.0 (out-of-state muni interest, federal tax addback not modeled)
- PA local EIT: `has_local_tax=True` but no bracket table
- MD county tax: simplified (no county-level variation)
- NYC local tax: 4-bracket simplification of actual schedule

### 3.10 Three JWT Signing Paths
- **Path A** (`src/rbac/jwt.py`): reads `JWT_SECRET` — canonical
- **Path B** (`src/core/services/auth_service.py`): reads via `rbac.jwt.get_jwt_secret()` — compatible
- **Path C** (`src/security/authentication.py`): reads `JWT_SECRET_KEY` (DIFFERENT env var) — **incompatible tokens**
- Two token revocation namespaces: `revoked_token:{jti}` (Path C) vs `revoked_jtis` set (Path A) — **invisible to each other**

### 3.11 PDF Generation
`src/export/pdf_generator.py` produces ASCII text bytes, not actual PDF binary. Not suitable for IRS submission or real file download.

### 3.12 Duplicate Upload Endpoint
Both `routes/upload_routes.py` (legacy) and `routers/documents.py` (RBAC) register `POST /api/upload` with different response schemas.

---

## 4. What is Stub / Non-Functional

### 4.1 UI Pages with No Backend Wiring
These pages render polished templates but **zero `fetch()` calls** — the JS was never wired to their APIs:

| Page | Template | API Exists? | Issue |
|------|----------|-------------|-------|
| `/tasks` | `tasks/list.html` | Yes (`/api/tasks`) | Template never calls API |
| `/tasks/kanban` | `tasks/kanban.html` | Yes | Template never calls API |
| `/tasks/{id}` | `tasks/detail.html` | Yes | Template never calls API |
| `/appointments/calendar` | `appointments/calendar.html` | Yes (`/api/appointments`) | Template never calls API |
| `/appointments/book` | `appointments/booking.html` | Yes | Template never calls API |
| `/appointments/settings` | `appointments/settings.html` | Yes | Template never calls API |
| `/deadlines` | `deadlines/list.html` | Yes (`/api/deadlines`) | Template never calls API |
| `/deadlines/calendar` | `deadlines/calendar.html` | Yes | Template never calls API |
| `/support/tickets` | `support/tickets.html` | Yes (`/api/support`) | Template never calls API |
| `/support/new` | `support/create.html` | Yes | Template never calls API |
| `/computation-worksheet` | `computation_worksheet.html` | No | Static UI only |
| `/capital-gains` | `capital_gains.html` | No | Static UI only |
| `/k1-basis` | `k1_basis.html` | No | Static UI only |
| `/draft-forms` | `draft_forms.html` | No | Static UI only |
| `/filing-package` | `filing_package.html` | No | Calls non-existent `/api/filing-package` |
| `/documents/{id}/view` | `documents/viewer.html` | Partial | No PDF viewer logic |

### 4.2 In-Memory Services (Data Lost on Restart)
| Service | File | Impact |
|---------|------|--------|
| PaymentService | `src/cpa_panel/payments/payment_service.py` | All invoice/payment history lost |
| StaffAssignmentService | `src/cpa_panel/staff/assignment_service.py` | Team membership and assignments reset |
| CPACapacity pool | `src/cpa_panel/services/funnel_orchestrator.py` | Auto-assignment pool reset |
| Tasks API | `src/web/routers/tasks_api.py` | All task data lost |
| Appointments API | `src/web/routers/appointments_api.py` | All appointment data lost |
| Deadlines API (custom) | `src/web/routers/deadlines_api.py` | Custom deadlines lost (IRS dates are hardcoded) |

### 4.3 Admin Panel Stubs (Hardcoded Responses)
| Endpoint | Returns |
|----------|---------|
| `GET /subscriptions/mrr` | Hardcoded `$98,500` |
| `GET /subscriptions/churn` | Hardcoded `2.3%` |
| `GET /features` | Hardcoded 2-item list |
| `POST /features` | Returns `{"status": "success"}` |
| `PUT /features/{id}` | No-op |
| `GET /system/health` | All hardcoded values |
| `GET /system/errors` | Single hardcoded error |
| `POST /system/announcements` | Hardcoded `234` firms |
| `GET /users/{id}` | Hardcoded `john.doe@acmetax.com` |
| `POST /users/{id}/impersonate` | Hardcoded token |
| `GET /partners/{id}` | Hardcoded fixture |
| `POST /partners` | Returns `"partner-new"` |
| `GET /activity` | Hardcoded 4-item list |
| `GET /regulatory/status` | Static result |
| `GET /regulatory/checks` | Hardcoded MFA warning |

### 4.4 CPA Messaging
Template renders, page serves, but **no API, no service, no persistence** for messages.

### 4.5 Compliance Reports
Created in SQLite and stay in `"pending"` status permanently — async processing worker doesn't exist.

### 4.6 `revoke_all_user_tokens()`
Exists in `AuthenticationManager` with only a `logger.warning` — bulk revocation (e.g., on password change) silently does nothing.

### 4.7 Sync `get_user_by_email()` / `get_user_by_id()` in Database Mode
When `AUTH_USE_DATABASE=true`, these sync methods only search the `_users_db` in-memory dict, not the database. Password reset is silently non-functional for real DB users.

---

## 5. What is Missing Entirely

| Feature | Impact |
|---------|--------|
| GDPR data erasure endpoint | `process_gdpr_requests` permission exists but no implementation |
| Stripe SDK integration | No `stripe` Python calls anywhere — billing is DB-only |
| Real PDF generation | Current output is ASCII text, not PDF binary |
| QBI REIT/PTP income | `Form8995` model has fields but `QBICalculator` doesn't read them |
| NOL carryforward tracking | AMT adjustment type listed but no prior-year NOL model |
| SECURE 2.0 age-check (60-63 catch-up) | Constant defined ($11,250) but no age logic to apply it |
| Admin firm detail page | `GET /firms/{firm_id}` returns HTTP 501 "Coming in Phase 2" |
| Admin user management UI | List endpoint works, detail/edit are stubs |
| Admin invitation flow | Model exists, API returns fixtures |
| Partner management | List works, detail/create/update are stubs |
| Feature flag management API | Model + `is_enabled_for_firm()` logic work, but API returns hardcoded data |
| `IntelligentTaxAgent` export | Not exported from `src/agent/__init__.py` — requires full import path |

---

## 6. Critical Bugs That Block Go-Live

### P0 — Will Crash at Runtime

| # | Bug | File:Line | Impact |
|---|-----|-----------|--------|
| 1 | `complete_mfa_login()` looks up users only in-memory dict, not DB | `auth_service.py:696` | MFA login broken for all DB users |
| 2 | Sync `get_user_by_email()` broken in DB mode | `auth_service.py:1129-1143` | Password reset fails silently for real users |
| 3 | `FirmService.create_firm()` uses `User(name=...)` but model has `first_name`/`last_name` | `firm_service.py:83` | Firm creation crashes with AttributeError |
| 4 | `BillingService.cancel_subscription()` uses `SubscriptionStatus.CANCELED` (wrong spelling) | `billing_service.py:273` | Cancellation crashes with AttributeError |
| 5 | `BillingService.get_plan_by_tier()` queries `.tier` but column is `.code` | `billing_service.py:73` | Plan lookup crashes |
| 6 | `BillingService.generate_invoice()` uses `InvoiceStatus.PENDING` (doesn't exist) | `billing_service.py:437` | Invoice generation crashes |
| 7 | `firm.current_client_count` doesn't exist on Firm model | `firm_service.py:295` | Usage summary crashes |
| 8 | `AuditService(None)` — all compliance routes pass null DB session | `compliance_routes.py` | Any audit query crashes |

### P1 — Security / Data Integrity

| # | Bug | File | Impact |
|---|-----|------|--------|
| 9 | JWT Path C uses `JWT_SECRET_KEY` (different env var from Path A's `JWT_SECRET`) | `authentication.py` | Tokens from legacy path rejected by RBAC middleware |
| 10 | Two incompatible token revocation namespaces | `authentication.py` vs `rbac/middleware.py` | Revocation from one system invisible to other |
| 11 | `api_partner` not a valid RBAC Role enum value | `auth_decorators.py:640` | API key users cause ValueError in RBAC middleware |
| 12 | `PermissionCache.invalidate_firm()` clears ALL firms' cache | `core/rbac/cache.py:50` | Permission changes leak across tenants briefly |
| 13 | Admin store (refunds, API keys, compliance) in SQLite, not PostgreSQL | `database/admin_store.py` | Data lost in multi-replica deployment, not backed up |

### P2 — Functional Breakage

| # | Bug | File | Impact |
|---|-----|------|--------|
| 14 | Scenarios page sends wrong API contract (field names, missing return_id) | `templates/scenarios.html` | Scenarios page completely non-functional |
| 15 | Duplicate `POST /api/upload` with different response schemas | `upload_routes.py` + `documents.py` | Upload response unpredictable |
| 16 | `revoke_all_user_tokens()` is a no-op | `authentication.py:313-327` | Password change doesn't invalidate existing sessions |

---

## 7. Architecture Observations

### Strengths
1. **Tax engine is production-grade** — 22+ IRS forms with real computation logic, IRS-compliant decimal arithmetic, deterministic outputs, 800+ tests
2. **Lead magnet funnel is end-to-end** — landing → estimate → gate → report → engagement letter, with PII encryption, rate limiting, and CPA branding throughout
3. **Security middleware stack is comprehensive** — 12 middleware layers in correct order, RBAC v2, CSRF, rate limiting, tenant isolation, correlation IDs
4. **Graceful degradation everywhere** — every external dependency wrapped in `try/import` with fallback
5. **AI integration is sophisticated** — function calling with confidence scoring, contradiction detection, PII scrubbing, circuit breakers

### Weaknesses
1. **Three parallel auth systems** — legacy decorators, RBAC v2 dependencies, and deprecated JWT implementation coexist with incompatible secrets
2. **Mixed persistence backends** — PostgreSQL (main), SQLite (admin ops, leads), Redis (sessions, cache), in-memory (payments, staff, tasks) — no single source of truth
3. **API layer doesn't expose full engine** — REST API uses simplified calculation path, missing AMT/QBI/SE
4. **Many polished UIs with no backend wiring** — templates exist but JS never calls the APIs
5. **E2E tests use vacuous assertions** — `assert status in [200, 404, 500]` passes regardless of actual behavior

### Design Patterns Used
- Cache-aside with SHA-256 versioning
- Circuit breaker + retry with exponential backoff
- Dead letter queue for Celery task failures
- Cascade with weighted voting (ML classifier)
- Strategy pattern (recommendation sub-analyzers)
- Forward-only state machine (lead pipeline)
- Hash-chained audit entries (tamper detection)

---

## 8. Feature-by-Feature Status Matrix

### Legend
- **WORKING** = Template + Route + API + Service + DB + Tests all connected
- **PARTIAL** = Core chain works but has bugs, missing persistence, or gaps
- **STUB** = UI renders but no backend wiring / hardcoded responses
- **MISSING** = Not implemented at all

### Tax Engine
| Feature | Status |
|---------|--------|
| Federal bracket calculation (all statuses) | WORKING |
| Self-employment tax | WORKING |
| AMT (Form 6251) | WORKING |
| QBI / Section 199A | WORKING |
| Passive Activity Loss | WORKING |
| Capital gains / Schedule D | WORKING |
| 22 IRS form models | WORKING |
| 41 state calculators + DC | WORKING |
| Decimal arithmetic / determinism | WORKING |
| API `/api/calculate/complete` | PARTIAL (simplified path, not full engine) |

### AI & Advisory
| Feature | Status |
|---------|--------|
| IntelligentTaxAgent (chat) | WORKING |
| Smart Tax orchestrator | WORKING |
| Advisory report generator | WORKING |
| Recommendation engine | WORKING |
| ML document classifier | WORKING |
| Document OCR parser | WORKING |
| PII scrubber | WORKING |
| Real-time tax estimator | WORKING |
| PDF export | PARTIAL (ASCII text, not real PDF) |

### Lead Magnet & CPA
| Feature | Status |
|---------|--------|
| Lead magnet funnel (7 steps) | WORKING |
| Lead state machine | WORKING |
| CPA dashboard | WORKING |
| Leads list + pipeline kanban | WORKING |
| Analytics | WORKING |
| CPA branding | PARTIAL (local disk uploads) |
| Team management | PARTIAL (in-memory persistence) |
| Return queue | PARTIAL (counts always zero) |
| CPA messaging | STUB |
| Invoice / payments | STUB (in-memory) |

### Client-Facing UI
| Feature | Status |
|---------|--------|
| Landing page | WORKING |
| Intelligent advisor | WORKING |
| Results page | WORKING |
| Legal pages (terms, privacy, etc.) | WORKING |
| Login / register / forgot password | WORKING |
| MFA setup / verify | PARTIAL (DB lookup bug) |
| Scenarios | PARTIAL (broken API contract) |
| Documents library | PARTIAL |
| Tasks | STUB (API exists, UI not wired) |
| Appointments | STUB (API exists, UI not wired) |
| Deadlines | STUB (API exists, UI not wired) |
| Support tickets | STUB (API exists, UI not wired) |
| Tax tools (capital gains, K-1, etc.) | STUB (static UI) |
| Filing package | STUB (calls non-existent API) |

### Admin Panel
| Feature | Status |
|---------|--------|
| Admin dashboard | WORKING |
| Impersonation | WORKING |
| API key management | WORKING |
| Compliance alerts | WORKING |
| Webhook delivery | WORKING |
| Audit logging | WORKING |
| Firm list | WORKING |
| Firm detail | MISSING (returns 501) |
| User management | PARTIAL (list works, detail stub) |
| Feature flags | PARTIAL (model works, API stubs) |
| Subscription management | PARTIAL (runtime bugs) |
| Refund workflow | PARTIAL (no real payment gateway) |
| Revenue metrics | PARTIAL (churn hardcoded) |
| GDPR erasure | MISSING |
| Stripe integration | MISSING (schema only) |

### Infrastructure
| Feature | Status |
|---------|--------|
| PostgreSQL (69 tables) | WORKING |
| Redis cache | WORKING |
| Celery task queue | WORKING |
| WebSocket real-time | WORKING |
| Email notifications (3 providers) | WORKING |
| Circuit breaker / retry | WORKING |
| Rate limiting | WORKING |
| RBAC v2 middleware | WORKING |
| CSRF protection | WORKING |
| Tenant isolation | WORKING |
| Health checks | WORKING |
| Docker multi-stage build | WORKING |

---

*This document represents the complete state of the platform as of 2026-03-19. It should be used as the authoritative reference for go-live readiness decisions and sprint planning.*
