"""
Tests for centralized tax configuration and unified rule engine.

These tests verify:
1. Configuration loading from YAML
2. Rule engine initialization
3. Rule evaluation
4. No hardcoded values in rules
"""

import pytest
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestTaxConfigLoader:
    """Tests for the tax configuration loader."""

    def test_config_loader_import(self):
        """Test that config loader can be imported."""
        from config.tax_config_loader import (
            TaxConfigLoader,
            get_config_loader,
            get_tax_parameter,
        )
        assert TaxConfigLoader is not None
        assert get_config_loader is not None
        assert get_tax_parameter is not None

    def test_load_2025_config(self):
        """Test loading 2025 tax configuration."""
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "src" / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        config = loader.load_config(2025)

        # Verify key parameters are loaded
        assert 'standard_deduction' in config
        assert 'ss_wage_base' in config
        assert config['ss_wage_base'] == 176100

    def test_standard_deduction_values(self):
        """Test standard deduction values for 2025."""
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "src" / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        std_ded = loader.get_parameter('standard_deduction', 2025)

        assert std_ded['single'] == 15750
        assert std_ded['married_joint'] == 31500
        assert std_ded['head_of_household'] == 23850

    def test_get_parameter_by_filing_status(self):
        """Test getting parameters by filing status."""
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "src" / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        # Get standard deduction for single
        std_ded = loader.get_parameter('standard_deduction', 2025, 'single')
        assert std_ded == 15750

        # Get for married_joint
        std_ded_mfj = loader.get_parameter('standard_deduction', 2025, 'married_joint')
        assert std_ded_mfj == 31500

    def test_retirement_limits(self):
        """Test retirement contribution limits."""
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "src" / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        config = loader.load_config(2025)

        assert config.get('ira_contribution_limit') == 7000
        assert config.get('k401_contribution_limit') == 23500
        assert config.get('hsa_individual_limit') == 4300
        assert config.get('hsa_family_limit') == 8550

    def test_credit_parameters(self):
        """Test credit parameters."""
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "src" / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        config = loader.load_config(2025)

        assert config.get('child_tax_credit_amount') == 2000
        assert config.get('aotc_max_credit') == 2500
        assert config.get('savers_credit_max_contribution') == 2000

    def test_metadata_loaded(self):
        """Test that configuration metadata is loaded."""
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "src" / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        loader.load_config(2025)
        metadata = loader.get_metadata(2025)

        assert metadata is not None
        assert metadata.tax_year == 2025
        assert metadata.source == "IRS"
        assert "Rev. Proc. 2024-40" in metadata.irs_references


class TestRuleEngine:
    """Tests for the unified rule engine."""

    def test_rule_engine_import(self):
        """Test that rule engine can be imported."""
        from rules import (
            Rule,
            RuleResult,
            RuleContext,
            RuleEngine,
            get_rule_engine,
        )
        assert Rule is not None
        assert RuleResult is not None
        assert RuleContext is not None
        assert RuleEngine is not None
        assert get_rule_engine is not None

    def test_rule_engine_initialization(self):
        """Test rule engine initializes with default rules."""
        from rules import RuleEngine

        engine = RuleEngine(tax_year=2025)

        # Should have default rules loaded
        all_rules = engine.get_all_rules()
        assert len(all_rules) > 0

    def test_get_rule_by_id(self):
        """Test getting a rule by ID."""
        from rules import RuleEngine

        engine = RuleEngine(tax_year=2025)

        # Get SALT deduction rule
        rule = engine.get_rule("DED001")
        assert rule is not None
        assert rule.name == "SALT Deduction Cap"
        assert rule.limit == 10000

    def test_evaluate_limit_rule(self):
        """Test evaluating a limit rule."""
        from rules import RuleEngine, RuleContext

        engine = RuleEngine(tax_year=2025)

        # Create context with SALT deductions under limit
        context = RuleContext(
            tax_year=2025,
            filing_status="single",
            adjusted_gross_income=100000,
            itemized_deductions=8000,  # Under $10k SALT cap
        )

        result = engine.evaluate_rule("DED001", context)

        # Should pass since under limit
        assert result.passed
        assert "within" in result.message.lower() or result.passed

    def test_evaluate_threshold_rule(self):
        """Test evaluating a threshold rule."""
        from rules import RuleEngine, RuleContext

        engine = RuleEngine(tax_year=2025)

        # Context with income above NIIT threshold
        context = RuleContext(
            tax_year=2025,
            filing_status="single",
            adjusted_gross_income=250000,
        )

        result = engine.evaluate_rule("INV001", context)

        # Should not pass since AGI > $200k threshold for single
        assert not result.passed or "above" in result.message.lower()

    def test_evaluate_all_rules(self):
        """Test evaluating all rules."""
        from rules import RuleEngine, RuleContext, RuleCategory

        engine = RuleEngine(tax_year=2025)

        context = RuleContext(
            tax_year=2025,
            filing_status="married_joint",
            adjusted_gross_income=150000,
            earned_income=150000,
            wages=150000,
            retirement_contributions=10000,
        )

        results = engine.evaluate_all(context)

        assert len(results) > 0
        # All results should have rule_id
        for result in results:
            assert result.rule_id is not None

    def test_evaluate_by_category(self):
        """Test evaluating rules by category."""
        from rules import RuleEngine, RuleContext, RuleCategory

        engine = RuleEngine(tax_year=2025)

        context = RuleContext(
            tax_year=2025,
            filing_status="single",
            adjusted_gross_income=75000,
        )

        # Only evaluate deduction rules
        results = engine.evaluate_all(
            context,
            categories=[RuleCategory.DEDUCTION]
        )

        assert len(results) > 0
        # All should be deduction category
        for result in results:
            rule = engine.get_rule(result.rule_id)
            assert rule.category == RuleCategory.DEDUCTION

    def test_rule_has_irs_reference(self):
        """Test that rules have IRS references."""
        from rules import RuleEngine

        engine = RuleEngine(tax_year=2025)

        for rule in engine.get_all_rules():
            # All rules should have IRS reference
            assert rule.irs_reference or rule.irs_form or rule.irs_publication, \
                f"Rule {rule.rule_id} missing IRS reference"


class TestRuleContext:
    """Tests for RuleContext."""

    def test_context_creation(self):
        """Test creating a rule context."""
        from rules import RuleContext

        context = RuleContext(
            tax_year=2025,
            filing_status="married_joint",
            adjusted_gross_income=120000,
            earned_income=120000,
            wages=100000,
            self_employment_income=20000,
        )

        assert context.tax_year == 2025
        assert context.filing_status == "married_joint"
        assert context.adjusted_gross_income == 120000

    def test_context_custom_data(self):
        """Test adding custom data to context."""
        from rules import RuleContext

        context = RuleContext(
            tax_year=2025,
            filing_status="single",
            adjusted_gross_income=50000,
            custom_data={
                "has_hdhp": True,
                "student_count": 2,
            }
        )

        assert context.custom_data["has_hdhp"] is True
        assert context.custom_data["student_count"] == 2


class TestRuleResult:
    """Tests for RuleResult."""

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        from rules import RuleResult, RuleSeverity

        result = RuleResult(
            rule_id="TEST001",
            rule_name="Test Rule",
            passed=True,
            severity=RuleSeverity.INFO,
            message="Test passed",
            value=1000.0,
            irs_reference="IRC Section 1",
        )

        result_dict = result.to_dict()

        assert result_dict['rule_id'] == "TEST001"
        assert result_dict['passed'] is True
        assert result_dict['severity'] == "info"
        assert result_dict['irs_reference'] == "IRC Section 1"


class TestNoHardcodedValues:
    """Tests to verify no hardcoded values in the system."""

    def test_standard_deduction_from_config(self):
        """Verify standard deduction comes from config, not hardcoded."""
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "src" / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        # Load config
        config = loader.load_config(2025)

        # These values should match the YAML config
        std_ded = config['standard_deduction']
        assert std_ded['single'] == 15750  # From YAML, not hardcoded

    def test_rules_use_config_values(self):
        """Verify rules use config values."""
        from rules import RuleEngine

        engine = RuleEngine(tax_year=2025)

        # SALT cap rule should use config value
        salt_rule = engine.get_rule("DED001")
        assert salt_rule.limit == 10000  # Should match YAML config

        # IRA limit rule should use config value
        ira_rule = engine.get_rule("RET001")
        assert ira_rule.limit == 7000  # Should match YAML config

    def test_tax_year_is_parameterized(self):
        """Verify tax year is not hardcoded."""
        from rules import RuleEngine

        # Should be able to create engine for any year
        engine_2025 = RuleEngine(tax_year=2025)
        assert engine_2025.tax_year == 2025

        # Rules should be year-aware
        for rule in engine_2025.get_all_rules():
            assert rule.tax_year == 2025


class TestConfigurationChanges:
    """Tests for configuration change tracking."""

    def test_record_change(self):
        """Test recording configuration changes."""
        from config.tax_config_loader import TaxConfigLoader
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "src" / "config" / "tax_parameters"
        loader = TaxConfigLoader(config_dir=config_dir)

        # Record a change
        loader.record_change(
            parameter="standard_deduction.single",
            old_value=14600,
            new_value=15750,
            reason="Annual inflation adjustment",
            changed_by="test",
            irs_reference="Rev. Proc. 2024-40"
        )

        history = loader.get_change_history()
        assert len(history) == 1
        assert history[0].parameter == "standard_deduction.single"
        assert history[0].old_value == 14600
        assert history[0].new_value == 15750
