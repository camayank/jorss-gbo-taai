# QBI W-2 Wage Limitation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix IRC §199A(b)(2)(B) compliance by applying W-2 wage limitation per qualified trade or business, not in aggregate.

**Architecture:** Add `QBIBusinessDetail` dataclass for per-business tracking. Refactor `QBICalculator.calculate()` to build per-business breakdown, apply wage limitation per business, then aggregate. Add warning generation for S-corp owners missing W-2 wages.

**Tech Stack:** Python, dataclasses, Decimal for precision, pytest for testing

---

### Task 1: Add QBIBusinessDetail Dataclass

**Files:**
- Modify: `src/calculator/qbi_calculator.py:26` (add after imports, before QBIBreakdown)
- Test: `tests/test_qbi_w2_wage_limitation.py` (create new file)

**Step 1: Write the failing test**

```python
"""
Tests for QBI W-2 wage limitation per IRC §199A(b)(2)(B).
"""

import pytest
from decimal import Decimal
from src.calculator.qbi_calculator import QBIBusinessDetail


class TestQBIBusinessDetailModel:
    """Tests for QBIBusinessDetail dataclass."""

    def test_default_values(self):
        """QBIBusinessDetail should have sensible defaults."""
        detail = QBIBusinessDetail()
        assert detail.business_name == ""
        assert detail.business_type == "sole_proprietorship"
        assert detail.qualified_business_income == Decimal("0")
        assert detail.w2_wages == Decimal("0")
        assert detail.ubia == Decimal("0")
        assert detail.is_sstb is False

    def test_wage_limitation_fields_exist(self):
        """QBIBusinessDetail should have wage limitation calculation fields."""
        detail = QBIBusinessDetail()
        assert hasattr(detail, 'wage_limit_50_pct')
        assert hasattr(detail, 'wage_limit_25_2_5_pct')
        assert hasattr(detail, 'wage_limitation')
        assert hasattr(detail, 'tentative_deduction')
        assert hasattr(detail, 'limited_deduction')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestQBIBusinessDetailModel -v`
Expected: FAIL with "ImportError: cannot import name 'QBIBusinessDetail'"

**Step 3: Write minimal implementation**

Add to `src/calculator/qbi_calculator.py` after line 25 (after existing imports):

```python
@dataclass
class QBIBusinessDetail:
    """Per-business QBI breakdown for W-2 wage limitation per IRC §199A(b)(2)(B)."""

    business_name: str = ""
    business_type: str = "sole_proprietorship"  # sole_proprietorship, partnership, s_corporation
    ein: str = ""

    # QBI components
    qualified_business_income: Decimal = Decimal("0")

    # W-2 wage limitation inputs
    w2_wages: Decimal = Decimal("0")
    ubia: Decimal = Decimal("0")
    is_sstb: bool = False

    # Calculated limitation values
    wage_limit_50_pct: Decimal = Decimal("0")  # 50% of W-2 wages
    wage_limit_25_2_5_pct: Decimal = Decimal("0")  # 25% of W-2 wages + 2.5% of UBIA
    wage_limitation: Decimal = Decimal("0")  # Greater of the two

    # Deduction calculation
    tentative_deduction: Decimal = Decimal("0")  # 20% of QBI
    limited_deduction: Decimal = Decimal("0")  # After applying wage limitation
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestQBIBusinessDetailModel -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/calculator/qbi_calculator.py tests/test_qbi_w2_wage_limitation.py
git commit -m "feat(qbi): add QBIBusinessDetail dataclass for per-business tracking"
```

---

### Task 2: Add business_details Field to QBIBreakdown

**Files:**
- Modify: `src/calculator/qbi_calculator.py:59` (add field to QBIBreakdown)
- Test: `tests/test_qbi_w2_wage_limitation.py`

**Step 1: Write the failing test**

Add to `tests/test_qbi_w2_wage_limitation.py`:

```python
from src.calculator.qbi_calculator import QBIBreakdown


class TestQBIBreakdownBusinessDetails:
    """Tests for business_details field in QBIBreakdown."""

    def test_breakdown_has_business_details_field(self):
        """QBIBreakdown should have business_details list."""
        breakdown = QBIBreakdown()
        assert hasattr(breakdown, 'business_details')
        assert isinstance(breakdown.business_details, list)
        assert len(breakdown.business_details) == 0

    def test_business_details_can_hold_qbi_business_detail(self):
        """business_details should accept QBIBusinessDetail objects."""
        breakdown = QBIBreakdown()
        detail = QBIBusinessDetail(
            business_name="Test LLC",
            qualified_business_income=Decimal("50000"),
        )
        breakdown.business_details.append(detail)
        assert len(breakdown.business_details) == 1
        assert breakdown.business_details[0].business_name == "Test LLC"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestQBIBreakdownBusinessDetails -v`
Expected: FAIL with "AttributeError: 'QBIBreakdown' object has no attribute 'business_details'"

**Step 3: Write minimal implementation**

Add to `QBIBreakdown` class in `src/calculator/qbi_calculator.py` (after line 59, before the class ends):

```python
    # Per-business breakdown for IRC §199A(b)(2)(B) compliance
    business_details: list = field(default_factory=list)  # List[QBIBusinessDetail]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestQBIBreakdownBusinessDetails -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/calculator/qbi_calculator.py tests/test_qbi_w2_wage_limitation.py
git commit -m "feat(qbi): add business_details field to QBIBreakdown"
```

---

### Task 3: Test Per-Business W-2 Wage Limitation Calculation

**Files:**
- Test: `tests/test_qbi_w2_wage_limitation.py`

**Step 1: Write the failing test**

Add to `tests/test_qbi_w2_wage_limitation.py`:

```python
from src.calculator.qbi_calculator import QBICalculator
from src.calculator.tax_year_config import TaxYearConfig
from src.models.tax_return import TaxReturn
from src.models.taxpayer import TaxpayerInfo, FilingStatus
from src.models.income import Income, ScheduleK1, K1SourceType
from src.models.deductions import Deductions
from src.models.credits import TaxCredits


class TestPerBusinessWageLimitation:
    """Tests for per-business W-2 wage limitation per IRC §199A(b)(2)(B)."""

    def test_two_businesses_different_wage_ratios_above_threshold(self):
        """
        Per-business limitation should apply to each business separately.

        Business A: $100K QBI, $80K W-2 wages (50% limit = $40K, 20% QBI = $20K) → gets $20K
        Business B: $100K QBI, $0 W-2 wages (50% limit = $0, 20% QBI = $20K) → gets $0

        Aggregate approach (WRONG): $200K QBI, $80K wages → limit $40K, deduction $40K
        Per-business approach (CORRECT): $20K + $0 = $20K
        """
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        # Two K-1s with different W-2 wage situations
        k1_with_wages = ScheduleK1(
            k1_type=K1SourceType.S_CORPORATION,
            entity_name="S-Corp With Wages",
            entity_ein="11-1111111",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=80000.0,  # Has W-2 wages
            ubia_for_qbi=0.0,
            is_sstb=False,
        )
        k1_no_wages = ScheduleK1(
            k1_type=K1SourceType.S_CORPORATION,
            entity_name="S-Corp No Wages",
            entity_ein="22-2222222",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=0.0,  # No W-2 wages
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1_with_wages, k1_no_wages]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        # Taxable income well above threshold ($247,300 for single)
        # Total QBI = $200K, so taxable income ~ $200K - $15K std ded = $185K
        # Need to add wages to get above threshold
        tax_return.income.wages = 150000.0  # Additional W-2 wages to push above threshold

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=350000.0,  # Well above $247,300 threshold
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        # Per-business breakdown should exist
        assert len(result.business_details) == 2

        # Business A (with wages): $20K deduction (20% of $100K QBI, not limited by $40K wage cap)
        biz_a = result.business_details[0]
        assert biz_a.business_name == "S-Corp With Wages"
        assert biz_a.limited_deduction == Decimal("20000")

        # Business B (no wages): $0 deduction (limited by $0 wage cap)
        biz_b = result.business_details[1]
        assert biz_b.business_name == "S-Corp No Wages"
        assert biz_b.limited_deduction == Decimal("0")

        # Total should be $20K (per-business), not $40K (aggregate)
        assert result.final_qbi_deduction == Decimal("20000")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestPerBusinessWageLimitation::test_two_businesses_different_wage_ratios_above_threshold -v`
Expected: FAIL with "AssertionError: assert 0 == 2" (business_details empty)

**Step 3: Continue to Task 4 for implementation**

(Test remains failing until Task 4 is complete)

**Step 4: Commit failing test**

```bash
git add tests/test_qbi_w2_wage_limitation.py
git commit -m "test(qbi): add failing test for per-business W-2 wage limitation"
```

---

### Task 4: Implement Per-Business Calculation Logic

**Files:**
- Modify: `src/calculator/qbi_calculator.py` (refactor calculate() method)

**Step 1: Test already written in Task 3**

**Step 2: Write the implementation**

Replace the `calculate()` method in `QBICalculator` class (lines 71-206) with:

```python
    def calculate(
        self,
        tax_return: "TaxReturn",
        taxable_income_before_qbi: float,
        net_capital_gain: float,
        filing_status: str,
        config: "TaxYearConfig",
    ) -> QBIBreakdown:
        """
        Calculate the QBI deduction per Section 199A.

        Per IRC §199A(b)(2)(B), the W-2 wage limitation is applied
        per qualified trade or business, not in aggregate.
        """
        breakdown = QBIBreakdown()
        breakdown.taxable_income_before_qbi = to_decimal(taxable_income_before_qbi)

        income = tax_return.income
        qbi_rate = to_decimal(config.qbi_deduction_rate)

        # Step 1: Get thresholds for filing status
        breakdown.threshold_start = to_decimal(self._get_threshold_start(filing_status, config))
        breakdown.threshold_end = to_decimal(self._get_threshold_end(filing_status, config))

        # Step 2: Determine threshold position
        taxable_income_decimal = to_decimal(taxable_income_before_qbi)
        breakdown.is_below_threshold = taxable_income_decimal <= breakdown.threshold_start
        breakdown.is_above_threshold = taxable_income_decimal >= breakdown.threshold_end

        if breakdown.is_below_threshold:
            breakdown.phase_in_ratio = Decimal("0")
        elif breakdown.is_above_threshold:
            breakdown.phase_in_ratio = Decimal("1")
        else:
            phase_range = subtract(breakdown.threshold_end, breakdown.threshold_start)
            excess = subtract(taxable_income_decimal, breakdown.threshold_start)
            breakdown.phase_in_ratio = divide(excess, phase_range) if phase_range > 0 else Decimal("1")

        # Step 3: Build per-business breakdown
        businesses: list[QBIBusinessDetail] = []

        # Self-employment (Schedule C) as one business
        se_income = to_decimal(income.self_employment_income)
        se_expenses = to_decimal(income.self_employment_expenses)
        se_net = subtract(se_income, se_expenses)
        if se_net > 0:
            breakdown.qbi_from_self_employment = se_net
            businesses.append(QBIBusinessDetail(
                business_name="Self-Employment (Schedule C)",
                business_type="sole_proprietorship",
                qualified_business_income=se_net,
                w2_wages=Decimal("0"),  # Sole props don't have W-2 wages
                ubia=Decimal("0"),
                is_sstb=False,
            ))

        # K-1 forms as separate businesses
        for k1 in income.schedule_k1_forms:
            qbi_income = to_decimal(k1.qbi_ordinary_income)
            if qbi_income > 0:
                breakdown.qbi_from_k1 = add(breakdown.qbi_from_k1, qbi_income)
                businesses.append(QBIBusinessDetail(
                    business_name=k1.entity_name,
                    business_type=k1.k1_type.value if hasattr(k1.k1_type, 'value') else str(k1.k1_type),
                    ein=k1.entity_ein or "",
                    qualified_business_income=qbi_income,
                    w2_wages=to_decimal(k1.w2_wages_for_qbi),
                    ubia=to_decimal(k1.ubia_for_qbi),
                    is_sstb=k1.is_sstb,
                ))

        # Total QBI
        breakdown.total_qbi = add(breakdown.qbi_from_self_employment, breakdown.qbi_from_k1)
        breakdown.has_sstb = income.has_sstb_income()

        # If no QBI, return early
        if breakdown.total_qbi <= 0:
            breakdown.business_details = businesses
            return breakdown

        # Aggregate W-2 wages and UBIA for backward compatibility
        breakdown.w2_wages_total = sum((b.w2_wages for b in businesses), Decimal("0"))
        breakdown.ubia_total = sum((b.ubia for b in businesses), Decimal("0"))

        # Step 4: Apply per-business wage limitation
        total_limited_deduction = Decimal("0")

        for biz in businesses:
            # Calculate tentative 20% deduction
            biz.tentative_deduction = multiply(biz.qualified_business_income, qbi_rate)

            # Calculate wage limitations
            biz.wage_limit_50_pct = multiply(biz.w2_wages, Decimal("0.50"))
            wage_25_pct = multiply(biz.w2_wages, Decimal("0.25"))
            ubia_2_5_pct = multiply(biz.ubia, Decimal("0.025"))
            biz.wage_limit_25_2_5_pct = add(wage_25_pct, ubia_2_5_pct)
            biz.wage_limitation = max_decimal(biz.wage_limit_50_pct, biz.wage_limit_25_2_5_pct)

            # Apply SSTB reduction if applicable
            effective_qbi = biz.qualified_business_income
            if biz.is_sstb and not breakdown.is_below_threshold:
                sstb_pct = self._calculate_sstb_percentage(breakdown.phase_in_ratio)
                effective_qbi = multiply(effective_qbi, sstb_pct)
                biz.tentative_deduction = multiply(effective_qbi, qbi_rate)

            # Apply limitation based on threshold position
            if breakdown.is_below_threshold:
                # No limitation - full 20% deduction
                biz.limited_deduction = biz.tentative_deduction
            elif breakdown.is_above_threshold:
                # Full wage limitation applies
                biz.limited_deduction = min_decimal(biz.tentative_deduction, biz.wage_limitation)
            else:
                # Phase-in: partially apply wage limitation
                if biz.tentative_deduction > biz.wage_limitation:
                    reduction = subtract(biz.tentative_deduction, biz.wage_limitation)
                    phased_reduction = multiply(reduction, breakdown.phase_in_ratio)
                    biz.limited_deduction = subtract(biz.tentative_deduction, phased_reduction)
                else:
                    biz.limited_deduction = biz.tentative_deduction

            total_limited_deduction = add(total_limited_deduction, biz.limited_deduction)

        breakdown.business_details = businesses
        breakdown.qbi_after_wage_limit = total_limited_deduction
        breakdown.wage_limitation_applies = not breakdown.is_below_threshold

        # Calculate aggregate wage limits for backward compatibility
        breakdown.wage_limit_50_pct = multiply(breakdown.w2_wages_total, Decimal("0.50"))
        wage_25_pct = multiply(breakdown.w2_wages_total, Decimal("0.25"))
        ubia_2_5_pct = multiply(breakdown.ubia_total, Decimal("0.025"))
        breakdown.wage_limit_25_2_5_pct = add(wage_25_pct, ubia_2_5_pct)
        breakdown.wage_limitation = max_decimal(breakdown.wage_limit_50_pct, breakdown.wage_limit_25_2_5_pct)
        breakdown.tentative_qbi_deduction = multiply(breakdown.total_qbi, qbi_rate)

        # SSTB percentage for backward compatibility
        if breakdown.has_sstb:
            breakdown.sstb_applicable_percentage = self._calculate_sstb_percentage(breakdown.phase_in_ratio)
        else:
            breakdown.sstb_applicable_percentage = Decimal("1")

        # Step 5: Apply taxable income limitation
        net_cap_gain = to_decimal(net_capital_gain)
        ti_minus_gain = subtract(taxable_income_decimal, net_cap_gain)
        taxable_income_for_limit = max_decimal(Decimal("0"), ti_minus_gain)
        breakdown.taxable_income_limit = multiply(taxable_income_for_limit, qbi_rate)

        # Step 6: Final QBI deduction is lesser of per-business total and TI limit
        breakdown.final_qbi_deduction = min_decimal(
            total_limited_deduction, breakdown.taxable_income_limit
        )

        # Ensure non-negative and round to cents
        breakdown.final_qbi_deduction = money(max_decimal(Decimal("0"), breakdown.final_qbi_deduction))

        return breakdown
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestPerBusinessWageLimitation -v`
Expected: PASS

**Step 4: Run existing QBI tests to ensure no regressions**

Run: `pytest tests/test_qbi_calculator.py -v`
Expected: All existing tests PASS

**Step 5: Commit**

```bash
git add src/calculator/qbi_calculator.py
git commit -m "feat(qbi): implement per-business W-2 wage limitation per IRC §199A(b)(2)(B)"
```

---

### Task 5: Add Tests for UBIA Alternative Calculation

**Files:**
- Test: `tests/test_qbi_w2_wage_limitation.py`

**Step 1: Write the test**

Add to `tests/test_qbi_w2_wage_limitation.py`:

```python
class TestUBIAAlternativeCalculation:
    """Tests for 25% W-2 + 2.5% UBIA alternative calculation."""

    def test_ubia_alternative_greater_than_50_pct_wages(self):
        """
        When 25% W-2 + 2.5% UBIA > 50% W-2, use the greater amount.

        W-2 wages: $20K → 50% = $10K, 25% = $5K
        UBIA: $400K → 2.5% = $10K
        25% + 2.5% = $15K (greater than $10K)
        """
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.S_CORPORATION,
            entity_name="Capital-Heavy Business",
            entity_ein="33-3333333",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=20000.0,
            ubia_for_qbi=400000.0,  # Large UBIA
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=300000.0,  # Above threshold
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        biz = result.business_details[0]

        # 50% of W-2 = $10K
        assert biz.wage_limit_50_pct == Decimal("10000")

        # 25% of W-2 + 2.5% of UBIA = $5K + $10K = $15K
        assert biz.wage_limit_25_2_5_pct == Decimal("15000")

        # Greater of the two = $15K
        assert biz.wage_limitation == Decimal("15000")

        # Limited deduction = min($20K tentative, $15K limit) = $15K
        assert biz.limited_deduction == Decimal("15000")
```

**Step 2: Run test**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestUBIAAlternativeCalculation -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_qbi_w2_wage_limitation.py
git commit -m "test(qbi): add UBIA alternative calculation test"
```

---

### Task 6: Add Tests for Phase-In Range

**Files:**
- Test: `tests/test_qbi_w2_wage_limitation.py`

**Step 1: Write the test**

Add to `tests/test_qbi_w2_wage_limitation.py`:

```python
class TestPhaseInRangePerBusiness:
    """Tests for partial wage limitation in phase-in range."""

    def test_phase_in_partial_limitation(self):
        """
        In phase-in range, wage limitation is applied proportionally per business.

        Single threshold: $197,300 start, $247,300 end ($50K range)
        At $222,300 taxable income: 50% through phase-in

        Business: $100K QBI, $10K W-2 wages
        Tentative: $20K (20% of $100K)
        Wage limit: $5K (50% of $10K)
        Reduction: $15K ($20K - $5K)
        Phased reduction: $7,500 (50% × $15K)
        Limited: $12,500 ($20K - $7,500)
        """
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Phase-In Business",
            entity_ein="44-4444444",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=10000.0,
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        # Exactly 50% through phase-in: ($197,300 + $247,300) / 2 = $222,300
        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=222300.0,
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        assert result.phase_in_ratio == pytest.approx(Decimal("0.5"), rel=0.01)

        biz = result.business_details[0]
        assert biz.tentative_deduction == Decimal("20000")
        assert biz.wage_limitation == Decimal("5000")
        # Limited = $20K - (50% × $15K) = $12,500
        assert biz.limited_deduction == pytest.approx(Decimal("12500"), rel=0.01)
```

**Step 2: Run test**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestPhaseInRangePerBusiness -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_qbi_w2_wage_limitation.py
git commit -m "test(qbi): add phase-in range per-business limitation test"
```

---

### Task 7: Add Warning Generation Method

**Files:**
- Modify: `src/calculator/qbi_calculator.py` (add get_qbi_warnings method)
- Test: `tests/test_qbi_w2_wage_limitation.py`

**Step 1: Write the failing test**

Add to `tests/test_qbi_w2_wage_limitation.py`:

```python
class TestQBIWarnings:
    """Tests for QBI warning generation."""

    def test_scorp_with_zero_wages_generates_warning(self):
        """S-corp with QBI but $0 W-2 wages should generate warning."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.S_CORPORATION,
            entity_name="Zero Wage S-Corp",
            entity_ein="55-5555555",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=0.0,  # No wages!
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=150000.0,  # Below threshold for now
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        warnings = calculator.get_qbi_warnings(result)

        assert len(warnings) >= 1
        assert "Zero Wage S-Corp" in warnings[0]
        assert "$0 W-2 wages" in warnings[0]
        assert "K-1 Box 17 Code V" in warnings[0]

    def test_partnership_above_threshold_with_zero_wages_generates_warning(self):
        """Partnership above threshold with $0 wages should warn about limitation."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="Zero Wage Partnership",
            entity_ein="66-6666666",
            ordinary_business_income=100000.0,
            qbi_ordinary_income=100000.0,
            w2_wages_for_qbi=0.0,
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(schedule_k1_forms=[k1]),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=300000.0,  # Above threshold
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        warnings = calculator.get_qbi_warnings(result)

        assert len(warnings) >= 1
        assert "Zero Wage Partnership" in warnings[0]
        assert "$0 W-2 wage limitation" in warnings[0]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestQBIWarnings -v`
Expected: FAIL with "AttributeError: 'QBICalculator' object has no attribute 'get_qbi_warnings'"

**Step 3: Write the implementation**

Add to `QBICalculator` class in `src/calculator/qbi_calculator.py`:

```python
    def get_qbi_warnings(self, breakdown: QBIBreakdown) -> list[str]:
        """
        Generate warnings for QBI calculation issues.

        Key warnings:
        1. S-corp shareholders with QBI but $0 W-2 wages
        2. Businesses with $0 wage limitation when above threshold
        """
        warnings = []

        for biz in breakdown.business_details:
            # Warning 1: S-corp with QBI but no W-2 wages
            if biz.business_type == "s_corporation" and biz.w2_wages == Decimal("0"):
                if biz.qualified_business_income > Decimal("0"):
                    warnings.append(
                        f"S-corporation '{biz.business_name}' has QBI of "
                        f"${to_float(biz.qualified_business_income):,.2f} but $0 W-2 wages reported. "
                        "This may limit your QBI deduction if taxable income exceeds threshold. "
                        "Verify K-1 Box 17 Code V for W-2 wages."
                    )

            # Warning 2: Zero wage limitation above threshold
            if not breakdown.is_below_threshold:
                if biz.qualified_business_income > Decimal("0") and biz.wage_limitation == Decimal("0"):
                    warnings.append(
                        f"Business '{biz.business_name}' has $0 W-2 wage limitation. "
                        f"Your QBI deduction is reduced. "
                        f"W-2 wages: ${to_float(biz.w2_wages):,.2f}, "
                        f"UBIA: ${to_float(biz.ubia):,.2f}."
                    )

        return warnings
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestQBIWarnings -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/calculator/qbi_calculator.py tests/test_qbi_w2_wage_limitation.py
git commit -m "feat(qbi): add warning generation for S-corp owners with missing W-2 wages"
```

---

### Task 8: Add Edge Case Tests

**Files:**
- Test: `tests/test_qbi_w2_wage_limitation.py`

**Step 1: Write the tests**

Add to `tests/test_qbi_w2_wage_limitation.py`:

```python
class TestQBIEdgeCases:
    """Edge case tests for per-business QBI calculation."""

    def test_sole_proprietorship_no_wage_limit_below_threshold(self):
        """Sole prop below threshold should get full 20% (no wage limitation)."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=50000.0,
                self_employment_expenses=0.0,
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=50000.0,
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        assert len(result.business_details) == 1
        biz = result.business_details[0]
        assert biz.business_type == "sole_proprietorship"
        assert biz.limited_deduction == Decimal("10000")  # Full 20%

    def test_mixed_se_and_k1_businesses(self):
        """Mixed self-employment and K-1 income should create separate businesses."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        k1 = ScheduleK1(
            k1_type=K1SourceType.PARTNERSHIP,
            entity_name="K1 Business",
            entity_ein="77-7777777",
            ordinary_business_income=30000.0,
            qbi_ordinary_income=30000.0,
            w2_wages_for_qbi=0.0,
            ubia_for_qbi=0.0,
            is_sstb=False,
        )

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(
                self_employment_income=20000.0,
                self_employment_expenses=0.0,
                schedule_k1_forms=[k1],
            ),
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=50000.0,
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        # Should have 2 businesses
        assert len(result.business_details) == 2

        # First is Schedule C
        assert result.business_details[0].business_name == "Self-Employment (Schedule C)"
        assert result.business_details[0].qualified_business_income == Decimal("20000")

        # Second is K-1
        assert result.business_details[1].business_name == "K1 Business"
        assert result.business_details[1].qualified_business_income == Decimal("30000")

        # Total QBI = $50K, deduction = $10K
        assert result.final_qbi_deduction == Decimal("10000")

    def test_no_qbi_returns_empty_business_details(self):
        """No QBI income should return empty business_details."""
        config = TaxYearConfig.for_2025()
        calculator = QBICalculator()

        tax_return = TaxReturn(
            tax_year=2025,
            taxpayer=TaxpayerInfo(
                first_name="Test",
                last_name="User",
                filing_status=FilingStatus.SINGLE,
            ),
            income=Income(wages=100000.0),  # Only W-2 wages, no QBI
            deductions=Deductions(use_standard_deduction=True),
            credits=TaxCredits(),
        )

        result = calculator.calculate(
            tax_return=tax_return,
            taxable_income_before_qbi=100000.0,
            net_capital_gain=0.0,
            filing_status="single",
            config=config,
        )

        assert len(result.business_details) == 0
        assert result.final_qbi_deduction == Decimal("0")
```

**Step 2: Run tests**

Run: `pytest tests/test_qbi_w2_wage_limitation.py::TestQBIEdgeCases -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_qbi_w2_wage_limitation.py
git commit -m "test(qbi): add edge case tests for per-business QBI"
```

---

### Task 9: Run Full Test Suite and Verify No Regressions

**Files:**
- None (verification only)

**Step 1: Run all QBI-related tests**

Run: `pytest tests/test_qbi_calculator.py tests/test_qbi_w2_wage_limitation.py tests/test_form_8995.py -v`
Expected: All tests PASS

**Step 2: Run form integration tests**

Run: `pytest tests/test_form_integration.py -v`
Expected: All tests PASS

**Step 3: Run engine tests to verify integration**

Run: `pytest tests/ -k "qbi or QBI" -v`
Expected: All tests PASS

**Step 4: Commit final verification**

```bash
git add -A
git commit -m "chore(qbi): verify all tests pass after per-business W-2 wage limitation"
```

---

### Task 10: Update Documentation

**Files:**
- Modify: `docs/plans/2026-02-25-qbi-w2-wage-limitation-design.md` (mark as implemented)

**Step 1: Update design doc status**

Change line 5 from:
```markdown
**Status:** Approved
```
to:
```markdown
**Status:** Implemented
```

**Step 2: Commit**

```bash
git add docs/plans/2026-02-25-qbi-w2-wage-limitation-design.md
git commit -m "docs: mark QBI W-2 wage limitation design as implemented"
```

---

## Summary

| Task | Description | Tests |
|------|-------------|-------|
| 1 | Add QBIBusinessDetail dataclass | 2 |
| 2 | Add business_details to QBIBreakdown | 2 |
| 3 | Test per-business W-2 wage limitation | 1 |
| 4 | Implement per-business calculation logic | 0 (uses Task 3 test) |
| 5 | Test UBIA alternative calculation | 1 |
| 6 | Test phase-in range per-business | 1 |
| 7 | Add warning generation method | 2 |
| 8 | Add edge case tests | 3 |
| 9 | Verify no regressions | 0 (runs existing tests) |
| 10 | Update documentation | 0 |

**Total new tests: 12**
**Total commits: 10**
