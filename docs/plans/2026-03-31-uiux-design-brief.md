# UI/UX Design Brief — AI Tax Advisor Platform
**Date:** March 31, 2026
**Version:** 1.0
**For:** Senior UI/UX Designer
**Prepared by:** Product & Engineering

---

## 1. Product Context

AI Tax Advisor is a tax SaaS platform targeting **$1M ARR**. It serves two distinct audiences:

| Audience | Entry Point | Goal |
|----------|-------------|------|
| **Consumers** | `/intelligent-advisor`, `/lead-magnet` | Get a free, personalized tax strategy |
| **CPA Firms** | `/for-cpas`, `/cpa/dashboard` | White-label lead capture & client management |

**Tech stack:** FastAPI + Jinja2 templates, Alpine.js, vanilla JS modules. No React.
**Design tokens (already in code, must be preserved):**
- `--navy: #0B1D3A` — primary brand color
- `--gold: #C9A84C` — accent, CTAs, highlights
- `--font-heading: 'Playfair Display', serif` — all h1/h2
- `--font-body: 'DM Sans', sans-serif` — all body copy
- `--font-display: 'Plus Jakarta Sans', sans-serif` — stat values, data
- Amber/parchment palette in advisor: `#1a1a18` charcoal, `#faf9f6` parchment, `#c4975a` amber

**Design philosophy:** "Quiet authority. Bloomberg Terminal meets private wealth advisor."
Not chatbot-generic. Not fintech startup. Premium, precise, trustworthy.

---

## 2. Primary Screen: Intelligent Advisor (`/intelligent-advisor`)

This is the crown jewel. A consumer's first real interaction with the product. Every design decision here directly impacts conversion to the lead magnet and report flow.

### 2.1 Progress Indicator

**Current state:** A gold progress bar + "X% Complete" text exists in code but only shows after the first API response. Users have no initial orientation.

**Required design:**
- Slim 4px gold bar directly above the messages area (not page top)
- Label: `"Question 3 of ~12 · Income"` — question count + current topic phase
- Topic phases: Income → Deductions → Retirement → Business → Review
- Bar animates smoothly (CSS transition: 0.5s ease)
- On mobile: label truncates to `"3 of ~12"`, bar stays full width
- Before first answer: bar hidden (not 0% — hidden entirely, shows on first response)

**Phases and color:**
- Income (0–25%): amber
- Deductions (25–50%): amber
- Retirement (50–75%): gold
- Business/Entity (75–90%): gold
- Review/Complete (90–100%): green (`#16a34a`)

### 2.2 Question Branching Transitions

**Current state:** Messages append sequentially with no visual grouping between phases.

**Required design:**
- When transitioning between phases (income → deductions), insert a visual "phase divider":
  - Thin horizontal rule
  - Phase label centered: `"Now: Deductions & Credits →"`
  - Subtle fade-in animation
- Within a phase, messages flow naturally
- The divider should feel like turning a page in a document, not a hard break

### 2.3 Strategy Card Hierarchy

**Current state:** Free / locked / CPA-recommended / unlocked tiers exist but visual hierarchy between them is unclear. Locked cards look like error states.

**Required design for each tier:**

| Tier | Visual Treatment |
|------|-----------------|
| **Free / DIY** | White card, navy border, "DIY" badge in slate |
| **Locked / Premium** | Soft blurred overlay (not full black), gold lock icon, "CPA-Recommended" badge in gold, subtle gold border. Should feel *desirable*, not broken. CTA: "Unlock Full Analysis →" links to `/upgrade` |
| **Unlocked** | White card, green checkmark badge, "Unlocked" in green |
| **CPA-Recommended** | Navy background card, white text, gold "★ CPA Pick" badge — visually premium |

**Lock overlay spec:**
- Background: `rgba(255,255,255,0.85)` blur backdrop (not solid)
- Gold lock icon (24px, centered)
- Text: `"This strategy requires a CPA consultation"`
- CTA button: gold fill, navy text, `"See How to Unlock →"`
- Hover: CTA scales up 1.02, cursor pointer

### 2.4 The Hero Moment — Savings Reveal

**Current state:** Savings total appears in a sticky banner but the reveal feels quiet.

**Required design:**
- When the first savings estimate is calculated, trigger a 2-second sequence:
  1. Live savings banner pulses gold (3 rings, expanding, 0.7s each)
  2. A toast appears center-screen: `"💰 We found $X,XXX in potential savings"`
  3. Confetti fires (already built — `CelebrationSystem.triggerConfetti()`)
  4. Strategy cards fade in below the calculation message
- The savings number in the banner should use a counter animation (count up from 0 to final value over 1.5s)
- On mobile: banner moves above the input area, not over the keyboard

### 2.5 Report Delivery (`/results`)

**Current state:** Results page renders as a web page with HTML sections.

**Required design:**
- The entire results content area should feel like a printed tax document:
  - White background, max-width 760px, centered
  - Subtle drop shadow (`0 2px 12px rgba(0,0,0,0.08)`)
  - CPA letterhead at top: firm logo, firm name, "Tax Analysis Report", date line, horizontal rule
  - Section headers use Playfair Display: "1. Tax Liability Summary", "2. Optimization Strategies", "3. Recommended Actions", "4. Next Steps"
  - Numbered sections with thin left border in gold
  - Page-break-before CSS on major sections (for print)
  - "Download PDF" button: navy button, printer icon, top-right position
  - Footer: CPA contact, disclaimer in 11px gray

### 2.6 Mobile-First Advisor Layout

**Current state:** On mobile, the sticky savings banner (fixed bottom-right) overlaps the keyboard and chat input.

**Required spec:**
- Savings banner position:
  - Desktop: fixed bottom-right, 20px from edges
  - Mobile (`max-width: 640px`): fixed top, full-width bar, height 44px, below the advisor header
  - When keyboard opens (viewport resize event): banner hides, re-shows when keyboard closes
- Input area: always pinned to the very bottom of the viewport on mobile, not scrollable away
- Quick-action buttons: horizontally scrollable row on mobile, no wrapping

### 2.7 Edit / Back Flow

**Current state:** No way to revise a previous answer without retyping.

**Required design:**
- On hover of any user message bubble: show a small `"Edit"` button (pencil icon, 14px, slate color) in the top-right corner
- Click → message content becomes editable inline
- Confirm with Enter or a small checkmark button
- On confirm: message updates + a new AI message appears: `"Got it — I've updated [field]. Let me recalculate..."`
- Do NOT re-run the full conversation — only send the corrected data point

### 2.8 Upload Confirmation Card

**Current state:** File uploads show a progress bar. After OCR, the result isn't shown to the user for confirmation.

**Required design:**
- After OCR extraction, show a confirmation card in the chat:
  ```
  ┌─────────────────────────────────────┐
  │  📄 W-2 from Employer Name          │
  │  ─────────────────────────────────  │
  │  Wages: $87,500                     │
  │  Federal withholding: $14,200       │
  │  State: California                  │
  │  [Edit] [Looks right → Continue]   │
  └─────────────────────────────────────┘
  ```
- "Edit" toggles individual fields to inline-editable inputs
- "Looks right → Continue" confirms data and advances the flow
- If extraction failed: show `"We couldn't read this document clearly. Enter manually?"` with a mini form

### 2.9 Voice Input UI

**Current state:** Voice recording indicator and transcript CSS exist but no backend endpoint is wired.

**Required design (UI only — for future wiring):**
- Mic button in the input bar (right of send button)
- States: idle (mic icon), recording (pulsing red dot + "Listening..."), processing (spinner)
- Transcript appears as typed text in the input field character by character
- If transcript is uncertain: show confidence indicator (`"Did you mean: ..."`)
- Correction flow: user can edit transcript before sending

---

## 3. Lead Magnet Funnel (`/lead-magnet/*`)

### 3.1 Landing Page (`/lead-magnet/`)

**Required:**
- Above-fold must contain within 600px viewport height:
  - Urgency chip: `"⏰ 15 days until April 15 filing deadline"` (dynamic, gold pill)
  - H1: Direct, money-focused (e.g., "Find Out What the IRS Owes You")
  - Subhead: 1 sentence, specific
  - Primary CTA button: large (56px height), gold, "Get My Free Tax Estimate →"
  - Social proof: `"Used by 500+ CPAs to qualify clients"` or similar
- Below fold: How it works (3 steps, icons), example savings scenarios

### 3.2 Teaser Page (`/lead-magnet/teaser`)

**Current problem:** Savings range too wide, feels made up.

**Required:**
- Contextualize the range: `"Freelancers in California with $95K income typically find $3,200–$7,800 in strategies"`
- Show a "Tax Health Score" dial (0–100, animated fill on load):
  - 0–40: red
  - 41–70: amber
  - 71–100: green
- Show 2–3 category hints (blurred): "Entity Structure", "Retirement Contributions", "Home Office"
- Each hint has a `"Unlock to see"` overlay
- CTA: `"Unlock Your Full Analysis →"` (not "Get Report" — implies action and reward)

### 3.3 Contact Capture Page (`/lead-magnet/contact`)

**Current problem:** User doesn't know what happens after they submit.

**Required:**
- Add a "What you'll receive" panel beside the form:
  ```
  ✓ Personalized tax strategy report (PDF-ready)
  ✓ Top 3–5 savings opportunities with $ estimates
  ✓ Action checklist with deadlines
  ✓ Direct contact with [CPA firm name]
  ```
- Privacy line below form: `"We never sell your data. Unsubscribe anytime."`
- After submit: show inline `"Generating your report..."` with 2s animated loader before redirect

### 3.4 Tier 1 Report (`/lead-magnet/report`)

**Current state:** Partially polished (document header + download button added in this sprint).

**Required additional work:**
- Report must look like a real tax document when printed (white background, letterhead, numbered sections)
- Each strategy item: clear before/after presentation
  ```
  Home Office Deduction
  Current: Not claimed
  Potential saving: $2,400/year
  Confidence: High ★★★
  Action: Document sq footage, calculate % of home
  ```
- "Download Full Analysis" CTA at bottom: opens `/lead-magnet/analysis` or shows upgrade gate
- Section labels: "Findings" not "Strategies", "Action Items" not "Next Steps"

### 3.5 Tier 2 Locked Page (`/lead-magnet/locked`)

**Current state:** Template exists, now has a route. Needs compelling design.

**Required:**
- Show the full Tier 2 report *blurred* behind a frosted glass overlay
- Overlay content:
  - Lock icon (gold, 40px)
  - Headline: `"Your Full Analysis Is Ready"`
  - Subhead: `"Schedule a 20-minute call with [CPA name] to unlock all [X] strategies"`
  - Two CTAs: `"Schedule Free Consultation"` (gold, primary) and `"Enter Your Email to Preview"` (text link)
- Blurred content should show enough to be tantalizing: strategy titles, savings numbers
- Trust signals: `"No obligation · 20 minutes · Free"`

---

## 4. CPA Dashboard

### 4.1 Analytics Page (`/cpa/analytics`)

**Required KPI cards (top row):**
- Pipeline Value ($): sum of estimated savings across all active leads
- Lead Conversion Rate (%): leads → clients this month
- Avg Savings per Client ($): across closed clients
- Team Utilization (%): tasks completed / tasks assigned this week

**Charts (below KPIs):**
- Lead funnel (horizontal bar: new → contacted → qualified → proposal → closed)
- Revenue trend (12-month line chart: monthly closed deal value)
- Lead source breakdown (donut: organic, referral, advisor embed, direct)

**Design:** Dark card headers (navy), white body, gold accent on numbers. No gradients on charts — flat, clean.

### 4.2 Leads Pipeline / Kanban

**Columns:** New Leads → Contacted → Qualified → Proposal Sent → Closed Won
**Card design:**
- Lead name + initials avatar
- Savings estimate badge (gold pill)
- Temperature dot (hot = red, warm = amber, cold = blue)
- Days in stage counter (red if >7 days)
- Quick actions on hover: `"Email"` `"Call"` `"Move →"`

**Drag-and-drop:** Cards draggable between columns. On drop: PATCH `/api/cpa/leads/{id}/state`. Visual confirmation: card pulses gold briefly.

**Column headers:** Count badge + total pipeline value (`"Qualified (4) · $28,400"`)

### 4.3 Notifications Center (`/cpa/notifications`)

**Grouping by type:**
- 🎯 New Lead (gold left border)
- 💬 Message (blue left border)
- ⏰ Deadline (red left border if overdue, amber if upcoming)
- ⚙️ System (gray left border)

**Unread:** Gold left border + light yellow background
**Actions per item:** Mark read (checkmark icon), View (arrow icon)
**Bulk:** "Mark all as read" button top-right

### 4.4 Return Review Layout

**Two-panel layout:**
- Left panel (280px): navigation tree — sections of the return (Income, Deductions, Credits, Summary)
- Right panel: content for selected section
- Section headers: numbered, Playfair Display
- Data fields: label/value pairs in a clean grid, editable on click
- Audit flags: red warning chip beside any flagged field
- Notes panel: collapsible sidebar within the right panel

---

## 5. Component Library — Full Spec Required

Each component needs: all states, hover, focus, disabled, mobile, and dark-mode variants.

| Component | States Needed |
|-----------|--------------|
| Strategy card | free, locked, unlocked, cpa-recommended |
| Progress indicator | 0%, 25%, 50%, 75%, 100%, phase labels |
| Savings reveal card | pre-reveal, animating, revealed, mobile |
| Trust badge row | 3-badge horizontal, 2-badge mobile stacked |
| CPA soft prompt | with booking URL, without booking URL (fallback) |
| Lead magnet report document | screen view, print view, PDF export |
| Kanban card | default, hover, dragging, overdue |
| Notification item | unread, read, hovered, grouped header |
| Upload confirmation card | loading OCR, success with data, failure |
| Phase divider | entering income, deductions, retirement, business, review |
| Tax health score dial | 0–40 red, 41–70 amber, 71–100 green, animating |

---

## 6. Deliverables

| Deliverable | Format | Priority |
|-------------|--------|----------|
| Figma component library (all states) | Figma | P0 |
| Intelligent advisor — full annotated flow (12 scenarios) | Figma + PDF | P0 |
| Mobile-first advisor specs (keyboard-aware, banner positions) | Figma | P0 |
| Lead magnet funnel — all 6 pages | Figma | P1 |
| CPA dashboard — analytics, pipeline, notifications, return review | Figma | P1 |
| Handoff spec with CSS variable mappings | Zeplin or Figma Inspect | P1 |
| Design tokens file (JSON) aligning with existing CSS variables | JSON | P1 |
| Micro-animation specs (savings reveal, progress bar, card transitions) | Lottie or CSS spec | P2 |

---

## 7. Success Criteria

| Metric | Target | Current |
|--------|--------|---------|
| Advisor completion rate | > 65% | Unknown |
| Lead magnet contact capture rate | > 30% | Unknown |
| CPA trial-to-paid conversion | > 20% | Unknown |
| Mobile usability (Lighthouse) | > 90 | Untested |
| Time to first savings estimate | < 90 seconds | Unknown |
| Report page print quality | PDF-ready | Partial |

---

## 8. Scenario Coverage — Designer Must Spec All 12

The advisor must handle each of these paths gracefully, with appropriate UI states:

1. Single W-2 employee, simple return (8 questions)
2. Freelancer, no entity, no retirement accounts (12 questions)
3. Freelancer + S-Corp election candidate (14 questions)
4. Small business owner, LLC, multi-revenue streams (16 questions)
5. Real estate investor, 3 rental properties (14 questions)
6. High-income W-2 + RSUs + Backdoor Roth candidate (12 questions)
7. Married filing jointly, one spouse self-employed (14 questions)
8. Retiree, Social Security + pension + RMDs (10 questions)
9. K-1 recipient, partnership passthrough (12 questions)
10. User answers "I don't know" to most questions (adaptive path)
11. User abandons at step 3, returns later (session resume flow)
12. User completes analysis but doesn't convert to lead (re-engagement CTA)

For each scenario: define entry state, question sequence, pivot points, strategy cards shown (free vs locked), and the final CTA presented.

---

## 9. Constraints & Non-Negotiables

- **No React.** All interactivity via Alpine.js + vanilla JS. Designer must account for this in animation specs (CSS transitions, not React spring animations).
- **CSS variables only.** No hardcoded hex colors in new components — all colors must reference existing tokens.
- **Accessibility:** All interactive elements must meet WCAG 2.1 AA. Progress indicators must have `aria-valuenow`/`aria-valuemax`. Strategy cards must be keyboard navigable.
- **Performance:** No new font families. No new icon libraries. Use existing Heroicons SVG set.
- **Brand hierarchy:** Navy is authority, gold is action/reward. Never use gold for warnings (use amber). Never use navy as a CTA button color on navy backgrounds.
- **Print:** Lead magnet report and results page must be print-ready. No background images, no fixed positioning in print CSS.

---

*Questions? Contact: product team via GitHub issues in `camayank/jorss-gbo-taai`*
