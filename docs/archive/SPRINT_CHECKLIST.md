# Sprint Checklist - Quick Reference

> Use this to track daily progress. Check off items as completed.

---

## Sprint 0: Critical Fixes (Days 1-3)

### Day 1: Secrets & Startup
- [ ] Remove hardcoded JWT secret from `src/rbac/jwt.py`
- [ ] Remove hardcoded secret from `src/core/services/auth_service.py`
- [ ] Add startup validation in `src/config/settings.py`
- [ ] Create `.env.production.example` with all required vars
- [ ] Test: App fails to start without `SECRET_KEY`

### Day 2: PII Encryption
- [ ] Create `src/database/encrypted_fields.py`
- [ ] Update lead persistence to encrypt email/phone
- [ ] Update session persistence to encrypt SSN
- [ ] Create migration script for existing data
- [ ] Test: `SELECT email FROM leads` returns encrypted blob

### Day 3: Isolation & Rate Limiting
- [ ] Add tenant validation to all lead endpoints
- [ ] Create `verify_lead_access()` function
- [ ] Add rate limiting: 10 estimates/min, 5 contacts/min
- [ ] Test: CPA A cannot access CPA B's leads
- [ ] Test: Rate limit returns 429 after threshold

---

## Sprint 1: Lead Magnet (Days 4-10)

### Day 4-5: Landing Page
- [ ] Create `src/web/templates/lead_magnet.html`
- [ ] Create `src/web/routers/lead_magnet.py`
- [ ] Add hero section with CTA
- [ ] Add trust signals section
- [ ] Apply tenant branding (colors, logo)
- [ ] Test: Page loads < 2 seconds
- [ ] Test: Mobile responsive

### Day 6-7: Quick Estimate Form
- [ ] Create 3-question form component
- [ ] Question 1: Filing status (dropdown)
- [ ] Question 2: Income range (slider or brackets)
- [ ] Question 3: Dependents (number input)
- [ ] Add progress indicator
- [ ] Create `POST /api/leads/quick-estimate` endpoint
- [ ] Implement savings range calculation
- [ ] Test: Form completes in < 60 seconds
- [ ] Test: Validation prevents bad data

### Day 8: Savings Teaser
- [ ] Create `src/web/templates/savings_teaser.html`
- [ ] Display savings range prominently
- [ ] Show top 3 opportunities (icons + titles)
- [ ] Add CPA introduction (photo, name, credentials)
- [ ] Add urgency element (tax deadline countdown)
- [ ] Test: Teaser displays correct savings
- [ ] Test: CPA info visible

### Day 9: Contact Capture
- [ ] Create contact form (email required, phone optional, name required)
- [ ] Add real-time email validation
- [ ] Create `POST /api/leads/{lead_id}/contact` endpoint
- [ ] Encrypt PII before storage
- [ ] Calculate and store lead score
- [ ] Transition lead state to EVALUATING
- [ ] Show success confirmation
- [ ] Test: Lead created in database
- [ ] Test: State is EVALUATING after capture

### Day 10: Full Analysis & Disclaimers
- [ ] Redirect to full analysis after contact capture
- [ ] Show all opportunities (not just top 3)
- [ ] Display CPA contact info prominently
- [ ] Add disclaimer to quick estimate (before starting)
- [ ] Add disclaimer to savings teaser (footer)
- [ ] Add disclaimer to full analysis (header + footer)
- [ ] Add T&C checkbox on contact capture
- [ ] Test: Full analysis only accessible after contact
- [ ] Test: Disclaimers visible at every step

---

## Sprint 2: CPA Dashboard (Days 11-20)

### Day 11-12: Dashboard Layout
- [ ] Create `src/web/templates/cpa/dashboard.html`
- [ ] Create `src/web/templates/cpa/base.html`
- [ ] Add navigation sidebar (Dashboard, Leads, Settings)
- [ ] Add header with CPA info and logout
- [ ] Create `src/web/routers/cpa_dashboard.py`
- [ ] Test: Layout renders correctly
- [ ] Test: Mobile responsive (collapsible sidebar)

### Day 13-14: Pipeline Summary Cards
- [ ] Create summary cards component
- [ ] Create `GET /api/cpa/dashboard/summary` endpoint
- [ ] Display: NEW, CONTACTED, ENGAGED, CONVERTED counts
- [ ] Add revenue card (total from converted)
- [ ] Make cards clickable (filter lead list)
- [ ] Test: Counts match database
- [ ] Test: Click filters work

### Day 15-17: Lead List Table
- [ ] Create lead table component
- [ ] Create `GET /api/cpa/leads` endpoint with pagination
- [ ] Add columns: Name, Email (masked), Income, Savings, Score, Status, Date
- [ ] Add filters: Status, Date range, Score range
- [ ] Add search by name/email
- [ ] Add sorting by any column
- [ ] Add bulk selection (checkboxes)
- [ ] Row click navigates to detail
- [ ] Test: 50 leads load < 1 second
- [ ] Test: All filters work correctly
- [ ] Test: Pagination works

### Day 18-19: Lead Detail View
- [ ] Create `src/web/templates/cpa/lead_detail.html`
- [ ] Create `GET /api/cpa/leads/{lead_id}` endpoint
- [ ] Display contact info section
- [ ] Display tax profile section
- [ ] Display savings breakdown
- [ ] Display activity timeline
- [ ] Add action buttons (Mark Contacted, etc.)
- [ ] Add notes section
- [ ] Test: All lead data displays correctly
- [ ] Test: Actions work

### Day 20: Lead Actions & Assignment
- [ ] Implement Mark as Contacted action
- [ ] Implement Mark as Engaged action
- [ ] Implement Convert to Client action
- [ ] Implement Archive Lead action
- [ ] Implement Add Note action
- [ ] Implement bulk actions
- [ ] Create unassigned leads view
- [ ] Implement self-assignment
- [ ] Test: All state transitions work
- [ ] Test: Activity logged for each action

---

## Sprint 3: Conversion Flow (Days 21-30)

### Day 21-23: CPA Notifications
- [ ] Create `src/notifications/cpa_notifications.py`
- [ ] Implement new lead email notification
- [ ] Implement high-value lead alert (score > 85)
- [ ] Implement in-app notifications (badge on dashboard)
- [ ] Add notification preferences for CPA
- [ ] Test: Email sent within 1 minute of lead capture
- [ ] Test: High-value leads get immediate alert

### Day 24-25: Lead Welcome Email
- [ ] Create `src/notifications/lead_emails.py`
- [ ] Create welcome email template (branded)
- [ ] Include savings summary
- [ ] Include CPA contact info
- [ ] Include next steps
- [ ] Add unsubscribe link
- [ ] Test: Email sent immediately after contact capture
- [ ] Test: Tenant branding applied

### Day 26-27: Follow-up Reminders
- [ ] Create `src/tasks/follow_up_tasks.py`
- [ ] Implement 24h reminder ("Lead not contacted")
- [ ] Implement 48h escalation ("Urgent")
- [ ] Implement 7-day stale warning
- [ ] Add overdue follow-ups widget to dashboard
- [ ] Test: Reminders sent at correct intervals
- [ ] Test: Visible in dashboard

### Day 28-30: Engagement Letter & Activity Logging
- [ ] Create engagement letter template
- [ ] Auto-populate from lead data
- [ ] Generate PDF from template
- [ ] Implement email send with attachment
- [ ] Track signature status (Sent, Viewed, Signed)
- [ ] Log all email sends
- [ ] Log all state changes
- [ ] Log all CPA actions
- [ ] Display in lead timeline
- [ ] Test: Letter generates with correct data
- [ ] Test: All activities logged

---

## Sprint 4: Polish & Launch (Days 31-40)

### Day 31-33: Security Audit
- [ ] Run OWASP ZAP scan
- [ ] Fix any HIGH/CRITICAL findings
- [ ] Manual penetration test on lead endpoints
- [ ] Review all SQL queries for injection
- [ ] Verify PII encryption working
- [ ] Test tenant isolation thoroughly
- [ ] Test: No HIGH/CRITICAL findings remain

### Day 34-35: Performance & Monitoring
- [ ] Add database indexes for lead queries
- [ ] Implement caching for dashboard summary
- [ ] Optimize lead list query
- [ ] Minify CSS/JS
- [ ] Set up Sentry for error tracking
- [ ] Create custom 404/500 error pages
- [ ] Create `/health` endpoint
- [ ] Set up uptime monitoring
- [ ] Test: Dashboard loads < 2 seconds
- [ ] Test: Lead list loads < 1 second

### Day 36-37: Documentation
- [ ] Write CPA onboarding guide
- [ ] Write lead magnet setup guide
- [ ] Write dashboard user guide
- [ ] Document API endpoints
- [ ] Write admin setup guide
- [ ] Review and update README

### Day 38-40: Beta Launch
- [ ] Create Dockerfile
- [ ] Create docker-compose.yml
- [ ] Set up CI/CD pipeline (GitHub Actions)
- [ ] Configure staging environment
- [ ] Configure production environment
- [ ] Set up database backup automation
- [ ] Create demo tenant with sample data
- [ ] Create beta signup form
- [ ] Add in-app feedback button
- [ ] Set up analytics tracking
- [ ] Deploy to production
- [ ] Invite first beta CPAs
- [ ] 🎉 **BETA LAUNCH!**

---

## Daily Standup Questions

1. What did I complete yesterday?
2. What will I complete today?
3. What's blocking me?

---

## Quick Links

- Sprint Plan: `SPRINT_PLAN.md`
- Lead Magnet Router: `src/web/routers/lead_magnet.py`
- CPA Dashboard: `src/web/templates/cpa/dashboard.html`
- Lead API: `src/cpa_panel/api/lead_routes.py`
- Notifications: `src/notifications/`

---

## Emergency Contacts

- Database issues: Check `src/database/`
- Auth issues: Check `src/security/`, `src/rbac/`
- Lead state: Check `src/cpa_panel/lead_state/`
