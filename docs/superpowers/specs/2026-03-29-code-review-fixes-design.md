# Code Review Fixes — Design Spec
**Date:** 2026-03-29
**Scope:** Critical + Important issues from post-commit code review
**Approach:** Surgical fixes — correct each issue in-place, minimal change surface

---

## Background

A code review of the last 5 commits (`1206dfaa..c4740695`) found 3 Critical bugs that silently prevent payment persistence from working, plus 6 Important issues covering security, data integrity, and input validation.

---

## Section 1: Payment Service Fixes

**File:** `src/cpa_panel/payments/payment_service.py`

### 1.1 Module-level imports (I-3)
Move `import sqlite3, json` from inside `__init__`, `_persist_invoice`, `_persist_payment`, and `_persist_link` to the module-level imports at the top of the file alongside `import os`.

### 1.2 Fix wrong attribute names in persist methods (C-1, C-2)

| Method | Current (broken) | Fixed |
|--------|------------------|-------|
| `_persist_invoice` line 76 | `invoice.invoice_id` | `invoice.id` |
| `_persist_payment` line 84 | `payment.payment_id` | `payment.id` |
| `_persist_link` line 92 | `link.link_id` | `link.id` |
| `_persist_link` line 92 | `getattr(link, 'code', '')` | `link.link_code` |

Each of these raises `AttributeError` at runtime because the dataclasses define `.id` and `.link_code`, not `.invoice_id`, `.payment_id`, `.link_id`, or `.code`. The errors are currently swallowed silently.

### 1.3 Replace silent exception suppression with logging (I-2)

All 4 `except Exception: pass` blocks in `create_invoice`, `record_payment`, `create_payment_link`, and `update_payment_link` become:

```python
# _persist_invoice
except Exception as e:
    logger.warning("Persistence failed for invoice %s: %s", invoice.id, e)

# _persist_payment
except Exception as e:
    logger.warning("Persistence failed for payment %s: %s", payment.id, e)

# _persist_link (2 call sites: create + update)
except Exception as e:
    logger.warning("Persistence failed for payment link %s: %s", link.id, e)
```

The call still returns normally (best-effort persistence, degraded not broken), but failures are now visible in logs.

### 1.4 Implement DB hydration on startup (I-1)

Add a `_load_from_db()` method and call it at the end of `__init__`. It:

1. Opens a read connection to the SQLite DB
2. Reads all rows from `pay_invoices`, `pay_payments`, and `pay_links`
3. For each row, deserializes `data_json` and reconstructs the appropriate dataclass
4. Populates `_invoices`, `_payments`, `_payment_links`, and `_links_by_code`
5. Sets `_db_loaded = True`
6. Wraps each row in a `try/except` — a single corrupted row logs a warning and is skipped rather than crashing startup

**Deserialization strategy:** Use `vars()`-compatible reconstruction. Since the models are plain dataclasses (not Pydantic), reconstruct with `Invoice(**{k: v for k, v in data.items() if k in Invoice.__dataclass_fields__})`.

Field conversions required:
- `UUID` fields (e.g. `id`, `firm_id`, `cpa_id`, `client_id`): `UUID(value) if value else None`
- `datetime` fields (e.g. `created_at`, `updated_at`, `completed_at`): `datetime.fromisoformat(value) if value else None`
- `date` fields (e.g. `issue_date`, `due_date`): `date.fromisoformat(value) if value else None`
- `Enum` fields (e.g. `status`, `payment_method`): reconstruct from `.value` string using the enum class
- `list` fields (e.g. `line_items`): reconstruct each item as a `LineItem(**item)`

---

## Section 2: CPA Signup Form

**File:** `src/web/templates/auth/signup.html`

### 2.1 Add firm name field (C-3)

Add a `<div id="firm-name-group">` containing:
```html
<label for="firm-name">Firm Name</label>
<input type="text" name="firmName" id="firm-name" placeholder="Your firm name">
```

- Hidden by default (`display: none`)
- Shown when `?type=cpa` is present in the URL
- `required` attribute set programmatically when shown
- JS reads `new URLSearchParams(window.location.search).get('type') === 'cpa'` on `DOMContentLoaded`

### 2.2 Fix post-signup redirect

The hidden `<input name="next" id="next-url">` currently hardcodes `/intelligent-advisor`. Update the JS initialization to:

```js
const nextParam = new URLSearchParams(window.location.search).get('next');
if (nextParam) document.getElementById('next-url').value = nextParam;
```

CPAs arriving via `/signup?type=cpa&next=/cpa/onboarding` will be redirected to the CPA onboarding wizard after registration.

---

## Section 3: Frontend & API Guards

### 3.1 Remove anonymous role from client nav condition (I-4)

**File:** `src/web/templates/base_modern.html`

```jinja2
{# Before #}
{% if user and user.role in ('client', 'firm_client', 'direct_client', 'anonymous') %}

{# After #}
{% if user and user.role in ('client', 'firm_client', 'direct_client') %}
```

Unauthenticated users (role `anonymous` or `user`) no longer see the client navigation bar with links to `/results`, `/filing-package`, `/refund-tracker`, etc.

### 3.2 Rate lookup input validation (I-5)

**File:** `src/web/app.py` — `/api/tools/tax-rate-lookup` handler

Add at the top of the handler before any calculation:

```python
VALID_STATUSES = {"single", "married_joint", "married_separate", "head_of_household"}
if filing_status not in VALID_STATUSES:
    raise HTTPException(status_code=422, detail=f"Invalid filing_status. Must be one of: {sorted(VALID_STATUSES)}")
income = max(0.0, income)
```

### 3.3 W-4 calculator input guards (I-6)

**File:** `src/web/app.py` — `/api/tools/w4-calculator` handler

Add at the top of the handler before any calculation:

```python
annual_income = max(0.0, annual_income)
dependents = max(0, dependents)
other_income = max(-200_000.0, other_income)  # allows business losses, caps abuse
```

---

## What Is Not In Scope

- Stripe SDK integration (separate billing track)
- JS code splitting / 497KB monolith (P2 UX item)
- Minor issues: nav accessibility, refund tracker disclaimer, test additions
- Any changes to the tax engine or CPA dashboard

---

## Files Changed

| File | Changes |
|------|---------|
| `src/cpa_panel/payments/payment_service.py` | Fix imports, attribute names, exception logging, add `_load_from_db()` |
| `src/web/templates/auth/signup.html` | Add firm name field, fix `next` redirect |
| `src/web/templates/base_modern.html` | Remove `anonymous` from nav condition |
| `src/web/app.py` | Input validation on 2 API endpoints |

**Total estimated lines changed:** ~60 lines modified, ~50 lines added (mostly `_load_from_db()`)
