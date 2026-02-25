# Tax Year Inconsistency Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 7 hardcoded tax year defaults from 2024 to 2025 across 4 files.

**Architecture:** Simple find-and-replace of default values. No new logic, just correcting inconsistent defaults to match the rest of the codebase.

**Tech Stack:** Python (no dependencies)

---

### Task 1: Fix orchestrator.py Tax Year Defaults

**Files:**
- Modify: `src/smart_tax/orchestrator.py:57,159`

**Step 1: Read current file to confirm line numbers**

Read the file and locate the two `tax_year: int = 2024` defaults.

**Step 2: Fix TaxFilingSession default (line ~57)**

Change:
```python
tax_year: int = 2024
```
To:
```python
tax_year: int = 2025
```

**Step 3: Fix create_session default (line ~159)**

Change:
```python
tax_year: int = 2024,
```
To:
```python
tax_year: int = 2025,
```

**Step 4: Verify syntax**

Run: `python3 -c "from smart_tax.orchestrator import TaxFilingSession, SmartTaxOrchestrator; print('OK')"`
Expected: OK (no import errors)

**Step 5: Commit**

```bash
git add src/smart_tax/orchestrator.py
git commit -m "fix: update orchestrator tax year default from 2024 to 2025"
```

---

### Task 2: Fix document_processor.py Tax Year Default

**Files:**
- Modify: `src/smart_tax/document_processor.py:214`

**Step 1: Read current file to confirm line number**

Read the file and locate `def __init__(self, tax_year: int = 2024)`.

**Step 2: Fix DocumentProcessor.__init__ default**

Change:
```python
def __init__(self, tax_year: int = 2024):
```
To:
```python
def __init__(self, tax_year: int = 2025):
```

**Step 3: Verify syntax**

Run: `python3 -c "from smart_tax.document_processor import DocumentProcessor; print('OK')"`
Expected: OK (no import errors)

**Step 4: Commit**

```bash
git add src/smart_tax/document_processor.py
git commit -m "fix: update document_processor tax year default from 2024 to 2025"
```

---

### Task 3: Fix scenarios_routes.py Tax Year Defaults

**Files:**
- Modify: `src/core/api/scenarios_routes.py:123,245,440`

**Step 1: Read current file to confirm line numbers**

Read the file and locate:
- Line ~123: `tax_year: int = 2024` in ScenarioRequest
- Line ~245: `.get("tax_year", 2024)`
- Line ~440: `.get("tax_year", 2024)`

**Step 2: Fix ScenarioRequest default (line ~123)**

Change:
```python
tax_year: int = 2024
```
To:
```python
tax_year: int = 2025
```

**Step 3: Fix first .get() call (line ~245)**

Change:
```python
tax_year=scenario_data.get("tax_year", 2024),
```
To:
```python
tax_year=scenario_data.get("tax_year", 2025),
```

**Step 4: Fix second .get() call (line ~440)**

Change:
```python
tax_year=scenario_data.get("tax_year", 2024),
```
To:
```python
tax_year=scenario_data.get("tax_year", 2025),
```

**Step 5: Verify syntax**

Run: `python3 -c "from core.api.scenarios_routes import scenarios_router; print('OK')"`
Expected: OK (no import errors)

**Step 6: Commit**

```bash
git add src/core/api/scenarios_routes.py
git commit -m "fix: update scenarios_routes tax year defaults from 2024 to 2025"
```

---

### Task 4: Fix test_data_init.py Tax Year Default

**Files:**
- Modify: `src/core/services/test_data_init.py:534`

**Step 1: Read current file to confirm line number**

Read the file and locate `"tax_year": 2024`.

**Step 2: Fix test data tax year**

Change:
```python
"tax_year": 2024,
```
To:
```python
"tax_year": 2025,
```

**Step 3: Verify syntax**

Run: `python3 -c "from core.services.test_data_init import *; print('OK')"`
Expected: OK (no import errors)

**Step 4: Commit**

```bash
git add src/core/services/test_data_init.py
git commit -m "fix: update test_data_init tax year from 2024 to 2025"
```

---

### Task 5: Run Test Suite and Verify

**Files:**
- None (verification only)

**Step 1: Run smart_tax tests**

Run: `python3 -m pytest tests/ -k "smart_tax or orchestrator or document" -v --tb=short 2>&1 | tail -30`
Expected: Tests pass (or pre-existing failures unrelated to tax year)

**Step 2: Run scenario tests**

Run: `python3 -m pytest tests/ -k "scenario" -v --tb=short 2>&1 | tail -20`
Expected: Tests pass (or pre-existing failures unrelated to tax year)

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: verify all tests pass after tax year consistency fix" --allow-empty
```

---

### Task 6: Update Design Doc Status

**Files:**
- Modify: `docs/plans/2026-02-25-tax-year-inconsistency-design.md`

**Step 1: Update status**

Change line 4 from:
```markdown
**Status:** Approved
```
To:
```markdown
**Status:** Implemented
```

**Step 2: Commit**

```bash
git add docs/plans/2026-02-25-tax-year-inconsistency-design.md
git commit -m "docs: mark tax year inconsistency fix as implemented"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Fix orchestrator.py defaults | orchestrator.py |
| 2 | Fix document_processor.py default | document_processor.py |
| 3 | Fix scenarios_routes.py defaults | scenarios_routes.py |
| 4 | Fix test_data_init.py default | test_data_init.py |
| 5 | Run test suite and verify | Verification |
| 6 | Update documentation | Design doc |

**Total: 6 tasks, 7 line changes**
