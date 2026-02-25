# Edge Case Tests (MVP) Design Document

**Date:** 2026-02-25
**Status:** Approved
**Approach:** 30-50 Critical Edge Case Tests (MVP)

## Overview

Add comprehensive edge case test coverage to the tax calculation engine to catch errors before production. MVP focuses on the most critical scenarios that could cause incorrect tax calculations.

## Problem

The SWOT analysis identified "Edge Cases Untested" as a Risk 7/10 issue:
- Only ~100 tests for 2,726-line calculation engine
- Happy path only coverage
- Missing tests for death during tax year, passive activities, mid-year changes, etc.
- TurboTax has 10,000+ test scenarios accumulated over 20+ years

## MVP Design

### Test Categories

**1. Life Event Edge Cases (10 tests)**
- Death during tax year (final return)
- Mid-year marriage
- Mid-year divorce
- Birth of child mid-year
- Death of dependent
- Marriage + state move same year

**2. Income Boundary Cases (10 tests)**
- Zero income return
- Exactly at standard deduction threshold
- Maximum income ($10M+)
- Negative AGI (losses exceed income)
- Income at phaseout boundaries (EITC, CTC, etc.)

**3. Filing Status Edge Cases (5 tests)**
- Qualifying widow(er) with dependent
- Head of household edge cases
- Married filing separately with itemized spouse
- Non-resident alien spouse election

**4. Credit/Deduction Phaseouts (10 tests)**
- Child Tax Credit at exact phaseout start
- EITC at maximum credit point
- Education credits at phaseout
- IRA deduction at phaseout
- Student loan interest at phaseout

**5. AMT Scenarios (5 tests)**
- AMT triggered by ISO exercise
- AMT triggered by high SALT
- AMT exemption phaseout
- AMT with foreign tax credit

**6. Complex Deduction Scenarios (5 tests)**
- Medical expenses at 7.5% AGI threshold
- Charitable contribution limits (60% AGI)
- Casualty loss in federally declared disaster
- Investment interest expense limitation

### Test Implementation

**File: `tests/test_edge_cases.py`**

```python
"""Edge case tests for tax calculation engine."""

import pytest
from decimal import Decimal
from src.calculator.engine import TaxCalculator

class TestLifeEventEdgeCases:
    """Tests for life event edge cases."""

    def test_death_during_tax_year_final_return(self):
        """Final return for taxpayer who died mid-year."""
        calc = TaxCalculator(tax_year=2025)
        result = calc.calculate(
            filing_status="single",
            date_of_death="2025-06-15",
            income_through_death=75000,
            is_final_return=True
        )
        # Should prorate standard deduction, calculate correctly
        assert result.is_final_return == True
        assert result.federal_tax > 0

    def test_mid_year_marriage(self):
        """Couple married October 15, choosing MFJ."""
        calc = TaxCalculator(tax_year=2025)
        result = calc.calculate(
            filing_status="married_filing_jointly",
            marriage_date="2025-10-15",
            spouse1_income=80000,
            spouse2_income=60000
        )
        # Full year MFJ even though married mid-year
        assert result.filing_status == "married_filing_jointly"

    # ... more tests


class TestIncomeBoundaries:
    """Tests for income boundary conditions."""

    def test_zero_income_return(self):
        """Return with exactly zero income."""
        calc = TaxCalculator(tax_year=2025)
        result = calc.calculate(
            filing_status="single",
            total_income=0
        )
        assert result.federal_tax == 0
        assert result.refundable_credits >= 0

    def test_income_at_standard_deduction(self):
        """Income exactly equal to standard deduction."""
        calc = TaxCalculator(tax_year=2025)
        result = calc.calculate(
            filing_status="single",
            total_income=15000  # 2025 single standard deduction
        )
        assert result.taxable_income == 0
        assert result.federal_tax == 0

    def test_maximum_income_scenario(self):
        """High income ($10M+) with all brackets."""
        calc = TaxCalculator(tax_year=2025)
        result = calc.calculate(
            filing_status="single",
            total_income=10000000
        )
        # Should hit 37% bracket
        assert result.effective_rate > 0.30

    # ... more tests


class TestPhaseouts:
    """Tests for credit/deduction phaseout boundaries."""

    def test_ctc_at_exact_phaseout_start(self):
        """CTC at exactly $200,000 (single) phaseout start."""
        calc = TaxCalculator(tax_year=2025)
        result = calc.calculate(
            filing_status="single",
            total_income=200000,
            num_children=2
        )
        # Should get full CTC (phaseout starts above)
        assert result.child_tax_credit == 4000  # $2000 x 2

    def test_eitc_at_maximum_credit(self):
        """EITC at income level producing maximum credit."""
        calc = TaxCalculator(tax_year=2025)
        result = calc.calculate(
            filing_status="single",
            earned_income=17500,  # Approximate max EITC income
            num_children=3
        )
        # Should be near maximum EITC
        assert result.eitc > 7000

    # ... more tests


class TestAMT:
    """Tests for Alternative Minimum Tax scenarios."""

    def test_amt_triggered_by_iso_exercise(self):
        """AMT triggered by incentive stock option exercise."""
        calc = TaxCalculator(tax_year=2025)
        result = calc.calculate(
            filing_status="married_filing_jointly",
            total_income=300000,
            iso_bargain_element=200000
        )
        # Should trigger AMT
        assert result.amt_liability > 0

    # ... more tests
```

### Test Data Fixtures

**File: `tests/fixtures/edge_case_scenarios.py`**

```python
"""Predefined edge case scenarios for testing."""

EDGE_CASE_SCENARIOS = {
    "death_mid_year": {
        "filing_status": "single",
        "date_of_death": "2025-06-15",
        "income": 75000,
        "expected_tax_range": (8000, 10000)
    },
    "zero_income": {
        "filing_status": "single",
        "income": 0,
        "expected_tax": 0
    },
    # ... 48 more scenarios
}
```

## Testing Strategy

Run edge case tests with verbose output:

```bash
python3 -m pytest tests/test_edge_cases.py -v --tb=short
```

Expected: All 45+ tests pass

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `tests/test_edge_cases.py` | Create | ~400 |
| `tests/fixtures/edge_case_scenarios.py` | Create | ~150 |

**Total: ~550 lines**

## Out of Scope (Future)

- 10,000+ test scenarios (TurboTax level)
- Property-based testing with Hypothesis
- Fuzzing for unexpected inputs
- Multi-year test scenarios
- State tax edge cases
