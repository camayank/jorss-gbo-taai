# Quick Test Guide - Advisory Report System

**Total Test Time**: ~5 minutes

---

## 🚀 Quick Start

### 1. Start the Server (30 seconds)

```bash
cd /Users/rakeshanita/Jorss-Gbo
python run.py
```

**Expected**: Server starts without errors

---

## ✅ Test Sequence

### Test 1: Verify API Endpoints (30 seconds)

**Action**: Open browser to `http://localhost:8000/docs`

**Expected**:
- Swagger UI loads
- Scroll to find "Advisory Reports" section
- Should see 7 endpoints:
  - POST `/api/v1/advisory-reports/generate`
  - GET `/api/v1/advisory-reports/{report_id}`
  - GET `/api/v1/advisory-reports/{report_id}/pdf`
  - GET `/api/v1/advisory-reports/{report_id}/data`
  - GET `/api/v1/advisory-reports/session/{session_id}/reports`
  - DELETE `/api/v1/advisory-reports/{report_id}`
  - POST `/api/v1/advisory-reports/test/generate-sample`

**Status**: ✅ PASS / ❌ FAIL

---

### Test 2: Generate Test Report via API (1 minute)

**Action**: In Swagger UI `/docs`:
1. Find POST `/api/v1/advisory-reports/test/generate-sample`
2. Click "Try it out"
3. Click "Execute"

**Expected**:
- Response code: 200
- Response body contains:
  ```json
  {
    "report_id": "...",
    "status": "completed",
    "message": "Sample report generated successfully"
  }
  ```

**Copy the `report_id`** for next test

**Status**: ✅ PASS / ❌ FAIL

---

### Test 3: View Report Preview (30 seconds)

**Action**: Open new tab to:
```
http://localhost:8000/advisory-report-preview?report_id=YOUR_REPORT_ID
```
(Replace YOUR_REPORT_ID with the one from Test 2)

**Expected**:
- Report preview loads
- Shows metrics: Tax Liability, Potential Savings, Confidence
- "Download PDF Report" button appears (may say "Generating PDF..." initially)
- After 5-10 seconds, button changes to "Download PDF Report"
- Savings breakdown with colorful bars appears

**Status**: ✅ PASS / ❌ FAIL

---

### Test 4: Download PDF (30 seconds)

**Action**: Click "Download PDF Report" button

**Expected**:
- PDF downloads automatically
- Open PDF - should show professional tax advisory report
- Check for: Header, metrics, recommendations, charts

**Status**: ✅ PASS / ❌ FAIL

---

### Test 5: Complete Tax Return & Generate Report (2 minutes)

**Action**:
1. Go to `http://localhost:8000/file`
2. Fill in basic information:
   - Name: John Doe
   - Filing Status: Single
   - Income: $75,000
   - Deductions: $12,000
3. Click through steps to Step 6 (Review)

**Expected**:
- At Step 6, see new buttons:
  - "📊 Generate Professional Report"
  - "📋 View Report History"

**Status**: ✅ PASS / ❌ FAIL

---

### Test 6: Generate Real Report (1 minute)

**Action**: Click "📊 Generate Professional Report"

**Expected**:
- Button changes to "⏳ Generating Report..."
- Green notification appears: "Report generated successfully!"
- New tab opens with report preview
- Report shows YOUR data (John Doe, $75,000 income)
- PDF button updates when ready

**Status**: ✅ PASS / ❌ FAIL

---

### Test 7: View Report History (30 seconds)

**Action**:
1. Go back to Step 6 tab
2. Click "📋 View Report History"

**Expected**:
- Modal overlay appears
- Shows "Your Advisory Reports" header
- Lists at least 1 report (the one you just generated)
- Shows metrics: Tax Liability, Potential Savings, Recommendations
- Shows date generated

**Status**: ✅ PASS / ❌ FAIL

---

### Test 8: Open from History (30 seconds)

**Action**: Click on a report in the history modal

**Expected**:
- New tab opens
- Shows the same report preview
- All data matches

**Status**: ✅ PASS / ❌ FAIL

---

## 🎨 Visual Checks

### Button Styling
- ✅ Blue gradient button for "Generate Report"
- ✅ White text, rounded corners
- ✅ Hover effect (lifts up slightly)
- ✅ Disabled state when generating (grayed out)

### Modal Styling
- ✅ Dark overlay with blur
- ✅ White modal centered on screen
- ✅ Close button (×) in top-right
- ✅ Click outside to close

### Notifications
- ✅ Slide in from right
- ✅ Green for success, red for error
- ✅ Auto-dismiss after 3 seconds
- ✅ Smooth slide out animation

### Savings Visualization
- ✅ Horizontal bars with green gradient
- ✅ Percentage labels on bars
- ✅ Dollar amounts aligned right
- ✅ Smooth width animation

---

## 📱 Mobile Test (Optional)

**Action**:
1. Open browser dev tools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Select iPhone or Android
4. Test all flows

**Expected**:
- Buttons stack vertically
- Modal is full-width
- Text is readable
- Touch targets are large enough

**Status**: ✅ PASS / ❌ FAIL

---

## 🐛 Common Issues & Fixes

### Issue: Endpoints not showing in /docs
**Fix**:
```bash
# Check if advisory_api.py exists
ls src/web/advisory_api.py
# Restart server
python run.py
```

### Issue: "Generate Report" button not appearing
**Fix**:
- Complete all steps through Step 6
- Check browser console for errors (F12)
- Verify you're on Step 6 (Review page)

### Issue: PDF button stays "Generating..."
**Fix**:
- Wait up to 30 seconds
- Check browser console for polling errors
- Verify report ID is correct

### Issue: Report history is empty
**Fix**:
- Generate at least one report first
- Check you're using same session
- Verify sessionId in localStorage (F12 → Application → Local Storage)

### Issue: Modal won't open
**Fix**:
- Check browser console for JavaScript errors
- Verify modal HTML is in page (F12 → Elements → search for "reportHistoryModal")
- Try hard refresh (Ctrl+Shift+R)

---

## 🎯 Success Criteria

All tests should PASS ✅

If any test fails:
1. Check browser console (F12) for errors
2. Check server logs for Python errors
3. Verify file paths are correct
4. Ensure all dependencies installed
5. Try hard refresh (Ctrl+Shift+R)

---

## 📊 Performance Benchmarks

- **Report Generation**: 2-5 seconds
- **PDF Creation**: 5-30 seconds
- **Preview Load**: < 1 second
- **History Load**: < 1 second
- **Polling Interval**: 1 second

---

## 🔧 Debug Commands

```bash
# Check if all files exist
ls src/web/advisory_api.py
ls src/advisory/report_generator.py
ls src/export/advisory_pdf_exporter.py
ls src/web/templates/advisory_report_preview.html

# Test Python syntax
python3 -m py_compile src/web/app.py
python3 -m py_compile src/web/advisory_api.py

# Check server logs
tail -f server.log  # if logging to file

# Test API directly
curl -X POST http://localhost:8000/api/v1/advisory-reports/test/generate-sample
```

---

## ✅ Test Complete!

If all 8 tests pass, the integration is successful! 🎉

**Next Steps**:
1. Show to stakeholders
2. Get user feedback
3. Deploy to staging
4. Deploy to production

---

**Questions?** Check `ADVISORY_REPORT_INTEGRATION_COMPLETE.md` for full documentation.
