# 🧪 Testing Guide: Advisory Reports
## End-to-End Verification (5-10 minutes)

**Status**: Server running ✅ (Process 49671)
**URL**: http://127.0.0.1:8000

---

## Test Scenario 1: Quick Test via Main Flow (Recommended)

### Step 1: Start a Tax Return Session
1. Open browser: http://127.0.0.1:8000/file
2. You should see the conversational AI tax advisor interface
3. Start by providing your name when prompted
4. Provide email address (this qualifies you as a lead)

### Step 2: Complete Basic Tax Information
Provide the following information when asked:
- **Name**: Test User
- **Email**: test@example.com
- **Filing Status**: Married Filing Jointly
- **Income**: $120,000
- **Dependents**: 2 children
- **State**: California

You can either:
- Type responses naturally, OR
- Upload a sample W-2 document if available

### Step 3: Get to Results Page
After providing basic information, the AI will:
- Calculate your tax liability
- Show estimated federal tax
- Display results on Step 6 (Results page)

### Step 4: Generate Advisory Report
**THIS IS THE KEY TEST**

On the results page, you should see:
```
📊 Generate Professional Report
```

Click this button.

**Expected Result**:
- New browser tab opens
- Shows "Generating advisory report..." message
- URL will be: http://127.0.0.1:8000/advisory-report-preview?report_id=rpt_xxxxx
- Page displays report preview with sections:
  * Executive Summary
  * Tax Situation Analysis
  * Optimization Recommendations
  * Multi-Year Projections
  * Action Items

### Step 5: Download PDF
On the report preview page:
1. Wait 5-10 seconds for PDF generation to complete
2. Button will change from "⏳ Generating PDF..." to "📄 Download PDF Report"
3. Click "Download PDF Report"

**Expected Result**:
- PDF file downloads (20-40 pages)
- Professional formatting
- All sections included
- Your data populated correctly

### Step 6: Test Report History
Back on the results page:
1. Click "📋 View Report History"

**Expected Result**:
- Modal opens showing all generated reports
- See your just-generated report listed
- Can click to re-open it

---

## Test Scenario 2: Quick API Verification (For Developers)

Since direct API testing requires CSRF token, we can verify endpoints are mounted:

### Check OpenAPI Documentation
1. Open browser: http://127.0.0.1:8000/docs
2. Look for "Advisory Reports" section
3. Should see 7 endpoints:
   - POST `/api/v1/advisory-reports/generate`
   - GET `/api/v1/advisory-reports/{report_id}`
   - GET `/api/v1/advisory-reports/{report_id}/pdf`
   - GET `/api/v1/advisory-reports/{report_id}/data`
   - GET `/api/v1/advisory-reports/session/{session_id}/reports`
   - DELETE `/api/v1/advisory-reports/{report_id}`
   - POST `/api/v1/advisory-reports/test/generate-sample`

**Expected Result**: All 7 endpoints visible in Swagger UI ✅

---

## Test Scenario 3: Verify Preview Page Route

### Direct Access Test
1. Open browser: http://127.0.0.1:8000/advisory-report-preview
2. Without a report_id parameter, should see error or prompt

**Expected Result**: Page loads (confirms route is mounted) ✅

---

## Expected Behaviors

### ✅ SUCCESS Indicators
- [ ] Button "Generate Professional Report" visible on results page
- [ ] Clicking button opens new tab
- [ ] Report preview page loads
- [ ] Report shows your data (name, income, filing status)
- [ ] Sections display: Summary, Analysis, Recommendations, Projections
- [ ] PDF status updates from "Generating..." to "Download"
- [ ] PDF downloads successfully (20-40 pages)
- [ ] Report history shows generated report
- [ ] Can re-open report from history

### ❌ FAILURE Indicators (Need Investigation)
- Button not visible → Frontend integration issue
- Button click does nothing → JavaScript error (check browser console)
- New tab doesn't open → Check for popup blockers
- Preview page shows error → Backend API issue
- PDF never completes → Check server logs
- PDF empty or incomplete → Data population issue
- History modal empty → Database query issue

---

## Troubleshooting

### Issue: Button Not Visible
**Check**:
1. Are you on Step 6 (Results page)?
2. Open browser console (F12) - any JavaScript errors?
3. Check if button exists in HTML:
   - Inspect page (right-click → Inspect)
   - Search for "Generate Professional Report"

**Fix**: Button should be at line 11498 in index.html

---

### Issue: Button Click Does Nothing
**Check**:
1. Open browser console (F12) before clicking
2. Look for JavaScript errors when clicking
3. Check network tab - is API call being made?

**Fix**: Function `generateAdvisoryReport()` should exist at line 16095

---

### Issue: API Returns Error
**Check Server Logs**:
```bash
# Check recent server logs
tail -100 /tmp/server.log | grep -i advisory
```

**Common Issues**:
- Session not found → Need to complete tax return first
- Database error → Check data/tax_returns.db exists
- Import error → Missing dependencies

---

### Issue: PDF Generation Fails
**Check**:
1. Server has write permissions to temp directory
2. ReportLab library installed: `pip list | grep -i reportlab`
3. All data fields populated correctly

**Server Logs**:
```bash
# Watch logs in real-time
tail -f /tmp/server.log
```

---

## Verification Checklist

After testing, verify:

- [x] ✅ Server running (Process 49671)
- [ ] ✅ Advisory API endpoints in /docs
- [ ] ✅ Generate button visible on results page
- [ ] ✅ Button click opens new tab
- [ ] ✅ Report preview displays
- [ ] ✅ Report shows correct data
- [ ] ✅ All sections present
- [ ] ✅ PDF generates (5-10 seconds)
- [ ] ✅ PDF downloads successfully
- [ ] ✅ PDF contains 20-40 pages
- [ ] ✅ Report history works
- [ ] ✅ Can re-open from history

---

## Next Steps After Testing

### If All Tests Pass ✅
**Congratulations!** Advisory reports are fully operational.

**Next Actions**:
1. ✅ Mark advisory reports as production-ready
2. 📖 Review masterplan: `MASTER_IMPLEMENTATION_PLAN_5MIN_1000_SAVINGS.md`
3. 🎯 Decide on next integration: Quick wins or 5-minute platform
4. 🚀 Start implementation

---

### If Tests Fail ❌
**Don't worry!** We can debug together.

**Share with me**:
1. Which test failed (step number)
2. Any error messages (browser console, server logs)
3. Screenshots if helpful
4. I'll provide specific fixes

---

## Test Results Template

After testing, report back:

```
✅ TEST RESULTS:

Server Status: Running ✅
API Endpoints: Visible ✅ / Not visible ❌
Generate Button: Visible ✅ / Not visible ❌
Button Click: Works ✅ / Error ❌
Preview Page: Loads ✅ / Error ❌
Report Data: Correct ✅ / Missing fields ❌
PDF Generation: Success ✅ / Failed ❌
PDF Download: Works ✅ / Failed ❌
PDF Content: Complete ✅ / Incomplete ❌
Report History: Works ✅ / Empty ❌

Overall Status: PASS ✅ / FAIL ❌

Notes: (any observations or issues)
```

---

## Estimated Testing Time

- **Quick Path** (just verify it works): 5 minutes
- **Thorough Path** (test all features): 10-15 minutes
- **With PDF Review** (read generated report): 20 minutes

**Recommended**: Quick path first (5 min), then decide if you want thorough testing.

---

## Ready to Test?

**Start here**: http://127.0.0.1:8000/file

**First action**: Provide name and email to start tax return

**Goal**: Click "Generate Professional Report" button and see it work

**Expected time**: 5-10 minutes

---

**Good luck! Let me know the results.** 🧪
