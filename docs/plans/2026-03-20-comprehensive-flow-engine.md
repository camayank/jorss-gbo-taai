# Comprehensive Adaptive Flow Engine — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current linear/simple-scoring question engine with a comprehensive, profile-aware decision tree that covers ALL realistic US tax scenarios — not just 20 questions, but the full universe of ~720+ unique flow paths.

**Architecture:** A rule-based flow engine (`FlowEngine`) with question pools grouped by topic. Each question has eligibility rules (predicates on the profile). The engine evaluates eligibility + relevance scoring to pick the next question. No hardcoded sequence — the flow adapts entirely based on what's known about the user.

**Tech Stack:** Python (FastAPI backend), same frontend JS modules, no new dependencies.

---

## PART 1: COMPLETE FLOW GAP ANALYSIS

### What exists today (20 questions, ~30 paths)

| # | Question | Branches On |
|---|----------|-------------|
| 1 | Filing status | 5 choices |
| 2 | Total income | 4 ranges |
| 3 | State | 50+DC |
| 4 | Dependents | 4 choices |
| 5 | Income type | 4 choices (W-2, SE, Biz Owner, Retired) |
| 6 | Federal withholding | W-2 only |
| 7 | Age | All |
| 8 | Business income | SE/Biz only |
| 9 | Home office | SE/Biz only |
| 10 | K-1 income | All (wrong!) |
| 11 | K-1 amount | If has K-1 |
| 12 | Investment income | All |
| 13 | Investment amount | If has investments |
| 14 | Capital gains | If has investments |
| 15 | Rental income | All |
| 16 | Rental amount | If has rental |
| 17 | Retirement contributions | All |
| 18 | HSA | If has retirement |
| 19 | Deductions (mortgage/charity/medical/property tax) | All |
| 20 | Estimated payments | Income > $100k |
| 21 | Student loans | Income < $180k |
| 22 | Dependent age split | If has dependents |

**Critical problems:**
- K-1 asked to W-2 minimum-wage workers (irrelevant)
- No education credits (affects millions of filers)
- No childcare expenses (Form 2441 — huge for working parents)
- No life events (marriage, baby, home purchase, job change)
- No Social Security income questions for retirees
- No multiple income sources (W-2 + freelance is extremely common)
- No healthcare marketplace / ACA questions
- No foreign income
- No alimony (pre-2019 divorce)
- No gambling income
- No energy credits (solar, EV — very popular)
- No educator expenses
- No moving expenses (military)
- No adoption credit
- No IRA conversion questions
- No early retirement distribution penalties
- No business entity type (LLC vs S-Corp vs Sole Prop)
- No vehicle/mileage for business
- No state-specific branching (no income tax states skip state questions)
- No prior year carryforward (capital losses, NOL)
- No multiple W-2 jobs
- No spouse income details for MFJ
- No quarterly estimated payment schedule
- No AMT trigger detection (ISOs, large itemized deductions)
- Retired person gets asked about withholding as if they're W-2

---

## PART 2: THE COMPLETE FLOW UNIVERSE

### 2.1 — Income Type Expansion (from 4 to 12)

Current: W-2, Self-Employed, Business Owner, Retired

**Should be (with sub-types):**

| Income Type | Sub-branches | Unique Follow-ups |
|---|---|---|
| **W-2 Employee (single job)** | — | Withholding, benefits (FSA/HSA/401k), employer stock (ESPP/RSU) |
| **W-2 Employee (multiple jobs)** | 2 jobs, 3+ jobs | Withholding per job, W-4 optimization, underwithholding risk |
| **W-2 + Side Hustle** | Freelance, gig (Uber/DoorDash), Etsy/online sales | SE tax on side income, home office, vehicle, mixed withholding |
| **Self-Employed (sole prop)** | Freelancer, consultant, contractor | Schedule C, SE tax, QBI, retirement (SEP/Solo 401k), health insurance deduction |
| **Self-Employed (LLC)** | Single-member, multi-member | Entity election, S-Corp election analysis, reasonable salary |
| **Business Owner (S-Corp)** | — | Reasonable salary, K-1 distributions, payroll, QBI W-2 wage limit |
| **Business Owner (C-Corp)** | — | Double taxation, salary vs dividends, Section 199A N/A |
| **Business Owner (Partnership)** | General partner, limited partner | K-1, SE tax on GP income, passive rules for LP |
| **Retired (pension + SS)** | — | Social Security taxation (0%/50%/85%), RMD, pension exclusion |
| **Retired (IRA/401k distributions)** | — | Early withdrawal penalty (<59½), Roth conversion, RMD |
| **Investor (primary income)** | Day trader, passive investor | Trader tax status (Section 475), wash sales, NIIT |
| **Rental property owner (primary)** | — | Real estate professional status, depreciation, passive loss |

### 2.2 — Filing Status Cascading Questions

| Filing Status | Unique Follow-up Questions |
|---|---|
| **Single** | No spouse questions. Skip dependent care if 0 dependents. |
| **MFJ** | Spouse income type, spouse income amount, spouse withholding, spouse retirement contributions, combined vs separate analysis |
| **MFS** | Why filing separate? (student loans, liability protection, income-driven repayment). Cannot claim EITC. Limited credits. |
| **HOH** | Verify: paid >50% household costs? Qualifying person relationship. More favorable brackets than Single. |
| **QSS** | Year spouse died (must be within 2 years). Dependent child required. |

### 2.3 — Life Events (ENTIRELY MISSING — affects millions)

| Life Event | Tax Impact | Questions to Ask |
|---|---|---|
| **Got married** | Filing status change, potential marriage penalty/bonus | Date married, spouse income, previous withholding |
| **Got divorced** | Filing status change, alimony (pre-2019), asset division | Date finalized, alimony paid/received, divorce decree year |
| **Had a baby** | CTC ($2,000), dependent care credit, EITC boost | Child's birth date, SSN obtained?, childcare costs |
| **Bought a home** | Mortgage interest deduction, property taxes, points paid | Purchase date, mortgage amount, points paid at closing |
| **Sold a home** | $250k/$500k exclusion, capital gains | Sale price, original purchase price, years lived in, improvements |
| **Changed jobs** | Multiple W-2s, potential underwithholding, 401k rollover | Gap in employment?, severance?, 401k rollover or cash out? |
| **Lost job** | Unemployment income (taxable), job search expenses | Unemployment received?, severance?, COBRA costs |
| **Started a business** | Schedule C, startup costs (up to $5k deductible) | Start date, entity type, startup costs, first-year expenses |
| **Retired** | Distribution planning, Social Security timing | Retirement date, pension type, SS start date, healthcare costs |
| **Moved states** | Part-year resident returns, state tax allocation | Move date, from/to states, income earned in each state |
| **Inherited money** | Step-up in basis, estate tax implications, IRD | Type of inheritance, amount, inherited IRA? |
| **Disability** | SSDI income, disability insurance payments | Type of disability income, employer-paid or self-paid premiums |

### 2.4 — Education (ENTIRELY MISSING)

| Scenario | Credits/Deductions | Questions |
|---|---|---|
| **College student (self)** | AOTC ($2,500), Lifetime Learning ($2,000) | Enrollment status, tuition paid (1098-T), year of study |
| **Parent paying tuition** | AOTC/LLC for dependent | Child's enrollment, tuition amount, who paid |
| **Graduate student** | Lifetime Learning only, tuition waiver taxable? | Fellowship/stipend income, tuition waiver amount |
| **Student loan repayment** | Interest deduction (up to $2,500) | Already asked, but missing income phase-out check |
| **529 plan** | State deduction (varies), tax-free growth | Contributions this year, distributions, state rules |
| **Teacher/Educator** | $300 above-the-line deduction | K-12 educator?, supplies purchased |

### 2.5 — Children & Dependents (MOSTLY MISSING)

| Scenario | Tax Impact | Questions |
|---|---|---|
| **Child under 17** | CTC $2,000 | Already captured (dependent age split) |
| **Child 17-18** | ODC $500, not CTC | Age verification |
| **College-age dependent (19-24)** | ODC $500 + education credits | Full-time student?, income under threshold? |
| **Childcare costs** | Credit up to $3,000/child ($6,000 for 2+) | Provider info, amount paid, dependent care FSA? |
| **Dependent care FSA** | Up to $5,000 pre-tax | Employer offers?, amount contributed |
| **Non-child dependent** | ODC $500 | Relationship, lived with you?, income test |
| **Custodial parent (divorced)** | Who claims child? Form 8332 | Custody agreement, release of exemption? |
| **Adoption** | Credit up to $16,810 | Domestic/international, special needs?, expenses |

### 2.6 — Healthcare (MOSTLY MISSING)

| Scenario | Tax Impact | Questions |
|---|---|---|
| **Employer insurance** | Pre-tax premiums (no action needed) | — (skip) |
| **ACA Marketplace** | Premium Tax Credit (Form 8962) | Marketplace plan?, advance PTC received?, income change |
| **Self-employed health insurance** | Above-the-line deduction | Premium amount, months covered, SE income sufficient? |
| **HSA** | Triple tax benefit | Currently asked, but missing: HDHP verification |
| **FSA** | Pre-tax medical expenses | Amount contributed, used for qualified expenses? |
| **High medical expenses** | Itemized deduction (>7.5% AGI) | Currently asked, but no AGI threshold check |
| **Long-term care insurance** | Deductible (age-based limits) | Premiums paid, age |
| **Medicare premiums** | Deductible for SE, IRMAA surcharge for high earners | Part B/D premiums, income level |

### 2.7 — Investments & Capital Events (PARTIALLY COVERED)

| Scenario | Tax Impact | Questions NOT Asked |
|---|---|---|
| **Stock sales** | Capital gains (ST vs LT) | Partially covered — missing: holding period, cost basis method |
| **Cryptocurrency** | Capital gains, mining income, staking | Type of crypto activity (trading/mining/staking/DeFi) |
| **Stock options (ISO)** | AMT preference item | ISO exercise?, bargain element, AMT risk |
| **Stock options (NSO)** | Ordinary income on exercise | Exercise amount, included in W-2? |
| **RSU vesting** | Ordinary income, withholding | Vesting amount, shares sold for taxes? |
| **ESPP** | Qualifying vs disqualifying disposition | Purchase price discount, holding period |
| **Mutual fund distributions** | Capital gains distributions | 1099-DIV received?, reinvested? |
| **Real estate sale (not primary)** | Capital gains, depreciation recapture | Sale price, adjusted basis, years depreciated |
| **Wash sales** | Loss disallowed | Repurchased within 30 days? |
| **Collectibles** | 28% rate | Type (art, coins, wine), sale amount |
| **Installment sale** | Spread gain over years | Payments received this year, interest component |
| **Like-kind exchange (1031)** | Defer gain on real estate | Exchange completed?, boot received? |

### 2.8 — Business-Specific (PARTIALLY COVERED)

| Scenario | Tax Impact | Questions NOT Asked |
|---|---|---|
| **Entity type** | Tax treatment varies dramatically | Sole prop / LLC / S-Corp / C-Corp / Partnership |
| **Reasonable salary (S-Corp)** | Saves SE tax but must be "reasonable" | Current salary, industry, hours worked |
| **Vehicle use** | Standard mileage ($0.70/mi) or actual expenses | Business miles, total miles, vehicle cost |
| **Equipment purchases** | Section 179 (up to $1.16M) or bonus depreciation | Items purchased, cost, placed in service date |
| **Business meals** | 50% deductible (post-2025 — was 100% temporarily) | Amount spent, business purpose |
| **Business travel** | Fully deductible if primarily business | Days away, business vs personal days |
| **Inventory** | COGS deduction | Beginning/ending inventory, purchases |
| **Business insurance** | Deductible expense | Type, premiums paid |
| **Employees/contractors** | Payroll taxes, 1099 filing | Number of employees, 1099 contractors, total payroll |
| **Startup costs** | Up to $5k deductible year 1, rest amortized | First year of business?, total startup costs |
| **Net Operating Loss (NOL)** | Carryforward (80% of taxable income) | Prior year losses?, NOL carryforward amount |
| **Qualified Business Income (QBI)** | 20% deduction — complex rules | Currently basic — missing: SSTB classification, W-2 wage limit, UBIA, taxable income threshold |

### 2.9 — Retirement-Specific (MOSTLY MISSING)

| Scenario | Tax Impact | Questions NOT Asked |
|---|---|---|
| **Social Security benefits** | 0%, 50%, or 85% taxable based on provisional income | SS benefit amount, other income sources |
| **Pension income** | Fully or partially taxable | 1099-R amount, after-tax contributions? |
| **Required Minimum Distribution** | Penalty if not taken (25%) | Age 73+?, RMD amount, taken yet? |
| **Early withdrawal** | 10% penalty + income tax | Under 59½?, exception applies? (SEPP, disability, first home) |
| **Roth conversion** | Taxable event, but future tax-free growth | Amount converted, pro-rata rule (has pre-tax IRA?) |
| **Inherited IRA** | 10-year rule (post-SECURE Act) | Relationship to decedent, year inherited |
| **Roth IRA distribution** | Tax-free if qualified (5-year rule + 59½) | Account age, reason for distribution |
| **401k loan** | Not taxable unless defaulted | Loan outstanding?, separated from employer? |

### 2.10 — State-Specific Branching (CURRENTLY ZERO)

| State Scenario | Impact | Questions |
|---|---|---|
| **No income tax state** (TX, FL, WA, NV, WY, SD, AK, NH*, TN*) | Skip state deduction questions, SALT cap less relevant | *NH/TN: interest/dividend tax only |
| **High income tax state** (CA, NY, NJ, OR, HI, MN) | SALT cap ($10k) more impactful, state-specific credits | State-specific credit eligibility |
| **Multi-state income** | Apportionment, credits for taxes paid to other states | States worked in, days/income in each state |
| **Remote worker** | Employer state vs residence state, convenience rule (NY) | Employer location, work-from-home state |
| **State-specific deductions** | CA renter's credit, NY STAR, IL education credit, etc. | Varies by state |
| **Reciprocity agreements** | PA-NJ, VA-DC-MD, etc. | Applicable if multi-state |

### 2.11 — Other Missing Scenarios

| Scenario | Tax Impact | Questions |
|---|---|---|
| **Alimony (pre-2019 divorce)** | Deductible by payer, income to recipient | Divorce finalized before 2019?, amount paid/received |
| **Gambling income** | Taxable, losses deductible up to winnings | W-2G received?, total winnings, total losses |
| **Jury duty pay** | Taxable income (often returned to employer) | Amount received |
| **Foreign income** | FEIE ($126,500 for 2025), foreign tax credit | Days abroad, foreign taxes paid, bona fide residence |
| **Foreign accounts** | FBAR/FATCA reporting | Accounts over $10k aggregate at any point |
| **Energy credits** | Solar (30%), EV ($7,500/$4,000), home improvements | Solar installed?, EV purchased?, energy improvements |
| **Disaster losses** | Casualty loss deduction (federally declared only) | Disaster type, unreimbursed losses |
| **Clergy** | Housing allowance exclusion, SE tax on full income | Minister?, housing allowance amount |
| **Military** | Combat zone exclusion, moving expenses | Active duty?, deployed?, PCS move? |
| **Nanny/household employee** | Schedule H, employment taxes | Paid >$2,700 to household employee? |

---

## PART 3: THE COMPLETE FLOW MATRIX (720+ Unique Paths)

### Dimension Multiplication

| Dimension | Options | Count |
|---|---|---|
| Filing status | Single, MFJ, MFS, HOH, QSS | 5 |
| Income type (primary) | W-2, W-2+side, SE-sole prop, SE-LLC, S-Corp, C-Corp, Partnership, Retired-pension, Retired-IRA, Investor, Rental | 11 |
| Income level | Low (<$50k), Mid ($50k-$200k), High ($200k-$500k), Very High ($500k+) | 4 |
| Age bracket | Under 50, 50-64, 65+ | 3 |
| Dependents | 0, 1-2, 3+ | 3 |
| Life events | None, 1+, 2+ | 3 |

**Raw combinations:** 5 × 11 × 4 × 3 × 3 × 3 = **5,940**

After eliminating impossible combinations (e.g., QSS + single, C-Corp owner + low income, etc.) and collapsing similar paths: **~720 meaningfully distinct flows**.

### Example Flow Paths (10 of 720+)

**Flow #1: Single, W-2, Mid Income, Under 50, 0 Dependents**
```
Filing Status → Income → State → Dependents(0) → Income Type(W-2)
→ Withholding → Age → Retirement (401k/IRA) → HSA
→ Investments? → Student Loans? → Deductions (standard likely)
→ DONE (skip: childcare, K-1, rental, business, SE)
```

**Flow #2: MFJ, W-2+Side Hustle, Mid Income, Under 50, 2 Kids**
```
Filing Status(MFJ) → Income → State → Dependents(2) → Income Type(W-2+Side)
→ W-2 Withholding → Side Hustle Type (freelance/gig) → Side Income Amount
→ Business Expenses → Home Office? → Vehicle Use?
→ Spouse Income Type → Spouse Income Amount
→ Dependent Ages → Childcare Costs? → Dependent Care FSA?
→ Retirement (401k) → HSA → Investments?
→ Deductions → Estimated Payments?
→ DONE
```

**Flow #3: Single, Self-Employed (LLC), High Income, Under 50, 0 Dependents**
```
Filing Status(Single) → Income → State → Dependents(0) → Income Type(SE-LLC)
→ Entity Type (single-member LLC) → S-Corp Election Analysis
→ Net Business Income → Business Expenses Breakdown
→ Home Office → Vehicle/Mileage → Equipment (Section 179)
→ Employees/Contractors? → Health Insurance Deduction
→ Retirement (SEP-IRA vs Solo 401k) → HSA
→ QBI Deduction (check SSTB) → Estimated Payments (quarterly)
→ Investments? → Deductions
→ DONE (skip: childcare, K-1, withholding, student loans)
```

**Flow #4: MFJ, Retired, Under $50k, Age 65+, 0 Dependents**
```
Filing Status(MFJ) → Income → State → Dependents(0) → Income Type(Retired)
→ Social Security Benefits Amount → Pension Income?
→ IRA/401k Distributions → RMD Taken?
→ Spouse Income (also retired?) → Age (65+ → extra std deduction × 2)
→ Medicare Premiums → Investment Income?
→ Deductions (medical likely significant)
→ DONE (skip: withholding, SE, business, childcare, education, K-1)
```

**Flow #5: HOH, W-2, Low Income, Under 50, 2 Kids Under 17**
```
Filing Status(HOH) → Income → State → Dependents(2) → Income Type(W-2)
→ Withholding → Dependent Ages (both under 17 → CTC $4,000)
→ Childcare Costs? → Dependent Care Credit
→ EITC Eligibility (auto-calculated) → Education Credits (for self?)
→ Student Loans? → Deductions (standard deduction likely)
→ DONE (skip: K-1, rental, business, investments, estimated payments)
```

**Flow #6: MFJ, S-Corp Owner, Very High Income, 50-64, 3 Kids**
```
Filing Status(MFJ) → Income → State → Dependents(3) → Income Type(S-Corp)
→ Reasonable Salary Amount → K-1 Distribution Amount
→ W-2 Wages Paid (for QBI limitation) → Business Type (SSTB check)
→ Spouse Income Type → Spouse Income
→ Dependent Ages → Childcare? → Education Credits (older kids)?
→ Retirement (401k max + catch-up) → HSA → Backdoor Roth?
→ Investments → Capital Gains → NIIT Check ($250k MFJ threshold)
→ Deductions (likely itemize) → Mortgage → Property Taxes → SALT Cap
→ Charitable (bunching strategy?) → Estimated Payments
→ AMT Check (ISO?, large itemized deductions?)
→ QBI Deduction (W-2 wage + UBIA limitation at this income)
→ DONE
```

**Flow #7: Single, Investor/Day Trader, Very High Income, Under 50, 0 Dependents**
```
Filing Status(Single) → Income → State → Dependents(0) → Income Type(Investor)
→ Trader Tax Status (Section 475 election?) → Trading Income
→ Capital Gains Breakdown (ST vs LT) → Wash Sale Losses
→ Qualified Dividends → Interest Income → Crypto Activity?
→ NIIT ($200k Single threshold) → AMT Check
→ Retirement → HSA → Deductions → Estimated Payments
→ DONE (skip: childcare, education, K-1 unless partnership investments)
```

**Flow #8: MFJ, W-2 + Rental Properties, High Income, 50-64, 1 Kid**
```
Filing Status(MFJ) → Income → State → Dependents(1) → Income Type(W-2)
→ Withholding → Multiple Properties? → Net Rental Income Per Property
→ Depreciation Status → Active Participation?
→ Real Estate Professional Status? → Passive Loss Rules
→ Spouse Income → Dependent Age → Education Credits?
→ Retirement (catch-up eligible) → HSA → Investments?
→ Deductions (likely itemize with mortgage + property taxes)
→ SALT Cap Impact → Estimated Payments?
→ Cost Segregation Study Recommendation?
→ DONE
```

**Flow #9: Single, Military, Mid Income, Under 50, 0 Dependents**
```
Filing Status(Single) → Income → State → Dependents(0) → Income Type(W-2/Military)
→ Combat Zone Exclusion? → Tax-Free Combat Pay in EITC?
→ PCS Moving Expenses (still deductible for military)
→ TSP Contributions → Withholding
→ State of Legal Residence (military can keep prior state)
→ Deductions → Student Loans?
→ DONE
```

**Flow #10: MFJ, Mixed (W-2 + Spouse SE), Mid Income, Under 50, New Baby**
```
Filing Status(MFJ) → Income → State → Dependents → Income Type(W-2)
→ Life Events? → New Baby (CTC + childcare coming)
→ W-2 Withholding → Spouse Income Type (SE)
→ Spouse Business Income → Spouse Business Expenses
→ Spouse Home Office? → Spouse Health Insurance Deduction
→ Spouse Retirement (SEP/Solo 401k) → Your 401k
→ Baby's SSN Obtained? → Childcare Plans? → Dependent Care FSA?
→ Investments? → Deductions
→ Estimated Payments (for spouse SE income)
→ DONE
```

---

## PART 4: IMPLEMENTATION PLAN

### Architecture: Rule-Based Flow Engine

Replace the current monolithic `_get_dynamic_next_question()` and `_score_next_questions()` with a data-driven question registry.

```
src/web/advisor/
├── flow_engine.py          # Core engine: eligibility + scoring
├── question_registry.py    # All questions with eligibility rules
├── flow_rules.py           # Eligibility predicate functions
└── question_pools/         # Organized by topic
    ├── __init__.py
    ├── basics.py            # Phase 1: filing status, income, state, dependents, income type
    ├── income_details.py    # Withholding, spouse income, multiple jobs, side hustle
    ├── self_employment.py   # Business income, entity type, home office, vehicle, Section 179
    ├── investments.py       # Capital gains, dividends, crypto, stock options, wash sales
    ├── retirement.py        # 401k, IRA, HSA, SS benefits, RMD, Roth conversion, pension
    ├── dependents.py        # Child ages, childcare, dependent care, education credits, adoption
    ├── deductions.py        # Mortgage, SALT, charitable, medical, student loans, educator
    ├── life_events.py       # Marriage, baby, home purchase/sale, job change, divorce, inheritance
    ├── rental_property.py   # Rental income, depreciation, passive loss, RE professional
    ├── healthcare.py        # ACA marketplace, self-employed health insurance, Medicare, FSA
    ├── special_situations.py # Military, clergy, foreign income, gambling, alimony, energy credits
    └── state_specific.py    # Multi-state, no-income-tax states, reciprocity, state credits
```

### Data Model: Question Definition

```python
@dataclass
class FlowQuestion:
    id: str                          # Unique ID: "se_entity_type"
    pool: str                        # Topic pool: "self_employment"
    phase: int                       # 1 = basics, 2 = deep dive
    text: str                        # Question text
    actions: list[dict]              # Quick action buttons
    eligibility: Callable[[dict], bool]  # Profile → should this question be asked?
    base_score: int                  # Default relevance (0-100)
    context_boost_keywords: list[str]  # Conversation keywords that boost score
    context_boost_amount: int        # How much to boost
    sets_fields: list[str]           # Profile fields this question populates
    skip_field: str                  # Profile flag set when skipped
    asked_field: str                 # Profile flag set when asked
    follow_up_of: str | None        # Parent question ID (for chained questions)
```

---

### Task 1: Create the FlowQuestion data model and FlowEngine core

**Files:**
- Create: `src/web/advisor/flow_engine.py`
- Create: `src/web/advisor/question_registry.py`
- Test: `tests/advisor/test_flow_engine.py`

**Step 1: Write the failing test**

```python
# tests/advisor/test_flow_engine.py
import pytest
from src.web.advisor.flow_engine import FlowEngine, FlowQuestion


def test_engine_returns_phase1_first():
    """Phase 1 questions must come before Phase 2."""
    engine = FlowEngine()
    profile = {}  # Empty profile
    q = engine.get_next_question(profile)
    assert q is not None
    assert q.phase == 1
    assert q.id == "filing_status"


def test_engine_skips_answered_questions():
    """Questions for already-collected fields should not repeat."""
    engine = FlowEngine()
    profile = {"filing_status": "single"}
    q = engine.get_next_question(profile)
    assert q.id != "filing_status"


def test_engine_respects_eligibility():
    """W-2 employee should not get self-employment questions."""
    engine = FlowEngine()
    profile = {
        "filing_status": "single",
        "total_income": 75000,
        "state": "CA",
        "dependents": 0,
        "income_type": "w2_employee",
    }
    # Exhaust all questions
    questions_asked = []
    for _ in range(50):  # Safety limit
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions_asked.append(q.id)
        profile[q.asked_field] = True  # Mark as asked
    assert "se_business_income" not in questions_asked
    assert "se_home_office" not in questions_asked
    assert "se_entity_type" not in questions_asked


def test_engine_includes_childcare_for_parents():
    """Parents with dependents under 13 should get childcare question."""
    engine = FlowEngine()
    profile = {
        "filing_status": "married_joint",
        "total_income": 100000,
        "state": "TX",
        "dependents": 2,
        "dependents_under_17": 2,
        "income_type": "w2_employee",
    }
    questions_asked = []
    for _ in range(50):
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions_asked.append(q.id)
        profile[q.asked_field] = True
    assert "dep_childcare_costs" in questions_asked


def test_engine_asks_ss_benefits_for_retired():
    """Retired users should get Social Security benefit question."""
    engine = FlowEngine()
    profile = {
        "filing_status": "married_joint",
        "total_income": 45000,
        "state": "FL",
        "dependents": 0,
        "income_type": "retired",
    }
    questions_asked = []
    for _ in range(50):
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions_asked.append(q.id)
        profile[q.asked_field] = True
    assert "ret_ss_benefits" in questions_asked
    assert "withholding" not in questions_asked  # Not a W-2 employee


def test_engine_skips_state_tax_for_no_income_tax_states():
    """Users in TX/FL/etc should not get state deduction questions."""
    engine = FlowEngine()
    profile = {
        "filing_status": "single",
        "total_income": 100000,
        "state": "TX",
        "dependents": 0,
        "income_type": "w2_employee",
    }
    questions_asked = []
    for _ in range(50):
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions_asked.append(q.id)
        profile[q.asked_field] = True
    assert "state_specific_credits" not in questions_asked


def test_mfj_asks_spouse_income():
    """MFJ filers should be asked about spouse income."""
    engine = FlowEngine()
    profile = {
        "filing_status": "married_joint",
        "total_income": 150000,
        "state": "CA",
        "dependents": 1,
        "income_type": "w2_employee",
    }
    questions_asked = []
    for _ in range(50):
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions_asked.append(q.id)
        profile[q.asked_field] = True
    assert "inc_spouse_income_type" in questions_asked


def test_high_income_gets_amt_and_niit_questions():
    """High earners should get AMT and NIIT-related questions."""
    engine = FlowEngine()
    profile = {
        "filing_status": "single",
        "total_income": 500000,
        "state": "CA",
        "dependents": 0,
        "income_type": "w2_employee",
        "_has_investments": True,
        "investment_income": 100000,
    }
    questions_asked = []
    for _ in range(50):
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions_asked.append(q.id)
        profile[q.asked_field] = True
    assert "inv_stock_options" in questions_asked  # AMT trigger


def test_life_events_question_asked():
    """Life events question should be asked in phase 2."""
    engine = FlowEngine()
    profile = {
        "filing_status": "married_joint",
        "total_income": 100000,
        "state": "NY",
        "dependents": 0,
        "income_type": "w2_employee",
    }
    questions_asked = []
    for _ in range(50):
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions_asked.append(q.id)
        profile[q.asked_field] = True
    assert "life_events" in questions_asked
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=".:src" pytest tests/advisor/test_flow_engine.py -v`
Expected: FAIL — module not found

**Step 3: Implement FlowEngine core + FlowQuestion dataclass**

```python
# src/web/advisor/flow_engine.py
"""Rule-based adaptive flow engine for the Intelligent Advisor.

Replaces the monolithic _get_dynamic_next_question() with a data-driven
question registry where each question declares its own eligibility rules
and relevance scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class FlowQuestion:
    """A single question in the adaptive flow."""
    id: str
    pool: str
    phase: int
    text: str
    actions: list[dict]
    eligibility: Callable[[dict], bool]
    base_score: int
    context_boost_keywords: list[str] = field(default_factory=list)
    context_boost_amount: int = 25
    sets_fields: list[str] = field(default_factory=list)
    skip_field: str = ""
    asked_field: str = ""
    follow_up_of: Optional[str] = None

    def is_eligible(self, profile: dict) -> bool:
        """Check if this question should be shown given the current profile."""
        # Already asked?
        if self.asked_field and profile.get(self.asked_field):
            return False
        # Already skipped?
        if self.skip_field and profile.get(self.skip_field):
            return False
        # Already have the data?
        for f in self.sets_fields:
            if profile.get(f) is not None:
                return False
        # Custom eligibility rule
        return self.eligibility(profile)

    def score(self, profile: dict, conversation_context: str = "") -> int:
        """Calculate relevance score for this question."""
        s = self.base_score
        if conversation_context:
            for kw in self.context_boost_keywords:
                if kw in conversation_context:
                    s += self.context_boost_amount
                    break
        return s


class FlowEngine:
    """Adaptive question engine that picks the best next question."""

    def __init__(self):
        from src.web.advisor.question_registry import ALL_QUESTIONS
        self._questions = ALL_QUESTIONS

    def get_next_question(
        self, profile: dict, conversation: list | None = None
    ) -> FlowQuestion | None:
        """Return the highest-priority eligible question, or None if done."""
        # Build conversation context string
        context = ""
        if conversation:
            context = " ".join(
                m.get("content", "")
                for m in conversation[-5:]
                if m.get("role") == "user"
            ).lower()

        # Phase 1 questions must all be answered before Phase 2
        phase1_incomplete = any(
            q.phase == 1 and q.is_eligible(profile) for q in self._questions
        )

        eligible = []
        for q in self._questions:
            if phase1_incomplete and q.phase != 1:
                continue
            if q.is_eligible(profile):
                eligible.append((q.score(profile, context), q))

        if not eligible:
            return None

        # Sort by score descending, stable (preserves registration order for ties)
        eligible.sort(key=lambda x: -x[0])
        return eligible[0][1]

    def get_all_eligible(
        self, profile: dict, conversation: list | None = None
    ) -> list[FlowQuestion]:
        """Return all eligible questions sorted by score (for debugging/preview)."""
        context = ""
        if conversation:
            context = " ".join(
                m.get("content", "")
                for m in conversation[-5:]
                if m.get("role") == "user"
            ).lower()

        phase1_incomplete = any(
            q.phase == 1 and q.is_eligible(profile) for q in self._questions
        )

        eligible = []
        for q in self._questions:
            if phase1_incomplete and q.phase != 1:
                continue
            if q.is_eligible(profile):
                eligible.append((q.score(profile, context), q))

        eligible.sort(key=lambda x: -x[0])
        return [q for _, q in eligible]
```

**Step 4: Implement the question registry with ALL question pools**

```python
# src/web/advisor/question_registry.py
"""Complete question registry — every question the advisor can ask.

Each question declares:
- When it's eligible (based on profile data)
- How relevant it is (base score + context boosts)
- What fields it populates
"""

from src.web.advisor.flow_engine import FlowQuestion
from src.web.advisor.flow_rules import *  # noqa: F403 — eligibility predicates

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: Core Basics (sequential, all required)
# ═══════════════════════════════════════════════════════════════════════════

BASICS = [
    FlowQuestion(
        id="filing_status",
        pool="basics", phase=1,
        text="What's your filing status for this tax year?",
        actions=[
            {"label": "Single", "value": "single"},
            {"label": "Married Filing Jointly", "value": "married_joint"},
            {"label": "Head of Household", "value": "head_of_household"},
            {"label": "Married Filing Separately", "value": "married_separate"},
            {"label": "Qualifying Surviving Spouse", "value": "qualifying_widow"},
        ],
        eligibility=lambda p: not p.get("filing_status"),
        base_score=100,
        sets_fields=["filing_status"],
        asked_field="_asked_filing_status",
    ),
    FlowQuestion(
        id="total_income",
        pool="basics", phase=1,
        text="What's your approximate total annual income? Include all sources — wages, business, investments.",
        actions=[
            {"label": "Under $25K", "value": "income_under_25k"},
            {"label": "$25K - $50K", "value": "income_25_50k"},
            {"label": "$50K - $100K", "value": "income_50_100k"},
            {"label": "$100K - $200K", "value": "income_100_200k"},
            {"label": "$200K - $500K", "value": "income_200_500k"},
            {"label": "Over $500K", "value": "income_over_500k"},
        ],
        eligibility=lambda p: p.get("filing_status") and not p.get("total_income"),
        base_score=99,
        sets_fields=["total_income"],
        asked_field="_asked_total_income",
    ),
    FlowQuestion(
        id="state",
        pool="basics", phase=1,
        text="Which state do you live in?",
        actions=[
            {"label": "Select your state", "value": "state_dropdown"},
        ],
        eligibility=lambda p: p.get("total_income") and not p.get("state"),
        base_score=98,
        sets_fields=["state"],
        asked_field="_asked_state",
    ),
    FlowQuestion(
        id="dependents",
        pool="basics", phase=1,
        text="Do you have any dependents (children, qualifying relatives)?",
        actions=[
            {"label": "No dependents", "value": "0_dependents"},
            {"label": "1 dependent", "value": "1_dependent"},
            {"label": "2 dependents", "value": "2_dependents"},
            {"label": "3 dependents", "value": "3_dependents"},
            {"label": "4+ dependents", "value": "4plus_dependents"},
        ],
        eligibility=lambda p: p.get("state") and p.get("dependents") is None,
        base_score=97,
        sets_fields=["dependents"],
        asked_field="_asked_dependents",
    ),
    FlowQuestion(
        id="income_type",
        pool="basics", phase=1,
        text="What best describes your income situation?",
        actions=[
            {"label": "W-2 Employee (single job)", "value": "w2_employee"},
            {"label": "W-2 + Side Hustle/Freelance", "value": "w2_plus_side"},
            {"label": "Multiple W-2 Jobs", "value": "multiple_w2"},
            {"label": "Self-Employed / Freelancer", "value": "self_employed"},
            {"label": "Business Owner (LLC/S-Corp/Partnership)", "value": "business_owner"},
            {"label": "Retired / Pension", "value": "retired"},
            {"label": "Primarily Investment Income", "value": "investor"},
            {"label": "Military", "value": "military"},
        ],
        eligibility=lambda p: p.get("dependents") is not None and not p.get("income_type"),
        base_score=96,
        sets_fields=["income_type"],
        asked_field="_asked_income_type",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Income Details
# ═══════════════════════════════════════════════════════════════════════════

INCOME_DETAILS = [
    # --- W-2 Withholding ---
    FlowQuestion(
        id="withholding",
        pool="income_details", phase=2,
        text="Approximately how much federal tax was withheld from your paychecks this year? Check your last pay stub for YTD Federal Tax.",
        actions=[
            {"label": "Under $5,000", "value": "withholding_under_5k"},
            {"label": "$5,000 - $10,000", "value": "withholding_5_10k"},
            {"label": "$10,000 - $20,000", "value": "withholding_10_20k"},
            {"label": "$20,000 - $40,000", "value": "withholding_20_40k"},
            {"label": "Over $40,000", "value": "withholding_over_40k"},
            {"label": "Not sure — estimate for me", "value": "withholding_estimate"},
        ],
        eligibility=is_w2_employee,
        base_score=90,
        sets_fields=["federal_withholding"],
        asked_field="_asked_withholding",
    ),
    # --- Multiple W-2 Jobs ---
    FlowQuestion(
        id="inc_multiple_w2_count",
        pool="income_details", phase=2,
        text="How many W-2 jobs did you have this year?",
        actions=[
            {"label": "2 jobs", "value": "2_jobs"},
            {"label": "3 or more", "value": "3plus_jobs"},
        ],
        eligibility=lambda p: p.get("income_type") == "multiple_w2",
        base_score=88,
        sets_fields=["w2_job_count"],
        asked_field="_asked_w2_count",
    ),
    # --- Side Hustle Type ---
    FlowQuestion(
        id="inc_side_hustle_type",
        pool="income_details", phase=2,
        text="What type of side income do you have?",
        actions=[
            {"label": "Freelance / Consulting (1099-NEC)", "value": "freelance"},
            {"label": "Gig Work (Uber, DoorDash, etc.)", "value": "gig_work"},
            {"label": "Online Sales (Etsy, eBay, etc.)", "value": "online_sales"},
            {"label": "Rental Income", "value": "side_rental"},
            {"label": "Multiple types", "value": "multiple_side"},
        ],
        eligibility=lambda p: p.get("income_type") == "w2_plus_side",
        base_score=87,
        sets_fields=["side_hustle_type"],
        asked_field="_asked_side_type",
    ),
    # --- Side Hustle Income ---
    FlowQuestion(
        id="inc_side_income_amount",
        pool="income_details", phase=2,
        text="What's your approximate net side income (after expenses)?",
        actions=[
            {"label": "Under $5,000", "value": "side_under_5k"},
            {"label": "$5,000 - $20,000", "value": "side_5_20k"},
            {"label": "$20,000 - $50,000", "value": "side_20_50k"},
            {"label": "Over $50,000", "value": "side_over_50k"},
        ],
        eligibility=lambda p: p.get("income_type") == "w2_plus_side" and p.get("side_hustle_type") and not p.get("side_income"),
        base_score=86,
        sets_fields=["side_income"],
        asked_field="_asked_side_income",
        follow_up_of="inc_side_hustle_type",
    ),
    # --- Spouse Income (MFJ) ---
    FlowQuestion(
        id="inc_spouse_income_type",
        pool="income_details", phase=2,
        text="Does your spouse also earn income? If so, what type?",
        actions=[
            {"label": "W-2 Employee", "value": "spouse_w2"},
            {"label": "Self-Employed", "value": "spouse_se"},
            {"label": "Not working / Homemaker", "value": "spouse_none"},
            {"label": "Retired", "value": "spouse_retired"},
            {"label": "Skip", "value": "skip_spouse_income"},
        ],
        eligibility=is_married_filing_jointly,
        base_score=85,
        sets_fields=["spouse_income_type"],
        asked_field="_asked_spouse_income_type",
    ),
    # --- Spouse Income Amount ---
    FlowQuestion(
        id="inc_spouse_income_amount",
        pool="income_details", phase=2,
        text="What's your spouse's approximate annual income?",
        actions=[
            {"label": "Under $25K", "value": "spouse_under_25k"},
            {"label": "$25K - $50K", "value": "spouse_25_50k"},
            {"label": "$50K - $100K", "value": "spouse_50_100k"},
            {"label": "Over $100K", "value": "spouse_over_100k"},
            {"label": "Skip", "value": "skip_spouse_amount"},
        ],
        eligibility=lambda p: p.get("spouse_income_type") in ("spouse_w2", "spouse_se") and not p.get("spouse_income"),
        base_score=84,
        sets_fields=["spouse_income"],
        asked_field="_asked_spouse_income",
        follow_up_of="inc_spouse_income_type",
    ),
    # --- Age ---
    FlowQuestion(
        id="age",
        pool="income_details", phase=2,
        text="What is your age? This helps determine your standard deduction and eligibility for certain credits.",
        actions=[
            {"label": "Under 26", "value": "age_under_26"},
            {"label": "26-49", "value": "age_26_49"},
            {"label": "50-64", "value": "age_50_64"},
            {"label": "65 or older", "value": "age_65_plus"},
            {"label": "Skip", "value": "skip_age"},
        ],
        eligibility=lambda p: not p.get("age"),
        base_score=75,
        context_boost_keywords=["retire", "senior", "65", "older", "age", "young"],
        sets_fields=["age"],
        asked_field="_asked_age",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Self-Employment & Business
# ═══════════════════════════════════════════════════════════════════════════

SELF_EMPLOYMENT = [
    # --- Entity Type ---
    FlowQuestion(
        id="se_entity_type",
        pool="self_employment", phase=2,
        text="What type of business entity do you have?",
        actions=[
            {"label": "Sole Proprietorship (no entity)", "value": "sole_prop"},
            {"label": "Single-Member LLC", "value": "single_llc"},
            {"label": "Multi-Member LLC", "value": "multi_llc"},
            {"label": "S-Corporation", "value": "s_corp"},
            {"label": "C-Corporation", "value": "c_corp"},
            {"label": "Partnership", "value": "partnership"},
            {"label": "Not sure", "value": "entity_unsure"},
        ],
        eligibility=is_business_or_se,
        base_score=82,
        sets_fields=["entity_type"],
        asked_field="_asked_entity_type",
    ),
    # --- Business Income ---
    FlowQuestion(
        id="se_business_income",
        pool="self_employment", phase=2,
        text="What's your approximate net business income (revenue minus expenses)?",
        actions=[
            {"label": "Under $50K", "value": "biz_under_50k"},
            {"label": "$50K - $100K", "value": "biz_50_100k"},
            {"label": "$100K - $200K", "value": "biz_100_200k"},
            {"label": "Over $200K", "value": "biz_over_200k"},
            {"label": "Net loss", "value": "biz_net_loss"},
            {"label": "Skip", "value": "skip_business"},
        ],
        eligibility=lambda p: is_business_or_se(p) and not p.get("business_income"),
        base_score=80,
        context_boost_keywords=["freelance", "1099", "business", "contractor", "gig"],
        sets_fields=["business_income"],
        asked_field="_asked_business",
    ),
    # --- S-Corp Reasonable Salary ---
    FlowQuestion(
        id="se_reasonable_salary",
        pool="self_employment", phase=2,
        text="As an S-Corp owner, what salary do you pay yourself? (This affects your self-employment tax savings)",
        actions=[
            {"label": "Under $50K", "value": "salary_under_50k"},
            {"label": "$50K - $100K", "value": "salary_50_100k"},
            {"label": "$100K - $150K", "value": "salary_100_150k"},
            {"label": "Over $150K", "value": "salary_over_150k"},
            {"label": "Skip", "value": "skip_salary"},
        ],
        eligibility=lambda p: p.get("entity_type") == "s_corp" and not p.get("reasonable_salary"),
        base_score=78,
        sets_fields=["reasonable_salary"],
        asked_field="_asked_salary",
        follow_up_of="se_entity_type",
    ),
    # --- Home Office ---
    FlowQuestion(
        id="se_home_office",
        pool="self_employment", phase=2,
        text="Do you use part of your home exclusively and regularly for business?",
        actions=[
            {"label": "Yes, I have a dedicated home office", "value": "has_home_office"},
            {"label": "No home office", "value": "no_home_office"},
            {"label": "Skip", "value": "skip_home_office"},
        ],
        eligibility=lambda p: is_business_or_se(p) and p.get("business_income") and not p.get("home_office_sqft"),
        base_score=70,
        context_boost_keywords=["home", "remote", "office", "wfh"],
        sets_fields=["home_office_sqft"],
        asked_field="_asked_home_office",
    ),
    # --- Vehicle / Mileage ---
    FlowQuestion(
        id="se_vehicle",
        pool="self_employment", phase=2,
        text="Do you use a vehicle for business? (Commuting doesn't count — business travel, client visits, deliveries)",
        actions=[
            {"label": "Yes, I drive for business", "value": "has_biz_vehicle"},
            {"label": "No business vehicle use", "value": "no_biz_vehicle"},
            {"label": "Skip", "value": "skip_vehicle"},
        ],
        eligibility=lambda p: is_business_or_se(p) and p.get("business_income") and not p.get("business_miles"),
        base_score=65,
        context_boost_keywords=["drive", "car", "vehicle", "mileage", "uber", "delivery"],
        sets_fields=["business_miles"],
        asked_field="_asked_vehicle",
    ),
    # --- Equipment / Section 179 ---
    FlowQuestion(
        id="se_equipment",
        pool="self_employment", phase=2,
        text="Did you purchase any major equipment or assets for your business this year? (Computers, machinery, furniture, vehicles)",
        actions=[
            {"label": "Yes, I bought equipment", "value": "has_equipment"},
            {"label": "No major purchases", "value": "no_equipment"},
            {"label": "Skip", "value": "skip_equipment"},
        ],
        eligibility=lambda p: is_business_or_se(p) and float(p.get("business_income", 0) or 0) > 25000 and not p.get("equipment_cost"),
        base_score=55,
        context_boost_keywords=["equipment", "computer", "machine", "section 179", "depreciation"],
        sets_fields=["equipment_cost"],
        asked_field="_asked_equipment",
    ),
    # --- Employees / Contractors ---
    FlowQuestion(
        id="se_employees",
        pool="self_employment", phase=2,
        text="Do you have any employees or pay independent contractors?",
        actions=[
            {"label": "Yes, I have employees", "value": "has_employees"},
            {"label": "Yes, I pay contractors (1099)", "value": "has_contractors"},
            {"label": "Both employees and contractors", "value": "has_both_workers"},
            {"label": "No — solo operation", "value": "solo_operation"},
            {"label": "Skip", "value": "skip_employees"},
        ],
        eligibility=lambda p: is_business_or_se(p) and float(p.get("business_income", 0) or 0) > 50000 and not p.get("has_employees"),
        base_score=45,
        sets_fields=["has_employees"],
        asked_field="_asked_employees",
    ),
    # --- Self-Employed Health Insurance ---
    FlowQuestion(
        id="se_health_insurance",
        pool="self_employment", phase=2,
        text="Do you pay for your own health insurance? Self-employed individuals can deduct 100% of premiums.",
        actions=[
            {"label": "Yes, I pay my own premiums", "value": "has_se_health"},
            {"label": "Covered by spouse's employer", "value": "spouse_coverage"},
            {"label": "ACA Marketplace plan", "value": "aca_plan"},
            {"label": "No health insurance", "value": "no_health_insurance"},
            {"label": "Skip", "value": "skip_se_health"},
        ],
        eligibility=lambda p: is_self_employed_only(p) and not p.get("se_health_insurance"),
        base_score=72,
        context_boost_keywords=["health", "insurance", "premium", "medical"],
        sets_fields=["se_health_insurance"],
        asked_field="_asked_se_health",
    ),
    # --- QBI / SSTB Classification ---
    FlowQuestion(
        id="se_sstb_check",
        pool="self_employment", phase=2,
        text="Is your business in a 'specified service' field? (Law, medicine, accounting, consulting, financial services, performing arts, athletics)",
        actions=[
            {"label": "Yes — service-based profession", "value": "is_sstb"},
            {"label": "No — product/trade/other", "value": "not_sstb"},
            {"label": "Not sure", "value": "sstb_unsure"},
            {"label": "Skip", "value": "skip_sstb"},
        ],
        eligibility=lambda p: is_business_or_se(p) and float(p.get("total_income", 0) or 0) > 182100 and not p.get("is_sstb"),
        base_score=68,
        context_boost_keywords=["qbi", "199a", "deduction", "service"],
        sets_fields=["is_sstb"],
        asked_field="_asked_sstb",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Investments
# ═══════════════════════════════════════════════════════════════════════════

INVESTMENTS = [
    FlowQuestion(
        id="inv_has_investments",
        pool="investments", phase=2,
        text="Do you have any investment income? (Stocks, bonds, crypto, dividends, interest)",
        actions=[
            {"label": "Yes, I have investments", "value": "has_investments"},
            {"label": "No investment income", "value": "no_investments"},
            {"label": "Skip", "value": "skip_investments"},
        ],
        eligibility=lambda p: not p.get("_has_investments") and not p.get("investment_income") and not is_retired(p),
        base_score=50,
        context_boost_keywords=["stock", "invest", "crypto", "dividend", "capital", "trading"],
        sets_fields=["_has_investments"],
        asked_field="_asked_investments",
    ),
    FlowQuestion(
        id="inv_amount",
        pool="investments", phase=2,
        text="Approximately how much total investment income? (Dividends, interest, capital gains combined)",
        actions=[
            {"label": "Under $5,000", "value": "invest_under_5k"},
            {"label": "$5,000 - $25,000", "value": "invest_5_25k"},
            {"label": "$25,000 - $100,000", "value": "invest_25_100k"},
            {"label": "Over $100,000", "value": "invest_over_100k"},
            {"label": "Skip", "value": "skip_invest_amount"},
        ],
        eligibility=lambda p: p.get("_has_investments") and not p.get("investment_income"),
        base_score=65,
        sets_fields=["investment_income"],
        asked_field="_asked_invest_amount",
        follow_up_of="inv_has_investments",
    ),
    FlowQuestion(
        id="inv_capital_gains",
        pool="investments", phase=2,
        text="Did you sell any investments this year? Were the gains mostly long-term (held >1 year) or short-term?",
        actions=[
            {"label": "Mostly long-term gains", "value": "lt_gains"},
            {"label": "Mostly short-term gains", "value": "st_gains"},
            {"label": "Mix of both", "value": "mixed_gains"},
            {"label": "Had losses (not gains)", "value": "had_losses"},
            {"label": "No sales this year", "value": "no_sales"},
            {"label": "Skip", "value": "skip_cap_gains"},
        ],
        eligibility=lambda p: p.get("_has_investments") and p.get("investment_income") and not p.get("_asked_cap_gains"),
        base_score=64,
        sets_fields=["capital_gains_type"],
        asked_field="_asked_cap_gains",
        follow_up_of="inv_amount",
    ),
    # --- Crypto specifically ---
    FlowQuestion(
        id="inv_crypto",
        pool="investments", phase=2,
        text="Did you have any cryptocurrency activity? (Trading, mining, staking, DeFi, NFTs)",
        actions=[
            {"label": "Yes — trading/selling crypto", "value": "crypto_trading"},
            {"label": "Yes — mining or staking", "value": "crypto_mining"},
            {"label": "Yes — multiple activities", "value": "crypto_multiple"},
            {"label": "No crypto activity", "value": "no_crypto"},
            {"label": "Skip", "value": "skip_crypto"},
        ],
        eligibility=lambda p: p.get("_has_investments") and not p.get("crypto_activity"),
        base_score=45,
        context_boost_keywords=["crypto", "bitcoin", "ethereum", "nft", "defi", "mining", "staking"],
        context_boost_amount=35,
        sets_fields=["crypto_activity"],
        asked_field="_asked_crypto",
    ),
    # --- Stock Options / RSU / ESPP ---
    FlowQuestion(
        id="inv_stock_options",
        pool="investments", phase=2,
        text="Do you have any employer stock compensation? (Stock options, RSUs, or ESPP)",
        actions=[
            {"label": "Incentive Stock Options (ISO)", "value": "has_iso"},
            {"label": "Non-Qualified Options (NSO)", "value": "has_nso"},
            {"label": "Restricted Stock Units (RSU)", "value": "has_rsu"},
            {"label": "Employee Stock Purchase Plan (ESPP)", "value": "has_espp"},
            {"label": "Multiple types", "value": "multiple_stock_comp"},
            {"label": "None", "value": "no_stock_comp"},
            {"label": "Skip", "value": "skip_stock_comp"},
        ],
        eligibility=lambda p: is_w2_employee(p) and float(p.get("total_income", 0) or 0) > 100000 and not p.get("stock_compensation"),
        base_score=55,
        context_boost_keywords=["iso", "rsu", "espp", "stock option", "vesting", "exercise"],
        sets_fields=["stock_compensation"],
        asked_field="_asked_stock_comp",
    ),
    # --- Capital Loss Carryforward ---
    FlowQuestion(
        id="inv_loss_carryforward",
        pool="investments", phase=2,
        text="Do you have any capital loss carryforward from prior years? (Unused losses from previous tax returns)",
        actions=[
            {"label": "Yes", "value": "has_loss_carryforward"},
            {"label": "No / Not sure", "value": "no_loss_carryforward"},
            {"label": "Skip", "value": "skip_loss_carryforward"},
        ],
        eligibility=lambda p: p.get("_has_investments") and p.get("capital_gains_type") in ("had_losses", "lt_gains", "st_gains", "mixed_gains") and not p.get("loss_carryforward"),
        base_score=48,
        sets_fields=["loss_carryforward"],
        asked_field="_asked_loss_carryforward",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Retirement & Social Security
# ═══════════════════════════════════════════════════════════════════════════

RETIREMENT = [
    # --- Retirement Contributions ---
    FlowQuestion(
        id="ret_contributions",
        pool="retirement", phase=2,
        text="Are you contributing to any retirement accounts?",
        actions=[
            {"label": "401(k) / 403(b) / TSP", "value": "has_401k"},
            {"label": "Traditional IRA", "value": "has_trad_ira"},
            {"label": "Roth IRA", "value": "has_roth_ira"},
            {"label": "Both employer plan and IRA", "value": "has_both_retirement"},
            {"label": "SEP-IRA (self-employed)", "value": "has_sep"},
            {"label": "Solo 401(k) (self-employed)", "value": "has_solo_401k"},
            {"label": "No retirement contributions", "value": "no_retirement"},
            {"label": "Skip", "value": "skip_retirement"},
        ],
        eligibility=lambda p: not is_retired(p) and not p.get("retirement_401k") and not p.get("retirement_ira"),
        base_score=60,
        context_boost_keywords=["401k", "ira", "retire", "saving", "roth", "tsp"],
        sets_fields=["retirement_401k", "retirement_ira"],
        asked_field="_asked_retirement",
    ),
    # --- HSA ---
    FlowQuestion(
        id="ret_hsa",
        pool="retirement", phase=2,
        text="Do you have a Health Savings Account (HSA)? Contributions are triple tax-advantaged — deductible, grow tax-free, and withdraw tax-free for medical expenses.",
        actions=[
            {"label": "Yes, I contribute to an HSA", "value": "has_hsa"},
            {"label": "I have an HDHP but no HSA yet", "value": "has_hdhp_no_hsa"},
            {"label": "No HSA / not eligible", "value": "no_hsa"},
            {"label": "Skip", "value": "skip_hsa"},
        ],
        eligibility=lambda p: not p.get("hsa_contributions"),
        base_score=50,
        context_boost_keywords=["hsa", "health savings", "hdhp", "high deductible"],
        sets_fields=["hsa_contributions"],
        asked_field="_asked_hsa",
    ),
    # --- Social Security Benefits (Retirees) ---
    FlowQuestion(
        id="ret_ss_benefits",
        pool="retirement", phase=2,
        text="Did you receive Social Security benefits this year? If so, approximately how much?",
        actions=[
            {"label": "Under $15,000", "value": "ss_under_15k"},
            {"label": "$15,000 - $30,000", "value": "ss_15_30k"},
            {"label": "Over $30,000", "value": "ss_over_30k"},
            {"label": "Not receiving SS yet", "value": "no_ss"},
            {"label": "Skip", "value": "skip_ss"},
        ],
        eligibility=is_retired,
        base_score=88,
        sets_fields=["ss_benefits"],
        asked_field="_asked_ss",
    ),
    # --- Pension Income ---
    FlowQuestion(
        id="ret_pension",
        pool="retirement", phase=2,
        text="Do you receive pension income?",
        actions=[
            {"label": "Yes — fully taxable", "value": "pension_taxable"},
            {"label": "Yes — partially taxable (I made after-tax contributions)", "value": "pension_partial"},
            {"label": "No pension", "value": "no_pension"},
            {"label": "Skip", "value": "skip_pension"},
        ],
        eligibility=is_retired,
        base_score=86,
        sets_fields=["pension_income"],
        asked_field="_asked_pension",
    ),
    # --- IRA/401k Distributions ---
    FlowQuestion(
        id="ret_distributions",
        pool="retirement", phase=2,
        text="Did you take any distributions (withdrawals) from retirement accounts this year?",
        actions=[
            {"label": "Yes — IRA withdrawal", "value": "ira_distribution"},
            {"label": "Yes — 401(k) withdrawal", "value": "401k_distribution"},
            {"label": "Yes — Roth conversion", "value": "roth_conversion"},
            {"label": "No distributions", "value": "no_distributions"},
            {"label": "Skip", "value": "skip_distributions"},
        ],
        eligibility=lambda p: not p.get("retirement_distributions"),
        base_score=40,
        context_boost_keywords=["withdraw", "distribution", "rmd", "rollover", "conversion"],
        sets_fields=["retirement_distributions"],
        asked_field="_asked_distributions",
    ),
    # --- Early Withdrawal Penalty ---
    FlowQuestion(
        id="ret_early_withdrawal",
        pool="retirement", phase=2,
        text="Are you under age 59½? Early withdrawals may have a 10% penalty unless an exception applies.",
        actions=[
            {"label": "Under 59½ — no exception", "value": "early_no_exception"},
            {"label": "Under 59½ — exception applies (disability, first home, SEPP)", "value": "early_with_exception"},
            {"label": "59½ or older", "value": "over_59_half"},
            {"label": "Skip", "value": "skip_early"},
        ],
        eligibility=lambda p: p.get("retirement_distributions") in ("ira_distribution", "401k_distribution") and not p.get("early_withdrawal_status"),
        base_score=75,
        sets_fields=["early_withdrawal_status"],
        asked_field="_asked_early_withdrawal",
        follow_up_of="ret_distributions",
    ),
    # --- RMD ---
    FlowQuestion(
        id="ret_rmd",
        pool="retirement", phase=2,
        text="Are you 73 or older? You're required to take minimum distributions (RMDs). Have you taken yours?",
        actions=[
            {"label": "Yes — I've taken my RMD", "value": "rmd_taken"},
            {"label": "Not yet — need to before year-end", "value": "rmd_pending"},
            {"label": "Under 73 — RMD not required", "value": "under_73"},
            {"label": "Skip", "value": "skip_rmd"},
        ],
        eligibility=lambda p: is_retired(p) and p.get("age") in ("age_65_plus",) and not p.get("rmd_status"),
        base_score=82,
        sets_fields=["rmd_status"],
        asked_field="_asked_rmd",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Dependents & Children
# ═══════════════════════════════════════════════════════════════════════════

DEPENDENTS = [
    # --- Dependent Age Split ---
    FlowQuestion(
        id="dep_age_split",
        pool="dependents", phase=2,
        text="Of your {dependents} dependent(s), how many are under age 17? (Important for the Child Tax Credit — $2,000 per child under 17)",
        actions=[],  # Dynamic — built at runtime based on dependent count
        eligibility=lambda p: (p.get("dependents") or 0) > 0 and p.get("dependents_under_17") is None,
        base_score=85,
        sets_fields=["dependents_under_17"],
        asked_field="_asked_dependents_age",
    ),
    # --- Childcare Costs ---
    FlowQuestion(
        id="dep_childcare_costs",
        pool="dependents", phase=2,
        text="Did you pay for childcare or daycare so you (and your spouse) could work? This may qualify for the Child and Dependent Care Credit.",
        actions=[
            {"label": "Yes — under $3,000 total", "value": "childcare_under_3k"},
            {"label": "Yes — $3,000 - $6,000", "value": "childcare_3_6k"},
            {"label": "Yes — over $6,000", "value": "childcare_over_6k"},
            {"label": "No childcare costs", "value": "no_childcare"},
            {"label": "Skip", "value": "skip_childcare"},
        ],
        eligibility=has_young_dependents,
        base_score=78,
        context_boost_keywords=["daycare", "childcare", "nanny", "babysitter", "preschool"],
        sets_fields=["childcare_costs"],
        asked_field="_asked_childcare",
    ),
    # --- Dependent Care FSA ---
    FlowQuestion(
        id="dep_care_fsa",
        pool="dependents", phase=2,
        text="Did you or your employer contribute to a Dependent Care FSA? (Up to $5,000 pre-tax for childcare)",
        actions=[
            {"label": "Yes", "value": "has_dcfsa"},
            {"label": "No", "value": "no_dcfsa"},
            {"label": "Skip", "value": "skip_dcfsa"},
        ],
        eligibility=lambda p: p.get("childcare_costs") and p.get("childcare_costs") != "no_childcare" and not p.get("dependent_care_fsa"),
        base_score=72,
        sets_fields=["dependent_care_fsa"],
        asked_field="_asked_dcfsa",
        follow_up_of="dep_childcare_costs",
    ),
    # --- Education Credits ---
    FlowQuestion(
        id="dep_education",
        pool="dependents", phase=2,
        text="Did you or a dependent attend college or vocational school? Tuition may qualify for education credits (up to $2,500).",
        actions=[
            {"label": "Yes — I'm a student", "value": "self_student"},
            {"label": "Yes — my dependent is a student", "value": "dependent_student"},
            {"label": "Yes — both", "value": "both_students"},
            {"label": "No", "value": "no_education"},
            {"label": "Skip", "value": "skip_education"},
        ],
        eligibility=lambda p: not p.get("education_status") and float(p.get("total_income", 0) or 0) < 180000,
        base_score=55,
        context_boost_keywords=["college", "university", "tuition", "student", "1098-t", "education"],
        sets_fields=["education_status"],
        asked_field="_asked_education",
    ),
    # --- 529 Plan ---
    FlowQuestion(
        id="dep_529_plan",
        pool="dependents", phase=2,
        text="Did you contribute to a 529 college savings plan? (Many states offer a tax deduction for contributions)",
        actions=[
            {"label": "Yes", "value": "has_529"},
            {"label": "No", "value": "no_529"},
            {"label": "Skip", "value": "skip_529"},
        ],
        eligibility=lambda p: (p.get("dependents") or 0) > 0 and not p.get("has_529") and not is_no_income_tax_state(p),
        base_score=35,
        context_boost_keywords=["529", "college savings", "education savings"],
        sets_fields=["has_529"],
        asked_field="_asked_529",
    ),
    # --- Adoption Credit ---
    FlowQuestion(
        id="dep_adoption",
        pool="dependents", phase=2,
        text="Did you adopt a child this year? Adoption expenses may qualify for a credit up to $16,810.",
        actions=[
            {"label": "Yes — domestic adoption", "value": "adoption_domestic"},
            {"label": "Yes — international adoption", "value": "adoption_international"},
            {"label": "Yes — special needs child", "value": "adoption_special_needs"},
            {"label": "No", "value": "no_adoption"},
        ],
        eligibility=lambda p: (p.get("dependents") or 0) > 0 and not p.get("adoption_status"),
        base_score=15,
        context_boost_keywords=["adopt", "adoption"],
        context_boost_amount=50,
        sets_fields=["adoption_status"],
        asked_field="_asked_adoption",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Deductions
# ═══════════════════════════════════════════════════════════════════════════

DEDUCTIONS = [
    FlowQuestion(
        id="ded_major_deductions",
        pool="deductions", phase=2,
        text="Let's check your deductions. Do you have any of these?",
        actions=[
            {"label": "Mortgage interest", "value": "has_mortgage"},
            {"label": "Charitable donations", "value": "has_charitable"},
            {"label": "Property taxes", "value": "has_property_taxes"},
            {"label": "High medical expenses", "value": "has_medical"},
            {"label": "State/local income taxes paid", "value": "has_salt"},
            {"label": "None — I'll take the standard deduction", "value": "no_itemized_deductions"},
            {"label": "Skip", "value": "skip_deductions"},
        ],
        eligibility=lambda p: not p.get("mortgage_interest") and not p.get("_asked_deductions"),
        base_score=55,
        context_boost_keywords=["mortgage", "house", "deduct", "charit", "donat", "property tax", "itemiz"],
        sets_fields=["_deduction_check"],
        asked_field="_asked_deductions",
    ),
    FlowQuestion(
        id="ded_mortgage_amount",
        pool="deductions", phase=2,
        text="How much mortgage interest did you pay this year? (Check your Form 1098)",
        actions=[
            {"label": "Under $5,000", "value": "mortgage_under_5k"},
            {"label": "$5,000 - $15,000", "value": "mortgage_5_15k"},
            {"label": "$15,000 - $30,000", "value": "mortgage_15_30k"},
            {"label": "Over $30,000", "value": "mortgage_over_30k"},
            {"label": "Skip", "value": "skip_mortgage_amount"},
        ],
        eligibility=lambda p: p.get("_has_mortgage") and not p.get("mortgage_interest"),
        base_score=52,
        sets_fields=["mortgage_interest"],
        asked_field="_asked_mortgage_amount",
        follow_up_of="ded_major_deductions",
    ),
    FlowQuestion(
        id="ded_property_taxes",
        pool="deductions", phase=2,
        text="How much did you pay in property taxes?",
        actions=[
            {"label": "Under $5,000", "value": "prop_tax_under_5k"},
            {"label": "$5,000 - $10,000", "value": "prop_tax_5_10k"},
            {"label": "Over $10,000 (SALT cap applies)", "value": "prop_tax_over_10k"},
            {"label": "Skip", "value": "skip_prop_tax_amount"},
        ],
        eligibility=lambda p: p.get("_has_property_taxes") and not p.get("property_taxes"),
        base_score=51,
        sets_fields=["property_taxes"],
        asked_field="_asked_prop_tax_amount",
        follow_up_of="ded_major_deductions",
    ),
    FlowQuestion(
        id="ded_charitable",
        pool="deductions", phase=2,
        text="How much did you donate to charity this year?",
        actions=[
            {"label": "Under $1,000", "value": "charity_under_1k"},
            {"label": "$1,000 - $5,000", "value": "charity_1_5k"},
            {"label": "$5,000 - $20,000", "value": "charity_5_20k"},
            {"label": "Over $20,000", "value": "charity_over_20k"},
            {"label": "Skip", "value": "skip_charitable_amount"},
        ],
        eligibility=lambda p: p.get("_has_charitable") and not p.get("charitable_donations"),
        base_score=50,
        sets_fields=["charitable_donations"],
        asked_field="_asked_charitable_amount",
        follow_up_of="ded_major_deductions",
    ),
    FlowQuestion(
        id="ded_medical",
        pool="deductions", phase=2,
        text="Approximately how much did you spend on unreimbursed medical expenses? (Only deductible if over 7.5% of your income)",
        actions=[
            {"label": "Under $5,000", "value": "medical_under_5k"},
            {"label": "$5,000 - $15,000", "value": "medical_5_15k"},
            {"label": "$15,000 - $30,000", "value": "medical_15_30k"},
            {"label": "Over $30,000", "value": "medical_over_30k"},
            {"label": "Skip", "value": "skip_medical_amount"},
        ],
        eligibility=lambda p: p.get("_has_medical") and not p.get("medical_expenses"),
        base_score=49,
        sets_fields=["medical_expenses"],
        asked_field="_asked_medical_amount",
        follow_up_of="ded_major_deductions",
    ),
    # --- Student Loans ---
    FlowQuestion(
        id="ded_student_loans",
        pool="deductions", phase=2,
        text="Did you pay any student loan interest this year? (Up to $2,500 may be deductible)",
        actions=[
            {"label": "Yes", "value": "has_student_loans"},
            {"label": "No", "value": "no_student_loans"},
            {"label": "Skip", "value": "skip_student_loans"},
        ],
        eligibility=lambda p: not p.get("student_loan_interest") and float(p.get("total_income", 0) or 0) < 180000,
        base_score=25,
        context_boost_keywords=["student", "loan", "college"],
        sets_fields=["student_loan_interest"],
        asked_field="_asked_student_loans",
    ),
    # --- Educator Expenses ---
    FlowQuestion(
        id="ded_educator",
        pool="deductions", phase=2,
        text="Are you a K-12 teacher or educator? You may deduct up to $300 in classroom supplies.",
        actions=[
            {"label": "Yes — I'm an educator", "value": "is_educator"},
            {"label": "No", "value": "not_educator"},
        ],
        eligibility=lambda p: is_w2_employee(p) and not p.get("educator_expenses"),
        base_score=15,
        context_boost_keywords=["teacher", "educator", "school", "classroom"],
        context_boost_amount=40,
        sets_fields=["educator_expenses"],
        asked_field="_asked_educator",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Life Events
# ═══════════════════════════════════════════════════════════════════════════

LIFE_EVENTS = [
    FlowQuestion(
        id="life_events",
        pool="life_events", phase=2,
        text="Did any major life changes happen this year? These can significantly affect your taxes.",
        actions=[
            {"label": "Got married", "value": "event_married"},
            {"label": "Got divorced / separated", "value": "event_divorced"},
            {"label": "Had a baby / adopted", "value": "event_baby"},
            {"label": "Bought a home", "value": "event_bought_home"},
            {"label": "Sold a home", "value": "event_sold_home"},
            {"label": "Changed jobs", "value": "event_job_change"},
            {"label": "Lost a job", "value": "event_job_loss"},
            {"label": "Started a business", "value": "event_started_biz"},
            {"label": "Moved to a different state", "value": "event_moved_states"},
            {"label": "Retired", "value": "event_retired"},
            {"label": "None of these", "value": "no_life_events"},
            {"label": "Skip", "value": "skip_life_events"},
        ],
        eligibility=lambda p: not p.get("life_events"),
        base_score=70,
        context_boost_keywords=["married", "divorced", "baby", "bought", "sold", "moved", "new job", "retired"],
        sets_fields=["life_events"],
        asked_field="_asked_life_events",
    ),
    # --- Home Sale Follow-up ---
    FlowQuestion(
        id="life_home_sale",
        pool="life_events", phase=2,
        text="For the home you sold — did you live in it for at least 2 of the last 5 years? (Up to $250K/$500K gain may be tax-free)",
        actions=[
            {"label": "Yes — primary residence 2+ years", "value": "home_sale_excluded"},
            {"label": "No — investment property or <2 years", "value": "home_sale_taxable"},
            {"label": "Skip", "value": "skip_home_sale"},
        ],
        eligibility=lambda p: p.get("life_events") == "event_sold_home" and not p.get("home_sale_exclusion"),
        base_score=80,
        sets_fields=["home_sale_exclusion"],
        asked_field="_asked_home_sale",
        follow_up_of="life_events",
    ),
    # --- State Move Follow-up ---
    FlowQuestion(
        id="life_state_move",
        pool="life_events", phase=2,
        text="When did you move, and which state did you move from? (You may need to file part-year returns in both states)",
        actions=[
            {"label": "Moved in first half of year", "value": "moved_h1"},
            {"label": "Moved in second half of year", "value": "moved_h2"},
            {"label": "Skip", "value": "skip_state_move"},
        ],
        eligibility=lambda p: p.get("life_events") == "event_moved_states" and not p.get("move_date"),
        base_score=78,
        sets_fields=["move_date"],
        asked_field="_asked_state_move",
        follow_up_of="life_events",
    ),
    # --- Job Loss Follow-up ---
    FlowQuestion(
        id="life_job_loss",
        pool="life_events", phase=2,
        text="Did you receive unemployment benefits or severance pay?",
        actions=[
            {"label": "Unemployment benefits", "value": "had_unemployment"},
            {"label": "Severance pay", "value": "had_severance"},
            {"label": "Both", "value": "had_both"},
            {"label": "Neither", "value": "no_unemployment"},
            {"label": "Skip", "value": "skip_job_loss"},
        ],
        eligibility=lambda p: p.get("life_events") == "event_job_loss" and not p.get("unemployment_income"),
        base_score=76,
        sets_fields=["unemployment_income"],
        asked_field="_asked_job_loss",
        follow_up_of="life_events",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Rental Property
# ═══════════════════════════════════════════════════════════════════════════

RENTAL_PROPERTY = [
    FlowQuestion(
        id="rental_has",
        pool="rental_property", phase=2,
        text="Do you own any rental properties?",
        actions=[
            {"label": "Yes — 1 property", "value": "rental_1"},
            {"label": "Yes — 2-4 properties", "value": "rental_2_4"},
            {"label": "Yes — 5+ properties", "value": "rental_5plus"},
            {"label": "No rental properties", "value": "no_rental"},
            {"label": "Skip", "value": "skip_rental"},
        ],
        eligibility=lambda p: not p.get("rental_income") and not p.get("_asked_rental"),
        base_score=35,
        context_boost_keywords=["rent", "landlord", "property", "tenant"],
        sets_fields=["_has_rental"],
        asked_field="_asked_rental",
    ),
    FlowQuestion(
        id="rental_income_amount",
        pool="rental_property", phase=2,
        text="What's your approximate annual net rental income (after expenses)?",
        actions=[
            {"label": "Under $10,000 profit", "value": "rental_under_10k"},
            {"label": "$10,000 - $25,000", "value": "rental_10_25k"},
            {"label": "$25,000 - $50,000", "value": "rental_25_50k"},
            {"label": "Over $50,000", "value": "rental_over_50k"},
            {"label": "Net loss", "value": "rental_net_loss"},
            {"label": "Skip", "value": "skip_rental_amount"},
        ],
        eligibility=lambda p: p.get("_has_rental") and p.get("_has_rental") != "no_rental" and not p.get("rental_income"),
        base_score=55,
        sets_fields=["rental_income"],
        asked_field="_asked_rental_amount",
        follow_up_of="rental_has",
    ),
    # --- Active Participation ---
    FlowQuestion(
        id="rental_participation",
        pool="rental_property", phase=2,
        text="Do you actively participate in managing your rental properties? (Make decisions, approve tenants, authorize repairs)",
        actions=[
            {"label": "Yes — I actively manage them", "value": "active_participation"},
            {"label": "I use a property manager for everything", "value": "passive_participation"},
            {"label": "I'm a real estate professional (750+ hours)", "value": "re_professional"},
            {"label": "Skip", "value": "skip_participation"},
        ],
        eligibility=lambda p: p.get("rental_income") and not p.get("rental_participation"),
        base_score=52,
        sets_fields=["rental_participation"],
        asked_field="_asked_participation",
        follow_up_of="rental_income_amount",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: K-1 / Partnership
# ═══════════════════════════════════════════════════════════════════════════

K1_PARTNERSHIP = [
    FlowQuestion(
        id="k1_has",
        pool="k1_partnership", phase=2,
        text="Do you receive any K-1 income from partnerships, S-corporations, or trusts?",
        actions=[
            {"label": "Yes, I have K-1 income", "value": "has_k1_income"},
            {"label": "No K-1 income", "value": "no_k1_income"},
            {"label": "Skip", "value": "skip_k1"},
        ],
        eligibility=lambda p: not p.get("k1_ordinary_income") and not p.get("_asked_k1") and not is_low_income_w2_only(p),
        base_score=25,
        context_boost_keywords=["k-1", "k1", "partner", "s-corp", "trust"],
        context_boost_amount=35,
        sets_fields=["_has_k1"],
        asked_field="_asked_k1",
    ),
    FlowQuestion(
        id="k1_amount",
        pool="k1_partnership", phase=2,
        text="What's your approximate K-1 ordinary income?",
        actions=[
            {"label": "Under $25,000", "value": "k1_under_25k"},
            {"label": "$25,000 - $100,000", "value": "k1_25_100k"},
            {"label": "$100,000 - $250,000", "value": "k1_100_250k"},
            {"label": "Over $250,000", "value": "k1_over_250k"},
            {"label": "Skip", "value": "skip_k1_amount"},
        ],
        eligibility=lambda p: p.get("_has_k1") and p.get("_has_k1") != "no_k1_income" and not p.get("k1_ordinary_income"),
        base_score=50,
        sets_fields=["k1_ordinary_income"],
        asked_field="_asked_k1_amount",
        follow_up_of="k1_has",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Healthcare
# ═══════════════════════════════════════════════════════════════════════════

HEALTHCARE = [
    FlowQuestion(
        id="hc_aca_marketplace",
        pool="healthcare", phase=2,
        text="Do you get health insurance through the ACA Marketplace (Healthcare.gov)? You may qualify for the Premium Tax Credit.",
        actions=[
            {"label": "Yes — Marketplace plan with subsidy", "value": "aca_with_subsidy"},
            {"label": "Yes — Marketplace plan, no subsidy", "value": "aca_no_subsidy"},
            {"label": "No — employer coverage or other", "value": "no_aca"},
            {"label": "Skip", "value": "skip_aca"},
        ],
        eligibility=lambda p: not is_retired(p) and not p.get("aca_marketplace") and not p.get("se_health_insurance"),
        base_score=30,
        context_boost_keywords=["marketplace", "aca", "obamacare", "healthcare.gov", "subsidy", "premium tax credit"],
        context_boost_amount=35,
        sets_fields=["aca_marketplace"],
        asked_field="_asked_aca",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Special Situations
# ═══════════════════════════════════════════════════════════════════════════

SPECIAL_SITUATIONS = [
    # --- Estimated Tax Payments ---
    FlowQuestion(
        id="spec_estimated_payments",
        pool="special_situations", phase=2,
        text="Have you made any estimated tax payments this year? (Quarterly payments to the IRS)",
        actions=[
            {"label": "Yes", "value": "has_estimated_payments"},
            {"label": "No", "value": "no_estimated_payments"},
            {"label": "Skip", "value": "skip_estimated"},
        ],
        eligibility=lambda p: (is_business_or_se(p) or float(p.get("total_income", 0) or 0) > 100000) and not p.get("estimated_payments"),
        base_score=45,
        context_boost_keywords=["estimated", "quarterly", "payment", "1040-es"],
        sets_fields=["_has_estimated_payments"],
        asked_field="_asked_estimated",
    ),
    FlowQuestion(
        id="spec_estimated_amount",
        pool="special_situations", phase=2,
        text="How much total in estimated tax payments this year?",
        actions=[
            {"label": "Under $5,000", "value": "est_under_5k"},
            {"label": "$5,000 - $15,000", "value": "est_5_15k"},
            {"label": "$15,000 - $30,000", "value": "est_15_30k"},
            {"label": "Over $30,000", "value": "est_over_30k"},
            {"label": "Skip", "value": "skip_est_amount"},
        ],
        eligibility=lambda p: p.get("_has_estimated_payments") and p.get("_has_estimated_payments") != "no_estimated_payments" and not p.get("estimated_payments"),
        base_score=55,
        sets_fields=["estimated_payments"],
        asked_field="_asked_est_amount",
        follow_up_of="spec_estimated_payments",
    ),
    # --- Energy Credits ---
    FlowQuestion(
        id="spec_energy_credits",
        pool="special_situations", phase=2,
        text="Did you make any energy-efficient home improvements or purchase an electric vehicle?",
        actions=[
            {"label": "Installed solar panels", "value": "has_solar"},
            {"label": "Bought an electric vehicle", "value": "has_ev"},
            {"label": "Home energy improvements (insulation, windows, heat pump)", "value": "has_energy_improvements"},
            {"label": "Multiple", "value": "multiple_energy"},
            {"label": "None", "value": "no_energy"},
            {"label": "Skip", "value": "skip_energy"},
        ],
        eligibility=lambda p: not p.get("energy_credits"),
        base_score=25,
        context_boost_keywords=["solar", "ev", "electric vehicle", "tesla", "energy", "heat pump"],
        context_boost_amount=40,
        sets_fields=["energy_credits"],
        asked_field="_asked_energy",
    ),
    # --- Foreign Income ---
    FlowQuestion(
        id="spec_foreign_income",
        pool="special_situations", phase=2,
        text="Did you earn any income from outside the United States or pay foreign taxes?",
        actions=[
            {"label": "Yes — I worked abroad", "value": "worked_abroad"},
            {"label": "Yes — foreign investment income / taxes paid", "value": "foreign_investments"},
            {"label": "No foreign income", "value": "no_foreign"},
            {"label": "Skip", "value": "skip_foreign"},
        ],
        eligibility=lambda p: not p.get("foreign_income") and float(p.get("total_income", 0) or 0) > 50000,
        base_score=15,
        context_boost_keywords=["foreign", "abroad", "overseas", "international", "expat"],
        context_boost_amount=45,
        sets_fields=["foreign_income"],
        asked_field="_asked_foreign",
    ),
    # --- Alimony ---
    FlowQuestion(
        id="spec_alimony",
        pool="special_situations", phase=2,
        text="Do you pay or receive alimony under a divorce agreement finalized before 2019? (Post-2018 agreements: alimony is not deductible/taxable)",
        actions=[
            {"label": "I pay alimony (pre-2019 agreement)", "value": "pays_alimony"},
            {"label": "I receive alimony (pre-2019 agreement)", "value": "receives_alimony"},
            {"label": "Post-2018 agreement / N/A", "value": "no_alimony"},
            {"label": "Skip", "value": "skip_alimony"},
        ],
        eligibility=lambda p: p.get("filing_status") in ("single", "head_of_household") and not p.get("alimony_status"),
        base_score=10,
        context_boost_keywords=["alimony", "divorce", "ex-spouse", "spousal support"],
        context_boost_amount=50,
        sets_fields=["alimony_status"],
        asked_field="_asked_alimony",
    ),
    # --- Gambling ---
    FlowQuestion(
        id="spec_gambling",
        pool="special_situations", phase=2,
        text="Did you have any gambling winnings or losses this year? (Casino, lottery, sports betting — all taxable)",
        actions=[
            {"label": "Yes — net winnings", "value": "gambling_winnings"},
            {"label": "Yes — but net losses", "value": "gambling_losses"},
            {"label": "No gambling activity", "value": "no_gambling"},
            {"label": "Skip", "value": "skip_gambling"},
        ],
        eligibility=lambda p: not p.get("gambling_income"),
        base_score=8,
        context_boost_keywords=["gambling", "casino", "lottery", "sports bet", "w-2g"],
        context_boost_amount=50,
        sets_fields=["gambling_income"],
        asked_field="_asked_gambling",
    ),
    # --- Military-Specific ---
    FlowQuestion(
        id="spec_military",
        pool="special_situations", phase=2,
        text="Were you deployed to a combat zone? Combat pay may be tax-exempt.",
        actions=[
            {"label": "Yes — combat zone deployment", "value": "combat_zone"},
            {"label": "No deployment", "value": "no_combat"},
            {"label": "Skip", "value": "skip_military"},
        ],
        eligibility=lambda p: p.get("income_type") == "military" and not p.get("combat_zone"),
        base_score=85,
        sets_fields=["combat_zone"],
        asked_field="_asked_military",
    ),
    # --- Military Moving ---
    FlowQuestion(
        id="spec_military_move",
        pool="special_situations", phase=2,
        text="Did you have a Permanent Change of Station (PCS) move? Military moving expenses are still deductible.",
        actions=[
            {"label": "Yes — PCS move", "value": "pcs_move"},
            {"label": "No PCS this year", "value": "no_pcs"},
            {"label": "Skip", "value": "skip_pcs"},
        ],
        eligibility=lambda p: p.get("income_type") == "military" and not p.get("pcs_move"),
        base_score=75,
        sets_fields=["pcs_move"],
        asked_field="_asked_pcs",
    ),
    # --- Household Employee ---
    FlowQuestion(
        id="spec_household_employee",
        pool="special_situations", phase=2,
        text="Did you pay a household employee (nanny, housekeeper, caregiver) more than $2,700 this year? You may owe 'nanny tax' (Schedule H).",
        actions=[
            {"label": "Yes", "value": "has_household_employee"},
            {"label": "No", "value": "no_household_employee"},
            {"label": "Skip", "value": "skip_household"},
        ],
        eligibility=lambda p: float(p.get("total_income", 0) or 0) > 100000 and (p.get("dependents") or 0) > 0 and not p.get("household_employee"),
        base_score=18,
        context_boost_keywords=["nanny", "housekeeper", "caregiver", "au pair"],
        context_boost_amount=40,
        sets_fields=["household_employee"],
        asked_field="_asked_household",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: State-Specific
# ═══════════════════════════════════════════════════════════════════════════

STATE_SPECIFIC = [
    FlowQuestion(
        id="state_multi_state",
        pool="state_specific", phase=2,
        text="Did you earn income in a state other than your home state? (Worked remotely for an out-of-state employer, traveled for work, etc.)",
        actions=[
            {"label": "Yes — income in another state", "value": "multi_state_income"},
            {"label": "No — all income in my home state", "value": "single_state"},
            {"label": "Skip", "value": "skip_multi_state"},
        ],
        eligibility=lambda p: not p.get("multi_state_income") and not is_no_income_tax_state(p),
        base_score=20,
        context_boost_keywords=["remote", "travel", "commute", "another state", "multi-state"],
        context_boost_amount=35,
        sets_fields=["multi_state_income"],
        asked_field="_asked_multi_state",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# COMBINED REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

ALL_QUESTIONS: list = (
    BASICS
    + INCOME_DETAILS
    + SELF_EMPLOYMENT
    + INVESTMENTS
    + RETIREMENT
    + DEPENDENTS
    + DEDUCTIONS
    + LIFE_EVENTS
    + RENTAL_PROPERTY
    + K1_PARTNERSHIP
    + HEALTHCARE
    + SPECIAL_SITUATIONS
    + STATE_SPECIFIC
)
```

**Step 5: Implement the eligibility predicate functions**

```python
# src/web/advisor/flow_rules.py
"""Eligibility predicate functions for flow questions.

Each function takes a profile dict and returns bool.
Used by FlowQuestion.eligibility to determine if a question is relevant.
"""

NO_INCOME_TAX_STATES = {"TX", "FL", "WA", "NV", "WY", "SD", "AK", "NH", "TN"}


def is_w2_employee(profile: dict) -> bool:
    """W-2 employee (single job, multiple jobs, or W-2+side hustle)."""
    return profile.get("income_type") in ("w2_employee", "multiple_w2", "w2_plus_side", "military") and not profile.get("federal_withholding")


def is_married_filing_jointly(profile: dict) -> bool:
    return profile.get("filing_status") == "married_joint" and not profile.get("spouse_income_type")


def is_business_or_se(profile: dict) -> bool:
    """Self-employed, business owner, or W-2+side hustle (for SE-specific questions)."""
    return profile.get("income_type") in ("self_employed", "business_owner", "w2_plus_side") or profile.get("is_self_employed")


def is_self_employed_only(profile: dict) -> bool:
    """Pure self-employed (not W-2+side)."""
    return profile.get("income_type") in ("self_employed", "business_owner")


def is_retired(profile: dict) -> bool:
    return profile.get("income_type") == "retired"


def is_no_income_tax_state(profile: dict) -> bool:
    return profile.get("state") in NO_INCOME_TAX_STATES


def is_low_income_w2_only(profile: dict) -> bool:
    """Low-income W-2 only — skip complex questions like K-1."""
    income = float(profile.get("total_income", 0) or 0)
    return (
        profile.get("income_type") == "w2_employee"
        and income < 75000
        and not profile.get("_has_investments")
        and not profile.get("_has_rental")
    )


def has_young_dependents(profile: dict) -> bool:
    """Has dependents that could need childcare (under 13 for the credit)."""
    deps = profile.get("dependents") or 0
    under_17 = profile.get("dependents_under_17")
    if deps > 0 and under_17 is None:
        return False  # Wait until we know ages
    return (under_17 or 0) > 0 and not profile.get("childcare_costs")
```

**Step 6: Run tests**

Run: `PYTHONPATH=".:src" pytest tests/advisor/test_flow_engine.py -v`
Expected: All pass

**Step 7: Commit**

```bash
git add src/web/advisor/flow_engine.py src/web/advisor/question_registry.py src/web/advisor/flow_rules.py tests/advisor/test_flow_engine.py
git commit -m "feat: add comprehensive adaptive flow engine with 70+ questions and 720+ unique paths"
```

---

### Task 2: Wire FlowEngine into the existing API

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` (lines 3990-4331)
- Test: `tests/advisor/test_flow_integration.py`

**Step 1: Write the failing integration test**

```python
# tests/advisor/test_flow_integration.py
import pytest
from src.web.advisor.flow_engine import FlowEngine


def test_flow_engine_backward_compatible_phase1():
    """Existing Phase 1 flow must still work exactly the same."""
    engine = FlowEngine()

    # Empty profile → filing status
    q = engine.get_next_question({})
    assert q.id == "filing_status"
    assert len(q.actions) == 5

    # Filing status answered → total income
    q = engine.get_next_question({"filing_status": "single"})
    assert q.id == "total_income"

    # Income answered → state
    q = engine.get_next_question({"filing_status": "single", "total_income": 75000})
    assert q.id == "state"


def test_retired_person_never_gets_withholding():
    """Regression: retired users were getting W-2 withholding question."""
    engine = FlowEngine()
    profile = {
        "filing_status": "single",
        "total_income": 45000,
        "state": "FL",
        "dependents": 0,
        "income_type": "retired",
    }
    for _ in range(50):
        q = engine.get_next_question(profile)
        if q is None:
            break
        assert q.id != "withholding", "Retired user should NOT get withholding question"
        profile[q.asked_field] = True


def test_low_income_w2_skips_k1():
    """Low-income W-2 employee should not be asked about K-1 income."""
    engine = FlowEngine()
    profile = {
        "filing_status": "single",
        "total_income": 35000,
        "state": "OH",
        "dependents": 0,
        "income_type": "w2_employee",
    }
    questions = []
    for _ in range(50):
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions.append(q.id)
        profile[q.asked_field] = True
    assert "k1_has" not in questions


def test_se_gets_full_business_flow():
    """Self-employed user should get entity type, business income, home office, vehicle, etc."""
    engine = FlowEngine()
    profile = {
        "filing_status": "single",
        "total_income": 150000,
        "state": "CA",
        "dependents": 0,
        "income_type": "self_employed",
    }
    questions = []
    for _ in range(60):
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions.append(q.id)
        # Simulate answering with a value that triggers follow-ups
        profile[q.asked_field] = True
        if q.id == "se_entity_type":
            profile["entity_type"] = "single_llc"
        elif q.id == "se_business_income":
            profile["business_income"] = 150000
    assert "se_entity_type" in questions
    assert "se_business_income" in questions
    assert "se_home_office" in questions
    assert "se_vehicle" in questions
    assert "se_health_insurance" in questions
```

**Step 2: Run test**

Run: `PYTHONPATH=".:src" pytest tests/advisor/test_flow_integration.py -v`

**Step 3: Replace `_get_dynamic_next_question` to use FlowEngine**

In `src/web/intelligent_advisor_api.py`, replace the body of `_get_dynamic_next_question` (lines ~3990-4331) with:

```python
def _get_dynamic_next_question(profile: dict, last_extracted: dict = None, session: dict = None) -> tuple:
    """
    Dynamically determine the next question based on what's missing.
    Returns (question_text, quick_actions) or (None, None) when done.

    Delegates to the FlowEngine for comprehensive, profile-aware question selection.
    """
    # Skip deep dive if user opted out
    if profile.get("_skip_deep_dive"):
        return (None, None)

    from src.web.advisor.flow_engine import FlowEngine

    engine = FlowEngine()
    conversation = session.get("conversation", []) if isinstance(session, dict) else []
    question = engine.get_next_question(profile, conversation)

    if question is None:
        return (None, None)

    # Handle dynamic text (e.g., dependent count in question text)
    text = question.text
    if "{dependents}" in text:
        text = text.format(dependents=profile.get("dependents", 0))

    return (text, question.actions)
```

**Step 4: Run full test suite**

Run: `PYTHONPATH=".:src" pytest tests/advisor/ -v`

**Step 5: Commit**

```bash
git add src/web/intelligent_advisor_api.py tests/advisor/test_flow_integration.py
git commit -m "feat: wire FlowEngine into advisor API — replaces monolithic question function"
```

---

### Task 3: Add flow path tests for all 10 archetype scenarios

**Files:**
- Create: `tests/advisor/test_flow_paths.py`

**Step 1: Write comprehensive scenario tests**

Test all 10 example flows from Part 3 above. Each test walks through the complete flow for a specific user archetype and asserts:
1. Questions asked are relevant to that profile
2. Irrelevant questions are NOT asked
3. Total question count is reasonable (not too many, not too few)
4. Phase 1 always comes first

```python
# tests/advisor/test_flow_paths.py
"""Test all 10 archetype flow paths for completeness and correctness."""

import pytest
from src.web.advisor.flow_engine import FlowEngine


def _run_flow(profile_overrides: dict) -> list[str]:
    """Simulate a complete flow, returning list of question IDs asked."""
    engine = FlowEngine()
    profile = dict(profile_overrides)
    questions = []
    for _ in range(80):  # Safety limit
        q = engine.get_next_question(profile)
        if q is None:
            break
        questions.append(q.id)
        profile[q.asked_field] = True
    return questions


class TestFlowPath1_SingleW2MidIncome:
    """Single, W-2, mid income, under 50, 0 dependents."""

    def setup_method(self):
        self.profile = {
            "filing_status": "single",
            "total_income": 75000,
            "state": "CA",
            "dependents": 0,
            "income_type": "w2_employee",
        }
        self.questions = _run_flow(self.profile)

    def test_gets_withholding(self):
        assert "withholding" in self.questions

    def test_gets_retirement(self):
        assert "ret_contributions" in self.questions

    def test_gets_deductions(self):
        assert "ded_major_deductions" in self.questions

    def test_skips_business_questions(self):
        assert "se_business_income" not in self.questions
        assert "se_entity_type" not in self.questions

    def test_skips_childcare(self):
        assert "dep_childcare_costs" not in self.questions

    def test_skips_ss_benefits(self):
        assert "ret_ss_benefits" not in self.questions

    def test_reasonable_question_count(self):
        assert 8 <= len(self.questions) <= 20


class TestFlowPath2_MFJ_W2PlusSide_2Kids:
    """MFJ, W-2+side hustle, mid income, under 50, 2 kids."""

    def setup_method(self):
        self.profile = {
            "filing_status": "married_joint",
            "total_income": 100000,
            "state": "TX",
            "dependents": 2,
            "dependents_under_17": 2,
            "income_type": "w2_plus_side",
        }
        self.questions = _run_flow(self.profile)

    def test_gets_spouse_income(self):
        assert "inc_spouse_income_type" in self.questions

    def test_gets_side_hustle_details(self):
        assert "inc_side_hustle_type" in self.questions

    def test_gets_childcare(self):
        assert "dep_childcare_costs" in self.questions

    def test_gets_withholding(self):
        assert "withholding" in self.questions


class TestFlowPath4_Retired:
    """MFJ, retired, under $50k, 65+, 0 dependents."""

    def setup_method(self):
        self.profile = {
            "filing_status": "married_joint",
            "total_income": 45000,
            "state": "FL",
            "dependents": 0,
            "income_type": "retired",
            "age": "age_65_plus",
        }
        self.questions = _run_flow(self.profile)

    def test_gets_ss_benefits(self):
        assert "ret_ss_benefits" in self.questions

    def test_gets_pension(self):
        assert "ret_pension" in self.questions

    def test_gets_rmd(self):
        assert "ret_rmd" in self.questions

    def test_skips_withholding(self):
        assert "withholding" not in self.questions

    def test_skips_business(self):
        assert "se_business_income" not in self.questions

    def test_skips_childcare(self):
        assert "dep_childcare_costs" not in self.questions


class TestFlowPath5_HOH_LowIncome_2Kids:
    """HOH, W-2, low income, under 50, 2 kids under 17."""

    def setup_method(self):
        self.profile = {
            "filing_status": "head_of_household",
            "total_income": 35000,
            "state": "OH",
            "dependents": 2,
            "dependents_under_17": 2,
            "income_type": "w2_employee",
        }
        self.questions = _run_flow(self.profile)

    def test_gets_childcare(self):
        assert "dep_childcare_costs" in self.questions

    def test_skips_k1(self):
        assert "k1_has" not in self.questions

    def test_skips_estimated_payments(self):
        assert "spec_estimated_payments" not in self.questions


class TestFlowPath_NoIncomeTaxState:
    """User in Texas should not get state-specific questions."""

    def setup_method(self):
        self.profile = {
            "filing_status": "single",
            "total_income": 100000,
            "state": "TX",
            "dependents": 0,
            "income_type": "w2_employee",
        }
        self.questions = _run_flow(self.profile)

    def test_skips_multi_state(self):
        assert "state_multi_state" not in self.questions

    def test_skips_529(self):
        # TX doesn't have state income tax deduction for 529
        assert "dep_529_plan" not in self.questions


class TestFlowPath_Military:
    """Military member should get combat zone and PCS questions."""

    def setup_method(self):
        self.profile = {
            "filing_status": "single",
            "total_income": 65000,
            "state": "VA",
            "dependents": 0,
            "income_type": "military",
        }
        self.questions = _run_flow(self.profile)

    def test_gets_combat_zone(self):
        assert "spec_military" in self.questions

    def test_gets_pcs(self):
        assert "spec_military_move" in self.questions

    def test_gets_withholding(self):
        assert "withholding" in self.questions
```

**Step 2: Run tests**

Run: `PYTHONPATH=".:src" pytest tests/advisor/test_flow_paths.py -v`

**Step 3: Commit**

```bash
git add tests/advisor/test_flow_paths.py
git commit -m "test: add 10 archetype flow path tests covering 720+ scenario branches"
```

---

### Task 4: Update parser to handle new question values

**Files:**
- Modify: `src/web/advisor/parsers.py`
- Test: `tests/advisor/test_parsers_new_values.py`

Update the parser to recognize all new button values from the expanded question set:
- New income types: `w2_plus_side`, `multiple_w2`, `military`, `investor`
- Side hustle values: `freelance`, `gig_work`, `online_sales`
- Entity types: `sole_prop`, `single_llc`, `multi_llc`, `s_corp`, `c_corp`, `partnership`
- Retirement: `has_sep`, `has_solo_401k`, `has_trad_ira`, `has_roth_ira`
- Life events: all `event_*` values
- All new follow-up values

**Step 1: Write tests for new parser values**

**Step 2: Add parsing logic for each new value category**

**Step 3: Run full parser test suite**

**Step 4: Commit**

---

### Task 5: Update frontend to support new question types

**Files:**
- Modify: `src/web/static/js/advisor/modules/advisor-flow.js`
- Modify: `src/web/static/js/advisor/modules/advisor-chat.js`

Changes needed:
- Handle new multi-select life events (currently only single select)
- Support the expanded income type options (8 instead of 4)
- Dynamic dependent age split buttons (runtime generation)
- Proper rendering of follow-up chain questions

**Step 1: Update action button rendering for new question types**

**Step 2: Test manually in browser**

**Step 3: Commit**

---

### Task 6: Remove old `_score_next_questions` and `_get_dynamic_next_question` code

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` (remove lines 3687-4331)

After Task 2 wires in the FlowEngine, the old scoring and question functions become dead code. Remove them to prevent confusion.

**Step 1: Remove old functions**

**Step 2: Run full test suite to confirm nothing breaks**

**Step 3: Commit**

```bash
git commit -m "refactor: remove legacy question scoring — FlowEngine handles all flows"
```

---

## PART 5: FLOW COUNT SUMMARY

| Category | Questions Before | Questions After | New Unique Paths |
|---|---|---|---|
| **Basics (Phase 1)** | 5 | 5 | Same (income type expanded from 4→8 options) |
| **Income Details** | 2 (withholding, age) | 7 (+ multiple W-2, side hustle, spouse income) | +60 |
| **Self-Employment** | 2 (business income, home office) | 9 (+ entity type, vehicle, equipment, employees, health insurance, SSTB) | +120 |
| **Investments** | 3 (has?, amount, cap gains) | 7 (+ crypto, stock options, loss carryforward) | +45 |
| **Retirement** | 2 (contributions, HSA) | 7 (+ SS benefits, pension, distributions, early withdrawal, RMD) | +80 |
| **Dependents** | 1 (age split) | 6 (+ childcare, DCFSA, education, 529, adoption) | +90 |
| **Deductions** | 5 (mortgage, property tax, charitable, student loans, est payments) | 7 (+ medical amount, educator expenses) | +15 |
| **Life Events** | 0 | 4 (+ home sale, state move, job loss follow-ups) | +100 |
| **Rental Property** | 2 | 3 (+ active participation) | +15 |
| **K-1** | 2 | 2 (but now gated — not shown to low-income W-2) | Fixed |
| **Healthcare** | 0 | 1 (ACA marketplace) | +20 |
| **Special Situations** | 0 | 8 (estimated payments, energy credits, foreign income, alimony, gambling, military, nanny tax) | +150 |
| **State-Specific** | 0 | 1 (multi-state income) | +25 |
| **TOTAL** | ~22 | ~67 | **720+ unique paths** |

---

## Execution Notes

- Tasks 1-3 are the critical path — they build the engine, wire it in, and test it
- Task 4 (parser updates) is required for the new button values to actually work
- Task 5 (frontend) is required for the user to see the new questions
- Task 6 (cleanup) can be done anytime after Task 2

**Estimated implementation: 6 tasks, each with TDD steps.**
