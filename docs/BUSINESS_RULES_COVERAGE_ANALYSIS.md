# Business Rules Coverage Analysis

## Tax Decision Intelligence Platform - Rule Validation Report

**Analysis Date**: January 2026
**Source File**: US_Individual_Tax_Business_Rules_580_FINAL.xlsx
**Tax Year**: 2025

---

## Executive Summary

### Key Findings

| Metric | Value |
|--------|-------|
| **Rules in Reference File** | 3,000 |
| **Rules Implemented in Platform** | ~500 |
| **Coverage Percentage** | ~16.7% |
| **Categories Covered** | 22 of 40 |
| **Critical Gaps Identified** | 8 major areas |

### Current Implementation Status

**Strengths**:
- Core income rules well-covered (50 rules)
- Deduction rules comprehensive (75 rules)
- Credit calculations robust (75 rules)
- Retirement rules implemented (15 rules)
- EITC/CTC calculations in place

**Gaps Requiring Attention**:
- Virtual Currency & Digital Assets (0 of 75 rules)
- Foreign Assets & Disclosures (0 of 64 rules)
- Household Employment Taxes (0 of 55 rules)
- K-1/Trust/Estate Income (limited coverage)
- Premium Tax Credit (limited coverage)
- Casualty/Theft/Disaster Losses (0 of 59 rules)

---

## Detailed Category Analysis

### Reference File Categories (40 Total, 3,000 Rules)

| Category | Reference Rules | Our Rules | Coverage | Priority |
|----------|-----------------|-----------|----------|----------|
| **FILING REQUIREMENTS** | 80 | ~15 | 19% | HIGH |
| **INCOME: WAGES/COMP** | 78 | 50 | 64% | COVERED |
| **INCOME: INTEREST/DIV** | 60 | 20 | 33% | MEDIUM |
| **INCOME: CAPITAL GAINS** | 60 | 15 | 25% | MEDIUM |
| **INCOME: BUSINESS (SCH C)** | 80 | 25 | 31% | MEDIUM |
| **INCOME: RENTAL/ROYALTY** | 59 | 12 | 20% | MEDIUM |
| **INCOME: RETIREMENT/SS** | 59 | 15 | 25% | MEDIUM |
| **ADJUSTMENTS (SCH 1)** | 79 | 20 | 25% | MEDIUM |
| **DEDUCTIONS: STANDARD** | 67 | 35 | 52% | COVERED |
| **DEDUCTIONS: ITEMIZED** | 59 | 40 | 68% | COVERED |
| **CREDITS: EITC/CTC/EDU** | 75 | 45 | 60% | COVERED |
| **DEPENDENTS: QC/QR/TIEBREAKER** | 67 | 25 | 37% | MEDIUM |
| **AMT (INDIVIDUAL)** | 60 | 10 | 17% | HIGH |
| **OTHER TAXES (SE Tax, etc.)** | 65 | 25 | 38% | MEDIUM |
| **LIMITS: STANDARD DEDUCTION** | 115 | 35 | 30% | MEDIUM |
| **LIMITS: IRA CONTRIBUTIONS** | 112 | 15 | 13% | HIGH |
| **LIMITS: EITC/CTC (GATING)** | 126 | 30 | 24% | MEDIUM |
| **LIMITS: ITEMIZED DEDUCTIONS** | 126 | 35 | 28% | MEDIUM |
| **LIMITS: STUDENT LOAN INTEREST** | 125 | 10 | 8% | MEDIUM |
| **PHASEOUTS: IRA (TRAD/ROTH)** | 130 | 10 | 8% | HIGH |
| **PHASEOUTS: EDUCATION BENEFITS** | 124 | 12 | 10% | HIGH |
| **VIRTUAL CURRENCY & DIGITAL ASSETS** | 75 | 0 | 0% | CRITICAL |
| **ALIMONY & SEPARATION PAYMENTS** | 68 | 0 | 0% | HIGH |
| **GAMBLING & OTHER MISC INCOME** | 67 | 5 | 7% | MEDIUM |
| **FOREIGN ASSETS & DISCLOSURES** | 64 | 0 | 0% | CRITICAL |
| **K-1 / TRUST / ESTATE INCOME** | 60 | 5 | 8% | HIGH |
| **PREMIUM TAX CREDIT (PTC)** | 61 | 3 | 5% | HIGH |
| **HEALTH COVERAGE & 1095 SERIES** | 65 | 12 | 18% | MEDIUM |
| **NET INVESTMENT INCOME TAX (NIIT)** | 55 | 5 | 9% | HIGH |
| **HOUSEHOLD EMPLOYMENT TAXES** | 55 | 0 | 0% | CRITICAL |
| **FILING STATUS EDGE CASES** | 61 | 8 | 13% | HIGH |
| **IDENTITY, IP PIN & FRAUD** | 59 | 5 | 8% | MEDIUM |
| **CASUALTY/THEFT/DISASTER LOSSES** | 59 | 0 | 0% | HIGH |
| **PAYMENTS & WITHHOLDING** | 59 | 10 | 17% | MEDIUM |
| **PAYMENTS, OFFSETS & REFUNDS** | 57 | 8 | 14% | MEDIUM |
| **PENALTIES/INTEREST/ADMIN** | 59 | 10 | 17% | MEDIUM |
| **AUDIT, NOTICES & RECORD RETENTION** | 67 | 10 | 15% | MEDIUM |
| **INTAKE & IDENTITY** | 61 | 15 | 25% | MEDIUM |
| **CAPS & THRESHOLDS: ENGINE CONTROLS** | 16 | 10 | 63% | COVERED |

---

## Our Implementation Architecture

### Current Rules Infrastructure

```
src/
├── validation/
│   └── tax_rules_engine.py          # ~100 field validation rules
│       ├── Personal Information (Rules 1-4)
│       ├── Filing Status (Rules 5-8)
│       ├── Spouse Rules (Rules 9-16)
│       ├── Dependent Rules (Rules 17-25)
│       ├── Income Rules (Rules 26-45)
│       ├── Deduction Rules (Rules 46-60)
│       ├── Credit Rules (Rules 61-90)
│       ├── State Tax Rules (Rules 91-95)
│       └── Cross-Field Rules (Rules 96-100)
│
├── recommendation/
│   └── tax_rules_engine.py          # ~383 comprehensive tax rules
│       ├── INCOME_RULES (50 rules)
│       ├── DEDUCTION_RULES (75 rules)
│       ├── CREDIT_RULES (75 rules)
│       ├── SELF_EMPLOYMENT_RULES (25 rules)
│       ├── RETIREMENT_RULES (15 rules)
│       ├── REAL_ESTATE_RULES (12 rules)
│       ├── HEALTHCARE_RULES (12 rules)
│       ├── EDUCATION_RULES (12 rules)
│       ├── BUSINESS_RULES (12 rules)
│       ├── FAMILY_RULES (10 rules)
│       ├── STATE_RULES (10 rules)
│       ├── FILING_STATUS_RULES (10 rules)
│       ├── PENALTY_RULES (10 rules)
│       ├── TIMING_RULES (10 rules)
│       ├── DOCUMENTATION_RULES (10 rules)
│       ├── CHARITABLE_RULES (10 rules)
│       ├── AMT_RULES (10 rules)
│       ├── INTERNATIONAL_RULES (10 rules)
│       └── NIIT_RULES (5 rules)
│
├── rules/
│   ├── rule_types.py                # Rule category and severity enums
│   ├── rule_engine.py               # Unified rule evaluation engine
│   └── default_rules.py             # ~20 IRS-referenced default rules
│
└── config/
    └── tax_config_loader.py         # Tax year parameters
```

### AI Integration Points

1. **Tax Agent AI** (`src/agent/tax_agent.py`)
   - Uses OpenAI for natural language understanding
   - Applies rules contextually based on conversation
   - Generates smart insights with IRC citations

2. **ML Document Classifier** (`src/ml/`)
   - Classifies tax documents automatically
   - Routes extracted data to appropriate rules

3. **Smart Insights Engine**
   - Applies relevant rules based on tax return data
   - Generates optimization recommendations
   - Provides IRC citations for each insight

---

## Critical Gap Analysis

### Priority 1: CRITICAL GAPS (Immediate Action Required)

#### 1. Virtual Currency & Digital Assets (0% Coverage)
**Reference Rules**: 75
**Impact**: High - IRS increased enforcement in this area

Sample required rules:
- BR3-0004: Compute gain/loss based on FMV at disposition and adjusted basis
- BR3-0012: Treat disposal of virtual currency as a taxable event
- Cost basis tracking for crypto-to-crypto trades
- Airdrop and hard fork income recognition
- NFT transaction handling

**Recommendation**: Implement core crypto rules in Phase 1 (15-20 rules)

#### 2. Foreign Assets & Disclosures (0% Coverage)
**Reference Rules**: 64
**Impact**: High - FBAR/FATCA penalties significant

Sample required rules:
- BR3-0014: Surface FBAR/FATCA compliance alerts
- Foreign account reporting thresholds
- Form 8938 requirements
- PFIC reporting rules

**Recommendation**: Implement compliance alerts and thresholds (10-15 rules)

#### 3. Household Employment Taxes (0% Coverage)
**Reference Rules**: 55
**Impact**: Medium - Nanny tax compliance

Sample required rules:
- BR3-0156: Require EIN for household employers
- Schedule H triggering conditions
- Wage threshold validation
- Quarterly payment requirements

**Recommendation**: Implement basic household employment rules (10 rules)

### Priority 2: HIGH GAPS (Action in Next Quarter)

#### 4. K-1/Trust/Estate Income (8% Coverage)
**Reference Rules**: 60
**Our Coverage**: ~5 rules

Missing:
- Passive activity loss rules
- At-risk limitation handling
- Basis tracking for partnerships
- Suspended loss carryforward

#### 5. Premium Tax Credit (5% Coverage)
**Reference Rules**: 61
**Our Coverage**: ~3 rules

Missing:
- Advance PTC reconciliation
- Multi-household allocation
- FPL-based eligibility tiers
- Clawback calculations

#### 6. AMT (17% Coverage)
**Reference Rules**: 60
**Our Coverage**: ~10 rules

Missing:
- Complete preference item handling
- AMT credit carryforward
- ISO stock option treatment
- State AMT interaction

#### 7. Phaseout Rules (8-10% Coverage)
**Reference Rules**: 254 (IRA + Education)
**Our Coverage**: ~22 rules

Missing:
- Complete MAGI calculations per benefit type
- Contribution recharacterization rules
- Excess contribution handling
- Backdoor Roth validation

#### 8. Casualty/Theft/Disaster Losses (0% Coverage)
**Reference Rules**: 59
**Our Coverage**: 0 rules

Missing:
- Presidential disaster area rules
- Per-event threshold calculations
- AGI floor application
- Insurance reimbursement netting

---

## Rule Implementation Robustness Assessment

### Current Strengths

| Area | Assessment | Notes |
|------|------------|-------|
| **Core Income Calculations** | ROBUST | W-2, 1099-INT/DIV, capital gains covered |
| **Standard Deduction** | ROBUST | All filing statuses, 65+/blind additions |
| **Child Tax Credit** | ROBUST | Phaseouts, refundable portion |
| **EITC** | ROBUST | Income limits, qualifying children |
| **IRS References** | GOOD | IRC citations included in most rules |
| **Field Validation** | ROBUST | 100+ conditional visibility rules |
| **AI Integration** | GOOD | OpenAI-powered insights and classification |

### Areas Needing Enhancement

| Area | Current State | Needed Improvement |
|------|--------------|-------------------|
| **Phaseout Calculations** | Basic | Need standardized phaseout function per BR2-0014 |
| **MAGI Definitions** | Single | Need benefit-specific MAGI calculations |
| **Test Case Generation** | Limited | Need boundary condition testing per BR2-0041 |
| **Audit Trail** | Basic | Need per-rule computation logging per BR-0135 |
| **Document Checklist** | Partial | Need dynamic checklist generation per BR-0136 |

---

## AI Usage in Rules Engine

### Current AI Integration

1. **Document Classification** (`src/ml/`)
   - OpenAI GPT-4o-mini for document type detection
   - TF-IDF fallback classifier
   - 95%+ accuracy on supported document types

2. **Smart Insights Generation** (`src/agent/`)
   - Rule-based triggers combined with AI explanation
   - IRC citation retrieval
   - Natural language recommendations

3. **Tax Return Analysis** (`src/services/tax_optimizer.py`)
   - Scenario comparison
   - Optimization opportunity detection
   - Risk assessment

### Recommended AI Enhancements

1. **Rule Explanation AI**
   - Generate plain-English explanations for complex rules
   - Provide examples for taxpayer education

2. **Dynamic Rule Application**
   - Use AI to determine which rules apply to specific situations
   - Handle edge cases not explicitly coded

3. **Compliance Alert AI**
   - Identify potential audit triggers
   - Suggest documentation requirements

---

## Implementation Roadmap

### Phase 1: Critical Gaps (Weeks 1-4)
- [ ] Virtual Currency basic rules (20 rules)
- [ ] Foreign Asset alerts (15 rules)
- [ ] Household Employment (10 rules)
- [ ] Standardized phaseout function

### Phase 2: High Priority (Weeks 5-8)
- [ ] K-1/Trust/Estate expanded (25 rules)
- [ ] Premium Tax Credit complete (30 rules)
- [ ] AMT comprehensive (30 rules)
- [ ] IRA phaseout complete (40 rules)

### Phase 3: Coverage Expansion (Weeks 9-12)
- [ ] Education benefit phaseouts (40 rules)
- [ ] Casualty/Disaster losses (30 rules)
- [ ] Alimony rules (25 rules)
- [ ] Gambling income rules (20 rules)

### Phase 4: Polish & Testing (Weeks 13-16)
- [ ] Boundary condition test cases
- [ ] Audit trail enhancement
- [ ] Dynamic document checklist
- [ ] AI explanation generation

---

## Metrics & Monitoring

### Target Coverage Goals

| Timeframe | Target Coverage | Rules to Add |
|-----------|-----------------|--------------|
| Q1 2026 | 25% | +250 rules |
| Q2 2026 | 50% | +750 rules |
| Q3 2026 | 75% | +750 rules |
| Q4 2026 | 90% | +450 rules |

### Quality Metrics

- Rule accuracy rate target: >99%
- IRC citation coverage: 100%
- Test case coverage per rule: 3+ cases
- AI explanation availability: 100%

---

## Appendix: Sample Rules from Reference File

### Filing Requirements Examples
```
BR-0001: Use Form 1040 as the default individual return; offer Form 1040-SR
         only if the taxpayer was born before January 2, 1961.
         Reference: Instructions for Form 1040 (2025)

BR-0002: Set the standard filing deadline for calendar-year 2025 returns to
         April 15, 2026, and flag late-filing risk if submission date exceeds.
         Reference: Publication 17 (2025)
```

### Virtual Currency Examples (NOT IMPLEMENTED)
```
BR3-0004: Compute gain or loss based on FMV at disposition and adjusted basis.
          Reference: Form 1040 Instructions (2025)

BR3-0012: Treat disposal of virtual currency as a taxable event unless excluded.
          Reference: IRS Notice 2014-21, Rev. Rul. 2019-24
```

### Phaseout Engine Control Example
```
BR2-0014: Represent phaseouts as a standardized function:
          (MAGI − phaseout_start) / (phaseout_end − phaseout_start),
          floored at 0 and capped at 1, then apply to the reducible amount.
          Reference: IRS Instructions for Form 1040 (2025)
```

---

## Conclusion

The platform has a solid foundation with ~500 implemented rules covering core tax calculations. However, achieving CPA-grade comprehensiveness requires expanding to cover the 3,000 rules in the reference file, with particular focus on:

1. **Virtual Currency** - Critical for modern tax compliance
2. **Foreign Assets** - High penalty exposure area
3. **Phaseout Standardization** - Foundation for many credit/deduction calculations
4. **K-1/Trust Income** - Essential for business/investment taxpayers

The recommended 16-week implementation roadmap would bring coverage to 25% with critical gaps addressed, followed by quarterly expansions to reach 90% coverage by end of 2026.
