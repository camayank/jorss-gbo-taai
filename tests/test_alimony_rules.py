"""
Tests for Alimony Tax Rules.

Verifies the 68 alimony rules (AL001-AL068) are properly
defined and can be loaded by the tax rules engine.
"""

import pytest
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestAlimonyRulesImport:
    """Tests for importing alimony rules."""

    def test_import_alimony_rules(self):
        """Test that alimony rules can be imported."""
        from rules.alimony_rules import ALIMONY_RULES
        assert ALIMONY_RULES is not None
        assert isinstance(ALIMONY_RULES, list)

    def test_rule_count(self):
        """Test that we have 68 alimony rules."""
        from rules.alimony_rules import ALIMONY_RULES
        assert len(ALIMONY_RULES) == 68

    def test_rule_id_prefix(self):
        """Test that all rules have AL prefix."""
        from rules.alimony_rules import ALIMONY_RULES
        for rule in ALIMONY_RULES:
            assert rule.rule_id.startswith("AL"), f"Rule {rule.rule_id} doesn't start with AL"

    def test_rule_id_sequence(self):
        """Test that rule IDs are sequential from AL001 to AL068."""
        from rules.alimony_rules import ALIMONY_RULES
        expected_ids = [f"AL{str(i).zfill(3)}" for i in range(1, 69)]
        actual_ids = [rule.rule_id for rule in ALIMONY_RULES]
        assert actual_ids == expected_ids


class TestAlimonyRulesContent:
    """Tests for alimony rules content."""

    def test_all_rules_have_required_fields(self):
        """Test that all rules have required fields."""
        from rules.alimony_rules import ALIMONY_RULES
        for rule in ALIMONY_RULES:
            assert rule.rule_id, f"Rule missing rule_id"
            assert rule.name, f"Rule {rule.rule_id} missing name"
            assert rule.description, f"Rule {rule.rule_id} missing description"
            assert rule.category, f"Rule {rule.rule_id} missing category"
            assert rule.severity, f"Rule {rule.rule_id} missing severity"
            assert rule.irs_reference, f"Rule {rule.rule_id} missing irs_reference"

    def test_correct_category(self):
        """Test that all rules have ALIMONY category."""
        from rules.alimony_rules import ALIMONY_RULES
        from recommendation.tax_rules_engine import RuleCategory
        for rule in ALIMONY_RULES:
            assert rule.category == RuleCategory.ALIMONY

    def test_critical_rules_exist(self):
        """Test that critical alimony rules exist."""
        from rules.alimony_rules import ALIMONY_RULES
        rule_ids = [rule.rule_id for rule in ALIMONY_RULES]

        critical_rules = [
            "AL025",  # Pre-2019 Instrument Identification
            "AL026",  # Post-2018 Not Deductible
            "AL027",  # Post-2018 Not Taxable
            "AL028",  # December 31, 2018 Cutoff
            "AL046",  # Child Support Not Deductible
        ]

        for critical in critical_rules:
            assert critical in rule_ids, f"Critical rule {critical} missing"

    def test_al001_pre2019_deductible(self):
        """Test AL001 - Pre-2019 Alimony Deductible."""
        from rules.alimony_rules import ALIMONY_RULES
        from recommendation.tax_rules_engine import RuleSeverity

        rule = next(r for r in ALIMONY_RULES if r.rule_id == "AL001")

        assert "pre-2019" in rule.description.lower() or "Pre-2019" in rule.name
        assert "deductible" in rule.description.lower()
        assert rule.severity == RuleSeverity.HIGH

    def test_al026_post2018_not_deductible(self):
        """Test AL026 - Post-2018 Alimony Not Deductible."""
        from rules.alimony_rules import ALIMONY_RULES
        from recommendation.tax_rules_engine import RuleSeverity

        rule = next(r for r in ALIMONY_RULES if r.rule_id == "AL026")

        assert "not deductible" in rule.description.lower()
        assert rule.severity == RuleSeverity.CRITICAL

    def test_al011_recapture_threshold(self):
        """Test AL011 - Recapture Calculation $15,000 threshold."""
        from rules.alimony_rules import ALIMONY_RULES

        rule = next(r for r in ALIMONY_RULES if r.rule_id == "AL011")

        assert rule.threshold == 15000.0
        assert "recapture" in rule.name.lower()


class TestAlimonyRulesIntegration:
    """Integration tests with TaxRulesEngine."""

    def test_rules_load_in_engine(self):
        """Test that alimony rules load into the tax rules engine."""
        from recommendation.tax_rules_engine import TaxRulesEngine, RuleCategory

        engine = TaxRulesEngine()
        al_rules = engine.get_rules_by_category(RuleCategory.ALIMONY)

        assert len(al_rules) == 68

    def test_can_retrieve_rule_by_id(self):
        """Test that rules can be retrieved by ID."""
        from recommendation.tax_rules_engine import TaxRulesEngine

        engine = TaxRulesEngine()

        rule = engine.get_rule("AL001")
        assert rule is not None
        assert "Alimony" in rule.name

    def test_no_duplicate_rule_ids(self):
        """Test that there are no duplicate rule IDs."""
        from rules.alimony_rules import ALIMONY_RULES

        rule_ids = [rule.rule_id for rule in ALIMONY_RULES]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs found"


class TestPreAndPost2018Rules:
    """Tests specifically for the pre-2019 vs post-2018 split."""

    def test_pre2019_rules_exist(self):
        """Test that pre-2019 rules (AL001-AL025) exist."""
        from rules.alimony_rules import ALIMONY_RULES
        rule_ids = [rule.rule_id for rule in ALIMONY_RULES]

        for i in range(1, 26):
            rule_id = f"AL{str(i).zfill(3)}"
            assert rule_id in rule_ids, f"Pre-2019 rule {rule_id} missing"

    def test_post2018_rules_exist(self):
        """Test that post-2018 rules (AL026-AL045) exist."""
        from rules.alimony_rules import ALIMONY_RULES
        rule_ids = [rule.rule_id for rule in ALIMONY_RULES]

        for i in range(26, 46):
            rule_id = f"AL{str(i).zfill(3)}"
            assert rule_id in rule_ids, f"Post-2018 rule {rule_id} missing"

    def test_child_support_rules_exist(self):
        """Test that child support rules (AL046-AL060) exist."""
        from rules.alimony_rules import ALIMONY_RULES
        rule_ids = [rule.rule_id for rule in ALIMONY_RULES]

        for i in range(46, 61):
            rule_id = f"AL{str(i).zfill(3)}"
            assert rule_id in rule_ids, f"Child support rule {rule_id} missing"
