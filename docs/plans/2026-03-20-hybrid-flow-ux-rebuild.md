# Hybrid Conversation Flow — Full-Stack Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the single-mode sequential chat with a 3-mode hybrid flow (Guided → Free-form/Sequential choice → Targeted follow-ups → Confirmation → Calculation) across backend, middleware, and frontend — with zero parallel old code remaining.

**Architecture:** Backend adds 3 new response types (`transition`, `summary`, `confirmation`) to `ChatResponse`. The chat endpoint detects which mode the user is in and routes accordingly. Frontend adds 4 new UI components (TransitionCards, FreeFormIntake, ParsedSummary, ProfileConfirmation) and modifies the existing chat renderer to handle topic groupings. All old single-mode code is removed.

**Tech Stack:** Python/FastAPI (backend), Vanilla JS modules (frontend), HTML/CSS with existing DM Sans + charcoal/parchment/amber design system.

---

## File Map — What Changes

| File | Action | What |
|------|--------|------|
| `src/web/advisor/models.py` | MODIFY | Add new response types and fields to `ChatResponse` |
| `src/web/intelligent_advisor_api.py` | MODIFY | Add transition detection, Mode A handler, summary builder, confirmation builder |
| `src/web/advisor/parsers.py` | MODIFY | Enhance free-form bulk parser to extract ALL fields from a paragraph |
| `src/web/templates/intelligent_advisor.html` | MODIFY | Add CSS for new components, update layout zones |
| `src/web/static/js/advisor/modules/advisor-chat.js` | MODIFY | Handle new response types, render new components |
| `src/web/static/js/advisor/modules/advisor-flow.js` | MODIFY | Add mode state machine, topic grouping, transition logic |
| `src/web/static/js/advisor/modules/advisor-display.js` | MODIFY | Add summary card renderer, confirmation renderer |
| `src/web/static/js/advisor/modules/advisor-core.js` | MODIFY | Add mode state (`guided`, `freeform`, `followup`, `confirmation`) |
| `src/web/static/js/advisor/modules/index.js` | MODIFY | Wire new event handlers |

---

## Task 1: Extend ChatResponse Model

**Files:**
- Modify: `src/web/advisor/models.py:273-312`

**What to add to `ChatResponse`:**

```python
class ChatResponse(BaseModel):
    # ... existing fields ...

    # NEW: Conversation mode fields
    conversation_mode: str = "guided"  # "guided", "freeform", "followup", "confirmation"

    # NEW: Transition data (shown after Phase 1 completes)
    show_transition: bool = False
    profile_summary: Optional[Dict[str, Any]] = None  # Phase 1 data summary

    # NEW: Parsed summary (after free-form intake)
    parsed_fields: Optional[Dict[str, Any]] = None  # What NLU extracted
    parsed_count: int = 0  # How many fields extracted
    remaining_gaps: int = 0  # How many questions still needed

    # NEW: Topic grouping (for guided mode)
    topic_name: Optional[str] = None  # "Income Details", "Family", etc.
    topic_number: Optional[int] = None  # 1-6
    topic_total: int = 6
    question_in_topic: Optional[int] = None  # 2 of 5
    questions_in_topic_total: Optional[int] = None

    # NEW: Confirmation data (before calculation)
    show_confirmation: bool = False
    full_profile_summary: Optional[Dict[str, Any]] = None
```

---

## Task 2: Add Phase 1 Completion Detection + Transition Response

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` — in the `intelligent_chat` endpoint

**Logic:** After the `_quick_action_map` processes a Phase 1 answer, check if ALL 5 Phase 1 fields are now populated. If yes, return a `transition` response instead of jumping to Phase 2.

```python
# After quick_action_map processing, before calling _get_dynamic_next_question:

phase1_complete = all([
    profile.get("filing_status"),
    profile.get("total_income"),
    profile.get("state"),
    profile.get("dependents") is not None,
    profile.get("income_type"),
])

# Check if this is the FIRST time Phase 1 is complete (transition not yet shown)
if phase1_complete and not profile.get("_transition_shown"):
    profile["_transition_shown"] = True
    await chat_engine.update_session(request.session_id, {"profile": profile})

    return ChatResponse(
        session_id=request.session_id,
        response="Great foundation! Now I need the details that'll save you the most money.",
        response_type="transition",
        show_transition=True,
        conversation_mode="guided",
        profile_summary={
            "filing_status": profile["filing_status"],
            "total_income": profile["total_income"],
            "state": profile["state"],
            "dependents": profile["dependents"],
            "income_type": profile["income_type"],
        },
        profile_completeness=0.15,
        quick_actions=[
            {"label": "Tell me everything", "value": "mode_freeform"},
            {"label": "Guide me step by step", "value": "mode_guided"},
        ],
    )
```

**Also add to `_quick_action_map`:**
```python
"mode_freeform": {"_conversation_mode": "freeform", "_transition_shown": True},
"mode_guided": {"_conversation_mode": "guided", "_transition_shown": True},
```

---

## Task 3: Add Mode A (Free-Form) Handler

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` — in the `intelligent_chat` endpoint

**Logic:** When `_conversation_mode == "freeform"` and user sends a long message (not a button click), run the enhanced parser on it, extract everything, build a summary, and return a `summary` response type.

```python
# After _quick_action_map check, before existing flow:

if profile.get("_conversation_mode") == "freeform" and not _quick_action_handled:
    if len(msg_original) > 30:  # Long message = free-form input
        # Run enhanced parser on the full text
        from src.web.advisor.parsers import enhanced_parse_user_message
        parse_result = enhanced_parse_user_message(msg_original, profile)
        extracted = parse_result.get("extracted", {})

        # Apply all extracted fields to profile
        for field, value in extracted.items():
            if not field.startswith("_") or field in ("_has_investments", "_has_rental", "_has_k1", "_has_mortgage", "_has_charitable", "_has_property_taxes", "_has_medical", "_has_salt", "_has_estimated_payments"):
                profile[field] = value

        # Count what was captured vs what's still needed
        captured_fields = {k: v for k, v in extracted.items() if not k.startswith("_")}

        # Calculate remaining gaps
        remaining = 0
        p_copy = dict(profile)
        for _ in range(100):
            text, actions = _get_dynamic_next_question(p_copy, session=session)
            if text is None:
                break
            remaining += 1
            # Mark as asked to count total
            for a in (actions or []):
                v = a.get("value", "")
                if v.startswith("skip_"):
                    p_copy[v] = True
                    break
            # Also set generic _asked flags
            p_copy["_counted_" + str(remaining)] = True
            if remaining > 60:
                break

        # Switch to followup mode
        profile["_conversation_mode"] = "followup"
        await chat_engine.update_session(request.session_id, {"profile": profile})

        return ChatResponse(
            session_id=request.session_id,
            response=f"Here's what I captured from your description. Please confirm or correct:",
            response_type="summary",
            conversation_mode="followup",
            parsed_fields=captured_fields,
            parsed_count=len(captured_fields),
            remaining_gaps=remaining,
            quick_actions=[
                {"label": "Looks right!", "value": "confirm_summary"},
                {"label": "Let me fix something", "value": "fix_summary"},
            ],
        )
```

---

## Task 4: Add Topic Grouping to Sequential Mode

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` — in the section that calls `_get_dynamic_next_question`

**Logic:** When `_conversation_mode == "guided"`, wrap the question response with topic metadata.

```python
# Topic mapping based on question content
TOPIC_MAP = {
    "withholding": ("Income Details", 1),
    "side": ("Income Details", 1),
    "entity": ("Income Details", 1),
    "business income": ("Income Details", 1),
    "spouse": ("Income Details", 1),
    "gig": ("Income Details", 1),
    "farm": ("Income Details", 1),
    "clergy": ("Income Details", 1),

    "dependent": ("Your Family", 2),
    "child": ("Your Family", 2),
    "custody": ("Your Family", 2),
    "education": ("Your Family", 2),
    "529": ("Your Family", 2),

    "life change": ("Life Events", 3),
    "married": ("Life Events", 3),
    "divorce": ("Life Events", 3),
    "sold": ("Life Events", 3),
    "moved": ("Life Events", 3),
    "inheritance": ("Life Events", 3),

    "investment": ("Investments & Retirement", 4),
    "crypto": ("Investments & Retirement", 4),
    "stock": ("Investments & Retirement", 4),
    "retirement": ("Investments & Retirement", 4),
    "401": ("Investments & Retirement", 4),
    "IRA": ("Investments & Retirement", 4),
    "HSA": ("Investments & Retirement", 4),
    "EITC": ("Investments & Retirement", 4),

    "deduction": ("Deductions & Credits", 5),
    "mortgage": ("Deductions & Credits", 5),
    "charit": ("Deductions & Credits", 5),
    "student loan": ("Deductions & Credits", 5),
    "medical": ("Deductions & Credits", 5),
    "educator": ("Deductions & Credits", 5),
    "rental": ("Deductions & Credits", 5),
    "K-1": ("Deductions & Credits", 5),

    "estimated": ("Final Checks", 6),
    "energy": ("Final Checks", 6),
    "foreign": ("Final Checks", 6),
    "gambling": ("Final Checks", 6),
    "AMT": ("Final Checks", 6),
    "alimony": ("Final Checks", 6),
    "state": ("Final Checks", 6),
    "extension": ("Final Checks", 6),
    "refund": ("Final Checks", 6),
}

def _get_topic_for_question(question_text: str) -> tuple:
    """Return (topic_name, topic_number) for a question."""
    text_lower = question_text.lower()
    for keyword, (topic, num) in TOPIC_MAP.items():
        if keyword.lower() in text_lower:
            return (topic, num)
    return ("Additional Details", 6)
```

Then when building the ChatResponse for a question:
```python
topic_name, topic_number = _get_topic_for_question(next_question_text)

return ChatResponse(
    session_id=request.session_id,
    response=next_question_text,
    response_type="question",
    conversation_mode=profile.get("_conversation_mode", "guided"),
    topic_name=topic_name,
    topic_number=topic_number,
    topic_total=6,
    quick_actions=next_actions,
    # ... existing fields ...
)
```

---

## Task 5: Add Confirmation Response Before Calculation

**Files:**
- Modify: `src/web/intelligent_advisor_api.py`

**Logic:** When `_get_dynamic_next_question` returns `(None, None)` (all questions answered), instead of immediately calculating, return a `confirmation` response with the full profile summary.

```python
if next_question_text is None:
    # All questions answered — show confirmation before calculating
    if not profile.get("_confirmed_profile"):
        summary = _build_profile_summary(profile)
        return ChatResponse(
            session_id=request.session_id,
            response="Here's your complete tax profile. Anything to add or change before I run the numbers?",
            response_type="confirmation",
            show_confirmation=True,
            conversation_mode="confirmation",
            full_profile_summary=summary,
            quick_actions=[
                {"label": "Looks right — run the numbers!", "value": "confirm_and_calculate"},
                {"label": "I need to change something", "value": "edit_profile"},
            ],
        )
    else:
        # Already confirmed — proceed to calculation
        # ... existing calculation logic ...
```

**Helper function:**
```python
def _build_profile_summary(profile: dict) -> dict:
    """Build organized profile summary for confirmation screen."""
    income = float(profile.get("total_income", 0) or 0)
    return {
        "basics": {
            "filing_status": profile.get("filing_status"),
            "state": profile.get("state"),
            "dependents": profile.get("dependents", 0),
            "age": profile.get("age"),
            "income_type": profile.get("income_type"),
        },
        "income": {
            "total_income": income,
            "business_income": profile.get("business_income"),
            "investment_income": profile.get("investment_income"),
            "rental_income": profile.get("rental_income"),
            "k1_ordinary_income": profile.get("k1_ordinary_income"),
            "ss_benefits": profile.get("ss_benefits"),
            "spouse_income": profile.get("spouse_income"),
        },
        "deductions": {
            "mortgage_interest": profile.get("mortgage_interest"),
            "property_taxes": profile.get("property_taxes"),
            "charitable_donations": profile.get("charitable_donations"),
            "medical_expenses": profile.get("medical_expenses"),
            "student_loan_interest": profile.get("student_loan_interest"),
        },
        "credits": {
            "dependents_under_17": profile.get("dependents_under_17"),
            "childcare_costs": profile.get("childcare_costs"),
            "education_status": profile.get("education_status"),
            "energy_credits": profile.get("energy_credits"),
        },
        "retirement": {
            "retirement_401k": profile.get("retirement_401k"),
            "retirement_ira": profile.get("retirement_ira"),
            "hsa_contributions": profile.get("hsa_contributions"),
        },
        "payments": {
            "federal_withholding": profile.get("federal_withholding"),
            "estimated_payments": profile.get("estimated_payments"),
            "state_withholding": profile.get("state_withholding"),
        },
    }
```

---

## Task 6: Frontend — Handle New Response Types in Chat Renderer

**Files:**
- Modify: `src/web/static/js/advisor/modules/advisor-chat.js`

**In `processAIResponse` function, add handlers for new response types:**

```javascript
// After existing response_type checks:

if (data.response_type === 'transition') {
    renderTransitionCards(data);
    return;
}

if (data.response_type === 'summary') {
    renderParsedSummary(data);
    return;
}

if (data.response_type === 'confirmation') {
    renderProfileConfirmation(data);
    return;
}

// For "question" type with topic info:
if (data.topic_name && data.topic_number) {
    renderTopicHeader(data.topic_name, data.topic_number, data.topic_total);
}
```

---

## Task 7: Frontend — Transition Cards Component

**Files:**
- Modify: `src/web/static/js/advisor/modules/advisor-display.js`
- Modify: `src/web/templates/intelligent_advisor.html` (CSS)

**Render function:**

```javascript
export function renderTransitionCards(data) {
    const chatArea = document.getElementById('chat-messages');

    // Profile summary banner
    const summaryHTML = `
        <div class="profile-summary-banner">
            <div class="summary-items">
                <span>${formatFilingStatus(data.profile_summary.filing_status)}</span>
                <span>$${Number(data.profile_summary.total_income).toLocaleString()}</span>
                <span>${data.profile_summary.state}</span>
                <span>${data.profile_summary.dependents} dependent(s)</span>
                <span>${formatIncomeType(data.profile_summary.income_type)}</span>
            </div>
        </div>
    `;

    // Two mode cards
    const cardsHTML = `
        <div class="transition-container">
            <p class="transition-intro">${escapeHtml(data.response)}</p>
            <div class="mode-cards">
                <div class="mode-card" data-mode="freeform">
                    <div class="mode-card-icon">📝</div>
                    <h3>Tell Me Everything</h3>
                    <p>Describe your full tax situation in your own words. I'll extract every detail and only follow up on what I need.</p>
                    <p class="mode-card-time">Fastest if you know your numbers</p>
                    <button class="mode-card-btn" onclick="handleQuickAction('mode_freeform')">Choose this</button>
                </div>
                <div class="mode-card" data-mode="guided">
                    <div class="mode-card-icon">💬</div>
                    <h3>Guide Me Step by Step</h3>
                    <p>I'll ask one question at a time, grouped by topic. Perfect if you're not sure what's relevant.</p>
                    <p class="mode-card-time">~5-15 minutes</p>
                    <button class="mode-card-btn" onclick="handleQuickAction('mode_guided')">Choose this</button>
                </div>
            </div>
        </div>
    `;

    chatArea.innerHTML += summaryHTML + cardsHTML;
    chatArea.scrollTop = chatArea.scrollHeight;
}
```

**CSS (add to intelligent_advisor.html):**

```css
.profile-summary-banner {
    background: var(--ink);
    color: var(--parchment);
    border-radius: var(--radius);
    padding: 12px 20px;
    margin: 16px 0;
}
.profile-summary-banner .summary-items {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    font-size: 0.85rem;
}
.profile-summary-banner .summary-items span {
    padding: 4px 12px;
    background: rgba(255,255,255,0.1);
    border-radius: 20px;
}

.transition-container { margin: 24px 0; }
.transition-intro {
    font-size: 1.1rem;
    color: var(--ink);
    margin-bottom: 20px;
    line-height: 1.5;
}

.mode-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}
@media (max-width: 640px) {
    .mode-cards { grid-template-columns: 1fr; }
}

.mode-card {
    background: var(--white);
    border: 2px solid var(--stone-200);
    border-radius: var(--radius);
    padding: 24px;
    text-align: center;
    transition: var(--transition);
    cursor: pointer;
}
.mode-card:hover {
    border-color: var(--amber);
    box-shadow: var(--shadow-md);
}
.mode-card-icon { font-size: 2rem; margin-bottom: 12px; }
.mode-card h3 {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--ink);
}
.mode-card p {
    font-size: 0.9rem;
    color: var(--stone-600);
    line-height: 1.4;
    margin-bottom: 8px;
}
.mode-card-time {
    font-size: 0.8rem;
    color: var(--amber);
    font-weight: 500;
}
.mode-card-btn {
    margin-top: 16px;
    background: var(--amber);
    color: var(--white);
    border: none;
    padding: 10px 24px;
    border-radius: var(--radius-sm);
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition);
}
.mode-card-btn:hover { filter: brightness(1.1); }
```

---

## Task 8: Frontend — Free-Form Intake Screen

**Files:**
- Modify: `src/web/static/js/advisor/modules/advisor-chat.js`

**When mode is "freeform" and user hasn't submitted yet, show large text area:**

```javascript
export function renderFreeFormIntake() {
    const chatArea = document.getElementById('chat-messages');

    chatArea.innerHTML += `
        <div class="freeform-container" id="freeform-intake">
            <p class="freeform-intro">Tell me about your tax situation. Include anything you think is relevant — I'll organize it all.</p>
            <div class="freeform-hints">
                <span>💡 Things to mention:</span>
                <ul>
                    <li>Income sources (W-2, business, investments, rental)</li>
                    <li>Major deductions (mortgage, charity, medical)</li>
                    <li>Life changes (married, kids, bought/sold home)</li>
                    <li>Retirement accounts (401k, IRA, HSA)</li>
                    <li>Anything unusual (crypto, foreign income, divorce)</li>
                </ul>
            </div>
            <textarea id="freeform-textarea" class="freeform-textarea"
                placeholder="Example: I make $120k as a W-2 employee, my wife is self-employed making about $80k. We have 2 kids in daycare. We pay $15k in mortgage interest..."
                rows="8"></textarea>
            <div class="freeform-actions">
                <button class="btn-primary" onclick="submitFreeForm()">Submit</button>
                <button class="btn-secondary" onclick="handleQuickAction('mode_guided')">Switch to guided mode</button>
            </div>
        </div>
    `;
}
```

---

## Task 9: Frontend — Parsed Summary Component

**Files:**
- Modify: `src/web/static/js/advisor/modules/advisor-display.js`

```javascript
export function renderParsedSummary(data) {
    const fields = data.parsed_fields || {};
    const chatArea = document.getElementById('chat-messages');

    let html = '<div class="parsed-summary"><h3>Here\'s what I captured:</h3>';

    const categories = {
        'Income': ['total_income', 'business_income', 'investment_income', 'rental_income', 'k1_ordinary_income'],
        'Family': ['dependents', 'childcare_costs', 'education_status'],
        'Deductions': ['mortgage_interest', 'property_taxes', 'charitable_donations', 'medical_expenses'],
        'Retirement': ['retirement_401k', 'retirement_ira', 'hsa_contributions'],
        'Other': [] // catch-all
    };

    for (const [category, keys] of Object.entries(categories)) {
        const items = keys.filter(k => fields[k] != null);
        if (items.length === 0) continue;

        html += `<div class="summary-category"><h4>${category}</h4>`;
        for (const key of items) {
            const value = fields[key];
            const display = typeof value === 'number' ? `$${value.toLocaleString()}` : value;
            html += `<div class="summary-item"><span class="check">✅</span> ${formatFieldName(key)}: ${display}</div>`;
        }
        html += '</div>';
    }

    html += `<div class="summary-footer">`;
    html += `<p>${data.remaining_gaps} follow-up questions remaining</p>`;
    html += `<div class="summary-actions">`;
    html += `<button class="btn-primary" onclick="handleQuickAction('confirm_summary')">✓ Looks right!</button>`;
    html += `<button class="btn-secondary" onclick="handleQuickAction('fix_summary')">✎ Let me fix something</button>`;
    html += `</div></div></div>`;

    chatArea.innerHTML += html;
}
```

---

## Task 10: Frontend — Profile Confirmation Component

**Files:**
- Modify: `src/web/static/js/advisor/modules/advisor-display.js`

```javascript
export function renderProfileConfirmation(data) {
    const summary = data.full_profile_summary || {};
    const chatArea = document.getElementById('chat-messages');

    let html = '<div class="profile-confirmation">';
    html += '<h2>Your Tax Profile Summary</h2>';

    // Basics row
    const b = summary.basics || {};
    html += `<div class="conf-row">
        <span>Filing: ${formatFilingStatus(b.filing_status)}</span>
        <span>State: ${b.state}</span>
        <span>Dependents: ${b.dependents}</span>
        <span>Age: ${b.age}</span>
    </div>`;

    // Income card
    html += renderConfSection('Income', summary.income);
    html += renderConfSection('Deductions', summary.deductions);
    html += renderConfSection('Credits', summary.credits);
    html += renderConfSection('Retirement', summary.retirement);
    html += renderConfSection('Payments', summary.payments);

    html += `<div class="conf-actions">
        <button class="btn-amber btn-large" onclick="handleQuickAction('confirm_and_calculate')">
            ✓ Looks right — run the numbers!
        </button>
        <button class="btn-secondary" onclick="handleQuickAction('edit_profile')">
            ✎ I need to change something
        </button>
    </div>`;

    html += '</div>';
    chatArea.innerHTML += html;
}
```

---

## Task 11: Frontend — Topic Grouping Headers

**Files:**
- Modify: `src/web/static/js/advisor/modules/advisor-chat.js`

```javascript
let lastTopicNumber = 0;

export function renderTopicHeader(topicName, topicNumber, topicTotal) {
    if (topicNumber === lastTopicNumber) return; // Same topic, no new header
    lastTopicNumber = topicNumber;

    const chatArea = document.getElementById('chat-messages');
    chatArea.innerHTML += `
        <div class="topic-header">
            <div class="topic-divider"></div>
            <div class="topic-label">
                <span class="topic-name">${topicName}</span>
                <span class="topic-count">${topicNumber} / ${topicTotal}</span>
            </div>
        </div>
    `;
}
```

**CSS:**
```css
.topic-header {
    margin: 28px 0 16px;
    text-align: center;
}
.topic-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--stone-300), transparent);
    margin-bottom: 12px;
}
.topic-label {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    background: var(--stone-50);
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--stone-600);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.topic-count {
    color: var(--amber);
    font-family: var(--mono);
}
```

---

## Task 12: Update Input Bar — Always Show Free-Form Hint

**Files:**
- Modify: `src/web/templates/intelligent_advisor.html`

**Replace the existing input placeholder and add persistent action links:**

```html
<div class="input-bar">
    <div class="input-row">
        <textarea id="user-input"
            placeholder="Type freely or click buttons above..."
            rows="1"></textarea>
        <button id="send-btn" class="send-btn">➤</button>
    </div>
    <div class="input-actions">
        <button class="input-action-link" onclick="handleQuickAction('skip_current')">
            Skip this question
        </button>
        <button class="input-action-link amber" onclick="handleQuickAction('done_calculating')" id="done-btn" style="display:none">
            I'm done — calculate my taxes
        </button>
    </div>
</div>
```

---

## Task 13: Backend — Remove Old Parallel Code

**Files:**
- Modify: `src/web/intelligent_advisor_api.py`

**What to remove/clean:**
1. The old `AI_ADAPTIVE_QUESTIONS_ENABLED` flag and `_score_next_questions` call (no longer used — sequential flow is primary)
2. Any duplicate question logic between `_score_next_questions` and `_get_dynamic_next_question`
3. Old response type handling that doesn't fit the new 3-mode flow

**What to keep:**
- `_get_dynamic_next_question` — this is the core sequential engine, untouched
- `_quick_action_map` — this is the button→profile mapping, untouched
- `_score_next_questions` — keep the function but don't call it from the main flow (may be useful for "smart ordering" later)

---

## Task 14: Integration Testing

**Files:**
- Create: `tests/advisor/test_hybrid_flow.py`

**Test scenarios:**

```python
class TestTransitionAfterPhase1:
    """After all 5 Phase 1 questions answered, should return transition response."""

class TestFreeFormIntake:
    """When user sends a paragraph in freeform mode, should parse and return summary."""

class TestGuidedWithTopics:
    """In guided mode, questions should include topic metadata."""

class TestConfirmationBeforeCalc:
    """When all questions done, should show confirmation before calculating."""

class TestFreeFormSkipsAnswered:
    """After free-form, follow-up mode should only ask unanswered questions."""

class TestMidFlowFreeForm:
    """If user types paragraph during guided mode, should parse and skip ahead."""
```

---

## Execution Order

| Task | Depends On | Effort |
|------|-----------|--------|
| 1. ChatResponse model | — | Small |
| 2. Transition detection | 1 | Medium |
| 3. Free-form handler | 1, 2 | Large |
| 4. Topic grouping | 1 | Medium |
| 5. Confirmation response | 1, 4 | Medium |
| 6. Frontend response handlers | 1 | Small |
| 7. Transition cards UI | 6 | Medium |
| 8. Free-form intake UI | 6 | Medium |
| 9. Parsed summary UI | 6 | Medium |
| 10. Confirmation UI | 6 | Medium |
| 11. Topic headers UI | 6 | Small |
| 12. Input bar update | — | Small |
| 13. Old code cleanup | All above | Medium |
| 14. Integration tests | All above | Medium |

**Critical path:** Tasks 1 → 2 → 3 → 5 → 6 → 7-11 (parallel) → 13 → 14
