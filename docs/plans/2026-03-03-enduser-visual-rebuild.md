# End-User Visual Rebuild — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the end-user flow from dark-enterprise to TurboTax-grade "Trust Blue + Money Green" — CSS variable swap, light sidebar, fixed broken states. No template rewrites.

**Architecture:** All color changes flow through CSS custom properties in `variables.css`. The sidebar theme is controlled by `navigation.css`. Chat/stepper styles live in `intelligent-advisor.css`. Changing tokens cascades to all 8 screens automatically.

**Tech Stack:** CSS custom properties, Jinja2 templates, existing Inter font stack.

---

### Task 1: Swap Color Tokens in variables.css

**Files:**
- Modify: `src/web/static/css/core/variables.css:14-37` (primary + accent scales)
- Modify: `src/web/static/css/core/variables.css:45-50` (gray-50 + gray-100 warmth)
- Modify: `src/web/static/css/core/variables.css:207` (shadow-primary)

**Step 1: Replace primary color scale (Trust Blue)**

Replace lines 14-25 in `variables.css`:

```css
  /* Primary Colors (Trust Blue) */
  --color-primary-50: #e8f4fd;
  --color-primary-100: #bee6f9;
  --color-primary-200: #8dd1f4;
  --color-primary-300: #54b8ec;
  --color-primary-400: #2098d4;
  --color-primary-500: #0077C5;
  --color-primary-600: #006BB3;
  --color-primary-700: #005A99;
  --color-primary-800: #004A80;
  --color-primary-900: #003A66;
  --color-primary-950: #002B4D;
```

**Step 2: Replace accent color scale (Money Green)**

Replace lines 27-37 in `variables.css`:

```css
  /* Secondary/Accent Colors (Money Green) */
  --color-accent-50: #edfcf2;
  --color-accent-100: #d1f7de;
  --color-accent-200: #a3efbd;
  --color-accent-300: #6de295;
  --color-accent-400: #38d16d;
  --color-accent-500: #14AA40;
  --color-accent-600: #0D8F35;
  --color-accent-700: #0B7A2D;
  --color-accent-800: #096524;
  --color-accent-900: #07501C;
```

**Step 3: Warm the page background**

Replace lines 45-46 in `variables.css`:

```css
  --color-gray-50: #F5F5F0;   /* Warm white page background (QuickBooks-style) */
  --color-gray-100: #EEEDE8;  /* Warm light gray */
```

**Step 4: Update shadow-primary**

Replace line 207 in `variables.css`:

```css
  --shadow-primary: 0 4px 14px 0 rgb(0 119 197 / 0.25);
```

**Step 5: Verify**

Open any page in browser. Primary buttons should be blue (#0077C5), accents green (#14AA40), page background warm-white (#F5F5F0).

**Step 6: Commit**

```bash
git add src/web/static/css/core/variables.css
git commit -m "style: swap color tokens to Trust Blue + Money Green"
```

---

### Task 2: Convert Sidebar to Light Theme

**Files:**
- Modify: `src/web/static/css/components/navigation.css:79-90` (sidebar base)
- Modify: `src/web/static/css/components/navigation.css:153-160` (sidebar header)
- Modify: `src/web/static/css/components/navigation.css:175-178` (brand text)
- Modify: `src/web/static/css/components/navigation.css:185-198` (toggle button)
- Modify: `src/web/static/css/components/navigation.css:215-222` (section labels)
- Modify: `src/web/static/css/components/navigation.css:239-261` (nav items)
- Modify: `src/web/static/css/components/navigation.css:335-338` (sidebar footer)
- Modify: `src/web/static/css/components/navigation.css:348-362` (user menu trigger)
- Modify: `src/web/static/css/components/navigation.css:364-374` (user avatar)
- Modify: `src/web/static/css/components/navigation.css:390-end` (user dropdown)

**Step 1: Sidebar base — white background**

```css
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: var(--sidebar-width);
  background: var(--sidebar-bg, #FFFFFF);
  border-right: 1px solid var(--color-gray-200);
  z-index: var(--z-modal);
  display: flex;
  flex-direction: column;
  transition: transform var(--transition-base), width var(--transition-base);
}
```

**Step 2: Sidebar header — light border**

```css
.sidebar-header {
  height: var(--header-height);
  padding: 0 var(--space-4);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-gray-200);
  flex-shrink: 0;
}
```

**Step 3: Brand text — dark color**

```css
.sidebar-brand-text {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-gray-900);
}
```

**Step 4: Toggle button — light hover**

```css
.sidebar-toggle {
  width: var(--space-8);
  height: var(--space-8);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--color-gray-500);
  transition: all var(--transition-fast);
}

.sidebar-toggle:hover {
  background: var(--color-gray-100);
  color: var(--color-gray-700);
}
```

**Step 5: Section labels — subtle gray**

```css
.nav-section-label {
  padding: 0 var(--space-5);
  margin-bottom: var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--color-gray-400);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wider);
}
```

**Step 6: Nav items — light theme with blue active state**

```css
.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2-5) var(--space-5);
  margin: var(--space-0-5) var(--space-3);
  border-radius: var(--radius-lg);
  color: var(--color-gray-600);
  text-decoration: none;
  transition: all var(--transition-fast);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.nav-item:hover {
  background: var(--color-gray-100);
  color: var(--color-gray-900);
}

.nav-item.active {
  background: var(--color-primary-50);
  color: var(--color-primary-600);
  font-weight: var(--font-semibold);
}
```

**Step 7: Nav icon — inherit color from parent**

```css
.nav-icon svg,
.nav-icon .icon {
  width: 100%;
  height: 100%;
  stroke: currentColor;
}
```

**Step 8: Sidebar footer — light border**

```css
.sidebar-footer {
  padding: var(--space-4);
  border-top: 1px solid var(--color-gray-200);
}
```

**Step 9: User menu trigger — light theme**

```css
.user-menu-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-lg);
  color: var(--color-gray-700);
  text-align: left;
  transition: background var(--transition-fast);
}

.user-menu-trigger:hover {
  background: var(--color-gray-100);
}
```

**Step 10: User avatar — primary blue on light**

```css
.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  background: var(--color-primary-500);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  flex-shrink: 0;
}
```

**Step 11: User dropdown — light background**

Find the `.user-dropdown` block and update background/border:

```css
.user-dropdown {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid var(--color-gray-200);
  border-radius: var(--radius-xl);
  padding: var(--space-2);
  box-shadow: var(--shadow-lg);
  margin-bottom: var(--space-2);
}

.user-dropdown a {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--color-gray-700);
  text-decoration: none;
  font-size: var(--text-sm);
  transition: background var(--transition-fast);
}

.user-dropdown a:hover {
  background: var(--color-gray-100);
  color: var(--color-gray-900);
}
```

**Step 12: Verify**

Open the intelligent advisor page. Sidebar should be white with blue active state, dark text, clean borders. CPA logo should render naturally without inversion.

**Step 13: Commit**

```bash
git add src/web/static/css/components/navigation.css
git commit -m "style: convert sidebar to light theme"
```

---

### Task 3: Update Sidebar Icon Colors in Template

**Files:**
- Modify: `src/web/templates/partials/sidebar.html` (icon color inheritance)

**Step 1: Update the sidebar icon macro**

The sidebar currently uses `{{ icon('name', 'sm') }}` which renders SVG icons. These SVGs use `stroke: currentColor` so they should inherit from the parent `.nav-item` color automatically after the CSS changes in Task 2.

Verify by checking that the `macros/icons.html` template outputs SVGs with `stroke="currentColor"`. If it does, no template change needed — the CSS color changes will cascade.

**Step 2: Update mobile header colors**

In `partials/sidebar.html`, the mobile header at line 107 uses `mobile-header`. Check if this has hardcoded dark colors and update the CSS if needed.

**Step 3: Verify**

Desktop + mobile sidebar both render with correct light theme colors.

**Step 4: Commit (if changes needed)**

```bash
git add src/web/templates/partials/sidebar.html
git commit -m "style: update sidebar template for light theme"
```

---

### Task 4: Update Chat Bubbles and Stepper Colors

**Files:**
- Modify: `src/web/static/css/pages/intelligent-advisor.css:418` (AI avatar bg)
- Modify: `src/web/static/css/pages/intelligent-advisor.css:450-454` (AI bubble)
- Modify: `src/web/static/css/pages/intelligent-advisor.css:461-466` (user bubble)
- Modify: `src/web/static/css/pages/intelligent-advisor.css:1934-1967` (stepper states)
- Modify: `src/web/static/css/pages/intelligent-advisor.css:1970-1975` (phase indicator)

**Step 1: AI bubble — light blue tint instead of gray**

Replace `.message.ai .bubble` (line 450):

```css
    .message.ai .bubble {
      background: var(--color-primary-50);
      border: 1px solid var(--color-primary-100);
      color: var(--color-gray-900);
      box-shadow: var(--shadow-sm);
    }
```

**Step 2: Update stepper completed state — use accent green**

Replace `.journey-step.completed .step-icon` (line 1944):

```css
    .journey-step.completed .step-icon {
      background: var(--color-accent-500);
      border-color: var(--color-accent-500);
    }
```

And `.journey-step.completed .step-label` (line 1966):

```css
    .journey-step.completed .step-label {
      color: var(--color-accent-600);
    }
```

**Step 3: Fix phase indicator — remove hardcoded rgba, use token**

Replace `.phase-indicator` (line 1971):

```css
    .phase-indicator {
      text-align: center;
      padding: var(--space-3) var(--space-6);
      background: var(--color-primary-50);
      border-bottom: 1px solid var(--color-gray-200);
    }
```

**Step 4: Update stepper active shadow — use new blue**

Replace `.journey-step.active .step-icon` (line 1934):

```css
    .journey-step.active .step-icon {
      background: var(--color-primary-500);
      border-color: var(--color-primary-500);
      box-shadow: 0 2px 8px rgb(0 119 197 / 0.3);
    }
```

**Step 5: Verify**

Load the intelligent advisor page. AI bubbles should have light blue tint. Stepper completed steps should be green. Active step should be blue.

**Step 6: Commit**

```bash
git add src/web/static/css/pages/intelligent-advisor.css
git commit -m "style: update chat bubbles and stepper to Trust Blue + Money Green"
```

---

### Task 5: Fix "Start Guided Analysis" Button — Primary CTA Green

**Files:**
- Modify: `src/web/static/css/pages/intelligent-advisor.css:493-513` (quick-action buttons)

The primary CTA "Start Guided Analysis" should use the accent green to signal "go/start/money." Secondary actions ("Upload Documents", "Learn More") stay outlined blue.

**Step 1: Add a `.quick-action.primary` class**

After the existing `.quick-action:active` block (line 518), add:

```css
    .quick-action.primary {
      background: var(--color-accent-500);
      border-color: var(--color-accent-500);
      color: white;
    }

    .quick-action.primary:hover {
      background: var(--color-accent-600);
      border-color: var(--color-accent-600);
      color: white;
      transform: translateY(-2px);
      box-shadow: 0 4px 14px rgb(20 170 64 / 0.3);
    }
```

**Step 2: Update template — add primary class to first button**

In `src/web/templates/intelligent_advisor.html`, find the "Start Guided Analysis" button and add the `primary` class. Search for `Start Guided Analysis` in the template.

**Step 3: Verify**

"Start Guided Analysis" should be solid green. "Upload Documents" and "Learn More" should be outlined blue.

**Step 4: Commit**

```bash
git add src/web/static/css/pages/intelligent-advisor.css src/web/templates/intelligent_advisor.html
git commit -m "style: green primary CTA for Start Guided Analysis"
```

---

### Task 6: Update Landing Page Colors

**Files:**
- Modify: `src/web/templates/landing.html` (inline styles referencing old colors)

**Step 1: Search for hardcoded color values**

Search `landing.html` for any hardcoded hex values like `#1e3a5f`, `#14b8a6`, `#0d9488`, `#1a3253`. Replace with CSS variable references or new hex values:

- `#1e3a5f` → `var(--color-primary-500)` or `#0077C5`
- `#14b8a6` → `var(--color-accent-500)` or `#14AA40`
- `#0d9488` → `var(--color-accent-600)` or `#0D8F35`

**Step 2: Update savings/refund display colors**

Any dollar amounts showing savings should use `var(--color-accent-500)` (green).

**Step 3: Verify**

Landing page hero, CTAs, and trust badges should all reflect new blue/green palette.

**Step 4: Commit**

```bash
git add src/web/templates/landing.html
git commit -m "style: update landing page to Trust Blue + Money Green"
```

---

### Task 7: Update Auth Pages

**Files:**
- Modify: `src/web/templates/auth/login.html` (hardcoded colors)
- Modify: `src/web/templates/auth/signup.html` (hardcoded colors)

**Step 1: Search for hardcoded color values in auth templates**

Replace any inline `#1e3a5f`, `#14b8a6`, `#1a3253`, `#0d9488` with CSS variable references. Primary buttons should use `var(--color-primary-500)`.

**Step 2: Verify**

Login and signup pages should show blue primary buttons, clean white card on warm background.

**Step 3: Commit**

```bash
git add src/web/templates/auth/login.html src/web/templates/auth/signup.html
git commit -m "style: update auth pages to Trust Blue + Money Green"
```

---

### Task 8: Update Results and Scenarios Pages

**Files:**
- Modify: `src/web/templates/results.html` (hardcoded colors)
- Modify: `src/web/templates/scenarios.html` (hardcoded colors)

**Step 1: Search for hardcoded color values**

Replace `#1e3a5f`, `#14b8a6`, etc. Savings/refund amounts should be green (`var(--color-accent-500)`). Action buttons should be blue (`var(--color-primary-500)`).

**Step 2: Verify**

Results page shows green savings numbers and blue action buttons. Scenarios comparison cards are clean with blue selected states.

**Step 3: Commit**

```bash
git add src/web/templates/results.html src/web/templates/scenarios.html
git commit -m "style: update results and scenarios pages to Trust Blue + Money Green"
```

---

### Task 9: Update Quick Estimate and Lead Magnet Pages

**Files:**
- Modify: `src/web/templates/quick_estimate.html` (hardcoded colors)
- Modify: `src/web/templates/lead_magnet/quick_estimate.html` (hardcoded colors)
- Modify: `src/web/templates/lead_magnet/savings_teaser.html` (hardcoded colors)
- Modify: `src/web/templates/lead_magnet/tier1_report.html` (hardcoded colors)

**Step 1: Search for hardcoded color values**

Replace old navy/teal hex values with new blue/green. Savings amounts green, CTAs blue.

**Step 2: Verify**

Quick estimate flow and lead magnet pages use new palette.

**Step 3: Commit**

```bash
git add src/web/templates/quick_estimate.html src/web/templates/lead_magnet/
git commit -m "style: update quick estimate and lead magnet pages to Trust Blue + Money Green"
```

---

### Task 10: Final Verification Pass

**Step 1: Visual smoke test**

Open each of the 8 screens in browser and verify:
- [ ] Landing page — blue CTAs, green savings, warm background
- [ ] Login/Signup — blue primary buttons, clean cards
- [ ] Intelligent Advisor — light sidebar, blue chat bubbles, green stepper completed, green primary CTA
- [ ] Quick Estimate — blue/green palette
- [ ] Results — green savings numbers, blue actions
- [ ] Scenarios — blue selected states
- [ ] Advisory Report — blue header bar

**Step 2: Contrast check**

Verify text on new backgrounds meets WCAG 2.1 AA (4.5:1 for normal text):
- `#0077C5` on `#FFFFFF` → 4.56:1 ✓ (AA pass)
- `#14AA40` on `#FFFFFF` → 3.31:1 ✗ (use for large text/icons only, not body text)
- `#006BB3` on `#FFFFFF` → 5.28:1 ✓ (AA pass for button text)
- `#0D8F35` on `#FFFFFF` → 4.15:1 ✓ for large text (use `#0B7A2D` for small text → 5.2:1)

Note: Green accent should be used for large numbers, badges, and icons. For small green text, use `--color-accent-700` (#0B7A2D) to maintain contrast.

**Step 3: Route count verification**

```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
import os; os.environ.setdefault('OPENAI_API_KEY', 'sk-test'); os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-test'); os.environ.setdefault('GOOGLE_AI_API_KEY', 'test')
from web.app import app
print(f'Routes: {len(list(app.routes))}')
"
```

Expected: `Routes: 1080`

**Step 4: Final commit**

```bash
git add -A
git commit -m "style: complete end-user visual rebuild — Trust Blue + Money Green"
```
