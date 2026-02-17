# Final Product Training Document (In-Depth)

Date: 2026-02-17  
Product: Jorss-GBO White-Label Tax Advisory Funnel for CPAs  
Primary GTM Objective: Convert anonymous taxpayer traffic into warm, data-rich CPA leads through a Connor-style emotional funnel.

Companion deep dive: `docs/launch/FINAL_PRODUCT_TRAINING_UI_UX_DEEP_DIVE.md` (screen-level UI/UX behavior, role flows, events, contracts, mobile/A11y standards).

## 1) Training Purpose

This is the operational training manual for launch and scale of the live product as implemented in code.

Use this document to:
- Train product, sales, onboarding, support, and operations teams.
- Run demos for CPA buyers and internal stakeholders.
- Operate launch gates, KPI monitoring, and incident triage.
- Keep implementation aligned to advisory lead generation (not return-prep-as-primary funnel).

## 2) Product Positioning (What We Are Selling)

Core offer to CPAs:
- CPA-branded white-label taxpayer experience.
- 60-120 second intake -> score reveal -> contact capture -> instant report.
- Structured lead payload delivered to CPA workflows for follow-up.

Core value to taxpayers:
- Fast "Tax Health Score" and savings estimate.
- Clear strategy preview and next steps.
- Immediate report unlock after contact capture.

Non-goal in this flow:
- The front-door funnel is not positioned as full do-it-yourself tax return preparation.
- Deep analysis, documents, advanced workflows, and extended advisory are downstream.

## 3) Platform Architecture (Current Implementation)

Stack:
- Backend: FastAPI (Python)
- UI: Jinja2 templates + vanilla JS
- Funnel analytics helper: `/src/web/static/js/lead_magnet_analytics.js`
- Primary persistence target: PostgreSQL for launch environments

Three operational layers:
1. Public taxpayer funnel (white-label CPA brand)
2. CPA dashboard and lead operations
3. Admin controls and platform governance

Primary code surfaces:
- Funnel pages: `/src/web/lead_magnet_pages.py`
- Funnel APIs: `/src/cpa_panel/api/lead_magnet_routes.py`
- Funnel business logic: `/src/cpa_panel/services/lead_magnet_service.py`
- Score config: `/src/cpa_panel/config/lead_magnet_score_config.py`
- Main web entry and route guards: `/src/web/app.py`

## 4) User Types and Access URLs

## 4.1 Taxpayer (Public Funnel)

Entry URLs:
- `/lead-magnet/?cpa=<cpa_slug>`
- `/lead-magnet/estimate?session=<session_id>`
- `/lead-magnet/teaser?session=<session_id>`
- `/lead-magnet/contact?session=<session_id>`
- `/lead-magnet/report?session=<session_id>`

Extra pages:
- `/lead-magnet/analysis?session=<session_id>` (deeper report stage)
- `/lead-magnet/engagement-letter?session=<session_id>`
- `/lead-magnet/universal-report?session=<session_id>`
- `/lead-magnet/share-card.svg?score=<0-100>` (share image)

## 4.2 CPA / Firm User

Login and app entry:
- `/login` (aliases: `/signin`, `/auth/login`)
- `/app` role-resolved entry
- `/app/workspace` -> guarded redirect to `/cpa/dashboard`

Core CPA URLs:
- `/cpa/dashboard`
- `/cpa/leads`
- `/cpa/leads/{lead_id}`
- `/cpa/analytics`
- `/cpa/branding`
- `/cpa/settings`
- `/cpa/team`
- `/cpa/clients`
- `/cpa/billing`
- `/cpa/onboarding`

## 4.3 Client Portal User (Post-conversion)

Login:
- `/client/login`

Portal:
- `/app/portal` (guarded; redirects anonymous users to `/client/login?next=/app/portal`)

## 4.4 Admin User

Admin entry:
- `/admin`
- `/admin/api-keys`

Guarded behavior:
- Anonymous requests are redirected to login and validated by role checks.

## 5) End-to-End Funnel Journey (Taxpayer)

## 5.1 Screen 1: Landing

What user sees:
- CPA brand identity
- urgency/deadline context
- hero variant (A-E)

What system captures:
- `cpa_slug`
- `variant_id`
- UTM tokens
- device context

Primary objective:
- Get "start" action to estimate flow.

## 5.2 Screen 2: Quick Estimate

What user submits:
- filing status
- state
- income range
- occupation/situation signals
- dependents/homeowner/related profile attributes

What system does:
- Creates personalization context
- Computes preview score + savings range seed
- Emits step events

## 5.3 Screen 3: Teaser (Emotional Peak)

What user sees:
- Tax Health Score preview and band
- benchmark context
- savings range
- limited strategy preview
- locked strategy count/value (curiosity gap)

What system tracks:
- teaser view
- sub-score interactions
- CTA clicks

## 5.4 Screen 4: Contact Gate (Conversion Event)

Fields:
- name
- email
- phone (variant-controlled required/optional)
- anti-spam honeypot
- dwell-time signal

Controls:
- honeypot rejection
- minimum dwell-time check
- variant-based phone requirement

On success:
- lead created
- `lead_submit` event tracked
- immediate report unlock path returned

## 5.5 Screen 5: Tier-1 Report

What user gets immediately:
- scored analysis summary
- strategy overview
- CPA consultation CTA
- share payload/copy support

What CPA receives in lead context:
- contact + profile
- score/sub-scores
- complexity and value signals
- variant and attribution metadata

## 5.6 Tier-2 Access Model

Tier-2 unlock requires both:
1. lead marked engaged by CPA
2. engagement letter acknowledged

Enforced via:
- `/api/cpa/lead-magnet/leads/{lead_id}/engage`
- `/api/cpa/lead-magnet/leads/{lead_id}/acknowledge-engagement`
- `/api/cpa/lead-magnet/{session_id}/report/full`

## 6) API Contract Training (Most Used Endpoints)

Public/prospect flow endpoints:
- `POST /api/cpa/lead-magnet/start`
- `POST /api/cpa/lead-magnet/{session_id}/profile`
- `POST /api/cpa/lead-magnet/{session_id}/event`
- `POST /api/cpa/lead-magnet/{session_id}/contact`
- `GET /api/cpa/lead-magnet/{session_id}/report`
- `GET /api/cpa/lead-magnet/{session_id}/report/full`

Analytics and CPA ops:
- `GET /api/cpa/lead-magnet/analytics/kpis`
- `GET /api/cpa/lead-magnet/leads`
- `GET /api/cpa/lead-magnet/leads/hot`
- `GET /api/cpa/lead-magnet/leads/stats`
- `GET /api/cpa/lead-magnet/leads/{lead_id}`
- `POST /api/cpa/lead-magnet/leads/{lead_id}/convert`

CPA profile/branding:
- `POST /api/cpa/lead-magnet/cpa-profiles`
- `GET /api/cpa/lead-magnet/cpa-profiles/{cpa_slug}`
- `PUT /api/cpa/lead-magnet/cpa-profiles/{cpa_id}`

Client portal auth:
- `POST /api/cpa/client/login`
- `POST /api/cpa/client/verify-token`

Core auth:
- `POST /api/core/auth/login`
- `POST /api/core/auth/register`
- `POST /api/core/auth/magic-link`
- `GET /api/core/auth/magic-link/verify`
- `POST /api/core/auth/refresh`
- `POST /api/core/auth/logout`

## 7) Connor Framework Mapping in Current Product

1. Minimal visible features:
- score
- savings preview + strategy teaser
- CPA booking/conversion CTA

2. Onboarding as product:
- page sequence itself is the product demonstration

3. Emotion-first:
- urgency + loss framing on landing
- shock/curiosity at teaser

4. Personalization:
- state, filing, income, occupation/situation reflected in report copy and scoring context

5. Proprietary score:
- weighted sub-scores configured in score config
- banded interpretation and benchmark context

6. Strategic gating:
- free preview before contact
- detail unlock after lead capture

7. Distribution support:
- CPA slug white-label links
- variant + UTM + device instrumentation
- share-card endpoint for social loop

## 8) Tax Health Score Training

Configured weighted components:
- Deduction utilization
- Entity efficiency
- Timing strategy
- Compliance safety/risk
- State optimization
- Confidence

Where defined:
- `/src/cpa_panel/config/lead_magnet_score_config.py`

Where assembled:
- `/src/cpa_panel/services/lead_magnet_service.py`

How to explain to CPA teams:
- Score is a prioritization signal, not legal/tax filing advice by itself.
- Lowest sub-scores map to first recommended strategy conversations.
- Use score + complexity + engagement to prioritize callbacks.

## 9) A/B Variants and Experimentation

Current matrix source:
- `/docs/launch/connor_variant_matrix.md`

Variant IDs:
- A, B, C, D, E

Variant dimensions:
- hero emotion
- phone required vs optional
- gate aggressiveness
- score visualization
- teaser CTA copy

Runtime controls:
- `LEAD_MAGNET_DEFAULT_VARIANT`
- `LEAD_MAGNET_RANDOMIZE_VARIANTS`

Tracking includes:
- `variant_id`
- UTM source/medium/campaign
- device type
- funnel step events

## 10) KPI Targets for Training and Operations

North-star conversion goals:
- Landing -> Estimate start: >60%
- Estimate -> Teaser: >85%
- Teaser -> Contact submit: >25%
- Contact submit -> Report view: >70%
- Report -> Booking: >20%

Engagement quality goals:
- Score interactions: >50%
- Strategy expansion engagement: >40%
- Share events: >5%

Operational expectation:
- Monitor by variant, source, and device before changing copy/design globally.

## 11) Login and Role Routing Behavior (Current)

Role-based entry behavior:
- `/app` resolves user role and routes to:
  - CPA/staff/partner/preparer -> `/cpa/dashboard`
  - client/taxpayer -> `/app/portal`

Guardrails:
- `/app/workspace` no longer renders broken pages; it redirects to canonical role destination.
- `/app/portal` requires valid client token or redirects to `/client/login`.
- `/admin` is guard-protected.

Cookie/token behavior:
- `auth_token` used for authenticated web/API role flows.
- `client_token` used for client portal session flow.

## 12) Launch Operations and Command Training

## 12.1 Environment Bootstrap

```bash
python scripts/setup_launch_env.py --environment production
```

## 12.2 Preflight Checks

```bash
python scripts/preflight_launch.py --mode production --skip-migration-status
python scripts/preflight_launch.py --mode production
```

## 12.3 Launch Gate

```bash
python scripts/run_connor_launch_gate.py
```

Optional live smoke:

```bash
python scripts/smoke_test_lead_magnet.py --base-url https://<domain> --cpa-slug <slug>
```

## 12.4 Targeted Test Suite

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH='.:src' python3 -m pytest \
  tests/test_lead_magnet_connor_funnel.py \
  tests/integration/test_lead_magnet_api_smoke.py \
  tests/security/test_admin_launch_blockers.py \
  tests/security/test_cpa_internal_route_auth.py \
  tests/security/test_web_launch_route_guards.py \
  tests/security/test_web_duplicate_route_guardrails.py -q
```

## 13) Security and Compliance Training Notes

Key practices:
- Keep taxpayer data scoped to tenant access boundaries.
- Do not expose Tier-2 without engagement controls.
- Use rate limits and anti-spam controls at contact capture.
- Keep auth routes and session handling consistent across web/API.

Messaging standard:
- This is AI-assisted advisory discovery with CPA review, not autonomous legal/tax filing advice.

## 14) Deprecated/Legacy Surface Policy

Current policy:
- Keep compatibility aliases for existing links during stabilization.
- Hard-delete only zero-reference assets.

Reference:
- `/docs/launch/legacy_deprecations_2026-02-17.md`

Already removed:
- `/src/web/templates/auth/register.html`
- `/src/web/templates/auth/forgot-password.html`

## 15) Support Team Triage Playbook

Issue: Taxpayer cannot log in to portal
- Check `/client/login` access.
- Validate `/api/cpa/client/login` response.
- Confirm token is stored (`client_token`) and redirected to `/app/portal`.

Issue: CPA not seeing leads
- Validate contact submit events.
- Confirm lead creation path in `/api/cpa/lead-magnet/{session_id}/contact`.
- Check CPA filters in `/api/cpa/lead-magnet/leads` and stats endpoints.

Issue: Funnel drop-off spike
- Pull KPI slice by variant/device/source.
- Check teaser and contact step latency and form friction settings.
- Roll to safer variant before broad design edits.

Issue: Tier-2 report blocked
- Confirm both engagement and engagement-letter acknowledgment.
- Re-check access via full-report endpoint guard response.

## 16) Training Rollout Plan (Internal Teams)

Day 1:
- Product narrative and demo flow.
- Taxpayer funnel walkthrough.
- KPI definitions and dashboard interpretation.

Day 2:
- CPA ops workflow and lead handling.
- Incident runbook simulation.
- Variant management drills.

Day 3:
- Launch gate dry run in staging.
- Smoke test execution.
- Go-live decision signoff.

## 17) Go-Live Signoff Criteria

Go-live only when:
- preflight passes
- launch gate tests pass
- smoke test passes for at least 2 CPA slugs
- conversion telemetry visible by variant/source/device
- no P0 auth, routing, or report rendering regressions

## 18) Reference Index

Primary docs:
- `/docs/launch/CONNOR_TAXPAYER_DEPLOY_RUNBOOK.md`
- `/docs/launch/CONNOR_TAXPAYER_LAUNCH_CHECKLIST.md`
- `/docs/launch/P0_fix_checklist.md`
- `/docs/launch/connor_variant_matrix.md`
- `/docs/launch/legacy_deprecations_2026-02-17.md`

Primary code:
- `/src/web/app.py`
- `/src/web/lead_magnet_pages.py`
- `/src/cpa_panel/api/lead_magnet_routes.py`
- `/src/cpa_panel/services/lead_magnet_service.py`
- `/src/cpa_panel/config/lead_magnet_score_config.py`
- `/src/web/static/js/lead_magnet_analytics.js`
