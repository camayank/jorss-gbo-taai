"""
Tests for K-1, Trust, and Estate Tax Rules.

Verifies the 60 K-1/Trust rules (K1001-K1060) are properly
defined and can be loaded by the tax rules engine.
"""

import pytest
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestK1TrustRulesImport:
    """Tests for importing K-1/Trust rules."""

    def test_import_k1_trust_rules(self):
        """Test that K-1/Trust rules can be imported."""
        from rules.k1_trust_rules import K1_TRUST_RULES
        assert K1_TRUST_RULES is not None
        assert isinstance(K1_TRUST_RULES, list)

    def test_rule_count(self):
        """Test that we have 60 K-1/Trust rules."""
        from rules.k1_trust_rules import K1_TRUST_RULES
        assert len(K1_TRUST_RULES) == 60

    def test_rule_id_prefix(self):
        """Test that all rules have K1 prefix."""
        from rules.k1_trust_rules import K1_TRUST_RULES
        for rule in K1_TRUST_RULES:
            assert rule.rule_id.startswith("K1"), f"Rule {rule.rule_id} doesn't start with K1"

    def test_rule_id_sequence(self):
        """Test that rule IDs are sequential from K1001 to K1060."""
        from rules.k1_trust_rules import K1_TRUST_RULES
        expected_ids = [f"K1{str(i).zfill(3)}" for i in range(1, 61)]
        actual_ids = [rule.rule_id for rule in K1_TRUST_RULES]
        assert actual_ids == expected_ids


class TestK1TrustRulesContent:
    """Tests for K-1/Trust rules content."""

    def test_all_rules_have_required_fields(self):
        """Test that all rules have required fields."""
        from rules.k1_trust_rules import K1_TRUST_RULES
        for rule in K1_TRUST_RULES:
            assert rule.rule_id, f"Rule missing rule_id"
            assert rule.name, f"Rule {rule.rule_id} missing name"
            assert rule.description, f"Rule {rule.rule_id} missing description"
            assert rule.category, f"Rule {rule.rule_id} missing category"
            assert rule.severity, f"Rule {rule.rule_id} missing severity"
            assert rule.irs_reference, f"Rule {rule.rule_id} missing irs_reference"

    def test_correct_category(self):
        """Test that all rules have K1_TRUST category."""
        from rules.k1_trust_rules import K1_TRUST_RULES
        from recommendation.tax_rules_engine import RuleCategory
        for rule in K1_TRUST_RULES:
            assert rule.category == RuleCategory.K1_TRUST

    def test_critical_rules_exist(self):
        """Test that critical K-1/Trust rules exist."""
        from rules.k1_trust_rules import K1_TRUST_RULES
        rule_ids = [rule.rule_id for rule in K1_TRUST_RULES]

        critical_rules = [
            "K1001",  # K-1 Partnership Form 1065
            "K1002",  # K-1 S-Corp Form 1120-S
            "K1029",  # Passive Loss Limitation
            "K1051",  # QBI Deduction 20%
        ]

        for critical in critical_rules:
            assert critical in rule_ids, f"Critical rule {critical} missing"

    def test_k1022_material_participation(self):
        """Test K1022 - Material Participation 500 Hour Test."""
        from rules.k1_trust_rules import K1_TRUST_RULES
        from recommendation.tax_rules_engine import RuleSeverity

        rule = next(r for r in K1_TRUST_RULES if r.rule_id == "K1022")

        assert rule.threshold == 500.0
        assert "material participation" in rule.name.lower()
        assert rule.severity == RuleSeverity.HIGH

    def test_k1030_rental_allowance(self):
        """Test K1030 - $25,000 Rental Real Estate Allowance."""
        from rules.k1_trust_rules import K1_TRUST_RULES

        rule = next(r for r in K1_TRUST_RULES if r.rule_id == "K1030")

        assert rule.limit == 25000.0
        assert rule.thresholds_by_status["single"] == 100000.0

    def test_k1051_qbi_rate(self):
        """Test K1051 - QBI Deduction 20%."""
        from rules.k1_trust_rules import K1_TRUST_RULES

        rule = next(r for r in K1_TRUST_RULES if r.rule_id == "K1051")

        assert rule.rate == 0.20
        assert "QBI" in rule.name


class TestK1TrustRulesIntegration:
    """Integration tests with TaxRulesEngine."""

    def test_rules_load_in_engine(self):
        """Test that K-1/Trust rules load into the tax rules engine."""
        from recommendation.tax_rules_engine import TaxRulesEngine, RuleCategory

        engine = TaxRulesEngine()
        k1_rules = engine.get_rules_by_category(RuleCategory.K1_TRUST)

        assert len(k1_rules) == 60

    def test_can_retrieve_rule_by_id(self):
        """Test that rules can be retrieved by ID."""
        from recommendation.tax_rules_engine import TaxRulesEngine

        engine = TaxRulesEngine()

        rule = engine.get_rule("K1001")
        assert rule is not None
        assert "K-1" in rule.name

    def test_no_duplicate_rule_ids(self):
        """Test that there are no duplicate rule IDs."""
        from rules.k1_trust_rules import K1_TRUST_RULES

        rule_ids = [rule.rule_id for rule in K1_TRUST_RULES]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs found"
