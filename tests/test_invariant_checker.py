"""Unit tests for the InvariantChecker runtime guards."""

import sys
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import math
import pytest
from unittest.mock import MagicMock

from validation.invariant_checker import InvariantChecker, InvariantViolation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tax_return(
    agi=50000,
    taxable_income=35000,
    tax_liability=5000,
    combined_tax_liability=5500,
    state_tax_liability=None,
    total_income=50000,
):
    """Create a mock TaxReturn with the given values."""
    tr = MagicMock()
    tr.adjusted_gross_income = agi
    tr.taxable_income = taxable_income
    tr.tax_liability = tax_liability
    tr.combined_tax_liability = combined_tax_liability
    tr.state_tax_liability = state_tax_liability

    income_mock = MagicMock()
    income_mock.get_total_income.return_value = total_income
    tr.income = income_mock

    return tr


# ---------------------------------------------------------------------------
# InvariantViolation
# ---------------------------------------------------------------------------

class TestInvariantViolation:

    def test_repr(self):
        v = InvariantViolation("TEST_CODE", "test message", "error")
        assert "TEST_CODE" in repr(v)
        assert "test message" in repr(v)

    def test_to_dict(self):
        v = InvariantViolation("CODE", "msg", "warning")
        d = v.to_dict()
        assert d == {"code": "CODE", "message": "msg", "severity": "warning"}


# ---------------------------------------------------------------------------
# InvariantChecker.check()
# ---------------------------------------------------------------------------

class TestInvariantCheckerCheck:

    def test_no_violations_for_valid_return(self):
        tr = _make_tax_return()
        violations = InvariantChecker.check(tr)
        assert violations == []

    def test_skips_uncalculated_return(self):
        tr = _make_tax_return(agi=None)
        violations = InvariantChecker.check(tr)
        assert violations == []

    def test_negative_taxable_income(self):
        tr = _make_tax_return(taxable_income=-1000)
        violations = InvariantChecker.check(tr)
        codes = [v.code for v in violations]
        assert "NEGATIVE_TAXABLE_INCOME" in codes

    def test_excessive_effective_rate(self):
        # tax > 56.1% of AGI
        tr = _make_tax_return(agi=100000, tax_liability=60000, total_income=100000)
        violations = InvariantChecker.check(tr)
        codes = [v.code for v in violations]
        assert "EXCESSIVE_EFFECTIVE_RATE" in codes

    def test_tax_exceeds_income(self):
        # tax > 110% of total income
        tr = _make_tax_return(
            agi=50000, tax_liability=60000, total_income=50000
        )
        violations = InvariantChecker.check(tr)
        codes = [v.code for v in violations]
        assert "TAX_EXCEEDS_INCOME" in codes

    def test_non_finite_agi(self):
        tr = _make_tax_return(agi=float('inf'))
        violations = InvariantChecker.check(tr)
        codes = [v.code for v in violations]
        assert "NON_FINITE_VALUE" in codes

    def test_non_finite_nan(self):
        tr = _make_tax_return(agi=float('nan'))
        violations = InvariantChecker.check(tr)
        codes = [v.code for v in violations]
        assert "NON_FINITE_VALUE" in codes

    def test_negative_state_tax(self):
        tr = _make_tax_return(state_tax_liability=-500)
        violations = InvariantChecker.check(tr)
        codes = [v.code for v in violations]
        assert "NEGATIVE_STATE_TAX" in codes

    def test_zero_agi_no_rate_violation(self):
        """Zero AGI should not trigger effective rate check."""
        tr = _make_tax_return(agi=0, tax_liability=0, total_income=0)
        violations = InvariantChecker.check(tr)
        codes = [v.code for v in violations]
        assert "EXCESSIVE_EFFECTIVE_RATE" not in codes

    def test_refundable_credits_negative_tax(self):
        """Negative tax (refundable credits) should not trigger rate check."""
        tr = _make_tax_return(agi=30000, tax_liability=-2000, total_income=30000)
        violations = InvariantChecker.check(tr)
        codes = [v.code for v in violations]
        assert "EXCESSIVE_EFFECTIVE_RATE" not in codes
        assert "TAX_EXCEEDS_INCOME" not in codes


# ---------------------------------------------------------------------------
# InvariantChecker.check_ai_narrative()
# ---------------------------------------------------------------------------

class TestCheckAINarrative:

    def test_no_violations_when_amounts_match(self):
        narrative = "Your tax liability is $5,000.00 on AGI of $50,000."
        computed = {"tax_liability": 5000, "agi": 50000}
        violations = InvariantChecker.check_ai_narrative(narrative, computed)
        assert violations == []

    def test_violation_when_amount_invented(self):
        narrative = "You could save $12,345 by switching to head of household."
        computed = {"tax_liability": 5000, "agi": 50000}
        violations = InvariantChecker.check_ai_narrative(narrative, computed)
        assert len(violations) == 1
        assert violations[0].code == "AI_INVENTED_NUMBER"
        assert "$12,345" in violations[0].message

    def test_small_amounts_ignored(self):
        """Amounts <= $100 are not checked (too common in generic text)."""
        narrative = "The standard deduction is $50 more than last year."
        computed = {"tax_liability": 5000}
        violations = InvariantChecker.check_ai_narrative(narrative, computed)
        assert violations == []

    def test_tolerance_applied(self):
        """Amounts within tolerance of engine value should pass."""
        narrative = "Your tax is $5,000.50."
        computed = {"tax_liability": 5000}
        violations = InvariantChecker.check_ai_narrative(narrative, computed, tolerance=1.0)
        assert violations == []

    def test_empty_narrative(self):
        violations = InvariantChecker.check_ai_narrative("", {"tax": 5000})
        assert violations == []

    def test_no_dollar_signs(self):
        narrative = "You should consider itemizing your deductions."
        computed = {"tax": 5000}
        violations = InvariantChecker.check_ai_narrative(narrative, computed)
        assert violations == []

    def test_multiple_invented_numbers(self):
        narrative = "Save $99,999 on income of $88,888!"
        computed = {"tax": 5000}
        violations = InvariantChecker.check_ai_narrative(narrative, computed)
        assert len(violations) == 2
