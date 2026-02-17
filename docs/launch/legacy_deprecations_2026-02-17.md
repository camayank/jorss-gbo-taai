# Legacy/Redundant Surface Deprecation Log (2026-02-17)

This document tracks non-canonical routes/pages identified during launch hardening.

## Canonical flows kept active

- CPA web app: `/cpa/dashboard`, `/cpa/clients`, `/cpa/team`, `/cpa/settings`, `/cpa/billing` from `web.cpa_dashboard_pages`
- Client portal: `/app/portal` and `/client/login`
- Health: `/health` from `web.routers.health`
- Validation API: `/api/validate/*` and `/api/suggestions` from `web.routers.validation`
- Lead state pipeline detail routes: `/api/cpa/leads/*` from `cpa_panel.api.lead_routes` + `pipeline_routes`

## Marked deprecated / moved

1. Legacy smart-tax route
- `GET /smart-tax-legacy` is now hidden from schema and marked deprecated.
- File: `src/web/app.py`

2. Legacy advisory aliases
- `/tax-advisory`, `/advisory`, `/start`, `/analysis`, `/tax-advisory/v2`, `/advisory/v2`, `/start/v2`, `/simple`, `/conversation`, `/chat`
- Hidden from schema and marked deprecated (still redirect to `/advisor`).
- File: `src/web/app.py`

3. Duplicate CPA page handlers in `web.app` (shadowed by canonical router)
- Replaced with explicit legacy aliases:
  - `/legacy/cpa`
  - `/legacy/cpa/v2`
  - `/legacy/cpa/clients`
  - `/legacy/cpa/settings`
  - `/legacy/cpa/team`
  - `/legacy/cpa/billing`
- Each redirects to canonical `/cpa/*` route.
- File: `src/web/app.py`

4. Duplicate root health handler in `web.app`
- Moved to deprecated alias: `GET /health/basic`
- Canonical `/health` remains in `web.routers.health`.
- File: `src/web/app.py`

5. Duplicate validation/suggestions handlers in `web.app`
- Moved to deprecated aliases:
  - `POST /api/legacy/validate/fields`
  - `POST /api/legacy/validate/field/{field_name}`
  - `POST /api/legacy/suggestions`
- Canonical `/api/validate/*` and `/api/suggestions` remain in `web.routers.validation`.
- File: `src/web/app.py`

6. CPA API route collisions removed
- Lead generation summary path changed:
  - `/api/cpa/leads/pipeline` -> `/api/cpa/leads/pipeline-summary`
- Lead generation detail path changed:
  - `/api/cpa/leads/{lead_id}` -> `/api/cpa/leads/{lead_id}/profile`
- Canonical state-engine routes keep ownership of `/api/cpa/leads/pipeline` and `/api/cpa/leads/{lead_id}`.
- Files:
  - `src/cpa_panel/api/lead_generation_routes.py`
  - `src/cpa_panel/api/router.py`

7. Removed orphan auth templates (hard-deleted)
- `src/web/templates/auth/register.html`
- `src/web/templates/auth/forgot-password.html`

Both had zero active route bindings and zero runtime references.

## Planned cleanup after 1 stable release

- Delete deprecated alias routes under `/legacy/*` and `/api/legacy/*` after confirming no access in logs.
- Re-check for any new duplicate auth templates before next release.
- Consider deleting `smart-tax-legacy` endpoint after access drops to zero.
