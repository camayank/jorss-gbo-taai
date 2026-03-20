# All Use Case Scenarios -- US Tax Advisory Chatbot

**Date:** 2026-03-20
**Status:** Reference Document
**Purpose:** Exhaustive catalog of every realistic user scenario with expected question flows, skip logic, and validation rules.
**Total Use Cases:** 250

---

## Table of Contents

1. [Question Flow Reference](#question-flow-reference)
2. [Elimination Rules for Impossible Combinations](#elimination-rules)
3. [GROUP 1: Simple W-2 Employees](#group-1-simple-w-2-employees) (UC-001 through UC-060)
4. [GROUP 2: W-2 + Side Hustle](#group-2-w-2--side-hustle) (UC-061 through UC-085)
5. [GROUP 3: Self-Employed / LLC](#group-3-self-employed--llc) (UC-086 through UC-110)
6. [GROUP 4: S-Corp / C-Corp / Partnership Owners](#group-4-s-corp--c-corp--partnership-owners) (UC-111 through UC-135)
7. [GROUP 5: Retired Individuals](#group-5-retired-individuals) (UC-136 through UC-160)
8. [GROUP 6: Investors (Primary Income)](#group-6-investors-primary-income) (UC-161 through UC-180)
9. [GROUP 7: Military](#group-7-military) (UC-181 through UC-195)
10. [GROUP 8: Life Event Scenarios](#group-8-life-event-scenarios) (UC-196 through UC-225)
11. [GROUP 9: Complex Multi-Situation Scenarios](#group-9-complex-multi-situation-scenarios) (UC-226 through UC-240)
12. [GROUP 10: Edge Cases and Unusual Combinations](#group-10-edge-cases-and-unusual-combinations) (UC-241 through UC-250)

---

## Question Flow Reference

### Phase 1 Questions (Core Profile -- Always Asked)

| # | Question ID | Question | Type | Always Asked? |
|---|-------------|----------|------|---------------|
| P1-1 | `filing_status` | What is your filing status? | select | YES |
| P1-2 | `state_of_residence` | What state do you live in? | select | YES |
| P1-3 | `gross_income` | What is your approximate total income? | currency | YES |
| P1-4 | `has_dependents` | Do you have any dependents? | boolean | YES |
| P1-5 | `num_dependents` | How many dependents? | number | If P1-4 = yes |
| P1-6 | `dependent_details` | Ages and relationship of dependents | composite | If P1-4 = yes |
| P1-7 | `primary_income_type` | What is your primary source of income? | select | YES |

### Phase 2 Questions (Adaptive -- Conditional)

| # | Question ID | Trigger Condition | Category |
|---|-------------|-------------------|----------|
| P2-1 | `age` | Always | Demographics |
| P2-2 | `multiple_w2s` | income_type = W-2 | Income |
| P2-3 | `w2_withholding` | income_type = W-2 | Income |
| P2-4 | `has_self_employment` | NOT already known from income_type | Income |
| P2-5 | `self_employment_income` | has_self_employment = yes | Income |
| P2-6 | `business_type` | has_self_employment = yes | Income |
| P2-7 | `has_business_expenses` | has_self_employment = yes | Deductions |
| P2-8 | `business_expense_amount` | has_business_expenses = yes | Deductions |
| P2-9 | `home_office` | has_self_employment = yes | Deductions |
| P2-10 | `has_rental_income` | Always (probe) | Income |
| P2-11 | `rental_income_amount` | has_rental = yes | Income |
| P2-12 | `rental_expenses` | has_rental = yes | Deductions |
| P2-13 | `has_investments` | Always (probe) | Income |
| P2-14 | `investment_types` | has_investments = yes | Income |
| P2-15 | `has_stock_sales` | has_investments = yes | Income |
| P2-16 | `has_crypto` | Always (probe) | Income |
| P2-17 | `has_k1_income` | income_type = business/partnership | Income |
| P2-18 | `k1_entity_type` | has_k1 = yes | Income |
| P2-19 | `has_foreign_income` | Always (probe) | Income |
| P2-20 | `foreign_income_details` | has_foreign = yes | Income |
| P2-21 | `has_education_expenses` | age < 30 OR has_dependents with students | Credits |
| P2-22 | `education_amount` | has_education = yes | Credits |
| P2-23 | `has_student_loans` | age < 50 (probe) | Deductions |
| P2-24 | `student_loan_interest` | has_student_loans = yes | Deductions |
| P2-25 | `has_retirement_contributions` | Always | Deductions |
| P2-26 | `retirement_type_amount` | has_retirement = yes | Deductions |
| P2-27 | `has_hsa` | Always (probe) | Deductions |
| P2-28 | `hsa_amount` | has_hsa = yes | Deductions |
| P2-29 | `has_mortgage` | income > $40k (probe) | Deductions |
| P2-30 | `mortgage_interest` | has_mortgage = yes | Deductions |
| P2-31 | `property_taxes` | has_mortgage = yes OR homeowner | Deductions |
| P2-32 | `charitable_donations` | income > $30k (probe) | Deductions |
| P2-33 | `donation_amount` | charitable = yes | Deductions |
| P2-34 | `has_childcare_expenses` | has_dependents with young children | Credits |
| P2-35 | `childcare_amount` | has_childcare = yes | Credits |
| P2-36 | `has_energy_improvements` | homeowner (probe) | Credits |
| P2-37 | `energy_type_amount` | has_energy = yes | Credits |
| P2-38 | `has_aca_marketplace` | Always (probe) | Compliance |
| P2-39 | `aca_details` | has_aca = yes | Compliance |
| P2-40 | `life_events` | Always | Life Events |
| P2-41 | `life_event_details` | life_events != none | Life Events |
| P2-42 | `estimated_tax_payments` | self-employed OR high income | Compliance |
| P2-43 | `has_gambling_income` | Complex returns only (probe) | Income |
| P2-44 | `has_alimony` | Divorced or complex (probe) | Income/Deductions |
| P2-45 | `has_household_employee` | High income (probe) | Compliance |
| P2-46 | `military_status` | income_type = military | Special |
| P2-47 | `combat_zone` | military_status = active | Special |
| P2-48 | `has_stock_options` | W-2 + high income OR tech worker | Income |
| P2-49 | `stock_option_type` | has_stock_options = yes | Income |
| P2-50 | `social_security_income` | age >= 62 | Income |
| P2-51 | `pension_income` | age >= 55 OR retired | Income |
| P2-52 | `rmd_taken` | age >= 73 | Compliance |
| P2-53 | `inherited_assets` | life_event = inheritance | Income |
| P2-54 | `disability_income` | life_event = disability | Income |

---

## Elimination Rules

### Impossible Combinations (MUST filter out)

| Rule | Reason |
|------|--------|
| QSS + No Dependents | QSS requires qualifying dependent child |
| QSS + Age < 30 | Statistically near-impossible; spouse must have died within last 2 years |
| HOH + No Dependents | HOH requires qualifying person maintained in home |
| MFS + EITC claimed | MFS filers are ineligible for EITC |
| Retired (pension/SS) + Age Under 26 | Cannot be retired at that age (normal track) |
| Military Active + Retired income type | Use "Retired" or "Military" -- not both |
| C-Corp Owner + Very Low Income (<$25k) | C-Corp owners typically have salary + distributions |
| Very Low Income + Has household employee | Economically contradictory |
| Under 26 + Pension income | Cannot draw pension that young (normal cases) |
| Under 26 + RMD questions | RMDs start at 73 |
| Single + Alimony paid (pre-2019 divorce) | Possible but extremely rare for under-26 |

### Filing Status Constraints

| Filing Status | Requires |
|---------------|----------|
| Single | Unmarried, no qualifying dependent for HOH |
| MFJ | Legally married, both spouses agree |
| MFS | Legally married, filing separately |
| HOH | Unmarried (or considered unmarried) + qualifying person + pays >50% household costs |
| QSS | Spouse died within last 2 tax years + dependent child + not remarried |

---

## GROUP 1: Simple W-2 Employees

**Scope:** Pure W-2 wage earners. Single job unless noted. No business income.

### Group 1 Rules

**Critical validation rules (MUST ask):**
- Filing status
- State of residence
- Total income / W-2 wages
- Dependents (yes/no + details if yes)
- Withholding adequacy
- Age bracket
- Life events

**Mutual exclusion rules (NEVER ask):**
- Business expenses / Schedule C questions
- K-1 / partnership / S-Corp questions
- Self-employment tax questions
- Estimated quarterly payments (unless also has investment income)
- QBI deduction questions
- Business entity type
- Home office deduction (unless also has side hustle)
- Depreciation / Section 179

**Follow-up chains:**
- IF has_dependents = yes AND child < 13 THEN ask childcare_expenses
- IF has_dependents = yes AND child < 17 THEN calculate CTC eligibility
- IF has_dependents = yes AND child 17-24 + student THEN ask education_expenses
- IF income < EITC threshold THEN ask EITC qualifying questions
- IF age < 26 THEN likely ask education, student loans; skip retirement planning
- IF age >= 50 THEN ask catch-up contributions; skip student loan likelihood
- IF age >= 65 THEN ask Social Security, Medicare, additional standard deduction

---

#### UC-001: Single, W-2, Very Low Income (<$25k), Under 26, No Dependents
**Profile:** Entry-level worker, likely first job, part-time, or recent grad.
**Phase 1:** Filing Status(Single) -> Income(<$25k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding (likely over-withheld, refund expected)
- Age (Under 26)
- Education expenses (likely student or recent grad)
- Student loan interest
- Health insurance / ACA marketplace (may be on parent's plan)
- Life events (none expected)
**Questions SKIPPED:** Business, K-1, rental, investments, childcare, estimated payments, HSA, energy credits, foreign income, military, mortgage, property taxes, charitable (below standard deduction), retirement contributions (unlikely), stock options, gambling, alimony, household employee
**Expected Count:** 8-12 questions total

#### UC-002: Single, W-2, Very Low Income (<$25k), Under 26, 1 Young Child (<13)
**Profile:** Young single parent, low-wage job, needs maximum credits.
**Phase 1:** Filing Status(HOH -- should be prompted to consider HOH) -> Income(<$25k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age (Under 26)
- Childcare expenses (critical for CDCTC)
- EITC qualifying questions (high priority -- max benefit)
- Child Tax Credit eligibility
- Education expenses (for self, if student)
- Student loans
- ACA marketplace (Form 1095-A)
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage, energy credits, foreign income, military, stock options, retirement (unlikely at this income/age), HSA, charitable, gambling, alimony, household employee
**Expected Count:** 10-14 questions total

#### UC-003: Single, W-2, Very Low Income (<$25k), 26-49, No Dependents
**Profile:** Low-wage worker, possibly hourly. Standard simple return.
**Phase 1:** Filing Status(Single) -> Income(<$25k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- EITC eligibility check (income within range, no investment income)
- Student loan interest (if under 40)
- Retirement contributions (Saver's Credit eligible at this income)
- Health insurance / ACA
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, childcare, mortgage, energy credits, foreign income, military, stock options, education (unless student), charitable, gambling, alimony, household employee, HSA (unlikely)
**Expected Count:** 8-11 questions total

#### UC-004: Single, W-2, Very Low Income (<$25k), 26-49, 1 Young Child (<13)
**Profile:** Single parent, low income, needs HOH filing status guidance.
**Phase 1:** Filing Status(HOH) -> Income(<$25k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Childcare expenses
- EITC (1 child -- significant credit)
- Child Tax Credit
- Saver's Credit eligibility
- ACA marketplace
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage, energy credits, foreign income, military, stock options, education (for self), charitable, gambling, alimony, household employee, student loans (probe only)
**Expected Count:** 10-14 questions total

#### UC-005: Single, W-2, Very Low Income (<$25k), 26-49, 2+ Young Children
**Profile:** Single parent with multiple young kids, maximum EITC territory.
**Phase 1:** Filing Status(HOH) -> Income(<$25k) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Childcare expenses (multiple children -- higher limit)
- EITC (2+ children -- maximum credit ~$7,430)
- Child Tax Credit (multiple children)
- Saver's Credit
- ACA marketplace
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage, energy credits, foreign income, military, stock options, education, charitable, gambling, alimony, household employee
**Expected Count:** 10-14 questions total

#### UC-006: Single, W-2, Very Low Income (<$25k), 50-64, No Dependents
**Profile:** Older low-wage worker, possibly approaching retirement.
**Phase 1:** Filing Status(Single) -> Income(<$25k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age (50-64 -- catch-up contribution eligible)
- EITC eligibility
- Retirement contributions (catch-up, Saver's Credit)
- Health insurance / ACA
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, childcare, education, student loans, mortgage (unlikely at this income), energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee, Social Security (not yet 62)
**Expected Count:** 8-11 questions total

#### UC-007: Single, W-2, Very Low Income (<$25k), 65+, No Dependents
**Profile:** Senior still working part-time, likely also receiving Social Security.
**Phase 1:** Filing Status(Single) -> Income(<$25k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age (65+ -- additional standard deduction $1,950)
- Social Security income (critical -- taxability depends on combined income)
- Medicare premiums / IRMAA
- Retirement account distributions (RMD if 73+)
- Health insurance
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, childcare, education, student loans, energy credits, foreign income, military, stock options, charitable (below threshold), gambling, alimony, household employee, EITC (may still qualify -- check)
**Expected Count:** 9-13 questions total

#### UC-008: Single, W-2, Low Income ($25k-$50k), Under 26, No Dependents
**Profile:** Young professional, first real job, may have education expenses.
**Phase 1:** Filing Status(Single) -> Income($25k-$50k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age (Under 26)
- Education expenses (AOTC if in college, LLC)
- Student loan interest (high likelihood)
- Retirement contributions (401k, Roth IRA -- Saver's Credit)
- HSA (if HDHP through employer)
- Health insurance
- Investments (probe -- may have started)
- Life events
**Questions SKIPPED:** Business, K-1, rental, childcare, mortgage (unlikely), energy credits, foreign income, military, stock options, charitable (below threshold), gambling, alimony, household employee
**Expected Count:** 10-14 questions total

#### UC-009: Single, W-2, Low Income ($25k-$50k), Under 26, 1 Young Child (<13)
**Profile:** Young single parent, moderate income, significant credit eligibility.
**Phase 1:** Filing Status(HOH) -> Income($25k-$50k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Childcare expenses (CDCTC)
- EITC (1 child, income in range)
- Child Tax Credit
- Education expenses (for self)
- Student loans
- Retirement contributions
- ACA marketplace
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage, energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee, HSA (unlikely)
**Expected Count:** 11-15 questions total

#### UC-010: Single, W-2, Low Income ($25k-$50k), 26-49, No Dependents
**Profile:** Mid-career worker, moderate income, standard return.
**Phase 1:** Filing Status(Single) -> Income($25k-$50k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Student loan interest (if under 40)
- Retirement contributions (401k, IRA, Saver's Credit check)
- HSA
- Investments (probe)
- Health insurance / ACA
- Charitable donations (probe)
- Life events
**Questions SKIPPED:** Business, K-1, rental, childcare, education (unless student), mortgage (unlikely), energy credits, foreign income, military, stock options, EITC (near/over threshold for 0 children), gambling, alimony, household employee
**Expected Count:** 9-13 questions total

#### UC-011: Single, W-2, Low Income ($25k-$50k), 26-49, 2+ Young Children
**Profile:** Single parent with multiple kids, needs credits maximized.
**Phase 1:** Filing Status(HOH) -> Income($25k-$50k) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Childcare expenses (multiple children)
- EITC (2+ children, income in range -- significant credit)
- Child Tax Credit (multiple)
- Education expenses (for self if applicable)
- Student loans
- Retirement contributions
- ACA marketplace
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage, energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 11-15 questions total

#### UC-012: Single, W-2, Mid Income ($50k-$100k), Under 26, No Dependents
**Profile:** Well-paid young professional, tech/finance, may have stock comp.
**Phase 1:** Filing Status(Single) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Education expenses (if still in grad school or recently graduated)
- Student loan interest
- Retirement contributions (401k -- important at this income)
- HSA
- Investments (likely started investing)
- Stock options / RSU (if tech worker)
- Charitable donations (probe)
- Life events
**Questions SKIPPED:** Business, K-1, rental, childcare, EITC (over threshold), mortgage (possible but less likely under 26), energy credits, foreign income, military, gambling, alimony, household employee
**Expected Count:** 11-15 questions total

#### UC-013: Single, W-2, Mid Income ($50k-$100k), 26-49, No Dependents
**Profile:** Core middle-class worker, possibly homeowner.
**Phase 1:** Filing Status(Single) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Student loan interest (if under 40)
- Retirement contributions (401k, IRA)
- HSA
- Mortgage / homeowner status
- Property taxes (if homeowner)
- Investments (probe)
- Charitable donations
- Life events
**Questions SKIPPED:** Business, K-1, rental (unless homeowner renting part), childcare, EITC, education (unless continuing ed), energy credits (probe if homeowner), foreign income, military, stock options (unless in tech), gambling, alimony, household employee
**Expected Count:** 11-15 questions total

#### UC-014: Single, W-2, Mid Income ($50k-$100k), 26-49, 1 Young Child (<13)
**Profile:** Single parent, comfortable income, childcare costs.
**Phase 1:** Filing Status(HOH) -> Income($50k-$100k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Childcare expenses
- Child Tax Credit (full $2,000 -- under phaseout)
- Retirement contributions
- HSA
- Mortgage / homeowner
- Student loans
- Investments (probe)
- Charitable donations
- Life events
**Questions SKIPPED:** Business, K-1, rental, EITC (likely over threshold), education (unless student), energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-015: Single, W-2, Mid Income ($50k-$100k), 50-64, Elderly/Disabled Relative
**Profile:** Caring for aging parent, may claim as dependent.
**Phase 1:** Filing Status(HOH -- if supporting parent in home) -> Income($50k-$100k) -> State -> Dependents(1, elderly relative) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Dependent's income test (must be under $4,700)
- Credit for Other Dependents ($500)
- Medical expenses for dependent (Schedule A -- possible if high)
- Retirement contributions (catch-up eligible)
- HSA
- Mortgage / homeowner
- Charitable donations
- Life events
**Questions SKIPPED:** Business, K-1, rental, childcare (not under 13), EITC (over threshold), education, student loans, energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-016: Single, W-2, High Income ($100k-$200k), Under 26, No Dependents
**Profile:** High-earning young professional (tech, finance, consulting).
**Phase 1:** Filing Status(Single) -> Income($100k-$200k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Student loan interest (phaseout check -- MAGI $75k-$90k)
- Retirement contributions (401k max out, backdoor Roth strategy)
- HSA
- Investments (high likelihood)
- Stock options / RSU (high likelihood for this demo)
- Mortgage / homeowner
- Charitable donations
- Life events
**Questions SKIPPED:** Business, K-1, rental, childcare, EITC, education credits (phased out above $90k single), NIIT (under $200k), AMT (check if ISO exercises), gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-017: Single, W-2, High Income ($100k-$200k), 26-49, No Dependents
**Profile:** Established professional, significant tax optimization opportunity.
**Phase 1:** Filing Status(Single) -> Income($100k-$200k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Retirement contributions (max 401k, backdoor Roth, mega backdoor)
- HSA
- Mortgage / homeowner (likely)
- Property taxes
- Investments (stocks, bonds, mutual funds)
- Stock options / RSU
- Charitable donations (itemize vs. standard comparison)
- Itemize vs. standard deduction analysis
- Life events
**Questions SKIPPED:** Business, K-1, rental (probe), childcare, EITC, education credits (phased out), student loans (phased out above $90k), NIIT (check if near $200k), gambling, alimony, household employee
**Expected Count:** 13-17 questions total

#### UC-018: Single, W-2, High Income ($100k-$200k), 26-49, 2+ Young Children
**Profile:** High-earning single parent, complex credits.
**Phase 1:** Filing Status(HOH) -> Income($100k-$200k) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Childcare expenses (CDCTC)
- Child Tax Credit (full -- under $200k HOH phaseout)
- Retirement contributions
- HSA
- Mortgage / homeowner (likely)
- Property taxes
- Investments
- Charitable donations
- Itemize vs. standard
- Life events
**Questions SKIPPED:** Business, K-1, rental, EITC (over threshold), education credits (for self -- phased out), student loans (phased out), foreign income, military, gambling, alimony, household employee
**Expected Count:** 14-18 questions total

#### UC-019: Single, W-2, Very High Income ($200k+), 26-49, No Dependents
**Profile:** Top earner, AMT and NIIT territory, needs tax planning.
**Phase 1:** Filing Status(Single) -> Income($200k+) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding (critical -- likely underwithholding risk)
- Age
- Retirement contributions (max out everything -- 401k, backdoor Roth)
- HSA (max out)
- Investments (probe for NIIT -- threshold $200k single)
- Stock options / RSU (AMT check for ISO exercises)
- Mortgage / homeowner
- Property taxes (SALT cap $10k)
- Charitable donations (donor-advised fund strategy)
- Itemize vs. standard
- AMT exposure check
- NIIT applicability
- Estimated payments (if investment income)
- Life events
**Questions SKIPPED:** Business, K-1, rental (probe), childcare, EITC, education credits (phased out), student loans (phased out), Saver's Credit (phased out), ACA (employer coverage), gambling, alimony (unless divorced), household employee (probe at this income)
**Expected Count:** 15-20 questions total

#### UC-020: Single, W-2, Very High Income ($200k+), 50-64, No Dependents
**Profile:** Peak earning years, retirement planning critical.
**Phase 1:** Filing Status(Single) -> Income($200k+) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age (50-64 -- catch-up contributions)
- Retirement contributions (max 401k $30,500 with catch-up, backdoor Roth)
- HSA (catch-up contributions if 55+)
- Investments
- Stock options / RSU
- Mortgage / homeowner
- Property taxes
- Charitable donations (QCD strategy if 70.5+)
- Itemize vs. standard
- AMT exposure
- NIIT
- Estimated payments
- Life events
**Questions SKIPPED:** Business, K-1, rental (probe), childcare, EITC, education, student loans, Saver's Credit, ACA, gambling, alimony (probe if divorced), household employee (probe)
**Expected Count:** 15-20 questions total

#### UC-021: MFJ, W-2 (single job), Very Low Income (<$25k), 26-49, No Dependents
**Profile:** Married couple, one working, low income. EITC territory.
**Phase 1:** Filing Status(MFJ) -> Income(<$25k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age (both spouses)
- Spouse employment status
- EITC eligibility (MFJ thresholds higher)
- Retirement contributions (Saver's Credit)
- ACA marketplace
- Life events (recently married?)
**Questions SKIPPED:** Business, K-1, rental, investments, childcare, education (probe), mortgage, energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 9-13 questions total

#### UC-022: MFJ, W-2 (single job), Very Low Income (<$25k), 26-49, 1 Young Child (<13)
**Profile:** Married couple, one income, young child. Maximum credit optimization.
**Phase 1:** Filing Status(MFJ) -> Income(<$25k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages (both spouses)
- Spouse employment
- Childcare expenses
- EITC (MFJ + 1 child -- up to ~$4,213)
- Child Tax Credit
- Saver's Credit
- ACA marketplace
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage, energy credits, foreign income, military, stock options, education, charitable, gambling, alimony, household employee
**Expected Count:** 11-15 questions total

#### UC-023: MFJ, W-2 (single job), Low Income ($25k-$50k), 26-49, 2+ Young Children
**Profile:** Family with moderate income, multiple kids, strong EITC/CTC.
**Phase 1:** Filing Status(MFJ) -> Income($25k-$50k) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Spouse employment
- Childcare expenses (multiple kids)
- EITC (2+ children, MFJ -- up to ~$7,430)
- Child Tax Credit (multiple)
- Education (for either spouse)
- Student loans
- Retirement contributions
- ACA marketplace
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage (probe), energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-024: MFJ, W-2 (single job), Mid Income ($50k-$100k), 26-49, No Dependents
**Profile:** Dual-income couple or one good earner, no kids.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Spouse income/employment
- Retirement contributions (both spouses)
- HSA
- Student loans
- Mortgage / homeowner (likely)
- Property taxes
- Investments (probe)
- Charitable donations
- Life events
**Questions SKIPPED:** Business, K-1, rental, childcare, EITC (over threshold for 0 children MFJ), education (probe), energy credits (probe if homeowner), foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-025: MFJ, W-2 (single job), Mid Income ($50k-$100k), 26-49, 2+ Young Children
**Profile:** Middle-class family, homeowners, standard American family return.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Spouse income
- Childcare expenses
- Child Tax Credit (2+ children = $4,000+)
- EITC (check -- MFJ threshold higher for 2+ kids ~$62k)
- Education (for either spouse)
- Student loans
- Retirement contributions
- HSA
- Mortgage / homeowner
- Charitable donations
- Life events
**Questions SKIPPED:** Business, K-1, rental, energy credits, foreign income, military, stock options, gambling, alimony, household employee, AMT, NIIT
**Expected Count:** 14-18 questions total

#### UC-026: MFJ, W-2 (single job), Mid Income ($50k-$100k), 50-64, Older Children (13-24 student)
**Profile:** Parents with college-age kids, education credits critical.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(1+, ages 13-24 students) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Spouse income
- Education expenses (AOTC up to $2,500/student -- CRITICAL)
- 529 plan distributions
- Student's income (may file own return)
- Student loan interest (for parents paying)
- Retirement contributions (catch-up)
- HSA
- Mortgage / homeowner
- Charitable donations
- Life events
**Questions SKIPPED:** Business, K-1, rental, childcare (kids over 13), EITC (over threshold), energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 13-17 questions total

#### UC-027: MFJ, W-2 (single job), High Income ($100k-$200k), 26-49, 2+ Young Children
**Profile:** Affluent family, both spouses likely working, complex credits.
**Phase 1:** Filing Status(MFJ) -> Income($100k-$200k) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Spouse income source
- Childcare expenses (Dependent Care FSA?)
- Child Tax Credit
- Retirement contributions (both spouses max 401k)
- HSA
- Mortgage / homeowner
- Property taxes
- Investments
- Education expenses (for kids if applicable)
- Charitable donations
- Itemize vs. standard
- Life events
**Questions SKIPPED:** Business, K-1, rental (probe), EITC (over threshold), student loans (probe -- phaseout $155k-$185k MFJ), energy credits (probe), foreign income, military, gambling, alimony, household employee (probe)
**Expected Count:** 15-19 questions total

#### UC-028: MFJ, W-2 (single job), High Income ($100k-$200k), 50-64, No Dependents
**Profile:** Empty nesters, peak saving years, retirement focus.
**Phase 1:** Filing Status(MFJ) -> Income($100k-$200k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages (catch-up contributions)
- Spouse income
- Retirement contributions (max catch-up both spouses)
- HSA (catch-up if 55+)
- Mortgage / homeowner
- Property taxes
- Investments
- Charitable donations
- Itemize vs. standard
- Life events
**Questions SKIPPED:** Business, K-1, rental (probe), childcare, EITC, education (unless adult learner), student loans (likely paid off or phased out), energy credits (probe), foreign income, military, stock options (probe), gambling, alimony (probe if previously divorced), household employee
**Expected Count:** 13-17 questions total

#### UC-029: MFJ, W-2 (single job), Very High Income ($200k+), 26-49, No Dependents
**Profile:** High-earning couple, complex tax optimization needed.
**Phase 1:** Filing Status(MFJ) -> Income($200k+) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding (underwithholding risk)
- Ages
- Spouse income details
- Retirement contributions (max everything, backdoor Roth)
- HSA
- Investments (NIIT check at $250k MFJ)
- Stock options / RSU
- Mortgage / homeowner
- Property taxes (SALT cap)
- Charitable donations (donor-advised fund)
- Itemize vs. standard
- AMT exposure
- NIIT applicability
- Estimated payments
- Life events
**Questions SKIPPED:** Business, K-1, childcare, EITC, education credits (phased out at $180k MFJ), student loans (phased out), Saver's Credit, ACA (employer coverage), gambling, alimony (probe), household employee (probe)
**Expected Count:** 16-21 questions total

#### UC-030: MFJ, W-2 (single job), Very High Income ($200k+), 26-49, 2+ Young Children
**Profile:** High-earning family, CTC phaseout territory at $400k MFJ.
**Phase 1:** Filing Status(MFJ) -> Income($200k+) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Spouse income
- Childcare expenses (Dependent Care FSA maxed)
- Child Tax Credit (check phaseout -- starts at $400k MFJ)
- Retirement contributions (max)
- HSA
- Investments
- Stock options / RSU
- Mortgage / homeowner
- Property taxes
- Charitable donations
- Itemize vs. standard
- AMT / NIIT
- Estimated payments
- Life events
**Questions SKIPPED:** Business, K-1, EITC, education credits (phased out), student loans (phased out), Saver's Credit, ACA, gambling, alimony, household employee (ask -- may have nanny)
**Expected Count:** 17-22 questions total

#### UC-031: MFS, W-2, Mid Income ($50k-$100k), 26-49, No Dependents
**Profile:** Married filing separately -- divorce pending, spouse has debt, or income-driven repayment.
**Phase 1:** Filing Status(MFS) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Reason for MFS (impacts strategy advice)
- Retirement contributions (IRA deduction different for MFS)
- Student loans (income-driven repayment reason for MFS?)
- Mortgage / homeowner
- Investments
- Charitable donations
- Itemize vs. standard (if spouse itemizes, MUST itemize)
- Life events
**Questions SKIPPED:** Business, K-1, rental, childcare, EITC (MFS CANNOT claim), education credits (MFS limited), Saver's Credit (lower threshold), energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 11-15 questions total
**CRITICAL NOTE:** If spouse itemizes, this filer MUST also itemize.

#### UC-032: MFS, W-2, High Income ($100k-$200k), 26-49, 1 Young Child
**Profile:** High earner filing separately, child custody arrangement.
**Phase 1:** Filing Status(MFS) -> Income($100k-$200k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Reason for MFS
- Who claims child (custody agreement / Form 8332)
- Child Tax Credit (different rules for MFS)
- Retirement contributions
- Mortgage / homeowner
- Investments
- Itemize vs. standard (must match spouse strategy)
- Life events
**Questions SKIPPED:** EITC (ineligible MFS), CDCTC (limited for MFS), education credits (phased out earlier for MFS -- $67.5k), student loans (phased out), Saver's Credit (lower threshold), energy credits, foreign income, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-033: HOH, W-2, Very Low Income (<$25k), 26-49, 1 Young Child (<13)
**Profile:** Unmarried head of household, low income, maximum benefits.
**Phase 1:** Filing Status(HOH) -> Income(<$25k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Confirm qualifying person lives with filer >50% of year
- Childcare expenses
- EITC (HOH + 1 child)
- Child Tax Credit
- Saver's Credit
- ACA marketplace
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage, energy credits, foreign income, military, stock options, education (probe), charitable, gambling, alimony, household employee, student loans (probe)
**Expected Count:** 10-14 questions total

#### UC-034: HOH, W-2, Low Income ($25k-$50k), 26-49, 2+ Young Children
**Profile:** Head of household with multiple kids, working-class family.
**Phase 1:** Filing Status(HOH) -> Income($25k-$50k) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Childcare expenses
- EITC (HOH + 2+ children -- max credit range)
- Child Tax Credit (multiple)
- Education (for self)
- Student loans
- Retirement contributions
- ACA marketplace
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage (probe), energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 11-15 questions total

#### UC-035: HOH, W-2, Mid Income ($50k-$100k), 26-49, Older Children (13-24 student)
**Profile:** Single parent with teenager/college student.
**Phase 1:** Filing Status(HOH) -> Income($50k-$100k) -> State -> Dependents(1+, ages 13-24 students) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Education expenses (AOTC / LLC for student dependents)
- 529 plan
- Student's own income
- Credit for Other Dependents (if 17+)
- Retirement contributions
- HSA
- Mortgage / homeowner
- Charitable donations
- Life events
**Questions SKIPPED:** Business, K-1, rental, childcare (over 13), EITC (likely over threshold), energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-036: QSS, W-2, Mid Income ($50k-$100k), 30-49, 1 Young Child (<13)
**Profile:** Qualifying surviving spouse, lost partner within last 2 years, young child.
**Phase 1:** Filing Status(QSS) -> Income($50k-$100k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Year of spouse's death (must be within 2 tax years)
- Childcare expenses
- Child Tax Credit
- Retirement contributions
- HSA
- Mortgage / homeowner
- Life events (bereavement-sensitive questions)
- Insurance / survivor benefits
**Questions SKIPPED:** Business, K-1, rental, EITC (check income), education (probe), student loans (probe), energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 12-16 questions total
**CRITICAL NOTE:** QSS status expires after 2 years from spouse's death. Must validate year.

#### UC-037: Single, W-2 (multiple jobs), Mid Income ($50k-$100k), 26-49, No Dependents
**Profile:** Worker with 2+ W-2s, possible withholding issues.
**Phase 1:** Filing Status(Single) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(W-2 multiple)
**Phase 2 Questions Asked:**
- Number of W-2s
- Withholding from each (CRITICAL -- multiple W-2 under-withholding trap)
- Age
- Retirement contributions (from primary employer)
- HSA
- Student loans (probe)
- Investments (probe)
- Life events (job change?)
**Questions SKIPPED:** Business, K-1, rental, childcare, EITC, education (probe), mortgage, energy credits, foreign income, military, stock options, charitable (probe), gambling, alimony, household employee
**Expected Count:** 10-14 questions total
**CRITICAL NOTE:** Multiple W-2 filers are the #1 group surprised by owing tax. Withholding check is critical.

#### UC-038: MFJ, W-2 (multiple jobs -- both spouses work), High Income ($100k-$200k), 26-49, 2+ Young Children
**Profile:** Dual-income married couple, both with W-2s, young kids.
**Phase 1:** Filing Status(MFJ) -> Income($100k-$200k) -> State -> Dependents(2+, children <13) -> Income Type(W-2 multiple)
**Phase 2 Questions Asked:**
- Number of W-2s (both spouses)
- Withholding from each (marriage penalty / two-earner trap)
- Ages
- Childcare expenses (Dependent Care FSA from each employer?)
- Child Tax Credit
- Retirement contributions (both employers)
- HSA (which employer?)
- Mortgage / homeowner
- Property taxes
- Investments
- Charitable donations
- Itemize vs. standard
- Life events
**Questions SKIPPED:** Business, K-1, rental (probe), EITC, education credits (phased out), student loans (probe), energy credits (probe), foreign income, military, gambling, alimony, household employee (probe -- nanny?)
**Expected Count:** 15-20 questions total

#### UC-039: MFJ, W-2, Very High Income ($200k+), 65+, No Dependents
**Profile:** High-income senior couple, one or both still working, Social Security.
**Phase 1:** Filing Status(MFJ) -> Income($200k+) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages (additional standard deduction for 65+)
- Social Security income (taxability at this income = 85%)
- Medicare premiums / IRMAA (high income surcharge)
- Retirement distributions / RMD (if 73+)
- Retirement contributions (if still working)
- Investments
- Mortgage / homeowner
- Property taxes
- Charitable donations (QCD strategy if 70.5+)
- Itemize vs. standard
- AMT / NIIT
- Estimated payments
- Life events
**Questions SKIPPED:** Business, K-1, childcare, EITC, education, student loans, Saver's Credit, ACA, energy credits (probe), foreign income, military, stock options, gambling (probe), alimony, household employee (probe)
**Expected Count:** 16-21 questions total

#### UC-040: Single, W-2, Low Income ($25k-$50k), 26-49, Elderly/Disabled Relative
**Profile:** Caretaker supporting parent/relative, may qualify for HOH.
**Phase 1:** Filing Status(HOH if qualifying) -> Income($25k-$50k) -> State -> Dependents(1, elderly relative) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Dependent's relationship and living arrangement
- Dependent's income (must be under $4,700 for qualifying relative)
- Support test (>50% of dependent's support)
- Credit for Other Dependents ($500)
- Medical expenses paid for dependent
- EITC eligibility (elderly dependent doesn't count for child EITC)
- Retirement contributions
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, childcare (not qualifying child), mortgage (probe), energy credits, foreign income, military, stock options, education, student loans, charitable, gambling, alimony, household employee
**Expected Count:** 11-15 questions total

#### UC-041 through UC-060: Additional W-2 Combinations

#### UC-041: Single, W-2, Very Low Income, 65+, 1 Young Child (grandparent raising grandchild)
**Profile:** Elderly grandparent raising grandchild on limited income.
**Phase 1:** Filing Status(HOH) -> Income(<$25k) -> State -> Dependents(1, grandchild <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age (65+ additional standard deduction)
- Social Security income
- EITC (grandchild qualifies as child for EITC)
- Child Tax Credit
- Childcare expenses
- Elderly/Blind credit check
- ACA / Medicare
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage, energy credits, foreign income, military, stock options, education, student loans, charitable, gambling, alimony, household employee, retirement contributions (probe)
**Expected Count:** 11-15 questions total

#### UC-042: MFJ, W-2, Low Income ($25k-$50k), 26-49, 1 Young Child + Elderly Relative
**Profile:** Sandwich generation -- caring for child and parent.
**Phase 1:** Filing Status(MFJ) -> Income($25k-$50k) -> State -> Dependents(2 -- child + elderly) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Child details (CTC eligibility)
- Elderly relative income test
- Childcare expenses
- Medical expenses for elderly relative
- EITC (1 qualifying child for EITC calculation)
- CTC + Credit for Other Dependents
- Retirement contributions
- ACA
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage (probe), energy credits, foreign income, military, stock options, education, student loans, charitable, gambling, alimony, household employee
**Expected Count:** 13-17 questions total

#### UC-043: Single, W-2, Mid Income ($50k-$100k), Under 26, Older Children (teenage parent with teen child)
**Profile:** Young person with older teen dependent -- uncommon but valid.
**Phase 1:** Filing Status(HOH) -> Income($50k-$100k) -> State -> Dependents(1, child 13-17) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Child Tax Credit (if child under 17)
- Credit for Other Dependents (if 17+)
- Education expenses (for self -- may be in college)
- Student loans
- Retirement contributions
- HSA
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, childcare (child over 13), EITC (probe), mortgage, energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 10-14 questions total

#### UC-044: MFJ, W-2 (multiple jobs), Very High Income ($200k+), 26-49, No Dependents
**Profile:** Power couple, both high earners, complex withholding.
**Phase 1:** Filing Status(MFJ) -> Income($200k+) -> State -> Dependents(0) -> Income Type(W-2 multiple)
**Phase 2 Questions Asked:**
- Number of W-2s and amounts
- Withholding adequacy (marriage penalty check)
- Ages
- Retirement (max 401k both, backdoor Roth both)
- HSA
- Investments (NIIT at $250k MFJ)
- Stock options / RSU (both spouses)
- Mortgage / homeowner
- Property taxes (SALT cap)
- Charitable donations
- Itemize vs. standard
- AMT / NIIT
- Estimated tax payments
- Life events
**Questions SKIPPED:** Business, K-1, childcare, EITC, education credits, student loans, Saver's Credit, ACA, gambling, alimony, household employee (probe)
**Expected Count:** 16-21 questions total

#### UC-045: HOH, W-2, Very High Income ($200k+), 26-49, 2+ Young Children
**Profile:** High-earning single parent, needs maximum optimization.
**Phase 1:** Filing Status(HOH) -> Income($200k+) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Childcare expenses
- Child Tax Credit (phaseout starts $200k single/HOH)
- Retirement (max out)
- HSA
- Investments
- Stock options / RSU
- Mortgage / homeowner
- Property taxes
- Charitable donations
- Itemize vs. standard
- AMT / NIIT
- Estimated payments
- Life events
**Questions SKIPPED:** Business, K-1, EITC, education credits (phased out), student loans (phased out), Saver's Credit, ACA, gambling, alimony (probe), household employee (ASK -- likely nanny)
**Expected Count:** 16-21 questions total

#### UC-046: MFJ, W-2, Mid Income, 65+, 1 Young Child (late-in-life child)
**Profile:** Older couple with young child. Additional standard deduction + CTC.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages (65+ for one or both -- extra deduction)
- Social Security (one or both collecting)
- Child Tax Credit
- Childcare expenses
- Retirement distributions
- RMD check (if 73+)
- Mortgage / homeowner
- Medicare / IRMAA
- Life events
**Questions SKIPPED:** Business, K-1, EITC (check), education, student loans, energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 13-17 questions total

#### UC-047: Single, W-2, Very Low Income (<$25k), Under 26, Older Child (17-24 student)
**Profile:** Young person supporting a student sibling as dependent.
**Phase 1:** Filing Status(HOH) -> Income(<$25k) -> State -> Dependents(1, sibling age 17-24 student) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Dependent relationship verification (sibling)
- Support test
- Credit for Other Dependents (if 17+)
- Education expenses (for dependent)
- EITC (qualifying relative rules different)
- ACA
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, childcare, mortgage, energy credits, foreign income, military, stock options, charitable, retirement, student loans, gambling, alimony, household employee
**Expected Count:** 10-14 questions total

#### UC-048: MFJ, W-2, Low Income ($25k-$50k), Under 26, 1 Young Child
**Profile:** Young married couple with baby, first family tax return.
**Phase 1:** Filing Status(MFJ) -> Income($25k-$50k) -> State -> Dependents(1, infant/toddler) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Spouse income
- Childcare expenses (if both work)
- EITC (MFJ + 1 child)
- Child Tax Credit
- Education (either spouse in school?)
- Student loans (likely)
- Retirement contributions (starting early = Saver's Credit)
- ACA
- Life events (had baby? recently married?)
**Questions SKIPPED:** Business, K-1, rental, investments, mortgage (unlikely under 26), energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-049: Single, W-2, High Income ($100k-$200k), 50-64, 2+ Young Children
**Profile:** Older parent with young kids, career + family.
**Phase 1:** Filing Status(Single or HOH) -> Income($100k-$200k) -> State -> Dependents(2+, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age (catch-up eligible)
- Childcare expenses
- Child Tax Credit
- Retirement contributions (catch-up)
- HSA (catch-up if 55+)
- Mortgage / homeowner
- Property taxes
- Investments
- Charitable donations
- Itemize vs. standard
- Life events
**Questions SKIPPED:** Business, K-1, rental, EITC, education credits, student loans (likely paid), energy credits (probe), foreign income, military, gambling, alimony, household employee (probe)
**Expected Count:** 14-18 questions total

#### UC-050: MFJ, W-2, Very High Income ($200k+), 50-64, Older Children (13-24 students)
**Profile:** Affluent empty-nesters-to-be with college kids.
**Phase 1:** Filing Status(MFJ) -> Income($200k+) -> State -> Dependents(1+, children 13-24 students) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages (catch-up)
- Education expenses (CRITICAL -- but phased out at $180k MFJ for AOTC)
- 529 plans
- Student's income and filing status
- Credit for Other Dependents (if 17+)
- Retirement (max catch-up)
- HSA
- Investments
- Stock options / RSU
- Mortgage
- Property taxes
- Charitable
- AMT / NIIT
- Estimated payments
- Life events
**Questions SKIPPED:** Business, K-1, childcare, EITC, student loans (phased out), Saver's Credit, ACA, energy credits (probe), foreign income, military, gambling, alimony (probe), household employee (probe)
**Expected Count:** 17-22 questions total

#### UC-051: HOH, W-2, Low Income ($25k-$50k), 65+, Elderly/Disabled Relative
**Profile:** Senior caring for another senior, limited income.
**Phase 1:** Filing Status(HOH) -> Income($25k-$50k) -> State -> Dependents(1, elderly relative) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age (65+ additional deduction)
- Social Security
- Dependent details and income test
- Credit for Other Dependents
- Medical expenses for both
- Elderly/Blind credit
- Retirement distributions
- ACA / Medicare
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, childcare, EITC (check -- elderly dep doesn't count as child), education, student loans, mortgage (probe), energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-052: MFS, W-2, Very High Income ($200k+), 26-49, No Dependents
**Profile:** High earner filing separately, possibly for liability protection or student loans.
**Phase 1:** Filing Status(MFS) -> Income($200k+) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Reason for MFS
- Retirement (IRA deduction restricted for MFS)
- HSA
- Investments
- Stock options / RSU
- Mortgage (must itemize if spouse does)
- Property taxes
- Charitable
- Itemize vs. standard (MUST match spouse)
- AMT (lower exemption for MFS)
- NIIT (threshold $125k for MFS!)
- Estimated payments
- Life events
**Questions SKIPPED:** EITC (ineligible), education credits (limited MFS), student loans (ineligible MFS), Saver's Credit (lower threshold), childcare (no deps), ACA premium credit (MFS ineligible), gambling, alimony, household employee
**Expected Count:** 15-20 questions total
**CRITICAL NOTE:** NIIT threshold is $125k for MFS (half of MFJ), not $200k.

#### UC-053: MFJ, W-2, Mid Income ($50k-$100k), 26-49, No Dependents, Pays Alimony
**Profile:** Remarried, paying alimony from pre-2019 divorce.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Spouse income
- Alimony paid (CRITICAL: deductible only if divorce finalized before 2019)
- Divorce date verification
- Alimony amount
- Retirement contributions
- Mortgage / homeowner
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments (probe), childcare, EITC, education, student loans, energy credits, foreign income, military, stock options, gambling, household employee
**Expected Count:** 11-15 questions total
**CRITICAL NOTE:** Alimony deduction ONLY for pre-2019 divorces. Post-2018 alimony is not deductible.

#### UC-054: Single, W-2, Mid Income, Under 26, No Dependents, Has Crypto
**Profile:** Young tech worker with W-2 and crypto trading.
**Phase 1:** Filing Status(Single) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Crypto transactions (CRITICAL -- must report)
- Crypto gains/losses
- Cost basis method
- Any crypto staking/mining income (ordinary income)
- Education expenses
- Student loans
- Retirement contributions
- HSA
- Life events
**Questions SKIPPED:** Business (unless mining), K-1, rental, childcare, EITC, mortgage, energy credits, foreign income (unless foreign exchange), military, charitable, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-055: MFJ, W-2, High Income, 26-49, 2 Young Children, Has Energy Credits (solar)
**Profile:** Family that installed solar panels, seeking Residential Clean Energy Credit.
**Phase 1:** Filing Status(MFJ) -> Income($100k-$200k) -> State -> Dependents(2, children <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Childcare expenses
- Child Tax Credit
- Energy improvements (CRITICAL: solar = 30% credit, no cap)
- Solar installation cost
- Battery storage
- Retirement contributions
- HSA
- Mortgage / homeowner
- Investments
- Charitable
- Life events
**Questions SKIPPED:** Business, K-1, rental, EITC, education credits, student loans, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 15-19 questions total

#### UC-056: Single, W-2, Low Income ($25k-$50k), 26-49, No Dependents, ACA Marketplace
**Profile:** Worker without employer insurance, bought marketplace plan.
**Phase 1:** Filing Status(Single) -> Income($25k-$50k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- ACA marketplace (Form 1095-A CRITICAL)
- Premium Tax Credit reconciliation
- Did you receive advance premium credits?
- Income changes during year (affects PTC)
- Retirement contributions
- HSA (not available with most marketplace plans)
- Student loans (probe)
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments, childcare, EITC (check), mortgage, energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 11-15 questions total

#### UC-057: MFJ, W-2 (multiple), Very High Income ($200k+), 26-49, 2+ Young Children, Has Household Employee (nanny)
**Profile:** High-income family with live-in or full-time nanny.
**Phase 1:** Filing Status(MFJ) -> Income($200k+) -> State -> Dependents(2+, children <13) -> Income Type(W-2 multiple)
**Phase 2 Questions Asked:**
- Withholding (multiple W-2s)
- Ages
- Nanny/household employee (Schedule H CRITICAL)
- Nanny wages paid
- Did you withhold FICA for nanny? (threshold $2,700)
- Childcare expenses (Dependent Care FSA)
- Child Tax Credit
- Retirement (max both)
- HSA
- Investments
- Mortgage
- Property taxes
- Charitable
- AMT / NIIT
- Estimated payments
- Life events
**Questions SKIPPED:** Business, K-1, EITC, education credits, student loans, Saver's Credit, ACA, gambling, alimony
**Expected Count:** 18-23 questions total
**CRITICAL NOTE:** Nanny tax (Schedule H) is a common audit trigger. Must ask if wages exceed $2,700.

#### UC-058: Single, W-2, Mid Income, 26-49, No Deps, Foreign Income
**Profile:** US citizen with W-2 + foreign income or foreign bank accounts.
**Phase 1:** Filing Status(Single) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Foreign income source (employment, investment, rental?)
- Foreign tax paid (Foreign Tax Credit or exclusion)
- FBAR requirement (foreign accounts > $10k aggregate)
- FATCA (Form 8938 if > $50k)
- Foreign bank accounts
- Retirement contributions
- HSA
- Investments
- Life events
**Questions SKIPPED:** Business, K-1, rental (unless foreign), childcare, EITC, education (probe), mortgage, energy credits, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 13-17 questions total

#### UC-059: MFJ, W-2, Mid Income, 26-49, 1 Young Child, Has Gambling Income
**Profile:** Casual gambler with W-2G reported winnings.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(1, child <13) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Ages
- Gambling winnings amount (Form W-2G)
- Gambling losses (deductible up to winnings, only if itemize)
- Childcare expenses
- Child Tax Credit
- Retirement contributions
- Mortgage / homeowner
- Itemize vs. standard (gambling losses only deductible if itemizing)
- Life events
**Questions SKIPPED:** Business, K-1, rental, EITC (check), education, student loans, energy credits, foreign income, military, stock options, alimony, household employee
**Expected Count:** 12-16 questions total

#### UC-060: HOH, W-2, Mid Income, 26-49, 1 Disabled Dependent
**Profile:** Parent caring for disabled child/adult, special credits.
**Phase 1:** Filing Status(HOH) -> Income($50k-$100k) -> State -> Dependents(1, disabled) -> Income Type(W-2)
**Phase 2 Questions Asked:**
- Withholding
- Age
- Dependent's disability status and documentation
- Credit for Other Dependents or CTC (depends on age)
- ABLE account contributions
- Medical expenses (may be significant -- itemize?)
- Disability-related care expenses
- Retirement contributions
- Mortgage / homeowner
- Life events
**Questions SKIPPED:** Business, K-1, rental, investments (probe), EITC (check), education (special rules for disabled students), energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 12-16 questions total

---

## GROUP 2: W-2 + Side Hustle

**Scope:** Primary W-2 income with secondary self-employment (1099-NEC, gig, freelance).

### Group 2 Rules

**Critical validation rules (MUST ask):**
- All Phase 1 core questions
- Side hustle income amount
- Business expenses (home office, mileage, supplies)
- Self-employment tax awareness
- Quarterly estimated payments made?
- Business entity type (sole prop assumed unless stated)

**Mutual exclusion rules (NEVER ask):**
- K-1 questions (unless explicitly stated)
- S-Corp / C-Corp questions (this is sole prop/gig)
- Partnership allocation questions
- Corporate tax questions

**Follow-up chains:**
- IF side_hustle = yes THEN ask income amount
- IF side_hustle_income > $400 THEN self-employment tax applies
- IF side_hustle_income > $0 THEN ask business expenses
- IF business_expenses = yes THEN ask home_office, mileage, supplies
- IF net_se_income > $0 THEN ask estimated_payments
- IF estimated_payments = no AND se_income > $1000 THEN warn about penalty

---

#### UC-061: Single, W-2 + Side Hustle, Low Income ($25k-$50k combined), Under 26, No Dependents
**Profile:** Young person with day job + freelance gig (Uber, Etsy, tutoring).
**Phase 1:** Filing Status(Single) -> Income($25k-$50k) -> State -> Dependents(0) -> Income Type(W-2 + Self-Employment)
**Phase 2 Questions Asked:**
- W-2 withholding
- Age
- Side hustle type and income
- Business expenses (mileage, phone, supplies)
- Home office (if applicable)
- Estimated tax payments made?
- Self-employment tax calculation
- QBI deduction eligibility
- Education expenses
- Student loans
- Retirement contributions (SEP-IRA or Solo 401k available!)
- Health insurance
- Life events
**Questions SKIPPED:** K-1, rental, investments (probe), childcare, EITC (check -- SE income counts as earned), mortgage, energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 14-18 questions total

#### UC-062: Single, W-2 + Side Hustle, Mid Income ($50k-$100k combined), 26-49, No Dependents
**Profile:** Professional with consulting or freelance side income.
**Phase 1:** Filing Status(Single) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(W-2 + Self-Employment)
**Phase 2 Questions Asked:**
- W-2 withholding
- Age
- Side hustle income and type
- Business expenses
- Home office
- Vehicle / mileage
- Estimated payments
- Self-employment tax
- QBI deduction
- Retirement (SEP-IRA from SE income)
- HSA
- Mortgage / homeowner
- Investments (probe)
- Charitable
- Life events
**Questions SKIPPED:** K-1, rental, childcare, EITC (over threshold), education (probe), student loans (probe), energy credits, foreign income, military, gambling, alimony, household employee
**Expected Count:** 15-19 questions total

#### UC-063: MFJ, W-2 + Side Hustle, Mid Income ($50k-$100k), 26-49, 2+ Young Children
**Profile:** One spouse has W-2, other does gig work while watching kids.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(2+, children <13) -> Income Type(W-2 + Self-Employment)
**Phase 2 Questions Asked:**
- W-2 withholding
- Ages
- Side hustle income (which spouse)
- Business expenses
- Home office
- Estimated payments
- Self-employment tax
- QBI deduction
- Childcare expenses (CRITICAL: must be work-related, including SE work)
- EITC (SE income counts, check MFJ thresholds)
- Child Tax Credit
- Retirement contributions (both spouses -- SEP for SE spouse)
- Student loans
- ACA marketplace (if SE spouse not covered)
- Life events
**Questions SKIPPED:** K-1, rental, investments (probe), mortgage (probe), energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 16-20 questions total

#### UC-064: Single, W-2 + Side Hustle, High Income ($100k-$200k combined), 26-49, No Dependents
**Profile:** High-earning professional with substantial consulting income.
**Phase 1:** Filing Status(Single) -> Income($100k-$200k) -> State -> Dependents(0) -> Income Type(W-2 + Self-Employment)
**Phase 2 Questions Asked:**
- W-2 withholding
- Age
- Side hustle income (Schedule C)
- Business expenses (detailed)
- Home office
- Vehicle / mileage
- Estimated payments (CRITICAL at this income)
- Self-employment tax
- QBI deduction (SSTB check -- phaseout $182,100-$232,100 single)
- Retirement (max SEP-IRA or Solo 401k -- big planning item)
- HSA
- Investments
- Stock options / RSU (from W-2 employer)
- Mortgage / homeowner
- Charitable
- Itemize vs. standard
- Life events
**Questions SKIPPED:** K-1, rental, childcare, EITC (over), education (phased out), student loans (phased out), energy credits, foreign income, military, gambling, alimony, household employee
**Expected Count:** 17-22 questions total

#### UC-065: MFJ, W-2 + Side Hustle, Very High Income ($200k+ combined), 26-49, 2+ Young Children
**Profile:** High-earning couple, one has side business generating significant income.
**Phase 1:** Filing Status(MFJ) -> Income($200k+) -> State -> Dependents(2+, children <13) -> Income Type(W-2 + Self-Employment)
**Phase 2 Questions Asked:**
- W-2 withholding
- Ages
- Side hustle income and type
- Business expenses
- Home office
- Estimated payments
- Self-employment tax
- QBI deduction (SSTB phaseout $364,200-$464,200 MFJ)
- Childcare expenses
- Child Tax Credit
- Retirement (max all vehicles)
- HSA
- Investments (NIIT check)
- Stock options
- Mortgage / homeowner
- Property taxes
- Charitable
- Itemize vs. standard
- AMT / NIIT
- Life events
**Questions SKIPPED:** K-1 (unless partnership), EITC, education credits (phased out), student loans (phased out), Saver's Credit, ACA, gambling, alimony, household employee (ASK -- nanny)
**Expected Count:** 20-25 questions total

#### UC-066: HOH, W-2 + Side Hustle, Low Income ($25k-$50k), 26-49, 1 Young Child
**Profile:** Single parent with W-2 and side gig to make ends meet.
**Phase 1:** Filing Status(HOH) -> Income($25k-$50k) -> State -> Dependents(1, child <13) -> Income Type(W-2 + Self-Employment)
**Phase 2 Questions Asked:**
- W-2 withholding
- Age
- Side hustle income and expenses
- Self-employment tax
- Childcare (work-related for both W-2 and SE)
- EITC (max benefit zone)
- Child Tax Credit
- QBI deduction
- Estimated payments
- Retirement (SEP from SE income)
- ACA marketplace
- Life events
**Questions SKIPPED:** K-1, rental, investments, mortgage, energy credits, foreign income, military, stock options, education (probe), student loans (probe), charitable, gambling, alimony, household employee
**Expected Count:** 14-18 questions total

#### UC-067: Single, W-2 + Side Hustle (Uber/Lyft), Low Income, Under 26, No Dependents
**Profile:** Young ride-share driver with part-time W-2 job.
**Phase 1:** Filing Status(Single) -> Income($25k-$50k) -> State -> Dependents(0) -> Income Type(W-2 + Gig)
**Phase 2 Questions Asked:**
- W-2 withholding
- Age
- Ride-share income (1099-NEC/1099-K)
- Vehicle expenses (standard mileage rate vs. actual -- CRITICAL for drivers)
- Mileage log
- Phone/data plan (business %)
- Car insurance (business %)
- Estimated payments
- Self-employment tax
- QBI deduction
- Education expenses
- Student loans
- Health insurance
- Life events
**Questions SKIPPED:** K-1, rental, investments, childcare, home office (unlikely for driver), mortgage, energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee
**Expected Count:** 15-19 questions total

#### UC-068: MFJ, W-2 + Etsy/Online Sales, Mid Income, 26-49, 1 Young Child
**Profile:** One spouse sells crafts/goods online, other has W-2.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(1, child <13) -> Income Type(W-2 + Self-Employment)
**Phase 2 Questions Asked:**
- W-2 withholding
- Ages
- Online sales income (1099-K threshold changes)
- Cost of goods sold (COGS)
- Business expenses (supplies, shipping, packaging)
- Home office / workspace
- Inventory
- Estimated payments
- Self-employment tax
- QBI deduction
- Childcare expenses
- Child Tax Credit
- Retirement
- Life events
**Questions SKIPPED:** K-1, rental, investments (probe), EITC (check), mortgage (probe), energy credits, foreign income, military, stock options, gambling, alimony, household employee
**Expected Count:** 15-19 questions total

#### UC-069 through UC-085: Additional W-2 + Side Hustle Combinations

#### UC-069: MFJ, W-2 + Real Estate Agent Side Hustle, High Income, 26-49, No Deps
**Profile:** Spouse does real estate on the side -- significant deductions.
**Phase 2 Added Questions:** Real estate license costs, MLS fees, open house expenses, marketing, vehicle/mileage, continuing education for license
**Expected Count:** 17-22 questions total

#### UC-070: Single, W-2 + Consulting, Very High Income ($200k+), 26-49, No Deps
**Profile:** Tech employee doing high-value consulting on the side.
**Phase 2 Added Questions:** S-Corp election consideration, reasonable salary, QBI SSTB check, estimated payments, retirement strategy
**Expected Count:** 18-23 questions total

#### UC-071: HOH, W-2 + DoorDash/Instacart, Very Low Income (<$25k), 26-49, 2+ Kids
**Profile:** Single parent doing delivery gigs, maximum EITC with SE income.
**Phase 2 Key Focus:** EITC with SE income, vehicle expenses, childcare during deliveries
**Expected Count:** 14-18 questions total

#### UC-072: MFJ, W-2 + Photography Business, Mid Income, 26-49, 1 Young Child
**Profile:** Hobbyist turned side-business photographer.
**Phase 2 Key Focus:** Hobby vs. business determination (profit motive), equipment depreciation, Section 179
**Expected Count:** 15-19 questions total

#### UC-073: Single, W-2 + YouTube/Content Creator, Mid Income, Under 26, No Deps
**Profile:** Content creator with ad revenue + sponsorships.
**Phase 2 Key Focus:** 1099-MISC/NEC from platforms, home studio deduction, equipment, self-employment tax
**Expected Count:** 15-19 questions total

#### UC-074: MFJ, W-2 + Rental Property Management Side Gig, High Income, 50-64, No Deps
**Profile:** One spouse manages properties as a business, other has W-2.
**Phase 2 Key Focus:** Crosses into Group 3 territory -- Schedule C for management + Schedule E for owned rentals
**Expected Count:** 18-23 questions total

#### UC-075: Single, W-2 + Tutoring/Teaching Side Hustle, Low Income, Under 26, No Deps
**Profile:** Teacher with private tutoring income on the side.
**Phase 2 Key Focus:** Educator expense deduction ($300), SE income, home office
**Expected Count:** 14-18 questions total

#### UC-076: MFJ, Both W-2 + One Side Hustle, Very High Income, 26-49, 2+ Kids
**Profile:** Both spouses have W-2s, one also has consulting income.
**Expected Count:** 20-25 questions total

#### UC-077: HOH, W-2 + Pet Sitting/Dog Walking, Low Income, 50-64, Elderly Relative
**Profile:** Older worker supplementing income with pet care, supporting parent.
**Expected Count:** 15-19 questions total

#### UC-078: Single, W-2 + Music/Art Sales, Very Low Income, Under 26, No Deps
**Profile:** Artist selling work, hobby vs. business question critical.
**Expected Count:** 13-17 questions total

#### UC-079: MFJ, W-2 + MLM/Direct Sales, Low Income, 26-49, 1 Young Child
**Profile:** MLM participant -- careful: most lose money, still must report.
**Phase 2 Key Focus:** Gross receipts vs. net, product for personal use, inventory
**Expected Count:** 14-18 questions total

#### UC-080: Single, W-2 + Crypto Mining, High Income, Under 26, No Deps
**Profile:** W-2 worker mining crypto as side income.
**Phase 2 Key Focus:** Mining = ordinary SE income, electricity costs, equipment depreciation
**Expected Count:** 16-20 questions total

#### UC-081: MFJ, W-2 + Airbnb (one room), Mid Income, 26-49, No Deps
**Profile:** Renting spare room on Airbnb -- Schedule C or Schedule E determination.
**Phase 2 Key Focus:** Days rented vs personal use, 14-day rule, Schedule C vs E
**Expected Count:** 16-20 questions total

#### UC-082: Single, W-2 + Amazon FBA, Mid Income, 26-49, No Deps
**Profile:** Amazon FBA seller with inventory, shipping, and platform fees.
**Phase 2 Key Focus:** COGS, inventory accounting, multi-state nexus, 1099-K
**Expected Count:** 16-20 questions total

#### UC-083: HOH, W-2 + Childcare Provider, Low Income, 26-49, 2+ Kids
**Profile:** Runs home daycare as side business, cares for own kids too.
**Phase 2 Key Focus:** Time/Space % for home office, food expenses, licensing
**Expected Count:** 16-20 questions total

#### UC-084: MFJ, W-2 + Freelance Writing, Very High Income, 26-49, No Deps, Foreign Income Component
**Profile:** Writer with foreign publication income.
**Phase 2 Key Focus:** Foreign tax credit for taxes paid to other countries, FBAR
**Expected Count:** 18-23 questions total

#### UC-085: Single, W-2 + Multiple Gigs (Uber + Instacart + TaskRabbit), Low Income, 26-49, No Deps
**Profile:** Multiple gig platforms, each issuing 1099s.
**Phase 2 Key Focus:** Consolidate all SE income, aggregate vehicle expenses, multiple 1099s
**Expected Count:** 15-19 questions total

---

## GROUP 3: Self-Employed / LLC

**Scope:** Primary income is self-employment. Sole proprietor or single-member LLC (disregarded entity).

### Group 3 Rules

**Critical validation rules (MUST ask):**
- Business type and nature
- Gross income and expenses (Schedule C)
- Home office (simplified or actual)
- Vehicle use
- Quarterly estimated payments
- Self-employment tax
- QBI deduction (Section 199A) -- SSTB determination CRITICAL
- Health insurance (self-employed health deduction)
- Retirement plan type and contributions

**Mutual exclusion rules (NEVER ask):**
- W-2 withholding (no employer)
- Employer benefits questions (401k match, etc.)
- K-1 questions (unless also has K-1 from another entity)

**Follow-up chains:**
- IF business_type = professional_service THEN ask SSTB determination for QBI
- IF gross_income > $250k THEN ask about S-Corp election consideration
- IF has_employees THEN ask about employer taxes, workers' comp
- IF home_office = yes THEN ask square footage method preference
- IF vehicle_use = yes THEN ask business % and method (standard vs actual)
- IF health_insurance = self_paid THEN calculate above-the-line deduction
- IF net_profit > $0 THEN calculate SE tax and suggest retirement contributions

---

#### UC-086: Single, Self-Employed (Sole Prop), Very Low Income (<$25k), Under 26, No Deps
**Profile:** Young freelancer just starting out, gig economy primary income.
**Phase 1:** Filing Status(Single) -> Income(<$25k) -> State -> Dependents(0) -> Income Type(Self-Employed)
**Phase 2 Questions Asked:**
- Business type/nature
- Gross income
- Business expenses (detailed)
- Home office
- Vehicle use
- 1099-NEC/1099-K received?
- Estimated payments made?
- Self-employment tax calculation
- QBI deduction
- Health insurance (marketplace?)
- ACA premium tax credit
- Education expenses (for self)
- Student loans
- Life events
**Questions SKIPPED:** W-2 withholding, K-1, rental, investments, childcare, mortgage, energy credits, foreign income, military, stock options, charitable, gambling, alimony, household employee, employer retirement
**Expected Count:** 15-19 questions total

#### UC-087: Single, Self-Employed (Sole Prop), Low Income ($25k-$50k), 26-49, No Deps
**Profile:** Established freelancer, moderate income.
**Phase 2 Questions Asked:**
- Business type, gross income, expenses
- Home office, vehicle
- Estimated payments (CRITICAL)
- SE tax
- QBI deduction (SSTB?)
- Retirement (SEP-IRA or Solo 401k -- MAJOR planning opportunity)
- Health insurance (SE health deduction)
- HSA
- Student loans (probe)
- Investments (probe)
- Life events
**Expected Count:** 15-19 questions total

#### UC-088: Single, Self-Employed (Sole Prop), Mid Income ($50k-$100k), 26-49, No Deps
**Profile:** Successful freelancer/consultant.
**Phase 2 Questions Asked:**
- Business details, income, expenses
- Home office, vehicle
- Estimated payments
- SE tax
- QBI (SSTB check critical at this income)
- Retirement (max SEP or Solo 401k)
- Health insurance (SE deduction)
- HSA (HDHP)
- Mortgage / homeowner
- Investments
- Charitable
- Life events
**Expected Count:** 16-20 questions total

#### UC-089: Single, Self-Employed (Sole Prop), High Income ($100k-$200k), 26-49, No Deps
**Profile:** High-earning consultant or professional.
**Phase 2 Questions Asked:**
- Business details, income, expenses (detailed)
- Home office, vehicle
- Estimated payments (quarterly)
- SE tax
- QBI (SSTB phaseout $182,100-$232,100 single -- CRITICAL)
- S-Corp election discussion (SE tax savings)
- Retirement (max Solo 401k with employer + employee contributions)
- Health insurance (SE deduction)
- HSA
- Investments
- Mortgage / homeowner
- Charitable
- Itemize vs. standard
- Life events
**Questions SKIPPED:** K-1, rental, childcare, EITC, education credits (phased out), student loans (phased out)
**Expected Count:** 17-22 questions total

#### UC-090: Single, Self-Employed (Sole Prop), Very High Income ($200k+), 26-49, No Deps
**Profile:** Top freelancer or consultant -- must discuss entity structure.
**Phase 2 Questions Asked:**
- Business details, income, expenses
- Estimated payments (penalty check)
- SE tax (MAJOR concern at this income)
- QBI (likely phased out for SSTB)
- S-Corp election (STRONG recommendation at this income)
- Retirement (max everything)
- Health insurance
- HSA
- Investments (NIIT check)
- Mortgage
- Property taxes
- Charitable
- AMT check
- NIIT applicability
- Life events
**Expected Count:** 18-23 questions total

#### UC-091: MFJ, Self-Employed + Spouse W-2, Mid Income ($50k-$100k), 26-49, 2+ Kids
**Profile:** One spouse self-employed, other has W-2 with benefits.
**Phase 2 Questions Asked:**
- W-2 spouse withholding
- SE spouse business details
- Business income and expenses
- Home office, vehicle
- Estimated payments
- SE tax
- QBI deduction
- Childcare expenses
- Child Tax Credit
- Retirement (employer plan + SEP/Solo 401k)
- Health insurance (through W-2 spouse? SE deduction?)
- HSA (through employer?)
- Education
- Student loans
- Life events
**Expected Count:** 18-23 questions total

#### UC-092: MFJ, Both Self-Employed, High Income ($100k-$200k), 26-49, No Deps
**Profile:** Entrepreneurial couple, both running businesses.
**Phase 2 Questions Asked:**
- Business 1 details (income, expenses, type)
- Business 2 details (income, expenses, type)
- Home office (both? allocate space)
- Vehicle (both?)
- Estimated payments (critical -- no withholding at all)
- SE tax (both schedules)
- QBI for each business
- Retirement (both can have SEP/Solo 401k)
- Health insurance
- HSA
- Investments
- Mortgage
- Charitable
- Itemize vs. standard
- Life events
**Expected Count:** 20-25 questions total

#### UC-093: Single, Self-Employed (LLC), Mid Income ($50k-$100k), 26-49, No Deps
**Profile:** LLC owner (single-member, disregarded entity).
**Phase 2 Questions Asked:**
- Same as UC-088 but additionally:
- LLC formation state
- LLC annual fees/registered agent
- Asset protection discussion
- Business insurance
**Expected Count:** 17-21 questions total
**NOTE:** Single-member LLC is tax-identical to sole prop unless S-Corp election made.

#### UC-094: HOH, Self-Employed, Low Income ($25k-$50k), 26-49, 1 Young Child
**Profile:** Self-employed single parent.
**Phase 2 Questions Asked:**
- Business details, income, expenses
- Home office, vehicle
- Estimated payments
- SE tax
- QBI deduction
- Childcare (MUST be work-related -- SE qualifies)
- EITC (SE income = earned income)
- Child Tax Credit
- ACA marketplace
- Retirement (SEP)
- Life events
**Expected Count:** 16-20 questions total

#### UC-095: MFJ, Self-Employed, Very High Income ($200k+), 50-64, No Deps
**Profile:** Mature self-employed professional at peak earnings.
**Phase 2 Questions Asked:**
- Business details (income/expenses)
- Estimated payments
- SE tax
- QBI (phaseout check)
- Entity structure optimization (S-Corp)
- Retirement (max Solo 401k with catch-up $30,500+)
- Defined benefit plan consideration (high income, age 50+)
- Health insurance
- HSA (catch-up)
- Investments (NIIT)
- Mortgage
- Charitable (donor-advised fund)
- AMT / NIIT
- Life events
**Expected Count:** 18-23 questions total

#### UC-096: Single, Self-Employed, Very Low Income (<$25k), 65+, No Deps
**Profile:** Semi-retired self-employed senior.
**Phase 2 Questions Asked:**
- Business details
- Social Security income (combined income taxability)
- SE tax
- QBI
- Health insurance (Medicare)
- Retirement distributions
- RMD (if 73+)
- Life events
**Expected Count:** 13-17 questions total

#### UC-097 through UC-110: Additional SE/LLC Combinations

#### UC-097: MFJ, Self-Employed (Consultant), Mid Income, 26-49, 2+ Kids, Has Education Expenses
**Profile:** Consultant spouse paying for MBA or certification.
**Phase 2 Key Focus:** Education as business expense vs. credit, continuing education deduction
**Expected Count:** 18-23 questions total

#### UC-098: Single, Self-Employed (Healthcare Provider), High Income, 26-49, No Deps
**Profile:** SSTB healthcare professional -- QBI phaseout critical.
**Phase 2 Key Focus:** SSTB determination (healthcare = yes), QBI phaseout at $182k-$232k
**Expected Count:** 17-22 questions total

#### UC-099: Single, Self-Employed (Lawyer), Very High Income ($200k+), 26-49, No Deps
**Profile:** Solo attorney -- SSTB, QBI fully phased out above $232,100.
**Phase 2 Key Focus:** QBI = $0 (SSTB above threshold), S-Corp election critical
**Expected Count:** 18-23 questions total

#### UC-100: MFJ, Self-Employed (Contractor/Trades), Mid Income, 26-49, 2+ Kids
**Profile:** Plumber, electrician, etc. Non-SSTB business.
**Phase 2 Key Focus:** QBI = full 20% (not SSTB), tools/equipment Section 179, vehicle heavy use
**Expected Count:** 18-23 questions total

#### UC-101: HOH, Self-Employed + Rental Property, Mid Income, 50-64, 1 Older Child
**Profile:** Self-employed with rental income -- crosses groups.
**Phase 2 Key Focus:** Schedule C + Schedule E, passive activity rules for rental
**Expected Count:** 19-24 questions total

#### UC-102: Single, Self-Employed, Low Income, Under 26, No Deps, Started Business This Year
**Profile:** First-year entrepreneur, startup costs.
**Phase 2 Key Focus:** Startup costs ($5k deduction + amortize), organizational costs, first-year elections
**Expected Count:** 16-20 questions total

#### UC-103: MFJ, Self-Employed, Mid Income, 26-49, No Deps, Moved States
**Profile:** Self-employed who relocated -- multi-state filing.
**Phase 2 Key Focus:** Multi-state income allocation, moving date, nexus for SE
**Expected Count:** 18-23 questions total

#### UC-104: Single, Self-Employed (LLC), Very High Income, 26-49, No Deps, ISO/RSU from Previous Employer
**Profile:** Left corporate job (still vesting stock options), now self-employed.
**Phase 2 Key Focus:** ISO exercise AMT impact, RSU vesting income, SE income + investment income
**Expected Count:** 20-25 questions total

#### UC-105: MFJ, Self-Employed, Low Income ($25k-$50k), 26-49, 2+ Kids, ACA Marketplace
**Profile:** Family on ACA with SE income -- premium credit calculation complex.
**Phase 2 Key Focus:** ACA PTC with fluctuating SE income, advance credits reconciliation
**Expected Count:** 17-22 questions total

#### UC-106: Single, Self-Employed (Day Trader), Very High Income, 26-49, No Deps
**Profile:** Full-time trader -- mark-to-market election consideration.
**Phase 2 Key Focus:** Trader vs investor status, Section 475 election, wash sale rules, SE tax on trading income
**Expected Count:** 19-24 questions total

#### UC-107: HOH, Self-Employed, Very Low Income, 26-49, 2+ Kids
**Profile:** Self-employed single parent barely making it -- maximum credits.
**Phase 2 Key Focus:** EITC with SE (must have positive net), CTC, childcare, ACA
**Expected Count:** 16-20 questions total

#### UC-108: MFJ, Self-Employed (Both spouses), Low Income, Under 26, 1 Young Child
**Profile:** Young couple both freelancing with new baby.
**Phase 2 Key Focus:** Two Schedule Cs, childcare for both to work, ACA for family
**Expected Count:** 19-24 questions total

#### UC-109: Single, Self-Employed, Mid Income, 50-64, No Deps, Became Disabled
**Profile:** Self-employed person with new disability.
**Phase 2 Key Focus:** SSDI eligibility, disability income reporting, medical expenses, SE continuation
**Expected Count:** 16-20 questions total

#### UC-110: MFJ, Self-Employed + Investment Income Heavy, Very High Income, 50-64, No Deps
**Profile:** Business owner with significant portfolio -- NIIT + SE tax.
**Phase 2 Key Focus:** NIIT on investment income, SE tax on business, retirement max out, charitable strategies
**Expected Count:** 20-25 questions total

---

## GROUP 4: S-Corp / C-Corp / Partnership Owners

**Scope:** Business owners with pass-through or corporate entity income.

### Group 4 Rules

**Critical validation rules (MUST ask):**
- Entity type (S-Corp, C-Corp, Partnership, multi-member LLC)
- K-1 income / distributions
- Reasonable compensation (S-Corp)
- Shareholder/partner basis
- Officer compensation
- Business income vs. distributions
- Payroll taxes paid
- Entity-level deductions

**Mutual exclusion rules (NEVER ask):**
- Schedule C questions (these are entity returns, not sole prop)
- Self-employment tax on S-Corp distributions (they're exempt)
- Standard sole prop questions

**Follow-up chains:**
- IF entity = S-Corp THEN ask reasonable salary, K-1 distributions, basis
- IF entity = C-Corp THEN ask salary, dividends, double taxation
- IF entity = Partnership THEN ask allocation %, guaranteed payments, at-risk
- IF K-1_income > $0 THEN ask QBI, SSTB, W-2 wages for QBI limitation
- IF distributions > basis THEN warn about capital gains on excess
- IF entity = S-Corp AND salary unreasonably low THEN flag IRS audit risk

---

#### UC-111: Single, S-Corp Owner, Mid Income ($50k-$100k), 26-49, No Deps
**Profile:** Small business owner with S-Corp election, pays self reasonable salary.
**Phase 1:** Filing Status(Single) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(Business Owner - S-Corp)
**Phase 2 Questions Asked:**
- W-2 from S-Corp (reasonable compensation)
- K-1 income from S-Corp
- Distributions taken
- Shareholder basis
- QBI deduction (W-2 wage limitation may apply at higher incomes)
- Retirement (can have 401k through S-Corp)
- Health insurance (S-Corp >2% shareholder rules)
- HSA
- Estimated payments (on K-1 income)
- Business expenses (entity level vs personal)
- Investments (probe)
- Mortgage
- Life events
**Questions SKIPPED:** Schedule C, SE tax on distributions, childcare (no deps), EITC, education, student loans
**Expected Count:** 16-21 questions total

#### UC-112: MFJ, S-Corp Owner, High Income ($100k-$200k), 26-49, 2+ Kids
**Profile:** S-Corp owner with family, W-2 salary + distributions.
**Phase 2 Questions Asked:**
- W-2 from S-Corp
- Spouse employment/income
- K-1 income
- Distributions and basis
- QBI (W-2 wage limitation check)
- Retirement (401k through S-Corp, spousal IRA)
- Health insurance (2% shareholder)
- HSA
- Childcare expenses
- Child Tax Credit
- Estimated payments
- Investments
- Mortgage / homeowner
- Charitable
- Itemize vs. standard
- Life events
**Expected Count:** 18-23 questions total

#### UC-113: MFJ, S-Corp Owner, Very High Income ($200k+), 26-49, No Deps
**Profile:** Successful S-Corp, substantial distributions, complex planning.
**Phase 2 Questions Asked:**
- W-2 from S-Corp (reasonable comp analysis)
- K-1 distributions (basis tracking critical)
- QBI (phaseout check, SSTB determination, W-2 wage limit)
- Retirement (defined benefit plan through S-Corp?)
- Health insurance
- HSA
- Investments (NIIT)
- Mortgage
- Charitable (donor-advised fund)
- AMT check
- NIIT
- Estimated payments
- Itemize vs. standard
- State tax planning
- Life events
**Expected Count:** 18-24 questions total

#### UC-114: Single, C-Corp Owner, High Income ($100k-$200k), 26-49, No Deps
**Profile:** C-Corp owner -- salary + potential dividends (double taxation issue).
**Phase 1:** Filing Status(Single) -> Income($100k-$200k) -> State -> Dependents(0) -> Income Type(Business Owner - C-Corp)
**Phase 2 Questions Asked:**
- W-2 salary from C-Corp
- Dividends declared (qualified vs ordinary)
- Retained earnings strategy
- Entity-level tax paid (21% flat rate)
- Personal income vs. entity income separation
- Retirement (C-Corp can have generous plans)
- Health insurance (C-Corp provides as benefit -- not taxable)
- Investments
- Mortgage
- Estimated payments
- Life events
**Questions SKIPPED:** K-1 (C-Corp doesn't issue K-1), QBI (C-Corp income not eligible), SE tax, Schedule C
**Expected Count:** 15-20 questions total
**CRITICAL NOTE:** C-Corp income is NOT eligible for QBI deduction. Only pass-through entities qualify.

#### UC-115: MFJ, C-Corp Owner, Very High Income ($200k+), 50-64, No Deps
**Profile:** Mature C-Corp owner, succession planning territory.
**Phase 2 Questions Asked:**
- Salary and dividends
- Retained earnings
- Entity-level deductions
- Retirement (defined benefit, cash balance plan -- massive deductions)
- Health insurance (C-Corp benefit)
- HSA
- Investments (NIIT)
- Qualified Small Business Stock (Section 1202 -- huge exclusion)
- Charitable (stock donation)
- AMT / NIIT
- Estate planning considerations
- Estimated payments
- Life events
**Expected Count:** 17-22 questions total

#### UC-116: MFJ, Partnership (50/50), Mid Income ($50k-$100k), 26-49, 1 Young Child
**Profile:** 50/50 partner in a partnership, receives K-1.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(1, child <13) -> Income Type(Business Owner - Partnership)
**Phase 2 Questions Asked:**
- K-1 income (ordinary income, guaranteed payments)
- Partner allocation %
- At-risk and passive activity
- Basis in partnership
- Distributions
- QBI deduction
- Self-employment tax on guaranteed payments
- Estimated payments
- Childcare expenses
- Child Tax Credit
- Retirement (partner can have SEP-IRA)
- Health insurance
- Life events
**Expected Count:** 17-22 questions total

#### UC-117: Single, Partnership (minority), High Income, 26-49, No Deps
**Profile:** Minority partner (20%) in a larger partnership.
**Phase 2 Questions Asked:**
- K-1 details (all boxes)
- Allocation % and special allocations
- At-risk limitations
- Passive activity (material participation?)
- Basis tracking
- QBI (partner's share of W-2 wages and UBIA)
- Distributions vs income
- Estimated payments
- Retirement
- Investments (personal + K-1 investment income)
- Life events
**Expected Count:** 16-21 questions total

#### UC-118: MFJ, S-Corp + Rental Properties, Very High Income ($200k+), 50-64, No Deps
**Profile:** Business owner with real estate portfolio.
**Phase 2 Questions Asked:**
- S-Corp W-2 and K-1
- Rental property income (Schedule E)
- Rental expenses and depreciation
- Passive activity limitations (real estate professional status?)
- QBI on S-Corp
- QBI on rental (safe harbor test)
- Basis tracking (both)
- NIIT on rental and investment income
- Retirement (max out through S-Corp)
- Charitable strategies
- AMT
- Estimated payments
- Life events
**Expected Count:** 22-28 questions total

#### UC-119: Single, S-Corp Owner, Low Income ($25k-$50k), 26-49, No Deps
**Profile:** Small S-Corp, modest income, may question S-Corp benefit.
**Phase 2 Key Focus:** Is S-Corp still beneficial at this income? Reasonable salary vs. costs of S-Corp compliance.
**Expected Count:** 15-19 questions total

#### UC-120: MFJ, Multiple K-1s (S-Corp + Partnership), Very High Income, 26-49, 2+ Kids
**Profile:** Serial entrepreneur with multiple entities.
**Phase 2 Key Focus:** Aggregate K-1s, separate QBI calculations per entity, basis for each, children credits.
**Expected Count:** 22-28 questions total

#### UC-121: Single, S-Corp Owner, Very High Income ($200k+), Under 26, No Deps
**Profile:** Young successful tech founder.
**Phase 2 Key Focus:** QSBS (Section 1202) for stock gains, reasonable comp, entity optimization
**Expected Count:** 18-23 questions total

#### UC-122: MFJ, Partnership (real estate), High Income, 26-49, No Deps
**Profile:** Real estate partnership investor.
**Phase 2 Key Focus:** Schedule K-1 from real estate partnership, passive activity, at-risk, depreciation, Section 1231 gains
**Expected Count:** 18-23 questions total

#### UC-123: HOH, S-Corp Owner, Mid Income, 26-49, 1 Young Child
**Profile:** Single parent running S-Corp.
**Phase 2 Key Focus:** S-Corp health insurance (2% shareholder), childcare, CTC, QBI
**Expected Count:** 17-22 questions total

#### UC-124: MFJ, C-Corp Owner + W-2 Spouse, High Income, 26-49, 2+ Kids
**Profile:** One spouse owns C-Corp, other is W-2 employee.
**Phase 2 Key Focus:** Salary optimization from C-Corp, spouse W-2 withholding, combined tax planning
**Expected Count:** 18-23 questions total

#### UC-125: Single, Partnership (limited partner), Very High Income, 50-64, No Deps
**Profile:** Limited partner in investment partnership -- passive income.
**Phase 2 Key Focus:** Passive activity (limited partner = passive by default), NIIT, at-risk
**Expected Count:** 16-21 questions total

#### UC-126: MFJ, S-Corp Owner, Mid Income, 26-49, No Deps, Has Foreign Income
**Profile:** S-Corp with foreign clients or operations.
**Phase 2 Key Focus:** Foreign tax credits, Form 5471 (if >10% foreign corp), FBAR
**Expected Count:** 19-24 questions total

#### UC-127: Single, Multi-Entity (S-Corp + LLC), Very High Income, 26-49, No Deps
**Profile:** Multiple business entities, complex structure.
**Phase 2 Key Focus:** Separate QBI for each, inter-entity transactions, basis tracking
**Expected Count:** 22-28 questions total

#### UC-128: MFJ, Partnership (GP), Very High Income, 50-64, No Deps
**Profile:** General partner -- SE tax on partnership income.
**Phase 2 Key Focus:** GP = SE tax on all partnership income (unlike LP), guaranteed payments
**Expected Count:** 18-23 questions total

#### UC-129: MFJ, S-Corp Owner, Low Income, Under 26, 1 Young Child
**Profile:** Young entrepreneur with new S-Corp, modest income.
**Phase 2 Key Focus:** S-Corp minimum salary requirements, EITC eligibility check
**Expected Count:** 17-22 questions total

#### UC-130: Single, C-Corp + Partnership Interests, Very High Income, 26-49, No Deps
**Profile:** Complex entity structure investor.
**Phase 2 Key Focus:** C-Corp dividends + K-1 from partnerships, NIIT on everything
**Expected Count:** 20-26 questions total

#### UC-131 through UC-135: Additional Business Entity Combinations

#### UC-131: MFJ, S-Corp (SSTB - Consulting), Very High Income, 26-49, 2+ Kids
**Phase 2 Key Focus:** QBI phaseout for SSTB ($364k-$464k MFJ), reasonable comp scrutiny
**Expected Count:** 20-26 questions total

#### UC-132: Single, Partnership, Mid Income, 26-49, No Deps, Moved States
**Phase 2 Key Focus:** Multi-state K-1 allocation, nexus, composite returns
**Expected Count:** 18-23 questions total

#### UC-133: MFJ, S-Corp + C-Corp, Very High Income, 50-64, No Deps
**Phase 2 Key Focus:** Two entities, different tax treatments, combined planning
**Expected Count:** 22-28 questions total

#### UC-134: HOH, Partnership (minority), Low Income, 26-49, 2+ Kids
**Phase 2 Key Focus:** EITC with partnership income, passive limitations at low income
**Expected Count:** 17-22 questions total

#### UC-135: MFJ, Family LLC, High Income, 50-64, Older Children (employed in business)
**Phase 2 Key Focus:** Children on payroll (FICA exemption if under 18), income shifting, family limited partnership
**Expected Count:** 20-26 questions total

---

## GROUP 5: Retired Individuals

**Scope:** Primary income from retirement sources (SS, pension, IRA/401k distributions, investments).

### Group 5 Rules

**Critical validation rules (MUST ask):**
- Age (determines RMD, SS taxability, additional standard deduction)
- Social Security income amount
- Pension income (Form 1099-R)
- IRA/401k distributions (Form 1099-R, taxable vs. nontaxable)
- RMD compliance (age 73+)
- Medicare premiums / IRMAA
- Health insurance (Medicare Parts A, B, D, Medigap, Medicare Advantage)

**Mutual exclusion rules (NEVER ask):**
- Self-employment questions (unless has side business in retirement)
- W-2 withholding (unless still working part-time)
- Student loan interest (extremely unlikely)
- Education credits (unlikely unless lifelong learner)
- EITC (no earned income unless working)
- Childcare expenses (unless raising grandchildren)
- ACA marketplace (Medicare-eligible)

**Follow-up chains:**
- IF age >= 73 THEN MUST ask RMD taken
- IF age >= 70.5 THEN ask about QCD (Qualified Charitable Distribution)
- IF SS + other income > $25k single / $32k MFJ THEN SS is partially taxable
- IF SS + other income > $34k single / $44k MFJ THEN SS is 85% taxable
- IF MAGI > IRMAA thresholds THEN Medicare surcharge applies
- IF has_retirement_accounts AND age >= 73 THEN verify RMD satisfied from each account

---

#### UC-136: Single, Retired (Pension + SS), Low Income ($25k-$50k), 65+, No Deps
**Profile:** Standard retiree on pension and Social Security.
**Phase 1:** Filing Status(Single) -> Income($25k-$50k) -> State -> Dependents(0) -> Income Type(Retired)
**Phase 2 Questions Asked:**
- Age (65+ additional standard deduction $1,950)
- Social Security benefits amount (Form SSA-1099)
- Pension income (Form 1099-R)
- Tax withheld from pension/SS
- Other retirement account distributions
- RMD compliance (if 73+)
- Investment income (interest, dividends)
- Medicare premiums
- Medical expenses (potential itemized deduction)
- Charitable donations (QCD if 70.5+)
- State pension/SS treatment (varies by state)
- Life events
**Questions SKIPPED:** W-2, SE, business, K-1, childcare, EITC (no earned income), education, student loans, mortgage (probe), HSA (cannot contribute after Medicare), energy credits, foreign income, military, stock options, ACA marketplace (has Medicare)
**Expected Count:** 13-17 questions total

#### UC-137: MFJ, Retired (Pension + SS both spouses), Mid Income ($50k-$100k), 65+, No Deps
**Profile:** Retired married couple, both receiving SS and pensions.
**Phase 1:** Filing Status(MFJ) -> Income($50k-$100k) -> State -> Dependents(0) -> Income Type(Retired)
**Phase 2 Questions Asked:**
- Ages (both spouses)
- Social Security (both -- each gets SSA-1099)
- Pensions (both -- each may have 1099-R)
- Tax withholding from all sources
- IRA/401k distributions
- RMDs (each spouse separately if 73+)
- Investment income
- Medicare premiums (both)
- Medical expenses
- Charitable (QCD strategy for both if 70.5+)
- Mortgage (may be paid off)
- Property taxes
- State treatment
- Life events
**Questions SKIPPED:** W-2, SE, business, K-1, childcare, EITC, education, student loans, HSA, energy credits, foreign income, military, stock options, ACA
**Expected Count:** 15-20 questions total

#### UC-138: Single, Retired (IRA/401k heavy), High Income ($100k-$200k), 65+, No Deps
**Profile:** Retiree with large retirement accounts, significant RMDs.
**Phase 2 Questions Asked:**
- Age
- SS income
- IRA/401k distributions (traditional -- fully taxable)
- Roth distributions (tax-free check)
- RMD amounts and compliance
- Withholding from distributions
- Investment income (dividends, capital gains)
- IRMAA surcharge (income > $103k single)
- Medical expenses
- Charitable (QCD to reduce RMD AGI)
- Mortgage / property taxes
- Itemize vs. standard
- Estimated payments
- Life events
**Expected Count:** 16-21 questions total

#### UC-139: MFJ, Retired, Very High Income ($200k+), 65+, No Deps
**Profile:** Wealthy retirees, large RMDs, IRMAA, possibly NIIT.
**Phase 2 Questions Asked:**
- Ages
- SS (both -- 85% taxable at this income)
- Pensions/annuities
- IRA/401k distributions (large RMDs)
- RMD compliance (each account)
- Roth conversions (strategy discussion)
- Investment income (NIIT at $250k MFJ)
- Capital gains from portfolio rebalancing
- IRMAA surcharges (both)
- Charitable (QCD, donor-advised fund, appreciated stock)
- Mortgage / property taxes
- Itemize vs. standard
- AMT check
- NIIT
- Estimated payments
- Life events
**Expected Count:** 18-24 questions total

#### UC-140: QSS, Retired (Pension + SS), Mid Income, 65+, 1 Young Child (grandchild)
**Profile:** Recently widowed retiree raising grandchild.
**Phase 2 Questions Asked:**
- Age
- Year of spouse's death (QSS 2-year limit)
- SS (own + survivor benefits)
- Pension
- Child Tax Credit for grandchild
- Childcare (if working or looking for work)
- RMDs
- Medical expenses
- Life events (bereavement)
**Expected Count:** 14-18 questions total

#### UC-141: Single, Retired This Year (partial W-2 + partial retirement), Mid Income, 50-64, No Deps
**Profile:** Mid-year retiree, split income between W-2 and retirement sources.
**Phase 2 Questions Asked:**
- W-2 income (partial year)
- W-2 withholding
- Retirement start date
- Pension or annuity start
- Lump-sum distribution? (special tax treatment)
- 401k rollover to IRA?
- COBRA / health insurance gap
- SS (if started -- reduced before full retirement age)
- Retirement contributions (before retirement)
- HSA (before Medicare enrollment)
- Severance pay
- Life events (retirement!)
**Expected Count:** 16-21 questions total

#### UC-142: MFJ, One Retired + One Working, High Income ($100k-$200k), 65+ and 50-64, No Deps
**Profile:** One spouse retired, other still working.
**Phase 2 Questions Asked:**
- Working spouse: W-2, withholding, retirement contributions
- Retired spouse: SS, pension, distributions
- Combined income effects on SS taxability
- Retirement contributions (working spouse only)
- Health insurance (working spouse's employer plan vs. Medicare)
- IRMAA check
- Investments
- Mortgage
- Charitable
- Life events
**Expected Count:** 16-21 questions total

#### UC-143: Single, Retired, Very Low Income (<$25k), 65+, No Deps
**Profile:** Low-income retiree, possibly only SS.
**Phase 2 Questions Asked:**
- Age
- SS income (may not be taxable if only income source)
- Any pension?
- Any other income?
- Additional standard deduction (65+)
- Property tax credit/rebate (state-specific)
- Medical expenses
- Medicare premiums
- Filing requirement check (may not need to file!)
**Questions SKIPPED:** Almost everything -- very simple return
**Expected Count:** 8-12 questions total
**CRITICAL NOTE:** If only SS income and under $25,000 single, may not need to file at all.

#### UC-144: MFJ, Retired, Low Income ($25k-$50k), 65+, Elderly/Disabled Relative
**Profile:** Retired couple supporting disabled family member.
**Phase 2 Questions Asked:**
- Ages (both spouses + dependent)
- SS (both)
- Pension income
- Dependent's income test
- Credit for Elderly or Disabled (Schedule R)
- Medical expenses for dependent
- Credit for Other Dependents
- Additional standard deduction (65+, possibly blind)
- Life events
**Expected Count:** 13-17 questions total

#### UC-145: Single, Retired + Rental Income, High Income, 65+, No Deps
**Profile:** Retiree with rental properties supplementing retirement.
**Phase 2 Questions Asked:**
- SS, pension, distributions
- RMDs
- Rental property income (Schedule E)
- Rental expenses and depreciation
- Passive activity (active participation?)
- NIIT on rental income (if high income)
- Investments
- Charitable (QCD)
- IRMAA
- Estimated payments
- Life events
**Expected Count:** 17-22 questions total

#### UC-146 through UC-160: Additional Retired Combinations

#### UC-146: MFJ, Retired, Mid Income, 65+, No Deps, Sold Home This Year
**Phase 2 Key Focus:** Section 121 exclusion ($500k MFJ), capital gains, downsizing
**Expected Count:** 16-21 questions total

#### UC-147: Single, Retired, Mid Income, 65+, No Deps, Inherited IRA
**Phase 2 Key Focus:** Inherited IRA rules (10-year rule for non-spouse), annual distribution requirements
**Expected Count:** 15-20 questions total

#### UC-148: MFJ, Retired + Part-Time W-2, Low Income, 65+, No Deps
**Phase 2 Key Focus:** W-2 withholding, SS benefit recalculation, earned income effects
**Expected Count:** 14-18 questions total

#### UC-149: Single, Retired, High Income, 65+, No Deps, Has Annuity
**Phase 2 Key Focus:** Annuity taxation (exclusion ratio), Form 1099-R code mapping
**Expected Count:** 15-20 questions total

#### UC-150: MFJ, Retired, Very High Income, 65+, No Deps, Roth Conversion Strategy
**Phase 2 Key Focus:** Roth conversion analysis, tax bracket filling, IRMAA impact of conversion
**Expected Count:** 17-22 questions total

#### UC-151: Single, Retired, Low Income, 65+, 1 Young Child (great-grandchild in custody)
**Phase 2 Key Focus:** CTC, dependency tests, EITC (no earned income = no EITC)
**Expected Count:** 13-17 questions total

#### UC-152: HOH, Retired, Mid Income, 65+, Elderly Relative
**Phase 2 Key Focus:** Two elderly people, medical expenses for both, caregiver credits
**Expected Count:** 14-18 questions total

#### UC-153: MFJ, Retired, Mid Income, 65+, Charitable Focus (large donations)
**Phase 2 Key Focus:** QCD strategy (reduces RMD and AGI), bunching strategy, donor-advised fund
**Expected Count:** 15-20 questions total

#### UC-154: Single, Retired + Small Business Income, Mid Income, 65+, No Deps
**Phase 2 Key Focus:** Hybrid -- retirement income + Schedule C, SE tax after 65 (still applies)
**Expected Count:** 17-22 questions total

#### UC-155: MFJ, Retired, High Income, 65+, No Deps, Sold Investment Property
**Phase 2 Key Focus:** Depreciation recapture, Section 1231 gain, capital gains, installment sale
**Expected Count:** 18-23 questions total

#### UC-156: Single, Retired, Very Low Income, 65+, No Deps, Only SS Income
**Phase 2 Key Focus:** Filing requirement analysis -- likely does NOT need to file
**Expected Count:** 6-8 questions total

#### UC-157: MFJ, Retired, Mid Income, 65+, No Deps, Foreign Pension
**Phase 2 Key Focus:** Foreign pension taxation, tax treaty benefits, FBAR on foreign accounts
**Expected Count:** 16-21 questions total

#### UC-158: Single, Retired Military (pension), Mid Income, 65+, No Deps
**Phase 2 Key Focus:** Military pension treatment (taxable), state exclusions vary, VA disability (tax-free)
**Expected Count:** 14-18 questions total

#### UC-159: MFJ, Retired, Low Income, 65+, No Deps, One Spouse Disabled
**Phase 2 Key Focus:** Credit for Elderly or Disabled, SSDI income, medical expenses
**Expected Count:** 13-17 questions total

#### UC-160: Single, Retired, High Income, 65+, No Deps, Early Distribution Penalty
**Profile:** Person 65+ who took early distribution when 59 (penalty year still open or amended).
**Phase 2 Key Focus:** 10% early withdrawal penalty exceptions, Form 5329
**Expected Count:** 15-20 questions total

---

## GROUP 6: Investors (Primary Income)

**Scope:** Primary income from investments -- capital gains, dividends, interest, options trading.

### Group 6 Rules

**Critical validation rules (MUST ask):**
- Types of investment income (dividends, capital gains, interest, options)
- Short-term vs long-term capital gains
- Wash sale tracking
- Cost basis method
- Qualified vs ordinary dividends
- Net Investment Income Tax (NIIT)
- AMT exposure (especially ISO exercises)
- Capital loss carryforward

**Mutual exclusion rules (NEVER ask):**
- W-2/employer questions (unless also employed)
- Self-employment tax on investment income (investment income is NOT SE income)
- Schedule C (investment income goes on Schedule D / Form 8949)
- EITC (investment income > $11,600 disqualifies)

**Follow-up chains:**
- IF investment_income > NIIT threshold THEN calculate NIIT (3.8%)
- IF has_wash_sales THEN ask about adjustment amounts
- IF has_capital_losses > $3000 THEN ask about carryforward
- IF has_ISO_exercises THEN calculate AMT preference items
- IF has_qualified_dividends THEN apply preferential rate
- IF total_investments > $50k foreign THEN ask FATCA

---

#### UC-161: Single, Investor (dividends + cap gains), High Income ($100k-$200k), 26-49, No Deps
**Profile:** Active investor, portfolio generates significant income.
**Phase 1:** Filing Status(Single) -> Income($100k-$200k) -> State -> Dependents(0) -> Income Type(Investor)
**Phase 2 Questions Asked:**
- Dividend income (qualified vs ordinary)
- Capital gains (short-term vs long-term)
- Capital losses and carryforward
- Cost basis method
- Wash sales
- Interest income (taxable + tax-exempt)
- Investment expenses
- NIIT (threshold $200k single)
- AMT check
- Estimated payments
- Retirement (IRA, taxable vs tax-advantaged allocation)
- Mortgage
- Charitable (appreciated stock donation strategy)
- Life events
**Questions SKIPPED:** W-2, SE, business, K-1 (unless fund), childcare, EITC (investment income too high), education, student loans, energy credits, military, ACA
**Expected Count:** 16-21 questions total

#### UC-162: MFJ, Investor, Very High Income ($200k+), 50-64, No Deps
**Profile:** Wealthy couple living off investment portfolio.
**Phase 2 Questions Asked:**
- Dividend income (both accounts)
- Capital gains/losses (detailed -- Form 8949)
- Wash sales
- Bond interest (municipal vs. taxable)
- Real estate investment trust (REIT) dividends
- Master limited partnership (MLP) income
- NIIT (3.8% on investment income above $250k MFJ)
- AMT
- Tax-loss harvesting opportunities
- Estimated payments
- Retirement accounts (Roth conversion strategy)
- Charitable (appreciated stock, donor-advised fund)
- Mortgage
- Property taxes
- Itemize vs. standard
- Life events
**Expected Count:** 18-24 questions total

#### UC-163: Single, Investor (day trader), Very High Income ($200k+), 26-49, No Deps
**Profile:** Full-time day trader -- special tax status considerations.
**Phase 2 Questions Asked:**
- Trader vs investor status (Section 475 election?)
- Number of trades
- Short-term gains (ordinary income rate for traders)
- Wash sale volume
- Trading expenses (platform fees, data subscriptions)
- Home office for trading
- Mark-to-market election
- NIIT
- AMT
- Estimated payments
- Retirement
- Life events
**Expected Count:** 16-21 questions total

#### UC-164: MFJ, Investor + W-2, High Income, 26-49, 2+ Kids
**Profile:** W-2 worker with substantial investment portfolio.
**Phase 2 Questions Asked:**
- W-2 withholding
- Investment income types
- Capital gains/losses
- Wash sales
- NIIT check
- AMT check
- Childcare
- Child Tax Credit
- Retirement
- HSA
- Mortgage
- Charitable
- Itemize vs. standard
- Life events
**Expected Count:** 17-22 questions total

#### UC-165: Single, Investor (stock options ISO/RSU), High Income, Under 26, No Deps
**Profile:** Tech worker with significant equity compensation.
**Phase 2 Questions Asked:**
- ISO exercises (AMT preference item -- CRITICAL)
- ISO holding period (qualifying vs disqualifying disposition)
- RSU vesting income (already on W-2)
- ESPP purchases and sales
- AMT calculation (Form 6251)
- AMT credit carryforward (Form 8801)
- Regular capital gains/losses
- Tax withholding adequacy
- Retirement
- Student loans
- Life events
**Expected Count:** 15-20 questions total

#### UC-166: MFJ, Investor (rental + stocks), Very High Income ($200k+), 50-64, No Deps
**Profile:** Diversified investor with real estate and securities.
**Phase 2 Questions Asked:**
- Rental income (all properties)
- Rental expenses, depreciation
- Passive activity (real estate professional status?)
- Capital gains from stock sales
- Dividends
- NIIT on all investment income
- AMT
- Estimated payments
- Retirement accounts
- Charitable strategies
- Itemize vs. standard
- Life events
**Expected Count:** 19-25 questions total

#### UC-167: Single, Investor (crypto-heavy), Mid Income, Under 26, No Deps
**Profile:** Young crypto investor with significant trading activity.
**Phase 2 Questions Asked:**
- Crypto sales/trades (each is taxable event)
- DeFi income (staking, yield farming -- ordinary income)
- NFT sales
- Airdrops (ordinary income at FMV)
- Mining income (if applicable -- SE income)
- Cost basis tracking method (FIFO, LIFO, specific ID)
- Wash sales (crypto -- currently unclear enforcement)
- Capital losses and $3k limit
- Education expenses
- Student loans
- Life events
**Expected Count:** 14-18 questions total

#### UC-168: MFJ, Investor (bonds/fixed income), Mid Income, 65+, No Deps
**Profile:** Conservative retired investors, bond-heavy portfolio.
**Phase 2 Questions Asked:**
- Interest income (taxable bonds)
- Municipal bond income (federal tax-free, may be state taxable)
- Treasury bond income (state tax-free)
- CD interest
- Series I/EE savings bond income
- Social Security
- Pension
- RMDs
- Medicare / IRMAA
- Charitable
- Life events
**Expected Count:** 14-18 questions total

#### UC-169 through UC-180: Additional Investor Combinations

#### UC-169: Single, Investor (options trader), Very High Income, 26-49, No Deps
**Phase 2 Key Focus:** Section 1256 contracts (60/40 rule), options premium income, straddles
**Expected Count:** 17-22 questions total

#### UC-170: MFJ, Investor + S-Corp, Very High Income, 26-49, 2+ Kids
**Phase 2 Key Focus:** Combined K-1 + investment income, NIIT on investment portion only
**Expected Count:** 22-28 questions total

#### UC-171: Single, Investor (inherited portfolio), High Income, 26-49, No Deps
**Phase 2 Key Focus:** Stepped-up basis on inherited assets, holding period (always long-term for inherited)
**Expected Count:** 16-21 questions total

#### UC-172: MFJ, Investor (ESOP distribution), Very High Income, 50-64, No Deps
**Phase 2 Key Focus:** Net Unrealized Appreciation (NUA) strategy, lump-sum vs rollover
**Expected Count:** 17-22 questions total

#### UC-173: Single, Investor (collectibles), High Income, 26-49, No Deps
**Phase 2 Key Focus:** Collectibles taxed at 28% max rate, not standard capital gains rates
**Expected Count:** 15-20 questions total

#### UC-174: MFJ, Investor (private equity K-1s), Very High Income, 26-49, No Deps
**Phase 2 Key Focus:** Fund K-1s (multiple), carried interest, management fees, UBTI
**Expected Count:** 19-25 questions total

#### UC-175: Single, Investor (REIT heavy), Mid Income, 50-64, No Deps
**Phase 2 Key Focus:** REIT dividends (ordinary vs capital gain), QBI deduction on REIT income
**Expected Count:** 15-20 questions total

#### UC-176: MFJ, Investor + Rental Empire, Very High Income, 50-64, No Deps
**Phase 2 Key Focus:** Real estate professional status (750 hours), material participation, PAL grouping
**Expected Count:** 22-28 questions total

#### UC-177: Single, Investor (international stocks), High Income, 26-49, No Deps
**Phase 2 Key Focus:** Foreign tax credit (Form 1116), foreign withholding, PFIC rules
**Expected Count:** 17-22 questions total

#### UC-178: MFJ, Investor (tax-loss harvesting focused), High Income, 26-49, No Deps
**Phase 2 Key Focus:** Tax-loss harvesting pairs, wash sale tracking, substantially identical securities
**Expected Count:** 16-21 questions total

#### UC-179: Single, Investor (angel investor/startup), Very High Income, 26-49, No Deps
**Phase 2 Key Focus:** Section 1202 QSBS exclusion (up to $10M or 10x basis), Section 1244 losses
**Expected Count:** 17-22 questions total

#### UC-180: MFJ, Investor (trust distributions), Very High Income, 65+, No Deps
**Phase 2 Key Focus:** Trust K-1 income, DNI, trust vs estate distributions, throwback rules
**Expected Count:** 18-24 questions total

---

## GROUP 7: Military

**Scope:** Active duty, reserve, or recently separated military personnel.

### Group 7 Rules

**Critical validation rules (MUST ask):**
- Active duty vs. reserve vs. veteran
- Combat zone deployment dates (if applicable)
- State of legal residence (domicile -- may differ from station)
- Military pay types (base, BAH, BAS, hazardous duty, combat)
- TSP contributions
- Moving expenses (military exemption still valid!)

**Mutual exclusion rules (NEVER ask):**
- Self-employment tax on military pay
- Combat zone pay as taxable income (it's excluded)
- ACA questions (TRICARE covers)
- State tax for combat zone income

**Follow-up chains:**
- IF active_duty = yes AND deployed THEN ask combat_zone
- IF combat_zone = yes THEN exclude combat pay from income
- IF combat_zone = yes THEN filing deadline extension (180 days after leaving zone)
- IF pcs_move = yes THEN deduct moving expenses (military only post-2018)
- IF reserve_duty = yes THEN ask travel > 100 miles (above-the-line deduction)
- IF stationed_overseas THEN ask Foreign Housing Exclusion

---

#### UC-181: Single, Military (Active), Low Income ($25k-$50k), Under 26, No Deps
**Profile:** Junior enlisted, first or second enlistment.
**Phase 1:** Filing Status(Single) -> Income($25k-$50k) -> State -> Dependents(0) -> Income Type(Military)
**Phase 2 Questions Asked:**
- Military branch and rank
- Active duty or reserve
- Combat zone deployment?
- Combat pay exclusion election (can include in earned income for EITC!)
- BAH/BAS (tax-free -- not reported on W-2)
- TSP contributions
- State of legal residence (SLA -- may be different from duty station)
- SCRA protections (state tax)
- Student loans (military repayment programs)
- Education (GI Bill, tuition assistance)
- TRICARE (no health insurance questions needed)
- Life events (PCS move?)
**Questions SKIPPED:** SE, business, K-1, rental, investments (probe), childcare, mortgage, energy credits, ACA, stock options, gambling, alimony, household employee
**Expected Count:** 13-17 questions total

#### UC-182: MFJ, Military (Active) + Spouse W-2, Mid Income ($50k-$100k), 26-49, 2+ Kids
**Profile:** Military family with dependent children, spouse works.
**Phase 2 Questions Asked:**
- Military pay details
- Combat zone?
- BAH/BAS
- TSP contributions
- Spouse W-2 and withholding
- State of legal residence (MSRRA for spouse)
- Childcare (on-base vs. off-base)
- Child Tax Credit
- EITC (combat pay election for EITC)
- Spouse education (MyCAA)
- Life events (PCS move, deployment)
- Moving expenses (military exempt from 2018 suspension!)
**Questions SKIPPED:** SE, business (unless spouse), K-1, rental, ACA, stock options, gambling, alimony, household employee
**Expected Count:** 15-20 questions total

#### UC-183: Single, Military (Active), Mid Income, Under 26, No Deps, Combat Zone
**Profile:** Deployed service member, combat zone tax exclusion.
**Phase 2 Questions Asked:**
- Combat zone location and dates
- Combat pay exclusion amount
- Deadline extension (180 days after leaving zone + days remaining)
- BAH/BAS
- TSP (combat zone contributions to Roth TSP -- powerful strategy)
- Savings Deposit Program (SDP -- tax-free interest)
- State tax treatment
- Education (GI Bill)
- Life events
**Questions SKIPPED:** Everything not military-related
**Expected Count:** 11-15 questions total
**CRITICAL NOTE:** Combat zone income is 100% excluded from federal tax for enlisted. Officers have monthly cap.

#### UC-184: MFJ, Military (Reserve), Mid Income, 26-49, 1 Young Child
**Profile:** Reservist with civilian job plus drill pay.
**Phase 2 Questions Asked:**
- Civilian W-2 income and withholding
- Reserve/Guard drill pay (W-2 from DFAS)
- Travel > 100 miles for drill (above-the-line deduction)
- Uniform expenses (if not reimbursed)
- TSP contributions
- Civilian retirement (401k)
- Childcare
- Child Tax Credit
- Life events (deployment activation?)
**Expected Count:** 14-18 questions total

#### UC-185: MFJ, Military (Active), Low Income ($25k-$50k), Under 26, 1 Young Child
**Profile:** Young military family, E-3/E-4 with baby.
**Phase 2 Key Focus:** BAH (tax-free), EITC with combat pay election, CTC, childcare
**Expected Count:** 14-18 questions total

#### UC-186: Single, Military (Active), High Income ($100k-$200k), 26-49, No Deps
**Profile:** Senior officer or senior NCO, significant pay.
**Phase 2 Key Focus:** TSP max ($23,000), special pay (flight, dive, hazardous), state domicile optimization
**Expected Count:** 14-18 questions total

#### UC-187: MFJ, Military + Spouse Business, Mid Income, 26-49, 2+ Kids
**Profile:** Military member with entrepreneur spouse.
**Phase 2 Key Focus:** Spouse Schedule C, military BAH, combined tax planning, childcare
**Expected Count:** 18-23 questions total

#### UC-188: Single, Military, Low Income, Under 26, No Deps, Moved States (PCS)
**Profile:** PCS move during tax year.
**Phase 2 Key Focus:** Moving expense deduction (military only!), dual-state filing, SLA vs. duty station
**Expected Count:** 13-17 questions total

#### UC-189: MFJ, Military (Active), Mid Income, 26-49, 2+ Kids, Overseas Station
**Profile:** Military family stationed overseas (Germany, Japan, etc.).
**Phase 2 Key Focus:** Foreign Housing Exclusion, SOFA treaty, overseas BAH, school expenses
**Expected Count:** 16-21 questions total

#### UC-190 through UC-195: Additional Military Combinations

#### UC-190: Single, Veteran (recently separated), Mid Income, 26-49, No Deps
**Phase 2 Key Focus:** Transition pay, TSP rollover, VA disability (tax-free), GI Bill usage
**Expected Count:** 13-17 questions total

#### UC-191: MFJ, Military + Rental Property (near base), Mid Income, 26-49, 1 Kid
**Phase 2 Key Focus:** Rental of prior home after PCS, Schedule E, passive activity
**Expected Count:** 17-22 questions total

#### UC-192: Single, Military (Active), Low Income, Under 26, No Deps, Combat Zone + Student Loans
**Phase 2 Key Focus:** Combat zone exclusion, student loan interest while deployed, SCRA rate cap
**Expected Count:** 12-16 questions total

#### UC-193: MFJ, Guard/Reserve, Low Income, 26-49, 2+ Kids, Activated for Deployment
**Phase 2 Key Focus:** Activation pay differential, employer supplement pay, deployment tax benefits
**Expected Count:** 15-20 questions total

#### UC-194: HOH, Veteran, Mid Income, 26-49, 1 Young Child, VA Disability
**Phase 2 Key Focus:** VA disability is TAX-FREE, does not count as income, does not affect other credits
**Expected Count:** 13-17 questions total

#### UC-195: MFJ, Military (Dual Military -- both active), High Income, 26-49, 1 Kid
**Phase 2 Key Focus:** Two military W-2s, two TSPs, two states of legal residence potentially, childcare during dual deployment
**Expected Count:** 16-21 questions total

---

## GROUP 8: Life Event Scenarios

**Scope:** Any income type crossed with significant life events that change tax treatment.

### Group 8 Rules

**Critical validation rules (MUST ask per event):**

| Life Event | Must Ask |
|-----------|----------|
| Got Married | Date of marriage, prior year filing status, spouse SSN, MFJ vs MFS comparison |
| Got Divorced | Date finalized, custody agreement, alimony (pre/post 2019), who claims kids |
| Had Baby | SSN obtained? (need for CTC), childcare plans, name/DOB |
| Bought Home | Purchase date, mortgage amount, points paid, property taxes |
| Sold Home | Sale date, sale price, Section 121 exclusion, lived 2 of 5 years? |
| Changed Jobs | Dates, multiple W-2s, retirement plan rollover, relocation expenses |
| Lost Job | Unemployment income (taxable!), severance, health insurance gap |
| Started Business | Business type, startup costs, entity election, EIN |
| Moved States | Dates, dual-state filing, income allocation |
| Inherited Money | Relationship to deceased, inherited IRA?, stepped-up basis, estate tax |
| Became Disabled | SSDI, employer disability plan, medical expenses |
| Retired This Year | See Group 5 -- hybrid year |

---

#### UC-196: MFJ, W-2, Mid Income, 26-49, No Deps -> Got Married This Year
**Profile:** Newlyweds, first joint return, need MFJ vs MFS comparison.
**Phase 2 Questions Asked:**
- Marriage date
- Prior filing status (both)
- MFJ vs MFS comparison (CRITICAL)
- Spouse income and W-2
- Combined withholding adequacy
- Student loans (income-driven repayment -- may favor MFS)
- Retirement contributions (both)
- Name change documentation
- Combined investment accounts
- Life events (wedding expenses are NOT deductible)
**Expected Count:** 14-18 questions total

#### UC-197: Single (was MFJ), W-2, Mid Income, 26-49, 2 Kids -> Got Divorced This Year
**Profile:** Newly divorced parent, custody arrangement affects everything.
**Phase 2 Questions Asked:**
- Divorce finalization date
- Custody agreement (who claims children)
- Form 8332 (release of claim to exemption)
- Alimony (pre-2019 divorce = deductible, post-2018 = not)
- Child support (not taxable/deductible)
- Filing status determination (Single vs HOH)
- Property settlement (generally not taxable)
- QDRO (retirement split)
- Childcare expenses
- Child Tax Credit
- ACA (lost spouse's coverage?)
- Life events
**Expected Count:** 16-21 questions total

#### UC-198: MFJ, W-2, Mid Income, 26-49, Had Baby This Year (now 1 child)
**Profile:** New parents, first child, new credits unlocked.
**Phase 2 Questions Asked:**
- Baby's SSN (CRITICAL -- no CTC without it)
- Baby's DOB
- Child Tax Credit ($2,000)
- Childcare expenses (if returning to work)
- Dependent Care FSA (mid-year enrollment)
- HOH vs MFJ consideration
- Medical expenses (delivery costs)
- Health insurance (add baby to plan)
- Life events
**Expected Count:** 13-17 questions total

#### UC-199: MFJ, W-2, High Income, 26-49, 2 Kids -> Bought Home This Year
**Profile:** First-time homebuyers, new deductions.
**Phase 2 Questions Asked:**
- Purchase date and price
- Mortgage amount and interest rate
- Points paid at closing (deductible in year 1 for purchase)
- Property taxes (prorated from purchase date)
- First-time homebuyer? (state credits vary)
- Itemize vs. standard (likely tips to itemize now)
- Mortgage insurance premium (if PMI)
- Home office potential
- Energy efficiency improvements planned
- Childcare, CTC (standard family questions)
- Life events
**Expected Count:** 16-21 questions total

#### UC-200: MFJ, W-2, High Income, 50-64, No Deps -> Sold Home This Year
**Profile:** Downsizing, potentially large gain.
**Phase 2 Questions Asked:**
- Sale date and price
- Original purchase price and improvements (basis)
- Lived in home 2 of last 5 years? (Section 121 requirement)
- Section 121 exclusion ($500k MFJ, $250k single)
- Gain exceeding exclusion?
- Used home for business (home office % recapture)
- Rental use history (partial exclusion)
- New home purchased?
- Moving costs (not deductible post-2018 unless military)
- Life events
**Expected Count:** 15-20 questions total

#### UC-201: Single, W-2, Mid Income, 26-49, No Deps -> Changed Jobs This Year
**Profile:** Job changer, possible withholding gap, retirement rollover.
**Phase 2 Questions Asked:**
- Number of W-2s
- Withholding from each (under-withholding risk in transition)
- Retirement plan rollover (direct vs indirect -- 60-day rule)
- Severance from old job
- Sign-on bonus from new
- Stock option vesting acceleration
- Relocation benefits (taxable if employer-paid)
- Gap in health insurance (COBRA)
- Moving expenses (not deductible unless military)
- Life events
**Expected Count:** 14-18 questions total

#### UC-202: Single, W-2, Low Income, 26-49, 2 Kids -> Lost Job This Year
**Profile:** Laid-off worker, unemployment income, potential hardship.
**Phase 2 Questions Asked:**
- W-2 income (partial year)
- Unemployment compensation (TAXABLE -- Form 1099-G)
- Severance pay (on W-2 or separate)
- Health insurance (COBRA, ACA marketplace)
- ACA Premium Tax Credit
- Early retirement distribution? (10% penalty unless exception)
- EITC (unemployment is NOT earned income for EITC)
- Child Tax Credit (still available)
- Childcare
- Life events
**Expected Count:** 14-18 questions total
**CRITICAL NOTE:** Unemployment income is taxable and often has NO withholding. Surprise tax bill risk.

#### UC-203: Single, W-2, Mid Income, 26-49, No Deps -> Started Business This Year
**Profile:** Side business or left job to start business.
**Phase 2 Questions Asked:**
- Business type and entity
- Startup costs (up to $5k deductible, rest amortized)
- Organizational costs (if LLC/Corp)
- EIN obtained?
- First-year income and expenses
- Home office
- Vehicle use
- Estimated payments
- QBI deduction
- Health insurance (SE deduction or marketplace)
- Equipment purchased (Section 179)
- Business insurance
- Life events
**Expected Count:** 17-22 questions total

#### UC-204: MFJ, W-2, Mid Income, 26-49, No Deps -> Moved States This Year
**Profile:** Relocated for work, dual-state tax return.
**Phase 2 Questions Asked:**
- Old state and new state
- Move date
- Income earned in each state
- Days worked in each state
- Part-year resident returns needed
- Relocation expenses (employer-paid = taxable)
- New home purchase?
- Sold old home?
- State-specific credits/deductions
- Driver's license / voter registration (domicile proof)
- Life events
**Expected Count:** 15-20 questions total

#### UC-205: Single, W-2, High Income, 26-49, No Deps -> Inherited Money This Year
**Profile:** Received inheritance, possibly including investment accounts.
**Phase 2 Questions Asked:**
- Relationship to deceased
- Inheritance type (cash, property, retirement accounts, business)
- Inherited IRA? (10-year distribution rule for non-spouse)
- Stepped-up basis on inherited assets
- Estate tax paid (deduction available)
- Income in Respect of a Decedent (IRD)
- Probate / executor fees
- Trust distributions (K-1)
- State inheritance tax (varies by state)
- Life events
**Expected Count:** 15-20 questions total
**CRITICAL NOTE:** Inheritance itself is NOT income. But inherited IRA distributions ARE. Stepped-up basis resets capital gains.

#### UC-206: MFJ, W-2, Mid Income, 26-49, No Deps -> Became Disabled This Year
**Profile:** Worker who became disabled mid-year.
**Phase 2 Questions Asked:**
- W-2 income (partial year before disability)
- Disability income source (employer plan, SSDI, private)
- Employer disability plan (pre-tax premiums = taxable benefits)
- SSDI application status
- Medical expenses (potentially massive -- itemize?)
- Health insurance (COBRA, disability continuation)
- Credit for Elderly or Disabled (if eligible)
- Retirement account access (disability exception to 10% penalty)
- Life events
**Expected Count:** 14-18 questions total

#### UC-207: MFJ, W-2, High Income, 50-64, No Deps -> Retired This Year
**Profile:** Mid-year retirement, complex split year.
**Phase 2 Questions Asked:**
- Last day of work
- W-2 income (partial year)
- W-2 withholding
- Pension start date and amount
- Lump sum distribution election?
- 401k rollover to IRA?
- Social Security (if started)
- COBRA / Medicare enrollment
- Retirement contributions (before retirement)
- HSA (before Medicare)
- Severance or buyout
- Estimated payments (now needed?)
- Life events
**Expected Count:** 17-22 questions total

#### UC-208 through UC-225: Additional Life Event Combinations

#### UC-208: MFJ, Self-Employed, High Income, 26-49, No Deps -> Got Married + Bought Home
**Profile:** Double life event -- marriage and home purchase same year.
**Phase 2 Key Focus:** First joint return, new mortgage deduction, combined income effects
**Expected Count:** 19-24 questions total

#### UC-209: HOH -> Single, W-2, Mid Income, 26-49, Older Child Aged Out
**Profile:** Child turned 24 or graduated -- lost dependent status.
**Phase 2 Key Focus:** Filing status change (HOH -> Single), lost CTC, higher tax bracket
**Expected Count:** 12-16 questions total

#### UC-210: MFJ, S-Corp, High Income, 26-49, 2 Kids -> Started Second Business
**Profile:** Serial entrepreneur adding another entity.
**Phase 2 Key Focus:** New entity setup, combined QBI, allocation strategies
**Expected Count:** 22-28 questions total

#### UC-211: Single, W-2, Low Income, Under 26, No Deps -> Had Baby (now HOH with 1 child)
**Profile:** Young single person becomes parent -- filing status and credits transform.
**Phase 2 Key Focus:** Filing status change to HOH, CTC, EITC, childcare
**Expected Count:** 14-18 questions total

#### UC-212: MFJ, W-2, Mid Income, 26-49, 2 Kids -> Divorced + Moved States
**Profile:** Triple disruption -- divorce, custody split, relocation.
**Phase 2 Key Focus:** Filing status, who claims kids, dual-state, alimony, property settlement
**Expected Count:** 18-23 questions total

#### UC-213: Single, W-2 + Investor, Very High Income, 26-49, No Deps -> Sold Home at Loss
**Profile:** Sold personal residence at a loss.
**Phase 2 Key Focus:** Personal residence loss is NOT deductible (unlike investment property)
**Expected Count:** 15-20 questions total

#### UC-214: MFJ, Retired, Mid Income, 65+, No Deps -> Spouse Died This Year
**Profile:** Year of spouse's death -- still file MFJ for death year.
**Phase 2 Key Focus:** Can file MFJ for year of death, then QSS for 2 years if qualifying child, then Single
**Expected Count:** 15-20 questions total

#### UC-215: Single, W-2, Mid Income, Under 26, No Deps -> Got Married + Had Baby
**Profile:** Life milestones stacking -- marriage and baby same year.
**Phase 2 Key Focus:** MFJ, new dependent CTC, childcare, health insurance changes
**Expected Count:** 16-21 questions total

#### UC-216: MFJ, Self-Employed, Mid Income, 26-49, No Deps -> Lost Business (closure)
**Profile:** Business failed and closed during the year.
**Phase 2 Key Focus:** Final Schedule C, net operating loss, asset disposition, debt cancellation (Form 982?)
**Expected Count:** 16-21 questions total

#### UC-217: Single, W-2, High Income, 26-49, No Deps -> Inherited IRA from Parent
**Profile:** Non-spouse inherited IRA -- 10-year rule applies.
**Phase 2 Key Focus:** SECURE Act 10-year distribution requirement, no stretch IRA, tax planning for distributions
**Expected Count:** 15-20 questions total

#### UC-218: MFJ, W-2, High Income, 26-49, 2 Kids -> Adopted Child This Year
**Profile:** Adoption finalized, Adoption Tax Credit.
**Phase 2 Key Focus:** Adoption Tax Credit (up to $16,810 for 2025), Form 8839, special needs child higher credit
**Expected Count:** 16-21 questions total

#### UC-219: MFJ, W-2, Mid Income, 26-49, 2 Kids -> Foreclosure/Short Sale
**Profile:** Lost home through foreclosure.
**Phase 2 Key Focus:** Cancellation of debt income (Form 1099-C), insolvency exclusion (Form 982), main home exclusion
**Expected Count:** 15-20 questions total

#### UC-220: Single, Self-Employed, Mid Income, 26-49, No Deps -> Natural Disaster (casualty loss)
**Profile:** Business/property damaged by declared disaster.
**Phase 2 Key Focus:** Casualty loss deduction (only for federally declared disasters post-2018), Form 4684
**Expected Count:** 16-21 questions total

#### UC-221: MFJ, W-2, Low Income, 26-49, 2 Kids -> Bankruptcy Filed
**Profile:** Filed bankruptcy during tax year.
**Phase 2 Key Focus:** Cancellation of debt exclusion, bankruptcy estate (Chapter 7), tax attributes reduction
**Expected Count:** 14-18 questions total

#### UC-222: Single, W-2, Mid Income, 26-49, No Deps -> Received Large Gift
**Profile:** Received large gift (from parent, etc.).
**Phase 2 Key Focus:** Gifts received are NOT taxable income. Donor files Form 709 if > $18k. Recipient has donor's basis for gifted assets.
**Expected Count:** 11-15 questions total

#### UC-223: MFJ, W-2, Very High Income, 26-49, No Deps -> Expatriated (left US)
**Profile:** US citizen who moved abroad.
**Phase 2 Key Focus:** Foreign Earned Income Exclusion (Form 2555), Foreign Tax Credit, FBAR, FATCA, renunciation implications
**Expected Count:** 18-24 questions total

#### UC-224: Single, W-2, Mid Income, 26-49, No Deps -> Identity Theft (IRS)
**Profile:** Tax return rejected due to identity theft.
**Phase 2 Key Focus:** Form 14039 Identity Theft Affidavit, IP PIN, paper filing requirement
**Expected Count:** 12-16 questions total

#### UC-225: MFJ, W-2, Mid Income, 26-49, 2 Kids -> One Child Has Special Needs (ABLE account)
**Profile:** Family with special needs child, ABLE account.
**Phase 2 Key Focus:** ABLE account contributions (up to $18k), not taxable to beneficiary, doesn't affect SSI eligibility (up to $100k)
**Expected Count:** 15-20 questions total

---

## GROUP 9: Complex Multi-Situation Scenarios

**Scope:** Users with 3+ overlapping complexity factors.

### Group 9 Rules

**Critical validation rules:**
- ALL relevant sections must be asked -- no shortcuts
- Cross-section interactions must be checked (NIIT + SE, AMT + ISO, etc.)
- Total question count will be HIGH (20-30+)

**Follow-up chains:**
- Complex returns require all follow-ups from each applicable group
- Must check interactions between income types
- Must verify no double-counting of deductions

---

#### UC-226: MFJ, S-Corp + Rental + Investments, Very High Income ($500k+), 50-64, 2+ Kids
**Profile:** Wealthy business owner with diversified income.
**Phase 2 Questions Asked:**
- S-Corp W-2 and K-1
- All rental properties (income, expenses, depreciation)
- Investment portfolio (dividends, capital gains, wash sales)
- QBI for S-Corp (SSTB check, W-2 wage limit)
- QBI for rental (safe harbor?)
- Passive activity rules (grouping election)
- Real estate professional status?
- NIIT on investment + passive income
- AMT exposure
- Childcare / nanny (Schedule H)
- Child Tax Credit (phaseout at $400k MFJ)
- Retirement (max S-Corp 401k, defined benefit?)
- HSA
- Mortgage (SALT cap)
- Charitable (donor-advised fund, appreciated stock)
- Estimated payments
- State tax planning
- Life events
**Questions SKIPPED:** Very few -- nearly everything applies
**Expected Count:** 25-32 questions total

#### UC-227: Single, Self-Employed + W-2 + Crypto + Rental, High Income, 26-49, No Deps
**Profile:** Multiple income streams, maximum complexity for single filer.
**Phase 2 Questions Asked:**
- W-2 details and withholding
- SE business income and expenses
- Crypto transactions (sales, staking, mining)
- Rental property income and expenses
- SE tax
- QBI deduction
- Capital gains/losses (crypto + stocks)
- Passive activity (rental)
- NIIT check
- AMT check
- Estimated payments
- Retirement (SEP from SE income)
- HSA
- Itemize vs. standard
- Life events
**Expected Count:** 22-28 questions total

#### UC-228: MFJ, Partnership + C-Corp Board Fees + Investments + Foreign Income, Very High Income, 50-64, No Deps
**Profile:** Complex executive with multiple income sources.
**Phase 2 Questions Asked:**
- Partnership K-1 details
- Board compensation (W-2 or 1099)
- C-Corp director fees (SE income)
- Investment portfolio (detailed)
- Foreign income and accounts
- FBAR / FATCA
- Foreign Tax Credit
- NIIT
- AMT
- Estimated payments
- Retirement strategies (multiple vehicles)
- Charitable (bunching, donor-advised)
- State tax implications
- Life events
**Expected Count:** 24-30 questions total

#### UC-229: HOH, Self-Employed + Rental + Disabled Child, Mid Income, 50-64, 1 Disabled Dep
**Profile:** Single parent with business, rental, and disabled dependent.
**Phase 2 Questions Asked:**
- SE business details
- Rental property details
- Passive activity rules
- Disabled child care expenses
- ABLE account
- Medical expenses (both -- may itemize)
- Credit for Other Dependents
- QBI deduction
- SE tax
- Retirement
- Health insurance
- Life events
**Expected Count:** 20-26 questions total

#### UC-230: MFJ, W-2 (tech ISO/RSU) + Spouse SE + Rental + 529, Very High Income, 26-49, 2 Kids
**Profile:** Tech couple with equity comp, side business, rental, and college savings.
**Phase 2 Questions Asked:**
- W-2 with RSU/ISO details
- ISO exercise AMT impact
- RSU vesting income
- Spouse SE business details
- Rental property
- 529 plan contributions and distributions
- Childcare / nanny (Schedule H)
- Child Tax Credit
- QBI on spouse's SE income
- Passive activity (rental)
- NIIT
- AMT (ISO + high income)
- Estimated payments
- Retirement (employer 401k + SEP)
- HSA
- Charitable
- Itemize vs. standard
- Life events
**Expected Count:** 25-32 questions total

#### UC-231: MFJ, Retired + Part-Time SE + Rental + Inherited IRA + RMDs, High Income, 65+, No Deps
**Profile:** Active retiree with multiple income streams in retirement.
**Phase 2 Questions Asked:**
- SS income
- Pension income
- IRA RMDs
- Inherited IRA distributions (10-year rule)
- Part-time SE income and expenses
- Rental property income
- SE tax (yes, even at 65+ if self-employed)
- QBI on SE and rental
- Passive activity
- Medicare / IRMAA
- QCD strategy
- Charitable
- Estimated payments
- Life events
**Expected Count:** 22-28 questions total

#### UC-232: Single, W-2 + Investments + Crypto + Stock Options + ACA, Very High Income, Under 26, No Deps
**Profile:** Young high earner with every investment type.
**Phase 2 Key Focus:** ISO AMT, crypto reporting, NIIT, ACA (may not have employer plan)
**Expected Count:** 22-28 questions total

#### UC-233: MFJ, S-Corp + W-2 Spouse + Rental + K-1 from Partnership + Moved States, Very High Income, 26-49, 2+ Kids
**Profile:** Everything scenario -- maximum question count.
**Phase 2 Key Focus:** S-Corp + Partnership K-1s, rental, spouse W-2, children, multi-state, QBI for each entity
**Expected Count:** 28-35 questions total

#### UC-234: HOH, Self-Employed + Alimony Received + Child Support + Rental, Mid Income, 26-49, 2 Kids
**Profile:** Divorced self-employed parent with rental and support income.
**Phase 2 Key Focus:** Alimony received (pre-2019 = income), child support (not income), SE, rental, kids
**Expected Count:** 20-26 questions total

#### UC-235: MFJ, Military + Spouse S-Corp + Rental (PCS home), Mid Income, 26-49, 2 Kids
**Profile:** Military family with spouse business and rental near old base.
**Phase 2 Key Focus:** Military pay + spouse S-Corp + rental of former home, state domicile
**Expected Count:** 22-28 questions total

#### UC-236: Single, Investor + Foreign Income + Rental + Crypto, Very High Income, 26-49, No Deps
**Profile:** International investor with diversified portfolio.
**Phase 2 Key Focus:** Foreign tax credit, PFIC, FBAR, FATCA, rental, crypto, NIIT on everything
**Expected Count:** 24-30 questions total

#### UC-237: MFJ, Both Self-Employed + Investments + Education Expenses + ACA, Mid Income, 26-49, 3+ Kids
**Profile:** Entrepreneurial family with many kids and marketplace insurance.
**Phase 2 Key Focus:** Two Schedule Cs, ACA PTC reconciliation, education credits, EITC, CTC, childcare
**Expected Count:** 24-30 questions total

#### UC-238: Single, W-2 + S-Corp + Partnership K-1 + Inherited Property, Very High Income, 50-64, No Deps
**Profile:** Complex executive with multiple entities and recent inheritance.
**Phase 2 Key Focus:** Three income sources, inherited property basis, QBI calculations, AMT/NIIT
**Expected Count:** 24-30 questions total

#### UC-239: MFJ, Retired + Active SE + Rental Empire + Trust, Very High Income, 65+, No Deps
**Profile:** Wealthy retiree with active business interests.
**Phase 2 Key Focus:** RMDs, SE at 65+, multiple rentals, trust K-1, real estate professional, NIIT, QCD
**Expected Count:** 26-33 questions total

#### UC-240: MFJ, W-2 (both) + Side Hustle (both) + Rental + Investments + 3 Kids + Bought Home + Energy Credits, High Income, 26-49
**Profile:** The "everything" family. Maximum realistic complexity.
**Phase 2 Questions Asked:**
- Both W-2s, withholding
- Both side hustles (Schedule C each)
- Rental property
- Investment income
- Home purchase details
- Energy credits (new home improvements)
- 3 children (CTC x 3)
- Childcare
- QBI (both SEs)
- SE tax (both)
- Estimated payments
- Retirement (employer plans + SEPs)
- HSA
- Mortgage interest + points
- Property taxes
- Charitable
- Life events
**Expected Count:** 30-38 questions total

---

## GROUP 10: Edge Cases and Unusual Combinations

**Scope:** Rare but valid tax situations that the system must handle.

### Group 10 Rules

**Critical validation rules:**
- Each edge case has unique validation -- see individual scenarios
- System must gracefully handle even if not perfectly optimized
- Should flag for CPA review when encountering truly unusual situations

---

#### UC-241: MFS, W-2, Mid Income, Community Property State, 26-49, No Deps
**Profile:** MFS in a community property state (CA, TX, WI, etc.).
**Phase 2 Key Focus:** Community property allocation rules -- each spouse reports 50% of community income regardless of who earned it. COMPLETELY different from common law states.
**CRITICAL NOTE:** Community property MFS filing is one of the most complex areas. Must identify state.
**Expected Count:** 14-18 questions total

#### UC-242: Single, No Income, Under 26, No Deps (Filing for Refund of Withholding Only)
**Profile:** Student or dependent with minimal income, wants withholding refund.
**Phase 2 Questions Asked:**
- Any W-2 income (even $500)
- Withholding amount
- Can someone claim you as dependent?
- Unearned income (Kiddie Tax check if under 19 or under 24 and student)
- Filing requirement check
**Expected Count:** 5-8 questions total

#### UC-243: MFJ, Non-Resident Alien Spouse, W-2, High Income, 26-49, 1 Kid
**Profile:** US citizen married to NRA, election to treat NRA as resident.
**Phase 2 Key Focus:** Section 6013(g) election, ITIN for spouse, worldwide income reporting, treaty benefits
**Expected Count:** 16-21 questions total

#### UC-244: Single, W-2, Mid Income, 26-49, No Deps, Lived in Two Countries
**Profile:** Split-year resident -- moved to/from US mid-year.
**Phase 2 Key Focus:** Dual-status return, Form 1040-NR for part of year, treaty benefits, FBAR
**Expected Count:** 16-21 questions total

#### UC-245: Single, Full-Time Minister/Clergy, Mid Income, 26-49, No Deps
**Profile:** Ordained minister with parsonage allowance.
**Phase 2 Key Focus:** Parsonage allowance (housing -- excluded from income), SE tax on full compensation including housing, dual-status tax treatment
**Expected Count:** 13-17 questions total

#### UC-246: MFJ, Farmer (Schedule F), Mid Income, 50-64, 2+ Kids
**Profile:** Family farmer, unique tax rules.
**Phase 2 Key Focus:** Schedule F (not C), crop insurance, commodity credit loans, conservation easements, Section 179 on farm equipment, income averaging (farmers can!)
**Expected Count:** 18-23 questions total

#### UC-247: Single, W-2, Mid Income, Under 26, No Deps, Kiddie Tax Applies
**Profile:** College student with significant unearned income.
**Phase 2 Key Focus:** Kiddie Tax (Form 8615) -- unearned income over $2,500 taxed at parent's rate
**Expected Count:** 11-15 questions total

#### UC-248: MFJ, Canceled Debt Income, Low Income, 26-49, 2+ Kids
**Profile:** Family with significant debt cancellation (credit card, mortgage).
**Phase 2 Key Focus:** Form 1099-C, insolvency exclusion (Form 982), qualified principal residence exclusion, impact on credits
**Expected Count:** 14-18 questions total

#### UC-249: Single, Gambling Professional, Very High Income, 26-49, No Deps
**Profile:** Professional gambler (Schedule C, not just W-2G).
**Phase 2 Key Focus:** Professional gambler = SE income, all expenses deductible (not limited to winnings), SE tax, travel, equipment
**Expected Count:** 16-21 questions total

#### UC-250: MFJ, Tribal Member Income, Mid Income, 26-49, 2+ Kids
**Profile:** Enrolled tribal member with per capita payments.
**Phase 2 Key Focus:** Tribal per capita distributions, Indian General Welfare Act exclusions, on-reservation income exclusions
**Expected Count:** 14-18 questions total

---

## Appendix A: Question Count Summary by Group

| Group | Scenarios | Min Questions | Max Questions | Avg Questions |
|-------|-----------|---------------|---------------|---------------|
| 1: Simple W-2 | 60 | 6 | 22 | 14 |
| 2: W-2 + Side Hustle | 25 | 13 | 25 | 17 |
| 3: Self-Employed/LLC | 25 | 13 | 25 | 19 |
| 4: S-Corp/C-Corp/Partnership | 25 | 15 | 28 | 20 |
| 5: Retired | 25 | 6 | 24 | 16 |
| 6: Investors | 20 | 14 | 28 | 19 |
| 7: Military | 15 | 11 | 23 | 16 |
| 8: Life Events | 30 | 11 | 28 | 17 |
| 9: Complex Multi | 15 | 20 | 38 | 27 |
| 10: Edge Cases | 10 | 5 | 23 | 16 |

**Total Use Cases: 250**

---

## Appendix B: Universal Skip Logic Matrix

This matrix shows which question categories are NEVER applicable given a specific profile attribute.

| Profile Attribute | SKIP These Questions |
|-------------------|---------------------|
| No dependents | Childcare, CTC, ODC, custody, EITC child questions |
| No earned income | EITC, SE tax, retirement contributions |
| MFS filing status | EITC, education credits (most), premium tax credit, student loan deduction |
| Income > $200k single | EITC, Saver's Credit, education credits |
| Income > $400k MFJ | CTC (phased out), EITC, Saver's Credit |
| Income < $15k single | Itemized deductions (standard is better), AMT, NIIT |
| Age < 18 | Saver's Credit, retirement contributions |
| Age < 26 | Pension, RMD, Medicare/IRMAA, catch-up contributions |
| Age < 59.5 | RMD, early withdrawal penalty check |
| Age >= 73 | Traditional IRA contributions (still allowed post-SECURE 2.0!) |
| No home ownership | Mortgage interest, property taxes, energy credits, home sale exclusion |
| No investments | NIIT, capital gains/losses, wash sales, Form 8949, Schedule D |
| No self-employment | SE tax, Schedule C, QBI (unless K-1 or rental), estimated payments (usually) |
| No foreign connections | FBAR, FATCA, Form 1116, Form 2555, Form 5471 |
| Medicare eligible | ACA marketplace, premium tax credit |
| Active military | ACA questions (has TRICARE), moving expense suspension (military exempt) |

---

## Appendix C: Critical Cross-Scenario Validation Rules

These rules apply ACROSS all scenarios and must be checked regardless of group:

1. **Filing Status + Dependent Consistency:** If HOH or QSS is selected, system MUST verify qualifying person exists.
2. **Income + Credit Phase-Outs:** Every credit must be checked against income thresholds specific to filing status.
3. **MFS Restrictions:** If MFS, system must block: EITC, most education credits, student loan deduction, premium tax credit, and alert about itemize requirement if spouse itemizes.
4. **Age + Retirement Rules:** Age determines RMD requirements, catch-up eligibility, Social Security taxability, Medicare, additional standard deduction.
5. **State of Residence:** Determines state tax obligations, property tax credits, pension exclusions, community property rules.
6. **Self-Employment + Quarterly Payments:** If SE income exceeds $1,000 net, estimated payments must be discussed.
7. **QBI Stacking:** If multiple QBI-eligible businesses, each must be calculated separately, then aggregated.
8. **NIIT vs SE Tax:** SE income is NOT subject to NIIT. Investment and passive income IS. Must separate correctly.
9. **AMT Triggers:** ISO exercises, large itemized deductions (SALT), private activity bonds, incentive stock options. Flag if any present.
10. **Dependent Filing Requirement:** If dependent has unearned income > $1,300 or earned income > $14,600, they must file their own return.
