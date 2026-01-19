# Product Team Training: Tax Decision Intelligence Platform

## Complete Onboarding Guide for Domain & Product Expertise

**Version:** 1.0
**Last Updated:** January 2026
**Audience:** Product Team, Engineering, Domain Experts

---

## Table of Contents

1. [Platform Vision & Identity](#part-1-platform-vision--identity)
2. [What We Are NOT](#part-2-what-we-are-not)
3. [Domain Knowledge: CPA Workflow](#part-3-domain-knowledge-cpa-workflow)
4. [Tax Intelligence Fundamentals](#part-4-tax-intelligence-fundamentals)
5. [The Three Portals](#part-5-the-three-portals)
6. [Role-Based Access Control (RBAC)](#part-6-role-based-access-control-rbac)
7. [Technical Architecture](#part-7-technical-architecture)
8. [Database Schema & Data Flow](#part-8-database-schema--data-flow)
9. [Key Features Deep Dive](#part-9-key-features-deep-dive)
10. [Current State & Capabilities](#part-10-current-state--capabilities)
11. [Scope Boundaries](#part-11-scope-boundaries)
12. [Product Roadmap](#part-12-product-roadmap)

---

## Part 1: Platform Vision & Identity

### The Core Value Proposition

**We are a Tax Decision Intelligence Platform** - a pre-return advisory engine that transforms how CPAs deliver value to their clients.

```
THE FUNDAMENTAL SHIFT:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  TRADITIONAL CPA WORKFLOW          OUR PLATFORM ENABLES                │
│  ────────────────────────          ────────────────────                │
│                                                                         │
│  Client → Documents → Data Entry   Client → Intelligence → Decisions  │
│     ↓                                   ↓                              │
│  Calculation → File → Done         "What if we..." scenarios          │
│                                         ↓                              │
│  "Here's your refund"              "Here's how to optimize"           │
│                                         ↓                              │
│  Annual interaction                 Advisory relationship              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Our Mission

**Transform CPAs from compliance processors into strategic advisors** by:

1. **Automating the mundane** - Document intake, data extraction, calculations
2. **Surfacing opportunities** - Tax savings the CPA might miss
3. **Enabling advisory conversations** - Client-facing reports and scenarios
4. **Productizing expertise** - Turn tribal knowledge into repeatable workflows

### The Three Problems We Solve

| Problem | Traditional Pain | Our Solution |
|---------|-----------------|--------------|
| **Pre-Return Decision Chaos** | Clients make tax-impacting decisions without CPA input | Real-time scenario modeling |
| **Data Quality Bottleneck** | CPAs spend 60% of time on data entry | AI-powered document extraction |
| **Non-Productized Advisory** | Advisory happens in CPAs' heads, not delivered to clients | Automated recommendation engine |

### Our Market Position

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     TAX TECHNOLOGY LANDSCAPE                            │
│                                                                         │
│  TAX PREP SOFTWARE        PRACTICE MGMT         US (INTELLIGENCE)      │
│  ─────────────────        ─────────────         ─────────────────      │
│  • TurboTax               • Karbon              • Decision Engine       │
│  • Drake                  • Canopy              • Scenario Modeling     │
│  • UltraTax              • Jetpack             • Advisory Amplifier    │
│  • ProConnect                                   • Client Intelligence   │
│                                                                         │
│  "Enter data, file"       "Track time,          "What decisions        │
│                            manage workflow"      optimize taxes?"       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Part 2: What We Are NOT

### Critical Identity Boundaries

Understanding what we are NOT is as important as understanding what we are.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       PLATFORM IDENTITY BOUNDARIES                      │
│                                                                         │
│  WE ARE NOT:                                                            │
│                                                                         │
│  ❌ Tax Preparation Software                                            │
│     - We don't file returns with the IRS                               │
│     - We don't compete with Drake, UltraTax, ProConnect                │
│     - We are a PRE-FILING intelligence layer                           │
│                                                                         │
│  ❌ Practice Management System                                          │
│     - We don't track billable hours                                    │
│     - We don't manage staff productivity                               │
│     - We don't do WIP tracking or time management                      │
│     - Partners: Karbon, Canopy, Jetpack                                │
│                                                                         │
│  ❌ Consumer Tax Product                                                │
│     - We don't serve DIY tax filers                                    │
│     - We don't compete with TurboTax, H&R Block                        │
│     - We are B2B: We serve CPAs who serve taxpayers                    │
│                                                                         │
│  ❌ E-Filing Platform                                                   │
│     - We don't transmit returns to IRS/states                          │
│     - We don't have e-file authorization                               │
│     - Export to existing e-file providers                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why This Matters

When building features, always ask:

1. Does this help CPAs **make better decisions**? ✅
2. Does this help CPAs **advise clients better**? ✅
3. Does this **track time or manage practice**? ❌ Out of scope
4. Does this **file returns**? ❌ Out of scope
5. Does this serve **DIY consumers**? ❌ Out of scope

---

## Part 3: Domain Knowledge: CPA Workflow

### The Tax Season Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ANNUAL CPA-CLIENT LIFECYCLE                          │
│                                                                         │
│  JAN-APR: TAX SEASON (COMPLIANCE CRUNCH)                               │
│  ─────────────────────────────────────────                              │
│  • Receive documents from clients                                       │
│  • Data entry into tax software                                         │
│  • Calculations and review                                              │
│  • Client meetings for signatures                                       │
│  • Filing deadlines (Apr 15, extensions)                               │
│                                                                         │
│  MAY-AUG: EXTENSION SEASON                                             │
│  ────────────────────────────                                           │
│  • Complete extended returns (Oct 15)                                   │
│  • Begin tax planning conversations                                     │
│  • Quarterly estimate reminders                                         │
│                                                                         │
│  SEP-DEC: PLANNING SEASON (HIGH-VALUE ADVISORY)                        │
│  ──────────────────────────────────────────────                         │
│  • Year-end tax planning                                                │
│  • Retirement contribution decisions                                    │
│  • Entity structure analysis                                            │
│  • Capital gain/loss harvesting                                         │
│  • Charitable giving strategies                                         │
│                                                                         │
│  WHERE WE ADD MOST VALUE: ↑ PLANNING SEASON                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Firm Team Roles

Understanding who uses our platform:

| Role | Responsibilities | Our Platform Value |
|------|-----------------|-------------------|
| **Firm Owner/Partner** | Strategy, client relationships, high-value advisory | Portfolio analytics, advisory reports |
| **Firm Admin** | Team management, billing, operations | Admin panel, team permissions |
| **Senior Preparer** | Complex returns, mentor juniors, quality review | Scenario modeling, optimization |
| **Preparer** | Return preparation, data entry, basic scenarios | Guided workflows, automation |
| **Reviewer** | Quality assurance, approve/reject returns | Review queue, compliance checks |

### Client Complexity Tiers

```
COMPLEXITY TIER DISTRIBUTION:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  TIER 1: SIMPLE (30%)                                                   │
│  • W-2 income only                                                      │
│  • Standard deduction                                                   │
│  • Income < $75K                                                        │
│  • Typical fee: $150-300                                                │
│                                                                         │
│  TIER 2: MODERATE (35%)                                                 │
│  • W-2 + investment income                                              │
│  • May itemize deductions                                               │
│  • Income $75K-200K                                                     │
│  • Typical fee: $300-600                                                │
│                                                                         │
│  TIER 3: COMPLEX (20%)                                                  │
│  • Self-employment or rental income                                     │
│  • Multiple states                                                      │
│  • Income $200K-500K                                                    │
│  • Typical fee: $600-1,500                                              │
│                                                                         │
│  TIER 4: HIGH NET WORTH (10%)                                           │
│  • Business owners, investors                                           │
│  • Entity structuring needs                                             │
│  • Income $500K-1M                                                      │
│  • Typical fee: $1,500-5,000                                            │
│                                                                         │
│  TIER 5: ULTRA COMPLEX (5%)                                             │
│  • Multi-entity structures                                              │
│  • International considerations                                         │
│  • Income > $1M                                                         │
│  • Typical fee: $5,000+                                                 │
│                                                                         │
│  OUR SWEET SPOT: Tiers 3-5 (where advisory value is highest)           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Part 4: Tax Intelligence Fundamentals

### The Scenario Types We Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     TAX SCENARIO CATALOG                                │
│                                                                         │
│  1. FILING STATUS OPTIMIZATION                                          │
│     Compare: Single vs MFJ vs MFS vs HOH vs QSS                        │
│     Impact: Tax brackets, standard deduction, credit eligibility       │
│                                                                         │
│  2. WHAT-IF ANALYSIS                                                    │
│     "What if I contribute $X more to 401k?"                            │
│     "What if I sell this stock?"                                        │
│     "What if I buy a rental property?"                                  │
│                                                                         │
│  3. ENTITY STRUCTURE COMPARISON                                         │
│     Sole Prop vs LLC vs S-Corp vs C-Corp                               │
│     Self-employment tax vs corporate tax                                │
│     Reasonable salary optimization                                      │
│                                                                         │
│  4. DEDUCTION BUNCHING                                                  │
│     Standard vs Itemized comparison                                     │
│     Multi-year bunching strategy                                        │
│     Charitable giving timing                                            │
│                                                                         │
│  5. RETIREMENT PLANNING                                                 │
│     Traditional vs Roth contributions                                   │
│     Backdoor Roth strategies                                            │
│     Required Minimum Distributions (RMDs)                               │
│                                                                         │
│  6. ROTH CONVERSION ANALYSIS                                            │
│     Tax bracket filling                                                 │
│     Multi-year conversion planning                                      │
│     Break-even analysis                                                 │
│                                                                         │
│  7. CAPITAL GAINS OPTIMIZATION                                          │
│     Short-term vs long-term                                             │
│     Tax-loss harvesting                                                 │
│     Qualified Small Business Stock (QSBS)                               │
│                                                                         │
│  8. ESTIMATED TAX PLANNING                                              │
│     Safe harbor calculations                                            │
│     Quarterly payment optimization                                      │
│     Penalty avoidance                                                   │
│                                                                         │
│  9. MULTI-YEAR PROJECTIONS                                              │
│     Income shifting strategies                                          │
│     Deduction timing                                                    │
│     Life event planning (retirement, sale of business)                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Tax Concepts

| Concept | Definition | Why It Matters |
|---------|-----------|----------------|
| **AGI** (Adjusted Gross Income) | Total income minus "above-the-line" deductions | Gateway to many tax benefits |
| **MAGI** (Modified AGI) | AGI with certain deductions added back | Controls Roth IRA, ACA eligibility |
| **Effective Tax Rate** | Total tax / Total income | True tax burden measure |
| **Marginal Tax Rate** | Tax rate on next dollar earned | Planning decisions |
| **Tax Bracket** | Income ranges with different rates | Optimization target |
| **Carryforward** | Unused losses/credits carried to future years | Multi-year planning |

### The Advisory Value Formula

```
ADVISORY VALUE = (Tax Savings Identified) × (Implementation Rate) × (Client Retention)

Example:
• Firm identifies $50K in tax savings across clients
• 60% of recommendations implemented
• 95% client retention (vs 70% industry average)
• = $50K × 0.6 × 0.95 = $28,500 in realized client value

OUR PLATFORM IMPACT:
• Increases savings identified (automation finds more)
• Improves implementation rate (clear action items)
• Boosts retention (visible value delivered)
```

---

## Part 5: The Three Portals

### Portal Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         THREE PORTAL ARCHITECTURE                       │
│                                                                         │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐   │
│  │   ADMIN PANEL     │  │    CPA PANEL      │  │  CLIENT PORTAL    │   │
│  │   /admin          │  │    /cpa           │  │  /portal          │   │
│  ├───────────────────┤  ├───────────────────┤  ├───────────────────┤   │
│  │                   │  │                   │  │                   │   │
│  │ Platform Admins   │  │ CPA Firm Teams    │  │ Taxpayer Clients  │   │
│  │                   │  │                   │  │                   │   │
│  │ • Firm management │  │ • Client workflow │  │ • Document upload │   │
│  │ • User management │  │ • Scenario model  │  │ • Status tracking │   │
│  │ • Subscription    │  │ • Advisory plans  │  │ • Report viewing  │   │
│  │ • Partner config  │  │ • Team dashboard  │  │ • Message CPA     │   │
│  │ • RBAC admin      │  │ • Analytics       │  │                   │   │
│  │ • Audit logs      │  │                   │  │                   │   │
│  │                   │  │                   │  │                   │   │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘   │
│                                                                         │
│  TECHNOLOGY: FastAPI backend + Jinja2 templates + Tailwind CSS         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Admin Panel Deep Dive

**Purpose:** Platform-level management for Anthropic staff and white-label partners.

**Key Sections:**

| Section | Function | API Endpoints |
|---------|----------|---------------|
| Dashboard | Platform health metrics | `GET /api/v1/admin/metrics/dashboard` |
| Firms | Manage CPA firm accounts | `GET/POST/PUT /api/v1/admin/firms` |
| Users | User management across firms | `GET/POST/PUT /api/v1/admin/users` |
| Partners | White-label partner config | `GET/POST /api/v1/admin/partners` |
| Subscriptions | Billing and tier management | `GET /api/v1/admin/subscriptions/tiers` |
| RBAC | Role and permission management | `GET /api/v1/admin/rbac/overview` |
| Audit Logs | Activity tracking | `GET /api/v1/admin/audit/logs` |
| Settings | Platform configuration | `GET/PUT /api/v1/admin/settings` |

**Access:** Platform admins only (`is_platform_admin: true`)

### CPA Panel Deep Dive

**Purpose:** The primary workspace for CPA firm teams.

**Key Modules:**

```
CPA PANEL MODULES:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  1. CLIENT MANAGEMENT                                                   │
│     • Client list with search/filter                                    │
│     • Client onboarding workflow                                        │
│     • Document collection tracking                                      │
│     • Communication history                                             │
│                                                                         │
│  2. RETURN WORKFLOW                                                     │
│     • Return status pipeline (Draft → Review → Approved → Filed)       │
│     • Smart intake with AI extraction                                   │
│     • Calculation and optimization                                      │
│     • Review and approval workflow                                      │
│                                                                         │
│  3. SCENARIO MODELING                                                   │
│     • Filing status comparison                                          │
│     • What-if analysis builder                                          │
│     • Entity structure comparison                                       │
│     • Side-by-side scenario comparison                                  │
│                                                                         │
│  4. ADVISORY PLANS                                                      │
│     • Automated recommendation generation                               │
│     • Priority-ranked action items                                      │
│     • Client-facing report export                                       │
│     • Implementation tracking                                           │
│                                                                         │
│  5. PRACTICE INTELLIGENCE (READ-ONLY ANALYTICS)                        │
│     • Advisory vs Compliance Mix                                        │
│     • Complexity Tier Distribution                                      │
│     • YoY Value Surface (tax metrics, not revenue)                     │
│     NOTE: NOT time tracking, billable hours, or staff productivity     │
│                                                                         │
│  6. TEAM COLLABORATION                                                  │
│     • Assignment and workload view                                      │
│     • Review queue                                                      │
│     • Internal notes and comments                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Access:** Firm team members based on role permissions

### Client Portal Deep Dive

**Purpose:** Self-service interface for CPA clients (taxpayers).

**Key Features:**

| Feature | Description |
|---------|-------------|
| Document Upload | Secure upload of W-2s, 1099s, receipts |
| Status Tracking | Real-time view of return progress |
| Report Viewing | Access advisory reports and summaries |
| Messaging | Secure communication with CPA team |
| E-Signatures | Sign engagement letters and authorizations |
| Payment | View and pay invoices |

**Access:** Taxpayer clients with magic link or password authentication

---

## Part 6: Role-Based Access Control (RBAC)

### The 5-Level Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RBAC HIERARCHY (5 LEVELS)                            │
│                                                                         │
│  LEVEL 0: PLATFORM                                                      │
│  ─────────────────────                                                  │
│  • Platform Admins (Anthropic staff)                                    │
│  • Global system access                                                 │
│  • Cross-tenant visibility                                              │
│  • Table: platform_admins                                               │
│                                                                         │
│  LEVEL 1: PARTNER                                                       │
│  ─────────────────────                                                  │
│  • White-label partners                                                 │
│  • Multi-firm management                                                │
│  • Partner-specific branding                                            │
│  • Table: partners                                                      │
│                                                                         │
│  LEVEL 2: FIRM                                                          │
│  ─────────────────────                                                  │
│  • CPA firm accounts                                                    │
│  • Subscription and billing                                             │
│  • Firm-level settings                                                  │
│  • Table: firms                                                         │
│                                                                         │
│  LEVEL 3: USER                                                          │
│  ─────────────────────                                                  │
│  • Firm team members                                                    │
│  • Role-based permissions                                               │
│  • Activity tracking                                                    │
│  • Table: users                                                         │
│                                                                         │
│  LEVEL 4: RESOURCE                                                      │
│  ─────────────────────                                                  │
│  • Clients, returns, documents                                          │
│  • Row-level security                                                   │
│  • Assignment-based access                                              │
│  • Tables: clients, tax_returns                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### User Roles Within Firms

| Role | Description | Key Permissions |
|------|-------------|-----------------|
| **firm_admin** | Full firm access | All permissions, team management, billing |
| **senior_preparer** | Experienced tax pro | All clients, complex returns, mentor role |
| **preparer** | Tax return preparer | Assigned clients, basic scenarios |
| **reviewer** | Quality assurance | Approve/reject returns, compliance |

### Permission Categories

```
PERMISSION CATALOG:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  TEAM MANAGEMENT                    CLIENT MANAGEMENT                  │
│  • manage_team                      • view_client                      │
│  • invite_users                     • view_all_clients                 │
│  • view_team_performance            • create_client                    │
│                                     • edit_client                      │
│                                     • archive_client                   │
│                                     • assign_clients                   │
│                                                                         │
│  RETURN OPERATIONS                  SCENARIOS & ANALYSIS               │
│  • view_returns                     • run_scenarios                    │
│  • create_return                    • view_optimization                │
│  • edit_return                      • generate_reports                 │
│  • submit_for_review                                                    │
│  • review_returns                                                       │
│  • approve_return                                                       │
│  • reject_return                                                        │
│                                                                         │
│  COMPLIANCE & AUDIT                 BILLING & ADMIN                    │
│  • view_compliance                  • view_billing                     │
│  • view_audit_logs                  • update_payment                   │
│  • export_audit_trail               • change_plan                      │
│  • gdpr_requests                    • update_branding                  │
│                                     • manage_api_keys                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Role-Permission Matrix

| Permission | Firm Admin | Senior Preparer | Preparer | Reviewer |
|------------|:----------:|:---------------:|:--------:|:--------:|
| manage_team | ✅ | ❌ | ❌ | ❌ |
| view_all_clients | ✅ | ✅ | ❌ | ❌ |
| create_client | ✅ | ✅ | ✅ | ❌ |
| edit_return | ✅ | ✅ | ✅ | ❌ |
| approve_return | ✅ | ❌ | ❌ | ✅ |
| run_scenarios | ✅ | ✅ | ✅ | ❌ |
| view_billing | ✅ | ❌ | ❌ | ❌ |

### Custom Permission Overrides

The system supports per-user permission overrides:

```json
{
  "user_id": "uuid",
  "role": "preparer",
  "custom_permissions": [
    {"action": "add", "permission": "approve_return"},
    {"action": "remove", "permission": "create_client"}
  ]
}
```

This allows fine-grained control beyond role defaults.

---

## Part 7: Technical Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SYSTEM ARCHITECTURE                              │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      PRESENTATION LAYER                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │   │
│  │  │Admin Panel  │  │ CPA Panel   │  │Client Portal│              │   │
│  │  │/admin       │  │ /cpa        │  │ /portal     │              │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                               │                                         │
│                               ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      API LAYER (FastAPI)                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │   │
│  │  │Admin Routes │  │ CPA Routes  │  │Core Routes  │              │   │
│  │  │/api/v1/admin│  │ /api/v1/cpa │  │ /api/v1/*   │              │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │   │
│  │                      │                                           │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │              RBAC MIDDLEWARE                             │    │   │
│  │  │  • JWT validation                                        │    │   │
│  │  │  • Permission checking                                   │    │   │
│  │  │  • Tenant context injection                              │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                               │                                         │
│                               ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      SERVICE LAYER                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │   │
│  │  │ TaxReturn    │  │ Scenario     │  │ Advisory     │          │   │
│  │  │ Service      │  │ Service      │  │ Service      │          │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │   │
│  │  │ Intake       │  │ Document     │  │ Export       │          │   │
│  │  │ Service      │  │ Service      │  │ Service      │          │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                               │                                         │
│                               ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      DOMAIN LAYER                                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │   │
│  │  │ Calculation  │  │ Optimization │  │ Validation   │          │   │
│  │  │ Engine       │  │ Engine       │  │ Engine       │          │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │   │
│  │  ┌────────────────────────────────────────────────────────┐    │   │
│  │  │              DOMAIN MODELS                              │    │   │
│  │  │  TaxReturn │ Scenario │ AdvisoryPlan │ ClientProfile   │    │   │
│  │  └────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                               │                                         │
│                               ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    INFRASTRUCTURE LAYER                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │   │
│  │  │ Repository  │  │ Event Store │  │ Cache       │              │   │
│  │  │ (Postgres)  │  │ (Audit)     │  │ (Redis)     │              │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | Jinja2 + Tailwind CSS | Server-rendered templates |
| API | FastAPI | REST API with async support |
| Auth | JWT + bcrypt | Token-based authentication |
| Database | PostgreSQL | Primary data store |
| ORM | SQLAlchemy (async) | Database abstraction |
| Migrations | Alembic | Schema versioning |
| Cache | Redis (planned) | Permission cache |
| Task Queue | (planned) | Background jobs |

### Directory Structure

```
src/
├── admin_panel/          # Admin Panel module
│   ├── api/              # Admin API routes
│   │   ├── superadmin_routes.py
│   │   ├── firm_routes.py
│   │   └── user_routes.py
│   ├── auth/             # Admin authentication
│   │   ├── jwt_handler.py
│   │   └── rbac.py
│   └── models/           # Admin-specific models
│
├── cpa_panel/            # CPA Panel module
│   ├── api/              # CPA API routes
│   │   ├── client_routes.py
│   │   ├── workflow_routes.py
│   │   └── practice_intelligence_routes.py
│   └── services/         # CPA business logic
│
├── core/                 # Shared core functionality
│   ├── rbac/             # Global RBAC system
│   │   ├── models.py
│   │   ├── permissions.py
│   │   ├── roles.py
│   │   └── dependencies.py
│   └── logging_config.py # Centralized logging
│
├── database/             # Database layer
│   ├── models/           # SQLAlchemy models
│   ├── repositories/     # Data access layer
│   ├── alembic/          # Migrations
│   └── connection.py     # DB connection handling
│
├── calculator/           # Tax calculation engine
│   ├── engine.py         # Main calculation orchestrator
│   ├── federal/          # Federal tax calculations
│   └── state/            # State tax calculations
│
├── models/               # Domain models
│   ├── tax_return.py
│   ├── taxpayer.py
│   └── scenario.py
│
├── recommendation/       # Advisory engine
│   ├── recommendation_engine.py
│   └── tax_strategy_advisor.py
│
└── web/                  # Web application
    ├── app.py            # FastAPI application
    └── templates/        # Jinja2 templates
```

---

## Part 8: Database Schema & Data Flow

### Core Tables

```sql
-- PLATFORM LEVEL
platform_admins (
    admin_id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    role VARCHAR(50),  -- 'super_admin', 'support', 'billing'
    is_active BOOLEAN
)

partners (
    partner_id UUID PRIMARY KEY,
    name VARCHAR(255),
    branding_config JSONB,
    is_active BOOLEAN
)

-- FIRM LEVEL
firms (
    firm_id UUID PRIMARY KEY,
    partner_id UUID REFERENCES partners,
    name VARCHAR(255),
    subscription_tier VARCHAR(50),
    is_active BOOLEAN,
    settings JSONB
)

users (
    user_id UUID PRIMARY KEY,
    firm_id UUID REFERENCES firms,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    role VARCHAR(50),  -- 'firm_admin', 'senior_preparer', etc.
    custom_permissions JSONB,
    is_active BOOLEAN
)

-- CLIENT LEVEL
clients (
    client_id UUID PRIMARY KEY,
    firm_id UUID REFERENCES firms,
    preparer_id UUID REFERENCES users,
    email VARCHAR(255),
    profile_data JSONB,
    is_active BOOLEAN
)

-- RETURN & SCENARIO LEVEL
tax_returns (
    return_id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients,
    tax_year INTEGER,
    status VARCHAR(20),  -- 'draft', 'review', 'approved', 'filed'
    return_data JSONB,
    calculation_result JSONB
)

scenarios (
    scenario_id UUID PRIMARY KEY,
    return_id UUID REFERENCES tax_returns,
    name VARCHAR(255),
    scenario_type VARCHAR(50),
    scenario_data JSONB,
    is_recommended BOOLEAN
)

advisory_plans (
    plan_id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients,
    return_id UUID REFERENCES tax_returns,
    tax_year INTEGER,
    plan_data JSONB,
    total_potential_savings DECIMAL
)
```

### Data Flow Example: Return Calculation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RETURN CALCULATION DATA FLOW                         │
│                                                                         │
│  1. CLIENT UPLOADS DOCUMENTS                                            │
│     └── POST /api/v1/documents/upload                                   │
│         └── Document stored in S3/local                                 │
│                                                                         │
│  2. AI EXTRACTS DATA                                                    │
│     └── POST /api/v1/intake/extract                                     │
│         └── GPT/Claude extracts W-2, 1099 data                         │
│         └── Returns structured JSON                                     │
│                                                                         │
│  3. CPA REVIEWS & ENRICHES                                              │
│     └── PUT /api/v1/returns/{id}                                        │
│         └── CPA adds/corrects data                                      │
│         └── tax_returns.return_data updated                             │
│                                                                         │
│  4. CALCULATION ENGINE                                                  │
│     └── POST /api/v1/returns/{id}/calculate                             │
│         ├── Load TaxReturn model                                        │
│         ├── Calculate federal (1040 flow)                               │
│         ├── Calculate state(s)                                          │
│         ├── Apply credits & deductions                                  │
│         └── Store calculation_result                                    │
│                                                                         │
│  5. OPTIMIZATION ENGINE                                                 │
│     └── POST /api/v1/returns/{id}/optimize                              │
│         ├── Generate filing status scenarios                            │
│         ├── Generate what-if scenarios                                  │
│         └── Store in scenarios table                                    │
│                                                                         │
│  6. ADVISORY GENERATION                                                 │
│     └── POST /api/v1/advisory/generate                                  │
│         ├── Analyze return for opportunities                            │
│         ├── Generate recommendations                                    │
│         └── Store advisory_plan                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Part 9: Key Features Deep Dive

### Feature 1: Smart Intake

**What it does:** AI-powered document extraction that converts uploaded documents into structured tax data.

```
SMART INTAKE FLOW:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  1. Client uploads W-2 PDF                                              │
│                 │                                                       │
│                 ▼                                                       │
│  2. OCR extracts text (AWS Textract / Google Vision)                   │
│                 │                                                       │
│                 ▼                                                       │
│  3. LLM identifies fields:                                              │
│     • Box 1: Wages = $85,000                                           │
│     • Box 2: Federal withholding = $12,750                             │
│     • Employer: Acme Corp                                               │
│                 │                                                       │
│                 ▼                                                       │
│  4. Structured JSON returned for CPA review                             │
│                 │                                                       │
│                 ▼                                                       │
│  5. CPA confirms/corrects, data flows to tax_return                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Feature 2: Scenario Comparison

**What it does:** Side-by-side comparison of different tax strategies.

```
SCENARIO COMPARISON UI:
┌─────────────────────────────────────────────────────────────────────────┐
│  COMPARE FILING STATUSES                                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │   CURRENT    │  │     MFJ      │  │  HOH ✓ BEST  │                 │
│  │   (Single)   │  │              │  │              │                 │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤                 │
│  │ Tax: $24,500 │  │ Tax: $22,800 │  │ Tax: $21,200 │                 │
│  │ Rate: 22%    │  │ Rate: 20%    │  │ Rate: 18.5%  │                 │
│  │              │  │ Save: $1,700 │  │ Save: $3,300 │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                         │
│  Recommendation: Head of Household saves $3,300                        │
│  Requirements: Paid >50% household costs, qualifying dependent         │
│                                                                         │
│  [Apply HOH to Return]  [Compare More Options]  [Export Report]        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Feature 3: Advisory Plan Generation

**What it does:** Automatically identifies tax-saving opportunities and generates prioritized recommendations.

```
ADVISORY PLAN STRUCTURE:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ADVISORY PLAN FOR: John Smith (TY 2025)                               │
│  Total Potential Savings: $8,450                                        │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════   │
│                                                                         │
│  IMMEDIATE ACTIONS (Before Dec 31)                                     │
│  ─────────────────────────────────                                      │
│  1. Maximize 401(k) Contribution        Save: $2,400/year              │
│     Current: $15,000 | Max: $23,000                                    │
│     Action: Increase payroll deferral to 15%                           │
│                                                                         │
│  2. Open and Fund HSA                   Save: $1,100/year              │
│     Current: $0 | Max: $4,150 (family)                                 │
│     Action: Open HSA at Fidelity, contribute max                       │
│                                                                         │
│  CURRENT YEAR OPPORTUNITIES                                            │
│  ──────────────────────────────                                         │
│  3. Charitable Bunching Strategy        Save: $650 (over 2 years)      │
│     Bundle 2 years of donations into current year                      │
│                                                                         │
│  4. Tax-Loss Harvesting                 Save: $800                     │
│     Sell underwater positions to offset gains                          │
│                                                                         │
│  LONG-TERM PLANNING                                                    │
│  ──────────────────                                                     │
│  5. Roth Conversion Strategy            Save: $3,500 (projected)       │
│     Convert $50K/year in low-income years                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Feature 4: Practice Intelligence

**What it does:** READ-ONLY portfolio analytics for CPA firms. NOT practice management.

**Scope Boundaries (LOCKED):**

| In Scope | Out of Scope |
|----------|--------------|
| Advisory vs Compliance Mix | Time tracking |
| Complexity Tier Distribution | Staff productivity |
| YoY Value Surface (tax metrics) | Revenue per staff |
| | Billable hours |
| | Utilization rates |
| | WIP tracking |

**Why this boundary exists:** We are an intelligence platform, not a practice management system. CPAs should use Karbon, Canopy, or Jetpack for practice management.

---

## Part 10: Current State & Capabilities

### What's Built (Approximately 75%)

```
CURRENT CAPABILITIES:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  TAX CALCULATION ENGINE                                    [COMPLETE]  │
│  ─────────────────────────                                              │
│  ✅ 25+ IRS form calculations                                          │
│  ✅ 50+ state tax calculations                                         │
│  ✅ Comprehensive bracket calculations                                  │
│  ✅ Standard/itemized deduction logic                                   │
│  ✅ Credit calculations (EITC, CTC, education, etc.)                   │
│  ✅ Self-employment tax (Schedule SE)                                   │
│  ✅ AMT calculations                                                    │
│                                                                         │
│  SCENARIO MODELING                                         [COMPLETE]  │
│  ────────────────────                                                   │
│  ✅ Filing status comparison                                            │
│  ✅ What-if analysis framework                                          │
│  ✅ Entity structure comparison (S-Corp vs LLC vs Sole Prop)           │
│  ✅ Retirement contribution optimization                                │
│  ✅ Scenario persistence and retrieval                                  │
│                                                                         │
│  RECOMMENDATION ENGINE                                     [COMPLETE]  │
│  ────────────────────────                                               │
│  ✅ Automated opportunity detection                                     │
│  ✅ Priority-ranked recommendations                                     │
│  ✅ Savings estimation                                                  │
│  ✅ Action step generation                                              │
│                                                                         │
│  THREE PORTALS                                             [COMPLETE]  │
│  ─────────────────                                                      │
│  ✅ Admin Panel with RBAC                                               │
│  ✅ CPA Panel with workflow                                             │
│  ✅ Client Portal with document upload                                  │
│                                                                         │
│  RBAC SYSTEM                                               [COMPLETE]  │
│  ────────────────                                                       │
│  ✅ 5-level hierarchy                                                   │
│  ✅ Database-driven permissions                                         │
│  ✅ Custom role overrides                                               │
│  ✅ Multi-tenant isolation                                              │
│                                                                         │
│  DATABASE INTEGRATION                                      [COMPLETE]  │
│  ─────────────────────                                                  │
│  ✅ PostgreSQL with async SQLAlchemy                                    │
│  ✅ Alembic migrations                                                  │
│  ✅ Repository pattern                                                  │
│  ✅ Real data in all API endpoints                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### What Needs Enhancement (Approximately 25%)

```
ENHANCEMENT AREAS:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  UI/UX POLISH                                              [IN PROGRESS]│
│  ─────────────────                                                      │
│  ⏳ Decision-first dashboard (vs form-first)                           │
│  ⏳ Mobile-responsive design                                            │
│  ⏳ Progressive disclosure patterns                                     │
│  ⏳ Real-time feedback loops                                            │
│                                                                         │
│  CLIENT-FACING REPORTS                                     [PLANNED]   │
│  ─────────────────────────                                              │
│  ⏳ PDF export for advisory plans                                       │
│  ⏳ White-label branding                                                │
│  ⏳ Email delivery                                                      │
│                                                                         │
│  AI INTAKE ENHANCEMENT                                     [PLANNED]   │
│  ────────────────────────                                               │
│  ⏳ Multi-document batch processing                                     │
│  ⏳ Confidence scoring                                                  │
│  ⏳ Auto-categorization                                                 │
│                                                                         │
│  MULTI-YEAR PLANNING                                       [PLANNED]   │
│  ─────────────────────                                                  │
│  ⏳ Prior year carryforward tracking                                    │
│  ⏳ 3-5 year projection models                                          │
│  ⏳ Life event planning (retirement, sale of business)                  │
│                                                                         │
│  INTEGRATIONS                                              [PLANNED]   │
│  ──────────────                                                         │
│  ⏳ QuickBooks/Xero sync                                                │
│  ⏳ Investment account aggregation                                      │
│  ⏳ Payroll provider integration                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Part 11: Scope Boundaries

### Firm Boundaries: What CPAs Control

| Element | Firm-Controlled | Platform-Controlled |
|---------|-----------------|---------------------|
| Team members | ✅ | |
| Client data | ✅ | |
| Branding (name, logo) | ✅ | |
| Workflow customization | ✅ | |
| Subscription tier | | ✅ |
| Feature availability | | ✅ (by tier) |
| System permissions | | ✅ |

### Feature Boundaries by Subscription Tier

```
SUBSCRIPTION TIERS:
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  STARTER ($99/month)                                                    │
│  ─────────────────────                                                  │
│  • Up to 50 clients                                                     │
│  • 2 team members                                                       │
│  • Basic scenarios (filing status only)                                 │
│  • Standard reports                                                     │
│                                                                         │
│  PROFESSIONAL ($299/month)                                              │
│  ─────────────────────────                                              │
│  • Up to 250 clients                                                    │
│  • 10 team members                                                      │
│  • All scenario types                                                   │
│  • Advisory plan generation                                             │
│  • Practice intelligence                                                │
│                                                                         │
│  ENTERPRISE ($599+/month)                                               │
│  ────────────────────────                                               │
│  • Unlimited clients                                                    │
│  • Unlimited team members                                               │
│  • White-label branding                                                 │
│  • API access                                                           │
│  • Custom integrations                                                  │
│  • Dedicated support                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### API Boundaries

| Endpoint Pattern | Access Level |
|-----------------|--------------|
| `/api/v1/admin/*` | Platform admins only |
| `/api/v1/cpa/*` | Firm team members (role-based) |
| `/api/v1/portal/*` | Authenticated clients only |
| `/api/v1/returns/*` | Requires return access permission |

---

## Part 12: Product Roadmap

### Near-Term (Q1 2026)

1. **Complete Admin Panel API Integration** - All sections connected to real data
2. **Design System Unification** - Consistent look across all portals
3. **Security Hardening** - XSS prevention, TESTING_MODE fixes

### Mid-Term (Q2-Q3 2026)

1. **Multi-Year Planning Module**
   - Prior year carryforward tracking
   - 3-5 year projection models
   - Life event planning

2. **Enhanced AI Intake**
   - Multi-document batch processing
   - Confidence scoring and validation
   - Auto-categorization

3. **Client-Facing Reports**
   - PDF export with white-label branding
   - Email delivery automation
   - Digital signature integration

### Long-Term (Q4 2026+)

1. **Integration Ecosystem**
   - QuickBooks/Xero sync
   - Investment account aggregation
   - Payroll provider integration

2. **Advanced Analytics**
   - Firm benchmarking
   - Client retention prediction
   - Opportunity scoring

3. **Mobile Applications**
   - CPA mobile app
   - Client mobile app

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| AGI | Adjusted Gross Income - total income minus specific deductions |
| CPA | Certified Public Accountant |
| EITC | Earned Income Tax Credit |
| HOH | Head of Household (filing status) |
| MAGI | Modified Adjusted Gross Income |
| MFJ | Married Filing Jointly |
| MFS | Married Filing Separately |
| RBAC | Role-Based Access Control |
| SSN | Social Security Number |

## Appendix B: Key Files Reference

| Purpose | File Path |
|---------|-----------|
| Main app entry | `src/web/app.py` |
| Admin routes | `src/admin_panel/api/superadmin_routes.py` |
| CPA routes | `src/cpa_panel/api/*.py` |
| RBAC system | `src/core/rbac/` |
| User model | `src/admin_panel/models/user.py` |
| Calculation engine | `src/calculator/engine.py` |
| Tax return model | `src/models/tax_return.py` |
| Database migrations | `src/database/alembic/versions/` |

## Appendix C: API Endpoint Catalog

### Admin Panel Endpoints

```
GET  /api/v1/admin/metrics/dashboard     Dashboard metrics
GET  /api/v1/admin/firms                 List firms
POST /api/v1/admin/firms                 Create firm
GET  /api/v1/admin/users                 List users
GET  /api/v1/admin/audit/logs            Audit logs
GET  /api/v1/admin/rbac/overview         RBAC overview
```

### CPA Panel Endpoints

```
GET  /api/v1/cpa/clients                 List clients
GET  /api/v1/cpa/workflow/returns        Return workflow
GET  /api/v1/cpa/intelligence/metrics    Practice metrics
POST /api/v1/cpa/onboarding/start        Start onboarding
```

### Core Endpoints

```
POST /api/v1/returns/{id}/calculate      Calculate return
POST /api/v1/scenarios                   Create scenario
POST /api/v1/scenarios/compare           Compare scenarios
POST /api/v1/advisory/generate           Generate advisory
```

---

*Document Version: 1.0*
*Training Date: January 2026*
*Maintainer: Product Team*
