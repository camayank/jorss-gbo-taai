# Tax Advisor - Complete Scenario Matrix

## 1. FILING STATUS COMBINATIONS (5 Primary)

| Status | Triggers | Special Rules |
|--------|----------|---------------|
| Single | Never married, divorced, legally separated | Standard deduction $15,000 |
| Married Filing Jointly (MFJ) | Married as of Dec 31 | Combined income, $30,000 std ded |
| Married Filing Separately (MFS) | Married but separate returns | Limited credits, $15,000 std ded |
| Head of Household (HOH) | Unmarried + qualifying dependent | $22,500 std ded, better brackets |
| Qualifying Surviving Spouse | Spouse died within 2 years + dependent child | Same as MFJ for 2 years |

### Edge Cases:
- Married Dec 31 → Must file MFJ or MFS (not single)
- Divorced Dec 31 → Can file single
- Spouse died during year → Can file MFJ for that year
- Common law marriage states → May be considered married
- Same-sex marriage → Recognized federally

---

## 2. INCOME TYPE COMBINATIONS (15+ Types)

### Employment Income
| Type | Forms | Special Handling |
|------|-------|------------------|
| W-2 wages | W-2 | Withholding already done |
| Multiple W-2s | Multiple W-2s | Check total withholding |
| Bonus/RSU | W-2 Box 1 | Often under-withheld |
| Tips | W-2, Form 4137 | May need additional reporting |

### Self-Employment Income
| Type | Forms | Special Handling |
|------|-------|------------------|
| Sole proprietor | Schedule C | SE tax 15.3%, QBI deduction |
| Gig economy (Uber, etc.) | 1099-NEC/K | Track mileage, expenses |
| Freelance | 1099-NEC | Quarterly estimated taxes |
| Side business | Schedule C | Hobby loss rules if no profit |

### Investment Income
| Type | Forms | Tax Treatment |
|------|-------|---------------|
| Dividends - Qualified | 1099-DIV | 0/15/20% rates |
| Dividends - Ordinary | 1099-DIV | Ordinary income rates |
| Interest | 1099-INT | Ordinary income |
| Capital gains - Short term | 1099-B | Ordinary income rates |
| Capital gains - Long term | 1099-B | 0/15/20% rates |
| Crypto | 1099-B/self-report | Each trade is taxable event |

### Passive Income
| Type | Forms | Special Rules |
|------|-------|---------------|
| Rental income | Schedule E | Passive loss rules, depreciation |
| K-1 (Partnership) | Schedule K-1 | Flow-through, QBI eligible |
| K-1 (S-Corp) | Schedule K-1 | Reasonable salary required |
| K-1 (Trust) | Schedule K-1 | Different character rules |
| Royalties | 1099-MISC | May be passive or active |

### Retirement Income
| Type | Forms | Tax Treatment |
|------|-------|---------------|
| Social Security | SSA-1099 | 0-85% taxable based on income |
| Pension | 1099-R | Usually fully taxable |
| Traditional IRA/401k | 1099-R | Fully taxable + possible penalty |
| Roth IRA | 1099-R | Tax-free if qualified |
| Required Minimum Distributions | 1099-R | Must take after 73, penalties |

### Other Income
| Type | Forms | Handling |
|------|-------|----------|
| Alimony (pre-2019) | - | Taxable to recipient |
| Gambling winnings | W-2G | Offset by losses up to winnings |
| Prizes/awards | 1099-MISC | Ordinary income |
| Unemployment | 1099-G | Taxable income |
| State tax refund | 1099-G | Taxable if itemized prior year |

---

## 3. DEDUCTION DECISION TREE

```
START: Calculate Standard Deduction
       ├── Single: $15,000
       ├── MFJ: $30,000
       ├── MFS: $15,000
       ├── HOH: $22,500
       └── QSS: $30,000

THEN: Calculate Itemized Total
       ├── SALT (capped at $10,000)
       │    ├── State income tax OR Sales tax
       │    └── Property tax
       ├── Mortgage interest (limit $750K loan)
       ├── Charitable contributions (60% AGI limit)
       ├── Medical expenses (>7.5% AGI)
       └── Casualty losses (federally declared disasters only)

COMPARE: If Itemized > Standard → Itemize
         If Standard > Itemized → Standard

EDGE CASES:
- MFS: If one spouse itemizes, both must itemize
- Age 65+: Additional $1,600-$2,000 standard deduction
- Blind: Additional $1,600-$2,000 standard deduction
```

---

## 4. TAX CREDIT ELIGIBILITY MATRIX

### Refundable Credits (Can create refund)
| Credit | Max Amount | Income Limits | Requirements |
|--------|------------|---------------|--------------|
| Child Tax Credit | $2,000/child | Phases out $200K/$400K | Child under 17, SSN |
| Additional CTC | $1,700 refundable | Same as CTC | Refundable portion |
| EITC | $7,830 (3+ kids) | Varies by filing/kids | Earned income, AGI limits |
| American Opportunity | $2,500 (40% refundable) | $80K/$160K phaseout | First 4 years college |
| Premium Tax Credit | Varies | 100-400% FPL | Marketplace insurance |

### Non-Refundable Credits
| Credit | Max Amount | Income Limits | Requirements |
|--------|------------|---------------|--------------|
| Child & Dependent Care | $3,000-$6,000 | 20-35% rate by income | Work-related care |
| Lifetime Learning | $2,000 | $80K/$160K phaseout | Any higher education |
| Saver's Credit | $1,000/$2,000 | $36.5K/$73K | Retirement contributions |
| Adoption Credit | $15,950 | $239K-$279K phaseout | Qualified expenses |
| Residential Energy | 30% of cost | No limit | Solar, EV charger, etc. |
| EV Credit | $7,500 | $150K/$300K | New qualifying vehicle |

### Credit Phase-out Calculations
```python
# Child Tax Credit Phase-out
if filing_status == "MFJ":
    phaseout_start = 400000
else:
    phaseout_start = 200000

reduction = max(0, (agi - phaseout_start)) // 1000 * 50
ctc = max(0, (children * 2000) - reduction)
```

---

## 5. STATE TAX VARIATIONS

### No Income Tax States (9)
- Alaska, Florida, Nevada, New Hampshire*, South Dakota
- Tennessee*, Texas, Washington, Wyoming
- (*NH/TN tax interest/dividends only)

### High Tax States (Top 5)
| State | Top Rate | Threshold |
|-------|----------|-----------|
| California | 13.3% | $1M+ |
| Hawaii | 11% | $200K+ |
| New Jersey | 10.75% | $1M+ |
| Oregon | 9.9% | $125K+ |
| Minnesota | 9.85% | $183K+ |

### Flat Tax States
| State | Rate |
|-------|------|
| Colorado | 4.4% |
| Illinois | 4.95% |
| Indiana | 3.05% |
| Michigan | 4.25% |
| Utah | 4.65% |

### Multi-State Scenarios
1. **Moved during year** → Part-year resident both states
2. **Work in different state** → May owe both, credit for taxes paid
3. **Remote work** → Some states tax based on employer location
4. **Reciprocal agreements** → Some neighboring states have agreements

---

## 6. LIFE EVENT TRIGGERS

### Marriage
- [ ] Change filing status
- [ ] Evaluate MFJ vs MFS (usually MFJ better)
- [ ] Update W-4 withholding
- [ ] Combine income may push into higher bracket
- [ ] Marriage penalty or bonus calculation

### Divorce
- [ ] Filing status changes (may be HOH if kids)
- [ ] Alimony treatment (pre/post 2019)
- [ ] Child support (not taxable/deductible)
- [ ] Property settlement (generally tax-free)
- [ ] Retirement account division (QDRO)

### New Baby
- [ ] Child Tax Credit (+$2,000)
- [ ] Child & Dependent Care Credit
- [ ] FSA/Dependent Care FSA eligibility
- [ ] May qualify for HOH
- [ ] EITC eligibility check

### Home Purchase
- [ ] Mortgage interest deduction
- [ ] Property tax deduction (SALT cap)
- [ ] Points deduction (year 1 or amortized)
- [ ] PMI deduction (if AGI < threshold)
- [ ] First-time homebuyer programs

### Job Change
- [ ] Multiple W-2s - check withholding
- [ ] 401k rollover options
- [ ] HSA portability
- [ ] Stock options/RSU vesting
- [ ] Moving expenses (military only now)

### Retirement
- [ ] Social Security timing strategy
- [ ] RMD requirements (age 73+)
- [ ] Roth conversion opportunities
- [ ] Medicare premium considerations
- [ ] State tax implications

### Death of Family Member
- [ ] QSS status (2 years)
- [ ] Step-up in basis for inherited assets
- [ ] Estate tax considerations ($12.92M exemption)
- [ ] IRA beneficiary rules (10-year rule)
- [ ] Final return for deceased

---

## 7. SPECIAL TAX SITUATIONS

### Alternative Minimum Tax (AMT)
```
Triggers:
- High state/local taxes (now less common due to SALT cap)
- Large incentive stock options (ISO) exercise
- High miscellaneous deductions
- Private activity bond interest

Calculation:
AMT Income = Regular Taxable Income + Adjustments + Preferences
AMT Exemption = $88,100 (single) / $137,000 (MFJ)
AMT Rate = 26% up to $232,600, then 28%
Tax = Greater of Regular Tax or Tentative AMT
```

### Net Investment Income Tax (NIIT)
```
Triggers when AGI exceeds:
- Single: $200,000
- MFJ: $250,000
- MFS: $125,000

Tax = 3.8% × Lesser of:
  - Net Investment Income
  - AGI exceeding threshold

NII includes:
- Interest, dividends, capital gains
- Rental income, royalties
- Passive business income
```

### Self-Employment Tax
```
SE Income = Net self-employment earnings × 0.9235
SE Tax = SE Income × 15.3% (up to $168,600)
       + SE Income × 2.9% (above $168,600)
       + 0.9% Additional Medicare (over $200K/$250K)

Deduction = 50% of SE Tax (above-the-line)
```

### Estimated Tax Requirements
```
Safe Harbor Rules:
1. Pay 100% of prior year tax, OR
2. Pay 90% of current year tax, OR
3. Owe less than $1,000

High Income ($150K+ prior year AGI):
- Must pay 110% of prior year tax for safe harbor

Penalty: ~8% annual rate on underpayment
```

---

## 8. BUSINESS STRUCTURE ANALYSIS

### Entity Comparison Matrix

| Factor | Sole Prop | LLC | S-Corp | C-Corp | Partnership |
|--------|-----------|-----|--------|--------|-------------|
| SE Tax | Full 15.3% | Full 15.3% | Salary only | None | Full 15.3% |
| QBI Deduction | Yes | Yes | Yes | No | Yes |
| Liability Protection | No | Yes | Yes | Yes | Yes (LP) |
| Payroll Required | No | No | Yes | Yes | No |
| Reasonable Salary | N/A | N/A | Required | Required | N/A |
| Double Taxation | No | No | No | Yes | No |
| State Fees | None | $800/yr (CA) | $800/yr | $800/yr | $800/yr |

### S-Corp Salary Optimization
```
Goal: Minimize SE tax while maintaining reasonable compensation

Example: $200,000 net business income

As Sole Prop:
- SE Tax = $200,000 × 0.9235 × 0.153 = $28,259

As S-Corp with $80,000 salary:
- Payroll Tax = $80,000 × 0.153 = $12,240
- Distribution = $120,000 (no SE tax)
- Savings = $28,259 - $12,240 = $16,019

Reasonable salary factors:
- Industry standards
- Experience/qualifications
- Time devoted to business
- Comparable employee salaries
```

---

## 9. CONVERSATION FLOW BRANCHES

### Initial Assessment Flow
```
START
  │
  ├─► "What's your filing status?"
  │     ├── Single → Ask about dependents (might be HOH)
  │     ├── Married → "Filing jointly or separately?"
  │     │              ├── Jointly → Continue
  │     │              └── Separately → "Any specific reason?" (warn about limitations)
  │     ├── Head of Household → Verify qualifying person
  │     └── Widowed → Check if within 2 years + dependent
  │
  ├─► "What's your approximate income?"
  │     ├── Under $50K → Check EITC eligibility
  │     ├── $50K-$150K → Standard optimization
  │     ├── $150K-$400K → Phase-out considerations
  │     └── Over $400K → AMT, NIIT, phase-outs
  │
  ├─► "What are your income sources?"
  │     ├── W-2 only → Simple return
  │     ├── W-2 + Side gig → Schedule C, quarterly taxes
  │     ├── Self-employed → Entity structure analysis
  │     ├── Investments → Capital gains strategies
  │     └── Rental → Passive loss rules, depreciation
  │
  └─► "Any major life changes this year?"
        ├── Marriage → MFJ vs MFS analysis
        ├── Divorce → Alimony, child support
        ├── New baby → Credits, care expenses
        ├── Home purchase → Deduction analysis
        ├── Job change → Multiple W-2s, 401k
        └── Retirement → Distribution strategies
```

### Strategy Recommendation Flow
```
AFTER PROFILE COMPLETE
  │
  ├─► Calculate current tax position
  │
  ├─► Identify optimization opportunities:
  │     │
  │     ├── RETIREMENT CONTRIBUTIONS
  │     │     ├── Max 401(k): $23,000 ($30,500 if 50+)
  │     │     ├── IRA: $7,000 ($8,000 if 50+)
  │     │     ├── SEP-IRA (self-employed): 25% of net
  │     │     └── Solo 401(k): $69,000 total
  │     │
  │     ├── HSA CONTRIBUTIONS
  │     │     ├── Individual: $4,150
  │     │     ├── Family: $8,300
  │     │     └── 55+ catch-up: +$1,000
  │     │
  │     ├── BUSINESS STRATEGIES
  │     │     ├── S-Corp election
  │     │     ├── Home office deduction
  │     │     ├── Vehicle expenses
  │     │     └── Retirement plan setup
  │     │
  │     ├── INVESTMENT STRATEGIES
  │     │     ├── Tax-loss harvesting
  │     │     ├── Long-term vs short-term gains
  │     │     ├── Qualified dividends
  │     │     └── Municipal bonds
  │     │
  │     └── TIMING STRATEGIES
  │           ├── Defer income to next year
  │           ├── Accelerate deductions
  │           ├── Bunch charitable donations
  │           └── Roth conversion opportunities
  │
  └─► Present recommendations with savings estimates
```

---

## 10. ERROR HANDLING & EDGE CASES

### Invalid Input Scenarios
| Input | Response |
|-------|----------|
| Negative income | "Income should be positive. Did you have a loss?" |
| Income > $100M | "Please verify this amount: $X" |
| Age < 0 or > 120 | "Please enter a valid age" |
| Dependents > 20 | "Please verify number of dependents" |
| Contradictory info | "Earlier you mentioned X, but now Y. Which is correct?" |

### Ambiguous Situations
| Situation | Clarification Needed |
|-----------|---------------------|
| "I'm separated" | "Legally separated? In which state?" |
| "Some investment income" | "Approximately how much? $1K-$10K, $10K-$50K, etc." |
| "I work from home" | "Employee or self-employed? Own or rent?" |
| "I have a side business" | "Sole proprietor, LLC, or corporation?" |

### Missing Critical Data
```
REQUIRED for basic calculation:
- Filing status (cannot proceed without)
- Total income estimate (cannot proceed without)

REQUIRED for accurate calculation:
- State of residence
- Income breakdown by type
- Deduction details

OPTIONAL but valuable:
- Prior year tax data
- Withholding information
- Estimated payments made
```

---

## 11. OUTCOME CATEGORIES

### Tax Position Outcomes
1. **Refund Expected** → "Great news! You're projected to receive $X refund"
2. **Balance Due** → "You may owe $X. Let's explore reduction strategies"
3. **Break Even** → "Your withholding is well-calibrated"
4. **Underpayment Penalty Risk** → "Warning: You may face penalties"

### Strategy Recommendations by Profile

#### Low Income (<$50K)
- Maximize EITC
- Check Saver's Credit eligibility
- Premium Tax Credit for insurance
- Free File options

#### Middle Income ($50K-$150K)
- 401(k) contributions
- HSA if eligible
- Child Tax Credit optimization
- Itemize vs Standard analysis

#### High Income ($150K-$400K)
- Max all retirement accounts
- Backdoor Roth IRA
- Tax-loss harvesting
- Charitable giving strategies
- Credit phase-out planning

#### Very High Income ($400K+)
- NIIT mitigation
- AMT planning
- Qualified Opportunity Zones
- Charitable remainder trusts
- State residency planning

#### Self-Employed
- S-Corp election analysis
- SEP-IRA vs Solo 401(k)
- Home office deduction
- Vehicle expense optimization
- Health insurance deduction

#### Investors
- Long-term vs short-term gains
- Tax-loss harvesting
- Qualified dividends
- Municipal bonds
- Opportunity Zone investments

---

## 12. RESPONSE TEMPLATES

### Greeting Variations
```
New user: "Welcome! I'm your AI tax advisor. Let's find ways to optimize your taxes."
Returning user: "Welcome back! Would you like to continue where we left off?"
Tax season: "Tax season is here! Let's make sure you're maximizing your return."
Extension filed: "I see you filed an extension. Let's finalize your return."
```

### Calculation Results
```
REFUND:
"Great news! Based on your information, you're looking at a refund of approximately $X.
Here's the breakdown:
• Federal: $X refund
• State: $X refund
• Total: $X

I also found $Y in additional savings opportunities we should discuss."

BALANCE DUE:
"Based on your information, you may owe approximately $X.
Here's the breakdown:
• Federal: $X owed
• State: $X owed
• Total: $X

Don't worry - I've identified strategies that could reduce this by $Y. Want to explore them?"
```

### Strategy Presentation
```
"I've identified [N] tax-saving opportunities for you:

🥇 TOP PRIORITY: [Strategy Name]
   Potential Savings: $X
   [Brief explanation]

🥈 [Strategy 2]
   Potential Savings: $X
   [Brief explanation]

🥉 [Strategy 3]
   Potential Savings: $X
   [Brief explanation]

Total Potential Savings: $X

Would you like me to explain any of these in detail?"
```

---

## 13. IMPLEMENTATION CHECKLIST

### Message Parsing Must Handle:
- [ ] All 5 filing statuses with variations
- [ ] Dollar amounts with various formats ($50k, 50,000, fifty thousand)
- [ ] All 50 states + DC with names and abbreviations
- [ ] Dependent counts (1 kid, two children, 3 dependents)
- [ ] Yes/No variations (yeah, nope, sure, nah)
- [ ] Income ranges (between 50 and 100k, under 50k, over 200k)
- [ ] Occupation/income type keywords

### Calculation Engine Must Support:
- [ ] All filing status bracket variations
- [ ] All state tax calculations
- [ ] Credit phase-outs at various income levels
- [ ] AMT calculation
- [ ] NIIT calculation
- [ ] Self-employment tax
- [ ] Capital gains (short and long term)
- [ ] Qualified dividends
- [ ] QBI deduction

### Response Generation Must:
- [ ] Provide specific dollar amounts
- [ ] Explain reasoning
- [ ] Offer next steps
- [ ] Handle uncertainty gracefully
- [ ] Maintain conversation context
- [ ] Remember prior answers
