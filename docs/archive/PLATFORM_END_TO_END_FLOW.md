# COMPREHENSIVE PLATFORM FLOW DOCUMENTATION
## CA4CPA Global LLC - Multi-Tenant Tax Filing Platform

---

## TABLE OF CONTENTS

1. [User Roles & Permissions Architecture](#1-user-roles--permissions-architecture)
2. [API Route Structure](#2-api-route-structure)
3. [Lead Generation & Conversion Flow](#3-lead-generation--conversion-flow)
4. [Client Onboarding Flows](#4-client-onboarding-flows)
5. [Tax Return Workflow](#5-tax-return-workflow)
6. [Payment & Billing Flows](#6-payment--billing-flows)
7. [Notification System](#7-notification-system)
8. [Real-Time Collaboration Features](#8-real-time-collaboration-features)
9. [Appointment Scheduling System](#9-appointment-scheduling-system)
10. [Task Management System](#10-task-management-system)
11. [Deadline Management System](#11-deadline-management-system)
12. [Firm Impersonation (Admin Feature)](#12-firm-impersonation-admin-feature)
13. [White-Labeling Features](#13-white-labeling-features)
14. [Feature Access Control](#14-feature-access-control)
15. [Support & Ticketing System](#15-support--ticketing-system)
16. [Practice Intelligence](#16-practice-intelligence)
17. [System Architecture & Flows](#17-system-architecture--flows)
18. [Advanced Features](#18-advanced-features)
19. [Integration Points](#19-integration-points)
20. [Deployment Architecture](#20-deployment-architecture)
21. [Summary of Key Flows](#21-summary-of-key-flows)

---

## 1. USER ROLES & PERMISSIONS ARCHITECTURE

### 1.1 Role Hierarchy (8 Total Roles)

#### LEVEL 0: PLATFORM (CA4CPA Internal)
| Role | Description | Access Level |
|------|-------------|--------------|
| **SUPER_ADMIN** | Full platform access | Founders, CTO |
| **PLATFORM_ADMIN** | Platform operations management | Operations team |
| **SUPPORT** | Customer support & troubleshooting | Can impersonate firms |
| **BILLING** | Finance operations only | Billing team |

#### LEVEL 1: CPA FIRM (B2B Customers)
| Role | Description | Access Level |
|------|-------------|--------------|
| **PARTNER** | CPA firm owner/admin | Full firm control |
| **STAFF** | CPA firm employees | Delegated access |

#### LEVEL 2: CLIENT (B2B2C - All Clients)
| Role | Description | Access Level |
|------|-------------|--------------|
| **FIRM_CLIENT** | Taxpayer client of CPA firm | Managed by CPA |

> **NOTE:** This platform is B2B only. All clients belong to CPA firms.
> There is no direct B2C channel - all clients access through their CPA's portal.

### 1.2 Permission System (50+ Granular Permissions)

**Permission Categories:**

| Category | Permissions |
|----------|-------------|
| **Platform** | Firm management, subscription management, feature control, audit logs |
| **Firm** | Settings, branding, billing, analytics |
| **Team** | View, invite, manage, remove team members |
| **Client** | View own/all clients, create, edit, archive, assign |
| **Return** | View, create, edit, submit, review, approve, run scenarios |
| **Document** | View, upload, delete |
| **Self-Service** | View/edit own returns, upload documents |
| **Features** | Express Lane, Smart Tax, AI Chat, Scenarios, Projections, Integrations, API Access |

---

## 2. API ROUTE STRUCTURE

### 2.1 Core API (`/api/core`)
**Purpose**: Unified API for all user types

| Router | Functionality |
|--------|---------------|
| `auth_routes` | Login, register, magic-link, refresh, logout |
| `users_routes` | Profile management, preferences |
| `tax_returns_routes` | Return CRUD, submission, analytics |
| `documents_routes` | Upload, storage, verification |
| `scenarios_routes` | Tax planning what-if analysis |
| `recommendations_routes` | AI-powered tax recommendations |
| `billing_routes` | Subscriptions, invoices, payment methods |
| `messaging_routes` | Conversations, messages, notifications |
| `premium_reports_routes` | Tiered advisory reports |

### 2.2 CPA Panel API (`/api/cpa`)
**Purpose**: Advanced CPA firm operations

**30+ Domain Routers:**
```
workflow_routes        analysis_routes       notes_routes
insights_routes        lead_routes           exposure_routes
staff_routes           engagement_routes     client_visibility_routes
practice_intelligence_routes                 aggregated_insights_routes
optimizer_routes       scenario_routes       pipeline_routes
document_routes        pricing_routes        intake_routes
report_routes          data_routes           smart_onboarding_routes
lead_generation_routes lead_magnet_routes    client_portal_routes
notification_routes    payment_settings_routes
deadline_routes        task_routes           appointment_routes
invoice_routes         payment_link_routes   payments_routes
```

### 2.3 Admin Panel API (`/api/admin` & `/api/superadmin`)
**Purpose**: Firm and platform administration

**Admin Routes:**
- `dashboard_routes` - Firm analytics
- `team_routes` - Team management
- `billing_routes` - Subscription management
- `settings_routes` - Firm configuration
- `auth_routes` - Admin authentication
- `compliance_routes` - Compliance tracking
- `client_routes` - Client management
- `workflow_routes` - Workflow configuration
- `alert_routes` - Alert management
- `rbac_routes` - Role-based access control
- `ticket_routes` - Support ticket management

**Superadmin Routes:**
- Multi-firm management (impersonate, manage)
- Subscription oversight and adjustments
- Feature flag management
- System health monitoring
- Platform billing and metrics

---

## 3. LEAD GENERATION & CONVERSION FLOW

### 3.1 Lead Generation Stages

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROSPECT DISCOVERY                           │
├─────────────────────────────────────────────────────────────────┤
│  1. Quick tax savings estimate form (filing status + income)    │
│  2. Document upload (1040 PDF/image) with OCR parsing           │
│  3. AI-powered teaser calculation (shows savings range)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LEAD CAPTURE                               │
├─────────────────────────────────────────────────────────────────┤
│  1. Prospect provides contact info (email, phone, name)         │
│  2. Unlocks full analysis and recommendations                   │
│  3. Lead record created with status: NEW                        │
└─────────────────────────────────────────────────────────────────┘
```

**Lead Status Flow:**
```
NEW → QUALIFIED → CONTACTED → ENGAGED → CONVERTED
                                    ↓
                                  LOST
```

**Lead Priorities:**
| Priority | Criteria |
|----------|----------|
| HIGH | 80+ savings potential score |
| MEDIUM | 50-79 savings potential score |
| LOW | Below 50 savings potential score |

**Lead Sources:**
- `website` - Direct website visit
- `referral` - Referred by existing client
- `calculator` - Used savings calculator
- `document_upload` - Uploaded tax documents
- `quick_estimate` - Quick estimate form
- `campaign` - Marketing campaign
- `direct` - Direct outreach

### 3.2 Lead Management (CPA-Facing)

| Feature | Description |
|---------|-------------|
| Pipeline View | Summary of all leads by stage |
| Lead Queue | Visible, monetizable, priority queues |
| Lead Assignment | Assign to specific CPA |
| Lead Conversion | Convert prospect to client |
| Lead Signals | Engagement tracking system |

### 3.3 Lead Magnet Strategy
- Smart tax advisory offers as lead generation
- Multi-stage nurture campaign
- Email follow-up automation
- Real-time lead scoring and prioritization

---

## 4. CLIENT ONBOARDING FLOWS

### 4.1 60-Second Smart Onboarding

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Start Session   │────▶│  Upload Document │────▶│  OCR Extraction  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                                           │
                                                           ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Create Client   │◀────│ Instant Analysis │◀────│ Smart Questions  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

**Components:**
| Component | Function |
|-----------|----------|
| Form 1040 Parser | OCR-based document extraction |
| AI Question Generator | Conditional questions based on profile |
| Benefit Estimator | Credits, deductions, strategies analysis |
| Instant Analysis Engine | Real-time savings calculation |

### 4.2 Client Portal (B2C Access)

| Feature | Description |
|---------|-------------|
| Dashboard | Returns overview |
| Documents | Request/upload capability |
| Returns | View filed returns, download copies |
| Messaging | Direct communication with CPA |
| Billing | Invoice payment |
| Profile | Account management |
| Notifications | Real-time alerts |

---

## 5. TAX RETURN WORKFLOW

### 5.1 Return Lifecycle States

```
DRAFT → SUBMITTED → IN_REVIEW → APPROVED → FILED → ARCHIVED
```

### 5.2 Return Processing

| Stage | Actions |
|-------|---------|
| Creation | Start new return (document-first or guided) |
| Data Entry | Input income, deductions, credits |
| Scenario Analysis | What-if tax planning |
| Delta Analysis | Compare returns over time |
| Tax Drivers | Identify key factors impacting tax |
| Review Queue | CPA review and approval |
| Approval | CPA approves for filing |
| Filing Package | Generate package for external e-filing |
| Archive | Post-filing storage |

> **NOTE:** This platform does NOT e-file directly with IRS. CPAs use the
> generated filing package with their preferred external e-filing software.

### 5.3 CPA Review Features
- Internal review notes
- Review checklist/insights
- Client communication
- Revision requests
- Approval certificate generation

---

## 6. PAYMENT & BILLING FLOWS

### 6.1 Platform Subscription Tiers

| Tier | Features |
|------|----------|
| **FREE** | Dashboard, documents, basic calculations |
| **STARTER** | Express lane, smart tax, scenarios, projections |
| **PROFESSIONAL** | AI chat, custom branding, team collaboration |
| **ENTERPRISE** | API access, webhooks, advanced security |
| **WHITE_LABEL** | Complete white-label, custom domain, full customization |

### 6.2 CPA-to-Client Payment Flow (Stripe Connect)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Create Invoice  │────▶│  Send to Client │────▶│ Client Receives │
│ (Line Items)    │     │                 │     │ Payment Link    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ CPA Receives    │◀────│ Platform Fee    │◀────│ Client Pays     │
│ Net Amount      │     │ (2.9% + $0.30)  │     │ via Stripe      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Payment Methods:**
- Stripe card payments
- Offline payment tracking (check, cash)
- Reusable payment links (custom or fixed amount)

**Invoice Statuses:**
```
DRAFT → SENT → VIEWED → PARTIALLY_PAID → PAID
                              ↓
                           OVERDUE
                              ↓
                         VOID/CANCELLED
```

---

## 7. NOTIFICATION SYSTEM

### 7.1 Real-Time Events (WebSocket)

| Category | Event Types |
|----------|-------------|
| Connection | CONNECTED, DISCONNECTED, HEARTBEAT |
| Notification | NOTIFICATION, NOTIFICATION_READ |
| Return | RETURN_STATUS_CHANGED, RETURN_UPDATED |
| Document | DOCUMENT_UPLOADED, DOCUMENT_PROCESSED |
| Appointment | APPOINTMENT_BOOKED, CANCELLED, REMINDER |
| Task | TASK_ASSIGNED, COMPLETED, UPDATED |
| Deadline | DEADLINE_APPROACHING, OVERDUE |
| Lead | LEAD_CAPTURED, CONVERTED |
| Client | CLIENT_MESSAGE, CLIENT_ACTIVITY |
| System | SYSTEM_ANNOUNCEMENT, MAINTENANCE_SCHEDULED |
| Collaboration | USER_JOINED_SESSION, RESOURCE_LOCKED |

**Event Targeting:**
| Target | Scope |
|--------|-------|
| Firm-wide | All users in a firm |
| User-specific | Individual user |
| Session-specific | Active session only |

**Priority Levels:** LOW, NORMAL, HIGH, URGENT

### 7.2 Multi-Channel Notification Delivery

| Channel | Provider |
|---------|----------|
| In-app | WebSocket real-time |
| Email | SendGrid, SES, SMTP |
| SMS | Configured (ready) |
| Push | Configured (ready) |

**Email Triggers:**
- Return status changes
- Document requests
- New leads captured
- Task assignments
- Deadline reminders
- Client messages
- Appointment notifications

**Notification Preferences:**
- Email new leads toggle
- Hot lead immediate notification (score > 80)
- Daily digest option
- Follow-up reminders
- In-app notifications toggle
- Custom digest time

---

## 8. REAL-TIME COLLABORATION FEATURES

### 8.1 WebSocket Connection Manager
- Maintains active client connections
- Routes events based on permissions
- Broadcast, targeted, and session-specific delivery
- Heartbeat/health check mechanism

### 8.2 Live Session Updates
- Multi-user editing on same return
- Resource locking (prevent simultaneous edits)
- Activity streaming to team members
- Concurrent document processing

### 8.3 Team Collaboration
- Internal notes and discussion threads
- Task assignment and tracking
- Review queues
- Activity feeds
- Audit trail of changes

---

## 9. APPOINTMENT SCHEDULING SYSTEM

### 9.1 CPA Availability Management

| Setting | Description |
|---------|-------------|
| Availability Windows | By day of week |
| Buffer Time | Between appointments |
| Booking Advance | Minimum notice required |
| Blocked Dates | Unavailable dates |
| Duration | Appointment length options |
| Meeting Link | Video conference URL |
| Location | Office address/phone |

### 9.2 Client Booking Flow

```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│ View Available │────▶│ Select Time    │────▶│ Confirm        │
│ Slots          │     │ Slot           │     │ Booking        │
└────────────────┘     └────────────────┘     └────────────────┘
                                                      │
                                                      ▼
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│ Attend         │◀────│ Get Reminders  │◀────│ Receive        │
│ Appointment    │     │ (24-48h)       │     │ Confirmation   │
└────────────────┘     └────────────────┘     └────────────────┘
```

### 9.3 Appointment Statuses

```
PENDING → CONFIRMED → COMPLETED
                  ↓
              NO_SHOW / CANCELLED
```

### 9.4 Reminders
| Type | Timing |
|------|--------|
| Email | 24-48 hours before |
| SMS | Configurable |
| In-app | Real-time |
| Push | Configurable |

---

## 10. TASK MANAGEMENT SYSTEM

### 10.1 Task Creation & Assignment

| Field | Description |
|-------|-------------|
| Title | Task name |
| Description | Detailed instructions |
| Assignee | Specific user |
| Priority | Low, Normal, High, Urgent |
| Due Date | Deadline |
| Client Link | Associated client |
| Session Link | Associated tax session |
| Deadline Link | Associated deadline |
| Parent Task | For subtask hierarchy |
| Estimated Hours | Time estimate |
| Category | Task classification |

### 10.2 Task Lifecycle

```
UNASSIGNED → ASSIGNED → IN_PROGRESS → COMPLETED
                              ↓
                           BLOCKED
```

**Additional Features:**
- Comments and internal notes
- Checklist items tracking
- Block/unblock for dependencies

### 10.3 Team Views

| View | Purpose |
|------|---------|
| My Tasks | Personal task list |
| Unassigned | Tasks needing assignment |
| Overdue | Past due tasks |
| Kanban Board | Visual workflow |
| Team Workload | Capacity analytics |

---

## 11. DEADLINE MANAGEMENT SYSTEM

### 11.1 Deadline Types

| Type | Description |
|------|-------------|
| Federal Income Tax | April 15 |
| Estimated Quarterly | Q1-Q4 deadlines |
| State Tax | Varies by state |
| Sales Tax | Monthly/quarterly |
| Payroll | Per pay period |
| IRS Deadlines | Various IRS filings |
| Custom | User-defined |

### 11.2 Deadline Tracking

| Feature | Description |
|---------|-------------|
| Create Deadline | With tax year |
| Assign | To team members |
| Priority | Urgency level |
| Extensions | File extension tracking |
| Reminders | Automatic generation |
| Calendar | Visual date views |
| Alerts | Upcoming/overdue notifications |

### 11.3 Reminder Schedule

| Days Before | Channel |
|-------------|---------|
| 90 days | Email |
| 60 days | Email |
| 30 days | Email |
| 14 days | Email + In-app |
| 7 days | Email + In-app |
| 3 days | Email + In-app + SMS |
| 1 day | All channels |

---

## 12. FIRM IMPERSONATION (Admin Feature)

### 12.1 Support Impersonation

| Role | Capability |
|------|------------|
| SUPPORT | Impersonate for troubleshooting |
| PLATFORM_ADMIN | Impersonate any firm |

**Features:**
- Full audit log of sessions
- Time-limited sessions
- View and interact as target role
- Testing without affecting real data

### 12.2 Access Control
- Only users with `platform_impersonate` permission
- Requires justification/reason
- Full audit trail of actions taken
- Session timeout protection
- Session extension capability
- Revocation support

---

## 13. WHITE-LABELING FEATURES

### 13.1 Tenant-Level Branding

**Customizable Elements:**

| Category | Elements |
|----------|----------|
| Identity | Platform name, tagline, company name, contact info |
| Colors | Primary, secondary, accent, text, background |
| Logo | Light and dark variants |
| Assets | Favicon, background images |
| Typography | Font family and sizing |
| Email | Header, footer branding |
| Social | Social media links |
| Legal | Privacy/terms URLs |

**Theme Presets:**
- Professional Blue
- Modern Green
- Corporate Gray
- Boutique Purple
- Classic Navy
- Custom

### 13.2 Advanced Customization
- Custom CSS/JavaScript injection
- Custom head HTML (for analytics)
- SEO customization (meta tags, keywords)
- Show/hide "Powered by" branding
- Custom domains (Enterprise tier)
- Custom email domains
- Billing address and terms customization

### 13.3 Sub-Branding (CPA-Level)
- Individual CPAs can customize within firm branding
- Personal logo and colors (if allowed by firm)
- Custom intro messaging
- Personal website links

### 13.4 Subscription Tier Gating

| Feature | FREE | STARTER | PROFESSIONAL | ENTERPRISE | WHITE_LABEL |
|---------|:----:|:-------:|:------------:|:----------:|:-----------:|
| Custom Branding | - | - | ✓ | ✓ | ✓ |
| Custom Domain | - | - | - | ✓ | ✓ |
| Remove Branding | - | - | - | - | ✓ |
| Custom CSS | - | - | - | ✓ | ✓ |

---

## 14. FEATURE ACCESS CONTROL

### 14.1 Feature Gates

**Filing Features:**
| Feature | Description |
|---------|-------------|
| Express Lane | 3-minute document-first filing |
| Smart Tax | Adaptive question-based filing |
| Guided Filing | Step-by-step assistance |
| Filing Package | Generate package for CPA to e-file externally |

**AI Features:**
| Feature | Description |
|---------|-------------|
| AI Tax Chat | Conversational AI assistance |
| Intelligent Suggestions | AI-powered recommendations |
| Document AI | Classification & extraction |

**Analysis Features:**
| Feature | Description |
|---------|-------------|
| Scenario Explorer | What-if analysis |
| Tax Projections | 5-year planning |
| Delta Analysis | Year-over-year comparison |
| Tax Drivers | Key factor identification |

**Integration Features:**
| Feature | Description |
|---------|-------------|
| QuickBooks | Accounting sync |
| Plaid | Financial data |
| API Access | Programmatic access |
| Webhooks | Event notifications |

**Collaboration Features:**
| Feature | Description |
|---------|-------------|
| Client Portal | Client self-service |
| Team Collaboration | Multi-user workflow |
| Client Messaging | Direct communication |
| Audit Logs | Activity tracking |

**Admin Features:**
| Feature | Description |
|---------|-------------|
| User Management | User CRUD |
| RBAC Configuration | Role management |
| Advanced Security | 2FA, IP whitelist, SSO |

### 14.2 Access Determination

```
┌─────────────────────────────────────────────────────────────────┐
│                    ACCESS CHECK FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Subscription tier check                                     │
│  2. Feature flag enablement                                     │
│  3. User role validation                                        │
│  4. Permission verification                                     │
│  5. Ownership/assignment requirements                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 15. SUPPORT & TICKETING SYSTEM

### 15.1 Ticket Creation

| Source | Method |
|--------|--------|
| Web | Self-service form |
| Email | Email integration |
| API | Programmatic submission |
| Phone | Manual entry |
| Auto | Automated assignment |

### 15.2 Ticket Management

**Categories:** billing, technical, feature_request, bug, other

**Priorities:** low, normal, high, urgent

**Status Flow:**
```
OPEN → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
                                    ↓
                                 REOPENED
```

### 15.3 Ticket Features

| Feature | Description |
|---------|-------------|
| Communication | Customer thread |
| Internal Notes | Agent-only comments |
| Reassignment | Transfer to different agent |
| Category Change | Reclassification |
| Priority Change | Urgency adjustment |
| Satisfaction Rating | 1-5 star rating |
| SLA Tracking | Response time monitoring |
| Escalation | Priority escalation paths |

### 15.4 Agent Dashboard
- Unassigned tickets
- Ticket queue by priority
- Performance metrics
- Response time tracking

---

## 16. PRACTICE INTELLIGENCE

### 16.1 Three Core Metrics Only

| Metric | Description |
|--------|-------------|
| Clients by Status | Breakdown of client stages |
| Returns in Progress | Pipeline view |
| Opportunities Dashboard | Aggregate savings potential |

### 16.2 Purpose
- High-level firm analytics
- No detailed reporting (upgrade for Advanced Analytics)
- Performance monitoring
- Real recommendation engine driving insights

---

## 17. SYSTEM ARCHITECTURE & FLOWS

### 17.1 Authentication

| Method | Description |
|--------|-------------|
| JWT Token | Bearer token authentication |
| Magic Link | Email-based passwordless login |
| Email/Password | Traditional login |
| Token Refresh | Session extension |
| RBAC Enforcement | Role-based access |

### 17.2 Multi-Tenancy

```
┌─────────────────────────────────────────────────────────────────┐
│                    TENANT ISOLATION                             │
├─────────────────────────────────────────────────────────────────┤
│  • Data partitioning by firm_id                                 │
│  • Subscription tier constraints                                │
│  • Feature flag evaluation per tenant                           │
│  • Custom branding per tenant                                   │
│  • Separate admin contexts                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 17.3 Data Models

**Key Entities:**

| Entity | Description |
|--------|-------------|
| User/CPA Profile | User account data |
| Firm (Tenant) | Organization/company |
| Client | Taxpayer record |
| Tax Return Session | Filing session |
| Document | Uploaded files |
| Scenario | What-if analysis |
| Recommendation | AI suggestions |
| Notification | Alerts and messages |
| Task | Work items |
| Deadline | Due dates |
| Appointment | Scheduled meetings |
| Invoice/Payment | Billing records |
| Lead | Prospect data |
| Support Ticket | Help requests |

### 17.4 Audit & Compliance

| Feature | Description |
|---------|-------------|
| Audit Logging | Complete activity trail |
| Activity Tracking | User behavior monitoring |
| Feature Analytics | Usage metrics |
| Error Tracking | Exception monitoring |
| Compliance Reports | Regulatory reporting |
| RBAC Logs | Access control audit |

---

## 18. ADVANCED FEATURES

### 18.1 Tax Optimization

| Analysis Type | Description |
|---------------|-------------|
| Credit Analysis | Child tax credit, EITC, education credits |
| Deduction Analysis | Itemized vs. standard, business deductions |
| Filing Status Comparison | Single, MFJ, MFS, HOH |
| Entity Comparison | S-corp, LLC, sole proprietor |
| Strategy Analysis | Retirement contributions, business structure |

### 18.2 Lead Scoring & Prioritization

| Factor | Weight |
|--------|--------|
| Savings Potential | High |
| Engagement Score | Medium |
| Conversion Probability | Medium |
| Lead Quality Signals | Variable |

### 18.3 Nurture Automation
- Email campaign sequences
- Lead scoring progression
- Automated follow-up reminders
- Activity tracking
- Conversion path optimization

---

## 19. INTEGRATION POINTS

### 19.1 External Services

| Service | Purpose |
|---------|---------|
| Stripe | Payments (Connect + direct) |
| SendGrid/SES/SMTP | Email delivery |
| OCR Service | Document processing |
| AI/ML Service | Recommendations engine |
| Plaid | Financial data aggregation |
| QuickBooks | Accounting sync |

### 19.2 Webhooks
- Real-time event delivery
- Custom integrations
- Third-party notifications
- Pipeline triggers

---

## 20. DEPLOYMENT ARCHITECTURE

### 20.1 API Servers

| Server | Purpose |
|--------|---------|
| Core API | Unified for all users |
| CPA Panel API | Advanced CPA features |
| Admin Panel API | Firm administration |
| Superadmin API | Platform administration |

### 20.2 Services

| Service | Technology |
|---------|------------|
| Database | PostgreSQL/MySQL |
| Cache | Redis |
| Email | SendGrid/SES |
| File Storage | S3/Cloud Storage |
| WebSocket | Real-time server |
| Background Jobs | Celery |

### 20.3 Health Checks
- Per-module health endpoints
- Service availability monitoring
- Dependency checking

---

## 21. SUMMARY OF KEY FLOWS

> **IMPORTANT:** This platform is B2B only. All clients belong to CPA firms.
> There is no direct B2C channel.

### B2B2C Flow (CPA Firm Client)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ CPA Creates │────▶│ Client Gets │────▶│ Client      │
│ Client      │     │ Invitation  │     │ Completes   │
└─────────────┘     └─────────────┘     │ Tax Info    │
                                        └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Client      │◀────│ CPA Files   │◀────│ CPA Reviews │
│ Portal      │     │ Externally  │     │ & Approves  │
│ Access      │     │ (e-file)    │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
                          ▲
                          │
                    Filing Package
                    Generated by
                    Platform
```

> **Filing Note:** Platform generates filing packages. CPA uses their preferred
> external e-filing software (ProSeries, Lacerte, Drake, etc.) to file with IRS.

### B2B Flow (Lead to Client)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Prospect    │────▶│ System      │────▶│ Prospect    │
│ Uploads Doc │     │ Shows       │     │ Provides    │
│             │     │ Teaser      │     │ Contact     │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Normal      │◀────│ CPA         │◀────│ Lead        │
│ Onboarding  │     │ Converts    │     │ Created in  │
│ Flow        │     │ to Client   │     │ Pipeline    │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## APPENDIX: API ENDPOINT REFERENCE

### Core API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/core/auth/login` | User login |
| POST | `/api/core/auth/register` | User registration |
| POST | `/api/core/auth/magic-link` | Magic link auth |
| GET | `/api/core/users/me` | Get current user |
| GET | `/api/core/tax-returns` | List returns |
| POST | `/api/core/tax-returns` | Create return |
| GET | `/api/core/documents` | List documents |
| POST | `/api/core/documents/upload` | Upload document |
| GET | `/api/core/scenarios` | List scenarios |
| POST | `/api/core/scenarios` | Create scenario |

### CPA Panel Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cpa/leads` | List leads |
| POST | `/api/cpa/leads/{id}/convert` | Convert lead |
| GET | `/api/cpa/clients` | List clients |
| POST | `/api/cpa/clients` | Create client |
| GET | `/api/cpa/invoices` | List invoices |
| POST | `/api/cpa/invoices` | Create invoice |
| GET | `/api/cpa/tasks` | List tasks |
| POST | `/api/cpa/tasks` | Create task |
| GET | `/api/cpa/deadlines` | List deadlines |
| GET | `/api/cpa/appointments` | List appointments |

### Admin Panel Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/dashboard` | Dashboard data |
| GET | `/api/admin/team` | Team members |
| POST | `/api/admin/team/invite` | Invite member |
| GET | `/api/admin/billing` | Billing info |
| GET | `/api/admin/settings` | Firm settings |
| PUT | `/api/admin/settings` | Update settings |

### Superadmin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/superadmin/firms` | List all firms |
| POST | `/api/superadmin/firms/{id}/impersonate` | Start impersonation |
| GET | `/api/superadmin/subscriptions` | All subscriptions |
| GET | `/api/superadmin/feature-flags` | Feature flags |
| GET | `/api/superadmin/health` | System health |

---

*Document generated: 2026-01-28*
*Platform Version: 1.0*
