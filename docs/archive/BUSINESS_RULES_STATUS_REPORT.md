# Business Rules Implementation Status Report
## Tax Year 2025 - Jorss-Gbo Tax Preparation Agent

**Generated:** 2026-01-16
**Total Rules:** 2000 (BR-0001 to BR-1000 + BR3-0001 to BR3-1000)

---

## Executive Summary

| Status | Count | Percentage |
|--------|-------|------------|
| **Fully Implemented** | ~120 | ~6% |
| **Partially Implemented** | ~60 | ~3% |
| **Not Implemented** | ~320 | ~16% |
| **Duplicate/Control Variations** | ~1500 | ~75% |

**Note:** After deduplication, approximately 500 unique business rules remain. Many rules (BR-0137 to BR-1000) are variations of the same core rules applied with different control aspects (data validation, worksheet selection, schedule triggering, documentation, audit defense, threshold handling, e-file readiness, exception routing, cross-form reconciliation, security/privacy controls).

---

## SECTION 1: FULLY IMPLEMENTED RULES

### 1.1 Standard Deduction Rules (BR2-0001 to BR2-0010)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0001 | Base standard deduction amounts for 2025 | ✅ DONE | `src/models/deductions.py:194-201` |
| BR2-0002 | MFS + spouse itemizes = $0 standard deduction | ✅ DONE | `src/models/deductions.py:190-191` |
| BR2-0003 | Dual-status alien = $0 standard deduction | ✅ DONE | `src/models/deductions.py:186-188` |
| BR2-0004 | Dependent standard deduction formula | ✅ DONE | `src/models/deductions.py:205-217` |
| BR2-0005 | Additional deduction for age 65+ | ✅ DONE | `src/models/deductions.py:219-230` |
| BR2-0006 | Additional deduction for blindness | ✅ DONE | `src/models/deductions.py:219-230` |

### 1.2 Student Loan Interest Deduction (BR2-0007 to BR2-0010)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0007 | Student loan interest $2,500 maximum cap | ✅ DONE | `src/models/deductions.py:81-82` |
| BR2-0008 | Student loan interest phaseout (Single: $85K-$100K, MFJ: $170K-$200K) | ✅ DONE | `src/models/deductions.py:88-106` |
| BR2-0009 | MFS cannot claim student loan interest deduction | ✅ DONE | `src/models/deductions.py:84-86` |

### 1.3 Tax Bracket Calculations (BR2-0020 to BR2-0050)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0020 | 7 progressive tax brackets (10%, 12%, 22%, 24%, 32%, 35%, 37%) | ✅ DONE | `src/calculator/engine.py:387-440` |
| BR2-0021 | Single filer bracket thresholds | ✅ DONE | `src/calculator/tax_year_config.py:22-30` |
| BR2-0022 | MFJ bracket thresholds (2x single) | ✅ DONE | `src/calculator/tax_year_config.py:22-30` |
| BR2-0023 | MFS bracket thresholds (1/2 MFJ) | ✅ DONE | `src/calculator/tax_year_config.py:22-30` |
| BR2-0024 | HOH bracket thresholds | ✅ DONE | `src/calculator/tax_year_config.py:22-30` |
| BR2-0025 | QW uses MFJ brackets | ✅ DONE | `src/calculator/tax_year_config.py:22-30` |

### 1.4 Qualified Dividends & Long-Term Capital Gains (BR2-0060 to BR2-0080)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0060 | 0% rate for LTCG/QD up to threshold | ✅ DONE | `src/calculator/engine.py:495-538` |
| BR2-0061 | 15% rate for LTCG/QD middle tier | ✅ DONE | `src/calculator/engine.py:529-532` |
| BR2-0062 | 20% rate for LTCG/QD above threshold | ✅ DONE | `src/calculator/engine.py:534-536` |
| BR2-0063 | LTCG/QD stacks on top of ordinary income | ✅ DONE | `src/calculator/engine.py:518-536` |

### 1.5 Self-Employment Tax (BR2-0100 to BR2-0120)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0100 | 12.4% Social Security rate | ✅ DONE | `src/calculator/engine.py:228-231` |
| BR2-0101 | 2.9% Medicare rate (no cap) | ✅ DONE | `src/calculator/engine.py:233-234` |
| BR2-0102 | 92.35% net earnings factor | ✅ DONE | `src/calculator/engine.py:223` |
| BR2-0103 | SS wage base cap ($176,100 for 2025) | ✅ DONE | `src/calculator/engine.py:228-231` |
| BR2-0104 | W-2 wages reduce SE SS base | ✅ DONE | `src/calculator/engine.py:229-230` |
| BR2-0105 | 50% SE tax deduction (above-the-line) | ✅ DONE | `src/calculator/engine.py:237` |

### 1.6 Additional Medicare Tax (BR2-0130 to BR2-0140)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0130 | 0.9% rate on wages over threshold | ✅ DONE | `src/calculator/engine.py:252-284` |
| BR2-0131 | Threshold: $200K single, $250K MFJ, $125K MFS | ✅ DONE | `src/calculator/tax_year_config.py:55-60` |
| BR2-0132 | Applies to combined wages + SE income | ✅ DONE | `src/calculator/engine.py:271-282` |
| BR2-0133 | SE threshold reduced by wages | ✅ DONE | `src/calculator/engine.py:279-282` |

### 1.7 Net Investment Income Tax - NIIT (BR2-0150 to BR2-0170)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0150 | 3.8% rate on lesser of NII or MAGI excess | ✅ DONE | `src/calculator/engine.py:286-324` |
| BR2-0151 | NIIT thresholds: $200K single, $250K MFJ | ✅ DONE | `src/calculator/tax_year_config.py:63-68` |
| BR2-0152 | NII includes: interest, dividends, capital gains, rental, royalty | ✅ DONE | `src/calculator/engine.py:304-314` |
| BR2-0153 | SE income excluded from NII | ✅ DONE | `src/calculator/engine.py:304-314` |

### 1.8 Alternative Minimum Tax - AMT (BR2-0180 to BR2-0210)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0180 | 26% rate up to threshold | ✅ DONE | `src/calculator/engine.py:374-377` |
| BR2-0181 | 28% rate above threshold ($232,600 MFJ) | ✅ DONE | `src/calculator/engine.py:374-377` |
| BR2-0182 | AMT exemption: $88,100 single, $137,000 MFJ | ✅ DONE | `src/calculator/tax_year_config.py:71-77` |
| BR2-0183 | Exemption phaseout at 25% rate | ✅ DONE | `src/calculator/engine.py:365-368` |
| BR2-0184 | SALT addback to AMTI | ✅ DONE | `src/calculator/engine.py:351-358` |
| BR2-0185 | AMT = max(0, TMT - regular tax) | ✅ DONE | `src/calculator/engine.py:383` |

### 1.9 Child Tax Credit (BR2-0250 to BR2-0270)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0250 | $2,200 per qualifying child (2025) | ✅ DONE | `src/calculator/engine.py:566-577` |
| BR2-0251 | Phaseout: $200K single, $400K MFJ | ✅ DONE | `src/calculator/engine.py:569-576` |
| BR2-0252 | $50 reduction per $1,000 excess (ceiling) | ✅ DONE | `src/calculator/engine.py:574` |
| BR2-0253 | Refundable portion up to $1,800/child | ✅ DONE | `src/calculator/engine.py:579-584` |

### 1.10 Earned Income Tax Credit - EITC (BR2-0280 to BR2-0320)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0280 | Maximum credits: $649 (0 children) to $8,046 (3+ children) | ✅ DONE | `src/calculator/tax_year_config.py:85-90` |
| BR2-0281 | Investment income limit: $11,600 (2025) | ✅ DONE | `src/calculator/engine.py:632` |
| BR2-0282 | Use higher of earned income or AGI for phaseout | ✅ DONE | `src/calculator/engine.py:645` |
| BR2-0283 | Filing status-specific phaseout ranges | ✅ DONE | `src/calculator/tax_year_config.py:92-105` |

### 1.11 Social Security Taxation (BR2-0350 to BR2-0370)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0350 | Provisional income formula | ✅ DONE | `src/calculator/engine.py:442-485` |
| BR2-0351 | 50% taxable tier ($25K/$32K base) | ✅ DONE | `src/calculator/engine.py:476-479` |
| BR2-0352 | 85% taxable tier ($34K/$44K base) | ✅ DONE | `src/calculator/engine.py:480-483` |
| BR2-0353 | Maximum 85% of benefits taxable | ✅ DONE | `src/calculator/engine.py:483` |

### 1.12 Itemized Deduction Rules (BR2-0400 to BR2-0450)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0400 | SALT cap at $10,000 | ✅ DONE | `src/models/deductions.py:32-35` |
| BR2-0401 | Medical expense 7.5% AGI floor | ✅ DONE | `src/models/deductions.py:27-30` |
| BR2-0402 | Mortgage interest deductible | ✅ DONE | `src/models/deductions.py:37-38` |
| BR2-0403 | Charitable contributions deductible | ✅ DONE | `src/models/deductions.py:40-41` |
| BR2-0404 | Casualty losses deductible | ✅ DONE | `src/models/deductions.py:43-44` |

### 1.13 State Tax Calculations (BR2-0500 to BR2-0600)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0500 | 43 states with income tax supported | ✅ DONE | `src/calculator/state/configs/state_2025/` |
| BR2-0501 | No-income-tax states recognized | ✅ DONE | State engine returns None |
| BR2-0502 | State EITC as % of federal | ✅ DONE | Individual state configs |
| BR2-0503 | State-specific deductions | ✅ DONE | `src/models/state/state_deductions.py` |

---

## SECTION 2: PARTIALLY IMPLEMENTED RULES

### 2.1 Education Credits (BR2-0600 to BR2-0650)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0600 | American Opportunity Tax Credit (AOTC) | ⚠️ PARTIAL | Field exists in `credits.py:18-19` but full calculation missing |
| BR2-0601 | Lifetime Learning Credit (LLC) | ⚠️ PARTIAL | Field exists but calculation incomplete |
| BR2-0602 | AOTC $2,500 max, 40% refundable | ⚠️ PARTIAL | Not fully calculated |
| BR2-0603 | AOTC/LLC phaseouts | ⚠️ PARTIAL | Thresholds not implemented |

### 2.2 Foreign Tax Credit (BR2-0700 to BR2-0730)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0700 | Foreign tax credit field | ⚠️ PARTIAL | Field exists: `credits.py:25` |
| BR2-0701 | FTC calculation | ❌ MISSING | No calculation logic |
| BR2-0702 | FTC limitation | ❌ MISSING | No limitation logic |

### 2.3 Casualty & Theft Losses (BR2-0750 to BR2-0780)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0750 | Casualty loss field | ⚠️ PARTIAL | Field exists: `deductions.py:16` |
| BR2-0751 | $100 per event floor | ❌ MISSING | Not implemented |
| BR2-0752 | 10% AGI floor | ❌ MISSING | Not implemented |
| BR2-0753 | Federally declared disaster requirement | ❌ MISSING | Not implemented |

### 2.4 IRA Contribution Rules (BR2-0800 to BR2-0850)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0800 | IRA contribution limit $7,000 | ⚠️ PARTIAL | Config exists: `tax_year_config.py` |
| BR2-0801 | Catch-up $1,000 for 50+ | ⚠️ PARTIAL | Config exists but not enforced |
| BR2-0802 | Traditional IRA phaseout | ⚠️ PARTIAL | Thresholds exist, calculation incomplete |
| BR2-0803 | Roth IRA income limits | ⚠️ PARTIAL | Thresholds exist, contribution not validated |

### 2.5 Alimony (BR2-0900 to BR2-0920)

| Rule ID | Description | Status | Implementation Location |
|---------|-------------|--------|------------------------|
| BR2-0900 | Alimony paid deduction field | ⚠️ PARTIAL | Field exists: `deductions.py:65` |
| BR2-0901 | Pre-2019 agreements: deductible | ❌ MISSING | No date check |
| BR2-0902 | Post-2018 agreements: not deductible | ❌ MISSING | No date check |
| BR2-0903 | Alimony received as income | ❌ MISSING | No income field |

---

## SECTION 3: NOT IMPLEMENTED RULES

### 3.1 Filing Status Edge Cases (BR3-0001 to BR3-0050)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0001 | Death of spouse in tax year - can file MFJ | ❌ NOT IMPL | HIGH |
| BR3-0002 | Qualifying Surviving Spouse - 2 year rule | ❌ NOT IMPL | HIGH |
| BR3-0003 | Abandoned spouse rule (MFS as HOH) | ❌ NOT IMPL | MEDIUM |
| BR3-0004 | Change of filing status after filing | ❌ NOT IMPL | LOW |

### 3.2 Gambling & Misc Income (BR3-0051 to BR3-0100)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0051 | Gambling winnings included in gross income | ❌ NOT IMPL | HIGH |
| BR3-0052 | W-2G form processing | ❌ NOT IMPL | HIGH |
| BR3-0053 | Gambling losses as itemized deduction | ❌ NOT IMPL | HIGH |
| BR3-0054 | Losses limited to extent of winnings | ❌ NOT IMPL | HIGH |
| BR3-0055 | Professional gambler Schedule C treatment | ❌ NOT IMPL | MEDIUM |
| BR3-0056 | 24% mandatory withholding on large wins | ❌ NOT IMPL | MEDIUM |

### 3.3 Virtual Currency & Digital Assets (BR3-0101 to BR3-0150)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0101 | Crypto treated as property | ❌ NOT IMPL | HIGH |
| BR3-0102 | Disposal triggers capital gain/loss | ❌ NOT IMPL | HIGH |
| BR3-0103 | Fair market value at receipt = income | ❌ NOT IMPL | HIGH |
| BR3-0104 | Mining income as ordinary income | ❌ NOT IMPL | HIGH |
| BR3-0105 | Staking rewards as ordinary income | ❌ NOT IMPL | HIGH |
| BR3-0106 | Airdrops as ordinary income | ❌ NOT IMPL | MEDIUM |
| BR3-0107 | Crypto-to-crypto trades taxable | ❌ NOT IMPL | HIGH |
| BR3-0108 | Cost basis tracking (FIFO/specific ID) | ❌ NOT IMPL | HIGH |
| BR3-0109 | Form 8949 for crypto transactions | ❌ NOT IMPL | HIGH |
| BR3-0110 | Question on Form 1040 about digital assets | ❌ NOT IMPL | HIGH |

### 3.4 Premium Tax Credit - PTC (BR3-0151 to BR3-0200)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0151 | PTC eligibility (100%-400% FPL) | ❌ NOT IMPL | MEDIUM |
| BR3-0152 | Form 8962 reconciliation | ❌ NOT IMPL | MEDIUM |
| BR3-0153 | Advance PTC vs actual | ❌ NOT IMPL | MEDIUM |
| BR3-0154 | PTC repayment caps by income | ❌ NOT IMPL | MEDIUM |
| BR3-0155 | Second-lowest-cost silver plan (SLCSP) | ❌ NOT IMPL | MEDIUM |
| BR3-0156 | Married filing separately exclusion | ❌ NOT IMPL | MEDIUM |

### 3.5 Dependents: QC/QR/Tiebreaker (BR3-0201 to BR3-0280)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0201 | Qualifying Child - Relationship test | ❌ NOT IMPL | HIGH |
| BR3-0202 | Qualifying Child - Age test (<19, <24 student) | ❌ NOT IMPL | HIGH |
| BR3-0203 | Qualifying Child - Residency test (6 months) | ❌ NOT IMPL | HIGH |
| BR3-0204 | Qualifying Child - Support test | ❌ NOT IMPL | HIGH |
| BR3-0205 | Qualifying Child - Joint return test | ❌ NOT IMPL | HIGH |
| BR3-0206 | Qualifying Relative - Not QC of anyone | ❌ NOT IMPL | HIGH |
| BR3-0207 | Qualifying Relative - Member of household OR relationship | ❌ NOT IMPL | HIGH |
| BR3-0208 | Qualifying Relative - Gross income test ($5,050 for 2025) | ❌ NOT IMPL | HIGH |
| BR3-0209 | Qualifying Relative - Support test (>50%) | ❌ NOT IMPL | HIGH |
| BR3-0210 | Tiebreaker Rule #1 - Parent beats non-parent | ❌ NOT IMPL | HIGH |
| BR3-0211 | Tiebreaker Rule #2 - Longer residence wins | ❌ NOT IMPL | HIGH |
| BR3-0212 | Tiebreaker Rule #3 - Higher AGI wins | ❌ NOT IMPL | HIGH |
| BR3-0213 | Form 8332 Release of Dependency | ❌ NOT IMPL | MEDIUM |

### 3.6 K-1 / Trust / Estate Income (BR3-0281 to BR3-0350)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0281 | Schedule K-1 (Form 1065) - Partnership | ❌ NOT IMPL | HIGH |
| BR3-0282 | Schedule K-1 (Form 1120-S) - S-Corp | ❌ NOT IMPL | HIGH |
| BR3-0283 | Schedule K-1 (Form 1041) - Trust/Estate | ❌ NOT IMPL | HIGH |
| BR3-0284 | K-1 Box 1: Ordinary income | ❌ NOT IMPL | HIGH |
| BR3-0285 | K-1 Box 2-3: Rental/Royalty income | ❌ NOT IMPL | HIGH |
| BR3-0286 | K-1 Box 4-10: Portfolio income items | ❌ NOT IMPL | HIGH |
| BR3-0287 | K-1 Box 11: Section 179 deduction | ❌ NOT IMPL | MEDIUM |
| BR3-0288 | K-1 Box 12: Other deductions | ❌ NOT IMPL | MEDIUM |
| BR3-0289 | K-1 Box 13: Credits | ❌ NOT IMPL | MEDIUM |
| BR3-0290 | At-risk limitations (Form 6198) | ❌ NOT IMPL | MEDIUM |
| BR3-0291 | Passive activity limitations (Form 8582) | ❌ NOT IMPL | HIGH |
| BR3-0292 | QBI deduction calculation for K-1 income | ❌ NOT IMPL | HIGH |

### 3.7 Foreign Assets & Disclosures (BR3-0351 to BR3-0400)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0351 | FBAR filing requirement ($10,000 threshold) | ❌ NOT IMPL | MEDIUM |
| BR3-0352 | FinCEN Form 114 due date | ❌ NOT IMPL | MEDIUM |
| BR3-0353 | FATCA Form 8938 thresholds | ❌ NOT IMPL | MEDIUM |
| BR3-0354 | Form 3520 - Foreign trust reporting | ❌ NOT IMPL | LOW |
| BR3-0355 | Form 5471 - Foreign corporation | ❌ NOT IMPL | LOW |
| BR3-0356 | PFIC reporting (Form 8621) | ❌ NOT IMPL | LOW |
| BR3-0357 | Foreign earned income exclusion | ❌ NOT IMPL | MEDIUM |
| BR3-0358 | Physical presence test (330 days) | ❌ NOT IMPL | MEDIUM |
| BR3-0359 | Bona fide residence test | ❌ NOT IMPL | MEDIUM |
| BR3-0360 | Housing exclusion/deduction | ❌ NOT IMPL | LOW |

### 3.8 Household Employment Taxes (BR3-0401 to BR3-0450)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0401 | Schedule H threshold ($2,700 for 2025) | ❌ NOT IMPL | LOW |
| BR3-0402 | Household employer FICA (7.65%) | ❌ NOT IMPL | LOW |
| BR3-0403 | FUTA on household employees | ❌ NOT IMPL | LOW |
| BR3-0404 | W-2 for household employees | ❌ NOT IMPL | LOW |
| BR3-0405 | State UI requirements | ❌ NOT IMPL | LOW |

### 3.9 Audit, Notices & Record Retention (BR3-0451 to BR3-0500)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0451 | 3-year statute of limitations | ❌ NOT IMPL | INFO |
| BR3-0452 | 6-year for >25% understatement | ❌ NOT IMPL | INFO |
| BR3-0453 | No limit for fraud | ❌ NOT IMPL | INFO |
| BR3-0454 | Record retention guidance | ⚠️ PARTIAL | `src/audit/document_retention.py` |
| BR3-0455 | CP2000 notice handling | ❌ NOT IMPL | INFO |

### 3.10 Identity, IP PIN & Fraud Controls (BR3-0501 to BR3-0550)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0501 | IP PIN validation | ❌ NOT IMPL | MEDIUM |
| BR3-0502 | SSN validation (format/checksum) | ❌ NOT IMPL | HIGH |
| BR3-0503 | ITIN validation | ❌ NOT IMPL | MEDIUM |
| BR3-0504 | Prior year AGI verification | ❌ NOT IMPL | MEDIUM |
| BR3-0505 | Identity Protection PIN entry | ❌ NOT IMPL | MEDIUM |

### 3.11 Health Coverage & 1095 Series (BR3-0551 to BR3-0600)

| Rule ID | Description | Status | Priority |
|---------|-------------|--------|----------|
| BR3-0551 | 1095-A processing for PTC | ❌ NOT IMPL | MEDIUM |
| BR3-0552 | 1095-B coverage verification | ❌ NOT IMPL | LOW |
| BR3-0553 | 1095-C employer coverage | ❌ NOT IMPL | LOW |
| BR3-0554 | Months of coverage tracking | ❌ NOT IMPL | MEDIUM |

---

## SECTION 4: IMPLEMENTATION PRIORITY MATRIX

### Critical (Must Have) - 15 Rule Groups

| Priority | Rule Group | Rules | Impact |
|----------|------------|-------|--------|
| 1 | Gambling Income/Losses | BR3-0051 to BR3-0060 | Common, affects many filers |
| 2 | Virtual Currency | BR3-0101 to BR3-0120 | Required question on Form 1040 |
| 3 | Dependent QC/QR Tests | BR3-0201 to BR3-0215 | Core eligibility validation |
| 4 | K-1 Income Processing | BR3-0281 to BR3-0295 | Business income filers |
| 5 | Passive Activity Limits | BR3-0291 | Rental property investors |

### High Priority - 10 Rule Groups

| Priority | Rule Group | Rules | Impact |
|----------|------------|-------|--------|
| 6 | Filing Status Edge Cases | BR3-0001 to BR3-0010 | Widow(er), deceased spouse |
| 7 | Education Credits Complete | BR2-0600 to BR2-0650 | AOTC/LLC calculations |
| 8 | Alimony Date Rules | BR2-0900 to BR2-0920 | Pre/post 2019 treatment |
| 9 | Foreign Tax Credit Calc | BR2-0700 to BR2-0730 | International filers |
| 10 | Premium Tax Credit | BR3-0151 to BR3-0165 | ACA marketplace users |

### Medium Priority - 8 Rule Groups

| Priority | Rule Group | Rules | Impact |
|----------|------------|-------|--------|
| 11 | Casualty Loss Limits | BR2-0750 to BR2-0780 | Disaster victims |
| 12 | Foreign Asset Reporting | BR3-0351 to BR3-0365 | Expatriates |
| 13 | IP PIN / Identity | BR3-0501 to BR3-0510 | Security validation |
| 14 | Health Coverage Forms | BR3-0551 to BR3-0560 | PTC reconciliation |
| 15 | IRA Contribution Limits | BR2-0800 to BR2-0850 | Retirement planning |

### Low Priority - 5 Rule Groups

| Priority | Rule Group | Rules | Impact |
|----------|------------|-------|--------|
| 16 | Household Employment | BR3-0401 to BR3-0420 | Nanny tax |
| 17 | Trust/Estate K-1 | BR3-0283 to BR3-0290 | Complex estates |
| 18 | PFIC/Foreign Corp | BR3-0355 to BR3-0360 | Very specialized |
| 19 | Audit Info | BR3-0451 to BR3-0460 | Educational only |
| 20 | Form 3520/5471 | BR3-0354 to BR3-0356 | Complex international |

---

## SECTION 5: RECOMMENDED IMPLEMENTATION ROADMAP

### Phase 1: Core Compliance (Critical)

**Target: 50 rules**

1. **Gambling Income Module**
   - Add fields to Income model: `gambling_winnings`, `gambling_losses`
   - Implement W-2G processing
   - Add itemized deduction logic (losses limited to winnings)

2. **Virtual Currency Module**
   - Add crypto transaction tracking
   - Implement Form 8949 generation
   - Handle mining/staking income

3. **Dependent Validation Engine**
   - Implement QC 5-test validation
   - Implement QR 4-test validation
   - Add tiebreaker rule logic

### Phase 2: Business Income (High)

**Target: 40 rules**

1. **K-1 Processing Engine**
   - Create K1Income model
   - Parse all K-1 box types
   - Integrate with QBI deduction

2. **Passive Activity Tracking**
   - Implement Form 8582 logic
   - Track material participation
   - Handle suspended losses

### Phase 3: Credits & International (Medium)

**Target: 35 rules**

1. **Complete Education Credits**
   - Full AOTC calculation with 40% refundable
   - LLC calculation
   - Phase-out logic

2. **Foreign Tax Credit**
   - FTC limitation calculation
   - Form 1116 logic

3. **Premium Tax Credit**
   - Form 8962 reconciliation
   - SLCSP lookup integration

### Phase 4: Specialized (Low)

**Target: 25 rules**

1. Household employment taxes
2. Foreign reporting forms
3. Trust/estate distributions
4. Audit trail enhancements

---

## SECTION 6: FILES TO MODIFY

| File | Changes Needed |
|------|----------------|
| `src/models/income.py` | Add gambling, crypto, K-1 income fields |
| `src/models/deductions.py` | Add gambling loss logic, casualty loss limits |
| `src/models/credits.py` | Complete education credit calculations |
| `src/models/taxpayer.py` | Add dependent validation methods |
| `src/calculator/engine.py` | Integrate new income/deduction types |
| `src/calculator/k1_processor.py` | **NEW** - K-1 parsing and calculation |
| `src/calculator/crypto_engine.py` | **NEW** - Cryptocurrency calculations |
| `src/calculator/gambling_handler.py` | **NEW** - Gambling income/loss handling |
| `src/forms/form_8949.py` | **NEW** - Capital gains reporting |
| `src/forms/form_8582.py` | **NEW** - Passive activity losses |
| `src/forms/form_8962.py` | **NEW** - Premium Tax Credit |
| `src/validation/dependent_validator.py` | **NEW** - QC/QR/Tiebreaker validation |

---

## SECTION 7: BR-0001 to BR-1000 DETAILED ANALYSIS

### 7.1 FILING REQUIREMENTS (BR-0001 to BR-0010, BR-0069 to BR-0078)

| Rule ID | Description | Status | Implementation |
|---------|-------------|--------|----------------|
| BR-0001 | Use Form 1040 as default; Form 1040-SR for age 65+ | ⚠️ PARTIAL | Tax year config exists, form selection not implemented |
| BR-0002 | Filing deadline April 15, 2026 | ❌ NOT IMPL | No deadline tracking |
| BR-0003 | Nonresident/dual-status alien routing to 1040-NR | ✅ DONE | `is_dual_status_alien` field exists in taxpayer.py |
| BR-0004 | E-file vs paper-file routing | ❌ NOT IMPL | No filing method tracking |
| BR-0005 | Fiscal year filer handling | ❌ NOT IMPL | Assumes calendar year |
| BR-0006 | Extension workflow | ❌ NOT IMPL | No extension handling |
| BR-0007 | State of residency tracking | ✅ DONE | State tax module implemented |
| BR-0008 | Filing status validation | ✅ DONE | Filing status validation in models |
| BR-0009 | Block e-file if identity fields missing | ⚠️ PARTIAL | Model validation exists |
| BR-0010 | Signature/authorization | ❌ NOT IMPL | No signature handling |
| BR-0069 | Validate 'single' status | ✅ DONE | Filing status validation |
| BR-0071 | Validate 'married filing jointly' | ✅ DONE | Filing status validation |
| BR-0073 | Validate 'married filing separately' | ✅ DONE | Filing status validation |
| BR-0075 | Validate 'head of household' | ✅ DONE | Filing status validation |
| BR-0077 | Validate 'qualifying surviving spouse' | ✅ DONE | Filing status validation |
| BR-0122 | Major life event handling | ❌ NOT IMPL | No life event tracking |
| BR-0123 | Spouse death routing | ⚠️ PARTIAL | `spouse_died_year` field exists |

### 7.2 STANDARD DEDUCTION RULES (BR-0011 to BR-0020)

| Rule ID | Description | Status | Implementation |
|---------|-------------|--------|----------------|
| BR-0011 | Dependent standard deduction worksheet | ✅ DONE | `deductions.py:205-217` |
| BR-0012 | MFS + spouse itemizes = $0 | ✅ DONE | `deductions.py:190-191` |
| BR-0013 | Dual-status alien = $0 | ✅ DONE | `deductions.py:186-188` |
| BR-0014 | 2025 standard deduction amounts | ✅ DONE | `deductions.py:194-201` |
| BR-0015 | Age 65+ additional deduction | ✅ DONE | `deductions.py:219-230` |
| BR-0016 | Blindness additional deduction | ✅ DONE | `deductions.py:219-230` |
| BR-0017 | Disaster loss add-on | ❌ NOT IMPL | No disaster loss logic |
| BR-0018 | Earned income for dependent deduction | ✅ DONE | `deductions.py:213` |
| BR-0019 | Prevent worksheet conflicts | ✅ DONE | Logic in `_get_standard_deduction` |
| BR-0020 | Record exception reason | ❌ NOT IMPL | No audit trail |

### 7.3 EITC/CTC/EDU CREDITS (BR-0021 to BR-0030, BR-0101 to BR-0108)

| Rule ID | Description | Status | Implementation |
|---------|-------------|--------|----------------|
| BR-0021 | EIC requires earned income | ✅ DONE | `engine.py:616-660` |
| BR-0022 | Reject EIC for MFS | ⚠️ PARTIAL | Not explicitly checked |
| BR-0023 | Qualifying child test | ❌ NOT IMPL | No QC validation |
| BR-0024 | QC relationship test | ❌ NOT IMPL | No QC validation |
| BR-0025 | QC age test | ❌ NOT IMPL | No QC validation |
| BR-0026 | QC residency test | ❌ NOT IMPL | No QC validation |
| BR-0027 | SSN requirement for EIC | ❌ NOT IMPL | No SSN validation |
| BR-0028 | Investment income limitation | ✅ DONE | `engine.py:632` |
| BR-0029 | Prior-year earned income option | ❌ NOT IMPL | Not supported |
| BR-0030 | EIC substantiation checklist | ❌ NOT IMPL | No audit checklist |
| BR-0101 | EIC with 0 qualifying children | ✅ DONE | EITC calculation supports this |
| BR-0103 | EIC with 1 qualifying child | ✅ DONE | EITC calculation supports this |
| BR-0105 | EIC with 2 qualifying children | ✅ DONE | EITC calculation supports this |
| BR-0107 | EIC with 3+ qualifying children | ✅ DONE | EITC calculation supports this |

### 7.4 IRA ADJUSTMENTS (BR-0031 to BR-0040, BR-0109 to BR-0118)

| Rule ID | Description | Status | Implementation |
|---------|-------------|--------|----------------|
| BR-0031 | IRA contribution limit $7,000/$8,000 | ⚠️ PARTIAL | Config exists, not enforced |
| BR-0032 | Contribution year labeling | ❌ NOT IMPL | No year tracking |
| BR-0033 | Earned compensation requirement | ❌ NOT IMPL | No validation |
| BR-0034 | Roth IRA MAGI phaseout | ⚠️ PARTIAL | Thresholds exist |
| BR-0035 | Traditional IRA deduction limits | ⚠️ PARTIAL | Thresholds exist |
| BR-0036 | Recharacterization tracking | ❌ NOT IMPL | Not supported |
| BR-0037 | Rollover validation | ❌ NOT IMPL | Not supported |
| BR-0038 | Excess contribution handling | ❌ NOT IMPL | Not supported |
| BR-0039 | RMD indicators | ❌ NOT IMPL | Not supported |
| BR-0040 | Form 8606 triggers | ❌ NOT IMPL | Not supported |

### 7.5 BUSINESS INCOME - Schedule C (BR-0041 to BR-0050, BR-0079 to BR-0090)

| Rule ID | Description | Status | Implementation |
|---------|-------------|--------|----------------|
| BR-0041 | Travel expense deductions | ⚠️ PARTIAL | SE expenses exist |
| BR-0042 | Substantiation requirements | ❌ NOT IMPL | No substantiation |
| BR-0043 | Disallow commuting costs | ❌ NOT IMPL | No mileage logic |
| BR-0044 | Standard mileage method | ❌ NOT IMPL | Not implemented |
| BR-0045 | Business/personal use allocation | ❌ NOT IMPL | No allocation |
| BR-0046 | Luxury auto depreciation limits | ❌ NOT IMPL | No depreciation |
| BR-0047 | Section 179 election | ❌ NOT IMPL | Not implemented |
| BR-0048 | Date placed in service | ❌ NOT IMPL | No tracking |
| BR-0049 | Receipt requirements | ❌ NOT IMPL | No receipts |
| BR-0050 | Accountable plan reimbursement | ❌ NOT IMPL | Not tracked |

### 7.6 INCOME: WAGES/COMP (BR-0051 to BR-0060, BR-0091 to BR-0100)

| Rule ID | Description | Status | Implementation |
|---------|-------------|--------|----------------|
| BR-0051 | Income taxable by default | ✅ DONE | All income taxable |
| BR-0052 | Separate tax-exempt interest | ✅ DONE | `income.py:60` |
| BR-0053 | Separate qualified dividends | ✅ DONE | `income.py:55` |
| BR-0054 | Schedule D capital gains | ✅ DONE | Short/long term in income.py |
| BR-0055 | Loss limitation and carryover | ❌ NOT IMPL | No carryover logic |
| BR-0056 | 1099 form mapping | ⚠️ PARTIAL | Form1099Info exists |
| BR-0057 | Social Security taxation | ✅ DONE | `engine.py:442-485` |
| BR-0058 | Retirement distribution codes | ❌ NOT IMPL | No code handling |
| BR-0059 | Scholarship taxation | ❌ NOT IMPL | No scholarship logic |
| BR-0060 | State tax refund handling | ❌ NOT IMPL | No prior year tracking |

### 7.7 OTHER TAXES (BR-0061 to BR-0068)

| Rule ID | Description | Status | Implementation |
|---------|-------------|--------|----------------|
| BR-0061 | Self-employment tax | ✅ DONE | `engine.py:211-250` |
| BR-0062 | Early distribution penalty | ❌ NOT IMPL | No penalty calc |
| BR-0063 | Household employment tax | ❌ NOT IMPL | No Schedule H |
| BR-0064 | NIIT and AMT triggers | ✅ DONE | `engine.py:286-385` |
| BR-0065 | PTC repayment/recapture | ❌ NOT IMPL | No PTC |
| BR-0066 | Underpayment penalty | ❌ NOT IMPL | No penalty calc |
| BR-0067 | Interest and late penalties | ❌ NOT IMPL | No penalty calc |
| BR-0068 | Due diligence checks | ❌ NOT IMPL | No DD checks |

### 7.8 INTAKE & IDENTITY (BR-0119 to BR-0121)

| Rule ID | Description | Status | Implementation |
|---------|-------------|--------|----------------|
| BR-0119 | ITIN validity check | ❌ NOT IMPL | No validation |
| BR-0120 | Name normalization | ❌ NOT IMPL | No normalization |
| BR-0121 | Bank account validation | ❌ NOT IMPL | No banking |

### 7.9 INCOME: INTEREST/DIV/GAINS/RENTAL/RETIREMENT (BR-0124 to BR-0134)

| Rule ID | Description | Status | Implementation |
|---------|-------------|--------|----------------|
| BR-0124 | Early withdrawal penalty routing | ⚠️ PARTIAL | Field exists |
| BR-0125 | Foreign tax paid routing | ⚠️ PARTIAL | FTC field exists |
| BR-0126 | Capital gains cost basis | ❌ NOT IMPL | No basis tracking |
| BR-0127 | Basis unknown flag | ❌ NOT IMPL | No flagging |
| BR-0128 | Rental property tracking | ⚠️ PARTIAL | Basic fields exist |
| BR-0129 | Rollover validation | ❌ NOT IMPL | No validation |
| BR-0130 | Student loan interest 1098-E | ✅ DONE | Deduction implemented |
| BR-0131 | SALT cap enforcement | ✅ DONE | `deductions.py:32-35` |
| BR-0132 | Charitable substantiation | ❌ NOT IMPL | No substantiation |
| BR-0133 | Withholding reconciliation | ⚠️ PARTIAL | W-2 tracking exists |
| BR-0134 | Estimated payment tracking | ✅ DONE | `income.py:75` |

---

## SECTION 8: CONTROL VARIATION RULES (BR-0137 to BR-1000)

Rules BR-0137 through BR-1000 are variations of the core rules (BR-0001 to BR-0136) applied with different control aspects. These represent the same business logic applied in different contexts:

| Control Aspect | Rule Range | Description |
|---------------|------------|-------------|
| Data validation | BR-0137-0151, 0287-0301, 0437-0451, 0587-0601, 0737-0751, 0887-0901 | Input validation rules |
| Worksheet selection | BR-0152-0166, 0302-0316, 0452-0466, 0602-0616, 0752-0766, 0902-0916 | Form/worksheet routing |
| Schedule triggering | BR-0167-0181, 0317-0331, 0467-0481, 0617-0631, 0767-0781, 0917-0931 | Schedule form triggers |
| Documentation | BR-0182-0196, 0332-0346, 0482-0496, 0632-0646, 0782-0796, 0932-0946 | Record keeping |
| Audit defense | BR-0197-0211, 0347-0361, 0497-0511, 0647-0661, 0797-0811, 0947-0961 | Audit trail |
| Threshold handling | BR-0212-0226, 0362-0376, 0512-0526, 0662-0676, 0812-0826, 0962-0976 | Variable thresholds |
| E-file readiness | BR-0227-0241, 0377-0391, 0527-0541, 0677-0691, 0827-0841, 0977-0991 | E-file validation |
| Exception routing | BR-0242-0256, 0392-0406, 0542-0556, 0692-0706, 0842-0856, 0992-1000 | Error handling |
| Cross-form reconciliation | BR-0257-0271, 0407-0421, 0557-0571, 0707-0721, 0857-0871 | Form cross-checks |
| Security/privacy | BR-0272-0286, 0422-0436, 0572-0586, 0722-0736, 0872-0886 | Data security |

**Implementation Status for Control Aspects:**
- Data validation: ⚠️ PARTIAL - Pydantic model validation exists
- Worksheet selection: ❌ NOT IMPL - No worksheet routing
- Schedule triggering: ⚠️ PARTIAL - Some schedule detection
- Documentation: ❌ NOT IMPL - No document management
- Audit defense: ⚠️ PARTIAL - `src/audit/` module exists
- Threshold handling: ✅ DONE - `tax_year_config.py` handles thresholds
- E-file readiness: ❌ NOT IMPL - No e-file validation
- Exception routing: ⚠️ PARTIAL - Basic error handling
- Cross-form reconciliation: ❌ NOT IMPL - No cross-form checks
- Security/privacy: ⚠️ PARTIAL - Basic field validation

---

## SECTION 9: APPENDIX - DUPLICATE RULES (BR3 Series)

The BR3 series (BR3-0001 to BR3-1000) contains significant duplication. The following patterns were identified:

- Rules BR3-0601 to BR3-1000 largely repeat BR3-0001 to BR3-0400
- ~500 rules are direct duplicates
- ~200 rules are minor variations

After deduplication, the unique rule count is approximately **500 unique rules** across both series.

---

## SECTION 10: IMPLEMENTATION SUMMARY BY CATEGORY

| Category | Total Rules | Implemented | Partial | Not Impl | Status |
|----------|-------------|-------------|---------|----------|--------|
| Filing Requirements | 18 | 7 | 3 | 8 | 39% done |
| Standard Deduction | 10 | 8 | 0 | 2 | 80% done |
| EITC/CTC/EDU Credits | 14 | 8 | 1 | 5 | 57% done |
| IRA/Adjustments | 18 | 0 | 4 | 14 | 11% done |
| Business Income (Sch C) | 22 | 0 | 1 | 21 | 2% done |
| Wages/Compensation | 20 | 5 | 2 | 13 | 25% done |
| Other Taxes | 8 | 2 | 0 | 6 | 25% done |
| Intake & Identity | 3 | 0 | 0 | 3 | 0% done |
| Interest/Div/Gains | 11 | 3 | 4 | 4 | 27% done |
| Control Variations | ~900 | ~100 | ~200 | ~600 | ~11% done |
| **TOTAL** | **~1024** | **~133** | **~215** | **~676** | **~13% done** |

---

## SECTION 11: CRITICAL IMPLEMENTATION GAPS

### Immediate Priority (Blocks Basic Filing)

1. **Dependent Qualification Tests (QC/QR)** - BR-0023 to BR-0026
   - Required for: CTC, EITC, HOH status
   - Impact: HIGH - affects eligibility determination

2. **Gambling Income/Losses** - BR3-0051 to BR3-0060
   - Required for: Complete income reporting
   - Impact: HIGH - common income source

3. **Virtual Currency** - BR3-0101 to BR3-0120
   - Required for: Form 1040 question compliance
   - Impact: HIGH - IRS mandatory question

### High Priority (Common Scenarios)

4. **K-1 Processing** - BR3-0281 to BR3-0295
   - Required for: Business/partnership/S-corp income
   - Impact: HIGH - many self-employed filers

5. **Education Credits Complete** - BR2-0600 to BR2-0650
   - Required for: AOTC/LLC calculations
   - Impact: MEDIUM - students and parents

6. **IRA Contribution Limits** - BR-0031 to BR-0040
   - Required for: Retirement planning accuracy
   - Impact: MEDIUM - retirement savers

### Medium Priority (Edge Cases)

7. **Rollover/Conversion Tracking** - BR-0036, BR-0037
8. **Casualty Loss Limits** - BR2-0750 to BR2-0780
9. **Foreign Tax Credit Calculation** - BR2-0700 to BR2-0730
10. **Premium Tax Credit** - BR3-0151 to BR3-0165

---

**End of Report**
