# Comprehensive Sequential Flow — Design Document

## What Changed

The advisor's question flow was expanded from **~22 questions with ~30 paths** to **~50+ questions with 720+ unique paths**, organized into 14 sequential blocks that follow the natural order a tax preparer uses when interviewing a client.

## Architecture

The flow lives entirely in `_get_dynamic_next_question()` using the sequential if/return pattern. No scoring randomization — the code order IS the conversation order.

### Sequential Block Order

```
Phase 1: Basics (5 questions — all required, strict order)
  Filing Status → Total Income → State → Dependents → Income Type (8 options)

Phase 2: Deep Dive (profile-aware, sequential blocks A-N)

  A. Income-Type-Specific (varies by profile)
     W-2:      Withholding
     Multi-W2: Job count → Withholding
     W-2+Side: Withholding → Side type → Side income
     SE/Biz:   Entity type → Business income → [S-Corp: Salary] → Home office
               → Vehicle → Equipment → Employees → Health insurance → [SSTB]
     Retired:  SS benefits → Pension → [65+: RMD]
     Military: Combat zone → PCS move → Withholding
     Investor: (skips to Block F)

  B. Age (everyone)

  C. Spouse Details (MFJ only)
     Spouse income type → Spouse income amount

  D. Dependent Details (if has dependents)
     Age split → Childcare → DCFSA → Education → 529 → Custody
     (No dependents: Education only if < $180k income)

  E. Life Events
     Life events check → Follow-ups (home sale, state move, job loss, new biz)

  F. Investments
     Has investments? → Amount → Capital gains type → Crypto → Stock options

  G. Retirement & Savings (non-retired)
     Contributions (with SE options) → HSA → Distributions → Early withdrawal

  H. Deductions
     Major check → Mortgage → Property taxes → Charitable → Medical
     → Student loans → Educator expenses

  I. Rental Property (gated: skip for low-income W-2)
     Has rental? → Income → Participation

  J. K-1 Income (gated: skip for low-income W-2)
     Has K-1? → Amount

  K. Healthcare
     ACA Marketplace (non-retired) OR Medicare premiums (retired 65+)

  L. Estimated Tax Payments (SE or income > $100k)
     Has estimated? → Amount

  M. Special Situations
     Energy credits → Foreign income → [FBAR] → AMT → Alimony
     → Gambling → Household employee

  N. State-Specific (skip for no-income-tax states)
     Multi-state income

Phase 3: Done → return (None, None) → trigger tax calculation
```

## Files Modified

| File | Change |
|------|--------|
| `src/web/intelligent_advisor_api.py` | Expanded Phase 1 income type (4→8 options), rewrote Phase 2 with 14 sequential blocks, added 200+ new entries to `_quick_action_map` |
| `src/web/advisor/flow_engine.py` | NEW — standalone FlowEngine for unit testing (not used in live flow) |
| `src/web/advisor/flow_rules.py` | NEW — eligibility predicates (used by FlowEngine tests) |
| `src/web/advisor/question_registry.py` | NEW — 79 question definitions (used by FlowEngine tests) |
| `tests/advisor/test_flow_paths.py` | NEW — 266 tests across 42+ scenarios |

## IRS Form Coverage

100% of individual tax forms (38/38) have corresponding flow questions.

## Gating Rules

| Rule | Effect |
|------|--------|
| `is_retired` | Skips withholding, gets SS/Pension/RMD/Medicare |
| `is_military` | Gets combat zone, PCS move |
| `is_w2` (any variant) | Gets withholding |
| `is_se` (any variant) | Gets entity type, business income, home office, vehicle, equipment |
| `is_investor` | Skips withholding, goes straight to investments |
| MFJ | Gets spouse income questions |
| Has dependents under 17 | Gets childcare, DCFSA |
| Low-income W-2 only | Skips K-1, rental property |
| No-income-tax state | Skips multi-state, 529 |
| Income > $100k | Gets stock options, estimated payments |
| Income > $150k | Gets AMT check |
| Income > $182k + SE | Gets QBI/SSTB check |
