# Golden Path Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the complete end-to-end flow: Client files via Advisor → CPA sees it in Queue → CPA reviews & approves → Client sees results → Admin sees metrics. Remove all hardcoded fallbacks.

**Architecture:** Fix 4 data-flow breakpoints, remove 5 hardcoded fallback values, then seed 20 realistic test returns. All changes target existing code — no new modules needed.

**Tech Stack:** Python/FastAPI, SQLite session persistence, Jinja2 templates

---

## Break Point Map

| # | Where | Status | Fix |
|---|-------|--------|-----|
| 1 | Client → Backend | Works | No change needed |
| 2 | Advisor → Session DB | Works | No change needed |
| 3 | Session → CPA Queue | Partial | Add data verification + refund display |
| 4 | CPA Review → Display | BROKEN | Remove demo fallback, fix data loading |
| 5 | Results → Display | Partial | Remove $4,847 fallback, show real data or empty state |
| 6 | Admin → Metrics | BROKEN | Query session_tax_returns not returns table |

## Tasks (12 total)

### Task 1: Fix CPA Return Queue — show real refund/owed amounts
### Task 2: Remove CPA Review demo data fallback
### Task 3: Fix CPA Review to load tax return data correctly
### Task 4: Remove Results page $4,847 hardcoded fallback
### Task 5: Fix Admin dashboard to query session data
### Task 6: Remove all remaining hardcoded fallback values
### Task 7: Seed realistic demo data (20 returns at various stages)
### Task 8: Wire client portal step 3 (documents) to real upload
### Task 9: Add proper empty states to all screens
### Task 10: Verify full E2E flow works
