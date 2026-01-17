# V2.0 Architecture and Planning Document

## Tax Decision Intelligence Platform - Future Roadmap

**Document Version**: 1.0
**Status**: Planning (Not Yet Implemented)
**Created**: Post-Freeze V1.0
**Implementation Timeline**: 14 weeks (phased)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scope, Reliance, and Professional Use Statement](#2-scope-reliance-and-professional-use-statement)
3. [Enterprise Architecture Blueprint](#3-enterprise-architecture-blueprint)
4. [Admin Panel Architecture](#4-admin-panel-architecture)
5. [CPA Practice Portal Architecture](#5-cpa-practice-portal-architecture)
6. [Client Portal Architecture](#6-client-portal-architecture)
7. [Core Engine Isolation](#7-core-engine-isolation)
8. [Identity and Access Control Services](#8-identity-and-access-control-services)
9. [Database Strategy](#9-database-strategy)
10. [Security Architecture](#10-security-architecture)
11. [Implementation Timeline](#11-implementation-timeline)
12. [Technical Specifications](#12-technical-specifications)

---

## 1. Executive Summary

### Current State (V1.0 - Frozen)

The platform currently provides:
- CPA-grade tax decision intelligence
- Document OCR and classification (ML-based)
- Tax optimization scenario analysis
- Smart insights with IRC citations
- Session-based persistence
- Single-user deployment model

### V2.0 Vision

Transform into an enterprise-grade, multi-tenant SaaS platform with:
- **Separate Service Boundaries**: Core Engine, Admin Panel, CPA Portal, Client Portal
- **Unified Identity**: Single authentication across all services
- **RBAC + ABAC**: Role-Based and Attribute-Based Access Control
- **Multi-Tenant Architecture**: Full tenant isolation with BYOK support
- **White-Label Ready**: Configurable branding per tenant

### Key Architectural Principles

1. **Core Engine Isolation**: Tax calculation engine has NO direct external access
2. **Defense in Depth**: Multiple security layers at every boundary
3. **Identity vs Authorization Separation**: Authentication centralized, authorization contextual
4. **Audit Everything**: Complete audit trail for CPA compliance
5. **Graceful Degradation**: Fallback chains for all external dependencies

---

## 2. Scope, Reliance, and Professional Use Statement

### 2.1 Platform Purpose

**Tax Decision Intelligence Platform** is a CPA Decision Intelligence System designed to augment—not replace—professional tax judgment. It provides scenario modeling, optimization insights, and compliance guidance under direct CPA supervision.

### 2.2 Intended Use

| Intended | NOT Intended |
|----------|--------------|
| CPA-supervised tax planning | Unsupervised consumer tax filing |
| Professional advisory support | Direct IRS submission |
| Decision scenario modeling | Legal/audit representation |
| Client education materials | Investment advice |

### 2.3 What the Platform Does

- **Calculates**: Standard deductions, credits, and optimization scenarios using current IRC rules
- **Flags**: Complex situations requiring manual CPA review (dispositions, passive losses, at-risk limits)
- **Provides**: IRC citations and professional reference materials
- **Tracks**: Complete audit trail of all calculations and decisions
- **Integrates**: Document extraction with mandatory human verification

### 2.4 What the Platform Does NOT Do

- File tax returns with any authority
- Provide legal advice or audit representation
- Make final determinations on ambiguous tax positions
- Replace professional judgment on complex transactions
- Guarantee accuracy of OCR-extracted data

### 2.5 Flagged Scenarios Requiring Manual CPA Review

The platform automatically flags and blocks calculation for:

| Scenario | System Behavior | Reason |
|----------|-----------------|--------|
| Asset Dispositions | `DispositionRequiresManualReviewError` | Gain/loss, Section 1245/1250 recapture requires manual calculation |
| Farm Losses > $10,000 | Warning with IRC §465 reference | At-risk rules may limit deduction |
| Schedule K-1 Documents | Manual entry required notice | Complex basis, passive activity, at-risk calculations |
| 1099-B Transactions | Manual entry required notice | Cost basis, wash sales, holding period verification |
| 1099-R Distributions | Manual entry required notice | Taxability, early withdrawal, Roth characterization |
| 1098 Series Forms | Manual entry required notice | Limitation calculations, AMT adjustments |

### 2.6 Data Handling and Privacy

- All data encrypted at rest (AES-256) and in transit (TLS 1.3)
- SSN hashing uses SHA-256 (limitations documented in codebase)
- No data shared with third parties except OpenAI API for document classification
- Tenant data isolation enforced at database schema level
- BYOK option for tenants requiring their own OpenAI API keys

### 2.7 Limitation of Liability

This platform is a decision-support tool. All outputs require CPA review before client delivery. The platform provider assumes no liability for:
- Tax positions taken based on platform outputs
- Errors in OCR-extracted data not verified by CPA
- Complex scenarios that bypass flagging logic
- Third-party API failures or inaccuracies

**CPA retains full professional responsibility for all client work product.**

---

## 3. Enterprise Architecture Blueprint

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOAD BALANCER / CDN                            │
│                           (CloudFlare / AWS ALB)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               API GATEWAY                                    │
│                    (Rate Limiting, Auth, Routing, CORS)                     │
│                         Kong / AWS API Gateway                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
          ▼                            ▼                            ▼
┌─────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
│  IDENTITY SVC   │      │   ACCESS CONTROL    │      │    EVENT BUS        │
│                 │      │      SERVICE        │      │                     │
│ - Authentication│      │ - RBAC Engine       │      │ - Async Events      │
│ - Token Mgmt    │      │ - ABAC Engine       │      │ - Webhooks          │
│ - SSO/SAML      │      │ - Policy Decisions  │      │ - Notifications     │
│ - MFA           │      │ - Audit Logging     │      │                     │
└─────────────────┘      └─────────────────────┘      └─────────────────────┘
          │                            │                            │
          └────────────────────────────┼────────────────────────────┘
                                       │
     ┌─────────────────┬───────────────┼───────────────┬─────────────────┐
     │                 │               │               │                 │
     ▼                 ▼               ▼               ▼                 ▼
┌─────────┐     ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐
│  ADMIN  │     │    CPA    │   │  CLIENT   │   │   CORE    │   │  BILLING  │
│ SERVICE │     │  SERVICE  │   │  SERVICE  │   │  ENGINE   │   │  SERVICE  │
│         │     │           │   │           │   │           │   │           │
│/admin/* │     │ /cpa/*    │   │/client/* │   │ INTERNAL  │   │/billing/* │
│         │     │           │   │           │   │   ONLY    │   │           │
└─────────┘     └───────────┘   └───────────┘   └───────────┘   └───────────┘
     │                 │               │               ▲                 │
     │                 │               │               │                 │
     └─────────────────┴───────────────┴───────────────┴─────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATABASE LAYER                                    │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Identity   │  │    Admin     │  │  CPA/Client  │  │ Core Engine  │   │
│  │    Schema    │  │    Schema    │  │    Schema    │  │    Schema    │   │
│  │              │  │              │  │ (per tenant) │  │  (isolated)  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                             │
│                         PostgreSQL with Row-Level Security                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Service Boundaries

| Service | Responsibility | External Access | Database |
|---------|---------------|-----------------|----------|
| Identity Service | Authentication, tokens, SSO | Yes (public) | identity_schema |
| Access Control | Authorization decisions | Yes (via gateway) | access_schema |
| Admin Service | Tenant management, billing, config | Yes (admin users) | admin_schema |
| CPA Service | Practice management, clients, reports | Yes (CPA users) | tenant_schema |
| Client Service | Limited client-facing portal | Yes (clients) | tenant_schema |
| Core Engine | Tax calculations, ML, optimization | **NO** (internal only) | core_schema |
| Billing Service | Usage tracking, invoicing | Yes (via gateway) | billing_schema |
| Event Bus | Async communication | No (internal) | events_schema |

### 3.3 Monorepo Directory Structure

```
jorss-gbo/
├── services/
│   ├── identity/                    # Authentication service
│   │   ├── src/
│   │   │   ├── api/
│   │   │   ├── models/
│   │   │   ├── services/
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   ├── access-control/              # Authorization service
│   │   ├── src/
│   │   │   ├── api/
│   │   │   ├── engines/
│   │   │   │   ├── rbac_engine.py
│   │   │   │   └── abac_engine.py
│   │   │   ├── policies/
│   │   │   └── main.py
│   │   ├── tests/
│   │   └── Dockerfile
│   │
│   ├── admin/                       # Admin panel service
│   │   ├── src/
│   │   │   ├── api/
│   │   │   ├── models/
│   │   │   ├── services/
│   │   │   └── main.py
│   │   ├── tests/
│   │   └── Dockerfile
│   │
│   ├── cpa-portal/                  # CPA practice management
│   │   ├── src/
│   │   │   ├── api/
│   │   │   ├── models/
│   │   │   ├── services/
│   │   │   ├── workflows/
│   │   │   └── main.py
│   │   ├── tests/
│   │   └── Dockerfile
│   │
│   ├── client-portal/               # Client-facing portal
│   │   ├── src/
│   │   │   ├── api/
│   │   │   ├── models/
│   │   │   └── main.py
│   │   ├── tests/
│   │   └── Dockerfile
│   │
│   ├── core-engine/                 # Tax calculation engine (ISOLATED)
│   │   ├── src/                     # Current src/ folder contents
│   │   │   ├── models/
│   │   │   ├── services/
│   │   │   ├── agent/
│   │   │   ├── ml/
│   │   │   └── internal_api.py      # Service-to-service only
│   │   ├── tests/
│   │   └── Dockerfile
│   │
│   ├── billing/                     # Usage and billing
│   │   ├── src/
│   │   └── Dockerfile
│   │
│   └── event-bus/                   # Async messaging
│       ├── src/
│       └── Dockerfile
│
├── packages/                        # Shared libraries
│   ├── common/                      # Shared utilities
│   │   ├── auth/
│   │   ├── logging/
│   │   ├── errors/
│   │   └── types/
│   │
│   ├── db-models/                   # Shared database models
│   │   └── base.py
│   │
│   └── api-client/                  # Service-to-service client
│       └── core_engine_client.py
│
├── infrastructure/
│   ├── docker/
│   │   └── docker-compose.yml
│   ├── kubernetes/
│   │   ├── base/
│   │   └── overlays/
│   ├── terraform/
│   └── scripts/
│
├── docs/
│   ├── V2_ARCHITECTURE_AND_PLANNING.md
│   ├── api/
│   └── runbooks/
│
└── tools/
    ├── migrations/
    └── scripts/
```

---

## 4. Admin Panel Architecture

### 4.1 Overview

The Admin Panel provides platform-wide management capabilities for super administrators and tenant administrators.

### 4.2 Data Models

```python
# services/admin/src/models/tenant.py

class Tenant(BaseModel):
    """Multi-tenant organization"""
    __tablename__ = "tenants"

    id: UUID
    name: str                           # "Acme Tax Services"
    slug: str                           # "acme-tax" (unique, URL-safe)
    status: TenantStatus                # active, suspended, trial, cancelled
    plan_id: UUID                       # Foreign key to Plan

    # Configuration
    settings: Dict[str, Any]            # JSONB tenant settings
    branding: Dict[str, Any]            # JSONB white-label config
    feature_flags: Dict[str, bool]      # JSONB feature toggles

    # Limits
    max_users: int
    max_clients: int
    max_storage_gb: int

    # Dates
    trial_ends_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class TenantStatus(str, Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class Plan(BaseModel):
    """Subscription plan definition"""
    __tablename__ = "plans"

    id: UUID
    name: str                           # "Professional", "Enterprise"
    code: str                           # "pro", "enterprise"

    # Pricing
    price_monthly: Decimal
    price_annual: Decimal

    # Limits
    included_users: int
    included_clients: int
    included_api_calls: int
    included_storage_gb: int

    # Features
    features: List[str]                 # ["ml_classification", "bulk_upload", ...]

    is_active: bool
    created_at: datetime


class APIKeyConfig(BaseModel):
    """Tenant API key configuration (BYOK support)"""
    __tablename__ = "api_key_configs"

    id: UUID
    tenant_id: UUID

    # OpenAI Configuration
    openai_api_key_encrypted: Optional[str]  # Encrypted with tenant-specific key
    openai_model_preference: str             # "gpt-4o-mini", "gpt-4o"
    use_platform_key: bool                   # True = use platform key, False = BYOK

    # Rate Limits (for BYOK)
    monthly_token_limit: Optional[int]
    daily_token_limit: Optional[int]

    created_at: datetime
    updated_at: datetime


class UsageRecord(BaseModel):
    """Usage tracking for billing"""
    __tablename__ = "usage_records"

    id: UUID
    tenant_id: UUID

    # Period
    period_start: date
    period_end: date

    # Metrics
    api_calls: int
    ai_tokens_used: int
    documents_processed: int
    storage_used_bytes: int
    active_users: int
    active_clients: int

    # Costs (if BYOK, this is $0)
    ai_cost_usd: Decimal

    created_at: datetime
```

### 4.3 Admin Services

```python
# services/admin/src/services/tenant_service.py

class TenantService:
    """Tenant lifecycle management"""

    async def create_tenant(self, data: TenantCreate) -> Tenant:
        """Create new tenant with default configuration"""

    async def update_tenant(self, tenant_id: UUID, data: TenantUpdate) -> Tenant:
        """Update tenant settings, limits, or status"""

    async def suspend_tenant(self, tenant_id: UUID, reason: str) -> Tenant:
        """Suspend tenant (e.g., non-payment, abuse)"""

    async def reactivate_tenant(self, tenant_id: UUID) -> Tenant:
        """Reactivate suspended tenant"""

    async def delete_tenant(self, tenant_id: UUID) -> None:
        """Soft delete tenant and schedule data purge"""

    async def get_tenant_usage(self, tenant_id: UUID, period: str) -> UsageRecord:
        """Get usage metrics for billing period"""


# services/admin/src/services/api_key_service.py

class APIKeyService:
    """BYOK API key management with encryption"""

    def __init__(self, encryption_service: EncryptionService):
        self._encryption = encryption_service

    async def set_openai_key(
        self,
        tenant_id: UUID,
        api_key: str
    ) -> APIKeyConfig:
        """
        Store tenant's OpenAI API key (BYOK).
        Key is encrypted with tenant-specific encryption key.
        """
        encrypted = self._encryption.encrypt_for_tenant(tenant_id, api_key)
        # Store encrypted key, never log or expose plaintext

    async def get_openai_key(self, tenant_id: UUID) -> Optional[str]:
        """
        Retrieve decrypted API key for use in Core Engine.
        Returns None if tenant uses platform key.
        """

    async def validate_api_key(self, tenant_id: UUID) -> APIKeyValidation:
        """Test API key validity with OpenAI"""

    async def rotate_api_key(
        self,
        tenant_id: UUID,
        new_key: str
    ) -> APIKeyConfig:
        """Rotate API key (atomic operation)"""

    async def revoke_api_key(self, tenant_id: UUID) -> None:
        """Revoke BYOK key, revert to platform key"""
```

### 4.4 Admin API Endpoints

```
# Tenant Management
POST   /admin/tenants                    # Create tenant
GET    /admin/tenants                    # List tenants (paginated)
GET    /admin/tenants/{id}               # Get tenant details
PATCH  /admin/tenants/{id}               # Update tenant
DELETE /admin/tenants/{id}               # Soft delete tenant
POST   /admin/tenants/{id}/suspend       # Suspend tenant
POST   /admin/tenants/{id}/reactivate    # Reactivate tenant

# Plan Management
POST   /admin/plans                      # Create plan
GET    /admin/plans                      # List plans
GET    /admin/plans/{id}                 # Get plan details
PATCH  /admin/plans/{id}                 # Update plan
DELETE /admin/plans/{id}                 # Deactivate plan

# API Key Management (BYOK)
GET    /admin/tenants/{id}/api-keys      # Get API key config (masked)
POST   /admin/tenants/{id}/api-keys      # Set BYOK API key
DELETE /admin/tenants/{id}/api-keys      # Revoke BYOK key
POST   /admin/tenants/{id}/api-keys/validate  # Test API key

# Usage & Billing
GET    /admin/tenants/{id}/usage         # Get usage metrics
GET    /admin/tenants/{id}/invoices      # Get invoice history
POST   /admin/tenants/{id}/invoices      # Generate invoice

# User Management (cross-tenant)
GET    /admin/users                      # List all users
GET    /admin/users/{id}                 # Get user details
POST   /admin/users/{id}/impersonate     # Impersonate user (audit logged)

# System Health
GET    /admin/health                     # System health check
GET    /admin/metrics                    # Platform-wide metrics
GET    /admin/audit-logs                 # Audit log viewer
```

### 4.5 Admin Roles

| Role | Permissions |
|------|-------------|
| `super_admin` | Full platform access, all tenants |
| `tenant_admin` | Full access to own tenant only |
| `billing_admin` | View/manage billing across tenants |
| `support_admin` | Read access, user impersonation |

---

## 5. CPA Practice Portal Architecture

### 5.1 Overview

The CPA Practice Portal is the primary interface for CPA firms to manage clients, engagements, and advisory work.

### 5.2 Data Models

```python
# services/cpa-portal/src/models/client.py

class Client(BaseModel):
    """CPA firm's client record"""
    __tablename__ = "clients"

    id: UUID
    tenant_id: UUID                      # Owning CPA firm

    # Client Information
    client_type: ClientType              # individual, business, trust, estate
    name: str                            # "John Smith" or "ABC Corp"
    email: Optional[str]
    phone: Optional[str]

    # Business Information (if applicable)
    business_name: Optional[str]
    ein: Optional[str]                   # Hashed
    entity_type: Optional[EntityType]    # llc, s_corp, c_corp, partnership, sole_prop

    # Individual Information (if applicable)
    ssn_hash: Optional[str]              # SHA-256 hashed
    filing_status: Optional[FilingStatus]

    # Relationships
    assigned_cpa_id: Optional[UUID]      # Primary CPA

    # Status
    status: ClientStatus                 # prospect, active, inactive, archived
    lifecycle_stage: LifecycleStage      # lead, onboarding, engaged, retained

    # Metadata
    tags: List[str]
    notes: str

    created_at: datetime
    updated_at: datetime


class ClientStatus(str, Enum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class LifecycleStage(str, Enum):
    LEAD = "lead"                        # Initial contact
    ONBOARDING = "onboarding"            # Gathering documents
    ENGAGED = "engaged"                  # Active engagement
    RETAINED = "retained"                # Ongoing relationship


# services/cpa-portal/src/models/engagement.py

class Engagement(BaseModel):
    """Client engagement/project"""
    __tablename__ = "engagements"

    id: UUID
    tenant_id: UUID
    client_id: UUID

    # Engagement Details
    engagement_type: EngagementType      # tax_prep, tax_planning, advisory, audit
    tax_year: Optional[int]
    title: str                           # "2024 Tax Return" or "Q3 Advisory"
    description: Optional[str]

    # Workflow
    status: EngagementStatus
    workflow_state: str                  # State machine state

    # Assignment
    lead_cpa_id: UUID
    team_member_ids: List[UUID]

    # Dates
    due_date: Optional[date]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Financials
    estimated_fee: Optional[Decimal]
    actual_fee: Optional[Decimal]

    created_at: datetime
    updated_at: datetime


class EngagementStatus(str, Enum):
    DRAFT = "draft"
    PENDING_DOCUMENTS = "pending_documents"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    PENDING_CLIENT_APPROVAL = "pending_client_approval"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class EngagementType(str, Enum):
    TAX_PREPARATION = "tax_prep"
    TAX_PLANNING = "tax_planning"
    ADVISORY = "advisory"
    BOOKKEEPING = "bookkeeping"
    AUDIT_SUPPORT = "audit_support"
    CONSULTATION = "consultation"


# services/cpa-portal/src/models/document.py

class ClientDocument(BaseModel):
    """Document associated with client/engagement"""
    __tablename__ = "client_documents"

    id: UUID
    tenant_id: UUID
    client_id: UUID
    engagement_id: Optional[UUID]

    # Document Info
    filename: str
    file_type: str                       # pdf, jpg, png
    file_size_bytes: int
    storage_path: str                    # S3 path or local path

    # Classification (from ML classifier)
    document_type: Optional[str]         # w2, 1099-int, etc.
    classification_confidence: Optional[float]
    classification_method: Optional[str] # openai, tfidf, regex

    # Processing Status
    processing_status: DocumentStatus
    ocr_completed: bool
    extraction_completed: bool

    # Verification
    verified_by_cpa: bool
    verified_at: Optional[datetime]
    verified_by_id: Optional[UUID]

    # Metadata
    tax_year: Optional[int]
    notes: Optional[str]

    uploaded_at: datetime
    updated_at: datetime


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    VERIFIED = "verified"
    REJECTED = "rejected"
    ERROR = "error"
```

### 5.3 Engagement Workflow State Machine

```python
# services/cpa-portal/src/workflows/engagement_workflow.py

class EngagementWorkflow:
    """
    State machine for engagement lifecycle.

    States:
        draft -> pending_documents -> in_progress -> pending_review
              -> pending_client_approval -> completed

    Any state can transition to: on_hold, cancelled
    """

    TRANSITIONS = {
        "draft": ["pending_documents", "cancelled"],
        "pending_documents": ["in_progress", "on_hold", "cancelled"],
        "in_progress": ["pending_review", "on_hold", "cancelled"],
        "pending_review": ["in_progress", "pending_client_approval", "on_hold"],
        "pending_client_approval": ["completed", "in_progress", "on_hold"],
        "completed": [],  # Terminal state
        "on_hold": ["pending_documents", "in_progress", "cancelled"],
        "cancelled": [],  # Terminal state
    }

    REQUIRED_FOR_TRANSITION = {
        "pending_documents -> in_progress": ["at_least_one_document"],
        "in_progress -> pending_review": ["all_documents_verified"],
        "pending_review -> pending_client_approval": ["review_notes_added"],
        "pending_client_approval -> completed": ["client_signature"],
    }

    async def transition(
        self,
        engagement: Engagement,
        target_state: str,
        actor_id: UUID,
        notes: Optional[str] = None
    ) -> Engagement:
        """
        Transition engagement to new state.
        Validates transition is allowed and requirements are met.
        """

    async def get_available_transitions(
        self,
        engagement: Engagement
    ) -> List[str]:
        """Get valid next states from current state"""
```

### 5.4 Advisory and Planning Services

```python
# services/cpa-portal/src/services/advisory_service.py

class AdvisoryService:
    """Tax planning and advisory scenario analysis"""

    def __init__(self, core_engine_client: CoreEngineClient):
        self._core = core_engine_client

    async def create_scenario(
        self,
        client_id: UUID,
        engagement_id: UUID,
        scenario_type: ScenarioType,
        parameters: Dict[str, Any]
    ) -> AdvisoryScenario:
        """
        Create a new planning scenario.

        Scenario types:
        - retirement_contribution: 401k/IRA optimization
        - entity_structure: LLC vs S-Corp analysis
        - income_timing: Defer vs accelerate income
        - deduction_bunching: Standard vs itemized analysis
        - estimated_payments: Quarterly payment optimization
        """

    async def run_comparison(
        self,
        client_id: UUID,
        scenario_ids: List[UUID]
    ) -> ComparisonResult:
        """Compare multiple scenarios side-by-side"""

    async def generate_client_report(
        self,
        engagement_id: UUID,
        report_type: ReportType,
        include_scenarios: List[UUID]
    ) -> ClientReport:
        """
        Generate client-facing report.

        Report types:
        - tax_summary: Current year summary
        - planning_recommendations: Advisory recommendations
        - year_over_year: Multi-year comparison
        - projection: Future year projections
        """


class ScenarioType(str, Enum):
    RETIREMENT_CONTRIBUTION = "retirement_contribution"
    ENTITY_STRUCTURE = "entity_structure"
    INCOME_TIMING = "income_timing"
    DEDUCTION_BUNCHING = "deduction_bunching"
    ESTIMATED_PAYMENTS = "estimated_payments"
    CHARITABLE_GIVING = "charitable_giving"
    CAPITAL_GAINS = "capital_gains"
    HOME_OFFICE = "home_office"
```

### 5.5 Report Generation

```python
# services/cpa-portal/src/services/report_service.py

class ReportService:
    """Client report generation"""

    REPORT_TEMPLATES = {
        "tax_summary": {
            "sections": [
                "income_summary",
                "deduction_summary",
                "credit_summary",
                "tax_liability",
                "effective_rate"
            ],
            "format": ["pdf", "docx"]
        },
        "planning_recommendations": {
            "sections": [
                "current_situation",
                "opportunities",
                "scenario_comparison",
                "recommendations",
                "action_items"
            ],
            "format": ["pdf", "docx"]
        },
        "engagement_letter": {
            "sections": [
                "scope_of_services",
                "fees",
                "responsibilities",
                "timeline",
                "signature_block"
            ],
            "format": ["pdf", "docx"]
        },
        "document_checklist": {
            "sections": [
                "required_documents",
                "received_documents",
                "missing_documents"
            ],
            "format": ["pdf", "xlsx"]
        }
    }

    async def generate_report(
        self,
        engagement_id: UUID,
        report_type: str,
        options: ReportOptions
    ) -> GeneratedReport:
        """Generate report from template"""

    async def get_report_preview(
        self,
        engagement_id: UUID,
        report_type: str
    ) -> ReportPreview:
        """Generate HTML preview without file creation"""
```

### 5.6 CPA Portal API Endpoints

```
# Client Management
POST   /cpa/clients                      # Create client
GET    /cpa/clients                      # List clients (paginated, filtered)
GET    /cpa/clients/{id}                 # Get client details
PATCH  /cpa/clients/{id}                 # Update client
DELETE /cpa/clients/{id}                 # Archive client
POST   /cpa/clients/{id}/assign          # Assign CPA to client

# Engagement Management
POST   /cpa/engagements                  # Create engagement
GET    /cpa/engagements                  # List engagements
GET    /cpa/engagements/{id}             # Get engagement details
PATCH  /cpa/engagements/{id}             # Update engagement
POST   /cpa/engagements/{id}/transition  # Workflow state transition
GET    /cpa/engagements/{id}/timeline    # Get engagement timeline/history

# Document Management
POST   /cpa/documents/upload             # Upload document
GET    /cpa/documents                    # List documents
GET    /cpa/documents/{id}               # Get document details
POST   /cpa/documents/{id}/classify      # Trigger classification
POST   /cpa/documents/{id}/verify        # Mark as verified
DELETE /cpa/documents/{id}               # Delete document

# Advisory & Planning
POST   /cpa/advisory/scenarios           # Create planning scenario
GET    /cpa/advisory/scenarios           # List scenarios
GET    /cpa/advisory/scenarios/{id}      # Get scenario details
POST   /cpa/advisory/compare             # Compare scenarios
POST   /cpa/advisory/optimize            # Run optimization

# Reports
GET    /cpa/reports/templates            # List available templates
POST   /cpa/reports/generate             # Generate report
GET    /cpa/reports/{id}                 # Download generated report
GET    /cpa/reports/{id}/preview         # Preview report (HTML)

# Dashboard & Analytics
GET    /cpa/dashboard/summary            # Dashboard metrics
GET    /cpa/dashboard/deadlines          # Upcoming deadlines
GET    /cpa/dashboard/workload           # Team workload view

# Tax Calculation (via Core Engine)
POST   /cpa/tax/calculate                # Calculate tax return
POST   /cpa/tax/optimize                 # Run tax optimization
GET    /cpa/tax/insights/{engagement_id} # Get smart insights
```

---

## 6. Client Portal Architecture

### 6.1 Overview

The Client Portal provides a limited, secure interface for CPA clients to upload documents, view status, and approve deliverables.

### 6.2 Client Portal Features

| Feature | Description |
|---------|-------------|
| **Document Upload** | Secure document upload with automatic classification |
| **Engagement Status** | View current engagement status and timeline |
| **Message Center** | Secure messaging with CPA |
| **Document Request** | View outstanding document requests |
| **Deliverable Review** | Review and approve/sign deliverables |
| **Payment** | View and pay invoices (optional integration) |

### 6.3 Client Portal API Endpoints

```
# Authentication (via Identity Service)
POST   /client/auth/login                # Client login
POST   /client/auth/magic-link           # Request magic link login

# Profile
GET    /client/profile                   # Get client profile
PATCH  /client/profile                   # Update profile (limited fields)

# Documents
POST   /client/documents/upload          # Upload document
GET    /client/documents                 # List my documents
GET    /client/documents/{id}            # Download document

# Engagements (read-only)
GET    /client/engagements               # List my engagements
GET    /client/engagements/{id}          # Get engagement details
GET    /client/engagements/{id}/status   # Get current status

# Document Requests
GET    /client/requests                  # Outstanding document requests
POST   /client/requests/{id}/fulfill     # Mark request as fulfilled

# Deliverables
GET    /client/deliverables              # List deliverables
GET    /client/deliverables/{id}         # View deliverable
POST   /client/deliverables/{id}/approve # Approve deliverable
POST   /client/deliverables/{id}/sign    # E-sign deliverable

# Messages
GET    /client/messages                  # List messages
POST   /client/messages                  # Send message to CPA
GET    /client/messages/{id}             # Get message thread
```

### 6.4 Security Constraints

- **No access to**: Tax calculations, optimization results, or CPA notes
- **Read-only**: Engagement details, status, timeline
- **Limited write**: Document upload, message, deliverable approval
- **Audit logged**: All client actions are logged
- **Session timeout**: 15 minutes of inactivity
- **IP restriction**: Optional IP whitelist per client

---

## 7. Core Engine Isolation

### 7.1 Isolation Principles

The Core Engine (current `src/` folder) must be completely isolated from external access:

1. **No public API endpoints**: Core Engine has no routes exposed via API Gateway
2. **Service-to-service only**: Only CPA Service and Admin Service can call Core Engine
3. **Authenticated requests**: All internal requests require service authentication token
4. **Network isolation**: Core Engine runs in private subnet (no internet access)
5. **No user context**: Core Engine operates on data, not user sessions

### 7.2 Internal API Design

```python
# services/core-engine/src/internal_api.py

from fastapi import FastAPI, Depends, HTTPException
from .auth import verify_service_token

app = FastAPI(
    title="Core Engine Internal API",
    description="INTERNAL ONLY - Not exposed to public",
    docs_url=None,  # Disable Swagger in production
    redoc_url=None,
)

# Service authentication middleware
async def require_service_auth(
    authorization: str = Header(...),
    x_service_name: str = Header(...),
) -> ServiceContext:
    """Verify calling service is authorized"""
    if not verify_service_token(authorization, x_service_name):
        raise HTTPException(403, "Invalid service credentials")
    return ServiceContext(service_name=x_service_name)


# Tax Calculation Endpoints
@app.post("/internal/tax/calculate")
async def calculate_tax(
    request: TaxCalculationRequest,
    ctx: ServiceContext = Depends(require_service_auth)
) -> TaxCalculationResponse:
    """Calculate tax return from provided data"""

@app.post("/internal/tax/optimize")
async def optimize_tax(
    request: OptimizationRequest,
    ctx: ServiceContext = Depends(require_service_auth)
) -> OptimizationResponse:
    """Run tax optimization scenarios"""

@app.post("/internal/tax/insights")
async def generate_insights(
    request: InsightsRequest,
    ctx: ServiceContext = Depends(require_service_auth)
) -> InsightsResponse:
    """Generate smart insights for tax return"""


# Document Classification Endpoints
@app.post("/internal/ml/classify")
async def classify_document(
    request: ClassificationRequest,
    ctx: ServiceContext = Depends(require_service_auth)
) -> ClassificationResponse:
    """Classify document using ML pipeline"""

@app.post("/internal/ml/extract")
async def extract_document(
    request: ExtractionRequest,
    ctx: ServiceContext = Depends(require_service_auth)
) -> ExtractionResponse:
    """Extract data from classified document"""


# Advisory Endpoints
@app.post("/internal/advisory/scenario")
async def run_scenario(
    request: ScenarioRequest,
    ctx: ServiceContext = Depends(require_service_auth)
) -> ScenarioResponse:
    """Run advisory planning scenario"""

@app.post("/internal/advisory/compare")
async def compare_scenarios(
    request: ComparisonRequest,
    ctx: ServiceContext = Depends(require_service_auth)
) -> ComparisonResponse:
    """Compare multiple scenarios"""
```

### 7.3 Core Engine Client (for other services)

```python
# packages/api-client/core_engine_client.py

class CoreEngineClient:
    """
    Client for calling Core Engine internal API.
    Used by CPA Service and Admin Service.
    """

    def __init__(
        self,
        base_url: str = "http://core-engine:8000",
        service_name: str = "unknown",
        service_token: str = None,
    ):
        self._base_url = base_url
        self._service_name = service_name
        self._token = service_token or os.getenv("CORE_ENGINE_SERVICE_TOKEN")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "X-Service-Name": self._service_name,
            "Content-Type": "application/json",
        }

    async def calculate_tax(
        self,
        tax_return_data: Dict[str, Any]
    ) -> TaxCalculationResult:
        """Call Core Engine to calculate tax"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/internal/tax/calculate",
                headers=self._headers(),
                json=tax_return_data,
            )
            response.raise_for_status()
            return TaxCalculationResult(**response.json())

    async def classify_document(
        self,
        document_text: str,
        filename: str,
    ) -> ClassificationResult:
        """Call Core Engine to classify document"""

    async def run_optimization(
        self,
        tax_return_data: Dict[str, Any],
        scenarios: List[str],
    ) -> OptimizationResult:
        """Call Core Engine to run optimization"""
```

---

## 8. Identity and Access Control Services

### 8.1 Identity Service

The Identity Service handles all authentication concerns:

```python
# services/identity/src/models/user.py

class User(BaseModel):
    """Platform user (can belong to multiple tenants)"""
    __tablename__ = "users"

    id: UUID
    email: str                           # Unique, primary identifier
    email_verified: bool

    # Authentication
    password_hash: Optional[str]         # bcrypt hash
    mfa_enabled: bool
    mfa_secret_encrypted: Optional[str]

    # Profile
    first_name: str
    last_name: str
    phone: Optional[str]

    # Status
    status: UserStatus                   # active, suspended, pending_verification

    # SSO (optional)
    sso_provider: Optional[str]          # google, microsoft, okta
    sso_subject_id: Optional[str]

    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]


class TenantMembership(BaseModel):
    """User membership in a tenant"""
    __tablename__ = "tenant_memberships"

    id: UUID
    user_id: UUID
    tenant_id: UUID

    # Role within this tenant
    role: str                            # admin, cpa, staff, client

    # Status
    is_active: bool
    invited_at: datetime
    accepted_at: Optional[datetime]

    created_at: datetime
```

### 8.2 Identity Service API

```
# Authentication
POST   /auth/register                    # Register new user
POST   /auth/login                       # Login (email/password)
POST   /auth/login/sso                   # SSO login
POST   /auth/logout                      # Logout (invalidate tokens)
POST   /auth/refresh                     # Refresh access token
POST   /auth/forgot-password             # Request password reset
POST   /auth/reset-password              # Reset password with token

# MFA
POST   /auth/mfa/enable                  # Enable MFA
POST   /auth/mfa/verify                  # Verify MFA code
POST   /auth/mfa/disable                 # Disable MFA

# Email Verification
POST   /auth/verify-email                # Verify email with token
POST   /auth/resend-verification         # Resend verification email

# User Profile
GET    /auth/me                          # Get current user
PATCH  /auth/me                          # Update profile
GET    /auth/me/tenants                  # List user's tenants
POST   /auth/me/switch-tenant            # Switch active tenant context

# Token Introspection (for other services)
POST   /auth/introspect                  # Validate and decode token
```

### 8.3 Access Control Service

The Access Control Service handles all authorization decisions:

```python
# services/access-control/src/engines/rbac_engine.py

class RBACEngine:
    """Role-Based Access Control engine"""

    # Role hierarchy (higher includes lower)
    ROLE_HIERARCHY = {
        "super_admin": ["tenant_admin", "cpa", "staff", "client"],
        "tenant_admin": ["cpa", "staff", "client"],
        "cpa": ["staff"],
        "staff": [],
        "client": [],
    }

    # Role permissions
    ROLE_PERMISSIONS = {
        "super_admin": ["*"],  # All permissions
        "tenant_admin": [
            "tenant:read", "tenant:update",
            "users:*", "clients:*", "engagements:*",
            "documents:*", "reports:*", "billing:read",
        ],
        "cpa": [
            "clients:*", "engagements:*",
            "documents:*", "reports:*", "tax:*",
        ],
        "staff": [
            "clients:read", "engagements:read",
            "documents:read", "documents:upload",
        ],
        "client": [
            "documents:upload", "documents:read:own",
            "engagements:read:own", "messages:*:own",
        ],
    }

    async def check_permission(
        self,
        user_id: UUID,
        tenant_id: UUID,
        permission: str,
    ) -> bool:
        """Check if user has permission in tenant context"""


# services/access-control/src/engines/abac_engine.py

class ABACEngine:
    """Attribute-Based Access Control engine"""

    async def evaluate_policy(
        self,
        subject: Dict[str, Any],     # User attributes
        resource: Dict[str, Any],    # Resource attributes
        action: str,                 # Requested action
        context: Dict[str, Any],     # Environmental context
    ) -> PolicyDecision:
        """
        Evaluate ABAC policy.

        Example policies:
        - "CPA can only access clients assigned to them"
        - "Staff can only upload documents during business hours"
        - "Clients can only see their own documents"
        """

    POLICIES = [
        # CPA can only access their assigned clients
        Policy(
            name="cpa_client_assignment",
            condition=lambda s, r, a, c: (
                s["role"] == "cpa" and
                r["type"] == "client" and
                r["assigned_cpa_id"] == s["user_id"]
            ),
        ),

        # Clients can only access their own data
        Policy(
            name="client_own_data",
            condition=lambda s, r, a, c: (
                s["role"] == "client" and
                r.get("client_id") == s["client_id"]
            ),
        ),
    ]
```

### 8.4 Access Enforcement Middleware

```python
# packages/common/auth/middleware.py

class AccessEnforcementMiddleware:
    """
    Middleware for enforcing access control on all requests.
    Installed in: CPA Service, Admin Service, Client Service
    """

    def __init__(
        self,
        identity_client: IdentityClient,
        access_control_client: AccessControlClient,
    ):
        self._identity = identity_client
        self._access = access_control_client

    async def __call__(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # 1. Extract token from Authorization header
        token = self._extract_token(request)

        # 2. Validate token with Identity Service
        user_context = await self._identity.introspect(token)
        if not user_context:
            return JSONResponse({"error": "Unauthorized"}, 401)

        # 3. Determine required permission for this endpoint
        permission = self._get_required_permission(request)

        # 4. Check permission with Access Control Service
        allowed = await self._access.check_permission(
            user_id=user_context.user_id,
            tenant_id=user_context.tenant_id,
            permission=permission,
            resource=self._extract_resource(request),
        )

        if not allowed:
            return JSONResponse({"error": "Forbidden"}, 403)

        # 5. Attach user context to request
        request.state.user = user_context

        # 6. Continue to endpoint
        return await call_next(request)
```

### 8.5 Access Control API

```
# Permission Checking (called by services)
POST   /access/check                     # Check single permission
POST   /access/check-batch               # Check multiple permissions

# Policy Management (admin only)
GET    /access/policies                  # List policies
POST   /access/policies                  # Create policy
PATCH  /access/policies/{id}             # Update policy
DELETE /access/policies/{id}             # Delete policy

# Role Management (admin only)
GET    /access/roles                     # List roles
POST   /access/roles                     # Create custom role
PATCH  /access/roles/{id}                # Update role permissions
DELETE /access/roles/{id}                # Delete custom role

# Audit
GET    /access/audit                     # Access decision audit log
```

---

## 9. Database Strategy

### 9.1 Schema Isolation

```sql
-- Schema per service
CREATE SCHEMA identity;
CREATE SCHEMA access_control;
CREATE SCHEMA admin;
CREATE SCHEMA billing;
CREATE SCHEMA core_engine;

-- Per-tenant schema for CPA/Client data
CREATE SCHEMA tenant_acme;
CREATE SCHEMA tenant_smith_cpa;
-- ... dynamically created for each tenant
```

### 9.2 Row-Level Security (Defense in Depth)

```sql
-- Enable RLS on tenant tables
ALTER TABLE tenant_acme.clients ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see rows for their tenant
CREATE POLICY tenant_isolation ON tenant_acme.clients
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Policy: Clients can only see their own data
CREATE POLICY client_own_data ON tenant_acme.client_documents
    FOR SELECT
    USING (
        client_id = current_setting('app.current_client_id')::UUID
        OR current_setting('app.user_role') IN ('cpa', 'staff', 'admin')
    );
```

### 9.3 Database Connection Management

```python
# packages/db-models/connection.py

class TenantAwareSession:
    """
    Database session that automatically sets tenant context.
    """

    async def __aenter__(self):
        self._session = await get_session()

        # Set tenant context for RLS
        await self._session.execute(
            f"SET app.current_tenant_id = '{self._tenant_id}'"
        )
        await self._session.execute(
            f"SET app.current_user_id = '{self._user_id}'"
        )
        await self._session.execute(
            f"SET app.user_role = '{self._user_role}'"
        )

        return self._session

    async def __aexit__(self, *args):
        # Reset context
        await self._session.execute("RESET app.current_tenant_id")
        await self._session.close()
```

---

## 10. Security Architecture

### 10.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Network Security                                       │
│ - WAF (Web Application Firewall)                               │
│ - DDoS protection                                               │
│ - IP whitelisting for admin                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: Transport Security                                     │
│ - TLS 1.3 everywhere                                            │
│ - Certificate pinning for mobile                                │
│ - HSTS headers                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: Authentication                                         │
│ - JWT tokens (short-lived: 15 min)                             │
│ - Refresh tokens (7 days, rotating)                            │
│ - MFA for admin/CPA roles                                       │
│ - SSO/SAML for enterprise                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Authorization                                          │
│ - RBAC (Role-Based Access Control)                             │
│ - ABAC (Attribute-Based Access Control)                        │
│ - Resource-level permissions                                    │
│ - Tenant isolation enforcement                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 5: Application Security                                   │
│ - Input validation (Pydantic)                                  │
│ - Output encoding                                               │
│ - CSRF protection                                               │
│ - Rate limiting per endpoint                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 6: Data Security                                          │
│ - Encryption at rest (AES-256)                                 │
│ - Encryption in transit (TLS)                                  │
│ - Field-level encryption (SSN, API keys)                       │
│ - Row-Level Security (PostgreSQL RLS)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│ Layer 7: Audit & Monitoring                                     │
│ - Complete audit trail                                          │
│ - Anomaly detection                                             │
│ - Security alerting                                             │
│ - Compliance reporting                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 Sensitive Data Handling

| Data Type | Storage | Access |
|-----------|---------|--------|
| SSN | SHA-256 hash (no salt) | Never displayed, lookup only |
| API Keys (BYOK) | AES-256 encrypted per-tenant | Decrypted only for API calls |
| Passwords | bcrypt hash (cost=12) | Never retrievable |
| Tax Returns | Encrypted at rest | Tenant-scoped access |
| Documents | Encrypted at rest | Tenant + client scoped |
| Audit Logs | Immutable, encrypted | Admin read-only |

### 10.3 Known Security Limitations (Documented)

1. **SSN Hashing**: Uses SHA-256 without salt. Limited keyspace (~1B) makes rainbow tables feasible. Acceptable for current use case (lookup, not security boundary). Future: Consider HMAC with pepper.

2. **Session Tokens**: JWT with 15-minute expiry. Tokens cannot be revoked before expiry. Mitigation: Short expiry + refresh token rotation.

3. **OpenAI API**: Document text sent to OpenAI for classification. Mitigation: No PII in classification request; BYOK option for sensitive tenants.

---

## 11. Implementation Timeline

### Phase 1: Foundation (Weeks 1-3)

| Week | Tasks |
|------|-------|
| 1 | Set up monorepo structure, CI/CD pipeline, Docker compose for local dev |
| 2 | Implement Identity Service (auth, tokens, user management) |
| 3 | Implement Access Control Service (RBAC engine, permission checking) |

**Deliverables**:
- Working Identity Service with login/register/token refresh
- Working Access Control Service with RBAC
- Docker compose for local development
- CI/CD pipeline running tests

### Phase 2: Admin Panel (Weeks 4-6)

| Week | Tasks |
|------|-------|
| 4 | Implement Admin Service (tenant CRUD, plan management) |
| 5 | Implement BYOK API key management, encryption |
| 6 | Implement usage tracking, billing integration |

**Deliverables**:
- Tenant management UI
- BYOK API key configuration
- Usage dashboard

### Phase 3: Core Engine Isolation (Weeks 7-8)

| Week | Tasks |
|------|-------|
| 7 | Refactor current src/ into services/core-engine/ |
| 8 | Implement internal API, service-to-service auth |

**Deliverables**:
- Core Engine running as isolated service
- Internal API with service authentication
- CoreEngineClient library for other services

### Phase 4: CPA Portal (Weeks 9-11)

| Week | Tasks |
|------|-------|
| 9 | Implement CPA Service (client management, basic CRUD) |
| 10 | Implement engagement workflow, document management |
| 11 | Implement advisory scenarios, report generation |

**Deliverables**:
- Client management UI
- Engagement workflow
- Document upload and classification
- Report generation

### Phase 5: Client Portal & Polish (Weeks 12-14)

| Week | Tasks |
|------|-------|
| 12 | Implement Client Portal (limited access, document upload) |
| 13 | End-to-end testing, security audit |
| 14 | Documentation, deployment preparation |

**Deliverables**:
- Client portal UI
- Security audit report
- Deployment documentation
- Production-ready V2.0

---

## 12. Technical Specifications

### 12.1 Technology Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.11+, FastAPI, Pydantic |
| **Database** | PostgreSQL 15+ with RLS |
| **Cache** | Redis (sessions, rate limiting) |
| **Queue** | Redis Streams or RabbitMQ |
| **Search** | PostgreSQL full-text (future: Elasticsearch) |
| **Storage** | S3-compatible (AWS S3, MinIO) |
| **Container** | Docker, Kubernetes |
| **CI/CD** | GitHub Actions |
| **Monitoring** | Prometheus, Grafana, Sentry |

### 12.2 API Standards

- **Format**: JSON (application/json)
- **Versioning**: URL path (/v1/, /v2/)
- **Pagination**: Cursor-based for lists
- **Errors**: RFC 7807 Problem Details
- **Rate Limiting**: Token bucket per tenant
- **Idempotency**: Idempotency-Key header for mutations

### 12.3 Docker Compose (Development)

```yaml
# infrastructure/docker/docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: jorss
      POSTGRES_PASSWORD: localdev
      POSTGRES_DB: jorss_dev
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  identity:
    build:
      context: ../../services/identity
    environment:
      DATABASE_URL: postgresql://jorss:localdev@postgres/jorss_dev
      REDIS_URL: redis://redis:6379
      JWT_SECRET: local-dev-secret-change-in-prod
    ports:
      - "8001:8000"
    depends_on:
      - postgres
      - redis

  access-control:
    build:
      context: ../../services/access-control
    environment:
      DATABASE_URL: postgresql://jorss:localdev@postgres/jorss_dev
      IDENTITY_SERVICE_URL: http://identity:8000
    ports:
      - "8002:8000"
    depends_on:
      - postgres
      - identity

  admin:
    build:
      context: ../../services/admin
    environment:
      DATABASE_URL: postgresql://jorss:localdev@postgres/jorss_dev
      IDENTITY_SERVICE_URL: http://identity:8000
      ACCESS_CONTROL_URL: http://access-control:8000
    ports:
      - "8003:8000"
    depends_on:
      - postgres
      - identity
      - access-control

  cpa-portal:
    build:
      context: ../../services/cpa-portal
    environment:
      DATABASE_URL: postgresql://jorss:localdev@postgres/jorss_dev
      IDENTITY_SERVICE_URL: http://identity:8000
      ACCESS_CONTROL_URL: http://access-control:8000
      CORE_ENGINE_URL: http://core-engine:8000
      CORE_ENGINE_SERVICE_TOKEN: local-service-token
    ports:
      - "8004:8000"
    depends_on:
      - postgres
      - identity
      - access-control
      - core-engine

  core-engine:
    build:
      context: ../../services/core-engine
    environment:
      DATABASE_URL: postgresql://jorss:localdev@postgres/jorss_dev
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      SERVICE_AUTH_TOKENS: cpa-portal:local-service-token
    ports:
      - "8005:8000"
    depends_on:
      - postgres

  client-portal:
    build:
      context: ../../services/client-portal
    environment:
      DATABASE_URL: postgresql://jorss:localdev@postgres/jorss_dev
      IDENTITY_SERVICE_URL: http://identity:8000
      ACCESS_CONTROL_URL: http://access-control:8000
    ports:
      - "8006:8000"
    depends_on:
      - postgres
      - identity
      - access-control

volumes:
  postgres_data:
```

### 12.4 Environment Variables

```bash
# .env.example

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379

# Identity Service
JWT_SECRET=your-256-bit-secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# OpenAI (Core Engine)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Service-to-Service Auth
CORE_ENGINE_SERVICE_TOKEN=your-service-token

# Encryption
ENCRYPTION_KEY=your-256-bit-encryption-key
TENANT_KEY_DERIVATION_SALT=your-salt

# Feature Flags
ENABLE_ML_CLASSIFICATION=true
ENABLE_BYOK=true

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **ABAC** | Attribute-Based Access Control - authorization based on attributes of user, resource, and environment |
| **BYOK** | Bring Your Own Key - tenant provides their own API keys |
| **Core Engine** | Isolated tax calculation and ML service |
| **Engagement** | A project/case for a client (e.g., "2024 Tax Return") |
| **RBAC** | Role-Based Access Control - authorization based on user roles |
| **RLS** | Row-Level Security - PostgreSQL feature for row-level data isolation |
| **Tenant** | A CPA firm or organization using the platform |

---

## Appendix B: Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| OpenAI API outage | High | Fallback to TF-IDF classifier, graceful degradation |
| SSN rainbow table attack | Medium | Documented limitation, consider HMAC upgrade |
| Cross-tenant data leak | Critical | Schema isolation + RLS + application-level checks |
| Service token compromise | High | Short-lived tokens, rotation policy, audit logging |
| BYOK key exposure | High | Tenant-specific encryption, never log keys |

---

## Appendix C: Compliance Considerations

| Requirement | Status | Notes |
|-------------|--------|-------|
| SOC 2 Type II | Planned | Audit trail, access controls, encryption |
| GDPR | Planned | Data deletion, export, consent management |
| IRS Publication 4557 | Compliant | Tax preparer data security guidelines |
| State privacy laws | Planned | California CCPA, state-specific requirements |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Post-Freeze V1.0 | System | Initial planning document |

---

*This document represents V2.0 planning. Implementation should follow the phased approach outlined in Section 11.*
