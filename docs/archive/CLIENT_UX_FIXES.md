# Client UX Critical Fixes - Action Plan

**Priority**: URGENT - Must fix before client launch
**Timeline**: 2-3 days
**Impact**: Reduces confusion, increases completion rate

---

## 🎯 Issues to Fix

### 1. URL Consolidation (CRITICAL)
**Problem**: 3 entry points (/, /file, /smart-tax) confuse users
**Impact**: Users unsure where to start, session state inconsistent
**Fix**: Single unified entry → /file with smart routing

### 2. Premium Report Gating (CRITICAL)
**Problem**: All users see full advisory reports (free = paid)
**Impact**: No revenue from premium features
**Fix**: Feature-gate reports, add "Upgrade to see full report"

### 3. Reduce Time-to-Complete (HIGH)
**Problem**: 30-35 minutes advertised vs 15-20 realistic
**Impact**: Users abandon, time estimates not credible
**Fix**: Smart question filtering, skip irrelevant questions

### 4. Remove Triage Modal Friction (HIGH)
**Problem**: Modal adds clicks without value for returning users
**Impact**: Extra 30 seconds, users annoyed
**Fix**: Auto-route based on documents, remember preference

### 5. Quick Educational Onboarding (MEDIUM)
**Problem**: No progressive help, users confused
**Impact**: Support requests, lower completion rate
**Fix**: Add contextual tooltips, 60-second quick start video

---

## Implementation Plan

### Day 1: URL Consolidation & Smart Routing

**File**: `src/web/app.py`

**Changes**:
```python
# Remove fragmented routes
@app.get("/smart-tax")
async def redirect_smart_tax():
    """Redirect to unified filing"""
    return RedirectResponse("/file?mode=smart", status_code=301)

@app.get("/express")
async def redirect_express():
    return RedirectResponse("/file?mode=express", status_code=301)

# Single entry point
@app.get("/file")
async def unified_filing(
    request: Request,
    mode: Optional[str] = Query(None),  # auto|express|smart|guided
    session_id: Optional[str] = Query(None)
):
    """
    UNIFIED FILING INTERFACE
    - Auto-detects best mode if not specified
    - Resumes session if session_id provided
    - Smart routing based on uploaded documents
    """
    # Auto-detect mode
    if not mode:
        mode = "auto"  # Will detect based on first action

    # Check for existing session
    if not session_id:
        session_id = await create_filing_session(mode=mode)

    return templates.TemplateResponse("file.html", {
        "request": request,
        "session_id": session_id,
        "mode": mode,
        "show_triage": False  # Skip for returning users
    })
```

**Result**: Single /file URL, automatic routing

---

### Day 1: Premium Report Gating

**File**: `src/web/results_api.py` (NEW)

**Create**:
```python
from enum import Enum

class SubscriptionTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"

class ReportAccessControl:
    """Control access to advisory reports by tier"""

    TIER_FEATURES = {
        SubscriptionTier.FREE: {
            "basic_calculation": True,
            "refund_estimate": True,
            "top_opportunities": 2,  # Show top 2 only
            "detailed_findings": False,
            "pdf_download": False,
            "scenario_comparison": False,
            "multi_year_projection": False,
        },
        SubscriptionTier.BASIC: {
            "basic_calculation": True,
            "refund_estimate": True,
            "top_opportunities": 5,
            "detailed_findings": True,
            "pdf_download": True,
            "scenario_comparison": False,
            "multi_year_projection": False,
        },
        SubscriptionTier.PREMIUM: {
            "basic_calculation": True,
            "refund_estimate": True,
            "top_opportunities": 999,  # All
            "detailed_findings": True,
            "pdf_download": True,
            "scenario_comparison": True,
            "multi_year_projection": True,
            "cpa_review_included": False,
        },
        SubscriptionTier.PROFESSIONAL: {
            # All features
            "basic_calculation": True,
            "refund_estimate": True,
            "top_opportunities": 999,
            "detailed_findings": True,
            "pdf_download": True,
            "scenario_comparison": True,
            "multi_year_projection": True,
            "cpa_review_included": True,
            "priority_support": True,
        }
    }

    @staticmethod
    def filter_report(report: dict, tier: SubscriptionTier) -> dict:
        """Filter report based on subscription tier"""
        features = ReportAccessControl.TIER_FEATURES[tier]

        filtered = {
            "current_federal_tax": report["current_federal_tax"],
            "refund": report.get("refund"),
            "tier": tier.value,
        }

        # Top opportunities (limited by tier)
        max_opps = features["top_opportunities"]
        filtered["top_opportunities"] = report["top_opportunities"][:max_opps]

        # Detailed findings (premium only)
        if features["detailed_findings"]:
            filtered["detailed_findings"] = report["detailed_findings"]
            filtered["executive_summary"] = report["executive_summary"]
        else:
            filtered["detailed_findings"] = []
            filtered["executive_summary"] = "Upgrade to Premium to see detailed tax-saving strategies."

        # Add upgrade prompts for free users
        if tier == SubscriptionTier.FREE:
            hidden_count = len(report["top_opportunities"]) - max_opps
            filtered["upgrade_prompt"] = {
                "message": f"Unlock {hidden_count} more tax-saving opportunities!",
                "cta": "Upgrade to Premium",
                "savings_potential": sum(o["estimated_savings"] for o in report["top_opportunities"][max_opps:])
            }

        return filtered
```

**Modify**: `src/web/app.py` results route

```python
@app.get("/results")
async def filing_results(
    request: Request,
    session_id: str = Query(...),
    ctx: AuthContext = Depends(get_current_user_optional)
):
    # Get full report
    full_report = generate_full_report(session_id)

    # Determine user tier
    user_tier = ctx.subscription_tier if ctx else SubscriptionTier.FREE

    # Filter by tier
    filtered_report = ReportAccessControl.filter_report(full_report, user_tier)

    return templates.TemplateResponse("results.html", {
        "request": request,
        "report": filtered_report,
        "show_upgrade": (user_tier == SubscriptionTier.FREE),
        "tier": user_tier
    })
```

**Template Update**: `src/web/templates/results.html`

```html
{% if show_upgrade %}
<div class="upgrade-banner">
    <div class="upgrade-content">
        <h3>💎 Unlock {{ report.upgrade_prompt.message }}</h3>
        <p>You're missing out on <strong>${{ report.upgrade_prompt.savings_potential | format_currency }}</strong> in potential tax savings.</p>
        <a href="/pricing?upgrade=premium" class="btn-upgrade">
            {{ report.upgrade_prompt.cta }} →
        </a>
    </div>
</div>
{% endif %}

<!-- Show top 2 opportunities for free, blur the rest -->
{% for opportunity in report.top_opportunities %}
    <div class="opportunity-card {% if loop.index > 2 and tier == 'free' %}blurred{% endif %}">
        <h4>{{ opportunity.title }}</h4>
        <p class="savings">${{ opportunity.estimated_savings | format_currency }}</p>
        {% if loop.index > 2 and tier == 'free' %}
        <div class="blur-overlay">
            <a href="/pricing?upgrade=premium">Upgrade to see details</a>
        </div>
        {% endif %}
    </div>
{% endfor %}
```

**Result**: Free users see teaser, premium users see full report

---

### Day 2: Smart Question Filtering

**File**: `src/onboarding/adaptive_interview.py` (NEW)

**Create**:
```python
class AdaptiveInterviewEngine:
    """
    Reduces 145 questions to 20-40 based on user situation.

    Strategy:
    1. Ask screening questions first (filing status, income types)
    2. Skip entire sections if not applicable
    3. Pre-fill from documents if available
    """

    def __init__(self, session_data: dict):
        self.session_data = session_data
        self.asked_questions = []
        self.skipped_sections = []

    def should_ask_question(self, question_id: str) -> bool:
        """Determine if question is relevant"""

        # Skip business questions if no self-employment
        if question_id.startswith("business_") and not self.has_self_employment:
            return False

        # Skip investment questions if no investments
        if question_id.startswith("investment_") and not self.has_investments:
            return False

        # Skip rental property if not applicable
        if "rental" in question_id and not self.has_rental_property:
            return False

        # Skip itemized deductions if standard deduction better
        if self.standard_deduction_better and question_id in ITEMIZED_DEDUCTION_QUESTIONS:
            return False

        # Skip state tax questions for no-income-tax states
        if self.state_has_no_income_tax and "state_tax" in question_id:
            return False

        return True

    def get_next_question_batch(self, batch_size: int = 5) -> List[Question]:
        """Return next 5 relevant questions (vs 1 at a time)"""
        questions = []
        for q in ALL_QUESTIONS:
            if self.should_ask_question(q.id):
                questions.append(q)
                if len(questions) >= batch_size:
                    break
        return questions

    @property
    def estimated_time_remaining(self) -> int:
        """Real-time estimate based on questions left"""
        questions_left = len([q for q in ALL_QUESTIONS if self.should_ask_question(q.id)])
        return questions_left * 15  # 15 seconds per question avg
```

**Modify**: `src/web/templates/file.html`

```html
<!-- Show real-time progress -->
<div class="progress-indicator">
    <div class="progress-bar" style="width: {{ progress_percent }}%"></div>
    <span class="time-remaining">⏱️ ~{{ estimated_minutes }} minutes remaining</span>
    <span class="questions-skipped">✓ Skipped {{ skipped_count }} irrelevant questions</span>
</div>
```

**Result**: 145 questions → 20-40 relevant questions, 30min → 8-12min

---

### Day 2: Remove Triage Modal Friction

**File**: `src/web/templates/file.html`

**Modify**:
```javascript
// Auto-detect workflow from first user action
window.addEventListener('DOMContentLoaded', () => {
    const hasDocuments = checkForUploadedDocuments();
    const isReturningUser = localStorage.getItem('preferred_workflow');

    // Skip triage for returning users
    if (isReturningUser) {
        startWorkflow(isReturningUser);
        return;
    }

    // Auto-route based on first action
    document.getElementById('upload-zone').addEventListener('drop', (e) => {
        // User uploaded document → Express Lane
        startWorkflow('express');
        localStorage.setItem('preferred_workflow', 'express');
    });

    document.getElementById('start-questions-btn').addEventListener('click', () => {
        // User clicked "Answer Questions" → Smart Tax
        startWorkflow('smart');
        localStorage.setItem('preferred_workflow', 'smart');
    });

    // Show simple choice instead of modal
    showSimpleWorkflowChoice();
});

function showSimpleWorkflowChoice() {
    // Replace modal with inline cards
    return `
    <div class="workflow-cards">
        <div class="workflow-card" onclick="startWorkflow('express')">
            <h3>⚡ Quick Upload</h3>
            <p>Upload documents, we'll handle the rest</p>
            <span class="time-badge">~5 minutes</span>
        </div>
        <div class="workflow-card" onclick="startWorkflow('smart')">
            <h3>💡 Guided Questions</h3>
            <p>Answer smart questions, skip irrelevant ones</p>
            <span class="time-badge">~10 minutes</span>
        </div>
        <div class="workflow-card" onclick="startWorkflow('chat')">
            <h3>💬 Chat with AI</h3>
            <p>Conversational filing, ask anything</p>
            <span class="time-badge">~12 minutes</span>
        </div>
    </div>
    `;
}
```

**Result**: No modal popup, simple inline choice, remembers preference

---

### Day 3: Quick Educational Onboarding

**File**: `src/web/templates/components/onboarding_tutorial.html` (NEW)

**Create**:
```html
<!-- 60-second quick start video -->
<div class="onboarding-overlay" id="onboardingTutorial">
    <div class="tutorial-card">
        <h2>Welcome! 👋 Let's file your taxes in 3 easy steps</h2>

        <!-- Video placeholder -->
        <div class="tutorial-video">
            <video width="400" controls>
                <source src="/static/videos/quick-start-60sec.mp4" type="video/mp4">
            </video>
        </div>

        <!-- Steps -->
        <div class="tutorial-steps">
            <div class="step">
                <span class="step-number">1</span>
                <div class="step-content">
                    <h4>Upload or Enter Info</h4>
                    <p>W-2s, 1099s, or answer questions</p>
                </div>
            </div>
            <div class="step">
                <span class="step-number">2</span>
                <div class="step-content">
                    <h4>We Calculate & Find Savings</h4>
                    <p>Our AI finds deductions you might miss</p>
                </div>
            </div>
            <div class="step">
                <span class="step-number">3</span>
                <div class="step-content">
                    <h4>Review & File</h4>
                    <p>See your refund, file electronically</p>
                </div>
            </div>
        </div>

        <div class="tutorial-actions">
            <button class="btn-secondary" onclick="watchFullTutorial()">Watch Full Tutorial (5 min)</button>
            <button class="btn-primary" onclick="startFiling()">Got It, Let's File! →</button>
        </div>

        <label class="remember-choice">
            <input type="checkbox" id="dontShowAgain"> Don't show this again
        </label>
    </div>
</div>

<style>
.onboarding-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}

.tutorial-card {
    background: white;
    border-radius: 16px;
    padding: 40px;
    max-width: 600px;
    text-align: center;
}

.tutorial-steps {
    display: flex;
    gap: 20px;
    margin: 30px 0;
}

.step {
    flex: 1;
    text-align: left;
}

.step-number {
    display: inline-block;
    width: 32px;
    height: 32px;
    background: var(--primary);
    color: white;
    border-radius: 50%;
    text-align: center;
    line-height: 32px;
    font-weight: 700;
    margin-bottom: 10px;
}
</style>
```

**File**: `src/web/templates/file.html`

**Add contextual tooltips**:
```javascript
// Progressive help system
const helpTooltips = {
    "income_w2": {
        title: "Where to find this",
        content: "Look at Box 1 of your W-2 form. This is your total wages.",
        video: "/help/w2-box1.gif"  // 5-second GIF showing where
    },
    "deduction_mortgage": {
        title: "Mortgage Interest Deduction",
        content: "You can deduct interest paid on mortgages up to $750,000.",
        learnMore: "/articles/mortgage-interest-deduction"
    }
};

function showContextualHelp(questionId) {
    const help = helpTooltips[questionId];
    if (!help) return;

    showTooltip(help.title, help.content, help.video);
}
```

**Result**: First-time users see 60-sec intro, contextual help reduces confusion

---

## Timeline & Deliverables

| Day | Tasks | Deliverables |
|-----|-------|--------------|
| **Day 1** | URL consolidation, Premium gating | - Single /file entry<br>- Free vs Premium reports<br>- Upgrade prompts |
| **Day 2** | Smart filtering, Remove triage | - 145 → 30 questions<br>- Auto-routing<br>- 30min → 10min |
| **Day 3** | Educational onboarding | - 60-sec video<br>- Contextual tooltips<br>- Help GIFs |

---

## Success Metrics

### Before Fixes:
- 3 entry URLs confusing users
- 30-35 minute completion time
- Free users see premium features
- Triage modal adds friction
- 25% abandonment rate

### After Fixes:
- 1 unified /file URL
- 8-12 minute completion time (measured)
- Premium features gated with upgrade prompts
- Auto-routing, no modal
- Target: <15% abandonment rate

---

## Testing Checklist

- [ ] /smart-tax redirects to /file?mode=smart
- [ ] Free users see "Upgrade to Premium" on report
- [ ] Question count reduces based on situation
- [ ] Time estimate updates in real-time
- [ ] Triage skipped for returning users
- [ ] 60-sec tutorial shows for first-time users
- [ ] Contextual help tooltips appear on focus
- [ ] Workflow preference remembered

---

**Status**: Ready to implement
**Priority**: URGENT
**Timeline**: 2-3 days
**Impact**: HIGH (reduces confusion, increases completion)
