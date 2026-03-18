"""
Unit tests for the lead-magnet → advisory-report schema bridge.

Covers income estimation, occupation-based income splitting, investment
allocation, homeowner deductions, retirement/HSA inference, state code
normalisation, override_income, None-stripping, and dataclass input.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import pytest

from cpa_panel.services.lead_magnet_report_builder import (
    build_tax_profile_input,
    INCOME_RANGE_MIDPOINTS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(**overrides) -> dict:
    """Return a minimal lead-magnet profile dict with sensible defaults."""
    base: Dict[str, Any] = {
        "filing_status": "single",
        "income_range": "50k-75k",
        "income_sources": [],
        "has_business": False,
        "occupation_type": "w2",
        "state_code": "CA",
        "dependents_count": 0,
        "is_homeowner": False,
        "has_student_loans": False,
        "retirement_savings": "none",
        "healthcare_type": "employer",
    }
    base.update(overrides)
    return base


class DictProfile:
    """Thin wrapper so build_tax_profile_input can call .to_dict()."""

    def __init__(self, data: dict):
        self._data = data

    def to_dict(self) -> dict:
        return dict(self._data)


# ---------------------------------------------------------------------------
# 1. Income range conversion — all ranges in INCOME_RANGE_MIDPOINTS
# ---------------------------------------------------------------------------

class TestIncomeRangeConversion:

    @pytest.mark.parametrize("range_key,expected_midpoint", list(INCOME_RANGE_MIDPOINTS.items()))
    def test_each_income_range_maps_to_correct_midpoint(self, range_key, expected_midpoint):
        profile = _make_profile(income_range=range_key)
        result = build_tax_profile_input(profile)
        assert result["total_income"] == expected_midpoint

    def test_unknown_range_falls_back_to_default(self):
        profile = _make_profile(income_range="unknown_range")
        result = build_tax_profile_input(profile)
        assert result["total_income"] == 62_500  # fallback default

    def test_missing_range_uses_default(self):
        profile = _make_profile()
        del profile["income_range"]
        result = build_tax_profile_input(profile)
        assert result["total_income"] == 62_500


# ---------------------------------------------------------------------------
# 2. W2-only occupation → all income as w2_income
# ---------------------------------------------------------------------------

class TestW2OnlyOccupation:

    def test_w2_occupation_assigns_all_income_to_w2(self):
        profile = _make_profile(occupation_type="w2", has_business=False, income_range="100k-150k")
        result = build_tax_profile_input(profile)
        assert result["w2_income"] == 125_000
        assert "business_income" not in result

    def test_default_occupation_is_w2(self):
        profile = _make_profile()
        del profile["occupation_type"]
        result = build_tax_profile_input(profile)
        assert result["w2_income"] == result["total_income"]


# ---------------------------------------------------------------------------
# 3. Self-employed → 70/30 split business/w2
# ---------------------------------------------------------------------------

class TestSelfEmployedSplit:

    @pytest.mark.parametrize("occ_type", ["self_employed", "1099"])
    def test_self_employed_with_w2_source_splits_70_30(self, occ_type):
        profile = _make_profile(
            occupation_type=occ_type,
            income_range="100k-150k",
            income_sources=["w2"],
        )
        result = build_tax_profile_input(profile)
        total = 125_000
        assert result["business_income"] == round(total * 0.7)
        assert result["w2_income"] == round(total * 0.3)

    def test_self_employed_without_w2_source_all_business(self):
        profile = _make_profile(
            occupation_type="self_employed",
            income_sources=[],
            income_range="75k-100k",
        )
        result = build_tax_profile_input(profile)
        assert result["business_income"] == 87_500
        assert "w2_income" not in result

    def test_has_business_flag_triggers_split(self):
        profile = _make_profile(
            has_business=True,
            occupation_type="w2",
            income_sources=["w2"],
            income_range="100k-150k",
        )
        result = build_tax_profile_input(profile)
        total = 125_000
        assert result["business_income"] == round(total * 0.7)
        assert result["w2_income"] == round(total * 0.3)


# ---------------------------------------------------------------------------
# 4. Investment income sources → 10% allocation
# ---------------------------------------------------------------------------

class TestInvestmentIncome:

    @pytest.mark.parametrize("source_key", ["investments", "investment"])
    def test_investment_source_allocates_10_percent(self, source_key):
        profile = _make_profile(
            income_sources=[source_key],
            income_range="200k-300k",
        )
        result = build_tax_profile_input(profile)
        total = 250_000
        expected_inv = round(total * 0.10)
        assert result["investment_income"] == expected_inv
        # w2 should be reduced by the investment amount
        assert result["w2_income"] == total - expected_inv

    def test_no_investment_source_omits_investment_income(self):
        profile = _make_profile(income_sources=[])
        result = build_tax_profile_input(profile)
        assert "investment_income" not in result

    def test_investment_with_self_employed_no_w2_source(self):
        """Investment deduction does not create negative w2 when w2 is None."""
        profile = _make_profile(
            occupation_type="self_employed",
            income_sources=["investment"],
            income_range="100k-150k",
        )
        result = build_tax_profile_input(profile)
        assert result["investment_income"] == round(125_000 * 0.10)
        # w2_income is None (not in result), so no subtraction
        assert "w2_income" not in result


# ---------------------------------------------------------------------------
# 5. Homeowner flag → mortgage_interest and property_taxes populated
# ---------------------------------------------------------------------------

class TestHomeownerDeductions:

    def test_homeowner_true_populates_deductions(self):
        profile = _make_profile(is_homeowner=True)
        result = build_tax_profile_input(profile)
        assert result["mortgage_interest"] == 12_000.0
        assert result["property_taxes"] == 5_000.0

    def test_homeowner_false_omits_deductions(self):
        profile = _make_profile(is_homeowner=False)
        result = build_tax_profile_input(profile)
        assert "mortgage_interest" not in result
        assert "property_taxes" not in result


# ---------------------------------------------------------------------------
# 6. Retirement savings levels: none / some / maxed
# ---------------------------------------------------------------------------

class TestRetirementSavings:

    def test_retirement_none_omits_401k(self):
        profile = _make_profile(retirement_savings="none")
        result = build_tax_profile_input(profile)
        assert "retirement_401k" not in result

    def test_retirement_some_gives_moderate_estimate(self):
        profile = _make_profile(retirement_savings="some")
        result = build_tax_profile_input(profile)
        assert result["retirement_401k"] == 8_000.0

    def test_retirement_maxed_gives_2025_max(self):
        profile = _make_profile(retirement_savings="maxed")
        result = build_tax_profile_input(profile)
        assert result["retirement_401k"] == 23_000.0


# ---------------------------------------------------------------------------
# 7. HSA from HDHP healthcare type
# ---------------------------------------------------------------------------

class TestHSAContributions:

    def test_hdhp_hsa_sets_hsa_contributions(self):
        profile = _make_profile(healthcare_type="hdhp_hsa")
        result = build_tax_profile_input(profile)
        assert result["hsa_contributions"] == 4_150.0

    def test_employer_healthcare_omits_hsa(self):
        profile = _make_profile(healthcare_type="employer")
        result = build_tax_profile_input(profile)
        assert "hsa_contributions" not in result

    def test_marketplace_healthcare_omits_hsa(self):
        profile = _make_profile(healthcare_type="marketplace")
        result = build_tax_profile_input(profile)
        assert "hsa_contributions" not in result


# ---------------------------------------------------------------------------
# 8. State code normalisation (2-letter vs "US")
# ---------------------------------------------------------------------------

class TestStateCodeNormalization:

    @pytest.mark.parametrize("code", ["CA", "TX", "NY", "FL"])
    def test_valid_two_letter_state_code_kept(self, code):
        profile = _make_profile(state_code=code)
        result = build_tax_profile_input(profile)
        assert result["state"] == code

    def test_us_code_is_excluded(self):
        profile = _make_profile(state_code="US")
        result = build_tax_profile_input(profile)
        assert "state" not in result

    def test_empty_state_code_is_excluded(self):
        profile = _make_profile(state_code="")
        result = build_tax_profile_input(profile)
        assert "state" not in result

    def test_long_state_string_is_excluded(self):
        profile = _make_profile(state_code="California")
        result = build_tax_profile_input(profile)
        assert "state" not in result


# ---------------------------------------------------------------------------
# 9. override_income parameter
# ---------------------------------------------------------------------------

class TestOverrideIncome:

    def test_override_replaces_midpoint(self):
        profile = _make_profile(income_range="0-25k")
        result = build_tax_profile_input(profile, override_income=99_999.0)
        assert result["total_income"] == 99_999.0

    def test_override_none_uses_midpoint(self):
        profile = _make_profile(income_range="0-25k")
        result = build_tax_profile_input(profile, override_income=None)
        assert result["total_income"] == 12_500

    def test_override_affects_w2_income(self):
        profile = _make_profile(income_range="0-25k", occupation_type="w2")
        result = build_tax_profile_input(profile, override_income=200_000.0)
        assert result["w2_income"] == 200_000.0


# ---------------------------------------------------------------------------
# 10. None values stripped from output
# ---------------------------------------------------------------------------

class TestNoneStripping:

    def test_none_values_not_in_result(self):
        profile = _make_profile(
            is_homeowner=False,
            retirement_savings="none",
            healthcare_type="employer",
        )
        result = build_tax_profile_input(profile)
        for value in result.values():
            assert value is not None

    def test_all_optional_fields_absent_when_not_applicable(self):
        """Minimal profile should omit all purely optional keys."""
        profile = _make_profile()
        result = build_tax_profile_input(profile)
        absent_keys = [
            "business_income",
            "investment_income",
            "mortgage_interest",
            "property_taxes",
            "retirement_401k",
            "hsa_contributions",
            "health_insurance_premiums",
        ]
        for key in absent_keys:
            assert key not in result, f"{key} should be absent"


# ---------------------------------------------------------------------------
# 11. TaxProfile dataclass input (mock with to_dict())
# ---------------------------------------------------------------------------

class TestTaxProfileDataclassInput:

    def test_dataclass_with_to_dict(self):
        @dataclass
        class FakeTaxProfile:
            filing_status: str = "married_filing_jointly"
            income_range: str = "150k-200k"
            income_sources: list = None
            has_business: bool = False
            occupation_type: str = "w2"
            state_code: str = "NY"
            dependents_count: int = 2
            is_homeowner: bool = True
            has_student_loans: bool = False
            retirement_savings: str = "maxed"
            healthcare_type: str = "employer"

            def __post_init__(self):
                if self.income_sources is None:
                    self.income_sources = []

            def to_dict(self) -> dict:
                return asdict(self)

        tp = FakeTaxProfile()
        result = build_tax_profile_input(tp)

        assert result["filing_status"] == "married_filing_jointly"
        assert result["total_income"] == 175_000
        assert result["w2_income"] == 175_000
        assert result["state"] == "NY"
        assert result["dependents"] == 2
        assert result["mortgage_interest"] == 12_000.0
        assert result["property_taxes"] == 5_000.0
        assert result["retirement_401k"] == 23_000.0
        assert result["is_self_employed"] is False

    def test_plain_dict_input_also_works(self):
        """build_tax_profile_input should fall back to dict() for plain dicts."""
        profile = _make_profile(income_range="300k-500k")
        result = build_tax_profile_input(profile)
        assert result["total_income"] == 400_000

    def test_wrapper_with_to_dict(self):
        """Objects with to_dict() method are handled correctly."""
        data = _make_profile(
            income_range="500k+",
            occupation_type="self_employed",
            income_sources=["w2", "investments"],
            is_homeowner=True,
            retirement_savings="some",
            healthcare_type="hdhp_hsa",
            state_code="TX",
        )
        wrapped = DictProfile(data)
        result = build_tax_profile_input(wrapped)

        assert result["total_income"] == 600_000
        assert result["business_income"] == round(600_000 * 0.7)
        assert result["investment_income"] == round(600_000 * 0.10)
        assert result["mortgage_interest"] == 12_000.0
        assert result["retirement_401k"] == 8_000.0
        assert result["hsa_contributions"] == 4_150.0
        assert result["state"] == "TX"
        assert result["is_self_employed"] is True


# ---------------------------------------------------------------------------
# Bonus: health insurance premiums for self-employed + marketplace
# ---------------------------------------------------------------------------

class TestHealthInsurancePremiums:

    def test_self_employed_marketplace_gets_premiums(self):
        profile = _make_profile(
            occupation_type="self_employed",
            healthcare_type="marketplace",
        )
        result = build_tax_profile_input(profile)
        assert result["health_insurance_premiums"] == 7_200.0

    def test_self_employed_individual_gets_premiums(self):
        profile = _make_profile(
            occupation_type="1099",
            healthcare_type="individual",
        )
        result = build_tax_profile_input(profile)
        assert result["health_insurance_premiums"] == 7_200.0

    def test_w2_employee_no_premiums(self):
        profile = _make_profile(
            occupation_type="w2",
            healthcare_type="marketplace",
        )
        result = build_tax_profile_input(profile)
        assert "health_insurance_premiums" not in result

    def test_self_employed_employer_healthcare_no_premiums(self):
        profile = _make_profile(
            occupation_type="self_employed",
            healthcare_type="employer",
        )
        result = build_tax_profile_input(profile)
        assert "health_insurance_premiums" not in result
