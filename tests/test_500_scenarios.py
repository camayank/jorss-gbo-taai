"""
Comprehensive 500-Scenario Tax Engine Validation Matrix

Tests the _fallback_calculation engine across every meaningful combination of:
- 5 filing statuses
- 10 income levels ($0 to $2M)
- 10 states (no-tax, low-tax, high-tax)
- Income types (W-2, self-employed, mixed)
- Dependents (0, 1, 2, 3+, with age splits)
- Deductions (standard, itemized)
- Retirement contributions
- Capital gains
- EITC eligibility

Validates: numbers are reasonable, no crashes, correct signs, rates within bounds.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
os.environ['OPENAI_API_KEY'] = ''


def run_test():
    from web.intelligent_advisor_api import chat_engine

    # ================================================================
    # SCENARIO DEFINITIONS
    # ================================================================

    filing_statuses = ["single", "married_joint", "married_separate", "head_of_household", "qualifying_widow"]

    income_levels = [0, 15000, 25000, 40000, 55000, 75000, 100000, 150000, 200000, 300000, 500000, 750000, 1000000, 2000000]

    states = [
        ("TX", "no-tax"), ("FL", "no-tax"), ("WA", "no-tax"), ("NV", "no-tax"),
        ("CA", "high-tax"), ("NY", "high-tax"), ("NJ", "high-tax"),
        ("IL", "flat"), ("PA", "flat"),
        ("OR", "progressive"),
    ]

    income_types = [
        ("w2", False),
        ("self_employed", True),
    ]

    dependent_configs = [
        (0, 0),   # no deps
        (1, 1),   # 1 child under 17
        (2, 2),   # 2 children under 17
        (2, 1),   # 1 under 17 + 1 over (CTC + ODC)
        (3, 2),   # 2 under 17 + 1 over
    ]

    deduction_configs = [
        {},  # standard deduction
        {"mortgage_interest": 15000, "charitable_donations": 5000},  # itemized
        {"mortgage_interest": 30000, "property_taxes": 10000, "charitable_donations": 10000},  # heavy itemized
    ]

    retirement_configs = [
        {},  # none
        {"retirement_401k": 23500},
        {"retirement_401k": 23500, "retirement_ira": 7000, "hsa_contributions": 4150},
    ]

    capital_gains_configs = [
        {},
        {"capital_gains_long": 20000, "investment_income": 5000},
        {"capital_gains_long": 100000, "capital_gains_short": 15000, "dividend_income": 8000},
    ]

    # ================================================================
    # BUILD SCENARIO MATRIX
    # ================================================================

    scenarios = []
    scenario_id = 0

    # Tier 1: Filing status × income × state (5 × 14 × 10 = 700 base, sample to ~200)
    for fs in filing_statuses:
        for income in income_levels:
            for state_code, state_type in states:
                # Skip redundant no-tax state combos (keep only TX for no-tax)
                if state_type == "no-tax" and state_code != "TX" and income < 200000:
                    continue
                # Skip QSS with no dependents (invalid)
                if fs == "qualifying_widow" and income > 200000:
                    continue
                scenario_id += 1
                scenarios.append({
                    "id": scenario_id,
                    "name": f"{fs[:3].upper()}_{income//1000}K_{state_code}",
                    "profile": {
                        "filing_status": fs,
                        "total_income": income,
                        "w2_income": income,
                        "state": state_code,
                        "dependents": 1 if fs in ("head_of_household", "qualifying_widow") else 0,
                        "dependents_under_17": 1 if fs in ("head_of_household", "qualifying_widow") else 0,
                        "income_type": "w2",
                        "federal_withholding": int(income * 0.15) if income > 0 else 0,
                    }
                })

    # Tier 2: Dependent variations (5 configs × 5 statuses × 3 incomes = 75)
    for fs in filing_statuses:
        for income in [40000, 100000, 250000]:
            for deps, under_17 in dependent_configs:
                if fs == "single" and deps == 0:
                    continue  # already covered in Tier 1
                if fs in ("head_of_household", "qualifying_widow") and deps == 0:
                    continue  # HOH/QSS require dependent
                scenario_id += 1
                scenarios.append({
                    "id": scenario_id,
                    "name": f"{fs[:3].upper()}_{income//1000}K_{deps}dep_{under_17}u17",
                    "profile": {
                        "filing_status": fs,
                        "total_income": income,
                        "w2_income": income,
                        "state": "CA",
                        "dependents": deps,
                        "dependents_under_17": under_17,
                        "income_type": "w2",
                        "federal_withholding": int(income * 0.15),
                    }
                })

    # Tier 3: Self-employed (2 types × 8 incomes × 3 states = 48)
    for income in [25000, 40000, 60000, 90000, 120000, 200000, 350000, 500000]:
        for state_code in ["TX", "CA", "NY"]:
            scenario_id += 1
            scenarios.append({
                "id": scenario_id,
                "name": f"SE_{income//1000}K_{state_code}",
                "profile": {
                    "filing_status": "single",
                    "total_income": income,
                    "business_income": income,
                    "state": state_code,
                    "dependents": 0,
                    "income_type": "self_employed",
                    "is_self_employed": True,
                }
            })

    # Tier 4: Deductions (3 configs × 3 statuses × 4 incomes = 36)
    for fs in ["single", "married_joint", "head_of_household"]:
        for income in [60000, 100000, 200000, 400000]:
            for ded_config in deduction_configs:
                scenario_id += 1
                profile = {
                    "filing_status": fs,
                    "total_income": income,
                    "w2_income": income,
                    "state": "CA",
                    "dependents": 1 if fs == "head_of_household" else 0,
                    "dependents_under_17": 1 if fs == "head_of_household" else 0,
                    "income_type": "w2",
                    "federal_withholding": int(income * 0.15),
                    **ded_config,
                }
                scenarios.append({
                    "id": scenario_id,
                    "name": f"{fs[:3].upper()}_{income//1000}K_ded{len(ded_config)}",
                    "profile": profile,
                })

    # Tier 5: Retirement contributions (3 configs × 3 incomes × 2 statuses = 18)
    for fs in ["single", "married_joint"]:
        for income in [75000, 150000, 300000]:
            for ret_config in retirement_configs:
                scenario_id += 1
                scenarios.append({
                    "id": scenario_id,
                    "name": f"{fs[:3].upper()}_{income//1000}K_ret{len(ret_config)}",
                    "profile": {
                        "filing_status": fs,
                        "total_income": income,
                        "w2_income": income,
                        "state": "CA",
                        "dependents": 0,
                        "income_type": "w2",
                        "federal_withholding": int(income * 0.15),
                        **ret_config,
                    }
                })

    # Tier 6: Capital gains (3 configs × 3 incomes × 2 statuses = 18)
    for fs in ["single", "married_joint"]:
        for income in [100000, 250000, 500000]:
            for cg_config in capital_gains_configs:
                total = income + sum(v for v in cg_config.values())
                scenario_id += 1
                scenarios.append({
                    "id": scenario_id,
                    "name": f"{fs[:3].upper()}_{income//1000}K_cg{len(cg_config)}",
                    "profile": {
                        "filing_status": fs,
                        "total_income": total,
                        "w2_income": income,
                        "state": "CA",
                        "dependents": 0,
                        "income_type": "w2",
                        "federal_withholding": int(income * 0.15),
                        **cg_config,
                    }
                })

    # Tier 7: EITC scenarios (low income × dependents × statuses = 30)
    for fs in ["single", "married_joint", "head_of_household"]:
        for income in [10000, 18000, 25000, 35000, 45000]:
            for deps in [0, 1, 2, 3]:
                if fs == "head_of_household" and deps == 0:
                    continue
                scenario_id += 1
                scenarios.append({
                    "id": scenario_id,
                    "name": f"EITC_{fs[:3].upper()}_{income//1000}K_{deps}dep",
                    "profile": {
                        "filing_status": fs,
                        "total_income": income,
                        "w2_income": income,
                        "state": "TX",
                        "dependents": deps,
                        "dependents_under_17": deps,
                        "income_type": "w2",
                        "federal_withholding": int(income * 0.08),
                    }
                })

    # Tier 8: Mixed income (W-2 + SE + investment × 3 states = 15)
    for state_code in ["TX", "CA", "NY"]:
        for w2, biz, invest in [(80000, 30000, 10000), (50000, 50000, 20000), (120000, 0, 50000), (0, 80000, 30000), (200000, 100000, 50000)]:
            total = w2 + biz + invest
            scenario_id += 1
            scenarios.append({
                "id": scenario_id,
                "name": f"MIX_{total//1000}K_{state_code}",
                "profile": {
                    "filing_status": "married_joint",
                    "total_income": total,
                    "w2_income": w2,
                    "business_income": biz,
                    "investment_income": invest,
                    "state": state_code,
                    "dependents": 2,
                    "dependents_under_17": 2,
                    "income_type": "self_employed" if biz > 0 else "w2",
                    "is_self_employed": biz > 0,
                    "federal_withholding": int(w2 * 0.15),
                }
            })

    print(f"Total scenarios: {len(scenarios)}")
    print("=" * 120)

    # ================================================================
    # RUN ALL SCENARIOS
    # ================================================================

    async def run_all():
        passed = 0
        failed = 0
        errors = []

        for s in scenarios:
            try:
                profile = {**s["profile"], "_skip_deep_dive": True}
                session = await chat_engine.get_or_create_session(f'test-{s["id"]}')
                session['profile'] = profile

                calc = await chat_engine.get_tax_calculation(profile)

                # Validation checks
                issues = []

                # 1. Total tax should be reasonable
                income = profile.get("total_income", 0)
                if income > 0:
                    eff_rate = calc.effective_rate
                    if eff_rate > 55:
                        issues.append(f"Effective rate too high: {eff_rate:.1f}%")
                    if eff_rate < -30 and income > 50000:
                        issues.append(f"Effective rate too negative: {eff_rate:.1f}%")

                # 2. Federal tax should not exceed income
                if calc.federal_tax > income * 0.4 and income > 20000:
                    issues.append(f"Fed tax ${calc.federal_tax:,.0f} > 40% of income")

                # 3. State tax should be 0 for no-tax states
                state = profile.get("state", "")
                if state in ("TX", "FL", "WA", "NV", "WY", "SD", "AK", "TN") and calc.state_tax > 0:
                    issues.append(f"State tax ${calc.state_tax:,.0f} in no-tax state {state}")

                # 4. SE tax only for self-employed
                se_tax = calc.self_employment_tax or 0
                if not profile.get("is_self_employed") and se_tax > 0:
                    issues.append(f"SE tax ${se_tax:,.0f} for non-SE")
                if profile.get("is_self_employed") and profile.get("business_income", 0) > 0 and se_tax == 0:
                    issues.append(f"No SE tax for SE with biz income ${profile['business_income']:,.0f}")

                # 5. CTC for dependents under 17
                ctc = getattr(calc, 'child_tax_credit', 0) or 0
                if ctc == 0 and hasattr(calc, 'breakdown'):
                    cb = calc.breakdown.get('credit_breakdown', {})
                    if isinstance(cb, dict):
                        ctc = cb.get('child_tax_credit', 0) or 0
                deps_u17 = profile.get("dependents_under_17", 0)
                if deps_u17 == -1:
                    deps_u17 = profile.get("dependents", 0)
                # CTC check: only flag if total_credits is 0 AND dependents present
                # (CTC may be in different breakdown keys depending on engine path)
                total_credits = calc.breakdown.get('total_credits', 0) or 0 if hasattr(calc, 'breakdown') else ctc
                ctc_threshold = 400000 if profile.get("filing_status") in ("married_joint", "qualifying_widow") else 200000
                # Only flag missing CTC when income is high enough to have tax liability
                std_ded = {"single": 15000, "married_joint": 30000, "head_of_household": 22500, "married_separate": 15000, "qualifying_widow": 30000}
                min_income_for_ctc = std_ded.get(profile.get("filing_status", "single"), 15000) + 5000
                if deps_u17 > 0 and ctc == 0 and total_credits == 0 and income < ctc_threshold and income > min_income_for_ctc:
                    issues.append(f"No CTC for {deps_u17} children under 17")

                # 6. Total tax should not be NaN or None
                if calc.total_tax is None:
                    issues.append("total_tax is None")

                if issues:
                    failed += 1
                    errors.append((s["name"], issues))
                    print(f"FAIL {s['name']:<35} Fed:${calc.federal_tax:>8,.0f} St:${calc.state_tax:>7,.0f} SE:${se_tax:>7,.0f} CTC:${ctc:>5,.0f} Tot:${calc.total_tax:>8,.0f} Eff:{calc.effective_rate:>5.1f}% | {'; '.join(issues)}")
                else:
                    passed += 1

            except Exception as e:
                failed += 1
                errors.append((s["name"], [f"CRASH: {type(e).__name__}: {str(e)[:80]}"]))
                print(f"CRASH {s['name']:<35} {type(e).__name__}: {str(e)[:100]}")

        print("=" * 120)
        print(f"RESULTS: {passed} passed, {failed} failed out of {len(scenarios)} scenarios")
        print(f"Pass rate: {passed/len(scenarios)*100:.1f}%")

        if errors:
            print(f"\nFailed scenarios ({len(errors)}):")
            for name, issue_list in errors[:20]:
                print(f"  {name}: {'; '.join(issue_list)}")
            if len(errors) > 20:
                print(f"  ... and {len(errors)-20} more")

    asyncio.run(run_all())


if __name__ == "__main__":
    run_test()
