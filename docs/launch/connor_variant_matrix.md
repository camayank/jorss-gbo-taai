# Connor Variant Matrix (Taxpayer Funnel)

Primary source of truth:
- `src/web/static/js/lead_magnet_analytics.js` (`EXPERIMENT_MATRIX`)

Default selection behavior:
- `src/web/lead_magnet_pages.py`
  - `LEAD_MAGNET_DEFAULT_VARIANT` default: `A`
  - `LEAD_MAGNET_RANDOMIZE_VARIANTS` default: `0` (deterministic launch default)
  - Set `LEAD_MAGNET_RANDOMIZE_VARIANTS=1` to randomize by page session when needed.

## Variant IDs

| Variant | Hero Emotion | Phone Field | Gate Aggressiveness | Score Visual | Teaser CTA |
|---|---|---|---|---|---|
| A | fear | optional | soft | donut | unlock_report |
| B | curiosity | optional | hard | gauge | free_analysis |
| C | benchmark | required | soft | donut | unlock_report |
| D | proof | optional | soft | gauge | free_analysis |
| E | deadline | optional | hard | donut | unlock_report |

## Template Conditionals Wired

- Landing:
  - `src/web/templates/lead_magnet/landing.html`
  - Uses `getExperimentConfig()` and tags start event metadata.
- Estimate:
  - `src/web/templates/lead_magnet/quick_estimate.html`
  - Stores experiment config in session storage for downstream screens.
- Teaser:
  - `src/web/templates/lead_magnet/savings_teaser.html`
  - `score_visualization` => donut vs gauge.
  - `gate_aggressiveness` => soft/hard preview exposure.
  - `teaser_cta` => unlock vs free-analysis CTA text.
- Contact:
  - `src/web/templates/lead_magnet/contact_capture.html`
  - `phone_capture_variant` => required/optional input behavior.
  - `teaser_cta` => form subtitle/button copy mode.

## Analytics Tagging

Event helper:
- `src/web/static/js/lead_magnet_analytics.js`

Every tracked event includes:
- `variant_id`
- `utm_source`, `utm_medium`, `utm_campaign`
- `device_type`
- Metadata arms:
  - `phone_capture_variant`
  - `gate_aggressiveness`
  - `score_visualization`
  - `teaser_cta`

KPI filter support:
- `src/cpa_panel/api/lead_magnet_routes.py`
- `src/cpa_panel/services/lead_magnet_service.py`
- Supports querying by `variant_id`, `utm_source`, `device_type`, date window, and `cpa_id`.

