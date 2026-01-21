# Client UX Upgrade - Progress Tracker

**Started**: 2026-01-21
**Status**: 🟡 In Progress
**Completion**: 0 / 25 issues (0%)

---

## Sprint 1: Critical Issues (5 total)

### ✅ Issue #1: Single Entry Point (/file only)
**Status**: 🔄 Starting
**Priority**: CRITICAL
**Time Estimate**: 1 hour
**Assigned**: In Progress

**Changes Needed**:
- [ ] Read current route structure in src/web/app.py
- [ ] Identify all entry points (/smart-tax, /entry-choice, /chat)
- [ ] Create 301 redirects to /file
- [ ] Update internal navigation links
- [ ] Test all redirects work
- [ ] Verify session state persists

**Files to Modify**:
- src/web/app.py (routes)
- src/web/templates/*.html (navigation links)

**Testing Checklist**:
- [ ] /smart-tax redirects to /file
- [ ] Session ID preserved across redirect
- [ ] No 404 errors
- [ ] User tested and approved ✅

**Notes**:
- Client wants ONE entry point only
- All other routes internal/hidden
- No free access, all authenticated

---

### ⏳ Issue #2: White-Label Branding
**Status**: Pending
**Priority**: CRITICAL

---

### ⏳ Issue #3: Trust Signals Header
**Status**: Pending
**Priority**: CRITICAL

---

### ⏳ Issue #4: Smart Question Filtering
**Status**: Pending
**Priority**: CRITICAL

---

### ⏳ Issue #5: Flatten Step 1 Wizard
**Status**: Pending
**Priority**: CRITICAL

---

## Sprint 2: High Priority (5 issues)
**Status**: Not Started

---

## Sprint 3: Medium Priority (10 issues)
**Status**: Not Started

---

## Sprint 4: Polish (5 issues)
**Status**: Not Started

---

## Metrics
- **Issues Completed**: 0 / 25
- **Time Spent**: 0 hours
- **Regressions Found**: 0
- **User Approvals**: 0 / 0

---

**Last Updated**: 2026-01-21 (Auto-updating)
