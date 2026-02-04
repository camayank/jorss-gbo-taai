# FREEZE & FINISH: Platform Completion Plan

## Executive Summary

This document defines the scope boundary for the **Jorss-Gbo CPA Lead Generation & AI Advisory Platform** MVP.

**BUSINESS MODEL:** Generate qualified, engaged leads for CPAs through AI-powered tax advisory.
- This is NOT a tax filing system
- This is NOT an engagement letter generator
- The CPA handles return filing, engagement, and payments OUTSIDE this system

All features listed as "IN SCOPE" must work end-to-end before launch.
Features "OUT OF SCOPE" will gracefully degrade with clear user messaging.

**See:** `FINAL_PRODUCT_FLOW.md` for the frozen user flow and feature scope.

---

## 1. FROZEN SCOPE DEFINITION

### Core Value Proposition (MUST WORK 100%)

| # | Feature | User Journey | Status |
|---|---------|--------------|--------|
| 1 | Lead Magnet Funnel | Landing → Estimate → Teaser → Capture → Report | COMPLETE |
| 2 | AI Tax Chat | Chat → Profile Build → Calculation → Strategies | COMPLETE |
| 3 | Intelligent Advisor | Full advisory with 35 recommendation sources | COMPLETE |
| 4 | Smart Tax Flow | Upload → OCR → Confirm → Report → Act | COMPLETE |
| 5 | Tax Calculations | Federal + 50 States + SE Tax + Credits | COMPLETE |
| 6 | Recommendations | 35 sources, deduplicated, actionable | COMPLETE |
| 7 | Scenario Analysis | What-if, Filing Status, Retirement, Entity | COMPLETE |
| 8 | CPA Dashboard | Lead list, Detail, Pipeline, Analytics | COMPLETE |
| 9 | Health Monitoring | /health, /health/live, /health/ready, /metrics | NEEDS FIX |

### Deferred to Phase 2 (Graceful Degradation)

| # | Feature | Current State | Graceful Message |
|---|---------|---------------|------------------|
| 1 | Stripe Payments | Mock responses | "Contact CPA directly for payment" |
| 2 | Email Notifications | Not wired | "Check dashboard for updates" |
| 3 | Multi-tenant Enforcement | Default tenant | Single-tenant mode |
| 4 | Admin Impersonation | Stub | Admin uses direct DB access |
| 5 | DNS Verification | Not implemented | Use platform subdomain |
| 6 | Prior Year Import | Mock data | "Feature coming soon" |

---

## 2. REQUIRED FIXES (12 Items)

### Priority 1: User-Facing Fixes (Blocks Core Journey)

#### Fix 1: Express Lane Prior Year - Remove Mock Data
**File:** `src/web/express_lane_api.py:337-356`
**Issue:** Returns hardcoded "John Doe" data
**Fix:** Return clear "feature unavailable" message instead of fake data

```python
# BEFORE: Returns mock "John Doe" data
# AFTER: Clear feature unavailability
return {
    "success": False,
    "imported_fields": {},
    "message": "Prior year import is not yet available. Please enter your information manually.",
    "feature_status": "coming_soon"
}
```

#### Fix 2: OCR Fallback - Clear Error Message
**File:** `src/cpa_panel/services/smart_onboarding_service.py:320-329`
**Issue:** Returns "Mock OCR text for testing" with 50% confidence
**Fix:** Return clear error asking user to upload clearer document

#### Fix 3: Payment Intent - Honest Response
**File:** `src/cpa_panel/api/payment_settings_routes.py:534-547`
**Issue:** Returns fake payment intent in development
**Fix:** Return clear message that payment is handled outside platform

### Priority 2: Health & Monitoring Fixes

#### Fix 4: Database Health Check - Real Query
**File:** `src/web/health_checks.py:67-86`
**Fix:** Actually query the SQLite database

```python
def check_database() -> DependencyStatus:
    try:
        import sqlite3
        import time
        from pathlib import Path

        db_path = Path(__file__).parent.parent / "database" / "jorss_gbo.db"
        start = time.time()

        conn = sqlite3.connect(str(db_path), timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()

        response_time = (time.time() - start) * 1000

        return DependencyStatus(
            name="database",
            status="up",
            response_time_ms=round(response_time, 2),
            message="SQLite connection OK"
        )
    except Exception as e:
        return DependencyStatus(
            name="database",
            status="down",
            message=str(e)
        )
```

#### Fix 5: Admin Metrics - Use Real Counters
**File:** `src/web/admin_endpoints.py:71-78`
**Fix:** Use the request/calculation metrics from health.py

### Priority 3: Graceful Degradation Messages

#### Fix 6: Team Invitation Email
**File:** `src/admin_panel/api/team_routes.py:321`
**Fix:** Add user message that invitation link will be shown on screen

#### Fix 7: Notification Preferences
**File:** `src/cpa_panel/api/notification_routes.py:209,230`
**Fix:** Store in session/local storage with clear "preferences saved locally" message

#### Fix 8: Client Assignment Notification
**File:** `src/admin_panel/api/client_routes.py:378`
**Fix:** Return clear message "Notification feature coming soon"

### Priority 4: Security Boundaries

#### Fix 9: Auth Decorator Logging
**File:** `src/security/auth_decorators.py`
**Fix:** Keep current permissive mode but add clear logging for audit trail

#### Fix 10: Tenant Isolation Logging
**File:** `src/security/tenant_isolation.py:94,373`
**Fix:** Log all access for audit, keep permissive for MVP

### Priority 5: Admin Features

#### Fix 11: Firm Details Endpoint
**File:** `src/admin_panel/api/superadmin_routes.py:261`
**Fix:** Return "Details unavailable" instead of fake metrics

#### Fix 12: Support Mode
**File:** `src/admin_panel/api/superadmin_routes.py:303`
**Fix:** Return clear error "Feature not available, use direct DB access"

---

## 3. IMPLEMENTATION CHECKLIST

### Phase A: Core Journey Fixes - COMPLETED
- [x] Fix 1: Express Lane - return "coming soon" message
- [x] Fix 2: OCR Fallback - clear error message
- [x] Fix 3: Payment Intent - honest response
- [x] Fix 4: Database Health - real SQLite query

### Phase B: Graceful Degradation - COMPLETED
- [x] Fix 5: Admin Metrics - real counters from health router
- [x] Fix 6: Team Invitation - link logged, email deferred note
- [x] Fix 7: Notification Preferences - localStorage recommendation
- [x] Fix 8: Assignment Notification - coming soon message

### Phase C: Security & Admin - COMPLETED
- [x] Fix 9: Auth logging - comprehensive [AUDIT] trail with IP/UA
- [x] Fix 10: Tenant access logging - permissive mode with audit
- [x] Fix 11: Firm details - 501 Not Implemented response
- [x] Fix 12: Support mode - 501 with audit logging

---

## 4. USER JOURNEY VALIDATION

After fixes, validate these complete journeys work:

### Journey 1: Lead Magnet (Taxpayer)
```
1. Visit /lead-magnet?cpa=demo
2. Click "Get Free Estimate"
3. Answer 3 questions
4. See savings teaser
5. Enter email/phone
6. View Tier 1 report with strategies
7. See CPA contact info
```

### Journey 2: AI Tax Chat (Taxpayer)
```
1. Visit /intelligent-advisor
2. Say "I made $150,000 this year"
3. Answer follow-up questions
4. See real-time tax estimate update
5. Ask "How can I save on taxes?"
6. Receive personalized strategies
7. See action steps with deadlines
```

### Journey 3: Smart Tax Flow (Taxpayer)
```
1. Visit /smart-tax
2. Upload W-2 document
3. See OCR extraction (or clear error)
4. Confirm/edit extracted data
5. View tax report
6. See complexity assessment
7. Get CPA recommendation if needed
```

### Journey 4: CPA Dashboard (CPA)
```
1. Visit /cpa/dashboard
2. See lead pipeline summary
3. Click on a lead
4. View full lead details + tax situation
5. See recommended strategies
6. View engagement letter option
```

### Journey 5: Health Check (DevOps)
```
1. GET /health - full system status
2. GET /health/live - returns OK
3. GET /health/ready - database connected
4. GET /metrics - real request counts
```

---

## 5. ACCEPTANCE CRITERIA

### Definition of Done

A feature is COMPLETE when:
1. User can complete the entire journey without errors
2. No mock/fake data is shown to users
3. Unavailable features show clear "coming soon" messages
4. All API responses are valid JSON with proper status codes
5. Errors are logged with context for debugging

### Quality Gates

Before marking FREEZE & FINISH complete:
- [x] All 5 user journeys pass manual testing (2026-01-27)
- [x] No console errors in browser
- [x] All /health endpoints return real data
- [x] No "John Doe" or "Mock" text visible to users
- [x] All deferred features show graceful messages

---

## 6. WHAT WE ARE NOT DOING

To maintain scope discipline, we explicitly will NOT:

1. ❌ Add new features
2. ❌ Integrate Stripe (Phase 2)
3. ❌ Integrate email service (Phase 2)
4. ❌ Enforce multi-tenant isolation (Phase 2)
5. ❌ Build mobile app
6. ❌ Add voice interface
7. ❌ Implement admin impersonation
8. ❌ Add new recommendation sources
9. ❌ Create new templates
10. ❌ Refactor existing working code

---

## 7. SUCCESS METRICS

### MVP Launch Criteria

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Lead Funnel Completion | 100% | Manual test all 8 pages |
| Chat Response Rate | 100% | All questions get valid response |
| Calculation Accuracy | 100% | Compare to IRS worksheets |
| Recommendation Generation | 100% | All profiles get strategies |
| Health Endpoint Accuracy | 100% | Real data, no hardcoded values |
| Error Rate | < 1% | No uncaught exceptions |

---

## 8. TIMELINE

| Day | Focus | Deliverable |
|-----|-------|-------------|
| Day 1 | Core Journey Fixes | Fixes 1-4 complete |
| Day 2 | Graceful Degradation | Fixes 5-8 complete |
| Day 3 | Security & Admin | Fixes 9-12 complete |
| Day 4 | Integration Testing | All journeys validated |
| Day 5 | Polish & Documentation | README updated, ready for demo |

---

## SIGN-OFF

- [x] Product Owner approves scope
- [x] All 12 fixes implemented (2025-01-27)
- [x] All 5 journeys tested (2026-01-27)
- [x] No fake data visible (mock data replaced with clear messages)
- [x] Documentation complete

**Platform Status: FROZEN & FINISHED** ✓

---

## IMPLEMENTATION LOG (2025-01-27)

### Files Modified:

| File | Change |
|------|--------|
| `src/web/express_lane_api.py` | Replaced mock "John Doe" data with "coming soon" message |
| `src/cpa_panel/services/smart_onboarding_service.py` | Replaced mock OCR with clear error + suggestions |
| `src/cpa_panel/api/payment_settings_routes.py` | Replaced fake payment intent with "contact CPA" message |
| `src/web/health_checks.py` | Real SQLite connectivity check with table count |
| `src/web/admin_endpoints.py` | Real metrics from health router counters |
| `src/admin_panel/api/team_routes.py` | Email deferred note (3 locations) |
| `src/cpa_panel/api/notification_routes.py` | localStorage recommendation for preferences |
| `src/admin_panel/api/client_routes.py` | Notification coming soon message |
| `src/security/auth_decorators.py` | Comprehensive [AUDIT] logging with IP/UA |
| `src/security/tenant_isolation.py` | Permissive mode with audit trail |
| `src/admin_panel/api/superadmin_routes.py` | 501 responses for firm details & impersonation |

### What Users Will See:

1. **Prior Year Import**: "Prior year import is coming soon. Please enter your information manually for now."
2. **OCR Failure**: Clear error with suggestions to upload clearer document
3. **Payment**: "Online payment processing is coming soon. Please contact your CPA directly."
4. **Health Check**: Real database status with table count
5. **Admin Metrics**: Actual request counts and calculation metrics
6. **Team Invitations**: Invitation link logged, "email coming soon" implicit
7. **Notifications**: "Preferences saved locally. Database sync coming soon."
8. **Client Assignment**: "Email notifications coming soon. Please notify the assignee manually."
9. **Admin Features**: HTTP 501 "Feature not available" for firm details/impersonation
