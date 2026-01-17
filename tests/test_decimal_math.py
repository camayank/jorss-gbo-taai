"""
Tests for Decimal Math Utilities.

Prompt 2: Deterministic Calculation - Verify same inputs always produce same outputs.

Tests verify:
1. Decimal precision eliminates floating point errors
2. Tax bracket calculations are deterministic
3. Money rounding follows IRS rules
4. Progressive tax calculations are accurate
"""

import pytest
from decimal import Decimal, InvalidOperation
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestDecimalConversion:
    """Tests for value conversion to Decimal."""

    def test_import(self):
        """Test module can be imported."""
        from calculator.decimal_math import (
            to_decimal, money, rate, add, subtract,
            multiply, divide, calculate_progressive_tax
        )
        assert to_decimal is not None

    def test_to_decimal_from_int(self):
        """Test converting integer to Decimal."""
        from calculator.decimal_math import to_decimal
        result = to_decimal(100)
        assert result == Decimal("100")
        assert isinstance(result, Decimal)

    def test_to_decimal_from_float(self):
        """Test converting float to Decimal preserves representation."""
        from calculator.decimal_math import to_decimal
        result = to_decimal(100.50)
        assert result == Decimal("100.5")

    def test_to_decimal_from_string(self):
        """Test converting string to Decimal."""
        from calculator.decimal_math import to_decimal
        result = to_decimal("100.50")
        assert result == Decimal("100.50")

    def test_to_decimal_from_decimal(self):
        """Test Decimal passes through unchanged."""
        from calculator.decimal_math import to_decimal
        original = Decimal("100.50")
        result = to_decimal(original)
        assert result is original


class TestMoneyRounding:
    """Tests for money rounding functions."""

    def test_money_rounds_half_up(self):
        """Test money() rounds to pennies using half-up."""
        from calculator.decimal_math import money
        assert money(100.994) == Decimal("100.99")
        assert money(100.995) == Decimal("101.00")
        assert money(100.996) == Decimal("101.00")

    def test_money_down_truncates(self):
        """Test money_down() truncates to pennies."""
        from calculator.decimal_math import money_down
        assert money_down(100.999) == Decimal("100.99")
        assert money_down(100.991) == Decimal("100.99")

    def test_money_up_rounds_up(self):
        """Test money_up() always rounds up."""
        from calculator.decimal_math import money_up
        assert money_up(100.001) == Decimal("100.01")
        assert money_up(100.009) == Decimal("100.01")

    def test_rate_precision(self):
        """Test rate() maintains 4 decimal places."""
        from calculator.decimal_math import rate
        assert rate(0.22) == Decimal("0.2200")
        assert rate(0.1234567) == Decimal("0.1235")


class TestArithmetic:
    """Tests for Decimal arithmetic operations."""

    def test_add_multiple_values(self):
        """Test adding multiple values."""
        from calculator.decimal_math import add
        result = add(100.10, 200.20, 300.30)
        assert result == Decimal("600.60")

    def test_add_avoids_float_error(self):
        """Test that add() avoids classic floating point error."""
        from calculator.decimal_math import add
        # Classic float: 0.1 + 0.2 = 0.30000000000000004
        result = add(0.1, 0.2)
        assert result == Decimal("0.3")

    def test_subtract(self):
        """Test subtraction."""
        from calculator.decimal_math import subtract
        result = subtract(100.50, 25.25)
        assert result == Decimal("75.25")

    def test_multiply(self):
        """Test multiplication."""
        from calculator.decimal_math import multiply
        result = multiply(100, 0.22)
        assert result == Decimal("22.00")

    def test_divide(self):
        """Test division."""
        from calculator.decimal_math import divide
        result = divide(100, 4)
        assert result == Decimal("25")

    def test_divide_by_zero_with_default(self):
        """Test division by zero returns default."""
        from calculator.decimal_math import divide
        result = divide(100, 0, default=0)
        assert result == Decimal("0")

    def test_divide_by_zero_raises(self):
        """Test division by zero raises without default."""
        from calculator.decimal_math import divide
        with pytest.raises(InvalidOperation):
            divide(100, 0)

    def test_percent(self):
        """Test percentage calculation."""
        from calculator.decimal_math import percent
        result = percent(1000, 0.22)
        assert result == Decimal("220")

    def test_percent_of(self):
        """Test calculating what percentage."""
        from calculator.decimal_math import percent_of
        result = percent_of(50, 100)
        assert result == Decimal("0.5")


class TestMinMaxClamp:
    """Tests for min/max/clamp functions."""

    def test_min_decimal(self):
        """Test finding minimum."""
        from calculator.decimal_math import min_decimal
        result = min_decimal(100, 50, 75)
        assert result == Decimal("50")

    def test_max_decimal(self):
        """Test finding maximum."""
        from calculator.decimal_math import max_decimal
        result = max_decimal(100, 50, 75)
        assert result == Decimal("100")

    def test_clamp_within_range(self):
        """Test clamp with value in range."""
        from calculator.decimal_math import clamp
        result = clamp(50, 0, 100)
        assert result == Decimal("50")

    def test_clamp_below_minimum(self):
        """Test clamp with value below minimum."""
        from calculator.decimal_math import clamp
        result = clamp(-50, 0, 100)
        assert result == Decimal("0")

    def test_clamp_above_maximum(self):
        """Test clamp with value above maximum."""
        from calculator.decimal_math import clamp
        result = clamp(150, 0, 100)
        assert result == Decimal("100")

    def test_sum_money(self):
        """Test summing money values."""
        from calculator.decimal_math import sum_money
        result = sum_money([100.10, 200.20, 300.305])
        assert result == Decimal("600.61")


class TestTaxBracketCalculations:
    """Tests for tax bracket calculations."""

    def test_calculate_tax_in_bracket_below(self):
        """Test tax when income below bracket."""
        from calculator.decimal_math import calculate_tax_in_bracket
        result = calculate_tax_in_bracket(
            income=40000,
            bracket_start=47150,
            bracket_end=100525,
            rate_value=0.22
        )
        assert result == Decimal("0")

    def test_calculate_tax_in_bracket_partial(self):
        """Test tax when income partially in bracket."""
        from calculator.decimal_math import calculate_tax_in_bracket
        result = calculate_tax_in_bracket(
            income=75000,
            bracket_start=47150,
            bracket_end=100525,
            rate_value=0.22
        )
        # (75000 - 47150) * 0.22 = 27850 * 0.22 = 6127
        assert result == Decimal("6127.00")

    def test_calculate_tax_in_bracket_full(self):
        """Test tax when income exceeds bracket."""
        from calculator.decimal_math import calculate_tax_in_bracket
        result = calculate_tax_in_bracket(
            income=150000,
            bracket_start=47150,
            bracket_end=100525,
            rate_value=0.22
        )
        # (100525 - 47150) * 0.22 = 53375 * 0.22 = 11742.50
        assert result == Decimal("11742.50")


class TestProgressiveTax:
    """Tests for progressive tax calculation."""

    def test_progressive_tax_single_bracket(self):
        """Test progressive tax in first bracket only."""
        from calculator.decimal_math import calculate_progressive_tax
        brackets = [
            (11600, 0.10),
            (47150, 0.12),
            (100525, 0.22),
        ]
        result = calculate_progressive_tax(10000, brackets)
        # 10000 * 0.10 = 1000
        assert result == Decimal("1000.00")

    def test_progressive_tax_multiple_brackets(self):
        """Test progressive tax spanning multiple brackets."""
        from calculator.decimal_math import calculate_progressive_tax
        brackets = [
            (11600, 0.10),
            (47150, 0.12),
            (100525, 0.22),
            (191950, 0.24),
        ]
        result = calculate_progressive_tax(75000, brackets)
        # 11600 * 0.10 = 1160
        # (47150 - 11600) * 0.12 = 35550 * 0.12 = 4266
        # (75000 - 47150) * 0.22 = 27850 * 0.22 = 6127
        # Total = 1160 + 4266 + 6127 = 11553
        assert result == Decimal("11553.00")

    def test_progressive_tax_determinism(self):
        """Test that progressive tax is deterministic."""
        from calculator.decimal_math import calculate_progressive_tax
        brackets = [
            (11600, 0.10),
            (47150, 0.12),
            (100525, 0.22),
            (191950, 0.24),
        ]
        results = [calculate_progressive_tax(75000, brackets) for _ in range(100)]
        assert all(r == results[0] for r in results)

    def test_progressive_tax_edge_at_bracket_boundary(self):
        """Test progressive tax exactly at bracket boundary."""
        from calculator.decimal_math import calculate_progressive_tax
        brackets = [
            (11600, 0.10),
            (47150, 0.12),
        ]
        result = calculate_progressive_tax(47150, brackets)
        # 11600 * 0.10 = 1160
        # (47150 - 11600) * 0.12 = 35550 * 0.12 = 4266
        # Total = 1160 + 4266 = 5426
        assert result == Decimal("5426.00")


class TestSelfEmploymentTax:
    """Tests for self-employment tax calculation."""

    def test_self_employment_tax_calculation(self):
        """Test SE tax calculation."""
        from calculator.decimal_math import calculate_self_employment_tax
        result = calculate_self_employment_tax(100000)

        assert "net_self_employment" in result
        assert "se_earnings" in result
        assert "ss_tax" in result
        assert "medicare_tax" in result
        assert "total_se_tax" in result
        assert "se_deduction" in result

        # SE earnings = 100000 * 0.9235 = 92350
        assert result["se_earnings"] == 92350.0

    def test_self_employment_tax_determinism(self):
        """Test SE tax is deterministic."""
        from calculator.decimal_math import calculate_self_employment_tax
        results = [calculate_self_employment_tax(100000) for _ in range(100)]
        assert all(r == results[0] for r in results)


class TestFormatting:
    """Tests for formatting functions."""

    def test_format_money(self):
        """Test money formatting."""
        from calculator.decimal_math import format_money
        assert format_money(1234567.89) == "$1,234,567.89"
        assert format_money(100) == "$100.00"

    def test_format_percentage(self):
        """Test percentage formatting."""
        from calculator.decimal_math import format_percentage
        assert format_percentage(0.22) == "22.00%"
        assert format_percentage(0.2245, decimal_places=2) == "22.45%"

    def test_to_float(self):
        """Test converting Decimal back to float."""
        from calculator.decimal_math import to_float
        result = to_float(Decimal("100.50"))
        assert result == 100.50
        assert isinstance(result, float)


class TestSafeOperations:
    """Tests for safe division and edge cases."""

    def test_safe_divide_for_rate(self):
        """Test safe division for rate calculation."""
        from calculator.decimal_math import safe_divide_for_rate
        result = safe_divide_for_rate(25, 100)
        assert result == Decimal("0.2500")

    def test_safe_divide_for_rate_zero_denominator(self):
        """Test safe division with zero denominator."""
        from calculator.decimal_math import safe_divide_for_rate
        result = safe_divide_for_rate(25, 0)
        assert result == Decimal("0.0000")


class TestConstants:
    """Tests for tax constants."""

    def test_constants_defined(self):
        """Test that constants are defined correctly."""
        from calculator.decimal_math import (
            ZERO, ONE, HUNDRED,
            SE_NET_EARNINGS_FACTOR, SS_RATE, MEDICARE_RATE,
            ADDITIONAL_MEDICARE_RATE, NIIT_RATE
        )
        assert ZERO == Decimal("0")
        assert ONE == Decimal("1")
        assert HUNDRED == Decimal("100")
        assert SE_NET_EARNINGS_FACTOR == Decimal("0.9235")
        assert SS_RATE == Decimal("0.124")
        assert MEDICARE_RATE == Decimal("0.029")
        assert ADDITIONAL_MEDICARE_RATE == Decimal("0.009")
        assert NIIT_RATE == Decimal("0.038")
