# Universal Report System - Pre-Launch Verification Checklist

## Overview
This checklist covers ALL critical areas that must be verified before the Universal Report System goes live. This system is the primary output seen by end users - it must be flawless.

---

## 🔴 CRITICAL - MUST PASS (Blocking Issues)

### 1. Tax Calculation Accuracy
These are the most important - incorrect tax numbers could cause legal/compliance issues.

| Item | Test | Status |
|------|------|--------|
| Federal tax brackets | Verify 2025 brackets match IRS Publication 17 | ⬜ |
| Effective tax rate | Check: (Total Tax / Gross Income) × 100 | ⬜ |
| Marginal tax rate | Verify correct bracket for taxable income | ⬜ |
| SALT cap | Confirm $10,000 limit enforced | ⬜ |
| 401(k) limits | 2025: $23,500 (under 50), $31,000 (50+) | ⬜ |
| IRA limits | 2025: $7,000 (under 50), $8,000 (50+) | ⬜ |
| HSA limits | 2025: $4,300 (individual), $8,550 (family) | ⬜ |
| Standard deduction | Single: $15,000, MFJ: $30,000, HoH: $22,500 | ⬜ |
| QBI deduction | 20% calculation, income phase-outs | ⬜ |
| Self-employment tax | 15.3% on 92.35% of SE income | ⬜ |
| NIIT threshold | $200K single, $250K MFJ | ⬜ |
| AMT calculations | If applicable, verify correctly | ⬜ |

### 2. Savings Estimates Accuracy
Overstated savings = unhappy clients = legal risk.

| Item | Test | Status |
|------|------|--------|
| Savings formula | Verify: Recommendation savings × marginal rate | ⬜ |
| Conservative estimates | Savings should be achievable, not theoretical max | ⬜ |
| No duplicate counting | Same strategy not counted twice | ⬜ |
| Confidence scoring | 85% default, adjusts based on data completeness | ⬜ |
| Range display | Show low-high range, not single number | ⬜ |

### 3. Data Integrity
Data flows correctly from all sources.

| Item | Test | Status |
|------|------|--------|
| Chatbot session data | All profile fields map correctly | ⬜ |
| Advisory analysis data | Sections extract properly | ⬜ |
| Lead magnet session | Limited data handled gracefully | ⬜ |
| Manual entry form | Form data converts accurately | ⬜ |
| OCR extraction | Document data maps correctly | ⬜ |
| Decimal precision | No rounding errors in calculations | ⬜ |
| Null/empty handling | Missing data doesn't break rendering | ⬜ |
| Negative values | Losses display correctly with minus sign | ⬜ |

### 4. Legal/Compliance
Required disclaimers and language.

| Item | Test | Status |
|------|------|--------|
| "Not Tax Advice" disclaimer | Prominently displayed | ⬜ |
| "Consult Professional" notice | Present and clear | ⬜ |
| Methodology disclosure | How calculations are made | ⬜ |
| IRS reference citations | Accurate and current | ⬜ |
| Confidentiality notice | Present on cover page | ⬜ |
| CPA firm disclaimer | Custom disclaimer if provided | ⬜ |

---

## 🟠 HIGH PRIORITY - Should Pass

### 5. Visualization Accuracy
Charts must show correct data proportions.

| Item | Test | Status |
|------|------|--------|
| **Savings Gauge** | | |
| - Needle position | Points to correct percentage | ⬜ |
| - Green zone width | Matches savings percentage | ⬜ |
| - Dollar labels | Match actual values | ⬜ |
| - Animation works | Needle sweeps on load | ⬜ |
| **Income Pie Chart** | | |
| - Slices sum to 100% | Verify totals | ⬜ |
| - Colors distinct | Easy to differentiate | ⬜ |
| - Legend matches | Labels correspond to slices | ⬜ |
| **Tax Bracket Chart** | | |
| - Bracket widths | Proportional to dollar amounts | ⬜ |
| - Correct bracket highlighted | User's bracket shown | ⬜ |
| - Bracket amounts | Match IRS tables | ⬜ |
| **Deduction Comparison** | | |
| - Bar heights | Proportional to values | ⬜ |
| - "Selected" badge | On chosen deduction type | ⬜ |

### 6. Section Rendering
All 14 sections render correctly.

| Section | Renders | Data Correct | Styling OK | Status |
|---------|---------|--------------|------------|--------|
| Cover Page | ⬜ | ⬜ | ⬜ | ⬜ |
| Executive Summary | ⬜ | ⬜ | ⬜ | ⬜ |
| Savings Gauge | ⬜ | ⬜ | ⬜ | ⬜ |
| Tax Summary | ⬜ | ⬜ | ⬜ | ⬜ |
| Income Analysis | ⬜ | ⬜ | ⬜ | ⬜ |
| Deductions Analysis | ⬜ | ⬜ | ⬜ | ⬜ |
| Tax Brackets | ⬜ | ⬜ | ⬜ | ⬜ |
| Recommendations | ⬜ | ⬜ | ⬜ | ⬜ |
| Action Items | ⬜ | ⬜ | ⬜ | ⬜ |
| Tax Education | ⬜ | ⬜ | ⬜ | ⬜ |
| Risk Assessment | ⬜ | ⬜ | ⬜ | ⬜ |
| Tax Timeline | ⬜ | ⬜ | ⬜ | ⬜ |
| Document Checklist | ⬜ | ⬜ | ⬜ | ⬜ |
| Disclaimers | ⬜ | ⬜ | ⬜ | ⬜ |

### 7. Branding/White-Label
CPA customization works correctly.

| Item | Test | Status |
|------|------|--------|
| Logo display | Correct size and position | ⬜ |
| Logo formats | PNG, JPG, SVG all work | ⬜ |
| Primary color | Applied to headings, accents | ⬜ |
| Accent color | Applied to savings, positive values | ⬜ |
| Firm name | Appears in header | ⬜ |
| Advisor name | Shows with credentials | ⬜ |
| Contact info | Email and phone displayed | ⬜ |
| Custom report title | Overrides default | ⬜ |
| Default branding | Works when no CPA profile | ⬜ |

### 8. Tier Restrictions
Content gating works correctly.

| Item | Test | Status |
|------|------|--------|
| Tier 1 (teaser) | Only summary sections shown | ⬜ |
| Tier 1 blur | Restricted content blurred | ⬜ |
| Tier 1 upgrade CTA | "Upgrade" prompt visible | ⬜ |
| Tier 2 (full) | All main sections visible | ⬜ |
| Tier 3 (complete) | Scenarios, projections included | ⬜ |

---

## 🟡 MEDIUM PRIORITY - Test Thoroughly

### 9. Export Quality

| Item | Test | Status |
|------|------|--------|
| **HTML Export** | | |
| - Standalone opens | Works without server | ⬜ |
| - CSS embedded | Styles in document | ⬜ |
| - Fonts load | Text renders correctly | ⬜ |
| - Images embedded | Base64 or accessible URLs | ⬜ |
| **PDF Export** | | |
| - Generates without error | No crashes | ⬜ |
| - Charts render | SVGs convert properly | ⬜ |
| - Page breaks clean | No cut-off content | ⬜ |
| - File size reasonable | <5MB | ⬜ |
| - WeasyPrint backend | Primary backend works | ⬜ |
| - ReportLab fallback | Backup works if needed | ⬜ |
| **Email Export** | | |
| - Email-safe HTML | Inline styles | ⬜ |
| - Images as attachments | Not broken links | ⬜ |

### 10. API Integration

| Endpoint | Method | Test | Status |
|----------|--------|------|--------|
| `/api/advisor/universal-report` | POST | Generate report | ⬜ |
| `/api/advisor/universal-report/{id}/html` | GET | Get HTML | ⬜ |
| `/api/advisor/universal-report/{id}/pdf` | GET | Get PDF | ⬜ |
| `/lead-magnet/universal-report` | GET | Lead magnet page | ⬜ |
| Error: Session not found | | Returns 404 | ⬜ |
| Error: Insufficient data | | Returns 400 | ⬜ |
| Error: Invalid tier | | Returns 400 | ⬜ |

### 11. Performance

| Item | Target | Test | Status |
|------|--------|------|--------|
| Report generation time | <3 seconds | ⬜ | ⬜ |
| HTML file size | <100KB | ⬜ | ⬜ |
| PDF file size | <5MB | ⬜ | ⬜ |
| Memory usage | No leaks on repeated gen | ⬜ | ⬜ |
| Concurrent generation | 10 simultaneous OK | ⬜ | ⬜ |

---

## 🟢 LOWER PRIORITY - Nice to Have

### 12. Cross-Browser Testing

| Browser | HTML Renders | Charts Work | Print OK | Status |
|---------|--------------|-------------|----------|--------|
| Chrome (latest) | ⬜ | ⬜ | ⬜ | ⬜ |
| Firefox (latest) | ⬜ | ⬜ | ⬜ | ⬜ |
| Safari (latest) | ⬜ | ⬜ | ⬜ | ⬜ |
| Edge (latest) | ⬜ | ⬜ | ⬜ | ⬜ |
| Mobile Safari | ⬜ | ⬜ | N/A | ⬜ |
| Mobile Chrome | ⬜ | ⬜ | N/A | ⬜ |

### 13. Accessibility

| Item | Test | Status |
|------|------|--------|
| Color contrast | WCAG AA (4.5:1 minimum) | ⬜ |
| Alt text on images | All charts have descriptions | ⬜ |
| Heading hierarchy | Proper H1 > H2 > H3 | ⬜ |
| Screen reader | VoiceOver/NVDA compatible | ⬜ |
| Font sizes | Readable without zoom | ⬜ |

### 14. Print Quality

| Item | Test | Status |
|------|------|--------|
| Print preview | Matches screen | ⬜ |
| Page breaks | Clean, no orphans | ⬜ |
| Charts print | Not pixelated | ⬜ |
| Colors print | Legible in B&W | ⬜ |
| Headers/footers | Page numbers work | ⬜ |

---

## Specific Test Scenarios

### Scenario 1: Simple W-2 Employee
```
Filing: Single
Income: $75,000 W-2
Deductions: Standard
Expected: ~$8,500 federal tax, 11.3% effective rate
```

### Scenario 2: Self-Employed Consultant
```
Filing: Single
Income: $150,000 business income
Expected: SE tax shown, QBI deduction mentioned
```

### Scenario 3: High-Income Married Couple
```
Filing: Married Joint
Income: $500,000 combined
Investments: $50,000 capital gains
Expected: NIIT mentioned, phase-outs noted
```

### Scenario 4: Complex Multiple Sources
```
Filing: Head of Household
W-2: $80,000
Business: $40,000
Rental: -$20,000 (loss)
Investments: $15,000
Expected: All income types shown, PAL rules mentioned
```

### Scenario 5: Minimal Data (Lead Magnet)
```
Filing: Single
Income: $100,000 (only)
Expected: Teaser report, savings estimate shown
```

### Scenario 6: Edge Case - Very High Income
```
Filing: Married Joint
Income: $5,000,000
Expected: Handles large numbers, no overflow
```

### Scenario 7: Edge Case - Zero/Negative
```
Filing: Single
Income: $0 or losses only
Expected: Doesn't crash, shows meaningful message
```

---

## Pre-Launch Sign-Off

### Required Approvals

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Tax Accuracy Review (CPA) | | | |
| Legal/Compliance Review | | | |
| UX/Design Review | | | |
| QA Testing Complete | | | |
| Product Owner Sign-off | | | |

### Final Checks

- [ ] All CRITICAL items pass
- [ ] All HIGH PRIORITY items pass
- [ ] Unit tests pass (41/41)
- [ ] Integration tests pass
- [ ] Manual testing complete
- [ ] Performance benchmarks met
- [ ] Error logging configured
- [ ] Monitoring/alerts in place
- [ ] Rollback plan documented
- [ ] Support documentation ready

---

## Known Limitations (Document These)

1. **PDF Generation**: Requires WeasyPrint or ReportLab installed
2. **Logo Handling**: External URLs must be accessible; base64 preferred
3. **Tax Year**: Currently hardcoded to 2025; update annually
4. **State Taxes**: Federal only; state calculations not included
5. **AMT**: Alternative Minimum Tax not fully calculated
6. **Estimated Payments**: Suggested but not precisely calculated

---

## Emergency Contacts

| Issue | Contact | Method |
|-------|---------|--------|
| Tax Accuracy Questions | [CPA Name] | [Email] |
| System Issues | [Dev Lead] | [Phone] |
| Legal Concerns | [Legal Contact] | [Email] |

---

**Last Updated**: 2025-01-27
**Version**: 1.0
**Next Review**: Before any major release
