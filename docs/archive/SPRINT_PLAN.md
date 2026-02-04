# CPA Lead-Gen Platform: 8-Week Sprint Plan

> **Goal:** Transform tax advisory platform into sellable B2B SaaS for CPA lead generation
> **Target:** First paying customer by Week 8
> **Effort:** ~280 hours total

---

## Overview

```
Week 1-2:  Sprint 0 - Critical Fixes + Sprint 1 - Lead Magnet
Week 3-4:  Sprint 2 - CPA Dashboard MVP
Week 5-6:  Sprint 3 - Conversion Flow + Automation
Week 7-8:  Sprint 4 - Polish, Security, Launch
```

---

## Sprint 0: Critical Fixes (Week 1, Days 1-3)
**Duration:** 3 days | **Effort:** 24 hours

### Goals
- [ ] Remove all production blockers
- [ ] Establish secure foundation for PII handling
- [ ] Enable safe beta testing

### Tasks

#### 0.1 Remove Hardcoded Secrets (4 hours)
**Priority:** P0 - BLOCKER

| Task | File | Action |
|------|------|--------|
| 0.1.1 | `src/rbac/jwt.py` | Replace hardcoded JWT secret with `os.environ.get()` |
| 0.1.2 | `src/core/services/auth_service.py` | Replace hardcoded secret |
| 0.1.3 | `src/config/settings.py` | Fail startup if `SECRET_KEY` not set |
| 0.1.4 | `src/security/encryption.py` | Fail startup if `ENCRYPTION_KEY` not set |
| 0.1.5 | Create `.env.production.example` | Document all required env vars |

**Acceptance Criteria:**
- App refuses to start without required secrets
- No secrets in codebase (grep returns 0 matches)
- `.env.example` documents all required variables

```python
# Example fix for src/config/settings.py
def get_secret_key():
    key = os.environ.get("SECRET_KEY")
    if not key:
        raise RuntimeError("SECRET_KEY environment variable required")
    if key == "change-me-in-production-INSECURE":
        raise RuntimeError("SECRET_KEY must be changed from default")
    return key
```

#### 0.2 PII Encryption at Rest (8 hours)
**Priority:** P0 - BLOCKER

| Task | File | Action |
|------|------|--------|
| 0.2.1 | `src/database/models.py` | Add encrypted field type for PII |
| 0.2.2 | `src/database/lead_state_persistence.py` | Encrypt email/phone before storage |
| 0.2.3 | `src/database/session_persistence.py` | Encrypt SSN fields |
| 0.2.4 | Create migration script | Encrypt existing data |

**Acceptance Criteria:**
- `SELECT email FROM leads` returns encrypted blob, not plaintext
- Decryption requires `ENCRYPTION_KEY` env var
- Existing data migrated to encrypted format

```python
# src/database/encrypted_fields.py
from cryptography.fernet import Fernet

class EncryptedString:
    """Transparent encryption for PII fields"""

    @staticmethod
    def encrypt(value: str) -> str:
        if not value:
            return value
        key = os.environ.get("ENCRYPTION_KEY")
        f = Fernet(key.encode())
        return f.encrypt(value.encode()).decode()

    @staticmethod
    def decrypt(value: str) -> str:
        if not value:
            return value
        key = os.environ.get("ENCRYPTION_KEY")
        f = Fernet(key.encode())
        return f.decrypt(value.encode()).decode()
```

#### 0.3 Lead Tenant Isolation (4 hours)
**Priority:** P0 - BLOCKER

| Task | File | Action |
|------|------|--------|
| 0.3.1 | `src/cpa_panel/api/lead_routes.py` | Add tenant validation to all endpoints |
| 0.3.2 | `src/security/tenant_isolation.py` | Add `verify_lead_access()` function |
| 0.3.3 | Add integration test | Verify CPA A can't access CPA B's leads |

**Acceptance Criteria:**
- API returns 403 when accessing other tenant's leads
- Audit log entry created for access attempts
- Test proves isolation works

#### 0.4 Startup Validation (4 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 0.4.1 | `src/config/startup_checks.py` | Create startup validation module |
| 0.4.2 | `src/web/app.py` | Run checks before app starts |
| 0.4.3 | Check database connectivity | Fail fast if DB unreachable |
| 0.4.4 | Check required env vars | List all missing vars |

**Acceptance Criteria:**
- App fails with clear error message if misconfigured
- All required services checked (DB, Redis if used, encryption key)

#### 0.5 Rate Limiting on Lead Endpoints (4 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 0.5.1 | `src/security/middleware.py` | Add rate limits to lead endpoints |
| 0.5.2 | `/api/leads/estimate` | 10 requests/minute per IP |
| 0.5.3 | `/api/leads/contact` | 5 requests/minute per IP |
| 0.5.4 | `/api/leads/queue/*` | 30 requests/minute per CPA |

---

## Sprint 1: Lead Magnet MVP (Week 1-2, Days 4-10)
**Duration:** 7 days | **Effort:** 56 hours

### Goals
- [ ] Create standalone lead capture flow
- [ ] Build savings teaser page
- [ ] Implement contact gate
- [ ] Show CPA branding in flow

### User Flow
```
[Landing] → [3-Question Form] → [Savings Teaser] → [Contact Gate] → [Full Analysis]
                                       ↓                  ↓
                              "Save $2,400-$4,800"    "Enter email to unlock"
                                       ↓                  ↓
                              [CPA Photo + Name]    [Lead Created in DB]
```

### Tasks

#### 1.1 Lead Magnet Landing Page (8 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 1.1.1 | `src/web/templates/lead_magnet.html` | Create new template |
| 1.1.2 | `src/web/routers/lead_magnet.py` | Create router |
| 1.1.3 | Design: Hero section | "Discover Your Hidden Tax Savings" |
| 1.1.4 | Design: Trust signals | "Trusted by X CPAs", "Bank-level security" |
| 1.1.5 | Design: CTA button | "Get My Free Tax Analysis" |
| 1.1.6 | White-label support | Pull colors/logo from tenant branding |

**Acceptance Criteria:**
- Page loads in <2 seconds
- Mobile responsive
- Tenant branding applied
- Single CTA leads to quick estimate form

```html
<!-- src/web/templates/lead_magnet.html structure -->
<div class="lead-magnet-hero" style="background: var(--tenant-primary)">
  <img src="{{ branding.logo_url }}" class="logo">
  <h1>Discover Your Hidden Tax Savings</h1>
  <p>In 60 seconds, see how much you could save with {{ branding.company_name }}</p>
  <button onclick="startEstimate()">Get My Free Analysis →</button>
</div>

<div class="trust-signals">
  <div>🔒 Bank-Level Encryption</div>
  <div>⚡ 60-Second Analysis</div>
  <div>📊 Personalized Results</div>
</div>
```

#### 1.2 Quick Estimate Form (12 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 1.2.1 | `src/web/templates/components/quick_estimate_form.html` | 3-question form |
| 1.2.2 | Question 1 | Filing status (Single/Married/HoH) |
| 1.2.3 | Question 2 | Annual income range (slider or brackets) |
| 1.2.4 | Question 3 | Number of dependents |
| 1.2.5 | Progress indicator | Step 1/2/3 visual |
| 1.2.6 | `src/web/routers/lead_magnet.py` | POST endpoint for estimate |
| 1.2.7 | Validation | Client-side + server-side |

**Acceptance Criteria:**
- Form completes in <60 seconds
- Validation prevents bad data
- Progress saved if user refreshes
- Mobile-friendly input controls

```python
# src/web/routers/lead_magnet.py
class QuickEstimateRequest(BaseModel):
    filing_status: Literal["single", "married_jointly", "married_separately", "head_of_household"]
    income_range: Literal["under_50k", "50k_100k", "100k_200k", "200k_500k", "over_500k"]
    dependents: int = Field(ge=0, le=10)
    session_id: str

@router.post("/api/leads/quick-estimate")
async def quick_estimate(request: QuickEstimateRequest):
    # Calculate potential savings range
    savings = calculate_savings_teaser(
        filing_status=request.filing_status,
        income_range=request.income_range,
        dependents=request.dependents
    )

    # Create lead record (BROWSING state)
    lead_id = create_lead(
        session_id=request.session_id,
        tenant_id=get_tenant_id(),
        initial_data=request.dict()
    )

    return {
        "lead_id": lead_id,
        "savings_range": savings,  # {"min": 2400, "max": 4800}
        "opportunities": ["retirement_contributions", "itemized_deductions", "credits"],
        "next_step": "contact_capture"
    }
```

#### 1.3 Savings Teaser Page (8 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 1.3.1 | `src/web/templates/savings_teaser.html` | Teaser results page |
| 1.3.2 | Savings display | "You could save $2,400 - $4,800" |
| 1.3.3 | Opportunity cards | 3 top opportunities (icons + titles) |
| 1.3.4 | CPA introduction | Photo, name, credentials |
| 1.3.5 | Contact CTA | "Enter email to see full breakdown" |
| 1.3.6 | Urgency element | "Tax deadline: X days away" |

**Acceptance Criteria:**
- Savings displayed prominently
- CPA branding visible
- Clear CTA to capture contact
- No full details until contact captured

```html
<!-- Savings teaser structure -->
<div class="savings-reveal">
  <h2>Great news, {{ lead.first_name or 'there' }}!</h2>
  <div class="savings-amount">
    <span class="currency">$</span>
    <span class="range">{{ savings.min | format_currency }} - {{ savings.max | format_currency }}</span>
  </div>
  <p>in potential tax savings identified</p>
</div>

<div class="opportunities-preview">
  <h3>Top opportunities found:</h3>
  <div class="opportunity-card">🏠 Home Office Deduction</div>
  <div class="opportunity-card">💰 Retirement Contributions</div>
  <div class="opportunity-card">👶 Child Tax Credits</div>
  <div class="locked">+ 3 more opportunities (unlock with email)</div>
</div>

<div class="cpa-intro">
  <img src="{{ cpa.photo_url }}" class="cpa-photo">
  <div>
    <strong>{{ cpa.display_name }}</strong>
    <span>{{ cpa.credentials | join(", ") }}</span>
    <p>{{ cpa.years_experience }} years helping clients like you</p>
  </div>
</div>

<div class="contact-capture">
  <h3>See your complete tax savings breakdown</h3>
  <form id="contactForm">
    <input type="email" name="email" placeholder="Enter your email" required>
    <button type="submit">Unlock My Full Analysis →</button>
  </form>
  <p class="disclaimer">Your CPA will review your results and reach out within 24 hours</p>
</div>
```

#### 1.4 Contact Capture & Lead Creation (12 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 1.4.1 | Contact form component | Email (required), Phone (optional), Name (required) |
| 1.4.2 | Email validation | Real-time + server-side |
| 1.4.3 | `src/cpa_panel/lead_state/lead_state_machine.py` | Transition to EVALUATING |
| 1.4.4 | `src/database/lead_state_persistence.py` | Store contact info (encrypted) |
| 1.4.5 | Lead score calculation | Based on income + complexity |
| 1.4.6 | Success page | "Thanks! Your CPA will contact you within 24h" |

**Acceptance Criteria:**
- Email required, validated
- Lead state transitions to EVALUATING
- Contact info encrypted in database
- Lead score calculated and stored
- Success confirmation shown

```python
# src/cpa_panel/api/lead_routes.py
class ContactCaptureRequest(BaseModel):
    lead_id: str
    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    phone: Optional[str] = None

@router.post("/api/leads/{lead_id}/contact")
async def capture_contact(lead_id: str, request: ContactCaptureRequest):
    # Validate lead exists and belongs to tenant
    lead = get_lead(lead_id)
    verify_tenant_access(lead.tenant_id)

    # Encrypt PII before storage
    encrypted_email = encrypt_pii(request.email)
    encrypted_phone = encrypt_pii(request.phone) if request.phone else None

    # Update lead with contact info
    update_lead_contact(
        lead_id=lead_id,
        name=request.name,
        email=encrypted_email,
        phone=encrypted_phone
    )

    # Calculate lead score
    score = calculate_lead_score(lead)
    update_lead_score(lead_id, score)

    # Transition state
    transition_lead_state(lead_id, LeadState.EVALUATING)

    # Trigger CPA notification (async)
    notify_cpa_new_lead.delay(lead_id)

    return {
        "success": True,
        "message": "Your CPA will contact you within 24 hours",
        "next_url": f"/analysis/{lead_id}"
    }
```

#### 1.5 Full Analysis Unlock (8 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 1.5.1 | Redirect to full analysis after contact | Show complete breakdown |
| 1.5.2 | Include all opportunities | Not just top 3 |
| 1.5.3 | CPA contact info prominent | "Questions? Contact [CPA Name]" |
| 1.5.4 | Download/print option | PDF of analysis |
| 1.5.5 | Disclaimer display | Show advisory disclaimer clearly |

**Acceptance Criteria:**
- Full analysis only accessible after contact captured
- All tax opportunities displayed
- CPA contact info visible
- Disclaimer shown prominently

#### 1.6 Disclaimer Integration (8 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 1.6.1 | Add disclaimer to quick estimate | Before starting |
| 1.6.2 | Add disclaimer to savings teaser | Footer |
| 1.6.3 | Add disclaimer to full analysis | Header + footer |
| 1.6.4 | Create disclaimer component | Reusable across pages |
| 1.6.5 | T&C checkbox on contact capture | Required to submit |

**Acceptance Criteria:**
- Disclaimers visible at every step
- T&C acceptance required before contact submission
- Link to full T&C and Privacy Policy

---

## Sprint 2: CPA Dashboard MVP (Week 3-4)
**Duration:** 10 days | **Effort:** 80 hours

### Goals
- [ ] Build lead management interface for CPAs
- [ ] Display lead pipeline with key metrics
- [ ] Enable lead assignment and status updates
- [ ] Show lead details with tax profile

### Dashboard Layout
```
┌─────────────────────────────────────────────────────────────────┐
│ [Logo] My Lead Dashboard                    [CPA Name] [Logout] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ NEW     │ │CONTACTED│ │ ENGAGED │ │CONVERTED│ │ TOTAL   │  │
│  │   12    │ │    8    │ │    3    │ │    2    │ │  $4,200 │  │
│  │ leads   │ │ leads   │ │ leads   │ │ clients │ │ revenue │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Lead Pipeline                          [Filter ▼] [Search]│ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │ ☐ │ Name          │ Email         │ Income  │ Savings │ ⚡│ │
│  │───│───────────────│───────────────│─────────│─────────│───│ │
│  │ ☐ │ John Smith    │ j***@mail.com │ $85,000 │ $3,200  │ 82│ │
│  │ ☐ │ Sarah Johnson │ s***@mail.com │ $120,000│ $4,800  │ 91│ │
│  │ ☐ │ Mike Davis    │ m***@mail.com │ $65,000 │ $2,100  │ 68│ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  [Assign Selected] [Mark Contacted] [Export CSV]               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Tasks

#### 2.1 Dashboard Layout & Navigation (8 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 2.1.1 | `src/web/templates/cpa/dashboard.html` | Main dashboard template |
| 2.1.2 | `src/web/templates/cpa/base.html` | CPA portal base template |
| 2.1.3 | Navigation sidebar | Dashboard, Leads, Settings, Profile |
| 2.1.4 | Header with CPA info | Name, photo, logout |
| 2.1.5 | Mobile responsive layout | Collapsible sidebar |
| 2.1.6 | `src/web/routers/cpa_dashboard.py` | Dashboard router |

**Acceptance Criteria:**
- Clean, professional dashboard layout
- Mobile responsive
- Navigation works
- CPA branding applied

#### 2.2 Lead Pipeline Summary Cards (8 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 2.2.1 | Summary cards component | NEW, CONTACTED, ENGAGED, CONVERTED |
| 2.2.2 | `GET /api/cpa/dashboard/summary` | Endpoint for counts |
| 2.2.3 | Revenue card | Total from converted leads |
| 2.2.4 | Trend indicators | ↑12% vs last month |
| 2.2.5 | Click to filter | Click card to filter lead list |

**Acceptance Criteria:**
- Real-time counts from database
- Clickable cards filter lead list
- Revenue calculated from converted leads

```python
# src/cpa_panel/api/dashboard_routes.py
@router.get("/api/cpa/dashboard/summary")
async def get_dashboard_summary(cpa_id: str = Depends(get_current_cpa)):
    return {
        "new_leads": count_leads_by_state(cpa_id, LeadState.EVALUATING),
        "contacted": count_leads_by_state(cpa_id, LeadState.CONTACTED),
        "engaged": count_leads_by_state(cpa_id, LeadState.ENGAGED),
        "converted": count_leads_by_state(cpa_id, LeadState.CONVERTED),
        "total_revenue": sum_converted_lead_revenue(cpa_id),
        "leads_this_month": count_leads_this_month(cpa_id),
        "conversion_rate": calculate_conversion_rate(cpa_id),
    }
```

#### 2.3 Lead List Table (16 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 2.3.1 | Lead table component | Sortable, filterable |
| 2.3.2 | Columns: Name, Email (masked), Income, Savings, Score, Status, Date |
| 2.3.3 | `GET /api/cpa/leads` | Paginated lead list endpoint |
| 2.3.4 | Filters: Status, Date range, Score range |
| 2.3.5 | Search: By name or email |
| 2.3.6 | Sorting: By any column |
| 2.3.7 | Bulk selection | Checkbox column |
| 2.3.8 | Row click → Lead detail | Navigate to detail view |

**Acceptance Criteria:**
- Loads 50 leads in <1 second
- All filters work
- Pagination works
- Bulk selection works
- Click row opens detail

```python
# src/cpa_panel/api/lead_routes.py
class LeadListRequest(BaseModel):
    status: Optional[LeadState] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    search: Optional[str] = None
    sort_by: str = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"
    page: int = 1
    per_page: int = 50

@router.get("/api/cpa/leads")
async def list_leads(
    request: LeadListRequest = Depends(),
    cpa_id: str = Depends(get_current_cpa)
):
    leads, total = get_leads_for_cpa(
        cpa_id=cpa_id,
        filters=request.dict(exclude_none=True)
    )

    return {
        "leads": [
            {
                "id": lead.id,
                "name": lead.name,
                "email_masked": mask_email(decrypt_pii(lead.email)),
                "income_range": lead.income_range,
                "potential_savings": lead.potential_savings,
                "lead_score": lead.score,
                "status": lead.state.value,
                "created_at": lead.created_at.isoformat(),
                "last_activity": lead.last_activity.isoformat(),
            }
            for lead in leads
        ],
        "total": total,
        "page": request.page,
        "per_page": request.per_page,
        "total_pages": (total + request.per_page - 1) // request.per_page,
    }
```

#### 2.4 Lead Detail View (16 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 2.4.1 | `src/web/templates/cpa/lead_detail.html` | Lead detail page |
| 2.4.2 | Contact info section | Name, Email, Phone (with reveal button) |
| 2.4.3 | Tax profile section | Filing status, income, dependents, etc. |
| 2.4.4 | Savings breakdown | All identified opportunities |
| 2.4.5 | Activity timeline | State transitions, interactions |
| 2.4.6 | Action buttons | Mark Contacted, Send Email, Schedule Call |
| 2.4.7 | Notes section | CPA can add notes |
| 2.4.8 | `GET /api/cpa/leads/{lead_id}` | Full lead details endpoint |

**Acceptance Criteria:**
- Full contact info visible (with audit log)
- Complete tax profile shown
- All opportunities listed
- Activity history visible
- Actions functional

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Leads                           Lead Score: 85/100 ⭐  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────┐  ┌─────────────────────────────┐  │
│  │ Contact Information     │  │ Tax Profile                 │  │
│  │ ─────────────────────   │  │ ─────────────────────────   │  │
│  │ Name: John Smith        │  │ Filing: Married Jointly     │  │
│  │ Email: john@email.com   │  │ Income: $120,000            │  │
│  │ Phone: (555) 123-4567   │  │ Dependents: 2               │  │
│  │                         │  │ State: California           │  │
│  │ [📧 Send Email]         │  │ Complexity: Medium          │  │
│  │ [📞 Log Call]           │  │                             │  │
│  └─────────────────────────┘  └─────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Potential Savings: $4,200 - $5,800                      │   │
│  │ ───────────────────────────────────────────────────────  │   │
│  │ ✓ 401(k) Contribution Opportunity      $1,200 - $1,800  │   │
│  │ ✓ Child Tax Credit                     $2,000           │   │
│  │ ✓ Itemized Deductions                  $800 - $1,500    │   │
│  │ ✓ Education Credits                    $200 - $500      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Activity Timeline                                       │   │
│  │ ───────────────────────────────────────────────────────  │   │
│  │ 📅 Jan 24, 2:30 PM - Lead created (Quick Estimate)      │   │
│  │ 📅 Jan 24, 2:32 PM - Contact captured                   │   │
│  │ 📅 Jan 24, 3:00 PM - Assigned to you                    │   │
│  │ 📅 Jan 25, 10:00 AM - You marked as Contacted           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Mark as Engaged] [Convert to Client] [Archive Lead]          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.5 Lead Actions (12 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 2.5.1 | Mark as Contacted | Update state, log activity |
| 2.5.2 | Mark as Engaged | Update state, log activity |
| 2.5.3 | Convert to Client | Final state, prompt for revenue |
| 2.5.4 | Archive Lead | Soft delete from active pipeline |
| 2.5.5 | Add Note | Free-text note with timestamp |
| 2.5.6 | Bulk actions | Apply action to selected leads |

**Acceptance Criteria:**
- All state transitions work
- Activity logged for each action
- Bulk actions work
- Confirmation dialogs for destructive actions

```python
# src/cpa_panel/api/lead_routes.py
@router.post("/api/cpa/leads/{lead_id}/status")
async def update_lead_status(
    lead_id: str,
    new_status: LeadState,
    note: Optional[str] = None,
    revenue: Optional[float] = None,  # Required for CONVERTED
    cpa_id: str = Depends(get_current_cpa)
):
    lead = get_lead(lead_id)
    verify_lead_access(cpa_id, lead)

    if new_status == LeadState.CONVERTED and not revenue:
        raise HTTPException(400, "Revenue required for conversion")

    # Update state
    transition_lead_state(lead_id, new_status)

    # Log activity
    log_lead_activity(
        lead_id=lead_id,
        cpa_id=cpa_id,
        action=f"Status changed to {new_status.value}",
        note=note
    )

    # Update revenue if converted
    if revenue:
        update_lead_revenue(lead_id, revenue)

    return {"success": True, "new_status": new_status.value}
```

#### 2.6 Lead Assignment (8 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 2.6.1 | Unassigned leads view | Leads without CPA assignment |
| 2.6.2 | Assign to me button | Quick self-assignment |
| 2.6.3 | Assign to team member | Dropdown of CPAs in tenant |
| 2.6.4 | Auto-assignment rules | Optional: round-robin, by specialty |

**Acceptance Criteria:**
- CPAs can claim unassigned leads
- Admins can assign to any CPA
- Assignment logged in activity

#### 2.7 Basic Analytics (12 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 2.7.1 | Conversion funnel chart | Leads → Contacted → Engaged → Converted |
| 2.7.2 | Leads over time chart | Line chart, last 30 days |
| 2.7.3 | Lead source breakdown | Pie chart by source |
| 2.7.4 | Average time to contact | Metric card |
| 2.7.5 | `GET /api/cpa/analytics` | Analytics data endpoint |

**Acceptance Criteria:**
- Charts render correctly
- Data updates in real-time
- Date range filter works

---

## Sprint 3: Conversion Flow & Automation (Week 5-6)
**Duration:** 10 days | **Effort:** 64 hours

### Goals
- [ ] Automated notifications for CPAs
- [ ] Welcome email to leads
- [ ] Follow-up reminders
- [ ] Engagement letter integration

### Tasks

#### 3.1 CPA Notification System (12 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 3.1.1 | `src/notifications/cpa_notifications.py` | Notification service |
| 3.1.2 | New lead email | "New lead: John Smith, $4,200 potential" |
| 3.1.3 | High-value lead alert | Immediate notification for score >85 |
| 3.1.4 | Daily digest | Summary of new leads |
| 3.1.5 | In-app notifications | Badge on dashboard |
| 3.1.6 | Notification preferences | CPA can configure |

**Acceptance Criteria:**
- Email sent within 1 minute of lead capture
- High-value leads get immediate alert
- CPA can disable notifications

```python
# src/notifications/cpa_notifications.py
async def notify_new_lead(lead_id: str):
    lead = get_lead(lead_id)
    cpa = get_assigned_cpa(lead) or get_default_cpa(lead.tenant_id)

    # Send email
    await send_email(
        to=cpa.email,
        subject=f"New Lead: {lead.name} - ${lead.potential_savings:,.0f} potential savings",
        template="new_lead_notification",
        context={
            "cpa_name": cpa.display_name,
            "lead_name": lead.name,
            "income_range": lead.income_range,
            "potential_savings": lead.potential_savings,
            "lead_score": lead.score,
            "dashboard_url": f"{BASE_URL}/cpa/leads/{lead.id}"
        }
    )

    # Create in-app notification
    create_notification(
        cpa_id=cpa.id,
        type="new_lead",
        title=f"New lead: {lead.name}",
        message=f"Potential savings: ${lead.potential_savings:,.0f}",
        link=f"/cpa/leads/{lead.id}"
    )
```

#### 3.2 Lead Welcome Email (8 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 3.2.1 | `src/notifications/lead_emails.py` | Lead email service |
| 3.2.2 | Welcome email template | Branded, introduces CPA |
| 3.2.3 | Include savings summary | "You could save $X" |
| 3.2.4 | CPA contact info | Direct phone/email |
| 3.2.5 | Next steps | "Your CPA will contact you within 24h" |

**Acceptance Criteria:**
- Email sent immediately after contact capture
- Tenant branding applied
- CPA info included
- Unsubscribe link present

```html
<!-- Email template: welcome_lead.html -->
<div style="font-family: Arial, sans-serif; max-width: 600px;">
  <img src="{{ branding.logo_url }}" style="max-height: 50px;">

  <h1>Welcome, {{ lead.name }}!</h1>

  <p>Great news! Based on your quick tax assessment, we've identified
     <strong>${{ lead.potential_savings_min | format }} - ${{ lead.potential_savings_max | format }}</strong>
     in potential tax savings for you.</p>

  <div style="background: #f5f5f5; padding: 20px; border-radius: 8px;">
    <h3>Your Tax Advisor</h3>
    <img src="{{ cpa.photo_url }}" style="width: 60px; border-radius: 50%;">
    <p><strong>{{ cpa.display_name }}</strong></p>
    <p>{{ cpa.credentials | join(", ") }}</p>
    <p>📧 {{ cpa.email }} | 📞 {{ cpa.phone }}</p>
  </div>

  <h3>What's Next?</h3>
  <ol>
    <li>{{ cpa.first_name }} will review your tax profile</li>
    <li>You'll receive a call within 24 hours</li>
    <li>Together, you'll create a plan to maximize your savings</li>
  </ol>

  <p>Questions? Reply to this email or call {{ cpa.phone }} directly.</p>

  <hr>
  <p style="font-size: 12px; color: #666;">
    This is an estimate only and does not constitute tax advice.
    {{ branding.company_name }} | <a href="{{ unsubscribe_url }}">Unsubscribe</a>
  </p>
</div>
```

#### 3.3 Follow-up Reminder System (12 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 3.3.1 | `src/tasks/follow_up_tasks.py` | Background task scheduler |
| 3.3.2 | 24h reminder | "Lead not contacted in 24h" |
| 3.3.3 | 48h escalation | "Urgent: Lead waiting 48h+" |
| 3.3.4 | Lead stale warning | "Lead inactive for 7 days" |
| 3.3.5 | Dashboard task widget | Overdue follow-ups |

**Acceptance Criteria:**
- Reminders sent at configured intervals
- Escalation to admin if >48h
- Visible in dashboard

```python
# src/tasks/follow_up_tasks.py
from celery import Celery
from datetime import datetime, timedelta

@celery_app.task
def check_lead_follow_ups():
    """Run every hour to check for overdue follow-ups"""

    # Leads not contacted in 24h
    overdue_24h = get_leads_not_contacted_since(hours=24)
    for lead in overdue_24h:
        send_follow_up_reminder(lead, urgency="normal")

    # Leads not contacted in 48h - escalate
    overdue_48h = get_leads_not_contacted_since(hours=48)
    for lead in overdue_48h:
        send_follow_up_reminder(lead, urgency="urgent")
        escalate_to_admin(lead)

    # Leads inactive for 7 days - stale warning
    stale_leads = get_inactive_leads(days=7)
    for lead in stale_leads:
        send_stale_lead_warning(lead)
```

#### 3.4 Engagement Letter Integration (16 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 3.4.1 | Engagement letter template | Standard CPA engagement letter |
| 3.4.2 | Auto-populate from lead data | Name, services, fees |
| 3.4.3 | Generate PDF | From template |
| 3.4.4 | Send via email | Attachment or DocuSign link |
| 3.4.5 | E-signature integration | DocuSign or simple accept |
| 3.4.6 | Track signature status | Sent, Viewed, Signed |

**Acceptance Criteria:**
- Letter generates with correct data
- PDF looks professional
- E-signature works
- Status tracked in lead record

#### 3.5 Lead Nurture Sequence (8 hours)
**Priority:** P2

| Task | File | Action |
|------|------|--------|
| 3.5.1 | Day 3 email | "Still thinking about your tax savings?" |
| 3.5.2 | Day 7 email | "Tax deadline reminder" |
| 3.5.3 | Day 14 email | "Last chance: Your savings are waiting" |
| 3.5.4 | Sequence stops when contacted | Don't email after CPA contact |

**Acceptance Criteria:**
- Emails sent on schedule
- Sequence stops when lead status changes
- Unsubscribe works

#### 3.6 Activity Logging (8 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 3.6.1 | Log all email sends | Type, timestamp, status |
| 3.6.2 | Log all state changes | Old state, new state, who changed |
| 3.6.3 | Log CPA actions | View, contact, note, etc. |
| 3.6.4 | Display in lead timeline | Chronological activity feed |

**Acceptance Criteria:**
- All activities logged
- Visible in lead detail
- Exportable for compliance

---

## Sprint 4: Polish, Security & Launch (Week 7-8)
**Duration:** 10 days | **Effort:** 56 hours

### Goals
- [ ] Security hardening
- [ ] Performance optimization
- [ ] Documentation
- [ ] Beta launch preparation

### Tasks

#### 4.1 Security Audit & Fixes (16 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 4.1.1 | Run security scanner | OWASP ZAP or similar |
| 4.1.2 | Fix any HIGH/CRITICAL findings | As identified |
| 4.1.3 | Penetration test lead endpoints | Manual testing |
| 4.1.4 | Review all SQL queries | Check for injection |
| 4.1.5 | Audit PII access | Ensure encryption working |
| 4.1.6 | Test tenant isolation | Cross-tenant access attempts |

**Acceptance Criteria:**
- No HIGH/CRITICAL security findings
- All SQL parameterized
- PII encrypted in database
- Tenant isolation verified

#### 4.2 Performance Optimization (8 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 4.2.1 | Add database indexes | On frequently queried columns |
| 4.2.2 | Implement caching | For dashboard summary |
| 4.2.3 | Optimize lead list query | Pagination, lazy loading |
| 4.2.4 | Asset compression | Minify CSS/JS |
| 4.2.5 | Image optimization | Compress uploaded images |

**Acceptance Criteria:**
- Dashboard loads in <2 seconds
- Lead list loads 50 leads in <1 second
- Page size <500KB

```sql
-- Database indexes for lead queries
CREATE INDEX idx_leads_tenant_state ON leads(tenant_id, state);
CREATE INDEX idx_leads_tenant_created ON leads(tenant_id, created_at DESC);
CREATE INDEX idx_leads_tenant_score ON leads(tenant_id, score DESC);
CREATE INDEX idx_leads_assigned_cpa ON leads(assigned_cpa_id, state);
```

#### 4.3 Error Handling & Monitoring (8 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 4.3.1 | Sentry integration | Error tracking |
| 4.3.2 | Custom error pages | 404, 500 branded pages |
| 4.3.3 | Health check endpoint | `/health` for monitoring |
| 4.3.4 | Uptime monitoring | Pingdom or similar |
| 4.3.5 | Alert on errors | Slack/email notification |

**Acceptance Criteria:**
- All errors captured in Sentry
- Health check returns service status
- Alerts configured for downtime

```python
# src/web/routers/health.py
@router.get("/health")
async def health_check():
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "encryption": check_encryption_key(),
    }

    all_healthy = all(checks.values())

    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks,
        "version": APP_VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }
```

#### 4.4 Documentation (8 hours)
**Priority:** P1

| Task | File | Action |
|------|------|--------|
| 4.4.1 | CPA onboarding guide | How to set up account |
| 4.4.2 | Lead magnet setup guide | How to embed/link |
| 4.4.3 | Dashboard user guide | How to manage leads |
| 4.4.4 | API documentation | For integrations |
| 4.4.5 | Admin setup guide | Tenant configuration |

#### 4.5 Beta Launch Preparation (8 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 4.5.1 | Create demo tenant | For sales demos |
| 4.5.2 | Seed demo data | Realistic sample leads |
| 4.5.3 | Beta signup form | Collect interested CPAs |
| 4.5.4 | Feedback mechanism | In-app feedback button |
| 4.5.5 | Analytics setup | Track key metrics |

#### 4.6 Deployment Setup (8 hours)
**Priority:** P0

| Task | File | Action |
|------|------|--------|
| 4.6.1 | Create Dockerfile | Production-ready container |
| 4.6.2 | Create docker-compose.yml | For local testing |
| 4.6.3 | CI/CD pipeline | GitHub Actions for deploy |
| 4.6.4 | Environment configs | Staging vs production |
| 4.6.5 | Database migration script | Alembic setup |
| 4.6.6 | Backup automation | Daily database backups |

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Run migrations and start app
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.web.app:app --host 0.0.0.0 --port 8000"]
```

---

## Summary: 8-Week Timeline

| Week | Sprint | Key Deliverables | Hours |
|------|--------|------------------|-------|
| 1 | Sprint 0 + 1 (partial) | Security fixes, Lead magnet started | 40 |
| 2 | Sprint 1 (complete) | Lead magnet MVP live | 40 |
| 3 | Sprint 2 (partial) | Dashboard layout, Lead list | 40 |
| 4 | Sprint 2 (complete) | Lead detail, Actions | 40 |
| 5 | Sprint 3 (partial) | Notifications, Welcome email | 32 |
| 6 | Sprint 3 (complete) | Follow-ups, Engagement letter | 32 |
| 7 | Sprint 4 (partial) | Security audit, Performance | 28 |
| 8 | Sprint 4 (complete) | Docs, Deployment, Beta launch | 28 |

**Total: ~280 hours over 8 weeks**

---

## Success Criteria for Beta Launch

### Must Have (Week 8)
- [ ] Lead magnet captures email with 40%+ conversion
- [ ] CPA dashboard shows all leads with key data
- [ ] CPA can update lead status and add notes
- [ ] Welcome email sent to leads automatically
- [ ] CPA notification on new lead
- [ ] No critical security vulnerabilities
- [ ] 99% uptime during beta

### Nice to Have (Post-Beta)
- [ ] Engagement letter generation
- [ ] Lead nurture sequence
- [ ] Advanced analytics
- [ ] CRM integrations
- [ ] Mobile app

---

## Post-Launch Roadmap (Weeks 9-16)

### Month 3: Iterate on Feedback
- User interviews with beta CPAs
- Fix top 10 pain points
- Add most-requested features

### Month 4: Scale & Monetize
- Launch paid plans
- Add payment processing (Stripe)
- Usage-based billing
- Referral program

### Month 5-6: Expand
- CRM integrations (Salesforce, HubSpot)
- Advanced automation
- Multi-CPA firm support
- White-label reseller program

---

## Key Metrics to Track

| Metric | Target (Beta) | Target (Launch) |
|--------|---------------|-----------------|
| Lead capture rate | 40% | 50%+ |
| CPA login frequency | 3x/week | Daily |
| Lead contact rate (<24h) | 60% | 80% |
| Lead → Client conversion | 10% | 15%+ |
| CPA retention (monthly) | 80% | 90%+ |
| NPS score | 30+ | 50+ |

---

*This plan assumes 1 full-time developer. Adjust timeline if team is larger.*
