# World-Class Tax Advisory Platform — 10 Features Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the tax advisory chatbot from a data collection tool into the world's best AI tax advisory experience — with live tax estimates, smart defaults, proactive advice, cascading skips, document auto-fill, multi-field extraction, emotional intelligence, comparison scenarios, progress confidence, and multi-year awareness.

**Architecture:** All 10 features integrate into the existing hybrid flow. The backend response model (ChatResponse) gains new fields. The tax calculation engine (FederalTaxEngine) is called partially during collection, not just at the end. The frontend's LiveSavingsDisplay already exists and is extended. No new services needed — everything builds on existing infrastructure.

**Tech Stack:** Python/FastAPI, FederalTaxEngine, NLU parser, existing JS modules, DM Sans + charcoal/amber design system.

---

## Existing Infrastructure We Build On

| Feature | Existing Code | Status |
|---------|--------------|--------|
| Partial tax estimate | `estimate_partial_savings()` in ChatEngine | Exists but basic — only retirement/HSA gaps |
| Profile completeness | `calculate_profile_completeness()` | Exists — 3-tier scoring |
| Live savings display | `LiveSavingsDisplay` class in advisor-display.js | Exists — shows savings estimate in UI |
| Savings update | `updateSavingsEstimate()` in advisor-chat.js | Exists — called after certain responses |
| Withholding auto-estimate | `_withholding_auto_estimate` flag | Exists — flag set but logic incomplete |
| OCR/Document upload | `upload_document()` endpoints, `OCREngine` | Exists — not wired into chat flow |
| Frustration detection | `frustrated_patterns` regex matching | Exists — returns help message |
| FederalTaxEngine | Full async tax calculator with 762 scenarios | Exists — called only at end |
| State calculators | 50+ state calculators | Exists |
| Enhanced parser | `enhanced_parse_user_message()` | Exists — extracts multiple fields |

---

## FEATURE 1: Live Tax Estimate (Real-Time Refund Counter)

### What it does
After every answer that affects tax (income, deductions, credits, withholding), run a quick partial calculation and return the estimate in every ChatResponse. Frontend shows a persistent banner: "Estimated refund: ~$3,247" or "Estimated owed: ~$1,200" that updates live.

### Files to modify
- `src/web/intelligent_advisor_api.py` — call partial calc after profile updates
- `src/web/advisor/models.py` — add `live_estimate` fields to ChatResponse
- `src/calculator/engine.py` — add `quick_estimate()` method (simplified, fast)
- `src/web/static/js/advisor/modules/advisor-display.js` — render live estimate banner
- `src/web/templates/intelligent_advisor.html` — CSS for estimate banner

### Implementation

**ChatResponse additions:**
```python
# Live tax estimate (updates with every answer)
live_tax_estimate: Optional[float] = None  # Positive = refund, negative = owed
live_estimate_confidence: str = "low"  # "low", "medium", "high"
live_estimate_label: Optional[str] = None  # "Estimated refund: ~$3,247"
```

**Backend logic (in intelligent_chat, after profile update):**
```python
# After every profile update that affects tax numbers
_tax_affecting_fields = {
    "total_income", "business_income", "federal_withholding", "state_withholding",
    "investment_income", "rental_income", "k1_ordinary_income", "mortgage_interest",
    "property_taxes", "charitable_donations", "retirement_401k", "retirement_ira",
    "hsa_contributions", "estimated_payments", "childcare_costs", "dependents_under_17",
    "ss_benefits", "farm_income", "side_income",
}
_changed_tax_fields = set(updates.keys()) & _tax_affecting_fields
if _changed_tax_fields and profile.get("total_income") and profile.get("filing_status"):
    estimate = _quick_tax_estimate(profile)
    # Include in response
```

**Quick estimate function:**
```python
def _quick_tax_estimate(profile: dict) -> dict:
    """Fast partial tax estimate from available profile data. Returns {amount, confidence, label}."""
    income = float(profile.get("total_income", 0) or 0)
    status = profile.get("filing_status", "single")

    # Standard deduction (default unless itemizing)
    std_deduction = {"single": 15000, "married_joint": 30000, "head_of_household": 22500,
                     "married_separate": 15000, "qualifying_widow": 30000}.get(status, 15000)

    # Itemized if we know enough
    itemized = sum(float(profile.get(f, 0) or 0) for f in [
        "mortgage_interest", "property_taxes", "charitable_donations", "medical_expenses"
    ])
    # SALT cap
    salt = min(float(profile.get("property_taxes", 0) or 0) + float(profile.get("state_local_taxes", 0) or 0), 10000)

    deduction = max(std_deduction, itemized)

    # Above-the-line: retirement, HSA, SE tax, student loans
    above_line = sum(float(profile.get(f, 0) or 0) for f in [
        "retirement_401k", "retirement_ira", "hsa_contributions",
    ])
    if profile.get("is_self_employed"):
        se_income = float(profile.get("business_income", 0) or 0)
        above_line += se_income * 0.0765  # 50% of SE tax

    taxable = max(0, income - deduction - above_line)

    # Progressive tax (simplified 2025 brackets)
    tax = _calc_progressive_tax(taxable, status)

    # Credits
    credits = 0
    under_17 = int(profile.get("dependents_under_17", 0) or 0)
    credits += under_17 * 2000  # CTC
    if profile.get("childcare_costs"):
        credits += min(float(profile.get("childcare_costs", 0) or 0), 3000) * 0.2
    if profile.get("energy_credits") == "has_solar" and profile.get("solar_cost"):
        credits += float(profile.get("solar_cost", 0) or 0) * 0.30

    net_tax = max(0, tax - credits)

    # Payments
    payments = sum(float(profile.get(f, 0) or 0) for f in [
        "federal_withholding", "estimated_payments",
    ])

    refund_or_owed = payments - net_tax  # Positive = refund

    # Confidence based on data completeness
    confidence = "low"
    if profile.get("federal_withholding"):
        confidence = "medium"
    if profile.get("federal_withholding") and (profile.get("_asked_deductions") or profile.get("_deduction_check")):
        confidence = "high"

    label = f"Estimated refund: ~${abs(refund_or_owed):,.0f}" if refund_or_owed >= 0 else f"Estimated owed: ~${abs(refund_or_owed):,.0f}"

    return {"amount": round(refund_or_owed), "confidence": confidence, "label": label}
```

**Frontend: Sticky estimate banner**
```javascript
// In processAIResponse, after handling response types:
if (data.live_tax_estimate != null) {
    updateLiveEstimate(data.live_tax_estimate, data.live_estimate_confidence, data.live_estimate_label);
}
```
```css
.live-estimate-banner {
    position: sticky; top: 0; z-index: 100;
    background: var(--ink); color: var(--parchment);
    padding: 10px 20px; display: flex; justify-content: space-between;
    align-items: center; border-radius: 0 0 var(--radius) var(--radius);
}
.live-estimate-amount { font-family: var(--mono); font-size: 1.3rem; font-weight: 700; }
.live-estimate-amount.refund { color: #4ade80; }
.live-estimate-amount.owed { color: #f87171; }
.live-estimate-confidence { font-size: 0.75rem; opacity: 0.7; }
```

---

## FEATURE 2: Smart Defaults (Pre-fill from Profile)

### What it does
Instead of asking "How much was withheld?", say "Your federal withholding is probably around $9,500 based on your income — does that sound right?" with [Yes, that's close] [No, let me enter it] buttons.

### Implementation
Add `_estimate_smart_default()` that calculates reasonable defaults for:
- Federal withholding (from income + filing status + exemptions)
- State withholding (from income + state rate)
- Standard deduction vs itemized (auto-recommend)
- Retirement contributions (common amounts by age/income)
- HSA contributions (max based on coverage type)

```python
def _estimate_smart_default(field: str, profile: dict) -> Optional[dict]:
    """Return estimated default value + explanation for a field."""
    income = float(profile.get("total_income", 0) or 0)
    status = profile.get("filing_status", "single")

    if field == "federal_withholding":
        # Estimate using simplified effective rate
        rate = _estimate_effective_rate(income, status)
        est = round(income * rate / 100) * 100  # Round to nearest $100
        return {
            "value": est,
            "explanation": f"Based on ${income:,.0f} income filing {status.replace('_',' ')}, your withholding is probably around ${est:,.0f}",
            "actions": [
                {"label": f"Yes, ~${est:,.0f} sounds right", "value": f"withholding_smart_{est}"},
                {"label": "No, let me enter the exact amount", "value": "withholding_manual"},
                {"label": "Not sure — estimate for me", "value": "withholding_estimate"},
            ]
        }
    # ... similar for state_withholding, retirement, HSA
```

Then in `_get_dynamic_next_question`, before asking withholding:
```python
if is_w2 and not profile.get("federal_withholding") and not profile.get("_asked_withholding"):
    smart = _estimate_smart_default("federal_withholding", profile)
    if smart:
        return (smart["explanation"], smart["actions"])
```

---

## FEATURE 3: Proactive Advice During Collection

### What it does
After certain answers, insert a brief advisory insight BEFORE the next question. Not just "Got it" — actual tax intelligence.

### Implementation
Add `_get_proactive_advice()` that returns advice based on what was just answered:

```python
PROACTIVE_ADVICE = {
    # (condition, advice_text)
    "high_mortgage_and_property_tax": (
        lambda p: float(p.get("mortgage_interest",0) or 0) + float(p.get("property_taxes",0) or 0) > 15000,
        "💡 With ${total:,.0f} in mortgage interest + property taxes, you'll likely save more by itemizing than taking the standard deduction."
    ),
    "se_no_estimated": (
        lambda p: p.get("is_self_employed") and float(p.get("business_income",0) or 0) > 30000 and not p.get("estimated_payments"),
        "⚠️ As self-employed with significant income, you may owe estimated tax penalties if you haven't made quarterly payments."
    ),
    "ctc_eligible": (
        lambda p: int(p.get("dependents_under_17",0) or 0) > 0,
        "💰 With {n} child(ren) under 17, you qualify for ${amount:,.0f} in Child Tax Credits!"
    ),
    "retirement_gap": (
        lambda p: float(p.get("retirement_401k",0) or 0) > 0 and float(p.get("retirement_401k",0) or 0) < 23500 and float(p.get("total_income",0) or 0) > 75000,
        "💡 You're contributing ${current:,.0f} to your 401(k), but the max is $23,500. Increasing could save ~${savings:,.0f} in taxes."
    ),
    "salt_cap_hit": (
        lambda p: float(p.get("property_taxes",0) or 0) >= 10000,
        "⚠️ Your property taxes alone hit the $10,000 SALT cap. Additional state/local taxes won't provide extra deductions."
    ),
    "solar_credit": (
        lambda p: p.get("energy_credits") in ("has_solar", "multiple_energy") and p.get("solar_cost"),
        "🎉 Your solar installation qualifies for a 30% credit — that's ~${credit:,.0f} off your tax bill!"
    ),
    "eitc_eligible": (
        lambda p: p.get("eitc_status") == "eitc_likely",
        "💰 Great news — you likely qualify for the Earned Income Tax Credit! This could mean ${range} back."
    ),
    "backdoor_roth_opportunity": (
        lambda p: float(p.get("total_income",0) or 0) > 150000 and not p.get("backdoor_roth") and p.get("retirement_ira"),
        "💡 At your income level, a Backdoor Roth IRA could let you contribute to a Roth despite being over the income limit."
    ),
}
```

Advice is inserted as a prefix to the next question's response text: `ack = advice + "\n\n" + next_question`

---

## FEATURE 4: Cascade Skip Logic

### What it does
When user answers "No investments", automatically skip ALL investment follow-ups (crypto, wash sales, NIIT, stock options, capital gains, collectibles, etc.) without showing each one.

### Implementation
Add skip cascades to `_quick_action_map`:

```python
"no_investments": {
    "_asked_investments": True, "investment_income": 0,
    # CASCADE: skip all investment follow-ups
    "_asked_invest_amount": True, "_asked_cap_gains": True,
    "_asked_crypto": True, "_asked_stock_comp": True,
    "_asked_wash_sale": True, "_asked_niit": True,
    "_asked_installment": True, "_asked_1031": True,
    "_asked_qsbs": True, "_asked_qoz": True,
    "_asked_collectibles": True, "_asked_inv_interest": True,
    "_asked_passive_carryforward": True, "_asked_section_1256": True,
    "_asked_mlp": True, "_asked_espp_disp": True, "_asked_iso_amt": True,
    "_asked_oid": True,
},
"no_retirement": {
    "_asked_retirement": True, "retirement_401k": 0, "retirement_ira": 0,
    # CASCADE
    "_asked_backdoor_roth": True, "_asked_ira_basis": True,
    "_asked_catch_up": True, "_asked_mega_backdoor": True,
    "_asked_ira_deduct": True, "_asked_savers_credit": True,
},
"no_rental": {
    "_asked_rental": True, "_has_rental": "no_rental", "rental_income": 0,
    # CASCADE
    "_asked_rental_amount": True, "_asked_participation": True,
    "_asked_short_term": True, "_asked_personal_use": True,
    "_asked_below_fmv": True, "_asked_cost_seg": True,
    "_asked_rental_convert": True, "_asked_rental_loss_allow": True,
},
"no_life_events": {
    "life_events": "no_life_events", "_asked_life_events": True,
    # CASCADE
    "_asked_home_sale": True, "_asked_home_gain": True,
    "_asked_partial_exclusion": True, "_asked_state_move": True,
    "_asked_job_loss": True, "_asked_startup": True,
    "_asked_mfj_mfs": True, "_asked_divorce_year": True,
    "_asked_qdro": True, "_asked_inheritance_type": True,
    "_asked_job_401k": True, "_asked_spouse_death": True,
    "_asked_mortgage_points": True, "_asked_first_home_ira": True,
},
```

This alone will cut 20-40 questions for simple filers.

---

## FEATURE 5: Document Upload → Auto-Fill

### What it does
After income type is selected, offer: "Want to upload your W-2? I'll fill in the details automatically." If uploaded, OCR extracts fields and pre-fills 10-15 profile fields.

### Implementation
Add a new response type `document_offer` after income type is collected:
```python
if income_type in ("w2_employee", "multiple_w2") and not profile.get("_doc_offer_shown"):
    profile["_doc_offer_shown"] = True
    return ChatResponse(
        response_type="document_offer",
        response="Want to upload your W-2? I can extract your income, withholding, and other details automatically.",
        quick_actions=[
            {"label": "Upload W-2", "value": "upload_w2"},
            {"label": "I'll enter manually", "value": "skip_upload"},
        ],
    )
```

When document is uploaded, call existing OCR pipeline and map extracted fields to profile.

---

## FEATURE 6: Multi-Field Extraction Acknowledgment

### What it does
When user answers a question with extra info ("I make $120k and my wife makes $80k, we have 2 kids"), the system extracts ALL mentioned fields and shows: "I also noticed you mentioned: spouse income ~$80K, 2 dependents. I've captured those too."

### Implementation
In the enhanced parsing section (after `_quick_action_handled`), after extracting fields:
```python
# Count how many EXTRA fields were extracted beyond what was asked
extra_fields = {k: v for k, v in extracted.items()
                if not k.startswith("_") and k not in asked_field_set}
if len(extra_fields) > 0:
    ack_parts = []
    for field, value in extra_fields.items():
        display = f"${value:,.0f}" if isinstance(value, (int, float)) else str(value)
        ack_parts.append(f"{field.replace('_',' ')}: {display}")
    multi_ack = "I also noticed you mentioned: " + ", ".join(ack_parts) + ". I've captured those too.\n\n"
    # Prepend to next question
```

---

## FEATURE 7: Emotional Intelligence / Adaptive Complexity

### What it does
Detect user frustration/confusion and adapt: simplify language, offer explanations, reduce question count, provide a "help me understand" mode.

### Implementation
Extend existing `frustrated_patterns` detection:
```python
if is_frustrated:
    profile["_complexity_level"] = "simple"
    return ChatResponse(
        response="I understand this can feel overwhelming. Let me simplify things.\n\nYou can say 'explain' anytime you need a term explained, or 'skip ahead' to jump to the calculation with what we have so far.",
        response_type="help",
        quick_actions=[
            {"label": "Continue with simpler questions", "value": "simplify_mode"},
            {"label": "Skip ahead to calculation", "value": "skip_deep_dive"},
            {"label": "I'm fine, let's continue", "value": "continue_normal"},
        ],
    )
```

When `_complexity_level == "simple"`:
- Add plain-English explanations to every question
- Skip niche questions (AMT, PFIC, Section 1256, etc.)
- Use friendlier language ("How much tax was taken from your paycheck?" vs "Federal withholding amount")

---

## FEATURE 8: Comparison Scenarios (MFJ vs MFS, Itemize vs Standard)

### What it does
At key decision points, calculate BOTH options and show side-by-side comparison.

### Implementation
Two comparison triggers:

**MFJ vs MFS (for married filers):**
```python
if filing_status == "married_joint" and profile.get("mfj_mfs_preference") == "compare":
    mfj_tax = _quick_tax_estimate({**profile, "filing_status": "married_joint"})
    mfs_tax = _quick_tax_estimate({**profile, "filing_status": "married_separate"})
    return ChatResponse(
        response_type="comparison",
        response="Here's how your filing options compare:",
        metadata={
            "comparison": {
                "option_a": {"label": "Married Filing Jointly", "tax": mfj_tax["amount"]},
                "option_b": {"label": "Married Filing Separately", "tax": mfs_tax["amount"]},
                "recommendation": "MFJ" if mfj_tax["amount"] >= mfs_tax["amount"] else "MFS",
                "savings": abs(mfj_tax["amount"] - mfs_tax["amount"]),
            }
        },
    )
```

**Itemize vs Standard (after deductions collected):**
Automatically compare and advise after deduction block completes.

---

## FEATURE 9: Progress Confidence Score

### What it does
Show: "Based on what you've told me, I'm 73% confident in my estimate. These remaining questions will improve accuracy." Updates with every answer.

### Implementation
Already have `calculate_profile_completeness()`. Extend to return a confidence message:
```python
def get_confidence_message(completeness: float) -> str:
    if completeness < 0.3:
        return f"I'm {int(completeness*100)}% through your profile — the estimate will get much more accurate as we continue."
    elif completeness < 0.6:
        return f"We're {int(completeness*100)}% complete — estimate is getting reliable."
    elif completeness < 0.9:
        return f"Almost there — {int(completeness*100)}% complete. Just a few more details for maximum accuracy."
    else:
        return "Your profile is complete — I have high confidence in the calculation."
```

Include in every ChatResponse alongside `profile_completeness`.

---

## FEATURE 10: Multi-Year Awareness

### What it does
Ask about prior year carryforwards: capital losses, NOL, AMT credit, excess contributions. Also ask "Did you get a refund last year?" (already have this question) and use the answer to contextualize advice.

### Implementation
Already partially implemented:
- `inv_loss_carryforward` question exists
- `nol_carryforward` question exists
- `prior_year_return` question exists in Block O

Extend with:
```python
# After prior_year_return is answered
if profile.get("prior_year_return") == "owed":
    # Proactive advice
    advice = "Since you owed last year, let's make sure your withholding/estimated payments are adequate this year to avoid penalties."
```

Also add questions:
- Prior year AMT credit carryforward
- Prior year charitable contribution carryforward
- Prior year passive loss carryforward (already exists)

---

## Execution Order (dependency chain)

| # | Feature | Depends On | Effort | Impact |
|---|---------|-----------|--------|--------|
| 4 | Cascade Skip Logic | — | Small | High (fewer Qs) |
| 1 | Live Tax Estimate | — | Large | Highest |
| 2 | Smart Defaults | Feature 1 (uses same calc) | Medium | High |
| 6 | Multi-Field Extraction | — | Small | Medium |
| 3 | Proactive Advice | Feature 1 (uses tax numbers) | Medium | High |
| 9 | Progress Confidence | — | Small | Medium |
| 7 | Emotional Intelligence | — | Medium | Medium |
| 8 | Comparison Scenarios | Feature 1 (uses calc) | Medium | High |
| 5 | Document Upload | OCR exists | Medium | High |
| 10 | Multi-Year Awareness | — | Small | Medium |

**Critical path:** 4 → 1 → 2 → 3 → 8 (cascade → live estimate → defaults → advice → comparisons)
**Parallel:** 6, 9, 7, 10 (independent of each other)
