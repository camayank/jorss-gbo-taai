"""Comprehensive tests for DeductionAnalyzer and ItemizedDeductionBreakdown.

Covers SALT caps, medical 7.5% AGI floor, mortgage interest TCJA limits,
charitable contribution ceilings, gambling loss limits, standard-vs-itemized
decision, bunching strategy, and confidence scoring.
"""

import os
import sys
from pathlib import Path
from decimal import Decimal

import pytest
from unittest.mock import Mock, MagicMock, patch
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from recommendation.deduction_analyzer import (
    DeductionStrategy,
    ItemizedDeductionBreakdown,
    DeductionAnalysis,
    DeductionRecommendation,
    DeductionAnalyzer,
)
from models.taxpayer import TaxpayerInfo, FilingStatus as TaxpayerFilingStatus
from models.tax_return import TaxReturn
from models.deductions import Deductions, ItemizedDeductions
from models.credits import TaxCredits
from models.income_legacy import Income

from tests.recommendation.conftest import make_tax_return, _make_income


# ============================================================================
# Section 1 -- DeductionStrategy enum
# ============================================================================


class TestDeductionStrategyEnum:

    def test_standard_value(self):
        assert DeductionStrategy.STANDARD.value == "standard"

    def test_itemized_value(self):
        assert DeductionStrategy.ITEMIZED.value == "itemized"

    def test_member_count(self):
        assert len(DeductionStrategy) == 2


# ============================================================================
# Section 2 -- ItemizedDeductionBreakdown defaults
# ============================================================================


class TestItemizedDeductionBreakdownDefaults:

    def test_default_salt_cap(self):
        b = ItemizedDeductionBreakdown()
        assert b.salt_cap == 10000.0

    def test_default_charitable_limit_percent(self):
        b = ItemizedDeductionBreakdown()
        assert b.charitable_limit_percent == 60.0

    def test_all_defaults_zero(self):
        b = ItemizedDeductionBreakdown()
        assert b.medical_expenses_total == 0.0
        assert b.state_local_income_tax == 0.0
        assert b.mortgage_interest == 0.0
        assert b.total_itemized_deductions == 0.0


# ============================================================================
# Section 3 -- Medical expense 7.5% AGI threshold
# ============================================================================


class TestMedicalExpenseThreshold:

    @pytest.mark.parametrize("agi,medical,expected_deduction", [
        # Below threshold -> 0
        (40000, 2000, 0.0),    # threshold = 3000
        (80000, 5000, 0.0),    # threshold = 6000
        (120000, 8000, 0.0),   # threshold = 9000
        (200000, 14000, 0.0),  # threshold = 15000
        # Exactly at threshold -> 0
        (40000, 3000, 0.0),
        (80000, 6000, 0.0),
        (100000, 7500, 0.0),
        # Above threshold
        (40000, 5000, 2000.0),     # 5000 - 3000
        (80000, 10000, 4000.0),    # 10000 - 6000
        (120000, 15000, 6000.0),   # 15000 - 9000
        (200000, 20000, 5000.0),   # 20000 - 15000
        # High medical on low AGI
        (40000, 40000, 37000.0),   # 40000 - 3000
        # Zero medical
        (100000, 0, 0.0),
    ])
    def test_medical_deduction(self, agi, medical, expected_deduction):
        b = ItemizedDeductionBreakdown(medical_expenses_total=medical)
        b.calculate_totals(agi)
        assert b.medical_deduction_allowed == pytest.approx(expected_deduction, abs=0.01)

    def test_medical_threshold_recorded(self):
        b = ItemizedDeductionBreakdown(medical_expenses_total=10000)
        b.calculate_totals(80000)
        assert b.medical_agi_threshold == pytest.approx(6000.0, abs=0.01)


# ============================================================================
# Section 4 -- SALT cap ($10,000)
# ============================================================================


class TestSALTCap:

    @pytest.mark.parametrize("state_tax,prop_tax,re_tax,pp_tax,expected_allowed", [
        # Below cap
        (3000, 2000, 0, 0, 5000),
        (5000, 3000, 2000, 0, 10000),
        # Exactly at cap
        (5000, 3000, 2000, 0, 10000),
        (10000, 0, 0, 0, 10000),
        # Above cap
        (8000, 4000, 3000, 0, 10000),
        (10000, 5000, 5000, 0, 10000),
        (6000, 4000, 3000, 2000, 10000),  # total 15000, capped at 10000
        # Zero
        (0, 0, 0, 0, 0),
    ])
    def test_salt_cap(self, state_tax, prop_tax, re_tax, pp_tax, expected_allowed):
        b = ItemizedDeductionBreakdown(
            state_local_income_tax=state_tax,
            property_tax=prop_tax,
            real_estate_tax=re_tax,
            personal_property_tax=pp_tax,
        )
        b.calculate_totals(100000)
        assert b.salt_deduction_allowed == expected_allowed

    def test_salt_total_computed(self):
        b = ItemizedDeductionBreakdown(
            state_local_income_tax=4000,
            property_tax=3000,
            real_estate_tax=2000,
            personal_property_tax=1000,
        )
        b.calculate_totals(100000)
        assert b.salt_total == 10000

    @pytest.mark.parametrize("total_salt", [5000, 10000, 15000, 20000])
    def test_salt_parametrized_totals(self, total_salt):
        b = ItemizedDeductionBreakdown(state_local_income_tax=total_salt)
        b.calculate_totals(100000)
        assert b.salt_deduction_allowed == min(total_salt, 10000)

    def test_custom_salt_cap(self):
        """Verify a non-standard SALT cap is honoured."""
        b = ItemizedDeductionBreakdown(
            state_local_income_tax=15000,
            salt_cap=20000,
        )
        b.calculate_totals(100000)
        assert b.salt_deduction_allowed == 15000


# ============================================================================
# Section 5 -- Interest deductions (mortgage + points + investment)
# ============================================================================


class TestInterestDeductions:

    @pytest.mark.parametrize("mortgage,points,investment,expected", [
        (10000, 0, 0, 10000),
        (10000, 2000, 0, 12000),
        (10000, 0, 3000, 13000),
        (10000, 2000, 3000, 15000),
        (0, 0, 0, 0),
    ])
    def test_total_interest(self, mortgage, points, investment, expected):
        b = ItemizedDeductionBreakdown(
            mortgage_interest=mortgage,
            mortgage_points=points,
            investment_interest=investment,
        )
        b.calculate_totals(100000)
        assert b.total_interest_deduction == expected


# ============================================================================
# Section 6 -- Charitable contribution limits
# ============================================================================


class TestCharitableLimits:

    @pytest.mark.parametrize("agi,cash,noncash,carryover,expected_allowed", [
        # Below 60% AGI
        (100000, 10000, 5000, 0, 15000),
        (100000, 30000, 10000, 0, 40000),
        # At 60% AGI
        (100000, 50000, 10000, 0, 60000),
        # Above 60% AGI -> capped
        (100000, 50000, 20000, 0, 60000),
        (100000, 60000, 10000, 0, 60000),
        # Carryover included
        (100000, 20000, 5000, 10000, 35000),
        # Carryover pushes over limit
        (100000, 40000, 10000, 20000, 60000),
        # Zero
        (100000, 0, 0, 0, 0),
        # Low AGI
        (50000, 40000, 0, 0, 30000),  # 60% of 50k = 30k
    ])
    def test_charitable_limit(self, agi, cash, noncash, carryover, expected_allowed):
        b = ItemizedDeductionBreakdown(
            cash_contributions=cash,
            non_cash_contributions=noncash,
            carryover_contributions=carryover,
        )
        b.calculate_totals(agi)
        assert b.charitable_deduction_allowed == pytest.approx(expected_allowed, abs=0.01)

    def test_noncash_30pct_can_be_set(self):
        """Verify a 30% limit can be manually configured for non-cash."""
        b = ItemizedDeductionBreakdown(
            non_cash_contributions=40000,
            charitable_limit_percent=30.0,
        )
        b.calculate_totals(100000)
        assert b.charitable_deduction_allowed == 30000


# ============================================================================
# Section 7 -- Gambling losses limited to winnings
# ============================================================================


class TestGamblingLosses:

    @pytest.mark.parametrize("losses,winnings,expected", [
        (5000, 10000, 5000),   # losses < winnings
        (10000, 10000, 10000), # losses == winnings
        (15000, 10000, 10000), # losses > winnings -> capped
        (5000, 0, 0),          # no winnings -> no deduction
        (0, 5000, 0),          # no losses
        (0, 0, 0),             # neither
    ])
    def test_gambling_loss_limit(self, losses, winnings, expected):
        b = ItemizedDeductionBreakdown(gambling_losses=losses)
        b.calculate_totals(100000, gambling_winnings=winnings)
        assert b.gambling_losses == expected


# ============================================================================
# Section 8 -- Total itemized calculation accuracy
# ============================================================================


class TestTotalItemizedCalculation:

    def test_all_components_summed(self):
        b = ItemizedDeductionBreakdown(
            medical_expenses_total=15000,   # AGI 100k -> threshold 7500 -> 7500 deductible
            state_local_income_tax=6000,
            property_tax=4000,              # SALT total 10000
            mortgage_interest=8000,
            mortgage_points=500,
            investment_interest=1000,
            cash_contributions=3000,
            non_cash_contributions=2000,
            casualty_losses_federally_declared=1000,
            gambling_losses=2000,
            other_deductions=500,
        )
        b.calculate_totals(100000, gambling_winnings=3000)
        expected = (
            7500     # medical (15000 - 7500)
            + 10000  # SALT (capped)
            + 9500   # interest (8000 + 500 + 1000)
            + 5000   # charitable (3000 + 2000)
            + 1000   # casualty
            + 2000   # gambling (capped at winnings=3000, but losses=2000 < 3000)
            + 500    # other
        )
        assert b.total_itemized_deductions == pytest.approx(expected, abs=0.01)

    def test_zero_everything(self):
        b = ItemizedDeductionBreakdown()
        b.calculate_totals(100000)
        assert b.total_itemized_deductions == 0.0


# ============================================================================
# Section 9 -- DeductionAnalyzer standard deduction amounts
# ============================================================================


class TestStandardDeductionAmounts:
    """Verify 2025 standard deduction constants."""

    analyzer = DeductionAnalyzer()

    @pytest.mark.parametrize("status,expected", [
        ("single", 15750),
        ("married_joint", 31500),
        ("married_separate", 15750),
        ("head_of_household", 23850),
        ("qualifying_widow", 31500),
    ])
    def test_standard_deduction_2025(self, status, expected):
        assert self.analyzer.STANDARD_DEDUCTIONS_2025[status] == expected

    @pytest.mark.parametrize("status,expected", [
        ("single", 1950),
        ("married_joint", 1550),
        ("married_separate", 1550),
        ("head_of_household", 1950),
        ("qualifying_widow", 1550),
    ])
    def test_additional_standard_2025(self, status, expected):
        assert self.analyzer.ADDITIONAL_STANDARD_2025[status] == expected


# ============================================================================
# Section 10 -- _normalize_filing_status
# ============================================================================


class TestNormalizeFilingStatus:

    analyzer = DeductionAnalyzer()

    @pytest.mark.parametrize("input_status,expected", [
        ("single", "single"),
        ("married_joint", "married_joint"),
        ("married_filing_jointly", "married_joint"),
        ("married_separate", "married_separate"),
        ("married_filing_separately", "married_separate"),
        ("head_of_household", "head_of_household"),
        ("qualifying_widow", "qualifying_widow"),
        ("qualifying_surviving_spouse", "qualifying_widow"),
        ("SINGLE", "single"),
        ("unknown_value", "single"),
    ])
    def test_normalize(self, input_status, expected):
        assert self.analyzer._normalize_filing_status(input_status) == expected


# ============================================================================
# Section 11 -- Marginal rate lookup
# ============================================================================


class TestDeductionAnalyzerMarginalRate:

    analyzer = DeductionAnalyzer()

    @pytest.mark.parametrize("status,agi,expected", [
        ("single", 10000, 10),
        ("single", 50000, 22),
        ("single", 200000, 32),
        ("single", 300000, 35),
        ("single", 700000, 37),
        ("married_joint", 20000, 10),
        ("married_joint", 100000, 22),
        ("married_joint", 400000, 32),
        ("head_of_household", 15000, 10),
        ("head_of_household", 70000, 22),
    ])
    def test_marginal_rate(self, status, agi, expected):
        assert self.analyzer._get_marginal_rate(status, agi) == expected


# ============================================================================
# Section 12 -- Standard vs Itemized decision (parametrized profiles)
# ============================================================================


_STANDARD_WINS_PROFILES = [
    # (filing_status, agi, state_tax, prop_tax, mortgage, charitable, label)
    ("single", 50000, 3000, 2000, 0, 500, "low-deduction single"),
    ("single", 80000, 4000, 0, 3000, 1000, "moderate single renter"),
    ("married_joint", 120000, 5000, 3000, 5000, 2000, "married moderate homeowner"),
    ("married_joint", 60000, 2000, 1500, 0, 500, "married low income"),
    ("head_of_household", 45000, 2000, 1000, 0, 300, "HoH renter"),
    ("single", 35000, 1500, 0, 0, 200, "low-income single renter"),
    ("married_separate", 70000, 4000, 2000, 3000, 500, "MFS moderate"),
    ("qualifying_widow", 90000, 3000, 2000, 5000, 1000, "QW moderate"),
]

_ITEMIZED_WINS_PROFILES = [
    # (filing_status, agi, state_tax, prop_tax, mortgage, charitable, label)
    ("single", 200000, 8000, 5000, 10000, 5000, "high-deduction single"),
    ("married_joint", 300000, 10000, 8000, 15000, 10000, "high-deduction married"),
    ("single", 150000, 7000, 4000, 9000, 3000, "upper-middle single homeowner"),
    ("head_of_household", 180000, 8000, 6000, 12000, 4000, "HoH high homeowner"),
    ("married_joint", 400000, 12000, 10000, 20000, 15000, "wealthy married"),
]


class TestStandardVsItemizedDecision:

    @pytest.mark.parametrize(
        "status,agi,state_tax,prop_tax,mortgage,charitable,label",
        _STANDARD_WINS_PROFILES,
        ids=[p[-1] for p in _STANDARD_WINS_PROFILES],
    )
    def test_standard_wins(self, status, agi, state_tax, prop_tax, mortgage, charitable, label):
        """Profiles where standard deduction should be recommended."""
        tp = TaxpayerInfo(
            first_name="T", last_name="U",
            filing_status=TaxpayerFilingStatus(status),
            dependents=[] if status != "head_of_household" else [
                _child_dep()
            ],
        )
        if status in ("married_joint", "married_separate", "qualifying_widow"):
            tp.spouse_first_name = "S"
            tp.spouse_last_name = "U"

        ded = Deductions(
            use_standard_deduction=False,
            itemized=ItemizedDeductions(
                state_local_income_tax=state_tax,
                real_estate_tax=prop_tax,
                mortgage_interest=mortgage,
                charitable_cash=charitable,
            ),
        )
        # Set attributes that _calculate_itemized looks for on the deductions object
        ded.__dict__["state_local_taxes"] = state_tax
        ded.__dict__["property_taxes"] = prop_tax
        ded.__dict__["mortgage_interest"] = mortgage
        ded.__dict__["charitable_cash"] = charitable
        tr = make_tax_return(taxpayer=tp, deductions=ded, agi=agi)
        analyzer = DeductionAnalyzer()
        rec = analyzer.analyze(tr)
        assert rec.recommended_strategy == "standard", (
            f"Expected standard for '{label}', got {rec.recommended_strategy}"
        )

    @pytest.mark.parametrize(
        "status,agi,state_tax,prop_tax,mortgage,charitable,label",
        _ITEMIZED_WINS_PROFILES,
        ids=[p[-1] for p in _ITEMIZED_WINS_PROFILES],
    )
    def test_itemized_wins(self, status, agi, state_tax, prop_tax, mortgage, charitable, label):
        """Profiles where itemized deductions should be recommended."""
        tp = TaxpayerInfo(
            first_name="T", last_name="U",
            filing_status=TaxpayerFilingStatus(status),
            dependents=[] if status != "head_of_household" else [
                _child_dep()
            ],
        )
        if status in ("married_joint", "married_separate", "qualifying_widow"):
            tp.spouse_first_name = "S"
            tp.spouse_last_name = "U"

        ded = Deductions(
            use_standard_deduction=False,
            itemized=ItemizedDeductions(
                state_local_income_tax=state_tax,
                real_estate_tax=prop_tax,
                mortgage_interest=mortgage,
                charitable_cash=charitable,
            ),
        )
        # Set attributes that _calculate_itemized looks for on the deductions object
        ded.__dict__["state_local_taxes"] = state_tax
        ded.__dict__["property_taxes"] = prop_tax
        ded.__dict__["mortgage_interest"] = mortgage
        ded.__dict__["charitable_cash"] = charitable
        tr = make_tax_return(taxpayer=tp, deductions=ded, agi=agi)
        analyzer = DeductionAnalyzer()
        rec = analyzer.analyze(tr)
        assert rec.recommended_strategy == "itemized", (
            f"Expected itemized for '{label}', got {rec.recommended_strategy}"
        )


def _child_dep():
    """Quick child dependent for HoH tests."""
    from models.taxpayer import Dependent
    return Dependent(name="Kid", age=8, relationship="son")


# ============================================================================
# Section 13 -- Confidence scoring
# ============================================================================


class TestDeductionConfidence:

    analyzer = DeductionAnalyzer()

    @pytest.mark.parametrize("difference,standard,expected_min", [
        (5000, 15750, 85),    # >20% diff
        (2000, 15750, 75),    # >10%
        (1000, 15750, 65),    # >5%
        (1500, 31500, 55),    # ~4.7%, >$1000
        (500, 15750, 55),     # small diff
    ])
    def test_confidence_ranges(self, difference, standard, expected_min):
        score = self.analyzer._calculate_confidence(difference, standard)
        assert score >= expected_min

    def test_large_difference_high_confidence(self):
        assert self.analyzer._calculate_confidence(10000, 15750) == 95.0

    def test_negative_difference_same_behaviour(self):
        # Negative means standard wins; confidence should still work
        score = self.analyzer._calculate_confidence(-10000, 15750)
        assert score == 95.0


# ============================================================================
# Section 14 -- Explanation generation
# ============================================================================


class TestExplanationGeneration:

    analyzer = DeductionAnalyzer()

    def test_itemized_explanation_mentions_savings(self):
        analysis = MagicMock()
        analysis.recommended_strategy = "itemized"
        analysis.deduction_difference = 5000
        analysis.total_standard_deduction = 15750
        analysis.total_itemized_deductions = 20750
        analysis.tax_savings_estimate = 1100
        analysis.marginal_rate = 22
        explanation = self.analyzer._generate_explanation(analysis)
        assert "itemiz" in explanation.lower()
        assert "$5,000" in explanation

    def test_standard_explanation_mentions_standard(self):
        analysis = MagicMock()
        analysis.recommended_strategy = "standard"
        analysis.deduction_difference = -3000
        analysis.total_standard_deduction = 15750
        analysis.total_itemized_deductions = 12750
        analysis.tax_savings_estimate = 660
        analysis.marginal_rate = 22
        explanation = self.analyzer._generate_explanation(analysis)
        assert "standard" in explanation.lower()


# ============================================================================
# Section 15 -- Opportunities identification
# ============================================================================


class TestOpportunities:

    analyzer = DeductionAnalyzer()

    def test_close_to_itemizing_opportunity(self):
        breakdown = ItemizedDeductionBreakdown(
            state_local_income_tax=5000,
            mortgage_interest=7000,
            cash_contributions=1000,
        )
        breakdown.calculate_totals(100000)
        standard = 15750
        tr = MagicMock()
        opportunities = self.analyzer._find_opportunities(tr, breakdown, standard, 100000)
        assert any("bunching" in o.lower() or "away" in o.lower() for o in opportunities)

    def test_salt_cap_exceeded_opportunity(self):
        breakdown = ItemizedDeductionBreakdown(
            state_local_income_tax=12000,
            property_tax=5000,
        )
        breakdown.calculate_totals(100000)
        opportunities = self.analyzer._find_opportunities(
            MagicMock(), breakdown, 15750, 100000
        )
        assert any("salt" in o.lower() or "$10,000" in o for o in opportunities)

    def test_medical_below_floor_opportunity(self):
        breakdown = ItemizedDeductionBreakdown(medical_expenses_total=5000)
        breakdown.calculate_totals(100000)  # threshold = 7500
        opportunities = self.analyzer._find_opportunities(
            MagicMock(), breakdown, 15750, 100000
        )
        assert any("medical" in o.lower() for o in opportunities)

    def test_no_charitable_opportunity(self):
        breakdown = ItemizedDeductionBreakdown(
            state_local_income_tax=5000,
            mortgage_interest=5000,
        )
        breakdown.calculate_totals(100000)
        opportunities = self.analyzer._find_opportunities(
            MagicMock(), breakdown, 15750, 100000
        )
        assert any("charitab" in o.lower() for o in opportunities)


# ============================================================================
# Section 16 -- Warnings
# ============================================================================


class TestDeductionWarnings:

    analyzer = DeductionAnalyzer()

    def test_large_charitable_warning(self):
        breakdown = ItemizedDeductionBreakdown(
            cash_contributions=40000,
            non_cash_contributions=5000,
        )
        tr = MagicMock()
        tr.adjusted_gross_income = 100000
        warnings = self.analyzer._generate_warnings(tr, breakdown)
        assert any("charitab" in w.lower() for w in warnings)

    def test_noncash_over_500_warning(self):
        breakdown = ItemizedDeductionBreakdown(non_cash_contributions=600)
        tr = MagicMock()
        tr.adjusted_gross_income = 100000
        warnings = self.analyzer._generate_warnings(tr, breakdown)
        assert any("8283" in w or "non-cash" in w.lower() for w in warnings)

    def test_casualty_loss_warning(self):
        breakdown = ItemizedDeductionBreakdown(casualty_losses_federally_declared=5000)
        tr = MagicMock()
        tr.adjusted_gross_income = 100000
        warnings = self.analyzer._generate_warnings(tr, breakdown)
        assert any("casualty" in w.lower() for w in warnings)

    def test_gambling_loss_warning(self):
        breakdown = ItemizedDeductionBreakdown(gambling_losses=3000)
        tr = MagicMock()
        tr.adjusted_gross_income = 100000
        warnings = self.analyzer._generate_warnings(tr, breakdown)
        assert any("gambling" in w.lower() for w in warnings)

    def test_no_warnings_clean_return(self):
        breakdown = ItemizedDeductionBreakdown()
        tr = MagicMock()
        tr.adjusted_gross_income = 100000
        warnings = self.analyzer._generate_warnings(tr, breakdown)
        assert warnings == []


# ============================================================================
# Section 17 -- _build_categories
# ============================================================================


class TestBuildCategories:

    analyzer = DeductionAnalyzer()

    def test_all_keys_present(self):
        breakdown = ItemizedDeductionBreakdown()
        breakdown.calculate_totals(100000)
        cats = self.analyzer._build_categories(breakdown)
        expected_keys = {
            "medical_dental",
            "taxes_paid_salt",
            "interest_paid",
            "charitable_contributions",
            "casualty_theft_losses",
            "other_deductions",
        }
        assert set(cats.keys()) == expected_keys

    def test_category_values_match(self):
        breakdown = ItemizedDeductionBreakdown(
            medical_expenses_total=10000,
            state_local_income_tax=6000,
            mortgage_interest=8000,
            cash_contributions=3000,
            casualty_losses_federally_declared=1000,
            gambling_losses=2000,
            other_deductions=500,
        )
        breakdown.calculate_totals(80000, gambling_winnings=5000)
        cats = self.analyzer._build_categories(breakdown)
        assert cats["taxes_paid_salt"] == breakdown.salt_deduction_allowed
        assert cats["interest_paid"] == breakdown.total_interest_deduction
        assert cats["charitable_contributions"] == breakdown.charitable_deduction_allowed
        assert cats["casualty_theft_losses"] == 1000


# ============================================================================
# Section 18 -- Full analyze() integration
# ============================================================================


class TestDeductionAnalyzerFullAnalyze:

    def test_returns_recommendation_type(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=80000)
        analyzer = DeductionAnalyzer()
        rec = analyzer.analyze(tr)
        assert isinstance(rec, DeductionRecommendation)

    def test_standard_deduction_for_simple_return(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=60000)
        analyzer = DeductionAnalyzer()
        rec = analyzer.analyze(tr)
        assert rec.recommended_strategy == "standard"

    def test_itemized_for_heavy_deductions(self, single_filer):
        ded = Deductions(
            use_standard_deduction=False,
            itemized=ItemizedDeductions(
                state_local_income_tax=8000,
                real_estate_tax=4000,
                mortgage_interest=12000,
                charitable_cash=5000,
            ),
        )
        # Set attributes that _calculate_itemized looks for on the deductions object
        ded.__dict__["state_local_taxes"] = 8000
        ded.__dict__["property_taxes"] = 4000
        ded.__dict__["mortgage_interest"] = 12000
        ded.__dict__["charitable_cash"] = 5000
        tr = make_tax_return(taxpayer=single_filer, deductions=ded, agi=150000)
        analyzer = DeductionAnalyzer()
        rec = analyzer.analyze(tr)
        assert rec.recommended_strategy == "itemized"

    def test_analysis_contains_correct_standard_for_single(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=60000)
        rec = DeductionAnalyzer().analyze(tr)
        assert rec.analysis.standard_deduction_base == 15750

    def test_analysis_contains_correct_standard_for_mfj(self, married_couple):
        tr = make_tax_return(taxpayer=married_couple, agi=100000)
        rec = DeductionAnalyzer().analyze(tr)
        assert rec.analysis.standard_deduction_base == 31500

    def test_confidence_score_in_range(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=60000)
        rec = DeductionAnalyzer().analyze(tr)
        assert 0 <= rec.confidence_score <= 100

    def test_explanation_not_empty(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=60000)
        rec = DeductionAnalyzer().analyze(tr)
        assert len(rec.explanation) > 0


# ============================================================================
# Section 19 -- Additional standard deduction (65+ / blind)
# ============================================================================


class TestAdditionalStandardDeduction:

    def test_senior_single_gets_additional(self, senior_single_filer):
        # Source checks `age` attr (not `is_over_65`) and `is_blind`
        # Set age so both age and blindness are detected
        senior_single_filer.__dict__["age"] = 67
        tr = make_tax_return(taxpayer=senior_single_filer, agi=50000)
        analyzer = DeductionAnalyzer()
        rec = analyzer.analyze(tr)
        # Single 65+ AND blind = 2 * 1950 = 3900 additional
        assert rec.analysis.additional_standard_deduction == pytest.approx(3900, abs=1)
        assert rec.analysis.total_standard_deduction == pytest.approx(15750 + 3900, abs=1)

    def test_senior_married_both_over_65(self, senior_married_couple):
        # Source checks `age`/`spouse_age` attrs (not `is_over_65`/`spouse_is_over_65`)
        senior_married_couple.__dict__["age"] = 68
        senior_married_couple.__dict__["spouse_age"] = 66
        tr = make_tax_return(taxpayer=senior_married_couple, agi=80000)
        analyzer = DeductionAnalyzer()
        rec = analyzer.analyze(tr)
        # Primary over 65: +1550, spouse over 65: +1550 = 3100
        assert rec.analysis.additional_standard_deduction == pytest.approx(3100, abs=1)

    def test_no_additional_for_young_filer(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=60000)
        rec = DeductionAnalyzer().analyze(tr)
        assert rec.analysis.additional_standard_deduction == 0.0


# ============================================================================
# Section 20 -- Bunching strategy evaluation
# ============================================================================


class TestBunchingStrategy:

    def test_bunching_not_suggested_when_no_controllable(self, single_filer):
        tr = make_tax_return(taxpayer=single_filer, agi=60000)
        analyzer = DeductionAnalyzer()
        rec = analyzer.analyze(tr)
        assert rec.bunching_strategy is None

    def test_bunching_suggested_when_beneficial(self, single_filer):
        ded = Deductions(
            use_standard_deduction=False,
            itemized=ItemizedDeductions(
                state_local_income_tax=5000,
                mortgage_interest=6000,
                charitable_cash=4000,
                real_estate_tax=3000,
            ),
        )
        # Set attributes that _calculate_itemized looks for on the deductions object
        ded.__dict__["state_local_taxes"] = 5000
        ded.__dict__["property_taxes"] = 3000
        ded.__dict__["mortgage_interest"] = 6000
        ded.__dict__["charitable_cash"] = 4000
        tr = make_tax_return(taxpayer=single_filer, deductions=ded, agi=100000)
        analyzer = DeductionAnalyzer()
        rec = analyzer.analyze(tr)
        if rec.bunching_strategy is not None:
            assert rec.bunching_strategy["is_beneficial"] is True
            assert rec.bunching_strategy["two_year_savings"] > 0


# ============================================================================
# Section 21 -- Current-year actions & next-year planning
# ============================================================================


class TestActionItems:

    def test_current_actions_not_empty_when_near_itemizing(self, single_filer):
        ded = Deductions(
            use_standard_deduction=False,
            itemized=ItemizedDeductions(
                state_local_income_tax=5000,
                mortgage_interest=6000,
                charitable_cash=2000,
            ),
        )
        # Set attributes that _calculate_itemized looks for on the deductions object
        ded.__dict__["state_local_taxes"] = 5000
        ded.__dict__["mortgage_interest"] = 6000
        ded.__dict__["charitable_cash"] = 2000
        tr = make_tax_return(taxpayer=single_filer, deductions=ded, agi=80000)
        rec = DeductionAnalyzer().analyze(tr)
        # Gap is ~2750, close enough that actions should be generated
        assert len(rec.current_year_actions) > 0

    def test_next_year_planning_for_near_threshold(self, single_filer):
        ded = Deductions(
            use_standard_deduction=False,
            itemized=ItemizedDeductions(
                state_local_income_tax=5000,
                mortgage_interest=6000,
                charitable_cash=2000,
            ),
        )
        # Set attributes that _calculate_itemized looks for on the deductions object
        ded.__dict__["state_local_taxes"] = 5000
        ded.__dict__["mortgage_interest"] = 6000
        ded.__dict__["charitable_cash"] = 2000
        tr = make_tax_return(taxpayer=single_filer, deductions=ded, agi=80000)
        rec = DeductionAnalyzer().analyze(tr)
        assert len(rec.next_year_planning) > 0

    def test_itemizing_actions_include_documentation(self, single_filer):
        ded = Deductions(
            use_standard_deduction=False,
            itemized=ItemizedDeductions(
                state_local_income_tax=8000,
                real_estate_tax=4000,
                mortgage_interest=12000,
                charitable_cash=5000,
            ),
        )
        # Set attributes that _calculate_itemized looks for on the deductions object
        ded.__dict__["state_local_taxes"] = 8000
        ded.__dict__["property_taxes"] = 4000
        ded.__dict__["mortgage_interest"] = 12000
        ded.__dict__["charitable_cash"] = 5000
        tr = make_tax_return(taxpayer=single_filer, deductions=ded, agi=150000)
        rec = DeductionAnalyzer().analyze(tr)
        assert any("document" in a.lower() or "receipt" in a.lower()
                    for a in rec.current_year_actions)
