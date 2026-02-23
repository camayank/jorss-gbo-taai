# Critical Tax Fixes Design Document

**Date:** 2026-02-24
**Status:** Approved
**Approach:** Minimal Surgical Fixes (Approach A)

## Overview

This document describes four critical tax calculation fixes required for 2025 tax year compliance. These are high-priority fixes that address calculation accuracy issues identified during domain analysis.

## Fixes Summary

| Fix | Issue | IRS Reference | Severity |
|-----|-------|---------------|----------|
| EITC Phase-In | Missing phase-in calculation | Pub. 596 | Critical |
| Educator Expense Cap | No $300/$600 limit enforced | IRC §62(a)(2)(D) | High |
| SECURE 2.0 RMD Ages | Outdated age thresholds | SECURE Act 2.0 | Critical |
| Form 8867 | No due diligence checklist | IRC §6695(g) | High |

## Fix 1: EITC Phase-In Calculation

### Problem

Lines 2637-2639 in `engine.py` return `max_credit` without calculating the phase-in. EITC builds up gradually based on earned income × phase-in rate before reaching the plateau.

### IRS Rules (Pub. 596)

| Children | Phase-In Rate | Earned Income Threshold |
|----------|---------------|------------------------|
| 0 | 7.65% | $8,490 |
| 1 | 34.00% | $12,730 |
| 2 | 40.00% | $17,880 |
| 3+ | 45.00% | $17,880 |

### Changes

**File: `src/calculator/tax_year_config.py`**

Add new fields to `TaxYearConfig` dataclass:

```python
eitc_phase_in_rate: Optional[Dict[int, float]] = None  # {0: 0.0765, 1: 0.34, 2: 0.40, 3: 0.45}
eitc_phase_in_end: Optional[Dict[int, float]] = None   # {0: 8490, 1: 12730, 2: 17880, 3: 17880}
```

Add values in `for_2025()` method:

```python
eitc_phase_in_rate = {0: 0.0765, 1: 0.34, 2: 0.40, 3: 0.45}
eitc_phase_in_end = {0: 8490.0, 1: 12730.0, 2: 17880.0, 3: 17880.0}
```

**File: `src/calculator/engine.py`**

Replace lines 2637-2639 in `_calculate_eitc()`:

```python
# Get phase-in parameters
phase_in_end = self.config.eitc_phase_in_end.get(num_children, 0) if self.config.eitc_phase_in_end else 0
phase_in_rate = self.config.eitc_phase_in_rate.get(num_children, 0) if self.config.eitc_phase_in_rate else 0

if earned_income <= phase_in_end:
    # Phase-in range: Credit = earned_income × phase_in_rate, capped at max
    credit = earned_income * phase_in_rate
    return float(money(min(credit, max_credit)))
elif income_for_eitc <= phaseout_start:
    # Plateau range: Full max credit
    return max_credit
# ... existing phaseout logic continues unchanged
```

## Fix 2: Educator Expense Deduction Cap

### Problem

Line 443 in `deductions.py` adds `self.educator_expenses` without enforcing the $300/$600 cap per IRC §62(a)(2)(D).

### IRS Rules

- Single educator: $300 maximum
- MFJ (two educators): $600 maximum ($300 each)
- Must be K-12 teacher, instructor, counselor, principal, or aide
- Must work 900+ hours during school year

### Changes

**File: `src/models/deductions.py`**

Update `get_total_adjustments()` method signature to accept `filing_status`:

```python
def get_total_adjustments(
    self,
    magi: float = 0.0,
    filing_status: str = "single",
    # ... existing params
) -> float:
```

Add educator expense cap logic before the return statement:

```python
# Cap educator expenses per IRC §62(a)(2)(D)
# $300 per educator, $600 max for MFJ with two educators
if filing_status == "married_joint":
    educator_cap = 600.0
else:
    educator_cap = 300.0
educator_deduction = min(self.educator_expenses, educator_cap)
```

Update return statement to use `educator_deduction` instead of `self.educator_expenses`.

Add helper property for user notification:

```python
def get_educator_expense_excess(self, filing_status: str = "single") -> float:
    """Amount of educator expenses exceeding the cap (for user notification)."""
    cap = 600.0 if filing_status == "married_joint" else 300.0
    return max(0, self.educator_expenses - cap)
```

## Fix 3: SECURE Act 2.0 RMD Age Thresholds

### Problem

RMD (Required Minimum Distribution) starting ages changed under SECURE 2.0. Current implementation may use outdated thresholds.

### IRS Rules (SECURE 2.0)

| Birth Year | RMD Starting Age |
|------------|------------------|
| 1950 or earlier | 72 |
| 1951-1959 | 73 |
| 1960 or later | 75 |

**Penalty Changes:**
- RMD failure penalty reduced from 50% to 25%
- If corrected within 2 years: penalty further reduced to 10%

### Changes

**File: `src/calculator/tax_year_config.py`**

Add new fields:

```python
rmd_failure_penalty_rate: float = 0.25  # Reduced from 50% per SECURE 2.0
rmd_corrected_penalty_rate: float = 0.10  # If corrected within correction window
```

**File: `src/models/form_5329.py`**

Update class constants:

```python
RMD_PENALTY_RATE: ClassVar[float] = 0.25  # Changed from 0.50
RMD_CORRECTED_PENALTY_RATE: ClassVar[float] = 0.10  # New
```

Add helper method:

```python
def get_rmd_starting_age(self, birth_year: int) -> int:
    """Get RMD starting age based on birth year per SECURE 2.0."""
    if birth_year <= 1950:
        return 72
    elif birth_year <= 1959:
        return 73
    else:
        return 75
```

Add field for correction tracking:

```python
rmd_corrected_timely: bool = Field(
    default=False,
    description="RMD shortfall corrected within correction window (10% penalty)"
)
```

Update penalty calculation:

```python
def calculate_rmd_penalty(self, shortfall: float) -> float:
    """Calculate RMD failure penalty with SECURE 2.0 rates."""
    if self.rmd_corrected_timely:
        return shortfall * self.RMD_CORRECTED_PENALTY_RATE
    return shortfall * self.RMD_PENALTY_RATE
```

## Fix 4: Form 8867 Due Diligence Checklist (Scaffold)

### Problem

Paid preparers claiming EITC, CTC, AOTC, or HOH must complete Form 8867. No implementation exists. Penalty is $600 per failure (2025).

### IRS Requirements

- Part I: Due diligence questions (did you verify eligibility?)
- Part II: Knowledge documentation
- Part III: Record retention acknowledgment
- Applies to: EITC, CTC/ACTC/ODC, AOTC, HOH filing status

### Changes

**New File: `src/models/form_8867.py`**

Create scaffold with:

1. `CreditType` enum for credits requiring due diligence
2. `DueDiligenceQuestion` model for individual questions
3. `Form8867` model with:
   - Preparer identification fields
   - Credits claimed tracking
   - Part I: Due diligence requirement flags
   - Part II: Knowledge documentation fields
   - Part III: Record retention acknowledgment
   - `validate_completeness()` method
   - `calculate_potential_penalty()` method

This is a **scaffold only** - full workflow integration is Phase 2.

## Testing Strategy

### Unit Tests Required

1. **EITC Phase-In Tests:**
   - Zero earned income → $0 credit
   - Income at phase-in threshold boundary
   - Income in plateau range → max credit
   - Income in phaseout range
   - All child counts (0, 1, 2, 3+)

2. **Educator Expense Tests:**
   - Single filer at/below/above $300
   - MFJ at/below/above $600
   - Zero expenses
   - Excess calculation property

3. **SECURE 2.0 RMD Tests:**
   - Birth year 1950 → age 72
   - Birth year 1955 → age 73
   - Birth year 1960 → age 75
   - Birth year 1965 → age 75
   - Penalty calculation at 25%
   - Corrected penalty at 10%

4. **Form 8867 Tests:**
   - Validation with all credits claimed
   - Validation with partial completion
   - Penalty calculation

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/calculator/tax_year_config.py` | Modify | ~25 |
| `src/calculator/engine.py` | Modify | ~20 |
| `src/models/deductions.py` | Modify | ~15 |
| `src/models/form_5329.py` | Modify | ~35 |
| `src/models/form_8867.py` | Create | ~150 |

**Total: ~245 lines**

## Out of Scope

The following are explicitly NOT in scope for this design:

- Form 8867 workflow integration with filing process
- Preparer mode UI for due diligence completion
- Architecture refactoring or centralized rules engine
- Migration utilities (fresh deployment confirmed)

These items are deferred to Phase 2.

## Approval

- [x] EITC Phase-In design approved
- [x] Educator Expense Cap design approved
- [x] SECURE 2.0 RMD design approved
- [x] Form 8867 Scaffold design approved
- [x] Complete design approved

Ready for implementation planning.
