# Phase 1: CSS Audit Report

**Generated**: 2026-02-06
**Branch**: phase-1-foundation

---

## CSS File Inventory (22 files)

### Core (5 files) - KEEP
| File | Purpose | Status |
|------|---------|--------|
| `core/variables.css` | Design tokens (CANONICAL) | Keep - Primary source |
| `core/reset.css` | CSS normalize | Keep |
| `core/typography.css` | Font styles | Keep |
| `core/layout.css` | Flexbox/Grid utilities | Keep |
| `core/animations.css` | Transitions/keyframes | Keep |

### Components (7 files) - KEEP
| File | Purpose | Status |
|------|---------|--------|
| `components/buttons.css` | Button variants | Keep |
| `components/cards.css` | Card components | Keep |
| `components/forms.css` | Form elements | Keep |
| `components/modals.css` | Modals/dialogs | Keep |
| `components/navigation.css` | Nav/sidebar | Keep |
| `components/tables.css` | Table styles | Keep |
| `components/toast.css` | Notifications | Keep |

### Pages (3 files) - KEEP
| File | Purpose | Status |
|------|---------|--------|
| `pages/advisor.css` | Advisor page | Keep |
| `pages/cpa-dashboard.css` | CPA dashboard | Keep |
| `pages/tax-form.css` | Tax form | Keep |

### Themes (3 files) - DEPRECATED
| File | Purpose | Status |
|------|---------|--------|
| `themes/admin.css` | Admin dark theme | **DELETE** - Merged to variables.css |
| `themes/advisor.css` | Advisor theme | Keep (review) |
| `themes/cpa.css` | CPA theme | **DELETE** - Merged to variables.css |

### Root Level (4 files)
| File | Purpose | Status |
|------|---------|--------|
| `main.css` | Entry point | Keep - Refactor |
| `unified-theme.css` | Bridge file | **DELETE** - No longer needed |
| `advisory-report.css` | Report styles | Keep |
| `chatbot-ux-enhancements.css` | Chatbot UX | Keep |

---

## Variable Naming Schemes (3 Found)

### Scheme 1: Design System (CANONICAL)
Location: `core/variables.css`

```css
/* Colors */
--color-primary-500: #1e3a5f;
--color-accent-500: #14b8a6;
--color-gray-200: #e5e7eb;
--color-success-500: #10b981;
--color-warning-500: #f59e0b;
--color-error-500: #ef4444;

/* Spacing */
--space-4: 1rem;

/* Typography */
--text-base: 1rem;

/* Radius */
--radius-lg: 0.5rem;
```

### Scheme 2: Legacy/Bridge
Location: `unified-theme.css`

```css
/* Maps short names to design system */
--primary: var(--color-primary-500);
--accent: var(--color-accent-500);
--gray-200: var(--color-gray-200);
--success: var(--color-success-500);
--warning: var(--color-warning-500);
--error: var(--color-error-500);
--white: #ffffff;
--border-color: var(--color-gray-200);
--text-muted: var(--color-gray-500);
```

### Scheme 3: Inline Template Overrides
Location: Various templates (inline `<style>` blocks)

| Template | Override | Current Value | Target Value |
|----------|----------|---------------|--------------|
| `intelligent_advisor.html` | `--accent` | `#2b6cb0` (blue) | `#14b8a6` (teal) |
| `intelligent_advisor.html` | `--accent-gold` | `#c69214` | REMOVE |
| `intelligent_advisor.html` | `--warning` | `#c69214` | `#f59e0b` |
| `client_portal.html` | `--accent` | `#059669` (green) | `#14b8a6` (teal) |
| `admin_dashboard.html` | `--accent` | `#0d9488` | `#14b8a6` (teal) |
| `cpa_dashboard.html` | `--accent` | `#5387c1` | `#14b8a6` (teal) |
| `test_auth.html` | `--accent` | `#1e3a5f` (navy) | `#14b8a6` (teal) |
| `smart_tax.html` | `--accent` | `#10b981` | `#14b8a6` (teal) |
| `landing.html` | `--warning` | `#c69214` | `#f59e0b` |
| `quick_estimate.html` | `--warning` | `#c69214` | `#f59e0b` |
| `advisory_report_preview.html` | `--warning` | `#c69214` | `#f59e0b` |

---

## Template CSS Import Analysis

### Templates using `unified-theme.css`: 48 files
All templates import via:
```html
<link rel="stylesheet" href="/static/css/unified-theme.css">
```

### Templates using `themes/admin.css`: 1 file
- `partials/head_styles.html` (conditional)

### Templates using `themes/cpa.css`: 2 files
- `partials/head_styles.html` (conditional)
- `cpa_dashboard_refactored.html`

---

## Deprecated Templates to Delete

| Template | Reason | Replacement |
|----------|--------|-------------|
| `cpa_dashboard.html` | Legacy version | `cpa/dashboard.html` |
| `cpa_dashboard_refactored.html` | Intermediate version | `cpa/dashboard.html` |
| `cpa_landing.html` | Unused | None |

---

## Non-Standard Colors to Fix

### Gold (`#c69214`) - 14 occurrences in `intelligent_advisor.html`
- Lines: 21, 24, 37, 398, 1828, 2050, 2360, 4573, 12640, 13739
- Action: Replace with `--color-warning-500` (#f59e0b) or remove

### Blue (`#2b6cb0`) - 6 occurrences in `intelligent_advisor.html`
- Lines: 19, 374, 386, 2399, 13739
- Action: Replace with `--color-accent-500` (#14b8a6)

---

## Migration Strategy

### Step 1: Add legacy variable mappings to `variables.css`
Move bridge variables from `unified-theme.css` to `variables.css` temporarily.

### Step 2: Update template imports
Replace: `unified-theme.css` → `variables.css`

### Step 3: Fix inline accent colors
Search/replace all non-standard `--accent` values → `#14b8a6`

### Step 4: Delete deprecated files
- `themes/admin.css`
- `themes/cpa.css`
- `unified-theme.css`
- `cpa_dashboard.html`
- `cpa_dashboard_refactored.html`
- `cpa_landing.html`

### Step 5: Remove bridge variables
After all templates updated, remove legacy mappings from `variables.css`

---

## Files to Modify

### CSS Files
1. `core/variables.css` - Add legacy bridge (temporary)
2. `main.css` - Update to be single entry point
3. Delete: `unified-theme.css`, `themes/admin.css`, `themes/cpa.css`

### Templates (inline style fixes)
1. `intelligent_advisor.html` - Fix 20+ color references
2. `client_portal.html` - Fix accent
3. `admin_dashboard.html` - Fix accent
4. `cpa_dashboard.html` - DELETE
5. `cpa_dashboard_refactored.html` - DELETE
6. `test_auth.html` - Fix accent
7. `smart_tax.html` - Fix accent
8. `landing.html` - Fix warning color
9. `quick_estimate.html` - Fix warning color
10. `advisory_report_preview.html` - Fix warning color
11. `partials/head_styles.html` - Remove theme imports

---

*Report generated for Phase 1 of UX Polish initiative*
