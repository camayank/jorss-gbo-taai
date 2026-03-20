# Frontend Flow Rewrite — Focused Plan

## The Problem
The frontend (`advisor-flow.js`) has its own client-side Phase 1 that fights with the backend.
The backend has the complete hybrid flow (194 questions, transitions, live estimate, smart defaults,
proactive advice) but the frontend bypasses it by handling Phase 1 locally.

## The Fix
Rewrite `advisor-flow.js` so that `handleQuickAction` is a THIN PASS-THROUGH to the backend.
No local state. No client-side questions. Backend is the single source of truth.

## Files to change

### 1. `src/web/static/js/advisor/modules/advisor-flow.js`
**DELETE entirely and rewrite.** The new version should be ~100 lines:

```javascript
export async function handleQuickAction(value, displayLabel = null) {
    // Show user's selection
    if (displayLabel || !['start','continue','no_manual'].includes(value)) {
        const text = displayLabel || value.replace(/_/g,' ').replace(/\b\w/g, l => l.toUpperCase());
        addMessage('user', text);
    }

    // EVERYTHING goes to backend
    await processAIResponse(value);
}

// startIntelligentQuestioning — removed. Backend handles all questions.
export async function startIntelligentQuestioning() {
    await processAIResponse('continue');
}

// showPreliminarySummary — removed. Backend handles confirmation.
export async function showPreliminarySummary() {
    await processAIResponse('continue');
}
```

Keep the exports that other modules depend on (resetQuestioningState, etc.) but make them no-ops.

### 2. `src/web/static/js/advisor/modules/advisor-chat.js`
In `processAIResponse`, ensure the backend response's `response_type` drives ALL rendering:
- `question` → show question + buttons (or checkboxes if multi_select)
- `transition` → show mode choice cards
- `freeform_intake` → show textarea
- `summary` → show parsed fields
- `confirmation` → show full profile
- `comparison` → show MFJ vs MFS
- `calculation` → show tax result
- `document_offer` → show upload option
- `help` → show explanation

No special casing. No client-side state checks. Just render what the backend says.

### 3. `src/web/templates/intelligent_advisor.html`
Remove the hardcoded welcome message buttons that use old values (`no_manual`, `yes_upload`).
Replace with a single "Start" button that sends to backend:
```html
<button class="quick-action primary" data-action="start">Start my tax estimate</button>
```

### 4. `src/web/static/js/advisor/modules/index.js`
Update the initial button handler to use the new simplified `handleQuickAction`.
Remove any references to `startIntelligentQuestioning` as a Phase 1 driver.

## What NOT to change
- Backend (`intelligent_advisor_api.py`) — already correct
- CSS — already correct
- `advisor-display.js` — already has all render functions
- `advisor-core.js` — session management stays
- `advisor-data.js` — API calls stay

## Test plan
1. Fresh page load → "Start" → backend returns filing status question
2. Click "Single" → backend returns income question
3. Click "$50K-$100K" → backend returns state question
4. Select "CA" → backend returns dependents question
5. Click "0 dependents" → backend returns income type question
6. Click "W-2 Employee" → backend returns document upload offer
7. Click "I'll enter manually" → backend returns transition (mode choice)
8. Click "Guide me step by step" → backend returns first Phase 2 question with live estimate
9. Continue through questions → each one from backend with topic headers
10. All done → confirmation screen → "Run the numbers" → calculation
