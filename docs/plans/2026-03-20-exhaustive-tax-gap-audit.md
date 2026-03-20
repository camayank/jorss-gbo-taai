# Exhaustive Tax Gap Audit: Chatbot Question Flow

**Date:** 2026-03-20
**Auditor Perspective:** Senior CPA, 10,000+ individual returns prepared
**Scope:** Every line of Form 1040 (2025), all schedules, all common forms, every taxpayer situation
**Current Registry:** 79 questions across 14 pools (question_registry.py)

---

## TABLE OF CONTENTS

1. [Missing Primary Income Types (Phase 1)](#1-missing-primary-income-types-phase-1)
2. [Missing Income & 1099 Coverage (Phase 2)](#2-missing-income--1099-coverage-phase-2)
3. [Missing Deduction & Adjustment Questions](#3-missing-deduction--adjustment-questions)
4. [Missing Credit Questions](#4-missing-credit-questions)
5. [Missing Investment Follow-Up Chains](#5-missing-investment-follow-up-chains)
6. [Missing Retirement & Distribution Scenarios](#6-missing-retirement--distribution-scenarios)
7. [Missing Dependent & Family Situations](#7-missing-dependent--family-situations)
8. [Missing Life Event Follow-Up Chains](#8-missing-life-event-follow-up-chains)
9. [Missing International & Expatriate Situations](#9-missing-international--expatriate-situations)
10. [Missing Business & Self-Employment Follow-Ups](#10-missing-business--self-employment-follow-ups)
11. [Missing Rental & Passive Activity Gaps](#11-missing-rental--passive-activity-gaps)
12. [Missing State-Specific Situations](#12-missing-state-specific-situations)
13. [Missing Identity & Filing Logistics](#13-missing-identity--filing-logistics)
14. [Missing Situation Layers (Cross-Cutting)](#14-missing-situation-layers-cross-cutting)
15. [Missing Follow-Up Chain Map](#15-missing-follow-up-chain-map)
16. [Priority Matrix](#16-priority-matrix)

---

## 1. MISSING PRIMARY INCOME TYPES (Phase 1)

The current `income_type` question (Q-05) offers 8 options. The following income situations have NO primary path:

### GAP 1.1 -- Farm Income
- **Question:** "What best describes your income situation?" -- add option: **"Farmer / Agricultural"**
- **Who:** Anyone; ~2% of returns nationally, much higher in rural states (IA, NE, KS, SD)
- **IRS Form:** Schedule F (Form 1040), Form 4835 (farm rental)
- **Commonality:** ~2-3% of all returns
- **Action:** Add `"farmer"` value to Q-05 actions

### GAP 1.2 -- Trust/Estate Beneficiary (Non-K-1 Awareness)
- **Question:** Add option: **"Trust/Estate Beneficiary"**
- **Who:** Beneficiaries receiving income distributions from trusts/estates; they often do not know they have a K-1
- **IRS Form:** Schedule K-1 (Form 1041), Schedule E Part III
- **Commonality:** ~5% of returns (higher in HNW)
- **Action:** Add `"trust_beneficiary"` value to Q-05, route to K-1 chain

### GAP 1.3 -- Unemployed / No Income
- **Question:** Add option: **"Not currently working / No income this year"**
- **Who:** Unemployed, stay-at-home parents, students with no income; still may need to file (e.g., received 1099-G, refundable credits)
- **IRS Form:** 1040 (may still get EITC, education credits, refunds from withholding)
- **Commonality:** ~3-5%
- **Action:** Add `"no_income"` value

### GAP 1.4 -- Gig Worker (Not Side Hustle)
- **Question:** Add option: **"Full-time Gig Worker (Uber, DoorDash, Instacart)"**
- **Who:** Distinguishes full-time gig workers from W-2 + side hustle. Full-time gig workers have unique SE tax and deduction needs.
- **IRS Form:** Schedule C, Schedule SE
- **Commonality:** ~4-6%
- **Action:** Add `"gig_worker_fulltime"` value, route to SE chain

### GAP 1.5 -- Clergy / Minister
- **Question:** Add option: **"Clergy / Minister"**
- **Who:** Ministers have dual tax status (employee for income tax, SE for FICA), housing allowance exclusion, optional SE exemption
- **IRS Form:** Schedule SE, Form 4361 (SE exemption), Form W-2 Box 14
- **Commonality:** <1% but extremely complex when it applies
- **Action:** Add `"clergy"` value

### GAP 1.6 -- Statutory Employee
- **Question:** Not a primary type but needs detection: "Does your W-2 have Box 13 'Statutory Employee' checked?"
- **Who:** Commission-based salespeople, certain delivery drivers, home workers, life insurance agents
- **IRS Form:** Schedule C (not Schedule SE), W-2 Box 13
- **Commonality:** ~1%
- **Action:** Follow-up for W-2 employees

---

## 2. MISSING INCOME & 1099 COVERAGE (Phase 2)

### GAP 2.1 -- Interest Income Breakdown (1099-INT)
- **Question:** "Did you receive more than $1,500 in interest income this year? (Bank accounts, CDs, bonds, Treasury securities)"
- **Who:** Anyone with bank accounts; if >$1,500, Schedule B is required
- **IRS Form:** Schedule B Part I, Form 1040 Line 2b
- **Commonality:** ~35% of all returns have some interest; ~15% exceed $1,500
- **Buttons:** "Under $1,500" | "$1,500 - $10,000" | "Over $10,000" | "Tax-exempt bond interest (muni bonds)" | "No interest income" | "Skip"

### GAP 2.2 -- Tax-Exempt Interest
- **Question:** "Did you receive any tax-exempt interest income? (Municipal bonds, tax-free money market funds)"
- **Who:** Anyone who answered "has investments" or has income > $100K
- **IRS Form:** Form 1040 Line 2a (reported but not taxed; affects SS taxation calculation & ACA subsidy)
- **Commonality:** ~8-10% of returns
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 2.3 -- Dividend Income Split (1099-DIV)
- **Question:** "Did you receive dividend income? If so, approximately how much in total dividends?"
- **Who:** Currently only asks qualified vs ordinary for high amounts; needs the gateway question for ALL investors
- **IRS Form:** Schedule B Part II (if >$1,500), Form 1040 Line 3a/3b
- **Commonality:** ~25% of returns
- **Buttons:** "Under $1,500" | "$1,500 - $10,000" | "Over $10,000" | "No dividends" | "Skip"

### GAP 2.4 -- 1099-G (Government Payments)
- **Question:** "Did you receive any government payments this year? (State tax refund, unemployment compensation, agricultural payments)"
- **Who:** Anyone who itemized last year and received a state refund (taxable); anyone who received unemployment
- **IRS Form:** Form 1040 Schedule 1 Line 1 (state refund), Line 7 (unemployment)
- **Commonality:** ~20-25% (state refunds alone)
- **Buttons:** "State/local tax refund" | "Unemployment compensation" | "Agricultural payments" | "None" | "Skip"

### GAP 2.5 -- State Tax Refund Taxability
- **Question:** "Did you itemize deductions on last year's tax return? (If yes, your state refund may be taxable)"
- **Who:** Follow-up to 1099-G state refund; only taxable if they itemized prior year
- **IRS Form:** Schedule 1 Line 1, State Tax Refund Worksheet
- **Commonality:** ~15% of filers
- **Buttons:** "Yes, I itemized last year" | "No, I took the standard deduction" | "Not sure" | "Skip"

### GAP 2.6 -- Jury Duty Pay
- **Question:** "Did you receive jury duty pay this year?"
- **Who:** Anyone; often small but reportable. If turned over to employer, deductible on Schedule 1.
- **IRS Form:** Form 1040 Line 8 (other income), Schedule 1 Line 24a (deduction if remitted to employer)
- **Commonality:** ~3-5%
- **Buttons:** "Yes -- kept it" | "Yes -- turned it over to employer" | "No" | "Skip"

### GAP 2.7 -- Hobby Income
- **Question:** "Do you have income from a hobby or activity not engaged in for profit? (Crafts, collectibles, occasional sales)"
- **Who:** Anyone with misc income from non-business activities; post-TCJA hobby expenses are NOT deductible
- **IRS Form:** Form 1040 Schedule 1 Line 8j (Other income)
- **Commonality:** ~5%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 2.8 -- Cancellation of Debt Income (1099-C)
- **Question:** "Did you have any debt forgiven or canceled this year? (Credit card debt, mortgage modification, student loan forgiveness, personal loan)"
- **Who:** Anyone; COD income is taxable unless exception/exclusion applies (insolvency, bankruptcy, QPRI, student loan)
- **IRS Form:** Form 982, Form 1040 Schedule 1 Line 8d
- **Commonality:** ~3-5%
- **Buttons:** "Yes -- credit card or personal debt" | "Yes -- mortgage debt (foreclosure/short sale)" | "Yes -- student loan forgiveness" | "No canceled debt" | "Skip"

### GAP 2.9 -- 1099-SA / HSA Distributions
- **Question:** "Did you take any distributions from your HSA this year? Were they used for qualified medical expenses?"
- **Who:** Anyone with an HSA who took distributions
- **IRS Form:** Form 8889 Part II, Form 1040 Schedule 1 Line 13
- **Commonality:** ~15% of HSA holders take distributions
- **Buttons:** "Yes -- all for qualified medical" | "Yes -- some non-qualified" | "No distributions" | "Skip"

### GAP 2.10 -- 1099-LTC (Long-Term Care)
- **Question:** "Did you receive any long-term care insurance benefits or accelerated death benefits this year?"
- **Who:** Elderly/disabled taxpayers; benefits may be excludable up to per diem limit
- **IRS Form:** Form 8853 Part III
- **Commonality:** ~1-2%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 2.11 -- 1099-Q (529 / Coverdell Distributions)
- **Question:** "Did you take any distributions from a 529 plan or Coverdell Education Savings Account?"
- **Who:** Anyone with education savings accounts; non-qualified distributions are taxable + 10% penalty
- **IRS Form:** Form 1040 (taxable portion on Line 8), may trigger additional tax
- **Commonality:** ~5-8%
- **Buttons:** "Yes -- for qualified education expenses" | "Yes -- some non-qualified" | "No distributions" | "Skip"

### GAP 2.12 -- 1099-R Breakdown (Not Just Retirement)
- **Question:** "Did you receive distributions from any of these: life insurance (cash value), annuity, pension, 457 plan, or disability pension?"
- **Who:** 1099-R covers much more than IRA/401k. Currently only asks about IRA/401k distributions.
- **IRS Form:** Form 1040 Lines 4a-4b, 5a-5b
- **Commonality:** ~20% of returns
- **Buttons:** "Annuity payments" | "Life insurance cash surrender" | "457(b) plan" | "Disability pension" | "None of these" | "Skip"

### GAP 2.13 -- 1099-K (Payment Card / Third Party)
- **Question:** "Did you receive a Form 1099-K from a payment platform? (PayPal, Venmo, Square, Stripe, Etsy, eBay)"
- **Who:** Anyone receiving payments through third-party networks; $600 threshold
- **IRS Form:** Schedule C or Schedule 1 Line 8z
- **Commonality:** ~10-15% (growing rapidly)
- **Buttons:** "Yes -- for my business" | "Yes -- but it's personal reimbursements (not income)" | "No 1099-K" | "Skip"

### GAP 2.14 -- 1099-OID (Original Issue Discount)
- **Question:** "Did you receive a 1099-OID for bonds purchased at a discount?"
- **Who:** Bond investors holding zero-coupon or discounted debt instruments
- **IRS Form:** Schedule B, Form 1040 Line 2b
- **Commonality:** ~2-3%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 2.15 -- Bartering Income
- **Question:** "Did you exchange goods or services through bartering (including barter exchanges)?"
- **Who:** Business owners, freelancers; 1099-B from barter exchanges, or unreported otherwise
- **IRS Form:** Schedule C or Form 1040 Schedule 1 Line 8z
- **Commonality:** <1%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 2.16 -- Prizes, Awards, Contest Winnings
- **Question:** "Did you win any prizes, awards, or contest winnings? (TV shows, raffles, employer awards, Nobel Prize, etc.)"
- **Who:** Anyone; all prizes/awards are taxable unless donated to charity
- **IRS Form:** Form 1040 Schedule 1 Line 8b (prizes/awards)
- **Commonality:** ~2-3%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 2.17 -- Royalty Income (1099-MISC Box 2)
- **Question:** "Did you receive any royalty income? (Oil/gas, mineral rights, book/music royalties, patent licensing)"
- **Who:** Authors, musicians, mineral rights owners, patent holders
- **IRS Form:** Schedule E Part I (royalties), possibly Schedule C if in the business of creating IP
- **Commonality:** ~2-4%
- **Buttons:** "Oil/gas/mineral royalties" | "Book/music/art royalties" | "Patent or licensing royalties" | "No royalties" | "Skip"

### GAP 2.18 -- Director Fees / Board Compensation
- **Question:** "Did you receive fees for serving on a board of directors?"
- **Who:** Corporate directors; reported on 1099-NEC, subject to SE tax
- **IRS Form:** Schedule C, Schedule SE
- **Commonality:** ~1-2%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 2.19 -- Tip Income (Unreported)
- **Question:** "Did you receive tips that were not reported to your employer?"
- **Who:** Service industry workers (restaurant, hotel, salon); unreported tips are subject to SE tax
- **IRS Form:** Form 4137 (Social Security and Medicare Tax on Unreported Tip Income)
- **Commonality:** ~3-5% of W-2 employees
- **Buttons:** "Yes" | "No / All tips reported on W-2" | "Skip"

---

## 3. MISSING DEDUCTION & ADJUSTMENT QUESTIONS

### GAP 3.1 -- IRA Contribution Deductibility
- **Question:** "You mentioned contributing to a Traditional IRA. Do you or your spouse have a retirement plan at work? (This affects whether your IRA contribution is deductible)"
- **Who:** Anyone contributing to Traditional IRA who also has workplace plan; AGI limits apply
- **IRS Form:** Form 1040 Schedule 1 Line 20, Form 8606 (nondeductible contributions)
- **Commonality:** ~10-15% of IRA contributors
- **Buttons:** "Yes -- I have a plan at work" | "Yes -- spouse has plan at work" | "Neither of us" | "Skip"

### GAP 3.2 -- Moving Expenses (Military Only)
- **Question:** "You mentioned a PCS move. What were your total unreimbursed moving expenses?"
- **Who:** Active duty military with PCS orders only (civilians lost this deduction post-TCJA)
- **IRS Form:** Form 3903
- **Commonality:** ~0.5% of all returns
- **Buttons:** "Under $2,000" | "$2,000 - $5,000" | "$5,000 - $10,000" | "Over $10,000" | "Skip"

### GAP 3.3 -- Self-Employment Tax Deduction Awareness
- **Question:** Not a question -- but the chatbot should flag: "As self-employed, you'll get an above-the-line deduction for 50% of your self-employment tax."
- **Who:** All SE/business filers
- **IRS Form:** Schedule 1 Line 15
- **Commonality:** 100% of SE filers
- **Action:** Add advisory text, not a question

### GAP 3.4 -- Penalty on Early Savings Withdrawal
- **Question:** "Were you charged an early withdrawal penalty by your bank for breaking a CD or time deposit before maturity?"
- **Who:** Anyone with bank CDs; above-the-line deduction
- **IRS Form:** Form 1040 Schedule 1 Line 18, reported on 1099-INT Box 2
- **Commonality:** ~2-3%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 3.5 -- Tuition and Fees (if Reinstated / Student Loan Interest Details)
- **Question:** "How much student loan interest did you pay? (Deductible up to $2,500; check Form 1098-E)"
- **Who:** Currently only asks yes/no. Need dollar amount for accurate calculation.
- **IRS Form:** Form 1040 Schedule 1 Line 21
- **Commonality:** ~15% of returns
- **Buttons:** "Under $1,000" | "$1,000 - $2,500" | "Over $2,500 (capped at $2,500)" | "Skip"

### GAP 3.6 -- Archer MSA Deduction
- **Question:** "Do you have an Archer Medical Savings Account (MSA)?"
- **Who:** Self-employed individuals or employees of small employers; being phased out but some still exist
- **IRS Form:** Form 8853
- **Commonality:** <0.5%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 3.7 -- Charitable Donations -- Non-Cash / Large Donations
- **Question:** "Did any of your charitable donations include non-cash items worth more than $500? (Clothing, furniture, vehicles, stock, artwork)"
- **Who:** Follow-up for anyone who said they made charitable donations
- **IRS Form:** Form 8283 (Noncash Charitable Contributions), Schedule A
- **Commonality:** ~10-15% of itemizers
- **Buttons:** "Yes -- donated property/goods over $500" | "Yes -- donated appreciated stock/securities" | "Yes -- donated vehicle worth over $500" | "No -- all cash/check donations" | "Skip"

### GAP 3.8 -- Charitable Donations -- Qualified Charitable Distribution (QCD)
- **Question:** "Are you 70 1/2 or older? Did you make a Qualified Charitable Distribution (QCD) directly from your IRA to charity? (Up to $105,000 is excluded from income)"
- **Who:** Retired/senior with IRA
- **IRS Form:** Form 1040 Line 4a/4b (reported but excluded)
- **Commonality:** ~5-8% of seniors
- **Buttons:** "Yes -- made QCD from IRA" | "No" | "Skip"

### GAP 3.9 -- Casualty and Theft Losses
- **Question:** "Did you suffer losses from a federally declared disaster? (Flood, hurricane, wildfire, tornado)"
- **Who:** Anyone in a federally declared disaster area; only disaster losses are deductible post-TCJA
- **IRS Form:** Form 4684, Schedule A Line 15
- **Commonality:** ~1-2% (spikes in disaster years)
- **Buttons:** "Yes -- federally declared disaster" | "Yes -- but not a declared disaster" | "No losses" | "Skip"

### GAP 3.10 -- Gambling Losses (Follow-Up)
- **Question:** "You mentioned gambling losses. Were your losses at least equal to your winnings? (You can deduct losses up to the amount of winnings if you itemize)"
- **Who:** Follow-up for anyone who said gambling_losses or gambling_winnings
- **IRS Form:** Schedule A Line 16 (other itemized deductions)
- **Commonality:** ~5% of filers
- **Buttons:** "Losses exceed winnings" | "Losses are less than winnings" | "Skip"

### GAP 3.11 -- Business Use of Home -- Simplified vs Regular
- **Question:** "For your home office, would you like to use the simplified method ($5/sq ft, max 300 sq ft = $1,500) or the regular method (actual expenses)?"
- **Who:** Follow-up for anyone who said they have a home office
- **IRS Form:** Form 8829 (regular) or Schedule C Line 30 (simplified)
- **Commonality:** 100% of home office filers
- **Buttons:** "Simplified method ($5/sq ft)" | "Regular method (actual expenses)" | "Not sure -- help me decide" | "Skip"

---

## 4. MISSING CREDIT QUESTIONS

### GAP 4.1 -- Earned Income Tax Credit (EITC)
- **Question:** "Based on your income and filing status, you may qualify for the Earned Income Tax Credit. Did you have earned income (wages, self-employment) this year?"
- **Who:** Filing status + income below EITC thresholds (varies by dependents: ~$17K-$63K); investment income must be under $11,600
- **IRS Form:** Schedule EIC, Form 1040 Line 27
- **Commonality:** ~20-25% of all returns
- **Buttons:** "Yes -- I think I qualify" | "My income is too high" | "I'm not sure" | "Skip"

### GAP 4.2 -- EITC Investment Income Check
- **Question:** "Is your total investment income (interest, dividends, capital gains) under $11,600? (Required for EITC eligibility)"
- **Who:** Follow-up for potential EITC claimants with investment income
- **IRS Form:** EITC Worksheet, Schedule EIC
- **Commonality:** ~20% of EITC claimants have investment income
- **Buttons:** "Yes -- under $11,600" | "No -- over $11,600" | "Not sure" | "Skip"

### GAP 4.3 -- Retirement Savings Credit (Saver's Credit)
- **Question:** "Are you contributing to a retirement account? You may qualify for the Saver's Credit (up to $1,000/$2,000 for low-to-moderate income). Your AGI must be under $38,250 (single) or $76,500 (MFJ)."
- **Who:** AGI below thresholds, age 18+, not a student, not claimed as dependent
- **IRS Form:** Form 8880, Form 1040 Schedule 3 Line 4
- **Commonality:** ~10% of eligible filers (massively underclaimed)
- **Buttons:** "Yes -- I think I qualify" | "Income too high" | "Skip"

### GAP 4.4 -- Credit for the Elderly or Disabled (Schedule R)
- **Question:** "Are you 65 or older, OR permanently and totally disabled? You may qualify for the Credit for the Elderly or Disabled."
- **Who:** Age 65+, or under 65 and permanently disabled, with income below thresholds
- **IRS Form:** Schedule R (Form 1040), Form 1040 Schedule 3 Line 6d
- **Commonality:** ~2-3% of eligible (massively underclaimed)
- **Buttons:** "65+ and income below $25,000 (single)" | "Permanently disabled" | "Not applicable" | "Skip"

### GAP 4.5 -- Foreign Tax Credit (Detail)
- **Question:** "You mentioned paying foreign taxes. How much in foreign taxes did you pay? (If under $300 single/$600 MFJ from qualified passive category income, you can claim directly without Form 1116)"
- **Who:** Follow-up for foreign_investments answer
- **IRS Form:** Form 1116 (or direct credit on Form 1040 Schedule 3 Line 1)
- **Commonality:** ~10-12% of returns
- **Buttons:** "Under $300 (single) / $600 (MFJ)" | "$300 - $5,000" | "Over $5,000" | "Skip"

### GAP 4.6 -- Child Tax Credit Phaseout Awareness
- **Question:** "Your income may affect your Child Tax Credit. Is your AGI over $200,000 (single) or $400,000 (MFJ)? (Credit phases out at $50 per $1,000 over the threshold)"
- **Who:** High-income filers with children under 17
- **IRS Form:** Form 1040 Line 19, Schedule 8812
- **Commonality:** ~5-8% of CTC claimants
- **Buttons:** "Under the threshold" | "Over the threshold" | "Not sure" | "Skip"

### GAP 4.7 -- Additional Child Tax Credit (Refundable Portion)
- **Question:** "If your tax liability is less than your total Child Tax Credit, you may receive the Additional Child Tax Credit as a refund. Do you expect a low tax liability?"
- **Who:** Low-to-moderate income with children; must have earned income > $2,500
- **IRS Form:** Schedule 8812
- **Commonality:** ~15% of CTC claimants
- **Buttons:** "Yes -- low tax liability" | "No" | "Not sure" | "Skip"

### GAP 4.8 -- Other Dependent Credit
- **Question:** "Do you have dependents who are 17 or older? (Adult dependents, college students 17+, elderly parents qualify for a $500 non-refundable credit each)"
- **Who:** Anyone with dependents age 17+
- **IRS Form:** Form 1040 Line 19 (part of unified credit), Schedule 8812
- **Commonality:** ~10%
- **Buttons:** "Yes -- dependents age 17+" | "All my dependents are under 17" | "Skip"

### GAP 4.9 -- Education Credits -- AOTC vs LLC
- **Question:** "For the student in your household: is this within the first 4 years of college? (American Opportunity Credit = up to $2,500, partially refundable) Or beyond year 4? (Lifetime Learning Credit = up to $2,000, non-refundable)"
- **Who:** Follow-up for anyone who answered education_status with student
- **IRS Form:** Form 8863
- **Commonality:** ~12% of returns
- **Buttons:** "First 4 years (AOTC)" | "Beyond year 4 or grad school (LLC)" | "Vocational/continuing education (LLC)" | "Not sure" | "Skip"

### GAP 4.10 -- Education Credits -- Felony Drug Conviction
- **Question:** "Has the student been convicted of a felony drug offense? (This disqualifies AOTC only)"
- **Who:** AOTC claimants; required question on Form 8863
- **IRS Form:** Form 8863 Part III Line 23
- **Commonality:** <1% but required for compliance
- **Buttons:** "No" | "Yes" | "Skip"

### GAP 4.11 -- Residential Clean Energy Credit (Solar Detail)
- **Question:** "What was the total cost of your solar installation? (You may qualify for a 30% credit)"
- **Who:** Follow-up for solar answer
- **IRS Form:** Form 5695 Part I
- **Commonality:** ~3-5% and growing
- **Buttons:** "Under $15,000" | "$15,000 - $30,000" | "$30,000 - $50,000" | "Over $50,000" | "Skip"

### GAP 4.12 -- Clean Vehicle Credit Detail
- **Question:** "For the electric vehicle you purchased: Was it new or used? What was the purchase price? (New EV credit up to $7,500; used EV credit up to $4,000)"
- **Who:** Follow-up for EV answer; strict MSRP limits, AGI limits, and assembly requirements
- **IRS Form:** Form 8936
- **Commonality:** ~3-5%
- **Buttons:** "New EV -- under $55K (sedan) or $80K (SUV/truck)" | "Used EV -- under $25K" | "New EV -- over MSRP limit" | "Skip"

### GAP 4.13 -- Energy Efficient Home Improvement Credit Detail
- **Question:** "What energy improvements did you make? (Annual limit $3,200 total: $1,200 general + $2,000 heat pump)"
- **Who:** Follow-up for energy_improvements answer
- **IRS Form:** Form 5695 Part II
- **Commonality:** ~5-8%
- **Buttons:** "Heat pump / heat pump water heater ($2,000 max)" | "Insulation / windows / doors ($1,200 max)" | "Electrical panel upgrade ($600 max)" | "Energy audit ($150 max)" | "Multiple improvements" | "Skip"

### GAP 4.14 -- Net Premium Tax Credit Reconciliation
- **Question:** "You mentioned an ACA marketplace plan with subsidy. Did your income end up higher or lower than what you estimated when you enrolled? (This affects whether you owe money back or get a bigger credit)"
- **Who:** Follow-up for aca_with_subsidy
- **IRS Form:** Form 8962
- **Commonality:** ~8-10% of ACA enrollees have significant reconciliation
- **Buttons:** "Income was higher than estimated" | "Income was lower than estimated" | "About what I estimated" | "Skip"

### GAP 4.15 -- Qualified Opportunity Zone (QOZ) Investment
- **Question:** "Did you invest capital gains into a Qualified Opportunity Zone fund this year?"
- **Who:** Anyone with capital gains; significant deferral/exclusion benefits
- **IRS Form:** Form 8997, Form 8949
- **Commonality:** ~0.5-1% (but high dollar impact)
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 4.16 -- Qualified Small Business Stock (QSBS) Exclusion
- **Question:** "Did you sell stock in a qualified small business (Section 1202 QSBS)? You may exclude up to $10M or 10x basis in gain."
- **Who:** Anyone selling stock in C-corporations that qualify; must hold 5+ years
- **IRS Form:** Schedule D, Form 8949
- **Commonality:** ~0.5% but enormous dollar impact
- **Buttons:** "Yes -- held 5+ years" | "Yes -- held less than 5 years" | "No / Not sure" | "Skip"

### GAP 4.17 -- Work Opportunity Tax Credit (WOTC)
- **Question:** "Did you hire employees from targeted groups? (Veterans, ex-felons, long-term unemployed, SNAP recipients)"
- **Who:** Business owners with employees
- **IRS Form:** Form 5884, Form 8850 (must be filed within 28 days of hire)
- **Commonality:** ~2% of employer returns
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 4.18 -- Excess Social Security Withholding
- **Question:** "Did you have more than one employer this year? If so, you may have had excess Social Security tax withheld (over the wage base of $176,100 for 2025)."
- **Who:** Multiple W-2 employees with combined wages exceeding SS wage base
- **IRS Form:** Form 1040 Schedule 3 Line 11
- **Commonality:** ~5% of multiple-W2 filers
- **Buttons:** "Yes -- combined wages over $176,100" | "No" | "Not sure" | "Skip"

---

## 5. MISSING INVESTMENT FOLLOW-UP CHAINS

### GAP 5.1 -- Wash Sale Awareness
- **Question:** "Did you sell any investments at a loss and buy the same or substantially identical securities within 30 days before or after? (This is a 'wash sale' -- the loss is disallowed)"
- **Who:** Anyone with investment losses
- **IRS Form:** Form 8949 Column (g), Schedule D
- **Commonality:** ~10-15% of active investors
- **Buttons:** "Yes / Possibly" | "No" | "Not sure" | "Skip"

### GAP 5.2 -- Section 1256 Contracts (Futures / Forex)
- **Question:** "Did you trade futures, options on futures, or foreign currency contracts (Section 1256 contracts)? These get special 60/40 long-term/short-term treatment."
- **Who:** Active traders, forex traders
- **IRS Form:** Form 6781
- **Commonality:** ~1-2%
- **Buttons:** "Yes -- regulated futures/options" | "Yes -- forex (Section 988)" | "No" | "Skip"

### GAP 5.3 -- Like-Kind Exchange (1031)
- **Question:** "Did you exchange any investment or business real property for similar property? (1031 like-kind exchange -- defers capital gains)"
- **Who:** Real estate investors, business property owners
- **IRS Form:** Form 8824
- **Commonality:** ~1-2%
- **Buttons:** "Yes -- completed exchange" | "Yes -- reverse exchange" | "Yes -- currently in exchange (45/180 day period)" | "No" | "Skip"

### GAP 5.4 -- Installment Sale
- **Question:** "Did you sell property and receive payments over multiple years? (Installment sale -- report gain as payments are received)"
- **Who:** Anyone who sold property with seller financing; also follow-up for home sale
- **IRS Form:** Form 6252
- **Commonality:** ~1-2%
- **Buttons:** "Yes" | "No -- received full payment at closing" | "Skip"

### GAP 5.5 -- Collectibles Gain (28% Rate)
- **Question:** "Did you sell any collectibles? (Art, antiques, coins, stamps, precious metals, gems -- taxed at 28% max rate)"
- **Who:** Anyone who sold investments; collectibles get higher rate
- **IRS Form:** Schedule D, 28% Rate Gain Worksheet
- **Commonality:** ~1-2%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 5.6 -- Net Investment Income Tax (NIIT)
- **Question:** "Is your modified AGI over $200,000 (single) or $250,000 (MFJ)? You may owe the 3.8% Net Investment Income Tax."
- **Who:** High-income investors; currently no question about NIIT
- **IRS Form:** Form 8960
- **Commonality:** ~5-8% of returns
- **Buttons:** "Yes -- MAGI over threshold" | "No" | "Not sure" | "Skip"

### GAP 5.7 -- Investment Interest Expense
- **Question:** "Did you borrow money to buy investments? (Margin interest, investment-related interest expense)"
- **Who:** Investors with margin accounts or investment loans
- **IRS Form:** Form 4952
- **Commonality:** ~3-5% of investors
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 5.8 -- Passive Activity Loss Limitations Detail
- **Question:** "Do you have passive activity losses from prior years that were disallowed? (Rental losses, limited partnership losses carried forward)"
- **Who:** Rental property owners, K-1 recipients with passive losses
- **IRS Form:** Form 8582
- **Commonality:** ~5-8%
- **Buttons:** "Yes -- prior year suspended losses" | "No" | "Not sure" | "Skip"

### GAP 5.9 -- MLP (Master Limited Partnership) Income
- **Question:** "Do you own any Master Limited Partnerships (MLPs)? (Common in energy/pipeline sector -- K-1 income with unique tax treatment)"
- **Who:** Investors with brokerage accounts holding MLPs
- **IRS Form:** Schedule K-1 (Form 1065), Schedule E, Form 8582
- **Commonality:** ~2-3%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 5.10 -- ESPP Disposition Type
- **Question:** "For your Employee Stock Purchase Plan (ESPP) shares that you sold: did you hold them for at least 2 years from grant date AND 1 year from purchase date? (Qualifying vs disqualifying disposition affects taxation)"
- **Who:** Follow-up for ESPP holders
- **IRS Form:** Form 3922, Form 8949, Schedule D
- **Commonality:** ~3-5% of W-2 tech/corporate employees
- **Buttons:** "Qualifying disposition (met holding periods)" | "Disqualifying disposition (sold early)" | "Haven't sold any shares" | "Not sure" | "Skip"

### GAP 5.11 -- ISO AMT Adjustment
- **Question:** "You mentioned exercising Incentive Stock Options. Did you exercise and HOLD (did not sell same year)? The spread is an AMT preference item."
- **Who:** Follow-up for ISO holders; critical AMT trigger
- **IRS Form:** Form 6251 Line 2i
- **Commonality:** ~2-3% of W-2 tech employees
- **Buttons:** "Exercised and held (did not sell same year)" | "Exercised and sold same year (no AMT)" | "Skip"

---

## 6. MISSING RETIREMENT & DISTRIBUTION SCENARIOS

### GAP 6.1 -- Backdoor Roth IRA
- **Question:** "Did you make a non-deductible Traditional IRA contribution and then convert it to a Roth IRA? (Backdoor Roth strategy)"
- **Who:** High-income earners over Roth IRA income limits
- **IRS Form:** Form 8606 Parts I and II
- **Commonality:** ~3-5% (increasingly common among HNW)
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 6.2 -- Form 8606 -- Basis in Traditional IRA
- **Question:** "Do you have any non-deductible (after-tax) contributions in your Traditional IRA? (This affects the tax on distributions and Roth conversions -- pro-rata rule)"
- **Who:** Anyone with IRA distributions or Roth conversions who may have basis
- **IRS Form:** Form 8606
- **Commonality:** ~5-8% of IRA holders
- **Buttons:** "Yes -- I have basis in my IRA" | "No -- all contributions were deductible" | "Not sure" | "Skip"

### GAP 6.3 -- Inherited IRA / Beneficiary Distribution
- **Question:** "Did you inherit a retirement account (inherited IRA/401k)? The rules for required distributions depend on when the original owner died and your relationship."
- **Who:** Anyone who inherited a retirement account; SECURE Act changed rules significantly
- **IRS Form:** Form 1099-R (distribution code 4), Form 1040 Lines 4a/4b
- **Commonality:** ~3-5%
- **Buttons:** "Yes -- inherited before 2020 (stretch IRA)" | "Yes -- inherited 2020 or later (10-year rule)" | "Yes -- I'm a spouse beneficiary" | "No" | "Skip"

### GAP 6.4 -- SIMPLE IRA / 403(b) / 457(b) Contributions
- **Question:** "Your retirement contribution: is it specifically to a 403(b), 457(b), or SIMPLE IRA? (Different contribution limits apply)"
- **Who:** Government/nonprofit employees, teachers, small employer workers
- **IRS Form:** W-2 Box 12 (codes E, G, H, S, etc.)
- **Commonality:** ~10-12%
- **Buttons:** "403(b)" | "457(b)" | "SIMPLE IRA" | "None of these (regular 401k)" | "Skip"

### GAP 6.5 -- Catch-Up Contributions
- **Question:** "Are you age 50 or older? You may be eligible for catch-up contributions ($7,500 extra for 401k, $1,000 extra for IRA)."
- **Who:** Age 50+, contributing to retirement accounts
- **IRS Form:** W-2 Box 12, Form 1040 Schedule 1 Line 20
- **Commonality:** ~15% of retirement contributors
- **Buttons:** "Yes -- I make catch-up contributions" | "Yes -- but I don't currently" | "Under 50" | "Skip"

### GAP 6.6 -- Mega Backdoor Roth (After-Tax 401k Contributions)
- **Question:** "Does your employer 401(k) plan allow after-tax contributions beyond the $23,500 limit? (Mega Backdoor Roth strategy)"
- **Who:** High-income W-2 employees at companies with permissive 401k plans
- **IRS Form:** Form 1099-R (in-plan conversion), Form 8606
- **Commonality:** ~1-2% (growing in tech/large companies)
- **Buttons:** "Yes -- my plan allows it" | "No / Not sure" | "Skip"

### GAP 6.7 -- 72(t) / SEPP Distributions
- **Question:** "Are you taking Substantially Equal Periodic Payments (SEPP / 72t) from a retirement account to avoid the early withdrawal penalty?"
- **Who:** Under 59.5 taking systematic distributions; modification triggers retroactive penalties
- **IRS Form:** Form 5329 (penalty exception), Form 1099-R
- **Commonality:** ~0.5-1%
- **Buttons:** "Yes" | "No" | "Skip"

---

## 7. MISSING DEPENDENT & FAMILY SITUATIONS

### GAP 7.1 -- Qualifying Relative (Non-Child) Dependent
- **Question:** "Besides children, do you support any other dependents? (Elderly parent, sibling, other relative who lives with you and earns less than $5,050)"
- **Who:** Anyone; qualifying relative dependent rules are different from qualifying child
- **IRS Form:** Form 1040 (dependent section), Schedule 8812 ($500 Other Dependent Credit)
- **Commonality:** ~5-8%
- **Buttons:** "Elderly parent" | "Other relative (sibling, grandparent, etc.)" | "Non-relative who lives with me" | "No" | "Skip"

### GAP 7.2 -- Multiple Support Agreement
- **Question:** "Do you share the financial support of a dependent with other family members? (Multiple Support Agreement -- Form 2120)"
- **Who:** Families sharing support of elderly parent or other relative
- **IRS Form:** Form 2120
- **Commonality:** ~1-2%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 7.3 -- Disabled Dependent
- **Question:** "Is any of your dependents permanently and totally disabled? (This affects credit eligibility and does not have an age limit for qualifying child status)"
- **Who:** Anyone with dependents
- **IRS Form:** Form 1040 dependent section, Schedule 8812, Schedule R
- **Commonality:** ~2-3%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 7.4 -- Child's Social Security Number vs ITIN
- **Question:** "Do all your dependents have Social Security Numbers? (Required for CTC; ITIN dependents get $500 Other Dependent Credit instead)"
- **Who:** Mixed-status families; common in immigrant communities
- **IRS Form:** Schedule 8812
- **Commonality:** ~2-3%
- **Buttons:** "All have SSNs" | "Some have ITINs" | "Skip"

### GAP 7.5 -- Student Dependent Age 19-23
- **Question:** "Is your dependent age 19-23 a full-time student? (Full-time students under 24 qualify as qualifying children if they don't provide more than half their own support)"
- **Who:** Parents of college-age children
- **IRS Form:** Form 1040 dependent section
- **Commonality:** ~8-10%
- **Buttons:** "Yes -- full-time student" | "No -- not a full-time student" | "Skip"

### GAP 7.6 -- Head of Household Eligibility Verification
- **Question:** "You selected Head of Household. To confirm: Did you pay more than half the cost of maintaining your home, AND did a qualifying person live with you for more than half the year?"
- **Who:** All HoH filers; most commonly audited filing status
- **IRS Form:** Form 1040 filing status, Publication 501
- **Commonality:** ~15% of filers claim HoH
- **Buttons:** "Yes -- I meet both requirements" | "I'm not sure" | "I should probably file as Single" | "Skip"

### GAP 7.7 -- Qualifying Surviving Spouse Details
- **Question:** "You selected Qualifying Surviving Spouse. To confirm: Did your spouse die in the prior 2 years, and do you have a dependent child living with you?"
- **Who:** QSS filers; rare but important validation
- **IRS Form:** Form 1040 filing status
- **Commonality:** <0.5%
- **Buttons:** "Yes -- spouse died in prior 2 years and I have dependent child" | "I should file differently" | "Skip"

### GAP 7.8 -- Divorced/Separated MFS in Community Property State
- **Question:** "You're filing Married Filing Separately in a community property state. Are you aware that community property rules require you to split community income 50/50 with your spouse?"
- **Who:** MFS filers in AZ, CA, ID, LA, NV, NM, TX, WA, WI
- **IRS Form:** Form 8958 (Allocation of Tax Amounts Between Certain Individuals in Community Property States)
- **Commonality:** ~1-2% of MFS filers
- **Buttons:** "Yes -- I understand" | "I need more information" | "Skip"

---

## 8. MISSING LIFE EVENT FOLLOW-UP CHAINS

### GAP 8.1 -- Home Purchase -- Mortgage Points
- **Question:** "For the home you bought: did you pay mortgage points (origination fees) at closing? (Points may be fully deductible in the year of purchase)"
- **Who:** Follow-up for event_bought_home
- **IRS Form:** Schedule A Line 8b, Form 1098 Box 2
- **Commonality:** ~60% of home buyers pay points
- **Buttons:** "Yes" | "No" | "Not sure (check closing statement)" | "Skip"

### GAP 8.2 -- Home Purchase -- First-Time Homebuyer IRA Withdrawal
- **Question:** "Did you withdraw from an IRA to help buy your first home? (Up to $10,000 is penalty-free for first-time homebuyers)"
- **Who:** First-time homebuyers under 59.5 who took IRA distributions
- **IRS Form:** Form 5329 (exception code 09)
- **Commonality:** ~3-5% of first-time buyers
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 8.3 -- Home Sale -- Gain Amount
- **Question:** "Approximately how much profit (gain) did you make on the home sale? (Purchase price vs sale price minus improvements)"
- **Who:** Follow-up for home sale
- **IRS Form:** Form 1040 Schedule D, Form 8949
- **Commonality:** All home sellers
- **Buttons:** "Under $100,000" | "$100,000 - $250,000" | "$250,000 - $500,000" | "Over $500,000" | "Loss" | "Skip"

### GAP 8.4 -- Home Sale -- Partial Exclusion
- **Question:** "Did you live in the home less than 2 years but have a qualifying reason for a partial exclusion? (Job change, health reasons, unforeseen circumstances)"
- **Who:** Home sellers who lived there <2 years
- **IRS Form:** Section 121(c) partial exclusion
- **Commonality:** ~2-3% of home sellers
- **Buttons:** "Job-related move" | "Health reasons" | "Unforeseen circumstances" | "None of these" | "Skip"

### GAP 8.5 -- Marriage Mid-Year -- MFS vs MFJ Decision
- **Question:** "You got married this year. Would you like us to compare Married Filing Jointly vs Married Filing Separately to see which saves more?"
- **Who:** Follow-up for event_married
- **IRS Form:** Form 1040 filing status
- **Commonality:** All newly married couples
- **Buttons:** "Yes -- compare both" | "We'll file jointly" | "We'll file separately" | "Skip"

### GAP 8.6 -- Divorce -- Decree Year & Property Transfers
- **Question:** "When was your divorce finalized? Did you transfer any property as part of the settlement? (Property transfers incident to divorce are generally tax-free)"
- **Who:** Follow-up for event_divorced
- **IRS Form:** Section 1041 (property transfers), alimony determination
- **Commonality:** All divorced filers
- **Buttons:** "Finalized this year" | "Finalized prior year" | "Still pending (separated)" | "Skip"

### GAP 8.7 -- Inheritance -- Type and Amount
- **Question:** "What did you inherit? (Inherited assets generally get a stepped-up basis, meaning no tax on the appreciation during the deceased person's lifetime)"
- **Who:** Follow-up for event_inheritance
- **IRS Form:** Various (no direct inheritance tax form, but stepped-up basis affects Schedule D)
- **Commonality:** All inheritors
- **Buttons:** "Cash" | "Real estate" | "Investment accounts" | "Retirement account (IRA/401k)" | "Business interest" | "Multiple types" | "Skip"

### GAP 8.8 -- Inheritance -- IRD (Income in Respect of Decedent)
- **Question:** "Did you inherit a retirement account or other income item that the deceased earned but hadn't received? (Income in Respect of a Decedent is taxable to you)"
- **Who:** Follow-up for inheritance of retirement accounts or accrued income
- **IRS Form:** Form 1040 (various income lines), possible Section 691(c) deduction
- **Commonality:** ~50% of inheritors with retirement accounts
- **Buttons:** "Yes -- inherited retirement account" | "Yes -- other accrued income" | "No -- inherited non-IRD assets" | "Skip"

### GAP 8.9 -- Job Change -- 401k Rollover
- **Question:** "When you changed jobs, what did you do with your old employer's retirement plan?"
- **Who:** Follow-up for event_job_change
- **IRS Form:** Form 1099-R (if distributed), Form 5498 (if rolled over)
- **Commonality:** ~40-50% of job changers have retirement accounts
- **Buttons:** "Rolled over to new employer plan" | "Rolled over to IRA" | "Cashed out (took a distribution)" | "Left it with old employer" | "Skip"

### GAP 8.10 -- Death of Taxpayer / Spouse
- **Question:** "I'm sorry for your loss. Did your spouse pass away during the tax year? (This affects filing status, final return requirements, and estate considerations)"
- **Who:** Surviving spouses; not currently a life event option
- **IRS Form:** Form 1040 (final return for deceased), Form 1041 (estate return if needed)
- **Commonality:** ~1-2%
- **Buttons:** "Yes -- filing final joint return" | "Not applicable"
- **NOTE:** Add "Spouse passed away" to life events list

---

## 9. MISSING INTERNATIONAL & EXPATRIATE SITUATIONS

### GAP 9.1 -- Foreign Earned Income Exclusion (FEIE)
- **Question:** "Did you live and work outside the US for a full tax year (or 330 days in a 12-month period)? You may qualify to exclude up to $130,000 of foreign earned income."
- **Who:** Follow-up for worked_abroad
- **IRS Form:** Form 2555
- **Commonality:** ~0.5-1%
- **Buttons:** "Yes -- bona fide residence test" | "Yes -- physical presence test (330 days)" | "No -- short-term assignment" | "Skip"

### GAP 9.2 -- Foreign Housing Exclusion/Deduction
- **Question:** "While living abroad, did your housing costs exceed $19,600 (base amount)? You may qualify for the foreign housing exclusion or deduction."
- **Who:** Follow-up for FEIE filers
- **IRS Form:** Form 2555 Part VI
- **Commonality:** ~50% of FEIE filers
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 9.3 -- FBAR Detail ($10K+ Foreign Accounts)
- **Question:** "You mentioned foreign accounts over $10,000. How many accounts do you have, and in which countries? (FBAR is due April 15 with automatic extension to October 15)"
- **Who:** Follow-up for has_foreign_accounts
- **IRS Form:** FinCEN Form 114 (FBAR), not filed with tax return
- **Commonality:** 100% of those with qualifying accounts
- **Buttons:** "1-2 accounts" | "3-5 accounts" | "More than 5" | "Skip"

### GAP 9.4 -- FATCA (Form 8938) -- Specified Foreign Financial Assets
- **Question:** "Is the total value of all your foreign financial assets over $50,000 at year-end (or $75,000 at any time during the year)? (Higher thresholds for MFJ and expats)"
- **Who:** Anyone with foreign accounts; separate from FBAR
- **IRS Form:** Form 8938
- **Commonality:** ~1-2%
- **Buttons:** "Yes" | "No" | "Not sure" | "Skip"

### GAP 9.5 -- Ownership in Foreign Corporation
- **Question:** "Do you own 10% or more of a foreign corporation? (Reporting required on Forms 5471 and/or 8865)"
- **Who:** Business owners with foreign entities; severe penalties for non-filing ($10,000+ per form)
- **IRS Form:** Form 5471 (foreign corp), Form 8865 (foreign partnership)
- **Commonality:** ~0.5-1%
- **Buttons:** "Yes -- foreign corporation" | "Yes -- foreign partnership" | "No" | "Skip"

### GAP 9.6 -- Foreign Trust
- **Question:** "Are you a beneficiary of, or did you make transfers to, a foreign trust?"
- **Who:** Beneficiaries/grantors of foreign trusts; severe penalties for non-reporting
- **IRS Form:** Form 3520 (Annual Return to Report Transactions with Foreign Trusts), Form 3520-A
- **Commonality:** ~0.5%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 9.7 -- Treaty-Based Positions
- **Question:** "Are you claiming any tax treaty benefits? (Common for foreign nationals on visas, or US residents with income from treaty countries)"
- **Who:** Non-resident aliens, dual-status filers, or anyone claiming treaty benefits
- **IRS Form:** Form 8833 (Treaty-Based Return Position Disclosure)
- **Commonality:** ~1-2%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 9.8 -- PFIC (Passive Foreign Investment Company)
- **Question:** "Do you own shares in foreign mutual funds or foreign companies classified as PFICs? (Most foreign mutual funds are PFICs with harsh tax treatment)"
- **Who:** US persons investing directly in foreign mutual funds/ETFs
- **IRS Form:** Form 8621
- **Commonality:** ~1-2% of investors (higher among expats)
- **Buttons:** "Yes" | "No" | "Not sure" | "Skip"

### GAP 9.9 -- Nonresident Alien Spouse Election
- **Question:** "Is your spouse a nonresident alien? Would you like to elect to treat them as a US resident for tax purposes? (Allows MFJ filing but subjects worldwide income to US tax)"
- **Who:** US citizen/resident married to nonresident alien
- **IRS Form:** Form 1040 (election statement), Section 6013(g)
- **Commonality:** ~1-2%
- **Buttons:** "Yes -- elect US resident treatment" | "No -- file MFS/NRA" | "Skip"

---

## 10. MISSING BUSINESS & SELF-EMPLOYMENT FOLLOW-UPS

### GAP 10.1 -- Business Losses and NOL
- **Question:** "Is your business operating at a net loss this year? Do you have net operating losses from prior years to carry forward?"
- **Who:** Business owners reporting losses
- **IRS Form:** Schedule C (current loss), Form 1040 Schedule 1, NOL carryforward worksheet
- **Commonality:** ~15-20% of Schedule C filers have losses
- **Buttons:** "Current year loss only" | "Prior year NOL carryforward" | "Both" | "No losses" | "Skip"

### GAP 10.2 -- Excess Business Loss Limitation
- **Question:** "Are your total business losses exceeding $305,000 (single) or $610,000 (MFJ)? The excess is converted to an NOL carryforward."
- **Who:** High-income filers with large business losses
- **IRS Form:** Form 461
- **Commonality:** ~1-2% of business filers
- **Buttons:** "Yes" | "No" | "Not sure" | "Skip"

### GAP 10.3 -- Business Use of Listed Property
- **Question:** "Do you use any of these for both business and personal: vehicle, computer, camera equipment, cell phone? What's the business-use percentage?"
- **Who:** All business/SE filers with listed property
- **IRS Form:** Form 4562 Part V
- **Commonality:** ~40% of Schedule C filers
- **Buttons:** "Over 50% business use" | "Under 50% business use" | "100% business use" | "No listed property" | "Skip"

### GAP 10.4 -- Meals & Travel Expenses
- **Question:** "Did you have business travel or client meal expenses this year?"
- **Who:** All business/SE filers
- **IRS Form:** Schedule C Lines 24a-24b
- **Commonality:** ~50% of Schedule C filers
- **Buttons:** "Yes -- significant travel" | "Yes -- mainly meals" | "Both" | "No travel or meal expenses" | "Skip"

### GAP 10.5 -- Business Insurance (Deductible)
- **Question:** "Do you pay for any business insurance? (Liability, E&O, professional, cyber, business property)"
- **Who:** Business/SE filers
- **IRS Form:** Schedule C Line 15
- **Commonality:** ~30% of Schedule C filers
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 10.6 -- Accounting Method
- **Question:** "What accounting method does your business use?"
- **Who:** Business owners; important for timing of income/expense recognition
- **IRS Form:** Schedule C Line F
- **Commonality:** 100% of business filers (most use cash)
- **Buttons:** "Cash basis" | "Accrual basis" | "Not sure" | "Skip"

### GAP 10.7 -- Inventory
- **Question:** "Does your business carry inventory? (Products for sale, raw materials)"
- **Who:** Product-based businesses
- **IRS Form:** Schedule C Lines 35-42 (Cost of Goods Sold)
- **Commonality:** ~15-20% of Schedule C filers
- **Buttons:** "Yes" | "No -- service-based business" | "Skip"

### GAP 10.8 -- Sale of Business Property (Form 4797)
- **Question:** "Did you sell or dispose of any business property or equipment this year?"
- **Who:** Business owners who sold depreciated assets
- **IRS Form:** Form 4797
- **Commonality:** ~3-5% of business filers
- **Buttons:** "Yes -- sold at a gain" | "Yes -- sold at a loss" | "Yes -- property was destroyed/stolen" | "No" | "Skip"

### GAP 10.9 -- Retirement Plan for Employees
- **Question:** "You mentioned having employees. Do you offer a retirement plan for them? (SIMPLE IRA, SEP-IRA, 401k -- employer contributions are deductible)"
- **Who:** Follow-up for has_employees
- **IRS Form:** Schedule C Line 19 (pension/profit sharing), Form 5500 (if applicable)
- **Commonality:** ~10% of employer businesses
- **Buttons:** "Yes" | "No -- interested in learning more" | "No" | "Skip"

### GAP 10.10 -- Qualified Business Income Deduction (Section 199A) -- W-2 Wage Limitation
- **Question:** "For QBI deduction purposes: how much did your business pay in total W-2 wages to employees?"
- **Who:** Business owners with income above $191,950 (single) / $383,900 (MFJ) where W-2 wage limitation applies
- **IRS Form:** Form 8995-A
- **Commonality:** ~10-15% of QBI claimants hit wage limitation
- **Buttons:** "Under $100,000" | "$100,000 - $250,000" | "Over $250,000" | "No W-2 employees" | "Skip"

---

## 11. MISSING RENTAL & PASSIVE ACTIVITY GAPS

### GAP 11.1 -- Short-Term Rentals (Airbnb / VRBO)
- **Question:** "Is your rental property a short-term rental (average stay under 7 days)? Short-term rentals have different passive activity and SE tax rules."
- **Who:** Rental owners; short-term rentals may not be passive if material participation exists
- **IRS Form:** Schedule E or Schedule C (if substantial services provided)
- **Commonality:** ~15-20% of rental owners
- **Buttons:** "Yes -- short-term (under 7 days avg)" | "Yes -- but I provide substantial hotel-like services" | "No -- long-term rental" | "Skip"

### GAP 11.2 -- Personal Use Days
- **Question:** "Did you or your family use the rental property personally for more than 14 days (or 10% of rental days)? This limits deductible expenses."
- **Who:** Rental owners, especially vacation property owners
- **IRS Form:** Schedule E, Form 8582 (personal use limitation)
- **Commonality:** ~10% of rental owners
- **Buttons:** "Yes -- personal use exceeds limit" | "No -- minimal personal use" | "Not sure" | "Skip"

### GAP 11.3 -- Rental at Fair Market Value
- **Question:** "Do you rent to a family member or anyone below fair market value? (Below-FMV rentals have limited deductions)"
- **Who:** Rental owners renting to relatives
- **IRS Form:** Schedule E, Section 280A
- **Commonality:** ~5% of rental owners
- **Buttons:** "Yes -- below market rent" | "No -- fair market rent" | "Skip"

### GAP 11.4 -- Cost Segregation Study
- **Question:** "Have you done or are you considering a cost segregation study on your rental property? (Can accelerate depreciation deductions significantly)"
- **Who:** Rental owners with properties worth $500K+; RE professionals benefit most
- **IRS Form:** Form 4562, Schedule E
- **Commonality:** ~2-5% of rental owners
- **Buttons:** "Yes -- already completed" | "Interested in learning more" | "No" | "Skip"

### GAP 11.5 -- Rental Property Conversion
- **Question:** "Did you convert a personal residence to a rental property (or vice versa) this year?"
- **Who:** Anyone who changed property use
- **IRS Form:** Schedule E, Form 4562 (new depreciation basis is lesser of FMV or adjusted basis at conversion)
- **Commonality:** ~2-3%
- **Buttons:** "Personal to rental" | "Rental to personal" | "No conversion" | "Skip"

### GAP 11.6 -- $25,000 Rental Loss Allowance -- AGI Phase-Out
- **Question:** "Your AGI may affect your ability to deduct rental losses. Is your modified AGI over $100,000? (The $25,000 rental loss allowance phases out between $100K-$150K)"
- **Who:** Active participants in rental activities with losses
- **IRS Form:** Form 8582
- **Commonality:** ~20-30% of rental loss claimants
- **Buttons:** "Under $100K (full $25K allowance)" | "$100K - $150K (partial)" | "Over $150K (no allowance unless RE professional)" | "Skip"

---

## 12. MISSING STATE-SPECIFIC SITUATIONS

### GAP 12.1 -- Community Property State Allocation
- **Question:** "You're filing in a community property state (AZ, CA, ID, LA, NV, NM, TX, WA, WI). Are you filing separately from your spouse? Community property rules require special income allocation."
- **Who:** MFS filers or RDP in community property states
- **IRS Form:** Form 8958
- **Commonality:** ~2-3% of MFS filers in these states
- **Buttons:** "Yes -- filing separately in community property state" | "Filing jointly" | "Skip"

### GAP 12.2 -- State 529 Deduction Amount
- **Question:** "How much did you contribute to a 529 plan this year? (Your state may offer a deduction; limits vary by state)"
- **Who:** Follow-up for has_529; state-specific amounts
- **IRS Form:** State return only (no federal deduction for 529 contributions)
- **Commonality:** ~10% of parents
- **Buttons:** "Under $5,000" | "$5,000 - $10,000" | "Over $10,000" | "Skip"

### GAP 12.3 -- State Disability Insurance (SDI/TDI)
- **Question:** "Did you pay State Disability Insurance (SDI/TDI) or Family Leave Insurance (FLI/PFL) premiums? (Applies in CA, NJ, NY, HI, RI, etc.)"
- **Who:** W-2 employees in states with mandatory disability programs
- **IRS Form:** State return (may affect itemized deductions)
- **Commonality:** ~15-20% of W-2 employees in applicable states
- **Buttons:** "Yes" | "No / Not applicable in my state" | "Skip"

### GAP 12.4 -- State-Specific Credits
- **Question:** "Does your state offer any of these credits? (Property tax circuit breaker, renter's credit, historic preservation, angel investor, film production, etc.)"
- **Who:** Varies by state; too numerous to list individually in chatbot but should prompt awareness
- **IRS Form:** State return only
- **Commonality:** Varies widely
- **Buttons:** "I may have state-specific credits" | "Not sure" | "No" | "Skip"

### GAP 12.5 -- Local Income Tax
- **Question:** "Do you live or work in a city/county with local income tax? (Common in OH, PA, MD, IN, KY, NY, etc.)"
- **Who:** Residents/workers in localities with income tax
- **IRS Form:** Local return, affects SALT deduction on Schedule A
- **Commonality:** ~15% of filers (heavy in certain states)
- **Buttons:** "Yes" | "No" | "Not sure" | "Skip"

---

## 13. MISSING IDENTITY & FILING LOGISTICS

### GAP 13.1 -- Prior Year Return Status
- **Question:** "Did you file a tax return last year? If so, did you get a refund or owe money?"
- **Who:** Everyone; needed for refund application to this year's estimated tax, prior year AGI for e-file PIN
- **IRS Form:** E-file validation (prior year AGI), estimated tax payments
- **Commonality:** ~95% filed prior year
- **Buttons:** "Filed -- got a refund" | "Filed -- owed money" | "Filed -- broke even" | "Didn't file last year" | "Skip"

### GAP 13.2 -- Extension Filed
- **Question:** "Have you already filed an extension for this tax year? (Form 4868)"
- **Who:** Anyone filing after April 15
- **IRS Form:** Form 4868
- **Commonality:** ~10-15% of filers
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 13.3 -- Identity Protection PIN
- **Question:** "Do you have an IRS Identity Protection PIN (IP PIN)?"
- **Who:** Anyone; IRS now offers IP PINs to all taxpayers voluntarily
- **IRS Form:** Form 1040 IP PIN field
- **Commonality:** ~5-8% (growing)
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 13.4 -- Amended Return Needed
- **Question:** "Do you need to amend a prior year return? (Received a corrected W-2 or 1099, forgot income or deduction, filing status change)"
- **Who:** Anyone; 1040-X within 3 years of original filing
- **IRS Form:** Form 1040-X
- **Commonality:** ~3-5%
- **Buttons:** "Yes" | "No" | "Skip"

### GAP 13.5 -- Taxpayer Identification Number
- **Question:** "Do you and your spouse (if applicable) have Social Security Numbers? Or do you use ITINs?"
- **Who:** Anyone; ITIN filers cannot claim certain credits (EITC)
- **IRS Form:** Form 1040
- **Commonality:** ~5%
- **Buttons:** "SSN for all filers" | "One or more ITINs" | "Skip"

### GAP 13.6 -- Direct Deposit / Refund Preference
- **Question:** "If you're due a refund, how would you like to receive it?"
- **Who:** Everyone expecting a refund
- **IRS Form:** Form 1040 Lines 35-37, Form 8888 (split refund)
- **Commonality:** ~75% get refunds
- **Buttons:** "Direct deposit" | "Paper check" | "Apply to next year's estimated tax" | "Split between accounts" | "Buy US savings bonds" | "Skip"

---

## 14. MISSING SITUATION LAYERS (Cross-Cutting)

These are situations that can affect ANY income type and are not currently captured:

### LAYER 14.1 -- Disability Income
- **Question:** "Do you receive disability income? (Social Security Disability, employer disability plan, VA disability)"
- **Who:** Anyone with disabilities
- **IRS Form:** Form 1040 Lines 4-5 (pension/annuity), Schedule R
- **Commonality:** ~5-8%
- **Buttons:** "Social Security Disability (SSDI)" | "VA Disability (tax-free)" | "Employer disability plan" | "Workers' compensation (tax-free)" | "No" | "Skip"

### LAYER 14.2 -- Bankruptcy
- **Question:** "Did you file for bankruptcy during the tax year? (This affects COD income exclusion, NOL treatment, and separate estate return)"
- **Who:** Anyone; Chapter 7 creates a separate taxable estate
- **IRS Form:** Form 982, separate return for bankruptcy estate
- **Commonality:** ~1-2%
- **Buttons:** "Chapter 7" | "Chapter 13" | "Chapter 11" | "No" | "Skip"

### LAYER 14.3 -- Identity Theft (Tax-Related)
- **Question:** "Have you been a victim of tax-related identity theft? (Someone filed a fraudulent return using your SSN)"
- **Who:** Anyone; affects filing procedures
- **IRS Form:** Form 14039 (Identity Theft Affidavit)
- **Commonality:** ~1-2%
- **Buttons:** "Yes" | "No" | "Skip"

### LAYER 14.4 -- Educator Expenses (Spouse)
- **Question:** "Is your spouse also a K-12 educator? (Each spouse can deduct up to $300, for a combined $600)"
- **Who:** MFJ where one spouse already identified as educator
- **IRS Form:** Form 1040 Schedule 1 Line 11
- **Commonality:** ~3-5% of MFJ with educators
- **Buttons:** "Yes" | "No" | "Skip"

### LAYER 14.5 -- Dependent Care Benefits from Employer (Box 10)
- **Question:** "Did your employer provide dependent care benefits shown in W-2 Box 10? (Up to $5,000 may be excluded from income)"
- **Who:** W-2 employees with employer DC benefits
- **IRS Form:** Form 2441 Part III
- **Commonality:** ~5-8%
- **Buttons:** "Yes" | "No" | "Skip"

### LAYER 14.6 -- Student Status (Yourself)
- **Question:** "Were you a full-time or part-time student during the tax year?"
- **Who:** Anyone; affects EITC eligibility (full-time students under 24), education credits, and standard deduction for dependents
- **IRS Form:** Various
- **Commonality:** ~10-12%
- **Buttons:** "Full-time student" | "Part-time student" | "Not a student" | "Skip"

### LAYER 14.7 -- Legally Blind
- **Question:** "Are you or your spouse legally blind? (Additional standard deduction amount applies)"
- **Who:** Anyone; $1,850 extra for single, $1,500 for MFJ per blind person
- **IRS Form:** Form 1040 Standard Deduction section
- **Commonality:** ~2-3%
- **Buttons:** "Yes -- taxpayer" | "Yes -- spouse" | "Both" | "No" | "Skip"

### LAYER 14.8 -- State Withholding
- **Question:** "How much state income tax was withheld from your paychecks? (Check your W-2 Box 17)"
- **Who:** W-2 employees in states with income tax
- **IRS Form:** State return, Schedule A (SALT deduction)
- **Commonality:** ~70% of W-2 employees
- **Buttons:** "Under $2,000" | "$2,000 - $5,000" | "$5,000 - $10,000" | "Over $10,000" | "Not sure" | "Skip"

### LAYER 14.9 -- Additional Medicare Tax
- **Question:** "Is your earned income over $200,000 (single) or $250,000 (MFJ)? You may owe the 0.9% Additional Medicare Tax."
- **Who:** High earners; not currently mentioned
- **IRS Form:** Form 8959
- **Commonality:** ~5-8%
- **Buttons:** "Yes" | "No" | "Skip"

### LAYER 14.10 -- Underpayment Penalty Exposure
- **Question:** "Did you owe more than $1,000 on last year's return? If so, did you increase your withholding or make estimated payments to avoid an underpayment penalty?"
- **Who:** Anyone who may have underpaid; Form 2210
- **IRS Form:** Form 2210 / 2210-F
- **Commonality:** ~10-15%
- **Buttons:** "May be exposed" | "I've adjusted" | "Not applicable" | "Skip"

---

## 15. MISSING FOLLOW-UP CHAIN MAP

For each existing question, these follow-up chains are missing:

| Trigger Answer | Missing Follow-Up | Form |
|---|---|---|
| `has_investments` + interest | Interest type: taxable, tax-exempt, OID | Schedule B, Line 2a |
| `has_investments` + dividends | Dividend amount, qualified vs ordinary | Schedule B, Line 3a/3b |
| `has_iso` or `has_nso` | Exercise date, # shares, strike price, FMV | Form 3921, 6251 |
| `has_rsu` | Vesting date, FMV at vest, shares sold | W-2 Box 12, Form 8949 |
| `has_espp` | Grant date, purchase date, holding period | Form 3922, 8949 |
| `roth_converted` | Amount converted, IRA basis (Form 8606) | Form 8606, 1040 |
| `has_k1_income` | K-1 type: partnership, S-Corp, trust/estate | Schedule E, 1065/1120S/1041 |
| `has_k1_income` | K-1 character: ordinary, capital gain, 199A, rental | K-1 Boxes 1-20 |
| `is_educator` | Educator expense dollar amount | Schedule 1 Line 11 |
| `has_student_loans` | Student loan interest dollar amount | Schedule 1 Line 21 |
| `event_married` | MFJ vs MFS comparison | Filing status |
| `event_bought_home` | Points, PMI, property tax | Schedule A, 1098 |
| `has_mortgage` | Is mortgage pre- or post-12/15/2017? ($750K vs $1M limit) | Schedule A |
| `active_farm` | Farm income amount, crop insurance, CRP payments | Schedule F |
| `gambling_winnings` | Gambling income amount | Schedule 1 Line 8b |
| `has_household_employee` | Wages paid, taxes withheld | Schedule H |
| `combat_zone` | Months in combat zone, combat pay amount | W-2, Form 1040 |
| `has_loss_carryforward` | Carryforward amount | Schedule D, Capital Loss CW |
| `has_charitable` > $5K | Non-cash donation detail, appraisal required? | Form 8283 |
| `rental_net_loss` | Is AGI under $150K? Active participation? | Form 8582 |
| `aca_with_subsidy` | 1095-A reconciliation amounts | Form 8962 |
| `has_hsa` | HSA contribution amount, catch-up (55+) | Form 8889 |
| `has_401k` or equivalent | Contribution amount, catch-up | W-2 Box 12 |
| `multiple_energy` | Breakdown: solar cost, EV cost, improvement cost | Form 5695, 8936 |
| `has_depreciation` | Total depreciation claimed, recapture risk | Form 4562, 4797 |

---

## 16. PRIORITY MATRIX

### TIER 1 -- HIGH IMPACT, HIGH FREQUENCY (Add Immediately)
| Gap | Est. % Returns | Revenue Impact |
|---|---|---|
| 4.1 EITC | 20-25% | Very High (refundable) |
| 2.1 Interest income ($1,500+ = Schedule B) | 15% | Medium |
| 2.4 1099-G state refunds | 20-25% | Medium |
| 2.13 1099-K payment platforms | 10-15% | High (growing) |
| 4.3 Saver's Credit | 10% | Medium (underclaimed) |
| 14.1 Disability income | 5-8% | High |
| 4.9 AOTC vs LLC distinction | 12% | High (up to $2,500) |
| 3.7 Non-cash charitable > $500 | 10-15% of itemizers | Medium |
| 5.6 NIIT (3.8% surtax) | 5-8% | Very High |
| 14.9 Additional Medicare Tax | 5-8% | High |
| 8.9 Job change 401k rollover | ~5% | High (avoids 10% penalty) |

### TIER 2 -- MODERATE IMPACT, MODERATE FREQUENCY (Add Soon)
| Gap | Est. % Returns | Revenue Impact |
|---|---|---|
| 2.8 Cancellation of debt (1099-C) | 3-5% | High |
| 2.17 Royalty income | 2-4% | Medium |
| 6.1 Backdoor Roth | 3-5% | High |
| 6.3 Inherited IRA | 3-5% | High |
| 3.8 QCD for seniors | 5-8% of seniors | High |
| 3.9 Casualty/disaster losses | 1-2% (spikes) | High |
| 4.5 Foreign tax credit detail | 10-12% | Medium |
| 11.1 Short-term rental (Airbnb) | 15-20% of rentals | High |
| 1.1 Farm income | 2-3% | High |
| 8.1 Home purchase points | ~3-5% | Medium |
| 2.12 1099-R breakdown (annuity, etc.) | 20% | Medium |

### TIER 3 -- LOW FREQUENCY BUT HIGH PENALTY/COMPLIANCE RISK
| Gap | Est. % Returns | Penalty Risk |
|---|---|---|
| 9.4 FATCA (Form 8938) | 1-2% | $10,000+ penalty |
| 9.5 Foreign corporation (Form 5471) | 0.5-1% | $10,000+ per form |
| 9.6 Foreign trust (Form 3520) | 0.5% | 35% of distribution penalty |
| 9.8 PFIC (Form 8621) | 1-2% | Punitive tax rates |
| 4.16 QSBS exclusion | 0.5% | $10M+ exclusion missed |
| 5.3 Like-kind exchange (1031) | 1-2% | Massive deferral |
| 10.2 Excess business loss | 1-2% | Compliance |
| 14.2 Bankruptcy | 1-2% | Complex |

### TIER 4 -- NICE TO HAVE / EDGE CASES
| Gap | Est. % Returns |
|---|---|
| 2.6 Jury duty pay | 3-5% (tiny amounts) |
| 2.15 Bartering income | <1% |
| 3.6 Archer MSA | <0.5% |
| 1.5 Clergy | <1% |
| 6.7 72(t) / SEPP | 0.5-1% |
| 7.2 Multiple support agreement | 1-2% |
| 2.14 1099-OID | 2-3% |

---

## SUMMARY STATISTICS

- **Current questions in registry:** 79
- **Gaps identified in this audit:** 119
- **Tier 1 (add immediately):** 11 gaps
- **Tier 2 (add soon):** 11 gaps
- **Tier 3 (compliance risk):** 8 gaps
- **Tier 4 (edge cases):** 7 gaps
- **Remaining (important but lower priority):** 82 gaps

### Critical Blind Spots (Zero Coverage Currently)
1. **EITC** -- The single most common refundable credit, affecting 20-25% of returns. No question exists.
2. **Interest/Dividend income detail** -- Schedule B triggers at $1,500. No amount question.
3. **1099-G / State refund taxability** -- Affects 20-25% of filers. No question exists.
4. **1099-K** -- Affects 10-15% and growing. No question exists.
5. **NIIT / Additional Medicare Tax** -- Affects 5-8% of higher-income returns. No question exists.
6. **Disability income** -- 5-8% of returns. No question exists.
7. **Inherited IRA** -- 3-5% of returns, complex SECURE Act rules. No question exists.
8. **Non-cash charitable donations** -- 10-15% of itemizers. Missing Form 8283 trigger.
9. **All international forms** -- FATCA/FBAR detail, 5471, 3520, 8621, 8833. Severe penalties for non-filing.
10. **Backdoor Roth / Form 8606** -- 3-5% of higher-income filers. Pro-rata rule is a trap.

---

*This audit covers Form 1040 lines 1-38, Schedules A-F, H, R, SE, 1-3, and Forms 982, 1116, 2120, 2210, 2441, 2555, 3520, 3903, 3921, 3922, 4137, 4562, 4684, 4797, 4868, 4952, 5329, 5471, 5695, 5884, 6198, 6251, 6252, 6781, 8283, 8332, 8582, 8606, 8615, 8621, 8689, 8801, 8824, 8833, 8839, 8853, 8863, 8880, 8889, 8910, 8936, 8938, 8949, 8958, 8959, 8960, 8962, 8995/8995-A, 8997, and 14039.*
