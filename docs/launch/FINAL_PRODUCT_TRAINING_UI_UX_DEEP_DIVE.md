# Final Product Training Manual: UI/UX Deep Dive

Date: 2026-02-17  
Product: Jorss-GBO White-Label Tax Advisory Platform  
Scope: Full UI/UX operating manual across taxpayer, CPA, client, and admin surfaces  
Primary objective: Convert anonymous taxpayer traffic into high-quality CPA leads, then move those leads through consultation and conversion workflows without UX friction.

---

## 1) What This Document Adds Beyond the Existing Training Manual

`FINAL_PRODUCT_TRAINING_DOCUMENT.md` already covers launch operations, positioning, and APIs.  
This companion adds implementation-level UI/UX depth:

1. Exact screen behavior and state transitions.
2. Event instrumentation per screen.
3. Role-by-role login and route flow.
4. Personalization and experiment behavior.
5. Data contract requirements for visual components.
6. Mobile, accessibility, and performance expectations.
7. QA checks tied to the actual templates and routes in code.

---

## 2) Source-of-Truth Code Surfaces

### Taxpayer funnel (Layer 1)
- Routes: `src/web/lead_magnet_pages.py`
- APIs: `src/cpa_panel/api/lead_magnet_routes.py`
- Service/business logic: `src/cpa_panel/services/lead_magnet_service.py`
- Analytics helper: `src/web/static/js/lead_magnet_analytics.js`
- Templates:
  - `src/web/templates/lead_magnet/landing.html`
  - `src/web/templates/lead_magnet/quick_estimate.html`
  - `src/web/templates/lead_magnet/savings_teaser.html`
  - `src/web/templates/lead_magnet/contact_capture.html`
  - `src/web/templates/lead_magnet/tier1_report.html`
  - `src/web/templates/lead_magnet/tier2_analysis.html`
  - `src/web/templates/lead_magnet/tier2_locked.html`
  - `src/web/templates/lead_magnet/engagement_letter.html`

### CPA workspace (Layer 2)
- Routes: `src/web/cpa_dashboard_pages.py`
- Templates: `src/web/templates/cpa/*.html`

### Unified app/auth/admin entry (Layer 3 and role routing)
- App entry and guards: `src/web/app.py`
- Auth templates:
  - `src/web/templates/auth/login.html`
  - `src/web/templates/auth/client_login.html`
  - `src/web/templates/auth/signup.html`
  - `src/web/templates/auth/forgot_password.html`
  - `src/web/templates/auth/reset-password.html`

---

## 3) Role-Based Login URLs and Canonical Entrypoints

## 3.1 Taxpayer (public)
- Start: `/lead-magnet/?cpa=<cpa_slug>`
- Flow:
  - `/lead-magnet/estimate?session=<session_id>`
  - `/lead-magnet/teaser?session=<session_id>`
  - `/lead-magnet/contact?session=<session_id>`
  - `/lead-magnet/report?session=<session_id>`
  - `/lead-magnet/analysis?session=<session_id>` (Tier-2, access-guarded)

## 3.2 CPA
- Login: `/login` (aliases `/signin`, `/auth/login`)
- App resolver: `/app`
- Workspace canonical entry: `/app/workspace` -> `/cpa/dashboard`

## 3.3 Client portal user
- Login: `/client/login`
- Portal canonical entry: `/app/portal`
- Guard behavior: anonymous users are redirected to `/client/login?next=/app/portal`

## 3.4 Admin
- Admin entry: `/admin`
- API key management: `/admin/api-keys`
- Guard behavior: non-admin redirected to login or role-appropriate path

---

## 4) Taxpayer Funnel UX: Screen-by-Screen Deep Dive

## 4.1 Screen S1: Landing
- Route: `/lead-magnet/`
- Template: `landing.html`
- User goal: decide to start assessment quickly.
- UX goal: emotion + trust in first 10-15 seconds.
- Key visible components:
  - CPA brand block (logo, name, credentials).
  - Dynamic deadline banner (`deadline_context.days_remaining`, urgency class).
  - Hero headline variant A-E.
  - Benefits grid and “What You’ll Get” list.
  - Single primary CTA.
- Personalization shown:
  - CPA identity.
  - Deadline urgency.
  - Shared-score mode (`?share=1&score=NN`) modifies hero copy.
- Invisible data captured:
  - `cpa_slug`, `variant_id`, UTM fields, `device_type`, referrer.
- Key events:
  - `start` on CTA success.
  - analytics helper also emits gtag-safe view.
- Errors/fallback:
  - Start API fail -> alert + button re-enabled.
- Mobile notes:
  - CTA full-width in mobile breakpoint.
  - Hero stack is single column.

## 4.2 Screen S2: Quick Estimate
- Route: `/lead-magnet/estimate`
- Template: `quick_estimate.html`
- User goal: finish intake quickly.
- UX goal: progress momentum + “this is tailored to me”.
- Question architecture:
  - Q1 filing status.
  - Q2 income range.
  - Q3 situations multi-select (homeowner, kids, self-employed, investments, student loans, major life change).
  - Q4 state selector.
- Trust/credibility component:
  - 2.2 second processing proof overlay with checklist.
- Personalization behavior:
  - live persona hint from selected filing/income/state.
  - processing subtitle references filing + state.
- Data persisted to sessionStorage:
  - complexity, score preview, score band, savings range, personalization tokens, benchmark, deadline days, comparison chart seed.
- Key events:
  - `step_complete` for each step.
  - `step_complete` for `estimate_view`.
  - `step_complete` for `profile` after API success.
  - `drop_off` beacon if user leaves before submit.
- Failure handling:
  - profile submit failure -> overlay closes + error alert.
- Mobile notes:
  - card-based options with tap targets >44px.
  - state picker and buttons are touch-sized.

## 4.3 Screen S3: Savings Teaser (emotional peak)
- Route: `/lead-magnet/teaser`
- Template: `savings_teaser.html`
- User goal: understand score and savings potential.
- UX goal: shock + relief + curiosity gap before contact gate.
- Above-fold components:
  - savings range hero.
  - score visualization (donut or gauge by variant).
  - score band and context.
  - personalization line.
  - current vs optimized comparison bars.
- Mid-section:
  - top insights preview.
  - locked insights block with dynamic count/list.
  - subscore chips for interaction.
- Variant-driven behavior:
  - `gate_aggressiveness`: soft (3 preview) vs hard (2 preview).
  - `score_visualization`: donut vs gauge.
  - `teaser_cta`: unlock wording vs free-analysis wording.
- Key events:
  - `step_complete` `teaser_view`.
  - `step_complete` `teaser` on CTA click.
  - `step_complete` `score_interaction` when subscore clicked.
  - `drop_off` beacon on exit before CTA.
- Data dependencies:
  - pulls from `GET /api/cpa/lead-magnet/{session}/report`.
  - uses fallback values if report call fails.
- Mobile notes:
  - score ring/gauge scales at small breakpoints.
  - chart and strategy sections are vertically stacked.

## 4.4 Screen S4: Contact Gate
- Route: `/lead-magnet/contact`
- Template: `contact_capture.html`
- User goal: unlock full report immediately.
- UX goal: make data exchange feel fair and safe.
- Components:
  - context recap card (savings, score, personalization).
  - report-includes checklist.
  - form fields: first name, email, phone (variant required/optional), consent checkbox.
  - anti-spam honeypot field.
  - loading + unlock success animation.
- Security/anti-abuse behavior:
  - honeypot rejection.
  - minimum dwell time validation (`MIN_CONTACT_FORM_DWELL_MS`).
  - variant-enforced phone requirement when active.
- Key events:
  - `step_complete` `contact_view`.
  - `step_complete` `contact_submit`.
  - server tracks `lead_submit`.
  - `drop_off` beacon if user leaves before submit.
- Post-submit UX:
  - success state inside loading card.
  - ~850ms unlock transition then redirect to report.
- Mobile notes:
  - autocomplete on name/email/phone.
  - inline error messages, no full-page refresh.

## 4.5 Screen S5: Tier-1 Report
- Route: `/lead-magnet/report`
- Template: `tier1_report.html`
- User goal: get clear initial plan and book CPA call.
- UX goal: conversion from curiosity to action.
- Above-fold:
  - tax health score, band, subscore bars.
  - benchmark lines.
  - missed savings range.
  - current vs optimized comparison.
  - top recommended actions.
- Mid/low sections:
  - insight cards.
  - strategy waterfall.
  - locked Tier-2 teaser.
  - CTA for consultation booking.
  - share section with copy/link/card link buttons.
- Key events:
  - `report_view` `report_tier1`.
  - `score_interaction` from subscore rows.
  - `share_copy_text`, `share_copy_link`, `share_copy_card_link`.
- Data dependencies:
  - expects `report.strategy_waterfall.bars[*].value/percent`.
- Mobile notes:
  - section cards stack.
  - score and comparison remain readable without horizontal scrolling.

## 4.6 Screen S6: Tier-2 Full Analysis
- Route: `/lead-magnet/analysis`
- Template: `tier2_analysis.html`
- Access guard:
  - requires lead engaged + engagement letter acknowledged.
- UX goal: comprehensive advisory package after qualification.
- Components:
  - full savings summary.
  - full insights with IRS/form/deadline metadata.
  - action checklist.
  - dynamic tax calendar.
  - CPA direct contact block.
  - full disclosures.
- Data dependencies:
  - `strategy_waterfall.bars`.
  - `tax_calendar[*].month/day/title/description`.
- Mobile notes:
  - single-column sections with readable metadata chips.

---

## 5) Funnel State Model and Transitions

### Session state progression
1. `start`
2. `profile_complete`
3. `teaser_view`
4. `contact_view`
5. `lead_submit`
6. `report_view`
7. `booked` (when booking CTA flow completes)

### Lead state progression
1. `created`
2. `scored`
3. `routed`
4. `engaged`
5. `converted`

### Blocking conditions
- No session -> estimate/teaser/contact/report routes redirect to landing.
- Tier-2 report denied unless both compliance conditions are met.

---

## 6) Experiment and Personalization System

## 6.1 Variant matrix (`lead_magnet_analytics.js`)
- A: fear hero, phone optional, soft gate, donut, unlock CTA.
- B: curiosity hero, phone optional, hard gate, gauge, free-analysis CTA.
- C: benchmark hero, phone required, soft gate, donut, unlock CTA.
- D: proof hero, phone optional, soft gate, gauge, free-analysis CTA.
- E: deadline hero, phone optional, hard gate, donut, unlock CTA.

## 6.2 Personalization tokens carried through flow
- `filing_status`, `income_range`, `occupation_type`, `state_code`, complexity.
- Rendered in:
  - estimate persona hint.
  - processing subtitle.
  - teaser copy.
  - contact context card.
  - report personalization lines and action rationale.

## 6.3 Deadline urgency behavior
- Derived from next April 15 using dynamic date logic.
- Payload includes: `deadline_date`, `days_remaining`, `urgency`, message.

---

## 7) Data Contract Deep Dive (UX-Critical)

## 7.1 Tier-1 report contract (high-impact fields for UI)
- `tax_health_score`:
  - `overall`, `band`, `subscores`, `benchmark`, `recommended_actions`, `zones`.
- `comparison_chart`:
  - bars for current vs optimized.
- `strategy_waterfall` (canonical):
  - `{ bars: [{label, value, percent, cumulative}], total_value, currency }`
- `personalization`:
  - `{ line, tokens }`
- `share_payload`:
  - `{ text, url, image_url }`

## 7.2 Tier-2 report contract (calendar + deep analysis)
- `all_insights`, `action_items`, `strategy_waterfall`, `tax_calendar`.
- `tax_calendar` canonical fields:
  - `date_iso`, `month`, `day`, `title`, `description`, `days_remaining`, `urgency`.

## 7.3 Why this matters for UX
- Waterfall and calendar visuals fail or degrade if shape mismatches occur.
- Teaser/report confidence drops fast when charts render fallback/static content.

---

## 8) Error and Fallback UX Matrix

| Area | Trigger | User-visible behavior | System behavior |
|---|---|---|---|
| Landing start | start API fails | alert + CTA reset | no session created |
| Estimate submit | profile API fails | overlay closed + alert | no transition |
| Teaser hydration | report API fails | fallback score/range/insights UI | local/session fallback |
| Contact submit | validation fails | inline field errors | no request sent |
| Contact submit | honeypot triggered | generic invalid message | request blocked |
| Contact submit | dwell too fast | “take a moment” message | 429 response |
| Tier-2 access | compliance not met | locked/denied route behavior | 403 with reason payload |

---

## 9) Mobile-First UX Implementation Standards

1. Single-column stack for all taxpayer flow screens.
2. Touch target minimum: 44px.
3. Form input height target: ~48px.
4. One primary CTA per screen.
5. Inline errors only, no disruptive page reload.
6. Score and comparison visuals fit without horizontal scroll.
7. Teaser/report payloads should stay lightweight for <3 second perceived render on 4G.

---

## 10) Accessibility and Interaction Standards

1. Interactive score rows in report use keyboard support (`tabindex`, Enter/Space handlers).
2. Form fields include proper labels and autocomplete hints.
3. Error states are shown adjacent to fields.
4. Consent is explicit and required.
5. Visual-only states (badges/colors) should always include text labels.

---

## 11) CPA Workspace UX Deep Dive

## 11.1 Primary navigation surfaces
- Dashboard: `/cpa/dashboard`
- Onboarding: `/cpa/onboarding`
- Leads list/detail: `/cpa/leads`, `/cpa/leads/{lead_id}`
- Analytics: `/cpa/analytics`
- Profile/branding/settings/team: `/cpa/profile`, `/cpa/branding`, `/cpa/settings`, `/cpa/team`
- Operations: `/cpa/tasks`, `/cpa/appointments`, `/cpa/deadlines`, `/cpa/returns/queue`, `/cpa/returns/{session_id}/review`
- Business admin: `/cpa/clients`, `/cpa/billing`

## 11.2 UX intent by module
- Dashboard: prioritize action queue and funnel health at a glance.
- Onboarding: drive “time to first live lead” with 3-step completion.
- Leads list/detail: move qualified leads to engagement quickly.
- Analytics: expose conversion, temperature, and value patterns.
- Branding/settings: preserve white-label consistency with minimal friction.

## 11.3 Authentication behavior
- `require_cpa_auth` enforces access.
- Demo mode is controlled and environment-gated.
- Role mismatches redirect to correct entrypoint.

---

## 12) Client Portal UX Deep Dive

## 12.1 Entry behavior
- Route: `/app/portal`
- If not authenticated and no `client_token`, redirect to `/client/login?next=/app/portal`.
- Admin users are redirected away from client portal surface.

## 12.2 UX purpose
- Give converted clients a clean, focused portal experience without exposing CPA/admin internals.

---

## 13) Admin and System UX Surfaces

### Core routes
- `/admin`
- `/admin/api-keys`
- `/hub` or `/system-hub`
- `/workflow` or `/workflow-hub`

### UX objective
- Operational observability, governance, and system controls with strict role isolation.

---

## 14) Event Instrumentation Reference

### Event names accepted by API
- `start`
- `step_complete`
- `drop_off`
- `lead_submit`
- `report_view`

### Common metadata injected by analytics helper
- `variant_id`, `hero_variant`
- `utm_source`, `utm_medium`, `utm_campaign`
- `device_type`
- `phone_capture_variant`
- `gate_aggressiveness`
- `score_visualization`
- `teaser_cta`

### KPI endpoint
- `GET /api/cpa/lead-magnet/analytics/kpis` with filters:
  - `date_from`, `date_to`, `variant_id`, `utm_source`, `device_type`, `cpa_id`

---

## 15) QA Playbook by Role

## 15.1 Taxpayer funnel QA
1. Landing variant/copy/CTA switch works for A-E.
2. Session starts and carries variant/UTM/device.
3. Estimate stepper tracks step events and blocks invalid transitions.
4. Teaser loads dynamic score, comparison, insights, and lock count.
5. Contact gate enforces consent and variant phone rule.
6. Contact submission creates lead and redirects to report.
7. Report tracks view and score/share interactions.
8. Tier-2 remains locked until compliance conditions are true.

## 15.2 CPA QA
1. `/app` resolves to `/cpa/dashboard` for CPA roles.
2. Onboarding step status updates accurately.
3. Leads list/detail show latest captured metadata.
4. Analytics renders key conversion and quality signals.

## 15.3 Client/Admin QA
1. Client login and portal redirect chain works with/without token.
2. Admin pages reject non-admin users.
3. Cross-role navigation does not leak unauthorized surfaces.

---

## 16) Known UX Risks to Monitor

1. Data shape regressions in waterfall/calendar payloads can silently degrade core visuals.
2. Aggressive gate variants can improve lead quality but reduce contact conversion volume.
3. Phone-required variant can increase friction on mobile.
4. Overly fallback-heavy UI can hide backend data issues if not observed in QA dashboards.

---

## 17) Recommended Operating Cadence

1. Weekly: variant KPI review (start rate, teaser-to-contact, report-to-booking).
2. Weekly: funnel replay QA on mobile widths (375/390/430).
3. Bi-weekly: copy/CTA experiments based on drop-off hotspots.
4. Monthly: route and template deprecation review to keep UX surface clean.

---

## 18) Practical Training Sequence for New Team Members

1. Read this document once end-to-end.
2. Run taxpayer flow manually from landing to report with one CPA slug.
3. Repeat with variants A and B to observe gate/score differences.
4. Capture a lead and verify CPA dashboard ingestion.
5. Test role routing: `/app`, `/app/workspace`, `/app/portal`, `/admin`.
6. Validate one Tier-2 unlock path (engage + acknowledge engagement letter).

This sequence gets a new team member from zero context to operational competence in under one day.

