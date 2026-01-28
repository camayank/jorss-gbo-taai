# User Roles → Modules/Features Mapping
## CA4CPA Global LLC - Comprehensive RBAC Documentation

---

## PLATFORM VISION ALIGNMENT

> **CRITICAL: This platform is B2B ONLY**
>
> - **NO e-filing capability** - Platform generates advisory reports and filing packages to SUPPORT external e-filing
> - **NO B2C channel** - All clients belong to CPA firms, accessing via white-labeled portals
> - **Payment model:** Platform collects from CPAs (subscription), CPAs collect from clients (Stripe Connect)
> - **All clients treated the same** - No distinction between client types

---

## TABLE OF CONTENTS

1. [Role Hierarchy Architecture](#1-role-hierarchy-architecture)
2. [Role Definitions & Who Uses Them](#2-role-definitions--who-uses-them)
3. [Module/Feature Access Matrix](#3-modulefeature-access-matrix)
4. [Detailed Permission Breakdown by Role](#4-detailed-permission-breakdown-by-role)
5. [Subscription Tier Feature Gating](#5-subscription-tier-feature-gating)
6. [Return Status Workflow](#6-return-status-workflow)
7. [Report Types (NOT E-Filing)](#7-report-types-not-e-filing)
8. [Data Visibility Rules](#8-data-visibility-rules)
9. [Security & Compliance](#9-security--compliance)

---

## 1. ROLE HIERARCHY ARCHITECTURE

### 1.1 Visual Role Hierarchy (7 Active Roles)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LEVEL 0: PLATFORM (CA4CPA Internal)                  │
│                                                                         │
│  ┌──────────────┐  ┌─────────────────┐  ┌──────────┐  ┌──────────┐     │
│  │ SUPER_ADMIN  │  │ PLATFORM_ADMIN  │  │ SUPPORT  │  │ BILLING  │     │
│  │  (Founders)  │  │  (Operations)   │  │(Help Desk)│ │(Finance) │     │
│  │     ★★★★     │  │      ★★★        │  │    ★★    │  │    ★     │     │
│  └──────────────┘  └─────────────────┘  └──────────┘  └──────────┘     │
│         │                  │                  │             │           │
│         │ Can Impersonate  │ Can Impersonate  │Can Imperson │           │
│         ▼                  ▼                  ▼             │           │
├─────────────────────────────────────────────────────────────────────────┤
│                    LEVEL 1: CPA FIRM (B2B Customers)                    │
│                                                                         │
│  ┌─────────────────────────┐  ┌─────────────────────────┐              │
│  │        PARTNER          │  │         STAFF           │              │
│  │   (CPA Firm Owner)      │  │   (CPA Employees)       │              │
│  │   Full Firm Control     │  │   Delegated Access      │              │
│  │         ★★★             │  │         ★★              │              │
│  └─────────────────────────┘  └─────────────────────────┘              │
│              │                          │                               │
│              │ Manages                  │ Serves                        │
│              ▼                          ▼                               │
├─────────────────────────────────────────────────────────────────────────┤
│                    LEVEL 2: CLIENT (B2B2C - CPA's Clients)              │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         CLIENT                                   │   │
│  │          (Taxpayer - CPA's Client via White-Label Portal)        │   │
│  │          All clients access through their CPA's portal           │   │
│  │                            ★                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

Legend: ★ = Access Level (more stars = higher privilege)

NOTE: There is NO B2C channel. All clients belong to CPA firms.
```

### 1.2 Access Level Rules

| Level | Numeric Value | Who | Data Access |
|-------|---------------|-----|-------------|
| PLATFORM | 0 | CA4CPA Internal | ALL levels (0, 1, 2) |
| FIRM | 1 | CPAs (Partner, Staff) | FIRM (1) and CLIENT (2) |
| CLIENT | 2 | Taxpayers | Only own data |

### 1.3 Impersonation Capabilities

| Role | Can Impersonate | Purpose |
|------|-----------------|---------|
| SUPER_ADMIN | ✓ Any role | System debugging, emergency access |
| PLATFORM_ADMIN | ✓ Firm-level or below | Customer support, troubleshooting |
| SUPPORT | ✓ Firm-level (read-mostly) | Issue investigation |
| BILLING | ✗ No | Finance operations only |
| PARTNER | ✗ No | Firm-level access |
| STAFF | ✗ No | Delegated access only |
| CLIENT | ✗ No | Own data only |

---

## 2. ROLE DEFINITIONS & WHO USES THEM

### 2.1 PLATFORM ROLES (CA4CPA Internal - Level 0)

#### SUPER_ADMIN
**Who:** Founders, CTO, Principal Engineers

**Capabilities:**
- Complete platform authority
- Manage platform admins
- Configure global system settings
- Access all data across all tenants
- Emergency access recovery

#### PLATFORM_ADMIN
**Who:** Operations Manager, Senior Operations Staff

**Capabilities:**
- Tenant (CPA firm) management
- Subscription management
- Feature flag configuration
- Platform metrics monitoring
- **Cannot:** Manage other platform admins

#### SUPPORT
**Who:** Customer Support Representatives, Help Desk

**Capabilities:**
- View firm data (read-only)
- Impersonate for troubleshooting
- View subscription status
- View audit logs
- **Cannot:** Make changes to firms

#### BILLING
**Who:** Finance Team, Billing Support

**Capabilities:**
- View subscriptions
- Process subscription changes
- View revenue metrics
- Handle refunds
- **Cannot:** Impersonate, view audit logs

---

### 2.2 CPA FIRM ROLES (Level 1)

#### PARTNER
**Who:** CPA Firm Owner, Managing Partner

**Capabilities:**
- Full firm settings and branding control
- Team management (invite, manage, remove)
- All clients (view, create, edit, archive, assign)
- All returns (view, create, edit, submit, review, approve)
- Generate filing packages
- Documents (view, upload, delete)
- Analytics and billing management

#### STAFF
**Who:** CPAs, Tax Preparers, Associates

**Capabilities:**
- Firm settings (view only)
- Assigned clients only
- Assigned returns (create, edit, submit, review, approve)
- Generate filing packages for assigned clients
- Documents (view, upload - no delete)
- **Cannot:** Team management, billing, client assignment

---

### 2.3 CLIENT ROLE (Level 2)

#### CLIENT (FIRM_CLIENT)
**Who:** Taxpayers who are clients of CPA firms

**Access Method:** CPA's white-labeled portal

**Capabilities:**
- View/edit own profile
- View/edit own returns (DRAFT status only)
- Upload documents
- View return status
- Message assigned CPA
- Use tax advisory tools (calculators, scenarios)
- **Cannot:** Generate filing packages, access professional tools

> **NOTE:** All clients are treated the same. There is no "direct client" concept.
> The platform does not serve individual taxpayers directly (B2B only).

---

## 3. MODULE/FEATURE ACCESS MATRIX

### 3.1 Core Features

| Feature | Super Admin | Platform Admin | Support | Billing | Partner | Staff | Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-------:|:-----:|:------:|
| **Dashboard** | ✓ Platform | ✓ Platform | ✓ Support | ✓ Billing | ✓ Firm | ✓ Personal | ✓ Personal |
| **Express Lane** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ |
| **Smart Tax** | ✓ | ✓ | - | - | ✓ᵀ | ✓ᵀ | ✓ᵀ |
| **Guided Filing** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ |
| **Document Upload** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ |
| **Basic Calculations** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ |

**Legend:** ✓ᵀ = Requires STARTER+ Tier

### 3.2 Advisory & Analysis Features

| Feature | Partner | Staff | Client | Min Tier |
|---------|:-------:|:-----:|:------:|:--------:|
| **Scenario Explorer** | ✓ | ✓ | ✓ | STARTER |
| **Tax Projections** | ✓ | ✓ | ✓ | STARTER |
| **Advisory Reports** | ✓ | ✓ | ✓ | FREE |
| **Premium Tiered Reports** | ✓ | ✓ | - | STARTER |
| **Advanced Analytics** | ✓ | - | - | PROFESSIONAL |
| **Custom Reports** | ✓ | - | - | ENTERPRISE |

### 3.3 AI Features (CPA Only)

| Feature | Partner | Staff | Client | Min Tier |
|---------|:-------:|:-----:|:------:|:--------:|
| **AI Tax Chat** | ✓ | ✓ | ✗ | PROFESSIONAL |
| **AI Suggestions** | ✓ | ✓ | ✗ | PROFESSIONAL |
| **Document AI** | ✓ | ✓ | ✗ | PROFESSIONAL |

### 3.4 Filing Package Generation (NOT E-Filing)

| Feature | Partner | Staff | Client | Min Tier |
|---------|:-------:|:-----:|:------:|:--------:|
| **Generate Filing Package** | ✓ | ✓ᴬ | ✗ | STARTER |
| **Draft Tax Return Export** | ✓ | ✓ᴬ | ✗ | STARTER |
| **Tax Computation Statement** | ✓ | ✓ᴬ | ✗ | STARTER |

**Legend:** ✓ᴬ = Assigned clients only

> **IMPORTANT:** The platform does NOT e-file with IRS.
> Filing packages are generated for CPAs to file externally using their preferred e-filing software.

### 3.5 Collaboration Features

| Feature | Partner | Staff | Client | Min Tier |
|---------|:-------:|:-----:|:------:|:--------:|
| **Client Portal** | ✓ | ✓ | ✓ | STARTER |
| **Team Collaboration** | ✓ | view | ✗ | PROFESSIONAL |
| **Client Messaging** | ✓ | ✓ | ✓ | PROFESSIONAL |

### 3.6 Admin & Management

| Feature | Super Admin | Platform Admin | Support | Partner | Staff | Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-----:|:------:|
| **User Management** | ✓ Platform | ✓ Platform | ✗ | ✓ Firm | ✗ | ✗ |
| **Firm Management** | ✓ | ✓ | ✓ᴿ | - | - | - |
| **Subscription Mgmt** | ✓ | ✓ | ✗ | - | - | - |
| **Feature Flags** | ✓ | ✓ | ✗ | - | - | - |
| **Audit Logs** | ✓ | ✓ | ✓ᴿ | ✓ᴾ | ✗ | ✗ |

**Legend:** ✓ᴿ = Read-only, ✓ᴾ = PROFESSIONAL+ tier

### 3.7 Integration & API

| Feature | Partner | Staff | Client | Min Tier |
|---------|:-------:|:-----:|:------:|:--------:|
| **QuickBooks** | ✓ | ✗ | ✗ | PROFESSIONAL |
| **Plaid** | ✓ | ✗ | ✗ | ENTERPRISE |
| **API Access** | ✓ | ✗ | ✗ | ENTERPRISE |
| **Webhooks** | ✓ | ✗ | ✗ | ENTERPRISE |
| **Stripe Connect** | ✓ | ✗ | ✗ | STARTER |

### 3.8 White-Label Features

| Feature | Partner | Staff | Client | Min Tier |
|---------|:-------:|:-----:|:------:|:--------:|
| **Custom Branding** | ✓ | ✗ | ✗ | PROFESSIONAL |
| **Custom Domain** | ✓ | ✗ | ✗ | ENTERPRISE |
| **Remove Platform Branding** | ✓ | ✗ | ✗ | WHITE_LABEL |
| **Custom CSS/JS** | ✓ | ✗ | ✗ | ENTERPRISE |

---

## 4. DETAILED PERMISSION BREAKDOWN BY ROLE

### 4.1 PARTNER Permissions (Full Firm Access)

| Category | Permissions |
|----------|-------------|
| **Firm** | View/manage settings, branding, analytics, billing |
| **Team** | View, invite, manage, remove members |
| **Client** | View all, create, edit, archive, assign |
| **Return** | View all, create, edit, submit, review, approve |
| **Filing Package** | Generate for any client |
| **Documents** | View, upload, delete |
| **Features** | All tier-appropriate features |

### 4.2 STAFF Permissions (Assigned Clients)

| Category | Permissions | Scope |
|----------|-------------|-------|
| **Firm** | View settings, analytics | Read-only |
| **Team** | View members | Read-only |
| **Client** | View, create, edit | **Assigned only** |
| **Return** | View, create, edit, submit, review, approve | **Assigned only** |
| **Filing Package** | Generate | **Assigned only** |
| **Documents** | View, upload | **No delete** |

### 4.3 CLIENT Permissions (Own Data)

| Category | Permissions | Restrictions |
|----------|-------------|--------------|
| **Profile** | View, edit | Own only |
| **Return** | View, edit | Own only, DRAFT status only |
| **Documents** | View, upload | Own only |
| **Portal** | Full access | - |
| **Messaging** | Send to CPA | Assigned CPA |
| **Advisory Tools** | Calculators, scenarios | As per tier |

---

## 5. SUBSCRIPTION TIER FEATURE GATING

### 5.1 Tier Overview

| Tier | Target | Key Features |
|------|--------|--------------|
| **FREE** | Trial | Express Lane, Guided Filing, Basic Reports |
| **STARTER** | Small practices | + Smart Tax, Scenarios, Projections, Filing Package |
| **PROFESSIONAL** | Growing firms | + AI Chat, Team, Branding, QuickBooks |
| **ENTERPRISE** | Large firms | + API, Webhooks, Custom Domain, Plaid |
| **WHITE_LABEL** | Resellers | + Remove all CA4CPA branding |

### 5.2 Feature Availability Matrix

| Feature | FREE | STARTER | PROFESSIONAL | ENTERPRISE | WHITE_LABEL |
|---------|:----:|:-------:|:------------:|:----------:|:-----------:|
| Express Lane | ✓ | ✓ | ✓ | ✓ | ✓ |
| Smart Tax | - | ✓ | ✓ | ✓ | ✓ |
| Scenarios | - | ✓ | ✓ | ✓ | ✓ |
| Filing Package | - | ✓ | ✓ | ✓ | ✓ |
| AI Chat | - | - | ✓ | ✓ | ✓ |
| Team Collaboration | - | - | ✓ | ✓ | ✓ |
| Custom Branding | - | - | ✓ | ✓ | ✓ |
| QuickBooks | - | - | ✓ | ✓ | ✓ |
| API Access | - | - | - | ✓ | ✓ |
| Custom Domain | - | - | - | ✓ | ✓ |
| Remove Branding | - | - | - | - | ✓ |

### 5.3 Usage Limits

| Limit | FREE | STARTER | PROFESSIONAL | ENTERPRISE | WHITE_LABEL |
|-------|:----:|:-------:|:------------:|:----------:|:-----------:|
| Returns/Month | 5 | 50 | 200 | Unlimited | Unlimited |
| CPAs | 1 | 3 | 10 | Unlimited | Unlimited |
| Clients/CPA | 10 | 50 | 200 | Unlimited | Unlimited |
| Storage (GB) | 1 | 10 | 50 | 500 | Unlimited |

---

## 6. RETURN STATUS WORKFLOW

### 6.1 Status Flow (NO E-Filing)

```
┌──────────┐     ┌───────────┐     ┌──────────────┐     ┌──────────────┐
│  DRAFT   │────▶│ IN_REVIEW │────▶│ CPA_APPROVED │────▶│ FILING_READY │
│          │     │           │     │              │     │              │
│ Client   │     │ CPA edits │     │ Ready for    │     │ Package      │
│ editable │     │ & reviews │     │ filing pkg   │     │ generated    │
└──────────┘     └───────────┘     └──────────────┘     └──────────────┘
                       │                                       │
                       │ Send back                             │ CPA files externally
                       ▼                                       ▼
                 ┌──────────┐                           ┌──────────────┐
                 │  DRAFT   │                           │   ACCEPTED   │
                 │          │                           │              │
                 │ Revisions│                           │ Filing done  │
                 │ needed   │                           │ externally   │
                 └──────────┘                           └──────────────┘
                                                              │
                                                              │ Issues found
                                                              ▼
                                                        ┌──────────────┐
                                                        │   REJECTED   │
                                                        │              │
                                                        │ Needs fixes  │
                                                        └──────────────┘
```

### 6.2 Status Definitions

| Status | Description | Who Can Edit |
|--------|-------------|--------------|
| **DRAFT** | Return being prepared | Client (own), CPA (assigned) |
| **IN_REVIEW** | Submitted for CPA review | CPA only |
| **CPA_APPROVED** | Approved, ready for filing package | Locked |
| **FILING_READY** | Filing package generated | Locked |
| **ACCEPTED** | CPA confirmed filed & accepted externally | Locked (final) |
| **REJECTED** | Issues found during external filing | CPA can fix |

> **IMPORTANT:** FILING_READY means the filing package is ready for download.
> The CPA then files using their preferred external e-filing software.
> This platform does NOT submit directly to IRS.

---

## 7. REPORT TYPES (NOT E-Filing)

### 7.1 Report Inventory

| Report Type | Format | Target Users | Purpose |
|-------------|--------|--------------|---------|
| **Advisory Report** | PDF, HTML, JSON | CPAs, Clients | Tax optimization recommendations |
| **Premium Tiered Reports** | PDF, HTML, JSON | Clients (paid) | Detailed analysis at 3 price tiers |
| **Tax Computation Statement** | PDF, HTML | CPAs | Detailed calculation breakdown |
| **Draft Tax Return** | PDF | CPAs | Forms for external filing |
| **Opportunity Detection** | JSON | Taxpayers | Savings opportunities |
| **Universal Report (Lead Magnet)** | PDF, HTML | Prospects | Branded teaser content |
| **Capital Gains (8949)** | PDF | Investors | Investment reporting |
| **Audit/Compliance** | HTML, JSON | Auditors | Compliance documentation |

### 7.2 Filing Package Contents

When CPA generates a "Filing Package" (FILING_READY status), it includes:

1. **Draft Tax Return PDF** - All forms ready for e-filing
2. **Tax Computation Statement** - Detailed calculations with IRC references
3. **Supporting Schedules** - All applicable schedules (A, C, D, E, etc.)
4. **Preparer Notes** - CPA review comments
5. **Missing Information Flags** - Items needing attention
6. **Data Export (JSON)** - Structured data for import into e-filing software

---

## 8. DATA VISIBILITY RULES

### 8.1 Client Data Visibility

| Role | Can See |
|------|---------|
| SUPER_ADMIN | All clients across all firms |
| PLATFORM_ADMIN | All clients across all firms |
| SUPPORT | All clients (read-only) |
| BILLING | No direct client access |
| PARTNER | All clients within their firm |
| STAFF | Assigned clients only |
| CLIENT | Own profile only |

### 8.2 Tenant Isolation

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   CPA Firm A    │   │   CPA Firm B    │   │   CPA Firm C    │
│   (Tenant 1)    │   │   (Tenant 2)    │   │   (Tenant 3)    │
├─────────────────┤   ├─────────────────┤   ├─────────────────┤
│ Partner A       │   │ Partner B       │   │ Partner C       │
│ Staff A1, A2    │   │ Staff B1        │   │ Staff C1-C3     │
│ Clients A       │   │ Clients B       │   │ Clients C       │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         │  COMPLETE ISOLATION │                     │
         │  (Cannot see each other's data)          │
         └─────────────────────┴─────────────────────┘
                              │
                    Platform Level
                    (Can see all tenants)
```

---

## 9. SECURITY & COMPLIANCE

### 9.1 Key Security Features

| Feature | Description | Availability |
|---------|-------------|--------------|
| **2FA** | Two-factor authentication | ENTERPRISE+ |
| **IP Whitelisting** | Restrict access by IP | ENTERPRISE+ |
| **SSO** | Single sign-on integration | ENTERPRISE+ |
| **Audit Logs** | Complete activity trail | PROFESSIONAL+ |
| **Session Timeout** | Configurable per tier | All tiers |

### 9.2 Role Escalation Prevention

- Partner cannot promote to Platform Admin
- Staff cannot promote to Partner (requires Partner action)
- Clients cannot gain CPA permissions
- Only Super Admin can create Platform Admins

### 9.3 Audit Trail

All actions are logged with:
- User ID and role
- Resource accessed
- Action performed
- Timestamp and IP address
- Impersonation context (if any)

---

## SUMMARY

### Business Model

| Relationship | Payment Flow |
|--------------|--------------|
| Platform → CPA | Subscription (monthly/annual) |
| CPA → Client | Per-service via Stripe Connect |

### Key Constraints

1. **NO E-Filing** - Platform generates reports/packages for external filing
2. **NO B2C** - All clients belong to CPA firms
3. **White-Label Only** - Platform is the infrastructure, CPAs are the brand
4. **All Clients Same** - No distinction between client types

---

*Document aligned with platform vision: 2026-01-28*
*Source files: src/rbac/roles.py, src/rbac/permissions.py, src/rbac/enhanced_permissions.py, src/rbac/feature_access_control.py, src/rbac/status_permissions.py*
