# Tiered Conversion Experience — Design Document

**Date:** 2026-02-27
**Status:** Approved
**Approach:** C — Tiered Experience with Instant Unlock

---

## Problem

The Jorss-Gbo tax advisory platform has 25+ AI services wired into the backend, but the user funnel is optimized for **report delivery**, not **CPA conversion**. Estimated CPA conversion: 2-5%. Users download their report and leave.

## Solution

A **tiered experience** that dynamically classifies tax strategies as Free (DIY) or Premium (CPA-recommended) based on actual AI risk analysis. Premium strategies show dollar amounts but gate the implementation plan behind a zero-friction "unlock" that leads to soft CPA lead capture.

---

## 1. Strategy Tiering Logic

### Classification Rules

Strategies are classified dynamically per user profile:

```
FREE (user can implement alone):
  - requires_professional_review = false
  - Strategy audit_risk contribution < 20
  - Single-step implementation (401k, HSA, charitable)

PREMIUM (CPA-recommended):
  - requires_professional_review = true  OR
  - Strategy audit_risk contribution >= 20  OR
  - Involves entity changes, conversions, or timing-dependent moves
```

### Data Sources
- `TaxReasoningService.analyze()` returns `requires_professional_review` and `confidence`
- `AnomalyDetector.assess_audit_risk()` returns `risk_score` and `primary_triggers`
- Strategy-level risk derived from strategy category and profile complexity

### Edge Cases
- **All strategies free** (simple W-2 profile): Show all strategies, no tiering. Soft CPA offer at report stage.
- **All strategies premium** (complex profile): Show all as premium. First unlock reveals all.
- **AI unavailable**: All strategies shown as free (graceful fallback). No tiering without AI confidence.

---

## 2. Unlock Flow

### Mechanism: Instant Unlock + Soft Lead Capture

```
User clicks locked strategy or "Unlock" button
          │
          ▼
  [All strategies immediately unlock — zero friction]
  [Full AI analysis revealed for all strategies]
          │
          ▼
  Bot message: "Your full analysis is unlocked.
   Want me to email you a copy and connect you
   with a CPA who can help implement?"

  [Yes, email me]  [No thanks]
          │
          ▼
  (If yes)
  Name:  [_______________]
  Email: [_______________]
  [Send & Connect]
          │
          ▼
  [Report emailed to user]
  [CPA team notified with full lead data + report]
  [Confirmation shown in chat]
```

### State Management
- Session tracks `premium_unlocked: boolean`
- Once unlocked, stays unlocked for session lifetime
- Unlock state persisted in session store

---

## 3. CPA Conversion Flow (Post-Unlock)

### After email capture:
1. **Confirmation email** sent to user (report attached, CPA intro)
2. **CPA notification** sent to internal team (lead data + report + session context)
3. **Chat confirmation**: "Your report has been sent. A CPA will reach out within 24 hours."
4. **Document upload prompt**: "Want to upload docs for your CPA to review?"

### Missing endpoint to build:
- `POST /api/advisor/report/email` — generates and sends report via email

---

## 4. Safety Check Display (User-Facing)

Currently safety checks are only visible to CPAs. In the new design, users see a compliance summary:

```
Compliance Summary:
  ✅ 9/10 checks passed
  ⚠️ 1 item needs professional review

  ✅ Fraud Detection: Clear
  ✅ Income Verification: Pass
  ✅ Deduction Validation: Pass
  ⚠️ EITC Due Diligence: Review recommended
  ✅ Circular 230: Compliant
```

This builds trust AND creates natural demand for CPA review on flagged items.

---

## 5. Frontend Design

### Aesthetic: Refined Professional
Bloomberg Terminal meets Stripe Dashboard. Clean cards, subtle gradients, crisp typography.

### New Components (proper CSS, not inline styles):

1. **Strategy Card (Free)** — white card, green savings badge, full content visible
2. **Strategy Card (Locked)** — frosted/blurred content, lock icon, visible dollar amount, "CPA-Recommended" badge
3. **Strategy Card (Unlocked)** — same as Free but with "Unlocked" indicator
4. **Safety Summary Panel** — compliance check list with pass/fail icons
5. **Audit Risk Badge** — prominent colored badge (green/amber/red) with score
6. **Unlock Modal** — centered overlay with value prop + email capture
7. **Action Plan Card** — step-by-step checklist from AI narrative

### CSS Architecture
- New stylesheet: `advisor-premium.css`
- CSS custom properties extending existing design system
- No inline styles in JavaScript

---

## 6. New AI Service Wiring (This Round)

| Service | Method | Where Used |
|---------|--------|-----------|
| ChatRouter | `compare_scenarios()` | Chat endpoint — "Should I do X or Y?" questions |
| TaxReasoningService | `analyze_amt_exposure()` | New `/amt-analysis` endpoint (premium) |
| AIMetricsService | `record_usage()` | Middleware wrapping all AI service calls |

---

## 7. Backend Changes Summary

### Modified Endpoints:
- `POST /api/advisor/chat` — add strategy tiering to calculation response
- `POST /api/advisor/analyze` — add tier classification to each strategy
- `GET /api/advisor/safety-check/{id}` — add user-facing summary format

### New Endpoints:
- `POST /api/advisor/report/email` — send report via email
- `POST /api/advisor/amt-analysis` — AMT exposure analysis
- `POST /api/advisor/unlock-strategies` — mark session as unlocked

### Modified Response Shapes:
- `StrategyRecommendation` gains: `tier` (free/premium), `risk_level`, `implementation_complexity`
- `ChatResponse` gains: `premium_unlocked`, `safety_summary`
- Report response gains: `email_sent` confirmation

---

## 8. Error Handling

- AI tiering failure → all strategies shown as free (graceful degradation)
- Email send failure → offer PDF download as fallback
- Safety check unavailable → hide compliance summary (don't show broken state)
- Unlock endpoint failure → unlock locally in session, retry backend sync

---

## 9. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| CPA conversion (report → CPA request) | ~2-5% | 15-25% |
| Email capture rate | ~0% (endpoint missing) | 30-40% |
| Strategy engagement (click-through) | Unknown | Track with metrics service |
| Funnel drop-off at Phase 2 questions | ~30% | <15% with "Skip All" |

---

## 10. Files Modified

| File | Changes |
|------|---------|
| `src/web/intelligent_advisor_api.py` | Strategy tiering, unlock endpoint, email endpoint, AMT endpoint, safety user summary, compare_scenarios wiring, record_usage middleware |
| `src/web/static/js/pages/intelligent-advisor.js` | Locked/unlocked strategy rendering, safety summary display, unlock flow, email capture UI, CPA flow enhancement |
| `src/web/static/css/advisor-premium.css` | **NEW** — all new component styles |
| `src/web/advisor_models.py` | Add tier/risk fields to StrategyRecommendation |
