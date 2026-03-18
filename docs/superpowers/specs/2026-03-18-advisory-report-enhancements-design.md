# Advisory Report Enhancements Design Spec

**Date:** 2026-03-18
**Status:** Approved (Rev 2 — post spec review)
**Approach:** Incremental enhancement of existing `AdvisoryReportGenerator`

## Context

The current `AdvisoryReportGenerator` orchestrates 4 engines (TaxCalculator, TaxRecommendationEngine, EntityStructureOptimizer, MultiYearProjectionEngine) to produce 7-section reports. The architecture is sound but has gaps:

- Savings are summed independently (strategies interact)
- "Optimized" tax position is faked (state tax copied as-is)
- AI generates summaries of numbers rather than reasoning about strategies
- Scenario analysis exists (`ScenarioService`, `TaxReasoningService`) but isn't wired in
- Multi-year projections don't show with/without strategy comparison
- AI calls run sequentially (10-20s overhead)
- Low confidence scores don't tell users what data to provide

## Audience

Both paths: lead magnet reports go direct to consumer; full reports go through CPA review before client delivery.

## Performance Target

Full report generation under 15 seconds including all AI calls.

## AI Trust Level

Smart: AI-suggested strategies get validated by the rules engine or calculator when possible. Verified suggestions appear with full confidence. Unverifiable suggestions appear with lower confidence and "Consult your CPA" tag. Nothing is discarded just because the rules engine lacks a specific rule.

---

## Enhancement 1: Pro Forma Comparison (P0)

### Problem
Total savings are summed independently: `total_savings = sum(o.estimated_savings for o in opportunities)`. Strategies interact (401k lowers AGI, changing QBI phaseout, NIIT threshold, etc.). The "optimized" state tax is a copy of current: `optimized_state = current_state`.

### Solution
Add `_generate_pro_forma_comparison()` to `AdvisoryReportGenerator`:

1. Clone the `TaxReturn` object
2. Apply each recommended strategy to the clone (increase 401k, switch deduction method, add HSA, etc.)
3. Run `TaxCalculator.calculate_complete_return()` on the modified clone (includes state tax)
4. Report the actual delta

### Strategy Application Mapping

Each `TaxSavingOpportunity` category maps to a concrete `TaxReturn` field modification. Only categories with directly modifiable fields are applied to the pro forma clone:

| Category | TaxReturn Field(s) Modified | Notes |
|----------|---------------------------|-------|
| `retirement` (SE taxpayer) | `deductions.self_employed_sep_simple` → max SEP-IRA/Solo 401k contribution (25% of net SE income, up to $69,000); `deductions.ira_contributions` → max ($7,000 + $1,000 catch-up) | Fields exist on `Deductions` model. Reduces AGI directly as above-the-line deduction. |
| `retirement` (W-2 employee) | **Not modifiable in pro forma** — W-2 employee 401k deferrals are already excluded from Box 1 wages before they reach the `Income` model. The TaxReturn has no field to increase W-2 401k contributions retroactively. | Strategy appears in report with `marginal_impact: 0.0` and note: "W-2 401k maximization requires employer payroll change — cannot be modeled in pro forma. Estimated savings shown independently." |
| `healthcare` | `deductions.hsa_contributions` → max ($4,300 individual / $8,550 family) | Field exists on `Deductions` model |
| `deductions` | `deductions.use_standard_deduction` → toggle; adjust `deductions.itemized.*` amounts | Fields exist on `Deductions` and `ItemizedDeductions` models |
| `charitable` | `deductions.itemized.charitable_cash` → increase per bunching recommendation | Field exists on `ItemizedDeductions` model |
| `business` | `income.self_employment_expenses` → increase per recommendation | Field exists on `Income` model. Home office/vehicle are sub-categories that reduce SE income via expenses |
| `timing` | **Excluded from pro forma** — income deferral and expense acceleration are cross-year operations that cannot be modeled by modifying a single-year TaxReturn | Noted in report as "timing strategies excluded from pro forma modeling" |

**When a strategy cannot be applied** (category not in the table, or the field is already at the recommended amount): the strategy appears in `strategies_applied` with `marginal_impact: 0.0` and a note explaining why it was not modeled.

### Return Type

`_generate_pro_forma_comparison()` returns a tuple to share the optimized TaxReturn with Enhancement 7 (dual projections):

```python
def _generate_pro_forma_comparison(
    self, tax_return: TaxReturn, recommendations: ComprehensiveRecommendation
) -> tuple[AdvisoryReportSection, TaxReturn]:
    """Returns (section, optimized_tax_return_clone)."""
```

The optimized `TaxReturn` is stored in `generate_report()` and passed to `_generate_multi_year_projection()`.

### Output Schema

```python
AdvisoryReportSection(
    section_id="pro_forma_comparison",
    title="Your Tax Position: Current vs Optimized",
    content={
        "current": {
            "federal_tax": float,
            "state_tax": float,
            "total_tax": float,
            "effective_rate": float,
            "agi": float,
            "taxable_income": float,
        },
        "optimized": {
            "federal_tax": float,
            "state_tax": float,
            "total_tax": float,
            "effective_rate": float,
            "agi": float,
            "taxable_income": float,
        },
        "actual_savings": float,  # current.total - optimized.total
        "rate_reduction": float,  # current.effective_rate - optimized.effective_rate
        "strategies_applied": [
            {"title": str, "modification": str, "marginal_impact": float}
        ],
    }
)
```

### Existing Code Used
- `TaxCalculator.calculate_complete_return()` — runs full federal + state calculation
- `copy.deepcopy(tax_return)` — clone for modification

### Files Modified
- `src/advisory/report_generator.py` — new method `_generate_pro_forma_comparison()`
- Update `generate_report()` to call it and use actual delta for `potential_savings`

---

## Enhancement 2: Fix Optimized State Tax (P0)

### Solution
Solved entirely by Enhancement 1. When the pro forma comparison runs `calculate_complete_return()` on the modified clone, `StateTaxEngine` computes the real optimized state tax. The line `optimized_state = current_state` is deleted.

### Files Modified
- Same as Enhancement 1 (no additional work)

---

## Enhancement 3: Parallelize AI Calls (P1)

### Problem
In `report_generation.py`'s `generate_report` endpoint, 5-7 AI calls run sequentially, adding 10-20 seconds.

### Design Decision: Async/Sync Boundary

**Decision: `AdvisoryReportGenerator.generate_report()` stays synchronous.** Rationale:
- It is called from both async endpoints and sync contexts (PDF generation, CLI tools)
- Making it async would require changes to all call sites
- AI calls within the generator use the existing thread pool pattern (sync wrapper around async AI service)

**Consequence:** All AI calls within `report_generator.py` methods (Enhancements 6, AI narrative in executive summary) use the existing pattern:
```python
from services.ai import get_ai_service, run_async
response = run_async(ai.complete(...))
```

**The `asyncio.gather()` optimization applies only to `report_generation.py`** (the async API endpoint layer), not to the generator itself.

### Solution

**In `report_generation.py` (`generate_report` endpoint):**

Replace sequential calls with `asyncio.gather()`. All AI calls from Enhancements 3 and 6 are included in the same gather to stay within the 15s budget:

```python
summary, multi_summaries, action_plan, email_client, email_internal, ai_strategies = await asyncio.gather(
    chat_engine.generate_executive_summary(profile, calculation, strategies),
    summarizer.generate_all_summaries(report_data, profile.get("name")),
    narrator.generate_action_plan_narrative(action_items, client_profile),
    summarizer.generate_summary_for_email(report_data, "client"),
    summarizer.generate_summary_for_email(report_data, "internal"),
    ai_reasoning_service.discover_strategies(profile, calculation, strategies),  # Enhancement 6
    return_exceptions=True,
)
# Handle any exceptions individually — if a call returned an Exception, use fallback
for i, result in enumerate(results):
    if isinstance(result, Exception):
        logger.warning(f"AI call {i} failed: {result}")
        # Use fallback value
```

**In `report_generator.py` (`_generate_executive_summary`):**

Add a `skip_ai_narrative: bool = False` parameter to `_generate_executive_summary()`. When `True`, the method skips the internal thread pool AI call and returns the section with static content only. The async endpoint sets `skip_ai_narrative=True` because it handles AI narrative generation in the `asyncio.gather()` above, then injects the AI narrative into the section content afterward.

When `generate_report()` is called from a sync context (PDF generation, CLI), `skip_ai_narrative` defaults to `False` and the existing thread pool + 8-second timeout pattern fires as before.

This prevents the dual AI call race condition where both the internal thread pool and the `asyncio.gather()` would fire simultaneously for the same content.

### Target
- AI-dependent sections: 3-5 seconds (parallel)
- Non-AI sections: <1 second (calculation engine)
- Total: under 15 seconds

### Files Modified
- `src/web/advisor/report_generation.py` — `asyncio.gather()` in `generate_report`
- `src/advisory/report_generator.py` — async option for AI narrative call

---

## Enhancement 4: Wire In Scenario Analysis (P1)

### Problem
`src/web/advisor/scenario_analysis.py` has 7 scenario endpoints (Roth, entity, deduction, AMT, multi-year, estate, audit risk) with deterministic fallbacks. None are used in the report.

### Solution
Add `_generate_scenario_comparisons()` to `AdvisoryReportGenerator`. It selects applicable scenarios based on the taxpayer's profile.

**Important:** The deterministic analysis functions (`_deterministic_roth_analysis()`, etc.) take primitive parameters, not `TaxReturn` objects. The generator must extract these primitives from the `TaxReturn`. If required fields are absent, the scenario is skipped.

### Data Field Availability Mapping

| Scenario | Required TaxReturn Fields | Primitive Parameters for Deterministic Function | Skip Condition |
|----------|--------------------------|------------------------------------------------|----------------|
| Roth Conversion | `income.retirement_income` (>0) OR `deductions.ira_contributions` (>0) OR `credits.elective_deferrals_401k` (>0) | `traditional_balance`: estimated from `retirement_income` or contributions; `current_bracket`: from calculation result marginal rate; `projected_bracket`: estimated lower (default 22%); `years_to_retirement`: from age (default 65-age); `filing_status`: from taxpayer | Skip if no retirement fields populated AND age not provided |
| Entity Structure | `income.self_employment_income` (>$40k) | `gross_revenue`: SE income + SE expenses; `business_expenses`: SE expenses; `owner_salary`: None (auto-calculated); `state`: taxpayer.state; `filing_status` | Skip if `self_employment_income` == 0 or < $40k |
| Deduction Strategy | `deductions.itemized.*` (any populated) | `income`: AGI from calc result; `current_deductions`: itemized total; `potential_deductions`: itemized fields dict; `filing_status`; `state` | Skip if all itemized fields are 0 |
| AMT Exposure | `income.amt_iso_exercise_spread` (>0) OR SALT > $10k OR `income.tax_exempt_interest` (>0) | `regular_income`: AGI; `salt_deduction`: SALT total from itemized; `iso_spread`: from income model; `tax_exempt_interest`: from income model; `filing_status` | Skip if no AMT-triggering fields populated |
| Estate Planning | AGI > $500k (from calc result) | `estate_value`: estimated from AGI * 10 (rough proxy); `annual_gifting`: 0; `trusts`: []; `beneficiaries`: dependents count; `state`; `goals`: [] | Skip if AGI <= $500k |

**Deduplication:** If a scenario (e.g., Roth Conversion) was already covered in the recommendations section, the scenario analysis provides the deeper what-if comparison but references the existing recommendation rather than duplicating the title.

For each applicable scenario, call the deterministic analysis function directly (not via HTTP endpoint). Optionally enhance with `TaxReasoningService` AI analysis when `AI_REPORT_NARRATIVES_ENABLED`.

### Output Schema

```python
AdvisoryReportSection(
    section_id="scenario_analysis",
    title="What-If Scenario Analysis",
    content={
        "scenarios": [
            {
                "name": "Roth Conversion Analysis",
                "applicable": True,
                "current_outcome": {"description": str, "tax_impact": float},
                "alternative_outcome": {"description": str, "tax_impact": float},
                "net_benefit": float,
                "recommendation": str,
                "key_factors": [str],
                "action_items": [str],
                "confidence": float,
                "irc_references": [str],
            }
        ],
        "scenarios_skipped": [
            {"name": str, "reason": str}  # e.g., "AMT: Not applicable — no ISO income"
        ],
    }
)
```

### Existing Code Used
- `TaxReasoningService._deterministic_roth_analysis()` (and other `_deterministic_*` methods)
- `TaxReasoningService.analyze_roth_conversion()` etc. (AI path, optional)
- Scenario analysis functions from `scenario_analysis.py`

### Files Modified
- `src/advisory/report_generator.py` — new method `_generate_scenario_comparisons()`
- Update `generate_report()` to insert section after entity comparison

---

## Enhancement 5: Confidence to Data Collection CTAs (P1)

### Problem
`confidence_score` and `data_completeness` are computed but not actionable. Users don't know what data to provide to improve their report.

### Solution
Add `_generate_data_improvement_ctas()` to `AdvisoryReportGenerator`. Analyzes the TaxReturn for missing fields and estimates the potential value of providing that data.

### CTA Rules

| Missing Data | Condition | CTA Message | Potential Value |
|-------------|-----------|-------------|-----------------|
| Business expenses | `is_self_employed` but no expenses | "Add business expenses to reduce SE tax" | "Could save $X in SE tax deductions" |
| Rental details | Has `property_tax` but no rental income | "Do you own rental property? Add details for depreciation deductions" | "$2,000-5,000 in annual deductions" |
| Retirement contributions | No 401k/IRA data, income > $50k | "Add retirement contribution details" | "Up to $X tax reduction" |
| HSA contributions | `deductions.hsa_contributions` == 0 AND income > $30k (proxy for likely having health insurance) | "HSA contributions are triple-tax-advantaged" | "Up to $X deduction" |
| State info | No state specified | "Add your state for accurate state tax calculation" | "State taxes can be 0-13% of income" |
| Capital gains detail | Has `investment_income` but no gains breakdown | "Specify long-term vs short-term gains for accurate rates" | "Long-term gains taxed at 0/15/20% vs ordinary rates" |
| Charitable donations | High income, no charitable data | "Charitable giving could reduce your taxable income" | "Potential savings at your marginal rate" |

### Output Schema

```python
AdvisoryReportSection(
    section_id="data_improvement_opportunities",
    title="Unlock More Savings",
    content={
        "current_completeness": float,  # 0-100
        "target_completeness": 100.0,
        "ctas": [
            {
                "field": str,
                "message": str,
                "potential_unlock": str,
                "priority": "high" | "medium" | "low",
            }
        ],
        "estimated_additional_savings_range": {"low": float, "high": float},
    }
)
```

Only included when `data_completeness < 80%`.

### Files Modified
- `src/advisory/report_generator.py` — new method `_generate_data_improvement_ctas()`
- Potentially `src/recommendation/recommendation_engine.py` — enhance `_calculate_data_completeness()` to return which fields are missing

---

## Enhancement 6: AI as Reasoning Layer (P2)

### Problem
AI currently generates summaries of calculation results. It doesn't discover strategies the rules engine missed.

### Solution
Add `_generate_ai_discovered_strategies()` to `AdvisoryReportGenerator`:

1. Collect: full profile, calculation results, existing recommendations
2. Call `UnifiedAIService.reason()` (Claude, temperature 0.3, "senior tax partner" system prompt)
3. Prompt: "Given this taxpayer's complete situation and the strategies already identified, what additional tax optimization opportunities exist? Consider: Roth conversion ladders, tax gain harvesting, charitable remainder trusts, qualified opportunity zones, backdoor Roth IRA, mega backdoor Roth, net unrealized appreciation, installment sales, like-kind exchanges, cost segregation, conservation easements, etc."
4. Parse response into candidate strategies
5. Validate each candidate:
   - If calculable (e.g., "max HSA"): run calculator to verify savings → full confidence
   - If rules-engine has a matching rule: verified → full confidence
   - If neither: include with reduced confidence (70%) and "AI-identified — verify with CPA" tag

### AI Response Parsing Contract

The prompt instructs Claude to return strategies in a structured JSON format. The prompt ends with:

```
Respond ONLY with a JSON array. Each element:
{
  "title": "Strategy name",
  "category": "retirement|investment|charitable|business|estate|timing",
  "estimated_savings": 0,
  "description": "Why this applies to this taxpayer",
  "action_required": "Specific next step",
  "priority": "immediate|current_year|next_year|long_term",
  "irc_reference": "IRC Section or IRS Form number",
  "confidence_explanation": "Why you believe this applies"
}
Return an empty array [] if no additional strategies found.
```

**Parsing function:** `_parse_ai_strategies(response_content: str) -> List[Dict]`:
1. Extract JSON array from response (handle markdown code blocks)
2. Validate each item has required keys (`title`, `category`, `estimated_savings`, `irc_reference`)
3. Discard items missing required keys
4. Cap at 5 strategies
5. If JSON parsing fails entirely, return empty list (fallback)

Each parsed strategy is converted to a `TaxSavingOpportunity` with `source="ai_reasoning"` in metadata.

### Output

AI-discovered strategies are appended to the `recommendations` section with a `source: "ai_reasoning"` tag. They appear in the action plan with appropriate confidence levels.

### Guardrails
- AI call is included in the `asyncio.gather()` from Enhancement 3 (not a separate sequential call)
- AI call timeout: 10 seconds
- Max 5 AI-discovered strategies per report
- Each must have a plausible IRS reference (IRC section, form number)
- Fallback: if AI fails, section is silently omitted (report still complete)

### Existing Code Used
- `UnifiedAIService.reason()` — Claude with tax partner system prompt
- `AIRecommendationEnhancer.enhance_recommendation()` — for formatting
- `TaxCalculator` — for validation calculations

### Files Modified
- `src/advisory/report_generator.py` — new method `_generate_ai_discovered_strategies()`
- Update `_generate_recommendations()` to merge AI strategies into opportunity list

---

## Enhancement 7: Dual Multi-Year Projections (P2)

### Problem
Multi-year projections show only the baseline (current position projected forward). No comparison of "do nothing" vs "implement strategies."

### Solution
Enhance `_generate_multi_year_projection()` to run two projections:

1. **Baseline** — current TaxReturn projected forward (existing behavior)
2. **Optimized** — pro forma TaxReturn (from Enhancement 1) projected forward

Both use the same assumptions (income growth, inflation). The gap between them is the cumulative value of implementing strategies.

### Output Schema

```python
content={
    "baseline": {
        "yearly_data": [...],
        "total_projected_tax": float,
    },
    "optimized": {
        "yearly_data": [...],
        "total_projected_tax": float,
    },
    "cumulative_savings_by_year": [float, ...],
    "total_savings_over_period": float,
    "chart_data": {  # from generate_projection_timeline_data()
        "years": [2025, 2026, 2027, ...],
        "baseline_tax": [X, Y, Z, ...],
        "optimized_tax": [X', Y', Z', ...],
        "savings_gap": [X-X', Y-Y', Z-Z', ...],
    },
}
```

### Existing Code Used
- `MultiYearProjectionEngine.project_multi_year()` — called twice
- `generate_projection_timeline_data()` — for chart-ready output

### Files Modified
- `src/advisory/report_generator.py` — modify `_generate_multi_year_projection()`

---

## Enhancement 8: S-Corp Salary Optimization Curve (P3)

### Problem
Entity comparison shows a single salary point. CPAs explore a curve of salary/distribution splits to find the optimal balance of SE tax savings vs IRS audit risk.

### Solution
Enhance `_generate_entity_comparison()` to generate a salary curve:

1. Get reasonable salary range from `calculate_reasonable_salary(net_income, gross_revenue)`
2. Generate 6-8 data points from IRS minimum ($40k floor) to 100% of net income
3. For each salary point:
   a. Call `calculate_scorp_savings(net_income, salary_point)` to get net tax savings
   b. Call `calculate_reasonable_salary(net_income, gross_revenue, fixed_salary=salary_point)` to get the IRS risk level at that specific point
4. Identify the optimal salary (max savings where `irs_risk_level` is "low" or "medium")

The `optimizer` instance used is the one already created in `_generate_entity_comparison()` (lines 426-438), not a new instance.

**IRS Risk Calculation Fix:** The current `calculate_reasonable_salary(fixed_salary=X)` returns `irs_risk_level="unknown"` when a fixed salary is provided (it skips the ratio-based risk logic). The implementer must compute the IRS risk level inline for each salary curve point using the salary-to-net-income ratio:
```python
ratio = salary_point / net_income
if ratio >= 0.60: irs_risk = "low"
elif ratio >= 0.40: irs_risk = "medium"
else: irs_risk = "high"
```
This mirrors the ratio logic in the `else` branch of `calculate_reasonable_salary()`. Alternatively, the implementer may patch `calculate_reasonable_salary()` to compute risk for `fixed_salary` inputs — but that is an optional improvement, not required.

### Output Schema

```python
content={
    # ... existing entity comparison data ...
    "salary_optimization": {
        "curve": [
            {
                "salary": float,
                "distribution": float,
                "total_tax": float,
                "savings_vs_sole_prop": float,
                "irs_risk": "low" | "medium" | "high",
            }
        ],
        "optimal_salary": float,
        "reasonable_range": {"low": float, "high": float},
        "recommended_salary": float,
        "savings_at_recommended": float,
        "methodology": str,
    }
}
```

### Existing Code Used
- `EntityStructureOptimizer.calculate_reasonable_salary()`
- `EntityStructureOptimizer.calculate_scorp_savings()`

### Files Modified
- `src/advisory/report_generator.py` — enhance `_generate_entity_comparison()`

---

## Enhancement 9: Strategy Interaction Modeling (P3)

### Problem
`total_savings = sum(o.estimated_savings)` double-counts when strategies interact. Contributing to a 401k lowers AGI, which changes QBI eligibility, NIIT threshold, etc.

### Solution
Add `_model_strategy_interactions()` to `AdvisoryReportGenerator`:

1. Sort strategies by independent savings (highest first)
2. For each step i (0 to N-1):
   a. **Fresh deepcopy** of the original (unmodified) TaxReturn
   b. Apply strategies 0 through i (cumulatively) to the fresh clone
   c. Run `calculate_complete_return()` on the clone
   d. Record marginal savings = (previous step's total tax) - (this step's total tax)
3. Report both independent and marginal savings for each strategy

**Critical:** Each cumulative step starts from a fresh `deepcopy()` of the original TaxReturn, NOT from the previously-mutated clone. This is required because `calculate_complete_return()` mutates the TaxReturn in place (writes `tax_liability`, `adjusted_gross_income`, `taxable_income`, etc.), which would corrupt subsequent strategy applications.

```python
# Correct pseudocode
original = tax_return  # unmodified original
baseline_total_tax = tax_return.combined_tax_liability  # from existing calculation (Section 2)
prev_step_tax = baseline_total_tax  # initialize to baseline before any strategies

for i in range(len(sorted_strategies)):
    working_copy = copy.deepcopy(original)
    for j in range(i + 1):
        apply_strategy(working_copy, sorted_strategies[j])
    result = self.tax_calculator.calculate_complete_return(working_copy)
    new_total_tax = result.combined_tax_liability
    marginal_savings = prev_step_tax - new_total_tax
    cumulative_total = baseline_total_tax - new_total_tax
    prev_step_tax = new_total_tax
```

### Output Schema

```python
content={
    "interaction_analysis": [
        {
            "strategy": str,
            "independent_savings": float,  # if applied alone
            "marginal_savings": float,     # when applied after higher-priority strategies
            "cumulative_total": float,     # running total
            "interaction_note": str | None,  # e.g., "Reduced by $2,400 due to AGI change from 401k maximization"
        }
    ],
    "naive_total": float,    # sum of independent savings (the old number)
    "actual_total": float,   # sum of marginal savings (the real number)
    "interaction_effect": float,  # naive - actual (positive = strategies overlap)
}
```

### Performance Note
This requires N+1 calculator runs AND N+1 `deepcopy()` calls. For N=8 strategies: 9 calculator runs (~100ms) + 9 deepcopy calls (~50ms) = ~150ms total. Acceptable within the 15s budget.

### Model Change
Add `marginal_savings: Optional[float] = None` to `TaxSavingOpportunity` dataclass (default `None` preserves backward compatibility with existing 80+ tests). This field is populated only by the interaction modeling step, not by the recommendation engine itself.

### Files Modified
- `src/advisory/report_generator.py` — new method `_model_strategy_interactions()`
- Update `generate_report()` to use interaction-modeled total instead of naive sum
- `src/recommendation/recommendation_engine.py` — add `marginal_savings: Optional[float] = None` to `TaxSavingOpportunity`

---

## Updated Report Section Order

After all enhancements, the `FULL_ANALYSIS` report contains:

1. **Executive Summary** (existing, enhanced with AI narrative)
2. **Current Tax Position** (existing)
3. **Pro Forma Comparison** (NEW — Enhancement 1)
4. **Tax Optimization Recommendations** (existing, enhanced with AI-discovered strategies — Enhancement 6)
5. **Strategy Interaction Analysis** (NEW — Enhancement 9)
6. **Scenario Analysis** (NEW — Enhancement 4: Roth, deduction, AMT, estate)
7. **Business Entity Comparison** (existing, enhanced with salary curve — Enhancement 8)
8. **Multi-Year Projection** (existing, enhanced with baseline vs optimized — Enhancement 7)
9. **Data Improvement Opportunities** (NEW — Enhancement 5, conditional on completeness < 80%)
10. **Prioritized Action Plan** (existing)
11. **Disclaimers & Methodology** (existing)

## Implementation Order

1. Enhancement 1 + 2 (Pro forma + fix state tax) — foundation for everything else
2. Enhancement 3 (Parallelize AI) — immediate performance win
3. Enhancement 5 (Confidence CTAs) — simple, high value
4. Enhancement 9 (Strategy interactions) — depends on Enhancement 1's clone mechanism
5. Enhancement 7 (Dual projections) — depends on Enhancement 1's optimized TaxReturn
6. Enhancement 4 (Scenario analysis) — independent, uses existing services
7. Enhancement 8 (Salary curve) — independent, uses existing optimizer
8. Enhancement 6 (AI reasoning) — last because it's the most complex integration

## Performance Budget (15s Target)

| Component | Time | Notes |
|-----------|------|-------|
| Calculator runs (pro forma, interactions) | ~300ms | N+1 deepcopy + calculate calls |
| Recommendation engine | ~200ms | 5 sub-analyzers |
| Entity optimizer + salary curve | ~50ms | 8 `calculate_scorp_savings()` calls |
| Multi-year projections (x2) | ~100ms | Baseline + optimized |
| Scenario analysis (deterministic) | ~50ms | 3-5 deterministic functions |
| **All AI calls (parallel via `asyncio.gather()`)** | **3-5s** | Enhancement 3 + 6 in single gather |
| Report assembly + serialization | ~50ms | |
| **Total** | **~4-6s** | Well within 15s budget |

**Key:** Enhancement 6's AI reasoning call (10s timeout) is included in the same `asyncio.gather()` as all other AI calls. It does NOT run sequentially after them.

## Testing Strategy

Each enhancement gets:
- Unit tests for the new method in `report_generator.py`
- Integration test verifying the section appears in the full report output
- Edge case tests (missing data, zero income, AI failure fallbacks)

Pro forma comparison (Enhancement 1) needs the most thorough testing:
- Verify clone doesn't mutate original TaxReturn
- Verify strategies are correctly applied to clone
- Verify savings delta matches manual calculation
- Test with various filing statuses and income combinations
