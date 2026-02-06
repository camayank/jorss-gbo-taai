# UX Polish & Design System Implementation Plan

**Created**: 2026-02-06
**Status**: Approved
**Goal**: Achieve 95%+ UI consistency across all portals with production-grade UX

---

## Executive Summary

Comprehensive UX polish initiative to unify the Jorss-Gbo tax platform's design system across all portals (Admin, CPA, Web, Lead Magnet). Currently at ~68% consistency, targeting 95%+.

### Key Decisions

| Decision | Choice |
|----------|--------|
| **Scope** | Comprehensive (visual, mobile, interactions) |
| **Timeline** | Flexible - prioritize quality |
| **Migration** | Hybrid: clean break (internal), gradual (public) |
| **Validation** | Manual review + automated visual regression |
| **Tooling** | Full design system with Storybook |

---

## Phase Overview

| Phase | Focus | Approach | Quality Gate |
|-------|-------|----------|--------------|
| **1** | Foundation (CSS consolidation) | Clean break | CSS consolidated, baseline screenshots |
| **2** | Component Library + Storybook | New tooling | Storybook live, visual tests pass |
| **3** | Internal Portals (Admin + CPA) | Clean break | Lighthouse ≥ 90, mobile works |
| **4** | Public Portal (Web + Lead Magnet) | Gradual (feature flag) | A/B metrics stable, 100% rollout |
| **5** | Polish & Testing | Comprehensive | WCAG AA, cross-browser, perf ≥ 90 |

### Branch Strategy

```
main
└── feature/ux-polish
    ├── phase-1-foundation
    ├── phase-2-components
    ├── phase-3-internal
    ├── phase-4-public
    └── phase-5-polish
```

---

## Phase 1: Foundation (CSS Consolidation)

**Goal**: Single source of truth for all design tokens, zero deprecated files.

### Tasks

1. **Audit & Document Current State**
   - Generate inventory of all CSS files with usage mapping
   - Identify which templates import which styles
   - Document all variable naming schemes currently in use

2. **Unify Design Tokens** (`src/web/static/css/core/variables.css`)
   - Consolidate 3 naming schemes → 1 canonical system
   - Standardize accent color: Teal `#14b8a6` everywhere
   - Create migration map: old variable → new variable

3. **Delete Deprecated Files**
   - Remove `admin.css` (deprecated marker)
   - Remove `cpa.css` (deprecated marker)
   - Remove `unified-theme.css` (bridge file, no longer needed)
   - Delete duplicate templates: `cpa_dashboard.html` (keep refactored version)

4. **Create Base Import Structure**
   ```
   css/
   ├── tokens.css          # Variables only (colors, spacing, typography)
   ├── reset.css           # Normalize + base styles
   ├── utilities.css       # Utility classes
   └── main.css            # Single entry point, imports all
   ```

5. **Quality Gate**
   - All pages render without CSS errors
   - No 404s for removed CSS files
   - Visual diff baseline captured (screenshots of all key pages)

### Robustness Additions
- Create `css-migration.json` mapping old → new for automated find/replace
- Add CSS linting (Stylelint) to catch variable misuse
- Baseline screenshot test suite before any changes

---

## Phase 2: Component Library + Storybook

**Goal**: Reusable Jinja2 components with visual documentation and isolated testing.

### Tasks

1. **Setup Storybook for Jinja2**
   - Install Storybook with HTML addon (works with rendered Jinja2)
   - Configure build to render Jinja2 partials → static HTML for Storybook
   - Add to `package.json` scripts: `storybook`, `build-storybook`

2. **Create Component Partials** (`src/web/templates/components/`)
   ```
   components/
   ├── buttons/
   │   ├── button.html        # All 8 variants + sizes
   │   └── button_group.html
   ├── forms/
   │   ├── input.html         # Text, email, password, etc.
   │   ├── select.html
   │   ├── checkbox.html
   │   ├── radio.html
   │   ├── form_group.html    # Label + input + error + help text
   │   └── validation.html    # Error/success states
   ├── feedback/
   │   ├── toast.html         # Notifications
   │   ├── alert.html         # Inline alerts
   │   ├── loading.html       # Spinner, skeleton, progress
   │   └── empty_state.html   # No data patterns
   ├── layout/
   │   ├── card.html          # All card variants
   │   ├── modal.html         # Modal, drawer, sheet
   │   ├── sidebar.html       # Navigation sidebar
   │   └── breadcrumb.html
   └── data/
       ├── table.html         # Responsive tables
       └── stat_card.html     # Metrics display
   ```

3. **Standardize Component API**
   Each component accepts consistent parameters:
   ```jinja2
   {% include "components/buttons/button.html" with
      variant="primary",      {# primary|secondary|danger|ghost #}
      size="md",              {# xs|sm|md|lg|xl #}
      loading=false,
      disabled=false,
      icon=none,
      full_width=false
   %}
   ```

4. **Add Visual Regression Testing**
   - Install Percy or Chromatic for Storybook
   - Capture baseline screenshots of each component state
   - CI integration: block merge if visual diff detected without approval

5. **Quality Gate**
   - All components render in Storybook
   - Each component has stories for: default, all variants, loading, disabled, error states
   - Visual regression baseline established
   - Documentation for each component (props, usage examples)

### Robustness Additions
- Component props validation (fail loudly on invalid props)
- Accessibility checks in Storybook (a11y addon)
- Mobile viewport stories for each component

---

## Phase 3: Internal Portals (Clean Break)

**Goal**: Admin + CPA portals fully migrated to component library, legacy templates deleted.

**Scope**: 16 templates (Admin: 3, CPA: 13)

### Tasks

1. **Admin Portal Migration** (3 templates)

   | Template | Action |
   |----------|--------|
   | `admin_dashboard.html` | Rebuild using components, remove inline styles |
   | `admin_api_keys.html` | Migrate to component library |
   | `admin_impersonation.html` | Migrate to component library |

   - Unify dark theme as proper theme variant (not separate CSS)
   - Add to `tokens.css`: `[data-theme="dark"]` variables
   - Apply consistent sidebar navigation

2. **CPA Portal Migration** (13 templates)

   | Priority | Templates |
   |----------|-----------|
   | **High** | `cpa/dashboard.html`, `cpa/clients.html`, `cpa/leads_list.html` |
   | **Medium** | `cpa/analytics.html`, `cpa/billing.html`, `cpa/branding.html` |
   | **Lower** | `cpa/appointments.html`, `cpa/deadlines.html`, `cpa/tasks.html`, `cpa/staff.html` |

   - Delete legacy files: `cpa_dashboard.html`, `cpa_dashboard_refactored.html`, `cpa_landing.html`
   - Update `cpa/base.html` to use component partials
   - Standardize accent: Teal across all CPA pages

3. **Shared Internal Components**
   ```
   components/internal/
   ├── data_table.html      # Sortable, filterable tables
   ├── metric_grid.html     # Dashboard stat cards
   ├── action_bar.html      # Bulk actions, filters
   └── nav_sidebar.html     # Collapsible sidebar
   ```

4. **Mobile Navigation (Internal)**
   - Implement hamburger menu → slide-out sidebar
   - Touch-friendly action buttons (48px minimum)
   - Responsive tables: horizontal scroll or card-stack on mobile

5. **Quality Gate**
   - Zero legacy CSS imports in internal portals
   - All pages pass Lighthouse accessibility audit (score ≥ 90)
   - Visual regression tests pass
   - Manual review: navigate every page on desktop + mobile
   - Load testing: dashboards render < 2s with 1000+ records

### Robustness Additions
- Add error boundaries: failed component renders fallback, not blank page
- Consistent loading skeletons for all data fetches
- Empty state for every list/table (no blank screens)
- Session timeout warning modal (5 min before expiry)

---

## Phase 4: Public Portal (Gradual Migration)

**Goal**: Web portal + Lead magnet migrated without disrupting active users. Feature-flagged rollout.

**Scope**: 30+ templates (Web: 22, Lead Magnet: 8)

### Tasks

1. **Feature Flag Setup**
   ```python
   # src/web/config.py
   UX_V2_ENABLED = env.bool("UX_V2_ENABLED", default=False)
   UX_V2_PERCENTAGE = env.int("UX_V2_PERCENTAGE", default=0)  # Gradual rollout
   ```
   - 0% → 10% → 50% → 100% rollout
   - Cookie-based consistency (same user sees same version)
   - Admin override: `?ux_v2=1` for testing

2. **Dual Template Strategy**
   ```
   templates/web/
   ├── dashboard.html           # Current (legacy)
   ├── v2/
   │   └── dashboard.html       # New (component-based)
   └── _resolver.html           # Routes based on feature flag
   ```

3. **High-Impact Pages First**

   | Priority | Page | Reason |
   |----------|------|--------|
   | **P0** | `intelligent_advisor.html` | 14K lines, needs refactor into partials |
   | **P0** | `guided_filing.html` | Core user flow |
   | **P0** | `results.html` | Conversion-critical |
   | **P1** | `dashboard.html` | Frequent use |
   | **P1** | `client_portal.html` | User home |
   | **P2** | `quick_estimate.html` | Lead capture |
   | **P2** | Lead magnet templates | Marketing pages |

4. **Intelligent Advisor Refactor** (largest file)
   Break 14,000-line file into:
   ```
   intelligent_advisor/
   ├── base.html                # Layout shell
   ├── partials/
   │   ├── chat_interface.html
   │   ├── form_sections/
   │   │   ├── income.html
   │   │   ├── deductions.html
   │   │   ├── credits.html
   │   │   └── ...
   │   ├── progress_tracker.html
   │   ├── document_upload.html
   │   └── results_preview.html
   └── scripts/
       ├── chat.js
       ├── validation.js
       └── autosave.js
   ```

5. **Form UX Standardization**
   - Real-time validation with inline feedback
   - Consistent error messages (red border + icon + text below field)
   - Success confirmation (green checkmark + brief message)
   - Auto-save indicator (subtle "Saved" badge)
   - Progress bar for multi-step forms

6. **Lead Magnet Polish**
   - Unify accent color (remove blue → teal)
   - Mobile-optimized forms
   - Fast load times (< 1.5s LCP)
   - Clear CTAs with loading states

7. **Rollout Process**
   ```
   Week 1: Internal testing (UX_V2_PERCENTAGE=0, manual override)
   Week 2: 10% rollout, monitor errors/analytics
   Week 3: 50% rollout if metrics stable
   Week 4: 100% rollout, delete legacy templates
   ```

8. **Quality Gate**
   - A/B metrics: bounce rate, completion rate, time-on-task
   - Error rate < 0.1% for v2 pages
   - No Sentry alerts from new templates
   - Core Web Vitals pass (LCP < 2.5s, CLS < 0.1)
   - Manual review at each rollout percentage

### Robustness Additions
- Automatic rollback: if error rate spikes, revert to 0%
- Session continuity: user mid-flow stays on same version
- Analytics events: track which version user sees
- Fallback rendering: if component fails, show simplified HTML

---

## Phase 5: Polish & Testing

**Goal**: Production-grade quality across mobile, accessibility, performance, and visual consistency.

### Tasks

1. **Mobile Responsiveness Audit**

   | Breakpoint | Target |
   |------------|--------|
   | 320px | Small phones (iPhone SE) |
   | 375px | Standard phones (iPhone 14) |
   | 768px | Tablets |
   | 1024px | Small laptops |
   | 1280px+ | Desktops |

   - Test every page at each breakpoint
   - Fix: sidebar collapse, table overflow, form stacking
   - Touch targets: minimum 44px (48px preferred)
   - No horizontal scroll on any viewport

2. **Accessibility Compliance (WCAG 2.1 AA)**

   | Area | Actions |
   |------|---------|
   | **Color contrast** | Audit all text/background combos (≥ 4.5:1) |
   | **Focus indicators** | Visible focus ring on all interactive elements |
   | **ARIA labels** | Add to icons, buttons, form fields |
   | **Keyboard navigation** | Tab order logical, no traps |
   | **Screen reader** | Test with VoiceOver/NVDA |
   | **Motion** | Respect `prefers-reduced-motion` |

   - Install: `axe-core` for automated testing
   - Add Storybook a11y addon checks

3. **Loading & Feedback States**

   | State | Implementation |
   |-------|----------------|
   | **Page load** | Skeleton screens for all data sections |
   | **Button actions** | `.btn-loading` spinner + disabled |
   | **Form submit** | Progress indicator + disable form |
   | **Data fetch** | Skeleton → content transition |
   | **Empty state** | Illustration + message + CTA |
   | **Error state** | Alert + retry button |
   | **Success state** | Toast notification (auto-dismiss 5s) |

4. **Visual Regression Test Suite**
   ```
   tests/visual/
   ├── components/          # Every Storybook component
   ├── pages/
   │   ├── admin/           # All admin pages
   │   ├── cpa/             # All CPA pages
   │   ├── web/             # All public pages
   │   └── auth/            # Login, signup, reset
   └── responsive/
       ├── mobile/          # 375px screenshots
       ├── tablet/          # 768px screenshots
       └── desktop/         # 1280px screenshots
   ```

   - CI pipeline: run on every PR
   - Block merge if unapproved visual diff
   - Baseline updates require explicit approval

5. **Performance Optimization**

   | Target | Action |
   |--------|--------|
   | **CSS bundle** | Single `main.css` < 50KB gzipped |
   | **Remove unused** | PurgeCSS to eliminate dead styles |
   | **Critical CSS** | Inline above-fold styles |
   | **Font loading** | `font-display: swap` |
   | **Image optimization** | WebP + lazy loading |

   - Lighthouse score targets: Performance ≥ 90, Accessibility ≥ 95

6. **Cross-Browser Testing**

   | Browser | Versions |
   |---------|----------|
   | Chrome | Latest 2 |
   | Firefox | Latest 2 |
   | Safari | Latest 2 (+ iOS Safari) |
   | Edge | Latest 2 |

   - Use BrowserStack or Playwright for automated cross-browser

7. **Documentation**
   ```
   docs/
   ├── design-system/
   │   ├── tokens.md           # Colors, spacing, typography
   │   ├── components.md       # Component usage guide
   │   ├── patterns.md         # Common UI patterns
   │   └── accessibility.md    # A11y guidelines
   └── storybook/              # Deployed Storybook URL
   ```

8. **Quality Gate (Final)**
   - [ ] All visual regression tests pass
   - [ ] Lighthouse: Performance ≥ 90, Accessibility ≥ 95, Best Practices ≥ 90
   - [ ] Zero WCAG 2.1 AA violations
   - [ ] All pages tested on mobile (real devices)
   - [ ] Cross-browser tests pass
   - [ ] Load test: pages render < 2s under load
   - [ ] Manual walkthrough: complete user journey on each portal
   - [ ] Design system documentation complete

### Robustness Additions
- Error monitoring: Sentry alerts for UI errors
- Performance monitoring: Core Web Vitals dashboard
- Automated accessibility CI checks (fail build on violations)
- Monthly accessibility audit scheduled

---

## File Changes Summary

### Delete (Deprecated)
```
src/web/static/css/themes/admin.css
src/web/static/css/themes/cpa.css
src/web/static/css/unified-theme.css
src/web/templates/cpa_dashboard.html
src/web/templates/cpa_dashboard_refactored.html
src/web/templates/cpa_landing.html
```

### Create (New)
```
src/web/static/css/tokens.css
src/web/static/css/main.css (single entry)
src/web/templates/components/ (20+ partials)
src/web/templates/web/v2/ (migrated templates)
.storybook/ (configuration)
tests/visual/ (regression tests)
docs/design-system/ (documentation)
```

### Modify (Major)
```
src/web/templates/intelligent_advisor.html → split into partials
src/web/templates/cpa/base.html → use components
src/web/templates/admin_*.html → rebuild with components
src/web/config.py → add feature flags
```

---

## Tooling Setup

| Tool | Purpose | Config File |
|------|---------|-------------|
| **Storybook** | Component documentation | `.storybook/main.js` |
| **Percy/Chromatic** | Visual regression | `.percy.yml` or Chromatic CI |
| **Stylelint** | CSS linting | `.stylelintrc.json` |
| **axe-core** | Accessibility testing | Storybook addon + CI |
| **PurgeCSS** | Remove unused CSS | `purgecss.config.js` |
| **Playwright** | Cross-browser testing | `playwright.config.ts` |

---

## CI/CD Integration

```yaml
# .github/workflows/ux-quality.yml
name: UX Quality Checks

on: [pull_request]

jobs:
  lint-css:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run lint:css

  storybook-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run build-storybook
      - run: npm run test:a11y

  visual-regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run build-storybook
      - run: npx percy storybook ./storybook-static

  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run build
      - uses: treosh/lighthouse-ci-action@v10
        with:
          configPath: ./lighthouserc.json
```

---

## Rollback Strategy

| Scenario | Action |
|----------|--------|
| Phase fails review | Revert phase branch, fix, retry |
| Public rollout issues | Set `UX_V2_PERCENTAGE=0` instantly |
| Component breaks | Feature flag individual component |
| Performance regression | Revert to previous CSS bundle |

---

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Design consistency | 68% | 95%+ |
| Lighthouse Performance | Unknown | ≥ 90 |
| Lighthouse Accessibility | Unknown | ≥ 95 |
| Mobile usability | 60% | 100% |
| WCAG violations | Unknown | 0 |
| CSS file count | ~25 | 1 (bundled) |
| Visual regression coverage | 0% | 100% |

---

## Dependencies & Risks

| Risk | Mitigation |
|------|------------|
| Large template refactor breaks flows | Feature flags, gradual rollout |
| Visual regression false positives | Tuned thresholds, manual approval flow |
| Storybook/Jinja2 integration issues | Fallback: render Jinja2 to HTML, test static |
| Team unfamiliar with design system | Documentation + component examples |
| Performance regression from Storybook | Storybook is dev-only, not production |

---

## Estimated Effort

| Phase | Effort |
|-------|--------|
| Phase 1: Foundation | ~3-4 days |
| Phase 2: Components | ~5-7 days |
| Phase 3: Internal | ~5-6 days |
| Phase 4: Public | ~7-10 days |
| Phase 5: Polish | ~5-7 days |
| **Total** | **~25-34 days** |

---

## Next Steps

1. Create feature branch: `feature/ux-polish`
2. Begin Phase 1: CSS audit and consolidation
3. Set up Stylelint for CSS quality gates
4. Capture baseline screenshots of all pages

---

*Plan created: 2026-02-06*
*Last updated: 2026-02-06*
