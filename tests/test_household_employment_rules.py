"""
Tests for Household Employment Tax Rules.

Verifies the 55 household employment rules (HH001-HH055) are properly
defined and can be loaded by the tax rules engine.
"""

import pytest
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestHouseholdEmploymentRulesImport:
    """Tests for importing household employment rules."""

    def test_import_household_employment_rules(self):
        """Test that household employment rules can be imported."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES
        assert HOUSEHOLD_EMPLOYMENT_RULES is not None
        assert isinstance(HOUSEHOLD_EMPLOYMENT_RULES, list)

    def test_rule_count(self):
        """Test that we have 55 household employment rules."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES
        assert len(HOUSEHOLD_EMPLOYMENT_RULES) == 55

    def test_rule_id_prefix(self):
        """Test that all rules have HH prefix."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES
        for rule in HOUSEHOLD_EMPLOYMENT_RULES:
            assert rule.rule_id.startswith("HH"), f"Rule {rule.rule_id} doesn't start with HH"

    def test_rule_id_sequence(self):
        """Test that rule IDs are sequential from HH001 to HH055."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES
        expected_ids = [f"HH{str(i).zfill(3)}" for i in range(1, 56)]
        actual_ids = [rule.rule_id for rule in HOUSEHOLD_EMPLOYMENT_RULES]
        assert actual_ids == expected_ids


class TestHouseholdEmploymentRulesContent:
    """Tests for household employment rules content."""

    def test_all_rules_have_required_fields(self):
        """Test that all rules have required fields."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES
        for rule in HOUSEHOLD_EMPLOYMENT_RULES:
            assert rule.rule_id, f"Rule missing rule_id"
            assert rule.name, f"Rule {rule.rule_id} missing name"
            assert rule.description, f"Rule {rule.rule_id} missing description"
            assert rule.category, f"Rule {rule.rule_id} missing category"
            assert rule.severity, f"Rule {rule.rule_id} missing severity"
            assert rule.irs_reference, f"Rule {rule.rule_id} missing irs_reference"

    def test_correct_category(self):
        """Test that all rules have HOUSEHOLD_EMPLOYMENT category."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES
        from recommendation.tax_rules_engine import RuleCategory
        for rule in HOUSEHOLD_EMPLOYMENT_RULES:
            assert rule.category == RuleCategory.HOUSEHOLD_EMPLOYMENT

    def test_critical_rules_exist(self):
        """Test that critical household employment rules exist."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES
        rule_ids = [rule.rule_id for rule in HOUSEHOLD_EMPLOYMENT_RULES]

        critical_rules = [
            "HH001",  # Schedule H Filing Threshold
            "HH005",  # Form W-2 Issuance
            "HH009",  # Employee vs Contractor
        ]

        for critical in critical_rules:
            assert critical in rule_ids, f"Critical rule {critical} missing"

    def test_hh001_schedule_h_threshold(self):
        """Test HH001 - Schedule H Filing Threshold."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES
        from recommendation.tax_rules_engine import RuleSeverity

        rule = next(r for r in HOUSEHOLD_EMPLOYMENT_RULES if r.rule_id == "HH001")

        assert rule.threshold == 2700.0
        assert rule.severity == RuleSeverity.CRITICAL
        assert "Schedule H" in rule.name

    def test_hh016_social_security_rate(self):
        """Test HH016 - Social Security Tax Rate."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES

        rule = next(r for r in HOUSEHOLD_EMPLOYMENT_RULES if r.rule_id == "HH016")

        assert rule.rate == 0.124  # 12.4% total
        assert "Social Security" in rule.name

    def test_hh018_wage_base(self):
        """Test HH018 - Social Security Wage Base 2025."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES

        rule = next(r for r in HOUSEHOLD_EMPLOYMENT_RULES if r.rule_id == "HH018")

        assert rule.limit == 176100.0


class TestHouseholdEmploymentRulesIntegration:
    """Integration tests with TaxRulesEngine."""

    def test_rules_load_in_engine(self):
        """Test that household employment rules load into the tax rules engine."""
        from recommendation.tax_rules_engine import TaxRulesEngine, RuleCategory

        engine = TaxRulesEngine()
        hh_rules = engine.get_rules_by_category(RuleCategory.HOUSEHOLD_EMPLOYMENT)

        assert len(hh_rules) == 55

    def test_can_retrieve_rule_by_id(self):
        """Test that rules can be retrieved by ID."""
        from recommendation.tax_rules_engine import TaxRulesEngine

        engine = TaxRulesEngine()

        rule = engine.get_rule("HH001")
        assert rule is not None
        assert "Schedule H" in rule.name

    def test_no_duplicate_rule_ids(self):
        """Test that there are no duplicate rule IDs."""
        from rules.household_employment_rules import HOUSEHOLD_EMPLOYMENT_RULES

        rule_ids = [rule.rule_id for rule in HOUSEHOLD_EMPLOYMENT_RULES]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs found"
