"""
Tests for ScenarioService and ScenarioTemplate.

Covers template management, scenario creation, comparison,
marginal rate calculation, quick compare, and edge cases.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cpa_panel.services.scenario_service import (
    ScenarioService,
    ScenarioTemplate,
    SCENARIO_TEMPLATES,
    get_scenario_service,
)


# =========================================================================
# SCENARIO TEMPLATE DATACLASS
# =========================================================================

class TestScenarioTemplate:
    """Tests for ScenarioTemplate dataclass."""

    def test_creation(self):
        template = ScenarioTemplate(
            template_id="test_1",
            name="Test Scenario",
            description="A test scenario",
            category="test",
            adjustments=[{"field": "income", "value": 1000}],
            variables=["amount"],
            default_values={"amount": 1000},
            notes=["Note 1"],
        )
        assert template.template_id == "test_1"
        assert template.category == "test"

    def test_to_dict(self):
        template = ScenarioTemplate(
            template_id="test_1",
            name="Test",
            description="Desc",
            category="cat",
            adjustments=[],
            variables=[],
            default_values={},
            notes=[],
        )
        d = template.to_dict()
        expected_keys = {
            "template_id", "name", "description", "category",
            "adjustments", "variables", "default_values", "notes",
        }
        assert set(d.keys()) == expected_keys

    def test_create_scenario_default_values(self):
        template = ScenarioTemplate(
            template_id="t1",
            name="Max 401k",
            description="Max out 401k",
            category="retirement",
            adjustments=[{
                "field": "401k_contribution",
                "value_key": "amount",
                "description": "401k increase",
            }],
            variables=["amount"],
            default_values={"amount": 23500},
            notes=[],
        )
        with patch("cpa_panel.services.scenario_service.ScenarioAdjustment") as MockAdj, \
             patch("cpa_panel.services.scenario_service.Scenario") as MockScenario:
            MockAdj.return_value = MagicMock()
            MockScenario.return_value = MagicMock()
            scenario = template.create_scenario()
            MockAdj.assert_called_once()
            # The value should use default_values["amount"] = 23500
            call_kwargs = MockAdj.call_args
            assert call_kwargs[1]["value"] == 23500 or call_kwargs[0][1] == 23500 \
                or MockAdj.call_args.kwargs.get("value") == 23500

    def test_create_scenario_custom_values(self):
        template = ScenarioTemplate(
            template_id="t1",
            name="Max 401k",
            description="Max out 401k",
            category="retirement",
            adjustments=[{
                "field": "401k_contribution",
                "value_key": "amount",
                "description": "401k increase",
            }],
            variables=["amount"],
            default_values={"amount": 23500},
            notes=[],
        )
        with patch("cpa_panel.services.scenario_service.ScenarioAdjustment") as MockAdj, \
             patch("cpa_panel.services.scenario_service.Scenario") as MockScenario:
            MockAdj.return_value = MagicMock()
            MockScenario.return_value = MagicMock()
            scenario = template.create_scenario(custom_values={"amount": 15000})
            # Custom value should override default
            call_args = MockAdj.call_args
            assert 15000 in [call_args.kwargs.get("value"), call_args[1].get("value")] \
                or (len(call_args[0]) > 1 and call_args[0][1] == 15000)

    def test_create_scenario_no_value_key(self):
        template = ScenarioTemplate(
            template_id="t2",
            name="Side Income",
            description="Add side income",
            category="income",
            adjustments=[{
                "field": "income",
                "value": 10000,
                "description": "Additional income",
            }],
            variables=[],
            default_values={},
            notes=[],
        )
        with patch("cpa_panel.services.scenario_service.ScenarioAdjustment") as MockAdj, \
             patch("cpa_panel.services.scenario_service.Scenario") as MockScenario:
            MockAdj.return_value = MagicMock()
            MockScenario.return_value = MagicMock()
            scenario = template.create_scenario()
            MockAdj.assert_called_once()


# =========================================================================
# PRE-BUILT TEMPLATES
# =========================================================================

class TestPreBuiltTemplates:
    """Verify all pre-built SCENARIO_TEMPLATES."""

    def test_templates_dict_not_empty(self):
        assert len(SCENARIO_TEMPLATES) > 0

    @pytest.mark.parametrize("template_id", [
        "max_401k", "max_ira", "max_hsa", "all_retirement",
        "mfj_vs_mfs", "charitable_bunching", "daf_contribution",
        "home_office", "vehicle_deduction", "business_equipment",
        "defer_income", "accelerate_income",
        "side_income_10k", "side_income_25k",
        "education_credits", "solar_installation", "ev_purchase",
    ])
    def test_template_exists(self, template_id):
        assert template_id in SCENARIO_TEMPLATES

    @pytest.mark.parametrize("template_id", list(SCENARIO_TEMPLATES.keys()))
    def test_template_has_required_fields(self, template_id):
        t = SCENARIO_TEMPLATES[template_id]
        assert isinstance(t, ScenarioTemplate)
        assert t.template_id == template_id
        assert len(t.name) > 0
        assert len(t.description) > 0
        assert len(t.category) > 0
        assert isinstance(t.adjustments, list)
        assert len(t.adjustments) > 0
        assert isinstance(t.notes, list)

    @pytest.mark.parametrize("template_id", list(SCENARIO_TEMPLATES.keys()))
    def test_template_to_dict(self, template_id):
        t = SCENARIO_TEMPLATES[template_id]
        d = t.to_dict()
        assert d["template_id"] == template_id
        assert isinstance(d["notes"], list)

    def test_categories_present(self):
        categories = {t.category for t in SCENARIO_TEMPLATES.values()}
        expected = {"retirement", "filing_status", "charitable", "business",
                    "income_timing", "income", "education", "energy"}
        assert expected.issubset(categories)

    @pytest.mark.parametrize("category", [
        "retirement", "filing_status", "charitable", "business",
        "income_timing", "income", "education", "energy",
    ])
    def test_category_has_templates(self, category):
        templates = [t for t in SCENARIO_TEMPLATES.values() if t.category == category]
        assert len(templates) > 0

    def test_retirement_templates_count(self):
        retirement = [t for t in SCENARIO_TEMPLATES.values() if t.category == "retirement"]
        assert len(retirement) >= 3

    def test_max_401k_default_value(self):
        t = SCENARIO_TEMPLATES["max_401k"]
        assert t.default_values["contribution_amount"] == 23500

    def test_max_ira_default_value(self):
        t = SCENARIO_TEMPLATES["max_ira"]
        assert t.default_values["contribution_amount"] == 7000

    def test_max_hsa_default_value(self):
        t = SCENARIO_TEMPLATES["max_hsa"]
        assert t.default_values["contribution_amount"] == 8550

    def test_ev_credit_default_value(self):
        t = SCENARIO_TEMPLATES["ev_purchase"]
        assert t.default_values["credit_amount"] == 7500

    def test_solar_default_value(self):
        t = SCENARIO_TEMPLATES["solar_installation"]
        assert t.default_values["credit_amount"] == 7500

    def test_home_office_default_value(self):
        t = SCENARIO_TEMPLATES["home_office"]
        assert t.default_values["deduction_amount"] == 1500

    def test_all_retirement_has_two_adjustments(self):
        t = SCENARIO_TEMPLATES["all_retirement"]
        assert len(t.adjustments) == 2

    def test_defer_income_negative(self):
        t = SCENARIO_TEMPLATES["defer_income"]
        assert t.default_values["deferral_amount"] < 0

    @pytest.mark.parametrize("template_id", list(SCENARIO_TEMPLATES.keys()))
    def test_each_adjustment_has_field(self, template_id):
        t = SCENARIO_TEMPLATES[template_id]
        for adj in t.adjustments:
            assert "field" in adj

    @pytest.mark.parametrize("template_id", list(SCENARIO_TEMPLATES.keys()))
    def test_notes_are_strings(self, template_id):
        t = SCENARIO_TEMPLATES[template_id]
        for note in t.notes:
            assert isinstance(note, str)
            assert len(note) > 0


# =========================================================================
# SCENARIO SERVICE
# =========================================================================

class TestScenarioService:
    """Tests for ScenarioService class."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch("cpa_panel.services.scenario_service.ScenarioComparator"):
            self.service = ScenarioService()

    def test_init_has_comparator(self):
        assert self.service.comparator is not None

    def test_init_has_templates(self):
        assert self.service.templates == SCENARIO_TEMPLATES

    # ---- get_templates ----

    def test_get_templates_all(self):
        templates = self.service.get_templates()
        assert len(templates) == len(SCENARIO_TEMPLATES)

    def test_get_templates_returns_dicts(self):
        templates = self.service.get_templates()
        for t in templates:
            assert isinstance(t, dict)
            assert "template_id" in t

    @pytest.mark.parametrize("category", [
        "retirement", "filing_status", "charitable",
        "business", "income_timing", "income", "education", "energy",
    ])
    def test_get_templates_by_category(self, category):
        templates = self.service.get_templates(category=category)
        assert len(templates) > 0
        for t in templates:
            assert t["category"] == category

    def test_get_templates_unknown_category(self):
        templates = self.service.get_templates(category="nonexistent")
        assert len(templates) == 0

    # ---- get_template_categories ----

    def test_get_template_categories(self):
        categories = self.service.get_template_categories()
        assert isinstance(categories, list)
        assert len(categories) > 0

    def test_get_template_categories_structure(self):
        categories = self.service.get_template_categories()
        for cat in categories:
            assert "category" in cat
            assert "count" in cat
            assert "templates" in cat
            assert cat["count"] > 0

    def test_categories_cover_all_templates(self):
        categories = self.service.get_template_categories()
        total = sum(c["count"] for c in categories)
        assert total == len(SCENARIO_TEMPLATES)

    # ---- compare_scenarios ----

    def test_compare_no_tax_return(self):
        with patch.object(self.service, "get_tax_return", return_value=None):
            result = self.service.compare_scenarios("session-1", [
                {"template_id": "max_401k"},
            ])
            assert result["success"] is False
            assert "not found" in result["error"]

    def test_compare_no_valid_scenarios(self):
        mock_return = MagicMock()
        with patch.object(self.service, "get_tax_return", return_value=mock_return):
            result = self.service.compare_scenarios("session-1", [
                {"template_id": "nonexistent"},
            ])
            assert result["success"] is False

    def test_compare_limits_to_4_scenarios(self):
        mock_return = MagicMock()
        self.service.comparator.compare.return_value = MagicMock(
            to_dict=MagicMock(return_value={"scenarios": []})
        )
        with patch.object(self.service, "get_tax_return", return_value=mock_return), \
             patch.object(self.service, "_build_scenario") as mock_build:
            mock_build.return_value = MagicMock()
            configs = [{"template_id": f"t{i}"} for i in range(6)]
            self.service.compare_scenarios("session-1", configs)
            # Should call _build_scenario at most 4 times
            assert mock_build.call_count <= 4

    def test_compare_success(self):
        mock_return = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"scenarios": [{"name": "Max 401k"}]}
        self.service.comparator.compare.return_value = mock_result
        with patch.object(self.service, "get_tax_return", return_value=mock_return), \
             patch.object(self.service, "_build_scenario", return_value=MagicMock()):
            result = self.service.compare_scenarios("session-1", [
                {"template_id": "max_401k"},
            ])
            assert result["success"] is True

    def test_compare_exception_handled(self):
        mock_return = MagicMock()
        self.service.comparator.compare.side_effect = Exception("boom")
        with patch.object(self.service, "get_tax_return", return_value=mock_return), \
             patch.object(self.service, "_build_scenario", return_value=MagicMock()):
            result = self.service.compare_scenarios("session-1", [
                {"template_id": "max_401k"},
            ])
            assert result["success"] is False
            assert "boom" in result["error"]

    # ---- compare_from_templates ----

    def test_compare_from_templates_no_valid(self):
        with patch.object(self.service, "get_tax_return", return_value=MagicMock()):
            result = self.service.compare_from_templates("s1", ["nonexistent"])
            assert result["success"] is False

    def test_compare_from_templates_no_return(self):
        with patch.object(self.service, "get_tax_return", return_value=None):
            result = self.service.compare_from_templates("s1", ["max_401k"])
            assert result["success"] is False

    def test_compare_from_templates_success(self):
        mock_return = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"scenarios": []}
        self.service.comparator.compare.return_value = mock_result
        with patch.object(self.service, "get_tax_return", return_value=mock_return):
            result = self.service.compare_from_templates("s1", ["max_401k"])
            assert result["success"] is True

    def test_compare_from_templates_custom_values(self):
        mock_return = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"scenarios": []}
        self.service.comparator.compare.return_value = mock_result
        with patch.object(self.service, "get_tax_return", return_value=mock_return):
            result = self.service.compare_from_templates(
                "s1",
                ["max_401k"],
                custom_values={"max_401k": {"contribution_amount": 10000}},
            )
            assert result["success"] is True

    def test_compare_from_templates_exception(self):
        mock_return = MagicMock()
        self.service.comparator.compare.side_effect = Exception("fail")
        with patch.object(self.service, "get_tax_return", return_value=mock_return):
            result = self.service.compare_from_templates("s1", ["max_401k"])
            assert result["success"] is False

    # ---- quick_compare ----

    def test_quick_compare_no_return(self):
        with patch.object(self.service, "get_tax_return", return_value=None):
            result = self.service.quick_compare("s1", [{"field": "income", "value": 1000}])
            assert result["success"] is False

    def test_quick_compare_success(self):
        mock_return = MagicMock()
        mock_return.tax_liability = 15000
        mock_return.taxable_income = 80000
        mock_return.filing_status = "single"
        self.service.comparator.quick_compare.return_value = {"estimated_change": -500}
        with patch.object(self.service, "get_tax_return", return_value=mock_return):
            result = self.service.quick_compare("s1", [{"field": "deduction", "value": 5000}])
            assert result["success"] is True

    def test_quick_compare_exception(self):
        mock_return = MagicMock()
        mock_return.tax_liability = 15000
        mock_return.taxable_income = 80000
        mock_return.filing_status = "single"
        self.service.comparator.quick_compare.side_effect = Exception("error")
        with patch.object(self.service, "get_tax_return", return_value=mock_return):
            result = self.service.quick_compare("s1", [{"field": "income", "value": 1000}])
            assert result["success"] is False

    # ---- get_common_scenarios ----

    def test_common_scenarios_no_return(self):
        with patch.object(self.service, "get_tax_return", return_value=None):
            result = self.service.get_common_scenarios("s1")
            assert result["success"] is False

    def test_common_scenarios_success(self):
        mock_return = MagicMock()
        mock_scenarios = [MagicMock(to_dict=MagicMock(return_value={"name": "s1"}))]
        self.service.comparator.create_common_scenarios.return_value = mock_scenarios
        with patch.object(self.service, "get_tax_return", return_value=mock_return):
            result = self.service.get_common_scenarios("s1")
            assert result["success"] is True
            assert result["total_scenarios"] == 1

    def test_common_scenarios_exception(self):
        mock_return = MagicMock()
        self.service.comparator.create_common_scenarios.side_effect = Exception("err")
        with patch.object(self.service, "get_tax_return", return_value=mock_return):
            result = self.service.get_common_scenarios("s1")
            assert result["success"] is False

    # ---- _build_scenario ----

    def test_build_scenario_from_template(self):
        with patch("cpa_panel.services.scenario_service.ScenarioAdjustment"), \
             patch("cpa_panel.services.scenario_service.Scenario") as MockScenario:
            MockScenario.return_value = MagicMock()
            result = self.service._build_scenario({"template_id": "max_401k"})
            assert result is not None

    def test_build_scenario_custom(self):
        with patch("cpa_panel.services.scenario_service.ScenarioAdjustment") as MockAdj, \
             patch("cpa_panel.services.scenario_service.Scenario") as MockScenario:
            MockAdj.return_value = MagicMock()
            MockScenario.return_value = MagicMock()
            result = self.service._build_scenario({
                "name": "Custom",
                "description": "Custom scenario",
                "adjustments": [{"field": "income", "value": 5000}],
            })
            assert result is not None

    def test_build_scenario_invalid_config(self):
        result = self.service._build_scenario({})
        assert result is None

    def test_build_scenario_nonexistent_template(self):
        result = self.service._build_scenario({"template_id": "does_not_exist"})
        assert result is None

    def test_build_scenario_custom_no_adjustments(self):
        result = self.service._build_scenario({"name": "Empty"})
        assert result is None


# =========================================================================
# MARGINAL RATE
# =========================================================================

class TestMarginalRate:
    """Tests for _get_marginal_rate."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch("cpa_panel.services.scenario_service.ScenarioComparator"):
            self.service = ScenarioService()

    @pytest.mark.parametrize("income,filing,expected", [
        (10000, "single", 0.10),
        (30000, "single", 0.12),
        (80000, "single", 0.22),
        (150000, "single", 0.24),
        (230000, "single", 0.32),
        (500000, "single", 0.35),
        (700000, "single", 0.37),
        (20000, "married_filing_jointly", 0.10),
        (60000, "married_filing_jointly", 0.12),
        (150000, "married_filing_jointly", 0.22),
        (300000, "married_filing_jointly", 0.24),
        (480000, "married_filing_jointly", 0.32),
        (600000, "married_filing_jointly", 0.35),
        (800000, "married_filing_jointly", 0.37),
        (10000, "married_filing_separately", 0.10),
        (30000, "married_filing_separately", 0.12),
        (80000, "married_filing_separately", 0.22),
        (15000, "head_of_household", 0.10),
        (50000, "head_of_household", 0.12),
        (80000, "head_of_household", 0.22),
        (20000, "qualifying_surviving_spouse", 0.10),
    ])
    def test_marginal_rate_brackets(self, income, filing, expected):
        rate = self.service._get_marginal_rate(income, filing)
        assert rate == expected

    def test_unknown_filing_defaults_to_single(self):
        rate = self.service._get_marginal_rate(80000, "unknown_status")
        assert rate == 0.22

    def test_none_filing_defaults_to_single(self):
        rate = self.service._get_marginal_rate(80000, None)
        assert rate == 0.22

    @pytest.mark.parametrize("income", [0, 1, 5000, 11925, 11926, 48475, 48476])
    def test_bracket_boundaries_single(self, income):
        rate = self.service._get_marginal_rate(income, "single")
        assert 0.10 <= rate <= 0.37

    def test_very_high_income(self):
        rate = self.service._get_marginal_rate(10_000_000, "single")
        assert rate == 0.37

    def test_zero_income(self):
        rate = self.service._get_marginal_rate(0, "single")
        assert rate == 0.10


# =========================================================================
# SINGLETON
# =========================================================================

class TestScenarioSingleton:
    """Test singleton accessor."""

    def test_get_service(self):
        with patch("cpa_panel.services.scenario_service.ScenarioComparator"):
            svc = get_scenario_service()
            assert isinstance(svc, ScenarioService)


# =========================================================================
# EDGE CASES
# =========================================================================

class TestScenarioEdgeCases:
    """Edge cases for scenario service."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        with patch("cpa_panel.services.scenario_service.ScenarioComparator"):
            self.service = ScenarioService()

    def test_compare_empty_scenario_list(self):
        with patch.object(self.service, "get_tax_return", return_value=MagicMock()):
            result = self.service.compare_scenarios("s1", [])
            assert result["success"] is False

    def test_compare_identical_scenarios(self):
        mock_return = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"scenarios": []}
        self.service.comparator.compare.return_value = mock_result
        with patch.object(self.service, "get_tax_return", return_value=mock_return):
            result = self.service.compare_scenarios("s1", [
                {"template_id": "max_401k"},
                {"template_id": "max_401k"},
            ])
            assert result["success"] is True

    def test_extreme_custom_value(self):
        with patch("cpa_panel.services.scenario_service.ScenarioAdjustment"), \
             patch("cpa_panel.services.scenario_service.Scenario") as MockScenario:
            MockScenario.return_value = MagicMock()
            result = self.service._build_scenario({
                "name": "Extreme",
                "adjustments": [{"field": "income", "value": 999_999_999}],
            })
            assert result is not None

    def test_negative_adjustment_value(self):
        with patch("cpa_panel.services.scenario_service.ScenarioAdjustment"), \
             patch("cpa_panel.services.scenario_service.Scenario") as MockScenario:
            MockScenario.return_value = MagicMock()
            result = self.service._build_scenario({
                "name": "Negative",
                "adjustments": [{"field": "income", "value": -50000}],
            })
            assert result is not None

    def test_zero_adjustment_value(self):
        with patch("cpa_panel.services.scenario_service.ScenarioAdjustment"), \
             patch("cpa_panel.services.scenario_service.Scenario") as MockScenario:
            MockScenario.return_value = MagicMock()
            result = self.service._build_scenario({
                "name": "Zero",
                "adjustments": [{"field": "income", "value": 0}],
            })
            assert result is not None

    def test_filing_status_normalization(self):
        """Spaces and casing should be normalized."""
        rate1 = self.service._get_marginal_rate(80000, "Single")
        rate2 = self.service._get_marginal_rate(80000, "SINGLE")
        rate3 = self.service._get_marginal_rate(80000, "single")
        assert rate1 == rate2 == rate3
