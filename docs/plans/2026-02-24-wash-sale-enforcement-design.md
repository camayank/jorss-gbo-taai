# Wash Sale Enforcement Design Document

**Date:** 2026-02-24
**Status:** Approved
**Approach:** Enhance Existing Form 8949 Methods

## Overview

Implement wash sale enforcement per IRC §1091 by enhancing the existing Form 8949 infrastructure. This addresses a critical compliance gap where wash sales are detected but not enforced.

## Requirements

1. **Auto-apply wash sale adjustments** when detected (30-day window rule)
2. **Cascade basis** to replacement shares
3. **Transfer holding period** to replacement shares per IRC §1223
4. **Flag IRA purchases** as permanently disallowed losses

## Existing Infrastructure

The codebase already has partial wash sale support in `src/models/form_8949.py`:

- `WashSaleInfo` model with `disallowed_loss` and `basis_adjustment` fields
- `SecurityTransaction.apply_wash_sale()` for manual adjustments
- `SecuritiesPortfolio.detect_wash_sales()` for detection (not enforcement)
- `AdjustmentCode.W` enum value for Form 8949 reporting

## Design

### Data Model Changes

**File: `src/models/form_8949.py`**

Extend `WashSaleInfo` with new fields:

```python
class WashSaleInfo(BaseModel):
    # Existing fields
    disallowed_loss: float = 0.0
    basis_adjustment: float = 0.0
    related_transaction_id: Optional[str] = None

    # New fields
    holding_period_adjustment_days: int = 0  # Days to add to replacement shares
    is_permanent_disallowance: bool = False  # True if replacement in IRA
    replacement_account_type: Optional[str] = None  # "taxable", "ira", "401k"
```

Add field to `SecurityTransaction`:

```python
class SecurityTransaction(BaseModel):
    # ... existing fields ...
    adjusted_holding_period_days: int = 0  # Additional days from wash sale tacking
```

### Enforcement Logic

**File: `src/models/form_8949.py`**

Add `enforce_wash_sales()` method to `SecuritiesPortfolio`:

```python
def enforce_wash_sales(self) -> List[WashSaleInfo]:
    """
    Detect and automatically apply wash sale adjustments.
    Per IRC §1091:
    1. Disallow loss on sale
    2. Add disallowed loss to basis of replacement shares
    3. Tack holding period from sold shares to replacement
    4. Flag permanent disallowance for IRA replacements
    """
    wash_sales = self.detect_wash_sales()

    for ws in wash_sales:
        loss_txn = self._find_transaction(ws.related_transaction_id)
        replacement_txn = self._find_replacement(loss_txn)

        # Apply disallowance to loss transaction
        loss_txn.apply_wash_sale(ws)

        # Cascade basis to replacement shares
        replacement_txn.cost_basis += ws.disallowed_loss

        # Tack holding period
        if not ws.is_permanent_disallowance:
            replacement_txn.adjusted_holding_period_days += ws.holding_period_adjustment_days

    return wash_sales
```

### IRA Permanent Disallowance

Enhance `detect_wash_sales()` to identify IRA replacements:

```python
def detect_wash_sales(self) -> List[WashSaleInfo]:
    # ... existing detection logic ...

    for loss_sale in loss_sales:
        replacement = self._find_replacement_in_window(loss_sale)
        if replacement:
            is_permanent = replacement.account_type in ("ira", "roth_ira", "401k", "403b")

            wash_sale_info = WashSaleInfo(
                disallowed_loss=abs(loss_sale.gain_or_loss),
                basis_adjustment=abs(loss_sale.gain_or_loss),
                related_transaction_id=loss_sale.id,
                holding_period_adjustment_days=loss_sale.holding_period_days,
                is_permanent_disallowance=is_permanent,
                replacement_account_type=replacement.account_type,
            )
            results.append(wash_sale_info)

    return results
```

Add user warning method:

```python
def get_permanent_disallowance_warnings(self) -> List[str]:
    """Return warnings for permanently disallowed losses (IRA wash sales)."""
    warnings = []
    for ws in self.wash_sales:
        if ws.is_permanent_disallowance:
            warnings.append(
                f"Loss of ${ws.disallowed_loss:,.2f} permanently disallowed - "
                f"replacement purchased in {ws.replacement_account_type}"
            )
    return warnings
```

## Testing Strategy

**Test file: `tests/test_wash_sale_enforcement.py`**

### Basic Enforcement Tests
- Sale followed by repurchase within 30 days → loss disallowed
- Repurchase before sale within 30 days → loss disallowed
- Sale with repurchase at day 31 → no wash sale
- No repurchase → no wash sale

### Basis Cascade Tests
- Verify replacement shares receive disallowed loss amount added to basis
- Multiple wash sales in sequence cascade correctly

### Holding Period Tests
- Verify holding period days transfer to replacement shares
- Long-term sale + short-term replacement → combined holding period

### IRA Tests
- Taxable sale + IRA repurchase → permanent disallowance flagged
- Taxable sale + Roth IRA repurchase → permanent disallowance
- Warning messages generated correctly

### Edge Cases
- Partial repurchase (100 shares sold, 50 repurchased)
- Multiple replacement lots
- Same-day transactions

## Files Changed

| File | Action | Estimated Lines |
|------|--------|-----------------|
| `src/models/form_8949.py` | Modify | ~80 |
| `tests/test_wash_sale_enforcement.py` | Create | ~150 |

**Total: ~230 lines**

## Out of Scope

- Multi-year wash sale tracking (shares held across tax years)
- "Substantially identical" determination beyond ticker matching
- Options and mutual fund equivalence rules
- Tax lot optimization to avoid wash sales

These are deferred to future enhancements.

## IRS References

- IRC §1091 - Wash sale rule
- IRC §1223 - Holding period tacking
- IRS Publication 550 - Investment Income and Expenses

## Approval

- [x] Data model design approved
- [x] Enforcement logic approved
- [x] IRA handling approved
- [x] Testing strategy approved
- [x] Complete design approved

Ready for implementation planning.
