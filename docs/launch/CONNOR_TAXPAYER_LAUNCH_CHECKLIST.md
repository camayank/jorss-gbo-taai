# Connor Taxpayer Funnel Launch Checklist

Scope: white-label end-taxpayer flow from landing page through contact conversion and Tier-1 advisory report.

## 1. Environment & Setup (Go/No-Go)
- [ ] `APP_ENVIRONMENT` is `staging` or `production`.
- [ ] All required secrets are configured and non-placeholder.
- [ ] `DATABASE_URL` points to PostgreSQL in launch environments.
- [ ] `OPENAI_API_KEY` is configured or AI fallback behavior is accepted.
- [ ] Run:
  - `python scripts/preflight_launch.py --mode production --skip-migration-status`
  - `python scripts/preflight_launch.py --mode production`

## 2. Funnel Contract Validation (Taxpayer UX)
- [ ] Landing loads at `/lead-magnet/?cpa=<slug>` and shows branded CPA identity.
- [ ] Quick Estimate uses 4-step flow and state selection.
- [ ] Profile API returns:
  - `score_preview`
  - `score_band`
  - `missed_savings_range`
  - `personalization_line`
- [ ] Teaser stage shows:
  - Tax Health Score
  - comparison chart payload
  - locked strategy teaser
- [ ] Contact form enforces anti-spam:
  - honeypot `website` must be empty
  - minimum dwell-time guard
- [ ] Tier-1 report includes:
  - score/subscores/benchmark
  - personalization payload
  - comparison payload
  - share payload

## 3. Tracking & Conversion Telemetry
- [ ] Event endpoint accepts and records:
  - `start`
  - `step_complete`
  - `drop_off`
  - `lead_submit`
  - `report_view`
- [ ] Variant metadata (`hero_variant`) appears in event metadata.
- [ ] Core KPI events are queryable in `lead_magnet_events`.

## 4. White-Label Readiness (CPA-facing)
- [ ] CPA profile branding renders correctly for at least 2 slugs.
- [ ] Credentials display correctly in landing/report.
- [ ] Booking CTA routes to CPA booking URL.

## 5. Automated Verification
- [ ] One-command launch gate:
  - `python scripts/run_connor_launch_gate.py`
- [ ] Run targeted regression tests:
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH='.:src' python3 -m pytest tests/test_lead_magnet_connor_funnel.py tests/integration/test_lead_magnet_api_smoke.py tests/security/test_cpa_internal_route_auth.py tests/security/test_web_launch_route_guards.py tests/security/test_web_duplicate_route_guardrails.py tests/security/test_admin_launch_blockers.py -q`
- [ ] Optional live smoke against staging:
  - `python scripts/smoke_test_lead_magnet.py --base-url https://<staging-domain> --cpa-slug <slug>`

## 6. KPI Sign-Off (First 7 Days)
- [ ] Landing -> Quick Estimate start >= 60%
- [ ] Quick Estimate -> Teaser >= 80%
- [ ] Teaser -> Contact capture >= 25%
- [ ] Contact capture -> Report view >= 70%
- [ ] Report -> Consultation booking >= 20%

## 7. Launch Decision
- [ ] Go only if Sections 1-5 are green.
- [ ] If Section 6 lags target, keep launch live but trigger funnel copy/CTA variant optimization immediately.
