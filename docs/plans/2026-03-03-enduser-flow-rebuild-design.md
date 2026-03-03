# Design: End-User Flow Visual Rebuild

## Problem

The platform charges CPAs $9,999/yr to white-label an AI tax advisor for their clients. The current UI uses dark navy + teal — looks like an internal enterprise tool, not a consumer-grade tax product. Competing with TurboTax-quality expectations on first impression.

Specific issues:
- Advisory Progress panel renders as a solid teal block (CSS override bug)
- Skeleton loading placeholders never resolve to useful content
- Dark sidebar feels like a developer console, not a financial advisor
- Dashboard link bounces to disconnected Client Portal login
- Color palette doesn't convey "your money is safe and growing"

## Constraints

- **No structural rewrites** — templates stay, only CSS + content fixes
- **White-label model** — CPAs customize logo + firm name only; color system stays consistent
- **8 screens in scope** — end-user flow only (landing through report)
- **Font stays Inter** — already industry-standard (TurboTax uses Avenir, QuickBooks uses Avenir, but Inter is the open-source equivalent)

## Design Decisions

### 1. Color System — Trust Blue + Money Green

Modeled after TurboTax/QuickBooks (blue primary) and H&R Block (green success). These are the proven palettes that global tax SaaS users already trust.

#### Primary Scale (Trust Blue)

| Token | Current | New |
|---|---|---|
| `--color-primary-50` | `#eef3f9` | `#e8f4fd` |
| `--color-primary-100` | `#d4e1f0` | `#bee6f9` |
| `--color-primary-200` | `#a9c3e0` | `#8dd1f4` |
| `--color-primary-300` | `#7ea5d1` | `#54b8ec` |
| `--color-primary-400` | `#5387c1` | `#2098d4` |
| `--color-primary-500` | `#1e3a5f` | `#0077C5` |
| `--color-primary-600` | `#1a3253` | `#006BB3` |
| `--color-primary-700` | `#152b47` | `#005A99` |
| `--color-primary-800` | `#11233b` | `#004A80` |
| `--color-primary-900` | `#0c1b2f` | `#003A66` |
| `--color-primary-950` | `#081620` | `#002B4D` |

#### Accent Scale (Money Green)

| Token | Current | New |
|---|---|---|
| `--color-accent-50` | `#f0fdfa` | `#edfcf2` |
| `--color-accent-100` | `#ccfbf1` | `#d1f7de` |
| `--color-accent-200` | `#99f6e4` | `#a3efbd` |
| `--color-accent-300` | `#5eead4` | `#6de295` |
| `--color-accent-400` | `#2dd4bf` | `#38d16d` |
| `--color-accent-500` | `#14b8a6` | `#14AA40` |
| `--color-accent-600` | `#0d9488` | `#0D8F35` |
| `--color-accent-700` | `#0f766e` | `#0B7A2D` |
| `--color-accent-800` | `#115e59` | `#096524` |
| `--color-accent-900` | `#134e4a` | `#07501C` |

#### Background Warmth

| Token | Current | New | Rationale |
|---|---|---|---|
| `--color-gray-50` | `#f9fafb` (cool) | `#F5F5F0` (warm) | QuickBooks warm-white; reduces eye fatigue |
| `--color-gray-100` | `#f3f4f6` | `#EEEDE8` | Slightly warmer |

Everything else in the gray scale stays — it's already WCAG AA compliant.

#### Semantic Colors

No change. Success green, warning amber, error red, info blue all stay as-is. They're standard.

#### Shadow Updates

| Token | Current | New |
|---|---|---|
| `--shadow-primary` | `rgb(30 58 95 / 0.39)` | `rgb(0 119 197 / 0.25)` |

### 2. Sidebar — Light Theme

Convert the sidebar from dark navy to light. Financial SaaS standard (QuickBooks, FreshBooks, TurboTax all use light or white sidebars on their consumer products).

Changes in `partials/sidebar.html` and sidebar CSS:
- Background: `#FFFFFF` with right border `#E5E7EB`
- Nav text: `--color-gray-700` (dark gray, not white)
- Active item: `--color-primary-50` background + `--color-primary-600` text + left border accent
- Hover: `--color-gray-100` background
- Section labels: `--color-gray-400` uppercase
- User avatar area: subtle `--color-gray-50` background
- Logo area: CPA's logo renders naturally (no dark-mode inversion needed)

### 3. Intelligent Advisor Page Fixes

#### a. Progress Bar (the teal block bug)
Already fixed: scoped `.progress-container .progress-bar` to prevent the chat progress-bar CSS from overriding the sidebar panel's progress bar.

#### b. Side Panel Initial State
Already fixed: replaced infinite skeleton shimmer with helpful text:
- Advisory Progress: "Start a conversation to track your tax profile completion."
- Strategic Recommendations: "Share your income and filing details to receive personalized tax-saving strategies."

#### c. Chat Area Theme
- AI message bubbles: light blue-50 background (not gray)
- User message bubbles: `--color-primary-500` blue (not teal)
- Savings callout: green accent border + green text for dollar amounts
- "Getting Started" badge: blue pill instead of gray

#### d. Stepper (Journey Steps)
- Active step: `--color-primary-500` blue circle + bold label
- Completed step: `--color-accent-500` green checkmark
- Future step: `--color-gray-300` muted circle
- Connector line between steps: green when completed, gray when pending

### 4. Landing Page

- Hero CTA buttons: `--color-primary-500` blue primary, `--color-accent-500` green secondary
- Trust badges (security, encryption): blue outlines, not teal
- Savings numbers: green text (`--color-accent-500`)
- Background: warm white `#F5F5F0`

### 5. Auth Pages (Login, Signup)

- Primary button: `--color-primary-500` blue
- Link text: `--color-primary-600`
- Form card: white on warm-white background
- Logo area at top: CPA's logo (white-label)

### 6. Results Page

- Refund/savings amount: large green text (`--color-accent-500`)
- "Potential Savings" card: green-50 background with green border
- Action buttons: blue primary CTAs
- Status badges: green for complete, blue for in-progress, gray for pending

### 7. Scenarios Page

- Comparison cards: white cards on warm background
- "Better" scenario highlight: green left border + green savings delta
- Active/selected scenario: blue outline

### 8. Advisory Report Preview

- Header bar: `--color-primary-500` blue
- Savings highlights: green
- CPA branding area: logo + firm name (from white-label config)
- Download button: blue primary
- Professional disclaimer: gray-500 text

### 9. Dashboard Link Fix
Already fixed: sidebar "Dashboard" now routes to `/app` (role-based router) instead of `/app/portal` (which bounced to Client Portal login for unauthenticated users).

## White-Label Integration

CPAs customize via branding settings:
- **Logo** — displayed in sidebar header, report headers, landing page
- **Firm name** — displayed in sidebar brand text, report headers
- **Contact info** — phone, email shown in "Talk to CPA" modals

Colors, fonts, layout are NOT customizable. This ensures every CPA's version looks premium.

## Implementation Approach

1. **variables.css** — Swap color tokens (primary + accent + gray-50/100 + shadow)
2. **Sidebar CSS** — Light theme overhaul
3. **intelligent-advisor.css** — Chat bubble colors, stepper colors
4. **Template tweaks** — Already done (progress bar fix, skeleton replacement, dashboard link)
5. **Landing/auth/results CSS** — Minor token-dependent updates (most will auto-update from variable changes)

## Verification

- All 8 screens render with new colors
- WCAG 2.1 AA contrast ratios maintained
- Sidebar is readable in light theme
- CPA logo renders cleanly on white sidebar
- No broken layouts from color changes
- Route count stays at 1080
