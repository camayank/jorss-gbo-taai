# QBI W-2 Wage Limitation Design Document

**Date:** 2026-02-25
**Status:** Implemented
**Approach:** Refactor QBICalculator for Per-Business Limitation

## Overview

Fix the QBI W-2 wage limitation to apply per qualified trade or business per IRC §199A(b)(2)(B). Currently, the QBICalculator aggregates all W-2 wages before applying the limitation, which produces incorrect results when multiple businesses have different wage/QBI ratios.

## Problem

IRC §199A(b)(2)(B) requires the W-2 wage limitation to be applied **per qualified trade or business**, not in aggregate:

> The amount determined under this paragraph with respect to any qualified trade or business shall not exceed the greater of—
> (i) 50 percent of the W–2 wages with respect to such qualified trade or business, or
> (ii) the sum of 25 percent of the W–2 wages with respect to such qualified trade or business, plus 2.5 percent of the unadjusted basis immediately after acquisition of all qualified property.

The current `QBICalculator` aggregates wages from all businesses and applies a single limitation, which is non-compliant.

## Design

### Data Model Changes

**File: `src/calculator/qbi_calculator.py`**

Add new dataclass for per-business tracking:

```python
@dataclass
class QBIBusinessDetail:
    """Per-business QBI breakdown for W-2 wage limitation."""

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

Update `QBIBreakdown` to include per-business details:

```python
@dataclass
class QBIBreakdown:
    # ... existing fields ...

    # NEW: Per-business breakdown for IRC §199A(b)(2)(B) compliance
    business_details: list = field(default_factory=list)  # List[QBIBusinessDetail]
```

### Per-Business Calculation Logic

**File: `src/calculator/qbi_calculator.py`**

Refactor `calculate()` method to:

1. Build per-business details from self-employment and K-1 income
2. Apply wage limitation per business using IRC §199A(b)(2)(B) rules
3. Aggregate limited amounts for final deduction

Key algorithm:
- Self-employment (Schedule C) counts as one business (no W-2 wages)
- Each K-1 form counts as a separate business with its own W-2 wages/UBIA
- Calculate wage limitation per business
- Sum limited deductions for total QBI deduction

### Validation & Warnings

Add `get_qbi_warnings()` method to generate warnings for:

1. **S-corp with $0 W-2 wages**: S-corporation shareholders with QBI income but no W-2 wages reported may have incorrect limitation applied
2. **Zero wage limitation above threshold**: Businesses with $0 W-2 wages and $0 UBIA when taxpayer is above threshold

### Warning Message Examples

```
S-corporation 'ABC Corp' has QBI of $100,000 but $0 W-2 wages reported.
This may limit your QBI deduction if taxable income exceeds threshold.
Verify K-1 Box 17 Code V for W-2 wages.
```

## Testing Strategy

**New file: `tests/test_qbi_w2_wage_limitation.py`**

### Test Categories (~15 tests)

1. **Per-Business Limitation Tests**
   - Two businesses with different W-2 wage ratios
   - Verify per-business limitation vs aggregate

2. **S-Corp Specific Tests**
   - S-corp K-1 with W-2 wages → full deduction
   - S-corp K-1 with $0 W-2 wages (high income) → limited to $0

3. **UBIA Interaction Tests**
   - 25% W-2 + 2.5% UBIA formula vs 50% W-2
   - Greater-of logic verification

4. **Phase-In Range Tests**
   - Multiple businesses in phase-in range
   - Partial limitation applied per-business

5. **Warning Generation Tests**
   - S-corp with $0 W-2 wages → warning generated
   - Partnership with $0 wages (above threshold) → warning

## Files Changed

| File | Action | Estimated Lines |
|------|--------|-----------------|
| `src/calculator/qbi_calculator.py` | Modify | ~100 |
| `tests/test_qbi_w2_wage_limitation.py` | Create | ~200 |

**Total: ~300 lines**

## Out of Scope

- Form 8995-A generation (existing Form8995 model handles this)
- QBI aggregation elections (Treas. Reg. §1.199A-4)
- Safe harbor for rental real estate (Rev. Proc. 2019-38)
- Patron reduction for cooperatives

## IRS References

- IRC §199A(b)(2)(B) - W-2 wage limitation
- Treas. Reg. §1.199A-2 - W-2 wage calculation rules
- Form 8995-A Instructions - Standard calculation worksheet

## Approval

- [x] Data model design approved
- [x] Per-business calculation logic approved
- [x] Validation/warnings design approved
- [x] Testing strategy approved
- [x] Complete design approved

Ready for implementation planning.
