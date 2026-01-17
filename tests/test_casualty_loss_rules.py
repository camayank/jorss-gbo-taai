"""
Tests for Casualty and Disaster Loss Tax Rules.

Verifies the 59 casualty loss rules (CL001-CL059) are properly
defined and can be loaded by the tax rules engine.
"""

import pytest
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestCasualtyLossRulesImport:
    """Tests for importing casualty loss rules."""

    def test_import_casualty_loss_rules(self):
        """Test that casualty loss rules can be imported."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES
        assert CASUALTY_LOSS_RULES is not None
        assert isinstance(CASUALTY_LOSS_RULES, list)

    def test_rule_count(self):
        """Test that we have 59 casualty loss rules."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES
        assert len(CASUALTY_LOSS_RULES) == 59

    def test_rule_id_prefix(self):
        """Test that all rules have CL prefix."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES
        for rule in CASUALTY_LOSS_RULES:
            assert rule.rule_id.startswith("CL"), f"Rule {rule.rule_id} doesn't start with CL"

    def test_rule_id_sequence(self):
        """Test that rule IDs are sequential from CL001 to CL059."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES
        expected_ids = [f"CL{str(i).zfill(3)}" for i in range(1, 60)]
        actual_ids = [rule.rule_id for rule in CASUALTY_LOSS_RULES]
        assert actual_ids == expected_ids


class TestCasualtyLossRulesContent:
    """Tests for casualty loss rules content."""

    def test_all_rules_have_required_fields(self):
        """Test that all rules have required fields."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES
        for rule in CASUALTY_LOSS_RULES:
            assert rule.rule_id, f"Rule missing rule_id"
            assert rule.name, f"Rule {rule.rule_id} missing name"
            assert rule.description, f"Rule {rule.rule_id} missing description"
            assert rule.category, f"Rule {rule.rule_id} missing category"
            assert rule.severity, f"Rule {rule.rule_id} missing severity"
            assert rule.irs_reference, f"Rule {rule.rule_id} missing irs_reference"

    def test_correct_category(self):
        """Test that all rules have CASUALTY_LOSS category."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES
        from recommendation.tax_rules_engine import RuleCategory
        for rule in CASUALTY_LOSS_RULES:
            assert rule.category == RuleCategory.CASUALTY_LOSS

    def test_critical_rules_exist(self):
        """Test that critical casualty loss rules exist."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES
        rule_ids = [rule.rule_id for rule in CASUALTY_LOSS_RULES]

        critical_rules = [
            "CL001",  # Federally Declared Disaster Requirement
            "CL003",  # FEMA Declaration Required
            "CL014",  # Form 4684 Required
            "CL053",  # Insurance Claim Requirement
        ]

        for critical in critical_rules:
            assert critical in rule_ids, f"Critical rule {critical} missing"

    def test_cl001_disaster_requirement(self):
        """Test CL001 - Federally Declared Disaster Requirement."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES
        from recommendation.tax_rules_engine import RuleSeverity

        rule = next(r for r in CASUALTY_LOSS_RULES if r.rule_id == "CL001")

        assert "federally declared disaster" in rule.description.lower()
        assert rule.severity == RuleSeverity.CRITICAL

    def test_cl004_per_event_floor(self):
        """Test CL004 - $100 Per-Event Floor."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES

        rule = next(r for r in CASUALTY_LOSS_RULES if r.rule_id == "CL004")

        assert rule.threshold == 100.0
        assert "$100" in rule.name

    def test_cl005_agi_reduction(self):
        """Test CL005 - 10% AGI Reduction."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES

        rule = next(r for r in CASUALTY_LOSS_RULES if r.rule_id == "CL005")

        assert rule.rate == 0.10
        assert "10%" in rule.name or "10%" in rule.description


class TestCasualtyLossRulesIntegration:
    """Integration tests with TaxRulesEngine."""

    def test_rules_load_in_engine(self):
        """Test that casualty loss rules load into the tax rules engine."""
        from recommendation.tax_rules_engine import TaxRulesEngine, RuleCategory

        engine = TaxRulesEngine()
        cl_rules = engine.get_rules_by_category(RuleCategory.CASUALTY_LOSS)

        assert len(cl_rules) == 59

    def test_can_retrieve_rule_by_id(self):
        """Test that rules can be retrieved by ID."""
        from recommendation.tax_rules_engine import TaxRulesEngine

        engine = TaxRulesEngine()

        rule = engine.get_rule("CL001")
        assert rule is not None
        assert "Disaster" in rule.name

    def test_no_duplicate_rule_ids(self):
        """Test that there are no duplicate rule IDs."""
        from rules.casualty_loss_rules import CASUALTY_LOSS_RULES

        rule_ids = [rule.rule_id for rule in CASUALTY_LOSS_RULES]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs found"
