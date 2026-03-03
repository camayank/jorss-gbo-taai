"""Comprehensive tests for FilingStatusOptimizer.

Covers eligibility rules, marginal-rate lookup, recommendation generation,
confidence scoring, and edge cases across all five filing statuses.
"""

import os
import sys
from pathlib import Path
from decimal import Decimal

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from recommendation.filing_status_optimizer import (
    FilingStatus,
    FilingStatusAnalysis,
    FilingStatusRecommendation,
    FilingStatusOptimizer,
)
from models.taxpayer import TaxpayerInfo, Dependent
from models.taxpayer import FilingStatus as TaxpayerFilingStatus
from models.tax_return import TaxReturn
from models.deductions import Deductions
from models.credits import TaxCredits
from models.income_legacy import Income

# Import helpers from conftest (available via pytest discovery)
from tests.recommendation.conftest import make_tax_return, make_w2_income, _child, _make_income


# ============================================================================
# Section 1 -- FilingStatus enum
# ============================================================================


class TestFilingStatusEnum:
    """Tests for the FilingStatus enum defined in the optimizer module."""

    def test_enum_members_count(self):
        assert len(FilingStatus) == 5

    @pytest.mark.parametrize("member,value", [
        (FilingStatus.SINGLE, "single"),
        (FilingStatus.MARRIED_FILING_JOINTLY, "married_joint"),
        (FilingStatus.MARRIED_FILING_SEPARATELY, "married_separate"),
        (FilingStatus.HEAD_OF_HOUSEHOLD, "head_of_household"),
        (FilingStatus.QUALIFYING_WIDOW, "qualifying_widow"),
    ])
    def test_enum_values(self, member, value):
        assert member.value == value

    def test_enum_lookup_by_value(self):
        assert FilingStatus("single") is FilingStatus.SINGLE


# ============================================================================
# Section 2 -- FilingStatusAnalysis dataclass
# ============================================================================


class TestFilingStatusAnalysis:

    def test_create_with_defaults(self):
        a = FilingStatusAnalysis(
            filing_status="single",
            federal_tax=5000.0,
            state_tax=1000.0,
            total_tax=6000.0,
            effective_rate=12.0,
            marginal_rate=22.0,
            refund_or_owed=-500.0,
            is_eligible=True,
        )
        assert a.eligibility_reason == ""
        assert a.benefits == []
        assert a.drawbacks == []

    def test_create_ineligible_with_reason(self):
        a = FilingStatusAnalysis(
            filing_status="married_joint",
            federal_tax=0.0,
            state_tax=0.0,
            total_tax=0.0,
            effective_rate=0.0,
            marginal_rate=0.0,
            refund_or_owed=0.0,
            is_eligible=False,
            eligibility_reason="Must be married to file jointly",
        )
        assert not a.is_eligible
        assert "married" in a.eligibility_reason.lower()

    def test_benefits_and_drawbacks(self):
        a = FilingStatusAnalysis(
            filing_status="married_separate",
            federal_tax=8000,
            state_tax=2000,
            total_tax=10000,
            effective_rate=15,
            marginal_rate=24,
            refund_or_owed=0,
            is_eligible=True,
            benefits=["Separates liability"],
            drawbacks=["Narrower brackets"],
        )
        assert len(a.benefits) == 1
        assert len(a.drawbacks) == 1


# ============================================================================
# Section 3 -- FilingStatusRecommendation dataclass
# ============================================================================


class TestFilingStatusRecommendation:

    def test_create_recommendation(self):
        rec = FilingStatusRecommendation(
            recommended_status="single",
            current_status="single",
            potential_savings=0.0,
            analyses={},
            recommendation_reason="Current status is optimal.",
            confidence_score=95.0,
        )
        assert rec.warnings == []
        assert rec.additional_considerations == []

    def test_recommendation_with_savings(self):
        rec = FilingStatusRecommendation(
            recommended_status="head_of_household",
            current_status="single",
            potential_savings=2500.0,
            analyses={},
            recommendation_reason="HoH saves money.",
            confidence_score=88.0,
            warnings=["Verify dependent qualifies"],
        )
        assert rec.potential_savings == 2500.0
        assert len(rec.warnings) == 1


# ============================================================================
# Section 4 -- Eligibility rules (_get_eligible_statuses / _check_eligibility)
# ============================================================================


class TestEligibilityRules:
    """Test which filing statuses a taxpayer qualifies for."""

    def _optimizer(self):
        return FilingStatusOptimizer()

    # -- Single filer (unmarried, no dependents) --

    def test_single_no_deps_eligible_for_single_only(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        opt = self._optimizer()
        eligible = opt._get_eligible_statuses(tr)
        assert "single" in eligible
        assert "married_joint" not in eligible
        assert "head_of_household" not in eligible

    def test_single_cannot_file_mfj(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        opt = self._optimizer()
        ok, reason = opt._check_eligibility(tr, "married_joint")
        assert not ok
        assert "married" in reason.lower()

    def test_single_cannot_file_mfs(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        opt = self._optimizer()
        ok, reason = opt._check_eligibility(tr, "married_separate")
        assert not ok

    def test_single_no_dep_cannot_file_hoh(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        opt = self._optimizer()
        ok, reason = opt._check_eligibility(tr, "head_of_household")
        assert not ok
        assert "dependent" in reason.lower()

    # -- Single filer WITH dependents --

    def test_single_with_dep_eligible_for_hoh(self):
        tp = TaxpayerInfo(
            first_name="Test", last_name="User",
            filing_status=TaxpayerFilingStatus.SINGLE,
            dependents=[_child()],
        )
        tr = make_tax_return(taxpayer=tp, agi=50000)
        opt = self._optimizer()
        eligible = opt._get_eligible_statuses(tr)
        assert "head_of_household" in eligible

    # -- Married filer --

    def test_married_eligible_for_mfj_and_mfs(self, married_couple):
        married_couple.__dict__["is_married"] = True
        tr = make_tax_return(taxpayer=married_couple, agi=100000)
        opt = self._optimizer()
        eligible = opt._get_eligible_statuses(tr)
        assert "married_joint" in eligible
        assert "married_separate" in eligible
        assert "single" not in eligible

    def test_married_cannot_file_single(self, married_couple):
        married_couple.__dict__["is_married"] = True
        tr = make_tax_return(taxpayer=married_couple, agi=100000)
        opt = self._optimizer()
        ok, _ = opt._check_eligibility(tr, "single")
        assert not ok

    def test_married_cannot_file_hoh(self, married_couple):
        married_couple.__dict__["is_married"] = True
        tr = make_tax_return(taxpayer=married_couple, agi=100000)
        opt = self._optimizer()
        ok, _ = opt._check_eligibility(tr, "head_of_household")
        assert not ok

    # -- Head of Household --

    def test_hoh_eligible_single_with_dependent(self, hoh_parent):
        tr = make_tax_return(taxpayer=hoh_parent, agi=60000)
        opt = self._optimizer()
        ok, _ = opt._check_eligibility(tr, "head_of_household")
        assert ok

    # -- Qualifying Widow --

    def test_qualifying_widow_eligible(self, qualifying_widow_filer):
        tr = make_tax_return(taxpayer=qualifying_widow_filer, agi=70000)
        opt = self._optimizer()
        eligible = opt._get_eligible_statuses(tr)
        assert "qualifying_widow" in eligible

    def test_qualifying_widow_requires_dependent(self):
        tp = TaxpayerInfo(
            first_name="Grace", last_name="Kim",
            filing_status=TaxpayerFilingStatus.QUALIFYING_WIDOW,
        )
        tp.__dict__["spouse_died_year"] = 2024
        tr = make_tax_return(taxpayer=tp, agi=70000)
        opt = self._optimizer()
        ok, reason = opt._check_eligibility(tr, "qualifying_widow")
        assert not ok
        assert "dependent" in reason.lower()

    def test_qualifying_widow_requires_spouse_death(self):
        tp = TaxpayerInfo(
            first_name="Grace", last_name="Kim",
            filing_status=TaxpayerFilingStatus.QUALIFYING_WIDOW,
            dependents=[_child()],
        )
        tr = make_tax_return(taxpayer=tp, agi=70000)
        opt = self._optimizer()
        ok, reason = opt._check_eligibility(tr, "qualifying_widow")
        assert not ok

    # -- Unknown status --

    def test_unknown_status_ineligible(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        opt = self._optimizer()
        ok, reason = opt._check_eligibility(tr, "some_invalid_status")
        assert not ok
        assert "unknown" in reason.lower()


# ============================================================================
# Section 5 -- Marginal-rate lookup (_get_marginal_rate)
# ============================================================================


class TestMarginalRateLookup:
    """Verify bracket boundaries for each filing status."""

    opt = FilingStatusOptimizer()

    @pytest.mark.parametrize("status,agi,expected_pct", [
        # -- Single brackets --
        ("single", 5000, 10.0),
        ("single", 11925, 10.0),
        ("single", 11926, 12.0),
        ("single", 48475, 12.0),
        ("single", 48476, 22.0),
        ("single", 103350, 22.0),
        ("single", 103351, 24.0),
        ("single", 197300, 24.0),
        ("single", 197301, 32.0),
        ("single", 250525, 32.0),
        ("single", 250526, 35.0),
        ("single", 626350, 35.0),
        ("single", 626351, 37.0),
        # -- MFJ brackets --
        ("married_joint", 23850, 10.0),
        ("married_joint", 23851, 12.0),
        ("married_joint", 96950, 12.0),
        ("married_joint", 96951, 22.0),
        ("married_joint", 206700, 22.0),
        ("married_joint", 206701, 24.0),
        ("married_joint", 394600, 24.0),
        ("married_joint", 394601, 32.0),
        ("married_joint", 751600, 35.0),
        ("married_joint", 751601, 37.0),
        # -- MFS brackets --
        ("married_separate", 11925, 10.0),
        ("married_separate", 48476, 22.0),
        ("married_separate", 375800, 35.0),
        ("married_separate", 375801, 37.0),
        # -- HoH brackets --
        ("head_of_household", 17000, 10.0),
        ("head_of_household", 17001, 12.0),
        ("head_of_household", 64850, 12.0),
        ("head_of_household", 64851, 22.0),
        # -- Qualifying widow (same as MFJ) --
        ("qualifying_widow", 23850, 10.0),
        ("qualifying_widow", 23851, 12.0),
    ])
    def test_marginal_rate(self, status, agi, expected_pct):
        result = self.opt._get_marginal_rate(status, agi)
        assert result == expected_pct

    def test_unknown_status_falls_back_to_single(self):
        assert self.opt._get_marginal_rate("nonexistent", 50000) == 22.0

    def test_zero_agi(self):
        assert self.opt._get_marginal_rate("single", 0) == 10.0

    def test_very_high_agi(self):
        assert self.opt._get_marginal_rate("single", 10_000_000) == 37.0


# ============================================================================
# Section 6 -- Status benefits / drawbacks helpers
# ============================================================================


class TestBenefitsDrawbacks:

    opt = FilingStatusOptimizer()

    @pytest.mark.parametrize("status,expected_fragment", [
        ("married_joint", "wider tax brackets"),
        ("married_joint", "higher standard deduction"),
        ("head_of_household", "wider brackets"),
        ("head_of_household", "higher standard deduction"),
        ("qualifying_widow", "married filing jointly brackets"),
        ("single", "simple filing"),
        ("married_separate", "separates liability"),
    ])
    def test_status_benefits_contain(self, status, expected_fragment):
        mock_return = MagicMock()
        benefits = self.opt._get_status_benefits(status, mock_return)
        combined = " ".join(b.lower() for b in benefits)
        assert expected_fragment.lower() in combined

    @pytest.mark.parametrize("status,expected_fragment", [
        ("married_separate", "narrower tax brackets"),
        ("married_separate", "lower or no eitc"),
        ("single", "narrower brackets"),
    ])
    def test_status_drawbacks_contain(self, status, expected_fragment):
        mock_return = MagicMock()
        drawbacks = self.opt._get_status_drawbacks(status, mock_return)
        combined = " ".join(d.lower() for d in drawbacks)
        assert expected_fragment.lower() in combined

    def test_hoh_no_drawbacks(self):
        mock_return = MagicMock()
        drawbacks = self.opt._get_status_drawbacks("head_of_household", mock_return)
        assert drawbacks == []


# ============================================================================
# Section 7 -- Recommendation reason generation
# ============================================================================


class TestRecommendationReason:

    opt = FilingStatusOptimizer()

    def test_same_status_reason(self):
        reason = self.opt._generate_recommendation_reason(
            "single", "single", 0, {}
        )
        assert "optimal" in reason.lower()

    def test_savings_reason(self):
        reason = self.opt._generate_recommendation_reason(
            "head_of_household", "single", 1500.0, {}
        )
        assert "$1,500" in reason
        assert "save" in reason.lower()

    def test_no_savings_reason(self):
        reason = self.opt._generate_recommendation_reason(
            "married_joint", "single", 0, {}
        )
        assert "recommended" in reason.lower()


# ============================================================================
# Section 8 -- Confidence scoring
# ============================================================================


class TestConfidenceScoring:

    opt = FilingStatusOptimizer()

    def test_single_eligible_status_returns_100(self):
        analyses = {
            "single": FilingStatusAnalysis(
                filing_status="single", federal_tax=5000, state_tax=0,
                total_tax=5000, effective_rate=10, marginal_rate=22,
                refund_or_owed=0, is_eligible=True,
            )
        }
        assert self.opt._calculate_confidence("single", analyses) == 100.0

    def test_clear_winner_high_confidence(self):
        analyses = {
            "married_joint": FilingStatusAnalysis(
                filing_status="married_joint", federal_tax=8000, state_tax=0,
                total_tax=8000, effective_rate=8, marginal_rate=12,
                refund_or_owed=0, is_eligible=True,
            ),
            "married_separate": FilingStatusAnalysis(
                filing_status="married_separate", federal_tax=15000, state_tax=0,
                total_tax=15000, effective_rate=15, marginal_rate=24,
                refund_or_owed=0, is_eligible=True,
            ),
        }
        conf = self.opt._calculate_confidence("married_joint", analyses)
        assert conf >= 70

    def test_missing_recommended_returns_50(self):
        analyses = {
            "single": FilingStatusAnalysis(
                filing_status="single", federal_tax=5000, state_tax=0,
                total_tax=5000, effective_rate=10, marginal_rate=22,
                refund_or_owed=0, is_eligible=True,
            ),
            "head_of_household": FilingStatusAnalysis(
                filing_status="head_of_household", federal_tax=4500, state_tax=0,
                total_tax=4500, effective_rate=9, marginal_rate=22,
                refund_or_owed=0, is_eligible=True,
            ),
        }
        assert self.opt._calculate_confidence("married_joint", analyses) == 50.0


# ============================================================================
# Section 9 -- Warnings generation
# ============================================================================


class TestWarnings:

    opt = FilingStatusOptimizer()

    def test_mfs_warnings(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        warnings = self.opt._generate_warnings(tr, "married_separate", {})
        warning_text = " ".join(warnings).lower()
        assert "disqualify" in warning_text or "credit" in warning_text

    def test_status_change_warning(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        warnings = self.opt._generate_warnings(tr, "head_of_household", {})
        assert any("changing" in w.lower() or "affect" in w.lower() for w in warnings)

    def test_no_change_no_status_change_warning(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        warnings = self.opt._generate_warnings(tr, "single", {})
        assert not any("changing" in w.lower() for w in warnings)


# ============================================================================
# Section 10 -- Considerations generation
# ============================================================================


class TestConsiderations:

    opt = FilingStatusOptimizer()

    def test_always_includes_consult_professional(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        considerations = self.opt._generate_considerations(tr, "single")
        assert any("professional" in c.lower() for c in considerations)

    def test_self_employment_consideration(self):
        inc = _make_income(self_employment_income=50000)
        tr = make_tax_return(income=inc, agi=50000)
        considerations = self.opt._generate_considerations(tr, "single")
        assert any("self-employment" in c.lower() for c in considerations)

    def test_dependents_consideration(self):
        tp = TaxpayerInfo(
            first_name="T", last_name="U",
            filing_status=TaxpayerFilingStatus.SINGLE,
            dependents=[_child()],
        )
        tr = make_tax_return(taxpayer=tp, agi=50000)
        considerations = self.opt._generate_considerations(tr, "single")
        assert any("dependent" in c.lower() for c in considerations)

    def test_capital_gains_consideration(self):
        inc = _make_income(long_term_capital_gains=30000)
        tr = make_tax_return(income=inc, agi=80000)
        considerations = self.opt._generate_considerations(tr, "single")
        assert any("capital" in c.lower() for c in considerations)


# ============================================================================
# Section 11 -- _create_test_return
# ============================================================================


class TestCreateTestReturn:

    opt = FilingStatusOptimizer()

    @pytest.mark.parametrize("target_status_str,expected_enum", [
        ("single", TaxpayerFilingStatus.SINGLE),
        ("married_joint", TaxpayerFilingStatus.MARRIED_JOINT),
        ("married_separate", TaxpayerFilingStatus.MARRIED_SEPARATE),
        ("head_of_household", TaxpayerFilingStatus.HEAD_OF_HOUSEHOLD),
        ("qualifying_widow", TaxpayerFilingStatus.QUALIFYING_WIDOW),
    ])
    def test_status_mapped_correctly(self, target_status_str, expected_enum):
        tr = make_tax_return(agi=50000)
        result = self.opt._create_test_return(tr, target_status_str)
        assert result.taxpayer.filing_status == expected_enum

    def test_original_return_unchanged(self):
        tr = make_tax_return(agi=50000)
        original_status = tr.taxpayer.filing_status
        self.opt._create_test_return(tr, "married_joint")
        assert tr.taxpayer.filing_status == original_status


# ============================================================================
# Section 12 -- Full analyze() with mocked calculator
# ============================================================================


class TestAnalyzeWithMockedCalculator:
    """Test the full analyze() flow by mocking the TaxCalculator."""

    def _mock_calculator(self, tax_liability=5000, state_tax=500):
        calc = MagicMock()
        result = MagicMock()
        result.tax_liability = tax_liability
        result.state_tax_liability = state_tax
        result.adjusted_gross_income = 75000
        result.combined_refund_or_owed = -200
        result.refund_or_owed = -200
        calc.calculate_complete_return.return_value = result
        return calc

    def test_analyze_returns_recommendation(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=75000)
        calc = self._mock_calculator()
        opt = FilingStatusOptimizer(calculator=calc)
        rec = opt.analyze(tr)
        assert isinstance(rec, FilingStatusRecommendation)
        assert rec.current_status == "single"

    def test_analyze_single_filer_recommends_single(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=75000)
        calc = self._mock_calculator()
        opt = FilingStatusOptimizer(calculator=calc)
        rec = opt.analyze(tr)
        assert rec.recommended_status == "single"
        assert rec.potential_savings == 0.0

    def test_analyze_married_finds_lowest_tax(self, married_couple):
        married_couple.__dict__["is_married"] = True
        # Start from MFS so switching to MFJ shows savings
        married_couple.filing_status = TaxpayerFilingStatus.MARRIED_SEPARATE
        tr = make_tax_return(taxpayer=married_couple, agi=150000)

        # MFJ returns lower tax than MFS
        calc = MagicMock()
        call_count = [0]

        def mock_calc(test_return):
            call_count[0] += 1
            result = MagicMock()
            result.adjusted_gross_income = 150000
            result.combined_refund_or_owed = 0
            result.refund_or_owed = 0
            status = test_return.taxpayer.filing_status.value
            if status == "married_joint":
                result.tax_liability = 20000
                result.state_tax_liability = 3000
            else:
                result.tax_liability = 28000
                result.state_tax_liability = 4000
            return result

        calc.calculate_complete_return.side_effect = mock_calc
        opt = FilingStatusOptimizer(calculator=calc)
        rec = opt.analyze(tr)
        assert rec.recommended_status == "married_joint"
        assert rec.potential_savings > 0

    def test_analyze_includes_all_eligible_statuses(self, married_couple):
        married_couple.__dict__["is_married"] = True
        tr = make_tax_return(taxpayer=married_couple, agi=100000)
        calc = self._mock_calculator()
        opt = FilingStatusOptimizer(calculator=calc)
        rec = opt.analyze(tr)
        assert "married_joint" in rec.analyses
        assert "married_separate" in rec.analyses

    def test_analyze_sets_confidence_score(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=60000)
        calc = self._mock_calculator()
        opt = FilingStatusOptimizer(calculator=calc)
        rec = opt.analyze(tr)
        assert 0 <= rec.confidence_score <= 100

    def test_analyze_handles_calculator_exception(self, single_filer):
        """If calculator.calculate_complete_return raises, status is marked ineligible."""
        tr = make_tax_return(taxpayer=single_filer, agi=60000)
        calc = MagicMock()
        calc.calculate_complete_return.side_effect = Exception("calc error")
        opt = FilingStatusOptimizer(calculator=calc)
        rec = opt.analyze(tr)
        # Should still return a recommendation (fallback)
        assert isinstance(rec, FilingStatusRecommendation)

    def test_analyze_no_calculator_instantiates_one(self, single_filer):
        """When no calculator is passed, analyze() imports and creates one."""
        tr = make_tax_return(taxpayer=single_filer, agi=60000)
        with patch("calculator.tax_calculator.TaxCalculator") as MockCalc:
            instance = MagicMock()
            result = MagicMock()
            result.tax_liability = 5000
            result.state_tax_liability = 0
            result.adjusted_gross_income = 60000
            result.combined_refund_or_owed = 0
            result.refund_or_owed = 0
            instance.calculate_complete_return.return_value = result
            MockCalc.return_value = instance

            opt = FilingStatusOptimizer()
            rec = opt.analyze(tr)
            assert isinstance(rec, FilingStatusRecommendation)


# ============================================================================
# Section 13 -- Filing status x income level parametrized tests
# ============================================================================


_STATUS_INCOME_COMBOS = [
    (TaxpayerFilingStatus.SINGLE, agi)
    for agi in [25000, 60000, 100000, 200000, 500000]
] + [
    (TaxpayerFilingStatus.MARRIED_JOINT, agi)
    for agi in [25000, 60000, 100000, 200000, 500000]
] + [
    (TaxpayerFilingStatus.HEAD_OF_HOUSEHOLD, agi)
    for agi in [25000, 60000, 100000, 200000, 500000]
] + [
    (TaxpayerFilingStatus.MARRIED_SEPARATE, agi)
    for agi in [25000, 60000, 100000, 200000, 500000]
] + [
    (TaxpayerFilingStatus.QUALIFYING_WIDOW, agi)
    for agi in [25000, 60000, 100000, 200000, 500000]
]


@pytest.mark.parametrize("filing_status,agi", _STATUS_INCOME_COMBOS)
def test_analyze_status_returns_analysis_for_each_combo(filing_status, agi):
    """Ensure analyze() returns a valid recommendation for every status x income."""
    is_married = filing_status in (
        TaxpayerFilingStatus.MARRIED_JOINT,
        TaxpayerFilingStatus.MARRIED_SEPARATE,
    )
    needs_dep = filing_status in (
        TaxpayerFilingStatus.HEAD_OF_HOUSEHOLD,
        TaxpayerFilingStatus.QUALIFYING_WIDOW,
    )
    tp = TaxpayerInfo(
        first_name="Test", last_name="User",
        filing_status=filing_status,
        dependents=[_child()] if needs_dep else [],
    )
    if is_married:
        tp.spouse_first_name = "Spouse"
        tp.spouse_last_name = "User"
        tp.__dict__["is_married"] = True
    if filing_status == TaxpayerFilingStatus.QUALIFYING_WIDOW:
        tp.__dict__["spouse_died_year"] = 2024

    tr = make_tax_return(taxpayer=tp, agi=agi)
    calc = MagicMock()
    result = MagicMock()
    result.tax_liability = agi * 0.15
    result.state_tax_liability = agi * 0.03
    result.adjusted_gross_income = agi
    result.combined_refund_or_owed = 0
    result.refund_or_owed = 0
    calc.calculate_complete_return.return_value = result

    opt = FilingStatusOptimizer(calculator=calc)
    rec = opt.analyze(tr)
    assert isinstance(rec, FilingStatusRecommendation)
    assert rec.current_status == filing_status.value
    assert rec.confidence_score >= 0


# ============================================================================
# Section 14 -- MFJ vs MFS comparison scenarios
# ============================================================================


class TestMFJvsMFS:
    """MFJ vs MFS comparison for various income splits."""

    def _run_comparison(self, mfj_tax, mfs_tax):
        tp = TaxpayerInfo(
            first_name="A", last_name="B",
            filing_status=TaxpayerFilingStatus.MARRIED_SEPARATE,
            spouse_first_name="C", spouse_last_name="D",
        )
        tp.__dict__["is_married"] = True
        tr = make_tax_return(taxpayer=tp, agi=200000)

        calc = MagicMock()

        def calc_side(test_return):
            r = MagicMock()
            r.adjusted_gross_income = 200000
            r.combined_refund_or_owed = 0
            r.refund_or_owed = 0
            r.state_tax_liability = 0
            if test_return.taxpayer.filing_status == TaxpayerFilingStatus.MARRIED_JOINT:
                r.tax_liability = mfj_tax
            else:
                r.tax_liability = mfs_tax
            return r

        calc.calculate_complete_return.side_effect = calc_side
        opt = FilingStatusOptimizer(calculator=calc)
        return opt.analyze(tr)

    def test_mfj_preferred_when_lower(self):
        rec = self._run_comparison(mfj_tax=30000, mfs_tax=38000)
        assert rec.recommended_status == "married_joint"

    def test_mfs_preferred_when_lower(self):
        rec = self._run_comparison(mfj_tax=38000, mfs_tax=30000)
        assert rec.recommended_status == "married_separate"

    def test_equal_tax_picks_mfj_or_mfs(self):
        rec = self._run_comparison(mfj_tax=30000, mfs_tax=30000)
        assert rec.recommended_status in ("married_joint", "married_separate")

    @pytest.mark.parametrize("mfj_tax,mfs_tax,expected_savings", [
        (30000, 38000, 8000),
        (25000, 25000, 0),
    ])
    def test_savings_calculation(self, mfj_tax, mfs_tax, expected_savings):
        rec = self._run_comparison(mfj_tax, mfs_tax)
        assert rec.potential_savings == pytest.approx(expected_savings, abs=1)


# ============================================================================
# Section 15 -- Edge cases
# ============================================================================


class TestEdgeCases:

    def test_zero_income(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=0)
        calc = MagicMock()
        result = MagicMock()
        result.tax_liability = 0
        result.state_tax_liability = 0
        result.adjusted_gross_income = 0
        result.combined_refund_or_owed = 0
        result.refund_or_owed = 0
        calc.calculate_complete_return.return_value = result
        opt = FilingStatusOptimizer(calculator=calc)
        rec = opt.analyze(tr)
        assert isinstance(rec, FilingStatusRecommendation)

    def test_very_high_income(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=10_000_000)
        calc = MagicMock()
        result = MagicMock()
        result.tax_liability = 3_500_000
        result.state_tax_liability = 500_000
        result.adjusted_gross_income = 10_000_000
        result.combined_refund_or_owed = -100000
        result.refund_or_owed = -100000
        calc.calculate_complete_return.return_value = result
        opt = FilingStatusOptimizer(calculator=calc)
        rec = opt.analyze(tr)
        assert rec.confidence_score >= 0

    def test_recently_widowed_gets_qw_and_single(self, qualifying_widow_filer):
        tr = make_tax_return(taxpayer=qualifying_widow_filer, agi=80000)
        opt = FilingStatusOptimizer()
        eligible = opt._get_eligible_statuses(tr)
        assert "qualifying_widow" in eligible
        assert "single" in eligible

    def test_multiple_dependents_still_only_one_hoh(self):
        tp = TaxpayerInfo(
            first_name="T", last_name="U",
            filing_status=TaxpayerFilingStatus.SINGLE,
            dependents=[_child("A", 5), _child("B", 10), _child("C", 14)],
        )
        tr = make_tax_return(taxpayer=tp, agi=90000)
        opt = FilingStatusOptimizer()
        eligible = opt._get_eligible_statuses(tr)
        assert eligible.count("head_of_household") == 1

    def test_analyze_status_ineligible_returns_zeroes(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=50000)
        calc = MagicMock()
        opt = FilingStatusOptimizer(calculator=calc)
        analysis = opt._analyze_status(tr, "married_joint", calc)
        assert not analysis.is_eligible
        assert analysis.total_tax == 0.0
        assert analysis.federal_tax == 0.0
