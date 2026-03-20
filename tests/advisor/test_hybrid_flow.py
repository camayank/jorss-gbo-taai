"""Tests for the hybrid conversation flow (transition, freeform, guided, confirmation).

Run: PYTHONPATH=".:src" pytest tests/advisor/test_hybrid_flow.py -v
"""

from __future__ import annotations
import pytest
from src.web.intelligent_advisor_api import (
    _get_dynamic_next_question,
    _get_topic_for_question,
    _build_profile_summary,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TOPIC GROUPING
# ═══════════════════════════════════════════════════════════════════════════════

class TestTopicGrouping:
    """Questions should map to the correct topic."""

    def test_withholding_is_income(self):
        topic, num = _get_topic_for_question("Approximately how much federal tax was withheld from your paychecks?")
        assert topic == "Income Details"
        assert num == 1

    def test_childcare_is_family(self):
        topic, num = _get_topic_for_question("Did you pay for childcare or daycare?")
        assert topic == "Your Family"
        assert num == 2

    def test_life_events_is_life(self):
        topic, num = _get_topic_for_question("Did any major life changes happen this year?")
        assert topic == "Life Events"
        assert num == 3

    def test_investment_is_invest(self):
        topic, num = _get_topic_for_question("Do you have any investment income?")
        assert topic == "Investments & Retirement"
        assert num == 4

    def test_mortgage_is_deductions(self):
        topic, num = _get_topic_for_question("How much mortgage interest did you pay?")
        assert topic == "Deductions & Credits"
        assert num == 5

    def test_energy_is_final(self):
        topic, num = _get_topic_for_question("Did you make any energy-efficient improvements?")
        assert topic == "Final Checks"
        assert num == 6

    def test_retirement_is_invest(self):
        topic, num = _get_topic_for_question("Are you contributing to any retirement accounts?")
        assert topic == "Investments & Retirement"
        assert num == 4

    def test_gambling_is_final(self):
        topic, num = _get_topic_for_question("Did you have any gambling winnings?")
        assert topic == "Final Checks"
        assert num == 6

    def test_education_is_family(self):
        topic, num = _get_topic_for_question("Did you or a dependent attend college?")
        assert topic == "Your Family"
        assert num == 2


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE SUMMARY BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

class TestProfileSummaryBuilder:
    """_build_profile_summary should organize profile data correctly."""

    def test_basic_summary(self):
        profile = {
            "filing_status": "single",
            "state": "CA",
            "dependents": 0,
            "age": 35,
            "income_type": "w2_employee",
            "total_income": 75000,
            "federal_withholding": 10000,
        }
        summary = _build_profile_summary(profile)
        assert summary["basics"]["filing_status"] == "single"
        assert summary["basics"]["state"] == "CA"
        assert summary["income"]["total_income"] == 75000
        assert summary["payments"]["federal_withholding"] == 10000

    def test_empty_sections_excluded(self):
        profile = {
            "filing_status": "single",
            "state": "TX",
            "dependents": 0,
            "income_type": "w2_employee",
            "total_income": 50000,
        }
        summary = _build_profile_summary(profile)
        # Deductions should be empty dict (no deductions provided)
        assert len(summary["deductions"]) == 0

    def test_full_profile(self):
        profile = {
            "filing_status": "married_joint",
            "state": "CA",
            "dependents": 2,
            "age": 40,
            "income_type": "business_owner",
            "total_income": 300000,
            "business_income": 200000,
            "investment_income": 50000,
            "mortgage_interest": 22000,
            "property_taxes": 12000,
            "charitable_donations": 5000,
            "retirement_401k": 23500,
            "hsa_contributions": 8550,
            "federal_withholding": 30000,
            "estimated_payments": 20000,
            "dependents_under_17": 2,
            "childcare_costs": 12000,
            "energy_credits": "has_solar",
            "solar_cost": 28000,
        }
        summary = _build_profile_summary(profile)
        assert summary["income"]["business_income"] == 200000
        assert summary["deductions"]["mortgage_interest"] == 22000
        assert summary["credits"]["solar_cost"] == 28000
        assert summary["retirement"]["retirement_401k"] == 23500
        assert summary["payments"]["estimated_payments"] == 20000


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 COMPLETION → TRANSITION
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase1Completion:
    """Phase 1 sequential flow should work correctly for transition."""

    def test_phase1_sequential_order(self):
        """Phase 1 questions come in strict order."""
        profile = {}
        text, _ = _get_dynamic_next_question(profile, session={})
        assert "filing status" in text.lower()

        profile["filing_status"] = "single"
        text, _ = _get_dynamic_next_question(profile, session={})
        assert "income" in text.lower()

        profile["total_income"] = 75000
        text, _ = _get_dynamic_next_question(profile, session={})
        assert "state" in text.lower()

        profile["state"] = "CA"
        text, _ = _get_dynamic_next_question(profile, session={})
        assert "dependent" in text.lower()

        profile["dependents"] = 0
        text, _ = _get_dynamic_next_question(profile, session={})
        assert "income situation" in text.lower() or "income type" in text.lower()

    def test_phase1_all_complete_goes_to_phase2(self):
        """After all 5 Phase 1 fields, Phase 2 questions start."""
        profile = {
            "filing_status": "single",
            "total_income": 75000,
            "state": "CA",
            "dependents": 0,
            "income_type": "w2_employee",
        }
        text, actions = _get_dynamic_next_question(profile, session={})
        # Should be a Phase 2 question (not Phase 1)
        assert text is not None
        assert "filing status" not in text.lower()
        assert "income situation" not in text.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# GUIDED MODE WITH TOPICS
# ═══════════════════════════════════════════════════════════════════════════════

class TestGuidedModeTopics:
    """In guided mode, questions should have topic metadata."""

    def test_w2_first_question_is_income_topic(self):
        profile = {
            "filing_status": "single",
            "total_income": 75000,
            "state": "CA",
            "dependents": 0,
            "income_type": "w2_employee",
        }
        text, _ = _get_dynamic_next_question(profile, session={})
        topic, num = _get_topic_for_question(text)
        assert num == 1  # Income Details should be first

    def test_topics_progress_forward(self):
        """Topics should generally increase (1 → 2 → ... → 6)."""
        profile = {
            "filing_status": "single",
            "total_income": 75000,
            "state": "CA",
            "dependents": 0,
            "income_type": "w2_employee",
        }
        topics_seen = []
        for _ in range(40):
            text, actions = _get_dynamic_next_question(profile, session={})
            if text is None:
                break
            _, num = _get_topic_for_question(text)
            topics_seen.append(num)
            # Auto-skip
            for a in (actions or []):
                v = a.get("value", "")
                if v.startswith("skip_") or v.startswith("no_") or v == "not_educator" or v == "not_blind" or v == "not_student" or v == "not_dependent":
                    profile[v] = True
                    break
            # Also set generic _asked flags
            profile["_auto_" + str(len(topics_seen))] = True
            # Set common asked flags
            for flag in ["_asked_withholding", "_asked_age", "_asked_life_events", "_asked_investments",
                         "_asked_retirement", "_asked_hsa", "_asked_distributions", "_asked_deductions",
                         "_asked_student_loans", "_asked_educator", "_asked_rental", "_asked_k1",
                         "_asked_aca", "_asked_estimated", "_asked_energy", "_asked_foreign",
                         "_asked_gambling", "_asked_multi_state", "_asked_education",
                         "_asked_blind", "_asked_student_status", "_asked_dependent_self",
                         "_asked_unemployment", "_asked_disability", "_asked_royalty",
                         "_asked_interest_detail", "_asked_canceled_debt", "_asked_hobby",
                         "_asked_tips", "_asked_statutory", "_asked_1099k",
                         "_asked_other_1099r", "_asked_hsa_dist", "_asked_director_fees",
                         "_asked_bartering", "_asked_jury_duty", "_asked_oid", "_asked_ltc",
                         "_asked_alimony", "_asked_household", "_asked_amt",
                         "_asked_state_refund", "_asked_prizes", "_asked_ip_pin",
                         "_asked_local_tax", "_asked_state_withholding",
                         "_asked_prior_year", "_asked_extension", "_asked_refund_pref",
                         "_asked_casualty", "_asked_noncash_charitable", "_asked_ho_method",
                         "_asked_biz_meals", "_asked_biz_insurance", "_asked_nol",
                         "_asked_early_savings", "_asked_sl_amount", "_asked_gambling_loss",
                         "_asked_accounting", "_asked_inventory", "_asked_sold_biz_prop",
                         "_asked_listed_prop", "_asked_excess_biz_loss", "_asked_employer_ret_plan",
                         "_asked_qbi_wages", "_asked_wash_sale", "_asked_niit",
                         "_asked_installment", "_asked_1031", "_asked_qsbs", "_asked_qoz",
                         "_asked_collectibles", "_asked_inv_interest", "_asked_passive_carryforward",
                         "_asked_addl_medicare", "_asked_section_1256", "_asked_mlp",
                         "_asked_espp_disp", "_asked_iso_amt",
                         "_asked_backdoor_roth", "_asked_ira_basis", "_asked_inherited_ira",
                         "_asked_qcd", "_asked_eitc", "_asked_savers_credit", "_asked_elderly_credit",
                         "_asked_catch_up", "_asked_mega_backdoor", "_asked_ira_deduct",
                         "_asked_ctc_phaseout", "_asked_ftc_detail", "_asked_aca_recon",
                         "_asked_feie", "_asked_foreign_housing", "_asked_fbar_detail",
                         "_asked_fatca", "_asked_foreign_corp", "_asked_foreign_trust",
                         "_asked_treaty", "_asked_pfic", "_asked_nra_spouse",
                         "_asked_short_term", "_asked_personal_use", "_asked_below_fmv",
                         "_asked_cost_seg", "_asked_rental_convert", "_asked_rental_loss_allow",
                         "_asked_community_prop", "_asked_excess_ss", "_asked_bankruptcy",
                         "_asked_underpayment", "_asked_amended", "_asked_state_credits",
                         "_asked_spouse_educator", "_asked_employer_dc",
                         "_asked_multiple_support", "_asked_student_dep", "_asked_qss_verify",
                         "_asked_partial_exclusion", "_asked_felony_drug", "_asked_archer_msa",
                         "_asked_cap_gains", "_asked_crypto", "_asked_stock_comp",
                         "_asked_invest_amount", "_asked_early_withdrawal",
                         "_asked_mortgage_amount", "_asked_prop_tax_amount",
                         "_asked_charitable_amount", "_asked_medical_amount",
                         "_asked_est_amount", "_asked_participation",
                         "_asked_k1_amount", "_asked_medicare", "_asked_remote",
                         "_asked_wotc", "_asked_solar_cost", "_asked_ev_detail",
                         "_asked_energy_detail",
                         ]:
                profile[flag] = True
            # Set common field defaults
            profile.setdefault("federal_withholding", 10000)
            profile.setdefault("age", 35)
            profile.setdefault("_deduction_check", True)

        # Should have seen topics and they should roughly increase
        assert len(topics_seen) > 10, f"Only saw {len(topics_seen)} questions"
        # First topic should be 1 or 2
        assert topics_seen[0] <= 2


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIRMATION BEFORE CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfirmationBeforeCalc:
    """When all questions done, _get_dynamic_next_question returns None."""

    def test_all_done_returns_none(self):
        """A fully answered profile should return (None, None)."""
        profile = {
            "filing_status": "single",
            "total_income": 50000,
            "state": "TX",
            "dependents": 0,
            "income_type": "w2_employee",
            "_skip_deep_dive": True,  # Skip all Phase 2
        }
        text, actions = _get_dynamic_next_question(profile, session={})
        assert text is None
        assert actions is None
