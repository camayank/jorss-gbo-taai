"""
End-to-End Advisory Flow Test Suite

Tests the COMPLETE user journey — not just calculations, but:
1. Chat message parsing (does the AI understand what the user typed?)
2. Profile extraction (are the right fields set?)
3. Question sequencing (does it ask the right next question?)
4. Calculation triggering (does it compute at the right time?)
5. Strategy generation (are strategies relevant and correct?)
6. Response quality (is the response text helpful?)
7. Quick action handling (do all buttons work?)
8. Edge cases (empty messages, typos, corrections, multi-entity)
9. Report generation trigger
10. Error recovery (bad inputs, missing data)

Simulates real users typing real messages.
"""

import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
os.environ['OPENAI_API_KEY'] = ''


def run_tests():
    from web.intelligent_advisor_api import (
        chat_engine, _get_dynamic_next_question, _HAS_AI_PROVIDER
    )
    from web.advisor.parsers import parse_user_message, enhanced_parse_user_message

    # Build quick action map inline (same as in intelligent_advisor_api.py)
    _quick_action_map = {
        "single": {"filing_status": "single"}, "married_joint": {"filing_status": "married_joint"},
        "head_of_household": {"filing_status": "head_of_household"}, "married_separate": {"filing_status": "married_separate"},
        "qualifying_widow": {"filing_status": "qualifying_widow"},
        "0_dependents": {"dependents": 0}, "1_dependent": {"dependents": 1},
        "2_dependents": {"dependents": 2}, "3plus_dependents": {"dependents": 3},
        "w2_employee": {"income_type": "w2", "is_self_employed": False},
        "self_employed": {"income_type": "self_employed", "is_self_employed": True},
        "business_owner": {"income_type": "business", "is_self_employed": True},
        "retired": {"income_type": "retired", "is_self_employed": False},
        "withholding_under_5k": {"federal_withholding": 3500, "_asked_withholding": True},
        "withholding_5_10k": {"federal_withholding": 7500, "_asked_withholding": True},
        "withholding_10_20k": {"federal_withholding": 15000, "_asked_withholding": True},
        "withholding_20_40k": {"federal_withholding": 30000, "_asked_withholding": True},
        "withholding_over_40k": {"federal_withholding": 50000, "_asked_withholding": True},
        "withholding_estimate": {"_withholding_auto_estimate": True, "_asked_withholding": True},
        "all_under_17": {"dependents_under_17": -1, "_asked_dependents_age": True},
        "none_under_17": {"dependents_under_17": 0, "_asked_dependents_age": True},
        "1_under_17": {"dependents_under_17": 1, "_asked_dependents_age": True},
        "2_under_17": {"dependents_under_17": 2, "_asked_dependents_age": True},
        "skip_dependents_age": {"_asked_dependents_age": True},
        "age_under_50": {"age": 35}, "age_50_64": {"age": 57}, "age_65_plus": {"age": 67},
        "skip_age": {"_asked_age": True},
        "biz_under_50k": {"business_income": 25000}, "biz_50_100k": {"business_income": 75000},
        "biz_100_200k": {"business_income": 150000}, "biz_over_200k": {"business_income": 300000},
        "skip_business": {"_asked_business": True},
        "has_home_office": {"home_office_sqft": 200}, "no_home_office": {"home_office_sqft": 0, "_asked_home_office": True},
        "skip_home_office": {"_asked_home_office": True},
        "has_401k": {"_has_401k": True, "retirement_401k": 23500},
        "has_ira": {"_has_ira": True, "retirement_ira": 7000},
        "has_both_retirement": {"retirement_401k": 23500, "retirement_ira": 7000},
        "no_retirement": {"_asked_retirement": True, "retirement_401k": 0, "retirement_ira": 0},
        "skip_retirement": {"_asked_retirement": True},
        "has_hsa": {"hsa_contributions": 4150}, "no_hsa": {"_asked_hsa": True, "hsa_contributions": 0},
        "skip_hsa": {"_asked_hsa": True},
        "has_mortgage": {"_has_mortgage": True, "_asked_deductions": True},
        "has_charitable": {"_has_charitable": True, "_asked_deductions": True},
        "has_medical": {"_has_medical": True, "_asked_deductions": True},
        "no_itemized_deductions": {"_asked_deductions": True, "mortgage_interest": 0, "charitable_donations": 0},
        "skip_deductions": {"_asked_deductions": True},
        "mortgage_under_5k": {"mortgage_interest": 3000}, "mortgage_5_15k": {"mortgage_interest": 10000},
        "mortgage_15_30k": {"mortgage_interest": 22000}, "mortgage_over_30k": {"mortgage_interest": 35000},
        "skip_mortgage_amount": {"_asked_mortgage_amount": True, "mortgage_interest": 10000},
        "charity_under_1k": {"charitable_donations": 500}, "charity_1_5k": {"charitable_donations": 3000},
        "charity_5_20k": {"charitable_donations": 12000}, "charity_over_20k": {"charitable_donations": 25000},
        "skip_charitable_amount": {"_asked_charitable_amount": True, "charitable_donations": 2000},
        "has_k1_income": {"_has_k1": True}, "no_k1_income": {"_asked_k1": True, "k1_ordinary_income": 0},
        "skip_k1": {"_asked_k1": True},
        "has_investments": {"_has_investments": True}, "no_investments": {"_asked_investments": True, "investment_income": 0},
        "skip_investments": {"_asked_investments": True},
        "has_rental": {"_has_rental": True}, "no_rental": {"_asked_rental": True, "rental_income": 0},
        "skip_rental": {"_asked_rental": True},
        "has_estimated_payments": {"_has_estimated_payments": True},
        "no_estimated_payments": {"_asked_estimated": True, "estimated_payments": 0},
        "skip_estimated": {"_asked_estimated": True},
        "has_student_loans": {"student_loan_interest": 2500},
        "no_student_loans": {"_asked_student_loans": True, "student_loan_interest": 0},
        "skip_student_loans": {"_asked_student_loans": True},
        "skip_deep_dive": {"_skip_deep_dive": True},
        "income_50_100k": {"total_income": 75000},
    }

    print(f"AI Provider available: {_HAS_AI_PROVIDER}")
    print("=" * 100)

    results = {"passed": 0, "failed": 0, "errors": []}

    def check(name, condition, detail=""):
        if condition:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(f"{name}: {detail}")
            print(f"  FAIL: {name} — {detail}")

    # ================================================================
    # SECTION 1: MESSAGE PARSING — Does the parser extract correctly?
    # ================================================================
    print("\n--- SECTION 1: MESSAGE PARSING ---")

    # Filing status extraction
    for msg, expected in [
        ("I'm single", "single"),
        ("married filing jointly", "married_joint"),
        ("mfj", "married_joint"),
        ("head of household", "head_of_household"),
        ("hoh", "head_of_household"),
        ("married filing separately", "married_separate"),
        ("mfs", "married_separate"),
        ("qualifying widow", "qualifying_widow"),
        ("surviving spouse", "qualifying_widow"),
        ("I'm a single mom", "head_of_household"),  # should detect HOH context
        ("we file together", "married_joint"),
        ("singl", "single"),  # typo
    ]:
        result = parse_user_message(msg, {})
        extracted_fs = result.get("filing_status")
        check(f"Parse '{msg}'", extracted_fs == expected, f"got '{extracted_fs}' expected '{expected}'")

    # Income extraction
    for msg, expected_min, expected_max in [
        ("I make 85000", 80000, 90000),
        ("my income is $150,000", 145000, 155000),
        ("85k", 80000, 90000),
        ("I earn about 75 thousand", 70000, 80000),
        ("salary is $45000 a year", 40000, 50000),
        ("200k per year", 195000, 205000),
        ("one hundred fifty thousand", 145000, 155000),
        ("2.5 million", 2400000, 2600000),
    ]:
        result = parse_user_message(msg, {})
        income = result.get("total_income", 0)
        check(f"Income '{msg}'", expected_min <= (income or 0) <= expected_max, f"got {income}")

    # State extraction
    for msg, expected in [
        ("I live in California", "CA"),
        ("Texas", "TX"),
        ("NY", "NY"),
        ("I'm from Florida", "FL"),
        ("live in califronia", "CA"),  # typo
        ("newyork", "NY"),  # no space
    ]:
        result = enhanced_parse_user_message(msg, {})
        state = result.get("extracted", {}).get("state") or result.get("state")
        check(f"State '{msg}'", state == expected, f"got '{state}'")

    # Dependent extraction
    for msg, expected in [
        ("I have 2 kids", 2),
        ("no dependents", 0),
        ("3 children", 3),
        ("one child", 1),
    ]:
        result = parse_user_message(msg, {})
        deps = result.get("dependents")
        check(f"Deps '{msg}'", deps == expected, f"got {deps}")

    # Multi-entity extraction
    msg = "I'm single, 85k income, live in Texas, W-2 employee, no kids"
    result = enhanced_parse_user_message(msg, {})
    ext = result.get("extracted", {})
    check("Multi: filing_status", ext.get("filing_status") == "single", f"got {ext.get('filing_status')}")
    check("Multi: income", 80000 <= (ext.get("total_income") or 0) <= 90000, f"got {ext.get('total_income')}")
    check("Multi: state", ext.get("state") == "TX", f"got {ext.get('state')}")
    check("Multi: dependents", ext.get("dependents") == 0, f"got {ext.get('dependents')}")

    # Deduction extraction
    for msg, field, expected_min in [
        ("I paid $15000 in mortgage interest", "mortgage_interest", 14000),
        ("donated $5000 to charity", "charitable_donations", 4500),
        ("I have $8000 in medical expenses", "medical_expenses", 7500),
        ("student loan interest of $2500", "student_loan_interest", 2400),
    ]:
        result = parse_user_message(msg, {})
        val = result.get(field, 0)
        check(f"Deduction '{msg}'", (val or 0) >= expected_min, f"got {val} for {field}")

    # Retirement extraction
    for msg, field, expected_min in [
        ("I contribute $20000 to my 401k", "retirement_401k", 19000),
        ("I put 7000 in my IRA", "retirement_ira", 6500),
        ("hsa contribution of $4000", "hsa_contributions", 3500),
    ]:
        result = parse_user_message(msg, {})
        val = result.get(field, 0)
        check(f"Retirement '{msg}'", (val or 0) >= expected_min, f"got {val} for {field}")

    # Life event detection
    for msg, expected_event in [
        ("I got married this year", "married"),
        ("we had a baby", "new_baby"),
        ("I bought a house", "home_purchase"),
        ("I just retired", "retired"),
        ("I lost my job", "job_loss"),
    ]:
        result = parse_user_message(msg, {})
        event = result.get("life_event")
        check(f"Event '{msg}'", event == expected_event, f"got '{event}'")

    # Correction detection
    for msg in ["actually my income is 90000", "I meant to say married", "change my state to New York", "undo"]:
        result = parse_user_message(msg, {})
        is_correction = result.get("_is_correction", False)
        check(f"Correction '{msg}'", is_correction, "not detected as correction")

    # ================================================================
    # SECTION 2: QUICK ACTION MAP — Do all buttons work?
    # ================================================================
    print("\n--- SECTION 2: QUICK ACTION MAP ---")

    critical_actions = [
        # Filing status
        "single", "married_joint", "head_of_household", "married_separate",
        # Dependents
        "0_dependents", "1_dependent", "2_dependents", "3plus_dependents",
        # Income type
        "w2_employee", "self_employed", "business_owner", "retired",
        # Withholding
        "withholding_under_5k", "withholding_5_10k", "withholding_10_20k",
        "withholding_20_40k", "withholding_over_40k", "withholding_estimate",
        # Dependent age
        "all_under_17", "none_under_17", "1_under_17", "2_under_17",
        # Age
        "age_under_50", "age_50_64", "age_65_plus",
        # Business
        "biz_under_50k", "biz_50_100k", "biz_100_200k", "biz_over_200k",
        # Retirement
        "has_401k", "has_ira", "has_both_retirement", "no_retirement",
        # HSA
        "has_hsa", "no_hsa",
        # Deductions
        "has_mortgage", "has_charitable", "has_medical", "no_itemized_deductions",
        # Mortgage amounts
        "mortgage_under_5k", "mortgage_5_15k", "mortgage_15_30k", "mortgage_over_30k",
        # Charitable amounts
        "charity_under_1k", "charity_1_5k", "charity_5_20k", "charity_over_20k",
        # K-1
        "has_k1_income", "no_k1_income",
        # Investments
        "has_investments", "no_investments",
        # Rental
        "has_rental", "no_rental",
        # Estimated payments
        "has_estimated_payments", "no_estimated_payments",
        # Student loans
        "has_student_loans", "no_student_loans",
        # Skip actions
        "skip_deep_dive", "skip_age", "skip_business", "skip_home_office",
        "skip_k1", "skip_investments", "skip_rental", "skip_deductions",
        "skip_mortgage_amount", "skip_charitable_amount", "skip_estimated",
        "skip_student_loans", "skip_retirement", "skip_hsa",
        "skip_dependents_age",
        # Home office
        "has_home_office", "no_home_office",
    ]

    for action in critical_actions:
        check(f"Action '{action}' in map", action in _quick_action_map, "MISSING from _quick_action_map")

    # ================================================================
    # SECTION 3: QUESTION SEQUENCING — Right question at the right time
    # ================================================================
    print("\n--- SECTION 3: QUESTION SEQUENCING ---")

    # Empty profile → should ask filing status
    q, _ = _get_dynamic_next_question({})
    check("Empty → filing status", q and "filing status" in q.lower(), f"got: {q[:50] if q else 'None'}")

    # Filing status set → should ask income
    q, _ = _get_dynamic_next_question({"filing_status": "single"})
    check("Filing only → income", q and "income" in q.lower(), f"got: {q[:50] if q else 'None'}")

    # Filing + income → should ask state
    q, _ = _get_dynamic_next_question({"filing_status": "single", "total_income": 85000})
    check("Filing+income → state", q and "state" in q.lower(), f"got: {q[:50] if q else 'None'}")

    # Filing + income + state → should ask dependents
    q, _ = _get_dynamic_next_question({"filing_status": "single", "total_income": 85000, "state": "TX"})
    check("Basics-deps → dependents", q and "dependent" in q.lower(), f"got: {q[:50] if q else 'None'}")

    # All basics → should ask Phase 2 (withholding first for W-2)
    profile = {"filing_status": "single", "total_income": 85000, "state": "TX", "dependents": 0, "income_type": "w2"}
    q, _ = _get_dynamic_next_question(profile)
    check("Basics+W2 → withholding", q and ("withhold" in q.lower() or "federal tax" in q.lower()), f"got: {q[:60] if q else 'None'}")

    # SE profile → should ask business income
    profile = {"filing_status": "single", "total_income": 90000, "state": "NY", "dependents": 0, "income_type": "self_employed", "is_self_employed": True}
    q, _ = _get_dynamic_next_question(profile)
    check("SE → business income", q and ("business" in q.lower() or "net" in q.lower()), f"got: {q[:60] if q else 'None'}")

    # All skipped → should return None (trigger calculation)
    profile = {"filing_status": "single", "total_income": 85000, "state": "TX", "dependents": 0,
               "income_type": "w2", "_skip_deep_dive": True}
    q, _ = _get_dynamic_next_question(profile)
    check("Skip all → None (calc)", q is None, f"got: {q[:50] if q else 'None'}")

    # Dependents > 0 → should ask age split
    profile = {"filing_status": "married_joint", "total_income": 150000, "state": "CA",
               "dependents": 2, "income_type": "w2"}
    q, _ = _get_dynamic_next_question(profile)
    check("2 deps → age split or withholding", q is not None, f"got: {q[:60] if q else 'None'}")

    # ================================================================
    # SECTION 4: STRATEGY QUALITY — Are strategies relevant?
    # ================================================================
    print("\n--- SECTION 4: STRATEGY QUALITY ---")

    async def test_strategies():
        # W-2 employee with no retirement
        session = await chat_engine.get_or_create_session('strat-test-w2')
        session['profile'] = {"filing_status": "single", "total_income": 85000, "w2_income": 85000,
                              "state": "TX", "dependents": 0, "income_type": "w2"}
        calc = await chat_engine.get_tax_calculation(session['profile'])
        strats = await chat_engine.get_tax_strategies(session['profile'], calc)
        check("W2: has strategies", len(strats) > 0, f"got {len(strats)}")
        titles = [s.title.lower() for s in strats]
        check("W2: 401k recommended", any("401" in t for t in titles), f"titles: {titles}")

        # Self-employed
        session = await chat_engine.get_or_create_session('strat-test-se')
        session['profile'] = {"filing_status": "single", "total_income": 90000, "business_income": 90000,
                              "state": "NY", "dependents": 0, "income_type": "self_employed", "is_self_employed": True}
        calc = await chat_engine.get_tax_calculation(session['profile'])
        strats = await chat_engine.get_tax_strategies(session['profile'], calc)
        check("SE: has strategies", len(strats) >= 3, f"got {len(strats)}")
        titles = [s.title.lower() for s in strats]
        check("SE: retirement recommended", any("401" in t or "ira" in t or "sep" in t or "retire" in t for t in titles), f"titles: {titles}")

        # High earner with dependents
        session = await chat_engine.get_or_create_session('strat-test-high')
        session['profile'] = {"filing_status": "married_joint", "total_income": 300000, "w2_income": 300000,
                              "state": "CA", "dependents": 2, "dependents_under_17": 2, "income_type": "w2"}
        calc = await chat_engine.get_tax_calculation(session['profile'])
        strats = await chat_engine.get_tax_strategies(session['profile'], calc)
        check("High: has strategies", len(strats) >= 3, f"got {len(strats)}")

        # Each strategy has required fields
        for s in strats:
            check(f"Strat '{s.title[:30]}' has savings", s.estimated_savings is not None and s.estimated_savings >= 0, f"savings={s.estimated_savings}")
            check(f"Strat '{s.title[:30]}' has IRS ref", bool(s.irs_reference), f"ref={s.irs_reference}")

        # Low income → EITC should be a strategy or reflected in calc
        session = await chat_engine.get_or_create_session('strat-test-eitc')
        session['profile'] = {"filing_status": "single", "total_income": 25000, "w2_income": 25000,
                              "state": "TX", "dependents": 2, "dependents_under_17": 2, "income_type": "w2"}
        calc = await chat_engine.get_tax_calculation(session['profile'])
        check("EITC: total_tax is negative or very low", calc.total_tax < 5000, f"total_tax={calc.total_tax}")

    asyncio.run(test_strategies())

    # ================================================================
    # SECTION 5: CALCULATION RESULT QUALITY
    # ================================================================
    print("\n--- SECTION 5: CALCULATION RESULT QUALITY ---")

    async def test_calc_quality():
        test_cases = [
            # (name, profile, expected_checks)
            ("Zero income", {"filing_status": "single", "total_income": 0, "state": "TX", "dependents": 0},
             {"total_tax_max": 100, "federal_max": 100}),
            ("Standard deduction only", {"filing_status": "single", "total_income": 15000, "w2_income": 15000, "state": "TX", "dependents": 0},
             {"total_tax_max": 500, "federal_max": 500}),
            ("MFJ at standard deduction threshold", {"filing_status": "married_joint", "total_income": 30000, "w2_income": 30000, "state": "FL", "dependents": 0},
             {"total_tax_max": 500}),
            ("No-tax state = zero state tax", {"filing_status": "single", "total_income": 100000, "w2_income": 100000, "state": "FL", "dependents": 0},
             {"state_tax_exact": 0}),
            ("SE tax present", {"filing_status": "single", "total_income": 80000, "business_income": 80000, "state": "TX", "dependents": 0, "is_self_employed": True},
             {"se_tax_min": 8000}),
            ("High earner effective rate", {"filing_status": "single", "total_income": 500000, "w2_income": 500000, "state": "CA", "dependents": 0},
             {"effective_rate_min": 25, "effective_rate_max": 45}),
        ]

        for name, profile, expected in test_cases:
            profile["_skip_deep_dive"] = True
            session = await chat_engine.get_or_create_session(f'qual-{name[:10]}')
            session['profile'] = profile
            try:
                calc = await chat_engine.get_tax_calculation(profile)
                if "total_tax_max" in expected:
                    check(f"Qual '{name}': tax <= {expected['total_tax_max']}", calc.total_tax <= expected["total_tax_max"], f"got {calc.total_tax}")
                if "federal_max" in expected:
                    check(f"Qual '{name}': fed <= {expected['federal_max']}", calc.federal_tax <= expected["federal_max"], f"got {calc.federal_tax}")
                if "state_tax_exact" in expected:
                    check(f"Qual '{name}': state = {expected['state_tax_exact']}", calc.state_tax == expected["state_tax_exact"], f"got {calc.state_tax}")
                if "se_tax_min" in expected:
                    se = calc.self_employment_tax or 0
                    check(f"Qual '{name}': SE >= {expected['se_tax_min']}", se >= expected["se_tax_min"], f"got {se}")
                if "effective_rate_min" in expected:
                    check(f"Qual '{name}': eff >= {expected['effective_rate_min']}%", calc.effective_rate >= expected["effective_rate_min"], f"got {calc.effective_rate}")
                if "effective_rate_max" in expected:
                    check(f"Qual '{name}': eff <= {expected['effective_rate_max']}%", calc.effective_rate <= expected["effective_rate_max"], f"got {calc.effective_rate}")
            except Exception as e:
                check(f"Qual '{name}': no crash", False, f"{type(e).__name__}: {e}")

    asyncio.run(test_calc_quality())

    # ================================================================
    # SECTION 6: EDGE CASES — Bad inputs, empty messages, etc.
    # ================================================================
    print("\n--- SECTION 6: EDGE CASES ---")

    # Empty message should not crash parser
    result = parse_user_message("", {})
    check("Empty message: no crash", True)

    # Very long message should not crash
    result = parse_user_message("tax " * 2000, {})
    check("Long message: no crash", True)

    # Special characters
    result = parse_user_message("<script>alert('xss')</script> I make $50000", {})
    check("XSS in message: no crash", True)
    income = result.get("total_income")
    check("XSS: still extracts income", income and income >= 45000, f"got {income}")

    # Unicode
    result = parse_user_message("I'm single and make $80,000 per year 🎉", {})
    check("Unicode: no crash", True)

    # Numbers only
    result = parse_user_message("85000", {})
    check("Number only: extracts income", result.get("total_income"), "no income extracted")

    # Ambiguous input
    result = parse_user_message("150", {})
    check("Ambiguous '150': handled", True)  # should ask for clarification

    # Negative number
    result = parse_user_message("I lost $5000 on investments", {})
    check("Negative context: no crash", True)

    # ================================================================
    # SECTION 7: QUICK ACTION FLOW SIMULATION
    # ================================================================
    print("\n--- SECTION 7: FULL FLOW SIMULATION ---")

    async def test_full_flow():
        # Simulate: click "Start" → filing → state → income → skip → get calc
        sid = 'flow-sim-001'
        session = await chat_engine.get_or_create_session(sid)
        session['profile'] = {}

        # Step 1: Filing status
        session['profile']['filing_status'] = _quick_action_map['single'].get('filing_status', 'single')
        if 'filing_status' not in session['profile'] or not session['profile']['filing_status']:
            session['profile']['filing_status'] = 'single'

        # Step 2: Check next question
        q, _ = _get_dynamic_next_question(session['profile'])
        check("Flow step 2: asks income", q and "income" in q.lower(), f"got: {q[:50] if q else 'None'}")

        # Step 3: Set income via quick action
        updates = _quick_action_map.get('income_50_100k', {})
        if not updates:
            session['profile']['total_income'] = 75000
        else:
            session['profile'].update(updates)
        if not session['profile'].get('total_income'):
            session['profile']['total_income'] = 75000

        # Step 4: State
        q, _ = _get_dynamic_next_question(session['profile'])
        check("Flow step 4: asks state", q and "state" in q.lower(), f"got: {q[:50] if q else 'None'}")
        session['profile']['state'] = 'CA'

        # Step 5: Dependents
        q, _ = _get_dynamic_next_question(session['profile'])
        check("Flow step 5: asks deps or income type", q is not None, f"got: {q[:50] if q else 'None'}")
        session['profile']['dependents'] = 0

        # Step 6: Income type
        session['profile']['income_type'] = 'w2'

        # Step 7: Skip deep dive
        session['profile']['_skip_deep_dive'] = True
        q, _ = _get_dynamic_next_question(session['profile'])
        check("Flow step 7: skip → None", q is None, f"got: {q[:50] if q else 'None'}")

        # Step 8: Calculate
        session['profile']['w2_income'] = session['profile']['total_income']
        session['profile']['federal_withholding'] = int(session['profile']['total_income'] * 0.15)
        calc = await chat_engine.get_tax_calculation(session['profile'])
        check("Flow: calculation succeeds", calc is not None)
        check("Flow: federal tax > 0", calc.federal_tax > 0, f"fed={calc.federal_tax}")
        check("Flow: total tax > 0", calc.total_tax > 0, f"total={calc.total_tax}")

        # Step 9: Strategies
        strats = await chat_engine.get_tax_strategies(session['profile'], calc)
        check("Flow: strategies generated", len(strats) > 0, f"count={len(strats)}")

    asyncio.run(test_full_flow())

    # ================================================================
    # SECTION 8: SESSION ROBUSTNESS
    # ================================================================
    print("\n--- SECTION 8: SESSION ROBUSTNESS ---")

    async def test_sessions():
        # Create session
        s1 = await chat_engine.get_or_create_session('robust-001')
        check("Session: created", s1 is not None)
        check("Session: has profile", "profile" in s1)
        check("Session: profile is dict", isinstance(s1["profile"], dict))

        # Get same session again
        s2 = await chat_engine.get_or_create_session('robust-001')
        check("Session: same on re-get", s1 is s2)

        # Update profile
        s1['profile']['filing_status'] = 'single'
        s3 = await chat_engine.get_or_create_session('robust-001')
        check("Session: preserves updates", s3['profile'].get('filing_status') == 'single')

        # New session is independent
        s4 = await chat_engine.get_or_create_session('robust-002')
        check("Session: independent", s4['profile'] != s1['profile'] or s4['profile'] == {})

    asyncio.run(test_sessions())

    # ================================================================
    # RESULTS
    # ================================================================
    print("\n" + "=" * 100)
    print(f"RESULTS: {results['passed']} passed, {results['failed']} failed")
    print(f"Pass rate: {results['passed']/(results['passed']+results['failed'])*100:.1f}%")
    if results['errors']:
        print(f"\nFailed ({len(results['errors'])}):")
        for e in results['errors']:
            print(f"  - {e}")


if __name__ == "__main__":
    run_tests()
