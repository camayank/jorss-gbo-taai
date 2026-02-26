# Jorss-Gbo: US Individual Tax Advisory Platform — Complete Project Blueprint

> **Production-Grade SaaS for Indian CA/Tax Professionals Serving US-Based NRI and Resident Individual Clients**

**Date:** 2026-02-25
**Version:** 1.0
**Status:** Production-Ready Specification

---

## Table of Contents

1. [Tech Stack & Architecture](#1-tech-stack--architecture)
2. [Core Modules Specification](#2-core-modules-specification)
3. [Database Schema](#3-database-schema)
4. [API Architecture](#4-api-architecture)
5. [Business Logic Rules](#5-business-logic-rules)
6. [AI Layer Design](#6-ai-layer-design)
7. [Compliance & Security](#7-compliance--security)
8. [Deployment Pipeline](#8-deployment-pipeline)
9. [Monetization Model](#9-monetization-model)
10. [Phase-Wise Roadmap](#10-phase-wise-roadmap)

---

## 1. Tech Stack & Architecture

### 1.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT TIER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ CPA Dashboard│  │ Client Portal│  │ Admin Panel              │  │
│  │ (White-Label)│  │ (Tax Filing) │  │ (Platform Management)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                 │                      │                   │
│  HTML/CSS/JS + Jinja2 Templates + Storybook Design System           │
└─────────┼─────────────────┼──────────────────────┼──────────────────┘
          │                 │                      │
┌─────────┼─────────────────┼──────────────────────┼──────────────────┐
│         ▼                 ▼                      ▼                   │
│                      API GATEWAY                                     │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ FastAPI 0.104.1 + Uvicorn ASGI                                │  │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │  │
│  │ │   CSRF   │ │  CORS    │ │Rate Limit│ │ Tenant Isolation  │  │  │
│  │ │Middleware│ │Middleware│ │Middleware│ │   Middleware      │  │  │
│  │ └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │  │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │  │
│  │ │Security  │ │Request   │ │Circuit   │ │  Idempotency     │  │  │
│  │ │Headers   │ │Validation│ │Breaker   │ │   Handler        │  │  │
│  │ └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│                      SERVICE TIER                                     │
│  ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌────────────────────┐   │
│  │ Tax Calc  │ │ AI/LLM    │ │ Document │ │ Advisory/Reports   │   │
│  │ Engine    │ │ Agent     │ │ Pipeline │ │ Engine             │   │
│  ├───────────┤ ├───────────┤ ├──────────┤ ├────────────────────┤   │
│  │• Federal  │ │• LangChain│ │• OCR     │ │• PDF Generation    │   │
│  │• 50 States│ │• GPT-4O   │ │• Classify│ │• Advisory Reports  │   │
│  │• AMT/QBI  │ │• Tax Chat │ │• Extract │ │• Computation Stmt  │   │
│  │• Intl Tax │ │• Citations│ │• Validate│ │• Draft Returns     │   │
│  └───────────┘ └───────────┘ └──────────┘ └────────────────────┘   │
│  ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌────────────────────┐   │
│  │ Auth/RBAC │ │ Audit     │ │ Billing  │ │ Notifications      │   │
│  │ System    │ │ Trail     │ │ Module   │ │ Engine             │   │
│  └───────────┘ └───────────┘ └──────────┘ └────────────────────┘   │
│                                                                      │
│                      DATA TIER                                       │
│  ┌───────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │ PostgreSQL 14+│  │ Redis        │  │ File Storage           │   │
│  │ (Neon)        │  │ (Upstash)    │  │ (Local/S3)             │   │
│  │ • ORM Models  │  │ • Sessions   │  │ • Uploaded Docs        │   │
│  │ • Encrypted   │  │ • Cache      │  │ • Generated PDFs       │   │
│  │   PII Fields  │  │ • Rate Limit │  │ • OCR Results          │   │
│  └───────────────┘  └──────────────┘  └────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Language** | Python | 3.11+ | Primary application language |
| **Web Framework** | FastAPI | 0.104.1 | Async REST API with automatic OpenAPI docs |
| **ASGI Server** | Uvicorn | 0.24.0 | High-performance async server |
| **Process Manager** | Gunicorn | 21.2.0 | Production process management with UvicornWorker |
| **ORM** | SQLAlchemy | 2.0.23 | Database abstraction with async support |
| **Migrations** | Alembic | 1.13.1 | Schema versioning and migration management |
| **Database (Prod)** | PostgreSQL | 14+ | Primary data store (Neon serverless) |
| **Database (Dev)** | SQLite | 3.x | Local development convenience |
| **Cache** | Redis | 5.0.1 | Session cache, rate limiting (Upstash serverless) |
| **AI/LLM** | LangChain + OpenAI | 0.1.0 / 1.0.0 | Tax advisory AI agent |
| **LLM Model** | GPT-4O | Latest | Conversational tax collection and advice |
| **Validation** | Pydantic | 2.5.0 | Request/response validation, settings |
| **Security** | PyJWT + bcrypt + cryptography | 2.8.0 / 4.1.2 / 41.0.7 | Auth, hashing, AES-256 encryption |
| **MFA** | pyotp | 2.9.0 | TOTP-based multi-factor authentication |
| **OCR** | Tesseract (pytesseract) | 0.3.10 | Document text extraction |
| **PDF Processing** | pypdf + pdfplumber | 3.17.0 / 0.10.3 | Tax document parsing |
| **PDF Generation** | ReportLab | 3.6.0 | Professional PDF output |
| **ML/Classification** | scikit-learn + joblib | 1.3.0 / 1.3.0 | Document type classification |
| **Math** | NumPy + Decimal | 1.26.2 | Precise financial calculations |
| **Visualization** | Matplotlib | 3.7.0 | Charts for tax reports |
| **Testing** | pytest + pytest-asyncio | 7.4.4 / 0.23.0+ | Test framework |
| **Frontend** | HTML/CSS/JS + Jinja2 | — | Server-rendered templates |
| **Design System** | Storybook | 8.0.0 | Component library and documentation |
| **Build Tool** | Vite | 5.0.0 | Frontend build tooling |
| **Containerization** | Docker | Multi-stage | Reproducible builds and deployment |
| **Deployment** | Render.com | — | Cloud PaaS hosting |

### 1.3 Architecture Principles

1. **Multi-Tenant by Default** — Every data access path includes `tenant_id` isolation
2. **IRS-Compliant Precision** — `Decimal(12,2)` with `ROUND_HALF_UP` for all monetary values
3. **Audit Everything** — HMAC-SHA256 hash-chained immutable audit trail
4. **Encrypt PII at Rest** — AES-256 for SSN, bank details; HMAC-SHA256 for lookup hashes
5. **Defense in Depth** — CSRF + CORS + Rate Limiting + Tenant Isolation + Security Headers
6. **Progressive Enhancement** — Server-rendered HTML with JavaScript enhancement
7. **Feature Flags** — Granular feature enablement per tenant/tier

---

## 2. Core Modules Specification

### 2.1 Module Map (43 Source Modules)

```
src/
├── calculator/              # Federal + State Tax Calculation Engine
│   ├── engine.py            #   FederalTaxEngine — core calculation orchestrator
│   ├── audited_engine.py    #   AuditedTaxEngine — adds audit logging wrapper
│   ├── tax_calculator.py    #   TaxCalculator — high-level federal+state coordinator
│   ├── decimal_math.py      #   IRS-compliant Decimal arithmetic
│   ├── tax_year_config.py   #   TaxYearConfig — brackets/thresholds per year (2022-2026)
│   ├── qbi_calculator.py    #   QBICalculator — Section 199A deduction
│   ├── validation.py        #   TaxReturnValidator — input validation
│   ├── recommendations.py   #   Tax optimization recommendation engine
│   └── state/               #   StateTaxEngine — all 50 states + DC
│       └── configs/state_2025/  # Per-state calculators (CA, NY, TX, etc.)
│
├── models/                  # 58+ Pydantic Models for IRS Forms
│   ├── form_1040.py         #   Main individual return
│   ├── schedule_a.py        #   Itemized deductions
│   ├── schedule_b.py        #   Interest and dividends
│   ├── schedule_c.py        #   Business profit/loss
│   ├── schedule_d.py        #   Capital gains/losses
│   ├── schedule_e.py        #   Rental/K-1 income
│   ├── schedule_f.py        #   Farm income
│   ├── schedule_h.py        #   Household employment
│   ├── form_1116.py         #   Foreign Tax Credit
│   ├── form_2555.py         #   Foreign Earned Income Exclusion
│   ├── form_5471.py         #   Foreign Corporation
│   ├── form_6251.py         #   AMT
│   ├── form_8949.py         #   Capital asset sales
│   ├── form_8995.py         #   QBI deduction
│   ├── form_8889.py         #   HSA
│   ├── form_8863.py         #   Education credits
│   ├── form_2210.py         #   Underpayment penalty
│   ├── form_4562.py         #   Depreciation
│   ├── form_8582.py         #   Passive activity losses
│   └── ... (40+ more)      #   Full IRS form coverage
│
├── database/                # Data Persistence Layer
│   ├── models.py            #   SQLAlchemy ORM (30+ tables)
│   ├── schema.py            #   Schema definitions
│   ├── connection.py        #   Sync database engine
│   ├── async_engine.py      #   Async PostgreSQL engine
│   ├── persistence.py       #   Session persistence
│   ├── encrypted_fields.py  #   AES-256 field encryption
│   ├── tenant_models.py     #   Multi-tenant: Tenant, CPABranding, FeatureFlags
│   ├── redis_session_persistence.py  # Redis-backed sessions
│   ├── unified_session.py   #   Combined session management
│   └── alembic/             #   13 migration files
│
├── web/                     # FastAPI Application + 25+ Route Files
│   ├── app.py               #   Main FastAPI app with middleware stack
│   ├── unified_filing_api.py #  Unified filing workflow endpoints
│   ├── intelligent_advisor_api.py # AI tax advisor with citations/audit
│   ├── ai_chat_api.py       #   Chat with AI agent
│   ├── capital_gains_api.py  #  Capital gains calculation
│   ├── k1_basis_api.py      #   K-1 basis tracking
│   ├── rental_depreciation_api.py # Rental property depreciation
│   ├── scenario_api.py      #   Tax scenario explorer
│   ├── smart_tax_api.py     #   Smart tax suggestions
│   ├── guided_filing_api.py  #  Step-by-step guided filing
│   ├── sessions_api.py      #   Session management
│   ├── mfa_api.py           #   Multi-factor authentication
│   ├── audit_api.py         #   Audit trail access
│   ├── admin_endpoints.py   #   Admin dashboard
│   ├── cpa_branding_api.py  #   CPA portal branding
│   ├── express_lane_api.py  #   Quick filing for simple returns
│   ├── lead_magnet_pages.py  #  Lead magnet landing pages
│   └── templates/           #   Jinja2 HTML templates
│
├── agent/                   # AI Tax Agent (LangChain)
│   ├── tax_agent.py         #   TaxAgent — conversational tax collection
│   └── intelligent_tax_agent.py # Enhanced agent with compliance features
│
├── smart_tax/               # Smart Tax Intelligence
│   ├── complexity_router.py  #  Route returns by complexity score
│   ├── deduction_detector.py #  Identify applicable deductions
│   ├── planning_insights.py  #  Tax planning recommendations
│   └── question_generator.py #  Generate targeted follow-up questions
│
├── security/                # Security & Authentication
│   ├── authentication.py    #   JWT auth with token management
│   ├── encryption.py        #   AES-256 PII encryption
│   ├── ssn_hash.py          #   HMAC-SHA256 SSN hashing
│   ├── fraud_detector.py    #   Fraud detection engine
│   ├── ai_compliance_reviewer.py # AI compliance validation
│   ├── tenant_isolation_middleware.py # Tenant data boundaries
│   └── file_upload_security.py # Secure file upload validation
│
├── rbac/                    # Role-Based Access Control (14 files)
│   ├── roles.py             #   8 role definitions
│   ├── permissions.py       #   Permission matrix
│   ├── feature_access_control.py # Feature-level gating
│   └── decorators.py        #   @require_auth, @require_role
│
├── audit/                   # Audit Trail System
│   ├── audit_trail.py       #   HMAC hash-chained audit events
│   ├── audit_logger.py      #   Audit event logging + AI response audit
│   └── audit_models.py      #   AIResponseAuditEvent for AI rationale
│
├── tax_references/          # Tax Law Citations
│   └── citations.py         #   Top 20 IRC section citations + topic detection
│
├── rules/                   # 381+ Tax Business Rules
│   ├── virtual_currency_rules.py
│   ├── foreign_assets_rules.py
│   ├── alimony_rules.py
│   ├── k1_trust_rules.py
│   └── ... (30+ rule files)
│
├── services/                # Service Layer
│   ├── ocr/                 #   Document OCR pipeline
│   │   ├── document_processor.py # Main processing coordinator
│   │   ├── ocr_engine.py    #   Multi-backend OCR (Tesseract/Google/Azure)
│   │   └── field_extractor.py #  Template-based field extraction
│   ├── calculation_pipeline.py # Async calculation orchestration
│   ├── tax_return_service.py #  Tax return CRUD
│   └── validation_service.py # Business validation
│
├── export/                  # Document Generation
│   ├── pdf_generator.py     #   PDF generation (ReportLab)
│   ├── premium_report_generator.py # Premium report templates
│   ├── advisory_pdf_exporter.py # AI advisory PDFs
│   ├── draft_form_generator.py #  Draft IRS form generation
│   ├── draft_return.py      #   Complete return drafts
│   └── computation_statement.py # IRS-style computation worksheets
│
├── subscription/            # Billing & SaaS Tiers
├── notifications/           # Email/Alert System
├── admin_panel/             # Platform Admin Interface
├── cpa_panel/               # White-Label CPA Portal
├── projection/              # Tax Projection Scenarios
├── advisory/                # AI-Powered Advisory Reports
├── config/                  # Branding & Configuration
├── cache/                   # Caching Layer (Redis)
├── middleware/              # Request/Response Middleware
├── resilience/              # Circuit Breaker, Retry Logic
├── realtime/                # WebSocket/Real-time Features
└── tasks/                   # Background Tasks
```

### 2.2 India-US Tax Specialization (NRI Focus)

**Currently Implemented International Forms:**
- Form 1116 (Foreign Tax Credit) — 6 income categories, 1-year carryback, 10-year carryforward
- Form 2555 (FEIE) — $130,000 exclusion (2025), housing exclusion/deduction
- Form 5471 (Foreign Corporation) — SUBPART F and GILTI income
- FBAR/FATCA rules — Foreign financial account reporting

**Gap: India-Specific Modules Needed for NRI Clients**

The following modules are **required** for the India-focused use case and are not yet implemented:

| Module | Purpose | Priority |
|--------|---------|----------|
| **India-US DTAA Engine** | Apply Articles 10-23 of India-US Tax Treaty for dividends (15%), interest (15%), royalties (15%), capital gains, pensions | P0 |
| **NRI Status Classifier** | Determine US tax residency (Substantial Presence Test), India tax residency (182-day rule), and treaty tiebreaker | P0 |
| **Form 8833 Generator** | Treaty-based return positions disclosure | P0 |
| **India Income Mapper** | Map Indian income types (salary per Indian IT Act, HRA, DA) to US equivalents (W-2, 1099) | P1 |
| **Indian TDS Credit Mapper** | Map Indian TDS (Tax Deducted at Source) certificates to Form 1116 foreign tax credit categories | P1 |
| **INR→USD Converter** | IRS-approved exchange rate conversion (annual average or transaction-date) | P1 |
| **PFIC Analysis** | Passive Foreign Investment Company analysis for Indian mutual funds held by US persons | P1 |
| **India Retirement Accounts** | EPF/PPF/NPS US tax treatment — potential treaty benefits under Article 20 | P2 |
| **FBAR/FATCA India** | India-specific account reporting thresholds and financial institution identification | P2 |
| **Section 91 Relief** | India's unilateral relief for double taxation when DTAA doesn't apply | P2 |

---

## 3. Database Schema

### 3.1 Entity Relationship Overview

```
┌──────────────┐    ┌──────────────────┐    ┌────────────────┐
│   Tenant     │◄──►│   Preparer       │◄──►│    Client      │
│ (CPA Firm)   │    │ (CPA/EA)         │    │ (Taxpayer)     │
└──────┬───────┘    └──────┬───────────┘    └──────┬─────────┘
       │                   │                       │
       │            ┌──────┴───────────┐           │
       │            │ ClientSession    │◄──────────┘
       │            │ (Work Session)   │
       │            └──────┬───────────┘
       │                   │
       │            ┌──────┴───────────┐
       └───────────►│  TaxReturn       │◄──── AuditLog
                    │  (Form 1040)     │
                    └──────┬───────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────┴─────┐  ┌──────┴─────┐  ┌──────┴──────┐
   │ Taxpayer   │  │ Income     │  │ Dependent   │
   │ (Personal) │  │ Records    │  │ Records     │
   └────────────┘  └──────┬─────┘  └─────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
   ┌──────┴─────┐ ┌──────┴─────┐ ┌──────┴──────┐
   │ W2Record   │ │Form1099Rec │ │ Deduction   │
   │            │ │            │ │ Record      │
   └────────────┘ └────────────┘ └─────────────┘
          │               │
   ┌──────┴─────┐ ┌──────┴─────┐ ┌─────────────┐
   │ Credit     │ │ StateReturn│ │ Computation │
   │ Record     │ │ Record     │ │ Worksheet   │
   └────────────┘ └────────────┘ └─────────────┘

   ┌────────────┐ ┌────────────┐ ┌─────────────┐
   │ Document   │►│ Extracted  │ │ DocProcess  │
   │ Record     │ │ Field      │ │ Log         │
   └────────────┘ └────────────┘ └─────────────┘

   ┌────────────┐ ┌────────────┐
   │ MFA        │ │ MFA Pending│
   │ Credential │ │ Setup      │
   └────────────┘ └────────────┘
```

### 3.2 Core Tables (30+ Tables)

#### **TaxReturnRecord** — Master tax return (Form 1040)
```sql
CREATE TABLE tax_returns (
    return_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tax_year            INTEGER NOT NULL,
    taxpayer_ssn_hash   VARCHAR(64) NOT NULL,          -- HMAC-SHA256 lookup
    filing_status       filing_status_enum NOT NULL,    -- SINGLE, MFJ, MFS, HOH, QSS
    status              return_status_enum NOT NULL DEFAULT 'DRAFT',
    is_amended          BOOLEAN DEFAULT FALSE,
    original_return_id  UUID REFERENCES tax_returns(return_id),
    amendment_number    INTEGER DEFAULT 0,

    -- IRS Form 1040 Lines (39 monetary fields)
    line_1_wages                NUMERIC(12,2) DEFAULT 0,
    line_2a_tax_exempt_interest NUMERIC(12,2) DEFAULT 0,
    line_2b_taxable_interest    NUMERIC(12,2) DEFAULT 0,
    line_3a_qualified_dividends NUMERIC(12,2) DEFAULT 0,
    line_3b_ordinary_dividends  NUMERIC(12,2) DEFAULT 0,
    line_4a_ira_distributions   NUMERIC(12,2) DEFAULT 0,
    line_4b_taxable_ira         NUMERIC(12,2) DEFAULT 0,
    line_5a_pensions            NUMERIC(12,2) DEFAULT 0,
    line_5b_taxable_pensions    NUMERIC(12,2) DEFAULT 0,
    line_6a_social_security     NUMERIC(12,2) DEFAULT 0,
    line_6b_taxable_ss          NUMERIC(12,2) DEFAULT 0,
    line_7_capital_gain_loss    NUMERIC(12,2) DEFAULT 0,
    line_8_other_income         NUMERIC(12,2) DEFAULT 0,
    line_9_total_income         NUMERIC(12,2) DEFAULT 0,
    line_10_adjustments         NUMERIC(12,2) DEFAULT 0,
    line_11_agi                 NUMERIC(12,2) DEFAULT 0,
    line_12_deductions          NUMERIC(12,2) DEFAULT 0,
    line_13_qbi_deduction       NUMERIC(12,2) DEFAULT 0,
    line_14_total_deductions    NUMERIC(12,2) DEFAULT 0,
    line_15_taxable_income      NUMERIC(12,2) DEFAULT 0,
    line_16_tax                 NUMERIC(12,2) DEFAULT 0,
    -- ... lines 17-38 (credits, payments, refund/owed)

    -- Additional tax components
    self_employment_tax         NUMERIC(12,2) DEFAULT 0,
    additional_medicare_tax     NUMERIC(12,2) DEFAULT 0,
    net_investment_income_tax   NUMERIC(12,2) DEFAULT 0,
    alternative_minimum_tax     NUMERIC(12,2) DEFAULT 0,

    -- Rates
    effective_tax_rate          NUMERIC(6,4),
    marginal_tax_rate           NUMERIC(6,4),

    -- State
    state_code                  VARCHAR(2),
    state_tax_liability         NUMERIC(12,2) DEFAULT 0,
    state_refund_or_owed        NUMERIC(12,2) DEFAULT 0,

    -- Combined
    combined_tax_liability      NUMERIC(12,2) DEFAULT 0,
    combined_refund_or_owed     NUMERIC(12,2) DEFAULT 0,

    -- Metadata
    preparer_ptin               VARCHAR(20),
    firm_ein                    VARCHAR(20),
    tenant_id                   VARCHAR(100) NOT NULL,
    computation_details         JSONB,
    validation_results          JSONB,

    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_return_tenant ON tax_returns(tenant_id);
CREATE INDEX idx_return_ssn ON tax_returns(taxpayer_ssn_hash);
CREATE INDEX idx_return_year ON tax_returns(tax_year);
CREATE INDEX idx_return_status ON tax_returns(status);
```

#### **TaxpayerRecord** — Personal information (encrypted PII)
```sql
CREATE TABLE taxpayers (
    taxpayer_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    return_id       UUID NOT NULL REFERENCES tax_returns(return_id),
    ssn_hash        VARCHAR(64) NOT NULL,         -- HMAC-SHA256 for lookup
    ssn_encrypted   TEXT,                          -- AES-256 encrypted actual SSN
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    date_of_birth   DATE,
    is_primary      BOOLEAN DEFAULT TRUE,
    is_over_65      BOOLEAN DEFAULT FALSE,
    is_blind        BOOLEAN DEFAULT FALSE,
    is_deceased     BOOLEAN DEFAULT FALSE,
    date_of_death   DATE,

    -- Address
    address_line_1  VARCHAR(200),
    city            VARCHAR(100),
    state           VARCHAR(2),
    zip_code        VARCHAR(10),

    -- Banking (AES-256 encrypted)
    bank_routing_encrypted  TEXT,
    bank_account_encrypted  TEXT,
    account_type            VARCHAR(20),

    -- Spouse fields (mirrored structure)
    spouse_ssn_hash         VARCHAR(64),
    spouse_ssn_encrypted    TEXT,
    spouse_first_name       VARCHAR(100),
    spouse_last_name        VARCHAR(100),
    -- ... additional spouse fields

    ip_pin          VARCHAR(6),
    spouse_ip_pin   VARCHAR(6),
    tenant_id       VARCHAR(100) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

#### **IncomeRecord** — All income sources
```sql
CREATE TABLE income_records (
    income_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    return_id           UUID NOT NULL REFERENCES tax_returns(return_id),
    source_type         income_source_enum NOT NULL,
    -- W2_WAGES, SELF_EMPLOYMENT, INTEREST, DIVIDENDS,
    -- CAPITAL_GAINS_SHORT, CAPITAL_GAINS_LONG, RENTAL,
    -- PARTNERSHIP_K1, S_CORP_K1, TRUST_K1, etc.
    gross_amount        NUMERIC(12,2) NOT NULL,
    adjustments         NUMERIC(12,2) DEFAULT 0,
    taxable_amount      NUMERIC(12,2),
    federal_withholding NUMERIC(12,2) DEFAULT 0,
    state_withholding   NUMERIC(12,2) DEFAULT 0,
    payer_name          VARCHAR(200),
    payer_ein           VARCHAR(20),
    form_type           VARCHAR(20),
    is_foreign_source   BOOLEAN DEFAULT FALSE,
    is_passive_income   BOOLEAN DEFAULT FALSE,
    is_qbi_eligible     BOOLEAN DEFAULT FALSE,
    state_code          VARCHAR(2),
    tenant_id           VARCHAR(100) NOT NULL,
    created_at          TIMESTAMP DEFAULT NOW()
);
```

#### **Tenant** — Multi-tenant CPA firm configuration
```sql
CREATE TABLE tenants (
    tenant_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_name             VARCHAR(200) NOT NULL,
    status                  tenant_status_enum DEFAULT 'ACTIVE',
    -- ACTIVE, TRIAL, SUSPENDED, CANCELLED, PENDING_SETUP
    subscription_tier       subscription_tier_enum DEFAULT 'FREE',
    -- FREE, STARTER, PROFESSIONAL, ENTERPRISE, WHITE_LABEL

    -- White-label branding (JSONB for flexibility)
    branding                JSONB,
    -- {platform_name, logo_url, primary_color, secondary_color,
    --  favicon_url, support_email, terms_url, privacy_url,
    --  custom_css, custom_js, show_powered_by, ...}

    -- Feature flags (JSONB)
    features                JSONB,
    -- {express_lane, smart_tax, ai_chat, scenario_explorer,
    --  cpa_dashboard, custom_domain, api_access, ...}

    -- Limits
    max_returns_per_month   INTEGER DEFAULT 5,
    max_cpas                INTEGER DEFAULT 1,
    max_clients_per_cpa     INTEGER DEFAULT 10,
    max_storage_gb          INTEGER DEFAULT 1,

    -- Domain
    custom_domain           VARCHAR(255),
    custom_domain_verified  BOOLEAN DEFAULT FALSE,

    -- Billing
    stripe_customer_id      VARCHAR(100),
    subscription_expires_at TIMESTAMP,

    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);
```

#### **Additional Tables** (abbreviated — see `src/database/models.py` for full definitions)

| Table | Key Fields | Purpose |
|-------|-----------|---------|
| `w2_records` | employer_name, box_1-20, state_wages | W-2 form data |
| `form1099_records` | form_type (12 types), box amounts, wash_sale_loss | All 1099 variants |
| `deduction_records` | deduction_type (19 types), gross/limitation/allowed amounts | Itemized & above-line |
| `credit_records` | credit_type (13 types), phaseout calculations | Tax credits |
| `dependent_records` | relation_type (20 types), qualifying tests, credit eligibility | Dependents |
| `state_returns` | state_code, residency, brackets, local_tax | Per-state returns |
| `audit_logs` | event_type, hash_value, previous_log_id | Hash-chained audit |
| `computation_worksheets` | worksheet_type, lines (JSONB), final_result | IRS worksheets |
| `documents` | document_type, ocr_confidence, extracted_data | Uploaded docs |
| `extracted_fields` | field_name, value, confidence, bounding_box | OCR fields |
| `preparers` | credentials, firm_name, branding | CPA profiles |
| `clients` | preparer_id FK, ssn_hash, contact info | CPA's clients |
| `client_sessions` | tax_year, status, metrics, document_ids | Work sessions |
| `mfa_credentials` | secret_encrypted (AES-256-GCM), backup_codes | MFA data |
| `session_states` | session_id, data_json, agent_state_blob | Session persistence |
| `return_status` | cpa_reviewer_id, approval_signature_hash | CPA workflow |

### 3.3 Key Enums

```sql
CREATE TYPE filing_status_enum AS ENUM (
    'SINGLE', 'MARRIED_FILING_JOINTLY', 'MARRIED_FILING_SEPARATELY',
    'HEAD_OF_HOUSEHOLD', 'QUALIFYING_SURVIVING_SPOUSE'
);

CREATE TYPE return_status_enum AS ENUM (
    'DRAFT', 'IN_PROGRESS', 'PENDING_REVIEW', 'REVIEWED',
    'READY_TO_FILE', 'FILED', 'ACCEPTED', 'REJECTED',
    'AMENDED', 'ARCHIVED'
);

CREATE TYPE income_source_enum AS ENUM (
    'W2_WAGES', 'SELF_EMPLOYMENT', 'INTEREST', 'DIVIDENDS',
    'CAPITAL_GAINS_SHORT', 'CAPITAL_GAINS_LONG', 'RENTAL', 'ROYALTY',
    'RETIREMENT', 'SOCIAL_SECURITY', 'UNEMPLOYMENT',
    'PARTNERSHIP_K1', 'S_CORP_K1', 'TRUST_K1', 'OTHER'
);
```

### 3.4 Alembic Migrations (13 Versions)

| Migration | Purpose |
|-----------|---------|
| `20260116_0001_initial_schema` | Create all core tables + enums + indexes |
| `20260118_0001_admin_panel_tables` | preparers, clients, client_sessions |
| `20260118_0002_rbac_tables` | Permission tables, role assignments |
| `20260119_0001_repository_tables` | Event sourcing, domain events |
| `20260128_0001_add_missing_fk_indexes` | Foreign key indexes |
| `20260128_0002_add_ssn_and_fk_indexes` | SSN lookup performance |
| `20260129_0001_webhook_tables` | Webhook event tracking |
| `20260203_add_performance_indexes` | Composite query indexes |
| `20260205_0002_session_tables` | Session persistence (6 tables) |
| `20260206_0001_mfa_credential_tables` | MFA credentials + pending setups |
| `20260206_0002_additional_performance_indexes` | Additional tuning |
| `20260212_0001_add_missing_tables` | Gap filling |
| `20260217_0001_lead_magnet_tables` | Lead magnet/CRM tables |

---

## 4. API Architecture

### 4.1 API Design Principles

- **RESTful** — Resource-oriented endpoints with standard HTTP methods
- **Versioned** — `/api/v1/` prefix for future breaking changes
- **Authenticated** — JWT bearer tokens with role-based access
- **Tenant-Scoped** — All data operations scoped to authenticated tenant
- **Rate-Limited** — Per-endpoint throttling with circuit breaker
- **Idempotent** — Idempotency keys for POST operations
- **Auto-Documented** — OpenAPI/Swagger at `/docs`

### 4.2 Endpoint Catalog (25+ Route Files)

#### **Filing Workflow**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/sessions` | Create new filing session |
| GET | `/api/sessions/{id}` | Get session status and data |
| POST | `/api/sessions/{id}/upload` | Upload tax document |
| POST | `/api/sessions/{id}/calculate` | Run tax calculation |
| POST | `/api/sessions/{id}/submit` | Submit return for review |
| GET | `/api/sessions/{id}/computation` | Get computation worksheet |
| POST | `/api/sessions/{id}/export/pdf` | Generate PDF return |

#### **AI Tax Advisor**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/advisor/chat` | Send message to AI advisor |
| GET | `/api/advisor/session/{id}` | Get chat history |
| POST | `/api/advisor/acknowledge-standards` | Record Circular 230 acknowledgment |

#### **Tax Calculations**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/capital-gains/calculate` | Calculate capital gains/losses |
| POST | `/api/k1-basis/calculate` | K-1 basis tracking |
| POST | `/api/rental-depreciation/calculate` | Rental depreciation (MACRS) |
| POST | `/api/scenario/compare` | Compare tax scenarios |
| POST | `/api/smart-tax/analyze` | Smart tax suggestions |
| GET | `/api/smart-tax/deductions` | Available deduction detection |

#### **CPA Workspace**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/cpa/dashboard` | CPA dashboard overview |
| GET | `/api/cpa/clients` | List CPA's clients |
| POST | `/api/cpa/clients` | Add new client |
| GET | `/api/cpa/clients/{id}/sessions` | Client work sessions |
| PUT | `/api/cpa/branding` | Update CPA branding |
| POST | `/api/cpa/custom-domain` | Configure custom domain |

#### **Authentication & Security**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/auth/login` | Authenticate user |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/mfa/setup` | Initialize MFA setup |
| POST | `/api/auth/mfa/verify` | Verify MFA code |
| POST | `/api/auth/mfa/disable` | Disable MFA |

#### **Admin**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/admin/tenants` | List all tenants |
| POST | `/api/admin/tenants` | Create tenant |
| GET | `/api/admin/users` | List platform users |
| PUT | `/api/admin/features/{tenant_id}` | Update feature flags |
| GET | `/api/admin/metrics` | Platform metrics |

#### **System**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/health` | Health check |
| GET | `/api/health/live` | Liveness probe |
| GET | `/api/health/ready` | Readiness probe |
| GET | `/docs` | OpenAPI documentation |

### 4.3 Middleware Stack (Applied in Order)

```python
# 1. Security Headers (HSTS, X-Frame-Options, CSP, etc.)
app.add_middleware(SecurityHeadersMiddleware)

# 2. CSRF Protection (state-changing requests)
app.add_middleware(CSRFMiddleware, secret=CSRF_SECRET_KEY)

# 3. CORS (configurable origins)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS)

# 4. Rate Limiting (per-IP, per-user, per-endpoint)
app.add_middleware(RateLimitMiddleware)

# 5. Tenant Isolation (extract tenant_id from JWT, scope queries)
app.add_middleware(TenantIsolationMiddleware)

# 6. Request Validation (schema validation)
app.add_middleware(ValidationMiddleware)
```

### 4.4 Authentication Flow

```
1. POST /api/auth/login {email, password}
   → Verify credentials
   → Generate JWT {sub: user_id, role: PREPARER, tenant_id: ..., exp: +8h}
   → Return access_token + refresh_token

2. Authenticated Request:
   Authorization: Bearer <access_token>
   → Extract JWT claims
   → Set tenant_id in request context
   → All DB queries filtered by tenant_id

3. POST /api/auth/refresh {refresh_token}
   → Validate refresh_token (30-day expiry)
   → Issue new access_token
```

---

## 5. Business Logic Rules

### 5.1 Federal Tax Calculation Sequence

The calculation follows IRS Form 1040 line-by-line order with proper dependency resolution:

```
Step 1: Self-Employment Tax (affects AGI)
  ├── SE income × 0.9235 × 0.153 (12.4% SS + 2.9% Medicare)
  ├── SS wage base cap: $176,100 (2025)
  └── Deductible half of SE tax → adjustments

Step 2: Adjusted Gross Income (AGI)
  ├── Total income = W-2 + SE + interest + dividends + cap gains + rental + K-1 + other
  ├── Adjustments = IRA deduction + student loan interest + HSA + SE deduction
  └── AGI = Total income - Adjustments

Step 3: Deductions
  ├── Standard: Single $15,750 / MFJ $31,500 / HOH $22,500 (2025)
  ├── Additional for 65+/blind: Single +$1,950 / Married +$1,550
  ├── Itemized (Schedule A):
  │   ├── Medical > 7.5% AGI floor
  │   ├── SALT capped at $10,000 ($5,000 MFS)
  │   ├── Mortgage interest (≤$750K acquisition debt)
  │   └── Charitable (cash ≤60% AGI, appreciated property ≤30% AGI)
  └── Use greater of standard vs itemized

Step 4: QBI Deduction (Section 199A)
  ├── 20% of qualified business income
  ├── Below threshold ($197,300 single / $394,600 MFJ): full deduction
  ├── Above threshold: W-2 wage/UBIA limitation phases in
  └── SSTB: complete phaseout above range

Step 5: Taxable Income
  └── AGI - Deductions - QBI Deduction (floor: $0)

Step 6: Tax Computation
  ├── Ordinary income: Progressive brackets (10% → 37%)
  ├── Qualified dividends + LTCG: Preferential rates (0% / 15% / 20%)
  └── NIIT: 3.8% on lesser of NII or MAGI above threshold

Step 7: Alternative Minimum Tax (Form 6251)
  ├── AMTI = taxable income + AMT adjustments (SALT add-back, ISO, etc.)
  ├── AMT = max(0, (AMTI - exemption) × 26%/28% - regular tax)
  └── Prior year minimum tax credit (Form 8801)

Step 8: Credits (ordered application)
  ├── Nonrefundable (limited to tax liability):
  │   ├── Child Tax Credit ($2,000/child, phaseout at $200K/$400K)
  │   ├── Other Dependent Credit ($500/dependent)
  │   ├── Child Care Credit (Form 2441)
  │   ├── Education Credits (AOTC $2,500 / LLC $2,000)
  │   ├── Foreign Tax Credit (Form 1116)
  │   └── Retirement Savings Credit
  └── Refundable:
      ├── Earned Income Credit (EITC)
      ├── Additional Child Tax Credit ($1,700/child refundable)
      └── Premium Tax Credit (Form 8962)

Step 9: Payments & Penalties
  ├── Federal withholding (W-2, 1099)
  ├── Estimated tax payments (1040-ES)
  ├── Underpayment penalty (Form 2210): safe harbor = 100%/110% of prior year
  └── Estimated tax penalty calculation

Step 10: Refund or Amount Owed
  └── Payments + refundable credits - total tax liability
```

### 5.2 Key Phaseout Rules

| Credit/Deduction | Threshold (Single) | Threshold (MFJ) | Rate |
|------------------|-------------------|-----------------|------|
| Child Tax Credit | $200,000 | $400,000 | $50 per $1,000 over |
| EITC (3 children) | Phaseout starts ~$21,560 | Phaseout starts ~$28,120 | Gradual reduction |
| EITC investment income limit | $11,950 | $11,950 | Disqualified |
| Education Credits (AOTC) | $80,000-$90,000 | $160,000-$180,000 | Linear phaseout |
| Student Loan Interest | $75,000-$90,000 | $155,000-$185,000 | Linear phaseout |
| IRA Deduction (covered by plan) | $77,000-$87,000 | $123,000-$143,000 | Linear phaseout |
| QBI Deduction | $197,300-$247,300 | $394,600-$494,600 | Phase-in of limits |
| AMT Exemption | $626,350 | $1,252,700 | 25% of excess |
| Additional Medicare Tax | $200,000 | $250,000 | 0.9% on excess |
| NIIT | $200,000 | $250,000 | 3.8% on lesser of NII or excess |

### 5.3 2025 Tax Brackets

**Single:**
| Taxable Income | Rate |
|---------------|------|
| $0 – $11,925 | 10% |
| $11,925 – $48,475 | 12% |
| $48,475 – $103,350 | 22% |
| $103,350 – $197,300 | 24% |
| $197,300 – $250,525 | 32% |
| $250,525 – $626,350 | 35% |
| $626,350+ | 37% |

**Married Filing Jointly:**
| Taxable Income | Rate |
|---------------|------|
| $0 – $23,850 | 10% |
| $23,850 – $96,950 | 12% |
| $96,950 – $206,700 | 22% |
| $206,700 – $394,600 | 24% |
| $394,600 – $501,050 | 32% |
| $501,050 – $751,600 | 35% |
| $751,600+ | 37% |

### 5.4 State Tax Coverage

**All 50 States + DC implemented** via `src/calculator/state/configs/state_2025/`

| Category | States |
|----------|--------|
| No Income Tax | AK, FL, NV, SD, TN, TX, WA, WY, NH (interest/dividends only) |
| Flat Rate | CO, IL, IN, KY, MA, MI, NC, PA, UT |
| Progressive | CA (12.3%+1% millionaire), NY (10.9%), NJ, OR, HI, MN, etc. |
| Local Taxes | NYC, Philadelphia, MD counties, OH municipalities |

### 5.5 International Tax Rules (Implemented)

**Foreign Tax Credit (Form 1116):**
- 6 income categories (GILTI, Branch, Passive, General, 901(j), Lump-sum)
- FTC Limitation = US Tax × (Foreign Source Income / Worldwide Income)
- Carryback 1 year, carryforward 10 years (FIFO)
- Simplified method: foreign taxes ≤$300 ($600 MFJ) from qualified payees

**FEIE (Form 2555):**
- Maximum exclusion: $130,000 (2025)
- Housing base: $20,800 (16% of max)
- Housing limit: $39,000 (30% of max)
- Qualification: Physical Presence (330 days/12 months) or Bona Fide Residence

**Foreign Corporation (Form 5471):**
- Subpart F income inclusion
- GILTI (Global Intangible Low-Taxed Income)
- CFC (Controlled Foreign Corporation) reporting

### 5.6 381+ Business Rules

The `src/rules/` directory contains categorized tax rules:

| Rule File | Examples |
|-----------|---------|
| `virtual_currency_rules.py` | Crypto taxation, NFTs, airdrops |
| `foreign_assets_rules.py` | FBAR ($10K threshold), FATCA |
| `alimony_rules.py` | Pre-2019 vs post-2019 treatment |
| `k1_trust_rules.py` | Partnership/trust income allocation |
| `casualty_loss_rules.py` | Federally declared disaster losses |
| `household_employment_rules.py` | Nanny tax (Schedule H) |
| `wash_sale_rules.py` | 30-day wash sale enforcement (IRC §1091) |

---

## 6. AI Layer Design

### 6.1 Architecture

```
┌─────────────────────────────────────────────────────┐
│                   AI LAYER                           │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │            Intelligent Tax Agent              │   │
│  │  (LangChain 0.1.0 + OpenAI GPT-4O)          │   │
│  │                                               │   │
│  │  Stages:                                      │   │
│  │  1. personal_info → 2. income →              │   │
│  │  3. deductions → 4. credits → 5. review      │   │
│  └──────────┬────────────────────┬──────────────┘   │
│             │                    │                    │
│  ┌──────────▼──────┐  ┌────────▼───────────────┐   │
│  │ Smart Tax Engine│  │ Tax Law Citations       │   │
│  │                 │  │ (Top 20 IRC Sections)   │   │
│  │ • Complexity    │  │ • Auto-detect topics    │   │
│  │   Router        │  │ • Append references     │   │
│  │ • Deduction     │  │ • IRC + Pub + Form      │   │
│  │   Detector      │  │                         │   │
│  │ • Planning      │  └────────────────────────┘   │
│  │   Insights      │                                │
│  │ • Question      │  ┌────────────────────────┐   │
│  │   Generator     │  │ Confidence Scoring      │   │
│  └─────────────────┘  │ • profile_completeness  │   │
│                        │ • response_confidence   │   │
│  ┌─────────────────┐  │ • confidence_reason     │   │
│  │ Document OCR    │  └────────────────────────┘   │
│  │ Pipeline        │                                │
│  │ • Tesseract/    │  ┌────────────────────────┐   │
│  │   Google/Azure  │  │ Audit Trail Integration │   │
│  │ • TF-IDF        │  │ • model_version        │   │
│  │   Classification│  │ • prompt_hash          │   │
│  │ • Field         │  │ • calculation_inputs   │   │
│  │   Extraction    │  │ • citations_included   │   │
│  └─────────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 6.2 Conversational Tax Collection

The AI agent collects tax information through multi-stage conversation:

**Stage 1: Personal Information**
- Filing status, dependents, state of residence
- Age-related qualifiers (65+, blind)

**Stage 2: Income Collection**
- W-2 wages, self-employment, investment income
- Document upload prompts for OCR processing
- K-1 income from partnerships/trusts

**Stage 3: Deductions**
- Standard vs itemized comparison
- Mortgage interest, SALT, charitable, medical expense probing
- Business expense categorization

**Stage 4: Credits**
- Child Tax Credit eligibility
- Education credits (AOTC/LLC)
- Foreign tax credit for NRI clients
- EITC qualification check

**Stage 5: Review**
- Summary of all collected data
- Calculation preview
- Warning flags for missing information
- Professional consultation recommendation

### 6.3 Confidence Scoring

Every AI response includes confidence metadata:

```python
class ConfidenceScore:
    profile_completeness: float  # 0.0-1.0 (how much data collected)
    response_confidence: str     # "high" | "medium" | "low"
    confidence_reason: str       # Why this confidence level

# Rules:
# - "high": ≥80% profile complete, standard scenario
# - "medium": 50-80% complete, or complex scenario (AMT, intl)
# - "low": <50% complete, or unusual edge case
```

### 6.4 Tax Law Citations

Automatic citation injection for the top 20 IRC sections:

| Topic | IRC Section | IRS Publication |
|-------|------------|-----------------|
| Standard Deduction | IRC §63(c) | Pub 501 |
| Mortgage Interest | IRC §163(h) | Pub 936 |
| Child Tax Credit | IRC §24 | Pub 972 |
| Earned Income Credit | IRC §32 | Pub 596 |
| SALT Deduction | IRC §164 | Pub 17 |
| Charitable Contributions | IRC §170 | Pub 526 |
| Medical Expenses | IRC §213 | Pub 502 |
| IRA Contributions | IRC §219 | Pub 590-A |
| 401(k) Contributions | IRC §401(k) | Pub 560 |
| HSA Contributions | IRC §223 | Pub 969 |
| Capital Gains | IRC §1(h) | Pub 550 |
| QBI Deduction | IRC §199A | Pub 535 |
| Self-Employment Tax | IRC §1401 | Pub 334 |
| Estimated Tax | IRC §6654 | Pub 505 |
| Filing Status | IRC §1 | Pub 501 |
| Dependents | IRC §152 | Pub 501 |
| Education Credits | IRC §25A | Pub 970 |
| Student Loan Interest | IRC §221 | Pub 970 |
| AMT | IRC §55 | Form 6251 Instructions |
| Social Security | IRC §86 | Pub 915 |

### 6.5 AI Audit Trail

Every AI response is logged with full rationale:

```python
@dataclass
class AIResponseAuditEvent:
    session_id: str
    timestamp: datetime
    model_version: str          # "gpt-4o"
    prompt_hash: str            # SHA-256 of system prompt
    response_type: str          # greeting, question, calculation, strategy
    profile_completeness: float
    response_confidence: str
    confidence_reason: str
    user_message: str           # Truncated to 500 chars
    extracted_fields: dict
    calculation_inputs: dict
    response_summary: str       # First 200 chars
    citations_included: list
    warnings_triggered: list
```

### 6.6 Document OCR Pipeline

```
Upload → File Validation → Classification → OCR → Field Extraction → Mapping

OCR Engines:
├── Tesseract (default, free) — confidence threshold 70%
├── Google Vision (optional) — higher accuracy
└── Azure AI (optional) — enterprise

Document Types:
├── W-2 (19 box fields)
├── 1099-INT, 1099-DIV, 1099-B, 1099-R, 1099-NEC, 1099-MISC, 1099-K
├── 1098 (mortgage), 1098-E (student loan), 1098-T (tuition)
├── K-1 (partnership/S-corp/trust)
└── Other (bank statements, brokerage statements)

Classification: TF-IDF vectorizer with confidence scoring
Extraction: Template-based field mapping with type validation
Output: Normalized data mapped to tax form models
```

---

## 7. Compliance & Security

### 7.1 Data Protection

| Protection | Implementation | Files |
|-----------|---------------|-------|
| **SSN Encryption** | AES-256 at rest | `src/security/encryption.py` |
| **SSN Hashing** | HMAC-SHA256 for lookup | `src/security/ssn_hash.py` |
| **Bank Account Encryption** | AES-256 at rest | `src/database/encrypted_fields.py` |
| **MFA Secrets** | AES-256-GCM | `src/database/models.py` |
| **Data Sanitization** | PII removal from logs | `src/security/data_sanitizer.py` |
| **Secure Serialization** | HMAC-SHA256 | `src/security/secure_serializer.py` |
| **XML Injection Prevention** | Safe XML parser | `src/security/safe_xml.py` |
| **File Upload Security** | Type/size/content validation | `src/security/file_upload_security.py` |

### 7.2 Authentication & Authorization

```
JWT Authentication:
├── Algorithm: HS256
├── Access Token: 8-hour expiry
├── Refresh Token: 30-day expiry
├── Claims: sub, role, tenant_id, permissions, exp, iat, jti
└── Revocation: Redis-backed token blacklist

RBAC (Role-Based Access Control):
├── TAXPAYER — End user filing taxes
├── PREPARER — CPA/tax preparer (manages clients)
├── REVIEWER — Senior reviewer (approves returns)
├── ADMIN — Platform administrator
├── 8 total roles with granular permissions
└── Feature-level access control per subscription tier

Decorators:
├── @require_auth — Require valid JWT
├── @require_role("ADMIN") — Role-based gating
├── @require_session_owner — Session ownership verification
└── @rate_limit(10, "minute") — Per-endpoint throttling
```

### 7.3 Circular 230 Compliance

Per IRS Circular 230 requirements, the platform implements:

1. **Professional Standards Acknowledgment** — Modal requires checkbox acceptance before AI advisor use
2. **Scope Limitation Banner** — Persistent banner on all tax advisory pages
3. **Session Persistence** — Acknowledgment stored in session (server-side)
4. **Audit Logging** — All acknowledgments logged with timestamp, IP, and user agent
5. **Disclaimer Text** — "This is NOT professional tax advice" + "Consult a qualified tax professional"

### 7.4 Audit Trail

**HMAC Hash-Chained Audit Events:**
```
Every audit entry contains:
├── event_type (200+ event types)
├── timestamp (immutable)
├── user_id, user_role, ip_address
├── field_name, old_value, new_value (for data changes)
├── previous_log_id (chain link)
└── hash_value (SHA-256: hash(event_data + previous_hash))

Guarantees:
├── Immutability — Cannot modify without breaking hash chain
├── Completeness — Every data change logged
├── Non-repudiation — User/IP/timestamp for every action
└── CPA Compliance — Full audit for IRS examination defense
```

### 7.5 Security Middleware Stack

| Middleware | Purpose |
|-----------|---------|
| SecurityHeadersMiddleware | HSTS, X-Frame-Options, CSP, X-Content-Type-Options |
| CSRFMiddleware | Double-submit cookie CSRF protection |
| CORSMiddleware | Configurable origin allowlist |
| RateLimitMiddleware | Per-IP and per-user rate limiting |
| TenantIsolationMiddleware | Extract tenant_id, enforce data boundaries |
| ValidationMiddleware | Request schema validation |

### 7.6 Fraud Detection

```python
# src/security/fraud_detector.py
FraudDetector:
├── Anomalous refund amounts (>3σ from user history)
├── Multiple SSN submissions from same IP
├── Rapid-fire return submissions
├── Inconsistent income patterns
└── Known fraud indicator patterns
```

---

## 8. Deployment Pipeline

### 8.1 Infrastructure

```
Production Stack:
├── Render.com (Web Service)
│   ├── Runtime: Python 3.11+
│   ├── Workers: 2 (Gunicorn + UvicornWorker)
│   ├── Timeout: 120s (for LLM responses)
│   ├── Health Check: /api/health
│   └── Auto-deploy: GitHub push to main
│
├── Neon (PostgreSQL)
│   ├── Serverless PostgreSQL 14+
│   ├── Auto-scaling, branching
│   └── Free tier: 512MB storage
│
├── Upstash (Redis)
│   ├── Serverless Redis
│   ├── Session cache + rate limiting
│   └── Free tier: 10K commands/day
│
└── OpenAI API
    ├── GPT-4O for tax advisory
    └── Pay-per-use pricing
```

### 8.2 Docker Configuration

```dockerfile
# Multi-stage build
# Stage 1: Builder — install dependencies
FROM python:3.11-slim AS builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Production — minimal runtime
FROM python:3.11-slim AS production
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
HEALTHCHECK CMD curl -f http://localhost:8000/health/live
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 8.3 Docker Compose Services

| Service | Purpose | Profile |
|---------|---------|---------|
| `app` | FastAPI application | default |
| `redis` | Session cache | with-redis |
| `nginx` | Reverse proxy | production |
| `worker` | Background tasks | with-workers |

### 8.4 Environment Configuration

**Required Secrets (auto-generated on Render):**
```
APP_SECRET_KEY          # ≥32 chars — application secret
JWT_SECRET              # ≥32 chars — JWT signing key
CSRF_SECRET_KEY         # ≥32 chars — CSRF protection
ENCRYPTION_MASTER_KEY   # ≥32 chars — AES-256 master key (CRITICAL: losing = data loss)
SSN_HASH_SECRET         # ≥32 chars — HMAC-SHA256 SSN hashing
AUTH_SECRET_KEY         # ≥32 chars — authentication secret
PASSWORD_SALT           # ≥16 chars — password hashing salt
```

**Required External Services:**
```
DATABASE_URL            # Neon PostgreSQL connection string
REDIS_URL               # Upstash Redis connection string
OPENAI_API_KEY          # OpenAI API key for AI features
```

**Feature Flags:**
```
UNIFIED_FILING=true     # Enable unified filing system
DB_PERSISTENCE=true     # Enable database persistence
NEW_LANDING=true        # Enable new landing page
SCENARIOS_ENABLED=true  # Enable scenario explorer
```

### 8.5 CI/CD Pipeline

```yaml
# .github/workflows/
├── test.yml           # Run pytest on PR
├── lint.yml           # Code quality checks
└── deploy.yml         # Auto-deploy to Render on main push

# Render auto-deploy:
# 1. Push to main
# 2. Render detects change
# 3. scripts/build.sh runs (install deps, run migrations)
# 4. Gunicorn starts with UvicornWorker
# 5. Health check passes → traffic routed
```

### 8.6 Monitoring

```
Health Endpoints:
├── /api/health         # Full health check (DB, Redis, AI)
├── /api/health/live    # Liveness probe (process alive)
└── /api/health/ready   # Readiness probe (dependencies ready)

Logging:
├── JSON-formatted (production) — structured log aggregation
├── Human-readable (development) — developer convenience
└── PII-redacted — SSN masking, data sanitization in all logs
```

---

## 9. Monetization Model

### 9.1 Subscription Tiers

| Tier | Price | Returns/Month | CPAs | Clients/CPA | Storage | Key Features |
|------|-------|---------------|------|-------------|---------|-------------|
| **FREE** | $0 | 5 | 1 | 10 | 1 GB | Basic filing, AI chat (limited) |
| **STARTER** | $49/mo | 50 | 3 | 50 | 10 GB | Smart tax, document OCR, scenarios |
| **PROFESSIONAL** | $149/mo | 200 | 10 | 200 | 50 GB | CPA dashboard, advisory reports, premium PDFs |
| **ENTERPRISE** | $399/mo | Unlimited | Unlimited | Unlimited | 500 GB | Custom domain, API access, white-label, collaboration |
| **WHITE_LABEL** | Custom | Unlimited | Unlimited | Unlimited | Unlimited | Remove all branding, custom email, full API |

### 9.2 Feature Matrix by Tier

| Feature | Free | Starter | Professional | Enterprise | White-Label |
|---------|------|---------|-------------|------------|-------------|
| Federal tax calculation | ✓ | ✓ | ✓ | ✓ | ✓ |
| State tax (all 50) | ✓ | ✓ | ✓ | ✓ | ✓ |
| AI tax advisor | Limited | ✓ | ✓ | ✓ | ✓ |
| Document OCR | — | ✓ | ✓ | ✓ | ✓ |
| Express Lane filing | — | ✓ | ✓ | ✓ | ✓ |
| Smart Tax engine | — | ✓ | ✓ | ✓ | ✓ |
| Scenario explorer | — | ✓ | ✓ | ✓ | ✓ |
| Tax projections | — | — | ✓ | ✓ | ✓ |
| CPA dashboard | — | — | ✓ | ✓ | ✓ |
| Advisory reports | — | — | ✓ | ✓ | ✓ |
| Premium PDF exports | — | — | ✓ | ✓ | ✓ |
| Multi-CPA support | — | — | ✓ | ✓ | ✓ |
| Custom domain | — | — | — | ✓ | ✓ |
| API access | — | — | — | ✓ | ✓ |
| Remove branding | — | — | — | — | ✓ |
| Custom email sender | — | — | — | — | ✓ |

### 9.3 Revenue Streams

1. **SaaS Subscriptions** — Primary revenue from CPA firms
2. **Lead Revenue Sharing** — 15% revenue share on leads connected to CPAs (12% for high-value)
3. **Per-Return Pricing** — Optional pay-per-return model for overflow
4. **White-Label Licensing** — Custom pricing for branded platform deployments
5. **API Access** — Metered API usage for Enterprise/White-Label tiers

### 9.4 Lead Funnel Configuration

```python
LEAD_REVENUE_SHARE_PERCENT = 15.0       # Standard lead revenue share
HIGH_VALUE_REVENUE_SHARE_PERCENT = 12.0  # Discount for high-value CPAs
AUTO_ASSIGNMENT_ENABLED = True           # Auto-assign leads to CPAs
ASSIGNMENT_ALGORITHM = "round_robin"     # round_robin | weighted | geographic
MAX_LEADS_PER_CPA_PER_DAY = 10
SEND_REPORT_TO_LEAD = True              # Email tax report to lead
SEND_REPORT_TO_CPA = True               # Email lead report to assigned CPA
SEND_HOT_LEAD_ALERTS = True             # Real-time alerts for high-value leads
AUTO_ENROLL_NURTURE = True              # Auto-enroll leads in email nurture
```

---

## 10. Phase-Wise Roadmap

### Phase 1: Foundation (Current State — Complete)

**Status: Production-Ready**

| Component | Status | Details |
|-----------|--------|---------|
| Federal Tax Engine | ✅ Complete | 7 brackets, all filing statuses, 2022-2026 configs |
| 58+ IRS Forms | ✅ Complete | Full model definitions with Pydantic validation |
| 50 State Calculators | ✅ Complete | All states + DC + local taxes |
| AMT/QBI/EITC/CTC | ✅ Complete | Full phaseout logic |
| International Forms | ✅ Complete | 1116, 2555, 5471, FBAR/FATCA |
| AI Tax Advisor | ✅ Complete | LangChain + GPT-4O conversational agent |
| Document OCR | ✅ Complete | Tesseract + field extraction pipeline |
| Multi-Tenant SaaS | ✅ Complete | Tenant isolation, branding, feature flags |
| CPA Dashboard | ✅ Complete | Client management, session tracking |
| Authentication | ✅ Complete | JWT + MFA + RBAC (8 roles) |
| Audit Trail | ✅ Complete | HMAC hash-chained + AI response audit |
| Tax Citations | ✅ Complete | Top 20 IRC sections auto-injected |
| Circular 230 | ✅ Complete | Acknowledgment modal + scope banner |
| Confidence Scores | ✅ Complete | Profile completeness + response confidence |
| Edge Case Tests | ✅ Complete | 27+ tests (phaseouts, AMT, brackets, etc.) |
| PDF Export | ✅ Complete | Professional reports, computation statements |
| Deployment | ✅ Complete | Render + Neon + Upstash + Docker |
| Test Suite | ✅ Complete | 4100+ tests, 208 test files |

### Phase 2: India-US DTAA Specialization

**Goal: Make the platform uniquely valuable for Indian CAs serving NRI clients**

| Task | Priority | Description |
|------|----------|-------------|
| DTAA Engine | P0 | India-US Tax Treaty Articles 10-23 implementation (dividends 15%, interest 15%, royalties 15%, capital gains, pensions) |
| NRI Status Classifier | P0 | Substantial Presence Test (US), 182-day rule (India), treaty tiebreaker resolution |
| Form 8833 Generator | P0 | Treaty-based return position disclosure automation |
| INR→USD Converter | P1 | IRS-approved exchange rates (annual average or transaction-date per Treasury reporting rates) |
| Indian TDS Mapper | P1 | Map TDS certificates (Form 16, 16A, 26AS) to Form 1116 FTC categories |
| India Income Mapper | P1 | Indian salary components (HRA, DA, LTA) → US W-2 equivalent mapping |
| PFIC Analysis | P1 | Indian mutual fund PFIC analysis (most Indian MFs are PFICs for US persons) |
| India Retirement | P2 | EPF/PPF/NPS US tax treatment under Article 20 |
| FBAR/FATCA India | P2 | India-specific account identification and reporting |

### Phase 3: Advanced AI & Automation

| Task | Priority | Description |
|------|----------|-------------|
| Multi-LLM Support | P1 | Add Claude, Gemini as alternative LLM providers |
| AI Tax Strategy | P1 | Proactive tax optimization recommendations with projected savings |
| Year-over-Year Comparison | P1 | Automated comparison with prior year returns |
| Batch Document Processing | P2 | Process multiple documents in parallel |
| Natural Language Filing | P2 | "File my taxes" end-to-end voice/chat workflow |
| Property-Based Testing | P2 | Hypothesis-based fuzzing for calculation engine |

### Phase 4: E-Filing & Compliance

| Task | Priority | Description |
|------|----------|-------------|
| IRS MeF Integration | P0 | Electronic filing via IRS Modernized e-File |
| State E-Filing | P1 | State-by-state e-file integration |
| EFIN Management | P1 | Electronic Filing Identification Number management |
| E-Signature | P1 | IRS-compliant digital signature (Form 8879) |
| IRS Account API | P2 | Pull transcripts, check refund status |
| Amended E-File | P2 | Form 1040-X electronic filing |

### Phase 5: Scale & Enterprise

| Task | Priority | Description |
|------|----------|-------------|
| Horizontal Scaling | P1 | Kubernetes deployment, auto-scaling |
| Real-time Collaboration | P1 | Multi-CPA working on same return |
| Client Portal | P1 | Self-service portal for taxpayers |
| Mobile App | P2 | iOS/Android native apps |
| QuickBooks Integration | P2 | Import income/expense from accounting |
| Stripe Billing | P2 | Automated subscription billing |
| SOC 2 Compliance | P2 | SOC 2 Type II certification |
| IRS Circular 230 Full | P2 | Full engagement letters, conflict tracking |

---

## Appendix A: Codebase Statistics

| Metric | Value |
|--------|-------|
| Total Python Files | 663 |
| Total Test Files | 208 |
| Total Passing Tests | 4,100+ |
| Total Source Directories | 43 modules |
| IRS Form Models | 58+ |
| State Tax Calculators | 50 + DC |
| Tax Business Rules | 381+ |
| API Route Files | 25+ |
| Database Tables | 30+ |
| Alembic Migrations | 13 |
| Lines of Code (estimated) | ~80,000+ |

## Appendix B: Configuration Reference

See `.env.example` (265 lines) for full environment variable documentation. Key categories:

- **Application** — APP_ENVIRONMENT, DEBUG, LOG_LEVEL, HOST, PORT, WORKERS
- **Database** — DATABASE_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW
- **Redis** — REDIS_URL, SESSION_STORAGE_TYPE
- **Security** — JWT_SECRET, ENCRYPTION_MASTER_KEY, SSN_HASH_SECRET (all ≥32 chars)
- **JWT** — JWT_ALGORITHM (HS256), ACCESS_TOKEN_EXPIRE_SECONDS (28800), REFRESH_TOKEN_EXPIRE_DAYS (30)
- **Sessions** — SESSION_EXPIRY_HOURS (24), SESSION_TIMEOUT_MINUTES (30)
- **AI** — OPENAI_API_KEY, OPENAI_MODEL (gpt-4o)
- **OCR** — OCR_PROVIDER (tesseract/google/aws), OCR_CONFIDENCE_THRESHOLD (70)
- **Upload** — MAX_UPLOAD_SIZE_MB (10), ALLOWED_FILE_TYPES
- **Branding** — PLATFORM_NAME, COMPANY_NAME, SUPPORT_EMAIL
- **Features** — UNIFIED_FILING, DB_PERSISTENCE, NEW_LANDING, SCENARIOS_ENABLED
- **Lead Funnel** — LEAD_REVENUE_SHARE_PERCENT, ASSIGNMENT_ALGORITHM, MAX_LEADS_PER_CPA_PER_DAY

---

*Generated 2026-02-25 | Jorss-Gbo Platform v1.0 | 663 Python files, 4100+ tests, 50 states + DC*
