# User Roles → Modules/Features Mapping
## CA4CPA Global LLC - Comprehensive RBAC Documentation

---

## TABLE OF CONTENTS

1. [Role Hierarchy Architecture](#1-role-hierarchy-architecture)
2. [Role Definitions & Who Uses Them](#2-role-definitions--who-uses-them)
3. [Module/Feature Access Matrix](#3-modulefeature-access-matrix)
4. [Detailed Permission Breakdown by Role](#4-detailed-permission-breakdown-by-role)
5. [Subscription Tier Feature Gating](#5-subscription-tier-feature-gating)
6. [Permission Categories & Definitions](#6-permission-categories--definitions)
7. [Access Control Decision Logic](#7-access-control-decision-logic)
8. [Data Visibility Rules](#8-data-visibility-rules)
9. [Feature-Specific Behavior by Role](#9-feature-specific-behavior-by-role)
10. [Security & Compliance Considerations](#10-security--compliance-considerations)

---

## 1. ROLE HIERARCHY ARCHITECTURE

### 1.1 Visual Role Hierarchy

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
├─────────────────────────────────────────────────────────────│───────────┤
│                    LEVEL 1A: CPA FIRM (B2B Customers)       │           │
│                                                             │           │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  │           │
│  │        PARTNER          │  │         STAFF           │  │           │
│  │   (CPA Firm Owner)      │  │   (CPA Employees)       │  │           │
│  │   Full Firm Control     │  │   Delegated Access      │  │           │
│  │         ★★★             │  │         ★★              │  │           │
│  └─────────────────────────┘  └─────────────────────────┘  │           │
│              │                          │                   │           │
│              │ Manages                  │ Serves            │           │
│              ▼                          ▼                   │           │
├───────────────────────────────────────────────────────────────────────┤
│                    LEVEL 1B: DIRECT CLIENT (B2C)                       │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      DIRECT_CLIENT                               │   │
│  │              (Self-Service DIY Taxpayer)                         │   │
│  │              Uses CA4CPA directly - No CPA                       │   │
│  │                          ★                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                    LEVEL 2: FIRM CLIENT (B2B2C)                        │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                       FIRM_CLIENT                                │   │
│  │             (CPA's Taxpayer Client)                              │   │
│  │             Managed by Partner/Staff                             │   │
│  │                          ★                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

Legend: ★ = Access Level (more stars = higher privilege)
```

### 1.2 Access Level Rules

| Level | Numeric Value | Can Access Data At Levels |
|-------|---------------|---------------------------|
| PLATFORM | 0 | ALL levels (0, 1, 2) |
| FIRM | 1 | FIRM (1) and CLIENT (2) |
| CLIENT | 2 | Only CLIENT (2) - own data |

### 1.3 Impersonation Capabilities

| Role | Can Impersonate |
|------|-----------------|
| SUPER_ADMIN | ✓ Any role at any level |
| PLATFORM_ADMIN | ✓ Any firm-level or below |
| SUPPORT | ✓ Any firm-level or below (read-mostly) |
| BILLING | ✗ Cannot impersonate |
| PARTNER | ✗ Cannot impersonate |
| STAFF | ✗ Cannot impersonate |
| DIRECT_CLIENT | ✗ Cannot impersonate |
| FIRM_CLIENT | ✗ Cannot impersonate |

---

## 2. ROLE DEFINITIONS & WHO USES THEM

### 2.1 SUPER_ADMIN

**Who:** Founders, CTO, Principal Engineers

**Description:** Complete platform authority. Can do anything including creating/deleting platform admins, configuring global system settings, and viewing all data across all tenants.

**Primary Responsibilities:**
- Platform architecture decisions
- Critical security configurations
- Admin user management
- Emergency access recovery
- Feature flag global controls
- Platform-wide policy enforcement

**Unique Capabilities:**
- Only role that can manage other platform admins (`PLATFORM_MANAGE_ADMINS`)
- Can override any permission check
- Has ALL permissions in the system

---

### 2.2 PLATFORM_ADMIN

**Who:** Operations Manager, Senior Operations Staff

**Description:** Day-to-day platform management without ability to modify admin team.

**Primary Responsibilities:**
- Tenant (CPA firm) management
- Subscription management
- Feature flag configuration per tenant
- Monitoring platform metrics
- Audit log review
- Customer escalations

**Key Permissions:**
- View/Create/Edit/Delete tenants
- Manage subscriptions and billing
- Configure features per tenant
- View platform-wide metrics
- View all audit logs
- **Cannot:** Manage other platform admins

---

### 2.3 SUPPORT

**Who:** Customer Support Representatives, Help Desk Staff

**Description:** Read-access focused role for troubleshooting with impersonation capability.

**Primary Responsibilities:**
- Troubleshoot customer issues
- View firm data for debugging
- Impersonate users to reproduce issues
- View subscription and account status
- Escalate complex issues

**Key Permissions:**
- View all firms (read-only)
- Impersonate for troubleshooting
- View subscription data (read-only)
- View platform metrics (read-only)
- View audit logs (read-only)
- **Cannot:** Make changes to firms, subscriptions, or features

---

### 2.4 BILLING

**Who:** Finance Team, Billing Support

**Description:** Finance-focused role for subscription and payment management.

**Primary Responsibilities:**
- Process subscription changes
- Handle billing inquiries
- Manage refunds
- View revenue metrics
- Process payment updates

**Key Permissions:**
- View all firms (read-only)
- View subscriptions
- Manage subscriptions (upgrades, downgrades, cancellations)
- View platform metrics
- **Cannot:** Impersonate, manage features, view audit logs

---

### 2.5 PARTNER

**Who:** CPA Firm Owner, Managing Partner

**Description:** Full administrative control of their own firm/tenant.

**Primary Responsibilities:**
- Firm configuration and branding
- Team management (invite, manage, remove staff)
- Client management (all clients in firm)
- Billing and subscription for their firm
- Analytics and reporting
- Feature configuration (within tier limits)

**Key Permissions:**
- Full firm settings and branding control
- Team management (invite, manage, remove)
- All clients (view, create, edit, archive, assign)
- All returns (view, create, edit, submit, review, approve)
- Documents (view, upload, delete)
- Analytics and billing management
- Client assignment to staff members

---

### 2.6 STAFF

**Who:** CPAs, Tax Preparers, Associates at a CPA Firm

**Description:** Delegated access to work on assigned clients only.

**Primary Responsibilities:**
- Prepare tax returns for assigned clients
- Upload and manage client documents
- Submit returns for review
- Communicate with clients
- Run tax scenarios and projections

**Key Permissions:**
- Firm settings (view only)
- Team members (view only)
- Assigned clients only (view, create, edit)
- Assigned returns (view, create, edit, submit)
- Documents (view, upload - no delete)
- Run scenarios and generate advisories
- **Cannot:** Team management, billing, client assignment, document deletion

**Scope Limitation:** Can only see/work with clients assigned to them

---

### 2.7 DIRECT_CLIENT

**Who:** Individual Taxpayers using CA4CPA directly (DIY filers)

**Description:** Self-service taxpayer without a CPA intermediary.

**Primary Responsibilities:**
- File own tax returns
- Upload own documents
- View own return status
- Use Express Lane and Smart Tax features

**Key Permissions:**
- View/edit own profile
- View/edit own returns (DRAFT status only)
- Upload documents to own account
- View return status
- Use Express Lane
- Use Smart Tax (if on STARTER+ tier)
- **Cannot:** Access AI Chat, E-File, Team features, or professional tools

---

### 2.8 FIRM_CLIENT

**Who:** Taxpayers who are clients of a CPA firm

**Description:** Limited self-service within CPA-managed workflow.

**Primary Responsibilities:**
- View own return status
- Upload requested documents
- Communicate with assigned CPA
- Edit returns when in DRAFT status
- Access client portal

**Key Permissions:**
- View/edit own profile
- View/edit own returns (DRAFT status only)
- Upload documents
- Client portal access
- Message assigned CPA
- **Cannot:** Access professional tools, team features, or filing capabilities

---

## 3. MODULE/FEATURE ACCESS MATRIX

### 3.1 Core Features Matrix

| Feature | Super Admin | Platform Admin | Support | Billing | Partner | Staff | Direct Client | Firm Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-------:|:-----:|:-------------:|:-----------:|
| **Dashboard** | ✓ Platform | ✓ Platform | ✓ Support | ✓ Billing | ✓ Firm | ✓ Personal | ✓ Personal | ✓ Personal |
| **Express Lane Filing** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ | ✓ |
| **Smart Tax Assistant** | ✓ | ✓ | - | - | ✓ᵀ | ✓ᵀ | ✓ᵀ | ✓ᵀ |
| **Guided Filing** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ | ✓ |
| **Document Upload** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ | ✓ |
| **Basic Calculations** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ | ✓ |
| **Basic Reports** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ | ✓ |

**Legend:**
- ✓ = Full Access
- ✓ᵀ = Requires STARTER+ Tier
- - = Not applicable to role

### 3.2 Analysis & Planning Features Matrix

| Feature | Super Admin | Platform Admin | Support | Billing | Partner | Staff | Direct Client | Firm Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-------:|:-----:|:-------------:|:-----------:|
| **Scenario Explorer** | ✓ | ✓ | - | - | ✓ᵀ | ✓ᵀ | ✓ᵀ | ✓ᵀ |
| **Tax Projections** | ✓ | ✓ | - | - | ✓ᵀ | ✓ᵀ | ✓ᵀ | ✓ᵀ |
| **Advanced Analytics** | ✓ | ✓ | - | - | ✓ᴾ | ✗ | ✗ | ✗ |
| **Custom Reports** | ✓ | ✓ | - | - | ✓ᴱ | ✗ | ✗ | ✗ |

**Legend:**
- ✓ᵀ = Requires STARTER+ Tier
- ✓ᴾ = Requires PROFESSIONAL+ Tier
- ✓ᴱ = Requires ENTERPRISE+ Tier

### 3.3 AI Features Matrix

| Feature | Super Admin | Platform Admin | Support | Billing | Partner | Staff | Direct Client | Firm Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-------:|:-----:|:-------------:|:-----------:|
| **AI Tax Chat** | ✓ | ✓ | - | - | ✓ᴾ | ✓ᴾ | ✗ | ✗ |
| **AI Suggestions** | ✓ | ✓ | - | - | ✓ᴾ | ✓ᴾ | ✗ | ✗ |
| **Document AI** | ✓ | ✓ | - | - | ✓ᴾ | ✓ᴾ | ✗ | ✗ |

**Key Insight:** AI features are exclusively for CPA roles (Partner/Staff) and require PROFESSIONAL tier.

### 3.4 Collaboration Features Matrix

| Feature | Super Admin | Platform Admin | Support | Billing | Partner | Staff | Direct Client | Firm Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-------:|:-----:|:-------------:|:-----------:|
| **Client Portal** | ✓ | ✓ | - | - | ✓ᵀ | ✓ᵀ | ✓ | ✓ |
| **Team Collaboration** | ✓ | ✓ | - | - | ✓ᴾ | ✗ | ✗ | ✗ |
| **Client Messaging** | ✓ | ✓ | - | - | ✓ᴾ | ✓ᴾ | ✗ | ✓ᴾ |

**Key Insight:** Team Collaboration is Partner-only. Client Messaging requires PROFESSIONAL tier.

### 3.5 Filing & E-File Features Matrix

| Feature | Super Admin | Platform Admin | Support | Billing | Partner | Staff | Direct Client | Firm Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-------:|:-----:|:-------------:|:-----------:|
| **Create Returns** | ✓ | ✓ | - | - | ✓ | ✓ | ✓ | ✓ |
| **Edit Returns** | ✓ | ✓ | - | - | ✓ | ✓ᴬ | ✓ᴰ | ✓ᴰ |
| **Submit for Review** | ✓ | ✓ | - | - | ✓ | ✓ᴬ | ✗ | ✗ |
| **Review Returns** | ✓ | ✓ | - | - | ✓ | ✓ᴬ | ✗ | ✗ |
| **Approve Returns** | ✓ | ✓ | - | - | ✓ | ✓ᴬ | ✗ | ✗ |
| **E-File Returns** | ✓ | ✓ | - | - | ✓ᵀ | ✓ᵀ | ✗ | ✗ |

**Legend:**
- ✓ᴬ = Assigned clients only
- ✓ᴰ = DRAFT status only (own returns)
- ✓ᵀ = Requires STARTER+ Tier

### 3.6 Admin & Management Features Matrix

| Feature | Super Admin | Platform Admin | Support | Billing | Partner | Staff | Direct Client | Firm Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-------:|:-----:|:-------------:|:-----------:|
| **User Management** | ✓ᴾˡᵃᵗ | ✓ᴾˡᵃᵗ | ✗ | ✗ | ✓ᵀᵉⁿ | ✗ | ✗ | ✗ |
| **Firm Management** | ✓ | ✓ | ✓ᴿ | ✓ᴿ | - | - | - | - |
| **Subscription Mgmt** | ✓ | ✓ | ✗ | ✓ | - | - | - | - |
| **Feature Flags** | ✓ | ✓ | ✗ | ✗ | - | - | - | - |
| **Audit Logs** | ✓ | ✓ | ✓ᴿ | ✗ | ✓ᴾ | ✗ | ✗ | ✗ |

**Legend:**
- ✓ᴾˡᵃᵗ = Platform-wide access
- ✓ᵀᵉⁿ = Tenant (own firm) only
- ✓ᴿ = Read-only access
- ✓ᴾ = Requires PROFESSIONAL+ Tier

### 3.7 Integration Features Matrix

| Feature | Super Admin | Platform Admin | Support | Billing | Partner | Staff | Direct Client | Firm Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-------:|:-----:|:-------------:|:-----------:|
| **QuickBooks** | ✓ | ✓ | - | - | ✓ᴾ | ✗ | ✗ | ✗ |
| **Plaid** | ✓ | ✓ | - | - | ✓ᴱ | ✗ | ✗ | ✗ |
| **API Access** | ✓ | ✓ | - | - | ✓ᴱ | ✗ | ✗ | ✗ |
| **Webhooks** | ✓ | ✓ | - | - | ✓ᴱ | ✗ | ✗ | ✗ |

### 3.8 White-Label Features Matrix

| Feature | Super Admin | Platform Admin | Support | Billing | Partner | Staff | Direct Client | Firm Client |
|---------|:-----------:|:--------------:|:-------:|:-------:|:-------:|:-----:|:-------------:|:-----------:|
| **Custom Branding** | ✓ | ✓ | - | - | ✓ᴾ | ✗ | ✗ | ✗ |
| **Custom Domain** | ✓ | ✓ | - | - | ✓ᴱ | ✗ | ✗ | ✗ |
| **Remove Platform Branding** | ✓ | ✓ | - | - | ✓ᵂ | ✗ | ✗ | ✗ |
| **Custom CSS/JS** | ✓ | ✓ | - | - | ✓ᴱ | ✗ | ✗ | ✗ |

**Legend:**
- ✓ᴾ = PROFESSIONAL+ Tier
- ✓ᴱ = ENTERPRISE+ Tier
- ✓ᵂ = WHITE_LABEL Tier only

---

## 4. DETAILED PERMISSION BREAKDOWN BY ROLE

### 4.1 SUPER_ADMIN Permissions (ALL PERMISSIONS)

**Platform Permissions:**
| Permission Code | Description |
|-----------------|-------------|
| `PLATFORM_VIEW_ALL_FIRMS` | View all CPA firms on platform |
| `PLATFORM_MANAGE_FIRMS` | Create, edit, suspend firms |
| `PLATFORM_IMPERSONATE` | Impersonate any user |
| `PLATFORM_VIEW_SUBSCRIPTIONS` | View all subscription data |
| `PLATFORM_MANAGE_SUBSCRIPTIONS` | Modify subscriptions, refunds |
| `PLATFORM_VIEW_METRICS` | View platform-wide analytics |
| `PLATFORM_MANAGE_FEATURES` | Control feature flags |
| `PLATFORM_VIEW_AUDIT_LOGS` | View all audit logs |
| `PLATFORM_MANAGE_ADMINS` | Add/remove platform admins |

*Plus ALL permissions from other roles*

---

### 4.2 PLATFORM_ADMIN Permissions

**Platform Permissions:**
| Permission Code | Description |
|-----------------|-------------|
| `PLATFORM_VIEW_ALL_FIRMS` | ✓ View all firms |
| `PLATFORM_MANAGE_FIRMS` | ✓ Create, edit, suspend firms |
| `PLATFORM_IMPERSONATE` | ✓ Impersonate for support |
| `PLATFORM_VIEW_SUBSCRIPTIONS` | ✓ View subscriptions |
| `PLATFORM_MANAGE_SUBSCRIPTIONS` | ✓ Modify subscriptions |
| `PLATFORM_VIEW_METRICS` | ✓ View metrics |
| `PLATFORM_MANAGE_FEATURES` | ✓ Control features |
| `PLATFORM_VIEW_AUDIT_LOGS` | ✓ View audit logs |
| `PLATFORM_MANAGE_ADMINS` | ✗ **Cannot manage admins** |

---

### 4.3 SUPPORT Permissions (Read + Impersonate)

| Permission Code | Access Level | Notes |
|-----------------|--------------|-------|
| `PLATFORM_VIEW_ALL_FIRMS` | ✓ Read | View firm data |
| `PLATFORM_IMPERSONATE` | ✓ Execute | For troubleshooting |
| `PLATFORM_VIEW_SUBSCRIPTIONS` | ✓ Read | View subscription status |
| `PLATFORM_VIEW_METRICS` | ✓ Read | View metrics |
| `PLATFORM_VIEW_AUDIT_LOGS` | ✓ Read | Debug issues |

**Cannot:** Modify firms, manage subscriptions, manage features

---

### 4.4 BILLING Permissions (Finance Focus)

| Permission Code | Access Level | Notes |
|-----------------|--------------|-------|
| `PLATFORM_VIEW_ALL_FIRMS` | ✓ Read | Billing context |
| `PLATFORM_VIEW_SUBSCRIPTIONS` | ✓ Read | View all subscriptions |
| `PLATFORM_MANAGE_SUBSCRIPTIONS` | ✓ Write | Process changes |
| `PLATFORM_VIEW_METRICS` | ✓ Read | Revenue metrics |

**Cannot:** Impersonate, manage features, view audit logs

---

### 4.5 PARTNER Permissions (Full Firm Control)

**Firm Management:**
| Permission Code | Description |
|-----------------|-------------|
| `FIRM_VIEW_SETTINGS` | View firm configuration |
| `FIRM_MANAGE_SETTINGS` | Edit firm configuration |
| `FIRM_MANAGE_BRANDING` | Update logo, colors, theme |
| `FIRM_VIEW_ANALYTICS` | View firm analytics |
| `FIRM_VIEW_BILLING` | View invoices, payments |
| `FIRM_MANAGE_BILLING` | Update payment methods, change plan |

**Team Management:**
| Permission Code | Description |
|-----------------|-------------|
| `TEAM_VIEW` | View all team members |
| `TEAM_INVITE` | Send team invitations |
| `TEAM_MANAGE` | Edit roles, permissions |
| `TEAM_REMOVE` | Remove team members |

**Client Management:**
| Permission Code | Description |
|-----------------|-------------|
| `CLIENT_VIEW_ALL` | View all firm clients |
| `CLIENT_CREATE` | Add new clients |
| `CLIENT_EDIT` | Update client info |
| `CLIENT_ARCHIVE` | Archive/unarchive |
| `CLIENT_ASSIGN` | Assign to staff |

**Return Management:**
| Permission Code | Description |
|-----------------|-------------|
| `RETURN_VIEW_ALL` | View all firm returns |
| `RETURN_CREATE` | Start new returns |
| `RETURN_EDIT` | Edit return data |
| `RETURN_SUBMIT` | Submit for review |
| `RETURN_REVIEW` | Review submissions |
| `RETURN_APPROVE` | Approve for filing |
| `RETURN_RUN_SCENARIOS` | Run tax scenarios |
| `RETURN_GENERATE_ADVISORY` | Generate advisory reports |

**Documents:**
| Permission Code | Description |
|-----------------|-------------|
| `DOCUMENT_VIEW` | View all documents |
| `DOCUMENT_UPLOAD` | Upload documents |
| `DOCUMENT_DELETE` | Delete documents |

---

### 4.6 STAFF Permissions (Assigned Clients Only)

**Firm (Read Only):**
| Permission Code | Description |
|-----------------|-------------|
| `FIRM_VIEW_SETTINGS` | View firm configuration |
| `FIRM_VIEW_ANALYTICS` | View firm analytics |

**Team (Read Only):**
| Permission Code | Description |
|-----------------|-------------|
| `TEAM_VIEW` | View team members |

**Client (Assigned Only):**
| Permission Code | Description | Scope |
|-----------------|-------------|-------|
| `CLIENT_VIEW_OWN` | View assigned clients | **Assigned only** |
| `CLIENT_CREATE` | Add new clients | Auto-assigned to self |
| `CLIENT_EDIT` | Update client info | **Assigned only** |

**Return (Assigned Only):**
| Permission Code | Description | Scope |
|-----------------|-------------|-------|
| `RETURN_VIEW_OWN` | View returns | **Assigned only** |
| `RETURN_CREATE` | Create returns | For assigned clients |
| `RETURN_EDIT` | Edit returns | **Assigned only** |
| `RETURN_SUBMIT` | Submit for review | **Assigned only** |
| `RETURN_RUN_SCENARIOS` | Run scenarios | **Assigned only** |
| `RETURN_GENERATE_ADVISORY` | Generate advisories | **Assigned only** |

**Documents:**
| Permission Code | Description | Restriction |
|-----------------|-------------|-------------|
| `DOCUMENT_VIEW` | View documents | For assigned clients |
| `DOCUMENT_UPLOAD` | Upload documents | For assigned clients |
| ~~`DOCUMENT_DELETE`~~ | **Cannot delete** | N/A |

**Cannot:**
- Manage team members
- Access billing
- Assign clients to others
- Approve returns
- Delete documents

---

### 4.7 DIRECT_CLIENT Permissions (Self-Service)

| Permission Code | Description | Scope |
|-----------------|-------------|-------|
| `SELF_VIEW_RETURN` | View own returns | Own only |
| `SELF_EDIT_RETURN` | Edit own returns | DRAFT status only |
| `SELF_UPLOAD_DOCS` | Upload documents | Own account |
| `SELF_VIEW_STATUS` | View return status | Own only |
| `DOCUMENT_VIEW` | View documents | Own only |
| `DOCUMENT_UPLOAD` | Upload documents | Own only |

**Cannot:**
- Access AI Chat
- E-File returns
- View other users' data
- Access team features
- Review/approve returns

---

### 4.8 FIRM_CLIENT Permissions (CPA-Managed)

| Permission Code | Description | Scope |
|-----------------|-------------|-------|
| `SELF_VIEW_RETURN` | View own returns | Own only |
| `SELF_EDIT_RETURN` | Edit own returns | DRAFT status only |
| `SELF_VIEW_STATUS` | View return status | Own only |
| `SELF_UPLOAD_DOCS` | Upload documents | Own account |
| `DOCUMENT_VIEW` | View documents | Own only |
| `DOCUMENT_UPLOAD` | Upload documents | Own only |

**Portal Features:**
- Access client portal
- Message assigned CPA
- View document requests
- Upload requested documents

**Cannot:**
- File returns directly
- Access professional tools
- View other clients' data

---

## 5. SUBSCRIPTION TIER FEATURE GATING

### 5.1 Subscription Tiers Overview

| Tier | Target Audience | Price Point |
|------|-----------------|-------------|
| **FREE** | Trial users, evaluation | $0/month |
| **STARTER** | Small practices, DIY clients | Entry-level |
| **PROFESSIONAL** | Growing CPA firms | Mid-tier |
| **ENTERPRISE** | Large firms, integrations | Premium |
| **WHITE_LABEL** | Resellers, franchise | Custom |

### 5.2 Feature Availability by Tier

#### FREE Tier
```
┌─────────────────────────────────────────────────────────────┐
│                        FREE TIER                            │
├─────────────────────────────────────────────────────────────┤
│ ✓ Dashboard                    ✓ Document Upload            │
│ ✓ Express Lane Filing          ✓ Basic Calculations         │
│ ✓ Guided Filing                ✓ Basic Reports              │
├─────────────────────────────────────────────────────────────┤
│ LIMITS:                                                     │
│ • 5 returns/month              • 1 CPA max                  │
│ • 10 clients/CPA               • 1 GB storage               │
├─────────────────────────────────────────────────────────────┤
│ DISABLED:                                                   │
│ ✗ Smart Tax    ✗ AI Chat       ✗ Scenarios    ✗ Projections │
│ ✗ Integrations ✗ Custom Domain ✗ API Access                 │
└─────────────────────────────────────────────────────────────┘
```

#### STARTER Tier
```
┌─────────────────────────────────────────────────────────────┐
│                      STARTER TIER                           │
├─────────────────────────────────────────────────────────────┤
│ Everything in FREE, plus:                                   │
├─────────────────────────────────────────────────────────────┤
│ ✓ Smart Tax Assistant          ✓ E-File Returns             │
│ ✓ Scenario Explorer            ✓ Tax Projections            │
│ ✓ Client Portal               ✓ User Management             │
├─────────────────────────────────────────────────────────────┤
│ LIMITS:                                                     │
│ • 50 returns/month             • 3 CPAs max                 │
│ • 50 clients/CPA               • 10 GB storage              │
├─────────────────────────────────────────────────────────────┤
│ STILL DISABLED:                                             │
│ ✗ AI Chat    ✗ QuickBooks     ✗ Custom Domain  ✗ API Access │
└─────────────────────────────────────────────────────────────┘
```

#### PROFESSIONAL Tier
```
┌─────────────────────────────────────────────────────────────┐
│                    PROFESSIONAL TIER                        │
├─────────────────────────────────────────────────────────────┤
│ Everything in STARTER, plus:                                │
├─────────────────────────────────────────────────────────────┤
│ ✓ AI Tax Chat                  ✓ AI Suggestions             │
│ ✓ Document AI                  ✓ Advanced Analytics         │
│ ✓ Team Collaboration           ✓ Client Messaging           │
│ ✓ QuickBooks Integration       ✓ Custom Branding            │
│ ✓ Audit Logs                                                │
├─────────────────────────────────────────────────────────────┤
│ LIMITS:                                                     │
│ • 200 returns/month            • 10 CPAs max                │
│ • 200 clients/CPA              • 50 GB storage              │
├─────────────────────────────────────────────────────────────┤
│ STILL DISABLED:                                             │
│ ✗ Custom Domain  ✗ API Access  ✗ Webhooks  ✗ Plaid          │
└─────────────────────────────────────────────────────────────┘
```

#### ENTERPRISE Tier
```
┌─────────────────────────────────────────────────────────────┐
│                     ENTERPRISE TIER                         │
├─────────────────────────────────────────────────────────────┤
│ Everything in PROFESSIONAL, plus:                           │
├─────────────────────────────────────────────────────────────┤
│ ✓ Custom Domain                ✓ API Access                 │
│ ✓ Webhooks                     ✓ Plaid Integration          │
│ ✓ Custom Reports               ✓ Advanced Security          │
│ ✓ Custom CSS/JavaScript        ✓ Custom Email Templates     │
│ ✓ CPA Collaboration (multi-CPA on same return)              │
├─────────────────────────────────────────────────────────────┤
│ LIMITS:                                                     │
│ • Unlimited returns            • Unlimited CPAs             │
│ • Unlimited clients            • 500 GB storage             │
├─────────────────────────────────────────────────────────────┤
│ STILL SHOWS "Powered by CA4CPA" BRANDING                    │
└─────────────────────────────────────────────────────────────┘
```

#### WHITE_LABEL Tier
```
┌─────────────────────────────────────────────────────────────┐
│                     WHITE_LABEL TIER                        │
├─────────────────────────────────────────────────────────────┤
│ Everything in ENTERPRISE, plus:                             │
├─────────────────────────────────────────────────────────────┤
│ ✓ Remove ALL Platform Branding                              │
│ ✓ Complete White-Label Solution                             │
│ ✓ All Integrations (Stripe, QuickBooks, Plaid)              │
│ ✓ E-Signature Support                                       │
│ ✓ Advanced OCR & Document Intelligence                      │
│ ✓ Multi-CPA Support with Full Dashboard                     │
│ ✓ Client Portal Customization                               │
├─────────────────────────────────────────────────────────────┤
│ LIMITS:                                                     │
│ • Unlimited everything                                      │
│ • Unlimited storage                                         │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Tier Comparison Matrix

| Feature | FREE | STARTER | PROFESSIONAL | ENTERPRISE | WHITE_LABEL |
|---------|:----:|:-------:|:------------:|:----------:|:-----------:|
| **Express Lane** | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Guided Filing** | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Basic Calculations** | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Smart Tax** | - | ✓ | ✓ | ✓ | ✓ |
| **E-File** | - | ✓ | ✓ | ✓ | ✓ |
| **Scenarios** | - | ✓ | ✓ | ✓ | ✓ |
| **Projections** | - | ✓ | ✓ | ✓ | ✓ |
| **Client Portal** | - | ✓ | ✓ | ✓ | ✓ |
| **AI Chat** | - | - | ✓ | ✓ | ✓ |
| **AI Suggestions** | - | - | ✓ | ✓ | ✓ |
| **Team Collaboration** | - | - | ✓ | ✓ | ✓ |
| **Client Messaging** | - | - | ✓ | ✓ | ✓ |
| **QuickBooks** | - | - | ✓ | ✓ | ✓ |
| **Custom Branding** | - | - | ✓ | ✓ | ✓ |
| **Audit Logs** | - | - | ✓ | ✓ | ✓ |
| **Advanced Analytics** | - | - | ✓ | ✓ | ✓ |
| **Custom Domain** | - | - | - | ✓ | ✓ |
| **API Access** | - | - | - | ✓ | ✓ |
| **Webhooks** | - | - | - | ✓ | ✓ |
| **Plaid** | - | - | - | ✓ | ✓ |
| **Custom Reports** | - | - | - | ✓ | ✓ |
| **Advanced Security** | - | - | - | ✓ | ✓ |
| **Remove Branding** | - | - | - | - | ✓ |
| **E-Signature** | - | - | - | - | ✓ |

### 5.4 Usage Limits by Tier

| Limit | FREE | STARTER | PROFESSIONAL | ENTERPRISE | WHITE_LABEL |
|-------|:----:|:-------:|:------------:|:----------:|:-----------:|
| Returns/Month | 5 | 50 | 200 | Unlimited | Unlimited |
| Max CPAs | 1 | 3 | 10 | Unlimited | Unlimited |
| Clients/CPA | 10 | 50 | 200 | Unlimited | Unlimited |
| Storage (GB) | 1 | 10 | 50 | 500 | Unlimited |

---

## 6. PERMISSION CATEGORIES & DEFINITIONS

### 6.1 Permission Scopes

| Scope | Description | Who Uses |
|-------|-------------|----------|
| `PLATFORM` | Platform-wide operations | Super Admin, Platform Admin |
| `TENANT` | Operations within a single tenant | Partner, Staff |
| `CPA` | CPA-specific operations | Partner, Staff |
| `CLIENT` | Client-specific operations | All client roles |
| `SELF` | User's own data only | All users |

### 6.2 Permission Categories

#### Platform Permissions (9 total)
- Firm management (view all, manage, delete)
- Subscription management (view, manage)
- System configuration
- Audit log access
- Admin management (super_admin only)
- Feature flag control
- Impersonation

#### Firm Permissions (6 total)
- Settings (view, manage)
- Branding (view, manage)
- Analytics (view)
- Billing (view, manage)

#### Team Permissions (4 total)
- View team
- Invite members
- Manage members
- Remove members

#### Client Permissions (6 total)
- View own clients
- View all clients
- Create clients
- Edit clients
- Archive clients
- Assign clients

#### Return Permissions (9 total)
- View own returns
- View all returns
- Create returns
- Edit returns
- Submit for review
- Review returns
- Approve returns
- Run scenarios
- Generate advisories

#### Document Permissions (3 total)
- View documents
- Upload documents
- Delete documents

#### Self-Service Permissions (4 total)
- View own return
- Edit own return
- Upload own docs
- View status

---

## 7. ACCESS CONTROL DECISION LOGIC

### 7.1 Access Check Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ACCESS CHECK ALGORITHM                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. AUTHENTICATION CHECK                                          │
│    Is user authenticated?                                        │
│    ├── NO  → 401 Unauthorized                                    │
│    └── YES → Continue                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. ROLE CHECK                                                    │
│    Does feature allow this role?                                 │
│    ├── NO  → 403 Forbidden (role not allowed)                    │
│    └── YES → Continue                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. PERMISSION CHECK                                              │
│    Does role have required permission?                           │
│    ├── NO  → 403 Forbidden (missing permission)                  │
│    └── YES → Continue                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. SUBSCRIPTION TIER CHECK                                       │
│    Is tenant's tier sufficient?                                  │
│    ├── NO  → 403 Forbidden (upgrade required)                    │
│    └── YES → Continue                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. FEATURE FLAG CHECK                                            │
│    Is feature enabled for this tenant?                           │
│    ├── NO  → 403 Forbidden (feature disabled)                    │
│    └── YES → Continue                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. OWNERSHIP/ASSIGNMENT CHECK (if required)                      │
│    Does user own resource or is assigned?                        │
│    ├── NO  → 403 Forbidden                                       │
│    └── YES → ACCESS GRANTED ✓                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Permission Resolution Order

1. **Super Admin Bypass:** If role = SUPER_ADMIN, grant access immediately
2. **Platform Admin Check:** Platform admins bypass tenant-level checks
3. **Role Restriction:** Check if feature has `allowed_roles` constraint
4. **Permission Lookup:** Check role → permission mapping
5. **Tier Validation:** Validate tenant subscription tier
6. **Feature Flag:** Check if feature flag is enabled for tenant
7. **Ownership/Assignment:** For scoped permissions, verify ownership

---

## 8. DATA VISIBILITY RULES

### 8.1 Client Data Visibility

| Role | Can See Clients |
|------|-----------------|
| SUPER_ADMIN | All clients across all firms |
| PLATFORM_ADMIN | All clients across all firms |
| SUPPORT | All clients (read-only, via impersonation) |
| BILLING | No direct client access |
| PARTNER | All clients within their firm |
| STAFF | Only assigned clients |
| DIRECT_CLIENT | Only own profile |
| FIRM_CLIENT | Only own profile |

### 8.2 Return Data Visibility

| Role | Can See Returns |
|------|-----------------|
| SUPER_ADMIN | All returns across all firms |
| PLATFORM_ADMIN | All returns across all firms |
| SUPPORT | All returns (read-only) |
| BILLING | No direct return access |
| PARTNER | All returns within their firm |
| STAFF | Only returns for assigned clients |
| DIRECT_CLIENT | Only own returns |
| FIRM_CLIENT | Only own returns |

### 8.3 Document Data Visibility

| Role | Can See Documents | Can Delete |
|------|-------------------|------------|
| SUPER_ADMIN | All | Yes |
| PLATFORM_ADMIN | All | Yes |
| SUPPORT | All (read-only) | No |
| BILLING | No access | No |
| PARTNER | All firm documents | Yes |
| STAFF | Assigned client docs | No |
| DIRECT_CLIENT | Own documents | No |
| FIRM_CLIENT | Own documents | No |

### 8.4 Tenant Isolation

```
┌─────────────────────────────────────────────────────────────────┐
│                     TENANT ISOLATION MODEL                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐│
│  │   CPA Firm A    │   │   CPA Firm B    │   │   CPA Firm C    ││
│  │   (Tenant 1)    │   │   (Tenant 2)    │   │   (Tenant 3)    ││
│  ├─────────────────┤   ├─────────────────┤   ├─────────────────┤│
│  │ Partner A       │   │ Partner B       │   │ Partner C       ││
│  │ Staff A1, A2    │   │ Staff B1        │   │ Staff C1, C2, C3││
│  │ Client A1-A50   │   │ Client B1-B20   │   │ Client C1-C100  ││
│  │ Returns A       │   │ Returns B       │   │ Returns C       ││
│  │ Documents A     │   │ Documents B     │   │ Documents C     ││
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘│
│           │                     │                     │         │
│           │  CANNOT SEE EACH OTHER'S DATA             │         │
│           │  (Complete Isolation)                     │         │
│           │                     │                     │         │
├───────────┼─────────────────────┼─────────────────────┼─────────┤
│           │                     │                     │         │
│           ▼                     ▼                     ▼         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              PLATFORM LEVEL (CA4CPA Internal)               ││
│  │  Super Admin / Platform Admin / Support / Billing           ││
│  │                                                              ││
│  │  CAN ACCESS ALL TENANTS (within permission limits)          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. FEATURE-SPECIFIC BEHAVIOR BY ROLE

### 9.1 Express Lane Filing

| Role | Behavior |
|------|----------|
| **PARTNER** | Can use for any client, sees all firm data |
| **STAFF** | Can use for assigned clients only |
| **DIRECT_CLIENT** | Can use for own return only |
| **FIRM_CLIENT** | Can use for own return only (via portal) |

### 9.2 AI Chat

| Role | Behavior |
|------|----------|
| **PARTNER** | Full access, can ask about any client |
| **STAFF** | Access limited to assigned client context |
| **DIRECT_CLIENT** | **No access** |
| **FIRM_CLIENT** | **No access** |

### 9.3 Team Collaboration

| Role | Behavior |
|------|----------|
| **PARTNER** | Full team management, task assignment |
| **STAFF** | Can view assigned tasks, add notes |
| **DIRECT_CLIENT** | **No access** |
| **FIRM_CLIENT** | **No access** |

### 9.4 Client Messaging

| Role | Behavior |
|------|----------|
| **PARTNER** | Can message any client |
| **STAFF** | Can message assigned clients |
| **DIRECT_CLIENT** | **No messaging** (no CPA assigned) |
| **FIRM_CLIENT** | Can message assigned CPA |

### 9.5 E-File Returns

| Role | Behavior |
|------|----------|
| **PARTNER** | Can e-file any firm return after approval |
| **STAFF** | Can e-file assigned returns after approval |
| **DIRECT_CLIENT** | **Cannot e-file** (must use CPA) |
| **FIRM_CLIENT** | **Cannot e-file** (CPA handles) |

### 9.6 Audit Logs

| Role | Behavior |
|------|----------|
| **SUPER_ADMIN** | Full platform-wide audit logs |
| **PLATFORM_ADMIN** | Full platform-wide audit logs |
| **SUPPORT** | Read-only platform audit logs |
| **PARTNER** | Firm-specific audit logs only |
| **STAFF** | **No access** |
| **Clients** | **No access** |

---

## 10. SECURITY & COMPLIANCE CONSIDERATIONS

### 10.1 Role Escalation Prevention

| Rule | Enforcement |
|------|-------------|
| Partner cannot promote to Platform Admin | System-enforced |
| Staff cannot promote to Partner | Requires Partner action |
| Clients cannot gain CPA permissions | System-enforced |
| Only Super Admin can create Platform Admins | System-enforced |

### 10.2 Audit Trail Requirements

| Action | Logged For |
|--------|-----------|
| Login/Logout | All roles |
| Permission changes | All roles |
| Data access | All roles |
| Impersonation | Platform roles only |
| Configuration changes | Admin roles |
| Billing changes | Billing/Admin roles |

### 10.3 Data Access Logging

All data access is logged with:
- User ID and role
- Resource accessed
- Action performed
- Timestamp
- IP address
- Impersonation context (if any)

### 10.4 Session Security

| Feature | Implementation |
|---------|----------------|
| Session timeout | Configurable per tier |
| Concurrent sessions | Limited based on tier |
| IP whitelisting | Enterprise+ only |
| 2FA requirement | Enterprise+ configurable |
| SSO integration | Enterprise+ only |

---

## CORRECTIONS FROM ORIGINAL DOCUMENT

Based on code validation, the following corrections were made:

### Corrected Mappings:

| Original | Corrected | Reason |
|----------|-----------|--------|
| AI Chat: Direct Client ✗ | Confirmed ✗ | AI features are CPA-only (PROFESSIONAL+ tier) |
| AI Chat: Firm Client ✗ | Confirmed ✗ | AI features are CPA-only |
| Team Collaboration: Staff ✗ | Corrected: Staff can view tasks | Staff has view-only team access |
| Client Messaging: Direct Client ✗ | Confirmed ✗ | No CPA assigned |
| Client Messaging: Firm Client ✓ | Confirmed ✓ | Can message assigned CPA |
| E-File: Direct Client ✗ | Confirmed ✗ | Only CPA roles can e-file |
| E-File: Firm Client ✗ | Confirmed ✗ | Only CPA roles can e-file |

### Additional Clarifications:

1. **Smart Tax** requires STARTER tier (not FREE)
2. **Scenario Explorer** and **Tax Projections** require STARTER tier
3. **AI Chat**, **Team Collaboration**, **Client Messaging** require PROFESSIONAL tier
4. **API Access**, **Custom Domain**, **Webhooks** require ENTERPRISE tier
5. **Remove Branding** requires WHITE_LABEL tier only

---

*Document validated against codebase: 2026-01-28*
*Source files: src/rbac/roles.py, src/rbac/permissions.py, src/rbac/enhanced_permissions.py, src/rbac/feature_access_control.py, src/database/tenant_models.py*
