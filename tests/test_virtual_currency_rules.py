"""
Tests for Virtual Currency Tax Rules.

Verifies the 75 virtual currency rules (VC001-VC075) are properly
defined and can be loaded by the tax rules engine.
"""

import pytest
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestVirtualCurrencyRulesImport:
    """Tests for importing virtual currency rules."""

    def test_import_virtual_currency_rules(self):
        """Test that virtual currency rules can be imported."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES
        assert VIRTUAL_CURRENCY_RULES is not None
        assert isinstance(VIRTUAL_CURRENCY_RULES, list)

    def test_rule_count(self):
        """Test that we have 75 virtual currency rules."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES
        assert len(VIRTUAL_CURRENCY_RULES) == 75

    def test_rule_id_prefix(self):
        """Test that all rules have VC prefix."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES
        for rule in VIRTUAL_CURRENCY_RULES:
            assert rule.rule_id.startswith("VC"), f"Rule {rule.rule_id} doesn't start with VC"

    def test_rule_id_sequence(self):
        """Test that rule IDs are sequential from VC001 to VC075."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES
        expected_ids = [f"VC{str(i).zfill(3)}" for i in range(1, 76)]
        actual_ids = [rule.rule_id for rule in VIRTUAL_CURRENCY_RULES]
        assert actual_ids == expected_ids


class TestVirtualCurrencyRulesContent:
    """Tests for virtual currency rules content."""

    def test_all_rules_have_required_fields(self):
        """Test that all rules have required fields."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES
        for rule in VIRTUAL_CURRENCY_RULES:
            assert rule.rule_id, f"Rule missing rule_id"
            assert rule.name, f"Rule {rule.rule_id} missing name"
            assert rule.description, f"Rule {rule.rule_id} missing description"
            assert rule.category, f"Rule {rule.rule_id} missing category"
            assert rule.severity, f"Rule {rule.rule_id} missing severity"
            assert rule.irs_reference, f"Rule {rule.rule_id} missing irs_reference"

    def test_correct_category(self):
        """Test that all rules have VIRTUAL_CURRENCY category."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES
        from recommendation.tax_rules_engine import RuleCategory
        for rule in VIRTUAL_CURRENCY_RULES:
            assert rule.category == RuleCategory.VIRTUAL_CURRENCY

    def test_critical_rules_exist(self):
        """Test that critical virtual currency rules exist."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES
        rule_ids = [rule.rule_id for rule in VIRTUAL_CURRENCY_RULES]

        critical_rules = [
            "VC001",  # Property Classification
            "VC002",  # Disposal as Taxable Event
            "VC003",  # Crypto-to-Crypto Exchange
            "VC012",  # Form 8949 Requirement
            "VC014",  # Form 1040 Question
            "VC049",  # FBAR Requirement
        ]

        for critical in critical_rules:
            assert critical in rule_ids, f"Critical rule {critical} missing"

    def test_vc001_property_classification(self):
        """Test VC001 - Virtual Currency Property Classification."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES
        from recommendation.tax_rules_engine import RuleSeverity

        rule = next(r for r in VIRTUAL_CURRENCY_RULES if r.rule_id == "VC001")

        assert "property" in rule.description.lower()
        assert rule.severity == RuleSeverity.CRITICAL
        assert "Notice 2014-21" in rule.irs_reference

    def test_vc049_fbar_threshold(self):
        """Test VC049 - FBAR Foreign Exchange Reporting threshold."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES

        rule = next(r for r in VIRTUAL_CURRENCY_RULES if r.rule_id == "VC049")

        assert rule.threshold == 10000.0
        assert "FBAR" in rule.name

    def test_vc037_nft_collectible_rate(self):
        """Test VC037 - NFT Collectible Rate."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES

        rule = next(r for r in VIRTUAL_CURRENCY_RULES if r.rule_id == "VC037")

        assert rule.rate == 0.28
        assert "NFT" in rule.name or "collectible" in rule.description.lower()


class TestVirtualCurrencyRulesIntegration:
    """Integration tests with TaxRulesEngine."""

    def test_rules_load_in_engine(self):
        """Test that virtual currency rules load into the tax rules engine."""
        from recommendation.tax_rules_engine import TaxRulesEngine, RuleCategory

        engine = TaxRulesEngine()
        vc_rules = engine.get_rules_by_category(RuleCategory.VIRTUAL_CURRENCY)

        assert len(vc_rules) == 75

    def test_can_retrieve_rule_by_id(self):
        """Test that rules can be retrieved by ID."""
        from recommendation.tax_rules_engine import TaxRulesEngine

        engine = TaxRulesEngine()

        rule = engine.get_rule("VC001")
        assert rule is not None
        assert rule.name == "Virtual Currency Property Classification"

    def test_no_duplicate_rule_ids(self):
        """Test that there are no duplicate rule IDs."""
        from rules.virtual_currency_rules import VIRTUAL_CURRENCY_RULES

        rule_ids = [rule.rule_id for rule in VIRTUAL_CURRENCY_RULES]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs found"
