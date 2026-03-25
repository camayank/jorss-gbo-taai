# Four-Track Platform Remediation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the most critical and feasible issues across tax accuracy, AI advisory, CPA workflow, and platform security — in priority order within each track.

**Architecture:** Each track is independent and can be parallelized. Within each track, tasks are ordered by severity and feasibility (quick wins first). Every task includes exact file paths, line numbers, and code changes.

**Tech Stack:** Python/FastAPI backend, Jinja2 templates, Alpine.js frontend, SQLite/PostgreSQL, OpenAI/Claude/Gemini AI providers.

---

## Track 1: Tax Domain Accuracy (14 tasks)

These bugs produce wrong tax numbers. Fix first.

---

### Task 1.1: Fix stale 2024 brackets in 3 web estimator paths

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:1385-1387` and `:3743-3750`
- Modify: `src/web/guided_filing_api.py:468-475`
- Modify: `src/web/filing_package_api.py:377-384`

**Step 1: Update intelligent_advisor_api.py brackets**

Replace 2024 MFJ brackets at line 1385:
```python
# OLD: brackets = [(23200, .10), (94300, .12), (201050, .22), (383900, .24), (487450, .32), (731200, .35)]
# NEW (2025 per Rev. Proc. 2024-40):
brackets = [(23850, .10), (96950, .12), (206700, .22), (394600, .24), (501050, .32), (751600, .35)]
```

Replace 2024 Single brackets at line 1387:
```python
# OLD: brackets = [(11600, .10), (47150, .12), (100525, .22), (191950, .24), (243725, .32), (609350, .35)]
# NEW:
brackets = [(11925, .10), (48475, .12), (103350, .22), (197300, .24), (250525, .32), (626350, .35)]
```

Apply same fix at lines 3743-3750.

**Step 2: Update guided_filing_api.py brackets**

At lines 468-475, replace all 2024 threshold values with 2025:
```python
if income <= 11925:
    return income * 0.10
elif income <= 48475:
    return 1192.50 + (income - 11925) * 0.12
elif income <= 103350:
    return 5578.50 + (income - 48475) * 0.22
elif income <= 197300:
    return 17651.00 + (income - 103350) * 0.24
elif income <= 250525:
    return 40199.00 + (income - 197300) * 0.32
elif income <= 626350:
    return 57231.00 + (income - 250525) * 0.35
else:
    return 188769.75 + (income - 626350) * 0.37
```

**Step 3: Update filing_package_api.py brackets**

Apply same 2025 values at lines 377-384.

**Step 4: Commit**
```
fix: update 2024 brackets to 2025 in 3 web estimator paths (Rev. Proc. 2024-40)
```

---

### Task 1.2: Fix AMT standard deduction addback

**Files:**
- Modify: `src/calculator/engine.py:1305-1354`

**Step 1: Fix AMT calculation**

In the `_calculate_amt` method, find the section where AMTI adjustments are computed (around line 1335). Add standard deduction addback:

```python
# After computing initial AMTI from taxable income, add back standard deduction
# IRC 56(b)(1)(E) - standard deduction is not allowed for AMT
if not breakdown.uses_itemized_deductions:
    standard_ded = self.config.standard_deductions.get(filing_status, 0)
    amti += standard_ded
    amt_result['standard_deduction_addback'] = standard_ded
```

This must go BEFORE the AMT exemption is applied but AFTER the initial AMTI is set from taxable income.

**Step 2: Commit**
```
fix: add AMT standard deduction addback per IRC 56(b)(1)(E)
```

---

### Task 1.3: Fix ACTC formula — add Schedule 8812 earned income test

**Files:**
- Modify: `src/calculator/engine.py:2320-2323`

**Step 1: Replace ACTC calculation**

Replace lines 2320-2323:
```python
# OLD (wrong - ignores earned income requirement):
# result['additional_child_tax_credit'] = min(
#     unused_ctc,
#     self.config.child_tax_credit_refundable * num_children
# )

# NEW (Schedule 8812 formula per IRC 24(d)):
earned_income = tax_return.income.get_total_earned_income()
earned_income_excess = max(0, earned_income - 2500)
actc_from_earned = earned_income_excess * 0.15

# Cap at unused nonrefundable CTC and per-child refundable limit
max_refundable = self.config.child_tax_credit_refundable * num_children
result['additional_child_tax_credit'] = min(
    unused_ctc,
    max_refundable,
    actc_from_earned
)
```

**Step 2: Commit**
```
fix: implement Schedule 8812 ACTC formula with earned income test (IRC 24(d))
```

---

### Task 1.4: Fix SEP-IRA limit ($69,000 -> $70,000)

**Files:**
- Modify: `src/calculator/tax_year_config.py:78`

**Step 1: Update limit**
```python
# OLD: sep_ira_limit: float = 69000.0
# NEW (Notice 2024-80):
sep_ira_limit: float = 70000.0
```

**Step 2: Grep and fix all other occurrences**
```bash
grep -rn "69000" src/ --include="*.py" --include="*.yaml"
```
Update every occurrence that refers to SEP-IRA / defined contribution limit.

**Step 3: Commit**
```
fix: update SEP-IRA limit to $70,000 for 2025 (Notice 2024-80)
```

---

### Task 1.5: Fix Additional Medicare Tax — include K-1 SE income

**Files:**
- Modify: `src/calculator/engine.py:1200-1232`

**Step 1: Add K-1 SE income to the calculation**

In `_calculate_additional_medicare_tax`, find where SE income is gathered (around line 1220). Add K-1 SE income:

```python
# Gather ALL self-employment income sources
se_income = tax_return.income.get_schedule_c_se_income()
# Add K-1 SE income from partnerships (Box 14)
k1_se = sum(
    getattr(k1, 'self_employment_earnings', 0) or 0
    for k1 in getattr(tax_return.income, 'k1_forms', [])
)
total_se_for_medicare = se_income + k1_se
```

**Step 2: Commit**
```
fix: include K-1 SE income in Additional Medicare Tax per IRC 3101(b)(2)
```

---

### Task 1.6: Fix EITC phaseout — use rate-based calculation

**Files:**
- Modify: `src/calculator/engine.py:2654-2657`

**Step 1: Replace linear interpolation with rate-based phaseout**

```python
# OLD (linear interpolation - wrong):
# phaseout_range = phaseout_end - phaseout_start
# excess = income_for_eitc - phaseout_start
# reduction_pct = excess / phaseout_range if phaseout_range > 0 else 1
# credit = max_credit * (1 - reduction_pct)

# NEW (rate-based per Pub 596):
EITC_PHASEOUT_RATES = {0: 0.0765, 1: 0.1598, 2: 0.2106, 3: 0.2106}
phaseout_rate = EITC_PHASEOUT_RATES.get(min(num_children, 3), 0.2106)
excess = max(0, income_for_eitc - phaseout_start)
reduction = excess * phaseout_rate
credit = max(0, max_credit - reduction)
```

**Step 2: Commit**
```
fix: use IRS rate-based EITC phaseout instead of linear interpolation (Pub 596)
```

---

### Task 1.7: Fix EITC investment income limit ($11,600 -> $11,950)

**Files:**
- Modify: `src/onboarding/contradiction_detector.py:423`
- Modify: `src/onboarding/tax_skip_rules.py:46,105,125`

**Step 1: Update contradiction_detector.py**
```python
# Line 423: Change 11600 to 11950
if claiming_eitc and investment_income and investment_income > 11950:
```
Also update the message string.

**Step 2: Update tax_skip_rules.py**
```python
# Line 46:
EITC_INVESTMENT_INCOME_LIMIT = Decimal("11950")
# Lines 105, 125: change 11600 to 11950
```

**Step 3: Commit**
```
fix: update EITC investment income limit to $11,950 for 2025 (Rev. Proc. 2024-40)
```

---

### Task 1.8: Fix Georgia flat rate (5.39% -> 5.49%)

**Files:**
- Modify: `src/calculator/state/configs/state_2025/georgia.py:24`

**Step 1: Fix rate**
```python
# OLD: flat_rate=0.0539,
# NEW (Ga. Code 48-7-20):
flat_rate=0.0549,  # 5.49% flat rate (HB 1437, effective 2024)
```

**Step 2: Commit**
```
fix: correct Georgia flat tax rate to 5.49% for 2025 (Ga. Code 48-7-20)
```

---

### Task 1.9: Fix California standard deduction (2023 -> 2025 amounts)

**Files:**
- Modify: `src/calculator/state/configs/state_2025/california.py:84-88`

**Step 1: Update deduction values**
```python
# NEW (FTB Pub 1005, 2025):
"single": 5540,
"married_joint": 11080,
"married_separate": 5540,
"head_of_household": 11080,
"qualifying_widow": 11080,
```

**Step 2: Commit**
```
fix: update California standard deduction to 2025 amounts (FTB Pub 1005)
```

---

### Task 1.10: Fix deduction detector marginal rate — use filing-status brackets

**Files:**
- Modify: `src/smart_tax/deduction_detector.py:632-642`

**Step 1: Add MFJ brackets and dispatch by filing status**
```python
def _get_marginal_rate(self, income: Decimal, filing_status: str) -> Decimal:
    """Get estimated marginal tax rate using correct filing status brackets."""
    BRACKETS = {
        "single": [(11925, "0.10"), (48475, "0.12"), (103350, "0.22"),
                   (197300, "0.24"), (250525, "0.32"), (626350, "0.35")],
        "married_filing_jointly": [(23850, "0.10"), (96950, "0.12"), (206700, "0.22"),
                                   (394600, "0.24"), (501050, "0.32"), (751600, "0.35")],
        "head_of_household": [(17000, "0.10"), (64850, "0.12"), (103350, "0.22"),
                              (197300, "0.24"), (250500, "0.32"), (626350, "0.35")],
    }
    brackets = BRACKETS.get(filing_status, BRACKETS["single"])
    standard = self.STANDARD_DEDUCTIONS_2025.get(filing_status, Decimal("15750"))
    taxable = max(income - standard, Decimal("0"))

    for threshold, rate in brackets:
        if taxable <= threshold:
            return Decimal(rate)
    return Decimal("0.37")
```

**Step 2: Commit**
```
fix: use filing-status-specific brackets in deduction detector marginal rate
```

---

### Task 1.11: Add unrecaptured Section 1250 gain (25% rate) to capital gains calc

**Files:**
- Modify: `src/calculator/engine.py` — find `_compute_preferential_tax` method

**Step 1: Add 25% rate tier**

In the preferential rate computation, before applying the 0%/15%/20% rates, carve out unrecaptured §1250 gain:

```python
# In _compute_preferential_tax, before the standard LTCG rate tiers:
unrecaptured_1250 = breakdown.schedule_d_unrecaptured_1250 or 0
if unrecaptured_1250 > 0:
    # Tax unrecaptured 1250 gain at max 25% (IRC 1(h)(1)(D))
    tax_1250 = min(unrecaptured_1250, remaining_preferential) * min(0.25, marginal_rate)
    preferential_tax += tax_1250
    remaining_preferential -= min(unrecaptured_1250, remaining_preferential)
```

**Step 2: Commit**
```
fix: apply 25% rate to unrecaptured Section 1250 gain per IRC 1(h)(1)(D)
```

---

### Task 1.12: Fix NIIT — respect PAL limitations on rental income

**Files:**
- Modify: `src/calculator/engine.py:1270-1271`

**Step 1: Add PAL awareness to NIIT rental calc**

```python
# OLD: max(0, inc.rental_income - inc.rental_expenses)
# NEW: Only include rental income that is not disallowed by PAL rules
net_rental = inc.rental_income - inc.rental_expenses
if net_rental > 0:
    nii += net_rental
# Rental losses: only include if PAL rules allow (per Treas. Reg. 1.1411-4(f))
# Suspended passive losses are excluded from NII
elif hasattr(breakdown, 'allowed_passive_losses'):
    nii += max(net_rental, -breakdown.allowed_passive_losses)
```

**Step 2: Commit**
```
fix: respect PAL limitations in NIIT rental income calc (Treas. Reg. 1.1411-4(f))
```

---

### Task 1.13: Fix QBI — subtract SE tax deduction from QBI

**Files:**
- Modify: `src/calculator/qbi_calculator.py:141-154`

**Step 1: Reduce QBI by SE tax deduction and health insurance**

```python
# After computing se_net from Schedule C:
se_net = se_income - se_expenses

# Per Treas. Reg. 1.199A-3(b)(1)(ii)(C)-(D):
# QBI must be reduced by the deductible portion of SE tax
# and self-employed health insurance deduction
se_tax_deduction = getattr(breakdown, 'se_tax_deduction', 0) or 0
se_health_deduction = getattr(breakdown, 'se_health_insurance_deduction', 0) or 0
qbi_from_schedule_c = se_net - se_tax_deduction - se_health_deduction
```

**Step 2: Commit**
```
fix: reduce QBI by SE tax deduction per Treas. Reg. 1.199A-3(b)(1)(ii)
```

---

### Task 1.14: Update Form 8995 docstring thresholds

**Files:**
- Modify: `src/models/form_8995.py:8-9`

**Step 1: Fix docstring**
```python
# OLD: "$182,100 (single) or $364,200 (MFJ) for 2024"
# NEW:
# "$197,300 (single) or $394,600 (MFJ) for 2025"
```

**Step 2: Commit**
```
fix: update Form 8995 docstring to 2025 QBI thresholds
```

---

## Track 2: AI Tax Advisory (10 tasks)

---

### Task 2.1: Add mandatory Circular 230 disclaimer to all AI outputs

**Files:**
- Create: `src/advisory/disclaimer.py`
- Modify: `src/advisory/ai_narrative_generator.py`
- Modify: `src/advisory/report_summarizer.py`

**Step 1: Create disclaimer module**
```python
"""Mandatory disclaimer for AI-generated tax content (Circular 230 compliance)."""

CIRCULAR_230_DISCLAIMER = (
    "IMPORTANT: This analysis was generated by AI and is for informational purposes only. "
    "It does not constitute tax advice under Treasury Circular 230. Consult a licensed "
    "tax professional before making any tax decisions based on this information."
)

SHORT_DISCLAIMER = "AI-generated estimate. Not professional tax advice."


def wrap_with_disclaimer(content: str, short: bool = False) -> str:
    """Programmatically append disclaimer to AI-generated content."""
    disclaimer = SHORT_DISCLAIMER if short else CIRCULAR_230_DISCLAIMER
    return f"{content}\n\n---\n{disclaimer}"
```

**Step 2: Apply to narrative generator**

In `ai_narrative_generator.py`, import `wrap_with_disclaimer` and call it on every output:
```python
from advisory.disclaimer import wrap_with_disclaimer

# At the end of generate_executive_summary:
narrative = wrap_with_disclaimer(raw_narrative)
```

**Step 3: Apply to report summarizer** — same pattern for all summary methods.

**Step 4: Commit**
```
feat: add mandatory Circular 230 disclaimer to all AI-generated tax content
```

---

### Task 2.2: Add AI audit trail event types

**Files:**
- Modify: `src/audit/audit_trail.py:17-66`

**Step 1: Add AI event types to enum**

```python
class AuditEventType(Enum):
    # ... existing events ...

    # AI Advisory Events
    AI_CONTENT_GENERATED = "ai_content_generated"
    AI_ADVICE_SURFACED = "ai_advice_surfaced"
    AI_RECOMMENDATION_ACCEPTED = "ai_recommendation_accepted"
    AI_RECOMMENDATION_DISMISSED = "ai_recommendation_dismissed"
```

**Step 2: Create logging helper**

```python
def log_ai_event(
    event_type: AuditEventType,
    user_id: str,
    session_id: str,
    model_id: str,
    provider: str,
    prompt_version: str,
    input_data_hash: str,
    output_hash: str,
    metadata: dict = None,
):
    """Log AI advisory event for Circular 230 compliance."""
    return log_event(
        event_type=event_type,
        user_id=user_id,
        session_id=session_id,
        details={
            "model_id": model_id,
            "provider": provider,
            "prompt_version": prompt_version,
            "input_hash": input_data_hash,
            "output_hash": output_hash,
            **(metadata or {}),
        },
    )
```

**Step 3: Wire into narrative generator** — call `log_ai_event` after every AI generation.

**Step 4: Commit**
```
feat: add AI audit trail events for Circular 230 compliance
```

---

### Task 2.3: Apply PII scrubbing to all AI call paths

**Files:**
- Modify: `src/services/ai/unified_ai_service.py`

**Step 1: Add scrubbing at the AI service boundary**

In `UnifiedAIService.complete()` (or equivalent method), apply `scrub_for_ai` before sending to any provider:

```python
from advisory.pii_scrubber import scrub_for_ai

class UnifiedAIService:
    async def complete(self, prompt: str, context: dict = None, **kwargs):
        # Scrub PII from context before sending to external AI
        if context:
            context = scrub_for_ai(context)
        # ... existing provider call logic ...
```

**Step 2: Commit**
```
fix: apply PII scrubbing at AI service boundary for all provider calls
```

---

### Task 2.4: Enable compliance review by default

**Files:**
- Modify: `src/services/ocr/ai_enhanced_processor.py` (find `enable_compliance_check`)

**Step 1: Change default to True**
```python
# OLD: enable_compliance_check=False
# NEW:
enable_compliance_check=True
```

**Step 2: Commit**
```
fix: enable compliance review by default for AI-enhanced processing
```

---

### Task 2.5: Add IRS reference content validation

**Files:**
- Modify: `src/recommendation/validation.py:51-56`

**Step 1: Add content validation beyond format**

```python
# Valid IRC section range (1-9834 as of 2025)
VALID_IRC_RANGE = range(1, 9835)
# Common valid IRS publications
VALID_PUBLICATIONS = {1, 15, 17, 334, 463, 501, 502, 503, 504, 505, 523, 525,
                      527, 529, 535, 536, 544, 550, 551, 554, 559, 560, 570,
                      575, 587, 590, 596, 915, 925, 926, 929, 936, 946, 970, 972}

def validate_irs_reference(ref: str) -> bool:
    """Validate IRS reference exists (not just format)."""
    import re
    # Check IRC section number is in valid range
    irc_match = re.search(r'IRC\s+Section\s+(\d+)', ref)
    if irc_match and int(irc_match.group(1)) not in VALID_IRC_RANGE:
        return False
    # Check publication number
    pub_match = re.search(r'Publication\s+(\d+)', ref)
    if pub_match and int(pub_match.group(1)) not in VALID_PUBLICATIONS:
        return False
    return True
```

**Step 2: Wire into `validate_before_surface`**

**Step 3: Commit**
```
feat: validate IRS reference content (not just format) to catch hallucinations
```

---

### Task 2.6: Fix Textract multi-page PDF handling

**Files:**
- Modify: `src/services/ocr/ocr_engine.py:373-377`

**Step 1: Implement page-by-page PDF processing**

```python
def process_pdf(self, pdf_path: str) -> OCRResult:
    """Process PDF with AWS Textract — convert pages to images first."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        logger.warning("pdf2image not installed, processing first page only")
        return self.process_image(pdf_path)

    pages = convert_from_path(pdf_path, dpi=300)
    all_text = []
    total_confidence = 0.0

    for i, page_img in enumerate(pages):
        # Save page as temp image
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            page_img.save(tmp.name, 'PNG')
            page_result = self.process_image(tmp.name)
            all_text.append(page_result.text)
            total_confidence += page_result.confidence

    combined_text = "\n--- PAGE BREAK ---\n".join(all_text)
    avg_confidence = total_confidence / len(pages) if pages else 0

    return OCRResult(
        text=combined_text,
        confidence=avg_confidence,
        pages=len(pages),
        words=page_result.words if pages else [],
    )
```

**Step 2: Commit**
```
fix: implement multi-page PDF processing for Textract OCR
```

---

### Task 2.7: Fix confidence scorer critical-field weighting

**Files:**
- Modify: `src/services/ocr/confidence_scorer.py:478`

**Step 1: Pass actual field names**

```python
# OLD: field_name = f"field_{i}"
# NEW: use actual field name from the fields list
for field_name, field_conf in field_confidences.items():
    weight = 2.0 if field_name in critical_fields else 1.0
```

**Step 2: Commit**
```
fix: use actual field names in confidence aggregator for critical-field weighting
```

---

### Task 2.8: Fix EITC estimate in deduction detector

**Files:**
- Modify: `src/smart_tax/deduction_detector.py:554`

**Step 1: Add earned income check and caveat**

```python
# OLD: eitc_estimate = max_eitc * Decimal("0.5")
# NEW: Use actual phase-in rate for rough estimate
EITC_PHASE_IN_RATES = {0: Decimal("0.0765"), 1: Decimal("0.34"), 2: Decimal("0.40"), 3: Decimal("0.45")}
phase_in_rate = EITC_PHASE_IN_RATES.get(min(num_children, 3), Decimal("0.34"))
eitc_estimate = min(max_eitc, earned_income * phase_in_rate)
```

**Step 2: Commit**
```
fix: use phase-in rate for EITC estimate instead of 50% haircut
```

---

### Task 2.9: Wire TaxResearchService into advisory generation

**Files:**
- Modify: `src/advisory/ai_narrative_generator.py`

**Step 1: Inject current-year limits before generation**

```python
# At the top of generate_executive_summary or generate_recommendation:
try:
    from services.ai.tax_research_service import TaxResearchService
    research = TaxResearchService()
    current_limits = await research.get_current_year_limits(2025)
    grounding_context = f"\nCurrent 2025 IRS limits: {current_limits}\n"
except Exception:
    grounding_context = ""  # Graceful degradation

# Inject into prompt:
prompt = f"{grounding_context}\n{base_prompt}"
```

**Step 2: Commit**
```
feat: ground AI advisory generation with live IRS data via TaxResearchService
```

---

### Task 2.10: Add human review flag for AI narratives

**Files:**
- Modify: `src/advisory/ai_narrative_generator.py`

**Step 1: Add review_required flag to generated narratives**

```python
@dataclass
class GeneratedNarrative:
    content: str
    metadata: dict
    review_required: bool = True  # Default: all AI content requires CPA review
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
```

**Step 2: Commit**
```
feat: add human review tracking for AI-generated narratives
```

---

## Track 3: CPA B2B Workflow (8 tasks)

---

### Task 3.1: Add authentication to all calculation endpoints

**Files:**
- Modify: `src/web/routers/calculations.py:71,183,247,307,331,398,468,537`

**Step 1: Add auth dependency to every route**

```python
from rbac.dependencies import require_auth
from rbac.context import AuthContext

# For each route handler, add ctx parameter:
@router.post("/calculate/complete")
async def calculate_complete(request: Request, ctx: AuthContext = Depends(require_auth)):
    ...

@router.post("/calculate-tax")
async def calculate_tax_quick(request: Request, ctx: AuthContext = Depends(require_auth)):
    ...

@router.post("/estimate")
async def estimate_tax(request: Request, ctx: AuthContext = Depends(require_auth)):
    ...
```

Repeat for all 8 endpoints. The import is already available in the file's import section.

**Step 2: Commit**
```
fix: add authentication to all 8 calculation endpoints
```

---

### Task 3.2: Add deduction comparison to results page

**Files:**
- Modify: `src/web/templates/results.html` (after the hero card, around line 677)

**Step 1: Add comparison card**

```html
<!-- DEDUCTION COMPARISON CARD -->
<div class="card" style="margin-top: var(--space-4);">
    <div class="card-header">
        <h2>Deduction Strategy</h2>
    </div>
    <div class="card-body">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4);">
            <div class="deduction-option" id="standard-option">
                <h3>Standard Deduction</h3>
                <div class="deduction-amount">${{ "{:,.0f}".format(return_data.get('standard_deduction', 0)) }}</div>
                <p class="text-secondary">No itemization required</p>
            </div>
            <div class="deduction-option" id="itemized-option">
                <h3>Itemized Deductions</h3>
                <div class="deduction-amount">${{ "{:,.0f}".format(return_data.get('total_itemized', 0)) }}</div>
                <ul class="deduction-breakdown">
                    {% if return_data.get('mortgage_interest', 0) > 0 %}
                    <li>Mortgage interest: ${{ "{:,.0f}".format(return_data.get('mortgage_interest', 0)) }}</li>
                    {% endif %}
                    {% if return_data.get('salt_deduction', 0) > 0 %}
                    <li>SALT: ${{ "{:,.0f}".format(return_data.get('salt_deduction', 0)) }}</li>
                    {% endif %}
                    {% if return_data.get('charitable', 0) > 0 %}
                    <li>Charitable: ${{ "{:,.0f}".format(return_data.get('charitable', 0)) }}</li>
                    {% endif %}
                </ul>
            </div>
        </div>
        {% set std = return_data.get('standard_deduction', 0) %}
        {% set itm = return_data.get('total_itemized', 0) %}
        {% if itm > std %}
        <div class="recommendation-badge" style="margin-top: var(--space-3); color: var(--color-success-600);">
            Itemizing saves you ${{ "{:,.0f}".format(itm - std) }} more
        </div>
        {% else %}
        <div class="recommendation-badge" style="margin-top: var(--space-3); color: var(--color-success-600);">
            Standard deduction is better by ${{ "{:,.0f}".format(std - itm) }}
        </div>
        {% endif %}
    </div>
</div>
```

**Step 2: Commit**
```
feat: add itemized vs standard deduction comparison to results page
```

---

### Task 3.3: Fix CPA return review — verify action buttons exist and wire them

**Files:**
- Modify: `src/web/templates/cpa/return_review.html:368-400`

The action buttons exist (Approve Return, Request Changes). Verify the JavaScript functions `approveReturn()` and `requestChanges()` are wired to the API:

**Step 1: Verify or add the JS handlers**

```javascript
async function approveReturn() {
    const signature = document.getElementById('cpaSignature').value;
    if (!signature) {
        alert('Please enter your electronic signature');
        return;
    }
    const response = await secureFetch(`/api/returns/${sessionId}/approve`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            cpa_reviewer_name: signature,
            review_notes: 'Approved via CPA panel'
        })
    });
    if (response.ok) {
        location.reload();
    }
}

async function requestChanges() {
    const notes = document.getElementById('changeRequest').value;
    if (!notes) {
        alert('Please describe the changes needed');
        return;
    }
    const response = await secureFetch(`/api/returns/${sessionId}/revert-to-draft`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({reason: notes})
    });
    if (response.ok) {
        location.reload();
    }
}
```

**Step 2: Commit**
```
fix: wire CPA return review approve/reject buttons to API endpoints
```

---

### Task 3.4: Add CPA dashboard lead table sorting

**Files:**
- Modify: `src/web/templates/cpa/dashboard.html:264-304`

**Step 1: Add sortable column headers**

```html
<thead>
    <tr>
        <th onclick="sortTable('name')" style="cursor:pointer;" aria-sort="none">Lead <span class="sort-arrow"></span></th>
        <th onclick="sortTable('state')" style="cursor:pointer;" aria-sort="none">State</th>
        <th onclick="sortTable('temperature')" style="cursor:pointer;" aria-sort="none">Temperature</th>
        <th onclick="sortTable('savings')" style="cursor:pointer;" aria-sort="none">Est. Savings</th>
        <th onclick="sortTable('age')" style="cursor:pointer;" aria-sort="none">Age</th>
    </tr>
</thead>
```

**Step 2: Add sorting JS**

```javascript
function sortTable(column) {
    const table = document.querySelector('.lead-table');
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const header = event.target.closest('th');
    const isAsc = header.getAttribute('aria-sort') !== 'ascending';

    // Reset all headers
    table.querySelectorAll('th').forEach(th => th.setAttribute('aria-sort', 'none'));
    header.setAttribute('aria-sort', isAsc ? 'ascending' : 'descending');

    rows.sort((a, b) => {
        const aVal = a.dataset[column] || a.cells[getColIndex(column)].textContent;
        const bVal = b.dataset[column] || b.cells[getColIndex(column)].textContent;
        return isAsc ? aVal.localeCompare(bVal, undefined, {numeric: true})
                     : bVal.localeCompare(aVal, undefined, {numeric: true});
    });

    const tbody = table.querySelector('tbody');
    rows.forEach(row => tbody.appendChild(row));
}
```

**Step 3: Commit**
```
feat: add sortable columns to CPA dashboard lead table
```

---

### Task 3.5: Replace income bucket dropdown with currency input in client portal

**Files:**
- Modify: `src/web/templates/client_portal.html:225-235`

**Step 1: Replace multi-select with dollar input**

The income section currently uses multi-select for income *types* (W-2, Self-Employed, etc.), which is correct. The issue is elsewhere — find the income *amount* field. If it uses buckets, replace with:

```html
<label class="form-label">Estimated Annual Income</label>
<div class="input-with-prefix">
    <span class="input-prefix">$</span>
    <input type="text" id="estimated-income" class="form-input"
           placeholder="75,000"
           inputmode="numeric"
           oninput="this.value = this.value.replace(/[^0-9]/g, '').replace(/\B(?=(\d{3})+(?!\d))/g, ',')">
</div>
```

**Step 2: Commit**
```
feat: replace income bucket dropdown with dollar input in client portal
```

---

### Task 3.6: Add tax term tooltips for non-professional users

**Files:**
- Create: `src/web/static/js/core/tax-glossary.js`
- Modify: `src/web/templates/base_modern.html` (include the script)

**Step 1: Create glossary component**

```javascript
const TAX_GLOSSARY = {
    'AGI': 'Adjusted Gross Income — your total income minus specific deductions like IRA contributions and student loan interest.',
    'AMT': 'Alternative Minimum Tax — a parallel tax system that limits certain deductions to ensure higher-income taxpayers pay a minimum amount.',
    'MAGI': 'Modified Adjusted Gross Income — AGI with certain deductions added back, used for determining eligibility for credits and deductions.',
    'EITC': 'Earned Income Tax Credit — a refundable tax credit for low-to-moderate income working individuals and families.',
    'QBI': 'Qualified Business Income — income from pass-through businesses eligible for a 20% deduction under Section 199A.',
    'SALT': 'State and Local Tax — deduction for state/local income, sales, and property taxes, capped at $10,000.',
    'HOH': 'Head of Household — a filing status for unmarried taxpayers who pay more than half the cost of maintaining a home for a qualifying person.',
};

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-tax-term]').forEach(el => {
        const term = el.dataset.taxTerm;
        const def = TAX_GLOSSARY[term];
        if (def) {
            el.setAttribute('title', def);
            el.style.borderBottom = '1px dotted var(--text-secondary)';
            el.style.cursor = 'help';
        }
    });
});
```

**Step 2: Usage in templates**
```html
<span data-tax-term="AGI">AGI</span>
```

**Step 3: Commit**
```
feat: add tax term glossary tooltips for non-professional users
```

---

### Task 3.7: Add notification indicator to CPA sidebar

**Files:**
- Modify: `src/web/templates/partials/sidebar.html` (find nav items section)

**Step 1: Add notification bell**

```html
<!-- In the sidebar header or top nav area -->
<div class="sidebar-notifications" style="position: relative;">
    <button onclick="toggleNotifications()" class="btn-icon" aria-label="Notifications">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        <span id="notification-badge" class="notification-badge" style="display:none;">0</span>
    </button>
</div>
```

**Step 2: Add fetch for unread count**

```javascript
async function loadNotificationCount() {
    try {
        const resp = await secureFetch('/api/notifications/unread-count');
        if (resp.ok) {
            const data = await resp.json();
            const badge = document.getElementById('notification-badge');
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.style.display = 'flex';
            }
        }
    } catch (e) { /* silent */ }
}
setInterval(loadNotificationCount, 60000);
loadNotificationCount();
```

**Step 3: Commit**
```
feat: add notification bell with unread count to CPA sidebar
```

---

### Task 3.8: Add return status display with whole-dollar formatting

**Files:**
- Modify: `src/web/templates/cpa/return_review.html` (find format strings)

**Step 1: Change 2-decimal to whole-dollar**

```python
# In all Jinja2 format strings, change:
# "{:,.2f}".format(...)
# to:
# "{:,.0f}".format(...)
```

**Step 2: Commit**
```
fix: use whole-dollar rounding in CPA return review per IRS convention
```

---

## Track 4: Critical Platform Capabilities (10 tasks)

---

### Task 4.1: Remove encryption base64 fallback — make cryptography required

**Files:**
- Modify: `src/database/encrypted_fields.py:256-263`
- Modify: `src/security/encryption.py` (similar fallback)

**Step 1: Replace fallback with hard error**

```python
# OLD:
# except ImportError:
#     logger.warning("cryptography not installed - using fallback encoding (NOT SECURE)")
#     return _fallback_encode(plaintext, field_type)

# NEW:
except ImportError:
    raise RuntimeError(
        "FATAL: 'cryptography' package is required for PII encryption. "
        "Install with: pip install cryptography"
    )
```

Remove the `_fallback_encode` and `_fallback_decode` functions entirely.

**Step 2: Commit**
```
fix: make cryptography package required — remove insecure base64 fallback
```

---

### Task 4.2: Fix SSN hashing — use HMAC-SHA256 with key

**Files:**
- Modify: `src/database/repositories/tax_return_repository.py:102`
- Modify: `src/database/persistence.py` (similar pattern)

**Step 1: Replace unsalted SHA-256 with keyed HMAC**

```python
import hmac
import os

def _hash_ssn(ssn: str) -> str:
    """Compute keyed HMAC-SHA256 hash of SSN (rainbow-table resistant)."""
    key = os.environ.get("ENCRYPTION_MASTER_KEY", "").encode()
    if not key:
        raise RuntimeError("ENCRYPTION_MASTER_KEY required for SSN hashing")
    clean_ssn = ssn.replace("-", "").strip()
    return hmac.new(key, clean_ssn.encode(), hashlib.sha256).hexdigest()
```

Apply the same pattern in `persistence.py` where SSN hashing occurs.

**Step 2: Commit**
```
fix: use HMAC-SHA256 for SSN hashing to prevent rainbow table attacks
```

---

### Task 4.3: Implement token revocation

**Files:**
- Modify: `src/security/authentication.py:313-328`

**Step 1: Replace no-op with token version check**

```python
def revoke_all_user_tokens(self, user_id: str) -> None:
    """Revoke all tokens for a user via token versioning."""
    try:
        import redis
        r = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
        # Increment the user's token version — all older tokens become invalid
        version_key = f"token_version:{user_id}"
        r.incr(version_key)
        logger.info(f"All tokens revoked for user {user_id}")
    except Exception as e:
        logger.error(f"Token revocation failed for {user_id}: {e}")
        raise
```

Also add version check in token verification:
```python
def verify_token(self, token: str) -> dict:
    payload = jwt.decode(...)
    # Check token version
    user_id = payload.get("sub")
    token_version = payload.get("token_version", 0)
    stored_version = self._get_current_token_version(user_id)
    if token_version < stored_version:
        raise InvalidTokenError("Token has been revoked")
    return payload
```

**Step 2: Commit**
```
feat: implement token revocation via Redis-backed version tracking
```

---

### Task 4.4: Fix rate limiter fail-open on Redis error

**Files:**
- Modify: `src/web/rate_limiter.py:131`

**Step 1: Fall back to memory limiter instead of allowing all**

```python
# OLD:
# except Exception:
#     return (True, limit - 1, 0)  # fail open

# NEW:
except Exception as e:
    logger.warning(f"Redis rate limiter unavailable: {e}, using in-memory fallback")
    # Fall back to in-memory limiter instead of allowing all traffic
    return self.memory_limiter.is_allowed(identifier) if self.memory_limiter else (True, limit - 1, 0)
```

**Step 2: Commit**
```
fix: rate limiter falls back to in-memory on Redis error instead of fail-open
```

---

### Task 4.5: Persist PII access audit log to database

**Files:**
- Modify: `src/database/encrypted_fields.py:446-482`

**Step 1: Replace in-memory list with database write**

```python
def _log_pii_access(field_type: str, action: str, user_id: str = None):
    """Log PII access to database for compliance."""
    from audit.audit_trail import log_event, AuditEventType

    log_event(
        event_type=AuditEventType.PII_ACCESSED,
        user_id=user_id or "system",
        details={
            "field_type": field_type,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
```

Add `PII_ACCESSED` to `AuditEventType` enum if not present.

**Step 2: Commit**
```
fix: persist PII access audit log to database instead of in-memory list
```

---

### Task 4.6: Fix CSRF token lifetime (7 days -> 1 hour)

**Files:**
- Modify: `src/web/app.py:256-260`

**Step 1: Reduce lifetime**

```python
# OLD: max_age=604800  (7 days)
# NEW:
max_age=3600  # 1 hour — regenerated on each login
```

**Step 2: Commit**
```
fix: reduce CSRF token lifetime from 7 days to 1 hour
```

---

### Task 4.7: Add Redis authentication

**Files:**
- Modify: `docker-compose.yml` (Redis service)
- Modify: `docker-compose.production.yml` (Redis service)

**Step 1: Add requirepass to Redis**

```yaml
redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-changeme}
    environment:
      - REDIS_PASSWORD=${REDIS_PASSWORD:-changeme}
```

**Step 2: Update REDIS_URL in app services**

```yaml
environment:
    - REDIS_URL=redis://:${REDIS_PASSWORD:-changeme}@redis:6379/0
```

**Step 3: Commit**
```
fix: add password authentication to Redis services
```

---

### Task 4.8: Generate and commit requirements.lock

**Files:**
- Create: `requirements.lock`

**Step 1: Generate lock file**

```bash
pip-compile requirements.txt -o requirements.lock --generate-hashes
```

**Step 2: Commit**
```
fix: add requirements.lock for reproducible production builds
```

---

### Task 4.9: Add mobile hamburger to landing page

**Files:**
- Modify: `src/web/templates/landing.html:63-96`

**Step 1: Add hamburger button and responsive CSS**

```html
<!-- Add after logo, before nav links -->
<button class="mobile-menu-toggle" onclick="document.querySelector('.nav-links').classList.toggle('open')"
        aria-label="Toggle navigation" aria-expanded="false">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
    </svg>
</button>
```

```css
@media (max-width: 768px) {
    .nav-links { display: none; flex-direction: column; position: absolute; top: 100%; left: 0; right: 0; background: var(--bg-primary); padding: var(--space-4); }
    .nav-links.open { display: flex; }
    .mobile-menu-toggle { display: block; }
}
@media (min-width: 769px) {
    .mobile-menu-toggle { display: none; }
}
```

**Step 2: Commit**
```
feat: add mobile hamburger menu to landing page
```

---

### Task 4.10: Add tenant filter at repository level

**Files:**
- Modify: `src/database/repositories/tax_return_repository.py`

**Step 1: Add mandatory tenant scoping to all queries**

```python
def get_by_id(self, return_id: str, tenant_scope: dict = None) -> Optional[TaxReturn]:
    """Load return with mandatory tenant scoping."""
    query = select(TaxReturnModel).where(TaxReturnModel.return_id == return_id)
    if tenant_scope:
        if 'user_id' in tenant_scope:
            query = query.where(TaxReturnModel.user_id == tenant_scope['user_id'])
        if 'firm_id' in tenant_scope:
            query = query.where(TaxReturnModel.firm_id == tenant_scope['firm_id'])
    result = self.session.execute(query).scalar_one_or_none()
    return result
```

**Step 2: Commit**
```
fix: enforce tenant scoping at repository level for all tax return queries
```

---

## Execution Order (Recommended)

**Week 1 — Tax Accuracy (highest liability):**
Tasks 1.1-1.9 (bracket fixes, AMT, ACTC, EITC, state rates)

**Week 2 — Security + AI Safety:**
Tasks 4.1-4.5 (encryption, SSN, tokens, rate limiter, PII audit)
Tasks 2.1-2.4 (disclaimers, audit trail, PII scrubbing, compliance)

**Week 3 — Platform + CPA Workflow:**
Tasks 3.1-3.3 (auth on calc endpoints, deduction comparison, review buttons)
Tasks 2.5-2.8 (IRS validation, Textract, confidence, EITC)

**Week 4 — Polish + Remaining:**
Tasks 3.4-3.8, 4.6-4.10, 1.10-1.14, 2.9-2.10

---

## Total: 42 tasks across 4 tracks
- Track 1 (Tax Accuracy): 14 tasks
- Track 2 (AI Advisory): 10 tasks
- Track 3 (CPA B2B): 8 tasks
- Track 4 (Platform): 10 tasks
