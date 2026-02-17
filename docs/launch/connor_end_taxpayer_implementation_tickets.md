# Connor End-Taxpayer Funnel Implementation Tickets (Launch Path)

Date baseline: 2026-02-17  
Funnel scope only: Landing -> Estimate -> Teaser -> Contact -> Tier-1 Report -> Booking/Share

## Dependency Order
1. API-001 -> API-002 -> API-003 -> API-004  
2. TPL-001 -> TPL-002 -> TPL-003 -> TPL-004 -> TPL-005  
3. MOB-001 -> MOB-002 -> MOB-003  
4. UX-001 -> UX-002  
5. API-005 (analytics filter expansion)  
6. API-006 (PostgreSQL persistence hardening)

## API Tickets

### API-001 | Canonical Strategy Waterfall Contract
- Type: `API`
- Files:
  - `src/cpa_panel/services/lead_magnet_service.py`
- Changes:
  - Add canonical contract transformer from `[{label, impact, cumulative}]` to:
    - `strategy_waterfall.bars[*].label`
    - `strategy_waterfall.bars[*].value`
    - `strategy_waterfall.bars[*].percent`
    - `strategy_waterfall.bars[*].cumulative`
    - `strategy_waterfall.total_value`
    - `strategy_waterfall.currency`
- Acceptance:
  - Tier-1 and Tier-2 report payloads both return `strategy_waterfall.bars`.
  - `tier1_report.html` and `tier2_analysis.html` render live bars without fallback rows.
- Depends on: none

### API-002 | Dynamic Tax Calendar (No Hardcoded Year)
- Type: `API`
- Files:
  - `src/cpa_panel/services/lead_magnet_service.py`
- Changes:
  - Add dynamic calendar builder that emits upcoming entries with:
    - `date_iso`, `month`, `day`, `title`, `description`, `days_remaining`, `urgency`
  - Remove hardcoded 2025 calendar payloads.
- Acceptance:
  - On 2026-02-17 baseline, first filing deadline resolves to 2026-04-15.
  - Template receives `date.month` and `date.day` for all returned rows.
- Depends on: none

### API-003 | Score Payload Completeness
- Type: `API`
- Files:
  - `src/cpa_panel/services/lead_magnet_service.py`
- Changes:
  - Extend score response with zone metadata and benchmark aliases:
    - `zones.critical|needs_attention|good|excellent`
    - `benchmark.average_score`, `benchmark.cpa_planned_average`
    - top-level `average_score`, `cpa_planned_average`
- Acceptance:
  - Teaser/report can render zone-aware visuals without template fallbacks.
  - Benchmark line can be built from payload only.
- Depends on: none

### API-004 | Share Payload + OG Card URL
- Type: `API`
- Files:
  - `src/cpa_panel/services/lead_magnet_service.py`
  - `src/web/lead_magnet_pages.py`
- Changes:
  - Add `share_payload.image_url`.
  - Add `/lead-magnet/share-card.svg` endpoint (score + savings + CPA brand).
- Acceptance:
  - Tier-1 response includes share text, share URL, and share image URL.
  - Share image endpoint returns valid SVG (`image/svg+xml`).
- Depends on: API-003

### API-005 | KPI Device Filter
- Type: `API`
- Files:
  - `src/cpa_panel/api/lead_magnet_routes.py`
  - `src/cpa_panel/services/lead_magnet_service.py`
- Changes:
  - Add `device_type` query filter to KPI endpoint and service aggregation.
- Acceptance:
  - KPI endpoint filters by variant + UTM + device.
- Depends on: none

### API-006 | Lead Persistence Migration to PostgreSQL (Scale Gate)
- Type: `API`
- Files:
  - `src/cpa_panel/services/lead_magnet_service.py`
  - `src/database/alembic/versions/*` (new migration chain)
  - `scripts/preflight_launch.py`
- Changes:
  - Move lead/session/event persistence off local SQLite file path to shared Postgres.
  - Ensure preflight migration check passes cleanly.
- Acceptance:
  - Multi-instance writes/read consistency verified.
  - No launch-blocking pending migrations in preflight gate.
- Depends on: API-001..005

## Template Tickets

### TPL-001 | Landing Headline Experiments + Share OG Tags
- Type: `TPL`
- Files:
  - `src/web/templates/lead_magnet/landing.html`
  - `src/web/static/js/lead_magnet_analytics.js`
- Changes:
  - Keep 5 hero variants.
  - Add Open Graph/Twitter image tags referencing share card endpoint.
  - Record experiment dimensions in events.
- Acceptance:
  - Landing variant visible by `variant_id`.
  - Shared links show branded score card preview.
- Depends on: API-004

### TPL-002 | Estimate Processing Proof + Personalization Context
- Type: `TPL`
- Files:
  - `src/web/templates/lead_magnet/quick_estimate.html`
- Changes:
  - Keep 2.2s processing confidence animation.
  - Inject state + filing tokens into processing subtitle.
  - Add major life change situation option for personalization surface.
- Acceptance:
  - Processing subtitle reflects selected state/filing.
  - Profile submission carries life-event signal when selected.
- Depends on: none

### TPL-003 | Teaser Variant Wiring (Gate + Score Viz + CTA)
- Type: `TPL`
- Files:
  - `src/web/templates/lead_magnet/savings_teaser.html`
  - `src/web/static/js/lead_magnet_analytics.js`
- Changes:
  - Add variant-driven score visualization mode (`donut` vs `gauge`).
  - Add gate aggressiveness (`soft` vs `hard`) for visible strategy count.
  - Add CTA copy variant (`Unlock My Full Report` vs `Get My Free Analysis`).
  - Emit score interaction events with experiment context.
- Acceptance:
  - Teaser reflects assigned variant dimensions without manual URL hacks.
  - Score/waterfall/personalization elements render with live payload.
- Depends on: API-001, API-003

### TPL-004 | Contact Gate Value Exchange + Phone Variant
- Type: `TPL`
- Files:
  - `src/web/templates/lead_magnet/contact_capture.html`
  - `src/web/static/js/lead_magnet_analytics.js`
- Changes:
  - Derive phone required/optional from shared experiment config.
  - Keep anti-spam + dwell-time checks.
  - Keep immediate unlock transition.
- Acceptance:
  - Contact gate aligns with variant and still posts `phone_capture_variant`.
  - Submit redirects immediately to report.
- Depends on: TPL-003

### TPL-005 | Tier-1 Share Card UX + Waterfall Binding
- Type: `TPL`
- Files:
  - `src/web/templates/lead_magnet/tier1_report.html`
  - `src/web/templates/lead_magnet/tier2_analysis.html`
- Changes:
  - Bind to canonical `strategy_waterfall.bars[*]`.
  - Add share-card preview + copy link action.
- Acceptance:
  - Report waterfall renders from payload (no static fallback required in happy path).
  - Share image URL copy action emits analytics.
- Depends on: API-001, API-004

## Mobile Tickets

### MOB-001 | Score Visual Sizing by Breakpoint
- Type: `MOB`
- Files:
  - `src/web/templates/lead_magnet/savings_teaser.html`
- Changes:
  - Mobile-specific score visual sizing and layout fallbacks.
- Acceptance:
  - Visual remains readable at 375px/390px/430px.
- Depends on: TPL-003

### MOB-002 | Contact Form Touch/Keyboard Optimization
- Type: `MOB`
- Files:
  - `src/web/templates/lead_magnet/contact_capture.html`
- Changes:
  - Keep 44px+ touch targets and semantic input types/autocomplete.
  - Preserve inline validation.
- Acceptance:
  - Autofill and mobile keyboard behavior verified on iOS/Android browsers.
- Depends on: TPL-004

### MOB-003 | Teaser/Report Load-Time Guardrails
- Type: `MOB`
- Files:
  - `src/web/templates/lead_magnet/quick_estimate.html`
  - `src/web/templates/lead_magnet/savings_teaser.html`
  - `src/web/templates/lead_magnet/tier1_report.html`
- Changes:
  - Keep prefetch during processing overlay.
  - Defer non-critical JS and keep chart rendering lightweight.
- Acceptance:
  - Teaser/report perceived load under 3s on 4G synthetic check.
- Depends on: TPL-002, TPL-003, TPL-005

## UX Tickets

### UX-001 | Emotional Copy + Deadline Escalation
- Type: `UX`
- Files:
  - `src/web/templates/lead_magnet/landing.html`
  - `src/web/templates/lead_magnet/savings_teaser.html`
  - `src/web/templates/lead_magnet/contact_capture.html`
- Changes:
  - Maintain 5 landing headline variants.
  - Align teaser/contact copy with value-exchange and urgency states.
- Acceptance:
  - Copy changes are variant-aware and measurable in event metadata.
- Depends on: TPL-001, TPL-003, TPL-004

### UX-002 | Personalization Token Reflection Map
- Type: `UX`
- Files:
  - `src/cpa_panel/services/lead_magnet_service.py`
  - `src/web/templates/lead_magnet/quick_estimate.html`
  - `src/web/templates/lead_magnet/savings_teaser.html`
  - `src/web/templates/lead_magnet/contact_capture.html`
  - `src/web/templates/lead_magnet/tier1_report.html`
- Changes:
  - Ensure tokens are emitted in payload and reflected in all post-estimate screens.
  - Add fallback token copy when fields are missing.
- Acceptance:
  - At least 15 tokenized touchpoints exist across screens.
- Depends on: API-003, TPL-002, TPL-003, TPL-004

