"""
Tests for Foreign Assets Tax Rules.

Verifies the 64 foreign assets rules (FA001-FA064) are properly
defined and can be loaded by the tax rules engine.
"""

import pytest
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestForeignAssetsRulesImport:
    """Tests for importing foreign assets rules."""

    def test_import_foreign_assets_rules(self):
        """Test that foreign assets rules can be imported."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES
        assert FOREIGN_ASSETS_RULES is not None
        assert isinstance(FOREIGN_ASSETS_RULES, list)

    def test_rule_count(self):
        """Test that we have 64 foreign assets rules."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES
        assert len(FOREIGN_ASSETS_RULES) == 64

    def test_rule_id_prefix(self):
        """Test that all rules have FA prefix."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES
        for rule in FOREIGN_ASSETS_RULES:
            assert rule.rule_id.startswith("FA"), f"Rule {rule.rule_id} doesn't start with FA"

    def test_rule_id_sequence(self):
        """Test that rule IDs are sequential from FA001 to FA064."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES
        expected_ids = [f"FA{str(i).zfill(3)}" for i in range(1, 65)]
        actual_ids = [rule.rule_id for rule in FOREIGN_ASSETS_RULES]
        assert actual_ids == expected_ids


class TestForeignAssetsRulesContent:
    """Tests for foreign assets rules content."""

    def test_all_rules_have_required_fields(self):
        """Test that all rules have required fields."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES
        for rule in FOREIGN_ASSETS_RULES:
            assert rule.rule_id, f"Rule missing rule_id"
            assert rule.name, f"Rule {rule.rule_id} missing name"
            assert rule.description, f"Rule {rule.rule_id} missing description"
            assert rule.category, f"Rule {rule.rule_id} missing category"
            assert rule.severity, f"Rule {rule.rule_id} missing severity"
            assert rule.irs_reference, f"Rule {rule.rule_id} missing irs_reference"

    def test_correct_category(self):
        """Test that all rules have INTERNATIONAL category."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES
        from recommendation.tax_rules_engine import RuleCategory
        for rule in FOREIGN_ASSETS_RULES:
            assert rule.category == RuleCategory.INTERNATIONAL

    def test_critical_rules_exist(self):
        """Test that critical foreign assets rules exist."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES
        rule_ids = [rule.rule_id for rule in FOREIGN_ASSETS_RULES]

        critical_rules = [
            "FA001",  # FBAR Filing Requirement
            "FA002",  # FBAR Aggregate Threshold
            "FA016",  # Form 8938 Filing
            "FA026",  # Form 8938 Penalty
            "FA031",  # FTC Limitation
        ]

        for critical in critical_rules:
            assert critical in rule_ids, f"Critical rule {critical} missing"

    def test_fa001_fbar_requirement(self):
        """Test FA001 - FBAR Filing Requirement."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES
        from recommendation.tax_rules_engine import RuleSeverity

        rule = next(r for r in FOREIGN_ASSETS_RULES if r.rule_id == "FA001")

        assert "FBAR" in rule.name
        assert rule.threshold == 10000.0
        assert rule.severity == RuleSeverity.CRITICAL

    def test_fa017_fatca_thresholds(self):
        """Test FA017 - Form 8938 Filing Thresholds."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES

        rule = next(r for r in FOREIGN_ASSETS_RULES if r.rule_id == "FA017")

        assert rule.thresholds_by_status is not None
        assert rule.thresholds_by_status["single"] == 50000.0

    def test_fa040_simplified_method_threshold(self):
        """Test FA040 - Simplified Method Threshold."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES

        rule = next(r for r in FOREIGN_ASSETS_RULES if r.rule_id == "FA040")

        assert rule.thresholds_by_status["single"] == 300.0
        assert rule.thresholds_by_status["married_joint"] == 600.0


class TestForeignAssetsRulesIntegration:
    """Integration tests with TaxRulesEngine."""

    def test_rules_load_in_engine(self):
        """Test that foreign assets rules load into the tax rules engine."""
        from recommendation.tax_rules_engine import TaxRulesEngine, RuleCategory

        engine = TaxRulesEngine()
        # Foreign assets rules use INTERNATIONAL category
        intl_rules = engine.get_rules_by_category(RuleCategory.INTERNATIONAL)

        # Should have at least the 64 foreign assets rules plus any existing international rules
        assert len(intl_rules) >= 64

    def test_can_retrieve_rule_by_id(self):
        """Test that rules can be retrieved by ID."""
        from recommendation.tax_rules_engine import TaxRulesEngine

        engine = TaxRulesEngine()

        rule = engine.get_rule("FA001")
        assert rule is not None
        assert "FBAR" in rule.name

    def test_no_duplicate_rule_ids(self):
        """Test that there are no duplicate rule IDs."""
        from rules.foreign_assets_rules import FOREIGN_ASSETS_RULES

        rule_ids = [rule.rule_id for rule in FOREIGN_ASSETS_RULES]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs found"
