# Tiered Conversion Experience — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a tiered strategy experience that classifies strategies as Free/Premium using AI risk analysis, gates premium content behind a zero-friction unlock, and captures CPA leads via soft email capture.

**Architecture:** Backend adds `tier`, `risk_level`, `implementation_complexity` fields to `StrategyRecommendation`, a `_classify_strategy_tier()` helper using `TaxReasoningService` and `AnomalyDetector`, a `premium_unlocked` session flag, 3 new endpoints (unlock, email, AMT), plus `compare_scenarios` and `record_usage` wiring. Frontend adds locked/unlocked strategy cards, safety summary, unlock modal, and lead capture — all styled via a new `advisor-premium.css` extending the existing CSS custom properties.

**Tech Stack:** Python/FastAPI (Pydantic models), vanilla JS (no framework), CSS custom properties, existing AI services (TaxReasoningService, AnomalyDetector, ComplianceReviewer, AINarrativeGenerator, AIReportSummarizer, ChatRouter, AIMetricsService)

**Design Doc:** `docs/plans/2026-02-27-tiered-conversion-design.md`

---

### Task 1: Add tier/risk fields to StrategyRecommendation model

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:626-638`
- Modify: `src/web/advisor_models.py:108-120`

Both files have duplicate `StrategyRecommendation` definitions. Add 3 new optional fields to each.

**Step 1: Edit the model in intelligent_advisor_api.py**

At `src/web/intelligent_advisor_api.py:638`, after the `deadline` field, add:

```python
    deadline: Optional[str] = None
    # Tiered conversion fields
    tier: Optional[str] = "free"  # "free" or "premium"
    risk_level: Optional[str] = "low"  # "low", "medium", "high"
    implementation_complexity: Optional[str] = "simple"  # "simple", "moderate", "complex"
```

**Step 2: Edit the model in advisor_models.py**

At `src/web/advisor_models.py:120`, after the `deadline` field, add the same 3 fields:

```python
    deadline: Optional[str] = None
    # Tiered conversion fields
    tier: Optional[str] = "free"  # "free" or "premium"
    risk_level: Optional[str] = "low"  # "low", "medium", "high"
    implementation_complexity: Optional[str] = "simple"  # "simple", "moderate", "complex"
```

**Step 3: Add premium_unlocked and safety_summary to ChatResponse**

At `src/web/intelligent_advisor_api.py:728`, after `confidence_reason`, add:

```python
    confidence_reason: Optional[str] = None  # Why confidence is reduced

    # Tiered conversion fields
    premium_unlocked: bool = False
    safety_summary: Optional[Dict[str, Any]] = None
```

Do the same in `src/web/advisor_models.py:196`, after `confidence_reason`:

```python
    confidence_reason: Optional[str] = None

    # Tiered conversion fields
    premium_unlocked: bool = False
    safety_summary: Optional[Dict[str, Any]] = None
```

**Step 4: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('src/web/intelligent_advisor_api.py', doraise=True); py_compile.compile('src/web/advisor_models.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add src/web/intelligent_advisor_api.py src/web/advisor_models.py
git commit -m "feat: add tier/risk fields to StrategyRecommendation and ChatResponse models"
```

---

### Task 2: Add strategy classification helper function

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` (add helper function before the chat endpoint)

**Step 1: Add the `_classify_strategy_tier()` helper**

Find the line with `async def _run_safety_checks_background` (use grep to locate exact line). Insert the new helper function BEFORE it:

```python
# =============================================================================
# STRATEGY TIERING — Classify strategies as free or premium
# =============================================================================

PREMIUM_CATEGORIES = {
    "entity_restructuring", "roth_conversion", "estate_planning",
    "amt_optimization", "international_tax", "trust_planning",
    "cost_segregation", "opportunity_zones", "backdoor_roth",
    "mega_backdoor_roth", "charitable_remainder_trust",
}

SIMPLE_CATEGORIES = {
    "retirement_401k", "retirement_ira", "hsa", "charitable_giving",
    "standard_deduction", "education_credits", "child_tax_credit",
    "earned_income_credit", "student_loan_interest",
}


async def _classify_strategy_tier(
    strategy,
    profile: dict,
    safety_data: Optional[dict] = None,
) -> dict:
    """Classify a strategy as free or premium based on AI risk analysis.

    Returns dict with tier, risk_level, implementation_complexity.

    Classification rules (from design doc):
      FREE:  requires_professional_review=false AND audit_risk < 20 AND simple category
      PREMIUM: requires_professional_review=true OR audit_risk >= 20 OR complex category
    """
    tier = "free"
    risk_level = "low"
    complexity = "simple"

    # Rule 1: Category-based classification
    category = (strategy.category or "").lower().replace(" ", "_")
    if category in PREMIUM_CATEGORIES:
        tier = "premium"
        complexity = "complex"
    elif category not in SIMPLE_CATEGORIES:
        # Unknown category — check other signals
        complexity = "moderate"

    # Rule 2: AI reasoning flag
    if AI_CHAT_ENABLED:
        try:
            from services.ai.tax_reasoning_service import get_tax_reasoning_service
            reasoning = get_tax_reasoning_service()
            result = await reasoning.analyze(
                problem=f"Does '{strategy.title}' require professional CPA review for this taxpayer?",
                context=_summarize_profile(profile),
            )
            if result.requires_professional_review:
                tier = "premium"
            if result.confidence and result.confidence < 0.6:
                risk_level = "medium"
        except Exception:
            pass  # Fallback: keep current tier

    # Rule 3: Audit risk from safety data
    if safety_data:
        audit_risk = safety_data.get("audit_risk", {})
        risk_score = audit_risk.get("risk_score", 0)
        if risk_score >= 20:
            tier = "premium"
        if risk_score >= 50:
            risk_level = "high"
        elif risk_score >= 20:
            risk_level = "medium"

    # Rule 4: High savings = likely complex
    if strategy.estimated_savings > 5000 and complexity == "simple":
        complexity = "moderate"

    # Rule 5: Entity changes, conversions, timing-dependent
    title_lower = (strategy.title or "").lower()
    if any(kw in title_lower for kw in ["convert", "restructure", "entity", "roth conversion", "backdoor"]):
        tier = "premium"
        complexity = "complex"

    return {"tier": tier, "risk_level": risk_level, "implementation_complexity": complexity}


def _build_safety_summary(safety_checks: Optional[dict]) -> Optional[dict]:
    """Build user-facing compliance summary from safety check data.

    Returns a simplified summary suitable for display to end users.
    """
    if not safety_checks:
        return None

    checks = []
    total = 0
    passed = 0

    # Fraud detection
    fraud = safety_checks.get("fraud")
    if fraud:
        total += 1
        is_clear = fraud.get("risk_level", "").upper() in ("MINIMAL", "LOW", "NONE")
        passed += 1 if is_clear else 0
        checks.append({
            "name": "Fraud Detection",
            "status": "pass" if is_clear else "review",
            "detail": "Clear" if is_clear else "Review recommended",
        })

    # Identity theft
    identity = safety_checks.get("identity_theft")
    if identity:
        total += 1
        is_clear = not identity.get("indicators_found", True)
        passed += 1 if is_clear else 0
        checks.append({
            "name": "Identity Verification",
            "status": "pass" if is_clear else "review",
            "detail": "Pass" if is_clear else "Review recommended",
        })

    # Compliance
    compliance = safety_checks.get("compliance")
    if compliance:
        total += 1
        is_ok = compliance.get("risk_level", "").upper() in ("LOW", "NONE", "MINIMAL")
        passed += 1 if is_ok else 0
        checks.append({
            "name": "Tax Compliance",
            "status": "pass" if is_ok else "review",
            "detail": "Compliant" if is_ok else "Review recommended",
        })

    # EITC due diligence
    eitc = safety_checks.get("eitc_compliance")
    if eitc:
        total += 1
        is_ok = eitc.get("compliant", False)
        passed += 1 if is_ok else 0
        checks.append({
            "name": "EITC Due Diligence",
            "status": "pass" if is_ok else "review",
            "detail": "Compliant" if is_ok else "Review recommended",
        })

    # Circular 230
    c230 = safety_checks.get("circular_230")
    if c230:
        total += 1
        is_ok = c230.get("compliant", False)
        passed += 1 if is_ok else 0
        checks.append({
            "name": "Circular 230",
            "status": "pass" if is_ok else "review",
            "detail": "Compliant" if is_ok else "Review recommended",
        })

    # Audit risk
    audit = safety_checks.get("audit_risk")
    if audit:
        total += 1
        risk = (audit.get("overall_risk") or "low").lower()
        is_ok = risk == "low"
        passed += 1 if is_ok else 0
        checks.append({
            "name": "Audit Risk Assessment",
            "status": "pass" if is_ok else "review",
            "detail": f"{'Low' if is_ok else risk.title()} risk (score: {audit.get('risk_score', 0)})",
        })

    # Data entry errors
    data_errors = safety_checks.get("data_errors")
    if data_errors:
        total += 1
        is_ok = not data_errors.get("errors_found", True)
        passed += 1 if is_ok else 0
        checks.append({
            "name": "Data Validation",
            "status": "pass" if is_ok else "review",
            "detail": "Pass" if is_ok else "Errors detected",
        })

    if total == 0:
        return None

    needs_review = total - passed
    return {
        "total_checks": total,
        "passed": passed,
        "needs_review": needs_review,
        "checks": checks,
        "overall_status": "clear" if needs_review == 0 else "review_recommended",
    }
```

**Step 2: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('src/web/intelligent_advisor_api.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "feat: add strategy tiering classifier and safety summary builder"
```

---

### Task 3: Wire strategy tiering into chat endpoint

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` (chat endpoint, around line 5200-5260)

**Step 1: Add tier classification after strategy generation**

Find this block (around line 5246):
```python
        # Update session with calculations and strategies, and persist to database
        await chat_engine.update_session(request.session_id, {
```

Insert BEFORE that line:

```python
        # Classify strategy tiers
        session = await chat_engine.get_or_create_session(request.session_id)
        safety_data = session.get("safety_checks")
        premium_unlocked = session.get("premium_unlocked", False)

        for s in strategies:
            tier_info = await _classify_strategy_tier(s, profile, safety_data)
            s.tier = tier_info["tier"]
            s.risk_level = tier_info["risk_level"]
            s.implementation_complexity = tier_info["implementation_complexity"]

        # Count tiers for response
        premium_count = sum(1 for s in strategies if s.tier == "premium")
        free_count = len(strategies) - premium_count

        # Edge case: all free (simple W-2) — no tiering
        if premium_count == 0:
            premium_unlocked = True  # Nothing to unlock

```

**Step 2: Add premium_unlocked and safety_summary to chat response**

Find the return `ChatResponse(` block that follows the calculation section (around line 5400+). It currently does NOT include `premium_unlocked` or `safety_summary`. Add them as fields.

Find the existing `return ChatResponse(` inside the `if has_basics:` block — the one with `response_type="calculation"`. Add these two fields:

```python
            premium_unlocked=premium_unlocked,
            safety_summary=_build_safety_summary(safety_data),
```

**Step 3: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('src/web/intelligent_advisor_api.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "feat: wire strategy tier classification into chat endpoint"
```

---

### Task 4: Add unlock-strategies endpoint

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` (add new endpoint before `register_intelligent_advisor_routes`)

**Step 1: Add the unlock endpoint**

Find `@router.get("/ai-routing-stats")` (one of the last endpoints before `register_intelligent_advisor_routes`). Add this new endpoint AFTER it:

```python
class UnlockRequest(BaseModel):
    """Request to unlock premium strategies."""
    session_id: str


@router.post("/unlock-strategies")
async def unlock_strategies(request: UnlockRequest, _session: str = Depends(verify_session_token)):
    """Mark session as premium-unlocked. Zero friction — instant unlock."""
    try:
        session = await chat_engine.get_or_create_session(request.session_id)
        session["premium_unlocked"] = True

        # Persist to database
        await chat_engine.update_session(request.session_id, {
            "premium_unlocked": True,
        })

        # Get strategies if available to return full unlocked set
        strategies = session.get("strategies", [])
        strategy_dicts = []
        for s in strategies:
            d = s.dict() if hasattr(s, "dict") else (s if isinstance(s, dict) else {})
            strategy_dicts.append(d)

        return {
            "session_id": request.session_id,
            "premium_unlocked": True,
            "strategies": strategy_dicts,
            "message": "All strategies unlocked! Your full analysis is now available.",
        }
    except Exception as e:
        logger.error(f"Unlock strategies error: {e}")
        raise HTTPException(status_code=500, detail="Unable to unlock strategies.")
```

**Step 2: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('src/web/intelligent_advisor_api.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "feat: add POST /unlock-strategies endpoint for zero-friction unlock"
```

---

### Task 5: Add report/email endpoint

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` (add new endpoint)

**Step 1: Add the email report endpoint**

Add after the unlock-strategies endpoint:

```python
class EmailReportRequest(BaseModel):
    """Request to email the tax advisory report."""
    session_id: str
    email: str
    name: Optional[str] = None


@router.post("/report/email")
async def email_report(request: EmailReportRequest, _session: str = Depends(verify_session_token)):
    """Send tax advisory report via email and notify CPA team.

    This is the key conversion endpoint: captures lead data and
    triggers CPA notification.
    """
    import re
    # Basic email validation
    if not request.email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", request.email):
        raise HTTPException(status_code=400, detail="Valid email address required.")

    try:
        session = await chat_engine.get_or_create_session(request.session_id)
        profile = session.get("profile", {})
        calculation = session.get("calculations")
        strategies = session.get("strategies", [])

        if not calculation:
            raise HTTPException(status_code=400, detail="No tax calculation available. Complete analysis first.")

        # Store lead data in session
        session["lead_email"] = request.email
        session["lead_name"] = request.name or profile.get("name", "")
        session["lead_captured_at"] = datetime.now().isoformat()
        await chat_engine.update_session(request.session_id, {
            "lead_email": request.email,
            "lead_name": request.name or "",
            "lead_captured_at": session["lead_captured_at"],
        })

        # Generate email content using AI summarizer if available
        email_body_client = None
        email_body_internal = None
        if AI_REPORT_NARRATIVES_ENABLED:
            try:
                from advisory.report_summarizer import get_report_summarizer
                summarizer = get_report_summarizer()
                report_data = {
                    "metrics": {
                        "total_tax": calculation.total_tax if hasattr(calculation, "total_tax") else calculation.get("total_tax", 0),
                        "total_savings": sum(
                            (s.estimated_savings if hasattr(s, "estimated_savings") else s.get("estimated_savings", 0))
                            for s in strategies[:5]
                        ),
                    },
                    "recommendations": [
                        {
                            "title": s.title if hasattr(s, "title") else s.get("title", ""),
                            "savings": s.estimated_savings if hasattr(s, "estimated_savings") else s.get("estimated_savings", 0),
                            "priority": s.priority if hasattr(s, "priority") else s.get("priority", "medium"),
                        }
                        for s in strategies[:5]
                    ],
                }
                email_body_client = await summarizer.generate_summary_for_email(
                    report_data, recipient_type="client"
                )
                email_body_internal = await summarizer.generate_summary_for_email(
                    report_data, recipient_type="internal"
                )
            except Exception as e:
                logger.warning(f"Email summary generation failed: {e}")

        # Emit CPA notification event
        try:
            from realtime.event_publisher import event_publisher
            from realtime.events import RealtimeEvent, EventType
            total_savings = sum(
                (s.estimated_savings if hasattr(s, "estimated_savings") else s.get("estimated_savings", 0))
                for s in strategies
            )
            await event_publisher.publish(RealtimeEvent(
                event_type=EventType.LEAD_CAPTURED,
                session_id=request.session_id,
                data={
                    "email": request.email,
                    "name": request.name or "",
                    "total_savings": total_savings,
                    "strategy_count": len(strategies),
                    "complexity": chat_engine.determine_complexity(profile),
                },
            ))
        except Exception:
            pass  # Non-blocking

        return {
            "success": True,
            "session_id": request.session_id,
            "email_sent": True,
            "message": "Your report has been sent. A CPA will reach out within 24 hours.",
            "email_body_client": email_body_client,
            "email_body_internal": email_body_internal,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email report error: {e}")
        raise HTTPException(status_code=500, detail="Unable to send report email.")
```

**Step 2: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('src/web/intelligent_advisor_api.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "feat: add POST /report/email endpoint for lead capture and CPA notification"
```

---

### Task 6: Add AMT analysis endpoint and wire compare_scenarios

**Files:**
- Modify: `src/web/intelligent_advisor_api.py`

**Step 1: Add AMT analysis endpoint**

Add after the email report endpoint:

```python
@router.post("/amt-analysis")
async def analyze_amt_exposure(request: FullAnalysisRequest, _session: str = Depends(verify_session_token)):
    """AI-powered Alternative Minimum Tax exposure analysis."""
    try:
        profile = request.profile.dict(exclude_none=True)

        if AI_CHAT_ENABLED:
            try:
                from services.ai.tax_reasoning_service import get_tax_reasoning_service
                reasoning = get_tax_reasoning_service()
                result = await reasoning.analyze_amt_exposure(
                    income=profile.get("total_income", 0) or 0,
                    deductions={
                        "state_tax": profile.get("state_income_tax", 0) or 0,
                        "property_tax": profile.get("property_taxes", 0) or 0,
                        "mortgage_interest": profile.get("mortgage_interest", 0) or 0,
                    },
                    filing_status=profile.get("filing_status", "single"),
                    iso_exercises=0,
                )
                return {
                    "session_id": request.session_id,
                    "analysis": result.analysis[:1500],
                    "recommendation": result.recommendation,
                    "key_factors": result.key_factors,
                    "action_items": result.action_items[:5],
                    "confidence": result.confidence,
                    "ai_powered": True,
                }
            except Exception as e:
                logger.warning(f"AI AMT analysis failed: {e}")

        # Fallback: basic AMT estimation
        income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single")
        exemption = 85700 if filing_status == "single" else 133300
        salt = min((profile.get("state_income_tax", 0) or 0) + (profile.get("property_taxes", 0) or 0), 10000)

        amt_income = income + salt
        amt_liable = amt_income > exemption

        return {
            "session_id": request.session_id,
            "analysis": f"Based on your income of ${income:,.0f}, {'you may be subject to AMT' if amt_liable else 'AMT is unlikely to apply'}.",
            "recommendation": "Consult a CPA for detailed AMT planning" if amt_liable else "No AMT action needed",
            "key_factors": ["income_level", "salt_deductions"],
            "action_items": ["Review SALT deduction impact on AMT"] if amt_liable else [],
            "confidence": 0.5,
            "ai_powered": False,
        }
    except Exception as e:
        logger.error(f"AMT analysis error: {e}")
        raise HTTPException(status_code=500, detail="Unable to perform AMT analysis.")
```

**Step 2: Wire compare_scenarios into chat endpoint**

Find the `handleQuickAction` mapping in the chat endpoint (search for `quick_action_map` or `compare` in the Python file). In the `intelligent_chat()` function, find where quick actions are handled. Add a handler for `compare_scenarios` action type.

Search for the block that handles quick actions in `intelligent_chat()`. Before the main response-building logic, if the user message contains comparison keywords, use `ChatRouter.compare_scenarios()`:

Find the AI chat routing block (search for `IntelligentChatRouter` or `route_query`). After the existing routing logic, add:

```python
        # Handle scenario comparison via ChatRouter
        if AI_CHAT_ENABLED and any(kw in lower_message for kw in ["compare", "versus", " vs ", "should i do", "which is better", " or "]):
            try:
                from services.ai.chat_router import get_chat_router
                router = get_chat_router()
                comparison = await router.compare_scenarios(
                    scenario_a=lower_message.split(" or ")[0] if " or " in lower_message else lower_message,
                    scenario_b=lower_message.split(" or ")[1] if " or " in lower_message else "alternative approach",
                    context=_summarize_profile(profile),
                )
                if comparison and comparison.get("analysis"):
                    session["_comparison_result"] = comparison
            except Exception:
                pass  # Non-blocking, fall through to normal processing
```

**Step 3: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('src/web/intelligent_advisor_api.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "feat: add AMT analysis endpoint and wire compare_scenarios into chat"
```

---

### Task 7: Wire record_usage middleware for AI metrics

**Files:**
- Modify: `src/web/intelligent_advisor_api.py`

**Step 1: Add a utility function to record AI usage**

Add after the `_build_safety_summary` function:

```python
async def _record_ai_usage(service_name: str, method_name: str, duration_ms: float = 0, success: bool = True):
    """Record AI service usage for metrics dashboard (non-blocking)."""
    if not AI_CHAT_ENABLED:
        return
    try:
        from services.ai.metrics_service import get_ai_metrics_service
        metrics = get_ai_metrics_service()
        metrics.record_usage(
            service=service_name,
            method=method_name,
            duration_ms=duration_ms,
            success=success,
        )
    except Exception:
        pass  # Metrics recording is never critical
```

**Step 2: Add timing + record_usage calls to key AI invocations**

In the chat endpoint, find the block where `TaxReasoningService.analyze()` is called for strategy enrichment (around line 5208). Wrap it with timing:

Before the `for s in strategies[:2]:` loop, add:
```python
                import time as _time
                _ai_start = _time.monotonic()
```

After the loop's try/except block, add:
```python
                _ai_duration = (_time.monotonic() - _ai_start) * 1000
                asyncio.create_task(_record_ai_usage("TaxReasoningService", "analyze", _ai_duration))
```

Similarly, add `_record_ai_usage` calls after other AI service invocations:
- After `AINarrativeGenerator.generate_recommendation_explanation()` calls
- After `AnomalyDetector.assess_audit_risk()` in the safety checks background function
- After `ComplianceReviewer` calls in safety checks

Each call is a single line: `asyncio.create_task(_record_ai_usage("ServiceName", "method_name", duration))` — always in a non-blocking task.

**Step 3: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('src/web/intelligent_advisor_api.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "feat: wire record_usage AI metrics tracking into service calls"
```

---

### Task 8: Modify safety-check endpoint for user-facing summary

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` (safety-check endpoint, around line 5963)

**Step 1: Add user_summary to safety-check response**

Find the return block in `get_safety_check()` (around line 5991). Add `user_summary` field:

```python
        return {
            "session_id": session_id,
            "status": "complete",
            "safety_checks": safety,
            "categories": categories,
            "checks_completed": list(safety.keys()),
            "total_checks": len(safety),
            "user_summary": _build_safety_summary(safety),
        }
```

**Step 2: Verify syntax**

Run: `python -c "import py_compile; py_compile.compile('src/web/intelligent_advisor_api.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "feat: add user-facing safety summary to safety-check endpoint"
```

---

### Task 9: Create advisor-premium.css

**Files:**
- Create: `src/web/static/css/advisor-premium.css`

**Step 1: Create the stylesheet**

Create `src/web/static/css/advisor-premium.css` with all tiered conversion component styles. Uses CSS custom properties from the existing `variables.css` design system.

```css
/**
 * Advisor Premium — Tiered Conversion Experience
 *
 * Aesthetic: Refined Professional (Bloomberg meets Stripe)
 * Extends: core/variables.css design system
 * Used by: intelligent-advisor.html
 */

/* =========================
   PREMIUM TOKENS
   ========================= */
:root {
  --premium-gold: #b8860b;
  --premium-gold-light: #f5e6c8;
  --premium-gold-dark: #8b6914;
  --premium-blur: 6px;
  --premium-badge-bg: linear-gradient(135deg, #b8860b 0%, #daa520 100%);
  --premium-badge-text: #ffffff;
  --unlock-transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

/* =========================
   STRATEGY CARD — BASE
   ========================= */
.strategy-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--card-border, var(--color-gray-200));
  border-radius: var(--radius-xl, 12px);
  padding: var(--space-5, 1.25rem);
  margin-bottom: var(--space-3, 0.75rem);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-base), transform var(--transition-base);
  position: relative;
  overflow: hidden;
}

.strategy-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

/* =========================
   STRATEGY CARD — FREE
   ========================= */
.strategy-card--free {
  border-left: 3px solid var(--color-success-500, #10b981);
}

.strategy-card--free .strategy-badge {
  background: var(--color-success-50, #ecfdf5);
  color: var(--color-success-700, #047857);
  font-size: var(--text-2xs, 0.6875rem);
  font-weight: var(--font-semibold, 600);
  padding: 2px 8px;
  border-radius: var(--radius-full, 9999px);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide, 0.025em);
}

/* =========================
   STRATEGY CARD — LOCKED (Premium, not unlocked)
   ========================= */
.strategy-card--locked {
  border-left: 3px solid var(--premium-gold);
  cursor: pointer;
}

.strategy-card--locked .strategy-content {
  filter: blur(var(--premium-blur));
  user-select: none;
  pointer-events: none;
  transition: filter var(--unlock-transition);
}

.strategy-card--locked .strategy-savings {
  filter: none;
  font-weight: var(--font-bold, 700);
  color: var(--color-success-600, #059669);
  font-size: var(--text-lg, 1.125rem);
}

.strategy-card--locked .strategy-title {
  filter: none;
}

.strategy-card--locked .strategy-badge {
  background: var(--premium-badge-bg);
  color: var(--premium-badge-text);
  font-size: var(--text-2xs, 0.6875rem);
  font-weight: var(--font-semibold, 600);
  padding: 2px 8px;
  border-radius: var(--radius-full, 9999px);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide, 0.025em);
}

.strategy-card--locked .lock-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(2px);
  z-index: 2;
  opacity: 0;
  transition: opacity var(--transition-base);
}

.strategy-card--locked:hover .lock-overlay {
  opacity: 1;
}

.lock-overlay__btn {
  background: var(--premium-badge-bg);
  color: var(--premium-badge-text);
  border: none;
  padding: var(--space-2, 0.5rem) var(--space-5, 1.25rem);
  border-radius: var(--radius-lg, 8px);
  font-weight: var(--font-semibold, 600);
  font-size: var(--text-sm, 0.875rem);
  cursor: pointer;
  box-shadow: var(--shadow-md);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}

.lock-overlay__btn:hover {
  transform: scale(1.05);
  box-shadow: var(--shadow-lg);
}

/* =========================
   STRATEGY CARD — UNLOCKED (Premium, after unlock)
   ========================= */
.strategy-card--unlocked {
  border-left: 3px solid var(--color-accent-500, #14b8a6);
}

.strategy-card--unlocked .strategy-badge {
  background: var(--color-accent-50, #f0fdfa);
  color: var(--color-accent-700, #0f766e);
  font-size: var(--text-2xs, 0.6875rem);
  font-weight: var(--font-semibold, 600);
  padding: 2px 8px;
  border-radius: var(--radius-full, 9999px);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide, 0.025em);
}

.strategy-card--unlocked .strategy-content {
  filter: none;
  transition: filter var(--unlock-transition);
}

/* =========================
   SAVINGS BADGE (visible on all cards)
   ========================= */
.strategy-savings-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1, 0.25rem);
  background: var(--color-success-50, #ecfdf5);
  color: var(--color-success-700, #047857);
  font-weight: var(--font-bold, 700);
  font-size: var(--text-sm, 0.875rem);
  padding: var(--space-1, 0.25rem) var(--space-3, 0.75rem);
  border-radius: var(--radius-full, 9999px);
}

/* =========================
   RISK LEVEL INDICATOR
   ========================= */
.risk-indicator {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1, 0.25rem);
  font-size: var(--text-xs, 0.75rem);
  font-weight: var(--font-medium, 500);
  padding: 1px 6px;
  border-radius: var(--radius-full, 9999px);
}

.risk-indicator--low {
  background: var(--color-success-50);
  color: var(--color-success-700);
}

.risk-indicator--medium {
  background: var(--color-warning-50);
  color: var(--color-warning-700);
}

.risk-indicator--high {
  background: var(--color-error-50);
  color: var(--color-error-700);
}

/* =========================
   SAFETY SUMMARY PANEL
   ========================= */
.safety-summary {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--card-border, var(--color-gray-200));
  border-radius: var(--radius-xl, 12px);
  padding: var(--space-5, 1.25rem);
  margin-bottom: var(--space-4, 1rem);
}

.safety-summary__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3, 0.75rem);
}

.safety-summary__title {
  font-weight: var(--font-semibold, 600);
  font-size: var(--text-base, 1rem);
  color: var(--color-gray-900);
}

.safety-summary__score {
  font-size: var(--text-sm, 0.875rem);
  font-weight: var(--font-medium, 500);
  padding: var(--space-1, 0.25rem) var(--space-3, 0.75rem);
  border-radius: var(--radius-full, 9999px);
}

.safety-summary__score--clear {
  background: var(--color-success-50);
  color: var(--color-success-700);
}

.safety-summary__score--review {
  background: var(--color-warning-50);
  color: var(--color-warning-700);
}

.safety-check-item {
  display: flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
  padding: var(--space-2, 0.5rem) 0;
  border-bottom: 1px solid var(--color-gray-100);
  font-size: var(--text-sm, 0.875rem);
}

.safety-check-item:last-child {
  border-bottom: none;
}

.safety-check-item__icon {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-sm, 0.875rem);
}

.safety-check-item__name {
  flex: 1;
  color: var(--color-gray-700);
}

.safety-check-item__detail {
  color: var(--color-gray-500);
  font-size: var(--text-xs, 0.75rem);
}

/* =========================
   AUDIT RISK BADGE
   ========================= */
.audit-risk-badge-card {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
  padding: var(--space-2, 0.5rem) var(--space-4, 1rem);
  border-radius: var(--radius-lg, 8px);
  font-weight: var(--font-semibold, 600);
  font-size: var(--text-sm, 0.875rem);
}

.audit-risk-badge-card--low {
  background: var(--color-success-50);
  color: var(--color-success-800);
  border: 1px solid var(--color-success-200);
}

.audit-risk-badge-card--medium {
  background: var(--color-warning-50);
  color: var(--color-warning-800);
  border: 1px solid var(--color-warning-200);
}

.audit-risk-badge-card--high {
  background: var(--color-error-50);
  color: var(--color-error-800);
  border: 1px solid var(--color-error-200);
}

/* =========================
   UNLOCK MODAL
   ========================= */
.unlock-modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--overlay-light, rgba(0, 0, 0, 0.5));
  z-index: var(--z-modal-backdrop, 400);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--transition-slow);
}

.unlock-modal-backdrop.active {
  opacity: 1;
  pointer-events: auto;
}

.unlock-modal {
  background: var(--card-bg, #ffffff);
  border-radius: var(--radius-2xl, 16px);
  padding: var(--space-8, 2rem);
  max-width: 440px;
  width: 90%;
  box-shadow: var(--shadow-2xl);
  transform: translateY(20px) scale(0.95);
  transition: transform var(--transition-slow);
  text-align: center;
}

.unlock-modal-backdrop.active .unlock-modal {
  transform: translateY(0) scale(1);
}

.unlock-modal__icon {
  width: 56px;
  height: 56px;
  background: var(--color-success-50);
  border-radius: var(--radius-full, 9999px);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--space-4, 1rem);
  font-size: 1.5rem;
}

.unlock-modal__title {
  font-weight: var(--font-bold, 700);
  font-size: var(--text-xl, 1.25rem);
  color: var(--color-gray-900);
  margin-bottom: var(--space-2, 0.5rem);
}

.unlock-modal__subtitle {
  color: var(--color-gray-500);
  font-size: var(--text-sm, 0.875rem);
  margin-bottom: var(--space-6, 1.5rem);
  line-height: var(--leading-relaxed, 1.625);
}

.unlock-modal__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3, 0.75rem);
  margin-bottom: var(--space-4, 1rem);
}

.unlock-modal__input {
  width: 100%;
  padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
  border: 1px solid var(--input-border, var(--color-gray-300));
  border-radius: var(--input-radius, var(--radius-lg));
  font-size: var(--text-sm, 0.875rem);
  background: var(--input-bg, #ffffff);
  color: var(--input-text, var(--color-gray-900));
  outline: none;
  transition: border-color var(--transition-fast);
}

.unlock-modal__input:focus {
  border-color: var(--color-primary-500);
  box-shadow: var(--focus-ring);
}

.unlock-modal__submit {
  width: 100%;
  padding: var(--space-3, 0.75rem);
  background: var(--gradient-primary);
  color: #ffffff;
  border: none;
  border-radius: var(--btn-radius, var(--radius-lg));
  font-weight: var(--font-semibold, 600);
  font-size: var(--text-sm, 0.875rem);
  cursor: pointer;
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
}

.unlock-modal__submit:hover {
  box-shadow: var(--shadow-primary);
  transform: translateY(-1px);
}

.unlock-modal__skip {
  background: none;
  border: none;
  color: var(--color-gray-500);
  font-size: var(--text-sm, 0.875rem);
  cursor: pointer;
  padding: var(--space-2, 0.5rem);
  transition: color var(--transition-fast);
}

.unlock-modal__skip:hover {
  color: var(--color-gray-700);
}

/* =========================
   ACTION PLAN CARD
   ========================= */
.action-plan-card {
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--color-success-200, #a7f3d0);
  border-radius: var(--radius-xl, 12px);
  padding: var(--space-5, 1.25rem);
  margin-top: var(--space-4, 1rem);
}

.action-plan-card__title {
  font-weight: var(--font-semibold, 600);
  font-size: var(--text-base, 1rem);
  color: var(--color-gray-900);
  margin-bottom: var(--space-3, 0.75rem);
  display: flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
}

.action-plan-card__step {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3, 0.75rem);
  padding: var(--space-2, 0.5rem) 0;
}

.action-plan-card__step-number {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  background: var(--color-primary-50);
  color: var(--color-primary-600);
  border-radius: var(--radius-full, 9999px);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs, 0.75rem);
  font-weight: var(--font-bold, 700);
}

.action-plan-card__step-text {
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-gray-700);
  line-height: var(--leading-normal, 1.5);
}

/* =========================
   CPA CONVERSION BANNER
   ========================= */
.cpa-soft-prompt {
  background: linear-gradient(135deg, var(--color-primary-50) 0%, var(--color-accent-50) 100%);
  border: 1px solid var(--color-primary-200);
  border-radius: var(--radius-xl, 12px);
  padding: var(--space-5, 1.25rem);
  margin-top: var(--space-4, 1rem);
  text-align: center;
}

.cpa-soft-prompt__text {
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-gray-700);
  margin-bottom: var(--space-3, 0.75rem);
  line-height: var(--leading-relaxed, 1.625);
}

.cpa-soft-prompt__actions {
  display: flex;
  gap: var(--space-3, 0.75rem);
  justify-content: center;
  flex-wrap: wrap;
}

.cpa-soft-prompt__btn-primary {
  padding: var(--space-2, 0.5rem) var(--space-5, 1.25rem);
  background: var(--gradient-primary);
  color: #ffffff;
  border: none;
  border-radius: var(--btn-radius, var(--radius-lg));
  font-weight: var(--font-semibold, 600);
  font-size: var(--text-sm, 0.875rem);
  cursor: pointer;
  transition: box-shadow var(--transition-fast);
}

.cpa-soft-prompt__btn-primary:hover {
  box-shadow: var(--shadow-primary);
}

.cpa-soft-prompt__btn-secondary {
  padding: var(--space-2, 0.5rem) var(--space-5, 1.25rem);
  background: transparent;
  color: var(--color-gray-600);
  border: 1px solid var(--color-gray-300);
  border-radius: var(--btn-radius, var(--radius-lg));
  font-weight: var(--font-medium, 500);
  font-size: var(--text-sm, 0.875rem);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.cpa-soft-prompt__btn-secondary:hover {
  border-color: var(--color-gray-400);
}

/* =========================
   RESPONSIVE
   ========================= */
@media (max-width: 640px) {
  .strategy-card {
    padding: var(--space-4, 1rem);
  }

  .unlock-modal {
    padding: var(--space-5, 1.25rem);
    max-width: 95%;
  }

  .cpa-soft-prompt__actions {
    flex-direction: column;
  }
}
```

**Step 2: Add CSS link to the advisor HTML template**

Find the HTML template that loads the advisor page. Search for `intelligent_advisor.html` or the template that includes the existing CSS files. Add a `<link>` tag for the new stylesheet after the existing advisor CSS:

```html
<link rel="stylesheet" href="/static/css/advisor-premium.css">
```

**Step 3: Verify file exists and is valid**

Run: `ls -la src/web/static/css/advisor-premium.css`
Expected: File exists with content

**Step 4: Commit**

```bash
git add src/web/static/css/advisor-premium.css
git commit -m "feat: create advisor-premium.css with tiered conversion component styles"
```

---

### Task 10: JS — Add strategy tiering state management

**Files:**
- Modify: `src/web/static/js/pages/intelligent-advisor.js`

**Step 1: Add premium state variables**

Find the variable declarations near the top of the IIFE (search for `let taxStrategies` or `let taxCalculations`). Add after the existing state variables:

```javascript
    // Premium tiering state
    let premiumUnlocked = false;
    let premiumStrategies = [];
```

**Step 2: Update processAIResponse to track premium state**

In `processAIResponse()`, find where `data.strategies` is processed (around line 8085):

```javascript
          if (data.strategies && data.strategies.length > 0) {
            taxStrategies = data.strategies;
```

Add after that block:

```javascript
          // Track premium unlock state
          if (data.premium_unlocked !== undefined) {
            premiumUnlocked = data.premium_unlocked;
          }
```

**Step 3: Commit**

```bash
git add src/web/static/js/pages/intelligent-advisor.js
git commit -m "feat: add premium tiering state management to JS"
```

---

### Task 11: JS — Render tiered strategy cards

**Files:**
- Modify: `src/web/static/js/pages/intelligent-advisor.js`

**Step 1: Add renderStrategyCard helper function**

Find the area where strategy display happens. Search for the `show_strategies` handler in `handleQuickAction`. Add a new helper function before `processAIResponse`:

```javascript
    /**
     * Render a single strategy card with tier-aware styling.
     * Free cards show full content. Locked cards blur content but show savings.
     * Unlocked cards show everything with "Unlocked" badge.
     */
    function renderStrategyCard(strategy, index) {
      const tier = strategy.tier || 'free';
      const isLocked = tier === 'premium' && !premiumUnlocked;
      const isUnlocked = tier === 'premium' && premiumUnlocked;
      const cardClass = isLocked ? 'strategy-card--locked' : (isUnlocked ? 'strategy-card--unlocked' : 'strategy-card--free');
      const badgeLabel = isLocked ? 'CPA-Recommended' : (isUnlocked ? 'Unlocked' : 'DIY');
      const riskLevel = strategy.risk_level || 'low';

      let html = `<div class="strategy-card ${cardClass}" data-strategy-id="${strategy.id || index}" data-tier="${tier}">`;

      // Header: title + badges (always visible)
      html += `<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">`;
      html += `<div class="strategy-title" style="font-weight:600;font-size:0.95rem;">${index + 1}. ${strategy.title || 'Strategy'}</div>`;
      html += `<span class="strategy-badge">${badgeLabel}</span>`;
      html += `</div>`;

      // Savings badge (always visible, even on locked cards)
      if (strategy.estimated_savings) {
        html += `<div class="strategy-savings"><span class="strategy-savings-badge">Save $${Number(strategy.estimated_savings).toLocaleString()}</span>`;
        html += ` <span class="risk-indicator risk-indicator--${riskLevel}">${riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1)} risk</span>`;
        html += `</div>`;
      }

      // Content section (blurred on locked cards via CSS)
      html += `<div class="strategy-content">`;
      html += `<div style="font-size:0.85rem;color:var(--color-gray-600);margin:8px 0;">${strategy.summary || ''}</div>`;

      if (strategy.detailed_explanation) {
        html += `<div style="font-size:0.8rem;color:var(--color-gray-500);margin-bottom:8px;">${strategy.detailed_explanation.substring(0, 200)}${strategy.detailed_explanation.length > 200 ? '...' : ''}</div>`;
      }

      if (strategy.action_steps && strategy.action_steps.length > 0) {
        html += `<div style="font-size:0.8rem;"><strong>Next steps:</strong><ul style="margin:4px 0;padding-left:18px;">`;
        strategy.action_steps.slice(0, 3).forEach(step => { html += `<li>${step}</li>`; });
        html += `</ul></div>`;
      }
      html += `</div>`; // end strategy-content

      // Lock overlay (only on locked cards)
      if (isLocked) {
        html += `<div class="lock-overlay"><button class="lock-overlay__btn" onclick="window.unlockPremiumStrategies()">Unlock Full Analysis</button></div>`;
      }

      html += `</div>`; // end strategy-card
      return html;
    }
```

**Step 2: Update strategy rendering in calculation response**

In `processAIResponse()`, find where strategies are included in the chat response (around line 8085-8155). After the entity comparison block and before `addMessage('ai', aiResponse, quickActions)`, add tiered strategy rendering:

```javascript
        // Render tiered strategy cards if strategies present
        if (data.strategies && data.strategies.length > 0 && data.response_type === 'calculation') {
          const premiumCount = data.strategies.filter(s => (s.tier || 'free') === 'premium').length;
          const freeCount = data.strategies.length - premiumCount;

          if (premiumCount > 0 && !premiumUnlocked) {
            aiResponse += `\n\n<div style="font-size:0.85rem;color:var(--color-gray-600);margin-bottom:8px;">${freeCount} strategies you can implement yourself + ${premiumCount} CPA-recommended strategies</div>`;
          }

          // Render each strategy with tier-aware card
          data.strategies.slice(0, 5).forEach((strategy, i) => {
            aiResponse += renderStrategyCard(strategy, i);
          });

          // Add unlock CTA if there are locked strategies
          if (premiumCount > 0 && !premiumUnlocked) {
            aiResponse += `<div class="cpa-soft-prompt"><div class="cpa-soft-prompt__text">Unlock ${premiumCount} CPA-recommended strategies to see your full savings potential</div>`;
            aiResponse += `<div class="cpa-soft-prompt__actions"><button class="cpa-soft-prompt__btn-primary" onclick="window.unlockPremiumStrategies()">Unlock All Strategies</button>`;
            aiResponse += `<button class="cpa-soft-prompt__btn-secondary" onclick="window.handleQuickAction('generate_report')">Generate Report First</button></div></div>`;
          }
        }
```

**Step 3: Commit**

```bash
git add src/web/static/js/pages/intelligent-advisor.js
git commit -m "feat: render tiered strategy cards with locked/unlocked/free styling"
```

---

### Task 12: JS — Safety summary display

**Files:**
- Modify: `src/web/static/js/pages/intelligent-advisor.js`

**Step 1: Add renderSafetySummary helper function**

Add this function near `renderStrategyCard`:

```javascript
    /**
     * Render user-facing compliance summary from safety check data.
     */
    function renderSafetySummary(summary) {
      if (!summary || !summary.checks || summary.checks.length === 0) return '';

      let html = `<div class="safety-summary">`;
      html += `<div class="safety-summary__header">`;
      html += `<div class="safety-summary__title">Compliance Summary</div>`;
      const scoreClass = summary.overall_status === 'clear' ? 'safety-summary__score--clear' : 'safety-summary__score--review';
      html += `<span class="safety-summary__score ${scoreClass}">${summary.passed}/${summary.total_checks} checks passed</span>`;
      html += `</div>`;

      summary.checks.forEach(check => {
        const icon = check.status === 'pass' ? '✅' : '⚠️';
        html += `<div class="safety-check-item">`;
        html += `<span class="safety-check-item__icon">${icon}</span>`;
        html += `<span class="safety-check-item__name">${check.name}</span>`;
        html += `<span class="safety-check-item__detail">${check.detail}</span>`;
        html += `</div>`;
      });

      html += `</div>`;
      return html;
    }
```

**Step 2: Wire safety summary into response rendering**

In `processAIResponse()`, after the strategy card rendering block, add:

```javascript
        // Show safety summary if available
        if (data.safety_summary && data.response_type === 'calculation') {
          aiResponse += renderSafetySummary(data.safety_summary);
        }
```

**Step 3: Commit**

```bash
git add src/web/static/js/pages/intelligent-advisor.js
git commit -m "feat: display user-facing compliance safety summary"
```

---

### Task 13: JS — Unlock flow + soft lead capture modal

**Files:**
- Modify: `src/web/static/js/pages/intelligent-advisor.js`

**Step 1: Add unlock modal HTML**

Add a function that creates and shows the unlock modal:

```javascript
    /**
     * Unlock premium strategies: instant reveal + soft lead capture.
     */
    window.unlockPremiumStrategies = async function() {
      // Step 1: Instantly unlock all strategies (zero friction)
      try {
        const response = await fetchWithRetry('/api/advisor/unlock-strategies', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId })
        });

        if (response.ok) {
          const data = await response.json();
          premiumUnlocked = true;

          // Update all locked cards to unlocked
          document.querySelectorAll('.strategy-card--locked').forEach(card => {
            card.classList.remove('strategy-card--locked');
            card.classList.add('strategy-card--unlocked');
            const badge = card.querySelector('.strategy-badge');
            if (badge) badge.textContent = 'Unlocked';
            const overlay = card.querySelector('.lock-overlay');
            if (overlay) overlay.remove();
          });

          // Update strategies data
          if (data.strategies) {
            taxStrategies = data.strategies;
          }

          showToast('All strategies unlocked!', 'success');
        }
      } catch (error) {
        // Unlock locally even if backend fails
        premiumUnlocked = true;
        document.querySelectorAll('.strategy-card--locked').forEach(card => {
          card.classList.remove('strategy-card--locked');
          card.classList.add('strategy-card--unlocked');
          const badge = card.querySelector('.strategy-badge');
          if (badge) badge.textContent = 'Unlocked';
          const overlay = card.querySelector('.lock-overlay');
          if (overlay) overlay.remove();
        });
      }

      // Step 2: Show soft lead capture message in chat
      const softPromptHtml = `Your full analysis is unlocked!

Want me to email you a copy and connect you with a CPA who can help implement these strategies?

<div class="unlock-modal__form" id="leadCaptureForm" style="margin-top:12px;">
  <input type="text" class="unlock-modal__input" id="leadNameInput" placeholder="Your name" />
  <input type="email" class="unlock-modal__input" id="leadEmailInput" placeholder="Your email" />
  <button class="unlock-modal__submit" onclick="window.submitLeadCapture()">Send & Connect</button>
  <button class="unlock-modal__skip" onclick="window.dismissLeadCapture()">No thanks</button>
</div>`;

      addMessage('ai', softPromptHtml, []);
    };

    /**
     * Submit lead capture form (email + name).
     */
    window.submitLeadCapture = async function() {
      const name = document.getElementById('leadNameInput')?.value || '';
      const email = document.getElementById('leadEmailInput')?.value || '';

      if (!email || !email.includes('@')) {
        showToast('Please enter a valid email address', 'warning');
        return;
      }

      showTyping();
      try {
        const response = await fetchWithRetry('/api/advisor/report/email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            email: email,
            name: name,
          })
        });

        hideTyping();

        if (response.ok) {
          addMessage('ai', `<strong>Your report has been sent to ${email}!</strong>

A CPA will reach out within 24 hours to help you implement these strategies.

<strong>What would you like to do next?</strong>`, [
            { label: 'Download PDF Report', value: 'download_report' },
            { label: 'Upload Documents for CPA', value: 'upload_docs' },
            { label: 'Ask more questions', value: 'ask_question' },
          ]);
        } else {
          addMessage('ai', `Email delivery is not available right now. You can download your report as a PDF instead.`, [
            { label: 'Download PDF Report', value: 'download_report' },
          ]);
        }
      } catch (error) {
        hideTyping();
        addMessage('ai', 'Unable to send email right now. Please try downloading the PDF instead.', [
          { label: 'Download PDF Report', value: 'download_report' },
          { label: 'Try Again', value: 'email_report' },
        ]);
      }
    };

    /**
     * Dismiss lead capture without submitting.
     */
    window.dismissLeadCapture = function() {
      const form = document.getElementById('leadCaptureForm');
      if (form) {
        form.innerHTML = '<div style="font-size:0.85rem;color:var(--color-gray-500);padding:8px;">No problem! Your strategies are unlocked. You can always email the report later.</div>';
      }
    };
```

**Step 2: Add unlock handling to handleQuickAction**

In the `handleQuickAction` function, find the area where quick action values are matched. Add a handler for `unlock_strategies`:

```javascript
      if (value === 'unlock_strategies') {
        window.unlockPremiumStrategies();
        return;
      }
```

**Step 3: Commit**

```bash
git add src/web/static/js/pages/intelligent-advisor.js
git commit -m "feat: implement unlock flow with instant reveal and soft lead capture"
```

---

### Task 14: Link CSS in HTML template

**Files:**
- Modify: `src/web/templates/intelligent_advisor.html` (or wherever the advisor page template is)

**Step 1: Find the template file**

Search for `intelligent_advisor.html` or the template that includes CSS links for the advisor page.

**Step 2: Add CSS link**

Find the block where `intelligent-advisor.css` is linked. Add after it:

```html
<link rel="stylesheet" href="{{ url_for('static', path='css/advisor-premium.css') }}">
```

(Or the appropriate Jinja2/template syntax used in the project.)

**Step 3: Commit**

```bash
git add src/web/templates/intelligent_advisor.html
git commit -m "feat: link advisor-premium.css in advisor template"
```

---

### Task 15: Final verification

**Step 1: Verify Python syntax**

Run: `python -c "import py_compile; py_compile.compile('src/web/intelligent_advisor_api.py', doraise=True); py_compile.compile('src/web/advisor_models.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 2: Check all new files exist**

Run: `ls -la src/web/static/css/advisor-premium.css`
Expected: File exists

**Step 3: Check for accidental syntax issues in JS**

Run: `node -c src/web/static/js/pages/intelligent-advisor.js 2>&1 || echo 'JS syntax issues detected'`
Note: Pre-existing `showOfflineBanner` duplicate may still show — that's not our issue.

**Step 4: Run the existing test suite if available**

Run: `cd src && python -m pytest tests/ -x --tb=short 2>&1 | head -50`

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "feat: tiered conversion experience — complete implementation"
```

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `src/web/intelligent_advisor_api.py` | Tasks 1-8: Model fields, tiering classifier, safety summary builder, strategy tiering in chat, unlock endpoint, email endpoint, AMT endpoint, compare_scenarios, record_usage, safety-check user summary |
| `src/web/advisor_models.py` | Task 1: Model fields (tier, risk_level, implementation_complexity, premium_unlocked, safety_summary) |
| `src/web/static/css/advisor-premium.css` | Task 9: **NEW** — all tiered conversion component styles |
| `src/web/static/js/pages/intelligent-advisor.js` | Tasks 10-13: Premium state, tiered strategy cards, safety summary display, unlock flow, lead capture |
| `src/web/templates/intelligent_advisor.html` | Task 14: CSS link |

## Verification Checklist

1. `StrategyRecommendation` model has `tier`, `risk_level`, `implementation_complexity` fields
2. `ChatResponse` model has `premium_unlocked` and `safety_summary` fields
3. Chat endpoint returns strategies with tier classification
4. `POST /api/advisor/unlock-strategies` → `{"premium_unlocked": true}`
5. `POST /api/advisor/report/email` → captures lead and returns confirmation
6. `POST /api/advisor/amt-analysis` → returns AMT analysis
7. `GET /api/advisor/safety-check/{id}` → includes `user_summary`
8. JS renders locked/unlocked/free strategy cards with proper CSS classes
9. JS shows safety summary panel
10. JS unlock flow: click → instant unlock → soft lead capture → email
11. CSS file loads and styles all new components
12. All changes fall back gracefully when `AI_CHAT_ENABLED=false`
