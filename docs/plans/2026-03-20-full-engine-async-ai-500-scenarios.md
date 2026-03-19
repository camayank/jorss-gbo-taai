# Full Engine + Async AI + 500 Scenario Validation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unlock the full FederalTaxEngine (22+ forms), make AI enrichment non-blocking, and validate across 500 tax scenarios.

**Architecture:** Fix SSN validation to enable full engine pipeline, restructure AI enrichment to return immediately with rule-based strategies then enrich asynchronously, build comprehensive test harness.

**Tech Stack:** Python, FastAPI, asyncio, FederalTaxEngine

---

### Task 1: Fix SSN validation to unlock full FederalTaxEngine

**Files:** `src/web/calculation_helper.py:264`

Change `ssn=profile.get("ssn", "000-00-0000")` to `ssn=profile.get("ssn")` (None is valid).
Also change `spouse_ssn=profile.get("spouse_ssn")` if it has a similar default.

### Task 2: Make AI enrichment non-blocking

**Files:** `src/web/intelligent_advisor_api.py` (the /chat endpoint, lines ~5347-5400)

Move the AI reasoning + narrative enrichment AFTER the response is returned. Use `asyncio.create_task()` to fire-and-forget. The response returns immediately with rule-based strategies. When AI finishes, it updates the session — the next user message will include the enriched data.

### Task 3: Build 500-scenario test harness and run

**Files:** Create `tests/test_500_scenarios.py`

Test matrix covering every meaningful combination of:
- 5 filing statuses × 10 income levels × 10 states × deduction combos × dependent combos × income types
