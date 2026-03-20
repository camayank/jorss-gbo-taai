# Input-Output Perfection Plan

## The Principle

Every piece of data we collect must either change the tax number or change a strategy recommendation. If it does neither, don't ask. Every number we show must be traceable to an IRS formula. If we can't show the math, don't show the number.

---

## INPUT: What to Collect and How

### Phase 1 (Client-Side — 6 clicks, under 30 seconds)

These are correct as-is. No changes needed.

1. Filing status (5 radio buttons)
2. State (searchable dropdown, 50+DC)
3. Income range (7 buttons + exact amount)
4. Income source (5 buttons)
5. Dependents (4 buttons)
6. Summary → Run Analysis

### Phase 2 (Server-Side — Smart, Adaptive, with Follow-Ups)

Current problem: we ask "Do you have investments?" (yes/no) but never ask HOW MUCH. The calculation needs dollar amounts, not boolean flags.

**Fix: Every yes-answer must trigger a dollar-amount follow-up.**

Correct Phase 2 flow:

```
WITHHOLDING (W-2 only, score 90)
  → "How much federal tax was withheld?" → amount buttons + exact

DEPENDENT AGE SPLIT (if dependents > 0, score 85)
  → "How many under 17?" → buttons

BUSINESS INCOME (SE only, score 80)
  → "Net business income after expenses?" → amount buttons
  → If yes: "Home office?" → yes/no

RETIREMENT (score 60-75)
  → "Contributing to retirement accounts?" → 401k/IRA/Both/None
  → Already captures dollar amounts ($23,500/$7,000)

DEDUCTIONS (score 50-60)
  → "Do you have any of these?"
  → CHANGE: Add "Property taxes" as an option alongside mortgage/charitable/medical
  → Each yes → amount follow-up (already works for mortgage/charitable)
  → ADD: Property taxes amount follow-up

INVESTMENTS (score 40-65)
  → "Do you have investment income?" → Yes/No
  → If Yes: NEW follow-up: "Approximately how much in total investment income?"
    Buttons: Under $5K, $5K-$25K, $25K-$100K, Over $100K, Enter exact
  → NEW follow-up: "Any long-term capital gains from stock sales?"
    Buttons: No gains, Under $10K, $10K-$50K, Over $50K

RENTAL (score 30-60)
  → "Own rental properties?" → Yes/No
  → If Yes: NEW follow-up: "Approximate annual net rental income (after expenses)?"
    Buttons: Under $10K, $10K-$25K, $25K-$50K, Over $50K, Net loss

K-1 (score 25-60)
  → "K-1 income from partnerships/S-corps?" → Yes/No
  → If Yes: NEW follow-up: "Approximate K-1 ordinary income?"
    Buttons: Under $25K, $25K-$100K, $100K-$250K, Over $250K

HSA (score 45, only if retirement answered)
  → Already works correctly

ESTIMATED PAYMENTS (income > $100K)
  → "Made estimated payments?" → Yes/No
  → If Yes: NEW follow-up: "Total estimated payments this year?"
    Buttons: Under $5K, $5K-$15K, $15K-$30K, Over $30K

STUDENT LOANS (income < $180K)
  → Already captures $2,500 default

AGE (score 35)
  → Already works
```

### What NOT to Ask (YAGNI)

- Education expenses (AOTC/LLC) — add later when we implement Form 8863
- Childcare expenses (CDCC) — add later when we implement Form 2441
- Health insurance/ACA — add later when we implement Form 8962
- Prior year data — add later for estimated tax penalty
- Spouse details for MFJ — add later for full joint return
- Multiple W-2s — add later
- State-specific questions — add later per state

---

## OUTPUT: What to Show and How

### The Calculation Result Card

```
┌─────────────────────────────────────────────────────────────┐
│  ESTIMATED REFUND: $3,847                                   │
│  Based on Single filing in California                       │
│                                                             │
│  ┌───────────────────┬───────────────────┐                  │
│  │ Federal Tax       │     $18,234       │                  │
│  │ State Tax (CA)    │      $6,421       │                  │
│  │ SE Tax            │          $0       │                  │
│  │ ─────────────────────────────────     │                  │
│  │ Total Tax         │     $24,655       │                  │
│  │ Withholding       │    -$28,502       │                  │
│  │ ═════════════════════════════════     │                  │
│  │ REFUND            │      $3,847       │                  │
│  └───────────────────┴───────────────────┘                  │
│                                                             │
│  Effective Rate: 16.4%  │  Marginal Rate: 24%               │
│                                                             │
│  Credits Applied:                                           │
│  • Child Tax Credit: $4,000 (2 children under 17)           │
│  • EITC: $0 (income above threshold)                        │
│                                                             │
│  Deduction: Standard ($30,000 MFJ)                          │
│  ────────────────────────────────────────────                │
│  Accuracy: ~90% based on 12 of 15 data points provided      │
│  Add more details to improve accuracy                       │
└─────────────────────────────────────────────────────────────┘
```

### Strategy Cards

Each strategy must have:
1. **Title** — what to do
2. **Savings** — dollar amount
3. **IRS Reference** — IRC section or form number
4. **Action Steps** — numbered steps the user can take
5. **Risk Level** — low/medium/high
6. **Complexity** — "DIY" or "CPA Recommended"

### Accuracy Indicator

Show a data completeness score based on how many fields are populated:

```
Fields available: filing_status, total_income, state, dependents,
  income_type, withholding, retirement, deductions
Fields missing: capital_gains, rental_income, k1_income,
  property_taxes, estimated_payments

Accuracy: ~85% (10 of 13 relevant fields provided)
```

---

## ENGINE: Ensure Full FederalTaxEngine Runs

Current problem: `calculation_helper.py` creates Dependent objects with names like "Child 1" which fail the name validator → full engine fails → falls back to simplified _fallback_calculation.

Fix: Use valid names (already done — "Alex", "Jordan", etc.)

But there may be other validation failures. The fix should be defensive:

```python
try:
    # Try full engine
    result = engine.calculate(tax_return)
except ValidationError:
    # Log which field failed, fix it, retry
    # If still fails, use fallback
```

---

## IMPLEMENTATION PRIORITY

### Batch 1: Fix engine reliability (30 min)
- Fix any remaining validation issues so full engine runs
- Verify with 762-scenario matrix

### Batch 2: Add dollar-amount follow-ups (1 hour)
- Investment income amount after "has_investments"
- Rental income amount after "has_rental"
- K-1 income amount after "has_k1"
- Estimated payments amount after "has_estimated_payments"
- Property taxes in deductions + amount follow-up
- All via _quick_action_map entries + _get_dynamic_next_question updates

### Batch 3: Improve output quality (1 hour)
- Restructure calculation response to show full breakdown
- Add accuracy indicator based on data completeness
- Ensure strategy cards have all 6 required fields
- Add "Show the math" expandable section
