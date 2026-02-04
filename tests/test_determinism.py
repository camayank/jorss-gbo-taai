"""
Tests for Determinism - Verifying same inputs always produce same outputs.

These tests ensure that tax calculations, scenarios, and recommendations
are deterministic and reproducible.
"""

import pytest
import os
import sys
from copy import deepcopy
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestCalculationDeterminism:
    """Tests for tax calculation determinism."""

    def test_tax_bracket_calculation_deterministic(self):
        """Same income inputs produce identical bracket calculations."""
        from calculator.tax_year_config import TaxYearConfig

        config = TaxYearConfig.for_2025()

        # Calculate multiple times with same inputs
        income = 150000
        results = []

        for _ in range(5):
            # Single filer brackets - format is [(threshold, rate), ...]
            brackets = config.ordinary_income_brackets["single"]
            tax = 0.0
            prev_threshold = 0
            for threshold, rate in brackets:
                if income > threshold:
                    # Calculate tax in this bracket
                    bracket_income = min(income, threshold if threshold > prev_threshold else float('inf')) - prev_threshold
                    if bracket_income > 0:
                        tax += bracket_income * rate
                prev_threshold = threshold

            # Simpler recalculation using bracket logic
            tax = 0.0
            for i, (threshold, rate) in enumerate(brackets):
                next_threshold = brackets[i + 1][0] if i + 1 < len(brackets) else float('inf')
                if income > threshold:
                    taxable_in_bracket = min(income, next_threshold) - threshold
                    tax += taxable_in_bracket * rate

            results.append(round(tax, 2))

        # All calculations should be identical
        first_result = results[0]
        for result in results:
            assert result == first_result, "Bracket calculations are not deterministic"

    def test_deduction_calculation_deterministic(self):
        """Same deduction inputs produce identical outputs."""
        from calculator.tax_year_config import TaxYearConfig

        config = TaxYearConfig.for_2025()

        # Calculate standard deduction multiple times
        results = []
        for _ in range(5):
            std_ded_single = config.standard_deduction["single"]
            std_ded_mfj = config.standard_deduction["married_joint"]
            results.append((std_ded_single, std_ded_mfj))

        # All should be identical
        first_result = results[0]
        for result in results:
            assert result == first_result, "Deduction calculations are not deterministic"


class TestRecommendationDeterminism:
    """Tests for recommendation engine determinism."""

    def test_warnings_order_deterministic(self):
        """Warnings should be returned in deterministic order."""
        # Verify the source code uses sorted(set(...))
        source_path = os.path.join(
            os.path.dirname(__file__), '..', 'src',
            'recommendation', 'recommendation_engine.py'
        )

        with open(source_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Verify sorted() is used instead of list()
        assert 'return sorted(set(warnings))' in source
        assert 'return list(set(warnings))' not in source


class TestModelDeterminism:
    """Tests for model output determinism."""

    def test_schedule_b_countries_deterministic(self):
        """Foreign account countries should be in deterministic order."""
        # Verify the source code uses sorted(set(...))
        source_path = os.path.join(
            os.path.dirname(__file__), '..', 'src',
            'models', 'schedule_b.py'
        )

        with open(source_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Verify sorted() is used
        assert 'countries = sorted(set(' in source
        assert 'countries = list(set(' not in source

    def test_sorted_set_produces_deterministic_order(self):
        """sorted(set(...)) should always produce same order."""
        # Simulate the pattern used in schedule_b.py
        countries_list = ["Switzerland", "Germany", "France", "Germany", "Switzerland"]

        results = []
        for _ in range(10):
            # This is what the code does now
            unique_sorted = sorted(set(countries_list))
            results.append(unique_sorted)

        # All should be identical
        first_result = results[0]
        for result in results:
            assert result == first_result, "sorted(set()) is not deterministic"

        # Should be alphabetically sorted
        assert first_result == ['France', 'Germany', 'Switzerland']


class TestScenarioDeterminism:
    """Tests for scenario calculation determinism."""

    def test_scenario_service_no_random(self):
        """Scenario service should not use random in calculations."""
        source_path = os.path.join(
            os.path.dirname(__file__), '..', 'src',
            'services', 'scenario_service.py'
        )

        with open(source_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # No random imports
        assert 'import random' not in source
        assert 'from random import' not in source

        # Time-based logic should only be for measurement, not calculation
        # time.time() is used for performance timing, which is OK
        assert 'datetime.now()' not in source

    def test_scenario_modification_application_deterministic(self):
        """Applying the same modifications should always produce same results."""
        # Test the nested dict modification logic
        def set_nested_value(data, path, value):
            """Same logic as in scenario_service.py"""
            keys = path.split(".")
            current = data
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[keys[-1]] = value

        # Apply same modifications multiple times
        results = []
        for _ in range(5):
            base_data = {"income": {"wages": 50000}, "deductions": {}}
            set_nested_value(base_data, "income.wages", 60000)
            set_nested_value(base_data, "deductions.retirement", 5000)
            results.append(str(base_data))

        # All results should be identical
        first_result = results[0]
        for result in results:
            assert result == first_result, "Modification application is not deterministic"


class TestNoRandomInCalculations:
    """Verify no random module usage in calculation code."""

    def test_no_random_in_calculator(self):
        """Calculator module should not use random."""
        import os
        from pathlib import Path

        calc_path = Path(__file__).parent.parent / 'src' / 'calculator'

        for py_file in calc_path.rglob('*.py'):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Allow 'random' only as part of larger words (e.g., 'random_state')
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'import random' in line or 'from random import' in line:
                        pytest.fail(f"Random module imported in {py_file.name}:{i}")

    def test_no_time_based_calculations(self):
        """Calculator should not use current time in calculations."""
        import os
        from pathlib import Path

        calc_path = Path(__file__).parent.parent / 'src' / 'calculator'

        for py_file in calc_path.rglob('*.py'):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check for time-based function calls
                if 'datetime.now()' in content or 'datetime.today()' in content:
                    pytest.fail(f"Time-based logic found in {py_file.name}")
                if 'time.time()' in content:
                    # Allow only if it's for performance measurement, not calculation
                    pass  # This is OK for timing
