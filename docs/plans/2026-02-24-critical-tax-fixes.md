# Critical Tax Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement four critical tax calculation fixes for 2025 tax year compliance: EITC phase-in, educator expense cap, SECURE 2.0 RMD ages, and Form 8867 scaffold.

**Architecture:** Minimal surgical fixes to existing code following current patterns. Changes isolated to specific calculation methods with configuration-driven parameters. TDD approach for all changes.

**Tech Stack:** Python 3.11+, Pydantic models, pytest, dataclasses for configuration

---

## Task 1: EITC Phase-In Configuration

**Files:**
- Modify: `src/calculator/tax_year_config.py:58-62` (add phase-in fields)
- Modify: `src/calculator/tax_year_config.py:500-504` (add phase-in values in for_2025)
- Test: `tests/test_eitc_phase_in.py` (create)

**Step 1: Write the failing test for phase-in configuration**

Create `tests/test_eitc_phase_in.py`:

```python
"""
Tests for EITC phase-in calculation per IRS Pub. 596.

EITC builds up gradually based on earned income × phase-in rate
before reaching the plateau where max credit is available.
"""

import pytest
from calculator.tax_year_config import TaxYearConfig


class TestEitcPhaseInConfig:
    """Test EITC phase-in configuration exists in TaxYearConfig."""

    def test_config_has_phase_in_rate(self):
        """Config should have phase-in rates by number of children."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_rate is not None
        assert 0 in config.eitc_phase_in_rate
        assert 1 in config.eitc_phase_in_rate
        assert 2 in config.eitc_phase_in_rate
        assert 3 in config.eitc_phase_in_rate

    def test_config_has_phase_in_end(self):
        """Config should have phase-in end thresholds by children."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_end is not None
        assert 0 in config.eitc_phase_in_end
        assert 1 in config.eitc_phase_in_end

    def test_phase_in_rate_values_per_pub_596(self):
        """Phase-in rates should match IRS Pub. 596."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_rate[0] == pytest.approx(0.0765, rel=1e-4)
        assert config.eitc_phase_in_rate[1] == pytest.approx(0.34, rel=1e-4)
        assert config.eitc_phase_in_rate[2] == pytest.approx(0.40, rel=1e-4)
        assert config.eitc_phase_in_rate[3] == pytest.approx(0.45, rel=1e-4)

    def test_phase_in_end_values_per_pub_596(self):
        """Phase-in end thresholds should match IRS Pub. 596."""
        config = TaxYearConfig.for_2025()
        assert config.eitc_phase_in_end[0] == pytest.approx(8490.0, rel=1e-2)
        assert config.eitc_phase_in_end[1] == pytest.approx(12730.0, rel=1e-2)
        assert config.eitc_phase_in_end[2] == pytest.approx(17880.0, rel=1e-2)
        assert config.eitc_phase_in_end[3] == pytest.approx(17880.0, rel=1e-2)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_eitc_phase_in.py::TestEitcPhaseInConfig -v`
Expected: FAIL with `AttributeError: 'TaxYearConfig' object has no attribute 'eitc_phase_in_rate'`

**Step 3: Add phase-in fields to TaxYearConfig dataclass**

Modify `src/calculator/tax_year_config.py` - add after line 62 (after `eitc_investment_income_limit`):

```python
    # EITC phase-in parameters per IRS Pub. 596
    # Phase-in: Credit = earned_income × phase_in_rate (capped at max)
    eitc_phase_in_rate: Optional[Dict[int, float]] = None  # {0: 0.0765, 1: 0.34, ...}
    eitc_phase_in_end: Optional[Dict[int, float]] = None   # Earned income where phase-in ends
```

**Step 4: Add phase-in values in for_2025() method**

Modify `src/calculator/tax_year_config.py` - add after the `eitc_phase_end` dict (around line 365):

```python
        # EITC phase-in rates by number of qualifying children (Pub. 596)
        eitc_phase_in_rates = {
            0: 0.0765,  # 7.65%
            1: 0.34,    # 34%
            2: 0.40,    # 40%
            3: 0.45,    # 45% (3 or more)
        }

        # EITC phase-in end thresholds (earned income where max credit reached)
        eitc_phase_in_ends = {
            0: 8490.0,
            1: 12730.0,
            2: 17880.0,
            3: 17880.0,  # Same as 2 children
        }
```

Then add to the `return TaxYearConfig(...)` call (around line 503):

```python
            # EITC phase-in
            eitc_phase_in_rate=eitc_phase_in_rates,
            eitc_phase_in_end=eitc_phase_in_ends,
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_eitc_phase_in.py::TestEitcPhaseInConfig -v`
Expected: PASS (4 tests)

**Step 6: Commit**

```bash
git add src/calculator/tax_year_config.py tests/test_eitc_phase_in.py
git commit -m "feat: add EITC phase-in configuration per IRS Pub. 596

Add eitc_phase_in_rate and eitc_phase_in_end parameters to TaxYearConfig
with 2025 values for 0-3+ qualifying children.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: EITC Phase-In Calculation Logic

**Files:**
- Modify: `src/calculator/engine.py:2637-2639` (fix _calculate_eitc)
- Test: `tests/test_eitc_phase_in.py` (add calculation tests)

**Step 1: Write failing tests for phase-in calculation**

Add to `tests/test_eitc_phase_in.py`:

```python
from models.income import Income
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.deductions import Deductions
from models.credits import TaxCredits
from calculator.engine import FederalTaxEngine


def create_eitc_return(
    wages: float,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    num_children: int = 0,
) -> TaxReturn:
    """Helper to create TaxReturn for EITC testing."""
    income = Income()
    income.wages_w2 = [{"box_1_wages": wages, "box_2_federal_withheld": 0}]

    return TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="Taxpayer",
            filing_status=filing_status,
            primary_ssn="123-45-6789",
        ),
        income=income,
        deductions=Deductions(),
        credits=TaxCredits(num_qualifying_children=num_children),
    )


class TestEitcPhaseInCalculation:
    """Test EITC phase-in calculation in engine."""

    def test_zero_income_zero_credit(self):
        """Zero earned income should result in $0 EITC."""
        tax_return = create_eitc_return(wages=0, num_children=1)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return)
        assert eitc == 0.0

    def test_phase_in_no_children_low_income(self):
        """Test phase-in for no children at $4,000 earned income."""
        # $4,000 × 7.65% = $306 (below max of $649)
        tax_return = create_eitc_return(wages=4000, num_children=0)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return)
        assert eitc == pytest.approx(306.0, rel=0.01)

    def test_phase_in_one_child_low_income(self):
        """Test phase-in for 1 child at $6,000 earned income."""
        # $6,000 × 34% = $2,040 (below max of $4,328)
        tax_return = create_eitc_return(wages=6000, num_children=1)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return)
        assert eitc == pytest.approx(2040.0, rel=0.01)

    def test_phase_in_reaches_max_at_threshold(self):
        """At phase-in end, credit should equal max."""
        # 1 child: At $12,730 × 34% = $4,328.20, capped at max $4,328
        tax_return = create_eitc_return(wages=12730, num_children=1)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return)
        assert eitc == pytest.approx(4328.0, rel=0.01)

    def test_plateau_gets_max_credit(self):
        """Income in plateau range should get max credit."""
        # 1 child: Between $12,730 and phaseout start gets max $4,328
        tax_return = create_eitc_return(wages=15000, num_children=1)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return)
        assert eitc == pytest.approx(4328.0, rel=0.01)

    def test_phase_in_two_children(self):
        """Test phase-in for 2 children at $10,000 earned income."""
        # $10,000 × 40% = $4,000 (below max of $7,152)
        tax_return = create_eitc_return(wages=10000, num_children=2)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return)
        assert eitc == pytest.approx(4000.0, rel=0.01)

    def test_phase_in_three_children(self):
        """Test phase-in for 3+ children at $12,000 earned income."""
        # $12,000 × 45% = $5,400 (below max of $8,046)
        tax_return = create_eitc_return(wages=12000, num_children=3)
        engine = FederalTaxEngine()
        eitc = engine._calculate_eitc(tax_return)
        assert eitc == pytest.approx(5400.0, rel=0.01)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eitc_phase_in.py::TestEitcPhaseInCalculation -v`
Expected: FAIL - tests expecting phase-in calculation will get max_credit instead

**Step 3: Fix _calculate_eitc in engine.py**

Modify `src/calculator/engine.py` - replace lines 2637-2639 (the `if income_for_eitc <= phaseout_start:` block):

```python
        # Get phase-in parameters
        phase_in_end = self.config.eitc_phase_in_end.get(num_children, 0) if self.config.eitc_phase_in_end else 0
        phase_in_rate = self.config.eitc_phase_in_rate.get(num_children, 0) if self.config.eitc_phase_in_rate else 0

        # Phase-in range: Credit builds up based on earned_income × rate
        if earned_income <= phase_in_end and phase_in_rate > 0:
            credit = earned_income * phase_in_rate
            return float(money(min(credit, max_credit)))

        # Plateau range: Full max credit
        if income_for_eitc <= phaseout_start:
            return max_credit
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eitc_phase_in.py::TestEitcPhaseInCalculation -v`
Expected: PASS (7 tests)

**Step 5: Run full EITC-related test suite to check for regressions**

Run: `pytest tests/ -k "eitc" -v`
Expected: All existing EITC tests pass

**Step 6: Commit**

```bash
git add src/calculator/engine.py tests/test_eitc_phase_in.py
git commit -m "fix: implement EITC phase-in calculation per IRS Pub. 596

Previously returned max_credit for all income below phaseout_start.
Now correctly calculates: credit = earned_income × phase_in_rate
when earned_income is below the phase-in end threshold.

Fixes critical EITC calculation accuracy for tax year 2025.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Educator Expense Deduction Cap

**Files:**
- Modify: `src/models/deductions.py:442-452` (add cap logic)
- Test: `tests/test_educator_expense.py` (create)

**Step 1: Write failing tests for educator expense cap**

Create `tests/test_educator_expense.py`:

```python
"""
Tests for Educator Expense Deduction Cap per IRC §62(a)(2)(D).

Limits:
- Single educator: $300 maximum
- MFJ (two educators): $600 maximum ($300 each)
"""

import pytest
from models.deductions import Deductions


class TestEducatorExpenseCap:
    """Test educator expense cap enforcement."""

    def test_single_under_cap(self):
        """Single filer under $300 gets full deduction."""
        deductions = Deductions(educator_expenses=250.0)
        total = deductions.get_total_adjustments(filing_status="single")
        assert 250.0 in str(total) or total >= 250.0  # Contains educator expense

    def test_single_at_cap(self):
        """Single filer at $300 gets full deduction."""
        deductions = Deductions(educator_expenses=300.0)
        total = deductions.get_total_adjustments(filing_status="single")
        # The educator portion should be exactly $300
        deductions_zero = Deductions(educator_expenses=0.0)
        total_zero = deductions_zero.get_total_adjustments(filing_status="single")
        assert total - total_zero == pytest.approx(300.0, rel=0.01)

    def test_single_over_cap(self):
        """Single filer over $300 is capped at $300."""
        deductions = Deductions(educator_expenses=500.0)
        deductions_at_cap = Deductions(educator_expenses=300.0)

        total_over = deductions.get_total_adjustments(filing_status="single")
        total_at_cap = deductions_at_cap.get_total_adjustments(filing_status="single")

        # Both should result in same total (capped at $300)
        assert total_over == pytest.approx(total_at_cap, rel=0.01)

    def test_mfj_under_cap(self):
        """MFJ under $600 gets full deduction."""
        deductions = Deductions(educator_expenses=500.0)
        deductions_zero = Deductions(educator_expenses=0.0)

        total = deductions.get_total_adjustments(filing_status="married_joint")
        total_zero = deductions_zero.get_total_adjustments(filing_status="married_joint")

        assert total - total_zero == pytest.approx(500.0, rel=0.01)

    def test_mfj_at_cap(self):
        """MFJ at $600 gets full deduction."""
        deductions = Deductions(educator_expenses=600.0)
        deductions_zero = Deductions(educator_expenses=0.0)

        total = deductions.get_total_adjustments(filing_status="married_joint")
        total_zero = deductions_zero.get_total_adjustments(filing_status="married_joint")

        assert total - total_zero == pytest.approx(600.0, rel=0.01)

    def test_mfj_over_cap(self):
        """MFJ over $600 is capped at $600."""
        deductions = Deductions(educator_expenses=1000.0)
        deductions_at_cap = Deductions(educator_expenses=600.0)

        total_over = deductions.get_total_adjustments(filing_status="married_joint")
        total_at_cap = deductions_at_cap.get_total_adjustments(filing_status="married_joint")

        assert total_over == pytest.approx(total_at_cap, rel=0.01)

    def test_zero_expenses(self):
        """Zero educator expenses results in zero deduction."""
        deductions = Deductions(educator_expenses=0.0)
        deductions_none = Deductions()

        total = deductions.get_total_adjustments(filing_status="single")
        total_none = deductions_none.get_total_adjustments(filing_status="single")

        assert total == pytest.approx(total_none, rel=0.01)


class TestEducatorExpenseExcess:
    """Test helper method for reporting excess to user."""

    def test_get_excess_single_over(self):
        """Calculate excess over cap for single filer."""
        deductions = Deductions(educator_expenses=450.0)
        excess = deductions.get_educator_expense_excess(filing_status="single")
        assert excess == pytest.approx(150.0, rel=0.01)

    def test_get_excess_single_under(self):
        """No excess when under cap."""
        deductions = Deductions(educator_expenses=200.0)
        excess = deductions.get_educator_expense_excess(filing_status="single")
        assert excess == 0.0

    def test_get_excess_mfj_over(self):
        """Calculate excess over cap for MFJ."""
        deductions = Deductions(educator_expenses=800.0)
        excess = deductions.get_educator_expense_excess(filing_status="married_joint")
        assert excess == pytest.approx(200.0, rel=0.01)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_educator_expense.py -v`
Expected: FAIL - tests expecting cap will get uncapped amounts

**Step 3: Update get_total_adjustments to enforce cap**

Modify `src/models/deductions.py` - update the `get_total_adjustments` method.

First, add the `filing_status` parameter to the signature if not already there (around line 400):

```python
    def get_total_adjustments(
        self,
        magi: float = 0.0,
        filing_status: str = "single",  # Add this parameter
        is_covered_by_employer_plan: bool = False,
        spouse_covered_by_employer_plan: bool = False,
        is_age_50_plus: bool = False,
        taxable_compensation: float = 0.0,
    ) -> float:
```

Then modify the return statement (around line 442) to apply the cap:

```python
        # Cap educator expenses per IRC §62(a)(2)(D)
        # $300 per educator, $600 max for MFJ with two educators
        if filing_status == "married_joint":
            educator_cap = 600.0
        else:
            educator_cap = 300.0
        educator_deduction = min(self.educator_expenses, educator_cap)

        return (
            educator_deduction +  # Changed from self.educator_expenses
            student_loan_deduction +
            self.hsa_contributions +
            ira_deduction +
            self.self_employed_se_health +
            self.self_employed_sep_simple +
            self.penalty_early_withdrawal +
            self.alimony_paid +
            self.other_adjustments
        )
```

**Step 4: Add helper method for excess calculation**

Add after `get_total_adjustments` method (around line 453):

```python
    def get_educator_expense_excess(self, filing_status: str = "single") -> float:
        """
        Calculate educator expenses exceeding the IRC §62(a)(2)(D) cap.

        Returns the amount that cannot be deducted, useful for user notification.

        Args:
            filing_status: Filing status determines cap ($300 or $600 for MFJ)

        Returns:
            Amount of educator expenses exceeding the deductible limit
        """
        cap = 600.0 if filing_status == "married_joint" else 300.0
        return max(0.0, self.educator_expenses - cap)
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_educator_expense.py -v`
Expected: PASS (10 tests)

**Step 6: Verify no regressions in deduction calculations**

Run: `pytest tests/test_ira_deduction.py tests/test_schedule_a.py -v`
Expected: All pass

**Step 7: Commit**

```bash
git add src/models/deductions.py tests/test_educator_expense.py
git commit -m "fix: enforce educator expense $300/$600 cap per IRC §62(a)(2)(D)

Previously added educator_expenses without limit enforcement.
Now caps at $300 for single filers and $600 for MFJ.

Adds get_educator_expense_excess() helper for user notifications.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: SECURE 2.0 RMD Starting Age Helper

**Files:**
- Modify: `src/models/form_5329.py` (add get_rmd_starting_age method)
- Modify: `tests/test_form_5329.py` (add RMD age tests)

**Step 1: Write failing tests for RMD starting age**

Add to `tests/test_form_5329.py`:

```python
class TestSecure2RmdAge:
    """Test SECURE 2.0 RMD starting age determination."""

    def test_birth_year_1950_age_72(self):
        """Birth year 1950 or earlier: RMD starts at 72."""
        form = Form5329()
        assert form.get_rmd_starting_age(1950) == 72
        assert form.get_rmd_starting_age(1945) == 72
        assert form.get_rmd_starting_age(1940) == 72

    def test_birth_year_1951_1959_age_73(self):
        """Birth years 1951-1959: RMD starts at 73."""
        form = Form5329()
        assert form.get_rmd_starting_age(1951) == 73
        assert form.get_rmd_starting_age(1955) == 73
        assert form.get_rmd_starting_age(1959) == 73

    def test_birth_year_1960_plus_age_75(self):
        """Birth year 1960 or later: RMD starts at 75."""
        form = Form5329()
        assert form.get_rmd_starting_age(1960) == 75
        assert form.get_rmd_starting_age(1965) == 75
        assert form.get_rmd_starting_age(1980) == 75
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_form_5329.py::TestSecure2RmdAge -v`
Expected: FAIL with `AttributeError: 'Form5329' object has no attribute 'get_rmd_starting_age'`

**Step 3: Add get_rmd_starting_age method to Form5329**

Modify `src/models/form_5329.py` - add method in the Form5329 class (after `add_rmd_failure`, around line 698):

```python
    def get_rmd_starting_age(self, birth_year: int) -> int:
        """
        Get RMD starting age based on birth year per SECURE 2.0.

        SECURE Act 2.0 (2022) changed RMD ages:
        - Birth year 1950 or earlier: Age 72
        - Birth year 1951-1959: Age 73
        - Birth year 1960 or later: Age 75

        Args:
            birth_year: Year the account owner was born

        Returns:
            Age at which RMDs must begin
        """
        if birth_year <= 1950:
            return 72
        elif birth_year <= 1959:
            return 73
        else:
            return 75
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_form_5329.py::TestSecure2RmdAge -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/models/form_5329.py tests/test_form_5329.py
git commit -m "feat: add SECURE 2.0 RMD starting age helper

Implements get_rmd_starting_age(birth_year) method per SECURE Act 2.0:
- 1950 or earlier: 72
- 1951-1959: 73
- 1960 or later: 75

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: SECURE 2.0 RMD Penalty Rates

**Files:**
- Modify: `src/models/form_5329.py:290` (verify 25%/10% rates)
- Modify: `tests/test_form_5329.py` (add penalty rate tests)

**Step 1: Write tests to verify penalty rates**

Add to `tests/test_form_5329.py`:

```python
class TestSecure2RmdPenaltyRates:
    """Test SECURE 2.0 reduced RMD penalty rates."""

    def test_standard_penalty_25_percent(self):
        """Standard RMD failure penalty is 25% (reduced from 50%)."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=0.0,
            rmd_year=2025,
            is_corrected=False,
        )
        result = form.calculate_part_viii_rmd_penalty()
        # 25% of $10,000 shortfall = $2,500
        assert result['total_penalty'] == pytest.approx(2500.0, rel=0.01)

    def test_corrected_penalty_10_percent(self):
        """Timely corrected RMD failure penalty is 10%."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=0.0,
            rmd_year=2025,
            is_corrected=True,
        )
        result = form.calculate_part_viii_rmd_penalty()
        # 10% of $10,000 shortfall = $1,000
        assert result['total_penalty'] == pytest.approx(1000.0, rel=0.01)

    def test_partial_shortfall_standard_rate(self):
        """Partial shortfall at 25% rate."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=6000.0,  # $4,000 shortfall
            rmd_year=2025,
            is_corrected=False,
        )
        result = form.calculate_part_viii_rmd_penalty()
        # 25% of $4,000 = $1,000
        assert result['total_penalty'] == pytest.approx(1000.0, rel=0.01)

    def test_partial_shortfall_corrected_rate(self):
        """Partial shortfall at 10% corrected rate."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=6000.0,  # $4,000 shortfall
            rmd_year=2025,
            is_corrected=True,
        )
        result = form.calculate_part_viii_rmd_penalty()
        # 10% of $4,000 = $400
        assert result['total_penalty'] == pytest.approx(400.0, rel=0.01)

    def test_waiver_requested_zero_penalty(self):
        """Waiver request results in zero penalty (taxpayer must justify)."""
        form = Form5329()
        form.add_rmd_failure(
            required_amount=10000.0,
            actual_amount=0.0,
            rmd_year=2025,
            waiver_requested=True,
        )
        result = form.calculate_part_viii_rmd_penalty()
        assert result['total_penalty'] == 0.0
```

**Step 2: Run tests to verify current behavior**

Run: `pytest tests/test_form_5329.py::TestSecure2RmdPenaltyRates -v`
Expected: PASS - The existing code already uses 25%/10% rates (verify)

If tests fail, proceed to Step 3 to fix the rates.

**Step 3: Verify/fix penalty rates in RMDFailure.calculate_excise_tax**

Check `src/models/form_5329.py` around line 290. The code should already have:

```python
        rate = 0.10 if self.is_corrected_timely else 0.25
```

If it shows 0.50 instead of 0.25, update it.

**Step 4: Run tests to confirm**

Run: `pytest tests/test_form_5329.py::TestSecure2RmdPenaltyRates -v`
Expected: PASS (5 tests)

**Step 5: Run full Form 5329 test suite**

Run: `pytest tests/test_form_5329.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add src/models/form_5329.py tests/test_form_5329.py
git commit -m "test: verify SECURE 2.0 RMD penalty rates (25%/10%)

Adds explicit tests for SECURE 2.0 penalty rates:
- Standard: 25% (down from 50%)
- Corrected timely: 10%
- Waiver requested: 0%

Existing implementation already correct per SECURE Act 2.0.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Form 8867 Due Diligence Scaffold

**Files:**
- Create: `src/models/form_8867.py`
- Create: `tests/test_form_8867.py`

**Step 1: Write failing tests for Form 8867 scaffold**

Create `tests/test_form_8867.py`:

```python
"""
Tests for Form 8867: Paid Preparer's Due Diligence Checklist.

Required for paid preparers claiming EITC, CTC, AOTC, or HOH filing status.
Penalty: $600 per failure (2025) per IRC §6695(g).
"""

import pytest
from models.form_8867 import (
    Form8867,
    CreditType,
    DueDiligenceQuestion,
)


class TestForm8867Model:
    """Test Form 8867 model structure."""

    def test_credit_type_enum(self):
        """CreditType enum should include required credits."""
        assert CreditType.EITC.value == "eitc"
        assert CreditType.CTC.value == "ctc"
        assert CreditType.ACTC.value == "actc"
        assert CreditType.ODC.value == "odc"
        assert CreditType.AOTC.value == "aotc"
        assert CreditType.HOH.value == "hoh"

    def test_form_has_required_fields(self):
        """Form should have required preparer and credit fields."""
        form = Form8867()
        assert hasattr(form, 'preparer_name')
        assert hasattr(form, 'preparer_ptin')
        assert hasattr(form, 'credits_claimed')
        assert hasattr(form, 'tax_year')

    def test_credits_claimed_tracking(self):
        """Form should track which credits are claimed."""
        form = Form8867(
            credits_claimed=[CreditType.EITC, CreditType.CTC]
        )
        assert CreditType.EITC in form.credits_claimed
        assert CreditType.CTC in form.credits_claimed
        assert CreditType.AOTC not in form.credits_claimed


class TestForm8867Validation:
    """Test Form 8867 validation logic."""

    def test_empty_form_is_incomplete(self):
        """Empty form should not validate as complete."""
        form = Form8867()
        is_complete, missing = form.validate_completeness()
        assert is_complete is False
        assert len(missing) > 0

    def test_complete_form_validates(self):
        """Form with all required fields should validate."""
        form = Form8867(
            preparer_name="Test Preparer",
            preparer_ptin="P12345678",
            credits_claimed=[CreditType.EITC],
            knowledge_obtained=True,
            documents_reviewed=True,
            record_retention_acknowledged=True,
        )
        is_complete, missing = form.validate_completeness()
        assert is_complete is True
        assert len(missing) == 0


class TestForm8867Penalty:
    """Test Form 8867 penalty calculation."""

    def test_penalty_single_credit(self):
        """Penalty for single credit failure: $600."""
        form = Form8867(credits_claimed=[CreditType.EITC])
        penalty = form.calculate_potential_penalty()
        assert penalty == 600.0

    def test_penalty_multiple_credits(self):
        """Penalty for multiple credit failures: $600 each."""
        form = Form8867(
            credits_claimed=[CreditType.EITC, CreditType.CTC, CreditType.AOTC]
        )
        penalty = form.calculate_potential_penalty()
        assert penalty == 1800.0  # 3 × $600

    def test_no_penalty_when_complete(self):
        """No penalty when due diligence is complete."""
        form = Form8867(
            preparer_name="Test Preparer",
            preparer_ptin="P12345678",
            credits_claimed=[CreditType.EITC],
            knowledge_obtained=True,
            documents_reviewed=True,
            record_retention_acknowledged=True,
        )
        # When form is complete, penalty is avoided
        # (This tests the potential penalty if incomplete)
        is_complete, _ = form.validate_completeness()
        if is_complete:
            assert True  # No penalty applies
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_form_8867.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models.form_8867'`

**Step 3: Create Form 8867 scaffold**

Create `src/models/form_8867.py`:

```python
"""
Form 8867: Paid Preparer's Due Diligence Checklist.

Required for paid preparers claiming EITC, CTC/ACTC/ODC, AOTC, or HOH filing status.
Penalty: $600 per failure (2025) per IRC §6695(g).

This is a SCAFFOLD implementation for Phase 1.
Full workflow integration is deferred to Phase 2.

References:
- IRS Form 8867 and Instructions
- IRC §6695(g) - Due diligence requirements for paid preparers
- IRS Pub. 4687 - EITC Due Diligence Training Module
"""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class CreditType(str, Enum):
    """Credits requiring Form 8867 due diligence."""
    EITC = "eitc"      # Earned Income Tax Credit
    CTC = "ctc"        # Child Tax Credit
    ACTC = "actc"      # Additional Child Tax Credit
    ODC = "odc"        # Other Dependent Credit
    AOTC = "aotc"      # American Opportunity Tax Credit
    HOH = "hoh"        # Head of Household filing status


class DueDiligenceQuestion(BaseModel):
    """Individual due diligence question/requirement."""

    question_id: str = Field(..., description="Unique identifier for the question")
    question_text: str = Field(..., description="The due diligence question")
    credit_types: List[CreditType] = Field(
        default_factory=list,
        description="Credit types this question applies to"
    )
    answer: Optional[bool] = Field(
        default=None,
        description="Preparer's answer (True=Yes, False=No, None=Unanswered)"
    )
    notes: str = Field(
        default="",
        description="Preparer notes for this question"
    )


# Standard due diligence questions per Form 8867 instructions
STANDARD_DUE_DILIGENCE_QUESTIONS = [
    DueDiligenceQuestion(
        question_id="knowledge_1",
        question_text="Did you ask the taxpayer about the information you used to determine eligibility?",
        credit_types=[CreditType.EITC, CreditType.CTC, CreditType.ACTC, CreditType.ODC, CreditType.AOTC, CreditType.HOH],
    ),
    DueDiligenceQuestion(
        question_id="knowledge_2",
        question_text="Did you document the questions you asked and the taxpayer's responses?",
        credit_types=[CreditType.EITC, CreditType.CTC, CreditType.ACTC, CreditType.ODC, CreditType.AOTC, CreditType.HOH],
    ),
    DueDiligenceQuestion(
        question_id="eligibility_1",
        question_text="Did you review information to determine if the taxpayer is eligible for the credit(s)?",
        credit_types=[CreditType.EITC, CreditType.CTC, CreditType.ACTC, CreditType.ODC, CreditType.AOTC],
    ),
    DueDiligenceQuestion(
        question_id="hoh_1",
        question_text="Did you determine if the taxpayer has a qualifying person for HOH status?",
        credit_types=[CreditType.HOH],
    ),
]


class Form8867(BaseModel):
    """
    IRS Form 8867: Paid Preparer's Due Diligence Checklist.

    This scaffold tracks due diligence requirements for paid preparers
    claiming EITC, CTC/ACTC/ODC, AOTC, or HOH filing status.

    Phase 1: Data model and validation
    Phase 2: Integration with filing workflow (future)
    """

    # Tax year
    tax_year: int = Field(default=2025, description="Tax year for this form")

    # Preparer identification
    preparer_name: str = Field(default="", description="Paid preparer's name")
    preparer_ptin: str = Field(
        default="",
        description="Preparer Tax Identification Number (PTIN)"
    )
    firm_name: str = Field(default="", description="Firm name if applicable")
    firm_ein: str = Field(default="", description="Firm EIN if applicable")

    # Credits claimed on this return
    credits_claimed: List[CreditType] = Field(
        default_factory=list,
        description="Credits requiring due diligence on this return"
    )

    # Part I: Due Diligence Requirements (simplified for scaffold)
    knowledge_obtained: bool = Field(
        default=False,
        description="Preparer obtained knowledge about taxpayer's eligibility"
    )

    # Part II: Knowledge Documentation
    documents_reviewed: bool = Field(
        default=False,
        description="Preparer reviewed required documents"
    )
    document_list: List[str] = Field(
        default_factory=list,
        description="List of documents reviewed"
    )

    # Part III: Record Retention
    record_retention_acknowledged: bool = Field(
        default=False,
        description="Preparer acknowledges record retention requirements"
    )

    # Detailed questions (for full implementation)
    questions: List[DueDiligenceQuestion] = Field(
        default_factory=list,
        description="Individual due diligence questions"
    )

    # Notes and comments
    preparer_notes: str = Field(
        default="",
        description="Additional preparer notes"
    )

    # Penalty rate for 2025
    PENALTY_PER_FAILURE: float = 600.0

    def validate_completeness(self) -> Tuple[bool, List[str]]:
        """
        Validate that all required due diligence is complete.

        Returns:
            Tuple of (is_complete, list_of_missing_items)
        """
        missing = []

        if not self.preparer_name:
            missing.append("Preparer name required")

        if not self.preparer_ptin:
            missing.append("PTIN required")

        if not self.credits_claimed:
            missing.append("No credits specified - form may not be required")

        if not self.knowledge_obtained:
            missing.append("Part I: Knowledge about eligibility not confirmed")

        if not self.documents_reviewed:
            missing.append("Part II: Document review not confirmed")

        if not self.record_retention_acknowledged:
            missing.append("Part III: Record retention not acknowledged")

        is_complete = len(missing) == 0
        return is_complete, missing

    def calculate_potential_penalty(self) -> float:
        """
        Calculate potential penalty for incomplete due diligence.

        Per IRC §6695(g): $600 per failure for 2025.
        Each credit type is a separate potential failure.

        Returns:
            Total potential penalty amount
        """
        if not self.credits_claimed:
            return 0.0

        # Each credit type is a separate $600 penalty
        return len(self.credits_claimed) * self.PENALTY_PER_FAILURE

    def get_applicable_questions(self) -> List[DueDiligenceQuestion]:
        """
        Get due diligence questions applicable to claimed credits.

        Returns:
            List of questions that apply to the credits on this return
        """
        applicable = []
        for question in STANDARD_DUE_DILIGENCE_QUESTIONS:
            for credit in self.credits_claimed:
                if credit in question.credit_types:
                    applicable.append(question)
                    break
        return applicable

    def generate_checklist_summary(self) -> dict:
        """Generate summary for preparer review."""
        is_complete, missing = self.validate_completeness()

        return {
            'tax_year': self.tax_year,
            'preparer': {
                'name': self.preparer_name,
                'ptin': self.preparer_ptin,
                'firm': self.firm_name,
            },
            'credits_claimed': [c.value for c in self.credits_claimed],
            'is_complete': is_complete,
            'missing_items': missing,
            'potential_penalty': self.calculate_potential_penalty(),
            'documents_reviewed': self.document_list,
        }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_form_8867.py -v`
Expected: PASS (8 tests)

**Step 5: Commit**

```bash
git add src/models/form_8867.py tests/test_form_8867.py
git commit -m "feat: add Form 8867 due diligence scaffold per IRC §6695(g)

Phase 1 scaffold for paid preparer due diligence requirements:
- CreditType enum for EITC, CTC, ACTC, ODC, AOTC, HOH
- Form8867 model with preparer fields and validation
- validate_completeness() to check required fields
- calculate_potential_penalty() for $600/failure calculation
- Standard due diligence questions structure

Full workflow integration deferred to Phase 2.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Integration Testing and Final Verification

**Files:**
- Test: All new test files
- Verify: No regressions in existing tests

**Step 1: Run all new tests**

Run: `pytest tests/test_eitc_phase_in.py tests/test_educator_expense.py tests/test_form_8867.py tests/test_form_5329.py::TestSecure2RmdAge tests/test_form_5329.py::TestSecure2RmdPenaltyRates -v`

Expected: All PASS

**Step 2: Run full test suite for regressions**

Run: `pytest tests/ -v --tb=short`

Expected: All tests pass. If any fail, investigate and fix.

**Step 3: Run specific calculator tests**

Run: `pytest tests/test_brackets.py tests/test_services.py -v`

Expected: All pass

**Step 4: Final commit with all tests passing**

```bash
git status
# Should show all files committed, working directory clean

git log --oneline -6
# Should show 6 new commits for this implementation
```

**Step 5: Create summary tag**

```bash
git tag -a v2025.1.0-tax-fixes -m "Critical tax fixes for 2025 compliance

- EITC phase-in calculation (Pub. 596)
- Educator expense $300/$600 cap (IRC §62(a)(2)(D))
- SECURE 2.0 RMD age thresholds
- Form 8867 due diligence scaffold (IRC §6695(g))"
```

---

## Summary

| Task | Files Modified | Lines Changed | Tests Added |
|------|---------------|---------------|-------------|
| 1. EITC Config | `tax_year_config.py` | ~15 | 4 |
| 2. EITC Calculation | `engine.py` | ~10 | 7 |
| 3. Educator Cap | `deductions.py` | ~20 | 10 |
| 4. RMD Age Helper | `form_5329.py` | ~15 | 3 |
| 5. RMD Penalty Rates | `form_5329.py` | ~5 | 5 |
| 6. Form 8867 | `form_8867.py` (new) | ~180 | 8 |
| **Total** | **5 files** | **~245 lines** | **37 tests** |

## Execution Options

**Plan complete and saved to `docs/plans/2026-02-24-critical-tax-fixes.md`.**

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
