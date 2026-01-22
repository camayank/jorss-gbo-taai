# Terminology Simplification - Layman-Friendly Language

**Goal**: Replace technical tax jargon with simple, clear language that anyone can understand

**Date**: 2026-01-21

---

## Technical Terms → Simple Language

### General Terms

| Technical Term | Simple/Friendly Alternative | Explanation |
|----------------|----------------------------|-------------|
| **Filing Status** | "Your Tax Situation" or "Who You're Filing For" | Less bureaucratic |
| **Deductions** | "Tax Savings" or "Money-Saving Expenses" | What it means to users |
| **Credits** | "Tax Breaks" or "Money Back" | More rewarding |
| **Standard Deduction** | "Standard Tax Savings" or "Automatic Savings" | Clearer benefit |
| **Itemized Deductions** | "List Your Expenses to Save More" | Action-oriented |
| **Taxable Income** | "Income You Pay Tax On" | Plain English |
| **AGI** (Adjusted Gross Income) | "Total Income (after adjustments)" | Spell it out |
| **Withholding** | "Taxes Already Paid" or "Money Taken from Paycheck" | What it really is |
| **Refund** | "Money Back" or "Your Refund" | Keep this, it's clear |
| **Owed** | "Amount You Need to Pay" | Clear obligation |
| **E-file** | "File Online" or "Submit Electronically" | Less technical |

---

### Filing Status Terms

| Technical Term | Simple Alternative | Help Text |
|----------------|-------------------|-----------|
| **Single** | "Single" ✓ (Keep) | "You're not married" |
| **Married Filing Jointly** | "Married - Filing Together" | "You and your spouse file one return" |
| **Married Filing Separately** | "Married - Filing Separately" | "You and your spouse file separate returns" |
| **Head of Household** | "Single Parent or Provider" | "You're unmarried and support dependents" |
| **Qualifying Surviving Spouse** | "Widowed (Recent)" | "Your spouse passed away in the last 2 years" |

---

### Form Names (Add Explanations)

| Form | Keep Name | Add Simple Explanation |
|------|-----------|------------------------|
| **W-2** | W-2 | "Wages from your job" |
| **1099** | 1099 | "Other income (freelance, interest, etc.)" |
| **1040** | Keep technical name hidden | Show as "Your Tax Return" |
| **Schedule A** | Hide from user | Just say "Detailed Expenses" |
| **Schedule C** | Hide from user | Just say "Business Income" |

---

### Field Labels

| Technical Label | Simple Alternative |
|----------------|-------------------|
| **SSN** | "Social Security Number" (spell out) |
| **DOB** | "Date of Birth" (spell out) |
| **Filing Preference** | "How do you want to file?" |
| **Dependent** | "Child or Person You Support" |
| **Exemption** | Remove term, explain in context |
| **Qualified expenses** | "Expenses that save you money" |
| **Employer Identification Number** | "Company Tax ID" |

---

### Deduction Categories (Step 4a)

| Technical Category | Simple Alternative | Friendly Icon |
|-------------------|-------------------|---------------|
| **Mortgage Interest & Property Tax** | "Home Expenses" | 🏠 |
| **Medical & Dental Expenses** | "Healthcare Costs" | 🏥 |
| **Charitable Donations** | "Donations & Giving" | ❤️ |
| **Education Expenses** | "School & Education Costs" | 🎓 |
| **Child & Dependent Care** | "Childcare Expenses" | 👶 |
| **Business Expenses** | "Work-Related Costs" | 💼 |
| **Investment & Retirement** | "Savings & Investments" | 📈 |
| **Casualty & Theft Losses** | "Disaster & Theft Losses" | 🔥 |
| **State Taxes** | "State & Local Taxes" | 🏛️ |
| **Other Deductions** | "Other Tax Savings" | 📋 |

---

### Button & Action Text

| Technical Text | Simple Alternative |
|---------------|-------------------|
| **Continue** | "Continue" ✓ or "Next" |
| **Submit Return** | "File Your Taxes" or "Send to IRS" |
| **Review** | "Check Everything" or "Review" ✓ |
| **Calculate** | "Calculate" ✓ or "See Your Total" |
| **Save & Exit** | "Save & Come Back Later" |
| **Import** | "Bring In" or "Load" |
| **Export** | "Download" or "Save Copy" |

---

### Status Messages

| Technical Message | Simple Alternative |
|------------------|-------------------|
| **Session expired** | "Your time ran out. Please log in again." |
| **Validation error** | "Please check this information" |
| **Required field** | "We need this information" |
| **Invalid format** | "Please enter in this format: ___" |
| **Processing...** | "Working on it..." |
| **Authentication required** | "Please sign in first" |

---

### Help Text & Explanations

#### Add Simple Explanations

**Before**: "Enter your AGI"
**After**: "Enter your total income (wages + other income - adjustments)"

**Before**: "Do you qualify for Head of Household?"
**After**: "Are you single and paying for more than half of your home costs?"

**Before**: "Itemize deductions?"
**After**: "Do you want to list your expenses? (Only if they're more than $13,850)"

**Before**: "Filing status"
**After**: "Choose your situation:"

---

## Implementation Locations

### Files to Update

1. **src/web/templates/index.html**
   - Step titles
   - Field labels
   - Button text
   - Help tooltips
   - Category names

2. **src/web/templates/landing.html** (if exists)
   - Marketing copy
   - Feature descriptions

3. **src/config/branding.py**
   - Default messaging
   - Claims and badges

---

## Specific Changes Needed

### Step 1: About You

**Current**:
```
Step 1: About You
Tell us about yourself so we can determine your best filing status
```

**New**:
```
Step 1: About You
Tell us about yourself so we can find the best way to file your taxes
```

---

### Filing Status Section

**Current**:
```
Filing Status
What's your marital status?
```

**New**:
```
Your Tax Situation
Choose the option that describes you:
```

**Cards**:
- "Single - I'm not married"
- "Married - Filing Together (saves money)"
- "Married - Filing Separately"
- "Widowed - My spouse passed away"

---

### Head of Household Question

**Current**:
```
Did you pay more than half the household costs?
```

**New**:
```
Did you pay for more than half of your home's expenses this year?
(Rent, utilities, food, repairs, etc.)
```

---

### Step 2: Documents

**Current**:
```
Step 2: Income & Documents
Upload or enter your income information
```

**New**:
```
Step 2: Your Income
Upload your tax forms or enter your income
```

**Upload Zone**:
```
📸 Tap to Upload Your Tax Documents
Or take a photo with your phone

What to upload:
• W-2 (from your employer)
• 1099 forms (if you have them)
```

---

### Step 3: Income

**Current**:
```
Step 3: Income
Enter your income from all sources
```

**New**:
```
Step 3: How Much Did You Earn?
Enter all money you received this year
```

**W-2 Section**:
```
Income from Your Job (W-2)

Wages: $_______
(Box 1 on your W-2)

Federal Tax Withheld: $_______
(Box 2 - money already paid to IRS)
```

---

### Step 4a: Category Selection

**Current**:
```
Step 4a: Deduction Categories
What types of expenses do you have?
Select all categories that apply to get relevant questions
```

**New**:
```
Step 4: Ways to Save Money on Taxes
Which of these did you spend money on this year?
(Only select what applies to you - we'll ask details next)
```

**"None" Option**:
```
⬜ None of these - I'll just take the standard savings
(Most people choose this - it's $13,850 in automatic tax savings)
```

---

### Step 4b: Deductions

**Current**:
```
Step 4b: Deductions & Credits
Answer questions for the categories you selected
```

**New**:
```
Step 4: Your Tax-Saving Expenses
Tell us about the expenses you selected
(These can reduce the taxes you owe)
```

**Category Headers**:
- "🏠 Home Expenses (mortgage, property tax)"
- "🏥 Healthcare Costs (doctor visits, prescriptions)"
- "❤️ Donations & Giving (charity, non-profits)"

---

### Step 5: Review

**Current**:
```
Step 5: Review & Submit
Review your return before filing
```

**New**:
```
Step 5: Check Everything
Make sure all your information is correct before filing
```

**Sections**:
```
👤 About You
💰 Your Income
💵 Tax Savings
📊 Your Tax Calculation
```

---

### Tax Calculation Display

**Current**:
```
Total Income: $75,000
Adjusted Gross Income: $75,000
Standard Deduction: $13,850
Taxable Income: $61,150
Federal Tax: $8,732.50
Withheld: $12,500.00
Refund: $3,767.50
```

**New**:
```
What You Earned: $75,000
Automatic Tax Savings: -$13,850
Income You Pay Tax On: $61,150
─────────────────────────────
Your Tax: $8,732.50
Already Paid: -$12,500.00
─────────────────────────────
💰 You're Getting Back: $3,767.50
```

---

## Help Tooltips to Add

### Everywhere

Add simple explanations:

```html
<span class="help-tip" data-tooltip="Explanation here">?</span>
```

**Examples**:

**SSN**: "Your Social Security Number (9 digits)"
**Filing Status**: "This affects how much tax you pay"
**Standard Deduction**: "Automatic tax savings everyone gets ($13,850)"
**W-2**: "The form your employer gives you showing your wages"
**Withholding**: "Taxes your employer already sent to the IRS"

---

## Progressive Disclosure

### Show Technical Terms Only When Needed

**Hide from user**:
- Form numbers (1040, Schedule A, etc.)
- Tax code sections
- IRS jargon
- Acronyms (unless spelled out)

**Show to user**:
- Simple descriptions
- Plain language
- What it means for them
- Clear actions to take

---

## Tone & Voice

### Guidelines

**DO**:
- Use "you" and "your" (conversational)
- Explain "why" not just "what"
- Be encouraging and positive
- Use simple, short sentences
- Add emojis for visual clarity

**DON'T**:
- Use IRS jargon
- Assume tax knowledge
- Be condescending
- Over-explain (keep it concise)
- Use fear tactics

**Examples**:

❌ "Enter your qualified education expenses per Section 25A"
✅ "How much did you spend on school this year?"

❌ "Indicate marital status as of December 31"
✅ "Were you married on December 31st?"

❌ "Calculate itemized deductions versus standard deduction"
✅ "Should you list your expenses? (We'll help you decide)"

---

## Implementation Priority

### High Priority (Do First)
1. Step titles and subtitles
2. Field labels (SSN, DOB, etc.)
3. Filing status cards
4. Category names (Step 4a)
5. Button text
6. Tax calculation display

### Medium Priority
7. Help tooltips
8. Error messages
9. Success messages
10. Form explanations

### Low Priority (Polish)
11. Loading messages
12. Empty states
13. Placeholder text
14. Footer text

---

## Testing

### After Changes, Verify

- [ ] A non-tax-expert can understand every label
- [ ] No unexplained acronyms (SSN → Social Security Number)
- [ ] No tax jargon without explanation
- [ ] Positive, encouraging tone throughout
- [ ] Clear calls-to-action
- [ ] Help available for complex terms

---

## Example: Before & After

### Before (Technical)
```
┌─────────────────────────────────────────────┐
│ Step 4a: Deduction Categories               │
│ Select applicable expense categories        │
│                                              │
│ ┌────────────────────────────────────────┐ │
│ │ 🏠 Mortgage Interest & Property Tax    │ │
│ │ IRC Section 163(h) qualified expenses  │ │
│ │ [ ] Select                             │ │
│ └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### After (Layman-Friendly)
```
┌─────────────────────────────────────────────┐
│ Ways to Save Money on Taxes                 │
│ Which did you spend money on? (Pick yours)  │
│                                              │
│ ┌────────────────────────────────────────┐ │
│ │ 🏠 Home Expenses                        │ │
│ │ Mortgage, property tax, home loan      │ │
│ │ [ ] I have these expenses              │ │
│ └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

---

## Ready to Implement

This document maps all technical terms to simple alternatives.

**Next step**: Update `src/web/templates/index.html` with new terminology.

**Estimated time**: 1-2 hours for all changes
