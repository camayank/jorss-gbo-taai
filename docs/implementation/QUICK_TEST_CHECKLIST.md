# Quick Test Checklist - Sprint 1 Issues

**Quick reference for testing all 5 Sprint 1 issues**

## Setup
```bash
cd /Users/rakeshanita/Jorss-Gbo
pip3 install -r requirements.txt
uvicorn src.web.app:app --reload --port 8000
```
**URL**: http://localhost:8000/file

---

## ✅ Issue #1: Entry Points (4 tests)

- [ ] `http://localhost:8000/` loads successfully
- [ ] `http://localhost:8000/file` loads successfully
- [ ] `http://localhost:8000/smart-tax` redirects to `/file?mode=smart`
- [ ] `http://localhost:8000/client` redirects to `/file`

**Pass Criteria**: All 4 URLs work without 404 errors

---

## ✅ Issue #2: Header Branding (3 tests)

- [ ] Logo shows firm initial badge (not "$")
- [ ] Company name + credentials displayed
- [ ] "All changes saved" shows (NO "Start Over" button)
- [ ] Header is mobile responsive

**Pass Criteria**: Professional header, no "Start Over" button

---

## ✅ Issue #3: Trust Badges (5 tests)

**Default badges** (4 visible):
- [ ] Security claim badge
- [ ] 256-bit Encryption badge
- [ ] IRS Certified badge
- [ ] GDPR Compliant badge

**Tooltips**:
- [ ] Hover over each badge → tooltip appears
- [ ] Tooltips have black bg, white text, arrow
- [ ] Tooltips fade in/out smoothly
- [ ] Mobile: tooltips hidden on touch devices

**Pass Criteria**: 4 badges with working tooltips on desktop

---

## ✅ Issue #4: Smart Filtering (7 tests)

**Step 4a: Category Selection**:
- [ ] Shows 8 category cards + "None" option
- [ ] Can select multiple categories
- [ ] "None" unchecks all others
- [ ] Continue with "None" → skips to Step 5

**Step 4b: Filtered Questions**:
- [ ] Only selected categories visible
- [ ] Unselected categories hidden
- [ ] State Taxes + Other always visible
- [ ] ~30-50 questions shown (vs 145 unfiltered)

**Pass Criteria**: Questions filtered based on selection, 70% reduction

---

## ✅ Issue #5: Flatten Step 1 (10 tests)

**Structure**:
- [ ] Single scrollable form (NO substeps)
- [ ] NO progress indicators (1/4, 2/4, etc.)
- [ ] ONE "Continue" button at bottom

**Sections** (8 total):
- [ ] Personal Information (always visible)
- [ ] Filing Status (always visible)
- [ ] Widowed Details (conditional)
- [ ] Spouse Information (conditional)
- [ ] Dependents (always visible)
- [ ] Head of Household (conditional)
- [ ] Additional Details (always visible)
- [ ] Direct Deposit (always visible)

**Conditional Logic**:
- [ ] Select "Married" → Spouse section appears
- [ ] Select "Widowed" → Widowed section appears
- [ ] Select "Yes, dependents" → Dependent form appears
- [ ] Select "Single + dependents" → HOH section appears

**Performance**:
- [ ] Complete Step 1 in 5-7 minutes (vs 8-10 min)
- [ ] Total clicks: 1 (vs 6-7 clicks)

**Pass Criteria**: 1 click to complete Step 1, conditional sections work

---

## 🧪 Cross-Cutting Tests

- [ ] No console errors (F12 → Console)
- [ ] No 404/500 errors (F12 → Network)
- [ ] Mobile responsive (iPhone SE 375px)
- [ ] Data persists when navigating back
- [ ] Tab navigation works (accessibility)

---

## 📊 Test Results

| Issue | Status | Notes |
|-------|--------|-------|
| #1: Entry Points | ⬜ PASS / ⬜ FAIL | |
| #2: Header | ⬜ PASS / ⬜ FAIL | |
| #3: Trust Badges | ⬜ PASS / ⬜ FAIL | |
| #4: Smart Filter | ⬜ PASS / ⬜ FAIL | |
| #5: Flatten Step 1 | ⬜ PASS / ⬜ FAIL | |
| Cross-Cutting | ⬜ PASS / ⬜ FAIL | |

**Overall Status**: ⬜ APPROVED / ⬜ NEEDS FIXES

**Critical Issues Found**: _____________________

**Tested By**: _______________ **Date**: _______________

---

## 🚀 After Testing

**If all tests pass**:
```bash
# Commit changes
git add .
git commit -m "Sprint 1 complete: All 5 critical issues implemented and tested"
git tag sprint-1-complete

# Update progress tracker
# Mark issues as "User Approved" in PROGRESS_TRACKER.md
```

**If issues found**:
1. Document in COMPREHENSIVE_MANUAL_TESTING_GUIDE.md
2. Report to developer
3. Re-test after fixes

---

**Detailed Test Instructions**: See `COMPREHENSIVE_MANUAL_TESTING_GUIDE.md`
**Estimated Time**: 30-45 minutes for quick test, 2-3 hours for thorough test
