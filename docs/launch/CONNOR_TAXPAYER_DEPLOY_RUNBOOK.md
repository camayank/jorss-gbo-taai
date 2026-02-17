# Connor Taxpayer Funnel Deploy Runbook

This runbook is for deploying the taxpayer-facing white-label funnel (landing -> estimate -> teaser -> contact -> report) for CPA distribution.

## A. Preconditions
- Code merged to deploy branch.
- DB migration graph healthy.
- Production/staging env vars configured.
- CPA branding records exist (`cpa_slug`, name, optional logo/booking link).

## B. Pre-Deploy Commands
Run from repo root:

```bash
python scripts/preflight_launch.py --mode production --skip-migration-status
python scripts/preflight_launch.py --mode production
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH='.:src' python3 -m pytest \
  tests/test_lead_magnet_connor_funnel.py \
  tests/integration/test_lead_magnet_api_smoke.py \
  tests/security/test_admin_launch_blockers.py \
  tests/security/test_cpa_internal_route_auth.py \
  tests/security/test_web_launch_route_guards.py \
  tests/security/test_web_duplicate_route_guardrails.py -q
```

Block deploy on any test/preflight failure.

## C. Deploy Procedure
1. Deploy app build using existing platform pipeline.
2. Ensure startup logs show successful route registration and no auth conflicts.
3. Run live smoke:

```bash
python scripts/smoke_test_lead_magnet.py --base-url https://<deployed-domain> --cpa-slug <slug>
```

4. Validate taxpayer pages:
- `/lead-magnet/?cpa=<slug>`
- `/lead-magnet/estimate?session=<id>`
- `/lead-magnet/teaser?session=<id>`
- `/lead-magnet/contact?session=<id>`
- `/lead-magnet/report?session=<id>`

## D. Post-Deploy Verification (15 minutes)
- Confirm lead conversion works end-to-end and lead is visible in CPA dashboard.
- Confirm `lead_magnet_events` records funnel events.
- Confirm report payload includes:
  - `tax_health_score`
  - `personalization`
  - `comparison_chart`
  - `share_payload`
- Confirm anti-spam controls:
  - honeypot rejects bot-style payloads
  - too-fast dwell time returns 429

## E. Rollback Plan
Rollback triggers:
- Funnel start/profile/contact failures > 5% sustained over 10 minutes.
- Missing/blank report payload fields on taxpayer flow.
- Severe conversion drop immediately post-deploy.

Rollback actions:
1. Revert to prior stable build in hosting platform.
2. Re-run smoke test against rolled-back deployment.
3. Mark incident and open blocker ticket with:
   - failed endpoint(s)
   - affected CPA slug(s)
   - sample session/lead ids
   - first failure timestamp

## F. Incident Triage Matrix
- `POST /api/cpa/lead-magnet/start` failing:
  - Check route mount, cpa_router import, app startup errors.
- `POST /api/cpa/lead-magnet/{session}/profile` failing:
  - Check payload schema changes, state_code handling, service errors.
- `POST /api/cpa/lead-magnet/{session}/contact` failing:
  - Check anti-spam dwell validation and email payload format.
- `GET /api/cpa/lead-magnet/{session}/report` missing fields:
  - Check score builder and serialization payload.
- UI rendering mismatch:
  - Validate template data bindings and session storage hydration.

## G. First 24h Monitoring
- Monitor KPI events:
  - `start`
  - `step_complete`
  - `drop_off`
  - `lead_submit`
  - `report_view`
- Compare against targets:
  - landing->start >= 60%
  - teaser->contact >= 25%
  - contact->report >= 70%
- If teaser->contact drops below target:
  - rotate hero variant copy and CTA copy first
  - preserve scoring/report logic
