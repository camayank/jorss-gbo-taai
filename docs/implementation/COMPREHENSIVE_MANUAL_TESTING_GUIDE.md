# Comprehensive Manual Testing Guide - Sprint 1 Issues

**Date**: 2026-01-21
**Sprint**: Sprint 1 (All 5 Critical Issues)
**Status**: Ready for Manual Testing
**Tester**: User (Rakesh Anita)

---

## Prerequisites

### 1. Environment Setup

**Install Dependencies:**
```bash
cd /Users/rakeshanita/Jorss-Gbo
pip3 install -r requirements.txt
```

**Check Environment Variables (Optional):**
```bash
# Check if .env file exists
ls -la .env

# If not, create one with defaults (optional)
cp .env.example .env 2>/dev/null || echo "No .env.example found"
```

### 2. Start Development Server

**Option A: Using uvicorn directly**
```bash
uvicorn src.web.app:app --reload --port 8000
```

**Option B: Using python module**
```bash
python3 -m uvicorn src.web.app:app --reload --port 8000
```

**Option C: Direct python execution**
```bash
python3 src/web/app.py
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Test Server is Running:**
```bash
curl http://localhost:8000/
# Should return HTML (not 404 or error)
```

---

## Screen-by-Screen Testing

---

## TEST 1: Issue #1 - Entry Points (Single Entry Point)

**Objective**: Verify all entry points redirect to `/file` correctly

### Test 1.1: Root Path (/)
1. **Navigate to**: `http://localhost:8000/`
2. **Expected**: Page loads successfully (serves index.html)
3. **Verify**:
   - ✅ Page title shows in browser tab
   - ✅ Page loads without 404 error
   - ✅ Main interface visible
   - ✅ No console errors (press F12, check Console tab)
4. **Status**: ⬜ PASS / ⬜ FAIL

**If FAIL, note error**: ___________________________

---

### Test 1.2: /file Path (New Entry Point)
1. **Navigate to**: `http://localhost:8000/file`
2. **Expected**: Page loads successfully (serves index.html)
3. **Verify**:
   - ✅ Same interface as `/` route
   - ✅ No redirect loop
   - ✅ URL stays as `/file`
   - ✅ Page fully functional
4. **Status**: ⬜ PASS / ⬜ FAIL

**If FAIL, note error**: ___________________________

---

### Test 1.3: /smart-tax Redirect
1. **Navigate to**: `http://localhost:8000/smart-tax`
2. **Expected**: Redirects to `/file?mode=smart`
3. **Verify**:
   - ✅ URL changes to `/file?mode=smart`
   - ✅ Page loads successfully
   - ✅ No 404 or error
   - ✅ Smart mode activated (if applicable)
4. **Status**: ⬜ PASS / ⬜ FAIL

**If FAIL, note error**: ___________________________

---

### Test 1.4: /client Redirect (Authenticated)
1. **Navigate to**: `http://localhost:8000/client`
2. **Expected**: Redirects to `/file`
3. **Verify**:
   - ✅ URL changes to `/file`
   - ✅ Page loads successfully
   - ✅ 302 redirect (not 404)
   - ✅ Session preserved (if logged in)
4. **Status**: ⬜ PASS / ⬜ FAIL

**If FAIL, note error**: ___________________________

---

## TEST 2: Issue #2 - White-Label Branding in Header

**Objective**: Verify professional header with white-label branding

### Test 2.1: Logo/Brand Display
1. **Navigate to**: `http://localhost:8000/file`
2. **Look at top-left of header**
3. **Expected**: Professional logo or firm initial badge
4. **Verify**:
   - ✅ Logo placeholder visible (letter badge like "C" for CA4CPA)
   - ✅ Company name displayed below logo
   - ✅ Firm credentials visible ("IRS-Approved E-File Provider")
   - ✅ Tagline visible below credentials
   - ✅ No "$" icon (old design)
   - ✅ Professional appearance
5. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test2-1-logo.png`

**If FAIL, note error**: ___________________________

---

### Test 2.2: Auto-Save Status (No "Start Over" Button)
1. **Look at top-right of header**
2. **Expected**: Auto-save status indicator (not "Start Over" button)
3. **Verify**:
   - ✅ "All changes saved" text visible
   - ✅ Checkmark icon next to text
   - ✅ NO "Start Over" button present
   - ✅ Help button visible
   - ✅ Support phone visible (if configured)
4. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test2-2-autosave.png`

**If FAIL, note error**: ___________________________

---

### Test 2.3: Mobile Responsive Header
1. **Open DevTools**: Press F12
2. **Toggle Device Toolbar**: Click phone icon or Ctrl+Shift+M
3. **Select**: iPhone SE (375px width)
4. **Expected**: Header adapts to mobile screen
5. **Verify**:
   - ✅ Logo/brand visible and readable
   - ✅ Elements don't overlap
   - ✅ No horizontal scroll
   - ✅ Trust badges wrap to next line
   - ✅ Buttons accessible
6. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test2-3-mobile.png`

**If FAIL, note error**: ___________________________

---

## TEST 3: Issue #3 - Trust Signals Header (Badges & Tooltips)

**Objective**: Verify enhanced trust badges with tooltips

### Test 3.1: Default Trust Badges (No Configuration)
1. **Navigate to**: `http://localhost:8000/file`
2. **Look at center of header**
3. **Expected**: 4 default trust badges visible
4. **Verify**:
   - ✅ **Badge 1**: Security claim (e.g., "Bank-level encryption")
   - ✅ **Badge 2**: "256-bit Encryption"
   - ✅ **Badge 3**: "IRS Certified"
   - ✅ **Badge 4**: "GDPR Compliant"
   - ✅ Each badge has an icon
   - ✅ Badges have pill/rounded shape
   - ✅ Professional styling (not plain text)
5. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test3-1-badges.png`

**Badge Count**: _____ (should be 4 by default)

**If FAIL, note error**: ___________________________

---

### Test 3.2: Tooltip Hover (Desktop)
**Test each badge individually:**

**Badge 1: Security**
1. **Hover mouse** over "Bank-level encryption" badge
2. **Expected**: Tooltip appears above badge
3. **Verify**:
   - ✅ Tooltip text: "Your data is protected with enterprise-grade encryption"
   - ✅ Tooltip has black background
   - ✅ Tooltip has white text
   - ✅ Arrow pointing to badge
   - ✅ Smooth fade-in animation (0.2s)
   - ✅ Tooltip disappears when mouse moves away
4. **Status**: ⬜ PASS / ⬜ FAIL

**Badge 2: 256-bit Encryption**
1. **Hover mouse** over "256-bit Encryption" badge
2. **Expected**: Tooltip: "All data transmitted using 256-bit SSL encryption"
3. **Status**: ⬜ PASS / ⬜ FAIL

**Badge 3: IRS Certified**
1. **Hover mouse** over "IRS Certified" badge
2. **Expected**: Tooltip: "IRS Authorized E-File Provider"
3. **Status**: ⬜ PASS / ⬜ FAIL

**Badge 4: GDPR Compliant**
1. **Hover mouse** over "GDPR Compliant" badge
2. **Expected**: Tooltip: "Compliant with EU data protection regulations"
3. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot with tooltip visible, save as `test3-2-tooltip.png`

**If FAIL, note error**: ___________________________

---

### Test 3.3: Optional Badges (With Configuration)
1. **Stop server** (Ctrl+C)
2. **Set environment variables**:
   ```bash
   export SHOW_CPA_BADGE=true
   export CPA_CREDENTIALS="CPA Reviewed"
   export SHOW_SOC2_BADGE=true
   export SHOW_AICPA_BADGE=true
   ```
3. **Restart server**
4. **Refresh page**: `http://localhost:8000/file`
5. **Expected**: 7 badges total (3 new badges added)
6. **Verify**:
   - ✅ "CPA Reviewed" badge appears
   - ✅ "SOC 2 Type II" badge appears
   - ✅ "AICPA Member" badge appears
   - ✅ All badges have tooltips
   - ✅ Layout not broken (badges wrap nicely)
7. **Status**: ⬜ PASS / ⬜ FAIL

**Badge Count with all enabled**: _____ (should be 7)

**Screenshot Location**: Take screenshot, save as `test3-3-all-badges.png`

**If FAIL, note error**: ___________________________

---

### Test 3.4: Custom Badge Text
1. **Stop server**
2. **Set custom text**:
   ```bash
   export ENCRYPTION_LEVEL="AES-256"
   export SECURITY_CLAIM="Military-grade encryption"
   export CPA_CREDENTIALS="Partner-level Review"
   ```
3. **Restart server**
4. **Refresh page**
5. **Expected**: Custom text appears in badges
6. **Verify**:
   - ✅ "Military-grade encryption" shows (not default)
   - ✅ "AES-256 Encryption" shows (not 256-bit)
   - ✅ "Partner-level Review" shows (if CPA badge enabled)
   - ✅ Tooltips updated with custom text
7. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test3-4-custom-text.png`

**If FAIL, note error**: ___________________________

---

### Test 3.5: Mobile Tooltips (Should be Hidden)
1. **Open DevTools** → Device Toolbar
2. **Select iPhone SE**
3. **Tap/click on badges**
4. **Expected**: No tooltips appear on mobile
5. **Verify**:
   - ✅ Badges visible and readable
   - ✅ No tooltips show on tap/touch
   - ✅ cursor: default (not cursor: help)
   - ✅ No layout issues
6. **Status**: ⬜ PASS / ⬜ FAIL

**Reason**: Touch devices don't have hover state

**If FAIL, note error**: ___________________________

---

## TEST 4: Issue #4 - Smart Question Filtering (145→30 Questions)

**Objective**: Verify two-tier filtering reduces questions shown

### Test 4.1: Navigate to Step 4 (Deductions)
1. **Navigate to**: `http://localhost:8000/file`
2. **Fill Step 1**: Personal info (dummy data OK)
3. **Click**: "Continue to Documents"
4. **Fill Step 2**: Upload/skip documents
5. **Click**: "Continue to Income"
6. **Fill Step 3**: Enter income (dummy data OK)
7. **Click**: "Continue to Deductions"
8. **Expected**: Arrives at **Step 4a: Category Selection Screen**
9. **Status**: ⬜ PASS / ⬜ FAIL

**If FAIL, note error**: ___________________________

---

### Test 4.2: Category Selection Screen (Step 4a)
1. **At Step 4a**
2. **Expected**: Professional card-based selection screen
3. **Verify**:
   - ✅ Title: "What types of expenses do you have?"
   - ✅ Subtitle: "Select all that apply..."
   - ✅ 8 category cards in grid layout:
     1. Mortgage Interest & Property Tax
     2. Medical & Dental Expenses
     3. Charitable Donations
     4. Education Expenses
     5. Child & Dependent Care
     6. Business Expenses
     7. Investment & Retirement
     8. Casualty & Theft Losses
   - ✅ 9th option: "None of these apply to me"
   - ✅ Each card has icon and description
   - ✅ Cards hover effect works
   - ✅ Multiple selection allowed
4. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test4-2-category-selection.png`

**If FAIL, note error**: ___________________________

---

### Test 4.3: Category Selection - "None" Option
1. **Click**: "None of these apply to me"
2. **Expected**: All other checkboxes uncheck
3. **Verify**:
   - ✅ "None" checkbox checked
   - ✅ All 8 category checkboxes unchecked
   - ✅ Cannot select "None" + another category
4. **Click**: "Continue"
5. **Expected**: Skips directly to **Step 5** (Review)
6. **Verify**:
   - ✅ Step 4 (detailed questions) skipped entirely
   - ✅ Lands on Step 5
   - ✅ No deduction questions shown
7. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot of Step 5, save as `test4-3-none-skip.png`

**If FAIL, note error**: ___________________________

---

### Test 4.4: Category Selection - Multiple Categories
1. **Navigate back to Step 4a** (use browser back or restart)
2. **Select 3 categories**:
   - ✅ Mortgage Interest & Property Tax
   - ✅ Medical & Dental Expenses
   - ✅ Charitable Donations
3. **Verify**:
   - ✅ 3 cards highlighted/checked
   - ✅ "None" option automatically unchecked
   - ✅ Visual checkmark on selected cards
4. **Click**: "Continue"
5. **Expected**: Shows **Step 4b: Filtered Questions**
6. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test4-4-multiple-selection.png`

**If FAIL, note error**: ___________________________

---

### Test 4.5: Filtered Questions (Step 4b)
1. **At Step 4b** (after selecting 3 categories)
2. **Expected**: Only selected categories visible
3. **Verify**:
   - ✅ **Section 1 visible**: "Mortgage Interest & Property Tax" questions
   - ✅ **Section 2 visible**: "Medical & Dental Expenses" questions
   - ✅ **Section 3 visible**: "Charitable Donations" questions
   - ✅ **NOT visible**: Education, Child Care, Business, Investment, Casualty sections
   - ✅ **Always visible**: "State Taxes" section
   - ✅ **Always visible**: "Other Deductions" section
4. **Count sections shown**: _____ (should be 5: 3 selected + State + Other)
5. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Scroll through and screenshot visible sections, save as `test4-5-filtered.png`

**If FAIL, note error**: ___________________________

---

### Test 4.6: Questions Count Comparison

**Without filtering (old design)**:
- Total questions: ~145 questions across all categories

**With filtering (new design - 3 categories selected)**:
- Estimated questions: ~30-40 questions

**Test**:
1. **Count visible input fields** in Step 4b
2. **Number of fields**: _____
3. **Expected**: 30-50 fields (vs 145 without filtering)
4. **Verify**: Significantly fewer questions shown
5. **Status**: ⬜ PASS / ⬜ FAIL

**Time saved**: Expected 70% reduction (30-35 min → 8-12 min)

**If FAIL, note error**: ___________________________

---

### Test 4.7: Mobile Responsive - Category Cards
1. **Open DevTools** → Device Toolbar
2. **iPhone SE (375px)**
3. **Navigate to Step 4a**
4. **Expected**: Cards stack vertically
5. **Verify**:
   - ✅ Cards stack in single column
   - ✅ All text readable
   - ✅ Icons visible
   - ✅ Checkboxes work on mobile
   - ✅ No horizontal scroll
6. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test4-7-mobile.png`

**If FAIL, note error**: ___________________________

---

## TEST 5: Issue #5 - Flatten Step 1 Wizard (6-7→1 Click)

**Objective**: Verify single scrollable form replaces nested wizard

### Test 5.1: Step 1 Structure (No Substeps)
1. **Navigate to**: `http://localhost:8000/file`
2. **Expected**: Lands on **Step 1: About You**
3. **Verify**:
   - ✅ Single form (not wizard with substeps)
   - ✅ All sections visible by scrolling
   - ✅ NO progress indicators (1/4, 2/4, 3/4, 4/4)
   - ✅ NO intermediate "Continue" buttons
   - ✅ ONE "Continue" button at bottom
4. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Full page screenshot, save as `test5-1-structure.png`

**If FAIL, note error**: ___________________________

---

### Test 5.2: Step 1 Sections Layout
**Scroll through Step 1 and verify all sections:**

1. **Section 1: Personal Information**
   - ✅ Name fields (First, Last)
   - ✅ SSN field
   - ✅ Date of Birth
   - ✅ Address fields
   - Status: ⬜ PASS / ⬜ FAIL

2. **Section 2: Filing Status**
   - ✅ Title: "Filing Status"
   - ✅ 3 card options: Single, Married, Widowed
   - ✅ Card-based selection (not dropdown)
   - ✅ Icons on each card
   - Status: ⬜ PASS / ⬜ FAIL

3. **Section 3: Widowed Details** (conditional)
   - ✅ Hidden by default
   - Status: ⬜ PASS / ⬜ FAIL

4. **Section 4: Spouse Information** (conditional)
   - ✅ Hidden by default
   - Status: ⬜ PASS / ⬜ FAIL

5. **Section 5: Dependents**
   - ✅ "Do you have dependents?" radio buttons
   - ✅ Dependent form hidden by default
   - Status: ⬜ PASS / ⬜ FAIL

6. **Section 6: Head of Household** (conditional)
   - ✅ Hidden by default
   - Status: ⬜ PASS / ⬜ FAIL

7. **Section 7: Additional Details**
   - ✅ Age 65+ checkbox
   - ✅ Blind checkbox
   - Status: ⬜ PASS / ⬜ FAIL

8. **Section 8: Direct Deposit**
   - ✅ Bank account fields (optional)
   - Status: ⬜ PASS / ⬜ FAIL

9. **Bottom Navigation**
   - ✅ ONE "Continue to Documents" button
   - ✅ NO other "Continue" buttons above
   - Status: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take multiple screenshots scrolling down, save as `test5-2-sections-*.png`

**If FAIL, note error**: ___________________________

---

### Test 5.3: Conditional Logic - Single Status
**Test: Single, No Dependents (Simplest Path)**

1. **Select**: "Single" filing status
2. **Expected**: No conditional sections appear
3. **Verify**:
   - ✅ Spouse section remains hidden
   - ✅ Widowed section remains hidden
   - ✅ HOH section remains hidden
4. **Select**: "No" for dependents
5. **Expected**: Dependent form remains hidden
6. **Verify**:
   - ✅ Dependent details form not visible
   - ✅ HOH section remains hidden
7. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test5-3-single-no-deps.png`

**If FAIL, note error**: ___________________________

---

### Test 5.4: Conditional Logic - Married Status
**Test: Married Filing Jointly**

1. **Refresh page** (start fresh)
2. **Select**: "Married" filing status
3. **Expected**: Spouse section appears with animation
4. **Verify**:
   - ✅ Spouse section slides in (smooth animation)
   - ✅ Spouse name fields visible
   - ✅ Spouse SSN field visible
   - ✅ Spouse DOB field visible
   - ✅ Filing preference options visible:
     - Radio: "Married Filing Jointly" (recommended)
     - Radio: "Married Filing Separately"
   - ✅ "Jointly" is pre-selected or recommended
5. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot with spouse section visible, save as `test5-4-married.png`

**If FAIL, note error**: ___________________________

---

### Test 5.5: Conditional Logic - Widowed Status
**Test: Widowed**

1. **Refresh page**
2. **Select**: "Widowed" filing status
3. **Expected**: Widowed section appears
4. **Verify**:
   - ✅ Widowed section slides in
   - ✅ Question: "When did your spouse pass away?"
   - ✅ Options: "In 2025", "In 2024", "In 2023", "Before 2023"
5. **Select**: "In 2024"
6. **Expected**: Filing status set to "Qualifying Surviving Spouse"
7. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test5-5-widowed.png`

**If FAIL, note error**: ___________________________

---

### Test 5.6: Conditional Logic - Dependents
**Test: Has Dependents**

1. **Scroll to Dependents section**
2. **Select**: "Yes, I have dependents"
3. **Expected**: Dependent details form appears
4. **Verify**:
   - ✅ Dependent form slides in
   - ✅ Fields visible:
     - Dependent name
     - Date of birth
     - Relationship
     - SSN
   - ✅ "Add another dependent" button
5. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test5-6-dependents.png`

**If FAIL, note error**: ___________________________

---

### Test 5.7: Conditional Logic - Head of Household
**Test: Single + Dependents = HOH Eligibility**

1. **Refresh page**
2. **Select**: "Single" filing status
3. **Select**: "Yes, I have dependents"
4. **Expected**: Head of Household section appears
5. **Verify**:
   - ✅ HOH section slides in
   - ✅ Question: "Did you pay more than half the household costs?"
   - ✅ Options: "Yes" / "No"
6. **Select**: "Yes"
7. **Expected**: Filing status set to "Head of Household"
8. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test5-7-hoh.png`

**If FAIL, note error**: ___________________________

---

### Test 5.8: Single Continue Button
**Test: One Click to Complete Step 1**

1. **Fill all visible fields** in Step 1 (dummy data OK)
2. **Scroll to bottom**
3. **Verify**:
   - ✅ ONE "Continue to Documents" button visible
   - ✅ NO other "Continue" buttons above
   - ✅ No "Next" or ">" buttons in sections
4. **Click**: "Continue to Documents"
5. **Expected**: Navigate to Step 2 (Documents)
6. **Verify**:
   - ✅ Step 2 loads successfully
   - ✅ Total clicks: 1 (not 6-7!)
   - ✅ No intermediate screens
7. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot of Step 2, save as `test5-8-step2.png`

**Clicks counted**: _____ (should be 1)

**If FAIL, note error**: ___________________________

---

### Test 5.9: Mobile Responsive - Step 1
1. **Open DevTools** → Device Toolbar
2. **iPhone SE (375px)**
3. **Navigate to Step 1**
4. **Expected**: All sections stack and are usable
5. **Verify**:
   - ✅ Form fields full width
   - ✅ Filing status cards stack vertically
   - ✅ Sections readable and accessible
   - ✅ Conditional sections work on mobile
   - ✅ No horizontal scroll
   - ✅ Continue button accessible
6. **Status**: ⬜ PASS / ⬜ FAIL

**Screenshot Location**: Take screenshot, save as `test5-9-mobile.png`

**If FAIL, note error**: ___________________________

---

### Test 5.10: Performance Comparison

**Old Design (Nested Wizard)**:
- Screens to click through: 6-7 substeps
- Total clicks: 6-7 clicks
- Estimated time: 8-10 minutes
- User experience: Confusing, false progress

**New Design (Flattened Form)**:
- Screens to click through: 1 form
- Total clicks: 1 click
- Estimated time: 5-7 minutes
- User experience: Clear, honest, straightforward

**Test**:
1. **Complete Step 1** from start to finish
2. **Time yourself**: _____ minutes
3. **Count clicks**: _____ clicks
4. **Expected**: 5-7 minutes, 1 click
5. **Improvement**: 40% faster, 85% fewer clicks
6. **Status**: ⬜ PASS / ⬜ FAIL

**If FAIL, note error**: ___________________________

---

## CROSS-CUTTING TESTS

### Test 6.1: Browser Compatibility
**Test on multiple browsers:**

1. **Chrome/Chromium**
   - Status: ⬜ PASS / ⬜ FAIL
   - Notes: _________________________

2. **Firefox**
   - Status: ⬜ PASS / ⬜ FAIL
   - Notes: _________________________

3. **Safari** (if on Mac)
   - Status: ⬜ PASS / ⬜ FAIL
   - Notes: _________________________

4. **Edge** (if on Windows)
   - Status: ⬜ PASS / ⬜ FAIL
   - Notes: _________________________

---

### Test 6.2: Console Errors
1. **Open DevTools** (F12)
2. **Go to Console tab**
3. **Navigate through all screens**
4. **Expected**: No errors (warnings OK)
5. **Verify**:
   - ✅ No red error messages
   - ✅ No JavaScript exceptions
   - ✅ No 404 errors for resources
   - ✅ No CORS errors
6. **Status**: ⬜ PASS / ⬜ FAIL

**If errors found, list them**: ___________________________

---

### Test 6.3: Network Errors
1. **Open DevTools** → **Network tab**
2. **Refresh page**
3. **Navigate through screens**
4. **Expected**: All requests successful (200/302)
5. **Verify**:
   - ✅ No 404 errors (missing files)
   - ✅ No 500 errors (server errors)
   - ✅ No failed requests (red lines)
6. **Status**: ⬜ PASS / ⬜ FAIL

**If errors found, list them**: ___________________________

---

### Test 6.4: Accessibility (Basic Check)
1. **Use Tab key** to navigate through form
2. **Expected**: Focus visible on all interactive elements
3. **Verify**:
   - ✅ Can tab through all fields
   - ✅ Focus indicator visible (blue outline)
   - ✅ Can submit with Enter key
   - ✅ Form labels associated with inputs
4. **Status**: ⬜ PASS / ⬜ FAIL

**If issues found**: ___________________________

---

### Test 6.5: Data Persistence (Auto-Save)
1. **Fill Step 1** partially
2. **Navigate to Step 2**
3. **Click Back** to Step 1
4. **Expected**: Data preserved (auto-saved)
5. **Verify**:
   - ✅ Personal info still filled
   - ✅ Filing status still selected
   - ✅ Dependents data preserved
   - ✅ No data loss
6. **Status**: ⬜ PASS / ⬜ FAIL

**If FAIL, note error**: ___________________________

---

## REGRESSION TESTS

### Test 7.1: Existing Features Still Work
**Verify no features were broken:**

1. **Step 2: Document Upload**
   - ✅ File upload works
   - Status: ⬜ PASS / ⬜ FAIL

2. **Step 3: Income**
   - ✅ W-2 income entry works
   - Status: ⬜ PASS / ⬜ FAIL

3. **Step 5: Review**
   - ✅ Review screen shows all data
   - Status: ⬜ PASS / ⬜ FAIL

4. **Step 6: Submit**
   - ✅ Can submit/generate return
   - Status: ⬜ PASS / ⬜ FAIL

**If any FAIL, note details**: ___________________________

---

## TEST SUMMARY

### Overall Results

**Total Tests**: 50+ individual test cases
**Tests Passed**: _____ / 50+
**Tests Failed**: _____ / 50+
**Pass Rate**: _____ %

**Critical Issues Found**: _____

**Status**: ⬜ APPROVED FOR PRODUCTION / ⬜ NEEDS FIXES

---

### Issue-by-Issue Summary

| Issue | Tests Passed | Tests Failed | Status |
|-------|-------------|--------------|--------|
| #1: Entry Points | ___/4 | ___/4 | ⬜ PASS / ⬜ FAIL |
| #2: Header Branding | ___/3 | ___/3 | ⬜ PASS / ⬜ FAIL |
| #3: Trust Badges | ___/5 | ___/5 | ⬜ PASS / ⬜ FAIL |
| #4: Smart Filtering | ___/7 | ___/7 | ⬜ PASS / ⬜ FAIL |
| #5: Flatten Step 1 | ___/10 | ___/10 | ⬜ PASS / ⬜ FAIL |
| Cross-Cutting | ___/5 | ___/5 | ⬜ PASS / ⬜ FAIL |
| Regression | ___/4 | ___/4 | ⬜ PASS / ⬜ FAIL |

---

### Screenshots Checklist

Save all screenshots in: `/docs/implementation/screenshots/`

- [ ] test2-1-logo.png (Header logo/branding)
- [ ] test2-2-autosave.png (Auto-save status)
- [ ] test2-3-mobile.png (Mobile header)
- [ ] test3-1-badges.png (Trust badges)
- [ ] test3-2-tooltip.png (Tooltip hover)
- [ ] test3-3-all-badges.png (All 7 badges)
- [ ] test3-4-custom-text.png (Custom badge text)
- [ ] test4-2-category-selection.png (Category cards)
- [ ] test4-3-none-skip.png (None option skip)
- [ ] test4-4-multiple-selection.png (Multiple categories)
- [ ] test4-5-filtered.png (Filtered questions)
- [ ] test4-7-mobile.png (Mobile category cards)
- [ ] test5-1-structure.png (Step 1 structure)
- [ ] test5-2-sections-*.png (All sections)
- [ ] test5-3-single-no-deps.png (Single status)
- [ ] test5-4-married.png (Married status)
- [ ] test5-5-widowed.png (Widowed status)
- [ ] test5-6-dependents.png (Dependents form)
- [ ] test5-7-hoh.png (Head of Household)
- [ ] test5-8-step2.png (Step 2 after completion)
- [ ] test5-9-mobile.png (Mobile Step 1)

---

### Critical Issues Log

**If you find critical bugs, document them here:**

#### Issue 1:
- **Test**: ___________________________
- **Expected**: ___________________________
- **Actual**: ___________________________
- **Severity**: 🔴 CRITICAL / 🟡 MEDIUM / 🟢 LOW
- **Blocking**: ⬜ YES / ⬜ NO

#### Issue 2:
- **Test**: ___________________________
- **Expected**: ___________________________
- **Actual**: ___________________________
- **Severity**: 🔴 CRITICAL / 🟡 MEDIUM / 🟢 LOW
- **Blocking**: ⬜ YES / ⬜ NO

#### Issue 3:
- **Test**: ___________________________
- **Expected**: ___________________________
- **Actual**: ___________________________
- **Severity**: 🔴 CRITICAL / 🟡 MEDIUM / 🟢 LOW
- **Blocking**: ⬜ YES / ⬜ NO

---

## APPROVAL SIGN-OFF

**Tester Name**: Rakesh Anita
**Date Tested**: _______________
**Testing Duration**: _____ hours

**Sprint 1 Status**:
- ⬜ ✅ **APPROVED** - All 5 issues working as expected, ready for production
- ⬜ ⚠️ **APPROVED WITH MINOR ISSUES** - Non-blocking issues found, can deploy
- ⬜ ❌ **REJECTED** - Critical issues found, fixes required before deployment

**Signature**: _____________________

**Notes**:
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________

---

**Next Steps After Approval**:
1. Commit all changes to git
2. Create git tags for each issue
3. Update PROGRESS_TRACKER.md with user approval
4. Move to Sprint 2 planning
5. Deploy to staging environment
6. User acceptance testing (UAT)

---

**For Developer Use**:

**Rollback Plan** (if critical issues found):
```bash
# Revert all Sprint 1 changes
git checkout checkpoint-pre-ux-upgrade

# Or revert individual issues
git revert [commit-hash-issue-1]
git revert [commit-hash-issue-2]
# etc.
```

**Re-test Command** (after fixes):
```bash
# Restart from this guide, Test X.X
```

---

**END OF COMPREHENSIVE MANUAL TESTING GUIDE**

*This document covers 50+ test cases across all 5 Sprint 1 issues*
*Estimated testing time: 2-3 hours for thorough testing*
*Save this document for future regression testing*
