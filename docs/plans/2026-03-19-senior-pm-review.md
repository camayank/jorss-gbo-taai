# Senior Product Manager Review: AI Tax Advisor Flow

> Reviewer perspective: 18 years in US TaxTech. Built intake flows at Intuit (TurboTax Live), led product at Thomson Reuters (UltraTax CS online), consulted for Drake, Canopy, and two YC tax startups. Evaluated against IRS e-file quality standards, CPA workflow integration requirements, and consumer tax UX benchmarks.

---

## What I'm Evaluating

The product claims to be an AI tax advisor that computes real numbers from conversation. I'm evaluating: does the flow collect enough data to produce a defensible tax estimate, does it handle the US tax code's complexity correctly, and does the UX create the right trust signals for both taxpayers and CPAs evaluating for whitelabel.

---

## Part 1: Flow Gaps — What a Real Tax Advisor Would Ask That We Don't

### 1.1 Filing Status Is Incomplete

**Missing: Qualifying Surviving Spouse (QSS)**

The Phase 1 radio buttons offer 4 statuses. The IRS has 5. QSS (formerly Qualifying Widow/Widower) is missing from both the client UI (`advisor-flow.js` line 258) and the server Phase 1 question (line 3754). The parser in `parsers.py` DOES handle QSS via regex (`\bqualifying\s*widow`, `\bsurviving\s*spouse\b`) — but there's no button for it.

**Impact:** A surviving spouse who should file QSS (and get MFJ brackets + $30K standard deduction) will either select "Single" (wrong — $15K deduction, higher rates) or "Head of Household" (wrong qualifications). This is a ~$3,000-$5,000 tax difference on a $100K income.

**Fix:** Add 5th radio option: "Qualifying Surviving Spouse — Spouse died in 2023 or 2024, with dependent child"

### 1.2 No W-2 Withholding Collection

The flow asks total income but **never asks federal withholding** — the amount already withheld from paychecks (W-2 Box 2). This is the single most important number for determining refund vs. owed.

The `_fallback_calculation` at line 2268 reads `profile.get("federal_withholding", 0)` — but no Phase 1 or Phase 2 question ever collects this field. The only way it enters the profile is through document upload (W-2 OCR extracts Box 2) or free-text NLU parsing.

**Impact:** Every refund/owed estimate for W-2 employees is wrong. A taxpayer earning $75K with $10K withheld should see a ~$1,000 refund. Without withholding data, `refund_or_owed = 0 - total_tax` = negative (always "you owe"), which is the opposite of what 75% of taxpayers experience. This destroys credibility instantly.

**Fix:** Add Phase 2 question after income source (for W-2 employees):
"Approximately how much federal tax was withheld from your paychecks? Check your last pay stub — it's the YTD Federal Tax line."
Buttons: Under $5K, $5K-$10K, $10K-$20K, $20K-$40K, Over $40K, Not sure (use estimate)
The "Not sure" option should auto-estimate withholding at ~18% of W-2 income (close to average effective withholding).

### 1.3 No State Withholding

Same issue. `profile.get("state_withheld", 0)` is never collected. State refund/owed is always wrong.

**Fix:** Follow-up question after federal withholding (for states with income tax): "Was state income tax also withheld?" Buttons: Yes (estimate at ~4% of income), No, Not sure.

### 1.4 Married Filing Jointly vs Separately Comparison Missing

When a user selects MFJ, a real tax advisor would automatically run MFS as an alternative and show the comparison. TurboTax does this. The `FilingStatusOptimizer` in `recommendation/filing_status_optimizer.py` already does this computation — but it's never triggered in the chat flow.

**Fix:** After calculation for MFJ filers, auto-run MFS comparison and include a strategy card: "We compared MFJ vs MFS. Filing jointly saves you $X,XXX. Here's why..."

### 1.5 Prior Year Comparison Missing

No question asks about prior year taxes. "Did you owe or get a refund last year? Approximately how much?" This grounds the estimate — if a user got $3K back last year and we estimate $2.8K this year, that's credible. If we show $0 refund when they got $3K last year, they'll close the tab.

**Fix:** Add optional Phase 2 question: "Last year, did you get a refund or owe?" Buttons: Got a refund ($amount), Owed taxes ($amount), First time filing, Skip.

### 1.6 Dependents Lack Detail

"2 dependents" is not enough. The CTC requires:
- Child must be under 17 at year-end
- Child must have a valid SSN
- Other Dependent Credit ($500) applies for dependents 17+

The flow treats all dependents as CTC-eligible children. A taxpayer with a 19-year-old college student and a 15-year-old should get $2,000 CTC + $500 ODC = $2,500, not $4,000.

**Fix:** After dependents > 0, ask: "How many of your dependents are under 17?" This single follow-up correctly splits CTC vs. ODC.

### 1.7 No Health Insurance / ACA Question

The Affordable Care Act requires either coverage or penalty (brought back in some states). More importantly:
- Premium Tax Credit (Form 8962) can be worth $3,000-$12,000 for marketplace enrollees
- Excess APTC repayment can turn a refund into an owed amount
- HSA eligibility depends on HDHP enrollment

The flow never asks about health insurance.

**Fix:** Phase 2 question: "How do you get health insurance?" Buttons: Employer, Marketplace/ACA, Medicare/Medicaid, Spouse's plan, No coverage. If Marketplace: "Did you receive advance premium tax credits?" This unlocks PTC/APTC strategy cards.

### 1.8 Education Credits Not Captured

American Opportunity Tax Credit (AOTC) = $2,500 per student, 40% refundable. Lifetime Learning Credit (LLC) = $2,000. These are major credits for families with college students.

The flow never asks about education expenses. The recommendation engine has generators for education credits, but they never fire because the profile never contains education data.

**Fix:** Phase 2 question (if dependents > 0 OR age < 30): "Did you or a dependent pay college tuition in 2025?" Buttons: Yes (→ unlock AOTC/LLC strategy), No, Skip.

### 1.9 Cryptocurrency Not Specifically Asked

IRS requires crypto disposition reporting (Question 1 on Form 1040). Crypto triggers capital gains (short/long-term) and potentially wash sale issues. The parser catches `\bcrypto\b` and `\bbitcoin\b` but no question asks about it.

**Fix:** Include in the investments question: "Do you have any investment income? This includes **stocks, cryptocurrency**, dividends, or interest."

### 1.10 Life Events Not Proactively Asked

The parser detects life events reactively (user mentions "I got married"). But a real advisor proactively asks: "Did anything major change in 2025?" — because life events have massive tax implications:
- Marriage → filing status change
- Divorce → alimony (pre-2019 agreements), filing status
- Baby → +$2,000 CTC
- Home purchase → mortgage interest deduction
- Home sale → $250K/$500K exclusion (Section 121)
- Retirement → distribution planning
- Job loss → unemployment income

**Fix:** Phase 2 question: "Did any of these happen in 2025?" Multi-select: Got married, Had a baby, Bought a home, Sold a home, Changed jobs, Started a business, Retired, None of these. Each selection triggers profile flags that the engine and strategy generators already handle.

---

## Part 2: Calculation Accuracy Improvements

### 2.1 Withholding Auto-Estimate

When withholding is unknown, estimate it instead of defaulting to $0. Use: `estimated_withholding = w2_income * 0.18` for single, `* 0.15` for MFJ. This is within 10% of actual for 80% of taxpayers and gives a meaningful refund/owed estimate.

### 2.2 Standard Deduction for 65+ Is Under-Counted

The `_fallback_calculation` adds $1,950 per person 65+ for single, but should add $1,550 per spouse for MFJ (it only adds once). If both spouses are 65+, they get $3,100 additional.

### 2.3 EITC Is Missing Entirely

Earned Income Tax Credit is the largest refundable credit for low-to-moderate income workers. It's worth up to $7,830 for 3+ children. The `_fallback_calculation` has NO EITC computation. The full `FederalTaxEngine` does, but the fallback (which runs in the chat flow) doesn't.

For the chat advisor, this is critical: a single parent with 2 kids earning $35K could get $6,604 EITC. Without it, we show a much smaller refund. CPA evaluating with this scenario sees wrong numbers.

**Fix:** Add EITC computation to `_fallback_calculation`. The 2025 parameters are in `tax_year_config.py`.

### 2.4 AMT Computation Is Too Simplified

The fallback AMT only adds back SALT. Real AMT also requires:
- ISO exercise spread (not collected)
- Private activity bond interest (not collected)
- Depreciation differences (not collected)

For the fallback, at minimum add back the medical deduction difference (AMT threshold is 10% vs. 7.5% for regular tax — already fixed post-2017, so this is moot). The SALT addback is the dominant AMT trigger for high earners, so the current simplified version is 80% correct. Document the limitation rather than fix it.

---

## Part 3: UX Flow Improvements

### 3.1 Show Running Estimate After Every Answer

The biggest UX win: after the user provides filing status + income, show a preliminary estimate inline. After each subsequent answer, update it. The user sees the refund go UP (or liability go DOWN) with each answer. This is addictive and creates a "wow this actually computes" moment on every single interaction.

The engine can compute from just 2 fields. Each additional field refines. Show the delta: "Adding your mortgage deduction saves you $4,400" → user sees the estimate change in real time.

**Implementation:** After every quick action in Phase 2, if `has_basics`, silently recalculate and show a mini estimate card below the next question: "Current estimate: $X,XXX refund (updates as you add more info)"

### 3.2 Smart Follow-Up Labels

Instead of generic "Skip" buttons on every question, use contextual skip labels:
- Retirement: "I don't have retirement accounts" (not "Skip")
- Mortgage: "I rent" (not "No mortgage")
- K-1: "I don't have K-1 income" (not "Skip K-1")

Users who don't know what K-1 means will hesitate on "Skip" but confidently click "I don't have K-1 income."

### 3.3 Progress Hint Without a Progress Bar

Instead of a visible progress bar (which we removed for good reason), add a subtle text hint below each Phase 2 question: "3 more questions to go" or "Almost done — 1 more question." This maintains momentum without adding visual clutter.

### 3.4 Calculation Result Should Lead With Refund/Owed

The first thing a taxpayer wants to know: "Am I getting money back or do I owe?" The calculation response currently leads with tax position bullets (Federal Tax, State Tax, Total, Effective Rate). Restructure to lead with the emotional answer:

```
Estimated Refund: $2,340
(Based on standard withholding for your income level)

Federal Tax: $11,234
State Tax (CA): $3,421
Self-Employment Tax: $0
Total Tax: $14,655
Effective Rate: 17.1%

4 strategies found to save you an additional $3,200
```

### 3.5 Strategy Cards Should Be Ranked by Impact

Currently strategies are sorted by `(priority, -savings, -confidence)`. The user sees them in priority order. For the chat experience, sort by **savings descending** — biggest dollar impact first. The CPA evaluating wants to see the most impactful strategy at the top.

### 3.6 "What If" Scenarios After Calculation

After showing results, offer scenario buttons:
- "What if I max my 401(k)?" → recalculate with retirement_401k=23500
- "What if I file separately?" → recalculate with MFS
- "What if I bought a house?" → recalculate with mortgage_interest=15000

This is the TurboTax "explore" moment. It shows the engine's power and creates engagement.

### 3.7 Report Should Be The Natural Conclusion

After calculation + strategies, the next AI message should naturally transition:
"I've identified $X,XXX in potential savings across N strategies. Want me to compile everything into a comprehensive advisory report you can share with your CPA?"

Button: "Generate My Report →"

Not buried as one of 6 quick actions. It should be THE call to action.

---

## Part 4: Trust and Compliance

### 4.1 Show the Math

For every tax number displayed, offer an expandable "How we calculated this" section. Show the actual computation:
```
Taxable income: $75,000 - $15,000 (standard deduction) = $60,000
Tax brackets:
  10% on first $11,925 = $1,192.50
  12% on $11,926 - $48,475 = $4,385.88
  22% on $48,476 - $60,000 = $2,535.50
Federal tax = $8,113.88
```

A CPA seeing this will trust the engine. A taxpayer seeing this will trust the numbers. No other AI tax tool shows the math.

### 4.2 IRS References on Everything

Every strategy card already has `irs_reference`. Make it prominent:
"Max Out Your 401(k) — Save $3,200 — IRC §402(g), IRS Publication 560"

CPAs evaluate tools by whether they cite the correct IRC section. This is a differentiation point.

### 4.3 Accuracy Confidence with Honest Ranges

After showing "Estimated Federal Tax: $11,234", add a confidence range:
"Accuracy: ±$500 based on information provided. Add more details to narrow this."

This is honest (we're estimating from limited data), builds trust (we're not pretending to be exact), and motivates the user to answer more questions.

### 4.4 Year Validation

The advisor should confirm we're computing for 2025. A user in January 2026 might want 2024 taxes. Add a subtle confirmation in the first response: "I'll calculate your 2025 federal and state taxes." If the user says "2024 taxes" → adjust tax_year parameter.

---

## Part 5: CPA Whitelabel Evaluation Signals

### 5.1 The CPA Will Test a Known Scenario

Every CPA evaluating this will enter a scenario they already know the answer to. The most common test case:
- MFJ, 2 kids under 17, $150K W-2 income, $15K mortgage interest, CA
- Expected: ~$20K federal + ~$8K CA state, ~$6K refund (with standard withholding), $4K CTC

If our numbers are close, they're interested. If off by more than $2K, they close the tab. **The withholding gap (Section 1.2 above) is the biggest risk here** — without it, we show no refund when the CPA knows there should be one.

### 5.2 The CPA Wants Speed

A CPA won't answer 18 questions. They want to type: "MFJ, 2 kids, $150K, California, W-2, $15K mortgage" → and see numbers. The NLU parser already handles this — it can extract filing_status + dependents + income + state + income_type + mortgage_interest from a single message. But the greeting flow forces them through button clicks.

**Fix:** After the welcome message, if the user types a full sentence with multiple entities, skip the remaining Phase 1 questions and jump directly to Phase 2 or calculation. The parser already does this — the client-side questioning engine (`startIntelligentQuestioning`) just needs to check if basics are already filled before showing the next question.

### 5.3 The CPA Wants to See Entity Extraction

Show what the AI extracted: "I understood: Filing jointly, 2 dependents, $150,000 income, California, W-2 employee, $15,000 mortgage interest." This transparency shows the AI is actually parsing, not just keyword matching. If it got something wrong, the user can correct it.

---

## Part 6: Priority Implementation Order

### Must-Have Before Any CPA Demo (Critical)

1. **Add withholding question + auto-estimate fallback** — without this, every refund is wrong
2. **Add QSS to filing status** — 5th IRS-required option
3. **Add dependent age split** — CTC vs ODC accuracy
4. **Add EITC to fallback calculation** — low-income estimates are dramatically wrong
5. **Show running estimate after each answer** — the "wow" moment
6. **Lead calculation result with refund/owed** — emotional answer first
7. **Make report the natural conclusion** — not buried in button list

### Should-Have Before Public Beta Launch

8. **Add withholding auto-estimate** (18% of W-2 income when user says "Not sure")
9. **Add life events question** (multi-select)
10. **Add education credits question** (AOTC/LLC)
11. **Add health insurance question** (PTC/ACA)
12. **Show the math** (expandable computation)
13. **What-if scenario buttons** after calculation
14. **MFJ vs MFS auto-comparison** for married filers
15. **Smart skip labels** ("I rent" not "Skip mortgage")

### Nice-to-Have

16. Prior year comparison question
17. Cryptocurrency specific question
18. Year validation (2024 vs 2025)
19. Accuracy confidence ranges
20. Entity extraction transparency ("I understood: ...")
