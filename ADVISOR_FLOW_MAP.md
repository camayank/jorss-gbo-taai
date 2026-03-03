
## COMPLETE INTELLIGENT ADVISOR FLOW MAP

Based on exhaustive analysis of `/Users/rakeshanita/Desktop/MAYANK-HQ/60_Code/jorss-gbo/src/web/static/js/pages/intelligent-advisor.js`, here is the complete flow mapping:

---

### **ENTRY & CONSENT FLOW**

**Initial Page Load → `initializeSession()`**
- Initializes session with `sessionId`
- Checks for existing session with `checkForExistingSession()`
- If session exists: `restoreSession()` → resume conversation
- If new: `sendInitialGreeting()` → displays initial greeting message with buttons:
  - `yes_upload` → document upload flow
  - `what_docs` → educational message about documents
  - `no_manual` → skip to questioning

---

### **LEAD CAPTURE FLOW (Name, Email, Phone)**

#### **NAME ENTRY (`enter_name` / `skip_name`)**
| Handler | Action | Next Step |
|---------|--------|-----------|
| `enter_name` | Shows text input for full name | `captureName()` function |
| `skip_name` | Adds 5 points to lead score | → `proceedToDataGathering()` |

**`captureName()` Processing:**
- Validates: ≥2 characters, sanitizes dangerous chars
- Stores in `extractedData.contact.name`
- Awards +15 lead score
- Shows email capture question

#### **EMAIL ENTRY (`enter_email` / `skip_email`)**
| Handler | Action | Points | Next Step |
|---------|--------|--------|-----------|
| `enter_email` | Shows email input | — | `captureEmail()` function |
| `skip_email` | Stores nothing, adds points | +10 | → `proceedToDataGathering()` |

**`captureEmail()` Processing:**
- Validates: email regex check, max 254 chars
- Stores in `extractedData.contact.email`
- Awards +20 points (QUALIFIES LEAD = **leadQualified = true**)
- Updates lead score calculation
- Shows data gathering mode selection:
  - `upload_docs_qualified` → Document upload
  - `conversational_qualified` → Questioning
  - `hybrid_qualified` → Documents + questions

---

### **DOCUMENT UPLOAD FLOW**

#### **Upload Mode Qualifiers**
| Handler | Prefix | Condition | Next |
|---------|--------|-----------|------|
| `upload_docs_qualified` | `upload_docs_qualified` | User has email | File input dialog |
| `conversational_qualified` | `conversational_qualified` | User has email | `startIntelligentQuestioning()` |
| `hybrid_qualified` | `hybrid_qualified` | User has email | Show upload + start questioning |

**`yes_upload` Handler:**
- Displays document type education message
- Shows upload button
- Provides option to skip: `no_manual` → start questioning

**`what_docs` Handler:**
- Shows educational message about W-2s, 1099s, prior returns, deductions
- Offers choice between:
  - `yes_upload` → Upload documents
  - `no_manual` → Answer questions conversationally

**`upload_w2` / `upload_1099` / `upload_other`:**
- All trigger `document.getElementById('fileInput').click()`
- File upload handled by `handleFileSelect()` → `uploadFileToAI()`

---

### **INITIAL GREETING BRANCHES**

**`yes_upload` → File Upload Workflow**
- Shows "Express Lane document analysis" message
- Lists supported docs: W-2, 1099, 1098, prior returns
- Trigger: `document.getElementById('fileInput').click()`

**`no_manual` → Bypass to Questioning**
- User wants to skip docs
- Shows filing status question directly (first question in `startIntelligentQuestioning()`)

---

### **FILING STATUS HANDLERS (`filing_*`)**

| Handler | Value | Label Shown | Mapping | Next |
|---------|-------|-------------|---------|------|
| `filing_single` | `filing_single` | Single | Single | Check divorce? |
| `filing_married` | `filing_married` | Married Filing Jointly | Married Filing Jointly | Check divorce? |
| `filing_hoh` | `filing_hoh` | Head of Household | Head of Household | Check divorce? |
| `filing_mfs` | `filing_mfs` | Married Filing Separately | Married Filing Separately | Check divorce? |
| `filing_qss` | `filing_qss` | Qualifying Surviving Spouse | Qualifying Surviving Spouse | Check divorce? |

**Actions for ALL `filing_*`:**
- Adds message: status text
- Sets confirmed value: `tax_profile.filing_status`
- Awards +10 points
- Updates stats & savings estimate
- **Conditional Check:** If (single/hoh/mfs) AND divorce NOT explored → Ask divorce question
- **Otherwise:** → `startIntelligentQuestioning()`

---

### **DIVORCE & MARITAL STATUS HANDLERS (`divorce_*`)**

#### **Initial Divorce Selector (`divorce_*`)**
| Handler | Value | Display | Condition | Next |
|---------|-------|---------|-----------|------|
| `divorce_recent` | `divorce_recent` | Recently divorced | Sets marital_change='recent' | Ask divorce year |
| `divorce_separated` | `divorce_separated` | Legally separated | Sets is_separated=true | Ask living arrangement |
| `divorce_widowed` | `divorce_widowed` | Widowed this year | Sets is_widowed=true | Ask dependent count |
| `divorce_none` | `divorce_none` | No change | Sets marital_change=none | → `startIntelligentQuestioning()` |

#### **Sub-flows:**

**DIVORCE YEAR (`divorce_year_*`)**
| Handler | Value | Next |
|---------|-------|------|
| `divorce_year_pre2019` | `divorce_year_pre2019` | Ask about alimony paid/received |
| `divorce_year_post2019` | `divorce_year_post2019` | Ask about child custody |

**ALIMONY (`alimony_*`)**
| Handler | Value | Amount Question | Next |
|---------|-------|-----------------|------|
| `alimony_paid` | `alimony_paid` | Ask how much paid | → `alimony_amt_*` |
| `alimony_received` | `alimony_received` | Ask how much received | → `alimony_amt_*` |
| `alimony_none` | `alimony_none` | No question | → `startIntelligentQuestioning()` |

**ALIMONY AMOUNT (`alimony_amt_*`)**
| Handler | Value Range | Stored Value | Next |
|---------|-------------|--------------|------|
| `alimony_amt_paid_under10k` | <$10k | 5,000 | `startIntelligentQuestioning()` |
| `alimony_amt_paid_10_25k` | $10-25k | 17,500 | `startIntelligentQuestioning()` |
| `alimony_amt_paid_25_50k` | $25-50k | 37,500 | `startIntelligentQuestioning()` |
| `alimony_amt_paid_over50k` | >$50k | 75,000 | `startIntelligentQuestioning()` |
| `alimony_amt_received_*` | (same ranges) | (same values) | `startIntelligentQuestioning()` |

**SEPARATED LIVING (`separated_*`)**
| Handler | Value | Next |
|---------|-------|------|
| `separated_live_apart` | `separated_live_apart` | Ask 6-month separation requirement |
| `separated_same_home` | `separated_same_home` | → `startIntelligentQuestioning()` |

**6 MONTHS APART (`apart_6months_*`)**
| Handler | Value | Effect | Next |
|---------|-------|--------|------|
| `apart_6months_yes` | `apart_6months_yes` | Sets may_qualify_hoh=true | → `startIntelligentQuestioning()` |
| `apart_6months_no` | `apart_6months_no` | No effect | → `startIntelligentQuestioning()` |

**CUSTODY (`custody_*`)**
| Handler | Value | Next |
|---------|-------|------|
| `custody_primary` | `custody_primary` | Ask about Form 8332 |
| `custody_shared` | `custody_shared` | Ask about Form 8332 |
| `custody_ex` | `custody_ex` | → `startIntelligentQuestioning()` |
| `custody_none` | `custody_none` | → `startIntelligentQuestioning()` |

**FORM 8332 (`form8332_*`)**
| Handler | Value | Effect | Next |
|---------|-------|--------|------|
| `form8332_signed` | `form8332_signed` | Sets released_dependency_claim=true | → `startIntelligentQuestioning()` |
| `form8332_no` | `form8332_no` | Claim children | → `startIntelligentQuestioning()` |
| `form8332_alternate` | `form8332_alternate` | Sets alternates_dependency_claim=true | → `startIntelligentQuestioning()` |
| `form8332_unsure` | `form8332_unsure` | No effect | → `startIntelligentQuestioning()` |

**WIDOWED (`widowed_*`)**
| Handler | Value | Effect | Next |
|---------|-------|--------|------|
| `widowed_with_deps` | `widowed_with_deps` | Sets qualifies_qss=true | Show QSS benefit message → `startIntelligentQuestioning()` |
| `widowed_no_deps` | `widowed_no_deps` | No effect | → `startIntelligentQuestioning()` |

---

### **INCOME HANDLERS (`income_*`)**

| Handler | Value | Label | Stored Amount | Points | Next |
|---------|-------|-------|----------------|--------|------|
| `income_custom` | `income_custom` | Custom entry | User input | +15 | `captureIncome()` |
| `income_0_50k` | `income_0_50k` | $0-$50k | 35,000 | +15 | → `startIntelligentQuestioning()` |
| `income_50_100k` | `income_50_100k` | $50-100k | 75,000 | +15 | → `startIntelligentQuestioning()` |
| `income_100_200k` | `income_100_200k` | $100-200k | 150,000 | +15 | → `startIntelligentQuestioning()` |
| `income_200_500k` | `income_200_500k` | $200-500k | 350,000 | +15 | → `startIntelligentQuestioning()` |
| `income_500k_plus` | `income_500k_plus` | >$500k | 750,000 | +15 | → `startIntelligentQuestioning()` |

**`captureIncome()` Processing:**
- Validates: positive number, max $50M
- Stores in `tax_profile.total_income` & `tax_profile.w2_income`
- Awards +15 points
- Calls `updateSavingsEstimate()`
- Proceeds to next questioning phase

---

### **DEPENDENTS HANDLERS (`dependents_*`)**

| Handler | Value | Label | Stored | Next |
|---------|-------|-------|--------|------|
| `dependents_0` | `dependents_0` | No dependents | 0 | → `startIntelligentQuestioning()` |
| `dependents_1` | `dependents_1` | 1 dependent | 1 | → `startIntelligentQuestioning()` |
| `dependents_2` | `dependents_2` | 2 dependents | 2 | → `startIntelligentQuestioning()` |
| `dependents_3plus` | `dependents_3plus` | 3+ dependents | 3 | → `startIntelligentQuestioning()` |

**Actions:**
- Awards +10 points
- Sets confirmed value `tax_profile.dependents`
- Calculates lead score
- Continues questioning

---

### **STATE HANDLERS (`state_*`)**

**ALL State Codes:** `AK, AL, AR, AZ, CA, CO, CT, DE, FL, GA, HI, IA, ID, IL, IN, KS, KY, LA, MA, MD, ME, MI, MN, MO, MS, MT, NC, ND, NE, NH, NJ, NM, NV, NY, OH, OK, OR, PA, RI, SC, SD, TN, TX, UT, VA, VT, WA, WI, WV, WY, DC`

| Handler | Value | Label | Points | Next |
|---------|-------|-------|--------|------|
| `state_XX` | `state_XX` | State name | +5 | Check local taxes / Special cases |

**Logic After State Selection:**

1. **Special States with Local Tax Follow-ups:** NY, OH, PA, MD, IN, KY
   - Shows city/county selector: `localtax_*`

2. **No Income Tax States:** AK, FL, NV, SD, TN, TX, WA, WY, NH
   - Shows benefit message → continues questioning

3. **High Tax States:** CA, NY, NJ, CT, MA, OR, MN, HI
   - Flags `high_tax_state=true` → continues questioning

4. **Default:**
   - → `startIntelligentQuestioning()`

#### **LOCAL TAX HANDLERS (`localtax_*`)**
| Handler | Value | City/County Options | Tax Rate | Next |
|---------|-------|---------------------|----------|------|
| `localtax_NY_0` | NYC | New York City | 3.876% | Continue + show rate |
| `localtax_NY_1` | Yonkers | Yonkers | 1.5% | Continue + show rate |
| `localtax_OH_0` | Columbus | Columbus | 2.5% | Continue + show rate |
| `localtax_PA_0` | Philadelphia | Philadelphia | 3.79% | Continue + show rate |
| `localtax_MD_0` | Baltimore City | Baltimore City | 3.2% | Continue + show rate |
| `localtax_IN_0` | Indianapolis/Marion | Indianapolis | 2.02% | Continue + show rate |
| `localtax_KY_0` | Louisville | Louisville | 2.2% | Continue + show rate |
| `localtax_*_unsure` | Unknown | (user unsure) | 0 | Continue |

**Actions:**
- Stores city and tax rate
- If rate > 0: shows calculated tax message
- → `startIntelligentQuestioning()`

---

### **INCOME SOURCE HANDLERS (`source_*`)**

| Handler | Value | Label | Sets Field | Points | Next |
|---------|-------|-------|------------|--------|------|
| `source_w2` | `source_w2` | W-2 Employee | income_source='W-2 Employee' | +10 | Continue |
| `source_self_employed` | `source_self_employed` | Self-Employed / 1099 | is_self_employed=true | +10 | Continue |
| `source_business` | `source_business` | Business Owner | income_source='Business Owner' | +10 | Continue |
| `source_investments` | `source_investments` | Investments / Retirement | income_source='Investments / Retirement' | +10 | Ask retirement type |
| `source_multiple` | `source_multiple` | Multiple sources | income_source='Multiple sources' | +10 | Continue |

**Retirement Income Sub-flow (`retire_income_*`):**
| Handler | Value | Next |
|---------|-------|------|
| `retire_income_ss` | Social Security | Ask SS amount |
| `retire_income_pension` | Pension | Ask pension amount |
| `retire_income_ira` | IRA/401k withdrawals | Ask RMD status |
| `retire_income_invest` | Investment income | → `startIntelligentQuestioning()` |
| `retire_income_multiple` | Multiple types | Ask SS amount |

---

### **WITHHOLDING HANDLERS (`withhold_*`)**

| Handler | Value | Label | Effect | Next |
|---------|-------|-------|--------|------|
| `withhold_strategic` | `withhold_strategic` | Adjust W-4 strategically | Sets withholding_explored=true | Continue |
| `withhold_default` | `withhold_default` | Default settings | Sets withholding_explored=true | Continue |
| `withhold_large_refund` | `withhold_large_refund` | Usually large refund | Sets withholding_explored=true | Continue |
| `withhold_owe` | `withhold_owe` | Usually owe taxes | Sets withholding_explored=true | Continue |
| `withhold_skip` | `withhold_skip` | Not sure / Skip | Sets withholding_explored=true | Continue |

---

### **PRIOR YEAR TAX HANDLERS (`prior_*`)**

| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `prior_large_refund` | `prior_large_refund` | Large refund >$2k | Continue |
| `prior_small_refund` | `prior_small_refund` | Small refund <$2k | Continue |
| `prior_owed` | `prior_owed` | Owed money | Continue |
| `prior_breakeven` | `prior_breakeven` | About break-even | Continue |
| `prior_skip` | `prior_skip` | First time / Skip | Continue |

---

### **SPOUSE INCOME HANDLERS (`spouse_*`)**

| Handler | Value | Label | Effect | Next |
|---------|-------|-------|--------|------|
| `spouse_w2` | `spouse_w2` | Yes, W-2 employment | Sets spouse_income_explored=true | Continue |
| `spouse_self_employed` | `spouse_self_employed` | Yes, self-employed | Sets spouse_income_explored=true | Continue |
| `spouse_both` | `spouse_both` | Both W-2 and self-employed | Sets spouse_income_explored=true | Continue |
| `spouse_none` | `spouse_none` | No spouse income | Sets spouse_income_explored=true | Continue |
| `spouse_skip` | `spouse_skip` | Skip question | Sets spouse_income_explored=true | Continue |

---

### **BUSINESS HANDLERS**

#### **Business Type (`biz_*`)**
| Handler | Value | Label | Sets Field | Next |
|---------|-------|-------|------------|------|
| `biz_professional` | `biz_professional` | Professional Services | business_type='professional' | Ask entity type |
| `biz_retail` | `biz_retail` | Retail / E-commerce | business_type='retail' | Ask entity type |
| `biz_realestate` | `biz_realestate` | Real Estate | business_type='realestate' | Ask entity type |
| `biz_tech` | `biz_tech` | Tech / Software | business_type='tech' | Ask entity type |
| `biz_farm` | `biz_farm` | Farming / Agriculture | business_type='farm' | Ask farm-specific questions |
| `biz_service` | `biz_service` | Other Service | business_type='service' | Ask entity type |

#### **Entity Type (`entity_*`)**
| Handler | Value | Label | Sets Field | Next |
|---------|-------|-------|------------|------|
| `entity_sole` | `entity_sole` | Sole Proprietorship | entity_type='sole' | Ask revenue |
| `entity_llc_single` | `entity_llc_single` | Single-Member LLC | entity_type='llc_single' | Ask revenue |
| `entity_llc_multi` | `entity_llc_multi` | Multi-Member LLC / Partnership | entity_type='llc_multi' | Ask revenue |
| `entity_scorp` | `entity_scorp` | S-Corporation | entity_type='scorp' | Ask S-Corp specific questions |
| `entity_ccorp` | `entity_ccorp` | C-Corporation | entity_type='ccorp' | Ask revenue |

#### **S-CORP HANDLERS (`scorp_*`)**
| Handler | Value Pattern | Question | Options |
|---------|---------------|----------|---------|
| `scorp_salary_*` | Amount ranges | S-Corp owner salary | <$50k, $50-100k, $100-150k, >$150k |
| `scorp_w2_*` | `scorp_w2_under5k` to `scorp_w2_over50k` | W-2 wages paid | Multiple ranges |
| `scorp_dist_*` | `scorp_dist_under10k` to `scorp_dist_over100k` | Distributions taken | Multiple ranges |

#### **BUSINESS REVENUE (`revenue_*`)**
| Handler | Value | Label | Stored | Next |
|---------|-------|-------|--------|------|
| `revenue_under50k` | `revenue_under50k` | <$50k | 25,000 | Ask expenses |
| `revenue_50_100k` | `revenue_50_100k` | $50-100k | 75,000 | Ask expenses |
| `revenue_100_250k` | `revenue_100_250k` | $100-250k | 175,000 | Ask expenses |
| `revenue_250_500k` | `revenue_250_500k` | $250-500k | 375,000 | Ask expenses |
| `revenue_over500k` | `revenue_over500k` | >$500k | 750,000 | Ask expenses |

#### **BUSINESS EXPENSES (Multi-Select) (`bizexp_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `bizexp_home_office` | `bizexp_home_office` | Home Office | business_expenses_explored=true | Continue |
| `bizexp_vehicle` | `bizexp_vehicle` | Vehicle / Mileage | (multi-select) | Continue |
| `bizexp_equipment` | `bizexp_equipment` | Equipment & Software | (multi-select) | Continue |
| `bizexp_marketing` | `bizexp_marketing` | Marketing & Advertising | (multi-select) | Continue |
| `bizexp_supplies` | `bizexp_supplies` | Supplies & Materials | (multi-select) | Continue |
| `bizexp_training` | `bizexp_training` | Training & Education | (multi-select) | Continue |

**Multi-select submission** (comma-separated):
- `bizexp_home_office,bizexp_vehicle` → Shows label, calls `processAIResponse(label)`

#### **NET BUSINESS INCOME (`netincome_*`)**
| Handler | Value | Label | Stored | Next |
|---------|-------|-------|--------|------|
| `netincome_under25k` | `netincome_under25k` | <$25k net | — | Continue |
| `netincome_25_75k` | `netincome_25_75k` | $25-75k | — | Continue |
| `netincome_75_150k` | `netincome_75_150k` | $75-150k | — | Continue |
| `netincome_150_250k` | `netincome_150_250k` | $150-250k | — | Continue |
| `netincome_over250k` | `netincome_over250k` | >$250k | — | Continue |

#### **FARM HANDLERS**
| Handler Pattern | Description |
|-----------------|-------------|
| `farm_type_*` | Ask farm type (livestock, crops, dairy, etc.) |
| `farm_income_*` | Ask farm income ranges |
| `farm_exp_*` | Multi-select farm expenses (feed, equipment, land maintenance, etc.) |

#### **QBI DEDUCTION (`qbi_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `qbi_yes` | `qbi_yes` | I claim QBI | Continue |
| `qbi_learn` | `qbi_learn` | What is it? | Show QBI benefit message → Continue |
| `qbi_cpa` | `qbi_cpa` | My CPA handles it | Continue |
| `qbi_unsure` | `qbi_unsure` | Not sure | Continue |
| `qbi_noted` / `qbi_cpa_help` | Special cases | Noted for later | Continue |

---

### **INVESTMENT HANDLERS (`invest_*`, `capgain_*`, etc.)**

#### **INVESTMENT TYPE (Multi-Select) (`invest_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `invest_stocks` | `invest_stocks` | Stock dividends & capital gains | investment_explored=true | Continue |
| `invest_rental` | `invest_rental` | Rental property income | (multi-select) | Continue |
| `invest_interest` | `invest_interest` | Interest income | (multi-select) | Continue |
| `invest_k1` | `invest_k1` | Partnership/K-1 | (multi-select) | Continue |
| `invest_crypto` | `invest_crypto` | Cryptocurrency | (multi-select) | Continue |

#### **CAPITAL GAINS (`capgain_*`)**
| Handler | Value | Label | Flag | Next |
|---------|-------|-------|------|------|
| `capgain_gains` | `capgain_gains` | Net gains (profit) | has_capital_gains=true | Ask amount |
| `capgain_losses` | `capgain_losses` | Net losses | has_capital_losses=true | Ask amount |
| `capgain_even` | `capgain_even` | Break-even | — | Continue |
| `capgain_none` | `capgain_none` | Haven't sold | — | Continue |
| `capgain_longterm` | `capgain_longterm` | Long-term | — | Continue |
| `capgain_shortterm` | `capgain_shortterm` | Short-term | — | Continue |
| `capgain_mixed` | `capgain_mixed` | Mix of both | — | Continue |
| `capgain_unsure` | `capgain_unsure` | Unsure | — | Continue |

#### **CAPITAL GAINS AMOUNT (`capgainamt_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `capgainamt_under10k` | `capgainamt_under10k` | <$10k | Continue |
| `capgainamt_10_50k` | `capgainamt_10_50k` | $10-50k | Continue |
| `capgainamt_50_100k` | `capgainamt_50_100k` | $50-100k | Continue |
| `capgainamt_over100k` | `capgainamt_over100k` | >$100k | Continue |

#### **CAPITAL LOSSES AMOUNT (`caplossamt_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `caplossamt_under3k` | `caplossamt_under3k` | <$3k | Continue |
| `caplossamt_3_10k` | `caplossamt_3_10k` | $3-10k | Continue |
| `caplossamt_over10k` | `caplossamt_over10k` | >$10k | Continue |

#### **WASH SALE (`washsale_*`)**
| Handler | Value | Description | Next |
|---------|-------|-------------|------|
| `washsale_yes` | `washsale_yes` | Has wash sales | Ask amount |
| `washsale_no` | `washsale_no` | No wash sales | Continue |

#### **WASH SALE PERCENT (`washsale_pct_*`)**
| Handler | Value | Percent | Next |
|---------|-------|---------|------|
| `washsale_pct_under25` | `washsale_pct_under25` | <25% | Continue |
| `washsale_pct_25_50` | `washsale_pct_25_50` | 25-50% | Continue |
| `washsale_pct_over50` | `washsale_pct_over50` | >50% | Continue |

---

### **RENTAL PROPERTY HANDLERS (`rental_*`)**

| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `rental_1` | `rental_1` | 1 property | rental_explored=true | Ask income |
| `rental_2_4` | `rental_2_4` | 2-4 properties | (same) | Ask income |
| `rental_5plus` | `rental_5plus` | 5+ properties | (same) | Ask income |

#### **RENTAL INCOME (`rental_income_*`)**
| Handler | Value | Label | Stored | Next |
|---------|-------|-------|--------|------|
| `rental_income_under20k` | `rental_income_under20k` | <$20k | 15,000 | Continue |
| `rental_income_20_50k` | `rental_income_20_50k` | $20-50k | 35,000 | Continue |
| `rental_income_50_100k` | `rental_income_50_100k` | $50-100k | 75,000 | Continue |
| `rental_income_over100k` | `rental_income_over100k` | >$100k | 150,000 | Continue |

#### **RENTAL DEPRECIATION (`rental_deprec_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `rental_deprec_yes` | `rental_deprec_yes` | Yes, I claim depreciation | Continue |
| `rental_deprec_no` | `rental_deprec_no` | No depreciation | Continue |

#### **RENTAL BASIS (`rental_basis_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `rental_basis_know` | `rental_basis_know` | I know my cost basis | Ask amount |
| `rental_basis_unsure` | `rental_basis_unsure` | Not sure of basis | Continue |

#### **RENTAL EXPENSES (`rental_exp_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `rental_exp_yes` | `rental_exp_yes` | Yes, significant expenses | Ask expense types |
| `rental_exp_no` | `rental_exp_no` | Minimal expenses | Continue |

---

### **DEPENDENT AGE HANDLERS (`dep_age_*`)**

| Handler | Value | Label | Sets | Effects | Next |
|---------|-------|-------|------|---------|------|
| `dep_age_under6` | `dep_age_under6` | All <6 years | dependent_ages='under6' | Sets has_young_children=true | Ask childcare |
| `dep_age_6_17` | `dep_age_6_17` | Children 6-17 | dependent_ages='6_17' | — | Continue |
| `dep_age_college` | `dep_age_college` | College students 18-24 | dependent_ages='college' | — | Ask education credits |
| `dep_age_adult` | `dep_age_adult` | Adult/elderly | dependent_ages='adult' | — | Continue |
| `dep_age_mixed` | `dep_age_mixed` | Mix of ages | dependent_ages='mixed' | — | Ask education credits |

#### **KIDDIE TAX (`kiddie_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `kiddie_yes` | `kiddie_yes` | Has kiddie tax situation | Ask child income amount |
| `kiddie_no` | `kiddie_no` | No kiddie tax | Continue |

#### **KIDDIE INCOME AMOUNT (`kiddie_amt_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `kiddie_amt_under1k` | `kiddie_amt_under1k` | <$1k | Continue |
| `kiddie_amt_1_3k` | `kiddie_amt_1_3k` | $1-3k | Continue |
| `kiddie_amt_3_5k` | `kiddie_amt_3_5k` | $3-5k | Continue |
| `kiddie_amt_over5k` | `kiddie_amt_over5k` | >$5k | Continue |

#### **CHILDCARE HANDLERS (`childcare_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `childcare_high` | `childcare_high` | >$5k/year | childcare_explored=true | Ask expense amount |
| `childcare_low` | `childcare_low` | <$5k/year | (same) | Ask expense amount |
| `childcare_none` | `childcare_none` | No childcare | (same) | Continue |

---

### **DEDUCTION HANDLERS (`deduction_*`, `has_*`)**

#### **Major Deductions (Multi-Select)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `deduction_mortgage` | `deduction_mortgage` | Mortgage interest | has_mortgage=true, deductions_explored=true | Continue |
| `deduction_charity` | `deduction_charity` | Charitable donations | has_charitable=true | Continue |
| `deduction_medical` | `deduction_medical` | High medical expenses | has_medical=true | Continue |
| `deduction_retirement` | `deduction_retirement` | Retirement contributions | has_retirement_contributions=true | Continue |
| `deduction_investment_loss` | `deduction_investment_loss` | Investment losses | — | Continue |
| `deduction_none` | `deduction_none` | None / Continue | deductions_explored=true | Continue |

#### **MORTGAGE AMOUNT (`mortgageamt_*`)**
| Handler | Value | Label | Stored | Next |
|---------|-------|-------|--------|------|
| `mortgageamt_under5k` | `mortgageamt_under5k` | <$5k | 2,500 | Ask property tax |
| `mortgageamt_5_15k` | `mortgageamt_5_15k` | $5-15k | 10,000 | Ask property tax |
| `mortgageamt_15_30k` | `mortgageamt_15_30k` | $15-30k | 22,500 | Ask property tax |
| `mortgageamt_over30k` | `mortgageamt_over30k` | >$30k | 50,000 | Ask property tax |
| `mortgageamt_none` | `mortgageamt_none` | No mortgage / Paid off | 0 | Ask property tax |

#### **PROPERTY TAX AMOUNT (`proptaxamt_*`)**
| Handler | Value | Label | Stored | Next |
|---------|-------|-------|--------|------|
| `proptaxamt_under2k` | `proptaxamt_under2k` | <$2k | 1,000 | Ask charity |
| `proptaxamt_2_5k` | `proptaxamt_2_5k` | $2-5k | 3,500 | Ask charity |
| `proptaxamt_5_10k` | `proptaxamt_5_10k` | $5-10k | 7,500 | Ask charity |
| `proptaxamt_over10k` | `proptaxamt_over10k` | >$10k | 15,000 | Ask charity |

#### **CHARITABLE AMOUNT (`charityamt_*`)**
| Handler | Value | Label | Stored | Next |
|---------|-------|-------|--------|------|
| `charityamt_under1k` | `charityamt_under1k` | <$1k | 500 | Ask medical |
| `charityamt_1_5k` | `charityamt_1_5k` | $1-5k | 3,000 | Ask medical |
| `charityamt_5_10k` | `charityamt_5_10k` | $5-10k | 7,500 | Ask medical |
| `charityamt_over10k` | `charityamt_over10k` | >$10k | 15,000 | Ask medical |

#### **MEDICAL AMOUNT (`medical_amount_*`)**
| Handler | Value Pattern | Label | Stored | Next |
|---------|---------------|-------|--------|------|
| `medical_amount_under5k` | <$5k | <$5k | 2,500 | Continue |
| `medical_amount_5_10k` | $5-10k | $5-10k | 7,500 | Continue |
| `medical_amount_10_25k` | $10-25k | $10-25k | 17,500 | Continue |
| `medical_amount_over25k` | >$25k | >$25k | 35,000 | Continue |
| `medical_amt_skip` | skip | Skip | 0 | Continue |

#### **FOCUS-SPECIFIC MEDICAL (`medical_high`, `medical_moderate`, `medical_ltc`)**
| Handler | Value | Description | Next |
|---------|-------|-------------|------|
| `medical_high` | `medical_high` | High expenses (>$5k/yr) | Ask amount |
| `medical_moderate` | `medical_moderate` | Moderate expenses | Ask amount |
| `medical_ltc` | `medical_ltc` | Long-term care | Ask amount |

---

### **RETIREMENT CONTRIBUTION HANDLERS (`retire_*`, `401k_*`, `hsa_*`)**

#### **RETIREMENT TYPE (`retire_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `retire_401k` | `retire_401k` | 401(k) | has_401k=true, retirement_detailed=true | Ask amount |
| `retire_trad_ira` | `retire_trad_ira` | Traditional IRA | has_traditional_ira=true | Continue |
| `retire_roth_ira` | `retire_roth_ira` | Roth IRA | has_roth_ira=true | Continue |
| `retire_both` | `retire_both` | Both 401k & IRA | has_401k=true, has_ira=true | Continue |
| `retire_sep` | `retire_sep` | SEP-IRA / Solo 401k | has_sep=true | Continue |

#### **401k AMOUNT (`401k_*`)**
| Handler | Value | Label | Stored | Next |
|---------|-------|-------|--------|------|
| `401k_under10k` | `401k_under10k` | <$10k | — | Continue |
| `401k_10_15k` | `401k_10_15k` | $10-15k | — | Continue |
| `401k_15_23k` | `401k_15_23k` | $15-23k | — | Continue |
| `401k_max` | `401k_max` | Maxing out ($23.5k) | — | Continue |
| `401k_unsure` | `401k_unsure` | Not sure | — | Continue |

#### **HSA CONTRIBUTIONS (`hsa_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `hsa_yes` | `hsa_yes` | Yes, I have HSA | has_hsa=true, hsa_explored=true | Ask amount |
| `hsa_no` | `hsa_no` | No HSA | hsa_explored=true | Continue |
| `hsa_unsure` | `hsa_unsure` | Not sure | hsa_explored=true | Continue |

#### **HSA AMOUNT (`hsaamt_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `hsaamt_under2k` | `hsaamt_under2k` | <$2k | Continue |
| `hsaamt_2_4k` | `hsaamt_2_4k` | $2-4k | Continue |
| `hsaamt_max` | `hsaamt_max` | Maxing out ($4.15k/$8.3k) | Continue |
| `hsaamt_unsure` | `hsaamt_unsure` | Not sure | Continue |

#### **SOCIAL SECURITY AMOUNT (`ss_amt_*`)**
| Handler | Value | Label | Stored | Calculation | Next |
|---------|-------|-------|--------|-------------|------|
| `ss_amt_under20k` | `ss_amt_under20k` | <$20k | 15,000 | Calculate % taxable | Ask if show strategies |
| `ss_amt_20_35k` | `ss_amt_20_35k` | $20-35k | 27,500 | (based on provisional income) | Ask if show strategies |
| `ss_amt_35_50k` | `ss_amt_35_50k` | $35-50k | 42,500 | (thresholds vary by filing status) | Ask if show strategies |
| `ss_amt_over50k` | `ss_amt_over50k` | >$50k | 60,000 | Up to 85% taxable | Ask if show strategies |

**SS Strategy Question (`ss_strategy_*`):**
| Handler | Value | Next |
|---------|-------|------|
| `ss_strategy_yes` | `ss_strategy_yes` | Continue to strategies |
| `ss_strategy_no` | `ss_strategy_no` | → `startIntelligentQuestioning()` |

#### **PENSION AMOUNT (`pension_amt_*`)**
| Handler | Value | Label | Stored | Next |
|---------|-------|-------|--------|------|
| `pension_amt_under25k` | `pension_amt_under25k` | <$25k | 15,000 | Continue |
| `pension_amt_25_50k` | `pension_amt_25_50k` | $25-50k | 37,500 | Continue |
| `pension_amt_50_100k` | `pension_amt_50_100k` | $50-100k | 75,000 | Continue |
| `pension_amt_over100k` | `pension_amt_over100k` | >$100k | 150,000 | Continue |

#### **RMD STATUS (`rmd_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `rmd_yes` | `rmd_yes` | Yes, I take RMDs | has_rmd=true | Ask amount |
| `rmd_no` | `rmd_no` | Not yet 73 | — | Continue |
| `rmd_soon` | `rmd_soon` | Close to RMD age | — | Continue |

#### **RMD AMOUNT (`rmd_amt_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `rmd_amt_under10k` | `rmd_amt_under10k` | <$10k | Continue |
| `rmd_amt_10_25k` | `rmd_amt_10_25k` | $10-25k | Continue |
| `rmd_amt_over25k` | `rmd_amt_over25k` | >$25k | Continue |

---

### **STUDENT LOAN HANDLERS (`studentloan_*`)**

| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `studentloan_yes` | `studentloan_yes` | Yes, I pay interest | has_student_loans=true, student_loan_explored=true | Ask amount |
| `studentloan_no` | `studentloan_no` | No student loans | student_loan_explored=true | Continue |

#### **STUDENT LOAN AMOUNT (`studentloanamt_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `studentloanamt_under1k` | `studentloanamt_under1k` | <$1k | Continue |
| `studentloanamt_1_2500` | `studentloanamt_1_2500` | $1-2.5k | Continue |
| `studentloanamt_over2500` | `studentloanamt_over2500` | >$2.5k | Continue |

---

### **EDUCATION CREDIT HANDLERS (`educredit_*`)**

| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `educredit_dependents` | `educredit_dependents` | College tuition for dependents | education_credits_explored=true, has_tuition_credits=true | Ask amount |
| `educredit_self` | `educredit_self` | For myself | (same) | Ask amount |
| `educredit_529` | `educredit_529` | I contribute to 529 | has_529=true | Ask amount |
| `educredit_none` | `educredit_none` | No education expenses | education_credits_explored=true | Continue |

#### **EDUCATION EXPENSE (`edu_*` - from focus flow)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `edu_self` | `edu_self` | For myself | Ask specific education expenses |
| `edu_dependents` | `edu_dependents` | For dependents | Ask specific expenses |
| `edu_loans` | `edu_loans` | Student loan interest | Ask amount |
| `edu_multiple` | `edu_multiple` | Multiple types | Ask details |

#### **EDUCATION AMOUNT (`students_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `students_1` | `students_1` | 1 student | Ask education credit amount |
| `students_2` | `students_2` | 2 students | Ask education credit amount |
| `students_3plus` | `students_3plus` | 3+ students | Ask education credit amount |

#### **STUDENT LOAN INTEREST (`student_loan_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `student_loan_yes` | `student_loan_yes` | Yes, I pay interest | Ask amount |
| `student_loan_no` | `student_loan_no` | No loans | Continue |

#### **COLLEGE STUDENTS (`college_students_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `college_students_aotc` | `college_students_aotc` | American Opportunity Tax Credit | Ask amount |
| `college_students_llc` | `college_students_llc` | Lifetime Learning Credit | Ask amount |
| `college_students_both` | `college_students_both` | Both / Unsure | Ask details |

#### **EDUCATION EXPENSE AMOUNT (`edu_expense_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `edu_expense_under5k` | `edu_expense_under5k` | <$5k | Continue |
| `edu_expense_5_15k` | `edu_expense_5_15k` | $5-15k | Continue |
| `edu_expense_over15k` | `edu_expense_over15k` | >$15k | Continue |

#### **529 CONTRIBUTION (`529amt_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `529amt_under5k` | `529amt_under5k` | <$5k | Continue |
| `529amt_5_15k` | `529amt_5_15k` | $5-15k | Continue |
| `529amt_over15k` | `529amt_over15k` | >$15k | Continue |

---

### **ENERGY CREDIT HANDLERS (`energy_*`)**

| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `energy_solar` | `energy_solar` | Solar panels installed | energy_explored=true | Show benefit message |
| `energy_ev` | `energy_ev` | Electric vehicle purchased | (same) | Show benefit message |
| `energy_hvac` | `energy_hvac` | Heat pump / HVAC upgrade | (same) | Show benefit message |
| `energy_home_improve` | `energy_home_improve` | Windows / insulation / doors | (same) | Show benefit message |
| `energy_none` | `energy_none` | None of these | energy_explored=true | Continue |

---

### **ITEMIZATION HANDLERS (`itemize_*`)**

| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `itemize_yes` | `itemize_yes` | I itemize deductions | itemize_decision_explored=true | Continue |
| `itemize_standard` | `itemize_standard` | I take standard deduction | (same) | Continue |
| `itemize_cpa` | `itemize_cpa` | My CPA decides | (same) | Continue |
| `itemize_unsure` | `itemize_unsure` | Not sure | (same) | Continue |

---

### **TAX GOAL HANDLERS (`goal_*`)**

| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `goal_reduce_taxes` | `goal_reduce_taxes` | Reduce current bill | goals_explored=true, primary_goal='reduce_taxes' | Continue |
| `goal_retirement` | `goal_retirement` | Maximize retirement savings | (same) | Continue |
| `goal_life_event` | `goal_life_event` | Plan for life event | (same) | Ask event type |
| `goal_wealth` | `goal_wealth` | Build long-term wealth | (same) | Continue |
| `goal_optimize` | `goal_optimize` | General optimization | (same) | Continue |

#### **LIFE EVENT (`event_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `event_marriage` | `event_marriage` | Getting married | life_event_type='marriage' | Continue |
| `event_baby` | `event_baby` | Having a baby | life_event_type='baby' | Continue |
| `event_home` | `event_home` | Buying a home | life_event_type='home' | Continue |
| `event_business` | `event_business` | Starting a business | life_event_type='business' | Continue |
| `event_retirement` | `event_retirement` | Retiring soon | life_event_type='retirement' | Continue |
| `event_sale` | `event_sale` | Selling major asset | life_event_type='sale' | Continue |

---

### **HIGH EARNER / ADVANCED HANDLERS (`adv_*`, `crypto_*`, `options_*`, `foreign_*`, etc.)**

#### **ADVANCED STRATEGIES (`adv_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `adv_backdoor` | `adv_backdoor` | Backdoor Roth IRA | Continue |
| `adv_charitable` | `adv_charitable` | Charitable giving optimization (DAF) | Continue |
| `adv_deferred` | `adv_deferred` | Deferred compensation | Continue |
| `adv_estate` | `adv_estate` | Estate planning | Continue |
| `adv_all` | `adv_all` | Show all opportunities | Continue |

#### **CRYPTOCURRENCY (`crypto_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `crypto_hold` | `crypto_hold` | Hold but haven't sold | crypto_explored=true, has_crypto=true | Continue |
| `crypto_sold` | `crypto_sold` | Sold/traded crypto | crypto_explored=true | Ask transaction details |
| `crypto_earned` | `crypto_earned` | Earned crypto (mining/staking) | crypto_explored=true | Ask amount |
| `crypto_none` | `crypto_none` | No crypto | crypto_explored=true | Continue |

#### **CRYPTO TRADES (`crypto_trades_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `crypto_trades_few` | `crypto_trades_few` | Few trades | Continue |
| `crypto_trades_many` | `crypto_trades_many` | Many trades | Continue |

#### **CRYPTO GAIN/LOSS (`crypto_gl_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `crypto_gl_gain` | `crypto_gl_gain` | Net gain | Continue |
| `crypto_gl_loss` | `crypto_gl_loss` | Net loss | Continue |

#### **CRYPTO EARNED (`crypto_earn_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `crypto_earn_yes` | `crypto_earn_yes` | Yes, earned crypto | Ask amount |
| `crypto_earn_no` | `crypto_earn_no` | No earned income | Continue |

#### **CRYPTO EARNED AMOUNT (`crypto_earned_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `crypto_earned_under1k` | `crypto_earned_under1k` | <$1k | Continue |
| `crypto_earned_1_10k` | `crypto_earned_1_10k` | $1-10k | Continue |
| `crypto_earned_over10k` | `crypto_earned_over10k` | >$10k | Continue |

#### **STOCK OPTIONS (`options_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `options_iso` | `options_iso` | ISOs (Incentive Stock Options) | stock_options_explored=true | Ask exercise details |
| `options_nso` | `options_nso` | NSOs (Non-Qualified) | (same) | Ask details |
| `options_rsu` | `options_rsu` | RSUs (Restricted Stock Units) | (same) | Ask vesting |
| `options_espp` | `options_espp` | ESPP (Employee Stock Purchase) | (same) | Ask details |
| `options_none` | `options_none` | No equity compensation | stock_options_explored=true | Continue |

#### **ISO EXERCISED (`iso_exercised_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `iso_exercised_yes` | `iso_exercised_yes` | Yes, exercised ISOs | Ask AMT details |
| `iso_exercised_no` | `iso_exercised_no` | No exercises | Continue |

#### **ISO SPREAD (`iso_spread_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `iso_spread_under10k` | `iso_spread_under10k` | <$10k spread | Continue |
| `iso_spread_10_50k` | `iso_spread_10_50k` | $10-50k | Continue |
| `iso_spread_over50k` | `iso_spread_over50k` | >$50k | Continue |

#### **FOREIGN INCOME (`foreign_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `foreign_income` | `foreign_income` | Yes, foreign income | foreign_explored=true, has_foreign_income=true | Ask type |
| `foreign_accounts` | `foreign_accounts` | Foreign bank accounts only | foreign_explored=true, has_foreign_accounts=true | Ask amount |
| `foreign_both` | `foreign_both` | Both income & accounts | foreign_explored=true | Ask details |
| `foreign_none` | `foreign_none` | No foreign activity | foreign_explored=true | Continue |

#### **FOREIGN INCOME TYPE (`foreign_type_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `foreign_type_salary` | `foreign_type_salary` | Foreign employment salary | Ask FEIE / FTC |
| `foreign_type_business` | `foreign_type_business` | Foreign business income | Ask FEIE / FTC |
| `foreign_type_investment` | `foreign_type_investment` | Investment income abroad | Ask FTC |
| `foreign_type_other` | `foreign_type_other` | Other foreign income | Ask FEIE / FTC |

#### **FOREIGN EARNED INCOME (`foreign_earned_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `foreign_earned_under50k` | `foreign_earned_under50k` | <$50k | Ask FEIE / FTC |
| `foreign_earned_50_100k` | `foreign_earned_50_100k` | $50-100k | Ask FEIE / FTC |
| `foreign_earned_over100k` | `foreign_earned_over100k` | >$100k | Ask FEIE / FTC |

#### **FOREIGN EARNED INCOME EXCLUSION (`feie_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `feie_yes` | `feie_yes` | Eligible for FEIE | Ask amount |
| `feie_no` | `feie_no` | Not eligible | Ask FTC |

#### **FOREIGN HOUSING (`foreign_housing_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `foreign_housing_claim` | `foreign_housing_claim` | Claim housing allowance | Continue |
| `foreign_housing_no` | `foreign_housing_no` | Don't claim | Continue |

#### **FOREIGN TAX CREDIT (`ftc_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `ftc_yes` | `ftc_yes` | Yes, pay foreign taxes | Ask amount |
| `ftc_no` | `ftc_no` | No foreign taxes | Continue |

#### **FOREIGN TAX CREDIT AMOUNT (`ftc_amt_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `ftc_amt_under5k` | `ftc_amt_under5k` | <$5k | Continue |
| `ftc_amt_5_20k` | `ftc_amt_5_20k` | $5-20k | Continue |
| `ftc_amt_over20k` | `ftc_amt_over20k` | >$20k | Continue |

#### **FBAR REPORTING (`fbar_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `fbar_yes` | `fbar_yes` | Yes, foreign accounts >$10k | Continue |
| `fbar_no` | `fbar_no` | No FBAR requirement | Continue |

#### **MULTISTATE FILING (`multistate_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `multistate_no` | `multistate_no` | Just one state | multistate_explored=true | Continue |
| `multistate_work` | `multistate_work` | Worked in another state | (same) | Ask which states |
| `multistate_moved` | `multistate_moved` | Moved to new state | (same) | Ask move date |
| `multistate_remote` | `multistate_remote` | Remote work multiple states | (same) | Ask states |

#### **REMOTE STATES (`remote_states_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `remote_states_2` | `remote_states_2` | 2 states | Continue |
| `remote_states_3_5` | `remote_states_3_5` | 3-5 states | Continue |
| `remote_states_more` | `remote_states_more` | More than 5 | Continue |

#### **MOVED (`moved_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `moved_jan_jun` | `moved_jan_jun` | Jan-June | Continue |
| `moved_jul_dec` | `moved_jul_dec` | July-Dec | Continue |

#### **WORK DAYS (`workdays_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `workdays_under50` | `workdays_under50` | <50 days | Continue |
| `workdays_50_180` | `workdays_50_180` | 50-180 days | Continue |
| `workdays_over180` | `workdays_over180` | >180 days | Continue |

#### **ESTIMATED TAX PAYMENTS (`estimated_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `estimated_yes` | `estimated_yes` | Yes, regular payments | estimated_explored=true | Ask amount |
| `estimated_sometimes` | `estimated_sometimes` | Sometimes inconsistent | estimated_explored=true | Ask amount |
| `estimated_no` | `estimated_no` | No payments | estimated_explored=true | Continue |
| `estimated_unsure` | `estimated_unsure` | Not sure if I should | estimated_explored=true | Continue |

#### **ESTIMATED AMOUNT (`estamt_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `estamt_under5k` | `estamt_under5k` | <$5k | Continue |
| `estamt_5_20k` | `estamt_5_20k` | $5-20k | Continue |
| `estamt_over20k` | `estamt_over20k` | >$20k | Continue |

#### **AMOUNT HANDLERS (General) (`amount_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `amount_under1k` | `amount_under1k` | <$1k | Continue |
| `amount_1_5k` | `amount_1_5k` | $1-5k | Continue |
| `amount_over5k` | `amount_over5k` | >$5k | Continue |

#### **HAS HANDLERS (Binary) (`has_*`)**
| Handler | Value | Label | Sets | Next |
|---------|-------|-------|------|------|
| `has_mortgage` | `has_mortgage` | Has mortgage | — | Ask amount |
| `has_charity` | `has_charity` | Charitable donations | — | Ask amount |
| `has_medical` | `has_medical` | Medical expenses | — | Ask amount |
| `has_business` | `has_business` | Business expenses | — | Ask details |
| `has_retirement` | `has_retirement` | Retirement contributions | — | Ask type |

---

### **FOCUS AREA FLOW** (`focus_*`)

#### **INITIAL FOCUS SELECTION**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `focus_real_estate` | `focus_real_estate` | Real Estate Tax Planning | Ask homeowner status |
| `focus_education` | `focus_education` | Education & Student Loans | Ask education situation |
| `focus_business` | `focus_business` | Business & Self-Employment | Ask business structure |
| `focus_healthcare` | `focus_healthcare` | Healthcare & Medical | Ask expense level |
| `focus_investments` | `focus_investments` | Investments & Retirement | Ask account types |

#### **REAL ESTATE FLOW**
- `homeowner_yes` → Ask mortgage amount
- `homeowner_no` → Continue to deductions
- `homeowner_rental` → Ask rental count
- `rental_props_*` → Ask rental income
- `rental_income_*` → Continue

#### **INVESTMENT FLOW**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `inv_traditional` | `inv_traditional` | 401k / Traditional IRA | Ask contribution |
| `inv_roth` | `inv_roth` | Roth IRA | Ask contribution |
| `inv_brokerage` | `inv_brokerage` | Taxable accounts | Ask amount |
| `inv_multiple` | `inv_multiple` | Multiple types | Ask details |

#### **TRADITIONAL CONTRIB (`trad_contrib_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `trad_contrib_under10k` | `trad_contrib_under10k` | <$10k | Continue |
| `trad_contrib_10_20k` | `trad_contrib_10_20k` | $10-20k | Continue |
| `trad_contrib_over20k` | `trad_contrib_over20k` | >$20k | Continue |

#### **ROTH CONTRIB (`roth_contrib_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `roth_contrib_under5k` | `roth_contrib_under5k` | <$5k | Continue |
| `roth_contrib_5_10k` | `roth_contrib_5_10k` | $5-10k | Continue |
| `roth_contrib_over10k` | `roth_contrib_over10k` | >$10k | Continue |

#### **BUSINESS FOCUS FLOW**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `biz_sole` | `biz_sole` | Sole Proprietor / Freelancer | Ask income |
| `biz_llc` | `biz_llc` | LLC / Partnership | Ask income |
| `biz_corp` | `biz_corp` | S-Corp / C-Corp | Ask income |
| `biz_side` | `biz_side` | Side business / Gig | Ask income |

#### **BUSINESS INCOME (`bizinc_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `bizinc_under25k` | `bizinc_under25k` | <$25k | Ask deductions |
| `bizinc_25_100k` | `bizinc_25_100k` | $25-100k | Ask deductions |
| `bizinc_100_500k` | `bizinc_100_500k` | $100-500k | Ask deductions |
| `bizinc_over500k` | `bizinc_over500k` | >$500k | Ask deductions |

#### **BUSINESS DEDUCTIONS (`deduct_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `deduct_home` | `deduct_home` | Home office deduction | Continue |
| `deduct_vehicle` | `deduct_vehicle` | Vehicle mileage | Continue |
| `deduct_equipment` | `deduct_equipment` | Equipment & software | Continue |
| `deduct_meals` | `deduct_meals` | Meals & entertainment | Continue |
| `deduct_other` | `deduct_other` | Other business expenses | Continue |

#### **BUSINESS CREDITS (`credit_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `credit_wotc` | `credit_wotc` | Work Opportunity Tax Credit | Continue |
| `credit_r_d` | `credit_r_d` | Research & Development | Continue |
| `credit_emp_health` | `credit_emp_health` | Employee health insurance | Continue |

---

### **FINAL FLOW HANDLERS**

#### **QUESTIONING COMPLETION**
When `startIntelligentQuestioning()` completes all phases → `showPreliminarySummary()`

#### **SHOW PRELIMINARY SUMMARY (`showPreliminarySummary()`)**
- Displays collected tax profile summary
- Shows filing status, state, income, complexity
- Shows business details (if applicable)
- Shows investment profile (if applicable)
- Shows deductions & credits
- Shows life event (if applicable)
- Offers buttons:
  - `run_full_analysis` → `performTaxCalculation()`
  - `edit_profile` / `edit_filing` / `edit_income` / `edit_state` → Edit specific fields
  - `analyze_deductions` → Ask deduction questions
  - `show_all_strategies` → Show strategies if already calculated

#### **REVIEW DATA HANDLERS**
| Handler | Value | Next |
|---------|-------|------|
| `review_data` | `review_data` | Show review message → ask edit or continue |
| `make_corrections` | `make_corrections` | Allow edits to specific fields |
| `change_filing_status` | `change_filing_status` | Show filing status options |
| `change_income` | `change_income` | Show income options |
| `change_state` | `change_state` | Show state selector |
| `change_dependents` | `change_dependents` | Show dependent options |
| `describe_change` | `describe_change` | Open free text for AI to process |
| `continue_to_report` | `continue_to_report` | Proceed to `performTaxCalculation()` |

---

### **TAX CALCULATION FLOW** (`performTaxCalculation()`)

**Sequence:**
1. Show loading overlay
2. Call `getIntelligentAnalysis()` → API returns calculation + strategies
3. Hide loading overlay
4. Display tax breakdown:
   - Federal tax
   - State tax
   - Total tax liability
   - Effective tax rate
   - Total potential savings from strategies
5. Offer buttons:
   - `explore_strategies` → `showNextStrategy()`
   - `quick_summary` → Show summary directly

**Error Handling:**
- If analysis fails: show missing fields → user re-answers
- If API fails: show retry option

---

### **STRATEGY REVIEW FLOW**

#### **STRATEGY EXPLORATION (`explore_strategies`)**
- Sets `currentStrategyIndex = 0`
- Calls `showNextStrategy()` for each strategy with:
  - Strategy title
  - Estimated savings
  - Detailed explanation
  - Action steps
  - IRS reference
  - Navigation buttons (Previous/Next or View Summary)

#### **STRATEGY NAVIGATION**
| Handler | Value | Action |
|---------|-------|--------|
| `next_strategy` | `next_strategy` | `currentStrategyIndex++` → show next |
| `previous_strategy` | `previous_strategy` | `currentStrategyIndex--` → show previous |
| `finish_strategies` | `finish_strategies` | `showStrategySummary()` |

#### **QUICK SUMMARY (`quick_summary`)**
- Skips individual strategy review
- Shows summary of all strategies with total savings
- Offers buttons:
  - `generate_report` → Report generation
  - `explore_strategies` → Go back to detailed view
  - `request_cpa_early` → CPA connection

---

### **REPORT GENERATION & DOWNLOAD FLOW**

| Handler | Value | Action | API Call | Next |
|---------|-------|--------|----------|------|
| `generate_report` | `generate_report` | Generate PDF | `/api/v1/advisory-reports/generate` | Poll for completion |
| `download_report` | `download_report` | Trigger download | Direct to `/pdf` | Show success message |
| `view_report` | `view_report` | View online | Open preview page | Back to chat |
| `email_report` | `email_report` | Send via email | `/api/advisor/report/email` | Confirm delivery |
| `schedule_consult` | `schedule_consult` | Schedule CPA call | Show scheduler | Capture time preference |

#### **REPORT EMAIL FLOW**
| Handler | Value | Validates | Next |
|---------|-------|-----------|------|
| `email_report` | `email_report` | Email input | Send via API |

**On Success:**
- Show "Report sent to [email]"
- Offer:
  - `download_report` → Also download PDF
  - `schedule_consult` → Schedule call
  - `finish_satisfied` → Exit

**On Failure:**
- Show "Email not available, download PDF instead"
- Offer:
  - `download_report` → Download PDF
  - `email_report` → Retry

#### **CONSULTATION SCHEDULING (`schedule_time`)**
- Shows scheduling interface
- Captures time preference
- Offers email or phone follow-up

#### **EMAIL-ONLY FOLLOW-UP (`email_only`)**
- User opts for email contact
- No call scheduled
- Reports sent for offline review

---

### **REPORT GENERATION (Early) (`generate_report_early`)**
- Can be called before lead capture is fully complete
- Shows "Generating your report..." message
- Calls `/api/v1/advisory-reports/generate`
- Polls for PDF completion

**Following Generation:**
- Offer download
- Offer email
- Offer CPA connection

---

### **CPA CONNECTION FLOW**

#### **REQUEST CPA EARLY (`request_cpa_early`)**
- Checks if lead score ≥ 60
- If yes: calls `sendLeadToCPA()`
  - Sends contact info + tax profile + score + savings estimate
  - Shows "CPA team will reach out in 24 hours"
  - Offers:
    - `schedule_time` → Schedule call
    - `email_only` → Email only
    - `generate_report` → Get report first

#### **SEND LEAD TO CPA (`sendLeadToCPA()`)**
- API: `POST /api/leads/create`
- Includes:
  - contact (name, email, phone)
  - tax_profile
  - tax_items
  - lead_score
  - complexity
  - estimated_savings
  - session_id
  - source = 'intelligent_advisor'
  - status = 'qualified'

#### **CPA CONNECTION STATUS (`status_*`)**
| Handler | Value | Label | Next |
|---------|-------|-------|------|
| `status_pending` | `status_pending` | Awaiting CPA contact | Wait message |
| `status_scheduled` | `status_scheduled` | Call scheduled | Show appointment |
| `status_completed` | `status_completed` | Consultation done | Ask for feedback |

---

### **UNLOCK PREMIUM STRATEGIES**

| Handler | Value | Action | API Call | Next |
|---------|-------|--------|----------|------|
| `unlock_strategies` | `unlock_strategies` | Unlock all premium strategies | `/api/advisor/unlock-strategies` | Show soft lead capture form |

**On Success:**
- Unlock all locked strategy cards
- Show soft lead capture form:
  - Name input
  - Email input
  - Send & Connect button
  - No thanks button

**On Lead Capture Submit:**
- Call `submitLeadCapture()` → `/api/advisor/report/email`
- Show "Report sent, CPA will contact"
