# Changelog - Updated for Tax Year 2025

## Overview
The tax preparation agent has been updated from Tax Year 2024 to **Tax Year 2025** (filing in 2026).

## Key Updates

### Tax Brackets (2025)
All tax brackets have been updated with inflation-adjusted thresholds:

**Single Filers:**
- 10%: $0 to $11,925 (was $0 to $11,600)
- 12%: $11,926 to $48,475 (was $11,601 to $47,150)
- 22%: $48,476 to $103,350 (was $47,151 to $100,525)
- 24%: $103,351 to $197,300 (was $100,526 to $191,950)
- 32%: $197,301 to $250,525 (was $191,951 to $243,725)
- 35%: $250,526 to $626,350 (was $243,726 to $609,350)
- 37%: $626,351+ (was $609,351+)

**Married Filing Jointly:**
- 10%: $0 to $23,850 (was $0 to $23,200)
- 12%: $23,851 to $96,950 (was $23,201 to $94,300)
- 22%: $96,951 to $206,700 (was $94,301 to $201,050)
- 24%: $206,701 to $394,600 (was $201,051 to $383,900)
- 32%: $394,601 to $501,050 (was $383,901 to $487,450)
- 35%: $501,051 to $751,600 (was $487,451 to $731,200)
- 37%: $751,601+ (was $731,201+)

**Head of Household:**
- Updated brackets with 2025 inflation adjustments

**Married Filing Separately:**
- Updated brackets with 2025 inflation adjustments

**Qualifying Widow(er):**
- Same brackets as Married Filing Jointly

### Standard Deductions (2025)
Increased standard deduction amounts:

- **Single:** $15,000 (was $14,600) - increase of $400
- **Married Filing Jointly:** $30,000 (was $29,200) - increase of $800
- **Married Filing Separately:** $15,000 (was $14,600) - increase of $400
- **Head of Household:** $22,500 (was $21,900) - increase of $600
- **Qualifying Widow(er):** $30,000 (was $29,200) - increase of $800

**Additional Standard Deduction for Age/Blindness (2025):**
- Single or Head of Household: $2,000 per condition (was $1,850)
- Married Filing Jointly/Separately/Qualifying Widow: $1,600 per person per condition (was $1,500)

### Child Tax Credit (2025)
- **Credit Amount:** $2,200 per qualifying child (increased from $2,000)
- **Refundable Amount:** Up to $1,800 per child (increased from $1,600)
- Phaseout thresholds remain at $200,000 (single) and $400,000 (married joint)

### Earned Income Tax Credit (EITC)
- EITC amounts and phaseout thresholds updated for 2025 inflation adjustments
- Phaseout thresholds increased approximately 2-3% to account for inflation

## Files Updated

1. **src/calculator/tax_calculator.py**
   - Updated all tax brackets for 2025
   - Updated file header documentation

2. **src/models/tax_return.py**
   - Changed default tax_year from 2024 to 2025

3. **src/models/deductions.py**
   - Updated standard deduction amounts for 2025
   - Updated additional standard deduction for age/blindness

4. **src/models/credits.py**
   - Updated Child Tax Credit to $2,200 per child
   - Updated refundable amount to $1,800
   - Updated EITC phaseout thresholds for 2025

5. **src/agent/tax_agent.py**
   - Updated prompts to reference tax year 2025

6. **src/forms/form_generator.py**
   - Updated form summary headers to show 2025

7. **Documentation Files**
   - README.md
   - USAGE.md
   - PROJECT_SUMMARY.md
   - All updated to reflect 2025 tax year

## Testing

To verify the updates, run:
```bash
python example.py
```

This will show example calculations using the 2025 tax brackets and deductions.

## Important Notes

- All calculations now use 2025 tax law
- Tax brackets are inflation-adjusted
- Standard deductions increased across all filing statuses
- Child Tax Credit increased to $2,200 per child
- Filing deadline for 2025 returns: April 15, 2026
- IRS filing season begins: January 26, 2026

## Next Steps

1. Test the agent with sample data to verify calculations
2. Review IRS final forms when available (currently draft forms)
3. Update any additional schedules or forms as needed
4. Consider adding state tax calculations if needed
