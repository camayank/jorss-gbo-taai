# Advisory Report Enhancements Design Spec

**Date:** 2026-03-18
**Status:** Approved
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

Each `TaxSavingOpportunity` category maps to a TaxReturn modification:

| Category | Modification |
|----------|-------------|
| `retirement` | Increase `retirement_contributions` to recommended amount |
| `healthcare` | Set `hsa_contributions` to max ($4,300 individual / $8,550 family) |
| `deductions` | Switch `use_standard_deduction` flag; adjust itemized amounts |
| `charitable` | Increase `charitable_donations` per bunching recommendation |
| `business` | Add `home_office_deduction`, `vehicle_deduction` per recommendation |
| `timing` | Defer income or accelerate expenses per recommendation |

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

### Solution

**In `report_generation.py` (`generate_report` endpoint):**

Replace sequential calls with `asyncio.gather()`:

```python
summary, multi_summaries, action_plan, email_client, email_internal = await asyncio.gather(
    chat_engine.generate_executive_summary(profile, calculation, strategies),
    summarizer.generate_all_summaries(report_data, profile.get("name")),
    narrator.generate_action_plan_narrative(action_items, client_profile),
    summarizer.generate_summary_for_email(report_data, "client"),
    summarizer.generate_summary_for_email(report_data, "internal"),
    return_exceptions=True,
)
# Handle any exceptions individually
```

**In `report_generator.py` (`_generate_executive_summary`):**

Replace the thread pool + 5-second timeout pattern with native async. Since `AdvisoryReportGenerator` is called from async endpoints, make `generate_report()` async and use `await` for AI calls.

If the generator must remain sync (called from non-async contexts), keep the thread pool but increase timeout to 8 seconds and add `asyncio.gather()` inside the async function being submitted.

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
Add `_generate_scenario_comparisons()` to `AdvisoryReportGenerator`. It selects applicable scenarios based on the taxpayer's profile:

| Scenario | Condition |
|----------|-----------|
| Roth Conversion | Has traditional IRA/401k balance or retirement income |
| Entity Structure | Self-employed with business income > $40k |
| Deduction Strategy | Itemized total is within 20% of standard deduction |
| AMT Exposure | High SALT, ISOs, or AMT-triggering deductions |
| Estate Planning | AGI > $500k or has significant assets |

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
| HSA contributions | No HSA data, has health insurance | "HSA contributions are triple-tax-advantaged" | "Up to $X deduction" |
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

### Output

AI-discovered strategies are appended to the `recommendations` section with a `source: "ai_reasoning"` tag. They appear in the action plan with appropriate confidence levels.

### Guardrails
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

1. Get reasonable salary range from `calculate_reasonable_salary()`
2. Generate 6-8 data points from IRS minimum to 100% of net income
3. For each point, call `calculate_scorp_savings()` to get net tax savings
4. Identify the optimal salary (max savings within reasonable range)

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
2. Clone the TaxReturn
3. Apply strategies one at a time, cumulatively
4. After each: run `calculate_complete_return()` and record marginal savings
5. Report both independent and marginal savings for each strategy

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
This requires N+1 calculator runs (where N = number of strategies applied). For a typical report with 5-8 applicable strategies, this adds ~50-100ms. Acceptable.

### Files Modified
- `src/advisory/report_generator.py` — new method `_model_strategy_interactions()`
- Update `generate_report()` to use interaction-modeled total instead of naive sum
- Update `ComprehensiveRecommendation` fields in `recommendation_engine.py` to include `marginal_savings`

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
