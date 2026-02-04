# Pre-Launch Checklist: Universal Report System

## CRITICAL - Must Pass Before Go-Live

This checklist covers the "brain, heart, backbone" of the portal - the report generation and display system that end users will see.

---

## 1. TAX CALCULATION ACCURACY (HIGHEST PRIORITY)

### 1.1 Tax Brackets Verification
- [ ] 2025 Single tax brackets correct (10%, 12%, 22%, 24%, 32%, 35%, 37%)
- [ ] 2025 Married Filing Jointly brackets correct
- [ ] 2025 Married Filing Separately brackets correct
- [ ] 2025 Head of Household brackets correct
- [ ] Bracket thresholds match IRS Publication 17

### 1.2 Deduction Limits
- [ ] Standard deduction 2025: Single = $14,600
- [ ] Standard deduction 2025: MFJ = $29,200
- [ ] Standard deduction 2025: HOH = $21,900
- [ ] SALT cap enforced at $10,000
- [ ] Mortgage interest limit correct ($750K for new mortgages)

### 1.3 Contribution Limits
- [ ] 401(k) limit 2025: $23,500 (under 50)
- [ ] 401(k) catch-up 2025: $7,500 (50+)
- [ ] IRA limit 2025: $7,000 (under 50)
- [ ] IRA catch-up 2025: $1,000 (50+)
- [ ] HSA Family limit 2025: $8,550
- [ ] HSA Individual limit 2025: $4,300

### 1.4 Self-Employment Taxes
- [ ] SE tax rate: 15.3% (12.4% SS + 2.9% Medicare)
- [ ] Social Security wage base 2025: $176,100
- [ ] Additional Medicare tax 0.9% above $200K single / $250K MFJ
- [ ] SE tax deduction (50% of SE tax) applied correctly

### 1.5 Special Tax Calculations
- [ ] QBI deduction (20%) calculated correctly
- [ ] QBI phase-out thresholds correct
- [ ] NIIT (3.8%) threshold: $200K single / $250K MFJ
- [ ] AMT exemption amounts correct
- [ ] Capital gains rates (0%, 15%, 20%) at correct thresholds

---

## 2. SAVINGS ESTIMATES VALIDATION

### 2.1 Savings Logic
- [ ] Potential savings NEVER exceeds current tax liability
- [ ] No duplicate counting of savings across strategies
- [ ] Savings confidence score between 0-100%
- [ ] Conservative estimates (not overpromising)

### 2.2 Strategy-Specific Validation
- [ ] Retirement contribution savings calculated correctly
- [ ] HSA savings accurate
- [ ] Entity restructuring savings realistic
- [ ] Depreciation strategies valid
- [ ] Timing strategies properly estimated

---

## 3. DATA INTEGRITY

### 3.1 Input Handling
- [ ] Decimal precision maintained (no rounding errors)
- [ ] Null/undefined values handled gracefully
- [ ] Negative values displayed correctly (refunds, losses)
- [ ] Very high income ($10M+) doesn't break calculations
- [ ] Zero income handled without division errors

### 3.2 Special Characters & Security
- [ ] XSS prevention: `<script>` tags escaped in all outputs
- [ ] Special characters in names handled: O'Brien, Smith & Co.
- [ ] Unicode characters supported: émigré, naïve
- [ ] SQL injection prevented in all database queries
- [ ] Session IDs validated and sanitized

### 3.3 Filing Status Mapping
- [ ] "single" maps correctly
- [ ] "married_filing_jointly" / "married_joint" normalized
- [ ] "married_filing_separately" / "married_separate" normalized
- [ ] "head_of_household" maps correctly
- [ ] "qualifying_widow" handled if applicable

---

## 4. VISUALIZATION ACCURACY

### 4.1 Savings Gauge
- [ ] Percentage calculation: (savings / current_tax) * 100
- [ ] Needle position matches percentage
- [ ] Dollar amounts displayed correctly
- [ ] Gauge renders on all browsers (Chrome, Firefox, Safari, Edge)
- [ ] Mobile rendering correct

### 4.2 Income Pie Chart
- [ ] All categories sum to 100%
- [ ] Category labels match data
- [ ] Colors distinguishable
- [ ] Legend readable
- [ ] Empty categories hidden (not 0% slices)

### 4.3 Tax Bracket Chart
- [ ] Bracket amounts match actual tax calculation
- [ ] Colors gradient from green (low) to red (high)
- [ ] Tax amounts in each bracket accurate
- [ ] Filing status reflected in brackets

### 4.4 Comparison Charts
- [ ] Current vs Optimized values accurate
- [ ] Savings annotation correct
- [ ] Bar heights proportional

---

## 5. PDF GENERATION

### 5.1 Content Accuracy
- [ ] All sections render without errors
- [ ] Data matches HTML report exactly
- [ ] No missing sections
- [ ] Page breaks at logical points

### 5.2 Branding
- [ ] Logo displays correctly (if provided)
- [ ] Logo doesn't display if not provided
- [ ] Primary color applied to headings
- [ ] Firm name in header/footer
- [ ] Advisor credentials displayed
- [ ] Contact info in footer

### 5.3 Visualizations in PDF
- [ ] Savings gauge embeds correctly
- [ ] Charts render at correct resolution
- [ ] No blank spaces where charts should be
- [ ] Charts readable when printed

### 5.4 Table of Contents
- [ ] All sections listed
- [ ] Section titles match content
- [ ] TOC appears after cover page

### 5.5 PDF File Integrity
- [ ] PDF opens in all readers (Adobe, Preview, Chrome)
- [ ] File size reasonable (<5MB for typical report)
- [ ] No corruption on download
- [ ] Filename sanitized (no special characters)

---

## 6. API ENDPOINTS

### 6.1 Report Generation Endpoints
- [ ] `GET /api/advisor/report/{session_id}` returns HTML
- [ ] `GET /api/advisor/report/{session_id}/pdf` returns PDF
- [ ] `GET /api/advisor/universal-report/{session_id}` returns HTML
- [ ] `GET /api/advisor/universal-report/{session_id}/pdf` returns PDF

### 6.2 Error Handling
- [ ] 404 for invalid session_id
- [ ] 400 for insufficient data
- [ ] 503 if PDF service unavailable
- [ ] 500 errors logged with details
- [ ] User-friendly error messages (no stack traces exposed)

### 6.3 Query Parameters
- [ ] `include_charts=true/false` works
- [ ] `include_toc=true/false` works
- [ ] `tier=1/2/3` applies correct restrictions
- [ ] `cpa=profile_id` applies branding
- [ ] `watermark=DRAFT` adds watermark

---

## 7. FRONTEND / USER EXPERIENCE

### 7.1 Chatbot Integration
- [ ] Profile data flows to report correctly
- [ ] "View Report" button works
- [ ] "Download PDF" button works
- [ ] Report updates when profile changes

### 7.2 Profile Editor
- [ ] Edit mode toggles correctly
- [ ] Changes save to session
- [ ] Cancel reverts changes
- [ ] Validation on numeric fields
- [ ] Required fields enforced

### 7.3 Tax Term Explanations
- [ ] QBI tooltip/modal shows definition
- [ ] NIIT explanation accurate
- [ ] AMT explanation accurate
- [ ] All linked terms clickable
- [ ] Modal closes properly

### 7.4 PDF Preview Modal
- [ ] Preview loads without downloading
- [ ] Download button works from preview
- [ ] Close button works
- [ ] Escape key closes modal

### 7.5 Comparison Views
- [ ] Current vs Optimized displays correctly
- [ ] Tier comparison table accurate
- [ ] Free vs Paid features clearly marked

---

## 8. MOBILE RESPONSIVENESS

### 8.1 Breakpoints
- [ ] Desktop (>1024px) - full layout
- [ ] Tablet (768-1024px) - adjusted layout
- [ ] Mobile (<768px) - stacked layout
- [ ] Small mobile (<480px) - compact layout

### 8.2 Mobile-Specific Features
- [ ] Side panel collapsible
- [ ] Drag handle works for panel
- [ ] Touch targets large enough (44px min)
- [ ] Charts readable on mobile
- [ ] PDF download works on mobile

### 8.3 Cross-Browser Testing
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] iOS Safari
- [ ] Android Chrome

---

## 9. LEGAL COMPLIANCE

### 9.1 Disclaimers (CRITICAL)
- [ ] "NOT TAX ADVICE" disclaimer prominent
- [ ] "CONSULT A PROFESSIONAL" notice present
- [ ] Disclaimers appear in HTML report
- [ ] Disclaimers appear in PDF report
- [ ] Disclaimers not hidden or minimized

### 9.2 Required Notices
- [ ] "For informational purposes only"
- [ ] "Estimates may not reflect actual tax situation"
- [ ] "Do not rely solely on this document"
- [ ] IRS references where applicable

---

## 10. PERFORMANCE

### 10.1 Response Times
- [ ] HTML report generates in <3 seconds
- [ ] PDF report generates in <10 seconds
- [ ] Page load time <2 seconds
- [ ] No timeout errors under normal load

### 10.2 Resource Usage
- [ ] Memory usage reasonable during PDF generation
- [ ] No memory leaks on repeated requests
- [ ] Temp files cleaned up after PDF generation

---

## 11. SESSION & DATA PERSISTENCE

### 11.1 Session Management
- [ ] Session data persists across page refreshes
- [ ] Session data saved to database
- [ ] Session retrieval from database works
- [ ] Session expiration handled gracefully

### 11.2 Data Flow
- [ ] Chatbot → Session storage works
- [ ] Session → Report generation works
- [ ] Session → PDF generation works
- [ ] Profile updates reflect in reports immediately

---

## 12. EDGE CASES TO TEST

### 12.1 Income Scenarios
- [ ] $0 income (unemployed)
- [ ] $25,000 (low income)
- [ ] $100,000 (middle income)
- [ ] $500,000 (high income)
- [ ] $5,000,000+ (very high income)
- [ ] Negative AGI (business losses)

### 12.2 Filing Status Scenarios
- [ ] Single, no dependents
- [ ] Single, with dependents
- [ ] Married, both working
- [ ] Married, one income
- [ ] Head of household
- [ ] Self-employed

### 12.3 Special Situations
- [ ] Multiple income sources (W-2 + 1099 + investments)
- [ ] Rental property income/losses
- [ ] Capital gains + losses
- [ ] Retirement distributions
- [ ] Foreign income (if applicable)

---

## 13. INTEGRATION TESTING

### 13.1 Full User Flow Tests
- [ ] New user → Chatbot → Report → PDF (complete flow)
- [ ] Returning user → Load session → View report
- [ ] CPA branding flow → Branded report → Branded PDF
- [ ] Lead magnet flow → Tier 1 report → Upgrade prompt

### 13.2 Error Recovery
- [ ] Network error during report generation → Retry works
- [ ] Browser refresh during generation → No duplicate
- [ ] Incomplete data → Clear error message

---

## 14. AUTOMATED TEST VERIFICATION

Run these test suites before go-live:

```bash
# Universal Report Tests (73 tests)
pytest tests/test_universal_report.py tests/test_universal_report_verification.py -v

# Specific test categories
pytest -k "tax_bracket" -v        # Tax bracket accuracy
pytest -k "savings" -v            # Savings calculations
pytest -k "xss" -v                # Security tests
pytest -k "branding" -v           # Branding tests
pytest -k "visualization" -v     # Chart tests
```

---

## 15. MANUAL TESTING CHECKLIST

### 15.1 Smoke Test (Do First)
1. [ ] Start fresh session in chatbot
2. [ ] Enter sample data (MFJ, $150K income, self-employed)
3. [ ] Complete conversation to get analysis
4. [ ] Click "View Report" - verify HTML renders
5. [ ] Click "Download PDF" - verify PDF downloads
6. [ ] Open PDF - verify content matches HTML
7. [ ] Check all visualizations render

### 15.2 CPA Branding Test
1. [ ] Generate report with branding parameters:
   ```
   /api/advisor/report/{session}/pdf?firm_name=Test%20CPA&advisor_name=John%20Smith&contact_email=john@test.com
   ```
2. [ ] Verify firm name in header
3. [ ] Verify advisor name on cover
4. [ ] Verify contact info in footer

### 15.3 Mobile Test
1. [ ] Open chatbot on mobile device
2. [ ] Complete a session
3. [ ] View report on mobile
4. [ ] Download PDF on mobile
5. [ ] Verify all elements readable

---

## SIGN-OFF

| Area | Tested By | Date | Status |
|------|-----------|------|--------|
| Tax Calculations | | | |
| Savings Estimates | | | |
| Data Integrity | | | |
| Visualizations | | | |
| PDF Generation | | | |
| API Endpoints | | | |
| Frontend UX | | | |
| Mobile | | | |
| Legal Compliance | | | |
| Performance | | | |
| Integration | | | |

**Final Approval:**
- [ ] All critical items passed
- [ ] No P0/P1 bugs outstanding
- [ ] Legal disclaimers verified by counsel
- [ ] Ready for production deployment

---

## QUICK REFERENCE: Critical Files

| File | Purpose |
|------|---------|
| `src/universal_report/template_engine.py` | Main report orchestrator |
| `src/universal_report/data_collector.py` | Data normalization |
| `src/universal_report/visualizations/` | Charts and gauges |
| `src/export/advisory_pdf_exporter.py` | PDF generation |
| `src/export/pdf_visualizations.py` | PDF chart generation |
| `src/web/intelligent_advisor_api.py` | API endpoints |
| `src/web/static/js/chatbot-ux-enhancements.js` | Frontend components |
| `src/web/static/css/chatbot-ux-enhancements.css` | Styling |
