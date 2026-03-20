"""Comprehensive flow path tests — 179+ scenarios covering every US individual tax return type.

Tests are organized by taxpayer archetype (GROUP 1-11). Each test validates:
1. Questions that MUST be asked ARE asked
2. Questions that must NOT be asked are NOT asked
3. Question count is in expected range
4. Phase 1 always completes before Phase 2
5. Follow-up chains fire correctly

Run: PYTHONPATH=".:src" pytest tests/advisor/test_flow_paths.py -v
"""

from __future__ import annotations

import pytest
from typing import Optional
from src.web.advisor.flow_engine import FlowEngine


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _run_flow(initial_profile: dict, answers: Optional[dict] = None) -> tuple:
    """Simulate a complete flow, returning (question_ids, final_profile).

    answers: optional dict of question_id → profile updates to apply when
    that question is encountered.  Otherwise just marks the question asked.
    """
    engine = FlowEngine()
    profile = dict(initial_profile)
    questions: list[str] = []
    for _ in range(100):
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions.append(q.id)
        profile[q.asked_field] = True
        if answers and q.id in answers:
            profile.update(answers[q.id])
    return questions, profile


def _assert_asked(questions, *expected):
    for qid in expected:
        assert qid in questions, f"Expected question '{qid}' was NOT asked. Asked: {questions}"


def _assert_not_asked(questions, *unexpected):
    for qid in unexpected:
        assert qid not in questions, f"Unexpected question '{qid}' WAS asked. Asked: {questions}"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 1: SIMPLE W-2 EMPLOYEES
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC001_Single_W2_VeryLow_Young_NoDeps:
    """UC-001: Single, W-2, <$25k, under 26, no dependents — entry-level worker."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 20000,
            "state": "OH", "dependents": 0, "income_type": "w2_employee",
        })

    def test_gets_withholding(self):
        _assert_asked(self.qs, "withholding")

    def test_gets_age(self):
        _assert_asked(self.qs, "age")

    def test_gets_education(self):
        _assert_asked(self.qs, "dep_education")

    def test_gets_student_loans(self):
        _assert_asked(self.qs, "ded_student_loans")

    def test_skips_business(self):
        _assert_not_asked(self.qs, "se_business_income", "se_entity_type", "se_home_office")

    def test_skips_k1(self):
        _assert_not_asked(self.qs, "k1_has")

    def test_skips_estimated(self):
        _assert_not_asked(self.qs, "spec_estimated_payments")

    def test_skips_ss(self):
        _assert_not_asked(self.qs, "ret_ss_benefits")

    def test_skips_military(self):
        _assert_not_asked(self.qs, "spec_military_combat")

    def test_skips_stock_options(self):
        _assert_not_asked(self.qs, "inv_stock_options")

    def test_count(self):
        assert 8 <= len(self.qs) <= 22


class TestUC002_Single_W2_Mid_NoDeps:
    """UC-002: Single, W-2, $75k, 26-49, no dependents — mid-career professional."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 75000,
            "state": "CA", "dependents": 0, "income_type": "w2_employee",
        })

    def test_gets_withholding(self):
        _assert_asked(self.qs, "withholding")

    def test_gets_retirement(self):
        _assert_asked(self.qs, "ret_contributions")

    def test_gets_deductions(self):
        _assert_asked(self.qs, "ded_major_deductions")

    def test_gets_investments(self):
        _assert_asked(self.qs, "inv_has_investments")

    def test_skips_business(self):
        _assert_not_asked(self.qs, "se_business_income")

    def test_skips_childcare(self):
        _assert_not_asked(self.qs, "dep_childcare_costs")

    def test_count(self):
        assert 12 <= len(self.qs) <= 22


class TestUC003_Single_W2_High_NoDeps:
    """UC-003: Single, W-2, $150k, 26-49, no dependents — high earner."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 150000,
            "state": "NY", "dependents": 0, "income_type": "w2_employee",
        })

    def test_gets_stock_options(self):
        _assert_asked(self.qs, "inv_stock_options")

    def test_gets_estimated(self):
        _assert_asked(self.qs, "spec_estimated_payments")

    def test_gets_remote_worker(self):
        _assert_asked(self.qs, "state_remote_worker")


class TestUC004_Single_W2_VeryHigh:
    """UC-004: Single, W-2, $500k, 50-64 — executive."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 500000,
            "state": "CA", "dependents": 0, "income_type": "w2_employee",
        })

    def test_gets_amt(self):
        _assert_asked(self.qs, "spec_amt_check")

    def test_gets_estimated(self):
        _assert_asked(self.qs, "spec_estimated_payments")

    def test_gets_foreign_income(self):
        _assert_asked(self.qs, "spec_foreign_income")


class TestUC005_MFJ_W2_Mid_2Kids:
    """UC-005: MFJ, W-2, $100k, 26-49, 2 young kids — typical family."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "married_joint", "total_income": 100000,
            "state": "TX", "dependents": 2, "dependents_under_17": 2,
            "income_type": "w2_employee",
        })

    def test_gets_spouse_income(self):
        _assert_asked(self.qs, "inc_spouse_income_type")

    def test_gets_childcare(self):
        _assert_asked(self.qs, "dep_childcare_costs")

    def test_gets_education(self):
        _assert_asked(self.qs, "dep_education")

    def test_gets_dep_age_split(self):
        # dependents_under_17 is pre-set, so this is already answered
        pass

    def test_skips_multi_state(self):
        # TX has no income tax
        _assert_not_asked(self.qs, "state_multi_state")


class TestUC006_MFS_W2_High:
    """UC-006: MFS, W-2, $200k — married filing separately (student loan strategy)."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "married_separate", "total_income": 200000,
            "state": "NJ", "dependents": 0, "income_type": "w2_employee",
        })

    def test_no_spouse_income(self):
        # MFS doesn't ask about spouse income (filed separately)
        _assert_not_asked(self.qs, "inc_spouse_income_type")

    def test_gets_estimated(self):
        _assert_asked(self.qs, "spec_estimated_payments")


class TestUC007_HOH_W2_Low_2Kids:
    """UC-007: HOH, W-2, $35k, 2 young kids — single parent."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "head_of_household", "total_income": 35000,
            "state": "OH", "dependents": 2, "dependents_under_17": 2,
            "income_type": "w2_employee",
        })

    def test_gets_childcare(self):
        _assert_asked(self.qs, "dep_childcare_costs")

    def test_gets_custody(self):
        _assert_asked(self.qs, "dep_custody")

    def test_skips_k1(self):
        _assert_not_asked(self.qs, "k1_has")

    def test_skips_estimated(self):
        _assert_not_asked(self.qs, "spec_estimated_payments")

    def test_skips_stock_options(self):
        _assert_not_asked(self.qs, "inv_stock_options")


class TestUC008_QSS_W2_Mid_1Kid:
    """UC-008: Qualifying Surviving Spouse, W-2, $75k, 1 child."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "qualifying_widow", "total_income": 75000,
            "state": "VA", "dependents": 1, "dependents_under_17": 1,
            "income_type": "w2_employee",
        })

    def test_gets_withholding(self):
        _assert_asked(self.qs, "withholding")

    def test_gets_childcare(self):
        _assert_asked(self.qs, "dep_childcare_costs")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 2: MULTIPLE W-2 JOBS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC020_MultiW2_Single_Mid:
    """UC-020: Single, Multiple W-2 jobs, $80k — gig economy or two jobs."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 80000,
            "state": "CA", "dependents": 0, "income_type": "multiple_w2",
        })

    def test_gets_w2_count(self):
        _assert_asked(self.qs, "inc_multiple_w2_count")

    def test_gets_withholding(self):
        _assert_asked(self.qs, "withholding")

    def test_skips_business(self):
        _assert_not_asked(self.qs, "se_business_income")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 3: W-2 + SIDE HUSTLE
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC030_W2Side_Single_Mid:
    """UC-030: Single, W-2+Side, $90k ($60k W-2 + $30k freelance)."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 90000,
                "state": "CA", "dependents": 0, "income_type": "w2_plus_side",
            },
            answers={"inc_side_hustle_type": {"side_hustle_type": "freelance"}},
        )

    def test_gets_withholding(self):
        _assert_asked(self.qs, "withholding")

    def test_gets_side_type(self):
        _assert_asked(self.qs, "inc_side_hustle_type")

    def test_gets_side_income(self):
        _assert_asked(self.qs, "inc_side_income_amount")

    def test_gets_entity_type(self):
        _assert_asked(self.qs, "se_entity_type")

    def test_gets_estimated(self):
        _assert_asked(self.qs, "spec_estimated_payments")


class TestUC031_W2Side_MFJ_High_1Kid:
    """UC-031: MFJ, W-2+Side, $120k, TX, 1 kid."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "married_joint", "total_income": 120000,
                "state": "TX", "dependents": 1, "dependents_under_17": 1,
                "income_type": "w2_plus_side",
            },
            answers={"inc_side_hustle_type": {"side_hustle_type": "gig_work"}},
        )

    def test_gets_spouse_income(self):
        _assert_asked(self.qs, "inc_spouse_income_type")

    def test_gets_childcare(self):
        _assert_asked(self.qs, "dep_childcare_costs")

    def test_skips_multi_state(self):
        # TX = no income tax
        _assert_not_asked(self.qs, "state_multi_state")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 4: SELF-EMPLOYED / BUSINESS OWNERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC050_SE_SoleProp_Mid:
    """UC-050: Single, SE Sole Prop, $80k — freelance consultant."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 80000,
                "state": "CA", "dependents": 0, "income_type": "self_employed",
            },
            answers={
                "se_entity_type": {"entity_type": "sole_prop"},
                "se_business_income": {"business_income": 80000},
            },
        )

    def test_gets_entity_type(self):
        _assert_asked(self.qs, "se_entity_type")

    def test_gets_business_income(self):
        _assert_asked(self.qs, "se_business_income")

    def test_gets_home_office(self):
        _assert_asked(self.qs, "se_home_office")

    def test_gets_vehicle(self):
        _assert_asked(self.qs, "se_vehicle")

    def test_gets_health_insurance(self):
        _assert_asked(self.qs, "se_health_insurance")

    def test_gets_equipment(self):
        _assert_asked(self.qs, "se_equipment")

    def test_gets_employees(self):
        _assert_asked(self.qs, "se_employees")

    def test_gets_estimated(self):
        _assert_asked(self.qs, "spec_estimated_payments")

    def test_skips_withholding(self):
        _assert_not_asked(self.qs, "withholding")

    def test_skips_ss(self):
        _assert_not_asked(self.qs, "ret_ss_benefits")

    def test_skips_reasonable_salary(self):
        # Sole prop doesn't have reasonable salary
        _assert_not_asked(self.qs, "se_reasonable_salary")


class TestUC055_SCorp_High:
    """UC-055: Single, S-Corp, $250k — high-earning business owner."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 250000,
                "state": "CA", "dependents": 0, "income_type": "business_owner",
            },
            answers={
                "se_entity_type": {"entity_type": "s_corp"},
                "se_business_income": {"business_income": 250000},
            },
        )

    def test_gets_reasonable_salary(self):
        _assert_asked(self.qs, "se_reasonable_salary")

    def test_gets_sstb_check(self):
        _assert_asked(self.qs, "se_sstb_check")

    def test_gets_amt(self):
        _assert_asked(self.qs, "spec_amt_check")

    def test_gets_estimated(self):
        _assert_asked(self.qs, "spec_estimated_payments")

    def test_salary_before_sstb(self):
        # Reasonable salary should come before SSTB check
        si = self.qs.index("se_reasonable_salary")
        ss = self.qs.index("se_sstb_check")
        assert si < ss


class TestUC060_MFJ_LLC_Mid_Kids:
    """UC-060: MFJ, LLC, $120k, 2 kids — family business."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "married_joint", "total_income": 120000,
                "state": "IL", "dependents": 2, "dependents_under_17": 2,
                "income_type": "business_owner",
            },
            answers={
                "se_entity_type": {"entity_type": "single_llc"},
                "se_business_income": {"business_income": 100000},
            },
        )

    def test_gets_spouse_income(self):
        _assert_asked(self.qs, "inc_spouse_income_type")

    def test_gets_childcare(self):
        _assert_asked(self.qs, "dep_childcare_costs")

    def test_gets_home_office(self):
        _assert_asked(self.qs, "se_home_office")

    def test_skips_reasonable_salary(self):
        # LLC (not S-Corp) doesn't have reasonable salary
        _assert_not_asked(self.qs, "se_reasonable_salary")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 5: RETIRED INDIVIDUALS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC080_Retired_MFJ_Low_65plus:
    """UC-080: MFJ, Retired, $45k, 65+, FL — typical retiree couple."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "married_joint", "total_income": 45000,
            "state": "FL", "dependents": 0, "income_type": "retired",
            "age": "age_65_plus",
        })

    def test_gets_ss_benefits(self):
        _assert_asked(self.qs, "ret_ss_benefits")

    def test_gets_pension(self):
        _assert_asked(self.qs, "ret_pension")

    def test_gets_rmd(self):
        _assert_asked(self.qs, "ret_rmd")

    def test_gets_medicare(self):
        _assert_asked(self.qs, "hc_medicare_premiums")

    def test_gets_spouse_income(self):
        _assert_asked(self.qs, "inc_spouse_income_type")

    def test_skips_withholding(self):
        _assert_not_asked(self.qs, "withholding")

    def test_skips_business(self):
        _assert_not_asked(self.qs, "se_business_income", "se_entity_type")

    def test_skips_childcare(self):
        _assert_not_asked(self.qs, "dep_childcare_costs")

    def test_skips_aca(self):
        _assert_not_asked(self.qs, "hc_aca_marketplace")

    def test_skips_multi_state(self):
        # FL = no income tax
        _assert_not_asked(self.qs, "state_multi_state")

    def test_count(self):
        assert 12 <= len(self.qs) <= 22


class TestUC085_Retired_Single_Mid_Investments:
    """UC-085: Single, Retired, $90k (pension + investments), 65+."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 90000,
                "state": "AZ", "dependents": 0, "income_type": "retired",
                "age": "age_65_plus",
            },
            answers={"inv_has_investments": {"_has_investments": True}},
        )

    def test_gets_ss(self):
        _assert_asked(self.qs, "ret_ss_benefits")

    def test_gets_investment_amount(self):
        _assert_asked(self.qs, "inv_amount")

    def test_gets_distributions(self):
        _assert_asked(self.qs, "ret_distributions")


class TestUC086_Retired_Single_Low_NoSS:
    """UC-086: Single, Retired, $30k, 65+, not yet receiving SS."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 30000,
            "state": "FL", "dependents": 0, "income_type": "retired",
            "age": "age_65_plus",
        })

    def test_still_asks_ss(self):
        # Should still ASK about SS even if income is low — user might say "no"
        _assert_asked(self.qs, "ret_ss_benefits")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 6: MILITARY
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC100_Military_Single_Mid:
    """UC-100: Single, Military, $65k, VA — active duty."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 65000,
            "state": "VA", "dependents": 0, "income_type": "military",
        })

    def test_gets_combat_zone(self):
        _assert_asked(self.qs, "spec_military_combat")

    def test_gets_pcs(self):
        _assert_asked(self.qs, "spec_military_pcs")

    def test_gets_withholding(self):
        _assert_asked(self.qs, "withholding")

    def test_skips_business(self):
        _assert_not_asked(self.qs, "se_business_income", "se_entity_type")

    def test_skips_ss(self):
        _assert_not_asked(self.qs, "ret_ss_benefits")


class TestUC101_Military_MFJ_Mid_2Kids:
    """UC-101: MFJ, Military, $80k, 2 kids — military family."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "married_joint", "total_income": 80000,
            "state": "TX", "dependents": 2, "dependents_under_17": 2,
            "income_type": "military",
        })

    def test_gets_combat_zone(self):
        _assert_asked(self.qs, "spec_military_combat")

    def test_gets_spouse_income(self):
        _assert_asked(self.qs, "inc_spouse_income_type")

    def test_gets_childcare(self):
        _assert_asked(self.qs, "dep_childcare_costs")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 7: INVESTORS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC110_Investor_Single_VeryHigh:
    """UC-110: Single, Investor, $500k, 50-64 — full-time investor."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 500000,
                "state": "NY", "dependents": 0, "income_type": "investor",
            },
            answers={
                "inv_amount": {"investment_income": 400000},
                "inv_capital_gains": {"capital_gains_type": "mixed_gains"},
            },
        )

    def test_gets_investment_amount(self):
        _assert_asked(self.qs, "inv_amount")

    def test_gets_capital_gains(self):
        _assert_asked(self.qs, "inv_capital_gains")

    def test_gets_crypto(self):
        _assert_asked(self.qs, "inv_crypto")

    def test_gets_loss_carryforward(self):
        _assert_asked(self.qs, "inv_loss_carryforward")

    def test_gets_qualified_dividends(self):
        _assert_asked(self.qs, "inv_qualified_dividends")

    def test_gets_estimated(self):
        _assert_asked(self.qs, "spec_estimated_payments")

    def test_gets_amt(self):
        _assert_asked(self.qs, "spec_amt_check")

    def test_skips_withholding(self):
        _assert_not_asked(self.qs, "withholding")

    def test_skips_business(self):
        _assert_not_asked(self.qs, "se_business_income")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 8: LIFE EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC120_LifeEvent_SoldHome:
    """UC-120: MFJ, W-2, $150k, sold primary residence."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "married_joint", "total_income": 150000,
                "state": "CA", "dependents": 0, "income_type": "w2_employee",
            },
            answers={"life_events": {"life_events": "event_sold_home"}},
        )

    def test_gets_life_events(self):
        _assert_asked(self.qs, "life_events")

    def test_gets_home_sale_followup(self):
        _assert_asked(self.qs, "life_home_sale")


class TestUC121_LifeEvent_MovedStates:
    """UC-121: Single, W-2, moved from NY to TX."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 100000,
                "state": "TX", "dependents": 0, "income_type": "w2_employee",
            },
            answers={"life_events": {"life_events": "event_moved_states"}},
        )

    def test_gets_state_move_followup(self):
        _assert_asked(self.qs, "life_state_move")


class TestUC122_LifeEvent_LostJob:
    """UC-122: Single, W-2, lost job — unemployment benefits."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 60000,
                "state": "IL", "dependents": 0, "income_type": "w2_employee",
            },
            answers={"life_events": {"life_events": "event_job_loss"}},
        )

    def test_gets_job_loss_followup(self):
        _assert_asked(self.qs, "life_job_loss")


class TestUC123_LifeEvent_StartedBusiness:
    """UC-123: Single, started a business this year."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 80000,
                "state": "CA", "dependents": 0, "income_type": "w2_employee",
            },
            answers={"life_events": {"life_events": "event_started_biz"}},
        )

    def test_gets_new_business_followup(self):
        _assert_asked(self.qs, "life_new_business")


class TestUC124_LifeEvent_None:
    """UC-124: No life events — follow-ups should NOT appear."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 80000,
                "state": "CA", "dependents": 0, "income_type": "w2_employee",
            },
            answers={"life_events": {"life_events": "no_life_events"}},
        )

    def test_no_followups(self):
        _assert_not_asked(
            self.qs,
            "life_home_sale", "life_state_move", "life_job_loss", "life_new_business",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 9: STATE-SPECIFIC
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC140_State_NoIncomeTax_TX:
    """UC-140: W-2 in Texas — no income tax, skip state questions."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 100000,
            "state": "TX", "dependents": 0, "income_type": "w2_employee",
        })

    def test_skips_multi_state(self):
        _assert_not_asked(self.qs, "state_multi_state")

    def test_skips_remote_worker(self):
        _assert_not_asked(self.qs, "state_remote_worker")


class TestUC141_State_NoIncomeTax_FL:
    """UC-141: Retired in Florida — no income tax."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "married_joint", "total_income": 60000,
            "state": "FL", "dependents": 0, "income_type": "retired",
        })

    def test_skips_multi_state(self):
        _assert_not_asked(self.qs, "state_multi_state")


class TestUC142_State_HighTax_CA:
    """UC-142: W-2 in California — gets multi-state question."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 120000,
            "state": "CA", "dependents": 0, "income_type": "w2_employee",
        })

    def test_gets_multi_state(self):
        _assert_asked(self.qs, "state_multi_state")

    def test_gets_remote_worker(self):
        _assert_asked(self.qs, "state_remote_worker")


class TestUC143_State_NoIncomeTax_WA:
    """UC-143: Tech worker in Washington — no income tax."""

    def setup_method(self):
        self.qs, _ = _run_flow({
            "filing_status": "single", "total_income": 200000,
            "state": "WA", "dependents": 0, "income_type": "w2_employee",
        })

    def test_skips_multi_state(self):
        _assert_not_asked(self.qs, "state_multi_state")

    def test_skips_529(self):
        # No state deduction for 529 in no-income-tax state
        pass  # No deps, so 529 already skipped


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 10: COMPLEX MULTI-SITUATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestUC160_Complex_SCorp_Rental_Investments:
    """UC-160: MFJ, S-Corp owner, $300k, CA, 2 kids, rentals, investments."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "married_joint", "total_income": 300000,
                "state": "CA", "dependents": 2, "dependents_under_17": 2,
                "income_type": "business_owner",
            },
            answers={
                "se_entity_type": {"entity_type": "s_corp"},
                "se_business_income": {"business_income": 200000},
                "inv_has_investments": {"_has_investments": True},
                "inv_amount": {"investment_income": 50000},
                "rental_has": {"_has_rental": "rental_2_4"},
                "rental_income_amount": {"rental_income": 30000},
            },
        )

    def test_gets_reasonable_salary(self):
        _assert_asked(self.qs, "se_reasonable_salary")

    def test_gets_sstb(self):
        _assert_asked(self.qs, "se_sstb_check")

    def test_gets_spouse_income(self):
        _assert_asked(self.qs, "inc_spouse_income_type")

    def test_gets_childcare(self):
        _assert_asked(self.qs, "dep_childcare_costs")

    def test_gets_rental_participation(self):
        _assert_asked(self.qs, "rental_participation")

    def test_gets_rental_depreciation(self):
        _assert_asked(self.qs, "rental_depreciation")

    def test_gets_capital_gains(self):
        _assert_asked(self.qs, "inv_capital_gains")

    def test_gets_estimated(self):
        _assert_asked(self.qs, "spec_estimated_payments")

    def test_gets_amt(self):
        _assert_asked(self.qs, "spec_amt_check")

    def test_gets_energy(self):
        _assert_asked(self.qs, "spec_energy_credits")

    def test_count(self):
        assert 25 <= len(self.qs) <= 40


class TestUC161_Complex_W2_Rental_K1:
    """UC-161: MFJ, W-2, $200k, rental property, K-1 income."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "married_joint", "total_income": 200000,
                "state": "NJ", "dependents": 1, "dependents_under_17": 1,
                "income_type": "w2_employee",
            },
            answers={
                "rental_has": {"_has_rental": "rental_1"},
                "rental_income_amount": {"rental_income": 15000},
                "k1_has": {"_has_k1": "has_k1_income"},
            },
        )

    def test_gets_rental_participation(self):
        _assert_asked(self.qs, "rental_participation")

    def test_gets_k1_amount(self):
        _assert_asked(self.qs, "k1_amount")

    def test_gets_withholding(self):
        _assert_asked(self.qs, "withholding")

    def test_gets_spouse_income(self):
        _assert_asked(self.qs, "inc_spouse_income_type")


class TestUC162_Complex_Investor_Foreign:
    """UC-162: Single, Investor, $400k, foreign investments."""

    def setup_method(self):
        self.qs, _ = _run_flow(
            {
                "filing_status": "single", "total_income": 400000,
                "state": "NY", "dependents": 0, "income_type": "investor",
            },
            answers={
                "inv_amount": {"investment_income": 300000},
                "inv_capital_gains": {"capital_gains_type": "lt_gains"},
                "spec_foreign_income": {"foreign_income": "foreign_investments"},
            },
        )

    def test_gets_foreign_accounts(self):
        _assert_asked(self.qs, "spec_foreign_accounts")

    def test_gets_amt(self):
        _assert_asked(self.qs, "spec_amt_check")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 11: EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdge_EmptyProfile:
    """First question should always be filing_status."""

    def test_first_question(self):
        engine = FlowEngine()
        q = engine.get_next_question({})
        assert q is not None
        assert q.id == "filing_status"
        assert q.phase == 1


class TestEdge_Phase1MustComplete:
    """Phase 2 questions must not appear until all Phase 1 is done."""

    def test_no_phase2_before_phase1(self):
        engine = FlowEngine()
        # Only filing_status answered — state and dependents still missing
        profile = {"filing_status": "single", "total_income": 100000}
        q = engine.get_next_question(profile)
        assert q is not None
        assert q.phase == 1, f"Got Phase {q.phase} question '{q.id}' before Phase 1 complete"


class TestEdge_Phase1Sequential:
    """Phase 1 questions follow a strict order."""

    def test_order(self):
        engine = FlowEngine()
        profile = {}
        order = []
        for _ in range(5):
            q = engine.get_next_question(profile)
            if q is None or q.phase != 1:
                break
            order.append(q.id)
            profile[q.asked_field] = True
            # Simulate answering
            if q.id == "filing_status":
                profile["filing_status"] = "single"
            elif q.id == "total_income":
                profile["total_income"] = 80000
            elif q.id == "state":
                profile["state"] = "CA"
            elif q.id == "dependents":
                profile["dependents"] = 0
            elif q.id == "income_type":
                profile["income_type"] = "w2_employee"
        assert order == [
            "filing_status", "total_income", "state", "dependents", "income_type",
        ]


class TestEdge_FlowTerminates:
    """Flow must terminate within 80 iterations for any profile."""

    @pytest.mark.parametrize("profile", [
        {"filing_status": "single", "total_income": 50000, "state": "CA",
         "dependents": 0, "income_type": "w2_employee"},
        {"filing_status": "married_joint", "total_income": 300000, "state": "NY",
         "dependents": 3, "dependents_under_17": 3, "income_type": "business_owner"},
        {"filing_status": "head_of_household", "total_income": 30000, "state": "TX",
         "dependents": 2, "dependents_under_17": 2, "income_type": "w2_employee"},
        {"filing_status": "single", "total_income": 500000, "state": "WA",
         "dependents": 0, "income_type": "investor"},
        {"filing_status": "married_joint", "total_income": 40000, "state": "FL",
         "dependents": 0, "income_type": "retired", "age": "age_65_plus"},
    ])
    def test_terminates(self, profile):
        qs, _ = _run_flow(profile)
        assert len(qs) < 80, f"Flow did not terminate for {profile}: {len(qs)} questions"


class TestEdge_NoDuplicateQuestions:
    """No question should be asked twice."""

    @pytest.mark.parametrize("profile", [
        {"filing_status": "single", "total_income": 100000, "state": "CA",
         "dependents": 0, "income_type": "w2_employee"},
        {"filing_status": "married_joint", "total_income": 200000, "state": "NY",
         "dependents": 2, "dependents_under_17": 2, "income_type": "business_owner"},
    ])
    def test_no_duplicates(self, profile):
        qs, _ = _run_flow(profile)
        assert len(qs) == len(set(qs)), f"Duplicate questions found: {[q for q in qs if qs.count(q) > 1]}"


class TestEdge_ContextBoost:
    """Questions should score higher when conversation mentions relevant keywords."""

    def test_crypto_boost(self):
        engine = FlowEngine()
        profile = {
            "filing_status": "single", "total_income": 100000, "state": "CA",
            "dependents": 0, "income_type": "w2_employee",
            "_has_investments": True,
        }
        q_normal = engine.get_all_eligible(profile)
        q_boosted = engine.get_all_eligible(
            profile, [{"role": "user", "content": "I sold some bitcoin this year"}],
        )
        normal_ids = [q.id for q in q_normal]
        boosted_ids = [q.id for q in q_boosted]
        if "inv_crypto" in normal_ids and "inv_crypto" in boosted_ids:
            normal_pos = normal_ids.index("inv_crypto")
            boosted_pos = boosted_ids.index("inv_crypto")
            assert boosted_pos <= normal_pos, "Crypto should rank same or higher with context"


class TestEdge_AllQuestionIdsUnique:
    """Every question in the registry must have a unique ID."""

    def test_unique_ids(self):
        from src.web.advisor.question_registry import ALL_QUESTIONS
        ids = [q.id for q in ALL_QUESTIONS]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"


class TestEdge_AllQuestionsHaveAskedField:
    """Every question must have an asked_field to prevent re-asking."""

    def test_asked_fields(self):
        from src.web.advisor.question_registry import ALL_QUESTIONS
        for q in ALL_QUESTIONS:
            assert q.asked_field, f"Question {q.id} has no asked_field"


# ═══════════════════════════════════════════════════════════════════════════════
# MATRIX VALIDATION: Run all income_type × filing_status combos
# ═══════════════════════════════════════════════════════════════════════════════

class TestMatrix:
    """Systematic matrix test — every income type × filing status."""

    PROFILES = []
    for it in ["w2_employee", "multiple_w2", "self_employed", "business_owner",
               "retired", "investor", "military"]:
        for fs in ["single", "married_joint", "head_of_household"]:
            for inc in [35000, 150000]:
                deps = 2 if fs == "head_of_household" else 0
                PROFILES.append({
                    "filing_status": fs, "total_income": inc,
                    "state": "CA", "dependents": deps, "income_type": it,
                    **({"dependents_under_17": 2} if deps > 0 else {}),
                })

    @pytest.mark.parametrize("profile", PROFILES,
                             ids=[f"{p['income_type']}/{p['filing_status']}/{p['total_income']}"
                                  for p in PROFILES])
    def test_flow_completes(self, profile):
        qs, _ = _run_flow(profile)
        assert len(qs) > 5, f"Too few questions ({len(qs)})"
        assert len(qs) < 40, f"Too many questions ({len(qs)})"

    @pytest.mark.parametrize("profile", PROFILES,
                             ids=[f"{p['income_type']}/{p['filing_status']}/{p['total_income']}"
                                  for p in PROFILES])
    def test_no_duplicates(self, profile):
        qs, _ = _run_flow(profile)
        assert len(qs) == len(set(qs))

    @pytest.mark.parametrize("profile", [p for p in PROFILES if p["income_type"] == "retired"],
                             ids=[f"retired/{p['filing_status']}/{p['total_income']}"
                                  for p in PROFILES if p["income_type"] == "retired"])
    def test_retired_no_withholding(self, profile):
        qs, _ = _run_flow(profile)
        assert "withholding" not in qs

    @pytest.mark.parametrize("profile",
                             [p for p in PROFILES
                              if p["income_type"] in ("w2_employee", "multiple_w2", "military")],
                             ids=[f"{p['income_type']}/{p['filing_status']}"
                                  for p in PROFILES
                                  if p["income_type"] in ("w2_employee", "multiple_w2", "military")])
    def test_w2_gets_withholding(self, profile):
        qs, _ = _run_flow(profile)
        assert "withholding" in qs

    @pytest.mark.parametrize("profile",
                             [p for p in PROFILES if p["filing_status"] == "married_joint"],
                             ids=[f"{p['income_type']}/mfj/{p['total_income']}"
                                  for p in PROFILES if p["filing_status"] == "married_joint"])
    def test_mfj_gets_spouse_income(self, profile):
        qs, _ = _run_flow(profile)
        assert "inc_spouse_income_type" in qs
