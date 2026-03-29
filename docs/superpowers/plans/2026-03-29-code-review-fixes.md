# Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 Critical persistence bugs in PaymentService, add DB hydration on startup, fix CPA signup firm name field, remove anonymous from client nav, and add input guards on two API endpoints.

**Architecture:** Surgical in-place fixes — no new abstractions, no file splits, no new dependencies. All changes are inside existing files. Test file `tests/cpa/test_payment_service.py` is new (no equivalent exists).

**Tech Stack:** Python 3.9, FastAPI, SQLite (sqlite3 stdlib), Jinja2 templates, pytest

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `src/cpa_panel/payments/payment_service.py` | Fix attribute names, imports, exception logging, add `_load_from_db` |
| Modify | `src/web/templates/auth/signup.html` | Add firmName input, fix next redirect |
| Modify | `src/web/templates/base_modern.html` | Remove `'anonymous'` from client nav condition |
| Modify | `src/web/app.py` | Add input validation to tax-rate-lookup and w4-calculator |
| Create | `tests/cpa/test_payment_service.py` | Unit tests for persist + load methods |
| Create | `tests/web/test_tools_api.py` | Unit tests for rate-lookup and w4-calculator validation |

---

### Task 1: Fix attribute names and exception logging in payment_service.py

**Files:**
- Modify: `src/cpa_panel/payments/payment_service.py:48-92,163-164,305-306,379-380,484-485`
- Create: `tests/cpa/test_payment_service.py`

- [ ] **Step 1: Write failing tests for _persist_invoice, _persist_payment, _persist_link**

```python
# tests/cpa/test_payment_service.py
import os
import sys
import sqlite3
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cpa_panel.payments.payment_service import PaymentService
from cpa_panel.payments.payment_models import Invoice, Payment, PaymentLink


@pytest.fixture
def svc(tmp_path):
    db = tmp_path / "test.db"
    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        return PaymentService()


def _row_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(str(db_path)) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_persist_invoice_writes_row(svc, tmp_path):
    """_persist_invoice must store a row using invoice.id, not invoice.invoice_id."""
    inv = Invoice(firm_id=uuid.uuid4(), cpa_id=uuid.uuid4())
    inv.add_line_item("Tax prep", 500.0)
    svc._persist_invoice(inv)
    assert _row_count(tmp_path / "test.db", "pay_invoices") == 1


def test_persist_payment_writes_row(svc, tmp_path):
    """_persist_payment must store a row using payment.id, not payment.payment_id."""
    pay = Payment(firm_id=uuid.uuid4(), cpa_id=uuid.uuid4(), amount=150.0)
    svc._persist_payment(pay)
    assert _row_count(tmp_path / "test.db", "pay_payments") == 1


def test_persist_link_writes_row_with_link_code(svc, tmp_path):
    """_persist_link must store a row using link.id and link.link_code."""
    link = PaymentLink(firm_id=uuid.uuid4(), cpa_id=uuid.uuid4(), name="Q1 Retainer")
    svc._persist_link(link)
    db = tmp_path / "test.db"
    with sqlite3.connect(str(db)) as conn:
        row = conn.execute("SELECT link_id, code FROM pay_links LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == str(link.id)           # link.id not link.link_id
    assert row[1] == link.link_code         # link.link_code not getattr(link,'code','')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
PYTHONPATH=src python -m pytest tests/cpa/test_payment_service.py -v 2>&1 | head -40
```

Expected: 3 FAILED with `AttributeError: 'Invoice' object has no attribute 'invoice_id'` (or similar).

- [ ] **Step 3: Fix payment_service.py**

Move module-level imports to the top of the file (replace lines 48-49 inline import with stdlib imports at module level), then fix all 3 attribute names, and replace all 4 silent `except Exception: pass` with logger calls.

Open `src/cpa_panel/payments/payment_service.py`. Make these changes:

**3a. Add `import sqlite3, json` and `from pathlib import Path` at module level** — after the existing `import os` line (line 8):

```python
import os
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
```

**3b. Remove the inline imports inside `__init__`, `_persist_invoice`, `_persist_payment`, `_persist_link`** — delete these lines (they appear as `import sqlite3, json` at lines 48, 72, 80, 88):

- Line 48: `import sqlite3, json` → delete
- Line 49: `from pathlib import Path` → delete
- Line 72: `import sqlite3, json` → delete
- Line 80: `import sqlite3, json` → delete
- Line 88: `import sqlite3, json` → delete

**3c. Fix `_persist_invoice` (line 75-76) — change `invoice.invoice_id` to `invoice.id`:**

```python
    def _persist_invoice(self, invoice):
        """Write-through cache: persist invoice to SQLite."""
        with sqlite3.connect(str(self._db_path)) as conn:
            data = invoice.model_dump() if hasattr(invoice, 'model_dump') else vars(invoice)
            conn.execute("INSERT OR REPLACE INTO pay_invoices (invoice_id, data_json, updated_at) VALUES (?, ?, ?)",
                         (str(invoice.id), json.dumps(data, default=str), datetime.now(timezone.utc).isoformat()))
```

**3d. Fix `_persist_payment` (line 83-84) — change `payment.payment_id` to `payment.id`:**

```python
    def _persist_payment(self, payment):
        """Write-through cache: persist payment to SQLite."""
        with sqlite3.connect(str(self._db_path)) as conn:
            data = payment.model_dump() if hasattr(payment, 'model_dump') else vars(payment)
            conn.execute("INSERT OR REPLACE INTO pay_payments (payment_id, data_json, updated_at) VALUES (?, ?, ?)",
                         (str(payment.id), json.dumps(data, default=str), datetime.now(timezone.utc).isoformat()))
```

**3e. Fix `_persist_link` (lines 90-92) — change `link.link_id` to `link.id` and `getattr(link, 'code', '')` to `link.link_code`:**

```python
    def _persist_link(self, link):
        """Write-through cache: persist payment link to SQLite."""
        with sqlite3.connect(str(self._db_path)) as conn:
            data = link.model_dump() if hasattr(link, 'model_dump') else vars(link)
            conn.execute("INSERT OR REPLACE INTO pay_links (link_id, code, data_json, updated_at) VALUES (?, ?, ?, ?)",
                         (str(link.id), link.link_code, json.dumps(data, default=str), datetime.now(timezone.utc).isoformat()))
```

**3f. Replace 4 silent `except Exception: pass` with logger warnings:**

Line 163-164 (in `create_invoice`):
```python
        self._invoices[invoice.id] = invoice
        try:
            self._persist_invoice(invoice)
        except Exception as e:
            logger.warning("Persistence failed for invoice %s: %s", invoice.id, e)
```

Line 304-306 (in `record_payment`):
```python
        self._payments[payment.id] = payment
        try:
            self._persist_payment(payment)
        except Exception as e:
            logger.warning("Persistence failed for payment %s: %s", payment.id, e)
```

Line 378-380 (in `create_payment_link`):
```python
        self._payment_links[link.id] = link
        self._links_by_code[link.link_code] = link.id
        try:
            self._persist_link(link)
        except Exception as e:
            logger.warning("Persistence failed for link %s: %s", link.id, e)
```

Line 483-485 (in `process_link_payment`):
```python
        self._payments[payment.id] = payment
        try:
            self._persist_payment(payment)
        except Exception as e:
            logger.warning("Persistence failed for payment %s: %s", payment.id, e)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
PYTHONPATH=src python -m pytest tests/cpa/test_payment_service.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
git add src/cpa_panel/payments/payment_service.py tests/cpa/test_payment_service.py
git commit -m "fix: correct attribute names in PaymentService persist methods

invoice_id→id, payment_id→id, link_id→id, code→link_code.
Also move imports to module level and log persistence failures."
```

---

### Task 2: Implement _load_from_db() in payment_service.py

**Files:**
- Modify: `src/cpa_panel/payments/payment_service.py`
- Modify: `tests/cpa/test_payment_service.py`

- [ ] **Step 1: Write the failing test for hydration**

Add to `tests/cpa/test_payment_service.py`:

```python
def test_load_from_db_restores_invoices(tmp_path):
    """After restart, a new PaymentService instance loads persisted invoices."""
    db = tmp_path / "test.db"
    firm = uuid.uuid4()
    cpa = uuid.uuid4()

    # First instance — create and persist
    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc1 = PaymentService()
        inv = svc1.create_invoice(
            firm_id=firm, cpa_id=cpa, cpa_name="Alice CPA", firm_name="Acme",
            client_name="Bob", client_email="bob@example.com",
            line_items=[{"description": "Tax prep", "amount": 800.0}],
        )
        inv_id = inv.id

    # Second instance — simulates restart
    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc2 = PaymentService()
        loaded = svc2.get_invoice(inv_id)

    assert loaded is not None
    assert loaded.id == inv_id
    assert loaded.client_name == "Bob"
    assert loaded.total_amount == 800.0


def test_load_from_db_restores_payments(tmp_path):
    """After restart, a new PaymentService loads persisted payments."""
    db = tmp_path / "test.db"
    firm = uuid.uuid4()
    cpa = uuid.uuid4()

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc1 = PaymentService()
        inv = svc1.create_invoice(
            firm_id=firm, cpa_id=cpa, cpa_name="Alice CPA", firm_name="Acme",
            client_name="Bob", client_email="bob@example.com",
            line_items=[{"description": "Tax prep", "amount": 500.0}],
        )
        _invoice, payment = svc1.record_payment(inv.id, 500.0)
        pay_id = payment.id

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc2 = PaymentService()
        loaded = svc2._payments.get(pay_id)

    assert loaded is not None
    assert loaded.amount == 500.0


def test_load_from_db_restores_payment_links(tmp_path):
    """After restart, a new PaymentService loads persisted payment links."""
    db = tmp_path / "test.db"
    firm = uuid.uuid4()
    cpa = uuid.uuid4()

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc1 = PaymentService()
        link = svc1.create_payment_link(
            firm_id=firm, cpa_id=cpa, name="Q1 Retainer", amount=1200.0
        )
        code = link.link_code

    with patch.dict(os.environ, {"DATABASE_PATH": str(db)}):
        svc2 = PaymentService()
        loaded = svc2.get_payment_link_by_code(code)

    assert loaded is not None
    assert loaded.name == "Q1 Retainer"
    assert loaded.amount == 1200.0
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
PYTHONPATH=src python -m pytest tests/cpa/test_payment_service.py::test_load_from_db_restores_invoices tests/cpa/test_payment_service.py::test_load_from_db_restores_payments tests/cpa/test_payment_service.py::test_load_from_db_restores_payment_links -v
```

Expected: 3 FAILED — `svc2.get_invoice(inv_id)` returns `None` because `_load_from_db` isn't implemented.

- [ ] **Step 3: Implement _load_from_db() and call it from __init__**

Add the method to `PaymentService` before the `# INVOICE MANAGEMENT` section (after line 69, after `self._stripe_configured` line). Also add a call at the end of `__init__`.

```python
    def _load_from_db(self) -> None:
        """Hydrate in-memory caches from SQLite on startup."""
        import datetime as _dt

        def _uuid(val):
            if val is None:
                return None
            if isinstance(val, UUID):
                return val
            try:
                return UUID(str(val))
            except (ValueError, AttributeError):
                return None

        def _dt_parse(val):
            if val is None:
                return None
            if isinstance(val, _dt.datetime):
                return val
            try:
                return _dt.datetime.fromisoformat(str(val))
            except (ValueError, AttributeError):
                return None

        def _date_parse(val):
            if val is None:
                return None
            if isinstance(val, _dt.date):
                return val
            try:
                return _dt.date.fromisoformat(str(val))
            except (ValueError, AttributeError):
                return None

        with sqlite3.connect(str(self._db_path)) as conn:
            # Load invoices
            for row in conn.execute("SELECT data_json FROM pay_invoices"):
                try:
                    d = json.loads(row[0])
                    items = [
                        LineItem(
                            description=li["description"],
                            amount=float(li["amount"]),
                            quantity=int(li.get("quantity", 1)),
                            tax_rate=float(li.get("tax_rate", 0.0)),
                        )
                        for li in d.get("line_items", [])
                    ]
                    inv = Invoice(
                        id=_uuid(d.get("id")),
                        invoice_number=d.get("invoice_number", ""),
                        firm_id=_uuid(d.get("firm_id")),
                        cpa_id=_uuid(d.get("cpa_id")),
                        cpa_name=d.get("cpa_name", ""),
                        firm_name=d.get("firm_name", ""),
                        client_id=_uuid(d.get("client_id")),
                        client_name=d.get("client_name", ""),
                        client_email=d.get("client_email", ""),
                        client_address=d.get("client_address"),
                        notes=d.get("notes"),
                        terms=d.get("terms"),
                        subtotal=float(d.get("subtotal", 0.0)),
                        tax_total=float(d.get("tax_total", 0.0)),
                        discount_amount=float(d.get("discount_amount", 0.0)),
                        total_amount=float(d.get("total_amount", 0.0)),
                        amount_paid=float(d.get("amount_paid", 0.0)),
                        currency=d.get("currency", "USD"),
                        issue_date=_date_parse(d.get("issue_date")) or _dt.date.today(),
                        due_date=_date_parse(d.get("due_date")) or _dt.date.today(),
                        paid_date=_date_parse(d.get("paid_date")),
                        status=InvoiceStatus(d.get("status", InvoiceStatus.DRAFT.value)),
                        payment_link=d.get("payment_link"),
                        stripe_invoice_id=d.get("stripe_invoice_id"),
                        created_at=_dt_parse(d.get("created_at")) or datetime.now(timezone.utc),
                        updated_at=_dt_parse(d.get("updated_at")) or datetime.now(timezone.utc),
                        sent_at=_dt_parse(d.get("sent_at")),
                    )
                    inv.line_items = items
                    self._invoices[inv.id] = inv
                except Exception as e:
                    logger.warning("Failed to load invoice row: %s", e)

            # Load payments
            for row in conn.execute("SELECT data_json FROM pay_payments"):
                try:
                    d = json.loads(row[0])
                    pay = Payment(
                        id=_uuid(d.get("id")),
                        firm_id=_uuid(d.get("firm_id")),
                        cpa_id=_uuid(d.get("cpa_id")),
                        client_id=_uuid(d.get("client_id")),
                        client_name=d.get("client_name", ""),
                        client_email=d.get("client_email", ""),
                        invoice_id=_uuid(d.get("invoice_id")),
                        invoice_number=d.get("invoice_number"),
                        amount=float(d.get("amount", 0.0)),
                        currency=d.get("currency", "USD"),
                        description=d.get("description", ""),
                        payment_method=PaymentMethod(d.get("payment_method", PaymentMethod.CARD.value)),
                        stripe_payment_intent_id=d.get("stripe_payment_intent_id"),
                        stripe_charge_id=d.get("stripe_charge_id"),
                        stripe_receipt_url=d.get("stripe_receipt_url"),
                        platform_fee=float(d.get("platform_fee", 0.0)),
                        net_amount=float(d.get("net_amount", 0.0)),
                        status=PaymentStatus(d.get("status", PaymentStatus.PENDING.value)),
                        refunded_amount=float(d.get("refunded_amount", 0.0)),
                        refund_reason=d.get("refund_reason"),
                        created_at=_dt_parse(d.get("created_at")) or datetime.now(timezone.utc),
                        updated_at=_dt_parse(d.get("updated_at")) or datetime.now(timezone.utc),
                        completed_at=_dt_parse(d.get("completed_at")),
                        metadata=d.get("metadata") or {},
                    )
                    self._payments[pay.id] = pay
                except Exception as e:
                    logger.warning("Failed to load payment row: %s", e)

            # Load payment links
            for row in conn.execute("SELECT data_json FROM pay_links"):
                try:
                    d = json.loads(row[0])
                    link = PaymentLink(
                        id=_uuid(d.get("id")),
                        link_code=d.get("link_code", ""),
                        firm_id=_uuid(d.get("firm_id")),
                        cpa_id=_uuid(d.get("cpa_id")),
                        name=d.get("name", ""),
                        description=d.get("description"),
                        amount=float(d["amount"]) if d.get("amount") is not None else None,
                        currency=d.get("currency", "USD"),
                        max_uses=int(d["max_uses"]) if d.get("max_uses") is not None else None,
                        expires_at=_dt_parse(d.get("expires_at")),
                        min_amount=float(d["min_amount"]) if d.get("min_amount") is not None else None,
                        max_amount=float(d["max_amount"]) if d.get("max_amount") is not None else None,
                        is_active=bool(d.get("is_active", True)),
                        uses_count=int(d.get("uses_count", 0)),
                        total_collected=float(d.get("total_collected", 0.0)),
                        stripe_price_id=d.get("stripe_price_id"),
                        stripe_payment_link_id=d.get("stripe_payment_link_id"),
                        created_at=_dt_parse(d.get("created_at")) or datetime.now(timezone.utc),
                    )
                    self._payment_links[link.id] = link
                    self._links_by_code[link.link_code] = link.id
                except Exception as e:
                    logger.warning("Failed to load payment link row: %s", e)

        self._db_loaded = True
```

Then at the end of `__init__`, after `self._stripe_configured = ...`, add:

```python
        self._load_from_db()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
PYTHONPATH=src python -m pytest tests/cpa/test_payment_service.py -v
```

Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
git add src/cpa_panel/payments/payment_service.py tests/cpa/test_payment_service.py
git commit -m "feat: add _load_from_db() to PaymentService — hydrate caches on startup"
```

---

### Task 3: Fix CPA signup form — add firmName input and fix next redirect

**Files:**
- Modify: `src/web/templates/auth/signup.html`

- [ ] **Step 1: Write a quick smoke test to verify the HTML fix**

The JS at line 681 reads `formData.get('firmName')` but there's no `<input name="firmName">`. Add a test in `tests/web/test_tools_api.py` later (Task 5). For this template change we do a manual verification step.

First, verify the bug exists:

```bash
grep -n 'firmName' /Users/rakeshanita/Desktop/60_Code/jorss-gbo/src/web/templates/auth/signup.html
```

Expected: Line 448 (hidden next-url input hardcoded `/intelligent-advisor`) and line 681 (`formData.get('firmName')`) — but NO `<input name="firmName">`.

- [ ] **Step 2: Add the firmName input group inside the form in signup.html**

In `src/web/templates/auth/signup.html`, after line 448 (`<input type="hidden" name="next" ...>`) and before the `<div class="form-row">` that contains firstName/lastName (line 450), insert the firm name group:

```html
                        <input type="hidden" name="next" id="next-url" value="/intelligent-advisor">

                        <div class="form-group" id="firm-name-group" style="display:none">
                            <label class="form-label" for="firmName">Firm Name</label>
                            <input type="text" id="firmName" name="firmName" class="form-input" placeholder="Smith & Associates CPA" autocomplete="organization">
                        </div>
```

- [ ] **Step 3: Wire up firmName visibility and required in the DOMContentLoaded block**

Inside the existing `document.addEventListener('DOMContentLoaded', function() {` block (around line 596), add after the `const nextUrl = ...` line:

```javascript
            // Show firmName field for CPA signup
            if (urlParams.get('type') === 'cpa') {
                const firmGroup = document.getElementById('firm-name-group');
                const firmInput = document.getElementById('firmName');
                if (firmGroup) firmGroup.style.display = '';
                if (firmInput) firmInput.required = true;
            }
```

- [ ] **Step 4: Verify fix manually**

```bash
grep -n 'firmName\|firm-name-group\|firm_name' /Users/rakeshanita/Desktop/60_Code/jorss-gbo/src/web/templates/auth/signup.html
```

Expected output shows:
- An `<input name="firmName">` in the HTML
- `firm-name-group` div
- JS `firmGroup` toggle
- JS `formData.get('firmName')` still on the submit handler line

- [ ] **Step 5: Commit**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
git add src/web/templates/auth/signup.html
git commit -m "fix: add firmName input to CPA signup form — was silently empty on every registration"
```

---

### Task 4: Remove 'anonymous' from client nav condition in base_modern.html

**Files:**
- Modify: `src/web/templates/base_modern.html:65`

- [ ] **Step 1: Verify the current condition**

```bash
grep -n 'anonymous\|client.*nav\|nav.*client' /Users/rakeshanita/Desktop/60_Code/jorss-gbo/src/web/templates/base_modern.html
```

Expected: line 65 shows `{% if user and user.role in ('client', 'firm_client', 'direct_client', 'anonymous') %}`

- [ ] **Step 2: Remove 'anonymous' from the condition**

In `src/web/templates/base_modern.html` line 65, change:

```jinja2
  {% if user and user.role in ('client', 'firm_client', 'direct_client', 'anonymous') %}
```

to:

```jinja2
  {% if user and user.role in ('client', 'firm_client', 'direct_client') %}
```

- [ ] **Step 3: Verify the change**

```bash
grep -n "user.role in" /Users/rakeshanita/Desktop/60_Code/jorss-gbo/src/web/templates/base_modern.html
```

Expected: line 65 without `'anonymous'`.

- [ ] **Step 4: Commit**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
git add src/web/templates/base_modern.html
git commit -m "fix: remove anonymous role from client nav condition — unauthenticated users must not see client nav"
```

---

### Task 5: Add input validation to tax-rate-lookup and w4-calculator endpoints

**Files:**
- Modify: `src/web/app.py:3049-3116`
- Create: `tests/web/test_tools_api.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_tools_api.py
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from web.app import app

client = TestClient(app)

VALID_STATUSES = {"single", "married_filing_jointly", "married_filing_separately",
                  "head_of_household", "qualifying_surviving_spouse"}


# --- tax-rate-lookup ---

def test_rate_lookup_valid():
    r = client.get("/api/tools/tax-rate-lookup?income=85000&filing_status=single")
    assert r.status_code == 200
    data = r.json()
    assert "marginal_rate" in data
    assert "effective_rate" in data


def test_rate_lookup_invalid_filing_status_returns_422():
    r = client.get("/api/tools/tax-rate-lookup?income=85000&filing_status=banana")
    assert r.status_code == 422


def test_rate_lookup_negative_income_clamped_to_zero():
    r = client.get("/api/tools/tax-rate-lookup?income=-5000&filing_status=single")
    assert r.status_code == 200
    assert r.json()["income"] == 0.0


# --- w4-calculator ---

def test_w4_valid():
    r = client.get("/api/tools/w4-calculator?annual_income=80000&filing_status=single")
    assert r.status_code == 200
    assert "recommendation" in r.json()


def test_w4_invalid_filing_status_returns_422():
    r = client.get("/api/tools/w4-calculator?annual_income=80000&filing_status=foobar")
    assert r.status_code == 422


def test_w4_negative_income_clamped():
    r = client.get("/api/tools/w4-calculator?annual_income=-1000&filing_status=single")
    assert r.status_code == 200
    assert r.json()["annual_tax_estimate"] >= 0


def test_w4_negative_dependents_clamped():
    r = client.get("/api/tools/w4-calculator?annual_income=50000&filing_status=single&dependents=-3")
    assert r.status_code == 200
    # negative dependents must not produce negative CTC
    assert r.json()["annual_tax_estimate"] >= 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
PYTHONPATH=src python -m pytest tests/web/test_tools_api.py -v 2>&1 | head -40
```

Expected: `test_rate_lookup_invalid_filing_status_returns_422` FAILED (returns 200 instead of 422), `test_rate_lookup_negative_income_clamped_to_zero` FAILED (income field returns -5000), `test_w4_invalid_filing_status_returns_422` FAILED, etc.

- [ ] **Step 3: Fix tax-rate-lookup in app.py**

Find the `@app.get("/api/tools/tax-rate-lookup")` endpoint (line 3049). Replace the function signature and first lines:

```python
VALID_FILING_STATUSES = {
    "single", "married_filing_jointly", "married_filing_separately",
    "head_of_household", "qualifying_surviving_spouse",
}

@app.get("/api/tools/tax-rate-lookup")
async def tax_rate_lookup(income: float = 85000, filing_status: str = "single"):
    """Quick tax rate lookup — marginal and effective rates for 2025."""
    if filing_status not in VALID_FILING_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid filing_status '{filing_status}'. Must be one of: {sorted(VALID_FILING_STATUSES)}")
    income = max(0.0, income)
    from calculator.tax_year_config import TaxYearConfig
    ...  # rest of function unchanged
```

Place the `VALID_FILING_STATUSES` set just above the `@app.get("/api/tools/tax-rate-lookup")` decorator (line 3049). Then add the two new lines at the start of the function body:

```python
    if filing_status not in VALID_FILING_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid filing_status '{filing_status}'. Must be one of: {sorted(VALID_FILING_STATUSES)}")
    income = max(0.0, income)
```

Also update the return dict to use the clamped `income`:
```python
    return JSONResponse({
        "income": income, ...  # already uses local 'income' variable so this is automatic
    })
```

- [ ] **Step 4: Fix w4-calculator in app.py**

Find the `@app.get("/api/tools/w4-calculator")` endpoint (line 3079). Add input guards at the start of the function body, immediately after the docstring:

```python
    """W-4 withholding calculator — recommends optimal W-4 settings."""
    if filing_status not in VALID_FILING_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid filing_status '{filing_status}'. Must be one of: {sorted(VALID_FILING_STATUSES)}")
    annual_income = max(0.0, annual_income)
    dependents = max(0, dependents)
    other_income = max(-200_000.0, other_income)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
PYTHONPATH=src python -m pytest tests/web/test_tools_api.py -v
```

Expected: 7 PASSED

- [ ] **Step 6: Run all new tests together**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
PYTHONPATH=src python -m pytest tests/cpa/test_payment_service.py tests/web/test_tools_api.py -v
```

Expected: 13 PASSED, 0 failed

- [ ] **Step 7: Commit**

```bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
git add src/web/app.py tests/web/test_tools_api.py
git commit -m "fix: add input validation to tax-rate-lookup and w4-calculator endpoints

Invalid filing_status returns 422. Negative income/dependents clamped to safe floor."
```

---

## Done

All 5 tasks complete. The payment service now persists correctly, survives restarts, the CPA signup form captures firm name, unauthenticated users don't see the client nav, and the two public API tools reject bad input gracefully.
